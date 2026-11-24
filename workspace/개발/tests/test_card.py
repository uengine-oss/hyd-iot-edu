"""가이드 카드(it/agent/agentsvc/card.py) — 원인 순위 · 근거 판정 · 조치 방법 목록. 무엇을 할지는 판단 카드(cards.evaluate)가 SOP 하나씩 고른다."""
import pytest

from agentsvc import card

T1 = [{'causeId': 'cause:cooler-fin-fouling', 'cause': '쿨러 핀 오염', 'prior': 0.6, 'failureModeId': 'fm:cooler-cooling-loss',
       'failureMode': '쿨러 냉각 성능 상실', 'evidence': [{'id': 'evd:ce-low', 'name': '냉각 효율 저하', 'weight': 1, 'expect': 'lt', 'threshold': 70}]},
      {'causeId': 'cause:fan-drive-fault', 'cause': '팬 구동 불량', 'prior': 0.2, 'failureModeId': 'fm:cooler-cooling-loss',
       'failureMode': '쿨러 냉각 성능 상실', 'evidence': [{'id': 'evd:vs1-high', 'name': '팬 진동 상승', 'weight': 1, 'expect': 'gte', 'threshold': 0.9}]}]
PASS = {'evd:ce-low': {'value': 46.2, 'passed': True}, 'evd:vs1-high': {'value': 0.57, 'passed': False}}
SKILLS = [{'skillId': 'skill:sop-cool-14', 'sopId': 'SOP-COOL-14', 'name': '쿨러 핀 세척', 'relation': 'REMEDIED_BY', 'kind': 'work_order',
           'actions': [{'id': 'action:work-order', 'code': 'WO_CREATE', 'name': '정비 작업지시 발행', 'kind': 'transaction', 'value': 'SOP-COOL-14', 'seq': 1}],
           'steps': [{'id': 's14-1', 'order': 1, 'text': '설비를 정지하고 LOTO'}]},
          {'skillId': 'skill:sop-cool-11', 'sopId': 'SOP-COOL-11', 'name': '팬 최대 운전', 'relation': 'MITIGATED_BY', 'kind': 'control',
           'actions': [{'id': 'action:set-fan', 'code': 'FAN_SET', 'name': '팬 속도 설정', 'kind': 'command', 'param': 'fan_pct', 'value': 100, 'seq': 1}],
           'steps': [{'id': 's11-1', 'order': 1, 'text': 'REMOTE_AUTO 확인'}]},
          {'skillId': 'skill:sop-cool-12', 'sopId': 'SOP-COOL-12', 'name': '팬 최대 운전과 부하 80 %', 'relation': 'MITIGATED_BY', 'kind': 'control',
           'actions': [{'id': 'action:set-fan', 'code': 'FAN_SET', 'name': '팬 속도 설정', 'kind': 'command', 'param': 'fan_pct', 'value': 100, 'seq': 1},
                       {'id': 'action:set-load', 'code': 'LOAD_SET', 'name': '펌프 부하 설정', 'kind': 'command', 'param': 'load_pct', 'value': 80, 'seq': 2}]}]


def test_원인은_사전확률_곱하기_통과_근거로_매기고_근거가_있는_원인이_위다():
    causes = card.rank_causes(T1, PASS)
    assert [(c['id'], c['score']) for c in causes] == [('cause:cooler-fin-fouling', 0.6), ('cause:fan-drive-fault', 0.0)]
    assert card.evidence_status(causes)['status'] == 'SUPPORTED'


def test_근거_항목은_읽은_시계열_태그를_실어_화면이_관측값의_단위를_붙인다():
    """한바퀴 11-009: 사건 상세의 「냉각 효율 저하 — 조건 충족 · 관측 46.20」에 단위가 없었다 — 근거 항목에 태그가 없어 화면이 알 수 없었다."""
    rows = [dict(T1[0], evidence=[dict(T1[0]['evidence'][0], tag='CE', windowSeconds=30)]), T1[1]]
    by_id = {e['id']: e for c in card.rank_causes(rows, PASS) for e in c['evidence']}
    assert by_id['evd:ce-low']['tag'] == 'CE' and by_id['evd:vs1-high']['tag'] is None   # 구간 조건이 아닌 근거는 태그 없음


@pytest.mark.parametrize('results, status', [({}, 'UNKNOWN'), ({'evd:ce-low': {'value': 80, 'passed': False}, 'evd:vs1-high': {'value': 0.5, 'passed': False}},
                                                                'UNSUPPORTED')], ids=['근거 조회 없음', '근거가 모두 맞지 않음'])
def test_근거를_모르거나_뒷받침이_없으면_조치를_보류한다(results, status):
    assessment = card.evidence_status(card.rank_causes(T1, results))
    assert assessment['status'] == status and assessment['withheld'] and assessment['reason']


@pytest.mark.parametrize('rows, said', [
    ([], '원인 지식이 지식 지도에 없어'),
    ([dict(r, evidence=[]) for r in T1], '원인 후보 2개에 설비 값으로 확인할 근거가 지식에 없어'),
    (T1, '현재 관측 근거로 뒷받침되는 원인이 없어'),
], ids=['원인 지식 없음(문서를 넣기 전 · 비운 뒤)', '원인은 있는데 근거 규칙 없음', '근거를 봤는데 모두 맞지 않음'])
def test_보류의_까닭은_무엇이_없었는지를_말하고_지식이_없는_것을_설비가_정상인_것처럼_말하지_않는다(rows, said):
    """빈 지식(매뉴얼을 넣기 전 · 비운 뒤)에서도 「현재 관측 근거로 뒷받침되는 원인이 없어」라고 해, 학생은 센서를 봤더니 아니었다고 읽었다."""
    results = {'evd:ce-low': {'value': 80, 'passed': False}, 'evd:vs1-high': {'value': 0.5, 'passed': False}}
    assessment = card.evidence_status(card.rank_causes(rows, results))
    assert assessment['status'] == 'UNSUPPORTED' and assessment['withheld'] and said in assessment['reason']
    assert ('지식 › 문서 등록' in assessment['reason']) == (rows is not T1)


def test_가이드_카드는_SOP마다_조치를_따로_싣고_섞은_권장_조치_목록을_만들지_않는다():
    """G1-04: 팬 100(SOP-COOL-11) + 부하 80(SOP-COOL-12) + 작업지시(SOP-COOL-13)를 한 목록으로 섞어 「권장 즉시 조치」라 불렀다 — 어느 절차에도 없다."""
    causes = card.rank_causes(T1, PASS)
    c = card.build_card(None, {'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION'}, causes,      # 진단하는 곳이 넘기는 경보의 꼴(설비 · 패턴)
                        {'cause:cooler-fin-fouling': SKILLS}, {'ok': True})
    assert 'recommended' not in c
    assert [(k['sopId'], k['actions']) for k in c['skills']] == [('SOP-COOL-11', ['팬 속도 설정 100 %']),
                                                                 ('SOP-COOL-12', ['팬 속도 설정 100 %', '펌프 부하 설정 80 %']),
                                                                 ('SOP-COOL-14', ['정비 작업지시 발행 SOP-COOL-14'])]
    assert '권장 즉시 조치' not in c['summary'] and 'fan_pct=' not in c['summary'] and '를 발행' not in c['summary']
    assert c['summary'].startswith("HYD-01에서 「쿨러 냉각 성능 상실」 경보가 발생했습니다. 가장 유력한 원인은 '")
    assert '조치 판단(규정 · 예측 · 순위)이 절차마다 비교합니다' in c['summary']
    assert {'skill:sop-cool-14', 'SOP-COOL-14', 'action:work-order', 's14-1', 'evd:ce-low'} <= set(c['citations'])


def test_보류한_카드에는_조치_방법이_없고_까닭이_요약이다():
    c = card.build_card(None, {'asset': 'HYD-01'}, card.rank_causes(T1, {}), {'cause:cooler-fin-fouling': SKILLS}, {'ok': True})
    assert c['withheld'] and c['skills'] == [] and c['summary'] == c['evidence_status']['reason']


def test_사람이_입력한_분석은_센서_근거가_없는_원인의_근거가_된다():
    rows = [{'causeId': 'cause:oil', 'cause': '작동유 열화', 'prior': 0.7, 'evidence': []}]
    alert = {'source': 'human_input', 'alertId': 'H-1', 'evidence': {'out_of_spec': True, 'item': 'TAN', 'value': 2.1}, 'enteredBy': {'name': '박정비'}}
    rows, results = card.with_human_evidence(rows, alert)
    assert rows[0]['evidence'][0]['id'] == 'human:H-1' and results['human:H-1']['passed'] is True
    assert card.with_human_evidence(rows, {'source': 'detector'}) == (rows, {})


def gap(ready, window=120.0, reason='OBSERVATION_GAP'):
    """mcp_tsdb.evaluate 가 덮이지 않은 창에 내는 결과 모양(값은 남기되 판정하지 않음)."""
    return {'value': 0.57, 'passed': None, 'status': 'UNKNOWN', 'reason': reason,
            'coverage': {'samples': 96, 'max_gap_s': 24.55, 'limit_s': 3.0, 'covered': False, 'ready_in_s': ready, 'tag': 'VS1', 'window_s': window}}


@pytest.mark.parametrize('results, said', [
    ({'evd:ce-low': {'value': 46.2, 'passed': True, 'status': 'PASS'}, 'evd:vs1-high': gap(24.55)}, '최근 120초 기록이 아직 다 차지 않았습니다'),
    ({'evd:ce-low': gap(3.2, window=30.0), 'evd:vs1-high': gap(24.55)}, '약 25초 뒤 다시 평가하세요'),
    ({'evd:ce-low': {'value': 46.2, 'passed': True, 'status': 'PASS'}, 'evd:vs1-high': gap(None)}, None),     # 지금 값이 오지 않음
    ({'evd:ce-low': {'value': None, 'passed': None, 'status': 'UNKNOWN', 'reason': 'NO_DATA'}, 'evd:vs1-high': gap(24.55)}, None),
], ids=['기록이_덜_참', '가장_긴_기다림', '지금_끊김은_말하지_않음', '다른_까닭이_섞임'])
def test_모르는_근거가_모두_곧_찰_기록이면_보류_까닭이_기다릴_시간을_말한다(results, said):
    """막 켠 스택의 「관측 공백」 보류가 센서 고장으로 읽히지 않게(2026-11-17 실제 AI). 근거 판정 문장은 진단 도구가 AI 에게, 판단 실험이
    화면에 그대로 준다. 다른 까닭이 섞이거나 지금 값이 오지 않으면 기다리라고 하지 않는다."""
    assessment = card.evidence_status(card.rank_causes(T1, results))
    assert assessment['status'] == 'UNKNOWN' and assessment['reason'].startswith('근거 조회가 불완전하여')
    assert (said in assessment['reason']) if said else ('다시 평가하세요' not in assessment['reason'])


# ---------------------------------------------------------------- 문서의 진단 규칙(dec:diagnose-cause)
#: HM-8.4 가 정한 진단 규칙과 같은 꼴(제공 문서 서명 묶음의 rule:hm-8-4-fouling-diagnosis): 쿨러 성능 저하에서 냉각 효율 70 % 미만이면 핀 오염 1순위
FOULING_RULE = {'decision': card.DIAGNOSIS, 'rule': 'rule:fouling-dx', 'annotation': '냉각 효율이 70 % 미만이면 핀 오염을 1순위 원인으로 둔다.',
                'tests': [{'input': 'in:pattern', 'variable': 'pattern', 'name': '경보 패턴', 'operator': '==', 'value': 'COOLER_DEGRADATION'},
                          {'input': 'in:ce', 'variable': 'ce', 'name': '냉각 효율', 'operator': '<', 'value': 70}],
                'outputs': ['cause:cooler-fin-fouling']}
#: 사전 확률 · 근거로는 팬 구동 불량이 1순위인 관측(팬 진동 높음, 냉각 효율 근거 미달)
FAN_EVIDENCE = {'evd:ce-low': {'value': 75.0, 'passed': False}, 'evd:vs1-high': {'value': 1.2, 'passed': True}}


@pytest.mark.parametrize('rules, ce, top, status', [
    ([], 60.0, 'cause:fan-drive-fault', 'SUPPORTED'),                 # 진단 규칙이 없는 지식: 사전 확률 × 근거 그대로
    ([FOULING_RULE], 60.0, 'cause:cooler-fin-fouling', 'SUPPORTED'),  # 규칙이 발화하면 그 원인이 근거 순위보다 앞선다
    ([FOULING_RULE], 84.0, None, 'UNSUPPORTED'),                     # 규칙이 있는데 맞지 않으면 원인을 정하지 않는다(정상 냉각 효율)
    ([FOULING_RULE], None, None, 'UNKNOWN'),                         # 규칙이 보는 값을 모르면 근거 미확인
], ids=['규칙 없음', '규칙 발화', '규칙 맞지 않음', '규칙 값 모름'])
def test_문서의_진단_규칙이_원인을_고른다(rules, ce, top, status):
    """탐사 C1: 문서가 정한 진단 규칙(「…이면 X를 1순위 원인으로 둔다」)을 판단 엔진이 평가하지 않아, 학생이 검토에서 그 규칙을 빼도 판단이 같았고
    냉각 효율이 정상인 설비도 사전 확률로 핀 오염이 골라졌다. 규칙을 빼면 판단이 달라진다(첫 줄과 둘째 줄)."""
    causes = card.rank_causes(T1, FAN_EVIDENCE, rules, {'pattern': 'COOLER_DEGRADATION', 'ce': ce})
    assessment = card.evidence_status(causes)
    assert assessment['status'] == status, assessment
    built = card.build_card(None, {'asset': 'HYD-03'}, causes, {c['id']: SKILLS for c in causes}, {'ok': True})
    assert built['topCause'] == top
    if status == 'UNSUPPORTED':
        assert '「냉각 효율이 70 % 미만이면 핀 오염을 1순위 원인으로 둔다.」' in assessment['reason'] and '맞지 않아' in assessment['reason']
    if status == 'UNKNOWN':
        assert '냉각 효율' in assessment['reason']
    if top == 'cause:cooler-fin-fouling':
        assert '문서의 진단 규칙' in built['summary'] and causes[0]['rules'][0]['status'] == 'FIRED'
