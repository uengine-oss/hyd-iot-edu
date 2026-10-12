import json,hashlib
from pathlib import Path
from urllib.request import urlopen
import psycopg
OUT=Path(__file__).parent
TREE=OUT.parent.parent/'.claude/worktrees/codex-portal-20261011'
assert (OUT.parent/'LIVE_LOCK').read_text(encoding='utf8').startswith('codex Sol6.1')
assert json.loads((OUT/'ui-positive-fix/pg-receipt-result.json').read_text(encoding='utf8'))['passed']
def save(name,data):(OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2,default=str),encoding='utf8')
def case():
    with urlopen('http://127.0.0.1:8080/api/instances/c3_pm.d99ee952-f943-42fd-ba53-745b569522f7',timeout=30) as r:return json.load(r)
path=TREE/'it/supabase/migrations/20261012000058_pm_receipt_korean.sql'
sql=path.read_text(encoding='utf8')
base=(TREE/'it/supabase/migrations/20261012000056_pm_scoped_schedule.sql').read_text(encoding='utf8').split('create or replace function ent.exec_skill',1)[1].split('$$')[1]
oldcase=case()
with psycopg.connect('postgresql://postgres:postgres@127.0.0.1:54322/postgres') as cx:
    def snapshot():
        names=[r[0] for r in cx.execute("select tablename from pg_tables where schemaname='ent' order by tablename").fetchall()]
        return {t:cx.execute(psycopg.sql.SQL("select coalesce(jsonb_agg(to_jsonb(x) order by to_jsonb(x)::text),'[]'::jsonb) from ent.{} x").format(psycopg.sql.Identifier(t))).fetchone()[0] for t in names}
    before=snapshot()
    original=cx.execute("select prosrc from pg_proc where oid='ent.exec_skill(jsonb)'::regprocedure").fetchone()[0]
    assert original==base,'Operating function differs from reviewed 056 baseline'
    cx.execute(sql)
    localized=cx.execute("select prosrc from pg_proc where oid='ent.exec_skill(jsonb)'::regprocedure").fetchone()[0]
    assert localized==sql.split('$$')[1]
    assert snapshot()==before,'Localization migration changed prior ERP rows'
    cx.execute(sql);assert snapshot()==before
    cx.commit()
assert case()==oldcase,'Localization rewrote stored original process report'
save('receipt-localization-applied.json',dict(migration=str(path.relative_to(TREE)),file_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),executed_sql_sha256=hashlib.sha256(sql.encode()).hexdigest(),prior_function_matches_reviewed_056=True,existing_ent_rows_exact=True,existing_B_case_exact=True,repeated_migration_unchanged=True,past_SMTP_resent=0,new_business_runs=0,new_LLM_runs=0))
print('Migration058 applied; existing ERP/process records untouched, no business or AI rerun')
