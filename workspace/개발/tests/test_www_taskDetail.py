"""단계 상세(it/portal/www/taskDetail.js) — 옆 판의 「받은 값 · 넘긴 값」 보기가 그리는 값."""
from www_node import run

FILES = ['ui.js', 'plainWords.js', 'trace.js', 'instanceSteps.js', 'approvalCard.js', 'taskDetail.js']

#: 판단 엔진이 판단을 등록할 때 다시 한 진단(판단 기록 origin.diagnosis — dmn-mcp _submitted_diagnosis 의 칸)
SERVER = {'top_cause': 'cause:cooler-fin-fouling', 'failure_mode': 'fm:cooler-cooling-loss',
          'causes': [{'id': 'cause:cooler-fin-fouling', 'name': '쿨러 핀 오염', 'score': 0.6, 'prior': 0.6, 'failureModeId': 'fm:cooler-cooling-loss',
                      'symptoms': ['냉각 효율 저하'], 'rules': [],
                      'evidence': [{'id': 'evd:ce-low', 'name': '냉각 효율 저하', 'tag': 'CE', 'expect': 'lt', 'threshold': 70,
                                    'value': 46.2, 'passed': True, 'status': 'PASS'}]}]}
#: AI 에이전트가 결과 칸에 옮겨 적으며 바꾼 원인 진단 결과
WRITTEN = {'topCause': 'cause:invented', 'causes': [{'id': 'cause:invented', 'name': '지어낸 원인', 'score': 0.9, 'prior': 0.9,
                                                     'evidence': [{'id': 'evd:x', 'name': '지어낸 근거', 'tag': 'TS1', 'value': 99.9, 'passed': True}]}]}
SCRIPT = r"""
const T = hydTaskDetail.T, clean = h => h.split('<details')[0].replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ');
T.wid = 'W1'; T.dec = { id: 'D-1', recommended: 'skill:a', options: [], origin: { diagnosis: DATA.server } };
const bound = { workitems: [{ id: 'W1', activity_id: 'T_agent', output: { decision_id: 'D-1', decision: { recommended: 'skill:a' } } }], instance: { variable_sources: {} } };
const unbound = { workitems: [{ id: 'W1', activity_id: 'task:diagnose', output: { cause: 'cause:invented' } }], instance: { variable_sources: {} } };
out({ bound: clean(hydTaskDetail.valueHtml('guide_card', DATA.written, bound)), unbound: clean(hydTaskDetail.valueHtml('guide_card', DATA.written, unbound)) });
"""


def test_원인_표는_판단_엔진이_다시_한_진단을_근거가_읽은_시계열의_단위로_그리고_AI가_옮겨_적은_글을_표로_그리지_않는다():
    """독립 검증(2026-11-02): 단계 상세의 원인 표에 단위가 없었다. 2026-11-22 탐사 N1 · F2: 그 표가 AI 가 옮겨 적은 원인 진단 결과(guide_card)를
    「원인 점수 · 조건 표」로 보였다 — 서버가 대조하지 않은 글이다. 표는 이 단계가 등록한 판단의 서버 진단으로 그리고, 판단을 등록하지 않은 단계는
    그 사실만 말한다(AI 의 글은 원문 접기에만)."""
    got = run(FILES, SCRIPT, {'server': SERVER, 'written': WRITTEN})
    assert '쿨러 핀 오염' in got['bound'] and '70 %' in got['bound'] and '46.2 %' in got['bound'], got
    assert '지어낸' not in got['bound'] and '99.9' not in got['bound'], got
    assert '지어낸' not in got['unbound'] and '판단 엔진이 판단을 등록할 때 다시 한 진단' in got['unbound'], got
