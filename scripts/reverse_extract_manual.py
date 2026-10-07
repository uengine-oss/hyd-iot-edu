"""A094 — reverse-extract a manual from the live ontology (what the graph actually knows, written back as a document).

    .venv314/Scripts/python scripts/reverse_extract_manual.py [out.md]

Purpose: measure how large a document the current scenario/schema/ontology implies, and give a round-trip fixture
(ontology → document → extraction should return the same sections/SOPs/steps). Nothing is invented: every line comes
from a node property; prose the ontology does not hold (descriptions, wiring, specifications) is simply absent.
"""
import os
import sys
from pathlib import Path

from neo4j import GraphDatabase

URI = os.environ.get('NEO4J_URI', 'bolt://127.0.0.1:7687')
AUTH = (os.environ.get('NEO4J_USER', 'neo4j'), os.environ.get('NEO4J_PASSWORD', 'hydpass123'))


def rows(session, q):
    return [r.data() for r in session.run(q)]


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('tests/fixtures/manuals/HM-REV_ontology-reverse.md')
    with GraphDatabase.driver(URI, auth=AUTH) as drv, drv.session() as s:
        sections = rows(s, 'MATCH (m:ManualSection) OPTIONAL MATCH (m)-[:DERIVED_FROM]-(r:Rule) OPTIONAL MATCH (m)-[:REFERS_TO]-(st:Step) '
                           'RETURN m.id AS id, m.title AS title, m.excerpt AS excerpt, collect(DISTINCT r.id) AS rules, collect(DISTINCT st.id) AS steps ORDER BY m.id')
        skills = rows(s, 'MATCH (k:Skill) OPTIONAL MATCH (k)-[:HAS_STEP]->(st:Step) OPTIONAL MATCH (f:FailureMode)-[rel:REMEDIED_BY|MITIGATED_BY]->(k) '
                         'WITH k, st, collect(DISTINCT type(rel) + " " + f.name) AS fms ORDER BY st.order '
                         'RETURN k.id AS id, k.name AS name, k.kind AS kind, k.description AS code, k.sopId AS sop, collect({order: st.order, text: st.text, manual: null, id: st.id}) AS steps, fms ORDER BY k.id')
        fms = rows(s, 'MATCH (f:FailureMode) OPTIONAL MATCH (f)-[:OCCURS_IN]->(c:Component) OPTIONAL MATCH (f)-[:CAUSES]->(ca:Cause) OPTIONAL MATCH (f)-[:INDICATES]->(sy:Symptom) '
                      'OPTIONAL MATCH (f)-[:LEADS_TO]->(g:FailureMode) RETURN f.id AS id, f.name AS name, c.name AS comp, collect(DISTINCT ca.name) AS causes, '
                      'collect(DISTINCT sy.name) AS symptoms, collect(DISTINCT g.name) AS leads ORDER BY f.id')
        tables = rows(s, 'MATCH (t:DecisionTable)-[:HAS_RULE]->(r:Rule) WITH t, r ORDER BY r.order RETURN t.id AS id, t.name AS name, '
                         'collect({id: r.id, when: r.when, effect: r.effect, note: r.annotation, order: r.order}) AS rules ORDER BY t.id')
        evidence = rows(s, 'MATCH (e:Evidence) RETURN e.id AS id, e.name AS name, e.rule AS rule, e.tag AS tag, e.windowSeconds AS win, e.weight AS weight ORDER BY e.id')
        inputs = rows(s, 'MATCH (i:InputData) RETURN i.id AS id, i.name AS name, i.variable AS binding, i.typeRef AS derive ORDER BY i.id')
        parts = rows(s, 'MATCH (p:Part) OPTIONAL MATCH (p)-[q:SUPPLIED_BY]->(su:Supplier) RETURN p.id AS id, p.name AS name, '
                        'collect({supplier: su.name, avl: su.avl, price: q.price, lead: q.leadDays}) AS quotes ORDER BY p.id')
    doc = ['# HYD 운전·정비 지식 (온톨로지 역추출, 교육용 가상 설비)', '',
           '이 문서는 라이브 온톨로지(Neo4j)의 노드·관계를 문서 형식으로 되돌린 것이다. 온톨로지에 없는 설명·사양·배선은 들어 있지 않다.', '']
    doc += ['# 1장 고장 유형', '']
    for f in fms:
        doc += [f"## {f['id']} {f['name']}", '', f"발생 부품: {f['comp'] or '-'}. 원인: {', '.join(x for x in f['causes'] if x) or '-'}. 징후: {', '.join(x for x in f['symptoms'] if x) or '-'}. 이어지는 고장: {', '.join(x for x in f['leads'] if x) or '-'}.", '']
    doc += ['# 2장 매뉴얼 절', '']
    for m in sections:
        doc += [f"## {m['id']} {m['title']}", '', m['excerpt'] or '', '',
                f"근거 규칙: {', '.join(x for x in m['rules'] if x) or '-'}. 참조 단계: {', '.join(x for x in m['steps'] if x) or '-'}.", '']
    doc += ['# 3장 조치 절차', '']
    for k in skills:
        steps = [st for st in k['steps'] if st['text']]
        doc += [f"### {k['sop'] or k['id']} {k['name']}", f"종류: {k['kind'] or '-'}. 설명: {k['code'] or '-'}. 적용 고장: {', '.join(k['fms']) or '-'}."]
        doc += [f"{st['order']}. {st['text']}" + (f" (절 {st['manual']})" if st['manual'] else '') for st in steps] + ['']
    doc += ['# 4장 판정 기준 (결정표)', '']
    for t in tables:
        doc += [f"## {t['id']} {t['name']}", '', '| 순서 | 조건 | 효과 | 설명 |', '|---|---|---|---|']
        doc += [f"| {r['order']} | {r['when']} | {r['effect']} | {r['note'] or ''} |" for r in t['rules']] + ['']
    doc += ['# 5장 근거 창', '', '| 근거 | 이름 | 규칙 | 태그 | 창(초) | 가중치 |', '|---|---|---|---|---|---|']
    doc += [f"| {e['id']} | {e['name']} | {e['rule']} | {e['tag'] or ''} | {e['win'] or ''} | {e['weight'] or ''} |" for e in evidence] + ['']
    doc += ['# 6장 입력 항목', '', '| 입력 | 이름 | 변수 | 형 |', '|---|---|---|---|']
    doc += [f"| {i['id']} | {i['name']} | {i['binding'] or ''} | {i['derive'] or ''} |" for i in inputs] + ['']
    doc += ['# 7장 예비품과 공급사', '']
    for p in parts:
        doc += [f"- {p['id']} {p['name']}: " + '; '.join(f"{q['supplier']}(AVL {q['avl']}, {q['price']}, {q['lead']}일)" for q in p['quotes'] if q['supplier']) ]
    text = '\n'.join(doc) + '\n'
    out.write_text(text, encoding='utf-8', newline='\n')
    print(f"{out} lines={text.count(chr(10))} chars={len(text)} bytes={len(text.encode('utf-8'))} sections={len(sections)} skills={len(skills)} "
          f"steps={sum(len([x for x in k['steps'] if x['text']]) for k in skills)} rules={sum(len(t['rules']) for t in tables)} evidence={len(evidence)} inputs={len(inputs)}")


if __name__ == '__main__':
    main()
