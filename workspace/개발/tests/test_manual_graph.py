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
    assert shown and {r['d'] for r in shown} == {f"문서 {plan['filename']}에서 검토해 넣은 조치 방법"}   # 학생이 올린 문서도 같은 판이라 「제공 문서」라 하지 않는다   # 승인 카드 설명(W1-13)


def test_적재_영수증의_후보_규칙_연결은_그래프에_실제로_이은_절차와_규칙만_싣는다(seeded_graph, archive):
    """06 화면 훑기(2026-11-20): 영수증(candidate_activation)이 고장 유형마다 그 유형만으로 고르는 규칙 목록을 빈 목록까지 실어, 화면이
    「후보 규칙에 연결: 쿨러 냉각 성능 상실 → (되돌리면 함께 빠집니다)」로 화살표 뒤를 비워 찍었다. 그 목록은 실제로 이은 것과도 달랐다 — 문서가 스스로
    후보 규칙을 적은 절차와 그 문서의 규칙은 잇지 않는다. 이제 영수증은 그래프 쓰기와 같은 판정(manual_graph.candidate_joins)으로 실제로 이은 것만 싣는다.
    ① 고장 유형만으로 고르는 규칙이 없으면 빈 묶음 ② 그런 규칙(조치 방법 화면이 만드는 rule:cand-…)이 있고 문서 규칙 하나를 빼 그 규칙의 절차가
    스스로 후보가 아니게 되면, 영수증의 절차 · 규칙이 그래프의 OUTPUTS 와 같고 비어 있지 않다."""
    first = commit(seeded_graph, plan_of(archive, 'HM-8'))
    assert first['candidate_activation'] == {}
    plan = plan_of(archive, 'HM-8', previous=first['batch'], document_id=first['document_id'], drop_rule='rule:hm-8-7-fin-cleaning')
    fms = sorted({p['failureMode'] for p in plan['procedures'] if p.get('failureMode')})
    with seeded_graph.driver.session() as session:
        for fm in fms:
            session.execute_write(skill_graph.ensure_candidate_rule, fm)
    receipt = commit(seeded_graph, plan)
    own = {r['id'] for r in plan['knowledge']['rules']}
    rows = seeded_graph.query('MATCH (r:Rule)-[:OUTPUTS]->(k:Skill) WHERE k._manual_document = $doc RETURN k.sopId AS sop, r.id AS rule', doc=plan['document'])
    linked = {}
    for row in rows:
        if row['rule'] not in own:
            linked.setdefault(row['sop'], []).append(row['rule'])
    assert linked and receipt['candidate_activation'] == {sop: sorted(rules) for sop, rules in linked.items()}, (receipt['candidate_activation'], linked)
    assert all(rules for rules in receipt['candidate_activation'].values())


def test_적재한_문서를_다시_열면_응답이_이미_적재된_판을_말한다(seeded_graph, archive):
    """전수 대조(2026-11-14): 이미 적재한 문서를 「보관한 원문 다시 열기」로 열면 응답에 적재 사실이 없어 화면이 「아직 AI가 문서를 읽기 전입니다」를
    보였다. 다시 열기 응답(GET …/sources/{id}/preview)은 지금 적재된 판(loaded)을 싣는다 — 적재 전에는 None, 되돌린 뒤에도 None, 같은
    문서의 다른 원문(개정본)을 열면 same_source 가 거짓이다."""
    from contextlib import contextmanager
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from procsvc import course_policy as cp, manual_api
    from procsvc.manual_approved_cache import ApprovedExtractions

    @contextmanager
    def driver():
        yield seeded_graph.driver
    app = FastAPI()
    app.state.course = cp.Policy(cp.Phase('pbl'))
    manual_api.register(app, archive_factory=lambda: archive, driver_factory=driver, tenant='hyd', audit=lambda *a, **k: None,
                        runtime_factory=lambda: None, approved_cache=ApprovedExtractions())
    client = TestClient(app)
    plan = plan_of(archive, 'HM-8')
    reopen = lambda source_id: client.get(f'/api/kg/manuals/sources/{source_id}/preview').json()      # noqa: E731
    before = reopen(plan['source_id'])
    assert before['loaded'] is None and before['previous_batch'] is None
    commit(seeded_graph, plan)
    after = reopen(plan['source_id'])
    loaded = after['loaded']
    assert after['previous_batch'] == plan['batch'] and loaded['batch'] == plan['batch'] and loaded['same_source'] is True
    assert (loaded['by'], loaded['procedures'], loaded['sections']) == (plan['by'], len(plan['procedures']), len(plan['sections']))
    assert loaded['at'] and loaded['filename'] == plan['filename']
    revised = archive.save('hyd', 'HM-8-개정.md', DOCS['HM-8']['raw'] + '\n\n(개정)\n'.encode(), document_id=plan['document_id'])
    assert reopen(revised['source_id'])['loaded']['same_source'] is False        # 같은 문서의 다른 원문: 적재된 것은 앞 원문의 판이다
    session_call(seeded_graph, manual_graph.rollback, 'hyd', plan['batch'], '담당자')
    assert reopen(plan['source_id'])['loaded'] is None


def test_적재한_파일을_새_문서로_다시_올리면_응답이_같은_원본으로_적재한_문서를_말한다(seeded_graph, archive):
    """2026-11-14: 이미 적재한 매뉴얼을 「새 문서 등록」으로 다시 올리면 새 문서가 생기고 응답에는 적재 사실이 없어, 화면이 「아직 AI가 문서를 읽기 전」을
    보이고 적재는 절차 번호가 먼저 적재한 문서와 겹쳐 「다른 원천/기존 지식이 소유합니다」로 끝났다. 올린 응답(POST …/preview)은 같은 원본 파일로 만든
    판이 적재돼 있는 다른 문서(same_original — 그 문서 id · 파일 이름 · 절차 수)를 싣는다. 적재 전 · 다른 내용의 파일 · 그 문서의 개정으로 올린 경우 ·
    되돌린 뒤에는 None 이다."""
    import base64
    from contextlib import contextmanager
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from procsvc import course_policy as cp, manual_api
    from procsvc.manual_approved_cache import ApprovedExtractions

    @contextmanager
    def driver():
        yield seeded_graph.driver
    app = FastAPI()
    app.state.course = cp.Policy(cp.Phase('pbl'))
    manual_api.register(app, archive_factory=lambda: archive, driver_factory=driver, tenant='hyd', audit=lambda *a, **k: None,
                        runtime_factory=lambda: None, approved_cache=ApprovedExtractions())
    client = TestClient(app)
    raw, name = DOCS['HM-8']['raw'], DOCS['HM-8']['filename']

    def upload(data, document_id=None):
        r = client.post('/api/kg/manuals/preview', json={'filename': name, 'data': base64.b64encode(data).decode(), 'document_id': document_id})
        assert r.status_code == 200, r.text
        return r.json()
    assert upload(raw)['same_original'] is None                       # 아직 아무것도 적재하지 않았다
    plan = plan_of(archive, 'HM-8')                                   # 같은 파일을 새 문서로 올려 적재한다
    commit(seeded_graph, plan)
    twin = upload(raw)                                                # 같은 파일을 「새 문서 등록」으로 한 번 더
    assert twin['document_id'] != plan['document_id'] and twin['loaded'] is None
    same = twin['same_original']
    assert (same['document_id'], same['batch'], same['filename'], same['procedures']) == (plan['document_id'], plan['batch'], plan['filename'], len(plan['procedures']))
    revise = upload(raw, document_id=same['document_id'])             # 화면의 [이 문서 개정]이 보내는 것
    assert revise['loaded']['same_source'] is True and revise['same_original'] is None
    assert upload(raw + '\n\n(다른 글)\n'.encode())['same_original'] is None          # 내용이 다른 파일은 같은 원본이 아니다
    session_call(seeded_graph, manual_graph.rollback, 'hyd', plan['batch'], '담당자')
    assert upload(raw)['same_original'] is None                       # 되돌린 문서는 적재된 판이 없다


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
def handover_doc():
    """강사 서명 묶음의 교대 인계 문서(HI-01) 검토본 한 건 — 시작의 적재 순서(class_knowledge.ORDER)에는 없고 학생이 실습에서 넣는 문서다.
    시작이 넣는 문서와 같은 함수(reviewed: 묶음 → 원문 sha256 대조 → 검토본)로 읽고, 학생이 포털에서 제안 그대로 검토 완료하는 것과 같은
    요청으로 만든다: 담당자 이름으로, 검토 방식 칸 없이(포털은 그 칸을 보내지 않는다). 묶음이 적어 둔 이 문서의 검토 방식
    (origin.review_method)은 검토 검증(manual_review.validate)이 받는 값이 아니라서, 시작의 적재처럼 그 값을 그대로 실으면 거절된다."""
    [item] = class_knowledge.reviewed(order=('HI-01',))
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


def test_적재하지_않은_파일을_새_문서로_다시_올리면_보관한_원문이_늘지_않고_적재한_뒤에는_새_문서가_되며_이미_쌓인_중복에서도_돈다(seeded_graph, archive):
    """V 8절 3(2026-11-16): 적재하지 않은 제공 문서의 줄을 누를 때마다(= 새 문서로 올리기) 새 문서가 생겨 「보관한 원문」에 같은 원문이 한 건씩 늘었다(HI-01 9건).
    같은 이름 · 같은 바이트이고 적재된 판이 없는 문서가 있으면 그 문서를 다시 쓴다(보관한 원문 수 그대로 · 같은 source_id — 이전 추출 결과가 이어진다).
    개정 · 새 문서 구분은 그대로다: 적재된 판이 있는 문서는 다시 쓰지 않아 새 문서가 되고 same_original 이 그 문서를 알린다. 이름이나 내용이 다르면 다른 원문이다.
    고치기 전에 쌓인 중복(같은 파일의 문서 여럿)이 있어도 가장 최근 것을 다시 쓰고 더 늘지 않는다."""
    import base64
    from contextlib import contextmanager
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from procsvc import course_policy as cp, manual_api
    from procsvc.manual_approved_cache import ApprovedExtractions

    @contextmanager
    def driver():
        yield seeded_graph.driver
    app = FastAPI()
    app.state.course = cp.Policy(cp.Phase('pbl'))
    manual_api.register(app, archive_factory=lambda: archive, driver_factory=driver, tenant='hyd', audit=lambda *a, **k: None,
                        runtime_factory=lambda: None, approved_cache=ApprovedExtractions())
    client = TestClient(app)
    raw, name = DOCS['HM-8']['raw'], DOCS['HM-8']['filename']

    def upload(data, filename=name, document_id=None):
        r = client.post('/api/kg/manuals/preview', json={'filename': filename, 'data': base64.b64encode(data).decode(), 'document_id': document_id})
        assert r.status_code == 200, r.text
        return r.json()
    total = lambda: client.get('/api/kg/manuals/sources').json()['total']      # noqa: E731 — 화면의 「보관한 원문 n건」
    # 고치기 전에 쌓인 중복: 같은 파일이 문서 셋으로 보관돼 있다(보관소에 직접 — 옛 판의 올리기가 하던 일)
    old = [archive.save('hyd', name, raw) for _ in range(3)]
    assert total() == 3 and len({s['document_id'] for s in old}) == 3
    first = upload(raw)
    again = upload(raw)
    assert total() == 3 and first['source_id'] == again['source_id'] and first['document_id'] in {s['document_id'] for s in old}
    assert first['loaded'] is None and first['same_original'] is None and first['status'] == 'READY'
    assert upload(raw, filename='copy-of-' + name)['document_id'] != first['document_id'] and total() == 4      # 이름이 다르면 다른 원문
    assert upload(raw + '\n(다른 글)\n'.encode())['document_id'] != first['document_id'] and total() == 5        # 내용이 다르면 다른 원문
    # 그 문서를 적재한 뒤: 고르지 않고 올리면 적재된 문서를 다시 쓰지 않는다(개정은 문서를 골라 올린다). 적재 안 된 옛 중복이 남아 있으면 그것을 다시 쓴다
    plan = plan_of(archive, 'HM-8', document_id=first['document_id'])
    commit(seeded_graph, plan)
    twin = upload(raw)
    assert twin['document_id'] != first['document_id'] and twin['same_original']['document_id'] == first['document_id'] and total() == 5
    assert upload(raw, document_id=first['document_id'])['loaded']['same_source'] is True and total() == 5      # [이 문서 개정]의 길은 그대로
    # 빈 보관소(중복이 없는 PC): 처음 올리면 문서가 하나 생기고, 그 뒤로는 그 문서를 다시 쓴다
    alone = ManualSources(archive.path + '.alone')
    app2 = FastAPI()
    app2.state.course = cp.Policy(cp.Phase('pbl'))
    manual_api.register(app2, archive_factory=lambda: alone, driver_factory=driver, tenant='hyd', audit=lambda *a, **k: None,
                        runtime_factory=lambda: None, approved_cache=ApprovedExtractions())
    c2 = TestClient(app2)
    post = lambda: c2.post('/api/kg/manuals/preview', json={'filename': 'own.md', 'data': base64.b64encode('# 내 문서\n\n본문\n'.encode()).decode()}).json()      # noqa: E731
    a, b = post(), post()
    assert a['source_id'] == b['source_id'] and c2.get('/api/kg/manuals/sources').json()['total'] == 1
