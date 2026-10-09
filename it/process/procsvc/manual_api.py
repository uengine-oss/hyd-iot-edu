"""Original → source-backed preview → human review → atomic graph endpoints."""
import asyncio
import base64
from urllib.parse import quote

from fastapi import HTTPException
from fastapi.responses import Response

from uuid import uuid4

from . import manual_graph, manual_review, manual_extraction, manual_golden
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
            inst = manual_extraction.start(runtime(),source,request_id,review_feedback=body.get('review_feedback'))
            seg = manual_extraction.engine.variables(inst).get('segment') or {}
            return dict(instance=inst['proc_inst_id'],status=inst['status'],source_id=source_id,segments=seg.get('total',1))
        return await run(work)

    @app.get('/api/kg/manuals/sources/{source_id}/extractions/{instance_id}')
    async def extraction_result(source_id: str, instance_id: str):
        def work():
            source = archive_factory().get(tenant,source_id)
            previous = graph(lambda session: manual_graph.head(session,tenant,source['document_id']))
            value = manual_extraction.result(runtime(),source,instance_id,previous)
            if value.get('preview'):
                # A077 (ontology-studio merge_warning): tell the reviewer *before* commit which proposed SOP ids another
                # document or admin knowledge already owns. Read-only; the commit-time Conflict stays as the hard rule.
                value['preview']['conflicts'] = graph(lambda session: manual_graph.sop_conflicts(
                    session, source['document_id'], [p['id'] for p in value['preview']['procedures']]))
            return value
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
            def commit_with_rules(session):
                from . import skill_graph
                fms = sorted({p['failureMode'] for p in plan['procedures']})
                plan['candidate_rules'] = {fm: session.execute_read(lambda tx, fm=fm: skill_graph.candidate_rules(tx, fm)) for fm in fms}
                return manual_graph.commit(session, plan)
            result = graph(commit_with_rules)
            audit('-', plan['by'], 'MANUAL_INGESTED', {key: result[key] for key in
                  ('batch', 'source_id', 'filename', 'sections', 'procedures', 'steps')})
            if body.get('golden_questions'):           # A118: ask right after the commit what this document made answerable
                result['golden'] = start_golden(result['batch'], body['golden_questions'], plan['by'], body.get('golden_request_id'))
            return result
        return await run(work)

    def start_golden(batch, questions, by, request_id=None):
        record = graph(lambda session: manual_golden.batch_knowledge(session, tenant, batch))
        req = manual_golden.request(record, questions, by)
        inst = manual_golden.start(runtime(), req, request_id or str(uuid4()))
        audit('-', req['by'] or '-', 'MANUAL_GOLDEN_REQUESTED', dict(batch=batch, instance=inst['proc_inst_id'], questions=len(req['questions'])))
        return dict(batch=batch, instance=inst['proc_inst_id'], questions=len(req['questions']), knowledge_ids=len(req['knowledge']['ids']))

    @app.post('/api/kg/manuals/batches/{batch}/golden-questions')
    async def golden_questions(batch: str, body: dict):
        """A118 (r14 B3): which questions can the ontology answer because of this document? Opens one agent task that
        answers each question from the graph, citing this document's node ids; GET …/golden-report reads the result."""
        return await run(lambda: start_golden(batch, body.get('questions'), body.get('by'), body.get('request_id')))

    @app.get('/api/kg/manuals/batches/{batch}/golden-report')
    async def golden_report(batch: str, optional: bool = False):
        # A161-U1 (A160 결함 12): the portal asks "is there a report yet?" for every batch on screen; a 404 there is a red
        # console error in the browser for a normal state. optional=1 answers 200 with null instead; without it, 404 as before.
        if optional:
            def maybe():
                try:
                    return manual_golden.result(runtime(), batch)
                except KeyError:
                    return None
            return await run(maybe)
        return await run(lambda: manual_golden.result(runtime(), batch))

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
