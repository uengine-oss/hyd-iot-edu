"""B5 에이전트에게 질문하기: 질문 하나 = 처리 건 하나(정식 정의 ask_agent 1.0), 답할 에이전트 선택이 워커 실행까지 닿음,
실제 도구 호출 이벤트(가짜 CLI를 돌리는 진짜 워커 Runner)로 답 · 근거 대조, 근거 없으면 '답할 수 없음 + 이유',
결정론 대체 모드(워커 없음)는 처리 건을 만들지 않고 사람이 읽을 사유, 같은 요청은 같은 처리 건, 되돌리기는 끝난 질문 기록만."""
import json
import uuid

import pytest
from cliagents import ExecEvent, ExecEventKind
from fastapi import FastAPI
from fastapi.testclient import TestClient

from procsvc import ask, engine, instance_mode
from procsvc.definition_registry import validate_definition
from test_instance_mode import DEFS, world  # noqa: F401 — world fixture (MemoryRepo + 실제 instance_mode.build)
from test_worker import TENANT_MCP
from worker.runner import Runner
from worker.settings import Settings

SQL = 'select asset, fg_stock from ent.fg_inventory order by fg_stock asc limit 1'
UP = lambda: {'url': 'http://worker:8097', 'reachable': True, 'error': None, 'agents': []}            # noqa: E731
DOWN = lambda: {'url': 'http://agent-worker:8097', 'reachable': False, 'error': 'URLError: connection refused', 'agents': []}  # noqa: E731


def _people(rt):
    rt.repo.upsert_tenant({'id': 'hyd', 'name': 'hyd', 'mcp': TENANT_MCP})
    rt.repo.upsert_user({'id': 'sys:agent', 'username': 'AI 에이전트', 'is_agent': True, 'agent_type': 'agent', 'goal': '원인 진단',
                         'tools': 'neo4j,enterprise,hyd-dmn'})
    rt.repo.upsert_user({'id': 'agent:student-db', 'username': '업무 DB 조회 도우미', 'is_agent': True, 'agent_type': 'agent',
                         'goal': '업무 DB로 답한다', 'tools': 'enterprise', 'origin': 'user'})
    rt.repo.upsert_user({'id': 'sys:scada', 'username': 'SCADA', 'is_agent': True, 'agent_type': 'system'})
    rt.repo.upsert_user({'id': 'role:operator', 'username': '운전원', 'is_agent': False})


def _ask(rt, q='완제품 재고가 가장 적은 설비와 그 수량은?', agent=None, probe=UP, bridge='off', rid=None):
    return ask.start(rt, q, agent, '수강생', rid, definitions_dir=DEFS, worker_probe=probe, bridge=bridge)


def _cli(answer: dict | str, calls=(('mcp__enterprise__describe_catalog', {}, '{"tables": ["fg_inventory"]}'),
                                     ('mcp__enterprise__query', {'sql': SQL}, '{"result": "ok", "document": {"rows": [["HYD-02", 100]]}}')),
         requests=None):
    """가짜 CLI: 도구 호출(시작 · 끝) 뒤 최종 답 하나. 워커 Runner가 이것을 이벤트 행으로 남긴다."""
    def fn(provider, request, env):
        if requests is not None:
            requests.append(request)
        yield ExecEvent(kind=ExecEventKind.RUN_START, text='model-x', session_id='s1')
        for i, (tool, inp, out) in enumerate(calls):
            yield ExecEvent(kind=ExecEventKind.TOOL_START, tool=tool, tool_input=inp, tool_use_id=f't{i}', session_id='s1')
            yield ExecEvent(kind=ExecEventKind.TOOL_END, tool=tool, text=out, tool_use_id=f't{i}', session_id='s1')
        yield ExecEvent(kind=ExecEventKind.RESULT, text=answer if isinstance(answer, str) else json.dumps(answer, ensure_ascii=False), session_id='s1')
    return fn


def _work(rt, tmp_path, cli):
    """실제 워커(Runner)가 질문 작업을 집어 실행 → 엔진이 제출을 처리."""
    r = Runner(Settings(workspace_root=tmp_path, schema_prompt_path=tmp_path / 'none.md', consumer='t:1', cancel_check_every_s=0),
               rt.repo, exec_fn=cli, schema_prompt='# s', resolve_provider=lambda pid: object())
    n = r.poll_once()
    rt.poll_once()
    return n


ANSWER = {'status': 'answered', 'answer': '완제품 재고가 가장 적은 설비는 HYD-02, 100개입니다.',
          'evidence': [{'tool': 'enterprise/query', 'query': SQL, 'result': 'HYD-02 | 100'}], 'note': 'fg_inventory.fg_stock 열 주석'}


# ---------------------------------------------------------------- 정식 정의
def test_the_probe_question_definition_is_a_registered_formal_definition(world):
    rt = world['rt']
    raw = ask.definition(DEFS)
    validate_definition(json.loads(json.dumps(raw)))
    row = rt.repo.get_proc_def(ask.DEFINITION_ID, rt.tenant_id, version=ask.VERSION)
    assert row is not None, 'instance_mode.build 가 기동 때 등록한다'
    act = row['definition']['activities'][0]
    assert act['agentMode'] == 'COMPLETE' and act['orchestration'] == 'cliagents' and act['inputData'] == ['question']
    assert row['definition']['roles'][0]['endpoint'] == ask.DEFAULT_AGENT
    assert row['definition']['forms']['ask_answer']['contract'] == ask.CONTRACT
    text = act['instruction']
    assert 'fg_inventory' not in text and 'ent.' not in text and '정답' not in text      # 표 · 열 · 정답을 박지 않음(메타데이터를 읽게)
    assert ask.register_definition(rt, DEFS)['prod_version'] == ask.VERSION              # 다시 등록해도 같은 판본


# ---------------------------------------------------------------- 질문 → 실제 도구 호출 → 근거 있는 답
def test_question_runs_as_one_instance_with_real_tool_call_events_and_a_grounded_answer(world, tmp_path):
    rt = world['rt']; _people(rt)
    v = _ask(rt)
    assert v['state'] == 'waiting' and v['agent']['id'] == 'sys:agent' and v['link'].startswith('#/instances/ask_agent.')
    assert '/task/' in v['link'] and v['result'] is None
    assert _work(rt, tmp_path, _cli(ANSWER)) == 1
    done = ask.view(rt, v['id'])
    assert done['state'] == 'done'
    assert [c['tool'] for c in done['tool_calls']] == ['enterprise/describe_catalog', 'enterprise/query']
    assert all(c['ok'] and not c['running'] for c in done['tool_calls'])
    ev = [e['event_type'] for e in rt.repo.list_events(todo_id=done['workitem'])]
    assert ev.count('tool_usage_started') == 2 and ev.count('tool_usage_finished') == 2      # 처리 과정 화면이 읽는 같은 이벤트
    res = done['result']
    assert res['kind'] == 'answered' and 'HYD-02' in res['answer'] and res['verified'] == 1
    assert res['evidence'][0]['verified'] and res['evidence'][0]['call'] == done['tool_calls'][1]['id']
    inst = rt.repo.get_instance(v['id'])
    assert inst['status'] == 'COMPLETED' and engine.variables(inst)['status'] == 'answered'
    hist = ask.history(rt)
    assert [h['id'] for h in hist] == [v['id']] and hist[0]['verdict'] == 'answered' and hist[0]['calls'] == 2


def test_the_chosen_agent_answers_its_profile_reaches_the_worker(world, tmp_path):
    rt = world['rt']; _people(rt)
    v = _ask(rt, agent='agent:student-db')
    wi = rt.repo.get_workitem(v['workitem'])
    assert wi['user_id'] == 'agent:student-db' and v['agent']['name'] == '업무 DB 조회 도우미'
    reqs = []
    _work(rt, tmp_path, _cli(ANSWER, requests=reqs))
    assert '업무 DB 조회 도우미' in reqs[0].prompt and 'AI 에이전트 (원인 진단)' not in reqs[0].prompt
    mcp = json.loads((tmp_path / 'hyd' / v['workitem'] / '.mcp.json').read_text(encoding='utf-8'))
    assert set(mcp['mcpServers']) == {'enterprise'}                                            # 그 에이전트의 도구(MCP)만
    # 다른 질문은 기본 에이전트 — 정의(기준)의 역할 담당은 그대로
    assert rt.repo.get_workitem(_ask(rt)['workitem'])['user_id'] == 'sys:agent'
    assert rt.repo.get_proc_def(ask.DEFINITION_ID, rt.tenant_id, version=ask.VERSION)['definition']['roles'][0]['endpoint'] == 'sys:agent'


def test_agent_choice_is_checked(world):
    rt = world['rt']; _people(rt)
    ids = [a['id'] for a in ask.agents(rt.repo, rt.tenant_id)]
    assert ids[0] == 'sys:agent' and 'agent:student-db' in ids and 'sys:scada' not in ids and 'role:operator' not in ids
    for bad in ('sys:scada', 'role:operator', 'agent:none'):
        with pytest.raises(LookupError, match='에이전트가 아닙니다'):
            _ask(rt, agent=bad)
    with pytest.raises(ValueError, match='질문을 입력'):
        _ask(rt, q='   ')
    with pytest.raises(ValueError, match='1000자'):
        _ask(rt, q='가' * 1001)
    with pytest.raises(ValueError, match='정의에 없는 역할'):
        rt.start_definition(ask.DEFINITION_ID, ask.VERSION, 'ask:x', values={'question': 'q'}, role_endpoints={'없는 역할': 'sys:agent'})
    assert rt.repo.list_source_runs(rt.tenant_id, ask.DEFINITION_ID, ask.EVENT_PREFIX) == []


# ---------------------------------------------------------------- 근거가 없으면 답할 수 없음 + 이유
def test_cannot_answer_comes_back_with_the_agents_reason(world, tmp_path):
    rt = world['rt']; _people(rt)
    v = _ask(rt, q='다음 달 원자재 환율은?')
    _work(rt, tmp_path, _cli({'status': 'cannot_answer', 'reason': '업무 DB 카탈로그에 환율 예측 표가 없습니다 (describe_catalog 확인)'},
                             calls=(('mcp__enterprise__describe_catalog', {}, '{"tables": []}'),)))
    res = ask.view(rt, v['id'])['result']
    assert res['kind'] == 'unanswerable' and res['by'] == 'agent' and '환율 예측 표가 없습니다' in res['reason']


def test_an_answer_without_any_tool_call_is_not_shown_as_an_answer(world, tmp_path):
    rt = world['rt']; _people(rt)
    v = _ask(rt)
    _work(rt, tmp_path, _cli(ANSWER, calls=()))                                               # 근거를 지어냄: 도구 호출 0
    res = ask.view(rt, v['id'])['result']
    assert res['kind'] == 'unanswerable' and res['by'] == 'server' and '성공한 도구 조회가 하나도 없습니다' in res['reason']
    assert res['claimed'] == ANSWER['answer']


def test_evidence_that_is_not_in_the_tool_call_record_is_not_trusted(world, tmp_path):
    rt = world['rt']; _people(rt)
    v = _ask(rt)
    other = dict(ANSWER, evidence=[{'tool': 'enterprise/query', 'query': 'select max(fg_stock) from ent.fg_inventory', 'result': '1200'}])
    _work(rt, tmp_path, _cli(other))
    res = ask.view(rt, v['id'])['result']
    assert res['kind'] == 'unanswerable' and res['by'] == 'server' and '찾지 못했습니다' in res['reason']
    assert res['evidence'][0]['verified'] is False


def test_a_rejected_query_is_not_evidence(world, tmp_path):
    rt = world['rt']; _people(rt)
    v = _ask(rt)
    _work(rt, tmp_path, _cli(ANSWER, calls=(('mcp__enterprise__query', {'sql': SQL}, '{"result": "rejected", "message": "쓰기 금지"}'),)))
    d = ask.view(rt, v['id'])
    assert d['tool_calls'][0]['ok'] is False and '거절' in d['tool_calls'][0]['problem']
    assert d['result']['kind'] == 'unanswerable'


def test_answered_without_evidence_goes_back_for_correction(world, tmp_path):
    rt = world['rt']; _people(rt)
    v = _ask(rt)
    _work(rt, tmp_path, _cli({'status': 'answered', 'answer': 'HYD-02, 100개'}))
    d = ask.view(rt, v['id'])
    assert d['state'] == 'correcting' and 'evidence' in d['message'] and d['result'] is None
    with pytest.raises(ValueError, match='status'):
        ask.validate_answer({'status': 'maybe'})
    with pytest.raises(ValueError, match='reason'):
        ask.validate_answer({'status': 'cannot_answer'})
    with pytest.raises(ValueError, match='query'):
        ask.validate_answer({'status': 'answered', 'answer': 'x', 'evidence': [{'tool': 'enterprise/query'}]})


def test_a_failed_run_shows_the_workers_error_as_the_reason(world, tmp_path):
    rt = world['rt']; _people(rt)
    v = _ask(rt)
    _work(rt, tmp_path, _cli('JSON 없이 말로만 답함'))
    _work(rt, tmp_path, _cli('또 JSON 없음'))                                                  # 교정 요청 뒤에도 형식이 틀림
    d = ask.view(rt, v['id'])
    assert d["state"] == "failed" and "실패" in d["message"] and d["result"] is None


# ---------------------------------------------------------------- 결정론 대체 모드 · 워커 없음
def test_legacy_mode_without_a_worker_creates_nothing_and_says_why(world):
    rt = world['rt']; _people(rt)
    with pytest.raises(ask.WorkerUnavailable) as e:
        _ask(rt, probe=DOWN, bridge='legacy')
    msg = str(e.value)
    assert 'AGENT_BRIDGE=legacy' in msg and '처리 건으로 만들지 않았습니다' in msg and 'connection refused' in msg
    with pytest.raises(ask.WorkerUnavailable, match='연결할 수 없어'):
        _ask(rt, probe=DOWN, bridge='off')
    assert rt.repo.list_source_runs(rt.tenant_id, ask.DEFINITION_ID, ask.EVENT_PREFIX) == []
    assert ask.readiness(UP, 'legacy')['ready'] and ask.readiness(UP, 'legacy')['reason'] is None


def test_waiting_question_explains_when_the_worker_disappears(world):
    rt = world['rt']; _people(rt)
    v = _ask(rt)
    from datetime import datetime, timedelta, timezone
    later = datetime.now(timezone.utc) + timedelta(seconds=60)
    d = ask.view(rt, v['id'], worker_probe=DOWN, now=later)
    assert d['state'] == 'waiting' and '아무도 집지 않았습니다' in d['message'] and 'connection refused' in d['message']


# ---------------------------------------------------------------- 같은 요청 · 되돌리기 · API
def test_same_request_id_returns_the_same_instance(world):
    rt = world['rt']; _people(rt)
    rid = str(uuid.uuid4())
    assert _ask(rt, rid=rid)['id'] == _ask(rt, rid=rid)['id']
    assert len(rt.repo.list_source_runs(rt.tenant_id, ask.DEFINITION_ID, ask.EVENT_PREFIX)) == 1


def test_reset_hides_finished_questions_only_and_keeps_the_baseline(world, tmp_path):
    rt = world['rt']; _people(rt)
    done = _ask(rt)
    _work(rt, tmp_path, _cli(ANSWER))
    running = _ask(rt, q='두 번째 질문')
    out = ask.reset(rt)
    assert out['hidden'] == 1 and out['kept_running'] == 1
    assert [h['id'] for h in ask.history(rt)] == [running['id']]
    with pytest.raises(KeyError):
        ask.view(rt, done['id'])
    assert rt.repo.get_proc_def(ask.DEFINITION_ID, rt.tenant_id, version=ask.VERSION) is not None
    assert {u['id'] for u in rt.repo.list_users(None, rt.tenant_id)} >= {'sys:agent', 'agent:student-db'}


def test_http_routes(world, tmp_path, monkeypatch):
    rt = world['rt']; _people(rt)
    state = {'probe': UP}
    app = FastAPI()
    ask.register(app, runtime_factory=lambda: rt, definitions_dir=DEFS, worker_probe=lambda: state['probe'](), bridge=lambda: 'legacy')
    c = TestClient(app)
    s = c.get('/api/ask/status').json()
    assert s['ready'] and s['default'] == 'sys:agent' and [a['id'] for a in s['agents']][:1] == ['sys:agent']
    r = c.post('/api/ask', json={'question': '재고가 가장 적은 설비?', 'agent': 'agent:student-db'})
    assert r.status_code == 201 and r.json()['agent']['id'] == 'agent:student-db'
    pid = r.json()['id']
    _work(rt, tmp_path, _cli(ANSWER))
    assert c.get(f'/api/ask/{pid}').json()['result']['kind'] == 'answered'
    assert [h['id'] for h in c.get('/api/ask').json()] == [pid]
    assert c.post('/api/ask', json={'question': ''}).status_code == 400
    assert c.post('/api/ask', json={'question': 'q', 'agent': 'sys:scada'}).status_code == 404
    assert c.get('/api/ask/ask_agent.none').status_code == 404
    state['probe'] = DOWN
    r = c.post('/api/ask', json={'question': '워커 없을 때'})
    assert r.status_code == 503 and 'AGENT_BRIDGE=legacy' in r.json()['detail']
    assert c.get('/api/ask/status').json()['ready'] is False
    assert c.post('/api/ask/reset').json()['hidden'] == 1
    assert c.get('/api/ask').json() == []


def test_process_service_mounts_the_ask_routes():
    from procsvc import main
    paths = {r.path for r in main.app.routes}
    assert {'/api/ask', '/api/ask/status', '/api/ask/{proc_inst_id}', '/api/ask/reset'} <= paths
    assert instance_mode.DEFINITIONS_DIR is not None
