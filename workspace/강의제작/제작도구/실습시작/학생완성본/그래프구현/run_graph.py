"""완성 모델을 폴더 전용 랩 DB에 적재하고 질문별 결과와 변경 전후를 남긴다."""
import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path
from graph_model import load_model, rows

HERE=Path(__file__).resolve().parent
INPUT=HERE/'입력'
OUT=HERE/'결과'


def statement(query, **params):
    return {'statement':query,'parameters':params}


def identifier(name):
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',name):
        raise ValueError('지원하지 않는 이름: '+name)
    return name


def batches(graph, previous=None):
    previous=previous or {'nodes':[],'rels':[]}
    old_nodes={n['props']['id']:n for n in previous['nodes']}
    old_edges={(e['a'],e['type'],e['b']):e for e in previous['rels']}
    result=[]
    for n in graph['nodes']:
        key=n['props']['id'];labels=':'.join(identifier(x) for x in n['labels'])
        if n!=old_nodes.get(key):result.append(statement(f'MERGE (n:{labels} {{id:$key}}) SET n += $props',key=key,props=n['props']))
    for e in graph['rels']:
        key=e['a'],e['type'],e['b']
        if e!=old_edges.get(key):result.append(statement(f'MATCH (a {{id:$a}}),(b {{id:$b}}) MERGE (a)-[r:{identifier(e["type"])}]->(b) SET r += $props',a=e['a'],b=e['b'],props=e['props']))
    return result


def read_query(name):return (HERE/'queries'/(name+'.cypher')).read_text(encoding='utf-8-sig').strip()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare',action='store_true',help='원자료와 변경 대상을 확인하고 DB 실행 전 준비 결과를 저장')
    parser.add_argument('--part',default='P-PMP-SEAL')
    parser.add_argument('--asset',default='',help='설비 질의를 설비 하나로 좁힐 때(통합반). 비우면 전체 설비')
    a=parser.parse_args()
    change=(INPUT/'자료_변경분').is_dir()          # 수정본 반영은 통합반 실습4만
    supply=(HERE/'queries/supply_terms.cypher').is_file()   # 공급 조건 조회는 실전반 실습4만
    base=load_model(INPUT);revised=load_model(INPUT,True) if change else None;delta=batches(revised,base) if change else []
    ids=[n['props']['id'] for n in base['nodes']]; assert len(set(ids))==len(ids)
    if any(e[k] not in ids for e in base['rels'] for k in ('a','b')):raise ValueError('입력 관계의 끝점이 없습니다.')
    OUT.mkdir(exist_ok=True)
    def save(name,obj):(OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    prep={'input_nodes':len(base['nodes']),'input_edges':len(base['rels'])}
    if change:prep.update(patch_statements=len(delta),patch_targets=[d['parameters'].get('key') or [d['parameters'].get('a'),d['parameters'].get('b')] for d in delta])
    if a.prepare:save('input_check.json',prep);print(json.dumps(prep,ensure_ascii=False));return
    from lab_db import prepare
    state=prepare();url=state['http']+'/db/neo4j/tx/commit'
    def run(items):
        request=urllib.request.Request(url,data=json.dumps({'statements':items}).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(request,timeout=90) as response:answer=json.load(response)
        if answer['errors']:raise RuntimeError(answer['errors'])
        return [[dict(zip(q['columns'],v['row'])) for v in q['data']] for q in answer['results']]
    def snapshot():return run([statement('MATCH (n) RETURN count(n) AS nodes'),statement('MATCH ()-[r]->() RETURN count(r) AS relationships'),statement('MATCH (a:Asset) RETURN a.id AS id,a.name AS name,a.status AS status ORDER BY id')])
    def question(name,**params):return run([statement(read_query(name),**params)])[0]
    def same_as(observed,model):
        assert observed[0][0]['nodes']==len(model['nodes']) and observed[1][0]['relationships']==len(model['rels']),'다른 자료가 있는 DB입니다. 이 완성본을 새 폴더에 풀어 전용 DB에서 시작하세요.'
        expected=sorted((n['props']['id'],n['props']['name'],n['props']['status']) for n in model['nodes'] if 'Asset' in n['labels'])
        assert [(x['id'],x['name'],x['status']) for x in observed[2]]==expected,'설비 이름·상태 대조 실패'
    for label in sorted({identifier(t) for n in base['nodes'] for t in n['labels']}):run([statement(f'CREATE CONSTRAINT lab_{label} IF NOT EXISTS FOR (n:{label}) REQUIRE n.id IS UNIQUE')])
    run(batches(base));before=snapshot();run(batches(base));assert before==snapshot(),'기준 재적재 결과가 달라졌습니다.'
    same_as(before,base)
    probes=list(dict.fromkeys([a.part,'P-PMP-SEAL','PS-4510','P-PMP-SEAL-HT','미등록-품번']))
    if supply:
        variants={p:question('part_usage',part=p) for p in probes}
        assert variants['P-PMP-SEAL']==variants['PS-4510'] and not variants['미등록-품번']
        actual={'baseline':before,'part_usage':variants,'repeat_load':'기준 2회 동일'}
        actual['supply_terms']=question('supply_terms',part=a.part)   # 값의 출처는 모델의 속성 — 조회만으로 돌려받는다
    else:
        actual={'baseline':before,'baseline_part_assets':question('part_assets',part=a.part)}
        if change:
            run(delta);after=snapshot();run(delta);assert after==snapshot(),'수정본 재적재 결과가 달라졌습니다.'
            same_as(after,revised)
            change_dir, = (INPUT/'자료_변경분').glob('*수정본')
            sensor_checks = []
            for line, row in enumerate(rows(change_dir/'센서_변경.csv'),2):
                key = row['설비코드'] + ':' + row['태그']
                observed, = run([statement('MATCH (s:Sensor {id:$id}) RETURN s.id AS id,s.unit AS unit,s.normal AS normal',id=key)])[0]
                if row['변경'] != '삭제':
                    assert observed['unit'] == row['단위'] and observed['normal'] == float(row['정상값'])
                sensor_checks.append({'line':line, 'change':row['변경'], 'observed':observed})
            actual.update(sensor_change_check=sensor_checks,revised=after,repeat_load='기준/수정 각 2회 동일')
        variants={p:question('part_assets',part=p) for p in probes}
        assert variants['P-PMP-SEAL']==variants['PS-4510'] and not variants['미등록-품번']
        actual['revised_part_assets' if change else 'part_assets']=variants
        actual['asset_counts']=question('asset_counts')
        actual['sensors']=question('asset_sensors',asset=a.asset);actual['asset_parts']=question('asset_parts',asset=a.asset)
    save('run_result.json',actual);print('결과/run_result.json에서 '+('기준·수정과 ' if change else '')+'다른 품번의 결과를 비교하세요.')

if __name__=='__main__':main()
