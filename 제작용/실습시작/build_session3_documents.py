"""실전반 온라인3 문서 지식화 랩 세 개(매뉴얼 대조·지식 추출·그래프 반영과 작업 확인 카드)의 독립 시작본.

학생 폴더에는 환경·원자료·작업 규칙·START·구조 검사기·앞 단계 완성 상태만 둔다.
추출 함수·완성 후보·적재문·작업 카드 같은 이번 과제의 답은 reference/session3_docs/에만 있다.
실습5의 입력/검토결과는 실습4의 강사 참조 검토본(앞 단계 완성 상태)이다.
"""
from build_labs import ROOT, OUT, page, write, dump, pack, RULES, reference_model
from pathlib import Path
import csv
import hashlib
import html
import io
import json
import shutil

HERE = Path(__file__).resolve().parent
REF = HERE / 'reference/session3_docs'
SRC = ROOT / '문서/시스템/참조/수업_문서_원문'
BUNDLE = ROOT / 'common/hydcommon/course_extractions.json'
MODEL_DATA = OUT / '통합반/실습/02회차/랩/02일차_실습3_온톨로지설계/자료'
LABS = OUT / '실전반/실습/03회차/랩'
VERSION = '2026-10-28-s3-v1'
DOCS = [('HM-8', 'HM-8_cooler-fan-manual.md', '유압 파워유닛 쿨러 팬 정비 매뉴얼'),
        ('PM-02', 'PM-02_powerpack-pm-checklist.md', '유압 파워팩 정기 점검표와 시행 기준'),
        ('PR-07', 'PR-07_spare-parts-standard.md', '예비품 관리 · 구매 기준서')]
MANUAL = '03일차_실습3_매뉴얼검토'
EXTRACT = '03일차_실습4_지식추출'
CARD = '03일차_실습5_그래프반영'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reset(folder):
    """옛 `코드/` 구조와 이전 생성물을 지우고 새로 만든다(이 랩 폴더 안만)."""
    if not folder.is_dir() or folder.parent != LABS:
        raise FileNotFoundError(f'대상 랩 폴더가 아닙니다: {folder}')
    for child in folder.iterdir():
        shutil.rmtree(child) if child.is_dir() else child.unlink()


def sources(folder, ids):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator='\n')
    w.writerow(['문서 식별자', '파일', '제목', 'SHA-256', '판본 설명'])
    for doc, name, title in DOCS:
        if doc not in ids:
            continue
        src = SRC / name
        if not src.is_file():
            raise FileNotFoundError(f'승인 원문이 없습니다: {src}')
        dest = folder / '자료/원문' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        w.writerow([doc, name, title, sha(src), '포털 수업용 승인 원문과 같은 판(문서/시스템/참조/수업_문서_원문)'])
    write(folder / '자료/문서_목록.csv', buf.getvalue())


def rules_file(folder, extra):
    text = RULES + ''.join(f'- {line}\n' for line in extra)
    for name in ['AGENTS.md', 'CLAUDE.md', '.github/copilot-instructions.md']:
        write(folder / name, text)


CYCLE = '''## 작업 순서 — AI와 만드는 방법

1. **탐색만 요청하기**: AI에게 START.md와 관련 자료를 읽고 무엇이 이미 있고 무엇이 비었는지 설명하게 하세요. 이때는 파일을 만들거나 바꾸지 말라고 함께 말합니다.
2. **요구를 자기 말로 정리하기**: 목표·입력·지켜야 할 제약·확인할 사례를 짧게 적어 AI에 전달하세요.
3. **계획 검토하기**: AI가 낸 계획이 요구와 제약을 지키는지, 확인할 사례가 빠지지 않았는지 보고 고칠 점을 말한 뒤 진행하세요.
4. **작은 단위로 구현하기**: 한 기능을 만들고 실행해 본 뒤 다음 기능으로 넘어가세요.
5. **실행 결과를 원자료와 대조하기**: 검사 통과나 AI의 완료 메시지가 아니라 원문과 실제 출력으로 판단하세요.
6. **수정 요청은 근거와 함께**: 어떤 입력에서, 무엇을 기대했고, 실제로 무엇이 나왔는지를 함께 전달하세요.
7. **저장하고 다시 열기**: 결과 파일을 저장하고 다시 열어 내용을 확인하세요.
'''

ASK = '<details><summary>요청을 정리할 때 볼 항목</summary><p>만들 결과 / 읽을 자료 / 바꾸지 않을 범위 / 지켜야 할 출력 계약 / 성공을 확인할 사례 / 확인하지 못하면 어떻게 표시할지</p></details>'

SAVE = '''## 저장과 다음 실습

결과 폴더를 저장하고 다시 열어 확인하세요. 재부팅하면 학교 PC의 작업 폴더가 사라질 수 있으니 보관할 결과는 USB 또는 개인 클라우드에 복사하세요. 다음 실습도 독립 시작본을 제공하므로 개인 결과는 선택 입력입니다.
'''


# ---------------------------------------------------------------- 실습4·5 공통: 출력 계약과 검사기
CONTRACT = '''# 추출 후보·검토 결과 출력 계약

이 계약은 실습4의 추출 결과(`결과/후보/<문서ID>.json`)와 검토 결과(`결과/검토/<문서ID>_검토.json`)의 모양이다. 실습5는 같은 모양의 검토 결과를 입력으로 읽는다. `check_candidates.py`가 이 계약의 구조와 인용을 검사한다.

## 1. 후보 파일

```json
{
  "doc_id": "HM-8",
  "source_file": "HM-8_cooler-fan-manual.md",
  "source_sha256": "자료/문서_목록.csv의 SHA-256",
  "extractor": "결과/extract.py",
  "generated_at": "2026-10-28T10:00:00+09:00",
  "candidates": [ { 후보 }, ... ],
  "warnings": ["추출 중 판단하지 못한 것"]
}
```

`source_file`은 `자료/원문/` 안의 파일 이름이다. `source_sha256`은 실제로 읽은 파일의 해시다. `extractor`와 `generated_at`은 이 결과를 만든 실행을 가리킨다. 실제 추출 실행 없이 다른 파일을 옮긴 결과는 후보 파일이 아니다.

## 2. 후보 하나

| 필드 | 필수 | 뜻 |
|---|---|---|
| `id` | 예 | 파일 안에서 고유한 문자열 |
| `doc_id` | 예 | 문서 식별자(`HM-8`, `PM-02`, `PR-07`) |
| `section` | 예 | 원문 `## ` 제목의 첫 낱말(예: `HM-8.5`). 첫 `## ` 앞의 글은 `머리말` |
| `procedure` | 예 | 원문 `### SOP-…` 절차 안이면 그 ID, 절차 밖이면 `null` |
| `kind` | 예 | `step` · `precondition` · `prohibition` · `completion` · `unit_value` 중 하나 |
| `text` | 예 | 후보의 내용. 표의 칸이면 행·열 머리글을 함께 적어 뜻이 남게 한다 |
| `quote` | 예 | 원문을 **한 글자도 바꾸지 않고** 옮긴 근거 문자열. `section` 절 안에 그대로 있어야 하고, 같은 절 안에서 위치를 알 수 있을 만큼 길어야 한다(표의 칸 값 하나만 옮기지 않는다) |
| `refs` | 예 | `quote` 안에 적힌 다른 절차·절 ID 목록. `SOP-COOL-11~13`처럼 범위로 적힌 것은 펼친다. 없으면 `[]` |
| `status` | 예 | 추출 직후에는 `pending` |
| `order` | `step`이면 예 | 절차 안 번호(1부터) |
| `value` | `unit_value`이면 예 | 숫자. 범위면 작은 값 |
| `value_max` | 범위이면 예 | 범위의 큰 값 |
| `unit` | `unit_value`이면 예 | 원문의 단위 그대로(℃, %, mm/s, h, 시간, 분, 만 원 …) |
| `comparator` | `unit_value`이면 예 | `>=` `>` `<=` `<` `=` `range` `±` 중 하나, 원문에 비교 표현이 없으면 `null` |
| `value_text` | `unit_value`이면 예 | 값·단위·비교 표현이 적힌 원문 조각 그대로. `quote` 안에 있어야 한다 |

종류의 뜻:

- `step`: 절차의 번호 단계.
- `precondition`: 작업을 하기 전에 충족·확인해야 하는 조건과 승인(예: 운전 모드, 잠금, 승인 역할).
- `prohibition`: 금지와 제한(하지 않는다, 쓰지 않는다, 몇 시간 이내).
- `completion`: 끝났다고 보는 기준과 끝나지 않았을 때의 처리.
- `unit_value`: 숫자와 단위가 있는 기준값.

한 문장이 여러 종류에 해당하면 종류마다 후보를 하나씩 만든다(예: 단계이면서 제한인 문장, 값이 둘 있는 문장). 다섯 종류 어디에도 맞지 않는 문장은 억지로 넣지 않고 `warnings` 또는 검토 기록에 남긴다.

## 3. 검토 결과 파일

후보 파일을 복사해 아래를 더한 별도 파일이다. 후보 파일 원본은 그대로 둔다.

```json
{
  ...후보 파일의 doc_id·source_file·source_sha256·extractor·generated_at...,
  "review": {"reviewer": "검토자", "reviewed_at": "시각", "candidates_file": "HM-8.json", "selected_task": "SOP-COOL-11 또는 SOP-COOL-14"},
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
지식의 맞고 틀림, 종류 판단, 빠진 지식은 판정하지 않는다. 생성·수정을 하지 않는다.
사용: python check_candidates.py 결과/후보/HM-8.json [다른 파일 …]
"""
from pathlib import Path
import hashlib, json, re, sys

HERE = Path(__file__).resolve().parent
KINDS = {'step', 'precondition', 'prohibition', 'completion', 'unit_value'}
COMPARATORS = {None, '>=', '>', '<=', '<', '=', 'range', '±'}
STATUS = {'채택': 'approved', '수정': 'approved', '제외': 'excluded', '보류': 'pending'}
REQUIRED = ['id', 'doc_id', 'section', 'procedure', 'kind', 'text', 'quote', 'refs', 'status']


def blocks(text):
    """절 ID → 절 본문, 절 ID → 그 절의 절차 ID 목록."""
    body, procs, current, lines = {}, {}, '머리말', []
    for line in text.splitlines():
        m = re.match(r'^##\s+(\S+)', line)
        if m and not line.startswith('###'):
            body[current] = '\n'.join(lines)
            current, lines = m.group(1), []
            continue
        p = re.match(r'^###\s+(SOP-[A-Z]+-\d+)', line)
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
        if not data.get(key):
            errors.append(f'최상위 필드 없음: {key}')
    if errors:
        return errors, notes
    source = HERE / '자료/원문' / data['source_file']
    if not source.is_file():
        return [f'자료/원문/{data["source_file"]} 파일이 없습니다.'], notes
    if hashlib.sha256(source.read_bytes()).hexdigest() != data['source_sha256']:
        errors.append('source_sha256이 자료/원문의 파일과 다릅니다(다른 판본을 읽었거나 해시를 지어냈음).')
    body, procs = blocks(source.read_text(encoding='utf-8'))
    reviewed = 'review' in data
    if reviewed:
        for key in ['reviewer', 'reviewed_at']:
            if not data['review'].get(key):
                errors.append(f'review.{key} 없음')
    seen, dup = set(), set()
    for i, c in enumerate(data['candidates']):
        where = c.get('id', f'#{i}')
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
        if c['kind'] == 'step' and not (isinstance(c.get('order'), int) and c['order'] >= 1):
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
            d = c.get('decision')
            if d not in STATUS:
                errors.append(f'{where}: decision은 채택·수정·제외·보류 중 하나')
            elif c['status'] != STATUS[d]:
                errors.append(f'{where}: {d}이면 status는 {STATUS[d]}')
            if not str(c.get('reason', '')).strip():
                errors.append(f'{where}: 결정 이유(reason)가 없음')
            if d == '수정' and not c.get('before'):
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
        kinds[c.get('kind')] = kinds.get(c.get('kind'), 0) + 1
    notes.append(f'후보 {len(data["candidates"])}개, 종류별 {kinds}')
    if reviewed:
        dec = {}
        for c in data['candidates']:
            dec[c.get('decision')] = dec.get(c.get('decision'), 0) + 1
        notes.append(f'결정별 {dec}, 누락 기록 {len(data.get("missing", []))}개')
    return errors, notes


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(2)
    failed = False
    for arg in sys.argv[1:]:
        try:
            errors, notes = check(arg)
        except (OSError, ValueError, TypeError, AttributeError, KeyError) as e:
            errors, notes = [f'읽기 실패: {e}'], []
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


def run(path):
    text = Path(path).read_text(encoding='utf-8-sig')
    parts, buf = [], []
    for line in text.splitlines():
        if line.strip().startswith('//') and not buf:
            continue
        buf.append(line)
        if line.rstrip().endswith(';'):
            parts.append('\n'.join(buf).rstrip().rstrip(';')); buf = []
    if '\n'.join(buf).strip():
        parts.append('\n'.join(buf))
    for i, s in enumerate(parts, 1):
        if WIPE.search(s):
            raise RuntimeError(f'{i}번째 문장: 전체 삭제문은 이 랩에서 실행하지 않습니다. 필요한 대상만 고치세요.')
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


def guide(folder, title, intro, sections):
    text = page(title, intro, sections)
    write(folder / 'guide.html', text)
    write(folder / '안내.html', text)


def start(folder, text):
    write(folder / 'START.md', text)
    write(folder / '준비_안내.md', text)


# ---------------------------------------------------------------- 실습3 매뉴얼 대조(포털 관찰, 코드 과제 아님)
def build_manual():
    folder = LABS / MANUAL
    reset(folder)
    sources(folder, ['HM-8'])
    rules_file(folder, ['이번 실습은 포털 관찰과 기록이다. 포털에서 매뉴얼 미리보기·에이전트 추출 요청·적재를 하지 않는다. 직접 추가 적재는 마지막 교대 실습에서 한다.',
                        '포털에서 보지 못한 표시는 보았다고 적지 않는다. 화면에서 찾지 못한 항목은 「포털에서 찾지 못함」으로 둔다.'])
    title = '포털 지식과 매뉴얼 원문 대조하기'
    intro = '포털에 등록된 HM-8 지식을 원문과 나란히 놓고, 팬 최대 운전과 쿨러 핀 세척을 하기 전에 확인할 항목을 원문 절에 연결합니다.'
    start(folder, f'''# {title}

{intro} 코드를 작성하지 않는 관찰 실습입니다.

## 출발 상태

- `자료/원문/HM-8_cooler-fan-manual.md`: 포털 수업용 승인 원문과 같은 판입니다. 해시는 `자료/문서_목록.csv`에 있습니다.
- 수업용 포털: 강사가 준비한 교육 환경입니다. 1회차에서 본 매뉴얼 적재 이후의 지식이 지식 지도에 있습니다. 상태가 다르면 강사에게 알리고 그 사실을 기록합니다.
- `결과/대조_기록.md`: 비어 있는 기록 틀입니다.

## 이번에 할 일

1. 원문에서 **팬 최대 운전(SOP-COOL-11)**과 **쿨러 핀 세척(SOP-COOL-14)**을 찾습니다. 절차의 단계뿐 아니라 그 작업을 가리키거나 적용 범위를 정하는 다른 절도 찾습니다.
2. 포털 왼쪽 메뉴의 지식 묶음에서 **지식 지도**를 열고 조치 방법 칸에서 두 작업을 찾습니다. 화면에 보이는 단계·조건·근거 표시를 그대로 기록합니다. **지식 관리** 화면에서는 HM-8이 등록되어 있는지만 확인합니다.
3. 두 작업마다 적용 조건·금지 사항·완료 기준·승인을 원문 절과 원문 문장에 연결하고, 포털에서 본 표현과 일치하는지 적습니다.
4. 문서에 적힌 **기준값**과 작업 직전에 설비·기록에서 읽어야 하는 **현재 값**을 다른 칸에 적습니다. 현재 값을 어디서 읽는지 문서에 없으면 그렇게 적습니다.
5. 원문으로 답할 수 없는 것은 남은 질문으로 적습니다.

## 확인할 사례의 종류

- 작업 조건이 그 절차 밖의 다른 절에 적혀 있는 경우
- 표의 머리글이 값의 뜻을 정하는 경우
- 「이상」과 「초과」, 「이내」처럼 경계를 바꾸는 표현
- 문서가 정하지 않은 것(현재 상태, 적용 설비 범위)

## 완료 판정 원칙

두 작업 모두 각 항목이 원문 절과 문장으로 이어지고, 포털 표시와의 대조 결과가 일치 / 표현 다름 / 포털에서 찾지 못함으로 구별되어 있으면 됩니다. 기준값과 현재 값이 섞이지 않아야 합니다. 포털에서 보지 못한 것을 추정으로 채우지 않습니다.

## 저장할 결과

결과/대조_기록.md

{SAVE}
다음 실습에서는 이렇게 대조한 지식을 원문에서 직접 추출하는 기능을 만듭니다.
''')
    write(folder / '입력/README.md', '이 실습은 앞 단계 결과가 필요 없습니다. 대조 대상은 자료/원문의 HM-8과 수업용 포털의 등록 지식입니다.\n')
    write(folder / '결과/README.md', '대조_기록.md를 여기에 작성합니다.\n')
    table = '| 구분 | 원문 절 | 원문 문장(그대로) | 포털에서 본 표현과 위치 | 대조 결과 | 작업 전 확인할 현재 값과 읽을 곳 |\n|---|---|---|---|---|---|\n| 적용 조건 | | | | | |\n| 금지·제한 | | | | | |\n| 완료 기준 | | | | | |\n| 승인 | | | | | |\n'
    write(folder / '결과/대조_기록.md', f'''# 매뉴얼 원문과 포털 지식 대조 기록

- 확인 일시:
- 포털에서 연 화면:
- 원문 판본(SHA-256 앞 12자리):

대조 결과는 일치 / 표현 다름(무엇이) / 포털에서 찾지 못함 중 하나로 적습니다. 한 구분에 항목이 여럿이면 행을 늘립니다.

## 1. 팬 최대 운전 (SOP-COOL-11)

{table}
## 2. 쿨러 핀 세척 (SOP-COOL-14)

{table}
## 3. 기준값과 현재 값

| 항목 | 문서의 기준값과 절 | 현재 값을 읽을 곳 | 관찰한 현재 값과 시각(또는 미확인) |
|---|---|---|---|

## 4. 남은 질문

''')
    guide(folder, title, intro, [
        ('시작하기', '<p>압축을 푼 폴더를 VS Code에서 열고 <a href="START.md">START.md</a>를 읽으세요. 이번 실습은 포털 관찰과 기록이며 코드를 만들지 않습니다.</p><pre>자료/원문/   HM-8 원문(포털 승인 원문과 같은 판)\n자료/문서_목록.csv   문서 ID·해시\n결과/대조_기록.md   작성할 기록</pre>'),
        ('요구 정하기', '<p>두 작업(SOP-COOL-11 팬 최대 운전, SOP-COOL-14 쿨러 핀 세척)에 대해 무엇을 확인해야 작업을 시작할 수 있는지 원문에서 먼저 찾으세요. 절차 단계만 보지 말고 그 작업을 가리키는 다른 절도 찾습니다.</p>'),
        ('포털에서 대조하기', '<p>포털 왼쪽 메뉴의 지식 묶음에서 <b>지식 지도</b>를 열고 조치 방법 칸에서 두 작업을 찾으세요. 화면에 보이는 단계·조건·근거 표시를 기록하고 원문 문장과 나란히 적습니다. <b>지식 관리</b>에서는 HM-8 등록 여부만 확인합니다.</p><p class="check">매뉴얼 등록·미리보기·에이전트 추출 요청·적재는 누르지 않습니다. 직접 추가 적재는 마지막 교대 실습에서 제공 보충 매뉴얼로 합니다.</p>'),
        ('결과 확인하기', '<ul><li>각 항목이 원문 절과 원문 문장으로 이어지나요?</li><li>절차 밖의 절에 있는 조건도 찾았나요?</li><li>표의 값은 행·열 머리글과 함께 읽었나요?</li><li>「이상」·「초과」·「이내」 같은 경계 표현을 그대로 옮겼나요?</li><li>문서의 기준값과 작업 직전에 읽을 현재 값을 다른 칸에 적었나요?</li></ul><p class="check">포털에서 찾지 못한 항목은 찾지 못했다고 적습니다. 추정으로 채운 대조는 확인한 대조가 아닙니다.</p>'),
        ('저장하기', '<p>결과/대조_기록.md를 저장하고 다시 열어 확인하세요. 보관할 결과는 USB 또는 개인 클라우드에 복사합니다.</p><p>다음 실습은 이 대조를 원문에서 직접 추출하는 기능으로 이어집니다. 다음 실습은 이 기록 없이도 시작할 수 있습니다.</p>')])
    return folder, title


# ---------------------------------------------------------------- 실습4 지식 추출
def build_extract():
    folder = LABS / EXTRACT
    reset(folder)
    sources(folder, ['HM-8', 'PM-02', 'PR-07'])
    rules_file(folder, ['추출 함수는 자료/원문의 Markdown만 읽는다. 이번 랩에서는 LLM·외부 API를 호출하지 않고 접속 키를 폴더에 두지 않는다.',
                        '입력/비교용_추출결과/는 비교 자료다. 이 파일을 읽어 후보를 만들거나 결과로 복사하지 않는다.',
                        'quote는 원문 문자열을 그대로 옮긴다. 원문에 없는 단계·조건·수치를 만들지 않는다.',
                        '채택·수정·제외·보류는 사람이 결정한다. AI는 근거 대조를 도울 수 있지만 결정을 확정하지 않는다.',
                        '후보 파일 원본은 남기고 검토 결과는 별도 파일로 만든다.'])
    write(folder / '입력/출력_계약.md', CONTRACT)
    write(folder / 'check_candidates.py', CHECKER)
    bundle = json.loads(BUNDLE.read_text(encoding='utf-8'))['payload']
    hm8 = sha(SRC / 'HM-8_cooler-fan-manual.md')
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

`HM-8_포털승인추출.json`은 포털 수업용 승인 추출 묶음(판본 {bundle['revision']}, 추출 판 {bundle['extraction_version']})의 HM-8 항목을 그대로 옮긴 것입니다. 포털 에이전트가 추출하고 사람이 검토한 결과이며, 이 폴더에서 실행한 추출이 아닙니다. 형식도 이번 출력 계약과 다릅니다.

쓰는 곳:

- 직접 만든 추출 결과와 비교해 빠진 단계·조건을 찾는 참고 자료
- 포털 화면 대조가 막혔을 때 포털에 등록된 지식이 무엇인지 확인하는 대안

이 파일을 읽어 후보를 만들거나 결과로 복사하면 추출을 실행한 것이 아닙니다. 비교한 내용은 결과/검토_기록.md의 비교 절에 적습니다.
''')
    write(folder / '입력/README.md', '''# 입력

- `출력_계약.md`: 추출 후보와 검토 결과의 JSON 모양. 추출 함수와 검토 결과는 이 계약을 따릅니다.
- `비교용_추출결과/`: 포털 승인 추출 결과(비교용). 실제 추출 실행이 아닙니다.

이 실습은 앞 단계 결과 없이 시작할 수 있습니다. 실습3의 대조 기록을 쓰고 싶으면 `입력/내_대조기록/`처럼 별도 폴더에 복사해 참고합니다.
''')
    write(folder / '결과/README.md', '추출 함수(extract.py), 후보(후보/), 검토 결과(검토/), 검토_기록.md를 여기에 둡니다.\n')
    write(folder / '결과/검토_기록.md', '''# 추출 후보 검토 기록

- 검토자 / 검토 일시:
- 원문 판본(SHA-256 앞 12자리):
- 실행한 명령과 결과(후보 수·종류별 수·검사 결과):

## 1. HM-8 후보 결정

| 후보 id | 종류 | 원문 절 | 결정 | 이유와 원문 근거 | 수정 전 → 후 |
|---|---|---|---|---|---|

## 2. 원문에 있는데 후보가 없는 것

| 원문 절 | 원문 문장 | 빠진 종류 | 처리(추출 규칙 보완 / 검토자 추가 / 남은 질문) |
|---|---|---|---|

## 3. 다른 문서에 적용

- 문서와 실행 명령:

| 사례 | 원문 문장 | 추출 결과 | 판정(정상 / 누락 / 근거 없는 생성 / 종류 오류) | 고친 점 |
|---|---|---|---|---|

## 4. 비교용 추출 결과와 비교

| 항목 | 내 추출 결과 | 비교용 결과 | 차이와 판단 |
|---|---|---|---|

## 5. 선택한 작업의 준비·금지·완료

- 선택한 작업:

| 구분 | 후보 id | 원문 절 | 절차 밖에서 찾은 조건이면 그 근거 |
|---|---|---|---|

## 6. 남은 질문

''')
    title = '매뉴얼에서 작업 지식 후보를 추출하고 검토하기'
    intro = '원문 Markdown에서 작업 순서·조건·금지·완료 기준·기준값을 문서 ID·절·인용과 함께 뽑는 추출 기능을 만들고, 사람이 후보를 검토합니다.'
    cmd = '''python 결과/extract.py 자료/원문/HM-8_cooler-fan-manual.md --doc HM-8 --out 결과/후보/HM-8.json
python check_candidates.py 결과/후보/HM-8.json
python 결과/extract.py 자료/원문/PM-02_powerpack-pm-checklist.md --doc PM-02 --out 결과/후보/PM-02.json
python check_candidates.py 결과/후보/PM-02.json
python check_candidates.py 결과/검토/HM-8_검토.json'''
    start(folder, f'''# {title}

{intro} 포털에서는 에이전트가 이 일을 했습니다. 이번에는 같은 일을 VS Code에서 직접 구현하고, 결과를 원문으로 검증합니다.

## 출발 상태

- `자료/원문/`: HM-8·PM-02·PR-07 원문(포털 승인 원문과 같은 판). 해시는 `자료/문서_목록.csv`.
- `입력/출력_계약.md`: 후보와 검토 결과의 JSON 모양. 이미 정해져 있습니다.
- `check_candidates.py`: 계약 구조와 **인용이 원문 절 안에 그대로 있는지**를 검사합니다. 빠진 지식이나 종류 판단은 검사하지 않습니다.
- `입력/비교용_추출결과/`: 포털 승인 추출 결과. 비교용이며 실제 추출 실행이 아닙니다.
- 비어 있는 것: 추출 함수, 후보, 검토 결과, 검토 기록.

## 이번에 구현할 범위

1. `결과/extract.py`: 원문 Markdown의 절(`##`)·절차(`###`)·번호 단계·표·문장을 읽어 계약대로 후보를 내는 함수와 실행 명령. API 키 없이 로컬에서 실행되는 규칙 기반 Python으로 만듭니다. 외부 모델 호출은 이번 범위가 아닙니다.
2. HM-8로 실행하고 `check_candidates.py`로 인용을 확인한 뒤 원문과 나란히 놓고 검토합니다. 인용 검사를 AI와 함께 더 엄격하게 만들어도 됩니다(제공 검사기는 바꾸지 말고 결과/에 새로 만드세요).
3. 후보마다 채택·수정·제외·보류를 정해 `결과/검토/HM-8_검토.json`(계약 3절)과 `결과/검토_기록.md`에 남깁니다. 원문에 있는데 빠진 것도 적습니다.
4. 같은 함수를 **다른 문서**(PM-02, 필요하면 PR-07)에 다시 실행해 누락과 근거 없는 생성을 찾고, 추출 규칙을 고쳐 다시 실행합니다.
5. 팬 최대 운전(SOP-COOL-11)과 쿨러 핀 세척(SOP-COOL-14) 중 하나를 골라 그 작업의 준비·금지·완료 후보를 묶어 둡니다. 다음 실습의 작업 확인 카드로 이어집니다.

{CYCLE}
## 확인할 사례의 종류

- 한 문장이 단계이면서 제한이거나 값을 여럿 가진 경우
- 표의 칸 값: 행·열 머리글이 없으면 뜻을 잃는 경우
- 경계 표현(이상/초과/미만/이내)과 범위(~), 천 단위 쉼표, 소수
- 「하지 않는다」 같은 부정 조건과 「~이면」 같은 적용 조건
- 작업 조건이 그 절차 밖의 절에 있거나 다른 절차 ID를 범위로 가리키는 경우
- 이름 속의 숫자처럼 기준값이 아닌 수치 — 근거 없는 기준값 생성
- 다른 문서에서만 나타나는 표현 — 한 문서에 맞춘 규칙의 누락

## 실행 명령

```
{cmd}
```

## 완료 판정 원칙

- 후보 파일이 이 폴더의 추출 함수를 실제로 실행해 만든 것이어야 합니다. 비교용 결과를 옮긴 것은 추출이 아닙니다.
- 검사기 통과는 출발점입니다. 원문과 대조해 결정과 이유를 남겼고, 빠진 것을 찾았고, 다른 문서에서 드러난 문제를 기록·수정했는지로 판단합니다.
- 맞게 나온 결과를 일부러 망가뜨려 고치는 과정을 만들 필요는 없습니다.

## 저장할 결과

결과/extract.py, 결과/후보/HM-8.json, 결과/후보/PM-02.json, 결과/검토/HM-8_검토.json, 결과/검토_기록.md

{SAVE}''')
    guide(folder, title, intro, [
        ('시작하기', '<p>압축을 푼 폴더를 VS Code에서 열고 <a href="START.md">START.md</a>와 <a href="입력/출력_계약.md">입력/출력_계약.md</a>를 읽으세요.</p><pre>자료/원문/        HM-8·PM-02·PR-07 원문\n입력/출력_계약.md   후보·검토 JSON 모양\n입력/비교용_추출결과/  포털 승인 추출(비교용, 실제 실행 아님)\ncheck_candidates.py  계약·인용 검사기\n결과/            이번에 만들 것</pre><p>AI에게 먼저 이 자료를 읽고 무엇이 있고 무엇이 비었는지 설명하게 하세요. 이때는 파일을 만들거나 바꾸지 말라고 함께 말합니다.</p>'),
        ('요구 정하기', '<p>목표(원문에서 다섯 종류의 후보를 문서 ID·절·인용과 함께 추출), 입력(자료/원문), 제약(원문 그대로의 인용, LLM 호출 없음, 비교용 결과 사용 금지), 확인할 사례(START의 사례 종류)를 자기 말로 정리해 전달하세요.</p><p>AI가 계획을 내면 계약의 필수 필드와 확인 사례가 빠지지 않았는지 보고 고칠 점을 말한 뒤 진행합니다.</p>'),
        ('AI와 만들기', '<p>작은 단위로 구현하고 실행합니다. 예: 절·절차 인식 → 번호 단계 → 표 칸 → 문장의 조건·금지·완료 → 값과 단위. 단계마다 HM-8로 실행해 출력을 원문과 비교한 뒤 다음으로 넘어갑니다.</p><p>수정 요청에는 어떤 원문 문장에서, 무엇을 기대했고, 실제로 무엇이 나왔는지를 함께 주세요.</p>' + ASK),
        ('결과 확인하기', f'<pre>{html.escape(cmd)}</pre><p><b>판단 원칙</b>: 검사기는 인용이 원문 절 안에 그대로 있는지와 계약 구조만 확인합니다. 지식이 맞는지, 빠졌는지는 원문과 직접 대조해 판단합니다.</p><ul><li>인용 검사에서 실패한 후보는 원문을 바꾸지 말고 추출 함수를 고칩니다.</li><li>한 문장에 단계와 제한이 함께 있으면 두 후보가 모두 있는지 봅니다.</li><li>표의 칸 값에 행·열 머리글이 text로 남았는지 봅니다.</li><li>「이상」과 「초과」가 같은 비교 기호로 바뀌지 않았는지 봅니다.</li><li>PM-02에 다시 실행했을 때 HM-8에는 없던 표현(쉼표 숫자, 여러 값이 든 표 칸, 「~보다 적으면」, 「~려면」)이 어떻게 나오는지 봅니다.</li><li>이름 속 숫자를 기준값으로 만든 후보는 근거 없는 생성으로 제외하거나 규칙을 고칩니다.</li></ul><p class="check">비교용 추출 결과와 차이가 나면 어느 쪽이 원문과 맞는지 원문으로 판단합니다. 비교용 결과가 정답 목록은 아닙니다.</p>'),
        ('저장하기', '<p>결과/extract.py, 결과/후보/, 결과/검토/, 결과/검토_기록.md를 저장하고 다시 열어 확인하세요. 검토 결과에 대해 check_candidates.py를 한 번 더 실행합니다.</p><p>보관할 결과는 USB 또는 개인 클라우드에 복사하세요. 다음 실습은 강사가 검토한 HM-8 검토 결과로 시작하므로 이번 결과가 없어도 진행할 수 있습니다.</p>')])
    return folder, title


# ---------------------------------------------------------------- 실습5 그래프 반영과 작업 확인 카드
def build_card():
    folder = LABS / CARD
    reviewed = REF / '검토결과/HM-8_검토.json'
    if not reviewed.is_file():
        raise FileNotFoundError(f'앞 단계 완성 검토본이 없습니다. reference/session3_docs/review_reference.py를 먼저 실행하세요: {reviewed}')
    reset(folder)
    sources(folder, ['HM-8', 'PM-02', 'PR-07'])
    rules_file(folder, ['DB 작업은 lab_db.py가 만든 이 폴더 전용 DB에서만 한다. 전체 삭제문을 쓰지 않는다.',
                        'approved 후보만 적재한다. 제외·보류 후보는 적재하지 않고 기록에 남긴다.',
                        '앞 단계 모델의 기존 ID를 새로 만들거나 바꾸지 않는다. 연결할 기존 ID가 없으면 만들지 말고 남은 질문으로 적는다.',
                        '작업 확인 카드는 현재 설비 상태나 승인을 대신 정하지 않는다. 현재 값과 승인이 필요한 것은 그렇게 표시한다.'])
    shutil.copy2(HERE / 'lab_db.py', folder / 'lab_db.py')
    write(folder / 'lab_cypher.py', LAB_CYPHER)
    write(folder / 'check_candidates.py', CHECKER)
    write(folder / '입력/출력_계약.md', CONTRACT)
    schema, graph = reference_model(True)
    dump(folder / '입력/모델/schema.json', schema)
    dump(folder / '입력/모델/graph.json', graph)
    shutil.copytree(MODEL_DATA, folder / '입력/모델/자료', dirs_exist_ok=True)
    data = json.loads(reviewed.read_text(encoding='utf-8'))
    if data['source_sha256'] != sha(SRC / 'HM-8_cooler-fan-manual.md'):
        raise ValueError('검토본의 원문 해시가 승인 원문과 다릅니다: ' + str(reviewed))
    (folder / '입력/검토결과').mkdir(parents=True, exist_ok=True)
    shutil.copyfile(reviewed, folder / '입력/검토결과/HM-8_검토.json')
    counts = {}
    for c in data['candidates']:
        counts[c['status']] = counts.get(c['status'], 0) + 1
    write(folder / '입력/README.md', f'''# 입력 — 앞 단계 완성 상태

- `모델/schema.json`·`모델/graph.json`: 2회차 완성 모델(설비·구성요소·센서·물리량·부품·공급사). `python lab_cypher.py model`로 랩 DB에 적재합니다. 원자료는 `모델/자료/`.
- `검토결과/HM-8_검토.json`: 실습4의 강사 검토본(앞 단계 완성 상태). approved {counts.get('approved', 0)}건, excluded {counts.get('excluded', 0)}건, pending {counts.get('pending', 0)}건. 학생의 검토 결과가 아니라 시작용 제공본입니다.
- `출력_계약.md`: 검토 결과 JSON의 필드 뜻.

개인 실습4 결과를 쓰려면 제공 입력을 그대로 두고 `입력/내_검토결과/`처럼 별도 폴더에 복사한 뒤 `python check_candidates.py <파일>`로 계약을 확인하세요. 원문 해시가 `자료/문서_목록.csv`와 같아야 합니다.
''')
    write(folder / '결과/README.md', '적재문(load.cypher), 조회문(query.cypher), 작업확인카드.md, 구축_기록.md와 직접 만든 생성 코드를 여기에 둡니다.\n')
    write(folder / '결과/구축_기록.md', '''# 온톨로지 구축 기록

- 확인 일시 / 사용한 랩 DB 주소(인증값 제외):

## 1. 질문

## 2. 모델 확장

| 새 종류·관계 | 뜻 | 연결한 기존 ID | 근거(원문 절·자료) |
|---|---|---|---|

## 3. 입력 문서와 검토 결과

| 파일 | 판본(SHA-256 앞 12자리) | 적재한 approved 수 | 적재하지 않은 수(제외·보류) |
|---|---|---|---|

## 4. 적재와 반복 적재

| 시점 | 노드 수 | 관계 수 | 메모 |
|---|---|---|---|
| 모델 적재 후 | | | |
| 1차 적재 후 | | | |
| 같은 적재 재실행 후 | | | |

## 5. 조회 결과

| 질문·사례 | 조회문 | 실제 결과 요약 | 원문 대조 |
|---|---|---|---|

## 6. 답할 수 있는 것과 없는 것

| 질문 | 그래프로 답함 / 현재 값 필요 / 승인 필요 / 원문에 없음 | 근거 |
|---|---|---|
''')
    title = '검토한 지식을 랩 그래프에 연결하고 작업 확인 카드 만들기'
    intro = '검토를 마친 HM-8 지식을 2회차 모델의 기존 ID에 연결해 별도 랩 DB에 적재하고, 선택한 작업의 준비·금지·완료 조건과 원문 출처를 모은 작업 확인 카드를 조회 결과로 만듭니다.'
    cmd = '''python lab_db.py
python lab_cypher.py model
python lab_cypher.py count
python lab_cypher.py run 결과/load.cypher
python lab_cypher.py count
python lab_cypher.py run 결과/load.cypher
python lab_cypher.py count
python lab_cypher.py run 결과/query.cypher'''
    start(folder, f'''# {title}

{intro}

## 출발 상태

- `입력/모델/`: 2회차 완성 모델과 원자료. 이번 과제의 답이 아니라 이미 끝난 앞 단계입니다.
- `입력/검토결과/HM-8_검토.json`: 실습4의 검토 완료본. `status`가 `approved`인 후보만 적재 대상입니다.
- `자료/원문/`: HM-8·PM-02·PR-07 원문. 카드의 출처를 다시 확인할 때 씁니다.
- `lab_db.py`: 이 폴더 전용 Neo4j 컨테이너를 준비합니다(Docker 필요). 포털 DB가 아닙니다.
- `lab_cypher.py`: 랩 DB에 Cypher 파일을 실행하고 노드·관계 수를 셉니다. 앞 단계 모델 적재(`model`)도 합니다.
- 비어 있는 것: 모델 확장, 적재문, 조회문, 작업 확인 카드, 구축 기록.

## 이번에 구현할 범위

1. 문서·절·절차·검토한 지식을 담을 모델 확장을 정하고, 기존 모델의 어떤 ID(예: 물리량, 부품)에 무엇을 근거로 연결할지 정합니다. 기존 ID는 그대로 둡니다.
2. `결과/load.cypher`: approved 후보만, 원문 출처(문서·판본·절·인용·검토 결정)와 함께 적재합니다. 같은 파일을 두 번 실행해도 노드·관계가 늘지 않아야 합니다. JSON에서 적재문을 만드는 코드를 AI와 함께 작성해도 됩니다.
3. `결과/query.cypher`: 선택한 작업의 준비·금지·완료 조건과 출처를 찾는 조회. 절차 밖의 절에 있거나 다른 절차를 가리키는 조건도 따라가야 합니다.
4. `결과/작업확인카드.md`: 조회 결과로 만든 카드. 아래 출력 계약을 지킵니다.
5. `결과/구축_기록.md`: 질문·모델·문서·추출/검토·적재·조회 결과를 연결해 남깁니다.

## 작업 확인 카드의 출력 계약

- 대상 작업: 절차 ID·이름, 문서 ID와 판본(SHA-256 앞 12자리)
- 준비 조건 / 금지·제한 / 완료 기준: 항목마다 원문 절과 원문 인용, 지식 후보 id
- 작업 순서: 단계 번호 순서
- 작업 직전에 읽어야 하는 현재 값: 문서의 기준값과 구분해, 그래프에 없으면 「현재 값 필요」로 표시
- 승인: 원문에 적힌 승인 역할. 카드가 승인을 대신하지 않음
- 남은 질문: 원문이 정하지 않은 것, 적재하지 않은(보류·제외) 후보 때문에 답하지 못하는 것, 기존 모델에 연결할 ID가 없는 것

## 확인할 사례의 종류

- 선택한 작업과 **다른 작업** 하나에도 같은 조회로 카드를 만들 수 있는가
- 원문이 제공하지 않는 절·작업을 물었을 때 「결과 없음」으로 구별되는가
- **같은 적재를 다시 실행**해도 노드·관계 수가 같은가(실제 count 수치로)
- 제외·보류 후보가 DB와 카드에 들어가지 않았는가
- 부품의 공급 정보와 작업 조건을 어디까지 함께 답할 수 있고, 현재 값·승인 없이 결정할 수 없는 것은 무엇인가

{CYCLE}
## 실행 명령

```
{cmd}
```

Neo4j Browser로 확인하려면 `lab_db.py`가 연 주소에서 Protocol은 bolt://, Connection URL은 출력된 127.0.0.1:포트, 사용자 neo4j, 비밀번호는 비워 둡니다.

## 완료 판정 원칙

- 기존 모델의 노드·관계 수는 모델 적재 직후 값에서 이번 적재로 늘어난 만큼만 늘고, 재적재 뒤에는 변하지 않아야 합니다.
- 카드의 항목은 모두 원문 절과 인용으로 돌아갈 수 있어야 하고, 원문과 대조해 빠진 조건이 없어야 합니다.
- 카드가 답하지 못하는 것을 추정으로 채우지 않고 남은 질문으로 둡니다. 개수만 맞고 답·출처가 틀린 결과는 완료가 아닙니다.

## 저장할 결과

결과/load.cypher, 결과/query.cypher, 결과/작업확인카드.md, 결과/구축_기록.md (생성 코드가 있으면 함께)

{SAVE}
다음 회차에는 이 지식으로 점검 요청을 만듭니다.
''')
    guide(folder, title, intro, [
        ('시작하기', '<p>압축을 푼 폴더를 VS Code에서 열고 <a href="START.md">START.md</a>를 읽으세요. Docker Desktop이 실행 중이어야 합니다.</p><pre>python lab_db.py\npython lab_cypher.py model\npython lab_cypher.py count</pre><p>「랩 DB 준비 완료」가 나온 뒤 앞 단계 모델을 적재하고 노드·관계 수를 구축 기록에 적어 두세요. 이 수가 기존 모델을 보존했는지 판단하는 기준입니다.</p><p>AI에게 먼저 입력/의 모델·검토 결과와 출력 계약을 읽고 무엇이 있는지 설명하게 하세요. 이때는 파일을 만들거나 바꾸지 말라고 함께 말합니다.</p>'),
        ('요구 정하기', '<p>목표(검토한 지식을 기존 ID에 연결해 적재하고 작업 확인 카드 만들기), 입력, 제약(approved만, 기존 ID 보존, 반복 적재 무중복, 전체 삭제 금지), 확인할 사례(다른 작업, 미제공 절, 재적재, 제외·보류)를 자기 말로 정리해 전달하세요.</p><p>AI의 계획에서 새 종류·관계와 기존 ID 연결의 근거가 원문·자료에 있는지 보고 고칠 점을 말한 뒤 진행합니다.</p>'),
        ('AI와 만들기', '<p>작은 단위로 진행합니다. 예: 문서·절·절차 적재 → 지식 후보 적재와 출처 연결 → 기존 ID 연결 → 조회 → 카드. 단계마다 count와 조회 결과를 확인합니다.</p><p>수정 요청에는 실행한 문장, 기대한 결과, 실제 결과(오류 메시지·수치)를 함께 주세요.</p>' + ASK),
        ('결과 확인하기', f'<pre>{html.escape(cmd)}</pre><p><b>판단 원칙</b>: 수치는 기존 모델 보존과 무중복을, 카드의 출처와 원문 대조는 내용을 판정합니다. 둘 중 하나만으로는 완료가 아닙니다.</p><ul><li>같은 load.cypher를 두 번 실행한 뒤 count가 같아야 합니다.</li><li>모델 적재 직후의 종류별 수(Asset·Sensor·Part 등)가 이번 적재 뒤에도 같아야 합니다.</li><li>카드의 각 항목에서 원문 절을 열어 인용을 찾을 수 있어야 합니다.</li><li>절차 밖의 절에 적힌 조건과 다른 절을 가리키는 완료 기준이 카드에 이어졌는지 원문 HM-8과 대조합니다.</li><li>보류·제외 후보 id로 조회하면 결과가 없어야 합니다.</li><li>원문에 없는 작업을 조회하면 결과 없음이 나오고, 카드에 그렇게 적혀야 합니다.</li></ul><p class="check">현재 운전 상태·누적 운전 시간처럼 작업 직전에 읽어야 하는 값과 승인은 카드가 정하지 않습니다. 「현재 값 필요」·「승인 필요」로 남깁니다.</p>'),
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
