"""조치 판단(it/agent/agentsvc/decide.py) — 판단 사실은 온톨로지가 정한 원천에서, 읽지 못하면 그 자리 까닭으로 멈춘다(H-8),
가정 실험의 바꿔 넣는 값은 판단 변수의 형식으로만. 실제 agent 서비스(stack) · 실제 그래프 · 업무 시스템(enterprise-sim)을 지난다."""
import json
import math
import threading
import time
import urllib.error
import urllib.request

import pytest

from agentsvc import decide

INPUTS = [{'variable': 'hours_at_next_window', 'name': '다음 정비 창까지 시간', 'typeRef': 'number'},
          {'variable': 'ambient_c', 'name': '외기 온도', 'typeRef': 'number'},
          {'variable': 'avl_ok', 'name': '승인 공급사', 'typeRef': 'boolean'},
          {'variable': 'plc_mode', 'name': 'PLC 상태', 'typeRef': 'enum'},
          {'variable': 'note_blob', 'name': '첨부', 'typeRef': 'object'}]


@pytest.mark.parametrize('overrides, expect', [
    ({'hours_at_next_window': 12}, {'hours_at_next_window': 12}),
    ({'hours_at_next_window': 0}, {'hours_at_next_window': 0}),
    ({'ambient_c': -5.0}, {'ambient_c': -5.0}),
    ({'avl_ok': False, 'plc_mode': 'REMOTE_MANUAL'}, {'avl_ok': False, 'plc_mode': 'REMOTE_MANUAL'}),
    (None, {}),
], ids=['시간', '경계 0', '온도는 음수 가능', '참거짓 · 글', '없음'])
def test_가정_실험은_지식에_있는_판단_변수만_그_형식으로_바꿔_넣는다(overrides, expect):
    assert decide.check_overrides(INPUTS, overrides) == expect


@pytest.mark.parametrize('overrides, needle', [
    ({'secret_fact': 1}, '바꿔 넣을 수 없는 사실'),
    ({'hours_at_next_window': -1}, '음수일 수 없습니다'),
    ({'hours_at_next_window': '12'}, '숫자를 넣습니다'),
    ({'hours_at_next_window': True}, '숫자를 넣습니다'),
    ({'hours_at_next_window': math.inf}, '숫자를 넣습니다'),
    ({'avl_ok': 1}, '참 · 거짓'),
    ({'plc_mode': '  '}, '비어 있지 않은 글'),
    ({'note_blob': {}}, '바꿀 수 없습니다'),
], ids=['지식에 없는 변수', '음수 시간', '글자 숫자', '참거짓을 숫자로', '무한대', '숫자를 참거짓으로', '빈 글', '바꿀 수 없는 형식'])
def test_형식이_다르거나_음수_시간인_가정값은_변수_이름과_함께_거절한다(overrides, needle):
    """G5a-7 ③: 음수 시간 · 형식이 다른 값이 그대로 규칙에 들어갔다."""
    with pytest.raises(ValueError) as e:
        decide.check_overrides(INPUTS, overrides)
    assert needle in str(e.value)


def test_판단_id_는_서비스_이름을_달고_재시작해도_겹치지_않는다():
    a, b = decide.DecisionRegistry('agent'), decide.DecisionRegistry('agent')
    ids = {a.new_id('DEC'), b.new_id('DEC'), a.new_id('EVAL')}
    assert len(ids) == 3 and all(i.split('-')[2] == 'agent' for i in ids)
    with pytest.raises(ValueError):
        a.new_id('RUN')
    with pytest.raises(ValueError):
        decide.DecisionRegistry('portal')


def test_원천을_못_읽은_판단_사실은_무엇을_어디서_왜_로_말한다():
    e = decide.FactUnavailable('hours_at_next_window', '다음 정비 창까지 시간', 'sys:mes', '업무 시스템이 15초 안에 답하지 않았습니다')
    assert str(e) == ('판단 사실 「다음 정비 창까지 시간」을 원천(sys:mes)에서 읽지 못해 판단을 멈췄습니다 — '
                      '업무 시스템이 15초 안에 답하지 않았습니다') and e.variable == 'hours_at_next_window'


# ---------------------------------------------------------------- 실제 agent 서비스
def post(url, body, timeout=90):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'null')


@pytest.fixture
def cooling(world):
    """HYD-01 쿨러 오염이 끝까지 진행돼 유온이 경보선 위에 머문 설비가 30분째 보고하는 상태(경보 · 처리 건은 없음)."""
    world.plant.inject('HYD-01', 'cooler_degradation', severity='moderate')
    world.settle(1800)
    world.reported_for('HYD-01')
    return world


def test_업무_시스템이_답하면_수동_판단이_조치_카드를_순위대로_낸다(cooling):
    status, d = post(cooling.stack.services['agent'].url + '/api/agent/decide', {'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION'})
    assert status == 200 and d['status'] in ('EVALUATED', 'NO_FEASIBLE_OPTION') and 'error_code' not in d, d.get('error')
    options = d['result']['options']
    assert options and [o['rank'] for o in options] == sorted(o['rank'] for o in options)
    assert d['provenance'] and all(p['how'] for p in d['provenance'])      # 사실마다 어느 원천에서 어떻게 읽었는지


def test_업무_시스템이_답하지_않으면_판단은_그_자리_까닭으로_멈추고_다시_시도할_수_있다(cooling):
    """H-8: 업무 시스템 읽기 실패가 None 으로 삼켜져 「값 없음」으로 판단했다(decide.py 250-252 · 354-356 옛 줄)."""
    agent = cooling.stack.services['agent'].url + '/api/agent/decide'
    with cooling.stack.services['enterprise-sim'].paused():
        status, d = post(agent, {'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION'})
    assert status == 200 and d['status'] == 'FAILED' and d['error_code'] == 'SOURCE_UNAVAILABLE'
    assert '읽지 못해 판단을 멈췄습니다' in d['error'] and '15초 안에 답하지 않았습니다' in d['error'] and '다시 시도' in d['error']
    assert not d.get('result')
    cooling.reported_for('HYD-01', seconds=120)     # 업무 시스템이 멈춘 동안에도 설비는 1초마다 보고했다(근거 구간에 빈칸이 없다 — 시험 시간과 무관하게)
    status, again = post(agent, {'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION'})          # 다시 답하면 같은 요청이 그대로 된다
    assert status == 200 and again['status'] != 'FAILED', again.get('error')


# ---------------------------------------------------------------- 예측에 쓰는 설비 상태가 낡았을 때(벽시계 15초 — decide.MAX_APPROVAL_FACT_AGE_S)
class _Handed(dict):
    """process 가 들고 있는 설비 최신 상태(main.plant_status)에 붙인 관측 지점: 판단이 그 설비의 상태를 읽어 간 때를 시험이 안다(값 · 동작은 그대로)."""
    def __init__(self, held, asset):
        super().__init__(held)
        self.asset, self.read = asset, threading.Event()

    def get(self, key, default=None):
        if key == self.asset:
            self.read.set()
        return super().get(key, default)


def _cooling_alert(world, monkeypatch, late_s):
    """쿨러 오염으로 유온이 경보선 위에 머문 HYD-01 에 냉각 성능 저하 경보가 올라 처리 건이 AI 판단 단계에서 기다린다. 그동안 process 가 받은
    설비 상태는 late_s 초 전에 관측된 것 하나뿐이다(수집이 그만큼 밀렸다). 돌려줌 = (처리 건 id, 판단이 상태를 읽어 간 때를 아는 관측 지점)."""
    from datetime import datetime, timedelta, timezone
    from conftest import COOLING
    from hydcommon import topics
    pattern, asset = COOLING
    world.plant.inject(asset, 'cooler_degradation', severity='moderate')
    world.settle(1800)
    tags = world.plant.tags(asset)
    _, pid = world.raise_alert(pattern, asset, ts1=tags['TS1'], ce=tags['CE'])
    world.stack.timescale.write(asset, tags)
    seen = (datetime.now(timezone.utc) - timedelta(seconds=late_s)).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
    world.receive(topics.K_STATUS, world.plant.status(asset, seen))
    handed = _Handed(world.main.plant_status, asset)
    monkeypatch.setattr(world.main, 'plant_status', handed)
    return pid, handed


def _decisions_of(world, pid):
    return [d for d in world.main.book.values() if ((d.get('origin') or {}).get('process_scope') or {}).get('instance') == pid]


def test_판단할_때_낡았던_설비_상태가_몇_초_뒤_새로_들어오면_제외가_굳지_않고_정상_판단이_등록된다(world, monkeypatch):
    """2026-11-14 01:01 처리 건: 수집이 잠깐 밀려 15초 넘은 설비 상태를 한 번 읽은 판단이 네 안을 모두 「현재 조치 예측을 확인할 수 없습니다」
    제외로 저장했고, 1초 뒤 값이 돌아왔는데도 그 건은 승인할 수 없었다. 실제 워커(재생) · 실제 판단 등록(dmn-mcp)으로 본다."""
    pid, handed = _cooling_alert(world, monkeypatch, late_s=15.5)
    box = {}
    run = threading.Thread(target=lambda: box.update(handled=world.runner('replay').poll_once()))
    run.start()
    assert handed.read.wait(120), '판단이 설비 상태를 읽지 않았다'
    time.sleep(3)                               # 판단은 낡은 값을 받은 채 3초를 더 기다린다
    world.report('HYD-01')                      # 설비 보고가 다시 들어온다(지금 값)
    run.join(180)
    row = world.row(pid, 'T_agent')
    assert box.get('handled') == 1 and row['status'] in ('SUBMITTED', 'DONE'), (box, row['status'], world._failure(row))
    (made,) = _decisions_of(world, pid)
    assert made['recommended'], made.get('explanation')
    for option in made['options']:
        assert not (option.get('forecastContext') or {}).get('error'), option['forecastContext']
        assert not [v for v in option['violations'] if v['rule'] == 'forecast:model-unavailable'], option['violations']
        assert 0 <= option['forecastContext']['provenance']['age_seconds'] <= decide.MAX_APPROVAL_FACT_AGE_S


def test_설비_상태가_끝내_새로_들어오지_않으면_모든_안을_제외한_판단을_등록하지_않고_그_까닭으로_단계가_멈춘다(world, monkeypatch):
    """낡은 값으로 예측하지도, 「예측 미확인」으로 모든 안을 제외한 판단을 남기지도 않는다 — 판단 사실을 못 읽은 것과 같은 길(FactUnavailable)로
    멈추고, 그 단계는 실패로 남아 사람이 다시 수행할 수 있다(처리 건은 닫히지 않는다)."""
    pid, handed, said = _stopped_for_stale_state(world, monkeypatch)
    assert '설비 상태' in said and '새로 들어오지 않았습니다' in said and '판단을 멈췄습니다' in said, said
    assert 'forecast_ts1' not in said and '시뮬레이터' not in said, said
    status, view = world.api('GET', f'/api/instances/{pid}')
    assert status == 200 and view['instance']['status'] == 'RUNNING', view
    (stuck,) = view['attention']['steps']
    assert (stuck['activity'], stuck['kind'], stuck['actions']) == ('T_agent', 'failed', ['rework', 'close']) and stuck['reason'] == said, stuck


def _stopped_for_stale_state(world, monkeypatch):
    """설비 상태가 끝내 새로 들어오지 않아 재생 워커의 AI 판단 단계가 실패로 멈춘 처리 건 → (처리 건 id, 관측 지점, 학생 문장)."""
    from agentsvc import forecasting
    from worker import ai_replay
    monkeypatch.setattr(ai_replay, 'WRITE_RETRY_WAITS_S', (0.2, 0.2))      # 시도 사이의 기다림만 줄인다(시도마다 판단 서비스가 8초를 다시 읽는다)
    pid, handed = _cooling_alert(world, monkeypatch, late_s=15.5)
    started = time.monotonic()
    handled = world.runner('replay').poll_once()
    waited = time.monotonic() - started
    assert _decisions_of(world, pid) == []
    row = world.row(pid, 'T_agent')
    assert handled == 1 and (row['status'], row['draft_status']) == ('IN_PROGRESS', 'FAILED'), (handled, row['status'], row['draft_status'])
    # 바로 포기하지 않았다: 판단 서비스가 한 번에 8초를 다시 읽고, 워커가 그 판단 등록을 세 번 불렀다
    assert handed.read.is_set() and waited >= 3 * (forecasting.SOURCE_REREAD_FOR_S - 1), waited
    return pid, handed, world._failure(row)['friendly']


def test_판단_등록이_끝내_안_되면_학생_문장에_도구의_내부_이름과_응답_원문이_없고_원문_칸에_남는다(world, monkeypatch):
    """재생 모드의 실패 문장이 「…에서 AI가 부른 hyd-dmn/submit_decision이(가) 이 PC에서 거절됐습니다: { "result": "error", "error_kind":
    "UNKNOWN", … }」였다 — 무엇을 하다가 · 왜 · 다음에 무엇을 하는지만 말하고, 도구 이름과 응답 원문은 원문 칸(raw_error)에 둔다."""
    from student_words import JARGON, WORKER_TALK
    pid, _, said = _stopped_for_stale_state(world, monkeypatch)
    failure = world._failure(world.row(pid, 'T_agent'))
    assert '등록하지 못했습니다' in said and '3번 시도' in said and '다시 수행' in said, said
    assert all(word not in said for word in ('hyd-dmn', 'submit_decision', 'error_kind', 'UNAVAILABLE', '{', '을(를)')), said
    assert not WORKER_TALK.search(said) and not JARGON.search(said), said
    assert 'hyd-dmn/submit_decision' in failure['raw_error'] and 'UNAVAILABLE' in failure['raw_error'], failure['raw_error']


def test_판단_등록이_값을_받지_못해_안_됐다가_값이_들어오면_같은_실행_안에서_다시_불러_끝까지_간다(world, monkeypatch):
    """판단 서비스가 8초를 다시 읽고도 설비 값을 받지 못해 판단을 멈춘 한 번이 재생 모드에서 그 단계의 실패로 굳었다. 판단 서비스가 그 까닭을
    「아직 받지 못함」 종류로 돌려주고(옛 판은 UNKNOWN — 엔진 결함과 구별되지 않았다), 워커가 같은 실행 안에서 기다렸다 다시 부른다."""
    from worker import ai_replay
    pid, handed = _cooling_alert(world, monkeypatch, late_s=15.5)
    waits = []

    def state_arrives(seconds, check_stop):       # 워커가 다음 시도를 기다리는 동안 설비 보고가 다시 들어온다
        waits.append(seconds)
        world.report('HYD-01')
    monkeypatch.setattr(ai_replay, '_wait', state_arrives)
    handled = world.runner('replay').poll_once()
    row = world.row(pid, 'T_agent')
    assert handled == 1 and row['status'] in ('SUBMITTED', 'DONE'), (row['status'], world._failure(row))
    assert waits == [ai_replay.WRITE_RETRY_WAITS_S[0]], waits                 # 첫 등록이 「아직 받지 못함」으로 안 됐고 한 번 기다린 뒤 됐다
    (made,) = _decisions_of(world, pid)
    assert made['recommended'] and world._failure(row) is None


def test_재생_모드에서_실패한_AI_단계를_다시_수행하면_그_처리_건에서_지금_값으로_판단이_등록된다(world, monkeypatch):
    """키 없는 PC: AI 단계가 한 번 실패하면 [다시 수행]이 「재작업으로 다시 하는 것을 지원하지 않습니다 … 새 처리 건으로」로 멈춰 그 건을 다시
    해 볼 길이 없었다. 다시 수행은 같은 단계를 같은 입력으로 새로 하는 것이므로 저장된 첫 실행의 응답을 내고, 판단은 이 PC에서 지금 값으로 등록한다."""
    from conftest import OPERATOR
    import uuid
    pid, _, _ = _stopped_for_stale_state(world, monkeypatch)
    failed = world.row(pid, 'T_agent')
    plan = world.rt.preview_rework(pid, failed['id'])
    assert not plan['blockers'], plan['blockers']
    result = world.rt.request_rework(pid, failed['id'], str(uuid.uuid4()), plan['snapshot_token'], OPERATOR['by'], OPERATOR['role'], '설비 값이 다시 들어옴')
    world.report('HYD-01')
    assert world.runner('replay').poll_once() == 1
    again = world.row(pid, 'T_agent')
    assert again['id'] == result['start_workitem'] != failed['id'] and again['status'] in ('SUBMITTED', 'DONE'), (again['status'], world._failure(again))
    (made,) = _decisions_of(world, pid)
    assert made['recommended'] and made['origin']['process_scope']['generation'] == 1 == world.inst(pid)['rework_generation']


@pytest.mark.parametrize('facts, needle', [({'fan100_hours': -5}, '음수일 수 없습니다'), ({'secret_fact': 1}, '바꿔 넣을 수 없는 사실')],
                         ids=['음수 시간', '지식에 없는 변수'])
def test_수동_판단에_틀린_사실을_넣으면_엔진이_422와_그_문장으로_거절한다(cooling, facts, needle):
    """한바퀴3 고침 4: 판단 엔진이 틀린 입력을 200 · status FAILED(판단 실패와 같은 꼴)로 돌려줬다 — 입력 거절은 4xx 다."""
    status, d = post(cooling.stack.services['agent'].url + '/api/agent/decide', {'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION', 'facts': facts})
    assert status == 422 and needle in str(d.get('detail')), (status, d)


def test_지금_설비를_세우고_세척하는_카드는_정지한_설비로_예측해_유온이_경보선_아래로_내려간다(cooling):
    """G1-05: 정지 · 세척 카드(SOP-COOL-14 — 작업지시만, 지금 시행)를 「운전 계속」으로 예측해 거짓 62 ℃ 로 졌다. 판단(decide)이
    cards.option_window → stops_now 로 정한 카드를 forecasting.candidates 에 정지로 넘기는지 실제 스택에서 본다."""
    status, d = post(cooling.stack.services['agent'].url + '/api/agent/decide', {'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION'})
    assert status == 200 and 'error_code' not in d, d.get('error')
    options = {o['sopId']: o for o in d['result']['options']}
    ts1 = {sop: next((x['value'] for x in o['forecast'] if x['variable'] == 'sv:ts1'), None) for sop, o in options.items()}
    assert ts1.get('SOP-COOL-14') is not None, ts1
    assert ts1['SOP-COOL-14'] < 55, f'정지한 설비의 예측이 아니다(운전 계속이면 경보선 위): {ts1}'


def test_판단_기록의_장면_이름은_학생이_읽는_고장_이름으로_쓴다(cooling):
    """W1-13: 장면 이름이 dec:rank-actions(id)로 학생에게 보였다."""
    status, d = post(cooling.stack.services['agent'].url + '/api/agent/decide', {'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION'})
    assert status == 200 and 'error_code' not in d, d.get('error')
    scenario = d['scenario']
    assert scenario['name'].endswith('조치 판단') and ':' not in scenario['name'], scenario     # 센서 출처 문장은 test_approval(원천을 새로 읽는 길)


from test_mcp_tsdb import asset, put, tsdb, tsdb_module  # noqa: E402,F401 — 시계열 읽기 준비(compose agent 의 읽기 계정 · 설비 이름)


def test_원천에서_새로_읽은_센서_사실은_학생이_읽는_센서_이름과_나이로_출처를_적는다(seeded_graph, timescale, tsdb, asset):
    """W1-13: 센서 사실 출처가 태그 id 만으로 학생에게 보였다. 판단 · 승인 검사는 경보 · 진단이 이미 정한 값이 없을 때 센서를
    시계열에서 읽는다 — 지식(시드 InputData in:ts1 → sen:ts1)과 실제 시계열로 그 길을 지난다."""
    import re
    from agentsvc.tools import mcp_kg
    inputs = [i for i in mcp_kg.KnowledgeGraph().inputs() if i['variable'] == 'ts1']
    put(timescale, asset, [('TS1', 51.5, 3)])
    facts, prov = decide.gather_facts(inputs, asset, {}, tsdb, variables={'ts1'})
    (row,) = prov
    assert facts['ts1'] == 51.5 and re.fullmatch(r'설비 센서 「유온」 최신값\(\d+초 전\)', row['how']), row


def test_승인_역할이_구매_담당이_아닌_구매_절차도_재고_보충_판단의_후보가_된다(world, course_graph):
    """전수검사 10-G5: 판단 엔진이 구매 후보를 승인 역할 = 구매 담당(role:purchasing)인 절차로만 걸러, 구매 팀장이 승인하는 구매 문서는 후보에서
    조용히 빠지고 판단이 「구매 후보 지식이 없습니다: PR_CREATE만 수행하는 work_order 스킬과 후보 규칙을 확인하세요」로 실패했다 — 진짜 까닭(승인
    역할)과 다른 말이다. 수업 구매 문서(PR-07)의 절차 셋을 구매 팀장 승인으로 바꾼 지식에서 같은 재고 보충 판단을 돌린다."""
    moved = course_graph.query(
        "MATCH (k:Skill {scope:'purchase'})-[old:APPROVED_BY]->(:Role {id:'role:purchasing'}) WHERE k.executable = true "
        "MATCH (mgr:Role {id:'role:purchasing-mgr'}) CREATE (k)-[new:APPROVED_BY]->(mgr) SET new = properties(old) DELETE old RETURN k.id AS id")
    assert len(moved) == 3, moved
    status, out = world.api('POST', '/api/scenario/C/start', {'by': '담당자', 'user_id': 'user:me', 'roles': ['role:purchasing']}, source_loop=True)
    assert status == 200, out
    did = world.agent(out['instance'], 'T_agent')
    cards = world.main.book[did]['options']
    assert {o['id'] for o in cards} == {m['id'] for m in moved} and world.main.book[did]['recommended'] == 'skill:sop-pur-11'
    assert {o['approver']['id'] for o in cards} == {'role:purchasing-mgr'}
