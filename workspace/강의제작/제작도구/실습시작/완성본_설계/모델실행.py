"""완성한 모델을 다시 만들고 부품·설비·센서 질문의 답을 확인한다."""
import argparse
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def write(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def by_part(nodes, relations, code):
    parts = [p for label, p in nodes.values() if label == 'Part']
    matches = [p for p in parts if p['id'] == code]
    if not matches:
        matches = [p for p in parts if code in p.get('other_codes', []) or p['name'] == code]
    belongs = {r['b']:r['a'] for r in relations if r['type']=='HAS_COMPONENT'}
    result = []
    for p in matches:
        usage = sorted((belongs[r['a']], r['a']) for r in relations if r['type']=='USES_PART' and r['b']==p['id'])
        row = {'품번':p['id'], '품명':p['name'], '사용 설비':sorted({a for a,_ in usage}), '사용 구성 요소':[c for _,c in usage]}
        if any(label=='Supplier' for label,_ in nodes.values()):
            row['공급 조건'] = [
                {'공급사':nodes[r['a']][1]['name'], **r['props']}
                for r in relations if r['type']=='SUPPLIES' and r['b']==p['id']]
        result.append(row)
    return result


def sensor_questions(nodes, relations):
    parents = {r['b']:r['a'] for r in relations if r['type']=='HAS_COMPONENT'}
    observed = {r['a']:r['b'] for r in relations if r['type']=='OBSERVES'}
    assets = {p['id']:{} for label,p in nodes.values() if label=='Asset'}
    quantities = defaultdict(list)
    for r in relations:
        if r['type'] != 'MONITORED_BY':
            continue
        place, sensor = r['a'], r['b']
        asset = parents.get(place, place)
        p = nodes[sensor][1]
        q = nodes[observed[sensor]][1]
        item = {'센서':sensor, '태그':p['tag'], '종류':p['kind'], '물리량':q['name'], '단위':p['unit'],
                '정상값':p.get('normal'), '한계':p.get('limit'), '한계 방향':p.get('limit_direction')}
        assets[asset].setdefault(place, []).append(item)
        quantities[q['name']].append({'설비':asset, '센서':sensor, '태그':p['tag'], '단위':p['unit']})
    return assets, dict(quantities)


def main():
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument('품번', nargs='?', default='P-PMP-SEAL', help='사내 품번·다른 표기·품명')
    code = args.parse_args().품번
    config = json.loads((HERE/'설계_기준.json').read_text(encoding='utf-8'))
    if (HERE/'공급조건.py').exists():
        from 공급조건 import extend_model
        graph, audit = extend_model()
        schema = json.loads((ROOT/'입력/schema.json').read_text(encoding='utf-8'))
        schema['classes'].update(config['classes'])
        schema['relations'].update(config['relations'])
        schema['constraints'].extend(config['constraints'])
    else:
        from 설비모델 import base_graph
        items, rels = base_graph()
        graph = {'nodes':items, 'rels':rels}
        schema = config
        audit = []
    write('schema.json', schema)
    write('graph.json', graph)
    subprocess.run([sys.executable, '-X','utf8',str(ROOT/'check.py'),str(HERE)],check=True,cwd=ROOT)
    nodes = {n['props']['id']:(n['labels'][0],n['props']) for n in graph['nodes']}
    parts = [p['id'] for kind,p in nodes.values() if kind=='Part']
    sensors, quantities = sensor_questions(nodes, graph['rels'])
    answer = {'설비별 센서':sensors, '물리량별 센서':quantities,
              '부품별 사용처':{part:by_part(nodes,graph['rels'],part)[0] for part in parts}}
    write('질문별_결과.json',answer)
    if (HERE/'공급조건.py').exists():
        write('견적_제외근거.json', audit)
    found = by_part(nodes,graph['rels'],code)
    print(f'조회한 표기: {code} · 일치하는 품번 {len(found)}개')
    print(json.dumps(found,ensure_ascii=False,indent=2))
    print(f'전체 질문 결과: 결과/질문별_결과.json · {len(sensors)}개 설비 · {len(parts)}개 부품')


if __name__ == '__main__':
    main()

