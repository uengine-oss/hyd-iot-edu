"""온라인3 실습1 포털 조건별 손익(What-if) 기록 랩. 두 과정 같은 화면, 실전반은 순위와 선택 가능 여부를 구별하는 해석을 더한다.
화면 구조 근거: it/portal/www/whatif.js(설비·이상 패턴 선택, 서버가 주는 변수별 시험값, 규칙 가중치·감점 시험, 관점 중요도, 조치 카드별 주 단위 손익).
변수 이름은 서버가 내려 주므로 여기에 지어 쓰지 않고 학생이 화면 표시를 그대로 기록한다."""
from build_labs import ROOT,OUT,page,write,dump,pack,RULES
from pathlib import Path
import json,hashlib,shutil
HERE=Path(__file__).resolve().parent
NAME='03일차_실습1_조치결과비교'
TITLE='조건을 바꿔 조치 결과 비교하기'
COMMON_STEPS='''1. 학교 PC에 준비된 HYD 포털에서 조건별 손익 화면을 엽니다. 기본 로컬 주소는 http://127.0.0.1:8088 입니다.
2. 설비와 이상 패턴을 고르고 기준 결과를 비교_기록.md에 적습니다. 허용·제외된 조치, 경고·감점, 적용 규칙, 예상 성과를 나누어 적습니다.
3. 시험값 하나만 바꿔 다시 계산하고 기준과 비교합니다. 바꾼 항목의 화면 이름·단위·기준값·시험값을 그대로 적습니다. 다음 시험 전에 기준값으로 되돌립니다.
4. 결과가 달라진 이유를 화면의 적용 규칙·근거에서 찾아 적습니다. 시험값을 바꾼 것은 실제 설비 조치가 아닙니다.'''
PRACTICAL_STEP='5. 결함 시뮬레이션 화면에서 같은 설비의 운전 모드를 현장 제어로 바꾸고(정비원이 현장 패널을 잡은 상황) 조건별 손익을 다시 불러옵니다. 점수나 손익 순위가 높던 후보가 규정상 제외되면, 선택할 수 없는 이유를 결과 화면의 규칙과 근거에서 찾아 적습니다. 순위와 선택 가능 여부를 다른 열에 기록하고, 끝나면 운전 모드를 원격 자동으로 되돌립니다. 운전 모드 전환은 시뮬레이터 조건이며 조치 승인·실행이 아닙니다.'
KPI_STEP='kpi.csv의 세 설비 인터록 여유로 평균과 최솟값을 계산해 목표와 비교합니다. 측정값은 그대로이고 집계 방식에 따라 판단이 달라지는지 봅니다.'
RECORD='''# 조건별 손익 비교 기록

- 포털 주소와 확인 시각:
- 설비와 이상 패턴:

## 기준 결과

| 조치 후보 | 허용·제외 | 경고·감점 | 적용 규칙·근거 | 예상 성과 |
|---|---|---|---|---|
| | | | | |

## 한 항목씩 바꾼 시험

| 시험 | 바꾼 항목(화면 이름) | 단위 | 기준값 → 시험값 | 달라진 결과 | 이유(규칙·근거) | 기준값으로 되돌림 |
|---|---|---|---|---|---|---|
| | | | | | | |
'''
PRACTICAL_RECORD='''
## 순위와 선택 가능 여부

| 조치 후보 | 순위 | 선택 가능 여부 | 막는 조건과 근거 |
|---|---|---|---|
| | | | |
'''
KPI_RECORD='''
## 목표와 집계

| 집계 | 값(℃) | 목표와 비교 |
|---|---|---|
| 평균 | | |
| 최솟값 | | |
'''
catalog=json.loads((HERE/'package-index.json').read_text(encoding='utf-8'))
for course,slug in [('통합반','integrated'),('실전반','practical')]:
    practical=course=='실전반'
    folder=OUT/course/'실습/03회차/랩'/NAME
    old=folder/'코드'
    kpi=(old/'kpi.csv').read_bytes() if (old/'kpi.csv').exists() else (folder/'kpi.csv').read_bytes()
    if old.exists():shutil.rmtree(old)
    (folder/'kpi.csv').write_bytes(kpi)
    rules=RULES.replace('입력/와 자료/는 보존한다.','kpi.csv는 보존한다. 기록은 비교_기록.md와 결과/에 작성한다.')
    for filename in ['AGENTS.md','CLAUDE.md','.github/copilot-instructions.md']:write(folder/filename,rules)
    steps=COMMON_STEPS+('\n'+PRACTICAL_STEP if practical else '')+f'\n{6 if practical else 5}. {KPI_STEP}\n{7 if practical else 6}. 기록을 결과/에 저장하고 다시 열어 확인합니다. 승인·실행 버튼은 누르지 않습니다.'
    nxt='다음 실습에서는 조건표를 읽어 후보를 판정하고 조치 검토 결과를 만드는 기능을 직접 만듭니다.' if practical else '다음 실습에서는 작업 절차와 판단 조건을 연결해 조치 기준(결정표)을 직접 만듭니다.'
    start=f'# {TITLE}\n\n{steps}\n\n보관할 파일은 재부팅 전에 USB 또는 개인 클라우드로 복사합니다. {nxt}\n'
    write(folder/'START.md',start);write(folder/'준비_안내.md',start)
    write(folder/'비교_기록.md',RECORD+(PRACTICAL_RECORD if practical else '')+KPI_RECORD)
    write(folder/'결과/README.md','비교 기록을 여기에 저장합니다.\n')
    sections=[('조건별 손익 열기','<p><a href="http://127.0.0.1:8088" target="_blank" rel="noopener">학교 PC의 HYD 포털 열기</a></p><p>조건별 손익 화면에서 설비와 이상 패턴을 고르세요. 비교_기록.md에 포털 주소와 확인 시각을 적습니다.</p>'),
              ('기준 결과 기록하기','<p>허용·제외된 조치, 경고·감점, 적용 규칙, 예상 성과를 후보별로 나누어 적으세요.</p><p class="check">점수와 손익 금액은 다른 열에 적습니다. 값이 표시되지 않은 칸은 0으로 채우지 않고 미확인으로 둡니다.</p>'),
              ('한 항목만 바꿔 비교하기','<p>시험값 하나를 바꾸고 다시 계산하세요. 바꾼 항목의 화면 이름·단위·기준값·시험값을 그대로 적습니다. 다음 시험 전에 기준값으로 되돌립니다.</p><p class="check">결과가 달라졌으면 그 이유를 적용 규칙과 근거에서 찾습니다. 시험값 변경은 실제 설비 조치가 아닙니다.</p>')]
    if practical:sections.append(('순위와 선택 가능 여부 구별하기','<p>결함 시뮬레이션 화면에서 같은 설비의 운전 모드를 「현장 제어」로 바꾼 뒤 조건별 손익에서 다시 불러오세요. 점수나 손익 순위가 높던 후보가 「규정상 제외」로 바뀌었는지 보고, 선택할 수 없는 이유를 결과 화면의 규칙과 근거에서 찾아 적습니다.</p><p class="check">순위와 선택 가능 여부를 다른 열에 기록합니다. 끝나면 운전 모드를 「원격 자동」으로 되돌립니다. 모드 전환은 시뮬레이터 조건이고, 비교 순위는 실행 승인이 아닙니다.</p>'))
    sections+= [('목표와 집계 비교하기',f'<p>{KPI_STEP}</p>'),('저장하기','<p>비교 기록을 결과/에 저장하고 다시 엽니다. 승인·실행 버튼은 누르지 않습니다. 보관할 파일은 USB 또는 개인 클라우드로 복사하세요.</p><p>'+nxt+'</p>')]
    for filename in ['guide.html','안내.html']:write(folder/filename,page(TITLE,'같은 설비에서 시험값 하나씩 바꾸며 허용·제외된 조치와 예상 성과가 달라지는 이유를 기록합니다.',sections))
    archive=pack(folder)
    lab_id=f'{slug}-03-whatif'
    catalog['labs']=[x for x in catalog['labs'] if x['id']!=lab_id]
    catalog['labs'].append({'id':lab_id,'course':course,'session':'온라인 03회차','title':TITLE,'version':'2026-10-28-s3-whatif-v2-mode' if practical else '2026-10-28-s3-whatif-v1','folder':'03회차/랩/'+NAME,'path':archive.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()})
catalog['labs'].sort(key=lambda x:(x['course'],x['session'],x['folder']))
dump(HERE/'package-index.json',catalog)
print('온라인3 조건별 손익 기록 랩 두 과정 생성')
