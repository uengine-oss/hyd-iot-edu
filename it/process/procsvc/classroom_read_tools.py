"""Student-side current-state adapter for the managed tool exchange.

Reuse the existing MCP connection/schema/read-only checks. A queued call cannot
choose a URL, launch command, or credential. Configuration is pinned for the
run and read again before each call. The instructor's allowlist remains the
authorization boundary; this local gate is additional defence, not its substitute.
"""
import json

from . import mcp_check, mcp_registry, mcp_secrets


class ReadRouter:
    def __init__(self, repo, tenant, allowed_tools):
        self.repo, self.tenant = repo, tenant
        self.allowed = frozenset(allowed_tools)
        servers = mcp_registry.store_for(repo).servers(tenant)
        self.fingerprints = {name:mcp_registry.fingerprint(spec) for name,spec in servers.items()
                             if any(tool.startswith(name+'/') for tool in self.allowed)}

    @staticmethod
    def error(reason):
        return {'is_error':True,'result':{'error':reason}}

    def __call__(self, qualified, arguments):
        if qualified not in self.allowed or qualified.count('/') != 1 or not isinstance(arguments,dict):
            return self.error('이 실행에서 허용하지 않은 도구 조회입니다')
        name, tool = qualified.split('/')
        try:
            entry = mcp_registry.store_for(self.repo).servers(self.tenant).get(name)
            if not entry or self.fingerprints.get(name) != mcp_registry.fingerprint(entry):
                return self.error('조회 연결 설정이 바뀌었습니다. 실행 계약을 다시 확인하세요')
            confirmed = set()
            if name not in mcp_registry.BASE_SERVERS:
                gate = (entry.get('hyd') or {}).get('gate') or {}
                if gate.get('fingerprint') != self.fingerprints[name] or tool not in (gate.get('read_tools') or []):
                    return self.error('읽기 도구 연결 검사를 통과하지 않았습니다')
                confirmed = set(mcp_registry.confirmed_of(entry))
            spec, secrets = mcp_secrets.runtime_spec(self.repo,self.tenant,name,entry)
            # call() obtains fresh tools/list and validates inputSchema in that
            # same session. A changed tool becoming writable cannot slip through.
            response = mcp_secrets.redact(mcp_check.call(spec,tool,arguments,timeout=25,
                                                       max_chars=32000,confirmed=confirmed),secrets)
        except Exception:
            return self.error('학생 조회 연결을 사용할 수 없습니다. 현재 상태는 미확인입니다')
        if response.get('status') != 'ok' or not isinstance(response.get('result'),dict):
            return self.error('학생 도구 조회가 거절되거나 실패했습니다. 현재 상태는 미확인입니다')
        result = response['result']
        if result.get('truncated'):
            return self.error('도구 응답이 잘렸습니다. 조회 범위를 줄이거나 상세 페이지로 나누세요')
        try:
            data = json.loads(result['text']) if result.get('json') else result['text']
        except (ValueError,KeyError,TypeError):
            return self.error('학생 도구 응답 형식을 확인할 수 없습니다')
        return {'is_error':bool(result.get('is_error')),'result':data}


class TaskRouter(ReadRouter):
    """Bind local reads and proposal registration to one live student task.
    Proposal intent is durable before RPC. Unknown outcomes are not retried;
    completed identical proposals reuse the receipt, not another registration.
    """
    def __init__(self,runtime,workitem_id,consumer,allowed_tools):
        super().__init__(runtime.repo,runtime.tenant_id,allowed_tools)
        self.runtime,self.workitem_id,self.consumer=runtime,workitem_id,consumer

    def claim(self):
        from . import worker_credentials
        row=worker_credentials._claim(self.runtime,{'tenant_id':self.tenant,'todo_id':self.workitem_id,'consumer':self.consumer})
        inst=self.repo.get_instance(row['proc_inst_id'])
        if not inst or inst.get('status')!='RUNNING' or inst.get('is_deleted'):
            raise ValueError('종료된 학생 작업입니다')
        return row,inst

    def __call__(self,qualified,arguments):
        from . import classroom_proposals
        try:
            row,inst=self.claim()
            if qualified in classroom_proposals.TOOLS:
                return self.propose(row,inst,qualified,arguments)
        except Exception:
            return self.error('학생 작업의 현재 담당·제안 저장 권한을 확인할 수 없습니다')
        from uuid import uuid4
        use_id=str(uuid4())
        common={'job_id':'CLASSROOM_LOCAL_READ','todo_id':row['id'],'proc_inst_id':inst['proc_inst_id'],'crew_type':'tool'}
        tool='mcp__'+qualified.replace('/','__')
        self.repo.record_events([dict(common,event_type='tool_usage_started',data={
            'tool':tool,'tool_use_id':use_id,'input':arguments})])
        reply=super().__call__(qualified,arguments)
        self.repo.record_events([dict(common,event_type='tool_usage_finished',data={
            'tool':tool,'tool_use_id':use_id,'output':reply['result'],'is_error':reply['is_error']})])
        return reply

    def propose(self,row,inst,qualified,arguments):
        from . import classroom_proposals,decision_scope,engine
        from .classroom_authority import digest
        from uuid import uuid4
        if qualified not in self.allowed or not isinstance(arguments,dict):
            return self.error('허용되지 않은 제안 저장입니다')
        scope=dict(decision_scope.expected(inst,row),consumer=self.consumer)
        decision_scope.validate_submission(inst,self.runtime.definition_for(inst),row,scope)
        values=engine.variables(inst);alert=values.get('alert') or {}
        expected={'asset':values.get('asset'),'incident':values.get('incident')}
        if qualified.endswith('/submit_purchase'):
            expected['part_no']=(alert.get('evidence') or {}).get('part_no')
        else:
            expected['pattern']=values.get('pattern')
        if any(not value or arguments.get(key)!=value for key,value in expected.items()) or arguments.get('overrides'):
            return self.error('현재 학생 사건의 설비·품목·조건과 다른 제안은 저장할 수 없습니다')
        if arguments.get('alert_id') not in (None,alert.get('alertId')):
            return self.error('다른 경보의 제안은 저장할 수 없습니다')
        args=dict(arguments,process_scope=scope)
        identity=digest([qualified,{k:v for k,v in args.items() if k!='process_scope'},decision_scope.expected(inst,row)])
        with self.repo.instance_transaction(self.tenant,inst['proc_inst_id']):
            current_row,current_inst=self.claim()
            decision_scope.validate_submission(current_inst,self.runtime.definition_for(current_inst),current_row,scope)
            if engine.variables(current_inst)!=values:
                return self.error('제안 준비 중 학생 사건의 입력이 바뀌었습니다. 현재 상태를 다시 확인하세요')
            history=[e for e in self.repo.list_events(todo_id=row['id'],limit=None)
                     if e.get('job_id') in ('CLASSROOM_PROPOSAL_STARTED','CLASSROOM_PROPOSAL_FINISHED')]
            if history:
                finished=next((e['data'] for e in reversed(history) if e['job_id']=='CLASSROOM_PROPOSAL_FINISHED'),None)
                if finished and finished.get('request_hash')==identity and not finished.get('outcome_unknown') and not finished['reply']['is_error']:
                    return finished['reply']
                return self.error('이 작업의 이전 제안 저장을 확인해야 합니다. 응답 미확인·다른 내용은 자동 재등록하지 않습니다')
            use_id=str(uuid4())
            self.repo.record_events([{'job_id':'CLASSROOM_PROPOSAL_STARTED','todo_id':row['id'],'proc_inst_id':inst['proc_inst_id'],
                'crew_type':'tool','event_type':'tool_usage_started','data':{'tool':'mcp__'+qualified.replace('/','__'),
                'tool_use_id':use_id,'input':args,'request_hash':identity}}])
        try:
            entry=mcp_registry.store_for(self.repo).servers(self.tenant).get('hyd-dmn')
            if not entry or mcp_registry.fingerprint(entry)!=self.fingerprints.get('hyd-dmn'):
                raise ValueError('DMN 설정 변경')
            spec,secrets=mcp_secrets.runtime_spec(self.repo,self.tenant,'hyd-dmn',entry)
            spec=dict(spec,headers=dict(spec.get('headers') or {},**{'X-HYD-Process-Scope':json.dumps(scope,separators=(',',':'))}))
            response=mcp_secrets.redact(classroom_proposals.call(spec,qualified,args),secrets)
            result=response.get('result') or {}
            unknown=response.get('status')!='ok' or bool(result.get('truncated'))
            if unknown:
                reply=self.error('제안 저장 응답이 확인되지 않았습니다. 실제 등록 결과 확인 전 재실행하지 마세요')
            else:
                data=json.loads(result['text']) if result.get('json') else result['text']
                reply={'is_error':bool(result.get('is_error')),'result':data}
                unknown=reply['is_error']
        except Exception:
            unknown=True;reply=self.error('제안 저장 응답이 확인되지 않았습니다. 실제 등록 결과 확인이 필요합니다')
        self.repo.record_events([{'job_id':'CLASSROOM_PROPOSAL_FINISHED','todo_id':row['id'],'proc_inst_id':inst['proc_inst_id'],
            'crew_type':'tool','event_type':'tool_usage_finished','data':{'tool':'mcp__'+qualified.replace('/','__'),
            'tool_use_id':use_id,'output':reply['result'],'is_error':reply['is_error'],'request_hash':identity,
            'reply':reply,'outcome_unknown':unknown}}])
        return reply
