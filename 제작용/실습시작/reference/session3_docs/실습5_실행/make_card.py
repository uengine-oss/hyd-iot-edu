"""강사 참조: 랩 DB 조회 결과와 기록(작업지시·재고)으로 작업 확인 카드를 만든다. 학생 배포 금지.
사용: python make_card.py SOP-COOL-14 [--match broad|strict] [--stock now|pr07] [--out 결과]
  --match  지난 시행으로 볼 작업지시: broad(기본) 절차 ID·구판 ID·작업 이름과 현장 약어, strict 절차 ID·구판 ID만
  --stock  부품 준비 수량: now(기본) 현재고−예약(HI-01 SOP-HI-03 3단계), pr07 현재고−예약+입고 예정(PR-07 7.2 가용 재고)
카드의 조건·출처는 DB 조회 결과에서 온다. 검토본 JSON은 적재하지 않은 후보(보류·제외·누락)를 남은 질문으로 옮길 때만 읽는다.
원문 파일은 PM-2.2 표의 부품 수량처럼 지식 후보가 없는 원문 근거를 직접 인용할 때만 읽는다.
"""
from pathlib import Path
import csv
import datetime as dt
import json
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from lab_cypher import cypher  # noqa: E402

KNOW = '''
MATCH (p:Procedure {id: $pid})-[:DEFINED_IN]->(s:Section)-[:IN_DOCUMENT]->(d:Document)
CALL {
  WITH p MATCH (p)-[:HAS_STEP|HAS_CONDITION]->(k:Knowledge) RETURN k, '절차 안' AS via
  UNION WITH p MATCH (k:Knowledge)-[:REFERS_TO]->(p) RETURN k, '이 절차를 ID로 가리킴' AS via
  UNION WITH p, s MATCH (k:Knowledge)-[:STATED_IN]->(s) WHERE NOT (k)<-[:HAS_STEP|HAS_CONDITION]-(:Procedure) AND k.kind <> 'unit_value' RETURN k, '같은 절의 절차 밖 문장' AS via
  UNION WITH p MATCH (p)-[:HAS_STEP|HAS_CONDITION]->(:Knowledge)-[:REFERS_TO]->(rs:Section)<-[:STATED_IN]-(k:Knowledge) WHERE NOT (k)<-[:HAS_STEP|HAS_CONDITION]-(:Procedure) RETURN k, '단계가 가리킨 절 ' + rs.section AS via
  UNION WITH p MATCH (p)-[:HAS_STEP]->(:Knowledge)-[:REFERS_TO]->(rp:Procedure)-[:HAS_STEP|HAS_CONDITION]->(k:Knowledge) RETURN k, '단계가 가리킨 절차 ' + rp.id AS via
}
MATCH (k)-[:STATED_IN]->(ks:Section)
OPTIONAL MATCH (k)<-[:HAS_STEP|HAS_CONDITION]-(owner:Procedure)
OPTIONAL MATCH (k)-[:ABOUT_QUANTITY]->(q:Quantity)
OPTIONAL MATCH (k)-[:MENTIONS_PART]->(part:Part)
RETURN p.id, p.name, d.id, d.status, d.sha256, s.section, k.id, k.kind, k.text, k.quote, k.order, k.value, k.value_max, k.unit,
       k.comparator, ks.section, owner.id, via, collect(DISTINCT q.id), collect(DISTINCT part.id), k.refs, k.unresolved_parts
ORDER BY k.id
'''
ASSETS = 'MATCH (p:Procedure {id: $pid}) OPTIONAL MATCH (p)-[x:APPLIES_TO]->(a:Asset) RETURN collect(a.id), collect(DISTINCT x.basis)'
SUPPLY = '''MATCH (part:Part {id: $part}) OPTIONAL MATCH (sup:Supplier)-[r:SUPPLIES]->(part)
RETURN part.name, collect([sup.name, r.approved, r.price_manwon, r.defect_rate, r.lead_days])'''
SAME_PART = '''MATCH (p:Procedure {id: $pid})-[:HAS_STEP|HAS_CONDITION]->(:Knowledge)-[:MENTIONS_PART]->(part:Part)<-[:MENTIONS_PART]-(k:Knowledge)
WHERE k.doc_id <> p.doc_id OPTIONAL MATCH (k)<-[:HAS_STEP|HAS_CONDITION]-(o:Procedure)
RETURN DISTINCT part.id, k.id, k.doc_id, k.section, o.id, k.quote ORDER BY k.id'''
# 작업 이름과 현장 약어(작업지시 서술을 읽고 정함). 구판 ID는 갈래/HM-8_판대응표.csv에서 읽는다.
WORDS = {
    'SOP-COOL-14': [r'핀\s*세척', r'핀\s*청소', r'핀세척', r'\bfin\b', r'쿨러 청소', r'쿨러 핀', r'HM-7\.6'],
    'SOP-PM-21': [r'2000\s*h', r'2,000\s*h', r'2천', r'PM 2천'],
    'SOP-PM-22': [r'4000\s*h', r'4,000\s*h', r'4천'],
    'T-3.1': [r'RTN FLT', r'리턴 필터', r'Return filter'],
    'T-4.1': [r'ACC', r'어큐', r'프리차지', r'N2'],
}
PACKAGE = {'SOP-PM-21': '2,000 h', 'SOP-PM-22': '4,000 h', 'SOP-PM-23': '8,000 h'}
REV11 = dt.date(2026, 9, 1)   # 문서 목록: HM-8 1.1판 시행일


def rows(statement, **params):
    return [r['row'] for r in cypher([(statement, params)])[0]['data']]


def records(name):
    lines = [l for l in (HERE / '자료/기록' / name).read_text(encoding='utf-8').splitlines() if not l.startswith('#')]
    return list(csv.DictReader(lines)), next(l for l in (HERE / '자료/기록' / name).read_text(encoding='utf-8').splitlines() if l.startswith('#'))


def asset_of(alias):
    m = re.search(r'(?:HYD[- ]?0?|HPU-L2-0|#|^)(\d)(?:호기| 파워팩|$)?', alias.strip())
    return f'HYD-0{m.group(1)}' if m else None


def old_ids(pid):
    path = HERE.parent / '갈래/HM-8_판대응표.csv'
    if not path.is_file():
        return []
    with path.open(encoding='utf-8') as f:
        return [r['1.0판 절차'] for r in csv.DictReader(f) if r['1.1판 절차'] == pid]


def num(text, pattern):
    m = re.search(pattern, text)
    return float(m.group(1).replace(',', '')) if m else None


def assess(pid, wo):
    """작업지시 한 행이 완료 기준을 보여 주는지. 근거 문장은 카드의 완료 기준 절에 있다."""
    rec, text, notes = wo['측정·시운전 기록'], wo['작업 내용'], []
    if wo['상태'] != '완료':
        return f'상태 {wo["상태"]}' + (f', 예정 {wo["예정일"]}' if wo['예정일'] else '') + ' — 시행 전'
    if not wo['완료일']:
        notes.append('완료일 없음')
    if pid == 'SOP-COOL-14':
        ce = num(rec, r'CE\s*(\d+(?:\.\d+)?)')
        day = dt.date.fromisoformat(wo['완료일'] or wo['요청일'])
        rev, need = ('1.1', 80) if day >= REV11 else ('1.0', 75)
        if ce is None:
            notes.append(f'CE 기록 없음 → 완료 기준 확인 불가(HI-01 SOP-HI-02 3단계: 확인 필요)')
        else:
            notes.append(f'CE {ce:g} % — 시행일 기준 {rev}판 {need} % 이상 {"충족" if ce >= need else "미달"}' + ('' if rev == '1.1' else f', 1.1판 80 % 기준으로는 {"충족" if ce >= 80 else "미달"}'))
        if '고압' in text:
            notes.append('기록에 「고압 세척기」 — 1.1판 금지 「고압수는 쓰지 않는다」와 맞지 않음, 확인 필요')
        if '저압수' in text:
            notes.append('기록에 「저압수」 — 1.0판은 허용, 1.1판은 압축공기만 적음(저압수 언급 없음), 확인 필요')
    elif pid in ('SOP-PM-21', 'SOP-PM-22'):
        ps, fs, vs = num(rec, r'PS1\s*(\d+(?:\.\d+)?)'), num(rec, r'FS1\s*(\d+(?:\.\d+)?)'), num(rec, r'VS1\s*(\d+(?:\.\d+)?)')
        h = num(wo['운전시간(h)'], r'([\d,]+)')
        if h is not None and h > 2200:
            notes.append(f'운전시간 {h:,.0f} h — PM-2.3 허용 오차 상한 2,200 h 초과 시행')
        if ps is None and fs is None:
            notes.append('시운전 값 없음 → PM-2.9 완료 확인 불가(확인 필요)')
        else:
            bad = [f'{n} {v:g}' for n, v, ok in [('PS1', ps, ps is not None and ps >= 178), ('FS1', fs, fs is not None and fs >= 8.8), ('VS1', vs, vs is not None and vs < 1.2)] if v is not None and not ok]
            lack = [n for n, v in [('PS1', ps), ('FS1', fs), ('VS1', vs)] if v is None]
            notes.append('PM-2.9 ' + ('미달 ' + ', '.join(bad) + ' — 완료로 닫힘(PM-2.9 「정비 오더를 닫지 않는다」와 맞지 않음, 확인 필요)' if bad else '기준 충족') + (f', 기록 없는 값 {lack}' if lack else ''))
        notes.append('교체 부품 로트 기록 없음(PM-2.3 기록 요건)' if '로트' not in rec + wo['사용 부품'] else '로트 기록 있음')
        if pid == 'SOP-PM-22' and not re.search(r'ACC|프리차지|N2', text + rec):
            notes.append('프리차지 점검 기록 없음')
    elif pid == 'T-3.1':
        dp = num(rec, r'(?:dP|차압)\s*(\d+(?:\.\d+)?)\s*psi')
        notes.append('차압 기록 없음 → 6단계 완료 확인 불가(확인 필요)' if dp is None else f'차압 {dp:g} psi — 10 psi 미만 {"충족" if dp < 10 else "미달"}')
        notes.append('엘리먼트 로트 기록 없음(6단계)' if '로트' not in rec else '로트 기록 있음')
    elif pid == 'T-4.1':
        both = rec + ' ' + text
        psi = num(both, r'보정\s*([\d,]+)\s*psi') or num(both, r'([\d,]+(?:\.\d+)?)\s*psi')
        bar = num(both, r'([\d.]+)\s*bar')
        val = psi if psi is not None else (bar * 14.5 if bar is not None else None)
        if val is None:
            notes.append('프리차지 값 기록 없음(확인 필요)')
        else:
            src = f'{psi:,.0f} psi' if psi is not None else f'{bar:g} bar ≈ {val:,.0f} psi(1 bar = 14.5 psi, 머리말)'
            low = val < 1450 * 0.9
            notes.append(f'{src} — 명판 1,450 psi의 90 %(1,305 psi) {"미만 → 재충전 대상" if low else "이상"}' + (', 재충전 기록 ' + ('있음' if '→' in both or '재충전' in text else '없음(확인 필요)') if low else ''))
        if '보정' not in rec:
            notes.append('20 °C 보정값인지 기록 없음(3단계)')
    return '; '.join(notes) or '판정할 기록 없음'


def card(pid, match='broad', stock='now'):
    data = rows(KNOW, pid=pid)
    if not data:
        return None
    pid_, name, did, dstatus, sha, sec = data[0][:6]
    items = {}
    for r in data:
        kid = r[6]
        if kid in items:
            items[kid]['via'].add(r[17]); continue
        items[kid] = dict(id=kid, kind=r[7], text=r[8], quote=r[9], order=r[10], value=r[11], value_max=r[12], unit=r[13], cmp=r[14],
                          sec=r[15], owner=r[16], via={r[17]}, qs=r[18], parts=r[19], refs=r[20] or [], unresolved=r[21] or [])
    # 단계가 「1~6단계」처럼 다른 절차의 일부 단계만 가리키면 그 범위 밖 단계는 뺀다
    ranges = {}
    for i in items.values():
        if i['owner'] == pid_ and i['kind'] == 'step':
            m = re.search(r'(\d+)~(\d+)단계', i['quote'])
            for ref in i['refs']:
                if m:
                    ranges[ref] = (int(m.group(1)), int(m.group(2)))
    for kid in list(items):
        i = items[kid]
        if i['owner'] in ranges and i['owner'] != pid_:
            lo, hi = ranges[i['owner']]
            if i['kind'] == 'step' and not lo <= i['order'] <= hi:
                del items[kid]
            elif i['kind'] != 'step' and i['kind'] != 'precondition':
                del items[kid]       # 범위 밖 단계의 완료 조건 등은 가져오지 않는다(시운전은 이 절차의 단계가 정함)
            elif i['quote'].startswith('승인'):
                del items[kid]
    def src(i):
        return f'{i["sec"]} 「{i["quote"]}」 ({i["id"]})'
    assets, basis = rows(ASSETS, pid=pid_)[0]
    own_steps = sorted([i for i in items.values() if i['owner'] == pid_ and i['kind'] == 'step'], key=lambda x: x['order'])
    other = [i for i in items.values() if not (i['owner'] == pid_ and i['kind'] == 'step')]
    approval = [i for i in other if i['kind'] == 'precondition' and re.match(r'^승인', i['quote']) and i['owner'] in (pid_, None)]
    sec_approval = [i for i in other if i['kind'] == 'precondition' and '승인은' in i['quote'] and i['owner'] is None]
    approval += [i for i in sec_approval if i not in approval]
    referenced_steps = sorted([i for i in other if i['kind'] == 'step'], key=lambda x: (x['owner'], x['order']))
    cond = lambda k: [i for i in other if i['kind'] == k and i not in approval]
    L = [f'# 작업 확인 카드 — {pid_} {name}', '']
    L += ['## 대상 작업', '', f'- {pid_} {name}', f'- 문서 {did} · 상태 {dstatus} · SHA-256 {sha[:12]} · 절차 정의 절 {sec}',
          f'- 적용 설비: {", ".join(sorted(assets)) if assets else "문서가 적용 설비를 정하지 않음(남은 질문)"}' + (f' — 근거 {basis[0]}' if basis else ''),
          '- 근거: 랩 DB 조회 결과(approved 지식만). 이 카드는 현재 설비 상태를 읽지 않고, 재고 사용과 승인을 대신하지 않는다.',
          f'- 판단 갈래: 지난 시행 {"절차 ID·구판 ID·작업 이름과 현장 약어" if match == "broad" else "절차 ID·구판 ID만"} / 부품 수량 {"현재고−예약(HI-01 SOP-HI-03)" if stock == "now" else "현재고−예약+입고 예정(PR-07 7.2)"}', '']
    for title, kind in [('준비 조건', 'precondition'), ('금지·제한', 'prohibition')]:
        L += [f'## {title}', '']
        L += [f'- {i["text"]} — {src(i)} · 찾은 경로: {", ".join(sorted(i["via"]))}' for i in cond(kind)] or ['- 없음 — 조회 결과 없음']
        L.append('')
    L += ['## 작업 순서', '']
    for i in own_steps:
        L.append(f'{i["order"]}. {i["text"]} — {i["sec"]} 「{i["quote"]}」 ({i["id"]})')
        for j in [x for x in referenced_steps if x['owner'] in i['refs']]:
            L.append(f'   - {j["owner"]} {j["order"]}단계: {j["text"]} — {src(j)}')
    if not own_steps:
        L.append('- 없음 — 조회 결과 없음')
    L += ['', '## 완료 기준', '']
    L += [f'- {i["text"]} — {src(i)} · 찾은 경로: {", ".join(sorted(i["via"]))} · 작업 뒤 실제 관측값으로 판정' for i in cond('completion')] or ['- 없음 — 조회 결과 없음']
    values = [i for i in other if i['kind'] == 'unit_value']
    if values:
        L += ['', '문서의 기준값(현재 값과 구분):', '']
        for i in values:
            v = f'{i["value"]:g}~{i["value_max"]:g}' if i['value_max'] is not None else f'{i["value"]:g}'
            L.append(f'- {v} {i["unit"]} (비교 {i["cmp"] or "표현 없음"}) — {src(i)} · 물리량 {", ".join(i["qs"]) or "연결 없음"}')
    L += ['', '## 작업 직전 확인할 현재 값', '', '문서의 기준은 위 항목이다. 아래가 지금 충족되는지는 작업 직전에 설비·운전 기록·현장에서 확인한다. 그래프에는 현재 값이 없다.', '']
    for i in cond('precondition') + cond('prohibition'):
        where = '현재 값 필요: ' + ', '.join(i['qs']) if i['qs'] else '현장·운전 기록에서 확인(기존 모델에 상태 ID 없음)'
        L.append(f'- {i["text"]} → {where}')
    if pid_.startswith('SOP-PM-'):
        L.append('- 마지막 정기 정비 뒤 운전시간(계수기) → 현재 값 필요(CMMS). PM-2.3·PM-2.5의 기한 조건은 이 작업 카드의 절 밖이다(남은 질문).')
    # 부품 준비
    stock_rows, stock_head = records('재고_현황.csv')
    L += ['', '## 부품 준비', '', f'- 재고 기준: {stock_head.lstrip("# ").split(" — ")[0]}', '']
    part_ids = sorted({p for i in items.values() for p in i['parts']})
    qty_note = ''
    if pid_ in PACKAGE:
        md = (HERE / '자료/원문/PM-02_powerpack-pm-checklist.md').read_text(encoding='utf-8')
        row = next(l for l in md.splitlines() if l.startswith(f'| {PACKAGE[pid_]} |'))
        cell = [c.strip() for c in row.strip('|').split('|')][3]
        qty_note = f'필요 수량 근거: PM-2.2 표 「{cell}」(표 칸의 단위 없는 수량이라 지식 후보 없음 — 원문 직접 확인)'
        if '패키지와 같음' in cell:
            base = re.search(r'([\d,]+ h) 패키지', cell).group(1)
            row2 = next(l for l in md.splitlines() if l.startswith(f'| {base} |'))
            qty_note += f' → PM-2.2 표 「{[c.strip() for c in row2.strip("|").split("|")][3]}」'
    if qty_note:
        L.append(f'- {qty_note}')
    for p in part_ids:
        s = next((r for r in stock_rows if r['품번'] == p), None)
        pname, offers = rows(SUPPLY, part=p)[0]
        if s is None:
            L.append(f'- {p} {pname}: 재고_현황.csv에 행 없음 → 확인 필요')
        else:
            on, res, order = int(s['현재고(on_hand)']), int(s['예약(reserved)']), int(s['입고 예정(on_order)'])
            n = on - res if stock == 'now' else on - res + order
            rule = '현재고−예약' if stock == 'now' else '현재고−예약+입고 예정'
            L.append(f'- {p} {pname}(제조사 품번 {s["제조사 품번"]}): 현재고 {on}, 예약 {res}({s["예약 근거"] or "—"}), 입고 예정 {order}{(" " + s["입고 예정일"]) if s["입고 예정일"] else ""}{(" · " + s["발주 상태"]) if s["발주 상태"] else ""} → {rule} = {n}{"" if n > 0 else " → 준비 불가 또는 확인 필요"}')
        ok = [o for o in offers if o[0]]
        if ok:
            L.append('  - 공급 조건(참고, 2회차 모델): ' + '; '.join(f'{o[0]} 승인 {"예" if o[1] else "아니오"} 단가 {o[2]:g}만원 불량률 {o[3]:g} 납기 {o[4]}일' for o in ok))
    unresolved_parts = [i for i in items.values() if i['unresolved']]
    for i in unresolved_parts:
        L.append(f'- {i["id"]}: 이름이 여러 부품과 맞아 연결하지 않음 {i["unresolved"]}')
    if pid_ == 'T-4.1':
        n2 = next((r for r in stock_rows if '질소' in r['품명']), None)
        if n2:
            L.append(f'- 건조 질소(4절 「Use dry nitrogen only.」): 재고_현황.csv 「{n2["품명"]}」 — {n2["발주 상태"]} → 공구실 대장 확인 필요')
    if not part_ids and pid_ != 'T-4.1':
        L.append('- 없음 — 이 작업의 지식에 연결된 부품이 없다')
    # 지난 시행 기록
    wos, wo_head = records('작업지시_서술.csv')
    ids = [pid_] + old_ids(pid_)
    pats = [re.escape(x) for x in ids] + (WORDS.get(pid_, []) if match == 'broad' else [])
    scope = set(assets) if assets else None
    found, out_scope = [], []
    for w in wos:
        if not any(re.search(p, w['작업 내용'], re.I) for p in pats):
            continue
        a = asset_of(w['설비'])
        (found if scope is None or a in scope else out_scope).append((w, a))
    L += ['', '## 지난 시행 기록', '', f'- 기록: {wo_head.lstrip("# ").split(" — ")[0]} · 찾은 기준: {", ".join(ids)}' + (' + 작업 이름·현장 약어' if match == 'broad' else ''), '']
    for w, a in found:
        L.append(f'- {w["작업지시"]} {w["설비"]}({a or "설비 미상"}) 완료일 {w["완료일"] or "—"} 「{w["작업 내용"]}」 → {assess(pid_, w)}')
    if not found:
        L.append('- 없음 — 찾은 기준에 맞는 작업지시가 없다')
    if out_scope:
        L.append(f'- 적용 설비 밖이라 뺀 작업지시: ' + ', '.join(f'{w["작업지시"]} {w["설비"]}({a or "설비 미상"})' for w, a in out_scope))
    L += ['', '## 승인', '']
    L += [f'- {i["text"]} — {src(i)} · 승인 필요(카드가 승인하지 않음)' for i in approval] or ['- 없음 — 원문에서 승인 역할을 찾지 못함, 확인 필요']
    # 남은 질문
    q = []
    if not assets:
        q.append(f'{did}는 적용 설비를 ID로 정하지 않는다. 그래프에서 {pid_}와 설비를 연결하지 않았다. 어느 설비에 적용하는지 확인 필요.')
    for r in rows(SAME_PART, pid=pid_):
        q.append(f'다른 문서 {r[2]} {r[3]}{(" " + r[4]) if r[4] else ""}도 같은 부품 {r[0]}을 다룬다: 「{r[5]}」({r[1]}). 같은 항목을 두 문서가 다르게 정하면 어느 쪽을 따를지 확인(제조사 발췌 머리말: PM-02 우선).')
    secs = {i['sec'] for i in items.values()} | {sec}
    doc_id = did.split('@')[0]
    for path in sorted((HERE / '입력/검토결과').glob('*_검토.json')):
        review = json.loads(path.read_text(encoding='utf-8'))
        if review['doc_id'] != doc_id:
            continue
        for c in review['candidates']:
            if c['status'] != 'approved' and (c['section'] in secs or pid_ in c['refs']):
                q.append(f'적재하지 않은 후보 {c["id"]}({c["decision"]}, {c["section"]}): 「{c["quote"]}」 — {c["reason"]}')
        for m in review.get('missing', []):
            if not m['added'] and m['section'] in secs:
                q.append(f'검토 때 기록한 누락 {m["section"]} 「{m["quote"]}」 — {m["note"]}')
    if pid_ == 'T-3.1':
        q.append('새 O링은 4단계에 있으나 재고_현황·모델에 품번이 없다. 엘리먼트에 포함되는지 확인 필요.')
    aliases = sorted({w['설비'] for w, a in found if a and w['설비'] not in ('HYD-01', 'HYD-02', 'HYD-03', 'HYD-04')})
    if aliases:
        q.append(f'작업지시의 설비 별칭 {", ".join(aliases)}를 n호기·#n·HPU-L2-0n = HYD-0n 관례로 읽었다. 설비 대장에는 HPU-L2-01만 등록돼 있다.')
    if match == 'broad':
        q.append('작업 이름·현장 약어로 찾은 작업지시는 이 절차를 따른 시행인지 기록만으로 확정할 수 없다(절차 ID가 없는 행). 담당자 확인 필요.')
    L += ['', '## 남은 질문', '']
    L += [f'- {x}' for x in q] or ['- 없음']
    return '\n'.join(L) + '\n', len(found)


if __name__ == '__main__':
    pid = sys.argv[1]
    opt = lambda k, d: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
    match, stock, out = opt('--match', 'broad'), opt('--stock', 'now'), opt('--out', '결과')
    res = card(pid, match, stock)
    if res is None:
        print(f'{pid}: 랩 DB에 이 절차가 없습니다(원문이 제공하지 않는 작업이거나 적재되지 않음). 카드를 만들지 않습니다.')
        sys.exit(3)
    text, n = res
    dest = HERE / out / f'작업확인카드_{pid}.md'
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding='utf-8')
    print(f'{dest.relative_to(HERE)} 저장 ({text.count(chr(10))}줄, 지난 시행 {n}건)')
