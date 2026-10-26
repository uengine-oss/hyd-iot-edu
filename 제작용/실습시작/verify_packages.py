"""배포 ZIP·해시·가이드 내부 링크·정답 경계 검증. 학생 AI 수행 검증은 아님."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import unquote,urlsplit
import hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
class Links(HTMLParser):
    def __init__(self):super().__init__();self.targets=[]
    def handle_starttag(self,tag,attrs):
        for key,value in attrs:
            if key in ['src','href'] and value:self.targets.append(value)
records=[]
for item in json.loads((HERE/'package-index.json').read_text(encoding='utf-8'))['labs']:
    archive=ROOT/item['path']
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==item['sha256']
    with zipfile.ZipFile(archive) as z:
        names=z.namelist();base=item['folder']+'/'
        for file in ['START.md','guide.html','결과/README.md']:assert base+file in names,(item['id'],file)
        assert not any(Path(x).name=='.env' or '__pycache__' in x for x in names)
        if '-02-' in item['id']:
            for file in ['결과/schema.json','결과/graph.json','결과/load.cypher','offline_load.py']:assert base+file not in names,(item['id'],file)
        if item['id'].endswith('-graph'):assert base+'입력/graph.json' in names
        if item['id']=='practical-02-ontology':
            previous=json.loads(z.read(base+'입력/graph.json'))
            assert not any('Supplier' in n['labels'] for n in previous['nodes'])
        parser=Links();parser.feed(z.read(base+'guide.html').decode('utf-8'))
        for link in parser.targets:
            path=urlsplit(link)
            if path.scheme or not path.path:continue
            assert base+unquote(path.path) in names,(item['id'],link)
    records.append({'id':item['id'],'sha256':item['sha256'],'files':len(names),'links':'pass','solution_boundary':'pass'})
for course in ['통합반','실전반']:
    guide=ROOT/'산출물'/course/'실습/01회차/오프라인_가이드.html'
    parser=Links();parser.feed(guide.read_text(encoding='utf-8'))
    for link in parser.targets:
        path=urlsplit(link)
        if path.scheme or not path.path:continue
        assert (guide.parent/unquote(path.path)).resolve().exists(),link
dest=ROOT/'.evidence/practice-20261026/package-verification.json'
dest.write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
print(f'{len(records)}개 ZIP: 해시·시작 파일·가이드 링크·과제 정답 경계 통과. 오프라인 가이드 링크 통과.')
