from pathlib import Path
import subprocess,json,hashlib
import psycopg
T=Path('D:/work/study/hyd-iot-edu/.claude/worktrees/codex-portal-20261011')
O=Path(__file__).parent
container='hyd-pm-receipt-pg-20261012'
cx=psycopg.connect('postgresql://postgres:hyd-edu-test-only@127.0.0.1:55757/hyd_edu_fixture',autocommit=True)
def sql(body,name):
    try:
        cx.execute(body)
        with (O/'bootstrap.log').open('a',encoding='utf8') as f:f.write(name+' PASS\n')
    except Exception as e:
        with (O/'bootstrap.log').open('a',encoding='utf8') as f:f.write(name+' FAIL '+str(e)+'\n')
        raise
sql('create role anon;create role authenticated;create role service_role;','isolated_roles')
names=['20261003000002','20261004000003','20261004000006','20261005000015','20261007000017','20261007000019','20261007000020','20261007000022','20261008000023','20261008000025','20261008000037','20261009000045','20261009000046','20261009000047','20261012000054','20261012000056','20261012000057']
sources=[]
for prefix in names:
    p=next((T/'it/supabase/migrations').glob(prefix+'*'))
    sources.append({'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    sql(p.read_text(encoding='utf8'),p.name)
seed=(T/'it/supabase/seed.sql').read_text(encoding='utf8').split('insert into public.tenants')[0]
(O/'enterprise-seed.sql').write_text(seed,encoding='utf8')
sql(seed+'\nselect ent.reanchor_scenario_times();','enterprise-only source seed')
(O/'bootstrap.json').write_text(json.dumps({'container':container,'scope':'Isolated tmpfs PG15 only, original ent migrations and enterprise-only seed slice; no process/public seed or live data','sources':sources},indent=2),encoding='utf8')
