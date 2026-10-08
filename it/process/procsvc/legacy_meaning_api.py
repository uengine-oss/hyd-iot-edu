"""A9 옛 DB 뜻 복원 — HTTP: request candidates (agent task) → read them → a person's review → the DDL preview applies only that.

POST /api/kg/ddl/meanings                     DDL text → observation + ontology catalog pinned into one agent task
GET  /api/kg/ddl/meanings/{instance}          task state, observation, validated candidates, earlier reviews
POST /api/kg/ddl/meanings/{instance}/reviews  APPROVE · EDIT · REJECT per candidate → immutable review + audit per decision
The DDL preview takes `meaning_review` (main.py) and the commit refuses a REPRESENTS/meaning no review approved (`check_commit`).
"""
from __future__ import annotations

import asyncio
from uuid import uuid4

from fastapi import HTTPException

from . import ingest, legacy_meaning as lm

ONTOLOGY_Q = ("MATCH (v) WHERE v:StateVariable OR v:Measure "
              "RETURN CASE WHEN v:StateVariable THEN 'StateVariable' ELSE 'Measure' END AS label, v.id AS id, v.name AS name, "
              "v.unit AS unit, coalesce(v.aliases, []) AS aliases ORDER BY id")
ASSETS_Q = "MATCH (a:Asset) RETURN a.id AS id, a.tag AS tag ORDER BY a.id"


def read_ontology(session) -> dict:
    rows = session.run(ONTOLOGY_Q).data()
    out = {'stateVariables': [], 'measures': [], 'assets': session.run(ASSETS_Q).data()}
    for r in rows:
        out['stateVariables' if r['label'] == 'StateVariable' else 'measures'].append(
            {'id': r['id'], 'name': r['name'], 'unit': r['unit'], 'aliases': list(r['aliases'] or [])})
    if not out['stateVariables'] and not out['measures']:
        raise ValueError('온톨로지에 상태 변수·성과 지표가 없어 연결 후보를 만들 수 없습니다 (온톨로지 적재 확인)')
    return out


class Bridge:
    """What main.py needs from A9 without knowing its storage: the review a preview applies, and the commit check."""

    def __init__(self, store_factory, tenant):
        self.store_factory, self.tenant = store_factory, tenant

    def review_for(self, review_id, text):
        if review_id in (None, ''):
            return None
        try:
            row = self.store_factory().get(self.tenant, str(review_id))
        except KeyError:
            raise ValueError('뜻 검토 기록이 없습니다 — 검토를 다시 저장하세요') from None
        if row['sha256'] != lm.text_sha256(text):
            raise ValueError('이 뜻 검토는 다른 DDL 파일의 것입니다 — 같은 파일로 미리보기 하세요')
        return row

    @staticmethod
    def applied(plan, row, refl):
        review = row['review']
        return {'id': row['id'], 'instance': row['instance'], 'by': row['by'], 'createdAt': row['created_at'], **lm.counts(review),
                'applied': lm.apply_links(plan, refl, row['id']), 'commentSql': lm.comment_sql(review),
                'reflected': [{'column': k, 'comment': v['comment'], 'link': v['link']} for k, v in refl.items()]}

    def check_commit(self, plan):
        """A meaning or REPRESENTS reaches the graph only as a review approved it (EDIT = the person's own words)."""
        reviews = {}
        for item in plan['inputs']:
            rid = item.get('meaningReview')
            if rid is None:
                if item.get('represents') is not None:
                    raise ValueError('온톨로지 연결(REPRESENTS)은 사람이 승인한 뜻 검토에서만 올 수 있습니다')
                continue
            if rid not in reviews:
                try:
                    reviews[rid] = self.store_factory().get(self.tenant, rid)['review']
                except KeyError:
                    raise ValueError(f'뜻 검토 기록이 없습니다: {rid}') from None
            want = lm.expected_input(reviews[rid], item)
            where = f"{item['schema']}.{item['table']}.{item['column']}"
            if want == {'represents': None, 'name': None, 'assetColumn': None}:
                raise ValueError(f'이 검토가 승인하지 않은 열입니다: {where}')
            if want['name'] is not None and item['name'] != want['name']:
                raise ValueError(f'승인한 뜻과 입력 이름이 다릅니다: {where}')
            if item.get('represents') != want['represents']:
                raise ValueError(f'승인한 온톨로지 연결과 다릅니다: {where}')
            if want['assetColumn'] is not None and item.get('assetColumn') != want['assetColumn']:
                raise ValueError(f'승인한 설비 식별 열과 다릅니다: {where}')


def register(app, *, driver_factory, tenant, audit, runtime_factory, store_factory, worker_probe):
    async def run(fn):
        try:
            return await asyncio.get_running_loop().run_in_executor(None, fn)
        except HTTPException:
            raise
        except KeyError as exc:
            raise HTTPException(404, str(exc.args[0]) if exc.args else '찾을 수 없습니다') from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    def runtime():
        rt = runtime_factory()
        if rt is None or rt.tenant_id != tenant:
            raise HTTPException(503, 'AI 뜻 후보에는 같은 tenant의 instance 실행 서비스가 필요합니다 (PROCESS_MODE=instance)')
        return rt

    @app.post('/api/kg/ddl/meanings')
    async def request_meanings(body: dict):
        def work():
            text = body.get('text')
            if not isinstance(text, str) or not text.strip():
                raise ValueError('DDL 본문(text)이 필요합니다')
            request_id = body.get('request_id') or str(uuid4())
            rt = runtime()
            tables = ingest.parse_ddl(text)
            if not tables:
                raise ValueError('CREATE TABLE 문을 찾지 못했다')
            try:
                with driver_factory() as drv, drv.session() as session:
                    ontology = read_ontology(session)
            except ValueError as e:
                raise HTTPException(409, str(e)) from e
            except Exception as e:  # noqa: BLE001
                raise HTTPException(502, f'온톨로지(그래프)를 읽지 못해 연결 후보를 만들 수 없습니다: {str(e)[:160]}') from e
            req = lm.request(filename=str(body.get('filename') or 'schema.sql'), text=text, tables=tables, ontology=ontology,
                             datasource=str(body.get('datasource') or 'hyd-enterprise'), catalog=str(body.get('catalog') or 'postgres'),
                             by=body.get('by'))
            worker = worker_probe()
            if not worker.get('reachable'):
                raise HTTPException(503, f"AI 일꾼(워커)에 연결할 수 없어 후보를 요청하지 않았습니다: {worker.get('url')} — "
                                         f"{worker.get('error') or '응답 없음'}. 워커를 켠 뒤 다시 요청하세요")
            inst = lm.start(rt, req, request_id)
            audit('-', req['by'] or '-', 'DDL_MEANING_REQUESTED', dict(instance=inst['proc_inst_id'], filename=req['source']['filename'],
                                                                      columns=len(req['columns'])))
            return dict(instance=inst['proc_inst_id'], status=inst['status'], columns=len(req['columns']), notes=req['notes'])
        return await run(work)

    @app.get('/api/kg/ddl/meanings/{instance_id}')
    async def read_meanings(instance_id: str):
        def work():
            out = lm.result(runtime(), instance_id)
            out['reviews'] = [dict(id=r['id'], by=r['by'], createdAt=r['created_at'], **lm.counts(r['review']),
                                   decisions=r['review']['decisions'])
                              for r in store_factory().list(tenant, instance_id)]
            return out
        return await run(work)

    @app.post('/api/kg/ddl/meanings/{instance_id}/reviews')
    async def review_meanings(instance_id: str, body: dict):
        def work():
            req, wi, candidates = lm.candidates_of(runtime(), instance_id)
            review = lm.validate_review(req, candidates, body)
            row = store_factory().add(tenant, instance_id, wi['id'], req['source'], review)
            for d in review['decisions']:
                audit('-', review['by'], 'DDL_MEANING_' + {'APPROVE': 'APPROVED', 'EDIT': 'EDITED', 'REJECT': 'REJECTED'}[d['verdict']],
                      dict(review=row['id'], instance=instance_id, column=d['column'], before=d['before'], after=d['after'], note=d['note']))
            c = lm.counts(review)
            audit('-', review['by'], 'DDL_MEANING_REVIEWED', dict(review=row['id'], instance=instance_id, **c,
                                                                  undecided=len(candidates) - len(review['decisions'])))
            return dict(id=row['id'], by=row['by'], createdAt=row['created_at'], **c, undecided=len(candidates) - len(review['decisions']),
                        decisions=review['decisions'], commentSql=lm.comment_sql(review),
                        reflected=[{'column': k, **v} for k, v in lm.reflection(review).items()])
        return await run(work)
