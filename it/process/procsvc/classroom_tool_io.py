"""Bounded reverse tool calls, scoped to the student's active managed run.

enqueue/result are private executor methods, never student HTTP operations.
pending/complete accept a student key, but cannot create work or spend model
budget. Tool errors remain errors. Results are observations, not authority to
perform a purchase, mark maintenance complete, or change instructor policy.
"""
import json
import re
from uuid import UUID, uuid4

from .classroom_authority import Denied, digest, key_hash, positive


def identifier(value):
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise Denied('도구 조회 ID가 올바르지 않습니다') from None


def encoded(value):
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf8')
    except (ValueError, TypeError, UnicodeError):
        raise Denied('도구 조회 내용은 유효한 JSON이어야 합니다') from None


class ToolIO:
    def __init__(self, authority):
        self.authority = authority

    def _run(self, db, run_id, hashed=None):
        # Serialize queue accounting and result acceptance for one run. Grant
        # revocation/policy checks are performed in this transaction as well.
        run = db.execute('SELECT *,deadline>now() AS active FROM hyd_classroom_runs WHERE id=%s FOR UPDATE',
                         (identifier(run_id),)).fetchone()
        if not run or hashed is not None and run['key_hash'] != hashed:
            raise Denied('접근 가능한 도구 조회 실행이 아닙니다')
        grant = self.authority._grant(db, run['key_hash'])
        if (run['action'] != 'agent_run' or run['state'] not in ('RESERVED','RUNNING') or not run['active']
                or run['policy_hash'] != digest([grant['scope'],grant['policy']])):
            raise Denied('현재 승인된 에이전트 실행에서만 도구를 조회할 수 있습니다')
        contract = grant['policy'].get('tool_io')
        if not isinstance(contract, dict) or not isinstance(contract.get('tools'), list) or not contract['tools']:
            raise Denied('강사가 승인한 도구 조회 계약이 없습니다')
        if any(not isinstance(t,str) or not re.fullmatch(r'[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+',t) for t in contract['tools']):
            raise Denied('승인 도구 이름은 서버/도구 형식이어야 합니다')
        for field in ('max_calls','max_input_bytes','max_result_bytes','total_result_bytes'):
            positive(contract.get(field), field)
        # These are transport ceilings; an instructor may choose lower limits.
        if contract['max_calls'] > 256 or contract['max_input_bytes'] > 12000 or contract['max_result_bytes'] > 128000:
            raise Denied('도구 조회 계약이 전송 상한을 초과했습니다')
        return run, contract

    def enqueue(self, run_id, call_id, tool, arguments):
        from psycopg.types.json import Jsonb
        if not isinstance(call_id,str) or not 1 <= len(call_id) <= 128 or not isinstance(arguments,dict):
            raise Denied('도구 호출 식별자·인자가 올바르지 않습니다')
        size = len(encoded(arguments))
        with self.authority.connect() as db:
            run, contract = self._run(db, run_id)
            if tool not in contract['tools'] or size > contract['max_input_bytes']:
                raise Denied('승인되지 않은 도구 또는 조회 입력 한도 초과')
            old = db.execute('SELECT * FROM hyd_classroom_tool_io WHERE run_id=%s AND call_id=%s', (run['id'],call_id)).fetchone()
            if old:
                if old['tool'] != tool or old['arguments'] != arguments:
                    raise Denied('같은 도구 호출 ID의 내용을 바꿀 수 없습니다')
                return str(old['id'])
            count = db.execute('SELECT count(*) AS n FROM hyd_classroom_tool_io WHERE run_id=%s',(run['id'],)).fetchone()['n']
            if count >= contract['max_calls']:
                raise Denied('실행의 도구 조회 횟수 한도 초과')
            request_id = str(uuid4())
            db.execute('INSERT INTO hyd_classroom_tool_io(id,run_id,call_id,tool,arguments,input_bytes) VALUES (%s,%s,%s,%s,%s,%s)',
                       (request_id,run['id'],call_id,tool,Jsonb(arguments),size))
            return request_id

    def pending(self, key, run_id):
        with self.authority.connect() as db:
            run, _ = self._run(db,run_id,key_hash(key))
            rows = db.execute("SELECT id,tool,arguments FROM hyd_classroom_tool_io WHERE run_id=%s AND state='WAITING' ORDER BY created_at,id LIMIT 1",
                              (run['id'],)).fetchall()
            return [dict(row,id=str(row['id'])) for row in rows]

    def complete(self, key, run_id, request_id, *, result, is_error):
        from psycopg.types.json import Jsonb
        if type(is_error) is not bool:
            raise Denied('도구 오류 여부를 명시해야 합니다')
        size = len(encoded(result)); fingerprint = digest([is_error,result])
        with self.authority.connect() as db:
            run, contract = self._run(db,run_id,key_hash(key))
            row = db.execute('SELECT * FROM hyd_classroom_tool_io WHERE id=%s AND run_id=%s',
                             (identifier(request_id),run['id'])).fetchone()
            if not row:
                raise Denied('요청한 적 없는 도구 결과입니다')
            if row['state'] != 'WAITING':
                if row['result_hash'] != fingerprint:
                    raise Denied('이미 받은 도구 결과를 바꿀 수 없습니다')
                return {'status':row['state'],'reused':True}
            total = db.execute('SELECT coalesce(sum(result_bytes),0) AS n FROM hyd_classroom_tool_io WHERE run_id=%s',
                               (run['id'],)).fetchone()['n']
            if size > contract['max_result_bytes'] or total+size > contract['total_result_bytes']:
                raise Denied('도구 조회 응답 또는 누적 크기 한도 초과')
            state = 'FAILED' if is_error else 'DONE'
            db.execute('UPDATE hyd_classroom_tool_io SET state=%s,result=%s,result_hash=%s,result_bytes=%s,completed_at=now() WHERE id=%s',
                       (state,Jsonb(result),fingerprint,size,row['id']))
            return {'status':state,'reused':False}

    def result(self, run_id, request_id):
        with self.authority.connect() as db:
            run, _ = self._run(db,run_id)
            row = db.execute('SELECT state,result FROM hyd_classroom_tool_io WHERE id=%s AND run_id=%s',
                             (identifier(request_id),run['id'])).fetchone()
            if not row:
                raise Denied('도구 조회 요청을 찾을 수 없습니다')
            return dict(row)
