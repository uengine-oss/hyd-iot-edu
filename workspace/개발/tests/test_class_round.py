"""수업 한 바퀴(workspace/개발/scripts/class_round.py)의 판정 함수 — 거짓 통과 · 거짓 실패가 없는가.

스택 없이 판정 함수만 부른다. 실라버스 대조는 정본 엑셀(읽기 전용)을 실제로 열고, 화면 누르기 도움 함수는 실제 index.html 을 실제 브라우저로 연다.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import class_round as cr  # noqa: E402


@pytest.mark.parametrize('text, ok', [
    ('정구매 님의 역할(구매 담당)로는 이 안을 승인할 수 없습니다', True),
    ('선택한 수업 조회 서버가 연결되지 않았습니다', True),
    ('경고와 NaN/Inf를 보존합니다', True),                     # 문장 속 기술어는 그린 값 실패가 아니다
    ('', False), ('가가가', False),
    ('Error 500 내부 오류', False), ('ValueError 발생', False), ('요청이 거절됨 (403)', False),
    ('detail: 권한 없음 role:operator', False), ('권한 없음 role:operator 입니다', False),
    ('서버가 쓰기 도구(readOnlyHint=false)로 표시했습니다', False), ('값 NaN 개를 읽었습니다', False),
    ({'reason': '거절'}, False), (None, False),
    ("쿨러 냉각 성능 상실 — 후보 4장 중 'SOP-COOL-11 팬 최대 운전'을 권한다", True),   # 매뉴얼 절차 번호는 원문 번호(한바퀴3)
    ('에너지 사용량 1,200 kWh · 목표 미달', True),
    ('절차 SOP-COOL-11 · 조치 COOL_SET 입니다', False), ('판정 COOLER_DEGRADATION 입니다', False),
])
def test_학생_문장_판정은_한글_문장만_통과시키고_영문_예외_상태_코드_원문_id_글이_아닌_값은_막는다(text, ok):
    assert cr.human_text(text)[0] is ok


def test_학생_문장이_아닌_값이_와도_판정이_죽지_않고_까닭을_남긴다():
    ok, why = cr.human_text({'reason': 'BPMN 2.0 파일이 아닙니다', 'problems': []})
    assert not ok and '글이 아님(dict)' in why


@pytest.mark.parametrize('session, source', [
    ('af97187a-b72d-4db8-bf12-54cbce8bd1e2', '실제 AI'), ('reuse:dd0c94ff34a5bf45:0', '같은 요청 다시 냄'),
    ('replay:7a5adc7beac53689:1', '강사 녹화 재생'), (None, '기록 없음'), ('', '기록 없음'),
])
def test_작업_세션_이름으로_실제_AI_다시_냄_녹화_재생을_가른다(session, source):
    assert cr.ai_source(session) == source


def run(ai, value, error=None):
    return {'ai': ai, 'kind': value, **({'error': error} if error else {})}


@pytest.mark.parametrize('runs, verdict', [
    ([run('실제 AI', 'a'), run('실제 AI', 'a'), run('실제 AI', 'a')], True),
    ([run('실제 AI', 'a'), run('실제 AI', 'b'), run('실제 AI', 'a')], False),
    ([run('실제 AI', 'a'), run('같은 요청 다시 냄', 'a'), run('같은 요청 다시 냄', 'a')], None),
    ([run('강사 녹화 재생', 'a')] * 3, None),
    ([run('실제 AI', 'a'), run('실제 AI', 'a', error='멈춤'), run('같은 요청 다시 냄', 'a')], None),
], ids=['실제_셋_같음', '실제_셋_다름', '실제_하나_다시냄_둘', '녹화_재생_셋', '실패한_실행은_세지_않음'])
def test_3번_같은지는_실제_AI_실행끼리만_재고_다시_낸_실행은_측정_안_함(runs, verdict):
    (name, ok, note), = cr.ai3_identity(runs, ('kind',))
    assert ok is verdict
    if verdict is None:
        assert '측정' not in name and '실제 AI 실행이' in note


ROLES = {'운전원', '설비보전팀장', '구매 담당', '생산관리자'}


@pytest.mark.parametrize('answer, expected, ok', [
    ('절차는 SOP-COOL-11, SOP-COOL-12입니다. 두 절차의 승인 역할은 모두 운전원입니다.', {'SOP-COOL-11': '운전원', 'SOP-COOL-12': '운전원'}, True),
    ('SOP-COOL-11은 운전원, SOP-COOL-14는 설비보전팀장이 승인합니다.', {'SOP-COOL-11': '운전원', 'SOP-COOL-14': '설비보전팀장'}, True),
    ('SOP-COOL-11은 설비보전팀장, SOP-COOL-14는 운전원이 승인합니다.', {'SOP-COOL-11': '운전원', 'SOP-COOL-14': '설비보전팀장'}, False),
    ('승인 역할은 모두 운전원이고 생산관리자도 함께 봅니다.', {'SOP-COOL-11': '운전원'}, False),
    ('승인 역할은 알 수 없습니다.', {'SOP-COOL-11': '운전원'}, False),
    ('아무 말', {}, False),
])
def test_질문_답의_승인_역할은_원문_승인_줄과_같아야_통과(answer, expected, ok):
    assert cr.roles_in_answer(answer, expected, ROLES)[0] is ok


def option(oid, sop, rank, feasible, approver, rules=()):
    return {'id': oid, 'sopId': sop, 'rank': rank, 'feasible': feasible, 'approver': {'name': approver}, 'violations': [{'rule': r} for r in rules]}


SOURCE = {'SOP-COOL-11': '운전원', 'SOP-COOL-14': '설비보전팀장'}


@pytest.mark.parametrize('dec, problems', [
    ({'recommended': 'a', 'options': [option('a', 'SOP-COOL-11', 1, True, '운전원'), option('b', 'SOP-COOL-14', 2, False, '설비보전팀장', ['rule:x'])]}, []),
    ({'recommended': 'b', 'options': [option('a', 'SOP-COOL-11', 1, True, '운전원'), option('b', 'SOP-COOL-14', 2, True, '설비보전팀장')]}, ['추천']),
    ({'recommended': 'a', 'options': [option('a', 'SOP-COOL-11', 1, True, '운전원'), option('b', 'SOP-COOL-14', 2, False, '설비보전팀장')]}, ['규칙이 없음']),
    ({'recommended': 'a', 'options': [option('a', 'SOP-COOL-11', 1, True, '설비보전팀장')]}, ['원문 운전원']),
    ({'recommended': 'a', 'options': [option('a', 'SOP-FAN-11', 1, True, '운전원')]}, ['「승인:」 줄이 없음']),
    ({'recommended': None, 'options': []}, ['카드가 없음']),
], ids=['맞음', '추천이_1순위_아님', '제외인데_규칙_없음', '승인_역할이_원문과_다름', '원문에_승인_없음', '카드_없음'])
def test_판단_카드는_실행_가능한_1순위_추천_제외_규칙_원문_승인_역할로_판정한다(dec, problems):
    got = cr.card_findings(dec, SOURCE)
    assert len(got) == len(problems) and all(p in g for p, g in zip(problems, got))


QUOTE = '불량 1건 손실(재교체)은 250만 원으로 본다. 불량률이 10 %를 넘는 승인 공급사는 전수 검사 비용 20만 원을 더해 비교한다.'


def purchase(sup='sup:b', qty=6, total=360.0, buy=330.0, fail=30.0, insp=0.0, avl=True, quote=QUOTE):
    policy = {'anchor': {'quote': quote}, 'loss_per_failure': 250, 'inspection_cost': 20, 'inspection_threshold': 0.1}
    eco = {'supplier': sup, 'quantity': qty, 'unit_price': 55, 'fail_rate': 0.02, 'purchase_amount': buy, 'expected_failure_cost': fail,
           'inspection_cost': insp, 'total_cost': total, 'policy': policy}
    return {'recommended': 'x', 'options': [{'id': 'x', 'economicComparison': eco}],
            'facts': {'spare_quotes': {'sup:b': {'avl': avl, 'price': 55, 'fail_rate': 0.02}}}}


@pytest.mark.parametrize('dec, need, problem', [
    (purchase(), 6, None),
    (purchase(total=330.0), 6, '총비용'),
    (purchase(buy=300.0, total=330.0), 6, '구매 금액'),
    (purchase(avl=False), 6, 'AVL'),
    (purchase(qty=4, buy=220.0, fail=20.0, total=240.0), 6, '부족 수량'),
    (purchase(quote='원문 인용이 없다'), 6, '원문 인용에 없음'),
    (purchase(sup='sup:z'), 6, '견적이 판단 사실에 없음'),
], ids=['맞음', '총비용이_원문_식과_다름', '구매_금액이_단가x수량과_다름', 'AVL_아님', '수량이_부족분보다_적음', '정책_값이_원문에_없음', '견적_없는_공급사'])
def test_구매_카드는_AVL_부족_수량_원문_PR07_총비용_식으로_판정한다(dec, need, problem):
    got = cr.purchase_findings(dec, {'need_qty': need})
    assert (not got) if problem is None else any(problem in g for g in got)


def checks(notes='conflict', parts='needs_check', orders_finding='WO-1 과 WO-2 가 배정됨'):
    return [{'area': 'equipment', 'state': 'observed', 'finding': '센서 값'}, {'area': 'work_orders', 'state': 'observed', 'finding': orders_finding},
            {'area': 'parts', 'state': parts, 'finding': '부품'}, {'area': 'work_notes', 'state': notes, 'finding': '메모'}]


@pytest.mark.parametrize('cs, problem', [
    (checks(), None),
    (checks(notes='observed'), '정비 완료'),
    (checks(parts='observed'), '도착 예정'),
    (checks(orders_finding='WO-1 만 배정됨'), '빠뜨림'),
    (checks(orders_finding='WO-1 · WO-2 · WO-9 가 배정됨'), '없는 작업지시'),
    (checks()[:3], '확인 영역'),
], ids=['맞음', '정비_완료_메모를_사실로', '도착_예정을_사실로', '열린_작업지시_누락', '없는_번호_지어냄', '영역_빠짐'])
def test_교대_인계안은_업무_DB의_열린_작업지시와_도착_예정으로_판정한다(cs, problem):
    got = cr.handover_findings(cs, ['WO-1', 'WO-2'], claims_done=True, claims_arrival=True, arriving=False)
    assert (not got) if problem is None else any(problem in g for g in got)


def test_원문_절차는_자기_승인_줄을_먼저_보고_없으면_절_머리의_승인_문장을_쓴다():
    text = ('## 1 완화\n### SOP-A 첫 절차\n1. 하나\n2. 둘\n\n승인: 운전원. 끝.\n'
            '## 2 근본 조치\n승인은 설비보전팀장이 한다.\n### SOP-B 세척\n1. 씻는다\n### SOP-C 교체\n1. 바꾼다\n승인: 구매 담당\n## 3 다른 절\n### SOP-D 기록\n1. 적는다\n')
    got = cr.source_procedures(text)
    assert {k: v['approver'] for k, v in got.items()} == {'SOP-A': '운전원', 'SOP-B': '설비보전팀장', 'SOP-C': '구매 담당', 'SOP-D': None}
    assert got['SOP-A']['steps'] == ['하나', '둘']


def test_사람_승인_단계의_지연_타이머는_20배속에서도_벽시계로_기다린다():
    definition = {'activities': [{'id': 'T', 'type': 'userTask'}], 'events': [{'id': 'B', 'timer': 'PT10M', 'attachedTo': 'T'}]}
    assert cr.timer_wait_s(definition, 'B', 20.0) == 600.0


@pytest.mark.parametrize('host', [
    {'id': 'T', 'type': 'userTask', 'agentMode': 'COMPLETE'}, {'id': 'T', 'type': 'serviceTask', 'tool': 'incident:reobserve'},
    {'id': 'T', 'type': 'serviceTask', 'tool': 'process:wait'}, {'id': 'T', 'type': 'serviceTask', 'tool': 'incident:command'},
], ids=['에이전트_단계', '재관측', '시간_대기', '명령'])
def test_경계_타이머의_실제_초는_도구가_따로_적지_않고_엔진_규칙을_따른다(host):
    definition = {'activities': [host], 'events': [{'id': 'B', 'timer': 'PT10M', 'attachedTo': 'T'}]}
    assert cr.timer_wait_s(definition, 'B', 20.0) == 600.0 / cr.process_engine.timer_scale(host, 20.0)


@pytest.mark.parametrize('only, start, chosen', [
    ('', '', ['01', '02', '05', '90']), ('02,90', '', ['02', '90']), ('', '05', ['05', '90']), ('90', '05', ['90']),
])
def test_고른_실습_번호대로_돈다(only, start, chosen):
    assert cr.select_labs(['01', '02', '05', '90'], only, start) == chosen


@pytest.mark.parametrize('only, start', [('5', ''), ('', '5'), ('01,99', '')], ids=['한_자리', '시작_번호', '하나는_없음'])
def test_없는_실습_번호를_고르면_판정_0개로_성공하지_않고_멈춘다(only, start):
    with pytest.raises(ValueError, match='없는 실습 번호'):
        cr.select_labs(['01', '02', '05', '90'], only, start)


@pytest.mark.parametrize('sentence, n', [('왼쪽의 일곱 메뉴 묶음을 차례로 연다', 7), ('세 개의 메뉴', None), ('', None)])
def test_실라버스_문장의_메뉴_묶음_수를_읽는다(sentence, n):
    assert cr.menu_group_count(sentence) == n


def test_실라버스의_포털_실습_행이_이_도구의_실습과_빠짐없이_맞는다():
    syllabus = cr.load_syllabus()
    assert cr.uncovered_rows(syllabus, cr.LAB_ROWS) == []
    missing = [(code, course, title) for code, rows in cr.LAB_ROWS.items() for course, title in rows if cr.find_row(syllabus, course, title) is None]
    assert missing == []


def test_새_포털_실습_행이_생기면_빠진_행으로_드러난다():
    syllabus = {'통합': [(9, '실습(포털)', '있는 행', ''), (10, '실습(포털)', '새 행', ''), (11, '이론', '이론 행', '')]}
    assert cr.uncovered_rows(syllabus, {'01': [('통합', '있는 행')]}) == ['통합 10행 「새 행」']


def test_추출_제안을_원문과_대조해_누락_오추출_단계수_부정조건_수치를_잡는다():
    src = {'SOP-A': {'steps': ['팬을 100 %로 올린다. 24시간 넘으면 안 된다.', '확인한다.'], 'approver': None}}
    preview = {'procedures': [{'id': 'SOP-A', 'steps': [{'order': 1, 'text': '팬을 올린다.'}]}, {'id': 'SOP-Z', 'steps': []}]}
    kinds = [f['kind'] for f in cr.extraction_quality(src, preview)]
    assert any('단계 수 1 ≠ 원문 2' in k for k in kinds) and any('오추출' in k for k in kinds)
    assert any("'넘으면' 빠짐" in k for k in kinds) and any('수치 100 빠짐' in k for k in kinds) and any('단위 % 빠짐' in k for k in kinds)
    assert cr.extraction_quality(src, {'procedures': [{'id': 'SOP-A', 'steps': [{'order': 1, 'text': src['SOP-A']['steps'][0]},
                                                                                {'order': 2, 'text': '확인한다.'}]}]}) == []


def test_기다림은_일시_오류만_다시_시도하고_칸_이름_변경은_바로_실패로_낸다():
    assert cr.transient(cr.HttpStatus('u', 503, ''))
    assert not cr.transient(cr.HttpStatus('u', 404, ''))
    assert cr.transient(ConnectionResetError())
    assert not cr.transient(KeyError('status'))
    assert not cr.transient(TypeError('x'))


def test_시작_지식은_실행_절차와_고장_유형만_세고_참고_보관_절차와_보충_자료는_뺀다():
    got = cr.start_knowledge()
    assert {'SOP-COOL-11', 'SOP-COOL-14', 'SOP-PM-21', 'SOP-PUR-11'} <= got['sop']
    assert not got['sop'] & {'SOP-PM-2-9', 'SOP-PR7-7', 'SOP-HI-01'}
    assert got['fm'] == {'fm:cooler-cooling-loss', 'fm:pump-volumetric-efficiency-loss'}


class _Page:                                                              # 바깥(브라우저)만 대체 — 판정 기록은 실제 Round
    def on(self, *_):
        pass

    def screenshot(self, path, full_page=False):
        Path(path).write_bytes(b'')


def test_원문_자리는_파일로_남고_통과로_세지_않는다(tmp_path):
    r = cr.Round(_Page(), tmp_path, {})
    r.lab, r.tags['03'] = '03', '통합 21행'
    r.lab = '03'
    r.evidence('노드 설명의 원문 id', '원문 글 asset:hyd-01', '정본 기준이 없음', axis=cr.AXES[1])
    r.check('지도 숫자 = API', True)
    r.write()
    summary = (tmp_path / 'summary.md').read_text(encoding='utf-8')
    row = next(line for line in summary.splitlines() if line.startswith('| 03 '))
    assert row.split('|')[3].strip() == '됨' and row.split('|')[4].strip() == '확인 못 함(1)'
    saved = list((tmp_path / '원문').glob('*.txt'))
    assert len(saved) == 1 and saved[0].read_text(encoding='utf-8') == '원문 글 asset:hyd-01'
    assert '원문 자리' in summary


@pytest.mark.parametrize('w, events, want', [
    ({'id': 't1', 'status': 'IN_PROGRESS', 'draft_status': 'FAILED'},
     [{'todo_id': 't1', 'event_type': 'error', 'data': {'friendly': '수업 단계에서는 이 AI 단계를 실행하지 않습니다'}}], '수업 단계에서는 이 AI 단계를 실행하지 않습니다'),
    ({'id': 't1', 'status': 'IN_PROGRESS', 'draft_status': 'FAILED'}, [], '(처리 기록에 문장 없음 — draft_status FAILED)'),
    ({'id': 't1', 'status': 'IN_PROGRESS', 'draft_status': 'STARTED'}, [], None),
    ({'id': 't1', 'status': 'CANCELLED', 'draft_status': None}, [], None),      # 사람이 닫은 단계는 AI 멈춤이 아니다
])
def test_AI_단계_멈춤은_작업_상태가_아니라_초안_상태와_오류_이벤트의_학생_문장으로_읽는다(w, events, want):
    assert cr.step_failure({'events': events}, w) == want


def test_질문_끝_상태는_서버의_질문_상태_함수가_내는_값과_맞는다():
    from procsvc import ask
    from procsvc.instances import InstanceRuntime
    base = {'status': 'RUNNING'}
    cases = [(base, None), (base, {'status': 'CANCELLED'}), ({'status': 'COMPLETED'}, {'status': 'DONE'}),
             (base, {'status': 'PENDING'}), (base, {'status': 'IN_PROGRESS', 'draft_status': 'FAILED'}),
             (base, {'status': 'IN_PROGRESS', 'draft_status': 'HUMAN_ASKED'}),
             (base, {'status': 'IN_PROGRESS', 'draft_status': 'FB_REQUESTED', 'feedback': {'kind': 'validation', 'history': ['x']}}),
             (base, {'status': 'SUBMITTED'}), (base, {'status': 'IN_PROGRESS', 'draft_status': 'STARTED'}), (base, {'status': 'IN_PROGRESS'}),
             ({'status': 'RUNNING', 'end_event': InstanceRuntime.HUMAN_CLOSE_END_EVENT}, {'status': 'IN_PROGRESS'})]
    states = {ask._state(inst, wi, [])[0] for inst, wi in cases}
    waiting = {'asking', 'correcting', 'submitted', 'running', 'waiting'}
    assert not cr.ASK_END & waiting, '진행 중 상태를 끝으로 읽으면 답이 오기 전에 판정한다'
    assert states == cr.ASK_END | waiting, '질문 상태가 늘거나 줄었다 — class_round.ASK_END(끝 상태)를 서버와 맞춘다'


def test_시스템_실행_이력_접기를_펼_때_안의_거래_접기가_여럿이어도_접기_자신만_편다():
    """한바퀴3 고침 2: 15 · 16 두 번째 실행부터 「#txFold summary」가 거래마다 붙은 접기(원문 · 변경 전후)의 summary 까지 3 · 7개를 골라
    strict mode violation 으로 멈췄다(화면은 정상 — 확인 도구 선택자 결함). 실제 index.html · enterprise.js 가 거래 둘을 그리게 한다 — 브라우저
    밖의 업무 시스템 응답만 이 시험이 준다(상태 · 거래 기록 꼴은 enterprise-sim /api/state · /api/transactions)."""
    from playwright.sync_api import sync_playwright
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles
    from conftest import WWW, Served
    app = FastAPI()
    app.mount('/', StaticFiles(directory=WWW, html=True))
    served = Served(app)
    state = {'mes': {'orders': []}, 'cmms': {'work_orders': []}, 'erp': {'purchase_requests': [], 'goods_receipts': []}}
    tx = [{'t': '2026-10-31T08:00:00Z', 'system': 'sys:cmms', 'by': 'sys:process', 'detail': f'WO-{i}', 'before': None,
           'after': {'id': f'WO-{i}', 'status': 'OPEN'}} for i in (1, 2)]
    body = {'/api/state': state, '/api/transactions': tx, '/api/decisions': []}
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page()
            page.route('**/svc/**', lambda route: route.fulfill(json=next((v for k, v in body.items() if route.request.url.split('?')[0].endswith(k)), {})))
            page.goto(served.url + '/index.html')
            page.locator("button[data-tab='process']").first.click()        # 승인과 실행 화면(확인 도구와 같은 메뉴)
            page.wait_for_function("document.querySelectorAll('#txList article.event-record').length === 2", timeout=15000)
            fold = page.locator('#txFold')
            assert fold.locator('summary').count() > 1, '접기 안의 거래에도 summary 가 있다(옛 선택자가 여럿을 고르는 조건)'
            cr.open_fold(fold)
            assert fold.evaluate('d => d.open') and page.locator('#txList details[open]').count() == 0
            b.close()
    finally:
        served.close()
