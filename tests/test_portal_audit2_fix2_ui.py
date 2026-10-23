"""포털 검수(.evidence/audit2/portal.md) 2차 수정 — P5 · P12 · P18, 흐름 되돌리기 확인 창, 「조치 전 해소」 결과 보고.

P5 · 확인 창 · 결과 보고는 실제 FastAPI+MemoryRepo(test_portal_approval_ui.Portal) 또는 가짜 API(portal_fake)에 전체 포털 스크립트를 붙여
Chromium 으로 본다. 결함 번호는 검수 문서의 P 번호다.
"""
from datetime import datetime, timedelta, timezone

import pytest

from portal_fake import FakePortal, browser, instance, iso, instance_handlers, todo_row, PEOPLE  # noqa: F401
from test_portal_approval_ui import Portal, approval_clock, pick_me  # noqa: F401
from test_instance_mode import world, _row  # noqa: F401


def open_instances(p, pid='inst-1'):
    p.open(f'#/instances/{pid}')
    p.page.evaluate("hydApp.selectTab('instances')")


# ---------------------------------------------------------------- P5 조치 카드 승인 · 거절에 「나」가 필요
def test_p5_card_without_me_blocks_approve_and_reject_until_me_is_picked(browser, world):
    """「나」가 없으면 자유 입력 승인자(기본 OP-17) 대신 '나 고르기' 안내만 보이고 [승인] · [거절]이 꺼진다.
    「나」(그 승인 역할의 구성원)를 고르면 켜지고, 서버에는 그 사람 id 로 간다."""
    p = Portal(browser, world, 'c3_pm', me=None)
    try:
        p.settle()
        panel = p.page.locator('#todoPanel')
        assert p.page.locator('#tdBy').count() == 0, 'free-text approver field must not be offered without 나'
        hint = panel.locator('[data-pick-me]').inner_text()
        assert '[나 고르기]' in hint and '생산관리자' in hint, hint
        assert p.page.locator('#tdGo').is_disabled() and p.page.locator('#tdRejectCard').is_disabled()
        p.page.evaluate("() => { document.querySelector('#tdGo').click(); document.querySelector('#tdRejectCard').click(); }")
        p.page.wait_for_timeout(300)
        assert p.posts == []
        pick_me(p, 'user:lee-prod')
        assert panel.locator('[data-pick-me]').count() == 0
        assert '이생산' in panel.inner_text()
        assert p.page.locator('#tdGo').is_enabled() and p.page.locator('#tdRejectCard').is_enabled()
        p.page.locator('#tdGo').click()
        p.settle()
        assert len(p.posts) == 1 and p.posts[0][0].endswith('/select')
        assert p.posts[0][1]['by'] == 'user:lee-prod' and p.posts[0][1]['role'] == 'role:prod-mgr'
        assert _row(p.rt, p.inst, 'T_approve')['output']['approval'] == '승인'
        assert not p.errors, p.errors
    finally:
        p.close()


def test_p5_card_me_with_lower_role_is_told_whom_to_pick(browser, world):
    """「나」의 역할(운전원)이 카드의 승인 역할(생산관리자)보다 낮으면 같은 방식으로 막고 안내한다 — 서버로 보내지 않는다."""
    p = Portal(browser, world, 'c3_spare', me='user:kim-op')
    try:
        p.settle()
        assert p.page.locator('#tdGo').is_disabled() and p.page.locator('#tdRejectCard').is_disabled()
        actions = p.page.locator('#todoPanel .form-actions').last.inner_text()
        assert '김운전' in actions and '생산관리자 역할(또는 더 높은 역할)' in actions and '[나 고르기]' in actions, actions
        p.page.evaluate("() => { document.querySelector('#tdGo').click(); document.querySelector('#tdRejectCard').click(); }")
        p.page.wait_for_timeout(300)
        assert p.posts == []
        pick_me(p, 'user:lee-prod')
        assert p.page.locator('#tdGo').is_enabled()
        assert '역할(또는 더 높은 역할)' not in p.page.locator('#todoPanel').inner_text()
    finally:
        p.close()


# ---------------------------------------------------------------- P12 · P18 승인 기한 칩
APPROVE_DEF = {
    'id': 'demo_flow', 'name': '시험 흐름', 'version': '1',
    'activities': [{'id': 'task:approve', 'name': '행사 승인', 'type': 'userTask', 'tool': 'formHandler:approve', 'role': 'operator',
                    'approval': {'key': 'slot', 'options': 'proposal.options', 'recommended': 'proposal.recommended'}},
                   {'id': 'task:done', 'name': '안내 발송', 'type': 'serviceTask', 'tool': 'mail:send', 'role': 'system'}],
    'events': [{'id': 'ev:late', 'name': '승인 지연', 'type': 'boundaryEvent', 'eventDefinition': 'timer', 'timer': 'PT10M',
                'attachedTo': 'task:approve', 'cancelActivity': False}],
    'sequences': [{'id': 's1', 'source': 'task:approve', 'target': 'task:done'}, {'id': 's2', 'source': 'ev:late', 'target': 'task:done'}],
    'gateways': [], 'roles': [{'name': 'operator', 'endpoint': 'role:operator'}]}

SELECT_DEF = {
    'id': 'demo_flow', 'name': '시험 흐름', 'version': '1',
    'activities': [{'id': 'task:select', 'name': '조치 카드 선택 (HITL)', 'type': 'userTask', 'tool': 'formHandler:select_card', 'role': 'operator'},
                   {'id': 'task:escalate', 'name': '상급자 호출', 'type': 'userTask', 'tool': 'formHandler:escalate', 'role': 'operator'}],
    # cancelActivity 를 적지 않은 경계 타이머 = 멈추는 타이머(기준 흐름 anomaly_response_v22 의 ev:select-timeout 과 같다). 「상급자 호출」은 명칭표로 「책임자 확인」
    'events': [{'id': 'ev:select-timeout', 'name': '선택 시간 초과', 'type': 'boundaryEvent', 'eventDefinition': 'timer', 'timer': 'PT10M',
                'attachedTo': 'task:select'}],
    'sequences': [{'id': 'seq:timeout-escalate', 'source': 'ev:select-timeout', 'target': 'task:escalate'}],
    'gateways': [], 'roles': [{'name': 'operator', 'endpoint': 'role:operator'}]}

DEC = {'id': 'dec-1', 'created': '2026-10-23T01:00:00Z', 'state': 'PENDING_APPROVAL', 'asset': 'HYD-01', 'recommended': 'skill:fan',
       'scenario': {'name': '쿨러 성능 저하', 'failureMode': 'fm:cooling-loss', 'cause': 'cause:fin'}, 'origin': {'kind': 'alert', 'incident': 'INC-1'},
       'roles': {'role:operator': {'name': '운전원', 'level': 1}}, 'history': [], 'executions': [], 'explanation': '팬을 올립니다.',
       'options': [{'id': 'skill:fan', 'name': '팬 증속', 'feasible': True, 'score': 1.2, 'approver': {'id': 'role:operator', 'level': 1}, 'actions': []}]}


def timer_portal(browser, defn, task, timer_id, due_s, variables=None):
    now = datetime.now(timezone.utc)
    wis = [dict(task, start_date=iso(now - timedelta(seconds=5)), generation=0),
           {'id': 'inst-1-timer', 'proc_inst_id': 'inst-1', 'activity_id': timer_id, 'activity_name': '타이머', 'status': 'IN_PROGRESS',
            'user_id': 'sys:timer', 'agent_orch': 'system', 'start_date': iso(now - timedelta(seconds=5)), 'due_date': iso(now + timedelta(seconds=due_s)), 'generation': 0}]
    view = instance(workitems=wis, current=[task['activity_id']], variables=variables)
    view['definition'] = defn
    h, _ = instance_handlers([view], [todo_row(task)], {task['id']: task}, moving_projection=False,
                             extra={('GET', '/api/process/definitions/demo_flow'): defn, ('GET', '/api/decisions/dec-1'): DEC})
    return FakePortal(browser, h, me='user:kim-op')


def test_p12_general_approval_deadline_counts_down_as_delay_notice(browser):
    """일반 승인(formHandler:approve)의 기한 칩도 1초마다 줄어들고, 멈추지 않는 타이머라 「지연 알림까지」라고 말한다."""
    task = {'id': 'inst-1-approve', 'proc_inst_id': 'inst-1', 'activity_id': 'task:approve', 'activity_name': '행사 승인', 'status': 'IN_PROGRESS',
            'tool': 'formHandler:approve', 'user_id': 'role:operator',
            'inputs': {'proposal': {'options': [{'slot': '오전 10시', 'reason': '참석 가능', 'score': 1.0}], 'recommended': '오전 10시'}}}
    p = timer_portal(browser, APPROVE_DEF, task, 'ev:late', 40)
    try:
        open_instances(p)
        chip = p.page.locator('#todoPanel [data-approval-until]')
        chip.wait_for()
        first = chip.inner_text()
        assert first.startswith('지연 알림까지') and first.endswith('초'), first
        p.page.wait_for_function("t => document.querySelector('#todoPanel [data-approval-until]').textContent !== t", arg=first, timeout=4000)
        later = chip.inner_text()
        assert int(later.split('까지 ')[1].rstrip('초')) < int(first.split('까지 ')[1].rstrip('초')), (first, later)
        assert not p.errors, p.errors
    finally:
        p.close()


def test_p18_interrupting_timer_says_step_moves_on(browser):
    """멈추는 타이머(cancelActivity 미지정)가 붙은 조치 카드는 「지연 알림까지」가 아니라 기한이 지나면 넘어갈 단계를 말한다."""
    task = {'id': 'inst-1-select', 'proc_inst_id': 'inst-1', 'activity_id': 'task:select', 'activity_name': '조치 카드 선택 (HITL)', 'status': 'IN_PROGRESS',
            'tool': 'formHandler:select_card', 'user_id': 'role:operator', 'inputs': {}}
    p = timer_portal(browser, SELECT_DEF, task, 'ev:select-timeout', 30,
                     variables=[{'key': 'asset', 'value': 'HYD-01'}, {'key': 'decision_id', 'value': 'dec-1'}])
    try:
        open_instances(p)
        chip = p.page.locator('#todoPanel [data-approval-until]')
        chip.wait_for()
        text = chip.inner_text()
        assert '지연 알림' not in text, text
        assert text.startswith('기한까지') and '지나면 「책임자 확인」 단계로 넘어갑니다' in text, text
        assert not p.errors, p.errors
    finally:
        p.close()


# ---------------------------------------------------------------- 기준 흐름으로 되돌리기(process P9: 수업 흐름은 남김, 응답 kept)
DEPLOY_DEFS = [{'id': 'c3_cooling', 'name': '쿨러 대응', 'version': '1'}]
DEPLOY_STATUS = {'id': 'c3_cooling', 'name': '쿨러 대응', 'prod_version': '1', 'history': [],
                 'versions': [{'version': '1', 'deployed': True, 'deployable': True, 'registered_at': None}]}
CLASS_FLOW = {'definition': 'c3_cooling', 'name': '쿨러 대응', 'version': '1', 'patterns': ['COOLER'], 'opens': ['COOLER'], 'shadowed': [], 'class_flow': True}
STUDENT_FLOW = {'definition': 'student_flow', 'name': '학생 흐름', 'version': '1', 'patterns': ['PUMP'], 'opens': ['PUMP'], 'shadowed': [], 'class_flow': False}


def deploy_portal(browser, routes, reset=None):
    h = {('GET', '/api/process/mode'): {'mode': 'instance'}, ('GET', '/api/inbox/users'): PEOPLE,
         ('GET', '/api/process/definitions'): DEPLOY_DEFS, ('GET', '/api/process/definitions/c3_cooling/versions'): DEPLOY_STATUS,
         ('GET', '/api/flows/deployments'): lambda q, b: routes[0]}
    if reset is not None:
        h[('POST', '/api/flows/deploy-reset')] = reset
    p = FakePortal(browser, h)
    p.open('#/admin')
    p.page.evaluate("hydApp.selectTab('admin')")
    p.page.locator('#definitionDeployPanel > summary').click()
    p.page.locator('#deployResetRef').wait_for()
    return p


def test_reset_to_reference_confirm_and_toast_say_class_flows_stay(browser):
    """확인 창은 '학생이 배포한 흐름만 내립니다. 강사가 배포한 수업 흐름은 남습니다'라고 말하고, 응답 kept 의 수업 흐름을 토스트에 보인다."""
    routes = [{'routes': [], 'flows': [CLASS_FLOW, STUDENT_FLOW], 'at_reference': False, 'reset_needed': True, 'reference': {'version': '1', 'changed': False}}]
    after = {'routes': [], 'flows': [CLASS_FLOW], 'at_reference': False, 'reset_needed': False, 'reference': {'version': '1', 'changed': False}}

    def reset(q, body):
        routes[0] = after
        return {'changes': [{'definition': 'student_flow', 'action': 'withdraw'}], 'already_reference': False,
                'kept': [{'definition': 'c3_cooling', 'name': '쿨러 대응', 'version': '1', 'patterns': ['COOLER']}],
                'message': '기준 흐름으로 되돌림 — 1건, 다음 경보부터 적용(열린 처리 건은 자기 판본으로 끝남)', 'routes': after}
    p = deploy_portal(browser, routes, reset)
    try:
        assert p.page.locator('#deployResetRef').is_enabled()
        p.page.locator('#deployBy').fill('학생1')
        p.page.locator('#deployResetRef').click()
        dialog = p.page.locator('dialog.confirm-dialog')
        dialog.wait_for()
        body = dialog.inner_text()
        assert '학생이 배포한 흐름만 내립니다' in body and '강사가 배포한 수업 흐름은 남습니다' in body, body
        assert '내가 배포한 흐름은 경보 경로에서 내리고' not in body
        dialog.locator('button[value=ok]').click()
        p.page.wait_for_function("document.querySelector('#deployMessage').textContent.includes('되돌림')")
        toast = p.page.locator('#deployMessage').inner_text()
        assert '남긴 수업 흐름: 쿨러 대응' in toast, toast
        assert [x for x in p.posts if x[1] == '/api/flows/deploy-reset'][0][2].get('include_class') is None, 'the portal must not withdraw class flows'
        # 남은 것이 수업 흐름뿐이면 되돌릴 것이 없다 — 버튼을 끈다
        assert p.page.locator('#deployResetRef').is_disabled()
        assert not p.errors, p.errors
    finally:
        p.close()


def test_reset_toast_does_not_repeat_kept_names_already_in_server_message(browser):
    routes = [{'routes': [], 'flows': [CLASS_FLOW, STUDENT_FLOW], 'at_reference': False, 'reset_needed': True, 'reference': {'version': '1', 'changed': False}}]
    msg = '기준 흐름으로 되돌림 — 1건 · 강사가 배포한 수업 흐름 1개(쿨러 대응)는 경보 경로에 그대로 남겼습니다'
    p = deploy_portal(browser, routes, {'changes': [{}], 'kept': [{'definition': 'c3_cooling', 'name': '쿨러 대응'}], 'message': msg, 'routes': routes[0]})
    try:
        p.page.locator('#deployBy').fill('학생1')
        p.page.locator('#deployResetRef').click()
        p.page.locator('dialog.confirm-dialog button[value=ok]').click()
        p.page.wait_for_function("document.querySelector('#deployMessage').textContent.includes('되돌림')")
        assert p.page.locator('#deployMessage').inner_text() == msg
    finally:
        p.close()


# ---------------------------------------------------------------- 「조치 전 해소」 · 실제 사유가 실린 결과 보고
BEFORE_ACTION = {'outcome': '조치 전 해소', 'level': 'info', 'verdict': 'info', 'title': 'HYD-01 처리 결과: 조치 전 해소',
                 'summary': '승인 전에 경보가 풀렸습니다(사건: 조치 전 자연 회복). 설비 명령 · 업무 처리 없이 처리 건을 닫았습니다 — 취소한 단계: 승인',
                 'by': 'sys:process', 'values': [], 'facts': {'asset': 'HYD-01'}, 'refs': {}, 'incident_closed': False,
                 'incident_state': 'RESOLVED_WITHOUT_ACTION', 'incident_reason': None, 'end_event': 'incident-ended-before-action'}
PLC_CAUSE = '설비 명령이 PLC 에서 거절됐습니다(사유 MODE_LOCAL) — 명령이 실행되지 않아 재관측하지 않았습니다. 운전 모드 · 인터록을 확인하세요'
ESCALATED = {'outcome': '미달', 'level': 'fail', 'verdict': 'fail', 'title': 'HYD-01 처리 결과: 미달', 'summary': PLC_CAUSE,
             'template_summary': '재관측 기준 미달 — 책임자 확인이 필요합니다', 'by': 'sys:process', 'values': [], 'facts': {'incident_reason': 'PLC REJECTED: MODE_LOCAL'},
             'refs': {}, 'cause': {'incident_state': 'ESCALATED', 'reason': 'PLC REJECTED: MODE_LOCAL', 'text': PLC_CAUSE, 'reobserved': False}}


@pytest.mark.parametrize('report, end_event, cause', [(BEFORE_ACTION, 'incident-ended-before-action', '승인 전에 경보가 풀렸습니다'),
                                                      (ESCALATED, 'E_fail', 'PLC 에서 거절됐습니다')])
def test_result_report_shows_actual_cause(browser, report, end_event, cause):
    """결과 보고가 실제 사유(조치 전 해소 · PLC 거절)를 보이고, 흐름의 보고 틀 문구(재관측 미달)를 사유처럼 보이지 않는다."""
    view = instance(status='COMPLETED', current=[], workitems=[],
                    variables=[{'key': 'asset', 'value': 'HYD-01'}, {'key': 'result_report', 'value': report}])
    view['instance'].update(end_event=end_event, end_date=iso(datetime.now(timezone.utc)))
    h, _ = instance_handlers([view], [], {}, moving_projection=False)
    p = FakePortal(browser, h)
    try:
        open_instances(p)
        p.page.locator('[data-inst-tab="result"]').click()
        card = p.page.locator('[data-pane="result"] .rr-card')
        card.wait_for()
        text = card.inner_text()
        assert cause in text, text
        assert report['outcome'] in card.locator('.rr-badge').inner_text()
        assert '재관측 기준 미달' not in text, text
        if end_event == 'incident-ended-before-action':
            assert '조치 전 해소' in p.page.locator('#instList').inner_text()
            assert 'incident-ended' not in p.page.locator('#view-instances').inner_text()
        assert not p.errors, p.errors
    finally:
        p.close()
