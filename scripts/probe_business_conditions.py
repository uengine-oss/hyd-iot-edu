"""A078 — a *new* business condition (contract failure cost · finished-goods stock) reaches the judgment with data only
(meeting L385~404: 설비 상태만이 아니라 계약·납기·품질 같은 업무 상황을 같이 보고 대안을 비교한다).

    .venv314/Scripts/python scripts/probe_business_conditions.py --out .evidence/reaudit/a078-conditions-<n>

Real HTTP (process), Neo4j, PostgreSQL (ent schema) and the DMN MCP tool the agents call. No code change, no Codex/Claude,
no PLC command. Path: real ent tables → DDL ingestion (physical InputData) → reviewed ranking-policy change that aliases the
new variables → evaluate_cards reads the live DB values → a real business change flips the recommendation → an approval
on the old card is refused → everything is restored (CAS policy restore, ingestion batch removed, DB values put back).
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import urllib.error
import urllib.parse
import uuid

import psycopg
from probe_physical_facts import http
from probe_ranking_policy import mcp

DSN = 'postgresql://postgres:postgres@127.0.0.1:54322/postgres'
DDL = '''
create table ent.sales_contracts (sales_order text, asset text, order_id text, customer text, customer_tier text,
    penalty_per_h numeric, failure_cost numeric, claim_cost numeric);
comment on column ent.sales_contracts.failure_cost is '설비 고장 시 계약상 손실 비용 (만원)';
create table ent.fg_inventory (asset text, fg_item text, fg_stock integer, ship_at timestamptz, warehouse text);
comment on column ent.fg_inventory.fg_stock is '완제품 재고 수량';
comment on column ent.fg_inventory.ship_at is '다음 출하 일시';
'''
ARGS = dict(asset='HYD-01', pattern='FAN_VIBRATION', cause='cause:fan-bearing-wear', failure_mode='fm:bearing-degradation')   # has keep · reduce · stop cards
PATH = '/api/kg/ranking-policy/rule%3Arank-value'


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True)
    out = Path(ap.parse_args().out); out.mkdir(parents=True, exist_ok=False)
    report = {'scope': __doc__, 'checks': {}}
    def save(): (out / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding='utf8')
    def check(name, ok, detail=None):
        report['checks'][name] = {'passed': bool(ok), 'detail': detail}; save()
        print(('PASS ' if ok else 'FAIL ') + name + ('' if detail is None else '  ' + json.dumps(detail, ensure_ascii=False, default=str)[:220]), flush=True)
        assert ok, name
    original = http(8080, PATH); current = original; report['original'] = original
    batch = None
    with psycopg.connect(DSN, autocommit=True) as db:
        before = db.execute("select failure_cost from ent.sales_contracts where asset='HYD-01'").fetchone()[0]
        stock_before, ship_before = db.execute("select fg_stock, ship_at from ent.fg_inventory where asset='HYD-01'").fetchone()
        report['db_before'] = dict(failure_cost=before, fg_stock=stock_before, ship_at=ship_before)
        try:
            # 1. the real tables become judgment inputs through the ordinary DDL ingestion (no new code)
            plan = http(8080, '/api/kg/ddl/preview', dict(text=DDL, filename='a078-real-business-tables.sql',
                        selection={'ent.sales_contracts': ['failure_cost'], 'ent.fg_inventory': ['fg_stock', 'ship_at']},
                        systems={'ent.sales_contracts': 'sys:erp', 'ent.fg_inventory': 'sys:erp'}))
            report['plan'] = plan; save()
            http(8080, '/api/kg/ddl/commit', plan); batch = plan['batch']
            var = {i['column']: i['variable'] for i in plan['inputs']}
            names = {i['column']: i['name'] for i in plan['inputs']}
            check('three_real_columns_became_physical_inputs_with_their_comments',
                  set(var) == {'failure_cost', 'fg_stock', 'ship_at'} and names['failure_cost'].startswith('설비 고장 시'), dict(var=var, names=names))
            derive = {i['column']: i.get('derive') for i in plan['inputs']}
            check('the_shipping_time_column_is_read_as_hours_from_now', derive == {'failure_cost': None, 'fg_stock': None, 'ship_at': 'hours_from_now'}, derive)   # A086
            # 2. a reviewed policy change aliases them; nothing else in the policy moves
            policy = json.loads(json.dumps(original['policy']))
            policy['inputs'].update(fail_cost=var['failure_cost'], stock=var['fg_stock'], ship_h=var['ship_at'])
            policy['components']['contract'] = "0 if fail_cost is None else -round(clamp(fail_cost / 1000, 0, 5), 2) * (1 if production == 'keep' else 0)"
            policy['components']['stock'] = "0 if stock is None or ship_h is None else round(clamp(stock / 1000, 0, 1), 2) * (1 if production == 'stop' else 0)"
            body = dict(policy=policy, annotation=original['annotation'] + ' + 계약 고장 손실(만원/1000, 유지 카드 감산, ≤5) + 완제품 재고(수량/1000, 정지 카드 가산, ≤1)',
                        expected_revision=current['revision'], request_id=str(uuid.uuid4()), by='[회귀 검사] A078 검사기',
                        reason='[회귀 검사] A078: 회의 L385~404 계약·재고 조건을 데이터만으로 추가하는 경로 검증')
            current = http(8080, PATH, body, 'PUT'); report['policy_write'] = current; save()
            check('policy_with_new_aliases_accepted', current['policy']['inputs']['fail_cost'] == var['failure_cost'])
            # 3. the DMN tool the agents call reads the live DB values and scores every card with the new components
            first = mcp('evaluate_cards', ARGS); report['evaluate_seed'] = first; save()
            facts = first['facts']
            ship_h = facts.get(var['ship_at'])
            expected_h = (ship_before - datetime.now(timezone.utc)).total_seconds() / 3600
            check('live_db_values_arrive_as_facts', str(facts.get(var['failure_cost'])).startswith(str(before)) and facts.get(var['fg_stock']) == stock_before
                  and ship_h is not None and abs(float(ship_h) - expected_h) < 0.2, {k: facts.get(v) for k, v in var.items()} | {'expected_ship_h': round(expected_h, 2)})
            opts = {o['id']: o for o in first['result']['options']}
            parts = {k: o.get('scoreParts', {}) for k, o in opts.items()}
            check('every_card_has_contract_and_stock_components', all({'contract', 'stock'} <= set(p) for p in parts.values()), parts)
            prod = {k: o.get('production') for k, o in opts.items()}
            check('keep_cards_pay_contract_risk_and_stop_cards_gain_stock_relief',
                  all((p['contract'] < 0) == (prod[k] == 'keep') and (p['stock'] > 0) == (prod[k] == 'stop') for k, p in parts.items()), dict(prod=prod))
            seed_reco = first['recommended']
            # 4. a real business change (contract loss jumps, big stock) → different recommendation, no code touched
            db.execute("update ent.sales_contracts set failure_cost=5000 where asset='HYD-01'")
            db.execute("update ent.fg_inventory set fg_stock=3000 where asset='HYD-01'")
            second = mcp('evaluate_cards', ARGS); report['evaluate_changed'] = second; save()
            parts2 = {o['id']: o.get('scoreParts', {}) for o in second['result']['options']}
            check('changed_values_change_component_scores', any(parts2[k] != parts[k] for k in parts2 if k in parts), {k: (parts[k].get('contract'), parts2[k].get('contract')) for k in parts2 if k in parts})
            def rank(doc, sid): return next(o['rank'] for o in doc['result']['options'] if o['id'] == sid)
            keeps = [k for k, p in prod.items() if p == 'keep']; stops = [k for k, p in prod.items() if p == 'stop']
            check('scenario_has_keep_and_stop_cards_to_compare', bool(keeps) and bool(stops), dict(keeps=keeps, stops=stops))
            before_order = {k: rank(first, k) for k in keeps + stops}; after_order = {k: rank(second, k) for k in keeps + stops}
            check('big_contract_loss_and_stock_put_the_stop_card_above_the_run_on_cards',
                  all(any(before_order[s] > before_order[k] for k in keeps) for s in stops) and all(after_order[s] < after_order[k] for s in stops for k in keeps),
                  dict(before=before_order, after=after_order, recommended_before=seed_reco, recommended_after=second['recommended']))
            old = dict(first, options=first['result']['options'])
            assessment = http(8091, '/api/agent/approval-check', dict(decision=old, option=seed_reco, role='role:prod-mgr'))
            report['approval_check'] = assessment; save()
            check('approving_the_old_card_after_the_change_is_refused', not assessment['allowed'] and any(var['failure_cost'] in r or var['fg_stock'] in r or 'policy' in r for r in assessment['reasons']), assessment['reasons'][:3])
        finally:
            db.execute("update ent.sales_contracts set failure_cost=%s where asset='HYD-01'", (before,))
            db.execute("update ent.fg_inventory set fg_stock=%s, ship_at=%s where asset='HYD-01'", (stock_before, ship_before))
            restore = dict(policy=original['policy'], annotation=original['annotation'], expected_revision=http(8080, PATH)['revision'],
                           request_id=str(uuid.uuid4()), by='[회귀 검사] A078 검사기', reason='[회귀 검사] A078 원래대로 복원')
            current = http(8080, PATH, restore, 'PUT')
            if batch:
                report['ingest_cleanup'] = http(8080, '/api/kg/ingests/' + urllib.parse.quote(batch, safe=''), method='DELETE')
            save()
    after = mcp('evaluate_cards', ARGS); report['evaluate_restored'] = after; save()
    check('restored_policy_and_graph_give_the_original_recommendation', current['policy'] == original['policy'] and after['recommended'] == report['evaluate_seed']['recommended']
          and not any(k.startswith('db_') for k in after['facts']), dict(reco=after['recommended']))
    print(out, flush=True)
    return 0 if all(c['passed'] for c in report['checks'].values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
