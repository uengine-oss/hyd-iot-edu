from copy import deepcopy

import pytest

from procsvc import classroom_manifest as manifest
from procsvc.classroom_authority import Denied
from test_classroom_agents import approved
from test_instances import rt  # noqa: F401


def candidate(runtime):
    approval = approved(runtime)
    runtime.repo.write_skill(dict(tenant_id=runtime.tenant_id, skill_name='student-check',
                                 description='확인', content='실제 상태를 조회한다'), create=True)
    runtime.repo.write_agent(dict(id='agent:student', tenant_id=runtime.tenant_id, username='학생 작성',
                                 is_agent=True, goal='인계안 작성', model='luna', tools='enterprise',
                                 email='excluded@example.invalid', api_key='excluded-secret'), ['student-check'], create=True)
    runtime.repo.put_agent_map(dict(tenant_id=runtime.tenant_id, proc_def_id=approval['definition'],
                                   activity_id=approval['activity'], agent_id='agent:student'))
    return manifest.export_candidate(runtime, approval)


def test_candidate_roundtrip_contains_actual_assignment_and_no_database_metadata(rt):
    runtime,_ = rt
    value = candidate(runtime)
    review = manifest.review_candidate(value)
    assert value['assignment'] == 'agent:student'
    assert review['execution']['agent']['agent_id'] == 'agent:student'
    assert review['execution']['agent']['skills'][0]['content'] == '실제 상태를 조회한다'
    assert review['permission_granted'] is False
    assert 'excluded' not in str(value)
    assert not runtime.repo.instances
    changed = deepcopy(value)
    changed['profile']['goal'] = '다른 행동'
    with pytest.raises(Denied, match='판본'):
        manifest.review_candidate(changed)


@pytest.mark.parametrize('change', ['assignment', 'skill', 'extra', 'schema', 'version', 'unused'])
def test_candidate_rejects_changed_or_unreviewable_execution(rt, change):
    runtime,_ = rt
    value = candidate(runtime)
    if change == 'assignment': value['assignment'] = None
    elif change == 'skill': value['skills'][0]['content'] = '다른 지시'
    elif change == 'extra': value['mcp_credentials'] = 'forbidden'
    elif change == 'schema': value['approval']['input_schema']['type'] = 'not-a-type'
    elif change == 'version': value['approval']['version'] = 'other'
    elif change == 'unused': value['skills'].append(dict(skill_name='unused', description='', content='unused'))
    with pytest.raises((Denied, ValueError)):
        manifest.review_candidate(value)
