"""실제 파일 도구로 두 전달 갈래와 구조 손상 검사를 실행한다. 모델 수행 시험은 아니다."""
from pathlib import Path
from datetime import datetime,timedelta
import argparse
import copy
import importlib.util
import json
import sys
import time

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]))
from build_agent_labs import LAB, policy_text


def dump(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')


def load_policy(path,branch):
    path.write_text(policy_text(branch),encoding='utf-8',newline='\n')
    spec=importlib.util.spec_from_file_location('reference_'+branch,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def ledger_for(store,request,policy):
    end=datetime.fromisoformat(request['as_of']); earlier=lambda seconds:(end-timedelta(seconds=seconds)).isoformat()
    calls=[('graph_query',{'labels':['Cause'],'depth':1,'relations':['ADDRESSES']}),
           ('graph_query',{'labels':['Knowledge'],'terms':['HM-8.4'],'depth':1,'relations':['STATED_IN'],'limit':30}),
           ('document',{'doc_id':'HM-8','revision':'1.1','section':'HM-8.3'}),
           ('document',{'doc_id':'HM-8','revision':'1.1','line_start':38,'line_end':40}),
           ('document',{'doc_id':'HM-8','revision':'1.1','section':'HM-8.7'}),
           ('observations',{'asset':request['asset'],'start':earlier(30),'end':request['as_of'],'tags':['CE']}),
           ('observations',{'asset':request['asset'],'start':earlier(120),'end':request['as_of'],'tags':['VS1','TS4']}),
           ('observations',{'asset':request['asset'],'start':earlier(60),'end':request['as_of'],'tags':['TS1']}),
           ('observations',{'asset':request['asset'],'start':earlier(2*86400),'end':earlier(86400),'tags':['CE','TS1'],'dataset':'10s','state':'RUN','load_pct':90}),
           ('history',{'asset':request['asset'],'start':earlier(30*86400),'end':request['as_of'],'kind':'maintenance'}),
           ('history',{'asset':request['asset'],'start':earlier(30*86400),'end':request['as_of'],'kind':'states'})]
    ledger=[]
    for name,arguments in calls:
        args=policy.prepare_query(name,arguments,request)
        ledger.append({'id':f'T{len(ledger)+1:03d}','tool':name,'model_arguments':None,'requested_arguments':arguments,'arguments':args,
                       'status':'ok','result':store.call(name,args),'method':'강사 참조의 직접 도구 실행 — 모델 호출 아님'})
    return ledger


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--lab',type=Path,default=LAB);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    sys.path.insert(0,str(args.lab))
    project=(args.lab/'data/source_manifest.json').is_file()
    if project:
        from app.utils.evidence import EvidenceStore, graph_errors, read_csv, sha
        from app.utils.contracts import structural_errors
    else:
        from tools.evidence import EvidenceStore, graph_errors, read_csv, sha
        from tools.runner import structural_errors
    store=EvidenceStore(args.lab);began=time.perf_counter();store.index();index_seconds=time.perf_counter()-began
    policies={branch:load_policy(args.out/(branch+'_policy.py'),branch) for branch in ['partial','bundle']}
    requests=read_csv(args.lab/('data' if project else '자료')/'requests.csv')
    base=store.request(store.manifest['default_request'])
    gap=next(r for r in requests if r['request_id'].startswith('OBS-'))
    other=next(r for r in requests if r['asset']!=base['asset'] and not r['request_id'].startswith('OBS-'))
    plans=[];query_seconds=[]
    # 자료 보완 뒤 실제 분포에서 고른 전이 입력: 외기 상승과 팬 진동 증가의 서로 다른 기간.
    transition = [store.request(identity) for identity in ['ALT-hyd03-0289-060b','ALT-hyd03-0294-4bf7','ALT-hyd03-0305-aa1f']]
    for request in [base,gap,other,*transition]:
        began=time.perf_counter();ledger=ledger_for(store,request,policies['partial']);query_seconds.append(time.perf_counter()-began)
        for branch,policy in policies.items():
            plan=policy.build_plan(request,ledger,{'summary':'강사 참조의 직접 도구 대조. 모델 종료 응답 아님.'})
            errors=structural_errors(plan,ledger)
            if errors:raise ValueError(errors)
            dump(args.out/branch/(request['request_id']+'.json'),{'request':request,'ledger':ledger,'plan':plan})
            plans.append({'request_id':request['request_id'],'branch':branch,'candidate_states':[x['status'] for x in plan['candidates']],
                          'checks':len(plan['next_checks']),'unresolved':len(plan['unresolved']),'plan_sha256':sha(args.out/branch/(request['request_id']+'.json'))})
    corruptions=[]
    for kind in ['duplicate_id','missing_endpoint','reversed_direction']:
        graph=copy.deepcopy(store.graph)
        if kind=='duplicate_id':graph['nodes'].append(copy.deepcopy(graph['nodes'][0]))
        elif kind=='missing_endpoint':graph['rels'][0]['b']='does-not-exist'
        else:
            rel=next(r for r in graph['rels'] if r['type']==store.shape['이름']['지식의_출처']);rel['a'],rel['b']=rel['b'],rel['a']
        errors=graph_errors(graph,store.schema,store.shape)
        if not errors:raise ValueError('손상 미검출: '+kind)
        corruptions.append({'kind':kind,'errors':errors})
    # 자기 결과: 의미 이름 변경과 판 노드를 분리하지 않는 두 지원 모양을 실제 읽는다.
    own_results=[]
    for kind in ['renamed','no_revision_node']:
        folder=args.out/'own_graph'/kind;folder.mkdir(parents=True,exist_ok=True)
        graph,schema,shape=copy.deepcopy(store.graph),copy.deepcopy(store.schema),copy.deepcopy(store.shape)
        if kind=='renamed':
            old=shape['이름']['지식'];new='AcceptedStatement';shape['이름']['지식']=new
            schema['classes'][new]=schema['classes'].pop(old)
            for rule in schema['relations'].values():
                for end in ['from','to']:
                    if rule.get(end)==old:rule[end]=new
            for node in graph['nodes']:node['labels']=[new if x==old else x for x in node['labels']]
        else:
            revision_label=shape['이름']['판'];document_label=shape['이름']['문서']
            revision_docs={n['props']['id']:n['props']['doc_id'] for n in graph['nodes'] if revision_label in n['labels']}
            graph['nodes']=[n for n in graph['nodes'] if revision_label not in n['labels']]
            graph['rels']=[r for r in graph['rels'] if r['type'] not in [shape['이름']['문서의_판'],shape['이름']['판의_대체']]]
            for rel in graph['rels']:
                if rel['type']==shape['이름']['판의_절']:rel['a']=revision_docs.get(rel['a'],rel['a'])
            schema['relations'][shape['이름']['판의_절']]['from']=document_label
            shape['판을_따로_둠']=False
        for name,value in [('graph.json',graph),('schema.json',schema),('shape.json',shape)]:dump(folder/name,value)
        selected=EvidenceStore(args.lab,folder);returned=selected.graph_query(labels=[shape['이름']['지식']],limit=1)
        if returned['source_sha256']!=sha(folder/'graph.json'):raise ValueError('자기 결과 해시가 기본 입력 해시로 반환됨')
        own_results.append({'kind':kind,'nodes':len(graph['nodes']),'relations':len(graph['rels']),'source_sha256':returned['source_sha256'],'returned_knowledge':returned['total']})
    results={'method':'무모델 강사 참조·구조 검증','index_seconds':round(index_seconds,3),'query_bundles_seconds':[round(x,4) for x in query_seconds],
             'index_bytes':(args.lab/('output' if project else '결과')/'observation_index.sqlite').stat().st_size,'plans':plans,'corruptions':corruptions,'own_inputs':own_results,
             'source_files':{str(p.relative_to(args.lab)):sha(p) for p in ([args.lab/'app/utils/evidence.py',args.lab/'app/utils/contracts.py',args.lab/'data/data_manifest.json'] if project else [args.lab/'tools/evidence.py',args.lab/'tools/runner.py',args.lab/'자료/data_manifest.json'])}}
    dump(args.out/'report.json',results);print(json.dumps(results,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
