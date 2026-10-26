"""Student-side current-state adapter for the managed tool exchange.

Reuse the existing MCP connection/schema/read-only checks. A queued call cannot
choose a URL, launch command, or credential. Configuration is pinned for the
run and read again before each call. The instructor's allowlist remains the
authorization boundary; this local gate is additional defence, not its substitute.
"""
import json

from . import mcp_check, mcp_registry, mcp_secrets


class ReadRouter:
    def __init__(self, repo, tenant, allowed_tools):
        self.repo, self.tenant = repo, tenant
        self.allowed = frozenset(allowed_tools)
        servers = mcp_registry.store_for(repo).servers(tenant)
        self.fingerprints = {name:mcp_registry.fingerprint(spec) for name,spec in servers.items()
                             if any(tool.startswith(name+'/') for tool in self.allowed)}

    @staticmethod
    def error(reason):
        return {'is_error':True,'result':{'error':reason}}

    def __call__(self, qualified, arguments):
        if qualified not in self.allowed or qualified.count('/') != 1 or not isinstance(arguments,dict):
            return self.error('이 실행에서 허용하지 않은 도구 조회입니다')
        name, tool = qualified.split('/')
        try:
            entry = mcp_registry.store_for(self.repo).servers(self.tenant).get(name)
            if not entry or self.fingerprints.get(name) != mcp_registry.fingerprint(entry):
                return self.error('조회 연결 설정이 바뀌었습니다. 실행 계약을 다시 확인하세요')
            confirmed = set()
            if name not in mcp_registry.BASE_SERVERS:
                gate = (entry.get('hyd') or {}).get('gate') or {}
                if gate.get('fingerprint') != self.fingerprints[name] or tool not in (gate.get('read_tools') or []):
                    return self.error('읽기 도구 연결 검사를 통과하지 않았습니다')
                confirmed = set(mcp_registry.confirmed_of(entry))
            spec, secrets = mcp_secrets.runtime_spec(self.repo,self.tenant,name,entry)
            # call() obtains fresh tools/list and validates inputSchema in that
            # same session. A changed tool becoming writable cannot slip through.
            response = mcp_secrets.redact(mcp_check.call(spec,tool,arguments,timeout=25,
                                                       max_chars=32000,confirmed=confirmed),secrets)
        except Exception:
            return self.error('학생 조회 연결을 사용할 수 없습니다. 현재 상태는 미확인입니다')
        if response.get('status') != 'ok' or not isinstance(response.get('result'),dict):
            return self.error('학생 도구 조회가 거절되거나 실패했습니다. 현재 상태는 미확인입니다')
        result = response['result']
        if result.get('truncated'):
            return self.error('도구 응답이 잘렸습니다. 조회 범위를 줄이거나 상세 페이지로 나누세요')
        try:
            data = json.loads(result['text']) if result.get('json') else result['text']
        except (ValueError,KeyError,TypeError):
            return self.error('학생 도구 응답 형식을 확인할 수 없습니다')
        return {'is_error':bool(result.get('is_error')),'result':data}
