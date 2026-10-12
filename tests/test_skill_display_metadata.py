"""Human-readable names travel with the exact provided bytes, without changing canonical skill keys."""
import hashlib

from cliagents import ExecEvent, ExecEventKind
from procsvc.agents_store import AgentSettings
from worker import events
from test_b1_agent_authoring import env


def test_provided_title_and_read_request_keep_the_exact_execution_snapshot():
    old_text = '---\nname: pm-planning\n---\n\n# 정기 점검 계획\n절차 원문\n'
    stored = {'skill_name': 'pm-planning', 'content': '# 나중에 수정된 제목', 'description': '당시 설명'}
    snapshot = events.skill_entry(stored, text=old_text, path='.agents/skills/pm-planning/SKILL.md', source='agent')
    assert snapshot['title'] == '정기 점검 계획'
    assert snapshot['name'] == 'pm-planning'
    assert snapshot['sha256'] == hashlib.sha256(old_text.encode('utf-8')).hexdigest()
    tracker = events.SkillReads([snapshot])
    stored['content'] = '# 또 바뀐 현재 제목'
    request = tracker.on_tool_start(ExecEvent(kind=ExecEventKind.TOOL_START, tool='Read',
                                             tool_input={'file_path': snapshot['path']}, tool_use_id='read-one'))[0]
    assert request.data['title'] == '정기 점검 계획'
    assert request.data['skill'] == 'pm-planning'
    assert request.data['sha256'] == snapshot['sha256']
    assert '읽기' in request.data['content'] and '요청' in request.data['content']
    assert tracker.on_tool_start(ExecEvent(kind=ExecEventKind.TOOL_START, tool='Read',
                                          tool_input={'file_path': snapshot['path']}, tool_use_id='again')) == []


def test_legacy_and_unprovided_reads_do_not_invent_historical_titles():
    legacy = {'name': 'pm-planning', 'sha256': 'a'*64, 'version': 'a'*12, 'source': 'agent'}
    tracker = events.SkillReads([legacy])
    for name, known in [('pm-planning', True), ('never-provided', False)]:
        request = tracker.on_tool_start(ExecEvent(kind=ExecEventKind.TOOL_START, tool='Read',
            tool_input={'file_path': f'.agents/skills/{name}/SKILL.md'}))[0]
        assert request.data['known'] is known
        assert 'title' not in request.data


def test_current_settings_and_authoring_options_supply_titles_without_changing_keys(env):
    client, rt = env
    skill = {'skill_name': 'pm-planning', 'description': '설명', 'content': '# 정기 점검 계획\n원문', 'origin': 'user'}
    rt.repo.put_skill(skill)
    settings = AgentSettings(agent_id='agent:test', profile={'username': '점검 담당'}, skills=[skill])
    summary = settings.summary()
    assert summary['skills'] == ['pm-planning']
    assert summary['skill_labels'] == [{'name': 'pm-planning', 'title': '정기 점검 계획'}]
    result = client.get('/api/agent-authoring/options')
    assert result.status_code == 200
    option = next(x for x in result.json()['skills'] if x['skill_name'] == 'pm-planning')
    assert option['title'] == '정기 점검 계획'
    assert option['description'] == '설명'
