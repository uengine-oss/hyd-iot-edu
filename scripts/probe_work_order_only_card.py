"""A090 — a root-cause work-order card (no PLC command) approved end to end: purchase request + CMMS work order + closure.

    .venv314/Scripts/python scripts/probe_work_order_only_card.py --out .evidence/reaudit/a090-wo-only-<n>

Real stack at TIME_SCALE=20 with AGENT_BRIDGE=legacy (host worker stopped). Pump leakage on HYD-02 → instance → cards.
The maintenance manager approves `skill:wo-pump-seal` (SOP-PMP-04: PR_CREATE seal kit from sup:b + WO_CREATE). Expected:
gw:control routes work_order → task:command never starts, the approval delivery creates the ERP purchase request, the
work-order step creates the CMMS work order, the Incident ends through the work-order-only path with no cmdId, the
instance ends with ev:closed. The plant alert stays RAISED (the seal is not replaced by the plant model); the plant is
reset at the end. The pump scenario in scenario_pump_fan_test.py covers the control-card path; this covers the other
branch of gw:control, never exercised live before A090.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scenario_pump_fan_test as sc  # noqa: E402

OPTION = 'skill:wo-pump-seal'
sc.REASSESS_HELD = True   # the 2-minute evidence windows still hold pre-fault samples 18 s after injection: the diagnosis is
                          # held (A053) and explicitly reassessed after a full window, as scenario_pump_fan_test does


def ent(sql):
    r = subprocess.run(['docker', 'exec', 'supabase_db_hyd-iot-edu', 'psql', '-U', 'postgres', '-d', 'postgres', '-At', '-F', '|', '-c', sql],
                       capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True)
    out = Path(ap.parse_args().out); out.mkdir(parents=True, exist_ok=False)
    def save(name, v): (out / f'{name}.json').write_text(json.dumps(v, ensure_ascii=False, indent=2, default=str), encoding='utf8')
    mode = sc.get(f'{sc.PROCESS}/api/process/mode')
    sc.check('process in instance mode with the legacy bridge', mode.get('mode') == 'instance' and mode.get('agent_bridge') == 'legacy', json.dumps(mode)[:160])
    sc.post(f'{sc.PLANT}/api/reset'); sc.post(f'{sc.ENT}/api/reset')
    pr_before = int(ent("select count(*) from ent.purchase_requests where asset='HYD-02'") or 0)
    try:
        r = sc.run_to_selection('HYD-02', 'pump_leakage', 'PUMP_LEAKAGE', 120)
        if not r:
            sc.summary()
        pid, inc_id, dec, sel, vd = r
        save('1-decision', dec)
        opts = {o['id']: o for o in dec.get('options', [])}
        card = opts.get(OPTION)
        sc.check('the root-cause work-order card is a feasible candidate (A090 link)', card is not None and card['feasible'] and card['kind'] == 'work_order'
                 and (card.get('facts') or {}).get('supplier_avl') is True,
                 json.dumps({k: (o.get('rank'), o.get('kind'), o.get('feasible')) for k, o in opts.items()}, ensure_ascii=False))
        sc.check('card carries the purchase request and the work order', {a.get('code') for a in card['actions']} >= {'PR_CREATE', 'WO_CREATE'} and card.get('approver', {}).get('id') == 'role:maint-mgr',
                 json.dumps(card['actions'], ensure_ascii=False)[:240])
        r = sc.select_with_review(sel, dec, OPTION, '김정비', 'role:maint-mgr', '누설 원인인 축 씰을 교체한다', inc_id)
        if not sc.check('maintenance manager approved the work-order card', 'instance' in r and not r.get('error'), str(r.get('body') or r)[:300]):
            sc.summary()
        save('2-select', r)
        def delivered():
            v = sc.view(pid)
            a = [x for x in v.get('approvals') or [] if x.get('status') in ('DELIVERED', 'FAILED')]
            return v if a else None
        v, dt = sc.wait_for(delivered, 90)
        appr = next((x for x in (v or {}).get('approvals') or [] if x.get('status') in ('DELIVERED', 'FAILED')), {})
        results = appr.get('results') or []
        pr = next((x for x in results if x.get('code') == 'PR_CREATE'), None)
        sc.check('approval delivered the ERP purchase request (sup:b) before any plant action', appr.get('status') == 'DELIVERED' and pr and pr.get('ok') is True and str(pr.get('ref', '')).startswith('PR-'),
                 json.dumps({'status': appr.get('status'), 'results': results, 'error': appr.get('error')}, ensure_ascii=False)[:300])
        rows = ent("select id, supplier, status from ent.purchase_requests where asset='HYD-02' order by created_at desc limit 3")
        sc.check('purchase request row exists in the business DB', int(ent("select count(*) from ent.purchase_requests where asset='HYD-02'") or 0) == pr_before + 1 and 'sup:b' in rows, rows)
        fin = sc.finish(pid, inc_id, 'ev:closed', timeout=180)
        inc = sc.get(f'{sc.PROCESS}/api/incidents/{inc_id}'); save('3-incident', inc)
        if fin:
            save('4-final', fin)
            wi = {w['activity_id']: w for w in fin['workitems']}
            sc.check('task:command never started (gw:control → work-order branch)', wi.get('task:command', {}).get('status') in ('TODO', 'CANCELLED') and wi.get('task:reobserve', {}).get('status') in ('TODO', 'CANCELLED'),
                     json.dumps({k: w['status'] for k, w in wi.items()}, ensure_ascii=False))
            wo = (wi.get('task:work-order') or {}).get('output', {}).get('work_order') or {}
            sc.check('CMMS work order created for SOP-PMP-04', wo.get('ok') is True and str(wo.get('ref', '')).startswith('WO-') and 'SOP-PMP-04' in json.dumps(wo, ensure_ascii=False), json.dumps(wo, ensure_ascii=False)[:200])
            sc.check('incident closed through the work-order-only path with no PLC command', inc.get('state') == 'CLOSED' and not inc.get('cmdId') and (inc.get('workOrder') or {}).get('ref') == wo.get('ref'),
                     json.dumps({'state': inc.get('state'), 'cmdId': inc.get('cmdId'), 'workOrder': inc.get('workOrder')}, ensure_ascii=False)[:200])
            audits = [a for a in sc.get(f'{sc.PROCESS}/api/audit') if a.get('incident') == inc_id]
            sc.check('no action.cmd was ever issued for this incident', not any(a.get('event') in ('ACTION_CMD', 'COMMAND_ISSUED', 'ACK') for a in audits), sorted({a.get('event') for a in audits}))
    finally:
        sc.post(f'{sc.PLANT}/api/reset')
    (out / 'checks.json').write_text(json.dumps(sc.results, ensure_ascii=False, indent=2), encoding='utf8')
    sc.summary()


if __name__ == '__main__':
    main()
