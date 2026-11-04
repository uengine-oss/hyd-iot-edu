"""냉각 경보 조치 판단 묶음 네 랩의 학생 폴더 · ZIP을 만든다 — 통합반 03회차 실습2(조치 기준) · 실습3(판단 기능),
실전반 02회차 실습5(조치 조건표) · 03회차 실습2(조치 검토 결과).

원자료 코어는 data_conditions.py 한 벌(고정 시드, 같은 입력이면 같은 바이트)이고, 랩마다 대조에 쓰는 파일만 넣는다.
단계 랩 틀(START.md 「진행 단계」 한 줄 = guide.html 한 절)과 작업 규칙 정본(STEP_RULES)은 build_labs.py에서 가져온다 — 문구 사본을 두지 않는다.
판정 랩의 입력/(조건표 · SOP 구조)은 조건 랩의 강사 검증 판(reference/session3/criteria.py, 지점1 가 · 지점2 가)이다 — 강사 참조 · 검사기 고의 손상 · 랩 사슬 확인은 reference/session3/run_reference.py.

이름: 판단 규칙의 표는 두 반 모두 「조건표」(`결과/조건표.csv`)다. 처음 나오는 자리에서 DMN의 결정표라고 한 번 푼다(두 반 조건 랩).
결과 JSON의 키는 영어 snake_case(코딩랩.md K-55)이고 계약에는 형식과 뜻만 둔다(K-43 — 판정 절차는 원문 · 작업기준이 가진다).
판정 랩의 「학생이 정할 것」은 실라버스 행 안의 기능에 있다 — 판단 입력의 정보 부족 처리(끊긴 기록)와 허용 후보 비교(경고 후보).
가이드(guide.html, 회차 안내가 가리키는 같은 바이트의 안내.html)는 build_labs.step_guide 틀로 만든다 — 2회차 랩과 같은 절 구조 · 블록 · 도구 첫 사용 안내(B.TOOL).
「막히면」은 이 랩의 check.py · python을 새 폴더에서 실제로 돌려 본 출력만 쓴다(가이드.md P-167).

사용: HYD_MAIN_ROOT=<main 체크아웃> python build_judgement_labs.py [--lab integrated-03-criteria|integrated-03-judge|practical-02-conditions|practical-03-review] [--check]
  --check   두 번 만들어 랩 폴더 바이트가 같은지만 본다(폴더는 다시 쓴다).
package-index · catalog 등록은 하지 않는다 — ZIP만 묶는다(등록은 lab_package.register / build_launcher.py로 따로).
"""
from pathlib import Path
import argparse
import csv
import hashlib
import io
import json
import shutil
import sys

import build_labs as B
from build_labs import H, S, STEP_RULES, req_template, step_start, tree, write
import data_conditions as DC
import data_session2 as D2
from lab_package import pack

sys.path.insert(0, str(B.TEACHER/'session3'))
import criteria as CR  # noqa: E402  강사 검증 판(판정 랩 입력)

OUT = B.OUT
LABS = {
    'integrated-03-criteria': OUT/'통합반/실습/03회차/랩/03일차_실습2_조치기준만들기',
    'integrated-03-judge': OUT/'통합반/실습/03회차/랩/03일차_실습3_판단기능만들기',
    'practical-02-conditions': OUT/'실전반/실습/02회차/랩/02일차_실습5_조치조건표',
    'practical-03-review': OUT/'실전반/실습/03회차/랩/03일차_실습2_판단기능만들기',
}
TITLES = {   # 랩 제목 = 실라버스 행 제목. 다음 실습을 이름으로 가리킬 때도 여기서 읽는다(K-144)
    'integrated-03-criteria': '작업 절차와 판단 조건을 연결해 조치 기준 만들기',
    'integrated-03-judge': '설비 조건별 최적의 조치를 비교하는 판단 기능 만들기',
    'practical-02-conditions': '작업 기준의 복합 조건과 예외를 조치 조건표로 표현하기',
    'practical-03-review': '판정·성과 비교를 조치 검토 결과로 완성하기',
}
MINE = {   # 내 앞 결과를 쓰는 길(선택 — 가이드.md P-83 · 코딩랩.md K-63). START 「출발점」과 가이드 첫 화면이 같은 문장을 쓴다
    'integrated-03-criteria': ('내 모델을 쓸 때: 제공 입력은 그대로 두고 내 `schema.json` · `graph.json`을 `결과/내_입력/`에 복사해, 형식과 ID 짓는 법이 제공 모델과 같은지 먼저 견준 뒤 씁니다. '
                               '구조 검사는 `결과/내_입력/graph.json`이 있으면 그 모델의 ID로 보고, 어느 모델을 봤는지 첫 줄에 찍습니다. 내 모델이 없어도 제공된 모델로 끝까지 할 수 있습니다.'),
    'integrated-03-judge': ('내 조치 기준을 쓸 때: 제공 입력은 그대로 두고 내 `조건표.csv` · `sop.json`을 `결과/내_입력/`에 복사해, 열 이름 · ID가 `입출력_계약.md`와 같은지 먼저 견준 뒤 씁니다. '
                            '구조 검사는 `결과/내_입력/`에 있는 파일을 기준으로 보고, 어느 파일을 봤는지 첫 줄에 찍습니다. 내 조치 기준이 없어도 제공된 입력으로 끝까지 할 수 있습니다.'),
    'practical-03-review': ('내 조건표를 쓸 때: 제공 입력은 그대로 두고 내 `조건표.csv`를 `결과/내_입력/`에 복사해, 열 이름 · 규칙이 거는 후보가 `입출력_계약.md`와 같은지 먼저 견준 뒤 씁니다. '
                            '구조 검사는 `결과/내_입력/`에 있는 파일을 기준으로 보고, 어느 파일을 봤는지 첫 줄에 찍습니다. 내 조건표가 없어도 제공된 조건표로 끝까지 할 수 있습니다.'),
}
LAB4_INPUT = OUT/'통합반/실습/02회차/랩/02일차_실습4_그래프구현과검증/입력'   # 앞 단계 입력 — 같은 바이트여야 한다(설계 조건 검사 4)
RULES_LINE = '`AGENTS.md` · `.github/copilot-instructions.md` · `CLAUDE.md` — Codex와 GitHub Copilot이 지키는 작업 규칙(세 파일이 같은 내용). 학생도 함께 읽습니다.'
TABLE_HEADER = 'rule_id,action,condition_index,logic,input,operator,value,unit,boundary_included,result,penalty_manwon,reason,source_section\n'


# ───────────── 계약(형식과 뜻만 — K-43) ─────────────
CODES_FROM_TARGETS = '`targets.csv`의 `kind` · `codes`'
CODES_FROM_EXPORT = '판단 시스템 결정표 내보내기의 「스킬」 절 — 종류 칸과, 동작 칸을 「코드 이름」 절의 괄호 안 코드로 바꾼 것'
TABLE_CONTRACT = '''## 조건표 (`결과/조건표.csv`)

조건표는 다음 실습의 판정 기능이 그대로 읽는 입력이다. 열 이름을 바꾸면 다음 단계에서 읽지 못한다. 이 문서는 형식과 뜻만 정하고, 어떤 조건을 어느 조치에 걸지는 원문에서 정한다.

열: `rule_id,action,condition_index,logic,input,operator,value,unit,boundary_included,result,penalty_manwon,reason,source_section`

- 비교 하나가 한 행이다. 같은 `rule_id` · `action`의 행은 한 규칙 묶음이고 `condition_index`를 1부터 차례로 적으며 `logic`은 `AND`다. OR는 다른 `rule_id`로 나눈다.
- `action`: `자료/targets.csv`의 SOP ID 하나. 같은 규칙을 여러 조치에 걸면 조치마다 묶음 전체를 적는다. 표에 없는 조치 · 규칙 조합은 그 조치에 그 규칙을 걸지 않는다는 뜻이다.
- `result`: `WARN`(경고) · `PENALTY`(감점) · `EXCLUDE`(제외). 같은 묶음의 `result` · `penalty_manwon` · `reason` · `source_section`은 모든 행에서 같다. `PENALTY`만 `penalty_manwon`(만원)을 적고 나머지는 빈칸이다.
- `operator`: `>=` · `>` · `<=` · `<` · `==` · `!=` · `has_other_than`(목록 입력에 기준값이 아닌 항목이 하나라도 있음). `boundary_included`: 기준값 자체가 조건에 들어가면 `예`, 들어가지 않으면 `아니오`, 글자 · 목록 비교는 `해당없음`.
- `input`과 단위: `forecast_ts1`(조치 후 예측 유온, ℃) · `forecast_ps1`(조치 후 예측 토출 압력, bar) · `fan100_hours`(팬 100 % 연속 운전 시간, h) · `plc_mode`(`REMOTE_AUTO` · `REMOTE_MANUAL` · `LOCAL`) · `plc_state`(`RUN` · `TRIP` · `STOP`) · `skill_kind`(조치 종류 `control` · `work_order`) · `skill_code`(실행 코드 목록). `skill_kind` · `skill_code` 값이 오는 곳: {codes_from}. 숫자 입력은 `unit`을 적는다.
- 목록 입력(`skill_code`)에는 `has_other_than`만 쓴다.
- `source_section`: 이 행의 근거를 다른 사람이 다시 찾을 수 있게 원문의 문서와 절을 적는다(여러 개면 `;`로 나눈다). 원문에서 근거 문장을 찾지 못한 행이면 그렇다는 것과, 그 행을 가져온 곳(파일과 그 안의 규칙 ID)을 적는다.

모양을 보이는 한 줄(이 과제의 규칙이 아니다):

```
R0,SOP-COOL-00,1,AND,forecast_ts1,>=,0,℃,예,WARN,,이유 문장,문서 절
```
'''

SOP_CONTRACT = '''## SOP 구조 (`결과/sop.json`)

키는 영어로 적고 값(원문 문장 · 역할 이름)은 원문 그대로 적는다.

```
{
  "document": {"id": "...", "revision": "...", "file": "자료/..."},
  "failure_modes": [ {"id": "failuremodes.csv의 ID", "name": "...", "source": "..."} ],
  "causes": [ {"id": "cause:...", "name": "...", "source": "..."} ],
  "sops": [
    {
      "id": "targets.csv의 SOP ID", "name": "...", "kind": "control 또는 work_order 또는 null", "codes": ["..."],
      "source": "문서 절", "failure_mode": "고장 유형 ID",
      "model_refs": {"assets": ["..."], "components": ["..."], "sensors": ["..."], "not_linked": "..."},
      "apply_conditions": [ {"text": "...", "source": "...", "rules": ["rule_id"]} ],
      "prohibitions": [ {"type": "금지 또는 제한", "text": "...", "source": "...", "rules": []} ],
      "steps": [ {"order": 1, "text": "...", "source": "..."} ],
      "completion": [ {"text": "...", "source": "...", "rules": []} ],
      "approval": {"role": "...", "source": "..."}
    }
  ],
  "relations": [ {"type": "...", "from": "ID", "to": "ID", "source": "..."} ]
}
```

- 키의 뜻: `document` 원문 문서(식별자 · 판 · 파일), `failure_modes` 고장 유형, `causes` 원인, `sops` 조치 절차, `kind` 조치 종류, `codes` 실행 코드, `source` 출처,
  `failure_mode` 그 절차가 다루는 고장 유형, `model_refs` 모델 참조(`assets` 설비 · `components` 구성 요소 · `sensors` 센서 · `not_linked` 걸지 않은 대상과 까닭),
  `apply_conditions` 적용 조건, `prohibitions` 금지 조건, `steps` 수행 단계(`order` 순서), `completion` 완료 기준, `approval` 승인(`role` 역할), `rules` 이 조건을 옮긴 조건표의 `rule_id`, `relations` 관계 목록.
- `targets.csv`의 SOP는 `sops`에 한 번씩 있다. `steps`의 `order`는 1부터 차례로 붙인다.
- `model_refs`의 값은 `입력/graph.json`에 있는 ID만 쓴다 — `assets`에는 설비, `components`에는 구성 요소, `sensors`에는 센서의 ID. 모델에 없는 대상은 ID를 만들지 않고 `not_linked`에 그 까닭을 적는다.
- `kind` · `codes` 값이 오는 곳: {codes_from}. 그곳에 같은 절차가 없으면 `kind`는 `null`, `codes`는 빈 목록이다.
- `causes`의 `id`는 `cause:`로 시작하는 영어 소문자 · 하이픈 이름이다.
- `relations`의 `type`: `MITIGATED_BY`(고장 유형 → 즉시 완화 SOP) · `REMEDIED_BY`(고장 유형 → 근본 조치 SOP) · `ADDRESSES`(SOP → 그 SOP가 맞는 원인). 양 끝은 이 파일의 `failure_modes` · `causes` · `sops`에 있는 ID다.
- 각 항목의 `source`는 문서 절과 SOP 단계(예: `HM-8.5 SOP-COOL-11 단계 2`)다.
- `approval`은 원문 승인 줄의 역할과 출처다. 원문에서 그 절차의 승인을 찾지 못하면 역할을 만들지 않고 `role`을 `미확인`으로 시작해 찾아본 결과를 적으며, `source`에는 찾아본 절을 적는다.
- 조건과 조건표의 연결은 `rules`에 조건표의 `rule_id`로 적는다. 조건표로 옮기지 않은 조건은 빈 목록이다.
'''


# ───────────── 검사기(구조만 — 의미 정답은 판정하지 않는다, K-51) ─────────────
# 기록 파일(요구사항 · 판단기록 · 기대결과.md)의 표는 한 곳에서 본다 — 칸이 채워졌는지와, 줄마다 칸 수가 머리 줄과 같은지
# (리허설: 36줄 대조 표에서 한 줄의 칸이 밀렸는데 「작성됨」으로 통과했다).
RECORD_CHECK = r'''def md_cells(line):
    # 마크다운 표 한 줄의 칸 목록 — 칸 안의 글자 |는 \| 로 쓴다
    s = line.strip()
    s = s[1:] if s.startswith('|') else s
    s = s[:-1] if s.endswith('|') and not s.endswith('\\|') else s
    return [c.strip() for c in re.split(r'(?<!\\)\|', s)]
def table_rows(path, column):
    # 마크다운 표에서 column으로 시작하는 칸이 있는 표의 (데이터 행 수, 그 칸이 빈 행 수)
    if not path.is_file(): return None
    head, total, empty = None, 0, 0
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        if not line.startswith('|'): head = None; continue
        cells = md_cells(line)
        if head is None: head = cells; continue
        if set(''.join(cells)) <= set('-: '): continue
        idx = [k for k, h in enumerate(head) if h.startswith(column)]
        if not idx or not any(cells): continue
        total += 1
        if idx[0] >= len(cells) or not cells[idx[0]]: empty += 1
    return total, empty
def record_part(path, column, label):
    got = table_rows(path, column)
    if got is None: return (f'{path.name} {label}', '없음', [], '', False)
    total, empty = got
    if total == 0 or empty == total: return (f'{path.name} {label}', '아직 비어 있음', [], f'「{column}」 칸을 채웁니다', False)
    return (f'{path.name} {label}', '작성 중' if empty else '작성됨', [], f'행 {total}개 중 빈 칸 {empty}개' if empty else f'행 {total}개', False)
def shape_part(path):
    # 표마다 머리 줄과 칸 수가 다른 줄 — 칸이 밀리면 뒤 칸의 값이 다른 칸에 들어가 대조가 어긋난다
    name = f'{path.name} 표 칸 수'
    if not path.is_file(): return (name, '없음', [], '', False)
    errs, head = [], None
    for no, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
        if not line.startswith('|'): head = None; continue
        n = len(md_cells(line))
        if head is None: head = n; continue
        if n != head: errs.append(f'{path.name}:{no} 칸 {n}개 — 이 표의 머리 줄은 {head}칸입니다. 칸이 밀렸는지 보고, 칸 안의 글자 |는 \\| 로 씁니다.')
    return (name, '확인 필요' if errs else '통과', errs, '', True)
def report(parts):
    ok = True
    for name, state, errs, note, required in parts:
        print(f'- {name}: {state}' + (f' — {note}' if note else ''))
        for e in errs[:40]: print('    ' + e)
        if len(errs) > 40: print(f'    … 외 {len(errs) - 40}건')
        if required and state != '통과': ok = False
    return ok
'''
TABLE_CHECK = r'''HEADER = ['rule_id','action','condition_index','logic','input','operator','value','unit','boundary_included','result','penalty_manwon','reason','source_section']
OPS = {'>=':'예','<=':'예','>':'아니오','<':'아니오','==':'해당없음','!=':'해당없음','has_other_than':'해당없음'}
NUMERIC = {'forecast_ts1','forecast_ps1','fan100_hours'}
TEXT = {'plc_mode': {'REMOTE_AUTO','REMOTE_MANUAL','LOCAL'}, 'plc_state': {'RUN','TRIP','STOP'}, 'skill_kind': {'control','work_order'}}
LIST_INPUTS = {'skill_code'}
INPUTS = NUMERIC | set(TEXT) | LIST_INPUTS
def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)
def check_table(path, sop_ids):
    """(상태, 오류 목록, 규칙 묶음 수, rule_id 집합). 상태: 없음 · 빈 틀 · 통과 · 확인 필요."""
    if not path.is_file(): return '없음', [], 0, set()
    header, table = read_csv(path)
    if header != HEADER: return '확인 필요', ['열 이름 · 순서가 계약과 다릅니다: ' + ','.join(header or [])], 0, set()
    if not table: return '빈 틀', [], 0, set()
    errs, groups = [], {}
    for line, r in enumerate(table, 2):
        at = f'{path.name}:{line}'
        if r['action'] not in sop_ids: errs.append(f'{at} targets.csv에 없는 action {r["action"]}')
        if r['logic'] != 'AND': errs.append(f'{at} logic은 AND입니다(OR는 다른 rule_id로 나눕니다).')
        if r['input'] not in INPUTS: errs.append(f'{at} 계약에 없는 input {r["input"]}')
        if r['operator'] not in OPS: errs.append(f'{at} 계약에 없는 operator {r["operator"]}')
        elif OPS[r['operator']] != r['boundary_included']: errs.append(f'{at} boundary_included({r["boundary_included"]})가 operator {r["operator"]}와 맞지 않습니다.')
        if r['input'] in LIST_INPUTS and r['operator'] != 'has_other_than': errs.append(f'{at} 목록 입력 {r["input"]}에는 has_other_than만 씁니다.')
        if r['operator'] == 'has_other_than' and r['input'] not in LIST_INPUTS: errs.append(f'{at} has_other_than은 목록 입력에만 씁니다.')
        if r['input'] in TEXT and r['operator'] in ('==', '!=') and r['value'] not in TEXT[r['input']]: errs.append(f'{at} {r["input"]}의 값 {r["value"]}은 계약에 없는 값입니다.')
        if r['input'] in NUMERIC:
            try: float(r['value'])
            except ValueError: errs.append(f'{at} 숫자 입력의 기준값이 숫자가 아닙니다.')
            if not r['unit']: errs.append(f'{at} 숫자 입력의 unit이 비었습니다.')
        if r['result'] not in {'WARN','PENALTY','EXCLUDE'}: errs.append(f'{at} result는 WARN · PENALTY · EXCLUDE 가운데 하나입니다.')
        if r['result'] == 'PENALTY':
            try: float(r['penalty_manwon'])
            except ValueError: errs.append(f'{at} PENALTY 행에 penalty_manwon이 없습니다.')
        elif r['penalty_manwon']: errs.append(f'{at} PENALTY가 아닌 행에 penalty_manwon이 있습니다.')
        if not r['reason'] or not r['source_section']: errs.append(f'{at} reason · source_section이 필요합니다.')
        key = (r['rule_id'], r['action']); head = (r['result'], r['penalty_manwon'], r['reason'], r['source_section'])
        g = groups.setdefault(key, {'head': head, 'index': []})
        if g['head'] != head: errs.append(f'{at} 같은 묶음 {key}의 result · penalty · reason · source가 다릅니다.')
        try: g['index'].append(int(r['condition_index']))
        except ValueError: errs.append(f'{at} condition_index가 정수가 아닙니다.')
    for key, g in groups.items():
        if sorted(g['index']) != list(range(1, len(g['index']) + 1)): errs.append(f'{path.name} 묶음 {key}: condition_index가 1부터 차례가 아닙니다: {g["index"]}')
    return ('확인 필요' if errs else '통과'), errs, len(groups), {k[0] for k in groups}
''' + RECORD_CHECK

PICK = r'''def pick(name):
    # 검사의 기준 입력: 결과/내_입력/에 같은 이름 파일이 있으면 그것, 없으면 제공 입력/. 고른 파일을 찍는다(조용히 바꾸지 않는다).
    mine = root/'결과/내_입력'/name
    if mine.is_file():
        print(f'기준 입력: 결과/내_입력/{name} (내 입력)')
        return mine
    if (root/'결과/내_입력').is_dir():
        print(f'기준 입력: 입력/{name} — 결과/내_입력/에 {name}이 없어 제공 입력으로 봅니다')
    else:
        print(f'기준 입력: 입력/{name}')
    return root/'입력'/name
'''
CRITERIA_CHECK = r'''"""결과/sop.json · 조건표.csv의 구조 검사와 요구사항.md 기록 칸 확인. 생성 · 수정 · 네트워크 접속을 하지 않는다.
의미(조건 · 경계 · 출처가 원문과 맞는지, 사건의 판정)는 판정하지 않는다 — 원자료와 따로 대조한다.
모델 ID는 결과/내_입력/graph.json이 있으면 그것으로, 없으면 입력/graph.json으로 본다(어느 쪽을 봤는지 첫 줄에 찍는다).
사용: python check.py
"""
from pathlib import Path
import csv, json, re, sys
root = Path(__file__).resolve().parent
''' + TABLE_CHECK + PICK + r'''
sop_ids = [r['sop_id'] for r in read_csv(root/'자료/targets.csv')[1]]
fm_ids = {r['failure_mode_id'] for r in read_csv(root/'자료/failuremodes.csv')[1]}
graph = json.loads(pick('graph.json').read_text(encoding='utf-8-sig'))
kind_of = {n['props']['id']: n['labels'][0] for n in graph['nodes']}
SLOT = {'assets': 'Asset', 'components': 'Component', 'sensors': 'Sensor'}
RELATIONS = {'MITIGATED_BY': ('failure_modes', 'sops'), 'REMEDIED_BY': ('failure_modes', 'sops'), 'ADDRESSES': ('sops', 'causes')}
def items(value, key):
    v = value.get(key)
    return v if isinstance(v, list) else None
def check_sop(path, rule_ids):
    if not path.is_file(): return '없음', [], ''
    try: sop = json.loads(path.read_text(encoding='utf-8-sig'))
    except ValueError as e: return '확인 필요', [f'JSON 읽기 실패: {e}'], ''
    if not isinstance(sop, dict) or not sop.get('sops'): return '빈 틀', [], ''
    errs, unconfirmed = [], []
    fms = [f.get('id') for f in sop.get('failure_modes') or [] if isinstance(f, dict)]
    causes = [c.get('id') for c in sop.get('causes') or [] if isinstance(c, dict)]
    for f in fms:
        if f not in fm_ids: errs.append(f'failure_modes {f}: failuremodes.csv에 없는 고장 유형 ID입니다.')
    for c in causes:
        if not isinstance(c, str) or not re.fullmatch(r'cause:[a-z0-9]+(-[a-z0-9]+)*', c): errs.append(f'causes {c}: 원인 ID는 cause:로 시작하는 영어 소문자 · 하이픈 이름입니다.')
    for name, ids in [('failure_modes', fms), ('causes', causes)]:
        for x in set(ids):
            if ids.count(x) > 1: errs.append(f'{name} {x}가 {ids.count(x)}번 있습니다.')
    found = [s.get('id') for s in sop['sops'] if isinstance(s, dict)]
    for sid in sop_ids:
        if found.count(sid) != 1: errs.append(f'{sid}가 {found.count(sid)}번 있습니다(1번이어야 합니다).')
    for s in sop['sops']:
        if not isinstance(s, dict): errs.append('sops의 항목이 객체가 아닙니다.'); continue
        sid = s.get('id')
        if sid not in sop_ids: errs.append(f'targets.csv에 없는 SOP {sid}')
        if not s.get('source'): errs.append(f'{sid}: 출처(source)가 없습니다.')
        if s.get('failure_mode') not in fms: errs.append(f'{sid}: 고장 유형 {s.get("failure_mode")}을 sop.json failure_modes에서 찾을 수 없습니다.')
        for key in ['apply_conditions', 'prohibitions', 'steps', 'completion']:
            value = items(s, key)
            if value is None: errs.append(f'{sid}: {key}는 목록이어야 합니다.'); continue
            for i, item in enumerate(value, 1):
                if not isinstance(item, dict) or not item.get('text') or not item.get('source'): errs.append(f'{sid}.{key}[{i}]: 내용(text) · 출처(source)가 필요합니다.'); continue
                for rid in item.get('rules') or []:
                    if rule_ids and rid not in rule_ids: errs.append(f'{sid}.{key}[{i}]: 조건표에 없는 규칙 {rid}')
        steps = [x.get('order') for x in items(s, 'steps') or [] if isinstance(x, dict)]
        if not steps or steps != list(range(1, len(steps) + 1)): errs.append(f'{sid}: 수행 단계(steps)의 순서가 1부터 차례가 아닙니다: {steps}')
        approval = s.get('approval')
        if not isinstance(approval, dict) or not approval.get('role') or not approval.get('source'): errs.append(f'{sid}: 승인(approval — role · source)이 필요합니다. 원문에서 승인을 찾지 못했으면 role을 「미확인」으로 시작하고 source에 찾아본 절을 적습니다.')
        elif str(approval['role']).startswith('미확인'): unconfirmed.append(sid)
        ref = s.get('model_refs')
        if not isinstance(ref, dict): errs.append(f'{sid}: 모델 참조(model_refs)는 객체여야 합니다.'); continue
        used = 0
        for slot, want in SLOT.items():
            for x in ref.get(slot) or []:
                used += 1
                if x not in kind_of: errs.append(f'{sid}: 모델에 없는 ID {x} (새 ID를 만들지 말고 not_linked에 까닭을 적습니다)')
                elif kind_of[x] != want: errs.append(f'{sid}: {slot} 자리에 {kind_of[x]} ID {x}가 있습니다.')
        if not used and not ref.get('not_linked'): errs.append(f'{sid}: 모델 참조(model_refs)가 비어 있습니다(걸 대상이 없으면 not_linked에 까닭을 적습니다).')
    ends = {'failure_modes': set(fms), 'sops': set(found), 'causes': set(causes)}
    rels = sop.get('relations')
    if not isinstance(rels, list) or not rels: errs.append('관계 목록(relations)이 비어 있습니다.')
    else:
        for i, r in enumerate(rels, 1):
            t = r.get('type') if isinstance(r, dict) else None
            if t not in RELATIONS: errs.append(f'relations[{i}]: type {t}은 계약의 셋(MITIGATED_BY · REMEDIED_BY · ADDRESSES) 가운데 하나가 아닙니다.'); continue
            a, b = RELATIONS[t]
            if r.get('from') not in ends[a]: errs.append(f'relations[{i}] {t}: 시작 {r.get("from")}이 sop.json {a}에 없습니다.')
            if r.get('to') not in ends[b]: errs.append(f'relations[{i}] {t}: 끝 {r.get("to")}이 sop.json {b}에 없습니다.')
            if not r.get('source'): errs.append(f'relations[{i}]: source가 필요합니다.')
    return ('확인 필요' if errs else '통과'), errs, f'SOP {len(found)}개 · 관계 {len(rels) if isinstance(rels, list) else 0}개' + (f' · 승인 미확인 {", ".join(unconfirmed)}' if unconfirmed else '')
t_state, t_errs, n, rule_ids = check_table(root/'결과/조건표.csv', sop_ids)
s_state, s_errs, s_note = check_sop(root/'결과/sop.json', rule_ids)
missing = [p for p in ('sop.json', '조건표.csv') if not (root/'결과'/p).is_file()]
if len(missing) == 2:
    print('아직 검사할 결과가 없습니다: 결과/sop.json · 결과/조건표.csv')
print('구조 검사 결과')
ok = report([('sop.json', s_state, s_errs, s_note, True), ('조건표.csv', t_state, t_errs, f'규칙 묶음 {n}개' if n else '', True),
             record_part(root/'결과/요구사항.md', '고른 것', '정한 것'), record_part(root/'결과/요구사항.md', '처리', '판단 시스템 결정표 대조'),
             record_part(root/'결과/요구사항.md', '맞은 규칙', '사건 · 확인 사례 대입'), shape_part(root/'결과/요구사항.md')])
print('구조 검사 통과' if ok else '구조 확인 필요 — 위 줄마다 결과 파일의 어느 항목인지 찾아 고친 뒤 다시 실행합니다.')
print('이 검사는 모양만 봅니다. 의미와 질문별 답(조건 · 경계 · 출처가 원문과 맞는지, 사건의 판정)은 원자료와 따로 대조합니다.')
sys.exit(0 if ok else 1)
'''

CONDITIONS_CHECK = r'''"""결과/조건표.csv의 구조 검사와 판단기록.md 기록 칸 확인. 생성 · 수정 · 네트워크 접속을 하지 않는다.
의미(조건 · 경계 · 출처가 원문과 맞는지, 사례의 판정)는 판정하지 않는다 — 원자료와 따로 대조한다.
사용: python check.py
"""
from pathlib import Path
import csv, re, sys
root = Path(__file__).resolve().parent
''' + TABLE_CHECK + r'''
sop_ids = [r['sop_id'] for r in read_csv(root/'자료/targets.csv')[1]]
state, errs, n, _ = check_table(root/'결과/조건표.csv', sop_ids)
if state == '없음':
    print('아직 검사할 결과가 없습니다: 결과/조건표.csv')
print('구조 검사 결과')
ok = report([('조건표.csv', state, errs, f'규칙 묶음 {n}개' if n else '', True),
             record_part(root/'결과/판단기록.md', '고른 것', '정한 것'), record_part(root/'결과/판단기록.md', '맞은 규칙', '사례 대조'),
             record_part(root/'결과/판단기록.md', '승인 역할', '남은 후보와 실행 승인'), shape_part(root/'결과/판단기록.md')])
print('구조 검사 통과' if ok else '구조 확인 필요 — 위 줄마다 결과 파일의 어느 항목인지 찾아 고친 뒤 다시 실행합니다.')
print('이 검사는 모양만 봅니다. 의미와 질문별 답(조건 · 경계 · 출처가 원문과 맞는지, 사례의 판정)은 원자료와 따로 대조합니다.')
sys.exit(0 if ok else 1)
'''


# ───────────── 학생 문장 ─────────────
USB = B.USB
CHECK_STEP_WHY = ('구조 검사는 ID · 관계의 양 끝 · 열 · 연산자와 경계의 짝처럼 모양만 봅니다. '
                  '조건과 출처가 원문과 맞는지, 사건에서 무엇이 나와야 하는지는 검사가 모르므로 내가 원문과 대조한 기록으로 판단합니다.')
TABLE_CHECK_WHY = ('구조 검사는 열 이름 · 조치 ID · 연산자와 경계의 짝 · 한 묶음 안의 결과처럼 모양만 봅니다. '
                   '조건과 출처가 원문과 맞는지, 사례에서 무엇이 나와야 하는지는 검사가 모르므로 내가 원문과 대조한 기록으로 판단합니다.')   # 조건표만 검사하는 랩
DIFFER_CHECK = '「구조 확인 필요」가 나오면 아래 줄마다 문제가 하나씩 적혀 있습니다. 줄마다 결과 파일의 어느 항목 · 행인지 AI에게 짚게 해 고친 뒤 다시 실행합니다.'
WHY_TABLE = ('DMN의 결정표는 입력 · 연산자 · 기준값 · 단위 · 결과를 한 행에 적고, 함께 맞아야 하는 비교 여러 개를 한 규칙으로 묶습니다. '
             '「이상」 「이하」는 기준값을 포함하고 「초과」 「미만」은 포함하지 않으므로, 기준값과 같은 값이 들어오면 결과가 갈립니다.')
HIT_POLICY = ('한 조치에 여러 규칙이 함께 맞을 수 있습니다. 여러 규칙이 맞을 때 무엇을 낼지 정한 것을 Hit Policy라고 하고, 이 판정은 맞은 경고 · 감점 · 제외를 모두 모읍니다.')
WHY_HIT = HIT_POLICY + ' 그래서 규칙마다 걸리는 조치를 따로 적어야 어느 조치에 무엇이 걸렸는지 흐려지지 않습니다.'   # 조건표를 만드는 랩
WHY_HIT_READ = HIT_POLICY + ' 맞은 사유를 하나만 내면 함께 맞은 다른 사유가 결과에서 사라집니다.'               # 조건표를 읽는 판정 랩
WHY_SOURCE = ('판단 시스템의 결정표는 만들 때의 판으로 적혀 있습니다. 판이 바뀌면 같은 내용이 다른 번호 · 다른 낱말로 옮겨 갈 수 있으므로, '
              '어느 행이 지금 원문의 어느 문장과 같은지 찾은 근거를 남겨야 다른 사람이 같은 판단을 다시 할 수 있습니다.')
WHY_UNKNOWN = ('조건이 거짓인 것과, 입력이 없어 참인지 거짓인지 확인할 수 없는 것은 다릅니다. 확인할 수 없는 조건을 거짓으로 치면 쓰면 안 되는 조치가 남을 수 있고, '
               '반대로 이미 확인된 제외 사유가 있으면 다른 입력이 빠져도 그 사유는 그대로입니다.')

# 가이드의 「막히면」 — 새로 받은 랩 폴더에서 check.py · python을 돌려 본 출력 그대로(가이드.md P-167 · P-168). step_guide의 guide_after에 HTML 조각으로 넣는다.
def stuck(text):
    return f'<p>{B.inline("**막히면** " + text)}</p>'
STUCK_PATH = stuck('「can\'t open file」 · 「No such file or directory」가 나오면 터미널이 이 실습 폴더가 아닌 곳에서 열렸거나 명령의 파일 이름이 실제 파일과 다른 것입니다. '
                   '터미널 맨 앞 경로가 이 실습 폴더인지, 명령의 파일 이름이 탐색기에 보이는 이름과 같은지 확인한 뒤 다시 실행합니다.')
STUCK_FIRST_SOP = stuck('이 단계에서는 SOP 하나만 만들었으므로 구조 검사가 「구조 확인 필요」로 끝납니다. 아직 만들지 않은 것을 짚는 줄 — 다른 SOP의 「0번 있습니다」, '
                        '그 SOP의 모델 참조(model_refs)를 짚는 줄, 「관계 목록(relations)이 비어 있습니다」, 조건표의 「빈 틀」, 기록 칸의 「아직 비어 있음」 — 이 나올 수 있고, 뒤 단계에서 채울 자리라 지금 고칠 문제가 아닙니다. '
                        '그 밖에 방금 만든 SOP의 칸 · 출처 · 단계 순서 · 승인을 짚는 줄이 있으면 그 줄을 고칩니다.')
STUCK_FIRST_TABLE = stuck('「판단기록.md … 아직 비어 있음」 줄은 뒤 단계에서 채울 기록 칸을 짚는 것입니다. 조건표 줄이 「통과」로 나오면 이 단계에서 고칠 것은 없습니다.')
def stuck_no_result(name):
    return stuck(f'「아직 검사할 결과가 없습니다: 결과/{name}」이 나오면 오류가 아니라 만든 코드가 결과를 그 이름 · 그 자리에 쓰지 않았다는 뜻입니다. '
                 '탐색기에서 `결과/`의 파일 이름을 보고, 만든 코드가 결과를 어디에 쓰는지 AI에게 짚게 한 뒤 코드를 다시 실행하고 검사합니다. '
                 '「기대 칸을 쓴 시각」이 비어 있다는 참고 줄은 `기대결과.md`에 실행 전에 기대를 적은 시각을 남기라는 뜻입니다.')


# 리허설: 「제 생각은 …」처럼 의견으로 말한 선택을 AI가 결정으로 받지 않아 한 턴이 더 들었다(작업 규칙 8번대로 다시 물음).
DECIDE_FIRM = ' 고른 것은 의견처럼 말하지 않고, 무엇으로 정했는지와 그 근거 줄을 단정해서 말합니다 — 의견으로 말하면 AI가 결정으로 받지 않고 다시 묻습니다.'
DECIDE_FIRM_AGAIN = ' 내 결정은 3단계처럼 단정해서 전합니다.'
# 리허설: AI가 만든 코드가 학생이 손으로 쓰는 기대결과.md의 「정한 것」 표를 읽어, 표 모양이 바뀌면 실행이 멈출 수 있었다.
DECIDE_INPUT = '「정한 것」의 결정(요청 문장으로 전한다 — 코드가 내가 쓰는 `결과/기대결과.md`를 읽지 않게)'

RESULT_KINDS = '**경고**는 그 조치에 주의할 점이 있다는 사유, **감점**은 비교할 때 금액으로 깎는 사유, **제외**는 그 조치를 쓸 수 없는 사유입니다.'
CONTRACT_TERM = '**계약**은 결과 파일의 모양(열 · 키와 그 뜻)을 정해 둔 `입출력_계약.md`입니다 — 다음 실습의 기능이 이 모양 그대로 읽습니다.'
JUDGE_TERMS = (RESULT_KINDS + ' 판정은 그 사유를 모아 **유지** · **제외** · **보류**로 나뉩니다 — 보류는 제외 사유는 없지만 입력이 없어 맞는지 알 수 없는 규칙이 있는 후보이고, '
               '세 말의 뜻은 `자료/작업기준.md` 4절에 있습니다. **판단 입력**은 규칙이 견주는 값(예측 유온 · 운전 모드 · 팬 연속 시간 등)이고 **원천**은 그 값이 기록된 곳, '
               '**비교 합계**는 주어진 산식의 네 손실과 감점을 더한 값입니다.')
SYSTEM_TERM = '**판단 시스템**은 경보가 나면 조치 후보를 판정해 보여 주는 회사 시스템이고, 그 결정표를 내보낸 파일이 `자료/판단시스템_결정표_내보내기.txt`입니다.'


def incident_time(files):
    """사건 메모의 경보 시각(HH:MM)."""
    for line in files['사건_기록_HYD-02_1027.md'].splitlines():
        if line.startswith('- 경보 ID'):
            return line.split(': ', 1)[1][:5]
    raise RuntimeError('사건 메모에서 경보 시각을 찾지 못했습니다.')


def criteria_lab(files):
    """통합반 03회차 실습2 — 작업 절차와 판단 조건을 연결해 조치 기준 만들기(구성안 5.1)."""
    title = TITLES['integrated-03-criteria']
    rec = '결과/요구사항.md'
    when = incident_time(files)
    save = ('`결과/sop.json` · `결과/조건표.csv` · `결과/요구사항.md`와 만든 코드를 함께 보관합니다. '
            f'다음 실습 「{TITLES["integrated-03-judge"]}」에서는 이 조건표를 읽어 조치를 판정하고 견주는 기능을 만듭니다. 그 실습도 제공된 조건표로 시작할 수 있으므로 이 결과는 골라서 가져갑니다. ' + USB)
    steps = [
        S('폴더와 출발점 확인', '시작',
          'VS Code 탐색기에서 이 폴더의 `입력/` · `자료/` · `결과/` · START.md를 열어 각 자리의 역할과 이번 질문을 확인합니다.',
          '이번 질문 세 개와, 이 답을 쓰는 두 사람이 누구인지 확인합니다.',
          '탐색기에서 네 자리를 찾았고, `입력/graph.json`에 조치 절차와 판단 규칙이 아직 없다는 것을 파일에서 확인했습니다.',
          why=B.WHY_START,
          differ=B.DIFFER_START),
        S('파일을 바꾸지 않고 자료 파악', '① 파악',
          'AI에게 파일을 바꾸지 말고, 냉각 계통 조치마다 그 조치를 말하는 줄을 자료마다 찾아 파일 · 줄로 짚어 달라고 합니다. 짚은 줄을 직접 엽니다.',
          '같은 조치나 조건을 자료마다 다르게 적은 곳, 번호 · 표기가 다른 곳처럼 자료끼리 말이 달라 보이는 곳이 있는지 묻습니다.',
          B.EVIDENCE_LOOK + ' 질문 1 ~ 3에 쓸 자료가 무엇인지 내 말로 말할 수 있습니다.',
          H('조치마다 근거 줄을 자료마다 모은다. 아직 아무것도 만들지 않는다.',
            '`입력/` · `자료/` 전체, START.md 「해결할 질문」',
            '파일을 바꾸지 않는다. 해석보다 파일 · 줄 번호를 먼저 받는다.',
            '「파일 · 줄 · 그 줄이 말하는 것」 목록과, 자료끼리 말이 달라 보이는 곳 목록',
            '짚은 줄 가운데 몇 개를 내가 직접 열어 같은 내용인지 본다'),
          why=('조치 기준에는 원문에 있는 것만 담아야 하므로, 만들기 전에 자료가 무엇을 말하는지부터 봅니다. '
               '현행 원문 · 옛 판 · 시스템 내보내기 · 작업 기록은 만든 때와 만든 사람이 달라 같은 일도 다르게 적혀 있을 수 있습니다. 자료마다 어느 판 · 어느 시점인지 먼저 알아 두어야 무엇을 근거로 삼을지 정할 수 있습니다. '
               '이 단계에서 파일을 바꾸지 않는 것은 무엇을 담을지 합의하기 전에 AI가 결과를 만들기 시작하지 않게 하려는 것입니다.'),
          differ=B.DIFFER_LOOK),
        S('요구와 기대 답 정하기', '② 요구',
          '목표 · 이 답을 쓰는 사람 · 쓸 판본 · 지킬 조건과 질문마다 기대 답 — 질문 1은 SOP 하나를 골라 그 다섯 칸(적용 조건 · 금지 조건 · 수행 단계 · 완료 기준 · 승인), '
          '질문 2는 판단 조건 하나의 입력 · 단위 · 연산자 · 경계 · 결과 · 출처와 판단 시스템 결정표에서 같은 조건이 어떻게 적혀 있는지, 질문 3은 사건 네 후보의 기대 판단 — 을 '
          '원문에서 직접 찾아 `결과/요구사항.md`에 편집기에서 내 말로 적습니다. 「학생이 정할 것」의 지점마다 고른 것과 근거 줄을 적습니다.' + B.REQ_AFTER,
          B.ASK_DECIDE + DECIDE_FIRM,
          B.REQ_EVIDENCE,
          B.req_hint(rec, 2, '목표와 질문 · 이 답을 쓰는 사람 · 자료와 기준일 · 지킬 조건 · 「정한 것」 · 질문 1 ~ 3마다 「기대 답과 실제 결과」'),
          why=B.WHY_REQ + ' SOP 하나는 적용 조건(이 조치를 써도 되는 때) · 금지 조건(쓰면 안 되는 때와 지킬 제한) · 수행 단계 · 완료 기준(끝났다고 볼 때) · 승인(누가 허락하는가)으로 나눕니다.',
          differ=B.DIFFER_REQ.format(rec=rec)),
        S('계획 검토', '③ 계획',
          'SOP 구조와 조건표에 무엇을 나눠 담을지와 5 ~ 13단계의 구현 순서를 AI의 계획으로 받아 검토하고 동의합니다. 아직 파일을 만들지 않습니다.',
          '같은 원문 문장이 SOP의 단계와 조건표의 행 둘 다에 걸리는 곳을 어떻게 이을지 정합니다.' + DECIDE_FIRM_AGAIN,
          '질문 1 ~ 3마다 계획의 어느 칸 · 행으로 답하는지 짚을 수 있습니다. 계획에 「이번 범위 밖」의 기능 — 원문에서 조건을 자동으로 뽑아내는 프로그램(인제스천, 뒤에서 직접 다룹니다)이나 조건표를 읽어 판정하는 프로그램 — 이 없습니다. 계획에 내가 동의했습니다.',
          H('만들기 전에 두 결과의 몫과 순서를 합의한다',
            '`입출력_계약.md`, `결과/요구사항.md`',
            '「정한 것」 표를 반영한다. 「이번 범위 밖」은 넣지 않는다.',
            'SOP 구조의 칸 · 관계 · 조건표 행의 목록과 구현 순서',
            '질문 1 ~ 3을 하나씩 계획에 대어 어느 칸 · 행으로 답하는지 짚게 한다'),
          why=('절차(SOP)는 사람이 차례대로 하는 일이고, 판단(DMN)은 입력 값이 정해지면 결과가 하나로 나오는 규칙입니다. '
               '「~일 때만 한다」 같은 문장은 절차의 확인 단계이면서 판단 조건이 되기도 하므로, 어느 쪽에 무엇을 두고 둘을 어떻게 이을지 먼저 정해야 같은 조건이 두 곳에 다르게 적히지 않습니다.'),
          differ=B.DIFFER_PLAN),
        S('구현 ① SOP 하나 구조화', '④ ~ ⑥ 구현 · 대조 · 고침',
          '3단계에서 기대 답을 적은 SOP 하나를 AI와 함께 `결과/sop.json`에 계약 모양으로 만들고 구조 검사를 실행합니다.' + B.OWN_RUN,
          '「~일 때만」 「~하지 않는다」 문장을 적용 조건과 금지 조건 가운데 어디에 둘지와 그 근거를 묻습니다.',
          '만든 SOP의 칸마다 3단계 기대 답과 같습니다. 구조 검사에서 그 SOP의 칸 · 출처 · 단계 순서 · 승인을 짚는 줄이 없습니다(모델 참조는 8단계에서 채웁니다).',
          H('고른 SOP 하나를 계약 모양으로 옮긴다',
            '매뉴얼의 그 절, `입출력_계약.md` 「SOP 구조」',
            '원문에 없는 단계 · 값을 만들지 않는다. 항목마다 출처를 단다. 모델 참조(`model_refs`)는 8단계에서 채우므로 비워 두고 임시 글을 넣지 않는다.',
            '`결과/sop.json`의 SOP 하나',
            '3단계 기대 답과 칸마다 견주고 구조 검사를 실행한다'),
          'python check.py',
          why=('같은 사실이라도 적용 조건과 금지 조건 가운데 어느 칸에 두느냐에 따라 판단이 「쓸 수 있다」와 「쓸 수 없다」로 갈리므로, '
               '칸마다 원문 문장을 출처로 붙여 다시 확인할 수 있게 합니다.'),
          differ=B.FIX_LOOP),
        S('구현 ② 나머지 SOP 구조화', '④ ~ ⑥ 구현 · 대조 · 고침',
          '같은 모양으로 남은 SOP를 모두 `결과/sop.json`에 더하고, SOP마다 단계 수 · 승인 · 참조한 절을 원문과 나란히 보여 달라고 합니다.',
          '다른 절이나 다른 SOP를 가리키는 단계를 무엇으로 이을지, SOP마다 승인 줄이 원문 어디에 있고 승인 줄을 찾지 못한 SOP는 무엇으로 적을지 묻습니다.',
          '`targets.csv`의 SOP가 한 번씩 있고(구조 검사에 「0번 있습니다」 줄이 없음), SOP마다 단계 순서와 승인이 원문과 같습니다.',
          H('남은 SOP를 같은 모양으로 옮긴다',
            '매뉴얼, `자료/targets.csv`, 5단계 결과',
            'SOP마다 한 번, 단계 순서는 원문대로. 5단계에서 만든 SOP를 바꾸지 않는다.',
            '`결과/sop.json` 전체',
            'SOP마다 단계 수 · 승인 · 참조한 절을 원문 줄과 나란히 출력하게 한다'),
          'python check.py',
          why='한 SOP의 단계가 다른 절의 판정이나 다른 SOP를 가리키면, 그 연결을 남겨야 한쪽이 바뀔 때 함께 고칠 곳을 찾을 수 있습니다.',
          differ=B.FIX_LOOP),
        S('구현 ③ 고장 유형 · 원인 · 조치 잇기', '④ ~ ⑥ 구현 · 대조 · 고침',
          '고장 유형에서 즉시 완화 조치 · 근본 조치로, 조치에서 그 조치가 맞는 원인으로 가는 관계를 `결과/sop.json`의 관계 목록(`relations`)에 만듭니다.',
          '조치가 특정 원인에만 맞는지와 그 근거 줄, 점검 · 확인만 하는 절차를 근본 조치로 이을 수 있는지를 묻습니다.',
          '구조 검사에 관계 목록(`relations`)을 짚는 줄이 없고(관계의 양 끝이 모두 `sop.json`에 있는 ID), 원인마다 이어진 조치를 원문 줄과 나란히 보일 수 있습니다.',
          H('고장 유형 · 원인 · 조치를 관계로 잇는다',
            '매뉴얼의 원인 절, `자료/failuremodes.csv`, `결과/sop.json`',
            '관계 이름은 계약의 셋만 쓴다. 원문에 없는 연결을 만들지 않는다.',
            '관계 목록(`relations`)과 원인 목록(`causes`)',
            '원인마다 이어진 조치를 원문 줄과 나란히 출력하게 한다'),
          'python check.py',
          why=('즉시 완화는 지금 증상을 누그러뜨리는 조치이고, 근본 조치는 원인을 없애는 조치입니다. 같은 고장 유형이라도 원인에 따라 맞는 근본 조치가 다르므로, '
               '조치와 원인 사이의 관계가 있어야 판단이 원인에 맞지 않는 근본 조치를 고르지 않습니다.'),
          differ=B.FIX_LOOP),
        S('구현 ④ 설비 모델 ID 잇기', '④ ~ ⑥ 구현 · 대조 · 고침',
          '`입력/graph.json`에서 SOP가 걸리는 설비 · 구성 요소 · 센서의 ID를 찾아 모델 참조(`model_refs`)를 채우는 코드를 `결과/`에 만들고 실행합니다. 설비마다 걸었음 · 뺐음과 그 까닭을 `요구사항.md`에 적습니다.',
          '이 단계의 결과는 내 결정에 따라 달라집니다. SOP마다 어느 구성 요소 · 센서를 걸지 그 기준(무엇을 보고 고르는지)을 정해 요청에 담고, 「정한 것」의 적용 범위 결정대로 됐는지, 모델에서 이 조치를 할 수 없는 설비를 무엇으로 알아냈는지 묻습니다. AI가 결정을 대신 정하려 하면 돌려보내고 내 선택과 근거를 다시 말합니다.',
          '구조 검사에 모델 참조(`model_refs`)를 짚는 줄(모델에 없는 ID · 다른 종류의 ID · 비어 있음)이 없습니다. 설비마다 걸었음 · 뺐음과 그 까닭을 모델 · 대장 줄로 말할 수 있습니다.',
          H('SOP가 걸리는 설비 · 구성 요소 · 센서 ID를 모델에서 찾는다',
            '`입력/graph.json` · `입력/schema.json` · `입력/자료/설비_대장.csv`, 「정한 것」 표',
            '모델에 없는 ID를 만들지 않는다. 걸 대상을 찾지 못하면 걸지 않은 대상(`not_linked`)과 그 까닭을 남긴다. 구성 요소 · 센서는 요청에 적은 내 기준대로 고른다.',
            'SOP마다 ID 목록, 설비마다 걸었음 · 뺐음 · 까닭',
            'SOP마다 그 SOP 문장에 나온 장치 · 태그와 걸린 ID를 나란히 출력하게 하고, 설비 몇 대는 모델 파일에서 관계를 직접 따라가 본다'),
          'python 결과/<만든 코드 이름>.py\npython check.py',
          why=('2회차에 만든 설비 모델의 ID를 그대로 써야 조치 기준이 모델과 이어집니다. 새 ID를 지으면 같은 설비가 두 이름으로 갈라져 판단이 설비를 찾지 못합니다. '
               '조치에 필요한 장치 · 센서가 그 설비에 실제로 있는지는 모델의 관계를 따라가 확인합니다.'),
          differ='걸었음 · 뺐음의 까닭을 모델 줄로 말할 수 없는 설비가 있으면 그 설비의 관계를 AI와 하나씩 따라가 확인하고, 고친 뒤 같은 출력을 다시 봅니다.'),
        S('구현 ⑤ 조건표 규칙 한 묶음', '④ ~ ⑥ 구현 · 대조 · 고침',
          '여러 조건이 함께 맞아야 하는 조건 하나를 골라 `결과/조건표.csv`에 계약 모양으로 옮기고 구조 검사를 실행합니다.',
          '여러 조건을 한 묶음(AND)으로 둘지 나눌지와, 기준값을 포함하는지를 원문 낱말로 정합니다.',
          '구조 검사의 조건표 줄이 「통과」이고, 원문 줄과 행을 나란히 놓았을 때 입력 · 연산자 · 기준값 · 경계 · 결과가 같습니다.',
          H('규칙 하나를 계약 모양으로 옮긴다',
            '그 원문 줄, `결과/sop.json`, `입출력_계약.md` 「조건표」',
            '경계는 원문 낱말대로 옮긴다',
            '`결과/조건표.csv`의 한 묶음',
            '구조 검사를 실행하고, 원문 줄과 행을 나란히 보여 달라고 한다'),
          'python check.py',
          why=WHY_TABLE, differ=B.FIX_LOOP),
        S('구현 ⑥ 나머지 규칙과 경계', '④ ~ ⑥ 구현 · 대조 · 고침',
          '원문의 경고 · 감점 · 제외 조건을 모두 `결과/조건표.csv`에 옮기고, `sop.json`의 조건에 그 규칙 ID를 적습니다.',
          '「이상 · 초과 · 미만」이 원문끼리 다른 곳을 무엇으로 정할지, 규칙을 어느 조치에 걸지 묻습니다.',
          '구조 검사의 sop.json · 조건표.csv 줄이 「통과」이고, 조건과 규칙 ID가 `sop.json`과 `조건표.csv` 양쪽에서 맞습니다. 규칙마다 원문 출처가 있습니다.',
          H('경고 · 감점 · 제외 조건을 모두 옮긴다',
            '매뉴얼, `자료/작업기준.md`, 「정한 것」 표, 9단계 결과',
            '한 규칙씩 옮긴다. 출처를 적는 방식을 섞지 않는다.',
            '`결과/조건표.csv` 전체와 `sop.json`의 `규칙` 칸',
            '규칙마다 구조 검사를 돌리고, 조건과 규칙 ID가 양쪽에서 맞는지 세게 한다'),
          'python check.py',
          why=WHY_HIT, differ=B.FIX_LOOP),
        S('구현 ⑦ 판단 시스템 결정표 대조', '⑤ 대조',
          '`자료/판단시스템_결정표_내보내기.txt`의 규칙 행마다 이번 조건표에 옮김 · 고침 · 뺌과 그 까닭을 `요구사항.md`의 대조 표에 적고, 행이 모두 표에 있는지 코드로 세게 합니다.',
          '행마다 처리의 근거가 원문 어디에 있는지 묻습니다. 「정한 것」의 결정이 걸린 행은 그 결정대로인지 봅니다.',
          '내보내기의 규칙 행이 모두 대조 표에 있고, 처리마다 근거 줄이 있습니다.',
          H('판단 시스템 결정표의 행마다 이번 조건표와의 관계를 정리한다',
            '`자료/판단시스템_결정표_내보내기.txt` · `자료/HM-8_1.0판_매뉴얼.md` · `자료/작업지시_이력.csv`, `결과/조건표.csv`',
            '이름만 보고 스킬과 SOP를 잇지 않는다. 원문에서 찾지 못한 근거는 찾지 못했다고 적는다.',
            '「행 · 처리 · 까닭 · 근거」 표(`요구사항.md`)',
            '내보내기의 행이 모두 표에 있는지 코드로 세게 하고, 몇 행은 원문을 직접 연다'),
          'python 결과/<만든 코드 이름>.py',
          why=WHY_SOURCE, differ=B.FIX_LOOP),
        S('사건과 확인 사례에 손으로 대어 보기', '⑤ 대조',
          '`자료/사건_기록_HYD-02_1027.md`의 값과, `자료/확인_사례.csv`에서 「정한 것」의 결정에 따라 결과가 달라지는 사례를 골라 그 값을 조건표에 손으로 대어, 후보마다 맞은 규칙 · 결과 · 확인할 수 없는 조건을 `요구사항.md`에 적고 3단계 기대와 견줍니다.',
          '사건 기록의 값 가운데 조건표 입력으로 그대로 쓸 수 없는 값과 그 까닭, 빠진 입력이 어느 후보의 어느 규칙에 걸리는지, 내 결정이 바꾸는 사례가 어느 것인지 정합니다.',
          '사건 네 후보의 결과가 3단계 기대와 같거나 다른 까닭이 `요구사항.md`에 있고, 내 결정이 바꾸는 확인 사례에서 그 결정으로 달라지는 후보를 원자료 줄로 말할 수 있습니다.',
          H('조건표가 사건과 결정이 걸린 사례에 무엇을 내는지 본다',
            '사건 기록, `자료/확인_사례.csv`, `결과/조건표.csv`, 「정한 것」 표',
            '코드 없이 손으로 한다. 빈 값을 채우지 않는다.',
            '사례 · 후보마다 맞은 규칙 · 결과 · 확인할 수 없는 조건',
            '사건은 3단계에 적은 기대와 후보마다 견주고, 결정이 걸린 사례는 다른 선택이었다면 무엇이 달라졌을지 함께 적는다'),
          why=WHY_UNKNOWN + ' 조건표를 읽어 판정하는 프로그램은 다음 실습에서 만들므로, 여기서는 손으로 대어 조건표가 사건과, 내 결정이 바꾸는 사례에서 무엇을 내는지 확인합니다. '
              '손으로 하는 까닭은 행 하나하나가 원문 줄과 맞는지를 사람이 직접 따라가 보려는 것입니다.',
          differ='기대와 다른 후보가 있으면 그 후보의 입력 값 · 맞은 규칙 · 원문 줄을 나란히 놓고 기대와 조건표 가운데 어느 쪽이 원문과 다른지 찾아 고칩니다.'),
        S('구현 ⑧ 출처 대조', '⑤ ⑥ 대조 · 고침',
          '`sop.json` · `조건표.csv`의 출처마다 원문에서 그 문장을 찾아 나란히 보여 주는 코드를 `결과/`에 만들고 실행합니다.',
          '짝이 맞지 않는 항목이 내가 옮기다 틀린 것인지, 원문끼리 다른 것인지 묻습니다.',
          '항목 · 출처 · 원문 문장 표가 나오고, 짝이 맞지 않는 항목 목록이 나옵니다.',
          H('모든 항목이 원문으로 돌아가는지 본다',
            '`결과/sop.json` · `결과/조건표.csv`, 매뉴얼들',
            '원자료를 바꾸지 않는다',
            '항목 · 출처 · 원문 문장 표와 짝이 맞지 않는 항목 목록',
            '몇 항목은 매뉴얼을 직접 열어 같은 문장인지 본다'),
          'python 결과/<만든 코드 이름>.py',
          why='출처는 다른 사람이 같은 문장을 다시 찾아 확인할 수 있게 하는 근거입니다. 항목이 많으면 눈으로는 다 볼 수 없으므로 코드로 짝을 맞춰 보고, 맞지 않는 항목만 사람이 봅니다.',
          differ=B.FIX_LOOP),
        S('구조 검사와 고치기', '⑤ ⑥ 대조 · 고침',
          '터미널에서 구조 검사를 실행하고, 검사와 13단계가 짚은 문제를 고친 뒤 12 · 13단계 확인을 다시 합니다.',
          '검사와 13단계가 짚은 문제가 결과 파일의 어느 항목인지 묻습니다.',
          '「구조 검사 통과」 줄이 나오고, 13단계에서 짝이 맞지 않는 항목이 없거나 남은 까닭이 `요구사항.md`에 있습니다.',
          H('구조 · 출처 문제를 고친다', '`python check.py`의 출력, 13단계 출력', '검사 기준과 원자료를 바꾸지 않는다', '고친 파일 목록과 다시 실행한 출력', '고친 뒤 12 · 13단계를 다시 한다'),
          'python check.py',
          why=CHECK_STEP_WHY, differ=DIFFER_CHECK),
        S('저장하고 다시 열기', '⑦ 저장 · 다시 열기',
          '결과 파일을 모두 저장하고 VS Code에서 폴더를 닫았다 다시 연 뒤 구조 검사와 13단계 코드를 다시 실행합니다. `요구사항.md` 끝에 기준일 · 저장 시점 · 확인하지 못한 점을 적습니다.',
          '확인하지 못한 점으로 무엇을 남길지 정합니다.',
          '다시 연 뒤에도 출력이 같습니다. `결과/`에 `sop.json` · `조건표.csv` · `요구사항.md`와 만든 코드가 있습니다.',
          cmd='python check.py', why=B.WHY_SAVE, differ=B.DIFFER_SAVE),
    ]
    extra = ('## 설비마다 걸었음 · 뺐음\n\n| 설비 | 걸었음 · 뺐음 | 까닭(모델 · 대장 줄) |\n|---|---|---|\n| | | |\n\n'
             '## 판단 시스템 결정표 대조\n\n| 내보내기 행 | 처리 | 까닭 | 근거(파일 · 줄) |\n|---|---|---|---|\n| | | | |\n\n'
             '## 사건 · 확인 사례 대입\n\n| 사례 / 후보 | 맞은 규칙 | 결과(경고 · 감점 · 제외) | 확인할 수 없는 조건과 까닭 | 기대와 같은가 · 다른 선택이었다면 |\n|---|---|---|---|---|\n| | | | | |\n\n')
    formats = ['## 결과 형식\n\n파일의 모양은 `입출력_계약.md`에 있습니다. 무엇을 어느 칸 · 행에 둘지는 원문을 읽고 직접 정합니다.\n\n'
               '- `결과/sop.json` — SOP 구조, 고장 유형 · 원인 · 조치 관계, 설비 모델 ID(계약 「SOP 구조」).\n'
               '- `결과/조건표.csv` — 판단 조건(계약 「조건표」). 「제공 빈 틀」에 열 이름이 있습니다.\n'
               '- `결과/요구사항.md` — 「제공 빈 틀」의 칸대로 채웁니다.\n'
               '- 만든 코드는 `결과/` 아래에 두고, 이름은 하는 일로 짓습니다.\n\n'
               '## 지킬 조건\n\n'
               '- 모델에 없는 대상에는 새 ID를 만들지 않습니다.\n'
               '- 조치 기준의 항목마다 원문 출처를 답니다.\n']
    return dict(
        title=title, rec=rec, readonly='`입력/` · `자료/`가', decide_step=2, course='통합반',
        goal=[f'포털의 조치 방법 화면에서 쿨러 조치의 단계 · 담당 · 승인을, 판단 규칙 화면에서 어떤 규칙이 조치를 허용 · 제외하는지 봤습니다. '
              f'이번에는 그 근거를 매뉴얼 원문에서 직접 찾아 작업 절차(SOP 구조)와 판단 조건(조건표)으로 나누고, 2회차에 만든 설비 모델의 ID에 잇습니다. '
              f'사건은 포털에서 본 경보와 같은 종류의 다른 경보 한 건, 10월 27일 {when} HYD-02 쿨러 성능 저하 경보입니다.',
              'SOP는 사람이 따라 하는 절차(적용 조건 · 금지 조건 · 수행 단계 · 완료 기준 · 승인)를 담고, 조건표는 어떤 입력이 어떤 값일 때 조치를 경고 · 감점 · 제외하는지를 담습니다. '
              '조건표는 DMN(판단을 표준 모양으로 적는 방식)의 결정표 — 입력 조건과 판단 결과를 한 행씩 적은 표 — 를 이 실습에서 부르는 이름입니다. '
              '두 결과가 같은 ID로 설비 모델에 이어져 있어야 판단 시스템이 설비와 사건을 보고 할 수 있는 조치와 그 근거를 같은 답으로 냅니다.',
              '자료는 현행 매뉴얼 · 옛 판 매뉴얼 · 판단 시스템에 등록된 결정표 · 1년치 작업 이력으로 나뉘어 있고 서로 적은 때와 사람이 다릅니다. '
              '손으로 다 맞춰 볼 수 없으므로 AI와 코드로 대조하고, 결과는 원문과 견줍니다.',
              B.STAGE_LINE.format(what='판단 지식 — 절차와 판단 조건을 원문에서 구조화해 설비 모델에 잇는 일 — ')],
        make='만들 것: `결과/sop.json`(SOP 구조 · 관계 · 설비 모델 ID), `결과/조건표.csv`, `결과/요구사항.md`, 결과를 만들고 확인하는 코드.',
        start=['`입력/schema.json` · `입력/graph.json` — 설비 7대의 설비 · 구성 요소 · 센서 · 부품 모델. 2회차에 만든 설비 모델과 같은 꼴로 제공된 판입니다. `입력/자료/설비_대장.csv` — 그 모델의 설비 대장(기준일 ' + D2.REF_DATE + ').',
               MINE['integrated-03-criteria'],
               '`자료/HM-8_매뉴얼.md` — 현행 HM-8 1.1판(2026-09-01 시행) 냉각 계통 조치 원문. `자료/HM-8_1.0판_매뉴얼.md` — 1.1판으로 대체된 옛 판(2025-03-10 시행). `자료/HI-01_보충매뉴얼.md` — 점검 · 이상 확인 보충 기준.',
               '`자료/판단시스템_결정표_내보내기.txt` — 판단 시스템에 등록된 결정표 · 스킬을 내보낸 것(2025년 도입 판, 2026-10-27 내보냄). `자료/작업지시_이력.csv` — CMMS 작업지시 1년치 내보내기(2026-10-28).',
               '`자료/작업기준.md` — 회사 작업 기준. `자료/targets.csv` — 냉각 계통 SOP 목록. `자료/failuremodes.csv` — 회사 고장 유형 목록. `자료/사건_기록_HYD-02_1027.md` — 야간 운전원이 HMI에서 옮겨 적은 사건 메모. '
               '`자료/확인_사례.csv` — 지난 30일 경보 가운데 고른 확인 사례의 판단 입력(입력마다 원천과 그 시각).',
               '`입출력_계약.md` — 결과 파일의 형식. `check.py` — 결과의 구조 검사.',
               '`결과/` — 이번에 만든 것을 두는 자리. 「제공 빈 틀」 `요구사항.md`와 열 이름만 있는 `조건표.csv`가 있습니다.',
               RULES_LINE],
        user='이 답은 설비보전팀장이 판단 시스템에 조치 기준을 올릴 때, 야간 운전원이 사건에서 할 수 있는 조치를 볼 때 씁니다.',
        questions=['냉각 계통 조치 일곱 개마다 적용 조건 · 금지 조건 · 수행 단계 · 완료 기준 · 승인은 무엇이고, 어느 고장 유형 · 원인과 어느 설비 · 구성 요소 · 센서에 걸리는가?',
                   '판단 규칙으로 옮길 조건의 입력 · 단위 · 연산자 · 경계 · 결과 · 출처는 무엇인가? 판단 시스템에 등록된 결정표 · 옛 판 매뉴얼 · 작업 이력과 무엇이 같고 무엇이 다른가?',
                   '사건 한 건의 판단 요청 때 값을 조건표에 대면 네 후보가 각각 어떻게 되는가?'],
        decide=[('적용 범위', '원문에 적용 범위 문장이 없을 때 이 조치 기준을 설비 모델의 어느 설비에 걸지'),
                ('출처가 확인되지 않는 기준', '판단 시스템 결정표에 있는데 지금 매뉴얼에서 근거 문장을 찾을 수 없는 규칙을 어떻게 둘지 — 그런 규칙이 여럿이면 규칙마다 정하고 근거를 적습니다')],
        outside=['원문에서 조건을 자동으로 뽑아내는 일(인제스천 — 뒤에서 직접 다룹니다)',
                 '조건표를 읽어 후보를 판정하고 견주는 프로그램(다음 실습)',
                 '설비 모델(schema · graph)을 고치거나 그래프 DB에 적재하는 일',
                 '실제 설비 · 포털 · 업무 시스템을 부르는 일'],
        formats=formats, steps=steps,
        cases=['같은 조치를 판마다 다른 번호 · 절 · 낱말로 적은 곳(현행 원문 · 옛 판 · 판단 시스템 · 작업 이력)',
               '경계 낱말(「이상 · 초과 · 미만」)이 원문끼리 다른 조건',
               '여러 조건이 함께 맞아야 하는 조건과 다른 절 · 다른 SOP를 가리키는 단계',
               '조치에 필요한 구성 요소 · 센서가 모델에 없는 설비',
               '판단 시스템 결정표에서 냉각 계통 밖을 다루는 행',
               '사건 기록에서 값이 비어 있는 후보',
               '「정할 것」의 결정에 따라 결과가 바뀌는 확인 사례',
               '같은 코드를 다시 실행한 결과'],
        commands='python check.py\npython 결과/<만든 코드 이름>.py',
        done=('형식 검사나 실행 성공만으로 완료하지 않습니다. 질문마다 원문에서 먼저 적은 기대 답과 실제 결과가 맞고, 「정한 것」마다 근거 줄과 그 선택으로 바뀌는 답을 설명할 수 있으며, '
              '`sop.json` · `조건표.csv`의 항목마다 원문 문장으로 돌아갈 수 있으면 완료입니다. 고친 점과 확인하지 못한 점은 `결과/요구사항.md`에 짧게 남깁니다.'),
        save=save, reopen='구조 검사와 13단계 출처 대조의 출력, `요구사항.md`의 기준일 · 저장 시점 · 확인하지 못한 점',
        tree=tree('03일차_실습2_조치기준만들기', [('.github/', 'Copilot 작업 규칙'), ('결과/', '이번에 만들 것(요구사항.md · 조건표.csv 빈 틀)'),
                                            ('입력/', '설비 모델과 설비 대장(읽기만)'), ('자료/', '매뉴얼 · 판단 시스템 결정표 · 작업 이력 · 사건 메모 · 확인 사례(읽기만)'),
                                            ('AGENTS.md', 'Codex 작업 규칙'), ('check.py', '구조 검사'), ('CLAUDE.md', '작업 규칙(같은 내용)'), ('guide.html', '이 가이드'),
                                            ('START.md', '이번 과제와 진행 단계'), ('안내.html', '이 가이드와 같은 파일'), ('입출력_계약.md', '결과 파일의 형식')]),
        lead='매뉴얼 원문에서 냉각 계통 조치의 절차를 SOP 구조로, 판단 조건을 조건표로 만들고 2회차에 만든 설비 모델의 ID에 이은 뒤, 사건 · 확인 사례와 원문 출처로 대조합니다.',
        need='VS Code와 Python, 로그인해 둔 Codex 또는 GitHub Copilot.',
        terms=('**SOP**는 표준 작업 절차(Standard Operating Procedure)입니다. 조건표의 결과는 셋입니다 — ' + RESULT_KINDS + ' ' + SYSTEM_TERM + ' ' + CONTRACT_TERM),
        first_more=[MINE['integrated-03-criteria']],
        guide_extra={1: ['ai', 'review'], 4: ['terminal']}, guide_after={4: [STUCK_PATH, STUCK_FIRST_SOP]}, files={
            'check.py': CRITERIA_CHECK,
            '입출력_계약.md': ('# 입출력 계약\n\n결과 파일의 형식과 뜻만 정한다. 무엇을 담을지는 원문에서 정한다.\n\n' + SOP_CONTRACT + '\n' + TABLE_CONTRACT + '\n' + CASES_CONTRACT).replace('{codes_from}', CODES_FROM_EXPORT),
            '결과/요구사항.md': req_template('요구사항', extra),
            '결과/조건표.csv': TABLE_HEADER,
            '결과/README.md': '이번 과제의 SOP 구조(sop.json) · 조건표(조건표.csv) · 요구사항.md와 만든 코드를 여기에 저장합니다.\n다시 열 때는 요구사항.md의 기준일 · 저장 시점과 구조 검사 · 출처 대조의 출력을 함께 봅니다.\n',
            '입력/README.md': '2회차에 만든 설비 모델과 같은 꼴의 설비 7대 모델(schema.json · graph.json)과 그 설비 대장(자료/설비_대장.csv)입니다. 이 폴더는 읽기만 합니다.\n',
        })


def conditions_lab(files):
    """실전반 02회차 실습5 — 작업 기준의 복합 조건과 예외를 조치 조건표로 표현하기(구성안 5.2)."""
    title = TITLES['practical-02-conditions']
    rec = '결과/판단기록.md'
    when = incident_time(files)
    save = ('`결과/조건표.csv` · `결과/판단기록.md`와 만든 코드를 함께 보관합니다. '
            f'다음 실습 「{TITLES["practical-03-review"]}」에서는 이 조건표를 읽어 후보별 판정과 조치 검토 결과를 만들고 후보마다 매뉴얼 근거를 잇습니다. '
            '그 실습도 제공된 조건표로 시작할 수 있으므로 이 결과는 골라서 가져갑니다. ' + USB)
    steps = [
        S('폴더와 출발점 확인', '시작',
          'VS Code 탐색기에서 이 폴더의 `자료/` · `결과/` · START.md를 열어 각 자리의 역할과 이번 질문을 확인합니다.',
          '이번 질문 세 개와, 이 답을 쓰는 사람이 누구인지 확인합니다.',
          '탐색기에서 세 자리를 찾았고, `결과/조건표.csv`에 열 이름만 있다는 것을 확인했습니다.',
          why=B.WHY_START + ' 절차(SOP)는 사람이 차례대로 하는 일을, 판단 규칙은 어떤 조건에서 조치를 쓸 수 있는지를 정합니다. 이번에는 판단 규칙 쪽을 표로 만듭니다.',
          differ=B.DIFFER_START),
        S('파일을 바꾸지 않고 자료 파악', '① 파악',
          'AI에게 파일을 바꾸지 말고, 원문의 조건 문장 · 판단 시스템 결정표의 행 · 사건 기록 · 확인 사례가 각각 무엇을 담고 있는지 파일 · 줄로 짚어 달라고 합니다. 짚은 줄을 직접 엽니다.',
          '자료끼리 말이 달라 보이는 곳이 있는지, 확인 사례의 값이 비는 까닭이 몇 가지인지 묻습니다.',
          B.EVIDENCE_LOOK + ' 질문 1 ~ 3에 쓸 자료가 무엇인지 내 말로 말할 수 있습니다.',
          H('조건과 판단 입력이 어디서 오는지 파악한다. 아직 아무것도 만들지 않는다.',
            '`자료/` 전체, START.md 「해결할 질문」',
            '파일을 바꾸지 않는다. 해석보다 파일 · 줄 번호를 먼저 받는다.',
            '원문 근거 목록, 자료끼리 말이 달라 보이는 곳 목록, 값이 비는 까닭 표',
            '짚은 줄 가운데 몇 개를 내가 직접 열어 같은 내용인지 본다'),
          why=('조건표에는 원문에 있는 조건만 담아야 합니다. 원문 · 시스템 내보내기 · 기록은 만든 때와 만든 사람이 달라 같은 조건도 다르게 적혀 있을 수 있으므로, 자료마다 어느 판 · 시점인지 먼저 압니다. '
               '이 단계에서 파일을 바꾸지 않는 것은 무엇을 옮길지 합의하기 전에 AI가 조건표를 만들기 시작하지 않게 하려는 것입니다.'),
          differ=B.DIFFER_LOOK),
        S('요구와 기대 판단 정하기', '② 요구',
          '`결과/판단기록.md` 첫머리에 목표 · 쓰는 사람 · 지킬 조건을 적고, 사건과 확인 사례 두세 개의 네 후보가 남는지 · 빠지는지 · 무엇이 아직 모르는 값인지를 원문에서 먼저 찾아 기대 판단으로 편집기에서 적습니다. 「학생이 정할 것」의 지점에 고른 것과 근거 줄을 적습니다.' + B.REQ_AFTER,
          B.ASK_DECIDE + DECIDE_FIRM,
          B.REQ_EVIDENCE,
          B.req_hint(rec, 2, '목표와 질문 · 이 답을 쓰는 사람 · 자료와 기준일 · 지킬 조건 · 「정한 것」 · 「기대 답과 실제 결과」'),
          why=B.WHY_REQ + ' 기대 판단을 경고 · 감점 · 제외로 나눠 적어 두어야 뒤에서 조건표 행의 결과 칸과 하나씩 견줄 수 있습니다.',
          differ=B.DIFFER_REQ.format(rec=rec)),
        S('계획 검토', '③ 계획',
          '조건표에 넣을 규칙과 옮길 순서를 AI의 계획으로 받아 검토하고 동의합니다. 아직 파일을 만들지 않습니다.',
          '조건표에 옮기지 않을 원문 조건과 그 까닭을 정합니다.' + DECIDE_FIRM_AGAIN,
          '사건의 네 후보에 걸릴 규칙을 계획에서 짚을 수 있습니다. 계획에 원문에 없는 기준값 · 조건이 없습니다. 계획에 내가 동의했습니다.',
          H('조건표에 들어갈 규칙과 순서를 합의한다',
            '`입출력_계약.md`, `결과/판단기록.md`',
            '원문에 없는 기준값 · 조건을 더하지 않는다. 「이번 범위 밖」은 넣지 않는다.',
            '규칙 목록과 옮길 순서',
            '사건의 네 후보에 어느 규칙이 걸리는지 계획에서 짚게 한다'),
          why='한 문장에 조건 여러 개와 예외가 섞인 원문을 바로 표로 옮기면 빠지거나 겹치는 행이 생깁니다. 무엇을 몇 행으로 옮길지 먼저 합의해야 행마다 원문으로 돌아갈 수 있습니다.',
          differ=B.DIFFER_PLAN),
        S('구현 ① 복합 조건 한 묶음', '④ ~ ⑥ 구현 · 대조 · 고침',
          '여러 조건이 함께 맞아야 하는 조건 하나를 골라 `결과/조건표.csv`에 계약 모양으로 옮기고 구조 검사를 실행합니다.' + B.OWN_RUN,
          '여러 조건을 한 묶음(AND)으로 둘지 나눌지와, 기준값을 포함하는지를 원문 낱말로 정합니다.',
          '구조 검사의 조건표 줄이 「통과」이고, 원문 줄과 행을 나란히 놓았을 때 입력 · 연산자 · 기준값 · 경계 · 결과가 같습니다.',
          H('규칙 하나를 계약 모양으로 옮긴다', '그 원문 줄, `입출력_계약.md`', '경계는 원문 낱말대로 옮긴다', '`결과/조건표.csv`의 한 묶음', '구조 검사를 실행하고, 원문 줄과 행을 나란히 보여 달라고 한다'),
          'python check.py',
          why=WHY_TABLE, differ=B.FIX_LOOP),
        S('구현 ② 나머지 조건과 경계', '④ ~ ⑥ 구현 · 대조 · 고침',
          '원문의 경고 · 감점 · 제외 조건을 모두 `결과/조건표.csv`에 옮깁니다.',
          '「이상 · 초과 · 미만」이 원문끼리 다른 곳을 무엇으로 정할지, 규칙을 어느 조치에 걸지 묻습니다.',
          '구조 검사의 조건표 줄이 「통과」이고, 규칙마다 원문 출처가 있습니다.',
          H('경고 · 감점 · 제외 조건을 모두 옮긴다', '매뉴얼, `자료/작업기준.md`, 5단계 결과', '한 규칙씩 옮긴다. 출처를 적는 방식을 섞지 않는다.', '`결과/조건표.csv` 전체', '규칙마다 구조 검사를 실행한다'),
          'python check.py',
          why=WHY_HIT, differ=B.FIX_LOOP),
        S('구현 ③ 판단 시스템 결정표와 출처 견주기', '⑤ 대조',
          '조건표의 행마다 `자료/판단시스템_결정표_내보내기.txt`에서 같은 내용의 행을 찾아 견주고, 출처 칸(`source_section`)에는 그 행의 근거인 원문 자리를 적습니다 — '
          '원문에서 근거를 찾지 못한 행이면 그렇다는 것과 그 행을 가져온 곳을 적습니다. 결정표와 다르게 옮긴 점은 `판단기록.md` 「정한 것」에 적고, 「정한 것」의 결정대로 됐는지 봅니다.',
          '「정한 것」의 결정대로인지, 같은 내용의 결정표 행과 무엇이 다른지 묻습니다. AI가 결정을 대신 정하려 하면 돌려보내고 내 선택과 근거를 다시 말합니다.',
          '조건표의 행마다 출처 칸이 원문으로 돌아가거나, 원문에서 찾지 못한 근거는 찾지 못했다고 적혀 있습니다.',
          H('조건표 행의 출처를 확정한다',
            '`자료/판단시스템_결정표_내보내기.txt`, `결과/조건표.csv`, 매뉴얼',
            '이름만 보고 스킬과 SOP를 잇지 않는다. 원문에서 찾지 못한 근거는 찾지 못했다고 적는다.',
            '조건표의 출처 칸(`source_section`)과 `판단기록.md` 「정한 것」',
            '조건표 행마다 같은 내용의 결정표 행을 짚게 하고, 몇 행은 직접 연다'),
          'python check.py',
          why=WHY_SOURCE, differ=B.FIX_LOOP),
        S('구현 ④ 확인 사례에 대는 기능', '④ ~ ⑥ 구현 · 대조 · 고침',
          '조건표를 `자료/확인_사례.csv`의 사례마다 대어 후보마다 맞은 규칙(경고 · 감점 · 제외)과 입력이 없어 맞는지 알 수 없는 규칙을 내는 기능을 `결과/`에 만들고 실행합니다. '
          '출력은 AI에게 `판단기록.md`의 대조 표로 옮기게 하고, 3단계에서 손으로 적은 사건과 사례의 기대와는 내가 견줍니다.',
          '결과가 기대와 다르면 조건표가 틀렸는지, 만든 기능이 틀렸는지, 기대가 틀렸는지 묻습니다. 대조 표의 「남는가 · 빠지는가」 칸은 기능이 내지 않으므로, 맞은 규칙 · 알 수 없는 규칙에 `자료/작업기준.md` 4절의 뜻을 대어 내가 적습니다.',
          '사례마다 후보의 맞은 규칙과 알 수 없는 규칙이 나오고, 손으로 구한 사건 · 사례와 같거나 다른 까닭이 `판단기록.md`에 있습니다. 입력이 빠졌는데 확인된 제외 사유도 있는 사례에서 제외와 미확인이 함께 나옵니다.',
          H('사례마다 조건표를 대어 맞은 규칙과 알 수 없는 규칙을 낸다',
            '`자료/확인_사례.csv`, `결과/조건표.csv`',
            '규칙은 조건표에서 읽는다(코드에 다시 적지 않는다). 빈 값을 0이나 앞의 값으로 채우지 않는다. 맞은 규칙은 모두 모은다. 대조 표는 출력에서 옮기고 칸을 더하거나 빼지 않는다.',
            '사례 · 후보마다 맞은 규칙 · 알 수 없는 규칙과 그 입력을 보이는 화면 출력, 그 출력을 옮긴 `판단기록.md` 「확인 사례 대조」 표',
            '3단계에서 손으로 구한 사건과 사례 두세 개를 출력과 견주고, 다른 줄은 원문 줄까지 따라간다'),
          'python 결과/<만든 코드 이름>.py',
          why=WHY_UNKNOWN + ' 사례가 많아 손으로 다 댈 수 없으므로 작은 기능으로 대고, 손으로 먼저 구한 몇 사례와 견주어 조건표와 기능을 함께 확인합니다.',
          differ='기대와 다른 사례가 있으면 그 사례의 입력 · 맞은 규칙 · 원문 줄을 나란히 놓고 조건표 · 기능 · 기대 가운데 어느 쪽이 원문과 다른지 찾아 고친 뒤 같은 기능을 다시 실행합니다.'),
        S('남은 후보와 실행 승인 나눠 적기', '⑤ 대조',
          '8단계 출력으로 사건과 사례마다 남은 후보와, 그 후보를 실행하려면 누가 승인하는지와 그 원문 출처(파일 · 줄)를 `판단기록.md`에 따로 적습니다. 판단을 보류한 후보도 남은 후보로 적되 보류와 빠진 입력을 함께 적습니다.',
          '남은 후보마다 누가 승인하고 그 근거가 원문 어디(파일 · 줄)에 있는지, 원문의 승인 줄이 하나로 읽히지 않는 후보가 있는지 묻습니다.',
          '「남은 후보」와 「승인 역할 · 근거」가 따로 적혀 있고, 승인은 원문의 파일 · 줄로 돌아갑니다. 보류한 후보에는 보류와 빠진 입력이 붙어 있습니다.',
          H('후보가 남는 것과 실행 승인을 따로 적는다',
            '8단계 표, 매뉴얼의 승인 줄',
            '남은 것이나 순서를 승인처럼 쓰지 않는다',
            '「남은 후보」(보류한 후보는 보류와 빠진 입력을 붙여) · 「승인 역할 · 근거(파일 · 줄)」 두 칸',
            '사건의 후보마다 승인 줄을 원문에서 직접 연다'),
          why='판단 규칙이 후보를 남겼다는 것은 쓸 수 있다는 뜻일 뿐 실행해도 된다는 허락이 아닙니다. 실행은 정해진 사람이 한 번 승인한 뒤에 하므로, 누가 승인하는지를 원문에서 따로 확인합니다.',
          differ=B.FIX_LOOP),
        S('구조 검사와 고치기', '⑤ ⑥ 대조 · 고침',
          '터미널에서 구조 검사를 실행하고, 짚은 문제를 고친 뒤 8단계 기능을 다시 실행해 사례 대조를 다시 합니다.',
          '검사가 짚은 문제가 결과 파일의 어느 항목 · 행인지 묻습니다.',
          '「구조 검사 통과」 줄이 나오고, 고친 뒤에도 8단계 사례 대조가 같습니다.',
          H('구조 문제를 고친다', '`python check.py`의 출력', '검사 기준과 원자료를 바꾸지 않는다', '고친 파일 목록과 다시 실행한 출력', '고친 뒤 8단계 기능을 다시 실행해 사례 대조를 다시 본다'),
          'python check.py',
          why=TABLE_CHECK_WHY, differ=DIFFER_CHECK),
        S('저장하고 다시 열기', '⑦ 저장 · 다시 열기',
          '결과 파일을 저장하고 VS Code에서 폴더를 닫았다 다시 연 뒤 만든 기능과 구조 검사를 다시 실행합니다. `판단기록.md` 끝에 기준일 · 저장 시점 · 확인하지 못한 점을 적습니다.',
          '확인하지 못한 점으로 무엇을 남길지 정합니다.',
          '다시 연 뒤에도 출력이 같습니다. `결과/`에 `조건표.csv` · `판단기록.md`와 만든 코드가 있습니다.',
          cmd='python 결과/<만든 코드 이름>.py\npython check.py', why=B.WHY_SAVE, differ=B.DIFFER_SAVE),
    ]
    extra = ('## 확인 사례 대조\n\n| 사례 | 후보 | 맞은 규칙 | 경고 | 감점(만원) | 제외 사유 | 미확인과 까닭 | 남는가 · 빠지는가 | 원문 근거 |\n'
             '|---|---|---|---|---:|---|---|---|---|\n| | | | | | | | | |\n\n'
             '## 남은 후보와 실행 승인\n\n| 사례 | 남은 후보 | 승인 역할 | 승인 근거(파일 · 줄) |\n|---|---|---|---|\n| | | | |\n\n')
    formats = ['## 결과 형식\n\n파일의 모양은 `입출력_계약.md`에 있습니다. 어떤 조건을 몇 행으로 옮길지는 원문을 읽고 직접 정합니다.\n\n'
               '- `결과/조건표.csv` — 판단 조건(계약 「조건표」). 「제공 빈 틀」에 열 이름이 있습니다.\n'
               '- `결과/판단기록.md` — 「제공 빈 틀」의 칸대로 채웁니다.\n'
               '- 만든 코드는 `결과/` 아래에 두고, 이름은 하는 일로 짓습니다.\n\n'
               '## 지킬 조건\n\n'
               '- 조건표의 행마다 원문 출처를 답니다.\n'
               '- 사례에 대는 기능은 규칙을 코드에 다시 적지 않고 `결과/조건표.csv`에서 읽습니다.\n'
               '- 남은 후보를 실행 승인처럼 적지 않습니다.\n']
    return dict(
        title=title, rec=rec, readonly='`자료/`가', decide_step=2, course='실전반',
        goal=[f'포털 판단 규칙 화면에서 허용 · 제외된 후보를 SOP의 금지 조건과 대조했습니다. 이번에는 그 근거를 제공 SOP(HM-8 매뉴얼)에서 직접 뽑아 조치 조건표로 만들고, '
              f'판단 시스템에 등록된 결정표와 행마다 출처를 견줍니다. 사건은 포털에서 본 경보와 같은 종류의 다른 경보 한 건, 10월 27일 {when} HYD-02 쿨러 성능 저하 경보입니다.',
              '조건표는 어떤 입력이 어떤 값일 때 조치를 경고 · 감점 · 제외하는지를 한 행씩 적은 판단 규칙이고, DMN(판단을 표준 모양으로 적는 방식)의 결정표 — 입력 조건과 판단 결과를 한 행씩 적은 표 — 를 이 실습에서 부르는 이름입니다. '
              '원문은 사람이 읽는 문장이라 한 문장에 조건 여러 개와 예외가 섞여 있고, '
              '판단 시스템에 등록된 표는 옛 판으로 만들어져 번호와 낱말이 다릅니다. 행마다 원문으로 돌아갈 수 있어야 판단 결과를 믿고 쓸 수 있습니다.',
              B.STAGE_LINE.format(what='판단 지식 — 작업 기준의 조건을 판단 규칙으로 옮기는 일 — ')],
        make='만들 것: `결과/조건표.csv`, `결과/판단기록.md`(요구 · 정한 것 · 기대 판단과 실제 · 확인 사례 대조 · 남은 후보와 실행 승인 · 저장 기록), 조건표를 확인 사례에 대는 코드.',
        start=['`자료/HM-8_매뉴얼.md` — 제공 SOP: 현행 HM-8 1.1판(2026-09-01 시행) 냉각 계통 조치 원문. `자료/HI-01_보충매뉴얼.md` — 점검 · 이상 확인 보충 기준. `자료/작업기준.md` — 회사 작업 기준.',
               '`자료/판단시스템_결정표_내보내기.txt` — 판단 시스템에 등록된 결정표 · 스킬을 내보낸 것(2025년 도입 판, 2026-10-27 내보냄).',
               '`자료/targets.csv` — 이번 경보에서 검토하는 조치 후보 넷. `자료/사건_기록_HYD-02_1027.md` — 야간 운전원이 HMI에서 옮겨 적은 사건 메모. '
               '`자료/확인_사례.csv` — 지난 30일 경보 가운데 고른 확인 사례의 판단 입력(입력마다 원천과 그 시각).',
               '`입출력_계약.md` — 조건표의 형식. `check.py` — 조건표의 구조 검사.',
               '`결과/` — 「제공 빈 틀」 `판단기록.md`와 열 이름만 있는 `조건표.csv`가 있습니다.',
               RULES_LINE],
        user='이 답은 야간 운전원이 경보가 났을 때 어느 조치가 남고 어느 조치가 빠지는지, 남은 조치를 누가 승인하는지 볼 때 씁니다.',
        questions=['네 조치의 경고 · 감점 · 제외 조건(입력 · 단위 · 연산자 · 경계 · 결과 · 출처)은 무엇인가?',
                   '사건과 확인 사례에서 각 후보는 남는가, 빠지는가, 무엇이 아직 모르는 값인가?',
                   '남은 후보와 실행 승인은 어떻게 다른가 — 남은 후보마다 누가 승인하는가?'],
        decide=[('출처가 확인되지 않는 기준', '판단 시스템 결정표에 있는데 제공 SOP에서 근거 문장을 찾을 수 없는 규칙을 조건표에 어떻게 둘지 — 그런 규칙이 여럿이면 규칙마다 정하고 근거를 적습니다')],
        outside=['원천 기록에서 판단 입력을 만드는 일과, 후보를 유지 · 제외 · 보류로 판정해 견주고 검토 결과로 내는 프로그램(다음 실습)',
                 'SOP 구조(적용 · 금지 · 단계 · 완료 · 승인 전체)를 만드는 일',
                 '실제 설비 · 포털 · 업무 시스템을 부르는 일'],
        formats=formats, steps=steps,
        cases=['조건표의 숫자 기준값마다 그 값과 같은 값, 그 값의 바로 위 · 아래에서 가장 가까운 값(경계)',
               '경고 · 감점 · 제외가 한 후보에 함께 맞는 경우(복수 사유)',
               '입력이 빠졌는데 이미 확인된 제외 사유가 있는 경우',
               '값이 비어 있어도 그 후보에는 해당 규칙이 걸리지 않는 경우(적용 대상 밖)',
               '「정할 것」의 결정에 따라 결과가 바뀌는 사례',
               '사건 한 건',
               '같은 코드를 다시 실행한 결과'],
        commands='python check.py\npython 결과/<만든 코드 이름>.py',
        done=('형식 검사 통과만으로 완료하지 않습니다. 조건표의 행마다 원문 문장으로 돌아갈 수 있고, 원문에서 먼저 적은 사건 · 사례의 기대 판단과 만든 기능이 조건표를 대어 낸 결과가 맞고, '
              '「정한 것」의 근거와 그 선택으로 바뀌는 사례를 설명할 수 있으며, 남은 후보와 실행 승인을 따로 적었으면 완료입니다.'),
        save=save, reopen='구조 검사의 출력, `판단기록.md`의 사례 대조와 기준일 · 저장 시점 · 확인하지 못한 점',
        tree=tree('02일차_실습5_조치조건표', [('.github/', 'Copilot 작업 규칙'), ('결과/', '이번에 만들 것(판단기록.md · 조건표.csv 빈 틀)'),
                                         ('자료/', '매뉴얼 · 판단 시스템 결정표 · 사건 메모 · 확인 사례(읽기만)'),
                                         ('AGENTS.md', 'Codex 작업 규칙'), ('check.py', '구조 검사'), ('CLAUDE.md', '작업 규칙(같은 내용)'), ('guide.html', '이 가이드'),
                                         ('START.md', '이번 과제와 진행 단계'), ('안내.html', '이 가이드와 같은 파일'), ('입출력_계약.md', '조건표의 형식')]),
        lead='제공 SOP의 경고 · 감점 · 제외 조건을 조치 조건표로 옮기고, 판단 시스템 결정표와 출처를 견준 뒤, 확인 사례에 대는 작은 기능을 만들어 남는 후보와 실행 승인을 구별합니다.',
        need='VS Code와 Python, 로그인해 둔 Codex 또는 GitHub Copilot.',
        terms=('**SOP**는 표준 작업 절차입니다. ' + RESULT_KINDS + ' **미확인**은 입력이 없어 조건이 맞는지 알 수 없는 상태입니다. ' + SYSTEM_TERM + ' ' + CONTRACT_TERM),
        guide_extra={1: ['ai', 'review'], 4: ['terminal']}, guide_after={4: [STUCK_PATH, STUCK_FIRST_TABLE]}, files={
            'check.py': CONDITIONS_CHECK,
            '입출력_계약.md': ('# 입출력 계약\n\n결과 파일의 형식과 뜻만 정한다. 무엇을 담을지는 원문에서 정한다.\n\n' + TABLE_CONTRACT + '\n' + CASES_CONTRACT).replace('{codes_from}', CODES_FROM_TARGETS),
            '결과/판단기록.md': req_template('판단 기록', extra),
            '결과/조건표.csv': TABLE_HEADER,
            '결과/README.md': '이번 과제의 조건표(조건표.csv)와 판단기록.md를 여기에 저장합니다.\n다시 열 때는 판단기록.md의 기준일 · 저장 시점과 구조 검사의 출력을 함께 봅니다.\n',
        })


# ───────────── 판정 랩 둘(통합 03-3 · 실전 03-2) — 계약 · 검사기 · 빈 틀 ─────────────
INPUT_NAMES = ['forecast_ts1', 'forecast_ps1', 'fan100_hours', 'plc_mode', 'plc_state', 'skill_kind', 'skill_code']
JUDGE_INPUT_CONTRACT = '''## 입력

- `입력/조건표.csv` — 조건표(아래 「조건표」). 판정 기능은 규칙을 코드에 다시 적지 않고 이 파일을 읽는다. 열 이름이 계약과 다르면 파일 · 행을 밝혀 멈춘다.
- `입력/sop.json` — SOP 구조(적용 조건 · 금지 조건 · 수행 단계 · 완료 기준 · 승인과 원문 출처). 키의 뜻은 `입력/README.md`에 있다.
- `자료/`의 원천 네 개(`경보_목록.csv` · `PLC_상태_수신.csv` · `팬_운전_카운터.csv` · `예측_결과.csv`), `자료/오더_현황.csv`, `자료/metrics/`(`지표_정의.md` · `업무_값.json` · `후보_설정.csv`).
- 내 앞 결과를 쓸 때는 `결과/내_입력/`에 같은 이름으로 둔다. 구조 검사는 그 폴더에 있는 파일을 기준으로 보고, 어느 파일을 봤는지 첫 줄에 찍는다.

## 판단 입력

- 경보 하나(`경보_목록.csv`의 RAISE 행)가 사례 하나이고, 사례마다 `자료/targets.csv`의 후보를 판정한다.
- 후보마다 아래 「조건표」의 입력 이름 일곱 개를 모두 만든다(조건표가 지금 쓰지 않는 입력도). 단위는 그 표의 단위다.
- `skill_kind` · `skill_code`는 `targets.csv`의 `kind` · `codes`(`;`로 나눈 목록)다.
- 값을 정할 수 없는 입력은 `null`이고, 왜 없는지(원천 · 시각)를 함께 적는다.

'''

CASES_CONTRACT = '''## 확인 사례 (`자료/확인_사례.csv`, 읽기만)

열: `사례,설비,판정_요청_시각,후보,입력,값,단위,원천,원천_시각,비고`. 한 줄이 사례 하나의 판단 입력 하나다.

- `값`은 판정을 요청한 때(`판정_요청_시각`)의 판단 입력이고 단위는 `단위` 칸이다. 조건표 `input`과의 짝: `운전_모드` = `plc_mode`, `상태` = `plc_state`,
  `팬100_연속` = `fan100_hours`(판정 요청 때까지 팬 100 % 연속 운전 시간, h), `예측_TS1` = `forecast_ts1`(℃), `예측_PS1` = `forecast_ps1`(bar).
- `후보`가 빈칸인 줄은 그 사례의 모든 후보에 같은 입력이다. `skill_kind` · `skill_code`는 이 파일에 없다 — 값이 오는 곳은 조건표 절의 `input` 설명과 같다.
- `값`이 빈칸이면 그 입력을 얻지 못한 것이고, `비고`에 원천의 사정이 있다.
- `원천` · `원천_시각`은 그 값을 만든 기록과 그 기록의 시각이다.
'''


SOP_KEYS = ('sop.json 키의 뜻: `document` 원문 문서, `failure_modes` 고장 유형, `causes` 원인, `sops` 조치 절차(`id` · `name` 이름 · `kind` 조치 종류(없으면 null) · `codes` 실행 코드 · `source` 출처 · '
            '`failure_mode` 고장 유형 · `model_refs` 모델 참조 · `apply_conditions` 적용 조건 · `prohibitions` 금지 조건 · `steps` 수행 단계 · `completion` 완료 기준 · `approval` 승인(`role` 역할)), '
            '`relations` 관계 목록. 항목마다 `text`는 원문 문장, `rules`는 그 조건을 옮긴 조건표의 `rule_id`다.\n')


def judge_table_contract():
    """판정 랩 계약의 「조건표」 절 — 조건 랩의 TABLE_CONTRACT에서 이 랩에 맞지 않는 문장(결과 위치 · 다음 실습 · 모양 예)만 바꾼다."""
    head, body = TABLE_CONTRACT.replace('{codes_from}', CODES_FROM_TARGETS).split('\n\n', 1)
    body = body.split('\n\n', 1)[1].split('모양을 보이는 한 줄')[0].rstrip()
    return '## 조건표 (`입력/조건표.csv`)\n\n' + body + '\n'


CANDIDATE_SHAPE = '''```
{"sop": "SOP-...", "status": "유지 | 제외 | 보류",
 "inputs": {"forecast_ts1": 숫자 또는 null, "forecast_ps1": ..., "fan100_hours": ..., "plc_mode": ..., "plc_state": ..., "skill_kind": ..., "skill_code": [...]},
 "missing_reasons": {"null인 입력": "왜 없는지(원천 · 시각)"},
 "warnings":   [ {"rule_id": "...", "reason": "...", "source_section": "...", "conditions": [ {"input": "...", "actual": 값, "operator": "...", "value": "...", "unit": "..."} ]} ],
 "penalties":  [ {위와 같음, "penalty_manwon": 숫자} ],
 "exclusions": [ {위와 같음} ],
 "unknown":    [ {"rule_id": "...", "result": "...", "missing": ["빠진 입력"], "source_section": "..."} ],
 "comparison": {"cost": 0, "production": 0, "quality": 0, "energy": 0, "penalty": 0, "total": 0} 또는 null,
 "no_comparison_reason": ["유지 후보인데 비교값이 없는 까닭"]}
```'''

COMMON_RESULT_NOTES = '''- 키의 뜻: `comparison_basis` 비교 기준 문장, `decisions` 정한 것(`item` 항목 · `decision` 정한 방법 · `basis` 근거), `decision_time` 판정을 요청한 시각, `status` 판정,
  `inputs` 판단 입력, `missing_reasons` 값이 없는 까닭, `comparison` 비교값(`cost` 비용 · `production` 생산 · `quality` 품질 · `energy` 에너지 · `penalty` 감점 · `total` 합계, 만원),
  `no_comparison_reason` 비교값이 없는 까닭, `rank` 순위.
- 사례의 순서는 `자료/경보_목록.csv`의 RAISE 행 순서, 후보의 순서는 `자료/targets.csv`의 순서다.
- `status`는 `유지` · `제외` · `보류` 가운데 하나이고, 세 말의 뜻은 `자료/작업기준.md` 4절의 말이다.
- `comparison`이 있는 후보는 `유지` 후보다. 비교값이 없는 유지 후보는 `no_comparison_reason`에 그 까닭을 적는다.
- 금액은 `지표_정의.md` 식의 원값을 소수 둘째 자리로 반올림해 적고, `total`은 네 손실과 감점의 원값을 더한 뒤 반올림한다.
  반올림은 사사오입이다 — 셋째 자리가 5 이상이면 올린다(0.125는 0.13). 부동소수 계산의 작은 오차로 끝자리 5가 4999…가 되어 내려가지 않게 한다.
- 순위는 비교값이 있는 후보마다 하나이고 `total`이 작은 순서다. 같은 `total`은 같은 순위다(1, 1, 3).
'''

JUDGE_RESULT = '''## 결과 (`결과/result.json`)

```
{
  "comparison_basis": "이 비교 합계가 무엇을 견주는 값인지, 포털 성과 지표의 점수와 어떻게 다른지",
  "decisions": [ {"item": "...", "decision": "판단 입력을 만든 방법 · 견주는 후보 등 정한 것", "basis": "파일 · 절"} ],
  "events": [
    {"id": "경보_ID", "asset": "HYD-..", "decision_time": "판정_요청_시각",
     "candidates": [ 후보 판정 ],
     "ranking": [ {"rank": 1, "sop": "...", "total": 0.0} ],
     "selection": {"reason": "1위를 고른 까닭 또는 순위가 없는 까닭", "checks": ["추가로 확인할 사항"]}}
  ]
}
```

후보 판정:

''' + CANDIDATE_SHAPE + '''

''' + COMMON_RESULT_NOTES + '''- 이 결과만의 키: `warnings` 경고 · `penalties` 감점 · `exclusions` 제외(맞은 규칙과 조건마다 실제 값 `actual`), `penalty_manwon` 감점 금액(만원),
  `unknown` 입력이 없어 맞는지 알 수 없는 규칙(`missing` 빠진 입력), `ranking` 순위 목록, `selection` 고른 까닭(`reason` · `checks`).
- `ranking`은 사례마다 비교값이 있는 후보의 순위 목록이고 `total`은 그 후보의 `comparison.total`과 같다.
- `selection`의 `reason`은 1위를 고른 까닭(순위가 없으면 그 까닭), `checks`는 실행 전후에 추가로 확인할 사항이다.
'''

REVIEW_RESULT = '''## 결과 (`결과/조치검토결과.json` · `결과/조치검토결과.md`)

```
{
  "comparison_basis": "이 비교 합계가 무엇을 견주는 값인지, 포털 성과 지표의 점수 · 실행 승인과 어떻게 다른지",
  "decisions": [ {"item": "...", "decision": "판단 입력을 만든 방법 · 견주는 후보 등 정한 것", "basis": "파일 · 절"} ],
  "events": [
    {"id": "경보_ID", "asset": "HYD-..", "decision_time": "판정_요청_시각",
     "candidates": [
       {"sop": "SOP-...", "status": "유지 | 제외 | 보류",
        "inputs": {"forecast_ts1": 숫자 또는 null, ...},
        "missing_reasons": {"null인 입력": "왜 없는지(원천 · 시각)"},
        "reasons": [ {"rule_id": "...", "result": "WARN | PENALTY | EXCLUDE | 미확인", "actual_inputs": {"입력": 값}, "expression": "식", "source": "...",
                      "missing_inputs": ["미확인일 때"], "missing_reason": "미확인일 때 원천의 사정"} ],
        "sources": ["..."],
        "checks": ["..."],
        "comparison": {"cost": 0, "production": 0, "quality": 0, "energy": 0, "penalty": 0, "total": 0} 또는 null,
        "no_comparison_reason": ["유지 후보인데 비교값이 없는 까닭"],
        "rank": 1 또는 null,
        "approval": {"role": "...", "source": "...", "note": "..."}}
     ],
     "review": {"top": ["..."], "reason": "...", "checks": ["..."]}}
  ]
}
```

''' + COMMON_RESULT_NOTES + '''- 이 결과만의 키: `reasons` 후보의 이유(맞은 규칙과, 입력이 없어 맞는지 알 수 없는 규칙 `미확인`) — `actual_inputs` 실제 입력 · `expression` 비교식 · `source` 출처 · `missing_inputs` 빠진 입력 · `missing_reason` 빠진 까닭,
  `sources` 원문 출처, `checks` 추가로 확인할 값, `approval` 승인(`role` 역할 · `source` 출처 · `note` 안내), `review` 검토 의견(`top` 승인 요청을 검토할 후보 · `reason` 까닭 · `checks` 먼저 확인할 값).
- `reasons`의 `result`가 `미확인`이면 `missing_inputs`와 `missing_reason`을 적는다.
- `sources`는 이유에 쓴 규칙의 출처와 그 후보 SOP의 절이다.
- `checks`에는 미확인 규칙의 빠진 입력마다 그 입력 이름과 다시 받을 곳을 적고, 유지 후보는 실행 전에 확인할 조건 · 완료 기준(`입력/sop.json`)을 적는다.
- `approval`은 그 후보의 승인 역할과 출처(`입력/sop.json`)와, 순위가 실행 승인이 아니라는 안내다.
- `review.top`은 비교 순위 1위 후보(없으면 빈 목록)이고, `reason`은 그 까닭 또는 순위가 없는 까닭, `checks`는 담당자가 먼저 확인할 값이다.
- `결과/조치검토결과.md`는 같은 내용을 사례마다 절로 나눠 사람이 읽게 쓴다. 절 제목에 경보 ID를 넣는다.
'''

JUDGE_CHECK_COMMON = r'''from pathlib import Path
import csv, json, re, sys
root = Path(__file__).resolve().parent
INPUTS = ['forecast_ts1', 'forecast_ps1', 'fan100_hours', 'plc_mode', 'plc_state', 'skill_kind', 'skill_code']
RANGE = {'forecast_ts1': (0, 150, '℃'), 'forecast_ps1': (50, 300, 'bar'), 'fan100_hours': (0, 1000, 'h')}
LOSS = ['cost', 'production', 'quality', 'energy', 'penalty']
def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as f: return list(csv.DictReader(f))
''' + PICK + r'''
alarms = [r['경보_ID'] for r in rows(root/'자료/경보_목록.csv') if r['구분'] == 'RAISE' and r['판정_요청_시각']]
sops = [r['sop_id'] for r in rows(root/'자료/targets.csv')]
table_path = pick('조건표.csv')
table = rows(table_path)
if not table or not {'rule_id', 'action'} <= set(table[0]):
    print(f'구조 확인 필요 — {table_path.relative_to(root).as_posix()}의 열 이름이 계약(rule_id · action …)과 다릅니다. 내 입력이면 계약과 견주어 고친 뒤 다시 실행합니다.')
    sys.exit(1)
groups = {(r['rule_id'], r['action']) for r in table}
def num(x): return isinstance(x, (int, float)) and not isinstance(x, bool)
def inputs_errors(at, inputs, reasons):
    out = []
    for k in INPUTS:
        if k not in inputs: out.append(f'{at}: 입력에 {k}가 없습니다(값이 없으면 null).')
        elif inputs[k] is None and not (reasons or {}).get(k): out.append(f'{at}: {k}가 null인데 왜 없는지가 없습니다.')
    for k, (lo, hi, unit) in RANGE.items():
        v = inputs.get(k)
        if num(v) and not lo <= v <= hi: out.append(f'{at}: {k}={v}는 계약 단위 {unit}의 범위({lo} ~ {hi})를 벗어납니다. 원천의 단위를 확인합니다.')
    return out
def total_errors(at, value):
    if not isinstance(value, dict) or not all(num(value.get(k)) for k in LOSS + ['total']): return [f'{at}: 비교값(comparison)에 {LOSS + ["total"]}가 숫자로 있어야 합니다.']
    if abs(sum(value[k] for k in LOSS) - value['total']) > 0.03: return [f'{at}: 합계 total {value["total"]}가 네 손실과 감점의 합 {sum(value[k] for k in LOSS):.2f}와 다릅니다.']
    return []
def rank_errors(at, ranked):
    """ranked = [(sop, 순위, 합계)] — 합계 오름차순과 같은 합계 같은 순위(1, 1, 3)."""
    out, ranked = [], sorted(ranked, key=lambda x: (x[1] if num(x[1]) else 9e9))
    totals = [t for _, _, t in ranked]
    if totals != sorted(totals): out.append(f'{at}: 순위가 합계가 작은 순서가 아닙니다.')
    for i, (s, r, t) in enumerate(ranked):
        want = ranked[i - 1][1] if i and ranked[i - 1][2] == t else i + 1
        if r != want: out.append(f'{at}: {s}의 순위 {r} — 같은 합계는 같은 순위, 다음은 그 수만큼 건너뜁니다(1, 1, 3).')
    return out
def kept_errors(at, status, value, note):
    """비교값은 유지 후보에만, 비교값이 없는 유지 후보에는 까닭."""
    if status != '유지':
        return [f'{at}: 유지가 아닌 후보({status})에 비교값이 있습니다.'] if value is not None else []
    if value is None:
        return [] if note else [f'{at}: 유지 후보에 비교값이 없으면 no_comparison_reason에 까닭이 필요합니다.']
    return total_errors(at, value)
def decisions_errors(value):
    if not isinstance(value, list) or not value or any(not (isinstance(d, dict) and d.get('item') and d.get('decision') and d.get('basis')) for d in value):
        return ['decisions(item · decision · basis — 판단 입력을 만든 방법 · 견주는 후보 등 정한 것)가 필요합니다.']
    return []
def expect_time(path):
    if not path.is_file(): return []
    m = re.search(r'기대 칸을 쓴 시각[^:]*:[ \t]*(\S.*)?$', path.read_text(encoding='utf-8-sig'), re.M)
    return [] if m and m.group(1) else ['기대결과.md 「기대 칸을 쓴 시각」이 비어 있습니다 — 실행 전에 기대를 먼저 적었는지 남깁니다.']
''' + RECORD_CHECK

JUDGE_CHECK = r'''"""결과/result.json의 구조와 계약 검사, 기대결과.md 기록 칸 확인. 생성 · 수정 · 네트워크 접속을 하지 않는다.
어떤 규칙이 맞아야 하는지, 금액이 맞는지, 어느 후보가 1위여야 하는지는 판정하지 않는다 — 원천 · 원문 · 지표_정의.md 손계산과 따로 대조한다.
규칙 ID는 결과/내_입력/조건표.csv가 있으면 그것으로, 없으면 입력/조건표.csv로 본다(어느 쪽을 봤는지 첫 줄에 찍는다).
사용: python check.py
"""
''' + JUDGE_CHECK_COMMON + r'''
def hit_errors(at, sop, hits, penalty=False):
    out = []
    if not isinstance(hits, list): return [f'{at}: 맞은 규칙은 목록입니다.']
    for h in hits:
        if (h.get('rule_id'), sop) not in groups: out.append(f'{at}: 기준 조건표에 없는 규칙 · 후보 {h.get("rule_id")}')
        if not h.get('source_section') or not isinstance(h.get('conditions'), list) or not h['conditions']: out.append(f'{at} {h.get("rule_id")}: source_section과 conditions(조건마다 실제 값)가 필요합니다.')
        if penalty and not num(h.get('penalty_manwon')): out.append(f'{at} {h.get("rule_id")}: penalty_manwon이 숫자로 필요합니다.')
    return out
def check_result(path):
    if not path.is_file(): return '없음', [], ''
    try: result = json.loads(path.read_text(encoding='utf-8-sig'))
    except ValueError as e: return '확인 필요', [f'JSON 읽기 실패: {e}'], ''
    errs = []
    if not str(result.get('comparison_basis', '')).strip(): errs.append('comparison_basis(비교 합계와 포털 성과 지표 점수의 구분 문장)가 없습니다.')
    errs += decisions_errors(result.get('decisions'))
    events = result.get('events')
    if not isinstance(events, list): return '확인 필요', errs + ['events 목록이 없습니다.'], ''
    got = [e.get('id') for e in events if isinstance(e, dict)]
    if got != alarms: errs.append(f'events: 경보_목록.csv의 RAISE 행과 사례 · 순서가 다릅니다(빠짐 {sorted(set(alarms) - set(got))}, 더함 {sorted(set(got) - set(alarms))}).')
    for e in events:
        eid = e.get('id'); cands = e.get('candidates') or []
        if [c.get('sop') for c in cands] != sops: errs.append(f'{eid}: 후보 목록 · 순서가 targets.csv와 다릅니다.')
        totals = {}
        for c in cands:
            at = f'{eid}/{c.get("sop")}'
            errs += inputs_errors(at, c.get('inputs') or {}, c.get('missing_reasons'))
            st = c.get('status')
            if st not in ('유지', '제외', '보류'): errs.append(f'{at}: status는 유지 · 제외 · 보류 가운데 하나입니다.'); continue
            errs += hit_errors(at, c.get('sop'), c.get('warnings')) + hit_errors(at, c.get('sop'), c.get('exclusions')) + hit_errors(at, c.get('sop'), c.get('penalties'), True)
            unknown = c.get('unknown') if isinstance(c.get('unknown'), list) else []
            for u in unknown:
                if (u.get('rule_id'), c.get('sop')) not in groups: errs.append(f'{at}: 기준 조건표에 없는 규칙 · 후보 {u.get("rule_id")}')
                if not u.get('missing'): errs.append(f'{at} {u.get("rule_id")}: unknown에는 빠진 입력 이름(missing)이 필요합니다.')
            ex = c.get('exclusions') or []
            want = '제외' if ex else ('보류' if unknown else '유지')
            if st != want: errs.append(f'{at}: status {st} — 제외 사유 {len(ex)}개 · 알 수 없는 규칙 {len(unknown)}개와 맞지 않습니다(뜻은 작업기준.md 4절).')
            comp = c.get('comparison')
            errs += kept_errors(at, st, comp, c.get('no_comparison_reason'))
            if st == '유지' and isinstance(comp, dict):
                totals[c.get('sop')] = comp.get('total')
                pen = sum(p.get('penalty_manwon', 0) for p in c.get('penalties') or [] if num(p.get('penalty_manwon')))
                if num(comp.get('penalty')) and abs(pen - comp['penalty']) > 0.001: errs.append(f'{at}: 감점 {comp["penalty"]}이 penalties 금액의 합 {pen}과 다릅니다.')
        ranking = e.get('ranking')
        if not isinstance(ranking, list): errs.append(f'{eid}: ranking 목록이 필요합니다.'); continue
        if sorted(r.get('sop') for r in ranking) != sorted(totals): errs.append(f'{eid}: ranking에는 비교값이 있는 후보가 모두 한 번씩 있어야 합니다(지금 {sorted(r.get("sop") for r in ranking)}, 비교값 있음 {sorted(totals)}).')
        for r in ranking:
            if r.get('total') != totals.get(r.get('sop')): errs.append(f'{eid}: ranking의 {r.get("sop")} total이 그 후보의 비교값과 다릅니다.')
        errs += rank_errors(eid, [(r.get('sop'), r.get('rank'), r.get('total')) for r in ranking])
        sel = e.get('selection') or {}
        if not sel.get('reason'): errs.append(f'{eid}: selection.reason(1위를 고른 까닭 또는 순위가 없는 까닭)이 필요합니다.')
        if not isinstance(sel.get('checks'), list): errs.append(f'{eid}: selection.checks 목록이 필요합니다(없으면 빈 목록).')
    return ('확인 필요' if errs else '통과'), errs, f'사례 {len(events)}건'
state, errs, note = check_result(root/'결과/result.json')
if state == '없음': print('아직 검사할 결과가 없습니다: 결과/result.json')
print('구조 검사 결과')
ok = report([('result.json', state, errs, note, True), record_part(root/'결과/기대결과.md', '고른 것', '정한 것'),
             record_part(root/'결과/기대결과.md', '실제 결과', '사례 대조'), record_part(root/'결과/기대결과.md', '프로그램', '손계산 대조'),
             shape_part(root/'결과/기대결과.md')])
for line in expect_time(root/'결과/기대결과.md'): print('참고: ' + line)
print('구조 검사 통과' if ok else '구조 확인 필요 — 위 줄마다 결과의 어느 사례 · 후보인지 찾아 고친 뒤 다시 실행합니다.')
print('이 검사는 모양과 계약만 봅니다. 의미와 질문별 답(어떤 규칙이 맞아야 하는지, 금액, 어느 후보가 1위인지)은 원자료와 따로 대조합니다.')
sys.exit(0 if ok else 1)
'''

REVIEW_CHECK = r'''"""결과/조치검토결과.json · .md의 구조와 계약 검사, 기대결과.md 기록 칸 확인. 생성 · 수정 · 네트워크 접속을 하지 않는다.
판정 · 이유 · 출처가 원문 · 원천과 맞는지, 금액, 어느 후보가 1위여야 하는지는 판정하지 않는다 — 원자료와 따로 대조한다.
규칙 ID는 결과/내_입력/조건표.csv, 승인 역할은 결과/내_입력/sop.json이 있으면 그것으로, 없으면 입력/의 파일로 본다(어느 쪽을 봤는지 찍는다).
사용: python check.py
"""
''' + JUDGE_CHECK_COMMON + r'''
sop_doc = json.loads(pick('sop.json').read_text(encoding='utf-8-sig'))
approver = {s['id']: (s.get('approval') or {}).get('role') for s in sop_doc.get('sops', [])}
def check_review(jpath, mpath):
    if not jpath.is_file(): return '없음', [], ''
    try: rv = json.loads(jpath.read_text(encoding='utf-8-sig'))
    except ValueError as e: return '확인 필요', [f'JSON 읽기 실패: {e}'], ''
    md = mpath.read_text(encoding='utf-8-sig') if mpath.is_file() else ''
    errs = [] if md else ['조치검토결과.md가 없습니다.']
    if not str(rv.get('comparison_basis', '')).strip(): errs.append('comparison_basis(비교 합계와 포털 성과 지표 점수 · 실행 승인의 구분 문장)가 없습니다.')
    errs += decisions_errors(rv.get('decisions'))
    events = rv.get('events')
    if not isinstance(events, list): return '확인 필요', errs + ['events 목록이 없습니다.'], ''
    got = [i.get('id') for i in events if isinstance(i, dict)]
    if got != alarms: errs.append(f'events: 경보_목록.csv의 RAISE 행과 사례 · 순서가 다릅니다(빠짐 {sorted(set(alarms) - set(got))}, 더함 {sorted(set(got) - set(alarms))}).')
    for it in events:
        iid = it.get('id'); cands = it.get('candidates') or []
        if md and not re.search(r'^#+\s.*(?<![A-Za-z0-9-])' + re.escape(str(iid)) + r'(?![A-Za-z0-9-])', md, re.M): errs.append(f'조치검토결과.md에 {iid}의 절 제목이 없습니다.')
        if [c.get('sop') for c in cands] != sops: errs.append(f'{iid}: 후보 목록 · 순서가 targets.csv와 다릅니다.')
        totals, ranked = {}, []
        for c in cands:
            at = f'{iid}/{c.get("sop")}'
            st = c.get('status')
            reasons = c.get('reasons') if isinstance(c.get('reasons'), list) else None
            errs += inputs_errors(at, c.get('inputs') or {}, c.get('missing_reasons'))
            if st not in ('유지', '제외', '보류'): errs.append(f'{at}: status는 유지 · 제외 · 보류 가운데 하나입니다.'); continue
            if reasons is None: errs.append(f'{at}: 이유 목록(reasons)이 필요합니다.'); continue
            for r in reasons:
                if (r.get('rule_id'), c.get('sop')) not in groups: errs.append(f'{at}: 기준 조건표에 없는 규칙 · 후보 {r.get("rule_id")}')
                if r.get('result') not in ('WARN', 'PENALTY', 'EXCLUDE', '미확인'): errs.append(f'{at} {r.get("rule_id")}: result는 WARN · PENALTY · EXCLUDE · 미확인 가운데 하나입니다.')
                if not r.get('expression') or not r.get('source') or not isinstance(r.get('actual_inputs'), dict): errs.append(f'{at} {r.get("rule_id")}: actual_inputs · expression · source가 필요합니다.')
                if r.get('result') == '미확인' and (not r.get('missing_inputs') or not r.get('missing_reason')): errs.append(f'{at} {r.get("rule_id")}: 미확인에는 missing_inputs와 missing_reason이 필요합니다.')
            kinds = [r.get('result') for r in reasons]
            want = '제외' if 'EXCLUDE' in kinds else ('보류' if '미확인' in kinds else '유지')
            if st != want: errs.append(f'{at}: 판정 {st}이 이유의 결과({", ".join(kinds) or "없음"})와 맞지 않습니다(뜻은 작업기준.md 4절).')
            if not c.get('sources'): errs.append(f'{at}: 원문 출처(sources)가 비었습니다.')
            checks = c.get('checks')
            if not isinstance(checks, list): errs.append(f'{at}: 추가로 확인할 값(checks) 목록이 필요합니다.'); checks = []
            for m in sorted({m for r in reasons if r.get('result') == '미확인' for m in r.get('missing_inputs') or []}):
                if not any(m in str(x) for x in checks): errs.append(f'{at}: 미확인 규칙의 빠진 입력 {m}이 추가로 확인할 값(checks)에 없습니다.')
            ap = c.get('approval') or {}
            if not ap.get('role') or not ap.get('source') or not ap.get('note'): errs.append(f'{at}: 승인(approval — role · source · note)이 필요합니다.')
            elif ap.get('role') != approver.get(c.get('sop')): errs.append(f'{at}: 승인 역할 {ap.get("role")}이 기준 sop.json의 {approver.get(c.get("sop"))}과 다릅니다.')
            value, rank = c.get('comparison'), c.get('rank')
            errs += kept_errors(at, st, value, c.get('no_comparison_reason'))
            if value is None and rank is not None: errs.append(f'{at}: 비교값이 없는 후보에 순위(rank)가 있습니다.')
            if st == '유지' and isinstance(value, dict):
                totals[c.get('sop')] = value.get('total'); ranked.append((c.get('sop'), rank, value.get('total')))
        errs += rank_errors(iid, ranked)
        op = it.get('review') or {}
        top = op.get('top') if isinstance(op.get('top'), list) else None
        if top is None: errs.append(f'{iid}: review.top 목록이 필요합니다(1위가 없으면 빈 목록).'); top = []
        for s in top:
            if s not in totals: errs.append(f'{iid}: review.top의 {s}는 비교값이 있는 유지 후보가 아닙니다.')
        if not op.get('reason'): errs.append(f'{iid}: review.reason이 필요합니다.')
        if not isinstance(op.get('checks'), list): errs.append(f'{iid}: review.checks 목록이 필요합니다(없으면 빈 목록).')
    return ('확인 필요' if errs else '통과'), errs, f'사례 {len(events)}건'
state, errs, note = check_review(root/'결과/조치검토결과.json', root/'결과/조치검토결과.md')
if state == '없음': print('아직 검사할 결과가 없습니다: 결과/조치검토결과.json')
print('구조 검사 결과')
ok = report([('조치검토결과.json · .md', state, errs, note, True), record_part(root/'결과/기대결과.md', '고른 것', '정한 것'),
             record_part(root/'결과/기대결과.md', '실제 결과', '사례 대조'), record_part(root/'결과/기대결과.md', '프로그램', '손계산 대조'),
             shape_part(root/'결과/기대결과.md')])
for line in expect_time(root/'결과/기대결과.md'): print('참고: ' + line)
print('구조 검사 통과' if ok else '구조 확인 필요 — 위 줄마다 결과의 어느 사례 · 후보인지 찾아 고친 뒤 다시 실행합니다.')
print('이 검사는 모양과 계약만 봅니다. 의미와 질문별 답(판정 · 이유 · 출처가 원문과 맞는지, 금액, 어느 후보가 1위인지)은 원자료와 따로 대조합니다.')
sys.exit(0 if ok else 1)
'''


def expect_template(extra=''):
    """판정 랩 결과/기대결과.md — 기대 칸을 실행 전에 원천 · 조건표 · 원문으로 적는 기록(전면 기법: 판정)."""
    return ('# 기대 결과와 실제 대조\n\n> 제공 빈 틀입니다. 보관하지 말고 바로 채웁니다.\n\n'
            '기대 칸은 프로그램을 실행하기 전에 원천 기록 · 조건표 · 원문으로 손으로 구해 적습니다. 실제 칸은 실행한 뒤에 적습니다. 실행 결과를 옮겨 기대 칸을 채우지 않습니다.\n\n'
            '- 기대 칸을 쓴 시각(실행 전, 내 PC 시계 그대로):\n- 실행한 명령과 실행 시각(내 PC 시계 그대로):\n\n'
            '## 목표와 질문\n\n## 이 답을 쓰는 사람과 쓰는 곳\n\n## 사용할 자료와 기준일\n\n## 지킬 조건\n\n'
            '## 정한 것\n\n| 지점(종류) | 고른 것 | 근거(파일 · 줄) | 이 선택으로 바뀌는 답 |\n|---|---|---|---|\n| | | | |\n\n'
            '## 판단 입력을 만든 방법\n\n| 입력 | 원천과 만든 방법 | 근거(파일 · 절) |\n|---|---|---|\n| | | |\n\n'
            '## 사례 대조\n\n| 사례 / 후보 | 사례 종류 | 원천 행과 판단 입력 | 기대 판정 · 이유(실행 전) | 근거(규칙 · 원문 절) | 실제 결과 | 같음 / 다른 까닭과 고친 점 |\n'
            '|---|---|---|---|---|---|---|\n| | | | | | | |\n\n'
            '## 손계산 대조\n\n| 사례 / 후보 | 지표 | 손계산 | 프로그램 | 같은가 |\n|---|---|---|---|---|\n| | | | | |\n\n'
            + extra + '## 저장 기록\n\n- 기준일:\n- 저장 시점:\n- 확인하지 못한 점:\n')


JUDGE_DECIDE = [('빈 값의 뜻', '정해진 주기로 남아야 할 기록이 빠져 판정을 요청한 때의 값을 기록에서 바로 읽을 수 없을 때, 끊긴 구간을 이어 판단 입력을 만들지 — '
                                '어느 원천의 어느 경보에 그런 구간이 있는지, 이을 근거가 원천에 있는지는 원천에서 찾습니다'),
                ('쓰는 사람에 따라 갈리는 답', '경고가 붙은 후보를 비교 산식으로 견주는 후보에 넣을지')]
WHY_SOURCE_INPUT = ('규칙은 판단 입력이 정해져야 판정할 수 있습니다. 판단 입력은 원천마다 기록 주기 · 단위 · 시각 표기가 다르고, 값이 비는 까닭도 원천마다 다릅니다. '
                    '판단할 때(판정을 요청한 시각)를 기준으로 그때까지의 기록만 써야 결과를 다시 만들 수 있고, 값이 없는 입력은 0이나 앞 값으로 채우지 않고 없는 까닭과 함께 남겨야 정보 부족을 가려낼 수 있습니다. '
                    '이 단계에서 파일을 바꾸지 않는 것은 원천을 어떻게 읽을지 정하기 전에 AI가 판단 입력을 만들어 버리지 않게 하려는 것입니다.')
WHY_EXPECT = ('판정 기능이 맞는지는 실행 결과만 봐서는 알 수 없습니다. 실행하기 전에 사례 종류마다 원천 줄 · 조건표 · 원문으로 기대를 먼저 적어 두어야, '
              '결과가 다를 때 프로그램이 틀렸는지 기대가 틀렸는지를 근거로 가릴 수 있습니다. AI가 낸 결과를 기대로 옮기면 틀린 결과도 맞아 보입니다.')
WHY_COMPARE = ('후보마다 비용 · 생산 · 품질 · 에너지처럼 서로 다른 성과가 함께 움직이므로, 한 가지 값으로 견주려면 주어진 산식이 필요합니다. '
               '어느 후보를 견줄지는 결과를 쓰는 사람의 일에 따라 달라질 수 있어 「정한 것」에 근거와 함께 남기고, 견주지 않은 후보는 그 까닭을 남깁니다. '
               '반올림은 끝에서 한 번만 해야 합계가 원값과 어긋나지 않습니다.')
WHY_SELECT = ('비교 합계는 후보를 견주는 계산이고 포털 성과 지표의 점수와 다른 값입니다. 1위를 고른 까닭과 아직 확인할 것을 함께 남겨야 결과를 읽는 사람이 근거를 따라갈 수 있고, '
              '그 1위도 실행 허가가 아닙니다 — 실행은 정해진 사람이 한 번 승인한 뒤에 합니다.')
WHY_OPINION = ('비교 합계는 후보를 견주는 계산이고 포털 성과 지표의 점수와 다른 값입니다. 검토 의견은 판정 · 비교 결과에서 나와야 '
               '같은 사례를 누가 다시 돌려도 같은 의견이 나오고, 담당자가 그 까닭을 따라갈 수 있습니다.')   # 승인 이야기는 다음 단계(승인 역할)에서 한 번
WHY_INPUT = ('판단 입력은 원천마다 기록 방식이 달라, 시각과 단위를 규칙에 맞춘 원값으로 만들고 값이 없는 입력은 0이나 앞 값으로 채우지 않고 까닭과 함께 남겨야 '
             '규칙이 무엇을 근거로 판정했는지 다시 따라갈 수 있습니다.')   # 일반 원리 한 문장(자료의 값-없음 종류를 나열하지 않는다)
DECISION_STEP = '이 단계의 결과는 내 결정에 따라 달라집니다. AI가 결정을 대신 정하려 하면 돌려보내고 내 선택과 근거를 다시 말합니다.'
WHY_HISTORY = ('사건 한 건이 맞아도 다른 경보에서 틀릴 수 있습니다. 경계값 · 모두 제외 · 값 누락처럼 결과가 갈리는 종류를 지난 경보 전체에서 골라 대조해야 '
               '기능을 다른 경보에도 쓸 수 있습니다. 결과에 맞추려고 기대를 바꾸면 대조가 아니게 됩니다.')


def judge_steps(review=False):
    """두 판정 랩의 앞 일곱 단계(같은 일 — 랩마다 결과 파일 이름만 다르다). review = 실전반(비교 기준 문장을 비교 단계의 결과로 — 통합반은 8단계)."""
    return [
        S('폴더와 출발점 확인', '시작',
          'VS Code 탐색기에서 이 폴더의 `입력/` · `자료/` · `결과/` · START.md를 열어 각 자리의 역할과 이번 질문을 확인합니다.',
          '이번 질문과, 이 답을 쓰는 사람이 누구인지 확인합니다.',
          '탐색기에서 네 자리를 찾았고, `입력/조건표.csv`가 규칙을, `자료/`의 원천 기록이 판단 입력을 담는다는 것을 파일에서 확인했습니다.',
          why=B.WHY_START,
          differ=B.DIFFER_START),
        S('파일을 바꾸지 않고 자료 파악', '① 파악',
          'AI에게 파일을 바꾸지 말고, 원천 네 개(경보 · PLC 상태 · 팬 카운터 · 예측)와 조건표 · 계약이 각각 무엇을 어떤 모양으로 담는지 파일 · 줄로 짚어 달라고 합니다. 짚은 줄을 직접 엽니다.',
          '원천마다 값이 비는 까닭이 몇 가지인지 묻습니다 — 칸이 빈 것뿐 아니라, 정해진 주기로 와야 할 기록이 오지 않은 곳(마지막 기록에서 판정 요청까지도)과 유효 시간이 지나 쓸 수 없는 값까지. '
          '원천마다 시각이 어떻게 적혔는지, 조건표가 규칙을 거는 조치와 함께 맞아야 하는 조건 묶음을 어떻게 적었는지도 묻습니다.',
          B.EVIDENCE_LOOK + ' 원천마다 기록 주기 · 단위 · 시각 표기 · 값이 비는 까닭을 내 말로 말할 수 있고, 판정 요청 직전 기록이 그 원천의 주기보다 오래된 경보 하나를 직접 열어 보았습니다.',
          H('판단 입력이 어디서 어떤 모양으로 오는지 파악한다. 아직 아무것도 만들지 않는다.',
            '`입력/` · `자료/` · `입출력_계약.md`',
            '파일을 바꾸지 않는다. 해석보다 파일 · 줄 번호를 먼저 받는다.',
            '원천마다 기록 주기 · 단위 · 시각 표기 · 값이 비는 까닭 표(칸이 빔, 와야 할 기록이 오지 않음, 유효 시간이 지남을 나눠)와 조건표 요약',
            '원천마다 두세 줄을 내가 직접 열어 같은 내용인지 본다'),
          why=WHY_SOURCE_INPUT, differ=B.DIFFER_LOOK),
        S('기대 결과 먼저 적기', '② 요구',
          '`결과/기대결과.md`에 목표 · 쓰는 사람 · 지킬 조건과, 사건의 네 후보와 「확인」의 사례 종류마다 하나 이상을 원천 줄 · 조건표 · 원문으로 손으로 구한 기대 판정과 근거로 편집기에서 먼저 적습니다. '
          '사례 종류에 맞는 경보는 AI에게 판정 · 순위를 빼고 위치와 사실(파일 · 줄)만 뽑게 해 고르고, 기대 판정은 그 줄을 열어 내가 구합니다. '
          '「학생이 정할 것」의 지점마다 고른 것과 근거를 적고, 다 쓰면 「기대 칸을 쓴 시각」을 적습니다.' + B.REQ_AFTER,
          B.ASK_DECIDE + DECIDE_FIRM,
          '사례 종류마다 기대 판정과 근거 줄이 있고, 「정한 것」 표의 지점마다 고른 것 · 근거 · 바뀌는 답이 채워져 있거나 미결로 적혀 있습니다. 「기대 칸을 쓴 시각」이 실행보다 앞입니다. '
          'AI의 되짚기가 내 요구와 같고, 편집 승인 창이 뜨지 않았으며 AI의 답에 바꾼 파일이 없습니다.',
          H('사례를 고를 사실을 찾게 하고, 내가 적은 기대를 AI가 같은 뜻으로 이해했는지 되짚게 한다',
            '2단계에서 연 원천 줄, `입력/조건표.csv`, 원문, 내가 채운 `결과/기대결과.md`',
            '파일을 바꾸지 않는다 — `기대결과.md`는 내가 편집기에서 채운다. AI에게는 사례의 위치 · 사실(파일 · 줄)만 찾게 하고 판정 · 순위는 묻지 않는다. AI의 출력을 기대로 옮기지 않는다. 「학생이 정할 것」은 내가 고른다.',
            '사례 종류마다 해당하는 경보의 위치 · 사실 목록과, 내가 채운 「정한 것」 · 「사례 대조」 기대 칸을 AI가 자기 말로 다시 말한 것',
            '고른 경보의 줄을 내가 직접 열어 보고, 되짚기가 내 뜻과 다른 곳을 내가 편집기에서 고친다'),
          why=WHY_EXPECT, differ=B.DIFFER_REQ.format(rec='결과/기대결과.md')),
        S('계획 검토', '③ 계획',
          '판단 입력 만들기 · 판정 · 비교와 그 뒤의 결과 쓰기를 어떤 순서의 기능으로 나눠 만들지 AI의 계획으로 받아 검토하고 동의합니다. 아직 파일을 만들지 않습니다.',
          '판정에서 정보 부족(보류)을 어떤 경우에 내는지가 내 기대와 같은지 묻습니다.' + DECIDE_FIRM_AGAIN,
          '사건 한 건을 계획에 대어 어느 기능이 무엇을 내는지 짚을 수 있습니다. 계획에 규칙을 코드에 다시 적는 부분과 「이번 범위 밖」의 일이 없습니다. 계획에 내가 동의했습니다.',
          H('구현 순서와 기능의 경계를 합의한다',
            '`입출력_계약.md`, `결과/기대결과.md`',
            '규칙은 조건표에서 읽는다(코드에 다시 적지 않는다). 「이번 범위 밖」은 넣지 않는다.',
            '기능 목록과 구현 순서',
            '사건 한 건을 계획에 대어 기능마다 무엇이 나오는지 짚게 한다'),
          why='판단 입력 · 판정 · 비교를 한 번에 만들면 결과가 다를 때 어느 부분이 틀렸는지 찾기 어렵습니다. 기능을 나눠 하나씩 만들고 확인해야 다른 줄의 원인을 한 곳으로 좁힐 수 있습니다.',
          differ=B.DIFFER_PLAN),
        S('구현 ① 판단 입력 만들기', '④ ~ ⑥ 구현 · 대조 · 고침',
          '사례 · 후보마다 계약의 판단 입력 일곱 개와 값이 없는 까닭을 원천에서 만드는 기능을 `결과/`에 만들고 실행해, 사건과 사례 몇 개의 입력을 원천 줄과 직접 견줍니다.' + B.OWN_RUN,
          '원천을 읽는 방법이 내 기대와 다를 때 어느 쪽이 원천의 기록 방식(`자료/수집_설명.md`)과 맞는지 근거를 묻습니다. 「정한 것」의 빈 값 지점이 걸린 입력이 내 결정대로 만들어졌는지 묻습니다. ' + DECISION_STEP,
          '사건 네 후보의 입력이 기대와 같고, 값이 없는 입력마다 까닭이 원천의 사정과 맞습니다. 「정한 것」의 빈 값 지점이 걸린 사례에서 그 입력이 내 결정대로입니다. 바뀐 파일이 `결과/` 아래뿐입니다' + B.PYCACHE + '.',
          H('사례 · 후보마다 판단 입력과 값이 없는 까닭을 만든다',
            '원천 네 개, `자료/수집_설명.md`, `자료/targets.csv`, ' + DECIDE_INPUT,
            '판정을 요청한 시각 뒤의 기록은 쓰지 않는다. 시각과 단위를 맞춘 원값으로 견준다. 빈 값을 0이나 앞 값으로 채우지 않는다. 「정한 것」의 빈 값 지점은 내 결정대로 만든다.',
            '사례 · 후보마다 입력 일곱 개와 값이 없는 까닭(계약의 판단 입력 `inputs` · 값이 없는 까닭 `missing_reasons` 꼴), 판단 입력을 만든 방법과 「정한 것」을 적는 정한 것(`decisions`)',
            '사건과 사례 두세 개의 입력을 원천 줄과 직접 견준다'),
          'python 결과/<만든 코드 이름>.py',
          why=WHY_INPUT,
          differ=B.FIX_LOOP),
        S('구현 ② 조건표로 판정', '④ ~ ⑥ 구현 · 대조 · 고침',
          '조건표를 읽어 후보마다 경고 · 감점 · 제외와 정보 부족을 이유와 함께 내는 기능을 더하고 실행해, 기대결과의 판정과 줄마다 견줍니다.',
          '규칙이 걸리지 않는 후보와, 입력이 없어 맞는지 알 수 없는 규칙을 어떻게 구별해 남기는지 묻습니다.',
          '사건 네 후보의 판정과 이유가 기대와 같거나, 다른 까닭이 `기대결과.md`에 있습니다.',
          H('경고 · 감점 · 제외 · 정보 부족을 이유와 함께 낸다',
            '`입력/조건표.csv`, 5단계에서 만든 판단 입력',
            '조건표를 읽어서만 판정한다. 같은 규칙의 감점은 한 번만 반영한다.',
            '후보 판정(계약의 판정 · 맞은 규칙 · 알 수 없는 규칙 꼴)',
            '기대결과의 판정과 후보마다 견준다'),
          'python 결과/<만든 코드 이름>.py',
          why=WHY_HIT_READ + ' ' + WHY_UNKNOWN, differ=B.FIX_LOOP),
        S('구현 ③ 비교 계산', '④ ~ ⑥ 구현 · 대조 · 고침',
          '견줄 후보를 `자료/metrics/지표_정의.md`의 식으로 네 손실과 감점을 더해 견주고 순위를 매기는 기능을 더합니다. 견주지 않은 유지 후보는 그 까닭을 남깁니다.',
          '「정한 것」의 경고 후보 지점대로 견줄 후보가 정해지는지, 견줄 수 없는 후보를 무엇으로 남길지 묻습니다. ' + DECISION_STEP,
          '`지표_정의.md` 손계산 예의 네 손실이 프로그램 값과 같습니다. 순위에는 비교값이 있는 후보만 있고, 견주지 않은 유지 후보마다 까닭이 있습니다.',
          H('견줄 후보의 비교 합계와 순위를 낸다',
            '`자료/metrics/` 세 파일, `자료/오더_현황.csv`, 예측 입력, 6단계 판정, ' + DECIDE_INPUT,
            '산식을 바꾸지 않는다. 반올림은 끝에서만, 계약의 반올림 규칙대로 한다.',
            ('비교값(`comparison`) · 순위(`ranking`) · 비교값이 없는 까닭(`no_comparison_reason`)과 비교 기준 문장(`comparison_basis` — 이 합계가 무엇을 견주는지, '
             '`지표_정의.md`의 포털 성과 지표 점수와 어떻게 다른지) — 계약 꼴' if review else
             '비교값(`comparison`) · 순위(`ranking`) · 비교값이 없는 까닭(`no_comparison_reason`) — 계약 꼴'),
            '손계산 예와 같은지 보고, 사건의 한 후보를 손으로 다시 계산해 견준다'),
          'python 결과/<만든 코드 이름>.py',
          why=WHY_COMPARE, differ=B.FIX_LOOP),
    ]


def judge_lab(files):
    """통합반 03회차 실습3 — 설비 조건별 최적의 조치를 비교하는 판단 기능 만들기(구성안 5.3)."""
    title = TITLES['integrated-03-judge']
    rec = '결과/기대결과.md'
    when = incident_time(files)
    n = sum(1 for r in csv.DictReader(io.StringIO(files['경보_목록.csv'])) if r['구분'] == 'RAISE' and r['판정_요청_시각'])
    save = ('`결과/result.json` · `결과/기대결과.md`와 만든 코드를 함께 보관합니다. 다음 실습에 넘길 것은 이 결과와, 받은 그대로의 `입력/조건표.csv` · `입력/sop.json`입니다. '
            '다음 실습 「문서에서 근거 있는 지식을 추출하는 기능 만들기」에서는 조건의 원문 근거를 검토합니다. ' + USB)
    steps = judge_steps() + [
        S('구현 ④ 선택 이유와 비교 기준', '④ ~ ⑥ 구현 · 대조 · 고침',
          '사례마다 1위를 고른 까닭(순위가 없으면 그 까닭)과 추가로 확인할 사항, 비교 기준 문장을 `결과/result.json`에 쓰는 기능을 더하고 실행합니다.',
          '사건의 선택 이유가 판정 · 비교 결과와 「정한 것」에서 나오는지, 추가로 확인할 사항이 빠진 입력 · 경고에서 나오는지 묻습니다.',
          '사건의 선택 이유가 순위 · 견주지 않은 후보 · 보류 후보와 맞습니다. 비교 기준 문장(`comparison_basis`)에 비교 합계와 포털 성과 지표 점수의 차이가 적혀 있습니다.',
          H('사례마다 선택 이유와 추가로 확인할 사항을 남긴다',
            '판정 · 비교 결과, ' + DECIDE_INPUT + ', `자료/metrics/지표_정의.md` 「포털의 성과 지표 점수」',
            '1위를 실행 승인처럼 쓰지 않는다',
            '계약의 선택 이유(`selection` — `reason` · `checks`)와 비교 기준 문장(`comparison_basis`)',
            '사건의 선택 이유를 순위와 원천 줄로 내 말로 따라가 본다'),
          'python 결과/<만든 코드 이름>.py',
          why=WHY_SELECT, differ=B.FIX_LOOP),
        S('이력 전체 대조', '⑤ 대조',
          '`결과/result.json`을 `기대결과.md`의 사례 종류마다 견주어 실제 칸을 채우고, 다른 줄은 원인이 판단 입력 · 판정 · 산식 가운데 어디인지 적습니다.',
          '다른 줄의 원인이 판단 입력 · 판정 · 산식 가운데 어디인지 묻습니다.',
          '사례 종류마다 기대와 실제가 나란히 있고, 다른 줄마다 원인이 적혀 있습니다.',
          H('사례 종류마다 기대와 실제를 견준다',
            '`결과/result.json`, `결과/기대결과.md`',
            '결과에 맞추려고 기대를 바꾸지 않는다. 기대를 고치면 근거를 남긴다.',
            '`기대결과.md` 「사례 대조」의 실제 칸과 다른 까닭',
            '종류마다 한 사례는 내가 원천 줄에서 다시 손으로 구해 본다'),
          why=WHY_HISTORY,
          differ='다른 줄이 있으면 그 사례의 원천 줄 · 판단 입력 · 맞은 규칙 · 비교 값을 나란히 놓고 어느 단계에서 갈렸는지 찾아, 그 기능만 고친 뒤 이미 맞았던 사례까지 다시 실행합니다.'),
        S('구조 검사와 고치기', '⑤ ⑥ 대조 · 고침',
          '터미널에서 구조 검사를 실행하고, 검사와 9단계가 짚은 문제를 고친 뒤 9단계 대조를 다시 합니다.',
          '검사와 9단계가 짚은 문제가 결과의 어느 사례 · 후보인지 묻습니다.',
          '「구조 검사 통과」 줄이 나오고, 9단계의 다른 줄이 없거나 남은 까닭이 `기대결과.md`에 있습니다.',
          H('구조 · 대조 문제를 고친다', '`python check.py`의 출력, 9단계 표', '검사 기준 · 원자료 · 기대를 바꾸지 않는다', '고친 파일 목록과 다시 실행한 출력', '고친 뒤 9단계 대조를 다시 한다'),
          'python check.py',
          why='구조 검사는 사례 수 · 후보 순서 · 판정과 이유의 짝 · 합계와 성분의 합 · 순위처럼 모양과 계약만 봅니다. 어떤 규칙이 맞아야 하는지, 어느 후보가 1위여야 하는지는 검사가 모르므로 9단계의 대조로 판단합니다.',
          differ=DIFFER_CHECK),
        S('저장하고 다시 열기', '⑦ 저장 · 다시 열기',
          '결과 파일을 모두 저장하고 VS Code에서 폴더를 닫았다 다시 연 뒤 만든 코드와 구조 검사를 다시 실행합니다. `기대결과.md` 끝에 기준일 · 저장 시점 · 확인하지 못한 점을 적습니다.',
          '확인하지 못한 점으로 무엇을 남길지 정합니다.',
          '다시 연 뒤에도 같은 출력이 나옵니다. `결과/`에 `result.json` · `기대결과.md`와 만든 코드가 있습니다.',
          cmd='python 결과/<만든 코드 이름>.py\npython check.py', why=B.WHY_SAVE, differ=B.DIFFER_SAVE),
    ]
    formats = ['## 결과 형식\n\n파일의 모양은 `입출력_계약.md`에 있습니다. 판단 입력을 어떻게 만들고 어느 후보를 견줄지는 원천과 원문을 읽고 직접 정합니다.\n\n'
               '- `결과/result.json` — 사례마다 후보 판정 · 비교 · 순위와 선택 이유(계약 「결과」).\n'
               '- `결과/기대결과.md` — 「제공 빈 틀」의 칸대로 채웁니다.\n'
               '- 만든 코드는 `결과/` 아래에 두고, 이름은 하는 일로 짓습니다.\n\n'
               '## 지킬 조건\n\n'
               '- `입력/`은 읽기만 합니다.\n'
               '- 규칙은 코드에 다시 적지 않고 `입력/조건표.csv`에서 읽습니다.\n'
               '- 비교 순위와 선택 이유를 실행 승인처럼 적지 않습니다.\n'
               '- 만든 코드는 내가 손으로 쓰는 `결과/기대결과.md`를 읽지 않습니다 — 「정한 것」은 요청에서 전합니다.\n']
    return dict(
        title=title, rec=rec, readonly='`입력/` · `자료/`가', decide_step=2, course='통합반',
        goal=[f'포털에서 운전 모드와 설비 상태를 바꿔 판단을 다시 돌리고, 조건별 손익에서 순위가 바뀌는 것을 봤습니다. 포털은 사실을 자동으로 모아 한 건씩 판단했습니다. '
              f'이번에는 같은 일을 원천 기록에서 직접 하고, 지난 30일 경보 전체로 기능을 검증합니다. 사건은 포털에서 본 경보와 같은 종류의 다른 경보 한 건, 10월 27일 {when} HYD-02 쿨러 성능 저하 경보입니다.',
              '판정 기능은 조건표를 읽어 후보마다 경고 · 감점 · 제외와, 입력이 없어 맞는지 알 수 없는 정보 부족을 이유와 함께 내고, 허용 후보만 주어진 비교 산식으로 견줍니다. '
              '규칙을 코드에 다시 적지 않고 조건표에서 읽어야 기준이 바뀌어도 코드를 고치지 않습니다.',
              f'판단 입력은 정리된 표가 아니라 원천 네 곳(경보 · PLC 상태 · 팬 카운터 · 예측)에 흩어져 있고, 원천마다 기록 주기 · 단위 · 시각 표기 · 값이 비는 까닭이 다릅니다. '
              f'경보 {n}건마다 후보가 넷이라 손으로 다 맞출 수 없으므로 코드로 만들고, 대표 사례는 손으로 구한 기대와 대조합니다.',
              B.STAGE_LINE.format(what='판단 지식 — 조건표를 읽어 조치를 판정하고 견주는 일 — ')],
        make='만들 것: `결과/result.json`(사례마다 후보 판정 · 비교 · 순위와 선택 이유), `결과/기대결과.md`, 판단 입력을 만들고 판정 · 비교하는 코드.',
        start=['`입력/조건표.csv` · `입력/sop.json` — 냉각 계통 조치의 조건표와 SOP 구조. 조치 기준을 만드는 실습의 결과와 같은 꼴로 검증해 제공하는 판입니다.',
               MINE['integrated-03-judge'],
               '`자료/경보_목록.csv` · `자료/PLC_상태_수신.csv` · `자료/팬_운전_카운터.csv` · `자료/예측_결과.csv` — 판단 입력의 원천 네 개(HYD-01 ~ 03, 2026-09-28 ~ 10-27). 기록 방식은 `자료/수집_설명.md`에 있습니다.',
               '`자료/오더_현황.csv` · `자료/metrics/` — 주어진 비교 산식(`지표_정의.md`)과 그 값.',
               '`자료/HM-8_매뉴얼.md` · `자료/HI-01_보충매뉴얼.md` · `자료/작업기준.md` — 조치 원문 · 보충 기준 · 회사 작업 기준. `자료/targets.csv` — 경보마다 검토하는 조치 후보 넷.',
               '`입출력_계약.md` — 입력과 결과 파일의 형식. `check.py` — 결과의 구조 검사.',
               '`결과/` — 이번에 만든 것을 두는 자리. 「제공 빈 틀」 `기대결과.md`가 있습니다.',
               RULES_LINE],
        user='이 답은 야간 운전원이 경보가 났을 때 네 후보를 쓸 수 있는지, 견준 후보 가운데 무엇이 1위이고 왜인지, 아직 무엇을 확인해야 하는지 볼 때 씁니다.',
        questions=['사건의 네 후보 — 판단 입력(원천 네 개, 판정을 요청한 시각 기준) · 판정(유지 · 제외 · 보류와 이유) · 비교값과 순위는 무엇인가?',
                   '같은 기능이 지난 경보의 정상 · 경계 · 복수 조건 · 모두 제외 · 필수값 누락 사례에서 기대와 같은가?',
                   '사건에서 1위는 무엇이고 그 까닭과 추가로 확인할 사항은 무엇인가? 이 비교값은 포털 성과 지표의 점수와 어떻게 다른가?'],
        decide=JUDGE_DECIDE,
        outside=['조건표 · SOP 구조를 고치는 일(입력은 읽기만 합니다)', '조건이 원문 어디에서 왔는지 다시 검토하는 일(다음 실습)',
                 '비교 산식을 바꾸는 일', '실제 설비 조작과 실행 승인'],
        formats=formats, steps=steps,
        cases=['규칙이 하나도 맞지 않는 후보(정상)',
               '조건표의 숫자 기준값마다(예측 유온 · 팬 연속 시간 등) 그 값과 같은 후보와, 그 값의 바로 위 · 아래에서 가장 가까운 후보(경계 — 단위가 다른 원천 포함)',
               '경고 · 감점 · 제외가 한 후보에 함께 맞는 경우(복수 조건 — 감점이 규칙마다 한 번인지)',
               '모든 후보가 제외된 경보',
               '원천에서 값이 비는 까닭이 서로 다른 경보(필수값 누락 — 그 값이 필요한 규칙에만 영향이 가는지)',
               '「정할 것」의 결정에 따라 판단 입력 · 순위가 바뀌는 경보',
               '`자료/metrics/지표_정의.md`의 손계산 예',
               '같은 코드를 다시 실행한 결과'],
        commands='python 결과/<만든 코드 이름>.py\npython check.py',
        done=('형식 검사나 실행 성공만으로 완료하지 않습니다. 사례 종류마다 실행 전에 원천 · 조건표 · 원문으로 적은 기대와 실행 결과가 같거나, 다른 까닭을 찾아 고친 기록이 있고, '
              '손계산 예의 네 손실이 프로그램 값과 같으며, 「정한 것」의 근거와 그 선택으로 바뀌는 판단 입력 · 순위를 설명할 수 있으면 완료입니다.'),
        save=save, reopen='만든 코드와 구조 검사의 출력, `기대결과.md`의 사례 대조와 기준일 · 저장 시점 · 확인하지 못한 점',
        tree=tree('03일차_실습3_판단기능만들기', [('.github/', 'Copilot 작업 규칙'), ('결과/', '이번에 만들 것(기대결과.md 빈 틀)'),
                                            ('입력/', '조건표와 SOP 구조(읽기만)'), ('자료/', '판단 입력의 원천 · 비교 산식 · 원문(읽기만)'),
                                            ('AGENTS.md', 'Codex 작업 규칙'), ('check.py', '구조 검사'), ('CLAUDE.md', '작업 규칙(같은 내용)'), ('guide.html', '이 가이드'),
                                            ('START.md', '이번 과제와 진행 단계'), ('안내.html', '이 가이드와 같은 파일'), ('입출력_계약.md', '입력과 결과 파일의 형식')]),
        lead='원천 기록에서 판단 입력을 만들고, 조건표로 후보를 판정하고, 주어진 비교 산식으로 견주어 사건의 순위와 선택 이유를 낸 뒤, 지난 30일 경보 전체로 대조합니다.',
        need='VS Code와 Python, 로그인해 둔 Codex 또는 GitHub Copilot.',
        terms=JUDGE_TERMS + ' ' + CONTRACT_TERM,
        first_more=[MINE['integrated-03-judge']],
        guide_extra={1: ['ai', 'review'], 4: ['terminal']}, guide_after={4: [STUCK_PATH], 9: [stuck_no_result('result.json')]}, files={
            'check.py': JUDGE_CHECK,
            '입출력_계약.md': '# 입출력 계약\n\n입력과 결과 파일의 형식과 뜻만 정한다. 판정 원칙은 원문(`자료/HM-8_매뉴얼.md` · `자료/작업기준.md` · `자료/HI-01_보충매뉴얼.md`), 원천의 기록 방식은 `자료/수집_설명.md`에 있다.\n\n'
                             + JUDGE_INPUT_CONTRACT + judge_table_contract() + '\n' + JUDGE_RESULT,
            '결과/기대결과.md': expect_template(),
            '결과/README.md': '이번 과제의 판정 결과(result.json) · 기대결과.md와 만든 코드를 여기에 저장합니다.\n다시 열 때는 기대결과.md의 기준일 · 저장 시점과, 만든 코드 · 구조 검사의 출력을 함께 봅니다.\n',
            '입력/README.md': '냉각 계통 조치의 조건표(조건표.csv)와 SOP 구조(sop.json)입니다. 조건표의 형식은 입출력_계약.md에 있습니다. 이 폴더는 읽기만 합니다.\n\n' + SOP_KEYS,
        })


def review_lab(files):
    """실전반 03회차 실습2 — 판정·성과 비교를 조치 검토 결과로 완성하기(구성안 5.4)."""
    title = TITLES['practical-03-review']
    rec = '결과/기대결과.md'
    when = incident_time(files)
    n = sum(1 for r in csv.DictReader(io.StringIO(files['경보_목록.csv'])) if r['구분'] == 'RAISE' and r['판정_요청_시각'])
    save = ('`결과/조치검토결과.json` · `결과/조치검토결과.md` · `결과/기대결과.md`와 만든 코드를 함께 보관합니다. 다음 실습에 넘길 것은 이 검토 결과와, 받은 그대로의 `입력/조건표.csv` · `입력/sop.json`입니다. '
            '다음 실습은 「문서에서 작업 조건과 근거를 추출하는 기능 만들기」입니다. ' + USB)
    steps = judge_steps(review=True) + [
        S('구현 ④ 후보별 추가로 확인할 값', '④ ~ ⑥ 구현 · 대조 · 고침',
          '후보마다 담당자가 먼저 확인할 값 — 판정을 막은 빠진 입력과 그 원천 — 을 추가로 확인할 값(`checks`)에 쓰는 기능을 더하고 실행합니다.',
          '알 수 없는 규칙마다 어떤 입력을 어디서 다시 받아야 하는지 묻습니다.',
          '알 수 없는 규칙마다 빠진 입력 · 원천이 `checks`에 있고, 사건의 보류 후보에 적힌 값이 원천에서 빠진 행 · 기록과 같습니다.',
          H('담당자가 먼저 확인할 값을 후보마다 남긴다',
            '판정의 알 수 없는 규칙, `자료/수집_설명.md`',
            '빠진 입력만 적는다. 값을 짐작해 채우지 않는다.',
            '계약의 추가로 확인할 값(`checks`)',
            '사건의 보류 후보에 적힌 값을 원천의 빠진 행 · 기록과 견준다'),
          'python 결과/<만든 코드 이름>.py',
          why='정보 부족은 「안 된다」가 아니라 「아직 모른다」입니다. 무엇이 빠졌고 어디서 다시 받으면 되는지 적어 두어야 담당자가 판정을 끝낼 수 있습니다.',
          differ=B.FIX_LOOP),
        S('구현 ⑤ 검토 의견', '④ ~ ⑥ 구현 · 대조 · 고침',
          '사례마다 승인 요청을 검토할 1위 후보와 그 까닭, 담당자가 먼저 확인할 값을 검토 의견(`review`)에 쓰는 기능을 더하고 실행합니다.',
          '사건의 검토 의견이 판정 · 비교 결과에서 나오는지, 먼저 확인할 값이 보류 후보의 빠진 입력과 같은지 묻습니다.',
          '사건의 검토 의견과 까닭이 순위 · 견주지 않은 후보 · 보류 후보와 맞고, 먼저 확인할 값이 보류 후보의 빠진 입력과 같습니다.',
          H('사례마다 검토 의견을 남긴다',
            '비교 · 추가 확인 결과, ' + DECIDE_INPUT,
            '순위를 실행 승인처럼 쓰지 않는다',
            '계약의 검토 의견(`review` — `top` · `reason` · `checks`)',
            '사건의 검토 의견을 순위와 원천 줄로 내 말로 따라가 본다'),
          'python 결과/<만든 코드 이름>.py',
          why=WHY_OPINION, differ=B.FIX_LOOP),
        S('구현 ⑥ 승인 역할과 실행 전 확인', '④ ~ ⑥ 구현 · 대조 · 고침',
          '후보마다 누가 승인하는지와 그 출처, 실행 전에 확인할 조건 · 완료 기준을 `입력/sop.json`에서 가져와 쓰는 기능을 더하고 실행합니다.',
          '후보마다 승인 역할과 실행 전 확인의 원문 출처가 어디인지 묻습니다.',
          '후보마다 승인(`approval`)의 역할이 `입력/sop.json`과 같고 출처가 원문 절로 돌아갑니다.',
          H('누가 승인하고 무엇을 확인한 뒤 실행하는지 남긴다',
            '`입력/sop.json`',
            '승인과 실행 전 확인은 SOP 원문 출처로만 적는다',
            '계약의 후보별 승인(`approval`)과 추가로 확인할 값(`checks`)의 실행 전 확인',
            '사건의 후보마다 승인 줄을 원문에서 직접 연다'),
          'python 결과/<만든 코드 이름>.py',
          why='판정과 비교는 「쓸 수 있는가」와 「무엇이 나은가」를 말할 뿐, 실행해도 된다는 허락이 아닙니다. 실행은 정해진 사람이 한 번 승인한 뒤에 하므로, 누가 승인하는지와 무엇을 확인한 뒤 실행하는지를 원문에서 함께 보여 줍니다.',
          differ=B.FIX_LOOP),
        S('구현 ⑦ 사람이 읽는 검토 결과', '④ ~ ⑥ 구현 · 대조 · 고침',
          '`조치검토결과.json`을 사례마다 절로 나눈 `결과/조치검토결과.md`로 쓰는 기능을 더하고 실행합니다.',
          '사건의 절만 읽고 다음 행동을 말할 수 있는지 묻습니다.',
          '사건의 절만 읽고 후보마다 판정 · 까닭 · 원문 출처 · 승인 역할과, 먼저 확인할 값을 말할 수 있습니다.',
          H('담당자가 읽고 결정할 수 있게 쓴다',
            '`결과/조치검토결과.json`',
            'JSON에 없는 내용을 더하지 않는다. 빈 목록 · null 같은 JSON 표기는 「없음」처럼 사람이 읽는 말로 바꿔 쓴다.',
            '`결과/조치검토결과.md`(사례마다 절, 절 제목에 경보 ID — 후보마다 판정 · 까닭 · 원문 출처 · 추가로 확인할 값 · 승인 역할)',
            '사건의 절만 읽고 다음 행동과 먼저 확인할 값을 말해 본다'),
          'python 결과/<만든 코드 이름>.py',
          why='검토 결과는 담당자가 읽고 결정하는 데 씁니다. 같은 내용을 사람이 읽는 글로 옮길 때 JSON에 없는 말을 더하면 근거 없는 판단이 섞입니다.',
          differ=B.FIX_LOOP),
        S('사례 대조', '⑤ 대조',
          '결과를 `기대결과.md`의 사례 종류(경계 · 제외 사유와 누락이 겹친 입력 · 모두 제외)마다 견주어 실제 칸을 채우고, 다른 줄은 원인이 판단 입력 · 판정 · 산식 가운데 어디인지 적습니다.',
          '다른 줄의 원인이 판단 입력 · 판정 · 산식 가운데 어디인지 묻습니다.',
          '사례 종류마다 기대와 실제가 나란히 있고, 다른 줄마다 원인이 적혀 있습니다.',
          H('사례 종류마다 기대와 실제를 견준다',
            '`결과/조치검토결과.json`, `결과/기대결과.md`',
            '결과에 맞추려고 기대를 바꾸지 않는다. 기대를 고치면 근거를 남긴다.',
            '`기대결과.md` 「사례 대조」의 실제 칸과 다른 까닭',
            '종류마다 한 사례는 내가 원천 줄에서 다시 손으로 구해 본다'),
          why=WHY_HISTORY,
          differ='다른 줄이 있으면 그 사례의 원천 줄 · 판단 입력 · 맞은 규칙 · 비교 값을 나란히 놓고 어느 단계에서 갈렸는지 찾아, 그 기능만 고친 뒤 이미 맞았던 사례까지 다시 실행합니다.'),
        S('구조 검사와 고치기', '⑤ ⑥ 대조 · 고침',
          '터미널에서 구조 검사를 실행하고, 검사와 12단계가 짚은 문제를 고친 뒤 12단계 대조를 다시 합니다.',
          '검사와 12단계가 짚은 문제가 결과의 어느 사례 · 후보인지 묻습니다.',
          '「구조 검사 통과」 줄이 나오고, 12단계의 다른 줄이 없거나 남은 까닭이 `기대결과.md`에 있습니다.',
          H('구조 · 대조 문제를 고친다', '`python check.py`의 출력, 12단계 표', '검사 기준 · 원자료 · 기대를 바꾸지 않는다', '고친 파일 목록과 다시 실행한 출력', '고친 뒤 12단계 대조를 다시 한다'),
          'python check.py',
          why='구조 검사는 사례 수 · 판정과 이유의 짝 · 추가로 확인할 값 · 승인 역할 · 합계와 순위처럼 모양과 계약만 봅니다. 판정과 1위가 맞는지는 검사가 모르므로 12단계의 대조로 판단합니다.',
          differ=DIFFER_CHECK),
        S('저장하고 다시 열기', '⑦ 저장 · 다시 열기',
          '결과 파일을 모두 저장하고 VS Code에서 폴더를 닫았다 다시 연 뒤 만든 코드와 구조 검사를 다시 실행합니다. `기대결과.md` 끝에 기준일 · 저장 시점 · 확인하지 못한 점을 적습니다.',
          '확인하지 못한 점으로 무엇을 남길지 정합니다.',
          '다시 연 뒤에도 같은 출력이 나옵니다. `결과/`에 `조치검토결과.json` · `조치검토결과.md` · `기대결과.md`와 만든 코드가 있습니다.',
          cmd='python 결과/<만든 코드 이름>.py\npython check.py', why=B.WHY_SAVE, differ=B.DIFFER_SAVE),
    ]
    formats = ['## 결과 형식\n\n파일의 모양은 `입출력_계약.md`에 있습니다. 판단 입력을 어떻게 만들고 어느 후보를 견줄지는 원천과 원문을 읽고 직접 정합니다.\n\n'
               '- `결과/조치검토결과.json` — 사례마다 후보별 판정 · 이유 · 원문 출처 · 추가로 확인할 값 · 비교 · 승인과 검토 의견(계약 「결과」).\n'
               '- `결과/조치검토결과.md` — 같은 내용을 사람이 읽는 글로, 사례마다 절.\n'
               '- `결과/기대결과.md` — 「제공 빈 틀」의 칸대로 채웁니다.\n'
               '- 만든 코드는 `결과/` 아래에 두고, 이름은 하는 일로 짓습니다.\n\n'
               '## 지킬 조건\n\n'
               '- `입력/`은 읽기만 합니다.\n'
               '- 규칙은 코드에 다시 적지 않고 `입력/조건표.csv`에서 읽습니다.\n'
               '- 비교 순위와 검토 의견을 실행 승인처럼 적지 않습니다. 승인 역할은 `입력/sop.json`의 원문 출처로 적습니다.\n'
               '- 만든 코드는 내가 손으로 쓰는 `결과/기대결과.md`를 읽지 않습니다 — 「정한 것」은 요청에서 전합니다.\n']
    return dict(
        title=title, rec=rec, readonly='`입력/` · `자료/`가', decide_step=2, course='실전반',
        goal=[f'포털에서 순위가 높아도 금지 조건에 걸리면 고를 수 없는 이유를 결과에서 찾았습니다. 이번에는 조치 조건표로 사건과 지난 30일 경보를 원천 기록에서 직접 판정하고, '
              f'담당자가 읽고 바로 결정할 수 있는 조치 검토 결과로 완성합니다. 사건은 포털에서 본 경보와 같은 종류의 다른 경보 한 건, 10월 27일 {when} HYD-02 쿨러 성능 저하 경보입니다.',
              '조치 검토 결과는 후보마다 판정과 그 이유 · 원문 출처 · 추가로 확인할 값 · 승인 역할을 담고, 허용 후보만 주어진 비교 산식으로 견준 순위와, 사례마다 승인 요청을 검토할 후보와 그 까닭을 적은 검토 의견을 담습니다. '
              '판단 입력은 원천 네 곳(경보 · PLC 상태 · 팬 카운터 · 예측)에 흩어져 있고 원천마다 기록 주기 · 단위 · 시각 표기 · 값이 비는 까닭이 다릅니다.',
              f'경보 {n}건마다 후보가 넷이라 손으로 다 맞출 수 없으므로 코드로 만들고, 대표 사례는 손으로 구한 기대와 대조합니다.',
              B.STAGE_LINE.format(what='판단 지식 — 조건표로 조치를 판정하고 견주어 담당자가 쓸 검토 결과로 내는 일 — ')],
        make='만들 것: `결과/조치검토결과.json` · `결과/조치검토결과.md`, `결과/기대결과.md`, 판단 입력을 만들고 판정 · 비교 · 검토 결과를 쓰는 코드.',
        start=['`입력/조건표.csv` — 냉각 계통 조치의 조치 조건표. 조치 조건표를 만드는 실습의 결과와 같은 꼴로 검증해 제공하는 판입니다. '
               '`입력/sop.json` — 제공 SOP 구조(적용 조건 · 금지 조건 · 수행 단계 · 완료 기준 · 승인과 원문 출처).',
               MINE['practical-03-review'],
               '`자료/경보_목록.csv` · `자료/PLC_상태_수신.csv` · `자료/팬_운전_카운터.csv` · `자료/예측_결과.csv` — 판단 입력의 원천 네 개(HYD-01 ~ 03, 2026-09-28 ~ 10-27). 기록 방식은 `자료/수집_설명.md`에 있습니다.',
               '`자료/오더_현황.csv` · `자료/metrics/` — 주어진 비교 산식(`지표_정의.md`)과 그 값.',
               '`자료/HM-8_매뉴얼.md` · `자료/HI-01_보충매뉴얼.md` · `자료/작업기준.md` — 조치 원문 · 보충 기준 · 회사 작업 기준. `자료/targets.csv` — 경보마다 검토하는 조치 후보 넷.',
               '`입출력_계약.md` — 입력과 결과 파일의 형식. `check.py` — 결과의 구조 검사.',
               '`결과/` — 이번에 만든 것을 두는 자리. 「제공 빈 틀」 `기대결과.md`가 있습니다.',
               RULES_LINE],
        user='이 답은 야간 운전원과 설비보전팀장이 이 검토 결과만 읽고 어느 후보를 승인 요청할지, 무엇을 먼저 확인할지 정할 때 씁니다.',
        questions=['사건의 네 후보 — 판단 입력(원천 네 개, 판정을 요청한 시각 기준) · 판정(유지 · 제외 · 보류와 이유) · 비교값과 순위는 무엇인가?',
                   '같은 기능이 지난 경보의 경계값 · 제외 사유와 누락이 겹친 입력 · 모두 제외된 입력에서 기대와 같은가?',
                   '사건에서 승인 요청을 검토할 후보와 그 까닭은 무엇인가? 후보마다 이유 · 원문 출처 · 추가로 확인할 값 · 승인 역할은 무엇이고, 비교 순위는 실행 승인과 어떻게 다른가?'],
        decide=JUDGE_DECIDE,
        outside=['조건표 · SOP 구조를 고치는 일(입력은 읽기만 합니다)', '원문에서 작업 조건을 뽑는 일(다음 실습)',
                 '비교 산식을 바꾸는 일', '실제 설비 조작과 실행 승인'],
        formats=formats, steps=steps,
        cases=['조건표의 숫자 기준값마다(예측 유온 · 팬 연속 시간 등) 그 값과 같은 후보와, 그 값의 바로 위 · 아래에서 가장 가까운 후보(경계값 — 단위가 다른 원천 포함)',
               '확인된 제외 사유와 입력 누락이 한 후보에 겹친 경우',
               '모든 후보가 제외된 경보',
               '원천에서 값이 비는 까닭이 서로 다른 경보(그 값이 필요한 규칙에만 영향이 가는지)',
               '「정할 것」의 결정에 따라 검토 의견이 바뀌는 경보',
               '`자료/metrics/지표_정의.md`의 손계산 예',
               '같은 코드를 다시 실행한 결과'],
        commands='python 결과/<만든 코드 이름>.py\npython check.py',
        done=('형식 검사나 실행 성공만으로 완료하지 않습니다. 사례 종류마다 실행 전에 원천 · 조건표 · 원문으로 적은 기대와 실행 결과가 같거나, 다른 까닭을 찾아 고친 기록이 있고, '
              '손계산 예의 네 손실이 프로그램 값과 같으며, 사건의 절만 읽고 후보마다 판정 · 까닭 · 승인 역할 · 먼저 확인할 값을 말할 수 있고, 「정한 것」의 근거와 그 선택으로 바뀌는 검토 의견을 설명할 수 있으면 완료입니다.'),
        save=save, reopen='만든 코드와 구조 검사의 출력, `조치검토결과.md`의 사건 절, `기대결과.md`의 사례 대조와 기준일 · 저장 시점 · 확인하지 못한 점',
        tree=tree('03일차_실습2_판단기능만들기', [('.github/', 'Copilot 작업 규칙'), ('결과/', '이번에 만들 것(기대결과.md 빈 틀)'),
                                            ('입력/', '조치 조건표와 SOP 구조(읽기만)'), ('자료/', '판단 입력의 원천 · 비교 산식 · 원문(읽기만)'),
                                            ('AGENTS.md', 'Codex 작업 규칙'), ('check.py', '구조 검사'), ('CLAUDE.md', '작업 규칙(같은 내용)'), ('guide.html', '이 가이드'),
                                            ('START.md', '이번 과제와 진행 단계'), ('안내.html', '이 가이드와 같은 파일'), ('입출력_계약.md', '입력과 결과 파일의 형식')]),
        lead='원천 기록에서 판단 입력을 만들고, 조건표로 후보를 판정 · 비교한 뒤, 후보별 이유 · 원문 출처 · 추가로 확인할 값 · 승인 역할과 검토 의견을 담은 조치 검토 결과로 완성합니다.',
        need='VS Code와 Python, 로그인해 둔 Codex 또는 GitHub Copilot.',
        terms=JUDGE_TERMS + ' **검토 의견**은 사례마다 승인 요청을 검토할 후보와 그 까닭, 먼저 확인할 값입니다. ' + CONTRACT_TERM,
        first_more=[MINE['practical-03-review']],
        guide_extra={1: ['ai', 'review'], 4: ['terminal']}, guide_after={4: [STUCK_PATH], 12: [stuck_no_result('조치검토결과.json')]}, files={
            'check.py': REVIEW_CHECK,
            '입출력_계약.md': '# 입출력 계약\n\n입력과 결과 파일의 형식과 뜻만 정한다. 판정 원칙은 원문(`자료/HM-8_매뉴얼.md` · `자료/작업기준.md` · `자료/HI-01_보충매뉴얼.md`), 원천의 기록 방식은 `자료/수집_설명.md`에 있다.\n\n'
                             + JUDGE_INPUT_CONTRACT + judge_table_contract() + '\n' + REVIEW_RESULT,
            '결과/기대결과.md': expect_template(),
            '결과/README.md': '이번 과제의 조치 검토 결과(조치검토결과.json · .md) · 기대결과.md와 만든 코드를 여기에 저장합니다.\n다시 열 때는 기대결과.md의 기준일 · 저장 시점과, 만든 코드 · 구조 검사의 출력을 함께 봅니다.\n',
            '입력/README.md': '냉각 계통 조치의 조치 조건표(조건표.csv)와 제공 SOP 구조(sop.json)입니다. 조건표의 형식은 입출력_계약.md에 있습니다. 이 폴더는 읽기만 합니다.\n\n' + SOP_KEYS,
        })


# 랩마다 넣는 원자료(구성안 3.2 「쓰는 랩」 — 대조에 쓰는 파일만, K-24). (자료 안 경로, 코어의 이름)
DATA = {
    'integrated-03-criteria': [('HM-8_매뉴얼.md',) * 2, ('HM-8_1.0판_매뉴얼.md',) * 2, ('HI-01_보충매뉴얼.md',) * 2, ('작업기준.md',) * 2,
                               ('판단시스템_결정표_내보내기.txt',) * 2, ('작업지시_이력.csv',) * 2, ('사건_기록_HYD-02_1027.md',) * 2,
                               ('확인_사례.csv',) * 2, ('targets.csv', 'targets_sop.csv'), ('failuremodes.csv',) * 2],
    'practical-02-conditions': [('HM-8_매뉴얼.md',) * 2, ('HI-01_보충매뉴얼.md',) * 2, ('작업기준.md',) * 2, ('판단시스템_결정표_내보내기.txt',) * 2,
                                ('사건_기록_HYD-02_1027.md',) * 2, ('확인_사례.csv',) * 2, ('targets.csv',) * 2],
}
DATA['integrated-03-judge'] = DATA['practical-03-review'] = [
    (name,) * 2 for name in ['HM-8_매뉴얼.md', 'HI-01_보충매뉴얼.md', '작업기준.md', '수집_설명.md', 'targets.csv', '경보_목록.csv', 'PLC_상태_수신.csv',
                             '팬_운전_카운터.csv', '예측_결과.csv', '오더_현황.csv', 'metrics/지표_정의.md', 'metrics/업무_값.json', 'metrics/후보_설정.csv']]
BUILDERS = {'integrated-03-criteria': criteria_lab, 'integrated-03-judge': judge_lab, 'practical-02-conditions': conditions_lab, 'practical-03-review': review_lab}


def criteria_inputs(folder):
    """통합 03-2 입력/ = 2회차 실습4 입력/의 모델 · 설비 대장과 같은 바이트(구성안 1절)."""
    schema, graph = B.reference_model(False, B.LAB4_INPUT_BRANCH['통합반'])
    B.dump(folder/'입력/schema.json', B.student_schema(schema))
    B.dump(folder/'입력/graph.json', graph)
    (folder/'입력/자료').mkdir(parents=True, exist_ok=True)
    (folder/'입력/자료/설비_대장.csv').write_text(D2._csv(D2.ASSET_COLS, D2.asset_rows()), encoding='utf-8', newline='')
    diff = []
    for rel in ['schema.json', 'graph.json', '자료/설비_대장.csv']:
        src = LAB4_INPUT/rel
        if src.is_file() and src.read_bytes() != (folder/'입력'/rel).read_bytes():
            diff.append(rel)
        elif not src.is_file():
            print(f'참고: 2회차 실습4 입력 {rel}이 없어 바이트 대조를 건너뜁니다.')
    if diff:
        raise RuntimeError(f'통합 03 실습2 입력이 2회차 실습4 입력과 다릅니다: {diff} — 2회차 생성기와 판을 맞춘 뒤 다시 만듭니다.')


def judge_inputs(folder):
    """판정 랩 입력/ = 조건 랩의 강사 검증 판(지점1 가 · 지점2 가). 실전반도 같은 조건표 바이트와 제공 SOP 구조를 받는다(구성안 1절)."""
    write(folder/'입력/조건표.csv', CR.table_csv(CR.BASE[1]))
    write(folder/'입력/sop.json', CR.sop_json(*CR.BASE))


def write_guide(folder, L, photos):
    """guide.html과 같은 바이트의 안내.html(회차 안내 · 노션이 가리키는 이름 — K-52). 틀 · 블록 · 도구 안내는 2회차와 같은 build_labs.step_guide."""
    guide = B.step_guide(L, photos)
    write(folder/'guide.html', guide)
    write(folder/'안내.html', guide)


def build(key, files):
    folder = LABS[key]
    L = BUILDERS[key](files)
    keep = {p.relative_to(folder).as_posix(): p.read_bytes() for p in (folder/'images').rglob('*') if p.is_file()} if (folder/'images').is_dir() else {}
    if folder.exists():
        shutil.rmtree(folder)                     # 이 생성기가 만드는 랩 폴더 — 옛 판 파일이 남지 않게 통째로 다시 쓴다(실제 화면 사진만 보존)
    folder.mkdir(parents=True)
    for rel, data in keep.items():
        (folder/rel).parent.mkdir(parents=True, exist_ok=True)
        (folder/rel).write_bytes(data)
    # 본 촬영 사진은 capture-provenance.json에 출처가 있는 것만 가이드의 그 절에 싣는다(2회차와 같은 확인 — 없으면 사진 없이)
    provenance = json.loads((B.TOOLS/'capture-provenance.json').read_text(encoding='utf-8'))
    photos = B.student_photos(folder, provenance, [s['name'] for s in L['steps']])
    for path in [folder/'AGENTS.md', folder/'.github/copilot-instructions.md', folder/'CLAUDE.md']:
        write(path, STEP_RULES)
    for name, core in DATA[key]:
        write(folder/'자료'/name, files[core])
    if key == 'integrated-03-criteria':
        criteria_inputs(folder)
    if key in ('integrated-03-judge', 'practical-03-review'):
        judge_inputs(folder)
    for name, text in L['files'].items():
        write(folder/name, text)
    # 공용 문장(build_labs.BACKTICK)의 파일 예를 이 랩의 파일로 바꾼다 — 이 랩에 없는 결과/schema.json을 가리키지 않게
    example = '`결과/조건표.csv`' if key in ('integrated-03-criteria', 'practical-02-conditions') else '`자료/수집_설명.md`'
    write(folder/'START.md', step_start(L).replace('`결과/schema.json`처럼', example + '처럼'))
    write_guide(folder, L, photos)
    return folder, L


def digest(folder):
    h = hashlib.sha256()
    for p in sorted(folder.rglob('*')):
        if p.is_file():
            h.update(p.relative_to(folder).as_posix().encode() + b'\0' + p.read_bytes())
    return h.hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--lab', choices=sorted(LABS), action='append')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    keys = args.lab or sorted(LABS)
    files, meta = DC.build()
    ref = B.TEACHER/'session3'
    ref.mkdir(parents=True, exist_ok=True)
    (ref/'원자료_메타.json').write_text(json.dumps(meta, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    for key in keys:
        folder, L = build(key, files)
        first = digest(folder)
        if args.check:
            files2, _ = DC.build()
            build(key, files2)
            second = digest(folder)
            print(f'{folder.name}: 두 번 생성 {"같음" if first == second else "다름"} ({first[:12]})')
            if first != second:
                return 1
        archive = pack(folder)
        print(f'{folder.name}: 파일 {sum(1 for p in folder.rglob("*") if p.is_file())}개, ZIP {archive.name} {hashlib.sha256(archive.read_bytes()).hexdigest()[:12]}')
    print('package-index · catalog 등록은 하지 않았습니다(lab_package.register · build_launcher.py로 따로).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
