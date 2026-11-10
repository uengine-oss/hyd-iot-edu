"""학생 랩 ZIP 검사 한 곳. 학생 AI 수행 검증은 아님.

    python verify_packages.py [<ZIP 또는 랩 폴더> …]

1. package-index.json의 ZIP마다 해시 · 시작 파일 · 가이드 링크 · 과제 정답 경계(verify_lab).
2. 학생 ZIP(산출물/*/실습/*/랩/*.zip 전부, 인수를 주면 그것만)마다 check_zip — 랩 폴더와 경로 집합 · 바이트(텍스트는 줄끝을 맞춰)가
   같은가, 강사 대본(/대본/) · 제작 지시 문구 · __pycache__ · .env(TEMPLATES 밖)가 없는가, 빈 틀(.env.example · TEMPLATES의 .env)의
   등호 뒤가 모두 비었는가, ZIP 안 HTML · START.md 링크가 ZIP 안 파일로 풀리는가. ZIP마다 한 줄(통과 · 실패)을 찍고, 실패가 있으면 종료 코드 1. 결과는 작업/검사/package-verification.json.
start_guides/build.py와 lab_package.py도 check_zip · forbidden_hits · link_errors를 부른다.
"""
from pathlib import Path, PurePosixPath
from html.parser import HTMLParser
from collections import Counter
from urllib.parse import unquote,urlsplit
import hashlib,html,json,posixpath,re,sys,zipfile
from build_labs import PICTURE_TYPES, student_photos
from lab_package import PRIVATE, guide_name, outside_guide, student_files, zip_root
from lab_frame import MARK, SHOW_RESULT
from project_layout import errors as project_errors
ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
OUT=ROOT/'workspace/강의제작/산출물'
FORBIDDEN=('제작 참고용','낭독하지 않음','강사 대본','비낭독')   # 제작 지시 문구 — 학생 파일에 있으면 안 된다
# 학생에게 주는 빈 .env 틀(값은 학생이 적는다 — START.md 「코드/.env: 모델 접속」). 동기화가 .env를 빼므로 다른 PC 체크아웃 폴더에는 없다.
TEMPLATES={'실전반/실습/04회차/랩/04일차_실습2_원인추론과점검계획/코드/.env'}
MD_LINK=re.compile(r'\]\(([^)\s]+)\)')
HREF=re.compile(r'href="([^"]+)"')

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

def text_of(data):
    """UTF-8 글이면 문자열, 아니면 None."""
    if b'\0' in data:return None
    try:return data.decode('utf-8-sig')
    except UnicodeDecodeError:return None

def forbidden_hits(files):
    """[(표시 이름, 바이트)] 중 글 파일의 제작 지시 문구."""
    hits=[]
    for label,data in files:
        text=text_of(data)
        if text is None:continue
        for word in FORBIDDEN:
            for n,line in enumerate(text.splitlines(),1):
                if word in line:hits.append(f'{label}:{n}: 제작 지시 문구 「{word}」')
    return hits

def link_errors(files,docs=None):
    """{랩 안 경로: 바이트}에서 docs(기본: 모든 .html과 START.md)의 상대 링크가 같은 묶음 안 파일 · 폴더로 풀리는가."""
    errors=[]
    for name in sorted(files):
        if docs is not None and name not in docs:continue
        if docs is None and not (name.endswith('.html') or name in ('START.md', 'README.md')):continue
        text=text_of(files[name]) or ''
        if name.endswith('.html'):
            parser=Links();parser.feed(text);targets=parser.targets
        else:
            targets=[html.unescape(x) for x in MD_LINK.findall(text)+HREF.findall(text)]
        for link in targets:
            parts=urlsplit(link)
            if parts.scheme or parts.netloc or not parts.path:continue
            target=posixpath.normpath(posixpath.join(posixpath.dirname(name),unquote(parts.path)))
            if target=='..' or target.startswith('../'):errors.append(f'{name}: 랩 폴더 밖 링크 {link}')
            elif target!='.' and target not in files and not any(f.startswith(target.rstrip('/')+'/') for f in files):
                errors.append(f'{name}: 없는 파일 링크 {link}')
    return errors

def same_content(a,b):
    if a==b:return True
    return text_of(a) is not None and text_of(b) is not None and a.replace(b'\r\n',b'\n')==b.replace(b'\r\n',b'\n')

ENV_NAMES=('OPENAI_BASE_URL','LLM_API_KEY','LLM_MODEL')   # 코딩랩.md K-7 — 학생이 받는 접속 세 줄의 이름(.env.example에 셋 다, 값은 빈 채)

def env_template_errors(name,data,need=()):
    """학생이 등호 뒤를 채우는 빈 틀(.env.example · TEMPLATES의 .env)에서 값이 든 줄과, need의 이름 가운데 빠진 것. 값은 학생 코드(llm_client)가 읽는 대로
    앞뒤 공백 · 따옴표를 걷어 본다. 값 자체는 찍지 않는다(키 · 주소일 수 있다)."""
    text=text_of(data)
    if text is None:return [f'{name}: 빈 틀이 글이 아님']
    errors=[];seen=set()
    for n,line in enumerate(text.splitlines(),1):
        line=line.strip()
        if not line or line.startswith('#') or '=' not in line:continue
        key,value=line.split('=',1)
        seen.add(key.strip())
        if value.strip().strip('"\''):errors.append(f'{name}:{n}: 빈 틀에 값이 들어 있음 {key.strip()}=…(키 · 주소가 섞였을 수 있음 — 값을 비운다)')
    missing=[k for k in need if k not in seen]
    if missing:errors.append(f'{name}: 접속 세 줄의 이름이 빠짐 {", ".join(missing)}(코딩랩.md K-7)')
    return errors

def check_zip(zpath,folder,need=(),exclude_names=PRIVATE):
    """학생 ZIP 하나를 랩 폴더와 대조한다. (오류, 참고) 목록을 돌려준다."""
    zpath=Path(zpath);folder=Path(folder);errors=[];notes=[]
    with zipfile.ZipFile(zpath) as z:
        names=[n for n in z.namelist() if not n.endswith('/')]
        try:
            root=zip_root(folder)+'/'
        except ValueError as exc:
            return [str(exc)],notes
        inside=[n for n in names if n.startswith(root)]
        if not inside:
            tops={n.split('/',1)[0] for n in names}
            if len(tops)!=1:return [f'{zpath.name}: ZIP 루트를 정할 수 없음 {sorted(tops)[:3]}'],notes
            root=tops.pop()+'/';inside=names
            notes.append(f'{zpath.name}: 루트 형식이 다름({root} — 다른 ZIP은 NN회차/랩/<랩>/)')
        guide=outside_guide(folder);gname=guide_name(folder) if guide else None
        if guide and gname not in names:errors.append(f'{zpath.name}: 랩 폴더 옆 가이드가 빠짐 {gname}')
        for n in names:
            if n in inside:continue
            if n==gname:
                if not same_content(z.read(n),guide.read_bytes()):errors.append(f'{zpath.name}: 가이드가 {guide.name}과 다름(다시 묶기 필요)')
                continue
            errors.append(f'{zpath.name}: 강사 대본이 들어 있음 {n}' if '/대본/' in '/'+n else f'{zpath.name}: 랩 폴더 밖 항목 {n}')
        packed={n[len(root):]:z.read(n) for n in inside}
        for info in z.infolist():
            if not info.filename.isascii() and not info.flag_bits & 0x800:
                errors.append(f'{zpath.name}: 한글 이름 항목에 UTF-8 표시(0x800)가 없음 {info.filename}')
    try:key=folder.resolve().relative_to(OUT.resolve()).as_posix()
    except ValueError:key=None
    templates={t[len(key)+1:] for t in TEMPLATES if key and t.startswith(key+'/')}
    present={p.relative_to(folder).as_posix():p.read_bytes() for p in student_files(folder,exclude_names)}
    for name,data in packed.items():
        parts=PurePosixPath(name).parts
        if '대본' in parts[:-1]:errors.append(f'{zpath.name}: 강사 대본이 들어 있음 {name}')
        if '__pycache__' in parts or name.endswith('.pyc'):errors.append(f'{zpath.name}: 실행 찌꺼기 {name}')
        if parts[-1]=='.env':
            errors+=[f'{zpath.name}: {e}' for e in env_template_errors(name,data)] if name in templates else [f'{zpath.name}: .env가 들어 있음 {name}']
        elif parts[-1]=='.env.example':
            errors+=[f'{zpath.name}: {e}' for e in env_template_errors(name,data,ENV_NAMES)]
    for name in sorted(templates-set(packed)):
        errors.append(f'{zpath.name}: 학생에게 줄 틀이 빠짐 {name}(이 PC 체크아웃에는 .env가 없다 — 틀이 있는 PC에서 묶는다)')
    only_zip=sorted(n for n in set(packed)-set(present)-templates if PurePosixPath(n).name!='.env')   # .env는 위에서 따로 찍었다
    only_dir=sorted(set(present)-set(packed))
    differ=sorted(n for n in set(packed)&set(present) if not same_content(packed[n],present[n]))
    for label,items in (('ZIP에만 있음',only_zip),('폴더에만 있음',only_dir),('내용 다름(다시 묶기 필요)',differ)):
        if items:errors.append(f'{zpath.name}: {label} {len(items)}개 — '+', '.join(items[:5])+(' …' if len(items)>5 else ''))
    errors+=forbidden_hits((f'{zpath.name}:{name}',data) for name,data in packed.items())
    if 'run.py' in packed and any(n.startswith('app/features/') for n in packed):
        errors += [f'{zpath.name}: {e}' for e in project_errors(packed, root.rstrip('/'))]
    errors+=[f'{zpath.name} 안: {e}' for e in link_errors(packed)]
    for name in need:
        if name not in packed:errors.append(f'{zpath.name}: 풀었을 때 {name} 없음')
    return errors,notes

START_STEP=re.compile(r'^\d+\. \*\*(.+?)\*\* — ',re.M)

def verify_outside_guide(item,z,names,base):
    """코딩 랩(guide_file 있음): 가이드는 랩 폴더 밖 한 파일이고 ZIP에는 랩 폴더 옆 그 자리에 같은 바이트로 들어 있다
    (해시 · 단계 이름 = START 「진행 단계」 · 정답 토글 · 상대 링크 0). 랩 폴더 안에는 가이드가 없고 결과 화면 두 파일이 있으며
    결과/는 README와 빈 틀뿐(공용틀_계약 2 · 3 · 4, K-7)."""
    spec=item['guide_file'];guide=ROOT/spec['path']
    assert hashlib.sha256(guide.read_bytes()).hexdigest()==spec['sha256'],(item['id'],'가이드 해시 불일치')
    root=base.rstrip('/')
    sibling=(root.rsplit('/',1)[0]+'/' if '/' in root else '')+guide.name
    assert sibling in names and z.read(sibling)==guide.read_bytes(),(item['id'],'ZIP의 랩 폴더 옆 가이드가 없거나 다름',sibling)
    for n in names:
        if n.startswith(base):
            assert PurePosixPath(n).name not in ('guide.html','안내.html') and not n.endswith('_guide.html'),(item['id'],'랩 폴더 안에 가이드',n)
    project=item.get('layout')=='project'
    if project:
        files={n[len(base):]:z.read(n) for n in names if n.startswith(base) and not n.endswith('/')}
        errors=project_errors(files, root)
        assert not errors,(item['id'],errors)
    else:
        for file in ['START.md','결과/README.md','show_result.py','lab_steps.py']:
            assert base+file in names,(item['id'],file)
        assert z.read(base+'show_result.py')==SHOW_RESULT.encode('utf-8'),(item['id'],'show_result.py가 공용 원본과 다름')
        for n in names:
            if n.startswith(base+'결과/') and not n.endswith('/'):
                rest=n[len(base):]
                assert rest!='결과/보기.html' and not rest.startswith('결과/.보기_이전'),(item['id'],'처음 ZIP에 결과 화면',rest)
                head=' '.join((text_of(z.read(n)) or '').splitlines()[:3])
                assert rest=='결과/README.md' or MARK in head,(item['id'],'결과/에 빈 틀이 아닌 파일',rest)
    text=guide.read_text(encoding='utf-8')
    headings=[html.unescape(h) for h in re.findall(r'<section id="s\d+"><h2>\d+ (.*?)</h2>', text)]
    steps=item.get('guide_steps',[]) if project else START_STEP.findall((text_of(z.read(base+'START.md')) or '').split('## 진행 단계',1)[-1].split('\n## ',1)[0])
    assert steps and headings==steps,(item['id'],'가이드 절과 랩 정의의 진행 단계가 다름',headings,steps)
    assert '<details class="answer">' in text,(item['id'],'정답 보기 토글 없음')
    parser=Links();parser.feed(text)
    for link in parser.targets:
        parts=urlsplit(link)
        assert parts.scheme or not parts.path,(item['id'],'폴더 밖 가이드의 상대 링크(폴더 이름이 바뀌어 풀리지 않음)',link)
    assert not parser.images,(item['id'],'폴더 밖 가이드에 사진 — 싣는 길이 아직 없음')

def verify_lab(item):
    archive=ROOT/item['path']
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==item['sha256']
    with zipfile.ZipFile(archive) as z:
        names=z.namelist();base=item['folder']+'/'
        if item.get('guide_file'):
            verify_outside_guide(item,z,names,base)
            assert not any(Path(x).name=='.env' or '__pycache__' in x for x in names)
            project=item.get('layout')=='project'
            input_dir='data/model/' if project else '입력/'
            changes_dir='data/changes/' if project else '입력/자료_변경분/'
            if '-02-' in item['id']:
                for file in ['결과/schema.json','결과/graph.json','offline_load.py']:assert base+file not in names,(item['id'],file)
                assert not any(Path(x).name in ('기대답.json','session2_검증.json') or '/갈래B/' in x for x in names),(item['id'],'강사 기대 답 포함')
            if item['id'].endswith('-02-graph'):assert base+input_dir+'graph.json' in names,(item['id'],input_dir+'graph.json')
            if item['id']=='integrated-02-graph':
                assert any(x.startswith(base+changes_dir) for x in names),(item['id'],'수정본 없음')
            if item['id']=='practical-02-ontology':
                previous=json.loads(z.read(base+input_dir+'graph.json'))
                assert not any('Supplier' in n['labels'] for n in previous['nodes'])
            return {'id':item['id'],'sha256':item['sha256'],'files':len(names),'guide':'outside','solution_boundary':'pass'}
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
        if item['id']=='integrated-02-graph':   # 수정본 반영은 통합반 실습4 행에만 있다(실전반 23행에는 없다)
            assert any(x.startswith(base+'입력/자료_변경분/') for x in names),(item['id'],'수정본 없음')
        if item['id'].startswith(('integrated-02-','practical-02-')) and item['id'].endswith(('-ontology','-graph')):
            assert not any(Path(x).name in ('기대답.json','session2_검증.json') or '/갈래B/' in x for x in names),(item['id'],'강사 기대 답 포함')
            guide=z.read(base+'guide.html')
            assert z.read(base+'안내.html') == guide, (item['id'],'가이드 판본 불일치')
            rules={z.read(base+n) for n in ('AGENTS.md','CLAUDE.md','.github/copilot-instructions.md')}
            assert len(rules)==1, (item['id'],'작업 규칙 세 파일이 다름')
            text=guide.decode('utf-8')
            headings=[html.unescape(h) for h in re.findall(r'<section id="s\d+"><h2>\d+ (.*?)</h2>', text)]   # 가이드의 단계 이름
            photos = student_photos(archive.with_suffix(''), json.loads((HERE/'capture-provenance.json').read_text(encoding='utf-8')), headings)
            assert {n[len(base):] for n in names if n.startswith(base+'images/') or Path(n).suffix.lower() in PICTURE_TYPES} == set(photos), item['id']
            photo_links=Links()
            photo_links.feed(text)
            expected=Counter((f's{headings.index(record["section"])+1}',name) for name,record in photos.items())
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

def student_zips(args):
    if not args:return sorted(OUT.glob('*/실습/*/랩/*.zip'))
    paths=[Path(a).resolve() for a in args]
    return [p if p.suffix=='.zip' else p.parent/(p.name+'.zip') for p in paths]

def main(argv):
    items = json.loads((HERE/'package-index.json').read_text(encoding='utf-8'))['labs']
    if argv:
        selected={p.resolve() for p in student_zips(argv)}
        items=[item for item in items if (ROOT/item['path']).resolve() in selected]
    records = [verify_lab(item) for item in items]
    for course in ([] if argv else ['통합반','실전반']):
        guide=ROOT/'workspace/강의제작/산출물'/course/'실습/01회차/오프라인_가이드.html'
        parser=Links();parser.feed(guide.read_text(encoding='utf-8'))
        for link in parser.targets:
            path=urlsplit(link)
            if path.scheme or not path.path:continue
            assert (guide.parent/unquote(path.path)).resolve().exists(),link
    print(f'package-index {len(records)}개 ZIP: 해시·시작 파일·가이드 링크·과제 정답 경계 통과.' + ('' if argv else ' 오프라인 가이드 링크 통과.'))
    results=[];failed=0
    for zpath in student_zips(argv):
        folder=zpath.parent/zpath.stem
        label=zpath.relative_to(OUT).as_posix() if zpath.is_relative_to(OUT) else str(zpath)
        if not zpath.is_file() or not folder.is_dir():
            errors,notes=[f'{label}: ZIP 또는 랩 폴더 없음'],[]
        else:
            errors,notes=check_zip(zpath,folder)
        failed+=bool(errors)
        print(f'{"실패" if errors else "통과"}({len(errors)})  {label}'+(f'  [{"; ".join(notes)}]' if notes else ''))
        for e in errors:print('    오류:',e)
        results.append({'zip':label,'result':'실패' if errors else '통과','errors':errors,'notes':notes})
    dest=ROOT/'작업/검사/package-verification.json';dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps({'package_index':records,'student_zips':results},ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'학생 ZIP {len(results)}개: 통과 {sum(r["result"]=="통과" for r in results)}, 실패 {failed}')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
