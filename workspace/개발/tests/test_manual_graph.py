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
    # 가상 설비의 고장 조치는 이 시스템의 업무 시스템이 수행한다 — 설비 명령은 SCADA, 정비 요청은 CMMS 하나씩(지식 지도 · 판단의 수행 시스템)
    performed = {r['sop']: (r['kind'], r['by']) for r in seeded_graph.query(
        'MATCH (k:Skill) WHERE k._manual_document = $doc AND k.kind <> "reference" '
        'RETURN k.sopId AS sop, k.kind AS kind, COLLECT { MATCH (s:System)-[:HAS_SKILL]->(k) RETURN s.id } AS by', doc=plan['document'])}
    assert performed and all(by == (['sys:scada'] if kind == 'control' else ['sys:cmms']) for kind, by in performed.values()), performed


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
    out = session_call(seeded_graph, manual_graph.rollback, 'hyd', second['batch'], 'user:me')
    assert (out['status'], out['restored_batch']) == ('ROLLED_BACK', first['batch'])
    assert RULE not in rule_ids(seeded_graph)
    assert session_call(seeded_graph, manual_graph.head, 'hyd', first['document_id']) == first['batch']


def test_첫_판을_되돌리면_그_문서의_지식이_모두_빠진다(seeded_graph, archive):
    plan = plan_of(archive, 'HM-8')
    commit(seeded_graph, plan)
    session_call(seeded_graph, manual_graph.rollback, 'hyd', plan['batch'], 'user:me')
    left = seeded_graph.query('MATCH (n) WHERE n._manual_document = $doc AND (n:Skill OR n:Step OR n:Rule OR n:FailureMode OR n:Cause '
                              'OR n:Evidence) RETURN count(n) AS n', doc=plan['document'])[0]['n']
    assert left == 0 and session_call(seeded_graph, manual_graph.head, 'hyd', plan['document_id']) is None


def _decided(graph, skill, cause):
    """사람이 승인한 처리 건의 그래프 투영(procsvc.case_projection 의 실제 질의 — 사건과 판단 사례): 사건은 원인 cause 로 진단됐고 판단은 skill 을 골랐다."""
    from procsvc import case_projection as cp
    tag = uuid4().hex[:8]
    graph.query(cp.INCIDENT_Q, key=f'Incident:INC-{tag}', revision=1, payload_hash='h', id=f'INC-{tag}', alert=f'ALR-{tag}',
                created='2026-11-22T00:00:00+00:00', asset='HYD-01', pattern='COOLER_DEGRADATION', cause=cause, trip=None, source_alert='{}',
                status='CLOSED', reason=None, closed=None, cleared=True, command=None, work_order=None)
    graph.query(cp.DECISION_CASE_Q, key=f'DecisionCase:DEC-{tag}', revision=1, payload_hash='h', id=f'case:DEC-{tag}',
                at='2026-11-22T00:00:00+00:00', reason='시험', followed=True, skill=skill, role='role:operator', incident=f'INC-{tag}', status='EXECUTED', model=None)
    return f'INC-{tag}', f'case:DEC-{tag}'


def _history(graph, incident, case):
    return graph.query('MATCH (i:Incident {id:$i}), (x:DecisionCase {id:$x}) '
                       'RETURN i.diagnosedCause AS cause, x.chosenSkill AS skill, '
                       '[(i)-[:DIAGNOSED_AS]->(c) | c.id] AS diagnosed, [(x)-[:CHOSE]->(k) | k.id] AS chose', i=incident, x=case)[0]


def test_판단_이력이_가리키는_문서를_비워도_되고_다시_넣으면_이력이_다시_이어진다(seeded_graph, archive):
    """학생이 흐름 A를 승인한 뒤(판단 사례가 문서의 조치 방법 · 원인을 가리킴) 그 문서를 등록 이력에서 되돌리면 「판단 이력이 연결돼 있어 거절」로
    막혔고, [기준으로 되돌리기] 전체도 멈췄다 — 미리 채운 시작 상태가 그 길을 가렸다. 기록은 남고(가리키던 id 를 제 속성으로) 연결만 빠지며,
    같은 문서를 다시 넣으면 그 연결이 다시 선다. 화면 조치 방법 지우기(skill_graph.remove)와 같은 규칙이다."""
    skill, cause = 'skill:sop-cool-11', 'cause:cooler-fin-fouling'
    plan = plan_of(archive, 'HM-8')
    commit(seeded_graph, plan)
    incident, case = _decided(seeded_graph, skill, cause)
    assert _history(seeded_graph, incident, case) == {'cause': cause, 'skill': skill, 'diagnosed': [cause], 'chose': [skill]}

    out = session_call(seeded_graph, manual_graph.rollback, 'hyd', plan['batch'], 'user:me')
    assert out['status'] == 'ROLLED_BACK' and out['history_kept'] == []
    assert {(h['node'], h['type'], h['count']) for h in out['history_detached']} == {(f'Skill {skill}', 'CHOSE', 1), (f'Cause {cause}', 'DIAGNOSED_AS', 1)}
    assert _history(seeded_graph, incident, case) == {'cause': cause, 'skill': skill, 'diagnosed': [], 'chose': []}     # 기록은 남고 연결만 빠짐
    assert not seeded_graph.query('MATCH (n) WHERE n.id IN [$s, $c] RETURN n.id AS id', s=skill, c=cause)

    again = plan_of(archive, 'HM-8', document_id=plan['document_id'])
    receipt = commit(seeded_graph, again)
    assert {(h['node'], h['type']) for h in receipt['history_reattached']} == {(f'Skill {skill}', 'CHOSE'), (f'Cause {cause}', 'DIAGNOSED_AS')}
    assert _history(seeded_graph, incident, case) == {'cause': cause, 'skill': skill, 'diagnosed': [cause], 'chose': [skill]}
    # 다시 이어진 연결은 그 문서의 그래프가 아니라 이력이다 — 되돌리기의 「적재 뒤 그래프가 바뀜」 검사에 걸리지 않고 다시 비울 수 있다
    out = session_call(seeded_graph, manual_graph.rollback, 'hyd', again['batch'], 'user:me')
    assert out['status'] == 'ROLLED_BACK' and len(out['history_detached']) == 2


def test_개정이_판단_이력이_가리키는_조치_방법을_빼도_적재되고_기록은_남는다(seeded_graph, archive):
    """회사는 썼던 절차를 은퇴시킨다 — 그 절차를 고른 옛 판단 기록이 개정을 막지 않는다(기록은 그 절차의 id 를 갖고 남는다)."""
    first = plan_of(archive, 'HM-8')
    commit(seeded_graph, first)
    # 이 문서의 규칙 · 정비 묶음이 가리키지 않는 절차 — 가리키는 절차를 빼면 검토 검증이 먼저 막는다(그 판단은 이 시험의 몫이 아니다)
    cited = json.dumps(DOCS['HM-8']['proposal']['knowledge'], ensure_ascii=False)
    dropped = next(p['id'] for p in first['procedures'] if p.get('kind') != 'reference' and p['id'] not in cited)
    skill = manual_graph.skill_id(dropped)
    incident, case = _decided(seeded_graph, skill, 'cause:cooler-fin-fouling')
    item = deepcopy(DOCS['HM-8'])
    item['proposal']['procedures'] = [p for p in item['proposal']['procedures'] if p['id'] != dropped]
    second = plan_of(archive, item, previous=first['batch'], document_id=first['document_id'])
    receipt = commit(seeded_graph, second)
    assert [(h['node'], h['type']) for h in receipt['history_detached']] == [(f'Skill {skill}', 'CHOSE')]
    assert _history(seeded_graph, incident, case)['chose'] == [] and _history(seeded_graph, incident, case)['skill'] == skill


def test_최신_판이_아니면_되돌리지_않는다(seeded_graph, archive):
    first = plan_of(archive, 'HM-8')
    commit(seeded_graph, first)
    second = plan_of(archive, 'HM-8', previous=first['batch'], document_id=first['document_id'])
    commit(seeded_graph, second)
    with pytest.raises(manual_graph.Conflict, match='최신 판본부터'):
        session_call(seeded_graph, manual_graph.rollback, 'hyd', first['batch'], 'user:me')


def test_적재_뒤_누가_그래프를_고쳤으면_되돌리지_않고_멈춘다(seeded_graph, archive):
    plan = plan_of(archive, 'HM-8')
    commit(seeded_graph, plan)
    seeded_graph.query('MATCH (r:Rule {id:$id}) SET r.annotation = $text', id=RULE, text='누가 고친 설명')
    with pytest.raises(manual_graph.Conflict, match='바뀌어 되돌릴 수 없습니다'):
        session_call(seeded_graph, manual_graph.rollback, 'hyd', plan['batch'], 'user:me')


@pytest.mark.parametrize('by', ['', '   ', None])
def test_되돌리는_담당자_없이는_되돌리지_않는다(seeded_graph, by):
    with pytest.raises(ValueError, match='담당자'):
        session_call(seeded_graph, manual_graph.rollback, 'hyd', 'b', by)


def test_없는_배치를_되돌리면_KeyError다(seeded_graph):
    with pytest.raises(KeyError):
        session_call(seeded_graph, manual_graph.rollback, 'hyd', str(uuid4()), 'user:me')


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


def test_절차의_수행_시스템은_의미_검사가_정하고_없으면_목표_모습을_만들지_않는다(archive):
    """적재가 절차 종류만 보고 CMMS · SCADA 를 수행 시스템으로 채우면 다른 설비의 절차도 이 시스템이 수행한다고 적혔다. 그 값은 의미 검사(check_graph →
    manual_knowledge.performers)가 지금 그래프의 설비 구조로 정한 것만 쓴다 — 규칙이 없는 다른 설비 문서(APU)도 그 판정 없이는 그래프 모습을 만들지 않는다."""
    import apu_document as apu
    plan = manual_review.validate(archive, 'hyd', apu.reviewed(apu_preview(archive)))
    with pytest.raises(ValueError, match='수행 시스템이 정해지지 않았습니다'):
        manual_graph.desired(plan)
    plan['performers'] = {}
    with pytest.raises(ValueError, match='SOP-APU-05: 이 절차의 수행 시스템이 정해지지 않았습니다'):
        manual_graph.desired(plan)


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


def _without_cause(archive, cause, **kw):
    """검토에서 원인 하나를 [적재에서 제외]한 검토본(그 원인을 가리키는 증거 · 절차의 대상 원인은 남는다 — 화면 밖 API 길)."""
    item = DOCS['HM-8']
    source = archive.save('hyd', item['filename'], item['raw'], **({'document_id': kw['document_id']} if kw.get('document_id') else {}))
    body = class_knowledge.commit_body(item, {'source_id': source['source_id'], 'document_id': source['document_id'], 'filename': item['filename'],
                                              'batch': str(uuid4()), 'previous_batch': kw.get('previous')})
    body['knowledge']['causes'] = [c for c in body['knowledge']['causes'] if c['id'] != cause]
    return manual_review.validate(archive, 'hyd', body)


def test_뺀_원인을_남은_항목이_가리키면_그_원인과_가리키는_항목을_이름으로_말하며_거절한다(seeded_graph, archive):
    """C3(2026-11-22): 검토에서 원인을 빼면 처음 적재는 「Cause cause:…: 대상이 없거나 유형이 변경됐습니다」, 개정은 「관계의 대상이 없어 전체 적재를
    취소했습니다」로 끝났다 — 무엇을 함께 빼야 하는지 말하지 않았다. 이제 한 번의 대조가 빠지는 원인과 그것을 가리키는 항목(증거 · 조치 방법)을 이름으로
    말한다. 처음 적재(지식 지도에 없음)와 개정(이 판에서 빠짐)이 같은 꼴이고, 그래프는 바뀌지 않는다."""
    cause = 'cause:fan-drive-fault'
    with pytest.raises(manual_graph.Conflict) as first:
        commit(seeded_graph, _without_cause(archive, cause))
    said = str(first.value)
    assert said.startswith(f'원인 {cause}는 이 검토본에도 지금 지식 지도에도 없는데 ') and '증거 「' in said and '조치 방법 「' in said, said
    assert '가리키는 항목도 함께 빼거나 이 항목을 남기세요' in said and 'Cause ' not in said
    assert not seeded_graph.query('MATCH (n:Skill) RETURN n.id LIMIT 1')            # 아무것도 쓰지 않았다

    full = commit(seeded_graph, plan_of(archive, 'HM-8'))
    with pytest.raises(manual_graph.Conflict) as revised:
        commit(seeded_graph, _without_cause(archive, cause, document_id=full['document_id'], previous=full['batch']))
    said = str(revised.value)
    assert said.startswith('원인 「팬 구동 불량」은 이 판에서 빠지는데 ') and '증거 「' in said and '조치 방법 「' in said, said
    assert session_call(seeded_graph, manual_graph.head, 'hyd', full['document_id']) == full['batch']


def test_조치_방법_화면에서_만든_조치_방법이_문서의_고장_유형에_이어져도_개정은_되고_그_고장_유형을_빼는_판은_길을_말하며_거절한다(seeded_graph, archive):
    """C4(2026-11-22): 수업 그래프의 고장 유형은 모두 문서가 만든 것이라 [새 조치 방법] 하나가 그 문서에 관계를 그었고, 그 문서의 개정 · 되돌리기가
    「적재 뒤 문서 그래프가 바뀌었습니다 … 기록에 없는 관계」로 막혔다. 그 관계는 조치 방법 화면이 관리하는 바깥 참조다 — 고장 유형이 남는 개정은
    지나고 화면 관계도 그대로 남으며, 그 고장 유형을 지우는 되돌리기는 무엇을 먼저 할지 말하며 거절한다."""
    from procsvc.main import SKILL_Q
    first = commit(seeded_graph, plan_of(archive, 'HM-8'))
    values = {'name': '팬 덮개 청소', 'description': '시험', 'kind': 'work_order', 'sopId': 'SOP-TEST-31', 'failureMode': 'fm:cooler-cooling-loss',
              'relation': 'REMEDIED_BY', 'steps': ['덮개를 연다', '먼지를 턴다'], 'approver': 'role:maint-mgr', 'affects': None}
    with seeded_graph.driver.session() as s:
        skill_graph.write(s, SKILL_Q, 'skill:sop-test-31', values, create=True, by='user:me')
    second = commit(seeded_graph, plan_of(archive, 'HM-8', previous=first['batch'], document_id=first['document_id']))
    assert second['status'] == 'ACTIVE'
    assert seeded_graph.query("MATCH (:FailureMode {id:'fm:cooler-cooling-loss'})-[:REMEDIED_BY]->(k:Skill {id:'skill:sop-test-31'}) RETURN k.id AS id")
    assert session_call(seeded_graph, manual_graph.rollback, 'hyd', second['batch'], 'user:me')['status'] == 'ROLLED_BACK'     # 앞 판에도 그 고장 유형이 있다
    with pytest.raises(manual_graph.Conflict) as refused:
        session_call(seeded_graph, manual_graph.rollback, 'hyd', first['batch'], 'user:me')
    assert str(refused.value).startswith('「지식 › 조치 방법」에서 만든 조치 방법 「팬 덮개 청소」가 이 판에서 빠지는 고장 유형 「쿨러 냉각 성능 상실」에 이어져 있습니다'), str(refused.value)
    with seeded_graph.driver.session() as s:
        skill_graph.remove(s, 'skill:sop-test-31', by='user:me')
    assert session_call(seeded_graph, manual_graph.rollback, 'hyd', first['batch'], 'user:me')['status'] == 'ROLLED_BACK'


def test_다른_문서가_가리키는_노드를_빼는_되돌리기는_그_문서를_파일_이름으로_부른다(seeded_graph, archive):
    """C11(2026-11-22): 「문서 3f…e9:4b1c-…가 참조하는 노드는 삭제/되돌리기를 할 수 없습니다: (FailureMode fm:…)-[:CAUSES]…」 — 어느 문서인지 알 수
    없었다. 가리키는 문서는 그 판을 적재한 파일 이름으로, 노드는 화면 이름으로 말한다."""
    hm8 = commit(seeded_graph, plan_of(archive, 'HM-8'))
    other = plan_of(archive, 'PM-02')
    other['knowledge']['causes'][0]['failure_mode'] = 'fm:cooler-cooling-loss'          # 다른 문서의 원인이 HM-8 의 고장 유형을 가리킨다
    commit(seeded_graph, other)
    with pytest.raises(manual_graph.Conflict) as refused:
        session_call(seeded_graph, manual_graph.rollback, 'hyd', hm8['batch'], 'user:me')
    said = str(refused.value)
    assert said.startswith(f"고장 유형 「쿨러 냉각 성능 상실」은 다른 문서 「{DOCS['PM-02']['filename']}」가 가리키고 있어 이 판에서 뺄 수 없습니다"), said
    assert other['document'] not in said


def test_이미_지식에_있는_항목이나_절차_번호를_다시_넣는_문서는_그_항목과_가진_문서를_이름으로_말하며_거절한다(seeded_graph, archive):
    """C11 과 같은 갈래(2026-11-23): 다른 문서가 이미 넣은 원인을 다시 정의하면 「Cause cause:…: 다른 원천/기존 지식이 소유합니다. 덮어쓰지 않았습니다」,
    절차 번호가 겹치면 「SOP 번호 …는 다른 원천의 스킬이 사용 중입니다」 — 영문 레이블 · 내부 id 뿐이고 누가 가졌는지 · 무엇을 하면 되는지가 없었다.
    항목은 화면 이름으로, 가진 쪽은 그 판을 적재한 파일 이름으로 부르고 할 일(적재에서 제외 · 개정으로 올리기)을 말한다. 덮어쓰지는 않는다."""
    hm8 = commit(seeded_graph, plan_of(archive, 'HM-8'))
    before = seeded_graph.query("MATCH (c:Cause {id:'cause:cooler-fin-fouling'}) RETURN c.prior AS prior")
    other = plan_of(archive, 'PM-02')
    other['knowledge']['causes'][0] = dict(other['knowledge']['causes'][0], id='cause:cooler-fin-fouling', name='쿨러 핀 오염', prior=0.1)
    # 검토 화면이 적재 전에 받는 알림(manual_api 가 미리 보기에 싣는 knowledge_conflicts)도 가진 문서를 파일 이름으로 싣는다
    held = session_call(seeded_graph, manual_knowledge.conflicts, other['knowledge'], other['document'])
    assert [(c['id'], c['label'], c['kind'], c.get('owner_name')) for c in held] == \
        [('cause:cooler-fin-fouling', 'Cause', 'other_document', DOCS['HM-8']['filename'])], held
    with pytest.raises(manual_graph.Conflict) as refused:
        commit(seeded_graph, other)
    said = str(refused.value)
    assert said.startswith(f"원인 「쿨러 핀 오염」은 다른 문서 「{DOCS['HM-8']['filename']}」의 같은 항목이 이미 지식에 있어 덮어쓰지 않았습니다"), said
    assert '적재에서 제외하세요' in said and 'Cause' not in said and hm8['batch'] not in said and other['document'] not in said
    assert seeded_graph.query("MATCH (c:Cause {id:'cause:cooler-fin-fouling'}) RETURN c.prior AS prior") == before
    again = plan_of(archive, 'HM-8')                       # 같은 파일을 새 문서로 — 절차 번호가 먼저 적재한 문서와 겹친다
    assert again['document_id'] != hm8['document_id']
    with pytest.raises(manual_graph.Conflict) as refused:
        commit(seeded_graph, again)
    said = str(refused.value)
    assert said.startswith('절차 번호 SOP-') and f"다른 문서 「{DOCS['HM-8']['filename']}」의 조치 방법이 이미 씁니다" in said and '개정으로 올리고' in said, said
    assert 'Skill' not in said and '스킬' not in said


def test_거절_문장의_노드_종류_이름은_지식_지도_화면의_이름과_같다():
    """manual_graph.LABEL_KO(서버 거절 문장)와 it/portal/www/enterprise.js LABEL_KO(지식 지도 화면)가 같은 노드 종류를 다른 이름으로 부르지 않는다."""
    import re
    from conftest import WWW
    js = (WWW / 'enterprise.js').read_text(encoding='utf-8')
    block = js[js.index('const LABEL_KO = {'):js.index('};', js.index('const LABEL_KO = {'))]
    screen = dict(re.findall(r"(\w+): '([^']+)'", block))
    assert {k: screen.get(k) for k in manual_graph.LABEL_KO} == manual_graph.LABEL_KO


# ---------------------------------------------------------------- 다른 설비 문서 — 새 항목(구성 요소 · 증상 · 센서)을 사람이 골라 넣는 길
def apu_preview(archive, document_id=None, previous=None):
    """다른 설비의 실제 규모 문서(apu_document — 지하철 차량 APU)를 올려 추출 계약을 지난 제안: 화면이 받는 추출 결과의 꼴."""
    import apu_document as apu
    from procsvc import manual_extraction
    source = archive.save('hyd', apu.FILENAME, apu.RAW, **({'document_id': document_id} if document_id else {}))
    checked = manual_extraction.validate_proposal(source, apu.proposal(source['source_id']))
    return dict(checked, document_id=source['document_id'], filename=source['filename'], previous_batch=previous)


APU_IDS = ('MATCH (n) WHERE any(p IN ["comp:apu-", "sym:apu-", "sen:apu-", "fm:apu-", "cause:apu-", "evd:apu-", "skill:sop-apu"] WHERE n.id STARTS WITH p) '
           'RETURN labels(n)[0] AS label, n.id AS id')


def apu_nodes(graph):
    return {(r['label'], r['id']) for r in graph.query(APU_IDS)}


def test_다른_설비_문서의_새_항목을_골라_넣으면_그_설비의_구조에_이어진_지식이_되고_되돌리기_다시_적재_개정이_같은_규칙이다(seeded_graph, archive):
    """학생이 PBL 에서 자기 설비(유압이 아닌 지하철 차량 APU)의 매뉴얼을 올린다. 전에는 문서 적재가 구성 요소 · 증상을 만들지 않고 증거 태그는 유압 수집
    태그만 받아, 이 문서는 「참고 절차 — 원문만 보관」으로만 들어갔다. 이제 추출이 원문 인용과 함께 낸 새 항목(구성 요소 9 · 증상 7 · 센서 15)을 사람이
    항목마다 넣기 · 제외로 고르고, 넣기를 고른 것만 그 문서가 가진다. 실제 Neo4j(kg-seed 가 끝난 그래프)에서:
      ① 적재 전 검사: 고칠 곳 0건. 참고로 판단 엔진이 평가하지 않는 증거 6건 · 지금 지식과 이름이 같은 새 구성 요소(구동 모터) · 판단 엔진의 후보 규칙이 닿지 않는 절차
      ② 기대는 항목이 남은 새 항목(모터 전류 센서가 붙은 구동 모터)을 제외하면 그 까닭으로 막히고 아무것도 들어가지 않는다
      ③ 기대는 것이 없는 새 항목(유량 펄스 · 타워 배출 감지 센서)을 제외하면 적재된다 — 고장 → 원인 → 증거(센서 태그) → 조치 절차가 구성 요소 · 증상에 이어지고,
         증거는 SQL 없이 판단 엔진이 평가하지 않는다는 문장을 가진다. 지식 지도 · 카탈로그에 보이고, 시작의 되읽기 검사 · 스키마 검사를 깨지 않으며, 설비(HYD)의
         구조(구성 요소 · 경보가 닿는 고장 유형)는 그대로다
      ④ 되돌리면 모두 빠지고, 다시 적재하면 같고, 개정으로 새 항목 하나를 빼면 그것만 빠지며 개정을 되돌리면 돌아온다"""
    import sys
    from pathlib import Path
    import apu_document as apu
    from procsvc import manual_preflight
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
    import ontology_v2 as onto
    root = Path(__file__).resolve().parents[3]
    plant = 'MATCH (a:Asset)-[:HAS_COMPONENT]->(c:Component) RETURN a.code AS a, c.id AS c ORDER BY a, c'
    plant_before = seeded_graph.query(plant)
    preview = apu_preview(archive)
    catalog = session_call(seeded_graph, manual_knowledge.catalog)
    # ① 적재 전 검사
    checked = manual_preflight.validate(preview, catalog)
    assert checked['technical_ready'] is True and checked['issues'] == [], checked['issues']
    notes = {}
    for n in checked['notices']:
        notes.setdefault(n['code'], []).append(n)
    assert len(notes['EVIDENCE_NOT_EVALUATED']) == 6 and all('판단 엔진이 이 증거를 평가하지 않습니다' in n['message'] for n in notes['EVIDENCE_NOT_EVALUATED'])
    assert [n['sop'] for n in notes['NEW_ITEM_SAME_NAME']] == ['comp:apu-motor'] and '구동 모터' in notes['NEW_ITEM_SAME_NAME'][0]['message']
    assert {n['sop'] for n in notes['CANDIDATE_OUTSIDE_PLANT']} == {p['id'] for p in preview['procedures'] if p['link'].get('kind') != 'reference'}
    assert all('HYD-01 · HYD-02 · HYD-03' in n['message'] for n in notes['CANDIDATE_OUTSIDE_PLANT'])
    # ② 기대는 항목이 남은 새 항목을 제외하면 막힌다
    blocked = manual_review.validate(archive, 'hyd', apu.reviewed(preview, drop={'comp:apu-motor'}))
    with pytest.raises(manual_graph.Conflict, match='구성 요소 comp:apu-motor은 이 검토본에도 지금 지식 지도에도 없는데 센서 「모터 전류」가 가리킵니다'):
        commit(seeded_graph, blocked)
    assert apu_nodes(seeded_graph) == set()
    # ③ 넣기 · 제외를 고른 검토본을 적재한다
    dropped = {'sen:apu-caudal-impulses', 'sen:apu-pressure-switch'}
    plan = manual_review.validate(archive, 'hyd', apu.reviewed(preview, drop=dropped))
    receipt = commit(seeded_graph, plan)
    assert (len(receipt['knowledge']['components']), len(receipt['knowledge']['symptoms']), len(receipt['knowledge']['sensors'])) == (9, 7, 13)
    first = apu_nodes(seeded_graph)
    assert ('Sensor', 'sen:apu-caudal-impulses') not in first and ('Component', 'comp:apu-motor') in first and ('Sensor', 'sen:apu-tp2') in first
    [path] = seeded_graph.query(
        'MATCH (sym:Symptom {id:"sym:apu-reservoir-drop"})-[:INDICATES]->(fm:FailureMode {id:"fm:apu-air-leak"})-[:OCCURS_IN]->(c:Component), '
        '(cause:Cause)-[:CAUSES]->(fm), (cause)-[:EVIDENCED_BY]->(e:Evidence {id:"evd:apu-leak-test-drop"}), '
        '(fm)-[:REMEDIED_BY]->(k:Skill {sopId:"SOP-APU-12"})-[:ADDRESSES]->(cause), '
        '(sym)-[:OBSERVED_BY]->(s:Sensor {tag:"Reservoirs"})<-[:MONITORED_BY]-(:Component {id:"comp:apu-reservoir"}) '
        'RETURN c.id AS component, cause.id AS cause, e.sql AS sql, e.note AS note, e.tag AS tag, e.rule AS rule')
    assert (path['component'], path['cause'], path['sql'], path['tag']) == ('comp:apu-piping', 'cause:apu-joint-leak', None, 'Reservoirs')
    assert path['rule'] == 'max(Reservoirs) - min(Reservoirs) over 600s > 0.5' and path['note'] == manual_knowledge.unevaluated_note('Reservoirs', '저장 탱크 압력')
    [ref] = seeded_graph.query('MATCH (k:Skill {sopId:"SOP-APU4-1"}) RETURN k.description AS d, k.kind AS kind')
    assert (ref['d'], ref['kind']) == (f'문서 {apu.FILENAME}의 참고 절차(실행하지 않음)', 'reference')     # 학생이 올린 문서를 「제공 문서」라 하지 않는다
    # 다른 설비의 절차는 이 시스템의 업무 시스템(CMMS · SCADA)이 수행한다고 적지 않는다 — 그 실행은 그 설비 시스템을 도구 서버로 연결한 흐름이 한다.
    # 적재 계획도 그 판정(수행 시스템 없음)을 싣고, 영수증 · 조치 방법 화면의 같은 질의(main.SKILL_Q 의 performers)가 빈 목록이 된다
    apu_sops = [p['id'] for p in plan['procedures'] if p['kind'] != 'reference']
    assert len(apu_sops) == 10 and plan['performers'] == {sop: None for sop in apu_sops}, plan['performers']
    assert seeded_graph.query('MATCH (s:System)-[:HAS_SKILL]->(k:Skill) WHERE k.sopId STARTS WITH "SOP-APU" RETURN s.id AS s, k.sopId AS k') == []
    # 설비(HYD)의 구조는 그대로 — 문서는 설비를 만들지 않고, 설비의 경보가 닿는 고장 유형에 다른 설비의 지식이 섞이지 않는다
    assert seeded_graph.query(plant) == plant_before
    assert seeded_graph.query('MATCH (:AnomalyPattern)-[:DETECTS]->(:Symptom)-[:INDICATES]->(fm:FailureMode) '
                              'WHERE fm.id STARTS WITH "fm:apu-" RETURN fm.id AS id') == []
    # 지식 지도(에이전트 /api/ontology/graph 와 같은 템플릿) · 카탈로그
    templates = root / 'it' / 'neo4j' / 'templates'
    shown = {r['id'] for r in seeded_graph.query((templates / 't0_graph_nodes.cypher').read_text(encoding='utf-8'), asset='HYD-01', ns='')}
    assert {i for _, i in first} <= shown
    edges = {(r['from'], r['type'], r['to']) for r in seeded_graph.query((templates / 't0_graph_edges.cypher').read_text(encoding='utf-8'), asset='HYD-01', ns='')}
    assert {('fm:apu-air-leak', 'OCCURS_IN', 'comp:apu-piping'), ('comp:apu-reservoir', 'MONITORED_BY', 'sen:apu-reservoirs'),
            ('sym:apu-reservoir-drop', 'OBSERVED_BY', 'sen:apu-reservoirs')} <= edges
    after = session_call(seeded_graph, manual_knowledge.catalog)
    assets = {c['id']: c['assets'] for c in after['components']}
    assert assets['comp:apu-piping'] == [] and assets['comp:cooler'] == ['HYD-01', 'HYD-02', 'HYD-03']
    assert 'Reservoirs' in {s['tag'] for s in after['sensors']}
    # 시작의 되읽기 검사 · 스키마 검사
    checks = [line for line in (root / 'it' / 'neo4j' / 'v2' / 'seed_checks.cypher').read_text(encoding='utf-8').splitlines()
              if line and not line.startswith('//')]
    assert [row['problem'] for q in checks for row in seeded_graph.query(q)] == []
    with seeded_graph.driver.session() as session:
        nodes, rels, _ = onto.base_scope(*onto.read_rows(session))
    assert onto.validate(nodes, rels, onto.load_schema()) == []
    # ④ 되돌리기 · 다시 적재 · 개정
    session_call(seeded_graph, manual_graph.rollback, 'hyd', receipt['batch'], '보전 담당 학생')
    assert apu_nodes(seeded_graph) == set()
    again = commit(seeded_graph, manual_review.validate(archive, 'hyd', apu.reviewed(preview, drop=dropped)))
    assert apu_nodes(seeded_graph) == first
    revised = manual_review.validate(archive, 'hyd', apu.reviewed(preview, drop=dropped | {'sen:apu-h1'}, previous=again['batch']))
    removed = session_call(seeded_graph, manual_graph.revision_preview, revised)['removed']
    assert [(n['labels'], n['id']) for n in removed if n['labels'][0] in ('Sensor', 'Component', 'Symptom')] == [(['Sensor'], 'sen:apu-h1')]
    revision = commit(seeded_graph, revised)
    assert apu_nodes(seeded_graph) == first - {('Sensor', 'sen:apu-h1')}
    session_call(seeded_graph, manual_graph.rollback, 'hyd', revision['batch'], '보전 담당 학생')
    assert apu_nodes(seeded_graph) == first
