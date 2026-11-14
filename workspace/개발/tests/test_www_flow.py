"""흐름 그림(it/portal/www/flow.js hydFlow) — 처리 건의 상태 표시와 그림 원본 만들기. node 에서 실제 화면 모듈을 싣고 부른다(www_node).
그리기(bpmn-js)는 브라우저 몫이라 여기서는 그림에 얹는 값(어느 요소가 끝남 · 지금 · 멈춤인가)과 정의에서 만든 BPMN 을 본다."""
import re

from www_node import run

FILES = ['ui.js', 'instanceSteps.js', 'flow.js']

DEF = {'processDefinitionId': 'cool', 'version': '1', 'processDefinitionName': '냉각 대응',
       'roles': [{'name': 'AI 에이전트', 'endpoint': 'sys:agent'}, {'name': '운전원', 'endpoint': 'role:operator'}, {'name': '프로세스', 'endpoint': 'sys:process'}],
       'events': [{'id': 'Start', 'type': 'startEvent', 'name': '경보', 'eventDefinition': 'message'}, {'id': 'E_end', 'type': 'endEvent', 'name': '끝'},
                  {'id': 'E_rej', 'type': 'endEvent', 'name': '거절 종결'},
                  {'id': 'B_late', 'type': 'boundaryEvent', 'name': '승인 지연', 'attachedTo': 'T_approve', 'cancelActivity': False, 'eventDefinition': 'timer'}],
       'activities': [{'id': 'T_agent', 'name': '원인 진단', 'type': 'userTask', 'role': 'AI 에이전트', 'agent': 'agent:cooling'},
                      {'id': 'T_approve', 'name': '운전원 승인', 'type': 'userTask', 'role': '운전원'},
                      {'id': 'T_cmd', 'name': '냉각 명령', 'type': 'serviceTask', 'role': '프로세스'},
                      {'id': 'R_rej', 'name': '결과 보고: 거절', 'type': 'serviceTask', 'role': '프로세스'},
                      {'id': 'T_notice', 'name': '승인 지연 알림', 'type': 'serviceTask', 'role': '프로세스'}],
       'gateways': [{'id': 'G', 'name': '승인?', 'type': 'exclusiveGateway'}],
       'sequences': [{'id': 'F1', 'source': 'Start', 'target': 'T_agent'}, {'id': 'F2', 'source': 'T_agent', 'target': 'T_approve'}, {'id': 'F3', 'source': 'T_approve', 'target': 'G'},
                     {'id': 'F_ok', 'name': '승인', 'source': 'G', 'target': 'T_cmd', 'condition': "approval == '승인'"}, {'id': 'F_no', 'name': '거절', 'source': 'G', 'target': 'R_rej'},
                     {'id': 'F5', 'source': 'T_cmd', 'target': 'E_end'}, {'id': 'F6', 'source': 'R_rej', 'target': 'E_rej'}, {'id': 'F7', 'source': 'B_late', 'target': 'T_notice'}]}


def wi(activity, status, start, **more):
    return {'id': 'w-' + activity, 'activity_id': activity, 'status': status, 'start_date': start, **more}


def marks(workitems, status='RUNNING', end_event=None):
    view = {'definition': DEF, 'instance': {'proc_inst_id': 'p', 'status': status, 'end_event': end_event}, 'workitems': workitems}
    return run(FILES, "const m = hydFlow.marksOf(DATA); out({ st: m.st, now: m.now, lastDone: m.lastDone })", view)


def test_승인을_기다리는_동안_걸어_둔_기한_타이머는_지금_단계로_표시하지_않는다():
    """승인 단계와 그 단계에 걸린 경계 타이머가 함께 진행 중 작업 행으로 온다 — 그림의 「지금」 꼬리표는 승인 단계 하나에만 붙어야 한다."""
    got = marks([wi('T_agent', 'DONE', '01'), wi('T_approve', 'IN_PROGRESS', '02'), wi('B_late', 'IN_PROGRESS', '02'), wi('T_cmd', 'TODO', None)])
    assert got['now'] == ['T_approve']
    assert got['st']['T_agent'] == 'done' and got['st']['F2'] == 'done' and got['st']['T_approve'] == 'now'
    assert 'B_late' not in got['st'] and 'T_cmd' not in got['st'] and 'F3' not in got['st']      # 아직 가지 않은 곳은 남음(표시 없음)


def test_끝난_건은_실제로_지나간_가지만_끝남으로_표시한다():
    """반려로 끝난 건: 갈림에서 거절 가지와 그 끝만 끝남이고, 승인 가지(냉각 명령 · 끝)는 남음으로 흐리게 둔다. 엔진이 시작 전에 취소한 가지는 지나온 것이 아니다."""
    got = marks([wi('T_agent', 'DONE', '01'), wi('T_approve', 'DONE', '02'), wi('R_rej', 'DONE', '03', end_date='04'),
                 wi('T_cmd', 'CANCELLED', None, log='cancelled: 가지 않은 가지'), wi('B_late', 'CANCELLED', '02')], status='COMPLETED', end_event='E_rej')
    st = got['st']
    assert [st.get(k) for k in ('G', 'F_no', 'R_rej', 'F6', 'E_rej')] == ['done'] * 5
    assert [k for k in ('T_cmd', 'F_ok', 'F5', 'E_end', 'B_late', 'F7', 'T_notice') if k in st] == []
    assert got['now'] == [] and got['lastDone'] == 'R_rej'


def test_실패한_AI_단계는_멈춤으로_표시되고_그_단계가_지금_자리다():
    got = marks([wi('T_agent', 'IN_PROGRESS', '01', draft_status='FAILED')])
    assert got['st']['T_agent'] == 'fail' and got['now'] == ['T_agent']


def test_그림_원본이_없는_흐름은_정의의_단계_갈림_선으로_BPMN_을_만든다():
    """정의(JSON)로만 등록된 흐름: 요소 id 가 정의와 같아야 상태 표시가 그 요소에 얹힌다. 경계 타이머는 붙은 단계와 「멈추지 않음」을 그대로 싣는다."""
    xml = run(FILES, "out(hydFlow.defToXml(DATA))", DEF)
    assert 'BPMNDiagram' not in xml      # 배치 정보는 없다 — 화면이 자동으로 놓고 그 사실을 알린다
    ids = set(re.findall(r'<bpmn:(?:\w+) id="([^"]+)"', xml))
    assert {'Start', 'E_end', 'E_rej', 'B_late', 'T_agent', 'T_approve', 'T_cmd', 'R_rej', 'T_notice', 'G', 'F1', 'F_ok', 'F7'} <= ids
    assert '<bpmn:boundaryEvent id="B_late" name="승인 지연" attachedToRef="T_approve" cancelActivity="false"><bpmn:timerEventDefinition/>' in xml
    assert '<bpmn:sequenceFlow id="F_ok" name="승인" sourceRef="G" targetRef="T_cmd"/>' in xml
    assert '<bpmn:startEvent id="Start" name="경보"><bpmn:messageEventDefinition/></bpmn:startEvent>' in xml


def test_남은_길은_정해진_데까지만_잇고_갈림_뒤는_가지마다_따로_낸다():
    """독립 검토 가-1: 승인 전에도 「… → 결과 보고: 정상」처럼 한 길을 골라 끝까지 적어 결과가 정해진 것처럼 읽혔다. 갈림에서 멈추고 가지를 모두 낸다."""
    view = {'definition': DEF, 'instance': {'status': 'RUNNING'}, 'workitems': [wi('T_agent', 'DONE', '01'), wi('T_approve', 'IN_PROGRESS', '02')]}
    got = run(FILES, "const m = hydFlow.pathModel(DATA.definition, DATA.workitems, DATA.instance); out([m.nodes.map(n => [n.id, n.state, n.who]), m.end, m.fork])", view)
    assert got[0] == [['T_agent', 'done', 'agent'], ['T_approve', 'now', 'human']] and got[1] is None      # 승인 뒤의 단계는 「남은 단계」 한 줄에 넣지 않는다
    assert got[2] == {'name': '승인?', 'branches': [{'label': '승인', 'steps': ['냉각 명령'], 'more': None, 'end': '끝'},
                                                   {'label': '거절', 'steps': ['결과 보고: 거절'], 'more': None, 'end': '거절 종결'}]}


def test_갈림이_없는_남은_길은_끝까지_잇는다():
    view = {'definition': DEF, 'instance': {'status': 'RUNNING'}, 'workitems': [wi('T_agent', 'DONE', '01'), wi('T_approve', 'DONE', '02'), wi('T_cmd', 'IN_PROGRESS', '03')]}
    got = run(FILES, "const m = hydFlow.pathModel(DATA.definition, DATA.workitems, DATA.instance); out([m.nodes.map(n => [n.id, n.state]), m.end && m.end.id, m.fork])", view)
    assert got == [[['T_agent', 'done'], ['T_approve', 'done'], ['T_cmd', 'now']], 'E_end', None]
