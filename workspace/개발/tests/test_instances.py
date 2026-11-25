"""처리 건 런타임(procsvc/instances.py) — 수업 흐름을 처음부터 끝까지 실제 엔진 · 실제 DB · 실제 서비스로 돌린다(conftest 머리말의 구성 표).

경보 접수 → 처리 건 → 에이전트 단계(실제 워커 · 재생) → 사람 승인(API 와 같은 함수 — 실제 agent 의 승인 현재 조건 검사) → 설비 명령(실제 관문
코드 → 가상 설비의 장치 층 → PLC — world.forward, 응답은 PLC 가 낸다) → 재관측(설비 모형이 낸 값 · 감지 규칙이 푼 경보 — world.pass_time) →
작업지시 · 발주 · 입고(실제 enterprise-sim) → 결과 보고까지 그대로다. 회복 여부를 시험이 값으로 넣지 않는다.
"""
import contextlib
import json
import re
import threading
import uuid

import psycopg
import pytest

from hydcommon import schemas, topics
from procsvc.inbox import NOT_A_PERSON

from conftest import COOLING, OPERATOR, RecordedCli, definition_version as _version, recording
from test_student_system_link import linked, pbl, system, _ok          # noqa: F401 — pbl · linked · system 은 고정물(PBL 단계 · 내 도구 서버)

ME = OPERATOR['by']               # 사람은 담당자 한 명이고 모든 역할의 구성원이다(migration 000072) — 역할만 다르게 내세운다
MAINT = dict(by=ME, role='role:maint-mgr')
BUYER = dict(by=ME, role='role:purchasing')
WINDOW_S = 15 * 60 / 20          # 재관측 창 = 15 시뮬레이션 분 ÷ 배속 20


# ---------------------------------------------------------------- 흐름 A (냉각 c3_cooling)
def _report(world, pid):
    inst = world.inst(pid)
    assert inst['status'] == 'COMPLETED', [(w['activity_id'], w['status'], (w.get('log') or '')[-200:]) for w in world.rows(pid)]
    return world.values(pid)['result_report']


def _effect(world, pid):
    """효과 확인이 판정할 때까지 시간을 흘린다(첫 창, 그 뒤 연장 창마다 — 설비 · 감지기 · 엔진이 같은 시간을 산다). 회복 여부는 설비 모형이 낸 값과
    감지 규칙이 정한다 — 시험은 값도 경보 해제도 넣지 않는다."""
    world.pass_time(WINDOW_S + 1)
    _effect_rest(world, pid)


def _effect_rest(world, pid):
    """첫 창 뒤: 처리 건이 끝날 때까지 연장 창(창의 3분의 1)마다 시간을 흘린다 — 연장 한도만큼."""
    from procsvc.service_parts import REOBSERVE_MAX_EXTENSIONS
    for _ in range(REOBSERVE_MAX_EXTENSIONS):
        if world.inst(pid)['status'] != 'RUNNING':
            break
        world.pass_time(WINDOW_S / 3 + 1)


def _setpoints_follow(world, cmd):
    """PLC 가 이 명령을 실행했고 설비의 지령이 명령 값과 같다 — 조치 → PLC 쓰기는 명령 계약 한 곳(schemas.actions_to_writes)이다. 지령 값(팬 · 부하)은
    설비 태그로, 펌프 전환은 설비의 운전 펌프로 본다(plantsim.plc.PUMP_OF)."""
    from plantsim import plc
    unit, tags = world.plant.units[cmd['asset']], world.plant.tags(cmd['asset'])
    assert (unit.ctrl.last_cmd_id, unit.ctrl.last_result) == (cmd['cmdId'], 'DONE'), (unit.ctrl.last_cmd_id, unit.ctrl.last_result, unit.ctrl.last_reason)
    for write in schemas.actions_to_writes(cmd['actions']):
        if write['res'] in tags:
            assert tags[write['res']] == write['v'], (write, {k: tags[k] for k in ('FanSpeedSP', 'LoadSP')})
        elif write['res'] == 'PumpSelect':
            assert unit.state.pump == plc.PUMP_OF[write['v']], (write, unit.state.pump)


def _recovered_on_plant(world, pid):
    """설비가 지금 그 사건의 회복 기준 안인가(설비 모형의 값) — 결과 보고의 판정을 이것과 견준다."""
    tag, op, limit = world.incident(pid).recovery
    value = world.plant.tags(world.incident(pid).asset)[tag]
    return value < limit if op == '<' else value >= limit


def _reviewed_approve(world, pid, decision, option, parameters, who):
    """승인자가 카드의 값을 바꾼 뒤([새 예측 검토] — 그 값의 새 예측을 본 검토본) 그 검토본으로 승인한다(포털의 값 바꿔 승인과 같은 길)."""
    approve = world.row(pid, 'T_approve', 'IN_PROGRESS')
    world.report()
    review = world.rt.preview_choice(approve['id'], decision, option, parameters)
    return world.approve(pid, decision, option, who, review_id=review['id'])


def test_냉각_흐름A는_승인한_명령이_설비를_실제로_식혀_효과_확인을_거쳐_정상으로_끝난다(world):
    """승인한 팬 최대(FAN_SET 100)가 관문 → PLC 를 지나 설비의 팬 지령이 되고, 설비 모형이 그 지령으로 유온을 내려 감지 규칙이 경보를 푼다."""
    alert, pid, decision = world.start_cooling()
    world.approve(pid, decision, 'skill:sop-cool-11', OPERATOR)
    cmd = world.commanded(pid)
    assert cmd['actions'] == [{'code': 'FAN_SET', 'fan_pct': 100}] and cmd['asset'] == 'HYD-01'
    ledger = world.kafka.of(topics.K_AUDIT)
    assert any(e.get('detail', {}).get('cmdId') == cmd['cmdId'] for e in ledger if e.get('event') == schemas.CMD_APPROVAL_LEDGER_EVENT), \
        '명령보다 먼저 승인 원장이 실려야 한다'
    receipt = world.forward()
    assert (receipt['kind'], receipt['status']) == ('ACK', 'HANDLED') and world.incident(pid).ack['result'] == 'DONE', receipt
    _setpoints_follow(world, cmd)
    assert world.row(pid, 'T_reobs', 'SUBMITTED')['due_date'], '재관측 창의 마감이 행에 저장돼야 한다'
    _effect(world, pid)
    report = _report(world, pid)
    assert report['outcome'] == '정상' and report['refs'].get('work_order'), report
    assert _recovered_on_plant(world, pid) and world.incident(pid).state == 'CLOSED'


PEOPLE = {'role:operator': OPERATOR, 'role:prod-mgr': dict(by=ME, role='role:prod-mgr'), 'role:maint-mgr': MAINT}


@pytest.mark.parametrize('sop', ['skill:sop-cool-11', 'skill:sop-cool-12', 'skill:sop-cool-13', 'skill:sop-cool-14'],
                         ids=['명령만(팬 최대)', '명령 둘(팬 최대 · 부하 80 %)', '명령 + 작업지시(부하 70 % · 야간 세척)', '작업지시만(정지 · 핀 세척)'])
def test_냉각_흐름A는_승인한_카드의_조치를_설비에_실제로_하고_설비가_낸_값으로_회복을_판정한다(world, sop):
    """메인 결정(2026-10-31): 흐름 A 는 승인한 카드의 실제 조치 종류(chosen_skill_kind)로 가른다 — 작업지시만인 카드(SOP-COOL-14)도
    정비 수행 뒤 명령 갈래와 같은 재관측(15 설비 분)으로 회복을 확인한다(HM-8.6 · SOP-COOL-14 「재가동 후 확인」). 승인자는 그 카드가 요구하는
    역할의 사람. 전에는 회복 여부를 시험이 매개변수로 정해 유온 값을 넣었다 — 명령이 설비에 닿지 않아도, 엉뚱한 지령으로 옮겨져도 초록이었다.
    지금은 명령이 PLC 를 거쳐 설비 지령이 되고(코드 → 쓰기 항목 대조), 정비 복구는 같은 설비에 닿으며, 판정은 설비 모형이 낸 값과 감지 규칙의
    해제로 난다. 수업 지식의 냉각 카드 넷은 모두 원인(쿨러 핀 오염)에 맞서 유온을 기준 안으로 내린다 — 지는 쪽은 손익(생산 손실 · 비용)이다."""
    alert, pid, decision = world.start_cooling()
    card = next(o for o in world.main.book[decision]['options'] if o['id'] == sop)
    world.approve(pid, decision, sop, PEOPLE[card['approver']['id']])
    commanded = any(a.get('kind') == 'command' for a in card.get('actions') or [])
    assert world.values(pid)['chosen_skill_kind'] == ('control' if commanded else 'work_order')
    if commanded:
        cmd = world.commanded(pid)
        assert world.forward()['kind'] == 'ACK'
        _setpoints_follow(world, cmd)
    world.poll(3)                                                   # 작업지시만: 작업지시 → 정비 수행(같은 설비의 복구) → 재관측 시작
    assert world.row(pid, 'T_reobs' if commanded else 'T_reobs_wo')['status'] != 'DONE', '재관측이 창을 지켜보기 전에 끝났다'
    if not commanded:
        assert world.values(pid)['maintenance']['restored']['targets'] == {'cooler_health': 1.0}, '정비 복구가 이 설비에 닿아야 한다'
    _effect(world, pid)
    report = _report(world, pid)
    assert (report['outcome'], bool(report['refs'].get('work_order'))) == ('정상', True), (report, world.plant.tags('HYD-01')['TS1'])
    assert _recovered_on_plant(world, pid), '결과 보고는 정상인데 설비 값이 회복 기준 밖이다'
    assert bool(world.kafka.of(topics.K_CMD)) is commanded
    assert world.incident(pid).state == 'CLOSED'


@pytest.mark.parametrize('fan, outcome, extensions', [
    (70, '미달', 0),           # 팬 70 % — 유온이 기준(55 ℃) 위에 머문다: 창 끝에 바로 미달
    (88, '미달', 3),           # 팬 88 % — 유온이 기준 안(55 ℃ 미만)이지만 해제선(52 ℃) 위에 머문다: 감지기가 경보를 풀지 않아 세 번 늘린 뒤 미달
], ids=['값이 기준 밖', '값은 기준 안 · 경보 그대로'])
def test_냉각_흐름A에서_승인자가_팬_값을_낮춰_승인하면_설비가_덜_식어_미달로_끝나고_사건은_완화_실패다(world, fan, outcome, extensions):
    """학생이 추천 카드의 값을 바꿔(새 예측을 본 검토본) 승인한 길 — 결과가 추천과 달라야 한다. 전에는 「회복하지 않음」을 시험이 유온 61 · 52 를
    넣어 만들었다. 지금은 바꾼 값이 PLC 를 지나 설비 지령이 되고, 설비 모형이 그 지령으로 덜 식는다."""
    alert, pid, decision = world.start_cooling()
    _reviewed_approve(world, pid, decision, 'skill:sop-cool-11', {'fan_pct': fan}, OPERATOR)
    cmd = world.commanded(pid)
    assert cmd['actions'] == [{'code': 'FAN_SET', 'fan_pct': fan}], cmd
    assert world.forward()['kind'] == 'ACK'
    _setpoints_follow(world, cmd)
    _effect(world, pid)
    report = _report(world, pid)
    inc = world.incident(pid)
    assert (report['outcome'], inc.state, inc.reason, inc.reobs_extensions) == (outcome, 'ESCALATED', 'MITIGATION_FAILED', extensions), \
        (report, world.plant.tags('HYD-01')['TS1'])
    assert not _recovered_on_plant(world, pid) or extensions, '창 끝에 바로 미달이면 설비 값이 기준 밖이어야 한다'


def test_냉각_흐름A에서_PLC가_명령을_거절하면_효과_확인_없이_그_까닭으로_닫힌다(world):
    """관문은 설비가 마지막으로 보고한 운전 모드(원격 자동)를 보고 명령을 넘겼는데, 그 사이 현장 패널에서 운전 모드를 현장 제어로 돌렸다 — PLC 가
    명령 주인 검사로 거절한다(MODE_MISMATCH). 응답은 PLC 가 낸 것이고, 사건은 30초 응답 없음을 기다리지 않고 그 까닭으로 책임자 확인이다."""
    alert, pid, decision = world.start_cooling()
    world.approve(pid, decision, 'skill:sop-cool-11', OPERATOR)
    with world.between_reports():                                           # 마지막 보고: 원격 자동 — 다음 1초 보고 전에 패널이 모드를 바꿈
        assert world.plant.set_mode('HYD-01', 'LOCAL', requester='LOCAL')
        receipt = world.forward()
    assert receipt['kind'] == 'ACK' and world.incident(pid).ack['result'] == 'REJECTED', receipt
    assert world.plant.units['HYD-01'].state.fan_pct != 100, 'PLC 가 거절한 명령이 설비를 바꿨다'
    world.poll(3)
    inc = world.incident(pid)
    from plantsim import plc
    assert (inc.state, inc.reason) == ('ESCALATED', f"PLC REJECTED: {plc.TEXT['MODE_MISMATCH']}"), (inc.state, inc.reason)   # 사유는 PLC 의 학생 문장(코드는 응답 기록에)
    assert inc.ack['reason'] == 'MODE_MISMATCH', inc.ack
    report = _report(world, pid)
    assert report['outcome'] == '미달' and '설비 명령이 PLC 에서 거절됐습니다' in report['summary'] and plc.TEXT['MODE_MISMATCH'] in report['summary'], report
    assert 'MODE_MISMATCH' not in report['summary'], report['summary']
    assert not any(e['job_id'] == 'REOBSERVE_STARTED' for e in world.events(pid)), '거절된 명령의 효과 확인 창을 열었다'


def test_냉각_흐름A에서_관문이_명령을_거절하면_설비에_닿지_않고_관문의_까닭으로_닫힌다(world):
    """승인 뒤 현장 패널이 운전 모드를 현장 제어로 돌렸고 설비가 그 상태를 보고했다 — 관문 검사 ⑥(원격 자동만)이 넘기지 않는다(CMD_REJECTED)."""
    alert, pid, decision = world.start_cooling()
    world.approve(pid, decision, 'skill:sop-cool-11', OPERATOR)
    assert world.plant.set_mode('HYD-01', 'LOCAL', requester='LOCAL')
    world.report('HYD-01')
    cmd = world.commanded(pid)
    receipt = world.forward()
    assert receipt['kind'] == 'REJECT', receipt
    assert world.plant.units['HYD-01'].state.fan_pct != 100 and world.plant.units['HYD-01'].ctrl.last_cmd_id != cmd['cmdId'], '관문이 넘기지 않은 명령이 설비에 닿았다'
    world.poll(3)
    inc = world.incident(pid)
    assert inc.state == 'ESCALATED' and inc.reason == f"GATEWAY_REJECTED: {world.gateway.gw.CHECK_TEXT['MODE']}", (inc.state, inc.reason)
    report = _report(world, pid)
    assert report['outcome'] == '미달' and world.gateway.gw.CHECK_TEXT['MODE'] in report['summary'], report


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


def test_재관측_값이_기준_안인데_감지기가_경보를_아직_풀지_않으면_창을_늘렸다가_풀리면_정상이다(world):
    """감지 규칙의 해제선(52 ℃ · 60초 유지)은 회복 기준(55 ℃)보다 안쪽이다(히스테리시스). 팬 최대로 식는 설비는 첫 창 끝에 기준 안이지만 아직
    해제선 위라 경보가 남아 있다 — 창을 늘려 기다리고, 감지기가 풀면 정상. 전에는 유온 52 를 시험이 넣고 해제도 시험이 골랐다."""
    alert, pid, decision = world.start_cooling()
    world.approve(pid, decision, 'skill:sop-cool-11', OPERATOR)
    world.forward()
    world.pass_time(WINDOW_S + 1)
    extended = [e for e in world.events(todo=world.row(pid, 'T_reobs')['id']) if e['job_id'] == 'REOBSERVATION_EXTENDED']
    assert extended and world.incident(pid).reobs_extensions == 1, [e['job_id'] for e in world.events(pid)]
    reading = extended[0]['data']['reading']
    assert reading['inside'] is True and reading['cleared'] is False, reading
    _effect_rest(world, pid)
    assert _report(world, pid)['outcome'] == '정상' and _recovered_on_plant(world, pid)


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
    world.forward()
    world.restart()
    assert world.incident(pid).state == 'RE_OBSERVING', '재관측은 읽기라 재시작이 결과를 바꾸지 않는다'
    _effect(world, pid)
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
    world.forward()
    _effect(world, pid)
    assert _report(world, pid)['outcome'] == '정상'


# ---------------------------------------------------------------- 승인자 규칙 (A-04)
@pytest.mark.parametrize('who, error', [
    (dict(by='승인자', role='role:operator'), re.escape(NOT_A_PERSON)),   # 자유 글 승인자 — 전에는 카드 승인만 받아 줬다
    (dict(by='OP-17', role='role:operator'), re.escape(NOT_A_PERSON)),
    (dict(by=ME, role='role:nobody-here'), '역할이 아니어서'),              # 사람이지만 내세운 역할의 구성원이 아님(담당자는 시드 역할 전부의 구성원)
], ids=['자유 글', '이름표', '구성원 아님'])
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
    alert, pid = _button(world, 'B', dict(by='담당자', user_id=ME, roles=['role:maint-mgr']))
    assert world.inst(pid)['proc_def_id'] == 'c3_pm'
    decision = world.agent(pid, 'T_agent')
    sent = len(world.stack.smtp.messages)
    world.approve(pid, decision, world.main.book[decision]['recommended'], MAINT)
    report = _report(world, pid)
    assert report['outcome'] == '정비 요청 등록' and report['refs']['work_order'].startswith('WO-')      # 이 흐름은 정비 요청을 등록하고 끝난다 — 정비가 끝난 것이 아니다
    inc = world.incident(pid)
    assert [h['state'] for h in inc.history] == ['GUIDE_RECEIVED', 'AWAITING_APPROVAL', 'APPROVED_EXECUTING', 'WORK_ORDER_CREATED', 'CLOSED'], \
        '설비 명령 없는 승인은 사건을 승인 뒤 실행 중으로 옮긴 뒤 정비 요청 영수증으로 닫는다'
    assert inc.approved_by == ME and inc.cmd_id is None
    mails = world.stack.smtp.messages[sent:]
    assert len(mails) == 1 and 'production@hyd.local' in mails[0], '정비 공지 메일 한 통'


def test_정기_정비_흐름B에서_거절하면_정비_오더_없이_반려로_끝난다(world):
    alert, pid = _button(world, 'B', dict(by='담당자', user_id=ME, roles=['role:maint-mgr']))
    decision = world.agent(pid, 'T_agent')
    approve = world.row(pid, 'T_approve', 'IN_PROGRESS')
    world.rt.reject_card(approve['id'], decision, reason='이번 주는 생산 우선', **MAINT)
    report = _report(world, pid)
    assert report['outcome'] == '반려' and 'work_order' not in report['refs']


DAY_S = 86400


@contextlib.contextmanager
def _purchasing_manager_notes(world):
    """담당자 한 명이 구매 담당 · 구매팀장을 함께 맡으면 두 역할의 알림이 한 줄로 합쳐져 구매팀장 몫을 가를 수 없다 — 이 블록 동안만
    담당자를 구매팀장 역할에서 빼 그 몫이 역할 id 로 남게 한다(구성원 없는 역할의 알림은 역할 id 그대로 — inbox.notification_targets).
    돌려줌 = 이 블록에서 새로 생긴 구매팀장 알림을 읽는 함수."""
    repo = world.rt.repo
    member = ('hyd', 'role:purchasing-mgr', ME)       # 화면 · API 에는 구성원을 빼는 길이 없다(사람은 담당자 한 명) — 시험만 업무 DB 행을 직접 뺐다 넣는다
    with psycopg.connect(world.dsn, autocommit=True) as db:
        [origin] = db.execute('DELETE FROM role_members WHERE tenant_id=%s AND role_id=%s AND user_id=%s RETURNING origin', member).fetchone()
    before = {n['id'] for n in repo.list_notifications('hyd', ['role:purchasing-mgr'])}
    try:
        yield lambda: [n for n in repo.list_notifications('hyd', ['role:purchasing-mgr']) if n['id'] not in before]
    finally:
        with psycopg.connect(world.dsn, autocommit=True) as db:
            db.execute('INSERT INTO role_members (tenant_id, role_id, user_id, origin) VALUES (%s, %s, %s, %s)', (*member, origin))


def _order(world, card=None):
    """흐름 C 를 발주까지: [재고 보충] → 발주안 제안(AI 자리) → 구매 담당이 카드 하나를 승인(card 가 없으면 추천 카드) → ERP 발주 · 입고 대기 시작.
    돌려줌 = (처리 건 id, 입고 단계의 대기 계획). 입고 단계는 공급사 리드타임을 기다리는 중이어야 한다 — 승인 직후에 입고가 끝나 있으면 실패."""
    alert, pid = _button(world, 'C', dict(by='담당자', user_id=ME, roles=['role:purchasing']))
    assert world.inst(pid)['proc_def_id'] == 'c3_spare'
    decision = world.agent(pid, 'T_agent')
    world.approve(pid, decision, card or world.main.book[decision]['recommended'], BUYER)
    world.poll(2)
    receipt = world.row(pid, 'T_gr')
    assert receipt['status'] == 'SUBMITTED' and world.values(pid).get('goods_receipt') is None and world.inst(pid)['status'] == 'RUNNING', \
        '발주 직후에는 입고 전이다 — 공급사 리드타임을 기다리는 「발주 중」 상태가 있어야 한다'
    return pid, next(e['data']['plan'] for e in world.events(todo=receipt['id']) if e['job_id'] == 'RECEIPT_WAIT')


def _stock(world, part='P-PMP-SEAL'):
    with psycopg.connect(world.dsn) as db:
        return db.execute('SELECT on_hand, reserved, on_order FROM ent.spare_stock WHERE part_no = %s', (part,)).fetchone()


def test_예비품_구매_흐름C는_승인하면_발주하고_리드타임을_기다린_뒤_입고하고_구매팀장에게도_알린다(world):
    """전에는 승인 직후 바로 입고됐다(흐름 설정 immediate) — 학생이 「발주 중」도 납기 지연도 볼 수 없었다. 기다림은 업무 시간(리드타임 5일)을
    배속 × 대기 압축으로 줄인 것이고, 수업에서 학생이 그 상태를 보고 [공급사 납기 지연]을 눌러 볼 만한 길이여야 한다(목표 1분 안팎)."""
    from procsvc import engine
    with _purchasing_manager_notes(world) as notes:
        pid, plan = _order(world)
        lead = world.values(pid)['purchase_order']['after']['lead_d']
        assert plan['real_s'] == pytest.approx(lead * DAY_S / (20 * engine.wait_compression()), abs=0.2) and lead == 5, plan
        assert 30 <= plan['real_s'] <= 90, f"추천 공급사(리드타임 {lead}일)의 입고 대기가 벽시계 {plan['real_s']}초다 — 수업에서 보고 누를 수 있는 1분 안팎이어야 한다"
        world.clock.advance(plan['real_s'] - 2)
        world.poll(2)
        assert world.row(pid, 'T_gr')['status'] == 'SUBMITTED', '입고 예정 전에 입고됐다'
        world.clock.advance(3)
        world.poll(3)
        report = _report(world, pid)
        values = world.values(pid)
        assert report['outcome'] == '입고 완료' and report['refs']['purchase_order'].startswith('PR-') and values['received'] is True
        assert values['approved_amount'] > 300
        assert any('재고 보충 결과' in n['title'] for n in notes()), '금액이 전결 기준(300만원)을 넘으면 구매팀장에게도 알린다'
        assert any('재고 보충 결과' in n['title'] for n in world.rt.repo.list_notifications('hyd', [ME])), '구매 담당(처리 건 참여자)에게도 간다'


def test_예비품_구매_흐름C는_승인_뒤_입고를_기다리는_동안_사건이_승인_뒤_실행_중이고_승인_전에만_여는_문이_닫힌다(world):
    """전에는 승인 → 발주 → 입고(리드타임) 동안 사건이 「승인 대기」였다 — 승인한 뒤인데 사건 목록이 승인 전이라고 말했고, 승인 전에만 여는 문
    (조치 후보 접수 · 원인 진단 바꾸기 · 설비 명령)이 열려 있었으며, 그 사이의 경보 해제를 가리려고 처리 건의 작업 기록을 따로 읽었다."""
    from copy import deepcopy
    from fastapi import HTTPException
    from procsvc import engine
    world.main._entsim_post('/erp/spare/reset', {'part_no': 'P-PMP-SEAL'})
    alert, pid = _button(world, 'C', dict(by='담당자', user_id=ME, roles=['role:purchasing']))
    decision = world.agent(pid, 'T_agent')
    inc = world.incident(pid)
    assert inc.state == 'AWAITING_APPROVAL'
    world.approve(pid, decision, world.main.book[decision]['recommended'], BUYER)
    world.poll(2)
    assert world.row(pid, 'T_gr')['status'] == 'SUBMITTED' and world.values(pid).get('goods_receipt') is None
    assert (inc.state, inc.approved_by, inc.cmd_id) == ('APPROVED_EXECUTING', ME, None)
    assert [h['state'] for h in inc.history] == ['GUIDE_RECEIVED', 'AWAITING_APPROVAL', 'APPROVED_EXECUTING']
    listed = next(i for i in world.api('GET', '/api/incidents')[1] if i['id'] == inc.id)
    assert (listed['state'], listed['terminal']) == ('APPROVED_EXECUTING', False)

    late = dict(deepcopy(world.main.book[decision]), id=decision + '-late')                       # 승인 전에만 여는 문 1: 조치 후보 접수
    late['origin'] = dict(late['origin'], process_scope=dict(late['origin']['process_scope'], workitem=str(uuid.uuid4())))
    with pytest.raises(HTTPException) as refused:
        world.main._store_decision(late)
    assert refused.value.status_code == 409 and '지금 사건: 승인 — 흐름이 실행 중' in refused.value.detail, refused.value.detail
    assert late['id'] not in world.main.book
    with pytest.raises(ValueError, match=r'승인 대기가 아니라\(지금 사건: 승인 — 흐름이 실행 중\) 원인 진단을 바꾸지 않습니다'):   # 문 2: 원인 진단 바꾸기(상태는 이름으로)
        world.rt.hooks.update_incident_card(inc.id, {'causes': []})
    sent = len(world.kafka.of(topics.K_CMD))                                                       # 문 3: 설비 명령
    forged = deepcopy(world.inst(pid))
    engine.set_variables(world.rt.definition_for(forged), forged, {'commands': [{'code': 'FAN_SET', 'fan_pct': 100}]})
    with pytest.raises(ValueError, match='설비 명령이 없는 승인으로 흐름이 실행 중'):
        world.rt._run_command(forged, {'id': str(uuid.uuid4())}, None)
    assert len(world.kafka.of(topics.K_CMD)) == sent and inc.cmd_id is None

    receipt = world.clear_alert(alert)                                                             # 입고 전에 재고 경보가 풀려도
    assert receipt['status'] == 'HANDLED' and receipt['result']['state'] == 'APPROVED_EXECUTING', receipt
    world.poll(2)
    assert inc.cleared and inc.state == 'APPROVED_EXECUTING' and world.inst(pid)['status'] == 'RUNNING', '승인 뒤의 해제는 자연 회복으로 닫지 않는다'
    plan = next(e['data']['plan'] for e in world.events(todo=world.row(pid, 'T_gr')['id']) if e['job_id'] == 'RECEIPT_WAIT')
    world.clock.advance(plan['real_s'] + 1)
    world.poll(3)
    assert _report(world, pid)['outcome'] == '입고 완료' and inc.state == 'CLOSED'
    assert [h['state'] for h in inc.history][-2:] == ['APPROVED_EXECUTING', 'CLOSED']


@pytest.mark.parametrize('card, outcome, received, accepted, rejected, order_state, incident', [
    ('skill:sop-pur-11', '입고 완료', True, 6, 0, '입고 완료', 'CLOSED'),      # 추천: 순정(OEM) — 불량률 2 % × 6개 = 기대 불량 0.12개 → 0개
    ('skill:sop-pur-12', '미달', False, 5, 1, '부분 입고', 'ESCALATED'),       # 지는 안: 대체 승인 공급사 — 12 % × 6개 = 0.72개 → 1개 반품
], ids=['추천 공급사', '불량률이 높은 공급사'])
def test_예비품_구매_흐름C는_고른_공급사의_불량률이_입고_검수_결과로_돌아온다(world, card, outcome, received, accepted, rejected, order_state, incident):
    """전에는 어느 공급사를 골라도 입고 검수가 늘 「합격」이고 로트 번호는 난수였다 — AI 가 불량률로 비교하고 사람이 고른 것이 결과와 이어지지 않았다.
    업무 시스템(모의 공급사)은 발주 수량 × 견적 불량률을 반올림한 개수를 검수에서 걸러 반품하고 합격분만 재고에 올린다(migration 074)."""
    world.main._entsim_post('/erp/spare/reset', {'part_no': 'P-PMP-SEAL'})       # 수업 시작값(실물 3 · 예약 2 · 입고 예정 0)에서
    on_hand, reserved, _ = _stock(world)
    pid, plan = _order(world, card)
    world.clock.advance(plan['real_s'] + 1)
    world.poll(3)
    report = _report(world, pid)
    values = world.values(pid)
    receipt = values['goods_receipt']
    assert (report['outcome'], values['received']) == (outcome, received), report
    assert (receipt['after']['qty'], receipt['after']['rejected_qty'], receipt['after']['ordered_qty']) == (accepted, rejected, 6)
    assert receipt['after']['lot'] == 'LOT-' + values['purchase_order']['ref'], '로트 번호는 발주 번호에서 만든다(난수로 짓지 않는다)'
    assert _stock(world) == (on_hand + accepted, reserved, 0), '합격분만 실물 재고에 오르고 입고 예정은 닫힌다'
    with psycopg.connect(world.dsn) as db:
        assert db.execute('SELECT status FROM ent.purchase_requests WHERE id = %s', (values['purchase_order']['ref'],)).fetchone()[0] == order_state
    assert world.incident(pid).state == incident
    shown = {r['name']: r['value'] for r in report['values']}
    assert shown['입고 수량'] == accepted and shown['가용 재고'] == on_hand + accepted - reserved
    assert shown.get('검수 불합격 · 반품') == (rejected or None), '반품이 있을 때만 그 수량을 측정값에 싣는다'
    assert next(r for r in report['values'] if r['name'] == '입고 수량')['ok'] is received, '입고 수량이 발주 수량과 같은지'
    if rejected:
        assert f'6개 중 {accepted}개 입고 · {rejected}개 검수 불합격 반품' in report['summary'] and '입고 완료가 아닙니다' in report['summary'], report['summary']
        assert '불량률 12 % × 6개 = 기대 불량 0.72개' in report['summary'], '결과 보고가 검수 규칙을 말해야 한다'


def test_예비품_구매_흐름C는_입고를_기다리는_동안_공급사가_납기를_늦추면_지연으로_끝나고_구매팀장에게_보고한다(world):
    """바깥 사건 [공급사 납기 지연](POST /api/scenario/C/delay — 업무 거래 skill:delay-delivery). 열린 발주가 없으면 까닭과 함께 거절하고,
    발주가 열려 있으면 입고 단계가 입고 예정 때 그 통보를 읽어 더 기다리며, 그 사이 납기 초과 타이머(발주 뒤 6일)가 울려 「지연」으로 끝난다."""
    from procsvc import engine
    person = {'by': '담당자', 'user_id': ME, 'roles': ['role:purchasing']}
    world.main._entsim_post('/erp/spare/reset', {'part_no': 'P-PMP-SEAL'})
    status, body = world.api('POST', '/api/scenario/C/delay', person)
    assert status == 409 and '진행 중인 예비품 구매 처리 건이 없어 늦출 발주가 없습니다' in body['detail'], (status, body)
    with _purchasing_manager_notes(world) as notes:
        pid, plan = _order(world)
        ref = world.values(pid)['purchase_order']['ref']
        state = world.api('GET', '/api/scenario/status')[1]['scenarios']['C']['events']
        assert [(e['act'], e['button'], e['enabled'], e['purchase_order']) for e in state] == [('delay', '공급사 납기 지연', True, ref)], state
        status, body = world.api('POST', '/api/scenario/C/delay', person)
        assert status == 200 and body['purchase_order'] == ref and body['instance'] == pid and body['days'] == 5, (status, body)
        again = world.api('POST', '/api/scenario/C/delay', person)
        assert again[0] == 409 and '이미 납기 지연 5일을 알렸습니다' in again[1]['detail'], again
        assert any(e['data'].get('button') == '공급사 납기 지연' and e['data'].get('purchase_order') == ref
                   for e in world.events(pid, job='SCENARIO_BUTTON')), '누름이 그 처리 건 기록에 남아야 한다'
        day = DAY_S / (20 * engine.wait_compression())
        world.clock.advance(plan['real_s'] + 1)                        # 원래 입고 예정(리드타임 5일): 입고하지 않고 늦어진 예정까지 더 기다린다
        world.poll(2)
        receipt = world.row(pid, 'T_gr')
        assert receipt['status'] == 'SUBMITTED' and any(e['job_id'] == 'RECEIPT_DELAYED' for e in world.events(todo=receipt['id'])), receipt['status']
        world.clock.advance(day)                                       # 발주 뒤 6일: 납기 초과
        world.poll(3)
        report = _report(world, pid)
        assert report['outcome'] == '지연' and ref in report['summary'] and '구매팀장에게 보고' in report['summary'], report
        assert world.values(pid).get('goods_receipt') is None and world.row(pid, 'T_gr')['status'] == 'CANCELLED'
        assert any('[지연]' in n['title'] for n in notes()), '납기 초과는 금액과 상관없이 구매팀장에게 보고한다'
    with psycopg.connect(world.dsn) as db:
        assert db.execute('SELECT status, delay_d FROM ent.purchase_requests WHERE id = %s', (ref,)).fetchone() == ('승인됨 → 발주', 5), '입고 전이라 발주는 열려 있다'
    assert world.incident(pid).state == 'ESCALATED'
    assert world.api('GET', '/api/scenario/status')[1]['scenarios']['C']['events'][0]['enabled'] is False


def test_예비품_구매_흐름C에서_거절하면_발주하지_않는다(world):
    alert, pid = _button(world, 'C', dict(by='담당자', user_id=ME, roles=['role:purchasing']))
    decision = world.agent(pid, 'T_agent')
    approve = world.row(pid, 'T_approve', 'IN_PROGRESS')
    world.rt.reject_card(approve['id'], decision, reason='다음 달 예산으로', **BUYER)
    report = _report(world, pid)
    assert report['outcome'] == '반려' and 'purchase_order' not in report['refs']


# ---------------------------------------------------------------- 교대 인수인계 (제공 정의 shift_handover · 가져온 ShiftHandover)
SENDER = RECEIVER = ME                 # 인계자 · 인수자 자리는 역할(role:shift-out · role:shift-in)이고 담당자가 두 역할의 구성원이다
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
    world.forward()
    world.rt.reconcile_projections(limit=200)
    before = _consumer_and_outbox(world, pid, 'T_reobs')
    world.clock.advance(10)
    world.poll(5)
    assert _consumer_and_outbox(world, pid, 'T_reobs') == before


def test_사람_검토_대기열_처리_건은_끝난_사건_정리가_매번_고르지_않는다(world):
    """A-03: 받는 배포 흐름이 없는 경보는 처음부터 사건이 끝난(에스컬레이션) 사람 검토 처리 건이다. 전에는 매 폴링이 그 처리 건의 잠금을 잡고
    아무것도 하지 않은 채 「바꿈 1」로 셌다. 검토 나-4: 사건 카드와 에스컬레이션 사유는 그 실제 까닭(받는 배포 흐름이 없음 — Incident.supported)을
    말한다 — 전에는 「회복 기준이 없어」라고 해, 회복 기준(시계열 태그)이 없어도 받는 내 경보 흐름과 까닭이 섞였다."""
    from procsvc import definition
    alert, pid = world.raise_alert('UNKNOWN_PATTERN_TEST', 'HYD-02')
    inc = world.incident(pid)
    assert world.inst(pid)['proc_def_id'] == 'alert_triage' and inc.state == 'ESCALATED'
    assert world.rt.reconcile_terminal_incidents() == 0
    assert world.row(pid, 'task:triage')['status'] == 'IN_PROGRESS'
    assert inc.card['summary'] == '경보 UNKNOWN_PATTERN_TEST를 받는 배포 흐름이 없어 현장 검토가 필요합니다', inc.card['summary']
    cause, reobserved = definition.escalation_cause(inc.reason)
    assert cause.startswith('이 경보를 받는 배포 흐름이 없어 처리 흐름 대신 현장 검토로 넘겼습니다') and not reobserved, cause
    assert '회복 기준' not in cause + inc.card['summary']


def test_커밋_뒤_효과가_실패하면_처리_건_기록에_쉬운_말로_남는다(world):
    """B-4(하-09): 전에는 커밋 뒤 효과(알림 · 판단 원문 기록 · 감사)의 실패가 로그 한 줄로만 삼켜졌다."""
    with world.storage_fails('notifications', 'true'):
        alert, pid, decision = world.start_cooling()
    failures = world.events(pid, job='POST_COMMIT_EFFECT_FAILED')
    assert failures and '담당자 알림' in failures[-1]['data']['friendly']
    assert world.row(pid, 'T_approve')['status'] == 'IN_PROGRESS', '효과가 실패해도 이미 커밋한 진행은 그대로'


def test_처리_건_하나의_대기_행이_실패해도_같은_바퀴의_다른_처리_건은_진행한다(world):
    """B-11: 전에는 대기 행 처리(reconcile_services)의 소유 전이에 처리 건 단위 try 가 없어, 한 처리 건의 예외가 폴링 한 바퀴를 멈췄다."""
    alert, pid, decision = world.start_cooling()
    tags = world.plant.tags('HYD-01')                               # 둘째 경보는 같은 설비 상태에서(결함을 다시 넣지 않는다 — 넣으면 첫 처리 건 뒤의 바깥 변화다)
    cases = [(alert, pid, decision), (*world.raise_alert(*COOLING, ts1=tags['TS1'], ce=tags['CE']), None)]
    cases[1] = (cases[1][0], cases[1][1], world.agent(cases[1][1], 'T_agent'))
    for alert, pid, decision in cases:                              # 둘 다 같은 설비 값으로 승인한다(앞 명령이 설비를 바꾸기 전 — 바꾼 뒤면 승인 검사가 새 검토를 요구한다)
        world.approve(pid, decision, 'skill:sop-cool-11', OPERATOR)
    world.forward()                                                 # 두 명령을 관문 · PLC 로
    runs = []
    for alert, pid, decision in cases:
        world.clear_alert(alert)                                    # 감지기 자리: 한 설비 · 한 패턴의 경보 둘은 감지기가 따로 풀지 않는다 — 이 시험은 회복이 아니라 폴링의 격리를 잰다
        runs.append((pid, world.row(pid, 'T_reobs')['id']))
    world.settle(15 * 60)                                           # 팬 최대가 된 설비가 창 동안 식는다(값은 설비 모형)
    world.report('HYD-01')
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
def test_추천이_아닌_카드를_승인하면_그_카드의_명령이_설비에_닿는다(world):
    """G5b-13: 전에는 흐름 A 가 늘 추천 카드만 승인했다 — 지는 대안을 고른 학생의 길은 시험에 없었다. 운전원이 승인할 수 있는, 설비 명령이 있는
    지는 대안을 하나 고른다(카드의 모양에 따라 판정 갈래를 바꾸지 않는다 — 그런 카드가 없으면 판단이 지는 대안을 내지 않은 것이라 실패).
    명령 없는 지는 대안(작업지시만)의 길은 카드별 매개변수 시험이 잰다."""
    alert, pid, decision = world.start_cooling()
    d = world.main.book[decision]
    alternative = next((o for o in d['options'] if o['id'] != d['recommended'] and o.get('feasible') and o.get('executable') is not False
                        and o['approver']['id'] == OPERATOR['role'] and any(a.get('kind') == 'command' for a in o.get('actions') or [])), None)
    assert alternative, f"운전원이 승인할 명령 있는 지는 대안이 없다: {[(o['id'], o['approver']['id'], o.get('feasible')) for o in d['options']]}"
    world.approve(pid, decision, alternative['id'], OPERATOR)
    assert world.values(pid)['chosen_option']['id'] == alternative['id'] and world.main.book[decision]['override'] is True
    cmd = world.commanded(pid)
    assert [a['code'] for a in cmd['actions']] == [a['code'] for a in alternative['actions'] if a.get('kind') == 'command']
    assert world.forward()['kind'] == 'ACK'
    _setpoints_follow(world, cmd)                                   # 고른 카드의 명령이 설비 지령이 됐다(추천 카드의 값이 아니라)


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
    with pytest.raises(PermissionError, match=re.escape(NOT_A_PERSON)):
        world.rt.close_agent_task(row['id'], 'OP-17', '수업 단계 밖')       # P1-15: 누가 했는지 모르는 닫기는 받지 않는다
    out = world.rt.close_agent_task(row['id'], ME, '수업 단계에서는 펌프 진단을 하지 않음')
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
    # 취소된 줄을 화면이 「가지 않은 길」과 「하다가 취소됨」으로 가를 사실: 흐름이 닿은 단계만 reached_at 이 있다. 승인 단계는 닿아서 열려 있다가
    # 경보가 풀려 취소됐고, 그 뒤 단계들(상급자 호출 등)은 닿기 전에 예정인 채 취소됐다 — 두 줄 모두 상태는 CANCELLED 이고 start_date 가 있다
    rows = world.rt.instance_view(pid)['workitems']
    cancelled = [w for w in rows if w['status'] == 'CANCELLED' and not w['activity_id'].startswith('ev:')]
    opened, never = [w for w in cancelled if w['reached_at']], [w for w in cancelled if not w['reached_at']]
    assert opened and never and all(w['start_date'] for w in cancelled), [(w['activity_id'], w['reached_at']) for w in cancelled]
    assert 'task:escalate' in {w['activity_id'] for w in never}
    assert all(w['reached_at'] for w in rows if w['status'] == 'DONE')            # 끝난 단계는 모두 닿았던 단계다


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


# ---------------------------------------------------------------- 기준 흐름(anomaly_response) — 거절 길 · 실행하지 않는 카드 · 흐름 A 의 정비 시점
BASE = 'anomaly_response_v22.json'
ACTIONS = {'control': [{'kind': 'command', 'code': 'FAN_SET'}], 'work_order': [{'kind': 'work_order', 'code': 'WO_CREATE'}],
           'purchase': [{'kind': 'transaction', 'code': 'PR_CREATE'}], 'other': []}


@pytest.mark.parametrize('kind, decision, reached', [
    ('control', '승인', 'task:command'),
    ('work_order', '승인', 'task:work-order-only'),
    ('purchase', '승인', 'task:purchase-order'),
    ('other', '승인', 'task:report-no-action'),
    (None, '반려', 'task:report-rejected'),
], ids=['설비 명령', '작업지시만', '발주만', '실행할 조치 없음', '거절'])
def test_기준_흐름은_승인한_카드의_조치_종류마다_갈_길이_있고_거절에도_길이_있다(kind, decision, reached):
    """전수 검사 01 지적 2: 판본 2.3 은 발주만 · 실행할 조치 없음 카드를 승인하면 분기에서 나갈 선이 없어 「진행 멈춤」으로 남았고, 거절 값을 내지
    않아 운전원이 카드를 거절할 길이 없었다. 제공 정의 파일을 실제 엔진으로 승인 단계까지 밀고, 승인 단계의 결과마다 흐름이 닿는 단계를 본다."""
    import json
    from datetime import datetime, timezone
    from conftest import DEFINITIONS
    from procsvc import engine
    from procsvc.instances import action_kind
    defn = engine.Definition.from_dict(json.loads((DEFINITIONS / BASE).read_text(encoding='utf8')))
    t0 = datetime(2026, 11, 14, 9, 0, tzinfo=timezone.utc)
    inst = engine.new_instance(defn, {'asset': 'HYD-02', 'pattern': 'PUMP_LEAKAGE', 'alert': {'alertId': 'A-1'}, 'incident': 'INC-1'}, now=t0)
    rows = {w['activity_id']: w for w in engine.start(defn, inst, now=t0).created}

    def turn_in(activity, output):
        engine.submit(defn, inst, rows[activity], output, now=t0)
        adv = engine.process_submitted(defn, inst, rows[activity], list(rows.values()), now=t0)
        assert not adv.pending, f'{activity} 뒤에 나갈 선이 없어 멈췄다: {rows[activity].get("log")}'
        rows.update({w['activity_id']: w for w in adv.created})
        return adv
    turn_in('task:diagnose', {'cause': 'cause:x', 'failure_mode': 'fm:x', 'guide_card': {}})
    turn_in('task:candidates', {'candidates': ['skill:x']})
    turn_in('task:compliance', {'compliance': {}})
    turn_in('task:rank', {'decision': {}, 'decision_id': 'DEC-1'})
    chosen = {'chosen_skill': 'skill:x', 'chosen_skill_kind': action_kind({'actions': ACTIONS[kind]})} if kind else {}
    adv = turn_in('task:select', dict(chosen, approval=decision, approval_reason='' if kind else '현장 확인 뒤 다시 판단'))
    assert [w['activity_id'] for w in adv.reached if w['activity_id'] in defn.activities] == [reached]


@pytest.mark.parametrize('recovered, path, end', [
    (True, ['task:fix', 'task:reobserve-wo'], 'ev:closed'),
    (False, ['task:fix', 'task:reobserve-wo', 'task:report-wo-failed', 'task:escalate'], 'ev:escalated'),
], ids=['정비 뒤 회복', '정비 뒤 미달'])
def test_기준_흐름의_정비_요청만_갈래는_정비_수행과_효과_확인을_거쳐_결과가_승인한_조치의_효과로_갈린다(recovered, path, end):
    """새8: 판본 2.7 까지는 정비 요청 등록 직후 「처리 완료」였다 — 어떤 정비 요청 카드를 승인해도 결과가 같았다. 2.8 은 흐름 A 처럼 정비 수행 →
    정비 뒤 효과 확인으로 회복을 재고, 회복하지 않으면 미달 결과 보고(사건을 책임자 확인으로) 뒤 책임자 확인 단계다. 제공 정의 파일을 실제 엔진으로."""
    import json
    from datetime import datetime, timezone
    from conftest import DEFINITIONS
    from procsvc import engine
    defn = engine.Definition.from_dict(json.loads((DEFINITIONS / BASE).read_text(encoding='utf8')))
    t0 = datetime(2026, 11, 23, 9, 0, tzinfo=timezone.utc)
    inst = engine.new_instance(defn, {'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION', 'alert': {'alertId': 'A-1'}, 'incident': 'INC-1'}, now=t0)
    rows = {w['activity_id']: w for w in engine.start(defn, inst, now=t0).created}
    reached = []

    def turn_in(activity, output):
        engine.submit(defn, inst, rows[activity], output, now=t0)
        adv = engine.process_submitted(defn, inst, rows[activity], list(rows.values()), now=t0)
        assert not adv.pending, f'{activity} 뒤에 나갈 선이 없어 멈췄다: {rows[activity].get("log")}'
        rows.update({w['activity_id']: w for w in adv.created})
        reached.extend(w['activity_id'] for w in adv.reached if w['activity_id'] in defn.activities)
    turn_in('task:diagnose', {'cause': 'cause:x', 'failure_mode': 'fm:x', 'guide_card': {}})
    turn_in('task:candidates', {'candidates': ['skill:x']})
    turn_in('task:compliance', {'compliance': {}})
    turn_in('task:rank', {'decision': {}, 'decision_id': 'DEC-1'})
    turn_in('task:select', {'chosen_skill': 'skill:x', 'chosen_skill_kind': 'work_order', 'approval': '승인', 'approval_reason': ''})
    assert reached[-1:] == ['task:work-order-only'], reached
    reached.clear()
    turn_in('task:work-order-only', {'work_order': {'ok': True, 'ref': 'WO-1'}})
    turn_in('task:fix', {'maintenance': {}})
    turn_in('task:reobserve-wo', {'recovered': recovered})
    if not recovered:
        turn_in('task:report-wo-failed', {'result_report': {}})
        turn_in('task:escalate', {'note': '정비 뒤에도 유온이 기준 밖 — 다음 조치'})
    assert reached == path, reached
    assert inst['status'] == 'COMPLETED' and inst.get('end_event') == end, (inst['status'], inst.get('end_event'))


def _worker_turns_in(world, pid, activity, output, decision=None):
    """AI 워커가 하는 일을 같은 저장소 함수 · 같은 process 경로로: 그 단계를 점유하고, (판단 단계면) 판단을 process 에 등록하고, 결과를 저장한다.
    기준 흐름의 AI 단계는 수업 재생에 녹화가 없어(수업 밖) 워커를 돌릴 수 없다 — 이 시험이 재는 것은 그 뒤의 사람 단계와 흐름이다."""
    consumer = 'base-flow-test:' + uuid.uuid4().hex[:8]
    [wi] = world.rt.repo.fetch_pending_task('cliagents', consumer, limit=1, tenant_id='hyd', proc_inst_id=pid)
    assert wi['activity_id'] == activity, (wi['activity_id'], activity)
    if decision is not None:
        inst = world.inst(pid)
        scope = {'tenant': 'hyd', 'instance': pid, 'workitem': wi['id'], 'generation': int(wi.get('generation') or 0),
                 'version': inst['proc_def_version'], 'consumer': consumer}
        status, out = world.api('POST', '/api/decisions', dict(decision, origin=dict(decision['origin'], process_scope=scope)))
        assert status == 200, out
    assert world.rt.repo.save_task_result(wi['id'], output, True, consumer)
    world.poll()


def _base_flow_at_approval(world, actions=None):
    """펌프 누설 경보 → 기준 흐름(이 경보를 여는 배포 흐름이 없다) → AI 단계 넷 → 운전원 승인 단계. 돌려줌 = (처리 건 id, 승인 단계 행, 판단 id).
    actions = 시험 카드 가의 동작(주면 그 카드는 실행 검사를 통과한 카드 — feasible)."""
    world.plant.inject('HYD-01', 'pump_leakage', severity='high')
    world.settle(1800)
    alert, pid = world.raise_alert('PUMP_LEAKAGE', 'HYD-01')
    inst = world.inst(pid)
    assert (inst['proc_def_id'], inst['proc_def_version']) == ('anomaly_response', _version(BASE))
    did = 'DEC-BASE-' + uuid.uuid4().hex[:10]
    checked = {'evaluation_mode': 'execution', 'execution_checked': True}      # 판단 엔진이 판단과 카드에 늘 싣는 실행 검사 표시
    decision = {'id': did, 'schema': 'v2', 'asset': 'HYD-01', 'recommended': 'skill:base-test-a', **checked,
                'origin': {'kind': 'alert', 'incident': world.values(pid)['incident'], 'alertId': alert['alertId'], 'pattern': alert['pattern']},
                'roles': {'role:operator': {'level': 1}, 'role:prod-mgr': {'level': 2}},
                'options': [{'id': 'skill:base-test-a', 'sopId': 'SOP-BASE-A', 'name': '시험 카드 가', 'approver': {'id': 'role:operator', 'level': 1},
                             **checked, **({'actions': actions, 'feasible': True} if actions else {})},
                            {'id': 'skill:base-test-b', 'sopId': 'SOP-BASE-B', 'name': '시험 카드 나', 'approver': {'id': 'role:operator', 'level': 1},
                             **checked}]}
    _worker_turns_in(world, pid, 'task:diagnose', {'cause': 'cause:base-test', 'failure_mode': 'fm:base-test', 'guide_card': {'summary': '시험 가이드'}})
    _worker_turns_in(world, pid, 'task:candidates', {'candidates': [o['id'] for o in decision['options']]})
    _worker_turns_in(world, pid, 'task:compliance', {'compliance': {o['id']: {'feasible': True} for o in decision['options']}})
    _worker_turns_in(world, pid, 'task:rank', {'decision': {'recommended': decision['recommended']}, 'decision_id': did}, decision)
    return pid, world.row(pid, 'task:select', 'IN_PROGRESS'), did


def test_기준_흐름의_조치_후보가_빈_목록이면_완료로_넘기지_않고_까닭을_말하는_보류로_돌려보낸다(world):
    """2026-11-23 실측 A8(HYD-02 펌프 누설, 실제 AI): 조치 후보 조회가 빈 목록으로 완료돼, 다음 규정 검토의 AI 가 「후보가 입력되지 않았다 ·
    담당자가 후보 평가를 완료해 제공하라」 — 학생이 할 수 없는 일을 까닭으로 보류했다(진짜 까닭: 그 고장 유형의 조치 방법 지식이 없음). 후보 폼의
    결과 계약(action-candidates-v1)이 빈 목록을 교정으로 돌려보내고, 에이전트가 보류로 내면 처리 건은 그 까닭으로 멈추며 규정 검토는 열리지 않는다.
    같은 후보를 두 번 적은 목록도 돌려보내고, 고친 목록은 다음 단계로 간다."""
    from procsvc import task_deferral
    world.plant.inject('HYD-01', 'pump_leakage', severity='high')
    world.settle(1800)
    alert, pid = world.raise_alert('PUMP_LEAKAGE', 'HYD-01')
    _worker_turns_in(world, pid, 'task:diagnose', {'cause': 'cause:base-test', 'failure_mode': 'fm:base-test', 'guide_card': {'summary': '시험 가이드'}})
    _worker_turns_in(world, pid, 'task:candidates', {'candidates': []})
    row = world.row(pid, 'task:candidates', 'IN_PROGRESS')
    assert (row['draft_status'], row['output'], row['feedback']['attempt']) == ('FB_REQUESTED', None, 1), row
    assert '조치 후보가 빈 목록입니다' in row['feedback']['text'] and '보류 객체로 제출' in row['feedback']['text'], row['feedback']['text']
    assert {w['status'] for w in world.rows(pid) if w['activity_id'] == 'task:compliance'} <= {'TODO'}     # 미리 만든 행은 대기 그대로

    consumer = 'base-flow-test:' + uuid.uuid4().hex[:8]
    [wi] = world.rt.repo.fetch_pending_task('cliagents', consumer, limit=1, tenant_id='hyd', proc_inst_id=pid)
    assert wi['id'] == row['id']
    reason = '펌프 누설에 쓸 조치 방법(정비 절차) 지식이 없어 조치 후보를 고르지 못했습니다 — 펌프 정비 절차가 든 매뉴얼을 적재한 뒤 다시 평가하세요'
    task_deferral.defer(world.rt.repo, 'hyd', wi['id'], expected_consumer=consumer, request_id='defer-' + uuid.uuid4().hex[:8],
                        assessment={'status': 'UNSUPPORTED', 'reason': reason, 'evidence': {'candidates': []}})
    world.poll()
    held = world.row(pid, 'task:candidates', 'PENDING')
    assert held['draft']['_deferral']['reason'] == reason and reason in held['log']
    assert {w['status'] for w in world.rows(pid) if w['activity_id'] == 'task:compliance'} <= {'TODO'}     # 미리 만든 행은 대기 그대로
    assert world.inst(pid)['status'] == 'RUNNING'

    # 두 번째 처리 건: 같은 후보를 두 번 적은 목록은 돌려보내고, 고친 목록은 규정 검토로 간다
    world.plant.inject('HYD-02', 'pump_leakage', severity='high')
    world.settle(1800)
    _, other = world.raise_alert('PUMP_LEAKAGE', 'HYD-02')
    _worker_turns_in(world, other, 'task:diagnose', {'cause': 'cause:base-test', 'failure_mode': 'fm:base-test', 'guide_card': {'summary': '시험 가이드'}})
    _worker_turns_in(world, other, 'task:candidates', {'candidates': ['skill:base-test-a', 'skill:base-test-a']})
    again = world.row(other, 'task:candidates', 'IN_PROGRESS')
    assert '같은 조치 후보를 두 번 적었습니다: skill:base-test-a' in again['feedback']['text'], again['feedback']['text']
    _worker_turns_in(world, other, 'task:candidates', {'candidates': ['skill:base-test-a', 'skill:base-test-b']})
    assert world.row(other, 'task:candidates', 'DONE')['output'] == {'candidates': ['skill:base-test-a', 'skill:base-test-b']}
    world.row(other, 'task:compliance', 'IN_PROGRESS')


def test_기준_흐름에서_운전원이_카드를_거절하면_명령_없이_반려로_끝난다(world):
    """전수 검사 01 지적 2 ①: 판본 2.3 은 거절 요청을 「이 흐름의 승인 단계는 거절 값을 내지 않아…」로 돌려보냈다 — 고르거나 10분을 기다려
    상급자에게 넘기는 길뿐이었다."""
    pid, select, decision = _base_flow_at_approval(world)
    with pytest.raises(PermissionError, match=re.escape(NOT_A_PERSON)):
        world.rt.reject_card(select['id'], decision, by='운전원', role='role:operator', reason='이름만 적은 거절')
    world.rt.reject_card(select['id'], decision, reason='누설량이 기준 안이라 지켜본다', **OPERATOR)
    report = _report(world, pid)
    assert report['outcome'] == '반려' and '누설량이 기준 안이라 지켜본다' in report['summary']
    assert world.inst(pid)['end_event'] == 'ev:rejected' and world.rt.instance_view(pid)['attention'] is None
    assert world.kafka.of(topics.K_CMD) == [], '거절이면 설비 명령을 내지 않는다'
    assert world.incident(pid).state == 'REJECTED_BY_OPERATOR' and world.main.book[decision]['state'] == 'REJECTED'
    assert world.row(pid, 'ev:select-timeout')['status'] == 'CANCELLED', '거절로 닫힌 승인 단계의 시한은 취소된다'


def test_기준_흐름은_발주할_부품_수량이_없는_처리_건에서_발주만_카드를_승인받지_않고_업무_거래를_내지_않는다(world):
    """새7: 전에는 흐름에 발주 단계가 없으면 승인 전달이 기본 제공 업무 시스템에 발주를 냈다(부품 번호 · 수량 · 금액 없이 카드 이름으로) — 흐름은
    「실행하지 않음」으로 보고하는 동안 발주는 이미 나가 있었다. 2.8 은 승인 전달이 거래를 내지 않고 「발주 등록」 단계가 승인 경로가 확정한
    공급사 · 부품 · 수량 · 금액으로 낸다. 센서 경보의 처리 건에는 발주할 부품 · 수량이 없어 금액을 정할 수 없으므로 승인 자체를 받지 않는다."""
    pid, select, decision = _base_flow_at_approval(world, actions=[{'kind': 'transaction', 'code': 'PR_CREATE', 'value': 'sup:a', 'name': '부품 구매요청'}])
    with pytest.raises(ValueError, match='발주할 부품 · 수량이 없습니다'):
        world.rt.select(select['id'], decision, 'skill:base-test-a', **OPERATOR)
    world.poll()
    assert world.row(pid, 'task:select')['status'] == 'IN_PROGRESS' and world.rt.repo.list_approvals(pid, 'hyd') == []
    assert world.row(pid, 'task:purchase-order')['status'] == 'TODO'
    with psycopg.connect(world.dsn) as db:
        assert db.execute('SELECT count(*) FROM ent.purchase_requests WHERE decision_id = %s', (decision,)).fetchone()[0] == 0


def _base_cooling(world):
    """쿨러 경보를 기준 흐름으로 연다 — 수업 흐름까지 경보 경로에서 내린 상태(내 구성 파일의 출발본을 불러온 직후와 같다 — flow_deploy.deploy_reset
    include_class). AI 단계 넷은 AI 가 부르는 판단 엔진 도구 그대로(원인 진단 → 판단 등록 — 키 없는 PC 의 재생은 수업 흐름의 처리 건만 낸다).
    돌려줌 = (경보, 처리 건 id, 판단 id)."""
    from procsvc import flow_deploy
    flow_deploy.deploy_reset(world.rt, ME, '기준 흐름 시험', include_class=True)
    asset = 'HYD-01'
    world.plant.inject(asset, 'cooler_degradation', severity='moderate')
    world.settle(1800)
    world.report(asset)
    tags = world.plant.tags(asset)
    alert, pid = world.raise_alert('COOLER_DEGRADATION', asset, ts1=tags['TS1'], ce=tags['CE'])
    assert (world.inst(pid)['proc_def_id'], world.inst(pid)['proc_def_version']) == ('anomaly_response', _version(BASE))
    with world.reporting():
        world.report()
        diag = _dmn(world, 'diagnose', asset=asset, pattern=alert['pattern'], alert_id=alert['alertId'])
    assert diag.get('withheld') is False and diag['top_cause'] == 'cause:cooler-fin-fouling', json.dumps(diag, ensure_ascii=False)[:600]
    _worker_turns_in(world, pid, 'task:diagnose', {'cause': diag['top_cause'], 'failure_mode': diag['failure_mode'], 'guide_card': diag['card']})
    _worker_turns_in(world, pid, 'task:candidates', {'candidates': ['skill:sop-cool-14']})
    _worker_turns_in(world, pid, 'task:compliance', {'compliance': {}})
    consumer = 'engine-ai:' + uuid.uuid4().hex[:8]
    [wi] = world.rt.repo.fetch_pending_task('cliagents', consumer, limit=1, tenant_id='hyd', proc_inst_id=pid)
    assert wi['activity_id'] == 'task:rank', wi['activity_id']
    scope = {'tenant': 'hyd', 'instance': pid, 'workitem': wi['id'], 'generation': int(wi.get('generation') or 0),
             'version': world.inst(pid)['proc_def_version'], 'consumer': consumer}
    with world.reporting():
        world.report()
        made = _dmn(world, 'submit_decision', asset=asset, pattern=alert['pattern'], cause=diag['top_cause'], failure_mode=diag['failure_mode'],
                    incident=world.values(pid)['incident'], alert_id=alert['alertId'], process_scope=scope)
    assert world.rt.repo.save_task_result(wi['id'], {'decision': {'recommended': made['recommended']}, 'decision_id': made['id']}, True, consumer)
    world.poll()
    return alert, pid, made['id']


def _base_fix_started(world, pid, decision):
    """정비 요청만 카드(SOP-COOL-14 쿨러 핀 세척 — 즉시 시행)를 승인 → 정비 요청 등록 → 정비 수행(같은 설비의 복구) → 정비 뒤 효과 확인 시작."""
    world.report()
    world.rt.select(world.row(pid, 'task:select', 'IN_PROGRESS')['id'], decision, 'skill:sop-cool-14', **MAINT)
    world.poll(3)
    assert world.values(pid)['chosen_skill_kind'] == 'work_order'
    assert world.row(pid, 'task:work-order-only')['status'] == 'DONE' and world.row(pid, 'task:fix')['status'] == 'DONE'
    assert world.values(pid)['maintenance']['restored']['targets'] == {'cooler_health': 1.0}, world.values(pid)['maintenance']
    assert world.row(pid, 'task:reobserve-wo')['status'] != 'DONE', '정비 뒤 효과 확인이 창을 지켜보기 전에 끝났다'
    assert world.kafka.of(topics.K_CMD) == [], '정비 요청만 카드는 설비 명령을 내지 않는다'
    with psycopg.connect(world.dsn) as db:
        assert db.execute('SELECT count(*) FROM ent.work_orders WHERE decision_id = %s', (decision,)).fetchone()[0] == 1


def test_기준_흐름의_정비_요청만_카드는_정비를_수행하고_설비_값으로_회복을_확인해야_처리_완료다(world):
    """새8: 판본 2.7 까지는 정비 요청 등록 즉시 「처리 완료」였다(어느 정비 요청 카드든 같은 결과). 2.8 은 흐름 A 와 같이 정비 수행 뒤 설비가 낸
    값과 감지 규칙의 해제로 회복을 판정한다."""
    alert, pid, decision = _base_cooling(world)
    _base_fix_started(world, pid, decision)
    _effect(world, pid)
    inst = world.inst(pid)
    assert (inst['status'], inst['end_event']) == ('COMPLETED', 'ev:closed'), [(w['activity_id'], w['status']) for w in world.rows(pid)]
    assert world.values(pid)['recovered'] is True and _recovered_on_plant(world, pid) and world.incident(pid).state == 'CLOSED'


def test_기준_흐름의_정비_뒤_효과_확인_중에_결함이_다시_생기면_미달_보고_뒤_책임자_확인이다(world):
    """정비 수행 뒤 효과 확인 창에서 설비가 승인한 조치 밖에서 바뀌면(결함이 다시 생김) 그 값은 정비의 효과가 아니다 — 회복이 아니고, 정비 요청으로
    닫혔던 사건은 그 까닭으로 책임자 확인이 되며, 흐름은 미달 결과 보고 뒤 책임자 확인 단계로 간다(처리 완료로 끝나지 않는다)."""
    alert, pid, decision = _base_cooling(world)
    _base_fix_started(world, pid, decision)
    world.plant.inject('HYD-01', 'cooler_degradation', severity='moderate')
    world.pass_time(WINDOW_S + 1)
    world.poll(2)
    report = world.values(pid)['result_report']
    inc = world.incident(pid)
    assert world.values(pid)['recovered'] is False and report['outcome'] == '미달', report
    assert '승인한 조치 밖에서' in report['summary'] and report['refs'].get('work_order'), report
    assert inc.state == 'ESCALATED' and inc.reason.startswith('OUTSIDE_CHANGE'), (inc.state, inc.reason)
    assert world.inst(pid)['status'] == 'RUNNING' and world.row(pid, 'task:escalate')['status'] == 'IN_PROGRESS'


# ---------------------------------------------------------------- 승인 전달은 효과를 내지 않는다 — 흐름에 그 동작을 내는 단계가 없으면 나가지 않고 그 사실을 말한다(새7)
def _cooling_without_work_order(pid):
    """학생이 그린 냉각 흐름: 판단 → 승인 → 설비 명령 → 효과 확인 → 결과 보고. 정비 요청 단계가 없다."""
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" id="D_{pid}"><bpmn:process id="{pid}" name="냉각 명령만">
  <bpmn:startEvent id="Start" name="쿨러 과열 경보"><bpmn:messageEventDefinition id="M1"/></bpmn:startEvent>
  <bpmn:userTask id="T_agent" name="원인 진단 · 냉각 조치 제안"/>
  <bpmn:userTask id="T_approve" name="운전원 승인"/>
  <bpmn:exclusiveGateway id="G_approved" name="승인?"/>
  <bpmn:serviceTask id="T_cmd" name="냉각 명령"/>
  <bpmn:serviceTask id="T_reobs" name="효과 확인"/>
  <bpmn:exclusiveGateway id="G_ok" name="유온 정상?"/>
  <bpmn:serviceTask id="R_ok" name="결과 보고: 정상"/>
  <bpmn:serviceTask id="R_fail" name="결과 보고: 미달"/>
  <bpmn:serviceTask id="R_rejected" name="결과 보고: 반려"/>
  <bpmn:endEvent id="E_end" name="처리 완료"/>
  <bpmn:endEvent id="E_rejected" name="반려 종결"/>
  <bpmn:sequenceFlow id="F1" sourceRef="Start" targetRef="T_agent"/><bpmn:sequenceFlow id="F2" sourceRef="T_agent" targetRef="T_approve"/>
  <bpmn:sequenceFlow id="F3" sourceRef="T_approve" targetRef="G_approved"/>
  <bpmn:sequenceFlow id="F_approved" name="승인" sourceRef="G_approved" targetRef="T_cmd"/>
  <bpmn:sequenceFlow id="F_rejected" name="반려" sourceRef="G_approved" targetRef="R_rejected"/>
  <bpmn:sequenceFlow id="F4" sourceRef="T_cmd" targetRef="T_reobs"/><bpmn:sequenceFlow id="F5" sourceRef="T_reobs" targetRef="G_ok"/>
  <bpmn:sequenceFlow id="F_yes" name="예" sourceRef="G_ok" targetRef="R_ok"/><bpmn:sequenceFlow id="F_no" name="아니요" sourceRef="G_ok" targetRef="R_fail"/>
  <bpmn:sequenceFlow id="F6" sourceRef="R_ok" targetRef="E_end"/><bpmn:sequenceFlow id="F7" sourceRef="R_fail" targetRef="E_end"/>
  <bpmn:sequenceFlow id="F8" sourceRef="R_rejected" targetRef="E_rejected"/>
</bpmn:process></bpmn:definitions>'''


COOLING_WITHOUT_WO = {
    'name': '냉각 명령만', 'lanes': {}, 'timers': {}, 'start': {'kind': 'alert', 'patterns': ['COOLER_DEGRADATION']},
    'tasks': {'T_agent': {'part': 'task:decide', 'agent': 'agent:cooling', 'instruction': '쿨러 과열의 원인을 진단하고 냉각 조치 후보를 비교해 낸다'},
              'T_approve': {'part': 'task:select-or-reject', 'role': '운전원'},
              'T_cmd': {'part': 'task:command'}, 'T_reobs': {'part': 'task:reobserve'},
              'R_ok': {'part': 'svc:report', 'config': {'outcome': '정상', 'title': '{asset} 냉각 결과', 'summary': '유온 정상 · 경보 해제 — {approved_by_name} 승인'}},
              'R_fail': {'part': 'svc:report', 'config': {'outcome': '미달', 'title': '{asset} 냉각 결과', 'summary': '효과 확인 기준 미달 — {approved_by_name} 승인'}},
              'R_rejected': {'part': 'svc:report', 'config': {'outcome': '반려', 'title': '{asset} 냉각 결과', 'summary': '반려 — 사유: {approval_reason}'}}},
    'flows': {'F_approved': {'var': 'approval', 'op': '==', 'value': '승인'}, 'F_rejected': {'default': True},
              'F_yes': {'var': 'recovered', 'op': '==', 'value': True}, 'F_no': {'default': True}},
}


def test_정비_요청_단계가_없는_흐름에서_정비_요청이_든_안을_승인하면_정비_요청은_나가지_않고_승인_화면과_결과_보고가_그_사실을_말한다(world, pbl):
    """새7(b) · 한 규칙: 승인 전달은 업무 거래를 내지 않고, 정비 요청 · 발주 · 설비 명령은 흐름의 단계가 낸다. PBL 학생 흐름 「승인 → 명령 → 효과 확인 →
    결과 보고」에서 SOP-COOL-13(부하 70 % + 야간 핀 세척 정비 요청)을 승인하면 전에는 정비 요청이 어디에도 등록되지 않고 결과 「정상」, 아무 말도
    없었다. 지금은 승인 화면이 읽는 판단(서버)이 그 안의 정비 요청이 나가지 않는다고 말하고, 명령은 나가며, 결과 보고가 그 사실을 싣는다."""
    from test_student_site_alert import _clean
    from procsvc.instances import skipped_sentence
    did = 'my_cool_' + uuid.uuid4().hex[:6]
    try:
        xml = _cooling_without_work_order(did)
        _ok(world.api('POST', '/api/flows/import', {'xml': xml, 'file_name': f'{did}.bpmn', 'definition_id': did}))
        checked = _ok(world.api('POST', f'/api/flows/{did}/check', {'mapping': COOLING_WITHOUT_WO}))
        assert checked['check']['ok'], checked['check']['problems']
        version = _ok(world.api('POST', f'/api/flows/{did}/register', {'mapping': COOLING_WITHOUT_WO, 'by': ME}), 201)['version']
        _ok(world.api('POST', f'/api/process/definitions/{did}/deploy', {'version': version, 'by': ME, 'reason': '정비 요청 없는 냉각 흐름'}))
        world.plant.inject('HYD-01', 'cooler_degradation', severity='moderate')
        world.settle(1800)
        world.report('HYD-01')
        tags = world.plant.tags('HYD-01')
        alert, pid = world.raise_alert('COOLER_DEGRADATION', 'HYD-01', ts1=tags['TS1'], ce=tags['CE'])
        assert world.inst(pid)['proc_def_id'] == did
        decision = _decided_by_engine(world, pid, alert)
        shown = {o['id']: o for o in _ok(world.api('GET', f'/api/decisions/{decision}'))['options']}
        said = skipped_sentence('냉각 명령만', [{'code': 'WO_CREATE', 'words': '정비 요청'}], done=False)
        assert (shown['skill:sop-cool-13']['flow_skips'], shown['skill:sop-cool-13']['flow_skip_text']) == ([{'code': 'WO_CREATE', 'words': '정비 요청'}], said)
        assert '이 안의 정비 요청을 실행하지 않습니다' in said
        assert (shown['skill:sop-cool-11']['flow_skips'], shown['skill:sop-cool-11']['flow_skip_text']) == ([], None), '명령만인 안은 이 흐름이 모두 낸다'
        card = world.main.book[decision]['options']
        card = next(o for o in card if o['id'] == 'skill:sop-cool-13')
        world.approve(pid, decision, 'skill:sop-cool-13', PEOPLE[card['approver']['id']])
        approval = world.rt.repo.list_approvals(pid, 'hyd')[0]
        assert approval['status'] == 'DELIVERED' and approval['results'] == [], approval
        cmd = world.commanded(pid)
        assert world.forward()['kind'] == 'ACK'
        _setpoints_follow(world, cmd)
        _effect(world, pid)
        report = _report(world, pid)
        assert report['outcome'] == '정상' and report['not_run']['actions'] == [{'code': 'WO_CREATE', 'words': '정비 요청'}], report
        assert report['summary'].endswith('이 흐름 「냉각 명령만」은 승인한 안의 정비 요청을 실행하지 않았습니다 — 그 조치는 나가지 않았습니다'), report['summary']
        with psycopg.connect(world.dsn) as db:
            assert db.execute('SELECT count(*) FROM ent.work_orders WHERE decision_id = %s', (decision,)).fetchone()[0] == 0
    finally:
        _clean(world, did)


def test_수업_흐름_A_B_C와_기준_흐름은_승인한_수업_안의_동작을_모두_자기_단계로_낸다(world):
    """승인 전달이 효과를 내지 않으므로, 수업 흐름의 결과는 흐름 단계가 그 안의 동작을 모두 내는가에 달렸다 — 시작이 설치한 흐름 A · B · C(배포된 판본)와
    기준 흐름(2.8)에서 각 흐름이 받는 안의 동작 모양마다 내지 않는 동작이 없다. 흐름 A 는 발주 단계가 없어 발주가 든 안만 「발주를 실행하지 않습니다」다."""
    from procsvc.instances import skipped_actions
    cmd, wo, change, pr = ({'kind': 'command', 'code': 'FAN_SET'}, {'kind': 'transaction', 'code': 'WO_CREATE'},
                           {'kind': 'transaction', 'code': 'WO_RESCHEDULE'}, {'kind': 'transaction', 'code': 'PR_CREATE'})
    cases = {'c3_cooling': [[cmd], [cmd, wo], [wo]], 'c3_pm': [[wo], [change]], 'c3_spare': [[pr]], 'anomaly_response': [[cmd], [cmd, wo], [wo], [pr]]}
    heads = {h['id']: h['prod_version'] for h in world.rt.repo.deployed_heads('hyd')}
    for did, shapes in cases.items():
        defn = world.rt.definition_for({'proc_def_id': did, 'tenant_id': 'hyd', 'proc_def_version': heads[did]})
        approval = next(a for a, x in defn.activities.items() if x.get('tool') == world.rt.APPROVAL_TOOL)
        for actions in shapes:
            assert skipped_actions(defn, approval, {'id': 'skill:x', 'actions': actions}) == [], (did, actions)
    flow_a = world.rt.definition_for({'proc_def_id': 'c3_cooling', 'tenant_id': 'hyd', 'proc_def_version': heads['c3_cooling']})
    assert skipped_actions(flow_a, 'T_approve', {'id': 'skill:x', 'actions': [pr]}) == [{'code': 'PR_CREATE', 'words': '발주'}]


def _next_window(world, asset):
    """업무 DB(CMMS)의 다가오는 예정된 정비 시간 하나 — 작업지시가 받는 창(ent.next_maintenance_windows)."""
    with psycopg.connect(world.dsn) as db:
        wid, label, starts = db.execute('SELECT id, label, starts_at FROM ent.next_maintenance_windows(%s, 14) ORDER BY starts_at LIMIT 1',
                                        (asset,)).fetchone()
    return {'id': wid, 'label': label, 'starts_at': starts.isoformat()}


def test_흐름A의_정비는_승인한_카드의_예정된_정비_시간까지_기다렸다_수행하고_그_전에는_재관측하지_않는다(world):
    """전수 검사 01 지적 1: 「정비 수행」에 기다릴 시각이 없어, 카드의 정비 시점과 상관없이 작업지시 직후 설비 결함을 지우고 재관측이 늘 「정상」이
    됐다. 수업 지식의 작업지시만 카드(SOP-COOL-14)는 즉시 시행이라, 판단 엔진이 창 규정이 걸린 카드에 싣는 것과 같은 모양의 정비 시점
    (agentsvc.cards.option_window ① — {id, starts_at, name, basis})을 등록된 판단의 그 카드에 싣는다. 창은 업무 DB 의 실제 정비 시간이다."""
    from hydcommon.timeutil import parse_iso
    alert, pid, decision = world.start_cooling()
    window = _next_window(world, 'HYD-01')
    card = next(o for o in world.main.book[decision]['options'] if o['id'] == 'skill:sop-cool-14')
    card['window'] = dict(window, name='이번 예정된 정비 시간', basis='hours_at_next_window')
    world.approve(pid, decision, 'skill:sop-cool-14', MAINT)
    world.poll(3)
    order = world.values(pid)['work_order']
    assert order['after']['window_id'] == window['id'] and parse_iso(order['after']['window_starts_at']) == parse_iso(window['starts_at'])
    fix = world.row(pid, 'T_fix')
    plan = next(e['data']['plan'] for e in world.events(todo=fix['id']) if e['job_id'] == 'WAIT_STARTED')
    from procsvc import engine
    wait_s = (parse_iso(window['starts_at']) - parse_iso(plan['started_at'])).total_seconds() / (20 * engine.wait_compression())   # 배속 20 × 대기 압축(compose 값)
    assert plan['real_s'] == pytest.approx(wait_s, abs=0.2) and plan['real_s'] > 2, plan
    assert fix['status'] != 'DONE' and world.values(pid).get('maintenance') is None, '예정된 정비 시간 전에 정비를 끝냈다'
    assert all(w['status'] == 'TODO' for w in world.rows(pid) if w['activity_id'] == 'T_reobs_wo'), '정비 전에 재관측이 돌았다'
    world.pass_time(plan['real_s'] - 1.5)                            # 기다리는 동안에도 설비는 돈다(결함 그대로 — 유온이 기준 위)
    assert world.row(pid, 'T_fix')['status'] != 'DONE', '예정된 정비 시간 전'
    assert not _recovered_on_plant(world, pid), '정비 전인데 설비가 식었다'
    world.pass_time(3)
    assert world.row(pid, 'T_fix')['status'] == 'DONE' and world.values(pid)['maintenance']['work_order'] == order['ref']
    assert world.row(pid, 'T_reobs_wo')['status'] != 'TODO', '정비 뒤에 재관측이 시작된다'
    _effect(world, pid)                                              # 정비가 같은 설비의 핀 오염을 되돌렸다 — 판정은 설비 모형의 값으로
    assert _report(world, pid)['outcome'] == '정상' and _recovered_on_plant(world, pid)
    assert world.plant.units['HYD-01'].state.cooler_health == 1.0


def test_흐름A의_즉시_시행_카드는_정비를_기다리지_않는다(world):
    alert, pid, decision = world.start_cooling()
    card = next(o for o in world.main.book[decision]['options'] if o['id'] == 'skill:sop-cool-14')
    assert card['window'].get('immediate') is True, '수업 지식의 작업지시만 카드는 지금 정지하고 시행하는 카드다'
    world.approve(pid, decision, 'skill:sop-cool-14', MAINT)
    world.poll(3)
    fix = world.row(pid, 'T_fix')
    assert fix['status'] == 'DONE' and any(e['job_id'] == 'WAIT_SKIPPED' for e in world.events(todo=fix['id']))


@pytest.mark.parametrize('standard', [True, False], ids=['표준 작업이 있는 SOP', '표준 작업이 없는 SOP'])
def test_정비_수행은_표준_작업이_없는_SOP면_부품_소모를_기록하지_않았다고_공지와_결과에_남긴다(world, standard):
    """전수검사 10-G13: 작업지시 완료는 SOP 의 표준 작업(정비 시스템의 부품 · 수량)만큼 부품을 소모한다. 수업 문서 밖의 새 SOP 는 표준 작업 행이 없어
    소모 없이 완료되는데 아무 말이 없었다 — 재고가 그대로라 다음 구매 판단 · 성과 지표가 틀린다. 표준 작업이 있는 SOP(쿨러 핀 세척 — 부품 없음)는
    그 말을 하지 않는다."""
    with psycopg.connect(world.dsn) as db:
        kept = db.execute("SELECT sop, name, from_profile, stop_h, labor_cost, part_no, part_qty FROM ent.task_standards WHERE sop = 'SOP-COOL-14'").fetchone()
        if not standard:
            db.execute("DELETE FROM ent.task_standards WHERE sop = 'SOP-COOL-14'")
    try:
        alert, pid, decision = world.start_cooling()
        world.approve(pid, decision, 'skill:sop-cool-14', MAINT)
        world.poll(3)
        done = world.values(pid)['maintenance']
        said = [e['data'].get('notice') for e in world.events(todo=world.row(pid, 'T_fix')['id']) if e['job_id'] == 'MAINTENANCE_DONE']
    finally:
        if not standard:
            with psycopg.connect(world.dsn) as db:
                db.execute('INSERT INTO ent.task_standards (sop, name, from_profile, stop_h, labor_cost, part_no, part_qty) VALUES (%s,%s,%s,%s,%s,%s,%s)', kept)
    assert done['completed']['ref'] == world.values(pid)['work_order']['ref']
    if standard:
        assert 'parts_note' not in done and '표준 작업' not in done['notice'] and '표준 작업' not in said[0]
    else:
        assert 'SOP-COOL-14의 표준 작업(부품 · 수량)이 없어 부품 소모를 기록하지 않았습니다' in done['parts_note']
        assert done['parts_note'] in done['notice'] and done['parts_note'] in said[0]


def test_흐름A는_즉시_시행도_아니고_정비_시각도_없는_카드의_작업지시를_즉시로_등록하지_않고_그_까닭으로_멈춘다(world):
    """판단 엔진은 예정된 정비 시간을 모르면 카드에 정비 시점을 싣지 않고 그 카드를 실행 후보에서 뺀다(agentsvc.cards — test_cards). 그래도 그런 카드가
    승인돼 오면: 전에는 작업지시가 업무 시스템에 「즉시」로 등록되고(사람이 승인하지 않은 시점) 그 뒤 「정비 수행」이 「언제 할지 모른다」로 멈춰,
    두 단계가 서로 다른 말을 했다. 작업지시 단계가 등록 전에 같은 까닭으로 멈춘다 — 등록된 작업지시 · 정비 · 재관측이 없다."""
    alert, pid, decision = world.start_cooling()
    card = next(o for o in world.main.book[decision]['options'] if o['id'] == 'skill:sop-cool-14')
    card['window'] = None
    with psycopg.connect(world.dsn) as db:
        before = db.execute("SELECT count(*) FROM ent.transactions WHERE asset = 'HYD-01'").fetchone()[0]
    world.approve(pid, decision, 'skill:sop-cool-14', MAINT)
    world.poll(3)
    with psycopg.connect(world.dsn) as db:
        after = db.execute("SELECT count(*) FROM ent.transactions WHERE asset = 'HYD-01'").fetchone()[0]
    assert world.values(pid).get('work_order') is None and after == before, '정비 시점이 없는데 작업지시를 등록했다'
    order = world.row(pid, 'T_wo_only')
    said = json.dumps([e['data'] for e in world.events(pid) if e['event_type'] == 'error'], ensure_ascii=False) + (order.get('log') or '')
    assert order['status'] != 'DONE' and '즉시 시행이 아닌데 정비를 언제 할지 정한 시각이 없습니다' in said and '「쿨러 핀 세척」' in said, said
    assert all(w['status'] == 'TODO' for w in world.rows(pid) if w['activity_id'] in ('T_fix', 'T_reobs_wo')), '작업지시 없이 정비 · 재관측이 돌았다'
    assert world.values(pid).get('maintenance') is None


def test_정비_수행은_작업지시에_예정된_정비_시각이_없으면_바로_정비하지_않고_작업지시_단계와_같은_까닭으로_멈춘다(world):
    """작업지시는 창과 함께 등록됐는데 그 영수증에 시작 시각이 없는 경우(정비 시스템이 창의 시각을 돌려주지 않음) — 「정비 수행」이 그것을 「지금」으로
    읽어 설비 결함을 지우면 하지 않은 정비가 한 것으로 남는다."""
    alert, pid, decision = world.start_cooling()
    window = _next_window(world, 'HYD-01')
    card = next(o for o in world.main.book[decision]['options'] if o['id'] == 'skill:sop-cool-14')
    card['window'] = dict(window, name='이번 예정된 정비 시간', basis='hours_at_next_window')
    real = world.rt.hooks.exec_enterprise

    def without_start(decision_id, item):
        res = real(decision_id, item)
        if item.get('code') == 'WO_CREATE':
            res = dict(res, after={k: v for k, v in (res.get('after') or {}).items() if k != 'window_starts_at'})
        return res
    world.rt.hooks.exec_enterprise = without_start
    try:
        world.approve(pid, decision, 'skill:sop-cool-14', MAINT)
        world.poll(3)
    finally:
        world.rt.hooks.exec_enterprise = real
    assert world.values(pid)['work_order']['ref']
    fix = world.row(pid, 'T_fix')
    said = json.dumps([e['data'] for e in world.events(pid) if e['event_type'] == 'error'], ensure_ascii=False) + (fix.get('log') or '')
    assert fix['status'] != 'DONE' and world.values(pid).get('maintenance') is None, '정비 시각을 모르는데 정비를 끝냈다'
    assert '예정된 정비 시간 값 work_order.after.window_starts_at' in said and '즉시 시행이 아닌데 정비를 언제 할지 정한 시각이 없습니다' in said, said
    assert not any(e['job_id'] in ('WAIT_STARTED', 'WAIT_SKIPPED') for e in world.events(todo=fix['id'])), '기다림을 지어내지 않는다'
    assert all(w['status'] == 'TODO' for w in world.rows(pid) if w['activity_id'] == 'T_reobs_wo'), '정비 전에 재관측이 돌았다'


# ---------------------------------------------------------------- P1-02 같은 질문 다시 보내기
def test_같은_질문을_다시_보내도_엔진이_막_저장한_끝_상태를_덮어쓰지_않는다(world):
    """P1-02: 전에는 잠금 없이 읽은 옛 처리 건 행 전체를 덮어써, 그 사이 엔진이 저장한 답 · 끝 상태를 지웠다."""
    version = _version('ask_agent_v1.json')
    values = {'question': '냉각기 점검 주기는?', 'asked_by': ME}
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
                                  values={'question': '가' * 300_000, 'asked_by': ME})


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


# ---------------------------------------------------------------- 흐름 A: 정비 수행이 고치는 것 = 승인한 조치 방법이 지식에서 줄인다고 한 결함 상태
def test_흐름A의_정비는_승인한_조치가_지식에서_줄인다고_한_결함만_같은_설비에서_되돌리고_그_사실을_공지한다(world):
    """전에는 「정비 수행」이 승인한 카드가 무엇이든 쿨러 결함을 지웠다(흐름 정의의 component: cooler) — 틀린 조치를 승인해도 재관측이 「회복」.
    지금은 승인한 조치 방법이 지식에서 줄인다고 한 외란 변수(영향 관계)만 가상 설비(world 와 같은 한 대)에서 되돌린다(service_parts.maintenance_scope —
    조치 방법마다의 대상은 아래 매개변수 시험). 유온은 설비 모형이 낸 값, 경보 해제는 감지 규칙(world.pass_time).
    (「AI 가 다른 원인을 짚어 그 원인의 조치를 승인 → 핀 오염이 남아 미달」 경우는 지웠다: 판단 등록이 지금 진단의 1순위 원인만 받게 바뀌어
    (dmn-mcp submit_decision — F3 고침) 그 카드가 이 경보에서 나오지 않는다. 판정 F4 「D-3」)"""
    alert, pid, decision = world.start_cooling()
    world.approve(pid, decision, 'skill:sop-cool-14', MAINT)
    world.poll(3)
    done = world.values(pid)['maintenance']
    assert world.row(pid, 'T_fix')['status'] == 'DONE' and world.row(pid, 'T_reobs_wo')['status'] != 'DONE'
    assert [t['id'] for t in done['scope']['targets']] == ['sv:fouling'] and done['restored']['targets'] == {'cooler_health': 1.0}, done
    assert '승인한 조치 방법 SOP-COOL-14가 지식에서 줄인다고 한 쿨러 핀 오염도를 가상 설비에서 정상으로 되돌렸습니다' in done['notice']
    _effect(world, pid)
    report = _report(world, pid)
    assert (report['outcome'], world.incident(pid).state) == ('정상', 'CLOSED'), (report, world.plant.tags('HYD-01'))
    assert world.plant.units['HYD-01'].state.cooler_health == 1.0 and _recovered_on_plant(world, pid)


@pytest.mark.parametrize('sop, targets, why', [
    ('SOP-COOL-14', ['sv:fouling'], None),                                  # 핀 세척 — 영향: 쿨러 핀 오염도를 줄인다
    ('SOP-FAN-11', [], '줄인다는 영향이 없습니다'),   # 쿨러 팬 점검 — 벨트 처짐을 재고 베어링을 확인할 뿐(HM-8.1). 전에는 근본 조치라 베어링 마모를 지웠다(새11)
    ('SOP-COOL-15', [], '줄인다는 영향이 없습니다'),  # 캐비닛 환기 보강 — 수업 지식이 바꾸는 설비 상태를 말하지 않는다
    ('SOP-PM-21', [], '줄인다는 영향이 없습니다'),    # 2,000 h 정기 점검 — 수업 지식에 영향이 없다(구성 요소 전체로 넓히던 짐작을 지움)
    ('SOP-COOL-11', [], '운전값 · 결과값이라 정비가 고치는 상태가 아닙니다'),  # 팬 최대 운전 — 영향은 팬 속도(조작 변수), 설비 명령의 몫
    ('SOP-없는-절차', [], '지식 지도에 조치 방법 SOP-없는-절차가 없어'),
], ids=['결함을 줄이는 조치', '점검 절차', '영향 없는 조치', '영향 없는 정기 점검', '운전값만 움직이는 조치', '지식에 없는 절차'])
def test_정비_수행이_고칠_대상은_승인한_조치_방법이_지식에서_줄인다고_한_결함_상태다(world, sop, targets, why):
    """수업 지식(HM-8 · PM-02 적재분)의 영향 관계(조치 방법 -AFFECTS{sign}-> 상태 변수)에서 외란 변수를 줄이는 것만 고칠 대상이다. 고칠 대상이 없으면
    그 까닭을 말한다 — 정비 수행은 가상 설비를 바꾸지 않고 공지가 그 문장을 싣는다(maintenance_sentence)."""
    from procsvc.service_parts import maintenance_scope, maintenance_sentence
    scope = maintenance_scope(world.rt.hooks.query_cypher, sop)
    assert [(t['id'], t['via']) for t in scope['targets']] == [(t, 'affects') for t in targets], scope
    assert (scope['why'] is None) if why is None else (why in scope['why']), scope
    if not targets:
        assert maintenance_sentence(scope, {'targets': {}}).endswith('가상 설비의 상태는 바꾸지 않았습니다'), scope


# ---------------------------------------------------------------- HYD-01 이 아닌 설비의 경보 → 판단 → 승인 → 명령 → 효과 확인 (T-2)
def _dmn(world, tool, **arguments):
    """판단 엔진 도구 서버(이 묶음의 실제 dmn-mcp) 도구 하나 — AI 가 부르는 것과 같은 길(process 의 도구 호출 함수). 돌려줌 = 문서(document)."""
    from procsvc import mcp_check
    from worker.ai_replay import WRITE_CALL_TIMEOUT_S                  # 재생이 판단 등록을 부를 때와 같은 한도(판단 계산 · 등록이 10초를 넘는다)
    spec = mcp_check.normalize(world.stack.tools['hyd-dmn'])
    out = (mcp_check.call_effect if tool.startswith('submit_') else mcp_check.call)(spec, tool, arguments, max_chars=1_000_000, timeout=WRITE_CALL_TIMEOUT_S)
    assert out['status'] == 'ok' and not out['result']['is_error'], (tool, out.get('error'), (out.get('result') or {}).get('text', '')[:600])
    body = json.loads(out['result']['text'])
    assert body.get('result') == 'ok', (tool, json.dumps(body, ensure_ascii=False)[:600])
    return body['document']


def _decided_by_engine(world, pid, alert):
    """흐름 A 의 AI 단계(원인 진단 · 냉각 조치 제안)를 AI 가 부르는 판단 엔진 도구 그대로 한다: 단계 점유 → 원인 진단(diagnose) → 판단 등록
    (submit_decision — 판단 엔진이 그 처리 건의 실행 범위로 이 설비의 값으로 계산해 등록) → 단계 결과. 키 없는 PC 의 재생은 수업 사례 설비(HYD-01)
    처리 건만 내므로(수업 경계 — 재생 녹화가 그 설비의 것) 다른 설비는 이 길로 잰다. 재는 것은 AI 의 글이 아니라 감지 → 판단 엔진 → 사람 승인 →
    설비 → 효과 확인의 사슬이다. 돌려줌 = 등록된 판단 id."""
    asset, pattern = alert['asset'], alert['pattern']
    consumer = 'engine-ai:' + uuid.uuid4().hex[:8]
    [wi] = world.rt.repo.fetch_pending_task('cliagents', consumer, limit=1, tenant_id='hyd', proc_inst_id=pid)
    assert wi['activity_id'] == 'T_agent', wi['activity_id']
    scope = {'tenant': 'hyd', 'instance': pid, 'workitem': wi['id'], 'generation': int(wi.get('generation') or 0),
             'version': world.inst(pid)['proc_def_version'], 'consumer': consumer}
    with world.reporting():                                         # 태그는 1초마다(시계열). 설비 상태(PLC)는 도구를 부르기 직전에 보고한다 — 판단은 15초 안의 상태만 쓴다
        world.report()
        diag = _dmn(world, 'diagnose', asset=asset, pattern=pattern, alert_id=alert['alertId'])
        assert diag.get('withheld') is False and diag.get('top_cause'), json.dumps(diag, ensure_ascii=False)[:800]
        world.report()
        made = _dmn(world, 'submit_decision', asset=asset, pattern=pattern, cause=diag['top_cause'], failure_mode=diag['failure_mode'],
                    incident=world.values(pid)['incident'], alert_id=alert['alertId'], process_scope=scope)
    output = {'cause': diag['top_cause'], 'failure_mode': diag['failure_mode'], 'guide_card': diag['card'],
              'decision': {'recommended': made['recommended']}, 'decision_id': made['id']}
    assert world.rt.repo.save_task_result(wi['id'], output, True, consumer)
    world.poll()
    return made['id']


def test_HYD01이_아닌_설비의_쿨러_경보도_감지에서_판단_승인_명령_효과_확인까지_설비가_낸_값으로_끝난다(world):
    """T-2: 처리 건을 여는 world 시험은 HYD-01 쿨러 열화뿐이었다(수업 결함 주입 단추가 그 하나다). 다른 설비도 같은 사슬로 돈다: HYD-02 의 쿨러
    핀 오염 → 감지기가 실제 감지 규칙으로 낸 경보 → 흐름 A → 판단 엔진이 HYD-02 의 값으로 진단 · 카드 → 설비 명령이 있는 카드 승인 → 관문 → PLC →
    HYD-02 설비 → 효과 확인. HYD-01 에는 명령이 닿지 않는다. (HYD-02 펌프 누설 · HYD-03 팬 진동은 수업 지식으로 승인까지 가지 못한다 — 판정 보고 T-2)"""
    pattern, asset = COOLING[0], 'HYD-02'
    world.plant.inject(asset, 'cooler_degradation', severity='moderate')
    world.settle(1800)
    alert, pid = world.raise_detected(pattern, asset)
    assert world.inst(pid)['proc_def_id'] == 'c3_cooling' and world.values(pid)['asset'] == asset
    decision = _decided_by_engine(world, pid, alert)
    d = world.main.book[decision]
    assert d['asset'] == asset, d['asset']
    card = next((o for o in d['options'] if o.get('feasible') and o.get('executable') is not False
                 and any(a.get('kind') == 'command' for a in o.get('actions') or [])), None)     # 설비 명령이 있는 카드 — 그 명령이 HYD-02 에 닿는지 잰다
    assert card, f"HYD-02 판단에 설비 명령이 있는 실행 가능한 카드가 없다: {[(o['id'], o.get('feasible')) for o in d['options']]}"
    world.approve(pid, decision, card['id'], PEOPLE[card['approver']['id']])
    cmd = world.commanded(pid)
    assert cmd['asset'] == asset and world.forward()['kind'] == 'ACK', cmd
    _setpoints_follow(world, cmd)
    untouched = world.plant.units['HYD-01']
    assert (untouched.state.fan_pct, untouched.ctrl.last_cmd_id) == (60.0, None), 'HYD-02 의 명령이 HYD-01 에 닿았다'
    _effect(world, pid)
    report = _report(world, pid)
    assert report['outcome'] == ('정상' if _recovered_on_plant(world, pid) else '미달'), (report, world.plant.tags(asset))
    assert report['outcome'] == '정상', (report, world.plant.tags(asset))


@pytest.fixture
def test_run_flow(request, world, pbl):
    """학생이 PBL 에서 배포한 자기 냉각 흐름: 수업 냉각 흐름의 그림 그대로, 정비 뒤 확인 자리(T_reobs_wo)에 효과 확인 대신 「시운전 확인」을 두고
    기준(유온 55 ℃ 미만)과 안정 시간을 적었다. 분기는 시운전 결과 passed 로 간다. request.param = 안정 시간(ISO-8601). 포털과 같은 차례(가져오기 →
    검사 → 판본 등록 → 배포)로 넣고, 끝나면 그 흐름을 지운다."""
    import copy
    from procsvc.course_policy import COURSE_FLOWS
    from test_student_site_alert import _clean
    _, xml, mapping = COURSE_FLOWS['c3_cooling']
    mapping = copy.deepcopy(mapping)
    mapping['name'] = '내 냉각 흐름 — 정비 뒤 시운전'
    mapping['tasks']['T_reobs_wo'] = {'part': 'svc:test-run', 'config': {'criteria': {'TS1': ['<', 55]}, 'settle': request.param}}
    mapping['flows']['F_wo_yes'] = {'var': 'passed', 'op': '==', 'value': True}
    did = 'my_cooling_run_' + uuid.uuid4().hex[:6]
    _ok(world.api('POST', '/api/flows/import', {'xml': xml, 'file_name': f'{did}.bpmn', 'definition_id': did}))
    checked = _ok(world.api('POST', f'/api/flows/{did}/check', {'mapping': mapping}))
    assert checked['check']['ok'], checked['check']['problems']
    version = _ok(world.api('POST', f'/api/flows/{did}/register', {'mapping': mapping, 'by': ME}), 201)['version']
    _ok(world.api('POST', f'/api/process/definitions/{did}/deploy', {'version': version, 'by': ME, 'reason': '내 냉각 흐름(시운전)'}))
    yield did
    _clean(world, did)


@pytest.mark.parametrize('test_run_flow, passes', [('PT30M', True), ('PT1M', False)], indirect=['test_run_flow'],
                         ids=['식을 만큼 안정시킨 뒤', '식기 전에 잰 시운전'])
def test_학생_흐름의_정비_뒤_시운전은_설비가_낸_값을_기준에_대어_통과와_미달로_갈린다(world, test_run_flow, passes):
    """T-5 · D-2: 시운전 확인(svc:test-run)을 실제 흐름으로 돌리는 시험이 없었다(판정 함수의 단위 시험만). 쿨러 핀 오염 경보 → 학생 흐름 → 판단 엔진의
    카드 가운데 핀 세척 작업지시(SOP-COOL-14) 승인 → 정비 요청 → 정비 수행(그 조치가 지식에서 줄이는 핀 오염만 되돌림) → 시운전. 시운전은 안정 시간
    뒤 설비가 실제로 낸 유온을 기준(55 ℃ 미만)에 댄다: 충분히 식은 뒤면 통과 → 정상, 정비 직후(유온이 아직 기준 위)면 미달 → 책임자 확인.
    회복 여부를 시험이 넣지 않는다 — 결과의 측정값은 설비 모형의 값이다."""
    pattern, asset = COOLING
    world.plant.inject(asset, 'cooler_degradation', severity='moderate')
    world.settle(1800)
    alert, pid = world.raise_detected(pattern, asset)
    assert world.inst(pid)['proc_def_id'] == test_run_flow, '쿨러 경보는 학생이 배포한 흐름이 맡는다(기본 제공 흐름보다 먼저)'
    decision = _decided_by_engine(world, pid, alert)
    card = next(o for o in world.main.book[decision]['options'] if o['id'] == 'skill:sop-cool-14')
    assert card.get('feasible') and (card.get('window') or {}).get('immediate') is True, card
    world.approve(pid, decision, card['id'], MAINT)
    world.poll(3)
    done = world.values(pid).get('maintenance') or {}
    assert world.row(pid, 'T_fix')['status'] == 'DONE' and [t['id'] for t in done['scope']['targets']] == ['sv:fouling'], done
    assert world.plant.units[asset].state.cooler_health < 1.0, '정비 복구는 설비 시간에 걸쳐 되돌린다 — 정비 직후에는 아직 오염이 남아 있다'
    hot = world.plant.tags(asset)['TS1']
    assert hot >= 55, f'정비 직후의 유온은 아직 기준 위다({hot})'
    settle_wall_s = (30 if passes else 1) * 60 / world.plant.time_scale        # 안정 시간은 배속만 적용
    world.pass_time(settle_wall_s + 2)
    values = world.values(pid)
    run = values['test_run']
    [reading] = [r for r in run['readings'] if r['tag'] == 'TS1']
    assert reading['value'] == pytest.approx(world.plant.tags(asset)['TS1'], abs=0.5), (reading, world.plant.tags(asset))   # 설비가 낸 값
    assert run['passed'] is values['passed'] is (reading['value'] < 55) is passes, run
    world.poll(3)
    report = _report(world, pid)
    assert report['outcome'] == ('정상' if passes else '미달'), report
    if passes:
        assert world.plant.units[asset].state.cooler_health == 1.0, '충분히 지난 뒤에는 핀 오염이 다 되돌려졌다'


# ---------------------------------------------------------------- 처리 건이 열린 채 일어난 바깥 조작 (T-4 — 판정은 procsvc machine.outside_change)
PRESS = {'by': '담당자', 'user_id': ME, 'roles': ['role:operator']}


def _outside(world, how):
    """처리 건이 열린 채 설비를 승인한 길 밖에서 바꾼다 — 포털 [쿨러 복구](process → plant-sim, world 와 같은 설비) 또는 설비 초기화(plant-sim 의
    초기화와 같은 함수)."""
    if how == 'cooler_restore':
        status, body = world.api('POST', '/api/scenario/A/restore', PRESS)
        assert status == 200, body
    else:
        world.plant.reset(button='설비 초기화', by=ME)


@pytest.mark.parametrize('how', ['cooler_restore', 'plant_reset'], ids=['[쿨러 복구]', '[설비 초기화]'])
def test_승인_대기_중_바깥에서_설비를_되돌려_경보가_풀리면_자연_회복이_아니라_책임자_확인이다(world, how):
    """D-1 · T-4: 승인 대기 중 [쿨러 복구] · [설비 초기화]로 결함을 되돌리면 감지기가 경보를 풀고, 전에는 처리 건이 「자연 회복」으로 닫혔다.
    설비 · 감지기 · 처리 엔진이 한 시간을 산다(world.pass_time) — 해제는 감지 규칙이 정하고, 판정은 처리 엔진의 바깥 변화 규칙이 한다."""
    from procsvc import definition
    alert, pid, decision = world.start_cooling()
    _outside(world, how)
    for _ in range(10):
        world.pass_time(10)                                             # 설비가 보고 → 감지기가 해제선 아래를 60 설비 초 지켜본 뒤 해제([쿨러 복구]는 300 설비 초에 걸쳐 되돌린다)
        if world.incident(pid).cleared:
            break
    inc = world.incident(pid)
    assert inc.cleared, '바깥에서 결함을 되돌렸는데 감지기가 경보를 풀지 않았다(감지 규칙 · 설비 값 확인)'
    assert inc.state == 'ESCALATED' and str(inc.reason).startswith(definition.OUTSIDE_CHANGE), (inc.state, inc.reason)
    assert world.rt.instance_view(pid)['instance'].get('end_label') != '자연 회복'


@pytest.mark.parametrize('how', ['cooler_restore', 'plant_reset'], ids=['[쿨러 복구]', '[설비 초기화]'])
def test_정상_보고_뒤_해제를_기다리는_중_바깥에서_설비를_되돌려_경보가_풀리면_종결이_아니라_책임자_확인이다(world, how):
    """2026-11-25: 정상 결과 보고가 해제를 기다리게 한 사건(AWAITING_CLEAR)의 해제도 승인 대기의 해제와 같이 바깥 변화를 본다 — 보고 뒤 [쿨러 복구] ·
    [설비 초기화]로 풀린 경보를 「결과 보고 뒤 해제로 종결」로 닫으면 학생은 흐름이 고쳤다고 믿는다. 결과 보고 자리는 흐름의 결과 보고 단계가 부르는
    훅(close_incident_result) 그대로이고, 설비 · 감지기 · 원천 접수 · 해제 판정은 실제 길이다."""
    from procsvc import definition
    alert, pid, decision = world.start_cooling()
    inc = world.incident(pid)
    assert world.rt.hooks.close_incident_result(inc.id, 'ok', '정상 — 도구 호출을 마쳤습니다', world.rt._now())
    assert inc.state == 'AWAITING_CLEAR' and not inc.cleared
    _outside(world, how)
    for _ in range(10):
        world.pass_time(10)
        if inc.cleared:
            break
    assert inc.cleared, '바깥에서 결함을 되돌렸는데 감지기가 경보를 풀지 않았다'
    assert inc.state == 'ESCALATED' and str(inc.reason).startswith(definition.CLEAR_UNPROVEN), (inc.state, inc.reason)
    assert f'[{"쿨러 복구" if how == "cooler_restore" else "설비 초기화"}]' in definition.escalation_cause(inc.reason)[0]


@pytest.mark.parametrize('how', ['cooler_restore', 'plant_reset'], ids=['[쿨러 복구]', '[설비 초기화]'])
def test_효과_확인_중_바깥에서_설비를_되돌리면_지는_값을_승인했어도_정상으로_끝나지_않는다(world, how):
    """D-1 · T-4: 팬 값을 낮춰(덜 식는 값) 승인한 뒤 효과 확인 창에서 바깥 조작으로 설비를 되돌리면, 전에는 창 끝의 값과 해제만 보아 「회복 → 정상」이
    승인한 조치 덕으로 적혔다. 바깥 변화 뒤의 값은 조치의 효과가 아니다 — 미달(책임자 확인)과 그 까닭."""
    from procsvc import definition
    alert, pid, decision = world.start_cooling()
    _reviewed_approve(world, pid, decision, 'skill:sop-cool-11', {'fan_pct': 70}, OPERATOR)
    assert world.forward()['kind'] == 'ACK'
    world.pass_time(5)
    _outside(world, how)
    _effect(world, pid)
    report = _report(world, pid)
    inc = world.incident(pid)
    assert report['outcome'] != '정상' and inc.state == 'ESCALATED' and str(inc.reason).startswith(definition.OUTSIDE_CHANGE), (report, inc.reason)


@pytest.mark.parametrize('reset_first, state', [(False, 'RESOLVED_WITHOUT_ACTION'), (True, 'ESCALATED')],
                         ids=['해제 → 초기화 → 해제 처리', '초기화 → 해제 → 해제 처리'])
def test_해제를_늦게_처리해도_해제_뒤에_누른_설비_초기화는_그_해제_전의_바깥_변화가_아니다(world, reset_first, state):
    """검토 의심(2026-11-24): 해제를 처리할 때 그 순간의 마지막 바깥 변화 기록과 견주었다 — 해제가 접수된 뒤 처리가 늦게 돌면(접수 처리 대기 · 다시
    켬) 그 사이 사람이 누른 [설비 초기화]가 해제 전에 일어난 일처럼 세어져 조치 전 자연 회복이 「바깥 변화 — 책임자 확인」이 됐다. 바깥 변화는 해제가
    난 때(해제의 t — 감지기가 싣는 가상 설비 시계)까지만 본다. 그 순서를 실제로 만든다: 해제를 원천 접수로 받기만 하고(처리기는 아직), 설비를
    초기화하고 설비가 그 기록을 실어 보고한 뒤에 처리기를 돌린다. 초기화가 해제보다 먼저였으면 그대로 바깥 변화다."""
    import time
    from datetime import datetime, timezone
    from types import SimpleNamespace
    from conftest import _run_async
    from procsvc import definition
    alert, pid, decision = world.start_cooling()
    if reset_first:
        _outside(world, 'plant_reset')
        world.report('HYD-01')
        time.sleep(0.01)
    cleared = dict(alert, state='CLEAR', t=datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z'))
    time.sleep(0.01)
    record = SimpleNamespace(topic=topics.K_ALERTS, partition=0, offset=next(world.offsets), value=json.dumps(cleared, ensure_ascii=False).encode())
    _run_async(world.main.receive_records([record]))                     # 해제 접수만 — 처리기는 아직 돌지 않았다
    assert not world.incident(pid).cleared
    if not reset_first:
        _outside(world, 'plant_reset')                                    # 해제 뒤에 사람이 [설비 초기화]
        world.report('HYD-01')                                            # 설비가 그 바깥 변화 기록을 실어 보고한다
    world.deliver()                                                       # 이제 해제를 처리한다
    inc = world.incident(pid)
    assert inc.cleared and inc.state == state, (inc.state, inc.reason)
    assert str(inc.reason or '').startswith(definition.OUTSIDE_CHANGE) is reset_first, inc.reason


# ---------------------------------------------------------------- 처리 건의 원인 = 판단의 원인 (검토 가-1) — 고쳐 낼 수 있으면 교정, 아니면 사람에게
def _cooling_alert(world):
    """HYD-01 쿨러 오염(수업 강도)이 끝까지 진행된 설비 → 설비 보고 → 냉각 성능 저하 경보. 돌려줌 = (경보, 처리 건 id)."""
    pattern, asset = COOLING
    world.plant.inject(asset, 'cooler_degradation', severity='moderate')
    world.settle(1800)
    world.report(asset)
    tags = world.plant.tags(asset)
    return world.raise_alert(pattern, asset, ts1=tags['TS1'], ce=tags['CE'])


def _claim_ai(world, pid, activity):
    """AI 워커 자리: 그 단계를 점유한다. 돌려줌 = (행, 점유 이름, 판단 등록의 실행 범위)."""
    consumer = 'engine-ai:' + uuid.uuid4().hex[:8]
    [wi] = world.rt.repo.fetch_pending_task('cliagents', consumer, limit=1, tenant_id='hyd', proc_inst_id=pid)
    assert wi['activity_id'] == activity, (wi['activity_id'], activity)
    scope = {'tenant': 'hyd', 'instance': pid, 'workitem': wi['id'], 'generation': int(wi.get('generation') or 0),
             'version': world.inst(pid)['proc_def_version'], 'consumer': consumer}
    return wi, consumer, scope


WRONG_CAUSE = 'cause:ambient-temperature-rise'      # 냉각 성능 저하 경보의 진단 지식에 있는 다른 원인(주변 온도 상승)


@pytest.mark.parametrize('written, said', [(WRONG_CAUSE, WRONG_CAUSE), (None, '(비움)'), ('', '(비움)')],
                         ids=['다른 원인', '원인을 null 로 비움', '원인을 빈 글로 비움'])
def test_판단을_낸_단계가_결과에_적은_원인이_판단과_다르면_교정으로_돌려보내고_같은_판단으로_고친_결과는_다음_단계로_간다(world, written, said):
    """검토 가-1: 흐름 A 의 판단 단계는 결과에 원인 칸이 있다 — AI 가 등록한 판단(판단 엔진이 지금 값으로 다시 진단한 1순위 원인)과 다른 원인을 적으면
    그 거절은 AI 가 고쳐 낼 수 있는 것이다. 전에는 교정 루프 밖에서 같은 결과를 세 번 다시 판정한 뒤 멈췄다(AI 에게 고칠 기회가 없었다). 지금은 교정
    루프로 돌려보내 무엇이 다르고 무엇을 적어 낼지 말하고, 같은 판단 id 로 고친 결과는 다음 단계(운전원 승인)로 간다. 판단 엔진은 실제 dmn-mcp 다.
    원인 칸을 비워 내는 것(null · 빈 글 — 이 단계의 폼은 진단 칸이 선택이라 받는다)도 판단과 다른 원인이다: 전에는 비운 값을 「견줄 것이 없음」으로
    건너뛰어 대조 없이 다음 단계로 갔고, 처리 건의 원인은 판단에 원인이 있는데도 비었다(감독관 재검토 2026-11-24)."""
    alert, pid = _cooling_alert(world)
    wi, consumer, scope = _claim_ai(world, pid, 'T_agent')
    with world.reporting():
        world.report()
        diag = _dmn(world, 'diagnose', asset=alert['asset'], pattern=alert['pattern'], alert_id=alert['alertId'])
        world.report()
        made = _dmn(world, 'submit_decision', asset=alert['asset'], pattern=alert['pattern'], cause=diag['top_cause'],
                    failure_mode=diag['failure_mode'], incident=world.values(pid)['incident'], alert_id=alert['alertId'], process_scope=scope)
    assert diag['top_cause'] == 'cause:cooler-fin-fouling' != WRONG_CAUSE, diag['top_cause']
    output = {'cause': written, 'failure_mode': diag['failure_mode'], 'guide_card': diag['card'],
              'decision': {'recommended': made['recommended']}, 'decision_id': made['id']}
    assert world.rt.repo.save_task_result(wi['id'], output, True, consumer)
    world.poll()
    row = world.row(pid, 'T_agent')
    assert (row['status'], row['draft_status'], row['output'], (row.get('feedback') or {}).get('attempt'), int(row.get('retry') or 0)) \
        == ('IN_PROGRESS', 'FB_REQUESTED', None, 1, 0), (row['status'], row['draft_status'], row.get('retry'), row.get('log'), world.values(pid).get('cause'))
    text = row['feedback']['text']
    assert f"원인 {said} — 판단은 {diag['top_cause']}" in text and f"cause = {diag['top_cause']}" in text \
        and '같은 decision_id 로 다시 제출하세요' in text, text
    assert world.values(pid).get('cause') is None and world.row(pid, 'T_approve')['status'] != 'IN_PROGRESS'
    again, consumer, _ = _claim_ai(world, pid, 'T_agent')
    assert again['id'] == row['id']
    assert world.rt.repo.save_task_result(again['id'], dict(output, cause=diag['top_cause']), True, consumer)
    world.poll()
    assert world.row(pid, 'T_agent')['status'] == 'DONE' and world.values(pid)['cause'] == diag['top_cause']
    world.row(pid, 'T_approve', 'IN_PROGRESS')


def test_판단을_등록한_단계의_원인이_앞_단계가_정한_원인과_다르면_재시도하지_않고_그_단계부터_다시_하라고_멈춘다(world):
    """검토 가-1: 판단 엔진은 판단을 등록할 때 지금 값으로 다시 진단한 1순위 원인을 쓴다(dmn-mcp submit_decision). 기준 흐름에서 원인 진단 단계가 정한
    원인과 그 원인이 다르면(진단 뒤 설비 값이 바뀜 · 조치 후보 정리만 다시 수행) 전에는 그 거절이 교정 루프 밖에서 세 번 재시도된 뒤 「판단을 등록할 때
    쓴 원인을 결과에 그대로 적으세요」로 멈췄다 — 조치 후보 정리의 결과에는 원인 칸이 없어 따를 수 없는 말이었고, 실제로 풀리는 길(원인 진단부터
    다시)은 말하지 않았다. 지금은 재시도 없이 바로 멈추고 원인을 정한 단계부터 다시 수행하라고 말하며, 그 다시 수행 길은 실제로 열려 있다. 원인 진단
    단계의 결과는 AI 가 그때 본 값으로 정한 원인(주변 온도 상승)이고, 그 뒤 판단 엔진은 설비가 지금 낸 값으로 쿨러 핀 오염을 1순위로 받는다."""
    from procsvc import flow_deploy
    flow_deploy.deploy_reset(world.rt, ME, '기준 흐름 시험', include_class=True)
    alert, pid = _cooling_alert(world)
    assert world.inst(pid)['proc_def_id'] == 'anomaly_response'
    with world.reporting():
        world.report()
        diag = _dmn(world, 'diagnose', asset=alert['asset'], pattern=alert['pattern'], alert_id=alert['alertId'])
    _worker_turns_in(world, pid, 'task:diagnose', {'cause': WRONG_CAUSE, 'failure_mode': diag['failure_mode'], 'guide_card': diag['card']})
    _worker_turns_in(world, pid, 'task:candidates', {'candidates': ['skill:sop-cool-14']})
    _worker_turns_in(world, pid, 'task:compliance', {'compliance': {}})
    wi, consumer, scope = _claim_ai(world, pid, 'task:rank')
    with world.reporting():
        world.report()
        made = _dmn(world, 'submit_decision', asset=alert['asset'], pattern=alert['pattern'], cause=diag['top_cause'],
                    failure_mode=diag['failure_mode'], incident=world.values(pid)['incident'], alert_id=alert['alertId'], process_scope=scope)
    assert diag['top_cause'] == 'cause:cooler-fin-fouling' != WRONG_CAUSE, diag['top_cause']
    assert world.rt.repo.save_task_result(wi['id'], {'decision': {'recommended': made['recommended']}, 'decision_id': made['id']}, True, consumer)
    world.poll()
    row = world.row(pid, 'task:rank')
    assert (row['status'], int(row.get('retry') or 0)) == ('PENDING', 1), (row['status'], row.get('retry'), row.get('log'))
    [error] = [e['data'] for e in world.events(pid) if e['event_type'] == 'error' and e['todo_id'] == row['id']]
    said = error['friendly']
    assert error['recovery'] == 'person', error
    assert said.startswith("'조치 후보 정리' 단계를 진행하지 않고 멈췄습니다") and f"원인 — 처리 건은 {WRONG_CAUSE}, 판단은 {diag['top_cause']}" in said \
        and '「원인 진단」 단계부터 [다시 수행]해 지금 값으로 원인을 다시 정하세요' in said, said
    assert world.row(pid, 'task:select')['status'] != 'IN_PROGRESS' and world.inst(pid)['status'] == 'RUNNING'
    [step] = [s for s in world.rt.instance_view(pid)['attention']['steps'] if s['workitem'] == row['id']]
    assert step['reason'] == said and 'rework' in step['actions'], step
    preview = world.rt.preview_rework(pid, world.row(pid, 'task:diagnose', 'DONE')['id'])
    assert preview['execution_available'] and not preview['blockers'], preview['blockers']


# ---------------------------------------------------------------- 가상 설비 전용 단계는 가상 설비의 처리 건에서만 (검토 가-2) — 실행 쪽
ONE_STEP = '''<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" id="D_ONE"><bpmn:process id="Process_ONE" name="정비 한 단계">
  <bpmn:startEvent id="Start" name="정비 요청 접수"/>
  <bpmn:userTask id="T_ok" name="운전원 승인"/>
  <bpmn:exclusiveGateway id="G_ok" name="승인?"/>
  <bpmn:serviceTask id="T_step" name="설비 정비 · 확인"/>
  <bpmn:endEvent id="E_end" name="끝"/>
  <bpmn:endEvent id="E_no" name="반려"/>
  <bpmn:sequenceFlow id="F1" sourceRef="Start" targetRef="T_ok"/>
  <bpmn:sequenceFlow id="F2" sourceRef="T_ok" targetRef="G_ok"/>
  <bpmn:sequenceFlow id="F_yes" name="승인" sourceRef="G_ok" targetRef="T_step"/>
  <bpmn:sequenceFlow id="F_no" name="반려" sourceRef="G_ok" targetRef="E_no"/>
  <bpmn:sequenceFlow id="F3" sourceRef="T_step" targetRef="E_end"/>
</bpmn:process></bpmn:definitions>'''


@pytest.mark.parametrize('part, config, name', [
    ('svc:maintenance', {}, '정비 수행'),
    ('svc:test-run', {'criteria': {'TS1': ['<', 55]}, 'settle': 'PT1M'}, '시운전 확인'),
], ids=['정비 수행', '시운전 확인'])
def test_가상_설비_전용_단계는_가상_설비가_아닌_처리_건에서_재시도하지_않고_그_까닭으로_멈춘다(world, part, config, name):
    """검토 가-2: 실행 쪽은 처리 건의 설비를 보지 않았다 — 설비 APU-01 의 정비 수행은 설비 시뮬레이터가 모르는 설비라 「설비 시뮬레이터에 정비 복구를
    요청하지 못했습니다 — 시작.bat …」(엉뚱한 까닭)으로 세 번 재시도한 뒤 멈췄고, 시운전 확인은 시계열에 값이 없는 것을 「미달」로 판정해 흐름을 이어
    갔다. 지금은 그 단계가 가상 설비 전용이라는 까닭과 할 일(내 시스템을 부르는 「승인 뒤 MCP 호출」)을 말하며 바로 멈추고, 설비 시뮬레이터 ·
    시계열을 부르지 않는다. 흐름 가져오기는 이런 흐름을 막으므로(test_bpmn_import), 정의는 가져오기로 만들되(가상 설비 셋에서 고르는 시작 칸) 시작
    칸을 글로 바꾼 JSON 을 등록한다 — 시스템 › 관리의 정의 JSON 등록 길(가져오기 검사를 지나지 않는다)과 같다."""
    import copy
    from procsvc import approval_part, bpmn_import, flows_api
    did = 'plant_only_' + uuid.uuid4().hex[:8]
    mapping = {'name': '정비 한 단계', 'lanes': {}, 'timers': {},
               'start': {'kind': 'human', 'fields': [{'key': 'asset', 'text': '설비', 'type': 'select', 'items': list(topics.ASSETS)},
                                                     {'key': 'proposal', 'text': '정비 안', 'type': 'object'}]},
               'tasks': {'T_ok': {'part': 'human:approve', 'role': '운전원', 'config': {'options': 'proposal.options'}},
                         'T_step': {'part': part, 'config': config}},
               'flows': {'F_yes': {'var': 'approval', 'op': '==', 'value': '승인'}, 'F_no': {'default': True}}}
    cat = bpmn_import.catalog(flows_api.default_base_loader(world.rt), world.rt.repo.list_users(None, world.rt.tenant_id))
    checked = bpmn_import.check(bpmn_import.parse_bpmn(ONE_STEP), mapping, {'catalog': cat, 'definition_id': did, 'version': '1',
                                'file_name': 'one-step.bpmn', 'xml_sha256': bpmn_import.xml_sha256(ONE_STEP), 'name': None})
    assert checked['ok'], checked['problems']
    raw = copy.deepcopy(checked['definition'])
    [field] = [f for f in raw['startForm']['fields_json'] if f['key'] == 'asset']
    field.update(type='text')
    field.pop('items')
    world.rt.register_definition(raw)
    pid = world.rt.start_definition(did, raw['version'], 'plant-only:' + uuid.uuid4().hex,
                                    values={'asset': 'APU-01', 'proposal': {'options': [{'slot': 'A', 'reason': '정비'}]}})['proc_inst_id']
    world.poll()
    world.rt.approve(world.row(pid, 'T_ok', 'IN_PROGRESS')['id'], approval_part.APPROVE, 'A', **OPERATOR)
    world.poll(2)
    row = world.row(pid, 'T_step')
    assert (row['status'], int(row.get('retry') or 0)) == ('PENDING', 1), (row['status'], row.get('retry'), row.get('log'))
    [error] = [e['data'] for e in world.events(pid) if e['event_type'] == 'error' and e['todo_id'] == row['id']]
    said = error['friendly']
    assert error['recovery'] == 'person', error
    assert said.startswith(f"'설비 정비 · 확인' 단계를 진행하지 않고 멈췄습니다 — {name}") and '이 처리 건의 설비 APU-01은 가상 설비가 아닙니다' in said \
        and '「승인 뒤 MCP 호출」' in said and '시작.bat' not in said, said
    assert not [e for e in world.events(pid) if e['job_id'] in ('TEST_RUN_STARTED', 'TEST_RUN', 'MAINTENANCE_DONE')]
    assert world.inst(pid)['status'] == 'RUNNING' and world.values(pid).get('test_run') is None and world.values(pid).get('maintenance') is None


# ---------------------------------------------------------------- 승인한 조치가 다루지 않는 결함은 정비가 고치지 않는다 (검토 ④ 가-1 · 의심 — 실제 스택)
def _fix_or_command(pid):
    """학생이 그린 냉각 흐름: 판단 → 승인 → 「팬 최대 + 부하 80 %」 안이면 설비 명령 → 효과 확인, 그 밖의 승인한 안은 정비 수행 → 시운전 확인
    (유온 55 ℃ 미만, 안정 30분). 설비 명령 단계는 다른 갈래에만 있다."""
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" id="D_{pid}"><bpmn:process id="{pid}" name="냉각 명령 또는 정비">
  <bpmn:startEvent id="Start" name="쿨러 과열 경보"><bpmn:messageEventDefinition id="M1"/></bpmn:startEvent>
  <bpmn:userTask id="T_agent" name="원인 진단 · 냉각 조치 제안"/>
  <bpmn:userTask id="T_approve" name="운전원 승인"/>
  <bpmn:exclusiveGateway id="G_approved" name="승인?"/>
  <bpmn:exclusiveGateway id="G_kind" name="팬 최대 · 부하 80 % 안?"/>
  <bpmn:serviceTask id="T_cmd" name="냉각 명령"/>
  <bpmn:serviceTask id="T_reobs" name="효과 확인"/>
  <bpmn:exclusiveGateway id="G_ok" name="유온 정상?"/>
  <bpmn:serviceTask id="T_fix" name="정비 수행"/>
  <bpmn:serviceTask id="T_run" name="시운전 확인"/>
  <bpmn:exclusiveGateway id="G_run" name="시운전 통과?"/>
  <bpmn:serviceTask id="R_ok" name="결과 보고: 정상"/>
  <bpmn:serviceTask id="R_fail" name="결과 보고: 미달"/>
  <bpmn:serviceTask id="R_fix_ok" name="결과 보고: 정비 뒤 정상"/>
  <bpmn:serviceTask id="R_fix_fail" name="결과 보고: 정비 뒤 미달"/>
  <bpmn:serviceTask id="R_rejected" name="결과 보고: 반려"/>
  <bpmn:endEvent id="E_end" name="처리 완료"/>
  <bpmn:endEvent id="E_rejected" name="반려 종결"/>
  <bpmn:sequenceFlow id="F1" sourceRef="Start" targetRef="T_agent"/><bpmn:sequenceFlow id="F2" sourceRef="T_agent" targetRef="T_approve"/>
  <bpmn:sequenceFlow id="F3" sourceRef="T_approve" targetRef="G_approved"/>
  <bpmn:sequenceFlow id="F_approved" name="승인" sourceRef="G_approved" targetRef="G_kind"/>
  <bpmn:sequenceFlow id="F_rejected" name="반려" sourceRef="G_approved" targetRef="R_rejected"/>
  <bpmn:sequenceFlow id="F_cmd" name="예" sourceRef="G_kind" targetRef="T_cmd"/>
  <bpmn:sequenceFlow id="F_fix" name="아니요" sourceRef="G_kind" targetRef="T_fix"/>
  <bpmn:sequenceFlow id="F4" sourceRef="T_cmd" targetRef="T_reobs"/><bpmn:sequenceFlow id="F5" sourceRef="T_reobs" targetRef="G_ok"/>
  <bpmn:sequenceFlow id="F_yes" name="예" sourceRef="G_ok" targetRef="R_ok"/><bpmn:sequenceFlow id="F_no" name="아니요" sourceRef="G_ok" targetRef="R_fail"/>
  <bpmn:sequenceFlow id="F6" sourceRef="T_fix" targetRef="T_run"/><bpmn:sequenceFlow id="F7" sourceRef="T_run" targetRef="G_run"/>
  <bpmn:sequenceFlow id="F_run_yes" name="예" sourceRef="G_run" targetRef="R_fix_ok"/><bpmn:sequenceFlow id="F_run_no" name="아니요" sourceRef="G_run" targetRef="R_fix_fail"/>
  <bpmn:sequenceFlow id="F8" sourceRef="R_ok" targetRef="E_end"/><bpmn:sequenceFlow id="F9" sourceRef="R_fail" targetRef="E_end"/>
  <bpmn:sequenceFlow id="F10" sourceRef="R_fix_ok" targetRef="E_end"/><bpmn:sequenceFlow id="F11" sourceRef="R_fix_fail" targetRef="E_end"/>
  <bpmn:sequenceFlow id="F12" sourceRef="R_rejected" targetRef="E_rejected"/>
</bpmn:process></bpmn:definitions>'''


FIX_OR_COMMAND = {
    'name': '냉각 명령 또는 정비', 'lanes': {}, 'timers': {}, 'start': {'kind': 'alert', 'patterns': ['COOLER_DEGRADATION']},
    'tasks': {'T_agent': {'part': 'task:decide', 'agent': 'agent:cooling', 'instruction': '쿨러 과열의 원인을 진단하고 냉각 조치 후보를 비교해 낸다'},
              'T_approve': {'part': 'task:select-or-reject', 'role': '운전원'},
              'T_cmd': {'part': 'task:command'}, 'T_reobs': {'part': 'task:reobserve'},
              'T_fix': {'part': 'svc:maintenance', 'config': {}},
              'T_run': {'part': 'svc:test-run', 'config': {'criteria': {'TS1': ['<', 55]}, 'settle': 'PT30M'}},
              'R_ok': {'part': 'svc:report', 'config': {'outcome': '정상', 'title': '{asset} 냉각 결과', 'summary': '유온 정상 — {approved_by_name} 승인'}},
              'R_fail': {'part': 'svc:report', 'config': {'outcome': '미달', 'title': '{asset} 냉각 결과', 'summary': '효과 확인 기준 미달 — {approved_by_name} 승인'}},
              'R_fix_ok': {'part': 'svc:report', 'config': {'outcome': '정상', 'title': '{asset} 정비 결과', 'summary': '정비 뒤 시운전 통과 — {approved_by_name} 승인'}},
              'R_fix_fail': {'part': 'svc:report', 'config': {'outcome': '미달', 'title': '{asset} 정비 결과', 'summary': '정비 뒤 시운전 미달 — {approved_by_name} 승인'}},
              'R_rejected': {'part': 'svc:report', 'config': {'outcome': '반려', 'title': '{asset} 냉각 결과', 'summary': '반려 — 사유: {approval_reason}'}}},
    'flows': {'F_approved': {'var': 'approval', 'op': '==', 'value': '승인'}, 'F_rejected': {'default': True},
              'F_cmd': {'var': 'chosen_skill', 'op': '==', 'value': 'skill:sop-cool-12'}, 'F_fix': {'default': True},
              'F_yes': {'var': 'recovered', 'op': '==', 'value': True}, 'F_no': {'default': True},
              'F_run_yes': {'var': 'passed', 'op': '==', 'value': True}, 'F_run_no': {'default': True}},
}


def test_승인한_조치가_결함을_줄이지_않으면_정비는_설비를_고치지_않아_시운전에서_미달이고_명령이_든_안이_명령_없는_갈래로_가도_사건은_승인_뒤_실행_중이다(world, pbl):
    """검토 ④: 「틀린 정비는 설비를 고치지 않는다」를 실제 스택에서 재던 시험(SOP-COOL-15 — 판단 등록이 지금 진단의 1순위 원인만 받게 바뀌어 그
    카드가 이 경보에서 나오지 않아 지웠다)을 같은 갈래로 되살린다: 판단 엔진이 실제로 낸 카드 가운데 결함(쿨러 핀 오염)을 줄이지 않는 「팬 최대 운전」
    (SOP-COOL-11 — 영향은 팬 속도, 운전값)을 학생 흐름의 정비 갈래로 승인한다. 정비 수행은 승인한 조치 방법이 지식에서 줄인다고 한 결함만 되돌리므로
    빈 범위를 설비 시뮬레이터에 보내고(범위를 빼면 시뮬레이터는 결함 전부를 되돌린다), 핀 오염은 그대로 남아 시운전이 설비가 낸 유온으로 미달이다.
    검토 의심(사건 승인 대기 남음): 이 안에는 설비 명령이 있고 흐름의 다른 갈래에 설비 명령 단계가 있다 — 전에는 「흐름 어딘가에 명령 단계」로 보아
    사건을 승인 대기로 두었다. 이 카드가 실제로 갈 길에는 명령 단계가 없으므로 사건은 「승인 — 흐름이 실행 중」이다."""
    from test_student_site_alert import _clean
    did = 'my_cool_fix_' + uuid.uuid4().hex[:6]
    try:
        xml = _fix_or_command(did)
        _ok(world.api('POST', '/api/flows/import', {'xml': xml, 'file_name': f'{did}.bpmn', 'definition_id': did}))
        checked = _ok(world.api('POST', f'/api/flows/{did}/check', {'mapping': FIX_OR_COMMAND}))
        assert checked['check']['ok'], checked['check']['problems']
        version = _ok(world.api('POST', f'/api/flows/{did}/register', {'mapping': FIX_OR_COMMAND, 'by': ME}), 201)['version']
        _ok(world.api('POST', f'/api/process/definitions/{did}/deploy', {'version': version, 'by': ME, 'reason': '명령 또는 정비 냉각 흐름'}))
        alert, pid = _cooling_alert(world)
        assert world.inst(pid)['proc_def_id'] == did
        decision = _decided_by_engine(world, pid, alert)
        card = next(o for o in world.main.book[decision]['options'] if o['id'] == 'skill:sop-cool-11')
        assert card.get('feasible') and any(a.get('kind') == 'command' for a in card.get('actions') or []), card
        shown = {o['id']: o for o in _ok(world.api('GET', f'/api/decisions/{decision}'))['options']}
        assert [s['words'] for s in shown['skill:sop-cool-11']['flow_skips']] == ['설비 명령'], shown['skill:sop-cool-11']['flow_skips']
        world.approve(pid, decision, card['id'], PEOPLE[card['approver']['id']])
        assert world.incident(pid).state == 'APPROVED_EXECUTING', world.incident(pid).state
        world.poll(3)
        assert world.kafka.of(topics.K_CMD) == [], '이 갈래에는 설비 명령이 없다'
        done = world.values(pid)['maintenance']
        assert world.row(pid, 'T_fix')['status'] == 'DONE' and done['scope']['targets'] == [] and done['restored']['targets'] == {}, done
        assert '운전값 · 결과값이라 정비가 고치는 상태가 아닙니다' in done['scope']['why'] and done['notice'].endswith('가상 설비의 상태는 바꾸지 않았습니다'), done
        world.pass_time(30 * 60 / world.plant.time_scale + 2)                   # 시운전 안정 시간(배속만 적용)
        world.poll(3)
        run = world.values(pid)['test_run']
        [reading] = [r for r in run['readings'] if r['tag'] == 'TS1']
        assert run['passed'] is False and reading['value'] >= 55, run
        assert reading['value'] == pytest.approx(world.plant.tags('HYD-01')['TS1'], abs=0.5), (reading, world.plant.tags('HYD-01'))
        assert world.plant.units['HYD-01'].state.cooler_health < 1.0, '결함을 줄이지 않는 조치를 승인했는데 핀 오염이 사라졌다'
        report = _report(world, pid)
        assert report['outcome'] == '미달' and world.incident(pid).state == 'ESCALATED', (report, world.incident(pid).state)
    finally:
        _clean(world, did)


# ---------------------------------------------------------------- 「승인한 내용 그대로 다시 보내기」는 승인 뒤 효과 단계에서만 (감독관 재검토 2026-11-24 — 실제 스택)
def _check_then_order(did):
    """학생 흐름: 시작 → 재고 읽기 확인(승인 앞 · effect: false) → 주문 승인 → 승인이면 비품 주문 넣기(승인 뒤 쓰기)."""
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" id="D_{did}"><bpmn:process id="{did}" name="재고 확인 뒤 주문">
  <bpmn:startEvent id="Start" name="재주문 요청"/>
  <bpmn:serviceTask id="T_check" name="재고 읽기 확인"/>
  <bpmn:userTask id="T_ok" name="주문 승인"/>
  <bpmn:exclusiveGateway id="G_ok" name="승인?"/>
  <bpmn:serviceTask id="T_order" name="비품 주문 넣기"/>
  <bpmn:endEvent id="E_done" name="주문 완료"/>
  <bpmn:endEvent id="E_no" name="반려"/>
  <bpmn:sequenceFlow id="F1" sourceRef="Start" targetRef="T_check"/>
  <bpmn:sequenceFlow id="F2" sourceRef="T_check" targetRef="T_ok"/>
  <bpmn:sequenceFlow id="F3" sourceRef="T_ok" targetRef="G_ok"/>
  <bpmn:sequenceFlow id="F_yes" name="승인" sourceRef="G_ok" targetRef="T_order"/>
  <bpmn:sequenceFlow id="F_no" name="반려" sourceRef="G_ok" targetRef="E_no"/>
  <bpmn:sequenceFlow id="F4" sourceRef="T_order" targetRef="E_done"/>
</bpmn:process></bpmn:definitions>'''


def test_승인_앞_읽기_확인이_멈추면_다시_수행을_말하고_승인한_내용을_다시_보내지_않으며_승인_뒤_쓰기가_멈추면_승인한_내용_그대로_다시_보낸다(world, linked, system):
    """감독관 재검토: 「승인한 내용 그대로 다시 보내기」를 도구 이름(정비 요청 등록 · MCP 호출)으로 가렸다. 승인 앞에 둘 수 있는 읽기 확인(MCP 호출,
    effect: false)도 같은 도구 이름이라, 읽기 확인이 세 번 실패해 멈추면 까닭 문장 · 멈춘 단계의 행동 · 화면이 「승인한 내용 그대로 [같은 내용
    다시 전달]」을 안내했고, 그 요청은 「승인 기록이 없어」로 거절됐다 — 학생은 없는 승인이 있다고 믿게 됐다. 지금은 단계의 성격(바깥에 효과를 내는
    승인 뒤 단계)으로 한 곳에서 가린다(instances.approved_resend). 같은 처리 건에서 두 갈래를 모두 밟는다: 승인 앞 읽기 확인은 [다시 수행]을 말하고
    그 길로 실제로 이어지며, 승인 뒤 쓰기는 [같은 내용 다시 전달]을 말하고 그 승인의 역할로 승인한 수량 그대로 한 번 나간다. 서버는 이 시험만의 이름으로
    등록한다 — 도구 호출 기록(/api/mcp/calls)은 서버 · 도구 이름으로 모이므로, linked 의 서버 이름을 쓰면 다른 시험이 보는 기록에 이 시험의 호출이 섞인다."""
    from test_student_system_link import ITEM, PROPOSAL, READ, ROLE_ID, ROLE_NAME, WRITE, _approve
    from procsvc import approval_part, instances
    did, mine = 'office_check_' + uuid.uuid4().hex[:6], 'office-stock-check'
    server = {'name': mine, 'url': system.url, 'description': '사내 비품 재고(읽기 확인 뒤 주문)', 'by': ME}
    _ok(world.api('POST', '/api/mcp/servers', server), 201)
    mapping = {'name': '재고 확인 뒤 주문', 'lanes': {}, 'timers': {},
               'start': {'kind': 'human', 'fields': [{'key': 'item', 'text': '품목', 'type': 'text'}, {'key': 'proposal', 'text': '주문안', 'type': 'object'}]},
               'tasks': {'T_check': {'part': 'svc:mcp-call', 'inputs': ['item'],
                                     'config': {'server': mine, 'tool': READ, 'arguments': {'item': '{item}'}, 'output': 'stock', 'effect': False}},
                         'T_ok': {'part': 'human:approve', 'role': ROLE_NAME, 'config': {'options': 'proposal.options', 'recommended': 'proposal.recommended'}},
                         'T_order': {'part': 'svc:mcp-call', 'inputs': ['item'],
                                     'config': {'server': mine, 'tool': WRITE, 'arguments': {'item': '{item}', 'qty': '{approved_option.qty}'}}}},
               'flows': {'F_yes': {'var': 'approval', 'op': '==', 'value': approval_part.APPROVE}, 'F_no': {'default': True}}}
    _ok(world.api('POST', '/api/flows/import', {'xml': _check_then_order(did), 'file_name': f'{did}.bpmn', 'definition_id': did}))
    checked = _ok(world.api('POST', f'/api/flows/{did}/check', {'mapping': mapping}))
    assert checked['check']['ok'], checked['check']['problems']                  # 읽기 확인은 효과가 아니라 승인 앞에 둘 수 있다
    version = _ok(world.api('POST', f'/api/flows/{did}/register', {'mapping': mapping, 'by': ME}), 201)['version']

    def stopped_at(pid, activity):
        row = world.row(pid, activity)
        assert row['status'] == 'PENDING' and int(row['retry']) == 3, (row['status'], row.get('retry'), row.get('log'))
        error = world._failure(row)
        [step] = [s for s in _ok(world.api('GET', f'/api/instances/{pid}'))['attention']['steps'] if s['workitem'] == row['id']]
        return row, error, step

    # ① 승인 앞 읽기 확인: 부를 서버가 없어 세 번 실패해 멈춘다(아무것도 보내지 않음)
    _ok(world.api('DELETE', f'/api/mcp/servers/{mine}?by={ME}&force=true'))
    pid = _ok(world.api('POST', '/api/instances/start', {'definition_id': did, 'version': version, 'event_id': 'office:' + uuid.uuid4().hex,
                                                        'variables': {'item': ITEM, 'proposal': PROPOSAL}}))['proc_inst_id']
    world.poll(5)
    row, error, step = stopped_at(pid, 'T_check')
    said = error['friendly']
    assert world.values(pid).get('approved_by') is None and system.called(READ) == []
    assert f"도구 서버 '{mine}'가 등록되어 있지 않습니다" in said and '[다시 수행]' in said, said
    assert '[같은 내용 다시 전달]' not in said and '승인한 내용' not in said, said                 # 없는 승인을 말하지 않는다
    assert error['recovery'] == 'bounded_retry' and step['actions'] == ['rework', 'close'] and 'retry_role' not in step, (error['recovery'], step)
    status, refused = world.api('POST', f"/api/todolist/{row['id']}/effect-retry", {'by': ME, 'role': ROLE_ID})
    assert status == 409 and '다시 보낼 수 있는 단계가 아닙니다' in str(refused), refused
    # 말한 길([다시 수행])이 실제로 열려 있다: 서버를 다시 등록하고 그 단계부터 다시 수행하면 읽고 승인 앞까지 간다
    _ok(world.api('POST', '/api/mcp/servers', server), 201)
    preview = _ok(world.api('GET', f"/api/instances/{pid}/rework-preview?workitem_id={row['id']}"))
    assert preview['blockers'] == [], preview['blockers']
    _ok(world.api('POST', f'/api/instances/{pid}/rework', {'workitem_id': row['id'], 'snapshot_token': preview['snapshot_token'],
                                                          'request_id': str(uuid.uuid4()), 'by': ME, 'role': ROLE_ID, 'reason': '도구 서버를 다시 등록함'}))
    world.poll(3)
    assert system.called(READ) == [{'item': ITEM}] and world.row(pid, 'T_check')['status'] == 'DONE'
    world.row(pid, 'T_ok', 'IN_PROGRESS')

    # ② 승인 뒤 쓰기: 승인 직전에 서버 등록이 사라져 세 번 실패해 멈춘다(아무것도 보내지 않음)
    _ok(world.api('DELETE', f'/api/mcp/servers/{mine}?by={ME}&force=true'))
    _ok(_approve(world, pid, approval_part.APPROVE, option='A'))
    world.poll(5)
    row, error, step = stopped_at(pid, 'T_order')
    said = error['friendly']
    assert system.called(WRITE) == [] and world.values(pid)['approved_by'] == ME
    assert '[같은 내용 다시 전달]' in said and '[다시 수행]' not in said, said
    assert error['recovery'] == instances.RESEND and step['actions'] == ['effect_retry', 'rework', 'close'], (error['recovery'], step)
    assert step['retry_role'] == ROLE_ID, step                                           # 화면이 보낼 역할은 서버가 그 승인에서 읽어 준다
    _ok(world.api('POST', '/api/mcp/servers', server), 201)
    _ok(world.api('POST', f"/api/todolist/{row['id']}/effect-retry", {'by': ME, 'role': step['retry_role']}))
    world.poll(5)
    inst = world.inst(pid)
    assert (inst['status'], inst['end_event']) == ('COMPLETED', 'E_done'), [(w['activity_id'], w['status'], w.get('log')) for w in world.rows(pid)]
    assert [(o['item'], o['qty']) for o in system.called(WRITE)] == [(ITEM, 2)]                # 승인한 안 그대로, 정확히 한 번
