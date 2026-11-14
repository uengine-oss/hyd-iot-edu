"""처리 기록(it/portal/www/caseRecord.js hydRecord.build) — 처리 건 view 한 건으로 만든 단계 이야기의 차례 · 문장.
node 에서 실제 화면 모듈을 차례대로 실어 build 를 부른다(DOM 없이 도는 부분)."""
import pytest

from www_node import run

FILES = ['ui.js', 'plainWords.js', 'trace.js', 'approvalCard.js', 'resultReport.js', 'caseRecord.js']
T = '2026-10-30T05:44:45.305Z'


def view(workitems, timeline, variables=(), events=()):
    acts = [{'id': w['activity_id'], 'name': w['activity_name'], 'type': 'serviceTask', 'tool': w.get('tool', '')} for w in workitems]
    return {'instance': {'proc_inst_id': 'c.1', 'proc_def_id': 'c', 'status': 'COMPLETED', 'start_date': '2026-10-30T05:40:00Z', 'end_date': T,
                         'variables_data': [{'key': k, 'value': v} for k, v in variables], 'variable_sources': {}},
            'definition': {'id': 'c', 'roles': [], 'gateways': [], 'activities': acts,
                           'events': [{'id': 'S', 'type': 'startEvent', 'name': '시작'}, {'id': 'E', 'type': 'endEvent', 'name': '끝'}], 'sequences': []},
            'workitems': [{'status': 'DONE', 'agent_orch': 'system', **w} for w in workitems],
            'flow_order': {a: i for i, a in enumerate(timeline)}, 'events': list(events), 'approvals': []}


def titles(v, ext=None):
    return run(FILES, "out(hydRecord.build(DATA.v, DATA.ext, []).steps.map(s => s.title))", {'v': v, 'ext': ext or {'agents': [], 'people': []}})


def test_같은_순간에_끝난_시스템_단계는_흐름_순서대로_보인다():
    """W1-01: 정비 오더 등록과 결과 보고가 한 트랜잭션에서 같은 시각에 끝나 「결과 보고 → 정비 오더」로 거꾸로 보였다."""
    wis = [{'id': 'w2', 'activity_id': 'R_ok', 'activity_name': '결과 보고: 정상', 'start_date': T, 'end_date': T},
           {'id': 'w1', 'activity_id': 'T_wo', 'activity_name': '작업지시 등록', 'start_date': T, 'end_date': T}]
    assert titles(view(wis, ['T_wo', 'R_ok'])) == ['시작', '작업지시 등록', '결과 보고: 정상', '처리 완료']


def test_처리_기록을_그려도_다른_화면의_값_이름이_정의_설명문으로_바뀌지_않는다():
    """W1-02: 처리 건 정의의 칸 설명(「판정한 원인 노드 id …」)이 전역 이름 사전을 덮어 승인 카드 · 다른 처리 건까지 바뀌었다."""
    v = view([{'id': 'w1', 'activity_id': 'T_a', 'activity_name': '원인 진단', 'start_date': T, 'end_date': T}], ['T_a'])
    v['definition']['startForm'] = {'fields_json': [{'key': 'cause', 'text': '판정한 원인 노드 id (예: cause:cooler-fin-fouling)'}]}
    got = run(FILES, "const before = hydWords.fieldName('cause'); hydRecord.build(DATA, { agents: [], people: [] }, []); out([before, hydWords.fieldName('cause')])", v)
    assert got == ['판정 원인', '판정 원인']


@pytest.mark.parametrize('sim_s, wall, expected', [
    (1200.0, ('05:43:42.085', '05:44:45.557'), '설비 시간 20분 (실제 1분 3초) 동안'),   # 연장 뒤 판정 줄의 설비 시간(시작 줄 15분이 아니라)
    (900.0, ('05:43:42.000', '05:44:27.000'), '설비 시간 15분 (실제 45초) 동안'),
])
def test_효과_확인_문장은_설비_시간과_실제_시간을_한_형식으로_적는다(sim_s, wall, expected):
    """W1-03: 효과 확인 단계가 「1분 3초 동안」(실제)만 말해 같은 카드의 「설비 시간 15분」과 어긋났다."""
    a, b = (f'2026-10-30T{t}Z' for t in wall)
    inc = {'id': 'INC-1', 'asset': 'HYD-01', 'state': 'CLOSED', 'recoveryPolicy': {'criterion': ['TS1', '<', 55]},
           'history': [{'state': 'RE_OBSERVING', 't': a, 'reobservation': {'sim_s': 900}},
                       {'state': 'RESOLVED', 't': b, 'note': '재관측 결과 회복', 'reobservation': {'tag': 'TS1', 'op': '<', 'limit': 55, 'value': 51.2, 'cleared': True, 'recovered': True, 'sim_s': sim_s}}],
           'reobsSeries': {'tag': 'TS1', 'op': '<', 'limit': 55, 'first': 60.8, 'last': 51.2, 'inside_share': 0.64, 'inside_last': True, 'from': a, 'to': b,
                           'points': [{'t': a, 'v': 60.8}, {'t': b, 'v': 51.2}]}}
    wis = [{'id': 'w1', 'activity_id': 'T_reobs', 'activity_name': '재관측', 'tool': 'incident:reobserve', 'start_date': a, 'end_date': b, 'output': {'recovered': True}}]
    v = view(wis, ['T_reobs'], variables=[('incident', 'INC-1'), ('recovered', True)])
    got = run(FILES, "const m = hydRecord.build(DATA.v, { agents: [], people: [], incident: DATA.inc }, []); out(m.steps.find(s => s.title === '재관측').sentence)",
              {'v': v, 'inc': inc})
    assert got.startswith(expected) and '기준(55 ℃ 아래) 안에 있던 시간 64 %' in got, got


def test_발주_단계의_공급사는_승인_때_확정한_업무_DB_공급사_이름으로_보인다():
    """넘김 FW → FT 덧: 공급사(sup:*)는 업무 DB 동기화로만 생겨 이름 사전에 없고, 판단 카드 선택지에 없으면 화면에 sup:c 가 보였다."""
    wis = [{'id': 'w1', 'activity_id': 'T_po', 'activity_name': '발주', 'tool': 'mcp__enterprise-purchase__PR_CREATE', 'start_date': T, 'end_date': T,
            'output': {'purchase_order': {'ref': 'PO-7'}}}]
    v = view(wis, ['T_po'], variables=[('approved_supplier', 'sup:c'), ('approved_supplier_name', '대성유압'), ('approved_qty', 2)])
    got = run(FILES, "out(hydRecord.build(DATA, { agents: [], people: [] }, []).steps.find(s => s.title === '발주').sentence)", v)
    assert '대성유압' in got and 'sup:c' not in got, got


def test_처리_기록의_원문_칸은_코드_값을_이름으로_바꾸지_않고_경로만_가린다():
    """한바퀴3: 「물은 원문」의 "pattern": "COOLER_DEGRADATION" 이 설명용 이름 바꾸기(UI.words)로 "쿨러 성능 저하"가 돼, 원문이 실제 호출과 달랐다."""
    # 원문 칸은 원문 판 하나(UI.raw — 이 PC 경로 · 모델 이름만 가린다)로 그린다
    got = run(FILES, "UI.patterns = {COOLER_DEGRADATION: '쿨러 성능 저하'}; out([UI.raw(DATA, { mask: true }), UI.clean('COOLER_DEGRADATION 경보')])",
              {'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION', 'file': '/home/user/work/result.json'})
    assert '&quot;pattern&quot;: &quot;COOLER_DEGRADATION&quot;' in got[0] and '쿨러 성능 저하' not in got[0]
    assert '&quot;file&quot;: &quot;result.json&quot;' in got[0] and '/home/user' not in got[0]
    assert got[1] == '쿨러 성능 저하 경보', '설명 문장(UI.clean)은 그대로 이름으로 바꾼다'


def test_결과_카드는_끝_이벤트_이름이_끝이면_끝난_곳을_따로_적지_않고_반려는_실패_색으로_칠하지_않는다():
    """「끝난 곳: 끝」처럼 뜻 없는 줄이 결과 카드에 나왔다. 끝 이벤트에 뜻 있는 이름(거절 종결)이 있을 때만 한 문장으로 적는다."""
    def card(report, end_label):
        v = view([{'id': 'w1', 'activity_id': 'R', 'activity_name': '결과 보고', 'start_date': T, 'end_date': T}], ['R'], variables=[('result_report', report)])
        v['instance']['end_label'] = end_label
        return run(FILES, "out(hydResultReport.html(DATA))", v)
    ok = card({'outcome': '정상', 'level': 'ok', 'title': 'HYD-01 긴급 대응 결과', 'summary': '유온 정상 · 경보 해제'}, '끝')
    assert '끝난 곳' not in ok and '에서 끝났습니다' not in ok
    assert '<div class="result-main">유온 정상 · 경보 해제</div>' in ok and 'data-tone="ok">정상</span>' in ok
    rejected = card({'outcome': '반려', 'verdict': 'rejected', 'title': 'HYD-01 냉각 조치 결과', 'summary': '담당자가 거절했습니다'}, '거절 종결')
    assert '처리 건은 「거절 종결」에서 끝났습니다.' in rejected
    assert 'data-tone="danger"' not in rejected and '<span class="tag">반려</span>' in rejected


def test_워커가_아직_가져가지_않은_AI_단계는_사람_단계로_그리지_않는다():
    """독립 검토 가-4: AI 에이전트가 맡은 작업 행은 워커가 가져가기 전 잠깐 agent_orch 가 비어 있다 — 그 순간 사람 단계(승인 대기)로 보였다."""
    wis = [{'id': 'w1', 'activity_id': 'T_agent', 'activity_name': '원인 진단', 'start_date': T, 'status': 'IN_PROGRESS', 'agent_orch': None, 'agent_mode': None, 'user_id': 'agent:cooling'}]
    v = view(wis, ['T_agent'])
    v['instance']['status'] = 'RUNNING'
    got = run(FILES, "out(hydRecord.build(DATA.v, DATA.ext, []).steps.map(s => [s.type, s.lane]))", {'v': v, 'ext': {'agents': [], 'people': []}})
    assert got[1] == ['agent', 'agent']
