"""Break only in this isolated Python process; product source stays unchanged."""
from pathlib import Path
import sys

T = Path('D:/work/study/hyd-iot-edu/.claude/worktrees/codex-portal-20261011')
sys.path[:0] = [str(T / 'common'), str(T / 'it/process')]
from procsvc import main
from procsvc.oauth_access_log import CallbackFilter
import pytest

main._health_state.__code__ = compile("lambda: {**state, 'ok': bool(state['kafka'])}", '<disabled-readiness>', 'eval').co_consts[0]
CallbackFilter.filter = lambda self, record: True
code = pytest.main(['-q', str(T / 'tests/test_process_health_readiness.py'), str(T / 'tests/test_mcp_oauth_deployment.py'), '-k', 'unavailable_runtime or callback_access_log'])
print('Deliberately disabled readiness and callback-log protection; expected pytest failure:', code == 1)
raise SystemExit(0 if code == 1 else 1)
