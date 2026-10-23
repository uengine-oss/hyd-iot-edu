"""포털 화면 검수(2026-10-23 .evidence/audit2/portal.md) 결함을 고친 뒤의 올바른 동작.

전체 포털(index.html + 모든 스크립트)을 가짜 API(portal_fake) 또는 실제 FastAPI+MemoryRepo(test_portal_approval_ui.Portal)에 붙여
Chromium 으로 확인한다. 결함 번호는 검수 문서의 P 번호다.
"""
import json
import re

import pytest

from portal_fake import FakePortal, browser, instance, esc_task, todo_row, instance_handlers, PEOPLE, NOW, iso  # noqa: F401

UUID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$')


def open_instances(p, pid='inst-1'):
    p.open(f'#/instances/{pid}')
    p.page.evaluate("hydApp.selectTab('instances')")


def mark(p, selector):
    """Tag the current DOM node so a later check can tell whether it was replaced (a full redraw)."""
    p.page.evaluate("s => { document.querySelector(s).__kept = true; }", selector)


def kept(p, selector):
    return p.page.evaluate("s => !!(document.querySelector(s) || {}).__kept", selector)


# ---------------------------------------------------------------- P1 처리 건 화면 다시 그리기
def test_p1_projection_poll_keeps_generic_form(browser):
    """지식 대조 시각(knowledge.last_checked)만 바뀌는 읽기는 폼을 다시 그리지 않는다 — 포커스 · 친 글자 유지, 시각 줄은 그 자리에서 갱신."""
    view = instance()
    h, counter = instance_handlers([view], [todo_row(esc_task())], {'inst-1-esc': esc_task()})
    p = FakePortal(browser, h)
    try:
        open_instances(p)
        p.page.locator('#tdField0').wait_for()
        p.page.locator('#tdField0').click()
        p.page.keyboard.type('첫 줄')
        mark(p, '#todoPanel section')
        before = counter['projections']
        p.page.wait_for_timeout(4500)
        assert counter['projections'] > before
        assert kept(p, '#todoPanel section'), 'the panel was redrawn by a poll that changed only knowledge.last_checked'
        assert p.page.evaluate('document.activeElement.id') == 'tdField0'
        p.page.keyboard.type(' 추가')
        assert p.page.locator('#tdField0').input_value() == '첫 줄 추가'
        assert not p.errors, p.errors
    finally:
        p.close()


def test_p1_other_instance_event_does_not_redraw_and_own_event_keeps_focus(browser):
    """다른 처리 건의 SSE 이벤트는 고른 처리 건의 폼을 다시 그리지 않는다. 고른 처리 건의 이벤트로 다시 그려도 포커스 · 커서 · 값이 남는다."""
    a, b = instance('inst-1'), instance('inst-2')
    h, _ = instance_handlers([a, b], [todo_row(esc_task('inst-1')), todo_row(esc_task('inst-2'))],
                             {'inst-1-esc': esc_task('inst-1'), 'inst-2-esc': esc_task('inst-2')}, moving_projection=False)
    p = FakePortal(browser, h)
    try:
        open_instances(p)
        p.page.locator('#tdField1').wait_for()
        p.page.wait_for_function("hydInstances.I.sel === 'inst-1' && !hydInstances.I.loading")
        p.page.locator('#tdField1').click()
        p.page.keyboard.type('담당자 메모')
        p.page.keyboard.press('ArrowLeft')
        mark(p, '#todoPanel section')
        b['instance']['current_activity_ids'] = ['task:agent']          # 다른 처리 건이 실제로 바뀐다 → 목록은 다시 그린다
        p.page.evaluate("""() => hydStream.push({ id: 'ev-b-1', event_type: 'task_started', proc_inst_id: 'inst-2', todo_id: 'inst-2-esc', timestamp: new Date().toISOString(), data: {} }, true)""")
        p.page.wait_for_timeout(1200)
        assert kept(p, '#todoPanel section'), "another case's event redrew the selected case's form"
        assert p.page.locator('#instList').inner_text().count('에이전트 판단') == 1, 'the list should show the other case moved on'
        p.page.evaluate("""() => hydStream.push({ id: 'ev-a-1', event_type: 'task_started', proc_inst_id: 'inst-1', todo_id: 'inst-1-esc', timestamp: new Date().toISOString(), data: {} }, true)""")
        p.page.wait_for_function("!hydInstances.I.loading")
        p.page.wait_for_timeout(800)
        assert not kept(p, '#todoPanel section'), 'own-case event must force a redraw (precondition)'
        assert p.page.evaluate('document.activeElement.id') == 'tdField1'
        assert p.page.evaluate("[document.activeElement.selectionStart, document.activeElement.selectionEnd]") == [len('담당자 메모') - 1] * 2
        p.page.keyboard.type('X')
        assert p.page.locator('#tdField1').input_value() == '담당자 메X모'
    finally:
        p.close()


def failed_approval(by='이생산'):
    return [{'todo_id': 'w-x', 'status': 'FAILED', 'attempts': 3, 'error': 'boom',
             'payload': {'by': by, 'option': 'skill:a', 'plan': {'option': {'name': '팬 100 %'}, '_snapshot': {'roles': {'role:operator': {}}}}}, 'history': []}]


def test_p1_retry_and_discard_inputs_survive_redraw(browser):
    """승인 재전달 · 폐기 폼의 칸 값과 [실행 효과 확인] 결과(폐기 확인)가 다시 그리기 뒤에도 남고, 다시 수행 사유 칸 포커스도 남는다."""
    view = instance(approvals=failed_approval())
    evidence = {'incident': {'state': 'CLOSED'}, 'enterprise_receipts': [], 'outcome': '실제 조치 없음', 'cancel_workitems': ['inst-1-esc']}
    h, _ = instance_handlers([view], [], {}, extra={('POST', '/api/todolist/w-x/approval-discard-preview'): evidence})
    p = FakePortal(browser, h)
    try:
        open_instances(p)
        p.page.locator('[data-retry-by]').wait_for()
        p.page.locator('[data-retry-by]').fill('김운전')
        p.page.locator('[data-retry-role]').select_option('role:operator')
        p.page.locator('[data-discard-reason]').fill('조치 없음 확인')
        p.page.locator('[data-approval-discard-preview]').click()
        p.page.locator('[data-confirm-discard]').wait_for()
        p.page.evaluate('hydInstances.load(true)')
        p.page.wait_for_function('!hydInstances.I.loading')
        assert p.page.locator('[data-retry-by]').input_value() == '김운전'
        assert p.page.locator('[data-retry-role]').input_value() == 'role:operator'
        assert p.page.locator('[data-discard-reason]').input_value() == '조치 없음 확인'
        assert p.page.locator('[data-confirm-discard]').count() == 1, 'the discard confirmation vanished on redraw'
        p.page.locator('#reworkPanel summary').first.click()
        p.page.locator('#rwReason').click()
        p.page.keyboard.type('조건 변경')
        p.page.evaluate('hydInstances.load(true)')
        p.page.wait_for_function('!hydInstances.I.loading')
        p.page.wait_for_timeout(300)
        assert p.page.evaluate('document.activeElement.id') == 'rwReason'
        assert p.page.locator('#rwReason').input_value() == '조건 변경'
    finally:
        p.close()


# ---------------------------------------------------------------- P2 「나」의 원문 id
def test_p2_me_shows_name_not_user_id(browser):
    view = instance(approvals=failed_approval(by='user:kim-op'))
    h, _ = instance_handlers([view], [todo_row(esc_task())], {'inst-1-esc': esc_task()}, moving_projection=False)
    p = FakePortal(browser, h, me='user:kim-op')
    try:
        open_instances(p)
        p.page.locator('#tdField0').wait_for()
        p.page.wait_for_function("document.querySelector('[data-approval-panel] .kv-line') && UI.performers['user:kim-op'] === '김운전'")
        p.page.evaluate('hydInstances.load(true)')
        p.page.wait_for_function('!hydInstances.I.loading')
        p.page.locator('#reworkPanel summary').first.click()
        text = p.page.locator('#view-instances').inner_text()
        assert 'user:' not in text, [line for line in text.splitlines() if 'user:' in line]
        assert '승인 김운전' in p.page.locator('[data-approval-panel] .kv-line').first.inner_text()
        assert '김운전' in p.page.locator('#reworkPanel').inner_text() and '(나)' in p.page.locator('#reworkPanel').inner_text()
        # 보내는 값은 서버가 구성원 검사를 할 수 있게 그대로 사람 id
        assert p.page.locator('#rwBy').input_value() == 'user:kim-op'
        assert p.page.locator('[data-retry-by]').input_value() == 'user:kim-op'
    finally:
        p.close()


# ---------------------------------------------------------------- P3 배포 패널 버튼
DEFS = [{'id': 'c3_cooling', 'name': '쿨러 대응', 'version': v, 'deployed': v == '1', 'deployed_version': '1'} for v in ('1', '2', '3')]
STATUS = {'id': 'c3_cooling', 'name': '쿨러 대응', 'alert_entry': True, 'deployed_version': '1', 'reference': False, 'reference_version': None,
          'rollback_version': None, 'history': [],
          'versions': [{'version': '1', 'deployed': True, 'deployable': True, 'registered_at': None},
                       {'version': '2', 'deployed': False, 'deployable': False, 'problem': '검사 실패', 'registered_at': None},
                       {'version': '3', 'deployed': False, 'deployable': True, 'registered_at': None}]}
ROUTES = {'routes': [], 'flows': [], 'at_reference': True, 'reference': {'version': '1', 'changed': False}}


def test_p3_failed_deploy_action_keeps_disabled_buttons(browser):
    h = {('GET', '/api/process/mode'): {'mode': 'instance'}, ('GET', '/api/inbox/users'): PEOPLE,
         ('GET', '/api/process/definitions'): DEFS, ('GET', '/api/process/definitions/c3_cooling/versions'): STATUS,
         ('GET', '/api/flows/deployments'): ROUTES}
    p = FakePortal(browser, h)
    try:
        p.open('#/admin')
        p.page.evaluate("hydApp.selectTab('admin')")
        p.page.locator('#definitionDeployPanel > summary').click()
        p.page.locator('[data-deploy="1"]').wait_for()
        state = "() => ['[data-deploy=\"1\"]', '[data-deploy=\"2\"]', '#deployResetRef', '[data-deploy=\"3\"]'].map(s => document.querySelector(s).disabled)"
        assert p.page.evaluate(state) == [True, True, True, False]
        p.page.locator('#deployBy').fill('')
        p.page.locator('[data-deploy="3"]').click()
        p.page.wait_for_function("document.querySelector('#deployMessage').textContent.includes('담당자')")
        assert p.page.evaluate(state) == [True, True, True, False]
    finally:
        p.close()


# ---------------------------------------------------------------- P4 다른 사람이 먼저 승인
def test_p4_server_text_translates_known_english_reasons(browser):
    p = FakePortal(browser, {('GET', '/api/process/mode'): {'mode': 'instance'}})
    try:
        p.open()
        out = p.page.evaluate("""() => ['T_approve is DONE', 'task deadline expired', 'task is not waiting for this deferral', 'reason must be nonblank text, at most 2000 characters', '그대로 둘 한국어 문구'].map(x => UI.serverText(x))""")
        assert out[0].startswith('이미 처리된 단계입니다') and 'DONE' not in out[0]
        assert out[1] == '선택 기한이 지나 이 단계가 닫혔습니다.'
        assert out[2].startswith('이 보류는 이미 다시 평가됐거나')
        assert out[3] == '사유 칸을 1~2000자로 적으세요.'
        assert out[4] == '그대로 둘 한국어 문구'
    finally:
        p.close()


from test_portal_approval_ui import Portal, approval_clock  # noqa: E402,F401
from test_instance_mode import world, _row  # noqa: E402,F401
from test_approval_stage import opened, MGR  # noqa: E402


def test_p4_other_approver_first(browser, world):
    """역할 공용 승인을 다른 사람이 먼저 하면 [승인]은 4xx — 패널 자리에 '이미 처리된 승인입니다'가 남고, 다른 처리 건 카드에는 그 오류가 붙지 않는다.
    고른 처리 건의 작업은 GET /api/todolist?proc_inst_id=…&status=IN_PROGRESS 로 읽는다."""
    p = Portal(browser, world, 'c3_pm')
    asked = []
    p.page.on('request', lambda r: asked.append(r.url) if '/api/todolist?' in r.url else None)
    try:
        opened(world, 'c3_spare')
        p.rt.select(_row(p.rt, p.inst, 'T_approve')['id'], p.d['id'], p.d['options'][0]['id'], *MGR, now=NOW)
        p.page.locator('#tdGo').click()
        p.settle()
        panel = p.page.locator('#todoPanel').inner_text()
        assert '이미 처리된 승인입니다' in panel, panel
        assert ' is DONE' not in panel
        assert any(f'proc_inst_id={p.inst["proc_inst_id"]}' in u and 'status=IN_PROGRESS' in u for u in asked), asked
        p.page.locator('#todoList .item').first.click()
        p.settle()
        p.page.locator('#tdGo').wait_for()
        p.settle()
        assert p.page.locator('#todoPanel .form-msg').all_inner_texts() == []
        assert '이미 처리된' not in p.page.locator('#todoPanel').inner_text()
    finally:
        p.close()


def test_p4_error_cleared_when_case_moves_to_next_task(browser):
    """같은 처리 건이 다음 단계로 넘어가면(고르기 없이 읽기만으로) 지난 단계의 오류 문구가 새 단계 패널에 남지 않는다."""
    rows = [todo_row(esc_task())]
    nxt = dict(esc_task(), id='inst-1-esc2', activity_name='담당 재확인')
    h, _ = instance_handlers([instance()], lambda: rows, {'inst-1-esc': esc_task(), 'inst-1-esc2': nxt}, moving_projection=False,
                             extra={('POST', '/api/todolist/inst-1-esc/submit'): (409, {'detail': '확인 메모 형식이 맞지 않습니다'})})
    p = FakePortal(browser, h)
    try:
        open_instances(p)
        p.page.locator('#tdField0').fill('메모')
        p.page.locator('#tdField1').fill('김운전')
        p.page.locator('#tdDone').click()
        p.page.wait_for_function("document.querySelector('#todoPanel .form-msg') && document.querySelector('#todoPanel .form-msg').innerText.includes('형식')")
        rows[:] = [todo_row(nxt)]
        p.page.evaluate('hydInstances.load(true)')
        p.page.wait_for_function("!hydInstances.I.loading && hydInstances.I.taskView && hydInstances.I.taskView.id === 'inst-1-esc2' && !!document.querySelector('#tdDone')")
        assert p.page.locator('#todoPanel .form-msg').count() == 0, p.page.locator('#todoPanel .form-msg').all_inner_texts()
    finally:
        p.close()


# ---------------------------------------------------------------- P6 「승인과 실행」 탭(처리 건 방식)
DEC = {'id': 'dec-1', 'created': '2026-10-23T01:00:00Z', 'state': 'PENDING_APPROVAL', 'asset': 'HYD-01', 'recommended': 'skill:fan',
       'scenario': {'name': '쿨러 성능 저하', 'failureMode': 'fm:cooling-loss', 'cause': 'cause:fin'}, 'origin': {'kind': 'alert', 'incident': 'INC-1'},
       'roles': {'role:operator': {'name': '운전원', 'level': 1}}, 'history': [], 'executions': [], 'explanation': '팬을 올립니다.',
       'options': [{'id': 'skill:fan', 'name': '팬 증속', 'feasible': True, 'score': 1.2, 'approver': {'id': 'role:operator'}, 'actions': []}]}


def test_p6_process_tab_sends_to_instance_instead_of_dead_form(browser):
    view = instance(variables=[{'key': 'asset', 'value': 'HYD-01'}, {'key': 'incident', 'value': 'INC-1'}])
    h, _ = instance_handlers([view], [], {}, moving_projection=False, extra={('GET', '/api/decisions'): [DEC], ('GET', '/api/decisions/dec-1'): DEC})
    p = FakePortal(browser, h)
    try:
        p.open('#/process')
        p.page.evaluate("hydApp.selectTab('process')")
        p.page.locator('#decGoInstance').wait_for(timeout=8000)
        assert p.page.locator('#decApprove').count() == 0 and p.page.locator('#decReject').count() == 0
        p.page.locator('#decGoInstance').click()
        p.page.wait_for_function("state.tab === 'instances' && hydInstances.I.sel === 'inst-1'")
        assert not [x for x in p.posts if x[1].endswith('/approve')]
    finally:
        p.close()


# ---------------------------------------------------------------- P8 모든 안 불가
@pytest.mark.parametrize('did', ['c3_cooling', 'c3_pm'])
def test_p8_all_infeasible_says_no_option_and_next_step(browser, world, did):
    p = Portal(browser, world, did)
    try:
        d = world['book'][p.d['id']]
        for o in d['options']:
            o['feasible'] = False
            o.setdefault('violations', []).append({'rule': 'rule:x', 'annotation': f'{o["name"]} — 예비 펌프 정비 중이라 실행 불가'})
        d['recommended'] = None
        p.page.evaluate("() => { const I = hydInstances.I; I.dec = null; I.form.option = null; I.form.review = null; return hydInstances.load(true); }")
        p.settle()
        panel = p.page.locator('#todoPanel')
        assert p.page.locator('#tdGo').is_disabled()
        assert '추천할 수 있는 안이 없습니다' in panel.locator('.ap-head').inner_text()
        assert '1순위' not in panel.locator('.ap-head').inner_text()
        body = panel.locator('.ap-card').inner_text()
        for o in d['options']:
            assert f'{o["name"]} — 예비 펌프 정비 중이라 실행 불가' in body
        actions = panel.locator('.form-actions').last.inner_text()
        assert '실행할 수 있는 안이 없어 승인할 수 없습니다' in actions and '[거절]' in actions
    finally:
        p.close()


# ---------------------------------------------------------------- P9 조건별 손익
MONEY = {'total_won': 1000, 'items': [], 'complete': True, 'missing': [], 'basis': ''}
WVIEW = {'id': 'w1', 'asset': 'HYD-01', 'created': '2026-10-23T00:00:00Z', 'summary': '기준', 'original': {'unchanged': True, 'note': ''},
         'top': {'decision': 'c1', 'money': 'c1'}, 'cause': {'name': '쿨러'},
         'cards': [{'id': 'c1', 'name': '팬 증속', 'feasible': True, 'decisionRank': 1, 'moneyRank': 1, 'score': 1.0, 'money': MONEY, 'excluded': []}],
         'variables': [{'id': 'price', 'label': '단가', 'unit': '원', 'kinds': ['money'], 'base': 10, 'source': {'kind': '데이터', 'where': 'ERP · 단가'}}],
         'policy': {'components': [], 'penalties': []}, 'perspectives': {'available': False, 'reason': ''}}


def test_p9_boundaries_arrival_keeps_typed_value_and_focus(browser):
    h = {('GET', '/api/process/mode'): {'mode': 'instance'}, ('GET', '/api/inbox/users'): PEOPLE,
         ('GET', '/api/ontology/patterns'): [{'code': 'COOLER_DEGRADATION', 'name': '쿨러 성능 저하'}],
         ('POST', '/api/agent/whatif'): WVIEW, ('POST', '/api/agent/whatif/w1/boundaries'): lambda q, b: 'HOLD'}
    p = FakePortal(browser, h)
    try:
        p.open('#/whatif')
        p.page.evaluate("hydApp.selectTab('whatif')")
        p.page.locator('#wiLoad:not([disabled])').wait_for()
        p.page.locator('#wiLoad').click()
        p.page.locator('[data-wi-tab="values"]').click()
        p.page.locator('[data-wi-var="price"]').click()
        p.page.keyboard.type('12')
        p.release({'id': 'w1', 'boundaries': []})
        p.page.wait_for_function("hydWhatif._W.bounds !== null")
        p.page.wait_for_timeout(200)
        assert p.page.locator('[data-wi-var="price"]').input_value() == '12'
        assert p.page.evaluate('document.activeElement.dataset.wiVar') == 'price'
        assert p.page.evaluate('hydWhatif._W.values') == {'price': 12}
    finally:
        p.close()


# ---------------------------------------------------------------- P10 흐름 가져오기 두 번 누름
def test_p10_direct_start_double_click_sends_once_with_stable_event_id(browser):
    starts = []

    def start(q, b):
        starts.append(b)
        return 'HOLD' if len(starts) == 1 else (409, {'detail': '같은 시작 이벤트'})
    h = {('GET', '/api/process/mode'): {'mode': 'instance'}, ('GET', '/api/inbox/users'): PEOPLE,
         ('GET', '/api/flows/catalog'): {'parts': [], 'roles': [], 'agents': [], 'patterns': [], 'ops': ['=='], 'base': {}},
         ('GET', '/api/flows'): {'drafts': [], 'versions': [{'id': 'oil_check', 'version': '1', 'name': '오일 점검', 'registered_at': '2026-10-23T00:00:00Z'}]},
         ('GET', '/api/process/definitions/oil_check'): {'processDefinitionName': '오일 점검', 'startForm': {'fields_json': [{'key': 'note', 'text': '메모', 'type': 'text'}]}},
         ('POST', '/api/instances/start'): start}
    p = FakePortal(browser, h)
    try:
        p.open('#/flows')
        p.page.evaluate("hydApp.selectTab('flows')")
        p.page.locator('[data-start="oil_check"]').click()
        go = p.page.locator('[data-startbox] [data-go]')
        go.wait_for()
        p.page.locator('[data-sv="note"]').fill('x')
        p.page.evaluate("() => { const b = document.querySelector('[data-startbox] [data-go]'); b.click(); b.click(); }")
        p.wait_until(lambda: len(starts) >= 1)
        p.page.wait_for_timeout(400)              # 두 번째 누름이 요청을 보낼 틈
        assert len(starts) == 1
        assert go.is_disabled()
        p.release({'detail': '응답 잃음'}, status=503)
        p.page.wait_for_function("!document.querySelector('[data-startbox] [data-go]').disabled")
        go.click()                                  # 실패 뒤 다시 누름 = 같은 요청의 재시도
        p.wait_until(lambda: len(starts) >= 2)
        assert len(starts) == 2 and starts[0]['event_id'] == starts[1]['event_id']
    finally:
        p.close()


def test_p10_import_double_click_sends_once(browser, tmp_path):
    h = {('GET', '/api/process/mode'): {'mode': 'instance'}, ('GET', '/api/inbox/users'): PEOPLE,
         ('GET', '/api/flows/catalog'): {'parts': [], 'roles': [], 'agents': [], 'patterns': [], 'ops': ['=='], 'base': {}},
         ('GET', '/api/flows'): {'drafts': [], 'versions': []}, ('POST', '/api/flows/import'): lambda q, b: 'HOLD'}
    f = tmp_path / 'a.bpmn'
    f.write_text('<definitions/>', encoding='utf-8')
    p = FakePortal(browser, h)
    try:
        p.open('#/flows')
        p.page.evaluate("hydApp.selectTab('flows')")
        p.page.locator('#flowFile').set_input_files(str(f))
        p.page.evaluate("() => { const b = document.querySelector('#flowImport'); b.click(); b.click(); }")
        p.wait_until(lambda: any(x[1] == '/api/flows/import' for x in p.posts))
        p.page.wait_for_timeout(400)              # 두 번째 누름이 요청을 보낼 틈
        assert len([x for x in p.posts if x[1] == '/api/flows/import']) == 1
        p.release({'detail': '그림 오류'}, status=422)
        p.page.wait_for_function("!document.querySelector('#flowImport').disabled")
    finally:
        p.close()


# ---------------------------------------------------------------- P11 상단바 「나」 · 종
def test_p11_shell_me_and_bell_count(browser):
    h = {('GET', '/api/process/mode'): {'mode': 'instance'}, ('GET', '/api/inbox/users'): PEOPLE,
         ('GET', '/api/inbox'): {'tasks': [], 'asked': [], 'roles': ['role:operator'], 'unread': 3, 'unassigned_roles': []},
         ('GET', '/api/inbox/notifications'): [], ('GET', '/api/inbox/assignments'): {'roles': [], 'people': PEOPLE}}
    p = FakePortal(browser, h, me='user:kim-op')
    try:
        p.open('#/inbox')
        p.page.wait_for_function("document.querySelector('#shellMe').innerText.includes('김운전')")
        assert '선택 안 함' not in p.page.locator('#shellMe').inner_text()
        p.page.wait_for_function("!document.querySelector('#shellBadge').hidden")
        assert p.page.locator('#shellBadge').inner_text() == '3'
        n0 = p.page.evaluate('hydInbox.X.badges.length')
        for _ in range(4):
            p.page.evaluate('hydShell.refreshBadge()')
        assert p.page.evaluate('hydInbox.X.badges.length') == n0 == 1
        p.page.evaluate("document.querySelector('[data-inbox-me]').value = 'user:lee-prod'; document.querySelector('[data-inbox-me]').dispatchEvent(new Event('change'))")
        p.page.wait_for_function("document.querySelector('#shellMe').innerText.includes('이생산')")
    finally:
        p.close()


# ---------------------------------------------------------------- P14 오래된 예측 거절 → 미리 보기
STALE = '현재 조건 재확인 실패: 검토한 예측이 시뮬레이션 12분 전 상태입니다: 새 카드 검토가 필요합니다'


def test_p14_stale_forecast_refusal_shows_preview(browser, world):
    p = Portal(browser, world, 'c3_cooling')
    try:
        p.page.route('**/select', lambda r: r.fulfill(status=403, content_type='application/json', body=json.dumps({'detail': STALE})))
        p.page.locator('#tdGo').click()
        p.settle()
        msg = ' '.join(p.page.locator('#todoPanel .form-msg').all_inner_texts())
        assert '[미리 보기]로 지금 조건을 다시 확인한 뒤 승인하세요' in msg
        now = p.page.locator('#tdPreviewNow')
        assert now.is_visible() and now.is_enabled()
        assert p.page.locator('#tdPreview').is_visible()
        previews = []

        def preview(route):      # 검토본 저장소는 이 시험 세계에 없다 — 서버 검토본 모양으로 답한다(그 판단 · 그 안 · 그 값)
            body = route.request.post_data_json
            previews.append(body)
            wid = route.request.url.split('/api/todolist/')[1].split('/')[0]
            d = world['book'][body['decision']]
            option = next(o for o in d['options'] if o['id'] == body['option'])
            review = {'id': 'rev-1', 'created': iso(NOW), 'scope': {'decision': d['id'], 'option': option['id'], 'workitem': wid},
                      'snapshot': {**d, 'options': [{**option, 'reviewed_choice': {'parameters': body['parameters']}}]}}
            route.fulfill(status=200, content_type='application/json', body=json.dumps(review, default=str))
        p.page.route('**/decision-preview', preview)
        now.click()
        p.settle()
        assert previews, 'the extra button must send the preview'
        assert p.page.locator('#tdPreviewNow').count() == 0, 'after a fresh preview the extra button goes away'
    finally:
        p.close()


# ---------------------------------------------------------------- P15 서비스 꺼짐
def test_p15_connection_refused_message_is_korean(browser):
    p = FakePortal(browser, {})
    try:
        p.page.route('http://portal.test:8080/**', lambda r: r.abort('connectionrefused'))
        p.open('#/inbox')
        p.page.evaluate("hydApp.selectTab('inbox')")
        p.page.wait_for_function("document.querySelector('#inboxView').innerText.includes('서비스에 연결하지 못했습니다')")
        p.page.evaluate("hydApp.selectTab('instances')")
        p.page.wait_for_function("document.querySelector('#instBanner').innerText.includes('서비스에 연결하지 못했습니다')")
        assert 'Failed to fetch' not in p.page.locator('#inboxView').inner_text() + p.page.locator('#instBanner').inner_text()
    finally:
        p.close()


# ---------------------------------------------------------------- P16 · P17 보류 재평가
def deferred_view():
    wis = [{'id': 'w-agent', 'proc_inst_id': 'inst-1', 'activity_id': 'task:agent', 'activity_name': '에이전트 판단', 'status': 'PENDING', 'agent_orch': 'cliagents', 'agent_mode': 'COMPLETE',
            'user_id': 'agent:judge', 'start_date': iso(NOW), 'generation': 0,
            'draft': {'_deferral': {'id': 'def-1', 'reason': '근거 확인 불가', 'at': iso(NOW), 'assessment': {'status': 'UNKNOWN', 'evidence': {}}}}}]
    return instance(workitems=wis, current=['task:agent'])


def reassess_portal(browser, reply, host):
    h, _ = instance_handlers([deferred_view()], [], {}, moving_projection=False, extra={('POST', '/api/todolist/w-agent/reassess'): reply})
    p = FakePortal(browser, h, host=host)
    open_instances(p)
    p.page.locator('[data-reassess]').wait_for()
    p.page.locator('[data-reassess-by]').fill('김운전')
    p.page.locator('[data-reassess-reason]').fill('다시 봐 주세요')
    return p


def test_p16_refused_reassess_releases_form(browser):
    p = reassess_portal(browser, (409, {'detail': 'task is not waiting for this deferral'}), 'localhost')
    try:
        p.page.locator('[data-reassess]').click()
        p.page.wait_for_function("document.querySelector('[data-deferral-task] .form-msg')")
        assert p.page.locator('[data-reassess]').inner_text() == '다시 평가'
        assert p.page.locator('[data-reassess-by]').is_enabled() and p.page.locator('[data-reassess-reason]').is_enabled()
        assert p.page.evaluate("Object.keys(sessionStorage).filter(k => k.startsWith('hyd:reassess'))") == []
        msg = p.page.locator('[data-deferral-task] .form-msg').inner_text()
        assert 'not waiting' not in msg and '이 보류는 이미 다시 평가됐거나' in msg
        p.page.locator('[data-reassess-reason]').fill('근거를 새로 확인')
        p.page.locator('[data-reassess]').click()
        p.wait_until(lambda: len([x for x in p.posts if x[1].endswith('/reassess')]) >= 2)
        sent = [x[2] for x in p.posts if x[1].endswith('/reassess')]
        assert len(sent) == 2 and sent[1]['reason'] == '근거를 새로 확인' and sent[0]['request_id'] != sent[1]['request_id']
    finally:
        p.close()


def test_p17_insecure_context_buttons_still_send(browser):
    """IP 주소처럼 보안 문맥이 아닌 주소(crypto.randomUUID 없음)에서도 [다시 평가]가 요청을 보내고, 공용 생성기는 v4 형식을 만든다."""
    p = reassess_portal(browser, {'ok': True}, 'portal.test')
    try:
        assert p.page.evaluate('window.isSecureContext') is False
        assert p.page.evaluate('typeof crypto.randomUUID') == 'undefined'
        p.page.locator('[data-reassess]').click()
        p.wait_until(lambda: any(x[1].endswith('/reassess') for x in p.posts))
        sent = [x[2] for x in p.posts if x[1].endswith('/reassess')]
        assert len(sent) == 1 and UUID.match(sent[0]['request_id']), sent
        ids = p.page.evaluate('Array.from({length: 50}, () => UI.uuid())')
        assert all(UUID.match(x) for x in ids) and len(set(ids)) == 50
        assert not [e for e in p.errors if 'randomUUID' in e], p.errors
    finally:
        p.close()


def test_p17_no_direct_random_uuid_calls_left():
    from portal_fake import WWW
    hits = [f'{f.name}:{i}' for f in WWW.glob('*.js') for i, line in enumerate(f.read_text(encoding='utf-8').splitlines(), 1)
            if 'randomUUID()' in line and f.name != 'ui.js']
    assert not hits, hits
