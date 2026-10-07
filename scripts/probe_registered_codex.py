"""Real registered definitions -> worker.main -> Codex -> enterprise SQL -> engine.

Requires the host worker and enterprise MCP. No PLC/enterprise writes. Failed
instances stay available for diagnosis; this probe never marks failures complete.
"""
import json
from pathlib import Path
import shutil
import time
import uuid

import psycopg
from probe_definition_registry import http, DSN, ROOT


def verify_tools(view, count, out, version):
    events=view['events']
    starts=[e['data'] for e in events if e['event_type']=='tool_usage_started']
    ends=[e['data'] for e in events if e['event_type']=='tool_usage_finished']
    assert {'enterprise/describe_schema','enterprise/query'} <= {e.get('tool') for e in starts}
    assert not any(e.get('is_error') for e in ends)
    queries=[e for e in ends if e.get('tool')=='enterprise/query']
    actual=[e['output']['structured_content']['document'] for e in queries]
    assert any(x['rows']==[[count]] for x in actual),actual
    wid=view['workitems'][0]['id']
    traces=list((ROOT/'.evidence/workspace/hyd'/wid).glob('*.events.jsonl'))
    assert traces,'worker raw CLI trace missing'
    for p in traces:shutil.copy2(p,out/f'v{version}-{p.name}')
    return {'started_tools':[e['tool'] for e in starts],'errors':0,'executed_queries':actual,
            'raw_cli_traces':[f'v{version}-{p.name}' for p in traces]}


def definition(did, version):
    fields=[{'key':'count','type':'integer','text':'실제 SQL 결과의 설비 수'},
            {'key':'sql','type':'text','text':'실제로 실행한 SELECT SQL'}]
    if version=='2':fields.append({'key':'note','type':'text','text':'대상 범위 변경 설명'})
    target='코드가 HYD-로 시작하는 모든 설비' if version=='1' else '코드가 HYD-01인 설비만'
    return {'processDefinitionId':did,'processDefinitionName':'DB 실측 설비 수 검토','version':version,
      'roles':[{'name':'조회 담당','endpoint':'sys:agent'}],
      'data':[{'name':'count','type':'Number'},{'name':'sql','type':'Text'},{'name':'note','type':'Text'}],
      'forms':{'measurement':{'fields_json':fields}},
      'activities':[{'id':'measure','type':'userTask','name':'업무 DB 조회','role':'조회 담당',
        'agentMode':'COMPLETE','orchestration':'cliagents','tool':'formHandler:measurement',
        'agentConfig':{'cli':'codex','model':'gpt-5.6-sol','permission':'read_only','reasoning_effort':'low'},
        'instruction':f'enterprise MCP describe_schema로 현재 스키마를 읽으세요. {target}의 수를 구하는 SELECT를 직접 작성하고 enterprise query로 실행하세요. 반환된 값만 count에 넣고 실행 SQL을 sql에 쓰세요. 표/컬럼을 추측하지 마세요. 이 작업은 설비목록 집계이며 원인 진단이나 조치 카드 제출이 아닙니다. 쓰기는 금지합니다. note 필드가 있으면 대상 범위를 설명하세요.',
        'outputData':[f['key'] for f in fields]}],
      'events':[{'id':'start','type':'startEvent'},{'id':'multiple','type':'endEvent'},{'id':'single','type':'endEvent'}],
      'gateways':[{'id':'choose','type':'exclusiveGateway'}],
      'sequences':[{'id':'s1','source':'start','target':'measure'},{'id':'s2','source':'measure','target':'choose'},
        {'id':'s3','source':'choose','target':'multiple','condition':'count > 1'},
        {'id':'s4','source':'choose','target':'single','properties':{'default':True}}]}


def main():
    did='codex-registry-'+uuid.uuid4().hex[:8]
    out=ROOT/'.evidence/reaudit'/did;out.mkdir()
    report={'definition_id':did,'versions':[],'passed':False}
    def save():
        (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    save();print('evidence',out,flush=True)
    with psycopg.connect(DSN) as c:
        expected=[c.execute("select count(*) from ent.assets where code like 'HYD-%'").fetchone()[0],
                  c.execute("select count(*) from ent.assets where code='HYD-01'").fetchone()[0]]
    for version,count in zip(('1','2'),expected):
        raw=definition(did,version)
        (out/f'definition-{version}.json').write_text(json.dumps(raw,ensure_ascii=False,indent=2),encoding='utf-8')
        code,body=http('/api/process/definitions',{'definition':raw});assert code==201,(code,body)
        code,body=http('/api/instances/start',{'definition_id':did,'version':version,'event_id':did+'-'+version})
        assert code==200,(code,body)
        pid=body['proc_inst_id'];phase={'version':version,'instance_id':pid,'expected_count':count}
        report['versions'].append(phase);save()
        until=time.monotonic()+360
        while time.monotonic()<until:
            code,view=http('/api/instances/'+pid)
            assert code==200,(code,view)
            wi=view['workitems'][0]
            if view['instance']['status']=='COMPLETED':break
            if wi.get('draft_status') in ('FAILED','HUMAN_ASKED'):
                raise RuntimeError('worker did not complete: '+json.dumps(wi,ensure_ascii=False))
            time.sleep(2)
        events=http('/api/events?proc_inst_id='+pid)[1]
        graph=http('/api/instances/'+pid+'/graph')[1]
        (out/f'instance-{version}.json').write_text(json.dumps(view,ensure_ascii=False,indent=2),encoding='utf-8')
        (out/f'events-{version}.json').write_text(json.dumps(events,ensure_ascii=False,indent=2),encoding='utf-8')
        (out/f'graph-{version}.json').write_text(json.dumps(graph,ensure_ascii=False,indent=2),encoding='utf-8')
        values={x['key']:x['value'] for x in view['instance']['variables_data']}
        phase.update(actual_count=values.get('count'),end_event=view['instance'].get('end_event'),
                     workitem_id=wi['id'],status=wi['status'],output=wi.get('output'))
        save()
        assert view['instance']['status']=='COMPLETED' and wi['status']=='DONE',phase
        assert values.get('count')==count,phase
        assert phase['end_event']==('multiple' if count>1 else 'single'),phase
        if version=='2':assert values.get('note'),phase
        phase['tool_verification']=verify_tools(view,count,out,version);save()
        print('version',version,'count',count,'end',phase['end_event'],flush=True)
    report['passed']=True;save()
    print('registered Codex two-version execution PASS; inspect tool trace separately',flush=True)


if __name__=='__main__':main()
