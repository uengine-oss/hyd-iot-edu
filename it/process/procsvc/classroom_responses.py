"""Bounded human input to the same approved run; never a new model reservation."""
from . import mcp_check,task_deferral
from .classroom_authority import Denied,digest


def control(row):
    draft=row.get('draft') or {}
    if not isinstance(draft,dict):return None
    if row.get('draft_status')=='HUMAN_ASKED':
        question=draft.get('_human_request') or {}
        if not isinstance(question.get('question'),str) or not question.get('job_id'):
            raise Denied('보관된 관리 질문을 확인할 수 없습니다')
        if len(question['question'].encode('utf8'))>16000:
            raise Denied('관리 질문의 표시 한도를 초과했습니다')
        return {'status':'NEEDS_INPUT','request_id':question['job_id'],'question':question['question'],'output':None}
    if row['status']=='PENDING' and isinstance(draft.get('_deferral'),dict):
        receipt=draft['_deferral']
        return {'status':'DEFERRED','request_id':receipt['id'],
                'assessment':task_deferral.validate(receipt['assessment']),'output':None}


def respond(runtime,inst,policies,kind,request_id,text):
    policy=policies.get(kind) or {}
    maximum=policy.get('max_count')
    schema=policy.get('schema')
    if (type(maximum) is not int or not 1<=maximum<=8 or not isinstance(schema,dict)
            or schema.get('type')!='string' or not isinstance(text,str) or not text.strip()
            or len(text.encode('utf8'))>8000):
        raise Denied('강사가 허용한 보완 입력·횟수 범위를 확인하세요')
    wrapped={'type':'object','properties':{'text':schema},'required':['text'],'additionalProperties':False}
    if mcp_check._argument_problem({'input_schema':wrapped},{'text':text}):
        raise Denied('보완 답변이 강사 승인 입력 스키마와 다릅니다')
    with runtime.repo.instance_transaction(runtime.tenant_id,inst['proc_inst_id']):
        rows=runtime.repo.list_workitems(proc_inst_id=inst['proc_inst_id'],limit=None)
        if len(rows)!=1:raise Denied('관리 실행의 단일 작업을 확인할 수 없습니다')
        row=rows[0]
        events=[e for e in runtime.repo.list_events(todo_id=row['id'],limit=None) if e['job_id']=='CLASSROOM_RESPONSE']
        for event in events:
            data=event['data']
            if data['kind']==kind and data['request_id']==request_id:
                if data['text_hash']!=digest(text):raise Denied('같은 질문의 답변을 바꿀 수 없습니다')
                return {'status':'QUEUED','reused':True}
        if sum(e['data']['kind']==kind for e in events)>=maximum:
            raise Denied('이 실행의 보완 답변 횟수 한도를 초과했습니다')
        current=control(row)
        expected='NEEDS_INPUT' if kind=='human_answer' else 'DEFERRED'
        if not current or current['status']!=expected or current['request_id']!=request_id:
            raise Denied('현재 대기 중인 질문·보류와 일치하지 않습니다')
        if kind=='human_answer':
            runtime.human_response(row['id'],request_id,text,'classroom-student')
        else:
            task_deferral.reassess(runtime.repo,runtime.tenant_id,row['id'],deferral_id=request_id,
                request_id=digest([kind,request_id]),by='classroom-student',reason=text)
        runtime.repo.record_events([{'job_id':'CLASSROOM_RESPONSE','todo_id':row['id'],'proc_inst_id':inst['proc_inst_id'],
            'crew_type':'human','event_type':'classroom_response','data':{
                'kind':kind,'request_id':request_id,'text_hash':digest(text)}}])
    return {'status':'QUEUED','reused':False}
