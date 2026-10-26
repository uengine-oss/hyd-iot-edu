"""Portable, reviewable agent candidates. Export/review never grants permission.

Only authored definitions, effective agent profiles and skill bodies travel;
tenant MCP connection settings, credentials and database metadata do not.
"""
from copy import deepcopy
from types import SimpleNamespace

from . import classroom_agents, definition_registry, mcp_check
from .classroom_authority import Denied, digest
from .classroom_tool_io import encoded

FORMAT = 'hyd-classroom-agent-v1'
MAX_BYTES = 1_048_576
PROFILE_FIELDS = ('id', 'username', 'name', 'role', 'goal', 'persona', 'model', 'tools', 'work_rules')


def export_candidate(runtime, approval):
    source, activity, role, bundle = classroom_agents.snapshot(runtime, approval)
    endpoint = role['endpoint']
    profile = None
    assigned = []
    if endpoint != 'sys:agent':
        row = runtime.repo.list_users([endpoint], runtime.tenant_id)[0]
        profile = {key: str(row.get(key) or '') for key in PROFILE_FIELDS}
        assigned = [row['skill_name'] for row in runtime.repo.list_agent_skills(runtime.tenant_id, endpoint)]
    mapping = runtime.repo.get_agent_map(runtime.tenant_id, approval['definition'], activity['id'])
    candidate = dict(format=FORMAT, tenant=runtime.tenant_id, approval=dict(approval, revision=digest(bundle)),
                     definition=deepcopy(source), profile=profile, agent_skills=assigned,
                     skills=deepcopy(bundle['agent']['skills']),
                     assignment=mapping['agent_id'] if mapping is not None else None)
    # Round-trip through a separate repository detects an incomplete export.
    review_candidate(candidate)
    return candidate


def review_candidate(candidate):
    from .procdb import MemoryRepo
    fields = {'format', 'tenant', 'approval', 'definition', 'profile', 'agent_skills', 'skills', 'assignment'}
    if not isinstance(candidate, dict) or set(candidate) != fields or candidate['format'] != FORMAT:
        raise Denied('에이전트 후보 명세 형식이 올바르지 않습니다')
    if len(encoded(candidate)) > MAX_BYTES:
        raise Denied('에이전트 후보 명세는 1 MiB 이하여야 합니다')
    tenant = candidate['tenant']
    if not isinstance(tenant, str) or not tenant.strip():
        raise Denied('후보 교육 공간이 필요합니다')
    source = deepcopy(candidate['definition'])
    definition_registry.validate_definition(source)
    if source != candidate['definition']:
        raise Denied('정규화된 등록 정의를 내보내야 합니다')
    approval = candidate['approval']
    if not isinstance(approval, dict) or approval.get('definition') != source['processDefinitionId'] or approval.get('version') != source['version']:
        raise Denied('후보 정의와 승인 대상 판본이 다릅니다')
    problem = mcp_check._argument_problem({'input_schema': approval.get('input_schema')}, {})
    if problem and problem['error_kind'] == 'input_schema':
        raise Denied('승인 입력 스키마가 유효하지 않습니다')
    repo = MemoryRepo()
    repo.upsert_proc_def(source, tenant)
    skills = candidate['skills']
    if not isinstance(skills, list) or any(not isinstance(s, dict) or set(s) != {'skill_name', 'description', 'content'}
                                         or any(not isinstance(v, str) for v in s.values()) for s in skills):
        raise Denied('스킬 후보 형식이 올바르지 않습니다')
    names = [s['skill_name'] for s in skills]
    assigned = candidate['agent_skills']
    if len(set(names)) != len(names) or not isinstance(assigned, list) or any(not isinstance(n, str) for n in assigned):
        raise Denied('스킬 이름이 중복되거나 배정 형식이 올바르지 않습니다')
    if len(set(assigned)) != len(assigned) or not set(assigned).issubset(names):
        raise Denied('배정 스킬의 본문이 없거나 중복됩니다')
    for skill in skills:
        repo.write_skill(dict(skill, tenant_id=tenant), create=True)
    profile = candidate['profile']
    if profile is not None:
        if not isinstance(profile, dict) or set(profile) != set(PROFILE_FIELDS) or any(not isinstance(v, str) for v in profile.values()):
            raise Denied('에이전트 프로필 형식이 올바르지 않습니다')
        repo.write_agent(dict(profile, tenant_id=tenant, is_agent=True, agent_type='agent'), assigned, create=True)
    elif assigned:
        raise Denied('프로필 없는 에이전트에 스킬을 배정할 수 없습니다')
    mapping = candidate['assignment']
    if mapping is not None:
        if not isinstance(mapping, str) or not mapping:
            raise Denied('담당 에이전트 연결이 올바르지 않습니다')
        repo.put_agent_map(dict(tenant_id=tenant, proc_def_id=approval['definition'], activity_id=approval['activity'], agent_id=mapping))
    runtime = SimpleNamespace(repo=repo, tenant_id=tenant)
    classroom_agents.checked(runtime, approval)
    bundle = classroom_agents.snapshot(runtime, approval)[3]
    if (profile['id'] if profile is not None else None) != bundle['agent']['agent_id']:
        raise Denied('실행하지 않는 프로필이 후보 명세에 포함되어 있습니다')
    if [s['skill_name'] for s in bundle['agent']['skills']] != names:
        raise Denied('실행하지 않는 스킬이 후보 명세에 포함되어 있습니다')
    return dict(fingerprint=digest(candidate), approval=deepcopy(approval), execution=bundle,
                assignment=mapping, permission_granted=False)


def _target_state(runtime, candidate):
    repo, tenant = runtime.repo, runtime.tenant_id
    if tenant != candidate['tenant']:
        raise Denied('후보와 강사 대상 교육 공간이 다릅니다')
    approval = candidate['approval']
    saved = repo.get_proc_def(approval['definition'], tenant, version=approval['version'])
    profile = candidate['profile']
    old = repo.list_users([profile['id']], tenant) if profile else []
    row = old[0] if old else None
    agent = None if row is None else dict(
        profile={k: str(row.get(k) or '') for k in PROFILE_FIELDS},
        is_agent=bool(row.get('is_agent')), origin=row.get('origin') or 'seed',
        skills=[s['skill_name'] for s in repo.list_agent_skills(tenant, profile['id'])])
    skills = {}
    for skill in candidate['skills']:
        existing = repo.get_skill(tenant, skill['skill_name'])
        skills[skill['skill_name']] = None if existing is None else dict(
            value={k: str(existing.get(k) or '') for k in ('skill_name','description','content')},
            origin=existing.get('origin') or 'seed')
    mapping = repo.get_agent_map(tenant, approval['definition'], approval['activity'])
    affected = sorted({r['user_id'] for r in repo.list_agent_skills(tenant)
                       if r['skill_name'] in skills})
    head = repo.get_proc_def(approval['definition'], tenant)
    return dict(definition=(saved or {}).get('definition'), agent=agent, skills=skills,
                assignment=None if mapping is None else mapping['agent_id'], affected_agents=affected,
                head=(head or {}).get('definition'), deployed_version=(head or {}).get('prod_version'))


def _changes(candidate, state):
    if state['definition'] is not None and state['definition'] != candidate['definition']:
        raise Denied('같은 정의 판본의 내용을 덮어쓸 수 없습니다')
    changes = []
    if state['definition'] is None:
        changes.append('definition')
    for skill in candidate['skills']:
        old = state['skills'][skill['skill_name']]
        if old is None or old['value'] != skill:
            if old and old['origin'] != 'user':
                raise Denied('기본 스킬은 후보 적용으로 덮어쓸 수 없습니다')
            changes.append('skill:'+skill['skill_name'])
    profile, old = candidate['profile'], state['agent']
    if profile is not None and (old is None or old['profile'] != profile or old['skills'] != candidate['agent_skills']):
        if old and (not old['is_agent'] or old['origin'] != 'user'):
            raise Denied('사람·기본 에이전트는 후보 적용으로 덮어쓸 수 없습니다')
        changes.append('agent')
    if candidate['assignment'] != state['assignment']:
        changes.append('assignment')
    return changes


def review_target(runtime, candidate):
    review = review_candidate(candidate)
    with runtime.repo.classroom_authoring_transaction(runtime.tenant_id):
        state = _target_state(runtime, candidate)
        changes = _changes(candidate, state)
        live = runtime.repo.classroom_has_live_work(runtime.tenant_id)
    return dict(review, target_fingerprint=digest(state), target=state, changes=changes,
                live_work=live, applicable=not (changes and live))


def apply_candidate(runtime, candidate, *, fingerprint, target_fingerprint):
    review = review_candidate(candidate)
    if review['fingerprint'] != fingerprint:
        raise Denied('검토한 후보와 적용 후보가 다릅니다')
    repo, tenant = runtime.repo, runtime.tenant_id
    with repo.classroom_authoring_transaction(tenant):
        state = _target_state(runtime, candidate)
        if digest(state) != target_fingerprint:
            raise Denied('검토 뒤 강사 대상 내용이 바뀌었습니다. 변경점을 다시 검토하세요')
        changes = _changes(candidate, state)
        if changes and repo.classroom_has_live_work(tenant):
            raise Denied('진행 중인 에이전트 작업이 있어 후보 변경을 적용할 수 없습니다')
        for skill in candidate['skills']:
            if 'skill:'+skill['skill_name'] in changes:
                repo.write_skill(dict(skill, tenant_id=tenant, origin='user'),
                                 create=state['skills'][skill['skill_name']] is None)
        if 'agent' in changes:
            repo.write_agent(dict(candidate['profile'], tenant_id=tenant, origin='user'),
                             candidate['agent_skills'], create=state['agent'] is None)
        if 'definition' in changes:
            repo.upsert_proc_def(candidate['definition'], tenant)
        if 'assignment' in changes:
            approval = candidate['approval']
            if candidate['assignment'] is None:
                repo.drop_agent_map(tenant, approval['definition'], approval['activity'])
            else:
                repo.put_agent_map(dict(tenant_id=tenant, proc_def_id=approval['definition'],
                    activity_id=approval['activity'], agent_id=candidate['assignment'], origin='user'))
        # Verify the real stored values before committing any import writes.
        if export_candidate(runtime, candidate['approval']) != candidate:
            raise Denied('서버에 저장한 실행 내용이 검토 후보와 다릅니다')
    return dict(fingerprint=fingerprint, approval=review['approval'], changes=changes, permission_granted=False)


def main():
    import argparse
    import json
    import os
    from pathlib import Path
    parser = argparse.ArgumentParser(description='학생 작성 에이전트 후보 내보내기·오프라인 검토 (권한 승인 없음)')
    parser.add_argument('action', choices=['export', 'review', 'review-target', 'apply'])
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--tenant')
    parser.add_argument('--approval', help='대상 정의·판본·단계·입력 스키마 JSON (revision은 pending 가능)')
    parser.add_argument('--fingerprint', help='검토한 후보 fingerprint')
    parser.add_argument('--target-fingerprint', help='검토한 강사 대상 target_fingerprint')
    args = parser.parse_args()
    try:
        path = Path(args.manifest)
        if args.action == 'export':
            from .procdb import PgRepo
            if not args.tenant or not args.approval:
                raise Denied('교육 공간과 승인 후보 입력이 필요합니다')
            approval = json.loads(Path(args.approval).read_text(encoding='utf8'))
            runtime = SimpleNamespace(repo=PgRepo(os.environ['SUPABASE_DSN']), tenant_id=args.tenant)
            candidate = export_candidate(runtime, approval)
            with path.open('x', encoding='utf8') as output:
                json.dump(candidate, output, ensure_ascii=False, indent=2)
            print(json.dumps({'fingerprint': digest(candidate), 'permission_granted': False}))
        else:
            with path.open('rb') as source:
                raw = source.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise Denied('후보 파일 크기 초과')
            candidate = json.loads(raw)
            if args.action == 'review':
                result = review_candidate(candidate)
            else:
                from .procdb import PgRepo
                if not args.tenant:
                    raise Denied('강사 대상 교육 공간을 지정해야 합니다')
                runtime = SimpleNamespace(repo=PgRepo(os.environ['SUPABASE_DSN']), tenant_id=args.tenant)
                result = (review_target(runtime, candidate) if args.action == 'review-target' else
                          apply_candidate(runtime, candidate, fingerprint=args.fingerprint,
                                          target_fingerprint=args.target_fingerprint))
            print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception:
        print('후보 처리 실패: 명세 형식·판본·배정·입력 스키마·DB 연결을 확인하세요.')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
