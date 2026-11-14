"""관리 › 흐름 정의 등록(it/portal/www/definitionRegistry.js) — 두 관리 패널이 함께 쓰는 패널 일 · 흐름 이름, JSON 칸 읽기, 등록 · 실행 단추.
node 에 실제 화면 파일을 index.html 차례로 싣는다. 브라우저 쪽만 대역이다(www_node.page_dom — 실제 index.html 의 요소 나무, 바깥 요청은 실패).
서버를 부르기 전에 끝나는 동작만 여기서 잰다 — 서버 응답을 받아 그리는 부분은 화면 순회(test_portal_ui)가 잰다."""
import pytest

from www_node import page_dom, run

FILES = ['ui.js', 'layers.js', 'courseAccess.js', 'definitionRegistry.js', 'definitionDeploy.js']


# 배포 패널(definitionDeploy.js)은 흐름 화면에 들어올 때 읽는다(app.js 의 탭 진입 표 hydTabs) — 여기서는 화면을 옮기지 않으므로 표만 대역으로 둔다
TABS = "globalThis.hydTabs = { onShow() {} };"


def js(script, data=None):
    return run(FILES, script, data, prelude=page_dom() + TABS)


@pytest.mark.parametrize('text, want', [
    ('{"processDefinitionId": "x"}', {'ok': {'processDefinitionId': 'x'}}),
    ('  {}  \n', {'ok': {}}),
    ('', {'error': '정의 칸이 비어 있습니다 — { } 로 묶은 JSON 객체를 적으세요'}),
    ('   ', {'error': '정의 칸이 비어 있습니다 — { } 로 묶은 JSON 객체를 적으세요'}),
    ('[1, 2]', {'error': '정의는 { } 로 묶은 JSON 객체여야 합니다'}),
    ('null', {'error': '정의는 { } 로 묶은 JSON 객체여야 합니다'}),
    ('"글"', {'error': '정의는 { } 로 묶은 JSON 객체여야 합니다'}),
    # 틀린 자리는 줄 · 글자로(3번째 줄 첫 글자의 } 앞에 쉼표가 남음)
    ('{\n  "a": 1,\n}', {'error': '정의 JSON을 읽지 못했습니다 (3번째 줄 1번째 글자) — 쉼표 · 따옴표 · 괄호가 짝이 맞는지 확인하세요'}),
    ('{"a": 1 "b": 2}', {'error': '정의 JSON을 읽지 못했습니다 (1번째 줄 9번째 글자) — 쉼표 · 따옴표 · 괄호가 짝이 맞는지 확인하세요'}),
    # 크롬이 자리 없이 틀린 글자만 말하는 꼴(값 자리에 } 가 옴)
    ('{"a": }', {'error': '정의 JSON을 읽지 못했습니다 (「}」 글자가 올 자리가 아닙니다) — 쉼표 · 따옴표 · 괄호가 짝이 맞는지 확인하세요'}),
    ('{"a": ', {'error': '정의 JSON을 읽지 못했습니다 (닫지 않은 괄호나 따옴표가 있습니다) — 쉼표 · 따옴표 · 괄호가 짝이 맞는지 확인하세요'}),
])
def test_JSON_칸은_객체만_받고_틀리면_자리를_한국어로_말한다(text, want):
    got = js("try { out({ ok: hydDefinitions.readObject(DATA.t, '정의') }); } catch (e) { out({ error: e.message }); }", {'t': text})
    assert got == want


@pytest.mark.parametrize('row, label', [
    ({'id': 'c3_pm', 'name': '정기 정비 흐름', 'version': '2'}, '정기 정비 흐름 · 판본 2'),
    # 이름이 없거나 id 를 그대로 이름으로 쓴 정의는 화면 이름표로 — 내부 id 를 보이지 않는다
    ({'id': 'c3_pm', 'name': None, 'version': '1'}, '정기 정비 · 판본 1'),
    ({'id': 'c3_pm', 'name': 'c3_pm', 'version': '1'}, '정기 정비 · 판본 1'),
    ({'id': 'student_x', 'name': '', 'version': '1'}, '흐름 표시 이름 미등록 · 판본 1'),
    # 서버가 지운 폼 출처 칸(form_source)이 와도 목록 글에 옛 표시가 붙지 않는다
    ({'id': 'c3_pm', 'name': '정기 정비', 'version': '1', 'form_source': 'legacy-live'}, '정기 정비 · 판본 1'),
])
def test_정의_목록의_한_줄은_흐름_이름과_판본만_말한다(row, label):
    assert js("out(hydDefinitions.optionLabel(DATA.r))", {'r': row}) == label


TASK = """
const buttons = DATA.before.map(d => ({ disabled: d }));
const panel = { querySelectorAll: sel => sel === 'button' ? buttons : [] }, note = { textContent: '', className: '' };
let afterCalls = 0, during = null, second = 'not called';
const t = hydDefinitions.task(panel, note, () => { afterCalls++; });
const first = t.run(async () => {
  during = [buttons.map(b => b.disabled), t.busy];
  await t.run(async () => { second = 'called'; });       // 도는 동안 다시 누름
  if (DATA.fail) throw new Error(DATA.fail);
});
await first;
out({ during, after: buttons.map(b => b.disabled), busy: t.busy, afterCalls, second, note });
"""


@pytest.mark.parametrize('before, fail, note', [
    ([False, False], None, {'textContent': '', 'className': ''}),
    # 원래 꺼져 있던 단추(운영 중 · 배포 불가 · 수업 경계)는 끝난 뒤에도 꺼진 채
    ([False, True, False], None, {'textContent': '', 'className': ''}),
    ([True], None, {'textContent': '', 'className': ''}),
    ([], None, {'textContent': '', 'className': ''}),
    # 실패는 패널 알림 줄에 그 문장 그대로, 실패라는 상태(data-tone=danger)와 함께
    ([False, True], '서버가 거절했습니다', {'textContent': '서버가 거절했습니다', 'className': '', 'dataset': {'tone': 'danger'}}),
])
def test_패널_일은_도는_동안_단추를_모두_끄고_끝나면_그_전_상태로_되돌린다(before, fail, note):
    got = js(TASK, {'before': before, 'fail': fail})
    assert got == {'during': [[True] * len(before), True], 'after': before, 'busy': False, 'afterCalls': 1, 'second': 'not called', 'note': note}


PANEL = """
const $ = id => document.getElementById(id);
for (const [id, v] of Object.entries(DATA.values || {})) $(id).value = v;
if (DATA.option) { const o = document.createElement('option'); o.value = JSON.stringify(DATA.option); $('definitionChoice').appendChild(o); $('definitionChoice').value = o.value; }
FETCHED.length = 0;   // 실릴 때 ui.js 가 이름 사전(names.json)을 읽는 것은 빼고, 단추를 누른 뒤의 요청만 본다
await $(DATA.click).fire('click');
const msg = $('definitionMessage');
out({ text: msg.textContent, tone: msg.dataset.tone, disabled: $('definitionEditor').querySelectorAll('button').map(b => [b.id, b.disabled]).filter(([, d]) => d), fetched: FETCHED });
"""


@pytest.mark.parametrize('click, values, option, text', [
    ('definitionPublish', {'definitionJson': ''}, None, '정의 칸이 비어 있습니다 — { } 로 묶은 JSON 객체를 적으세요'),
    ('definitionPublish', {'definitionJson': '{"processDefinitionId": "x",}'}, None,
     '정의 JSON을 읽지 못했습니다 (1번째 줄 29번째 글자) — 쉼표 · 따옴표 · 괄호가 짝이 맞는지 확인하세요'),
    ('definitionStart', {}, None, '등록된 정의 판본을 고르세요'),
    ('definitionCopy', {}, None, '등록된 정의 판본을 고르세요'),
    ('definitionStart', {'definitionEvent': '  '}, ['c3_pm', '1'],
     '시작 요청 번호를 적으세요 — 같은 번호로 다시 실행하면 서버가 중복으로 보고 시작하지 않습니다'),
    ('definitionStart', {'definitionEvent': 'run-1', 'definitionValues': '{"asset": }'}, ['c3_pm', '1'],
     '시작 변수 JSON을 읽지 못했습니다 (「}」 글자가 올 자리가 아닙니다) — 쉼표 · 따옴표 · 괄호가 짝이 맞는지 확인하세요'),
    ('definitionStart', {'definitionEvent': 'run-1', 'definitionAlert': '[]'}, ['c3_pm', '1'], '경보는 { } 로 묶은 JSON 객체여야 합니다'),
])
def test_등록_실행_단추는_서버를_부르기_전에_틀린_입력을_학생_말로_멈추고_단추를_되살린다(click, values, option, text):
    got = js(PANEL, {'click': click, 'values': values, 'option': option})
    assert got == {'text': text, 'tone': 'danger', 'disabled': [], 'fetched': []}
