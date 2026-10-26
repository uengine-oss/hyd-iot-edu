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

    def test_real_stdio_managed_mcp_and_result_checker_inside_boundary(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        import threading
        from uuid import uuid4
        from worker import managed_tools, result_check
        calls, pending = [], {}
        meta = {'server':'enterprise', 'name':'spare_stock', 'description':'test student stock',
                'inputSchema':{'type':'object','properties':{'part':{'type':'string'}},
                               'required':['part'],'additionalProperties':False}}
        proposal = dict(meta,server='hyd-dmn',name='submit_decision',kind='proposal')
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                if self.headers.get('Authorization') != 'Bearer HydModel test-permit':
                    self.send_error(403); return
                if self.path.endswith('/tool-catalog'):
                    reply = {'tools':[meta,proposal]}
                elif self.path.endswith('/tool-request'):
                    calls.append(body)
                    ident = str(uuid4()); pending[ident] = body
                    reply = {'request_id':ident}
                elif self.path.endswith('/tool-result'):
                    request = pending[body['request_id']]
                    missing = request['arguments']['part'] == 'missing'
                    result = {'proposal_id':'DEC-TEST'} if request['tool']=='hyd-dmn/submit_decision' else {'available':7}
                    reply = {'state':'FAILED' if missing else 'DONE',
                             'result':{'error':'student source unavailable'} if missing else result}
                else:
                    self.send_error(404); return
                data = json.dumps(reply).encode()
                self.send_response(200); self.send_header('Content-Length', str(len(data)))
                self.end_headers(); self.wfile.write(data)
        server = ThreadingHTTPServer(('127.0.0.1',0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            config, _ = managed_tools.attach({'url':f'http://127.0.0.1:{server.server_port}',
                                             'token':'HydModel test-permit'}, self.work)
            config = result_check.attach(config, self.work, 10000)
            (self.work/'output').mkdir()
            (self.work/'output'/'result.json').write_text('{"proposal":{}}')
            script = '''import asyncio,json
from fastmcp import Client
async def main():
 async with Client('''+repr(config)+''') as client:
  tools=await client.list_tools()
  names=[t.name for t in tools]
  assert next(t for t in tools if t.name=='hyd-dmn_submit_decision').annotations.readOnlyHint is False
  stock=await client.call_tool('enterprise_spare_stock',{'part':'seal'})
  proposal=await client.call_tool('hyd-dmn_submit_decision',{'part':'seal'})
  checked=await client.call_tool('hyd-result_check_result_json',{})
  rejected=[]
  for args in ({'part':9},{'part':'missing'}):
   try:await client.call_tool('enterprise_spare_stock',args);rejected.append(False)
   except Exception:rejected.append(True)
  print(json.dumps({'names':names,'stock':json.loads(stock.content[0].text),'proposal':json.loads(proposal.content[0].text),
                    'check':json.loads(checked.content[0].text),'rejected':rejected}))
asyncio.run(main())
'''
            result = self.run_child(script)
            self.assertEqual(result['stock'], {'available':7})
            self.assertEqual(result['proposal'], {'proposal_id':'DEC-TEST'})
            self.assertTrue(result['check']['ok'])
            self.assertEqual(result['rejected'], [True, True])
            self.assertEqual([c['arguments'] for c in calls], [{'part':'seal'},{'part':'seal'},{'part':'missing'}])
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=3)

    def test_real_cli_disables_project_hooks_without_removing_assigned_skill(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        import threading
        class StopModel(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_POST(self):
                self.rfile.read(int(self.headers.get('Content-Length', 0)))
                data = b'{"type":"error","error":{"type":"invalid_request_error","message":"test endpoint; no model executed"}}'
                self.send_response(400); self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
        server = ThreadingHTTPServer(('127.0.0.1',0),StopModel)
        thread = threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            folder=self.work/'.claude'; folder.mkdir()
            skill=folder/'skills'/'approved-test';skill.mkdir(parents=True)
            (skill/'SKILL.md').write_text('---\nname: approved-test\ndescription: Instructor approved test skill\n---\nRead the supplied context.\n')
            command="/usr/local/bin/python -c \"from pathlib import Path;Path('hook-ran').write_text('hook')\""
            (folder/'settings.local.json').write_text(json.dumps({'hooks':{'SessionStart':[{'hooks':[{'type':'command','command':command}]}]}}))
            env=dict(os.environ,ANTHROPIC_API_KEY='test-only-fake-key',ANTHROPIC_BASE_URL=f'http://127.0.0.1:{server.server_port}',
                     CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1',DISABLE_TELEMETRY='1',DISABLE_AUTOUPDATER='1')
            for guarded in (False,True):
                (self.work/'hook-ran').unlink(missing_ok=True)
                args=['/usr/bin/claude','--print','No model execution; test startup only','--output-format','stream-json',
                      '--verbose','--model','coding','--max-turns','1']
                if guarded:args+=isolation.cli_args()
                tree=_ProcessTree(isolation.group_file(self.work))
                try:
                    proc=tree.spawn(args,cwd=str(self.work),env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                    output,error=proc.communicate(timeout=25)
                    self.assertNotEqual(proc.returncode,0) # Deliberate local HTTP 400, no model.
                    self.assertEqual((self.work/'hook-ran').exists(),not guarded)
                    if guarded:
                        events=[json.loads(line) for line in output.splitlines() if line.startswith('{')]
                        init=next(e for e in events if e.get('type')=='system' and e.get('subtype')=='init')
                        self.assertIn('approved-test',init['skills'])
                        self.assertEqual(set(init['tools']),{'Read','Glob','Grep','Write','Edit','Skill'})
                        self.assertNotIn('Bash',init['tools'])
                        self.assertNotIn('WebFetch',init['tools'])
                finally:tree.close()
        finally:
            server.shutdown();server.server_close();thread.join(timeout=3)
