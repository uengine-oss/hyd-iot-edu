"""지식 그래프 질의 템플릿(it/neo4j/templates/*.cypher)을 agent 가 부르는 그대로(agentsvc.tools.mcp_kg.KnowledgeGraph) 실제 Neo4j 에서 판정한다.

그래프 = kg-seed 결과(seeded_graph) + 이 파일이 넣는 작은 고장 지식(수업 문서 적재가 만드는 모양 그대로)과 실행 기록 · 학생 이름 공간 노드.
템플릿 폴더는 agent 이미지와 같은 자리 설정(KG_TEMPLATES)으로 저장소의 it/neo4j/templates 를 가리킨다.
"""
import importlib

import pytest
from conftest import ROOT

KNOWLEDGE = [
    # 공급사 · 견적: 업무 DB 정본을 처리 엔진 동기화(scm_sync)가 그래프로 옮긴 모양 그대로(시드에는 없다)
    "UNWIND [['sup:a','A정밀 (저가)',true,false],['sup:b','B-OEM (순정)',true,true],['sup:c','C트레이딩 (최저가)',false,false]] AS r "
    "CREATE (:Supplier {id:r[0], name:r[1], avl:r[2], oem:r[3]})",
    "UNWIND [['part:cooler-core','sup:a',180],['part:cooler-core','sup:b',260],['part:cooler-core','sup:c',120]] AS r "
    "MATCH (p:Part {id:r[0]}), (s:Supplier {id:r[1]}) CREATE (p)-[:SUPPLIED_BY {price:r[2], failRate:0.1, leadDays:3}]->(s)",
    # 고장 유형 · 원인 · 증거 (HM-8 적재가 만드는 꼴)
    "MATCH (c:Component {id:'comp:cooler'}), (s:Symptom {id:'sym:ts1-rise'}) "
    "CREATE (fm:FailureMode {id:'fm:t-cool', name:'시험 냉각 상실'})-[:OCCURS_IN]->(c), (s)-[:INDICATES]->(fm)",
    "MATCH (fm:FailureMode {id:'fm:t-cool'}) CREATE (:Cause {id:'cause:t-fouling', name:'시험 핀 오염', prior:0.6})-[:CAUSES]->(fm), "
    "(:Cause {id:'cause:t-ambient', name:'시험 외기 고온', prior:0.2})-[:CAUSES]->(fm)",
    "MATCH (c:Cause {id:'cause:t-fouling'}) CREATE (c)-[:EVIDENCED_BY]->(:Evidence {id:'evd:t-ce', name:'시험 냉각 효율 낮음', rule:'avg(CE) over 30s < 70', "
    "weight:0.6, expect:'lt', threshold:70, sql:'SELECT 1 AS value', tag:'CE', windowSeconds:30})",
    "CREATE (:KnowledgeSource {id:'ks:t-manual', name:'시험 매뉴얼', kind:'manual'})<-[:PART_OF]-(:ManualSection {id:'ms:t-1', ref:'T-1', title:'시험 절', excerpt:'팬을 올린다'})",
    # 스킬: 즉시 완화 · 원인 한정 근본 조치 둘 · 참고 보관 · 구매 · 예방 정비
    "MATCH (fm:FailureMode {id:'fm:t-cool'}), (ro:Role {id:'role:operator'}), (a:Action {id:'action:set-fan'}), (sys:System {id:'sys:scada'}), (ms:ManualSection {id:'ms:t-1'}) "
    "CREATE (fm)-[:MITIGATED_BY]->(k:Skill {id:'skill:t-mitigate', name:'시험 팬 최대', sopId:'SOP-T-1', kind:'control', description:'팬만 올린다'}), "
    "(k)-[:APPROVED_BY]->(ro), (k)-[:CONSISTS_OF {seq:1, value:100}]->(a), (sys)-[:HAS_SKILL]->(k), "
    "(k)-[:HAS_STEP]->(:Step {id:'SOP-T-1/1', order:1, text:'팬을 100 %로 올린다'})-[:REFERS_TO]->(ms)",
    "MATCH (fm:FailureMode {id:'fm:t-cool'}), (c:Cause {id:'cause:t-fouling'}) "
    "CREATE (fm)-[:REMEDIED_BY]->(k:Skill {id:'skill:t-clean', name:'시험 핀 세척', sopId:'SOP-T-2', kind:'work_order', description:'세척'})-[:ADDRESSES]->(c), "
    "(k)-[:HAS_STEP]->(:Step {id:'SOP-T-2/1', order:1, text:'세척한다'})",
    "MATCH (fm:FailureMode {id:'fm:t-cool'}), (c:Cause {id:'cause:t-ambient'}) "
    "CREATE (fm)-[:REMEDIED_BY]->(k:Skill {id:'skill:t-vent', name:'시험 환기', sopId:'SOP-T-3', kind:'work_order', description:'환기'})-[:ADDRESSES]->(c), "
    "(k)-[:HAS_STEP]->(:Step {id:'SOP-T-3/1', order:1, text:'환기한다'})",
    "MATCH (fm:FailureMode {id:'fm:t-cool'}) CREATE (fm)-[:REMEDIED_BY]->(:Skill {id:'skill:t-ref', name:'시험 참고', sopId:'SOP-T-4', kind:'reference', executable:false, description:'참고'})",
    "MATCH (fm:FailureMode {id:'fm:t-cool'}), (p:Part {id:'part:cooler-core'}) "
    "CREATE (fm)-[:MITIGATED_BY]->(k:Skill {id:'skill:t-buy', name:'시험 구매', sopId:'SOP-T-5', kind:'work_order', scope:'purchase', executable:true, description:'구매'})-[:INVOLVES_PART]->(p)",
    "MATCH (fm:FailureMode {id:'fm:t-cool'}) CREATE (fm)-[:PREVENTED_BY]->(:Skill {id:'skill:t-prevent', name:'시험 예방 정비', sopId:'SOP-T-6', kind:'work_order', description:'예방'})",
    "MATCH (k:Skill {id:'skill:t-mitigate'}), (v:StateVariable {id:'sv:fan-speed'}) CREATE (k)-[:AFFECTS {sign:1, delta:40, unit:'%'}]->(v)",
    # 판단 사례: 미리 넣은 예시(seeded) 하나와 승인 투영 하나 — 선례는 예시만 센다. 다른 설비(HYD-02)의 사건은 HYD-01 지도에 없다.
    "MATCH (a1:Asset {id:'asset:hyd-01'}), (a2:Asset {id:'asset:hyd-02'}), (c:Cause {id:'cause:t-fouling'}), (k:Skill {id:'skill:t-mitigate'}), (k2:Skill {id:'skill:t-clean'}) "
    "CREATE (i1:Incident {id:'inc:t-1', alertId:'ALT-T-1'})-[:ON_ASSET]->(a1), (i1)-[:DIAGNOSED_AS]->(c), "
    "(:DecisionCase {id:'case:t-seeded', seeded:true, reason:'예시 사유', followedRecommendation:true})-[:FOR_INCIDENT]->(i1), "
    "(:DecisionCase {id:'case:t-approved', reason:'승인 사유', followedRecommendation:false})-[:FOR_INCIDENT]->(i1), "
    "(i2:Incident {id:'inc:t-2', alertId:'ALT-T-2'})-[:ON_ASSET]->(a2), (i2)-[:DIAGNOSED_AS]->(c)",
    "MATCH (s:DecisionCase {id:'case:t-seeded'}), (p:DecisionCase {id:'case:t-approved'}), (k:Skill {id:'skill:t-mitigate'}), (k2:Skill {id:'skill:t-clean'}) "
    "CREATE (s)-[:CHOSE]->(k), (p)-[:CHOSE]->(k2)",
    # 실행 기록(처리 엔진 투영) · 내부 기록 — 지식 지도에 보이지 않아야 한다
    "MATCH (a:Asset {id:'asset:hyd-01'}), (r:Role {id:'role:operator'}) "
    "CREATE (pv:ProcessVersion {id:'proc-version:hyd:t:1'})-[:HAS_NODE]->(t:FlowNode:Task {id:'flow:hyd:t:1:task', name:'투영 작업', taskType:'user'}), "
    "(pi:ProcessInstance {id:'pi:t-1'})-[:USES_VERSION]->(pv), (pi)-[:ON_ASSET]->(a), (w:WorkItem {id:'wi:t-1'})-[:IN_INSTANCE]->(pi), (w)-[:EXECUTES]->(t), "
    "(w)-[:ASSIGNED_TO]->(u:ExecutionActor:User {id:'execution-actor:hyd:user%3At', name:'시험 사용자'}), (pi)-[:ROLE_BOUND]->(r), "
    "(:KnowledgeEdit {id:'edit:t-1'}), (:ManualIngestionDocument {id:'doc:t-1'})",
    # 학생 이름 공간(업무 스키마 실습): 학생 노드 하나가 기준 노드(쿨러)에 다리를 놓는다
    "MATCH (c:Component {id:'comp:cooler'}) CREATE (:Meeting {id:'s01:meeting', ns:'s01', name:'학생 회의'})-[:ABOUT]->(c)",
]
HIDDEN = {'FlowNode', 'ProcessVersion', 'ProcessInstance', 'WorkItem', 'ExecutionActor', 'User', 'Agent', 'IngestionControl', 'IngestionBatch',
          'ExecutionProjection', 'CaseProjection', 'KnowledgeEdit', 'ManualIngestionDocument', 'ManualIngestionBatch', 'Task'}


@pytest.fixture
def kg(seeded_graph, monkeypatch):
    for statement in KNOWLEDGE:
        seeded_graph.query(statement)
    monkeypatch.setenv('KG_TEMPLATES', str(ROOT / 'it' / 'neo4j' / 'templates'))      # agent 이미지의 ENV KG_TEMPLATES 자리
    from agentsvc.tools import mcp_kg
    graph = importlib.reload(mcp_kg).KnowledgeGraph()
    yield graph
    graph.driver.close()


def test_원인_후보는_패턴의_증상이_가리키는_고장_유형의_원인을_사전_확률_순으로_증거와_함께_낸다(kg):
    rows = kg.t1_causes('COOLER_DEGRADATION')
    assert [(r['causeId'], r['prior'], r['failureModeId'], r['component']) for r in rows] == [
        ('cause:t-fouling', 0.6, 'fm:t-cool', '오일 쿨러'), ('cause:t-ambient', 0.2, 'fm:t-cool', '오일 쿨러')]
    assert rows[0]['symptoms'] == ['유온 상승']        # 쿨러 패턴은 냉각 효율 저하도 감지하지만 이 고장 유형을 가리키는 증상은 유온 상승뿐
    assert [(e['id'], e['expect'], e['threshold'], e['tag'], e['windowSeconds']) for e in rows[0]['evidence']] == [('evd:t-ce', 'lt', 70, 'CE', 30)]
    assert rows[1]['evidence'] == []


@pytest.mark.parametrize('pattern', ['FAN_VIBRATION', 'PM_DUE', 'NO_SUCH_PATTERN'], ids=['증상은 있고 고장 지식 없음', '업무 감시 패턴', '없는 패턴'])
def test_고장_지식이_없거나_없는_패턴이면_원인_후보가_비어_있다(kg, pattern):
    assert kg.t1_causes(pattern) == []


@pytest.mark.parametrize('cause, skills', [
    ('cause:t-fouling', [('skill:t-mitigate', 'MITIGATED_BY'), ('skill:t-clean', 'REMEDIED_BY')]),
    ('cause:t-ambient', [('skill:t-mitigate', 'MITIGATED_BY'), ('skill:t-vent', 'REMEDIED_BY')]),
    ('cause:no-such', []),
], ids=['핀 오염 → 완화 + 세척', '외기 고온 → 완화 + 환기', '없는 원인'])
def test_원인의_조치_후보는_원인_한정_스킬을_거르고_참고_구매_예방_절차를_빼고_낸다(kg, cause, skills):
    rows = kg.t2_skills(cause)
    assert sorted((r['skillId'], r['relation']) for r in rows) == sorted(skills)


def test_조치_후보는_원자_조치_값과_단계의_매뉴얼_절을_함께_낸다(kg):
    row = next(r for r in kg.t2_skills('cause:t-fouling') if r['skillId'] == 'skill:t-mitigate')
    assert (row['approver']['id'], row['failureModeId']) == ('role:operator', 'fm:t-cool')
    assert [(a['code'], a['value'], a['target']) for a in row['actions']] == [('FAN_SET', 100, 'actr:fan-drive')]
    assert [(s['order'], s['manual']['ref']) for s in row['steps']] == [(1, 'T-1')]


def test_스킬_상세는_참고_보관_절차를_빼고_구매_절차는_업무_범위와_함께_낸다(kg):
    rows = {r['skillId']: r for r in kg.skills(['skill:t-mitigate', 'skill:t-ref', 'skill:t-buy', 'skill:no-such'])}
    assert sorted(rows) == ['skill:t-buy', 'skill:t-mitigate']
    assert (rows['skill:t-buy']['scope'], rows['skill:t-buy']['parts']) == ('purchase', ['part:cooler-core'])
    assert {s['supplier']: s['oem'] for s in rows['skill:t-buy']['partSuppliers']} == {'sup:a': False, 'sup:b': True, 'sup:c': False}
    assert rows['skill:t-mitigate']['performers'] == ['sys:scada']


def test_판단_규칙은_결정표마다_검사_출력_근거와_순위_정책을_낸다(kg):
    rules = {r['rule']: r for r in kg.dmn()}
    assert {r['decision']: r['hitPolicy'] for r in rules.values()} == {'dec:compliance': 'COLLECT', 'dec:rank-actions': 'UNIQUE'}
    hard = rules['rule:ts1-hard']
    assert (hard['effect'], hard['when'], hard['tests'], hard['sources']) == (
        'EXCLUDE', 'forecast_ts1 >= 65', [{'input': 'in:forecast-ts1', 'variable': 'forecast_ts1', 'operator': '>=', 'value': 65, 'unit': '℃'}], ['SR-04'])
    assert rules['rule:rank-value']['rankingPolicy'] and rules['rule:rank-value']['tests'] == []


def test_판단_입력은_모두_출처와_함께_나온다(kg):
    rows = kg.inputs()
    assert rows and [r['id'] for r in rows if r['source'] is None] == []
    oil = next(r for r in rows if r['id'] == 'in:oil-analysis')
    assert (oil['variable'], oil['typeRef'], oil['source'], oil['sourceKind']) == ('oil_analysis_out_of_spec', 'boolean', 'sys:cmms', 'System')


def test_성과_지표_득실은_경로마다_부호와_강도의_곱으로_처음_닿는_성과_지표에서_멈춘다(kg):
    paths = {(r['measure'], tuple(r['nodes'])): r for r in kg.tradeoffs(['skill:t-mitigate'])}
    energy = paths[('msr:energy-use', ('skill:t-mitigate', 'sv:fan-speed', 'msr:energy-use'))]
    assert (energy['dir'], energy['weight'], energy['good'], energy['conditional']) == (1, 0.3, False, False)
    margin = paths[('msr:safety-margin', ('skill:t-mitigate', 'sv:fan-speed', 'sv:ts1', 'msr:safety-margin'))]
    assert (margin['dir'], margin['weight'], margin['good']) == (1, 1.0, True)
    oil = paths[('msr:oil-life', ('skill:t-mitigate', 'sv:fan-speed', 'sv:ts1', 'msr:oil-life'))]
    assert (oil['conditional'], oil['conds']) == (True, ['유온 60 ℃ 이상에서 크게'])
    assert all(n.startswith(('skill:', 'sv:')) for r in paths.values() for n in r['nodes'][:-1])


def test_모르는_강도가_있는_경로는_무게를_정하지_않는다(kg, seeded_graph):
    seeded_graph.query("MATCH (:StateVariable {id:'sv:fan-speed'})-[i:INFLUENCES]->(:Measure {id:'msr:energy-use'}) SET i.strength = 'unknown'")
    energy = [r for r in kg.tradeoffs(['skill:t-mitigate']) if r['measure'] == 'msr:energy-use']
    assert [r['weight'] for r in energy] == [None]


def test_예측_모델은_설비마다_명시한_하나이고_없는_설비면_실패한다(kg):
    from hydcommon import forecast        # 그래프의 바인딩은 예측 엔진의 모델 · 판과 같아야 한다(agent forecasting 이 다르면 예측을 거절)
    assert kg.forecast_model('HYD-01') == {'asset_id': 'asset:hyd-01', 'asset': 'HYD-01', 'model_id': forecast.MODEL_ID,
                                           'model_revision': forecast.MODEL_REVISION, 'scope': forecast.MODEL_SCOPE,      # 그래프 시드(instances.cypher forecastScope)가 정본 상수와 같아야 한다
                                           'horizon_s': 900}
    with pytest.raises(ValueError):
        kg.forecast_model('HYD-09')


def test_선례는_미리_넣은_예시_사례만_세고_승인으로_쌓인_사례는_세지_않는다(kg):
    assert kg.precedents('fm:t-cool') == [{'skill': 'skill:t-mitigate', 'n': 1, 'reasons': ['예시 사유']}]
    assert kg.precedents('fm:no-such') == []


def test_역할은_직급_순으로_부서와_함께_나온다(kg):
    rows = kg.roles()
    assert [r['level'] for r in rows] == sorted(r['level'] for r in rows)
    assert {'id': 'role:purchasing', 'name': '구매 담당', 'level': 1, 'deptName': '구매팀'} in rows


def test_관점은_재무부터_차례로_그_관점의_성과_지표와_함께_나온다(kg):
    rows = kg.perspectives()
    assert [r['id'] for r in rows] == ['persp:financial', 'persp:customer', 'persp:internal', 'persp:learning']
    assert 'msr:op-profit' in rows[0]['measures'] and 'msr:precedent' in rows[3]['measures']


def test_공급사는_승인_여부와_함께_나온다(kg):
    assert {k: v['avl'] for k, v in kg.suppliers().items()} == {'sup:a': True, 'sup:b': True, 'sup:c': False}


@pytest.mark.parametrize('part_no, part', [('P-PMP-SEAL', 'part:pump-seal'), ('P-RTN-FLT', 'part:return-filter'), ('P-NONE', None)],
                         ids=['씰 키트', '리턴 필터', '없는 부품 번호'])
def test_부품_번호로_부품_하나를_찾고_없으면_실패한다(kg, part_no, part):
    if part is None:
        with pytest.raises(ValueError):
            kg.purchase_part(part_no)
    else:
        assert kg.purchase_part(part_no)['id'] == part


def test_패턴_목록은_원인까지_이어진_고장_유형_이름을_함께_낸다(kg):
    rows = {r['code']: r['failureModes'] for r in kg.patterns()}
    assert (rows['COOLER_DEGRADATION'], rows['OVERHEAT_TRIP'], rows['FAN_VIBRATION'], rows['PM_DUE']) == (['시험 냉각 상실'], ['시험 냉각 상실'], [], [])


def test_지식_지도는_고른_설비의_지식만_보이고_실행_내부_기록과_다른_설비의_사건을_숨긴다(kg):
    graph = kg.graph('HYD-01')
    nodes = {n['id']: n for n in graph['nodes']}
    assert 'asset:hyd-01' in nodes and 'asset:hyd-02' not in nodes and 'inc:t-1' in nodes and 'inc:t-2' not in nodes
    assert 'case:t-seeded' in nodes and 's01:meeting' not in nodes
    assert [n['id'] for n in graph['nodes'] if n['label'] in HIDDEN] == []
    assert {'flow:hyd:t:1:task', 'pi:t-1', 'wi:t-1', 'execution-actor:hyd:user%3At', 'edit:t-1', 'doc:t-1'}.isdisjoint(nodes)
    assert [e for e in graph['edges'] if e['from'] not in nodes or e['to'] not in nodes] == []
    assert {'from': 'sym:ts1-rise', 'to': 'fm:t-cool', 'type': 'INDICATES'} in graph['edges']


def test_학생_이름_공간_지도는_학생_노드와_다리_놓인_기준_노드만_낸다(kg):
    graph = kg.graph('HYD-01', 's01')
    assert sorted(n['id'] for n in graph['nodes']) == ['comp:cooler', 's01:meeting']
    assert graph['edges'] == [{'from': 's01:meeting', 'to': 'comp:cooler', 'type': 'ABOUT'}]
    assert kg.namespaces() == [{'ns': 's01', 'nodes': 1}]
