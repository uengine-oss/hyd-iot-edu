"""Managed classroom entry points. No raw LLM endpoint or remote policy editor.

Mount only on the instructor-managed executor, whose upstream credentials never
leave that server. Student-supplied prompts/catalog/model parameters are rejected.
"""
from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from . import manual_cache
from .classroom_authority import Denied


class ExtractionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    sha256: str = Field(pattern=r'^[0-9a-f]{64}$')


class AgentRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reference: str = Field(min_length=1,max_length=120,pattern=r'^[A-Za-z0-9_.:-]+$')
    inputs: dict
    expected_revision: str | None = Field(default=None,pattern=r'^[0-9a-f]{64}$')


def create_app(authority, *, source_loader, runtime_factory, catalog_factory, upstream_factory=None,
               archive_factory=None, agent_enabled=False):
    app = FastAPI(title='HYD managed classroom execution')
    from .classroom_tool_io import ToolIO
    tool_io = ToolIO(authority)
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

    @app.get('/v1/classroom/runs/{run_id}/tool-requests')
    def tool_requests(run_id: str, authorization: str | None = Header(default=None)):
        return {'requests': allowed(lambda: tool_io.pending(key(authorization), run_id))}

    @app.post('/v1/classroom/tool-results')
    async def tool_result(request: Request, authorization: str | None = Header(default=None)):
        import asyncio
        import json
        credential = key(authorization)
        raw = bytearray()
        async for chunk in request.stream():
            if len(raw)+len(chunk) > 192000:
                raise HTTPException(413, '도구 결과 전송 크기 한도 초과')
            raw.extend(chunk)
        try:
            body = json.loads(raw)
            if not isinstance(body, dict) or set(body) != {'run_id','request_id','result','is_error'}:
                raise ValueError()
        except (ValueError, UnicodeError):
            raise HTTPException(422, '도구 결과 필드가 올바르지 않습니다') from None
        return await asyncio.to_thread(allowed, lambda: tool_io.complete(
            credential, body['run_id'], body['request_id'], result=body['result'], is_error=body['is_error']))

    @app.get('/v1/classroom/agents/contract')
    def agent_contract(definition: str, version: str, activity: str, authorization: str | None = Header(default=None)):
        from . import classroom_agents
        from .classroom_tool_io import catalog
        binding=allowed(lambda:authority.agent_binding(key(authorization),definition,version,activity))
        runtime=runtime_factory(binding['subject'])
        if runtime.tenant_id!=binding['subject']:
            raise HTTPException(503,'승인된 교육 공간의 실행 서비스가 준비되지 않았습니다')
        allowed(lambda:classroom_agents.checked(runtime,binding['approval']))
        tools=allowed(lambda:catalog(binding['tool_io']))
        # Only schemas/names leave the server, never runtime URLs or secrets.
        return {name:binding[name] for name in ('reference','approval','max_seconds')} | {'tools':tools}

    @app.post('/v1/classroom/agents')
    def agent_start(body: AgentRequest, authorization: str | None = Header(default=None)):
        from . import classroom_agents
        if not agent_enabled:
            raise HTTPException(503,'관리 에이전트 실행 연결이 아직 활성화되지 않았습니다')
        credential=key(authorization)
        grant=allowed(lambda:authority.authorize_agent(credential,body.reference))
        runtime=runtime_factory(grant['subject'])
        if runtime.tenant_id!=grant['subject']:
            raise HTTPException(503,'관리 실행기의 수업 공간이 일치하지 않습니다')
        approval=grant['approval']
        if body.expected_revision is not None and body.expected_revision!=approval['revision']:
            raise HTTPException(409,'실행 준비 중 강사 승인 판본이 바뀌었습니다')
        allowed(lambda:classroom_agents.checked(runtime,approval))
        allowed(lambda:classroom_agents.validate_input(approval,body.inputs))
        contract=dict(reference=body.reference,revision=approval['revision'],inputs=body.inputs)
        run=allowed(lambda:authority.reserve(credential,'agent_run',contract))
        if run['state'] in ('DONE','FAILED','EXPIRED'):
            # A historical judgment is reviewable, never a new current-state
            # execution. An instructor must authorize another exercise scope.
            raise HTTPException(409,'기존 실행이 끝났습니다. 현재 상태의 새 실행은 강사 승인 범위를 확인하세요')
        if not run['work_ref']:
            inst=allowed(lambda:classroom_agents.start(runtime,approval,body.inputs,run['id'],body.reference))
            allowed(lambda:authority.bind_work(credential,run['id'],inst['proc_inst_id']))
        return {'run_id':str(run['id']),'state':run['state'],'reused':run['reused']}

    @app.post('/v1/classroom/agents/runs/{run_id}/cancel')
    def agent_cancel(run_id: str, authorization: str | None = Header(default=None)):
        credential=key(authorization)
        row=read(run_id,authorization)
        if row['action']!='agent_run':
            raise HTTPException(403,'관리 에이전트 실행만 중단할 수 있습니다')
        if row['state'] in ('DONE','FAILED','EXPIRED'):
            return {'state':row['state']}
        # Revoke model/tool authorization first, even if the process DB is down.
        allowed(lambda:authority.finish(credential,row['id'],validated=False))
        if row['work_ref']:
            runtime=runtime_factory(row['subject'])
            if runtime.tenant_id!=row['subject']:
                raise HTTPException(503,'관리 실행 공간이 일치하지 않습니다')
            with runtime.repo.instance_transaction(runtime.tenant_id,row['work_ref']):
                for wi in runtime.repo.list_workitems(proc_inst_id=row['work_ref'],limit=None):
                    if wi['status']=='IN_PROGRESS' and wi.get('agent_orch')=='cliagents':
                        wi.update(draft_status='CANCELLED')
                        runtime.repo.update_workitem(wi)
        return {'state':'FAILED'}

    @app.get('/v1/classroom/agents/runs/{run_id}/result')
    def agent_result(run_id: str, authorization: str | None = Header(default=None)):
        from . import classroom_agents,engine
        from .classroom_authority import digest
        row=read(run_id,authorization)
        if row['action']!='agent_run' or row['state'] in ('FAILED','EXPIRED'):
            raise HTTPException(409,'결과를 확인할 수 있는 에이전트 실행이 아닙니다')
        if not row['work_ref']:
            return {'status':'PENDING','output':None}
        runtime=runtime_factory(row['subject'])
        inst=runtime.repo.get_instance(row['work_ref'])
        if runtime.tenant_id!=row['subject'] or not inst or inst.get('tenant_id')!=row['subject']:
            raise HTTPException(503,'승인된 에이전트 실행을 찾을 수 없습니다')
        values=engine.variables(inst)
        grant=allowed(lambda:authority.authorize_agent(key(authorization),values.get('classroom_agent_reference')))
        approval=allowed(lambda:classroom_agents.verify_instance(runtime,inst))
        if approval!=grant['approval'] or values.get('classroom_execution')!={'run_id':str(row['id'])}:
            raise HTTPException(403,'현재 승인과 실행의 연결이 다릅니다')
        items=runtime.repo.list_workitems(proc_inst_id=inst['proc_inst_id'],limit=None)
        if any(w['status'] in ('PENDING','CANCELLED') or w.get('draft_status') in ('FAILED','CANCELLED') for w in items):
            allowed(lambda:authority.finish(key(authorization),row['id'],validated=False))
            return {'status':'FAILED','output':None}
        if inst['status']!='COMPLETED' or len(items)!=1 or items[0]['status']!='DONE':
            return {'status':'PENDING','output':None}
        activity=runtime.definition_for(inst).activities[approval['activity']]
        output={name:values[name] for name in activity.get('outputData',[]) if name in values}
        allowed(lambda:authority.finish(key(authorization),row['id'],validated=True,result_ref=digest(output)))
        return {'status':'DONE','output':output,'historical_proposal':True,'requires_local_review':True}

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
