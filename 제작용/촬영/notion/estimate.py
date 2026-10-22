"""연속 발화 원고의 계획 시간을 산정한다. 실측·TTS 호출·브라우저 조작 없음."""
from pathlib import Path
import re
import json
import hashlib

HERE = Path(__file__).resolve().parent

def weighted(text):
    return (len(re.findall('[가-힣]', text))
            + 1.6 * len(re.findall('[0-9]', text))
            + .6 * len(re.findall('[A-Za-z]', text)))

def main():
    path = HERE / '수업원고.md'
    source = path.read_text(encoding='utf-8')
    rows = []
    # 말하는 동안 수행하는 클릭·드래그는 추가하지 않는다. 아래는 문장이 끝난 뒤
    # 남을 수 있는 전환/확인의 계획 여유 범위(초)이며 고정 지연을 지시하지 않는다.
    residual = {1:(0,5),2:(0,5),3:(0,3),4:(0,2),5:(0,2),6:(0,5),
                7:(0,8),8:(0,4),9:(0,4),10:(0,4),11:(0,3),12:(0,3),
                13:(0,3),14:(0,3),15:(0,4),16:(0,4),17:(2,10),18:(3,12),
                19:(0,6),20:(5,20),21:(5,20),22:(0,8),23:(0,5),
                24:(3,12),25:(2,10),26:(0,3),27:(0,3),28:(10,35),29:(0,5)}
    for sid,title,body in re.findall(r'^## (N\d+) · (.+)\n([\s\S]*?)(?=^## N\d+ · |\Z)',source,re.M):
        paragraphs = [p.strip() for p in body.split('\n\n') if p.strip() and not p.startswith('>')]
        spoken = '\n'.join(paragraphs)
        # 원고의 작은따옴표는 실제 입력/바꾸기 문구. 파일 선택 이름은 타이핑에서 제외.
        inputs = [s for s in re.findall('‘([^’]+)’', spoken) if not s.endswith(('.png','.md'))]
        chars = sum(len(s) for s in inputs)
        speech = weighted(spoken) / 275 * 60
        gap = residual[int(sid[1:])]
        # 입력할 문장을 먼저 읽고 실제로 입력하는 보수적 모델. 이 입력은 발화와
        # 겹쳤다고 빼지 않으며, 말하며 입력할 경우 실제 시간은 아래보다 짧아진다.
        rows.append(dict(scene=sid,title=title,paragraphs=len(paragraphs),speech_seconds=round(speech,2),
                         input_strings=inputs,input_characters=chars,
                         typing_seconds_range=[round(chars/6,2),round(chars/4,2)],
                         residual_seconds_range=list(gap),
                         total_seconds_range=[round(speech+chars/6+gap[0],2),round(speech+chars/4+gap[1],2)]))
    speech=sum(r['speech_seconds'] for r in rows)
    lower=sum(r['total_seconds_range'][0] for r in rows)
    upper=sum(r['total_seconds_range'][1] for r in rows)
    data={'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
          'speech_rate_weighted_units_per_minute':275,'typing_characters_per_second_range':[4,6],
          'is_measured':False,'speech_seconds':round(speech,2),
          'input_characters':sum(r['input_characters'] for r in rows),
          'estimated_total_seconds_range':[round(lower,2),round(upper,2)],'scenes':rows}
    (HERE/'예상시간.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    def stamp(n):return f'{int(round(n))//60}:{int(round(n))%60:02}'
    text=f'''# Notion 연속 대본 예상 시간

현재 원고 기준 순수 발화는 **{stamp(speech)}**, 입력과 화면 전환을 포함한 계획 예상은 **{stamp(lower)}~{stamp(upper)}**다. 촬영·낭독 실측은 하지 않았다. 원고 해시: `{data['source_sha256']}`.

## 계산 기준

- 제목·제작 메모를 제외한29장면의 실제 발화124문단을 모두 센다. 한글 음절+숫자×1.6+영문 글자×0.6을 분당275로 나눈다. 앞 원고15.21분은 조작 안내가 빠진 구판의 발화 추정이며 현재 영상 길이로 사용하지 않는다.
- 안내 먼저→조작→결과 확인을 연속으로 진행한다. 설명하면서 하는 클릭·메뉴 탐색·드래그 시간을 발화에 다시 더하지 않는다. 컷·배속·입력 생략을 가정하지 않는다.
- 원고에서 입력 문구로 명시한 작은따옴표 안의 {data['input_characters']}자를 별도 집계했다. 파일 선택 이름은 제외했다. 입력 문장을 먼저 알려 준 뒤 입력하는 보수적 모델로 초당4~6자(공백·문장부호 포함)를 가정했다. 키 누름 횟수/분이나 실제 사용자의 입력 측정값이 아니다. 설명하면서 입력하면 겹친 만큼 실제 길이는 줄어든다.
- 메뉴 열기와 결과 확인에서 말이 끝난 뒤 남을 수 있는 전환만 장면별0~수십 초 범위로 따로 가정했다. 업로드·내보내기 대기도 포함한다. 계산상의 여유이지 촬영 때 멈춰 기다리라는 지시가 아니다. 화면이 준비되면 바로 이어 간다.
- 따라서 위 범위는 조건부 제작 예상이며 시간 보장도, 실제 화면 싱크 검증도 아니다. 느린 네트워크·메뉴 차이·입력 속도·발화 속도에 따라 달라진다.50분에 맞춰 느리게 진행하거나 말을 추가하지 않는다.

## 장면별 예상

| 장면 | 내용 | 발화 | 입력·전환 포함 |
|---|---|---:|---:|
'''
    for r in rows:text+=f"| {r['scene']} | {r['title']} | {stamp(r['speech_seconds'])} | {stamp(r['total_seconds_range'][0])}~{stamp(r['total_seconds_range'][1])} |\n"
    text+='\n문단별 낭독 내용은 수업원고.md 하나로 진행한다. 계산 상세와 입력 문자열 목록은 예상시간.json, 재계산은 estimate.py를 사용한다. 실제 결과가 없는 상태에서 결과 확인 대사를 먼저 말하지 않는다.\n'
    (HERE/'예상시간.md').write_text(text,encoding='utf-8',newline='\n')
    print(f'Speech {stamp(speech)}; total {stamp(lower)}–{stamp(upper)}; {data["input_characters"]} typed characters')

if __name__=='__main__':
    main()
