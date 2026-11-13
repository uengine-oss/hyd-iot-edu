"""읽기 SQL 가드(common/hydcommon/sql_read.py) — 허용 함수는 sqlglot 정규 이름으로 견주고(G2-03), 객체 식별 형식 변환을 막는다(G2-19).

규칙: 흔한 읽기(EXISTS · ANY(ARRAY) · 정규식 · jsonb ? · TO_CHAR …)는 통과하고, 쓰기 · 다른 스키마 · 시스템 함수 · reg* 변환은 그 이름을
말하며 거절한다. 바깥 LIMIT 은 늘 한도 이하로 붙는다. 실제 업무 DB 에 그대로 돌려 「통과한 SQL 은 실제로 실행된다」도 본다.
"""
import psycopg
import pytest

from hydcommon.sql_read import MAX_ROWS, TIMESERIES_FUNCTIONS, SqlRejected, guard


@pytest.mark.parametrize('sql', [
    "select to_char(created_at, 'YYYY-MM') from work_orders",
    "select to_date('2026-10-30', 'YYYY-MM-DD'), to_timestamp('2026', 'YYYY'), to_timestamp(0)",
    "select json_agg(id), jsonb_agg(id), var_pop(1), string_agg(id, ','), bool_and(true) from work_orders",
    "select * from work_orders w where exists (select 1 from parts p where p.part_no = w.id)",
    "select * from work_orders w where not exists (select 1 from parts)",
    "select * from parts where part_no = any(array['P-PMP-SEAL', 'P-FAN-BRG'])",
    "select * from parts where part_no ~ '^P-' and part_no !~ 'X'",
    "select date_trunc('hour', now()), now() - interval '1 hour', 1::numeric, 'a'::text",
    "select case when 1 > 0 then 'y' else 'n' end, coalesce(null, 1), position('a' in 'cat')",
    "with x as (select 1 as a) select a from x union select 2",
])
def test_흔한_읽기는_통과한다(sql):
    assert guard(sql).endswith(f'LIMIT {MAX_ROWS}')


@pytest.mark.parametrize('sql, word', [
    ("select 'public.users'::regclass", 'REGCLASS'),                    # G2-19: 객체 존재를 알아낼 수 있었다
    ("select 'ent.exec_skill'::regproc", 'REGPROC'),
    ("select 'postgres'::regrole", 'REGROLE'),
    ('select pg_sleep(1)', 'PG_SLEEP'),
    ("select set_config('a', 'b', false)", 'SET_CONFIG'),
    ('select generate_series(1, 3)', 'GENERATE_SERIES'),
    ('select * from public.users', 'public.users'),
    ('select * from pg_catalog.pg_roles', 'pg_roles'),
    ('delete from parts', 'SELECT'),
    ('select 1; delete from parts', 'SELECT'),
    ('with d as (delete from parts returning *) select * from d', 'delete'),
    ('select * into t from parts', 'into'),
    ('select * from parts for update', 'lock'),
    ('', 'SQL'),
])
def test_막을_것은_그_이름을_말하며_거절한다(sql, word):
    with pytest.raises(SqlRejected) as caught:
        guard(sql)
    assert word.lower() in str(caught.value).lower()


@pytest.mark.parametrize('sql, limit', [('select 1 limit 100000', 200), ('select 1 limit all', 200), ('select 1 limit 5', 5),
                                        ('select 1 fetch first 5000 rows only', 200)])
def test_바깥_행_한도는_요청보다_크지_않다(sql, limit):
    assert guard(sql).endswith(f'LIMIT {limit}')


def test_시계열_가드는_세_표와_time_bucket만_더한다():
    ok = guard("select time_bucket('1 minute', time) b, avg(value) from tag_1s group by b", schema='public',
               tables={'tag_1s', 'feat_1s', 'tag_1m'}, functions=TIMESERIES_FUNCTIONS)
    assert 'public.tag_1s' in ok
    with pytest.raises(SqlRejected, match='sink_offsets'):
        guard('select * from sink_offsets', schema='public', tables={'tag_1s'}, functions=TIMESERIES_FUNCTIONS)


def test_통과한_읽기는_실제_업무_DB에서_실행된다(pg_dsn):
    sql = guard("select part_no, to_char(now(), 'YYYY') from parts p where exists (select 1 from parts q where q.part_no = p.part_no) "
                "and part_no = any(array['P-PMP-SEAL']) and part_no ~ '^P-'")
    with psycopg.connect(pg_dsn) as db:
        rows = db.execute(sql).fetchall()
    assert rows and rows[0][0] == 'P-PMP-SEAL'
