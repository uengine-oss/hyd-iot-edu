import copy, hashlib, json, pathlib, subprocess, sys
T=pathlib.Path('D:/work/study/hyd-iot-edu/.claude/worktrees/codex-portal-20261011')
H=pathlib.Path(__file__).parent
sys.path.insert(0,str(T));sys.path.insert(0,str(T/'it/process'));sys.path.insert(0,str(T/'common'))
from procsvc import bpmn_import
from scripts import prepare_google_meeting_mapping as prep
agent=json.loads((H/'identity-created-agent.json').read_text(encoding='utf-8'))
role=json.loads((H/'identity-created-role.json').read_text(encoding='utf-8'))
catalog=json.loads((H/'identity-catalog-after.json').read_text(encoding='utf-8'))
assert any(a['id']==agent['id'] for a in catalog['agents'])
assert any(r['name']==role['name'] and r['endpoint']==role['id'] for r in catalog['roles'])
assert not agent.get('model') and not agent.get('tools') and role['members']==[]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def originals():return {str(p.relative_to(prep.EXAMPLE)):sha(p) for p in prep.EXAMPLE.rglob('*') if p.is_file()}
before=originals(); target=H/'prepared'
command=[sys.executable,str(T/'scripts/prepare_google_meeting_mapping.py'),'--agent-id',agent['id'],'--organizer-role',role['name'],'--calendar-server','google-meeting-calendar','--drive-server','google-meeting-drive','--output-dir',str(target)]
completed=subprocess.run(command,cwd=T,capture_output=True,text=True,encoding='utf-8')
assert completed.returncode==0,completed.stdout+completed.stderr
xml=(target/'flow.bpmn').read_text(encoding='utf-8');mapping=json.loads((target/'mapping.json').read_text(encoding='utf-8'))
preconditions=json.loads((target/'preconditions.json').read_text(encoding='utf-8'))
ctx=dict(catalog=catalog,definition_id='google-meeting-prepared',version='1',file_name='flow.bpmn',xml_sha256=bpmn_import.xml_sha256(xml),name=None)
parsed=bpmn_import.parse_bpmn(xml);checked=bpmn_import.check(parsed,mapping,ctx)
assert checked['ok'],checked['problems']
assert not any(preconditions[k] for k in ['registration_verified','google_read_verified','execution_ready'])
assert 'idempotency_key' not in mapping['tasks']['Activity_invite']['config']['arguments']
negative=copy.deepcopy(mapping);negative['tasks']['Activity_propose']['agent']='agent:unregistered-meeting'
rejected=bpmn_import.check(parsed,negative,ctx);assert not rejected['ok']
overwrite=subprocess.run(command,cwd=T,capture_output=True,text=True,encoding='utf-8');assert overwrite.returncode!=0
assert before==originals()
proof=dict(status='PREPARED_STRUCTURAL_IMPORT_VALIDATED_NOT_EXECUTION_READY',actual_agent_id=agent['id'],actual_organizer_role=role['name'],actual_organizer_role_id=role['id'],model='inherit runtime default; no GPU connectivity assertion',agent_tools_attached=False,organizer_member_assigned=False,registration_verified=False,google_read_verified=False,execution_ready=False,command=command,cli_stdout=completed.stdout,structural_check={'ok':checked['ok'],'problems':checked['problems'],'definition':checked['definition']},negative_unknown_agent={'ok':rejected['ok'],'problems':rejected['problems']},negative_overwrite={'exit_code':overwrite.returncode,'stdout':overwrite.stdout},original_before=before,original_after=originals(),original_unchanged=True,output_files={p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in target.iterdir()},live_POST=0,Google_calls=0,token_reads=0,whole27_repeated=0,offline_entrypoint='procsvc.bpmn_import.parse_bpmn/check with actual refreshed GET catalog')
(H/'prepared-bundle-proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:proof[k] for k in ['status','actual_agent_id','actual_organizer_role','original_unchanged','execution_ready']},ensure_ascii=False))
