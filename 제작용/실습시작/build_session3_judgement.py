"""온라인 3회차 SOP·조건표·판단 랩 세 개의 독립 시작본(현업화 판).

통합반 03일차_실습2_조치기준만들기, 통합반 03일차_실습3_판단기능만들기,
실전반 03일차_실습2_판단기능만들기. 원자료는 data_conditions.py가 시뮬레이터 로직으로 만든 냉각 경보 사례 48건 묶음이다
(실전반 2회차 조건표 랩과 같은 묶음). 강사 참조 답안은 reference/session3/에만 둔다.
학생 폴더에는 이전 단계 완성 상태(설비 모델, 완성 조건표·SOP 구조)와 원자료만 넣는다.
계약 문서에는 형식·의미만 적고 판정 절차·정답 방향은 적지 않는다(원칙은 원문 작업기준.md·HM-8·HI-01·수집_설명.md).
"""
from build_labs import ROOT, OUT, page, write, dump, pack, RULES, reference_model
from data_conditions import build as build_data
from pathlib import Path
import hashlib
import json
import shutil

HERE = Path(__file__).resolve().parent
REFERENCE = HERE/'reference/session3'
VERSION = '2026-10-28-s3-v4-rh3'
SESSION = '온라인 03회차'
CRITERIA = OUT/'통합반/실습/03회차/랩/03일차_실습2_조치기준만들기'
JUDGE = OUT/'통합반/실습/03회차/랩/03일차_실습3_판단기능만들기'
REVIEW = OUT/'실전반/실습/03회차/랩/03일차_실습2_판단기능만들기'
LABS = [CRITERIA, JUDGE, REVIEW]

DOCS = ['HM-8_매뉴얼.md', '규칙_원문.txt', '작업기준.md', 'HI-01_보충매뉴얼.md', '수집_설명.md', 'targets.csv']
RAW = ['경보_목록.csv', 'PLC_상태_수신.csv', '팬_운전_카운터.csv', '예측_결과.csv']
METRICS = ['지표_정의.md', '업무_값.json', '후보_설정.csv']
# 옛 판의 파일. 새 판에는 없으므로 지운다(학생 결과/는 건드리지 않는다).
OBSOLETE = ['자료/cases.csv', '자료/적용범위.md', '자료/metrics/판정_요청.json', '자료/failuremodes.csv']

STEP_TIPS = '''## 진행할 때

- 채팅에 파일 이름을 쓸 때는 백틱(`)으로 감쌉니다. 예: `자료/예측_결과.csv`. 채팅 입력이 밑줄(_)을 서식으로 바꿔 이름이 달라질 수 있습니다.
- AI가 완료를 알리면 실행한 명령과 그 출력 원문(요약이 아니라 나온 글자 그대로)을 붙여 달라고 요청합니다.
- AI가 질문 카드(선택지와 「(권장)」 표시)로 물으면, 「(권장)」은 AI의 추천일 뿐입니다. 근거가 되는 원문·원자료 줄을 열어 확인한 뒤 고르거나 직접 입력 칸에 결정과 근거를 적습니다.
- 파일 편집 승인 창(「Allow ChatGPT to edit …」)이 뜨면 바뀔 파일이 `결과/` 아래인지 보고 「Allow once」, 아니면 「Deny」를 누릅니다.
- AI에게 고치게 할 때는 입력·기대·실제를 함께 주고, 고친 뒤에는 내가 예로 든 행만 맞았는지가 아니라 같은 종류의 다른 행에도 통하는지 다시 세어 달라고 합니다.
'''

TABLE_CONTRACT = '''## 결정표 형식 (rules.csv)

열: `rule_id,action,condition_index,logic,input,operator,value,unit,boundary_included,result,penalty_만원,reason,source_section`

- 비교 하나가 한 행이다. 같은 `rule_id`·`action`의 행은 한 규칙 묶음이고 `condition_index`를 1부터 차례로 적으며 `logic`은 `AND`다. OR는 다른 `rule_id`로 나눈다.
- `action`은 `targets.csv`의 SOP ID 하나다. 같은 규칙을 여러 후보에 두면 후보마다 묶음 전체를 적는다. 표에 없는 후보·규칙 조합은 그 후보에 적용하지 않는다는 뜻이다.
- `result`: `WARN`(경고), `PENALTY`(감점), `EXCLUDE`(제외). 같은 묶음의 `result`·`penalty_만원`·`reason`·`source_section`은 모든 행에서 같다. `PENALTY`만 `penalty_만원`(만원)을 적고 나머지는 빈칸이다.
- `operator`: `>=`, `>`, `<=`, `<`, `==`, `!=`, `has_other_than`(목록 입력에 기준값이 아닌 항목이 하나라도 있음). `boundary_included`: 기준값 자체가 조건에 들어가면 `예`, 들어가지 않으면 `아니오`, 문자열·목록 비교는 `해당없음`.
- `input` 이름과 단위: `forecast_ts1`(조치 후 예측 유온, ℃), `forecast_ps1`(조치 후 예측 토출 압력, bar), `fan100_hours`(팬 100 % 연속 운전 시간, h), `plc_mode`(`REMOTE_AUTO`·`REMOTE_MANUAL`·`LOCAL`), `plc_state`(`RUNNING`·`TRIP`), `skill_kind`(`control`·`work_order`), `skill_code`(실행 코드 목록). 숫자 입력은 `unit`을 적는다.
- 목록 입력(`skill_code`)에는 `has_other_than`만 쓴다. `==`·`!=`로 목록과 글자 하나를 비교하지 않는다. `has_other_than`은 목록 입력에만 쓴다.
- `source_section`에는 원문 근거를 적는다. 규칙 발췌의 시드 출처와 첨부 HM-8의 절은 서로 다른 체계이므로 구별해 적는다(예: `규칙발췌 rule:xxx(시드 HM-x.y); HM-8.z`).

형식 예시(가상의 행이며 정답 행이 아니다):

```
R0,SOP-COOL-00,1,AND,forecast_ts1,>=,0,℃,예,WARN,,이유 문장,근거 절
```
'''

RULES_CHECK = r'''import re
HEADER = ['rule_id','action','condition_index','logic','input','operator','value','unit','boundary_included','result','penalty_만원','reason','source_section']
OPS = {'>=':'예','<=':'예','>':'아니오','<':'아니오','==':'해당없음','!=':'해당없음','has_other_than':'해당없음'}
NUMERIC = {'forecast_ts1','forecast_ps1','fan100_hours'}
LIST_INPUTS = {'skill_code'}
INPUTS = NUMERIC | {'plc_mode','plc_state','skill_kind'} | LIST_INPUTS
def check_rules(path, sop_ids):
    """(상태, 오류 목록, 묶음 수). 상태: 없음·빈 틀·통과·확인 필요."""
    if not path.is_file(): return '없음', [], 0
    with path.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f); header = reader.fieldnames; table = list(reader)
    errs, groups = [], {}
    if header != HEADER: return '확인 필요', ['열 이름·순서가 계약과 다릅니다: '+','.join(header or [])], 0
    if not table: return '빈 틀', [], 0
    for line, r in enumerate(table, 2):
        at = f'{path.name}:{line}'
        if r['action'] not in sop_ids: errs.append(f'{at} targets.csv에 없는 action {r["action"]}')
        if r['logic'] != 'AND': errs.append(f'{at} logic은 AND')
        if r['input'] not in INPUTS: errs.append(f'{at} 계약에 없는 input {r["input"]}')
        if r['operator'] not in OPS: errs.append(f'{at} 계약에 없는 operator {r["operator"]}')
        elif OPS[r['operator']] != r['boundary_included']: errs.append(f'{at} boundary_included({r["boundary_included"]})가 operator {r["operator"]}와 맞지 않습니다.')
        if r['input'] in LIST_INPUTS and r['operator'] != 'has_other_than': errs.append(f'{at} 목록 입력 {r["input"]}에는 has_other_than만 씁니다(목록과 글자를 {r["operator"]}로 비교하지 않음).')
        if r['operator'] == 'has_other_than' and r['input'] not in LIST_INPUTS: errs.append(f'{at} has_other_than은 목록 입력({", ".join(sorted(LIST_INPUTS))})에만 씁니다.')
        if r['result'] not in {'WARN','PENALTY','EXCLUDE'}: errs.append(f'{at} result는 WARN·PENALTY·EXCLUDE')
        if r['input'] in NUMERIC:
            try: float(r['value'])
            except ValueError: errs.append(f'{at} 숫자 입력의 기준값이 숫자가 아닙니다.')
            if not r['unit']: errs.append(f'{at} 숫자 입력의 unit이 비었습니다.')
        if r['result'] == 'PENALTY':
            try: float(r['penalty_만원'])
            except ValueError: errs.append(f'{at} PENALTY에 penalty_만원이 없습니다.')
        elif r['penalty_만원']: errs.append(f'{at} PENALTY가 아닌 행에 penalty_만원이 있습니다.')
        if not r['reason'] or not r['source_section']: errs.append(f'{at} reason·source_section이 필요합니다.')
        key = (r['rule_id'], r['action']); head = (r['result'], r['penalty_만원'], r['reason'], r['source_section'])
        g = groups.setdefault(key, {'head': head, 'index': []})
        if g['head'] != head: errs.append(f'{at} 같은 묶음 {key}의 result·penalty·reason·source가 다릅니다.')
        try: g['index'].append(int(r['condition_index']))
        except ValueError: errs.append(f'{at} condition_index가 정수가 아닙니다.')
    for key, g in groups.items():
        if sorted(g['index']) != list(range(1, len(g['index'])+1)): errs.append(f'{path.name} 묶음 {key}: condition_index가 1부터 연속이 아닙니다: {g["index"]}')
    return ('확인 필요' if errs else '통과'), errs, len(groups)
def empty_rows(path, column):
    """마크다운 표에서 column 칸이 빈 데이터 행 수와 데이터 행 수."""
    if not path.is_file(): return None, 0
    head, empty, total = None, 0, 0
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        if not line.startswith('|'): head = None; continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if head is None: head = cells; continue
        if set(''.join(cells)) <= set('-: '): continue
        idx = [k for k, h in enumerate(head) if h.startswith(column)]
        if not idx: continue
        if not any(cells): continue
        total += 1
        i = idx[0]
        if i >= len(cells) or not cells[i]: empty += 1
    return empty, total
def excerpt_rules(path):
    """규칙 발췌(규칙_원문.txt)에 실린 규칙 ID."""
    return re.findall(r"^\s*\['(rule:[A-Za-z0-9_-]+)'", path.read_text(encoding='utf-8-sig'), re.M) if path.is_file() else []
def section_text(path, word):
    """마크다운에서 제목에 word가 들어 있는 절의 본문."""
    if not path.is_file(): return ''
    out, on = [], False
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        if line.startswith('#'): on = word in line; continue
        if on: out.append(line)
    return '\n'.join(out)
def mentioned(rid, text):
    return re.search(re.escape(rid) + r'(?![A-Za-z0-9_-])', text) is not None
def unused_rules(rules_path, excerpt_path, record_path, word):
    """규칙 발췌의 규칙 중 조건표 source_section에도, 기록의 결정 절에도 이름이 없는 것. 옳고 그름은 판정하지 않는다."""
    if not rules_path.is_file(): return []
    with rules_path.open(encoding='utf-8-sig', newline='') as f: used = ' '.join(r.get('source_section') or '' for r in csv.DictReader(f))
    if not used.strip(): return []
    note = section_text(record_path, word)
    return [rid for rid in excerpt_rules(excerpt_path) if not mentioned(rid, used) and not mentioned(rid, note)]
def missing_kinds(path, column, kinds):
    """kinds: [(종류 이름, [찾을 말…])]. 표의 column 칸 어디에서도 찾을 말이 없는 종류 이름. 표에 행이 없으면 빈 목록."""
    if not path.is_file(): return []
    head, seen = None, []
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        if not line.startswith('|'): head = None; continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if head is None: head = cells; continue
        if set(''.join(cells)) <= set('-: '): continue
        idx = [k for k, h in enumerate(head) if h.startswith(column)]
        if idx and idx[0] < len(cells) and any(cells): seen.append(cells[idx[0]])
    text = ' '.join(seen)
    if not text.strip(): return []
    return [name for name, words in kinds if not any(w in text for w in words)]
def expect_time(path):
    """기대결과.md 머리의 「기대 칸을 쓴 시각」과 「실행 시각」 정보."""
    if not path.is_file(): return []
    text = path.read_text(encoding='utf-8-sig')
    def when(label):
        m = re.search(r'^- ' + label + r'[^:\n]*:[ \t]*(.*)$', text, re.M)
        if not m or not m.group(1).strip(): return None, False
        x = re.search(r'(\d{4}-\d{2}-\d{2})[ T](\d{1,2}):(\d{2})', m.group(1))
        return (f'{x.group(1)} {int(x.group(2)):02d}:{x.group(3)}' if x else None), True
    e, e_filled = when('기대 칸을 쓴 시각'); r, _ = when('실행 시각')
    if not e_filled: return ['기대결과.md 「기대 칸을 쓴 시각」이 비어 있습니다. 실행 전에 기대 칸을 쓰고 그 시각을 적으세요.']
    if e and r and e > r: return [f'기대결과.md 기대 칸을 쓴 시각({e})이 실행 시각({r})보다 뒤입니다. 실행 출력을 보고 기대를 쓰지 않았는지 확인하세요.']
    return []
def notes(lines):
    for line in lines: print('참고: ' + line)
def report(parts):
    """parts: [(이름, 상태, 오류, 설명)]. 단계별 상태를 나눠 출력하고, 필수 단계가 모두 통과면 0."""
    ok = True
    for name, state, errs, note, required in parts:
        print(f'- {name}: {state}' + (f' — {note}' if note else ''))
        for e in errs: print('    ' + e)
        if required and state != '통과': ok = False
    return ok
'''


def rules_for(extra):
    text = RULES.replace('입력/와 자료/는 보존한다.', '입력/·자료/의 파일과 check.py는 보존한다.')
    text = text.replace('- DB 작업은 안내된 별도 랩 주소만 사용한다. 포털 DB와 시스템 파일을 수정하거나 전체 삭제하지 않는다.\n', '- 실제 설비·포털·업무 시스템을 호출하지 않는다. 이번 실습은 제공 파일만 읽는다.\n')
    if '입력/·자료/의 파일과 check.py는 보존한다.' not in text or '실제 설비·포털·업무 시스템을 호출하지 않는다.' not in text:
        raise RuntimeError('build_labs.RULES 문구가 바뀌어 랩 규칙을 조정하지 못했습니다(보존·DB 줄).')
    return text + ''.join(f'- {line}\n' for line in extra)


def place_data(folder, names, data):
    for name in names:
        if name not in data:
            raise KeyError(f'data_conditions에 {name} 없음')
        target = folder/'자료'/('metrics/' + name if name in METRICS else name)
        write(target, data[name])


def reset(folder):
    """빌더가 만드는 파일만 다시 쓴다. 학생 결과 폴더의 다른 파일은 건드리지 않는다."""
    for sub in ['입력', '.github', '자료']:
        if (folder/sub).is_dir():
            shutil.rmtree(folder/sub)
    for name in OBSOLETE:
        if (folder/name).exists():
            (folder/name).unlink()


def common_files(folder, start, extra_rules, title, intro, sections):
    text = rules_for(extra_rules)
    for name in ['AGENTS.md', 'CLAUDE.md', '.github/copilot-instructions.md']:
        write(folder/name, text)
    write(folder/'START.md', start)
    if (folder/'준비_안내.md').exists():
        (folder/'준비_안내.md').unlink()
    guide = page(title, intro, sections)
    write(folder/'guide.html', guide)
    write(folder/'안내.html', guide)


def keep(path, text):
    """학생 결과 틀. 이미 있으면 덮어쓰지 않는다(빌드 재실행이 작업을 지우지 않게)."""
    if not path.exists():
        write(path, text)


def force_template(path, text, markers):
    """옛 판의 빈 틀(새 틀의 표지가 없음)만 새 틀로 바꾼다. 학생이 쓴 내용이 있으면 건드리지 않는다."""
    if path.exists() and all(m in path.read_text(encoding='utf-8-sig') for m in markers):
        return
    if path.exists() and not is_old_empty(path):
        return
    write(path, text)


def is_old_empty(path):
    text = path.read_text(encoding='utf-8-sig')
    if path.suffix == '.csv':
        return len([l for l in text.splitlines() if l.strip()]) <= 1
    if path.suffix == '.json':
        try:
            d = json.loads(text)
        except ValueError:
            return False
        return not d.get('SOP') and not d.get('events') and not d.get('항목')
    lines = text.splitlines()
    data = []
    for i, l in enumerate(lines):
        if not l.startswith('|') or set(l.strip()) <= set('|-: '):
            continue
        header = i + 1 < len(lines) and lines[i + 1].startswith('|') and set(lines[i + 1].strip()) <= set('|-: ')
        if not header:
            data.append(l)
    return all(not ''.join(c.strip() for c in l.strip().strip('|').split('|')) for l in data)


DATA_INTRO = '''- 원자료(교육용 가상 자료, 수업용 시뮬레이터 로직으로 생성): `자료/경보_목록.csv`(쿨러 냉각 경보 사례 E01~E48, HYD-01~03), `자료/PLC_상태_수신.csv`(운전 모드·상태 수신), `자료/팬_운전_카운터.csv`(팬 100 % 연속 운전 분), `자료/예측_결과.csv`(후보별 조치 후 예측). 원천마다 주기·단위·값이 비는 이유가 다르며 `자료/수집_설명.md`에 적혀 있습니다.
- 원문: `자료/HM-8_매뉴얼.md`(SOP), `자료/규칙_원문.txt`(시드 결정표 발췌), `자료/작업기준.md`(회사 작업 기준), `자료/HI-01_보충매뉴얼.md`(관측 시각·조회 실패 기준). `자료/targets.csv`: 이번 후보 SOP 네 개.'''


# ───────────── 통합반 실습2: SOP 구조와 결정표 ─────────────

CRITERIA_CHECK = r'''"""결과/sop.json·rules.csv의 구조 검사와 기록 칸 확인. 의미 정답은 판정하지 않는다.
단계별로 상태를 나눠 출력한다(예: sop.json 통과 / rules.csv 아직 없음)."""
from pathlib import Path
import csv, json, sys
root = Path(__file__).resolve().parent
''' + RULES_CHECK + r'''
CASE_KINDS = [('정상', ['정상']), ('경계', ['경계']), ('복수 조건', ['복수']), ('모두 제외·유지 후보 없음', ['모두 제외', '유지 후보 없음', '추천 없음']),
              ('값 없음', ['값 없음', '누락', '미확인']), ('적용 대상 밖', ['대상 밖']), ('결정에 따라 바뀌는 사례', ['결정', '갈래', '갈림'])]
def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as f: return list(csv.DictReader(f))
sop_ids = [t['sop_id'] for t in rows(root/'자료/targets.csv')]
graph = json.loads((root/'입력/graph.json').read_text(encoding='utf-8-sig'))
model_ids = {n['props']['id'] for n in graph['nodes']}
def refs(value):
    if isinstance(value, str): yield value
    elif isinstance(value, list):
        for v in value: yield from refs(v)
    elif isinstance(value, dict):
        for k, v in value.items():
            if k != '미기재': yield from refs(v)
def check_sop(path):
    if not path.is_file(): return '없음', [], ''
    try: sop = json.loads(path.read_text(encoding='utf-8-sig'))
    except ValueError as e: return '확인 필요', [f'JSON 읽기 실패: {e}'], ''
    items = sop.get('SOP') or []
    if not items: return '빈 틀', [], ''
    errs = []
    fm_ids = {f.get('id') for f in sop.get('고장유형', [])}
    found = [s.get('id') for s in items]
    for sid in sop_ids:
        if found.count(sid) != 1: errs.append(f'{sid}가 {found.count(sid)}번 있습니다(1번이어야 함).')
    for s in items:
        sid = s.get('id')
        if sid not in sop_ids: errs.append(f'targets.csv에 없는 SOP {sid}')
        if not s.get('출처'): errs.append(f'{sid}: 출처 없음')
        for key in ['적용_조건','금지_조건','수행_단계','완료_기준']:
            value = s.get(key)
            if not isinstance(value, list): errs.append(f'{sid}: {key}는 목록이어야 합니다.'); continue
            for i, item in enumerate(value, 1):
                if not isinstance(item, dict) or not item.get('내용') or not item.get('출처'): errs.append(f'{sid}.{key}[{i}]: 내용·출처가 필요합니다.')
        steps = [x.get('순서') for x in s.get('수행_단계') or [] if isinstance(x, dict)]
        if not steps or steps != list(range(1, len(steps)+1)): errs.append(f'{sid}: 수행_단계 순서가 1부터 연속이 아닙니다: {steps}')
        approval = s.get('승인')
        if not isinstance(approval, dict) or not approval.get('역할') or not approval.get('출처'): errs.append(f'{sid}: 승인(역할·출처)이 필요합니다.')
        if s.get('고장유형') not in fm_ids: errs.append(f'{sid}: 고장유형 {s.get("고장유형")}을 sop.json 고장유형에서 찾을 수 없습니다.')
        got = list(refs(s.get('모델_참조', {})))
        for ref in got:
            if ref not in model_ids: errs.append(f'{sid}: 모델에 없는 ID {ref} (새 ID를 만들지 말고 미기재로 남기세요)')
        if not got: errs.append(f'{sid}: 모델_참조가 비어 있습니다.')
    for f in sop.get('고장유형', []):
        for ref in refs(f.get('모델_참조', {})):
            if ref not in model_ids: errs.append(f'고장유형 {f.get("id")}: 모델에 없는 ID {ref}')
    return ('확인 필요' if errs else '통과'), errs, f'SOP {len(items)}개'
s_state, s_errs, s_note = check_sop(root/'결과/sop.json')
r_state, r_errs, n = check_rules(root/'결과/rules.csv', sop_ids)
parts = [('sop.json', s_state, s_errs, s_note, True), ('rules.csv', r_state, r_errs, f'규칙 묶음 {n}개' if n else '', True)]
for name, column in [('사례대조.md', '판정'), ('요구사항.md', '정한 내용')]:
    empty, total = empty_rows(root/'결과'/name, column)
    if empty is None: parts.append((name, '없음', [], '', False))
    elif total == 0 or empty == total: parts.append((name, '아직 비어 있음', [], f'「{column}」 칸을 채우세요', False))
    else: parts.append((name, '작성 중' if empty else '작성됨', [], f'행 {total}개 중 「{column}」 빈 칸 {empty}개' if empty else f'행 {total}개', False))
print('구조 검사 결과')
ok = report(parts)
left = unused_rules(root/'결과/rules.csv', root/'자료/규칙_원문.txt', root/'결과/요구사항.md', '정한 결정')
if left: notes([f'규칙 발췌의 규칙 중 rules.csv source_section에도, 요구사항.md 결정 표에도 이름이 없는 것: {", ".join(left)}. 옮기지 않기로 정했다면 그 이유를 결정 표에 적습니다.'])
kinds = missing_kinds(root/'결과/사례대조.md', '사례 종류', CASE_KINDS)
if kinds: notes([f'START.md 사례 종류 중 사례대조.md 「사례 종류」 칸에서 찾지 못한 것: {", ".join(kinds)} (다른 말로 적었다면 그대로 두어도 됩니다).'])
print('구조 검사는 형식만 봅니다. 경계 포함 여부·적용 대상·출처가 원문과 맞는지는 결과/사례대조.md에서 원문·원자료와 별도로 대조하세요.')
sys.exit(0 if ok else 1)
'''

SOP_CONTRACT = '''## SOP 구조 형식 (sop.json)

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
      "모델_참조": {"설비": ["..."], "구성요소": ["..."], "센서": ["..."]},
      "적용_조건": [ {"내용": "...", "출처": "...", "규칙": ["rule_id"]} ],
      "금지_조건": [ {"구분": "금지 또는 제한", "내용": "...", "출처": "...", "규칙": []} ],
      "수행_단계": [ {"순서": 1, "내용": "...", "출처": "..."} ],
      "완료_기준": [ {"내용": "...", "출처": "...", "규칙": []} ],
      "승인": {"역할": "...", "출처": "..."}
    }
  ]
}
```

- `targets.csv`의 SOP는 한 번씩 있어야 한다. `수행_단계`의 `순서`는 1부터 차례로 붙인다.
- `모델_참조`의 값은 `입력/graph.json`에 있는 ID만 쓴다. 모델에 없는 대상은 `"미기재": "이유"`로 남긴다.
- 각 항목의 `출처`는 HM-8 절과 SOP 단계(예: `HM-8.5 SOP-COOL-11 단계 2`) 또는 규칙 발췌 ID다.
- 조건과 결정표의 연결은 `규칙`에 rule_id로 적는다. 결정표로 옮기지 않은 조건은 빈 목록으로 둔다.
'''

CRITERIA_START = '''# SOP 구조와 조치 결정표 만들기

쿨러 냉각 성능 상실 경보에 쓰는 조치 네 개(SOP-COOL-11~14)를 원문에서 읽어, 적용 조건·금지 조건·수행 단계·완료 기준을 나눈 SOP 구조와 판단 규칙의 결정표로 만듭니다. 다음 실습의 판정 기능이 이 두 결과를 읽어 경보 사례 48건을 판정합니다.

## 출발점

- `입력/schema.json`, `입력/graph.json`: 이전 단계에서 완성한 설비 모델입니다. 설비·구성요소·센서·부품 ID를 그대로 재사용합니다.
''' + DATA_INTRO + '''
- `자료/failuremodes.csv`: 고장 유형. `입출력_계약.md`: 두 결과 파일의 형식.

이전 개인 결과가 없어도 시작할 수 있습니다. 자기 모델을 쓰려면 제공 입력은 그대로 두고 별도 폴더에 복사해 ID를 대조하세요.

## 이번에 만들 결과

- `결과/sop.json`: SOP마다 적용 조건·금지 조건·수행 단계·완료 기준·승인을 나누고 항목마다 원문 출처를 남깁니다. 대상 설비·구성요소·센서는 `입력/graph.json`의 ID로 가리킵니다.
- `결과/rules.csv`: 판단 규칙의 결정표(입력·연산자·기준값·단위·경계 포함 여부·결과·출처).
- `결과/요구사항.md`: 목표·자료·제약·확인 사례와, 원문만으로 정해지지 않아 **사람이 정한 결정**과 그 근거.
- `결과/사례대조.md`: 경보 사례에서 사례 종류마다 하나 이상 골라, 원자료로 판단 입력을 확인하고 결정표에 손으로 대입한 판정과 근거.

원문 자동 추출(인제스천) 프로그램은 만들지 않습니다.

## 작업 순서

1. **탐색만 요청**: AI에게 파일을 바꾸지 말고 자료/·입력/을 읽어 SOP 네 개와 규칙 발췌가 어디에 있는지, 두 자료의 출처 체계가 어떻게 다른지, 원천 자료마다 무엇이 들어 있는지 설명하게 합니다. 설명은 실제 파일과 대조합니다.
2. **요구 정리**: `결과/요구사항.md`에 목표·사용할 자료·지킬 조건·확인할 사례를 자기 말로 적습니다. 원문으로 정해지지 않는 점을 찾으면 AI에게 맡기지 말고 직접 원문을 읽어 정하고, 그 결정과 근거, 결정에 따라 결과가 바뀌는 사례를 적습니다.
3. **계획 검토**: AI에게 만들 순서를 계획만 받습니다. 원문에 없는 단계·값, 기존 ID 대신 새 ID를 만드는 부분이 없는지 확인합니다.
4. **작은 단위로 만들기**: SOP 하나 → 나머지 SOP → 규칙 하나씩 순서로 요청하고, 단계마다 `python check.py`로 그 부분이 통과하는지 봅니다. 모든 항목에 원문 근거(출처 칸)를 달게 합니다.
5. **원문과 대조**: 항목마다 출처 칸의 절을 열어 문장이 같은지 확인합니다. 고른 사례를 원자료로 확인하고 결정표에 대입해 `결과/사례대조.md`를 씁니다.
6. **수정 요청**: 다르면 해당 항목, 원문 문장(기대), 지금 결과(실제)를 함께 주고 그 부분만 고치게 합니다.
7. **저장·재열기**: 저장한 파일을 다시 열어 확인합니다.

''' + STEP_TIPS + '''
## 확인할 사례 종류

- 정상: 어떤 규칙도 맞지 않는 후보
- 경계: 기준값과 같은 값, 바로 위·아래 값
- 복수 조건: 경고·감점·제외가 함께 맞는 후보
- 모두 제외 또는 유지 후보 없음
- 값 없음: 원천에서 값이 비는 이유가 서로 다른 사례. 제외 사유가 이미 있는 경우와 없는 경우
- 적용 대상 밖: 값이 비어 있어도 그 후보에는 해당 규칙이 적용되지 않는 경우
- 사람이 정한 결정에 따라 결과가 바뀌는 사례

사례는 48건이라 눈으로 다 찾기 어렵습니다. 종류에 맞는 사례를 찾는 일은 AI에게 원자료 조회를 맡기고, 찾은 행을 직접 열어 확인합니다.

## 학생이 정할 것

원문만으로 하나로 정해지지 않아 학생이 원문을 읽고 정하는 지점입니다. 어느 규칙·절이 해당하는지는 탐색에서 직접 찾고, 정한 내용·근거·바뀌는 사례를 `결과/요구사항.md` 결정 표에 적습니다. AI는 이 지점을 정하기 전에 학생에게 묻습니다.

- 규칙의 식(적용 대상 목록)과 설명 문장이 서로 다른 범위를 말하는 곳
- 규칙 발췌와 HM-8이 같은 내용을 다르게 적은 곳, 시드의 스킬 ID와 이번 후보 SOP ID를 무엇을 근거로 잇는지
- 규칙 발췌의 규칙 가운데 결정표에 옮기지 않을 규칙과 그 이유

## 이번 범위 밖

원문 자동 추출(인제스천) 프로그램, 경보 사례 48건 전체를 판정하는 프로그램과 비교 계산(다음 실습). 사례 대조는 고른 사례를 결정표에 손으로 대입합니다.

## 실행

```
python check.py
```

`check.py`는 sop.json·rules.csv의 형식과 기록 칸을 단계별로 보여 줍니다. 규칙 발췌의 규칙 중 결정표와 요구사항.md 어디에도 이름이 없는 규칙, 사례대조.md에 아직 없는 사례 종류도 「참고」로 알려 줍니다. 형식 통과는 원문과 맞는다는 뜻이 아닙니다.

## 완료 조건

- `python check.py`에서 sop.json과 rules.csv가 통과합니다.
- 결정표의 모든 행에서 원문 문장으로 돌아갈 수 있고, 규칙 발췌의 시드 출처와 HM-8 절을 구별했습니다.
- SOP 네 개의 단계 순서·금지·승인이 원문과 같고, 원문에 없는 단계를 추가하지 않았습니다.
- 요구사항.md에 사람이 정한 결정과 근거가, 사례대조.md에 사례 종류마다 원자료 확인·판정·근거가 있습니다.
- 규칙 발췌의 규칙마다 결정표에 옮겼거나, 옮기지 않은 이유를 요구사항.md 결정 표에 적었습니다.

## 저장과 다음 실습

결과 폴더를 저장하고 다시 열어 확인하세요. 보관할 결과는 재부팅 전에 USB 또는 개인 클라우드에 복사하세요. 다음 실습(판정 기능)은 완성된 조건표와 SOP 구조를 제공하므로 이번 결과가 없어도 시작할 수 있습니다.
'''

CASE_TEMPLATE = '''# 사례 대조

> 제공 빈 틀입니다. 보관하지 말고 바로 채웁니다.

결정표를 손으로 대입한 판정입니다. 판단 입력은 원자료의 행(파일·시각)으로 확인해 적고, 근거에는 결정표의 rule_id와 원문 절을 적습니다.

| 사례 | 사례 종류 | 후보 | 판단 입력(값 또는 없음과 이유, 원자료 행) | 일치 규칙 | 경고 | 감점(만원) | 제외 사유 | 미확인 입력 | 판정 | 근거 |
|---|---|---|---|---|---|---:|---|---|---|---|
| | | | | | | | | | | |

## 사례별 추천(유지 후보 없음 사유)

| 사례 | 유지 후보 | 유지 후보가 없으면 그 사유 |
|---|---|---|
| | | |

## 원문과 다르게 정한 점·확인하지 못한 점
'''

REQ_TEMPLATE = '''# 이번에 만들 결과

> 제공 빈 틀입니다. 보관하지 말고 바로 채웁니다.

## 목표

## 사용할 자료와 범위

## 지킬 조건

## 사람이 원문으로 정한 결정

| 모호한 점 | 정한 내용 | 원문 근거(파일·절·문장) | 이 결정으로 결과가 바뀌는 사례 |
|---|---|---|---|
| | | | |

## 확인할 사례와 기대 결과의 근거
'''


def build_criteria(data):
    folder = CRITERIA
    reset(folder)
    place_data(folder, DOCS + RAW + ['failuremodes.csv'], data)
    schema, graph = reference_model()
    dump(folder/'입력/schema.json', schema)
    dump(folder/'입력/graph.json', graph)
    write(folder/'입력/README.md', '이전 단계(온라인 2회차 모델 설계)의 완성 설비 모델입니다. 설비·구성요소·센서·부품 ID를 재사용합니다. 개인 모델을 쓰려면 이 파일은 그대로 두고 별도 폴더에 복사하세요.\n')
    write(folder/'입출력_계약.md', '# SOP 구조와 결정표의 계약\n\n두 결과는 다음 실습의 판정 기능이 그대로 읽는 입력이다. 열 이름과 키를 바꾸면 다음 단계에서 읽지 못한다. 이 문서는 형식과 뜻만 정한다. 무엇을 어느 후보에 적용할지는 원문에서 정한다.\n\n' + SOP_CONTRACT + '\n' + TABLE_CONTRACT + '\n## 원본과 결과\n\n입력/·자료/는 보존한다. 결과는 결과/에만 쓴다. 실제 설비·평가 함수를 실행하지 않는다.\n')
    write(folder/'check.py', CRITERIA_CHECK)
    write(folder/'결과/README.md', 'sop.json, rules.csv, 요구사항.md, 사례대조.md를 여기에 저장합니다.\n')
    force_template(folder/'결과/sop.json', json.dumps({'문서': {'id': 'HM-8', '파일': '자료/HM-8_매뉴얼.md'}, '고장유형': [], 'SOP': []}, ensure_ascii=False, indent=2)+'\n', ['"SOP"'])
    force_template(folder/'결과/rules.csv', 'rule_id,action,condition_index,logic,input,operator,value,unit,boundary_included,result,penalty_만원,reason,source_section\n', ['rule_id'])
    force_template(folder/'결과/요구사항.md', REQ_TEMPLATE, ['이 결정으로 결과가 바뀌는 사례', '제공 빈 틀'])
    force_template(folder/'결과/사례대조.md', CASE_TEMPLATE, ['사례별 추천(유지 후보 없음 사유)', '제공 빈 틀'])
    sections = [
        ('시작하기', '<p>VS Code에서 이 폴더를 열고 <a href="START.md">START.md</a>와 <a href="입출력_계약.md">입출력_계약.md</a>를 읽으세요.</p><pre>입력/   이전 단계 완성 설비 모델(schema.json, graph.json)\n자료/   HM-8 매뉴얼, 규칙 발췌, 작업기준, HI-01, 수집 설명, 대상·고장 유형\n        경보 사례 48건의 원자료 4종(경보 목록, PLC 상태, 팬 카운터, 예측 결과)\n결과/   이번에 만들 sop.json, rules.csv, 요구사항.md, 사례대조.md\ncheck.py   단계별 구조 검사</pre><p>원자료는 수업용 시뮬레이터 로직으로 만든 교육용 가상 자료입니다. 실제 공장처럼 원천마다 수집 주기·단위가 다르고 값이 비는 이유도 다릅니다.</p>'),
        ('요구 정하기', '<p>먼저 AI에게 <b>파일을 바꾸지 말고</b> 자료/와 입력/을 읽어 SOP 네 개, 규칙 발췌, 원천 자료 네 개를 설명하게 하세요. 파일 이름은 백틱(`)으로 감싸 적습니다. 설명은 실제 파일과 대조합니다.</p><p>그다음 결과/요구사항.md에 자기 말로 적습니다.</p><ul><li>무엇을 만드는가: SOP 네 개의 구조와 판단 규칙의 결정표</li><li>어떤 자료를 쓰는가: HM-8 원문, 규칙 발췌, 작업기준</li><li>지킬 조건: 원문에 없는 단계·값을 만들지 않는다, 기존 모델 ID를 재사용한다, 자동 추출 프로그램은 만들지 않는다</li><li>확인할 사례: START.md의 사례 종류</li></ul><p class="check">이번 실습의 판단 지점: 규칙의 식과 설명 문장, 규칙 발췌와 HM-8이 서로 다른 범위를 말하는 곳이 있습니다. 그런 곳은 <b>AI가 아니라 사람이 원문을 읽고 정해</b> 근거와 함께 요구사항.md에 적고, 그 결정으로 결과가 바뀌는 사례도 찾아 적습니다.</p><p>AI가 이 지점을 질문 카드(Question 1 of 2, 선택지, 「(권장)」 표시, 직접 입력 칸)로 물을 수 있습니다. 「(권장)」은 AI의 추천일 뿐입니다. 선택지마다 결정표가 어떻게 달라지는지 묻고, 근거가 되는 원문 절(HM-8·규칙 발췌의 문장)을 직접 열어 확인한 뒤 고르거나 직접 적습니다.</p>'),
        ('AI와 만들기', '<p>먼저 만들 순서를 계획으로만 받아 검토하세요.</p><ol><li>SOP-COOL-11 하나의 구조를 먼저 만들고 원문 단계와 한 줄씩 대조합니다. <code>python check.py</code>로 sop.json 부분을 확인한 뒤 나머지 SOP로 넓힙니다.</li><li>결정표는 규칙 하나씩 만듭니다. 같은 규칙의 비교 두 개는 한 묶음으로 둡니다.</li><li>모든 항목과 행에 <b>원문 근거 칸(출처)</b>을 채우게 요구합니다. 근거를 못 대는 항목은 지우거나 미기재로 둡니다.</li></ol><p>AI가 완료를 알리면 실행한 명령과 출력 원문을 붙여 달라고 요청합니다.</p><details><summary>요청을 정리할 때 볼 항목</summary><p>만들 결과 / 참고할 자료 / 사람이 정한 결정 / 바꾸지 않을 범위 / 출처 칸 요구 / 성공을 확인할 사례</p></details>'),
        ('결과 확인하기', '<pre>python check.py</pre><p>sop.json과 rules.csv가 각각 통과인지, 기록 파일이 비어 있지 않은지 단계별로 나옵니다. 그다음 사례 종류마다 경보 사례를 골라 결과/사례대조.md를 채웁니다.</p><ul><li>판단 입력은 원자료의 행에서 직접 확인합니다. 값이 비면 왜 비었는지(수집_설명.md·HI-01)를 함께 적습니다.</li><li>경계값은 원문의 「이상·초과·미만」 그대로 판단합니다.</li><li>여러 규칙이 함께 맞으면 경고·감점·제외를 모두 남깁니다.</li><li>사례별 추천 표에는 유지 후보를, 없으면 그 사유를 적습니다.</li></ul><p class="check">결과가 예상과 다르면 결정표가 원문과 다른지, 손으로 대입한 예상이 틀렸는지 원문으로 돌아가 확인하세요. 고칠 때는 해당 항목, 원문 문장(기대), 지금 결과(실제)를 함께 AI에 전달하고 그 부분만 고치게 합니다.</p>'),
        ('저장하기', '<p>결과/sop.json, 결과/rules.csv, 결과/요구사항.md, 결과/사례대조.md를 저장하고 다시 열어 확인하세요. 보관할 결과는 재부팅 전에 USB 또는 개인 클라우드에 복사합니다.</p><p>다음 실습(판정 기능)은 완성된 조건표와 SOP 구조를 제공합니다.</p>')]
    common_files(folder, CRITERIA_START, ['이번 실습은 원문 자동 추출(인제스천) 프로그램을 만들지 않는다. 원문을 읽어 구조와 결정표를 작성한다.', '입력/graph.json에 없는 대상은 새 ID를 만들지 않고 미기재로 남긴다.', '원문만으로 정해지지 않는 점은 학생이 정한다. 학생에게 묻거나 미결로 표시하고 임의로 정하지 않는다.'], 'SOP 구조와 조치 결정표 만들기', '조치 원문을 적용 조건·금지 조건·수행 단계·완료 기준으로 나누고, 판단 규칙을 결정표로 만듭니다. 경보 사례 48건의 원자료로 경계·복수 조건·값 없음을 확인합니다.', sections)


# ───────────── 판정 기능 공통 ─────────────

def judge_inputs(folder, data):
    place_data(folder, DOCS + RAW + ['오더_현황.csv'] + METRICS, data)
    for name in ['rules.csv', 'sop.json']:
        source = REFERENCE/name
        if not source.is_file():
            raise FileNotFoundError(f'이전 단계 완성본 없음: {source}')
        write(folder/'입력'/name, source.read_text(encoding='utf-8-sig'))


JUDGE_CHECK_COMMON = r'''from pathlib import Path
from datetime import datetime
import csv, json, re, sys
root = Path(__file__).resolve().parent
''' + RULES_CHECK + r'''
def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as f: return list(csv.DictReader(f))
alarms = {r['사례']: r['후보'].split(';') for r in rows(root/'자료/경보_목록.csv')}
rule_actions = {(r['rule_id'], r['action']) for r in rows(root/'입력/rules.csv')}
RULE_INPUTS = {r['input'] for r in rows(root/'입력/rules.csv')}
STATUS = {'유지','제외','보류'}
def num(x): return isinstance(x, (int, float)) and not isinstance(x, bool)
UNIT_RANGE = {'forecast_ts1': (0, 150, '℃'), 'forecast_ps1': (50, 300, 'bar'), 'fan100_hours': (0, 24*40, 'h')}
def unit_errors(at, inputs):
    out = []
    for k, (lo, hi, unit) in UNIT_RANGE.items():
        v = inputs.get(k)
        if num(v) and not lo <= v <= hi: out.append(f'{at}: {k}={v}는 계약 단위 {unit}의 범위({lo}~{hi})를 벗어납니다. 원천 단위 환산을 확인하세요.')
    return out
'''

JUDGE_CHECK = '"""결과/result.json의 구조와 계약 불변식 검사, 기대결과.md 기록 칸 확인. 어떤 규칙이 맞아야 하는지·금액은 판정하지 않는다."""\n' + JUDGE_CHECK_COMMON + r'''
def check_result(path):
    if not path.is_file(): return '없음', [], ''
    try: result = json.loads(path.read_text(encoding='utf-8-sig'))
    except ValueError as e: return '확인 필요', [f'JSON 읽기 실패: {e}'], ''
    errs = []
    if not str(result.get('comparison_basis', '')).strip(): errs.append('comparison_basis(교육용 비교값과 HYD 점수의 구분 문장)가 없습니다.')
    dec = result.get('input_decisions')
    if not isinstance(dec, list) or not dec or any(not (d.get('항목') and d.get('결정') and d.get('근거')) for d in dec): errs.append('input_decisions(판단 입력을 만든 결정: 항목·결정·근거)가 필요합니다.')
    events = result.get('events')
    if not isinstance(events, list): return '확인 필요', errs + ['events 목록이 없습니다.'], ''
    got = [e.get('id') for e in events]
    if got != list(alarms): errs.append(f'events: 경보_목록.csv의 사례 순서·구성과 다릅니다(빠짐 {sorted(set(alarms)-set(got))}, 더함 {sorted(set(got)-set(alarms))}).')
    for e in events:
        eid = e.get('id'); cands = e.get('candidates') or []
        if eid in alarms and [c.get('sop') for c in cands] != alarms[eid]: errs.append(f'{eid}: 후보 목록이 경보_목록.csv와 다릅니다.')
        for c in cands:
            at = f'{eid}/{c.get("sop")}'
            inputs, reasons = c.get('inputs'), c.get('missing_reasons')
            if not isinstance(inputs, dict) or not isinstance(reasons, dict): errs.append(f'{at}: inputs와 missing_reasons가 필요합니다.'); continue
            for k in RULE_INPUTS:
                if k not in inputs: errs.append(f'{at}: inputs에 {k}가 없습니다(값이 없으면 null).')
                elif inputs[k] is None and not reasons.get(k): errs.append(f'{at}: {k}가 null인데 missing_reasons에 이유가 없습니다.')
            errs += unit_errors(at, inputs)
            if c.get('status') not in STATUS: errs.append(f'{at}: status는 유지·제외·보류'); continue
            lists = {k: c.get(k) for k in ['warnings','penalties','exclusions','unknown']}
            if any(not isinstance(v, list) for v in lists.values()): errs.append(f'{at}: warnings·penalties·exclusions·unknown은 목록'); continue
            for k in ['warnings','penalties','exclusions']:
                for h in lists[k]:
                    if (h.get('rule_id'), c.get('sop')) not in rule_actions: errs.append(f'{at}: 조건표에 없는 규칙·후보 {h.get("rule_id")}')
                    if not h.get('source_section') or not isinstance(h.get('conditions'), list) or not h['conditions']: errs.append(f'{at} {h.get("rule_id")}: source_section과 conditions(실제 입력·비교)가 필요')
            for h in lists['penalties']:
                if not num(h.get('amount_만원')): errs.append(f'{at} {h.get("rule_id")}: amount_만원 숫자 필요')
            for u in lists['unknown']:
                if not u.get('missing'): errs.append(f'{at} {u.get("rule_id")}: unknown에는 빠진 입력 이름(missing)이 필요')
            if lists['exclusions'] and c['status'] != '제외': errs.append(f'{at}: 제외 사유가 있는데 status가 {c["status"]}입니다.')
            if not lists['exclusions'] and lists['unknown'] and c['status'] != '보류': errs.append(f'{at}: 제외 없이 미확인이 있는데 status가 {c["status"]}입니다.')
            if not lists['exclusions'] and not lists['unknown'] and c['status'] != '유지': errs.append(f'{at}: 제외·미확인이 없는데 status가 {c["status"]}입니다.')
            comp = c.get('comparison')
            if c['status'] != '유지':
                if comp: errs.append(f'{at}: 유지가 아닌 후보에 비교값이 있습니다.')
            elif comp is None:
                if not c.get('comparison_unavailable'): errs.append(f'{at}: 비교값이 없으면 comparison_unavailable 이유가 필요합니다.')
            else:
                keys = ['비용','생산','품질','에너지','감점','합계']
                if not all(num(comp.get(k)) for k in keys): errs.append(f'{at}: 비교값에 {keys}가 숫자로 필요합니다.'); continue
                if abs(sum(comp[k] for k in keys[:5]) - comp['합계']) > 0.02: errs.append(f'{at}: 합계가 네 손실+감점과 다릅니다.')
                if abs(sum(p['amount_만원'] for p in lists['penalties'] if num(p.get('amount_만원'))) - comp['감점']) > 0.001: errs.append(f'{at}: 감점이 penalties 금액 합과 다릅니다.')
        ranking = e.get('ranking'); rec = e.get('recommendation') or {}
        if not isinstance(ranking, list): errs.append(f'{eid}: ranking 목록 필요'); continue
        kept = {c.get('sop') for c in cands if c.get('status') == '유지' and c.get('comparison')}
        if sorted(r.get('sop') for r in ranking) != sorted(kept): errs.append(f'{eid}: ranking에는 비교값이 있는 유지 후보만 모두 있어야 합니다.')
        totals = [r.get('합계') for r in ranking]
        if totals != sorted(totals): errs.append(f'{eid}: ranking이 합계 오름차순이 아닙니다.')
        for i, r in enumerate(ranking):
            tie = i > 0 and ranking[i-1].get('합계') == r.get('합계')
            if r.get('rank') != (ranking[i-1].get('rank') if tie else i+1): errs.append(f'{eid}: 순위 {r.get("sop")}가 동순위 규칙(1,1,3)과 다릅니다.')
        top = sorted(r.get('sop') for r in ranking if r.get('rank') == 1)
        if sorted(rec.get('sops') or []) != top: errs.append(f'{eid}: recommendation.sops는 1위 유지 후보여야 합니다.')
        if not rec.get('reason'): errs.append(f'{eid}: recommendation.reason이 필요합니다(추천이 없으면 그 사유).')
    return ('확인 필요' if errs else '통과'), errs, f'사례 {len(events)}건'
state, errs, note = check_result(root/'결과/result.json')
parts = [('judge.py', '있음' if (root/'결과/judge.py').is_file() else '없음', [], '', False), ('result.json', state, errs[:40] + ([f'… 외 {len(errs)-40}건'] if len(errs) > 40 else []), note, True)]
empty, total = empty_rows(root/'결과/기대결과.md', '실제 결과')
if empty is None: parts.append(('기대결과.md', '없음', [], '', False))
elif total == 0: parts.append(('기대결과.md', '아직 비어 있음', [], '실행 전에 기대 칸을 먼저 채우세요', False))
else: parts.append(('기대결과.md', '작성 중' if empty else '작성됨', [], f'행 {total}개 중 「실제 결과」 빈 칸 {empty}개' + (' — 실행 뒤 실제 결과를 적어 대조하세요' if empty else ''), False))
print('구조 검사 결과')
ok = report(parts)
kinds = missing_kinds(root/'결과/기대결과.md', '사례 종류', [('정상', ['정상']), ('경계', ['경계']), ('복수 조건', ['복수']), ('모두 제외·유지 후보 없음', ['모두 제외', '유지 후보 없음', '추천 없음']), ('값 없음', ['값 없음', '누락', '미확인']), ('결정에 따라 바뀌는 사례', ['결정', '갈래', '갈림'])])
notes(([f'START.md 사례 종류 중 기대결과.md 「사례 종류」 칸에서 찾지 못한 것: {", ".join(kinds)} (다른 말로 적었다면 그대로 두어도 됩니다).'] if kinds else []) + expect_time(root/'결과/기대결과.md'))
print('구조 검사는 형식과 계약의 불변식만 봅니다. 어떤 규칙이 맞아야 하는지와 금액은 원문·원자료·지표_정의.md 손계산과 별도로 대조하세요.')
sys.exit(0 if ok else 1)
'''

INPUT_CONTRACT = '''## 판단 입력

- 조건표의 입력 이름·단위는 아래 「조건표 형식」을 따른다. 후보마다 판단 시각 기준으로 원자료에서 만든다. 원천의 열 이름·단위·주기·값이 비는 이유는 `자료/수집_설명.md`에 있다.
- `skill_kind`·`skill_code`는 `자료/targets.csv`의 `kind`·`codes`다(`workorder`는 계약 이름 `work_order`, `codes`는 `;` 목록).
- 값을 정할 수 없는 입력은 `null`이고, 왜 없는지(원천·시각)를 함께 남긴다.
- 원천의 해석에 판단이 필요한 곳은 결정과 근거를 결과에 남긴다(`input_decisions`).

'''


def judge_contract():
    return ('# 판정 기능의 입출력 계약\n\n이 문서는 입력과 결과의 형식·뜻만 정한다. 판정 원칙은 `자료/작업기준.md`·HM-8·HI-01, 원천 해석은 `자료/수집_설명.md`에 있다.\n\n'
            '## 입력\n\n- `입력/rules.csv`: 이전 단계 완성 조건표(형식은 아래). 규칙을 코드에 다시 적어 고정하지 않고 이 파일에서 읽는다. 형식이 계약과 다르면 파일·행을 밝혀 실패한다.\n- `입력/sop.json`: 이전 단계 완성 SOP 구조(적용 조건·금지 조건·수행 단계·완료 기준·승인·출처).\n- `자료/`의 원자료 네 개와 `자료/오더_현황.csv`, `자료/metrics/`(지표_정의.md·업무_값.json·후보_설정.csv).\n\n'
            + INPUT_CONTRACT + TABLE_CONTRACT.replace('## 결정표 형식 (rules.csv)', '## 조건표 형식 (입력/rules.csv)').split('형식 예시')[0] +
            '\n## 교육용 비교\n\n비교 식은 `자료/metrics/지표_정의.md`를 그대로 쓴다. 비교 합계 = 비용 + 생산 + 품질 + 에너지 + 그 후보의 감점 합(만원, 작을수록 유리). 네 손실과 합계는 각각 원값으로 계산한 뒤 소수 둘째 자리로 반올림해 적는다. 합계는 반올림한 네 값을 더하지 않고 원값의 합을 반올림한다. 같은 합계는 같은 순위다(예: 1, 1, 3). 이 합계는 교육용 비교값이며 HYD의 일곱 성분 정책 점수와 같은 것으로 설명하지 않는다.\n')


JUDGE_RESULT = '''
## 출력 결과/result.json

```
{
  "comparison_basis": "교육용 비교값과 HYD 일곱 성분 점수의 구분 문장",
  "input_decisions": [{"항목": "...", "결정": "...", "근거": "파일·절"}],
  "events": [
    {"id": "E01", "asset": "HYD-..", "decision_time": "...",
     "candidates": [후보 판정],
     "ranking": [{"rank": 1, "sop": "...", "합계": 0.0}],
     "recommendation": {"sops": ["1위 유지 후보"], "reason": "추천 이유 또는 추천이 없는 사유", "held": ["보류 후보"]}}
  ]
}
```

후보 판정:

```
{"sop": "SOP-COOL-11", "status": "유지 | 제외 | 보류",
 "inputs": {"forecast_ts1": 숫자 또는 null, "forecast_ps1": ..., "fan100_hours": ..., "plc_mode": ..., "plc_state": ..., "skill_kind": ..., "skill_code": [...]},
 "missing_reasons": {"null인 입력": "왜 없는지(원천·시각)"},
 "warnings":   [{"rule_id": "...", "reason": "...", "source_section": "...", "conditions": [{"input": "...", "actual": 값, "operator": "...", "value": "...", "unit": "..."}]}],
 "penalties":  [{... 위와 같음, "amount_만원": 숫자}],
 "exclusions": [{... 위와 같음}],
 "unknown":    [{"rule_id": "...", "result": "...", "missing": ["빠진 입력"], "source_section": "..."}],
 "comparison": {"비용": 0, "생산": 0, "품질": 0, "에너지": 0, "감점": 0, "합계": 0} 또는 null,
 "comparison_unavailable": ["계산하지 못한 이유"]}
```

- `events`의 순서와 후보 순서는 `자료/경보_목록.csv`와 같다. `comparison`은 유지 후보에만 있다.
- 실행 결과와 별도로 `결과/기대결과.md`에 실행 전 원문·원자료로 적은 기대, 실제 결과, 차이와 수정을 남긴다.
'''

JUDGE_START = '''# 조건표를 읽는 조치 판정·비교 기능 만들기

쿨러 냉각 경보 사례 48건마다 조치 후보 네 개의 판단 입력을 원자료에서 만들고, 제공된 완성 조건표로 유지·제외·보류를 이유와 함께 판정한 뒤, 허용된 후보만 교육용 손실 산식으로 비교하는 프로그램을 만듭니다.

## 출발점

- `입력/rules.csv`, `입력/sop.json`: 이전 단계(SOP 구조와 결정표)의 완성본입니다. 고치지 말고 읽기만 합니다.
''' + DATA_INTRO + '''
- `자료/오더_현황.csv`, `자료/metrics/`: 교육용 비교에 쓰는 오더 값과 손실 식(지표_정의.md에 손계산 예).
- `입출력_계약.md`: 입력과 결과의 형식. `check.py`: 결과의 구조 검사.

이전 개인 결과가 없어도 시작할 수 있습니다.

## 직접 구현할 것

`결과/judge.py`를 만들어 실행하면 `결과/result.json`이 생기게 합니다.

1. 사례·후보마다 판단 입력을 원자료에서 만듭니다. 원천마다 단위·주기·값이 비는 이유가 다르므로 `자료/수집_설명.md`와 원문을 근거로 만드는 방법을 정합니다.
2. 조건표를 읽어 후보마다 경고·감점·제외·정보 부족을 이유와 함께 판정합니다. 규칙을 코드에 다시 적지 않습니다.
3. 유지 후보만 네 손실과 감점을 더해 비교하고 순위를 매깁니다. 추천이 없으면 사유를 남깁니다.
4. 결과에 교육용 비교값과 실제 HYD 성과 점수(일곱 성분)의 구분을 문장으로 남깁니다.

## 작업 순서

1. **탐색만 요청**: AI에게 파일을 바꾸지 말고 입력/·자료/·입출력_계약.md를 읽어 원천 네 개의 모양(주기·단위·빈 값), 조건표의 묶음 방식, 결과 형식을 설명하게 합니다. 설명을 실제 파일과 대조합니다.
2. **기대 결과 먼저**: 코드를 만들기 전에 `결과/기대결과.md`에 아래 사례 종류마다 하나 이상, 원자료 행과 조건표·원문으로 손으로 구한 기대 판정과 근거를 적습니다. 원천 해석에서 정한 결정도 적습니다. 다 쓰면 머리의 「기대 칸을 쓴 시각」을 적고 저장한 뒤 실행합니다. 구현 출력을 복사해 기대값을 만들지 않습니다.
3. **요구 정리와 계획 검토**: 목표·입력·제약·확인 사례와 정한 결정을 자기 말로 AI에 전달하고 구현 계획만 먼저 받습니다.
4. **작은 단위로 구현**: 판단 입력 만들기 → 판정 → 비교 → 저장 순서로 하나씩 만들고 실행합니다. 판단 입력은 몇 사례를 원자료 행과 직접 맞춰 본 뒤 다음으로 갑니다.
5. **기대와 실제 대조**: 실행 결과를 기대결과.md의 기대 칸과 한 줄씩 대조합니다.
6. **수정 요청**: 다르면 입력(사례·후보·원자료 행), 기대(근거), 실제(출력)를 함께 주고 원인을 찾게 합니다. 기대가 틀렸다면 근거로 고친 이유를 남기고, 결과에 맞추려고 기대를 바꾸지 않습니다.
7. **저장·재열기**: 저장한 파일을 다시 열어 확인합니다.

''' + STEP_TIPS + '''
## 실행

```
python 결과/judge.py
python check.py
```

## 기대 결과를 먼저 적을 사례 종류

- 정상: 규칙이 맞지 않는 후보
- 경계: 예측 유온·예측 압력·팬 연속 시간이 기준값과 같거나 바로 위·아래인 후보(단위가 다른 원천 포함)
- 복수 조건: 경고·감점·제외가 함께 맞는 후보, 감점이 규칙당 한 번인지
- 모두 제외 또는 유지 후보 없음
- 값 없음: 원천에서 값이 비는 이유가 서로 다른 사례. 그 값이 필요한 후보만 영향을 받는지
- 원천 해석에서 정한 결정에 따라 결과(감점·판정·추천)가 바뀌는 사례
- 비교: 지표_정의.md의 손계산과 프로그램 결과

## 학생이 정할 것

수집 설명만으로 하나로 정해지지 않아 학생이 근거를 찾아 정하는 지점입니다. 탐색에서 직접 찾고, 정한 방법·근거·바뀌는 사례를 `결과/기대결과.md` 「판단 입력을 만드는 결정」 표에 적습니다. AI는 이 지점을 정하기 전에 학생에게 묻습니다.

- 원천의 기록 방식이 두 가지로 읽히는 곳에서 판단 입력을 어떻게 만들지
- 그 결정으로 감점·판정·추천이 바뀌는 사례

## 이번 범위 밖

조건표·SOP 구조의 수정(입력은 읽기만 합니다), 매뉴얼 원문 재검토(다음 회차), 실제 설비 조작과 실행 승인.

## 완료 조건

- `python 결과/judge.py`가 사례 48건을 모두 처리하고 `python check.py`에서 result.json이 통과합니다.
- 지표_정의.md 손계산 예의 네 손실이 프로그램 결과와 같습니다.
- 기대결과.md에 위 사례 종류마다 실행 전에 적은 기대·근거와 실행 후 실제가 있고, 차이가 있었다면 원인(원천 해석·조건표 해석·계산식)과 수정을 적었습니다.
- 결과를 맞추려고 조건표·원자료·기대를 바꾸지 않았습니다.

## 저장과 다음 실습

결과 폴더를 저장하고 다시 열어 확인하세요. 보관할 결과는 재부팅 전에 USB 또는 개인 클라우드에 복사하세요. 다음 회차에는 조건의 원문 근거를 다시 검토합니다.
'''

EXPECT_TEMPLATE = '''# 기대 결과와 실제 대조

> 제공 빈 틀입니다. 보관하지 말고 바로 채웁니다.

기대 칸은 프로그램을 실행하기 **전에** 원자료 행과 조건표(입력/rules.csv)·원문으로 손으로 구해 적습니다. 실제 칸은 실행 후에 적습니다. 실제 출력을 복사해 기대 칸을 채우지 않습니다.

- 기대 칸을 쓴 시각(실행 전):
- 실행한 명령:
- 실행 시각:
- 사용한 입력: 입력/rules.csv, 자료/ 원자료

## 판단 입력을 만드는 결정

| 항목 | 정한 방법 | 근거(파일·절) | 이 결정으로 결과가 바뀌는 사례 |
|---|---|---|---|
| | | | |

## 사례 대조

| 사례 / 후보 | 사례 종류 | 원자료 행과 판단 입력 | 기대 판정·이유 | 근거(rule_id·원문 절) | 실제 결과 | 일치 / 차이와 수정 |
|---|---|---|---|---|---|---|
| | | | | | | |

## 손계산 대조

## 기대를 고친 경우(근거와 이유)

## 남은 미확인
'''


def build_judge(data):
    folder = JUDGE
    reset(folder)
    judge_inputs(folder, data)
    write(folder/'입력/README.md', f'이전 단계(SOP 구조와 결정표)의 완성본입니다. 판본 {VERSION}. rules.csv는 조건표, sop.json은 SOP 구조입니다.\n\n고치지 말고 읽기만 하세요. 자기 조건표를 쓰려면 이 파일은 그대로 두고 별도 폴더에 두어 열 이름이 입출력_계약.md와 같은지 먼저 확인하세요.\n')
    write(folder/'입출력_계약.md', judge_contract() + JUDGE_RESULT)
    write(folder/'check.py', JUDGE_CHECK)
    write(folder/'결과/README.md', 'judge.py, result.json, 기대결과.md를 여기에 저장합니다.\n')
    force_template(folder/'결과/기대결과.md', EXPECT_TEMPLATE, ['판단 입력을 만드는 결정', '기대 칸을 쓴 시각'])
    sections = [
        ('시작하기', '<p>VS Code에서 이 폴더를 열고 <a href="START.md">START.md</a>와 <a href="입출력_계약.md">입출력_계약.md</a>를 읽으세요.</p><pre>입력/   이전 단계 완성 조건표(rules.csv)와 SOP 구조(sop.json)\n자료/   경보 사례 48건의 원자료 4종, 오더 현황, 원문, 수집 설명\n        metrics/의 손실 식(지표_정의.md)과 값\n결과/   이번에 만들 judge.py, result.json, 기대결과.md\ncheck.py   단계별 구조 검사</pre><p>원자료는 수업용 시뮬레이터 로직으로 만든 교육용 가상 자료입니다. 판단 입력은 이미 정리된 표가 아니라 원천 네 곳에 흩어져 있고, 원천마다 주기·단위·빈 값의 이유가 다릅니다. 48건 × 후보 4개라 손으로 다 맞출 수 없으므로 코드로 처리하고 대표 사례를 직접 대조합니다.</p><p>먼저 AI에게 <b>파일을 바꾸지 말고</b> 원천 네 개의 모양을 설명하게 하고, 그 설명을 실제 파일과 대조하세요. 파일 이름은 백틱(`)으로 감싸 적습니다.</p>'),
        ('요구 정하기', '<p class="check">이번 실습의 판단 지점: <b>원천에서 판단 입력을 만드는 방법</b>을 원문과 수집 설명을 근거로 직접 정합니다. 수집 설명만으로 하나로 정해지지 않는 곳이 있으면 결정과 근거, 그 결정으로 결과가 바뀌는 사례를 기대결과.md에 적습니다.</p><p>그다음 기대 결과를 먼저 적습니다. 사례 종류마다 하나 이상, 원자료 행을 직접 열어 손으로 구한 판정과 근거를 적으세요. 프로그램 출력을 보고 기대 칸을 채우면 검증이 되지 않습니다.</p>'),
        ('AI와 만들기', '<p>구현 전에 계획만 받아 검토하세요. 규칙을 코드에 다시 적는 계획, 빈 값을 0이나 이전 값으로 채우는 계획, 단위를 그대로 쓰는 계획이 있으면 계획 단계에서 고칩니다.</p><ol><li>판단 입력 만들기부터 작게 만들고, 기대결과.md에 적은 사례의 입력이 원자료 행과 같은지 봅니다.</li><li>판정을 붙이고 기대 판정과 대조합니다.</li><li>비교를 붙이고 지표_정의.md 손계산과 대조합니다.</li><li>마지막으로 결과 형식과 저장을 맞춥니다.</li></ol><p>AI가 완료를 알리면 실행한 명령과 출력 원문을 붙여 달라고 요청합니다.</p><details><summary>요청을 정리할 때 볼 항목</summary><p>만들 결과 / 참고할 자료 / 정한 결정 / 바꾸지 않을 범위 / 이번 단계의 범위 / 성공을 확인할 사례</p></details>'),
        ('결과 확인하기', '<pre>python 결과/judge.py\npython check.py</pre><p>check.py는 judge.py·result.json·기대결과.md의 상태를 나눠 보여 줍니다. 구조 검사는 형식과 계약의 불변식만 봅니다. 판정이 맞는지는 다음 기준으로 원문·원자료와 대조하세요.</p><ul><li>판단 입력: 고른 사례의 입력값이 원자료 행(시각·단위 환산)과 같고, 값이 없으면 그 이유가 원천의 사정과 맞는지</li><li>경계: 원문의 「이상·초과·미만」대로 판정되는지</li><li>복수 조건: 경고·감점·제외가 함께 남는지, 감점이 규칙당 한 번인지</li><li>값 없음: 그 값이 필요한 후보만 보류되는지, 제외 사유가 있으면 제외와 미확인이 함께 남는지</li><li>비교: 지표_정의.md 손계산과 같은지</li></ul><p class="check">기대결과.md의 기대 칸과 실제 출력을 한 줄씩 대조하세요. 다르면 입력(원자료 행), 기대(근거), 실제(출력)를 함께 AI에 주고 원인을 찾게 한 뒤 필요한 부분만 고칩니다. 같은 사례와 이미 맞았던 사례를 다시 실행합니다.</p>'),
        ('저장하기', '<p>결과/judge.py, 결과/result.json, 결과/기대결과.md를 저장하고 다시 열어 확인하세요. 보관할 결과는 재부팅 전에 USB 또는 개인 클라우드에 복사합니다.</p><p>비교 합계는 교육용 비교값입니다. 실제 HYD 성과 점수와 다르며 순위가 실행 승인을 뜻하지 않습니다.</p>')]
    common_files(folder, JUDGE_START, ['입력/rules.csv의 규칙을 코드에 다시 적어 고정하지 않는다. 조건표를 읽어 판정한다.', '빈 값을 0이나 정상값, 이전 값으로 채우지 않는다. 결과를 맞추려고 조건표·원자료·기대를 바꾸지 않는다.', '원천 해석에서 판단이 필요한 곳은 학생에게 묻거나 미결로 표시한다. 임의로 정하지 않는다.'], '조건표를 읽는 조치 판정·비교 기능 만들기', '경보 사례 48건의 원자료에서 판단 입력을 만들고, 완성 조건표로 후보별 경고·감점·제외·정보 부족을 판정한 뒤 허용 후보만 교육용 손실로 비교합니다.', sections)


# ───────────── 실전반 실습2: 조치 검토 결과 ─────────────

REVIEW_CHECK = '"""결과/조치검토결과.json·.md의 구조와 계약 불변식 검사, 기대결과.md 기록 칸 확인. 판정의 의미 정답은 판정하지 않는다."""\n' + JUDGE_CHECK_COMMON + r'''
def check_review(jpath, mpath):
    if not jpath.is_file(): return '없음', [], ''
    try: review = json.loads(jpath.read_text(encoding='utf-8-sig'))
    except ValueError as e: return '확인 필요', [f'JSON 읽기 실패: {e}'], ''
    md = mpath.read_text(encoding='utf-8-sig') if mpath.is_file() else ''
    errs = [] if md else ['조치검토결과.md가 없습니다.']
    if not str(review.get('비교_기준', '')).strip(): errs.append('비교_기준(교육용 비교값과 HYD 점수·실행 승인의 구분 문장)이 없습니다.')
    dec = review.get('입력_결정')
    if not isinstance(dec, list) or not dec or any(not (d.get('항목') and d.get('결정') and d.get('근거')) for d in dec): errs.append('입력_결정(판단 입력을 만든 결정: 항목·결정·근거)이 필요합니다.')
    items = review.get('항목')
    if not isinstance(items, list): return '확인 필요', errs + ['항목 목록이 없습니다.'], ''
    got = [i.get('id') for i in items]
    if got != list(alarms): errs.append(f'항목: 경보_목록.csv의 사례 순서·구성과 다릅니다(빠짐 {sorted(set(alarms)-set(got))}).')
    for item in items:
        iid = item.get('id')
        if iid not in alarms: continue
        cands = item.get('후보') or []
        if [c.get('sop') for c in cands] != alarms[iid]: errs.append(f'{iid}: 후보 목록이 경보_목록.csv와 다릅니다.')
        if md and not re.search(r'^#+\s.*(?<![A-Za-z0-9])'+re.escape(iid)+r'(?![A-Za-z0-9])', md, re.M): errs.append(f'조치검토결과.md에 {iid} 절 제목이 없습니다.')
        for c in cands:
            at = f'{iid}/{c.get("sop")}'
            inputs = c.get('입력')
            if not isinstance(inputs, dict): errs.append(f'{at}: 입력(판단 입력 값)이 필요합니다.')
            else:
                for k in RULE_INPUTS:
                    if k not in inputs: errs.append(f'{at}: 입력에 {k}가 없습니다(값이 없으면 null).')
                errs += unit_errors(at, inputs)
            status = c.get('판정')
            if status not in STATUS: errs.append(f'{at}: 판정은 유지·제외·보류'); continue
            reasons = c.get('이유')
            if not isinstance(reasons, list): errs.append(f'{at}: 이유 목록 필요'); continue
            for r in reasons:
                if (r.get('규칙'), c.get('sop')) not in rule_actions: errs.append(f'{at}: 조건표에 없는 규칙·후보 {r.get("규칙")}')
                if r.get('결과') not in {'WARN','PENALTY','EXCLUDE','미확인'}: errs.append(f'{at}: 이유의 결과는 WARN·PENALTY·EXCLUDE·미확인')
                if not r.get('비교') or not r.get('출처') or not isinstance(r.get('실제_입력'), dict): errs.append(f'{at} {r.get("규칙")}: 실제_입력·비교·출처가 필요합니다.')
                if r.get('결과') == '미확인' and (not r.get('빠진_입력') or not r.get('빠진_이유')): errs.append(f'{at} {r.get("규칙")}: 미확인에는 빠진_입력과 빠진_이유가 필요합니다.')
            kinds = {r.get('결과') for r in reasons}
            if status == '제외' and 'EXCLUDE' not in kinds: errs.append(f'{at}: 제외인데 EXCLUDE 이유가 없습니다.')
            if status == '보류' and ('EXCLUDE' in kinds or '미확인' not in kinds): errs.append(f'{at}: 보류는 제외 없이 미확인 이유가 있어야 합니다.')
            if status == '유지' and kinds & {'EXCLUDE', '미확인'}: errs.append(f'{at}: 유지인데 제외·미확인 이유가 있습니다.')
            if not c.get('원문_출처'): errs.append(f'{at}: 원문_출처가 비었습니다.')
            checks = c.get('추가_확인')
            if not isinstance(checks, list) or (status == '보류' and not checks): errs.append(f'{at}: 추가_확인 목록이 필요하고 보류 후보는 비어 있으면 안 됩니다.')
            missing = [m for r in reasons if r.get('결과') == '미확인' for m in r.get('빠진_입력', [])]
            if any(not any(m in str(x) for x in checks or []) for m in missing): errs.append(f'{at}: 빠진 입력 {missing}이 추가_확인에 없습니다.')
            approval = c.get('승인') or {}
            if not approval.get('역할') or not approval.get('출처') or not approval.get('안내'): errs.append(f'{at}: 승인(역할·출처·안내)이 필요합니다.')
            value, rank = c.get('비교값'), c.get('순위')
            if status != '유지':
                if value or rank is not None: errs.append(f'{at}: 비교값·순위는 유지 후보에만 둡니다.')
            elif value is not None:
                keys = ['비용','생산','품질','에너지','감점','합계']
                if not all(num(value.get(k)) for k in keys): errs.append(f'{at}: 비교값에 {keys}가 숫자로 필요합니다.')
                elif abs(sum(value[k] for k in keys[:5]) - value['합계']) > 0.02: errs.append(f'{at}: 합계가 네 손실+감점과 다릅니다.')
            elif not c.get('비교_불가'): errs.append(f'{at}: 유지 후보에 비교값이 없으면 비교_불가 이유가 필요합니다.')
        opinion = item.get('검토_의견') or {}
        kept = [c for c in cands if c.get('판정') == '유지' and c.get('순위') is not None]
        top = sorted(c['sop'] for c in kept if c['순위'] == 1)
        top_total = min((c['비교값']['합계'] for c in kept if c['순위'] == 1 and isinstance(c.get('비교값'), dict) and num(c['비교값'].get('합계'))), default=None)
        held = [c.get('sop') for c in cands if c.get('판정') == '보류']
        impact = opinion.get('보류_영향')
        possible = []
        if not isinstance(impact, list): errs.append(f'{iid}: 검토_의견.보류_영향 목록이 필요합니다(보류 후보가 없으면 빈 목록).')
        else:
            if sorted(x.get('sop') for x in impact if isinstance(x, dict)) != sorted(held): errs.append(f'{iid}: 보류_영향에는 보류 후보 {held}가 하나씩 있어야 합니다.')
            for x in impact:
                if not isinstance(x, dict): errs.append(f'{iid}: 보류_영향 항목은 객체'); continue
                total, can = x.get('잠정_합계'), x.get('1위_가능')
                if total is not None and not num(total): errs.append(f'{iid} {x.get("sop")}: 잠정_합계는 숫자 또는 null')
                if can not in (True, False, None): errs.append(f'{iid} {x.get("sop")}: 1위_가능은 true·false·null')
                if not x.get('근거'): errs.append(f'{iid} {x.get("sop")}: 보류_영향.근거가 필요합니다.')
                if num(total) and top_total is not None and can is not None and can != (total <= top_total): errs.append(f'{iid} {x.get("sop")}: 1위_가능({can})이 잠정_합계 {total}와 1위 합계 {top_total}의 비교와 다릅니다.')
                if total is None and can is not None: errs.append(f'{iid} {x.get("sop")}: 잠정_합계를 계산하지 못했으면 1위_가능은 null입니다.')
                if can is not False: possible.append(x.get('sop'))
        rec = sorted(opinion.get('추천') or [])
        if rec != top and not (rec == [] and top and possible): errs.append(f'{iid}: 추천은 순위 1위 유지 후보이거나, 1위가 될 수 있는 보류 후보가 있어 추천을 미룰 때만 빈 목록입니다.')
        if not opinion.get('사유'): errs.append(f'{iid}: 검토_의견.사유가 필요합니다(추천이 없거나 미루면 그 사유).')
    return ('확인 필요' if errs else '통과'), errs, f'사례 {len(items)}건'
state, errs, note = check_review(root/'결과/조치검토결과.json', root/'결과/조치검토결과.md')
parts = [('review.py', '있음' if (root/'결과/review.py').is_file() else '없음', [], '', False), ('조치검토결과.json·.md', state, errs[:40] + ([f'… 외 {len(errs)-40}건'] if len(errs) > 40 else []), note, True)]
empty, total = empty_rows(root/'결과/기대결과.md', '실제 결과')
if empty is None: parts.append(('기대결과.md', '없음', [], '', False))
elif total == 0: parts.append(('기대결과.md', '아직 비어 있음', [], '실행 전에 기대 칸을 먼저 채우세요', False))
else: parts.append(('기대결과.md', '작성 중' if empty else '작성됨', [], f'행 {total}개 중 「실제 결과」 빈 칸 {empty}개' + (' — 실행 뒤 실제 결과를 적어 대조하세요' if empty else ''), False))
print('구조 검사 결과')
ok = report(parts)
kinds = missing_kinds(root/'결과/기대결과.md', '사례 종류', [('경계', ['경계']), ('제외와 값 없음이 겹친 후보', ['겹', '제외+', '제외와']), ('모두 제외·유지 후보 없음', ['모두 제외', '유지 후보 없음', '추천 없음']), ('값 없음', ['값 없음', '누락', '미확인']), ('결정에 따라 바뀌는 사례', ['결정', '갈래', '갈림']), ('보류 후보가 1위가 될 수 있는 사례', ['1위', '보류 후보'])])
notes(([f'START.md 사례 종류 중 기대결과.md 「사례 종류」 칸에서 찾지 못한 것: {", ".join(kinds)} (다른 말로 적었다면 그대로 두어도 됩니다).'] if kinds else []) + expect_time(root/'결과/기대결과.md'))
print('구조 검사는 형식과 계약의 불변식만 봅니다. 판정·이유·출처가 원문·원자료와 맞는지와 금액은 별도로 대조하세요.')
sys.exit(0 if ok else 1)
'''

REVIEW_START = '''# 후보별 조치 검토 결과 만들기

지난 회차 조치 조건표의 완성본에서 출발해, 쿨러 냉각 경보 사례 48건마다 조치 후보의 판정과 이유를 내고 허용된 후보만 교육용 손실 산식으로 비교한 **조치 검토 결과**를 만듭니다. 담당자가 이 결과를 읽고 어느 후보를 승인 요청할지, 무엇을 더 확인할지 결정할 수 있어야 합니다. 검토 결과의 순위는 실행 승인이 아닙니다.

## 출발점

- `입력/rules.csv`: 지난 회차 실습5(조치 조건표)의 완성본입니다. 고치지 말고 읽기만 합니다.
- `입력/sop.json`: 제공 SOP 구조입니다. 적용 조건·금지 조건·수행 단계·완료 기준·승인과 원문 출처가 있습니다.
''' + DATA_INTRO + '''
- `자료/오더_현황.csv`, `자료/metrics/`: 교육용 비교에 쓰는 오더 값과 손실 식(지표_정의.md에 손계산 예).
- `입출력_계약.md`: 결과 형식. `check.py`: 결과의 구조 검사.

지난 회차 결과가 없어도 시작할 수 있습니다. 지난 회차에 정한 판단 입력 방법이 있으면 이어서 씁니다.

## 직접 구현할 것

`결과/review.py`를 만들어 실행하면 `결과/조치검토결과.json`과 사람이 읽을 `결과/조치검토결과.md`가 생기게 합니다.

후보마다 다음을 담습니다.

| 항목 | 내용 |
|---|---|
| 판단 입력 | 원자료에서 만든 값, 값이 없으면 그 이유 |
| 판정 | 유지 · 제외 · 보류 |
| 이유 | 맞은 규칙과 미확인 규칙마다 규칙 ID, 실제 입력값, 비교식, 결과 종류 |
| 원문 출처 | 이유에 쓴 규칙의 출처와 후보 SOP의 HM-8 절 |
| 추가로 확인할 값 | 빠진 입력과 어디서 무엇을 확인하면 되는지. 유지 후보는 실행 전에 확인할 조건·완료 기준(sop.json) |
| 비교값·순위 | 유지 후보만. 비용·생산·품질·에너지·감점·합계와 순위 |
| 승인 | 실행 승인 역할과 출처, 비교 순위가 실행 승인이 아니라는 안내 |
| 보류 후보의 영향 | 보류 후보마다 아는 값만으로 계산한 잠정 합계와, 빠진 값이 확인되면 1위가 될 수 있는지 |

사례마다 검토 의견(추천 후보 또는 추천 없음·추천을 미룬 이유, 보류 후보와 그 영향)을 남깁니다. 결과에는 교육용 비교값과 실제 HYD 성과 점수(일곱 성분)를 구분하는 문장을 넣습니다.

## 작업 순서

1. **탐색만 요청**: AI에게 파일을 바꾸지 말고 입력/·자료/·입출력_계약.md를 읽어 원천 네 개의 모양, 이유·출처·승인·완료 기준을 어디서 얻는지 설명하게 합니다. 설명을 실제 파일과 대조합니다.
2. **요구와 기대 정리**: 이 결과를 읽을 담당자가 결정하려면 무엇이 보여야 하는지 자기 말로 정리합니다. 판단 입력을 만드는 방법과 근거를 정하고, `결과/기대결과.md`에 아래 사례 종류마다 하나 이상 원자료 행으로 기대 판정·이유·추가로 확인할 값을 먼저 적습니다. 다 쓰면 머리의 「기대 칸을 쓴 시각」을 적고 저장한 뒤 실행합니다.
3. **계획 검토**: 구현 계획만 먼저 받아 출력 계약의 항목이 모두 어디서 채워지는지 확인합니다. 원문에 없는 확인 항목을 만드는 계획은 고칩니다.
4. **작은 단위로 구현**: 판단 입력 → 판정과 이유 → 비교 → 검토 결과 작성 순서로 하나씩 만들고 실행합니다.
5. **출력 계약으로 품질 판정**: 조치검토결과.md를 담당자 입장에서 읽고 후보마다 계약 항목이 원문·원자료와 맞게 채워졌는지, 기대결과.md와 같은지 대조합니다.
6. **수정 요청**: 다르면 입력(사례·후보·원자료 행), 기대(근거), 실제(출력)를 함께 주고 그 부분만 고치게 합니다. 결과에 맞추려고 기대를 바꾸지 않습니다.
7. **저장·재열기**: 저장한 파일을 다시 열어 확인합니다.

''' + STEP_TIPS + '''
## 실행

```
python 결과/review.py
python check.py
```

## 기대 결과를 먼저 적을 사례 종류

- 경계: 예측 유온·예측 압력·팬 연속 시간이 기준값과 같거나 바로 위·아래인 후보(단위가 다른 원천 포함)
- 제외 사유와 값 없음이 겹친 후보: 제외를 유지하면서 빠진 값도 추가 확인에 남는지
- 모두 제외 또는 유지 후보가 없는 사례: 추천 없이 그 사유가 남는지
- 값 없음: 원천에서 값이 비는 이유가 서로 다른 사례
- 판단 입력을 만드는 결정에 따라 결과가 바뀌는 사례
- 보류 후보가 빠진 값이 확인되면 1위가 될 수 있는 사례: 검토 의견이 내가 정한 방침대로 나오는지
- 비교: 지표_정의.md 손계산과 같은지, 1위 후보의 승인 역할이 함께 보이는지

## 학생이 정할 것

원문·수집 설명만으로 하나로 정해지지 않아 학생이 근거를 찾아 정하는 지점입니다. 정한 내용·근거·바뀌는 사례를 `결과/기대결과.md` 「판단 입력을 만드는 결정」 표에 적습니다. AI는 이 지점을 정하기 전에 학생에게 묻습니다.

- 원천의 기록 방식이 두 가지로 읽히는 곳에서 판단 입력을 어떻게 만들지
- 보류 후보가 빠진 값이 확인되면 1위가 될 수 있을 때, 지금 1위 유지 후보를 승인 요청 대상으로 추천할지, 추천을 미루고 빠진 값 확인을 먼저 요청할지(근거를 원문에서 찾아 적습니다)

## 이번 범위 밖

조건표·SOP 구조의 수정(입력은 읽기만 합니다), 매뉴얼 원문 재검토와 근거 확장(다음 실습), 실제 조치 실행과 승인 요청 발송.

## 완료 조건

- `python 결과/review.py`가 사례 48건을 모두 처리하고 `python check.py`에서 조치검토결과가 통과합니다.
- 조치검토결과.md만 읽고도 후보별 판정 이유·원문 출처·추가로 확인할 값을 설명할 수 있습니다.
- 기대결과.md에 위 사례 종류마다 실행 전에 적은 기대·근거와 실행 후 실제가 있습니다.
- 비교 순위를 실행 승인처럼 쓰지 않았고, 결과를 맞추려고 조건표·원자료·기대를 바꾸지 않았습니다.

## 저장과 다음 실습

결과 폴더를 저장하고 다시 열어 확인하세요. 보관할 결과는 재부팅 전에 USB 또는 개인 클라우드에 복사하세요. 다음 실습에서는 매뉴얼 원문을 검토해 근거를 넓힙니다.
'''

REVIEW_RESULT = '''
## 출력 결과/조치검토결과.json

```
{
  "비교_기준": "교육용 비교값과 HYD 일곱 성분 점수, 실행 승인의 구분 문장",
  "입력_결정": [{"항목": "...", "결정": "...", "근거": "파일·절"}],
  "항목": [
    {"id": "E01", "설비": "HYD-..", "판단_시각": "...",
     "후보": [
       {"sop": "SOP-COOL-11", "판정": "유지 | 제외 | 보류",
        "입력": {"forecast_ts1": 숫자 또는 null, ...},
        "이유": [{"규칙": "rule_id", "결과": "WARN | PENALTY | EXCLUDE | 미확인", "실제_입력": {"입력": 값}, "비교": "forecast_ts1 >= 55 ℃", "출처": "...", "빠진_입력": ["미확인일 때"], "빠진_이유": "미확인일 때 원천의 사정"}],
        "원문_출처": ["..."],
        "추가_확인": ["..."],
        "비교값": {"비용": 0, "생산": 0, "품질": 0, "에너지": 0, "감점": 0, "합계": 0} 또는 null,
        "비교_불가": ["유지 후보인데 비교값이 없을 때 이유"],
        "순위": 1 또는 null,
        "승인": {"역할": "...", "출처": "...", "안내": "비교 순위는 실행 승인이 아니다 ..."}}
     ],
     "검토_의견": {"추천": ["1위 유지 후보"] 또는 [], "사유": "...", "보류": ["..."],
                 "보류_영향": [{"sop": "보류 후보", "잠정_합계": 숫자 또는 null, "1위_가능": true | false | null, "근거": "..."}]}}
  ]
}
```

- `항목`과 후보의 순서는 `자료/경보_목록.csv`와 같다. `이유`에는 맞은 규칙과 미확인 규칙만 둔다.
- `보류_영향`에는 보류 후보마다 한 항목을 둔다(보류 후보가 없으면 빈 목록). `잠정_합계`는 그 후보를 아는 값만으로 비교 식에 넣은 합계다(미확인 규칙의 감점은 넣지 않는다). 비교 식에 필요한 값이 없으면 `null`이다. `1위_가능`은 `잠정_합계`가 지금 1위 유지 후보의 합계 이하이면 `true`, 크면 `false`, 계산하지 못했으면 `null`이다.
- `추천`은 순위 1위 유지 후보다. 1위가 될 수 있는 보류 후보(`1위_가능`이 `false`가 아닌 후보)가 있어 추천을 미루기로 정했다면 빈 목록으로 두고, `사유`에 먼저 확인할 값을 적는다.
- `추가_확인`에는 미확인 규칙의 빠진 입력 이름을 그대로 넣는다.
- `결과/조치검토결과.md`는 같은 내용을 사례마다 절로 나눠 사람이 읽게 쓴다. 각 절 제목에 사례 id를 넣는다.
'''


def build_review(data):
    folder = REVIEW
    reset(folder)
    judge_inputs(folder, data)
    write(folder/'입력/README.md', f'지난 회차 조치 조건표의 완성본(rules.csv)과 제공 SOP 구조(sop.json)입니다. 판본 {VERSION}.\n\n고치지 말고 읽기만 하세요. 자기 조건표를 쓰려면 이 파일은 그대로 두고 별도 폴더에 두어 열 이름이 입출력_계약.md와 같은지 먼저 확인하세요.\n')
    write(folder/'입출력_계약.md', judge_contract().replace('# 판정 기능의 입출력 계약', '# 조치 검토 결과의 입출력 계약').replace('(`input_decisions`)', '(`입력_결정`)') + REVIEW_RESULT)
    write(folder/'check.py', REVIEW_CHECK)
    write(folder/'결과/README.md', 'review.py, 조치검토결과.json, 조치검토결과.md, 기대결과.md를 여기에 저장합니다.\n')
    force_template(folder/'결과/기대결과.md', EXPECT_TEMPLATE.replace('| 기대 판정·이유 |', '| 기대 판정·이유·추가로 확인할 값 |'), ['판단 입력을 만드는 결정', '기대 칸을 쓴 시각', '추가로 확인할 값'])
    sections = [
        ('시작하기', '<p>VS Code에서 이 폴더를 열고 <a href="START.md">START.md</a>와 <a href="입출력_계약.md">입출력_계약.md</a>를 읽으세요.</p><pre>입력/   지난 회차 완성 조건표(rules.csv)와 제공 SOP 구조(sop.json)\n자료/   경보 사례 48건의 원자료 4종, 오더 현황, 원문, 수집 설명\n        metrics/의 손실 식(지표_정의.md)과 값\n결과/   이번에 만들 review.py, 조치검토결과.json·.md, 기대결과.md\ncheck.py   단계별 구조 검사</pre><p>원자료는 수업용 시뮬레이터 로직으로 만든 교육용 가상 자료입니다. 48건 × 후보 4개의 판단 입력이 원천 네 곳에 흩어져 있어 코드로 처리하고 대표 사례를 직접 대조합니다.</p><p>먼저 AI에게 <b>파일을 바꾸지 말고</b> 원천의 모양과 이유·출처·승인·완료 기준을 어느 파일에서 얻는지 설명하게 하고, 그 설명을 실제 파일과 대조하세요. 파일 이름은 백틱(`)으로 감싸 적습니다.</p>'),
        ('요구 정하기', '<p>이 결과를 읽을 사람은 조치 승인을 요청할 담당자입니다. 그 사람이 결정하려면 무엇이 보여야 하는지 먼저 정하세요.</p><ul><li>후보마다 판정과 그 이유가 실제 입력값과 함께 보이는가</li><li>이유마다 원문으로 돌아갈 출처가 있는가</li><li>보류·제외 후보에서 무엇을 어디서 더 확인하면 되는가</li><li>1위 후보도 누가 승인하고 실행 전에 무엇을 확인해야 하는가</li></ul><p class="check">이번 실습의 판단 지점: 판단 입력을 원천에서 만드는 방법을 근거로 정하고, 정한 방법에 따라 결과가 바뀌는 사례를 기대결과.md에 적습니다. 지난 회차에 정한 방법이 있으면 이어서 씁니다. 또 하나는 담당자 입장의 판단입니다. 보류 후보가 빠진 값만 확인되면 1위가 될 수 있을 때 지금 추천을 낼지, 확인을 먼저 요청할지 원문(HI-01·작업기준 4절)을 근거로 정합니다.</p><p>기대 판정·이유·추가로 확인할 값은 원자료 행으로 먼저 적습니다. 출력을 보고 기대를 채우지 않습니다.</p>'),
        ('AI와 만들기', '<p>구현 전에 계획만 받아, 출력 계약의 항목(판단 입력·판정·이유·원문 출처·추가로 확인할 값·비교값·승인)이 각각 어느 입력에서 채워지는지 확인하세요. 원문에 없는 확인 항목을 만드는 계획, 빈 값을 0이나 이전 값으로 채우는 계획은 고칩니다.</p><ol><li>판단 입력부터 만들고 기대결과.md의 사례와 원자료 행을 맞춰 봅니다.</li><li>판정과 이유를 붙이고 경계·값 없음 사례를 확인합니다.</li><li>비교를 붙이고 지표_정의.md 손계산과 대조합니다.</li><li>sop.json에서 승인 역할·실행 전 확인·완료 기준을 읽어 검토 결과에 붙입니다.</li></ol><p>AI가 완료를 알리면 실행한 명령과 출력 원문을 붙여 달라고 요청합니다.</p><details><summary>요청을 정리할 때 볼 항목</summary><p>만들 결과 / 참고할 자료 / 정한 결정 / 바꾸지 않을 범위 / 성공을 확인할 사례</p></details>'),
        ('결과 확인하기', '<pre>python 결과/review.py\npython check.py</pre><p>check.py는 review.py·조치검토결과·기대결과.md의 상태를 나눠 보여 줍니다. 구조 검사는 형식과 계약의 불변식만 봅니다. 내용은 다음 기준으로 원문·원자료와 대조하세요.</p><ul><li>판단 입력이 원자료 행(시각·단위 환산)과 같고, 값이 없으면 그 이유가 원천의 사정과 맞는지</li><li>경계값이 원문의 「이상·초과·미만」대로 판정되는지</li><li>제외와 값 없음이 겹친 후보에서 제외를 유지하면서 빠진 값이 추가 확인에 남는지</li><li>추천이 없는 사례에 그 사유가 남는지</li><li>1위 후보에도 승인 역할과 실행 전 확인 조건이 함께 보이고, 순위가 실행 승인이 아니라는 안내가 있는지</li></ul><p class="check">이번 실습의 판단 지점: <b>출력 계약으로 결과물의 품질을 판정합니다.</b> 조치검토결과.md만 읽고 후보마다 판정·이유·원문 출처·추가로 확인할 값·승인 구분이 있고, 원문 절까지 따라갈 수 있는지 확인하세요. 기대결과.md와 다르면 입력·기대·실제를 함께 주고 필요한 부분만 고친 뒤 이미 맞았던 사례를 다시 확인합니다.</p>'),
        ('저장하기', '<p>결과/review.py, 결과/조치검토결과.json, 결과/조치검토결과.md, 결과/기대결과.md를 저장하고 다시 열어 확인하세요. 보관할 결과는 재부팅 전에 USB 또는 개인 클라우드에 복사합니다.</p><p>비교 합계는 교육용 비교값입니다. 실제 HYD 성과 점수와 다르며 순위가 실행 승인을 뜻하지 않습니다.</p>')]
    common_files(folder, REVIEW_START, ['입력/rules.csv의 규칙을 코드에 다시 적어 고정하지 않는다. 조건표를 읽어 판정한다.', '빈 값을 0이나 정상값, 이전 값으로 채우지 않는다. 결과를 맞추려고 조건표·원자료·기대를 바꾸지 않는다.', '비교 순위를 실행 승인으로 쓰지 않는다. 승인 역할과 실행 전 확인은 sop.json의 원문 근거로만 적는다.', '원천 해석에서 판단이 필요한 곳은 학생에게 묻거나 미결로 표시한다. 임의로 정하지 않는다.'], '후보별 조치 검토 결과 만들기', '경보 사례 48건의 원자료와 완성 조건표로 후보별 판정·이유·원문 출처·추가로 확인할 값을 만들고, 허용 후보만 교육용 손실로 비교합니다. 순위는 실행 승인이 아닙니다.', sections)


ENTRIES = [
    ('integrated-03-criteria', '통합반', 'SOP 구조와 조치 결정표 만들기', CRITERIA),
    ('integrated-03-judge', '통합반', '조건표를 읽는 조치 판정·비교 기능 만들기', JUDGE),
    ('practical-03-review', '실전반', '후보별 조치 검토 결과 만들기', REVIEW),
]


def main():
    data, _ = build_data()
    build_criteria(data)
    build_judge(data)
    build_review(data)
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
