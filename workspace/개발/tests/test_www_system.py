"""시스템 무리의 화면 — 성과 지표(it/portal/www/kpi.js) · 관리(configBundle.js · studentCases.js · sourceEvents.js).

실제 index.html 을 실제 브라우저(Playwright Chromium)로 연다. 브라우저 밖의 서비스 응답(지표 실적 · 역추적 · 구성 목록 · 접수)만 이 시험이 준다
(꼴은 process /api/kpi · /api/kpi/trace · /api/config/cases · /api/source-events). 배치는 고정 px 가 아니라 브라우저에서 잰 관계로 판정한다."""
import json

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from conftest import WWW, Served, open_screen

ME = {'id': 'user:me', 'name': '담당자', 'roles': []}
LABELS = {'met': '달성', 'missed': '미달', 'no_target': '목표 없음', 'incomparable': '단위 달라 판정 안 함', 'partial': '부분 실적', 'no_data': '기록 없음', 'unavailable': '계산 불가', 'error': '조회 실패'}


def _page(answers, sent, *, width=1440):
    """index.html 을 띄우고 /svc/ 요청은 answers(주소 끝 → 응답 · (상태, 응답) · 함수)로 답한다. 쓰기 요청의 (방법, 주소, 본문)은 sent 에 남는다."""
    from playwright.sync_api import sync_playwright
    app = FastAPI()
    app.mount('/', StaticFiles(directory=WWW, html=True))
    served = Served(app)

    def answer(route):
        url = route.request.url.split('?')[0]
        if route.request.method != 'GET':
            sent.append((route.request.method, url, json.loads(route.request.post_data or '{}')))
        hit = next((body for tail, body in answers.items() if url.endswith(tail)), {})
        if callable(hit):
            hit = hit(route.request)
        status, body = hit if isinstance(hit, tuple) else (200, hit)
        return route.fulfill(status=status, json=body)
    pw = sync_playwright().start()
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width': width, 'height': 900})
    page.route('**/svc/**', answer)
    page.goto(served.url + '/index.html')

    def close():
        browser.close()
        pw.stop()
        served.close()
    return page, close


def _measure(mid, name, status, *, value=None, target=None, rate=None, unit='%', note=None, reason=None):
    return {'id': mid, 'name': name, 'status': status, 'value': value, 'unit': unit, 'displayUnit': unit, 'target': target, 'rate': rate, 'kpiRole': 'leading',
            'reason': reason, 'note': note, 'definition': {'kind': 'calc', 'formula': f'{name}의 식', 'sources': [{'system': '업무 DB', 'table': 'ent.t', 'columns': 'a'}]}}


def _kpi():
    """판정이 갈리는 지표 열: 미달 1 · 달성 1 · 판정하지 않음 5(목표 없음 넷 · 단위가 달라 견주지 않은 것 하나 — 이 하나만 목표 줄이 있다) · 계산할 수 없음 2."""
    money = [_measure('msr:a', '에너지비', 'no_target', value=93.32, unit='만원/월'), _measure('msr:b', '견줄 수 없는 지표', 'incomparable', value=3, target=5, unit='ea'),
             _measure('msr:c', '부품 구매비', 'no_target', value=0, unit='만원/월'), _measure('msr:d', '재고량', 'no_target', value=1200, unit='ea'),
             _measure('msr:e', '전력 사용량', 'no_target', value=207.4, unit='kWh/일'),
             _measure('msr:x', '매출', 'unavailable', reason='업무 DB에 판매 기록이 없습니다'), _measure('msr:y', '부품 단가', 'no_data', reason='기간 안 발주가 없습니다')]
    inner = [_measure('msr:miss', '인터록 여유', 'missed', value=8.09, target=10, rate=80.9, unit='℃'), _measure('msr:met', '설비 가동률', 'met', value=100, target=95, rate=105.3)]
    return {'window': {'period': '24h', 'label': '최근 24시간', 'start': '2026-11-15T00:00:00Z', 'end': '2026-11-16T00:00:00Z'}, 'periods': {'24h': '최근 24시간', '7d': '최근 7일'}, 'sourceErrors': [],
            'summary': {'total': 9, 'met': 1, 'missed': 1, 'no_target': 4, 'incomparable': 1, 'partial': 0, 'no_data': 1, 'unavailable': 1, 'error': 0, 'labels': LABELS},
            'perspectives': [{'id': 'p:f', 'name': '재무', 'objectives': [{'id': 'o:1', 'name': '원가 절감', 'supports': [], 'measures': money}]},
                             {'id': 'p:i', 'name': '내부 프로세스', 'objectives': [{'id': 'o:2', 'name': '무재해 운전', 'supports': [{'name': '설비 가용성 확보'}], 'measures': inner}]}]}


TRACE = {'measure': {'id': 'msr:miss', 'name': '인터록 여유', 'value': 8.09, 'target': 10, 'unit': '℃', 'displayUnit': '℃'}, 'window': {'label': '최근 24시간'}, 'instancesRead': 3, 'instanceTotal': 1,
         'sourceErrors': [], 'actions': [], 'assets': [], 'drivers': [], 'objectives': [], 'skills': [],
         'instances': [{'asset': 'PRESS-07', 'patternName': '쿨러 성능 저하', 'pattern': 'COOLER_DEGRADATION', 'start': '2026-11-15T05:00:00Z', 'chosenSkill': None, 'causeName': '쿨러 핀 오염',
                        'reasons': ['지표를 깎은 시각에 열려 있던 처리 건'], 'link': '#/instances/c3_cooling.x1'}]}


def test_성과_지표는_숫자_카드를_누르면_그_판정의_지표만_보이고_지표_카드는_줄이_달라도_높이가_같다():
    """전에는 관점마다 모든 지표 카드와 카드마다의 [계산 근거] 단추 · 설명 문단 · 「목표 없음」 뱃지가 첫 화면에 펼쳐졌고(본문 요소 62), 목표 줄이 있는 카드와 없는 카드가
    섞인 줄만 키가 커서 줄마다 높이가 달랐다. 이제 숫자 카드 넷이 보기 고르기이고, 처음에는 미달(이 화면의 일은 미달의 원인을 따라가는 것)이 골라져 있다."""
    page, close = _page({'/api/kpi': _kpi(), '/api/inbox/users': [ME]}, [])
    try:
        open_screen(page, 'kpi')
        page.wait_for_selector('#kpiView .kpi-stats', timeout=15000)
        groups = page.locator('#kpiView [data-kpi-group]')
        assert groups.evaluate_all('xs => xs.map(x => [x.dataset.kpiGroup, x.querySelector(".stat-value").textContent.trim(), x.getAttribute("aria-pressed")])') == \
            [['missed', '1개', 'true'], ['met', '1개', 'false'], ['open', '5개', 'false'], ['dead', '2개', 'false']]
        shown = lambda: page.locator('#kpiView .kpi-card').evaluate_all('xs => xs.map(x => x.dataset.kpi)')      # noqa: E731
        assert shown() == ['msr:miss']                                           # 처음에는 미달만
        card = page.locator("#kpiView .kpi-card[data-kpi='msr:miss']")
        assert card.locator('.stat-pill').inner_text() == '미달' and '목표 10 ℃ · 달성률 80.9 %' in card.inner_text() and card.locator('[data-kpi-trace]').inner_text() == '원인 찾기'
        assert card.locator('button').count() == 2                                # 이름(계산 근거) · 원인 찾기 — 「계산 근거」 단추와 설명 문단은 카드에 없다

        page.evaluate("window.__head = document.querySelector('#kpiView .page-head')")      # 본문을 다시 그려도 화면 머리는 그대로다(연 「…」 메뉴가 닫히지 않는다)
        groups.nth(2).click()                                                     # 판정하지 않음: 다섯 장이 1440 폭에서 두 줄
        assert page.evaluate("window.__head === document.querySelector('#kpiView .page-head') && window.__head.isConnected")
        assert shown() == ['msr:a', 'msr:b', 'msr:c', 'msr:d', 'msr:e'] and groups.nth(2).get_attribute('aria-pressed') == 'true'
        boxes = page.locator('#kpiView .kpi-card').evaluate_all('xs => xs.map(x => { const r = x.getBoundingClientRect(); return [Math.round(r.top), Math.round(r.height)]; })')
        assert len({top for top, _ in boxes}) == 2, boxes                         # 두 줄에 걸쳐 있다
        assert len({h for _, h in boxes}) == 1, f'줄마다 카드 높이가 다르다: {boxes}'
        # 목표가 없는 지표는 판정 칸을 비운다(「목표 없음」 뱃지 없음). 영문 단위 약자는 화면 말로
        assert page.locator('#kpiView .kpi-card .stat-pill').count() == 0 and '목표 없음' not in page.inner_text('#kpiView .kpi-list')
        assert '1,200개' in page.locator("#kpiView .kpi-card[data-kpi='msr:d']").inner_text().replace('\n', '') and 'ea' not in page.inner_text('#kpiView .kpi-list')
        assert '판정하지 않은 지표입니다' in page.inner_text('#kpiView .kpi-list .scope')      # 이 보기가 무엇인지 한 줄

        groups.nth(3).click()                                                     # 계산할 수 없음: 큰 숫자 카드가 아니라 까닭 표
        assert shown() == [] and page.locator('#kpiView .kpi-dead tbody tr').count() == 2
        assert '업무 DB에 판매 기록이 없습니다' in page.inner_text('#kpiView .kpi-dead') and '기간 안 발주가 없습니다' in page.inner_text('#kpiView .kpi-dead')
        groups.nth(1).click()
        assert shown() == ['msr:met'] and page.locator("#kpiView .kpi-card[data-kpi='msr:met'] .stat-pill").inner_text() == '달성'
    finally:
        close()


def test_성과_지표_카드를_누르면_옆_판에_계산_근거가_열리고_미달의_원인_찾기는_처리_건까지_이어진다():
    """계산 근거는 카드마다의 단추가 아니라 카드를 누르면 옆 판에 열린다. 미달 카드의 「원인 찾기」는 같은 옆 판의 「미달 원인」 보기를 열고,
    찾는 동안 무엇을 하는 중인지와 걸린 시간이 보이며, 원인 처리 건의 「처리 건에서 보기」가 처리 건 화면으로 간다."""
    hold = {'on': True}

    def trace(request):
        return (503, {'detail': '잠시 뒤 다시'}) if hold['on'] else TRACE
    page, close = _page({'/api/kpi': _kpi(), '/api/kpi/trace': trace, '/api/inbox/users': [ME]}, [])
    try:
        open_screen(page, 'kpi')
        page.wait_for_selector('#kpiView .kpi-card', timeout=15000)
        sheet = page.locator('dialog[data-kpi-sheet]')
        assert not sheet.evaluate('d => d.open')
        # 카드의 어디를 눌러도(이름이 아닌 큰 숫자) 계산 근거가 열린다
        spot = page.locator("#kpiView .kpi-card[data-kpi='msr:miss'] .stat-value").bounding_box()
        page.mouse.click(spot['x'] + spot['width'] / 2, spot['y'] + spot['height'] / 2)
        page.wait_for_function("document.querySelector('dialog[data-kpi-sheet]').open")
        said = sheet.inner_text()
        assert '인터록 여유' in said and '내부 프로세스 › 무재해 운전' in said and '인터록 여유의 식' in said and '설비 가용성 확보' in said
        assert sheet.locator("[data-kpi-view='basis']").get_attribute('aria-selected') == 'true'
        sheet.locator('[data-kpi-sheet-close]').click()
        page.wait_for_function("!document.querySelector('dialog[data-kpi-sheet]').open")

        # 원인 찾기: 읽지 못하면 그 자리에 까닭과 [다시 찾기], 다시 찾으면 처리 건까지
        page.locator("#kpiView [data-kpi-trace='msr:miss']").click()
        page.wait_for_function("document.querySelector('dialog[data-kpi-sheet]').innerText.includes('미달 원인을 찾지 못했습니다')", timeout=8000)
        assert sheet.locator("[data-kpi-view='trace']").get_attribute('aria-selected') == 'true' and '잠시 뒤 다시' in sheet.inner_text()
        hold['on'] = False
        sheet.locator("[data-kpi-trace='msr:miss']").click()
        page.wait_for_function("document.querySelector('dialog[data-kpi-sheet]').innerText.includes('처리 건에서 보기')", timeout=8000)
        said = sheet.inner_text()
        assert '같은 기간의 처리 건 3건 가운데 1건이 이 지표에 영향을 주는 경로에 걸려 있습니다.' in said and 'PRESS-07 · 쿨러 성능 저하' in said
        sheet.locator('a[data-kpi-go]').click()
        page.wait_for_function("state.tab === 'instances'", timeout=8000)
        assert not sheet.evaluate('d => d.open') and page.evaluate('location.hash') == '#/instances/c3_cooling.x1'
    finally:
        close()


CASES = {'assets': [{'kind': 'flows', 'asset_id': 'c3_cooling', 'name': '냉각 긴급 대응', 'kind_name': '흐름', 'label': ''},
                    {'kind': 'agents', 'asset_id': 'agent:u-1', 'name': '내 에이전트', 'kind_name': 'AI 에이전트', 'label': ''}]}
FLOWS = {'versions': [{'id': 'c3_cooling', 'class_flow': True}], 'drafts': []}
WHY = '출발본 불러오기는 제한 없이 쓰는 단계에서 엽니다 — 파일에 든 내 도구 서버와 흐름이 함께 들어오기 때문입니다.'
ACCESS = {'phase': 'course', 'actions': {'config.import': {'allowed': False, 'reason': WHY}, 'tool_servers.register': {'allowed': True}},
          'reasons': {'assign': '-', 'start': '-', 'import_flow': '-', 'document': '-'}}      # 불러오기가 막힌 단계 — 단추가 꺼지고 까닭 한 줄이 붙는다


def test_관리의_내_설정은_설정_줄_넷이고_줄마다_동작이_하나이며_사례_이름_표는_옆_판에_있다():
    """전에는 「내 사례」의 구성 표(입력 칸 줄줄이) · 범위 고르기 · 파일 칸 · 「지우는 것 · 남는 것」 접기가 첫 화면에 펼쳐져 있었다(본문 요소 41).
    이제 설정 하나에 줄 하나(이름 · 한 줄 설명 · 오른쪽 끝 동작 하나)이고, 표는 [사례 보기]로 여는 옆 판에 있다."""
    sent = []

    def tag(request):
        return {'label': json.loads(request.post_data)['label']}
    page, close = _page({'/api/config/cases/tag': tag, '/api/config/cases': CASES, '/api/flows': FLOWS, '/api/inbox/users': [ME], '/api/course-access': ACCESS}, sent)
    try:
        open_screen(page, 'admin')
        rows = page.locator('#configBundleView .settings > .setting')
        page.wait_for_function("document.querySelectorAll('#configBundleView .settings > .setting').length === 4", timeout=8000)
        assert rows.locator('b').all_inner_texts() == ['내 사례', '출발본 내보내기', '출발본 불러오기', '기준으로 되돌리기']
        page.wait_for_selector('#configBundleView [data-course-why]', timeout=8000)
        acts = rows.evaluate_all("""xs => xs.map(x => { const b = [...x.querySelectorAll('button, select, input, a')].filter(n => n.getClientRects().length);
          return { n: b.length, right: Math.round(b[0].getBoundingClientRect().right), desc: x.querySelectorAll('p').length,
                   mid: Math.abs((b[0].getBoundingClientRect().top + b[0].getBoundingClientRect().bottom) - (x.getBoundingClientRect().top + x.getBoundingClientRect().bottom)) / 2 }; })""")
        assert [a['n'] for a in acts] == [1, 1, 1, 1], f'줄마다 보이는 동작은 하나다: {acts}'
        assert len({a['right'] for a in acts}) == 1, f'동작의 오른쪽 끝이 같은 세로선에 서지 않는다: {acts}'
        assert all(a['desc'] == 1 for a in acts), acts                                   # 설명은 한 줄씩
        # 막힌 동작(불러오기)은 그 자리에서 꺼져 있고, 까닭 한 줄은 단추 옆에 끼지 않고 줄 아래 온 줄로 놓인다(단추의 자리는 다른 줄과 같다)
        page.wait_for_selector('#configBundleView [data-course-why]', timeout=8000)
        why = page.evaluate("""() => { const w = document.querySelector('#configBundleView [data-course-why]').getBoundingClientRect(), b = document.querySelector('#cfgImport').getBoundingClientRect(),
          r = document.querySelector('#cfgImport').closest('.setting').getBoundingClientRect(); return { below: w.top >= b.bottom, left: Math.abs(w.left - r.left), text: document.querySelector('#configBundleView [data-course-why]').textContent }; }""")
        assert page.locator('#cfgImport').is_disabled() and why['text'] == WHY and why['below'] and why['left'] <= 1, why
        assert page.locator('#configBundleView table').count() == 0 and page.locator('#configBundleView details').count() == 0
        assert page.locator('#configBundleView .setting-more:visible').count() == 0      # 줄 아래 칸은 그 동작을 한 뒤에만 나타난다

        page.locator('#caseOpen').click()
        page.wait_for_selector('#caseSheet[open] [data-case-row]', timeout=8000)
        sheet = page.locator('#caseSheet')
        assert sheet.locator('[data-case-row]').count() == 2 and '기본 제공' in sheet.locator('[data-case-row]').nth(0).inner_text() and '내가 만든 것' in sheet.locator('[data-case-row]').nth(1).inner_text()
        assert sheet.locator('#caseExport').is_disabled()                                # 사례를 고르기 전에는 받을 수 없다
        box = sheet.locator('[data-case-label]').nth(1)
        box.fill('비품 재주문'); box.press('Enter')
        page.wait_for_function("document.querySelector('#caseMessage').textContent.includes('「내 에이전트」를 「비품 재주문」 사례에 넣었습니다')", timeout=8000)
        assert ('PUT', {'kind': 'agents', 'asset_id': 'agent:u-1', 'label': '비품 재주문'}) in [(m, b) for m, u, b in sent if u.endswith('/api/config/cases/tag')]
        page.select_option('#caseFilter', '비품 재주문')
        assert sheet.locator('[data-case-row]').count() == 1 and not sheet.locator('#caseExport').is_disabled()
        sheet.locator('[data-case-close]').click()
        page.wait_for_function("!document.querySelector('#caseSheet').open")
    finally:
        close()


RECEIPT = {'id': 7, 'kind': 'RAISE', 'status': 'HANDLED', 'asset': 'PRESS-07', 'source': 'kafka', 'received_at': '2026-11-16T05:01:00Z', 'attempts': 1, 'failures': 0, 'error': None,
           'payload': {'alertId': 'ALT-1'}, 'policy': {'definition': 'my_flow'}, 'history': [], 'wire_kind': 'decoded',
           'result': {'incident': 'INC-1116-01-7362', 'instance': 'my_flow.abc', 'definition': {'version': '1', 'definition': 'my_flow'}}}


def test_관리의_접수_기록은_처음부터_전체를_읽고_처리_결과를_글과_처리_건_링크로_보인다():
    """전에는 처음 거르기가 「처리 실패」라 결함을 넣은 뒤에도 「접수가 없습니다」였고, 고른 접수의 처리 결과는 {"incident":…,"instance":…} JSON 한 줄이었다."""
    asked = []

    def listing(request):
        asked.append(request.url.split('?')[1])
        return [] if 'status=FAILED' in request.url else [RECEIPT]
    page, close = _page({'/api/source-events/7': RECEIPT, '/api/source-events': listing, '/api/inbox/users': [ME]}, [])
    try:
        open_screen(page, 'admin')
        page.locator("#adminList [data-admin='sourceEventsPanel']").click()
        page.wait_for_selector('#sourceEventList .row', timeout=8000)
        assert page.locator('#sourceEventStatus').input_value() == '' and 'status=' not in asked[0]
        page.locator('#sourceEventList .row').first.click()
        page.wait_for_selector('#sourceEventDetail .pane-title', timeout=8000)
        said = page.inner_text('#sourceEventDetail')
        assert '경보 발생 · PRESS-07' in said and '처리 건을 열었습니다' in said and 'INC-1116-01-7362' in said
        assert '{"incident"' not in page.locator('#sourceEventDetail dl.kv').first.inner_text()      # 원문은 접은 「처리 결과 원문」 안에만
        assert page.locator('#sourceEventDetail details.raw', has_text='처리 결과 원문').count() == 1
        assert page.locator('#sourceEventDetail .pane-ic').count() == 0                        # 상세 머리에 아이콘 칸이 없다(5-1)
        assert page.locator('#sourceEventRetry').is_hidden()                                   # 다시 처리는 실패한 접수에만
        page.locator('#sourceEventDetail a.go').click()
        page.wait_for_function("state.tab === 'instances'", timeout=8000)
        assert page.evaluate('location.hash') == '#/instances/my_flow.abc'
        # 거른 상태에 접수가 없으면 「그 상태인 접수가 없다」와 거르기를 푸는 길을 말한다(접수가 아예 없다고 하지 않는다)
        open_screen(page, 'admin')
        page.select_option('#sourceEventStatus', 'FAILED')
        page.wait_for_function("document.querySelector('#sourceEventDetail').innerText.includes('「처리 실패」 상태인 접수가 없습니다')", timeout=8000)
        assert '「전체」로 바꾸면' in page.inner_text('#sourceEventDetail')
    finally:
        close()


def test_실패한_접수는_사유를_적어야_다시_처리를_보내고_보낸_사람은_이_PC의_담당자다():
    """다시 처리 폼은 실패한 접수에만 열린다. 사유 없이 누르면 보내지 않는다(자유 글 담당자 칸은 없다)."""
    failed = dict(RECEIPT, id=9, status='FAILED', error='process 서비스에 닿지 못했습니다', result=None, failures=1)
    sent = []
    # 다시 처리를 받은 뒤에는 서버가 그 접수를 「처리 대기」로 돌려준다
    now = lambda request: dict(failed, status='PENDING') if any(u.endswith('/retry') for m, u, b in sent) else failed      # noqa: E731
    page, close = _page({'/api/source-events/9/retry': {'ok': True}, '/api/source-events/9': now, '/api/source-events': [failed], '/api/inbox/users': [ME]}, sent)
    try:
        open_screen(page, 'admin')
        page.wait_for_function('window.hydInbox && hydInbox.me()', timeout=8000)
        page.locator("#adminList [data-admin='sourceEventsPanel']").click()
        page.locator('#sourceEventList .row').first.click()
        page.wait_for_selector('#sourceEventRetry:not([hidden])', timeout=8000)
        assert 'process 서비스에 닿지 못했습니다' in page.inner_text('#sourceEventDetail') and page.locator('#sourceEventRetry input').count() == 0
        page.locator('#sourceEventRetry button[type=submit]').click()                          # 사유 없이: 필수 칸이 비어 보내지 않는다
        page.wait_for_timeout(400)
        assert not [x for x in sent if x[1].endswith('/retry')] and page.locator('#sourceEventReason:invalid').count() == 1
        page.fill('#sourceEventReason', '연결을 되살린 뒤 다시')
        page.locator('#sourceEventRetry button[type=submit]').click()
        page.wait_for_function("document.querySelector('#sourceEventDetail .pane-title').innerText.includes('처리 대기')", timeout=8000)      # 다시 읽은 상태가 머리에 보이고 폼은 닫힌다
        assert page.locator('#sourceEventRetry').is_hidden()
        assert [b for m, u, b in sent if u.endswith('/retry')] == [{'by': '담당자', 'reason': '연결을 되살린 뒤 다시'}]
    finally:
        close()
