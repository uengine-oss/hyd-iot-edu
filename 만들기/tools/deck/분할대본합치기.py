"""회차 폴더의 구성.json에 따라 합본·낭독본·구성표를 생성한다.

사용: python 만들기/tools/deck/분할대본합치기.py 산출물/교재/대본/통합반_온라인/01회차
실습은 별도 낭독본으로 생성하며 PPTX 합본에 섞지 않는다. 범위·순서·중복·누락을 검사한 뒤 출력한다.
"""
from pathlib import Path
import json,re,sys

def speech(block):
    head,rest=block.split('\n',1)
    lines=[s.replace('**','').rstrip() for s in rest.splitlines() if not s.startswith(('>','# ','---'))]
    return head+'\n\n'+re.sub(r'\n{3,}','\n\n','\n'.join(lines)).strip()+'\n'

def estimate(text):
    t=re.sub(r'^#.*$|^>.*$|\*\*','',text,flags=re.M)
    t=re.sub(r'[A-Za-z][A-Za-z0-9 _\-/\.]*\(([가-힣 ]+)\)',r'\1',t)
    return (len(re.findall('[가-힣]',t))+1.6*len(re.findall(r'\d',t))+.6*len(re.findall('[A-Za-z]',t)))/275

def build(folder):
    data=json.loads((folder/'구성.json').read_text(encoding='utf8'))
    assert data['version']==1
    day=data['day']; base=folder.parent
    coverage=[]; rows=[]; bodies=[]; reading=[]; outputs={}; total=0; wait=0; count=0
    assert len({u['file'] for u in data['units']})==len(data['units'])
    for u in data['units']:
        name=u['file']; assert Path(name).name==name
        path=folder/name
        if u['kind']=='empty_practice':
            assert path.read_bytes()==b'',f'빈 실습 파일에 내용이 생겼습니다: {path}'
            rows.append(f'| {name} | 실제 실습 · 미작성 | — | — |'); continue
        if u['kind']=='practice':
            text=path.read_text(encoding='utf8')
            assert text.strip(),f'실습 대본 없음: {path}'
            cleaned='\n'.join(s for s in text.splitlines() if not s.startswith(('>','#','---'))).strip()
            mins=estimate(cleaned)
            outputs[folder/'낭독본'/name]='# '+text.splitlines()[0][2:]+' — 낭독 대본\n\n'+re.sub(r'\n{3,}','\n\n',cleaned)+'\n'
            rows.append(f'| [{name}]({name}) | 실습 대본 · 실행 미검증 | {mins:.1f}분(발화만) | — |')
            continue
        assert u['kind']=='pptx'
        text=path.read_text(encoding='utf8')
        blocks=re.split(r'(?=^## \[SLIDE )',text,flags=re.M)[1:]
        assert blocks,f'슬라이드 없음: {path}'
        nums=[]
        for b in blocks:
            m=re.match(r'## \[SLIDE (\d+)(?:~(\d+))?\]',b); assert m
            start=int(m[1]);end=int(m[2] or m[1]);assert start<=end
            nums.extend(range(start,end+1));assert speech(b).split('\n',1)[1].strip()
        assert nums==list(range(u['slides'][0],u['slides'][1]+1)),f'단위 범위 불일치: {path}'
        coverage+=nums; count+=len(blocks)
        cleaned='\n'.join(speech(b) for b in blocks)
        assert '영상' not in re.sub(r'^#.*$','',cleaned,flags=re.M),f'발화에 영상: {path}'
        mins=estimate(cleaned);total+=mins
        seconds=sum(map(int,re.findall(r'^>\s*\[대기\s*(\d+)\s*초\]',text,flags=re.M)));wait+=seconds
        title=text.splitlines()[0][2:]
        heading=f'# [이론 {name[:2]}] {title.split(" — ",1)[-1]}\n\n'
        bodies.append(heading+'\n\n'.join(b.strip() for b in blocks))
        reading.append(heading+cleaned)
        outputs[folder/'낭독본'/name]='# '+title+' — 낭독 대본\n\n'+cleaned
        rows.append(f'| [{name}]({name}) | {nums[0]}~{nums[-1]} | {mins:.1f}분 | {seconds}초 |')
    assert coverage==list(range(1,data['slide_count']+1)),'회차 누락·중복·순서 오류'
    table='| 단위 파일 | PPTX 장 / 상태 | 낭독 추정 | 학습 대기 |\n|---|---|---:|---:|\n'+'\n'.join(rows)
    guide=f'# 통합반 {day}회차 — 구성표\n\n분할 파일이 수정 원본입니다. 합본·낭독본을 직접 수정하지 않습니다. 제목과 제작 표시는 읽지 않습니다. 이론 대본에 실습 간지·설명과 해당 마무리를 포함합니다. 실제 실습의 삽입·재개는 제작 표시와 진행 순서를 따릅니다. 빈 실습 파일은 작성 완료나 촬영 분량으로 세지 않습니다.\n\n{table}\n\n진행 순서: {data.get("playback", "구성 순서와 제작 표시를 따릅니다.")}\n\nPPTX {data["slide_count"]}장, 대본 {count}블록. 이론 낭독 추정 합 {total:.1f}분, 학습 대기 {wait}초 별도. 기존 분당 275음절 산식을 사용한 견적이며 실제 녹음 길이가 아닙니다. 실습 운영 시간과 합치거나 240분에 맞추지 않습니다.\n\n재생성: `python 만들기/tools/deck/분할대본합치기.py 산출물/교재/대본/통합반_온라인/{day:02d}회차`\n\nPDF는 합본 낭독본에서 별도로 재생성합니다. 제작 근거는 `제작기록.md`에 있습니다.\n'
    outputs[folder/'구성표.md']=guide
    outputs[base/f'통합반_{day:02d}일차_대본.md']=f'# 통합반 {day}회차 — 촬영 대본\n\n> 자동 생성 합본. 수정 원본은 `{day:02d}회차/`의 분할 대본입니다. 제작 제목은 낭독하지 않습니다. 실제 실습 삽입 위치는 회차 구성표와 본문의 제작 표시를 따릅니다. 실습 간지·설명은 포함하고 실제 실습 발화는 포함하지 않습니다.\n\n'+table+'\n\n'+'\n\n---\n\n'.join(bodies)+'\n\n# 촬영 본문 끝\n\n## 제작 확인용 — 낭독하지 않음\n\n세부 근거와 이전 이력: '+f'`{day:02d}회차/제작기록.md`. 현재 시간과 범위: `{day:02d}회차/구성표.md`.\n'
    outputs[base/'낭독본'/f'통합반_{day:02d}일차_낭독본.md']=f'# 통합반 {day}회차 — 낭독 대본\n\n'+'\n\n'.join(reading)
    for p,t in outputs.items():
        p.parent.mkdir(parents=True,exist_ok=True);p.write_text(t,encoding='utf8')
    print(json.dumps({'slides':len(coverage),'blocks':count,'minutes':round(total,1),'wait_seconds':wait,'outputs':len(outputs)},ensure_ascii=False))

if __name__=='__main__':
    build(Path(sys.argv[1]))
