"""업무 시뮬레이터(it/enterprise-sim/entsim/main.py) — 업무 데이터는 Supabase ent 스키마 한 벌, 쓰기는 process 만(하-05).

conftest stack 이 Dockerfile 의 실행 명령 그대로 이 PC 에 띄운 서비스를 HTTP 로 부른다. 응답 규칙: 업무 거절 400(초기화 409) · 멱등 충돌 409 ·
연결 장애 503 · 그 밖 500, detail 은 업무 DB 가 쓴 문장 그대로.
"""
import json
import os
import uuid

import httpx
import psycopg
import pytest

CALLER = {'X-HYD-Process-Caller': os.environ['PROCESS_CALLER_TOKEN']}
WRITES = [('/api/exec', {'decision': 'D-x', 'option': 'o', 'skill': 'skill:없는-스킬', 'asset': 'HYD-01', 'params': {}}),
          ('/api/reanchor', {}), ('/erp/spare/reset', {'part_no': 'P-PMP-SEAL'}), ('/cmms/pm/reset', {})]


def call(url, tool, args):
    """MCP 도구 하나를 실제 클라이언트로 부른다(process · 워커가 부르는 꼴) → (오류인가, 본문 글)."""
    import asyncio
    from fastmcp import Client
    from fastmcp.client.transports import StreamableHttpTransport

    async def run():
        async with Client(StreamableHttpTransport(url)) as c:
            r = await c.call_tool(tool, args, raise_on_error=False)
            return r.is_error, r.content[0].text if r.content else ''
    return asyncio.run(run())


def exec_(stack, body):
    return httpx.post(stack.ent + '/api/exec', json=body, headers=CALLER, timeout=20)


def work_order(decision=None, **params):
    return {'decision': decision or 'DEC-' + uuid.uuid4().hex[:10], 'option': 'opt-1', 'skill': 'skill:schedule-maintenance',
            'asset': 'HYD-01', 'by': 'user:park-maint', 'params': {'task': 'SOP-COOL-04 쿨러 핀 세척', 'window': '즉시', **params}}


@pytest.mark.parametrize('path, body', WRITES, ids=[w[0] for w in WRITES])
@pytest.mark.parametrize('headers', [{}, {'X-HYD-Process-Caller': 'guess'}], ids=['머리글_없음', '틀린_값'])
def test_쓰기_끝점은_process만_아는_값이_없으면_실행하지_않는다(stack, path, body, headers):
    r = httpx.post(stack.ent + path, json=body, headers=headers, timeout=20)
    assert r.status_code == 403 and '사람 승인을 거친 process' in r.json()['detail']


def test_process의_승인된_작업지시는_업무_DB에_한_번_기록되고_같은_요청은_같은_거래를_돌려준다(stack):
    body = work_order()
    first, again = exec_(stack, body), exec_(stack, body)
    assert first.status_code == 200, first.text
    assert again.status_code == 200 and again.json()['id'] == first.json()['id']
    with psycopg.connect(stack.dsn) as db:
        (status,) = db.execute('SELECT status FROM ent.work_orders WHERE id=%s', (first.json()['ref'],)).fetchone()
    assert status == '배정됨'


@pytest.mark.parametrize('body, status, reason', [
    ({'decision': 'D-x', 'option': 'o', 'skill': 'skill:없는-스킬', 'asset': 'HYD-01', 'params': {}}, 400, '업무 시스템에 없는 거래'),
    (dict(work_order(), asset=None), 400, '거래 대상 설비(asset)가 없습니다'),
    (dict(work_order(), params={'window': '즉시'}), 400, '작업 내용(task)이 없습니다'),
], ids=['없는_거래', '설비_없음', '작업_없음'])
def test_업무_DB가_거절한_거래는_까닭_그대로_400이다(stack, body, status, reason):
    r = exec_(stack, body)
    assert r.status_code == status and reason in r.json()['detail']


def test_같은_판단의_같은_거래를_다른_입력으로_다시_보내면_409다(stack):
    body = work_order()
    assert exec_(stack, body).status_code == 200
    r = exec_(stack, dict(body, params=dict(body['params'], task='다른 작업')))
    assert r.status_code == 409 and '멱등 충돌' in r.json()['detail']


def test_원거래_id가_실린_되돌리기는_업무_DB의_되돌리기_함수가_처리한다(stack):
    forward = exec_(stack, work_order()).json()
    r = exec_(stack, {'decision': forward['decision'], 'skill': 'skill:cancel-work-order', 'asset': 'HYD-01', 'by': 'user:park-maint',
                      'params': {'ref': forward['ref']}, 'compensates': forward['id']})
    assert r.status_code == 200, r.text
    assert r.json()['compensates'] == forward['id'] and r.json()['after']['status'] == '취소'


def test_원문_정비_범위_취소는_되돌리기_함수로_가서_원거래를_따진다(stack):
    """G2-01: entsim 의 손 표에 원문 정비 범위 취소가 빠져 「없는 거래」(exec_skill)로 거절됐다 — 이제 되돌리기 함수가 원거래를 확인한다."""
    forward = exec_(stack, work_order()).json()             # 원문 범위 오더가 아닌 거래를 원거래로 대 본다
    r = exec_(stack, {'decision': forward['decision'], 'skill': 'skill:cancel-maintenance-scoped', 'asset': 'HYD-01', 'by': 'user:park-maint',
                      'params': {'ref': forward['ref']}, 'compensates': forward['id']})
    assert r.status_code == 400
    assert 'skill:schedule-maintenance-scoped' in r.json()['detail'] and '업무 시스템에 없는 거래' not in r.json()['detail']


def test_읽기_끝점은_누구나_읽고_없는_대상은_404다(stack):
    ok = httpx.get(stack.ent + '/erp/spare_stock', params={'part': 'P-PMP-SEAL'}, timeout=20)
    missing = httpx.get(stack.ent + '/erp/spare_stock', params={'part': 'P-없음'}, timeout=20)
    assert ok.status_code == 200 and ok.json()['facts']['part_no'] == 'P-PMP-SEAL'
    assert missing.status_code == 404 and 'part=P-없음' in missing.json()['detail']


def test_건강_검사는_업무_DB의_실제_거래_수를_센다(stack):
    """G2-20: 예전에는 거래 300행을 읽어 300에서 잘린 수를 냈다 — 거래를 301건 넘게 둔 뒤 센다(시험 거래는 끝나면 지운다)."""
    tag = 'DEC-health-' + uuid.uuid4().hex[:8]
    with psycopg.connect(stack.dsn, autocommit=True) as db:
        db.execute("INSERT INTO ent.transactions(id, system, skill, ref, detail, asset, decision_id, fingerprint) "
                   "SELECT %s || '-' || g, 'sys:cmms', 'skill:schedule-maintenance', 'WO-x', '건강 검사 시험', 'HYD-01', %s || '-' || g, 'x' "
                   "FROM generate_series(1, 301) g", (tag, tag))
        try:
            (count,) = db.execute('SELECT count(*) FROM ent.transactions').fetchone()
            h = httpx.get(stack.ent + '/healthz', timeout=20).json()
        finally:
            db.execute('DELETE FROM ent.transactions WHERE decision_id LIKE %s', (tag + '-%',))
    assert count > 300 and h['ok'] is True and h['transactions'] == count and h['assets'] == 3


def test_켜질_때_업무_DB가_끝내_답하지_않으면_정한_시간만_기다리고_까닭_한_줄로_실패한다(monkeypatch):
    """G2-20: Docker 를 다시 켜면 업무 DB 가 늦게 떠 시작 훅이 연결 오류 사슬(traceback)로 세 번 죽었다. 업무 DB 자리는 닫힌 포트
    (바깥 — DB 꺼짐), 기다리는 시간은 설정 값 하나만 줄인다. 앱을 실제로 켠다(lifespan)."""
    from starlette.testclient import TestClient
    import entsim.main as entsim_main
    monkeypatch.setattr(entsim_main, 'SUPABASE_DSN', 'postgresql://postgres:postgres@127.0.0.1:9/postgres')
    monkeypatch.setattr(entsim_main, 'START_WAIT_S', 0.5)
    with pytest.raises(RuntimeError) as err, TestClient(entsim_main.app):
        pass
    assert '업무 DB에 연결하지 못했습니다' in str(err.value) and err.value.__cause__ is None and len(str(err.value).splitlines()) == 1


def test_승인한_원문_정비_범위_오더는_묶음_전체를_취소하고_예약한_부품을_돌려준다(stack, tool_servers, course_graph):
    """G2-01: 원문 정비 범위 오더의 되돌리기가 업무 시뮬레이터에서 늘 「없는 거래」로 거절됐다. 실제 판단 엔진(dmn-mcp)이 학생 PC 의 시작 뒤
    그래프로 낸 정기 정비 카드의 정비 계획을 그대로 등록하고(process 가 보내는 모양), 원거래 id 로 묶음 전체를 취소한다."""
    _, causes = call(tool_servers['hyd-dmn'], 'business_causes', {'asset': 'HYD-02', 'pattern': 'PM_DUE'})
    cause = json.loads(causes)['document']
    _, evaluated = call(tool_servers['hyd-dmn'], 'evaluate_cards', {'asset': 'HYD-02', 'pattern': 'PM_DUE', 'cause': cause['top_cause'],
                                                                   'failure_mode': cause['failure_mode']})
    body = json.loads(evaluated)
    assert body['result'] == 'ok', body
    plans = [o for o in body['document']['options'] if (o.get('maintenancePlan') or {}).get('stock_effect') == 'reserve'
             and (o.get('maintenancePlan') or {}).get('code') == 'WO_CREATE']
    # 카드의 실행 가능 판정(예측 · 규정)은 이 테스트 밖이다 — 정비 계획 범위는 업무 DB(ent.pm_scope_check)가 등록할 때 다시 확인한다
    assert plans, '부품을 예약하는 정기 정비 계획이 실린 카드가 없다: ' + json.dumps([dict(id=o.get('id'), feasible=o.get('feasible'), code=(o.get('maintenancePlan') or {}).get('code'), stock=(o.get('maintenancePlan') or {}).get('stock_effect'), violations=o.get('violations')) for o in body['document']['options']], ensure_ascii=False)[:3000]
    plan = plans[0]['maintenancePlan']
    parts = {p['part_no']: p['qty'] for p in plan['parts_totals']}
    with psycopg.connect(stack.dsn) as db:
        before = dict(db.execute('SELECT part_no, reserved FROM ent.spare_stock WHERE part_no = ANY(%s)', (list(parts),)).fetchall())
    decision = 'DEC-' + uuid.uuid4().hex[:10]
    forward = exec_(stack, {'decision': decision, 'option': plans[0]['id'], 'skill': 'skill:schedule-maintenance-scoped', 'asset': 'HYD-02',
                            'by': 'user:park-maint', 'params': {'task': plans[0]['name'], 'plan': plan}})
    assert forward.status_code == 200, forward.text
    undo = exec_(stack, {'decision': decision, 'skill': 'skill:cancel-maintenance-scoped', 'asset': 'HYD-02', 'by': 'user:park-maint',
                         'params': {'ref': forward.json()['ref']}, 'compensates': forward.json()['id']})
    assert undo.status_code == 200, undo.text
    with psycopg.connect(stack.dsn) as db:
        statuses = {s for (s,) in db.execute("SELECT status FROM ent.work_orders WHERE scope_group = (SELECT scope_group FROM ent.work_orders "
                                              "WHERE id=%s)", (forward.json()['ref'],)).fetchall()}
        after = dict(db.execute('SELECT part_no, reserved FROM ent.spare_stock WHERE part_no = ANY(%s)', (list(parts),)).fetchall())
    assert statuses == {'취소'} and after == before
