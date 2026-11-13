"""공급사 · 견적 동기화(procsvc/scm_sync.py) — 그래프의 공급사 · SUPPLIED_BY 견적이 업무 DB(ERP 가 발주 확인에 쓰는 ent.quote_rows)를 따른다.

실제 업무 DB(테스트 DB, 마이그레이션 + 시드)와 kg-seed 와 같은 시드가 들어간 실제 그래프로 돌린다.
"""
import psycopg
import pytest

from procsvc import scm_sync


def _connect(pg_dsn):
    return lambda: psycopg.connect(pg_dsn)


def test_동기화의_원천은_ERP가_발주_확인에_쓰는_부품별_견적_전부다(pg_dsn):
    """P4-02 · G2-06: 전에는 ent.suppliers(쿨러 코어 견적)만 읽어 씰 키트 · 팬 베어링 견적(ent.part_quotes)은 그래프로 가지 않았다."""
    suppliers, quotes = scm_sync.source(_connect(pg_dsn))
    with psycopg.connect(pg_dsn) as db:
        expected = db.execute('SELECT q.part_no, q.supplier_id, q.price FROM ent.parts p CROSS JOIN LATERAL ent.quote_rows(p.part_no) q '
                              'ORDER BY 1, 2').fetchall()
    assert [(q['part_no'], q['supplier_id'], q['price']) for q in quotes] == expected
    assert {q['part_no'] for q in quotes} >= {'P-PMP-SEAL', 'P-FAN-BRG', 'P-CLR-CORE'}
    assert {s['id'] for s in suppliers} == {q['supplier_id'] for q in quotes}


def _graph_quotes(g, part):
    return {r['supplier']: (r['price'], r['leadDays']) for r in g.query(scm_sync.GRAPH_QUOTES_Q) if r['part'] == part}


def test_업무_DB에서_씰_키트_견적을_바꾸면_동기화가_그래프의_견적도_바꾼다(pg_dsn, seeded_graph):
    with psycopg.connect(pg_dsn, autocommit=True) as db:
        before = db.execute("SELECT price FROM ent.part_quotes WHERE part_no='P-PMP-SEAL' AND supplier_id='sup:b'").fetchone()[0]
        db.execute("UPDATE ent.part_quotes SET price = 61, lead_d = 4 WHERE part_no='P-PMP-SEAL' AND supplier_id='sup:b'")
    try:
        report = scm_sync.sync(seeded_graph.query, _connect(pg_dsn))
        assert _graph_quotes(seeded_graph, 'P-PMP-SEAL')['sup:b'] == (61.0, 4)
        assert report['graph_only'] == [] and report['changed'] >= 1
        again = scm_sync.sync(seeded_graph.query, _connect(pg_dsn))
        assert again['changed'] == 0, '같은 원천이면 두 번째 동기화는 바꾸는 것이 없다'
    finally:
        with psycopg.connect(pg_dsn, autocommit=True) as db:
            db.execute("UPDATE ent.part_quotes SET price = %s, lead_d = 5 WHERE part_no='P-PMP-SEAL' AND supplier_id='sup:b'", (before,))


def test_공급사_이름과_승인_공급사_순정_여부는_업무_DB_값을_따른다(pg_dsn, seeded_graph):
    scm_sync.sync(seeded_graph.query, _connect(pg_dsn))
    with psycopg.connect(pg_dsn) as db:
        rows = {r[0]: (r[1], r[2], r[3]) for r in db.execute('SELECT id, name, avl, oem FROM ent.suppliers').fetchall()}
    graph = {r['id']: (r['name'], r['avl'], r['oem']) for r in seeded_graph.query(scm_sync.GRAPH_SUPPLIERS_Q) if r['id'] in rows}
    assert graph == rows



def test_이미_있는_공급사의_순정_여부가_업무_DB에서_바뀌면_다음_동기화가_그래프도_바꾼다(pg_dsn, seeded_graph):
    """FD 검증 ⑤: oem 비교를 빼도 위 시험은 통과했다(처음 동기화는 공급사를 모두 새로 쓴다) — 이미 있는 공급사의 변화만 재야 한다."""
    scm_sync.sync(seeded_graph.query, _connect(pg_dsn))
    with psycopg.connect(pg_dsn, autocommit=True) as db:
        before = db.execute("SELECT oem FROM ent.suppliers WHERE id='sup:a'").fetchone()[0]
        db.execute("UPDATE ent.suppliers SET oem = NOT oem WHERE id='sup:a'")
    try:
        report = scm_sync.sync(seeded_graph.query, _connect(pg_dsn))
        graph = {r['id']: r['oem'] for r in seeded_graph.query(scm_sync.GRAPH_SUPPLIERS_Q)}
        assert graph['sup:a'] is (not before) and [s['id'] for s in report['set_suppliers']] == ['sup:a'], report['set_suppliers']
    finally:
        with psycopg.connect(pg_dsn, autocommit=True) as db:
            db.execute("UPDATE ent.suppliers SET oem = %s WHERE id='sup:a'", (before,))
        scm_sync.sync(seeded_graph.query, _connect(pg_dsn))


PARTS = {'P-PMP-SEAL'}
SOURCE_Q = [{'part_no': 'P-PMP-SEAL', 'supplier_id': 'sup:a', 'price': 35, 'fail_rate': 0.12, 'lead_d': 2}]


@pytest.mark.parametrize('graph_quotes, parts, expect', [
    ([], PARTS, {'set_quotes': 1, 'delete_quotes': 0, 'missing_part': 0, 'graph_only': 0}),
    ([{'part': 'P-PMP-SEAL', 'supplier': 'sup:a', 'price': 35.0, 'failRate': 0.12, 'leadDays': 2}], PARTS,
     {'set_quotes': 0, 'delete_quotes': 0, 'missing_part': 0, 'graph_only': 0}),
    ([{'part': 'P-PMP-SEAL', 'supplier': 'sup:z', 'price': 1, 'failRate': 0, 'leadDays': 1}], PARTS,
     {'set_quotes': 1, 'delete_quotes': 1, 'missing_part': 0, 'graph_only': 0}),
    ([{'part': 'P-RTN-FLT', 'supplier': 'sup:a', 'price': 9, 'failRate': 0, 'leadDays': 1}], PARTS,
     {'set_quotes': 1, 'delete_quotes': 0, 'missing_part': 0, 'graph_only': 1}),
    ([], set(), {'set_quotes': 0, 'delete_quotes': 0, 'missing_part': 1, 'graph_only': 0}),
], ids=['그래프에 없음', '같음', '원천에 없는 견적은 지움', '원천에 견적이 없는 부품은 둠', '그래프에 부품 없음'])
def test_동기화_계획은_차이만_쓰고_원천이_없는_부품의_견적은_건드리지_않는다(graph_quotes, parts, expect):
    plan = scm_sync.plan([{'id': 'sup:a', 'name': 'A정밀 (저가)', 'avl': True, 'oem': False}], SOURCE_Q,
                         [{'id': 'sup:a', 'name': 'A정밀 (저가)', 'avl': True, 'oem': False}], graph_quotes, parts)
    assert {k: len(plan[k]) for k in expect} == expect and plan['set_suppliers'] == []
