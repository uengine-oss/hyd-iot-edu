"""강사 참조: 검토 결과(approved만)와 원문 절 구조로 결과/load.cypher를 만든다. 학생 배포 금지.

모델 확장(이번 단계에서 새로 만드는 것):
  (:Document {id: '<문서>@<판>'})  판·상태·해시는 자료/문서_목록.csv
  (:Section {id: '<문서>:<절>'})-[:IN_DOCUMENT]->(:Document)
  (:Procedure {id})-[:DEFINED_IN]->(:Section)
  (:Knowledge:<Step|Precondition|Prohibition|Completion|UnitValue> {id, …출처·검토})-[:STATED_IN]->(:Section)
  (:Procedure)-[:HAS_STEP {order}]->(:Step), (:Procedure)-[:HAS_CONDITION]->(:Knowledge)
  (:Knowledge)-[:REFERS_TO]->(:Procedure|:Section)        refs에 적힌 ID만
기존 모델 연결(기존 노드는 MATCH로만 찾고 만들거나 고치지 않는다):
  (:Knowledge)-[:ABOUT_QUANTITY]->(:Quantity)   인용 속 태그 → 모델의 Sensor.tag → OBSERVES → Quantity
  (:Knowledge)-[:MENTIONS_PART]->(:Part)        인용 속 품명(규격 표기를 뺀 이름)·다른 표기(other_codes). 같은 이름이 여럿이면
                                                 그 문서가 적용되는 설비가 쓰는 부품(USES_PART)으로 좁히고, 그래도 여럿이면 연결하지 않는다
  (:Procedure)-[:APPLIES_TO {basis}]->(:Asset)  문서가 적용 범위를 적은 경우만(아래 SCOPE). HM-8은 적지 않아 연결하지 않는다
"""
from pathlib import Path
import csv
import json
import re

HERE = Path(__file__).resolve().parent
LABEL = {'step': 'Step', 'precondition': 'Precondition', 'prohibition': 'Prohibition', 'completion': 'Completion', 'unit_value': 'UnitValue'}
# 문서의 적용 범위 근거. 설비 ID 목록은 모델의 Asset에서 찾는다.
SCOPE = {
    'PM-02': ('ids', ['HYD-01', 'HYD-02', 'HYD-03'], 'PM-2.1 「같은 모델의 유압 파워팩 세 대(1~3호기)」 — n호기 = HYD-0n(작업지시 별칭과 같은 관례, 설비 대장에는 호기 표기 없음)'),
    'HI-01': ('ids', ['HYD-01', 'HYD-02', 'HYD-03'], 'HI-1 「HYD-01, HYD-02, HYD-03」'),
    'OEM-HPP45A-MM': ('model', 'HPP-45A', '머리말 사내 주석 「설비 대장에 모델 HPP-45A로 등록된 설비」 — 모델의 Asset.model'),
}


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
        p = re.match(r'^###\s+(\S+)\s*(.*)$', line)
        if p:
            procs[p.group(1)] = (p.group(2), cur)
    return sections, procs


def base_name(name):
    return re.sub(r'\s*\(.*?\)|\s+\d+(?:\.\d+)?\s*(?:µm|L)\b|\d+(?:\.\d+)?µm', '', name).strip()


def main():
    graph = json.loads((HERE / '입력/모델/graph.json').read_text(encoding='utf-8'))
    nodes = {n['props']['id']: n for n in graph['nodes']}
    tag_q = {}
    for r in graph['rels']:
        if r['type'] == 'OBSERVES' and 'Sensor' in nodes[r['a']]['labels']:
            tag_q.setdefault(nodes[r['a']]['props'].get('tag'), set()).add(r['b'])
    assets = {i: n['props'] for i, n in nodes.items() if 'Asset' in n['labels']}
    parts = {i: n['props'] for i, n in nodes.items() if 'Part' in n['labels']}
    comp_asset = {r['b']: r['a'] for r in graph['rels'] if r['type'] == 'HAS_COMPONENT'}
    used_by = {}
    for r in graph['rels']:
        if r['type'] == 'USES_PART':
            used_by.setdefault(r['b'], set()).add(comp_asset.get(r['a']))
    with (HERE / '자료/문서_목록.csv').open(encoding='utf-8', newline='') as f:
        register = {r['파일']: r for r in csv.DictReader(f) if r['파일']}
    out = ['// 생성: make_load.py — 입력/검토결과의 approved 후보만. 다시 실행해도 MERGE로 늘지 않는다.']
    report = {'documents': [], 'skipped_not_approved': {}, 'unresolved_tags': {}, 'part_links': {}, 'ambiguous_parts': {}, 'applies_to': {}}
    for path in sorted((HERE / '입력/검토결과').glob('*_검토.json')):
        review = json.loads(path.read_text(encoding='utf-8'))
        row = register[review['source_file']]
        doc = review['doc_id']; did = f'{doc}@{row["판"]}'
        md = (HERE / '자료/원문' / review['source_file']).read_text(encoding='utf-8')
        sections, procs = structure(md)
        out.append(f'MERGE (d:Document {{id: {lit(did)}}}) SET d += {mp({"doc_id": doc, "rev": row["판"], "status": row["상태"], "title": row["제목"], "file": review["source_file"], "sha256": review["source_sha256"]})};')
        for sid, title in sections.items():
            out.append(f'MATCH (d:Document {{id: {lit(did)}}}) MERGE (s:Section {{id: {lit(doc + ":" + sid)}}}) SET s += {mp({"doc_id": doc, "section": sid, "title": title})} MERGE (s)-[:IN_DOCUMENT]->(d);')
        scope = SCOPE.get(doc)
        targets = []
        if scope:
            targets = [a for a in scope[1] if a in assets] if scope[0] == 'ids' else sorted(a for a, p in assets.items() if p.get('model') == scope[1])
        report['applies_to'][doc] = targets
        for pid, (name, sid) in procs.items():
            out.append(f'MATCH (s:Section {{id: {lit(doc + ":" + sid)}}}) MERGE (p:Procedure {{id: {lit(pid)}}}) SET p += {mp({"name": name, "doc_id": doc})} MERGE (p)-[:DEFINED_IN]->(s);')
            for a in targets:
                out.append(f'MATCH (p:Procedure {{id: {lit(pid)}}}), (a:Asset {{id: {lit(a)}}}) MERGE (p)-[x:APPLIES_TO]->(a) SET x.basis = {lit(scope[2])};')
        skipped = []
        for c in review['candidates']:
            if c['status'] != 'approved':
                skipped.append(c['id']); continue
            props = {k: c.get(k) for k in ['kind', 'text', 'quote', 'refs', 'order', 'value', 'value_max', 'unit', 'comparator', 'value_text', 'decision', 'reason', 'origin']}
            props.update(doc_id=doc, doc_rev=row['판'], section=c['section'], source_sha256=review['source_sha256'],
                         reviewer=review['review']['reviewer'], reviewed_at=review['review']['reviewed_at'], status='approved')
            tags = sorted({t for t in tag_q if t and re.search(rf'(?<![A-Za-z0-9_]){re.escape(t)}(?![A-Za-z0-9_])', c['quote'])}
                          | set(re.findall(r'(?<![A-Za-z])([A-Z]{2}\d)(?!\d)', c['quote'])))
            qids = sorted({q for t in tags for q in tag_q.get(t, set())})
            missing = [t for t in tags if t not in tag_q]
            if missing:
                props['unresolved_tags'] = missing; report['unresolved_tags'][c['id']] = missing
            hits = []
            for pid_, p in parts.items():
                names = [base_name(p.get('name', ''))] + list(p.get('other_codes', []))
                if any(n and len(n) >= 4 and n in c['quote'] for n in names):
                    hits.append(pid_)
            if len(hits) > 1 and targets:
                narrowed = [h for h in hits if used_by.get(h, set()) & set(targets)]
                hits = narrowed if narrowed else hits
            if len(hits) > 1:
                report['ambiguous_parts'][c['id']] = hits; props['unresolved_parts'] = hits; hits = []
            if hits:
                report['part_links'][c['id']] = hits
            s = f'MATCH (s:Section {{id: {lit(doc + ":" + c["section"])}}}) MERGE (k:Knowledge {{id: {lit(c["id"])}}}) SET k += {mp(props)}, k:{LABEL[c["kind"]]} MERGE (k)-[:STATED_IN]->(s)'
            if c['procedure']:
                rel = f'HAS_STEP {{order: {c["order"]}}}' if c['kind'] == 'step' else 'HAS_CONDITION'
                s += f' WITH k MATCH (p:Procedure {{id: {lit(c["procedure"])}}}) MERGE (p)-[:{rel}]->(k)'
            out.append(s + ';')
            for ref in c['refs']:
                target = ref if ref in procs or re.match(r'^(SOP|T)-', ref) else f'{doc}:{ref}'
                out.append(f'MATCH (k:Knowledge {{id: {lit(c["id"])}}}), (t {{id: {lit(target)}}}) WHERE t:Procedure OR t:Section MERGE (k)-[:REFERS_TO]->(t);')
            for q in qids:
                out.append(f'MATCH (k:Knowledge {{id: {lit(c["id"])}}}), (q:Quantity {{id: {lit(q)}}}) MERGE (k)-[:ABOUT_QUANTITY]->(q);')
            for p in hits:
                out.append(f'MATCH (k:Knowledge {{id: {lit(c["id"])}}}), (p:Part {{id: {lit(p)}}}) MERGE (k)-[:MENTIONS_PART]->(p);')
        report['skipped_not_approved'][path.name] = skipped
        report['documents'].append({'file': path.name, 'document': did, 'status': row['상태'], 'sha12': review['source_sha256'][:12],
                                    'approved': sum(1 for c in review['candidates'] if c['status'] == 'approved'), 'not_loaded': len(skipped)})
    (HERE / '결과').mkdir(exist_ok=True)
    (HERE / '결과/load.cypher').write_text('\n'.join(out) + '\n', encoding='utf-8')
    report['statements'] = len(out) - 1
    (HERE / '결과/load_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'load.cypher 문장 {report["statements"]}개')
    for d in report['documents']:
        print(f'  {d["file"]}: {d["document"]}({d["status"]}, {d["sha12"]}) approved {d["approved"]} 적재, 적재 안 함 {d["not_loaded"]}')
    print(f'  적용 설비 {report["applies_to"]}')
    print(f'  부품 연결 {len(report["part_links"])}건, 이름이 여럿 맞아 연결 안 함 {report["ambiguous_parts"]}, 기존 ID 없는 태그 {report["unresolved_tags"]}')


if __name__ == '__main__':
    main()
