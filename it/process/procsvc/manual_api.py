"""Original → source-backed preview → human review → atomic graph endpoints."""
import asyncio
import base64
from urllib.parse import quote

from fastapi import HTTPException
from fastapi.responses import Response

from . import manual_graph, manual_review, manual_extraction
from .manual_sources import MAX_BYTES


def register(app, *, archive_factory, driver_factory, tenant, audit, runtime_factory=lambda: None):
    async def run(fn):
        try:
            return await asyncio.get_running_loop().run_in_executor(None, fn)
        except manual_graph.Conflict as exc:
            raise HTTPException(409, str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(404, '문서 판본 또는 배치를 찾을 수 없습니다') from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    def graph(fn):
        with driver_factory() as driver, driver.session() as session:
            return fn(session)

    def runtime():
        rt = runtime_factory()
        if rt is None or rt.tenant_id != tenant:
            raise HTTPException(503, '문서 추출에는 같은 tenant의 instance 실행 서비스가 필요합니다')
        return rt

    @app.post('/api/kg/manuals/sources/{source_id}/extractions')
    async def extract(source_id: str, body: dict):
        def work():
            request_id = body.get('request_id')
            if not isinstance(request_id,str):raise ValueError('재전송에 사용할 request_id UUID가 필요합니다')
            source = archive_factory().get(tenant,source_id)
            inst = manual_extraction.start(runtime(),source,request_id)
            return dict(instance=inst['proc_inst_id'],status=inst['status'],source_id=source_id)
        return await run(work)

    @app.get('/api/kg/manuals/sources/{source_id}/extractions/{instance_id}')
    async def extraction_result(source_id: str, instance_id: str):
        def work():
            source = archive_factory().get(tenant,source_id)
            previous = graph(lambda session: manual_graph.head(session,tenant,source['document_id']))
            return manual_extraction.result(runtime(),source,instance_id,previous)
        return await run(work)

    @app.get('/api/kg/manuals/sources/{source_id}/extractions')
    async def extraction_history(source_id: str, limit: int = 50, offset: int = 0):
        def work():
            source = archive_factory().get(tenant,source_id)
            if not 1 <= limit <= 100 or offset < 0:raise ValueError('목록 범위가 올바르지 않습니다')
            rows = runtime().repo.list_source_runs(tenant,manual_extraction.DEFINITION_ID,
                        'manual-extraction:'+source['source_id']+':',limit+1,offset)
            return dict(items=rows[:limit],offset=offset,limit=limit,next_offset=offset+limit if len(rows)>limit else None)
        return await run(work)

    def preview(source):
        def with_catalog(session):
            modes = session.run('MATCH (f:FailureMode) OPTIONAL MATCH (f)-[:OCCURS_IN]->(c:Component) '
                                "RETURN f.id AS id, f.name + ' ' + coalesce(c.name, '') AS name").data()
            result = manual_review.proposal(source, modes)
            result['previous_batch'] = manual_graph.head(session, tenant, source['document_id'])
            return result
        return graph(with_catalog)

    @app.post('/api/kg/manuals/preview')
    async def upload(body: dict):
        def work():
            data = body.get('data')
            if not isinstance(data, str) or len(data) > ((MAX_BYTES + 2) // 3) * 4:
                raise ValueError('30 MiB 이하 파일의 base64 데이터가 필요합니다')
            try:
                raw = base64.b64decode(data, validate=True)
            except Exception as exc:
                raise ValueError('base64 파일 데이터가 올바르지 않습니다') from exc
            source = archive_factory().save(tenant, body.get('filename'), raw,
                                             document_id=body.get('document_id'))
            return preview(source)
        return await run(work)

    @app.get('/api/kg/manuals/sources/{source_id}')
    async def source(source_id: str):
        return await run(lambda: archive_factory().get(tenant, source_id))

    @app.get('/api/kg/manuals/sources')
    async def sources(limit: int = 50, offset: int = 0):
        return await run(lambda: archive_factory().list(tenant, limit, offset))

    @app.get('/api/kg/manuals/sources/{source_id}/original')
    async def original(source_id: str):
        def work():
            archive = archive_factory()
            stored = archive.get(tenant, source_id)
            return Response(archive.original(tenant, source_id), media_type=stored['media_type'],
                            headers={'Content-Disposition': "attachment; filename*=UTF-8''" + quote(stored['filename'], safe='')})
        return await run(work)

    @app.post('/api/kg/manuals/sources/{source_id}/preview')
    async def reopen(source_id: str):
        return await run(lambda: preview(archive_factory().get(tenant, source_id)))

    @app.post('/api/kg/manuals/commit')
    async def commit(body: dict):
        def work():
            # All source/shape checks run before even opening the graph connection.
            plan = manual_review.validate(archive_factory(), tenant, body)
            if body.get('method') == manual_extraction.CONTRACT:
                binding = body.get('extraction')
                if not isinstance(binding,dict) or not isinstance(binding.get('instance'),str):
                    raise ValueError('추출 제안의 실제 작업 연결이 필요합니다')
                source = archive_factory().get(tenant,plan['source_id'])
                current = manual_extraction.result(runtime(),source,binding['instance'],plan['previous_batch'])['preview']
                if current is None or current['extraction'] != binding:
                    raise ValueError('추출 작업이 완료되지 않았거나 검토한 작업 세대가 다릅니다')
                plan['extraction'] = current['extraction']
                plan['page_reviews'] = current['page_reviews']
            result = graph(lambda session: manual_graph.commit(session, plan))
            audit('-', plan['by'], 'MANUAL_INGESTED', {key: result[key] for key in
                  ('batch', 'source_id', 'filename', 'sections', 'procedures', 'steps')})
            return result
        return await run(work)

    @app.post('/api/kg/manuals/batches/{batch}/rollback')
    async def rollback(batch: str, body: dict):
        def work():
            result = graph(lambda session: manual_graph.rollback(session, tenant, batch, body.get('by')))
            audit('-', body['by'], 'MANUAL_ROLLED_BACK', result)
            return result
        return await run(work)

    @app.get('/api/kg/manuals')
    async def history():
        return await run(lambda: graph(lambda session: manual_graph.history(session, tenant)))
