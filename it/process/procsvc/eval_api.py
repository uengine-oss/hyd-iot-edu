"""A4 (U6) — AI 판단 채점 HTTP (process 서비스). 순수 로직은 judgment_eval.py, 화면은 portal/www/evaluation.js, CLI 는 scripts/evaluate_judgment.py.

  GET    /api/eval/golden                 정답표(저장된 항목 — 처음엔 비어 있다) + 저장소 종류 + 판단 경로 안내 + 가중치
  POST   /api/eval/golden/items           {item, by}  항목 새로 적기 (모양 검사 + 인용 id 가 지식 그래프에 있는지)
  PUT    /api/eval/golden/items/{id}      {item, by}  항목 고치기
  DELETE /api/eval/golden/items/{id}?by=  항목 지우기
  GET    /api/eval/knowledge              지금 지식 상태 (그래프 지문 · 노드 · 관계 수 · 마지막 변경)
  GET    /api/eval/worker-candidates      채점할 수 있는 지난 처리 건 (에이전트 task 출력 + 제출된 판단이 있는 것)
  POST   /api/eval/runs                   {path: decide|evaluate, items?, repeats?, by, note?}  정답표 항목을 agent 로 N회 판단해 채점
                                          {path: worker, instances: [{instance, item?}], by, note?}  지난 처리 건의 실제 워커 판단을 채점
  GET    /api/eval/runs · /api/eval/runs/{id} · /api/eval/compare?before=&after=
채점은 읽기 전용이다 — agent decide · evaluate 는 제출하지 않고, 처리 건 · 설비 명령 · 기준 데이터를 만들거나 바꾸지 않는다.
"""
from __future__ import annotations

import asyncio
import json
import logging
import urllib.error
import urllib.request
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, Field

from . import judgment_eval as je

log = logging.getLogger('process.eval')
MAX_WORKER_INSTANCES = 50          # 마이그레이션 30 의 repeats 상한과 같다


class RunReq(BaseModel):
    path: str = 'decide'
    by: str
    items: list[str] | None = None
    repeats: int = Field(1, ge=1, le=je.MAX_REPEATS)
    instances: list[dict] | None = None
    note: str | None = None


class GoldenReq(BaseModel):
    item: dict
    by: str


def _post(url: str, body: dict, timeout: float) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body, ensure_ascii=False).encode(), headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors='replace')[:2000]
        try:
            detail = json.loads(raw).get('detail')
        except ValueError:
            detail = raw
        e.reason_text = detail.get('reason') if isinstance(detail, dict) else str(detail)
        raise
    except urllib.error.URLError as e:
        raise ConnectionError(f'에이전트 서비스에 연결할 수 없습니다: {e.reason}') from e


def http_decide(agent_url: str, timeout: float = 60.0):
    """규칙 판단: agent POST /api/agent/decide (정답표의 가정 사실을 넣는다). 409(근거 보류) · 404(후보 없음)는 '보류'로 채점되고,
    연결 실패는 ConnectionError(→ 503) — 0점으로 감추지 않는다."""
    def decide(item: dict) -> dict:
        try:
            return je.normalize_decision(_post(agent_url + '/api/agent/decide', {'asset': item['asset'], 'pattern': item['pattern'], 'facts': item.get('facts') or {}}, timeout))
        except urllib.error.HTTPError as e:
            reason = getattr(e, 'reason_text', '')
            if e.code in (404, 409):
                return je.withheld(f'판단 보류 ({e.code}): {reason}')
            if e.code == 503:
                raise ConnectionError(f'에이전트가 판단할 수 없는 상태입니다: {reason}') from e
            return je.withheld(f'에이전트 오류 ({e.code}): {reason}', status='ERROR')
    return decide


def http_evaluate(agent_url: str, timeout: float = 120.0):
    """에이전트 읽기 평가: agent POST /api/agent/evaluate — 경보 하나를 전체 파이프라인으로 돌리되 제출하지 않는다.
    경보 id 는 채점 전용(EVAL-…)으로 만들어 실제 경보와 섞이지 않게 한다."""
    def evaluate(item: dict) -> dict:
        alert = {'alertId': 'EVAL-' + uuid4().hex[:10], 'asset': item['asset'], 'pattern': item['pattern'], 'state': 'RAISE', 'source': 'judgment-eval'}
        try:
            return je.normalize_evaluation(_post(agent_url + '/api/agent/evaluate', {'alert': alert}, timeout))
        except urllib.error.HTTPError as e:
            reason = getattr(e, 'reason_text', '')
            if e.code == 503:
                raise ConnectionError(f'에이전트가 판단할 수 없는 상태입니다: {reason}') from e
            return je.withheld(f'에이전트 오류 ({e.code}): {reason}', status='ERROR')
    return evaluate


def register(app, *, driver_factory, store_factory, agent_url: str, book: dict, incidents: dict, runtime_factory, audit,
             decide_fn=None, evaluate_fn=None):
    judges = {'decide': decide_fn or http_decide(agent_url), 'evaluate': evaluate_fn or http_evaluate(agent_url)}
    stores: dict = {}

    def store():
        if 'store' not in stores:
            stores['store'] = store_factory()
        return stores['store']

    async def run(fn):
        try:
            return await asyncio.get_running_loop().run_in_executor(None, fn)
        except FileExistsError as exc:
            raise HTTPException(409, f'같은 id 의 정답표 항목이 이미 있습니다: {exc.args[0] if exc.args else exc} — 고치려면 수정하세요') from exc
        except KeyError as exc:
            raise HTTPException(404, f'없는 항목 · 실행 · 처리 건: {exc.args[0] if exc.args else exc}') from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except ConnectionError as exc:
            raise HTTPException(503, str(exc)) from exc

    def graph_read(fn):
        try:
            with driver_factory() as driver, driver.session() as session:
                return session.execute_read(fn)
        except Exception as exc:  # noqa: BLE001 — 지식 상태 · 이름 확인 없이 진행하면 전후 비교 · 정답표가 거짓이 된다
            raise ConnectionError(f'지식 그래프를 읽지 못했습니다: {str(exc)[:160]}') from exc

    def knowledge() -> dict:
        def read(tx):
            return ([r.data() for r in tx.run(je.KNOWLEDGE_Q)], [r.data() for r in tx.run(je.KNOWLEDGE_RELS_Q)],
                    [r.data() for r in tx.run(je.KNOWLEDGE_NODES_Q, skip=je.BOOKKEEPING_LABELS)])
        rows, rels, nodes = graph_read(read)
        return je.knowledge_state(rows, rels, nodes)

    def unknown_ids(ids: list[str]) -> list[str]:
        q = 'UNWIND $ids AS i OPTIONAL MATCH (n {id: i}) WITH i, count(n) AS c WHERE c = 0 RETURN collect(i) AS missing'
        rows = graph_read(lambda tx: [r.data() for r in tx.run(q, ids=ids)])
        return list((rows[0] if rows else {}).get('missing') or [])

    def by_of(by: str) -> str:
        if not isinstance(by, str) or not by.strip():
            raise ValueError('누가 적었는지(by)가 필요합니다')
        return by.strip()[:120]

    # ---------------------------------------------------------------- 정답표
    @app.get('/api/eval/golden')
    async def golden():
        items = await run(lambda: store().golden_list())
        return {'items': items, 'storage': store().kind, 'paths': je.PATH_NOTES, 'weights': je.DEFAULT_WEIGHTS, 'max_repeats': je.MAX_REPEATS,
                'empty_note': None if items else '정답표가 비어 있습니다. 경보 상황마다 기대 원인 · 허용 1위 조치 · 빠질 조치 · 있어야 할 근거를 적어 저장하세요.'}

    def save(req: GoldenReq, create: bool, iid: str | None = None) -> dict:
        by = by_of(req.by)
        item = je.validate_item(req.item)
        if iid is not None and item['id'] != iid:
            raise ValueError(f"주소의 항목 id({iid})와 내용의 id({item['id']})가 다릅니다 — id 는 바꿀 수 없습니다")
        missing = unknown_ids(je.referenced_ids(item))
        if missing:
            raise ValueError('지식 그래프에 없는 이름이 있습니다: ' + ', '.join(missing) + ' — 지식 지도에서 id 를 확인하세요')
        rec = store().golden_put(item, by, create=create)
        audit('-', by, 'JUDGMENT_GOLDEN_SAVED', {'item': item['id'], 'created': create, 'item_hash': rec['item_hash']})
        return rec

    @app.post('/api/eval/golden/items', status_code=201)
    async def golden_create(req: GoldenReq):
        return await run(lambda: save(req, True))

    @app.put('/api/eval/golden/items/{iid}')
    async def golden_update(iid: str, req: GoldenReq):
        return await run(lambda: save(req, False, iid))

    @app.delete('/api/eval/golden/items/{iid}')
    async def golden_delete(iid: str, by: str = ''):
        def work():
            who = by_of(by)
            store().golden_delete(iid)
            audit('-', who, 'JUDGMENT_GOLDEN_DELETED', {'item': iid})
            return {'deleted': iid}
        return await run(work)

    # ---------------------------------------------------------------- 지식 상태 · 후보
    @app.get('/api/eval/knowledge')
    async def knowledge_now():
        return je.public_knowledge(await run(knowledge))

    def runtime():
        rt = runtime_factory()
        if rt is None:
            raise ValueError('지난 처리 건 채점에는 처리 건 기능(PROCESS_MODE=instance)이 필요합니다')
        return rt

    def candidates(limit: int) -> list[dict]:
        rt = runtime()
        items = store().golden_list()
        out = []
        for inst in rt.repo.list_instances(limit=max(limit * 4, 20), tenant_id=rt.tenant_id):
            c = je.instance_candidate(inst, book.get)
            if not c:
                continue
            try:
                c['item'] = je.match_item(items, c)['id']
                c['match_note'] = None
            except ValueError as exc:
                c['item'], c['match_note'] = None, str(exc)
            c.pop('guide_card', None)
            out.append(c)
            if len(out) >= limit:
                break
        return out

    @app.get('/api/eval/worker-candidates')
    async def worker_candidates(limit: int = 20):
        return await run(lambda: candidates(limit))

    # ---------------------------------------------------------------- 채점 실행
    def server_run(req: RunReq, golden: list[dict]) -> list[dict]:
        by_id = {it['id']: it for it in golden}
        wanted = req.items or list(by_id)
        if not wanted:
            raise ValueError('정답표가 비어 있습니다 — 채점할 항목을 먼저 적으세요')
        items = []
        for i in wanted:
            if i not in by_id:
                raise KeyError(i)
            items.append(by_id[i])
        judge = judges[req.path]
        return [je.aggregate(it, [judge(it) for _ in range(req.repeats)], deterministic=req.path == 'decide') for it in items]

    def worker_run(req: RunReq, golden: list[dict]) -> list[dict]:
        if not req.instances:
            raise ValueError('채점할 처리 건(instances)을 하나 이상 고르세요')
        if len(req.instances) > MAX_WORKER_INSTANCES:
            raise ValueError(f'한 번에 채점할 처리 건은 {MAX_WORKER_INSTANCES}건까지입니다')
        rt = runtime()
        by_id = {it['id']: it for it in golden}
        groups: dict[str, list] = {}
        for n, spec in enumerate(req.instances):
            pid = spec.get('instance') if isinstance(spec, dict) else None
            if not pid:
                raise ValueError(f'instances[{n}].instance 가 필요합니다')
            inst = rt.repo.get_instance(pid)
            if not inst:
                raise KeyError(pid)
            cand = je.instance_candidate(inst, book.get)
            if not cand:
                raise ValueError(f'처리 건 {pid} 에는 채점할 에이전트 판단(원인 · 판단 id)이 없습니다')
            if spec.get('item'):
                if spec['item'] not in by_id:
                    raise KeyError(spec['item'])
                item = by_id[spec['item']]
            else:
                item = je.match_item(golden, cand)
            d = book.get(cand['decision_id'])
            inc = incidents.get(((d or {}).get('origin') or {}).get('incident'))
            judged = je.worker_judgement(cand, d, cand.get('guide_card') or getattr(inc, 'card', None))
            groups.setdefault(item['id'], [item, [], []])
            groups[item['id']][1].append(judged)
            groups[item['id']][2].append({k: cand[k] for k in ('instance', 'name', 'status', 'started', 'decision_id', 'chosen_skill')})
        results = []
        for item, judged, cands in groups.values():
            r = je.aggregate(item, judged, deterministic=False)
            r['instances'] = cands
            results.append(r)
        return results

    @app.post('/api/eval/runs', status_code=201)
    async def create_run(req: RunReq):
        if req.path not in je.PATHS:
            raise HTTPException(400, f"path 는 {' | '.join(je.PATHS)} 중 하나입니다")
        if not req.by.strip():
            raise HTTPException(400, '누가 실행했는지(by)가 필요합니다')

        def work():
            golden = store().golden_list()
            state = knowledge()
            results = worker_run(req, golden) if req.path == 'worker' else server_run(req, golden)
            rec = je.new_run(path=req.path, by=req.by, repeats=req.repeats if req.path != 'worker' else max(r['repeats'] for r in results),
                             knowledge=state, results=results, note=req.note)
            store().put(rec)
            audit('-', rec['by'], 'JUDGMENT_EVALUATED', {'run': rec['id'], 'path': rec['path'], 'score': rec['summary']['score'], 'items': rec['summary']['items']})
            return {**rec, 'knowledge': je.public_knowledge(rec['knowledge'])}
        return await run(work)

    @app.get('/api/eval/runs')
    async def list_runs(limit: int = 50):
        return await run(lambda: store().list(limit))

    @app.get('/api/eval/runs/{rid}')
    async def get_run(rid: str):
        rec = await run(lambda: store().get(rid))
        if not rec:
            raise HTTPException(404, '없는 실행입니다')
        return {**rec, 'knowledge': je.public_knowledge(rec['knowledge'])}

    @app.get('/api/eval/compare')
    async def compare_runs(before: str, after: str):
        def work():
            a, b = store().get(before), store().get(after)
            if not a or not b:
                raise KeyError(before if not a else after)
            return je.compare(a, b)
        return await run(work)
