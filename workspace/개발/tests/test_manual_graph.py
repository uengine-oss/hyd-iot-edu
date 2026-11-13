"""문서가 가진 지식 그래프(procsvc/manual_graph.py) — 검토한 계획을 한 거래로 바꿔 끼우고(적재 · 개정), 최신 판부터 앞 판의 모습으로 되돌린다.
같은 배치는 한 번만, 판이 미리보기 뒤에 바뀌었거나 적재 뒤 그래프를 누가 고쳤으면 쓰지 않고 멈춘다. 실제 Neo4j(kg-seed 가 끝난 그래프)와
실제 보관소 · 검토 검증(manual_review.validate)으로 만든 강사 검토본 계획으로 판정한다 — 적재 API 와 같은 차례(의미 검사 → 후보 규칙 → 바꿔 끼우기)."""
import json
from copy import deepcopy
from uuid import uuid4

import pytest

import class_knowledge
from procsvc import manual_graph, manual_knowledge, manual_references, manual_review, skill_graph
from procsvc.manual_sources import ManualSources

DOCS = {i['doc']: i for i in class_knowledge.reviewed()}
RULE = 'rule:cooler-forecast-temperature-warning'


@pytest.fixture
def archive(tmp_path):
    return ManualSources(tmp_path / 'm.sqlite3')


def plan_of(archive, doc, *, previous=None, document_id=None, drop_rule=None, by=None, rebind=None):
    """doc = 시작이 넣는 문서의 이름(DOCS) 또는 강사 서명 묶음의 문서 한 건(class_knowledge.reviewed 의 원소).
    rebind = {SOP 번호: (다시 가리킬 조치 방법 id, 대조한 실행 계약 지문)} — 그 절차를 이미 있는 조치 방법을 다시 가리키는 참고 절차로 낸다."""
    item = DOCS[doc] if isinstance(doc, str) else doc
    source = archive.save('hyd', item['filename'], item['raw'], **({'document_id': document_id} if document_id else {}))
    body = class_knowledge.commit_body(item, {'source_id': source['source_id'], 'document_id': source['document_id'],
                                              'filename': item['filename'], 'batch': str(uuid4()), 'previous_batch': previous})
    if drop_rule:
        body['knowledge']['rules'] = [r for r in body['knowledge']['rules'] if r['id'] != drop_rule]
    if by:
        body['by'] = by
    for sop, (skill, pin) in (rebind or {}).items():
        body['links'][sop] = dict(body['links'][sop], existing_skill_id=skill, reference_contract_sha256=pin)
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
    with pytest.raises(manual_graph.Conflict, match='문서 등록 이후'):
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


# ---------------------------------------------------------------- 교대 인계 문서(HI-01): 실행 후보가 아닌 참고 절차
@pytest.fixture
def handover_doc(monkeypatch):
    """강사 서명 묶음의 교대 인계 문서(HI-01) 검토본 한 건 — 시작의 적재 순서(class_knowledge.ORDER)에는 없고 학생이 실습에서 넣는 문서다.
    시작이 넣는 문서와 같은 함수(reviewed: 묶음 → 원문 sha256 대조 → 검토본)로 읽고, 학생이 포털에서 제안 그대로 검토 완료하는 것과 같은
    요청으로 만든다: 담당자 이름으로, 검토 방식 칸 없이(포털은 그 칸을 보내지 않는다). 묶음이 적어 둔 이 문서의 검토 방식
    (origin.review_method)은 검토 검증(manual_review.validate)이 받는 값이 아니라서, 시작의 적재처럼 그 값을 그대로 실으면 거절된다."""
    monkeypatch.setattr(class_knowledge, 'ORDER', ('HI-01',))
    [item] = class_knowledge.reviewed()
    return dict(item, by='user:me', review_method=None)


def _read(graph, fn, *args):
    with graph.driver.session() as session:
        return session.execute_read(lambda tx: fn(tx, *args))


def test_교대_인계_문서의_참고_절차는_그래프에_들어가_계약으로_읽히고_실행_후보는_되지_않는다(seeded_graph, archive, handover_doc):
    """전수 검사 13B 「가」 1: HI-01 은 시작의 적재 순서에 없어 문서마다 도는 시험이 빼고 돌았고, 참고 절차가 그래프에 들어가 계약으로 다시 읽히는
    길(manual_references.contracts · check_plan)은 어느 시험도 지나지 않았다."""
    plan = plan_of(archive, handover_doc)
    sops = [p['id'] for p in plan['procedures']]
    assert sops == ['SOP-HI-01', 'SOP-HI-02', 'SOP-HI-03'] and {p['kind'] for p in plan['procedures']} == {'reference'}
    receipt = commit(seeded_graph, plan)
    assert (receipt['procedures'], receipt['status']) == (3, 'ACTIVE')
    skills = {sop: manual_graph.skill_id(sop) for sop in sops}
    read = _read(seeded_graph, manual_references.contracts, list(skills.values()))
    assert set(read) == set(skills.values()), '참고 절차 셋이 모두 조치 방법 계약으로 읽혀야 한다'
    for p in plan['procedures']:
        c = read[skills[p['id']]]
        assert (c['sopId'], c['owner']) == (p['id'], plan['document'])
        assert c['steps'] == [{'order': s['order'], 'text': s['text']} for s in p['steps']], '원문 단계가 순서 · 글 그대로 들어간다'
        assert {s['ref'] for s in c['sections']} == {s['manual'] for s in p['steps']}
        assert (c['contract']['skill']['kind'], c['contract']['skill']['executable']) == ('reference', False)
        # 실행 연결이 하나도 없다: 고장 유형이 이 절차를 조치로 갖지 않고(판단 엔진의 후보는 고장 유형 → 조치 방법 관계로 찾는다), 후보 규칙의
        # 결과도 아니며, 승인 역할 · 원자 조치 · 대상 원인 · 영향도 없다
        assert c['contract']['incoming'] == [] and c['contract']['outgoing'] == [], c['contract']
    assert _read(seeded_graph, manual_references.check_plan, plan) == {}, '다른 조치 방법을 다시 가리키지 않는 문서다'
    offered = seeded_graph.query('MATCH (n)-[r:MITIGATED_BY|REMEDIED_BY|PREVENTED_BY|OUTPUTS|HAS_SKILL]->(k:Skill) WHERE k.id IN $ids '
                                 'RETURN k.id AS id, type(r) AS rel', ids=list(skills.values()))
    assert offered == [], '참고 절차가 실행 후보로 이어졌다'


def test_다른_문서가_참고_절차를_다시_가리키면_대조한_계약_지문과_단계가_그대로일_때만_받는다(seeded_graph, archive, handover_doc):
    """다시 가리키기(existing_skill_id): 뒤에 온 문서(같은 원문을 다른 문서로 등록)가 먼저 적재된 참고 절차의 조치 방법을 가리킨다 — 그래프에서 읽은
    계약 지문(contracts)과 원문 번호 · 전체 단계를 실제 그래프와 대조한다(check_plan)."""
    first = plan_of(archive, handover_doc)
    commit(seeded_graph, first)
    sop = 'SOP-HI-02'
    skill = manual_graph.skill_id(sop)
    pin = _read(seeded_graph, manual_references.contracts, [skill])[skill]['contract_sha256']
    second = plan_of(archive, handover_doc, rebind={sop: (skill, pin)})
    assert second['document'] != first['document']
    bound = _read(seeded_graph, manual_references.check_plan, second)
    assert set(bound) == {sop} and bound[sop]['skill'] == skill and (bound[sop]['contract_sha256'], bound[sop]['owner']) == (pin, first['document'])
    stale = plan_of(archive, handover_doc, rebind={sop: (skill, 'f' * 64)})
    with pytest.raises(ValueError, match='실행 계약이 바뀌었습니다'):
        _read(seeded_graph, manual_references.check_plan, stale)
    other = plan_of(archive, handover_doc, rebind={sop: (manual_graph.skill_id('SOP-HI-03'), pin)})
    with pytest.raises(ValueError, match='SOP 번호와 다릅니다'):
        _read(seeded_graph, manual_references.check_plan, other)
