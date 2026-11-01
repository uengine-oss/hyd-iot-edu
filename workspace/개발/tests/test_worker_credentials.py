"""워커만 부르는 내부 경로의 공용 확인(procsvc/worker_credentials.py) — 실행기 인증 파일과 살아 있는 점유."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from conftest import start_handover
from procsvc import worker_credentials as wc


@pytest.mark.parametrize('content, says', [(None, '자리(HYD_WORKER_RUNTIME_KEY_FILE)가 설정되지 않았습니다'), ('short', '올바르지 않습니다')],
                         ids=['자리 없음', '짧은 키'])
def test_인증_파일이_없거나_짧으면_503과_까닭(monkeypatch, tmp_path, content, says):
    if content is None:
        monkeypatch.delenv('HYD_WORKER_RUNTIME_KEY_FILE', raising=False)
    else:
        path = tmp_path / 'runtime.key'
        path.write_text(content, encoding='utf8')
        monkeypatch.setenv('HYD_WORKER_RUNTIME_KEY_FILE', str(path))
    with pytest.raises(HTTPException) as refused:
        wc._key()
    assert refused.value.status_code == 503 and says in refused.value.detail


def test_인증_파일이_없는_자리면_준비되지_않았다고_말한다(monkeypatch, tmp_path):
    monkeypatch.setenv('HYD_WORKER_RUNTIME_KEY_FILE', str(tmp_path / 'none.key'))
    with pytest.raises(HTTPException) as refused:
        wc._key()
    assert (refused.value.status_code, refused.value.detail) == (503, '실행 연결 인증 파일이 준비되지 않았습니다')


@pytest.fixture
def claimed(course):
    inst = start_handover(course.rt)
    consumer = 'test-worker:' + uuid.uuid4().hex
    [row] = course.rt.repo.fetch_pending_task('cliagents', consumer, tenant_id='hyd', proc_inst_id=inst['proc_inst_id'])
    return course.rt, row


def test_살아_있는_점유면_그_작업_행을_돌려준다(claimed):
    rt, row = claimed
    assert wc._claim(rt, {'tenant_id': 'hyd', 'todo_id': row['id'], 'consumer': row['consumer']})['id'] == row['id']


@pytest.mark.parametrize('change, status', [
    ({'tenant_id': 'other'}, 403),
    ({'consumer': 'someone-else'}, 409),
    ({'todo_id': str(uuid.uuid4())}, 409),
], ids=['다른 교육 공간', '다른 실행기', '없는 작업'])
def test_내_점유가_아니면_거절한다(claimed, change, status):
    rt, row = claimed
    with pytest.raises(HTTPException) as refused:
        wc._claim(rt, dict({'tenant_id': 'hyd', 'todo_id': row['id'], 'consumer': row['consumer']}, **change))
    assert refused.value.status_code == status


def test_임대가_끝난_점유는_거절한다(claimed):
    rt, row = claimed
    with rt.repo._conn() as c:                                # 준비: 임대를 1초 전에 끝난 것으로(update_workitem 은 임대 칸을 쓰지 않는다)
        c.execute('update todolist set lease_until = %s where id = %s', (datetime.now(timezone.utc) - timedelta(seconds=1), row['id']))
    assert rt.repo.get_workitem(row['id'])['lease_until'] is not None
    with pytest.raises(HTTPException) as refused:
        wc._claim(rt, {'tenant_id': 'hyd', 'todo_id': row['id'], 'consumer': row['consumer']})
    assert (refused.value.status_code, refused.value.detail) == (409, '현재 실행 단계의 임대 시간이 만료되었습니다')
