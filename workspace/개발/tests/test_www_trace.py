"""처리 과정 시간 형식(it/portal/www/trace.js fmtMs) — 기다림 · 기한까지 · 걸린 시간이 모두 이 함수를 쓴다."""
import pytest

from www_node import run


@pytest.mark.parametrize('ms, text', [
    (0, '0.1초 미만'), (50, '0.1초'), (400, '0.4초'), (999.6, '1.0초'), (9950, '10초'), (10400, '10초'),
    (59999, '1분'),            # 「60.0 s」가 아니라
    (61000, '1분 1초'),
    (119600, '2분'),           # 「1분 60초」가 아니라(W1-15)
    (3599600, '1시간'),        # 「59분 60초」가 아니라
    (7199999, '2시간'),        # 「1시간 60분」이 아니라
    (5400000, '1시간 30분'),
    (-1, ''), (float('nan'), ''),
])
def test_걸린_시간은_보일_자리로_반올림한_뒤_나누고_단위는_한국어다(ms, text):
    script = "out(hydTrace.fmtMs(DATA === 'nan' ? NaN : DATA))"
    assert run(['ui.js', 'plainWords.js', 'trace.js'], script, 'nan' if ms != ms else ms) == text


@pytest.mark.parametrize('step, status, open_', [
    ({'live': True, 'state': 'idle'}, 'RUNNING', True),
    ({'live': False, 'state': 'pending'}, 'RUNNING', True),       # 멈춘 AI 단계 — 안에 [단계 닫기]
    ({'live': False, 'state': 'fail'}, 'RUNNING', True),          # 실패한 AI 단계 — 안에 [단계 닫기]
    ({'live': False, 'state': 'ask'}, 'RUNNING', True),
    ({'live': False, 'state': 'ok'}, 'RUNNING', False),
    ({'live': False, 'state': 'fail'}, 'COMPLETED', False),       # 끝난 처리 건은 할 일이 없다
], ids=['도는 단계', '멈춘 단계', '실패한 단계', '질문 단계', '끝난 단계', '끝난 처리 건의 실패'])
def test_사람_조치를_기다리는_단계는_기본으로_펼쳐_단추가_보인다(step, status, open_):
    """한바퀴3: 멈춘 AI 단계 카드가 접혀 그 안의 [단계 닫기]가 보이지 않았다(93 실습) — 주석은 「기다리는 단계는 편다」였는데 코드는 도는 단계만 폈다."""
    got = run(['ui.js', 'plainWords.js', 'trace.js'], "out(hydTrace.defaultOpen(DATA.s, {instance: {status: DATA.st}}))", {'s': step, 'st': status})
    assert got is open_
