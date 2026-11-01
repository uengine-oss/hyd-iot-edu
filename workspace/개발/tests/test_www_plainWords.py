"""포털 이름 사전(it/portal/www/plainWords.js) — 값 이름 · 비교 기호 · 도구 이름이 한 곳에서 정해지는지. node 로 실제 사전을 부른다."""
import pytest

from www_node import run

FILES = ['ui.js', 'plainWords.js', 'toolNames.js']


@pytest.mark.parametrize('key, case_fields, expected', [
    # 처리 건 정의의 칸 설명(에이전트 출력 계약 문장)이 화면 사전 이름을 덮지 않는다(W1-02 — 처리 기록을 한 번 그리면 「판정한 원인 노드 id …」로 바뀌었다)
    ('cause', {'cause': '판정한 원인 노드 id (예: cause:cooler-fin-fouling)'}, '판정 원인'),
    ('asset', {'asset': '경보가 난 설비 (상관 키, 예: HYD-01)'}, '설비'),
    ('decision_id', {'decision_id': 'submit_decision 이 돌려준 조치 카드 묶음 id'}, '조치 카드 묶음 번호'),
    # 사전에 없는 칸(학생 흐름이 만든 칸)은 그 흐름이 붙인 화면 이름
    ('oil_iso', {'oil_iso': 'ISO 청정도'}, 'ISO 청정도'),
    ('oil_iso', {}, 'oil iso'),
])
def test_값_이름은_화면_사전이_이기고_사전에_없는_칸만_처리_건_이름을_쓴다(key, case_fields, expected):
    assert run(FILES, "hydWords.caseFields = DATA.cf; out(hydWords.fieldName(DATA.key))", {'cf': case_fields, 'key': key}) == expected


@pytest.mark.parametrize('op, sym', [('>=', '≥'), ('<=', '≤'), ('==', '='), ('!=', '≠'), ('lt', '<'), ('lte', '≤'), ('gt', '>'), ('gte', '≥'),
                                     ('eq', '='), ('ne', '≠'), ('<', '<'), ('~', '~')])
def test_비교_기호는_식_기호와_규칙_낱말_연산자를_한_표로_바꾼다(op, sym):
    """W1-11: 비교 기호가 네 벌이라 승인 증거에 「lte」 원문이 보였다."""
    assert run(FILES, "out(hydWords.sym(DATA))", op) == sym


@pytest.mark.parametrize('tool, name, known', [
    ('mcp__hyd-dmn__gather_facts', '판단 사실 모으기', True),               # 화면마다 「사실 수집」 · 「판단 사실 수집」으로 달랐다(W3-09)
    ('mcp__enterprise-maint__pm_status', '정비 계수기 · 계획 조회', True),   # 업무 서버 세 벌(전부 · 정비 · 구매)은 도구 이름으로 찾는다
    ('mcp__enterprise-purchase__describe_schema', '업무 자료 구조 보기', True),
    ('mcp__neo4j__write_neo4j_cypher', '지식 그래프 쓰기', True),
    ('hyd-dmn/evaluate_cards', '대안 평가 (후보 · 규정 · 득실 · 순위)', True),   # 워커 기록의 「서버/도구」 꼴
    ('shell', '명령 실행', True),
    ('mcp__student__foo', '도구 표시 이름 확인 중', False),                  # 사전 · 등록 목록에 없으면 지어내지 않고 그 상태를 말한다
])
def test_도구_이름은_사전_하나에서_나오고_UI_toolName도_같은_이름이다(tool, name, known):
    got = run(FILES, "out([hydWords.toolName(DATA), UI.toolName(DATA), hydWords.knownTool(DATA)])", tool)
    assert got == [name, name, known]


@pytest.mark.parametrize('key, unit', [('ts1_slope', '℃/설비 초'), ('vs1_slope', '(mm/s)/설비 초'), ('ts1', '℃')])
def test_감지기_기울기_단위는_설비_시간_1초당이다(key, unit):
    """G3b-25: 감지기 기울기는 설비 시간(TIME_SCALE 배속) 1초당인데 「℃/s」로 보였다."""
    assert run(FILES, "out(hydWords.unit(DATA))", key) == unit


def test_그래프에_있는_시스템_구동기_이름은_이름_사전_한_곳에서_오고_감지기는_sys_cep_와_같은_이름이다():
    """넘김 FW → FT: plainWords 의 시스템 표가 names.json(portal_names.PLAIN)과 같은 말을 따로 가져 「센서 경보 감지기」 · 「이상 감지기 (CEP)」 두 이름이 보였다.
    사전 값을 바꿔 실으면 화면 이름도 따라와야 한 곳이다(사본이면 옛 값이 남는다)."""
    import json
    from www_node import WWW
    names = {k: v + ' (사전)' for k, v in json.loads((WWW / 'names.json').read_text(encoding='utf-8')).items()}
    ids = sorted(k for k in names if k.startswith(('sys:', 'actr:')))
    got = run(FILES, "UI.names = DATA.names; out({ each: DATA.ids.map(i => [i, hydWords.system(i), UI.who(i)]), detector: hydWords.system('detector') })",
              {'names': names, 'ids': ids})
    assert ids and all(sys_name == who == names[i] for i, sys_name, who in got['each']), got['each']
    assert got['detector'] == names['sys:cep']
