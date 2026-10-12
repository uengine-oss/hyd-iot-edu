import json,sys,importlib.util,hashlib
from pathlib import Path
import psycopg
TREE=Path('D:/work/study/hyd-iot-edu/.claude/worktrees/codex-portal-20261011')
OUT=Path(__file__).parent
for p in ['common','it/enterprise-sim']:sys.path.insert(0,str(TREE/p))
spec=importlib.util.spec_from_file_location('education_fixture_test',TREE/'tests/test_education_pm_inventory_fixture.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
state=module.EnterpriseState();plan=module.approved(state)
req=dict(skill='skill:schedule-maintenance-scoped',asset='HYD-02',decision='ISOLATED-LOCALE',option='fixture-policy',by='isolated-test',params=dict(plan=plan,task='source policy exercise'))
memory=state.execute(req)
sql=(TREE/'it/supabase/migrations/20261012000058_pm_receipt_korean.sql').read_text(encoding='utf8')
cx=psycopg.connect('postgresql://postgres:hyd-edu-test-only@127.0.0.1:55757/hyd_edu_fixture')
pm=cx.execute('select ent.pm_status_read(null)').fetchone()[0]['records']
parts=cx.execute('select ent.spare_stock_read(null)').fetchone()[0]['records']
asset=next(r for r in pm if r['asset']=='HYD-02')
window=dict(id=asset['night_window_id'],starts_at=asset['night_window_at'],basis='hours_at_next_window')
req['params']['plan']=module.plan(module.source_skill(),dict(pm_context=dict(asset='HYD-02',records=pm,parts=parts)),window)
def execute():return cx.execute('select ent.exec_skill(%s::jsonb)',(json.dumps(req),)).fetchone()[0]
def rows():
    return {t:cx.execute(psycopg.sql.SQL("select coalesce(jsonb_agg(to_jsonb(x) order by to_jsonb(x)::text),'[]'::jsonb) from ent.{} x").format(psycopg.sql.Identifier(t))).fetchone()[0] for t in ['transactions','work_orders','spare_stock','pm_part_reservations','pm_counters']}
try:
    old=execute();assert old['detail']=='Source-scoped maintenance orders registered'
    before=rows();cx.execute(sql);fn=cx.execute("select prosrc from pg_proc where oid='ent.exec_skill(jsonb)'::regprocedure").fetchone()[0]
    assert rows()==before,'Localization migration rewrote prior business data'
    cx.execute(sql);assert rows()==before
    assert execute()==old,'Previously accepted idempotent receipt changed'
    assert cx.execute("select prosrc from pg_proc where oid='ent.exec_skill(jsonb)'::regprocedure").fetchone()[0]==fn
    cx.rollback()
    cx.execute(sql);new=execute()
    assert new['detail']==memory['detail'],'Supabase and Memory producer wording differs'
    assert execute()==new
    reservations=cx.execute('select part_no,qty from ent.pm_part_reservations where work_order=%s order by part_no',(new['ref'],)).fetchall()
    assert dict(reservations)=={'P-PMP-SEAL':1,'P-RTN-FLT':1}
    proof=dict(passed=True,isolated_port=55757,actual_production_function=True,migration_sha256=hashlib.sha256(sql.encode()).hexdigest(),existing_business_rows_unchanged=True,migration_twice_unchanged=True,original_receipt_replay_exact=True,future_receipt_matches_memory=True,future_detail=new['detail'],new_reservations=[dict(part_no=p,qty=float(q)) for p,q in reservations],all_test_effects_rolled_back=True,operating_DB_writes=0,models=0)
    (OUT/'pg-receipt-result.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(proof,ensure_ascii=False))
finally:cx.rollback();cx.close()
