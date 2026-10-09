"""확정 TODO C1 라이브 검증 — 버려도 되는 Neo4j(검증 전용 컨테이너)에서만 돌린다. 그래프를 비운다(--i-know-this-wipes).

1. seed-diff: 옛 시드 파일(--orig-instances · --orig-a098, 커밋 전 사본)로 만든 그래프와 새 전체판 그래프를 비교한다.
   새 전체판 = 옛 그래프 + scenario_structure.cypher 추가분이어야 한다(회귀 동작 불변).
2. structure: 구조판을 적재하고 되읽기 단언(구조판 줄)을 돌린다 — 고장 지식 레이블이 비어 있어야 한다.
3. ingest: 구조판 위에 문서 A(HM-8) → B(PM-02 정기 점검표) → C(PR-07)를 추출 제안 → 검토 → 적재 경로로 넣는다
   (LLM 추출 대신 tests/c1_fixtures.py 대역). 판단 템플릿(t1 원인 · t3 스킬)과 결정표로 시나리오 지식이 읽히는지,
   전체판 되읽기 단언 · 스키마 검사(ontology_v2 validate)를 통과하는지, 구조판 시드를 다시 돌려도 문서 지식이 그대로인지,
   다른 문서가 참조 중인 문서는 되돌리기가 막히는지, 재적재 · 되돌리기가 되는지 본다.
   B는 판단 엔진(agentsvc.cards.evaluate)을 실제 그래프 템플릿(t3_dmn · t3_skills · t3_tradeoffs)으로 돌려 경쟁 순위를 본다.
4. full-conflict: 전체판 위에 문서 A를 적재하면 시드가 가진 고장 유형 때문에 거절되는지 본다.
사용: .venv/bin/python scripts/probe_c1_knowledge.py --uri bolt://127.0.0.1:17688 --password … --orig-instances … --orig-a098 … --i-know-this-wipes
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
for p in ('common', 'it/process', 'it/agent', 'tests', 'scripts'):
    sys.path.insert(0, str(ROOT / p))

import ontology_v2 as ov  # noqa: E402
import c1_fixtures as fx  # noqa: E402
from neo4j import GraphDatabase  # noqa: E402
from agentsvc import cards  # noqa: E402
from procsvc import manual_extraction, manual_graph, manual_knowledge, manual_review, skill_graph  # noqa: E402
from procsvc.manual_sources import ManualSources  # noqa: E402

JOURNAL = {'ManualIngestionBatch', 'ManualIngestionDocument', 'IngestionControl'}
results = []


def check(name, ok, detail=''):
    results.append(dict(check=name, ok=bool(ok), detail=detail))
    print(('PASS ' if ok else 'FAIL ') + name + (f' — {detail}' if detail else ''))


def wipe(s):
    s.run('MATCH (n) DETACH DELETE n').consume()


def load(s, texts):
    for t in texts:
        for st in ov.split_statements(t):
            s.run(st).consume()


def edition_texts(edition):
    return [ov.edition_filter((ov.V2 / f).read_text(encoding='utf-8'), edition) for f in ov.SEED_FILES]


def dump(s):
    nodes = {json.dumps(dict(l=sorted(r['l']), p=r['p']), sort_keys=True, ensure_ascii=False, default=str)
             for r in s.run('MATCH (n) RETURN labels(n) AS l, properties(n) AS p').data()}
    rels = {json.dumps(r, sort_keys=True, ensure_ascii=False, default=str)
            for r in s.run('MATCH (a)-[x]->(b) RETURN type(x) AS t, a.id AS a, b.id AS b, properties(x) AS p').data()}
    return nodes, rels


def run_checks(s, edition):
    bad = []
    for q in ov.edition_checks((ov.V2 / 'seed_checks.cypher').read_text(encoding='utf-8'), edition):
        bad += [r['problem'] for r in s.run(q).data()]
    return bad


def validate(s):
    nodes = [{'labels': r['l'], 'props': dict(r['p'])} for r in s.run('MATCH (n) RETURN labels(n) AS l, properties(n) AS p')
             if not set(r['l']) & JOURNAL]
    rels = [{'type': r['t'], 'a': r['a'], 'b': r['b'], 'la': r['la'], 'lb': r['lb'], 'props': dict(r['p'])} for r in s.run(
        'MATCH (a)-[x]->(b) RETURN type(x) AS t, a.id AS a, b.id AS b, labels(a) AS la, labels(b) AS lb, properties(x) AS p')]
    return ov.validate(nodes, rels, ov.load_schema())


def ingest(s, archive, name, text, spec, links, previous=None, document_id=None):
    source = archive.save('hyd', name, text.encode(), document_id=document_id)
    prop = manual_extraction.validate_proposal(source, fx.proposal(source, spec, links))
    body = fx.reviewed_body(source, prop, by='[C1 검증] 검토자')
    body['batch'] = str(uuid4())
    body['previous_batch'] = manual_graph.head(s, 'hyd', source['document_id']) if previous is None else previous
    plan = manual_review.validate(archive, 'hyd', body)
    manual_knowledge.check_graph(s, plan, manual_graph.skill_id)
    fms = sorted({p['failureMode'] for p in plan['procedures']})
    plan['candidate_rules'] = {fm: s.execute_read(lambda tx, fm=fm: skill_graph.candidate_rules(tx, fm)) for fm in fms}
    return source, manual_graph.commit(s, plan), manual_knowledge.conflicts(s, prop.get('knowledge'))


def template(name, **params):
    text = (ROOT / 'it/neo4j/templates' / name).read_text(encoding='utf-8')
    return '\n'.join(l for l in text.splitlines() if not l.strip().startswith('//'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--uri', required=True)
    ap.add_argument('--password', required=True)
    ap.add_argument('--orig-instances', required=True)
    ap.add_argument('--orig-a098', required=True)
    ap.add_argument('--out', default=str(ROOT / '.evidence/a161-c1/probe_c1_knowledge.json'))
    ap.add_argument('--i-know-this-wipes', action='store_true')
    a = ap.parse_args()
    if not a.i_know_this_wipes:
        sys.exit('이 검증은 그래프를 비운다. 검증 전용 Neo4j에서 --i-know-this-wipes로 실행하세요')
    with GraphDatabase.driver(a.uri, auth=('neo4j', a.password)) as d, d.session() as s:
        # 1. 전체판 = 옛 시드 + scenario_structure 추가분
        wipe(s)
        orig = [(ov.V2 / 'constraints.cypher').read_text(encoding='utf-8'), Path(a.orig_instances).read_text(encoding='utf-8'),
                Path(a.orig_a098).read_text(encoding='utf-8'), (ov.V2 / 'detector-patterns.cypher').read_text(encoding='utf-8')]
        load(s, orig)
        old_n, old_r = dump(s)
        wipe(s)
        load(s, edition_texts('full'))
        new_n, new_r = dump(s)
        check('전체판: 옛 시드의 노드 · 관계가 하나도 빠지거나 바뀌지 않음', not (old_n - new_n) and not (old_r - new_r),
              f'빠진 노드 {len(old_n - new_n)} · 빠진 관계 {len(old_r - new_r)}')
        added_n = sorted(json.loads(x)['p']['id'] for x in new_n - old_n)
        check('전체판: 더해진 노드는 scenario_structure 추가분뿐', set(added_n) == {'role:purchasing', 'in:spare-gap', 'in:po-amount',
              'in:lead-slack-days', 'pattern:spare-below-min', 'ks:pm-plan', 'part:return-filter', 'in:hours-since-pm',
              'in:next-scheduled-time', 'in:hours-if-deferred', 'in:pm-crew', 'in:spare-available', 'pattern:pm-due'}, ', '.join(added_n))
        check('전체판: 되읽기 단언 통과', not run_checks(s, 'full'), str(run_checks(s, 'full')))
        full_errs = validate(s)
        check('전체판: 스키마 검사(ontology_v2 validate)', not full_errs, '; '.join(full_errs[:5]))

        # 2. 구조판
        wipe(s)
        load(s, edition_texts('structure'))
        bad = run_checks(s, 'structure')
        check('구조판: 되읽기 단언 통과', not bad, str(bad))
        counts = {r['l']: r['n'] for r in s.run('MATCH (n) UNWIND labels(n) AS l RETURN l, count(*) AS n').data()}
        check('구조판: 고장 · 원인 · 증거 · 스킬 · 매뉴얼 절 · 예측 · 선례 없음',
              not any(counts.get(l) for l in fx_knowledge_labels()), json.dumps(counts, ensure_ascii=False))
        rules = sorted(r['id'] for r in s.run('MATCH (r:Rule) RETURN r.id AS id').data())
        check('구조판: 회사 규정 · 순위 정책만', rules == ['rule:avl', 'rule:rank-value', 'rule:ts1-hard'], str(rules))
        before = run_cause_template(s, 'COOLER_DEGRADATION')
        check('구조판: 문서 적재 전 쿨러 경보의 원인 후보 0', before == [], str(before))
        st_errs = validate(s)
        check('구조판: 스키마 검사', not st_errs, '; '.join(st_errs[:5]))

        # 3. 문서 적재
        archive = ManualSources(Path(tempfile.mkdtemp()) / 'manuals.sqlite')
        src_a, rec_a, _ = ingest(s, archive, fx.DOC_A.name, fx.DOC_A.read_text(encoding='utf-8'), fx.A_KNOWLEDGE, fx.A_LINKS)
        check('문서 A 적재: 고장 유형 1 · 원인 3 · 증거 4 · 규칙 5', {k: len(v) for k, v in rec_a['knowledge'].items()} ==
              dict(failure_modes=1, causes=3, evidence=4, rules=5), json.dumps(rec_a['knowledge'], ensure_ascii=False))
        causes = run_cause_template(s, 'COOLER_DEGRADATION')
        check('문서 A 뒤: 쿨러 경보 → 증상 → 고장 유형 → 원인 + 증거(t1 템플릿)',
              [c['causeId'] for c in causes][:1] == ['cause:cooler-fin-fouling'] and all(c['evidence'] for c in causes if c['causeId'] != 'cause:x'),
              json.dumps([(c['causeId'], c['prior'], len(c['evidence'])) for c in causes], ensure_ascii=False))
        cand = s.run("MATCH (:DecisionTable {id:'dt:action-candidates'})-[:HAS_RULE]->(r:Rule)-[t:TESTS]->(:InputData {id:'in:failure-mode'}) "
                     "WHERE t.value='fm:cooling-loss' MATCH (r)-[:OUTPUTS]->(k:Skill) RETURN r.id AS r, collect(k.sopId) AS sops").data()
        check('문서 A 뒤: 후보 규칙이 SOP-COOL · SOP-FAN을 낸다', cand and len(cand[0]['sops']) == 7, json.dumps(cand, ensure_ascii=False))
        sk = s.run(template('t3_skills.cypher'), ids=['skill:sop-cool-12']).data()
        check('문서 A 뒤: 카드가 원자 조치 값(팬 100 · 부하 80)을 읽는다(t3 템플릿)',
              sk and [(x['code'], x['value']) for x in sk[0]['actions']] == [('FAN_SET', 100), ('LOAD_SET', 80)] and sk[0]['approver']['id'] == 'role:operator',
              json.dumps(sk[0]['actions'] if sk else None, ensure_ascii=False))
        # 문서 B(정기 점검표): 예방 조치 스킬 · 패키지 단계 · 규칙(임계값 TESTS) · C가 기대는 펌프 고장 지식
        src_p, rec_p, _ = ingest(s, archive, fx.DOC_B.name, fx.DOC_B.read_text(encoding='utf-8'), fx.B_KNOWLEDGE, fx.B_LINKS)
        check('문서 B 적재: 고장 유형 1 · 원인 2 · 증거 2 · 규칙 9', {k: len(v) for k, v in rec_p['knowledge'].items()} ==
              dict(failure_modes=1, causes=2, evidence=2, rules=9), json.dumps(rec_p['knowledge'], ensure_ascii=False))
        pv = s.run("MATCH (:FailureMode {id:'fm:volumetric-loss'})-[r]->(k:Skill) WHERE k.sopId STARTS WITH 'SOP-PM' "
                   "RETURN type(r) AS t, count(*) AS n").data()
        check('문서 B 뒤: 정기 정비 SOP 7개가 모두 예방 조치(PREVENTED_BY)', pv == [dict(t='PREVENTED_BY', n=7)], json.dumps(pv))
        due = s.run("MATCH (p:AnomalyPattern {code:'PM_DUE'})-[t:TESTS]->(i:InputData)-[:SOURCED_FROM]->(src) "
                    "MATCH (:DecisionTable {id:'dt:action-candidates'})-[:HAS_RULE]->(r:Rule)-[x:TESTS]->(:InputData {id:'in:pattern'}) "
                    "WHERE x.value='PM_DUE' MATCH (r)-[:OUTPUTS]->(k:Skill) "
                    "RETURN i.id AS input, t.operator + toString(t.value) AS test, src.id AS source, collect(k.sopId) AS sops").data()
        check('문서 B 뒤: PM_DUE(CMMS 운전시간 ≥ 1950) → 후보 규칙 → 시행 방식 4',
              due and due[0]['source'] == 'sys:cmms' and sorted(due[0]['sops']) == fx.B_OPTIONS, json.dumps(due, ensure_ascii=False))
        t2 = [r['sopId'] for r in s.run(template('t2_skills.cypher'), cause='cause:pump-seal-wear').data()]
        check('문서 B 뒤: 펌프 경보 대응 후보(t2)에는 정기 정비 SOP가 없다', not [x for x in t2 if x.startswith('SOP-PM')], str(t2))
        ranked = live_rank(s, fx.B_OPTIONS, fx.B_FACTS)
        o = {x['sopId']: x for x in ranked['options']}
        check('문서 B 뒤: 실제 그래프로 판단 — 이번 정비 시간 단독(SOP-PM-11) 추천',
              ranked['recommended'] == 'skill:sop-pm-11', json.dumps([(x['rank'], x['sopId'], x['feasible'], x['score']) for x in ranked['options']]))
        check('문서 B 뒤: 미루기는 허용 오차 위반 제외 · 지금 정지는 오더 손실 감점 · 두 대 묶기는 인력 부족 감점',
              [v['rule'] for v in o['SOP-PM-13']['violations']] == ['rule:pm-defer-limit']
              and [p['rule'] for p in o['SOP-PM-12']['penalties']] == ['rule:pm-stop-order']
              and [p['rule'] for p in o['SOP-PM-14']['penalties']] == ['rule:pm-bundle-crew']
              and o['SOP-PM-11']['score'] > o['SOP-PM-14']['score'] > o['SOP-PM-12']['score'],
              json.dumps({k: (v['scoreParts'], [x['rule'] for x in v['violations'] + v['penalties'] + v['warnings']]) for k, v in o.items()}, ensure_ascii=False))
        flip = live_rank(s, fx.B_OPTIONS, dict(fx.B_FACTS, pm_crew_available=4))
        check('문서 B 뒤: 정비 인원 4명이면 두 대 묶기가 이긴다(값이 바뀌면 답이 바뀜)', flip['recommended'] == 'skill:sop-pm-14',
              json.dumps([(x['sopId'], x['score']) for x in flip['options']]))
        src_c, rec_c, _ = ingest(s, archive, fx.DOC_C.name, fx.DOC_C.read_text(encoding='utf-8'), fx.C_KNOWLEDGE, fx.C_LINKS)
        spare = s.run("MATCH (:DecisionTable {id:'dt:action-candidates'})-[:HAS_RULE]->(r:Rule)-[t:TESTS]->(:InputData {id:'in:pattern'}) "
                      "WHERE t.value='SPARE_BELOW_MIN' MATCH (r)-[:OUTPUTS]->(k:Skill)-[c:CONSISTS_OF]->(:Action {code:'PR_CREATE'}) "
                      "RETURN k.sopId AS sop, c.value AS supplier ORDER BY sop").data()
        check('문서 C 뒤: 재고 경보 후보 규칙 → 구매 SOP 3 · 공급사 값', [(r['sop'], r['supplier']) for r in spare] ==
              [('SOP-PUR-11', 'sup:b'), ('SOP-PUR-12', 'sup:a'), ('SOP-PUR-13', 'sup:c')], json.dumps(spare, ensure_ascii=False))
        # 재고 경보에는 진단 원인이 없다. 구매 SOP는 원인 한정(ADDRESSES)이므로, 부족한 부품을 쓰는 원인(Cause -INVOLVES_PART-> Part)을
        # 그래프에서 읽어 사실로 준다 — C 판단 에이전트가 할 일(C2/C3)과 같은 조회다.
        seal_cause = [r['c'] for r in s.run("MATCH (c:Cause)-[:INVOLVES_PART]->(:Part {id:'part:pump-seal'}) RETURN c.id AS c").data()]
        cr = live_rank(s, fx.C_PURCHASE, dict(pattern='SPARE_BELOW_MIN', spare_gap=-1, po_amount=330, lead_slack_days=2,
                                                 plc_mode='REMOTE_AUTO', plc_state='RUN', cause=seal_cause[0] if seal_cause else None,
                                                 failure_mode='fm:volumetric-loss'))
        co = {x['sopId']: x for x in cr['options']}
        check('문서 C 뒤: 순정(B-OEM) 추천 · 비승인 공급사(C트레이딩)는 AVL 규정으로 제외 · 저가(A정밀)는 전수 검사 비용 감점 · 300만 원 초과는 경고만(승인 1회)',
              set(co) == set(fx.C_PURCHASE) and cr['recommended'] == 'skill:sop-pur-11'
              and 'rule:pur-avl' in [v['rule'] for v in co['SOP-PUR-13']['violations']]
              and [p['rule'] for p in co['SOP-PUR-12']['penalties']] == ['rule:pur-inspection']
              and all(any(w['rule'] == 'rule:pur-amount' for w in x['warnings']) for x in co.values()),
              json.dumps([(x['rank'], x['sopId'], x['feasible'], x['score'], x['scoreParts']) for x in cr['options']], ensure_ascii=False))
        mixed = s.run("MATCH (r:Rule)-[:OUTPUTS]->(k:Skill) WHERE k.sopId STARTS WITH 'SOP-PUR' AND r.id <> 'rule:cand-spare-purchase' RETURN r.id AS r").data()
        check('문서 C 뒤: 구매 SOP가 다른 후보 규칙에 섞이지 않음', not mixed, str(mixed))
        comp = s.run("MATCH (:DecisionTable {id:'dt:compliance'})-[:HAS_RULE]->(r:Rule) RETURN r.id AS id, r.when AS w, r.effect AS e ORDER BY id").data()
        check('문서 C 뒤: 금액 전결 · AVL · 납기 규정 규칙', {'rule:pur-amount', 'rule:pur-avl', 'rule:pur-lead'} <= {r['id'] for r in comp},
              json.dumps(comp, ensure_ascii=False))
        bad = run_checks(s, 'full')
        # 이번에 적재하지 않은 주제(팬 진동 · 작동유 · 고진동 트립)의 패턴은 아직 고장 유형이 없다 — 그 문서를 적재하면 채워진다
        not_ingested = ('pattern:fan-vibration', 'pattern:oil-analysis', 'pattern:high-vibration-trip')
        real = [b for b in bad if 'empty label' not in b and 'seeded DecisionCase' not in b and not b.endswith(not_ingested)]
        check('적재 뒤: 전체판 불변식(고장 유형 · 스킬 · 규칙 · 원인)과 쿨러 · 펌프 패턴 → 고장 유형 연결', real == [], str(bad))
        errs = validate(s)
        check('적재 뒤: 스키마 검사(스키마 v2 그대로)', not errs, '; '.join(errs[:8]))

        # 시드를 다시 돌려도(kg-seed 재시작) 문서 지식은 그대로
        snap = dump(s)
        load(s, edition_texts('structure'))
        after_n, after_r = dump(s)
        added = sorted(json.loads(x)['t'] + ' ' + str(json.loads(x)['a']) + '→' + str(json.loads(x)['b']) for x in after_r - snap[1])
        # 시드 재실행이 더하는 것은 경보 시작 이벤트 ↔ 패턴 연결(CORRELATES, 문서와 무관한 기존 시드 순서 특성)뿐이어야 한다
        check('구조판 시드 재실행: 문서가 가진 노드 · 관계를 지우거나 바꾸지 않음', not (snap[0] - after_n) and not (snap[1] - after_r)
              and after_n == snap[0] and all(a.startswith('CORRELATES ev:alert') for a in added), f'더한 관계 {added}')

        # 되돌리기 · 재적재
        try:
            manual_graph.rollback(s, 'hyd', rec_p['batch'], '[C1 검증]')
            check('참조 중인 문서(B 정기 점검표)는 C가 있는 동안 되돌리기 거절', False)
        except manual_graph.Conflict as exc:
            check('참조 중인 문서(B 정기 점검표)는 C가 있는 동안 되돌리기 거절', True, str(exc))
        _, rec_a2, conflicts = ingest(s, archive, fx.DOC_A.name, fx.DOC_A.read_text(encoding='utf-8'), fx.A_KNOWLEDGE, fx.A_LINKS, document_id=src_a['document_id'])
        check('문서 A 재적재(같은 문서 새 배치): 충돌 없이 교체', rec_a2['status'] == 'ACTIVE' and rec_a2['batch'] != rec_a['batch'],
              f"미리보기 knowledge_conflicts(자기 문서 포함 표시) {len(conflicts)}")
        for rec in (rec_c, rec_a2, rec_a, rec_p):
            out = manual_graph.rollback(s, 'hyd', rec['batch'], '[C1 검증]')
            check(f"되돌리기 {rec['filename']} {rec['batch'][:8]}", out['status'] == 'ROLLED_BACK', json.dumps(out, ensure_ascii=False))
        counts = {r['l']: r['n'] for r in s.run('MATCH (n) UNWIND labels(n) AS l RETURN l, count(*) AS n').data()}
        check('모두 되돌린 뒤: 구조판 상태로 복귀', not any(counts.get(l) for l in fx_knowledge_labels()) and not run_checks(s, 'structure'),
              json.dumps({k: v for k, v in counts.items() if k in fx_knowledge_labels()}, ensure_ascii=False))

        # 4. 전체판 위 문서 A → 시드가 가진 고장 유형과 충돌
        wipe(s)
        load(s, edition_texts('full'))
        archive = ManualSources(Path(tempfile.mkdtemp()) / 'manuals.sqlite')
        src = archive.save('hyd', fx.DOC_A.name, fx.DOC_A.read_bytes())
        conflicts = manual_knowledge.conflicts(s, fx.proposal(src, fx.A_KNOWLEDGE, fx.A_LINKS)['knowledge'])
        check('전체판 미리보기: 시드가 가진 고장 유형 · 원인 id를 충돌로 알린다', any(c['id'] == 'fm:cooling-loss' and c['owner'] == 'seed' for c in conflicts),
              json.dumps(conflicts, ensure_ascii=False)[:300])
        try:
            ingest(s, archive, fx.DOC_A.name, fx.DOC_A.read_text(encoding='utf-8'), fx.A_KNOWLEDGE, fx.A_LINKS)
            check('전체판 적재: 시드 고장 유형을 덮어쓰지 않고 거절', False)
        except manual_graph.Conflict as exc:
            check('전체판 적재: 시드 고장 유형을 덮어쓰지 않고 거절', 'fm:cooling-loss' in str(exc) or 'cause:' in str(exc), str(exc))
        try:
            ingest(s, archive, fx.DOC_B.name, fx.DOC_B.read_text(encoding='utf-8'), fx.B_KNOWLEDGE, fx.B_LINKS)
            check('전체판 적재: 문서 B도 시드 펌프 지식을 덮어쓰지 않고 거절', False)
        except manual_graph.Conflict as exc:
            check('전체판 적재: 문서 B도 시드 펌프 지식을 덮어쓰지 않고 거절', 'fm:volumetric-loss' in str(exc) or 'cause:' in str(exc), str(exc))
        wipe(s)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding='utf-8')
    failed = [r for r in results if not r['ok']]
    print(f'{len(results) - len(failed)}/{len(results)} PASS')
    return 1 if failed else 0


def fx_knowledge_labels():
    return ('FailureMode', 'Cause', 'Evidence', 'Skill', 'Step', 'ManualSection', 'Forecast', 'DecisionCase', 'Incident')


def live_rank(s, sops, facts):
    """The agent's judgment engine on the live graph: t3_dmn · t3_skills · t3_tradeoffs rows → cards.evaluate.
    Work-order cards carry no PLC command, so their forecast is the present operating point (nominal 48 ℃)."""
    dmn = s.run(template('t3_dmn.cypher')).data()
    ids = [r['id'] for r in s.run('MATCH (k:Skill) WHERE k.sopId IN $sops RETURN k.id AS id', sops=sops).data()]
    skills = {r['skillId']: r for r in s.run(template('t3_skills.cypher'), ids=ids).data()}
    tradeoffs = s.run(template('t3_tradeoffs.cypher'), ids=ids).data()
    forecasts = {k: {'sv:ts1': dict(value=48.0, variableName='유온', unit='℃', method='nominal', id='fc:nominal')} for k in skills}
    suppliers = {r['id']: r for r in s.run(template('t3_suppliers.cypher')).data()}
    return cards.evaluate(dmn, skills, facts, forecasts, tradeoffs, [], suppliers)


def run_cause_template(s, pattern):
    return s.run(template('t1_causes.cypher'), pattern=pattern, asset='HYD-01').data()


if __name__ == '__main__':
    sys.exit(main())
