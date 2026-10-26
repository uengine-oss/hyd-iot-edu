"""Two real document journals share a failure mode; revisions must preserve the other document's edges."""
import pytest
from uuid import uuid4
from procsvc import manual_graph as mg, manual_review as review
from test_manual_revision_history import graph, archive, TEXT, REVISED, journal


def proposal(archive, text, *, previous=None, document=None, own_failure=True):
    source = archive.save('hyd', 'manual.md', text.encode(), document_id=document)
    body = review.proposal(source)
    body.update(by='검토자', reviewed=True, previous_batch=previous,
                links={p['id']: {'failureMode': 'fm:bearing-degradation' if own_failure else 'fm:shared'} for p in body['procedures']})
    if own_failure:
        body['knowledge'] = {'failure_modes': [{'id': 'fm:shared', 'name': '문서가 정의한 고장',
            'component': 'comp:shared', 'section': body['sections'][0]['ref'], 'anchor': body['sections'][0]['anchor']}]}
    return source, review.validate(archive, 'hyd', body)


def test_cross_document_reference_survives_revision_but_blocks_target_removal(graph, archive):
    graph.run("CREATE (:Component {id:'comp:shared'})").consume()
    a, first = proposal(archive, TEXT)
    v1 = mg.commit(graph, first)
    b, dependent = proposal(archive, TEXT.replace('SOP-REF-91', 'SOP-REF-93').replace('SOP-REF-92', 'SOP-REF-94'), own_failure=False)
    b1 = mg.commit(graph, dependent)
    def refs():
        return graph.run("MATCH (:FailureMode {id:'fm:shared'})-[r]->(s:Skill) RETURN elementId(r) AS edge,s.id AS skill ORDER BY skill").data()
    original = refs()
    assert len(original) == 2
    _, revision = proposal(archive, REVISED, document=a['document_id'], previous=v1['batch'])
    v2 = mg.commit(graph, revision)
    assert refs() == original
    mg.rollback(graph, 'hyd', v2['batch'], '검토자')
    assert refs() == original and journal(graph, a)[0] == v1['batch']
    before = journal(graph, a)
    with pytest.raises(mg.Conflict, match='의존 문서를 먼저'):
        mg.rollback(graph, 'hyd', v1['batch'], '검토자')
    assert journal(graph, a) == before and refs() == original
    # A managed dependency is not an exemption for arbitrary edits.
    graph.run("MATCH (f:FailureMode {id:'fm:shared'}),(s:Skill {sopId:'SOP-REF-93'}) CREATE (s)-[:UNKNOWN_REF]->(f)").consume()
    with pytest.raises(mg.Conflict, match='관계'):
        mg.commit(graph, dict(revision, batch=str(uuid4())))
    graph.run('MATCH ()-[r:UNKNOWN_REF]->() DELETE r').consume()
    # Remove the dependent source first; then the original can be undone normally.
    mg.rollback(graph, 'hyd', b1['batch'], '검토자')
    mg.rollback(graph, 'hyd', v1['batch'], '검토자')
    assert graph.run("MATCH (f:FailureMode {id:'fm:shared'}) RETURN count(f) AS n").single()['n'] == 0
