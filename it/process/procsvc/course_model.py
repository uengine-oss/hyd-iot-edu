"""Local classroom model gateway, using the existing durable authority ledger.

The instructor's process owns the provider key. A worker gets a claim-bound
capability, never that key. Student wording is not an approval fingerprint:
only the classroom activity, its live lease and its bounded usage are authority.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os
from pathlib import Path
import secrets

from fastapi import HTTPException

from hydcommon import course_access as rules
from . import classroom_model, engine, worker_credentials
from .classroom_authority import Authority, Denied, key_hash


POLICY = dict(profile=dict(model='coding', revision='local-course-v1'), documents={},
              max_concurrency=1, total_calls=600, total_input_bytes=100_000_000,
              total_output_tokens=20_000_000,
              limits_revision='2026-10-27-2',
              actions={'class_check': dict(max_seconds=600, max_calls=24,
                         max_input_bytes=4_000_000, max_output_tokens=768_000)})


def ensure_runtime_key(path):
    """Create once in the private shared volume; never reset on restart."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        old = Path('/data/mcp/worker-runtime.key')
        value = old.read_text(encoding='utf8').strip() if old.is_file() and old != path else secrets.token_urlsafe(48)
        if len(value) < 32:raise ValueError('기존 워커 인증 파일을 확인하세요')
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, 'w', encoding='utf8') as stream:
                stream.write(value)
                stream.flush();os.fsync(stream.fileno())
    if path.is_symlink() or len(path.read_text(encoding='utf8').strip()) < 32:
        raise ValueError('워커 인증 파일을 확인하세요')


class CourseAuthority(Authority):
    def __init__(self, connect, access_store, *, key_loader=worker_credentials._key):
        super().__init__(connect)
        self.access_store, self.key_loader = access_store, key_loader

    def _account(self, tenant):
        return hmac.new(self.key_loader().encode(),('hyd-local-course-v1:'+tenant).encode(),hashlib.sha256).hexdigest()

    def _reconcile(self, db, hashed):
        db.execute('''UPDATE hyd_classroom_runs r SET
            state=CASE WHEN w.status='DONE' AND split_part(r.work_ref,'#',2)=coalesce(w.generation,0)::text THEN 'DONE' ELSE 'FAILED' END,
            result_ref=CASE WHEN w.status='DONE' AND split_part(r.work_ref,'#',2)=coalesce(w.generation,0)::text THEN r.work_ref ELSE NULL END
            FROM todolist w,hyd_classroom_grants g WHERE r.key_hash=%s AND g.key_hash=r.key_hash AND r.state IN ('RESERVED','RUNNING')
            AND split_part(r.work_ref,'#',1)=w.id::text
            AND (w.status IN ('DONE','CANCELLED') OR w.draft_status='CANCELLED'
                 OR (w.draft_status='FAILED' AND (r.deadline<=now()
                     OR r.calls>=(g.policy->'actions'->r.action->>'max_calls')::bigint
                     OR r.input_bytes>=(g.policy->'actions'->r.action->>'max_input_bytes')::bigint
                     OR r.output_tokens>=(g.policy->'actions'->r.action->>'max_output_tokens')::bigint))
                 OR split_part(r.work_ref,'#',2)<>coalesce(w.generation,0)::text)''',(hashed,))

    def usage(self, runtime):
        hashed=key_hash(self._account(runtime.tenant_id))
        with self.connect() as db:
            self._reconcile(db,hashed)
            grant=db.execute('SELECT enabled,policy,calls,input_bytes,output_tokens FROM hyd_classroom_grants WHERE key_hash=%s',(hashed,)).fetchone()
            states=db.execute('SELECT state,count(*) AS n FROM hyd_classroom_runs WHERE key_hash=%s GROUP BY state',(hashed,)).fetchall()
            paused=db.execute('''SELECT count(*) AS n FROM hyd_classroom_runs r JOIN todolist w
                ON split_part(r.work_ref,'#',1)=w.id::text WHERE r.key_hash=%s AND r.state IN ('RESERVED','RUNNING')
                AND w.draft_status='FAILED' AND r.deadline>now()''',(hashed,)).fetchone()['n']
        policy=grant['policy'] if grant else POLICY
        return dict(enabled=grant['enabled'] if grant else True,
            used=dict(model_requests=grant['calls'] if grant else 0,input_bytes=grant['input_bytes'] if grant else 0,
                      reserved_output_tokens=grant['output_tokens'] if grant else 0),
            limits={k:v for k,v in policy.items() if k.startswith('total_') or k in ('max_concurrency','actions')},
            executions={r['state']:r['n'] for r in states},paused_executions=paused)

    def local_execution(self, runtime, row):
        inst = runtime.repo.get_instance(row['proc_inst_id'])
        if not inst or inst['tenant_id'] != runtime.tenant_id:raise Denied('현재 수업 작업이 없습니다')
        definition = runtime.definition_for(inst)
        values = engine.variables(inst)
        try:
            rules.authorize_task(definition.raw, row['activity_id'], values)
        except rules.AccessDenied as exc:
            raise Denied(str(exc)) from None
        if len(rules.canonical(values)) > 128_000:raise Denied('수업 작업의 입력 크기 한도 초과')
        account = self._account(runtime.tenant_id)
        hashed = key_hash(account)
        from psycopg.types.json import Jsonb
        with self.connect() as db:
            # A restart or a repeated grant request must not reset counters,
            # revive a disabled account, or silently replace its policy.
            db.execute('''INSERT INTO hyd_classroom_grants(key_hash,subject,scope,expires_at,policy)
                VALUES(%s,%s,%s,%s,%s) ON CONFLICT(key_hash) DO NOTHING''',
                (hashed,runtime.tenant_id,'local-course-v1',datetime.now(timezone.utc)+timedelta(days=365),Jsonb(POLICY)))
            self._reconcile(db,hashed)
        contract = dict(todo_id=row['id'], generation=int(row.get('generation') or 0),
                        definition=inst['proc_def_id'], version=inst['proc_def_version'], activity=row['activity_id'])
        run = self.reserve(account, 'class_check', contract)
        work_ref = row['id']+'#'+str(contract['generation'])
        self.bind_work(account, run['id'], work_ref)
        return self.execution_context(runtime.tenant_id, work_ref, execution_run_id=run['id'])


def mount(app, *, access_store, runtime_factory, settings):
    def connect():
        import psycopg
        from psycopg.rows import dict_row
        runtime = runtime_factory()
        dsn = getattr(getattr(runtime,'repo',None),'dsn',None)
        if not dsn:raise HTTPException(503,'수업 실행 장부가 준비되지 않았습니다')
        return psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5)

    def runtime(tenant):
        value = runtime_factory()
        if value is None or value.tenant_id != tenant:
            raise HTTPException(503,'현재 수업의 실행 서비스를 확인하세요')
        return value

    def upstream():
        key = settings.get('LLM_API_KEY','').strip()
        url = settings.get('LLM_RELAY_URL','').strip()
        if not key or not url:raise HTTPException(503,'수업 중계 설정이 준비되지 않았습니다')
        return dict(url=url,key=key)

    @app.on_event('startup')
    def prepare():
        ensure_runtime_key(settings.get('HYD_WORKER_RUNTIME_KEY_FILE','/data/mcp/worker-runtime.key'))

    authority = CourseAuthority(connect, access_store)
    classroom_model.mount(app, authority, runtime, upstream)

    @app.get('/api/course-access/usage')
    def usage():
        value=runtime_factory()
        if value is None:raise HTTPException(503,'수업 실행 서비스가 준비되지 않았습니다')
        return authority.usage(value)

    access_store.questions_enabled = True
    return authority
