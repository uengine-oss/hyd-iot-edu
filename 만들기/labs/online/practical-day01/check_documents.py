"""실습을 실행하지 않고 배포 문서·화면 자리·보호 파일만 검사한다."""
from pathlib import Path
from html.parser import HTMLParser
import ast, hashlib, json, re, zipfile

ROOT=Path(__file__).resolve().parents[4]
BASE=ROOT/'산출물/실습/실전반_온라인'
class GuideParser(HTMLParser):
    def __init__(self):super().__init__();self.shots=[];self.prompts=0;self.links=[]
    def handle_starttag(self,tag,attrs):
        values=dict(attrs)
        if 'data-shot' in values:self.shots.append(values['data-shot'])
        if tag=='details' and values.get('class')!='result-reference':self.prompts+=1
        if tag=='link' and 'href' in values:self.links.append(values['href'])

report={'live_practice_executed':False,'guides':[]}
for folder in sorted(BASE.glob('01일차_실습*')):
    p=folder/'가이드.html'; parser=GuideParser();parser.feed(p.read_text('utf-8'))
    assert len(parser.shots)==len(set(parser.shots))
    assert len(parser.shots)>=5 and parser.prompts>=4
    for link in parser.links:assert (folder/link).exists(),link
    shots=(folder/'채울_화면.md').read_text('utf-8')
    for sid in parser.shots:assert sid in shots,sid
    report['guides'].append({'folder':folder.name,'screen_slots':parser.shots,'prompt_toggles':parser.prompts})
assert len(report['guides'])==4
for p in (BASE/'01일차_실습3_기록추적/코드').glob('*.py'):ast.parse(p.read_text('utf-8'))
report['lab_python_syntax']='passed; no execution'
before=json.loads((ROOT/'.evidence/practical01/protected-before.json').read_text('utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
changed=[name for name,digest in before['workspace'].items() if sha(ROOT/name)!=digest]
assert not changed,changed
report['workspace_protected_unchanged']=len(before['workspace'])
with zipfile.ZipFile(ROOT/'산출물/교재/PPTX/실전반_온라인/실전반_01일차.pptx') as current, zipfile.ZipFile(ROOT/'.evidence/practical01/output/산출물/교재/PPTX/실전반_온라인/실전반_01일차.pptx') as baseline:
    for name in baseline.namelist():
        if not re.fullmatch(r'ppt/notesSlides/notesSlide\d+\.xml',name) and name not in [f'ppt/slides/slide{n}.xml' for n in [43,45,47]]:
            assert baseline.read(name)==current.read(name),name
report['theory_pptx_except_notes_and_reviewed_43_45_47_unchanged']=True
(ROOT/'.evidence/practical01/document-only-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'guides':len(report['guides']),'screen_slots':sum(len(g['screen_slots']) for g in report['guides']),'prompt_toggles':sum(g['prompt_toggles'] for g in report['guides']),'protected_unchanged':len(before['workspace'])},ensure_ascii=False))
