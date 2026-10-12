from pathlib import Path
import hashlib,json,socket,subprocess,urllib.request
R=Path('D:/work/study/hyd-iot-edu');T=R/'.claude/worktrees/codex-portal-20261011';H=R/'.evidence/easy-mcp-20261013'
D='C:/Users/roede/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
assert (R/'.evidence/LIVE_LOCK').read_text(encoding='utf-8').startswith('root-easy-mcp-20261013 |')
def docker(*args):
    p=subprocess.run([D,*args],capture_output=True,text=True,encoding='utf-8',errors='replace')
    if p.returncode:raise RuntimeError(p.stderr)
    return p.stdout
name='hyd-system-progress-20261013'
label=docker('inspect',name,'--format','{{index .Config.Labels "hyd.owner"}}').strip()
assert label=='root-easy-mcp-20261013'
docker('stop',name);docker('rm',name)
containers=[json.loads(line) for line in docker('ps','--format','{{json .}}').splitlines()]
proof={'removed_owned_tmpfs_container':name,'project_volumes_deleted':False,'running_containers':[{'name':c['Names'],'status':c['Status']} for c in containers],'ports':{}}
assert len(containers)==29 and not any(c['Names']==name for c in containers)
for port in (55757,8764,8765,8766,8767,8097):
    with socket.socket() as sock:
        sock.settimeout(.25);opened=sock.connect_ex(('127.0.0.1',port))==0
    proof['ports'][str(port)]={'open':opened};assert not opened,str(port)+' remained open'
with urllib.request.urlopen('http://localhost:8080/healthz',timeout=5) as r:proof['health']=json.loads(r.read())
assert proof['health']['ok'] and proof['health']['runtime']['ready']
with urllib.request.urlopen('http://localhost:8080/api/mcp/servers',timeout=5) as r:servers=json.loads(r.read())
proof['registered_server_names']=[s['name'] for s in servers['servers']]
before=json.loads((H/'deployment.json').read_text(encoding='utf-8'))['before_server_names']
assert sorted(proof['registered_server_names'])==sorted(before)
proof['source_and_served_sha']={}
for name in ('mcpConnections.js','mcpConnections.css','mcp.js','index.html'):
    source=(T/'it/portal/www'/name).read_bytes()
    with urllib.request.urlopen('http://localhost:8088/'+name,timeout=5) as r:served=r.read()
    assert served==source,name+' served different bytes'
    proof['source_and_served_sha'][name]=hashlib.sha256(source).hexdigest()
proof['container_stability']=docker('inspect','hyd-iot-edu-process-1','hyd-iot-edu-portal-1','--format','{{.Name}} {{.State.StartedAt}} {{.RestartCount}}')
proof['ok']=True
(H/'final-cleanup.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'ok':True,'running_containers':len(containers),'servers':len(before),'owned_helpers_remaining':0}))
