"""업무분장 · 승인자 · 내 작업함(procsvc/inbox.py) — 역할에 묶인 단계는 역할 그대로 두고(구성원이 한 명이어도 사람으로 바꿔 적지 않는다),
승인은 포털의 「나」(사람 사용자)이고 그 역할 구성원일 때만(P2-17 — 이름만 적은 승인은 받지 않음), 작업함은 열린 일을 자르지 않는다(P2-18).
실제 process(world)의 저장소 · 시드 사람(담당자 user:me 한 명 — 모든 역할의 구성원)으로 판정한다."""
import uuid

import pytest

from conftest import OPERATOR, start_handover
from procsvc import inbox


@pytest.fixture
def repo(world):
    return world.rt.repo


def test_역할에_사람이_한_명이어도_단계는_역할_그대로_두고_그_구성원이_처리한다(repo):
    """2026-11-13: 구성원이 한 명이면 그 사람(user:*)으로 바꿔 적던 규칙을 없앴다 — 화면과 기록이 「어느 역할의 일인가」를 보여야 한다."""
    members = inbox.members_of(repo, 'hyd', OPERATOR['role'])
    assert members == [OPERATOR['by']], '시드의 운전원 역할 구성원은 담당자 한 명'
    assert inbox.resolve(repo, 'hyd', OPERATOR['role']) == {'kind': 'role', 'user_id': OPERATOR['role'], 'members': members}
    assert inbox.notification_targets(repo, 'hyd', OPERATOR['role']) == members, '알림은 역할의 구성원에게 간다'


@pytest.mark.parametrize('endpoint, kind', [(OPERATOR['by'], 'person'), ('role:nobody-here', 'none'), (None, 'none'), ('sys:agent', 'none')])
def test_사람_역할_없는_역할_시스템은_정해진_대로_해석한다(repo, endpoint, kind):
    assert inbox.resolve(repo, 'hyd', endpoint)['kind'] == kind


@pytest.mark.parametrize('by', ['담당자', '승인자', '', None, 'role:operator'], ids=['이름만', '자유 글', '빈 값', '없음', '역할 id'])
def test_사람_사용자가_아닌_승인자는_받지_않는다(repo, by):
    """P2-17: 옛 「자유 입력 승인자」 갈래는 아무 확인 없이 그 글자를 승인자로 썼다."""
    with pytest.raises(PermissionError) as refused:
        inbox.check_actor(repo, 'hyd', by, 'role:operator')
    assert str(refused.value) == inbox.NOT_A_PERSON
    with pytest.raises(PermissionError):
        inbox.person_name(repo, 'hyd', by)


def test_역할_구성원인_사람은_그_역할로_승인하고_이름이_보고에_실린다(repo):
    assert inbox.check_actor(repo, 'hyd', OPERATOR['by'], OPERATOR['role']) == OPERATOR['by']
    assert inbox.person_name(repo, 'hyd', OPERATOR['by']) == '담당자'


def test_그_역할이_아닌_사람은_내_역할을_보여_주며_거절한다(repo):
    """담당자는 시드의 모든 역할의 구성원이다 — 구성원이 아닌 역할은 업무분장에 없는 역할로 잰다."""
    with pytest.raises(PermissionError, match='역할이 아니어서') as refused:
        inbox.check_actor(repo, 'hyd', OPERATOR['by'], 'role:nobody-here')
    assert '내 역할: ' in str(refused.value) and '내 역할: 없음' not in str(refused.value)


def test_없는_사람_사용자는_거절한다(repo):
    with pytest.raises(PermissionError, match='없는 사람'):
        inbox.check_actor(repo, 'hyd', 'user:nobody', 'role:operator')


def test_없는_사람의_작업함은_LookupError다(world):
    with pytest.raises(LookupError):
        inbox.inbox_view(world.rt, 'user:nobody')


def test_운전원의_작업함에_냉각_승인_차례가_보이고_단계로_가는_링크가_있다(world):
    alert, pid, decision = world.start_cooling()
    view = inbox.inbox_view(world.rt, OPERATOR['by'])
    mine = [t for t in view['tasks'] if t['proc_inst_id'] == pid]
    assert [t['activity_id'] for t in mine] == ['T_approve'] and mine[0]['kind'] == 'select'
    assert mine[0]['link'] == '#' + inbox.task_url(pid, mine[0]['id'])


def test_작업함은_열린_일이_많아도_오래된_내_차례를_자르지_않는다(world):
    """P2-18: 열린 작업을 최신 500개로 잘라 오래된 내 차례가 말없이 사라졌다."""
    alert, pid, decision = world.start_cooling()
    world.clock.advance(1)                       # 뒤에 연 일이 더 새 일이다(최신 순으로 자르면 내 차례가 빠진다)
    for _ in range(501):
        start_handover(world.rt)
    assert len(world.rt.repo.list_workitems(status='IN_PROGRESS', limit=None, tenant_id='hyd')) > 501
    view = inbox.inbox_view(world.rt, OPERATOR['by'])
    assert any(t['proc_inst_id'] == pid and t['activity_id'] == 'T_approve' for t in view['tasks'])


def test_알림_링크는_처리_건_작업을_가리키고_없는_작업이면_까닭을_단다(world):
    alert, pid, decision = world.start_cooling()
    row = world.row(pid, 'T_approve', 'IN_PROGRESS')
    notes = inbox.with_links(world.rt.repo, [{'url': f'/instances/{pid}'}, {'url': f'/todolist/{row["id"]}'},
                                            {'url': f'/todolist/{uuid.uuid4()}'}, {'url': 'mailto:x'}])
    assert notes[0]['link'] == f'#/instances/{pid}' and notes[1]['link'] == '#' + inbox.task_url(pid, row['id'])
    assert notes[2]['link'] is None and notes[2]['link_error'] and notes[3]['link'] is None


def test_알림_대상은_나와_내_역할이다(repo):
    ids = inbox.user_ids_for(repo, 'hyd', OPERATOR['by'])
    assert OPERATOR['by'] in ids and 'role:operator' in ids


def test_업무분장_표는_역할마다_구성원을_보인다(repo):
    board = inbox.assignment_board(repo, 'hyd')
    operator = next(r for r in board['roles'] if r['id'] == 'role:operator')
    assert OPERATOR['by'] in operator['members']
