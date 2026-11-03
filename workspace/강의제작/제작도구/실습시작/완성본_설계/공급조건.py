"""앞 단계의 그래프에 기준일 현재의 견적과 승인 근거를 추가한다."""
import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATE = '2026-10-15'


def records(name):
    with (ROOT / '자료' / name).open(encoding='utf-8-sig', newline='') as stream:
        return [(line, row) for line, row in enumerate(csv.DictReader(stream), 2)]


def extend_model():
    graph = json.loads((ROOT / '입력/graph.json').read_text(encoding='utf-8'))
    parts = {node['props']['id']: node['props'] for node in graph['nodes'] if 'Part' in node['labels']}
    approval = {(row['공급사'], row['품번']): (ln, row) for ln, row in records('승인공급사_목록.csv')}
    latest = {}
    ignored = []
    for line, quote in records('공급_조건.csv'):
        item = quote['품번']
        if item not in parts:
            candidates = [code for code, props in parts.items() if item == props['name'] or item in props.get('other_codes', [])]
            if len(candidates) != 1:
                raise ValueError(f'공급_조건.csv {line}행의 품번을 확인하세요: {item}')
            item = candidates[0]
        supplier = quote['공급사'].partition('(')[0].strip()
        pair = supplier, item
        if not quote['견적일'] <= DATE <= quote['유효기한']:
            ignored.append(f'공급_조건.csv {line}행: {item}, {supplier}, 기준일 밖 견적')
            continue
        if pair in latest:
            old_ln, old = latest[pair]
            if old['견적일'] == quote['견적일']:
                raise ValueError(f'같은 날의 유효 견적 두 건: {old_ln}, {line}행')
            if old['견적일'] > quote['견적일']:
                ignored.append(f'공급_조건.csv {line}행: 더 최근 유효 견적으로 대체')
                continue
            ignored.append(f'공급_조건.csv {old_ln}행: 더 최근 유효 견적으로 대체')
        latest[pair] = line, quote

    for supplier in sorted({s for s, _ in latest}):
        graph['nodes'].append({'labels':['Supplier'], 'props':{'id':'supplier:'+supplier, 'name':supplier}})
    for (supplier, item), (line, quote) in sorted(latest.items()):
        a_line, registration = approval.get((supplier, item), (None, {}))
        status = registration.get('승인상태', '미등록')
        if registration.get('승인일', '') > DATE or (registration.get('유효기한') and registration['유효기한'] < DATE):
            status = '유효기간 밖'
        rate = quote['불량률']
        lead = quote['납기(일)']
        props = {
            'approved': status in ('승인', '조건부 승인'), 'approval_status':status,
            'price_manwon':float(quote['단가(만원)']), 'defect_rate':float(rate.rstrip('%')) / (100 if rate.endswith('%') else 1),
            'lead_days':int(lead[:-1])*7 if lead.endswith('주') else int(lead),
            'quote_date':quote['견적일'], 'valid_until':quote['유효기한'], 'supplier_part_no':quote['공급사품번'],
            'min_order_qty':int(quote['최소주문수량']), 'quote_source':f'공급_조건.csv {line}행',
            'approval_source':f'승인공급사_목록.csv {a_line}행' if a_line else '등록 행 없음', 'as_of':DATE,
        }
        if registration.get('조건'):
            props['condition'] = registration['조건']
        graph['rels'].append({'type':'SUPPLIES','a':'supplier:'+supplier,'b':item,'props':props})
    return graph, ignored

