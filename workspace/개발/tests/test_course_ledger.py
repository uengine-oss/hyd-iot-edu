"""로컬 중계 관문의 실행 장부(procsvc/course_ledger.py) — 실행 하나 = 워커 점유 한 번. 실제 DB · 실제 처리 흐름의 작업 행으로 판정한다."""
import copy
import json
import uuid

import psycopg
import pytest
from psycopg.rows import dict_row

from conftest import start_handover, task_of
from procsvc import course_ledger
from procsvc.course_ledger import POLICY, REASONS, CourseLedger, Denied


@pytest.fixture
def ledger(course):
    return CourseLedger(lambda: psycopg.connect(course.dsn, row_factory=dict_row), POLICY)


def claim(rt, consumer=None):
    """처리 건 하나를 열고 워커처럼 그 AI 작업을 점유한다 → 점유된 작업 행."""
    start_handover(rt)
    [row] = rt.repo.fetch_pending_task('cliagents', consumer or f'test-worker:{uuid.uuid4().hex}', tenant_id='hyd')
    return row


def reclaim(rt, row, consumer=None):
    """같은 작업을 다시 잡는다(사람 답 · 재평가 · 재개처럼 작업이 다시 워커 차례가 된 뒤)."""
    with psycopg.connect(rt.repo.dsn) as db:
        db.execute("UPDATE todolist SET status='IN_PROGRESS', draft_status='FB_REQUESTED', consumer=NULL WHERE id=%s", (row['id'],))
    [again] = rt.repo.fetch_pending_task('cliagents', consumer or f'test-worker:{uuid.uuid4().hex}', tenant_id='hyd')
    assert again['id'] == row['id']
    return again


def runs(dsn):
    with psycopg.connect(dsn, row_factory=dict_row) as db:
        return db.execute('SELECT * FROM hyd_course_runs ORDER BY created_at').fetchall()


def use(ledger, run, row, n=1, *, input_bytes=1000, output_tokens=1000):
    for _ in range(n):
        ledger.charge(run['run_id'], todo_id=row['id'], consumer=row['consumer'], input_bytes=input_bytes, output_tokens=output_tokens)


def test_같은_점유는_토큰을_다시_받아도_같은_실행이다(course, ledger):
    row = claim(course.rt)
    assert ledger.open_run('hyd', row)['run_id'] == ledger.open_run('hyd', row)['run_id']
    assert len(runs(course.dsn)) == 1


def test_같은_작업을_새로_점유하면_첫_실행_기한이_지나도_새_실행이_열린다(course, ledger):
    """B-01: 옛 장부는 작업 행 · 세대 하나에 실행 하나라, 첫 예약 10분 뒤 이어 하기(사람 답 · 재평가 · 재개 · 교정)는 영구 거절이었다."""
    row = claim(course.rt)
    first = ledger.open_run('hyd', row)
    use(ledger, first, row, 3)
    ledger.end('hyd', row['id'], row['consumer'])
    with psycopg.connect(course.dsn) as db:
        db.execute("UPDATE hyd_course_runs SET deadline=now()-interval '1 minute'")
    again = reclaim(course.rt, row)
    second = ledger.open_run('hyd', again)
    use(ledger, second, again)
    assert second['run_id'] != first['run_id']
    assert [(r['consumer'], r['calls']) for r in runs(course.dsn)] == [(row['consumer'], 3), (again['consumer'], 1)]


def _submitted(rt, row):
    rt.repo.save_task_result(row['id'], {'text': 'x'}, final=True, expected_consumer=row['consumer'])


def _failed(rt, row):
    rt.repo.update_task_error(row['id'], expected_consumer=row['consumer'])


def _asked(rt, row):
    rt.repo.set_draft_status(row['id'], 'HUMAN_ASKED', expected_consumer=row['consumer'])


def _deferred(rt, row):
    from procsvc import task_deferral
    task_deferral.defer(rt.repo, 'hyd', row['id'], expected_consumer=row['consumer'], request_id=uuid.uuid4().hex,
                        assessment={'status': 'UNKNOWN', 'reason': '근거 부족', 'evidence': {}})


def _released(rt, row):
    rt.repo.release_worker_claim(row['id'], row['consumer'])


def _lease_lapsed(rt, row):
    with psycopg.connect(rt.repo.dsn) as db:
        db.execute("UPDATE todolist SET lease_until=now()-interval '1 second' WHERE id=%s", (row['id'],))


@pytest.mark.parametrize('end, state', [
    (_submitted, 'ENDED'), (_failed, 'ENDED'), (_asked, 'ENDED'), (_deferred, 'ENDED'), (_released, 'ENDED'),
    (_lease_lapsed, 'ENDED'),
], ids=['결과 제출', '실패', '사람 대기', '보류', '취소', '워커 재시작(임대 끊긴 작업을 새 워커가 다시 잡음)'])
def test_끝난_점유의_실행은_작업_행으로_닫히고_동시_한도에_세지_않는다(course, ledger, end, state):
    """B-01 ②: 워커가 끝을 알리지 못해도(죽음) 작업 행이 정본이다. 끝난 점유는 PC의 하나뿐인 동시 실행 자리를 막지 않는다."""
    row = claim(course.rt)
    ledger.open_run('hyd', row)
    end(course.rt, row)
    other = claim(course.rt)
    ledger.open_run('hyd', other)
    assert [r['state'] for r in runs(course.dsn)] == [state, 'OPEN']


def test_살아_있는_다른_점유가_있으면_동시_한도로_거절한다(course, ledger):
    ledger.open_run('hyd', claim(course.rt))
    with pytest.raises(Denied) as caught:
        ledger.open_run('hyd', claim(course.rt))
    assert (caught.value.code, str(caught.value)) == ('concurrent', REASONS['concurrent'].text)


def test_워커가_점유를_끝내면_그_실행만_닫는다(course, ledger):
    row = claim(course.rt)
    ledger.open_run('hyd', row)
    assert ledger.end('hyd', row['id'], 'someone-else') == 0
    assert ledger.end('hyd', row['id'], row['consumer']) == 1
    assert [r['state'] for r in runs(course.dsn)] == ['ENDED']


@pytest.mark.parametrize('field, amount', [('calls', 1), ('input_bytes', 1000), ('output_tokens', 1000)])
def test_한_번의_실행_상한을_넘는_호출은_보내기_전에_거절한다(course, ledger, field, amount):
    small = copy.deepcopy(POLICY)
    small['run'][field] = 3 * amount
    ledger = CourseLedger(ledger.connect, small)
    row = claim(course.rt)
    run = ledger.open_run('hyd', row)
    use(ledger, run, row, 3, **({field: amount} if field != 'calls' else {}))
    with pytest.raises(Denied) as caught:
        use(ledger, run, row, 1, **({field: amount} if field != 'calls' else {}))
    assert caught.value.code == 'run_limit'
    assert runs(course.dsn)[0]['calls'] == 3


@pytest.mark.parametrize('field', ['calls', 'input_bytes', 'output_tokens'])
def test_작업_단위_누적_상한은_이어_한_실행을_모두_더해_막는다(course, ledger, field):
    """같은 작업을 거듭 다시 실행해 한도를 새로 받는 남용을 막는다 — 한 실행 상한은 남아도 작업 전체가 다 쓰면 새 점유도 열리지 않는다."""
    small = copy.deepcopy(POLICY)
    per = {'calls': 1, 'input_bytes': 1000, 'output_tokens': 1000}[field]
    small['task'][field] = 2 * per
    ledger = CourseLedger(ledger.connect, small)
    row = claim(course.rt)
    use(ledger, ledger.open_run('hyd', row), row, 2)
    ledger.end('hyd', row['id'], row['consumer'])
    again = reclaim(course.rt, row)
    with pytest.raises(Denied) as caught:
        ledger.open_run('hyd', again)
    assert (caught.value.code, str(caught.value)) == ('task_limit', REASONS['task_limit'].text)


def test_PC_전체_상한을_넘으면_다른_작업도_거절한다(course, ledger):
    small = copy.deepcopy(POLICY)
    small['pc']['calls'] = 2
    ledger = CourseLedger(ledger.connect, small)
    row = claim(course.rt)
    run = ledger.open_run('hyd', row)
    use(ledger, run, row, 2)
    with pytest.raises(Denied) as caught:
        use(ledger, run, row, 1)
    assert caught.value.code == 'pc_limit'


def test_코드의_정책_판본이_바뀌면_장부_정책을_바꾸고_사용량은_그대로다(course, ledger, caplog):
    """B-10: 첫 기동 때 넣은 정책이 영영 남아(ON CONFLICT DO NOTHING) 상한을 고쳐 배포해도 이미 켠 PC는 옛 상한이었다."""
    row = claim(course.rt)
    use(ledger, ledger.open_run('hyd', row), row, 2)
    ledger.end('hyd', row['id'], row['consumer'])
    newer = copy.deepcopy(POLICY)
    newer['revision'] = POLICY['revision'] + '-next'
    newer['pc']['calls'] = 5
    CourseLedger(ledger.connect, newer).open_run('hyd', claim(course.rt))
    with psycopg.connect(course.dsn, row_factory=dict_row) as db:
        grant = db.execute("SELECT * FROM hyd_course_grants WHERE account='hyd'").fetchone()
    assert (grant['policy']['revision'], grant['policy']['pc']['calls'], grant['calls']) == (newer['revision'], 5, 2)
    assert any('정책 판본' in r.getMessage() for r in caplog.records)


def test_실행_기한이_지나면_같은_점유의_호출은_시간_초과로_거절한다(course, ledger):
    row = claim(course.rt)
    run = ledger.open_run('hyd', row)
    with psycopg.connect(course.dsn) as db:
        db.execute("UPDATE hyd_course_runs SET deadline=now()-interval '1 second'")
    with pytest.raises(Denied) as caught:
        use(ledger, run, row)
    assert caught.value.code == 'run_time'


def test_다른_점유의_이름으로는_그_실행에_적을_수_없다(course, ledger):
    row = claim(course.rt)
    run = ledger.open_run('hyd', row)
    with pytest.raises(Denied) as caught:
        ledger.charge(run['run_id'], todo_id=row['id'], consumer='someone-else', input_bytes=10, output_tokens=10)
    assert caught.value.code == 'claim_ended'


@pytest.mark.parametrize('text, sentence', [
    ('API Error: 429 {"error":{"message":"[HYD:task_limit] …"}}', REASONS['task_limit'].text),
    ('API Error: 502 ' + json.dumps({'error': {'message': course_ledger.coded('relay_auth')}}, ensure_ascii=True), REASONS['relay_auth'].text),
    ('[HYD:no_such_code] 아무 말', None),
    ('API Error: 500 Internal Server Error', None),
])
def test_CLI_오류_글_안의_관문_거절_코드는_사유_표의_문장으로_읽는다(text, sentence):
    """B-05: 원문(중계 본문)이 아니라 코드만 보고, 한글이 이스케이프된 오류 글에서도 찾는다."""
    assert course_ledger.reason_in(text) == sentence
