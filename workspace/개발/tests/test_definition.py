"""사건 상태 표 · 시한 · 에스컬레이션 사유 문장(procsvc/definition.py) — 상태 · 사유의 사람 이름은 이 한 곳이 갖는다."""
import pytest

from procsvc import definition


def test_사건_기계가_쓰는_모든_상태에_사람_이름이_있고_이름에_개발자_말이_없다():
    """P1-26: 전에는 「action.cmd 발행」 · 「PLC ACK 대기」 · 「ACK DONE」 같은 코드 말이 학생 거절 문장에 그대로 실렸다."""
    states = {s for s, _, _ in definition.STEPS} | set(definition.FAILURE_STATES)
    assert definition.TERMINAL <= states
    for state in states:
        label = definition.state_label(state)
        assert not any(word in label for word in ('action.cmd', 'ACK DONE', 'PLC ACK', 'CLEAR', 's)')), label


def test_표에_없는_사건_상태는_좌표를_붙여_실패한다():
    with pytest.raises(ValueError, match="'NOPE'"):
        definition.state_label('NOPE')


@pytest.mark.parametrize('reason, words, reobserved', [
    ('PLC REJECTED: INTERLOCK', 'PLC 에서 거절됐습니다(사유 INTERLOCK)', False),
    ('GATEWAY_REJECTED: 설비가 원격 자동 모드가 아니어서 보내지 않았습니다', '명령 관문이 설비 명령을 넘기지 않고 거절했습니다 — 설비가 원격 자동', False),
    ('ACK_TIMEOUT', '30초 안에 오지 않았습니다', False),
    ('CMD_SEND_FAILED', '명령 통로(Kafka)에 싣지 못했습니다', False),
    ('PROCESS_RESTART_REVIEW', 'process 가 다시 시작돼', False),
    ('UNSUPPORTED_RECOVERY_CRITERION', '회복 기준이 없어 재관측으로 판정하지 못했습니다', True),
    ('UNSUPPORTED_ALERT_PATTERN', '현장 검토로 넘겼습니다', False),
    ('PROCESS_ENDED: 사람이 닫음', '「사람이 닫음」(으)로 끝나', False),
])
def test_에스컬레이션_사유_코드마다_학생이_읽는_문장이_있다(reason, words, reobserved):
    cause, did_reobserve = definition.escalation_cause(reason)
    assert words in cause and did_reobserve is reobserved


@pytest.mark.parametrize('reason', ['MITIGATION_FAILED', definition.RESULT_REPORT, None])
def test_재관측_미달과_결과_보고가_닫은_사건은_흐름의_보고_틀을_쓴다(reason):
    assert definition.escalation_cause(reason) is None


def test_문장이_없는_사유_코드는_그대로_싣지_않고_실패한다():
    """P1-26: 전에는 모르는 코드를 「사유 UNSUPPORTED_X」로 학생 문장에 그대로 실었다."""
    with pytest.raises(ValueError, match='SOMETHING_NEW'):
        definition.escalation_cause('SOMETHING_NEW')
