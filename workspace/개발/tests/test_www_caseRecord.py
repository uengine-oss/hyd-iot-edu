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


@pytest.mark.parametrize('sim_s, wall, series, expected', [
    # 값은 기준 안인데 경보 해제가 늦어 한 번 늘린 판정 줄(설비 시간 20분) — 도는 동안 본 기본 창 15분과 늘린 만큼을 따로 적는다
    (1200.0, ('05:43:42.085', '05:44:45.557'), True, '설비 시간 15분 + 연장 5분 (실제 1분 3초) 동안 유온 60.8→51.2 ℃, 기준(55 ℃ 아래) 안에 있던 시간 64 % — 회복으로 판정했습니다.'),
    (900.0, ('05:43:42.000', '05:44:27.000'), True, '설비 시간 15분 (실제 45초) 동안 유온 60.8→51.2 ℃, 기준(55 ℃ 아래) 안에 있던 시간 64 % — 회복으로 판정했습니다.'),
    (1800.0, ('05:43:42.000', '05:45:12.000'), False, '설비 시간 15분 + 연장 15분 동안 지켜본 뒤 유온 51.2 ℃ — 기준 ‘유온 < 55 ℃’ 안이라 회복으로 판정했습니다.'),   # 값 흐름 없는 판정 줄 · 세 번 늘림
])
def test_효과_확인_문장은_설비_시간과_실제_시간을_한_형식으로_적고_늘린_창은_기본_창과_따로_적는다(sim_s, wall, series, expected):
    """W1-03: 효과 확인 단계가 「1분 3초 동안」(실제)만 말해 같은 카드의 「설비 시간 15분」과 어긋났다. 2026-11-17 06 촬영 전: 도는 동안
    「(설비 시간 15분)」이던 같은 단계가 끝난 뒤 「설비 시간 20분 (실제 1분 2초)」로 보여 시간이 달라 보였다 — 서버가 창을 늘린 것(15분 + 5분)인데
    늘렸다는 말 없이 합만 적었다. 판정 줄의 설비 시간이 시작 줄의 기본 창보다 길면 「기본 창 + 연장」으로 적는다."""
    a, b = (f'2026-10-30T{t}Z' for t in wall)
    inc = {'id': 'INC-1', 'asset': 'HYD-01', 'state': 'CLOSED', 'recoveryPolicy': {'criterion': ['TS1', '<', 55]},
           'history': [{'state': 'RE_OBSERVING', 't': a, 'reobservation': {'sim_s': 900}},
                       {'state': 'RESOLVED', 't': b, 'note': '재관측 결과 회복', 'reobservation': {'tag': 'TS1', 'op': '<', 'limit': 55, 'value': 51.2, 'cleared': True, 'recovered': True, 'sim_s': sim_s}}]}
    if series:
        inc['reobsSeries'] = {'tag': 'TS1', 'op': '<', 'limit': 55, 'first': 60.8, 'last': 51.2, 'inside_share': 0.64, 'inside_last': True, 'from': a, 'to': b,
                              'points': [{'t': a, 'v': 60.8}, {'t': b, 'v': 51.2}]}
    wis = [{'id': 'w1', 'activity_id': 'T_reobs', 'activity_name': '재관측', 'tool': 'incident:reobserve', 'start_date': a, 'end_date': b, 'output': {'recovered': True}}]
    v = view(wis, ['T_reobs'], variables=[('incident', 'INC-1'), ('recovered', True)])
    got = run(FILES, "const m = hydRecord.build(DATA.v, { agents: [], people: [], incident: DATA.inc }, []); const s = m.steps.find(s => s.title === '효과 확인'); out([s.sentence, UI.leadRest(s.sentence, 110)[0]])",
              {'v': v, 'inc': inc})
    assert got[0] == expected, got[0]
    assert got[1] == got[0]          # 단계 줄의 보조 글(caseRecord stepRow — 110자 넘으면 가른다)에 판정까지 다 보인다


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
    # 긴 결과 문장은 결론 한 마디만 굵게, 나머지 근거는 그 아래에 그대로 잇는다(굵은 글씨 여섯 줄이 화면을 덮었다)
    long = '펌프 축 씰 키트 발주 7개 중 6개 입고 · 1개 검수 불합격 반품 (발주 PR-1, 로트 LOT-PR-1, A정밀 불량률 12 % × 7개 = 기대 불량 0.84개) — 업무 시간 리드타임 2일을 실제 24초로 줄여 기다린 뒤 입고했습니다'
    short = card({'outcome': '미달', 'level': 'fail', 'title': '재고 보충 결과', 'summary': long}, '끝')
    assert '<div class="result-main">펌프 축 씰 키트 발주 7개 중 6개 입고 · 1개 검수 불합격 반품</div>' in short
    assert '<div class="result-sub" data-rest>(발주 PR-1, 로트 LOT-PR-1, A정밀 불량률 12 % × 7개 = 기대 불량 0.84개) — 업무 시간' in short and '입고했습니다</div>' in short
    assert 'data-rest' not in ok
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
    붉은 ✕로 줄줄이 섰다. 흐름이 닿은 적 없이 닫힌 줄(서버의 reached_at 이 null)은 일어난 일이 아니다 — 본줄에서 빼고 이름만 모은다(build().skipped).
    흐름이 닿았다가 취소된 줄(reached_at 에 시각)은 본줄에 서고 「닿았지만 시작하기 전에 취소됐다」고 말한다."""
    T0, T1 = '2026-10-30T05:40:00.000Z', T
    wis = [{'id': 'w1', 'activity_id': 'R_rej', 'activity_name': '결과 보고: 반려', 'tool': 'process:report', 'start_date': T1, 'end_date': T1},
           {'id': 'w2', 'activity_id': 'T_cmd', 'activity_name': '냉각 명령', 'tool': 'incident:command', 'status': 'CANCELLED', 'start_date': T0, 'end_date': T1, 'reached_at': None, 'log': '취소: 처리 건이 끝남 — 반려 종결; '},
           {'id': 'w3', 'activity_id': 'T_obs', 'activity_name': '효과 확인', 'tool': 'incident:reobserve', 'status': 'CANCELLED', 'start_date': T0, 'end_date': T1, 'reached_at': None, 'log': '취소: 처리 건이 끝남 — 반려 종결; '}]
    v = view(wis, ['T_cmd', 'T_obs', 'R_rej'])
    v['workitems'].append({'id': 'w0', 'activity_id': 'T_a', 'activity_name': '원인 진단', 'status': 'DONE', 'agent_orch': 'system', 'start_date': T0, 'end_date': T1})
    got = run(FILES, "const m = hydRecord.build(DATA, { agents: [], people: [] }, []); out({ titles: m.steps.map(s => s.title), skipped: m.skipped.map(x => x.name), said: m.steps.map(s => s.sentence || '').join(' ') })", v)
    assert '냉각 명령' not in got['titles'] and '효과 확인' not in got['titles'] and got['skipped'] == ['냉각 명령', '효과 확인']
    assert '명령을 보냈' not in got['said'] and '판정했습니다' not in got['said']
    # 흐름이 닿았다가 취소된 줄: 가지 않은 길이 아니다 — 본줄에 서고, 한 일의 문장 대신 닿았지만 시작 전에 취소됐다고 말한다
    wis[1]['reached_at'] = T0
    got = run(FILES, "const m = hydRecord.build(DATA, { agents: [], people: [] }, []); out({ steps: m.steps.map(s => [s.title, s.sentence || '']), skipped: m.skipped.map(x => x.name) })", view(wis, ['T_cmd', 'T_obs', 'R_rej']))
    assert got['skipped'] == ['효과 확인']
    assert ['냉각 명령', '흐름이 이 단계에 닿았지만, 일을 시작하기 전에 닫혔습니다 — 처리 건이 끝남 — 반려 종결.'] in got['steps']      # 한 일의 문장이 아니라 닫혔다는 것과 까닭 한 번


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


def test_사람이_넣은_값으로_연_건의_시작은_센서_경보가_아니라_누가_무엇을_넣었는지로_말한다():
    """오일 분석 입력(사람 입력 경보 — source human_input)으로 연 건의 시작 단계가 「센서 경보로 시작 — HYD-01의 센서 값이 경보 규칙에 걸려 …」라고 했다.
    센서가 낸 경보가 아니다: 넣은 사람 · 항목 · 값 · 기준 이탈 여부를 말한다. 센서 경보로 연 건은 그대로 센서 경보다."""
    def start(alert):
        v = view([{'id': 'w1', 'activity_id': 'T', 'activity_name': '현장 검토', 'start_date': T, 'end_date': T}], ['T'], variables=[('alert', alert)])
        return run(FILES, "const s = hydRecord.build(DATA, { agents: [], people: [] }, []).steps[0]; out([s.title, s.actor, s.sentence, s.lane])", v)
    typed = {'t': T, 'asset': 'HYD-01', 'state': 'RAISE', 'source': 'human_input', 'alertId': 'A1', 'pattern': 'OIL_ANALYSIS', 'enteredBy': {'id': 'user:me', 'name': '담당자'},
             'evidence': {'item': 'tan', 'item_name': '산가 TAN', 'value': 21, 'unit': 'mgKOH/g', 'out_of_spec': True, 'memo': '시료'}}
    title, actor, sentence, lane = start(typed)
    assert (title, actor, lane) == ('사람이 넣은 값으로 시작', '담당자', 'person')
    assert '담당자가 HYD-01의 산가 TAN 21 mgKOH/g를 기준 이탈로 넣어' in sentence and '센서' not in sentence
    sensor = {'t': T, 'asset': 'HYD-01', 'state': 'RAISE', 'source': 'detector', 'alertId': 'A2', 'pattern': 'COOLER_DEGRADATION', 'evidence': {'values': {'TS1': 55.6}}}
    assert start(sensor)[0] == '센서 경보로 시작'


def test_AI_결론의_근거_줄은_조사를_바로_앞_낱말에_맞추고_주의_글을_제_줄로_보인다():
    """「조치 3개를 순위 식으로 견줘 「순정(OEM) 공급사 표준 발주」 SOP-PUR-11가 -420점으로 …」: 조사를 이름에 맞춰 놓고 그 사이에 절차 번호를 끼워, 번호 뒤의
    조사가 틀렸다(십일 + 가). 조사는 바로 앞에 보이는 낱말에 맞춘다. 감점 · 경고 규칙의 글(「… 표시한다.」)은 결론 아래 한 줄에 이어 붙이지 않고 근거 줄 하나로 둔다."""
    opts = [{'id': 'skill:a', 'name': '순정(OEM) 공급사 표준 발주', 'sopId': 'SOP-PUR-11', 'score': -420, 'feasible': True, 'rank': 1, 'penalties': [{'annotation': '발주안에 전결 기준 초과를 표시한다.'}]},
            {'id': 'skill:b', 'name': '대체 공급사 발주', 'sopId': 'SOP-PUR-12', 'score': -475, 'feasible': True, 'rank': 2}]
    data = {'s': {'w': {'id': 'w1', 'output': {}}, 'type': 'agent'},
            'm': {'v': {}, 'inst': {'variable_sources': {}}, 'steps': [{'type': 'agent'}], 'decision': {'id': 'D1', 'recommended': 'skill:a', 'options': opts, 'facts': {}}}}
    got = run(FILES, "const f = hydRecord.agentFront(DATA.s, DATA.m); out({ sub: f.sub, evid: f.evid.map(x => x[1].replace(/<[^>]+>/g, '')) })", data)
    line = next(x for x in got['evid'] if '순위 식' in x)
    assert 'SOP-PUR-11이 −420점으로 가장 높았습니다' in line and 'SOP-PUR-11가' not in line
    assert '주의 발주안에 전결 기준 초과를 표시한다.' in got['evid'] and '주의' not in got['sub']
    opts[0]['sopId'] = 'SOP-PUR-12'                                  # 번호가 「이」로 끝나면 「가」
    got = run(FILES, "out(hydRecord.agentFront(DATA.s, DATA.m).evid.map(x => x[1].replace(/<[^>]+>/g, '')).join(' '))", data)
    assert 'SOP-PUR-12가 −420점으로' in got


def _agent_front(decision, recorded, cause='cause:pump-shaft-seal-wear'):
    """AI 단계 하나(이 단계가 원인과 판단을 냈다 — variable_sources)의 결론 · 근거 줄(hydRecord.agentFront)."""
    sources = {k: {'kind': 'workitem', 'id': 'w1'} for k in ('cause', 'decision', 'decision_id')}
    data = {'s': {'w': {'id': 'w1', 'output': {'decision': recorded, 'decision_id': 'D1'}}, 'type': 'agent'},
            'm': {'v': {'cause': cause, 'guide_card': {}}, 'inst': {'variable_sources': sources}, 'steps': [{'type': 'agent'}], 'decision': decision}}
    return run(FILES, "UI.names['cause:pump-shaft-seal-wear'] = '펌프 축 씰 마모'; const f = hydRecord.agentFront(DATA.s, DATA.m);"
                      "out({ verdict: f.verdict, evid: f.evid.map(x => x[1].replace(/<[^>]+>/g, '')), opts: f.opts.map(o => [o.id, o.score]) })", data)


PM_OPTS = [{'id': 'skill:sop-pm-11', 'name': '이번 예정된 정비 시간에 단독 시행', 'sopId': 'SOP-PM-11', 'score': 2.04, 'feasible': True, 'rank': 1},
           {'id': 'skill:sop-pm-12', 'name': '지금 바로 정지하고 시행', 'sopId': 'SOP-PM-12', 'score': -2.04, 'feasible': True, 'rank': 2}]


def _pm_decision(route='prevention', recommended='skill:sop-pm-11'):
    return {'id': 'D1', 'recommended': recommended, 'options': PM_OPTS, 'facts': {},
            'scenario': {'cause': '펌프 축 씰 마모', 'failureMode': '주 펌프 체적 효율 저하'}, 'origin': {'cause_route': route} if route else {}}


def test_결과_글의_점수가_등록한_판단과_달라도_AI_단계의_결론은_그_단계가_등록한_판단의_추천안을_말한다():
    """2026-11-14 정기 정비 한 건: 준비된 결과 글을 재생한 단계는 결과에 그 글을 쓸 때의 점수(1.54)를 적는데, 이 PC 가 등록한 판단의 점수는 2.04 였다.
    점수까지 같아야 같은 판단으로 읽어, 결론이 추천안 없이 「원인을 … 판단했습니다」뿐이었다(승인 단계는 그 추천안을 승인했다고 말하는데).
    추천 · 후보 · 순위가 같으면 그 단계가 등록한 판단이다 — 결론이 추천안을 말하고 점수는 등록한 판단의 것이다. 추천이 다르면 다른 판단이라 쓰지 않는다."""
    replayed = {'recommended': 'skill:sop-pm-11', 'order': [{'id': 'skill:sop-pm-11', 'rank': 1, 'score': 1.54}, {'id': 'skill:sop-pm-12', 'rank': 2, 'score': -2.54}]}
    got = _agent_front(_pm_decision(), replayed)
    assert '「이번 예정된 정비 시간에 단독 시행」을 추천합니다' in got['verdict'], got
    assert got['opts'] == [['skill:sop-pm-11', 2.04], ['skill:sop-pm-12', -2.04]]
    other = _agent_front(_pm_decision(), dict(replayed, recommended='skill:sop-pm-12'))            # 결과가 적은 추천이 등록한 판단과 다르다
    assert other['opts'] == [] and '추천합니다' not in other['verdict'] and other['verdict'] == '', other
    swapped = _agent_front(_pm_decision(), {'recommended': 'skill:sop-pm-11', 'order': [{'id': 'skill:sop-pm-11', 'rank': 2}, {'id': 'skill:sop-pm-12', 'rank': 1}]})
    assert swapped['opts'] == [] and swapped['verdict'] == '', swapped                              # 순위가 다르다


def test_다시_평가한_판단에서는_결과가_적은_점수와_같은_판을_고른다():
    """판단 기록은 다시 평가되면 처음 판(original_decision)을 안에 지닌다. 추천 · 순위가 같은 두 판 가운데 결과가 적은 점수와 같은 판이 그 단계의 판단이다."""
    first = dict(_pm_decision(), options=[dict(PM_OPTS[0], score=1.54), dict(PM_OPTS[1], score=-2.54)])
    now = dict(_pm_decision(), original_decision=first)
    made_first = {'recommended': 'skill:sop-pm-11', 'order': [{'id': 'skill:sop-pm-11', 'rank': 1, 'score': 1.54}, {'id': 'skill:sop-pm-12', 'rank': 2, 'score': -2.54}]}
    made_now = {'recommended': 'skill:sop-pm-11', 'order': [{'id': 'skill:sop-pm-11', 'rank': 1, 'score': 2.04}, {'id': 'skill:sop-pm-12', 'rank': 2, 'score': -2.04}]}
    assert _agent_front(now, made_first)['opts'] == [['skill:sop-pm-11', 1.54], ['skill:sop-pm-12', -2.54]]
    assert _agent_front(now, made_now)['opts'] == [['skill:sop-pm-11', 2.04], ['skill:sop-pm-12', -2.04]]


def test_정기_정비처럼_센서로_진단하지_않은_판단의_결론은_원인을_진단했다고_말하지_않는다():
    """정기 정비 도래 건의 결론이 「원인을 펌프 축 씰 마모로 판단했습니다」 · 근거가 「… 관측값과 맞습니다」였다. 그 원인은 센서 값으로 가린 것이 아니라
    지식 지도에서 「정기 정비로 막는 원인」으로 찾은 것이다(판단 origin.cause_route = prevention). 센서 진단인 판단은 그대로 「원인은 …로 보고」다."""
    made = {'recommended': 'skill:sop-pm-11', 'order': [{'id': 'skill:sop-pm-11', 'rank': 1, 'score': 2.04}]}
    pm = _agent_front(_pm_decision('prevention'), made)
    assert pm['verdict'] == '정기 정비로 막는 원인 ‘펌프 축 씰 마모’를 찾고, 「이번 예정된 정비 시간에 단독 시행」을 추천합니다.', pm
    line = pm['evid'][0]
    assert '관측값과 맞습니다' not in ' '.join(pm['evid']) and '정기 정비로 막는 원인은 펌프 축 씰 마모입니다' in line and '정기 정비로 막는 고장: 주 펌프 체적 효율 저하' in line
    assert '센서 값으로 진단한 것이 아닙니다' in line
    sensed = _agent_front(_pm_decision('diagnosis'), made)
    assert sensed['verdict'].startswith('원인은 펌프 축 씰 마모로 보고, ') and '관측값과 맞습니다' in sensed['evid'][0]
    assert _agent_front(_pm_decision(None), made)['verdict'].startswith('원인은 펌프 축 씰 마모로 보고, ')      # 이 칸이 생기기 전의 판단 기록은 진단으로 읽는다


def test_긴_단계_문장은_괄호_밖의_첫_마디에서_결론과_근거로_갈리고_글은_빠지지_않는다():
    """화면 정돈 6단계: 같은 긴 근거(번호 · 계산 · 기다린 시간)가 결과 카드와 단계마다 되풀이돼 화면을 덮었다. 단계 줄에는 결론 한 마디만 두고 나머지는 접기에 둔다.
    가르는 자리는 괄호 밖이어야 한다 — 「(설비 시간 48시간 (실제 24초))」 안에서 자르면 결론이 괄호 중간에서 끊긴다."""
    long = '기준 밖 — 입고 예정까지 기다린 뒤(설비 시간 48시간 (실제 24초)) 검수했지만 일부만 입고됐습니다 — 불합격 1개 반품. 펌프 축 씰 키트 발주 7개 중 6개 입고 · 1개 검수 불합격 반품 (발주 PR-1, 로트 LOT-PR-1)'
    short = '담당자가 ‘대체 승인 공급사 발주’ 안을 승인했습니다.'
    nocut = '가' * 200
    got = run(FILES, "out(DATA.map(t => UI.leadRest(t, 110)))", [long, short, nocut])
    assert got[0][0] == '기준 밖 — 입고 예정까지 기다린 뒤(설비 시간 48시간 (실제 24초)) 검수했지만 일부만 입고됐습니다'
    assert got[0][1].startswith('불합격 1개 반품. 펌프 축 씰 키트') and got[0][1].endswith('로트 LOT-PR-1)')
    assert len(got[0][0]) + len(got[0][1]) == len(long) - len(' — '), '가르는 표시만 빠지고 글은 그대로다'
    assert got[1] == [short, ''] and got[2] == [nocut, ''], '짧은 문장과 가를 자리가 없는 문장은 통째로 결론이다'


# ---- 2026-11-16 process-gpt-lite 를 본으로 다시 짠 진행 상황(단계 타임라인)과 단계의 옆 판 ----
def _live_view():
    """AI 단계가 도구 하나를 끝내고 다음 도구를 부르는 중인 처리 건(다음 단계는 사람 승인)."""
    t = lambda s: f'2026-11-16T07:00:{s:02d}Z'
    wis = [{'id': 'wa', 'activity_id': 'T_agent', 'activity_name': '원인 진단', 'start_date': t(1), 'status': 'IN_PROGRESS', 'draft_status': 'STARTED',
            'agent_orch': 'cliagents', 'agent_mode': 'COMPLETE', 'consumer': 'worker-1', 'user_id': 'agent:cooling', 'reached_at': t(1)}]
    evs = [{'id': 'e1', 'todo_id': 'wa', 'proc_inst_id': 'c.1', 'event_type': 'task_started', 'job_id': 'run-1', 'timestamp': t(2), 'data': {'goal': '원인 진단'}},
           {'id': 'e2', 'todo_id': 'wa', 'proc_inst_id': 'c.1', 'event_type': 'tool_usage_started', 'job_id': 'run-1', 'timestamp': t(3), 'data': {'tool': 'mcp__dmn__diagnose', 'tool_use_id': 'u1', 'input': {'asset': 'HYD-01'}}},
           {'id': 'e3', 'todo_id': 'wa', 'proc_inst_id': 'c.1', 'event_type': 'tool_usage_finished', 'job_id': 'run-1', 'timestamp': t(4), 'data': {'tool': 'mcp__dmn__diagnose', 'tool_use_id': 'u1', 'output': '{"causes": []}'}},
           {'id': 'e4', 'todo_id': 'wa', 'proc_inst_id': 'c.1', 'event_type': 'tool_usage_started', 'job_id': 'run-1', 'timestamp': t(5), 'data': {'tool': 'mcp__dmn__evaluate', 'tool_use_id': 'u2', 'input': {'asset': 'HYD-01'}}}]
    v = view(wis, ['T_agent'], events=evs)
    v['instance']['status'] = 'RUNNING'; v['instance']['end_date'] = None
    v['workitems'][0].update(status='IN_PROGRESS', agent_orch='cliagents')
    return v


LIVE_JS = """const m = hydRecord.build(DATA, { agents: [], people: [] }, []); const s = m.steps.find(x => x.type === 'agent');
  const p = hydRecord.rowParts(s, m, new Set(), new Set()); const strip = h => h.replace(/<[^>]+>/g, ' ').replace(/\\s+/g, ' ').trim();
  out({ live: s.live, state: p.state, busy: p.busy, row: strip(p.row), body: strip(p.body), folds: (p.body.match(/<details class="line-fold"/g) || []).length,
        names: [UI.toolName('mcp__dmn__diagnose'), UI.toolName('mcp__dmn__evaluate')], tabs: hydRecord.detailGroups(s, [], m).map(g => g.key) })"""


def test_AI가_일하는_동안_그_단계_줄에_지금_부르는_도구가_보이고_줄_아래에_끝낸_일이_한_줄씩_붙는다():
    """DoD 15 — 도는 고리나 「처리 중」 글만 두지 않는다: 일이 끝나기 전에 단계 이름과 부른 도구 이름이 화면에 나온다. 끝낸 호출의 줄은 누르면 원문이 펼쳐지는 접기다."""
    got = run(FILES, LIVE_JS, _live_view())
    done, now = got['names']
    assert got['live'] is True and got['state'] == 'now' and got['busy'] is True, got      # 기계가 실제로 일하는 중 — 맥박
    assert got['row'].startswith('원인 진단') and now in got['row'], got                    # ① 지금 하는 일 한 줄: 단계 이름 + 부르는 도구 이름
    assert done in got['body'] and '마쳤습니다' in got['body'] and now in got['body'], got   # ② 방금 한 일이 한 줄씩
    assert got['folds'] == 1, got                                                          # 끝낸 호출 하나 = 원문을 펴는 접기 하나(하는 중인 호출은 아직 원문이 없다)
    assert 'judge' not in got['tabs'], got                                                 # 아직 내지 않은 결론을 옆 판에 그리지 않는다


def test_사람을_기다리는_단계는_멈춘_내_차례이고_끝난_단계의_줄은_누가와_결론_한_마디다():
    """디자인기준 1-5 · 4-11: 맥박은 기계가 실제로 일할 때만이다 — 사람을 기다리는 단계는 주황 점의 멈춘 「내 차례」다. 끝난 단계의 보조 줄은 「누가 · 결론 한 마디」이고,
    문장이 이미 그 이름으로 시작하면 이름을 앞에 또 적지 않는다(「설비 제어 · 설비 제어에 …」로 읽혔다)."""
    wis = [{'id': 'w1', 'activity_id': 'T_cmd', 'activity_name': '냉각 명령', 'tool': 'incident:command', 'start_date': T, 'end_date': T, 'reached_at': T},
           {'id': 'w2', 'activity_id': 'T_ok', 'activity_name': '운전원 승인', 'tool': 'formHandler:select_card', 'start_date': T, 'status': 'IN_PROGRESS', 'agent_orch': None, 'user_id': 'role:operator', 'reached_at': T}]
    v = view(wis, ['T_cmd', 'T_ok'], variables=[('commands', [{'code': 'FAN', 'param': 'fan_pct', 'value': 100}])])
    v['definition']['activities'][1]['type'] = 'userTask'
    v['instance']['status'] = 'RUNNING'; v['instance']['end_date'] = None
    got = run(FILES, """const m = hydRecord.build(DATA, { agents: [], people: [] }, []); const strip = h => h.replace(/<[^>]+>/g, '|').replace(/\\|+/g, '|');
      const by = id => m.steps.find(x => x.w && x.w.id === id); const mine = new Set(['w2']);
      const a = hydRecord.rowParts(by('w1'), m, mine, new Set()), b = hydRecord.rowParts(by('w2'), m, mine, new Set()), c = hydRecord.rowParts(by('w2'), m, new Set(), new Set());
      out({ cmd: [a.state, a.busy, strip(a.row)], mine: [b.state, b.busy, strip(b.row)], other: [c.state, c.busy], actor: by('w1').actor })""", v)
    assert got['mine'][:2] == ['mine', False] and '|내 차례|' in got['mine'][2], got
    assert got['other'] == ['now', False], got                    # 내 차례인지 모를 때도 사람 단계는 맥박치지 않는다
    assert got['cmd'][0] == 'done' and got['cmd'][2].count(got['actor']) == 1, got      # 누가는 한 번만


def test_끝난_AI_단계의_줄은_결론_한_문장이고_옆_판의_첫_보기가_결론_근거_후보_비교다():
    """DoD 13 — 결론 먼저 · 근거 다음: 단계 줄에는 AI 의 결론 한 문장만 서고, 줄을 누르면 열리는 옆 판의 첫 보기 「판단」에 결론 → 근거 → 후보 비교가 차례로 있다."""
    opt = lambda i, name, score: {'id': f'skill:{i}', 'name': name, 'feasible': True, 'rank': i, 'score': score, 'actions': [], 'kind': 'control', 'approver': {'id': 'role:operator', 'name': '운전원'}}
    d = {'id': 'D-1', 'recommended': 'skill:1', 'options': [opt(1, '팬 최대 운전', 3.4), opt(2, '부하 낮춤', 2.1)], 'origin': {'cause_route': 'diagnosis'}, 'evaluation_mode': 'execution', 'execution_checked': True,
         'explanation': '1순위 팬 최대 운전.', 'scenario': {}}
    guide = {'topCause': 'cause:fin', 'causes': [{'id': 'cause:fin', 'name': '쿨러 핀 오염', 'failureMode': '쿨러 냉각 성능 상실', 'evidence': [{'name': '냉각 효율 저하', 'tag': 'CE', 'expect': 'lt', 'threshold': 70, 'value': 46.2, 'passed': True, 'status': 'PASS'}]}]}
    wis = [{'id': 'wa', 'activity_id': 'T_agent', 'activity_name': '원인 진단', 'start_date': T, 'end_date': T, 'agent_orch': 'cliagents', 'agent_mode': 'COMPLETE', 'user_id': 'agent:cooling', 'reached_at': T}]
    v = view(wis, ['T_agent'], variables=[('decision_id', 'D-1'), ('cause', 'cause:fin'), ('guide_card', guide)])
    got = run(FILES, """const m = hydRecord.build(DATA.v, { agents: [], people: [], decision: DATA.d }, []); const s = m.steps.find(x => x.type === 'agent');
      const strip = h => h.replace(/<[^>]+>/g, ' ').replace(/\\s+/g, ' ').trim(); const g = hydRecord.detailGroups(s, [], m);
      out({ row: strip(hydRecord.rowParts(s, m, new Set(), new Set()).row), tabs: g.map(x => x.key), judge: strip(g[0].html) })""", {'v': v, 'd': d})
    verdict = '원인은 쿨러 핀 오염으로 보고, 「팬 최대 운전」을 추천합니다.'
    assert verdict in got['row'] and '냉각 효율 저하' not in got['row'], got                       # 줄에는 결론만 — 근거는 옆 판
    assert got['tabs'][0] == 'judge' and got['tabs'][-1] == 'raw' and 'io' in got['tabs'], got
    j = got['judge']
    assert j.index('결론') < j.index(verdict) < j.index('근거') < j.index('냉각 효율 저하') < j.index('후보 비교') < j.index('부하 낮춤'), j


def test_정비_요청_결과는_같은_말을_두_번_적지_않고_업무_시스템에_남긴_거래가_있을_때만_그_기록으로_가는_길을_둔다():
    """기록.md 「사용자만 정할 수 있는 것」 — 「정비 요청 WO-… 등록 · 생산팀 공지 — 원문 정비 범위 HYD-02 정비 요청 등록」: 흐름 정의를 바꾸지 않고 화면에서 꼬리의 되풀이만 뺀다.
    DoD 6-3 — 끝난 건의 결과에서 다음 할 일로 가는 링크는 실행이 업무 시스템에 남긴 거래가 있을 때만."""
    def card(report, variables=()):
        v = view([{'id': 'w1', 'activity_id': 'R', 'activity_name': '결과 보고', 'start_date': T, 'end_date': T}], ['R'], variables=[('result_report', report), *variables])
        return run(FILES, "const h = hydResultReport.html(DATA); out([h.replace(/<[^>]+>/g, '|').replace(/\\|+/g, '|'), (h.match(/data-go-tab=\"([^\"]+)\"/) || [])[1] || null])", v)
    summary = '정비 요청 WO-1 등록 · 생산팀 공지 — 원문 정비 범위 HYD-02 정비 요청 등록'
    text, link = card({'outcome': '정비 요청 등록', 'level': 'info', 'title': 'HYD-02 정기 정비 결과', 'summary': summary, 'refs': {'work_order': 'WO-1'}},
                      [('work_order', {'ref': 'WO-1', 'detail': '원문 정비 범위 HYD-02 정비 요청 등록'})])
    assert '|정비 요청 WO-1 등록 · 생산팀 공지 — 원문 정비 범위 HYD-02|' in text and text.count('정비 요청 등록') == 1, text      # 남은 한 번은 상태 알약
    assert link == 'process' and '업무 시스템 기록에서 보기' in text
    text, link = card({'outcome': '반려', 'verdict': 'rejected', 'title': 'HYD-01 냉각 조치 결과', 'summary': '담당자가 반려했습니다'})
    assert link is None and '업무 시스템 기록' not in text, text


def test_승인_전에_닫혀_취소된_단계는_멈춤이_아니라_보통_색의_취소이고_까닭은_한국어로_한_번만_말한다():
    """감독이 본 결함(2026-11-16): 승인 전에 경보가 풀려 「조치 전 해소」로 닫힌 건의 「운전원 승인」이 빨간 ✕ · 빨간 「멈춤」으로 서고, 문장이
    「운전원 · cancelled: 조치 전 해소 — … — cancelled: 조치 전 해소 — …」로 영문 머리와 같은 말이 두 번 읽혔다. 정상 취소를 고장처럼 보이면 화면이 거짓말을 한다.
    옆 판에도 하지 않은 승인의 구획(「고른 안 – 추천안 그대로」)이 섰다. 흐름 그림도 그 상자를 멈춤(빨간 테)으로 칠했다."""
    log = 'cancelled: 조치 전 해소 — 사건 조치 전 자연 회복(경보 해제), 조치 전 종료; '
    wis = [{'id': 'w1', 'activity_id': 'T_ok', 'activity_name': '운전원 승인', 'tool': 'formHandler:select_card', 'status': 'CANCELLED', 'agent_orch': None, 'user_id': 'role:operator',
            'start_date': T, 'end_date': T, 'reached_at': T, 'log': log}]
    v = view(wis, ['T_ok'])
    v['definition']['activities'][0]['type'] = 'userTask'
    got = run(FILES + ['instanceSteps.js', 'flow.js'], """const m = hydRecord.build(DATA, { agents: [], people: [] }, []); const s = m.steps.find(x => x.w); const p = hydRecord.rowParts(s, m, new Set(), new Set());
      const strip = h => h.replace(/<[^>]+>/g, '|').replace(/\\|+/g, '|');
      out({ state: s.state, dot: p.state, busy: p.busy, pill: (p.row.match(/<span class="tag"[^>]*>[^<]*<\\/span>/) || [''])[0], row: strip(p.row),
            sheet: strip(hydRecord.detailGroups(s, [], m).filter(g => g.key !== 'raw').map(g => g.html).join('')), memo: UI.logText(DATA.workitems[0].log),
            mark: hydFlow.marksOf(DATA).st.T_ok, node: hydFlow.pathModel(DATA.definition, DATA.workitems, DATA.instance).nodes.map(n => n.state) })""", v)
    assert got['state'] == 'cancel' and got['dot'] == 'todo' and got['busy'] is False, got            # 실패(fail)의 빨간 점이 아니다
    assert got['pill'] == '<span class="tag">취소</span>', got['pill']                                 # 색 없는 보통 알약
    why = '조치 전 해소 — 사건 조치 전 자연 회복(경보 해제), 조치 전 종료'
    for text in (got['row'], got['sheet'], got['memo']):
        assert 'cancelled' not in text.lower() and text.count(why) <= 1, text
    assert got['row'].count(why) == 1 and '닫혔습니다' in got['row'] and '멈춤' not in got['row'], got['row']
    assert '추천안 그대로' not in got['sheet'] and '고른 안' not in got['sheet'], got['sheet']          # 하지 않은 승인을 한 것처럼 적지 않는다
    assert got['mark'] == 'cancel' and got['node'] == ['cancel'], got                                  # 흐름 그림도 멈춤으로 칠하지 않는다


def test_일이_끝난_단계의_결과를_처리_흐름이_받는_사이에는_결과가_없다고_하지_않고_받는_중이라고_말한다():
    """실행 중인 처리 건에서 단계의 끝 이벤트는 실시간 연결로 먼저 오고 그 단계의 결과 값은 다음 읽기에 온다. 그 사이(1초 안팎) 단계 줄이
    「결과 기록이 없습니다 — 단계 상태: 제출됨」 · 「정비 요청 등록 결과가 없습니다」로 바뀌었다 사라져, 결과가 빠진 것처럼 읽혔다(2026-11-16 실측). 멈춘 단계는 그대로 「결과 기록이 없습니다」다."""
    done = lambda wid: {'id': 'e-' + wid, 'todo_id': wid, 'event_type': 'task_completed', 'timestamp': T, 'job_id': 'j', 'data': {}}
    wis = [{'id': 'w1', 'activity_id': 'T_wo', 'activity_name': '정비 요청 등록', 'tool': 'ent:WO_CREATE', 'status': 'SUBMITTED', 'agent_orch': 'hyd-process', 'start_date': T, 'end_date': None},
           {'id': 'w2', 'activity_id': 'R_ok', 'activity_name': '결과 보고', 'tool': 'report', 'status': 'SUBMITTED', 'agent_orch': 'hyd-process', 'start_date': T, 'end_date': None}]
    v = view(wis, ['T_wo', 'R_ok'], events=[done('w1'), done('w2')])
    v['instance'].update(status='RUNNING', end_date=None)
    got = run(FILES, "out(hydRecord.build(DATA, { agents: [], people: [] }, []).steps.filter(s => s.key !== 'start' && s.sentence).map(s => s.sentence))", v)
    assert len(got) == 2 and all(s == '이 단계의 일은 끝났습니다 — 처리 흐름이 결과를 받아 다음 단계로 넘기는 중입니다.' for s in got), got
    # 실행이 실패로 끝나 멈춘 단계(끝 이벤트는 있지만 실패)는 받는 중이 아니다
    v['workitems'][1]['draft_status'] = 'FAILED'
    got = run(FILES, "out(hydRecord.build(DATA, { agents: [], people: [] }, []).steps.filter(s => s.key !== 'start' && s.sentence).map(s => s.sentence))", v)
    assert '결과 기록이 없습니다' in got[1] and '실행 실패' in got[1], got
