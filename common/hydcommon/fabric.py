"""A11 데이터 패브릭 미니 — 업무 DB(Supabase `ent`)와 시계열 DB(TimescaleDB)를 읽기 전용으로 한 질문에 묶는다.

HANDOFF §2 "데이터 패브릭은 구현하지 않고 후반 설명만"(회의 L63~67·L447)을 사용자 확정 TODO A11(2026-10-08 밤, "todo 다
구현")에 따라 **가볍게** 구현한 것이다. 새 서비스(MindsDB 등) 없이 이미 있는 두 전용 읽기 계정(hyd_enterprise_reader ·
hyd_timeseries_reader)과 같은 SQL 가드(hydcommon.sql_read)를 쓴다. 참고: ontology-studio의 데이터소스 기반 가상 클래스
(openspec/changes/add-datasource-backed-virtual-classes/design.md — 인스턴스 0건 저장, 질의 시점에 원천을 읽음, 행 제한은 호출자가
아니라 바인더가 붙임)와 ontologic data-fabric(MindsDB 카탈로그). HYD는 원천이 둘뿐이라 카탈로그는 각 DB의 시스템 카탈로그를
직접 읽는다.

  1 원천(SOURCES)     : 연결 상태 · 표 · 열 · 샘플. 실패는 사람이 읽을 사유(failure_reason)로.
  2 클래스 ↔ 표·열     : 온톨로지 클래스의 식별 키(CLASS_KEYS)와 InputData의 원천 링크(SOURCED_FROM · DDL 적재로 생긴 물리 바인딩)를
                        살아 있는 카탈로그에 대어 OK · MISSING을 판정한다. 이름으로 의미를 추측하지 않는다.
  3 묶어 보기         : 설비 하나 → 두 원천의 연결된 값을 출처(원천 · 표 · 열 · 조건 · 실행 SQL · 관측 시각)와 함께 합침,
                        정의된 교차 조회(CROSS_QUERIES), 에이전트가 쓴 SELECT(원천별 가드). 모두 읽기 전용 트랜잭션 · 5초 · 행 제한.

연결은 주입한다(connect={source: callable}, graph=callable(cypher, **params)). process(포털 API)와 dmn-mcp(fabric_query 도구)가
같은 코드를 쓴다.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import date, datetime, time, timezone
from decimal import Decimal
from uuid import UUID

import psycopg

from .enterprise import reader_connection as enterprise_reader
from .sql_read import MAX_ROWS, READ_FUNCTIONS, SqlRejected, guard

ENT, TS = 'hyd-enterprise', 'hyd-timeseries'
TS_TABLES = ('tag_1s', 'feat_1s', 'tag_1m')
SOURCES = {
    ENT: dict(id=ENT, label='업무 DB', engine='Supabase PostgreSQL', schema='ent', role='hyd_enterprise_reader',
              env=('ENTERPRISE_READ_DSN',), systems=('sys:mes', 'sys:erp', 'sys:cmms', 'sys:qms', 'sys:scm'),
              about='ERP · MES · CMMS · QMS · SCM · EMS 업무 기록 (주문 · 계약 · 정비 · 품질 · 구매)'),
    TS: dict(id=TS, label='시계열 DB', engine='TimescaleDB', schema='public', role='hyd_timeseries_reader',
             env=('TSDB_READ_DSN', 'TSDB_DSN'), systems=('sys:historian',), tables=TS_TABLES,
             about='센서 · 설정값 1초 기록(tag_1s), 파형 특징(feat_1s), 1분 집계(tag_1m)'),
}
SAMPLE_MAX = 20
RECENT = "time > now() - interval '10 minutes'"

# 온톨로지 클래스의 식별 키 ↔ 원천 열. 값(정답)이 아니라 구조(어느 열이 같은 것을 가리키나)다.
CLASS_KEYS = (
    dict(klass='Asset', label='설비', key='code', key_label='설비 코드', source=ENT, table='assets', column='code'),
    dict(klass='Asset', label='설비', key='code', key_label='설비 코드', source=TS, table='tag_1s', column='asset', recent=True),
    dict(klass='Sensor', label='센서', key='tag', key_label='태그', source=TS, table='tag_1s', column='name', recent=True),
    dict(klass='Actuator', label='구동기 설정값', key='resource', key_label='설정값 태그', source=TS, table='tag_1s', column='name', recent=True),
    dict(klass='Part', label='부품', key='partNo', key_label='부품 번호', source=ENT, table='parts', column='part_no'),
    dict(klass='Supplier', label='공급사', key='id', key_label='공급사 식별자', source=ENT, table='suppliers', column='id'),
)
CLASS_Q = """MATCH (n) WHERE n:Asset OR n:Sensor OR n:Actuator OR n:Part OR n:Supplier
RETURN [l IN labels(n) WHERE l IN ['Asset','Sensor','Actuator','Part','Supplier']][0] AS klass, n.id AS id, n.name AS name,
       n.code AS code, n.tag AS tag, n.unit AS unit, n.resource AS resource, n.partNo AS partNo
ORDER BY klass, id"""
# it/neo4j/templates/t3_inputs.cypher 와 같은 열(process 이미지에는 템플릿 폴더가 없어 여기 둔다)
INPUTS_Q = """MATCH (i:InputData)
OPTIONAL MATCH (i)-[:SOURCED_FROM]->(src)
RETURN i.id AS id, i.name AS name, i.variable AS variable, i.typeRef AS typeRef,
       i.datasource AS datasource, i.schema AS schema, i.table AS table, i.column AS column, i.assetColumn AS assetColumn,
       i.sqlType AS sqlType, i.derive AS derive, i.sourceState AS sourceState,
       src.id AS source, coalesce(src.name, src.id) AS sourceName, labels(src)[0] AS sourceKind, src.tag AS tag
ORDER BY i.id"""
LIMIT_Q = """MATCH (p:AnomalyPattern)-[t:TESTS]->(i:InputData {variable: $variable}) WHERE t.operator IN ['>', '>=']
RETURN p.name AS pattern, t.operator AS operator, t.value AS value, t.unit AS unit ORDER BY p.id LIMIT 1"""

# 정의된 교차 조회: 한 질문 = 원천별 SELECT 몇 개(모두 가드 통과) + 그 결과에서 고른 답. 답은 계산하지 않고 원천 값을 그대로 옮긴다.
CROSS_QUERIES = {
    'due-vs-temp': dict(
        title='납기가 걸린 오더와 지금 설비 상태',
        question='이 설비가 돌리는 생산오더의 납기는 얼마나 남았고, 지금 유온과 펌프 부하는 어떤가?',
        parts=[dict(id='orders', source=ENT, purpose='MES 생산오더 — 납기 일시, 남은 시간, 시간당 생산 가치',
                    sql="select order_id, customer, due_at, round(extract(epoch from (due_at - now())) / 3600, 2) as due_in_h, "
                        "hour_value, remaining_qty, status from ent.production_orders where asset = %(asset)s order by due_at"),
               dict(id='contract', source=ENT, purpose='ERP 계약 — 납기 지연 시 시간당 보상과 고객 등급',
                    sql="select sales_order, customer_tier, penalty_per_h from ent.sales_contracts where asset = %(asset)s"),
               dict(id='now', source=TS, purpose='센서 최신값 — 유온(TS1) · 펌프 부하 설정(LoadSP), 최근 10분',
                    sql="select name, value, time from tag_1s where asset = %(asset)s and name in ('TS1', 'LoadSP') "
                        "and " + RECENT + " order by time desc limit 20")],
        answer=[('가장 이른 납기 오더', 'orders', ('first', 'order_id'), None),
                ('납기까지', 'orders', ('first', 'due_in_h'), 'h'),
                ('시간당 생산 가치', 'orders', ('first', 'hour_value'), '만원'),
                ('지연 시 시간당 보상', 'contract', ('first', 'penalty_per_h'), '만원'),
                ('지금 유온', 'now', ('latest', 'TS1'), '℃'),
                ('펌프 부하 설정', 'now', ('latest', 'LoadSP'), '%')]),
    'hot-lots-vs-ts1': dict(
        title='고온 구간 로트와 실제 유온 기록',
        question='품질 시스템이 고온 구간으로 기록한 로트와, 시계열에 남은 최근 60분 유온이 기준을 넘은 시간은 어떤가?',
        params={'ts1_limit': 'ts1'},
        parts=[dict(id='lots', source=ENT, purpose='QMS 고온 구간 로트 — 기록된 고온 시간(분), 출하 대기 로트 · 수량 · 클레임 위험',
                    sql="select hot_min, auto_lot, auto_qty, auto_claim, gen_lot, gen_qty from ent.quality_profiles where asset = %(asset)s"),
               dict(id='ts1', source=TS, purpose='TS1이 기준(지식 그래프의 이상 패턴 임계값)을 넘은 분 수 · 최고값, 최근 60분',
                    sql="select count(distinct time_bucket('1 minute', time)) filter (where value > %(ts1_limit)s) as minutes_over, "
                        "max(value) as peak, count(*) as samples from tag_1s where asset = %(asset)s and name = 'TS1' "
                        "and time > now() - interval '60 minutes'")],
        answer=[('QMS 기록 고온 시간', 'lots', ('first', 'hot_min'), '분'),
                ('출하 대기 로트', 'lots', ('first', 'auto_lot'), None),
                ('출하 대기 수량', 'lots', ('first', 'auto_qty'), '개'),
                ('클레임 위험', 'lots', ('first', 'auto_claim'), '만원'),
                ('시계열: 기준 초과 시간 (최근 60분)', 'ts1', ('first', 'minutes_over'), '분'),
                ('시계열: 최고 유온 (최근 60분)', 'ts1', ('first', 'peak'), '℃')]),
    'maintenance-vs-vibration': dict(
        title='정비 이력과 최근 진동 추세',
        question='이 설비의 최근 정비 작업은 언제 무엇이었고, 최근 30분 팬 진동은 오르고 있는가?',
        parts=[dict(id='history', source=ENT, purpose='CMMS 과거 작업지시 — 작업 번호 · 내용 · 수행 일시(최근 5건)',
                    sql="select wo, task, performed_at from ent.maintenance_history where asset = %(asset)s order by performed_at desc limit 5"),
               dict(id='vs1', source=TS, purpose='팬 진동(VS1) 5분 평균 · 최고, 최근 30분',
                    sql="select time_bucket('5 minutes', time) as bucket, round(avg(value)::numeric, 3) as vs1_avg, "
                        "round(max(value)::numeric, 3) as vs1_max from tag_1s where asset = %(asset)s and name = 'VS1' "
                        "and time > now() - interval '30 minutes' group by 1 order by 1")],
        answer=[('최근 작업지시', 'history', ('first', 'wo'), None),
                ('작업 내용', 'history', ('first', 'task'), None),
                ('수행 일시', 'history', ('first', 'performed_at'), None),
                ('진동 5분 평균 (처음 구간)', 'vs1', ('first', 'vs1_avg'), 'mm/s'),
                ('진동 5분 평균 (마지막 구간)', 'vs1', ('last', 'vs1_avg'), 'mm/s')]),
}


class SourceUnavailable(RuntimeError):
    """A source cannot be read; `reason` is the sentence a person reads."""
    def __init__(self, reason: str, detail: str = ''):
        super().__init__(reason)
        self.reason, self.detail = reason, detail


class FabricUnavailable(RuntimeError):
    """Every source a request needed failed: no partial answer exists (never an empty success)."""


def first_line(exc: BaseException) -> str:
    text = str(exc).strip()
    return (text.splitlines()[0] if text else type(exc).__name__)[:200]


def failure_reason(exc: BaseException) -> str:
    """Connection/read failure → a Korean sentence naming what to check. Raw text stays in `detail`."""
    if isinstance(exc, SourceUnavailable):
        return exc.reason
    low = str(exc).lower()
    if 'dedicated unprivileged reader role' in low:
        return '전용 읽기 계정이 아닌 계정으로 연결돼 거부했습니다 (쓰기 권한이 있는 계정은 쓰지 않습니다)'
    if 'password authentication failed' in low:
        return '읽기 전용 계정 인증에 실패했습니다 (계정 · 비밀번호 확인)'
    if 'role' in low and 'does not exist' in low:
        return '읽기 전용 계정이 DB에 없습니다 (읽기 계정을 만드는 초기화 SQL 적용 확인)'
    if 'database' in low and 'does not exist' in low:
        return '데이터베이스 이름이 없습니다 (연결 주소의 DB 이름 확인)'
    if 'translate host name' in low or 'name or service not known' in low or 'nodename nor servname' in low:
        return 'DB 주소(호스트 이름)를 찾을 수 없습니다'
    if 'timeout' in low or 'timed out' in low or 'canceling statement' in low:
        return '연결 또는 조회 시간이 초과됐습니다 (5초)'
    if 'connection refused' in low or 'could not connect' in low or 'connection to server' in low or 'server closed' in low:
        return 'DB 서버에 연결할 수 없습니다 (서버가 켜져 있는지 · 주소 · 포트 확인)'
    if 'permission denied' in low:
        return '읽기 권한이 없는 표입니다'
    if 'read-only transaction' in low:
        return '읽기 전용 연결이라 쓰기를 거부했습니다'
    return 'DB 오류: ' + first_line(exc)


def jsonable(value):
    """DB scalar → JSON value. Decimal stays exact when integral, else a float (display); times as ISO text."""
    if value is None or isinstance(value, (bool, int, str, float)):
        return value
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    return str(value)


def ident(name: str) -> str:
    if not isinstance(name, str) or not name or '\x00' in name:
        raise ValueError('잘못된 SQL 식별자')
    return '"' + name.replace('"', '""') + '"'


def guard_for(source: str, sql: str, limit: int) -> str:
    """The same read-only SELECT contract per source: ent tables only / the three time-series tables only."""
    if source == ENT:
        return guard(sql, limit, schema='ent')
    if source == TS:
        return guard(sql, limit, schema='public', tables=frozenset(TS_TABLES), functions=READ_FUNCTIONS | {'TIME_BUCKET'})
    raise ValueError(f'등록되지 않은 원천: {source}')


def timeseries_reader(dsn: str):
    """The time-series twin of hydcommon.enterprise.reader_connection: refuse anything but the dedicated reader."""
    conn = psycopg.connect(dsn, autocommit=False, connect_timeout=5)
    try:
        row = conn.execute('select current_user, rolsuper, rolcreaterole, rolcreatedb, rolbypassrls '
                           'from pg_roles where rolname=current_user').fetchone()
        if row != ('hyd_timeseries_reader', False, False, False, False):
            raise RuntimeError('timeseries requires the dedicated unprivileged reader role')
        conn.rollback()
        return conn
    except Exception:
        conn.close()
        raise


def env_connectors(env=None) -> dict:
    env = os.environ if env is None else env

    def make(source):
        names = SOURCES[source]['env']
        def connect():
            dsn = next((env.get(n) for n in names if env.get(n)), None)
            if not dsn:
                raise SourceUnavailable(f"연결 설정이 없습니다 ({' 또는 '.join(names)} 환경변수)")
            return enterprise_reader(dsn) if source == ENT else timeseries_reader(dsn)
        return connect
    return {s: make(s) for s in SOURCES}


CATALOG_SQL = """select c.relname, obj_description(c.oid, 'pg_class'), c.relkind, a.attname, format_type(a.atttypid, a.atttypmod),
  not a.attnotnull, col_description(c.oid, a.attnum),
  exists(select 1 from pg_constraint k where k.conrelid=c.oid and k.contype='p' and a.attnum = any(k.conkey)),
  (select fc.relname || '.' || fa.attname from pg_constraint k join pg_class fc on fc.oid=k.confrelid
     join pg_attribute fa on fa.attrelid=k.confrelid and fa.attnum=k.confkey[1]
   where k.conrelid=c.oid and k.contype='f' and array_length(k.conkey, 1)=1 and k.conkey[1]=a.attnum limit 1)
from pg_class c join pg_namespace n on n.oid=c.relnamespace
  join pg_attribute a on a.attrelid=c.oid and a.attnum>0 and not a.attisdropped
where n.nspname = %(schema)s and c.relkind in ('r','p','v','m') and has_table_privilege(c.oid, 'SELECT')
  and (%(tables)s::text[] is null or c.relname = any(%(tables)s::text[]))
order by c.relname, a.attnum"""


class Fabric:
    def __init__(self, connect: dict | None = None, graph=None):
        self._connect = connect if connect is not None else env_connectors()
        self._graph = graph

    # ------------------------------------------------------------------ connections
    @contextmanager
    def _session(self, source: str):
        if source not in SOURCES:
            raise ValueError(f'등록되지 않은 원천: {source}')
        conn = self._connect[source]()
        try:
            with conn.cursor() as cur:
                cur.execute('set transaction read only')
                cur.execute("set local statement_timeout = '5000ms'")
                cur.execute("set local lock_timeout = '1000ms'")
                yield cur
        finally:
            try:
                conn.rollback()
            finally:
                conn.close()

    @staticmethod
    def _fail(exc) -> dict:
        return {'ok': False, 'reason': failure_reason(exc), 'detail': first_line(exc)}

    def _tables(self, cur, source: str) -> list[dict]:
        s = SOURCES[source]
        cur.execute(CATALOG_SQL, {'schema': s['schema'], 'tables': list(s['tables']) if s.get('tables') else None})
        tables: dict[str, dict] = {}
        for rel, comment, kind, col, typ, nullable, ccomment, pk, fk in cur.fetchall():
            t = tables.setdefault(rel, {'name': rel, 'comment': comment, 'kind': {'r': '표', 'p': '표', 'v': '뷰', 'm': '집계 뷰'}.get(kind, kind),
                                        'columns': []})
            t['columns'].append({'name': col, 'type': typ, 'nullable': nullable, 'comment': ccomment, 'pk': pk, 'fk': fk})
        return list(tables.values())

    def _graph_rows(self, cypher: str, **params) -> list[dict]:
        if self._graph is None:
            raise SourceUnavailable('지식 그래프 연결이 설정되지 않았습니다')
        return self._graph(cypher, **params)

    # ------------------------------------------------------------------ 1 원천
    def sources(self) -> list[dict]:
        out = []
        for sid, s in SOURCES.items():
            row = {k: s[k] for k in ('id', 'label', 'engine', 'schema', 'role', 'about')}
            try:
                with self._session(sid) as cur:
                    cur.execute("select current_user, current_setting('transaction_read_only'), current_database(), now()")
                    user, ro, db, now = cur.fetchone()
                    tables = self._tables(cur, sid)
                row.update(ok=True, user=user, read_only=ro == 'on', database=db, checked_at=jsonable(now),
                           tables=[{'name': t['name'], 'comment': t['comment'], 'kind': t['kind'], 'columns': len(t['columns'])} for t in tables])
            except (psycopg.Error, RuntimeError, OSError) as e:
                row.update(self._fail(e))
            out.append(row)
        return out

    def tables(self, source: str) -> dict:
        with self._session(source) as cur:
            return {'source': source, 'label': SOURCES[source]['label'], 'schema': SOURCES[source]['schema'],
                    'tables': self._tables(cur, source)}

    def sample(self, source: str, table: str, limit: int = 5) -> dict:
        """Newest rows of one catalog table. The table name must be in the live reader-visible catalog (no free text reaches SQL)."""
        n = _limit(limit, SAMPLE_MAX)
        with self._session(source) as cur:
            known = {t['name']: t for t in self._tables(cur, source)}
            if table not in known:
                raise ValueError(f"{SOURCES[source]['label']}에서 읽을 수 있는 표가 아닙니다: {table}")
            cols = [c['name'] for c in known[table]['columns']]
            order = next((c for c in ('time', 'bucket', 'created_at', 't', 'performed_at') if c in cols), None)
            target = ident(SOURCES[source]['schema']) + '.' + ident(table)
            where = f" where {ident(order)} > now() - interval '1 day'" if source == TS and order else ''
            statement = f"select * from {target}{where}{(' order by ' + ident(order) + ' desc') if order else ''} limit {n}"
            cur.execute(statement)
            columns = [d.name for d in cur.description]
            rows = [[jsonable(v) for v in r] for r in cur.fetchall()]
        return {'source': source, 'label': SOURCES[source]['label'], 'table': table, 'statement': statement,
                'columns': columns, 'rows': rows, 'row_count': len(rows), 'row_limit': n}

    # ------------------------------------------------------------------ 2 클래스 ↔ 표·열
    def links(self) -> dict:
        graph = {'ok': True}
        try:
            nodes, inputs = self._graph_rows(CLASS_Q), self._graph_rows(INPUTS_Q)
        except Exception as e:  # noqa: BLE001 — neo4j driver errors have no common base we import here
            graph, nodes, inputs = self._fail(e), [], []
        live, keys_found = {}, {}
        for sid in SOURCES:
            try:
                with self._session(sid) as cur:
                    tables = {t['name']: {c['name']: c for c in t['columns']} for t in self._tables(cur, sid)}
                    for b in (b for b in CLASS_KEYS if b['source'] == sid and b['table'] in tables and b['column'] in tables[b['table']]):
                        wanted = sorted({n[b['key']] for n in nodes if n['klass'] == b['klass'] and n.get(b['key'])})
                        if wanted:
                            recent = f' and {RECENT}' if b.get('recent') else ''
                            cur.execute(f"select distinct {ident(b['column'])} from {ident(SOURCES[sid]['schema'])}.{ident(b['table'])} "
                                        f"where {ident(b['column'])} = any(%(keys)s){recent}", {'keys': wanted})
                            keys_found[(b['klass'], sid, b['table'], b['column'])] = {r[0] for r in cur.fetchall()}
                live[sid] = {'ok': True, 'tables': tables}
            except (psycopg.Error, RuntimeError, OSError) as e:
                live[sid] = self._fail(e)
        classes = []
        for b in CLASS_KEYS:
            src = live[b['source']]
            wanted = [n for n in nodes if n['klass'] == b['klass'] and n.get(b['key'])]
            row = {'klass': b['klass'], 'label': b['label'], 'key': b['key'], 'key_label': b['key_label'], 'source': b['source'],
                   'source_label': SOURCES[b['source']]['label'], 'table': b['table'], 'column': b['column'],
                   'window': '최근 10분 관측' if b.get('recent') else None, 'instances': len(wanted)}
            if not src['ok']:
                row.update(state='SOURCE_DOWN', reason=src['reason'])
            elif b['table'] not in src['tables'] or b['column'] not in src['tables'][b['table']]:
                row.update(state='MISSING', reason='원천에 이 표 · 열이 없습니다')
            else:
                found = keys_found.get((b['klass'], b['source'], b['table'], b['column']), set())
                row.update(state='OK', matched=[{'id': n['id'], 'name': n.get('name'), 'key': n[b['key']]} for n in wanted if n[b['key']] in found],
                           unmatched=[{'id': n['id'], 'name': n.get('name'), 'key': n[b['key']]} for n in wanted if n[b['key']] not in found])
            classes.append(row)
        return {'graph': graph, 'sources': {s: ({'ok': True} if v['ok'] else {k: v[k] for k in ('ok', 'reason', 'detail')}) for s, v in live.items()},
                'classes': classes, 'inputs': [self._input_link(i, live) for i in inputs]}

    @staticmethod
    def _input_link(i: dict, live: dict) -> dict:
        row = {k: i.get(k) for k in ('id', 'name', 'variable', 'source', 'sourceName', 'sourceKind', 'sourceState')}
        if i.get('table') and i.get('column'):
            sid = i.get('datasource')
            row.update(binding='physical', datasource=sid, table=i['table'], column=i['column'], key=i.get('assetColumn'),
                       derive=i.get('derive'), how='DDL 적재로 연결된 업무 DB 열')
            src = live.get(sid)
            if sid not in SOURCES or i.get('schema') != SOURCES[sid]['schema']:
                row.update(state='UNREGISTERED', reason='등록된 원천(업무 DB · 시계열 DB)이 아닌 연결입니다')
            elif not src['ok']:
                row.update(state='SOURCE_DOWN', reason=src['reason'])
            elif i['column'] not in src['tables'].get(i['table'], {}):
                row.update(state='MISSING', reason='원천에 이 열이 없습니다 (DDL이 바뀌었으면 다시 적재)')
            else:
                row.update(state='OK' if i.get('sourceState') in (None, 'OK') else i['sourceState'])
        elif i.get('sourceKind') == 'Sensor' and i.get('tag'):
            src = live[TS]
            row.update(binding='sensor', datasource=TS, table='tag_1s', column='value', key='asset',
                       where=f"name = '{i['tag']}'", how='센서 태그의 1초 기록')
            row.update(state='OK' if src['ok'] else 'SOURCE_DOWN', **({} if src['ok'] else {'reason': src['reason']}))
        else:
            owner = next((sid for sid, s in SOURCES.items() if i.get('source') in s['systems']), None)
            if owner == ENT:
                row.update(binding='system', datasource=ENT, state='UNBOUND',
                           reason='출처 시스템만 연결돼 있습니다 — 표 · 열은 지식 관리 "업무 데이터 연결"(DDL 적재)로 정합니다')
            elif owner == TS:
                row.update(binding='system', datasource=TS, state='DERIVED', reason='시계열에서 계산하는 값입니다 (표 · 열 하나로 정하지 않음)')
            else:
                row.update(binding='outside', datasource=None, state='OUTSIDE',
                           reason='DB에 저장된 값이 아니라 실행 중에 만들어지는 값입니다 (탐지기 · PLC · AI 에이전트 · 프로세스)')
        return row

    # ------------------------------------------------------------------ 3 묶어 보기
    def queries(self) -> list[dict]:
        return [{'id': qid, 'title': q['title'], 'question': q['question'],
                 'parts': [{'id': p['id'], 'source': p['source'], 'source_label': SOURCES[p['source']]['label'], 'purpose': p['purpose']}
                           for p in q['parts']]} for qid, q in CROSS_QUERIES.items()]

    def query(self, asset: str, query: str = 'asset', limit: int = 50, sql: dict | None = None) -> dict:
        """One entry for the portal and the MCP tool `fabric_query`.
        query='asset' : the asset's linked values from both sources, merged with provenance.
        query=<id>    : a defined cross query (CROSS_QUERIES).
        query='sql'   : sql={'hyd-enterprise': SELECT, 'hyd-timeseries': SELECT} written by a person/agent; each is guarded for
                        its own source before any connection opens (writes, other schemas, multiple statements → SqlRejected)."""
        if not isinstance(asset, str) or not asset.strip() or len(asset) > 40:
            raise ValueError('설비 코드가 필요합니다 (예: HYD-01)')
        asset, n = asset.strip(), _limit(limit, MAX_ROWS)
        if query == 'asset':
            return self._asset(asset, n)
        if query == 'sql':
            if not isinstance(sql, dict) or not sql or set(sql) - set(SOURCES):
                raise ValueError(f"sql은 원천별 SELECT입니다: {{'{ENT}': '...', '{TS}': '...'}}")
            parts = [dict(id=sid, source=sid, purpose='직접 쓴 SELECT', statement=guard_for(sid, text, n)) for sid, text in sql.items()]
            return self._run('sql', '직접 쓴 SELECT', None, asset, n, parts, [], {'asset': asset})
        if query not in CROSS_QUERIES:
            raise ValueError(f"정의되지 않은 교차 조회입니다: {query} (가능: asset, sql, {', '.join(CROSS_QUERIES)})")
        q = CROSS_QUERIES[query]
        params, notes = {'asset': asset}, []
        for name, variable in (q.get('params') or {}).items():
            rows = self._graph_rows(LIMIT_Q, variable=variable)       # the threshold is knowledge, not a code constant
            if not rows or rows[0].get('value') is None:
                raise SourceUnavailable(f'지식 그래프에 {variable} 임계값이 없습니다')
            params[name] = rows[0]['value']
            notes.append(f"기준값 {rows[0]['operator']} {rows[0]['value']}{rows[0].get('unit') or ''} — 지식 그래프 '{rows[0]['pattern']}' 패턴")
        parts = [dict(p, statement=guard_for(p['source'], p['sql'], n)) for p in q['parts']]
        return self._run(query, q['title'], q['question'], asset, n, parts, q['answer'], params, notes)

    def _run(self, qid, title, question, asset, n, parts, answer_spec, params, notes=()) -> dict:
        results, status = [], {}
        for p in parts:
            out = {'id': p['id'], 'source': p['source'], 'source_label': SOURCES[p['source']]['label'], 'purpose': p['purpose'],
                   'statement': p['statement'], 'params': {k: v for k, v in params.items() if f'%({k})s' in p['statement']}}
            try:
                with self._session(p['source']) as cur:
                    cur.execute(p['statement'], out['params'] or None)
                    out['columns'] = [d.name for d in cur.description]
                    out['rows'] = [[jsonable(v) for v in r] for r in cur.fetchall()]
                out.update(ok=True, row_count=len(out['rows']), row_limit=n, at_row_limit=len(out['rows']) >= n)
                status.setdefault(p['source'], {'ok': True})
            except (psycopg.Error, RuntimeError, OSError) as e:
                out.update(self._fail(e), rows=[], columns=[])
                status[p['source']] = {k: v for k, v in out.items() if k in ('ok', 'reason', 'detail')}
            results.append(out)
        if not any(r['ok'] for r in results):
            raise FabricUnavailable(' / '.join(f"{SOURCES[sid]['label']}: {v['reason']}" for sid, v in status.items()))
        by_id = {r['id']: r for r in results}
        answer = [_pick(label, by_id[part], how, unit) for label, part, how, unit in answer_spec]
        return {'asset': asset, 'query': qid, 'title': title, 'question': question, 'at': datetime.now(timezone.utc).isoformat(),
                'read_only': True, 'row_limit': n, 'partial': not all(r['ok'] for r in results), 'notes': list(notes),
                'sources': status, 'answer': answer, 'parts': results}

    def _asset(self, asset: str, n: int) -> dict:
        """Merged view: business rows whose foreign key points at ent.assets(code) + DDL-bound InputData values (업무 DB) and the
        newest sample of every tag recorded for the asset (시계열 DB). Each value names its class, source, table · column and
        condition. A tag no ontology class claims is shown as such, not dropped."""
        graph = {'ok': True}
        try:
            nodes, inputs = self._graph_rows(CLASS_Q), self._graph_rows(INPUTS_Q)
        except Exception as e:  # noqa: BLE001
            graph, nodes, inputs = self._fail(e), [], []
        values, parts, status, found = [], [], {}, {}
        # ---- 업무 DB
        try:
            with self._session(ENT) as cur:
                tables = {t['name']: t for t in self._tables(cur, ENT)}
                if 'assets' not in tables:
                    raise SourceUnavailable('업무 DB에 설비 표(ent.assets)가 없습니다')
                cur.execute('select * from ent.assets where code = %(asset)s', {'asset': asset})
                cols, row = [d.name for d in cur.description], cur.fetchone()
                found[ENT] = row is not None
                if row is not None:
                    for c, v in zip(cols, row):
                        values.append(_value('Asset', '설비', c, v, None, ENT, 'assets', c, f"code = '{asset}'", None))
                for t in tables.values():
                    keys = [c['name'] for c in t['columns'] if c['fk'] == 'assets.code']
                    if not keys or t['name'] == 'assets':
                        continue
                    where = ' or '.join(f'{ident(k)} = %(asset)s' for k in keys)
                    statement = f"select * from ent.{ident(t['name'])} where {where} limit {min(n, 5) + 1}"
                    cur.execute(statement, {'asset': asset})
                    rcols, rows = [d.name for d in cur.description], cur.fetchall()
                    if rows:
                        parts.append({'id': 'ent:' + t['name'], 'source': ENT, 'source_label': '업무 DB', 'ok': True,
                                      'purpose': (t['comment'] or t['name']) + f" — {', '.join(keys)} → 설비 코드(외래키)",
                                      'statement': statement, 'params': {'asset': asset}, 'columns': rcols,
                                      'rows': [[jsonable(v) for v in r] for r in rows[:min(n, 5)]], 'row_count': min(len(rows), min(n, 5)),
                                      'row_limit': min(n, 5), 'at_row_limit': len(rows) > min(n, 5)})
                for i in inputs:
                    if i.get('datasource') != ENT or i.get('schema') != 'ent' or not i.get('assetColumn') or i.get('table') not in tables:
                        continue
                    tcols = {c['name'] for c in tables[i['table']]['columns']}
                    if i.get('column') not in tcols or i['assetColumn'] not in tcols:
                        values.append(_value('InputData', i['name'], i['variable'], None, None, ENT, i['table'], i.get('column'),
                                             f"{i['assetColumn']} = '{asset}'", None, state='MISSING', reason='원천에 열이 없습니다'))
                        continue
                    if i.get('sourceState') not in (None, 'OK'):
                        values.append(_value('InputData', i['name'], i['variable'], None, None, ENT, i['table'], i['column'],
                                             f"{i['assetColumn']} = '{asset}'", None, state=i['sourceState'],
                                             reason='DDL 동기화가 이 열의 변경을 확인해 값을 읽지 않습니다'))
                        continue
                    col = ident(i['column'])
                    hours = f'round((extract(epoch from ({col} - now())) / 3600)::numeric, 2)' if i.get('derive') == 'hours_from_now' else 'null'
                    cur.execute(f"select {col}, {hours} from ent.{ident(i['table'])} where {ident(i['assetColumn'])} = %(asset)s limit 2",
                                {'asset': asset})
                    rows = cur.fetchall()
                    one = len(rows) == 1
                    extra = {} if one else {'state': 'NOT_ONE_ROW', 'reason': f"설비별 행이 {len(rows) if len(rows) < 2 else '2개 이상'}입니다"}
                    if one and i.get('derive') == 'hours_from_now':
                        extra = {'anchor': jsonable(rows[0][0]), 'derive': '저장된 시각을 지금부터 시간(h)으로 환산'}
                    values.append(_value('InputData', i['name'], i['variable'],
                                         (rows[0][1] if i.get('derive') == 'hours_from_now' else rows[0][0]) if one else None,
                                         'h' if i.get('derive') == 'hours_from_now' else None, ENT,
                                         i['table'], i['column'], f"{i['assetColumn']} = '{asset}'", None, **extra))
            status[ENT] = {'ok': True}
        except (psycopg.Error, RuntimeError, OSError) as e:
            status[ENT] = self._fail(e)
        # ---- 시계열 DB
        try:
            with self._session(TS) as cur:
                statement = ("select distinct on (name) name, value, time, extract(epoch from now() - time) from public.tag_1s "
                             f"where asset = %(asset)s and {RECENT} order by name, time desc")
                cur.execute(statement, {'asset': asset})
                rows = cur.fetchall()
                found[TS] = bool(rows)
                by_tag = {}
                for nd in nodes:
                    tag = nd.get('tag') if nd['klass'] == 'Sensor' else nd.get('resource') if nd['klass'] == 'Actuator' else None
                    if tag:
                        by_tag[tag] = nd
                used_by = {}
                for i in inputs:
                    if i.get('sourceKind') == 'Sensor' and i.get('tag'):
                        used_by.setdefault(i['tag'], []).append(i['name'])
                for name, value, at, age in rows:
                    nd = by_tag.get(name)
                    values.append(_value(nd['klass'] if nd else None, nd['name'] if nd else '온톨로지에 연결된 클래스 없음', name, value,
                                         nd.get('unit') if nd else None, TS, 'tag_1s', 'value', f"asset = '{asset}', name = '{name}'",
                                         jsonable(at), age_s=round(float(age), 1), inputs=used_by.get(name, [])))
                parts.append({'id': 'ts:latest', 'source': TS, 'source_label': '시계열 DB', 'ok': True,
                              'purpose': '태그별 최신값 (최근 10분)', 'statement': statement, 'params': {'asset': asset},
                              'columns': ['name', 'value', 'time', 'age_s'], 'rows': [[r[0], jsonable(r[1]), jsonable(r[2]), round(float(r[3]), 1)] for r in rows],
                              'row_count': len(rows), 'row_limit': None, 'at_row_limit': False})
            status[TS] = {'ok': True}
        except (psycopg.Error, RuntimeError, OSError) as e:
            status[TS] = self._fail(e)
        if not any(s['ok'] for s in status.values()):
            raise FabricUnavailable(' / '.join(f"{SOURCES[s]['label']}: {v['reason']}" for s, v in status.items()))
        if all(s['ok'] for s in status.values()) and not any(found.values()):
            raise ValueError(f'설비 코드 {asset}는 업무 DB(ent.assets)에도, 시계열 DB 최근 10분 기록에도 없습니다')
        notes = [f"{SOURCES[s]['label']}에 이 설비 기록이 없습니다" for s, ok in found.items() if not ok]
        return {'asset': asset, 'query': 'asset', 'title': '설비 하나로 두 원천 묶어 보기', 'question': None,
                'at': datetime.now(timezone.utc).isoformat(), 'read_only': True, 'row_limit': n,
                'partial': not all(s['ok'] for s in status.values()), 'notes': notes, 'graph': graph,
                'sources': status, 'answer': values, 'parts': parts}


def _limit(value, cap: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= cap:
        raise ValueError(f'행 제한은 1~{cap} 사이 정수입니다')
    return value


def _value(klass, label, field, value, unit, source, table, column, where, at, **extra) -> dict:
    return {'klass': klass, 'label': label, 'field': field, 'value': jsonable(value), 'unit': unit,
            'source': source, 'source_label': SOURCES[source]['label'],
            'from': f"{SOURCES[source]['schema']}.{table}.{column}" if column else f"{SOURCES[source]['schema']}.{table}",
            'where': where, 'at': at, **extra}


def _pick(label: str, part: dict, how: tuple, unit) -> dict:
    """Copy one value out of a part's rows (first row / last row / newest row of a tag), keeping where it came from."""
    out = {'label': label, 'unit': unit, 'part': part['id'], 'source': part['source'], 'source_label': part['source_label']}
    if not part['ok']:
        return dict(out, value=None, state='SOURCE_DOWN', reason=part['reason'])
    kind, name = how
    cols, rows = part['columns'], part['rows']
    if kind == 'latest':        # rows are (name, value, time) newest first
        row = next((r for r in rows if r[0] == name), None)
        if row is None:
            return dict(out, value=None, state='NO_DATA', reason=f'{name} 최근 기록이 없습니다')
        return dict(out, value=row[1], at=row[2], column='value', where=f"name = '{name}'")
    if name not in cols:
        return dict(out, value=None, state='MISSING', reason=f'결과에 {name} 열이 없습니다')
    if not rows:
        return dict(out, value=None, state='NO_DATA', reason='해당 설비의 행이 없습니다')
    row = rows[0] if kind == 'first' else rows[-1]
    return dict(out, value=row[cols.index(name)], column=name, row=0 if kind == 'first' else len(rows) - 1, rows=len(rows))


__all__ = ['CLASS_KEYS', 'CROSS_QUERIES', 'ENT', 'Fabric', 'FabricUnavailable', 'SOURCES', 'SourceUnavailable', 'SqlRejected', 'TS',
           'env_connectors', 'failure_reason', 'guard_for', 'timeseries_reader']
