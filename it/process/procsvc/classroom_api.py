"""Managed classroom entry points. No raw LLM endpoint or remote policy editor.

Mount only on the instructor-managed executor, whose upstream credentials never
leave that server. Student-supplied prompts/catalog/model parameters are rejected.
"""
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from . import manual_cache
from .classroom_authority import Denied


class ExtractionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    sha256: str = Field(pattern=r'^[0-9a-f]{64}$')


def create_app(authority, *, source_loader, runtime_factory, catalog_factory, upstream_factory=None,
               archive_factory=None):
    app = FastAPI(title='HYD managed classroom execution')
    if upstream_factory is not None:
        from . import classroom_model
        classroom_model.mount(app, authority, runtime_factory, upstream_factory)

    def key(header):
        if not header or not header.startswith('Bearer '):
            raise HTTPException(401, '수업 접속 키가 필요합니다')
        return header[7:]

    def allowed(fn):
        try:
            return fn()
        except Denied as exc:
            raise HTTPException(403, str(exc)) from None

    @app.get('/healthz')
    def health():
        return {'status': 'ok', 'service': 'classroom-execution', 'raw_llm_routes': False}

    @app.get('/v1/classroom/documents/{sha256}')
    def document(sha256: str, authorization: str | None = Header(default=None)):
        grant = allowed(lambda: authority.authorize_document(key(authorization), sha256))
        return {k: grant[k] for k in ('scope', 'profile')}

    @app.get('/v1/classroom/session')
    def session(authorization: str | None = Header(default=None)):
        return allowed(lambda: authority.session(key(authorization)))

    @app.post('/v1/classroom/extractions')
    def extract(body: ExtractionRequest, authorization: str | None = Header(default=None)):
        credential = key(authorization)
        grant = allowed(lambda: authority.authorize_document(credential, body.sha256))
        # Approved bytes and schema come from the managed server, never uploads
        # or arbitrary prompts delivered to this endpoint.
        source = source_loader(grant['document'])
        if source['sha256'] != body.sha256:
            raise HTTPException(503, '강사 서버의 승인 원문 판본이 일치하지 않습니다')
        runtime = runtime_factory(grant['subject'])
        if runtime.tenant_id != grant['subject']:
            raise HTTPException(503, '관리 실행기의 수업 공간이 일치하지 않습니다')
        catalog = catalog_factory(runtime)
        cache_key = manual_cache.identity(runtime.tenant_id, source, catalog,
                                           scope=grant['scope'], profile=grant['profile'])
        run = allowed(lambda: authority.reserve(credential, 'manual_extract', {'sha256': body.sha256, 'cache_key': cache_key}))
        if run['state'] in ('FAILED', 'EXPIRED'):
            raise HTTPException(409, '기존 추출이 실패·만료됐습니다. 강사 확인 없이 유료 재실행하지 않습니다')
        if not run['work_ref']:
            # Reservation UUID is server generated. Partial HTTP failures return
            # to the same DB event/cache key, never a new paid operation.
            work = manual_cache.start(runtime, source, str(run['id']), catalog,
                                      scope=grant['scope'], profile=grant['profile'], execution_run_id=run['id'])
            allowed(lambda: authority.bind_work(credential, run['id'], work['instance']))
        return dict(run_id=str(run['id']), state=run['state'], reused=run['reused'])

    @app.get('/v1/classroom/runs/{run_id}')
    def run(run_id: str, authorization: str | None = Header(default=None)):
        row = read(run_id, authorization)
        return {k: row[k] for k in ('id', 'action', 'state', 'deadline', 'calls', 'input_bytes', 'output_tokens', 'result_ref')}

    def read(run_id, authorization):
        from uuid import UUID
        try:
            identifier = UUID(run_id)
        except ValueError:
            raise HTTPException(422, '수업 실행 ID가 올바르지 않습니다') from None
        return allowed(lambda: authority.read_run(key(authorization), identifier))

    @app.get('/v1/classroom/runs/{run_id}/result')
    def result(run_id: str, authorization: str | None = Header(default=None)):
        from . import engine
        from .classroom_authority import digest
        row = read(run_id, authorization)
        if row['action'] != 'manual_extract' or row['state'] in ('FAILED', 'EXPIRED'):
            raise HTTPException(409, '완료 가능한 문서 추출 실행이 아닙니다')
        if not archive_factory:
            raise HTTPException(503, '관리 서버 원문 저장소가 연결되지 않았습니다')
        if not row['work_ref']:
            return {'status': 'PENDING', 'preview': None}
        runtime = runtime_factory(row['subject'])
        if runtime.tenant_id != row['subject']:
            raise HTTPException(503, '관리 실행기의 수업 공간이 일치하지 않습니다')
        instance = runtime.repo.get_instance(row['work_ref'])
        if not instance or instance.get('tenant_id') != row['subject']:
            raise HTTPException(503, '관리 실행의 추출 작업을 찾을 수 없습니다')
        cache = engine.variables(instance).get('extraction_cache') or {}
        if cache.get('key') != row['cache_key'] or not cache.get('source_id'):
            raise HTTPException(503, '승인 실행과 추출 작업의 원문 연결이 다릅니다')
        archive = archive_factory(row['subject'])
        source = archive.get(row['subject'], cache['source_id'])
        allowed(lambda: authority.authorize_document(key(authorization), source['sha256']))
        try:
            value = manual_cache.result(runtime, archive, source, row['work_ref'], None)
        except (ValueError, KeyError):
            # Invalid extraction must never become a successful cache hit.
            # The instructor can inspect the private task for correction.
            raise HTTPException(422, '추출 결과의 원문·의미 검증을 통과하지 못했습니다') from None
        if value['status'] in ('FAILED', 'CANCELLED'):
            allowed(lambda: authority.finish(key(authorization), row['id'], validated=False))
        elif value['status'] == 'DONE':
            if not value.get('preview') or not value.get('cache', {}).get('validated'):
                raise HTTPException(422, '검증된 추출 결과가 없습니다')
            # Each preview has a fresh human-review batch ID. It is not part
            # of the immutable extraction artifact's identity.
            reference = digest({k: v for k, v in value['preview'].items() if k != 'batch'})
            allowed(lambda: authority.finish(key(authorization), row['id'], validated=True, result_ref=reference))
        # This is a proposal. Local graph conflicts/preflight and human review
        # must run against the student's current graph before loading it.
        return {k: value[k] for k in ('status', 'preview', 'cache', 'progress', 'corrections') if k in value} | {
            'source_fingerprint': manual_cache.source_fingerprint(source)}

    return app
