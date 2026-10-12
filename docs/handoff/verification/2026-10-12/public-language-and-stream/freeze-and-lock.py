from pathlib import Path
import json,hashlib,re,subprocess,datetime
R=Path('D:/work/study/hyd-iot-edu'); T=R/'.claude/worktrees/codex-portal-20261011'; H=Path(__file__).parent
p=T/'it/portal/www/index.html'; b=p.read_bytes(); b,n=re.subn(rb'flows\.js\?v=[^"\s]+',b'flows.js?v=20261012-mcp-preparation',b); assert n==1; p.write_bytes(b)
old=json.loads((R/'.evidence/google-meeting-import-20261012/source-manifest.json').read_text(encoding='utf8'))
paths=set(old)
changed=subprocess.check_output(['git','diff','--name-only'],cwd=T,text=True).splitlines()
new=subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=T,text=True).splitlines()
paths.update(changed+new)
assert not any(x.startswith(('docs/교재/','.claude/skills/lecture-deck/')) for x in changed+new)
manifest={x:hashlib.sha256((T/x).read_bytes()).hexdigest() for x in sorted(paths) if (T/x).is_file()}
(H/'source-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
(H/'freeze.json').write_text(json.dumps({'count':len(manifest),'changed_paths':changed,'new_paths':new,'cache_bumps':['flows.js']},ensure_ascii=False,indent=2),encoding='utf8')
owner='Codex Sol6.1 '+datetime.datetime.now(datetime.timezone.utc).isoformat()+' public language / MCP preflight deployment and owned draft only; 40 min'
with (R/'.evidence/LIVE_LOCK').open('x',encoding='utf8') as f:f.write(owner+'\n')
(H/'live-lock.json').write_text(json.dumps({'owner':owner},indent=2),encoding='utf8')
print(json.dumps({'source_count':len(manifest),'lock_acquired':True,'changes':len(changed+new)}))
