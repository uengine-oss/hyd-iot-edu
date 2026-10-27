"""결과/result.json의 구조와 계약 불변식 검사. 어떤 규칙이 맞아야 하는지·금액은 판정하지 않는다."""
from pathlib import Path
import csv, json, re, sys
root = Path(__file__).resolve().parent
errors = []
def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as f: return list(csv.DictReader(f))
cases = {r['case']: r['candidate_sops'].split(';') for r in rows(root/'자료/cases.csv')}
requests = {q['번호']: [c['sop'] for c in q['후보']] for q in json.loads((root/'자료/metrics/판정_요청.json').read_text(encoding='utf-8-sig'))['요청']}
rule_actions = {(r['rule_id'], r['action']) for r in rows(root/'입력/rules.csv')}
STATUS = {'유지','제외','보류'}
def num(x): return isinstance(x, (int, float)) and not isinstance(x, bool)

try:
    result = json.loads((root/'결과/result.json').read_text(encoding='utf-8-sig'))
    if not isinstance(result.get('comparison_basis'), str) or not result['comparison_basis'].strip(): errors.append('comparison_basis(교육용 비교값과 HYD 점수의 구분 문장)가 없습니다.')
    for kind, expected in [('cases', cases), ('requests', requests)]:
        entries = result.get(kind)
        if not isinstance(entries, list): errors.append(f'{kind} 목록이 없습니다.'); continue
        got = [e.get('id') for e in entries]
        if sorted(got) != sorted(expected): errors.append(f'{kind}: 입력의 {sorted(expected)}와 결과의 {sorted(got)}가 다릅니다.')
        for e in entries:
            eid = e.get('id'); cands = e.get('candidates', [])
            if eid in expected and [c.get('sop') for c in cands] != expected[eid]: errors.append(f'{eid}: 후보 목록이 입력 순서·구성과 다릅니다.')
            for c in cands:
                at = f'{eid}/{c.get("sop")}'
                if c.get('status') not in STATUS: errors.append(f'{at}: status는 유지·제외·보류'); continue
                lists = {k: c.get(k) for k in ['warnings','penalties','exclusions','unknown']}
                if any(not isinstance(v, list) for v in lists.values()): errors.append(f'{at}: warnings·penalties·exclusions·unknown은 목록'); continue
                for k in ['warnings','penalties','exclusions']:
                    for h in lists[k]:
                        if (h.get('rule_id'), c.get('sop')) not in rule_actions: errors.append(f'{at}: 조건표에 없는 규칙·후보 {h.get("rule_id")}')
                        if not h.get('source_section') or not isinstance(h.get('conditions'), list) or not h['conditions']: errors.append(f'{at} {h.get("rule_id")}: source_section과 conditions(실제 입력·비교)가 필요')
                for h in lists['penalties']:
                    if not num(h.get('amount_만원')): errors.append(f'{at} {h.get("rule_id")}: amount_만원 숫자 필요')
                for u in lists['unknown']:
                    if not u.get('missing'): errors.append(f'{at} {u.get("rule_id")}: unknown에는 빠진 입력 이름(missing)이 필요')
                expected_status = '제외' if lists['exclusions'] else ('보류' if lists['unknown'] else '유지')
                if c['status'] != expected_status: errors.append(f'{at}: status {c["status"]}가 계약(제외>보류>유지)과 다릅니다. 기대 {expected_status}')
            if kind == 'cases':
                allowed = [c.get('sop') for c in cands if c.get('status') == '유지']
                if e.get('allowed') != allowed: errors.append(f'{eid}: allowed는 유지 후보 목록이어야 합니다.')
                if not allowed and not e.get('no_allowed_reason'): errors.append(f'{eid}: 유지 후보가 없으면 no_allowed_reason이 필요합니다.')
            else:
                for c in cands:
                    at = f'{eid}/{c.get("sop")}'; comp = c.get('comparison')
                    if c.get('status') != '유지':
                        if comp: errors.append(f'{at}: 유지가 아닌 후보에 비교값이 있습니다.')
                    elif comp is None:
                        if not c.get('comparison_unavailable'): errors.append(f'{at}: 비교값이 없으면 comparison_unavailable 이유가 필요합니다.')
                    else:
                        keys = ['비용','생산','품질','에너지','감점','합계']
                        if not all(num(comp.get(k)) for k in keys): errors.append(f'{at}: 비교값에 {keys}가 숫자로 필요합니다.'); continue
                        if abs(sum(comp[k] for k in keys[:5]) - comp['합계']) > 0.02: errors.append(f'{at}: 합계가 네 손실+감점과 다릅니다.')
                        if abs(sum(p['amount_만원'] for p in c.get('penalties', []) if num(p.get('amount_만원'))) - comp['감점']) > 0.001: errors.append(f'{at}: 감점이 penalties 금액 합과 다릅니다.')
                ranking = e.get('ranking'); rec = e.get('recommendation') or {}
                if not isinstance(ranking, list): errors.append(f'{eid}: ranking 목록 필요'); continue
                kept = {c.get('sop'): c for c in cands if c.get('status') == '유지' and c.get('comparison')}
                if sorted(r.get('sop') for r in ranking) != sorted(kept): errors.append(f'{eid}: ranking에는 비교값이 있는 유지 후보만 모두 있어야 합니다.')
                totals = [r.get('합계') for r in ranking]
                if totals != sorted(totals): errors.append(f'{eid}: ranking이 합계 오름차순이 아닙니다.')
                for i, r in enumerate(ranking):
                    tie = i > 0 and ranking[i-1].get('합계') == r.get('합계')
                    if r.get('rank') != (ranking[i-1].get('rank') if tie else i+1): errors.append(f'{eid}: 순위 {r.get("sop")}가 동순위 규칙(1,1,3)과 다릅니다.')
                top = sorted(r.get('sop') for r in ranking if r.get('rank') == 1)
                if sorted(rec.get('sops') or []) != top: errors.append(f'{eid}: recommendation.sops는 1위 유지 후보여야 합니다.')
                if not rec.get('reason'): errors.append(f'{eid}: recommendation.reason이 필요합니다.')
except (OSError, ValueError, TypeError, AttributeError) as e:
    errors.append(f'result.json: {e}')
if errors:
    print('구조 확인 필요'); print('\n'.join(errors)); sys.exit(1)
print(f'구조 검사 통과: 사례 {len(cases)}건, 요청 {len(requests)}건. 어떤 규칙이 맞아야 하는지와 금액은 원문·지표_정의.md 손계산과 별도로 대조하세요.')
