"""A079 — whole-ontology semantic connectivity audit (meeting L1~30: BSC · 프로세스 · 리소스 · 진단 · 조치 · 실행이 한 그래프로 이어진다).

    .venv314/Scripts/python scripts/probe_semantic_links.py --out .evidence/reaudit/a079-semantic-<n>

Read-only Neo4j (bolt 127.0.0.1:7687). Two parts:
  1. schema conformance — every relationship declared in it/neo4j/v2/schema_prompt.md (## 관계) is compared with the live graph:
     declared-but-absent, present-but-undeclared, and N:1 / 1:1 cardinality violations.
  2. golden questions — cross-layer questions the meeting implies, each answered by a real path query; an offender list says
     exactly which node breaks the chain. Version-level FlowNodes (ProcessVersion) are checked through MAPS_TO; the semantic
     edges live on the ontology-level Process nodes.
No writes. Findings are gaps for a knowledge author or expert, not auto-fixed here (no invented domain knowledge).
"""
import argparse
import json
import re
from pathlib import Path

from neo4j import GraphDatabase

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / 'it/neo4j/v2/schema_prompt.md'
EXEC_LABELS = {'WorkItem', 'CaseProjection', 'ExecutionProjection', 'ProcessInstance', 'ProcessVersion', 'KnowledgeEdit',
               'IngestionBatch', 'ManualIngestionBatch', 'ManualIngestionDocument', 'IngestionControl'}
REL_RE = re.compile(r'^- `\(:([A-Za-z|]+)\)-\[:([A-Z_]+)(?: \{[^}]*\})?\]->\(:([A-Za-z|]+)\)` (N:1|1:1|1:N|N:M)')


def declared_relations():
    out = []
    text = SCHEMA.read_text(encoding='utf8')
    body = text.split('## 관계', 1)[1]
    for line in body.splitlines():
        m = REL_RE.match(line.strip())
        if m:
            out.append(dict(froms=m.group(1).split('|'), rel=m.group(2), tos=m.group(3).split('|'), card=m.group(4)))
    return out


GOLDEN = [
    ('Q01 모든 센서가 상태 변수를 거쳐 성과 지표까지 닿는다 (리소스→BSC)',
     "MATCH (s:Sensor) WHERE NOT EXISTS { (s)-[:OBSERVES]->(:StateVariable)-[:INFLUENCES*1..4]->(:Measure) } RETURN s.id AS id"),
    ('Q02 모든 고장 유형에 원인이 있거나, 원인이 있는 선행 고장이 있다 (진단; A098 전문가 질문 3-A: 트립은 선행 고장의 결과)',
     "MATCH (f:FailureMode) WHERE NOT (:Cause)-[:CAUSES]->(f) AND NOT EXISTS { (:Cause)-[:CAUSES]->(:FailureMode)-[:LEADS_TO]->(f) } RETURN f.id AS id"),
    ('Q03 모든 고장 유형에 조치(스킬)가 하나 이상 있다 (진단→조치)',
     "MATCH (f:FailureMode) WHERE NOT (f)-[:MITIGATED_BY|REMEDIED_BY]->(:Skill) RETURN f.id AS id"),
    ('Q04 모든 스킬이 성과 지표에 닿는다 (조치→BSC: AFFECTS 직접 또는 상태 변수 경로)',
     "MATCH (k:Skill) WHERE NOT EXISTS { (k)-[:AFFECTS]->(:Measure) } AND NOT EXISTS { (k)-[:AFFECTS]->(:StateVariable)-[:INFLUENCES*1..4]->(:Measure) } RETURN k.id AS id"),
    ('Q05 모든 스킬에 승인 역할이 있고 그 역할은 부서에 속한다 (조치→리소스)',
     "MATCH (k:Skill) WHERE NOT EXISTS { (k)-[:APPROVED_BY]->(:Role)-[:MEMBER_OF]->(:OrgUnit) } RETURN k.id AS id"),
    ('Q06 모든 스킬 단계가 매뉴얼 절→지식 출처로 추적된다 (조치→출처)',
     "MATCH (k:Skill)-[:HAS_STEP]->(st:Step) WHERE NOT EXISTS { (st)-[:REFERS_TO]->(:ManualSection)-[:PART_OF]->(:KnowledgeSource) } RETURN DISTINCT k.id AS id"),
    ('Q07 판단이 요구하는 모든 입력에 출처 시스템/센서가 있다 (판단→리소스)',
     "MATCH (:Decision)-[:REQUIRES_INPUT]->(i:InputData) WHERE NOT (i)-[:SOURCED_FROM]->() RETURN i.id AS id"),
    ('Q08 모든 규칙에 출처(DERIVED_FROM)가 있다 (규칙→출처)',
     "MATCH (r:Rule) WHERE NOT (r)-[:DERIVED_FROM]->() RETURN r.id AS id"),
    ('Q09 모든 판단에 통제 출처(GOVERNED_BY)와 결정표가 있다',
     "MATCH (d:Decision) WHERE NOT (d)-[:GOVERNED_BY]->(:KnowledgeSource) OR NOT (d)-[:IMPLEMENTED_BY]->(:DecisionTable) RETURN d.id AS id"),
    ('Q10 온톨로지 프로세스가 BSC 목표와 대상 설비를 모두 가진다 (프로세스→BSC·리소스)',
     "MATCH (p:Process) WHERE NOT (p)-[:ACHIEVES]->(:Objective) OR NOT (p)-[:ACTS_ON]->(:Asset) RETURN p.id AS id"),
    ('Q11 온톨로지 프로세스의 모든 작업에 수행자(역할/시스템)가 있다 (프로세스→리소스)',
     "MATCH (:Process)-[:HAS_NODE]->(t:Task) WHERE NOT (t)-[:PERFORMED_BY]->() RETURN t.id AS id"),
    ('Q12 온톨로지 프로세스의 판단 규칙 작업은 판단을 부른다 (프로세스→DMN)',
     "MATCH (:Process)-[:HAS_NODE]->(t:Task {taskType:'businessRule'}) WHERE NOT (t)-[:INVOKES]->(:Decision) RETURN t.id AS id"),
    ('Q13 온톨로지 프로세스의 메시지 시작 이벤트는 경보 패턴과 연결된다 (이벤트→진단; catchAll 제외)',
     "MATCH (:Process)-[:HAS_NODE]->(e:Event {position:'start', eventDefinition:'message'}) WHERE NOT (e)-[:CORRELATES]->(:AnomalyPattern) AND coalesce(e.catchAll, false) = false RETURN e.id AS id"),
    ('Q14 모든 경보 패턴이 증상→고장 유형까지 닿는다 (ISO 13374 SD→HA)',
     "MATCH (a:AnomalyPattern) WHERE NOT EXISTS { (a)-[:DETECTS]->(:Symptom)-[:INDICATES]->(:FailureMode) } RETURN a.id AS id"),
    ('Q15 모든 증상이 센서에서 보이거나, 사람이 입력하는 항목으로 보인다 (경보 패턴이 검사하는 InputData에 출처 시스템이 있음; A098 사용자 결정: 오일 분석은 사람 입력)',
     "MATCH (s:Symptom) WHERE NOT (s)-[:OBSERVED_BY]->(:Sensor) "
     "AND NOT EXISTS { (:AnomalyPattern)-[:DETECTS]->(s) } RETURN s.id AS id "
     "UNION MATCH (s:Symptom) WHERE NOT (s)-[:OBSERVED_BY]->(:Sensor) "
     "AND NOT EXISTS { (p:AnomalyPattern)-[:DETECTS]->(s) WHERE EXISTS { (p)-[:TESTS]->(:InputData)-[:SOURCED_FROM]->(:System) } } RETURN s.id AS id"),
    ('Q16 BSC: 모든 목표가 관점에 속하고 모든 지표가 목표를 측정하며 부서가 소유한다',
     "MATCH (o:Objective) WHERE NOT (o)-[:IN_PERSPECTIVE]->() RETURN o.id AS id UNION MATCH (m:Measure) WHERE NOT (m)-[:MEASURES]->() OR NOT (m)-[:OWNED_BY]->() RETURN m.id AS id"),
    ('Q17 BSC 전략맵 인과는 아래 관점에서 위 관점으로만 간다',
     "MATCH (o:Objective)-[:SUPPORTS]->(t:Objective) MATCH (o)-[:IN_PERSPECTIVE]->(a),(t)-[:IN_PERSPECTIVE]->(b) WHERE a.order > b.order RETURN o.id+'→'+t.id AS id"),
    ('Q18 온톨로지 프로세스를 가진 실행 버전의 모든 흐름 노드가 온톨로지 노드에 대응한다 (실행→프로세스)',
     "MATCH (v:ProcessVersion)-[:HAS_NODE]->(n:FlowNode) WHERE NOT (n)-[:MAPS_TO]->() AND v.ontology_ref IS NOT NULL AND EXISTS { MATCH (p:Process {id: v.ontology_ref}) } RETURN n.id AS id"),
    ('Q19 처리된 사건은 경보 패턴→증상→고장 유형→스킬까지 설명된다 (실행→진단→조치)',
     "MATCH (pi:ProcessInstance)-[:HANDLES]->(inc:Incident)-[:RAISED_BY]->(a:AnomalyPattern) WHERE NOT EXISTS { (a)-[:DETECTS]->(:Symptom)-[:INDICATES]->(:FailureMode)-[:MITIGATED_BY|REMEDIED_BY]->(:Skill) } RETURN DISTINCT inc.id AS id"),
    ('Q20 사람의 판단 사례가 고른 스킬은 성과 지표에 닿는다 (실행→BSC)',
     "MATCH (c:DecisionCase)-[:CHOSE]->(k:Skill) WHERE NOT EXISTS { (k)-[:AFFECTS]->(:Measure) } AND NOT EXISTS { (k)-[:AFFECTS]->(:StateVariable)-[:INFLUENCES*1..4]->(:Measure) } RETURN DISTINCT k.id AS id"),
    ('Q21 판정된 원인은 그 사건의 고장 유형을 일으키는 원인이다 (진단 정합)',
     "MATCH (inc:Incident)-[:DIAGNOSED_AS]->(c:Cause) MATCH (inc)-[:RAISED_BY]->(a:AnomalyPattern)-[:DETECTS]->(:Symptom)-[:INDICATES]->(f:FailureMode) WITH inc, c, collect(DISTINCT f) AS fms WHERE NONE(f IN fms WHERE (c)-[:CAUSES]->(f)) RETURN DISTINCT inc.id+' '+c.id AS id"),
    ('Q22 고장 유형의 모든 조치(스킬)는 그 고장 유형의 후보 규칙이 내놓는다 (지식→판단 도달; A090: 시드 근본 조치 4건이 빠져 있었다)',
     "MATCH (f:FailureMode)-[:MITIGATED_BY|REMEDIED_BY]->(k:Skill) "
     "WHERE NOT EXISTS { MATCH (:DecisionTable {id:'dt:action-candidates'})-[:HAS_RULE]-(r:Rule)-[t:TESTS]->(:InputData {variable:'failure_mode'}) WHERE t.value = f.id AND (r)-[:OUTPUTS]->(k) } "
     "RETURN f.id+' → '+k.id AS id"),
]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True); ap.add_argument('--uri', default='bolt://127.0.0.1:7687')
    args = ap.parse_args(); out = Path(args.out); out.mkdir(parents=True, exist_ok=False)
    report = {'scope': __doc__, 'schema': {}, 'golden': {}}
    def save(): (out / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding='utf8')
    driver = GraphDatabase.driver(args.uri, auth=('neo4j', 'hydpass123'))
    with driver.session() as s:
        def rows(q, **p): return s.execute_read(lambda tx: tx.run(q, **p).data())
        # ---- 1. schema conformance
        # every label pair counts (a Task is labelled Task:FlowNode; the schema names the specific label)
        live = {}
        for r in rows("MATCH (a)-[r]->(b) RETURN labels(a) AS a, type(r) AS rel, labels(b) AS b, count(*) AS n"):
            for la in r['a']:
                for lb in r['b']:
                    live[(la, r['rel'], lb)] = live.get((la, r['rel'], lb), 0) + r['n']
        declared = declared_relations()
        absent, present, undeclared, violations = [], [], [], []
        allowed = set()
        for d in declared:
            pairs = [(f, d['rel'], t) for f in d['froms'] for t in d['tos']]
            allowed.update(pairs)
            n = sum(live.get(pr, 0) for pr in pairs)
            (present if n else absent).append(dict(d, count=n))
            if d['card'] in ('N:1', '1:1') and n:
                labels = '|'.join(d['froms'])
                bad = rows(f"MATCH (a)-[r:{d['rel']}]->(b) WHERE any(l IN labels(a) WHERE l IN $fr) WITH a, count(DISTINCT b) AS c WHERE c > 1 RETURN a.id AS id, c LIMIT 20", fr=d['froms'])
                if bad: violations.append(dict(rel=d['rel'], froms=d['froms'], card=d['card'], offenders=bad))
        seen = set()
        for r in rows("MATCH (a)-[r]->(b) RETURN labels(a) AS a, type(r) AS rel, labels(b) AS b, count(*) AS n"):
            if set(r['a']) & EXEC_LABELS or set(r['b']) & EXEC_LABELS: continue
            if not any((la, r['rel'], lb) in allowed for la in r['a'] for lb in r['b']):
                key = ('|'.join(r['a']), r['rel'], '|'.join(r['b']))
                if key not in seen:
                    seen.add(key); undeclared.append(dict(a=key[0], rel=r['rel'], b=key[2], n=r['n']))
        report['schema'] = dict(declared=len(declared), present=len(present), absent=absent, undeclared=undeclared, cardinality_violations=violations)
        print(f"schema: declared {len(declared)} · present {len(present)} · absent {len(absent)} · undeclared {len(undeclared)} · cardinality violations {len(violations)}", flush=True)
        for d in absent: print('  ABSENT  ', '|'.join(d['froms']), d['rel'], '|'.join(d['tos']), d['card'])
        for u in undeclared: print('  UNDECLARED', u['a'], u['rel'], u['b'], u['n'])
        for v in violations: print('  CARDINALITY', v['rel'], v['card'], v['offenders'][:3])
        save()
        # ---- 2. golden questions
        passed = 0
        for name, q in GOLDEN:
            offenders = [r['id'] for r in rows(q)]
            ok = not offenders
            passed += ok
            report['golden'][name] = dict(passed=ok, offenders=offenders[:50], count=len(offenders), query=q)
            print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else f'  ({len(offenders)}) ' + json.dumps(offenders[:6], ensure_ascii=False)), flush=True)
            save()
        print(f"golden questions passed {passed}/{len(GOLDEN)}", flush=True)
    driver.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
