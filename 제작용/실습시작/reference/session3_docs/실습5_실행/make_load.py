"""강사 참조: 검토 결과(approved만)와 원문 절 구조로 결과/load.cypher를 만든다. 학생 배포 금지.

모델 확장(이번 단계에서 새로 만드는 것):
  (:Document {id})  (:Section {id})-[:IN_DOCUMENT]->(:Document)
  (:Procedure {id})-[:DEFINED_IN]->(:Section)
  (:Knowledge:<Step|Precondition|Prohibition|Completion|UnitValue> {id, …출처·검토})-[:STATED_IN]->(:Section)
  (:Procedure)-[:HAS_STEP {order}]->(:Step), (:Procedure)-[:HAS_CONDITION]->(:Knowledge)
  (:Knowledge)-[:REFERS_TO]->(:Procedure|:Section)      quote에 적힌 ID(refs)만
  (:Knowledge)-[:ABOUT_QUANTITY]->(:Quantity)           기존 모델 ID. quote에 태그·물리량 이름이 있을 때만
기존 모델 노드는 MATCH로만 찾고 만들거나 고치지 않는다. 연결할 기존 ID가 없는 태그는 unresolved_tags로 남긴다.
"""
from pathlib import Path
import json
import re

HERE = Path(__file__).resolve().parent
LABEL = {'step': 'Step', 'precondition': 'Precondition', 'prohibition': 'Prohibition', 'completion': 'Completion', 'unit_value': 'UnitValue'}


def lit(v):
    if v is None:
        return 'null'
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, list):
        return '[' + ', '.join(lit(x) for x in v) + ']'
    return json.dumps(str(v), ensure_ascii=False)


def mp(d):
    return '{' + ', '.join(f'{k}: {lit(v)}' for k, v in d.items() if v is not None) + '}'


def structure(md):
    sections, procs, cur = {}, {}, '머리말'
    for line in md.splitlines():
        m = re.match(r'^##\s+(\S+)\s*(.*)$', line)
        if m and not line.startswith('###'):
            cur = m.group(1); sections[cur] = m.group(2); continue
        p = re.match(r'^###\s+(SOP-[A-Z]+-\d+)\s*(.*)$', line)
        if p:
            procs[p.group(1)] = (p.group(2), cur)
    return sections, procs


def main():
    review = json.loads((HERE / '입력/검토결과/HM-8_검토.json').read_text(encoding='utf-8'))
    graph = json.loads((HERE / '입력/모델/graph.json').read_text(encoding='utf-8'))
    quantities = {n['props']['id']: n['props']['name'] for n in graph['nodes'] if 'Quantity' in n['labels']}
    by_tag = {qid.split(':', 1)[1]: qid for qid in quantities}
    by_name = {name: qid for qid, name in quantities.items()}
    titles = {'HM-8': '유압 파워유닛 쿨러 팬 정비 매뉴얼'}
    md = (HERE / '자료/원문' / review['source_file']).read_text(encoding='utf-8')
    sections, procs = structure(md)
    doc = review['doc_id']
    out = [f'// 생성: make_load.py — {review["source_file"]} 검토본(approved만). 다시 실행해도 MERGE로 늘지 않는다.']
    out.append(f'MERGE (d:Document {{id: {lit(doc)}}}) SET d += {mp({"title": titles.get(doc), "file": review["source_file"], "sha256": review["source_sha256"]})};')
    for sid, title in sections.items():
        out.append(f'MATCH (d:Document {{id: {lit(doc)}}}) MERGE (s:Section {{id: {lit(sid)}}}) SET s += {mp({"doc_id": doc, "title": title})} MERGE (s)-[:IN_DOCUMENT]->(d);')
    for pid, (name, sid) in procs.items():
        out.append(f'MATCH (s:Section {{id: {lit(sid)}}}) MERGE (p:Procedure {{id: {lit(pid)}}}) SET p += {mp({"name": name, "doc_id": doc})} MERGE (p)-[:DEFINED_IN]->(s);')
    unresolved, skipped = {}, []
    for c in review['candidates']:
        if c['status'] != 'approved':
            skipped.append(c['id']); continue
        props = {k: c.get(k) for k in ['kind', 'text', 'quote', 'order', 'value', 'value_max', 'unit', 'comparator', 'value_text', 'decision', 'reason', 'origin']}
        props.update(doc_id=doc, source_sha256=review['source_sha256'], reviewer=review['review']['reviewer'], reviewed_at=review['review']['reviewed_at'], status='approved')
        tags = sorted(set(re.findall(r'(?<![A-Za-z])([A-Z]{2}\d)(?!\d)', c['quote'])))
        qids = sorted({by_tag[t] for t in tags if t in by_tag} | {q for n, q in by_name.items() if n in c['quote']})
        missing = [t for t in tags if t not in by_tag]
        if missing:
            props['unresolved_tags'] = missing
            unresolved[c['id']] = missing
        s = f'MATCH (s:Section {{id: {lit(c["section"])}}}) MERGE (k:Knowledge {{id: {lit(c["id"])}}}) SET k += {mp(props)}, k:{LABEL[c["kind"]]} MERGE (k)-[:STATED_IN]->(s)'
        if c['procedure']:
            rel = f'HAS_STEP {{order: {c["order"]}}}' if c['kind'] == 'step' else 'HAS_CONDITION'
            s += f' WITH k MATCH (p:Procedure {{id: {lit(c["procedure"])}}}) MERGE (p)-[:{rel}]->(k)'
        out.append(s + ';')
        for ref in c['refs']:
            out.append(f'MATCH (k:Knowledge {{id: {lit(c["id"])}}}), (t {{id: {lit(ref)}}}) WHERE t:Procedure OR t:Section MERGE (k)-[:REFERS_TO]->(t);')
        for q in qids:
            out.append(f'MATCH (k:Knowledge {{id: {lit(c["id"])}}}), (q:Quantity {{id: {lit(q)}}}) MERGE (k)-[:ABOUT_QUANTITY]->(q);')
    (HERE / '결과').mkdir(exist_ok=True)
    (HERE / '결과/load.cypher').write_text('\n'.join(out) + '\n', encoding='utf-8')
    report = {'statements': len(out) - 1, 'skipped_not_approved': skipped, 'unresolved_tags': unresolved,
              'sections': len(sections), 'procedures': len(procs)}
    (HERE / '결과/load_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'load.cypher 문장 {report["statements"]}개, 적재 제외(approved 아님) {len(skipped)}건 {skipped}, 기존 ID 없는 태그 {unresolved}')


if __name__ == '__main__':
    main()
