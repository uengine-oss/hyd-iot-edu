"""전용 읽기 연결(common/hydcommon/enterprise.py `reader_connection(dsn, role)`) — 연결한 계정이 정확히 요구한 역할이고 특권(superuser ·
createrole · createdb · bypassrls)이 하나도 없을 때만 연결을 돌려준다. 아니면 그 계정 이름을 말하며 거절하고 연 연결은 닫는다.

업무 DB(MCP · 현재 사실 확인)의 hyd_enterprise_reader 와 시계열 DB(데이터 연결)의 hyd_timeseries_reader 가 같은 함수를 쓴다(G3b-26 —
옛 판은 시계열 쪽에 같은 코드 사본이 있었다). 실제 테스트 업무 DB(pg_dsn)와 이 테스트 자리의 시계열 컨테이너(timescale)에 붙는다.
특권 속성 표는 이 테스트 자리의 시계열 컨테이너(버리는 서버)에 시험 계정을 만들어 본다.
"""
import uuid

import psycopg
import pytest

from conftest import until
from conftest import as_user, ent_reader, ts_reader
from hydcommon.enterprise import reader_connection

ENT_ROLE, TS_ROLE = 'hyd_enterprise_reader', 'hyd_timeseries_reader'



def test_업무_DB_전용_읽기_계정이면_연결을_돌려주고_쓰기는_DB가_거절한다(pg_dsn):
    conn = reader_connection(ent_reader(pg_dsn))
    try:
        assert conn.info.transaction_status == psycopg.pq.TransactionStatus.IDLE      # 확인 질의의 트랜잭션은 닫고 준다
        assert conn.execute('select current_user').fetchone() == (ENT_ROLE,)
        assert conn.execute("select count(*) from ent.parts where part_no = 'P-PMP-SEAL'").fetchone() == (1,)
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            conn.execute("insert into ent.parts (part_no, name, std_price) values ('P-FO2', '시험', 1)")
    finally:
        conn.close()


def test_시계열_전용_읽기_계정은_그_역할을_요구하면_받고_세_표_밖은_DB가_거절한다(timescale):
    conn = reader_connection(ts_reader(timescale), TS_ROLE)
    try:
        assert conn.execute('select current_user').fetchone() == (TS_ROLE,)
        conn.execute('select count(*) from tag_1s').fetchone()
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute('select * from alerts')
    finally:
        conn.close()


def _backends(admin_dsn, app):
    with psycopg.connect(admin_dsn, autocommit=True) as db:
        return db.execute('select count(*) from pg_stat_activity where application_name = %s', (app,)).fetchone()[0]


@pytest.mark.parametrize('who, role, connected', [
    ('ent_admin', ENT_ROLE, 'postgres'),           # 관리자(쓰기 권한) 계정
    ('ts_reader', ENT_ROLE, TS_ROLE),              # 다른 전용 계정
    ('ent_reader', TS_ROLE, ENT_ROLE),
    ('ts_admin', TS_ROLE, 'hyd'),
], ids=['업무 관리자', '업무 자리에 시계열 계정', '시계열 자리에 업무 계정', '시계열 관리자'])
def test_요구한_역할이_아닌_계정은_그_이름을_말하며_거절하고_연_연결을_닫는다(pg_dsn, timescale, who, role, connected):
    app = 'fo2-' + uuid.uuid4().hex[:12]
    dsn, admin = {'ent_admin': (as_user(pg_dsn, 'postgres', 'postgres', application_name=app), pg_dsn),
                  'ts_reader': (ts_reader(timescale, application_name=app), timescale.dsn),
                  'ent_reader': (ent_reader(pg_dsn, application_name=app), pg_dsn),
                  'ts_admin': (timescale.dsn + f'?application_name={app}', timescale.dsn)}[who]
    with pytest.raises(RuntimeError) as caught:
        reader_connection(dsn, role)
    assert f'{role} required' in str(caught.value) and f'this connection is {connected}' in str(caught.value)
    until(lambda: _backends(admin, app) == 0, f'거절한 연결({app})이 닫힌다', timeout=10)


@pytest.fixture
def probe_role(timescale):
    """시계열 컨테이너(이 테스트 자리 전용)에 특권 속성 하나를 가진 로그인 계정을 만든다 — 끝나면 지운다."""
    made = []

    def make(attribute):
        name = f'fo2_probe_{attribute.lower()}'
        with psycopg.connect(timescale.dsn, autocommit=True) as db:
            db.execute(f'DROP ROLE IF EXISTS {name}')
            db.execute(f"CREATE ROLE {name} LOGIN {attribute} PASSWORD 'fo2-probe'")
        made.append(name)
        return name, as_user(timescale.dsn, name, 'fo2-probe')
    yield make
    with psycopg.connect(timescale.dsn, autocommit=True) as db:
        for name in made:
            db.execute(f'DROP ROLE IF EXISTS {name}')


@pytest.mark.parametrize('attribute, accepted', [
    ('NOSUPERUSER', True), ('SUPERUSER', False), ('CREATEROLE', False), ('CREATEDB', False), ('BYPASSRLS', False),
], ids=['특권 없음', 'superuser', 'createrole', 'createdb', 'bypassrls'])
def test_이름이_맞아도_특권이_하나라도_있으면_거절한다(probe_role, attribute, accepted):
    name, dsn = probe_role(attribute)
    if accepted:
        reader_connection(dsn, name).close()
    else:
        with pytest.raises(RuntimeError, match=f'{name} required'):
            reader_connection(dsn, name)


def test_인증이_틀리면_DB_오류를_그대로_올린다(pg_dsn):
    """연결 실패는 삼키지 않는다 — 부르는 쪽(fabric.failure_reason)이 사람 문장으로 바꾼다."""
    with pytest.raises(psycopg.OperationalError, match='password authentication failed'):
        reader_connection(as_user(pg_dsn, ENT_ROLE, 'wrong-password'))
