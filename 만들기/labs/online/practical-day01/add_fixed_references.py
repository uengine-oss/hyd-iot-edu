"""공통 교재 문장을 고치지 않고 실습에 필요한 장의 화면 원문을 발췌한다."""
from pathlib import Path
import re, hashlib

ROOT=Path(__file__).resolve().parents[4]
BASE=ROOT/'산출물/실습/실전반_온라인'
deck=ROOT/'만들기/decks/practical/day01/실전반_01일차.md'
text=deck.read_text('utf-8')
blocks={int(re.match(r'## SLIDE (\d+)',b)[1]):b for b in re.split(r'(?=^## SLIDE )',text,flags=re.M)[1:]}
groups={1:list(range(4,10)),2:[38,40,41,43],3:[37,38,39,45],4:[49,50,64,65,67,68,71]}
for n,folder in enumerate(sorted(BASE.glob('01일차_실습*')),1):
    out=['# 공통 교재 화면 원문 발췌','', '실습에서 다시 확인할 교재 범위다. 문장을 고치지 않고 해당 장의 화면 내용을 가져왔다. 코드 실행 결과가 아니다. 그림 자체는 공통 PPTX의 같은 장을 참조한다. 실습의 10월14일 기록과 교재 예시 사건의 숫자를 섞지 않는다.','']
    for slide in groups[n]:
        block=blocks[slide]
        body=block.split('### 화면 내용',1)[1].split('### 화면 구성',1)[0]
        body=re.sub(r'^- 노트:.*\n?','',body,flags=re.M).strip()
        out += [f'## 교재 {slide}장',body,'']
    out += ['원본: 만들기/decks/practical/day01/실전반_01일차.md','원본 SHA256: '+hashlib.sha256(deck.read_bytes()).hexdigest()]
    (folder/'참고_교재_발췌.md').write_text('\n'.join(out),encoding='utf-8')
print('Fixed textbook excerpts added without changing textbook')
