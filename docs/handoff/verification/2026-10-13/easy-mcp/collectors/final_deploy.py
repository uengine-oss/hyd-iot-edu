"""Final deployment under root-owned lock; output never includes environment values."""
from pathlib import Path
import hashlib,json,os,subprocess,time,urllib.request
R=Path('D:/work/study/hyd-iot-edu')
T=R/'.claude/worktrees/codex-portal-20261011'
H=R/'.evidence/easy-mcp-20261013'
D='C:/Users/roede/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
assert (R/'.evidence/LIVE_LOCK').read_text(encoding='utf-8').startswith('root-easy-mcp-20261013 |')
sources=['instances.py','service_parts.py','service_progress.py','procdb.py','instance_mode.py','mcp_oauth.py','main.py']
expected={n:hashlib.sha256((T/'it/process/procsvc'/n).read_bytes()).hexdigest() for n in sources}
def run(args,name):
    p=subprocess.run([D]+args,cwd=T,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace')
    (H/name).write_text(p.stdout+p.stderr,encoding='utf-8')
    if p.returncode:raise RuntimeError(name+' failed')
    return p.stdout
env=os.environ.copy()
env.update(PROCESS_MODE='instance',PROCESS_REPO='pg',AGENT_BRIDGE='off',PROCESS_MEM_LIMIT='768m',TIME_SCALE='20',ENTERPRISE_BACKEND='supabase',WORKER_URL='http://host.docker.internal:8097',HYD_MCP_OAUTH_CALLBACK_URL='http://localhost:8088/api/mcp/connections/callback')
args=['compose','-p','hyd-iot-edu']
for profile in ['ot','backbone','detect','knowledge','agent','enterprise','process','cliagents']:args+=['--profile',profile]
before=run(['inspect','hyd-iot-edu-process-1','hyd-iot-edu-portal-1','--format','{{.Name}} {{.State.StartedAt}} {{.RestartCount}}'],'final-deploy-before.log')
run(args+['build','process'],'final-build.log')
run(args+['up','-d','--no-deps','process'],'final-up.log')
result={'source_sha':expected,'before':before,'health_attempt_errors':[]}
for _ in range(60):
    try:
        with urllib.request.urlopen('http://localhost:8080/healthz',timeout=3) as r:health=json.loads(r.read())
        if not health.get('ok'):raise RuntimeError('not ready')
        result['health']=health;break
    except Exception as exc:result['health_attempt_errors'].append(type(exc).__name__);time.sleep(1)
else:raise RuntimeError('process did not become ready')
container_code="import hashlib,json;from pathlib import Path;names="+repr(sources)+";print(json.dumps({n:hashlib.sha256((Path('/app/procsvc')/n).read_bytes()).hexdigest() for n in names}))"
# Resolve the image package directory through the actual installed module.
container_code=container_code.replace("Path('/app/procsvc')","Path(__import__('procsvc').__file__).parent")
actual=json.loads(run(['exec','hyd-iot-edu-process-1','python','-c',container_code],'final-image-sha.log'))
assert actual==expected,'image/source mismatch'
assert expected=={n:hashlib.sha256((T/'it/process/procsvc'/n).read_bytes()).hexdigest() for n in sources},'source changed during build'
result['image_sha_matches']=True
with urllib.request.urlopen('http://localhost:8088/api/mcp/connections',timeout=5) as r:catalog=json.loads(r.read())
result['connection_count']=len(catalog['connections'])
result['catalog']=catalog['catalog']
assert result['connection_count']==0,'unexpected external account registration'
result['after']=run(['inspect','hyd-iot-edu-process-1','hyd-iot-edu-portal-1','--format','{{.Name}} {{.State.StartedAt}} {{.RestartCount}}'],'final-deploy-after.log')
result['ok']=True
(H/'final-deployment.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'ok':True,'image_sha_matches':True,'connection_count':result['connection_count'],'runtime':health.get('runtime')},ensure_ascii=False))
