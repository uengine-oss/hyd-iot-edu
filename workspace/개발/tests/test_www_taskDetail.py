"""단계 상세(it/portal/www/taskDetail.js) — 「지금:」 줄."""
import pytest

from www_node import run

FILES = ['ui.js', 'plainWords.js', 'trace.js', 'instanceSteps.js', 'approvalCard.js', 'taskDetail.js']


@pytest.mark.parametrize('label, status, shown', [
    ('사람이 닫음', 'COMPLETED', '사람이 닫음'),        # 기술 끝 이름은 서버 end_label(P1-08 — 화면이 정의 · 상태에서 지어 「완료」로 보였다)
    ('정상 종결', 'COMPLETED', '정상 종결'),
    (None, 'CANCELLED', '취소'),                         # 서버가 이름을 주지 않으면 상태 이름
])
def test_끝난_처리_건의_지금_줄은_서버가_준_끝_이름을_보인다(label, status, shown):
    view = {'instance': {'proc_inst_id': 'c.1', 'status': status, 'end_event': 'E', 'end_label': label, 'variables_data': []},
            'definition': {'events': [{'id': 'E', 'name': '끝'}], 'activities': []}, 'workitems': [], 'events': []}
    got = run(FILES, r"out(hydTaskDetail.nowHtml(DATA).replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim())", view)
    assert got == f'끝 {shown}', got
