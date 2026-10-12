import copy, hashlib, json, pathlib, sys
T = pathlib.Path('D:/work/study/hyd-iot-edu/.claude/worktrees/codex-portal-20261011')
OUT = pathlib.Path(__file__).parent
sys.path.insert(0, str(T))
sys.path.insert(0, str(T/'it/process'))
sys.path.insert(0, str(T/'common'))
from procsvc import bpmn_import
from scripts import prepare_google_meeting_mapping as prep

original = prep.EXAMPLE
def hashes():
    return {str(p.relative_to(original)): hashlib.sha256(p.read_bytes()).hexdigest() for p in original.rglob('*') if p.is_file()}
before = hashes()
xml = (original/'flow.bpmn').read_text(encoding='utf-8')
mapping = json.loads((original/'mapping.json').read_text(encoding='utf-8'))
catalog = json.loads((OUT/'actual-import-catalog.json').read_text(encoding='utf-8'))
parsed = bpmn_import.parse_bpmn(xml)
ctx = dict(catalog=catalog, definition_id='google-meeting-prepared', version='1', file_name='flow.bpmn', xml_sha256=bpmn_import.xml_sha256(xml), name=None)
checked = bpmn_import.check(parsed, mapping, ctx)
assert checked['ok'] is False
problems = checked['problems']
assert any('역할' in p.get('reason','') for p in problems)
assert any('에이전트' in p.get('reason','') for p in problems)
negative = []
for field in ['agent_id','organizer_role']:
    values = dict(agent_id='UNUSED', organizer_role='UNUSED', calendar_server='google-meeting-calendar', drive_server='google-meeting-drive')
    values[field] = ''
    try:
        prep.prepare(**values)
        raise AssertionError('Missing explicit identity unexpectedly accepted')
    except ValueError as exc:
        negative.append(dict(field=field, rejected=True, message=str(exc)))
assert before == hashes()
result = dict(status='BLOCKED_MISSING_ACTUAL_MEETING_AGENT_AND_ORGANIZER', structural_import_ok=False, current_original_import_problems=problems, negative_preparation_checks=negative, original_sha_before=before, original_sha_after=hashes(), original_unchanged=True, offline_entrypoint='procsvc.bpmn_import.parse_bpmn + check; same function used by flows_api; actual GET catalog context', live_POST=0, Google_calls=0, token_reads=0, tests_repeated=0, generated_executable_copy=False, proposed_server_names=['google-meeting-calendar','google-meeting-drive'], registration_verified=False, google_read_verified=False, execution_ready=False)
(OUT/'preparation-result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'status':result['status'], 'import_problem_count':len(problems),'negative_missing_identity_checks':len(negative),'original_unchanged':True,'generated_executable_copy':False},ensure_ascii=False))
