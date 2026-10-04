import pytest
import psycopg
from agentsvc.tools.mcp_tsdb import read_sql
from hydcommon.sql_read import SqlRejected
from dmn_mcp.tools import enveloped


@pytest.mark.parametrize('sql',[
    'delete from tag_1s',
    'select * from public.audit',
    'select * from pg_catalog.pg_authid',
    'select * from ent.assets',
    "select set_config('default_transaction_read_only','off',false)",
    'select pg_sleep(10)',
    'with x as (delete from tag_1s returning *) select * from x',
    'select * into temp t from tag_1s',
    'select public.evil(value) from tag_1s',
    'select * from tag_1s for update',
    'select 1;select 2',
])
def test_rejects_non_sensor_or_effectful_query(sql):
    with pytest.raises(SqlRejected):read_sql(sql)


def test_generated_duration_query_preserves_scope_parameters_and_window():
    sql="""with samples as (
      select time,value,lag(time) over (order by time) as previous
      from tag_1s where asset=%(asset)s and name='VS1' and time>now()-interval '30 seconds'
    ) select bool_and(value>1.2) as all_observed_high,max(time)-min(time) as covered,
      max(time-previous) as largest_gap,count(*) as observations from samples"""
    checked=read_sql(sql)
    assert 'public.tag_1s' in checked and 'public.samples' not in checked
    assert '%(asset)s' in checked and 'LAG(time)' in checked and checked.endswith('LIMIT 200')


def test_timescale_buckets_and_row_boundary():
    checked=read_sql("select time_bucket(interval '1 minute',time),avg(value) from tag_1s group by 1 limit 900")
    assert 'TIME_BUCKET' in checked and checked.endswith('LIMIT 200')


def test_business_queries_also_accept_boolean_combinations():
    from enterprise_mcp.sql_guard import guard
    result=guard("select code from assets where code='HYD-01' and (name is not null or code='HYD-02')")
    assert 'ent.assets' in result and ' AND ' in result and ' OR ' in result


def test_database_errors_are_not_normal_empty_results():
    def invalid():raise psycopg.errors.UndefinedColumn('column missing')
    def unavailable():raise psycopg.OperationalError('connection unavailable')
    assert enveloped(invalid)()['error_kind']=='INVALID'
    assert enveloped(unavailable)()['error_kind']=='UNKNOWN'
    assert enveloped(lambda:dict(rows=[],row_count=0))()['result']=='ok'
