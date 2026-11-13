"""오래 걸리는 요청의 진행 기록(procsvc/progress.py) — 단계의 차례 · 실패 · 만료 · 상한, 그리고 일하는 스레드와 읽는 요청 사이.

기록을 적는 네 동작(판단 채점 · 시험 비교 · 출발본 · 도구 서버 연결 검사)이 실제로 단계를 적는지는 그 동작의 시험이 본다
(test_eval_api · test_agent_trials · test_config_bundle · test_mcp_registry)."""
import threading
import uuid

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from procsvc import progress


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    """기록은 프로세스 메모리에 있다 — 시험마다 빈 기록과 손으로 옮기는 시계로 시작한다."""
    now = {'t': 1000.0}
    monkeypatch.setattr(progress, '_RECORDS', {})
    monkeypatch.setattr(progress, 'clock', lambda: now['t'])
    return now


def rid():
    return str(uuid.uuid4())


def states(request_id):
    return [(s['key'], s['state'], s['note']) for s in progress.read(request_id)['steps']]


def test_단계는_적은_차례대로_남고_시작과_끝_시각이_일의_경계에_찍힌다():
    r = rid()
    p = progress.begin(r, 'config_reset', [('check', '진행 중인 처리 건 확인'), ('flows', '가져온 흐름 지우기')])
    assert progress.read(r)['state'] == 'running' and states(r) == [('check', 'wait', ''), ('flows', 'wait', '')]
    with p:
        p.start('check')
        assert states(r)[0] == ('check', 'run', '')
        p.done('check', '막는 처리 건 없음')
        p.plan([('item:0', '쿨러 성능 저하')])                       # 일하다 알게 된 단계는 뒤에 붙는다
        p.start('flows', '판본 2개')
        p.note('flows', '판본 1/2')
        p.done('flows', '판본 2 · 흐름 1')
        p.start('item:0')
        p.done('item:0', '85점', label='쿨러 성능 저하(HYD-01)')
    out = progress.read(r)
    assert out['state'] == 'done' and out['error'] is None and out['kind'] == 'config_reset' and out['ended_at']
    assert states(r) == [('check', 'ok', '막는 처리 건 없음'), ('flows', 'ok', '판본 2 · 흐름 1'), ('item:0', 'ok', '85점')]
    assert out['steps'][2]['label'] == '쿨러 성능 저하(HYD-01)'
    assert all(s['started_at'] and s['ended_at'] and s['started_at'] <= s['ended_at'] for s in out['steps'])


def test_일이_예외로_끝나면_하던_단계와_기록이_그_사유와_함께_실패로_남고_예외는_그대로_올라간다():
    r = rid()
    p = progress.begin(r, 'eval_run', [('golden', '정답표 읽기'), ('save', '채점 기록 저장')])
    with pytest.raises(ConnectionError):
        with p:
            p.start('golden')
            raise ConnectionError('지식 그래프를 읽지 못했습니다')
    out = progress.read(r)
    assert (out['state'], out['error']) == ('failed', '지식 그래프를 읽지 못했습니다')
    assert states(r) == [('golden', 'fail', '지식 그래프를 읽지 못했습니다'), ('save', 'wait', '')]      # 하지 않은 단계는 한 것으로 적지 않는다


@pytest.mark.parametrize('error, said', [
    (HTTPException(409, {'reason': '진행 중인 처리 건이 있어 되돌리지 않았습니다'}), '진행 중인 처리 건이 있어 되돌리지 않았습니다'),
    (HTTPException(400, '담당자 정보 없이 온 요청'), '담당자 정보 없이 온 요청'),
    (KeyError('cooler-x'), 'cooler-x'),
    (RuntimeError(), 'RuntimeError'),
], ids=['사유 칸이 든 거절', '글로 된 거절', '없는 것', '글 없는 예외'])
def test_실패_사유는_예외가_실은_사람_글이다(error, said):
    assert progress.reason_of(error) == said


def test_기록이_없는_번호는_404_가_아니라_없음으로_답하고_UUID_가_아닌_번호는_400_이다():
    out = progress.read(rid())
    assert (out['state'], out['steps']) == ('none', []) and '아직 서버에 닿지 않았거나' in out['note']
    with pytest.raises(HTTPException) as refused:
        progress.read('../etc/passwd')
    assert refused.value.status_code == 400
    with pytest.raises(HTTPException) as refused:
        progress.begin('아무 글자', 'x')
    assert refused.value.status_code == 400


@pytest.mark.parametrize('request_id', [None, ''], ids=['없음', '빈 글자'])
def test_요청_번호_없이_온_요청은_기록_없이_돈다(request_id):
    p = progress.begin(request_id, 'eval_run', [('golden', '정답표 읽기')])
    with p:
        p.start('golden')
        p.plan([('more', '더')])
        p.done('golden', '항목 3개')
    assert p is progress.SILENT and progress._RECORDS == {}


def test_같은_요청_번호를_두_번_열면_409_로_거절한다():
    r = rid()
    progress.begin(r, 'x')
    with pytest.raises(HTTPException) as refused:
        progress.begin(r, 'x')
    assert refused.value.status_code == 409


def test_없는_단계를_적거나_같은_단계를_두_번_적으면_조용히_넘기지_않는다():
    p = progress.begin(rid(), 'x', [('a', '가')])
    with pytest.raises(KeyError):
        p.start('b')
    with pytest.raises(ValueError):
        p.plan([('a', '또 가')])


def test_끝난_기록은_남겨_두는_시간이_지나면_지워지고_하는_중인_기록은_남는다(clock):
    done, running = rid(), rid()
    with progress.begin(done, 'x', [('a', '가')]) as p:
        p.done('a')
    live = progress.begin(running, 'x', [('a', '가')])
    clock['t'] += progress.KEEP_DONE_S - 1
    assert progress.read(done)['state'] == 'done'
    live.start('a')                                                   # 하는 중인 일은 적을 때마다 살아 있다
    clock['t'] += 2
    assert progress.read(done)['state'] == 'none'
    assert progress.read(running)['state'] == 'running'


def test_아무도_적지_않는_기록은_버려진_것으로_보고_지운다(clock):
    r = rid()
    progress.begin(r, 'x', [('a', '가')])                             # 요청이 실행기에 닿기 전에 죽었다 — 끝도 실패도 적히지 않는다
    clock['t'] += progress.STALE_S + 1
    assert progress.read(r)['state'] == 'none' and progress._RECORDS == {}


def test_기록_수가_상한을_넘으면_끝난_것부터_지운다():
    first_running, finished = rid(), rid()
    progress.begin(first_running, 'x')
    with progress.begin(finished, 'x'):
        pass
    for _ in range(progress.MAX_RECORDS - 1):
        progress.begin(rid(), 'x')
    assert len(progress._RECORDS) == progress.MAX_RECORDS
    assert progress.read(finished)['state'] == 'none'                 # 끝난 기록이 먼저 나갔다
    assert progress.read(first_running)['state'] == 'running'
    progress.begin(rid(), 'x')                                        # 끝난 것이 없으면 가장 오래된 것
    assert len(progress._RECORDS) == progress.MAX_RECORDS and progress.read(first_running)['state'] == 'none'


def test_한_기록의_단계_수는_상한까지다():
    p = progress.begin(rid(), 'x', [(f's{n}', '단계') for n in range(progress.MAX_STEPS)])
    with pytest.raises(ValueError) as refused:
        p.plan([('one-more', '하나 더')])
    assert str(progress.MAX_STEPS) in str(refused.value)


def test_긴_사유는_잘라_적는다():
    r = rid()
    p = progress.begin(r, 'x', [('a', '가')])
    p.fail('a', '가' * 5000)
    assert len(progress.read(r)['steps'][0]['note']) == progress.NOTE_CHARS


def test_일이_실행기_스레드에서_도는_동안_다른_요청이_지금_단계를_읽는다(monkeypatch):
    """라우트가 쓰는 길 그대로: 기록은 요청을 받은 자리에서 열고(tracked), 일은 다른 스레드에서 돌고, 화면은 GET 으로 읽는다."""
    monkeypatch.setattr(progress, 'clock', progress.time.monotonic)
    app = FastAPI()
    progress.register(app)
    client = TestClient(app)
    r = rid()
    at_step, go_on = threading.Event(), threading.Event()

    def job(p):
        p.plan([('connect', '서버에 연결'), ('tools', '도구 목록 받기')])
        p.start('connect')
        at_step.set()
        assert go_on.wait(10)
        p.done('connect', 'ok')
        p.start('tools')
        p.done('tools', '도구 3개')
        return 'result'
    before = client.get(f'/api/progress/{r}')
    assert before.status_code == 200 and before.json()['state'] == 'none'      # 요청이 닿기 전: 404 가 아니다
    work = progress.tracked(r, 'mcp_check', job)
    box = {}
    thread = threading.Thread(target=lambda: box.update(out=work()))
    thread.start()
    assert at_step.wait(10)
    during = client.get(f'/api/progress/{r}').json()
    assert during['state'] == 'running' and [(s['key'], s['state']) for s in during['steps']] == [('connect', 'run'), ('tools', 'wait')]
    go_on.set()
    thread.join(10)
    after = client.get(f'/api/progress/{r}').json()
    assert box['out'] == 'result' and after['state'] == 'done'
    assert [(s['key'], s['state'], s['note']) for s in after['steps']] == [('connect', 'ok', 'ok'), ('tools', 'ok', '도구 3개')]
    assert client.get('/api/progress/not-a-uuid').status_code == 400
