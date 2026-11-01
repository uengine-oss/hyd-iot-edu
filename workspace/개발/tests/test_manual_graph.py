"""문서가 가진 지식 그래프(procsvc/manual_graph.py) — 검토한 계획을 한 거래로 바꿔 끼우고(적재 · 개정), 최신 판부터 앞 판의 모습으로 되돌린다.
같은 배치는 한 번만, 판이 미리보기 뒤에 바뀌었거나 적재 뒤 그래프를 누가 고쳤으면 쓰지 않고 멈춘다. 실제 Neo4j(kg-seed 가 끝난 그래프)와
실제 보관소 · 검토 검증(manual_review.validate)으로 만든 강사 검토본 계획으로 판정한다 — 적재 API 와 같은 차례(의미 검사 → 후보 규칙 → 바꿔 끼우기)."""
import json
from copy import deepcopy
from uuid import uuid4

import pytest

import class_knowledge
from procsvc import manual_graph, manual_knowledge, manual_review, skill_graph
from procsvc.manual_sources import ManualSources

DOCS = {i['doc']: i for i in class_knowledge.reviewed()}
RULE = 'rule:cooler-forecast-temperature-warning'


@pytest.fixture
def archive(tmp_path):
    return ManualSources(tmp_path / 'm.sqlite3')


def plan_of(archive, doc, *, previous=None, document_id=None, drop_rule=None, by=None):
    item = DOCS[doc]
    source = archive.save('hyd', item['filename'], item['raw'], **({'document_id': document_id} if document_id else {}))
    body = class_knowledge.commit_body(item, {'source_id': source['source_id'], 'document_id': source['document_id'],
                                              'filename': item['filename'], 'batch': str(uuid4()), 'previous_batch': previous})
    if drop_rule:
        body['knowledge']['rules'] = [r for r in body['knowledge']['rules'] if r['id'] != drop_rule]
    if by:
        body['by'] = by
    return manual_review.validate(archive, 'hyd', body)


def commit(graph, plan):
    """적재 API(manual_api.commit)와 같은 차례: 지금 그래프로 의미 검사 → 고장 유형의 후보 규칙 → 바꿔 끼우기."""
    with graph.driver.session() as session:
        manual_knowledge.check_graph(session, plan, manual_graph.skill_id)
        fms = sorted({p['failureMode'] for p in plan['procedures'] if p.get('failureMode')})
        plan['candidate_rules'] = {fm: session.execute_read(lambda tx, fm=fm: skill_graph.candidate_rules(tx, fm)) for fm in fms}
        return manual_graph.commit(session, plan)


def session_call(graph, fn, *args):
    with graph.driver.session() as session:
        return fn(session, *args)


def rule_ids(graph):
    """그래프의 규칙 id 전부 — 문서 규칙은 표시 속성 없이 적재 기록으로 소유된다(manual_graph KNOWLEDGE_LABELS)."""
    return {r['id'] for r in graph.query('MATCH (r:Rule) RETURN r.id AS id')}


def test_검토본을_적재하면_그_문서가_지식을_갖고_지금_판이_된다(seeded_graph, archive):
    assert RULE not in rule_ids(seeded_graph)
    plan = plan_of(archive, 'HM-8')
    receipt = commit(seeded_graph, plan)
    assert (receipt['batch'], receipt['procedures'], receipt['status']) == (plan['batch'], len(plan['procedures']), 'ACTIVE')
    assert session_call(seeded_graph, manual_graph.head, 'hyd', plan['document_id']) == plan['batch']
    assert RULE in rule_ids(seeded_graph)
    [row] = [r for r in session_call(seeded_graph, manual_graph.history, 'hyd') if r['batch'] == plan['batch']]
    assert (row['current'], row['by']) == (True, plan['by'])
    shown = seeded_graph.query('MATCH (s:Skill) WHERE s._manual_document = $doc RETURN s.description AS d', doc=plan['document'])
    assert shown and {r['d'] for r in shown} == {f"제공 문서 {plan['filename']}에서 검토해 넣은 조치 방법"}   # 승인 카드 설명(W1-13)


def test_같은_배치를_다시_보내면_한_번만_적용되고_다른_내용이면_거절한다(seeded_graph, archive):
    plan = plan_of(archive, 'HM-8')
    commit(seeded_graph, plan)
    assert commit(seeded_graph, deepcopy(plan))['replayed'] is True
    changed = deepcopy(plan)
    changed['procedures'][0]['name'] += ' (다름)'
    with pytest.raises(manual_graph.Conflict, match='배치 ID'):
        commit(seeded_graph, changed)


def test_개정_미리보기는_새_판에서_빠지는_노드를_알린다(seeded_graph, archive):
    first = plan_of(archive, 'HM-8')
    commit(seeded_graph, first)
    second = plan_of(archive, 'HM-8', previous=first['batch'], document_id=first['document_id'], drop_rule=RULE)
    preview = session_call(seeded_graph, manual_graph.revision_preview, second)
    assert [n['id'] for n in preview['removed']] == [RULE]


def test_미리보기_뒤_다른_판이_적재되면_개정을_멈춘다(seeded_graph, archive):
    first = plan_of(archive, 'HM-8')
    commit(seeded_graph, first)
    stale = plan_of(archive, 'HM-8', previous=None, document_id=first['document_id'])
    with pytest.raises(manual_graph.Conflict, match='미리보기 이후'):
        commit(seeded_graph, stale)


def test_되돌리면_앞_판의_모습으로_돌아간다(seeded_graph, archive):
    first = plan_of(archive, 'HM-8', drop_rule=RULE)
    commit(seeded_graph, first)
    second = plan_of(archive, 'HM-8', previous=first['batch'], document_id=first['document_id'])
    commit(seeded_graph, second)
    assert RULE in rule_ids(seeded_graph)
    out = session_call(seeded_graph, manual_graph.rollback, 'hyd', second['batch'], '수강생')
    assert (out['status'], out['restored_batch']) == ('ROLLED_BACK', first['batch'])
    assert RULE not in rule_ids(seeded_graph)
    assert session_call(seeded_graph, manual_graph.head, 'hyd', first['document_id']) == first['batch']


def test_첫_판을_되돌리면_그_문서의_지식이_모두_빠진다(seeded_graph, archive):
    plan = plan_of(archive, 'HM-8')
    commit(seeded_graph, plan)
    session_call(seeded_graph, manual_graph.rollback, 'hyd', plan['batch'], '수강생')
    left = seeded_graph.query('MATCH (n) WHERE n._manual_document = $doc AND (n:Skill OR n:Step OR n:Rule OR n:FailureMode OR n:Cause '
                              'OR n:Evidence) RETURN count(n) AS n', doc=plan['document'])[0]['n']
    assert left == 0 and session_call(seeded_graph, manual_graph.head, 'hyd', plan['document_id']) is None


def test_최신_판이_아니면_되돌리지_않는다(seeded_graph, archive):
    first = plan_of(archive, 'HM-8')
    commit(seeded_graph, first)
    second = plan_of(archive, 'HM-8', previous=first['batch'], document_id=first['document_id'])
    commit(seeded_graph, second)
    with pytest.raises(manual_graph.Conflict, match='최신 판본부터'):
        session_call(seeded_graph, manual_graph.rollback, 'hyd', first['batch'], '수강생')


def test_적재_뒤_누가_그래프를_고쳤으면_되돌리지_않고_멈춘다(seeded_graph, archive):
    plan = plan_of(archive, 'HM-8')
    commit(seeded_graph, plan)
    seeded_graph.query('MATCH (r:Rule {id:$id}) SET r.annotation = $text', id=RULE, text='누가 고친 설명')
    with pytest.raises(manual_graph.Conflict, match='바뀌어 되돌릴 수 없습니다'):
        session_call(seeded_graph, manual_graph.rollback, 'hyd', plan['batch'], '수강생')


@pytest.mark.parametrize('by', ['', '   ', None])
def test_되돌리는_담당자_없이는_되돌리지_않는다(seeded_graph, by):
    with pytest.raises(ValueError, match='담당자'):
        session_call(seeded_graph, manual_graph.rollback, 'hyd', 'b', by)


def test_없는_배치를_되돌리면_KeyError다(seeded_graph):
    with pytest.raises(KeyError):
        session_call(seeded_graph, manual_graph.rollback, 'hyd', str(uuid4()), '수강생')


def test_다른_문서가_가진_SOP_번호는_미리_알린다(seeded_graph, archive):
    plan = plan_of(archive, 'HM-8')
    commit(seeded_graph, plan)
    other_doc = manual_review.document_key('hyd', str(uuid4()))
    conflicts = session_call(seeded_graph, manual_graph.sop_conflicts, other_doc, [plan['procedures'][0]['id']])
    assert [c['sop'] for c in conflicts] == [plan['procedures'][0]['id']]


def test_목표_모습은_의미_검사를_거친_계획만으로_정해진다(seeded_graph, pg_dsn, archive):
    import psycopg
    from procsvc import scm_sync
    scm_sync.sync(lambda cypher, **params: seeded_graph.query(cypher, **params), lambda: psycopg.connect(pg_dsn))     # 구매 절차의 공급 관계(정본 업무 DB — 시작이 적재 전에 옮긴다)
    plan = plan_of(archive, 'PR-07')
    with seeded_graph.driver.session() as session:
        manual_knowledge.check_graph(session, plan, manual_graph.skill_id)       # 규칙 입력의 변수 이름을 지금 그래프에서 정한다
    a, b = manual_graph.desired(deepcopy(plan)), manual_graph.desired(deepcopy(plan))
    assert json.dumps(a, sort_keys=True, ensure_ascii=False) == json.dumps(b, sort_keys=True, ensure_ascii=False)
    assert {n['labels'][0] for n in a['nodes']} >= {'KnowledgeSource', 'ManualSection', 'Skill', 'Step'}


def test_의미_검사를_거치지_않은_계획으로는_목표_모습을_만들지_않는다(archive):
    with pytest.raises(ValueError, match='check_graph'):
        manual_graph.desired(plan_of(archive, 'PR-07'))
