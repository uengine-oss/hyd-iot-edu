"""에이전트에게 질문하기(procsvc/ask.py) 가운데 학생 화면에 보이는 준비 · 실패 문장 — 내부어(설정 이름 · 예외 이름 · 주소) 없이 할 일을 말한다."""
import re
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from conftest import DEFINITIONS, ask_question, task_of
from procsvc import ask

INTERNAL = re.compile(r'AGENT_BRIDGE|PROCESS_MODE|legacy|\.env|http://|Error\b|Exception|[A-Z][a-z]+Error|RuntimeError')


@pytest.mark.parametrize('probe, ready', [
    ({'reachable': True, 'health': {'status': 'ok', 'ai_mode': 'replay', 'replay_questions': ['질문 하나']}}, True),
    ({'reachable': False, 'url': 'http://agent-worker:8097', 'error': 'HTTPError: HTTP Error 503: Service Unavailable'}, False),
    ({'reachable': False, 'url': 'http://agent-worker:8097', 'error': 'URLError: <urlopen error [Errno 111] Connection refused>'}, False),
], ids=['켜짐(재생)', '켜지는 중(503)', '꺼짐'])
def test_질문_준비_상태는_워커_상태만으로_정하고_학생이_할_일을_말한다(probe, ready):
    out = ask.readiness(lambda: probe)
    assert out['ready'] is ready
    if ready:
        assert out['reason'] is None and out['worker']['replay_questions'] == ['질문 하나']
    else:
        assert out['reason'] == ask.NOT_READY and not INTERNAL.search(out['reason'])
        assert probe['url'] not in str(out) and probe['error'] not in str(out)


def test_처리_흐름_서비스가_켜지는_중이면_질문_화면은_기다리라고만_말한다():
    app = FastAPI()
    ask.register(app, runtime_factory=lambda: None, definitions_dir=DEFINITIONS, worker_probe=lambda: {'reachable': True})
    response = TestClient(app).get('/api/ask/status')
    assert (response.status_code, response.json()['detail']) == (503, ask.RUNTIME_NOT_READY)


def test_워커가_닿지_않으면_질문을_처리_건으로_만들지_않는다(course):
    with pytest.raises(ask.WorkerUnavailable) as caught:
        ask.start(course.rt, '설비 HYD-01 의 최근 경보는?', None, '수강생', definitions_dir=DEFINITIONS,
                  worker_probe=lambda: {'reachable': False, 'error': 'URLError: refused'})
    assert str(caught.value) == ask.NOT_READY
    assert course.rt.repo.list_source_runs('hyd', ask.DEFINITION_ID, ask.EVENT_PREFIX, limit=10) == []


def test_실패한_질문은_워커가_적은_학생_문장만_보이고_원문은_보이지_않는다(course):
    """B-09: 옛 화면은 hint 가 없으면 raw_error(「RuntimeConnectionError: …」 같은 예외 이름)를 그대로 보였다."""
    view = ask_question(course.rt, '설비 HYD-01 의 최근 경보는?')
    task = task_of(course.rt, view['id'])
    [row] = course.rt.repo.fetch_pending_task('cliagents', 'test-worker:' + uuid.uuid4().hex, tenant_id='hyd')
    course.rt.repo.update_task_error(row['id'], expected_consumer=row['consumer'])
    course.rt.repo.record_events([{'job_id': 'TASK_ERROR', 'todo_id': task['id'], 'proc_inst_id': view['id'], 'crew_type': 'agent',
                                   'event_type': 'error', 'data': {'name': '연결 확인 필요', 'friendly': 'AI 워커의 실행기 인증 파일을 읽지 못했습니다.',
                                                                   'raw_error': 'RuntimeConnectionError: key file /run/hyd-credentials/runtime.key'}}])
    after = ask.view(course.rt, view['id'])
    assert (after['state'], after['message']) == ('failed', 'AI 워커의 실행기 인증 파일을 읽지 못했습니다.')


@pytest.mark.parametrize('reachable, expected', [(False, ask.NOT_PICKED), (True, ask.BUSY)])
def test_아무도_집지_않은_질문은_워커_상태로_까닭을_말한다(course, reachable, expected):
    from datetime import datetime, timedelta, timezone
    view = ask_question(course.rt, '설비 HYD-01 의 최근 경보는?')
    later = datetime.now(timezone.utc) + timedelta(seconds=ask.WAIT_PROBE_AFTER_S + 5)
    after = ask.view(course.rt, view['id'], worker_probe=lambda: {'reachable': reachable, 'url': 'http://agent-worker:8097'}, now=later)
    age = int(re.match(r'(\d+)초째', after['message']).group(1))
    assert after['message'] == expected.format(age=age) and 'http://' not in after['message']
