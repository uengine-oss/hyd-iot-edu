"""Durable new-generation requests, serialized with claims/submissions/timers."""
from copy import deepcopy
import uuid

from . import engine, rework


class ReworkRuntime:
    def _rework_proposal(self, inst, workitem_id):
        from . import rework_effects
        defn = self.definition_for(inst)
        work = self.repo.list_workitems(proc_inst_id=inst['proc_inst_id'], limit=None)
        approvals = self.repo.list_approvals(inst['proc_inst_id'], self.tenant_id)
        proposal = rework.plan(defn, inst, work, workitem_id, approvals)
        # A generation cancels future TODO services too. Its administrative log
        # is not execution evidence. Exempt only an exact cancellation proven by
        # the immutable receipt and original TODO status, never arbitrary logs.
        never_started = set()
        by_id = {w['id']: w for w in work}
        for receipt in self.repo.list_reworks(self.tenant_id, inst['proc_inst_id']):
            result = receipt['result']
            for prior in result['plan']['affected_workitems']:
                row = by_id.get(prior['id'])
                if (prior['status'] == 'TODO' and prior['id'] in result['cancelled'] and row
                        and row['status'] == 'CANCELLED' and not row.get('output')
                        and row.get('log') == f"rework superseded: {receipt['request_id']}; "):
                    never_started.add(prior['id'])
        proposal['started_services'] = [wid for wid in proposal['started_services'] if wid not in never_started]
        proposal['blockers'] = [b for b in proposal['blockers']
            if not (b['code'] == 'service_effects_require_review' and b.get('workitem') in never_started)]
        proposal['execution_available'] = not proposal['blockers'] and bool(proposal['request_roles'])
        if engine.variables(inst).get('incident') and self.hooks.rework_effects is not None:
            evidence = self.hooks.rework_effects(deepcopy(inst))
            # Previously reviewed, unissued commands may have administrative
            # cancellation logs. Admit only exact rows from immutable receipts,
            # and only while the entire case still has no external effects.
            if rework_effects.no_effects(evidence, approvals):
                for receipt in self.repo.list_reworks(self.tenant_id, inst['proc_inst_id']):
                    result = receipt['result']
                    for prior in result['plan'].get('unissued_command_evidence', []):
                        row = by_id.get(prior['id'])
                        if (row and prior['id'] in result['cancelled'] and prior['status'] == 'PENDING'
                                and row['status'] == 'CANCELLED' and not row.get('output')
                                and row.get('log') == (prior.get('log') or '') + f"rework superseded: {receipt['request_id']}; "):
                            never_started.add(prior['id'])
                proposal['started_services'] = [wid for wid in proposal['started_services'] if wid not in never_started]
                proposal['blockers'] = [b for b in proposal['blockers']
                    if not (b['code'] == 'service_effects_require_review' and b.get('workitem') in never_started)]
            proposal = rework_effects.admit(proposal, defn, inst, work, approvals, evidence)
        return proposal

    def request_rework(self, proc_inst_id, workitem_id, request_id, snapshot_token, by, role, reason, now=None):
        try:
            request_id = str(uuid.UUID(request_id))
        except (ValueError, TypeError, AttributeError):
            raise ValueError('재작업 요청 ID는 UUID여야 합니다')
        if not all(isinstance(v, str) and v.strip() for v in (snapshot_token, by, role, reason)):
            raise ValueError('관측 token, 요청자, 역할, 사유가 필요합니다')
        request = dict(workitem_id=workitem_id, snapshot_token=snapshot_token, by=by, role=role, reason=reason)
        with self._transition(proc_inst_id):
            inst = self.repo.get_instance(proc_inst_id)
            defn = self.definition_for(inst)
            human_roles = {defn.role_endpoint(a.get('role')) for a in defn.activities.values() if a['type'] in engine.USER_TYPES}
            if role not in human_roles:
                raise PermissionError('고정 정의의 사람 업무 담당 역할로 요청하세요')
            prior = self.repo.get_rework(self.tenant_id, proc_inst_id, request_id)
            if prior:
                if prior['request'] != request:
                    raise ValueError('같은 요청 ID에 다른 재작업 내용을 사용할 수 없습니다')
                return deepcopy(prior['result'])
            work = self.repo.list_workitems(proc_inst_id=proc_inst_id, limit=None)
            proposal = self._rework_proposal(inst, workitem_id)
            if proposal['snapshot_token'] != snapshot_token:
                raise ValueError('미리보기 이후 실행 상태가 바뀌었습니다. 영향 범위를 다시 확인하세요')
            if not proposal['execution_available']:
                raise ValueError('재작업 검토가 필요합니다: ' + ', '.join(b['code'] for b in proposal['blockers']))
            for wid in proposal.get('retire_approvals', []):
                _, approval = self._discard_owner(wid, by, role)
                previous_status = approval['status']
                approval['status'] = 'DISCARDED'
                approval['history'].append({'status': 'DISCARDED', 't': engine.now_iso(now),
                    'previous_status': previous_status,
                    'request_id': request_id, 'by': by, 'role': role, 'reason': reason,
                    'via': 'rework', 'effects': deepcopy(proposal['effects'])})
                self.repo.update_approval(approval)
            adv = rework.new_generation(defn, inst, work, proposal, request_id, now, self.time_scale)
            for row in adv.updated:
                self.repo.update_workitem(row)
            self.repo.insert_workitems(adv.created)
            self.repo.update_instance(inst)
            result = {'request_id': request_id, 'instance': proc_inst_id, 'generation': inst['rework_generation'],
                      'start_workitem': next(w['id'] for w in adv.created if w.get('supersedes_id') == workitem_id), 'created': deepcopy(adv.created),
                      'cancelled': [w['id'] for w in adv.updated], 'plan': proposal,
                      'by': by, 'role': role, 'reason': reason, 'at': engine.now_iso(now)}
            self.repo.insert_rework({'tenant_id': self.tenant_id, 'proc_inst_id': proc_inst_id, 'request_id': request_id,
                                    'generation': inst['rework_generation'], 'request': request, 'result': result})
            self.repo.record_events([{'job_id': 'PROCESS_REWORK', 'todo_id': result['start_workitem'],
                'proc_inst_id': proc_inst_id, 'crew_type': 'human', 'event_type': 'task_working',
                'data': {'name': '새 작업 세대 시작', 'request_id': request_id, 'generation': inst['rework_generation'],
                         'by': by, 'role': role, 'reason': reason, 'previous': workitem_id}}])
            self._after_commit(self._project, inst)
            for row in adv.reached:
                if row['status'] == 'SUBMITTED' and row.get('agent_orch') == engine.PROCESS_ORCH:
                    self._after_commit(self._run_service, inst, row, now)
        return result
