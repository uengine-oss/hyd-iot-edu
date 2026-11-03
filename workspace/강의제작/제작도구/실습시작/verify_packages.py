"""배포 ZIP·해시·가이드 내부 링크·정답 경계 검증. 학생 AI 수행 검증은 아님."""
from pathlib import Path
from html.parser import HTMLParser
from collections import Counter
from urllib.parse import unquote,urlsplit
import hashlib,json,zipfile
from build_labs import GUIDE_HEADINGS, PICTURE_TYPES, student_photos
ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.targets=[]
        self.images=[]
        self.sections=[]
    def handle_starttag(self,tag,attrs):
        if tag=='section':
            self.sections.append(dict(attrs).get('id'))
        if tag=='img':
            self.images.append((self.sections[-1] if self.sections else None,dict(attrs).get('src')))
        for key,value in attrs:
            if key in ['src','href'] and value:self.targets.append(value)
    def handle_endtag(self,tag):
        if tag=='section' and self.sections:
            self.sections.pop()

def verify_lab(item):
    archive=ROOT/item['path']
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==item['sha256']
    with zipfile.ZipFile(archive) as z:
        names=z.namelist();base=item['folder']+'/'
        required = ['guide.html']
        if item.get('entry') == 'neo4j':
            required.extend(['prepare_example.py','lab_db.py','예제_적재.cypher'])
            assert not any(n.startswith(base+'결과/') or Path(n).name in ('AGENTS.md','CLAUDE.md','START.md','조회_기록.md','조회_작성.cypher') for n in names)
        elif item.get('entry') != 'guide':
            required.append('START.md')
        if item.get('entry') not in ('guide','neo4j'):
            required.append('결과/README.md')
        for file in required:
            assert base + file in names, (item['id'], file)
        assert not any(Path(x).name=='.env' or '__pycache__' in x for x in names)
        if '-02-' in item['id']:
            for file in ['결과/schema.json','결과/graph.json','결과/load.cypher','offline_load.py']:assert base+file not in names,(item['id'],file)
        if item['id'].endswith('-graph'):assert base+'입력/graph.json' in names
        if item['id'] in ('integrated-02-graph','practical-02-graph'):
            assert any(x.startswith(base+'입력/자료_변경분/') for x in names),(item['id'],'수정본 없음')
        if item['id'].startswith(('integrated-02-','practical-02-')) and item['id'].endswith(('-ontology','-graph')):
            assert not any(Path(x).name in ('기대답.json','session2_검증.json') or '/갈래B/' in x for x in names),(item['id'],'강사 기대 답 포함')
            photos = student_photos(archive.with_suffix(''), json.loads((HERE/'capture-provenance.json').read_text(encoding='utf-8')))
            assert {n[len(base):] for n in names if n.startswith(base+'images/') or Path(n).suffix.lower() in PICTURE_TYPES} == set(photos), item['id']
            photo_links=Links()
            guide=z.read(base+'guide.html')
            assert z.read(base+'안내.html') == guide, (item['id'],'가이드 판본 불일치')
            photo_links.feed(guide.decode('utf-8'))
            expected=Counter((f's{GUIDE_HEADINGS.index(record["section"])+1}',name) for name,record in photos.items())
            assert Counter(photo_links.images)==expected, (item['id'],'절별 사진 목록 불일치')
            for name, record in photos.items():
                assert hashlib.sha256(z.read(base+name)).hexdigest()==record['sha256'], (item['id'],name)
        if item['id']=='practical-02-ontology':
            previous=json.loads(z.read(base+'입력/graph.json'))
            assert not any('Supplier' in n['labels'] for n in previous['nodes'])
        parser=Links();parser.feed(z.read(base+'guide.html').decode('utf-8'))
        for link in parser.targets:
            path=urlsplit(link)
            if path.scheme or not path.path:continue
            assert base+unquote(path.path) in names,(item['id'],link)
    return {'id':item['id'],'sha256':item['sha256'],'files':len(names),'links':'pass','solution_boundary':'pass'}


def main():
    items = json.loads((HERE/'package-index.json').read_text(encoding='utf-8'))['labs']
    records = [verify_lab(item) for item in items]
    for course in ['통합반','실전반']:
        guide=ROOT/'workspace/강의제작/산출물'/course/'실습/01회차/오프라인_가이드.html'
        parser=Links();parser.feed(guide.read_text(encoding='utf-8'))
        for link in parser.targets:
            path=urlsplit(link)
            if path.scheme or not path.path:continue
            assert (guide.parent/unquote(path.path)).resolve().exists(),link
    dest=ROOT/'작업/검사/package-verification.json';dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'{len(records)}개 ZIP: 해시·시작 파일·가이드 링크·과제 정답 경계 통과. 오프라인 가이드 링크 통과.')


if __name__ == '__main__':
    main()
