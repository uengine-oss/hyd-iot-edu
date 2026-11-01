"""판단 엔진 도구 본체(it/dmn-mcp/dmn_mcp/tools.py) — 봉투 · 등록 판정 · 카드 비교 칸 · 근거 조각 읽기, 그리고 kg-seed 그래프(seeded_graph)에
대어 보는 업무 원인 · 지식 확인. 엔진(agentsvc)과 그래프는 실제, 바깥(시계열 · 업무 시스템)은 부르지 않는 경로만 고른다.
"""
import importlib

import psycopg
import pytest

from conftest import _compose_default, _compose_service, _dockerfile, _image_env, here


@pytest.fixture(scope='module')
def dmn():
    """dmn-mcp 컨테이너가 받는 환경(compose dmn-mcp environment, 주소만 이 PC)으로 도구 모듈을 가져온다 — 감지기와 같은 수집 계약
    (DAQ_PROFILE) 등을 가져올 때 읽는다."""
    copies, image_env, _ = _dockerfile('dmn-mcp')
    env = dict(_image_env(copies, image_env))          # 이미지 ENV(KG_TEMPLATES 등 — 저장소 자리로)
    env.update({k: here(_compose_default(v)) for k, v in _compose_service('dmn-mcp')['environment'].items() if not k.startswith('NEO4J_')})
    with pytest.MonkeyPatch.context() as mp:
        for k, v in env.items():
            mp.setenv(k, v)
        # 판단 엔진은 지식 질의 자리(KG_TEMPLATES)를 부를 때 읽으므로 이 모듈의 테스트가 도는 동안 환경을 그대로 둔다
        yield importlib.import_module('dmn_mcp.tools')


def raises(error):
    def fn():
        raise error
    return fn


@pytest.mark.parametrize('error, kind', [
    (ValueError('인자 틀림'), 'INVALID'),
    (('UNKNOWN', 'process 거절'), 'UNKNOWN'),          # NotRegistered(종류, 까닭) — 종류 그대로
    (('INVALID', '후보 0개'), 'INVALID'),
    (KeyError('options'), 'UNKNOWN'),                     # G2-18: 엔진 · 그래프 결함 — 옛 판은 INVALID 라 에이전트가 자기 인자 탓으로 알았다
    (TypeError('NoneType'), 'UNKNOWN'),
    (psycopg.errors.UndefinedColumn('column x does not exist'), 'INVALID'),   # 생성한 SQL 은 메타데이터로 고칠 수 있다(42xxx)
    (psycopg.OperationalError('connection refused'), 'UNKNOWN'),
    (RuntimeError('graph down'), 'UNKNOWN'),
], ids=['값_오류', '미등록_UNKNOWN', '미등록_INVALID', 'KeyError', 'TypeError', 'SQL_42', 'DB_연결', '그_밖'])
def test_도구는_어떤_실패든_같은_봉투로_답하고_종류를_가른다(dmn, error, kind):
    error = dmn.NotRegistered(*error) if isinstance(error, tuple) else error
    out = dmn.enveloped(raises(error))()
    assert out['result'] == 'error' and out['error_kind'] == kind and out['message']


def test_도구가_성공하면_ok_봉투다(dmn):
    assert dmn.enveloped(lambda: {'x': 1})() == {'result': 'ok', 'document': {'x': 1}}


@pytest.mark.parametrize('rec, kind, phrase', [
    ({'status': 'FAILED', 'error_code': 'SUBMIT_REFUSED', 'submit_status': 409, 'error': '처리 범위가 다릅니다'}, 'INVALID', '처리 범위가 다릅니다'),
    ({'status': 'FAILED', 'error_code': 'SUBMIT_REFUSED', 'submit_status': 503, 'error': '잠시 뒤'}, 'UNKNOWN', '잠시 뒤'),
    ({'status': 'FAILED', 'error_code': 'SUBMIT_FAILED', 'error': 'timeout'}, 'UNKNOWN', 'process 에 연결하거나'),
    ({'status': 'REJECTED_BY_GUARDRAIL', 'steps': [{'name': 'guardrail', 'output': {'violations': ['V1']}}]}, 'UNKNOWN', 'V1'),
    ({'status': 'EVALUATED', 'result': {'options': []}, 'explanation': '규칙 불일치'}, 'INVALID', '후보가 0개'),
], ids=['process_거절_4xx', 'process_거절_5xx', '연결_실패', '가드레일', '후보_0개'])
def test_쓰기_도구는_process가_저장한_판단만_성공으로_돌려준다(dmn, rec, kind, phrase):
    with pytest.raises(dmn.NotRegistered) as err:
        dmn.registered(rec, '조치 카드 판단')
    assert err.value.kind == kind and phrase in str(err.value)


def test_process가_저장한_판단은_그대로_돌려준다(dmn):
    rec = {'status': 'SUBMITTED', 'id': 'DEC-1'}
    assert dmn.registered(rec, '판단') is rec


@pytest.mark.parametrize('rec, outcome', [
    ({'status': 'EVALUATED', 'id': 'EVAL-1', 'result': {'options': [{'id': 'o1'}]}, 'recommended': 'o1'}, 'ranked'),
    ({'status': 'EVALUATED', 'id': 'EVAL-1', 'result': {'options': [{'id': 'o1'}]}, 'recommended': None}, 'no_feasible_option'),
    ({'status': 'EVALUATED', 'id': 'EVAL-1', 'result': {'options': []}}, 'no_candidates'),
    ({'status': 'REJECTED_BY_GUARDRAIL', 'id': 'EVAL-1', 'result': {'options': [{'id': 'o1'}]}}, 'guardrail_rejected'),
], ids=['순위', '전부_제외', '후보_없음', '가드레일'])
def test_읽기_평가는_결과_종류를_밝히고_저장되지_않은_id임을_알린다(dmn, rec, outcome):
    out = dmn.read_outcome(rec, '평가')
    assert out['outcome'] == outcome and 'EVAL-1' in out['notice'] and 'decision_id 로 쓰지 않습니다' in out['notice']


def test_카드_비교_칸은_큰_근거를_빼고_뺀_것과_받는_법을_알린다(dmn):
    option = {'rank': 1, 'id': 'o1', 'sopId': 'SOP-1', 'name': '세척', 'feasible': True, 'score': 0.9,
              'rankingEvidence': ['x' * 9000], 'steps': [{'n': 1}], 'approver': {'name': '설비보전팀장'}}
    rec = {'id': 'EVAL-1', 'status': 'EVALUATED', 'result': {'options': [option]}, 'facts': {'a': 1, 'pm_context': {'big': 1}},
           'provenance': [{'variable': 'a', 'source': 'sys:mes', 'error': '닿지 않음', 'how': 'GET'}]}
    view = dmn.agent_view(rec)
    card = view['options'][0]
    assert 'rankingEvidence' not in card and 'steps' not in card and card['approver'] == '설비보전팀장'
    assert view['facts'] == {'a': 1} and view['facts_omitted'] == ['pm_context'] and view['source_errors'][0]['error'] == '닿지 않음'
    detail = dmn.agent_view(rec, 'SOP-1')['options'][0]['detail']
    assert detail['rankingEvidence'].endswith('…[truncated]') and len(detail['rankingEvidence']) <= dmn.DETAIL_FIELD_MAX_CHARS + 20


@pytest.fixture
def tools(dmn, seeded_graph):
    return dmn.DmnTools(kg=importlib.import_module('agentsvc.tools.mcp_kg').KnowledgeGraph())


@pytest.mark.parametrize('ref, field, offset, phrase', [
    ('없는참조', 'facts', 0, '없거나 만료'), ('없는참조', 'secret', 0, '조회 가능한 근거 칸'), ('없는참조', 'facts', -1, '0 이상의 정수'),
], ids=['없는_참조', '없는_칸', '음수_offset'])
def test_평가_근거_조각_읽기는_잘못된_참조_칸_자리를_거절한다(dmn, tools, ref, field, offset, phrase):
    with pytest.raises(ValueError, match=phrase):
        tools.read_evaluation_evidence(ref, None, field, offset)


def test_정기_정비_도래의_원인은_정비가_막는_고장의_원인이다(dmn, course_graph):
    """PREVENTED_BY 는 시작이 넣는 수업 지식(정기 정비 원문)에서 온다 — 학생 PC 의 시작 뒤 그래프(course_graph)로 본다."""
    tools = dmn.DmnTools(kg=importlib.import_module('agentsvc.tools.mcp_kg').KnowledgeGraph())
    seeded_graph = course_graph
    out = tools.business_causes('HYD-02', 'PM_DUE')
    expected = seeded_graph.query('MATCH (fm:FailureMode)-[:PREVENTED_BY]->(:Skill) WITH DISTINCT fm MATCH (c:Cause)-[:CAUSES]->(fm) '
                                  'RETURN c.id AS causeId ORDER BY c.prior DESC')
    assert expected, '시작 뒤 그래프에 정비가 막는 고장(PREVENTED_BY)이 없다'
    assert [c['causeId'] for c in out['causes']] == [r['causeId'] for r in expected] and out['top_cause'] == expected[0]['causeId']


@pytest.mark.parametrize('call', ['business_causes', 'evaluate_cards'])
def test_재고_기준_이탈은_원인_경로가_아니라_구매_도구로_보낸다(dmn, tools, call):
    """G2-26: 옛 원인 경로는 경보의 부품이 아니라 모자란 모든 부품에서 사전 확률 1순위를 골랐다 — 구매는 부품이 근거다."""
    args = ('HYD-02', 'SPARE_BELOW_MIN') if call == 'business_causes' else ('HYD-02', 'SPARE_BELOW_MIN', 'cause:x', 'fm:x')
    with pytest.raises(ValueError, match='purchase_context'):
        getattr(tools, call)(*args)


@pytest.mark.parametrize('call, args, phrase', [
    ('business_causes', ('HYD-01', 'COOLER_DEGRADATION'), '업무 경보가 아닙니다'),
    ('dmn_rules', ('dec:없는-판단',), '등록되지 않은 Decision id'),
    ('precedents', ('fm:없는-고장',), '등록되지 않은 FailureMode id'),
    ('tradeoffs', (['skill:없는-스킬'],), '등록되지 않은 Skill id'),
    ('evaluate_cards', ('HYD-02', 'PM_DUE', 'cause:없는-원인', 'fm:x'), '업무 근거'),
], ids=['센서_경보', '없는_판단', '없는_고장', '없는_스킬', '근거_없는_원인'])
def test_지식에_없는_id는_빈_결과가_아니라_까닭과_함께_거절한다(dmn, tools, call, args, phrase):
    with pytest.raises(ValueError, match=phrase):
        getattr(tools, call)(*args)


@pytest.mark.parametrize('incident', ['', '  ', None], ids=['빈_값', '공백', '없음'])
def test_처리_건_incident_없이는_판단도_구매도_제출하지_않는다(dmn, tools, incident):
    with pytest.raises(ValueError, match='incident'):
        tools.submit_decision('HYD-01', 'COOLER_DEGRADATION', 'cause:x', 'fm:x', incident)
    with pytest.raises(ValueError, match='incident'):
        tools.submit_purchase('HYD-02', 'P-PMP-SEAL', incident)


def test_가정_사실로는_판단을_제출하지_않는다(dmn, tools):
    with pytest.raises(ValueError, match='가정 facts'):
        tools.submit_decision('HYD-01', 'COOLER_DEGRADATION', 'cause:x', 'fm:x', 'INC-1', overrides={'plc_mode': 'LOCAL'})


@pytest.mark.parametrize('reachable', [True, False], ids=['그래프_있음', '그래프_없음'])
def test_건강은_지금_그래프에_닿는지다(dmn, seeded_graph, monkeypatch, reachable):
    if not reachable:
        monkeypatch.setenv('NEO4J_URI', 'bolt://127.0.0.1:9')      # 바깥(그래프)이 꺼진 자리
    assert dmn.DmnTools(kg=importlib.import_module('agentsvc.tools.mcp_kg').KnowledgeGraph()).health() == {'neo4j': reachable}

