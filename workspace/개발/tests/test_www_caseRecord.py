"""처리 기록(it/portal/www/caseRecord.js hydRecord.build) — 처리 건 view 한 건으로 만든 단계 이야기의 차례 · 문장.
node 에서 실제 화면 모듈을 차례대로 실어 build 를 부른다(DOM 없이 도는 부분)."""
import pytest

from www_node import run

FILES = ['ui.js', 'plainWords.js', 'trace.js', 'approvalCard.js', 'resultReport.js', 'caseRecord.js']
T = '2026-10-30T05:44:45.305Z'


def view(workitems, timeline, variables=(), events=()):
    acts = [{'id': w['activity_id'], 'name': w['activity_name'], 'type': 'serviceTask', 'tool': w.get('tool', '')} for w in workitems]
    return {'instance': {'proc_inst_id': 'c.1', 'proc_def_id': 'c', 'status': 'COMPLETED', 'start_date': '2026-10-30T05:40:00Z', 'end_date': T,
                         'variables_data': [{'key': k, 'value': v} for k, v in variables], 'variable_sources': {}},
            'definition': {'id': 'c', 'roles': [], 'gateways': [], 'activities': acts,
                           'events': [{'id': 'S', 'type': 'startEvent', 'name': '시작'}, {'id': 'E', 'type': 'endEvent', 'name': '끝'}], 'sequences': []},
            'workitems': [{'status': 'DONE', 'agent_orch': 'system', **w} for w in workitems],
            'flow_order': {a: i for i, a in enumerate(timeline)}, 'events': list(events), 'approvals': []}


def titles(v, ext=None):
    return run(FILES, "out(hydRecord.build(DATA.v, DATA.ext, []).steps.map(s => s.title))", {'v': v, 'ext': ext or {'agents': [], 'people': []}})


def test_같은_순간에_끝난_시스템_단계는_흐름_순서대로_보인다():
    """W1-01: 정비 오더 등록과 결과 보고가 한 트랜잭션에서 같은 시각에 끝나 「결과 보고 → 정비 오더」로 거꾸로 보였다."""
    wis = [{'id': 'w2', 'activity_id': 'R_ok', 'activity_name': '결과 보고: 정상', 'start_date': T, 'end_date': T},
           {'id': 'w1', 'activity_id': 'T_wo', 'activity_name': '작업지시 등록', 'start_date': T, 'end_date': T}]
    assert titles(view(wis, ['T_wo', 'R_ok'])) == ['시작', '정비 요청 등록', '결과 보고: 정상', '처리 완료']      # 옛 판본의 단계 이름 「작업지시 등록」은 지금 이름으로 보인다(ui.js flow.name)


def test_처리_기록을_그려도_다른_화면의_값_이름이_정의_설명문으로_바뀌지_않는다():
    """W1-02: 처리 건 정의의 칸 설명(「판정한 원인 노드 id …」)이 전역 이름 사전을 덮어 승인 카드 · 다른 처리 건까지 바뀌었다."""
    v = view([{'id': 'w1', 'activity_id': 'T_a', 'activity_name': '원인 진단', 'start_date': T, 'end_date': T}], ['T_a'])
    v['definition']['startForm'] = {'fields_json': [{'key': 'cause', 'text': '판정한 원인 노드 id (예: cause:cooler-fin-fouling)'}]}
    got = run(FILES, "const before = hydWords.fieldName('cause'); hydRecord.build(DATA, { agents: [], people: [] }, []); out([before, hydWords.fieldName('cause')])", v)
    assert got == ['판정 원인', '판정 원인']


@pytest.mark.parametrize('sim_s, wall, expected', [
    (1200.0, ('05:43:42.085', '05:44:45.557'), '설비 시간 20분 (실제 1분 3초) 동안'),   # 연장 뒤 판정 줄의 설비 시간(시작 줄 15분이 아니라)
    (900.0, ('05:43:42.000', '05:44:27.000'), '설비 시간 15분 (실제 45초) 동안'),
])
def test_효과_확인_문장은_설비_시간과_실제_시간을_한_형식으로_적는다(sim_s, wall, expected):
    """W1-03: 효과 확인 단계가 「1분 3초 동안」(실제)만 말해 같은 카드의 「설비 시간 15분」과 어긋났다."""
    a, b = (f'2026-10-30T{t}Z' for t in wall)
    inc = {'id': 'INC-1', 'asset': 'HYD-01', 'state': 'CLOSED', 'recoveryPolicy': {'criterion': ['TS1', '<', 55]},
           'history': [{'state': 'RE_OBSERVING', 't': a, 'reobservation': {'sim_s': 900}},
                       {'state': 'RESOLVED', 't': b, 'note': '재관측 결과 회복', 'reobservation': {'tag': 'TS1', 'op': '<', 'limit': 55, 'value': 51.2, 'cleared': True, 'recovered': True, 'sim_s': sim_s}}],
           'reobsSeries': {'tag': 'TS1', 'op': '<', 'limit': 55, 'first': 60.8, 'last': 51.2, 'inside_share': 0.64, 'inside_last': True, 'from': a, 'to': b,
                           'points': [{'t': a, 'v': 60.8}, {'t': b, 'v': 51.2}]}}
    wis = [{'id': 'w1', 'activity_id': 'T_reobs', 'activity_name': '재관측', 'tool': 'incident:reobserve', 'start_date': a, 'end_date': b, 'output': {'recovered': True}}]
    v = view(wis, ['T_reobs'], variables=[('incident', 'INC-1'), ('recovered', True)])
    got = run(FILES, "const m = hydRecord.build(DATA.v, { agents: [], people: [], incident: DATA.inc }, []); out(m.steps.find(s => s.title === '효과 확인').sentence)",
              {'v': v, 'inc': inc})
    assert got.startswith(expected) and '기준(55 ℃ 아래) 안에 있던 시간 64 %' in got, got


def test_발주_단계의_공급사는_승인_때_확정한_업무_DB_공급사_이름으로_보인다():
    """넘김 FW → FT 덧: 공급사(sup:*)는 업무 DB 동기화로만 생겨 이름 사전에 없고, 판단 카드 선택지에 없으면 화면에 sup:c 가 보였다."""
    wis = [{'id': 'w1', 'activity_id': 'T_po', 'activity_name': '발주', 'tool': 'mcp__enterprise-purchase__PR_CREATE', 'start_date': T, 'end_date': T,
            'output': {'purchase_order': {'ref': 'PO-7'}}}]
    v = view(wis, ['T_po'], variables=[('approved_supplier', 'sup:c'), ('approved_supplier_name', '대성유압'), ('approved_qty', 2)])
    got = run(FILES, "out(hydRecord.build(DATA, { agents: [], people: [] }, []).steps.find(s => s.title === '발주').sentence)", v)
    assert '대성유압' in got and 'sup:c' not in got, got


def test_처리_기록의_원문_칸은_코드_값을_이름으로_바꾸지_않고_경로만_가린다():
    """한바퀴3: 「물은 원문」의 "pattern": "COOLER_DEGRADATION" 이 설명용 이름 바꾸기(UI.words)로 "쿨러 성능 저하"가 돼, 원문이 실제 호출과 달랐다."""
    # 원문 칸은 원문 판 하나(UI.raw — 이 PC 경로 · 모델 이름만 가린다)로 그린다
    got = run(FILES, "UI.patterns = {COOLER_DEGRADATION: '쿨러 성능 저하'}; out([UI.raw(DATA, { mask: true }), UI.clean('COOLER_DEGRADATION 경보')])",
              {'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION', 'file': '/home/user/work/result.json'})
    assert '&quot;pattern&quot;: &quot;COOLER_DEGRADATION&quot;' in got[0] and '쿨러 성능 저하' not in got[0]
    assert '&quot;file&quot;: &quot;result.json&quot;' in got[0] and '/home/user' not in got[0]
    assert got[1] == '쿨러 성능 저하 경보', '설명 문장(UI.clean)은 그대로 이름으로 바꾼다'


def test_결과_카드는_끝_이벤트_이름이_끝이면_끝난_곳을_따로_적지_않고_반려는_실패_색으로_칠하지_않는다():
    """「끝난 곳: 끝」처럼 뜻 없는 줄이 결과 카드에 나왔다. 끝 이벤트에 뜻 있는 이름(거절 종결)이 있을 때만 한 문장으로 적는다."""
    def card(report, end_label):
        v = view([{'id': 'w1', 'activity_id': 'R', 'activity_name': '결과 보고', 'start_date': T, 'end_date': T}], ['R'], variables=[('result_report', report)])
        v['instance']['end_label'] = end_label
        return run(FILES, "out(hydResultReport.html(DATA))", v)
    ok = card({'outcome': '정상', 'level': 'ok', 'title': 'HYD-01 긴급 대응 결과', 'summary': '유온 정상 · 경보 해제'}, '끝')
    assert '끝난 곳' not in ok and '에서 끝났습니다' not in ok
    assert '<div class="result-main">유온 정상 · 경보 해제</div>' in ok and 'data-tone="ok">정상</span>' in ok
    rejected = card({'outcome': '반려', 'verdict': 'rejected', 'title': 'HYD-01 냉각 조치 결과', 'summary': '담당자가 거절했습니다'}, '거절 종결')
    assert '처리 건은 「거절 종결」에서 끝났습니다.' in rejected
    assert 'data-tone="danger"' not in rejected and '<span class="tag">반려</span>' in rejected


def test_워커가_아직_가져가지_않은_AI_단계는_사람_단계로_그리지_않는다():
    """독립 검토 가-4: AI 에이전트가 맡은 작업 행은 워커가 가져가기 전 잠깐 agent_orch 가 비어 있다 — 그 순간 사람 단계(승인 대기)로 보였다."""
    wis = [{'id': 'w1', 'activity_id': 'T_agent', 'activity_name': '원인 진단', 'start_date': T, 'status': 'IN_PROGRESS', 'agent_orch': None, 'agent_mode': None, 'user_id': 'agent:cooling'}]
    v = view(wis, ['T_agent'])
    v['instance']['status'] = 'RUNNING'
    got = run(FILES, "out(hydRecord.build(DATA.v, DATA.ext, []).steps.map(s => [s.type, s.lane]))", {'v': v, 'ext': {'agents': [], 'people': []}})
    assert got[1] == ['agent', 'agent']


def test_정비_수행_문장은_서버가_적은_정비_완료_공지를_그대로_쓰고_화면이_복구를_지어_말하지_않는다():
    """화면 정돈 2단계: 승인한 조치가 다루는 구성 요소만 고친다(서버 maintenance.notice · scope). 전에는 화면이 「설비 … 복구를 기록했습니다」를 지어 붙여
    틀린 조치를 승인한 건도 고친 것처럼 읽혔다."""
    notice = 'HYD-01 정비 완료 — WO-1 완료. 승인한 조치 방법 SOP-X이(가) 다루는 팬 베어링은(는) 가상 설비에서 이미 정상이라 바꾼 것이 없습니다'
    wis = [{'id': 'w1', 'activity_id': 'T_m', 'activity_name': '정비 수행', 'tool': 'plant:restore', 'start_date': T, 'end_date': T,
            'output': {'maintenance': {'asset': 'HYD-01', 'component': None, 'work_order': 'WO-1', 'notice': notice, 'scope': {'sop': 'SOP-X', 'targets': [], 'why': '다루는 구성 요소 없음'}}}}]
    got = run(FILES, "const s = hydRecord.build(DATA, { agents: [], people: [] }, []).steps.find(s => s.title === '정비 수행'); out([s.sentence, s.sections.filter(Boolean).map(x => x.title)])", view(wis, ['T_m']))
    assert got[0] == notice and '복구를 기록' not in got[0]
    assert '승인한 조치가 고친 것' in got[1] and '정비 완료 알림' not in got[1]


@pytest.mark.parametrize('received, rejected, state, word', [(False, 2, 'bad', '일부만 입고됐습니다 — 불합격 2개 반품'), (True, 0, 'ok', '입고 · 검수')])
def test_검수에서_일부가_불합격인_입고는_정상이_아니라_기준_밖으로_보인다(received, rejected, state, word):
    """화면 정돈 2단계: 서버는 부분 입고를 received=false 로 넘겨 「미달」 가지로 보낸다. 전에는 입고 기록이 있기만 하면 화면이 초록 체크와 「기록했습니다」로 그렸다."""
    wis = [{'id': 'w1', 'activity_id': 'T_gr', 'activity_name': '입고 확인', 'tool': 'enterprise:GR_CONFIRM', 'start_date': T, 'end_date': T,
            'output': {'received': received, 'goods_receipt': {'ref': 'GR-1', 'detail': '씰 키트 6개 가운데 4개 입고', 'after': {'rejected_qty': rejected}}}}]
    got = run(FILES, "const s = hydRecord.build(DATA, { agents: [], people: [] }, []).steps.find(s => s.title === '입고 확인'); out([s.type, s.state || 'ok', s.sentence])", view(wis, ['T_gr']))
    assert got[0] == 'check' and got[1] == state and word in got[2], got


def test_잘려_온_도구_결과는_JSON_오류로_읽지_않고_보관된_전체_결과를_기다리며_정말_못_읽는_결과만_그_까닭을_적는다():
    """워커는 4,000자를 넘는 도구 결과를 잘라 보내고(output_truncated) 전체는 따로 보관한다(full_output). 실행 기록의 한 줄이 잘린 미리보기를 JSON 으로
    읽어, 성공한 줄에 「구조화 응답을 JSON으로 읽을 수 없습니다」가 붙었다(화면 정돈 2단계는 그 말을 끝난 줄에서 숨기기만 했다)."""
    def ev(kind, tid, **data):
        return {'id': f'{kind}-{tid}', 'event_type': kind, 'timestamp': T, 'proc_inst_id': 'c.1', 'todo_id': 'w1', 'job_id': 'j1', 'data': {'tool': 'mcp__hyd-dmn__diagnose', 'tool_use_id': tid, **data}}
    cut = '{"result":"ok","document":{"withheld":false,"causes":[{"name":"쿨러 핀 오염"'      # 4,000자에서 잘린 JSON(닫히지 않았다)
    ref = {'stored': True, 'ref': 'a' * 64, 'sha256': 'b' * 64, 'chars': 9000, 'original_chars': 9000, 'cut': False, 'content_type': 'json', 'source': 'tool_result'}
    events = [ev('tool_usage_started', 't1', input={'asset': 'HYD-01'}), ev('tool_usage_finished', 't1', output=cut, output_truncated=True, full_output=ref, is_error=False),
              ev('tool_usage_started', 't2', input={'asset': 'HYD-01'}), ev('tool_usage_finished', 't2', output='{"result":"ok","document":{"note":"짧은 결과"}}', is_error=False),
              ev('tool_usage_started', 't3', input={'asset': 'HYD-01'}), ev('tool_usage_finished', 't3', output='{"result": 깨진 글', is_error=False)]
    got = run(FILES, "const rows = hydRecord.rowsOf(DATA).filter(r => r.kind === 'tool'); out(rows.map(r => hydRecord.lineOf(r, false, false)))", events,
              prelude='globalThis.queueMicrotask = () => {};')      # 브라우저의 것: 보관된 전체 결과를 읽으러 가는 예약(시험 문맥에는 서버가 없다)
    assert len(got) == 3
    assert 'JSON으로 읽을 수 없습니다' not in got[0] and '마쳤습니다' in got[0]            # 잘린 미리보기: 전체 결과를 읽어 오는 동안 받은 것을 비워 둔다(오류로 적지 않는다)
    assert 'JSON으로 읽을 수 없습니다' not in got[1] and '마쳤습니다' in got[1]
    assert 'JSON으로 읽을 수 없습니다' in got[2]                                          # 잘리지 않았는데 정말 읽을 수 없는 결과는 숨기지 않는다


def test_가지_않은_길의_단계는_단계_기록의_본줄에_서지_않고_이름만_따로_모이며_한_일의_문장을_만들지_않는다():
    """반려로 끝난 건의 단계 기록에 「냉각 명령 — 취소: … — 설비 제어에 명령을 보냈고 …」(보내지 않았다)와 「효과 확인 … 회복으로 판정했습니다」가
    붉은 ✕로 줄줄이 섰다. 한 번도 시작되지 않은 채 닫힌 줄은 일어난 일이 아니다 — 본줄에서 빼고 이름만 모은다(build().skipped)."""
    T0, T1 = '2026-10-30T05:40:00.000Z', T
    wis = [{'id': 'w1', 'activity_id': 'R_rej', 'activity_name': '결과 보고: 반려', 'tool': 'process:report', 'start_date': T1, 'end_date': T1},
           {'id': 'w2', 'activity_id': 'T_cmd', 'activity_name': '냉각 명령', 'tool': 'incident:command', 'status': 'CANCELLED', 'start_date': T0, 'end_date': T1, 'log': '취소: 처리 건이 끝남 — 반려 종결; '},
           {'id': 'w3', 'activity_id': 'T_obs', 'activity_name': '효과 확인', 'tool': 'incident:reobserve', 'status': 'CANCELLED', 'start_date': T0, 'end_date': T1, 'log': '취소: 처리 건이 끝남 — 반려 종결; '}]
    v = view(wis, ['T_cmd', 'T_obs', 'R_rej'])
    v['workitems'].append({'id': 'w0', 'activity_id': 'T_a', 'activity_name': '원인 진단', 'status': 'DONE', 'agent_orch': 'system', 'start_date': T0, 'end_date': T1})
    got = run(FILES, "const m = hydRecord.build(DATA, { agents: [], people: [] }, []); out({ titles: m.steps.map(s => s.title), skipped: m.skipped.map(x => x.name), said: m.steps.map(s => s.sentence || '').join(' ') })", v)
    assert '냉각 명령' not in got['titles'] and '효과 확인' not in got['titles'] and got['skipped'] == ['냉각 명령', '효과 확인']
    assert '명령을 보냈' not in got['said'] and '판정했습니다' not in got['said']


def test_효과_확인이_늘어나면_연장됐다는_것과_까닭을_말하고_판정_전을_판정_중했습니다로_적지_않는다():
    """판정 예정 시각이 지나면 말없이 「판정까지 11초」를 다시 셌다(서버는 값이 기준 안인데 경보가 아직 꺼지지 않아 늘린 것 — 기록 줄
    REOBSERVATION_EXTENDED). 연장 중 머리 문장은 「… 51 % — 판정 중했습니다.」였다."""
    a = '2026-10-30T05:43:42.000Z'
    series = {'tag': 'TS1', 'op': '<', 'limit': 55, 'first': 60.3, 'last': 52.3, 'inside_share': 0.51, 'inside_last': True, 'from': a, 'to': T, 'points': [{'t': a, 'v': 60.3}, {'t': T, 'v': 52.3}]}
    inc = {'id': 'INC-1', 'asset': 'HYD-01', 'state': 'RE_OBSERVING', 'recoveryPolicy': {'criterion': ['TS1', '<', 55]},
           'history': [{'state': 'RE_OBSERVING', 't': a, 'reobservation': {'sim_s': 900, 'tag': 'TS1', 'op': '<', 'limit': 55}}], 'reobsSeries': series}
    plan = {'kind': 'command', 'due_at': '2099-01-01T00:00:00Z', 'window_s': 45.0, 'extensions': 1, 'started_at': a}
    events = [{'id': 'e1', 'event_type': 'task_working', 'timestamp': T, 'proc_inst_id': 'c.1', 'todo_id': 'w1', 'job_id': 'REOBSERVATION_EXTENDED',
               'data': {'name': '효과 확인 연장 (값은 기준 안, 경보 해제 대기)', 'plan': plan, 'reading': {'tag': 'TS1', 'op': '<', 'limit': 55, 'value': 52.3, 'inside': True}}}]
    wis = [{'id': 'w1', 'activity_id': 'T_reobs', 'activity_name': '효과 확인', 'tool': 'incident:reobserve', 'status': 'IN_PROGRESS', 'start_date': a, 'end_date': None}]
    v = view(wis, ['T_reobs'], variables=[('incident', 'INC-1'), ('asset', 'HYD-01')], events=events)
    v['instance'].update(status='RUNNING', end_date=None)
    got = run(FILES, "const m = hydRecord.build(DATA.v, { agents: [], people: [], incident: DATA.inc }, DATA.v.events); const s = m.steps.find(x => x.title === '효과 확인'); out([s.sentence, s.liveLine || '', s.liveBox || ''])",
              {'v': v, 'inc': inc}, prelude="globalThis.state = { plant: { units: { 'HYD-01': { tags: { TS1: 52.3 } } } } };")
    sentence, line, box = got
    assert '판정 중했습니다' not in sentence and sentence.endswith('아직 판정하지 않았습니다.'), sentence
    assert '연장됨 — 값은 기준 안인데 경보가 아직 꺼지지 않아 더 지켜봅니다' in line and '연장됨' in box and '판정까지 (연장)' in box
    assert '>52.3</span>' in line and '판정까지 ' in line and '>–<' not in line      # 그릴 때 아는 값과 남은 시간을 바로 적는다(「– ℃ · –」로 그렸다가 채우지 않는다)
