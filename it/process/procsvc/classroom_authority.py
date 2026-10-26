"""Instructor-side authorization and atomic usage ledger; no student admin API.

All paid calls must originate from the managed executor and call charge() before
the upstream request. A student key is never forwarded as an upstream LLM key.
This module deliberately exposes neither arbitrary completions nor policy edits.
PostgreSQL row locks serialize quota decisions across service replicas.
"""
from __future__ import annotations

import hashlib
import json
from uuid import uuid4


class Denied(ValueError):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def key_hash(key):
    if not isinstance(key, str) or not 32 <= len(key) <= 512:
        raise Denied('수업 접속 키가 올바르지 않습니다')
    return hashlib.sha256(key.encode()).hexdigest()


def positive(value, name):
    if type(value) is not int or value <= 0:
        raise Denied(name+' 한도가 올바르지 않습니다')
    return value


def validate_policy(policy):
    if not isinstance(policy, dict) or not isinstance(policy.get('actions'), dict) or not policy['actions']:
        raise Denied('승인된 수업 행동이 없습니다')
    profile = policy.get('profile') or {}
    if not profile.get('model') or not profile.get('revision'):
        raise Denied('모델·추출 설정 판본이 없습니다')
    for field in ('max_concurrency', 'total_calls', 'total_input_bytes', 'total_output_tokens'):
        positive(policy.get(field), field)
    for action, limits in policy['actions'].items():
        if action not in ('manual_extract', 'agent_run', 'class_check') or not isinstance(limits, dict):
            raise Denied('정의되지 않은 수업 행동입니다')
        for field in ('max_seconds', 'max_calls', 'max_input_bytes', 'max_output_tokens'):
            positive(limits.get(field), field)
    if not isinstance(policy.get('documents'), dict):
        raise Denied('승인 문서 목록이 없습니다')
    return policy


class Authority:
    def __init__(self, connect):
        # connect() returns a psycopg connection with dict_row, never a student
        # supplied DSN. Context ownership is local to each short transaction.
        self.connect = connect

    def _grant(self, db, hashed, *, lock=False):
        row = db.execute('SELECT *, expires_at > now() AS active FROM hyd_classroom_grants WHERE key_hash=%s'
                         + (' FOR UPDATE' if lock else ''), (hashed,)).fetchone()
        if not row or not row['enabled'] or not row['active']:
            raise Denied('수업 접속 권한이 없거나 만료됐습니다')
        validate_policy(row['policy'])
        return row

    def session(self, key):
        """Authenticate startup without reserving work or exposing policy data."""
        with self.connect() as db:
            self._grant(db, key_hash(key))
        return {'status': 'ok', 'service': 'classroom-execution'}

    def agent_binding(self,key,definition,version,activity):
        """Resolve exactly one approved activity without reserving paid work."""
        with self.connect() as db:
            grant=self._grant(db,key_hash(key))
            policy=grant['policy']
            if 'agent_run' not in policy['actions']:
                raise Denied('이 수업에서 관리 에이전트 실행을 허용하지 않습니다')
            matches=[(ref,value) for ref,value in (policy.get('agents') or {}).items()
                     if isinstance(value,dict) and (value.get('definition'),value.get('version'),value.get('activity'))
                     ==(definition,version,activity)]
            if len(matches)!=1:
                raise Denied('현재 작업 판본에 대응하는 강사 승인이 없거나 중복됐습니다')
            reference,approval=matches[0]
            return dict(subject=grant['subject'],reference=reference,approval=approval,
                        tool_io=policy.get('tool_io'),max_seconds=policy['actions']['agent_run']['max_seconds'])

    def authorize_document(self, key, content_hash):
        with self.connect() as db:
            grant = self._grant(db, key_hash(key))
            document = grant['policy']['documents'].get(content_hash)
            if not isinstance(document, dict) or not document.get('source_id'):
                raise Denied('강사가 승인한 문서 내용·판본이 아닙니다')
            return dict(subject=grant['subject'], scope=grant['scope'], profile=grant['policy']['profile'],
                        document=document)

    def reserve(self, key, action, input_contract):
        """input_contract is reconstructed by the managed endpoint, not a raw
        student prompt. Exact duplicates join a durable run even after failure;
        caller-controlled request IDs cannot increase paid work.
        """
        hashed = key_hash(key)
        with self.connect() as db:
            grant = self._grant(db, hashed, lock=True)
            policy = grant['policy']
            limits = policy['actions'].get(action)
            if not limits:
                raise Denied('이 수업에서 허용되지 않은 행동입니다')
            if action == 'manual_extract':
                if input_contract.get('sha256') not in policy['documents']:
                    raise Denied('승인되지 않은 문서는 추출할 수 없습니다')
            elif action == 'agent_run':
                if set(input_contract)!={'reference','revision','inputs'}:
                    raise Denied('승인된 에이전트 입력 계약이 필요합니다')
                approval=(policy.get('agents') or {}).get(input_contract['reference'])
                if not isinstance(approval,dict) or approval.get('revision')!=input_contract['revision']:
                    raise Denied('예약 직전 에이전트 승인 판본이 바뀌었습니다')
                from .classroom_agents import validate_input
                validate_input(approval,input_contract['inputs'])
            input_hash = digest(input_contract)
            request_key = digest([grant['scope'], policy['profile'], action, input_hash])
            db.execute("UPDATE hyd_classroom_runs SET state='EXPIRED' WHERE key_hash=%s AND state IN ('RESERVED','RUNNING') AND deadline<=now()", (hashed,))
            old = db.execute('SELECT * FROM hyd_classroom_runs WHERE key_hash=%s AND request_key=%s',
                             (hashed, request_key)).fetchone()
            if old:
                if old['policy_hash'] != digest([grant['scope'], policy]):
                    raise Denied('강사 승인 정책 판본이 바뀌었습니다')
                return dict(old, reused=True)
            count = db.execute("SELECT count(*) AS n FROM hyd_classroom_runs WHERE key_hash=%s AND state IN ('RESERVED','RUNNING')", (hashed,)).fetchone()['n']
            if count >= policy['max_concurrency']:
                raise Denied('수업의 동시 실행 한도에 도달했습니다')
            row = db.execute('''INSERT INTO hyd_classroom_runs(id,key_hash,request_key,action,input_hash,policy_hash,cache_key,state,deadline)
                VALUES (%s,%s,%s,%s,%s,%s,%s,'RESERVED',now()+%s*interval '1 second') RETURNING *''',
                (uuid4(), hashed, request_key, action, input_hash, digest([grant['scope'], policy]),
                 input_contract.get('cache_key') if action == 'manual_extract' else None, limits['max_seconds'])).fetchone()
            return dict(row, reused=False)

    def authorize_agent(self,key,reference):
        with self.connect() as db:
            grant=self._grant(db,key_hash(key))
            approval=(grant['policy'].get('agents') or {}).get(reference)
            if not isinstance(approval,dict) or 'agent_run' not in grant['policy']['actions']:
                raise Denied('강사가 승인한 에이전트 작업 판본이 아닙니다')
            return dict(subject=grant['subject'],approval=approval)

    def charge(self, key, run_id, *, input_bytes, max_output_tokens):
        """Reserve the full output cap before a call, including retries. Unknown
        outcomes are never refunded automatically. No client usage report is trusted.
        """
        return self._charge(key_hash(key), run_id, input_bytes=input_bytes, max_output_tokens=max_output_tokens)

    def _charge(self, hashed, run_id, *, input_bytes, max_output_tokens):
        positive(input_bytes, 'input_bytes'); positive(max_output_tokens, 'max_output_tokens')
        with self.connect() as db:
            grant = self._grant(db, hashed, lock=True)
            run = db.execute('SELECT *, deadline>now() AS active FROM hyd_classroom_runs WHERE id=%s AND key_hash=%s FOR UPDATE',
                             (run_id, hashed)).fetchone()
            if not run or not run['active'] or run['state'] not in ('RESERVED', 'RUNNING'):
                raise Denied('유효한 수업 실행이 아닙니다')
            policy = grant['policy']; limits = policy['actions'].get(run['action'])
            if run['policy_hash'] != digest([grant['scope'], policy]):
                raise Denied('강사 승인 정책 판본이 바뀌었습니다')
            if not limits:
                raise Denied('실행 중인 행동의 승인이 취소됐습니다')
            usage = dict(calls=1, input_bytes=input_bytes, output_tokens=max_output_tokens)
            for field, amount in usage.items():
                if run[field]+amount > limits['max_'+field] or grant[field]+amount > policy['total_'+field]:
                    raise Denied('수업 실행 또는 누적 사용량 한도 초과: '+field)
            db.execute("UPDATE hyd_classroom_runs SET state='RUNNING',calls=calls+1,input_bytes=input_bytes+%s,output_tokens=output_tokens+%s WHERE id=%s",
                       (input_bytes, max_output_tokens, run_id))
            db.execute('UPDATE hyd_classroom_grants SET calls=calls+1,input_bytes=input_bytes+%s,output_tokens=output_tokens+%s WHERE key_hash=%s',
                       (input_bytes, max_output_tokens, hashed))

    def execution_context(self, subject, work_ref, cache_key=None, *, execution_run_id=None):
        """Private managed-worker lookup; never exposed as a student API."""
        with self.connect() as db:
            rows = db.execute('''SELECT r.*,g.policy,g.scope FROM hyd_classroom_runs r
                JOIN hyd_classroom_grants g ON g.key_hash=r.key_hash
                WHERE g.subject=%s AND (r.work_ref=%s OR r.cache_key=%s) AND g.enabled AND g.expires_at>now()
                AND r.deadline>now() AND r.state IN ('RESERVED','RUNNING')
                AND (%s::uuid IS NULL OR r.id=%s::uuid)''',
                (subject, work_ref, cache_key, execution_run_id, execution_run_id)).fetchall()
            if len(rows) != 1:
                raise Denied('승인된 실행과 연결된 현재 작업이 하나여야 합니다')
            run = rows[0]
            if run['policy_hash'] != digest([run['scope'], run['policy']]):
                raise Denied('강사 승인 정책 판본이 바뀌었습니다')
            return dict(run_id=str(run['id']), model=run['policy']['profile']['model'],
                        deadline=run['deadline'].timestamp())

    def charge_execution(self, run_id, *, input_bytes, max_output_tokens):
        # Called only after the private worker capability and current lease
        # have been checked by classroom_model.authorize().
        with self.connect() as db:
            row = db.execute('SELECT key_hash FROM hyd_classroom_runs WHERE id=%s', (run_id,)).fetchone()
            if not row:
                raise Denied('승인된 수업 실행이 없습니다')
        return self._charge(row['key_hash'], run_id, input_bytes=input_bytes, max_output_tokens=max_output_tokens)

    def finish(self, key, run_id, *, validated, result_ref=None):
        if type(validated) is not bool or validated and not result_ref:
            raise Denied('검증된 결과 참조가 필요합니다')
        with self.connect() as db:
            hashed = key_hash(key)
            grant = self._grant(db, hashed, lock=True)
            run = db.execute('SELECT policy_hash,state,result_ref FROM hyd_classroom_runs WHERE id=%s AND key_hash=%s', (run_id, hashed)).fetchone()
            if not run or run['policy_hash'] != digest([grant['scope'], grant['policy']]):
                raise Denied('강사 승인 정책 판본이 바뀌었습니다')
            if run['state'] == ('DONE' if validated else 'FAILED') and run['result_ref'] == (result_ref if validated else None):
                return  # Concurrent result readers may confirm the same artifact.
            row = db.execute("UPDATE hyd_classroom_runs SET state=%s,result_ref=%s WHERE id=%s AND key_hash=%s AND state IN ('RESERVED','RUNNING') AND deadline>now() RETURNING id",
                             ('DONE' if validated else 'FAILED', result_ref if validated else None, run_id, hashed)).fetchone()
            if not row:
                raise Denied('끝났거나 만료된 실행에는 결과를 확정할 수 없습니다')

    def read_run(self, key, run_id):
        with self.connect() as db:
            hashed = key_hash(key)
            grant = self._grant(db, hashed)
            row = db.execute('SELECT *,deadline>now() AS active FROM hyd_classroom_runs WHERE id=%s AND key_hash=%s', (run_id, hashed)).fetchone()
            if not row or row['policy_hash'] != digest([grant['scope'], grant['policy']]):
                raise Denied('접근 가능한 현재 수업 실행이 아닙니다')
            if not row['active'] and row['state'] in ('RESERVED', 'RUNNING'):
                row['state'] = 'EXPIRED'
            row['subject'] = grant['subject']
            return row

    def bind_work(self, key, run_id, work_ref):
        with self.connect() as db:
            hashed = key_hash(key)
            grant = self._grant(db, hashed, lock=True)
            row = db.execute('''UPDATE hyd_classroom_runs SET work_ref=%s WHERE id=%s AND key_hash=%s
                AND policy_hash=%s AND state IN ('RESERVED','RUNNING') AND deadline>now()
                AND (work_ref IS NULL OR work_ref=%s) RETURNING id''',
                (work_ref, run_id, hashed, digest([grant['scope'], grant['policy']]), work_ref)).fetchone()
            if not row:
                raise Denied('실행을 다른 작업으로 바꾸거나 만료 후 시작할 수 없습니다')
