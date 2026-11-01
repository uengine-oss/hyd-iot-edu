"""업무 데이터 연결 적재 · 되돌리기(procsvc/graph_ingest.py) — DDL 미리보기 계획을 그래프에 소유 이력과 함께 넣고, 배치 하나를 되돌리면 그 배치가
만든 입력 · 시스템은 지우고 원래 있던 노드는 처음 속성으로 돌린다. 실라버스 4회차 40행(제공 legacy-plant-db.sql 적재 → 되돌리기)을 여러 번
되풀이해도 그래프가 처음 모습으로 돌아오는지가 판정 대상이다. 실제 Neo4j(kg-seed 가 끝난 그래프 — seeded_graph)로 판정한다."""
import json

import pytest

from conftest import SAMPLES

from procsvc import graph_ingest, ingest

LEGACY = (SAMPLES / 'legacy-plant-db.sql').read_text(encoding='utf-8')
AUDIT_LABELS = ('IngestionBatch', 'IngestionControl')       # 적재 기록 · 잠금 노드(감사용으로 남는다)


def plan(n=0, selection=None, systems=None):
    tables = ingest.parse_ddl(LEGACY)
    return ingest.plan(tables, filename='legacy-plant-db.sql', batch=f'ingest:ddl:test-{n}',
                       selection=selection or {'T_EQP01': ['C_TMP_O', 'C_PRS_A'], 'T_MNT10': ['CST_AMT']},
                       systems=systems or {'T_EQP01': 'sys:cmms', 'T_MNT10': 'sys:cmms'})


def snapshot(graph):
    """감사 노드를 뺀 그래프 전체(노드 레이블 · 속성, 관계 종류 · 양 끝 · 속성)."""
    nodes = graph.query('MATCH (n) WHERE NONE(l IN labels(n) WHERE l IN $audit) RETURN labels(n) AS l, properties(n) AS p', audit=list(AUDIT_LABELS))
    rels = graph.query('MATCH (a)-[r]->(b) WHERE NONE(l IN labels(a) + labels(b) WHERE l IN $audit) '
                       'RETURN type(r) AS t, a.id AS a, b.id AS b, properties(r) AS p', audit=list(AUDIT_LABELS))
    dump = lambda rows: sorted(json.dumps(r, sort_keys=True, ensure_ascii=False, default=str) for r in rows)
    return dump(nodes), dump(rels)


def commit(graph, p):
    with graph.driver.session() as s:
        return graph_ingest.commit(s, p)


def clear(graph, batch):
    with graph.driver.session() as s:
        return graph_ingest.clear(s, batch)


def test_적재하면_입력_데이터가_고른_출처_시스템에_이어진다(seeded_graph):
    p = plan()
    out = commit(seeded_graph, p)
    assert (out['inputs'], out['replayed']) == (3, False)
    rows = seeded_graph.query('MATCH (i:InputData)-[:SOURCED_FROM]->(s:System) WHERE i.id IN $ids RETURN i.id AS i, s.id AS s',
                              ids=[i['id'] for i in p['inputs']])
    assert {r['s'] for r in rows} == {'sys:cmms'} and len(rows) == 3


def test_같은_배치를_다시_보내면_한_번만_적용된다(seeded_graph):
    p = plan()
    commit(seeded_graph, p)
    assert commit(seeded_graph, p)['replayed'] is True
    assert seeded_graph.query('MATCH (b:IngestionBatch {id:$id}) RETURN count(b) AS n', id=p['batch'])[0]['n'] == 1


def test_같은_배치_id에_다른_내용은_받지_않는다(seeded_graph):
    commit(seeded_graph, plan())
    other = plan(selection={'T_EQP01': ['C_TMP_O']})
    with pytest.raises(graph_ingest.Conflict, match='배치 ID'):
        commit(seeded_graph, other)


@pytest.mark.parametrize('rounds', [1, 3], ids=['한 번', '세 번 되풀이'])
def test_적재하고_되돌리기를_되풀이해도_그래프는_처음_모습으로_돌아온다(seeded_graph, rounds):
    """실라버스 4회차 40행 · 메인 확인 요청: 같은 실습을 여러 번 해도 입력 · 시스템 · 관계가 남지 않는다(적재 기록 노드만 감사용으로 남음)."""
    before = snapshot(seeded_graph)
    for n in range(rounds):
        p = plan(n)
        commit(seeded_graph, p)
        out = clear(seeded_graph, p['batch'])
        assert out['deleted'] >= 3
    assert snapshot(seeded_graph) == before
    assert seeded_graph.query("MATCH (b:IngestionBatch) WHERE b.status='CLEARED' RETURN count(b) AS n")[0]['n'] == rounds


def test_원래_있던_시스템은_되돌려도_지우지_않고_그대로_둔다(seeded_graph):
    before = seeded_graph.query("MATCH (s:System {id:'sys:cmms'}) RETURN properties(s) AS p")
    assert before, 'kg-seed 에 sys:cmms 가 있다'
    p = plan()
    commit(seeded_graph, p)
    clear(seeded_graph, p['batch'])
    assert seeded_graph.query("MATCH (s:System {id:'sys:cmms'}) RETURN properties(s) AS p") == before


def test_두_배치가_같은_입력을_쓰면_하나를_되돌려도_다른_배치의_모습으로_남는다(seeded_graph):
    first, second = plan(1, systems={'T_EQP01': 'sys:cmms', 'T_MNT10': 'sys:cmms'}), plan(2, systems={'T_EQP01': 'sys:mes', 'T_MNT10': 'sys:cmms'})
    commit(seeded_graph, first)
    commit(seeded_graph, second)
    out = clear(seeded_graph, second['batch'])
    assert out['retained'] >= 1
    sid = next(i['id'] for i in first['inputs'] if i['column'] == 'C_TMP_O')
    assert seeded_graph.query('MATCH (:InputData {id:$id})-[:SOURCED_FROM]->(s) RETURN s.id AS s', id=sid) == [{'s': 'sys:cmms'}]


def test_되돌린_배치를_또_되돌리면_아무것도_하지_않는다(seeded_graph):
    p = plan()
    commit(seeded_graph, p)
    clear(seeded_graph, p['batch'])
    assert clear(seeded_graph, p['batch'])['replayed'] is True


def test_없는_배치를_되돌리면_KeyError다(seeded_graph):
    with pytest.raises(KeyError):
        clear(seeded_graph, 'ingest:ddl:none')


def test_적재_뒤_다른_작업이_입력을_쓰면_되돌리기를_멈춘다(seeded_graph):
    p = plan()
    commit(seeded_graph, p)
    iid = p['inputs'][0]['id']
    seeded_graph.query("MATCH (i:InputData {id:$id}) CREATE (:Rule {id:'rule:test-uses'})-[:TESTS]->(i)", id=iid)
    with pytest.raises(graph_ingest.Conflict, match='사용 중'):
        clear(seeded_graph, p['batch'])


def test_적재_뒤_다른_작업이_원천_속성을_바꾸면_되돌리기를_멈춘다(seeded_graph):
    p = plan()
    commit(seeded_graph, p)
    seeded_graph.query("MATCH (i:InputData {id:$id}) SET i.name = '누가 고친 이름'", id=p['inputs'][0]['id'])
    with pytest.raises(graph_ingest.Conflict, match='다른 작업'):
        clear(seeded_graph, p['batch'])


def test_적재_이력은_살아_있는_배치와_그_노드_수를_보인다(seeded_graph):
    p = plan()
    commit(seeded_graph, p)
    rows = seeded_graph.query(graph_ingest.BATCHES_Q)
    assert {(r['batch'], r['label'], r['nodes']) for r in rows} >= {(p['batch'], 'InputData', 3)}
    assert all(set(r) == {'batch', 'label', 'nodes', 'source'} for r in rows)
