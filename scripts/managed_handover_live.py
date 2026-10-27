"""One bounded teacher-side Luna handover through real managed HTTP/PG/CLI.
Student reads use the existing ReadRouter and live MCPs. No student workitem is
created: this proves teacher execution, not final student/UI completion.
"""
import argparse, json, os, secrets, subprocess, sys, threading, time
from datetime import datetime, timedelta, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'common'),str(ROOT/'it/process')]
import httpx, psycopg, uvicorn
from psycopg.rows import dict_row
from procsvc import classroom_admin, classroom_manifest, engine, instances
from procsvc.classroom_api import create_app
from procsvc.classroom_authority import Authority
from procsvc.procdb import PgRepo

parser=argparse.ArgumentParser()
parser.add_argument('--resume',action='store_true')
parser.add_argument('--state-probe',action='store_true',help='No model: exercise real PG/API/worker NEEDS_INPUT preservation and same-run response')
parser.add_argument('--user-approved-unpriced',action='store_true',help='Explicit user authorization for this bounded paid run despite unavailable relay pricing')
parser.add_argument('--answer-file',type=Path)
parser.add_argument('--input-usd-per-million',type=float)
parser.add_argument('--output-usd-per-million',type=float)
parser.add_argument('--max-usd',type=float)
args=parser.parse_args()
suffix='managed-handover-state-probe2' if args.state_probe else 'managed-handover-tools-v2'
OUT=ROOT/'.evidence/audit-20261027'/suffix
PRIVATE=ROOT/'work'/(suffix+'-private')
PRIVATE.mkdir(exist_ok=True)
STATE=PRIVATE/'credentials.json'
OUT.mkdir(exist_ok=True)
if not args.resume and (OUT/'attempt-started').exists():
    raise RuntimeError('Attempt exists: inspect or --resume; never overwrite original summary')
if not args.resume and not args.state_probe and not args.user_approved_unpriced:
    import math
    rates=[args.input_usd_per_million,args.output_usd_per_million,args.max_usd]
    if any(x is None or not math.isfinite(x) or x<=0 for x in rates):
        raise RuntimeError('Verified positive input/output USD rates and --max-usd required before live execution')
    # Conservative reservation: one input token per request byte, plus full output reservation.
    cost_bound=4*args.input_usd_per_million+0.768*args.output_usd_per_million
    if cost_bound>args.max_usd:raise RuntimeError('Reserved token/byte budget exceeds the USD cap')
PG='hyd-managed-handover-pg'+('-state-probe2' if args.state_probe else '')
WORKER='hyd-managed-handover-worker'+('-state-probe2' if args.state_probe else '')
DSN='postgresql://postgres@127.0.0.1:55757/hyd_system_progress_test'
BASE='http://127.0.0.1:55762'
report={'status':'preflight','model':'coding (previous routing proof: gpt-6-luna)',
        'scope':'teacher managed handover + real student-side read router, no UI/student submission',
        'attempt_limit':1,'max_seconds':600,'tool_calls':[]}
if args.state_probe:report.update(model='deterministic state probe; no AI',scope='preservation and same-run response only',cost_usd=0)
if args.user_approved_unpriced:report['cost_reservation']={'authorization':'user explicitly approved paid calls despite unavailable relay rates',
    'max_usd':None,'actual_cost':'unknown; enforced shared call/byte/output reservation limits only'}
if not args.resume and not args.state_probe and not args.user_approved_unpriced:report['cost_reservation']={'max_usd':args.max_usd,'upper_bound_usd':cost_bound,
    'input_usd_per_million':args.input_usd_per_million,'output_usd_per_million':args.output_usd_per_million,
    'actual_cost':'not measured; output_tokens is reserved, not generated'}
created=[]; server=None; thread=None; worker_log=None; repo=None; auth=None
if args.resume:
    report=json.loads((OUT/'summary.json').read_text(encoding='utf8'))
    if not report.get('run_id'):raise RuntimeError('No existing run to resume')
    if report.get('status') in ('DONE','COMPLETED'):raise RuntimeError('Completed run must not be regenerated')

def docker(*args,input=None,timeout=60):
    p=subprocess.run(['docker',*args],input=input,text=True,encoding='utf8',capture_output=True,timeout=timeout)
    if p.returncode:raise RuntimeError('docker operation failed: '+str(args[:2]))
    return p.stdout.strip()

def save():
    (OUT/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),encoding='utf8')

try:
    # No key is read during preflight. Never reuse a previous live attempt.
    if not args.resume and (OUT/'attempt-started').exists():raise RuntimeError('Live attempt already started; inspect its evidence, do not rerun')
    candidate=json.loads((ROOT/'.evidence/audit-20261027/instructor-candidates/ShiftHandover-task_draft.json').read_text(encoding='utf8'))
    policy=json.loads((ROOT/'.evidence/audit-20261027/instructor-candidates/policy-draft.json').read_text(encoding='utf8'))
    policy['documents']={};policy['agents']={'shift.draft':candidate['approval']}
    policy['actions']={'agent_run':dict(policy['actions']['agent_run'])}
    policy['responses']={'shift.draft':policy['responses']['ShiftHandover-task_draft']}
    # One initial invocation and at most one reviewed same-run continuation.
    # The ledger's existing total caps remain shared across both invocations.
    policy['actions']['agent_run']['max_seconds']=1800
    policy['total_calls']=24;policy['total_input_bytes']=4000000;policy['total_output_tokens']=768000
    policy['actions']['agent_run'].update(max_calls=24,max_input_bytes=4000000,max_output_tokens=768000)
    policy['max_concurrency']=1
    tool_policy=policy['tool_io']
    # This rehearsal performs only reads, never proposal/physical effects.
    tool_policy['tools']=[t for t in tool_policy['tools'] if t not in ('hyd-dmn/submit_decision','hyd-dmn/submit_purchase')]
    tool_policy['catalog']={k:v for k,v in tool_policy['catalog'].items() if k in tool_policy['tools']}
    tool_policy['catalog']['enterprise/describe_catalog']['inputSchema']={
        'type':'object','properties':{'table':{'anyOf':[{'type':'string'},{'type':'null'}],'default':None,
        'description':'목록의 name 또는 ent.name. 생략하면 표 목록'},
        'offset':{'type':'integer','default':0,'minimum':0},
        'limit':{'type':'integer','default':12,'minimum':1,'maximum':20}},'additionalProperties':False}
    report['approved_read_tools']=len(tool_policy['tools'])
    report['revision']=candidate['approval']['revision']
    if not args.resume:
        docker('run','-d','--name',PG,
               '-e','POSTGRES_HOST_AUTH_METHOD=trust','-e','POSTGRES_DB=hyd_system_progress_test',
               '-p','127.0.0.1:55757:5432','postgres:17')
        created.append(PG)
    else:
        state=json.loads(docker('inspect',PG))[0]['State']
        if not state['Running']:docker('start',PG)
    for _ in range(15):
        try:
            with psycopg.connect(DSN,connect_timeout=1):pass
            break
        except psycopg.OperationalError:time.sleep(.5)
    else:raise RuntimeError('preserved PostgreSQL unavailable')
    if not args.resume:
        p=subprocess.run([sys.executable,str(ROOT/'work/bootstrap_audit_pg.py')],cwd=ROOT,capture_output=True,timeout=60)
        if p.returncode:raise RuntimeError('migration failed; preserve database for diagnosis')
    repo=PgRepo(DSN)
    if not args.resume:
        with repo._conn() as db:db.execute("insert into tenants(id,name) values ('hyd','Managed handover rehearsal')")
    runtime=instances.InstanceRuntime(repo,engine.Definition.from_dict(candidate['definition']),instances.Hooks(),time_scale=20,tenant_id='hyd')
    if not args.resume:
        review=classroom_manifest.review_target(runtime,candidate)
        classroom_manifest.apply_candidate(runtime,candidate,fingerprint=review['fingerprint'],target_fingerprint=review['target_fingerprint'])
    auth=Authority(lambda:psycopg.connect(DSN,row_factory=dict_row))
    private_file=PRIVATE/'runtime.key'
    if args.resume:
        student_key=json.loads(STATE.read_text(encoding='utf8'))['student_key']
        assert private_file.is_file()
    else:
        student_key=secrets.token_urlsafe(40); private_key=secrets.token_urlsafe(40)
        private_file.write_text(private_key,encoding='utf8')
        STATE.write_text(json.dumps({'student_key':student_key}),encoding='utf8')
    os.environ['HYD_WORKER_RUNTIME_KEY_FILE']=str(private_file)
    if not args.resume:
        classroom_admin.approve(auth,None,key=student_key,subject='hyd',scope='one-managed-handover-rehearsal',
            expires_at=datetime.now(timezone.utc)+timedelta(hours=24),policy=policy,runtime=runtime)
    def upstream():
        if args.state_probe:raise RuntimeError('State probe cannot call a model')
        # Read at authorized model execution only; never persist/print this key.
        v=json.loads(docker('inspect','hyd-system-audit-20261026-agent-worker-1'))[0]
        env={x.partition('=')[0]:x.partition('=')[2] for x in v['Config']['Env']}
        url=env['ANTHROPIC_BASE_URL'].rstrip('/')
        assert url=='https://knu-litellm-1087825885001.asia-northeast3.run.app'
        return {'url':url,'key':env['ANTHROPIC_API_KEY']}
    app=create_app(auth,source_loader=None,catalog_factory=None,runtime_factory=lambda _:runtime,
                   upstream_factory=upstream,agent_enabled=True)
    server=uvicorn.Server(uvicorn.Config(app,host='0.0.0.0',port=55762,log_level='error',access_log=False))
    thread=threading.Thread(target=server.run,daemon=True);thread.start()
    for _ in range(40):
        if server.started:break
        time.sleep(.1)
    else:raise RuntimeError('managed API not ready')
    reach=docker('run','--rm','--add-host','classroom:host-gateway','--entrypoint','python',
        'hyd-classroom-worker-isolated:20261027','-c',
        "import urllib.request; assert urllib.request.urlopen('http://classroom:55762/healthz',timeout=5).status==200; print('reachable')")
    assert reach=='reachable'
    report['preflight']='candidate approved in preserved PG; worker reaches real API'
    save()
    headers={'Authorization':'Bearer '+student_key}
    client=httpx.Client(base_url=BASE,headers=headers,trust_env=False,timeout=15)
    inputs={'asset':'HYD-01','shift_label':'다음 교대','as_of':datetime.now(timezone.utc).isoformat(),
            'work_notes':'정비 완료라고 전달받았으나 열린 작업지시와 대조가 필요합니다. 부품 도착 예정 메모는 실제 재고 확인 전입니다.',
            'sender_notes':None,'receiver_notes':None}
    if args.resume:
        run_id=report['run_id']
        # Reattach the existing run. Never reserve another run or reset its ledger/deadline.
        current=client.get(f'/v1/classroom/agents/runs/{run_id}/result')
        current.raise_for_status()
        if args.answer_file:
            if report.get('responses'):raise RuntimeError('One reviewed continuation limit reached')
            value=current.json()
            if value['status']!='NEEDS_INPUT':raise RuntimeError('Existing run is not waiting for an answer')
            answer={'kind':'human_answer','request_id':value['request_id'],'text':args.answer_file.read_text(encoding='utf8')}
            response=client.post(f'/v1/classroom/agents/runs/{run_id}/respond',json=answer)
            response.raise_for_status()
            report.setdefault('responses',[]).append({'request_id':value['request_id'],'receipt':response.json()})
        state=json.loads(docker('inspect',WORKER))[0]['State']
        if state['Running']:
            report['reattached_active_worker']=True
        elif args.answer_file or (current.json()['status']=='PENDING' and report.get('responses')):
            # A response may have been durably queued before docker start failed.
            # Resume that queued work without posting another answer/reservation.
            docker('start',WORKER)
        else:
            raise RuntimeError('Stopped worker preserved; supply a reviewed answer, do not restart blindly')
    else:
        # Mark before POST: an ambiguous HTTP outcome must not create another run.
        (OUT/'attempt-started').write_text(datetime.now(timezone.utc).isoformat(),encoding='utf8')
        response=client.post('/v1/classroom/agents',json={'reference':'shift.draft','inputs':inputs,'expected_revision':candidate['approval']['revision']})
        response.raise_for_status();run_id=response.json()['run_id'];report['run_id']=run_id
        save()
    worker_code="from worker.main import _repo,settings; from worker.runner import Runner; r=Runner(settings,_repo()); assert r.poll_once()==1; print('bounded worker finished')"
    if args.state_probe:
        worker_code="""import json
from cliagents import ExecEvent,ExecEventKind
from worker.main import _repo,settings
from worker.runner import Runner
def execute(provider,request,env):
    resumed=bool(request.resume_session)
    if resumed:assert request.resume_session=='preserved-session'
    yield ExecEvent(kind=ExecEventKind.RUN_START,session_id='preserved-session')
    yield ExecEvent(kind=ExecEventKind.RESULT,session_id='preserved-session',text=json.dumps(
        {'__human_input__':{'question':'same-session-resumed' if resumed else 'preservation-probe'}}))
r=Runner(settings,_repo(),exec_fn=execute)
assert r.poll_once()==1
print('state probe worker finished; no AI')
"""
    worker_args=['run' ,'-d','--name',WORKER,'--add-host','classroom:host-gateway',
        '--mount',f'type=bind,source={private_file},target=/run/secrets/worker_runtime,readonly',
        '-e','HYD_WORKER_RUNTIME_KEY_FILE=/run/secrets/worker_runtime','-e','HYD_MANAGED_MODEL_REQUIRED=1',
        '-e','HYD_MANAGED_MODEL_URL=http://classroom:55762',
        '-e','SUPABASE_DSN=postgresql://postgres@host.docker.internal:55757/hyd_system_progress_test',
        '-e','TENANT_ID=hyd','-e','CLIAGENTS_RUN_TIMEOUT_SECONDS=600',
        '--entrypoint','python','hyd-classroom-worker-isolated:20261027','-c',worker_code]
    if not args.resume:
        docker(*worker_args);created.append(WORKER)
    started=time.monotonic();last_notice=0
    observation_reported=False
    while True:
        if time.monotonic()-started>=630 and not observation_reported:
            report['observation_timeout']='continuing to serve existing worker, no restart'
            observation_reported=True
            save()
        pending=client.get(f'/v1/classroom/runs/{run_id}/tool-requests');pending.raise_for_status()
        for query in pending.json()['requests']:
            assert query['tool'] in tool_policy['tools']
            # Existing process holds its own MCP credentials. ReadRouter rejects
            # writes and truncated responses; only its normalized reply returns.
            code="""import json,sys
from procsvc.procdb import PgRepo
from procsvc.classroom_read_tools import ReadRouter
from procsvc import mcp_check,mcp_secrets
captured={}; credentials=[]
shape=mcp_check.shape_result; spec=mcp_secrets.runtime_spec
def capture_shape(value,*args,**kwargs):
    captured['mcp_response']=value
    return shape(value,*args,**kwargs)
def capture_spec(*args,**kwargs):
    value=spec(*args,**kwargs);credentials.extend(value[1]);return value
mcp_check.shape_result=capture_shape;mcp_secrets.runtime_spec=capture_spec
v=json.load(sys.stdin)
reply=ReadRouter(PgRepo(),'hyd',v['allowed'])(v['tool'],v['arguments'])
print(json.dumps({'reply':reply,'source':mcp_secrets.redact(captured,credentials)},ensure_ascii=False))
"""
            request={'allowed':tool_policy['tools'],'tool':query['tool'],'arguments':query['arguments']}
            payload=code+'\n'
            # Supply code through argv (no credentials), request through stdin.
            raw=docker('exec','-i','hyd-system-audit-20261026-process-1','python','-c',payload,input=json.dumps(request),timeout=45)
            envelope=json.loads(raw);reply=envelope['reply']
            with (OUT/'tool-responses.jsonl').open('a',encoding='utf8') as trace:
                trace.write(json.dumps({'request':query,'raw':raw,'reply':reply},ensure_ascii=False)+'\n')
            result=client.post('/v1/classroom/tool-results',json=dict(run_id=run_id,request_id=query['id'],**reply));result.raise_for_status()
            report['tool_calls'].append({'tool':query['tool'],'is_error':reply['is_error']})
            save()
        runtime.poll_once()
        result=client.get(f'/v1/classroom/agents/runs/{run_id}/result');result.raise_for_status()
        value=result.json()
        if value['status']!='PENDING':
            report['status']=value['status'];(OUT/'result.json').write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8');break
        if time.monotonic()-last_notice>30:
            print(json.dumps({'status':'running','seconds':round(time.monotonic()-started),'tool_calls':len(report['tool_calls'])}),flush=True)
            last_notice=time.monotonic()
        live=json.loads(docker('inspect',WORKER))[0]
        if not live['State']['Running']:
            runtime.poll_once()
            report['status']='worker-exited-before-terminal-result';break
        time.sleep(1)
    report['seconds']=round(time.monotonic()-started,2)
    with auth.connect() as db:
        usage=db.execute('select state,calls,input_bytes,output_tokens,work_ref from hyd_classroom_runs where id=%s',(run_id,)).fetchone()
        report['usage']=dict(usage)
    if usage['work_ref']:
        view=runtime.repo.get_instance(usage['work_ref'])
        items=repo.list_workitems(proc_inst_id=usage['work_ref'],limit=None)
        (OUT/'instance.json').write_text(json.dumps({'instance':view,'workitems':items},ensure_ascii=False,indent=2,default=str),encoding='utf8')
    save()
except BaseException as exc:
    report['exception_type']=type(exc).__name__
    report['status_before_exception']=report.get('status')
    report['status']='INTERRUPTED'
    raise
finally:
    # Always retain the actual DB and worker filesystem, including CLI sessions.
    # Snapshot failures must not trigger deletion or prevent other snapshots.
    errors=[]
    if repo is not None:
        try:
            with (OUT/'database.dump').open('wb') as archive:
                subprocess.run(['docker','exec',PG,'pg_dump','-U','postgres','-Fc','hyd_system_progress_test'],
                               stdout=archive,stderr=subprocess.PIPE,check=True,timeout=60)
            if report.get('run_id'):
                with auth.connect() as db:
                    row=db.execute('select * from hyd_classroom_runs where id=%s',(report['run_id'],)).fetchone()
                (OUT/'ledger.json').write_text(json.dumps(dict(row),ensure_ascii=False,indent=2,default=str),encoding='utf8')
                if row and row['work_ref']:
                    items=repo.list_workitems(proc_inst_id=row['work_ref'],limit=None)
                    trace={w['id']:repo.list_events(todo_id=w['id'],limit=None) for w in items}
                    (OUT/'full-trace.json').write_text(json.dumps(trace,ensure_ascii=False,indent=2,default=str),encoding='utf8')
        except Exception as exc:errors.append('database:'+type(exc).__name__)
    try:
        proc=subprocess.run(['docker','logs',WORKER],capture_output=True,timeout=15)
        if proc.returncode==0:(OUT/'worker.log').write_bytes(proc.stdout+proc.stderr)
    except Exception as exc:errors.append('worker:'+type(exc).__name__)
    # PG, worker, workspace volume, credentials, and original attempt marker remain.
    if server:
        server.should_exit=True
        if thread:thread.join(timeout=5)
    report['preserved']={'postgres':PG,'worker':WORKER,'private_state':str(PRIVATE),
                         'snapshot_errors':errors,'cleanup':'none; explicit diagnosis/cleanup required'}
    save()
print(json.dumps(report,ensure_ascii=False,default=str),flush=True)
