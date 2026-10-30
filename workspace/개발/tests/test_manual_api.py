"""문서 넣기(procsvc/manual_api.py `POST /api/kg/manuals/preview`) — 받을 수 없는 파일은 그래프 · 저장 전에 학생이 읽을 까닭으로 거절되는가.

수업 단계는 제공 문서(내용을 고치지 않은 원문)만 받는다 — 허용 밖 문서는 형식과 상관없이 저장 전에 거절된다. PBL 단계는 어느 문서나
받되 형식 · 크기 · 글자 검사는 그대로다. 실제 보관소(ManualSources, 임시 파일)와 실제 수업 규칙을 쓰고, 거절 경로는 그래프에 닿지 않아야
하므로 그래프 연결은 불리면 실패한다. 받아들인 제공 문서가 그래프 미리보기까지 가는 길은 시작 7단계 · 수업 한 바퀴(실제 스택)가 본다.
"""
import base64

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from procsvc import course_policy as cp, manual_api
from procsvc.manual_approved_cache import ApprovedExtractions
from procsvc.manual_sources import MAX_BYTES, ManualSources

def b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode()


@pytest.fixture
def portal(tmp_path):
    def build(phase):
        archive = ManualSources(tmp_path / 'manuals.sqlite3')
        app = FastAPI()
        app.state.course = cp.Policy(cp.Phase(phase))

        def no_graph():
            raise AssertionError('거절할 파일인데 그래프까지 갔다')
        manual_api.register(app, archive_factory=lambda: archive, driver_factory=no_graph, tenant='hyd', audit=lambda *a, **k: None,
                            runtime_factory=lambda: None, approved_cache=ApprovedExtractions())
        return TestClient(app), archive
    return build


NOT_PROVIDED = '# 우리 공장 설비 매뉴얼\n\n1. 펌프를 멈춘다.\n'.encode()
BIG = b'#' * (MAX_BYTES + 1)


@pytest.mark.parametrize('phase, body, status, says', [
    ('course', dict(filename='my-manual.md', data=b64(NOT_PROVIDED)), 403, '강사가 제공한 수업 문서'),   # 허용 밖 문서
    ('course', dict(filename='manual.docx', data=b64(b'PK\x03\x04 word')), 403, '강사가 제공한 수업 문서'),  # 다른 형식도 먼저 허용 밖
    ('course', dict(filename='big.md', data=b64(BIG)), 400, '30 MiB 이하'),                             # 한도를 넘는 큰 파일
    ('course', dict(filename='empty.md', data=''), 400, '빈 파일'),                                     # 빈 파일
    ('course', dict(filename='x.md', data='이건 base64 가 아님!'), 400, 'base64'),                       # 깨진 전송
    ('pbl', dict(filename='big.md', data=b64(BIG)), 400, '30 MiB 이하'),
    ('pbl', dict(filename='manual.docx', data=b64(b'PK\x03\x04 word')), 400, 'Markdown, TXT, PDF'),     # 다른 형식
    ('pbl', dict(filename='manual.pdf', data=b64(b'not a pdf at all')), 400, 'PDF 파일 서명'),           # 깨진 PDF
    ('pbl', dict(filename='notes.txt', data=b64(b'\xff\xfe\xfa\xfb\x81\xff')), 400, '해독할 수 없습니다'),  # 깨진 글자
    ('pbl', dict(filename='notes.txt', data=b64('설비\x00점검'.encode())), 400, 'NUL'),                  # 바이너리 섞임
    ('pbl', dict(filename='blank.md', data=b64(b'   \n\n  ')), 400, '비어 있거나'),                     # 내용 없는 글
])
def test_받을_수_없는_문서는_그래프와_저장_전에_까닭과_함께_거절된다(portal, phase, body, status, says):
    client, archive = portal(phase)
    response = client.post('/api/kg/manuals/preview', json=body)
    assert response.status_code == status, response.text
    assert says in response.json()['detail']
    assert archive.list('hyd')['total'] == 0

