"""판단 실험의 조건 판(it/portal/www/whatif.js · enterprise.js 규칙 판단) — 설비 목록을 화면이 지어내지 않고 서버에서 읽는다.

실제 index.html 을 실제 브라우저(Playwright Chromium)로 연다. 브라우저 밖의 서비스 응답(설비 상태 · 이상 패턴 · 판단)만 이 시험이 준다.
설비 상태 응답의 꼴은 plant-sim /api/state(units: {설비: {tags, status}}), 판단 응답의 꼴은 agent /api/agent/decide 다."""
import json

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from conftest import WWW, Served, open_screen

UNIT = {'tags': {'TS1': 48.0, 'CE': 84.0}, 'status': {'state': 'RUN', 'mode': 'REMOTE_AUTO'}}
PLANT = {'units': {'PRESS-07': UNIT, 'PRESS-08': UNIT}, 't': '2026-11-14T00:00:00Z'}      # 수업 설비 이름(HYD-0N)이 아닌 이름 — 화면에 박힌 목록이 있으면 드러난다
PATTERNS = [{'id': 'pattern:x', 'code': 'SEAL_WEAR', 'name': '씰 마모', 'failureModes': []}]


def _page(answers, sent):
    """index.html 을 띄우고, /svc/ 요청은 answers(주소 끝 → 응답 또는 (상태, 응답))로 답한다. POST 본문은 sent 에 남는다."""
    from playwright.sync_api import sync_playwright
    app = FastAPI()
    app.mount('/', StaticFiles(directory=WWW, html=True))
    served = Served(app)

    def answer(route):
        url = route.request.url.split('?')[0]
        if route.request.method == 'POST':
            sent.append((url, json.loads(route.request.post_data or '{}')))
        hit = next((body for tail, body in answers.items() if url.endswith(tail)), {})
        if callable(hit):
            hit = hit(json.loads(route.request.post_data or '{}'))
        status, body = hit if isinstance(hit, tuple) else (200, hit)
        return route.fulfill(status=status, json=body)
    pw = sync_playwright().start()
    browser = pw.chromium.launch()
    page = browser.new_page()
    page.route('**/svc/**', answer)
    page.goto(served.url + '/index.html')

    def close():
        browser.close()
        pw.stop()
        served.close()
    return page, close


def test_조건별_손익은_설비_목록을_서버의_설비_상태에서_읽고_고른_설비로_계산을_청한다():
    """해피패스 조사 9번: 화면 코드에 ['HYD-01','HYD-02','HYD-03']가 박혀 있어, 설비가 달라도 그 셋만 고를 수 있었다."""
    sent = []
    page, close = _page({'/plant-sim/api/state': PLANT, '/api/ontology/patterns': PATTERNS,
                         '/api/agent/whatif': (422, {'detail': '이 설비에는 씰 마모의 원인 지식이 없습니다'})}, sent)
    try:
        open_screen(page, 'whatif')
        page.wait_for_function("document.querySelectorAll('#wiAsset option').length > 0", timeout=8000)
        assert page.eval_on_selector_all('#wiAsset option', 'xs => xs.map(x => x.textContent)') == ['PRESS-07', 'PRESS-08']
        page.select_option('#wiAsset', 'PRESS-08')
        page.locator('#wiLoad').click()
        page.wait_for_selector("#whatifView [role='alert']", timeout=8000)
        asked = [body for url, body in sent if url.endswith('/api/agent/whatif')]
        assert asked == [{'asset': 'PRESS-08', 'pattern': 'SEAL_WEAR'}]
        # 서버가 거절하면 빈 결과가 아니라 서버의 까닭이 결과 자리에 남는다
        assert '이 설비에는 씰 마모의 원인 지식이 없습니다' in page.inner_text("#whatifView [role='alert']")
    finally:
        close()


def test_조건별_손익은_설비_목록을_읽지_못하면_빈_목록으로_두지_않고_까닭과_다시_시도를_보인다():
    sent = []
    page, close = _page({'/plant-sim/api/state': (503, {'detail': '설비 시뮬레이터가 응답하지 않습니다'}), '/api/ontology/patterns': PATTERNS}, sent)
    try:
        open_screen(page, 'whatif')
        page.wait_for_selector("#whatifView [role='alert']", timeout=15000)
        assert '설비 목록을 읽지 못했습니다' in page.inner_text("#whatifView [role='alert']")
        assert page.locator('#wiLoad').is_disabled() and page.locator("#whatifView [data-retry]").count() == 1
    finally:
        close()


def test_규칙_판단은_설비_목록을_서버에서_읽고_결론을_응답의_칸으로_짓는다():
    """규칙 판단의 설비 고르기도 화면에 박혀 있었다. 결론은 서버 설명문의 첫 문장을 문장 부호로 잘라 쓰던 것이었는데(후보마다의 제외 사유가 한 문장에
    줄줄이 달리면 큰 글 한 줄이 문단이 됐다), 이제 응답의 칸(1순위 원인 · 추천 · 후보)으로 짓고 설명문 전문은 「원문」 보기에 받은 그대로 둔다."""
    why = '; '.join(f'SOP-X-{n} 조치 {n} (현재 조치 예측을 확인할 수 없습니다: 지금 바뀌는 중인 외란이 있어 입력을 고정한 예측이 맞지 않습니다)' for n in range(1, 4))
    options = [{'id': f'skill:x-{n}', 'name': f'조치 {n}', 'sopId': f'SOP-X-{n}', 'feasible': False, 'rank': None, 'score': None, 'actions': [], 'approver': {'name': '운전원'},
                'violations': [{'rule': 'rule:forecast', 'annotation': '현재 조치 예측을 확인할 수 없습니다'}]} for n in range(1, 4)]
    decided = {'id': 'EVAL-1', 'created': '2026-11-14T00:00:00Z', 'asset': 'PRESS-08', 'status': 'NO_FEASIBLE_OPTION', 'steps': [], 'causes': [], 'provenance': [],
               'scenario': {'name': '씰 마모 조치 판단'}, 'facts': {},
               'result': {'options': options, 'recommended': None, 'trace': [], 'explanation': f'씰 마모 — 후보 3장 모두 규정상 제외됐다: {why}.'}}
    sent = []
    page, close = _page({'/plant-sim/api/state': PLANT, '/api/ontology/patterns': PATTERNS, '/api/agent/decide': decided}, sent)
    try:
        open_screen(page, 'decision')
        page.wait_for_function("document.querySelectorAll('#decAsset option').length > 0 && document.querySelectorAll('#decPattern option').length > 0", timeout=8000)
        assert page.eval_on_selector_all('#decAsset option', 'xs => xs.map(x => x.value)') == ['PRESS-07', 'PRESS-08']
        page.select_option('#decAsset', 'PRESS-08')
        page.locator('#decRun').click()
        page.wait_for_selector('#decResult .panel-head h2', timeout=8000)
        assert [body for url, body in sent if url.endswith('/api/agent/decide')] == [{'asset': 'PRESS-08', 'pattern': 'SEAL_WEAR', 'facts': {}}]
        # 결론 문장은 응답의 칸(추천 없음 · 후보 3개 모두 제외)으로 짓는다 — 서버 설명문의 첫 문장을 잘라 쓰지 않는다
        assert page.inner_text('#decResult .panel-head h2') == '추천할 조치가 없습니다 — 조치 후보 3개가 모두 규정에서 제외됐습니다.'
        # 나머지 설명문은 버리지 않되 첫 화면에 줄글로 펼치지 않는다 — 결과 아래의 하나뿐인 접기(「자세히 보기」)의 「원문」 보기 안에 있고 접혀서 시작한다
        fold = page.locator('#decResult details', has=page.locator('.result-sub'))
        assert 'SOP-X-3 조치 3' in fold.locator('.result-sub').text_content() and fold.evaluate('d => d.open') is False
        assert page.locator('#decResult details').count() == page.locator('#decResult details.raw').count() + page.locator('#decResult .panel-sec > details').count()      # 근거 줄 사이에 따로 선 접기가 없고, 후보별 근거(optionDetail) 안에도 접기가 없다(접기 안의 접기 금지)
        assert page.locator('#decResult [data-dec-body="options"] .opt-detail').count() == 3 and page.locator('#decResult [data-opt-pick] option').count() == 3
        assert fold.locator('summary').first.inner_text().strip() == '자세히 보기'
        fold.locator('summary').first.click(); page.click('#decResult [data-dec-pane="raw"]')
        shown = page.inner_text('#decResult [data-dec-body="raw"]')
        assert '판단 엔진 설명 전문' in shown and 'SOP-X-3 조치 3' in shown and page.locator('#decResult [data-dec-body="inputs"]').is_hidden()
    finally:
        close()


def test_규칙_판단의_보류는_실패가_아닌_판단_보류로_보이고_늘_같은_답에는_다시_시도를_붙이지_않는다():
    """독립 검토 가-8: 판단 엔진의 정상 결과인 「원인 보류」(409 — 지금 관측 값으로 뒷받침되는 원인이 없음)가 빨간 「판단 실패」와 [다시 시도]로 보였다.
    원인 지식이 없는 이상 패턴(404)도 다시 눌러 봐야 같은 답이다. 연결 · 서버 오류(500)만 실패이고 다시 시도가 붙는다."""
    held = {'detail': {'reason': '현재 관측 근거로 뒷받침되는 원인이 없어 조치를 보류합니다.', 'causes': [
        {'id': 'cause:x', 'name': '씰 마모', 'failureMode': '체적 효율 저하', 'score': 0.0,
         'evidence': [{'id': 'evd:x', 'name': '토출 압력 평균 165 bar 미만', 'tag': 'PS1', 'passed': False, 'status': 'FAIL', 'value': 182.0}]}]}}
    answers = {'/plant-sim/api/state': PLANT, '/api/ontology/patterns': PATTERNS, '/api/agent/decide': (409, held)}
    page, close = _page(answers, [])
    try:
        open_screen(page, 'decision')
        page.wait_for_function("document.querySelectorAll('#decAsset option').length > 0 && document.querySelectorAll('#decPattern option').length > 0", timeout=8000)
        page.locator('#decRun').click()
        page.wait_for_selector('#decResult .panel-head h2', timeout=8000)
        said = page.inner_text('#decResult')
        assert '판단 보류' in said and '실패가 아닙니다' in said and '판단 실패' not in said
        assert '토출 압력 평균 165 bar 미만' in said and '조건 미충족' in said      # 무엇을 확인했고 왜 원인으로 삼지 않았는지
        assert page.locator("#decResult [role='alert']").count() == 0 and page.locator('#decResult [data-retry]').count() == 0

        answers['/api/agent/decide'] = (404, {'detail': "'씰 마모'의 원인 지식이 아직 없습니다"})
        page.locator('#decRun').click()
        page.wait_for_selector("#decResult [role='alert']", timeout=8000)
        assert '원인 지식이 아직 없습니다' in page.inner_text('#decResult') and '판단 실패' not in page.inner_text('#decResult')
        assert page.locator('#decResult [data-retry]').count() == 0

        answers['/api/agent/decide'] = (500, {'detail': '판단 서비스가 지식 그래프에 연결하지 못했습니다'})
        page.locator('#decRun').click()
        page.wait_for_function("document.querySelector('#decResult').innerText.includes('판단 실패')", timeout=8000)
        assert page.locator('#decResult [data-retry]').count() == 1
    finally:
        close()


def _trial(side, status, *, cause=None, top=None, skills=(), calls=(), asset='HYD-01', pattern='COOLER_DEGRADATION', reason=None, tools=('hyd-dmn',)):
    """에이전트 시험 한쪽의 기록(process /api/agent-trials/run 응답의 a · b 꼴)."""
    return {'id': f'TRY-{side}', 'created_at': '2026-11-14T00:00:00Z', 'snapshot_id': 'SNAP-1', 'asset': asset, 'pattern': pattern, 'agent_id': f'agent:{side}',
            'setting': {'name': f'에이전트 {side}', 'skills': [{'name': k['name']} for k in skills]}, 'variant': {}, 'status': status, 'fingerprint': side * 12,
            'result': {'status': status, 'reason': reason, 'explanation': None, 'calls': list(calls), 'citations': [], 'facts': [], 'ranking': [],
                       'diagnosis': {'top': {'id': cause, 'failureModeId': 'fm:x'}} if cause else None, 'recommended': {'id': top, 'sopId': 'SOP-1'} if top else None,
                       'agent': {'tools': list(tools), 'skills': list(skills)}}}


def _diff(a, b, *, same_result, rows, order_same):
    top = lambda t: ((t['result']['diagnosis'] or {}).get('top') or {}).get('id')      # noqa: E731
    rec = lambda t: (t['result']['recommended'] or {}).get('id')                         # noqa: E731
    return {'same_input': True, 'same_result': same_result, 'cause': {'a': top(a), 'b': top(b), 'same': top(a) == top(b)},
            'recommended': {'a': rec(a), 'b': rec(b), 'a_sop': 'SOP-1', 'b_sop': 'SOP-1', 'same': rec(a) == rec(b)},
            'calls': rows, 'order_same': order_same, 'calls_only_a': sum(1 for r in rows if r['b'] is None), 'calls_only_b': sum(1 for r in rows if r['a'] is None),
            'citations': {'only_a': [], 'only_b': [], 'shared': 0}, 'ranking': [], 'facts': [], 'compliance': [], 'rules': {'only_a': [], 'only_b': []}}


def test_에이전트_시험_비교의_결론은_호출_기록의_지문이_아니라_두_구성이_이른_판단으로_말한다():
    """독립 검토 가-2: 결론이 서버의 same_result(호출 기록 전체의 지문)로 정해져, 원인 · 1순위가 같고 막힌 제출 호출 한 줄만 달라도 「다릅니다」,
    두 쪽 모두 판단을 보류해도 「같습니다」였다. 스킬 줄은 부르지 못한 호출 하나를 「도구 호출 1개를 순서대로 따름」이라고 했다."""
    diagnose = {'tool': 'diagnose', 'server': 'hyd-dmn', 'by': 'engine', 'status': 'DONE', 'args': {}, 'summary': '원인 후보 1개'}
    blocked = {'tool': 'submit_decision', 'server': '-', 'by': '스킬 my-skill', 'status': 'BLOCKED', 'args': {}, 'reason': '시험 실행은 판단 결과를 제출하지 않습니다'}

    def run(body):
        if body['scenario'] == 'cooler':       # 원인 · 1순위는 같고, B 의 스킬 문서가 가리킨 제출 호출 한 줄만 다르다 → 지문은 다르다
            a = _trial('a', 'EVALUATED', cause='cause:x', top='skill:x', calls=[diagnose])
            b = _trial('b', 'EVALUATED', cause='cause:x', top='skill:x', calls=[diagnose, blocked], skills=[{'name': 'my-skill', 'applied': True, 'reason': None, 'steps': 1}])
            return {'snapshot': {'created_at': '2026-11-14T00:00:00Z'}, 'a': a, 'b': b,
                    'diff': _diff(a, b, same_result=False, rows=[{'a': 0, 'b': 0, 'same': True}, {'a': None, 'b': 1, 'same': False}], order_same=False)}
        if body['scenario'] == 'pump':         # 두 쪽 모두 보류 → 지문은 같다
            a, b = (_trial(s, 'WITHHELD', asset='HYD-02', pattern='PUMP_LEAKAGE', reason='현재 관측 근거로 뒷받침되는 원인이 없어 조치를 보류합니다.', calls=[diagnose]) for s in 'ab')
            return {'snapshot': {'created_at': '2026-11-14T00:00:00Z'}, 'a': a, 'b': b, 'diff': _diff(a, b, same_result=True, rows=[{'a': 0, 'b': 0, 'same': True}], order_same=True)}
        a = _trial('a', 'EVALUATED', asset='HYD-03', pattern='FAN_VIBRATION', cause='cause:x', top='skill:x', calls=[diagnose])      # B 는 판단 도구 서버가 없다
        b = _trial('b', 'NO_ENGINE_TOOL', asset='HYD-03', pattern='FAN_VIBRATION', tools=(), reason='판단 엔진 도구(hyd-dmn)가 없어 원인 진단·조치 판단을 할 수 없습니다',
                   calls=[dict(diagnose, status='BLOCKED', reason='이 에이전트의 도구 구성에 hyd-dmn 가 없어 부르지 못했습니다')])
        return {'snapshot': {'created_at': '2026-11-14T00:00:00Z'}, 'a': a, 'b': b, 'diff': _diff(a, b, same_result=False, rows=[{'a': 0, 'b': 0, 'same': False}], order_same=True)}

    options = {'scenarios': [{'key': 'cooler', 'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION', 'label': '쿨러 성능 저하 · HYD-01'},
                             {'key': 'pump', 'asset': 'HYD-02', 'pattern': 'PUMP_LEAKAGE', 'label': '펌프 내부 누설 · HYD-02'},
                             {'key': 'fan', 'asset': 'HYD-03', 'pattern': 'FAN_VIBRATION', 'label': '팬 진동 상승 · HYD-03'}],
               'agents': [{'id': 'agent:a', 'name': '에이전트 a', 'tools': ['hyd-dmn'], 'skills': []},
                          {'id': 'agent:b', 'name': '에이전트 b', 'tools': ['hyd-dmn'], 'skills': [{'name': 'my-skill', 'description': '내 스킬 설명'}]}]}
    history = [{'id': 'TRY-1', 'created_at': '2026-11-14T00:00:00Z', 'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION', 'agent_id': 'agent:a', 'agent_name': '에이전트 a', 'variant': {}, 'status': 'EVALUATED', 'recommended': 'skill:x'},
               {'id': 'TRY-2', 'created_at': '2026-11-14T00:01:00Z', 'asset': 'HYD-02', 'pattern': 'PUMP_LEAKAGE', 'agent_id': 'agent:a', 'agent_name': '에이전트 a', 'variant': {}, 'status': 'WITHHELD', 'recommended': None}]
    page, close = _page({'/api/agent-trials/options': options, '/api/agent-trials/run': run, '/api/agent-trials': history}, [])
    try:
        open_screen(page, 'compare')
        page.wait_for_selector("#compareView [data-f='scenario']", timeout=8000)

        def trial(scenario):
            page.select_option("#compareView [data-f='scenario']", scenario)
            page.locator("#compareView [data-act='run']").click()
            page.wait_for_selector("#compareView [data-r='result'] .turn-facts", timeout=8000)
            return page.inner_text("#compareView [data-r='result'] .panel-head h2"), page.inner_text("#compareView [data-r='result']")
        title, body = trial('cooler')
        assert title.startswith('두 구성이 같은 원인') and '다릅니다' not in title
        assert '문서에서 알아본 도구 호출 1개 · 실제로 부른 것 0개 · 부르지 못한 것 1개(시험 실행은 판단 결과를 제출하지 않습니다)' in body
        assert '내 스킬 설명' in body and '순서대로 따름' not in body
        assert '부르지 못한 호출 1회 포함' in body and 'hyd-dmn' not in body
        title, body = trial('pump')
        assert title.startswith('두 구성 모두 판단을 보류했습니다') and '같습니다' not in title
        assert '실패가 아니라 판단하지 않은 것입니다' in body
        title, body = trial('fan')
        assert title.startswith('B만 판단에 이르지 못했습니다') and '판단 시스템 도구 서버가 없어' in title and 'hyd-dmn' not in body
        # 이 시험이 무엇을 하지 않는지: 스킬 문서의 뜻을 읽지 않는다 · 지금 이상 값이 없으면 보류한다
        # 보류 조건은 시나리오 칸 아래에 늘 보이고, 스킬 문서를 어떻게 다루는지는 스킬을 고르는 접기(「B에서 빼 보기」)를 펼치면 그 목록 아래에 있다
        form = page.inner_text('#compareView form')
        assert '지금 이상 값이 없으면 어느 구성이든 원인 진단을 보류합니다' in form
        if not page.evaluate("document.querySelector('#compareView [data-cmp-drop]').open"):      # 뺀 것이 있으면 이미 펼쳐져 있다
            assert '스킬 문서는 뜻을 읽지 않습니다' not in form
            page.click('#compareView [data-cmp-drop] > summary')
        page.wait_for_function("document.querySelector('#compareView [data-cmp-drop]').innerText.includes('스킬 문서는 뜻을 읽지 않습니다')", timeout=5000)      # 접기가 펼쳐지는 움직임이 끝난 뒤에 보인다

        # 지난 시험과 비교: 고르기 줄이 무엇의 시험인지 말하고, 서로 다른 시나리오의 시험 둘은 견주지 않는다
        page.locator("#compareView [data-act='history']").click()
        page.wait_for_selector("#compareView [data-pick='a']", timeout=8000)
        assert '쿨러 성능 저하 · HYD-01 · 에이전트 a' in page.inner_text("#compareView [data-pick='a']")
        page.select_option("#compareView [data-pick='a']", 'TRY-1')
        page.select_option("#compareView [data-pick='b']", 'TRY-2')
        assert page.locator("#compareView [data-act='diff']").is_disabled()
        assert '시나리오가 다릅니다' in page.inner_text('#compareView .io-out > .panel')
    finally:
        close()


def test_원인_진단_대상이_아닌_이상_패턴을_고르면_누르기_전에_서버의_까닭을_보이고_실행_단추를_끈다():
    """이상 패턴 목록이 줄마다 주는 judgeable · reason 을 쓴다. 전에는 모든 패턴을 똑같이 늘어놓아, 정기 정비 도래 같은 업무 경보를 골라 누른 뒤에야 404 로 까닭을 봤다."""
    why = "'정기 정비 도래'는 고장 원인을 진단하는 이상 패턴이 아닙니다 — 업무 흐름의 에이전트가 판단합니다"
    patterns = [{'id': 'pattern:pm', 'code': 'PM_DUE', 'name': '정기 정비 도래', 'failureModes': [], 'judgeable': False, 'reason': why},
                {'id': 'pattern:x', 'code': 'SEAL_WEAR', 'name': '씰 마모', 'failureModes': ['씰 누설'], 'judgeable': True, 'reason': None}]
    sent = []
    page, close = _page({'/plant-sim/api/state': PLANT, '/api/ontology/patterns': patterns}, sent)
    try:
        open_screen(page, 'decision')
        page.wait_for_function("document.querySelectorAll('#decPattern option').length === 2", timeout=8000)
        # 판단할 수 있는 패턴이 먼저(기본으로 골라진다), 판단할 수 없는 패턴은 묶음 아래에
        assert page.eval_on_selector('#decPattern', 's => s.value') == 'SEAL_WEAR' and page.locator('#decPattern optgroup option').all_inner_texts() == ['정기 정비 도래']
        assert page.locator('#decWhy').is_hidden() and not page.locator('#decRun').is_disabled()
        page.select_option('#decPattern', 'PM_DUE')
        assert page.inner_text('#decWhy') == why and page.locator('#decRun').is_disabled()
        page.select_option('#decPattern', 'SEAL_WEAR')
        assert page.locator('#decWhy').is_hidden() and not page.locator('#decRun').is_disabled()
        open_screen(page, 'whatif')
        page.wait_for_function("document.querySelectorAll('#wiPattern option').length === 2", timeout=8000)
        page.select_option('#wiPattern', 'PM_DUE')
        page.wait_for_function("document.querySelector('#wiLoad').disabled", timeout=8000)
        assert why in page.inner_text('#whatifView .io-in, #whatifView')
    finally:
        close()
