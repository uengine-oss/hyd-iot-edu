"""Whole portal (index.html + every script in its order) against a fake API, for UI regression tests.

The portal page is served at http://<host>/ and every service port answers from `handlers`:
{(method, path): callable(query: dict, body) -> (status, json) | json | 'HOLD'}.
Unknown API paths answer 404 {"detail": "Not Found"} like FastAPI; SSE paths answer an empty stream.
'HOLD' keeps the request open until release() — used to press a button twice while a request is in flight.
host 'portal.test' is not a secure context (no crypto.randomUUID), like the portal opened by the instructor PC's IP.
"""
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[1]
WWW = ROOT / 'it/portal/www'
HOST = 'portal.test'
NOW = datetime.now(timezone.utc)


def iso(d):
    return d.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'


@pytest.fixture
def browser():
    pw = pytest.importorskip('playwright.sync_api')
    with pw.sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()


class FakePortal:
    def __init__(self, browser, handlers, width=1440, me=None, storage=None, host=HOST):
        self.host = host
        self.handlers = dict(handlers)
        self.posts, self.gets, self.errors, self.held = [], [], [], []
        self.page = browser.new_page(viewport={'width': width, 'height': 1000}, locale='ko-KR')
        self.page.on('pageerror', lambda e: self.errors.append(str(e)))
        init = {}
        if me:
            init['hyd.me'] = me
        init.update(storage or {})
        if init:
            self.page.add_init_script('(() => { const s = %s; for (const [k, v] of Object.entries(s)) localStorage.setItem(k, v); })()' % json.dumps(init))
        self.page.route('**/*', self.route)

    def open(self, hash_=''):
        self.page.goto(f'http://{self.host}/' + hash_)
        self.page.wait_for_function('window.hydInstances && window.hydInbox')

    def route(self, route):
        req = route.request
        u = urlsplit(req.url)
        if u.hostname == self.host and not u.port:
            path = u.path
            if path == '/':
                route.fulfill(content_type='text/html', body=(WWW / 'index.html').read_text(encoding='utf-8'))
                return
            f = WWW / path.lstrip('/')
            if f.is_file():
                route.fulfill(path=str(f))
                return
            route.fulfill(status=404, body='')
            return
        path = u.path
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        if path.endswith('/stream'):
            route.fulfill(status=200, content_type='text/event-stream', body='')
            return
        body = None
        if req.method in ('POST', 'PUT', 'DELETE'):
            try:
                body = req.post_data_json
            except Exception:
                body = req.post_data
            self.posts.append((req.method, path, body))
        else:
            self.gets.append((path, q))
        h = self.handlers.get((req.method, path))
        if h is None:
            route.fulfill(status=404, content_type='application/json', body=json.dumps({'detail': 'Not Found'}),
                          headers={'Access-Control-Allow-Origin': '*'})
            return
        out = h(q, body) if callable(h) else h
        if out == 'HOLD':
            self.held.append(route)
            return
        status, payload = out if isinstance(out, tuple) else (200, out)
        route.fulfill(status=status, content_type='application/json', body=json.dumps(payload),
                      headers={'Access-Control-Allow-Origin': '*'})

    def release(self, payload, status=200):
        for r in self.held:
            r.fulfill(status=status, content_type='application/json', body=json.dumps(payload), headers={'Access-Control-Allow-Origin': '*'})
        self.held.clear()

    def close(self):
        self.page.close()


PEOPLE = [{'id': 'user:kim-op', 'name': '김운전', 'roles': ['role:operator']},
          {'id': 'user:lee-prod', 'name': '이생산', 'roles': ['role:prod-mgr']}]

DEFN = {'id': 'demo_flow', 'name': '시험 흐름', 'version': '1',
        'activities': [{'id': 'task:agent', 'name': '에이전트 판단', 'type': 'serviceTask', 'tool': 'agent:judge', 'role': 'agent'},
                       {'id': 'task:escalate', 'name': '담당 확인', 'type': 'userTask', 'tool': 'formHandler:escalate', 'role': 'operator'}],
        'sequences': [{'id': 's1', 'source': 'task:agent', 'target': 'task:escalate'}], 'events': [], 'gateways': [],
        'roles': [{'name': 'operator', 'endpoint': 'role:operator'}]}


def instance(pid='inst-1', status='RUNNING', variables=None, approvals=None, workitems=None, events=None, current=None):
    inst = {'proc_inst_id': pid, 'proc_inst_name': f'HYD-01 쿨러 성능 저하 {pid}', 'status': status, 'proc_def_id': 'demo_flow', 'proc_def_version': '1',
            'start_date': iso(NOW - timedelta(minutes=2)), 'end_date': None, 'current_activity_ids': current or ['task:escalate'],
            'variables_data': variables or [{'key': 'asset', 'value': 'HYD-01', 'name': '설비'}], 'initial_variables': {}, 'variable_sources': {},
            'rework_generation': 0, 'flow_state': {}}
    wis = workitems if workitems is not None else [
        {'id': f'{pid}-agent', 'proc_inst_id': pid, 'activity_id': 'task:agent', 'activity_name': '에이전트 판단', 'status': 'DONE', 'agent_orch': 'cliagents', 'agent_mode': 'COMPLETE',
         'user_id': 'agent:judge', 'start_date': iso(NOW - timedelta(minutes=2)), 'end_date': iso(NOW - timedelta(minutes=1)), 'generation': 0, 'output': {}},
        {'id': f'{pid}-esc', 'proc_inst_id': pid, 'activity_id': 'task:escalate', 'activity_name': '담당 확인', 'status': 'IN_PROGRESS', 'tool': 'formHandler:escalate',
         'user_id': 'role:operator', 'start_date': iso(NOW - timedelta(minutes=1)), 'generation': 0}]
    return {'instance': inst, 'definition': DEFN, 'workitems': wis, 'events': events or [], 'approvals': approvals or [], 'reworks': []}


def esc_task(pid='inst-1'):
    return {'id': f'{pid}-esc', 'proc_inst_id': pid, 'activity_id': 'task:escalate', 'activity_name': '담당 확인', 'status': 'IN_PROGRESS',
            'tool': 'formHandler:escalate', 'user_id': 'role:operator', 'inputs': {'recovered': False},
            'form': {'fields_json': [{'key': 'note', 'text': '확인 메모', 'type': 'textarea'}, {'key': 'owner', 'text': '담당', 'type': 'text'}]}}


def todo_row(task):
    return {k: v for k, v in task.items() if k not in ('form', 'inputs')}


def instance_handlers(views, todo_rows, task_views, extra=None, moving_projection=True):
    """views: [instance view]; task_views: {task id: GET /api/todolist/{id} body}. graph-projections' knowledge.last_checked
    moves every call (the server's knowledge reconciler stamps it every 15 s) unless moving_projection=False."""
    counter = {'projections': 0}

    def projections(q, b):
        counter['projections'] += 1
        return {'pending': 0, 'items': [], 'worker_running': True,
                'knowledge': {'last_checked': time.time() if moving_projection else 1.0, 'last_error': None}}

    def todolist(q, b):
        rows = todo_rows() if callable(todo_rows) else todo_rows
        if q.get('proc_inst_id'):
            rows = [r for r in rows if r['proc_inst_id'] == q['proc_inst_id']]
        return rows
    h = {
        ('GET', '/api/process/mode'): {'mode': 'instance'},
        ('GET', '/api/instances'): lambda q, b: [dict(v['instance']) for v in views],
        ('GET', '/api/graph-projections'): projections,
        ('GET', '/api/process/definitions/demo_flow'): DEFN,
        ('GET', '/api/todolist'): todolist,
        ('GET', '/api/inbox/users'): PEOPLE,
        ('GET', '/api/inbox'): {'tasks': [], 'asked': [], 'roles': ['role:operator'], 'unread': 0, 'unassigned_roles': []},
        ('GET', '/api/inbox/notifications'): [],
        ('GET', '/api/inbox/assignments'): {'roles': [], 'people': PEOPLE},
        ('GET', '/api/events'): [],
    }
    for v in views:
        pid = v['instance']['proc_inst_id']
        h[('GET', f'/api/instances/{pid}')] = (lambda view: lambda q, b: view)(v)
        h[('GET', f'/api/instances/{pid}/graph')] = {'graph': None, 'projection': {'pending': 0}, 'cypher': '', 'params': {}}
    for tid, tv in task_views.items():
        h[('GET', f'/api/todolist/{tid}')] = (lambda body: lambda q, b: body)(tv)
    h.update(extra or {})
    return h, counter
