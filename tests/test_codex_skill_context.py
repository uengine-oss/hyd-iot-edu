import hashlib

import pytest
from cliagents import ArtifactBundle, ExecEvent, ExecEventKind, registry
from procsvc.agents_store import skill_markdown
from worker import workspace
from worker.runner import Runner, _provided_skills
from worker.skill_context import inline_skills
from test_worker import _repo, _settings


SKILL = {'skill_name': 'pm-schedule-planning', 'description': '점검 계획',
         'content': '---\nname: pm-schedule-planning\n---\n\n# 점검 계획\n등록된 업무 도구로 점검 시기를 확인한다.\n'}
ANSWER = '{"cause":"c","failure_mode":"f","guide_card":{"value":1}}'


@pytest.mark.parametrize('mode', ['initial', 'correction', 'human_resume'])
def test_codex_gets_registered_rendered_skill_body_and_audit_hash_every_round(tmp_path, mode):
    repo, inst = _repo()
    repo.put_skill(SKILL)
    repo.attach_skill('sys:agent', SKILL['skill_name'])
    row = repo.list_workitems(proc_inst_id=inst['proc_inst_id'])[0]
    if mode == 'human_resume':
        repo.update_workitem(row | {'draft_status': 'FB_REQUESTED',
            'draft': {'_human_request': {'job_id': 'question', 'session_id': 'prior'}},
            'feedback': {'job_id': 'question', 'human_answer': '검토한 조건으로 진행'}})
    requests = []

    def execute(provider, request, env):
        requests.append(request)
        text = '형식 오류' if mode == 'correction' and len(requests) == 1 else ANSWER
        yield ExecEvent(kind=ExecEventKind.RESULT, text=text, session_id='session')

    runner = Runner(_settings(tmp_path, cli_agent='codex', max_inline_prompt_chars=1), repo,
                    exec_fn=execute, schema_prompt='schema', resolve_provider=lambda _: object())
    assert runner.poll_once() == 1
    expected = registry.get('codex').render(ArtifactBundle().add_skill(SKILL['skill_name'], skill_markdown(SKILL),
                                           description=SKILL['description']).artifacts[0])
    expected_sha = hashlib.sha256(expected.encode('utf-8')).hexdigest()
    assert len(requests) == (2 if mode == 'correction' else 1)
    for request in requests:
        body = request.prompt.split('<registered-skill>\n')[1].split('\n</registered-skill>')[0]
        assert body == expected and hashlib.sha256(body.encode('utf-8')).hexdigest() == expected_sha
        assert expected_sha in request.prompt
        assert '파일 읽기 없이' in request.prompt
        assert '업무에 해당하는 스킬을 먼저 읽고' not in request.prompt
        assert '먼저 그 파일을 Read 도구로' not in request.prompt
    if mode == 'human_resume':
        assert requests[0].resume_session == 'prior' and '담당자 응답' in requests[0].prompt
    started = next(e['data'] for e in repo.list_events(todo_id=row['id']) if e['event_type'] == 'task_started')
    entry = started['skills'][0]
    assert entry['sha256'] == expected_sha and entry['delivery'] == 'prompt' and entry['verified_registered_content']
    assert not any(e['data'].get('type') == 'skill_used' for e in repo.list_events(todo_id=row['id']))
    assert repo.get_workitem(row['id'])['status'] == 'SUBMITTED'


def test_codex_skill_mismatch_fails_closed_before_delivery(tmp_path):
    ws = workspace.for_run(tmp_path, 'task', tenant_id='hyd')
    workspace.provision(ws, agent_id='codex', constitution='', schema_prompt='', task={}, skills=[SKILL])
    entries = _provided_skills(ws, [SKILL], 'codex', activity_skills=[])
    (ws.path / entries[0]['path']).write_text('replaced body', encoding='utf-8')
    with pytest.raises(ValueError, match='해시'):
        inline_skills(ws, [SKILL], entries, 'codex')


def test_registered_skill_bytes_preserve_crlf_hash(tmp_path):
    skill = dict(SKILL, content=SKILL['content'].replace('\n', '\r\n'))
    ws = workspace.for_run(tmp_path, 'task', tenant_id='hyd')
    workspace.provision(ws, agent_id='codex', constitution='', schema_prompt='', task={}, skills=[skill])
    entries = _provided_skills(ws, [skill], 'codex', activity_skills=[])
    body = inline_skills(ws, [skill], entries, 'codex').split('<registered-skill>\n')[1].split('\n</registered-skill>')[0]
    assert hashlib.sha256(body.encode('utf-8')).hexdigest() == entries[0]['sha256']
    assert '\r\n' in body
