"""실전반 온라인 1회차: 최신 공통 1회차 본문과 과정별 대본을 조립한다.

python 만들기/decks/practical/day01/조립.py [--source-root 최신통합반저장소]
본문은 바꾸지 않는다. 표지 과정과 발표자 노트만 과정에 맞추고 그림은 그대로 복사한다.
"""
from pathlib import Path
import argparse,hashlib,json,re,shutil

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def speech(block):
    rest=block.split('\n',1)[1]
    return ' '.join(s.replace('**','').strip() for s in rest.splitlines() if s.strip() and not s.startswith(('>','# ','---')))
def screen(block):
    return re.sub(r'^- 노트:.*\n?', '', block.split('### 화면 내용',1)[1].split('### 화면 구성',1)[0],flags=re.M).strip()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source-root',type=Path,default=ROOT);args=ap.parse_args()
    src=args.source_root/'만들기/decks/integrated/day01/통합반_01일차.md'
    folder=ROOT/'산출물/교재/대본/실전반_온라인/01회차'
    config=json.loads((folder/'구성.json').read_text('utf8'))
    assert sha(src)==config['source_deck_sha256'],'공통 원본 버전 변경: 대응과 검토를 먼저 갱신하세요'
    original=src.read_text('utf8');blocks=re.split(r'(?=^## SLIDE )',original,flags=re.M)[1:]
    notes={};covered=[]
    for u in config['units']:
        if u['kind']!='pptx':continue
        text=(folder/u['file']).read_text('utf8')
        for b in re.split(r'(?=^## \[SLIDE )',text,flags=re.M)[1:]:
            m=re.match(r'## \[SLIDE (\d+)(?:~(\d+))?\]',b);start=int(m[1]);end=int(m[2] or start)
            notes[start]=speech(b)
            for n in range(start,end+1):
                covered.append(n)
                if n>start:notes[n]=''
    assert covered==list(range(1,79))
    assembled=[];provenance=[]
    for n,b in enumerate(blocks,1):
        assert b.startswith(f'## SLIDE {n:02d} — ')
        new=b
        if n==1:
            assert new.count('- 과정: 설비 데이터와 지식 모델')==1
            new=new.replace('- 과정: 설비 데이터와 지식 모델','- 과정: 실전반 온라인 1회차',1)
        new=re.sub(r'^- 노트:.*\n?','',new,flags=re.M)
        new=new.replace('### 화면 구성','- 노트: '+notes[n]+'\n\n### 화면 구성',1)
        expected=screen(b).replace('- 과정: 설비 데이터와 지식 모델','- 과정: 실전반 온라인 1회차') if n==1 else screen(b)
        assert screen(new)==expected,(n,'공통 본문 변경')
        assets=[]
        for rel in re.findall(r'^- 그림: (.+)$',new,re.M):
            p=src.parent/rel.strip();target=HERE/rel.strip();target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(p,target);assert sha(p)==sha(target)
            assets.append({'path':rel.strip(),'sha256':sha(p)})
        assembled.append(new)
        provenance.append({'slide':n,'source_slide':n,'source_title':b.splitlines()[0].split(' — ',1)[1],'screen_sha256':hashlib.sha256(screen(new).encode()).hexdigest(),'body_unchanged':True,'cover_course_changed':n==1,'assets':assets})
    header='<!-- 조립.py 생성. 공통 본문 고정. 표지 과정과 과정별 발표자 노트만 조립한다. 직접 수정하지 않는다. -->\n'
    (HERE/'실전반_01일차.md').write_text(header+original.split('## SLIDE ')[0]+''.join(assembled),encoding='utf8')
    (HERE/'단원대응.json').write_text(json.dumps({'source':'만들기/decks/integrated/day01/통합반_01일차.md','source_sha256':sha(src),'slides':provenance},ensure_ascii=False,indent=2),encoding='utf8')
    print('78장 조립, 공통 본문 불변, 그림 해시 일치, 과정별 발표자 노트 반영')
if __name__=='__main__':main()
