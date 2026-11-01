"""작업함 · 알림 API(procsvc/inbox_api.py) — 사람 사용자만(아니면 404), 알림 id 형식 검사, 읽음 표시 뒤 안 읽은 수. 실제 process 앱(world.api)."""
import uuid

import pytest

from conftest import OPERATOR


def test_사람_사용자의_작업함과_업무분장을_읽는다(world):
    status, view = world.api('GET', f"/api/inbox?user_id={OPERATOR['by']}")
    assert status == 200 and view['user']['id'] == OPERATOR['by'] and 'role:operator' in view['roles']
    status, people = world.api('GET', '/api/inbox/users')
    assert status == 200 and any(p['id'] == OPERATOR['by'] for p in people)


@pytest.mark.parametrize('path', ['/api/inbox?user_id=user:nobody', '/api/inbox/notifications?user_id=role:operator',
                                  '/api/inbox/notifications/unread-count?user_id=sys:agent'],
                         ids=['없는 사람', '역할 id', '시스템 id'])
def test_사람_사용자가_아니면_404다(world, path):
    status, body = world.api('GET', path)
    assert status == 404 and '사람 사용자' in body['detail']


def test_알림을_읽음으로_표시하면_안_읽은_수가_줄어든다(world):
    world.start_cooling()                                     # 운전원 승인 차례 → 운전원에게 알림
    status, notes = world.api('GET', f"/api/inbox/notifications?user_id={OPERATOR['by']}&unread=true")
    assert status == 200 and notes
    status, out = world.api('POST', '/api/inbox/notifications/read', {'user_id': OPERATOR['by'], 'ids': [notes[0]['id']]})
    assert status == 200 and out['marked'] == 1
    status, count = world.api('GET', f"/api/inbox/notifications/unread-count?user_id={OPERATOR['by']}")
    assert count['unread'] == out['unread'] == len(notes) - 1


def test_알림_id_형식이_아니면_400이다(world):
    status, body = world.api('POST', '/api/inbox/notifications/read', {'user_id': OPERATOR['by'], 'ids': ['not-a-uuid']})
    assert status == 400 and '알림 id' in body['detail']


def test_없는_작업의_배정_이력은_404다(world):
    status, _ = world.api('GET', f'/api/todolist/{uuid.uuid4()}/assignments')
    assert status == 404
