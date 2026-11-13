"""사람에게 묻기(worker/hitl.py) — 업무 질문 형식 · 권한 거절 감지 · DB 가 정본인 이어 하기."""
import json

import pytest
from cliagents import ExecEvent, ExecEventKind

from worker import hitl


@pytest.mark.parametrize('text, expect', [
    (json.dumps({'__human_input__': {'question': ' 정비 창을 고를까요? ', 'options': ['오늘', '내일']}}), {'question': '정비 창을 고를까요?', 'options': ['오늘', '내일']}),
    ('```json\n{"__human_input__": {"question": "확인"}}\n```', {'question': '확인', 'options': []}),
    ('{"cause": "a"}', None),
    ('그냥 글', None),
], ids=['질문 + 선택지', '코드펜스 안', '완료 결과', 'JSON 아님'])
def test_업무_질문은_정한_모양일_때만_질문으로_읽는다(text, expect):
    assert hitl.business_question(text) == expect


@pytest.mark.parametrize('value, needle', [
    ({'__human_input__': {'question': 'q'}, 'cause': 'a'}, '함께 제출'),
    ({'__human_input__': {'question': 'q', 'extra': 1}}, 'question/options'),
    ({'__human_input__': {'question': ''}}, '1~4000자'),
    ({'__human_input__': {'question': 'q', 'options': [''] * 2}}, '선택지'),
    ({'__human_input__': {'question': 'q', 'options': ['a'] * 9}}, '최대8개'),
], ids=['결과와 섞임', '모르는 칸', '빈 질문', '빈 선택지', '선택지 9개'])
def test_틀린_질문_모양은_까닭과_함께_거절한다(value, needle):
    with pytest.raises(ValueError) as e:
        hitl.business_question(json.dumps(value))
    assert needle in str(e.value)


def test_질문_기록은_작업_폴더에_남기고_같은_질문은_한_번만이다(tmp_path):
    request = hitl.PendingRequest(run_id='t', agent_id='claude-code', session_id='s1', question='q', job_id='j', fingerprint=hitl.fingerprint('claude-code', 'q'))
    assert hitl.remember(tmp_path, request) is True
    assert hitl.remember(tmp_path, request) is False and hitl.recall(tmp_path).session_id == 's1'
    hitl.clear(tmp_path)
    assert hitl.recall(tmp_path) is None


REQUEST = {'run_id': 't', 'agent_id': 'a', 'session_id': 's9', 'question': 'q', 'job_id': 'j', 'fingerprint': 'f'}


def test_답이_오기_전에는_DB_의_질문이_기다리는_질문이고_이어_할_세션은_없다():
    row = {'draft': {'_human_request': REQUEST}, 'feedback': None}
    assert hitl.pending_request(row).question == 'q' and hitl.durable_resume(row) is None


def test_같은_질문에_답이_오면_그_세션으로_이어_하고_더_기다리지_않는다():
    row = {'draft': {'_human_request': REQUEST}, 'feedback': {'job_id': 'j', 'answer': '오늘'}}
    assert hitl.durable_resume(row).session_id == 's9' and hitl.pending_request(row) is None


def test_다른_질문의_답으로는_이어_하지_않는다():
    row = {'draft': {'_human_request': REQUEST}, 'feedback': {'job_id': 'other'}}
    assert hitl.durable_resume(row) is None and hitl.pending_request(row).job_id == 'j'


@pytest.mark.parametrize('event, refused', [
    (ExecEvent(kind=ExecEventKind.PERMISSION_REQUEST, text='Claude requested permissions to use mcp__x__write'), True),
    (ExecEvent(kind=ExecEventKind.TOOL_END, is_error=True, text='tool call requires approval'), True),
    (ExecEvent(kind=ExecEventKind.TOOL_END, is_error=True, text='connection refused'), False),
    (ExecEvent(kind=ExecEventKind.TOOL_END, text='ok'), False),
], ids=['CLI 권한 요청', '도구 승인 필요', '다른 도구 오류', '정상 결과'])
def test_권한_요청과_도구_승인_거절만_멈춤_까닭이다(event, refused):
    assert bool(hitl.permission_refusal(event)) is refused
