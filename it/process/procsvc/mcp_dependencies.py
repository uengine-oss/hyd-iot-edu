"""흐름 단계 ↔ 도구 서버의 의존 판정 한 곳(저장된 정보만 읽는다 — 서버를 부르지 않는다).

  call_of      흐름 단계 하나가 부르는 (서버, 도구): 「승인 뒤 MCP 호출」 단계의 설정. 단계 설정 초안(part · config)과 등록된 정의(tool · service)
               두 모양을 같은 함수가 읽는다 — 흐름 검사(diagnose)와 도구 서버 지우기(steps_using)가 같은 판정을 쓴다.
  diagnose     가져온 흐름의 단계 설정이 가리키는 서버 · 도구가 지금 쓸 수 있는가(흐름 검사 화면).
  steps_using  이 도구 서버를 부르는 흐름 단계(도구 지도의 쓰임 · 지우기 전 확인). 흐름마다 최신 판본(다음 처리 건이 쓰는 판)과,
               옛 판본으로 진행 중인 처리 건의 판본을 본다.
"""
from . import mcp_registry

PART, TOOL = 'svc:mcp-call', 'mcp:call'      # effect_parts.PARTS 의 열쇠 · 그 부품의 tool(effect_parts.MCP_TOOL)
LIMIT = '저장된 연결 검사 기준입니다. 현재 인증·실제 자료 접근·입력 형식은 호출할 때 다시 검사합니다.'


def call_of(task, *, mapping):
    """흐름 단계 하나가 부르는 (서버 이름, 도구 이름) — 「승인 뒤 MCP 호출」 단계가 아니면 None. 적지 않은 칸은 빈 글자.
    mapping=True: 단계 설정 초안의 한 칸 {part, config}, False: 등록된 정의의 활동 {tool, service}."""
    if not isinstance(task, dict) or (task.get('part') != PART if mapping else task.get('tool') != TOOL):
        return None
    config = task.get('config' if mapping else 'service')
    config = config if isinstance(config, dict) else {}
    server, tool = config.get('server'), config.get('tool')
    return (server if isinstance(server, str) else '', tool if isinstance(tool, str) else '')


def steps_using(repo, tenant_id, names) -> dict:
    """도구 서버 이름 → 그 서버를 부르는 흐름 단계 [{definition, definition_name, version, activity_id, activity_name, tool, read_check,
    latest, running}]. latest = 그 흐름의 최신 판본(다음에 시작하는 처리 건이 이 단계에서 이 서버를 부른다), running = 그 판본으로 진행 중인
    처리 건 수. 최신도 아니고 진행 중인 처리 건도 없는 옛 판본은 싣지 않는다(다시 불릴 일이 없다)."""
    out = {n: [] for n in names}
    rows = repo.list_definitions(tenant_id)                    # 정의마다 오래된 판본부터 — 마지막 행이 최신
    latest = {r['id']: str(r['prod_version']) for r in rows}
    running = {}
    for inst in repo.list_instances(status='RUNNING', limit=None, tenant_id=tenant_id):
        key = (inst.get('proc_def_id'), str(inst.get('proc_def_version')))
        running[key] = running.get(key, 0) + 1
    for r in rows:
        version = str(r['prod_version'])
        is_latest, live = latest[r['id']] == version, running.get((r['id'], version), 0)
        if not is_latest and not live:
            continue
        raw = r.get('definition') or {}
        for a in raw.get('activities') or []:
            called = call_of(a, mapping=False)
            if called and called[0] in out:
                out[called[0]].append({'definition': r['id'], 'definition_name': r.get('name') or raw.get('processDefinitionName') or r['id'],
                                       'version': version, 'activity_id': a.get('id'), 'activity_name': a.get('name') or a.get('id'),
                                       'tool': called[1], 'read_check': (a.get('service') or {}).get('effect') is False,
                                       'latest': is_latest, 'running': live})
    return out


def diagnose(parsed, mapping, servers, checks, internal_names=()):
    names = {task['id']: task.get('name') or task['id'] for task in parsed.get('tasks', [])}
    rows = []
    for node, task in (mapping.get('tasks') or {}).items():
        called = call_of(task, mapping=True)
        if called is None:
            continue
        server, tool = called
        config = task['config'] if isinstance(task.get('config'), dict) else {}
        status, reason = 'needs_check', '도구 서버 이름과 도구 이름을 먼저 입력하세요.'
        if server and tool:
            if server in internal_names:
                status, reason = 'internal', '기본 제공 도구 서버입니다. 도구와 입력 형식은 호출할 때 확인합니다.'
            elif server not in servers:
                status, reason = 'missing_server', '이 이름의 도구 서버가 등록되어 있지 않습니다. [도구 연결]에서 먼저 등록하세요.'
            else:
                entry, record = servers[server], checks.get(server)
                state = mcp_registry.check_state(server, entry, record)
                if state['status'] != 'ok':
                    reason = {'never': '아직 연결 검사를 하지 않았습니다. [도구 연결]에서 검사하세요.',
                              'stale': '검사 뒤 서버 설정이 바뀌었습니다. 연결 검사를 다시 하세요.',
                              'failed': '최근 연결 검사가 실패했습니다. [도구 연결]에서 확인하세요.'}.get(state['status'], '연결 검사를 다시 확인하세요.')
                else:
                    saved = next((t for t in record.get('tools', []) if t.get('name') == tool), None)
                    if saved is None:
                        status, reason = 'missing_tool', '저장된 검사 목록에 이 도구가 없습니다. 도구 이름을 확인하고 다시 검사하세요.'
                    elif config.get('effect') is False and not mcp_registry.counts_as_read(saved, mcp_registry.confirmed_of(entry)):
                        status, reason = 'read_unconfirmed', '읽기 확인 단계에서 사용할 읽기 도구로 확인되지 않았습니다.'
                    else:
                        status, reason = 'saved_check', '저장된 검사에서 서버와 도구를 확인했습니다. 현재 연결 성공을 뜻하지 않습니다.'
        rows.append(dict(node_id=node, node_name=names.get(node, node), server=server, tool=tool, status=status, reason=reason))
    return dict(items=rows, attention_count=sum(r['status'] not in ('saved_check', 'internal') for r in rows), note=LIMIT,
                blocking=False, input_schema_verified=False, authentication_verified=False)


def for_repo(repo, tenant_id, parsed, mapping, internal_names=()):
    store = mcp_registry.store_for(repo)
    return diagnose(parsed, mapping, store.servers(tenant_id), store.checks(tenant_id), internal_names)
