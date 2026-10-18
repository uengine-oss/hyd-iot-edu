"""사용자 변경 범위를 문서에 반영한다. 실습을 실행하지 않는다."""
from pathlib import Path
import json, re
from html import escape
from build_guides import LESSONS, ROOT, BASE

scripts=ROOT/'산출물/교재/대본/실전반_온라인/01회차'
lab=BASE/'01일차_실습3_기록추적'
guide=lab/'가이드.html'
t=guide.read_text('utf-8')
t=re.sub(r'<p class="status">.*?</p>', '<p class="status">제작 범위: 랩·가이드·대본을 수정하고 실제 실행·화면 캡처는 하지 않습니다. 화면 자리는 추후 채웁니다. 앞서 검증한 로컬 출력과 2026-10-14 저장 기록은 기존 근거로 유지합니다. 프롬프트는 상황별 학습 예시이며 실제 Copilot 대화 기록이 아닙니다.</p>', t, flags=re.S)
opening='''<section><h2>먼저: 경보에서 작업지시까지 전체 과정 읽기</h2>
<p>이 가이드는 전체 사건 관찰 뒤 참조 비교를 작은 코드로 구현하는 활동입니다. 저장된 동일 사건의 경보→추천→승인→명령→ACK→재관측→작업지시 순서를 먼저 정리합니다. 실습 환경을 직접 제어하지 않고 제공 기록으로 관측 범위와 빠진 근거를 구분합니다.</p>
<ol><li>경보의 설비·시각·패턴·순간값을 적고 진단 구간 평균과 구분합니다.</li><li>추천 근거와 후보를 비교합니다. 추천 상태와 승인 상태를 혼동하지 않습니다.</li><li>승인 결정의 기록과 시각, 명령 식별자와 응답을 대조합니다. 승인 전 명령 없음은 해당 구간 기록이 충분할 때만 판정합니다.</li><li>재관측과 작업지시 상태를 따로 적습니다. ACK, 유온 완화, 정비 완료는 서로 다른 결과입니다.</li><li>작업지시에서 판단·사건·경보를 역으로 찾고 직접 참조 필드와 도착 식별자를 비교합니다.</li></ol>
<p><b>완료 조건:</b> 전체 흐름의 근거와 미확인 구간을 설명할 수 있어야 합니다. 현재 제공 발췌만으로 세 참조가 모두 입증되지는 않습니다. 이것은 실제 시스템에 참조가 없다는 결론이 아닙니다.</p>
<details><summary>막혔을 때 · 승인과 실행을 구분하는 요청 예시</summary><p>제가 적은 사건 순서와 제공 기록을 붙였습니다. 추천, 승인, 명령 응답, 재관측 중 무엇을 같은 상태로 읽었는지 먼저 질문해 주세요. 답한 뒤 한 구간만 근거와 비교하고, 원본이 부족하면 미확인으로 남겨 주세요.</p></details>
<div class="capture" data-shot="03-00"><b>화면 03-00 · 후속 삽입 자리</b><p>동일 사건의 경보·추천·승인·명령/ACK·재관측·작업지시를 순서대로 보여 주는 화면 묶음. 사건 식별자와 시각이 보이게 합니다. 실제 확인일: ____ / 미확인 구간: ____</p></div></section>'''
if 'data-shot="03-00"' not in t:t=t.replace('<section><h2>1.',opening+'<section><h2>1.',1)
shots=[('03-01','원본 발췌의 참조·도착 식별자와 원본 경로'),('03-02','검사 함수의 값 없음·다름·같음 조건'),('03-03','첫 실행 출력과 결과 JSON: 확인1·미확인2, 작업지시 배정됨'),('03-04','가림 자료와 결과 비교·검사 네 항목. 실제 실패 사례로 표시하지 않음'),('03-05','연결표·추가 원문 요청·작업지시 상태를 담은 제출 결과')]
for n,(sid,desc) in enumerate(shots,1):
    pattern=r'(<section><h2>'+str(n)+r'\..*?)(</section>)'
    if f'data-shot="{sid}"' not in t:
        t=re.sub(pattern,lambda m:m[1]+f'<div class="capture" data-shot="{sid}"><b>화면 {sid} · 후속 삽입 자리</b><p>{escape(desc)}</p><p>실제 확인일: ____ / 관측 결과: ____</p></div>'+m[2],t,count=1,flags=re.S)
if '.capture{' not in t:t=t.replace('</style>','.capture{min-height:180px;border:2px dashed #9da8b4;padding:20px;margin:20px 0;background:#fafbfd}</style>')
guide.write_text(t,encoding='utf-8')
(lab/'채울_화면.md').write_text('# 후속 화면 삽입 목록\n\n직접 캡처는 이번 범위에서 제외합니다. 원본에 없는 결과를 연출하지 않습니다.\n\n'+ '\n'.join(f'- {sid}: {desc}' for sid,desc in [('03-00','동일 사건 전체 흐름과 시각·식별자'),*shots]),encoding='utf-8')
(lab/'연결표.md').write_text('''# 사건 흐름과 연결표

## 전체 흐름
| 단계 | 관측 값·상태 | 시각 | 원본 위치 | 판정·미확인 이유 |
|---|---|---|---|---|
| 경보 | | | | |
| 추천 | | | | |
| 승인 | | | | |
| 명령·ACK | | | | |
| 재관측 | | | | |
| 작업지시 | | | | |

## 역추적
| 출발 | 실제 참조 필드·값 | 도착 식별자 | 근거 위치 | 판정 |
|---|---|---|---|---|
| 작업지시→판단 | | | | |
| 판단→사건 | | | | |
| 사건→경보 | | | | |

추가로 필요한 원문 / 다음 확인 담당 / 아직 말할 수 없는 결론:
''',encoding='utf-8')
mapping={'01일차_실습1_학습노트':'02_실습_학습노트.md','01일차_실습2_실행환경':'04_실습_실행환경.md','01일차_실습4_관계그림':'08_실습_관계그림.md'}
for folder,title,minutes,steps in LESSONS:
    p=scripts/mapping[folder]
    text=p.read_text('utf-8').replace('촬영 초안','촬영 대본')
    # 이전 실측 대기 요구는 최신 사용자 범위와 구분한다.
    text=re.sub(r'^> \[제작:.*$',f'> [제작: 사용자 지시에 따라 직접 실습·캡처하지 않는다. 가이드의 화면 자리와 아래 조작·확인 기준을 따라 후속 촬영한다. 문서 설계 {minutes}분이며 실측이 아니다.]',text,count=1,flags=re.M)
    text+='\n\n# 단계별 조작과 추가 설명 — 해당 단계에서 사용\n\n'
    for n,(heading,action,criterion,question,hint,prompt,shot) in enumerate(steps,1):
        text+=f'## {n}. {heading}\n\n> [화면: 가이드 {n}단계 캡처 자리. {shot}]\n> [조작: {action}]\n\n{question} 먼저 여러분의 판단을 적어 보세요. {hint} 답을 떠올렸다면 어떤 근거를 보았는지 설명해 보겠습니다.\n\n도움이 필요할 때만 가이드의 접힌 요청 예시를 열겠습니다. 예시를 그대로 보내기 전에 내가 보고 있는 자료와 현재 판단을 붙여 주세요. 답을 받으면 그 결과를 확인하고, 아직 확인하지 못한 부분은 남겨 둡니다.\n\n이 단계의 확인 기준을 읽어 보겠습니다. {criterion} 이 기준과 다른 결과라면 어떤 자료를 더 확인해야 할지 적습니다.\n\n'
    p.write_text(text,encoding='utf-8')
p=scripts/'06_실습_전체과정관찰.md'
text=p.read_text('utf-8').replace('촬영 초안','촬영 대본').replace('운영 견적 30분은 코드 응용 추가 후 재리허설 필요.','운영 설계 견적 35분. 실제 리허설은 이번 범위에서 제외.')
text=text.replace('포털 전체 경로 화면 대기.','직접 실습·캡처는 사용자 지시로 제외. 가이드의 후속 화면 자리를 사용.')
p.write_text(text,encoding='utf-8')
config=json.loads((scripts/'구성.json').read_text('utf-8'))
for u in config['units']:
    if u['kind']=='practice':u['status']='문서 대본 작성·화면 후속 삽입'
(scripts/'구성.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
(scripts/'실습_검증범위.md').write_text('''# 최신 제작 범위

2026-10-18 사용자 변경 지시: 직접 실습 실행·브라우저 조작·캡처를 하지 않고 랩·가이드·대본을 수정한다. 실제 화면은 가이드의 빈 자리에 나중에 채운다. 따라서 권한 승인 대기나 실제 촬영을 이번 작업의 완료 조건으로 두지 않는다.

실습 가이드 네 개, 화면 자리·필요 장면 목록, 상황별 접이식 프롬프트, 실습 대본 네 개를 문서로 작성했다. 기록 추적 코드와 기존 로컬 실행 결과는 유지한다. 이번 변경 후 새 실습 실행은 하지 않았다. 화면·앱 기능·학생 완주를 실측 검증했다고 표시하지 않는다.

기존 근거: 2026-10-14 사건 발췌, 앞선 기록 추적기 두 입력 실행과 검사4개 통과. 직접 참조 한 개만 확인되며 두 개는 발췌 부족으로 미확인. 이는 실제 시스템의 참조 누락을 입증하지 않는다.

PDF·HTML·대본 구조와 파일 대응은 문서 검증 대상이다. 사용자 요청이 다시 바뀌기 전에는 실제 실습을 재개하지 않는다.
''',encoding='utf-8')
print('4 guides and scripts updated; no live practice performed')
