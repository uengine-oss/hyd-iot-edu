"""지식 바뀜 뒤 그래프 반영 다시 잇기(procsvc/knowledge_projection.py) — 사건 · 실행 반영이 기대는 지식 노드 목록의 지문이 바뀌면 처리 건 반영
(PG 대기열)과 사건 반영(SQLite 대기열)을 다시 쌓고 검사점을 옮긴다. 같은 지문이면 아무것도 하지 않는다. 실제 그래프(seeded_graph) · 실제 업무 DB의
대기열(pg_dsn) · 실제 사건 저장소(Store, 임시 파일)로 판정한다."""
import psycopg
import pytest

from procsvc import procdb
from procsvc.knowledge_projection import KnowledgeReconciler, digest
from procsvc.store import Store


def outbox(dsn):
    with psycopg.connect(dsn) as db:
        return db.execute("SELECT count(*) FROM execution_projection_outbox WHERE tenant_id='hyd' AND processed_at IS NULL").fetchone()[0]


@pytest.fixture
def reconciler(seeded_graph, pg_dsn, tmp_path):
    return KnowledgeReconciler(Store(str(tmp_path / 'process.sqlite3')), seeded_graph.query, 'hyd', procdb.PgRepo(pg_dsn))


def test_처음_보면_다시_잇기를_쌓고_같은_지식이면_다시_쌓지_않는다(reconciler, pg_dsn):
    assert reconciler.scan() is True
    after_first = outbox(pg_dsn)
    assert reconciler.scan() is False and outbox(pg_dsn) == after_first
    assert reconciler.status()['queued']['digest'] == reconciler.observed and reconciler.last_error is None


def test_반영이_기대는_지식_노드가_바뀌면_다시_쌓는다(reconciler, seeded_graph):
    reconciler.scan()
    seeded_graph.query("CREATE (:Skill {id:'skill:test-new', name:'새 조치'})")
    assert reconciler.scan() is True


def test_반영이_기대지_않는_노드가_바뀌어도_다시_쌓지_않는다(reconciler, seeded_graph):
    reconciler.scan()
    seeded_graph.query("CREATE (:Step {id:'step:test-new', text:'단계'})")
    assert reconciler.scan() is False


def test_그래프를_읽지_못하면_검사점을_옮기지_않고_까닭을_상태에_남긴다(seeded_graph, pg_dsn, tmp_path):
    def broken(q):
        raise ConnectionError('neo4j down')
    r = KnowledgeReconciler(Store(str(tmp_path / 'p.sqlite3')), broken, 'hyd', procdb.PgRepo(pg_dsn))
    assert r.scan() is False and r.last_error == 'ConnectionError: neo4j down' and r.status()['queued'] is None


def test_지문은_목록_차례와_레이블_차례에_상관없다():
    rows = [{'kind': 'node', 'identity': '1', 'id': 'a', 'code': None, 'labels': ['Skill', 'Role'], 'source': None, 'target': None},
            {'kind': 'node', 'identity': '2', 'id': 'b', 'code': None, 'labels': ['Asset'], 'source': None, 'target': None}]
    flipped = [dict(rows[1]), dict(rows[0], labels=['Role', 'Skill'])]
    assert digest(rows) == digest(flipped) != digest(rows[:1])


def test_검사_주기_전에는_지식이_바뀌어도_다시_보지_않고_주기가_지나면_본다(seeded_graph, pg_dsn, tmp_path):
    """주기는 다시 잇기가 받는 시계로 잰다 — 시험은 벽시계를 기다리지 않고 그 시계를 옮긴다(전에는 주기 1초 · 1.1초 잠이라, 첫 검사의 그래프
    질의와 지식 바꾸기가 1초를 넘는 바쁜 PC 에서 둘째 검사가 주기 밖이 되어 깨졌다)."""
    now = [1000]
    reconciler = KnowledgeReconciler(Store(str(tmp_path / 'process.sqlite3')), seeded_graph.query, 'hyd', procdb.PgRepo(pg_dsn),
                                     monotonic=lambda: now[0])
    assert reconciler.poll() is True
    seeded_graph.query("CREATE (:Skill {id:'skill:test-interval', name:'주기 시험 조치'})")
    now[0] += reconciler.interval - 1
    assert reconciler.poll() is False                       # 주기 안 — 지식이 바뀌었어도 아직 보지 않는다
    now[0] += 1
    assert reconciler.poll() is True                        # 주기가 다 되면 바뀐 지식을 본다
