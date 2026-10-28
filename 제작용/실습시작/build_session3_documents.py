"""실전반 온라인3 문서 지식화 랩 세 개(매뉴얼 대조·지식 추출·그래프 반영과 작업 확인 카드)의 독립 시작본.

자료는 현업 규모의 문서 묶음이다(판·상태가 다른 문서, 영한 병기 제조사 지침, CMMS 작업지시 서술, ERP 재고).
생성 자료는 data_documents.py(고정 시드)가 만든다. 승인 원문(HM-8 1.1·PM-02·PR-07·HI-01)은 복사만 한다.
학생 폴더에는 환경·원자료·작업 규칙·START·구조 검사기·앞 단계 완성 상태만 둔다.
추출 함수·후보·검토 결정·적재문·작업 카드 같은 이번 과제의 답은 reference/session3_docs/에만 있다.
실습5의 입력/검토결과는 실습4의 강사 참조 검토본(앞 단계 완성 상태)이다.
"""
from build_labs import ROOT, OUT, page, write, dump, pack, RULES, reference_model
from pathlib import Path
import csv
import hashlib
import html
import json
import shutil

import data_documents as data

HERE = Path(__file__).resolve().parent
REF = HERE / 'reference/session3_docs'
BUNDLE = ROOT / 'common/hydcommon/course_extractions.json'
MODEL_DATA = OUT / '통합반/실습/02회차/랩/02일차_실습3_온톨로지설계/자료'
LABS = OUT / '실전반/실습/03회차/랩'
VERSION = '2026-10-28-s3-v4-rh3'
MANUAL = '03일차_실습3_매뉴얼검토'
EXTRACT = '03일차_실습4_지식추출'
CARD = '03일차_실습5_그래프반영'
HM8_ONLY = {('HM-8', '1.0'), ('HM-8', '1.1'), ('HM-8', '1.2')}
REVIEWED = ['HM-8', 'PM-02', 'OEM-HPP45A-MM', 'HI-01']   # 실습5에 앞 단계 완성 상태로 주는 강사 검토본
TASKS = ['SOP-COOL-14', 'SOP-PM-21', 'SOP-PM-22', 'T-3.1', 'T-4.1']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reset(folder):
    """이전 생성물을 지우고 새로 만든다(이 랩 폴더 안만)."""
    if not folder.is_dir() or folder.parent != LABS:
        raise FileNotFoundError(f'대상 랩 폴더가 아닙니다: {folder}')
    for child in folder.iterdir():
        shutil.rmtree(child) if child.is_dir() else child.unlink()


def rules_file(folder, extra):
    text = RULES + ''.join(f'- {line}\n' for line in extra)
    for name in ['AGENTS.md', 'CLAUDE.md', '.github/copilot-instructions.md']:
        write(folder / name, text)


def register_rows(folder):
    with (folder / '자료/문서_목록.csv').open(encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


CYCLE = '''## 진행 방법 — AI와 함께

1. **탐색만 요청하기**: AI에게 이 폴더의 자료를 읽고 무엇이 있고 무엇이 비었는지, 자료끼리 어떻게 다른지 설명하게 하세요. 이때는 파일을 만들거나 바꾸지 말라고 함께 말합니다.
2. **요구를 자기 말로 정리하기**: 목표·입력·지켜야 할 제약·확인할 사례를 짧게 적고, 원자료에서 직접 찾은 기대 결과 2~3건을 실행 전에 적어 둡니다. AI에게 요구에서 애매한 점을 먼저 물어봐 달라고 해도 좋습니다.
3. **계획 검토하기**: AI의 계획에 확인 단계가 있는지, 아래 「정할 것」을 AI가 대신 정하지 않았는지 보고 고칠 점을 말한 뒤 진행하세요.
4. **작은 단위로 구현하기**: 한 기능을 만들고 실행해 본 뒤 다음으로 넘어갑니다.
5. **실행 증거로 판단하기**: AI가 끝났다고 하면 실행한 명령과 **출력 원문**(요약이 아니라 명령 뒤에 나온 글자 그대로)과 바뀐 파일 목록을 붙여 달라고 하세요. 직접 한 번 실행해 같은 출력이 나오는지 보고, 미리 적은 기대 결과와 대조합니다.
6. **수정 요청은 근거와 함께**: 어떤 입력에서, 무엇을 기대했고, 실제로 무엇이 나왔는지를 함께 전달하세요. 고친 뒤에는 내가 예로 든 행만 맞았는지가 아니라 같은 종류의 다른 행에도 통하는지 다시 세어 달라고 합니다. 두 번 고쳐도 같은 문제가 남으면 새 대화를 열고 지금까지 알게 된 것을 담아 다시 요청합니다.
7. **설명할 수 있을 때 저장하기**: 이 결과가 무엇을 하는지 한 문장으로 말할 수 있는지 확인하고 저장한 뒤 다시 열어 봅니다.

AI가 질문 카드(선택지와 「(권장)」 표시)로 물으면 「(권장)」은 AI의 추천일 뿐이니 원문 근거를 열어 확인하고 고르거나 직접 적습니다. 파일 편집 승인 창은 바뀔 파일이 `결과/` 아래일 때만 허용합니다. Codex 패널이 「Codex could not start」로 뜨지 않으면 VS Code 창을 닫고 같은 폴더를 다시 엽니다.

채팅 입력창은 밑줄(`_`)과 물결(`~`)을 서식으로 바꿀 수 있습니다. 파일 이름·명령·절 번호는 `` `작업지시_서술.csv` ``처럼 백틱(`)으로 감싸거나 파일을 첨부해 요청하고, 보낸 문장이 그대로 들어갔는지 눈으로 확인하세요.
'''

ASK = '<details><summary>요청을 정리할 때 볼 항목</summary><p>만들 결과 / 읽을 자료 / 바꾸지 않을 범위 / 지켜야 할 출력 계약 / 실행 전에 적은 기대 결과 / 확인하지 못하면 어떻게 표시할지 / 내가 정할 것(AI가 정하지 않게)</p></details>'

SAVE = '''## 저장과 다음 실습

결과 폴더를 저장하고 다시 열어 확인하세요. 재부팅하면 학교 PC의 작업 폴더가 사라질 수 있으니 보관할 결과는 USB 또는 개인 클라우드에 복사하세요. 다음 실습도 독립 시작본을 제공하므로 개인 결과는 선택 입력입니다.
'''


# ---------------------------------------------------------------- 실습4·5 공통: 출력 계약과 검사기
CONTRACT = '''# 추출 후보·검토 결과 출력 계약

이 계약은 실습4의 추출 결과(`결과/후보/*.json`)와 검토 결과(`결과/검토/*_검토.json`)의 모양과 필드의 뜻이다. 어떤 문장을 어떤 후보로 만들지는 정하지 않는다. 실습5는 같은 모양의 검토 결과를 입력으로 읽는다. `check_candidates.py`가 이 계약의 구조와 인용을 검사한다.

## 1. 후보 파일

```json
{
  "doc_id": "문서_목록.csv의 문서 식별자",
  "source_file": "자료/원문/ 안의 파일 이름",
  "source_sha256": "실제로 읽은 파일의 SHA-256",
  "extractor": "이 결과를 만든 실행(예: 결과/extract.py와 옵션)",
  "generated_at": "실행 시각(ISO 8601)",
  "candidates": [ { 후보 }, ... ],
  "warnings": ["추출 중 판단하지 못한 것"]
}
```

문서의 판과 상태(현행·폐기·보충·참고)는 `자료/문서_목록.csv`에서 파일 이름과 SHA-256으로 찾는다. 실제 추출 실행 없이 다른 파일을 옮긴 결과는 후보 파일이 아니다.

## 2. 후보 하나

| 필드 | 필수 | 뜻 |
|---|---|---|
| `id` | 예 | 파일 안에서 고유한 문자열 |
| `doc_id` | 예 | 파일의 `doc_id`와 같은 문서 식별자 |
| `section` | 예 | 그 내용이 있는 원문 `## ` 제목의 첫 낱말. 첫 `## ` 앞의 글은 `머리말` |
| `procedure` | 예 | 그 내용이 원문 `### ` 절차 안이면 그 제목의 첫 낱말(절차 ID), 절차 밖이면 `null` |
| `kind` | 예 | `step` · `precondition` · `prohibition` · `completion` · `unit_value` 중 하나 |
| `text` | 예 | 후보의 내용을 사람이 읽을 수 있게 적은 것 |
| `quote` | 예 | 근거가 되는 원문 문자열. 한 글자도 바꾸지 않은 연속 문자열이며 `section` 절 안에 있어야 한다 |
| `refs` | 예 | `quote`가 가리키는 다른 절·절차의 ID 목록(원문의 ID 표기). 없으면 `[]` |
| `status` | 예 | 추출 직후에는 `pending` |
| `order` | `step`이면 예 | 절차 안 번호(1부터) |
| `value` | `unit_value`이면 예 | 숫자. 범위면 작은 값 |
| `value_max` | 범위이면 예 | 범위의 큰 값 |
| `unit` | `unit_value`이면 예 | 원문에 적힌 단위 |
| `comparator` | `unit_value`이면 예 | `>=` `>` `<=` `<` `=` `range` `±` 중 하나, 원문에 비교 표현이 없으면 `null` |
| `value_text` | `unit_value`이면 예 | 값·단위·비교 표현이 적힌 원문 조각 그대로. `quote` 안에 있어야 한다 |

종류의 뜻:

- `step`: 절차의 번호 단계.
- `precondition`: 작업을 하기 전에 충족·확인해야 하는 조건과 승인.
- `prohibition`: 금지와 제한.
- `completion`: 끝났다고 보는 기준과 끝나지 않았을 때의 처리.
- `unit_value`: 숫자와 단위가 있는 기준값.

## 3. 검토 결과 파일

후보 파일을 복사해 아래를 더한 별도 파일이다. 후보 파일 원본은 그대로 둔다.

```json
{
  ...후보 파일의 doc_id·source_file·source_sha256·extractor·generated_at...,
  "review": {"reviewer": "검토자", "reviewed_at": "시각", "candidates_file": "후보 파일 이름", "selected_task": "선택한 작업 ID 또는 null", "decisions": ["검토 전체에 적용한 결정과 근거"]},
  "candidates": [ {후보 필드 + 아래 검토 필드} ],
  "missing": [ {"section": "…", "procedure": null, "kind": "…", "quote": "원문 그대로", "note": "왜 빠졌는지", "added": false} ]
}
```

| 검토 필드 | 뜻 |
|---|---|
| `decision` | `채택` · `수정` · `제외` · `보류` |
| `status` | 채택·수정 → `approved`, 제외 → `excluded`, 보류 → `pending` |
| `reason` | 원문 근거를 든 결정 이유 |
| `before` | `수정`일 때 바꾸기 전 필드 값 |
| `origin` | 추출 함수가 낸 후보는 `extractor`, 검토자가 원문 문장으로 추가한 후보는 `reviewer` |

`missing`은 원문에 있는데 후보가 없는 것이다. 검토자가 근거 문장으로 후보를 추가했다면 `added: true`로 표시하고 그 후보의 `origin`을 `reviewer`로 둔다. 다음 단계에는 `approved` 후보만 쓴다.
'''

CHECKER = r'''"""후보·검토 JSON의 계약 검사. 인용이 원문 절 안에 그대로 있는지 대조한다.
지식의 맞고 틀림, 종류 판단, 빠진 지식, 어떤 문서를 근거로 쓸지는 판정하지 않는다. 생성·수정을 하지 않는다.
사용:
  python check_candidates.py                          단계별 상태(무엇이 있고 무엇이 비었는지)
  python check_candidates.py 결과/후보/HM-8.json [...]   파일별 계약 검사
"""
from pathlib import Path
import csv, hashlib, json, re, sys

HERE = Path(__file__).resolve().parent
KINDS = {'step', 'precondition', 'prohibition', 'completion', 'unit_value'}
COMPARATORS = {None, '>=', '>', '<=', '<', '=', 'range', '±'}
STATUS = {'채택': 'approved', '수정': 'approved', '제외': 'excluded', '보류': 'pending'}
REQUIRED = ['id', 'doc_id', 'section', 'procedure', 'kind', 'text', 'quote', 'refs', 'status']


def register():
    path = HERE / '자료/문서_목록.csv'
    with path.open(encoding='utf-8-sig', newline='') as f:
        return {r['파일']: r for r in csv.DictReader(f) if r['파일']}


def blocks(text):
    """절 ID → 절 본문, 절 ID → 그 절의 절차 ID 목록."""
    body, procs, current, lines = {}, {}, '머리말', []
    for line in text.splitlines():
        m = re.match(r'^##\s+(\S+)', line)
        if m and not line.startswith('###'):
            body[current] = '\n'.join(lines)
            current, lines = m.group(1), []
            continue
        p = re.match(r'^###\s+(\S+)', line)
        if p:
            procs.setdefault(current, []).append(p.group(1))
        lines.append(line)
    body[current] = '\n'.join(lines)
    return body, procs


def check(path):
    errors, notes = [], []
    data = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if not isinstance(data, dict):
        return ['최상위가 객체가 아닙니다.'], notes
    for key in ['doc_id', 'source_file', 'source_sha256', 'extractor', 'generated_at', 'candidates']:
        if not data.get(key) and key != 'candidates' or key not in data:
            errors.append(f'최상위 필드 없음: {key}')
    if errors:
        return errors, notes
    source = HERE / '자료/원문' / data['source_file']
    if not source.is_file():
        return [f'자료/원문/{data["source_file"]} 파일이 없습니다.'], notes
    if hashlib.sha256(source.read_bytes()).hexdigest() != data['source_sha256']:
        errors.append('source_sha256이 자료/원문의 파일과 다릅니다(다른 판을 읽었거나 해시를 지어냈음).')
    row = register().get(data['source_file'])
    if row is None:
        errors.append('자료/문서_목록.csv에 없는 파일입니다.')
    else:
        notes.append(f'문서_목록: {row["문서 식별자"]} {row["판"]}판 · 상태 {row["상태"]}')
        if row['SHA-256'] != data['source_sha256']:
            errors.append('source_sha256이 문서_목록.csv의 해시와 다릅니다.')
        if row['문서 식별자'] != data['doc_id']:
            errors.append(f'doc_id {data["doc_id"]!r}가 문서_목록의 식별자 {row["문서 식별자"]!r}와 다릅니다.')
    body, procs = blocks(source.read_text(encoding='utf-8'))
    reviewed = 'review' in data
    if reviewed:
        for key in ['reviewer', 'reviewed_at']:
            if not data['review'].get(key):
                errors.append(f'review.{key} 없음')
    seen, dup = set(), set()
    for i, c in enumerate(data['candidates']):
        where = c.get('id', f'#{i}') if isinstance(c, dict) else f'#{i}'
        if not isinstance(c, dict):
            errors.append(f'{where}: 후보가 객체가 아님'); continue
        miss = [k for k in REQUIRED if k not in c]
        if miss:
            errors.append(f'{where}: 필수 필드 없음 {miss}')
            continue
        if c['id'] in seen:
            errors.append(f'{where}: 중복 id')
        seen.add(c['id'])
        if c['doc_id'] != data['doc_id']:
            errors.append(f'{where}: doc_id가 파일의 doc_id와 다름')
        if c['kind'] not in KINDS:
            errors.append(f'{where}: 알 수 없는 kind {c["kind"]!r}')
        if not str(c['text']).strip():
            errors.append(f'{where}: text가 비어 있음')
        if not isinstance(c['refs'], list):
            errors.append(f'{where}: refs는 목록이어야 함')
        if c['section'] not in body:
            errors.append(f'{where}: 원문에 없는 절 {c["section"]!r}')
        elif not c['quote'] or c['quote'] not in body[c['section']]:
            hit = [s for s, t in body.items() if c['quote'] and c['quote'] in t]
            errors.append(f'{where}: quote가 {c["section"]} 절 안에 그대로 없음' + (f'(다른 절 {hit}에 있음)' if hit else '(원문 어디에도 없음)'))
        if c['procedure'] is not None and c['procedure'] not in procs.get(c['section'], []):
            errors.append(f'{where}: {c["section"]} 절에 없는 절차 {c["procedure"]!r}')
        if c['kind'] == 'step' and not (isinstance(c.get('order'), int) and not isinstance(c.get('order'), bool) and c['order'] >= 1):
            errors.append(f'{where}: step에는 1 이상의 정수 order가 필요')
        if c['kind'] == 'unit_value':
            if not isinstance(c.get('value'), (int, float)) or isinstance(c.get('value'), bool):
                errors.append(f'{where}: unit_value의 value는 숫자여야 함')
            if not c.get('unit'):
                errors.append(f'{where}: unit_value에 unit이 없음')
            if c.get('comparator', 'missing') not in COMPARATORS:
                errors.append(f'{where}: comparator가 계약 값이 아님 {c.get("comparator", "(필드 없음)")!r}')
            if c.get('comparator') == 'range' and not isinstance(c.get('value_max'), (int, float)):
                errors.append(f'{where}: range에는 value_max가 필요')
            if not c.get('value_text') or c['value_text'] not in c['quote']:
                errors.append(f'{where}: value_text가 quote 안에 그대로 없음')
        key = (c['kind'], c['section'], c['procedure'], c['text'], c['quote'], c.get('value_text'))
        if key in dup:
            errors.append(f'{where}: 같은 종류·절·내용·인용·값의 후보가 이미 있음')
        dup.add(key)
        if reviewed:
            dec = c.get('decision')
            if dec not in STATUS:
                errors.append(f'{where}: decision은 채택·수정·제외·보류 중 하나')
            elif c['status'] != STATUS[dec]:
                errors.append(f'{where}: {dec}이면 status는 {STATUS[dec]}')
            if not str(c.get('reason', '')).strip():
                errors.append(f'{where}: 결정 이유(reason)가 없음')
            if dec == '수정' and not c.get('before'):
                errors.append(f'{where}: 수정에는 바꾸기 전 값(before)이 필요')
            if c.get('origin') not in ('extractor', 'reviewer'):
                errors.append(f'{where}: origin은 extractor 또는 reviewer')
        elif c['status'] != 'pending':
            errors.append(f'{where}: 추출 직후 status는 pending')
    for m in data.get('missing', []) if reviewed else []:
        sec = m.get('section')
        if sec not in body or not m.get('quote') or m['quote'] not in body[sec]:
            errors.append(f'missing {sec}: quote가 원문 절 안에 그대로 없음')
    kinds = {}
    for c in data['candidates']:
        if isinstance(c, dict):
            kinds[c.get('kind')] = kinds.get(c.get('kind'), 0) + 1
    notes.append(f'후보 {len(data["candidates"])}개, 종류별 {kinds}')
    if reviewed:
        dec = {}
        for c in data['candidates']:
            if isinstance(c, dict):
                dec[c.get('decision')] = dec.get(c.get('decision'), 0) + 1
        notes.append(f'결정별 {dec}, 누락 기록 {len(data.get("missing", []))}개')
    return errors, notes


def run(path):
    try:
        return check(path)
    except (OSError, ValueError, TypeError, AttributeError, KeyError) as e:
        return [f'읽기 실패: {e}'], []


def empty_tables(md):
    """기록 파일의 절별 빈 표·빈 칸 수. 제목 줄과 구분 줄은 세지 않는다."""
    out, sec, header = {}, '머리', False
    for line in md.splitlines():
        if line.startswith('## '):
            sec, header = line[3:].strip(), False
            continue
        if line.startswith('|'):
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            if all(re.fullmatch(r':?-{2,}:?', c) for c in cells):
                header = True
                out.setdefault(sec, [0, 0])
                continue
            if not header:
                continue
            out.setdefault(sec, [0, 0])
            out[sec][0] += 1
            out[sec][1] += sum(1 for c in cells if not c)
        elif not line.strip():
            header = False
    return out


def stages():
    todo = []
    ext = HERE / '결과/extract.py'
    print(f'[1] 추출 함수 결과/extract.py: {"있음" if ext.is_file() else "없음"}')
    if not ext.is_file():
        todo.append('추출 함수가 없습니다.')
    files = sorted((HERE / '결과/후보').glob('*.json'))
    print(f'[2] 후보 파일 {len(files)}개')
    docs = set()
    for f in files:
        errors, notes = run(f)
        state = '계약 통과' if not errors else f'계약 확인 필요 {len(errors)}건'
        print(f'    {f.name}: {state} · ' + ' · '.join(notes))
        if errors:
            todo.append(f'{f.name} 계약 오류(파일 이름을 인자로 주고 실행하면 목록이 나옵니다).')
        try:
            docs.add(json.loads(f.read_text(encoding='utf-8-sig')).get('source_file'))
        except (OSError, ValueError, AttributeError):
            pass
    print(f'[3] 후보를 만든 원문 파일 {len(docs)}개: {", ".join(sorted(d for d in docs if d)) or "없음"}')
    if len(docs) < 2:
        todo.append('다른 문서에 다시 실행한 후보가 아직 없습니다.')
    reviews = sorted((HERE / '결과/검토').glob('*.json'))
    print(f'[4] 검토 결과 {len(reviews)}개')
    for f in reviews:
        errors, notes = run(f)
        print(f'    {f.name}: {"계약 통과" if not errors else f"계약 확인 필요 {len(errors)}건"} · ' + ' · '.join(notes))
        if errors:
            todo.append(f'{f.name} 계약 오류.')
        try:
            data = json.loads(f.read_text(encoding='utf-8-sig'))
            cands = [c for c in data.get('candidates', []) if isinstance(c, dict)]
        except (OSError, ValueError, AttributeError):
            continue
        if not any(c.get('status') == 'approved' for c in cands):
            todo.append(f'{f.name}: approved 후보가 없습니다. 다음 단계는 approved 후보만 쓰므로, 원문과 대조해 채택·수정한 후보가 있어야 합니다.')
        elif cands and all(c.get('decision') == '채택' for c in cands) and not data.get('missing'):
            todo.append(f'{f.name}: 모든 후보가 「채택」이고 누락 기록이 0개입니다. 사람이 원문과 나란히 놓고 대조한 흔적(수정·제외·보류한 후보, 원문에 있는데 빠진 것)이 없습니다. 대조한 절의 후보를 원문과 한 줄씩 다시 보고, 시간 안에 보지 못한 후보는 「보류」(이유: 미검토)로 둡니다.')
    if not reviews:
        todo.append('검토 결과가 없습니다.')
    record = HERE / '결과/검토_기록.md'
    print('[5] 검토_기록.md')
    if not record.is_file():
        todo.append('검토_기록.md가 없습니다.')
    else:
        text = record.read_text(encoding='utf-8-sig')
        for line in text.splitlines():
            if re.match(r'^- [^:]+:\s*$', line):
                print(f'    빈 항목: {line.strip()}')
                todo.append(f'검토_기록.md의 빈 항목 「{line.strip()}」')
        for sec, (rows, blanks) in empty_tables(text).items():
            if rows == 0:
                print(f'    「{sec}」: 표에 기록 없음')
                todo.append(f'검토_기록.md 「{sec}」 표가 비어 있습니다.')
            elif blanks:
                print(f'    「{sec}」: {rows}행, 빈 칸 {blanks}개')
                todo.append(f'검토_기록.md 「{sec}」 빈 칸 {blanks}개(실제 결과 칸은 직접 채웁니다).')
            else:
                print(f'    「{sec}」: {rows}행')
    print()
    if todo:
        print('완료 아님 — 남은 것:')
        for t in todo:
            print('  - ' + t)
        return 1
    print('구조상 빠진 단계는 없습니다. 내용이 맞는지·빠진 지식·근거 문서 선택은 원문과 직접 대조하세요.')
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(stages())
    failed = False
    for arg in sys.argv[1:]:
        errors, notes = run(arg)
        print(f'== {arg}')
        for n in notes:
            print('  ' + n)
        if errors:
            failed = True
            print(f'  계약 확인 필요 {len(errors)}건')
            for e in errors[:40]:
                print('  - ' + e)
            if len(errors) > 40:
                print(f'  … 외 {len(errors) - 40}건')
        else:
            print('  계약 검사 통과: 모든 인용이 원문 절 안에 그대로 있습니다. 빠진 지식과 종류 판단은 원문과 직접 대조하세요.')
    sys.exit(1 if failed else 0)
'''

LAB_CYPHER = r'''"""이 폴더 전용 랩 DB(lab_db.py가 만든 컨테이너)에 Cypher를 실행하는 도구. 포털 DB에 접속하지 않는다.
사용:
  python lab_cypher.py model              입력/모델/graph.json(앞 단계 완성 모델)을 적재
  python lab_cypher.py run 결과/load.cypher  파일의 문장을 차례로 실행(문장은 줄 끝 ; 로 구분)
  python lab_cypher.py count              전체·종류별 노드 수와 관계 수
"""
from pathlib import Path
import json, re, sys, urllib.request, urllib.error

HERE = Path(__file__).resolve().parent
STATE = HERE / '랩_연결.json'
WIPE = re.compile(r'MATCH\s*\(\s*\w*\s*\)\s*(DETACH\s+)?DELETE', re.I)


def endpoint():
    if not STATE.is_file():
        raise RuntimeError('랩_연결.json이 없습니다. 먼저 python lab_db.py 를 실행하세요.')
    return json.loads(STATE.read_text(encoding='utf-8'))['http'] + '/db/neo4j/tx/commit'


def cypher(statements):
    body = json.dumps({'statements': [{'statement': s, 'parameters': p, 'includeStats': True} for s, p in statements]}).encode()
    req = urllib.request.Request(endpoint(), body, {'Content-Type': 'application/json', 'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
    except urllib.error.URLError as e:
        raise RuntimeError(f'랩 DB에 연결하지 못했습니다({e}). python lab_db.py 로 DB를 다시 준비하세요.')
    if data.get('errors'):
        raise RuntimeError('; '.join(e.get('message', '') for e in data['errors']))
    return data['results']


def show(result):
    cols = result['columns']
    rows = [r['row'] for r in result['data']]
    if cols:
        print(' | '.join(cols))
        for row in rows[:50]:
            print(' | '.join(json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v for v in row))
        if len(rows) > 50:
            print(f'… 외 {len(rows) - 50}행')
        print(f'({len(rows)}행)')
    stats = {k: v for k, v in result.get('stats', {}).items() if isinstance(v, int) and v}
    if stats:
        print('변경:', stats)


def model():
    graph = json.loads((HERE / '입력/모델/graph.json').read_text(encoding='utf-8'))
    by_label = {}
    for n in graph['nodes']:
        by_label.setdefault(n['labels'][0], []).append(n['props'])
    stmts = [(f'UNWIND $rows AS p MERGE (n:`{label}` {{id:p.id}}) SET n += p', {'rows': rows}) for label, rows in by_label.items()]
    by_type = {}
    for r in graph['rels']:
        by_type.setdefault(r['type'], []).append({'a': r['a'], 'b': r['b'], 'props': r['props']})
    stmts += [(f'UNWIND $rows AS r MATCH (a {{id:r.a}}), (b {{id:r.b}}) MERGE (a)-[x:`{t}`]->(b) SET x += r.props', {'rows': rows}) for t, rows in by_type.items()]
    cypher(stmts)
    print(f'앞 단계 모델 적재: 노드 {len(graph["nodes"])}개·관계 {len(graph["rels"])}개 입력(MERGE, 다시 실행해도 늘지 않음)')
    count()


def statements(text):
    parts, buf = [], []
    for line in text.splitlines():
        if line.strip().startswith('//') and not buf:
            continue
        buf.append(line)
        if line.rstrip().endswith(';'):
            parts.append('\n'.join(buf).rstrip().rstrip(';')); buf = []
    if '\n'.join(buf).strip():
        parts.append('\n'.join(buf))
    return parts


def run(path):
    parts = statements(Path(path).read_text(encoding='utf-8-sig'))
    for i, s in enumerate(parts, 1):
        if WIPE.search(s):
            raise RuntimeError(f'{i}번째 문장: 전체 삭제문은 이 랩에서 실행하지 않습니다. 필요한 대상만 고치세요.')
    for i, s in enumerate(parts, 1):
        print(f'-- {i}/{len(parts)}')
        try:
            show(cypher([(s, {})])[0])
        except RuntimeError as e:
            raise RuntimeError(f'{path} {i}번째 문장 실패: {e}')


def count():
    res = cypher([('MATCH (n) RETURN count(n) AS nodes', {}), ('MATCH ()-[r]->() RETURN count(r) AS rels', {}),
                  ('MATCH (n) UNWIND labels(n) AS label RETURN label, count(*) AS n ORDER BY label', {})])
    print(f'전체 노드 {res[0]["data"][0]["row"][0]}개, 관계 {res[1]["data"][0]["row"][0]}개')
    print('종류별:', ', '.join(f'{r["row"][0]} {r["row"][1]}' for r in res[2]['data']))


if __name__ == '__main__':
    try:
        if sys.argv[1:2] == ['model']:
            model()
        elif sys.argv[1:2] == ['run'] and len(sys.argv) == 3:
            run(sys.argv[2])
        elif sys.argv[1:2] == ['count']:
            count()
        else:
            print(__doc__); sys.exit(2)
    except (OSError, ValueError, KeyError, RuntimeError) as e:
        print('실행 확인 필요: ' + str(e)); sys.exit(1)
'''

CARD_HEADINGS = ['대상 작업', '준비 조건', '금지·제한', '작업 순서', '완료 기준', '작업 직전 확인할 현재 값', '부품 준비', '지난 시행 기록', '승인', '남은 질문']

CARD_CHECK = r'''"""실습5 단계별 상태와 작업 확인 카드의 형식 검사. 생성·수정·DB 변경을 하지 않는다.
카드의 「인용」이 원문·기록 파일에 그대로 있는지, 카드가 가리킨 작업지시·품번이 자료에 있는지만 대조한다.
조건이 빠졌는지, 지난 시행을 어떻게 골랐는지, 수량을 어떻게 셌는지가 맞는지는 판정하지 않는다.
랩 DB가 준비돼 있으면 읽기 조회로 「적재한 지식이 앞 단계 모델의 기존 ID와 이어졌는지」 개수만 센다(어디에 이어야 맞는지는 판정하지 않는다).
사용: python check_card.py
"""
from pathlib import Path
import csv, json, re, sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
HEADINGS = __HEADINGS__
DELETE = re.compile(r'\bDELETE\b', re.I)
QUOTE = re.compile(r'「([^」]+)」')
LISTED = ['준비 조건', '금지·제한', '작업 순서', '완료 기준']


def sources():
    with (HERE / '자료/문서_목록.csv').open(encoding='utf-8-sig', newline='') as f:
        rows = [r for r in csv.DictReader(f) if r['파일']]
    out = [(r, (HERE / '자료/원문' / r['파일']).read_text(encoding='utf-8')) for r in rows]
    for p in sorted((HERE / '자료/기록').glob('*.csv')):
        out.append(({'파일': p.name, '상태': '기록'}, p.read_text(encoding='utf-8-sig')))
    return out


def csv_rows(name):
    path = HERE / '자료/기록' / name
    lines = [l for l in path.read_text(encoding='utf-8-sig').splitlines() if not l.startswith('#')]
    return list(csv.DictReader(lines))


def parts():
    known = {r['품번'] for r in csv_rows('재고_현황.csv') if r['품번']}
    graph = json.loads((HERE / '입력/모델/graph.json').read_text(encoding='utf-8'))
    known |= {n['props'].get('id') for n in graph['nodes']}
    return known


def sections(md):
    out, cur = {}, None
    for line in md.splitlines():
        if line.startswith('## '):
            cur = line[3:].strip(); out[cur] = []; continue
        if cur is not None and line.strip():
            out[cur].append(line)
    return out


def check_card(path, docs, orders, known):
    errors, notes = [], []
    md = path.read_text(encoding='utf-8-sig')
    secs = sections(md)
    for h in HEADINGS:
        if h not in secs:
            errors.append(f'제목 「## {h}」 없음')
        elif not secs[h]:
            errors.append(f'「{h}」 아래가 비어 있음(해당 없음이면 그렇게 적고 이유를 씀)')
    for h in LISTED:
        for line in secs.get(h, []):
            if line.lstrip().startswith(('-', '*')) or re.match(r'^\s*\d+\.', line):
                if not QUOTE.search(line) and '없음' not in line:
                    errors.append(f'「{h}」 항목에 「원문 인용」이 없음: {line.strip()[:60]}')
    quotes = QUOTE.findall(md)
    stale = []
    for q in quotes:
        hit = [r for r, text in docs if q in text]
        if not hit:
            errors.append(f'원문·기록 어디에도 그대로 없는 인용: 「{q[:50]}」')
        elif all(r['상태'] == '폐기' for r in hit):
            stale.append(q)
    for wo in sorted(set(re.findall(r'WO-\d{4}-\d{5}', md))):
        if wo not in orders:
            errors.append(f'작업지시_서술.csv에 없는 작업지시 {wo}')
    for p in sorted(set(re.findall(r'\bP-[A-Z0-9]+(?:-[A-Z0-9]+)*', md))):
        if p not in known:
            notes.append(f'재고_현황·모델에 없는 품번 표기 {p}')
    notes.append(f'인용 {len(quotes)}개' + (f', 폐기 판에만 있는 인용 {len(stale)}개' if stale else ''))
    return errors, notes


def main():
    todo = []
    state = HERE / '랩_연결.json'
    print(f'[1] 랩 DB 연결 정보 랩_연결.json: {"있음" if state.is_file() else "없음(python lab_db.py)"}')
    if not state.is_file():
        todo.append('랩 DB를 아직 준비하지 않았습니다.')
    for name in ['load.cypher', 'query.cypher']:
        p = HERE / '결과' / name
        if not p.is_file():
            print(f'[2] 결과/{name}: 없음'); todo.append(f'결과/{name}이 없습니다.'); continue
        text = p.read_text(encoding='utf-8-sig')
        wipe = re.search(r'MATCH\s*\(\s*\w*\s*\)\s*(DETACH\s+)?DELETE', text, re.I)
        n = len([l for l in text.splitlines() if l.rstrip().endswith(';') and not l.lstrip().startswith('//')])
        print(f'[2] 결과/{name}: 문장 약 {n}개' + (' · 전체 삭제문 있음' if wipe else ''))
        if wipe:
            todo.append(f'{name}에 전체 삭제문이 있습니다.')
        from lab_cypher import statements
        dels = [i for i, s in enumerate(statements(text), 1)
                if DELETE.search('\n'.join(l for l in s.splitlines() if not l.lstrip().startswith('//')))]
        if dels:
            print(f'    결과/{name}: 삭제(DELETE) 문장 {len(dels)}개 — {", ".join(f"{i}번째" for i in dels[:10])}' + (' …' if len(dels) > 10 else ''))
            todo.append(f'결과/{name} {", ".join(f"{i}번째" for i in dels[:10])} 문장에 DELETE가 있습니다. '
                        + ('적재문은 만들고 고치는 문장(MERGE·SET)만 두어 다시 실행해도 같은 결과가 나오게 합니다. 잘못 적재한 것은 적재문을 고친 뒤 랩 DB를 새로 준비해 다시 적재합니다.'
                           if name == 'load.cypher' else '조회문은 읽기만 합니다.'))
    if state.is_file():
        try:
            from lab_cypher import cypher
            ids = [n['props']['id'] for n in json.loads((HERE / '입력/모델/graph.json').read_text(encoding='utf-8'))['nodes']]
            res = cypher([('MATCH (k) WHERE k.id IS NULL OR NOT k.id IN $ids RETURN count(k)', {'ids': ids}),
                          ('MATCH (m)-[r]-(k) WHERE m.id IN $ids AND (k.id IS NULL OR NOT k.id IN $ids) '
                           'RETURN labels(m)[0] AS 기존, type(r) AS 관계, count(DISTINCT r) AS n ORDER BY 기존, 관계', {'ids': ids})])
            extra = res[0]['data'][0]['row'][0]
            links = [r['row'] for r in res[1]['data']]
            total = sum(r[2] for r in links)
            print(f'[2] 랩 DB: 앞 단계 모델 밖에서 적재한 노드 {extra}개, 그중 기존 모델 ID와 이어진 관계 {total}개'
                  + (' — ' + ', '.join(f'{a} {t} {n}개' for a, t, n in links[:12]) if links else ''))
            if extra == 0:
                todo.append('랩 DB에 앞 단계 모델 밖의 노드가 없습니다. load.cypher를 아직 실행하지 않았습니다.')
            elif total == 0:
                todo.append(f'적재한 노드 {extra}개가 앞 단계 모델의 기존 ID(설비·구성요소·센서·물리량·부품 등)와 하나도 이어지지 않았습니다. '
                            'START 범위 1: 기존 모델의 어떤 ID에 무엇을 근거로 연결할지 정하고, 연결할 ID가 없으면 남은 질문으로 적습니다.')
        except (OSError, ValueError, KeyError, RuntimeError) as e:
            print(f'[2] 랩 DB 조회 실패: {e}')
            todo.append(f'랩 DB를 조회하지 못해 기존 모델 ID와의 연결을 세지 못했습니다({e}).')
    docs = sources()
    orders = {r['작업지시'] for r in csv_rows('작업지시_서술.csv')}
    known = parts()
    cards = sorted((HERE / '결과').glob('작업확인카드*.md'))
    print(f'[3] 작업 확인 카드 {len(cards)}개')
    for c in cards:
        errors, notes = check_card(c, docs, orders, known)
        print(f'    {c.name}: {"형식 통과" if not errors else f"확인 필요 {len(errors)}건"} · ' + ' · '.join(notes))
        for e in errors[:20]:
            print('      - ' + e)
        if errors:
            todo.append(f'{c.name} 형식 확인 필요.')
    if len(cards) < 2:
        todo.append('선택한 작업과 다른 작업 하나 이상의 카드가 필요합니다.')
    record = HERE / '결과/구축_기록.md'
    print('[4] 구축_기록.md')
    if record.is_file():
        cur, header, rows, blanks = None, False, {}, {}
        for line in record.read_text(encoding='utf-8-sig').splitlines():
            if line.startswith('## '):
                cur, header = line[3:].strip(), False; continue
            if line.startswith('|') and cur:
                cells = [x.strip() for x in line.strip().strip('|').split('|')]
                if all(re.fullmatch(r':?-{2,}:?', x) for x in cells):
                    header = True; rows.setdefault(cur, 0); blanks.setdefault(cur, 0); continue
                if header:
                    rows[cur] += 1; blanks[cur] += sum(1 for x in cells if not x)
            elif not line.strip():
                header = False
        for sec in rows:
            if rows[sec] == 0:
                print(f'    「{sec}」: 표에 기록 없음'); todo.append(f'구축_기록.md 「{sec}」 표가 비어 있습니다.')
            elif blanks[sec]:
                print(f'    「{sec}」: {rows[sec]}행, 빈 칸 {blanks[sec]}개'); todo.append(f'구축_기록.md 「{sec}」 빈 칸 {blanks[sec]}개(실제 수치·결과 칸은 직접 채웁니다).')
            else:
                print(f'    「{sec}」: {rows[sec]}행')
    else:
        todo.append('구축_기록.md가 없습니다.')
    print()
    if todo:
        print('완료 아님 — 남은 것:')
        for t in todo:
            print('  - ' + t)
        return 1
    print('형식상 빠진 단계는 없습니다. 카드 내용·빠진 조건·지난 시행과 수량 판단은 원문·자료와 직접 대조하세요.')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError) as e:
        print('실행 확인 필요: ' + str(e)); sys.exit(1)
'''.replace('__HEADINGS__', repr(CARD_HEADINGS))


def guide(folder, title, intro, sections):
    text = page(title, intro, sections)
    write(folder / 'guide.html', text)
    write(folder / '안내.html', text)


def start(folder, text):
    write(folder / 'START.md', text)
    write(folder / '준비_안내.md', text)


def doc_table(folder):
    rows = register_rows(folder)
    lines = ['| 문서 | 판 | 상태 | 파일 |', '|---|---|---|---|']
    lines += [f'| {r["문서 식별자"]} | {r["판"]} | {r["상태"]} | {("`" + r["파일"] + "`") if r["파일"] else "(파일 없음)"} |' for r in rows]
    return '\n'.join(lines)


# ---------------------------------------------------------------- 실습3 매뉴얼 대조(포털 관찰, 코드 과제 아님)
def build_manual():
    folder = LABS / MANUAL
    reset(folder)
    data.write_all(folder, HM8_ONLY)
    rules_file(folder, ['이번 실습은 포털 관찰과 기록이다. 포털에서 매뉴얼 등록·미리보기·에이전트 추출 요청·적재를 하지 않는다. 직접 추가 적재는 마지막 교대 실습에서 한다.',
                        '포털에서 보지 못한 표시는 보았다고 적지 않는다. 화면에서 찾지 못한 항목은 「포털에서 찾지 못함」으로 둔다.'])
    title = '포털 지식과 매뉴얼 원문 대조하기'
    intro = '포털에 등록된 HM-8 지식을 문서 목록의 현행 원문과 나란히 놓고, 팬 최대 운전과 쿨러 핀 세척을 하기 전에 확인할 항목을 원문 절에 연결합니다. 현장에 남아 있는 다른 판도 함께 대조합니다.'
    start(folder, f'''# {title}

{intro} 코드를 작성하지 않는 관찰 실습입니다.

자료는 교육용 가상 자료입니다(공개 현업 문제 유형을 따라 생성).

## 출발 상태

`자료/문서_목록.csv`에 등록된 HM-8의 판과 상태입니다.

{doc_table(folder)}

- 수업용 포털: 강사가 준비한 교육 환경입니다. 1회차에서 본 매뉴얼 적재 이후의 지식이 지식 지도에 있습니다. 상태가 다르면 강사에게 알리고 그 사실을 기록합니다.
- `결과/대조_기록.md`: 비어 있는 기록 틀입니다.

## 이번에 할 일

1. 문서 목록에서 포털 지식과 대조할 판을 정하고, 포털의 HM-8이 그 판인지 확인할 방법을 적습니다.
2. 그 판의 원문에서 **팬 최대 운전**과 **쿨러 핀 세척**을 찾습니다. 절차의 단계뿐 아니라 그 작업을 가리키거나 적용 범위를 정하는 다른 절도 찾습니다.
3. 포털 왼쪽 메뉴의 지식 묶음에서 **지식 지도**를 열고 조치 방법 칸에서 두 작업을 찾습니다. 화면에 보이는 단계·조건·근거 표시를 그대로 기록합니다. **지식 관리** 화면에서는 HM-8이 등록되어 있는지만 확인합니다.
4. 두 작업마다 적용 조건·금지 사항·완료 기준·승인을 원문 절과 원문 문장에 연결하고, 포털에서 본 표현과 일치하는지 적습니다.
5. 다른 판에서 같은 작업을 찾아, 현장에서 그 판을 보고 일하면 작업 전 확인이 어떻게 달라지는지 적습니다.
6. 문서에 적힌 **기준값**과 작업 직전에 설비·기록에서 읽어야 하는 **현재 값**을 다른 칸에 적습니다.
7. 원문의 한 문장이 어느 작업에 적용되는지 원문만으로 정해지지 않으면, 어떻게 적용할지 정하고 근거를 적습니다. 정할 수 없으면 남은 질문으로 둡니다.

## 확인할 사례의 종류

- 작업 조건이 그 절차 밖의 다른 절에 적혀 있는 경우
- 표의 머리글이 값의 뜻을 정하는 경우
- 경계를 정하는 표현(이상·초과·미만·이내)
- 판이 다르면 같은 작업의 ID·절 번호·기준·승인이 달라지는 경우
- 문서가 정하지 않은 것(현재 상태, 적용 설비 범위)

## 완료 판정 원칙

두 작업 모두 각 항목이 원문 절과 문장으로 이어지고, 포털 표시와의 대조 결과가 일치 / 표현 다름 / 포털에서 찾지 못함으로 구별되어 있으면 됩니다. 판 차이는 어느 판의 어느 문장인지와 함께 적습니다. 기준값과 현재 값이 섞이지 않아야 합니다. 포털에서 보지 못한 것을 추정으로 채우지 않습니다.

## 저장할 결과

`결과/대조_기록.md`

{SAVE}
다음 실습에서는 이렇게 대조한 지식을 원문에서 직접 추출하는 기능을 만듭니다.
''')
    write(folder / '입력/README.md', '이 실습은 앞 단계 결과가 필요 없습니다. 대조 대상은 자료/원문의 HM-8과 수업용 포털의 등록 지식입니다.\n')
    write(folder / '결과/README.md', '대조_기록.md를 여기에 작성합니다.\n')
    table = '| 구분 | 원문 절 | 원문 문장(그대로) | 포털에서 본 표현과 위치 | 대조 결과 | 작업 전 확인할 현재 값과 읽을 곳 |\n|---|---|---|---|---|---|\n| 적용 조건 | | | | | |\n| 금지·제한 | | | | | |\n| 완료 기준 | | | | | |\n| 승인 | | | | | |\n'
    write(folder / '결과/대조_기록.md', f'''# 매뉴얼 원문과 포털 지식 대조 기록

- 확인 일시:
- 포털에서 연 화면:
- 대조한 원문 판과 SHA-256 앞 12자리:
- 포털 지식이 그 판인지 확인한 방법:

대조 결과는 일치 / 표현 다름(무엇이) / 포털에서 찾지 못함 중 하나로 적습니다. 한 구분에 항목이 여럿이면 행을 늘립니다.

## 1. 팬 최대 운전

{table}
## 2. 쿨러 핀 세척

{table}
## 3. 다른 판과의 차이

| 작업 | 다른 판의 ID·절 | 다른 판의 문장(그대로) | 대조한 판의 문장(그대로) | 작업 전 확인이 어떻게 달라지는가 |
|---|---|---|---|---|

## 4. 기준값과 현재 값

| 항목 | 문서의 기준값과 절 | 현재 값을 읽을 곳 | 관찰한 현재 값과 시각(또는 미확인) |
|---|---|---|---|

## 5. 적용 범위를 정한 것

| 원문 문장(그대로) | 정한 적용 범위 | 근거 | 다르게 정하면 바뀌는 것 |
|---|---|---|---|

## 6. 남은 질문

''')
    guide(folder, title, intro, [
        ('시작하기', '<p>압축을 푼 폴더를 VS Code에서 열고 <a href="START.md">START.md</a>를 읽으세요. 이번 실습은 포털 관찰과 기록이며 코드를 만들지 않습니다.</p><pre>자료/문서_목록.csv   HM-8의 판·상태·해시\n자료/원문/          문서 목록에 파일이 있는 판\n결과/대조_기록.md   작성할 기록</pre><p>두 원문을 나란히 보려면 탐색기에서 두 파일을 함께 선택하고 마우스 오른쪽 버튼 → <b>선택한 항목 비교</b>를 누릅니다.</p>'),
        ('요구 정하기', '<p>문서 목록을 보고 어느 판을 포털 지식과 대조할지 먼저 정하고 그 이유를 적으세요. 두 작업(팬 최대 운전, 쿨러 핀 세척)에 대해 무엇을 확인해야 작업을 시작할 수 있는지 원문에서 찾습니다. 절차 단계만 보지 말고 그 작업을 가리키는 다른 절도 찾습니다.</p>'),
        ('포털에서 대조하기', '<p>포털 왼쪽 메뉴의 지식 묶음에서 <b>지식 지도</b>를 열고 조치 방법 칸에서 두 작업을 찾으세요. 화면에 보이는 단계·조건·근거 표시를 기록하고 원문 문장과 나란히 적습니다. <b>지식 관리</b>에서는 HM-8 등록 여부만 확인합니다.</p><p class="check">매뉴얼 등록·미리보기·에이전트 추출 요청·적재는 누르지 않습니다. 직접 추가 적재는 마지막 교대 실습에서 제공 보충 매뉴얼로 합니다.</p>'),
        ('결과 확인하기', '<ul><li>각 항목이 원문 절과 원문 문장으로 이어지나요?</li><li>절차 밖의 절에 있는 조건도 찾았나요?</li><li>경계 표현을 원문 그대로 옮겼나요?</li><li>다른 판과의 차이를 어느 판의 어느 문장인지와 함께 적었나요?</li><li>원문만으로 적용 범위가 정해지지 않은 문장을 어떻게 처리했는지, 다르게 정하면 무엇이 바뀌는지 적었나요?</li><li>문서의 기준값과 작업 직전에 읽을 현재 값을 다른 칸에 적었나요?</li></ul><p class="check">포털에서 찾지 못한 항목은 찾지 못했다고 적습니다. 추정으로 채운 대조는 확인한 대조가 아닙니다.</p>'),
        ('저장하기', '<p>결과/대조_기록.md를 저장하고 다시 열어 확인하세요. 보관할 결과는 USB 또는 개인 클라우드에 복사합니다.</p><p>다음 실습은 이 대조를 원문에서 직접 추출하는 기능으로 이어집니다. 다음 실습은 이 기록 없이도 시작할 수 있습니다.</p>')])
    return folder, title


# ---------------------------------------------------------------- 실습4 지식 추출
def build_extract():
    folder = LABS / EXTRACT
    reset(folder)
    data.write_all(folder, data.ALL)
    rules_file(folder, ['추출 함수는 자료/원문의 Markdown만 읽는다. 이번 랩에서는 LLM·외부 API를 호출하지 않고 접속 키를 폴더에 두지 않는다.',
                        '입력/비교용_추출결과/는 비교 자료다. 이 파일을 읽어 후보를 만들거나 결과로 복사하지 않는다.',
                        'quote는 원문 문자열을 그대로 옮긴다. 원문에 없는 단계·조건·수치를 만들지 않는다.',
                        '어떤 문서·판·언어를 근거로 쓸지와 채택·수정·제외·보류는 사람이 결정한다. AI는 근거 대조를 도울 수 있지만 결정을 확정하지 않는다.',
                        '후보 파일 원본은 남기고 검토 결과는 별도 파일로 만든다.'])
    write(folder / '입력/출력_계약.md', CONTRACT)
    write(folder / 'check_candidates.py', CHECKER)
    bundle = json.loads(BUNDLE.read_text(encoding='utf-8'))['payload']
    hm8 = sha(folder / '자료/원문/HM-8_cooler-fan-manual.md')
    entry = bundle['documents'].get(hm8)
    if entry is None:
        raise KeyError(f'포털 승인 추출 묶음에 HM-8 정본({hm8[:12]})이 없습니다: {BUNDLE}')
    dump(folder / '입력/비교용_추출결과/HM-8_포털승인추출.json', {
        '설명': '포털 수업용 승인 추출 묶음의 HM-8 항목 발췌. 포털 에이전트가 추출하고 검토를 거친 결과이며 이번 랩의 추출 실행 결과가 아니다. 출력 계약도 다르다(절·절차·지식 연결 형식).',
        'bundle_revision': bundle['revision'], 'extraction_version': bundle['extraction_version'],
        'source_file': entry['filename'], 'source_sha256': hm8,
        'origin': {k: entry['origin'][k] for k in ['reviewer', 'review_method', 'review_notes'] if k in entry['origin']},
        'proposal': entry['proposal']})
    write(folder / '입력/비교용_추출결과/README.md', f'''# 비교용 추출 결과 — 실제 추출 실행이 아님

`HM-8_포털승인추출.json`은 포털 수업용 승인 추출 묶음(판본 {bundle['revision']}, 추출 판 {bundle['extraction_version']})의 HM-8 항목(현행 1.1판)을 그대로 옮긴 것입니다. 포털 에이전트가 추출하고 사람이 검토한 결과이며, 이 폴더에서 실행한 추출이 아닙니다. 형식도 이번 출력 계약과 다릅니다. 다른 문서의 비교용 결과는 없습니다.

쓰는 곳:

- 직접 만든 추출 결과와 비교해 빠진 단계·조건을 찾는 참고 자료
- 포털 화면 대조가 막혔을 때 포털에 등록된 지식이 무엇인지 확인하는 대안

이 파일을 읽어 후보를 만들거나 결과로 복사하면 추출을 실행한 것이 아닙니다. 비교한 내용은 결과/검토_기록.md의 비교 절에 적습니다.
''')
    write(folder / '입력/README.md', '''# 입력

- `출력_계약.md`: 추출 후보와 검토 결과의 JSON 모양과 필드의 뜻.
- `비교용_추출결과/`: 포털 승인 추출 결과(HM-8 현행판, 비교용). 실제 추출 실행이 아닙니다.

이 실습은 앞 단계 결과 없이 시작할 수 있습니다. 실습3의 대조 기록을 쓰고 싶으면 `입력/내_대조기록/`처럼 별도 폴더에 복사해 참고합니다.
''')
    write(folder / '결과/README.md', '추출 함수(extract.py), 후보(후보/), 검토 결과(검토/), 검토_기록.md를 여기에 둡니다. 제공된 빈 틀은 보관 없이 바로 채워도 됩니다.\n')
    write(folder / '결과/검토_기록.md', '''# 추출 후보 검토 기록

- 검토자 / 검토 일시:
- 실행한 명령과 출력 요약(후보 수·종류별 수·검사 결과):

## 1. 정한 것

| 정할 것 | 정한 내용 | 근거(문서·절) | 다르게 정하면 바뀌는 후보·수 |
|---|---|---|---|
| 문서 목록의 판·상태별 처리(원문 근거) | | | |
| 영문 원본과 번역이 함께 있을 때 인용 근거(원문 근거) | | | |
| 한 문장·한 행에 조건·기준이 여럿일 때 후보를 나누는 단위 | | | |

## 2. 실행 전에 적은 기대 결과와 실제

| 원문 절·문장 | 기대한 후보(종류·값) | 실제 후보 id와 내용 | 일치 여부 |
|---|---|---|---|

## 3. HM-8 현행판 후보 결정

| 후보 id | 종류 | 원문 절 | 결정 | 이유와 원문 근거 | 수정 전 → 후 |
|---|---|---|---|---|---|

## 4. 원문에 있는데 후보가 없는 것

| 문서·절 | 원문 문장 | 빠진 종류 | 처리(추출 규칙 보완 / 검토자 추가 / 남은 질문) |
|---|---|---|---|

## 5. 다른 문서에 다시 실행

| 문서 | 실행 명령 | 후보 수 | 누락 수 | 근거 없는 생성 수 | 고친 점과 다시 실행한 결과 |
|---|---|---|---|---|---|

| 사례 | 원문 문장 | 추출 결과 | 판정(정상 / 누락 / 근거 없는 생성 / 종류 오류) | 고친 점 |
|---|---|---|---|---|

## 6. 비교용 추출 결과와 비교

| 항목 | 내 추출 결과 | 비교용 결과 | 차이와 판단 |
|---|---|---|---|

## 7. 선택한 작업의 준비·금지·완료

- 선택한 작업:

| 구분 | 문서·후보 id | 원문 절 | 절차 밖·다른 문서에서 찾은 조건이면 그 근거 |
|---|---|---|---|

## 8. 남은 질문

''')
    title = '현장 문서 묶음에서 작업 지식 후보를 추출하고 검토하기'
    intro = '판·상태·언어가 다른 현장 문서 묶음에서 작업 순서·조건·금지·완료 기준·기준값을 문서 ID·절·인용과 함께 뽑는 추출 기능을 만들고, 사람이 후보를 검토한 뒤 다른 문서에 다시 적용합니다.'
    cmd = '''python check_candidates.py
python 결과/extract.py 자료/원문/HM-8_cooler-fan-manual.md --doc HM-8 --out 결과/후보/HM-8.json
python check_candidates.py 결과/후보/HM-8.json
python 결과/extract.py 자료/원문/PM-02_powerpack-pm-checklist.md --doc PM-02 --out 결과/후보/PM-02.json
python 결과/extract.py 자료/원문/OEM-HPP45A-MM_maintenance-excerpt.md --doc OEM-HPP45A-MM --out 결과/후보/OEM-HPP45A-MM.json
python check_candidates.py 결과/검토/HM-8_검토.json
python check_candidates.py'''
    start(folder, f'''# {title}

{intro} 포털에서는 에이전트가 이 일을 했습니다. 이번에는 같은 일을 VS Code에서 직접 구현하고 결과를 원문으로 검증합니다.

자료는 교육용 가상 자료입니다(공개 현업 문제 유형을 따라 생성). 문서 한두 개는 눈으로 읽을 수 있지만, 여러 문서·판·언어의 후보 수백 개를 원문과 맞추는 일은 코드로 대조해야 끝까지 할 수 있습니다.

## 출발 상태

`자료/문서_목록.csv`에 등록된 문서입니다.

{doc_table(folder)}

- `입력/출력_계약.md`: 후보와 검토 결과의 JSON 모양과 필드의 뜻. 이미 정해져 있습니다.
- `check_candidates.py`: 인자 없이 실행하면 지금 어느 단계까지 했는지 보여 주고, 파일을 주면 계약 구조와 **인용이 원문 절 안에 그대로 있는지**를 검사합니다. 빠진 지식, 종류 판단, 어떤 문서를 근거로 쓸지는 검사하지 않습니다.
- `입력/비교용_추출결과/`: 포털 승인 추출 결과(HM-8 현행판). 비교용이며 실제 추출 실행이 아닙니다.
- 비어 있는 것: 추출 함수, 후보, 검토 결과, 검토 기록.

## 이번에 구현할 범위

1. `결과/extract.py`: 원문 Markdown을 읽어 계약대로 후보를 내는 함수와 실행 명령. API 키 없이 로컬에서 실행되는 규칙 기반 Python으로 만듭니다. 외부 모델 호출은 이번 범위가 아닙니다.
2. HM-8 현행판으로 실행하고 검사기로 인용을 확인한 뒤 원문과 나란히 놓고 검토합니다. 아래 4번에서 고른 작업이 있는 절과 그 작업이 가리키는 절의 후보는 사람이 원문과 한 줄씩 대조해 채택·수정·제외·보류를 정하고, 시간 안에 보지 못한 나머지 후보는 「보류」로 두고 이유에 「미검토」를 적습니다. 결과는 `결과/검토/HM-8_검토.json`(계약 3절)과 `결과/검토_기록.md`에 남기고, 대조한 절에서 원문에 있는데 빠진 것도 적습니다.
3. 같은 함수를 **다른 문서**에 다시 실행합니다. PM-02와 제조사 지침 발췌는 반드시, HI-01·PR-07은 필요하면. 누락과 근거 없는 생성을 세고, 추출 규칙을 고쳐 다시 실행해 수가 어떻게 바뀌는지 기록합니다.
4. 다음 실습에서 카드로 만들 작업({', '.join(TASKS)}) 중 하나를 골라 그 작업의 준비·금지·완료 후보를 문서를 가리지 않고 모아 둡니다.

## 원문에서 근거를 찾아 정할 것

문서 목록이나 문서 머리말에 기준이 적혀 있습니다. 그 문장을 직접 찾아 처리와 근거(문서·절·문장)를 `결과/검토_기록.md` 1절에 적습니다.

- 문서 목록의 상태(현행·폐기·개정 요청·보충·참고)가 다른 문서를 추출과 검토에서 각각 어떻게 다룰지
- 영문 원본과 사내 번역이 함께 적힌 문서에서 무엇을 인용 근거로 쓸지

## 정할 것 — 정답이 정해져 있지 않으며 결정과 근거를 기록합니다

- 원문의 한 문장이나 표의 한 행에 조건·기준값이 여럿 들어 있을 때 후보를 어느 단위로 나눌지. 나눈 후보 하나하나가 다음 실습에서 검토·적재·카드 항목의 단위가 됩니다.

정한 내용에 따라 후보의 수와 모양이 달라집니다. 무엇이 달라지는지 `결과/검토_기록.md` 1절에 적습니다.

{CYCLE}
## 확인할 사례의 종류

- 문서마다 절·절차의 ID 표기와 쓰는 언어·단위가 다른 경우
- 한 원문 문장이나 표의 한 행에 여러 지식이 들어 있는 경우
- 다른 절·다른 절차·다른 문서를 가리키는 문장
- 판이 다른 같은 문서, 같은 항목을 다르게 정한 두 문서
- 한 문서에 맞춘 규칙이 다른 문서에서 놓치는 것과 없는 것을 만들어 내는 것

## 실행 명령

```
{cmd}
```

## 완료 판정 원칙

- 후보 파일이 이 폴더의 추출 함수를 실제로 실행해 만든 것이어야 합니다. 비교용 결과를 옮긴 것은 추출이 아닙니다.
- 검사기 통과는 출발점입니다. 원문과 대조해 결정과 이유를 남겼고, 빠진 것을 찾았고, 다른 문서에서 드러난 문제를 수치로 기록·수정했는지, 정할 것을 정하고 근거를 남겼는지로 판단합니다.
- 맞게 나온 결과를 일부러 망가뜨려 고치는 과정을 만들 필요는 없습니다.

## 저장할 결과

`결과/extract.py`, `결과/후보/`(HM-8과 다른 문서 둘 이상), `결과/검토/HM-8_검토.json`, `결과/검토_기록.md`

{SAVE}''')
    guide(folder, title, intro, [
        ('시작하기', '<p>압축을 푼 폴더를 VS Code에서 열고 <a href="START.md">START.md</a>와 <a href="입력/출력_계약.md">입력/출력_계약.md</a>를 읽으세요.</p><pre>자료/문서_목록.csv   문서의 판·상태·해시\n자료/원문/         문서 묶음(현행·폐기·보충·제조사 발췌)\n입력/출력_계약.md   후보·검토 JSON 모양\n입력/비교용_추출결과/  포털 승인 추출(비교용, 실제 실행 아님)\ncheck_candidates.py  단계 점검·계약·인용 검사기\n결과/            이번에 만들 것</pre><p>터미널에서 <code>python check_candidates.py</code>를 실행해 지금 비어 있는 단계를 확인하세요. AI에게는 먼저 문서 목록과 원문들을 읽고 문서끼리 무엇이 다른지 설명하게 합니다. 이때는 파일을 만들거나 바꾸지 말라고 함께 말합니다.</p>'),
        ('요구 정하기', '<p>목표, 입력, 제약(원문 그대로의 인용, LLM 호출 없음, 비교용 결과 사용 금지), 확인할 사례를 자기 말로 정리하세요. 실행 전에 HM-8 원문에서 기대 후보 2~3건(절·종류·값)을 직접 골라 검토 기록 2절에 적습니다. 그중 하나는 한 문장이나 표의 한 행에 기준값이나 조건이 둘 이상 들어 있는 줄로 고릅니다.</p><p>START의 「원문에서 근거를 찾아 정할 것」 두 가지는 문서 목록과 문서 머리말에서 근거 문장을 찾아 적고, 「정할 것」(한 문장·한 행의 여러 조건을 후보로 나누는 단위)은 다음 실습에서 그 후보를 어떻게 쓸지 생각해 직접 정합니다. AI의 계획이 이것을 대신 정했으면 되돌려 묻습니다.</p>'),
        ('AI와 만들기', '<p>작은 단위로 구현하고 실행합니다. 한 부분을 만들 때마다 HM-8로 실행해 출력을 원문과 비교한 뒤 다음으로 넘어갑니다. 완료라고 하면 실행한 명령과 출력 원문을 붙여 달라고 하세요.</p><p>수정 요청에는 어떤 원문 문장에서, 무엇을 기대했고, 실제로 무엇이 나왔는지를 함께 주세요. 파일 이름은 백틱(`)으로 감싸 보냅니다.</p>' + ASK),
        ('결과 확인하기', f'<pre>{html.escape(cmd)}</pre><p><b>판단 원칙</b>: 검사기는 인용이 원문 절 안에 그대로 있는지와 계약 구조만 확인합니다. 지식이 맞는지, 빠졌는지, 어느 문서를 근거로 삼을지는 원문과 문서 목록으로 판단합니다.</p><ul><li>인용 검사에서 실패한 후보는 원문을 바꾸지 말고 추출 함수를 고칩니다.</li><li>실행 전에 적은 기대 후보가 실제로 나왔는지 대조합니다.</li><li>다른 문서에 다시 실행하면 후보 수만이 아니라 누락과 근거 없는 생성을 사례로 세고, 고친 뒤 다시 센 수와 비교합니다.</li><li>정한 것을 바꾸면 어떤 후보가 달라지는지 한 번 확인해 기록합니다.</li></ul><p class="check">비교용 추출 결과와 차이가 나면 어느 쪽이 원문과 맞는지 원문으로 판단합니다. 비교용 결과가 정답 목록은 아닙니다.</p>'),
        ('저장하기', '<p>결과/extract.py, 결과/후보/, 결과/검토/, 결과/검토_기록.md를 저장하고 다시 열어 확인하세요. 마지막에 <code>python check_candidates.py</code>를 인자 없이 실행해 「완료 아님」 항목이 남지 않았는지 봅니다.</p><p>보관할 결과는 USB 또는 개인 클라우드에 복사하세요. 다음 실습은 강사가 검토한 결과로 시작하므로 이번 결과가 없어도 진행할 수 있습니다.</p>')])
    return folder, title


# ---------------------------------------------------------------- 실습5 그래프 반영과 작업 확인 카드
def build_card():
    folder = LABS / CARD
    reviewed = {doc: REF / '검토결과' / f'{doc}_검토.json' for doc in REVIEWED}
    lost = [str(p) for p in reviewed.values() if not p.is_file()]
    if lost:
        raise FileNotFoundError('앞 단계 완성 검토본이 없습니다. reference/session3_docs/review_reference.py를 먼저 실행하세요: ' + ', '.join(lost))
    reset(folder)
    data.write_all(folder, data.ALL, records=True)
    rules_file(folder, ['DB 작업은 lab_db.py가 만든 이 폴더 전용 DB에서만 한다. 전체 삭제문을 쓰지 않는다.',
                        'approved 후보만 적재한다. 제외·보류 후보는 적재하지 않고 기록에 남긴다.',
                        '앞 단계 모델의 기존 ID를 새로 만들거나 바꾸지 않는다. 연결할 기존 ID가 없으면 만들지 말고 남은 질문으로 적는다.',
                        '작업 확인 카드는 현재 설비 상태·재고 사용·승인을 대신 정하지 않는다. 현재 값과 승인이 필요한 것은 그렇게 표시한다.',
                        '작업지시 서술과 재고 현황은 기록이다. 기록을 고치거나 작업지시를 닫지 않는다.'])
    shutil.copy2(HERE / 'lab_db.py', folder / 'lab_db.py')
    write(folder / 'lab_cypher.py', LAB_CYPHER)
    write(folder / 'check_candidates.py', CHECKER)
    write(folder / 'check_card.py', CARD_CHECK)
    write(folder / '입력/출력_계약.md', CONTRACT)
    schema, graph = reference_model(True)
    dump(folder / '입력/모델/schema.json', schema)
    dump(folder / '입력/모델/graph.json', graph)
    shutil.copytree(MODEL_DATA, folder / '입력/모델/자료', dirs_exist_ok=True)
    files = {r['파일']: r for r in register_rows(folder) if r['파일']}
    lines = []
    (folder / '입력/검토결과').mkdir(parents=True, exist_ok=True)
    for doc, path in reviewed.items():
        review = json.loads(path.read_text(encoding='utf-8'))
        row = files.get(review['source_file'])
        if row is None or row['SHA-256'] != review['source_sha256']:
            raise ValueError(f'검토본의 원문 해시가 문서 목록과 다릅니다: {path}')
        shutil.copyfile(path, folder / '입력/검토결과' / path.name)
        counts = {}
        for c in review['candidates']:
            counts[c['status']] = counts.get(c['status'], 0) + 1
        lines.append(f'| `{path.name}` | {doc} {row["판"]}판({row["상태"]}) | {counts.get("approved", 0)} | {counts.get("excluded", 0)} | {counts.get("pending", 0)} |')
    wo = len([l for l in (folder / '자료/기록/작업지시_서술.csv').read_text(encoding='utf-8').splitlines()[2:] if l.strip()])
    write(folder / '입력/README.md', f'''# 입력 — 앞 단계 완성 상태

- `모델/schema.json`·`모델/graph.json`: 2회차 완성 모델(설비·구성요소·센서·물리량·부품·공급사). `python lab_cypher.py model`로 랩 DB에 적재합니다. 원자료는 `모델/자료/`.
- `검토결과/`: 실습4의 강사 검토본(앞 단계 완성 상태). 학생의 검토 결과가 아니라 시작용 제공본입니다.

| 파일 | 원문 | approved | excluded | pending |
|---|---|---|---|---|
{chr(10).join(lines)}

- `출력_계약.md`: 검토 결과 JSON의 필드 뜻.

개인 실습4 결과를 쓰려면 제공 입력을 그대로 두고 `입력/내_검토결과/`처럼 별도 폴더에 복사한 뒤 `python check_candidates.py <파일>`로 계약을 확인하세요. 원문 해시가 `자료/문서_목록.csv`와 같아야 합니다.
''')
    write(folder / '결과/README.md', '적재문(load.cypher), 조회문(query.cypher), 작업확인카드_<작업 ID>.md, 구축_기록.md와 직접 만든 생성 코드를 여기에 둡니다. 제공된 빈 틀은 보관 없이 바로 채워도 됩니다.\n')
    write(folder / '결과/구축_기록.md', '''# 온톨로지 구축 기록

- 확인 일시 / 사용한 랩 DB 주소(인증값 제외):

## 1. 질문

## 2. 정한 것

| 정할 것 | 정한 내용 | 근거(문서·절·자료) | 다르게 정하면 바뀌는 카드 항목 |
|---|---|---|---|
| 지난 시행으로 볼 작업지시의 범위 | | | |
| 부품 준비 수량을 세는 기준 | | | |

## 3. 모델 확장

| 새 종류·관계 | 뜻 | 연결한 기존 ID | 근거(원문 절·자료) |
|---|---|---|---|

## 4. 입력 문서와 검토 결과

| 파일 | 판·상태(SHA-256 앞 12자리) | 적재한 approved 수 | 적재하지 않은 수(제외·보류) |
|---|---|---|---|

## 5. 적재와 반복 적재

| 시점 | 노드 수 | 관계 수 | 메모 |
|---|---|---|---|
| 모델 적재 후 | | | |
| 1차 적재 후 | | | |
| 같은 적재 재실행 후 | | | |

## 6. 조회와 카드

| 질문·사례 | 실행 전 기대 | 조회문 | 실제 결과 요약 | 원문·자료 대조 |
|---|---|---|---|---|

## 7. 답할 수 있는 것과 없는 것

| 질문 | 그래프로 답함 / 현재 값 필요 / 승인 필요 / 원문에 없음 | 근거 |
|---|---|---|
''')
    title = '검토한 지식을 랩 그래프에 연결하고 작업 확인 카드 만들기'
    intro = '여러 문서에서 검토를 마친 지식을 2회차 모델의 기존 ID에 연결해 별도 랩 DB에 적재하고, 작업지시 기록·재고 현황과 함께 선택한 작업의 준비·금지·완료 조건과 원문 출처를 모은 작업 확인 카드를 조회 결과로 만듭니다.'
    cmd = '''python check_card.py
python lab_db.py
python lab_cypher.py model
python lab_cypher.py count
python lab_cypher.py run 결과/load.cypher
python lab_cypher.py count
python lab_cypher.py run 결과/load.cypher
python lab_cypher.py count
python lab_cypher.py run 결과/query.cypher
python check_card.py'''
    heads = '\n'.join(f'- `## {h}`' for h in CARD_HEADINGS)
    start(folder, f'''# {title}

{intro}

자료는 교육용 가상 자료입니다(공개 현업 문제 유형을 따라 생성). 작업지시 서술 {wo}행과 문서 여러 개의 지식 수백 건을 작업마다 맞추는 일은 눈으로 끝낼 수 없고, 그래프 조회와 코드 대조로 해야 합니다.

## 출발 상태

- `입력/모델/`: 2회차 완성 모델과 원자료. 이번 과제의 답이 아니라 이미 끝난 앞 단계입니다.
- `입력/검토결과/`: 실습4의 검토 완료본(문서별). `status`가 `approved`인 후보만 적재 대상입니다.
- `자료/문서_목록.csv`와 `자료/원문/`: 문서의 판·상태와 원문. 카드의 출처를 다시 확인할 때 씁니다.
- `자료/기록/작업지시_서술.csv`: CMMS 작업지시 내보내기({wo}행). 현장 작성자가 쓴 그대로입니다.
- `자료/기록/재고_현황.csv`: ERP 재고 내보내기(현재고·예약·입고 예정).
- `lab_db.py`: 이 폴더 전용 Neo4j 컨테이너를 준비합니다(Docker 필요). 포털 DB가 아닙니다.
- `lab_cypher.py`: 랩 DB에 Cypher 파일을 실행하고 노드·관계 수를 셉니다. 앞 단계 모델 적재(`model`)도 합니다.
- `check_card.py`: 지금 어느 단계까지 했는지와 카드의 형식·인용을 검사합니다. 카드 내용이 맞는지는 판정하지 않습니다.
- 비어 있는 것: 모델 확장, 적재문, 조회문, 작업 확인 카드, 구축 기록.

## 이번에 구현할 범위

1. 문서·판·절·절차·검토한 지식을 담을 모델 확장을 정하고, 기존 모델의 어떤 ID에 무엇을 근거로 연결할지 정합니다. 기존 ID는 그대로 둡니다.
2. `결과/load.cypher`: approved 후보만, 원문 출처(문서·판·절·인용·검토 결정)와 함께 적재합니다. 같은 파일을 두 번 실행해도 노드·관계가 늘지 않아야 하므로 적재문에는 지우는 문장(DELETE)을 두지 않습니다. 검토 JSON에서 적재문을 만드는 코드를 AI와 함께 작성해도 됩니다.
3. `결과/query.cypher`: 작업 하나의 준비·금지·완료 조건과 출처를 찾는 조회. 절차 밖의 절, 다른 절차, 다른 문서에 있는 조건도 따라가야 합니다.
4. 작업 확인 카드: 대상 작업은 {', '.join(TASKS)}입니다. 하나를 골라 `결과/작업확인카드_<작업 ID>.md`를 만들고, 같은 방법으로 **다른 작업 하나 이상**의 카드도 만듭니다. 원문이 제공하지 않는 작업을 물으면 카드 대신 「결과 없음」이 나와야 합니다.
5. 카드의 지난 시행 기록과 부품 준비는 `자료/기록/`의 두 파일에서 코드로 찾아 원자료의 작업지시 번호·품번과 함께 적습니다.
6. `결과/구축_기록.md`: 질문·모델·문서·추출/검토·적재·조회 결과를 연결해 남깁니다.

## 정할 것 — 정답이 정해져 있지 않으며 결정과 근거를 기록합니다

- 작업지시 서술의 어떤 행을 그 작업의 지난 시행으로 볼지
- 카드의 부품 준비 수량을 재고 현황의 어느 칸으로 셀지

정한 내용에 따라 카드가 달라집니다. 무엇이 달라지는지 `결과/구축_기록.md` 2절에 적습니다.

## 작업 확인 카드의 출력 계약

카드는 아래 제목을 이 순서로 가집니다. 해당하는 것이 없으면 「없음」과 이유를 적습니다.

{heads}

- 원문에서 온 항목은 원문 절, 「원문 인용」(원문 그대로), 지식 후보 id를 함께 적습니다. 작업지시·재고 기록에서 온 것은 작업지시 번호·품번과 「기록 그대로」를 적습니다.
- `대상 작업`에는 작업 ID·이름, 문서 ID·판·상태, 원문 SHA-256 앞 12자리를 적습니다.
- `작업 직전 확인할 현재 값`은 문서의 기준값과 구분합니다. 그래프에 없는 값은 「현재 값 필요」로 표시합니다.
- `부품 준비`는 품번·필요 수량·센 수량과 센 기준, 재고 현황의 기준 시각을 적습니다.
- `지난 시행 기록`은 작업지시 번호·설비·완료일과 그 기록이 완료 기준을 보여 주는지를 적습니다.
- `승인`은 원문에 적힌 승인 역할입니다. 카드가 승인을 대신하지 않습니다.
- `남은 질문`에는 원문이 정하지 않은 것, 적재하지 않은(보류·제외) 후보 때문에 답하지 못하는 것, 기존 모델에 연결할 ID가 없는 것, 기록끼리 맞지 않는 것을 적습니다.

## 확인할 사례의 종류

- 선택한 작업과 **다른 작업**에도 같은 조회·생성으로 카드가 만들어지는가
- 원문이 제공하지 않는 절·작업을 물었을 때 「결과 없음」으로 구별되는가
- **같은 적재를 다시 실행**해도 노드·관계 수가 같은가(실제 count 수치로)
- 제외·보류 후보가 DB와 카드에 들어가지 않았는가
- 기록에 「완료」라고 적혀 있어도 완료 기준을 보여 주지 않는 시행
- 부품의 공급 정보·재고와 작업 조건을 어디까지 함께 답할 수 있고, 현재 값·승인 없이 결정할 수 없는 것은 무엇인가

{CYCLE}
## 실행 명령

```
{cmd}
```

Neo4j Browser로 확인하려면 `lab_db.py`가 연 주소에서 Protocol은 bolt://, Connection URL은 출력된 127.0.0.1:포트, 사용자 neo4j, 비밀번호는 비워 둡니다.

## 완료 판정 원칙

- 기존 모델의 노드·관계 수는 모델 적재 직후 값에서 이번 적재로 늘어난 만큼만 늘고, 재적재 뒤에는 변하지 않아야 합니다.
- 카드의 항목은 모두 원문 절과 인용, 작업지시 번호, 품번으로 돌아갈 수 있어야 하고, 원문과 대조해 빠진 조건이 없어야 합니다.
- 카드가 답하지 못하는 것을 추정으로 채우지 않고 남은 질문으로 둡니다. 개수만 맞고 답·출처가 틀린 결과는 완료가 아닙니다.
- `check_card.py`의 「완료 아님」 항목이 남지 않아야 합니다. 이것은 형식 검사이며 내용 판정은 원문·자료 대조로 합니다.

## 저장할 결과

`결과/load.cypher`, `결과/query.cypher`, `결과/작업확인카드_<작업 ID>.md`(둘 이상), `결과/구축_기록.md` (생성 코드가 있으면 함께)

{SAVE}
다음 회차에는 이 지식으로 점검 요청을 만듭니다.
''')
    guide(folder, title, intro, [
        ('시작하기', '<p>압축을 푼 폴더를 VS Code에서 열고 <a href="START.md">START.md</a>를 읽으세요. Docker Desktop이 실행 중이어야 합니다.</p><pre>python check_card.py\npython lab_db.py\npython lab_cypher.py model\npython lab_cypher.py count</pre><p>「랩 DB 준비 완료」가 나온 뒤 앞 단계 모델을 적재하고 노드·관계 수를 구축 기록에 적어 두세요. 이 수가 기존 모델을 보존했는지 판단하는 기준입니다.</p><p>AI에게 먼저 입력/의 모델·검토 결과, 자료/기록의 두 파일, 출력 계약을 읽고 무엇이 있는지 설명하게 하세요. 이때는 파일을 만들거나 바꾸지 말라고 함께 말합니다.</p>'),
        ('요구 정하기', '<p>목표, 입력, 제약(approved만, 기존 ID 보존, 반복 적재 무중복, 전체 삭제 금지, 기록 수정 금지), 확인할 사례를 자기 말로 정리하세요. 고른 작업에 대해 원문과 작업지시 서술에서 기대 결과 2~3건(카드에 들어가야 할 조건 하나, 지난 시행 하나, 필요한 부품 하나)을 직접 찾아 구축 기록 6절에 먼저 적습니다.</p><p>START의 「정할 것」 두 가지는 원문·자료를 보고 직접 정합니다. AI의 계획에서 새 종류·관계와 기존 ID 연결의 근거가 원문·자료에 있는지도 봅니다.</p>'),
        ('AI와 만들기', '<p>작은 단위로 진행합니다. 한 부분을 적재하거나 조회할 때마다 count와 조회 결과를 확인합니다. 완료라고 하면 실행한 명령과 출력 원문을 붙여 달라고 하세요.</p><p>수정 요청에는 실행한 문장, 기대한 결과, 실제 결과(오류 메시지·수치)를 함께 주세요. 파일 이름은 백틱(`)으로 감싸 보냅니다.</p>' + ASK),
        ('결과 확인하기', f'<pre>{html.escape(cmd)}</pre><p><b>판단 원칙</b>: 수치는 기존 모델 보존과 무중복을, 카드의 출처와 원문·자료 대조는 내용을 판정합니다. 둘 중 하나만으로는 완료가 아닙니다.</p><ul><li>같은 load.cypher를 두 번 실행한 뒤 count가 같아야 합니다.</li><li>모델 적재 직후의 종류별 수가 이번 적재 뒤에도 같아야 합니다.</li><li>카드의 각 항목에서 원문 절을 열어 인용을 찾을 수 있어야 합니다. <code>check_card.py</code>가 인용과 작업지시 번호를 원자료와 대조합니다.</li><li>실행 전에 적은 기대 결과가 카드에 있는지 대조합니다.</li><li>정한 것을 바꾸면 카드의 어느 항목이 달라지는지 한 번 확인해 기록합니다.</li><li>원문에 없는 작업을 조회하면 결과 없음이 나오고, 그렇게 기록되어야 합니다.</li></ul><p class="check">현재 운전 상태·누적 운전 시간·지금 쓸 수 있는 부품처럼 작업 직전에 확인해야 하는 것과 승인은 카드가 정하지 않습니다. 「현재 값 필요」·「승인 필요」로 남깁니다.</p>'),
        ('저장하기', '<p>결과 파일을 저장하고 다시 열어 확인하세요. 랩 DB의 내용은 컨테이너 안에 있으므로 적재문·조회문·카드·구축 기록 파일이 결과입니다. 보관할 결과는 USB 또는 개인 클라우드에 복사하세요.</p><p>다음 회차는 이 지식으로 점검 요청을 만듭니다. 다음 실습도 독립 시작본을 제공합니다.</p>')])
    return folder, title


def main():
    built = [('practical-03-manual',) + build_manual(), ('practical-03-extract',) + build_extract(), ('practical-03-card',) + build_card()]
    entries = []
    for lab_id, folder, title in built:
        archive = pack(folder)
        entries.append({'id': lab_id, 'course': '실전반', 'session': '온라인 03회차', 'title': title, 'version': VERSION,
                        'folder': '03회차/랩/' + folder.name, 'path': archive.relative_to(ROOT).as_posix(), 'sha256': sha(archive)})
    index = HERE / 'package-index.json'
    catalog = json.loads(index.read_text(encoding='utf-8'))  # 다른 생성기의 항목을 보존하고 이 세 항목만 바꾼다
    ids = {e['id'] for e in entries}
    catalog['labs'] = [x for x in catalog['labs'] if x['id'] not in ids] + entries
    dump(index, catalog)
    for e in entries:
        print(f"{e['id']}: {e['path']} {e['sha256'][:12]}")


if __name__ == '__main__':
    main()
