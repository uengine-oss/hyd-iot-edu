"""흐름 화면의 「판본 · 배포」와 「경보별 운영 흐름」(it/portal/www/definitionDeploy.js — 패널은 index.html 의 view-flows 안에 있다) — 「기준과 비교」 단추를 다는 판정, 배포 · 되돌리기 결과 한 줄.
node 에 실제 화면 파일을 index.html 차례로 싣는다(브라우저 쪽만 대역 — www_node.page_dom). 서버 응답 모양은 서버 코드 그대로:
versions 의 compare_base = flow_deploy.compare_base, 배포 응답 = instances.InstanceRuntime.deploy_definition."""
import re

import pytest

from conftest import ROOT
from www_node import page_dom, run

# 경보 이름표의 정본은 그래프(AnomalyPattern.name) — 화면은 agent /api/ontology/patterns 로 읽는다(ui.js). 여기서는 그 응답 대신 시드 원문을 읽는다
SEED = ROOT / 'it' / 'neo4j' / 'v2' / 'instances.cypher'
PATTERNS = {code: name for name, code in re.findall(r"\['pattern:[^']+','([^']+)','([A-Z_]+)'", SEED.read_text(encoding='utf-8'))}

FILES = ['ui.js', 'layers.js', 'courseAccess.js', 'definitionRegistry.js', 'definitionDeploy.js']


# 배포 패널은 흐름 화면에 들어올 때 읽는다(app.js 의 탭 진입 표 hydTabs) — 여기서는 화면을 옮기지 않으므로 표만 대역으로 둔다
TABS = "globalThis.hydTabs = { shown: [], onShow(fn) { this.shown.push(fn); } };"


def js(script, data=None):
    return run(FILES, script, data, prelude=page_dom() + TABS)


REF = {'definition': 'anomaly_response', 'version': '2.2', 'name': '설비 이상 조치', 'why': '기준 흐름의 기준 판본'}
OTHER = {'definition': 'anomaly_response', 'version': '2.2', 'name': '설비 이상 조치', 'pattern': 'PUMP_LEAKAGE', 'why': '이 흐름이 없을 때 같은 경보를 여는 기준 흐름'}


@pytest.mark.parametrize('status, version, shown', [
    # 기준 흐름: 기준 판본 자신만 빼고 단다
    ({'id': 'anomaly_response', 'compare_base': REF}, '2.2', False),
    ({'id': 'anomaly_response', 'compare_base': REF}, '2.3', True),
    # 경보로 시작하는 학생 흐름: 서버가 고른 기준(다른 흐름)과 — 판본이 기준 판본 번호와 같아도 다른 흐름이라 단다
    ({'id': 'student_pump', 'compare_base': OTHER}, '1', True),
    ({'id': 'student_pump', 'compare_base': OTHER}, '2.2', True),
    # 강사가 설치한 수업 흐름 · 경보로 시작하지 않는 흐름(교대 · 질문): 서버가 기준 없음(null) — 단지 않는다(눌러 봐야 409, W3-03)
    ({'id': 'c3_pm', 'compare_base': None, 'alert_entry': True, 'class_flow': True}, '1', False),
    ({'id': 'shift_handover', 'compare_base': None, 'alert_entry': False}, '1', False),
    # 화면이 경보 흐름 여부를 따로 셈하지 않는다 — 서버 기준이 있으면 단다
    ({'id': 'student_pump', 'compare_base': OTHER, 'alert_entry': False, 'class_flow': False}, '1', True),
])
def test_기준과_비교_단추는_서버가_정한_비교_기준이_있을_때만_단다(status, version, shown):
    assert js("out(hydDefinitionDeploy.refComparable(DATA.s, { version: DATA.v }))", {'s': status, 'v': version}) is shown


@pytest.mark.parametrize('out, name, verb, text', [
    ({'definition': 'student_pump', 'version': '2', 'previous_version': '1', 'patterns': ['PUMP_LEAKAGE'], 'applies_to': '다음 경보부터(PUMP_LEAKAGE)'},
     '펌프 누설 대응', '배포', '「펌프 누설 대응」 운영 판본 1 → 2 배포. 다음 경보(펌프 내부 누설)부터 적용됩니다.'),
    ({'definition': 'anomaly_response', 'version': '2.2', 'previous_version': '2.3', 'patterns': ['COOLER_DEGRADATION', 'FAN_VIBRATION'],
      'applies_to': '다음 경보부터'},
     None, '되돌림', '「설비 이상 조치」 운영 판본 2.3 → 2.2 되돌림. 다음 경보(쿨러 성능 저하 · 팬 진동 상승)부터 적용됩니다.'),
    # 처음 배포(이전 판본 없음) · 경보 시작 조건이 없는 흐름은 서버 문장 그대로
    ({'definition': 'c3_pm', 'version': '1', 'previous_version': None, 'patterns': [], 'applies_to': '다음 직접 시작부터(경보 시작 조건 없음)'},
     'c3_pm', '배포', '「정기 정비」 운영 판본 없음 → 1 배포. 다음 직접 시작부터(경보 시작 조건 없음) 적용됩니다.'),
    # 표에 없는 경보 코드(학생이 만든 경보)는 지어내지 않고 코드 그대로
    ({'definition': 'student_x', 'version': '1', 'previous_version': None, 'patterns': ['MY_ALARM'], 'applies_to': '다음 경보부터(MY_ALARM)'},
     '내 흐름', '배포', '「내 흐름」 운영 판본 없음 → 1 배포. 다음 경보(MY_ALARM)부터 적용됩니다.'),
])
def test_배포_결과_한_줄은_흐름과_경보를_이름으로_말한다(out, name, verb, text):
    assert js("UI.patterns = DATA.p; out(hydDefinitionDeploy.doneText(DATA.o, DATA.n, DATA.v))", {'o': out, 'n': name, 'v': verb, 'p': PATTERNS}) == text


PANEL = """
const $ = id => document.getElementById(id);
for (const [id, v] of Object.entries(DATA.values)) $(id).value = v;
window.hydInbox = { me: () => DATA.me };   // 「나」는 inbox.js 가 쥔다 — 여기서는 고른 사람만 대역
UI.confirm = async () => false;            // 확인 창에서 [취소] — 서버를 부르기 직전에 멈춘다
FETCHED.length = 0;   // 실릴 때 읽는 이름 사전(names.json)은 빼고
await $('deployRoutesBox').fire('click', { target: $('deployResetRef') });   // 화면 아래 「경보별 운영 흐름」의 [기준 흐름으로 되돌리기]
const msg = $('deployResetMessage'), box = msg.parentElement;   // 그 자리의 알림 판(alert) — 실패면 destructive 로 바뀌고 보인다
out({ text: msg.textContent, failed: box.dataset.variant === 'destructive', hidden: box.hidden, fetched: FETCHED, by: $('deployBy').value, readOnly: $('deployBy').readOnly });
"""


def test_기준_흐름으로_되돌리기는_담당자를_못_읽었으면_서버를_부르지_않고_멈춘다():
    """담당자 칸에 적은 글은 쓰지 않는다 — 자유 입력이 배포 이력에 지어낸 이름으로 남던 것(FW2 → FA2)."""
    got = js(PANEL, {'values': {'deployBy': '아무 이름'}, 'me': None})
    assert got == {'text': '담당자 정보를 읽지 못했습니다. 화면을 새로 고친 뒤 다시 해 주세요', 'failed': True, 'hidden': False, 'fetched': [], 'by': '', 'readOnly': True}


def test_담당자_칸은_고른_나의_이름을_읽기만으로_보인다():
    got = js(PANEL, {'values': {'deployBy': '아무 이름'}, 'me': {'id': 'user:kim-op', 'name': '김운영', 'roles': []}})
    assert got['by'] == '김운영' and got['readOnly'] is True and got['fetched'] == []
