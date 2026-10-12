from pathlib import Path
import json,hashlib,re
H=Path(__file__).parent;R=H.parents[1];T=R/'.claude/worktrees/codex-portal-20261011'
paths=['it/portal/www/main.js','tests/js/test_public_display_language.js','it/portal/www/index.html']
p=T/paths[-1];b=p.read_bytes();b,n=re.subn(rb'main\.js\?v=[^"\s]+',b'main.js?v=20261013-node-labels',b);assert n==1;p.write_bytes(b)
for file in ['source-manifest','capture-manifest']:
    p=H/(file+'.json');(H/(file+'-before-main.json')).write_bytes(p.read_bytes());m=json.loads(p.read_text(encoding='utf8'))
    for key in paths:m[key]=hashlib.sha256((T/key).read_bytes()).hexdigest()
    p.write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf8')
(H/'main-freeze.json').write_text(json.dumps({'paths':paths,'backend_unchanged':True,'prior_B_C_agent_5_png_reused':True,'owned_warning_1_png_reused':True,'new_capture_scope':['main','whatif','reference_comparison']},indent=2),encoding='utf8')
print('Main consumer freeze ready; source819/capture19; prior6PNG preserved')
