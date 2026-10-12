from pathlib import Path
import json, hashlib, collections, subprocess
O=Path(__file__).parent;R=O.parents[1];T=R/'.claude/worktrees/codex-portal-20261011';E=R/'.evidence'
def sha(b):return hashlib.sha256(b).hexdigest()
def ref(p):return {'path':str(p),'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size}
dirs=[E/'delegated-review-20261012/watch-B-final-live',E/'delegated-review-20261012/watch-C-live',E/'education-fixture-correction-20261012/watch-B-live']
streams=[];refs=[]
for d in dirs:
    result=json.loads((d/'result.json').read_text(encoding='utf8'))
    frames=[json.loads(s) for s in (d/'sse-frames.jsonl').read_text(encoding='utf8').splitlines()]
    fresh=[f for f in frames if f['sse_event_name']=='message']
    events=[json.loads(f['frame_data']) for f in fresh]
    pairs=[]
    for e in events:
        if e['event_type']=='tool_usage_started':
            x=e.get('data') or {};key=(e.get('proc_inst_id'),e.get('todo_id'),e.get('job_id'),x.get('tool_use_id'))
            ends=[v for v in events if v['event_type']=='tool_usage_finished' and (v.get('proc_inst_id'),v.get('todo_id'),v.get('job_id'),v.get('data',{}).get('tool_use_id'))==key]
            pairs.append({'identity':key,'tool':x.get('tool'),'start_id':e['id'],'start_at':e['timestamp'],'input_present':'input' in x,'end_id':ends[0]['id'] if ends else None,'output_present':bool(ends and 'output' in ends[0].get('data',{}))})
    caps=[{'kind':c['kind'],'png':ref(d/c['png']),'identity':c.get('identity'),'capture_begin':c.get('capture_begin'),'native_row_text':c.get('native_row_text'),'bounds':c.get('native_bounds'),'before_agent_boundary':c.get('before_agent_boundary',c.get('before_actual_completion'))} for c in result.get('captures',[])]
    streams.append({'directory':str(d),'reported_passed':result.get('passed'),'armed_at':result.get('armed_at'),'total_frames':len(frames),'fresh_frames':len(fresh),'history_frames':len(frames)-len(fresh),'event_types':dict(collections.Counter(e['event_type'] for e in events)),'private_events_reported':result.get('privateEvents'),'errors':result.get('errors'),'tools':pairs,'public_message_identities':[{'id':e['id'],'job_id':e.get('job_id'),'timestamp':e['timestamp'],'message_id':e.get('data',{}).get('message_id'),'sequence':e.get('data',{}).get('sequence'),'complete':e.get('data',{}).get('complete')} for e in events if e.get('data',{}).get('type') in ['text','public_text']],'boundaries':[{'id':e['id'],'event_type':e['event_type'],'timestamp':e['timestamp'],'job_id':e.get('job_id')} for e in events if e['event_type'] in ['task_completed','task_deferred','human_response']],'captures':caps,'frame_hashes_valid':all(sha(f['frame_data'].encode())==f['frame_sha256'] for f in frames)})
    refs.extend([ref(d/'result.json'),ref(d/'sse-frames.jsonl'),ref(d/'native-dom.jsonl')])
sourcefiles=['it/agent-worker/worker/events.py','it/agent-worker/worker/runner.py','it/process/procsvc/instance_mode.py','it/portal/www/liveStream.js','it/portal/www/trace.js','it/portal/www/caseRecord.js','it/portal/www/taskDetail.js','it/portal/www/ui.js']
refs.extend(ref(T/p) for p in sourcefiles)
referencefiles=[E/'reaudit/references-latest/process-gpt/docs/en/architecture.md',E/'reaudit/references-latest/process-gpt-vue3/src/ds/components/PgToolStep.vue',E/'reaudit/references-latest/ontology-studio/frontend/src/features/files/FilePanel.vue',T/'docs/handoff/verification/2026-10-12/final-delegated/reference-dify.png']
refs.extend(ref(p) for p in referencefiles)
stored=[E/'delegated-review-20261012/portal-final-delegated-live/A-record-1440.json',E/'delegated-review-20261012/portal-final-delegated-live/A-result-1440.json',E/'k3-preparation-20261012/live-F27-final-3/result.json',E/'k3-preparation-20261012/F27-trace-captures/result.json',E/'education-fixture-correction-20261012/native-B-final/result.json',E/'google-meeting-import-20261012/native-labels/result.json']
refs.extend(ref(p) for p in stored)
refs.append(ref(E/'delegated-review-20261012/pytest-public-stream-final3.log'))
refs.append(ref(T/'docs/handoff/verification/2026-10-12/final-delegated/C-business-completion-proof.json'))
fixture=T/'tests/fixtures/actual_bc_record_followup.json'
fv=json.loads(fixture.read_text(encoding='utf8')); refs.append(ref(fixture))
rows=[]
for line in (O/'audit.md').read_text(encoding='utf8').splitlines():
    if line.startswith('|') and not line.startswith('|---'):rows.append(dict(zip(['segment','real_stream_evidence','display_and_stored_boundary'],[x.strip() for x in line.strip('|').split('|')])))
head=subprocess.check_output(['git','-C',str(T),'rev-parse','HEAD'],text=True).strip()
v={'method':'Independent read-only original evidence and current source audit; no live GET, test, capture, LLM, POST, business replay or injected SSE','head':head,'matrix':rows[1:],'streams':streams,'evidence_sha256':refs,'confirmed_product_subscription_defect':None,'collector_evidence_limits':['C fresh tool identity mismatches historical 10:13:03 native row chosen in tool PNG','B first live tool PNG is shell, not full opened MCP I/O','Education-corrected B collector stopped after public PNG and eight fresh frames; completion native evidence is stored state'],'remaining_gaps':['Real-time final recommendation card rendering at creation','Real-time approval waiting/delay/reject transitions','Real-time system processing and automatic verification completion','Concurrent Trace and TaskDetail native display for the same fresh run'],'no_new_run_requested':True,'images_inspected':[str(d/c['png']) for d in dirs for c in json.loads((d/'result.json').read_text(encoding='utf8')).get('captures',[])],'not_user_visual_approval':True}
v['current_tool_call_identity']='ui.js:5-6 already uses case+todo+job+tool_use_id; historical collector selection does not establish current product correlation defect'
v['stored_fixture_case_event_counts']={k:len(x.get('events',[])) for k,x in fv.items() if isinstance(x,dict) and isinstance(x.get('events'),list)}
v['source_unchanged_during_audit']=all(sha(Path(x['path']).read_bytes())==x['sha256'] for x in refs if str(T) in x['path'])
v['markdown_sha256']=sha((O/'audit.md').read_bytes())
(O/'audit.json').write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'head':head,'matrix':len(v['matrix']),'streams':[(s['fresh_frames'],s['history_frames'],s['frame_hashes_valid']) for s in streams]},ensure_ascii=False))
