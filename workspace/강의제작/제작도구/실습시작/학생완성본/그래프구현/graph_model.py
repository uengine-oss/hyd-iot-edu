"""실습 폴더의 입력 모델과(통합반이면) 수정본을 읽어 갱신할 대상을 만든다."""
import csv
import json
from pathlib import Path


def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def validate_schema(graph, schema):
    classes = schema['classes']
    by_id = {}
    for node in graph['nodes']:
        props = node['props']
        if props['id'] in by_id:
            raise ValueError('중복 ID: '+props['id'])
        for label in node['labels']:
            missing = set(classes[label]['required']) - props.keys()
            if missing:
                raise ValueError(f"{props['id']} 필수 속성 누락: {sorted(missing)}")
        by_id[props['id']] = set(node['labels'])
    for edge in graph['rels']:
        rule = schema['relations'][edge['type']]
        starts = rule['from'] if isinstance(rule['from'], list) else [rule['from']]
        ends = rule['to'] if isinstance(rule['to'], list) else [rule['to']]
        if not by_id.get(edge['a'], set()).intersection(starts) or not by_id.get(edge['b'], set()).intersection(ends):
            raise ValueError('스키마와 다른 관계 끝점: '+str((edge['a'],edge['type'],edge['b'])))


def load_model(source, revised=False):
    graph = json.loads((source / 'graph.json').read_text(encoding='utf-8-sig'))
    schema = json.loads((source / 'schema.json').read_text(encoding='utf-8-sig'))
    validate_schema(graph, schema)
    nodes = {n['props']['id']: n for n in graph['nodes']}
    edges = {(e['a'], e['type'], e['b']): e for e in graph['rels']}
    if len(nodes) != len(graph['nodes']) or len(edges) != len(graph['rels']):
        raise ValueError('입력에서 같은 ID 또는 중복 관계를 확인하세요.')
    if not revised:
        return graph
    changes, = (source / '자료_변경분').glob('*수정본')
    for row in rows(changes / '설비_대장_변경.csv'):
        nodes[row['설비코드']]['props'].update(name=row['설비명'], status=row['상태'])
    for row in rows(changes / '센서_변경.csv'):
        key = row['설비코드'] + ':' + row['태그']
        if row['변경'] == '삭제' and '중복 행' in row['비고']:
            # 원자료의 중복 행을 정리해도 유일한 센서 노드는 남는다.
            continue
        nodes[key]['props'].update(unit=row['단위'], normal=float(row['정상값']))
    for row in rows(changes / '구성요소_변경.csv'):
        matches = [n['props']['id'] for n in nodes.values() if n['props']['id'].startswith(row['설비코드'] + ':') and n['props'].get('serial') == row['일련번호']]
        component, = matches
        part = row['교체부품']
        if part not in nodes:
            raise ValueError('알 수 없는 품번: ' + part)
        edges[component,'USES_PART',part] = dict(a=component,b=part,type='USES_PART',props={'source_text':part})
    return {'nodes':list(nodes.values()),'rels':list(edges.values())}
