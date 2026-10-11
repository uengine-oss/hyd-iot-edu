"""The per-run Windows backend enables the chosen sandbox, never bypasses it."""
import pytest
from cliagents import ExecRequest, Permission
from worker import codex_provider


@pytest.mark.parametrize('platform', ['win32', 'linux', 'darwin'])
@pytest.mark.parametrize('permission', [Permission.WORKSPACE_WRITE, Permission.READ_ONLY])
@pytest.mark.parametrize('session', [None, 'prior-session'])
def test_windows_backend_is_scoped_to_workspace_write_and_preserves_isolation(monkeypatch, tmp_path, platform, permission, session):
    monkeypatch.setattr(codex_provider.sys, 'platform', platform)
    provider = codex_provider.WorkerCodexProvider()
    monkeypatch.setattr(provider, 'resolve_executable', lambda: 'codex')
    extra = ['--ignore-user-config', '--disable', 'apps', '-c', 'project_doc_max_bytes=0', '-c', 'mcp_servers={}']
    request = ExecRequest(prompt='-', workdir=str(tmp_path), permission=permission,
                          resume_session=session, extra_args=list(extra))
    argv = provider.exec_argv(request)
    assert request.extra_args == extra
    assert argv[argv.index('--sandbox') + 1] == ('workspace-write' if permission is Permission.WORKSPACE_WRITE else 'read-only')
    expected_backend = platform == 'win32' and permission is Permission.WORKSPACE_WRITE
    assert ('windows.sandbox="elevated"' in argv) is expected_backend
    assert '--ignore-user-config' in argv and 'mcp_servers={}' in argv and 'project_doc_max_bytes=0' in argv
    assert argv[argv.index('--disable') + 1] == 'apps'
    assert not any(flag in argv for flag in ('--yolo', '--dangerously-bypass-approvals-and-sandbox', '--full-auto', 'danger-full-access'))
    if session:
        assert argv[-3:] == ['resume', session, '-']
        assert argv.index('--sandbox') < argv.index('resume')
        if expected_backend:
            assert argv.index('windows.sandbox="elevated"') < argv.index('resume')
