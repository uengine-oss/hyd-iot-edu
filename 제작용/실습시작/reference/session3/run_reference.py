"""강사 참조 답안 실행·대조. 학생 폴더는 임시 사본에서만 실행하고 원본 결과/를 건드리지 않는다.

사용: python run_reference.py
산출: expected_results.json, 기대결과.md, 검사기_확인.json (이 폴더)
"""
from pathlib import Path
import copy
import csv
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
import judge  # noqa: E402
import review  # noqa: E402

OUT = ROOT/'산출물'
CRITERIA = OUT/'통합반/실습/03회차/랩/03일차_실습2_조치기준만들기'
JUDGE = OUT/'통합반/실습/03회차/랩/03일차_실습3_판단기능만들기'
REVIEW = OUT/'실전반/실습/03회차/랩/03일차_실습2_판단기능만들기'
PREVIOUS = OUT/'실전반/실습/02회차/랩/02일차_실습5_조치조건표'
failures = []


def fail(msg):
    failures.append(msg)
    print('불일치:', msg)


# ── 1. 원문에서 직접 옮긴 독립 판정(조건표를 읽지 않음) ──
def oracle(sop, kind, codes, x):
    """규칙_원문.txt + 적용범위.md + HM-8.6을 손으로 옮긴 판정. 조건표 행 오타를 잡기 위한 두 번째 구현."""
    rules = []
    if sop == 'SOP-COOL-11': rules.append(('R1', 'WARN', [('forecast_ts1', lambda v: v >= 55)]))
    if sop in ('SOP-COOL-12', 'SOP-COOL-13'): rules.append(('R6', 'WARN', [('forecast_ts1', lambda v: v >= 55)]))
    rules.append(('R2', 'WARN', [('forecast_ps1', lambda v: v < 165)]))
    if sop in ('SOP-COOL-11', 'SOP-COOL-12', 'SOP-COOL-13'): rules.append(('R3', 'EXCLUDE', [('skill_kind', lambda v: v == 'control'), ('plc_mode', lambda v: v != 'REMOTE_AUTO')]))
    rules.append(('R4', 'EXCLUDE', [('plc_state', lambda v: v == 'TRIP'), ('skill_code', lambda v: any(c != 'RESET' for c in v))]))
    if sop in ('SOP-COOL-11', 'SOP-COOL-12'): rules.append(('R5', 'PENALTY', [('fan100_hours', lambda v: v > 24)]))
    x = {**x, 'skill_kind': kind, 'skill_code': codes}
    hit, unknown = {}, set()
    for rid, res, conds in rules:
        vals = [(x[k] is None, None if x[k] is None else f(x[k])) for k, f in conds]
        if any(not m and v is False for m, v in vals):
            continue
        if any(m for m, _ in vals):
            unknown.add(rid)
        else:
            hit[rid] = res
    status = '제외' if 'EXCLUDE' in hit.values() else ('보류' if unknown else '유지')
    return status, set(hit), unknown


def summarize(c):
    return c['status'], {h['rule_id'] for k in ['warnings', 'penalties', 'exclusions'] for h in c[k]}, {u['rule_id'] for u in c['unknown']}


def num(v):
    return None if v in (None, '') else float(v)


def cross_check(result):
    targets = judge.load_targets(JUDGE/'자료/targets.csv')
    rows = judge.read_csv(JUDGE/'자료/cases.csv')
    for row, entry in zip(rows, result['cases']):
        x = {'forecast_ts1': num(row['forecast_ts1_C']), 'forecast_ps1': num(row['forecast_ps1_bar']), 'plc_mode': row['plc_mode'] or None, 'plc_state': row['plc_state'] or None, 'fan100_hours': num(row['fan100_hours'])}
        for c in entry['candidates']:
            t = targets[c['sop']]
            if oracle(c['sop'], t['skill_kind'], t['skill_code'], x) != summarize(c):
                fail(f'사례 {entry["id"]} {c["sop"]}: 엔진 {summarize(c)} / 원문 {oracle(c["sop"], t["skill_kind"], t["skill_code"], x)}')
    requests = json.loads((JUDGE/'자료/metrics/판정_요청.json').read_text(encoding='utf-8'))['요청']
    for q, entry in zip(requests, result['requests']):
        for cand, c in zip(q['후보'], entry['candidates']):
            t = targets[c['sop']]
            x = {'forecast_ts1': cand['forecast_ts1'], 'forecast_ps1': cand['forecast_ps1'], 'plc_mode': q['plc_mode'], 'plc_state': {'RUN': 'RUNNING'}.get(q['plc_state'], q['plc_state']), 'fan100_hours': q['fan100_hours']}
            if oracle(c['sop'], t['skill_kind'], t['skill_code'], x) != summarize(c):
                fail(f'요청 {entry["id"]} {c["sop"]}: 엔진 {summarize(c)} / 원문 {oracle(c["sop"], t["skill_kind"], t["skill_code"], x)}')
    # 지표_정의.md의 손계산 예(C01 SOP-COOL-12)
    c01 = next(c for c in result['requests'][0]['candidates'] if c['sop'] == 'SOP-COOL-12')['comparison']
    for k, v in {'비용': 3.86, '생산': 33.33, '품질': 0.0, '에너지': 0.54}.items():
        if c01[k] != v:
            fail(f'C01 SOP-COOL-12 {k}: {c01[k]} / 손계산 {v}')
    print('원문 독립 판정·C01 손계산 대조 완료')


def previous_session_check():
    """2회차 실전 실습5 사례 A~I를 SOP-COOL-11(=skill:fan-max)로 넣어 2회차 강사 대조표와 비교."""
    groups = judge.load_rules(HERE/'rules.csv')
    table = {}
    for line in (ROOT/'제작용/실습시작/reference/실전반/조건표_사례검토.md').read_text(encoding='utf-8').splitlines():
        cells = [c.strip() for c in line.strip('|').split('|')]
        if len(cells) == 7 and len(cells[0]) == 1 and cells[0].isalpha():
            table[cells[0]] = cells
    checked = 0
    for row in judge.read_csv(PREVIOUS/'사례_입력.csv'):
        inputs = judge.normalize({'forecast_ts1': row['forecast_ts1_C'], 'forecast_ps1': row['forecast_ps1_bar'], 'plc_mode': row['plc_mode'], 'plc_state': row['plc_state'], 'fan100_hours': row['fan100_hours'], 'skill_kind': row['skill_kind'], 'skill_code': row['skill_code'].split(';')}, '2회차 사례_입력.csv')
        c = judge.evaluate('SOP-COOL-11', inputs, groups)
        status, hit, unknown = summarize(c)
        cells = table[row['case']]
        want_hit = set() if cells[1] == '없음' else set(cells[1].split('·'))
        want_status = {'유지': '유지', '제외': '제외', '보류': '보류', '제외·미확인 병기': '제외'}[cells[6]]
        want_unknown = {'R1'} if 'R1' in cells[5] else set()
        if (status, hit, unknown) != (want_status, want_hit, want_unknown) or sum(p['amount_만원'] for p in c['penalties']) != float(cells[3]):
            fail(f'2회차 사례 {row["case"]}: 엔진 {(status, hit, unknown)} / 2회차 대조표 {cells}')
        checked += 1
    print(f'2회차 실습5 사례 {checked}건과 2회차 강사 대조표 대조 완료')
    return checked


# ── 2. 학생 검사기 실제 실행과 고의 손상 ──
def run_check(folder):
    p = subprocess.run([sys.executable, 'check.py'], cwd=folder, capture_output=True, text=True, encoding='utf-8', env={'PYTHONUTF8': '1', 'SYSTEMROOT': 'C:\\Windows'})
    return p.returncode, (p.stdout + p.stderr).strip()


def checker_trials(tmp):
    records = []

    def trial(lab, name, mutate, path, expect_pass):
        folder = tmp/lab.name
        target = folder/path
        original = target.read_bytes()
        mutate(target)
        code, out = run_check(folder)
        target.write_bytes(original)
        ok = (code == 0) == expect_pass
        records.append({'lab': lab.name, 'trial': name, 'exit': code, 'expected_pass': expect_pass, 'ok': ok, 'output_head': out.splitlines()[:3]})
        if not ok:
            fail(f'검사기 {lab.name} [{name}] 기대 {"통과" if expect_pass else "실패"}, 실제 exit {code}: {out[:300]}')

    def edit_json(fn):
        def m(path):
            data = json.loads(path.read_text(encoding='utf-8'))
            fn(data)
            path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        return m

    def edit_text(old, new):
        def m(path):
            text = path.read_text(encoding='utf-8')
            if old not in text:
                raise RuntimeError(f'손상 대상 문자열 없음: {old}')
            path.write_text(text.replace(old, new, 1), encoding='utf-8')
        return m

    noop = lambda p: None
    # 통합 실습2
    trial(CRITERIA, '참조 답안', noop, '결과/rules.csv', True)
    trial(CRITERIA, '빈 결과 틀', lambda p: (tmp/CRITERIA.name/'결과/sop.json').write_text('{"SOP": []}', encoding='utf-8'), '결과/sop.json', False)
    trial(CRITERIA, '경계 표시와 연산자 불일치', edit_text('forecast_ts1,>=,55,℃,예', 'forecast_ts1,>=,55,℃,아니오'), '결과/rules.csv', False)
    trial(CRITERIA, '같은 묶음의 결과 불일치', edit_text('R3,SOP-COOL-11,2,AND,plc_mode,!=,REMOTE_AUTO,,해당없음,EXCLUDE', 'R3,SOP-COOL-11,2,AND,plc_mode,!=,REMOTE_AUTO,,해당없음,WARN'), '결과/rules.csv', False)
    trial(CRITERIA, '감점 금액 누락', edit_text('PENALTY,20', 'PENALTY,'), '결과/rules.csv', False)
    trial(CRITERIA, '모델에 없는 ID', edit_json(lambda d: d['SOP'][0]['모델_참조']['센서'].append('HYD-01:TS4')), '결과/sop.json', False)
    trial(CRITERIA, '단계 순서 건너뜀', edit_json(lambda d: d['SOP'][0]['수행_단계'][1].update({'순서': 3})), '결과/sop.json', False)
    trial(CRITERIA, 'SOP 누락', edit_json(lambda d: d['SOP'].pop()), '결과/sop.json', False)
    # 통합 실습3
    trial(JUDGE, '참조 답안', noop, '결과/result.json', True)

    def excluded_as_kept(d):
        c = next(c for c in d['cases'] if c['id'] == 'G')['candidates'][0]
        c['status'] = '유지'

    def excluded_in_ranking(d):
        q = next(q for q in d['requests'] if q['id'] == 'C05')
        q['ranking'].append({'rank': 2, 'sop': 'SOP-COOL-11', '합계': 9999})

    def double_penalty(d):
        c = next(c for c in d['requests'] if c['id'] == 'C04')['candidates'][0]
        c['comparison']['감점'] = 40
        c['comparison']['합계'] += 20

    def unknown_dropped(d):
        c = next(c for c in d['cases'] if c['id'] == 'K')['candidates'][0]
        c['unknown'][0]['missing'] = []

    def all_excluded_recommend(d):
        q = next(q for q in d['requests'] if q['id'] == 'C10')
        q['recommendation']['reason'] = ''

    def missing_request(d):
        d['requests'].pop()

    def tie_rank(d):
        q = next(q for q in d['requests'] if q['id'] == 'C01')
        q['ranking'][1]['rank'] = 3

    for name, fn in [('제외 후보를 유지로', excluded_as_kept), ('제외 후보를 순위에', excluded_in_ranking), ('감점 두 번 합산', double_penalty), ('미확인 입력 이름 누락', unknown_dropped), ('모두 제외인데 이유 없음', all_excluded_recommend), ('요청 누락', missing_request), ('순위 번호 오류', tie_rank)]:
        trial(JUDGE, name, edit_json(fn), '결과/result.json', False)
    # 실전 실습2
    trial(REVIEW, '참조 답안', noop, '결과/조치검토결과.json', True)

    def extra_removed(d):
        item = next(i for i in d['항목'] if i['id'] == 'C13')
        item['후보'][0]['추가_확인'] = []

    def recommend_excluded(d):
        item = next(i for i in d['항목'] if i['id'] == 'C05')
        item['검토_의견']['추천'] = ['SOP-COOL-11']

    def no_source(d):
        d['항목'][0]['후보'][0]['원문_출처'] = []

    def no_approval_note(d):
        next(i for i in d['항목'] if i['id'] == 'C01')['후보'][0]['승인']['안내'] = ''

    def compare_case(d):
        d['항목'][0]['후보'][0]['비교값'] = {'비용': 1, '생산': 1, '품질': 0, '에너지': 0, '감점': 0, '합계': 2}

    def keep_excluded_k(d):
        item = next(i for i in d['항목'] if i['id'] == 'K')
        item['후보'][0]['판정'] = '보류'

    for name, fn in [('보류 후보의 추가 확인 삭제', extra_removed), ('제외 후보를 추천', recommend_excluded), ('원문 출처 없음', no_source), ('승인 안내 없음', no_approval_note), ('사례에 비교값', compare_case), ('제외+미확인을 보류로', keep_excluded_k)]:
        trial(REVIEW, name, edit_json(fn), '결과/조치검토결과.json', False)
    def drop_heading(path):
        text = path.read_text(encoding='utf-8')
        kept = [l for l in text.splitlines() if not (l.startswith('#') and 'C14' in l)]
        path.write_text(chr(10).join(kept), encoding='utf-8')
    trial(REVIEW, 'md에 C14 절 제목 없음', drop_heading, '결과/조치검토결과.md', False)
    return records


def boundary_check():
    names = []
    for lab in [CRITERIA, JUDGE, REVIEW]:
        with zipfile.ZipFile(lab.with_suffix('.zip')) as z:
            for n in z.namelist():
                low = n.lower()
                bad = any(x in low for x in ['judge.py', 'review.py', 'result.json', '조치검토결과.json', 'expected', '기대결과.md'.lower() + '_정답'])
                if n.endswith('결과/rules.csv') and len(z.read(n).decode('utf-8-sig').strip().splitlines()) > 1:
                    bad = True
                if n.endswith('결과/sop.json') and json.loads(z.read(n)).get('SOP'):
                    bad = True
                if '/코드/' in n:
                    bad = True
                if bad:
                    names.append(n)
    if names:
        fail(f'학생 ZIP 정답 경계 위반: {names}')
    print('학생 ZIP 정답 경계(참조 구현·완성 결과·옛 코드/ 없음) 확인')


def table_md(result, rv):
    lines = ['# 3회차 판정 랩 기대 결과 (강사용)', '', '학생 ZIP에 넣지 않는다. `run_reference.py`가 참조 조건표(`rules.csv`)와 참조 구현(`judge.py`, `review.py`)을 학생 시작본의 실제 입력에 실행해 만든 결과다. 같은 입력을 원문에서 직접 옮긴 두 번째 판정(`run_reference.py`의 oracle)과 대조해 일치했다.', '',
             '표기: 일치 규칙 [ ], 미확인 { }(빠진 입력). 금액 단위 만원. 통합 실습2의 학생 결정표가 R6(HM-8.6 확장)을 두지 않았거나 적용 대상을 다르게 정했다면 사례대조 결과도 달라진다. 원문 근거로 판단한다.', '',
             '## 사례 A~M (판정)', '', '| 사례 | 후보 | 판정 | 일치 규칙 | 미확인 | 유지 후보 / 없음 사유 |', '|---|---|---|---|---|---|']
    for e in result['cases']:
        for i, c in enumerate(e['candidates']):
            s, hit, unk = summarize(c)
            extra = (', '.join(e['allowed']) or e.get('no_allowed_reason', '')) if i == 0 else ''
            lines.append(f'| {e["id"]} | {c["sop"]} | {s} | {"·".join(sorted(hit)) or "-"} | {"·".join(f"{u["rule_id"]}:{"/".join(u["missing"])}" for u in c["unknown"]) or "-"} | {extra} |')
    lines += ['', '## 요청 C01~C14 (판정과 교육용 비교)', '', '| 요청 | 후보 | 판정 | 일치 규칙 | 미확인 | 비용 | 생산 | 품질 | 에너지 | 감점 | 합계 | 순위 |', '|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for e in result['requests']:
        ranks = {r['sop']: r['rank'] for r in e['ranking']}
        for c in e['candidates']:
            s, hit, unk = summarize(c)
            v = c.get('comparison') or {}
            lines.append(f'| {e["id"]} | {c["sop"]} | {s} | {"·".join(sorted(hit)) or "-"} | {"·".join(f"{u["rule_id"]}:{"/".join(u["missing"])}" for u in c["unknown"]) or "-"} | ' + ' | '.join(str(v.get(k, '-')) for k in ['비용', '생산', '품질', '에너지', '감점', '합계']) + f' | {ranks.get(c["sop"], "-")} |')
        lines.append(f'| {e["id"]} | 검토 의견 | | | | | | | | | | {", ".join(e["recommendation"]["sops"]) or "추천 없음"}: {e["recommendation"]["reason"]} |')
    lines += ['', '## 판단 근거 요약', '',
              '- 경계: 55 ℃는 R1·R6에 포함(이상), 165 bar는 R2에 불포함(미만), 24 h는 R5에 불포함(초과). 사례 C·D, 요청 C02~C04·C07·C09.',
              '- 감점은 R5 묶음당 한 번(20만원). SOP-COOL-11·12에만 적용(HM-8.8, 적용범위.md). C04·C12에서 부하 감소·작업지시 후보에는 감점 없음.',
              '- 제외+미확인 병기: 사례 K(R3 제외 + 예측 유온 누락). 보류: H·L, C13(팬 시간 누락 → SOP-COOL-11·12만), C14(SOP-COOL-13 예측 유온 누락).',
              '- 적용 대상 밖: 사례 M의 SOP-COOL-14는 R3·R5 대상이 아니어서 모드·팬 시간이 비어도 유지.',
              '- 모두 제외: 사례 F·G·K, 요청 C10·C11. C10·C11은 R4(트립 중 리셋 외 코드)가 규칙 발췌의 적용 대상 전체(applies=[])로 SOP-COOL-14의 WO_CREATE에도 적용된 결과다(아래 남은 문제 1).',
              '- C01 SOP-COOL-12의 네 손실은 지표_정의.md 손계산(3.86 / 33.33 / 0 / 0.54)과 일치.',
              '- 비교 합계는 교육용이며 HYD 일곱 성분 점수가 아니다. 순위는 실행 승인이 아니다(승인 역할: SOP-COOL-11~13 운전원, SOP-COOL-14 설비보전팀장).', '',
              '## 남은 문제(원자료 해석)', '',
              '1. R4 적용 대상: 규칙 발췌 rule:trip-reset-only의 applies가 빈 목록이고, 적용범위.md가 "RESET 외 코드 존재를 목록으로 판정"이라 적어 SOP-COOL-14(작업지시 WO_CREATE)도 트립 중 제외로 처리했다. CMMS 작업지시 발행이 PLC 제어 명령인지는 원문 근거가 부족하다. 이 해석을 바꾸면 C10·C11에서 SOP-COOL-14가 유지·추천된다.',
              '2. R6(HM-8.6 확장): 시드 R1은 팬 최대 운전용이라 SOP-COOL-12·13에는 HM-8.6 회복 판정 문장을 근거로 별도 규칙을 두었다. SOP-COOL-14는 HM-8.7 근본 조치로 HM-8.6 회복 판정 대상이 아니라고 보고 두지 않았다.', '']
    return '\n'.join(lines)


def main():
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        for lab in [CRITERIA, JUDGE, REVIEW]:
            shutil.copytree(lab, tmp/lab.name)
        shutil.copy2(HERE/'sop.json', tmp/CRITERIA.name/'결과/sop.json')
        shutil.copy2(HERE/'rules.csv', tmp/CRITERIA.name/'결과/rules.csv')
        result = judge.run(tmp/JUDGE.name)
        (tmp/JUDGE.name/'결과/result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        rv = review.build(tmp/REVIEW.name)
        (tmp/REVIEW.name/'결과/조치검토결과.json').write_text(json.dumps(rv, ensure_ascii=False, indent=2), encoding='utf-8')
        (tmp/REVIEW.name/'결과/조치검토결과.md').write_text(review.markdown(rv), encoding='utf-8')
        if judge.run(tmp/REVIEW.name) != result:
            fail('실전반 시작본 입력으로 돌린 판정이 통합반 실습3과 다름')
        cross_check(result)
        checked = previous_session_check()
        records = checker_trials(tmp)
        (HERE/'참조_조치검토결과.md').write_text(review.markdown(rv), encoding='utf-8')
    boundary_check()
    (HERE/'expected_results.json').write_text(json.dumps({'판본': '2026-10-28-s3-v1', 'integrated_judge_result': result, 'practical_review': rv}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (HERE/'기대결과.md').write_text(table_md(result, rv), encoding='utf-8')
    (HERE/'검사기_확인.json').write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    passed = sum(r['ok'] for r in records)
    print(f'검사기 시험 {passed}/{len(records)} 기대대로, 2회차 사례 {checked}건 대조')
    if failures:
        print(f'불일치 {len(failures)}건'); sys.exit(1)
    print('참조 실행·대조 모두 일치')


if __name__ == '__main__':
    main()
