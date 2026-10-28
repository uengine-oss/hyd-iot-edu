"""강사 참조: 실전반 조치 검토 결과(현업화 판). 판정 코어는 judge.py를 그대로 쓴다. 학생 ZIP에 넣지 않는다.

사용: python review.py <랩 폴더> <출력 폴더> [--counter recorded|elapsed]
→ <출력 폴더>/조치검토결과.json, 조치검토결과.md

검토 의견의 방침(담당자 판단 갈래, 리허설 2 실전 3-2 제안 3):
- policy=defer(강사 주 갈래): 빠진 값만 확인되면 1위가 될 수 있는 보류 후보(잠정 합계 ≤ 1위 합계, 또는 계산 불가)가 있으면
  추천을 미루고 먼저 확인할 값을 적는다. 근거: HI-01 SOP-HI-01(관측 실패면 정상 판단 금지), 작업기준.md 4절(필요한 입력이 빠지면 최종 허용 판단 보류).
- policy=propose: 1위 유지 후보를 승인 요청 검토 대상으로 추천하고 보류 후보는 다시 비교하라고만 적는다.
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


def why(cand, names):
    return '; '.join(sorted({cand['missing_reasons'].get(m, '') for m in names} - {''}))


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
        out.append({'규칙': u['rule_id'], '결과': '미확인', '실제_입력': {c['input']: c['actual'] for c in rule['conditions']}, '비교': ' AND '.join(expr(c) for c in rule['conditions']),
                    '출처': u['source_section'], '설명': rule['reason'], '빠진_입력': u['missing'], '빠진_이유': why(cand, u['missing']), '미확인_규칙의_결과': u['result']})
    return out


def extra_checks(cand, sop):
    checks = []
    for u in cand['unknown']:
        effect = {'EXCLUDE': '참이면 제외', 'PENALTY': '참이면 감점', 'WARN': '참이면 경고'}[u['result']]
        checks.append(f'{", ".join(u["missing"])} 값을 확인한다 — 없는 이유: {why(cand, u["missing"])} ({u["rule_id"]} {effect}, 근거 {u["source_section"]})')
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
    found = [sop['출처'] + f' {sop["id"]}']
    for r in reasons(cand):
        for part in r['출처'].split('; '):
            if part not in found:
                found.append(part)
    return found


def candidate(cand, sop, ranking):
    rank = next((r['rank'] for r in ranking if r['sop'] == cand['sop']), None)
    out = {'sop': cand['sop'], '이름': sop['이름'], '판정': cand['status'], '입력': cand['inputs'], '이유': reasons(cand), '원문_출처': sources(cand, sop),
           '추가_확인': extra_checks(cand, sop), '비교값': cand.get('comparison'), '순위': rank,
           '승인': {'역할': sop['승인']['역할'], '출처': sop['승인']['출처'], '안내': f'비교 순위는 실행 승인이 아니다. 실행하려면 {sop["승인"]["역할"]}의 승인과 실행 전 확인이 필요하다.'}}
    if cand.get('comparison_unavailable'):
        out['비교_불가'] = cand['comparison_unavailable']
    return out


def impacts(entry, metric):
    """보류 후보마다 아는 값만으로 계산한 잠정 합계(미확인 규칙의 감점 제외)와 1위 가능 여부."""
    values, works, settings, orders = metric
    top = min((r['합계'] for r in entry['ranking'] if r['rank'] == 1), default=None)
    out = []
    for c in entry['candidates']:
        if c['status'] != '보류':
            continue
        comp, lost = judge.compare(c, c['inputs']['forecast_ts1'], settings[c['sop']], values, works, orders[entry['id']])
        total = comp['합계'] if comp else None
        can = None if total is None else (True if top is None else total <= top)
        missing = sorted({m for u in c['unknown'] for m in u['missing']})
        basis = (f'빠진 값 {", ".join(missing)}을 뺀 잠정 합계 {total}' + (f', 1위 유지 후보 합계 {top}' if top is not None else ', 비교할 유지 후보 없음')) if total is not None else f'잠정 합계 계산 불가: {"; ".join(lost)}'
        out.append({'sop': c['sop'], '잠정_합계': total, '1위_가능': can, '근거': basis})
    return out


def opinion(entry, metric, policy='defer'):
    held = [c['sop'] for c in entry['candidates'] if c['status'] == '보류']
    rec = entry['recommendation']
    impact = impacts(entry, metric)
    could = [x for x in impact if x['1위_가능'] is not False]
    if rec['sops'] and policy == 'defer' and could:
        need = sorted({m for c in entry['candidates'] if c['sop'] in {x['sop'] for x in could} for u in c['unknown'] for m in u['missing']})
        reason = (f'보류 후보 {", ".join(x["sop"] for x in could)}는 빠진 값만 확인되면 1위가 될 수 있어(잠정 합계가 1위 유지 후보 {", ".join(rec["sops"])} 이하이거나 계산 불가) 추천을 미룬다. '
                  f'먼저 확인할 값: {", ".join(need)}. 확인 뒤 다시 비교한다. 근거: HI-01 SOP-HI-01, 작업기준.md 4절.')
        return {'추천': [], '사유': reason, '보류': held, '보류_영향': impact}
    if rec['sops']:
        reason = f'교육용 비교 합계 1위 유지 후보 {", ".join(rec["sops"])}를 승인 요청 검토 대상으로 제안한다. 실행 승인은 아니다.' + (f' 보류 후보 {", ".join(held)}는 빠진 값을 확인한 뒤 다시 비교한다.' if held else '')
    else:
        reason = rec['reason']
    return {'추천': rec['sops'], '사유': reason, '보류': held, '보류_영향': impact}


def build(lab, counter='recorded', rules_path=None, policy='defer'):
    if policy not in ('defer', 'propose'):
        raise judge.ContractError(f'policy는 defer·propose: {policy}')
    result = judge.run(lab, rules_path, counter)
    metric = judge.metric_inputs(lab)
    sop = {s['id']: s for s in json.loads((Path(lab)/'입력/sop.json').read_text(encoding='utf-8-sig'))['SOP']}
    items = []
    for entry in result['events']:
        ranking = entry.get('ranking', [])
        items.append({'id': entry['id'], '설비': entry['asset'], '판단_시각': entry['decision_time'], '후보': [candidate(c, sop[c['sop']], ranking) for c in entry['candidates']], '검토_의견': opinion(entry, metric, policy)})
    return {'비교_기준': BASIS, '입력_결정': result['input_decisions'], '항목': items}


def fmt(v):
    if v is None:
        return '-'
    if isinstance(v, list):
        return ';'.join(v)
    if isinstance(v, float):
        return f'{v:.4g}' if abs(v) < 100 else f'{v:.2f}'
    return str(v)


def markdown(review):
    lines = ['# 조치 검토 결과', '', review['비교_기준'], '', '## 판단 입력을 만든 결정', '']
    lines += [f'- {d["항목"]}: {d["결정"]} (근거 {d["근거"]})' for d in review['입력_결정']] + ['']
    for item in review['항목']:
        lines += [f'## {item["id"]} ({item["설비"]}, 판단 {item["판단_시각"]})', '',
                  '| 후보 | 판정 | 비용 | 생산 | 품질 | 에너지 | 감점 | 합계 | 순위 | 승인 |', '|---|---|---:|---:|---:|---:|---:|---:|---:|---|']
        for c in item['후보']:
            v = c['비교값'] or {}
            lines.append(f'| {c["sop"]} {c["이름"]} | {c["판정"]} | ' + ' | '.join(fmt(v.get(k)) for k in ['비용', '생산', '품질', '에너지', '감점', '합계']) + f' | {fmt(c["순위"])} | {c["승인"]["역할"]} |')
        lines.append('')
        for c in item['후보']:
            lines.append(f'### {item["id"]} · {c["sop"]} — {c["판정"]}')
            lines.append('- 판단 입력: ' + ', '.join(f'{k}={fmt(v)}' for k, v in c['입력'].items()))
            if c['이유']:
                for r in c['이유']:
                    actual = ', '.join(f'{k}={fmt(v)}' for k, v in r['실제_입력'].items())
                    extra = f' / 없는 이유: {r["빠진_이유"]}' if r['결과'] == '미확인' else ''
                    lines.append(f'- 이유 {r["규칙"]} {KIND[r["결과"]]}: {r["비교"]} / 실제 {actual}{extra} — {r["설명"]} (출처 {r["출처"]})')
            else:
                lines.append('- 이유: 맞은 규칙과 미확인 규칙 없음')
            lines.append(f'- 원문 출처: {"; ".join(c["원문_출처"])}')
            for x in c.get('비교_불가', []):
                lines.append(f'- 비교 불가: {x}')
            for x in c['추가_확인']:
                lines.append(f'- 추가 확인: {x}')
            lines.append(f'- 승인: {c["승인"]["역할"]}({c["승인"]["출처"]}). {c["승인"]["안내"]}')
            lines.append('')
        for x in item['검토_의견'].get('보류_영향', []):
            lines.append(f'- 보류 후보 {x["sop"]}: 잠정 합계 {fmt(x["잠정_합계"])}, 1위 가능 {fmt(x["1위_가능"])} — {x["근거"]}')
        lines += ['', f'**검토 의견**: {item["검토_의견"]["사유"]}', '']
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('lab'); ap.add_argument('out')
    ap.add_argument('--counter', default='recorded'); ap.add_argument('--policy', default='defer')
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    review = build(a.lab, a.counter, None, a.policy)
    (out/'조치검토결과.json').write_text(json.dumps(review, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (out/'조치검토결과.md').write_text(markdown(review), encoding='utf-8')
    print(f'항목 {len(review["항목"])}건 → {out}')
