"""강사 참조 답안 실행·대조(현업화 판). 학생 폴더는 임시 사본에서만 실행하고 원본 결과/를 건드리지 않는다.

사용: python run_reference.py
대상: 실전 2-5 조건표, 통합 3-2 SOP·결정표, 통합 3-3 판정 기능, 실전 3-2 조치 검토 결과.
1. 참조 엔진(judge.py·review.py)을 학생 시작본 입력에 실행한다. 판단 갈림 두 축(팬 카운터 기록값/경과 더함,
   트립·인터록 예측 규칙의 작업지시 후보 적용 여부)과 R6(HM-8.6 확장) 유무를 모두 실행해 바뀌는 사례를 기록한다.
2. 원문에서 직접 옮긴 두 번째 구현(oracle, 조건표·judge.py를 읽지 않음)과 모든 갈래에서 대조한다.
3. 손으로 구한 표본(원자료 행을 읽어 계산)과 대조한다.
4. 학생 검사기를 참조 답안·고의 손상 입력으로 실제 실행한다.
5. 학생 ZIP에 참조 구현·완성 결과가 없는지 본다.
산출: expected_results.json, 기대결과.md, 검사기_확인.json, 참조_조치검토결과.md, ../실전반/조건표_사례검토.md
"""
from datetime import datetime
from pathlib import Path
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
CONDITIONS = OUT/'실전반/실습/02회차/랩/02일차_실습5_조치조건표'
CRITERIA = OUT/'통합반/실습/03회차/랩/03일차_실습2_조치기준만들기'
JUDGE = OUT/'통합반/실습/03회차/랩/03일차_실습3_판단기능만들기'
REVIEW = OUT/'실전반/실습/03회차/랩/03일차_실습2_판단기능만들기'
LABS = [CONDITIONS, CRITERIA, JUDGE, REVIEW]
failures = []


def fail(msg):
    failures.append(msg)
    print('불일치:', msg)


def rows(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


# ── 갈래 조건표 ──
def variant_rules(tmp):
    main = rows(HERE/'rules.csv')
    header = list(main[0].keys())

    def save(name, table):
        path = tmp/name
        with path.open('w', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, header, lineterminator='\n'); w.writeheader(); w.writerows(table)
        return path
    alt = list(main)
    for rid in ['R4', 'R7']:
        alt += [dict(r, action='SOP-COOL-14') for r in main if r['rule_id'] == rid and r['action'] == 'SOP-COOL-11']
    return {'main': HERE/'rules.csv', 'wo': save('rules_wo.csv', alt), 'no_r6': save('rules_no_r6.csv', [r for r in main if r['rule_id'] != 'R6'])}


# ── 1. 원문에서 직접 옮긴 독립 구현(조건표·judge.py를 읽지 않음) ──
def oracle(lab, counter='recorded', wo_scope=False, r6=True):
    """원천 해석: 수집_설명.md(12초 하트비트 유예, 품질 bad 대체 금지, 카운터 종료/12분, 예측 120초·MPa), HI-01 SOP-HI-01.
    규칙: 규칙_원문.txt의 식과 적용 대상 + HM-8.6(R6) + 강사 결정(트립·인터록 예측 규칙의 작업지시 적용 여부)."""
    d = Path(lab)/'자료'
    T = lambda s: datetime.fromisoformat(s)
    status, counters, fc = {}, {}, {}
    for r in rows(d/'PLC_상태_수신.csv'):
        status.setdefault(r['설비'], []).append(r)
    for r in rows(d/'팬_운전_카운터.csv'):
        counters.setdefault(r['설비'], []).append(r)
    for r in rows(d/'예측_결과.csv'):
        fc[(r['사례'], r['후보'])] = r
    kinds = {r['sop_id']: (r['kind'], r['codes'].split(';')) for r in rows(d/'targets.csv')}
    out = {}
    for a in rows(d/'경보_목록.csv'):
        t = T(a['판단_시각'])
        st = sorted((r for r in status.get(a['설비'], []) if T(r['수신_시각']) <= t), key=lambda r: T(r['수신_시각']))
        last = st[-1] if st else None
        ok = last is not None and last['품질'] == 'good' and (t - T(last['수신_시각'])).total_seconds() <= 12
        mode = last['운전_모드'] if ok else None
        state = ('TRIP' if last['상태'] == 'TRIP' else 'RUNNING') if ok else None
        cs = sorted((r for r in counters.get(a['설비'], []) if T(r['기록_시각']) <= t), key=lambda r: T(r['기록_시각']))
        c = cs[-1]
        age = (t - T(c['기록_시각'])).total_seconds() / 60
        if c['기록_종류'] == '종료':
            fan = 0.0
        elif age > 12:
            fan = None
        else:
            fan = (int(c['팬100_연속_분']) + (age if counter == 'elapsed' else 0)) / 60
        for sop in a['후보'].split(';'):
            f = fc.get((a['사례'], sop))
            ts1 = ps1 = None
            if f and f['상태'] == '완료' and (t - T(f['기준_관측_시각'])).total_seconds() <= 120:
                ts1 = float(f['예측_TS1_C'])
                ps1 = float(f['예측_PS1']) * (10 if f['PS1_단위'] == 'MPa' else 1)
            kind, codes = kinds[sop]
            control = kind == 'control'
            rules = []
            if sop == 'SOP-COOL-11':
                rules.append(('R1', 'WARN', [ts1 is None or ts1 >= 55], [ts1 is None]))
            if r6 and sop in ('SOP-COOL-12', 'SOP-COOL-13'):
                rules.append(('R6', 'WARN', [ts1 is None or ts1 >= 55], [ts1 is None]))
            rules.append(('R2', 'WARN', [ps1 is None or ps1 < 165], [ps1 is None]))
            if sop in ('SOP-COOL-11', 'SOP-COOL-12', 'SOP-COOL-13'):
                rules.append(('R3', 'EXCLUDE', [control, mode is None or mode != 'REMOTE_AUTO'], [False, mode is None]))
            if control or wo_scope:
                rules.append(('R4', 'EXCLUDE', [state is None or state == 'TRIP', any(x != 'RESET' for x in codes)], [state is None, False]))
                rules.append(('R7', 'EXCLUDE', [ts1 is None or ts1 >= 65], [ts1 is None]))
            if sop in ('SOP-COOL-11', 'SOP-COOL-12'):
                rules.append(('R5', 'PENALTY', [fan is None or fan > 24], [fan is None]))
            hit, unknown = set(), set()
            excluded = False
            for rid, res, holds, missing in rules:
                if not all(holds):
                    continue
                if any(missing):
                    unknown.add(rid)
                else:
                    hit.add(rid)
                    excluded = excluded or res == 'EXCLUDE'
            s = '제외' if excluded else ('보류' if unknown else '유지')
            out[(a['사례'], sop)] = (s, hit, unknown, 20.0 if 'R5' in hit else 0.0, {'forecast_ts1': ts1, 'forecast_ps1': ps1, 'fan100_hours': fan, 'plc_mode': mode, 'plc_state': state})
    return out


def summary(result):
    out = {}
    for e in result['events']:
        for c in e['candidates']:
            hit = {h['rule_id'] for k in ['warnings', 'penalties', 'exclusions'] for h in c[k]}
            unk = {u['rule_id'] for u in c['unknown']}
            inputs = {k: c['inputs'][k] for k in ['forecast_ts1', 'forecast_ps1', 'fan100_hours', 'plc_mode', 'plc_state']}
            out[(e['id'], c['sop'])] = (c['status'], hit, unk, sum(p['amount_만원'] for p in c['penalties']), inputs)
    return out


def same_inputs(a, b):
    for k in a:
        x, y = a[k], b[k]
        if (x is None) != (y is None):
            return False
        if isinstance(x, float) and abs(x - y) > 1e-9:
            return False
        if not isinstance(x, float) and x != y:
            return False
    return True


def cross_check(lab, results):
    checked = 0
    for (counter, rules_key), result in results.items():
        o = oracle(lab, counter, wo_scope=(rules_key == 'wo'), r6=(rules_key != 'no_r6'))
        e = summary(result)
        if set(o) != set(e):
            fail(f'oracle/엔진 후보 구성 다름 {counter}/{rules_key}')
        for key in o:
            if o[key][:4] != e[key][:4] or not same_inputs(o[key][4], e[key][4]):
                fail(f'{counter}/{rules_key} {key}: 엔진 {e[key]} / 원문 {o[key]}')
            checked += 1
    print(f'원문 독립 구현과 엔진 대조: 갈래 {len(results)}개 × 후보 192 = {checked}건')
    return checked


# ── 손으로 구한 표본(원자료 행을 직접 읽어 계산, 2026-10-28) ──
HAND = [
    # E21 HYD-02 정상: 예측 52.60/48.63/52.12/61.27 ℃, 182/179/176/182 bar, PLC 18:11:12 good, 카운터 종료, 오더 9.0 h·1550 ea·로트 800
    ('E21', 'SOP-COOL-11', '유지', set(), {'비용': 5.79, '생산': 0.0, '품질': 0.0, '에너지': 0.81, '합계': 6.60}),
    ('E21', 'SOP-COOL-12', '유지', set(), {'비용': 5.79, '생산': 50.0, '품질': 0.0, '에너지': 0.81, '합계': 56.60}),
    ('E21', 'SOP-COOL-13', '유지', set(), {'비용': 40.0, '생산': 327.14, '품질': 0.0, '에너지': 0.0, '합계': 367.14}),
    ('E21', 'SOP-COOL-14', '유지', set(), {'비용': 40.0, '생산': 150.0, '품질': 150.0, '에너지': 0.0, '합계': 340.0}),
    # E26 HYD-03 옛 MPa 내보내기 16.499 MPa = 164.99 bar < 165 → 네 후보 모두 R2 경고
    ('E26', 'SOP-COOL-11', '유지', {'R2'}, None), ('E26', 'SOP-COOL-14', '유지', {'R2'}, None),
    # E03 마지막 PLC 수신 15:23:35 품질 bad(판단 15:23:41) → 모드·상태 없음, 앞 수신으로 대신하지 않음
    ('E03', 'SOP-COOL-11', '보류', set(), None), ('E03', 'SOP-COOL-14', '유지', set(), None),
    # E39 카운터 06:48:17 주기 1440분, 판단 06:49:17: 기록값 24.0 h(감점 없음) / 경과 더함 24.017 h(감점) — 아래 갈래 표본
    ('E39', 'SOP-COOL-11', '유지', {'R1'}, None),
    # E11 SOP-COOL-14 예측 65.00 ℃: 주 갈래(작업지시에 인터록 예측 규칙 미적용) 유지
    ('E11', 'SOP-COOL-14', '유지', set(), None),
]
HAND_BRANCH = [
    ('elapsed', 'main', 'E39', 'SOP-COOL-11', '유지', {'R1', 'R5'}),
    ('elapsed', 'main', 'E22', 'SOP-COOL-12', '유지', {'R6', 'R5'}),
    ('recorded', 'wo', 'E11', 'SOP-COOL-14', '제외', {'R7'}),
    ('recorded', 'wo', 'E09', 'SOP-COOL-14', '제외', {'R2', 'R4'}),
]


def hand_check(results, metric_doc):
    main = summary(results[('recorded', 'main')])
    comp = {(e['id'], c['sop']): c.get('comparison') for e in results[('recorded', 'main')]['events'] for c in e['candidates']}
    n = 0
    for eid, sop, status, hits, values in HAND:
        got = main[(eid, sop)]
        if got[0] != status or got[1] != hits:
            fail(f'손계산 {eid} {sop}: 기대 {status} {hits} / 엔진 {got[:2]}')
        if values:
            for k, v in values.items():
                if abs(comp[(eid, sop)][k] - v) > 0.005:
                    fail(f'손계산 {eid} {sop} {k}: 기대 {v} / 엔진 {comp[(eid, sop)][k]}')
        n += 1
    for counter, rk, eid, sop, status, hits in HAND_BRANCH:
        got = summary(results[(counter, rk)])[(eid, sop)]
        if got[0] != status or got[1] != hits:
            fail(f'손계산 갈래 {counter}/{rk} {eid} {sop}: 기대 {status} {hits} / 엔진 {got[:2]}')
        n += 1
    # 지표_정의.md 손계산 예(문서의 숫자를 엔진과 대조)
    import re
    eid = re.search(r'사례 (E\d+)의 SOP-COOL-12', metric_doc).group(1)
    want = {k: float(v) for k, v in re.findall(r'\| (비용|생산|품질|에너지) \| [^|]+ \| ([\d.]+) \|', metric_doc)}
    for k, v in want.items():
        if abs(comp[(eid, 'SOP-COOL-12')][k] - v) > 0.005:
            fail(f'지표_정의.md 손계산 {eid} {k}: 문서 {v} / 엔진 {comp[(eid, "SOP-COOL-12")][k]}')
    print(f'손계산 표본 {n}건 + 지표_정의.md 예({eid}) 대조')
    return n, eid


# ── 2. 학생 검사기 실제 실행과 고의 손상 ──
def run_check(folder):
    p = subprocess.run([sys.executable, 'check.py'], cwd=folder, capture_output=True, text=True, encoding='utf-8', env={'PYTHONUTF8': '1', 'SYSTEMROOT': 'C:\\Windows'})
    return p.returncode, (p.stdout + p.stderr).strip()


def checker_trials(tmp):
    records = []

    def trial(lab, name, mutate, path, expect_pass, expect_text=None):
        folder = tmp/lab.name
        target = folder/path
        original = target.read_bytes() if target.exists() else None
        mutate(target)
        code, out = run_check(folder)
        if original is None:
            target.unlink(missing_ok=True)
        else:
            target.write_bytes(original)
        ok = (code == 0) == expect_pass and (expect_text is None or all(t in out for t in expect_text))
        records.append({'lab': lab.name, 'trial': name, 'exit': code, 'expected_pass': expect_pass, 'ok': ok, 'output_head': out.splitlines()[:6]})
        if not ok:
            fail(f'검사기 {lab.name} [{name}] 기대 {"통과" if expect_pass else "실패"} {expect_text or ""}, 실제 exit {code}: {out[:400]}')

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

    def put(text):
        return lambda p: p.write_text(text, encoding='utf-8')

    noop = lambda p: None
    header = 'rule_id,action,condition_index,logic,input,operator,value,unit,boundary_included,result,penalty_만원,reason,source_section\n'
    # 실전 2-5
    trial(CONDITIONS, '참조 조건표', noop, '결과/조건표.csv', True, ['조건표.csv: 통과'])
    trial(CONDITIONS, '빈 틀(형식만)', put(header), '결과/조건표.csv', False, ['조건표.csv: 빈 틀'])
    trial(CONDITIONS, '경계 표시와 연산자 불일치', edit_text('forecast_ts1,>=,55,℃,예', 'forecast_ts1,>=,55,℃,아니오'), '결과/조건표.csv', False)
    trial(CONDITIONS, '감점 금액 누락', edit_text('PENALTY,20', 'PENALTY,'), '결과/조건표.csv', False)
    trial(CONDITIONS, '숫자 입력 단위 누락', edit_text('forecast_ps1,<,165,bar', 'forecast_ps1,<,165,'), '결과/조건표.csv', False)
    trial(CONDITIONS, '계약에 없는 입력 이름', edit_text('fan100_hours,>,24', 'fan100_minutes,>,24'), '결과/조건표.csv', False)
    # 통합 3-2
    trial(CRITERIA, '참조 답안', noop, '결과/rules.csv', True, ['sop.json: 통과', 'rules.csv: 통과'])
    trial(CRITERIA, 'sop만 완성·rules 빈 틀(단계 구분)', put(header), '결과/rules.csv', False, ['sop.json: 통과', 'rules.csv: 빈 틀'])
    trial(CRITERIA, 'sop 빈 틀', put('{"SOP": []}'), '결과/sop.json', False, ['sop.json: 빈 틀'])
    trial(CRITERIA, '같은 묶음의 결과 불일치', edit_text('R3,SOP-COOL-11,2,AND,plc_mode,!=,REMOTE_AUTO,,해당없음,EXCLUDE', 'R3,SOP-COOL-11,2,AND,plc_mode,!=,REMOTE_AUTO,,해당없음,WARN'), '결과/rules.csv', False)
    trial(CRITERIA, '모델에 없는 ID', edit_json(lambda d: d['SOP'][0]['모델_참조']['센서'].append('HYD-01:TS9')), '결과/sop.json', False)
    trial(CRITERIA, '단계 순서 건너뜀', edit_json(lambda d: d['SOP'][0]['수행_단계'][1].update({'순서': 3})), '결과/sop.json', False)
    trial(CRITERIA, 'SOP 누락', edit_json(lambda d: d['SOP'].pop()), '결과/sop.json', False)
    trial(CRITERIA, '사례대조 빈 칸 경고', noop, '결과/사례대조.md', True, ['사례대조.md: 작성 중'])
    # 통합 3-3
    trial(JUDGE, '참조 답안', noop, '결과/result.json', True, ['result.json: 통과', '기대결과.md: 작성됨'])

    def first(d, eid):
        return next(e for e in d['events'] if e['id'] == eid)

    def excluded_as_kept(d):
        first(d, 'E04')['candidates'][0]['status'] = '유지'

    def excluded_in_ranking(d):
        first(d, 'E04')['ranking'].append({'rank': 2, 'sop': 'SOP-COOL-11', '합계': 9999})

    def double_penalty(d):
        c = first(d, 'E33')['candidates'][0]
        c['comparison']['감점'] = 40; c['comparison']['합계'] += 20

    def unknown_dropped(d):
        first(d, 'E30')['candidates'][0]['unknown'][0]['missing'] = []

    def null_without_reason(d):
        first(d, 'E03')['candidates'][0]['missing_reasons'] = {}

    def mpa_not_converted(d):
        first(d, 'E26')['candidates'][0]['inputs']['forecast_ps1'] = 16.499

    def minutes_not_converted(d):
        first(d, 'E39')['candidates'][0]['inputs']['fan100_hours'] = 1440.0

    def no_reason_when_none(d):
        first(d, 'E17')['recommendation']['reason'] = ''

    def missing_event(d):
        d['events'].pop()

    def tie_rank(d):
        first(d, 'E21')['ranking'][1]['rank'] = 3

    def no_decisions(d):
        d['input_decisions'] = []

    for name, fn in [('제외 후보를 유지로', excluded_as_kept), ('제외 후보를 순위에', excluded_in_ranking), ('감점 두 번 합산', double_penalty), ('미확인 입력 이름 누락', unknown_dropped),
                     ('값 없음 이유 누락', null_without_reason), ('MPa 환산 안 함', mpa_not_converted), ('분을 h로 환산 안 함', minutes_not_converted), ('추천 없음 사유 없음', no_reason_when_none),
                     ('사례 누락', missing_event), ('순위 번호 오류', tie_rank), ('입력 결정 기록 없음', no_decisions)]:
        trial(JUDGE, name, edit_json(fn), '결과/result.json', False)
    trial(JUDGE, '기대결과 실제 칸 비움 경고', edit_text('| 유지 | 일치 |', '|  | 일치 |'), '결과/기대결과.md', True, ['기대결과.md: 작성 중'])
    # 실전 3-2
    trial(REVIEW, '참조 답안', noop, '결과/조치검토결과.json', True, ['조치검토결과.json·.md: 통과'])

    def item(d, iid):
        return next(i for i in d['항목'] if i['id'] == iid)

    def extra_removed(d):
        item(d, 'E30')['후보'][0]['추가_확인'] = []

    def recommend_excluded(d):
        item(d, 'E04')['검토_의견']['추천'] = ['SOP-COOL-11']

    def no_source(d):
        item(d, 'E01')['후보'][0]['원문_출처'] = []

    def no_approval_note(d):
        item(d, 'E21')['후보'][0]['승인']['안내'] = ''

    def keep_excluded(d):
        item(d, 'E47')['후보'][0]['판정'] = '보류'

    def missing_reason_text(d):
        c = item(d, 'E03')['후보'][0]
        for r in c['이유']:
            r.pop('빠진_이유', None)

    def unconverted(d):
        item(d, 'E26')['후보'][0]['입력']['forecast_ps1'] = 16.499

    for name, fn in [('보류 후보의 추가 확인 삭제', extra_removed), ('제외 후보를 추천', recommend_excluded), ('원문 출처 없음', no_source), ('승인 안내 없음', no_approval_note),
                     ('제외+미확인을 보류로', keep_excluded), ('미확인의 없는 이유 누락', missing_reason_text), ('MPa 환산 안 함', unconverted)]:
        trial(REVIEW, name, edit_json(fn), '결과/조치검토결과.json', False)

    def drop_heading(path):
        text = path.read_text(encoding='utf-8')
        path.write_text('\n'.join(l for l in text.splitlines() if not (l.startswith('#') and 'E48' in l)), encoding='utf-8')
    trial(REVIEW, 'md에 E48 절 제목 없음', drop_heading, '결과/조치검토결과.md', False)
    return records


def boundary_check():
    names = []
    for lab in LABS:
        with zipfile.ZipFile(lab.with_suffix('.zip')) as z:
            for n in z.namelist():
                low = n.lower()
                bad = any(x in low for x in ['judge.py', 'review.py', 'result.json', '조치검토결과', 'expected', 'oracle', 'rules_wo', '/코드/'])
                for result_table in ['결과/rules.csv', '결과/조건표.csv']:
                    if n.endswith(result_table) and len(z.read(n).decode('utf-8-sig').strip().splitlines()) > 1:
                        bad = True
                if n.endswith('결과/sop.json') and json.loads(z.read(n)).get('SOP'):
                    bad = True
                if n.endswith('.md') and '결과/' in n and any(x in z.read(n).decode('utf-8-sig') for x in ['E21', 'SOP-COOL-11 |']):
                    bad = True
                if bad:
                    names.append(n)
    if names:
        fail(f'학생 ZIP 정답 경계 위반: {names}')
    print('학생 ZIP 정답 경계(참조 구현·완성 결과·채운 기록 없음) 확인')


def diff_rows(base, other):
    a, b = summary(base), summary(other)
    out = []
    for key in a:
        if a[key][:4] != b[key][:4]:
            out.append((key, a[key][:4], b[key][:4]))
    return out


def fmt_set(s):
    return '·'.join(sorted(s)) or '-'


def tables(results, diffs, hand_n, example):
    base = results[('recorded', 'main')]
    lines = ['# 냉각 경보 판정 랩 기대 결과 (강사용)', '', '학생 ZIP에 넣지 않는다. `run_reference.py`가 참조 조건표(`rules.csv`)와 참조 구현(`judge.py`·`review.py`)을 학생 시작본의 실제 원자료에 실행해 만든 결과다. 원문에서 직접 옮긴 두 번째 구현(oracle)과 모든 갈래에서 일치했고, 손계산 표본과도 일치했다.', '',
             '판단 입력의 주 갈래: PLC 상태는 판단 시각 이전 마지막 수신(품질 bad·12초 넘게 끊김이면 값 없음), 팬 연속 시간은 마지막 카운터 기록값(종료면 0, 시작·주기 뒤 12분 넘게 끊기면 값 없음), 예측은 행 없음·거부·120초 지남이면 값 없음, MPa ×10. 조건표 주 갈래: 트립(R4)·인터록 예측(R7) 규칙은 제어 후보 SOP-COOL-11~13에만, HM-8.6 확장(R6)은 SOP-COOL-12·13.', '',
             '표기: 일치 규칙 / 미확인 {규칙}. 금액 단위 만원.', '', '## 사례 E01~E48 (주 갈래)', '',
             '| 사례 | 설비 | 후보 | 판정 | 일치 규칙 | 미확인 | 값 없음 이유 | 비교 합계 | 순위 | 추천 / 없음 사유 |', '|---|---|---|---|---|---|---|---:|---:|---|']
    for e in base['events']:
        ranks = {r['sop']: r['rank'] for r in e['ranking']}
        for i, c in enumerate(e['candidates']):
            hit = {h['rule_id'] for k in ['warnings', 'penalties', 'exclusions'] for h in c[k]}
            unk = {u['rule_id'] for u in c['unknown']}
            why = '; '.join(sorted(set(c['missing_reasons'].values())))
            rec = (', '.join(e['recommendation']['sops']) or e['recommendation']['reason']) if i == 0 else ''
            lines.append(f'| {e["id"]} | {e["asset"]} | {c["sop"]} | {c["status"]} | {fmt_set(hit)} | {fmt_set(unk)} | {why or "-"} | {(c.get("comparison") or {}).get("합계", "-")} | {ranks.get(c["sop"], "-")} | {rec} |')
    lines += ['', '## 판단에 따라 갈리는 사례(강사 참조 두 갈래 실행)', '']
    names = {('elapsed', 'main'): '팬 카운터 기록 뒤 경과 시간을 더함(주 갈래: 기록값 그대로)',
             ('recorded', 'wo'): '트립(R4)·인터록 예측(R7) 규칙을 작업지시 후보 SOP-COOL-14에도 적용(주 갈래: 제어 후보만)',
             ('recorded', 'no_r6'): 'HM-8.6 유온 기준(R6)을 SOP-COOL-12·13에 두지 않음(주 갈래: 둠)'}
    for key, rowsd in diffs.items():
        lines += [f'### {names[key]}', '', '| 사례 / 후보 | 주 갈래 판정·규칙·감점 | 이 갈래 판정·규칙·감점 |', '|---|---|---|']
        for (eid, sop), a, b in rowsd:
            lines.append(f'| {eid} / {sop} | {a[0]} {fmt_set(a[1])} {{{fmt_set(a[2])}}} {a[3]:g} | {b[0]} {fmt_set(b[1])} {{{fmt_set(b[2])}}} {b[3]:g} |')
        rec_a = {e['id']: e['recommendation']['sops'] for e in base['events']}
        rec_b = {e['id']: e['recommendation']['sops'] for e in results[key]['events']}
        changed = [f'{k}: {rec_a[k] or "없음"} → {rec_b[k] or "없음"}' for k in rec_a if rec_a[k] != rec_b[k]]
        lines += ['', '추천이 바뀌는 사례: ' + ('; '.join(changed) if changed else '없음(판정·감점만 바뀜)'), '']
    lines += ['## 판단 근거 요약', '',
              f'- 손계산 표본 {hand_n}건(E21 네 후보의 네 손실, E26 MPa 환산 경계, E03 품질 bad, E39·E22 카운터 갈래, E11·E09 작업지시 적용 갈래)과 지표_정의.md 예({example} SOP-COOL-12)가 엔진과 일치.',
              '- 경계: 예측 유온 54.99·55.00·55.01(R1·R6 이상), 예측 압력 164.99(16.499 MPa)·165.00·165.01(R2 미만), 팬 1440분 = 24 h(R5 초과 아님), 예측 65.00(R7 이상, 갈래에서만 SOP-COOL-14).',
              '- 값 없음의 두 원인: 카운터 종료 뒤 기록 없음 = 정상(0), 주기 기록 12분 넘게 끊김 = 수집 실패(E30). PLC 하트비트 끊김(E23·E40), 품질 bad(E03), 예측 거부(외란 변화 E17·E42, 트립 중 제어 예측), 예측 행 없음(E34·E43·E47), 예측 120초 지남(E19·E45), 오더 조회 실패(E36, 비교 불가).',
              '- 제외+미확인 병기: 트립 사례 E09·E27·E37(R4 제외 + 예측 거부로 R1·R2·R6·R7 미확인), E47(수동 R3 제외 + 예측 행 없음).',
              '- 비교 합계는 교육용이며 HYD 일곱 성분 점수가 아니다. 순위는 실행 승인이 아니다(승인: SOP-COOL-11~13 운전원, SOP-COOL-14 설비보전팀장).', '']
    return '\n'.join(lines)


def conditions_md(results, diffs):
    base = results[('recorded', 'main')]
    lines = ['# 강사용 사례 대조 — 실전 2-5 조치 조건표', '', '학생 ZIP에 포함하지 않는다. 강사 완성 조건표는 `reference/session3/rules.csv`이며 다음 회차 실전 실습2의 `입력/rules.csv`와 같다. 아래는 그 조건표를 학생 폴더 원자료(경보 사례 48건)에 적용한 판정이다. 실행: `reference/session3/run_reference.py`.', '',
             '사례 종류별 대표(학생이 판단기록.md에 고를 만한 사례):', '',
             '| 종류 | 사례 | 확인할 점 |', '|---|---|---|',
             '| 경계·예측 유온 | E13(54.99)·E20(55.00)·E24(55.01) SOP-COOL-11 | R1 「이상」: 55.00 포함 |',
             '| 경계·예측 압력(단위) | E26 16.499 MPa·E46 165.00 bar·E29 16.501 MPa | MPa ×10 뒤 R2 「미만」 |',
             '| 경계·팬 시간 | E39(1440분)·E22(1440분, 기록 3.5분 뒤)·E32(1430분)·E33(1450분) | R5 「초과」, 기록값/경과 더함 결정 |',
             '| 복수 사유 | E35 SOP-COOL-11(R1 경고 + R3 제외), E33(R1 + R5 감점) | 사유를 모두 남김, 감점 한 번 |',
             '| 값 없음 + 확인된 제외 | E09·E27·E37(트립) E47(수동 + 예측 행 없음) | 제외 유지 + 미확인 병기 |',
             '| 값 없음(두 원인) | E30(카운터 끊김) vs 카운터 종료 뒤 무기록(대부분), E23·E40(PLC 끊김), E03(품질 bad) | 보류, 0으로 채우지 않음 |',
             '| 적용 대상 밖 | E03·E23 SOP-COOL-14(모드 몰라도 R3 대상 아님) | 유지 |',
             '| 결정에 따라 갈림 | 트립 E09·E27·E37, 예측 65 이상 E11·E14·E38·E41 SOP-COOL-14 | R4·R7 작업지시 적용 여부 |', '',
             '| 사례 | 후보 | 판정 | 일치 규칙 | 미확인 | 감점 |', '|---|---|---|---|---|---:|']
    for e in base['events']:
        for c in e['candidates']:
            hit = {h['rule_id'] for k in ['warnings', 'penalties', 'exclusions'] for h in c[k]}
            lines.append(f'| {e["id"]} | {c["sop"]} | {c["status"]} | {fmt_set(hit)} | {fmt_set({u["rule_id"] for u in c["unknown"]})} | {sum(p["amount_만원"] for p in c["penalties"]):g} |')
    lines += ['', '후보 유지와 실행 승인은 다르다. HM-8.5의 24시간 이내 수행 제한과 승인·재관측을 따로 확인한다. 현장 세척은 HM-8.7의 별도 절차다.', '']
    return '\n'.join(lines)


def main():
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        for lab in LABS:
            shutil.copytree(lab, tmp/lab.name)
        rules = variant_rules(tmp)
        shutil.copy2(HERE/'rules.csv', tmp/CONDITIONS.name/'결과/조건표.csv')
        shutil.copy2(HERE/'sop.json', tmp/CRITERIA.name/'결과/sop.json')
        shutil.copy2(HERE/'rules.csv', tmp/CRITERIA.name/'결과/rules.csv')
        (tmp/CRITERIA.name/'결과/사례대조.md').write_text((tmp/CRITERIA.name/'결과/사례대조.md').read_text(encoding='utf-8').replace('| | | | | | | | | | | |', '| E21 | 정상 | SOP-COOL-11 | 예측 52.60 ℃ 182 bar (예측_결과.csv) | - | - | 0 | - | - | 유지 | HM-8.5 |' + chr(10) + '| E03 | 값 없음 | SOP-COOL-11 | PLC 품질 bad | - | - | 0 | - | R3·R4 | | |'), encoding='utf-8')
        results = {}
        for counter in ['recorded', 'elapsed']:
            results[(counter, 'main')] = judge.run(tmp/JUDGE.name, rules['main'], counter)
        results[('recorded', 'wo')] = judge.run(tmp/JUDGE.name, rules['wo'], 'recorded')
        results[('recorded', 'no_r6')] = judge.run(tmp/JUDGE.name, rules['no_r6'], 'recorded')
        base = results[('recorded', 'main')]
        (tmp/JUDGE.name/'결과/result.json').write_text(json.dumps(judge.strip(base), ensure_ascii=False, indent=2), encoding='utf-8')
        (tmp/JUDGE.name/'결과/기대결과.md').write_text((tmp/JUDGE.name/'결과/기대결과.md').read_text(encoding='utf-8').replace('| | | | | | | |', '| E21 / SOP-COOL-11 | 정상 | 52.60 ℃ | 유지 | - | 유지 | 일치 |'), encoding='utf-8')
        rv = review.build(tmp/REVIEW.name)
        (tmp/REVIEW.name/'결과/조치검토결과.json').write_text(json.dumps(rv, ensure_ascii=False, indent=2), encoding='utf-8')
        (tmp/REVIEW.name/'결과/조치검토결과.md').write_text(review.markdown(rv), encoding='utf-8')
        if judge.run(tmp/REVIEW.name) != base:
            fail('실전반 시작본 입력으로 돌린 판정이 통합반 실습3과 다름')
        if (CONDITIONS/'자료/경보_목록.csv').read_bytes() != (JUDGE/'자료/경보_목록.csv').read_bytes():
            fail('실전 2-5와 3회차 판정 랩의 원자료가 다름')
        checked = cross_check(tmp/JUDGE.name, results)
        hand_n, example = hand_check(results, (JUDGE/'자료/metrics/지표_정의.md').read_text(encoding='utf-8'))
        diffs = {k: diff_rows(base, results[k]) for k in [('elapsed', 'main'), ('recorded', 'wo'), ('recorded', 'no_r6')]}
        for k, v in diffs.items():
            if not v:
                fail(f'갈래 {k}에서 바뀌는 사례가 없음(판단 지점이 결과를 바꾸지 않음)')
        records = checker_trials(tmp)
        (HERE/'참조_조치검토결과.md').write_text(review.markdown(rv), encoding='utf-8')
    boundary_check()
    (HERE/'expected_results.json').write_text(json.dumps({'판본': '2026-10-28-s3-v2-field', 'integrated_judge_result': judge.strip(base), 'practical_review': rv,
                                                          'branches': {f'{c}/{r}': [{'사례': k[0], '후보': k[1], '주': [a[0], sorted(a[1]), sorted(a[2]), a[3]], '갈래': [b[0], sorted(b[1]), sorted(b[2]), b[3]]} for k, a, b in v] for (c, r), v in diffs.items()}},
                                                         ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (HERE/'기대결과.md').write_text(tables(results, diffs, hand_n, example), encoding='utf-8')
    (HERE.parent/'실전반/조건표_사례검토.md').write_text(conditions_md(results, diffs), encoding='utf-8')
    (HERE/'검사기_확인.json').write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    passed = sum(r['ok'] for r in records)
    print(f'검사기 시험 {passed}/{len(records)} 기대대로, oracle 대조 {checked}건, 갈래별 바뀌는 후보 ' + ', '.join(f'{c}/{r} {len(v)}' for (c, r), v in diffs.items()))
    if failures:
        print(f'불일치 {len(failures)}건'); sys.exit(1)
    print('참조 실행·대조 모두 일치')


if __name__ == '__main__':
    main()
