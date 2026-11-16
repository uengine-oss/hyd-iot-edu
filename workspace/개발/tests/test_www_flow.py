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
                 wi('T_cmd', 'CANCELLED', None, reached_at=None, log='cancelled: 가지 않은 가지'), wi('B_late', 'CANCELLED', '02', reached_at='02')], status='COMPLETED', end_event='E_rej')
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
    「멈춤」으로 그렸다. 판정은 까닭 글도 시작 시각도 아니고 서버가 줄마다 싣는 reached_at(흐름이 그 단계에 닿은 시각, 닿은 적 없으면 null) 하나다. 다시 수행 뒤에는 앞 차수의 닫힌 줄이 남아 머리 줄이
    「1번째 단계 … 에서 멈춤」이라고 했다 — 지금 차수의 줄만 지금 상태다."""
    T0, T1, T2 = '2026-11-14T06:33:04.882Z', '2026-11-14T06:33:07.835Z', '2026-11-14T06:34:37.270Z'
    rows = [   # 반려로 끝난 건: 냉각 명령은 처리 건이 열릴 때 만들어져 한 번도 시작되지 않고 닫혔다(까닭 글은 한국어)
        wi('T_agent', 'DONE', T0, end_date=T1), wi('T_approve', 'DONE', T1, end_date=T2),
        wi('T_cmd', 'CANCELLED', T0, end_date=T2, reached_at=None, log='취소: 처리 건이 끝남 — 거절 종결; '), wi('R_rej', 'DONE', T2, end_date=T2)]
    got = marks(rows, status='COMPLETED', end_event='E_rej')
    assert 'T_cmd' not in got['st'] and got['st']['R_rej'] == 'done' and got['now'] == []
    # 다시 수행: 앞 차수(0)의 승인 줄은 기다리던 중에 닫혔고(시작된 적 있음), 새 차수(1)의 승인 줄이 지금 내 차례다
    again = [dict(wi('T_agent', 'DONE', T0, end_date=T1), id='a0', generation=0), dict(wi('T_approve', 'CANCELLED', T1, end_date=T2, reached_at=T1, log='rework superseded: r1; '), id='p0', generation=0),
             dict(wi('T_cmd', 'CANCELLED', T1, end_date=T2, reached_at=T1, log='rework superseded: r1; '), id='c0', generation=0),      # 앞 차수에서 시작됐다가 닫힌 줄 — 새 차수의 같은 단계는 아직 예정이다
             dict(wi('T_agent', 'DONE', T2, end_date=T2), id='a1', generation=1), dict(wi('T_approve', 'IN_PROGRESS', T2), id='p1', generation=1), dict(wi('T_cmd', 'TODO', T2), id='c1', generation=1)]
    view = {'definition': DEF, 'instance': {'proc_inst_id': 'p', 'status': 'RUNNING'}, 'workitems': again}
    nodes = run(FILES, "const m = hydFlow.pathModel(DATA.definition, DATA.workitems, DATA.instance); out(m.nodes.map(n => [n.id, n.state]))", view)
    assert ['T_approve', 'now'] in nodes and not any(state == 'fail' for _, state in nodes), nodes
    assert marks(again)['now'] == ['T_approve']


def test_남은_길은_지금_단계에_걸린_기한이_먼저_오면_가는_가지도_말한다():
    """입고를 기다리는 동안 「남은 단계」가 입고 뒤의 두 가지(합격 · 불합격)만 말하고, 그림에는 있는 납기 초과 가지(기한이 먼저 오면 → 지연 결과 보고)는
    말하지 않았다. 지금 단계에 붙은 경계 타이머에서 나가는 길을 따로 싣는다(pathModel().timers). 지금 단계가 아닌 단계의 타이머는 싣지 않는다."""
    view = {'definition': DEF, 'instance': {'proc_inst_id': 'p', 'status': 'RUNNING'},
            'workitems': [wi('T_agent', 'DONE', '01', end_date='02'), wi('T_approve', 'IN_PROGRESS', '02'), wi('T_cmd', 'TODO', None)]}
    got = run(FILES, "const m = hydFlow.pathModel(DATA.definition, DATA.workitems, DATA.instance); out({ timers: m.timers, fork: m.fork.branches.map(b => b.label) })", view)
    assert got['timers'] == [{'label': '승인 지연', 'steps': ['승인 지연 알림'], 'more': None, 'end': None}]
    assert got['fork'] == ['승인', '거절']
    view['workitems'] = [wi('T_agent', 'IN_PROGRESS', '01'), wi('T_approve', 'TODO', None)]      # AI 단계가 지금: 승인 단계의 기한은 아직 걸리지 않았다
    assert run(FILES, "out(hydFlow.pathModel(DATA.definition, DATA.workitems, DATA.instance).timers)", view) == []


def test_가려진_화면에서_그린_흐름_그림은_오류_없이_실리고_보이는_순간_읽을_크기로_놓인다():
    """2026-11-14 한 바퀴: 관리 화면에서 [기준으로 되돌리기]를 하면 흐름 화면이 가려진 채 목록을 다시 읽어 그림을 그린다. 캔버스 크기가 0 이라 bpmn-js 의
    배율이 0 이 되고 「흐름 그림을 그리지 못했습니다 — … non-finite」로 끝나, 그 뒤 흐름 화면을 열면 그림 대신 오류 판이 보였다.
    실제 index.html · flow.js · bpmn-js 를 실제 브라우저로 연다(브라우저 밖의 process 응답만 빈 값으로 준다)."""
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles
    from playwright.sync_api import sync_playwright
    from conftest import ROOT, WWW, Served
    app = FastAPI()
    app.mount('/', StaticFiles(directory=WWW, html=True))
    served = Served(app)
    xml = (ROOT / 'it/process/definitions/shift_handover.bpmn').read_text(encoding='utf-8')
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page(viewport={'width': 1440, 'height': 900})
            errors = []
            page.on('console', lambda m: m.type == 'error' and 'hydFlow' in m.text and errors.append(m.text))
            page.route('**/svc/**', lambda route: route.fulfill(json={}))
            page.goto(served.url + '/index.html')
            page.wait_for_function("() => typeof hydFlow !== 'undefined' && typeof UI !== 'undefined'")
            page.evaluate("""xml => { const box = document.createElement('div'); box.id = 'hiddenFlow'; box.style.display = 'none';
                const host = document.createElement('div'); host.id = 'hiddenFlowHost'; box.appendChild(host); document.querySelector('main').appendChild(box);
                hydFlow.show(host, { key: 'k1', title: '교대', cap: '판본 1', mine: false, load: async () => ({ xml }) }); }""", xml)
            page.wait_for_function("() => { const h = document.querySelector('#hiddenFlowHost'); return h._flow && (h._flow.D || h.querySelector('.alert')); }", timeout=20000)
            assert errors == [] and page.locator('#hiddenFlowHost .alert').count() == 0          # 가려진 채로도 그림은 오류 없이 실린다
            page.evaluate("() => { document.querySelector('#hiddenFlow').style.display = ''; }")
            page.wait_for_function("() => { const z = document.querySelector('#hiddenFlowHost')._flow.D.viewer.get('canvas').zoom(); return Number.isFinite(z) && z > 0; }", timeout=10000)
            page.wait_for_timeout(300)
            got = page.evaluate("""() => { const host = document.querySelector('#hiddenFlowHost'), c = host._flow.D.viewer.get('canvas'), vb = c.viewbox();
                return { zoom: c.zoom(), inside: vb.x <= vb.inner.x && vb.inner.x < vb.x + vb.width, boxes: host.querySelectorAll('.djs-shape').length }; }""")
            assert 0.85 <= got['zoom'] <= 1 and got['inside'] and got['boxes'] > 5, got                # 보이는 순간 읽을 크기로, 그림의 시작 쪽이 판 안에 놓인다
            assert errors == []
            b.close()
    finally:
        served.close()


def test_진행_길의_끝남_지금_남음은_밝은_캔버스에서_서로_다른_색으로_또렷이_보인다():
    """흐름 그림은 밝은 캔버스(옅은 회색 바탕 · 흰 상자)에 그린다. 상태색이 바탕에 묻히면 「어디까지 왔는가」를 읽을 수 없다:
    끝남 · 지금 · 남음의 테두리가 서로 다른 색이고 저마다 캔버스 바탕과 대비 3 이상(글자가 아닌 그림의 기준), 상자 안의 글자는 그 상자의 면과 대비 4.5 이상,
    지금 단계의 꼬리표 글자도 꼬리표 바탕과 4.5 이상이어야 한다. 차선 틀은 상자보다 옅다(상자와 선이 주인공).
    실제 index.html · flow.js · bpmn-js 를 실제 브라우저로 연다(그림 원본이 없는 흐름 — 정의에서 만들어 자동으로 놓는 길)."""
    import json

    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles
    from playwright.sync_api import sync_playwright
    from conftest import WWW, Served
    app = FastAPI()
    app.mount('/', StaticFiles(directory=WWW, html=True))
    served = Served(app)
    view = {'definition': DEF, 'instance': {'proc_inst_id': 'p1', 'status': 'RUNNING', 'end_event': None},
            'workitems': [wi('T_agent', 'DONE', '01'), wi('T_approve', 'IN_PROGRESS', '02'), wi('T_cmd', 'TODO', None)]}
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page(viewport={'width': 1440, 'height': 900})
            page.route('**/svc/**', lambda route: route.fulfill(status=404, body='') if '/bpmn' in route.request.url else route.fulfill(json={}))
            page.goto(served.url + '/index.html')
            page.wait_for_function("() => typeof hydFlow !== 'undefined' && typeof UI !== 'undefined'")
            page.evaluate("""view => { const host = document.createElement('div'); host.id = 'stateFlowHost'; host.style.cssText = 'position:fixed;left:0;top:0;width:1100px;z-index:999';
                document.body.appendChild(host); hydFlow.mount(host, view, { mine: ['T_approve'] }); }""", view)
            page.wait_for_function("() => { const h = document.querySelector('#stateFlowHost'); return h._flow && h._flow.D; }", timeout=20000)
            page.wait_for_timeout(300)
            got = page.evaluate(r"""() => {
              // 색 글(rgb · color(srgb …) · oklch — 키트의 색은 oklch 다)을 브라우저가 실제로 칠하는 값으로 읽는다: 흰 바탕 위에 칠한 한 점
              const lum = c => { const x = document.createElement('canvas').getContext('2d'); x.fillStyle = '#fff'; x.fillRect(0, 0, 1, 1); x.fillStyle = c; x.fillRect(0, 0, 1, 1);
                const [r, g, b] = [...x.getImageData(0, 0, 1, 1).data].slice(0, 3).map(v => v / 255).map(x => x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
              const ratio = (a, b) => { const x = lum(a), y = lum(b); return +((Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05)).toFixed(2); };
              const host = document.querySelector('#stateFlowHost'), bg = getComputedStyle(host.querySelector('.canvas')).backgroundColor;
              const of = id => { const g = host.querySelector(`.djs-shape[data-element-id="${hydFlow.xid(id)}"]`), box = g.querySelector('.djs-visual > rect'), s = getComputedStyle(box), text = g.querySelector('.djs-visual text');
                const fade = parseFloat(getComputedStyle(g.querySelector('.djs-visual')).opacity);
                return { cls: g.getAttribute('class'), stroke: s.stroke, edge: ratio(s.stroke, bg), text: ratio(getComputedStyle(text).fill, s.fill), fade }; };
              const tip = host.querySelector('.bpmn-tip'), ts = getComputedStyle(tip);
              return { done: of('T_agent'), now: of('T_approve'), todo: of('T_cmd'), tip: { text: tip.textContent, ratio: ratio(ts.color, ts.backgroundColor) }, check: host.querySelectorAll('.bpmn-check').length }; }""")
            assert 'is-done' in got['done']['cls'] and 'is-now' in got['now']['cls'] and 'is-todo' in got['todo']['cls'], got
            assert len({got[k]['stroke'] for k in ('done', 'now', 'todo')}) == 3, got                     # 세 상태의 테두리색이 서로 다르다
            assert all(got[k]['edge'] >= 3 for k in ('done', 'now')), got                                 # 끝남 · 지금의 테두리는 캔버스 바탕 위에서 또렷하다
            assert all(got[k]['text'] >= 4.5 for k in ('done', 'now', 'todo')), got                       # 상자 안 글자는 그 상자의 면 위에서 읽힌다
            assert got['todo']['fade'] < 1 and got['done']['fade'] == 1 and got['now']['fade'] == 1, got  # 남은 단계만 흐리다
            assert got['tip']['text'] == '지금 · 내 차례' and got['tip']['ratio'] >= 4.5 and got['check'] == 1, got
            b.close()
    finally:
        served.close()
