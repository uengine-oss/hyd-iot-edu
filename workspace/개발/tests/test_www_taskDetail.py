"""단계 상세(it/portal/www/taskDetail.js) — 옆 판의 「받은 값 · 넘긴 값」 보기가 그리는 값."""
from www_node import run

FILES = ['ui.js', 'plainWords.js', 'trace.js', 'instanceSteps.js', 'approvalCard.js', 'taskDetail.js']


def test_원인_표의_기준값과_관측값은_근거가_읽은_시계열의_단위를_붙인다():
    """독립 검증(2026-11-02): 사건 상세(app.js)에는 단위를 붙였지만 단계 상세의 원인 표는 「냉각 효율 저하 < 70 · 관측 46.20」으로 단위가 없었다."""
    guide = {'causes': [{'id': 'cause:cooler-fin-fouling', 'name': '쿨러 핀 오염', 'score': 0.6, 'prior': 0.6,
                         'evidence': [{'id': 'evd:ce-low', 'name': '냉각 효율 저하', 'tag': 'CE', 'expect': 'lt', 'threshold': 70,
                                       'value': 46.2, 'passed': True, 'status': 'PASS', 'weight': 1}]}]}
    got = run(FILES, r"out(hydTaskDetail.valueHtml('guide_card', DATA, {}).replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' '))", guide)
    assert '70 %' in got and '46.2 %' in got, got
