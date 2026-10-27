"""강사 참조: 랩 DB 조회 결과로 작업 확인 카드를 만든다. 학생 배포 금지.
사용: python make_card.py SOP-COOL-11 [--part P-CLR-CORE]
카드의 조건·출처는 모두 DB 조회 결과에서 온다. 검토본 JSON은 적재하지 않은 후보(보류·제외·누락)를 남은 질문으로 옮길 때만 읽는다.
"""
from pathlib import Path
import json
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from lab_cypher import cypher  # noqa: E402

# 이 작업에 해당하는 지식: (1) 절차에 직접 달린 것 (2) 이 절차를 ID로 가리키는 것
# (3) 같은 절의 절차 밖 문장 (4) 이 절차의 지식이 가리키는 절에 적힌 것
CARD = '''
MATCH (p:Procedure {id: $pid})-[:DEFINED_IN]->(s:Section)-[:IN_DOCUMENT]->(d:Document)
CALL {
  WITH p MATCH (p)-[r:HAS_STEP|HAS_CONDITION]->(k:Knowledge) RETURN k, '절차 안' AS via
  UNION WITH p MATCH (k:Knowledge)-[:REFERS_TO]->(p) RETURN k, '이 절차를 ID로 가리킴' AS via
  UNION WITH p, s MATCH (k:Knowledge)-[:STATED_IN]->(s) WHERE NOT (k)<-[:HAS_STEP|HAS_CONDITION]-(:Procedure) RETURN k, '같은 절의 절차 밖 문장' AS via
  UNION WITH p MATCH (p)-[:HAS_STEP|HAS_CONDITION]->(:Knowledge)-[:REFERS_TO]->(rs:Section)<-[:STATED_IN]-(k:Knowledge) RETURN k, '단계가 가리킨 절 ' + rs.id AS via
}
MATCH (k)-[:STATED_IN]->(ks:Section)
OPTIONAL MATCH (k)<-[:HAS_STEP|HAS_CONDITION]-(owner:Procedure)
OPTIONAL MATCH (k)-[:ABOUT_QUANTITY]->(q:Quantity)
RETURN p.id, p.name, d.id, d.sha256, s.id, k.id, k.kind, k.text, k.quote, k.order, k.value, k.value_max, k.unit, k.comparator,
       ks.id, owner.id, via, collect(DISTINCT q.id), k.unresolved_tags
ORDER BY k.kind, ks.id, k.order, k.id
'''
UNLINKED = '''
MATCH (p:Procedure {id: $pid})-[:DEFINED_IN]->(:Section)-[:IN_DOCUMENT]->(d:Document)
MATCH (k:Knowledge)-[:STATED_IN]->(ks:Section)-[:IN_DOCUMENT]->(d)
WHERE k.kind IN ['precondition', 'prohibition'] AND NOT (k)<-[:HAS_CONDITION]-(:Procedure) AND NOT (k)-[:REFERS_TO]->()
  AND NOT (p)-[:DEFINED_IN]->(ks)
RETURN k.id, ks.id, k.kind, k.quote ORDER BY k.id
'''
ASSET = 'MATCH (p:Procedure {id: $pid}) OPTIONAL MATCH (p)-[*1..2]-(a) WHERE a:Asset OR a:Component OR a:Part RETURN count(a)'
SUPPLY = '''
MATCH (part:Part {id: $part}) OPTIONAL MATCH (sup:Supplier)-[r:SUPPLIES]->(part)
OPTIONAL MATCH (c:Component)-[:USES_PART]->(part)
RETURN part.id, part.name, collect(DISTINCT c.id), collect(DISTINCT [sup.name, r.approved, r.price_manwon, r.defect_rate, r.lead_days])
'''


def rows(statement, **params):
    return [r['row'] for r in cypher([(statement, params)])[0]['data']]


def card(pid, part=None):
    data = rows(CARD, pid=pid)
    if not data:
        return None
    pid_, name, doc, sha, sec = data[0][:5]
    items = {}
    for r in data:
        kid = r[5]
        if kid in items:
            items[kid]['via'].add(r[16]); continue
        items[kid] = dict(id=kid, kind=r[6], text=r[7], quote=r[8], order=r[9], value=r[10], value_max=r[11], unit=r[12], cmp=r[13],
                          sec=r[14], owner=r[15], via={r[16]}, qs=r[17], unresolved=r[18] or [])
    def src(i):
        return f'{i["sec"]} 「{i["quote"]}」 ({i["id"]})'
    lines = [f'# 작업 확인 카드 — {pid_} {name}', '',
             f'- 문서: {doc} (SHA-256 {sha[:12]}), 절차 정의 절: {sec}',
             '- 근거: 랩 DB 조회 결과(approved 지식만). 각 항목의 절·인용으로 원문을 다시 확인할 수 있다.',
             '- 이 카드는 현재 설비 상태를 읽지 않고, 승인을 대신하지 않는다.', '']
    own = [i for i in items.values() if i['owner'] == pid_ and i['kind'] == 'step']
    other = [i for i in items.values() if not (i['owner'] == pid_ and i['kind'] == 'step')]
    approval = [i for i in other if i['kind'] == 'precondition' and i['quote'].startswith('승인')]
    groups = [('준비 조건', [i for i in other if i['kind'] == 'precondition' and i not in approval and i['owner'] in (pid_, None)]),
              ('금지·제한', [i for i in other if i['kind'] == 'prohibition' and i['owner'] in (pid_, None)]),
              ('완료 기준', [i for i in other if i['kind'] == 'completion' and i['owner'] in (pid_, None)])]
    for title, group in groups:
        lines += [f'## {title}', '']
        tail = ' · 작업 뒤 실제 관측값으로 판정' if title == '완료 기준' else ''
        lines += [f'- {i["text"]} — {src(i)} · 찾은 경로: {", ".join(sorted(i["via"]))}{tail}' for i in group] or ['- (조회 결과 없음)']
        lines.append('')
    lines += ['## 작업 순서', '']
    lines += [f'{i["order"]}. {i["text"]} — {i["sec"]} ({i["id"]})' for i in sorted(own, key=lambda x: x['order'])] or ['(조회 결과 없음)']
    refs = [i for i in other if i['owner'] not in (pid_, None)]
    if refs:
        lines += ['', '## 다른 절차에서 이 작업을 가리키는 내용', '']
        lines += [f'- {i["owner"]}: {i["text"]} — {src(i)}' for i in refs]
    values = [i for i in other if i['kind'] == 'unit_value' and i['owner'] in (pid_, None)]
    lines += ['', '## 문서의 기준값', '']
    for i in values:
        v = f'{i["value"]}~{i["value_max"]}' if i['value_max'] is not None else f'{i["value"]}'
        q = ', '.join(i['qs']) or '기존 모델 ID 연결 없음'
        lines.append(f'- {v} {i["unit"]} (비교 {i["cmp"] or "표현 없음"}) — {src(i)} · 물리량: {q}')
    if not values:
        lines.append('- (조회 결과 없음)')
    lines += ['', '## 작업 직전 확인 — 그래프에 없는 현재 상태', '',
              '문서의 기준은 위 항목이다. 아래 조건이 지금 충족되는지는 작업 직전에 설비·운전 기록·현장에서 확인한다. 그래프에는 현재 값이 없다.', '']
    for i in [x for x in other if x['kind'] in ('precondition', 'prohibition') and x not in approval and x['owner'] in (pid_, None)]:
        where = '현재 값 필요: ' + ', '.join(i['qs']) if i['qs'] else '현장·운전 기록에서 확인(기존 모델에 상태 ID 없음)'
        lines.append(f'- {i["text"]} → {where}')
    lines += ['', '## 승인', '']
    lines += [f'- {i["text"]} — {src(i)} · 승인 필요' for i in approval] or ['- (원문에서 승인 역할을 찾지 못함 — 확인 필요)']
    if part:
        sup = rows(SUPPLY, part=part)
        lines += ['', f'## 부품·공급 정보 (참고 조회: {part})', '']
        if not sup:
            lines.append(f'- {part}: 모델에 없음')
        else:
            pid2, pname, comps, offers = sup[0]
            lines.append(f'- {pid2} {pname}: 사용 구성요소 {", ".join(sorted(comps))}')
            for o in offers:
                if o[0]:
                    lines.append(f'  - {o[0]}: 승인 {"예" if o[1] else "아니오"}, 단가 {o[2]}만원, 불량률 {o[3]}, 납기 {o[4]}일')
            lines.append(f'- 그래프에서 {pid_}와 {part}를 잇는 관계는 없다. 원문 HM-8은 이 작업과 부품을 ID로 연결하지 않으므로 공급 정보는 작업 조건이 아니라 참고다.')
    lines += ['', '## 남은 질문', '']
    q = []
    if rows(ASSET, pid=pid_)[0][0] == 0:
        q.append(f'{doc}은 적용 설비를 ID로 정하지 않는다. 그래프의 HYD-01~03 설비·구성요소와 {pid_}를 연결하지 않았다. 어느 설비에 적용하는지 확인 필요.')
    for i in items.values():
        if i['unresolved']:
            q.append(f'{i["id"]}의 태그 {", ".join(i["unresolved"])}는 기존 모델에 ID가 없어 연결하지 않았다(새로 만들지 않음).')
    near = {i['sec'] for i in items.values() if i['owner'] is None}  # 이 작업의 조건이 적힌 절차 밖 절
    for r in rows(UNLINKED, pid=pid_):
        if r[1] not in near or r[0] in items:
            continue
        q.append(f'{r[1]}의 {r[2]} 「{r[3]}」({r[0]})는 절차 ID 없이 적혀 이 작업에 연결하지 않았다. 적용 여부를 원문으로 확인 필요.')
    review = json.loads((HERE / '입력/검토결과/HM-8_검토.json').read_text(encoding='utf-8'))
    secs = near | {sec}
    for c in review['candidates']:
        if c['status'] != 'approved' and (c['section'] in secs or pid_ in c['refs']):
            q.append(f'적재하지 않은 후보 {c["id"]}({c["decision"]}, {c["section"]}): 「{c["quote"]}」 — {c["reason"]}')
    for m in review.get('missing', []):
        if not m['added'] and m['section'] in secs:
            q.append(f'검토 때 기록한 누락 {m["section"]} 「{m["quote"]}」 — {m["note"]}')
    lines += [f'- {x}' for x in q] or ['- (없음)']
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    pid = sys.argv[1]
    part = sys.argv[sys.argv.index('--part') + 1] if '--part' in sys.argv else None
    text = card(pid, part)
    if text is None:
        print(f'{pid}: 랩 DB에 이 절차가 없습니다(원문이 제공하지 않는 작업이거나 적재되지 않음). 카드를 만들지 않습니다.')
        sys.exit(3)
    dest = HERE / '결과' / f'작업확인카드_{pid}.md'
    dest.write_text(text, encoding='utf-8')
    print(f'{dest.name} 저장 ({text.count(chr(10))}줄)')
