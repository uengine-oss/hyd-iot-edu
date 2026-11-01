"""업무 DB 구조 변화 → 지식 그래프의 입력 상태(procsvc/ddl_sync.py) — 실제 PostgreSQL 카탈로그와 실제 Neo4j(빈 그래프)."""
import psycopg
import pytest

from procsvc import ddl_sync


@pytest.mark.parametrize('declared, live, state', [
    ('timestamp with time zone', 'timestamp without time zone', 'OK'),       # 같은 「시각」 묶음
    ('integer', 'bigint', 'OK'), ('varchar(20)', 'character varying', 'OK'),
    ('integer', 'text', 'TYPE_CHANGED'), ('timestamptz', 'integer', 'TYPE_CHANGED'),
    ('integer', None, 'MISSING'),
])
def test_묶인_열의_상태는_뜻의_묶음이_같은지로_판정한다(declared, live, state):
    row = {'id': 'in:x', 'schema': 'ent', 'table': 't', 'column': 'c', 'sqlType': declared}
    columns = {} if live is None else {('ent', 't', 'c'): live}
    assert ddl_sync.drift([row], columns)[0]['state'] == state


def test_주석은_처음_본_값을_기준으로_두고_그_뒤에_바뀌면_알린다():
    row = {'id': 'in:x', 'schema': 'ent', 'table': 't', 'column': 'c', 'sqlType': 'integer'}
    first = ddl_sync.drift([row], {('ent', 't', 'c'): ('integer', '수량')})[0]
    assert (first['state'], first['base'], first['changed']) == ('OK', '수량', True)
    seen = dict(row, state='OK', live='integer', liveComment='수량', baseComment='수량')
    assert ddl_sync.drift([seen], {('ent', 't', 'c'): ('integer', '수량')})[0]['changed'] is False
    assert ddl_sync.drift([seen], {('ent', 't', 'c'): ('integer', '주문 수량(개)')})[0]['state'] == 'COMMENT_CHANGED'


def test_업무_DB_구조가_바뀌면_그래프의_입력_상태가_바뀐_것만_고쳐진다(scratch_db, neo4j_graph):
    with psycopg.connect(scratch_db, autocommit=True) as db:
        db.execute("CREATE SCHEMA ent; CREATE TABLE ent.orders (due timestamptz, qty integer, note text)")
        db.execute("COMMENT ON COLUMN ent.orders.qty IS '수량'")
    neo4j_graph.query("""UNWIND $rows AS r CREATE (i:InputData) SET i = r""", rows=[
        {'id': 'in:due', 'datasource': 'hyd-enterprise', 'schema': 'ent', 'table': 'orders', 'column': 'due', 'sqlType': 'timestamptz'},
        {'id': 'in:qty', 'datasource': 'hyd-enterprise', 'schema': 'ent', 'table': 'orders', 'column': 'qty', 'sqlType': 'integer'},
        {'id': 'in:gone', 'datasource': 'hyd-enterprise', 'schema': 'ent', 'table': 'orders', 'column': 'gone', 'sqlType': 'text'},
        {'id': 'in:other', 'datasource': 'mes', 'schema': 'ent', 'table': 'orders', 'column': 'nowhere', 'sqlType': 'text'}])
    q = lambda query, **params: neo4j_graph.query(query, **params)                       # noqa: E731
    connect = lambda: psycopg.connect(scratch_db)                                        # noqa: E731
    first = ddl_sync.sync(q, connect)
    assert first['checked'] == 3, '다른 원천(mes)의 입력은 이 연결로 보지 않는다'
    assert first['states'] == {'OK': ['in:due', 'in:qty'], 'MISSING': ['in:gone']}
    assert ddl_sync.sync(q, connect)['changed'] == 0, '바뀐 것이 없으면 쓰지 않는다'
    with psycopg.connect(scratch_db, autocommit=True) as db:
        db.execute("ALTER TABLE ent.orders ALTER COLUMN due TYPE integer USING 0")
        db.execute("COMMENT ON COLUMN ent.orders.qty IS '주문 수량(개)'")
    after = ddl_sync.sync(q, connect)
    assert after['states'] == {'TYPE_CHANGED': ['in:due'], 'COMMENT_CHANGED': ['in:qty'], 'MISSING': ['in:gone']}
    nodes = {r['id']: r for r in neo4j_graph.query('MATCH (i:InputData) RETURN i.id AS id, i.sourceState AS state, i.sourceLiveType AS live')}
    assert (nodes['in:due']['state'], nodes['in:due']['live']) == ('TYPE_CHANGED', 'integer')
    assert nodes['in:other']['state'] is None


# ---------------------------------------------------------------- 원천 정하기(place) — 실제 업무 DB 카탈로그(마이그레이션 · 시드)
from pathlib import Path

LEGACY_SQL = (Path(__file__).resolve().parents[3] / 'it' / 'portal' / 'www' / 'samples' / 'legacy-plant-db.sql').read_text(encoding='utf-8')


def test_원천을_고르지_않으면_파일의_표가_있는_원천의_스키마로_해석한다(pg_dsn):
    tables, source, notes = ddl_sync.place(LEGACY_SQL, None, lambda: psycopg.connect(pg_dsn))
    assert source == 'hyd-legacy' and {t.schema for t in tables} == {'legacy'}, (source, notes)
    assert notes == ['이 파일의 표가 있는 원천: 옛 설비 DB (legacy 스키마)'], notes


@pytest.mark.parametrize('text, picked, source, schema, note', [
    (LEGACY_SQL, 'hyd-enterprise', 'hyd-enterprise', 'ent', None),
    ('CREATE TABLE assets (code text primary key, name text);', None, 'hyd-enterprise', 'ent', '이 파일의 표가 있는 원천: 업무 DB'),
    ('CREATE TABLE nowhere_t (a int);', None, 'hyd-enterprise', 'ent', '이 파일의 표가 없어'),
], ids=['사람이 고른 원천', '업무 DB 표', '어디에도 없는 표'])
def test_고른_원천이나_표가_있는_원천을_쓰고_없으면_그렇게_말한다(pg_dsn, text, picked, source, schema, note):
    tables, got, notes = ddl_sync.place(text, picked, lambda: psycopg.connect(pg_dsn))
    assert got == source and {t.schema for t in tables} == {schema}
    assert (not notes) if note is None else note in notes[0], notes


def test_옛_설비_DB에_이은_입력도_구조_변화를_맞춘다(pg_dsn, neo4j_graph):
    neo4j_graph.query("""UNWIND $rows AS r CREATE (i:InputData) SET i = r""", rows=[
        {'id': 'in:tmp', 'datasource': 'hyd-legacy', 'schema': 'legacy', 'table': 'T_EQP01', 'column': 'C_TMP_O', 'sqlType': 'numeric(5,1)'},
        {'id': 'in:gone', 'datasource': 'hyd-legacy', 'schema': 'legacy', 'table': 'T_EQP01', 'column': 'NO_SUCH', 'sqlType': 'text'}])
    report = ddl_sync.sync(lambda query, **p: neo4j_graph.query(query, **p), lambda: psycopg.connect(pg_dsn))
    assert report['states'] == {'OK': ['in:tmp'], 'MISSING': ['in:gone']}, report


@pytest.mark.parametrize('requested', ['hyd-unknown', 'ent', 'mes'])
def test_고를_수_없는_원천이면_화면의_원천_이름으로_거절하고_내부_id를_보이지_않는다(requested):
    """마지막고침 검증 H12: 학생에게 가는 거절 문장에 원천 id(hyd-enterprise · hyd-legacy)가 아니라 화면의 원천 이름이 실린다.
    고를 수 없는 원천은 카탈로그를 읽기 전에 거절되므로 연결은 부르지 않는다(부르면 실패하는 연결을 준다)."""
    def no_connect():
        raise AssertionError('원천을 고른 거절은 업무 DB 카탈로그를 읽지 않는다')
    with pytest.raises(ValueError) as caught:
        ddl_sync.place('CREATE TABLE T_EQP00 (EQP_ID VARCHAR(10));', requested, no_connect)
    message = str(caught.value)
    assert '고를 수 있는 원천' in message
    assert all(ddl_sync.SOURCES[d]['label'] in message for d in ddl_sync.DDL_SOURCES)
    assert not any(d in message for d in ddl_sync.DDL_SOURCES), message
