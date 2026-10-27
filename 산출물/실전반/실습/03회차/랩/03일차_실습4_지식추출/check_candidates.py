"""후보·검토 JSON의 계약 검사. 인용이 원문 절 안에 그대로 있는지 대조한다.
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
            print(f'    참고: {f.name}은 모든 후보가 「채택」이고 누락 기록이 0개입니다. 원문과 나란히 놓고 대조했는지, 빠진 것이 정말 없는지 확인하세요.')
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
