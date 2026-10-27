"""온라인 3회차 SOP·조건표·판단 랩 세 개의 독립 시작본.

통합반 03일차_실습2_조치기준만들기, 통합반 03일차_실습3_판단기능만들기,
실전반 03일차_실습2_판단기능만들기. 강사 참조 답안은 reference/session3/에만 둔다.
학생 폴더에는 이전 단계 완성 상태(설비 모델, 완성 조건표·SOP 구조)와 원자료만 넣는다.
"""
from build_labs import ROOT, OUT, page, write, dump, pack, RULES, reference_model
from pathlib import Path
import hashlib
import html
import json
import shutil

HERE = Path(__file__).resolve().parent
REFERENCE = HERE/'reference/session3'
VERSION = '2026-10-28-s3-v1'
SESSION = '온라인 03회차'
PREVIOUS = OUT/'실전반/실습/02회차/랩/02일차_실습5_조치조건표'
CRITERIA = OUT/'통합반/실습/03회차/랩/03일차_실습2_조치기준만들기'
JUDGE = OUT/'통합반/실습/03회차/랩/03일차_실습3_판단기능만들기'
REVIEW = OUT/'실전반/실습/03회차/랩/03일차_실습2_판단기능만들기'
LABS = [CRITERIA, JUDGE, REVIEW]

# 원자료의 단일 소유 위치. 2회차 조건표 랩과 같은 판본의 매뉴얼·규칙 발췌를 그대로 쓴다.
OWNED_ELSEWHERE = {'HM-8_매뉴얼.md': PREVIOUS/'HM-8_매뉴얼.md', '규칙_원문.txt': PREVIOUS/'규칙_원문.txt'}
# 옛 코드/ 구조에서 옮겨 온 뒤 이 위치가 원본이다.
CANON_SOURCE = {name: CRITERIA/'자료'/name for name in ['작업기준.md', 'targets.csv', 'failuremodes.csv', 'cases.csv']}
CANON_METRICS = {name: JUDGE/'자료/metrics'/name for name in ['지표_정의.md', '업무_값.json', '후보_설정.csv', '판정_요청.json']}
LEGACY = {**{name: ('코드/source/'+name if name.endswith('.md') else '코드/'+name) for name in CANON_SOURCE}, **{name: '코드/metrics/'+name for name in CANON_METRICS}}

SCOPE = '''# 입력과 적용 범위

작업기준.md는 팬 최대 운전 후보(skill:fan-max) 하나를 중심으로 정리한 이전 기준이다. 이번에는 targets.csv의 SOP 네 개로 넓힌다. 다른 후보는 targets.csv의 SOP ID와 HM-8 원문의 적용 범위를 대조해 행을 확장한다. 기존 설비 모델의 ID는 SOP 구조의 모델 참조에 적는다. reference_skill_id 빈칸은 이름만 보고 채우지 않는다.

팬 감점은 SOP-COOL-11·12에만, 원격 모드 제외는 SOP-COOL-11~13에 적용한다. 압력·트립 규칙은 첨부 구조화 발췌를 근거로 쓴다. 작업지시와 제어의 kind를 구별한다. 실행 코드는 목록이므로 FAN_SET 포함 여부와 RESET 외 코드 존재를 목록으로 판정한다.

cases.csv는 경계·누락·복수 규칙 비교용 입력이며 실제 사건 기록이 아니다. 한 사례의 후보들은 같은 예측값을 쓰므로 규칙의 적용 대상 차이만 비교된다. HM-8.5의 팬 24시간 수행 제한과 감점 조건은 별개이며 후보 유지가 실행 허가는 아니다.
'''

TABLE_CONTRACT = '''## 결정표 rules.csv

열: `rule_id,action,condition_index,logic,input,operator,value,unit,boundary_included,result,penalty_만원,reason,source_section`

- 비교 하나가 한 행이다. 같은 `rule_id`·`action`의 행은 한 규칙 묶음이고 `condition_index` 1부터 순서대로 적으며 `logic`은 `AND`다. OR는 다른 `rule_id`로 나눈다.
- `action`은 targets.csv의 SOP ID 하나다. 여러 후보에 같은 규칙을 적용하면 후보마다 묶음 전체를 적는다. 표에 없는 후보·규칙 조합은 적용 대상 밖이다.
- `result`는 `WARN`(경고), `PENALTY`(감점), `EXCLUDE`(제외) 중 하나다. 같은 묶음의 `result`·`penalty_만원`·`reason`·`source_section`은 모든 행에서 같다. `PENALTY`만 `penalty_만원`(만원)을 적고 나머지는 빈칸이다.
- `operator`: `>=`, `>`, `<=`, `<`, `==`, `!=`, `has_other_than`(목록 입력에 기준값이 아닌 항목이 하나라도 있음). `boundary_included`는 기준값 자체가 조건에 들어가면 `예`(`>=`,`<=`), 아니면 `아니오`(`>`,`<`), 문자열·목록 비교는 `해당없음`이다.
- `input` 이름: `forecast_ts1`(조치 후 예측 유온, ℃), `forecast_ps1`(조치 후 예측 토출 압력, bar), `fan100_hours`(팬 100 % 연속 운전 시간, h), `plc_mode`, `plc_state`(`RUNNING`/`TRIP`), `skill_kind`(`control`/`work_order`), `skill_code`(실행 코드 목록). 숫자 입력은 `unit`을 적는다.
- `source_section`에는 원문 근거를 적는다. 규칙_원문.txt의 시드 출처(HM-3.2·HM-5.2·HM-7.3·HM-7.5·HM-9.4)는 첨부 HM-8의 절 번호와 다른 체계다. 같은 번호로 바꾸지 말고 `규칙발췌 rule:...(시드 HM-x.y)`처럼 구별하고, 첨부 HM-8에서 같은 내용을 찾으면 그 절을 함께 적는다. HM-8에 없는 문장을 HM-8 인용으로 만들지 않는다.
- 시드 R1(rule:ts1-warn)은 팬 최대 운전·팬 감속용이다. HM-8.6의 예측 유온 기준을 다른 후보에도 적용하려면 별도 `rule_id`와 HM-8.6 출처를 쓰고 같은 후보에 R1과 겹쳐 세지 않는다.

예시 한 줄(형식만 보여 주는 가상의 행이며 정답 행이 아니다):

```
R0,SOP-COOL-00,1,AND,forecast_ts1,>=,0,℃,예,WARN,,이유 문장,근거 절
```
'''

JUDGE_RULES = '''## 판정 규칙

1. 후보의 입력을 만든다. cases.csv의 `forecast_ts1_C`→`forecast_ts1`, `forecast_ps1_bar`→`forecast_ps1`로 이름만 바꾸고, 판정_요청.json의 `RUN`은 `RUNNING`으로 바꾼다(`TRIP`과 구별). `skill_kind`·`skill_code`는 targets.csv에서 후보별로 읽고 kind `workorder`는 `work_order`로, 코드의 `;` 목록은 나눈다. 빈 칸·`null`은 0이나 정상값으로 채우지 않는다.
2. 후보마다 `action`이 그 후보인 규칙 묶음만 평가한다(적용 대상 밖은 평가하지 않는다).
3. 묶음의 조건 중 값이 있는데 거짓인 조건이 하나라도 있으면 불일치다. 거짓이 없고 값이 빠진 조건이 있으면 미확인(unknown)이다. 모두 참이면 일치다.
4. 일치한 묶음은 결과 종류별로 모두 모은다. 첫 일치에서 멈추지 않는다. 감점은 묶음당 한 번만 더한다(조건 행 수와 무관).
5. 판정: 제외 사유가 있으면 `제외`(미확인도 함께 남김), 제외 없이 미확인이 있으면 `보류`, 둘 다 없으면 `유지`. 제외됐다고 경고·감점 기록을 지우지 않는다. 이 미확인 처리는 이 랩의 보수적 검토 계약이며 HYD 함수의 누락값 처리를 실행해 검증한 결과가 아니다.
6. 유지 후보가 없으면 추천은 비우고 이유를 남긴다. 모두 제외된 경우와 보류 때문에 유지 후보가 없는 경우를 구별해 적는다.

사람이 원문으로 판단할 지점: 트립 규칙(rule:trip-reset-only)의 문장은 「PLC가 리셋 외 제어 명령을 거부한다」인데 판정식(`plc_state == 'TRIP' and skill_code != 'RESET'`)에는 적용 대상 제한이 없어 작업지시 후보에도 걸린다. 포털의 판단도 이 식을 그대로 쓴다. 식대로 따를지, 문장대로 제어 후보에만 적용할지 정했다면 그 근거와 바뀌는 사례를 기록에 남긴다.
'''

COMPARE_RULES = '''## 교육용 비교

- 판정_요청.json의 C01~C14만 비교한다. cases.csv의 A~M는 판정(적용 대상·경계·누락) 확인용이다.
- 비교는 `유지` 후보만 한다. 제외·보류 후보는 순위에서 뺀다. 식은 자료/metrics/지표_정의.md를 그대로 쓴다. 지표_정의.md의 C01 손계산(SOP-COOL-12)을 먼저 맞춘다.
- 비교 합계 = 비용 + 생산 + 품질 + 에너지 + 그 후보의 감점 합. 단위는 만원이고 작을수록 유리하다. 각 지표의 값과 감점은 따로 남긴다. 금액은 소수 둘째 자리로 반올림해 저장한다.
- 같은 합계는 같은 순위다(예: 1, 1, 3). 필요한 값이 없어 지표를 계산할 수 없으면 그 후보의 합계와 순위를 비우고 이유를 남긴다.
- 이 합계는 교육용 비교값이다. 이론에서 본 HYD의 일곱 성분 정책 점수와 섞거나 같은 것으로 설명하지 않는다. 결과 파일에 이 구분을 문장으로 남긴다.
'''


def rules_for(extra):
    text = RULES.replace('입력/와 자료/는 보존한다.', '입력/·자료/의 파일과 check.py는 보존한다.')
    text = text.replace('- DB 작업은 안내된 별도 랩 주소만 사용한다. 포털 DB와 시스템 파일을 수정하거나 전체 삭제하지 않는다.\n', '- 실제 설비·포털·업무 시스템을 호출하지 않는다. 이번 실습은 제공 파일만 읽는다.\n')
    if text == RULES:
        raise RuntimeError('build_labs.RULES 문구가 바뀌어 랩 규칙을 조정하지 못했습니다.')
    return text + ''.join(f'- {line}\n' for line in extra)


def migrate_legacy():
    """옛 코드/ 구조의 원자료를 새 원본 위치로 옮기고 코드/를 지운다. 이미 옮겼으면 동일성만 확인한다."""
    for name, target in {**CANON_SOURCE, **CANON_METRICS}.items():
        legacy_owner = CRITERIA if target.is_relative_to(CRITERIA) else JUDGE
        legacy = legacy_owner/LEGACY[name]
        if not target.is_file():
            if not legacy.is_file():
                raise FileNotFoundError(f'원자료 없음: {target} (옛 위치 {legacy}도 없음)')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(legacy, target)
            print('옮김:', legacy.relative_to(ROOT), '→', target.relative_to(ROOT))
    for folder in LABS:
        legacy_dir = folder/'코드'
        if legacy_dir.is_dir():
            for name in ['cases.csv', 'targets.csv', 'failuremodes.csv']:
                old = legacy_dir/name
                if old.is_file() and old.read_bytes() != CANON_SOURCE[name].read_bytes():
                    raise RuntimeError(f'옛 {old}가 원본 {CANON_SOURCE[name]}과 다릅니다. 확인 전에는 지우지 않습니다.')
            shutil.rmtree(legacy_dir)
            print('지움:', legacy_dir.relative_to(ROOT))


def copy_sources(folder, names):
    for name in names:
        source = OWNED_ELSEWHERE.get(name) or CANON_SOURCE.get(name)
        if source is None or not source.is_file():
            raise FileNotFoundError(f'원자료 없음: {name} ({source})')
        if folder/'자료'/name != source:
            write(folder/'자료'/name, source.read_text(encoding='utf-8-sig'))
    write(folder/'자료/적용범위.md', SCOPE)


def copy_metrics(folder):
    for name, source in CANON_METRICS.items():
        target = folder/'자료/metrics'/name
        text = source.read_text(encoding='utf-8-sig')
        if name == '지표_정의.md':
            text = text.replace('`output/result.json`', '`결과/result.json`').replace('`metrics/', '`자료/metrics/')
            if folder == REVIEW:
                text = text.replace('`결과/result.json`', '`결과/조치검토결과.json`')
        if target != source or text != source.read_text(encoding='utf-8-sig'):
            write(target, text)


def reset(folder):
    """빌더가 만드는 파일만 다시 쓴다. 학생 결과 폴더의 다른 파일은 건드리지 않는다."""
    for sub in ['입력', '.github']:
        if (folder/sub).is_dir():
            shutil.rmtree(folder/sub)
    for name in ['metrics', '적용범위.md']:
        path = folder/'자료'/name
        if path.is_dir() and folder != JUDGE:
            shutil.rmtree(path)


def common_files(folder, start, extra_rules, title, intro, sections):
    text = rules_for(extra_rules)
    for name in ['AGENTS.md', 'CLAUDE.md', '.github/copilot-instructions.md']:
        write(folder/name, text)
    write(folder/'START.md', start)
    write(folder/'준비_안내.md', start)
    guide = page(title, intro, sections)
    write(folder/'guide.html', guide)
    write(folder/'안내.html', guide)


def esc(text):
    return html.escape(text)


# ───────────── 통합반 실습2: SOP 구조와 결정표 ─────────────

CRITERIA_CHECK = r'''"""결과/sop.json과 결과/rules.csv의 구조 검사. 의미 정답은 판정하지 않는다."""
from pathlib import Path
import csv, json, sys
root = Path(__file__).resolve().parent
errors = []
HEADER = ['rule_id','action','condition_index','logic','input','operator','value','unit','boundary_included','result','penalty_만원','reason','source_section']
OPS = {'>=':'예','<=':'예','>':'아니오','<':'아니오','==':'해당없음','!=':'해당없음','has_other_than':'해당없음'}
NUMERIC = {'forecast_ts1','forecast_ps1','fan100_hours'}
INPUTS = NUMERIC | {'plc_mode','plc_state','skill_kind','skill_code'}
def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)
_, targets = rows(root/'자료/targets.csv')
sop_ids = [t['sop_id'] for t in targets]
_, fms = rows(root/'자료/failuremodes.csv')
graph = json.loads((root/'입력/graph.json').read_text(encoding='utf-8-sig'))
model_ids = {n['props']['id'] for n in graph['nodes']}
def refs(value):
    if isinstance(value, str): yield value
    elif isinstance(value, list):
        for v in value: yield from refs(v)
    elif isinstance(value, dict):
        for v in value.values(): yield from refs(v)
try:
    sop = json.loads((root/'결과/sop.json').read_text(encoding='utf-8-sig'))
    fm_ids = {f['reference_id'] for f in fms} | {f.get('id') for f in sop.get('고장유형', [])}
    items = sop.get('SOP', [])
    found = [s.get('id') for s in items]
    for sid in sop_ids:
        if found.count(sid) != 1: errors.append(f'sop.json: {sid}가 {found.count(sid)}번 있습니다(1번이어야 함).')
    for s in items:
        sid = s.get('id')
        if sid not in sop_ids: errors.append(f'sop.json: targets.csv에 없는 SOP {sid}')
        if not s.get('출처'): errors.append(f'sop.json {sid}: 출처 없음')
        for key in ['적용_조건','금지_조건','수행_단계','완료_기준']:
            value = s.get(key)
            if not isinstance(value, list): errors.append(f'sop.json {sid}: {key}는 목록이어야 합니다.'); continue
            for i, item in enumerate(value, 1):
                if not isinstance(item, dict) or not item.get('내용') or not item.get('출처'):
                    errors.append(f'sop.json {sid}.{key}[{i}]: 내용·출처가 필요합니다.')
        steps = [x.get('순서') for x in s.get('수행_단계') or [] if isinstance(x, dict)]
        if not steps or steps != list(range(1, len(steps)+1)): errors.append(f'sop.json {sid}: 수행_단계 순서가 1부터 연속이 아닙니다: {steps}')
        approval = s.get('승인')
        if not isinstance(approval, dict) or not approval.get('역할') or not approval.get('출처'): errors.append(f'sop.json {sid}: 승인(역할·출처)이 필요합니다.')
        if s.get('고장유형') not in fm_ids: errors.append(f'sop.json {sid}: 고장유형 {s.get("고장유형")}을 찾을 수 없습니다.')
        for ref in refs(s.get('모델_참조', {})):
            if ref not in model_ids: errors.append(f'sop.json {sid}: 모델에 없는 ID {ref} (새 ID를 만들지 말고 미기재로 남기세요)')
        if not list(refs(s.get('모델_참조', {}))): errors.append(f'sop.json {sid}: 모델_참조가 비어 있습니다.')
    for f in sop.get('고장유형', []):
        for ref in refs(f.get('모델_참조', {})):
            if ref not in model_ids: errors.append(f'sop.json 고장유형 {f.get("id")}: 모델에 없는 ID {ref}')
except (OSError, ValueError, TypeError, AttributeError) as e:
    errors.append(f'sop.json: {e}')
groups = {}
try:
    header, table = rows(root/'결과/rules.csv')
    if header != HEADER: errors.append('rules.csv 열 이름·순서가 계약과 다릅니다: '+','.join(header or []))
    elif not table: errors.append('rules.csv에 규칙 행이 없습니다.')
    for line, r in enumerate(table if header == HEADER else [], 2):
        at = f'rules.csv:{line}'
        if r['action'] not in sop_ids: errors.append(f'{at} targets.csv에 없는 action {r["action"]}')
        if r['logic'] != 'AND': errors.append(f'{at} logic은 AND')
        if r['input'] not in INPUTS: errors.append(f'{at} 계약에 없는 input {r["input"]}')
        if r['operator'] not in OPS: errors.append(f'{at} 계약에 없는 operator {r["operator"]}')
        elif OPS[r['operator']] != r['boundary_included']: errors.append(f'{at} boundary_included({r["boundary_included"]})가 operator {r["operator"]}와 맞지 않습니다.')
        if r['result'] not in {'WARN','PENALTY','EXCLUDE'}: errors.append(f'{at} result는 WARN·PENALTY·EXCLUDE')
        if r['input'] in NUMERIC:
            try: float(r['value'])
            except ValueError: errors.append(f'{at} 숫자 입력의 기준값이 숫자가 아닙니다.')
            if not r['unit']: errors.append(f'{at} 숫자 입력의 unit이 비었습니다.')
        if r['result'] == 'PENALTY':
            try: float(r['penalty_만원'])
            except ValueError: errors.append(f'{at} PENALTY에 penalty_만원이 없습니다.')
        elif r['penalty_만원']: errors.append(f'{at} PENALTY가 아닌 행에 penalty_만원이 있습니다.')
        if not r['reason'] or not r['source_section']: errors.append(f'{at} reason·source_section이 필요합니다.')
        key = (r['rule_id'], r['action'])
        head = (r['result'], r['penalty_만원'], r['reason'], r['source_section'])
        g = groups.setdefault(key, {'head': head, 'index': []})
        if g['head'] != head: errors.append(f'{at} 같은 묶음 {key}의 result·penalty·reason·source가 다릅니다.')
        try: g['index'].append(int(r['condition_index']))
        except ValueError: errors.append(f'{at} condition_index가 정수가 아닙니다.')
    for key, g in groups.items():
        if sorted(g['index']) != list(range(1, len(g['index'])+1)): errors.append(f'rules.csv 묶음 {key}: condition_index가 1부터 연속이 아닙니다: {g["index"]}')
except (OSError, ValueError) as e:
    errors.append(f'rules.csv: {e}')
if errors:
    print('구조 확인 필요'); print('\n'.join(errors)); sys.exit(1)
print(f'구조 검사 통과: SOP {len(items)}개, 규칙 묶음 {len(groups)}개. 원문의 의미·경계·적용 대상은 결과/사례대조.md에서 원문과 별도로 대조하세요.')
'''

CRITERIA_START = '''# SOP 구조와 조치 결정표 만들기

쿨러 냉각 성능 상실에 쓰는 조치 네 개(SOP-COOL-11~14)를 원문에서 읽어, 적용 조건·금지 조건·수행 단계·완료 기준을 나눈 SOP 구조와 판단 규칙의 결정표로 만듭니다. 다음 실습의 판정 기능이 이 두 결과를 읽습니다.

## 출발점

- `입력/schema.json`, `입력/graph.json`: 이전 단계에서 완성한 설비 모델입니다. 설비·구성요소·센서·부품 ID를 그대로 재사용합니다.
- `자료/HM-8_매뉴얼.md`: SOP 원문입니다. `자료/규칙_원문.txt`: 구조화 규칙 발췌입니다. `자료/작업기준.md`: 팬 최대 운전 하나를 중심으로 정리한 이전 기준입니다. `자료/적용범위.md`: 이번에 넓힐 적용 범위입니다.
- `자료/targets.csv`: 이번 대상 SOP 네 개의 ID·종류·실행 코드입니다. `자료/failuremodes.csv`: 고장 유형입니다.
- `자료/cases.csv`: 결정표를 확인할 사례 A~M입니다. 실제 사건 기록이 아닙니다.
- `입출력_계약.md`: 두 결과 파일의 형식입니다.

이전 개인 결과가 없어도 시작할 수 있습니다. 자기 모델을 쓰려면 제공 입력은 그대로 두고 별도 폴더에 복사해 ID를 대조하세요.

## 이번에 만들 결과

- `결과/sop.json`: SOP마다 적용 조건·금지 조건·수행 단계·완료 기준·승인을 나누고 항목마다 원문 출처를 남깁니다. 고장 유형과 연결하고, 대상 설비·구성요소·센서·부품은 `입력/graph.json`의 ID로 가리킵니다. 원문에 없는 값은 지어내지 말고 미기재로 남깁니다.
- `결과/rules.csv`: 판단 규칙을 입력·연산자·기준값·단위·경계 포함 여부·결과(WARN/PENALTY/EXCLUDE)·출처로 나눕니다. 같은 규칙의 비교 여러 개는 한 묶음으로 둡니다.
- `결과/요구사항.md`: 목표·자료·제약·확인 사례와, 원문이 모호해 **사람이 정한 결정**(경계 포함 여부, 적용 대상)과 그 원문 근거.
- `결과/사례대조.md`: cases.csv의 A~M를 후보마다 결정표에 손으로 대입한 판정(유지/제외/보류)과 근거.

원문 자동 추출(인제스천) 프로그램은 만들지 않습니다. 원문을 읽고 구조를 직접 확인하는 것이 이번 과제입니다.

## 작업 순서

1. **탐색만 요청**: AI에게 파일을 바꾸지 말고 자료/·입력/을 읽어 SOP 네 개와 규칙 발췌가 어디에 있는지, 두 자료의 절 번호가 어떻게 다른지 설명하게 합니다.
2. **요구 정리**: `결과/요구사항.md`에 목표·사용할 자료·지킬 조건·확인할 사례를 자기 말로 적습니다. "이상/초과", 어느 후보에 어떤 규칙이 적용되는지처럼 모호한 부분은 AI에게 맡기지 말고 직접 원문을 읽어 정하고 근거 절과 함께 적습니다.
3. **계획 검토**: AI에게 만들 순서를 계획만 받습니다. 원문에 없는 단계·값을 추가하려는 부분, 기존 ID 대신 새 ID를 만드는 부분이 없는지 확인합니다.
4. **작은 단위로 만들기**: SOP 하나 → 나머지 SOP → 규칙 하나씩 순서로 요청합니다. 모든 항목에 원문 근거(출처 칸)를 달라고 요구합니다.
5. **원문과 대조**: `python check.py`로 구조를 확인하고, 항목마다 출처 칸의 절을 열어 문장이 같은지 확인합니다. 사례 A~M를 손으로 대입해 `결과/사례대조.md`를 씁니다.
6. **수정 요청**: 다르면 해당 항목, 원문 문장(기대), 지금 결과(실제)를 함께 주고 그 부분만 고치게 합니다.
7. **저장·재열기**: 저장한 파일을 다시 열어 확인합니다.

## 확인할 사례 종류

- 정상: 어떤 규칙도 맞지 않는 사례
- 경계: 기준값과 같은 값, 바로 위·아래 값(유온 55 ℃, 압력 165 bar, 팬 24시간)
- 복수 조건: 경고·감점·제외가 함께 맞는 사례
- 모두 제외: 후보가 모두 제외되는 사례
- 필수값 누락: 값이 빠진 사례. 제외 사유가 이미 있는 경우와 없는 경우를 구별합니다.
- 적용 대상 밖: 값이 비어 있어도 그 후보에는 해당 규칙이 적용되지 않는 사례

## 실행

```
python check.py
```

구조 검사 통과는 형식이 맞다는 뜻입니다. 경계 포함 여부, 적용 대상, 출처가 원문과 맞는지는 `결과/사례대조.md`에서 직접 대조합니다.

## 완료 조건

- `python check.py`가 통과합니다.
- 결정표의 모든 행에서 원문 문장으로 돌아갈 수 있습니다. 규칙 발췌의 시드 출처 번호와 HM-8 절 번호를 구별했습니다.
- SOP 네 개의 단계 순서·금지·승인이 원문과 같고, 원문에 없는 단계를 추가하지 않았습니다.
- 사례대조.md에 위 사례 종류마다 근거와 함께 기록이 있고, 같은 규칙의 감점을 두 번 세지 않았습니다.

## 저장과 다음 실습

결과 폴더를 저장하고 다시 열어 확인하세요. 보관할 결과는 재부팅 전에 USB 또는 개인 클라우드에 복사하세요. 다음 실습(판정 기능)은 완성된 조건표와 SOP 구조를 제공하므로 이번 결과가 없어도 시작할 수 있습니다.
'''

SOP_CONTRACT = '''## SOP 구조 sop.json

```
{
  "문서": {"id": "...", "파일": "자료/HM-8_매뉴얼.md"},
  "고장유형": [ {"id": "...", "이름": "...", "출처": "...", "모델_참조": {...}} ],
  "SOP": [
    {
      "id": "targets.csv의 SOP ID",
      "이름": "...", "종류": "control 또는 work_order", "실행코드": ["..."],
      "출처": "HM-8 절",
      "고장유형": "고장 유형 ID",
      "모델_참조": {"설비": "...", "구성요소": ["..."], "센서": ["..."]},
      "적용_조건": [ {"내용": "...", "출처": "...", "규칙": ["rule_id"]} ],
      "금지_조건": [ {"구분": "금지 또는 제한", "내용": "...", "출처": "...", "규칙": []} ],
      "수행_단계": [ {"순서": 1, "내용": "...", "출처": "..."} ],
      "완료_기준": [ {"내용": "...", "출처": "...", "규칙": []} ],
      "승인": {"역할": "...", "출처": "..."}
    }
  ]
}
```

- targets.csv의 SOP는 모두 한 번씩 있어야 한다. 단계의 순서는 원문 순서와 같다.
- `모델_참조`의 값은 `입력/graph.json`에 있는 ID만 쓴다. 모델에 없는 대상은 새 ID를 만들지 말고 `"미기재": "이유"`로 남긴다.
- 각 항목의 `출처`는 HM-8 절과 SOP 단계(예: `HM-8.5 SOP-COOL-11 단계 2`) 또는 규칙 발췌 ID다. 원문에 없는 준비 사항·값은 만들지 않는다.
- 조건과 결정표의 연결은 `규칙`에 rule_id로 적는다. 결정표가 다루지 않는 금지(예: 부하 하한)는 빈 목록으로 두고 SOP 구조에 남긴다.
- 후보 유지는 실행 허가가 아니다. 감점이 있어도 시간 제한·승인·재관측은 SOP에 그대로 남긴다.
'''


def build_criteria():
    folder = CRITERIA
    reset(folder)
    copy_sources(folder, ['HM-8_매뉴얼.md', '규칙_원문.txt', '작업기준.md', 'targets.csv', 'failuremodes.csv', 'cases.csv'])
    schema, graph = reference_model()
    dump(folder/'입력/schema.json', schema)
    dump(folder/'입력/graph.json', graph)
    write(folder/'입력/README.md', '이전 단계(온라인 2회차 모델 설계)의 완성 설비 모델입니다. 설비·구성요소·센서·부품 ID를 재사용합니다. 개인 모델을 쓰려면 이 파일은 그대로 두고 별도 폴더에 복사하세요.\n')
    write(folder/'입출력_계약.md', '# SOP 구조와 결정표의 계약\n\n두 결과는 다음 실습의 판정 기능이 그대로 읽는 입력이다. 열 이름과 키를 바꾸면 다음 단계에서 읽지 못한다.\n\n'+SOP_CONTRACT+'\n'+TABLE_CONTRACT+'\n'+JUDGE_RULES.replace('## 판정 규칙', '## 사례 대조에 쓰는 판정 규칙')+'\n## 원본과 결과\n\n입력/·자료/는 보존한다. 결과는 결과/에만 쓴다. 실제 설비·평가 함수를 실행하지 않는다.\n')
    write(folder/'check.py', CRITERIA_CHECK)
    write(folder/'결과/README.md', 'sop.json, rules.csv, 요구사항.md, 사례대조.md를 여기에 저장합니다.\n')
    keep(folder/'결과/sop.json', json.dumps({'문서': {'id': 'HM-8', '파일': '자료/HM-8_매뉴얼.md'}, '고장유형': [], 'SOP': []}, ensure_ascii=False, indent=2)+'\n')
    keep(folder/'결과/rules.csv', 'rule_id,action,condition_index,logic,input,operator,value,unit,boundary_included,result,penalty_만원,reason,source_section\n')
    keep(folder/'결과/요구사항.md', '# 이번에 만들 결과\n\n## 목표\n\n## 사용할 자료와 범위\n\n## 지킬 조건\n\n## 사람이 원문으로 정한 결정\n\n| 모호한 점(경계·적용 대상) | 정한 내용 | 원문 근거(파일·절·문장) |\n|---|---|---|\n| | | |\n\n## 확인할 사례와 기대 결과의 근거\n')
    keep(folder/'결과/사례대조.md', '# 사례 대조\n\n결정표를 손으로 대입한 예상입니다. 근거에는 결정표의 rule_id와 원문 절을 적습니다.\n\n| 사례 | 후보 | 일치 규칙 | 경고 | 감점(만원) | 제외 사유 | 미확인 입력 | 판정 | 근거 |\n|---|---|---|---|---:|---|---|---|---|\n| | | | | | | | | |\n\n## 원문과 다르게 정한 점·확인하지 못한 점\n')
    sections = [
        ('시작하기', '<p>VS Code에서 이 폴더를 열고 <a href="START.md">START.md</a>와 <a href="입출력_계약.md">입출력_계약.md</a>를 읽으세요.</p><pre>입력/   이전 단계 완성 설비 모델(schema.json, graph.json)\n자료/   HM-8 매뉴얼, 규칙 발췌, 작업기준, 적용범위, 대상·고장 유형·사례\n결과/   이번에 만들 sop.json, rules.csv, 요구사항.md, 사례대조.md\ncheck.py   구조 검사</pre><p>이전 개인 결과가 없어도 됩니다. 제공 모델의 ID를 그대로 재사용합니다.</p>'),
        ('요구 정하기', '<p>먼저 AI에게 <b>파일을 바꾸지 말고</b> 자료/와 입력/을 읽어 SOP 네 개, 규칙 발췌, 두 자료의 절 번호 차이를 설명하게 하세요. 설명은 실제 파일과 대조합니다.</p><p>그다음 결과/요구사항.md에 자기 말로 적습니다.</p><ul><li>무엇을 만드는가: SOP 네 개의 구조와 판단 규칙의 결정표</li><li>어떤 자료를 쓰는가: HM-8 원문과 규칙 발췌</li><li>지킬 조건: 원문에 없는 단계·값을 만들지 않는다, 기존 모델 ID를 재사용한다, 자동 추출 프로그램은 만들지 않는다</li><li>확인할 사례: 정상·경계·복수 조건·모두 제외·필수값 누락·적용 대상 밖</li></ul><p class="check">이번 실습의 판단 지점: "55 ℃ 이상"이 55.0을 포함하는지, 팬 감점이 어느 후보에 붙는지처럼 모호한 경계와 적용 대상은 <b>AI가 아니라 사람이 원문을 읽고 정해</b> 근거 절과 함께 요구사항.md에 적습니다. AI에게는 그 결정을 전달합니다.</p>'),
        ('AI와 만들기', '<p>먼저 만들 순서를 계획으로만 받아 검토하세요. 원문에 없는 단계를 넣거나 기존 ID 대신 새 ID를 만들려는 부분이 있으면 계획 단계에서 고칩니다.</p><ol><li>SOP-COOL-11 하나의 구조를 먼저 만들고 원문 단계와 한 줄씩 대조합니다. 맞으면 나머지 SOP로 넓힙니다.</li><li>결정표는 규칙 하나씩 만듭니다. 같은 규칙의 비교 두 개는 한 묶음으로 둡니다.</li><li>모든 항목과 행에 <b>원문 근거 칸(출처)</b>을 채우게 요구합니다. 근거를 못 대는 항목은 지우거나 미기재로 둡니다.</li></ol><details><summary>요청을 정리할 때 볼 항목</summary><p>만들 결과 / 참고할 자료 / 사람이 정한 경계·적용 대상 / 바꾸지 않을 범위 / 출처 칸 요구 / 성공을 확인할 사례</p></details>'),
        ('결과 확인하기', '<pre>python check.py</pre><p>구조 검사가 통과한 뒤 사례 A~M를 결정표에 대입해 결과/사례대조.md를 채웁니다. 판단 기준은 다음과 같습니다.</p><ul><li>원문이 "55 ℃ 이상"이면 55.0은 포함, "165 bar 미만"이면 165.0은 포함하지 않습니다. "24시간을 넘으면"은 24.0을 포함하지 않습니다.</li><li>사례 F처럼 여러 규칙이 함께 맞으면 경고·감점·제외를 모두 남깁니다. 제외됐다고 경고를 지우지 않습니다.</li><li>사례 K처럼 값이 빠졌어도 이미 확인된 제외 사유가 있으면 제외하면서 빠진 값을 함께 적습니다. 제외 사유 없이 값이 빠진 사례 H·L은 보류입니다.</li><li>사례 M의 작업지시 후보는 원격 모드·팬 시간 규칙의 대상이 아니므로 그 칸이 비어 있어도 보류하지 않습니다.</li></ul><p class="check">결과가 예상과 다르면 결정표가 원문과 다른지, 손으로 대입한 예상이 틀렸는지 원문으로 돌아가 확인하세요. 고칠 때는 해당 항목, 원문 문장(기대), 지금 결과(실제)를 함께 AI에 전달하고 그 부분만 고치게 합니다. AI의 완료 메시지는 대조를 대신하지 않습니다.</p>'),
        ('저장하기', '<p>결과/sop.json, 결과/rules.csv, 결과/요구사항.md, 결과/사례대조.md를 저장하고 다시 열어 확인하세요. 보관할 결과는 재부팅 전에 USB 또는 개인 클라우드에 복사합니다.</p><p>다음 실습(판정 기능)은 완성된 조건표와 SOP 구조를 제공합니다. 자기 결과를 쓰고 싶으면 다음 실습의 제공 입력을 보존하고 별도 폴더에서 대조하세요.</p>')]
    common_files(folder, CRITERIA_START, ['이번 실습은 원문 자동 추출(인제스천) 프로그램을 만들지 않는다. 원문을 읽어 구조와 결정표를 작성한다.', '입력/graph.json에 없는 대상은 새 ID를 만들지 않고 미기재로 남긴다.'], 'SOP 구조와 조치 결정표 만들기', '조치 원문을 적용 조건·금지 조건·수행 단계·완료 기준으로 나누고, 판단 규칙을 결정표로 만듭니다. 사례 A~M로 경계·복수 조건·누락을 확인합니다.', sections)


def keep(path, text):
    """학생 결과 틀. 이미 있으면 덮어쓰지 않는다(빌드 재실행이 작업을 지우지 않게)."""
    if not path.exists():
        write(path, text)


# ───────────── 판정 기능 공통 입력 ─────────────

def judge_inputs(folder):
    copy_sources(folder, ['HM-8_매뉴얼.md', '규칙_원문.txt', '작업기준.md', 'targets.csv', 'cases.csv'])
    copy_metrics(folder)
    for name in ['rules.csv', 'sop.json']:
        source = REFERENCE/name
        if not source.is_file():
            raise FileNotFoundError(f'이전 단계 완성본 없음: {source}')
        write(folder/'입력'/name, source.read_text(encoding='utf-8-sig'))
    write(folder/'입력/README.md', f'이전 단계(SOP 구조와 결정표)의 완성본입니다. 판본 {VERSION}. rules.csv는 조건표, sop.json은 SOP 구조입니다.\n\n이 파일을 고치지 말고 읽기만 하세요. 자기 조건표를 쓰려면 이 파일은 그대로 두고 별도 폴더에 두어 열 이름이 입출력_계약.md와 같은지 먼저 확인하세요.\n')


JUDGE_CHECK_COMMON = r'''from pathlib import Path
import csv, json, re, sys
root = Path(__file__).resolve().parent
errors = []
def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as f: return list(csv.DictReader(f))
cases = {r['case']: r['candidate_sops'].split(';') for r in rows(root/'자료/cases.csv')}
requests = {q['번호']: [c['sop'] for c in q['후보']] for q in json.loads((root/'자료/metrics/판정_요청.json').read_text(encoding='utf-8-sig'))['요청']}
rule_actions = {(r['rule_id'], r['action']) for r in rows(root/'입력/rules.csv')}
STATUS = {'유지','제외','보류'}
def num(x): return isinstance(x, (int, float)) and not isinstance(x, bool)
'''

JUDGE_CHECK = '"""결과/result.json의 구조와 계약 불변식 검사. 어떤 규칙이 맞아야 하는지·금액은 판정하지 않는다."""\n'+JUDGE_CHECK_COMMON+r'''
try:
    result = json.loads((root/'결과/result.json').read_text(encoding='utf-8-sig'))
    if not isinstance(result.get('comparison_basis'), str) or not result['comparison_basis'].strip(): errors.append('comparison_basis(교육용 비교값과 HYD 점수의 구분 문장)가 없습니다.')
    for kind, expected in [('cases', cases), ('requests', requests)]:
        entries = result.get(kind)
        if not isinstance(entries, list): errors.append(f'{kind} 목록이 없습니다.'); continue
        got = [e.get('id') for e in entries]
        if sorted(got) != sorted(expected): errors.append(f'{kind}: 입력의 {sorted(expected)}와 결과의 {sorted(got)}가 다릅니다.')
        for e in entries:
            eid = e.get('id'); cands = e.get('candidates', [])
            if eid in expected and [c.get('sop') for c in cands] != expected[eid]: errors.append(f'{eid}: 후보 목록이 입력 순서·구성과 다릅니다.')
            for c in cands:
                at = f'{eid}/{c.get("sop")}'
                if c.get('status') not in STATUS: errors.append(f'{at}: status는 유지·제외·보류'); continue
                lists = {k: c.get(k) for k in ['warnings','penalties','exclusions','unknown']}
                if any(not isinstance(v, list) for v in lists.values()): errors.append(f'{at}: warnings·penalties·exclusions·unknown은 목록'); continue
                for k in ['warnings','penalties','exclusions']:
                    for h in lists[k]:
                        if (h.get('rule_id'), c.get('sop')) not in rule_actions: errors.append(f'{at}: 조건표에 없는 규칙·후보 {h.get("rule_id")}')
                        if not h.get('source_section') or not isinstance(h.get('conditions'), list) or not h['conditions']: errors.append(f'{at} {h.get("rule_id")}: source_section과 conditions(실제 입력·비교)가 필요')
                for h in lists['penalties']:
                    if not num(h.get('amount_만원')): errors.append(f'{at} {h.get("rule_id")}: amount_만원 숫자 필요')
                for u in lists['unknown']:
                    if not u.get('missing'): errors.append(f'{at} {u.get("rule_id")}: unknown에는 빠진 입력 이름(missing)이 필요')
                expected_status = '제외' if lists['exclusions'] else ('보류' if lists['unknown'] else '유지')
                if c['status'] != expected_status: errors.append(f'{at}: status {c["status"]}가 계약(제외>보류>유지)과 다릅니다. 기대 {expected_status}')
            if kind == 'cases':
                allowed = [c.get('sop') for c in cands if c.get('status') == '유지']
                if e.get('allowed') != allowed: errors.append(f'{eid}: allowed는 유지 후보 목록이어야 합니다.')
                if not allowed and not e.get('no_allowed_reason'): errors.append(f'{eid}: 유지 후보가 없으면 no_allowed_reason이 필요합니다.')
            else:
                for c in cands:
                    at = f'{eid}/{c.get("sop")}'; comp = c.get('comparison')
                    if c.get('status') != '유지':
                        if comp: errors.append(f'{at}: 유지가 아닌 후보에 비교값이 있습니다.')
                    elif comp is None:
                        if not c.get('comparison_unavailable'): errors.append(f'{at}: 비교값이 없으면 comparison_unavailable 이유가 필요합니다.')
                    else:
                        keys = ['비용','생산','품질','에너지','감점','합계']
                        if not all(num(comp.get(k)) for k in keys): errors.append(f'{at}: 비교값에 {keys}가 숫자로 필요합니다.'); continue
                        if abs(sum(comp[k] for k in keys[:5]) - comp['합계']) > 0.02: errors.append(f'{at}: 합계가 네 손실+감점과 다릅니다.')
                        if abs(sum(p['amount_만원'] for p in c.get('penalties', []) if num(p.get('amount_만원'))) - comp['감점']) > 0.001: errors.append(f'{at}: 감점이 penalties 금액 합과 다릅니다.')
                ranking = e.get('ranking'); rec = e.get('recommendation') or {}
                if not isinstance(ranking, list): errors.append(f'{eid}: ranking 목록 필요'); continue
                kept = {c.get('sop'): c for c in cands if c.get('status') == '유지' and c.get('comparison')}
                if sorted(r.get('sop') for r in ranking) != sorted(kept): errors.append(f'{eid}: ranking에는 비교값이 있는 유지 후보만 모두 있어야 합니다.')
                totals = [r.get('합계') for r in ranking]
                if totals != sorted(totals): errors.append(f'{eid}: ranking이 합계 오름차순이 아닙니다.')
                for i, r in enumerate(ranking):
                    tie = i > 0 and ranking[i-1].get('합계') == r.get('합계')
                    if r.get('rank') != (ranking[i-1].get('rank') if tie else i+1): errors.append(f'{eid}: 순위 {r.get("sop")}가 동순위 규칙(1,1,3)과 다릅니다.')
                top = sorted(r.get('sop') for r in ranking if r.get('rank') == 1)
                if sorted(rec.get('sops') or []) != top: errors.append(f'{eid}: recommendation.sops는 1위 유지 후보여야 합니다.')
                if not rec.get('reason'): errors.append(f'{eid}: recommendation.reason이 필요합니다.')
except (OSError, ValueError, TypeError, AttributeError) as e:
    errors.append(f'result.json: {e}')
if errors:
    print('구조 확인 필요'); print('\n'.join(errors)); sys.exit(1)
print(f'구조 검사 통과: 사례 {len(cases)}건, 요청 {len(requests)}건. 어떤 규칙이 맞아야 하는지와 금액은 원문·지표_정의.md 손계산과 별도로 대조하세요.')
'''

JUDGE_CONTRACT = '''# 판정 기능의 입출력 계약

## 입력

- `입력/rules.csv`: 이전 단계 완성 조건표. 열의 뜻은 아래 「조건표 읽는 법」을 따른다. 규칙을 코드에 다시 적어 고정하지 않고 이 파일에서 읽는다. 조건표 형식이 계약과 다르면(열 누락, 같은 묶음의 결과가 다름 등) 파일·행을 밝혀 실패한다.
- `입력/sop.json`: 이전 단계 완성 SOP 구조(적용 조건·금지 조건·수행 단계·완료 기준·승인·출처).
- `자료/targets.csv`: 후보의 종류(kind)와 실행 코드 목록.
- `자료/cases.csv`: 판정 확인 사례 A~M. 한 사례의 후보는 같은 예측값을 쓴다.
- `자료/metrics/판정_요청.json`: 비교 요청 C01~C14. 후보마다 예측값이 다르다. `자료/metrics/업무_값.json`, `후보_설정.csv`, `지표_정의.md`: 교육용 비교 입력과 식.

'''+TABLE_CONTRACT.replace('## 결정표 rules.csv', '## 조건표 읽는 법').replace('예시 한 줄(형식만 보여 주는 가상의 행이며 정답 행이 아니다):\n\n```\nR0,SOP-COOL-00,1,AND,forecast_ts1,>=,0,℃,예,WARN,,이유 문장,근거 절\n```\n', '')+'\n'+JUDGE_RULES+'\n'+COMPARE_RULES


def judge_contract_result():
    return '''
## 출력 결과/result.json

```
{
  "comparison_basis": "교육용 비교값과 HYD 일곱 성분 점수의 구분 문장",
  "cases": [
    {"id": "A", "candidates": [후보 판정], "allowed": ["유지 후보"], "no_allowed_reason": "유지 후보가 없을 때만"}
  ],
  "requests": [
    {"id": "C01", "candidates": [후보 판정 + 비교],
     "ranking": [{"rank": 1, "sop": "...", "합계": 0.0}],
     "recommendation": {"sops": ["1위 유지 후보"], "reason": "...", "held": ["보류 후보"]}}
  ]
}
```

후보 판정:

```
{"sop": "SOP-COOL-11", "status": "유지 | 제외 | 보류",
 "warnings":   [{"rule_id": "...", "reason": "...", "source_section": "...", "conditions": [{"input": "...", "actual": 값, "operator": "...", "value": "...", "unit": "..."}]}],
 "penalties":  [{... 위와 같음, "amount_만원": 숫자}],
 "exclusions": [{... 위와 같음}],
 "unknown":    [{"rule_id": "...", "result": "...", "missing": ["빠진 입력"], "source_section": "..."}],
 "comparison": {"비용": 0, "생산": 0, "품질": 0, "에너지": 0, "감점": 0, "합계": 0} 또는 null,
 "comparison_unavailable": ["계산하지 못한 이유"]}
```

- `cases`와 `requests`의 순서·후보 순서는 입력과 같다. `comparison`은 요청의 유지 후보에만 있다.
- 실행 결과와 별도로 `결과/기대결과.md`에 실행 전 원문으로 적은 기대, 실제 결과, 차이와 수정을 남긴다.
'''


JUDGE_START = '''# 조건표를 읽는 조치 판정·비교 기능 만들기

제공된 완성 조건표와 SOP 구조를 읽어, 조치 후보마다 유지·제외·보류를 이유와 함께 판정하고, 허용된 후보만 교육용 손실 산식으로 비교하는 프로그램을 만듭니다.

## 출발점

- `입력/rules.csv`, `입력/sop.json`: 이전 단계(SOP 구조와 결정표)의 완성본입니다. 이번 프로그램의 기준입니다. 고치지 말고 읽기만 합니다.
- `자료/cases.csv`: 판정 확인 사례 A~M. `자료/metrics/판정_요청.json`: 비교 요청 C01~C14.
- `자료/metrics/지표_정의.md`·`업무_값.json`·`후보_설정.csv`: 교육용 비용·생산·품질·에너지 손실 식과 값.
- `자료/targets.csv`, `자료/HM-8_매뉴얼.md`, `자료/규칙_원문.txt`: 후보 정보와 원문.
- `입출력_계약.md`: 판정 규칙과 결과 형식. `check.py`: 결과의 구조 검사.

이전 개인 결과가 없어도 시작할 수 있습니다.

## 직접 구현할 것

`결과/judge.py`를 만들어 실행하면 `결과/result.json`이 생기게 합니다.

1. 조건표를 읽어 규칙 묶음(rule_id·action)을 만듭니다. 규칙을 코드에 다시 적지 않습니다.
2. 사례·요청마다 후보의 입력을 만듭니다. 이름 변환과 빈 값 처리는 계약을 따릅니다.
3. 후보마다 적용 대상인 규칙만 평가해 경고·감점·제외·미확인을 모으고 유지·제외·보류를 판정합니다.
4. 요청 C01~C14에서 유지 후보만 네 손실과 감점을 더해 비교하고 순위를 매깁니다. 유지 후보가 없으면 추천 없이 이유를 남깁니다.
5. 결과에 교육용 비교값과 실제 HYD 성과 점수(일곱 성분)의 구분을 문장으로 남깁니다.

## 작업 순서

1. **탐색만 요청**: AI에게 파일을 바꾸지 말고 입력/·자료/·입출력_계약.md를 읽어 입력 형식, 조건표의 묶음 방식, 결과 형식을 설명하게 합니다. 설명을 실제 파일과 대조합니다.
2. **기대 결과 먼저**: 코드를 만들기 전에 `결과/기대결과.md`에 아래 사례 종류마다 하나 이상, 조건표와 원문으로 손으로 구한 기대 판정과 근거를 적습니다. 구현 출력을 복사해 기대값을 만들지 않습니다.
3. **요구 정리와 계획 검토**: 목표·입력·제약·확인 사례를 자기 말로 AI에 전달하고 구현 계획만 먼저 받습니다. 규칙을 코드에 고정하는 계획, 첫 일치에서 멈추는 계획, 빈 값을 0으로 바꾸는 계획이 없는지 봅니다.
4. **작은 단위로 구현**: 판정(사례 A~M) → 비교(C01~C14) → 저장 순서로 하나씩 만들고 실행합니다.
5. **기대와 실제 대조**: 실행 결과를 기대결과.md의 기대 칸과 한 줄씩 대조합니다.
6. **수정 요청**: 다르면 입력(사례·후보), 기대(원문 근거), 실제(출력)를 함께 주고 원인을 찾게 합니다. 기대가 틀렸다면 원문 근거로 고친 이유를 남기고, 결과에 맞추려고 기대를 바꾸지 않습니다.
7. **저장·재열기**: 저장한 파일을 다시 열어 확인합니다.

## 실행

```
python 결과/judge.py
python check.py
```

## 기대 결과를 먼저 적을 사례 종류

- 정상: 규칙이 맞지 않는 후보
- 경계: 유온 54.9·55·55.1 ℃, 압력 164.9·165·165.1 bar, 팬 23.9·24·24.1 h
- 복수 조건: 경고·감점·제외가 함께 맞는 후보. 감점이 묶음당 한 번인지
- 모두 제외: 유지 후보가 하나도 없는 사례·요청
- 필수값 누락: 제외 사유가 있는 누락과 없는 누락, 적용 대상 밖의 빈 값
- 비교: 지표_정의.md의 C01 손계산과 프로그램 결과

## 완료 조건

- `python 결과/judge.py`가 사례 13건과 요청 14건을 모두 처리하고 `python check.py`가 통과합니다.
- C01 SOP-COOL-12의 네 손실이 지표_정의.md의 손계산과 같습니다.
- 기대결과.md에 위 사례 종류마다 실행 전에 적은 기대·근거와 실행 후 실제가 있고, 차이가 있었다면 원인(조건표 해석·입력 변환·계산식)과 수정을 적었습니다.
- 결과를 맞추려고 조건표·원자료·기대를 바꾸지 않았습니다.

## 저장과 다음 실습

결과 폴더를 저장하고 다시 열어 확인하세요. 보관할 결과는 재부팅 전에 USB 또는 개인 클라우드에 복사하세요. 다음 회차에는 조건의 원문 근거를 다시 검토합니다.
'''


EXPECT_TEMPLATE = '''# 기대 결과와 실제 대조

기대 칸은 프로그램을 실행하기 **전에** 조건표(입력/rules.csv)와 원문으로 손으로 구해 적습니다. 실제 칸은 실행 후에 적습니다. 실제 출력을 복사해 기대 칸을 채우지 않습니다.

- 실행한 명령:
- 실행 시각:
- 사용한 입력 판본: 입력/README.md

| 사례·요청 / 후보 | 사례 종류 | 기대 판정·이유 | 근거(rule_id·원문 절) | 실제 결과 | 일치 / 차이와 수정 |
|---|---|---|---|---|---|
| | | | | | |

## C01 손계산 대조

## 기대를 고친 경우(원문 근거와 이유)

## 남은 미확인
'''


def build_judge():
    folder = JUDGE
    reset(folder)
    judge_inputs(folder)
    write(folder/'입출력_계약.md', JUDGE_CONTRACT+judge_contract_result())
    write(folder/'check.py', JUDGE_CHECK)
    write(folder/'결과/README.md', 'judge.py, result.json, 기대결과.md를 여기에 저장합니다.\n')
    keep(folder/'결과/기대결과.md', EXPECT_TEMPLATE)
    sections = [
        ('시작하기', '<p>VS Code에서 이 폴더를 열고 <a href="START.md">START.md</a>와 <a href="입출력_계약.md">입출력_계약.md</a>를 읽으세요.</p><pre>입력/   이전 단계 완성 조건표(rules.csv)와 SOP 구조(sop.json)\n자료/   사례 A~M, 대상 후보, 원문, metrics/의 비교 요청 C01~C14와 손실 식\n결과/   이번에 만들 judge.py, result.json, 기대결과.md\ncheck.py   결과 구조 검사</pre><p>입력/의 조건표가 이번 프로그램의 기준입니다. 고치지 말고 읽기만 합니다.</p><p>먼저 AI에게 <b>파일을 바꾸지 말고</b> 입력 형식·조건표의 묶음 방식·결과 형식을 설명하게 하고, 그 설명을 실제 파일과 대조하세요.</p>'),
        ('요구 정하기', '<p class="check">이번 실습의 판단 지점: <b>기대 결과를 원문에서 먼저 적습니다.</b> 코드를 만들기 전에 결과/기대결과.md에 사례 종류마다 하나 이상, 조건표와 원문으로 손으로 구한 판정과 근거를 적으세요. 프로그램 출력을 보고 기대 칸을 채우면 검증이 되지 않습니다.</p><p>그다음 AI에게 전달할 요구를 자기 말로 정리합니다.</p><ul><li>입력 이름 변환: forecast_ts1_C → forecast_ts1, RUN → RUNNING, workorder → work_order</li><li>판정 순서: 적용 대상 → AND 묶음 → 결과 모으기 → 제외·보류·유지</li><li>비교: 유지 후보만, 네 손실 + 감점, 동순위, 계산 불가</li></ul>'),
        ('AI와 만들기', '<p>구현 전에 계획만 받아 검토하세요. 규칙을 코드에 다시 적는 계획, 첫 일치에서 멈추는 계획, 빈 값을 0으로 바꾸는 계획, 감점을 행마다 더하는 계획이 있으면 계획 단계에서 고칩니다.</p><ol><li>사례 A~M의 판정부터 만들고 실행합니다.</li><li>판정이 기대와 맞으면 C01~C14 비교를 붙이고 C01 손계산과 대조합니다.</li><li>마지막으로 결과 형식과 저장을 맞춥니다.</li></ol><details><summary>요청을 정리할 때 볼 항목</summary><p>만들 결과 / 참고할 자료 / 바꾸지 않을 범위 / 이번 단계의 범위 / 성공을 확인할 사례</p></details>'),
        ('결과 확인하기', '<pre>python 결과/judge.py\npython check.py</pre><p>구조 검사는 형식과 계약의 불변식만 봅니다. 판정이 맞는지는 다음 기준으로 원문과 대조하세요.</p><ul><li>경계: C03처럼 팬이 정확히 24시간이면 감점이 없고, C04의 24.1시간이면 팬 최대 운전 후보(SOP-COOL-11·12)에만 20만 원 감점이 붙습니다. 부하 감소 후보에는 붙지 않습니다.</li><li>복수 조건: 사례 F는 경고·감점·제외가 함께 남습니다. 감점은 조건 행 수와 관계없이 규칙당 한 번입니다.</li><li>누락: C13처럼 팬 운전 시간을 모르면 그 값이 필요한 후보만 보류되고, 관련 없는 후보까지 보류되지 않습니다.</li><li>모두 제외: 유지 후보가 없는 요청에서는 추천이 비고 이유가 남습니다.</li><li>비교: C01 SOP-COOL-12는 지표_정의.md의 손계산(비용 3.86, 생산 33.33, 품질 0, 에너지 0.54)과 같아야 합니다.</li></ul><p class="check">기대결과.md의 기대 칸과 실제 출력을 한 줄씩 대조하세요. 다르면 입력(사례·후보), 기대(원문 근거), 실제(출력)를 함께 AI에 주고 원인을 찾게 한 뒤 필요한 부분만 고칩니다. 같은 사례와 이미 맞았던 사례를 다시 실행합니다.</p>'),
        ('저장하기', '<p>결과/judge.py, 결과/result.json, 결과/기대결과.md를 저장하고 다시 열어 확인하세요. 보관할 결과는 재부팅 전에 USB 또는 개인 클라우드에 복사합니다.</p><p>비교 합계는 교육용 비교값입니다. 실제 HYD 성과 점수와 다르며 순위가 실행 승인을 뜻하지 않습니다.</p>')]
    common_files(folder, JUDGE_START, ['입력/rules.csv의 규칙을 코드에 다시 적어 고정하지 않는다. 조건표를 읽어 판정한다.', '빈 값을 0이나 정상값으로 채우지 않는다. 결과를 맞추려고 조건표·원자료·기대를 바꾸지 않는다.'], '조건표를 읽는 조치 판정·비교 기능 만들기', '완성 조건표로 후보별 경고·감점·제외·정보 부족을 판정하고, 허용 후보만 교육용 손실로 비교합니다.', sections)


# ───────────── 실전반 실습2: 조치 검토 결과 ─────────────

REVIEW_CHECK = '"""결과/조치검토결과.json·.md의 구조와 계약 불변식 검사. 판정의 의미 정답은 판정하지 않는다."""\n'+JUDGE_CHECK_COMMON+r'''
try:
    review = json.loads((root/'결과/조치검토결과.json').read_text(encoding='utf-8-sig'))
    md = (root/'결과/조치검토결과.md').read_text(encoding='utf-8-sig')
    if not str(review.get('비교_기준', '')).strip(): errors.append('비교_기준(교육용 비교값과 HYD 점수·실행 승인의 구분 문장)이 없습니다.')
    items = review.get('항목')
    if not isinstance(items, list): raise ValueError('항목 목록이 없습니다.')
    expected = {**{k: ('사례', v) for k, v in cases.items()}, **{k: ('요청', v) for k, v in requests.items()}}
    got = [i.get('id') for i in items]
    if sorted(got) != sorted(expected): errors.append(f'항목 id가 입력과 다릅니다: {sorted(set(expected) ^ set(got))}')
    for item in items:
        iid = item.get('id')
        if iid not in expected: continue
        kind, sops = expected[iid]
        if item.get('종류') != kind: errors.append(f'{iid}: 종류는 {kind}')
        cands = item.get('후보', [])
        if [c.get('sop') for c in cands] != sops: errors.append(f'{iid}: 후보 목록이 입력과 다릅니다.')
        if not re.search(r'^#+\s.*(?<![A-Za-z0-9])'+re.escape(iid)+r'(?![A-Za-z0-9])', md, re.M): errors.append(f'조치검토결과.md에 {iid} 절 제목이 없습니다.')
        for c in cands:
            at = f'{iid}/{c.get("sop")}'
            status = c.get('판정')
            if status not in STATUS: errors.append(f'{at}: 판정은 유지·제외·보류'); continue
            reasons = c.get('이유')
            if not isinstance(reasons, list): errors.append(f'{at}: 이유 목록 필요'); continue
            for r in reasons:
                if (r.get('규칙'), c.get('sop')) not in rule_actions: errors.append(f'{at}: 조건표에 없는 규칙·후보 {r.get("규칙")}')
                if r.get('결과') not in {'WARN','PENALTY','EXCLUDE','미확인'}: errors.append(f'{at}: 이유의 결과는 WARN·PENALTY·EXCLUDE·미확인')
                if not r.get('비교') or not r.get('출처') or not isinstance(r.get('실제_입력'), dict): errors.append(f'{at} {r.get("규칙")}: 실제_입력·비교·출처가 필요합니다.')
            kinds = {r.get('결과') for r in reasons}
            if status == '제외' and 'EXCLUDE' not in kinds: errors.append(f'{at}: 제외인데 EXCLUDE 이유가 없습니다.')
            if status == '보류' and ('EXCLUDE' in kinds or '미확인' not in kinds): errors.append(f'{at}: 보류는 제외 없이 미확인 이유가 있어야 합니다.')
            if status == '유지' and kinds & {'EXCLUDE', '미확인'}: errors.append(f'{at}: 유지인데 제외·미확인 이유가 있습니다.')
            if not c.get('원문_출처'): errors.append(f'{at}: 원문_출처가 비었습니다.')
            checks = c.get('추가_확인')
            if not isinstance(checks, list) or (status == '보류' and not checks): errors.append(f'{at}: 추가_확인 목록이 필요하고 보류 후보는 비어 있으면 안 됩니다.')
            missing = [m for r in reasons if r.get('결과') == '미확인' for m in r.get('빠진_입력', [])]
            if any(not any(m in str(x) for x in checks or []) for m in missing): errors.append(f'{at}: 빠진 입력 {missing}이 추가_확인에 없습니다.')
            approval = c.get('승인') or {}
            if not approval.get('역할') or not approval.get('출처') or not approval.get('안내'): errors.append(f'{at}: 승인(역할·출처·안내)이 필요합니다.')
            value, rank = c.get('비교값'), c.get('순위')
            if kind == '사례' or status != '유지':
                if value or rank is not None: errors.append(f'{at}: 비교값·순위는 요청의 유지 후보에만 둡니다.')
            elif value is not None:
                keys = ['비용','생산','품질','에너지','감점','합계']
                if not all(num(value.get(k)) for k in keys): errors.append(f'{at}: 비교값에 {keys}가 숫자로 필요합니다.')
                elif abs(sum(value[k] for k in keys[:5]) - value['합계']) > 0.02: errors.append(f'{at}: 합계가 네 손실+감점과 다릅니다.')
        opinion = item.get('검토_의견') or {}
        kept = [c for c in cands if c.get('판정') == '유지' and c.get('순위') is not None]
        top = sorted(c['sop'] for c in kept if c['순위'] == 1)
        if kind == '요청' and sorted(opinion.get('추천') or []) != top: errors.append(f'{iid}: 추천은 순위 1위 유지 후보여야 합니다.')
        if kind == '사례' and opinion.get('추천'): errors.append(f'{iid}: 사례 A~M는 비교하지 않으므로 추천을 두지 않습니다.')
        if not opinion.get('사유'): errors.append(f'{iid}: 검토_의견.사유가 필요합니다.')
except (OSError, ValueError, TypeError, AttributeError) as e:
    errors.append(f'조치검토결과: {e}')
if errors:
    print('구조 확인 필요'); print('\n'.join(errors)); sys.exit(1)
print(f'구조 검사 통과: 사례 {len(cases)}건, 요청 {len(requests)}건. 판정·이유·출처가 원문과 맞는지와 금액은 별도로 대조하세요.')
'''

REVIEW_START = '''# 후보별 조치 검토 결과 만들기

제공된 완성 조건표에서 출발해 조치 후보마다 판정과 이유를 내고, 허용된 후보만 교육용 손실 산식으로 비교한 **조치 검토 결과**를 만듭니다. 담당자가 이 결과를 읽고 어느 후보를 승인 요청할지, 무엇을 더 확인할지 결정할 수 있어야 합니다. 검토 결과의 순위는 실행 승인이 아닙니다.

## 출발점

- `입력/rules.csv`: 이전 단계 완성 조건표입니다. 지난 회차 실습5(조치 조건표)에서 팬 최대 운전 하나로 정리한 규칙을 SOP 네 개로 넓힌 판본입니다. 고치지 말고 읽기만 합니다.
- `입력/sop.json`: 이전 단계 완성 SOP 구조입니다. 적용 조건·금지 조건·수행 단계·완료 기준·승인과 원문 출처가 있습니다.
- `자료/cases.csv`: 판정 확인 사례 A~M. `자료/metrics/판정_요청.json`: 비교 요청 C01~C14.
- `자료/metrics/지표_정의.md`·`업무_값.json`·`후보_설정.csv`: 교육용 손실 식과 값.
- `자료/targets.csv`, `자료/HM-8_매뉴얼.md`, `자료/규칙_원문.txt`: 후보 정보와 원문.
- `입출력_계약.md`: 판정 규칙과 결과 형식. `check.py`: 결과의 구조 검사.

지난 회차 결과가 없어도 시작할 수 있습니다.

## 직접 구현할 것

`결과/review.py`를 만들어 실행하면 `결과/조치검토결과.json`과 사람이 읽을 `결과/조치검토결과.md`가 생기게 합니다.

후보마다 다음을 담습니다.

| 항목 | 내용 |
|---|---|
| 판정 | 유지 · 제외 · 보류 |
| 이유 | 맞은 규칙과 미확인 규칙마다 규칙 ID, 실제 입력값, 비교식, 결과 종류(경고·감점·제외·미확인) |
| 원문 출처 | 이유에 쓴 규칙의 출처와 후보 SOP의 HM-8 절 |
| 추가로 확인할 값 | 빠진 입력과 그 값이 판정을 어떻게 바꿀 수 있는지. 유지 후보는 실행 전에 확인할 조건·완료 기준(sop.json) |
| 비교값·순위 | 요청 C01~C14의 유지 후보만. 비용·생산·품질·에너지·감점·합계와 순위 |
| 승인 | 실행 승인 역할과 출처, 그리고 "비교 순위는 실행 승인이 아니다"라는 안내 |

사례·요청마다 검토 의견(추천 후보 또는 추천 없음과 그 이유, 보류 후보)을 남깁니다. 결과에는 교육용 비교값과 실제 HYD 성과 점수(일곱 성분)를 구분하는 문장을 넣습니다.

## 작업 순서

1. **탐색만 요청**: AI에게 파일을 바꾸지 말고 입력/·자료/·입출력_계약.md를 읽어 조건표와 SOP 구조에서 이유·출처·승인·완료 기준을 어디서 얻는지 설명하게 합니다. 설명을 실제 파일과 대조합니다.
2. **요구와 기대 정리**: 이 결과를 읽을 담당자가 결정하려면 무엇이 보여야 하는지 자기 말로 정리합니다. `결과/기대결과.md`에 아래 사례 종류마다 하나 이상, 원문으로 기대 판정·이유·추가로 확인할 값을 먼저 적습니다.
3. **계획 검토**: 구현 계획만 먼저 받아 출력 계약의 항목(판정·이유·원문 출처·추가로 확인할 값·비교값·승인)이 모두 어디서 채워지는지 확인합니다. 원문에 없는 확인 항목을 만드는 계획은 고칩니다.
4. **작은 단위로 구현**: 판정과 이유 → 비교 → 검토 결과 작성 순서로 하나씩 만들고 실행합니다.
5. **출력 계약으로 품질 판정**: 조치검토결과.md를 담당자 입장에서 읽고 후보마다 계약 항목이 원문과 맞게 채워졌는지, 기대결과.md와 같은지 대조합니다.
6. **수정 요청**: 다르면 입력(사례·후보), 기대(원문 근거), 실제(출력)를 함께 주고 그 부분만 고치게 합니다. 결과에 맞추려고 기대를 바꾸지 않습니다.
7. **저장·재열기**: 저장한 파일을 다시 열어 확인합니다.

## 실행

```
python 결과/review.py
python check.py
```

## 기대 결과를 먼저 적을 사례 종류

- 경계: 유온 55 ℃, 압력 165 bar, 팬 24시간 바로 아래·같은 값·바로 위
- 제외 사유와 누락이 겹친 입력: 제외를 유지하면서 빠진 값도 추가 확인에 남는지
- 모두 제외된 입력: 추천 없이 이유가 남는지
- 필수값 누락: 그 값이 필요한 후보만 보류되는지
- 비교: 지표_정의.md의 C01 손계산과 같은지, 1위 후보의 승인 역할이 함께 보이는지

## 완료 조건

- `python 결과/review.py`가 사례 13건과 요청 14건을 모두 처리하고 `python check.py`가 통과합니다.
- 조치검토결과.md만 읽고도 후보별 판정 이유·원문 출처·추가로 확인할 값을 설명할 수 있습니다.
- 기대결과.md에 위 사례 종류마다 실행 전에 적은 기대·근거와 실행 후 실제가 있습니다.
- 비교 순위를 실행 승인처럼 쓰지 않았고, 결과를 맞추려고 조건표·원자료·기대를 바꾸지 않았습니다.

## 저장과 다음 실습

결과 폴더를 저장하고 다시 열어 확인하세요. 보관할 결과는 재부팅 전에 USB 또는 개인 클라우드에 복사하세요. 다음 실습에서는 매뉴얼 원문을 검토해 근거를 넓힙니다.
'''


def review_contract_result():
    return '''
## 출력 결과/조치검토결과.json

```
{
  "비교_기준": "교육용 비교값과 HYD 일곱 성분 점수, 실행 승인의 구분 문장",
  "항목": [
    {"id": "A 또는 C01", "종류": "사례 | 요청",
     "후보": [
       {"sop": "SOP-COOL-11", "판정": "유지 | 제외 | 보류",
        "이유": [{"규칙": "rule_id", "결과": "WARN | PENALTY | EXCLUDE | 미확인", "실제_입력": {"입력": 값}, "비교": "forecast_ts1 >= 55 ℃", "출처": "...", "빠진_입력": ["미확인일 때"]}],
        "원문_출처": ["..."],
        "추가_확인": ["..."],
        "비교값": {"비용": 0, "생산": 0, "품질": 0, "에너지": 0, "감점": 0, "합계": 0} 또는 null,
        "순위": 1 또는 null,
        "승인": {"역할": "...", "출처": "...", "안내": "비교 순위는 실행 승인이 아니다 ..."}}
     ],
     "검토_의견": {"추천": ["요청의 1위 유지 후보"], "사유": "...", "보류": ["..."]}}
  ]
}
```

- `이유`에는 맞은 규칙(경고·감점·제외)과 미확인 규칙만 둔다. 불일치 규칙은 넣지 않는다.
- 사례 A~M는 판정만 하고 비교값·순위·추천을 두지 않는다. 요청 C01~C14의 유지 후보만 비교한다.
- `추가_확인`에는 미확인 규칙의 빠진 입력 이름을 그대로 넣는다. 유지 후보는 sop.json의 실행 전 확인 조건과 완료 기준을 넣는다.
- `결과/조치검토결과.md`는 같은 내용을 사례·요청마다 절로 나눠 사람이 읽게 쓴다. 각 절 제목에 사례·요청 id를 넣는다.
'''


def build_review():
    folder = REVIEW
    reset(folder)
    judge_inputs(folder)
    write(folder/'입출력_계약.md', JUDGE_CONTRACT.replace('# 판정 기능의 입출력 계약', '# 조치 검토 결과의 입출력 계약')+review_contract_result())
    write(folder/'check.py', REVIEW_CHECK)
    write(folder/'결과/README.md', 'review.py, 조치검토결과.json, 조치검토결과.md, 기대결과.md를 여기에 저장합니다.\n')
    keep(folder/'결과/기대결과.md', EXPECT_TEMPLATE.replace('| 사례·요청 / 후보 | 사례 종류 | 기대 판정·이유 |', '| 사례·요청 / 후보 | 사례 종류 | 기대 판정·이유·추가로 확인할 값 |'))
    sections = [
        ('시작하기', '<p>VS Code에서 이 폴더를 열고 <a href="START.md">START.md</a>와 <a href="입출력_계약.md">입출력_계약.md</a>를 읽으세요.</p><pre>입력/   이전 단계 완성 조건표(rules.csv)와 SOP 구조(sop.json)\n자료/   사례 A~M, 대상 후보, 원문, metrics/의 비교 요청 C01~C14와 손실 식\n결과/   이번에 만들 review.py, 조치검토결과.json·.md, 기대결과.md\ncheck.py   결과 구조 검사</pre><p>입력/rules.csv는 지난 회차 조건표의 팬 최대 운전 규칙을 SOP 네 개로 넓힌 완성본입니다. 고치지 말고 읽기만 합니다.</p><p>먼저 AI에게 <b>파일을 바꾸지 말고</b> 이유·출처·승인·완료 기준을 어느 파일에서 얻는지 설명하게 하고, 그 설명을 실제 파일과 대조하세요.</p>'),
        ('요구 정하기', '<p>이 결과를 읽을 사람은 조치 승인을 요청할 담당자입니다. 그 사람이 결정하려면 무엇이 보여야 하는지 먼저 정하세요.</p><ul><li>후보마다 판정과 그 이유가 실제 입력값과 함께 보이는가</li><li>이유마다 원문으로 돌아갈 출처가 있는가</li><li>보류·제외 후보에서 무엇을 더 확인하면 되는가</li><li>1위 후보도 누가 승인하고 실행 전에 무엇을 확인해야 하는가</li></ul><p>결과/기대결과.md에 사례 종류별 기대 판정·이유·추가로 확인할 값을 원문으로 먼저 적습니다. 출력을 보고 기대를 채우지 않습니다.</p>'),
        ('AI와 만들기', '<p>구현 전에 계획만 받아, 출력 계약의 항목(판정·이유·원문 출처·추가로 확인할 값·비교값·승인)이 각각 어느 입력에서 채워지는지 확인하세요. 원문에 없는 확인 항목을 만드는 계획은 고칩니다. 그다음 판정 → 비교 → 검토 결과 작성 순서로 나눠 요청합니다. 요청에는 읽을 파일, 바꾸면 안 되는 것(입력/·자료/, 조건표를 코드에 고정하지 않기)을 함께 적습니다.</p><ol><li>사례 A~M의 판정과 이유부터 만들고 경계·누락 사례를 확인합니다.</li><li>C01~C14 비교를 붙이고 C01 손계산과 대조합니다.</li><li>sop.json에서 승인 역할·실행 전 확인·완료 기준을 읽어 검토 결과에 붙입니다. 원문에 없는 확인 항목을 만들지 않습니다.</li></ol><details><summary>요청을 정리할 때 볼 항목</summary><p>만들 결과 / 참고할 자료 / 바꾸지 않을 범위 / 성공을 확인할 사례</p></details>'),
        ('결과 확인하기', '<pre>python 결과/review.py\npython check.py</pre><p>구조 검사는 형식과 계약의 불변식만 봅니다. 내용은 다음 기준으로 원문과 대조하세요.</p><ul><li>경계: 팬이 정확히 24시간인 C03에는 감점이 없고 24.1시간인 C04에는 팬 최대 운전 후보에만 20만 원 감점이 이유와 출처로 남습니다.</li><li>제외와 누락이 겹친 사례 K: 제외 판정을 유지하면서 빠진 예측 유온이 추가로 확인할 값에 남아야 합니다.</li><li>모두 제외된 입력: 추천 없음과 그 이유(어느 규칙 때문에 모두 제외됐는지)가 남아야 합니다.</li><li>누락 C13: 팬 운전 시간이 필요한 후보만 보류되고, 추가로 확인할 값에 fan100_hours가 보입니다.</li><li>순위 1위 후보에도 승인 역할과 실행 전 확인 조건이 함께 보이고, 순위가 실행 승인이 아니라는 안내가 있습니다.</li></ul><p class="check">이번 실습의 판단 지점: <b>출력 계약으로 결과물의 품질을 판정합니다.</b> 조치검토결과.md만 읽고 후보마다 판정·이유·원문 출처·추가로 확인할 값·승인 구분이 있고, 원문 절까지 따라갈 수 있는지 확인하세요. 기대결과.md와 다르면 입력·기대·실제를 함께 주고 필요한 부분만 고친 뒤 이미 맞았던 사례를 다시 확인합니다.</p>'),
        ('저장하기', '<p>결과/review.py, 결과/조치검토결과.json, 결과/조치검토결과.md, 결과/기대결과.md를 저장하고 다시 열어 확인하세요. 보관할 결과는 재부팅 전에 USB 또는 개인 클라우드에 복사합니다.</p><p>비교 합계는 교육용 비교값입니다. 실제 HYD 성과 점수와 다르며 순위가 실행 승인을 뜻하지 않습니다.</p>')]
    common_files(folder, REVIEW_START, ['입력/rules.csv의 규칙을 코드에 다시 적어 고정하지 않는다. 조건표를 읽어 판정한다.', '빈 값을 0이나 정상값으로 채우지 않는다. 결과를 맞추려고 조건표·원자료·기대를 바꾸지 않는다.', '비교 순위를 실행 승인으로 쓰지 않는다. 승인 역할과 실행 전 확인은 sop.json의 원문 근거로만 적는다.'], '후보별 조치 검토 결과 만들기', '완성 조건표로 후보별 판정·이유·원문 출처·추가로 확인할 값을 만들고, 허용 후보만 교육용 손실로 비교합니다. 순위는 실행 승인이 아닙니다.', sections)


ENTRIES = [
    ('integrated-03-criteria', '통합반', 'SOP 구조와 조치 결정표 만들기', CRITERIA),
    ('integrated-03-judge', '통합반', '조건표를 읽는 조치 판정·비교 기능 만들기', JUDGE),
    ('practical-03-review', '실전반', '후보별 조치 검토 결과 만들기', REVIEW),
]


def main():
    migrate_legacy()
    build_criteria()
    build_judge()
    build_review()
    catalog = json.loads((HERE/'package-index.json').read_text(encoding='utf-8'))
    ids = {e[0] for e in ENTRIES}
    catalog['labs'] = [x for x in catalog['labs'] if x['id'] not in ids]
    for lab_id, course, title, folder in ENTRIES:
        archive = pack(folder)
        catalog['labs'].append({'id': lab_id, 'course': course, 'session': SESSION, 'title': title, 'version': VERSION, 'folder': '03회차/랩/'+folder.name, 'path': archive.relative_to(ROOT).as_posix(), 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()})
        print('ZIP:', archive.relative_to(ROOT).as_posix())
    dump(HERE/'package-index.json', catalog)
    print('3회차 SOP·조건표·판단 시작본 3개, ZIP 3개, 목록 동기화')


if __name__ == '__main__':
    main()
