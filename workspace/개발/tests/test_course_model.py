"""로컬 중계 관문(procsvc/course_model.py) — 워커 토큰 발급 · 모델 호출 전달 · 거절 문장. 실제 수업 판정 · 실제 장부 · 실제 DB, 강의 중계만 대체 서버.

모델 호출의 거절 · 중계 실패는 Anthropic 오류 모양이고 message 는 [HYD:<code>] + 학생 문장이다(중계 원문은 넘기지 않는다).
"""
import json
import uuid

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from conftest import RELAY_KEY, WORKER_KEY, definition_version, start_handover
from procsvc import course_model, course_policy
from procsvc.course_ledger import REASONS


def gateway(course, phase='course', **settings):
    app = FastAPI()
    policy = course_policy.mount(app, runtime_factory=lambda: course.rt, phase=course_policy.Phase(phase))
    course_model.mount(app, policy=policy, runtime_factory=lambda: course.rt, settings=dict(course.settings, **settings))
    return TestClient(app)


def claimed(course, **start):
    start_handover(course.rt, **start)
    [row] = course.rt.repo.fetch_pending_task('cliagents', f'test-worker:{uuid.uuid4().hex}', tenant_id='hyd')
    return row


def permit(client, row, key=WORKER_KEY):
    return client.post('/internal/worker/model-runtime', headers={'Authorization': 'Bearer ' + key},
                       json={'tenant_id': 'hyd', 'todo_id': str(row['id']), 'consumer': row['consumer']})


def call(client, token, **body):
    payload = {'model': 'coding', 'max_tokens': 64, 'messages': [{'role': 'user', 'content': '다음 단계'}], **body}
    return client.post('/internal/model/v1/messages', headers={'x-api-key': token}, json=payload)


def calls_on_ledger(dsn):
    with psycopg.connect(dsn, row_factory=dict_row) as db:
        return db.execute('SELECT coalesce(sum(calls),0) AS n FROM hyd_course_runs').fetchone()['n']


def code_of(response):
    return response.json()['error']['message'].split(']')[0].removeprefix('[HYD:')


def test_토큰으로_부른_모델_호출은_process_의_중계_키로_전달되고_장부에_한_번_적힌다(course, relay):
    client = gateway(course)
    token = permit(client, claimed(course)).json()['token']
    response = call(client, token)
    assert response.status_code == 200 and response.json()['content'][0]['text'] == 'ok'
    [sent] = relay.requests
    assert sent['headers']['x-api-key'] == RELAY_KEY and token not in json.dumps(sent['headers'])
    assert calls_on_ledger(course.dsn) == 1


def test_실행기_인증_파일이_다르면_토큰을_주지_않는다(course):
    response = permit(gateway(course), claimed(course), key='x' * 48)
    assert (response.status_code, response.json()['detail']) == (401, course_policy.WORKER_AUTH_FAILED)


@pytest.fixture
def my_handover(course):
    """학생이 따로 등록한 교대 흐름(수업 밖) — 이 테스트가 등록하고 끝나면 지운다(다음 테스트의 정의 목록에 남지 않게)."""
    from conftest import DEFINITIONS
    did = 'my_handover_' + uuid.uuid4().hex[:8]
    raw = json.loads((DEFINITIONS / 'shift_handover_v1.json').read_text(encoding='utf8'))
    raw.update(processDefinitionId=did, processDefinitionName='내가 만든 인계', version='1')
    course.rt.register_definition(raw)
    yield did
    with psycopg.connect(course.dsn, autocommit=True) as db:
        db.execute('DELETE FROM bpm_proc_inst WHERE proc_def_id=%s', (did,))
        db.execute('DELETE FROM proc_def_version WHERE proc_def_id=%s', (did,))
        db.execute('DELETE FROM proc_def WHERE id=%s', (did,))


def test_수업_밖_흐름의_AI_단계는_까닭과_함께_토큰을_주지_않는다(course, my_handover):
    row = claimed(course, definition=my_handover, version='1')
    response = permit(gateway(course), row)
    assert (response.status_code, response.json()['detail']) == (403, course_policy.Policy.REASONS['ai_slot'])


def test_문서_넣기_구간처럼_큰_작업_변수도_토큰을_받는다(course, tmp_path):
    """P2-03: 관문이 작업 변수 크기를 128,000바이트로 따로 막아 문서 넣기 구간(80,000자 · 한국어 약 24만 바이트 + 카탈로그)이 시작부터
    거절됐다. 입력 크기는 모델 호출마다 잰다(INPUT_MAX · 실행당 입력 상한). 문서 넣기 AI 는 PBL 단계의 일이라 PBL 관문으로, 실제 문서
    추출(manual_extraction.start — 보관소에 올린 한 구간 크기의 문서)의 작업으로 판정한다."""
    from procsvc import engine, manual_extraction, manual_segments
    from procsvc.manual_sources import ManualSources
    body = '\n\n'.join(f'{n}. 냉각 팬 점검 단계를 기록한다 — ' + '가' * 900 for n in range(1, 80))
    text = '# 큰 정비 문서\n\n## 1 점검\n\n' + body
    assert len(text) <= manual_segments.DEFAULT_MAX_CHARS
    source = ManualSources(tmp_path / 'm.sqlite3').save('hyd', 'big-manual.md', text.encode('utf8'))
    inst = manual_extraction.start(course.rt, source, str(uuid.uuid4()))
    [row] = course.rt.repo.fetch_pending_task('cliagents', f'test-worker:{uuid.uuid4().hex}', tenant_id='hyd', proc_inst_id=inst['proc_inst_id'])
    assert len(course_policy.canonical(engine.variables(course.rt.repo.get_instance(row['proc_inst_id'])))) > 128_000
    response = permit(gateway(course, phase='pbl'), row)
    assert response.status_code == 200, response.text


def test_장부가_거절한_토큰_요청은_워커가_고를_사유_코드와_문장을_준다(course):
    """P2-13: 동시 실행 · 한도 거절은 권한 문제가 아니다 — 워커가 머리말을 고를 수 있게 [HYD:<code>]를 싣는다."""
    client = gateway(course)
    assert permit(client, claimed(course)).status_code == 200
    response = permit(client, claimed(course))
    assert (response.status_code, response.json()['detail']) == (403, '[HYD:concurrent] ' + REASONS['concurrent'].text)


@pytest.mark.parametrize('status, body, code, retry', [
    (401, {'error': {'message': 'Authentication Error, Invalid proxy server token passed'}}, 'relay_auth', 'false'),
    (400, {'error': {'message': 'Budget has been exceeded! Current cost: 5.1', 'type': 'budget_exceeded'}}, 'relay_budget', 'false'),
    (403, {'error': {'message': 'key not allowed to access model. This key can only access models=[coding]'}}, 'relay_model', 'false'),
    (429, {'error': {'message': 'Rate limit reached for coding'}}, 'relay_busy', 'true'),
    # 2026-10-31 실제 강의 중계(LiteLLM 1.90.2)의 비스트리밍 답 — 뒤쪽 OpenAI 계정 잔액 소진. 429 라 「붐빔 · 다시 실행」으로 읽혔다
    (429, {'error': {'message': 'litellm.RateLimitError: RateLimitError: OpenAIException - {"error": {"message": "You have no credits '
                                'remaining.", "type": "insufficient_quota", "code": "credit_balance_exhausted"}}. Received Model Group=coding',
                     'type': 'throttling_error', 'code': '429'}}, 'relay_budget', 'false'),
    (529, {'error': {'type': 'overloaded_error', 'message': 'Overloaded'}}, 'relay_busy', 'true'),
    (400, {'error': {'message': 'messages: text content blocks must be non-empty'}}, 'relay_rejected', 'false'),
    (500, b'<html>upstream exploded</html>', 'relay_failed', 'true'),
], ids=['키 틀림', '예산 소진', '모델 거절', '혼잡 429', '중계 계정 잔액 소진', '과부하 529', '요청 거절', '중계 내부 오류'])
def test_강의_중계의_거절은_종류별_학생_문장과_다시_보내도_되는지로_바뀐다(course, relay, status, body, code, retry):
    """B-05: 옛 관문은 400/408/429 말고는 모두 502 「요청을 완료하지 못했습니다」 한 문장이라 키 오류 · 예산 소진을 가르지 못했다."""
    relay.answer(status, body)
    client = gateway(course)
    response = call(client, permit(client, claimed(course)).json()['token'])
    assert (code_of(response), response.headers['x-should-retry']) == (code, retry)
    assert response.json()['error']['message'].endswith(REASONS[code].text)
    upstream = body['error']['message'] if isinstance(body, dict) else body.decode()
    assert upstream not in response.text                     # 중계 원문은 넘기지 않는다


def test_중계_설정이_없으면_장부에_적기_전에_거절한다(course, relay):
    """B-05: 옛 관문은 과금(장부 적기)을 중계 설정 확인보다 먼저 해 설정이 없어도 호출 한 번을 써 버렸다."""
    client = gateway(course, LLM_API_KEY='')
    response = call(client, permit(client, claimed(course)).json()['token'])
    assert (response.status_code, code_of(response), response.headers['x-should-retry']) == (503, 'relay_config', 'false')
    assert calls_on_ledger(course.dsn) == 0 and relay.requests == []


@pytest.mark.parametrize('body', [{'model': 'claude-opus-4'}, {'max_tokens': None}, {'messages': []}],
                         ids=['수업 밖 모델', '출력 상한 없음', '빈 메시지'])
def test_수업_모델이_아니거나_한도가_없는_요청은_보내지도_적지도_않는다(course, relay, body):
    client = gateway(course)
    response = call(client, permit(client, claimed(course)).json()['token'], **body)
    assert (response.status_code, code_of(response)) == (422, 'bad_request')
    assert calls_on_ledger(course.dsn) == 0 and relay.requests == []


def test_임대가_끊긴_점유의_토큰으로는_더_부르지_못한다(course, relay):
    client = gateway(course)
    row = claimed(course)
    token = permit(client, row).json()['token']
    with psycopg.connect(course.dsn) as db:
        db.execute("UPDATE todolist SET lease_until=now()-interval '1 second' WHERE id=%s", (row['id'],))
    response = call(client, token)
    assert (response.status_code, code_of(response)) == (409, 'claim_ended')
    assert relay.requests == []


def test_고친_토큰은_받지_않는다(course):
    client = gateway(course)
    token = permit(client, claimed(course)).json()['token']
    forged = token[:-4] + ('0000' if not token.endswith('0000') else '1111')
    assert code_of(call(client, forged)) == 'token'


def test_워커가_점유를_끝내면_그_실행이_닫힌다(course):
    client = gateway(course)
    row = claimed(course)
    permit(client, row)
    body = {'tenant_id': 'hyd', 'todo_id': str(row['id']), 'consumer': row['consumer']}
    response = client.post('/internal/worker/model-runtime/end', headers={'Authorization': 'Bearer ' + WORKER_KEY}, json=body)
    assert response.json()['ended'] == 1
    with psycopg.connect(course.dsn, row_factory=dict_row) as db:
        assert [r['state'] for r in db.execute('SELECT state FROM hyd_course_runs').fetchall()] == ['ENDED']


def test_다른_인증_파일로는_실행을_닫지_못하고_401이다(course):
    client = gateway(course)
    row = claimed(course)
    permit(client, row)
    body = {'tenant_id': 'hyd', 'todo_id': str(row['id']), 'consumer': row['consumer']}
    response = client.post('/internal/worker/model-runtime/end', headers={'Authorization': 'Bearer ' + 'x' * 48}, json=body)
    assert (response.status_code, response.json()['detail']) == (401, course_policy.WORKER_AUTH_FAILED)
    with psycopg.connect(course.dsn, row_factory=dict_row) as db:
        assert [r['state'] for r in db.execute('SELECT state FROM hyd_course_runs').fetchall()] == ['OPEN']


@pytest.mark.parametrize('url, ok', [
    ('https://relay.example.com', True), ('http://127.0.0.1:4000', True), ('http://relay.example.com', False),
    ('https://user:pw@relay.example.com', False), ('https://relay.example.com/?key=1', False), ('', False),
])
def test_강의_중계_주소는_HTTPS_또는_이_PC_안의_HTTP만_받는다(url, ok):
    from procsvc.course_ledger import Denied
    if ok:
        assert course_model.relay_url(url) == url
    else:
        with pytest.raises(Denied):
            course_model.relay_url(url)


# 2026-10-31 실제 강의 중계(LiteLLM 1.90.2, 수업 모델 coding)의 스트리밍 답 그대로 — 뒤쪽 모델 계정 잔액이 바닥나자 200 + 내용 블록 없는
# 메시지(토큰 0)를 냈다. 관문이 이것을 흘려보내 CLI 가 「No response requested.」로 끝났고 모든 AI 단계가 「결과를 반환하지 않았습니다」였다.
EMPTY_STREAM = (b'event: message_start\ndata: {"type": "message_start", "message": {"id": "msg_b6a9b14b", "type": "message", "role": "assistant", '
                b'"content": [], "model": "gpt-6-luna", "stop_reason": null, "stop_sequence": null, "usage": {"input_tokens": 0, "output_tokens": 0, '
                b'"cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}}}\n\n') * 2 + (
                b'event: message_delta\ndata: {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": null}, '
                b'"usage": {"input_tokens": 0, "output_tokens": 0}}\n\n'
                b'event: message_stop\ndata: {"type": "message_stop"}\n\n')
# 같은 중계의 정상 답 모양(강사 녹화 it/agent-worker/replay/*.json.gz 의 사건 순서 — message_start 두 번 뒤 내용 블록, 끝 message_delta 에 사용량)
ANSWER_STREAM = (b'event: message_start\ndata: {"type": "message_start", "message": {"id": "msg_1", "type": "message", "role": "assistant", '
                 b'"content": [], "model": "gpt-6-luna", "usage": {"input_tokens": 0, "output_tokens": 0}}}\n\n') * 2 + (
                 b'event: content_block_start\ndata: {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}\n\n'
                 b'event: content_block_delta\ndata: {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "blue"}}\n\n'
                 b'event: content_block_stop\ndata: {"type": "content_block_stop", "index": 0}\n\n'
                 b'event: message_delta\ndata: {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"input_tokens": 12, "output_tokens": 2}}\n\n'
                 b'event: message_stop\ndata: {"type": "message_stop"}\n\n')
STARTED = b'event: message_start\ndata: {"type": "message_start", "message": {"content": []}}\n\n'


def streamed(course, relay, body):
    relay.answer(200, body, 'text/event-stream')
    client = gateway(course)
    return call(client, permit(client, claimed(course)).json()['token'], stream=True)


def test_중계가_내용_없는_빈_스트리밍_답을_내면_까닭_코드로_거절하고_다시_보내지_않게_한다(course, relay):
    response = streamed(course, relay, EMPTY_STREAM)
    assert (response.status_code, code_of(response), response.headers['x-should-retry']) == (502, 'relay_empty', 'false')
    assert response.json()['error']['message'].endswith(REASONS['relay_empty'].text)


def test_중계의_정상_스트리밍_답은_바이트_그대로_흘려보낸다(course, relay):
    response = streamed(course, relay, ANSWER_STREAM)
    assert response.status_code == 200 and response.headers['content-type'].startswith('text/event-stream')
    assert response.content == ANSWER_STREAM


def test_중계의_정상_스트리밍_답은_중계가_끝나기_전에_앞부분부터_흘려보낸다(course, relay):
    """마지막고침 검증 A7: 관문은 첫 내용 블록까지만 읽고 판정한 뒤 나머지를 흘려보낸다 — 답을 끝까지 모았다가 보내면 학생 화면 · AI 실행 도구가
    긴 답 내내 아무것도 받지 못한다. 실제 HTTP 로 띄운 관문에, 첫 내용 뒤 3초 쉬었다 끝을 보내는 중계를 물려 첫 바이트가 끝보다 먼저 오는지 잰다."""
    import time as clock
    import httpx
    from conftest import Served
    cut = ANSWER_STREAM.index(b'event: content_block_stop')
    relay.answer(200, [ANSWER_STREAM[:cut], 3.0, ANSWER_STREAM[cut:]], 'text/event-stream')
    app = FastAPI()
    policy = course_policy.mount(app, runtime_factory=lambda: course.rt, phase=course_policy.Phase('course'))
    course_model.mount(app, policy=policy, runtime_factory=lambda: course.rt, settings=dict(course.settings))
    token = permit(TestClient(app), claimed(course)).json()['token']
    served = Served(app, lifespan='off')
    try:
        payload = {'model': 'coding', 'max_tokens': 64, 'messages': [{'role': 'user', 'content': '다음 단계'}], 'stream': True}
        start, first_at, body = clock.monotonic(), None, b''
        with httpx.stream('POST', served.url + '/internal/model/v1/messages', headers={'x-api-key': token}, json=payload, timeout=30) as response:
            assert response.status_code == 200, response.read()
            for chunk in response.iter_raw():
                if first_at is None and chunk:
                    first_at = clock.monotonic() - start
                body += chunk
        total = clock.monotonic() - start
    finally:
        served.close()
    assert body == ANSWER_STREAM                                            # 바이트 그대로
    assert first_at is not None and first_at < 2.0 and total >= 3.0, (first_at, total)   # 앞부분은 중계가 쉬는 동안 이미 왔다


def test_스트리밍_중_첫_내용_전에_온_오류_사건은_종류별로_거절한다(course, relay):
    response = streamed(course, relay, STARTED + b'event: error\ndata: {"type": "error", "error": {"type": "overloaded_error", '
                                                 b'"message": "Overloaded"}}\n\n')
    assert (code_of(response), response.headers['x-should-retry']) == ('relay_busy', 'true')


def test_스트리밍이_판정_전에_끊기면_끝나지_않은_답으로_거절한다(course, relay):
    response = streamed(course, relay, STARTED)
    assert (response.status_code, code_of(response)) == (502, 'relay_failed')
