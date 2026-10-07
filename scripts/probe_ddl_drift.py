"""A087 (DoD 4) — a business DDL that no longer matches the live database is detected and never read as a fact.

    .venv314/Scripts/python scripts/probe_ddl_drift.py --out .evidence/reaudit/a087-ddl-drift-<n>

Real stack: process DDL ingestion + DDL source sync, Neo4j, hyd-dmn evaluate_cards (the DMN tool the agents call).
1. A reviewed DDL is ingested whose columns disagree with the live ent.fg_inventory: fg_item declared integer (live text),
   ship_eta declared timestamptz (no such column), fg_stock integer (matches). The commit's own sync marks them
   TYPE_CHANGED · MISSING · OK.
2. A reviewed ranking-policy change aliases the three inputs, so the DMN tool gathers them as facts: only fg_stock arrives
   with its live value; the other two are unknown with the DDL-sync reason (no wrong-meaning value, no read of a ghost).
3. Policy and batch are restored; the bindings disappear with the batch.
"""
import argparse
import json
import urllib.parse
import uuid
from pathlib import Path

import psycopg
from probe_physical_facts import http
from probe_ranking_policy import mcp

DSN = 'postgresql://postgres:postgres@127.0.0.1:54322/postgres'
DDL = '''
create table ent.fg_inventory (asset text, fg_item integer, fg_stock integer, ship_eta timestamptz);
comment on column ent.fg_inventory.fg_item is '완제품 품목 번호 (이 DDL에서는 정수로 선언)';
comment on column ent.fg_inventory.fg_stock is '완제품 재고 수량';
comment on column ent.fg_inventory.ship_eta is '출하 예정 일시 (실제 DB에는 없는 열)';
'''
ARGS = dict(asset='HYD-01', pattern='FAN_VIBRATION', cause='cause:fan-bearing-wear', failure_mode='fm:bearing-degradation')
PATH = '/api/kg/ranking-policy/rule%3Arank-value'


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True)
    out = Path(ap.parse_args().out); out.mkdir(parents=True, exist_ok=False)
    report = {'scope': __doc__, 'checks': {}}
    def save(): (out / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding='utf8')
    def check(name, ok, detail=None):
        report['checks'][name] = {'passed': bool(ok), 'detail': detail}; save()
        print(('PASS ' if ok else 'FAIL ') + name + ('' if detail is None else '  ' + json.dumps(detail, ensure_ascii=False, default=str)[:300]), flush=True)
    original = http(8080, PATH); report['original_policy_revision'] = original['revision']
    with psycopg.connect(DSN, autocommit=True) as db:
        live = dict(db.execute("select column_name, data_type from information_schema.columns where table_schema='ent' and table_name='fg_inventory'").fetchall())
        stock = db.execute("select fg_stock from ent.fg_inventory where asset='HYD-01'").fetchone()[0]
    report['live_columns'] = live
    batch = None
    try:
        plan = http(8080, '/api/kg/ddl/preview', dict(text=DDL, filename='a087-stale-fg-inventory.sql',
                    selection={'ent.fg_inventory': ['fg_item', 'fg_stock', 'ship_eta']}, systems={'ent.fg_inventory': 'sys:erp'}))
        committed = http(8080, '/api/kg/ddl/commit', plan); batch = plan['batch']; report['commit'] = committed; save()
        var = {i['column']: i['variable'] for i in plan['inputs']}; ids = {i['column']: i['id'] for i in plan['inputs']}
        states = (committed.get('sourceSync') or {}).get('states') or {}
        by_id = {iid: s for s, lst in states.items() for iid in lst}
        check('commit_sync_marks_each_binding_against_the_live_catalog',
              by_id.get(ids['fg_item']) == 'TYPE_CHANGED' and by_id.get(ids['ship_eta']) == 'MISSING' and by_id.get(ids['fg_stock']) == 'OK',
              dict(states={c: by_id.get(i) for c, i in ids.items()}, live=live))
        again = http(8080, '/api/kg/ddl/sync', {}); report['resync'] = again; save()
        check('a_second_poll_changes_nothing', again.get('changed') == 0, again)
        policy = json.loads(json.dumps(original['policy']))
        policy['inputs'].update(item=var['fg_item'], stock=var['fg_stock'], eta=var['ship_eta'])
        policy['components']['stock'] = "0 if stock is None else round(clamp(stock / 1000, 0, 1), 2) * (1 if production == 'stop' else 0)"
        body = dict(policy=policy, annotation=original['annotation'] + ' + A087 DDL 동기화 검증용 별칭', expected_revision=original['revision'],
                    request_id=str(uuid.uuid4()), by='A087 probe', reason='A087: 원천 DDL과 어긋난 바인딩을 판단에 쓰지 않는지 검증')
        http(8080, PATH, body, 'PUT')
        doc = mcp('evaluate_cards', ARGS); report['evaluate'] = doc; save()
        facts = doc.get('facts') or {}
        prov = {p['variable']: p for p in doc.get('provenance') or []}
        check('only_the_matching_column_arrives_as_a_fact', facts.get(var['fg_stock']) == stock and facts.get(var['fg_item']) is None and facts.get(var['ship_eta']) is None,
              {c: facts.get(v) for c, v in var.items()})
        reasons = {c: (prov.get(v) or {}).get('error') for c, v in var.items()}
        check('the_stale_bindings_carry_the_ddl_sync_reason', all(r and 'DDL 동기화' in r for r in (reasons['fg_item'], reasons['ship_eta']))
              and 'TYPE_CHANGED' in reasons['fg_item'] and 'MISSING' in reasons['ship_eta'] and not reasons['fg_stock'], reasons)
    finally:
        cur = http(8080, PATH)
        restore = dict(policy=original['policy'], annotation=original['annotation'], expected_revision=cur['revision'],
                       request_id=str(uuid.uuid4()), by='A087 probe', reason='A087 restore')
        report['restored_policy'] = http(8080, PATH, restore, 'PUT')['policy'] == original['policy']
        if batch:
            report['ingest_cleanup'] = http(8080, '/api/kg/ingests/' + urllib.parse.quote(batch, safe=''), method='DELETE')
        save()
    after = http(8080, '/api/kg/ddl/sync', {}); report['after_cleanup'] = after
    check('policy_restored_and_bindings_gone_with_the_batch', report['restored_policy'] and after.get('checked') == 0, after)
    failed = [k for k, v in report['checks'].items() if not v['passed']]
    print('ALL PASS' if not failed else f'FAILED: {failed}', flush=True)
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
