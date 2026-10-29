"""오프라인1 가이드의 실제 참조만 묶는다. 정본 HTML/자료를 바이트 그대로 사용."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote
import zipfile,posixpath
ROOT=Path(__file__).resolve().parents[4]
class Links(HTMLParser):
    def __init__(self):super().__init__();self.urls=[]
    def handle_starttag(self,tag,attrs):
        self.urls.extend(v for k,v in attrs if k in ['src','href'] and v)
for course in ['통합반','실전반']:
    base=ROOT/'workspace/강의제작/산출물'/course/'실습/01회차'
    included={base/'오프라인_가이드.html',ROOT/'workspace/강의제작/제작도구/실습시작/index.html',ROOT/'workspace/강의제작/제작도구/실습시작/실습시작.zip'}
    folders=[base/'랩/01일차_실습4_관계그림',base/'랩/01일차_오프라인_모델과질문',ROOT/'workspace/강의제작/산출물/통합반/실습/02회차/랩/02일차_실습3_온톨로지설계']
    for folder in folders:
        included.update(f for f in folder.rglob('*') if f.is_file() and '__pycache__' not in f.parts)
    included.add((base/'랩/01일차_오프라인_모델과질문').with_suffix('.zip'))
    target=base/'오프라인1_가이드.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
        for f in sorted(included):z.write(f,f.relative_to(ROOT).as_posix())
        entry=f'workspace/강의제작/산출물/{course}/실습/01회차/오프라인_가이드.html'
        z.writestr('가이드열기.html',f'<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url={entry}"><a href="{entry}">오프라인1 가이드 열기</a>')
    with zipfile.ZipFile(target) as z:
        names=set(z.namelist())
        for file in names:
            if not file.endswith('.html'):continue
            parser=Links();parser.feed(z.read(file).decode('utf-8-sig'))
            for link in parser.urls:
                url=urlsplit(link)
                if url.scheme or not url.path:continue
                dest=posixpath.normpath(posixpath.join(posixpath.dirname(file),unquote(url.path)))
                assert dest in names,(file,link)
    print(course,'가이드 ZIP',len(names),'파일, 내부 링크 확인')
