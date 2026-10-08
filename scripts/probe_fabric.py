"""A11 데이터 패브릭 미니 라이브 검사 — 실제 두 원천(업무 DB · 시계열 DB)에 대어 값 · 출처 · 쓰기 거부 · 연결 실패 사유를 확인한다.

    ENTERPRISE_READ_DSN=… TSDB_READ_DSN=… [NEO4J_URI=… NEO4J_AUTH=…] python scripts/probe_fabric.py --asset HYD-01 --out .evidence/A11/probe.json
    (그래프 없이 돌릴 때만 --graph-fixture FILE: {"nodes": [...], "inputs": [...], "limits": {"ts1": {...}}})

검사 (모두 실제 연결):
  sources      두 원천 연결 · 전용 읽기 계정 · read_only=on · 표 목록
  values       교차 조회 값이 같은 읽기 계정으로 직접 읽은 원천 값과 같다(가장 이른 납기 오더 · 최신 TS1)
  write_guard  쓰기 SQL은 연결 전에 거절(SqlRejected)
  write_db     가드를 건너뛰어 같은 연결로 INSERT를 보내도 DB가 거절(읽기 전용 트랜잭션 · 권한)
  failures     닫힌 포트 · 틀린 비밀번호 · 쓰기 가능한 계정 → 사람이 읽을 사유, 한 원천만 실패하면 partial
종료 코드 0 = 전부 통과.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'common'))

import psycopg  # noqa: E402

from hydcommon import fabric as fb  # noqa: E402
from hydcommon.fabric import ENT, TS, Fabric, FabricUnavailable, SqlRejected  # noqa: E402


def neo4j_graph():
    from neo4j import GraphDatabase
    user, pwd = os.getenv('NEO4J_AUTH', 'neo4j/hydpass123').split('/', 1)
    driver = GraphDatabase.driver(os.getenv('NEO4J_URI', 'bolt://localhost:7687'), auth=(user, pwd))

    def graph(cypher, **params):
        with driver.session() as s:
            return s.execute_read(lambda tx: [r.data() for r in tx.run(cypher, **params)])
    return graph


def fixture_graph(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))

    def graph(cypher, **params):
        if 'AnomalyPattern' in cypher:
            row = data.get('limits', {}).get(params.get('variable'))
            return [row] if row else []
        if 'SOURCED_FROM' in cypher:
            return data['inputs']
        return data['nodes']
    return graph


def dsn_with(dsn, *, port=None, password=None, user=None):
    u = urlsplit(dsn)
    host = u.hostname
    netloc = f"{user or u.username}:{password if password is not None else u.password}@{host}:{port or u.port}"
    return urlunsplit((u.scheme, netloc, u.path, u.query, u.fragment))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--asset', default='HYD-01')
    ap.add_argument('--graph-fixture')
    ap.add_argument('--writer-dsn', help='쓰기 가능한 계정 DSN (전용 읽기 계정 검사가 거절하는지 확인)')
    ap.add_argument('--out')
    a = ap.parse_args()
    ent_dsn, ts_dsn = os.environ['ENTERPRISE_READ_DSN'], os.getenv('TSDB_READ_DSN') or os.environ['TSDB_DSN']
    graph = fixture_graph(a.graph_fixture) if a.graph_fixture else neo4j_graph()
    f = Fabric(graph=graph)
    report, checks = {'asset': a.asset, 'graph': 'fixture ' + a.graph_fixture if a.graph_fixture else os.getenv('NEO4J_URI', 'bolt://localhost:7687')}, {}

    def check(name, ok, **detail):
        checks[name] = {'ok': bool(ok), **detail}
        print(('PASS ' if ok else 'FAIL ') + name, json.dumps(detail, ensure_ascii=False, default=str)[:300])

    # 1 sources
    sources = f.sources()
    report['sources'] = sources
    check('sources_connected_read_only', all(s['ok'] and s['read_only'] for s in sources),
          sources=[(s['id'], s.get('user'), s.get('read_only'), len(s.get('tables') or []), s.get('reason')) for s in sources])
    report['tables'] = {s: f.tables(s) for s in fb.SOURCES}
    report['samples'] = {ENT: f.sample(ENT, 'production_orders', 3), TS: f.sample(TS, 'tag_1s', 5)}
    check('samples_have_rows', all(v['row_count'] > 0 for v in report['samples'].values()),
          rows={k: v['row_count'] for k, v in report['samples'].items()})

    # 2 links
    links = f.links()
    report['links'] = links
    check('class_links_verified', links['graph']['ok'] and all(c['state'] in ('OK', 'MISSING') for c in links['classes']),
          classes=[(c['klass'], c['source'], c['table'] + '.' + c['column'], c['state'], len(c.get('matched') or []), len(c.get('unmatched') or []))
                   for c in links['classes']])

    # 3 values — fabric answer vs a direct read through the same reader accounts
    report['queries'] = {}
    for q in ['asset', *fb.CROSS_QUERIES]:
        report['queries'][q] = f.query(a.asset, q, 20)
    due = report['queries']['due-vs-temp']
    with fb.enterprise_reader(ent_dsn) as c:
        direct_order = c.execute('select order_id from ent.production_orders where asset=%s order by due_at limit 1', (a.asset,)).fetchone()[0]
    with fb.timeseries_reader(ts_dsn) as c:
        direct_ts1 = c.execute("select value from tag_1s where asset=%s and name='TS1' order by time desc limit 1", (a.asset,)).fetchone()[0]
    got = {x['label']: x for x in due['answer']}
    ts1 = got['지금 유온']
    check('cross_query_value_equals_source', got['가장 이른 납기 오더']['value'] == direct_order and ts1['source'] == TS and ts1['value'] is not None
          and abs(ts1['value'] - direct_ts1) < 5, fabric=[got['가장 이른 납기 오더']['value'], ts1['value']], direct=[direct_order, direct_ts1],
          note='TS1 은 시뮬레이터가 1초마다 쓰므로 직접 읽기와 몇 초 차이가 날 수 있다')
    check('every_answer_names_its_source', all(x.get('source') in fb.SOURCES for q in report['queries'].values() for x in q['answer'])
          and all(p.get('statement') for q in report['queries'].values() for p in q['parts']),
          answers=sum(len(q['answer']) for q in report['queries'].values()))
    check('cross_queries_not_partial', not any(q['partial'] for q in report['queries'].values()),
          nulls=[(qid, x['label'], x.get('state')) for qid, q in report['queries'].items() if qid != 'asset' for x in q['answer'] if x['value'] is None])

    # 4 writes refused
    refused = {}
    for src, sql in ((ENT, "insert into ent.assets(code, name) values ('X', 'x')"), (ENT, 'delete from ent.production_orders'),
                     (TS, "insert into tag_1s values (now(), 'HYD-01', 'TS1', 99)"), (ENT, 'select 1; drop table ent.assets')):
        try:
            f.query(a.asset, 'sql', sql={src: sql})
            refused[sql] = 'NOT REFUSED'
        except SqlRejected as e:
            refused[sql] = str(e)
    check('write_sql_refused_before_connection', all(v != 'NOT REFUSED' for v in refused.values()), refused=refused)
    db_refusals = {}
    for src, connect, sql in ((ENT, f._connect[ENT], "insert into ent.assets(code, name) values ('X', 'x')"),
                              (TS, f._connect[TS], "insert into tag_1s values (now(), 'HYD-01', 'TS1', 99)")):
        try:
            with f._session(src) as cur:
                cur.execute(sql)
            db_refusals[src] = 'NOT REFUSED'
        except psycopg.Error as e:
            db_refusals[src] = {'sqlstate': e.sqlstate, 'error': fb.first_line(e), 'reason': fb.failure_reason(e)}
    check('write_refused_by_database_too', all(v != 'NOT REFUSED' for v in db_refusals.values()), refused=db_refusals)

    # 5 failures with reasons
    dead_port = dsn_with(ts_dsn, port=1)
    wrong_pw = dsn_with(ent_dsn, password='wrong-password')
    partial = Fabric(connect={ENT: f._connect[ENT], TS: lambda: fb.timeseries_reader(dead_port)}, graph=graph).query(a.asset, 'due-vs-temp')
    check('one_source_down_is_partial_with_reason', partial['partial'] and not partial['sources'][TS]['ok']
          and partial['sources'][ENT]['ok'], reason=partial['sources'][TS])
    bad = Fabric(connect={ENT: lambda: fb.enterprise_reader(wrong_pw), TS: lambda: fb.timeseries_reader(dead_port)}, graph=graph)
    status = {s['id']: s for s in bad.sources()}
    check('connection_failure_reasons', not status[ENT]['ok'] and '인증' in status[ENT]['reason'] and not status[TS]['ok']
          and '연결할 수 없습니다' in status[TS]['reason'], reasons={k: (v['reason'], v['detail']) for k, v in status.items()})
    try:
        bad.query(a.asset, 'due-vs-temp')
        check('both_down_is_an_error', False)
    except FabricUnavailable as e:
        check('both_down_is_an_error', True, message=str(e))
    if a.writer_dsn:
        writer = Fabric(connect={ENT: lambda: fb.enterprise_reader(a.writer_dsn), TS: lambda: fb.timeseries_reader(a.writer_dsn)}, graph=graph)
        st = {s['id']: s for s in writer.sources()}
        check('writer_account_refused', all(not s['ok'] and '전용 읽기 계정이 아닌' in s['reason'] for s in st.values()),
              reasons={k: v['reason'] for k, v in st.items()})
    unset = Fabric(connect=fb.env_connectors({}), graph=graph).sources()
    check('missing_setting_named', all('환경변수' in s['reason'] for s in unset), reasons=[s['reason'] for s in unset])

    report['checks'] = checks
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str), encoding='utf-8')
    failed = [k for k, v in checks.items() if not v['ok']]
    print(f"{len(checks) - len(failed)}/{len(checks)} passed" + (f" — FAILED {failed}" if failed else ''))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
