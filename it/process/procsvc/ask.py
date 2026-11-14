"""B5 — 에이전트에게 질문하기 (ProcessGPT의 대표 상호작용: 질문 하나 = 처리 건 하나).

    POST /api/ask {question, agent?, by?, request_id?}   질문 → 정식 정의 ask_agent(판본은 정의 파일의 version)의 처리 건 하나(답할 에이전트 = 고른 에이전트)
    GET  /api/ask/status                                답할 수 있나(AI 에이전트 상태) + 고를 수 있는 에이전트(그 에이전트가 질문에 쓰는 도구 서버)
    GET  /api/ask                                       지난 질문 목록(최근 것 먼저)
    GET  /api/ask/{proc_inst_id}                        한 질문: 진행 상태 · 도구 호출(실시간) · 답 + 근거 또는 답할 수 없음 + 이유 · 처리 과정 링크
    POST /api/ask/{proc_inst_id}/retry                  실패해 멈춘 같은 질문을 같은 작업으로 다시 진행(질문한 사람만, 2회까지)
    POST /api/ask/reset                                 기준으로 되돌리기: 끝난 질문 기록을 목록에서 지운다(정의 · 에이전트 · 기준 데이터는 그대로)

정의는 정식 파일 하나(it/process/definitions/ask_agent_v1.json)다. 기동 때 instance_mode.build가 등록하고, 질문할 때도 같은 파일을
다시 등록한다(같은 판본이면 그대로). 질문이 쓰는 도구 서버는 agents_store.run_servers(질문 계약 — 질문용 조회 도구 표)로 정한다.

답의 계약(폼 ask-answer-v1, 교정 루프 A077): status = answered | cannot_answer. answered면 answer와 근거(evidence: 도구 · 실행한 질의 ·
결과)가 있어야 하고, cannot_answer면 reason이 있어야 한다. 형식이 틀리면 같은 세션에 교정 피드백이 간다.
서버는 에이전트의 자기 보고를 그대로 믿지 않는다: 근거로 적은 질의가 이 작업의 실제 도구 호출 기록(events)에 있는지 대조하고,
없으면 "답할 수 없음 + 이유"로 보여 준다(근거 없는 답을 성공처럼 보이지 않는다).

답할 AI 워커가 켜져 있지 않으면 질문을 처리 건으로 만들지 않고 503 + 학생이 할 일을 적은 사유를 돌려준다(아무도 집지 않을 처리 건을 남기지 않는다).
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from hydcommon.timeutil import parse_iso
from pydantic import BaseModel

from . import engine
from .agents_store import QUESTION_CONTRACT
from .instances import InstanceRuntime

log = logging.getLogger('process.ask')

DEFINITION_FILE = 'ask_agent_v1.json'
DEFINITION_ID = 'ask_agent'
ACTIVITY = 'task:answer'
ROLE = '답변 에이전트'
DEFAULT_AGENT = 'sys:agent'
CONTRACT = QUESTION_CONTRACT     # 정의 파일 forms.ask_answer.contract 와 같은 값(질문용 조회 도구 표의 열쇠 — agents_store.FIXED_READS)
EVENT_PREFIX = 'ask:'
STATUSES = ('answered', 'cannot_answer')
MAX_QUESTION_CHARS = 1000
WAIT_PROBE_AFTER_S = 10        # 아무도 집지 않은 지 이만큼 지나면 워커 연결을 다시 확인해 사유를 붙인다


class WorkerUnavailable(RuntimeError):
    """답할 AI 에이전트가 없다 — 처리 건을 만들지 않았다(사유는 사람이 읽을 문장)."""


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
        if not isinstance(item.get('tool'), str) or not item['tool'].strip():
            raise ValueError(f'evidence {i}번 항목의 tool이 비어 있습니다 (서버를 포함한 실제 도구 이름)')
        query = item.get('query')
        if not (isinstance(query, str) and query.strip()) and not isinstance(query, dict):
            raise ValueError(f'evidence {i}번 항목의 query는 실제 질의 문자열 또는 실행한 인자 JSON 객체여야 합니다 (인자 없는 호출은 {{}})')
        if isinstance(query, dict):
            try:
                json.dumps(query, sort_keys=True, allow_nan=False)
            except (TypeError, ValueError) as error:
                raise ValueError(f'evidence {i}번 항목의 query는 유효한 JSON 객체여야 합니다') from error


def validate_result(form, inst, output) -> None:
    if form and form.get('contract') == CONTRACT:
        validate_answer(output)


# ---------------------------------------------------------------- 답할 에이전트 · 준비 상태
def agents(repo, tenant_id) -> list[dict]:
    """고를 수 있는 에이전트: users.is_agent 이고 시스템(SCADA · CMMS · 프로세스)이 아닌 것. 기본 에이전트가 먼저.
    servers = 이 에이전트로 질문할 때 실제로 연결하는 도구 서버(agents_store.run_servers — 질문용 조회 도구 표, 워커와 같은 규칙),
    left_out = 에이전트에 적혀 있지만 질문에는 쓰지 않는 서버(질문용 조회 도구가 없는 서버)."""
    from . import mcp_registry
    from .agents_store import agent_settings, csv_list, role_text, run_servers
    tenant = mcp_registry.store_for(repo).servers(tenant_id)
    skills: dict[str, list[str]] = {}
    for r in repo.list_agent_skills(tenant_id):
        skills.setdefault(r['user_id'], []).append(r['skill_name'])
    out = []
    for u in repo.list_users(None, tenant_id):
        if not u.get('is_agent') or (u.get('agent_type') or 'agent') == 'system':
            continue
        tools = csv_list(u.get('tools'))
        servers = list(run_servers(agent_settings(repo, tenant_id, u).tools, tenant, CONTRACT))
        out.append({'id': u['id'], 'name': u.get('username') or u['id'], 'role': role_text(u.get('role')), 'goal': u.get('goal') or '',
                    'tools': tools, 'servers': servers, 'left_out': [t for t in tools if t not in servers],
                    'skills': sorted(skills.get(u['id'], [])), 'model': u.get('model') or None,
                    'default': u['id'] == DEFAULT_AGENT, 'mine': u.get('origin') == 'user'})
    return sorted(out, key=lambda a: (not a['default'], a['mine'], a['name']))


NOT_READY = 'AI 에이전트가 아직 켜지는 중이거나 꺼져 있어 질문을 보내지 않았습니다. 1분 뒤 다시 보내고, 계속되면 시작.bat을 다시 실행하세요.'
NOT_PICKED = ('{age}초째 답할 AI 에이전트가 질문을 맡지 않았습니다 — AI 에이전트에 연결할 수 없습니다. 시작.bat을 다시 실행하면 이어서 답합니다'
              '(처리 과정 보기에서 닫을 수도 있습니다).')
BUSY = '{age}초째 대기 중 — AI 에이전트는 켜져 있습니다(앞 작업을 처리하는 중일 수 있습니다).'
RUNTIME_NOT_READY = '질문을 받을 처리 흐름 서비스가 아직 켜지는 중입니다. 1분 뒤 다시 보내세요.'
BAD_REQUEST_ID = '요청 번호의 형식이 올바르지 않습니다 — 화면을 새로 고친 뒤 다시 보내세요.'


def request_uuid(value) -> str:
    """화면이 만든 요청 번호(UUID) — 형식이 틀리면 학생이 읽을 사유로(라이브러리 영문 오류를 그대로 보이지 않는다)."""
    try:
        return str(uuid.UUID(str(value)))
    except ValueError:
        raise ValueError(BAD_REQUEST_ID) from None


def readiness(worker_probe) -> dict:
    """질문을 받을 수 있나 — AI 에이전트 실행 서비스이 상태 확인(/health)에 「켜짐」으로 답하는가(켜지는 중 · 오류면 503 이라 닿지 않음으로 온다)."""
    w = worker_probe()
    health = w.get('health') or {}
    ready = bool(w.get('reachable'))
    return {'ready': ready, 'reason': None if ready else NOT_READY,
            'worker': {'reachable': ready, 'agents': w.get('agents') or [],
                       # 키 없는 PC: 저장된 답이 있는 질문만 답한다 — 화면이 예시로 보인다
                       'ai_mode': health.get('ai_mode'), 'replay_questions': health.get('replay_questions') or []}}


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


def agent_identity(settings) -> dict:
    """실행에 영향을 주는 에이전트 설정(표시 이름 · 시각은 뺀다). 질문 묶음 · AI 워커의 같은 요청 판정이 같은 함수를 쓴다."""
    from dataclasses import asdict
    value = asdict(settings)
    value['profile'] = {k:v for k,v in (value.get('profile') or {}).items()
                        if k not in {'username','name','created_at','updated_at'}}
    return value


def execution_binding(question, settings, *, version):
    """Bind a question to the execution-relevant agent settings, not its label. version = the question definition's version."""
    from .course_ledger import digest
    return digest({'question':question,'agent':agent_identity(settings),'version':version})


def start(rt, question, agent_id=None, by=None, request_id=None, *, definitions_dir, worker_probe) -> dict:
    """질문 하나 = 처리 건 하나. 같은 request_id로 다시 보내면 같은 처리 건을 돌려준다(중복 클릭 · 재시도)."""
    q = check_question(question)
    agent = check_agent(rt.repo, rt.tenant_id, agent_id)
    ready = readiness(worker_probe)
    if not ready['ready']:
        raise WorkerUnavailable(ready['reason'])
    request_id = request_uuid(request_id) if request_id else str(uuid.uuid4())
    raw = definition(definitions_dir)
    rt.register_definition(raw)
    version = raw['version']
    event_id = EVENT_PREFIX + request_id
    from .agents_store import agent_settings
    binding = execution_binding(q, agent_settings(rt.repo,rt.tenant_id,agent['id']), version=version)
    previous = rt.repo.find_event_instance(rt.tenant_id,DEFINITION_ID,event_id)
    if previous:
        endpoint = next((b.get('endpoint') for b in previous.get('role_bindings',[]) if b.get('name')==ROLE),None)
        if engine.variables(previous).get('question') != q or endpoint != agent['id']:
            raise ValueError('이 요청 ID는 다른 질문·에이전트에 이미 사용됐습니다')
        previous_binding = (engine.variables(previous).get('_runtime_coalescing') or {}).get('key')
        if previous_binding != binding:
            raise ValueError('이 요청 ID는 다른 에이전트 조건에 사용됐거나 기존 조건을 확인할 수 없습니다. 기존 질문을 확인하거나 새 질문을 보내세요')
        return view(rt,previous['proc_inst_id'])
    from .inbox import actor_or_400
    asked_by = actor_or_400(by)[:120]
    inst = rt.start_definition(DEFINITION_ID, version, event_id, values={'question': q, 'asked_by': asked_by},
                               name='질문 · ' + (q if len(q) <= 40 else q[:40] + '…'), role_endpoints={ROLE: agent['id']},
                               _coalesce_key=binding)
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


def _failed(output, is_error, tool=None) -> str | None:
    if is_error:
        return '도구가 오류를 돌려줬습니다'
    env = _envelope(output)
    if isinstance(env, dict):
        if env.get('isError') is True or env.get('is_error') is True:
            return '도구가 오류를 돌려줬습니다'
        if env.get('error'):
            return f"도구 오류: {str(env['error'])[:200]}"
        # mcp-neo4j-cypher returns JSON rows as TextContent, which the CLI
        # adapter may wrap in {result: "[...]"}. This is data, not our
        # enterprise/DMN result-status envelope. Preserve explicit errors.
        if (not env.get('error') and not env.get('isError') and
                short_tool(str(tool or '')).endswith(('/read_neo4j_cypher','/get_neo4j_schema')) and isinstance(env.get('result'), str)):
            try:
                rows = json.loads(env['result'])
                if isinstance(rows,dict) and isinstance(rows.get('rows'),list) and not any(rows.get(k) for k in ('error','isError','is_error')):
                    if not rows['rows'] and rows.get('truncated'):
                        return '응답 한도로 결과가 생략됐습니다. 필요한 이름·속성을 좁혀 추가 조회하세요'
                    rows=rows['rows']
                if isinstance(rows, list) and all(isinstance(row, dict) for row in rows):
                    return None
            except ValueError:
                pass
        if isinstance(env.get('result'), str) and env['result'] != 'ok':
            return f"도구가 거절했습니다: {str(env.get('message') or env['result'])[:200]}"
    return None


def _preview(value, n=600) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    text = ' '.join(str(text).split())
    return text if len(text) <= n else text[:n] + '…'


def _event_value(event, direction, payload_loader):
    """Resolve only the original bound to this case; previews never count as complete evidence."""
    data = event.get('data') or {}
    value = data.get(direction)
    ref = data.get('full_' + direction) or {}
    complete = value is not None and not data.get(direction + '_truncated') and not ref
    if payload_loader and ref.get('stored') and ref.get('ref'):
        row = payload_loader(ref['ref'])
        if row and row.get('proc_inst_id') == event.get('proc_inst_id') and row.get('proc_inst_id'):
            value = row.get('content')
            complete = not (row.get('meta') or {}).get('cut', False) and not ref.get('cut', False)
            if direction == 'input' and isinstance(value, str):
                try:
                    value = json.loads(value)
                except ValueError:
                    complete = False
    envelope = _envelope(value)
    if direction == 'output' and isinstance(envelope, dict) and envelope.get('truncated') is True:
        complete = False
    return value, complete


def tool_calls(events, payload_loader=None) -> list[dict]:
    """이 작업의 도구 호출(시작 · 끝을 tool_use_id로 짝지음), 일어난 순서대로."""
    calls, by_id = [], {}
    for e in events:
        d = e.get('data') or {}
        if e.get('event_type') == 'tool_usage_started':
            actual_input, input_complete = _event_value(e, 'input', payload_loader)
            c = {'id': d.get('tool_use_id') or e.get('id'), 'tool': short_tool(d.get('tool')), 'raw_tool': d.get('tool'),
                 'data': is_data_tool(d.get('tool')), 'input': d.get('input'), 'input_text': _preview(d.get('input')),
                 '_input': actual_input if input_complete else None,
                 'started': e.get('timestamp'), 'finished': None, 'running': True, 'ok': None, 'output_text': None, 'problem': None}
            calls.append(c)
            by_id[c['id']] = c
        elif e.get('event_type') == 'tool_usage_finished':
            c = by_id.get(d.get('tool_use_id'))
            if c is None:
                c = {'id': d.get('tool_use_id') or e.get('id'), 'tool': short_tool(d.get('tool')), 'raw_tool': d.get('tool'),
                     'data': is_data_tool(d.get('tool')), 'input': None, 'input_text': '', 'started': None}
                calls.append(c)
            actual_output, output_complete = _event_value(e, 'output', payload_loader)
            problem = _failed(actual_output, d.get('is_error'), c.get('tool'))
            c.update(finished=e.get('timestamp'), running=False, ok=problem is None, problem=problem,
                     output_text=_preview(actual_output), output_complete=output_complete, _output=actual_output)
    return calls


def _norm(text) -> str:
    # Compare the entire query. Do not fold quoted values/identifiers or accept
    # substrings (a different WHERE clause must never become verified evidence).
    return str(text or '').strip().rstrip(';').strip()


def _queries(value):
    """Legacy query-text contracts; generic argument objects use exact matching."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key in ('sql', 'query', 'cypher', 'promql'):
            if isinstance(value.get(key), str):
                yield value[key]


def _matches(item, call) -> bool:
    def advertised(name):
        # The model may write a hyphenated MCP server name with underscores
        # when it cites evidence. Preserve the complete server and tool identity;
        # verdict rejects collisions instead of guessing between real servers.
        server, sep, tool = short_tool(str(name or '').strip()).partition('/')
        return (server.replace('-', '_'), tool) if sep else None
    claimed = advertised(item.get('tool'))
    if claimed is None or claimed != advertised(call.get('tool')):
        return False
    query = item.get('query')
    # Models can serialize structured MCP arguments as JSON text. Accept only
    # an object and compare every field exactly; SQL strings remain unchanged.
    if isinstance(query, str) and query.lstrip().startswith('{'):
        try:
            parsed = json.loads(query)
            if isinstance(parsed, dict):
                query = parsed
        except (ValueError, TypeError):
            pass
    if isinstance(query, dict):
        actual = call.get('_input', call.get('input'))
        if not isinstance(actual, dict):
            return False
        try:
            # JSON equality keeps bool distinct from number and checks every
            # argument recursively, including empty objects and list ordering.
            if json.dumps(query, sort_keys=True, allow_nan=False) == json.dumps(actual, sort_keys=True, allow_nan=False):
                return True
        except (TypeError, ValueError):
            return False
        # enterprise/query executes the shared guarded, normalized SQL, and
        # reports that exact statement in its complete successful response.
        # Match equivalent spellings (e.g. now() / CURRENT_TIMESTAMP) only if
        # both guarded inputs equal that authoritative executed statement.
        if (advertised(call.get('tool')) == ('enterprise','query') and set(query) == {'sql'} and set(actual) == {'sql'}
                and call.get('ok') is True and call.get('output_complete') is True):
            response = _envelope(call.get('_output'))
            doc = response.get('document') if isinstance(response, dict) and response.get('result') == 'ok' else None
            if isinstance(doc, dict) and isinstance(doc.get('statement'), str):
                try:
                    from hydcommon.sql_read import guard
                    return guard(query['sql']) == guard(actual['sql']) == doc['statement']
                except (ValueError, TypeError):
                    return False
        return False
    q = _norm(query)
    if not isinstance(query, str) or not q:
        return False
    for s in _queries(call.get('_input', call.get('input'))):
        n = _norm(s)
        if n and n == q:
            return True
    return False


_ID_PATTERN = (r'(?<![A-Za-z0-9_])(?:[a-z][a-z_]*:[a-zA-Z0-9_:-]+|[A-Z]{2,}-\d+(?:-\d+)*(?![A-Za-z0-9_])'
               # 날짜 · 시각은 통째로 하나의 값이다(2026-10-30 을 2026 · 10 · 30 낱개 수로 쪼개지 않는다)
               r'|\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?|(?<![\d:])\d{1,2}:\d{2}(?::\d{2})?(?![\d:]))')
_NUMBER = r'(?<![\d.])-?\d[\d,]*(?:\.\d+)?(?![\d.])'


def literal_facts(value) -> dict[str, str]:
    """글 속 수치 · ID · 날짜 → {대조용 정규화 값: 글에 적힌 그대로}. 수치는 쉼표 · 끝자리 0을 지워 견주고(70 = 70.0 = 70.00),
    화면에는 답에 적힌 글자를 그대로 돌려준다(정규화 값 7E+1 같은 내부 표기를 보이지 않는다 — P3-12)."""
    from decimal import Decimal, InvalidOperation
    import re
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    # ASCII edges, not \b: a Korean particle right after an id ("SOP-COOL-13이며") is a word character for \b.
    out = {m: m for m in re.findall(_ID_PATTERN, text)}
    # Digits inside an identifier or a date are part of it, not an independent measurement (HYD-01 must not also become -1).
    numeric_text = re.sub(_ID_PATTERN, lambda match: ' ' * len(match.group()), text)
    for raw in re.findall(_NUMBER, numeric_text):
        try:
            key = format(Decimal(raw.replace(',', '')).normalize(), 'f')
        except InvalidOperation:
            continue
        out.setdefault(key, raw)
    return out


def result_comparison(claimed, calls):
    """A warning about literal numbers/ids, never a semantic truth certificate (units/calculations may differ)."""
    originals = [c.get('_output') for c in calls if c.get('output_complete')]
    if not originals or len(originals) != len(calls):
        return {'status': 'unavailable', 'note': '조회 결과 원문 전체가 없어 답의 수치·ID를 대조하지 못했습니다'}
    present = set().union(*(literal_facts(x) for x in originals))
    stated = literal_facts(claimed)
    missing = [stated[k] for k in sorted(stated) if k not in present]
    return {'status': 'review' if missing else 'literal_match', 'missing': missing,
            'note': ('조회 결과에서 찾지 못한 수치·ID가 있습니다. 계산·단위 환산 또는 잘못 옮긴 값인지 확인하세요' if missing else
                     '수치·ID의 표기만 대조했습니다. 답의 의미와 계산이 맞다는 보증은 아닙니다')}


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
        matches = [c for c in data_ok if _matches(item, c)]
        # Repeated calls to one real tool are valid; distinct servers collapsing
        # to the same advertised name with identical arguments are ambiguous.
        identities = {c['tool'] for c in matches}
        hit = matches[0] if len(identities) == 1 else None
        evidence.append({'tool': item.get('tool'), 'query': item.get('query'), 'result': item.get('result'),
                         'verified': hit is not None, 'call': hit and hit['id'],
                         'actual_result': hit and hit.get('output_text'),
                         'result_check': result_comparison(item.get('result'), matches) if hit else None})
    if not any(e['verified'] for e in evidence):
        return {'kind': 'unanswerable', 'by': 'server', 'claimed': claimed, 'evidence': evidence,
                'reason': (f'에이전트가 근거로 적은 질의 {len(evidence)}개를 이 작업의 실제 도구 호출 기록(성공 {len(data_ok)}건)에서 찾지 못했습니다 — '
                           '근거를 확인할 수 없어 답으로 보이지 않습니다')}
    return {'kind': 'answered', 'answer': claimed, 'evidence': evidence, 'note': output.get('note'),
            'answer_check': result_comparison(claimed, [c for c in data_ok if any(e['call'] == c['id'] for e in evidence)]),
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


def retry(rt, proc_inst_id, request_id, by, reason):
    """Explicit recovery of the same failed question; never reset its budget."""
    request_id = request_uuid(request_id)
    if not isinstance(reason,str) or not reason.strip() or len(reason)>1000:
        raise ValueError('재개 사유를 1000자 이내로 적으세요')
    with rt._transition(proc_inst_id):
        inst = _instance(rt,proc_inst_id)
        if not by or engine.variables(inst).get('asked_by') != by:
            raise PermissionError('질문한 사람과 재개 요청자가 다릅니다')
        wi = _task(rt,inst)
        if not wi:raise ValueError('질문의 작업을 찾을 수 없습니다')
        history = [e for e in rt.repo.list_events(todo_id=wi['id'])
                   if isinstance(e.get('data'),dict) and e['data'].get('ask_retry_id')]
        previous = next((e for e in history if e['data']['ask_retry_id']==request_id),None)
        if previous:
            if previous['data'].get('reason') != reason or previous['data'].get('by') != by:
                raise ValueError('같은 재개 요청 ID의 내용이 다릅니다')
            return view(rt,proc_inst_id)
        if inst['status']!='RUNNING' or wi['status']!='IN_PROGRESS' or wi.get('draft_status')!='FAILED':
            raise ValueError('실패해 멈춘 질문만 같은 작업으로 재개할 수 있습니다')
        if len(history)>=2:raise ValueError('같은 질문의 재개는 2회까지입니다. 처리 과정의 원문을 시스템 관리자에게 보여 주세요')
        rt.repo.record_events([dict(job_id='ask-retry:'+request_id,todo_id=wi['id'],proc_inst_id=proc_inst_id,
            crew_type='human',event_type='task_working',data=dict(type='notice',name='실패한 질문 재개',
            ask_retry_id=request_id,by=by,reason=reason,retry_number=len(history)+1))])
        wi['feedback'] = dict(wi.get('feedback') or {},text=reason.strip(),by=by,kind='human_retry')
        wi.update(draft_status='FB_REQUESTED',consumer=None,lease_until=None)
        rt.repo.update_workitem(wi)
        rt._after_commit(rt._project,inst)
        return view(rt,proc_inst_id)


def _error_reason(events) -> str | None:
    for e in reversed(events):
        if e.get('event_type') == 'error':
            d = e.get('data') or {}
            # 학생이 읽는 칸은 friendly 하나다(워커가 쓴다 — 내부어 · 예외 이름 없음). 원문(raw_error)은 처리 과정의 접힌 칸에만 있다
            return str(d.get('friendly') or d.get('name') or '')[:600] or None
    return None


def _state(inst, wi, events, now=None) -> tuple[str, str]:
    if wi is None:
        return 'broken', '이 질문의 처리 단계를 찾지 못했습니다 — 처리 과정 보기를 시스템 관리자에게 보여 주세요'
    # P2 (audit2 2026-10-23): 사람이 [닫기]로 닫은 질문은 처리 건이 COMPLETED(기술 끝 closed-by-human)이고 작업이 CANCELLED 다 — 처리 건
    # 상태만 보고 '답이 나왔습니다'로 읽으면 답 없는 질문에 서버 판정까지 붙었다. 닫힘을 먼저 본다.
    if (wi['status'] == 'CANCELLED' or inst.get('status') in ('CANCELLED', 'TERMINATED')
            or inst.get('end_event') == InstanceRuntime.HUMAN_CLOSE_END_EVENT):
        return 'closed', '사람이 닫은 질문입니다' + (f" — {wi.get('log')}" if wi.get('log') else '')
    if wi['status'] == 'DONE' or inst.get('status') == 'COMPLETED':
        return 'done', '답이 나왔습니다'
    if wi['status'] == 'PENDING':
        return 'failed', '답을 받지 못했습니다: ' + (wi.get('log') or _error_reason(events) or '처리 흐름이 에이전트의 답을 받지 못해 멈췄습니다')
    ds = wi.get('draft_status')
    fb = wi.get('feedback') if isinstance(wi.get('feedback'), dict) else {}
    if ds == 'FAILED':
        return 'failed', _error_reason(events) or '에이전트 실행이 실패했습니다(사유 기록 없음). 처리 과정을 시스템 관리자에게 보여 주세요.'
    if ds == 'HUMAN_ASKED':
        return 'asking', '에이전트가 사람에게 묻고 기다립니다 (처리 과정 보기에서 답할 수 있습니다)'
    if ds == 'FB_REQUESTED' and fb.get('kind') == 'validation':
        return 'correcting', '에이전트의 답이 정해진 답 형식과 달라 다시 고쳐 쓰라고 돌려보냈습니다: ' + str((fb.get('history') or [''])[-1])[:300]
    if wi['status'] == 'SUBMITTED':
        return 'submitted', '에이전트가 답을 냈습니다 — 처리 흐름이 받는 중입니다'
    if ds == 'STARTED':
        return 'running', '에이전트가 조회하는 중'
    return 'waiting', '답할 AI 에이전트가 아직 질문을 맡지 않았습니다'


def view(rt, proc_inst_id, *, worker_probe=None, now=None) -> dict:
    """질문 하나의 지금 상태. 아무도 맡지 않은 채 오래 기다렸으면 워커 연결을 확인해 까닭을 붙인다 — 그 확인은 몇 초 걸릴 수 있어서(워커가
    바쁘면 답이 늦다), 확인하는 동안 에이전트가 질문을 맡았는지 다시 읽고 그 상태로 답한다. 전에는 확인 전에 읽은 「대기」를 확인이 끝난 뒤에
    돌려줘, 처리 과정에는 이미 에이전트의 조회가 흘러나오는데 상태는 뒤늦게 「아직 질문을 맡지 않았습니다」로 왔다."""
    out = _view(rt, proc_inst_id, now)
    waited = out.pop('_waited_s')
    if out['state'] == 'waiting' and worker_probe is not None and waited is not None and waited >= WAIT_PROBE_AFTER_S:
        reachable = worker_probe().get('reachable')
        out = _view(rt, proc_inst_id, now)
        waited = out.pop('_waited_s')
        if out['state'] == 'waiting' and waited is not None:
            out['message'] = (BUSY if reachable else NOT_PICKED).format(age=int(waited))
    return out


def _view(rt, proc_inst_id, now=None) -> dict:
    inst = _instance(rt, proc_inst_id)
    wi = _task(rt, inst)
    events = rt.repo.list_events(todo_id=wi['id']) if wi else []
    values = engine.variables(inst)
    state, message = _state(inst, wi, events, now)
    performer = (wi or {}).get('user_id') or next((b.get('endpoint') for b in inst.get('role_bindings') or [] if b.get('name') == ROLE), None)
    user = next(iter(rt.repo.list_users([performer], rt.tenant_id)), None) if performer else None
    calls = tool_calls(events, rt.repo.get_event_payload)
    out = {'id': inst['proc_inst_id'], 'question': values.get('question'), 'asked_by': values.get('asked_by'),
           'agent': {'id': performer, 'name': (user or {}).get('username') or performer},
           'started': inst.get('start_date'), 'ended': inst.get('end_date'), 'state': state, 'message': message,
           'workitem': (wi or {}).get('id'), 'tool_calls': [{k:v for k,v in c.items() if not k.startswith('_')} for c in calls],
           'counts': {'calls': len(calls), 'data': sum(1 for c in calls if c['data']), 'ok': sum(1 for c in calls if c['data'] and c['ok']),
                      'running': sum(1 for c in calls if c['running'])},
           'link': f"#/instances/{inst['proc_inst_id']}" + (f"/task/{wi['id']}" if wi else ''), 'result': None}
    if state == 'done':
        out['result'] = verdict((wi or {}).get('output'), calls)
        if out['result'].get('kind') == 'unanswerable':
            # 2026-10-25 수업 한 바퀴: 답하지 못한 질문의 머리말이 「답이 나왔습니다」였다(아래 카드는 「답할 수 없음」)
            out['message'] = '답할 수 없음 — 아래 이유를 확인하세요'
    out['_waited_s'] = _age_s((wi or {}).get('start_date') or inst.get('start_date'), now) if state == 'waiting' else None
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
                    | {'verdict': res.get('kind'), 'calls': v['counts']['calls']})     # 본문의 「도구 호출 N」과 같은 기준(모든 도구)
    return rows


def reset(rt, by=None) -> dict:
    """기준으로 되돌리기(B5 영역): 끝난 질문 기록만 목록에서 지운다(행은 남기고 is_deleted). 진행 중인 질문은 남긴다. 실패해 멈춘 질문은
    닫은 뒤 지운다(_close_stopped). 질문 정의 · 에이전트 · 업무 DB · 지식은 질문으로 바뀌지 않으므로 되돌릴 것이 없다.
    by: 지우기를 누른 담당자(사람 사용자 id). 없으면 이 PC의 담당자(사람 사용자가 한 명일 때)다."""
    closer = by or _the_person(rt)
    runs = rt.repo.list_source_runs(rt.tenant_id, DEFINITION_ID, EVENT_PREFIX, limit=1000)
    done = [r['proc_inst_id'] for r in runs if r.get('status') != 'RUNNING']
    closed = [r['proc_inst_id'] for r in runs if r.get('status') == 'RUNNING' and closer and _close_stopped(rt, r['proc_inst_id'], closer)]
    hidden = rt.repo.hide_instances(rt.tenant_id, DEFINITION_ID, done + closed) if done or closed else 0
    kept = len(runs) - len(done) - len(closed)
    return {'hidden': hidden, 'closed_stopped': len(closed), 'kept_running': kept,
            'note': '끝난 질문 기록을 목록에서 지웠습니다. 질문 정의 · 에이전트 · 업무 DB · 지식은 질문으로 바뀌지 않아 그대로입니다'
                    + (f' · 실패해 멈춰 있던 질문 {len(closed)}건은 닫고 지웠습니다' if closed else '')
                    + (f' · 진행 중인 질문 {kept}건은 끝난 뒤 지울 수 있습니다' if kept else '')}


STOPPED_CLOSE_REASON = '끝난 질문 기록 지우기 — 실패해 멈춘 질문을 닫음'


def _the_person(rt) -> str | None:
    """이 PC의 담당자 id — 사람 사용자가 한 명일 때만(이 시스템에는 로그인이 없고 쓰는 사람은 늘 담당자 한 명이다, inbox 머리말). 여럿이면
    누가 눌렀는지 알 수 없으므로 None(이름을 지어 넣지 않는다)."""
    people = [u['id'] for u in rt.repo.list_users(None, rt.tenant_id) if str(u.get('id') or '').startswith('user:') and not u.get('is_agent')]
    return people[0] if len(people) == 1 else None


def _close_stopped(rt, proc_inst_id, by) -> bool:
    """실패 · 취소 · 보류로 멈춘 질문(답이 나올 수 없는 채 처리 건만 진행 중으로 남은 것)을 닫는다 → 닫았는가. 화면에는 「실패」인데 처리 건이
    진행 중이라 [끝난 기록 지우기]가 지우지 못했고, 처리 건 목록에도 끝나지 않은 건으로 남았다(재생 모드에서 저장된 응답이 없는 질문은
    다시 물어도 같은 답이라 닫는 것 말고 할 일이 없다). 처리 건의 「단계 닫기」와 같은 함수로 닫는다(닫은 사람 · 사유가 처리 기록에 남는다).
    아직 도는 질문(대기 · 조회 중 · 사람에게 묻는 중)은 닫지 않는다."""
    try:
        inst = _instance(rt, proc_inst_id)
    except KeyError:
        return False
    wi = _task(rt, inst)
    if wi is None or InstanceRuntime.stuck(wi) is None:
        return False
    try:
        rt.close_agent_task(wi['id'], by, STOPPED_CLOSE_REASON)
    except (ValueError, PermissionError, KeyError, LookupError) as exc:
        log.warning('멈춘 질문 %s 을(를) 닫지 못해 남깁니다: %s', proc_inst_id, exc)
        return False
    return (rt.repo.get_instance(proc_inst_id) or {}).get('status') != 'RUNNING'


# ---------------------------------------------------------------- HTTP
class AskReq(BaseModel):
    question: str
    agent: str | None = None
    by: str | None = None
    request_id: str | None = None


class AskResetReq(BaseModel):
    by: str | None = None       # 지우기를 누른 담당자 — 없으면 이 PC의 담당자(reset)


class AskRetryReq(BaseModel):
    model_config = {'extra':'forbid'}
    request_id: str
    by: str
    reason: str


def register(app, *, runtime_factory, definitions_dir, worker_probe):
    """worker_probe: () -> instance_mode.worker_status() 모양({'reachable', 'health', 'agents', …})."""
    import asyncio
    from fastapi import HTTPException

    def rt():
        r = runtime_factory()
        if r is None:
            raise HTTPException(503, RUNTIME_NOT_READY)
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
        return await run(lambda: readiness(worker_probe) | {'agents': agents(r.repo, r.tenant_id), 'default': DEFAULT_AGENT})

    @app.get('/api/ask')
    async def ask_history(limit: int = 30):
        r = rt()
        return await run(lambda: history(r, limit))

    @app.post('/api/ask', status_code=201)
    async def ask_start(req: AskReq):
        r = rt()
        return await run(lambda: start(r, req.question, req.agent, req.by, req.request_id, definitions_dir=definitions_dir,
                                       worker_probe=worker_probe))

    @app.post('/api/ask/reset')
    async def ask_reset(req: AskResetReq | None = None):
        r = rt()
        try:
            return await run(lambda: reset(r, req.by if req else None))
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from None

    @app.post('/api/ask/{proc_inst_id}/retry')
    async def ask_retry(proc_inst_id: str, req: AskRetryReq):
        try:
            return await run(lambda: retry(rt(),proc_inst_id,req.request_id,req.by,req.reason))
        except PermissionError as exc:
            raise HTTPException(403,str(exc)) from None

    @app.get('/api/ask/{proc_inst_id}')
    async def ask_view(proc_inst_id: str):
        r = rt()
        return await run(lambda: view(r, proc_inst_id, worker_probe=worker_probe))
