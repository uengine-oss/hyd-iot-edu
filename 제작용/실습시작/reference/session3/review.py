"""강사 참조: 실전반 조치 검토 결과. 판정 코어는 judge.py를 그대로 쓴다. 학생 ZIP에 넣지 않는다.

사용: python review.py <랩 폴더> <출력 폴더>
→ <출력 폴더>/조치검토결과.json, 조치검토결과.md
"""
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import judge  # noqa: E402

KIND = {'WARN': '경고', 'PENALTY': '감점', 'EXCLUDE': '제외', '미확인': '미확인'}
BASIS = ('비교값은 지표_정의.md의 교육용 네 손실(비용·생산·품질·에너지)과 규칙 감점의 합계(만원)다. '
         '실제 HYD 성과 점수(일곱 성분)가 아니며, 순위는 승인 요청을 검토할 순서일 뿐 실행 승인이 아니다.')


def expr(c):
    unit = f' {c["unit"]}' if c['unit'] else ''
    return f'{c["input"]} {c["operator"]} {c["value"]}{unit}'


def reasons(cand):
    out = []
    for key, kind in [('exclusions', 'EXCLUDE'), ('penalties', 'PENALTY'), ('warnings', 'WARN')]:
        for h in cand[key]:
            item = {'규칙': h['rule_id'], '결과': kind, '실제_입력': {c['input']: c['actual'] for c in h['conditions']}, '비교': ' AND '.join(expr(c) for c in h['conditions']), '출처': h['source_section'], '설명': h['reason']}
            if kind == 'PENALTY':
                item['감점_만원'] = h['amount_만원']
            out.append(item)
    for u in cand['unknown']:
        rule = next(r for r in cand['rules'] if r['rule_id'] == u['rule_id'])
        out.append({'규칙': u['rule_id'], '결과': '미확인', '실제_입력': {c['input']: c['actual'] for c in rule['conditions']}, '비교': ' AND '.join(expr(c) for c in rule['conditions']), '출처': u['source_section'], '설명': rule['reason'], '빠진_입력': u['missing'], '미확인_규칙의_결과': u['result']})
    return out


def extra_checks(cand, sop):
    checks = []
    for u in cand['unknown']:
        effect = {'EXCLUDE': '참이면 제외', 'PENALTY': '참이면 감점', 'WARN': '참이면 경고'}[u['result']]
        checks.append(f'{", ".join(u["missing"])} 값을 확인한다({u["rule_id"]} {effect}, 근거 {u["source_section"]}).')
    if cand['status'] == '유지':
        for item in sop['적용_조건']:
            checks.append(f'실행 직전 적용 조건 재확인: {item["내용"]} ({item["출처"]})')
        for item in sop['금지_조건']:
            if item['구분'] == '제한':
                checks.append(f'제한: {item["내용"]} ({item["출처"]})')
        for item in sop['완료_기준']:
            checks.append(f'완료 기준: {item["내용"]} ({item["출처"]})')
    return checks


def sources(cand, sop):
    found = [sop['출처']+f' {sop["id"]}']
    for r in reasons(cand):
        for part in r['출처'].split('; '):
            if part not in found:
                found.append(part)
    return found


def candidate(cand, sop, ranking):
    rank = next((r['rank'] for r in ranking if r['sop'] == cand['sop']), None)
    return {'sop': cand['sop'], '이름': sop['이름'], '판정': cand['status'], '이유': reasons(cand), '원문_출처': sources(cand, sop), '추가_확인': extra_checks(cand, sop), '비교값': cand.get('comparison'), '순위': rank,
            '승인': {'역할': sop['승인']['역할'], '출처': sop['승인']['출처'], '안내': f'비교 순위는 실행 승인이 아니다. 실행하려면 {sop["승인"]["역할"]}의 승인과 실행 전 확인이 필요하다.'}}


def opinion(entry, kind):
    held = [c['sop'] for c in entry['candidates'] if c['status'] == '보류']
    if kind == '사례':
        allowed = entry['allowed']
        reason = (f'유지 후보 {", ".join(allowed)}. 사례는 판정 확인용이며 비교·추천을 하지 않는다.' if allowed else entry['no_allowed_reason'])
        return {'추천': [], '사유': reason, '보류': held}
    rec = entry['recommendation']
    if rec['sops']:
        reason = f'교육용 비교 합계 1위 유지 후보 {", ".join(rec["sops"])}를 승인 요청 검토 대상으로 제안한다. 실행 승인은 아니다.' + (f' 보류 후보 {", ".join(held)}는 빠진 값을 확인한 뒤 다시 비교한다.' if held else '')
    else:
        excl = sorted({h['rule_id'] for c in entry['candidates'] for h in c['exclusions']})
        reason = rec['reason'] + (f'(제외 규칙 {", ".join(excl)})' if excl else '')
    return {'추천': rec['sops'], '사유': reason, '보류': held}


def build(lab):
    result = judge.run(lab)
    sop = {s['id']: s for s in json.loads((Path(lab)/'입력/sop.json').read_text(encoding='utf-8-sig'))['SOP']}
    items = []
    for kind, key in [('사례', 'cases'), ('요청', 'requests')]:
        for entry in result[key]:
            ranking = entry.get('ranking', [])
            items.append({'id': entry['id'], '종류': kind, '후보': [candidate(c, sop[c['sop']], ranking) for c in entry['candidates']], '검토_의견': opinion(entry, kind)})
    return {'비교_기준': BASIS, '항목': items}


def fmt(v):
    return '-' if v is None else (f'{v:g}' if isinstance(v, float) else str(v))


def markdown(review):
    lines = ['# 조치 검토 결과', '', review['비교_기준'], '']
    for item in review['항목']:
        lines += [f'## {item["id"]} ({item["종류"]})', '']
        if item['종류'] == '요청':
            lines += ['| 후보 | 판정 | 비용 | 생산 | 품질 | 에너지 | 감점 | 합계 | 순위 | 승인 |', '|---|---|---:|---:|---:|---:|---:|---:|---:|---|']
            for c in item['후보']:
                v = c['비교값'] or {}
                lines.append(f'| {c["sop"]} {c["이름"]} | {c["판정"]} | ' + ' | '.join(fmt(v.get(k)) for k in ['비용', '생산', '품질', '에너지', '감점', '합계']) + f' | {fmt(c["순위"])} | {c["승인"]["역할"]} |')
            lines.append('')
        for c in item['후보']:
            lines.append(f'### {item["id"]} · {c["sop"]} — {c["판정"]}')
            if c['이유']:
                for r in c['이유']:
                    actual = ', '.join(f'{k}={fmt(v) if not isinstance(v, list) else ";".join(v)}' for k, v in r['실제_입력'].items())
                    lines.append(f'- 이유 {r["규칙"]} {KIND[r["결과"]]}: {r["비교"]} / 실제 {actual} — {r["설명"]} (출처 {r["출처"]})')
            else:
                lines.append('- 이유: 맞은 규칙과 미확인 규칙 없음')
            lines.append(f'- 원문 출처: {"; ".join(c["원문_출처"])}')
            for x in c['추가_확인']:
                lines.append(f'- 추가 확인: {x}')
            lines.append(f'- 승인: {c["승인"]["역할"]}({c["승인"]["출처"]}). {c["승인"]["안내"]}')
            lines.append('')
        op = item['검토_의견']
        lines += [f'**검토 의견**: {op["사유"]}', '']
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit('사용: python review.py <랩 폴더> <출력 폴더>')
    out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
    review = build(sys.argv[1])
    (out/'조치검토결과.json').write_text(json.dumps(review, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (out/'조치검토결과.md').write_text(markdown(review), encoding='utf-8')
    print(f'항목 {len(review["항목"])}건 → {out}')
