"""AI 판단 보류 · 다시 평가(procsvc/task_deferral.py) — 실제 PostgreSQL 의 처리 건 · 작업 행에 쓴다(같은 요청 id 는 한 번)."""
import json
import uuid

import pytest

from conftest import new_database
from procsvc import procdb, task_deferral

TENANT = 'hyd'
ASSESSMENT = {'status': 'UNKNOWN', 'reason': '재고 사실을 읽지 못했습니다', 'evidence': {'tool': 'erp', 'error': '시간 초과'}}


@pytest.fixture(scope='module')
def repo(pg_dsn):
    with new_database(pg_dsn, schema=True) as dsn:
        yield procdb.PgRepo(dsn)


def _task(repo, *, status='RUNNING', agent=True, generation=0):
    pid = f'p.{uuid.uuid4()}'
    repo.insert_instance({'proc_inst_id': pid, 'proc_def_id': 'p', 'proc_def_version': '1', 'tenant_id': TENANT, 'status': status,
                          'rework_generation': generation, 'variables_data': [], 'start_event_id': uuid.uuid4().hex})
    wid = str(uuid.uuid4())
    repo.insert_workitems([{'id': wid, 'proc_inst_id': pid, 'tenant_id': TENANT, 'proc_def_id': 'p', 'version': '1', 'activity_id': 'T_agent',
                            'status': 'IN_PROGRESS', 'draft_status': 'STARTED', 'consumer': 'worker-1', 'generation': 0,
                            'agent_mode': 'COMPLETE' if agent else None, 'agent_orch': 'cliagents' if agent else None,
                            'start_date': '2026-10-30T09:00:00.000Z'}])
    return wid


def _defer(repo, wid, request='REQ-1', assessment=ASSESSMENT, consumer='worker-1'):
    return task_deferral.defer(repo, TENANT, wid, expected_consumer=consumer, request_id=request, assessment=assessment)


def test_보류는_작업을_멈춤으로_두고_근거와_함께_기록하며_같은_요청은_한_번만_한다(repo):
    wid = _task(repo)
    receipt = _defer(repo, wid)
    row = repo.get_workitem(wid)
    assert (row['status'], row['consumer'], row['draft']['_deferral']['reason']) == ('PENDING', None, ASSESSMENT['reason'])
    assert _defer(repo, wid) == receipt, '같은 요청 id · 같은 내용이면 같은 영수증'
    with pytest.raises(ValueError, match='같은 요청 id 로 다른 내용'):
        _defer(repo, wid, assessment=dict(ASSESSMENT, reason='다른 사유'))


@pytest.mark.parametrize('prepare, words', [
    (lambda repo: _task(repo, status='COMPLETED'), '세대가 아닙니다'),
    (lambda repo: _task(repo, generation=1), '세대가 아닙니다'),                   # 다시 수행된 처리 건의 옛 세대 작업
    (lambda repo: _task(repo, agent=False), 'AI 단계만'),
])
def test_끝났거나_옛_세대이거나_사람_단계면_보류를_받지_않는다(repo, prepare, words):
    with pytest.raises(ValueError, match=words):
        _defer(repo, prepare(repo))


def test_그_작업을_집은_실행이_아니면_보류를_받지_않는다(repo):
    with pytest.raises(ValueError, match='더 이상 이 단계를 맡고 있지 않습니다'):
        _defer(repo, _task(repo), consumer='late-worker')


@pytest.mark.parametrize('value, words', [
    ({'status': 'UNKNOWN', 'reason': 'x'}, '세 칸만'),
    ({'status': 'MAYBE', 'reason': 'x', 'evidence': {}}, 'UNKNOWN'),
    ({'status': 'UNKNOWN', 'reason': '  ', 'evidence': {}}, '사유'),
    ({'status': 'UNKNOWN', 'reason': 'x', 'evidence': []}, '객체'),
    ({'status': 'UNKNOWN', 'reason': 'x', 'evidence': {'n': float('nan')}}, '유한한 수'),
    ({'status': 'UNKNOWN', 'reason': 'x', 'evidence': {'blob': '가' * 50_000}}, '128 KiB'),
])
def test_보류_모양이_틀리면_쉬운_말로_거절한다(value, words):
    """P1-10: 전에는 「deferral requires only status, reason and evidence」 같은 영문이었다."""
    with pytest.raises(ValueError, match=words):
        task_deferral.validate(value)


@pytest.mark.parametrize('text, result', [
    (json.dumps({'__deferred__': ASSESSMENT}, ensure_ascii=False), ASSESSMENT),
    ('```json\n' + json.dumps({'__deferred__': ASSESSMENT}, ensure_ascii=False) + '\n```', ASSESSMENT),   # CLI 가 감싼 울타리
    (json.dumps({'decision_id': 'D-1'}), None),                                                          # 업무 결과 — 보류 아님
    ('설명 ' + json.dumps({'__deferred__': ASSESSMENT}), None),                                           # 글이 섞이면 보류 아님
])
def test_마지막_메시지_전체가_보류_객체일_때만_보류로_읽는다(text, result):
    assert task_deferral.control(text) == result


def test_보류와_업무_결과를_섞으면_거절한다():
    with pytest.raises(ValueError, match='섞을 수 없습니다'):
        task_deferral.control(json.dumps({'__deferred__': ASSESSMENT, 'decision_id': 'D-1'}))


def test_다시_평가는_그_보류를_기다리는_작업만_새_실행으로_되돌리고_같은_요청은_한_번만_한다(repo):
    wid = _task(repo)
    receipt = _defer(repo, wid)
    with pytest.raises(ValueError, match='그 보류에 대한 다시 평가'):
        task_deferral.reassess(repo, TENANT, wid, deferral_id='other', request_id='R-1', by='user:kim-op', reason='새 근거')
    done = task_deferral.reassess(repo, TENANT, wid, deferral_id=receipt['id'], request_id='R-1', by='user:kim-op', reason='재고 다시 확인')
    row = repo.get_workitem(wid)
    assert (row['status'], row['draft'], row['draft_status'], row['consumer']) == ('IN_PROGRESS', None, None, None), '워커가 새로 집는다'
    assert '재고 다시 확인' in row['feedback']['text'] and done['status'] == 'QUEUED'
    assert task_deferral.reassess(repo, TENANT, wid, deferral_id=receipt['id'], request_id='R-1', by='user:kim-op',
                                  reason='재고 다시 확인') == done


def test_없는_작업이면_작업_id_로_KeyError(repo):
    with pytest.raises(KeyError):
        _defer(repo, str(uuid.uuid4()))
