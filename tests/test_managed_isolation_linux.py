"""Run in the worker image with HYD_MANAGED_ISOLATION_TEST=1; no model calls."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from worker import bridge, managed_isolation as isolation
from worker.process_control import _ProcessTree


@unittest.skipUnless(sys.platform == 'linux' and os.getenv('HYD_MANAGED_ISOLATION_TEST') == '1',
                     'requires isolated Linux worker image')
class ManagedIsolation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.root.chmod(0o755)
        self.work = self.root / 'hyd' / 'run'
        self.work.mkdir(parents=True)
        self.secret = self.root / 'runtime.key'
        self.secret.write_text('test-only-world-readable-key')
        self.secret.chmod(0o644)
        self.env = patch.dict(os.environ, HYD_MANAGED_MODEL_REQUIRED='1', CLIAGENTS_WORKSPACE_ROOT=str(self.root))
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def run_child(self, script):
        tree = _ProcessTree(isolation.group_file(self.work))
        try:
            proc = tree.spawn([sys.executable, '-c', script], cwd=str(self.work), env=dict(os.environ),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            output, error = proc.communicate(timeout=20)
            self.assertEqual(proc.returncode, 0, error)
            return json.loads(output)
        finally:
            tree.close()

    def test_secrets_other_runs_parent_environment_and_control_record_denied(self):
        other = self.work.parent / 'other'
        other.mkdir()
        (other / 'data').write_text('another scope')
        record = isolation.group_file(self.work)
        paths = [str(self.secret), str(other / 'data'), f'/proc/{os.getpid()}/environ', str(record)]
        result = self.run_child('''import json,os
from pathlib import Path
results=[]
for p in '''+repr(paths)+''':
 try: Path(p).read_bytes(); results.append('READABLE')
 except PermissionError: results.append('denied')
Path('result.txt').write_text('valid output')
print(json.dumps({'reads':results,'uid':os.getuid(),'groups':os.getgroups(),
 'status':Path('/proc/self/status').read_text(),'output':Path('result.txt').read_text()}))
''')
        self.assertEqual(result['reads'], ['denied'] * 4)
        self.assertEqual(result['uid'], isolation.UID)
        self.assertEqual(result['groups'], [])
        self.assertIn('NoNewPrivs:\t1', result['status'])
        self.assertIn('CapBnd:\t0000000000000000', result['status'])
        self.assertEqual(result['output'], 'valid output')

    def test_resume_keeps_own_output_and_isolates_cli_config(self):
        env = bridge.runtime_env(self.work, 'claude-code', False)
        self.assertIn('CLAUDE_CONFIG_DIR', env)
        self.run_child("from pathlib import Path;Path('state').write_text('resume');print('{}')")
        self.assertEqual(self.run_child("import json;from pathlib import Path;print(json.dumps(Path('state').read_text()))"), 'resume')

    def test_existing_link_rejected_before_process_creation(self):
        (self.work / 'escape').symlink_to(self.secret)
        with self.assertRaisesRegex(RuntimeError, '링크'):
            isolation.prepare(['true'], {'cwd':str(self.work), 'env':{}})

    def test_cli_cannot_create_symlink_or_write_outside_workspace(self):
        result=self.run_child('''import json
from pathlib import Path
r=[]
for action in (lambda:Path('escape').symlink_to('''+repr(str(self.secret))+'''),lambda:Path('''+repr(str(self.secret))+''').write_text('changed')):
 try:action();r.append('ALLOWED')
 except PermissionError:r.append('denied')
print(json.dumps(r))''')
        self.assertEqual(result, ['denied', 'denied'])

    def test_failed_landlock_setup_does_not_execute_command(self):
        argv, kwargs = isolation.prepare([sys.executable, '-c', "print('UNSAFE_EXECUTION')"],
                                         {'cwd':str(self.work), 'env':dict(os.environ)})
        argv[argv.index('--landlock-rule')+1] = 'path-beneath:read-file:/nonexistent-isolation-rule'
        result = subprocess.run(argv, **kwargs, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('UNSAFE_EXECUTION', result.stdout)

    def test_real_cli_starts_inside_boundary_without_model_request(self):
        result = self.run_child("import json,subprocess;print(json.dumps(subprocess.check_output(['/usr/bin/claude','--version'],text=True)))")
        self.assertIn('Claude Code', result)

    def test_cancellation_kills_isolated_child_and_removes_private_record(self):
        record = isolation.group_file(self.work)
        tree = _ProcessTree(record)
        proc = tree.spawn([sys.executable, '-c', "import time;print('ready',flush=True);time.sleep(60)"],
                          cwd=str(self.work), env=dict(os.environ), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(proc.stdout.readline().strip(), 'ready')
            self.assertTrue(record.exists())
        finally:
            tree.close()
            proc.communicate(timeout=5)
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse(record.exists())
