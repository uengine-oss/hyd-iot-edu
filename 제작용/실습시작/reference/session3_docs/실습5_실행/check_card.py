"""실습5 단계별 상태와 작업 확인 카드의 형식 검사. 생성·수정·DB 변경을 하지 않는다.
카드의 「인용」이 원문·기록 파일에 그대로 있는지, 카드가 가리킨 작업지시·품번이 자료에 있는지만 대조한다.
조건이 빠졌는지, 지난 시행을 어떻게 골랐는지, 수량을 어떻게 셌는지가 맞는지는 판정하지 않는다.
랩 DB가 준비돼 있으면 읽기 조회로 「적재한 지식이 앞 단계 모델의 기존 ID와 이어졌는지」 개수만 센다(어디에 이어야 맞는지는 판정하지 않는다).
사용: python check_card.py
"""
from pathlib import Path
import csv, json, re, sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
HEADINGS = ['대상 작업', '준비 조건', '금지·제한', '작업 순서', '완료 기준', '작업 직전 확인할 현재 값', '부품 준비', '지난 시행 기록', '승인', '남은 질문']
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
