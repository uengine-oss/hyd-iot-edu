import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[2] / '.claude/worktrees/codex-portal-20261011/tests'))
import test_u1_task_detail as u
from test_failed_attempt_trace import *
u.RENDER=Path(__file__).with_name('render-system-progress-direct.js')
def test_direct_production_vm_consumer(world,tmp_path):
    test_the_task_panel_shows_each_failed_call_and_why(world,tmp_path)
