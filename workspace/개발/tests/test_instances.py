"""처리 건 런타임(procsvc/instances.py) — 수업 흐름을 처음부터 끝까지 실제 엔진 · 실제 DB · 실제 서비스로 돌린다(conftest 머리말의 구성 표).

경보 접수 → 처리 건 → 에이전트 단계(실제 워커 · 재생) → 사람 승인(API 와 같은 함수 — 실제 agent 의 승인 현재 조건 검사) → 설비 명령 · ACK →
재관측 → 작업지시 · 발주 · 입고(실제 enterprise-sim) → 결과 보고까지 그대로다.
"""
import threading
import uuid

import psycopg
import pytest

from hydcommon import schemas, topics

from conftest import COOLING, OPERATOR, RecordedCli, definition_version as _version, recording

MAINT = dict(by='user:park-maint', role='role:maint-mgr')
BUYER = dict(by='user:jung-buy', role='role:purchasing')
WINDOW_S = 15 * 60 / 20          # 재관측 창 = 15 시뮬레이션 분 ÷ 배속 20


# ---------------------------------------------------------------- 흐름 A (냉각 c3_cooling)
def _report(world, pid):
    inst = world.inst(pid)
    assert inst['status'] == 'COMPLETED', [(w['activity_id'], w['status'], (w.get('log') or '')[-200:]) for w in world.rows(pid)]
    return world.values(pid)['result_report']


def test_냉각_흐름A는_승인_명령_재관측_작업지시를_거쳐_정상으로_끝난다(world):
    alert, pid, decision = world.start_cooling()
    world.approve(pid, decision, 'skill:sop-cool-11', OPERATOR)
    cmd = world.commanded(pid)
    assert cmd['actions'] == [{'code': 'FAN_SET', 'fan_pct': 100}] and cmd['asset'] == 'HYD-01'
    ledger = world.kafka.of(topics.K_AUDIT)
    assert any(e.get('detail', {}).get('cmdId') == cmd['cmdId'] for e in ledger if e.get('event') == schemas.CMD_APPROVAL_LEDGER_EVENT), \
        '명령보다 먼저 승인 원장이 실려야 한다'
    world.ack('HYD-01', cmd['cmdId'])
    assert world.row(pid, 'T_reobs', 'SUBMITTED')['due_date'], '재관측 창의 마감이 행에 저장돼야 한다'
    world.tag('HYD-01', 'TS1', 50.0)
    world.clear_alert(alert)
    world.clock.advance(WINDOW_S + 1)
    world.poll()
    report = _report(world, pid)
    assert report['outcome'] == '정상' and report['refs'].get('work_order')
    assert world.incident(pid).state == 'CLOSED'


PEOPLE = {'role:operator': OPERATOR, 'role:prod-mgr': dict(by='user:lee-prod', role='role:prod-mgr'), 'role:maint-mgr': MAINT}


@pytest.mark.parametrize('sop, commanded, recovered, outcome, state', [
    ('skill:sop-cool-11', True, True, '정상', 'CLOSED'),        # 명령만(팬 최대) → 명령 → 재관측 → 작업지시
    ('skill:sop-cool-13', True, True, '정상', 'CLOSED'),        # 명령 + 작업지시(부하 70 % · 야간 세척) → 같은 길
    ('skill:sop-cool-14', False, True, '정상', 'CLOSED'),       # 작업지시만(정지 · 세척) → 작업지시 → 정비 수행 → 재관측 회복
    ('skill:sop-cool-14', False, False, '미달', 'ESCALATED'),   # 정비 뒤에도 회복하지 않으면 명령 갈래의 비회복과 같은 미달 · 책임자 확인
], ids=['명령만', '명령 + 작업지시', '작업지시만 · 회복', '작업지시만 · 미회복'])
def test_냉각_흐름A는_승인한_카드의_조치_종류로_길을_갈라_회복을_확인한_뒤_끝난다(world, sop, commanded, recovered, outcome, state):
    """메인 결정(2026-10-31): 흐름 A 는 승인한 카드의 실제 조치 종류(chosen_skill_kind)로 가른다 — 작업지시만인 카드(SOP-COOL-14)도
    정비 수행 뒤 명령 갈래와 같은 재관측(15 설비 분)으로 회복을 확인한다(HM-8.6 · SOP-COOL-14 「재가동 후 확인」 — 전에는 작업지시만 내고
    회복 확인 없이 종결로 닫았다, FA1 검증 §4-2). 승인자는 그 카드가 요구하는 역할의 사람."""
    alert, pid, decision = world.start_cooling()
    card = next(o for o in world.main.book[decision]['options'] if o['id'] == sop)
    world.approve(pid, decision, sop, PEOPLE[card['approver']['id']])
    assert world.values(pid)['chosen_skill_kind'] == ('control' if commanded else 'work_order')
    if commanded:
        world.ack('HYD-01', world.commanded(pid)['cmdId'])
    world.poll(3)                                                   # 작업지시만: 작업지시 → 정비 수행 → 재관측 시작
    assert world.row(pid, 'T_reobs' if commanded else 'T_reobs_wo')['status'] != 'DONE', '재관측이 시작되기 전이나 회복 값을 넣기 전에 끝났다'
    world.tag('HYD-01', 'TS1', 50.0 if recovered else 60.0)
    if recovered:
        world.clear_alert(alert)
    world.clock.advance(WINDOW_S + 1)
    world.poll(3)
    report = _report(world, pid)
    assert (report['outcome'], bool(report['refs'].get('work_order'))) == (outcome, True), report
    assert bool(world.kafka.of(topics.K_CMD)) is commanded
    assert world.incident(pid).state == state


@pytest.mark.parametrize('actions, kind', [
    ([{'kind': 'command', 'code': 'FAN_SET'}], 'control'),
    ([{'kind': 'command', 'code': 'LOAD_SET'}, {'kind': 'work_order', 'code': 'WO_CREATE'}], 'control'),
    ([{'kind': 'work_order', 'code': 'WO_CREATE'}], 'work_order'),
    ([{'kind': 'transaction', 'code': 'WO_RESCHEDULE'}], 'work_order'),
    ([{'kind': 'transaction', 'code': 'PR_CREATE'}], 'purchase'),
    ([], 'other'),
    ([{'kind': 'transaction', 'code': 'EMAIL_SEND'}], 'other'),
], ids=['명령만', '명령 + 작업지시', '작업지시', '정비 일정 변경', '발주', '조치 없음', '모르는 코드'])
def test_승인한_카드의_조치_종류는_실제_조치로_정하고_모르면_다른_종류로_짐작하지_않는다(actions, kind):
    from procsvc.instances import action_kind
    assert action_kind({'actions': actions}) == kind


def test_냉각_흐름A에서_운전원이_거절하면_명령_없이_반려로_끝난다(world):
    alert, pid, decision = world.start_cooling()
    approve = world.row(pid, 'T_approve', 'IN_PROGRESS')
    world.rt.reject_card(approve['id'], decision, reason='현장 확인 뒤 다시 판단', **OPERATOR)
    report = _report(world, pid)
    assert report['outcome'] == '반려' and '현장 확인 뒤 다시 판단' in report['summary']
    assert world.kafka.of(topics.K_CMD) == [], '거절이면 설비 명령을 내지 않는다'
    assert world.incident(pid).state == 'REJECTED_BY_OPERATOR'
    assert world.main.book[decision]['state'] == 'REJECTED'


def test_승인_지연_알림은_벽시계_10분에_울리고_배속을_곱하지_않는다(world):
    """#2: 사람이 읽고 고르는 시간은 벽시계다. 전에는 PT10M ÷ 20 = 30초에 「승인 지연」 보고 · 알림이 났다."""
    alert, pid, decision = world.start_cooling()
    timer = world.row(pid, 'B_overdue', 'IN_PROGRESS')
    world.clock.advance(31)
    world.poll()
    assert world.row(pid, 'B_overdue')['status'] == 'IN_PROGRESS', '30초 만에 승인 지연이 울리면 안 된다(20배속을 곱한 것)'
    world.clock.advance(10 * 60)
    world.poll()
    assert world.row(pid, 'T_notice')['status'] == 'DONE', '벽시계 10분이 지나면 승인 지연을 알린다'
    assert any(e['event'] == 'TIMER_FIRED' and e['detail']['event'] == 'B_overdue' for e in world.main.audit_log), \
        'A-08: 타이머 발화는 TIMER_FIRED + 이벤트 id 로 남는다'
    assert world.row(pid, 'B_overdue')['id'] == timer['id'] and world.row(pid, 'B_overdue')['status'] == 'DONE'
    world.approve(pid, decision, 'skill:sop-cool-11', OPERATOR)     # 알림 타이머는 멈추지 않는 타이머 — 알림 뒤에도 승인할 수 있다
    assert world.incident(pid).state == 'AWAITING_ACK'


def test_재관측에서_회복하지_않으면_미달로_끝나고_사건은_완화_실패다(world):
    alert, pid, decision = world.start_cooling()
    world.approve(pid, decision, 'skill:sop-cool-11', OPERATOR)
    world.ack('HYD-01', world.commanded(pid)['cmdId'])
    world.tag('HYD-01', 'TS1', 61.0)                                     # 기준(55 ℃) 밖, 경보도 그대로
    world.clock.advance(WINDOW_S + 1)
    world.poll()
    report = _report(world, pid)
    assert report['outcome'] == '미달'
    inc = world.incident(pid)
    assert (inc.state, inc.reason) == ('ESCALATED', 'MITIGATION_FAILED')


def test_재관측_값이_기준_안인데_경보가_아직이면_창을_세_번까지_늘린다(world):
    alert, pid, decision = world.start_cooling()
    world.approve(pid, decision, 'skill:sop-cool-11', OPERATOR)
    world.ack('HYD-01', world.commanded(pid)['cmdId'])
    world.tag('HYD-01', 'TS1', 52.0)
    for extension in (1, 2, 3):
        world.clock.advance(WINDOW_S + 1)
        world.poll()
        assert world.row(pid, 'T_reobs')['draft']['reobserve']['extensions'] == extension
        assert world.incident(pid).reobs_extensions == extension
    world.clear_alert(alert)
    world.clock.advance(WINDOW_S)
    world.poll()
    assert _report(world, pid)['outcome'] == '정상'


def test_ACK가_마감까지_안_오면_ACK_시간_초과로_사람_검토에_넘긴다(world):
    alert, pid, decision = world.start_cooling()
    world.approve(pid, decision, 'skill:sop-cool-11', OPERATOR)
    world.commanded(pid)
    world.clock.advance(20)
    world.poll()
    assert world.incident(pid).state == 'AWAITING_ACK', '마감 전에는 기다린다'
    world.clock.advance(11)
    world.poll(2)
    inc = world.incident(pid)
    assert (inc.state, inc.reason) == ('ESCALATED', 'ACK_TIMEOUT')
    report = _report(world, pid)
    assert report['outcome'] == '미달' and 'ACK' in report['summary']


def test_명령_송신이_실패하면_다시_보내지_않고_사람_검토로_넘기며_실패를_기록한다(world):
    """A-07: 승인 원장 · 명령의 Kafka 송신 결과를 기다린다. 실패하면 30초 뒤 「ACK 없음」으로 보이지 않고 그 자리에서 사유가 남는다."""
    alert, pid, decision = world.start_cooling()
    world.kafka.fail.add(topics.K_CMD)
    world.approve(pid, decision, 'skill:sop-cool-11', OPERATOR)
    inc = world.incident(pid)
    assert (inc.state, inc.reason) == ('ESCALATED', 'CMD_SEND_FAILED')
    errors = [e for e in world.events(pid) if e['event_type'] == 'error' and e['job_id'] == 'TASK_ERROR']
    assert errors and '명령 통로' in errors[-1]['data']['friendly'], 'A-06: 실패 기록에 학생이 읽을 문장이 있다'
    world.kafka.fail.clear()
    world.poll(2)
    report = _report(world, pid)
    assert report['outcome'] == '미달' and '명령 통로' in report['summary']
    assert len([v for t, _, v in world.kafka.sent if t == topics.K_CMD]) == 0, '실패한 명령을 다시 보내지 않는다'


# ---------------------------------------------------------------- 도중 재시작
def test_재관측_중_process가_다시_켜져도_저장한_마감으로_회복을_판정한다(world):
    """A-02(실행으로 재현된 결함): 전에는 재시작이 재관측 중 사건을 무조건 ESCALATED/PROCESS_RESTART_REVIEW 로 바꿔 「미달」로 끝났다."""
    alert, pid, decision = world.start_cooling()
    world.approve(pid, decision, 'skill:sop-cool-11', OPERATOR)
    world.ack('HYD-01', world.commanded(pid)['cmdId'])
    world.restart()
    assert world.incident(pid).state == 'RE_OBSERVING', '재관측은 읽기라 재시작이 결과를 바꾸지 않는다'
    world.tag('HYD-01', 'TS1', 49.5)
    world.clear_alert(alert)
    world.clock.advance(WINDOW_S + 1)
    world.poll()
    assert _report(world, pid)['outcome'] == '정상'
    assert world.incident(pid).state == 'CLOSED'


def test_ACK_대기_중_process가_다시_켜지면_사람_검토로_넘긴다(world):
    """ACK 대기만은 명령이 실행됐는지 알 수 없어 사람 검토다 — 결과 보고가 그 사유를 쉬운 말로 싣는다."""
    alert, pid, decision = world.start_cooling()
    world.approve(pid, decision, 'skill:sop-cool-11', OPERATOR)
    world.commanded(pid)
    world.restart()
    inc = world.incident(pid)
    assert (inc.state, inc.reason) == ('ESCALATED', 'PROCESS_RESTART_REVIEW')
    world.clock.advance(31)
    world.poll(2)
    report = _report(world, pid)
    assert report['outcome'] == '미달' and 'process 가 다시 시작돼' in report['summary']


def test_AI_단계_중_process가_다시_켜져도_워커의_결과로_이어_간다(world):
    alert, pid = world.raise_alert(*COOLING)
    world.restart()
    decision = world.agent(pid, 'T_agent')
    assert world.row(pid, 'T_approve')['status'] == 'IN_PROGRESS'
    world.approve(pid, decision, 'skill:sop-cool-11', OPERATOR)
    assert world.incident(pid).state == 'AWAITING_ACK'


def test_승인_대기_중_process가_다시_켜져도_승인하면_명령이_나간다(world):
    alert, pid, decision = world.start_cooling()
    world.restart()
    world.approve(pid, decision, 'skill:sop-cool-11', OPERATOR)
    world.ack('HYD-01', world.commanded(pid)['cmdId'])
    world.tag('HYD-01', 'TS1', 50.0)
    world.clear_alert(alert)
    world.clock.advance(WINDOW_S + 1)
    world.poll()
    assert _report(world, pid)['outcome'] == '정상'


# ---------------------------------------------------------------- 승인자 규칙 (A-04)
@pytest.mark.parametrize('who, error', [
    (dict(by='승인자', role='role:operator'), '사람 사용자'),          # 자유 글 승인자 — 전에는 카드 승인만 받아 줬다
    (dict(by='OP-17', role='role:operator'), '사람 사용자'),
    (dict(by='user:park-maint', role='role:operator'), '역할이 아니어서'),  # 사람이지만 그 역할의 구성원이 아님
])
def test_조치_카드_승인은_그_역할의_사람_사용자만_할_수_있다(world, who, error):
    alert, pid, decision = world.start_cooling()
    with pytest.raises(PermissionError, match=error):
        world.approve(pid, decision, 'skill:sop-cool-11', who)
    approve = world.row(pid, 'T_approve')
    with pytest.raises(PermissionError, match=error):
        world.rt.reject_card(approve['id'], decision, reason='사유', **who)
    assert world.row(pid, 'T_approve')['status'] == 'IN_PROGRESS'


# ---------------------------------------------------------------- 바깥 응답과 처리 건 잠금 (A-05)
def _in_thread(fn):
    """fn 을 다른 스레드에서 돌린다 — (스레드, 결과 {'ok' | 'error'})."""
    result = {}

    def run():
        try:
            result['ok'] = fn()
        except Exception as e:  # noqa: BLE001 — 결과로 확인한다
            result['error'] = e
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread, result


def _same_case_write(world, pid):
    """같은 처리 건 잠금을 잡는 다른 일 하나(워커 결과 저장 · 임대 갱신과 같은 길 — 작업 행 쓰기는 처리 건 행을 먼저 잠근다)."""
    row = world.row(pid, 'T_approve')
    world.rt.repo.update_workitem({'id': row['id'], 'log': (row.get('log') or '') + 'same-case write; '})
    return True


@pytest.mark.parametrize('call', ['approve', 'preview'])
def test_agent_응답을_기다리는_동안_같은_처리_건의_다른_일은_줄_서지_않는다(world, call):
    """A-05 · P1-04: 전에는 승인 현재 조건 검사 · [새 예측 검토](agent 최대 20초)를 처리 건 잠금 안에서 기다려, 그 사이 같은 처리 건의 워커 결과
    저장 · 임대 갱신이 멈췄다. agent 를 실제로 얼려 둔 채 같은 처리 건에 쓴다."""
    alert, pid, decision = world.start_cooling()
    approve = world.row(pid, 'T_approve', 'IN_PROGRESS')
    with world.stack.services['agent'].paused() as slow:
        if call == 'approve':
            thread, result = _in_thread(lambda: world.approve(pid, decision, 'skill:sop-cool-11', OPERATOR))
        else:
            thread, result = _in_thread(lambda: world.rt.preview_choice(approve['id'], decision, 'skill:sop-cool-11', {'fan_pct': 90}))
        slow.wait_client()
        writer, wrote = _in_thread(lambda: _same_case_write(world, pid))
        writer.join(10)
        assert wrote.get('ok'), f'agent 가 답할 때까지 같은 처리 건의 다른 일이 기다렸다: {wrote}'
    thread.join(60)
    assert 'error' not in result, result


def test_승인_검사를_기다리는_사이_다른_사람이_먼저_승인하면_두_번째_승인은_받지_않는다(world):
    alert, pid, decision = world.start_cooling()
    with world.stack.services['agent'].paused() as slow:
        runs = [_in_thread(lambda: world.approve(pid, decision, 'skill:sop-cool-11', OPERATOR)) for _ in range(2)]
        slow.wait_client()
    for thread, _ in runs:
        thread.join(60)
    results = [r for _, r in runs]
    assert sum('ok' in r for r in results) == 1, results
    refused = next(r['error'] for r in results if 'error' in r)
    assert isinstance(refused, ValueError) and '이미 처리된 승인' in str(refused), results
    assert len(world.events(pid, job='APPROVAL_ACCEPTED')) == 1, '승인 접수는 한 번'


# ---------------------------------------------------------------- 흐름 B (정기 정비 c3_pm) · C (예비품 구매 c3_spare)
def _button(world, key, person):
    """포털 결함 실험 [정기 점검] · [재고 보충]과 같은 함수로 지금 업무 값의 경보를 만든다(초기화 뒤)."""
    from procsvc import scenario_buttons
    world.main._entsim_post(*scenario_buttons.SCENARIOS[key]['reset'])
    prep = scenario_buttons.prepare(key, world.instance_mode.enterprise_read, world.rt, world.main._scenario_route,
                                    scenario_buttons.who(person))
    receipt = world.receive(topics.K_ALERTS, prep['alert'])
    assert receipt['status'] == 'HANDLED', receipt
    return prep['alert'], receipt['result']['instance']


def test_정기_정비_흐름B는_승인하면_정비_오더와_생산팀_공지를_내고_정상으로_끝난다(world):
    alert, pid = _button(world, 'B', dict(by='박정비', user_id='user:park-maint', roles=['role:maint-mgr']))
    assert world.inst(pid)['proc_def_id'] == 'c3_pm'
    decision = world.agent(pid, 'T_agent')
    sent = len(world.stack.smtp.messages)
    world.approve(pid, decision, world.main.book[decision]['recommended'], MAINT)
    report = _report(world, pid)
    assert report['outcome'] == '정상' and report['refs']['work_order'].startswith('WO-')
    mails = world.stack.smtp.messages[sent:]
    assert len(mails) == 1 and 'production@hyd.local' in mails[0], '정비 공지 메일 한 통'


def test_정기_정비_흐름B에서_거절하면_정비_오더_없이_반려로_끝난다(world):
    alert, pid = _button(world, 'B', dict(by='박정비', user_id='user:park-maint', roles=['role:maint-mgr']))
    decision = world.agent(pid, 'T_agent')
    approve = world.row(pid, 'T_approve', 'IN_PROGRESS')
    world.rt.reject_card(approve['id'], decision, reason='이번 주는 생산 우선', **MAINT)
    report = _report(world, pid)
    assert report['outcome'] == '반려' and 'work_order' not in report['refs']


def test_예비품_구매_흐름C는_승인하면_발주_입고까지_하고_구매팀장에게도_알린다(world):
    alert, pid = _button(world, 'C', dict(by='정구매', user_id='user:jung-buy', roles=['role:purchasing']))
    assert world.inst(pid)['proc_def_id'] == 'c3_spare'
    decision = world.agent(pid, 'T_agent')
    world.approve(pid, decision, world.main.book[decision]['recommended'], BUYER)
    report = _report(world, pid)
    values = world.values(pid)
    assert report['outcome'] == '입고 완료' and report['refs']['purchase_order'].startswith('PR-') and values['received'] is True
    assert values['approved_amount'] > 300
    notes = world.rt.repo.list_notifications('hyd', ['user:han-buymgr', 'role:purchasing-mgr'])
    assert any('재고 보충 결과' in n['title'] for n in notes), '금액이 전결 기준(300만원)을 넘으면 구매팀장에게도 알린다'


def test_예비품_구매_흐름C에서_거절하면_발주하지_않는다(world):
    alert, pid = _button(world, 'C', dict(by='정구매', user_id='user:jung-buy', roles=['role:purchasing']))
    decision = world.agent(pid, 'T_agent')
    approve = world.row(pid, 'T_approve', 'IN_PROGRESS')
    world.rt.reject_card(approve['id'], decision, reason='다음 달 예산으로', **BUYER)
    report = _report(world, pid)
    assert report['outcome'] == '반려' and 'purchase_order' not in report['refs']


# ---------------------------------------------------------------- 교대 인수인계 (제공 정의 shift_handover · 가져온 ShiftHandover)
SENDER, RECEIVER = 'user:kim-op', 'user:choi-op'
FIRST, REVISION = '인계안 작성', '인계안 작성 · 보완 1'


def _start_handover(world, definition='shift_handover', version=None):
    version = version or _version('shift_handover_v1.json')
    inputs = recording('handover/draft-1')['runs'][-1]['context']['inputs']
    inst = world.rt.start_definition(definition, version, 'handover:' + uuid.uuid4().hex,
                                     values={k: inputs[k] for k in ('asset', 'shift_label', 'as_of', 'work_notes')})
    return inst['proc_inst_id']


def _human(world, pid, activity, by, output):
    row = world.row(pid, activity, 'IN_PROGRESS')
    return world.rt.submit_human(row['id'], output, by)


def _draft(world, pid, activity, cli=None):
    """AI 초안 단계를 끝까지: process 검사가 결과를 돌려보내면(「거절 n/상한」 — 에이전트 재작업) 워커가 다시 잡는다(키 없는 PC 는 녹화된
    고친 답, 넘김 FG 1344). 상한(instances.InstanceRuntime.CORRECTION_ROUNDS) 안에서 끝나야 한다 — 상한이면 사람 확인으로 멈춘 것이라 실패."""
    from procsvc.instances import InstanceRuntime
    for _ in range(InstanceRuntime.CORRECTION_ROUNDS):
        world.agent(pid, activity, cli=cli)
        row = world.row(pid, activity)
        if row['status'] == 'DONE' or row.get('draft_status') != 'FB_REQUESTED':
            break
    assert row['status'] == 'DONE', (row['status'], row.get('draft_status'), row.get('log'))


@pytest.mark.parametrize('revisions, end', [(0, 'ev:confirmed'), (1, 'ev:confirmed'), (2, 'ev:confirmed'), (3, 'ev:followup')])
def test_교대_인수인계는_보완_요청을_두_번까지_받고_세_번째는_후속_확인으로_끝난다(world, revisions, end):
    """보완 0 · 1 · 2번은 인수 확인으로 끝나고, 2번을 넘기면(세 번째 보완 요청) 「후속 확인 필요 · 인수 미확정」 끝 이벤트로 끝난다.
    보완 2번째 초안(task:draft-r3)은 녹화가 없어(키 없는 PC 에서는 멈춘다 — 확정 방향 2-5) 키 있는 PC 길(CLI 자리 · 관문)로 보완 1 녹화를 낸다."""
    pid = _start_handover(world)
    rounds = [('task:draft', 'task:sender', 'task:receiver', None), ('task:draft-r2', 'task:sender-r2', 'task:receiver-r2', None),
              ('task:draft-r3', 'task:sender-r3', 'task:receiver-r3', 'handover/draft-2')]
    for n, (draft, sender, receiver, keyed) in enumerate(rounds):
        _draft(world, pid, draft, RecordedCli(recording(keyed)['runs'][0]) if keyed else None)
        if n == revisions:
            _human(world, pid, sender, SENDER, {'sender_decision': 'approve', 'sender_notes': '확인 사항을 전달합니다'})
            _human(world, pid, receiver, RECEIVER, {'receiver_decision': 'confirm', 'receiver_notes': '확인했습니다', 'communication_only': True})
            break
        _human(world, pid, sender, SENDER, {'sender_decision': 'revise', 'sender_notes': f'보완 {n + 1}: 작업지시와 재고를 다시 대조'})
    inst = world.inst(pid)
    assert (inst['status'], inst['end_event']) == ('COMPLETED', end), [(w['activity_id'], w['status']) for w in world.rows(pid)]


def test_가져온_교대_흐름_ShiftHandover도_같은_규칙으로_끝까지_돈다(world):
    """학생이 bpmn.io 로 가져오는 제공 교대 그림(course_policy.HANDOVER) — 흐름 가져오기 · 등록과 같은 서버 길로 등록해 처음부터 끝까지."""
    from procsvc.course_policy import HANDOVER as handover
    version = world.import_flow('ShiftHandover', handover['xml'], handover['mapping'], 'shift-handover.bpmn')
    pid = _start_handover(world, 'ShiftHandover', version)
    _draft(world, pid, 'task_draft')
    _human(world, pid, 'task_sender', SENDER, {'sender_decision': 'approve', 'sender_notes': '전달'})
    _human(world, pid, 'task_receiver', RECEIVER, {'receiver_decision': 'confirm', 'receiver_notes': '확인', 'communication_only': True})
    inst = world.inst(pid)
    assert inst['status'] == 'COMPLETED' and inst['end_event']


# ---------------------------------------------------------------- 폴링이 하는 일 (B-2 · A-03 · B-4 · B-11)
def _consumer_and_outbox(world, pid, activity):
    import psycopg
    row = world.row(pid, activity)
    with psycopg.connect(world.dsn) as db:
        n = db.execute('SELECT count(*) FROM execution_projection_outbox WHERE proc_inst_id=%s', (pid,)).fetchone()[0]
    return row['consumer'], row['updated_at'] if 'updated_at' in row else None, n


def test_마감이_남은_대기_행은_폴링이_다시_집지_않는다(world):
    """B-2(하-08): 전에는 ACK · 재관측을 기다리는 행을 2초마다 다시 집어 담당 표식을 새로 쓰고, 그때마다 그래프 반영 대기열에 한 줄씩 쌓였다."""
    alert, pid, decision = world.start_cooling()
    world.approve(pid, decision, 'skill:sop-cool-11', OPERATOR)
    world.ack('HYD-01', world.commanded(pid)['cmdId'])
    world.rt.reconcile_projections(limit=200)
    before = _consumer_and_outbox(world, pid, 'T_reobs')
    world.clock.advance(10)
    world.poll(5)
    assert _consumer_and_outbox(world, pid, 'T_reobs') == before


def test_사람_검토_대기열_처리_건은_끝난_사건_정리가_매번_고르지_않는다(world):
    """A-03: 회복 기준이 없는 경보는 처음부터 사건이 끝난(에스컬레이션) 사람 검토 처리 건이다. 전에는 매 폴링이 그 처리 건의 잠금을 잡고
    아무것도 하지 않은 채 「바꿈 1」로 셌다."""
    alert, pid = world.raise_alert('UNKNOWN_PATTERN_TEST', 'HYD-02')
    assert world.inst(pid)['proc_def_id'] == 'alert_triage' and world.incident(pid).state == 'ESCALATED'
    assert world.rt.reconcile_terminal_incidents() == 0
    assert world.row(pid, 'task:triage')['status'] == 'IN_PROGRESS'


def test_커밋_뒤_효과가_실패하면_처리_건_기록에_쉬운_말로_남는다(world):
    """B-4(하-09): 전에는 커밋 뒤 효과(알림 · 판단 원문 기록 · 감사)의 실패가 로그 한 줄로만 삼켜졌다."""
    with world.storage_fails('notifications', 'true'):
        alert, pid, decision = world.start_cooling()
    failures = world.events(pid, job='POST_COMMIT_EFFECT_FAILED')
    assert failures and '담당자 알림' in failures[-1]['data']['friendly']
    assert world.row(pid, 'T_approve')['status'] == 'IN_PROGRESS', '효과가 실패해도 이미 커밋한 진행은 그대로'


def test_처리_건_하나의_대기_행이_실패해도_같은_바퀴의_다른_처리_건은_진행한다(world):
    """B-11: 전에는 대기 행 처리(reconcile_services)의 소유 전이에 처리 건 단위 try 가 없어, 한 처리 건의 예외가 폴링 한 바퀴를 멈췄다."""
    runs = []
    for _ in range(2):
        alert, pid, decision = world.start_cooling()
        world.approve(pid, decision, 'skill:sop-cool-11', OPERATOR)
        world.ack('HYD-01', world.commanded(pid)['cmdId'])
        world.clear_alert(alert)
        runs.append((pid, world.row(pid, 'T_reobs')['id']))
    world.tag('HYD-01', 'TS1', 50.0)
    first, second = sorted(runs, key=lambda r: r[1])                # 폴링은 행 id 순서로 돈다 — 앞 처리 건을 실패시킨다
    world.clock.advance(WINDOW_S + 1)
    with world.storage_fails('todolist', f"NEW.id = '{first[1]}' AND NEW.consumer IS DISTINCT FROM OLD.consumer"):
        world.poll()
        assert world.inst(second[0])['status'] == 'COMPLETED'
        world.poll()                                                # 같은 실패가 한 번 더
    failures = world.events(first[0], job='ENGINE_STEP_FAILED')
    assert len(failures) == 1 and '다시 시도합니다' in failures[-1]['data']['friendly'], \
        'P1-28: 같은 실패가 그 처리 건의 마지막 기록이면 2초마다 다시 쌓지 않는다(기록은 처리 건 기록에서 판정)'
    world.poll()
    assert world.inst(first[0])['status'] == 'COMPLETED', '저장소가 돌아오면 다음 바퀴에 이어 간다'


# ---------------------------------------------------------------- 지는 대안 · 연장 한도 (G5b-13)
def test_추천이_아닌_카드를_승인하면_그_카드의_조치로_간다(world):
    """G5b-13: 전에는 흐름 A 가 늘 추천 카드만 승인했다 — 지는 대안을 고른 학생의 길은 시험에 없었다."""
    alert, pid, decision = world.start_cooling()
    d = world.main.book[decision]
    alternative = next(o for o in d['options'] if o['id'] != d['recommended'] and o.get('feasible')
                       and o['approver']['id'] in (OPERATOR['role'],) and o.get('executable') is not False)
    world.approve(pid, decision, alternative['id'], OPERATOR)
    assert world.values(pid)['chosen_option']['id'] == alternative['id'] and world.main.book[decision]['override'] is True
    commands = [a for a in alternative.get('actions') or [] if a.get('kind') == 'command']
    if commands:
        assert [a['code'] for a in world.commanded(pid)['actions']] == [a['code'] for a in commands]
    else:
        assert world.kafka.of(topics.K_CMD) == [], '설비 명령이 없는 카드는 명령을 내지 않는다'


def test_재관측_창을_세_번_늘려도_경보가_그대로면_미달로_끝난다(world):
    alert, pid, decision = world.start_cooling()
    world.approve(pid, decision, 'skill:sop-cool-11', OPERATOR)
    world.ack('HYD-01', world.commanded(pid)['cmdId'])
    world.tag('HYD-01', 'TS1', 52.0)                                     # 값은 기준 안, 경보는 끝까지 그대로
    for _ in range(4):
        world.clock.advance(WINDOW_S + 1)
        world.poll()
    assert _report(world, pid)['outcome'] == '미달'
    assert (world.incident(pid).state, world.incident(pid).reason, world.incident(pid).reobs_extensions) == ('ESCALATED', 'MITIGATION_FAILED', 3)


# ---------------------------------------------------------------- H-10 · P1-01 · P1-15 · P1-08 멈춘 AI 단계 → 사람이 닫으면 사건도 닫힌다
def _pump_case(world):
    """수업 단계에서 펌프 누설 경보(기준 흐름 anomaly_response) — 펌프 진단 AI 단계는 수업 밖이라 워커가 실행하지 않고 실패로 남는다."""
    world.plant.inject('HYD-01', 'pump_leakage', severity='high')
    world.settle(1800)
    alert, pid = world.raise_alert('PUMP_LEAKAGE', 'HYD-01')
    assert world.inst(pid)['proc_def_id'] == 'anomaly_response'
    world.report()
    world.runner('replay').poll_once()
    return alert, pid


def test_실패한_AI_단계의_처리_건은_멈춤으로_보이고_사람이_닫으면_사건도_책임자_확인으로_닫힌다(world):
    """H-10: 전에는 실패 · 거절 · 보류로 끝난 AI 단계 뒤 처리 건이 RUNNING 으로 끝없이 남았고, 사건이 열려 있으면 [닫기]도 거절됐다.
    P1-01: 처리 건이 끝나도 사건은 「승인 대기」로 남아 열린 사건 수를 부풀렸다."""
    alert, pid = _pump_case(world)
    row = world.row(pid, 'task:diagnose')
    assert (row['status'], row['draft_status']) == ('IN_PROGRESS', 'FAILED')
    stuck = world.rt.instance_view(pid)['attention']
    step = stuck['steps'][0]
    assert stuck['label'] == '멈춤 — 사람 조치 필요' and step['kind'] == 'failed' and {'close', 'rework'} <= set(step['actions'])
    assert step['reason'], '멈춘 까닭(학생 문장)이 함께 실린다'
    listed = next(r for r in world.api('GET', '/api/instances')[1] if r['proc_inst_id'] == pid)
    assert listed['attention']['steps'] == [row['activity_name']]
    assert world.incident(pid).state == 'AWAITING_APPROVAL'
    with pytest.raises(PermissionError, match="'나'"):
        world.rt.close_agent_task(row['id'], 'OP-17', '수업 단계 밖')       # P1-15: 누가 했는지 모르는 닫기는 받지 않는다
    out = world.rt.close_agent_task(row['id'], 'user:kim-op', '수업 단계에서는 펌프 진단을 하지 않음')
    inst = world.inst(pid)
    assert out['instance_ended'] and (inst['status'], inst['end_event']) == ('COMPLETED', 'closed-by-human')
    inc = world.incident(pid)
    assert inc.state == 'ESCALATED' and inc.reason == 'PROCESS_ENDED: 사람이 닫음'
    view = world.rt.instance_view(pid)
    assert view['instance']['end_label'] == '사람이 닫음' and view['attention'] is None


def test_처리_건이_끝났는데_사건이_열려_있으면_폴링이_사건을_닫는다(world):
    """P1-01: 커밋 뒤 사건 닫기가 끊겨도(다시 켜짐 · 저장소 실패) 폴링 정리가 같은 규칙으로 다시 한다."""
    alert, pid = _pump_case(world)
    with psycopg.connect(world.dsn, autocommit=True) as db:            # 처리 건만 끝나고 사건은 그대로인 상태(커밋 뒤 끊김)
        db.execute("UPDATE bpm_proc_inst SET status='COMPLETED', end_event='ev:escalated' WHERE proc_inst_id=%s", (pid,))
    assert world.incident(pid).state == 'AWAITING_APPROVAL'
    world.poll()
    inc = world.incident(pid)
    assert inc.state == 'ESCALATED' and inc.reason.startswith('PROCESS_ENDED: ')


def test_승인_전에_경보가_풀려_처리_건이_닫히면_승인_대기_판단도_승인_전_종료로_끝난다(world):
    """재시작 확인(2026-11-01): 조치 전 해소로 닫힌 HYD-02 처리 건의 판단 카드가 「승인 대기」로 남아 승인할 것처럼 보였다."""
    alert, pid, did = world.start_cooling()
    assert world.main.book[did]['state'] == 'PENDING_APPROVAL'
    world.clear_alert(alert)
    world.poll()
    assert world.inst(pid)['end_event'] == 'incident-ended-before-action'
    d = world.main.book[did]
    assert (d['state'], d['history'][-1]['reason']) == ('CLOSED_UNAPPROVED', '조치 전 해소')


def test_보호_정지를_먼저_풀고_냉각_경보가_풀려도_자연_회복이_아니라_책임자_확인으로_닫는다(world):
    """재시작 확인 · 독립 검증(2026-11-01~02): 설비가 유온 높음으로 보호 정지해 펌프가 멈추고 식어 경보가 풀렸는데 냉각 사건이 「자연 회복」으로
    닫혔다. 사람이 PLC 를 리셋해 보호 정지가 먼저 풀린 뒤 냉각 경보가 풀리는 순서도 같다 — 감지기의 보호 정지 경보(근거 trip)를 원천 접수로 흘린다."""
    alert, pid, did = world.start_cooling()
    trip, _ = world.raise_alert('OVERHEAT_TRIP', 'HYD-01', trip='OVERTEMP')
    world.clear_alert(trip)                                              # 사람이 보호 정지를 먼저 리셋
    world.clear_alert(alert)
    world.poll()
    inc = world.incident(pid)
    assert inc.state == 'ESCALATED' and inc.reason.startswith('TRIPPED_BEFORE_ACTION'), (inc.state, inc.reason)
    assert world.main.book[did]['state'] == 'CLOSED_UNAPPROVED'


def test_처리_건이_끝났는데_판단이_승인_대기로_남으면_폴링이_판단을_끝낸다(world):
    """독립 검증(2026-11-02): 판단 닫기는 커밋 뒤에 따로 돈다 — 그 사이 process 가 다시 켜지면 판단이 승인 대기로 남았다. 처리 건만 끝나고
    판단은 그대로인 상태(커밋 뒤 끊김)를 만들고 폴링 정리가 같은 규칙으로 끝내는지 본다."""
    alert, pid, did = world.start_cooling()
    with psycopg.connect(world.dsn, autocommit=True) as db:
        db.execute("UPDATE bpm_proc_inst SET status='COMPLETED', end_event='closed-by-human' WHERE proc_inst_id=%s", (pid,))
    world.incident(pid).state = 'ESCALATED'          # 사건은 이미 끝났다 — 사건 정리(reconcile_open_incidents)는 이 처리 건을 다시 보지 않는다
    assert world.main.book[did]['state'] == 'PENDING_APPROVAL'
    world.poll()
    assert world.main.book[did]['state'] == 'CLOSED_UNAPPROVED'


def test_승인_전에_경보가_풀리면_기준_흐름도_상급자_호출_없이_조치_전_해소로_닫는다(world):
    """P1-09: 전에는 기준 흐름이 저절로 나은 사건에도 「상급자 호출」 사람 단계를 열어 「에스컬레이션 종료」로 끝냈다."""
    alert, pid = _pump_case(world)
    world.clear_alert(alert)
    world.poll()
    inst = world.inst(pid)
    assert (inst['status'], inst['end_event']) == ('COMPLETED', 'incident-ended-before-action')
    assert world.rt.instance_view(pid)['instance']['end_label'] == '조치 전 해소'
    assert all(w['status'] != 'IN_PROGRESS' for w in world.rows(pid) if w['activity_id'] == 'task:escalate')


def test_처리_건이_열리지_못한_사건은_정한_시간이_지나면_책임자_확인으로_닫는다(world):
    """P1-30: 사건을 만든 뒤 처리 건 저장이 실패하면 처리 건 없는 사건이 「승인 대기」로 남았다."""
    from procsvc import instances
    before = set(world.main.incidents)
    with world.storage_fails('bpm_proc_inst', 'true'), pytest.raises(AssertionError):
        world.raise_alert(*COOLING)
    orphan = next(i for i in world.main.incidents.values() if i.id not in before)
    assert orphan.state == 'AWAITING_APPROVAL'
    world.poll()
    assert orphan.state == 'AWAITING_APPROVAL', '원천 재접수가 이어 갈 시간을 준다'
    from hydcommon.timeutil import parse_iso
    world.clock.advance(max(0.0, (parse_iso(orphan.created) - world.clock()).total_seconds()) + instances.ORPHAN_INCIDENT_S + 1)
    world.poll()
    assert orphan.state == 'ESCALATED' and orphan.reason == 'PROCESS_ENDED: 처리 건이 열리지 못함'


# ---------------------------------------------------------------- P1-02 같은 질문 다시 보내기
def test_같은_질문을_다시_보내도_엔진이_막_저장한_끝_상태를_덮어쓰지_않는다(world):
    """P1-02: 전에는 잠금 없이 읽은 옛 처리 건 행 전체를 덮어써, 그 사이 엔진이 저장한 답 · 끝 상태를 지웠다."""
    version = _version('ask_agent_v1.json')
    values = {'question': '냉각기 점검 주기는?', 'asked_by': '수강생'}
    key = 'K-' + uuid.uuid4().hex
    first = world.rt.start_definition('ask_agent', version, 'q-' + uuid.uuid4().hex, values=values, _coalesce_key=key)
    pid = first['proc_inst_id']
    held, release = threading.Event(), threading.Event()

    def engine_finishes():
        with world.rt.repo.instance_transaction('hyd', pid):
            world.rt.repo.update_instance({'proc_inst_id': pid, 'status': 'COMPLETED', 'end_event': 'closed-by-human'})
            held.set()
            assert release.wait(30)
    finisher, _ = _in_thread(engine_finishes)
    assert held.wait(30)
    resend, result = _in_thread(lambda: world.rt.start_definition('ask_agent', version, 'q-' + uuid.uuid4().hex, values=values,
                                                                  _coalesce_key=key))
    resend.join(1)
    release.set()
    finisher.join(30)
    resend.join(30)
    assert world.inst(pid)['status'] == 'COMPLETED', '엔진이 저장한 끝 상태가 그대로'
    assert result['ok']['proc_inst_id'] != pid, '끝난 질문에 합치지 않고 새 질문으로 연다'


# ---------------------------------------------------------------- P1-16 시작 값 크기
def test_너무_큰_시작_값은_쉬운_말로_거절한다(world):
    with pytest.raises(ValueError, match='시작 값이 너무 큽니다'):
        world.rt.start_definition('ask_agent', _version('ask_agent_v1.json'), 'q-' + uuid.uuid4().hex,
                                  values={'question': '가' * 300_000, 'asked_by': '수강생'})


# ---------------------------------------------------------------- H-2 · P1-14 지운 흐름 정리는 필요할 때만
def test_지운_흐름의_그래프_정리는_기동_때_한_번이고_그_뒤에는_정의를_지우거나_실패했을_때만_한다(world):
    status = world.rt.graph_cleanup_status()
    world.poll()
    assert world.rt.graph_cleanup_status()['due'] is False, '기동 뒤 첫 폴링에서 한 번 정리한다'
    world.rt.definitions_changed()
    assert world.rt.graph_cleanup_status()['due'] is True
    world.poll()
    assert world.rt.graph_cleanup_status()['due'] is False and status is not None


def test_지운_흐름의_고아_판본은_한_번에_고르는_수보다_많아도_한_번의_정리로_모두_지운다(world):
    """FA1 검증 P1-14: 정리가 고아 판본을 limit(20)개만 한 번 고르고 끝났다고 표시해 나머지가 다음 계기(기동 · 판본 삭제)까지 그래프에 남았다.
    (살아 있는 처리 건이 쓰는 판본을 건너뛰는 경우는 시험으로 꾸미지 못했다 — 반영기가 처리 건 노드의 판본 관계를 곧 다시 써서. 코드는 id 차례로 읽는다)"""
    tag = uuid.uuid4().hex[:8]
    ids = [f'proc-version:hyd:gone-{tag}-{i:02d}:1' for i in range(5)]
    q = world.rt.hooks.record_cypher
    q("UNWIND $ids AS id CREATE (:ProcessVersion {id: id, tenant_id: 'hyd', definition_id: split(id, ':')[2], version: '1'})", ids=ids)
    try:
        assert world.rt.cleanup_removed_definitions(limit=2) is True
        left = {r['id'] for r in world.rt.hooks.query_cypher("MATCH (pv:ProcessVersion) WHERE pv.id IN $ids RETURN pv.id AS id", ids=ids)}
        assert left == set(), left
    finally:
        q("MATCH (pv:ProcessVersion) WHERE pv.id IN $ids DETACH DELETE pv", ids=ids)


def test_처리_건_보기는_읽는_도중_다른_커밋이_끼어도_처리_건과_단계를_한_시점으로_보인다(world, monkeypatch):
    """한바퀴3: 처리 건 보기가 처리 건 · 단계를 따로 읽어, 그 사이 커밋된 전이가 반쯤 보였다(승인 단계는 열렸는데 판단 id 는 없음 — 확인 도구가
    「추천 카드의 승인 역할을 알 수 없음」). 처리 건을 읽은 직후 다른 연결이 처리 건 이름과 승인 단계 기록을 한 트랜잭션으로 바꾼다."""
    alert, pid, decision = world.start_cooling()
    approve = world.row(pid, 'T_approve', 'IN_PROGRESS')
    repo, real = world.rt.repo, type(world.rt.repo).get_instance
    fired = []

    def get_instance(self, proc_inst_id, *a, **k):
        got = real(self, proc_inst_id, *a, **k)
        if proc_inst_id == pid and not fired:
            fired.append(True)
            with psycopg.connect(world.dsn) as other, other.transaction():
                other.execute("update bpm_proc_inst set proc_inst_name = proc_inst_name || ' (바뀜)' where proc_inst_id = %s", (pid,))
                other.execute("update todolist set log = coalesce(log, '') || '바뀜; ' where id = %s", (approve['id'],))
        return got
    monkeypatch.setattr(type(repo), 'get_instance', get_instance)
    view = world.rt.instance_view(pid)
    row = next(w for w in view['workitems'] if w['id'] == approve['id'])
    assert fired and view['instance']['proc_inst_name'].endswith('(바뀜)') == ('바뀜;' in (row.get('log') or '')), \
        (view['instance']['proc_inst_name'], row.get('log'))
