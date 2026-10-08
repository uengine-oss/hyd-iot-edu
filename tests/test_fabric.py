"""A11 데이터 패브릭 미니 (hydcommon.fabric · procsvc.fabric_api · dmn-mcp fabric_query).

Scripted fake connections stand in for the two readers: every statement the fabric sends is recorded, so the tests check
what reaches a database (read-only transaction first, guarded SQL, parameters) and what a person reads when a source fails.
The live run against real PostgreSQL schemas is scripts/probe_fabric.py (.evidence/A11/)."""
from __future__ import annotations

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hydcommon import fabric as fb
from hydcommon.fabric import ENT, TS, Fabric, FabricUnavailable, SourceUnavailable, SqlRejected


class Col:
    def __init__(self, name):
        self.name = name


class FakeCursor:
    def __init__(self, conn):
        self.conn, self.description, self._rows = conn, None, []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.conn.log.append((sql, params))
        out = self.conn.handler(sql, params)
        cols, rows = out if out is not None else ([], [])
        self.description = [Col(c) for c in cols] if cols else None
        self._rows = list(rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


class FakeConn:
    def __init__(self, handler, log):
        self.handler, self.log, self.closed = handler, log, False

    def cursor(self):
        return FakeCursor(self)

    def rollback(self):
        self.log.append(('ROLLBACK', None))

    def close(self):
        self.closed = True


def catalog_rows(tables):
    """tables: {name: [(column, type, fk)]} → CATALOG_SQL rows."""
    return [(t, None, 'r', c, typ, True, None, False, fk) for t, cols in tables.items() for c, typ, fk in cols]


ENT_TABLES = {
    'assets': [('code', 'text', None), ('name', 'text', None), ('line', 'text', None)],
    'production_orders': [('order_id', 'text', None), ('asset', 'text', 'assets.code'), ('due_at', 'timestamp with time zone', None),
                          ('hour_value', 'numeric', None)],
    'sales_contracts': [('sales_order', 'text', None), ('asset', 'text', 'assets.code'), ('penalty_per_h', 'numeric', None)],
    'parts': [('part_no', 'text', None)],
    'suppliers': [('id', 'text', None)],
}
TS_TABLES = {'tag_1s': [('time', 'timestamp with time zone', None), ('asset', 'text', None), ('name', 'text', None),
                        ('value', 'double precision', None)]}


def ent_handler(sql, params):
    from datetime import datetime, timezone
    from decimal import Decimal
    if 'from pg_class c' in sql:
        return [None] * 9, catalog_rows(ENT_TABLES)
    if 'current_setting' in sql:
        return ['u', 'ro', 'db', 'now'], [('hyd_enterprise_reader', 'on', 'postgres', datetime(2026, 10, 8, tzinfo=timezone.utc))]
    if 'FROM ent.production_orders' in sql:
        return ['order_id', 'customer', 'due_at', 'due_in_h', 'hour_value', 'remaining_qty', 'status'], [
            ('MO-1', 'A사', datetime(2026, 10, 8, 16, tzinfo=timezone.utc), Decimal('6.00'), Decimal('50'), 400, 'RUNNING')]
    if 'FROM ent.sales_contracts' in sql:
        return ['sales_order', 'customer_tier', 'penalty_per_h'], [('SO-1', 'OEM', Decimal('120'))]
    if 'FROM ent.quality_profiles' in sql:
        return ['hot_min', 'auto_lot', 'auto_qty', 'auto_claim', 'gen_lot', 'gen_qty'], [(12, 'L-1', 800, Decimal('3000'), 'L-2', 300)]
    if 'FROM ent.maintenance_history' in sql:
        return ['wo', 'task', 'performed_at'], [('WO-9', '팬 베어링 교체', datetime(2026, 9, 1, tzinfo=timezone.utc))]
    if 'from ent.assets' in sql:
        return ['code', 'name', 'line'], ([('HYD-01', '유압 파워팩 1호기', 'A라인')] if params['asset'] == 'HYD-01' else [])
    if 'from ent."production_orders"' in sql:
        return ['order_id', 'asset'], [('MO-1', 'HYD-01')]
    if 'from ent."sales_contracts"' in sql:
        return ['sales_order', 'asset'], []
    if sql.startswith('select distinct'):
        return ['k'], [('HYD-01',), ('P-CLR-CORE',)]
    return None


def ts_handler(sql, params):
    from datetime import datetime, timezone
    t = datetime(2026, 10, 8, 10, tzinfo=timezone.utc)
    if 'from pg_class c' in sql:
        return [None] * 9, catalog_rows(TS_TABLES)
    if 'current_setting' in sql:
        return ['u', 'ro', 'db', 'now'], [('hyd_timeseries_reader', 'on', 'hyd', t)]
    if 'FROM public.tag_1s' in sql and "'TS1', 'LoadSP'" in sql:
        return ['name', 'value', 'time'], [('LoadSP', 90.0, t), ('TS1', 58.4, t), ('TS1', 58.1, t)]
    if sql.startswith('select * from "public"."tag_1s"'):
        return ['time', 'asset', 'name', 'value'], [(t, 'HYD-01', 'TS1', 58.4)]
    if "name = 'VS1'" in sql:
        return ['bucket', 'vs1_avg', 'vs1_max'], [(t, 0.61, 0.7), (t, 0.92, 1.1)]
    if 'FILTER' in sql:
        return ['minutes_over', 'peak', 'samples'], [(41, 59.3, 3600)]
    if 'distinct on (name)' in sql:
        return ['name', 'value', 'time', 'age'], ([('TS1', 58.4, t, 2.0), ('XYZ', 1.0, t, 2.0)] if params['asset'] == 'HYD-01' else [])
    if sql.startswith('select distinct'):
        return ['k'], [('HYD-01',), ('TS1',)]
    return None


NODES = [dict(klass='Asset', id='asset:hyd-01', name='HYD-01', code='HYD-01'), dict(klass='Sensor', id='sen:ts1', name='유온 센서', tag='TS1', unit='℃'),
         dict(klass='Part', id='part:cooler-core', name='쿨러 코어', partNo='P-CLR-CORE'), dict(klass='Part', id='part:pump-seal', name='씰', partNo='P-PMP-SEAL')]
INPUTS = [dict(id='in:ts1', name='유온', variable='ts1', source='sen:ts1', sourceKind='Sensor', tag='TS1'),
          dict(id='in:order-due', name='긴급 오더 남은 시간', variable='order_due_h', source='sys:mes', sourceKind='System'),
          dict(id='in:pattern', name='경보 패턴', variable='pattern', source='sys:cep', sourceKind='System'),
          dict(id='in:db:due', name='납기 일시 (지금부터 h)', variable='db_due', datasource=ENT, schema='ent', table='production_orders',
               column='due_at', assetColumn='asset', derive='hours_from_now', source='sys:mes', sourceKind='System'),
          dict(id='in:db:gone', name='사라진 열', variable='db_gone', datasource=ENT, schema='ent', table='production_orders',
               column='removed_col', assetColumn='asset', source='sys:mes', sourceKind='System')]


def graph(cypher, **params):
    if 'AnomalyPattern' in cypher:
        return [dict(pattern='쿨러 성능 저하', operator='>', value=55, unit='℃')]
    if 'SOURCED_FROM' in cypher:
        return INPUTS
    return NODES


def make(ent=ent_handler, ts=ts_handler, g=graph):
    log = {ENT: [], TS: []}
    calls = {ENT: 0, TS: 0}

    def connector(source, handler):
        def connect():
            calls[source] += 1
            if isinstance(handler, Exception):
                raise handler
            return FakeConn(handler, log[source])
        return connect
    return Fabric(connect={ENT: connector(ENT, ent), TS: connector(TS, ts)}, graph=g), log, calls


# ------------------------------------------------------------------ 교차 조회: 값과 출처
def test_cross_query_merges_values_with_their_source_and_runs_read_only():
    f, log, _ = make()
    out = f.query('HYD-01', 'due-vs-temp', limit=10)
    got = {a['label']: a for a in out['answer']}
    assert got['가장 이른 납기 오더']['value'] == 'MO-1' and got['가장 이른 납기 오더']['source'] == ENT
    assert got['납기까지']['value'] == 6 and got['납기까지']['unit'] == 'h' and got['납기까지']['column'] == 'due_in_h'
    assert got['지연 시 시간당 보상']['value'] == 120 and got['지연 시 시간당 보상']['part'] == 'contract'
    assert got['지금 유온']['value'] == 58.4 and got['지금 유온']['source'] == TS and got['지금 유온']['at'].startswith('2026-10-08T10')
    assert got['펌프 부하 설정']['value'] == 90.0 and out['partial'] is False and out['read_only'] is True
    for source in (ENT, TS):
        statements = [s for s, _ in log[source]]
        assert statements[0] == 'set transaction read only' and "statement_timeout" in statements[1]   # read-only before any read
        assert log[source][-1][0] == 'ROLLBACK'
    run = [s for s, p in log[ENT] if 'production_orders' in s][0]
    assert 'LIMIT 10' in run and dict(next(p for s, p in log[ENT] if 'production_orders' in s)) == {'asset': 'HYD-01'}
    part = next(p for p in out['parts'] if p['id'] == 'orders')
    assert part['statement'] == run and part['source_label'] == '업무 DB' and part['row_count'] == 1


def test_threshold_comes_from_the_knowledge_graph_not_code():
    f, log, _ = make()
    out = f.query('HYD-01', 'hot-lots-vs-ts1')
    ts = next(p for p in out['parts'] if p['id'] == 'ts1')
    assert ts['params'] == {'asset': 'HYD-01', 'ts1_limit': 55} and '55' in out['notes'][0] and '쿨러 성능 저하' in out['notes'][0]
    assert next(a for a in out['answer'] if a['part'] == 'ts1' and a['column'] == 'minutes_over')['value'] == 41
    no_limit, _, calls = make(g=lambda cypher, **p: [] if 'AnomalyPattern' in cypher else graph(cypher, **p))
    with pytest.raises(SourceUnavailable, match='임계값'):
        no_limit.query('HYD-01', 'hot-lots-vs-ts1')
    assert calls == {ENT: 0, TS: 0}


def test_asset_view_merges_both_sources_and_names_unclaimed_tags():
    f, _, _ = make()
    out = f.query('HYD-01', 'asset')
    rows = out['answer']
    asset_name = next(r for r in rows if r['klass'] == 'Asset' and r['field'] == 'name')
    assert asset_name['value'] == '유압 파워팩 1호기' and asset_name['from'] == 'ent.assets.name' and asset_name['where'] == "code = 'HYD-01'"
    ts1 = next(r for r in rows if r['field'] == 'TS1')
    assert ts1['klass'] == 'Sensor' and ts1['label'] == '유온 센서' and ts1['source'] == TS and ts1['inputs'] == ['유온'] and ts1['age_s'] == 2.0
    other = next(r for r in rows if r['field'] == 'XYZ')
    assert other['klass'] is None and other['label'] == '온톨로지에 연결된 클래스 없음'
    gone = next(r for r in rows if r['field'] == 'db_gone')
    assert gone['state'] == 'MISSING' and gone['value'] is None
    assert [p['id'] for p in out['parts'] if p['source'] == ENT] == ['ent:production_orders']    # fk → assets.code, empty tables omitted
    with pytest.raises(ValueError, match='어디에도|에도'):
        f.query('HYD-99', 'asset')


# ------------------------------------------------------------------ 쓰기 거부
@pytest.mark.parametrize('sql', [
    {ENT: 'delete from ent.assets'},
    {ENT: "update ent.production_orders set due_at = now()"},
    {ENT: 'select 1; drop table ent.assets'},
    {ENT: 'with x as (delete from ent.assets returning *) select * from x'},
    {ENT: 'select * from public.todolist'},                 # another schema of the same database
    {TS: 'insert into tag_1s values (now(), \'HYD-01\', \'TS1\', 1)'},
    {TS: 'select * from alerts'},                           # time-series table outside the reader's three
    {TS: 'select pg_sleep(10)'},
])
def test_writes_and_out_of_scope_sql_are_refused_before_any_connection(sql):
    f, log, calls = make()
    with pytest.raises(SqlRejected):
        f.query('HYD-01', 'sql', sql=sql)
    assert calls == {ENT: 0, TS: 0} and log == {ENT: [], TS: []}


def test_free_select_is_guarded_and_limited_per_source():
    f, log, _ = make()
    out = f.query('HYD-01', 'sql', limit=3, sql={ENT: 'select * from production_orders where asset = %(asset)s'})
    assert out['parts'][0]['statement'].endswith('LIMIT 3') and 'ent.production_orders' in out['parts'][0]['statement']
    assert out['parts'][0]['params'] == {'asset': 'HYD-01'}
    with pytest.raises(ValueError):
        f.query('HYD-01', 'sql', sql={'other-db': 'select 1'})
    with pytest.raises(ValueError):
        f.query('HYD-01', 'asset', limit=500)


def test_sample_only_reads_a_table_from_the_live_catalog():
    f, log, _ = make()
    with pytest.raises(ValueError, match='읽을 수 있는 표가 아닙니다'):
        f.sample(ENT, 'assets; drop table ent.assets')
    sent = [entry[0] for entry in log[ENT]]
    assert not [s for s in sent if 'assets; drop' in s]
    assert [s for s in sent if s.startswith('select')] == [fb.CATALOG_SQL]       # only the catalog was read
    out = f.sample(TS, 'tag_1s', 3)
    assert out['statement'] == 'select * from "public"."tag_1s" where "time" > now() - interval \'1 day\' order by "time" desc limit 3'
    with pytest.raises(ValueError):
        f.sample(TS, 'tag_1s', 999)


# ------------------------------------------------------------------ 연결 실패 사유
@pytest.mark.parametrize('exc,expect', [
    (psycopg.OperationalError('connection to server at "127.0.0.1", port 1 failed: Connection refused'), 'DB 서버에 연결할 수 없습니다'),
    (psycopg.OperationalError('FATAL:  password authentication failed for user "hyd_enterprise_reader"'), '인증에 실패'),
    (psycopg.OperationalError('FATAL:  role "hyd_timeseries_reader" does not exist'), '읽기 전용 계정이 DB에 없습니다'),
    (psycopg.OperationalError('could not translate host name "timescaledb" to address: Name or service not known'), '호스트 이름'),
    (psycopg.OperationalError('connection timeout expired'), '시간이 초과'),
    (RuntimeError('enterprise requires the dedicated unprivileged reader role'), '전용 읽기 계정이 아닌 계정'),
    (psycopg.errors.ReadOnlySqlTransaction('cannot execute INSERT in a read-only transaction'), '쓰기를 거부'),
])
def test_failure_reason_is_a_sentence_a_person_can_act_on(exc, expect):
    assert expect in fb.failure_reason(exc)


def test_missing_connection_setting_is_named():
    connect = fb.env_connectors({})
    with pytest.raises(SourceUnavailable, match='ENTERPRISE_READ_DSN'):
        connect[ENT]()
    with pytest.raises(SourceUnavailable, match='TSDB_READ_DSN 또는 TSDB_DSN'):
        connect[TS]()


def test_one_source_down_is_partial_with_its_reason_both_down_is_an_error():
    down = psycopg.OperationalError('connection to server at "x", port 5432 failed: Connection refused')
    f, _, _ = make(ts=down)
    out = f.query('HYD-01', 'due-vs-temp')
    assert out['partial'] is True and out['sources'][TS]['ok'] is False and 'DB 서버에 연결할 수 없습니다' in out['sources'][TS]['reason']
    ts1 = next(a for a in out['answer'] if a['label'] == '지금 유온')
    assert ts1['value'] is None and ts1['state'] == 'SOURCE_DOWN' and ts1['reason']
    assert next(a for a in out['answer'] if a['label'] == '납기까지')['value'] == 6           # the other source still answers
    status = {s['id']: s for s in f.sources()}
    assert status[ENT]['ok'] and status[ENT]['read_only'] and not status[TS]['ok'] and 'DB 서버' in status[TS]['reason']
    both, _, _ = make(ent=down, ts=RuntimeError('timeseries requires the dedicated unprivileged reader role'))
    with pytest.raises(FabricUnavailable) as e:
        both.query('HYD-01', 'due-vs-temp')
    assert '업무 DB: DB 서버에 연결할 수 없습니다' in str(e.value) and '시계열 DB: 전용 읽기 계정이 아닌 계정' in str(e.value)
    with pytest.raises(FabricUnavailable):
        both.query('HYD-01', 'asset')


# ------------------------------------------------------------------ 클래스 ↔ 표·열
def test_links_check_class_keys_and_input_sources_against_the_live_catalog():
    f, _, _ = make()
    out = f.links()
    part = next(c for c in out['classes'] if c['klass'] == 'Part')
    assert part['state'] == 'OK' and [m['key'] for m in part['matched']] == ['P-CLR-CORE'] and [m['key'] for m in part['unmatched']] == ['P-PMP-SEAL']
    sensor = next(c for c in out['classes'] if c['klass'] == 'Sensor')
    assert sensor['table'] == 'tag_1s' and sensor['column'] == 'name' and sensor['window'] == '최근 10분 관측'
    states = {i['id']: (i['binding'], i['state']) for i in out['inputs']}
    assert states == {'in:ts1': ('sensor', 'OK'), 'in:order-due': ('system', 'UNBOUND'), 'in:pattern': ('outside', 'OUTSIDE'),
                      'in:db:due': ('physical', 'OK'), 'in:db:gone': ('physical', 'MISSING')}
    down, _, _ = make(ent=psycopg.OperationalError('Connection refused'))
    out = down.links()
    assert next(c for c in out['classes'] if c['klass'] == 'Part')['state'] == 'SOURCE_DOWN'
    assert next(i for i in out['inputs'] if i['id'] == 'in:db:due')['state'] == 'SOURCE_DOWN'
    nograph = Fabric(connect=make()[0]._connect, graph=None).links()
    assert nograph['graph']['ok'] is False and '지식 그래프' in nograph['graph']['reason']


# ------------------------------------------------------------------ 포털 API · MCP 도구
def client(fabric):
    from procsvc import fabric_api
    app = FastAPI()
    fabric_api.register(app, driver_factory=lambda: None, fabric_factory=lambda: fabric)
    return TestClient(app)


def test_process_api_status_codes():
    f, _, _ = make()
    c = client(f)
    ok = c.post('/api/fabric/query', json={'asset': 'HYD-01', 'query': 'due-vs-temp'})
    assert ok.status_code == 200 and ok.json()['answer'][0]['value'] == 'MO-1'
    bad = c.post('/api/fabric/query', json={'asset': 'HYD-01', 'query': 'sql', 'sql': {ENT: 'delete from ent.assets'}})
    assert bad.status_code == 400 and '읽기 전용 SELECT만' in bad.json()['detail']
    assert c.get('/api/fabric/sources/other/tables').status_code == 404
    assert [q['id'] for q in c.get('/api/fabric/queries').json()] == list(fb.CROSS_QUERIES)
    down = psycopg.OperationalError('Connection refused')
    both, _, _ = make(ent=down, ts=down)
    r = client(both).post('/api/fabric/query', json={'asset': 'HYD-01', 'query': 'asset'})
    assert r.status_code == 503 and 'DB 서버에 연결할 수 없습니다' in r.json()['detail']
    r = client(both).get(f'/api/fabric/sources/{ENT}/tables')
    assert r.status_code == 503 and 'DB 서버에 연결할 수 없습니다' in r.json()['detail']
    assert client(both).get('/api/fabric/sources').status_code == 200          # status itself is not an error


def test_dmn_mcp_fabric_query_envelope():
    from dmn_mcp import tools as dmn
    f, _, _ = make()
    t = dmn.DmnTools(kg=object(), tsdb=object(), fabric=f)
    ok = dmn.enveloped(lambda: t.fabric_query('HYD-01', 'maintenance-vs-vibration'))()
    assert ok['result'] == 'ok' and ok['document']['query'] == 'maintenance-vs-vibration'
    picked = {a['label']: a['value'] for a in ok['document']['answer']}
    assert picked['최근 작업지시'] == 'WO-9' and picked['진동 5분 평균 (처음 구간)'] == 0.61 and picked['진동 5분 평균 (마지막 구간)'] == 0.92
    refused = dmn.enveloped(lambda: t.fabric_query('HYD-01', 'sql', 50, {ENT: 'delete from ent.assets'}))()
    assert refused['result'] == 'error' and refused['error_kind'] == 'INVALID'
    down = psycopg.OperationalError('Connection refused')
    both, _, _ = make(ent=down, ts=down)
    failed = dmn.enveloped(lambda: dmn.DmnTools(kg=object(), tsdb=object(), fabric=both).fabric_query('HYD-01'))()
    assert failed['result'] == 'error' and failed['error_kind'] == 'UNKNOWN' and 'DB 서버에 연결할 수 없습니다' in failed['message']
