"""결과/조치검토결과.json·.md의 구조와 계약 불변식 검사. 판정의 의미 정답은 판정하지 않는다."""
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
    review = json.loads((root/'결과/조치검토결과.json').read_text(encoding='utf-8-sig'))
    md = (root/'결과/조치검토결과.md').read_text(encoding='utf-8-sig')
    if not str(review.get('비교_기준', '')).strip(): errors.append('비교_기준(교육용 비교값과 HYD 점수·실행 승인의 구분 문장)이 없습니다.')
    items = review.get('항목')
    if not isinstance(items, list): raise ValueError('항목 목록이 없습니다.')
    expected = {**{k: ('사례', v) for k, v in cases.items()}, **{k: ('요청', v) for k, v in requests.items()}}
    got = [i.get('id') for i in items]
    if sorted(got) != sorted(expected): errors.append(f'항목 id가 입력과 다릅니다: {sorted(set(expected) ^ set(got))}')
    for item in items:
        iid = item.get('id')
        if iid not in expected: continue
        kind, sops = expected[iid]
        if item.get('종류') != kind: errors.append(f'{iid}: 종류는 {kind}')
        cands = item.get('후보', [])
        if [c.get('sop') for c in cands] != sops: errors.append(f'{iid}: 후보 목록이 입력과 다릅니다.')
        if not re.search(r'^#+\s.*(?<![A-Za-z0-9])'+re.escape(iid)+r'(?![A-Za-z0-9])', md, re.M): errors.append(f'조치검토결과.md에 {iid} 절 제목이 없습니다.')
        for c in cands:
            at = f'{iid}/{c.get("sop")}'
            status = c.get('판정')
            if status not in STATUS: errors.append(f'{at}: 판정은 유지·제외·보류'); continue
            reasons = c.get('이유')
            if not isinstance(reasons, list): errors.append(f'{at}: 이유 목록 필요'); continue
            for r in reasons:
                if (r.get('규칙'), c.get('sop')) not in rule_actions: errors.append(f'{at}: 조건표에 없는 규칙·후보 {r.get("규칙")}')
                if r.get('결과') not in {'WARN','PENALTY','EXCLUDE','미확인'}: errors.append(f'{at}: 이유의 결과는 WARN·PENALTY·EXCLUDE·미확인')
                if not r.get('비교') or not r.get('출처') or not isinstance(r.get('실제_입력'), dict): errors.append(f'{at} {r.get("규칙")}: 실제_입력·비교·출처가 필요합니다.')
            kinds = {r.get('결과') for r in reasons}
            if status == '제외' and 'EXCLUDE' not in kinds: errors.append(f'{at}: 제외인데 EXCLUDE 이유가 없습니다.')
            if status == '보류' and ('EXCLUDE' in kinds or '미확인' not in kinds): errors.append(f'{at}: 보류는 제외 없이 미확인 이유가 있어야 합니다.')
            if status == '유지' and kinds & {'EXCLUDE', '미확인'}: errors.append(f'{at}: 유지인데 제외·미확인 이유가 있습니다.')
            if not c.get('원문_출처'): errors.append(f'{at}: 원문_출처가 비었습니다.')
            checks = c.get('추가_확인')
            if not isinstance(checks, list) or (status == '보류' and not checks): errors.append(f'{at}: 추가_확인 목록이 필요하고 보류 후보는 비어 있으면 안 됩니다.')
            missing = [m for r in reasons if r.get('결과') == '미확인' for m in r.get('빠진_입력', [])]
            if any(not any(m in str(x) for x in checks or []) for m in missing): errors.append(f'{at}: 빠진 입력 {missing}이 추가_확인에 없습니다.')
            approval = c.get('승인') or {}
            if not approval.get('역할') or not approval.get('출처') or not approval.get('안내'): errors.append(f'{at}: 승인(역할·출처·안내)이 필요합니다.')
            value, rank = c.get('비교값'), c.get('순위')
            if kind == '사례' or status != '유지':
                if value or rank is not None: errors.append(f'{at}: 비교값·순위는 요청의 유지 후보에만 둡니다.')
            elif value is not None:
                keys = ['비용','생산','품질','에너지','감점','합계']
                if not all(num(value.get(k)) for k in keys): errors.append(f'{at}: 비교값에 {keys}가 숫자로 필요합니다.')
                elif abs(sum(value[k] for k in keys[:5]) - value['합계']) > 0.02: errors.append(f'{at}: 합계가 네 손실+감점과 다릅니다.')
        opinion = item.get('검토_의견') or {}
        kept = [c for c in cands if c.get('판정') == '유지' and c.get('순위') is not None]
        top = sorted(c['sop'] for c in kept if c['순위'] == 1)
        if kind == '요청' and sorted(opinion.get('추천') or []) != top: errors.append(f'{iid}: 추천은 순위 1위 유지 후보여야 합니다.')
        if kind == '사례' and opinion.get('추천'): errors.append(f'{iid}: 사례 A~M는 비교하지 않으므로 추천을 두지 않습니다.')
        if not opinion.get('사유'): errors.append(f'{iid}: 검토_의견.사유가 필요합니다.')
except (OSError, ValueError, TypeError, AttributeError) as e:
    errors.append(f'조치검토결과: {e}')
if errors:
    print('구조 확인 필요'); print('\n'.join(errors)); sys.exit(1)
print(f'구조 검사 통과: 사례 {len(cases)}건, 요청 {len(requests)}건. 판정·이유·출처가 원문과 맞는지와 금액은 별도로 대조하세요.')
