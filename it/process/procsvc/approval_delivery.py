"""Approval delivery belongs to the instance, and never advances on failure.

The owning instance transaction serializes concurrent dispatchers. A process
crash rolls back the delivery marker, so external operations must be idempotent
under the saved decision/skill key. PLC commands are reached only afterwards.
"""
from copy import deepcopy

from hydcommon.timeutil import now_iso
from . import decisions, engine, rework_effects


class ApprovalDelivery:
    def _discard_owner(self, wid, by, role):
        wi = self.repo.get_workitem(wid)
        if not wi or wi.get('tenant_id') != self.tenant_id:
            raise KeyError('no such approval work item')
        row = self.repo.get_approval(wid, self.tenant_id)
        if not row:
            raise KeyError('no such approval')
        if not isinstance(by, str) or not by.strip() or not isinstance(role, str) or not role.strip():
            raise ValueError('요청자와 역할을 입력하세요')
        snapshot = deepcopy(row['payload']['plan'].get('_snapshot'))
        if not snapshot or role not in (snapshot.get('roles') or {}):
            raise PermissionError('승인 원문의 복구 역할을 확인할 수 없습니다')
        snapshot['state'] = 'PENDING_APPROVAL'
        decisions.approve(snapshot, row['payload']['option'], by, role, 'retire failed consent')
        return wi, row

    def _discard_evidence(self, wi, row):
        inst = self.repo.get_instance(wi['proc_inst_id'])
        eligible = (row['status'] == 'FAILED' and wi['status'] == 'SUBMITTED') or (row['status'] == 'DELIVERED' and wi['status'] == 'DONE')
        if (not eligible
                or inst['status'] != 'RUNNING' or inst.get('is_deleted')):
            raise ValueError('진행 중 인스턴스의 전달 실패 또는 미실행 승인만 폐기할 수 있습니다')
        if any(a['todo_id'] != wi['id'] and a['status'] != 'DISCARDED'
               for a in self.repo.list_approvals(wi['proc_inst_id'], self.tenant_id)):
            raise ValueError('다른 승인과 효과를 먼저 확인해야 합니다')
        defn = self.definition_for(inst)
        work = self.repo.list_workitems(proc_inst_id=wi['proc_inst_id'], limit=None)
        if self.hooks.rework_effects is None:
            raise ValueError('사건 전체 효과 조회가 연결되지 않았습니다')
        approvals = self.repo.list_approvals(wi['proc_inst_id'], self.tenant_id)
        case = self.hooks.rework_effects(deepcopy(inst))
        if not rework_effects.no_effects(case, approvals):
            raise ValueError('기존 조치 또는 불명확한 실행 기록이 있어 효과 확인/보상이 필요합니다')
        unissued = rework_effects.unissued_commands(defn, inst, work, approvals, case)
        if row['status'] == 'DELIVERED' and not unissued:
            raise ValueError('승인에 연결된 미실행 보류 명령을 확인할 수 없습니다')
        for item in work:
            if item['id'] in unissued:
                continue
            activity = defn.activities.get(item['activity_id']) or {}
            if activity.get('type') in engine.SERVICE_TYPES and item['status'] not in {'TODO', 'CANCELLED'}:
                raise ValueError('이미 시작된 서비스의 효과 확인/보상이 필요합니다')
            if (item['id'] != wi['id'] and item['activity_id'] not in defn.events
                    and item['status'] in engine.LIVE_STATUSES):
                raise ValueError('다른 진행 중 작업이 있어 인스턴스를 종료할 수 없습니다')
        if self.hooks.approval_effects is None:
            raise ValueError('효과 조회가 연결되지 않았습니다')
        effects = self.hooks.approval_effects(deepcopy(row))
        effects['case'] = case
        effects['unissued_commands'] = sorted(unissued)
        incident = effects['incident']
        if incident['state'] not in {'RESOLVED_WITHOUT_ACTION', 'REJECTED_BY_OPERATOR', 'ESCALATED'}:
            raise ValueError('활성 사건은 새 판단 재작업이나 별도 종료 검토가 필요합니다')
        if (incident.get('cmdId') or incident.get('workOrder') or incident.get('workOrderRequest')
                or effects['enterprise_receipts'] or effects['local_executions'] or effects['delivery_results']):
            raise ValueError('기존 조치 또는 불명확한 실행 기록이 있어 효과 확인/보상이 필요합니다')
        return inst, work, effects

    def preview_approval_discard(self, wid, by, role):
        wi, _ = self._discard_owner(wid, by, role)
        with self._transition(wi['proc_inst_id']):
            wi, row = self._discard_owner(wid, by, role)
            inst, work, effects = self._discard_evidence(wi, row)
            return {'can_discard': True, 'approval': wid, 'instance': inst['proc_inst_id'],
                    **effects, 'cancel_workitems': [w['id'] for w in work if w['status'] not in engine.TERMINAL_STATUSES],
                    'outcome': '승인 이력을 보존하고 인스턴스를 CANCELLED로 종료합니다. 사건 상태와 외부 효과를 변경하지 않습니다.'}

    def discard_approval(self, wid, by, role, reason, request_id, now=None):
        if not isinstance(reason, str) or not reason.strip() or not isinstance(request_id, str) or not request_id.strip():
            raise ValueError('폐기 사유와 중복 방지 요청 ID가 필요합니다')
        wi, _ = self._discard_owner(wid, by, role)
        with self._transition(wi['proc_inst_id']):
            wi, row = self._discard_owner(wid, by, role)
            if row['status'] == 'DISCARDED':
                prior = row['history'][-1]
                if all(prior.get(k) == v for k, v in dict(request_id=request_id, by=by, role=role, reason=reason).items()):
                    return row
                raise ValueError('이미 다른 폐기 요청으로 처리됐습니다')
            inst, work, effects = self._discard_evidence(wi, row)
            record = {'status': 'DISCARDED', 'previous_status': row['status'], 't': engine.now_iso(now), 'request_id': request_id,
                      'by': by, 'role': role, 'reason': reason, 'effects': effects}
            row['status'] = 'DISCARDED'
            row['history'].append(record)
            self.repo.update_approval(row)
            for item in work:
                if item['status'] not in engine.TERMINAL_STATUSES:
                    item.update(status='CANCELLED', consumer=None, end_date=engine.now_iso(now),
                                log=(item.get('log') or '') + f'approval discarded: {request_id}; ')
                    self.repo.update_workitem(item)
            inst.update(status='CANCELLED', current_activity_ids=[], end_date=engine.now_iso(now),
                        end_event='administrative:approval-discard')
            self.repo.update_instance(inst)
            self.repo.record_events([{'job_id': 'APPROVAL_DISCARDED', 'todo_id': wid, 'proc_inst_id': wi['proc_inst_id'],
                'crew_type': 'human', 'event_type': 'task_working', 'data': {'name': '승인 폐기·인스턴스 취소', **record}}])
            self._after_commit(self._project, inst)
        return self.repo.get_approval(wid, self.tenant_id)

    def reconcile_approvals(self, now=None):
        count, after = 0, None
        while True:
            rows = self.repo.pending_approvals(self.tenant_id, after_id=after)
            if not rows:
                return count
            for row in rows:
                self.deliver_approval(row['todo_id'], now=now)
                count += 1
            after = rows[-1]['todo_id']

    def deliver_approval(self, wid, now=None):
        wi = self.repo.get_workitem(wid)
        if not wi or wi.get('tenant_id') != self.tenant_id:
            raise KeyError('no such approval work item')
        with self._transition(wi['proc_inst_id']):
            row = self.repo.get_approval(wid, self.tenant_id)
            wi = self.repo.get_workitem(wid)
            inst = self.repo.get_instance(wi['proc_inst_id'])
            if not row or row['status'] != 'PENDING':
                return
            if inst['status'] != 'RUNNING' or inst.get('is_deleted') or wi['status'] != 'SUBMITTED':
                return
            row['attempts'] += 1
            try:
                # The hook applies only the committed snapshot. It does not send PLC commands.
                if self.hooks.deliver_approval is not None:
                    results = self.hooks.deliver_approval(deepcopy(row))
                else:
                    results = [self.hooks.exec_enterprise(row['decision_id'], item)
                               for item in row['payload']['plan'].get('enterprise', [])
                               if item.get('code') != 'WO_CREATE']
                if any(r.get('ok') is not True for r in results):
                    raise RuntimeError(str([r for r in results if r.get('ok') is not True]))
            except Exception as error:
                row.update(status='FAILED', error=f'{type(error).__name__}: {str(error)[:500]}')
                row['history'].append({'status':'FAILED', 't':engine.now_iso(now), 'error':row['error']})
                self.repo.update_approval(row)
                self.repo.record_events([{'job_id':'APPROVAL_DELIVERY', 'todo_id':wid,
                    'proc_inst_id':wi['proc_inst_id'], 'crew_type':'human', 'event_type':'error',
                    'data':{'name':'승인 전달 실패', 'approval':wid, 'error':row['error'], 'attempt':row['attempts']}}])
                return
            row.update(status='DELIVERED', error=None, results=results)
            row['history'].append({'status':'DELIVERED', 't':engine.now_iso(now)})
            self.repo.update_approval(row)
            self.repo.record_events([{'job_id':'APPROVAL_DELIVERY', 'todo_id':wid,
                'proc_inst_id':wi['proc_inst_id'], 'crew_type':'human', 'event_type':'task_working',
                'data':{'name':'승인 전달 완료', 'approval':wid, 'results':results, 'attempt':row['attempts']}}])
            wi['consumer'] = self.consumer
            self.repo.update_workitem(wi)
            self.process_workitem(wi, now=now)
            v = engine.variables(inst)
            self._after_commit(self.hooks.audit, v.get('asset', '-'), row['payload']['by'],
                'DECISION_APPROVED', {'decision':row['decision_id'], 'option':row['payload']['option'],
                 'role':row['payload']['role'], 'approval':wid, 'via':'durable instance approval'},
                incident=v.get('incident'))
            self._after_commit(self.hooks.record_approval, deepcopy(row))

    def retry_approval(self, wid, by, role=None, now=None):
        wi = self.repo.get_workitem(wid)
        if not wi or wi.get('tenant_id') != self.tenant_id:
            raise KeyError('no such approval work item')
        with self._transition(wi['proc_inst_id']):
            row = self.repo.get_approval(wid, self.tenant_id)
            inst = self.repo.get_instance(wi['proc_inst_id'])
            wi = self.repo.get_workitem(wid)
            if not row or row['status'] != 'FAILED':
                raise ValueError('전달 실패한 승인만 재시도할 수 있습니다')
            if inst['status'] != 'RUNNING' or inst.get('is_deleted') or wi['status'] != 'SUBMITTED':
                raise ValueError('이 인스턴스는 승인을 재전달할 수 없습니다')
            if not by or not str(by).strip():
                raise ValueError('복구 요청자를 입력하세요')
            snapshot = deepcopy(row['payload']['plan'].get('_snapshot'))
            if snapshot:
                snapshot['state'] = 'PENDING_APPROVAL'
                decisions.approve(snapshot, row['payload']['option'], by, role or '', 'retry same approval')
            row.update(status='PENDING', error=None)
            row['history'].append({'status':'PENDING', 't':engine.now_iso(now), 'by':by, 'role':role, 'reason':'manual retry'})
            self.repo.update_approval(row)
            self._after_commit(self.deliver_approval, wid, now)
        return self.repo.get_approval(wid, self.tenant_id)
