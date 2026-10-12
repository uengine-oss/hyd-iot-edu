import hashlib,json,os
from pathlib import Path
from datetime import datetime,timezone
from urllib.request import urlopen
import psycopg

ROOT=Path('D:/work/study/hyd-iot-edu')
TREE=ROOT/'.claude/worktrees/codex-portal-20261011'
OUT=Path(__file__).parent
LOCK=ROOT/'.evidence/LIVE_LOCK'
B='c3_pm.d99ee952-f943-42fd-ba53-745b569522f7'
C='c3_spare.01a60b8d-284d-422b-96db-113dda3dd43f'
def save(name,data):
    (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2,default=str),encoding='utf8')
def get(path):
    with urlopen('http://127.0.0.1:8080'+path,timeout=30) as r:return json.load(r)
owner='codex Sol6.1 '+datetime.now(timezone.utc).isoformat()+' final remaining work B education initializer and actual B continuation; expected 60 minutes'
with LOCK.open('x',encoding='utf8') as f:f.write(owner+'\n')
save('live-lock-acquired.json',dict(owner=owner))
before={k:get('/api/instances/'+v) for k,v in {'B':B,'C':C}.items()}
save('cases-before-fixture.json',before)
save('eligible-tasks-before-fixture.json',get('/api/todolist?status=IN_PROGRESS&agent_orch=cliagents&limit=500'))
sqlpath=TREE/'it/supabase/migrations/20261012000057_b_return_filter_fixture.sql'
cx=psycopg.connect('postgresql://postgres:postgres@127.0.0.1:54322/postgres')
def snapshot():
    tables=[x[0] for x in cx.execute("select tablename from pg_tables where schemaname='ent' order by tablename").fetchall()]
    return {t:cx.execute(psycopg.sql.SQL("select coalesce(jsonb_agg(to_jsonb(x) order by to_jsonb(x)::text),'[]'::jsonb) from ent.{} x").format(psycopg.sql.Identifier(t))).fetchone()[0] for t in tables}
try:
    old=snapshot();save('erp-before-fixture.json',old)
    cx.execute(sqlpath.read_text(encoding='utf8'))
    new=snapshot()
    stripped={t:[r for r in rows if not(t in ['parts','spare_stock'] and r.get('part_no')=='P-RTN-FLT')] for t,rows in new.items()}
    old_stripped={t:[r for r in rows if not(t in ['parts','spare_stock'] and r.get('part_no')=='P-RTN-FLT')] for t,rows in old.items()}
    assert stripped==old_stripped,'Existing educational ERP data changed'
    cx.execute(sqlpath.read_text(encoding='utf8'))
    assert snapshot()==new,'Repeated migration changed data'
    cx.commit();save('erp-after-fixture.json',new)
finally:cx.close()
after={k:get('/api/instances/'+v) for k,v in {'B':B,'C':C}.items()}
save('cases-after-fixture.json',after)
assert before==after,'Existing process history changed'
proof=dict(fixture_version='B-ERP-20261012-v1',migration=str(sqlpath.relative_to(TREE)),sha256=hashlib.sha256(sqlpath.read_bytes()).hexdigest(),existing_erp_rows_unchanged=True,repeated_migration_unchanged=True,existing_B_C_history_unchanged=True,new_filter_master=next(x for x in new['parts'] if x['part_no']=='P-RTN-FLT'),new_filter_stock=next(x for x in new['spare_stock'] if x['part_no']=='P-RTN-FLT'),at=datetime.now(timezone.utc).isoformat())
save('official-fixture-applied.json',proof)
print(json.dumps(proof,ensure_ascii=False))
