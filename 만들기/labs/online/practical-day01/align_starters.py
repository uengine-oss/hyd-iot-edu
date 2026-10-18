from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[4]
BASE=ROOT/'산출물/실습/실전반_온라인'
for folder in BASE.glob('01일차_실습*'):
    p=folder/'가이드.html';text=p.read_text('utf-8')
    match=re.search(r'<section><h2>시작 · 실습 자료 다운로드와 작업 공간</h2>.*?</section>',text,re.S)
    assert match,p
    start=match.group(0);text=text[:match.start()]+text[match.end():]
    text=re.sub(r'<section\b',lambda m:start+m.group(0),text,count=1)
    p.write_text(text,encoding='utf-8')
print('All four guides start with downloading and workspace setup')
