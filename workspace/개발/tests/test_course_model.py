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

from conftest import RELAY_KEY, WORKER_KEY, start_handover
from procsvc import course_model, course_policy
from procsvc.course_ledger import REASONS


def gateway(course, **settings):
    app = FastAPI()
    policy = course_policy.mount(app, runtime_factory=lambda: course.rt, phase=course_policy.Phase('course'))
    course_model.mount(app, policy=policy, runtime_factory=lambda: course.rt, settings=dict(course.settings, **settings))
    return TestClient(app)


def claimed(course):
    start_handover(course.rt)
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
    assert response.status_code == 403


def test_수업_밖_흐름의_AI_단계는_까닭과_함께_토큰을_주지_않는다(course):
    raw = json.loads((__import__('conftest').DEFINITIONS / 'shift_handover_v1.json').read_text(encoding='utf8'))
    raw.update(processDefinitionId='my_handover', processDefinitionName='내가 만든 인계', version='1')
    course.rt.register_definition(raw)
    start_handover(course.rt, definition='my_handover', version='1')
    [row] = course.rt.repo.fetch_pending_task('cliagents', 'test-worker:x', tenant_id='hyd')
    response = permit(gateway(course), row)
    assert response.status_code == 403
    assert response.json()['detail'].startswith('수업에서는 준비된 흐름')


@pytest.mark.parametrize('status, body, code, retry', [
    (401, {'error': {'message': 'Authentication Error, Invalid proxy server token passed'}}, 'relay_auth', 'false'),
    (400, {'error': {'message': 'Budget has been exceeded! Current cost: 5.1', 'type': 'budget_exceeded'}}, 'relay_budget', 'false'),
    (403, {'error': {'message': 'key not allowed to access model. This key can only access models=[coding]'}}, 'relay_model', 'false'),
    (429, {'error': {'message': 'Rate limit reached for coding'}}, 'relay_busy', 'true'),
    (529, {'error': {'type': 'overloaded_error', 'message': 'Overloaded'}}, 'relay_busy', 'true'),
    (400, {'error': {'message': 'messages: text content blocks must be non-empty'}}, 'relay_rejected', 'false'),
    (500, b'<html>upstream exploded</html>', 'relay_failed', 'true'),
], ids=['키 틀림', '예산 소진', '모델 거절', '혼잡 429', '과부하 529', '요청 거절', '중계 내부 오류'])
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
