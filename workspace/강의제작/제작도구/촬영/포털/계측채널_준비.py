"""2회차 비교용 포털의 전용 DB에 현장 원자료의 동명 센서 두 행을 준비한다."""
import argparse
import csv
import json
from pathlib import Path
import subprocess

LAB = Path(__file__).resolve().parents[3] / '산출물/통합반/실습/02회차/랩'
NAMESPACE = 'day02-sensors'


def channels():
    source = LAB / 'ontology-lab/data/sensors.csv'
    model = LAB / 'graph-lab/data/model/graph.json'
    sensors = {n['props']['id']: n['props'] for n in json.loads(model.read_text('utf8'))['nodes']
               if n['labels'] == ['Sensor']}
    rows = []
    with source.open(encoding='utf-8-sig', newline='') as stream:
        for line, row in enumerate(csv.DictReader(stream), 2):
            asset = row['설비코드']
            if asset not in ('HYD-01', 'HYD-02') or row['태그'] != 'TS1' or row['센서명'] != '유온 센서':
                continue
            node_id = asset + ':' + row['태그']
            sensor = sensors[node_id]
            if (sensor['instrument_tag'], sensor['unit']) != (row['계장태그'], row['단위']):
                raise ValueError(f'{source.name} {line}행과 제공 모델이 다릅니다.')
            rows.append(dict(id=node_id, name=row['센서명'], ns=NAMESPACE, tag=row['태그'],
                             instrument_tag=row['계장태그'], unit=row['단위'], asset_code=asset,
                             source=f'{source.name} {line}행'))
    if len(rows) != 2 or len({row['instrument_tag'] for row in rows}) != 2:
        raise ValueError('동명 센서의 설비·계장태그를 원자료에서 확인하세요.')
    return rows


def prepare(container, rows):
    label = subprocess.check_output(['docker', 'inspect', '--format',
                                     '{{index .Config.Labels "hyd.lesson"}}', container], text=True).strip()
    if label != 'day02-map':
        raise ValueError('hyd.lesson=day02-map 라벨을 가진 별도 수업 DB를 지정하세요.')
    # 본 수업용 컨테이너 자체의 loopback만 사용한다. 기존의 다른 노드와 ID가 겹치면 트랜잭션을 중단한다.
    encoded = '[' + ','.join('{' + ','.join(k + ':' + json.dumps(v, ensure_ascii=False)
                                             for k, v in r.items()) + '}' for r in rows) + ']'
    cypher = (
        f'WITH {encoded} AS rows UNWIND rows AS row OPTIONAL MATCH (old {{id:row.id}}) '
        'WITH collect({props:row, conflict:old IS NOT NULL AND '
        '(NOT old:Sensor OR properties(old) <> row)}) AS items '
        'WHERE none(item IN items WHERE item.conflict) UNWIND items AS item WITH item.props AS props '
        'MERGE (s:Sensor {id:props.id, ns:props.ns}) ON CREATE SET s=props '
        'RETURN count(s) AS prepared;'
    )
    result = subprocess.run(['docker', 'exec', '-i', container, 'cypher-shell', '-a', 'bolt://localhost:7687',
                             '--format', 'plain'], input=cypher, capture_output=True, text=True,
                            encoding='utf8', check=True)
    if result.stdout.strip().splitlines()[-1:] != ['2']:
        raise ValueError('대상 ID가 기존 데이터와 다릅니다. 변경하지 않았습니다.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply-to', metavar='CONTAINER', help='라벨이 있는 격리 DB에 적용')
    args = parser.parse_args()
    data = channels()
    if args.apply_to:
        prepare(args.apply_to, data)
    print(json.dumps(data, ensure_ascii=False, indent=2))
