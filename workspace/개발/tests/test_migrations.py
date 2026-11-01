"""업무 DB 마이그레이션(it/supabase/migrations) — 이미 쓰던 학생 PC의 DB에 새 마이그레이션이 들어갈 때 시작.bat 이 멈추지 않고 정해진 규칙으로 정리되는가.

새 DB를 따로 만들어 앞 마이그레이션까지 넣고, 옛 판이 남겼을 수 있는 데이터를 넣은 뒤 그 마이그레이션 파일을 실제로 적용해 결과를 본다.
"""
import pytest

from conftest import MIGRATIONS

AUDIT_CLEANUP = '20261030000068'
HEALTH_FIXES = '20261030000069'


@pytest.fixture
def db_before_068(scratch_db):
    """마이그레이션 067까지 넣은 버릴 DB(테스트마다 새로 — conftest scratch_db) → psycopg 연결."""
    import psycopg
    with psycopg.connect(scratch_db, autocommit=True) as conn:
        for sql in sorted(MIGRATIONS.glob('*.sql')):
            if sql.name >= AUDIT_CLEANUP:
                break
            conn.execute(sql.read_text(encoding='utf8'))
        conn.execute("INSERT INTO tenants(id, name) VALUES ('hyd', '시험 공장')")     # 처리 건 · 작업 행이 가리키는 테넌트
        yield conn


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


# ---------------------------------------------------------------- 069 건강검진 고침(이미 쓰던 DB 에 들어갈 때)
STDIO_NEO4J = {"command": "python", "args": ["-m", "hydcommon.neo4j_mcp"],
               "env": {"NEO4J_URI": "bolt://neo4j:7687", "NEO4J_USERNAME": "neo4j", "NEO4J_PASSWORD": "hydpass123"}}
NEO4J_URL = {"type": "url", "url": "http://dmn-mcp:8198/neo4j/mcp", "transport": "streamable_http"}


@pytest.fixture
def db_before_069(scratch_db):
    """마이그레이션 068까지 넣은 버릴 DB(옛 판 학생 PC 의 업무 DB 자리) → psycopg 연결."""
    import psycopg
    with psycopg.connect(scratch_db, autocommit=True) as conn:
        for sql in sorted(MIGRATIONS.glob('*.sql')):
            if sql.name >= HEALTH_FIXES:
                break
            conn.execute(sql.read_text(encoding='utf8'))
        yield conn


def apply_069(conn):
    conn.execute(next(MIGRATIONS.glob(HEALTH_FIXES + '_*.sql')).read_text(encoding='utf8'))


def seed_text(skill):
    import re
    seed = (MIGRATIONS.parent / 'seed.sql').read_text(encoding='utf8')
    return re.search(r"'" + skill + r"', '[^']*', \$skill\$(.*?)\$skill\$", seed, re.S).group(1)


def text_053_new():
    import re
    src = next(MIGRATIONS.glob('20261012000053_*.sql')).read_text(encoding='utf8')
    return re.search(r"new_content text := \$new\$(.*?)\$new\$", src, re.S).group(1)


@pytest.mark.parametrize('before, after', [
    (STDIO_NEO4J, NEO4J_URL),                                                     # 기준 stdio 설정 → dmn-mcp 의 HTTP 주소
    (dict(STDIO_NEO4J, command='python3'), NEO4J_URL),                            # 같은 기준(python3)
    ({"command": "python", "args": ["-m", "my_neo4j"]}, {"command": "python", "args": ["-m", "my_neo4j"]}),   # 학생이 바꾼 설정은 그대로
    ({"type": "url", "url": "http://other:1/mcp", "transport": "streamable_http"},
     {"type": "url", "url": "http://other:1/mcp", "transport": "streamable_http"}),
], ids=['기준_stdio', '기준_python3', '학생_명령', '학생_주소'])
def test_수업_neo4j_도구가_기준_stdio_설정이면_dmn_mcp의_HTTP_주소로_바뀌고_다른_설정은_그대로다(db_before_069, before, after):
    from psycopg.types.json import Jsonb
    db_before_069.execute("INSERT INTO tenants(id, name, mcp) VALUES ('hyd', '시험', %s)", (Jsonb({'mcpServers': {'neo4j': before}}),))
    apply_069(db_before_069)
    (mcp,) = db_before_069.execute("SELECT mcp FROM tenants WHERE id='hyd'").fetchone()
    assert mcp['mcpServers']['neo4j'] == after


@pytest.mark.parametrize('content, origin, changed', [
    ('053', 'seed', True),          # 053 이 올린 판 그대로 → 지금 seed 본문
    ('student', 'seed', False),     # 강사 · 학생이 고친 본문은 그대로
    ('053', 'user', False),         # 포털에서 만든(origin=user) 같은 이름 스킬은 그대로
], ids=['053_기준_본문', '고친_본문', '학생_스킬'])
def test_예비품_구매_기준_스킬이_053_판이면_seed_본문으로_바뀐다(db_before_069, content, origin, changed):
    old = text_053_new() if content == '053' else '# 학생이 고친 구매 스킬'
    db_before_069.execute("INSERT INTO tenants(id, name) VALUES ('hyd', '시험')")
    db_before_069.execute("INSERT INTO tenant_skills(tenant_id, skill_name, description, content, origin) VALUES ('hyd', 'spare-purchase-planning', 'd', %s, %s)",
                          (old, origin))
    apply_069(db_before_069)
    (now,) = db_before_069.execute("SELECT content FROM tenant_skills WHERE skill_name='spare-purchase-planning'").fetchone()
    assert now == (seed_text('spare-purchase-planning') if changed else old)


def outbox(conn, pid, decision):
    import uuid
    from psycopg.types.json import Jsonb
    todo = str(uuid.uuid4())
    conn.execute("INSERT INTO todolist(id, proc_inst_id, activity_id, status, tenant_id) VALUES (%s, %s, 'T_approve', 'DONE', 'hyd')", (todo, pid))
    conn.execute("INSERT INTO process_approval_outbox(todo_id, proc_inst_id, tenant_id, decision_id, payload, status) VALUES (%s, %s, 'hyd', %s, %s, 'PENDING')",
                 (todo, pid, decision, Jsonb({'decision': decision})))
    return todo


@pytest.mark.parametrize('end_event, status', [('duplicate-closed', 'DISCARDED'), (None, 'PENDING')], ids=['068이_닫은_중복', '진행_중_처리_건'])
def test_068이_닫은_중복_처리_건의_승인_전달_대기는_폐기되고_다른_처리_건은_그대로다(db_before_069, end_event, status):
    db_before_069.execute("INSERT INTO tenants(id, name) VALUES ('hyd', '시험')")
    running(db_before_069, 'c3_cooling.x', 'INC-1029-09', '2026-10-29 10:00:00',
            status='CANCELLED' if end_event else 'RUNNING')
    db_before_069.execute('UPDATE bpm_proc_inst SET end_event=%s WHERE proc_inst_id=%s', (end_event, 'c3_cooling.x'))
    todo = outbox(db_before_069, 'c3_cooling.x', 'DEC-dup')
    apply_069(db_before_069)
    got, history = db_before_069.execute('SELECT status, history FROM process_approval_outbox WHERE todo_id=%s', (todo,)).fetchone()
    assert got == status
    if status == 'DISCARDED':
        assert history[-1]['previous_status'] == 'PENDING' and '068' in history[-1]['reason']


WRITES = [
    ("INSERT INTO public.tenants(id, name) VALUES ('evil', 'x')", 'tenants'),
    ("UPDATE public.tenants SET mcp = '{}'::jsonb", 'tenants'),
    ("INSERT INTO public.todolist(id, proc_inst_id, activity_id, status, tenant_id) VALUES (gen_random_uuid(), 'p', 'a', 'TODO', 'hyd')", 'todolist'),
    ("DELETE FROM public.process_rework_receipt", 'process_rework_receipt'),
    ("SELECT * FROM public.process_rework_receipt", 'process_rework_receipt'),
]


@pytest.mark.parametrize('role', ['anon', 'authenticated'])
@pytest.mark.parametrize('sql, table', WRITES, ids=[f'{w[1]}_{w[0].split()[0]}' for w in WRITES])
def test_공개_키_역할은_업무_표에_쓰거나_재작업_영수증을_읽지_못한다(pg_dsn, role, sql, table):
    """G2-02: 시드까지 들어간 학생 PC 의 업무 DB(묶음 DB)에서 Supabase 공개 키 역할(anon · 가입한 사용자 authenticated)로 해 본다."""
    import psycopg
    with psycopg.connect(pg_dsn) as conn:
        conn.execute(f'SET LOCAL ROLE {role}')
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(sql)


def test_CMMS_표준_작업은_지금_지식의_SOP_번호이고_옛_번호는_없다(db_before_069):
    """FG 넘김: 표준 작업이 옛 SOP 번호(037)라 손익이 모든 작업지시 카드에서 「미확인」이었다."""
    apply_069(db_before_069)
    rows = dict(db_before_069.execute('SELECT sop, part_no FROM ent.task_standards').fetchall())
    assert rows == {'SOP-COOL-14': None, 'SOP-COOL-15': None, 'SOP-FAN-11': 'P-FAN-BRG', 'SOP-FAN-12': 'P-FAN-BRG'}


def inbox(conn, kind, status, parent=None, semantic='a'):
    row = conn.execute(
        "INSERT INTO process_source_inbox(tenant_id, source, delivery_key, topic, partition_no, offset_no, event_key, asset, kind, payload, "
        "payload_sha, semantic_sha, wire_kind, wire_base64, wire_sha, policy, status, parent_id) "
        "VALUES ('hyd', 'kafka', gen_random_uuid()::text, 'plant.status', 0, (random() * 1e9)::bigint, 'ack:CMD-1', 'HYD-01', %s, '{}', "
        "repeat('0', 64), repeat(%s, 64), 'decoded', '', repeat('0', 64), '{}', %s, %s) RETURNING id",
        (kind, semantic, status, parent)).fetchone()
    return row[0]


def test_쌓인_같은_명령_응답_중복_접수는_지우고_설비_상태는_원래_접수를_가리킨다(db_before_069):
    """P2-01: 설비 상태에 실린 같은 명령 응답이 1초마다 「중복 접수」 행으로 쌓였다(코드는 FB 가 고침 — 이미 쌓인 행)."""
    first = inbox(db_before_069, 'ACK', 'HANDLED')
    dups = [inbox(db_before_069, 'ACK', 'DUPLICATE', first) for _ in range(3)]
    conflicts = [inbox(db_before_069, 'ACK', 'CONFLICT', first, semantic='b') for _ in range(2)]
    db_before_069.execute("INSERT INTO process_source_state(tenant_id, asset, source_time, receipt_id, payload) VALUES ('hyd', 'HYD-01', now(), %s, '{}')",
                          (dups[-1],))
    apply_069(db_before_069)
    left = [r for (r,) in db_before_069.execute('SELECT id FROM process_source_inbox ORDER BY id').fetchall()]
    (state,) = db_before_069.execute("SELECT receipt_id FROM process_source_state WHERE asset='HYD-01'").fetchone()
    assert left == [first, conflicts[0]] and state == first


def test_처리_기록_위치는_옛_위치를_이어받고_새_기록은_시각_순서로_다음_번호를_받는다(db_before_069):
    """G2-11: 스트림 위치를 찾으려 조회마다 events 전체를 훑었다 — 위치를 events 칸 하나와 「위치 없음」 부분 색인으로."""
    for n, at in enumerate(('2026-10-30 10:00', '2026-10-30 10:01')):
        db_before_069.execute("INSERT INTO events(id, job_id, event_type, data, \"timestamp\") VALUES (%s, 'j', 'task_started', '{}', %s)", (f'old{n}', at))
        db_before_069.execute('INSERT INTO event_stream_positions(event_id) VALUES (%s)', (f'old{n}',))
    apply_069(db_before_069)
    db_before_069.execute("INSERT INTO events(id, job_id, event_type, data, \"timestamp\") VALUES ('new-late', 'j', 'task_started', '{}', '2026-10-30 10:05'), "
                          "('new-early', 'j', 'task_started', '{}', '2026-10-30 10:03')")
    (count,) = db_before_069.execute('SELECT public.publish_event_positions()').fetchone()
    order = [r for (r,) in db_before_069.execute('SELECT id FROM events ORDER BY stream_position').fetchall()]
    assert count == 2 and order == ['old0', 'old1', 'new-early', 'new-late']
    assert db_before_069.execute("SELECT to_regclass('public.event_stream_positions')").fetchone() == (None,)


FOLLOWUPS = '20261030000070'


@pytest.fixture
def db_before_070(scratch_db):
    """마이그레이션 069까지 넣은 버릴 DB → psycopg 연결."""
    import psycopg
    with psycopg.connect(scratch_db, autocommit=True) as conn:
        for sql in sorted(MIGRATIONS.glob('*.sql')):
            if sql.name >= FOLLOWUPS:
                break
            conn.execute(sql.read_text(encoding='utf8'))
        yield conn


def apply_070(conn):
    conn.execute(next(MIGRATIONS.glob(FOLLOWUPS + '_*.sql')).read_text(encoding='utf8'))


@pytest.mark.parametrize('topic, kind', [('audit', 'REJECT'), ('plant.status', 'ACK')], ids=['관문_거절', '명령_응답'])
def test_원천_접수는_명령_관문의_거절을_받는다(db_before_070, topic, kind):
    """G3b-9: 관문 거절(감사 토픽)이 접수 종류 · 토픽 검사에 없어 insert 에서 실패했다."""
    apply_070(db_before_070)
    (n,) = db_before_070.execute(
        "INSERT INTO process_source_inbox(tenant_id, source, delivery_key, topic, partition_no, offset_no, event_key, asset, kind, payload, "
        "payload_sha, semantic_sha, wire_kind, wire_base64, wire_sha, policy, status) VALUES ('hyd', 'kafka', gen_random_uuid()::text, %s, 0, 1, "
        "'k', 'HYD-01', %s, '{}', repeat('0', 64), repeat('0', 64), 'decoded', '', repeat('0', 64), '{}', 'PENDING') RETURNING id",
        (topic, kind)).fetchone()
    assert n


def test_순정_공급사_여부는_공급사_원장에_있고_견적_읽기에_실린다(db_before_070):
    """G3b-27: 순정 여부를 표시 이름 글자로 가렸다 — 주인은 업무 DB 공급사 원장."""
    db_before_070.execute("INSERT INTO ent.suppliers(id, key, name, part_no, price, fail_rate, lead_d, avl, quality_score) VALUES "
                          "('sup:a','a','A','P-CLR-CORE',1,0,1,true,1), ('sup:b','b','B','P-CLR-CORE',1,0,1,true,1)")
    apply_070(db_before_070)
    oem = dict(db_before_070.execute("SELECT supplier, oem FROM jsonb_to_recordset(ent.part_quotes_read('P-PMP-SEAL')->'records') "
                                     "AS r(supplier text, oem boolean)").fetchall())
    assert oem == {'sup:a': False, 'sup:b': True}


def test_원문에_값이_없는_표준_작업과_쓰는_길_없는_업무_표는_없다(db_before_070):
    """069 §9 가 팬 점검 · 벨트 교체에 베어링 소모를 지어 넣었다 — 강사 서명 원문에 그 값이 없다."""
    apply_070(db_before_070)
    sops = {s for (s,) in db_before_070.execute('SELECT sop FROM ent.task_standards').fetchall()}
    tables = db_before_070.execute("SELECT to_regclass('ent.shipments'), to_regclass('ent.lot_dispositions'), to_regclass('ent.ems_actions')").fetchone()
    assert sops == {'SOP-COOL-14', 'SOP-COOL-15'} and tables == (None, None, None)
