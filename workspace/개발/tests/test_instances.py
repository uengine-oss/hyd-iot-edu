"""처리 건 런타임(procsvc/instances.py) — 수업 흐름을 처음부터 끝까지 실제 엔진 · 실제 DB 로 돌린다.

바깥(AI · Kafka · TimescaleDB · Neo4j · agent 검사 · SMTP)만 대체물이고(conftest `# ---- engine ----`), 경보 접수 → 처리 건 → 에이전트 단계
(녹화본) → 사람 승인(API 와 같은 함수) → 설비 명령 · ACK → 재관측 → 작업지시 · 발주 · 입고(실제 enterprise-sim) → 결과 보고까지 그대로다.
"""
import pytest

from hydcommon import schemas, topics

COOLING = ('COOLER_DEGRADATION', 'HYD-01')
OPERATOR = dict(by='user:kim-op', role='role:operator')
MAINT = dict(by='user:park-maint', role='role:maint-mgr')
BUYER = dict(by='user:jung-buy', role='role:purchasing')
WINDOW_S = 15 * 60 / 20          # 재관측 창 = 15 시뮬레이션 분 ÷ 배속 20


# ---------------------------------------------------------------- 흐름 A (냉각 c3_cooling)
def _start_cooling(world):
    alert, pid = world.raise_alert(*COOLING)
    assert world.inst(pid)['proc_def_id'] == 'c3_cooling'
    decision = world.agent(pid, 'T_agent', '원인 진단 · 냉각 조치 제안')
    return alert, pid, decision


def _approve(world, pid, decision, option, who):
    approve = world.row(pid, 'T_approve', 'IN_PROGRESS')
    return world.rt.select(approve['id'], decision, option, **who)


def _commanded(world, pid):
    cmd = world.kafka.of(topics.K_CMD)[-1]
    assert world.incident(pid).state == 'AWAITING_ACK', world.incident(pid).state
    return cmd


def _report(world, pid):
    inst = world.inst(pid)
    assert inst['status'] == 'COMPLETED', [(w['activity_id'], w['status'], (w.get('log') or '')[-200:]) for w in world.rows(pid)]
    return world.values(pid)['result_report']


def test_냉각_흐름A는_승인_명령_재관측_작업지시를_거쳐_정상으로_끝난다(world):
    alert, pid, decision = _start_cooling(world)
    _approve(world, pid, decision, 'skill:sop-cool-11', OPERATOR)
    cmd = _commanded(world, pid)
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


def test_냉각_흐름A에서_운전원이_거절하면_명령_없이_반려로_끝난다(world):
    alert, pid, decision = _start_cooling(world)
    approve = world.row(pid, 'T_approve', 'IN_PROGRESS')
    world.rt.reject_card(approve['id'], decision, reason='현장 확인 뒤 다시 판단', **OPERATOR)
    report = _report(world, pid)
    assert report['outcome'] == '반려' and '현장 확인 뒤 다시 판단' in report['summary']
    assert world.kafka.of(topics.K_CMD) == [], '거절이면 설비 명령을 내지 않는다'
    assert world.incident(pid).state == 'REJECTED_BY_OPERATOR'
    assert world.main.book[decision]['state'] == 'REJECTED'


def test_승인_지연_알림은_벽시계_10분에_울리고_배속을_곱하지_않는다(world):
    """#2: 사람이 읽고 고르는 시간은 벽시계다. 전에는 PT10M ÷ 20 = 30초에 「승인 지연」 보고 · 알림이 났다."""
    alert, pid, decision = _start_cooling(world)
    timer = world.row(pid, 'B_overdue', 'IN_PROGRESS')
    world.clock.advance(31)
    world.poll()
    assert world.row(pid, 'B_overdue')['status'] == 'IN_PROGRESS', '30초 만에 승인 지연이 울리면 안 된다(20배속을 곱한 것)'
    world.clock.advance(10 * 60)
    world.poll()
    assert world.row(pid, 'T_notice')['status'] == 'DONE', '벽시계 10분이 지나면 승인 지연을 알린다'
    assert any(e['event'] == 'TIMER_FIRED' and e['detail']['event'] == 'B_overdue' for e in world.main.audit_log), \
        'A-08: 타이머 발화는 TIMER_FIRED + 이벤트 id 로 남는다'
    assert timer['activity_id'] == 'B_overdue'
    _approve(world, pid, decision, 'skill:sop-cool-11', OPERATOR)     # 알림 타이머는 멈추지 않는 타이머 — 알림 뒤에도 승인할 수 있다
    assert world.incident(pid).state == 'AWAITING_ACK'


def test_재관측에서_회복하지_않으면_미달로_끝나고_사건은_완화_실패다(world):
    alert, pid, decision = _start_cooling(world)
    _approve(world, pid, decision, 'skill:sop-cool-11', OPERATOR)
    world.ack('HYD-01', _commanded(world, pid)['cmdId'])
    world.tag('HYD-01', 'TS1', 61.0)                                     # 기준(55 ℃) 밖, 경보도 그대로
    world.clock.advance(WINDOW_S + 1)
    world.poll()
    report = _report(world, pid)
    assert report['outcome'] == '미달'
    inc = world.incident(pid)
    assert (inc.state, inc.reason) == ('ESCALATED', 'MITIGATION_FAILED')


def test_재관측_값이_기준_안인데_경보가_아직이면_창을_세_번까지_늘린다(world):
    alert, pid, decision = _start_cooling(world)
    _approve(world, pid, decision, 'skill:sop-cool-11', OPERATOR)
    world.ack('HYD-01', _commanded(world, pid)['cmdId'])
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
    alert, pid, decision = _start_cooling(world)
    _approve(world, pid, decision, 'skill:sop-cool-11', OPERATOR)
    _commanded(world, pid)
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
    alert, pid, decision = _start_cooling(world)
    world.kafka.fail.add(topics.K_CMD)
    _approve(world, pid, decision, 'skill:sop-cool-11', OPERATOR)
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
    alert, pid, decision = _start_cooling(world)
    _approve(world, pid, decision, 'skill:sop-cool-11', OPERATOR)
    world.ack('HYD-01', _commanded(world, pid)['cmdId'])
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
    alert, pid, decision = _start_cooling(world)
    _approve(world, pid, decision, 'skill:sop-cool-11', OPERATOR)
    _commanded(world, pid)
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
    decision = world.agent(pid, 'T_agent', '원인 진단 · 냉각 조치 제안')
    assert world.row(pid, 'T_approve')['status'] == 'IN_PROGRESS'
    _approve(world, pid, decision, 'skill:sop-cool-11', OPERATOR)
    assert world.incident(pid).state == 'AWAITING_ACK'


def test_승인_대기_중_process가_다시_켜져도_승인하면_명령이_나간다(world):
    alert, pid, decision = _start_cooling(world)
    world.restart()
    _approve(world, pid, decision, 'skill:sop-cool-11', OPERATOR)
    world.ack('HYD-01', _commanded(world, pid)['cmdId'])
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
    alert, pid, decision = _start_cooling(world)
    with pytest.raises(PermissionError, match=error):
        _approve(world, pid, decision, 'skill:sop-cool-11', who)
    approve = world.row(pid, 'T_approve')
    with pytest.raises(PermissionError, match=error):
        world.rt.reject_card(approve['id'], decision, reason='사유', **who)
    assert world.row(pid, 'T_approve')['status'] == 'IN_PROGRESS'


# ---------------------------------------------------------------- 바깥 응답과 처리 건 잠금 (A-05)
def _held_approval(world, pid, decision, who):
    """승인 현재 조건 검사(agent)가 답하지 않는 동안의 승인 하나 — (들어옴, 풀어 줌, 결과)."""
    import threading
    entered, release, result = threading.Event(), threading.Event(), {}
    world.services.verdict['hold'] = (entered, release)

    def run():
        try:
            result['ok'] = _approve(world, pid, decision, 'skill:sop-cool-11', who)
        except Exception as e:  # noqa: BLE001 — 결과로 확인한다
            result['error'] = e
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    assert entered.wait(30), '승인이 agent 검사에 닿지 않았다'
    return release, thread, result


def test_승인_검사가_agent_응답을_기다리는_동안_같은_처리_건의_다른_일은_줄_서지_않는다(world):
    """A-05: 전에는 승인 현재 조건 검사(최대 20초)를 처리 건 잠금 안에서 기다려, 그 사이 같은 처리 건의 워커 결과 저장 · 임대 갱신이 멈췄다."""
    import threading
    alert, pid, decision = _start_cooling(world)
    release, thread, result = _held_approval(world, pid, decision, OPERATOR)
    done = threading.Event()

    def other_work():
        with world.rt._transition(pid):        # 같은 처리 건 잠금을 잡는 다른 일(워커 결과 저장과 같은 길)
            done.set()
    other = threading.Thread(target=other_work, daemon=True)
    other.start()
    try:
        assert done.wait(10), '승인 검사가 끝날 때까지 같은 처리 건의 다른 일이 기다렸다'
    finally:
        release.set()
        thread.join(30)
        other.join(30)
    assert 'error' not in result and result['ok']['accepted'], result
    assert world.row(pid, 'T_approve')['status'] == 'DONE', '승인은 그대로 접수 · 전달돼 다음 단계로 갔다'


def test_승인_검사를_기다리는_사이_다른_사람이_먼저_승인하면_두_번째_승인은_받지_않는다(world):
    alert, pid, decision = _start_cooling(world)
    release, thread, result = _held_approval(world, pid, decision, OPERATOR)
    try:
        first = _approve(world, pid, decision, 'skill:sop-cool-11', OPERATOR)
        assert first['accepted']
    finally:
        release.set()
        thread.join(30)
    assert isinstance(result.get('error'), ValueError) and '이미 처리된 승인' in str(result['error']), result
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
    decision = world.agent(pid, 'T_agent', '정비 계획 제안')
    sent = len(world.services.smtp.messages)
    _approve(world, pid, decision, world.main.book[decision]['recommended'], MAINT)
    report = _report(world, pid)
    assert report['outcome'] == '정상' and report['refs']['work_order'].startswith('WO-')
    mails = world.services.smtp.messages[sent:]
    assert len(mails) == 1 and 'production@hyd.local' in mails[0], '정비 공지 메일 한 통'


def test_정기_정비_흐름B에서_거절하면_정비_오더_없이_반려로_끝난다(world):
    alert, pid = _button(world, 'B', dict(by='박정비', user_id='user:park-maint', roles=['role:maint-mgr']))
    decision = world.agent(pid, 'T_agent', '정비 계획 제안')
    approve = world.row(pid, 'T_approve', 'IN_PROGRESS')
    world.rt.reject_card(approve['id'], decision, reason='이번 주는 생산 우선', **MAINT)
    report = _report(world, pid)
    assert report['outcome'] == '반려' and 'work_order' not in report['refs']


def test_예비품_구매_흐름C는_승인하면_발주_입고까지_하고_구매팀장에게도_알린다(world):
    alert, pid = _button(world, 'C', dict(by='정구매', user_id='user:jung-buy', roles=['role:purchasing']))
    assert world.inst(pid)['proc_def_id'] == 'c3_spare'
    decision = world.agent(pid, 'T_agent', '발주안 제안')
    _approve(world, pid, decision, world.main.book[decision]['recommended'], BUYER)
    report = _report(world, pid)
    values = world.values(pid)
    assert report['outcome'] == '입고 완료' and report['refs']['purchase_order'].startswith('PR-') and values['received'] is True
    assert values['approved_amount'] > 300
    notes = world.rt.repo.list_notifications('hyd', ['user:han-buymgr', 'role:purchasing-mgr'])
    assert any('재고 보충 결과' in n['title'] for n in notes), '금액이 전결 기준(300만원)을 넘으면 구매팀장에게도 알린다'


def test_예비품_구매_흐름C에서_거절하면_발주하지_않는다(world):
    alert, pid = _button(world, 'C', dict(by='정구매', user_id='user:jung-buy', roles=['role:purchasing']))
    decision = world.agent(pid, 'T_agent', '발주안 제안')
    approve = world.row(pid, 'T_approve', 'IN_PROGRESS')
    world.rt.reject_card(approve['id'], decision, reason='다음 달 예산으로', **BUYER)
    report = _report(world, pid)
    assert report['outcome'] == '반려' and 'purchase_order' not in report['refs']


# ---------------------------------------------------------------- 교대 인수인계 (제공 정의 shift_handover · 가져온 ShiftHandover)
SENDER, RECEIVER = 'user:kim-op', 'user:choi-op'
FIRST, REVISION = '인계안 작성', '인계안 작성 · 보완 1'


def _start_handover(world, definition='shift_handover', version='1.1'):
    import uuid
    inputs = world.recording_of(FIRST)['runs'][-1]['context']['inputs']
    inst = world.rt.start_definition(definition, version, 'handover:' + uuid.uuid4().hex,
                                     values={k: inputs[k] for k in ('asset', 'shift_label', 'as_of', 'work_notes')})
    return inst['proc_inst_id']


def _human(world, pid, activity, by, output):
    row = world.row(pid, activity, 'IN_PROGRESS')
    return world.rt.submit_human(row['id'], output, by)


def _draft(world, pid, activity, step):
    world.agent(pid, activity, step)
    assert world.row(pid, activity)['status'] == 'DONE', world.row(pid, activity).get('log')


@pytest.mark.parametrize('revisions, end', [(0, 'ev:confirmed'), (1, 'ev:confirmed'), (2, 'ev:confirmed'), (3, 'ev:followup')])
def test_교대_인수인계는_보완_요청을_두_번까지_받고_세_번째는_후속_확인으로_끝난다(world, revisions, end):
    """보완 0 · 1 · 2번은 인수 확인으로 끝나고, 2번을 넘기면(세 번째 보완 요청) 「후속 확인 필요 · 인수 미확정」 끝 이벤트로 끝난다.
    보완 2번째 초안(task:draft-r3)은 녹화가 없어 보완 1 녹화를 다시 쓴다(엔진이 보는 것은 형식과 근거 대조다)."""
    pid = _start_handover(world)
    rounds = [('task:draft', 'task:sender', 'task:receiver', FIRST), ('task:draft-r2', 'task:sender-r2', 'task:receiver-r2', REVISION),
              ('task:draft-r3', 'task:sender-r3', 'task:receiver-r3', REVISION)]
    for n, (draft, sender, receiver, step) in enumerate(rounds):
        _draft(world, pid, draft, step)
        if n == revisions:
            _human(world, pid, sender, SENDER, {'sender_decision': 'approve', 'sender_notes': '확인 사항을 전달합니다'})
            _human(world, pid, receiver, RECEIVER, {'receiver_decision': 'confirm', 'receiver_notes': '확인했습니다', 'communication_only': True})
            break
        _human(world, pid, sender, SENDER, {'sender_decision': 'revise', 'sender_notes': f'보완 {n + 1}: 작업지시와 재고를 다시 대조'})
    inst = world.inst(pid)
    assert (inst['status'], inst['end_event']) == ('COMPLETED', end), [(w['activity_id'], w['status']) for w in world.rows(pid)]


def test_가져온_교대_흐름_ShiftHandover도_같은_규칙으로_끝까지_돈다(world):
    """학생이 bpmn.io 로 가져오는 제공 교대 그림(course_handover.json) — 흐름 가져오기 · 등록과 같은 서버 길로 등록해 처음부터 끝까지."""
    import json
    from procsvc.course_policy import HANDOVER as handover
    version = world.import_flow('ShiftHandover', handover['xml'], handover['mapping'], 'shift-handover.bpmn')
    pid = _start_handover(world, 'ShiftHandover', version)
    _draft(world, pid, 'task_draft', FIRST)
    _human(world, pid, 'task_sender', SENDER, {'sender_decision': 'approve', 'sender_notes': '전달'})
    _human(world, pid, 'task_receiver', RECEIVER, {'receiver_decision': 'confirm', 'receiver_notes': '확인', 'communication_only': True})
    inst = world.inst(pid)
    assert inst['status'] == 'COMPLETED' and inst['end_event']


# ---------------------------------------------------------------- 폴링이 하는 일 (B-2 · A-03 · B-4 · B-11)
def _consumer_and_outbox(world, pid, activity):
    import psycopg
    row = world.row(pid, activity)
    with psycopg.connect(world.services.dsn) as db:
        n = db.execute('SELECT count(*) FROM execution_projection_outbox WHERE proc_inst_id=%s', (pid,)).fetchone()[0]
    return row['consumer'], row['updated_at'] if 'updated_at' in row else None, n


def test_마감이_남은_대기_행은_폴링이_다시_집지_않는다(world):
    """B-2(하-08): 전에는 ACK · 재관측을 기다리는 행을 2초마다 다시 집어 담당 표식을 새로 쓰고, 그때마다 그래프 반영 대기열에 한 줄씩 쌓였다."""
    alert, pid, decision = _start_cooling(world)
    _approve(world, pid, decision, 'skill:sop-cool-11', OPERATOR)
    world.ack('HYD-01', _commanded(world, pid)['cmdId'])
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
        alert, pid, decision = _start_cooling(world)
    failures = world.events(pid, job='POST_COMMIT_EFFECT_FAILED')
    assert failures and '담당자 알림' in failures[-1]['data']['friendly']
    assert world.row(pid, 'T_approve')['status'] == 'IN_PROGRESS', '효과가 실패해도 이미 커밋한 진행은 그대로'


def test_처리_건_하나의_대기_행이_실패해도_같은_바퀴의_다른_처리_건은_진행한다(world):
    """B-11: 전에는 대기 행 처리(reconcile_services)의 소유 전이에 처리 건 단위 try 가 없어, 한 처리 건의 예외가 폴링 한 바퀴를 멈췄다."""
    runs = []
    for _ in range(2):
        alert, pid, decision = _start_cooling(world)
        _approve(world, pid, decision, 'skill:sop-cool-11', OPERATOR)
        world.ack('HYD-01', _commanded(world, pid)['cmdId'])
        world.clear_alert(alert)
        runs.append((pid, world.row(pid, 'T_reobs')['id']))
    world.tag('HYD-01', 'TS1', 50.0)
    first, second = sorted(runs, key=lambda r: r[1])                # 폴링은 행 id 순서로 돈다 — 앞 처리 건을 실패시킨다
    world.clock.advance(WINDOW_S + 1)
    with world.storage_fails('todolist', f"NEW.id = '{first[1]}' AND NEW.consumer IS DISTINCT FROM OLD.consumer"):
        world.poll()
    assert world.inst(second[0])['status'] == 'COMPLETED'
    failures = world.events(first[0], job='ENGINE_STEP_FAILED')
    assert failures and '다시 시도합니다' in failures[-1]['data']['friendly']
    world.poll()
    assert world.inst(first[0])['status'] == 'COMPLETED', '저장소가 돌아오면 다음 바퀴에 이어 간다'
