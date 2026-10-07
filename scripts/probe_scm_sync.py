"""A089/A090 — supplier master data in the graph follows ent.suppliers, and an AVL withdrawal in SCM excludes the purchase card.

    .venv314/Scripts/python scripts/probe_scm_sync.py --out .evidence/reaudit/a090-scm-<n>

Real stack: process SCM sync (periodic + POST /api/kg/scm/sync), Neo4j, hyd-dmn evaluate_cards. The sync may already have
run before this probe, so each check first creates the exact difference it judges:
1. the cooler-core quote of sup:c is removed from the graph → one sync puts it back with ent's values;
2. a second sync changes nothing;
3. pump scenario: skill:wo-pump-seal (PR_CREATE sup:b) is a feasible card while sup:b is approved;
4. ent.suppliers sup:b avl=false → sync → the same card is excluded by rule:avl (supplier_avl False);
5. avl restored → sync → the card is feasible again. Nothing else is touched.
"""
import argparse
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_ranking_policy import mcp  # noqa: E402

PUMP = dict(asset='HYD-02', pattern='PUMP_LEAKAGE', cause='cause:pump-seal-wear', failure_mode='fm:volumetric-loss')


def post(path):
    req = urllib.request.Request('http://127.0.0.1:8080' + path, data=b'{}', method='POST', headers={'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(req, timeout=60))


def ent(sql):
    r = subprocess.run(['docker', 'exec', 'supabase_db_hyd-iot-edu', 'psql', '-U', 'postgres', '-d', 'postgres', '-At', '-c', sql],
                       capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def cy(q):
    r = subprocess.run(['docker', 'exec', 'hyd-iot-edu-neo4j-1', 'cypher-shell', '-u', 'neo4j', '-p', 'hydpass123', '--format', 'plain', q],
                       capture_output=True, text=True, encoding='utf-8', timeout=60)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip().splitlines()[1:]


def card(doc, sid='skill:wo-pump-seal'):
    return next((o for o in (doc.get('result') or {}).get('options', []) if o['id'] == sid), None)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True)
    out = Path(ap.parse_args().out); out.mkdir(parents=True, exist_ok=False)
    report = {'scope': __doc__, 'checks': {}}
    def save(name, v): (out / f'{name}.json').write_text(json.dumps(v, ensure_ascii=False, indent=2, default=str), encoding='utf8')
    def check(name, ok, detail=None):
        report['checks'][name] = {'passed': bool(ok), 'detail': detail}; save('result', report)
        print(('PASS ' if ok else 'FAIL ') + name + ('' if detail is None else '  ' + json.dumps(detail, ensure_ascii=False, default=str)[:260]), flush=True)
    src = ent("select price, fail_rate, lead_d from ent.suppliers where id='sup:c' and part_no='P-CLR-CORE'").split('|')
    cy("MATCH (:Part {partNo:'P-CLR-CORE'})-[x:SUPPLIED_BY]->(:Supplier {id:'sup:c'}) DELETE x RETURN count(*)")
    assert cy("MATCH (:Part {partNo:'P-CLR-CORE'})-[x:SUPPLIED_BY]->(:Supplier {id:'sup:c'}) RETURN x") == [], 'edge removal failed'
    first = post('/api/kg/scm/sync'); save('1-sync-after-removal', first)
    edge = cy("MATCH (:Part {partNo:'P-CLR-CORE'})-[x:SUPPLIED_BY]->(:Supplier {id:'sup:c'}) RETURN x.price, x.failRate, x.leadDays")
    check('sync_restores_the_removed_quote_with_ents_values',
          any(q['supplier'] == 'sup:c' for q in first['set_quotes']) and edge == [f'{float(src[0])}, {float(src[1])}, {int(src[2])}'],
          dict(set_quotes=first['set_quotes'], edge=edge, ent=src))
    check('second_sync_is_a_no_op', post('/api/kg/scm/sync')['changed'] == 0)
    before = mcp('evaluate_cards', PUMP); c0 = card(before); save('2-cards-approved', before)
    check('purchase_card_is_a_feasible_candidate_while_sup_b_is_approved',
          c0 is not None and c0['feasible'] and (c0.get('facts') or {}).get('supplier_avl') is True,
          dict(rank=c0 and c0['rank'], feasible=c0 and c0['feasible'], avl=c0 and c0['facts'].get('supplier_avl')))
    try:
        ent("update ent.suppliers set avl = false where id = 'sup:b'")
        s = post('/api/kg/scm/sync'); save('3-sync-after-withdrawal', s)
        check('avl_withdrawal_reaches_the_graph', any(x['id'] == 'sup:b' and x['avl'] is False for x in s['set_suppliers'])
              and cy("MATCH (s:Supplier {id:'sup:b'}) RETURN s.avl") == ['FALSE'], s['set_suppliers'])
        after = mcp('evaluate_cards', PUMP); c1 = card(after); save('4-cards-withdrawn', after)
        check('rule_avl_now_excludes_the_purchase_card',
              c1 is not None and not c1['feasible'] and (c1.get('facts') or {}).get('supplier_avl') is False
              and any(v.get('rule') == 'rule:avl' for v in c1.get('violations') or []),
              dict(feasible=c1 and c1['feasible'], avl=c1 and c1['facts'].get('supplier_avl'), violations=c1 and [v.get('rule') for v in c1.get('violations') or []]))
    finally:
        ent("update ent.suppliers set avl = true where id = 'sup:b'")
        restored = post('/api/kg/scm/sync'); save('5-sync-after-restore', restored)
    c2 = card(mcp('evaluate_cards', PUMP))
    check('restored_card_is_feasible_again', cy("MATCH (s:Supplier {id:'sup:b'}) RETURN s.avl") == ['TRUE'] and c2 is not None and c2['feasible'],
          dict(feasible=c2 and c2['feasible']))
    failed = [k for k, v in report['checks'].items() if not v['passed']]
    print('ALL PASS' if not failed else f'FAILED: {failed}', flush=True)
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
