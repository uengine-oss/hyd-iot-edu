"""포털의 수업 단계 표(it/portal/www/courseAccess.js) — 막힌 행동의 단추는 초점이 가는 채로 막혀 있고, 까닭은 늘 붙어 있지 않다. 학생이 그 단추를
누르거나 Enter 를 칠 때만 동작이 막히고(요청이 나가지 않는다) 단추 바로 뒤 한 줄에 서버가 준 문장이 보인다(문장 사본 없음 — W2-08 · W3-07, CLAUDE.md 5절
「학생이 막힌 행동을 하려 할 때만 그 자리에서 까닭을 말한다」 — 사용자 2026-11-20). 메뉴 줄 아래의 줄은 PBL 기간과 그것이 끝난 때만 있다(PBL 선언이
없던 때에는 없다 — 사용자 2026-11-20 「저게뭐임?」 · 「굳이 저런게 있으면안되는데」). PBL 기한 시각에 표를 다시 읽어 끝난 것을 보이고(W2-09), 표를 못 읽으면
「단계 정보 읽기 실패」를 보이고 잠그지 않는다(G5b-22).
실제 포털 파일(it/portal/www, nginx 와 같은 /svc/process 경로)과 실제 수업 경계(course_policy.mount — 판정 · 시계는 서버)를 이 PC 포트에 띄우고
실제 브라우저(Playwright Chromium)로 index.html 을 연다. 다른 서비스(/svc/agent 등)는 띄우지 않는다 — 그 화면의 실패는 이 판정과 무관하다."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from conftest import WWW, Served
from procsvc import course_policy as cp



def portal(phase):
    process = FastAPI()
    cp.mount(process, runtime_factory=lambda: None, phase=phase)
    app = FastAPI()
    app.mount('/svc/process', process)
    app.mount('/', StaticFiles(directory=WWW, html=True))
    return Served(app)


@pytest.fixture(scope='module')
def browser():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture
def page(browser):
    pg = browser.new_page()
    yield pg
    pg.close()


def opened(page, served):
    page.goto(served.url + '/index.html')
    page.wait_for_function('window.hydCourseAccess && (window.hydCourseAccess.access || window.hydCourseAccess.error)', timeout=15000)
    return page


def test_수업_단계의_막힌_까닭은_서버_문장_그대로다(page):
    served = portal(cp.Phase('course'))
    try:
        opened(page, served)
        got = page.evaluate("""() => ({assign: hydCourseAccess.assignBlocked('c3_cooling'), start: hydCourseAccess.startBlocked('my_flow'),
            importing: hydCourseAccess.importBlocked('my_flow'), document: hydCourseAccess.reason('document'),
            golden: hydCourseAccess.blocked('documents.golden'), open: hydCourseAccess.assignBlocked('ShiftHandover'),
            question: hydCourseAccess.questionMaxChars, editable: hydCourseAccess.handoverEditable})""")
        reasons = cp.Policy.REASONS
        assert got == {'assign': reasons['assign'], 'start': reasons['start'], 'importing': reasons['import_flow'], 'document': reasons['document'],
                       'golden': cp.Policy.ACTIONS['documents.golden'], 'open': '', 'question': cp.question_max_chars(),
                       'editable': {'flow_name': True, 'agent_tasks': list(cp.HANDOVER_AGENT_TASKS)}}
        # PBL 선언이 없던 때에는 메뉴 줄 아래 줄이 없다 — 늘 같은 그 상태는 학생이 읽을 것이 없고, 막힌 까닭은 그 단추를 누를 때 나온다(아래 마지막 시험)
        assert page.inner_text('#courseStatus') == '' and not page.is_visible('#courseStatus')
        assert page.get_attribute('#courseStatus', 'title') is None
    finally:
        served.close()


def test_켜_둔_화면도_PBL_기한이_지나면_다시_읽어_PBL_기간이_끝난_것을_보인다(page):
    until = datetime.now(timezone.utc) + timedelta(seconds=3)
    served = portal(cp.Phase('pbl', note='1기 PBL', expires=until.isoformat()))
    try:
        opened(page, served)
        assert page.evaluate('hydCourseAccess.access.phase') == 'pbl' and page.inner_text('#courseStatus').strip().startswith('PBL 기간 · ')
        page.wait_for_function("hydCourseAccess.access && hydCourseAccess.access.phase === 'course'", timeout=15000)
        line = page.inner_text('#courseStatus')
        assert 'PBL 기간이 끝났습니다' in line and '막힌 행동' not in line and '단계' not in line, line      # 끝났다는 사실만 — 막힌 행동을 늘어놓지 않는다
        assert page.evaluate("hydCourseAccess.assignBlocked('c3_cooling')") == cp.Policy.REASONS['assign']
    finally:
        served.close()


def test_표를_못_읽으면_잠그지_않고_수업_단계_정보_읽기_실패와_다시_시도를_보인다(page):
    served = portal(cp.Phase('course'))
    try:
        page.route('**/svc/process/api/course-access', lambda route: route.abort('connectionrefused'))
        opened(page, served)
        text = page.inner_text('#courseStatus')
        assert '단계 정보 읽기 실패' in text and '다시 시도' in text and '범위' not in text and '수업' not in text
        assert page.evaluate("hydCourseAccess.assignBlocked('c3_cooling')") == ''        # 모르면 막지 않는다(서버가 판정)
    finally:
        served.close()


def test_막힌_단추는_초점이_가고_누를_때만_요청_없이_그_뒤에_까닭_한_줄이_보인다(page):
    """W3-07: 꺼진(disabled) 단추는 키보드 · 터치로 초점이 가지 않아 까닭을 읽을 길이 없었고, 그래서 까닭 줄을 늘 붙여 두었다. 지금은 단추를
    aria-disabled 로 두어 초점이 가게 하고, 까닭은 학생이 그 단추를 누르거나 Enter 를 칠 때만 그 뒤 한 줄로 보인다(다시 눌러도 · 다시 맞춰도 한 줄).
    막힌 단추의 동작(화면 모듈의 처리기 · 서버 요청)은 일어나지 않고, 열린 단추는 그대로 동작한다."""
    served = portal(cp.Phase('course'))
    try:
        opened(page, served)
        sent = []
        page.on('request', lambda r: sent.append(r.url) if '/api/probe' in r.url else None)
        page.evaluate("""() => {
            const box = document.createElement('div'); box.id = 'probe';
            box.innerHTML = `<button id="g" type="button" class="btn"${hydCourseAccess.attrs('documents.golden')}>묻기</button><button id="o" type="button" class="btn"${hydCourseAccess.attrs('no.such')}>열림</button>`;
            document.body.prepend(box);
            window.ran = [];
            for (const b of box.querySelectorAll('button')) b.addEventListener('click', () => { window.ran.push(b.id); fetch('/svc/process/api/probe/' + b.id).catch(() => {}); });
            hydCourseAccess.apply(box); hydCourseAccess.apply(box);
        }""")
        state = "() => ({lines: [...document.querySelectorAll('#probe [data-course-why]')].map(n => [n.previousElementSibling.id, n.textContent]), ran: window.ran, " \
                "g: [document.querySelector('#g').disabled, document.querySelector('#g').getAttribute('aria-disabled'), document.querySelector('#g').title], " \
                "o: [document.querySelector('#o').disabled, document.querySelector('#o').getAttribute('aria-disabled')], focus: document.activeElement.id})"
        why = cp.Policy.ACTIONS['documents.golden']
        # 누르기 전: 막힌 단추는 꺼진(disabled) 것이 아니라 aria-disabled 이고, 까닭 줄도 도움말(title)도 없다
        assert page.evaluate(state) == {'lines': [], 'ran': [], 'g': [False, 'true', ''], 'o': [False, None], 'focus': ''}
        page.focus('#g')
        page.keyboard.press('Enter')                     # 키보드: 초점이 가고, Enter 가 동작 대신 까닭을 낸다
        assert page.evaluate(state) == {'lines': [['g', why]], 'ran': [], 'g': [False, 'true', ''], 'o': [False, None], 'focus': 'g'}
        page.click('#g', force=True)                     # 마우스로 다시 눌러도 한 줄(force: Playwright 는 aria-disabled 단추를 누를 수 있게 되기를 기다린다 — 실제 마우스 누름은 그대로 간다)
        page.evaluate('hydCourseAccess.apply(document)')
        assert page.evaluate(state)['lines'] == [['g', why]] and page.evaluate('window.ran') == []
        assert page.get_attribute('#probe [data-course-why]', 'role') == 'status'      # 화면 낭독기도 그때 읽는다
        page.click('#o')                                 # 열린 단추는 그대로 동작한다
        page.wait_for_function("window.ran.length === 1")
        page.wait_for_timeout(200)
        assert page.evaluate('window.ran') == ['o'] and [u.rsplit('/', 1)[1] for u in sent] == ['o'], sent
    finally:
        served.close()
