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


FILE_XML = '<bpmn:definitions xmlns:bpmn="b" xmlns:bpmndi="d"><bpmn:process id="p"/><bpmndi:BPMNDiagram id="D"/></bpmn:definitions>'      # 배치 정보가 든 그림(자동 배치를 거치지 않는다)
ASK = """const calls = [];
fetch = async u => { calls.push(u); return { status: DATA.status, ok: DATA.status === 200, text: async () => DATA.xml }; };
UI.need = async () => {}; window.hydBpmnLayout = { ensureLayout: async xml => ({ xml, laidOut: true }) };      // 브라우저 부품(자동 배치) 대역 — 정의에서 만든 그림은 이 길로 간다
let got; try { const s = await hydFlow.xmlOf(DATA.def); got = { source: s.source, file: s.xml === DATA.xml, laidOut: !!s.laidOut }; } catch (e) { got = { error: e.message }; }
out({ got, calls, back: hydFlow.defIdOf('task_x3a_draft'), seq: hydFlow.defIdOf('seq_x3a_0') });"""


def ask(status, **more):
    d = {'processDefinitionId': 'c3_cooling', 'version': '2', 'events': [{'id': 'ev:start', 'type': 'startEvent'}], 'gateways': [],
         'activities': [{'id': 'task:draft', 'name': '초안', 'type': 'userTask'}], 'sequences': [{'id': 'seq:0', 'source': 'ev:start', 'target': 'task:draft'}], **more}
    return run(FILES, ASK, {'def': d, 'status': status, 'xml': FILE_XML}, prelude="var API = { process: '' };")      # API 주소 표(app.js)의 대역


def test_흐름_그림은_가져온_흐름이_아니어도_서버에_먼저_묻고_받은_그림의_id를_정의의_id와_잇는다():
    """기본 제공 흐름에도 사람이 배치한 그림이 서버에 있다 — 전에는 정의에 bpmnImport 가 있을 때만 물어 기본 제공 흐름이 늘 자동 배치로 그려졌다.
    서버는 그림의 id 를 xid 규칙(task:draft → task_x3a_draft)으로 바꿔 내주므로, 받은 그림을 쓸 때 정의의 모든 id 의 대응을 채워야 상태 표시와 누름이 그 단계를 찾는다."""
    got = ask(200)      # bpmnImport 가 없는 흐름
    assert got['calls'] == ['/api/flows/c3_cooling/versions/2/bpmn']
    assert got['got'] == {'source': 'file', 'file': True, 'laidOut': False}
    assert got['back'] == 'task:draft' and got['seq'] == 'seq:0'


def test_서버에_그림이_없으면_정의에서_만들어_자동으로_놓고_그_밖의_실패는_오류로_드러낸다():
    for status in (204, 404):
        got = ask(status)
        assert got['got'] == {'source': 'definition', 'file': False, 'laidOut': True} and len(got['calls']) == 1, (status, got)
    assert ask(500)['got'] == {'error': '흐름 그림 원본을 읽지 못했습니다(500)'}


def test_끝_이름이_처리_완료이면_어디서_끝났는지를_따로_말하지_않는다():
    """새 판본의 끝 이벤트 이름은 「처리 완료」다 — 「처리 건은 「처리 완료」에서 끝났습니다」 같은 문장이 나오지 않게 한 곳(UI.plainEnd)에서 가른다."""
    assert run(['ui.js'], "out(['처리 완료', '끝', ' 종료 ', '', null, '반려 종결', '책임자 확인으로 종료'].map(x => UI.plainEnd(x)))") == [True, True, True, True, True, False, False]


def test_옛_판본으로_돈_처리_건의_옛_단계_이름은_지금_이름으로_보인다():
    assert run(['ui.js'], "out(['재관측', '작업지시 등록', '결과 보고: 거절', '거절 종결', '원인 진단'].map(x => UI.flowName(x)))") == ['효과 확인', '정비 요청 등록', '결과 보고: 반려', '반려 종결', '원인 진단']


def test_가지_않은_길의_취소_줄은_지나온_것도_멈춤도_아니고_다시_수행_뒤에는_앞_차수의_닫힌_줄이_지금_단계를_가리지_않는다():
    """서버가 취소 까닭을 한국어(「취소: 처리 건이 끝남 — …」)로 적기 시작하자, 글머리 「cancelled:」로 가르던 화면이 가지 않은 길의 줄을 모두
    「멈춤」으로 그렸다. 판정은 까닭 글이 아니라 줄의 사실(취소됨 · 시작된 적 없음)로 한다. 다시 수행 뒤에는 앞 차수의 닫힌 줄이 남아 머리 줄이
    「1번째 단계 … 에서 멈춤」이라고 했다 — 지금 차수의 줄만 지금 상태다."""
    T0, T1, T2 = '2026-11-14T06:33:04.882Z', '2026-11-14T06:33:07.835Z', '2026-11-14T06:34:37.270Z'
    rows = [   # 반려로 끝난 건: 냉각 명령은 처리 건이 열릴 때 만들어져 한 번도 시작되지 않고 닫혔다(까닭 글은 한국어)
        wi('T_agent', 'DONE', T0, end_date=T1), wi('T_approve', 'DONE', T1, end_date=T2),
        wi('T_cmd', 'CANCELLED', T0, end_date=T2, log='취소: 처리 건이 끝남 — 거절 종결; '), wi('R_rej', 'DONE', T2, end_date=T2)]
    got = marks(rows, status='COMPLETED', end_event='E_rej')
    assert 'T_cmd' not in got['st'] and got['st']['R_rej'] == 'done' and got['now'] == []
    # 다시 수행: 앞 차수(0)의 승인 줄은 기다리던 중에 닫혔고(시작된 적 있음), 새 차수(1)의 승인 줄이 지금 내 차례다
    again = [dict(wi('T_agent', 'DONE', T0, end_date=T1), id='a0', generation=0), dict(wi('T_approve', 'CANCELLED', T1, end_date=T2, log='rework superseded: r1; '), id='p0', generation=0),
             dict(wi('T_cmd', 'CANCELLED', T1, end_date=T2, log='rework superseded: r1; '), id='c0', generation=0),      # 앞 차수에서 시작됐다가 닫힌 줄 — 새 차수의 같은 단계는 아직 예정이다
             dict(wi('T_agent', 'DONE', T2, end_date=T2), id='a1', generation=1), dict(wi('T_approve', 'IN_PROGRESS', T2), id='p1', generation=1), dict(wi('T_cmd', 'TODO', T2), id='c1', generation=1)]
    view = {'definition': DEF, 'instance': {'proc_inst_id': 'p', 'status': 'RUNNING'}, 'workitems': again}
    nodes = run(FILES, "const m = hydFlow.pathModel(DATA.definition, DATA.workitems, DATA.instance); out(m.nodes.map(n => [n.id, n.state]))", view)
    assert ['T_approve', 'now'] in nodes and not any(state == 'fail' for _, state in nodes), nodes
    assert marks(again)['now'] == ['T_approve']
