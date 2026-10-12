import hashlib,json,re
from pathlib import Path
T=Path('D:/work/study/hyd-iot-edu/.claude/worktrees/codex-portal-20261011');H=Path(__file__).parent
index=T/'it/portal/www/index.html'
original=index.read_bytes();current=original
files=['ui.js','enterprise.js','main.js','hitl.js','plainWords.js','caseRecord.js','agents.js','whatif.js','compare.js']
for name in files:
    pattern=rb'src="'+re.escape(name.encode())+rb'\?v=[^"\r\n]+"'
    current,count=re.subn(pattern,('src="'+name+'?v=20261012-public-language"').encode(),current)
    assert count==1,name
index.write_bytes(current)
(H/'root-cache-version.json').write_text(json.dumps({'files':files,'sha256':hashlib.sha256(current).hexdigest(),'scope':'cache only after label implementation freeze; no CSS/color change'},ensure_ascii=False,indent=2),encoding='utf8')
print('Cache refreshed for nine changed UI files')
