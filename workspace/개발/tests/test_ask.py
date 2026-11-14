"""에이전트에게 질문하기(procsvc/ask.py) — 학생 화면에 보이는 준비 · 실패 문장(내부어 없이 할 일), 고를 수 있는 에이전트가 질문에 쓰는 도구 서버,
답의 수치 · ID 대조 표기."""
import re
import uuid
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from conftest import DEFINITIONS, ask_question, task_of
from hydcommon.handover_tools import QUESTION_READS
from hydcommon.timeutil import parse_iso
from procsvc import ask, procdb

INTERNAL = re.compile(r'AGENT_BRIDGE|PROCESS_MODE|legacy|\.env|http://|Error\b|Exception|[A-Z][a-z]+Error|RuntimeError|워커|엔진|계약|세션')


@pytest.mark.parametrize('probe, ready', [
    ({'reachable': True, 'health': {'status': 'ok', 'ai_mode': 'replay', 'replay_questions': ['질문 하나']}}, True),
    ({'reachable': False, 'url': 'http://agent-worker:8097', 'error': 'HTTPError: HTTP Error 503: Service Unavailable'}, False),
    ({'reachable': False, 'url': 'http://agent-worker:8097', 'error': 'URLError: <urlopen error [Errno 111] Connection refused>'}, False),
], ids=['켜짐(재생)', '켜지는 중(503)', '꺼짐'])
def test_질문_준비_상태는_AI_일꾼_상태만으로_정하고_학생이_할_일을_말한다(probe, ready):
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


@pytest.mark.parametrize('value', ['not-a-uuid', '1234'], ids=['글', '짧은 수'])
def test_요청_번호_형식이_틀리면_라이브러리_영문_대신_학생_문장으로_거절한다(value):
    with pytest.raises(ValueError) as refused:
        ask.request_uuid(value)
    assert str(refused.value) == ask.BAD_REQUEST_ID


# ---------------------------------------------------------------- 수치 · ID 대조 — 답에 적힌 그대로 보인다
@pytest.mark.parametrize('claimed, output, missing', [
    ('HYD-01 온도는 61.5도이고 내일은 70도로 오릅니다', '{"asset": "HYD-01", "temp": 61.5}', ['70']),
    ('0.5% 증가, 2026-10-30 기준', '{"rate": 0.5}', ['2026-10-30']),                         # 날짜는 통째로 하나의 값
    ('70.0도 · 1,200건', '{"t": 70, "n": 1200}', []),                                        # 표기만 다른 같은 수
    ('10:30 에 기록됨', '{"at": "2026-10-30T10:30:00"}', ['10:30']),
    ('SOP-COOL-13이며 HYD-02', '{"sop": "SOP-COOL-13", "asset": "HYD-02"}', []),
], ids=['수 하나 없음', '날짜 없음', '표기만 다름', '시각 없음', 'ID 와 한국어 조사'])
def test_조회_결과에_없는_수치와_ID는_답에_적힌_글자_그대로_보인다(claimed, output, missing):
    call = {'_output': output, 'output_complete': True}
    out = ask.result_comparison(claimed, [call])
    assert out.get('missing', []) == missing
    assert not any('E+' in m for m in out.get('missing', []))


def test_조회_원문이_없으면_대조하지_못했다고_말한다():
    assert ask.result_comparison('70', [{'_output': 'x', 'output_complete': False}])['status'] == 'unavailable'


# ---------------------------------------------------------------- 고를 수 있는 에이전트 — 질문에 실제로 쓰는 도구 서버
def test_에이전트마다_질문에_쓰는_도구_서버와_쓰지_않는_서버를_서버가_정해_준다(pg_dsn):
    agents = {a['id']: a for a in ask.agents(procdb.PgRepo(pg_dsn), 'hyd')}
    pm = agents['agent:pm-plan']                                   # 시드: neo4j · hyd-dmn · enterprise-maint
    assert (pm['servers'], pm['left_out']) == (['neo4j', 'hyd-dmn'], ['enterprise-maint'])
    assert set(agents['sys:agent']['servers']) <= set(QUESTION_READS) and agents['sys:agent']['default']
    assert all(a['id'] != 'sys:scada' for a in agents.values())     # 시스템 수행자는 고르지 않는다


# ---------------------------------------------------------------- 실제 처리 건(학생 PC 구성)
def test_AI_일꾼이_닿지_않으면_질문을_처리_건으로_만들지_않는다(course):
    with pytest.raises(ask.WorkerUnavailable) as caught:
        ask.start(course.rt, '설비 HYD-01 의 최근 경보는?', None, '수강생', definitions_dir=DEFINITIONS,
                  worker_probe=lambda: {'reachable': False, 'error': 'URLError: refused'})
    assert str(caught.value) == ask.NOT_READY
    assert course.rt.repo.list_source_runs('hyd', ask.DEFINITION_ID, ask.EVENT_PREFIX, limit=10) == []


def test_실패한_질문은_AI_일꾼이_적은_학생_문장만_보이고_원문은_보이지_않는다(course):
    """B-09: 옛 화면은 hint 가 없으면 raw_error(「RuntimeConnectionError: …」 같은 예외 이름)를 그대로 보였다."""
    view = ask_question(course.rt, '설비 HYD-01 의 최근 경보는?')
    task = task_of(course.rt, view['id'])
    [row] = course.rt.repo.fetch_pending_task('cliagents', 'test-worker:' + uuid.uuid4().hex, tenant_id='hyd')
    course.rt.repo.update_task_error(row['id'], expected_consumer=row['consumer'])
    course.rt.repo.record_events([{'job_id': 'TASK_ERROR', 'todo_id': task['id'], 'proc_inst_id': view['id'], 'crew_type': 'agent',
                                   'event_type': 'error', 'data': {'name': '연결 확인 필요', 'friendly': 'AI 에이전트의 실행기 인증 파일을 읽지 못했습니다.',
                                                                   'raw_error': 'RuntimeConnectionError: key file /run/hyd-credentials/runtime.key'}}])
    after = ask.view(course.rt, view['id'])
    assert (after['state'], after['message']) == ('failed', 'AI 에이전트의 실행기 인증 파일을 읽지 못했습니다.')


@pytest.mark.parametrize('reachable, expected', [(False, ask.NOT_PICKED), (True, ask.BUSY)], ids=['일꾼 꺼짐', '일꾼 바쁨'])
def test_아무도_맡지_않은_질문은_그_시간과_AI_일꾼_상태로_까닭을_말한다(course, reachable, expected):
    view = ask_question(course.rt, '설비 HYD-01 의 최근 경보는?')
    started = parse_iso(task_of(course.rt, view['id'])['start_date'])
    later = started + timedelta(seconds=ask.WAIT_PROBE_AFTER_S + 5)
    after = ask.view(course.rt, view['id'], worker_probe=lambda: {'reachable': reachable, 'url': 'http://agent-worker:8097'}, now=later)
    assert after['message'] == expected.format(age=ask.WAIT_PROBE_AFTER_S + 5)
    assert not INTERNAL.search(after['message'])


def test_맡기_전_질문의_상태_문장에는_내부어가_없다(course):
    view = ask_question(course.rt, '설비 HYD-01 의 최근 경보는?')
    assert (view['state'], view['message']) == ('waiting', '답할 AI 에이전트가 아직 질문을 맡지 않았습니다')


def test_재생_모드에서_저장된_답이_없는_질문은_실패로_남고_끝난_기록_지우기가_그_처리_건을_닫아_지운다(course, worker):
    """화면은 「실패」인데 그 질문의 처리 건은 진행 중으로 남아 [끝난 기록 지우기]를 눌러도 목록에 그대로였다(눌러도 아무 일이 없음) — 처리 건
    목록에도 끝나지 않은 질문으로 남았다. 실제 재생 워커가 낸 실패를, 실제 지우기 경로(POST /api/ask/reset)로 지운다. 아직 도는 질문은 남는다."""
    from student_words import JARGON, WORKER_TALK
    failed = ask_question(course.rt, '저장된 답이 없는 질문 하나')
    assert worker('replay').poll_once() == 1
    said = ask.view(course.rt, failed['id'])
    assert said['state'] == 'failed' and said['message'].startswith('AI 키가 없을 때 쓰는 재생 모드에서는'), said
    assert not WORKER_TALK.search(said['message']) and not JARGON.search(said['message']), said['message']
    assert course.rt.repo.get_instance(failed['id'])['status'] == 'RUNNING'           # 실패는 자동으로 닫지 않는다(다시 시도할 수 있다)
    waiting = ask_question(course.rt, '아직 아무도 맡지 않은 질문')
    status, out = course.world.api('POST', '/api/ask/reset')
    assert status == 200 and (out['closed_stopped'], out['kept_running']) == (1, 1), out
    assert course.rt.repo.get_instance(failed['id'])['status'] != 'RUNNING'
    status, left = course.world.api('GET', '/api/ask')
    assert status == 200 and [q['id'] for q in left] == [waiting['id']], left
    closed = [e for e in course.rt.repo.list_events(proc_inst_id=failed['id']) if e['job_id'] == 'TASK_CLOSED']
    assert closed and closed[-1]['data']['by'] == 'user:me' and closed[-1]['data']['reason'] == ask.STOPPED_CLOSE_REASON, closed
