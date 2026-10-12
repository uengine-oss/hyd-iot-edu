from pathlib import Path
import json,hashlib,re
H=Path(__file__).parent;R=H.parents[1];T=R/'.claude/worktrees/codex-portal-20261011'
old=json.loads((H/'source-manifest.json').read_text(encoding='utf8'));(H/'source-manifest-before-consumer.json').write_text(json.dumps(old,ensure_ascii=False,indent=2),encoding='utf8')
p=T/'it/portal/www/index.html';b=p.read_bytes();b,n=re.subn(rb'caseRecord\.js\?v=[^"\s]+',b'caseRecord.js?v=20261013-process-labels',b);assert n==1;p.write_bytes(b)
changed=['it/portal/www/caseRecord.js','tests/js/test_public_display_language.js','it/portal/www/index.html']
for key in changed:old[key]=hashlib.sha256((T/key).read_bytes()).hexdigest()
(H/'source-manifest.json').write_text(json.dumps(old,ensure_ascii=False,indent=2),encoding='utf8')
narrow=json.loads((H/'capture-manifest.json').read_text(encoding='utf8'))
for key in changed:narrow[key]=old[key]
(H/'capture-manifest-before-consumer.json').write_bytes((H/'capture-manifest.json').read_bytes())
(H/'capture-manifest.json').write_text(json.dumps(narrow,ensure_ascii=False,indent=2),encoding='utf8')
(H/'consumer-freeze.json').write_text(json.dumps({'changed':changed,'source_count':len(old),'capture_count':len(narrow),'backend_changed':False,'served_bind_mount':True,'earlier_owned_warning_proof':'Before consumer-only change; flow diagnostic source unchanged'},indent=2),encoding='utf8')
print(json.dumps({'source':len(old),'capture':len(narrow),'updated':changed}))
