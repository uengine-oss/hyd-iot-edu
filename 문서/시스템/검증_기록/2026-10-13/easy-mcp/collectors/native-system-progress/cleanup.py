import json,sys
from pathlib import Path
sys.path[:0]=['D:/work/study/hyd-iot-edu/.claude/worktrees/codex-portal-20261011/it/process','D:/work/study/hyd-iot-edu/.claude/worktrees/codex-portal-20261011/common']
from procsvc import procdb
out=Path(__file__).parent
repo=procdb.PgRepo('postgresql://hyd_test:isolated-progress-test@127.0.0.1:55757/hyd_system_progress_test')
proof=[]
for path in [out/'first-wrapper-layout/result.json',out/'result.json']:
    if not path.exists():continue
    tenant=json.loads(path.read_text(encoding='utf-8'))['tenant']
    assert tenant.startswith('native-progress-')
    if any(p['tenant']==tenant for p in proof):continue
    with repo._conn() as c:
        c.execute('delete from events where proc_inst_id in(select proc_inst_id from bpm_proc_inst where tenant_id=%s)',(tenant,))
        c.execute('delete from bpm_proc_inst where tenant_id=%s',(tenant,))
        c.execute('delete from tenants where id=%s',(tenant,))
        left=c.execute('select count(*) n from tenants where id=%s',(tenant,)).fetchone()['n']
        assert left==0
    proof.append({'tenant':tenant,'remaining_tenants':left})
(out/'cleanup-result.json').write_text(json.dumps({'ok':True,'owned_only':proof},indent=2),encoding='utf-8')
