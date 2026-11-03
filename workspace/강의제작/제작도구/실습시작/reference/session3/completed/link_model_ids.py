"""sop.json의 절차(sops)마다 설비 모델(입력/graph.json)에서 걸 설비 · 구성 요소 · 센서 ID를 찾아 모델 참조(model_refs)를 채운다.
어느 설비에 걸지와 절차마다 필요한 장치 · 센서는 결과/설비_연결_기준.json(정한 것)에 있다. 모델에 없는 ID는 만들지 않고 not_linked에 까닭을 남긴다.
사용: python 결과/link_model_ids.py        (결과/sop.json을 고쳐 쓰고, 설비마다 건 절차 수를 찍는다)
"""
from pathlib import Path
import json

root = Path(__file__).resolve().parents[1]
rule = json.loads((root/'결과/설비_연결_기준.json').read_text(encoding='utf-8'))
mine = root/'결과/내_입력/graph.json'
graph = json.loads((mine if mine.is_file() else root/'입력/graph.json').read_text(encoding='utf-8-sig'))
kind = {n['props']['id']: n['labels'][0] for n in graph['nodes']}

sop_path = root/'결과/sop.json'
doc = json.loads(sop_path.read_text(encoding='utf-8'))
count = {}
for s in doc['sops']:
    need = rule['sops'][s['id']]
    assets = [a for a in need['assets'] if kind.get(a) == 'Asset']
    refs = {'assets': assets,
            'components': [f'{a}:{c}' for c in need['components'] for a in assets if kind.get(f'{a}:{c}') == 'Component'],
            'sensors': [f'{a}:{x}' for x in need['sensors'] for a in assets if kind.get(f'{a}:{x}') == 'Sensor']}
    missing = [f'{a}:{x}' for x in need['components'] + need['sensors'] for a in assets if f'{a}:{x}' not in kind]
    refs['not_linked'] = need['not_linked'] + ('. 모델에서 찾지 못한 ID: ' + ', '.join(missing) if missing else '')
    s['model_refs'] = refs
    for a in assets:
        count[a] = count.get(a, 0) + 1
sop_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('설비마다 건 절차 수: ' + ', '.join(f'{a} {n}' for a, n in sorted(count.items())))
print('걸지 않은 설비와 까닭은 각 절차의 model_refs.not_linked에 있습니다.')
