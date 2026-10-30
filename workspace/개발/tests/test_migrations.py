"""업무 DB 마이그레이션(it/supabase/migrations) — 이미 쓰던 학생 PC의 DB에 새 마이그레이션이 들어갈 때 시작.bat 이 멈추지 않고 정해진 규칙으로 정리되는가.

새 DB를 따로 만들어 앞 마이그레이션까지 넣고, 옛 판이 남겼을 수 있는 데이터를 넣은 뒤 그 마이그레이션 파일을 실제로 적용해 결과를 본다.
"""
import uuid
from urllib.parse import urlsplit, urlunsplit

import pytest

from conftest import MIGRATIONS

AUDIT_CLEANUP = '20261030000068'


@pytest.fixture
def db_before_068(pg_dsn):
    """마이그레이션 067까지 넣은 버릴 DB(테스트마다 새로) → psycopg 연결."""
    import psycopg
    name = 'hyd_mig_' + uuid.uuid4().hex[:8]
    parts = urlsplit(pg_dsn)
    admin = urlunsplit(parts._replace(path='/postgres'))
    with psycopg.connect(admin, autocommit=True) as c:
        c.execute(f'CREATE DATABASE "{name}"')
    conn = psycopg.connect(urlunsplit(parts._replace(path='/' + name)), autocommit=True)
    try:
        for sql in sorted(MIGRATIONS.glob('*.sql')):
            if sql.name >= AUDIT_CLEANUP:
                break
            conn.execute(sql.read_text(encoding='utf8'))
        conn.execute("INSERT INTO tenants(id, name) VALUES ('hyd', '시험 공장')")     # 처리 건 · 작업 행이 가리키는 테넌트
        yield conn
    finally:
        conn.close()
        with psycopg.connect(admin, autocommit=True) as c:
            c.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


def apply_068(conn):
    path = next(MIGRATIONS.glob(AUDIT_CLEANUP + '_*.sql'))
    conn.execute(path.read_text(encoding='utf8'))


def running(conn, pid, incident, started, *, status='RUNNING'):
    from psycopg.types.json import Jsonb
    conn.execute("INSERT INTO bpm_proc_inst(proc_inst_id, proc_def_id, tenant_id, status, start_date, variables_data, current_activity_ids) "
                 "VALUES (%s, 'c3_cooling', 'hyd', %s, %s, %s, %s)",
                 (pid, status, started, Jsonb([{'key': 'incident', 'value': incident}]), ['T_approve']))
    conn.execute("INSERT INTO todolist(id, proc_inst_id, activity_id, status, tenant_id) VALUES (gen_random_uuid(), %s, 'T_approve', 'IN_PROGRESS', 'hyd')",
                 (pid,))


def state(conn, pid):
    inst = conn.execute('SELECT status, end_event FROM bpm_proc_inst WHERE proc_inst_id=%s', (pid,)).fetchone()
    todo = conn.execute('SELECT status FROM todolist WHERE proc_inst_id=%s', (pid,)).fetchone()
    note = conn.execute("SELECT data->>'friendly' FROM events WHERE proc_inst_id=%s AND job_id='INSTANCE_DUPLICATE_CLOSED'", (pid,)).fetchone()
    return (str(inst[0]), inst[1], str(todo[0]), note[0] if note else None)


@pytest.mark.parametrize('copies', [2, 3])
def test_같은_사건의_진행_중_처리_건이_여럿이면_가장_먼저_열린_것만_남기고_나머지는_까닭과_함께_닫는다(db_before_068, copies):
    pids = [f'c3_cooling.dup{n}' for n in range(copies)]
    for n, pid in enumerate(pids):
        running(db_before_068, pid, 'INC-1029-01', f'2026-10-29 10:0{n}:00')
    apply_068(db_before_068)
    assert state(db_before_068, pids[0]) == ('RUNNING', None, 'IN_PROGRESS', None)
    for pid in pids[1:]:
        status, end_event, todo, note = state(db_before_068, pid)
        assert (status, end_event, todo) == ('CANCELLED', 'duplicate-closed', 'CANCELLED')
        assert '먼저 열린 처리 건만 남기고' in note


@pytest.mark.parametrize('second', [
    dict(incident='INC-1029-02'),                     # 다른 사건
    dict(incident='INC-1029-01', status='COMPLETED'),  # 같은 사건이지만 이미 끝난 처리 건
])
def test_중복이_아닌_처리_건은_건드리지_않는다(db_before_068, second):
    running(db_before_068, 'c3_cooling.first', 'INC-1029-01', '2026-10-29 10:00:00')
    running(db_before_068, 'c3_cooling.other', second['incident'], '2026-10-29 10:05:00', status=second.get('status', 'RUNNING'))
    apply_068(db_before_068)
    assert state(db_before_068, 'c3_cooling.first')[0] == 'RUNNING'
    assert state(db_before_068, 'c3_cooling.other')[0] == second.get('status', 'RUNNING')


def test_정리_뒤에는_같은_사건에_진행_중_처리_건을_하나_더_열_수_없다(db_before_068):
    import psycopg
    running(db_before_068, 'c3_cooling.first', 'INC-1029-01', '2026-10-29 10:00:00')
    apply_068(db_before_068)
    with pytest.raises(psycopg.errors.UniqueViolation):
        running(db_before_068, 'c3_cooling.second', 'INC-1029-01', '2026-10-29 10:09:00')
