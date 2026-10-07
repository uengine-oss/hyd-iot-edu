"""Actual Codex business question -> portal answer -> same session -> MCP query.

Start creates two executions of one published definition, then waits for their
questions. Answer through the portal, then verify using the emitted report path.
The probe never answers on the user's behalf or marks a failed task complete.
"""
import argparse
import json
from pathlib import Path
import shutil
import time
import uuid

from probe_definition_registry import ROOT, http


def definition(did):
    fields=[{'key':'selected_asset','type':'text','text':'담당자가 선택한 실제 설비 코드'},
            {'key':'asset_name','type':'text','text':'업무 DB에서 조회한 설비 이름'},
            {'key':'sql','type':'text','text':'실제 실행한 SELECT SQL'}]
    return {'processDefinitionId':did,'processDefinitionName':'담당자 대상 확인 후 업무 조회','version':'1',
      'roles':[{'name':'조회 담당','endpoint':'sys:agent'}],
      'data':[{'name':f['key'],'type':'Text'} for f in fields],
      'forms':{'confirmed_asset':{'fields_json':fields}},
      'activities':[{'id':'confirm-and-query','type':'userTask','name':'담당자에게 대상 확인 후 조회',
         'role':'조회 담당','agentMode':'COMPLETE','orchestration':'cliagents','tool':'formHandler:confirmed_asset',
         'agentConfig':{'cli':'codex','model':'gpt-5.6-sol','permission':'read_only','reasoning_effort':'low'},
         'instruction':'조회할 대상 설비는 아직 제공되지 않았습니다. 담당자에게 HYD-02 또는 HYD-03 중 어느 설비인지 업무 질문을 보내고 답변을 기다리세요. 임의 선택이나 기본값은 금지합니다. 질문의 선택지는 HYD-02, HYD-03입니다. 답변이 오면 enterprise MCP describe_schema로 스키마를 확인하고 선택한 코드의 설비 이름을 SELECT로 직접 조회하세요. selected_asset/asset_name/sql에 확인된 값과 실제 SQL을 제출하세요. 조치 실행이나 다른 질문은 필요 없습니다.',
         'outputData':[f['key'] for f in fields]}],
      'events':[{'id':'start','type':'startEvent'},{'id':'pump','type':'endEvent'},{'id':'fan','type':'endEvent'},{'id':'unexpected','type':'endEvent'}],
      'gateways':[{'id':'choice','type':'exclusiveGateway'}],
      'sequences':[{'id':'s1','source':'start','target':'confirm-and-query'},
        {'id':'s2','source':'confirm-and-query','target':'choice'},
        {'id':'s3','source':'choice','target':'pump','condition':"selected_asset == 'HYD-02'"},
        {'id':'s4','source':'choice','target':'fan','condition':"selected_asset == 'HYD-03'"},
        {'id':'s5','source':'choice','target':'unexpected','properties':{'default':True}}]}


def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')


def wait(pid,predicate,seconds=360):
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        code,view=http('/api/instances/'+pid);assert code==200,(code,view)
        wi=view['workitems'][0]
        if wi.get('draft_status')=='FAILED':raise RuntimeError(json.dumps(wi,ensure_ascii=False))
        if predicate(view):return view
        time.sleep(2)
    raise TimeoutError(pid)


def start():
    did='codex-human-'+uuid.uuid4().hex[:8];out=ROOT/'.evidence/reaudit'/did;out.mkdir()
    report={'definition':did,'cases':[],'passed':False};path=out/'report.json';save(path,report)
    raw=definition(did);save(out/'definition.json',raw)
    code,body=http('/api/process/definitions',{'definition':raw});assert code==201,(code,body)
    for label,expected,end in [('A','HYD-02','pump'),('B','HYD-03','fan')]:
        code,inst=http('/api/instances/start',{'definition_id':did,'version':'1','event_id':did+'-'+label,'name':'사람 질문 실습 '+label})
        assert code==200,(code,inst)
        case={'label':label,'instance':inst['proc_inst_id'],'expected_answer':expected,'expected_end':end}
        report['cases'].append(case);save(path,report)
    print('REPORT',path,flush=True)
    for case in report['cases']:
        view=wait(case['instance'],lambda v:v['workitems'][0].get('draft_status')=='HUMAN_ASKED')
        wi=view['workitems'][0];asked=[e for e in view['events'] if e['event_type']=='human_asked']
        assert len(asked)==1 and not wi.get('output') and view['instance']['status']=='RUNNING'
        case.update(workitem=wi['id'],job_id=asked[0]['job_id'],session=wi['draft']['cliagents_session_id'],question=asked[0]['data'])
        save(out/f"asked-{case['label']}.json",view);save(path,report)
        print('ASKED',case['label'],case['workitem'],case['session'],flush=True)
    print('Answer A=HYD-02 / B=HYD-03 through the portal, then --verify this report.',flush=True)


def verify(path):
    report=json.loads(path.read_text(encoding='utf-8'));out=path.parent
    for case in report['cases']:
        view=wait(case['instance'],lambda v:v['instance']['status']=='COMPLETED')
        save(out/f"final-{case['label']}.json",view)
        wi=view['workitems'][0];output=wi.get('output') or {};events=view['events']
        assert output.get('cliagents_session_id')==case['session'],'different session'
        assert output.get('selected_asset')==case['expected_answer'] and output.get('asset_name')
        assert view['instance']['end_event']==case['expected_end'] and wi['status']=='DONE'
        assert sum(e['event_type']=='human_asked' for e in events)==1
        assert sum(e['event_type']=='human_response' for e in events)==1
        calls=[e for e in events if e['event_type']=='tool_usage_finished']
        assert {'enterprise/describe_schema','enterprise/query'}<={e['data'].get('tool') for e in calls}
        assert not any(e['data'].get('is_error') for e in calls)
        query=[e['data']['output']['structured_content']['document'] for e in calls if e['data'].get('tool')=='enterprise/query']
        assert any(output['asset_name'] in json.dumps(q,ensure_ascii=False) for q in query)
        for trace in (ROOT/'.evidence/workspace/hyd'/wi['id']).glob('*.events.jsonl'):
            shutil.copy2(trace,out/f"{case['label']}-{trace.name}")
        case.update(status=wi['status'],end=view['instance']['end_event'],output=output,queries=query)
        save(path,report);print('PASS',case['label'],case['session'],case['expected_end'],flush=True)
    report['passed']=True;save(path,report)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--verify',type=Path);args=parser.parse_args()
    if args.verify:verify(args.verify)
    else:start()
