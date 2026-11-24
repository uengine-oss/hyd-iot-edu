"""로컬 중계 관문의 실행 장부(procsvc/course_ledger.py) — 실행 하나 = 워커 점유 한 번. 실제 DB · 실제 처리 흐름의 작업 행으로 판정한다.

장부의 기한 · 임대 판정은 장부 시계 하나로 잰다(바깥 — 테스트가 앞으로 옮긴다). 작업 행의 임대 시각은 워커 대기열(DB 함수)이 정하므로
「새 워커가 끊긴 임대를 다시 잡음」만 그 임대 시각을 지난 시각으로 적어 흉내 낸다(대기열의 DB 시각을 옮기는 길이 따로 없다).
"""
import copy
import json
import uuid
from datetime import datetime, timedelta

import psycopg
import pytest
from psycopg.rows import dict_row

from conftest import EngineClock as Clock, start_handover, task_of
from procsvc import course_ledger
from procsvc.course_ledger import POLICY, REASONS, CourseLedger, Denied


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def ledger(course, clock):
    return CourseLedger(lambda: psycopg.connect(course.dsn, row_factory=dict_row), POLICY, clock=clock)


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


def use(ledger, run, row, n=1, *, input_bytes=1000, output_tokens=1000, phase='course'):
    for _ in range(n):
        ledger.charge(run['run_id'], todo_id=row['id'], consumer=row['consumer'], input_bytes=input_bytes, output_tokens=output_tokens,
                      phase=phase)


def test_같은_점유는_토큰을_다시_받아도_같은_실행이다(course, ledger):
    row = claim(course.rt)
    assert ledger.open_run('hyd', row, phase='course')['run_id'] == ledger.open_run('hyd', row, phase='course')['run_id']
    assert len(runs(course.dsn)) == 1


def test_같은_작업을_새로_점유하면_첫_실행_기한이_지나도_새_실행이_열린다(course, ledger, clock):
    """B-01: 옛 장부는 작업 행 · 세대 하나에 실행 하나라, 첫 예약 10분 뒤 이어 하기(사람 답 · 재평가 · 재개 · 교정)는 영구 거절이었다."""
    row = claim(course.rt)
    first = ledger.open_run('hyd', row, phase='course')
    use(ledger, first, row, 3)
    ledger.end('hyd', row['id'], row['consumer'])
    clock.advance(POLICY['run']['seconds'] + 60)
    again = reclaim(course.rt, row)
    second = ledger.open_run('hyd', again, phase='course')
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
    """워커가 죽어 임대를 늘리지 못한 채 그 시각이 지났고(대기열의 DB 시각 — 위 머리말), 새 워커가 바로 그 작업을 다시 잡았다.
    새 처리 건을 열기 전에 다시 잡는다 — 열린 작업이 둘이면 대기열이 어느 것을 줄지 정해져 있지 않아, 다른 작업을 잡으면 옛 점유가
    「점유 중 · 임대 끊김」(EXPIRED)으로 남는다(2026-11-01 따로 돌려도 가끔 EXPIRED — 시험이 잡을 행을 정하지 않았던 것)."""
    with psycopg.connect(rt.repo.dsn) as db:
        db.execute("UPDATE todolist SET lease_until=now()-interval '1 second' WHERE id=%s", (row['id'],))
    [again] = rt.repo.fetch_pending_task('cliagents', f'test-worker:{uuid.uuid4().hex}', tenant_id='hyd')
    assert again['id'] == row['id']


def _lease_ran_out(clock):
    """워커가 죽은 채 임대 시각이 지났다(장부 시계로) — 아무도 다시 잡지 않았다."""
    def end(rt, row):
        lease = rt.repo.get_workitem(str(row['id']))['lease_until']
        lease = datetime.fromisoformat(lease.replace('Z', '+00:00')) if isinstance(lease, str) else lease
        clock.at = lease + timedelta(seconds=1)
    return end


def _run_time_passed(clock):
    """점유는 살아 있는데 실행 기한(POLICY run.seconds)이 지났다."""
    def end(rt, row):
        clock.advance(POLICY['run']['seconds'] + 1)
    return end


@pytest.mark.parametrize('end, state', [
    (lambda clock: _submitted, 'ENDED'), (lambda clock: _failed, 'ENDED'), (lambda clock: _asked, 'ENDED'),
    (lambda clock: _deferred, 'ENDED'), (lambda clock: _released, 'ENDED'), (lambda clock: _lease_lapsed, 'ENDED'),
    (_lease_ran_out, 'EXPIRED'), (_run_time_passed, 'EXPIRED'),
], ids=['결과 제출', '실패', '사람 대기', '보류', '취소', '워커 재시작(임대 끊긴 작업을 새 워커가 다시 잡음)',
        '워커가 죽어 임대 시각이 지남', '실행 기한이 지남'])
def test_끝난_점유의_실행은_작업_행으로_닫히고_동시_한도에_세지_않는다(course, ledger, clock, end, state):
    """B-01 ②: 워커가 끝을 알리지 못해도(죽음) 작업 행이 정본이다. 끝난 점유는 PC의 하나뿐인 동시 실행 자리를 막지 않는다."""
    row = claim(course.rt)
    ledger.open_run('hyd', row, phase='course')
    end(clock)(course.rt, row)
    other = claim(course.rt)
    ledger.open_run('hyd', other, phase='course')
    assert [r['state'] for r in runs(course.dsn)] == [state, 'OPEN']


def test_살아_있는_다른_점유가_있으면_동시_한도로_거절한다(course, ledger):
    ledger.open_run('hyd', claim(course.rt), phase='course')
    with pytest.raises(Denied) as caught:
        ledger.open_run('hyd', claim(course.rt), phase='course')
    assert (caught.value.code, str(caught.value)) == ('concurrent', REASONS['concurrent'].text)


def test_워커가_점유를_끝내면_그_실행만_닫는다(course, ledger):
    row = claim(course.rt)
    ledger.open_run('hyd', row, phase='course')
    assert ledger.end('hyd', row['id'], 'someone-else') == 0
    assert ledger.end('hyd', row['id'], row['consumer']) == 1
    assert [r['state'] for r in runs(course.dsn)] == ['ENDED']


@pytest.mark.parametrize('field, amount', [('calls', 1), ('input_bytes', 1000), ('output_tokens', 1000)])
def test_한_번의_실행_상한을_넘는_호출은_보내기_전에_거절한다(course, ledger, field, amount):
    small = copy.deepcopy(POLICY)
    small['run'][field] = 3 * amount
    ledger = CourseLedger(ledger.connect, small)
    row = claim(course.rt)
    run = ledger.open_run('hyd', row, phase='course')
    use(ledger, run, row, 3, **({field: amount} if field != 'calls' else {}))
    with pytest.raises(Denied) as caught:
        use(ledger, run, row, 1, **({field: amount} if field != 'calls' else {}))
    assert caught.value.code == 'run_limit'
    assert runs(course.dsn)[0]['calls'] == 3


def test_수업_실행의_입력_한도는_호출_수_한도보다_먼저_막지_않는다(course, ledger):
    """제품 한도(POLICY) 그대로, 수업에서 잰 가장 큰 실행으로 판정한다 — 2026-11-23 실습 17 교대 인계안이 결과 검사에서 두 번 돌려보내진 뒤의
    세 번째 차례: 같은 대화를 이어 가 호출 하나가 평균 639,464바이트(끝에는 713 KB)였고, 그 12번(합 7,673,568)에서 한 번 실행의 입력 한도
    8,000,000 이 호출 수 한도(48)의 4분의 1 자리에서 먼저 막았다. 그 크기의 호출이 호출 수 한도까지 가고, 막는 것은 호출 수다."""
    row = claim(course.rt)
    run = ledger.open_run('hyd', row, phase='course')
    use(ledger, run, row, 12, input_bytes=639_464)
    use(ledger, run, row, POLICY['run']['calls'] - 12, input_bytes=713_000)        # 13번째부터 — 전에는 여기서 run_limit
    with pytest.raises(Denied) as caught:
        use(ledger, run, row, 1, input_bytes=713_000)
    assert caught.value.code == 'run_limit'
    [spent] = runs(course.dsn)
    assert (spent['calls'], spent['input_bytes']) == (48, 12 * 639_464 + 36 * 713_000)
    assert spent['input_bytes'] < POLICY['run']['input_bytes']          # 49번째를 막은 것은 입력 합이 아니라 호출 수다


@pytest.mark.parametrize('field', ['calls', 'input_bytes', 'output_tokens'])
def test_작업_단위_누적_상한은_이어_한_실행을_모두_더해_막는다(course, ledger, field):
    """같은 작업을 거듭 다시 실행해 한도를 새로 받는 남용을 막는다 — 한 실행 상한은 남아도 작업 전체가 다 쓰면 새 점유도 열리지 않는다."""
    small = copy.deepcopy(POLICY)
    per = {'calls': 1, 'input_bytes': 1000, 'output_tokens': 1000}[field]
    small['task'][field] = 2 * per
    ledger = CourseLedger(ledger.connect, small)
    row = claim(course.rt)
    use(ledger, ledger.open_run('hyd', row, phase='course'), row, 2)
    ledger.end('hyd', row['id'], row['consumer'])
    again = reclaim(course.rt, row)
    with pytest.raises(Denied) as caught:
        ledger.open_run('hyd', again, phase='course')
    assert (caught.value.code, str(caught.value)) == ('task_limit', REASONS['task_limit'].text)


def test_PC_전체_상한을_넘으면_다른_작업도_거절한다(course, ledger):
    small = copy.deepcopy(POLICY)
    small['pc']['calls'] = 2
    ledger = CourseLedger(ledger.connect, small)
    row = claim(course.rt)
    run = ledger.open_run('hyd', row, phase='course')
    use(ledger, run, row, 2)
    with pytest.raises(Denied) as caught:
        use(ledger, run, row, 1)
    assert caught.value.code == 'pc_limit'


def test_코드의_정책_판본이_바뀌면_장부_정책을_바꾸고_사용량은_그대로다(course, ledger, caplog):
    """B-10: 첫 기동 때 넣은 정책이 영영 남아(ON CONFLICT DO NOTHING) 상한을 고쳐 배포해도 이미 켠 PC는 옛 상한이었다."""
    row = claim(course.rt)
    use(ledger, ledger.open_run('hyd', row, phase='course'), row, 2)
    ledger.end('hyd', row['id'], row['consumer'])
    newer = copy.deepcopy(POLICY)
    newer['revision'] = POLICY['revision'] + '-next'
    newer['pc']['calls'] = 5
    CourseLedger(ledger.connect, newer).open_run('hyd', claim(course.rt), phase='course')
    with psycopg.connect(course.dsn, row_factory=dict_row) as db:
        grant = db.execute("SELECT * FROM hyd_course_grants WHERE account='hyd'").fetchone()
    assert (grant['policy']['revision'], grant['policy']['pc']['calls'], grant['calls']) == (newer['revision'], 5, 2)
    assert any('정책 판본' in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize('after, code', [(POLICY['run']['seconds'] - 1, None), (POLICY['run']['seconds'], 'run_time')],
                         ids=['기한 1초 전 — 적힘', '기한 그 시각 — 시간 초과'])
def test_실행_기한까지만_같은_점유의_호출을_적는다(course, ledger, clock, after, code):
    row = claim(course.rt)
    run = ledger.open_run('hyd', row, phase='course')
    clock.advance(after)
    if code is None:
        use(ledger, run, row)
        assert runs(course.dsn)[0]['calls'] == 1
    else:
        with pytest.raises(Denied) as caught:
            use(ledger, run, row)
        assert caught.value.code == code


def test_PBL_단계의_실행은_긴_문서_한_구간이_끝나는_시간을_받고_수업_전체를_잰_PC_한도에_막히지_않는다(course, ledger, clock):
    """탐사 S: 관문 장부 한도가 PBL 에도 수업 값 그대로였다 — 한 번 실행 600초는 긴 문서 한 구간(워커 실행 한도 1,800초에 맞춰 정한 크기,
    82,795자 실측 1,180초)을 「한 번 실행 시간을 넘었습니다」로 다시 해도 또 멈추게 했고, PC 전체 600회 · 1억 바이트(이 PC의 수업 전체)가
    실제 규모 문서 · 실데이터 일을 막았다. PBL 단계의 실행은 그 단계의 한도로 열고 적는다(비용의 최종 방어는 중계 키 한도)."""
    from worker.settings import Settings
    row = claim(course.rt)
    with psycopg.connect(course.dsn, autocommit=True) as db:      # 이 PC 는 수업에서 PC 한도를 다 썼다
        db.execute('INSERT INTO hyd_course_grants(account, policy, calls) VALUES (%s, %s, %s) ON CONFLICT (account) DO UPDATE SET calls = excluded.calls',
                   ('hyd', psycopg.types.json.Jsonb(POLICY), POLICY['pc']['calls']))
    with pytest.raises(Denied) as course_phase:
        ledger.open_run('hyd', row, phase='course')
    assert course_phase.value.code == 'pc_limit'
    run = ledger.open_run('hyd', row, phase='pbl')
    assert run['deadline'] - clock().timestamp() == pytest.approx(Settings().run_timeout_s, abs=1)     # 워커의 한 번 실행 한도와 같다
    clock.advance(POLICY['run']['seconds'] + 60)                                                      # 수업 한도(600초)를 넘긴 때에도
    use(ledger, run, row, phase='pbl', input_bytes=course_ledger.CALL_INPUT_BYTES)                  # 큰 호출이 적힌다
    assert runs(course.dsn)[0]['calls'] == 1
    with pytest.raises(ValueError):
        ledger.open_run('hyd', claim(course.rt), phase='holiday')                                     # 모르는 단계는 한도를 짐작하지 않는다


def test_PBL_에서_쓴_사용량은_수업_단계의_PC_한도에_더하지_않는다(course, ledger):
    """PC 누적은 「이 PC의 수업 전체」를 재는 값이다 — 단계를 가리지 않고 더하던 때는 PBL 의 실제 규모 일이 그 값을 채워, PBL 기한 뒤 수업 단계로
    돌아온 PC 의 수업 AI 단계가 PC 한도로 막혔다. PBL 사용량은 그 실행 행에만 남고, 수업 단계의 사용량은 전처럼 PC 누적에 든다."""
    small = copy.deepcopy(POLICY)
    small['pc']['calls'] = 2
    ledger = CourseLedger(ledger.connect, small)
    row = claim(course.rt)
    run = ledger.open_run('hyd', row, phase='pbl')
    use(ledger, run, row, 3, phase='pbl')                                                             # 수업 PC 한도(2회)보다 많이
    ledger.end('hyd', row['id'], row['consumer'])
    with psycopg.connect(course.dsn, row_factory=dict_row) as db:
        grant = db.execute("SELECT calls, input_bytes, output_tokens FROM hyd_course_grants WHERE account='hyd'").fetchone()
    assert grant == {'calls': 0, 'input_bytes': 0, 'output_tokens': 0} and runs(course.dsn)[0]['calls'] == 3
    again = reclaim(course.rt, row)                                                                   # PBL 기한 뒤 수업 단계의 실행
    back = ledger.open_run('hyd', again, phase='course')
    use(ledger, back, again, 2)
    with pytest.raises(Denied) as caught:
        use(ledger, back, again, 1)
    assert caught.value.code == 'pc_limit'                                                            # 수업 단계의 사용량은 PC 누적에 든다


def test_다른_점유의_이름으로는_그_실행에_적을_수_없다(course, ledger):
    row = claim(course.rt)
    run = ledger.open_run('hyd', row, phase='course')
    with pytest.raises(Denied) as caught:
        ledger.charge(run['run_id'], todo_id=row['id'], consumer='someone-else', input_bytes=10, output_tokens=10, phase='course')
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
