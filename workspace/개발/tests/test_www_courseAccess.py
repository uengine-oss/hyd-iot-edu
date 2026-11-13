"""포털의 수업 단계 표(it/portal/www/courseAccess.js) — 막힌 까닭은 서버가 준 문장만 보이고(문장 사본 없음 — W2-08 · W3-07), PBL 기한 시각에
표를 다시 읽어 수업 단계로 돌아온 것을 보이며(W2-09), 표를 못 읽으면 「수업 단계 정보 읽기 실패」를 보이고 잠그지 않는다(G5b-22).
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
        assert '지금 단계: 수업' in page.inner_text('#courseStatus')
    finally:
        served.close()


def test_켜_둔_화면도_PBL_기한이_지나면_다시_읽어_수업_단계로_돌아온_것을_보인다(page):
    until = datetime.now(timezone.utc) + timedelta(seconds=3)
    served = portal(cp.Phase('pbl', note='1기 PBL', expires=until.isoformat()))
    try:
        opened(page, served)
        assert page.evaluate('hydCourseAccess.access.phase') == 'pbl' and 'PBL' in page.inner_text('#courseStatus')
        page.wait_for_function("hydCourseAccess.access && hydCourseAccess.access.phase === 'course'", timeout=15000)
        assert 'PBL 기한 지남' in page.inner_text('#courseStatus')
        assert page.evaluate("hydCourseAccess.assignBlocked('c3_cooling')") == cp.Policy.REASONS['assign']
    finally:
        served.close()


def test_표를_못_읽으면_잠그지_않고_수업_단계_정보_읽기_실패와_다시_시도를_보인다(page):
    served = portal(cp.Phase('course'))
    try:
        page.route('**/svc/process/api/course-access', lambda route: route.abort('connectionrefused'))
        opened(page, served)
        text = page.inner_text('#courseStatus')
        assert '수업 단계 정보 읽기 실패' in text and '다시 시도' in text and '범위' not in text
        assert page.evaluate("hydCourseAccess.assignBlocked('c3_cooling')") == ''        # 모르면 막지 않는다(서버가 판정)
    finally:
        served.close()


def test_막힌_단추_뒤에는_까닭_한_줄이_하나만_보인다(page):
    """W3-07: 꺼진 단추는 키보드 · 터치로 초점이 가지 않아 title 의 까닭을 못 읽었다 — 단추 바로 뒤 한 줄로 보인다(다시 맞춰도 한 줄)."""
    served = portal(cp.Phase('course'))
    try:
        opened(page, served)
        lines = page.evaluate("""() => {
            const box = document.createElement('div');
            box.innerHTML = `<button id="g"${hydCourseAccess.attrs('documents.golden')}>묻기</button><button id="o"${hydCourseAccess.attrs('no.such')}>열림</button>`;
            document.body.append(box);
            hydCourseAccess.apply(box); hydCourseAccess.apply(box);
            return {lines: [...box.querySelectorAll('[data-course-why]')].map(n => [n.previousElementSibling.id, n.textContent]),
                    disabled: [box.querySelector('#g').disabled, box.querySelector('#o').disabled]};
        }""")
        assert lines == {'lines': [['g', cp.Policy.ACTIONS['documents.golden']]], 'disabled': [True, False]}
    finally:
        served.close()
