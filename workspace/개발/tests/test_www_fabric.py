"""데이터 연결 화면(it/portal/www/fabric.js) — 요약 카드가 원천을 읽는 중과 못 읽은 것을 구별하는지. node 에서 실제 화면 파일을 싣는다."""
import pytest

from www_node import run

FILES = ['ui.js', 'plainWords.js', 'fabric.js']
EL = "const el = { innerHTML: '', addEventListener: () => {} };"


# 서버 요청(app.js getJ — 브라우저 밖에서는 실리지 않는다)만 시스템 밖 대역으로 둔다. 화면 코드(fabric.js)는 실제 파일 그대로다.
@pytest.mark.parametrize('request_fn, expect_fail', [
    ('() => new Promise(() => {})', False),                                # 응답 전: 읽는 중
    ("() => Promise.reject(new Error('연결 거부'))", True),                 # 실제로 못 읽음: 확인 실패
])
def test_원천_카드는_응답_전에는_읽는_중이고_못_읽었을_때만_확인_실패다(request_fn, expect_fail):
    """1회차 04 촬영 검토(2026-11-03): 화면을 열 때마다 응답 전 0.1초 동안 「확인 실패」 카드가 보였다."""
    html = run(FILES, EL + "hydFabric.mount(el); for (let i = 0; i < 50; i++) await Promise.resolve(); out(el.innerHTML)",
               prelude=f"globalThis.API = {{ process: '' }}; globalThis.getJ = {request_fn};")
    assert ('확인 실패' in html) == expect_fail, html[:400]
    assert '원천' in html
