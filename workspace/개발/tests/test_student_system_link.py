"""학생이 자기 시스템을 연결하는 길 — 처음부터 끝까지(모듈 하나가 아니라 길 하나를 잰다: 도구 서버 등록 → 에이전트 → 역할 → 흐름 → 승인 → 실행).

이 제품이 수업 사례 밖으로 넓어지는 길은 이것 하나다(스펙 「나침반」): 설비를 넣는 것이 아니라 학생의 시스템을 도구 서버로 연결하고, 쓰기는
사람 승인 뒤 「승인 뒤 MCP 호출」 단계로만 한다. 사례는 유압 설비와 무관한 「사내 비품 재주문」이다.

실제인 것: process 앱의 HTTP 경로(포털과 같은 라우트 · 같은 수업 경계 문지기), 실제 업무 DB, 실제 지식 그래프, 실제 엔진 폴링, 실제 AI 워커
(worker.runner.Runner) · 수업 관문.
시스템 밖이라 대체한 것: 학생의 시스템(작은 HTTP MCP 서버 — 받은 호출을 남긴다), Claude Code CLI(StudentCli — 실제 AI 를 부르지 않는다. 작업 폴더의
도구 서버 설정과 워커가 준 허용 · 금지 목록대로만 도구를 부른다), 강의 중계(FakeRelay).
단계 열기: 실제 스택은 강사 서명 키가 있어야 「제한 없이 쓰는 단계(PBL)」가 열린다. 시험은 시험용 키로 서명한 단계 선언을 학생 PC 와 같은
함수(course_policy.load_phase — 서명 · 기한 검사)로 읽어 이 process 의 판정 표에 넣는다.
"""
import base64
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
import pytest

from conftest import OPERATOR, STUDENT_HOST, TENANT, Served, _run_async
from procsvc import agent_authoring as A, approval_part, course_policy as cp, mcp_registry
from procsvc.bpmn_store import FlowStore

ME = OPERATOR['by']
SERVER = 'my-stock'
ROLE_NAME, ROLE_ID = '총무 담당', 'role:office-admin'
ITEM = 'A4 용지'
READ, UNMARKED, WRITE, WRITE_FAILS = 'find_stock', 'supplier_of', 'place_order', 'book_order'


class StockSystem:
    """학생의 시스템 자리(사내 비품 재고) — HTTP MCP 서버 하나. 읽기 표시 도구 · 표시 없는 조회 도구 · 쓰기 도구를 내고 받은 호출을 남긴다."""

    def __init__(self):
        from fastmcp import FastMCP
        from mcp.types import ToolAnnotations
        self.calls, self.orders = [], []
        self.on_hand, self.reorder_point = {ITEM: 3}, 5
        app = FastMCP('사내 비품 재고')

        @app.tool(name=READ, annotations=ToolAnnotations(readOnlyHint=True))
        def find_stock(item: str) -> dict:
            """품목의 지금 재고와 재주문 기준을 돌려준다"""
            self.calls.append((READ, {'item': item}))
            return {'item': item, 'on_hand': self.on_hand.get(item, 0), 'reorder_point': self.reorder_point}

        @app.tool(name=UNMARKED)
        def supplier_of(item: str) -> dict:
            """품목의 거래처를 돌려준다(읽기 표시 없음)"""
            self.calls.append((UNMARKED, {'item': item}))
            return {'item': item, 'supplier': '문구나라'}

        @app.tool(name=WRITE, annotations=ToolAnnotations(readOnlyHint=False))
        def place_order(item: str, qty: int, idempotency_key: str = '') -> dict:
            """품목을 주문한다"""
            self.calls.append((WRITE, {'item': item, 'qty': qty, 'idempotency_key': idempotency_key}))
            order = {'order_id': f'ORD-{len(self.orders) + 1:03d}', 'item': item, 'qty': qty}
            self.orders.append(order)
            return order

        @app.tool(name=WRITE_FAILS, annotations=ToolAnnotations(readOnlyHint=False))
        def book_order(item: str, qty: int) -> dict:
            """품목을 주문한다 — 요청을 받은 뒤 오류로 끝난다(같은 호출을 알아볼 열쇠를 받지 않는 도구)"""
            self.calls.append((WRITE_FAILS, {'item': item, 'qty': qty}))
            raise RuntimeError('재고 시스템 내부 오류')
        self.served = Served(app.http_app(path='/mcp'), host=STUDENT_HOST)      # 학생 서버는 루프백이 아닌 이 PC 주소
        self.url = self.served.url + '/mcp'

    def called(self, name):
        return [args for tool, args in self.calls if tool == name]


@pytest.fixture(scope='module')
def system():
    s = StockSystem()
    yield s
    s.served.close()


class StudentCli:
    """Claude Code 자리. 실제 CLI 가 하는 일만 한다: 작업 폴더 .mcp.json 의 서버에, 워커가 준 미리 허용 목록(--allowedTools)에 있고 금지 목록
    (--disallowedTools)에 없는 도구만 부른다(그 밖의 도구는 부르지 못하고 refused 에 남는다). 모델 호출 자리(수업 관문)를 한 번 지나고, 읽은 재고로
    주문안을 만들어 결과 파일에 쓴다. wants = 이 「AI」가 부르려는 도구 — 쓰기 도구까지 욕심내는 에이전트를 흉내 낸다."""
    accepts_check_stop = True

    def __init__(self, wants=(READ, WRITE)):
        self.wants, self.requests, self.called, self.refused = wants, [], [], []

    @staticmethod
    def _flag(args, name):
        return [t for t in args[args.index(name) + 1].split(',') if t]

    @staticmethod
    def _call(entry, tool, arguments):
        from fastmcp import Client
        from fastmcp.client.transports import StreamableHttpTransport

        async def go():
            async with Client(StreamableHttpTransport(entry['url'], headers=entry.get('headers') or {})) as client:
                return (await client.call_tool(tool, arguments)).structured_content
        return _run_async(go())

    def __call__(self, provider, request, env, *, check_stop=None):
        import urllib.request
        from cliagents import ExecEvent, ExecEventKind
        self.requests.append(request)
        session = str(uuid.uuid4())
        body = json.dumps({'model': request.model, 'max_tokens': 64, 'messages': [{'role': 'user', 'content': '다음 단계'}]}).encode()
        with urllib.request.urlopen(urllib.request.Request(env['ANTHROPIC_BASE_URL'] + '/v1/messages', data=body, method='POST', headers={
                'x-api-key': env['ANTHROPIC_API_KEY'], 'content-type': 'application/json'}), timeout=15) as response:
            response.read()
        servers = json.loads((Path(request.workdir) / '.mcp.json').read_text(encoding='utf8'))['mcpServers']
        allowed, denied = self._flag(request.extra_args, '--allowedTools'), self._flag(request.extra_args, '--disallowedTools')
        stock = None
        for tool in self.wants:
            name = f'mcp__{SERVER}__{tool}'
            if SERVER not in servers or name not in allowed or name in denied:
                self.refused.append(name)
                continue
            use = str(uuid.uuid4())
            args = {'item': ITEM} if tool != WRITE else {'item': ITEM, 'qty': 99}
            yield ExecEvent(kind=ExecEventKind.TOOL_START, tool=name, tool_input=args, tool_use_id=use, session_id=session)
            out = self._call(servers[SERVER], tool, args)
            self.called.append(name)
            stock = out if tool == READ else stock
            yield ExecEvent(kind=ExecEventKind.TOOL_END, tool=name, tool_output=json.dumps(out, ensure_ascii=False), tool_use_id=use, session_id=session)
        if stock is None:
            yield ExecEvent(kind=ExecEventKind.RESULT, is_error=True, session_id=session, text='재고를 읽을 도구가 없습니다')
            return
        need = stock['reorder_point'] - stock['on_hand']
        proposal = {'options': [{'slot': 'A', 'qty': need, 'reason': f"재고 {stock['on_hand']}개 — 재주문 기준 {stock['reorder_point']}개까지"},
                                {'slot': 'B', 'qty': need * 2, 'reason': '두 달치'}], 'recommended': 'A'}
        target = Path(request.workdir) / 'output' / 'result.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({'proposal': proposal}, ensure_ascii=False), encoding='utf8')
        yield ExecEvent(kind=ExecEventKind.RESULT, session_id=session, text='주문안을 냈습니다')


def _bpmn(process_id, name, with_agent):
    agent = '<bpmn:userTask id="T_agent" name="재고 확인 · 주문안 작성"/>' if with_agent else ''
    first = ('<bpmn:sequenceFlow id="F1" sourceRef="Start" targetRef="T_agent"/><bpmn:sequenceFlow id="F2" sourceRef="T_agent" targetRef="T_ok"/>'
             if with_agent else '<bpmn:sequenceFlow id="F1" sourceRef="Start" targetRef="T_ok"/>')
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" id="D_{process_id}"><bpmn:process id="{process_id}" name="{name}">
  <bpmn:startEvent id="Start" name="재주문 요청"/>{agent}
  <bpmn:userTask id="T_ok" name="주문 승인"/>
  <bpmn:exclusiveGateway id="G_ok" name="승인?"/>
  <bpmn:serviceTask id="T_order" name="비품 주문 넣기"/>
  <bpmn:endEvent id="E_done" name="주문 완료"/>
  <bpmn:endEvent id="E_no" name="반려"/>
  {first}
  <bpmn:sequenceFlow id="F3" sourceRef="T_ok" targetRef="G_ok"/>
  <bpmn:sequenceFlow id="F_yes" name="승인" sourceRef="G_ok" targetRef="T_order"/>
  <bpmn:sequenceFlow id="F_no" name="반려" sourceRef="G_ok" targetRef="E_no"/>
  <bpmn:sequenceFlow id="F4" sourceRef="T_order" targetRef="E_done"/>
</bpmn:process></bpmn:definitions>'''


def _mapping(name, agent=None, arguments=None, tool=WRITE):
    """단계 설정: (에이전트 단계 — 내 에이전트) → 사람 승인(내 역할) → 승인 뒤 MCP 호출(내 서버의 쓰기 도구)."""
    fields = [{'key': 'item', 'text': '품목', 'type': 'text'}] + ([] if agent else [{'key': 'proposal', 'text': '주문안', 'type': 'object'}])
    tasks = {'T_ok': {'part': 'human:approve', 'role': ROLE_NAME, 'config': {'options': 'proposal.options', 'recommended': 'proposal.recommended'}},
             'T_order': {'part': 'svc:mcp-call', 'inputs': ['item'],
                         'config': {'server': SERVER, 'tool': tool, 'arguments': arguments or {'item': '{item}', 'qty': '{approved_option.qty}'}}}}
    if agent:
        tasks['T_agent'] = {'part': 'agent', 'agent': agent, 'inputs': ['item'],
                            'instruction': '품목의 재고를 조회해 재주문 기준까지 채우는 주문안을 낸다. 주문은 하지 않는다.',
                            'outputs': [{'key': 'proposal', 'text': '주문안', 'type': 'object'}]}
    return {'name': name, 'start': {'kind': 'human', 'fields': fields}, 'tasks': tasks,
            'flows': {'F_yes': {'var': 'approval', 'op': '==', 'value': approval_part.APPROVE}, 'F_no': {'default': True}}, 'lanes': {}, 'timers': {}}


def _clean(world):
    """학생이 만든 것과 이 시험의 처리 건을 지운다(시험 자리를 다음 시험에 넘기기 전에)."""
    with psycopg.connect(world.dsn, autocommit=True) as db:      # 끝나지 않은 이 시험의 처리 건과 그 열린 단계를 닫는다(제품의 [닫기]가 하는 일의 결과)
        db.execute("UPDATE todolist SET status='CANCELLED' WHERE tenant_id=%s AND status IN ('TODO','IN_PROGRESS','SUBMITTED','PENDING') "
                   "AND proc_inst_id IN (SELECT proc_inst_id FROM bpm_proc_inst WHERE proc_def_id LIKE 'office_%%')", (TENANT,))
        db.execute("UPDATE bpm_proc_inst SET status='CANCELLED' WHERE tenant_id=%s AND proc_def_id LIKE 'office_%%' AND status='RUNNING'", (TENANT,))
    store = FlowStore(world.rt.repo, TENANT)
    for did in {v['id'] for v in store.versions()} | {d['proc_def_id'] for d in store.drafts()}:
        if did.startswith('office_'):
            out = store.reset(did)
            for pid in out['projection_instances']:
                world.rt._project({'proc_inst_id': pid})
    world.rt.cleanup_removed_definitions()
    A.reset(world.rt, by=ME)
    mcp_registry.reset(mcp_registry.store_for(world.rt.repo), TENANT)


@pytest.fixture
def pbl(world, tmp_path):
    """「제한 없이 쓰는 단계(PBL)」를 강사 도구와 같은 길로 연다: 시험용 키로 서명한 단계 선언 파일 → load_phase(서명 · 기한 검사) → 이 process 의
    판정 표. 판정 표(course_policy.Policy)는 process 가 켜질 때 선언을 읽어 든다 — 시험은 켜진 process 에 그 읽은 값을 넣는다."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    private = Ed25519PrivateKey.generate()
    public = base64.urlsafe_b64encode(private.public_key().public_bytes_raw()).decode().rstrip('=')
    path = tmp_path / 'course_phase.json'
    payload = {'contract': cp.PHASE_CONTRACT, 'phase': 'pbl', 'note': '연결 길 시험',
               'expires': (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()}
    path.write_text(json.dumps(cp.sign_phase(payload, private), ensure_ascii=False), encoding='utf8')
    policy = world.main.app.state.course
    before = policy._declared
    _clean(world)
    policy._declared = cp.load_phase(path, keys=(public,))
    yield policy
    policy._declared = before
    _clean(world)


def _ok(result, want=200):
    status, body = result
    assert status == want, body
    return body


@pytest.fixture
def linked(world, pbl, system):
    """포털이 하는 차례 그대로(HTTP): 내 도구 서버 등록 → 표시 없는 조회 도구를 읽기로 확인 → 내 스킬 · 내 에이전트(그 서버를 붙임) → 내 역할."""
    system.calls.clear()
    system.orders.clear()
    server = _ok(world.api('POST', '/api/mcp/servers', {'name': SERVER, 'url': system.url, 'description': '사내 비품 재고', 'by': ME}), 201)
    _ok(world.api('POST', f'/api/mcp/servers/{SERVER}/read-confirm', {'tool': UNMARKED, 'by': ME, 'reason': '거래처 이름만 돌려준다'}))
    _ok(world.api('POST', '/api/skills', {'skill_name': 'stock-check', 'description': '비품 재고를 확인해 주문안을 쓴다',
                                          'content': '# 비품 재고 확인\n1. find_stock 으로 재고를 읽는다\n2. 재주문 기준까지의 수량을 낸다', 'by': ME}), 201)
    agent = _ok(world.api('POST', '/api/agents', {'name': '비품 재고 에이전트', 'goal': '재고를 조회해 주문안을 낸다', 'tools': [SERVER],
                                                  'skills': ['stock-check'], 'by': ME}), 201)
    role = _ok(world.api('POST', '/api/roles', {'name': ROLE_NAME, 'key': ROLE_ID.split(':', 1)[1], 'by': ME}), 201)
    return {'server': server, 'agent': agent['id'], 'role': role}


def _register(world, did, name, **mapping):
    """흐름 가져오기 → 검사 → 판본 등록(포털과 같은 세 요청). 돌려줌 = (검사 결과, 판본)."""
    xml = _bpmn(did, name, with_agent=bool(mapping.get('agent')))
    _ok(world.api('POST', '/api/flows/import', {'xml': xml, 'file_name': f'{did}.bpmn', 'definition_id': did}))
    checked = _ok(world.api('POST', f'/api/flows/{did}/check', {'mapping': _mapping(name, **mapping)}))
    if not checked['check']['ok']:
        return checked, None
    made = _ok(world.api('POST', f'/api/flows/{did}/register', {'mapping': _mapping(name, **mapping), 'by': ME}), 201)
    return checked, made['version']


def _start(world, did, version, **values):
    inst = _ok(world.api('POST', '/api/instances/start', {'definition_id': did, 'version': version, 'event_id': 'office:' + uuid.uuid4().hex,
                                                          'variables': {'item': ITEM, **values}}))
    world.poll()
    return inst['proc_inst_id']


def _approve(world, pid, decision, option=None, reason=''):
    row = world.row(pid, 'T_ok', 'IN_PROGRESS')
    return world.api('POST', f"/api/todolist/{row['id']}/approve", {'decision': decision, 'option': option, 'by': ME, 'role': ROLE_ID, 'reason': reason})


PROPOSAL = {'options': [{'slot': 'A', 'qty': 2, 'reason': '재주문 기준까지'}], 'recommended': 'A'}


# ---------------------------------------------------------------- 길의 문: 만들 수 없는 단계 ↔ 만들 수 있는 단계
def test_제공된_것만_쓰는_단계에서는_내_서버를_만들지도_지우지도_못하고_저장된_서버의_검사와_읽기_도구_써_보기는_된다(world, system):
    """도구 서버는 만들 수 있는 단계에서만 지울 수 있다(사용자 2026-11-14) — 전에는 만들 수는 없는데 지우기 · 되돌리기는 열려 있어, 지우면
    되살릴 길이 없었다. 까닭 문장은 무엇이 언제 열리는지 말한다."""
    _clean(world)
    store = mcp_registry.store_for(world.rt.repo)
    mcp_registry.register(store, TENANT, {'name': SERVER, 'url': system.url}, by=ME)     # 앞선 단계(PBL)에서 만들어 둔 서버
    try:
        closed = cp.Policy.ACTIONS['tool_servers.register']
        for method, path, body in (('POST', '/api/mcp/servers', {'name': 'other', 'url': system.url, 'by': ME}),
                                   ('DELETE', f'/api/mcp/servers/{SERVER}?by={ME}', None),
                                   ('POST', '/api/mcp/reset', {'by': ME})):
            assert world.api(method, path, body) == (403, {'detail': closed}), (method, path)
        assert SERVER in store.servers(TENANT)
        assert _ok(world.api('POST', f'/api/mcp/servers/{SERVER}/check', {'by': ME}))['check']['status'] == 'ok'
        system.calls.clear()
        tried = _ok(world.api('POST', f'/api/mcp/servers/{SERVER}/tools/{READ}/call', {'arguments': {'item': ITEM}, 'by': ME}))
        assert system.called(READ) == [{'item': ITEM}] and '"on_hand":3' in tried['result']['text'].replace(' ', '')
    finally:
        _clean(world)


# ---------------------------------------------------------------- 길 전체: 등록 → 에이전트 → 역할 → 흐름 → 승인 → 실행
def test_내_도구_서버는_연결_검사를_통과해야_등록되고_읽기_도구만_에이전트_몫이_된다(world, linked, system):
    gate = linked['server']['gate']
    assert linked['server']['check']['status'] == 'ok' and gate['read_tools'] == [READ] and sorted(gate['blocked_tools']) == sorted([WRITE, WRITE_FAILS, UNMARKED])
    listed = next(s for s in _ok(world.api('GET', '/api/mcp/servers'))['servers'] if s['name'] == SERVER)
    assert listed['selectable'] and sorted(listed['read_confirmed']) == [UNMARKED]            # 읽기로 확인한 도구가 에이전트 몫에 더해졌다
    stamp = mcp_registry.store_for(world.rt.repo).servers(TENANT)[SERVER]['hyd']['gate']
    assert sorted(stamp['read_tools']) == [READ, UNMARKED] and sorted(stamp['blocked_tools']) == sorted([WRITE, WRITE_FAILS])
    # 포털의 [써 보기]는 쓰기 도구를 부르지 않고 까닭을 말한다(학생의 시스템에 호출이 가지 않는다)
    status, refused = world.api('POST', f'/api/mcp/servers/{SERVER}/tools/{WRITE}/call', {'arguments': {'item': ITEM, 'qty': 1}, 'by': ME})
    assert status == 403 and '쓰기 도구' in refused['detail'] and system.called(WRITE) == []


def test_내가_만든_역할은_담당자가_구성원이고_지식_지도의_역할로도_바로_생긴다(world, linked):
    """역할의 정본은 업무 DB — 포털에서 만든 역할이 지식 그래프의 Role 로 옮겨져 문서 · 조치 방법의 승인 역할로 고를 수 있다."""
    assert linked['role']['members'] == [ME] and linked['role']['knowledge']['synced'] and ROLE_ID in linked['role']['knowledge']['created']
    [node] = world.stack.graph._run('MATCH (r:Role {id:$id}) RETURN r.name AS name, r.level AS level', id=ROLE_ID)
    assert node == {'name': ROLE_NAME, 'level': 2}
    assert ROLE_ID in [r['id'] for r in _ok(world.api('GET', '/api/kg/catalog'))['roles']]          # 조치 방법 화면의 승인 역할 목록


def test_수업과_무관한_내_흐름이_내_에이전트_내_역할_내_서버로_끝까지_돈다(world, linked, system, relay):
    """등록 → 검사 → 판본 등록 → 직접 시작 → 에이전트가 읽기 도구를 실제로 부름 → 승인 전에는 쓰기가 한 번도 나가지 않음 → 담당자가 승인 →
    process 가 쓰기 도구를 정확히 한 번, 사람이 고른 안의 값으로 부름 → 결과가 처리 건의 그 단계 기록과 값에 남음 → 끝."""
    did = 'office_reorder_' + uuid.uuid4().hex[:6]
    checked, version = _register(world, did, '비품 재주문', agent=linked['agent'])
    assert version, checked['check']['problems']
    [dep] = checked['check']['dependencies']['items']
    assert (dep['server'], dep['tool'], dep['status']) == (SERVER, WRITE, 'saved_check')        # 검사 화면: 저장된 검사에 그 서버 · 도구가 있다
    relay.reset()
    pid = _start(world, did, version)
    step = world.row(pid, 'T_agent', 'IN_PROGRESS')
    assert step['user_id'] == linked['agent']

    cli = StudentCli()
    assert world.runner('live', cli).poll_once() == 1
    step = world.row(pid, 'T_agent')
    assert step['status'] in ('SUBMITTED', 'DONE'), world._failure(step)
    # 에이전트: 읽기 도구는 실제로 불렸고, 쓰기 도구는 워커가 금지 목록에 넣어 부르지 못했다. 모델 호출은 수업 관문을 지났다(실제 AI 아님)
    assert cli.called == [f'mcp__{SERVER}__{READ}'] and cli.refused == [f'mcp__{SERVER}__{WRITE}']
    assert system.called(READ) == [{'item': ITEM}] and system.called(WRITE) == []
    assert len(relay.requests) == 1
    world.poll()
    assert world.values(pid)['proposal']['options'][0] == {'slot': 'A', 'qty': 2, 'reason': '재고 3개 — 재주문 기준 5개까지'}

    # 사람 승인 앞: 담당자에게 내 역할의 일로 와 있고, 쓰기는 아직 나가지 않았다
    waiting = world.row(pid, 'T_ok', 'IN_PROGRESS')
    assert waiting['user_id'] in (ME, ROLE_ID)
    world.poll(2)
    assert system.called(WRITE) == [] and world.values(pid).get('mcp_receipt') is None

    _ok(_approve(world, pid, approval_part.APPROVE, option='A'))
    world.poll(3)
    inst = world.inst(pid)
    assert (inst['status'], inst['end_event']) == ('COMPLETED', 'E_done'), [(w['activity_id'], w['status'], w.get('log')) for w in world.rows(pid)]
    [order] = system.called(WRITE)                                                   # 정확히 한 번
    assert (order['item'], order['qty']) == (ITEM, 2) and order['idempotency_key']   # 처리 건 값(품목)과 사람이 고른 안(수량 2)
    receipt = world.values(pid)['mcp_receipt']
    assert (receipt['server'], receipt['tool']) == (SERVER, WRITE) and 'ORD-001' in receipt['result']
    events = world.events(todo=world.row(pid, 'T_order')['id'], job='MCP_EFFECT_CALL')
    assert [e['event_type'] for e in events] == ['tool_usage_started', 'tool_usage_finished'] and 'ORD-001' in events[-1]['data']['result']
    # 도구 지도의 호출 기록에도 그 호출이 남는다(처리 건으로 이어진다)
    logged = _ok(world.api('GET', f'/api/mcp/calls?server={SERVER}&tool={WRITE}'))['calls']
    assert [c['proc_inst_id'] for c in logged] == [pid]


def test_반려하면_쓰기_도구는_불리지_않고_반려로_끝난다(world, linked, system):
    did = 'office_reorder_' + uuid.uuid4().hex[:6]
    _, version = _register(world, did, '비품 재주문', agent=linked['agent'])
    pid = _start(world, did, version)
    assert world.runner('live', StudentCli(wants=(READ,))).poll_once() == 1
    world.poll()
    status, body = _approve(world, pid, approval_part.REJECT)
    assert status == 400 and '반려 사유' in body['detail']                              # 사유 없는 반려는 받지 않고 무엇이 빠졌는지 말한다
    _ok(_approve(world, pid, approval_part.REJECT, reason='이번 달 예산 초과'))
    world.poll(3)
    inst = world.inst(pid)
    assert (inst['status'], inst['end_event']) == ('COMPLETED', 'E_no')
    assert system.called(WRITE) == [] and world.values(pid).get('mcp_receipt') is None
    assert world.values(pid)['approved_by'] is None                                   # 반려는 승인 값을 남기지 않는다


# ---------------------------------------------------------------- AI 키 없는 PC(재생 모드)
def test_AI_키_없는_PC에서_내_에이전트_단계는_까닭을_말하고_멈추고_에이전트_없는_흐름은_끝까지_간다(world, linked, system):
    """재생 모드에는 학생이 만든 에이전트 단계의 저장된 응답이 없다 — 지어내지 않고 멈추며 「강사」 · 「녹화」 없이 까닭을 말한다.
    사람 승인 → 승인 뒤 MCP 호출만 있는 흐름은 AI 가 필요 없어 키 없이도 끝까지 간다."""
    from worker import ai_replay
    did = 'office_reorder_' + uuid.uuid4().hex[:6]
    _, version = _register(world, did, '비품 재주문', agent=linked['agent'])
    pid = _start(world, did, version)
    assert world.runner('replay').poll_once() == 1
    step = world.row(pid, 'T_agent')
    said = json.dumps(world._failure(step), ensure_ascii=False)
    assert step['status'] not in ('SUBMITTED', 'DONE') and ai_replay.REPLAY in said and '재고 확인 · 주문안 작성' in said, said
    assert '강사' not in said and '녹화' not in said
    assert system.calls == []                                                          # 재생은 학생의 시스템을 부르지 않았다

    direct = 'office_direct_' + uuid.uuid4().hex[:6]
    _, version = _register(world, direct, '비품 바로 주문')
    pid = _start(world, direct, version, proposal=PROPOSAL)
    _ok(_approve(world, pid, approval_part.APPROVE, option='A'))
    world.poll(3)
    assert (world.inst(pid)['status'], world.inst(pid)['end_event']) == ('COMPLETED', 'E_done')
    assert [(o['item'], o['qty']) for o in system.called(WRITE)] == [(ITEM, 2)]


# ---------------------------------------------------------------- 길이 막히는 곳: 까닭을 말하는가
def test_인자_틀의_값_이름이_틀리면_실행_전에_그_칸에서_알린다(world, linked):
    """한 줄 실수(오타)가 승인 뒤 실행 때에야 드러나지 않게 — 검사가 그 단계의 설정 칸과 쓸 수 있는 값 이름을 말한다."""
    did = 'office_direct_' + uuid.uuid4().hex[:6]
    checked, version = _register(world, did, '비품 바로 주문', arguments={'item': '{itme}', 'qty': '{approved_option.qty}'})
    assert version is None
    [problem] = checked['check']['problems']
    assert (problem['where']['id'], problem['field']) == ('T_order', 'config') and '{itme}' in problem['reason'] and 'item' in problem['reason']


def _direct_flow(world):
    """에이전트 없는 흐름(사람 승인 → 승인 뒤 MCP 호출) 하나를 등록하고 처리 건 하나를 승인 앞까지. 돌려줌 = (흐름 id, 판본, 처리 건 id)."""
    did = 'office_direct_' + uuid.uuid4().hex[:6]
    _, version = _register(world, did, '비품 바로 주문')
    return did, version, _start(world, did, version, proposal=PROPOSAL)


def _uses(world):
    return next(s for s in _ok(world.api('GET', '/api/mcp/servers'))['servers'] if s['name'] == SERVER)


def test_도구_지도는_내_서버를_부르는_흐름_단계를_보이고_옛_판본으로_진행_중인_처리_건의_단계도_센다(world, linked):
    """화면이 지우기 확인창에 보일 것: 이 서버를 도구로 붙인 에이전트와, 이 서버의 도구를 부르는 흐름 단계(최신 판본 · 진행 중인 옛 판본)."""
    did, version, _ = _direct_flow(world)
    assert [a['id'] for a in _uses(world)['agents']] == [linked['agent']]
    assert [(s['definition'], s['version'], s['activity_id'], s['activity_name'], s['tool'], s['latest'], s['running']) for s in _uses(world)['flow_steps']] == [
        (did, version, 'T_order', '비품 주문 넣기', WRITE, True, 1)]
    newer = _ok(world.api('POST', f'/api/flows/{did}/register', {'mapping': _mapping('비품 바로 주문'), 'by': ME}), 201)['version']
    assert [(s['version'], s['latest'], s['running']) for s in _uses(world)['flow_steps']] == [(version, False, 1), (newer, True, 0)]


def test_흐름_단계가_부르는_서버는_지우지_않고_무엇이_쓰는지_말한다(world, linked):
    """전에는 지우기가 에이전트만 봐서, 흐름의 「승인 뒤 MCP 호출」 단계가 부르는 서버를 지우면 흐름이 실행 때에야 조용히 깨졌다."""
    _direct_flow(world)
    _ok(world.api('PUT', f"/api/agents/{linked['agent']}", {'name': '비품 재고 에이전트', 'role': '', 'goal': '재고를 조회해 주문안을 낸다', 'persona': '',
                                                          'model': '', 'tools': [], 'skills': ['stock-check'], 'work_rules': '', 'by': ME}))
    status, refused = world.api('DELETE', f'/api/mcp/servers/{SERVER}?by={ME}')              # 에이전트에서는 뺐다 — 남은 것은 흐름 단계뿐
    assert status == 409 and '「비품 바로 주문」' in refused['detail'] and '「비품 주문 넣기」' in refused['detail'] and '진행 중인 처리 건 1건' in refused['detail']
    assert SERVER in mcp_registry.store_for(world.rt.repo).servers(TENANT)


def _stopped_without_server(world, system):
    """에이전트 없는 흐름의 처리 건을 승인한 뒤, 그 단계가 부를 서버를 강제로 지워 「승인 뒤 MCP 호출」 단계가 멈춘 상태. 돌려줌 = (처리 건 id, 멈춘 행)."""
    did, version, pid = _direct_flow(world)
    gone = _ok(world.api('DELETE', f'/api/mcp/servers/{SERVER}?by={ME}&force=true'))
    assert [(s['version'], s['activity_id']) for s in gone['flow_steps_still_calling_it']] == [(version, 'T_order')]
    _ok(_approve(world, pid, approval_part.APPROVE, option='A'))
    world.poll(5)
    stopped = world.row(pid, 'T_order')
    assert stopped['status'] == 'PENDING' and system.called(WRITE) == []
    return pid, stopped


def test_강제로_지운_서버를_부르는_단계는_아무것도_보내지_않았다는_사실과_무엇을_하면_되는지_말하며_멈춘다(world, linked, system):
    """전에는 「앞선 외부 쓰기(메일 · 발주 등)가 실제로 됐는지 확인되지 않아 자동 재시도를 멈췄습니다」로 멈췄다 — 서버에 아무것도 보내지 않았는데
    외부 결과를 확인하라고 했고, 진짜 까닭(등록되지 않은 서버)은 가려졌다."""
    _, stopped = _stopped_without_server(world, system)
    said = world._failure(stopped)['friendly']
    assert f"도구 서버 '{SERVER}'가 등록되어 있지 않습니다" in said and '[도구 연결]' in said and '다시 수행' in said, said
    assert '외부 쓰기' not in said and '외부 결과' not in said, said
    assert int(stopped['retry']) == 3                                            # 보내지 않은 실패는 정해진 횟수만큼 다시 해 본 뒤 멈춘다


def test_멈춘_호출_단계는_서버를_다시_등록한_뒤_그_단계부터_다시_수행하면_승인은_그대로_두고_끝까지_간다(world, linked, system):
    """전에는 사람 승인이 있는 흐름은 승인한 뒤로 어느 단계에서도 다시 수행할 수 없었다(승인 값을 「누가 만든 값인지 모르는 값」으로, 한 번도
    보내지 못한 호출 단계를 「이미 실행된 시스템 단계」로 막았다) — 멈춘 단계의 안내는 [다시 수행]을 말하는데 그 길이 닫혀 있었다."""
    pid, stopped = _stopped_without_server(world, system)
    _ok(world.api('POST', '/api/mcp/servers', {'name': SERVER, 'url': system.url, 'by': ME}), 201)
    preview = _ok(world.api('GET', f"/api/instances/{pid}/rework-preview?workitem_id={stopped['id']}"))
    assert preview['blockers'] == [] and preview['affected_nodes'] == ['E_done', 'T_order'], preview['blockers']
    assert {r['variable'] for r in preview['retained_outputs']} >= {'approved_by', 'approved_option', 'approval'}      # 승인은 다시 받지 않는다
    _ok(world.api('POST', f'/api/instances/{pid}/rework', {'workitem_id': stopped['id'], 'snapshot_token': preview['snapshot_token'],
                                                          'request_id': str(uuid.uuid4()), 'by': ME, 'role': ROLE_ID, 'reason': '도구 서버를 다시 등록함'}))
    world.poll(5)
    assert (world.inst(pid)['status'], world.inst(pid)['end_event']) == ('COMPLETED', 'E_done'), [(w['activity_id'], w['status'], w.get('log')) for w in world.rows(pid)]
    assert [(o['item'], o['qty']) for o in system.called(WRITE)] == [(ITEM, 2)]              # 다시 수행한 뒤 정확히 한 번, 승인한 수량으로


def test_승인_단계부터_다시_수행하면_앞선_승인_값은_지워지고_새로_승인해야_호출이_나간다(world, linked, system):
    """승인 값(승인자 · 고른 안)은 승인 단계가 만든 값이다 — 승인 단계를 다시 하면 남아 있지 않아야 한다(옛 승인으로 쓰기가 나가지 않는다)."""
    pid, stopped = _stopped_without_server(world, system)
    _ok(world.api('POST', '/api/mcp/servers', {'name': SERVER, 'url': system.url, 'by': ME}), 201)
    approved = world.row(pid, 'T_ok', 'DONE')
    preview = _ok(world.api('GET', f"/api/instances/{pid}/rework-preview?workitem_id={approved['id']}"))
    assert preview['blockers'] == [] and {'approved_by', 'approved_option', 'approval'} <= set(preview['invalidated_variables']), preview
    _ok(world.api('POST', f'/api/instances/{pid}/rework', {'workitem_id': approved['id'], 'snapshot_token': preview['snapshot_token'],
                                                          'request_id': str(uuid.uuid4()), 'by': ME, 'role': ROLE_ID, 'reason': '수량을 다시 고른다'}))
    world.poll(3)
    assert world.values(pid).get('approved_by') is None and system.called(WRITE) == []      # 새 승인 전에는 나가지 않는다
    _ok(_approve(world, pid, approval_part.APPROVE, option='A'))
    world.poll(5)
    assert world.inst(pid)['end_event'] == 'E_done' and [(o['item'], o['qty']) for o in system.called(WRITE)] == [(ITEM, 2)]


def test_쓰기_요청을_받은_서버가_오류로_끝나면_다시_보내지_않고_외부_결과를_확인하라고_멈춘다(world, linked, system):
    """보내지 않은 실패(등록 없는 서버 — 위)와 달리, 서버가 쓰기 요청을 받은 뒤의 실패는 썼는지 알 수 없다. 같은 호출을 알아볼 열쇠
    (idempotency_key)를 받지 않는 도구면 process 는 자동으로 다시 보내지 않는다(두 번 주문하지 않는다)."""
    did = 'office_direct_' + uuid.uuid4().hex[:6]
    _, version = _register(world, did, '비품 바로 주문', tool=WRITE_FAILS)
    pid = _start(world, did, version, proposal=PROPOSAL)
    _ok(_approve(world, pid, approval_part.APPROVE, option='A'))
    world.poll(5)
    stopped = world.row(pid, 'T_order')
    assert stopped['status'] == 'PENDING' and system.called(WRITE_FAILS) == [{'item': ITEM, 'qty': 2}]      # 한 번만 보냈다
    assert '외부 결과를 확인' in world._failure(stopped)['friendly'], world._failure(stopped)
