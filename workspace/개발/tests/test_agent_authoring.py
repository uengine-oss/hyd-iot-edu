"""에이전트 만들기 · 복제(procsvc/agent_authoring.py) — 기본 에이전트는 모두 도구 · 스킬 그대로 복제해 고칠 수 있고, 등록 안 된 도구 서버 ·
수업 모델 밖 모델 · 같은 이름은 학생이 읽을 까닭과 함께 거절된다. 실제 업무 DB(시드 테넌트 hyd).

옛 판은 수업용 도구 서버 목록(셋)을 따로 적어, 정비 · 구매 서버를 쓰는 기본 정비 · 구매 에이전트의 [복제해서 고치기]가 늘 거절됐다(견적 #7).
"""
import psycopg
import pytest

from procsvc import agent_authoring as A, procdb
from procsvc.agent_authoring import AuthoringError

SEED_AGENTS = ['sys:agent', 'agent:cooling', 'agent:pm-plan', 'agent:spare-buy', 'agent:handover']


@pytest.fixture
def authoring(pg_dsn):
    repo, made = procdb.PgRepo(pg_dsn), []
    yield repo, made
    with psycopg.connect(pg_dsn, autocommit=True) as db:
        for agent_id in made:
            db.execute('DELETE FROM agent_skills WHERE user_id=%s', (agent_id,))
            db.execute('DELETE FROM users WHERE id=%s', (agent_id,))


def tools_of(row):
    return sorted(A.csv_list(row.get('tools')))


@pytest.mark.parametrize('agent_id', SEED_AGENTS)
def test_기본_에이전트는_모두_도구와_스킬을_그대로_복제해_고칠_수_있다(authoring, agent_id):
    repo, made = authoring
    source = A._agent(repo, 'hyd', agent_id)
    copy = A.clone_agent(repo, 'hyd', agent_id, by='user:kim-op')
    made.append(copy['id'])
    assert (A.origin_of(copy), tools_of(copy), copy.get('work_rules')) == (A.USER, tools_of(source), source.get('work_rules'))
    assert [r['skill_name'] for r in repo.list_agent_skills('hyd', copy['id'])] == [r['skill_name'] for r in repo.list_agent_skills('hyd', agent_id)]
    edited = A.update_agent(repo, 'hyd', copy['id'], {'name': copy['username'], 'goal': '내가 고친 목표', 'tools': tools_of(copy)})
    assert edited['goal'] == '내가 고친 목표'


@pytest.mark.parametrize('body, says', [
    (dict(name='내 에이전트', goal='점검', tools=['neo4j', 'no-such-server']), '등록되지 않은 도구 서버'),
    (dict(name='내 에이전트', goal='점검', model='gpt-9-ultra'), '수업 모델'),
    (dict(name='냉각 긴급 대응 에이전트', goal='기본과 같은 이름'), '같은 이름'),
    (dict(name='', goal='이름 없음'), '이름'),
])
def test_받을_수_없는_에이전트는_까닭과_함께_거절되고_만들어지지_않는다(authoring, body, says):
    repo, _ = authoring
    before = {u['id'] for u in repo.list_users(None, 'hyd')}
    with pytest.raises(AuthoringError) as refused:
        A.create_agent(repo, 'hyd', body, by='user:kim-op')
    assert says in str(refused.value)
    assert {u['id'] for u in repo.list_users(None, 'hyd')} == before
