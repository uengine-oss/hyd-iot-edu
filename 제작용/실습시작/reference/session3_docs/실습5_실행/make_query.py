"""강사 참조: 결과/query.cypher(학생 제출물에 해당하는 조회문)를 만든다. 학생 배포 금지.
카드 생성에 쓴 조회(make_card.KNOW)를 선택 작업과 다른 작업에 그대로 적고, 재적재·제외 후보·미제공 작업·공급 조회를 덧붙인다."""
from pathlib import Path
import json
import make_card as m

HERE = Path(__file__).resolve().parent
excluded = []
for p in sorted((HERE / '입력/검토결과').glob('*_검토.json')):
    excluded += [c['id'] for c in json.loads(p.read_text(encoding='utf-8'))['candidates'] if c['status'] != 'approved']
q = ['// 생성: make_query.py — 문장은 줄 끝 ; 로 구분']
for pid in ['SOP-COOL-14', 'T-3.1']:
    q.append(f'// 작업 확인 카드 조회: {pid}')
    q.append(' '.join(m.KNOW.replace('$pid', json.dumps(pid)).split()) + ';')
q.append('// 미제공 작업(원문에 없는 절차): 0행이어야 한다')
q.append("MATCH (p:Procedure) WHERE p.id IN ['SOP-PM-24', '코어교체'] RETURN p.id;")
q.append('// 적재하지 않은 후보(제외·보류)가 DB에 없어야 한다: 0')
q.append(f'MATCH (k:Knowledge) WHERE k.id IN {json.dumps(excluded, ensure_ascii=False)} RETURN count(k) AS loaded_not_approved;')
q.append('// 폐기 판 문서가 적재되지 않았는지')
q.append("MATCH (d:Document) RETURN d.id, d.status ORDER BY d.id;")
q.append('// 작업 → 부품 → 공급 조건(2회차 모델의 기존 ID)')
q.append("MATCH (p:Procedure)-[:HAS_STEP|HAS_CONDITION]->(:Knowledge)-[:MENTIONS_PART]->(part:Part) OPTIONAL MATCH (s:Supplier)-[r:SUPPLIES]->(part) RETURN DISTINCT p.id, part.id, s.name, r.approved, r.price_manwon, r.lead_days ORDER BY p.id, part.id, s.name;")
q.append('// 작업 → 적용 설비')
q.append("MATCH (p:Procedure)-[:APPLIES_TO]->(a:Asset) RETURN p.doc_id, count(DISTINCT p) AS procedures, collect(DISTINCT a.id) AS assets ORDER BY p.doc_id;")
(HERE / '결과/query.cypher').write_text('\n'.join(q) + '\n', encoding='utf-8')
print(f'query.cypher 문장 {sum(1 for l in q if l.endswith(";"))}개, 제외·보류 후보 {len(excluded)}개 확인')
