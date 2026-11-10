"""적재 파일 · 랩 DB · 내보내기 · build_record.md · 작업 확인 카드의 구조 검사. 생성 · 수정 · DB 변경을 하지 않는다(랩 DB는 읽기 조회만).
무엇을 어디에 이어야 맞는지, 조회 결과가 질문에 맞게 답하는지는 판정하지 않는다 — 의미와 질문별 답은 원자료와 따로 대조한다.
사용: python run.py check
"""
from pathlib import Path
import csv, io, json, re, sys, urllib.request, urllib.error

HERE = Path(__file__).resolve().parents[2]
RESULT = HERE / 'output'
PRACTICAL = True
HEADINGS = ['대상 작업', '준비 조건', '금지 · 제한', '작업 순서', '완료 기준', '작업 직전 확인할 현재값', '승인', '추가 자료가 필요한 질문']
END = '의미와 질문별 답은 원자료와 따로 대조합니다.'
WIPE = re.compile(r'MATCH\s*\(\s*\w*\s*\)\s*(DETACH\s+)?DELETE', re.I)
DELETE = re.compile(r'\bDELETE\b', re.I)
ID_LITERAL = re.compile(r'\bid\s*:\s*[\'"]([^\'"]+)[\'"]')
SHAPES = [re.compile(p) for p in (r'^HYD-\d\d(?::[\w-]+)?$', r'^P-[A-Z0-9]+(?:-[A-Z0-9]+)*$', r'^SOP-[A-Z]+-\d+(?::\d+)?$', r'^fm:[\w-]+$', r'^cause:[\w-]+$', r'^R\d+$')]
NOW_KEYS = re.compile(r'on_hand|reserved|on_order|stock|현재고|예약|입고|재고', re.I)
QUOTE = re.compile(r'「([^」]+)」')


def read(path):
    raw = Path(path).read_bytes()
    for enc in ('utf-8-sig', 'cp949'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', 'replace')


def csv_rows(path):
    lines = [x for x in read(path).splitlines() if x.strip() and not x.startswith('#')]
    return list(csv.DictReader(io.StringIO('\n'.join(lines))))


def basis(rel):
    mine = HERE / 'app/features/my_inputs' / rel
    return mine if mine.exists() else HERE / 'data' / rel


def known_ids():
    """설비 모델 · SOP 구조 · 조건표가 만드는 기존 ID."""
    graph = json.loads(read(basis('model/graph.json')))
    sop = json.loads(read(basis('sop.json')))
    ids = {n['props']['id'] for n in graph['nodes']}
    ids |= {x['id'] for x in sop['failure_modes'] + sop['causes']}
    for s in sop['sops']:
        ids.add(s['id'])
        ids |= {f'{s["id"]}:{st["order"]}' for st in s['steps']}
    ids |= {r['rule_id'] for r in csv_rows(basis('conditions.csv'))}
    return ids


def reviews():
    """[(문서 식별자, 판, 후보 id, 상태, 인용)] — 기준 검토 결과의 후보 전부. 후보 id는 파일 안에서만 고유하다."""
    out = []
    for f in sorted(basis('reviews').glob('*_review.json')):
        data = json.loads(read(f))
        for c in data.get('candidates', []):
            out.append((str(data.get('doc_id')), str(data.get('rev') or ''), c['id'], c.get('status'), c.get('quote')))
    return out


def approved_values():
    """승인(approved) 후보가 가진 글 값 전부(인용 · 내용 · 값 글 · 절 · 절차) — 같은 글이 다른 문서의 승인하지 않은 후보 인용과 겹쳐도 승인한 지식의 값이다."""
    out = set()
    for f in sorted(basis('reviews').glob('*_review.json')):
        for c in json.loads(read(f)).get('candidates', []):
            if c.get('status') == 'approved':
                out |= {v for v in c.values() if isinstance(v, str)}
    return out


def points_to(value, cands):
    """값(ID · 글)이 가리키는 후보들 — 후보 id 그대로이거나, 문서 식별자를 품고 후보 id로 끝나는 값(판이 보이면 그 판으로 좁힘)."""
    hits = [c for c in cands if value == c[2] or (value.endswith(c[2]) and c[0] in value)]
    narrowed = [c for c in hits if c[1] and c[1] in value.replace(c[2], '')]
    return narrowed or hits


def held(value, cands):
    """값이 승인(approved)이 아닌 후보만 가리키는가."""
    hits = points_to(value, cands)
    return bool(hits) and all(c[3] != 'approved' for c in hits)


def headings():
    """data/documents/ 원문에 절 머리로 있는 표기 — 「## 」 · 「### 」 줄의 첫 낱말, 「제N조」, 「HM-9.x 제목」 꼴 줄."""
    out = set()
    for f in (HERE / 'data/documents').iterdir():
        if f.suffix not in ('.md', '.txt'):
            continue
        for line in read(f).splitlines():
            m = re.match(r'^#{2,3}\s+(\S+)', line) or re.match(r'^(제\d+조)\(', line) or re.match(r'^([A-Z]{2}-\d+(?:\.\d+)?)\s+\S+\s*\S*$', line.strip())
            if m and '....' not in line:
                out.add(m.group(1))
    return out


def labels_in(text):
    return set(re.findall(r'\b[A-Z]{2}-\d+\.\d+\b|\bT-\d+\.\d+\b|제\d+조', text))


def missing_docs():
    """문서 목록에 있지만 받은 파일이 없는 문서 식별자."""
    return {r['문서 식별자'] for r in csv_rows(HERE / 'data/documents/catalog.csv') if not r.get('파일')}


def db():
    state = HERE / '.lab_connection.json'
    if not state.is_file():
        return None
    url = json.loads(read(state))['http'] + '/db/neo4j/tx/commit'
    def run(statements):
        body = json.dumps({'statements': [{'statement': s, 'parameters': p} for s, p in statements]}).encode()
        req = urllib.request.Request(url, body, {'Content-Type': 'application/json', 'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        if data.get('errors'):
            raise RuntimeError('; '.join(e.get('message', '') for e in data['errors']))
        return [[row['row'] for row in res['data']] for res in data['results']]
    return run


def check_loads(todo, known, cands):
    files = sorted(p for p in RESULT.glob('*.cypher'))
    print(f'output/의 Cypher 파일 {len(files)}개: ' + ', '.join(p.name for p in files))
    loads = [p for p in files if p.name != 'query.cypher']
    if not loads:
        todo.append('output/load.cypher가 없습니다 — python run.py load를 아직 실행하지 않았습니다.')
    seen_ids = set()
    for p in files:
        text = read(p)
        body = '\n'.join(l for l in text.splitlines() if not l.lstrip().startswith('//'))
        if WIPE.search(body):
            todo.append(f'{p.name}: 전체를 지우는 문장이 있습니다.')
        dels = [n for n, l in enumerate(text.splitlines(), 1) if DELETE.search(l) and not l.lstrip().startswith('//')]
        if dels and p.name == 'query.cypher':
            todo.append(f'query.cypher {", ".join(map(str, dels))}줄: 쿼리은 읽기만 합니다(DELETE).')
        elif dels:
            print(f'    참고: {p.name} {", ".join(map(str, dels))}줄에 DELETE — 적재문은 만들고 고치는 문장만 두어 다시 실행해도 같은 결과가 나오게 합니다.')
        tokens = set(re.findall(r'[\w:.@#-]+', body))
        used = sorted(x for x in tokens if held(x, cands)) if p.name != 'query.cypher' else []   # 쿼리은 보류 확인에서 보류 후보를 일부러 묻는다
        if used:
            todo.append(f'{p.name}: 승인(approved)이 아닌 후보 id를 가리킵니다 — {", ".join(used[:8])}')
        for lit in ID_LITERAL.findall(body):
            seen_ids.add(lit)
            if any(s.match(lit) for s in SHAPES) and lit not in known:
                todo.append(f'{p.name}: 기존 ID 꼴인데 설비 모델 · SOP 구조 · 조건표에 없는 ID — {lit}')
    return seen_ids


def check_db(todo, known, cands):
    run = db()
    if run is None:
        print('랩 DB: .lab_connection.json 없음(python run.py db)')
        todo.append('랩 DB를 아직 준비하지 않았습니다.')
        return
    try:
        ok_values = approved_values()
        bad_quotes = {c[4] for c in cands if c[3] != 'approved' and c[4] and c[4] not in ok_values}
        ids = sorted(known)
        res = run([('MATCH (n) WHERE n.id IS NULL OR NOT n.id IN $ids RETURN count(n)', {'ids': ids}),
                   ('MATCH (m)-[r]-(k) WHERE m.id IN $ids AND (k.id IS NULL OR NOT k.id IN $ids) RETURN labels(m)[0], type(r), count(DISTINCT r) ORDER BY 1, 2', {'ids': ids}),
                   ('MATCH (n) WHERE n.id IS NULL OR NOT n.id IN $ids UNWIND keys(n) AS k WITH n, k WHERE n[k] IS :: STRING RETURN coalesce(n.id, "(id 없음)"), k, n[k]', {'ids': ids}),
                   ('MATCH (n) UNWIND keys(n) AS k RETURN DISTINCT k', {}),
                   ('MATCH (n) WHERE n.id IS NULL OR NOT n.id IN $ids RETURN n.id', {'ids': ids})])
    except (OSError, urllib.error.URLError, RuntimeError, ValueError) as e:
        print(f'랩 DB 조회 실패: {e}')
        todo.append(f'랩 DB를 조회하지 못했습니다({e}). python run.py db 로 다시 켜고 실행합니다.')
        return
    extra, links, keys, new_ids = res[0][0][0], res[1], [r[0] for r in res[3]], [r[0] for r in res[4]]
    held_props = []
    for nid, k, value in res[2]:
        if (k == 'id' or len(value) < 80) and held(value, cands) or value in bad_quotes:
            held_props.append((nid, k))
        if len(held_props) >= 20:
            break
    total = sum(r[2] for r in links)
    print(f'랩 DB: 설비 모델 · 조치 기준 밖에서 적재한 노드 {extra}개, 그 노드와 기존 ID를 잇는 관계 {total}개'
          + (' — ' + ', '.join(f'{a} {t} {n}개' for a, t, n in links[:12]) if links else ''))
    if extra == 0:
        todo.append('랩 DB에 설비 모델 · 조치 기준 밖의 노드가 없습니다 — python run.py load를 아직 실행하지 않았습니다.')
    elif total == 0:
        todo.append(f'적재한 노드 {extra}개가 기존 ID와 하나도 이어지지 않았습니다.')
    for nid, k in held_props:
        todo.append(f'랩 DB 노드 {nid}의 {k}: 승인(approved)이 아닌 후보의 id · 인용입니다.')
    now = sorted(k for k in keys if NOW_KEYS.search(k))
    if now:
        todo.append(f'랩 DB에 현재값(재고 · 예약 · 입고) 속성이 있습니다 — {", ".join(now)}. 현재값은 그래프에 두지 않고 읽을 원천을 가리킵니다.')
    if any(x is None for x in new_ids):
        todo.append('랩 DB에 id가 없는 노드가 있습니다(새 대상도 ID로 찾아 다시 적재해도 늘지 않게 합니다).')
    present = headings()
    for nid in [x for x in new_ids if x]:
        ghost = sorted(lab for lab in labels_in(nid) if lab not in present)
        if ghost:
            todo.append(f'랩 DB 노드 {nid}: 원문에 절 머리가 없는 절 표기({", ".join(ghost)}) — 제공되지 않은 절은 노드로 만들지 않고 추가 자료가 필요한 질문으로 둡니다.')
        for doc in missing_docs():
            if doc in nid:
                todo.append(f'랩 DB 노드 {nid}: 받은 파일이 없는 문서({doc}) — 제공되지 않은 문서는 노드로 만들지 않고 추가 자료가 필요한 질문으로 둡니다.')


def check_export(todo):
    path = HERE / 'output/knowledge_export.json'
    if not path.is_file():
        print('output/knowledge_export.json: 없음')
        todo.append('output/knowledge_export.json이 없습니다(python run.py export).')
        return
    try:
        data = json.loads(read(path))
        ids = [n['props'].get('id') for n in data['nodes']]
        dup = sorted({i for i in ids if ids.count(i) > 1 and i is not None})
        ends = set(ids)
        dangling = [r for r in data['rels'] if r.get('a') not in ends or r.get('b') not in ends]
        questions = data.get('remaining_questions')
    except (ValueError, KeyError, TypeError, AttributeError) as e:
        todo.append(f'knowledge_export.json의 꼴이 계약과 다릅니다({e}).')
        return
    print(f'output/knowledge_export.json: 노드 {len(ids)}개 · 관계 {len(data["rels"])}개 · 추가 자료가 필요한 질문 {len(questions or [])}개')
    if None in ids:
        todo.append('knowledge_export.json에 id가 없는 노드가 있습니다.')
    if dup:
        todo.append(f'knowledge_export.json에 같은 id의 노드가 둘 이상 — {", ".join(dup[:6])}')
    if dangling:
        todo.append(f'knowledge_export.json에 끝점이 없는 관계 {len(dangling)}개 — 예: {dangling[0].get("type")} {dangling[0].get("a")} → {dangling[0].get("b")}')
    if not isinstance(questions, list):
        todo.append('knowledge_export.json에 remaining_questions 목록이 없습니다.')
    else:
        for q in questions:
            if not isinstance(q, dict) or not q.get('item') or not q.get('note'):
                todo.append('remaining_questions의 항목마다 item과 note가 필요합니다.')
                break


def empty_tables(md):
    out, sec, width = {}, '머리', None
    for line in md.splitlines():
        if line.startswith('## '):
            sec, width = line[3:].strip(), None
            continue
        if line.startswith('|'):
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            if all(re.fullmatch(r':?-{2,}:?', c) for c in cells):
                out.setdefault(sec, [0, 0])
                continue
            if width is None:
                width = len(cells)
                continue
            out.setdefault(sec, [0, 0])
            out[sec][0] += 1
            out[sec][1] += sum(1 for c in cells if not c)
        elif not line.strip():
            width = None
    return out


def check_record(todo, n):
    record = HERE / 'app/features/build_record.md'
    print(f'build_record.md')
    if not record.is_file():
        todo.append('build_record.md가 없습니다.')
        return
    text = read(record)
    for line in text.splitlines():
        if re.match(r'^- [^:]+:[ \t]*$', line):
            todo.append(f'build_record.md의 빈 항목 「{line.strip()}」')
    for sec, (rows, blanks) in empty_tables(text).items():
        state = '표에 기록 없음' if rows == 0 else f'{rows}행' + (f', 빈 칸 {blanks}개' if blanks else '')
        print(f'    「{sec}」: {state}')
        if rows == 0 or blanks:
            todo.append(f'build_record.md 「{sec}」 — {state}(실제로 센 수 · 조회 결과로 채웁니다)')


def card_sources():
    out = []
    for f in sorted((HERE / 'data/documents').iterdir()):
        if f.suffix in ('.md', '.txt', '.csv'):
            out.append((f.name, read(f)))
    return out


def check_card(path, docs, parts):
    errors, notes = [], []
    md = read(path)
    secs, cur = {}, None
    for line in md.splitlines():
        if line.startswith('## '):
            cur = line[3:].strip()
            secs[cur] = []
        elif cur is not None and line.strip():
            secs[cur].append(line)
    for h in HEADINGS:
        if h not in secs:
            errors.append(f'제목 「## {h}」 없음')
        elif not secs[h]:
            errors.append(f'「{h}」 아래가 비어 있음(없으면 「없음」과 까닭)')
    order = [h for h in secs if h in HEADINGS]
    if order != [h for h in HEADINGS if h in secs]:
        errors.append('제목의 순서가 계약과 다름')
    for h in ['준비 조건', '금지 · 제한', '작업 순서', '완료 기준']:
        for line in secs.get(h, []):
            if line.lstrip().startswith(('-', '*')) or re.match(r'^\s*\d+\.', line):
                if not QUOTE.search(line) and '없음' not in line:
                    errors.append(f'「{h}」 항목에 「원문 인용」이 없음: {line.strip()[:60]}')
    quotes = QUOTE.findall(md)
    for q in quotes:
        if not any(q in text for _, text in docs):
            errors.append(f'data/documents/ 어디에도 그대로 없는 인용: 「{q[:50]}」')
    for p in sorted(set(re.findall(r'\bP-[A-Z0-9]+(?:-[A-Z0-9]+)*', md))):
        if p not in parts:
            errors.append(f'설비 모델에 없는 품번 {p}')
    notes.append(f'인용 {len(quotes)}개')
    return errors, notes


def check_cards(todo):
    docs = card_sources()
    graph = json.loads(read(basis('model/graph.json')))
    parts = {n['props']['id'] for n in graph['nodes'] if n['labels'][0] == 'Part'}
    cards = sorted(RESULT.glob('work_card_*.md'))
    print(f'작업 확인 카드 {len(cards)}개')
    for c in cards:
        errors, notes = check_card(c, docs, parts)
        print(f'    {c.name}: {"형식 통과" if not errors else f"확인 필요 {len(errors)}건"} · ' + ' · '.join(notes))
        for e in errors[:20]:
            print('      - ' + e)
        if errors:
            todo.append(f'{c.name} 형식 확인 필요.')
    if len(cards) < 2:
        todo.append('이 사건의 작업과 다른 작업 하나 이상의 카드가 필요합니다.')


def slot_errors():
    """빈 틀의 꼴 — 제공 코드(app/utils/graph.py)의 검사로 본다."""
    from app.utils import graph as G
    out = []
    known = G.model_ids()[0]
    for fn in (G.shape, lambda: G.link_rows(known), lambda: G.alias_rows(known), lambda: G.other_rows(known), G.role_rows, G.now_rows):
        try:
            fn()
        except G.Problem as e:
            out.append(f'빈 틀: {e}')
    return out


def main():
    todo = []
    known = known_ids()
    cands = reviews()
    print(f'기준 입력: {basis("reviews").relative_to(HERE).as_posix()}(후보 {len(cands)}개, 승인 {sum(1 for c in cands if c[3] == "approved")}개) · '
          f'{basis("model/graph.json").relative_to(HERE).as_posix()} · {basis("sop.json").relative_to(HERE).as_posix()} · {basis("conditions.csv").relative_to(HERE).as_posix()}')
    schema = HERE / 'output/schema_ext.json'
    if not schema.is_file():
        todo.append('output/schema_ext.json이 없습니다.')
    else:
        try:
            ext = json.loads(read(schema))
            print(f'    schema_ext.json: 종류 {len(ext.get("classes", {}))}개 · 관계 {len(ext.get("relations", {}))}개')
        except ValueError as e:
            todo.append(f'schema_ext.json을 읽지 못했습니다({e}).')
    check_loads(todo, known, cands)
    check_db(todo, known, cands)
    check_export(todo)
    check_record(todo, 5)
    if PRACTICAL:
        check_cards(todo)
    todo += slot_errors() + chosen_errors(HERE) + provided_errors(HERE)
    print()
    if todo:
        print('구조 확인 필요:')
        for t in todo:
            print('  - ' + t)
        print(END)
        return 1
    print('구조 검사 통과. ' + END)
    return 0


def chosen_errors(root):
    """app/features/decisions.csv — 빈 칸 · 근거 꼴(파일:줄)만 본다. 고른 것이 맞는지는 보지 않는다."""
    import csv, io, re
    p = root / 'app/features' / 'decisions.csv'
    if not p.is_file():
        return ['app/features/decisions.csv가 없습니다 — 받은 ZIP의 빈 틀을 지우지 않습니다.']
    lines = [x for x in p.read_text(encoding='utf-8-sig').splitlines() if x.strip() and not x.lstrip().startswith('#')]
    rows = list(csv.DictReader(io.StringIO('\n'.join(lines))))
    need = ['지점', '고른_것', '근거', '바뀌는_답']
    if not lines or [c.strip() for c in csv.reader([lines[0]]).__next__()] != need:
        return ['app/features/decisions.csv: 열 이름이 ' + ','.join(need) + '이어야 합니다.']
    out = []
    for n, r in enumerate(rows, 1):
        empty = [c for c in need if not (r.get(c) or '').strip()]
        if empty:
            out.append(f'app/features/decisions.csv {n}번째 행: 빈 칸 ' + ', '.join(empty) + '(못 정했으면 고른_것에 「미결」).')
        elif not re.search(r'[^\s:]+:\d+', r['근거']):
            out.append(f'app/features/decisions.csv {n}번째 행: 근거에 파일:줄이 없습니다.')
    return out

import hashlib as _h
_PROVIDED = {
 "app/ui/render.py": "794a7c0de17bbbf7dd6e2896397c1db32cb4079b6fe7dfa88dc67160c2a0d81e",
 "app/utils/actions.py": "fc84830c7e708c29ea3c8c4d128065212447abd7d0a249501445b0f3b6a3adef",
 "app/utils/cypher.py": "6c6272d9ea66ae25a3635280fba4b6a6e554eff91ff01b9e98a8ab64caf1946e",
 "app/utils/db.py": "4d5d6187db53e56f39d7ad9802a5477803bc55d7ab589470f7648124beaef200",
 "app/utils/graph.py": "ccf03d4913a7036f64fef1dc1101df79c4c3f93495301515ef33013530c33ee4",
 "app/utils/results.py": "1c5b0596745e9ac1e9b7f06d84c7463d99720597edcf46801d32a51e640ae86b",
 "run.py": "a00350d7fc80b54988ee7ae1a54303f29f99f4940aa7678ce214bf301e74159d"
}
def provided_errors(root):
    out = []
    for name, digest in _PROVIDED.items():
        p = root / name
        if not p.is_file():
            out.append(f'제공 파일이 없습니다: {name} — 받은 ZIP의 것으로 되돌리세요.')
        elif _h.sha256(p.read_bytes()).hexdigest() != digest:
            out.append(f'제공 파일이 바뀌었습니다: {name} — 받은 ZIP의 것으로 되돌리세요.')
    return out

if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError) as e:
        print('실행 확인 필요: ' + str(e))
        sys.exit(1)
