"""판단 채점 화면(it/portal/www/evaluation.js) — 화면이 학생에게 어느 경로가 AI 인지 사실대로 말한다.

실제 index.html · evaluation.js 를 실제 브라우저(Playwright Chromium)로 연다. 브라우저 밖의 process 응답(정답표 · 실행 목록 · 경로 안내)만
이 시험이 준다(꼴은 procsvc eval_api — 경로 안내 문장은 서버 judgment_eval.PATH_NOTES 그대로)."""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from conftest import WWW, Served
from procsvc import judgment_eval


def test_판단_채점_화면은_AI가_판단하는_경로가_지난_처리_건_하나라고_말한다():
    """J4 D3(2026-11-01): 부제가 「AI 판단을 대어 점수를 낸다」였는데 기본 경로(규칙 판단)와 읽기 평가는 AI 모델 없이 돈다."""
    from playwright.sync_api import sync_playwright
    app = FastAPI()
    app.mount('/', StaticFiles(directory=WWW, html=True))
    served = Served(app)

    def answer(route):
        url = route.request.url.split('?')[0]
        if url.endswith('/api/eval/paths'):
            return route.fulfill(json={'paths': [{'key': k, 'note': v} for k, v in judgment_eval.PATH_NOTES.items()]})
        if url.endswith('/api/eval/items') or url.endswith('/api/eval/runs'):
            return route.fulfill(json=[])
        return route.fulfill(json={})
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page()
            page.route('**/svc/**', answer)
            page.goto(served.url + '/index.html')
            page.locator("button[data-tab='eval']").first.click()
            page.wait_for_function("[...document.querySelectorAll('.card-sub')].some(e => e.textContent.includes('정답표'))", timeout=15000)
            sub = next(t for t in page.locator('.card-sub').all_inner_texts() if '정답표' in t)
            b.close()
    finally:
        served.close()
    assert 'AI가 판단하는 것은 「지난 처리 건」 하나' in sub and 'AI 판단을 대어' not in sub, sub
    assert 'AI 모델 없이' in judgment_eval.PATH_NOTES['evaluate'] and 'AI 모델 없이' in judgment_eval.PATH_NOTES['decide']
