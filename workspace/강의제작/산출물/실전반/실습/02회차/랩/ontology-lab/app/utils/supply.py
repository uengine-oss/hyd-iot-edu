"""설비 · 부품 모델에 공급 정보를 더하는 제공 코드 — `data/model/`의 모델과 `data/`의 원자료, `app/features/`의 판단 함수(내가 쓴 것)를 읽어 `output/schema.json` · `output/graph.json`을 쓴다.

이 파일은 누가 해도 같은 일만 한다: 파일 읽기, 견적표 공급사 칸에서 괄호 앞 이름 떼기, 품번 칸이 품명으로 적힌 줄을 예비품 목록의 품명으로 찾기,
단위 맞추기(불량률 % → 0~1 비율, 납기 「주」 → 일 — 바꾼 값은 원래 표기를 *_original에 남김), 값마다 출처 남기기(파일 · 줄과 기준일),
계약 꼴로 쓰기, 모델에 물어보기. 어느 견적을 기준일 조건으로 쓸지, 승인을 어떻게 담을지, 구매 담당에게 무엇을 함께 남길지는 `app/features/`의 판단 함수가 정한다.
직접 실행하지 않는다 — 루트 run.py가 요청한 기능을 실행한다.
"""
from pathlib import Path
import csv
import importlib.util
import io
import json
import re

HERE = Path(__file__).resolve().parents[2]
DATA = HERE / 'data'
OUT = HERE / 'app/features'
OUTPUT = HERE / 'output'
AS_OF = '2026-10-15'      # 자료 기준일(현장 메모 · 가이드)
QUOTES, AVL = 'supply_terms.csv', 'approved_suppliers.csv'


class Stop(Exception):
    """판단 함수의 답이 계약과 다름 · 원자료를 읽지 못함. 글에 파일 · 행이 있다."""


def table(name):
    with (DATA / name).open(encoding='utf-8-sig', newline='') as f:
        return [(line, {k: (v or '').strip() for k, v in r.items()}) for line, r in enumerate(csv.DictReader(f), 2)]


def source(name, line):
    return f'{name} {line}행'


def load_rule(name):
    path = OUT / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def supplier_name(text):
    """견적표 공급사 칸의 괄호 앞 이름(「B-OEM (순정)」 · 「B-OEM(순정)」 → 「B-OEM」)."""
    return re.split(r'\s*\(', text, 1)[0].strip()


def base_model():
    schema = json.loads((HERE / 'data/model/schema.json').read_text(encoding='utf-8'))
    graph = json.loads((HERE / 'data/model/graph.json').read_text(encoding='utf-8'))
    return schema, graph


def part_of(text, parts, line):
    """견적표 품번 칸 → 사내 품번. 사내 품번이면 그대로, 품명으로 적혔으면 예비품의 같은 품명 하나."""
    if text in parts:
        return text, '사내 품번'
    hits = [p for p, props in parts.items() if props.get('name') == text]
    if len(hits) == 1:
        return hits[0], '품명'
    raise Stop(f'data/{QUOTES}:{line}: 품번 칸 「{text}」을 사내 품번으로 찾지 못했습니다(품명 일치 {len(hits)}개).')


def defect(text):
    t = text.strip()
    if t.endswith('%'):
        return float(t[:-1]) / 100, t
    return float(t), None


def lead(text):
    t = text.strip()
    if t.endswith('주'):
        return int(t[:-1]) * 7, t
    return int(t), None


def quote_groups():
    """견적 줄을 (공급사 이름, 사내 품번) 쌍으로 모은다. 돌려주는 것: ({쌍: [줄 dict]}, 품번 찾은 줄 [(줄, 원래 글, 사내 품번, 찾은 법)])."""
    _, graph = base_model()
    parts = {n['props']['id']: n['props'] for n in graph['nodes'] if 'Part' in n['labels']}
    grouped, found = {}, []
    for line, r in table(QUOTES):
        pid, how = part_of(r['품번'], parts, line)
        if how != '사내 품번':
            found.append((line, r['품번'], pid, how))
        grouped.setdefault((supplier_name(r['공급사']), pid), []).append({**r, '줄': line})
    return grouped, found


def several_live():
    """기준일에 유효기한이 남은 견적이 둘 이상인 쌍 — [(공급사, 사내 품번, [줄])]. 어느 줄을 쓸지는 정하지 않는다(app/features/decisions.csv의 결정)."""
    grouped, _ = quote_groups()
    return [(sup, pid, [q['줄'] for q in quotes if q['유효기한'] >= AS_OF]) for (sup, pid), quotes in sorted(grouped.items())
            if sum(q['유효기한'] >= AS_OF for q in quotes) > 1]


def pairs(stage):
    """stage = '견적'(app/features/quote_rule.py까지) · '승인'(app/features/approval_rule.py까지).
    돌려주는 것: (쌍 목록 [dict], 견적 줄 갈래 {줄: '씀' · '기준일에 안 씀'}, 품번 찾은 줄 [(줄, 원래 글, 사내 품번, 찾은 법)])."""
    quote_rule = load_rule('quote_rule.py')
    grouped, found = quote_groups()
    used, out = {}, []
    for (sup, pid), quotes in sorted(grouped.items()):
        pick = quote_rule.use_quote([dict(q) for q in quotes], AS_OF)
        if pick is not None and (not isinstance(pick, dict) or pick.get('줄') not in [q['줄'] for q in quotes]):
            raise Stop(f'app/features/quote_rule.py use_quote: {sup} · {pid}에 받은 견적 줄 가운데 하나(dict) 또는 None을 돌려줘야 합니다(돌려준 값 {pick!r}).')
        for q in quotes:
            used[q['줄']] = '씀' if pick is not None and q['줄'] == pick['줄'] else '기준일에 안 씀'
        if pick is None:
            continue
        d, d_raw = defect(pick['불량률'])
        days, days_raw = lead(pick['납기(일)'])
        out.append({'supplier': sup, 'part': pid, 'price_manwon': float(pick['단가(만원)']), 'defect_rate': d, 'defect_rate_original': d_raw,
                    'lead_days': days, 'lead_days_original': days_raw, 'min_order_qty': int(pick['최소주문수량']),
                    'supplier_part_no': pick['공급사품번'], 'quote_date': pick['견적일'], 'valid_until': pick['유효기한'],
                    'quote_source': source(QUOTES, pick['줄']), 'as_of': AS_OF})
    if stage == '견적':
        return out, used, found
    approval_rule = load_rule('approval_rule.py')
    avl = {(r['공급사'], r['품번']): {**r, '줄': line} for line, r in table(AVL)}
    for pair in out:
        entry = avl.get((pair['supplier'], pair['part']))
        got = approval_rule.approval(dict(entry) if entry else None, AS_OF)
        if not isinstance(got, dict) or not isinstance(got.get('approved'), bool):
            raise Stop(f'app/features/approval_rule.py approval: {pair["supplier"]} · {pair["part"]}에 approved(True · False)가 든 dict를 돌려줘야 합니다(돌려준 값 {got!r}).')
        pair.update({k: v for k, v in got.items()})
        pair['approval_source'] = source(AVL, entry['줄']) if entry else None
        extra = approval_rule.buyer_info(dict(pair))
        if not isinstance(extra, dict):
            raise Stop(f'app/features/approval_rule.py buyer_info: {pair["supplier"]} · {pair["part"]}에 dict를 돌려줘야 합니다({{}}이면 남길 것 없음).')
        clash = [k for k in extra if k in pair]
        if clash:
            raise Stop(f'app/features/approval_rule.py buyer_info: 이미 있는 속성 {clash}를 덮어쓰지 않습니다 — 새 속성 이름을 씁니다.')
        pair.update(extra)
    return out, used, found


def kind(v):
    return 'boolean' if isinstance(v, bool) else 'integer' if isinstance(v, int) else 'number' if isinstance(v, float) else 'list' if isinstance(v, list) else 'string'


def write_model(rows):
    schema, graph = base_model()
    nodes = list(graph['nodes'])
    rels = list(graph['rels'])
    for sup in sorted({r['supplier'] for r in rows}):
        nodes.append({'labels': ['Supplier'], 'props': {'id': 'supplier:' + sup, 'name': sup}})
    props_spec = {}
    for r in rows:
        props = {k: v for k, v in r.items() if k not in ('supplier', 'part') and v not in (None, '')}
        for k, v in props.items():
            props_spec.setdefault(k, kind(v))
        rels.append({'type': 'SUPPLIES', 'a': 'supplier:' + r['supplier'], 'b': r['part'], 'props': props})
    schema = dict(schema)
    schema['classes'] = dict(schema['classes'], Supplier={'meaning': '견적을 낸 공급사(승인 목록의 이름)', 'required': {'id': 'string', 'name': 'string'}})
    schema['relations'] = dict(schema['relations'], SUPPLIES={'from': 'Supplier', 'to': 'Part', 'cardinality': 'N:M',
                                                               'note': '공급사 · 부품 쌍마다 기준일에 쓸 견적 하나', 'properties': props_spec})
    OUTPUT.mkdir(exist_ok=True)
    (OUTPUT / 'schema.json').write_text(json.dumps(schema, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    (OUTPUT / 'graph.json').write_text(json.dumps({'nodes': nodes, 'rels': rels}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    return schema, {'nodes': nodes, 'rels': rels}


# ───────────── 물어보기(모델만 읽는다) ─────────────
def answers(asks):
    """asks = [(질문, 물을 값)] → [{'질문','물을_값','항목','답'}]. 질문 1 = 품번 · 표기 → 그 부품을 쓰는 설비(항목 = 찾은 사내 품번),
    질문 2 = 품번 · 표기 → 공급사마다 「승인 · 단가 · 불량률 · 납기」(항목 = 사내 품번/공급사), 없는 품번은 답 「없음」."""
    graph = json.loads((OUTPUT / 'graph.json').read_text(encoding='utf-8'))
    label = {n['props']['id']: n['labels'][0] for n in graph['nodes']}
    props = {n['props']['id']: n['props'] for n in graph['nodes']}
    owner = {r['b']: r['a'] for r in graph['rels'] if label.get(r['a']) == 'Asset' and label.get(r['b']) == 'Component'}
    out = []
    for q, value in asks:
        q = str(q).strip()
        ids = sorted(i for i, p in props.items() if label[i] == 'Part' and (i == value or value in p.get('other_codes', [])))
        if q not in ('1', '2'):
            raise Stop(f'app/features/expected.csv: 질문 「{q}」 — 이 표에서 묻는 질문은 1 · 2입니다(질문 3은 1 · 2를 다른 표기 · 없는 품번으로 묻습니다).')
        if not ids:
            out.append({'질문': q, '물을_값': value, '항목': '', '답': '없음'})
            continue
        for pid in ids:
            if q == '1':
                assets = sorted({owner[r['a']] for r in graph['rels'] if r['b'] == pid and r['a'] in owner})
                out.append({'질문': q, '물을_값': value, '항목': pid, '답': ' · '.join(assets) or '쓰는 설비 없음'})
            else:
                rows = [r for r in graph['rels'] if r['type'] == 'SUPPLIES' and r['b'] == pid]
                if not rows:
                    out.append({'질문': q, '물을_값': value, '항목': pid, '답': '기준일에 쓸 공급 조건 없음'})
                for r in rows:
                    p = r['props']
                    out.append({'질문': q, '물을_값': value, '항목': f'{pid}/{props[r["a"]]["name"]}',
                                '답': f'{"승인" if p.get("approved") else "비승인"} · {p["price_manwon"]:g} · {p["defect_rate"]:g} · {p["lead_days"]}'})
    return out
