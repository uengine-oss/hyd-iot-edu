"""포털 공용 화면 도우미(it/portal/www/ui.js) — 처리 건 행의 차례 · 승인 전달 상태 이름 · 사람 이름 · 문장 속 원래 id · 시각 형식.
node 에서 실제 ui.js 를 실어 부른다(www_node). 화면 순회(test_portal_ui)와 달리 떠 있는 스택이 필요 없다."""
import json

import pytest

from www_node import WWW, run

FILES = ['ui.js', 'plainWords.js']
T = '2026-10-30T05:44:45.305Z'


@pytest.mark.parametrize('rows, timeline, expected', [
    # 한 트랜잭션에서 연달아 끝나 시작 · 끝 시각이 같다 → 흐름 순서(view.flow_order)대로(W1-01: 결과 보고가 정비 오더보다 먼저 보였다)
    ([('R_ok', T, T), ('T_wo', T, T)], ['T_wo', 'R_ok'], ['T_wo', 'R_ok']),
    # 시각이 다르면 흐름 순서보다 시각이 먼저
    ([('R_ok', '2026-10-30T05:44:40Z', T), ('T_wo', T, T)], ['T_wo', 'R_ok'], ['R_ok', 'T_wo']),
    # 시작이 같고 끝이 다르면 끝 시각
    ([('B', T, '2026-10-30T05:45:00Z'), ('A', T, '2026-10-30T05:44:50Z')], ['B', 'A'], ['A', 'B']),
    # 시작 시각이 없는 행(아직 안 한 단계)은 뒤로, 흐름 표에 없는 행(타이머)은 같은 순간이면 뒤로
    ([('X', None, None), ('timer', T, T), ('A', T, T)], ['A'], ['A', 'timer', 'X']),
])
def test_처리_건_작업_행은_시각_순서이고_같은_순간이면_흐름_순서다(rows, timeline, expected):
    items = [{'activity_id': a, 'start_date': s, 'end_date': e} for a, s, e in rows]
    got = run(FILES, "out(DATA.items.sort(UI.workitemOrder({ flow_order: Object.fromEntries(DATA.timeline.map((a, i) => [a, i])) })).map(w => w.activity_id))",
              {'items': items, 'timeline': timeline})
    assert got == expected


@pytest.mark.parametrize('status, label', [
    ('PENDING', '전달 대기'), ('DELIVERED', '전달 완료'), ('FAILED', '전달 실패'), ('DISCARDED', '승인 폐기'),
    ('UNKNOWN_X', 'UNKNOWN_X'),        # 모르는 상태는 지어내지 않고 원래 값
])
def test_승인_전달_상태는_단계_보류와_다른_이름이다(status, label):
    """W1-04: 승인 전달 PENDING 이 단계 상태표의 「보류」로 보여 승인이 보류된 줄 알았다."""
    got = run(FILES, "out(UI.deliveryChip(DATA).replace(/<[^>]+>/g, ''))", status)
    assert got == label


@pytest.mark.parametrize('people, who, expected', [
    ({'user:kim-op': '김운전'}, 'user:kim-op', '김운전'),
    ({}, 'user:kim-op', '담당자 (이름 확인 안 됨)'),        # 사람 목록을 못 읽었을 때 원래 id 를 보이지 않는다(W1-13)
    ({}, 'agent:u-030be032', 'AI 에이전트'),
    ({}, 'role:operator', '운전원'),
    ({}, '', '–'),
    ({}, None, '–'),
    ({}, 'sys:cmms', '정비 관리'),                       # 시스템 이름은 이름 사전 names.json 한 곳(W2-03 · 넘김 FW → FT — 화면이 실은 사전에서)
    ({}, 'detector', '센서 경보 감지기'),
    ({}, 'org:unknown-thing', 'org:unknown-thing'),       # 사람 · AI · 시스템이 아닌 모르는 id 는 그대로(지어내지 않음)
])
def test_사람_이름은_사람_목록에서_없으면_원래_id_대신_확인_안_됨(people, who, expected):
    got = run(FILES, "UI.names = DATA.names; Object.assign(UI.performers, DATA.people); out(UI.who(DATA.who))",
              {'people': people, 'who': who, 'names': json.loads((WWW / 'names.json').read_text(encoding='utf-8'))})   # 화면이 시작에 싣는 사전(UI.loadNames)
    assert got == expected


@pytest.mark.parametrize('text, expected', [
    ('조치 action:set-fan 을 고름', '조치 팬 속도 설정 을 고름'),     # 접두어 목록에 없던 action: · in: · sen: · dept: 도 이름으로(W2-02)
    ('입력 in:ce 가 70 미만', '입력 냉각 효율 가 70 미만'),
    ('부서 dept:sales', '부서 영업팀'),
    ('적재 ks:manual:abc%3A1:x 확인', '적재 HM-8 확인'),
    ('모르는 zz:abc 그대로', '모르는 zz:abc 그대로'),             # 사전에 없는 id 는 그대로
    ('시각 14:43:18 · https://x.y/a:b', '시각 14:43:18 · https://x.y/a:b'),   # 시각 · 주소는 id 가 아니다
])
def test_문장_속_원래_id는_사전에_있으면_이름으로_바뀐다(text, expected):
    names = {'action:set-fan': '팬 속도 설정', 'in:ce': '냉각 효율', 'dept:sales': '영업팀', 'ks:manual:abc%3A1:x': 'HM-8'}
    assert run(FILES, "UI.names = DATA.names; out(UI.idText(DATA.text))", {'names': names, 'text': text}) == expected


@pytest.mark.parametrize('value, expected', [('2026-10-30T05:43:18.120Z', 'HH:MM:SS'), ('nope', 'nope'), (None, '–')])
def test_시각은_시분초_한_형식이다(value, expected):
    """W1-14: 처리 기록 14:43:18 · 결과 보고 14시 43분 42초 — 한 화면 안에 두 형식이었다."""
    got = run(FILES, "out(UI.time(DATA))", value)
    if expected == 'HH:MM:SS':
        assert len(got) == 8 and got[2] == ':' and got[5] == ':' and got.replace(':', '').isdigit(), got
    else:
        assert got == expected


@pytest.mark.parametrize('code, name', [('COOLER_DEGRADATION', '쿨러 성능 저하'), ('PM_DUE', '정기 정비 도래'),
                                        ('TEMP_TRIP', 'TEMP_TRIP'), ('MY_PBL_ALERT', 'MY_PBL_ALERT')])
def test_경보_패턴_이름은_그래프_목록에서_읽고_화면_사본이_없다(code, name):
    """G3b-8: 경보 패턴 이름 사전이 화면에 사본으로 있었고 어디서도 안 나오는 TEMP_TRIP 까지 들었다 — 이제 agent /api/ontology/patterns(그래프 AnomalyPattern.name)에서."""
    graph = [{'code': 'COOLER_DEGRADATION', 'name': '쿨러 성능 저하'}, {'code': 'PM_DUE', 'name': '정기 정비 도래'}]
    got = run(FILES, "globalThis.API = { agent: '' }; globalThis.getJ = async () => DATA; globalThis.requireList = v => v; "
                     "const before = UI.patternName('COOLER_DEGRADATION'); await UI.loadPatterns(); out([before, UI.patternName(DATA2)])".replace('DATA2', repr(code)), graph)
    assert got == ['COOLER_DEGRADATION', name]


@pytest.mark.parametrize('me, html_has, html_not', [
    ({'id': 'user:kim-op', 'name': '김운전', 'roles': []}, ['value="user:kim-op"', '김운전'], ['<input data-x value']),
    (None, ['value=""', '나를 고르세요'], ['<input data-x value']),      # 「나」가 없으면 자유 글 칸이 아니라 안내(서버는 등록된 「나」만 받는다, W1-08)
])
def test_담당자_칸은_나만_받고_자유_글_칸을_그리지_않는다(me, html_has, html_not):
    got = run(FILES, "window.hydInbox = { me: () => DATA }; out(UI.actorInput('data-x', 'OP-17'))", me)
    assert all(h in got for h in html_has) and not any(n in got for n in html_not), got


@pytest.mark.parametrize('skill, expected', [
    ({'skill': 'cooling-emergency-response'}, 'cooling-emergency-response'),            # 한국어 이름 · 설명이 없는 기록: 등록 이름 그대로
    ({'name': 'pm-plan', 'description': '정기 정비 계획 스킬'}, '정기 정비 계획 스킬'),  # 한국어 설명이 있으면 그것
])
def test_스킬_이름은_한국어_이름이_없으면_등록된_이름을_그대로_보인다(skill, expected):
    """06 촬영 검토(2026-11-03): 처리 과정에 「스킬의 한국어 표시 이름 기록 없음」이 학생 화면에 보였다."""
    assert run(FILES, "out(UI.skillLabel(DATA).label)", skill) == expected
