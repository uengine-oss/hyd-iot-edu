"""B5 — 에이전트에게 질문하기 (ProcessGPT의 대표 상호작용: 질문 하나 = 처리 건 하나).

    POST /api/ask {question, agent?, by?, request_id?}   질문 → 정식 정의 ask_agent 1.0의 처리 건 하나(답할 에이전트 = 고른 에이전트)
    GET  /api/ask/status                                답할 수 있나(워커 연결 · 결정론 대체 모드) + 고를 수 있는 에이전트
    GET  /api/ask                                       지난 질문 목록(최근 것 먼저)
    GET  /api/ask/{proc_inst_id}                        한 질문: 진행 상태 · 도구 호출(실시간) · 답 + 근거 또는 답할 수 없음 + 이유 · 처리 과정 링크
    POST /api/ask/reset                                 기준으로 되돌리기: 끝난 질문 기록을 목록에서 지운다(정의 · 에이전트 · 기준 데이터는 그대로)

정의는 회귀 검사기(scripts/probe_business_questions · probe_timeseries_questions · probe_rule_questions)가 매번 임시로
등록하던 질문 정의를 하나로 묶어 정식 파일(it/process/definitions/ask_agent_v1.json)로 올린 것이다. 기동 때 instance_mode.build가
등록하고, 질문할 때도 같은 파일을 다시 등록한다(같은 판본이면 그대로).

답의 계약(폼 ask-answer-v1, 교정 루프 A077): status = answered | cannot_answer. answered면 answer와 근거(evidence: 도구 · 실행한 질의 ·
결과)가 있어야 하고, cannot_answer면 reason이 있어야 한다. 형식이 틀리면 같은 세션에 교정 피드백이 간다.
서버는 에이전트의 자기 보고를 그대로 믿지 않는다: 근거로 적은 질의가 이 작업의 실제 도구 호출 기록(events)에 있는지 대조하고,
없으면 "답할 수 없음 + 이유"로 보여 준다(근거 없는 답을 성공처럼 보이지 않는다).

결정론 대체 모드(AGENT_BRIDGE=legacy)의 내장 판단은 경보 처리 건의 판단 4단계만 채운다. 자유 질문에 답할 일꾼(워커)이 없으면
질문을 처리 건으로 만들지 않고 503 + 사람이 읽을 사유를 돌려준다(legacy_meaning_api와 같은 방식 — 아무도 집지 않을 처리 건을 남기지 않는다).
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from hydcommon.timeutil import parse_iso
from pydantic import BaseModel

from . import engine

DEFINITION_FILE = 'ask_agent_v1.json'
DEFINITION_ID = 'ask_agent'
VERSION = '1.0'
ACTIVITY = 'task:answer'
ROLE = '답변 에이전트'
DEFAULT_AGENT = 'sys:agent'
CONTRACT = 'ask-answer-v1'
EVENT_PREFIX = 'ask:'
STATUSES = ('answered', 'cannot_answer')
MAX_QUESTION_CHARS = 1000
WAIT_PROBE_AFTER_S = 10        # 아무도 집지 않은 지 이만큼 지나면 워커 연결을 다시 확인해 사유를 붙인다


class WorkerUnavailable(RuntimeError):
    """답할 일꾼이 없다 — 처리 건을 만들지 않았다(사유는 사람이 읽을 문장)."""


# ---------------------------------------------------------------- 정의
def definition(definitions_dir) -> dict:
    return json.loads((Path(definitions_dir) / DEFINITION_FILE).read_text(encoding='utf-8'))


def register_definition(rt, definitions_dir) -> dict:
    return rt.register_definition(definition(definitions_dir))


def validate_answer(output) -> None:
    """폼 ask-answer-v1 (교정 가능한 계약). ValueError → 같은 세션에 교정 피드백."""
    if not isinstance(output, dict):
        raise ValueError('답은 JSON 객체여야 합니다')
    status = output.get('status')
    if status not in STATUSES:
        raise ValueError(f"status는 {' | '.join(STATUSES)} 중 하나여야 합니다")
    if status == 'cannot_answer':
        if not isinstance(output.get('reason'), str) or not output['reason'].strip():
            raise ValueError('답할 수 없다면 reason에 무엇을 조회했고 왜 답할 수 없는지 적어야 합니다')
        return
    if not isinstance(output.get('answer'), str) or not output['answer'].strip():
        raise ValueError('status가 answered면 answer가 비어 있으면 안 됩니다')
    ev = output.get('evidence')
    if not isinstance(ev, list) or not ev:
        raise ValueError('답했다면 evidence에 실제로 실행한 질의를 하나 이상 남겨야 합니다 (근거 없는 답). 근거를 얻지 못했으면 status를 cannot_answer로 하세요')
    for i, item in enumerate(ev, 1):
        if not isinstance(item, dict):
            raise ValueError(f'evidence {i}번 항목은 {{"tool", "query", "result"}} 객체여야 합니다')
        for key in ('tool', 'query'):
            if not isinstance(item.get(key), str) or not item[key].strip():
                raise ValueError(f'evidence {i}번 항목의 {key}가 비어 있습니다 (실행한 도구 이름과 질의 그대로)')


def validate_result(form, inst, output) -> None:
    if form and form.get('contract') == CONTRACT:
        validate_answer(output)


# ---------------------------------------------------------------- 답할 에이전트 · 준비 상태
def agents(repo, tenant_id) -> list[dict]:
    """고를 수 있는 에이전트: users.is_agent 이고 시스템(SCADA · CMMS · 프로세스)이 아닌 것. 기본 에이전트가 먼저."""
    from .agents_store import csv_list, role_text
    skills: dict[str, list[str]] = {}
    try:
        for r in repo.list_agent_skills(tenant_id):
            skills.setdefault(r['user_id'], []).append(r['skill_name'])
    except Exception:  # noqa: BLE001 — 스킬 표가 없어도 에이전트는 고를 수 있다
        pass
    out = []
    for u in repo.list_users(None, tenant_id):
        if not u.get('is_agent') or (u.get('agent_type') or 'agent') == 'system':
            continue
        out.append({'id': u['id'], 'name': u.get('username') or u['id'], 'role': role_text(u.get('role')), 'goal': u.get('goal') or '',
                    'tools': csv_list(u.get('tools')), 'skills': sorted(skills.get(u['id'], [])), 'model': u.get('model') or None,
                    'default': u['id'] == DEFAULT_AGENT, 'mine': u.get('origin') == 'user'})
    return sorted(out, key=lambda a: (not a['default'], a['mine'], a['name']))


def readiness(worker_probe, bridge: str | None) -> dict:
    """질문을 받을 수 있나. 워커 연결이 판단 기준이다(AGENT_BRIDGE=legacy여도 워커가 있으면 질문 작업은 워커가 집는다)."""
    w = worker_probe() if worker_probe else {'reachable': False, 'url': None, 'error': '워커 확인 경로가 없습니다'}
    out = {'ready': bool(w.get('reachable')), 'bridge': bridge, 'worker': {'url': w.get('url'), 'reachable': bool(w.get('reachable')),
                                                                          'error': w.get('error'), 'agents': w.get('agents') or []}}
    if out['ready']:
        out['reason'] = None
        return out
    where = f"{w.get('url') or '워커 주소 미설정'} — {w.get('error') or '응답 없음'}"
    if bridge == 'legacy':
        out['reason'] = ('지금은 결정론 대체 모드(AGENT_BRIDGE=legacy)입니다. 이 모드의 내장 판단은 경보 처리 건의 판단 4단계(원인 진단 · 조치 후보 · '
                         '규정 검토 · 우선순위)만 채우고, 자유 질문에 답할 AI 일꾼(워커)은 없습니다. 질문은 처리 건으로 만들지 않았습니다. '
                         f'워커 연결 확인: {where}. 워커를 켜고(scripts/run_worker_host.sh) process의 WORKER_URL이 그 워커를 가리키면 질문할 수 있습니다.')
    else:
        out['reason'] = (f'AI 일꾼(워커)에 연결할 수 없어 질문을 처리 건으로 만들지 않았습니다: {where}. '
                         '워커를 켠 뒤(scripts/run_worker_host.sh) 다시 보내세요.')
    return out


# ---------------------------------------------------------------- 질문 → 처리 건
def check_question(question) -> str:
    if not isinstance(question, str) or not question.strip():
        raise ValueError('질문을 입력하세요')
    q = question.strip()
    if len(q) > MAX_QUESTION_CHARS:
        raise ValueError(f'질문은 {MAX_QUESTION_CHARS}자 이하로 적어 주세요 (지금 {len(q)}자)')
    return q


def check_agent(repo, tenant_id, agent_id) -> dict:
    agent_id = (agent_id or DEFAULT_AGENT).strip()
    found = next((a for a in agents(repo, tenant_id) if a['id'] == agent_id), None)
    if found is None:
        raise LookupError(f'질문에 답할 수 있는 에이전트가 아닙니다: {agent_id} (에이전트 목록에서 고르세요)')
    return found


def start(rt, question, agent_id=None, by=None, request_id=None, *, definitions_dir, worker_probe, bridge) -> dict:
    """질문 하나 = 처리 건 하나. 같은 request_id로 다시 보내면 같은 처리 건을 돌려준다(중복 클릭 · 재시도)."""
    q = check_question(question)
    agent = check_agent(rt.repo, rt.tenant_id, agent_id)
    ready = readiness(worker_probe, bridge)
    if not ready['ready']:
        raise WorkerUnavailable(ready['reason'])
    request_id = str(uuid.UUID(request_id)) if request_id else str(uuid.uuid4())
    register_definition(rt, definitions_dir)
    event_id = EVENT_PREFIX + request_id
    inst = rt.start_definition(DEFINITION_ID, VERSION, event_id, values={'question': q, 'asked_by': str(by or '수강생').strip()[:120]},
                               name='질문 · ' + (q if len(q) <= 40 else q[:40] + '…'), role_endpoints={ROLE: agent['id']})
    inst = inst or rt.repo.find_event_instance(rt.tenant_id, DEFINITION_ID, event_id)
    return view(rt, inst['proc_inst_id'])


# ---------------------------------------------------------------- 도구 호출 · 근거 대조
def short_tool(name) -> str:
    raw = str(name or 'tool')
    return raw[5:].replace('__', '/') if raw.startswith('mcp__') else raw


def is_data_tool(name) -> bool:
    """MCP 도구(조회)만 근거가 된다. 작업 폴더 쓰기 · 도구 검색 같은 내장 도구는 근거가 아니다."""
    raw = str(name or '')
    return raw.startswith('mcp__') or '/' in raw


def _envelope(out):
    if isinstance(out, dict):
        return out.get('structured_content') or out
    if isinstance(out, str):
        try:
            v = json.loads(out)
        except ValueError:
            return None
        return v if isinstance(v, dict) else None
    return None


def _failed(output, is_error) -> str | None:
    if is_error:
        return '도구가 오류를 돌려줬습니다'
    env = _envelope(output)
    if isinstance(env, dict):
        if isinstance(env.get('result'), str) and env['result'] != 'ok':
            return f"도구가 거절했습니다: {str(env.get('message') or env['result'])[:200]}"
        if env.get('error') and 'result' not in env:
            return f"도구 오류: {str(env['error'])[:200]}"
    return None


def _preview(value, n=600) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    text = ' '.join(str(text).split())
    return text if len(text) <= n else text[:n] + '…'


def tool_calls(events) -> list[dict]:
    """이 작업의 도구 호출(시작 · 끝을 tool_use_id로 짝지음), 일어난 순서대로."""
    calls, by_id = [], {}
    for e in events:
        d = e.get('data') or {}
        if e.get('event_type') == 'tool_usage_started':
            c = {'id': d.get('tool_use_id') or e.get('id'), 'tool': short_tool(d.get('tool')), 'raw_tool': d.get('tool'),
                 'data': is_data_tool(d.get('tool')), 'input': d.get('input'), 'input_text': _preview(d.get('input')),
                 'started': e.get('timestamp'), 'finished': None, 'running': True, 'ok': None, 'output_text': None, 'problem': None}
            calls.append(c)
            by_id[c['id']] = c
        elif e.get('event_type') == 'tool_usage_finished':
            c = by_id.get(d.get('tool_use_id'))
            if c is None:
                c = {'id': d.get('tool_use_id') or e.get('id'), 'tool': short_tool(d.get('tool')), 'raw_tool': d.get('tool'),
                     'data': is_data_tool(d.get('tool')), 'input': None, 'input_text': '', 'started': None}
                calls.append(c)
            problem = _failed(d.get('output'), d.get('is_error'))
            c.update(finished=e.get('timestamp'), running=False, ok=problem is None, problem=problem, output_text=_preview(d.get('output')))
    return calls


def _norm(text) -> str:
    return re.sub(r'\s+', ' ', str(text or '')).strip().rstrip(';').strip().lower()


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)


def _matches(query, call) -> bool:
    q = _norm(query)
    if len(q) < 4:
        return False
    for s in _strings(call.get('input')):
        n = _norm(s)
        if n and (n == q or (len(n) >= 12 and (q in n or n in q))):
            return True
    return False


def verdict(output, calls) -> dict:
    """에이전트 출력 + 실제 도구 호출 → 화면이 보일 결론. 근거가 기록에 없으면 답을 성공처럼 보이지 않는다."""
    output = output or {}
    data_ok = [c for c in calls if c['data'] and c['ok']]
    if output.get('status') == 'cannot_answer':
        return {'kind': 'unanswerable', 'by': 'agent', 'reason': output.get('reason'), 'note': output.get('note'),
                'queried': len(data_ok)}
    claimed = output.get('answer')
    if not data_ok:
        return {'kind': 'unanswerable', 'by': 'server', 'claimed': claimed,
                'reason': '에이전트가 답을 냈지만 이 질문을 처리하며 성공한 도구 조회가 하나도 없습니다 — 근거 없는 답이라 답으로 보이지 않습니다'}
    evidence = []
    for item in output.get('evidence') or []:
        hit = next((c for c in data_ok if _matches(item.get('query'), c)), None)
        evidence.append({'tool': item.get('tool'), 'query': item.get('query'), 'result': item.get('result'),
                         'verified': hit is not None, 'call': hit and hit['id']})
    if not any(e['verified'] for e in evidence):
        return {'kind': 'unanswerable', 'by': 'server', 'claimed': claimed, 'evidence': evidence,
                'reason': (f'에이전트가 근거로 적은 질의 {len(evidence)}개를 이 작업의 실제 도구 호출 기록(성공 {len(data_ok)}건)에서 찾지 못했습니다 — '
                           '근거를 확인할 수 없어 답으로 보이지 않습니다')}
    return {'kind': 'answered', 'answer': claimed, 'evidence': evidence, 'note': output.get('note'),
            'verified': sum(1 for e in evidence if e['verified']), 'queried': len(data_ok)}


# ---------------------------------------------------------------- 보기
def _age_s(ts, now=None) -> float | None:
    try:
        t = parse_iso(ts) if isinstance(ts, str) else ts
    except (TypeError, ValueError):
        return None
    if t is None:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return max(0.0, ((now or datetime.now(timezone.utc)) - t).total_seconds())


def _instance(rt, proc_inst_id):
    inst = rt.repo.get_instance(proc_inst_id)
    if not inst or inst.get('tenant_id') != rt.tenant_id or inst.get('proc_def_id') != DEFINITION_ID or inst.get('is_deleted'):
        raise KeyError(proc_inst_id)
    return inst


def _task(rt, inst):
    rows = [w for w in rt.repo.list_workitems(proc_inst_id=inst['proc_inst_id'], limit=None) if w['activity_id'] == ACTIVITY]
    return max(rows, key=engine.workitem_order) if rows else None


def _error_reason(events) -> str | None:
    for e in reversed(events):
        if e.get('event_type') == 'error':
            d = e.get('data') or {}
            return str(d.get('raw_error') or d.get('content') or d.get('error') or d.get('message') or '')[:600] or None
    return None


def _state(inst, wi, events, now=None) -> tuple[str, str]:
    if wi is None:
        return 'broken', '질문 작업이 없습니다 (정의 확인 필요)'
    if wi['status'] == 'DONE' or inst.get('status') == 'COMPLETED':
        return 'done', '답이 나왔습니다'
    if wi['status'] in ('CANCELLED',) or inst.get('status') in ('CANCELLED', 'TERMINATED'):
        return 'closed', '사람이 닫은 질문입니다' + (f" — {wi.get('log')}" if wi.get('log') else '')
    if wi['status'] == 'PENDING':
        return 'failed', '답을 받지 못했습니다: ' + (wi.get('log') or _error_reason(events) or '엔진이 결과를 받을 수 없어 보류했습니다')
    ds = wi.get('draft_status')
    fb = wi.get('feedback') if isinstance(wi.get('feedback'), dict) else {}
    if ds == 'FAILED':
        return 'failed', '에이전트 실행이 실패했습니다: ' + (_error_reason(events) or '사유 기록 없음')
    if ds == 'HUMAN_ASKED':
        return 'asking', '에이전트가 사람에게 묻고 기다립니다 (처리 과정 보기에서 답할 수 있습니다)'
    if ds == 'FB_REQUESTED' and fb.get('kind') == 'validation':
        return 'correcting', '답의 형식이 계약과 달라 같은 세션에 고쳐 달라고 돌려보냈습니다: ' + str((fb.get('history') or [''])[-1])[:300]
    if wi['status'] == 'SUBMITTED':
        return 'submitted', '답을 제출했습니다 · 엔진이 받는 중'
    if ds == 'STARTED':
        return 'running', '에이전트가 조회하는 중'
    return 'waiting', '답할 일꾼(워커)이 아직 질문을 집지 않았습니다'


def view(rt, proc_inst_id, *, worker_probe=None, now=None) -> dict:
    inst = _instance(rt, proc_inst_id)
    wi = _task(rt, inst)
    events = rt.repo.list_events(todo_id=wi['id']) if wi else []
    values = engine.variables(inst)
    state, message = _state(inst, wi, events, now)
    performer = (wi or {}).get('user_id') or next((b.get('endpoint') for b in inst.get('role_bindings') or [] if b.get('name') == ROLE), None)
    user = next(iter(rt.repo.list_users([performer], rt.tenant_id)), None) if performer else None
    calls = tool_calls(events)
    out = {'id': inst['proc_inst_id'], 'question': values.get('question'), 'asked_by': values.get('asked_by'),
           'agent': {'id': performer, 'name': (user or {}).get('username') or performer},
           'started': inst.get('start_date'), 'ended': inst.get('end_date'), 'state': state, 'message': message,
           'workitem': (wi or {}).get('id'), 'tool_calls': calls,
           'counts': {'calls': len(calls), 'data': sum(1 for c in calls if c['data']), 'ok': sum(1 for c in calls if c['data'] and c['ok']),
                      'running': sum(1 for c in calls if c['running'])},
           'link': f"#/instances/{inst['proc_inst_id']}" + (f"/task/{wi['id']}" if wi else ''), 'result': None}
    if state == 'done':
        out['result'] = verdict((wi or {}).get('output'), calls)
    if state == 'waiting' and worker_probe is not None:
        age = _age_s((wi or {}).get('start_date') or inst.get('start_date'), now)
        if age is not None and age >= WAIT_PROBE_AFTER_S:
            w = worker_probe()
            if not w.get('reachable'):
                out['message'] = (f"{int(age)}초째 아무도 집지 않았습니다 — AI 일꾼(워커)에 연결할 수 없습니다: {w.get('url')} — "
                                  f"{w.get('error') or '응답 없음'}. 워커를 켜면 이어서 답합니다(처리 과정 보기에서 닫을 수도 있습니다)")
            else:
                out['message'] = f'{int(age)}초째 대기 중 — 워커는 연결돼 있습니다(다른 작업을 처리 중일 수 있습니다)'
    return out


def history(rt, limit=30) -> list[dict]:
    rows = []
    for r in rt.repo.list_source_runs(rt.tenant_id, DEFINITION_ID, EVENT_PREFIX, limit=max(1, min(int(limit), 100))):
        try:
            v = view(rt, r['proc_inst_id'])
        except KeyError:
            continue
        res = v['result'] or {}
        rows.append({k: v[k] for k in ('id', 'question', 'agent', 'started', 'ended', 'state', 'message', 'link')}
                    | {'verdict': res.get('kind'), 'calls': v['counts']['data']})
    return rows


def reset(rt) -> dict:
    """기준으로 되돌리기(B5 영역): 끝난 질문 기록만 목록에서 지운다(행은 남기고 is_deleted). 진행 중인 질문은 남긴다.
    질문 정의 · 에이전트 · 업무 DB · 지식은 질문으로 바뀌지 않으므로 되돌릴 것이 없다."""
    runs = rt.repo.list_source_runs(rt.tenant_id, DEFINITION_ID, EVENT_PREFIX, limit=1000)
    done = [r['proc_inst_id'] for r in runs if r.get('status') != 'RUNNING']
    hidden = rt.repo.hide_instances(rt.tenant_id, DEFINITION_ID, done) if done else 0
    return {'hidden': hidden, 'kept_running': len(runs) - len(done),
            'note': '끝난 질문 기록을 목록에서 지웠습니다. 질문 정의 · 에이전트 · 업무 DB · 지식은 질문으로 바뀌지 않아 그대로입니다'
                    + (f' · 진행 중인 질문 {len(runs) - len(done)}건은 끝난 뒤 지울 수 있습니다' if len(runs) != len(done) else '')}


# ---------------------------------------------------------------- HTTP
class AskReq(BaseModel):
    question: str
    agent: str | None = None
    by: str | None = None
    request_id: str | None = None


def register(app, *, runtime_factory, definitions_dir, worker_probe, bridge):
    """bridge: () -> AGENT_BRIDGE 값. worker_probe: () -> instance_mode.worker_status() 모양."""
    import asyncio
    from fastapi import HTTPException

    def rt():
        r = runtime_factory()
        if r is None:
            raise HTTPException(409, '질문은 처리 건으로 실행되므로 instance 모드(PROCESS_MODE=instance)가 필요합니다')
        return r

    async def run(fn):
        try:
            return await asyncio.get_running_loop().run_in_executor(None, fn)
        except WorkerUnavailable as e:
            raise HTTPException(503, str(e)) from e
        except KeyError as e:
            raise HTTPException(404, f'그런 질문이 없습니다: {e.args[0] if e.args else ""}') from e
        except LookupError as e:
            raise HTTPException(404, str(e)) from e
        except ValueError as e:
            raise HTTPException(400, str(e)) from e

    @app.get('/api/ask/status')
    async def ask_status():
        r = rt()
        return await run(lambda: readiness(worker_probe, bridge()) | {'agents': agents(r.repo, r.tenant_id), 'default': DEFAULT_AGENT})

    @app.get('/api/ask')
    async def ask_history(limit: int = 30):
        r = rt()
        return await run(lambda: history(r, limit))

    @app.post('/api/ask', status_code=201)
    async def ask_start(req: AskReq):
        r = rt()
        return await run(lambda: start(r, req.question, req.agent, req.by, req.request_id, definitions_dir=definitions_dir,
                                       worker_probe=worker_probe, bridge=bridge()))

    @app.post('/api/ask/reset')
    async def ask_reset():
        r = rt()
        return await run(lambda: reset(r))

    @app.get('/api/ask/{proc_inst_id}')
    async def ask_view(proc_inst_id: str):
        r = rt()
        return await run(lambda: view(r, proc_inst_id, worker_probe=worker_probe))
