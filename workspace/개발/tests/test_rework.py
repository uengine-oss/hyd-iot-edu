"""다시 수행 계획(procsvc/rework.py) — 막힘마다 학생이 읽는 문장(무엇이 · 왜 · 다음에 무엇을)을 서버가 함께 주고, 막히면 그 문장으로 거절한다.

막힘 문장의 정본은 rework.BLOCKER_TEXT 한 곳이다(포털 instanceRework.js 는 그 문장을 그대로 보인다). 실제 흐름 A(냉각)를 실제 엔진 · DB 로
돌려 학생이 [영향 확인]을 누르는 자리(preview_rework)와 [다시 수행]을 누르는 자리(request_rework)를 본다.
"""
import uuid

import pytest

from conftest import OPERATOR
from procsvc import rework

CODE_RE = r'[a-z]+(?:_[a-z]+){2,}'          # 막힘 코드 꼴(incident_command_in_flight) — 학생 문장에 나오지 않는다


@pytest.mark.parametrize('code', sorted(rework.BLOCKER_TEXT))
def test_막힘_코드마다_무엇이_왜_다음에_무엇을_말하는_한국어_문장이_있다(code):
    text = rework.blocker(code)['text']
    assert ' — ' in text and not __import__('re').search(CODE_RE, text), text


def test_문장이_없는_막힘_코드는_만든_자리에서_실패한다():
    """P4-03 · W1-09: 전에는 화면 사전에 없는 코드가 「지원 범위를 확인해야 합니다」로 그려졌다 — 이제 코드를 만드는 곳에서 바로 실패한다."""
    with pytest.raises(KeyError, match='made_up_blocker'):
        rework.blocker('made_up_blocker', workitem='x')


def test_막힘의_세부_칸은_코드_문장과_함께_그대로_남는다():
    assert rework.blocker('variable_provenance_requires_review', variable='decision') == {
        'code': 'variable_provenance_requires_review', 'text': rework.BLOCKER_TEXT['variable_provenance_requires_review'], 'variable': 'decision'}


def test_거절_문장은_겹친_막힘을_한_번씩만_말한다():
    blockers = [rework.blocker('approval_requires_review', workitem='a'), rework.blocker('approval_requires_review', workitem='b'),
                rework.blocker('instance_not_running')]
    message = rework.blocked_message(blockers)
    assert message.count(rework.BLOCKER_TEXT['approval_requires_review']) == 1 and message.startswith('다시 수행할 수 없습니다: ')


# ---------------------------------------------------------------- 실제 흐름 A 에서
def test_명령_응답을_기다리는_사건을_다시_수행하려_하면_응답_뒤에_다시_확인하라고_말한다(world):
    """P4-03: 명령이 오가는 동안의 막힘(incident_command_in_flight)이 화면 사전에 없어 「지원 범위를 확인해야 합니다」로 보였다."""
    alert, pid, decision = world.start_cooling()
    world.approve(pid, decision, 'skill:sop-cool-11', OPERATOR)
    world.commanded(pid)
    plan = world.rt.preview_rework(pid, world.row(pid, 'T_agent')['id'])
    blockers = {b['code']: b['text'] for b in plan['blockers']}
    assert blockers.get('incident_command_in_flight') == '설비 명령의 응답(ACK)을 기다리는 중입니다 — 응답이 온 뒤 영향 확인을 다시 누르세요.', blockers
    assert all(b['text'] == rework.BLOCKER_TEXT[b['code']] for b in plan['blockers'])
    assert plan['execution_available'] is False


def test_막힌_다시_수행을_요청하면_코드가_아니라_학생_문장으로_거절한다(world):
    alert, pid, decision = world.start_cooling()
    world.approve(pid, decision, 'skill:sop-cool-11', OPERATOR)
    world.commanded(pid)
    agent = world.row(pid, 'T_agent')
    plan = world.rt.preview_rework(pid, agent['id'])
    with pytest.raises(ValueError) as caught:
        world.rt.request_rework(pid, agent['id'], str(uuid.uuid4()), plan['snapshot_token'], OPERATOR['by'], OPERATOR['role'], '다시 판단')
    message = str(caught.value)
    assert message.startswith('다시 수행할 수 없습니다: ') and '설비 명령의 응답(ACK)을 기다리는 중' in message
    assert not __import__('re').search(CODE_RE, message), message


def test_효과가_남은_사건의_막힘은_실행_효과를_정리하라는_한_가지만_말한다(world):
    """ACK 뒤(명령이라는 효과가 남음) — 전에는 「사건이 이미 끝났다」(incident_not_active_for_rework)가 효과 막힘과 함께 붙어 틀린 말을 했다."""
    alert, pid, decision = world.start_cooling()
    world.approve(pid, decision, 'skill:sop-cool-11', OPERATOR)
    cmd = world.commanded(pid)
    world.ack('HYD-01', cmd['cmdId'])
    plan = world.rt.preview_rework(pid, world.row(pid, 'T_agent')['id'])
    codes = [b['code'] for b in plan['blockers']]
    assert 'effects_require_compensation_or_review' in codes and 'incident_not_active_for_rework' not in codes, codes
    assert any(e['kind'] == 'plc' for e in plan['effects_resolution']['effects'])


def test_승인_전_판단_단계부터는_새_차수를_막힘_없이_요청할_수_있다(world):
    alert, pid, decision = world.start_cooling()
    plan = world.rt.preview_rework(pid, world.row(pid, 'T_agent')['id'])
    assert plan['blockers'] == [] and plan['execution_available'] is True, plan['blockers']
    assert 'decision_id' in plan['invalidated_variables']
