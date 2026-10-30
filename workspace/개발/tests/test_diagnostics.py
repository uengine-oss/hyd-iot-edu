"""비밀값 가림 한 곳(worker/diagnostics.py) — 워커가 남기는 모든 것은 남기기 직전 여기를 지난다(#18: 가림 구현 세 벌 → 하나)."""
import json

import pytest

from procsvc.mcp_secrets import REDACTED
from worker import diagnostics

TOKEN = 'HydModel eyJ0ZW5hbnQiOiJoeWQifQ.0123456789abcdef'
QUOTED = 'pa"ss\\word-123'


@pytest.mark.parametrize('value, hidden', [
    (f'헤더 {TOKEN}', f'헤더 {REDACTED}'),
    ('토큰 조각만 eyJ0ZW5hbnQiOiJoeWQifQ.0123456789abcdef 이 나와도', f'토큰 조각만 {REDACTED} 이 나와도'),
    (json.dumps({'password': QUOTED}), json.dumps({'password': REDACTED}, ensure_ascii=False)),
    ({'nested': [QUOTED, {'k': f'x{QUOTED}y'}]}, {'nested': [REDACTED, {'k': f'x{REDACTED}y'}]}),
    ('비밀이 없는 글', '비밀이 없는 글'),
], ids=['값 그대로', '「HydModel <토큰>」의 토큰 조각', 'JSON 안에 이스케이프된 꼴', '객체 안 깊은 곳', '비밀 없음'])
def test_알려진_비밀값은_어떤_꼴로_실려도_가린다(value, hidden):
    assert diagnostics.hide(value, [TOKEN, QUOTED]) == hidden


def test_업무_DB_쓰기는_가린_뒤_넘기고_읽기는_그대로_넘긴다(course):
    """실제 저장소(PgRepo)에 점유한 작업의 결과 · 처리 기록을 쓰고 다시 읽는다."""
    import uuid
    from conftest import start_handover
    start_handover(course.rt)
    [row] = course.rt.repo.fetch_pending_task('cliagents', 'test-worker:' + uuid.uuid4().hex, tenant_id='hyd')
    secrets = []
    hidden = diagnostics.HiddenRepo(course.rt.repo, secrets)
    secrets.append(QUOTED)                      # 실행 중에 늘어난 비밀(실행 토큰)도 그다음 쓰기부터 가린다
    assert hidden.save_task_result(row['id'], {'text': f'결과 {QUOTED}'}, final=True, expected_consumer=row['consumer'])
    hidden.record_events([{'job_id': 'j', 'todo_id': row['id'], 'proc_inst_id': row['proc_inst_id'], 'crew_type': 'agent',
                           'event_type': 'error', 'data': {'friendly': f'까닭 {QUOTED}'}}])
    assert course.rt.repo.get_workitem(row['id'])['output'] == {'text': f'결과 {REDACTED}'}
    assert [e['data']['friendly'] for e in course.rt.repo.list_events(todo_id=row['id']) if e['event_type'] == 'error'] == [f'까닭 {REDACTED}']
    assert hidden.get_workitem(row['id'])['id'] == row['id']        # 읽기는 같은 저장소를 그대로


@pytest.mark.parametrize('text, leaked', [
    ('connect postgresql://postgres:hydpass123@db:5432/x failed', 'hydpass123'),
    ('Authorization: Bearer sk-abcdefghijklmnop', 'sk-abcdefghijklmnop'),
    ('neo4j password=hydpass123 refused', 'hydpass123'),
], ids=['주소 속 비밀번호', 'Bearer 토큰', '이름=값'])
def test_오류_글은_모르는_비밀도_이름_모양으로_가리고_길이를_줄인다(text, leaked):
    out = diagnostics.excerpt(text + ' ' + 'x' * 2000, limit=300)
    assert leaked not in out and len(out) <= 300 and '[중간 생략]' in out
