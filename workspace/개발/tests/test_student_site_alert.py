"""학생 현장(유압이 아닌 설비)의 경보로 학생 흐름이 끝까지 — 내 경보 종류 선언 → 흐름 가져오기 · 배포 → 바깥 프로그램의 경보(HTTP) → 판단(내 에이전트가
내 시스템을 읽음) → 사람 승인 · 반려 → 승인 뒤 MCP 호출(내 시스템에 정비 기록) → 결과 보고 → 바깥 프로그램의 해제(HTTP).

학생 쪽 자리는 공개 데이터(MetroPT-3 공기 공급 장치)에서 잰 모양으로 만든 데이터와 학생 감지 규칙 · 도구 서버를 작게 옮긴 것이다(student_apu.py 머리말). 유압 태그 ·
가상 설비 시계열은 이 길 어디에도 없다. AI 는 부르지 않는다 — Claude Code 자리(ApuCli)는 워커가 준 허용 목록의 도구만 부르는 대역이고, 모델 호출은
강의 중계 대역(relay)을 지난다(test_student_system_link 와 같은 규칙). 단계는 PBL(그 시험 파일의 pbl 고정물 — 시험용 키로 서명한 단계 선언).
"""
import json
import uuid
from pathlib import Path

import pytest

import student_apu as apu
from conftest import OPERATOR, STUDENT_HOST, TENANT
from procsvc import approval_part, definition, mcp_registry
from procsvc import agent_authoring as A
from procsvc.bpmn_store import FlowStore
from test_student_system_link import pbl, _ok          # noqa: F401 — pbl 은 고정물(PBL 단계를 연다)

ME = OPERATOR['by']
SERVER = 'my-apu'
ROLE_NAME, ROLE_ID = '차량 정비 담당', 'role:apu-maint'
OPTIONS = [{'slot': 'A', 'sop': 'SOP-APU-03', 'action': '공기 배관 누설 점검 · 체결부 조임', 'reason': '부하 운전 비율 1.0 · 오일 85 ℃ 이상이 60분'},
           {'slot': 'B', 'sop': 'SOP-APU-01', 'action': '다음 정기 점검까지 관찰', 'reason': '운행 중단 없이'}]


@pytest.fixture
def site(tmp_path):
    db = apu.build(tmp_path / 'apu.sqlite3')
    s = apu.ApuSystem(db, STUDENT_HOST)
    yield s
    s.served.close()
    db.close()


class ApuCli:
    """Claude Code 자리 — 작업 폴더 .mcp.json 의 내 서버에, 허용 목록에 있고 금지 목록에 없는 도구만 부른다. 모델 호출 자리(관문)를 한 번 지나고,
    읽은 창 요약으로 조치 후보 둘을 결과 파일에 쓴다. 쓰기 도구도 부르려 해 본다(워커가 막아야 한다)."""
    accepts_check_stop = True

    def __init__(self):
        self.called, self.refused = [], []

    def __call__(self, provider, request, env, *, check_stop=None):
        import urllib.request
        from cliagents import ExecEvent, ExecEventKind
        from test_student_system_link import StudentCli
        session = str(uuid.uuid4())
        body = json.dumps({'model': request.model, 'max_tokens': 64, 'messages': [{'role': 'user', 'content': '다음 단계'}]}).encode()
        with urllib.request.urlopen(urllib.request.Request(env['ANTHROPIC_BASE_URL'] + '/v1/messages', data=body, method='POST', headers={
                'x-api-key': env['ANTHROPIC_API_KEY'], 'content-type': 'application/json'}), timeout=15) as response:
            response.read()
        servers = json.loads((Path(request.workdir) / '.mcp.json').read_text(encoding='utf8'))['mcpServers']
        allowed, denied = StudentCli._flag(request.extra_args, '--allowedTools'), StudentCli._flag(request.extra_args, '--disallowedTools')
        seen = None
        for tool, args in (('apu_windows', {'hours': 1.0}), ('record_maintenance', {'case_id': 'x', 'sop': 'x', 'action': 'x', 'performed_by': 'x',
                                                                                     'idempotency_key': 'x'})):
            name = f'mcp__{SERVER}__{tool}'
            if SERVER not in servers or name not in allowed or name in denied:
                self.refused.append(name)
                continue
            use = str(uuid.uuid4())
            yield ExecEvent(kind=ExecEventKind.TOOL_START, tool=name, tool_input=args, tool_use_id=use, session_id=session)
            out = StudentCli._call(servers[SERVER], tool, args)
            self.called.append(name)
            seen = out if tool == 'apu_windows' else seen
            yield ExecEvent(kind=ExecEventKind.TOOL_END, tool=name, tool_output=json.dumps(out, ensure_ascii=False), tool_use_id=use, session_id=session)
        if seen is None:
            yield ExecEvent(kind=ExecEventKind.RESULT, is_error=True, session_id=session, text='창 요약을 읽을 도구가 없습니다')
            return
        hot = [w for w in seen['windows'] if apu.leaking(w)]
        target = Path(request.workdir) / 'output' / 'result.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({'proposal': {'options': OPTIONS, 'recommended': 'A', 'evidence': f'누설 의심 창 {len(hot)}개'}},
                                     ensure_ascii=False), encoding='utf8')
        yield ExecEvent(kind=ExecEventKind.RESULT, session_id=session, text='조치 후보를 냈습니다')


def _bpmn(pid, after='report'):
    """after = 정비 기록 뒤의 길: 'report'(바로 결과 보고) · 'wait'(12분 기다린 뒤 결과 보고 — 승인 뒤 · 닫히기 전 구간이 있다) ·
    'check'(사람이 회복을 확인하고, 아니면 새 조치 후보 · 새 승인으로 되돌아간다) · 'late'(12분 기다림에 5분 경계 타이머 — 넘으면 지연 보고)."""
    tail = {'report': '<bpmn:sequenceFlow id="F4" sourceRef="T_record" targetRef="R_ok"/>',
            'wait': '<bpmn:serviceTask id="T_wait" name="정비 뒤 기다림"/><bpmn:sequenceFlow id="F4" sourceRef="T_record" targetRef="T_wait"/>'
                    '<bpmn:sequenceFlow id="F4b" sourceRef="T_wait" targetRef="R_ok"/>',
            'late': '<bpmn:serviceTask id="T_wait" name="정비 뒤 기다림"/><bpmn:sequenceFlow id="F4" sourceRef="T_record" targetRef="T_wait"/>'
                    '<bpmn:sequenceFlow id="F4b" sourceRef="T_wait" targetRef="R_ok"/>'
                    '<bpmn:boundaryEvent id="B_slow" name="지켜보기 시간 초과" attachedToRef="T_wait"><bpmn:timerEventDefinition id="TD1"/></bpmn:boundaryEvent>'
                    '<bpmn:serviceTask id="R_slow" name="결과 보고: 지연"/><bpmn:endEvent id="E_slow" name="지켜보기 시간 초과"/>'
                    '<bpmn:sequenceFlow id="F_slow" sourceRef="B_slow" targetRef="R_slow"/><bpmn:sequenceFlow id="F_slow2" sourceRef="R_slow" targetRef="E_slow"/>',
            'check': '<bpmn:userTask id="T_check" name="회복 확인"/><bpmn:exclusiveGateway id="G_fix" name="회복?"/>'
                     '<bpmn:sequenceFlow id="F4" sourceRef="T_record" targetRef="T_check"/><bpmn:sequenceFlow id="F4b" sourceRef="T_check" targetRef="G_fix"/>'
                     '<bpmn:sequenceFlow id="F_fixed" name="회복" sourceRef="G_fix" targetRef="R_ok"/>'
                     '<bpmn:sequenceFlow id="F_again" name="다시" sourceRef="G_fix" targetRef="T_agent"/>'}[after]
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" id="D_{pid}"><bpmn:process id="{pid}" name="공기 누설 대응">
  <bpmn:startEvent id="Start" name="공기 누설 의심 경보"><bpmn:messageEventDefinition id="M1"/></bpmn:startEvent>
  <bpmn:userTask id="T_agent" name="운영 데이터 확인 · 조치 후보"/>
  <bpmn:userTask id="T_ok" name="정비 승인"/>
  <bpmn:exclusiveGateway id="G_ok" name="승인?"/>
  <bpmn:serviceTask id="T_record" name="정비 기록 남기기"/>
  <bpmn:serviceTask id="R_ok" name="결과 보고: 정상"/>
  <bpmn:serviceTask id="R_no" name="결과 보고: 반려"/>
  <bpmn:endEvent id="E_done" name="정비 기록 완료"/>
  <bpmn:endEvent id="E_no" name="반려"/>
  <bpmn:sequenceFlow id="F1" sourceRef="Start" targetRef="T_agent"/><bpmn:sequenceFlow id="F2" sourceRef="T_agent" targetRef="T_ok"/>
  <bpmn:sequenceFlow id="F3" sourceRef="T_ok" targetRef="G_ok"/>
  <bpmn:sequenceFlow id="F_yes" name="승인" sourceRef="G_ok" targetRef="T_record"/>
  <bpmn:sequenceFlow id="F_no" name="반려" sourceRef="G_ok" targetRef="R_no"/>
  {tail}<bpmn:sequenceFlow id="F5" sourceRef="R_ok" targetRef="E_done"/>
  <bpmn:sequenceFlow id="F6" sourceRef="R_no" targetRef="E_no"/>
</bpmn:process></bpmn:definitions>'''


def _mapping(agent, after='report'):
    m = _base_mapping(agent)
    if after in ('wait', 'late'):
        m['tasks']['T_wait'] = {'part': 'svc:wait', 'config': {'duration': WAIT, 'label': '정비 뒤 지켜보기'}}
    if after == 'late':
        m['timers']['B_slow'] = LATE
        m['tasks']['R_slow'] = {'part': 'svc:report', 'config': {'outcome': '지연', 'title': '{asset} 공기 누설 대응 결과',
                                                                  'summary': '정비 뒤 지켜보기가 정한 시간을 넘었습니다'}}
    if after == 'check':
        m['tasks']['T_check'] = {'part': 'human', 'role': ROLE_NAME, 'fields': [{'key': 'fixed', 'text': '회복했는가(예 · 아니오)', 'type': 'text'}]}
        m['flows'].update(F_fixed={'var': 'fixed', 'op': '==', 'value': '예'}, F_again={'default': True})
    return m


WAIT, WAIT_S = 'PT12M', 12 * 60        # 내 현장의 처리 건은 벽시계로 기다린다(가상 설비가 아니다) — 12분은 12분
LATE, LATE_S = 'PT5M', 5 * 60          # 그 기다림에 붙인 경계 타이머도 벽시계 — 5분은 5분


def _base_mapping(agent):
    return {'name': '공기 누설 대응', 'lanes': {}, 'timers': {},
            'start': {'kind': 'alert', 'patterns': [], 'declared': [{'pattern': apu.PATTERN, 'name': apu.NAME}]},
            'tasks': {'T_agent': {'part': 'agent', 'agent': agent, 'inputs': ['asset', 'alert'],
                                  'instruction': '내 시스템의 최근 창 요약을 읽어 공기 누설 의심의 조치 후보를 낸다. 정비 기록은 쓰지 않는다.',
                                  'outputs': [{'key': 'proposal', 'text': '조치 후보', 'type': 'object'}]},
                      'T_ok': {'part': approval_part.KEY, 'role': ROLE_NAME, 'config': {'options': 'proposal.options', 'recommended': 'proposal.recommended'}},
                      'T_record': {'part': 'svc:mcp-call', 'inputs': ['asset'],
                                   'config': {'server': SERVER, 'tool': 'record_maintenance',
                                              'arguments': {'case_id': '{proc_inst_id}', 'sop': '{approved_option.sop}', 'action': '{approved_option.action}',
                                                            'performed_by': '{approved_by}'}}},
                      'R_ok': {'part': 'svc:report', 'config': {'outcome': '정상', 'title': '{asset} 공기 누설 대응 결과',
                                                                 'summary': '{approved_option.action} — 내 시스템에 정비 기록을 남겼습니다'}},
                      'R_no': {'part': 'svc:report', 'config': {'outcome': '반려', 'title': '{asset} 공기 누설 대응 결과',
                                                                 'summary': '담당자가 반려했습니다 — 사유: {approval_reason}'}}},
            'flows': {'F_yes': {'var': 'approval', 'op': '==', 'value': approval_part.APPROVE}, 'F_no': {'default': True}}}


def _clean(world, did):
    store = FlowStore(world.rt.repo, TENANT)
    if did in {v['id'] for v in store.versions()} and did in {h['id'] for h in world.rt.repo.deployed_heads(TENANT)}:
        world.rt.repo.clear_deployment(did, TENANT, actor=ME, reason='시험 끝')
    import psycopg
    with psycopg.connect(world.dsn, autocommit=True) as db:
        db.execute("UPDATE todolist SET status='CANCELLED' WHERE tenant_id=%s AND status IN ('TODO','IN_PROGRESS','SUBMITTED','PENDING') "
                   "AND proc_inst_id IN (SELECT proc_inst_id FROM bpm_proc_inst WHERE proc_def_id=%s)", (TENANT, did))
        db.execute("UPDATE bpm_proc_inst SET status='CANCELLED' WHERE tenant_id=%s AND proc_def_id=%s AND status='RUNNING'", (TENANT, did))
    out = store.reset(did)
    for pid in out['projection_instances']:
        world.rt._project({'proc_inst_id': pid})
    world.rt.cleanup_removed_definitions()
    A.reset(world.rt, by=ME)
    mcp_registry.reset(mcp_registry.store_for(world.rt.repo), TENANT)


@pytest.fixture
def flow(request, world, pbl, site):
    """포털과 같은 차례(HTTP): 내 도구 서버 등록 · 내 에이전트(그 서버) · 내 역할 → 흐름 가져오기(내 경보 종류 선언) → 검사 → 판본 등록 → 배포.
    정비 기록 뒤의 길(_bpmn 의 after)은 시험이 매개변수로 고른다(@pytest.mark.parametrize('flow', ['wait'], indirect=True)) — 없으면 바로 결과 보고."""
    after = getattr(request, 'param', 'report')
    _ok(world.api('POST', '/api/mcp/servers', {'name': SERVER, 'url': site.url, 'description': '지하철 APU 운영 데이터', 'by': ME}), 201)
    agent = _ok(world.api('POST', '/api/agents', {'name': 'APU 정비 에이전트', 'goal': '운영 데이터로 공기 누설 조치 후보를 낸다', 'tools': [SERVER], 'by': ME}), 201)
    _ok(world.api('POST', '/api/roles', {'name': ROLE_NAME, 'key': ROLE_ID.split(':', 1)[1], 'by': ME}), 201)
    did = 'apu_leak_' + uuid.uuid4().hex[:6]
    _ok(world.api('POST', '/api/flows/import', {'xml': _bpmn(did, after), 'file_name': f'{did}.bpmn', 'definition_id': did}))
    checked = _ok(world.api('POST', f'/api/flows/{did}/check', {'mapping': _mapping(agent['id'], after)}))
    assert checked['check']['ok'], checked['check']['problems']
    version = _ok(world.api('POST', f'/api/flows/{did}/register', {'mapping': _mapping(agent['id'], after), 'by': ME}), 201)['version']
    _ok(world.api('POST', f'/api/process/definitions/{did}/deploy', {'version': version, 'by': ME, 'reason': '내 현장 경보 흐름'}))
    yield did
    _clean(world, did)


def _detected(site):
    """감지 규칙이 표본에서 낸 발생 · 해제 — 시험마다 다른 사건이 되게 alertId 끝에 시험 표시를 붙인다(바깥 프로그램은 사건마다 새 id 를 쓴다)."""
    raise_, clear = apu.detected(site.db)
    aid = f"{raise_['alertId']}-{uuid.uuid4().hex[:6]}"
    return dict(raise_, alertId=aid), dict(clear, alertId=aid)


def _alert(world, alert):
    return world.api('POST', '/api/instances/start', {'alert': alert}, source_loop=True)


def _approve(world, pid, decision, option=None, reason=''):
    row = world.row(pid, 'T_ok', 'IN_PROGRESS')
    return world.api('POST', f"/api/todolist/{row['id']}/approve", {'decision': decision, 'option': option, 'by': ME, 'role': ROLE_ID, 'reason': reason})


def _no_plant_tags(value):
    text = json.dumps(value, ensure_ascii=False)
    return not any(f'"{t}"' in text for t in ('TS1', 'PS1', 'FS1', 'VS1', 'CE'))


@pytest.mark.parametrize('decision', [approval_part.APPROVE, approval_part.REJECT], ids=['승인', '반려'])
def test_내_현장_경보가_내_흐름을_열고_승인_반려와_해제까지_유압_태그_없이_끝난다(world, flow, site, relay, decision):
    raise_, clear = _detected(site)
    status, opened = _alert(world, raise_)
    assert status == 200, opened
    route = opened['route']
    assert (route['route'], route['definition']['definition']) == ('response', flow) and '「공기 누설 대응」이 이 경보를 열었습니다' in route['text'], route
    pid = opened['proc_inst_id']
    inc = world.incident(pid)
    assert (inc.asset, inc.state, inc.recovery, inc.supported) == (apu.ASSET, 'AWAITING_APPROVAL', None, True)    # 시계열 기준 없음 — 회복은 원천의 해제

    cli = ApuCli()
    assert world.runner('live', cli).poll_once() == 1
    step = world.row(pid, 'T_agent')
    assert step['status'] in ('SUBMITTED', 'DONE'), world._failure(step)
    assert cli.called == [f'mcp__{SERVER}__apu_windows'] and cli.refused == [f'mcp__{SERVER}__record_maintenance']
    assert site.called('record_maintenance') == []                                             # 승인 전에는 내 시스템에 쓰지 않는다
    world.poll()
    assert world.values(pid)['proposal']['evidence'] == '누설 의심 창 4개'                     # 내 시스템의 실제 표본에서 읽은 값

    reason = '' if decision == approval_part.APPROVE else '이번 주 정비 인원 없음 — 관찰로'
    _ok(_approve(world, pid, decision, option='A' if decision == approval_part.APPROVE else None, reason=reason))
    world.poll(3)
    inst = world.inst(pid)
    report = world.values(pid)['result_report']
    if decision == approval_part.APPROVE:
        assert (inst['status'], inst['end_event']) == ('COMPLETED', 'E_done'), [(w['activity_id'], w['status'], w.get('log')) for w in world.rows(pid)]
        [written] = site.called('record_maintenance')                                          # 정확히 한 번, 사람이 고른 안으로
        assert (written['case_id'], written['sop'], written['performed_by']) == (pid, 'SOP-APU-03', ME) and written['idempotency_key']
        assert site.log() == [(pid, 'SOP-APU-03', '공기 배관 누설 점검 · 체결부 조임', ME)]
        # 정상 보고지만 내 시스템이 아직 해제를 보내지 않았다 — 사건은 닫지 않고 해제를 기다린다(보고만으로 고쳐졌다고 말하지 않는다)
        assert (report['outcome'], world.incident(pid).state) == ('정상', 'AWAITING_CLEAR'), report
        assert (report['incident_closed'], report['incident_state']) == (False, 'AWAITING_CLEAR'), report
        assert _states(world.incident(pid))[-3:] == ['AWAITING_APPROVAL', 'APPROVED_EXECUTING', 'AWAITING_CLEAR']
    else:
        assert (inst['status'], inst['end_event']) == ('COMPLETED', 'E_no')
        assert site.called('record_maintenance') == [] and site.log() == []
        assert report['outcome'] == '반려' and reason in report['summary']
        assert world.incident(pid).state == 'REJECTED_BY_OPERATOR'
    assert _no_plant_tags(world.values(pid)) and _no_plant_tags(report), '유압 태그가 내 현장 처리 건에 끼었다'

    status, cleared = _alert(world, clear)                                                        # 바깥 프로그램이 보내는 해제(같은 alertId)
    assert status == 200 and cleared['incident'] == inc.id and cleared['state'] == 'CLEAR', cleared
    assert world.incident(pid).cleared and world.incident(pid).state == ('CLOSED' if decision == approval_part.APPROVE else 'REJECTED_BY_OPERATOR')
    if decision == approval_part.APPROVE:
        assert cleared['text'].endswith('사건: 종결'), cleared['text']
        assert world.incident(pid).history[-1]['note'] == '결과 보고 뒤 원천 경보가 풀려 종결'
    assert _alert(world, clear)[0] == 409, '같은 해제를 두 번 받지 않는다'


def _to_approval(world, site):
    """발생 → 내 에이전트가 조치 후보를 냄 → 사람 승인 단계가 열림. 돌려줌 = (처리 건 id, 그 경보의 해제)."""
    raise_, clear = _detected(site)
    status, opened = _alert(world, raise_)
    assert status == 200, opened
    pid = opened['proc_inst_id']
    assert world.runner('live', ApuCli()).poll_once() == 1
    world.poll()
    assert world.row(pid, 'T_ok')['status'] == 'IN_PROGRESS'
    return pid, clear


def _states(inc):
    return [h['state'] for h in inc.history]


@pytest.mark.parametrize('flow', ['wait'], indirect=True)
def test_승인한_뒤_정비_기록과_기다림_동안_사건은_승인_뒤_실행_중이고_그_사이의_해제는_자연_회복이_아니다(world, flow, site, relay):
    """실측(2026-11-23): 승인 → 정비 기록 → 12분 기다림 → 결과 보고로 간 내 현장 처리 건의 사건이 닫힐 때까지 「승인 대기」였다 — 승인한 뒤 12분 동안
    사건 목록과 해제 응답(「사건: 담당자 승인 대기」)이 승인 전이라고 말했고, 승인 전에만 여는 문(원인 진단 바꾸기 · 조치 후보 접수)이 열려 있었다."""
    pid, clear = _to_approval(world, site)
    inc = world.incident(pid)
    assert inc.state == 'AWAITING_APPROVAL'
    _ok(_approve(world, pid, approval_part.APPROVE, option='A'))
    world.poll(2)
    assert len(site.called('record_maintenance')) == 1 and world.row(pid, 'T_wait')['status'] == 'SUBMITTED' and world.inst(pid)['status'] == 'RUNNING'
    assert (inc.state, inc.approved_by, inc.cmd_id) == ('APPROVED_EXECUTING', ME, None)
    assert _states(inc)[-2:] == ['AWAITING_APPROVAL', 'APPROVED_EXECUTING']
    listed = next(i for i in _ok(world.api('GET', '/api/incidents')) if i['id'] == inc.id)
    assert (listed['state'], listed['terminal'], listed['approvedBy']) == ('APPROVED_EXECUTING', False, ME)
    with pytest.raises(ValueError, match=r'승인 대기가 아니라\(지금 사건: 승인 — 흐름이 실행 중\)'):                                    # 승인 전에만 여는 문: 원인 진단 바꾸기
        world.rt.hooks.update_incident_card(inc.id, {'causes': [{'id': 'x'}]})
    assert world.rt.hooks.flow_approved(inc.id, 'user:someone-else') is False and inc.approved_by == ME

    status, cleared = _alert(world, clear)                                                        # 기다리는 동안 내 시스템이 해제를 보낸다
    assert status == 200 and cleared['incident_state'] == 'APPROVED_EXECUTING', cleared
    assert cleared['text'].endswith('사건: 승인 — 흐름이 실행 중'), cleared['text']
    world.poll(2)
    assert inc.cleared and inc.state == 'APPROVED_EXECUTING' and world.inst(pid)['status'] == 'RUNNING', '승인 뒤의 해제는 자연 회복으로 닫지 않는다'
    assert world.row(pid, 'T_wait')['status'] == 'SUBMITTED'

    # 내 현장의 기다림은 벽시계다(가상 설비 · 모의 업무 시스템만 수업 압축) — 12분에서 2초 모자라면 아직 기다리고, 3초 더 가면 끝난다
    world.clock.advance(WAIT_S - 2)
    world.poll(2)
    assert world.row(pid, 'T_wait')['status'] == 'SUBMITTED' and world.inst(pid)['status'] == 'RUNNING', '12분 기다림이 12분 전에 끝났다'
    world.clock.advance(3)
    world.poll(3)
    inst = world.inst(pid)
    assert (inst['status'], inst['end_event']) == ('COMPLETED', 'E_done'), [(w['activity_id'], w['status'], w.get('log')) for w in world.rows(pid)]
    assert (world.values(pid)['result_report']['outcome'], inc.state) == ('정상', 'CLOSED')
    assert _states(inc)[-3:] == ['AWAITING_APPROVAL', 'APPROVED_EXECUTING', 'CLOSED']
    assert len(site.called('record_maintenance')) == 1


@pytest.mark.parametrize('flow', ['check'], indirect=True)
@pytest.mark.parametrize('reopen', ['바로', '저장 실패 뒤 다시 켬'])
def test_승인_뒤_회복하지_않아_흐름이_새_승인으로_되돌아가면_사건도_승인_대기로_돌아가_반려까지_된다(world, flow, site, relay, reopen):
    """승인 뒤 실행 중인 사건은 승인 전에만 여는 문을 닫는다 — 그래서 흐름이 새 조치 후보 · 새 승인으로 되돌아가면 사건도 승인 대기로 돌아가야
    두 번째 판단을 받고 반려할 수 있다(되돌아간 뒤에도 실행 중으로 남으면 반려 결과 보고가 「승인 대기 중인 사건만」으로 막힌다).
    저장 실패 뒤 다시 켬: 되돌아감은 DB 에 커밋됐는데 뒤따르는 사건 다시 열기의 저장이 실패하고(사건 저장 파일을 다른 쪽이 잠금) 그대로 process 가
    다시 켜지면, 다시 켠 process 는 실행 중인 사건을 읽는다 — 폴링이 커밋된 되돌아감을 보고 사건을 다시 연다(복구)."""
    pid, _clear = _to_approval(world, site)
    _ok(_approve(world, pid, approval_part.APPROVE, option='A'))
    world.poll(2)
    assert world.incident(pid).state == 'APPROVED_EXECUTING' and len(site.called('record_maintenance')) == 1
    check = world.row(pid, 'T_check', 'IN_PROGRESS')
    if reopen == '바로':
        _ok(world.api('POST', f"/api/todolist/{check['id']}/submit", {'output': {'fixed': '아니오'}, 'by': ME}))
    else:
        lock = world.incident_store_lock()
        _ok(world.api('POST', f"/api/todolist/{check['id']}/submit", {'output': {'fixed': '아니오'}, 'by': ME}))      # 커밋은 된다
        failed = [e['data'] for e in world.events(pid) if e['job_id'] == 'POST_COMMIT_EFFECT_FAILED']
        # 그 저장소에 쓰는 뒤따름(사건 다시 열기 · 감사 기록)이 모두 잠금으로 실패하고 처리 건 기록에 남는다
        assert '_reopen_for_recheck' in {f['effect'] for f in failed} and all('database is locked' in f['raw_error'] for f in failed), failed
        world.restart(while_down=lock.release)
        assert world.incident(pid).state == 'APPROVED_EXECUTING', '다시 켠 process 는 저장된(다시 열기 전) 사건을 읽는다'
    world.poll(2)
    inc = world.incident(pid)
    assert inc.state == 'AWAITING_APPROVAL' and inc.approved_by is None, _states(inc)
    assert (inc.superseded[-1]['kind'], inc.superseded[-1]['state_before'], inc.superseded[-1]['approvedBy']) == ('recheck', 'APPROVED_EXECUTING', ME)
    reopened = [e['data']['reason'] for e in world.events(pid) if e['job_id'] == 'INCIDENT_REOPENED_RECHECK']
    assert len(reopened) == 1 and reopened[0].endswith('(복구)') == (reopen != '바로'), reopened
    assert world.runner('live', ApuCli()).poll_once() == 1                                        # 되돌아간 조치 후보 단계를 내 에이전트가 다시 한다
    world.poll()
    _ok(_approve(world, pid, approval_part.REJECT, reason='두 번 조여도 그대로 — 부품 교체를 따로 잡는다'))
    world.poll(3)
    inst = world.inst(pid)
    assert (inst['status'], inst['end_event']) == ('COMPLETED', 'E_no'), [(w['activity_id'], w['status'], w.get('log')) for w in world.rows(pid)]
    assert inc.state == 'REJECTED_BY_OPERATOR' and len(site.called('record_maintenance')) == 1, '반려한 두 번째 판단으로는 내 시스템에 쓰지 않는다'


def test_승인_전에_내_시스템이_해제를_보내면_조치_전_해소로_닫고_까닭을_말한다(world, flow, site, relay):
    """회복 기준이 시계열에 없으니 회복은 원천의 해제다 — 사람이 승인하기 전에 해제가 오면 조치 없이 풀린 것으로 닫는다(실행은 나가지 않는다).
    전에는 「조치 전 종료」가 판단 카드 승인 단계만 승인으로 세어, 일반 사람 승인(안 고르기) 흐름은 해제 뒤에도 처리 건이 진행 중 · 승인 단계가
    열린 채 남았고, 그 뒤 승인하면 끝난 사건에 내 시스템 쓰기가 나갈 수 있었다."""
    raise_, clear = _detected(site)
    status, opened = _alert(world, raise_)
    assert status == 200, opened
    pid = opened['proc_inst_id']
    assert world.runner('live', ApuCli()).poll_once() == 1
    world.poll()
    assert world.row(pid, 'T_ok')['status'] == 'IN_PROGRESS'                                        # 사람 승인을 기다린다
    status, cleared = _alert(world, clear)
    assert status == 200 and cleared['incident_state'] == 'RESOLVED_WITHOUT_ACTION', cleared
    assert '사건: 조치 전 자연 회복' in cleared['text'], cleared
    world.poll()                                                                                  # 사건 전이 뒤의 처리 건 갱신(유압 수업 흐름과 같은 길)
    inst = world.inst(pid)
    assert inst['status'] == 'COMPLETED' and '조치 전' in world.values(pid)['result_report']['outcome'], world.values(pid).get('result_report')
    assert world.row(pid, 'T_ok')['status'] == 'CANCELLED'
    assert site.called('record_maintenance') == [] and site.log() == []


def test_발생을_보낸_적_없는_경보의_해제와_받는_흐름이_없는_내_경보는_까닭을_말한다(world, pbl, site):
    """해제는 같은 alertId 의 발생 뒤에만 붙는다(차례를 아는 HTTP 는 기다리지 않고 거절). 내 경보를 받는 흐름이 배포되지 않았으면 현장 검토로
    가고, 응답이 그렇다고 말한다(200 만 받고 내 흐름이 안 열린 것을 모르지 않게)."""
    raise_, clear = _detected(site)
    status, refused = _alert(world, dict(clear, alertId='APU-01-never-raised'))
    assert status == 404 and '발생(RAISE)을 받은 적이 없어' in refused['detail'], refused
    status, opened = _alert(world, dict(raise_, alertId=raise_['alertId'] + '-' + uuid.uuid4().hex[:6]))
    assert status == 200 and opened['route']['route'] == 'triage', opened
    assert '받는 배포 흐름이 없어' in opened['route']['text'] and '「내 경보 종류」' in opened['route']['text'], opened['route']


def test_정의_JSON으로_등록한_흐름도_스스로_정한_경보_종류로_열리고_시계열에_없는_회복_기준을_지어_넣지_않아도_된다(world, pbl):
    """탐사 S 「JSON 개발자 길」: 흐름 정의를 JSON 으로 직접 등록하는 길(시스템 › 관리)은 경보 정책에 회복 기준(태그 · 연산 · 임계)이 꼭 있어야 해, 내
    설비의 경보를 받으려면 시계열에 없는 태그를 지어 넣어야 했다. 이제 받는 경보 종류와 「회복은 원천의 해제」만 적으면 등록 · 배포되고, 바깥 프로그램의
    그 경보가 이 흐름을 연다. 해제 계약(requireClear)이 빠진 정책은 그 까닭으로 거절한다."""
    from conftest import DEFINITIONS
    did, pattern = 'json_site_' + uuid.uuid4().hex[:6], 'CONVEYOR_JAM'
    raw = json.loads((DEFINITIONS / 'alert_triage_v1.json').read_text(encoding='utf-8'))       # 사람 단계 하나짜리 흐름(메시지 시작)
    raw.pop('ontologyRef', None)
    raw.update(processDefinitionId=did, processDefinitionName='컨베이어 걸림 사람 확인', version='1',
               alertPolicy={'patterns': {pattern: {'name': '컨베이어 걸림'}}, 'unsupported': {'definition': 'alert_triage', 'version': '1.0'}})
    status, refused = world.api('POST', '/api/process/definitions', {'definition': raw})
    assert status == 400 and f'경보 {pattern}의 회복 계약에는 requireClear=true(원천의 해제)가 필요합니다' in str(refused), refused
    raw['alertPolicy']['patterns'][pattern]['requireClear'] = True
    try:
        _ok(world.api('POST', '/api/process/definitions', {'definition': raw}), 201)
        _ok(world.api('POST', f'/api/process/definitions/{did}/deploy', {'version': '1', 'by': ME, 'reason': '내 설비 경보 흐름(JSON 등록)'}))
        alert = {'alertId': f'CONV-07-{pattern}-{uuid.uuid4().hex[:6]}', 'asset': 'CONV-07', 'pattern': pattern, 'name': '컨베이어 걸림',
                 'severity': 'HIGH', 'state': 'RAISE', 'evidence': {'belt_current_a': 41.5, 'rule': '벨트 전류 40 A 이상 30초'}}
        status, opened = _alert(world, alert)
        assert status == 200, opened
        route = opened['route']
        assert (route['route'], route['definition']['definition']) == ('response', did) and '「컨베이어 걸림 사람 확인」이 이 경보를 열었습니다' in route['text'], route
        pid = opened['proc_inst_id']
        inc = world.incident(pid)
        assert (inc.asset, inc.state, inc.recovery, inc.supported) == ('CONV-07', 'AWAITING_APPROVAL', None, True)
        assert world.inst(pid)['proc_def_id'] == did and _no_plant_tags(world.values(pid))
        status, cleared = _alert(world, dict(alert, state='CLEAR', evidence={'belt_current_a': 12.0}))
        assert status == 200 and cleared['incident_state'] == 'RESOLVED_WITHOUT_ACTION', cleared     # 회복은 원천이 보낸 해제
    finally:
        _clean(world, did)


def test_승인_뒤_내_시스템_쓰기_단계가_멈추면_원인을_고친_뒤_승인한_내용_그대로_다시_보내_끝까지_가고_같은_경보는_상태대로_답한다(world, flow, site, relay):
    """2026-11-23 실측(학생 서버가 꺼진 갈래): 승인 뒤 「정비 기록 등록」이 3번 실패해 멈췄다. 안내는 [다시 수행]이었는데 ① 사건이 있는 처리 건에서 승인 뒤
    단계 하나만 다시 수행하는 것은 늘 막히고(새 판단이 있어야 한다) ② 판단 단계부터의 다시 수행도 「사건이 이미 해제됐거나 끝났다」로 막혔다 — 해제는 오지
    않았고, 시계열 회복 기준이 없는 경보(회복은 원천의 해제)를 끝난 사건으로 본 탓이다. ③ 「승인한 내용 그대로 다시 보내기」는 기본 제공 정비 요청 단계에만
    있었다. 이제 멈춘 까닭 문장 · 행동이 되는 길(다시 보내기)을 말하고, 그 길이 승인 값 그대로 한 번만 쓰며, 판단 단계부터의 다시 수행은 사건이 살아 있으면
    그 까닭으로 막히지 않는다. 같은 경보를 다시 보내면 처리 건이 진행 중인지 끝났는지를 사실대로 답한다."""
    raise_, clear = _detected(site)
    status, opened = _alert(world, raise_)
    assert status == 200, opened
    pid = opened['proc_inst_id']
    assert world.runner('live', ApuCli()).poll_once() == 1
    world.poll()
    _ok(world.api('DELETE', f'/api/mcp/servers/{SERVER}?by={ME}&force=true'))                   # 승인 직전에 내 서버 등록이 사라졌다(닿지 않는 서버)
    _ok(_approve(world, pid, approval_part.APPROVE, option='A'))
    world.poll(5)
    stopped = world.row(pid, 'T_record')
    assert stopped['status'] == 'PENDING' and int(stopped['retry']) == 3 and site.called('record_maintenance') == []
    said = world._failure(stopped)['friendly']
    assert '[같은 내용 다시 전달]' in said and '[다시 수행]' not in said and '다시 수행하세요' not in said, said
    view = _ok(world.api('GET', f'/api/instances/{pid}'))
    step = next(s for s in view['attention']['steps'] if s['workitem'] == stopped['id'])
    assert step['actions'] == ['effect_retry', 'rework', 'close'], step
    inc = world.incident(pid)
    assert (inc.state, inc.cleared, inc.recovery) == ('APPROVED_EXECUTING', False, None)

    status, again = _alert(world, raise_)                                                      # 진행 중에 같은 경보를 다시 보냄
    assert status == 409 and f'이 경보로 이미 열린 처리 건이 있습니다: {pid}' in again['detail'], again

    codes = [b['code'] for b in _ok(world.api('GET', f"/api/instances/{pid}/rework-preview?workitem_id={world.row(pid, 'T_agent')['id']}"))['blockers']]
    assert 'incident_not_active_for_rework' not in codes, codes                                # 해제되지 않은 사건은 살아 있다(시계열 기준이 없어도)
    codes = [b['code'] for b in _ok(world.api('GET', f"/api/instances/{pid}/rework-preview?workitem_id={stopped['id']}"))['blockers']]
    assert 'incident_not_active_for_rework' not in codes and 'rework_requires_new_decision' in codes, codes

    status, refused = world.api('POST', f"/api/todolist/{stopped['id']}/effect-retry", {'by': ME, 'role': 'role:operator'})
    assert status == 403 and '승인했던 역할로만' in str(refused), refused                       # 승인한 역할이 아니면 다시 보내지 않는다
    _ok(world.api('POST', '/api/mcp/servers', {'name': SERVER, 'url': site.url, 'description': '지하철 APU 운영 데이터', 'by': ME}), 201)   # 원인을 고침
    _ok(world.api('POST', f"/api/todolist/{stopped['id']}/effect-retry", {'by': ME, 'role': ROLE_ID}))
    world.poll(5)
    inst = world.inst(pid)
    assert (inst['status'], inst['end_event']) == ('COMPLETED', 'E_done'), [(w['activity_id'], w['status'], w.get('log')) for w in world.rows(pid)]
    assert site.log() == [(pid, 'SOP-APU-03', '공기 배관 누설 점검 · 체결부 조임', ME)]           # 승인한 안 그대로, 정확히 한 번
    assert world.values(pid)['result_report']['outcome'] == '정상' and world.incident(pid).state == 'AWAITING_CLEAR', '해제가 오기 전에는 닫지 않는다'
    status, refused = world.api('POST', f"/api/todolist/{stopped['id']}/effect-retry", {'by': ME, 'role': ROLE_ID})
    assert status == 409 and '다시 보낼 수 있는 단계가 아닙니다' in str(refused), refused         # 끝난 단계는 다시 보내지 않는다

    status, again = _alert(world, raise_)                                                      # 끝난 뒤에 같은 경보를 다시 보냄
    assert status == 409 and '이미 받았습니다' in again['detail'] and f'처리 건 {pid}(끝 「' in again['detail']         and '새 경보 id(alertId)로 보내세요' in again['detail'] and '이미 열린 처리 건' not in again['detail'], again


@pytest.mark.parametrize('flow', ['late'], indirect=True)
def test_내_현장_처리_건의_기다림에_붙인_경계_타이머는_벽시계로_울린다(world, flow, site, relay):
    """CLAUDE.md 4절 「시간은 세 갈래」: 가상 설비 · 모의 업무 시스템이 아닌 처리 건(학생 현장)은 시간 대기와 경계 타이머가 모두 벽시계다. 엔진의 실제
    배선(경계 타이머의 마감 — engine reach · 기다림 부품 — service_parts wait_for)을 처리 건 하나로 지난다: 5분 경계 타이머는 5분에서 2초 모자라면
    울리지 않고, 3초 더 가면 울려 지연 보고로 간다(12분 기다림은 끝나지 않았다)."""
    pid, _clear = _to_approval(world, site)
    _ok(_approve(world, pid, approval_part.APPROVE, option='A'))
    world.poll(2)
    assert world.row(pid, 'T_wait')['status'] == 'SUBMITTED' and len(site.called('record_maintenance')) == 1
    world.clock.advance(LATE_S - 2)
    world.poll(2)
    assert world.inst(pid)['status'] == 'RUNNING' and world.row(pid, 'T_wait')['status'] == 'SUBMITTED', '5분 경계 타이머가 5분 전에 울렸다'
    world.clock.advance(3)
    world.poll(3)
    inst = world.inst(pid)
    assert (inst['status'], inst['end_event']) == ('COMPLETED', 'E_slow'), [(w['activity_id'], w['status'], w.get('log')) for w in world.rows(pid)]
    assert world.values(pid)['result_report']['outcome'] == '지연'


def test_정상_보고_뒤_내_시스템이_해제를_끝내_보내지_않으면_벽시계_30분_뒤_책임자_확인으로_넘기고_늦은_해제는_그대로_둔다(world, flow, site, relay):
    """2026-11-25 감사: 승인 → 정비 기록 → 결과 보고(정상)로 끝난 내 현장 처리 건이, 경보가 켜진 채 「종결」로 보였다. 이제 사건은 해제를 기다리고,
    시한(내 현장은 벽시계 30분 — definition.CLEAR_WAIT_S)이 지나도 해제가 없으면 조치가 효과를 냈다는 확인이 없으니 책임자 확인으로 넘긴다."""
    pid, clear = _to_approval(world, site)
    _ok(_approve(world, pid, approval_part.APPROVE, option='A'))
    world.poll(3)
    inc = world.incident(pid)
    assert world.inst(pid)['status'] == 'COMPLETED' and inc.state == 'AWAITING_CLEAR', [(w['activity_id'], w['status']) for w in world.rows(pid)]
    listed = next(i for i in _ok(world.api('GET', '/api/incidents')) if i['id'] == inc.id)
    assert (listed['state'], listed['terminal'], listed['clearDueAt']) == ('AWAITING_CLEAR', False, inc.clear_due_at), '열린 사건으로 센다'
    world.clock.advance(definition.CLEAR_WAIT_S - 2)
    world.poll(2)
    assert inc.state == 'AWAITING_CLEAR', '30분 시한이 30분 전에 지났다'
    world.clock.advance(3)
    assert world.poll(2) == [], '폴링의 해제 기다림 일이 실패했다'
    assert (inc.state, inc.reason) == ('ESCALATED', f'{definition.CLEAR_TIMEOUT}: 30분') and inc.closed
    assert '원천 경보가 30분 안에 해제되지 않았습니다' in definition.escalation_cause(inc.reason)[0]
    status, cleared = _alert(world, clear)                                                        # 늦게 온 해제
    assert status == 200 and cleared['text'].endswith('사건: 책임자 확인'), cleared
    assert inc.cleared and inc.state == 'ESCALATED', '책임자 확인으로 넘긴 사건을 늦은 해제가 다시 닫지 않는다'
