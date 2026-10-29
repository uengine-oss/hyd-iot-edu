"""순차 발화→행동 계획 시간. 실행·촬영·음성 호출 없음."""
from pathlib import Path
import re,json,hashlib
HERE=Path(__file__).resolve().parent
def weighted(s):
    return len(re.findall('[가-힣]',s))+1.6*len(re.findall('[0-9]',s))+.6*len(re.findall('[A-Za-z]',s))
def stamp(s):
    n=round(s);return f'{n//60}:{n%60:02}'
def main():
    src=HERE/'수업원고.md';text=src.read_text(encoding='utf-8')
    actions=json.loads((HERE/'행동목록.json').read_text(encoding='utf-8'))
    assert re.findall(r'^> 실행 (N\d+-\d+):',text,re.M)==[a['id'] for a in actions]
    for a in actions:
        assert a['speech']+'\n\n> 실행 '+a['id']+':' in text,a['id']
    # 정상 조작 자체의 시간 범위. 지시된 대기나 실측값이 아니다.
    seconds={'ui':(.6,1.2),'input':(.6,1.2),'drag':(1.2,2.5),'scroll':(.8,1.8)}
    # 네트워크/다운로드 응답만 별도 가정. 포인터 끊김·녹화 지연은 제외.
    response={2:(0,3),7:(0,4),8:(0,2),10:(0,2),16:(0,2),17:(1,6),19:(0,3),20:(3,15),21:(3,15),24:(2,10),25:(1,6),28:(5,25)}
    rows=[]
    for sid,title,body in re.findall(r'^## (N\d+) · (.+)\n([\s\S]*?)(?=^## N\d+ · |\Z)',text,re.M):
        blocks=[p for p in body.strip().split('\n\n') if p and not p.startswith('>')]
        speech=weighted('\n'.join(blocks))/275*60
        subset=[a for a in actions if a['scene']==sid]
        chars=sum(sum(len(v) for v in a['inputs']) for a in subset)
        motorlo=sum(a['motor_events']*seconds[a['kind']][0] for a in subset if not a['conditional'])
        motorhi=sum(a['motor_events']*seconds[a['kind']][1] for a in subset)
        gap=response.get(int(sid[1:]),(0,0))
        rows.append(dict(scene=sid,title=title,speech_seconds=round(speech,2),spoken_blocks=len(blocks),
                         action_cues=len(subset),input_characters=chars,
                         typing_seconds_range=[round(chars/6,2),round(chars/4,2)],
                         motor_seconds_range=[round(motorlo,2),round(motorhi,2)],response_seconds_range=list(gap),
                         total_seconds_range=[round(speech+chars/6+motorlo+gap[0],2),round(speech+chars/4+motorhi+gap[1],2)]))
    speech=sum(r['speech_seconds'] for r in rows);lo=sum(r['total_seconds_range'][0] for r in rows);hi=sum(r['total_seconds_range'][1] for r in rows)
    data=dict(source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),is_measured=False,model='speech_then_action_no_overlap',speech_seconds=round(speech,2),action_cues=len(actions),input_characters=sum(r['input_characters'] for r in rows),estimated_total_seconds_range=[round(lo,2),round(hi,2)],scenes=rows,actions=actions)
    (HERE/'예상시간.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    out=f'''# Notion 대본 — 순차 진행 예상 시간

발화 **{stamp(speech)}**, 안내 종료 뒤 입력·조작·응답을 합산한 계획 예상 **{stamp(lo)}~{stamp(hi)}**. 전체 실측·음성 청취는 하지 않았다. 50분에 맞춘 배정값이 아니다.

## 현재 계산

- 실제 발화만 한글 음절+숫자×1.6+영문 글자×0.6, 분당275 기준으로 계산한다. 제목·실행 표시·제작 메모는 낭독하지 않는다.
- 실행 표시 {len(actions)}개를 실제 대사 직후에 배치했다. 그 행동 안내를 마친 다음 클릭·키 입력·드래그·선택·본문 입력을 수행한다. 말과 동작의 동시 진행으로 시간을 할인하지 않는다.
- 입력 문구 {data['input_characters']}자는 초당4~6자 가정이다. 공백·문장부호 포함, 파일 선택 이름 제외. 한글 자모 타수나 실제 입력 측정값이 아니다. 입력 문자열은 행동목록.json에 공개한다.
- 클릭·선택·키 조작은 건당0.6~1.2초, 드래그1.2~2.5초, 스크롤0.8~1.8초의 정상 수행 가정이다. 말로 안내한 복합 행동은 해당 목록의 motor_events 수를 사용한다. 조건부 행동은 하한에서 제외하고 상한에 포함했다. 입력 자체의 시간과 별도로 필요한 클릭·확정만 더한다.
- 파일 업로드·다운로드와 페이지 응답은 해당 장면에만 별도 범위를 두었다. 네트워크에 따라 달라진다. 프레임 누락·커서 끊김·녹화 처리 지연을 정상 소요 시간으로 인정하지 않는다.
- 모든 수치는 계획 가정이며 고정 지연 지시가 아니다. 화면과 손의 조작이 끝나면 바로 다음 대사로 간다. 컷·배속·입력 생략은 가정하지 않는다. 실제 속도·메뉴 판본에 따라 범위 밖일 수도 있다.
- 구판45:32~51:22는 동시 진행 가정을 포함하므로 이 판본에는 사용하지 않는다. 현재 전체 과정을 자연스럽게 담으면50분을 넘을 수 있다. 억지로 늦추거나 필요한 안내를 잘라 시간을 맞추지 않는다.

## 장면별 계획

| 장면 | 내용 | 발화 | 순차 진행 합계 |
|---|---|---:|---:|
'''
    for r in rows:out+=f"| {r['scene']} | {r['title']} | {stamp(r['speech_seconds'])} | {stamp(r['total_seconds_range'][0])}~{stamp(r['total_seconds_range'][1])} |\n"
    out+=f'\n원고 SHA-256: `{data["source_sha256"]}`. 세부 계산은 예상시간.json, 재계산은 estimate.py. 화면 상태가 다르면 해당 대사와 행동만 수정한 뒤 재산정한다.\n'
    (HERE/'예상시간.md').write_text(out,encoding='utf-8',newline='\n')
    print(f'Speech {stamp(speech)}; sequential total {stamp(lo)}–{stamp(hi)}; cues {len(actions)}')
if __name__=='__main__':main()
