"""Pure, non-blocking diagnostics from saved MCP metadata; never call a server."""
from . import mcp_registry

LIMIT = '저장된 연결 검사 기준입니다. 현재 인증·실제 자료 접근·입력 형식은 호출할 때 다시 검사합니다.'


def diagnose(parsed, mapping, servers, checks, internal_names=()):
    names = {task['id']: task.get('name') or task['id'] for task in parsed.get('tasks', [])}
    rows = []
    for node, task in (mapping.get('tasks') or {}).items():
        if not isinstance(task, dict) or task.get('part') != 'svc:mcp-call':
            continue
        config = task.get('config') if isinstance(task.get('config'), dict) else {}
        server, tool = config.get('server'), config.get('tool')
        server = server if isinstance(server, str) else ''
        tool = tool if isinstance(tool, str) else ''
        status, reason = 'needs_check', '연결 서버와 도구 이름을 먼저 입력하세요.'
        if server and tool:
            if server in internal_names:
                status, reason = 'internal', '수업 기본 연결입니다. 도구와 입력 형식은 호출할 때 확인합니다.'
            elif server not in servers:
                status, reason = 'missing_server', '연결 서버가 등록되어 있지 않습니다. 도구 연결에서 서버를 준비하세요.'
            else:
                entry, record = servers[server], checks.get(server)
                state = mcp_registry.check_state(server, entry, record)
                if state['status'] != 'ok':
                    reason = {'never': '아직 연결 검사를 하지 않았습니다. 도구 연결에서 검사하세요.',
                              'stale': '검사 뒤 서버 설정이 바뀌었습니다. 연결 검사를 다시 하세요.',
                              'failed': '최근 연결 검사가 실패했습니다. 도구 연결에서 확인하세요.'}.get(state['status'], '연결 검사를 다시 확인하세요.')
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
