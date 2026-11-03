"""강사 참조 실행 · 대조 — 냉각 경보 조치 판단 묶음 네 랩(통합 03회차 실습2 · 3, 실전 02회차 실습5 · 03회차 실습2). 학생 ZIP에 넣지 않는다.

사용: HYD_MAIN_ROOT=<main 체크아웃> python run_reference.py     (학생 폴더는 임시 사본에서만 실행하고 원본 결과/를 건드리지 않는다)
1. 원자료 코어를 다시 만들어(data_conditions.build) 네 랩의 자료/ · 입력/이 그 판 · 강사 검증 판과 같은 바이트인지 본다.
2. 조건 랩 갈래 — 통합 03-2: 지점1(가 · 나) × 지점2(가 · 나 · 다) = 6, 실전 02-5: 지점2 = 3 — 를 갈래/에 쓰고, 그 결과로 학생 검사기를 실제 실행한다.
   사건 네 후보(사건 메모의 값)와 확인 사례(확인_사례.csv)를 갈래마다 조건표로 판정한다.
3. 판정 갈래 — 입력 = 지점1 가 · 지점2 가, 지점3(끊긴 기록: 가 · 나) × 지점4(경고 후보: 가 · 나) = 4 — 를 판정 랩 사본에서 judge_actions.py로 실행하고 학생 검사기를 돌린다.
   조건 랩의 모든 조건표 갈래를 판정 랩 입력으로 넣어도 판정 랩 계약 · 검사기가 맞물리는지 본다(랩 사슬).
4. 두 번째 구현(oracle): 생성기 안쪽 값(원자료_메타.json — 궤적에서 바로 낸 판단 입력 · 오더 값)과 원문에서 따로 옮긴 규칙 뜻(조건표 파일 · judge_actions.py를 쓰지 않음)으로
   모든 갈래 · 사례 · 후보를 다시 판정 · 비교 · 권고해 엔진과 견준다.
5. 손계산: 사건 네 후보의 손실을 사건 메모 값으로 식 그대로 다시 계산해 엔진 · 생성기 값과 견주고, 지표_정의.md 손계산 예를 엔진 값과 견준다.
   구성안 4절의 설계 목표와 실행 값을 나란히 남긴다.
6. 검사기 고의 손상: 네 랩의 check.py에 일부러 망가뜨린 결과(내 입력 폴더 `결과/내_입력/`을 쓴 경우 포함)를 넣어 잡는지 본다 → 검사기_확인.json.
7. 학생 폴더에 강사 참조 파일 · 그 랩의 결정 답 문장 · 사건 비교 합계가 없는지 본다.
8. 학생용 완성본 넷(기본 갈래 — 조건 랩 지점1 가 · 지점2 가, 판정 랩 지점3 가 · 지점4 가)을 실습 폴더와 따로 받는 ZIP으로 묶고(산출물/<과정>/실습/NN회차/완성본/),
   새 폴더에 풀어 안내의 명령을 실행해 동봉한 결과와 같은지, 학생 검사기가 통과하는지 본다.
산출: 갈래/, expected_results.json, 사건_갈래표.md, 검사기_확인.json, 완성본 ZIP 넷. 어긋나면 「불일치」 줄(파일 · 사례 · 후보)을 찍고 종료 코드 1 — 결과를 맞추지 말고 원인을 고친다(코딩랩.md K요-11).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import copy
import csv
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parents[1]
sys.path[:0] = [str(HERE), str(TOOLS)]
import criteria as CR  # noqa: E402
import judge_actions as J  # noqa: E402
import build_judgement_labs as BJ  # noqa: E402
import data_conditions as DC  # noqa: E402

LAB = BJ.LABS
BRANCHES = HERE/'갈래'
POLICIES = [('가', '가'), ('가', '나'), ('나', '가'), ('나', '나')]   # (지점3 끊긴 기록, 지점4 경고 후보)
GAP = {'가': 'carry', '나': 'unknown'}       # 지점3 갈래 → judge_actions.py --gap
WARN = {'가': 'compare', '나': 'skip'}       # 지점4 갈래 → judge_actions.py --warned
BASE_POLICY = ('가', '가')                  # 학생용 완성본 · 갈래 파일 전부를 남기는 판정 갈래


def jp(pol):
    """갈래 이름(지점3, 지점4) → judge_actions.py의 정한 것 값."""
    return GAP[pol[0]], WARN[pol[1]]


assert jp(BASE_POLICY) == J.BASE_POLICY, '완성본 갈래와 judge_actions.py 기본값이 다름'
KST = timezone(timedelta(hours=9))
DESIGN = {   # 구성안 4절 손계산(설계 목표 — 생성기를 다시 짜면 실행 값으로 바뀐다)
    'SOP-COOL-11': dict(예측=56.90, 합계=184.66), 'SOP-COOL-12': dict(예측=None, 아는_값_합계=145.77, 다시_계산한_예측=52.23),
    'SOP-COOL-13': dict(예측=48.11, 합계=635.08), 'SOP-COOL-14': dict(예측=56.90, 합계=340.00)}
failures = []


def fail(msg):
    failures.append(msg)
    print('불일치:', msg)


def rows(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def copy_lab(key, tmp):
    dst = Path(tmp)/LAB[key].name
    shutil.copytree(LAB[key], dst)
    return dst


def run_py(folder, *args):
    p = subprocess.run([sys.executable, '-B', *args], cwd=folder, capture_output=True, text=True, encoding='utf-8',
                       env={'PYTHONUTF8': '1', 'PATH': '/usr/bin:/bin', 'SYSTEMROOT': 'C:\\Windows'})
    return p.returncode, (p.stdout + p.stderr).strip()


def run_check(folder):
    return run_py(folder, 'check.py')


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8', newline='\n')


# ───────────── 1. 자료 · 입력 바이트 ─────────────
def same_bytes(files):
    for key, folder in LAB.items():
        for name, core in BJ.DATA[key]:
            p = folder/'자료'/name
            if not p.is_file() or p.read_text(encoding='utf-8') != files[core]:
                fail(f'{folder.name}/자료/{name}이 원자료 코어({core})와 다름 — build_judgement_labs.py --lab {key}로 다시 만든다')
    for key, table, sop in [('integrated-03-judge', '가', CR.sop_json(*CR.BASE)), ('practical-03-review', '가', CR.sop_json(*CR.BASE))]:
        if (LAB[key]/'입력/조건표.csv').read_text(encoding='utf-8') != CR.table_csv(table):
            fail(f'{LAB[key].name}/입력/조건표.csv가 강사 검증 판(지점2 {table})과 다름')
        if (LAB[key]/'입력/sop.json').read_text(encoding='utf-8') != sop:
            fail(f'{LAB[key].name}/입력/sop.json이 강사 검증 판(지점1 가 · 지점2 가)과 다름')


# ───────────── 2. 조건 랩 갈래 ─────────────
def memo_inputs(memo):
    """사건 메모에서 사건 네 후보의 판단 입력(손으로 대어 보는 값 그대로)."""
    def grab(pat):
        m = re.search(pat, memo, re.M)
        if not m:
            raise RuntimeError(f'사건 메모에서 찾지 못함: {pat}')
        return m.groups()
    req = grab(r'^- (\d\d:\d\d:\d\d) 조치 판단 요청')[0]
    mode, state = grab(r'^- 운전 모드 (\S+), 상태 (\S+)')
    t_cnt, kind, minutes = grab(r'^- 마지막 기록: (\S+ \S+) 「(\S+)」 (\d+)분')
    day = t_cnt.split()[0]
    J_ = datetime.fromisoformat(f'{day}T{req}+09:00')
    age = (J_ - datetime.fromisoformat(t_cnt.replace(' ', 'T') + '+09:00')).total_seconds() / 60
    fan = 0.0 if kind == '종료' else round((float(minutes) + age) / 60, 2)     # 손으로 구한 판정 요청 때 연속 시간(h, 확인_사례.csv와 같은 자리수)
    out = {}
    targets = J.load_targets(LAB['practical-03-review']/'자료/targets.csv')
    for sop, tg in targets.items():
        m = re.search(rf'^\| {sop} \| ([0-9.]+) ℃ \| ([0-9.]+) bar', memo, re.M)
        out[sop] = {'forecast_ts1': float(m.group(1)) if m else None, 'forecast_ps1': float(m.group(2)) if m else None, 'fan100_hours': fan,
                    'plc_mode': mode, 'plc_state': state, 'skill_kind': tg['skill_kind'], 'skill_code': tg['skill_code']}
    return out


def check_case_inputs(path, targets):
    """확인_사례.csv(긴 꼴)에서 사례마다 후보 넷의 판단 입력 — 값은 판정 요청 때의 입력 그대로(입출력_계약 「확인 사례」, 팬 연속 시간은 h)."""
    cases = {}
    for r in rows(path):
        c = cases.setdefault(r['사례'], {'asset': r['설비'], 'common': {}, 'fc': {}})
        if r['입력'] == '운전_모드':
            c['common']['plc_mode'] = r['값'] or None
        elif r['입력'] == '상태':
            c['common']['plc_state'] = r['값'] or None
        elif r['입력'] == '팬100_연속':
            if r['단위'] != 'h':
                fail(f'확인_사례.csv {r["사례"]}: 팬100_연속의 단위가 h가 아님({r["단위"]})')
            c['common']['fan100_hours'] = float(r['값']) if r['값'] else None
        else:
            key = {'예측_TS1': 'forecast_ts1', '예측_PS1': 'forecast_ps1'}[r['입력']]
            c['fc'].setdefault(r['후보'], {})[key] = float(r['값']) if r['값'] else None
    out = {}
    for cid, c in cases.items():
        out[cid] = {sop: {**c['common'], **c['fc'].get(sop, {}), 'skill_kind': tg['skill_kind'], 'skill_code': tg['skill_code']} for sop, tg in targets.items()}
    return out


def judged_summary(sop, j):
    return {'판정': j['status'], '경고': [h['rule_id'] for h in j['warnings']], '감점': [h['rule_id'] for h in j['penalties']],
            '제외': [h['rule_id'] for h in j['exclusions']], '미확인': [u['rule_id'] for u in j['unknown']]}


def condition_branches(files, tmp, expected):
    memo = memo_inputs(files['사건_기록_HYD-02_1027.md'])
    t02 = J.load_targets(LAB['practical-02-conditions']/'자료/targets.csv')
    checks = check_case_inputs(LAB['practical-02-conditions']/'자료/확인_사례.csv', t02)
    inc = DC_META['incident']
    for sop in memo:   # 사건 메모와 확인 사례의 사건 값이 같은가(같은 사실 두 자리)
        a, b = memo[sop], checks[inc][sop]
        for k in J.INPUTS:
            if (a[k] is None) != (b[k] is None) or (a[k] is not None and k in J.NUMERIC and abs(a[k] - b[k]) > 1e-9) or (a[k] is not None and k not in J.NUMERIC and a[k] != b[k]):
                fail(f'사건 메모와 확인_사례.csv의 사건 {sop} {k}이 다름: {a[k]} / {b[k]}')
    exp_crit, exp_cond = {}, {}
    for p2 in CR.P2:
        table_text = CR.table_csv(p2)
        path = Path(tmp)/f'table_{p2}.csv'
        path.write_text(table_text, encoding='utf-8')
        groups = J.load_table(path)
        incident = {sop: judged_summary(sop, J.evaluate(sop, memo[sop], groups)) for sop in memo}
        for p1 in CR.P1:
            d = BRANCHES/f'조치기준_{p1}-{p2}'
            write(d/'sop.json', CR.sop_json(p1, p2))
            write(d/'조건표.csv', table_text)
            write(d/'요구사항_참조.md', criteria_record(p1, p2, incident))
            lab = copy_lab('integrated-03-criteria', tmp/f'crit_{p1}{p2}')
            shutil.copy(d/'sop.json', lab/'결과/sop.json')
            shutil.copy(d/'조건표.csv', lab/'결과/조건표.csv')
            code, out = run_check(lab)
            if code != 0 or '구조 검사 통과' not in out:
                fail(f'통합 03-2 갈래 {p1}-{p2}: 학생 검사기가 강사 참조를 통과시키지 않음\n{out}')
            exp_crit[f'{p1}-{p2}'] = {'사건': incident, '설비': CR.asset_scope(p1), '결정표_대조': CR.export_treatment(p2), '검사기': f'exit {code}'}
        d = BRANCHES/f'조건표_{p2}'
        write(d/'조건표.csv', table_text)
        cases = {cid: {sop: judged_summary(sop, J.evaluate(sop, x, groups)) for sop, x in cs.items()} for cid, cs in checks.items()}
        write(d/'판단기록_참조.md', conditions_record(p2, cases))
        lab = copy_lab('practical-02-conditions', tmp/f'cond_{p2}')
        shutil.copy(d/'조건표.csv', lab/'결과/조건표.csv')
        code, out = run_check(lab)
        if code != 0 or '구조 검사 통과' not in out:
            fail(f'실전 02-5 갈래 {p2}: 학생 검사기가 강사 참조를 통과시키지 않음\n{out}')
        if (BRANCHES/f'조치기준_가-{p2}'/'조건표.csv').read_bytes() != (d/'조건표.csv').read_bytes():
            fail(f'지점2 {p2}: 통합 03-2와 실전 02-5의 조건표 바이트가 다름(같은 13열 · 같은 규칙이어야 한다)')
        exp_cond[p2] = {'확인_사례': cases, '검사기': f'exit {code}'}
    # 판정 랩 입력 = 강사 검증 판(K-48)
    if (BRANCHES/'조치기준_가-가'/'조건표.csv').read_bytes() != (LAB['integrated-03-judge']/'입력/조건표.csv').read_bytes():
        fail('통합 03-3 입력/조건표.csv가 갈래 가-가와 다름')
    if (BRANCHES/'조치기준_가-가'/'sop.json').read_bytes() != (LAB['integrated-03-judge']/'입력/sop.json').read_bytes():
        fail('통합 03-3 입력/sop.json이 갈래 가-가와 다름')
    if (BRANCHES/'조건표_가'/'조건표.csv').read_bytes() != (LAB['practical-03-review']/'입력/조건표.csv').read_bytes():
        fail('실전 03-2 입력/조건표.csv가 실전 02-5 갈래 가와 다름')
    expected['조치기준_통합03-2'] = exp_crit
    expected['조건표_실전02-5'] = exp_cond
    return checks


def criteria_record(p1, p2, incident):
    lines = [f'# 조치 기준 강사 참조 — 지점1 {p1} · 지점2 {p2}', '', '## 정한 것', '',
             CR.md_table(['지점', '고른 것', '근거', '바뀌는 답'], [
                 ['적용 범위', {'가': 'HYD-01~03에만 건다', '나': 'HYD-04에도 SOP-COOL-13 · 15와 냉각 성능 판정을 건다'}[p1],
                  '설비_대장.csv HYD-04 비고 「HPP-45A 후속형. 수냉식 열교환기」; graph.json HYD-04 구성 요소 · 센서; 작업지시_이력.csv HYD-04 냉각수측 스케일; HM-8에 적용 범위 문장 없음',
                  'sop.json 모델_참조의 HYD-04 ID · 미기재'],
                 ['출처가 확인되지 않는 기준', {'가': '옛 시스템 그대로 네 후보에 제외', '나': '설명 문장대로 제어 후보 11~13에만', '다': '옮기지 않음'}[p2],
                  '판단시스템_결정표_내보내기.txt 15 · 32행(출처 ks:sr-04 · HM-9.4) — HM-8 1.1 · 1.0에 같은 문장 없음; HM-8.3 인터록 65 ℃ 이상',
                  '트립 · 예측 65 이상 사례의 판정(사건은 바뀌지 않음)']]),
             '', '## 설비마다 걸었음 · 뺐음', '', CR.md_table(['설비', '걸었음 · 뺐음', '까닭(모델 · 대장 줄)'], CR.asset_scope(p1)),
             '', '## 판단 시스템 결정표 대조', '', CR.md_table(['내보내기 행', '처리', '까닭', '근거'], CR.export_treatment(p2)),
             '', '## 사건 대입(사건 메모의 값)', '',
             CR.md_table(['후보', '판정', '경고', '감점', '제외', '확인할 수 없는 규칙'],
                         [[s, v['판정'], ' · '.join(v['경고']) or '—', ' · '.join(v['감점']) or '—', ' · '.join(v['제외']) or '—', ' · '.join(v['미확인']) or '—'] for s, v in incident.items()])]
    return '\n'.join(lines) + '\n'


def conditions_record(p2, cases):
    body = []
    for cid, cs in cases.items():
        for sop, v in cs.items():
            body.append([cid, sop, v['판정'], ' · '.join(v['경고']) or '—', ' · '.join(v['감점']) or '—', ' · '.join(v['제외']) or '—', ' · '.join(v['미확인']) or '—',
                         {'SOP-COOL-14': '설비보전팀장(HM-8.7)'}.get(sop, '운전원(HM-8.5)') if v['판정'] != '제외' else '—'])
    return (f'# 조치 조건표 강사 참조 — 지점2 {p2}\n\n## 확인 사례 대조\n\n'
            + CR.md_table(['사례', '후보', '판정', '경고', '감점', '제외', '미확인', '남으면 승인 역할'], body) + '\n')


# ───────────── 3. 판정 갈래와 랩 사슬 ─────────────
def judge_branches(tmp, expected):
    out = {}
    sop_doc = json.loads(CR.sop_json(*CR.BASE))
    for pol in POLICIES:
        name = ''.join(pol)
        lab = copy_lab('integrated-03-judge', tmp/f'judge_{name}')
        res = J.run(lab, policy=jp(pol))
        dump(lab/'결과/result.json', J.student_view(res))
        code, text = run_check(lab)
        if code != 0 or '구조 검사 통과' not in text:
            fail(f'통합 03-3 갈래 {name}: 학생 검사기가 강사 참조를 통과시키지 않음\n{text[:3000]}')
        lab2 = copy_lab('practical-03-review', tmp/f'review_{name}')
        groups = J.load_table(lab2/'입력/조건표.csv')
        rv = J.review(res, sop_doc, groups)
        dump(lab2/'결과/조치검토결과.json', rv)
        write(lab2/'결과/조치검토결과.md', J.review_md(rv))
        code2, text2 = run_check(lab2)
        if code2 != 0 or '구조 검사 통과' not in text2:
            fail(f'실전 03-2 갈래 {name}: 학생 검사기가 강사 참조를 통과시키지 않음\n{text2[:3000]}')
        out[pol] = (res, rv)
        if pol == BASE_POLICY:
            d = BRANCHES/f'판정_{pol[0]}-{pol[1]}'
            dump(d/'result.json', J.student_view(res))
            dump(d/'조치검토결과.json', rv)
            write(d/'조치검토결과.md', J.review_md(rv))
        expected.setdefault('판정', {})[f'{pol[0]}-{pol[1]}'] = {
            '검사기': {'통합 03-3': f'exit {code}', '실전 03-2': f'exit {code2}'},
            '사례': {e['id']: {'후보': {c['sop']: dict(judged_summary(c['sop'], c), 합계=(c['comparison'] or {}).get('total'),
                                                       견주지_않음=c.get('no_comparison_reason')) for c in e['candidates']},
                              '순위': [[r['rank'], r['sop'], r['total']] for r in e['ranking']], '1위': [r['sop'] for r in e['ranking'] if r['rank'] == 1]}
                     for e in res['events']}}
    return out


def chain(tmp, expected):
    """조건 랩의 강사 참조 결과(모든 조건표 갈래)를 판정 랩 입력으로 넣어 판정 랩 계약 · 검사기가 맞물리는지 본다."""
    rec = {}
    for p1 in CR.P1:
        for p2 in CR.P2:
            d = BRANCHES/f'조치기준_{p1}-{p2}'
            lab = copy_lab('integrated-03-judge', tmp/f'chain_i_{p1}{p2}')
            shutil.copy(d/'조건표.csv', lab/'입력/조건표.csv')
            shutil.copy(d/'sop.json', lab/'입력/sop.json')
            res = J.run(lab, policy=jp(BASE_POLICY))
            dump(lab/'결과/result.json', J.student_view(res))
            code, text = run_check(lab)
            if code != 0:
                fail(f'사슬 통합 03-2 갈래 {p1}-{p2} → 03-3: 검사기 실패\n{text[:2000]}')
            rec[f'통합 {p1}-{p2} → 03-3'] = summary_counts(res, code)
    for p2 in CR.P2:
        lab = copy_lab('practical-03-review', tmp/f'chain_p_{p2}')
        shutil.copy(BRANCHES/f'조건표_{p2}'/'조건표.csv', lab/'입력/조건표.csv')
        res = J.run(lab, policy=jp(BASE_POLICY))
        rv = J.review(res, json.loads((lab/'입력/sop.json').read_text(encoding='utf-8')), J.load_table(lab/'입력/조건표.csv'))
        dump(lab/'결과/조치검토결과.json', rv)
        write(lab/'결과/조치검토결과.md', J.review_md(rv))
        code, text = run_check(lab)
        if code != 0:
            fail(f'사슬 실전 02-5 갈래 {p2} → 03-2: 검사기 실패\n{text[:2000]}')
        rec[f'실전 {p2} → 03-2'] = summary_counts(res, code)
    expected['랩_사슬'] = rec
    return rec


def summary_counts(res, code):
    from collections import Counter
    st = Counter(c['status'] for e in res['events'] for c in e['candidates'])
    allx = [e['id'] for e in res['events'] if all(c['status'] == '제외' for c in e['candidates'])]
    trip = next(e for e in res['events'] if e['id'] == TRIP_CASE)
    hot = next(e for e in res['events'] if e['id'] == HOT_CASE)
    return {'검사기': f'exit {code}', '판정_수': dict(st), '모두_제외': allx,
            '트립_사례': {c['sop']: c['status'] for c in trip['candidates']}, '예측65_사례': {c['sop']: c['status'] for c in hot['candidates']}}


# ───────────── 4. 두 번째 구현(oracle) ─────────────
def oracle_case(case, p2, pol):
    """생성기 안쪽 값 + 원문에서 옮긴 규칙 뜻. 조건표 파일 · judge_actions.py를 쓰지 않는다.
    pol = (지점3 끊긴 기록, 지점4 경고 후보) — 가 · 나의 뜻은 judge_actions.py 머리(GAP · WARN 짝)와 같은 말을 이 함수가 따로 구현한다."""
    p3, p4 = pol
    x = case['inputs']
    J_ = datetime.fromisoformat(case['judge'])
    cnt = x['counter']
    if cnt is None:
        fan = None
    elif cnt[3] == '종료':
        fan = 0.0
    elif (J_ - datetime.fromisoformat(cnt[1])).total_seconds() > 600:          # 주기를 넘게 기록이 없음
        fan = None if (p3 == '나' or x['mode'] is None) else x['fan_elapsed_min'] / 60
    else:
        fan = x['fan_elapsed_min'] / 60
    remote = ['SOP-COOL-11', 'SOP-COOL-12', 'SOP-COOL-13']
    hard = {'가': remote + ['SOP-COOL-14'], '나': remote, '다': []}[p2]
    def known(v, f):
        return None if v is None else f(v)
    out = {}
    for sop in ['SOP-COOL-11', 'SOP-COOL-12', 'SOP-COOL-13', 'SOP-COOL-14']:
        ts1 = x['ts1'][sop]
        tests = []
        if sop in remote:
            tests += [('auto', 'EXCLUDE', known(x['mode'], lambda m: m != 'REMOTE_AUTO')), ('warn55', 'WARN', known(ts1, lambda t: t >= 55.0))]
        if sop in ('SOP-COOL-11', 'SOP-COOL-12'):
            tests.append(('fan24', 'PENALTY', known(fan, lambda h: h > 24.0)))
        if sop in hard:
            tests += [('hard65', 'EXCLUDE', known(ts1, lambda t: t >= 65.0)), ('trip', 'EXCLUDE', known(x['state'], lambda s: s == 'TRIP'))]
        hits = {k: sorted(n for n, r, v in tests if v is True and r == k) for k in ('WARN', 'PENALTY', 'EXCLUDE')}
        unknown = sorted(n for n, r, v in tests if v is None)
        status = '제외' if hits['EXCLUDE'] else ('보류' if unknown else '유지')
        o = case['order']
        if o is None:
            L = {'비용': None, '생산': None, '품질': None, '에너지': None}
        else:
            L = DC.losses(sop, o['due_h'], float(o['remain']), float(o['hot']), ts1)
        pen = 20.0 * len(hits['PENALTY'])
        complete = all(L[k] is not None for k in ('비용', '생산', '품질', '에너지'))
        compared = status == '유지' and complete and not (p4 == '나' and hits['WARN'])
        total = round(sum(L[k] for k in ('비용', '생산', '품질', '에너지')) + pen + 0.0, 2) if compared else None
        out[sop] = dict(status=status, hits=hits, unknown=unknown, fan=fan, ts1=ts1, ps1=x['ps1'][sop], total=total)
    ranked = sorted([(v['total'], s) for s, v in out.items() if v['total'] is not None])
    ranks, prev, pos = {}, None, 0
    for i, (t, s) in enumerate(ranked, 1):
        if t != prev:
            pos, prev = i, t
        ranks[s] = pos
    top = sorted(s for s, r in ranks.items() if r == 1)
    return out, ranks, top


SEM = {v: k for k, v in CR.SEMANTIC.items()}


def oracle_compare(meta, engine_results):
    cases = {c['id']: c for c in meta['cases']}
    n = 0
    for p2 in CR.P2:
        for pol in POLICIES:
            res = engine_results[(p2, pol)]
            for e in res['events']:
                case = cases.get(e['id'])
                if case is None:
                    fail(f'oracle: 메타에 없는 사례 {e["id"]}')
                    continue
                out, ranks, top = oracle_case(case, p2, pol)
                at = f'지점2 {p2} 정책 {"".join(pol)} {e["id"]}'
                for c in e['candidates']:
                    o = out[c['sop']]
                    n += 1
                    got = {'status': c['status'], 'WARN': sorted(CR.SEMANTIC[h['rule_id']] for h in c['warnings']),
                           'PENALTY': sorted(CR.SEMANTIC[h['rule_id']] for h in c['penalties']), 'EXCLUDE': sorted(CR.SEMANTIC[h['rule_id']] for h in c['exclusions']),
                           'unknown': sorted(CR.SEMANTIC[u['rule_id']] for u in c['unknown'])}
                    want = {'status': o['status'], **o['hits'], 'unknown': o['unknown']}
                    if got != want:
                        fail(f'oracle {at} {c["sop"]}: 엔진 {got} / 두 번째 구현 {want}')
                    for k, ov in (('fan100_hours', o['fan']), ('forecast_ts1', o['ts1']), ('forecast_ps1', o['ps1'])):
                        ev = c['inputs'][k]
                        if (ev is None) != (ov is None) or (ev is not None and abs(ev - ov) > 0.06):
                            fail(f'oracle {at} {c["sop"]} 입력 {k}: 엔진 {ev} / 두 번째 구현 {ov}')
                    et = (c['comparison'] or {}).get('total')
                    if (et is None) != (o['total'] is None) or (et is not None and abs(et - o['total']) > 0.005):
                        fail(f'oracle {at} {c["sop"]} 합계: 엔진 {et} / 두 번째 구현 {o["total"]}')
                if {r['sop']: r['rank'] for r in e['ranking']} != ranks:
                    fail(f'oracle {at} 순위: 엔진 {e["ranking"]} / 두 번째 구현 {ranks}')
                if sorted(r['sop'] for r in e['ranking'] if r['rank'] == 1) != top:
                    fail(f'oracle {at} 1위: 엔진 {e["ranking"][:1]} / 두 번째 구현 {top}')
    return n


def oracle_check_cases(meta, checks):
    """실전 02-5 확인 사례: 확인_사례.csv를 엔진 판정한 값과, 메타 값 + 규칙 뜻으로 다시 낸 값."""
    cases = {c['id']: c for c in meta['cases']}
    n = 0
    for p2 in CR.P2:
        path = BRANCHES/f'조건표_{p2}'/'조건표.csv'
        groups = J.load_table(path)
        for cid, cs in checks.items():
            out, _, _ = oracle_case(cases[cid], p2, BASE_POLICY)
            for sop, x in cs.items():
                j = J.evaluate(sop, x, groups)
                got = (j['status'], sorted(CR.SEMANTIC[u['rule_id']] for u in j['unknown']), sorted(CR.SEMANTIC[h['rule_id']] for h in j['exclusions']))
                want = (out[sop]['status'], out[sop]['unknown'], out[sop]['hits']['EXCLUDE'])
                n += 1
                if got != want:
                    fail(f'oracle 확인 사례 지점2 {p2} {cid} {sop}: 엔진 {got} / 두 번째 구현 {want}')
    return n


# ───────────── 5. 손계산 ─────────────
def hand_check(memo_text, base_res, meta, expected):
    """사건 메모의 값으로 지표_정의.md 식을 한 줄씩 다시 계산(엔진 · 생성기 함수를 쓰지 않음)."""
    due = float(re.search(r'납기까지 ([0-9.]+)시간', memo_text).group(1))
    remain = float(re.search(r'잔량 ([0-9,]+) ea', memo_text).group(1).replace(',', ''))
    lot = float(re.search(r'고온 로트[^:]*: ([0-9,]+) ea', memo_text).group(1).replace(',', ''))
    ts = {s: (float(m.group(1)) if (m := re.search(rf'^\| {s} \| ([0-9.]+) ℃', memo_text, re.M)) else None) for s in DESIGN}
    risk = 900 * min(1, due / 1400)
    fan_energy = (100 - 60) * 6 / 40 * due * 0.015
    hand = {
        'SOP-COOL-11': dict(비용=risk, 생산=50 * (due * (1 - 90 / 90) + 0) + 120 * max(0, 0 + remain / (300 * 1.0) - due), 품질=150.0 if ts['SOP-COOL-11'] >= 55 and lot > 0 else 0.0, 에너지=fan_energy, 감점=20.0),
        'SOP-COOL-12': dict(비용=risk, 생산=50 * (due * (1 - 80 / 90) + 0) + 120 * max(0, 0 + remain / (300 * 80 / 90) - due), 품질=None, 에너지=fan_energy, 감점=20.0),
        'SOP-COOL-13': dict(비용=40 + 0, 생산=50 * (due * (1 - 70 / 90) + 3) + 120 * max(0, 3 + remain / (300 * 70 / 90) - due), 품질=150.0 if ts['SOP-COOL-13'] >= 55 and lot > 0 else 0.0, 에너지=0.0, 감점=0.0),
        'SOP-COOL-14': dict(비용=40 + 0, 생산=50 * (due * 0 + 3) + 120 * max(0, 3 + remain / 300 - due), 품질=150.0 if ts['SOP-COOL-14'] >= 55 and lot > 0 else 0.0, 에너지=0.0, 감점=0.0),
    }
    inc = next(e for e in base_res['events'] if e['id'] == meta['incident'])
    rows_ = []
    for c in inc['candidates']:
        h = hand[c['sop']]
        known = round(sum(v for v in h.values() if v is not None), 2)
        eng = (c['comparison'] or {}).get('total')
        known_eng = round(sum(v for v in c['_raw'].values() if v is not None) + sum(x['penalty_manwon'] for x in c['penalties']) + 0.0, 2)   # 보류 후보의 아는 값 합계
        eng_val = eng if eng is not None else known_eng
        gen = meta['incident_totals'][c['sop']]['합계'] if meta['incident_totals'][c['sop']]['합계'] is not None else meta['incident_totals'][c['sop']]['아는_값_합계']
        if eng_val is None or abs(eng_val - known) > 0.005 or abs(gen - known) > 0.005:
            fail(f'손계산 사건 {c["sop"]}: 손계산 {known} / 엔진 {eng_val} / 생성기 {gen}')
        d = DESIGN[c['sop']]
        rows_.append([c['sop'], d.get('예측') if d.get('예측') is not None else '행 없음', ts[c['sop']] if ts[c['sop']] is not None else '행 없음',
                      d.get('합계', d.get('아는_값_합계')), known, eng_val, gen, ' · '.join(f'{k} {v:.2f}' for k, v in h.items() if v is not None)])
    # 지표_정의.md 손계산 예
    doc = (LAB['integrated-03-judge']/'자료/metrics/지표_정의.md').read_text(encoding='utf-8')
    cid = re.search(r'사례 (\S+)의 SOP-COOL-12', doc).group(1)
    vals = dict(re.findall(r'^\| (비용|생산|품질|에너지) \| .* \| ([0-9.]+) \|$', doc, re.M))
    ex = next(e for e in base_res['events'] if e['id'] == cid)
    c12 = next(c for c in ex['candidates'] if c['sop'] == 'SOP-COOL-12')
    key = {v: k for k, v in J.LOSS_NAME.items()}
    if not c12['comparison']:
        fail(f'지표_정의.md 손계산 예 {cid} SOP-COOL-12가 엔진에서 비교값이 없음({c12["status"]})')
    else:
        for k, v in vals.items():
            if abs(c12['comparison'][key[k]] - float(v)) > 0.005:
                fail(f'지표_정의.md 손계산 예 {cid} {k}: 문서 {v} / 엔진 {c12["comparison"][key[k]]}')
    recomputed = meta['incident_sop12_recomputed']
    expected['손계산'] = {'사건': {r[0]: {'설계_예측': r[1], '실행_예측': r[2], '설계_합계': r[3], '손계산': r[4], '엔진': r[5], '생성기': r[6], '성분': r[7]} for r in rows_},
                         'SOP-COOL-12_다시_계산한_예측': {'설계': DESIGN['SOP-COOL-12']['다시_계산한_예측'], '실행': recomputed},
                         '지표_정의_예': {'사례': cid, '문서': vals, '엔진': {k: c12['comparison'][key[k]] for k in vals} if c12['comparison'] else None},
                         '사건_입력': {'납기까지_h': due, '잔량_ea': remain, '고온_로트_ea': lot}}
    return rows_, recomputed


# ───────────── 6. 검사기 고의 손상 ─────────────
def trial(key, tmp, name, files, expect_pass, needle=None, must=()):
    """files = {상대 경로: 글 · JSON 값 · None(지움)}. must = 출력에 꼭 있어야 하는 줄 조각(검사기가 무엇을 기준으로 봤는지 등)."""
    lab = copy_lab(key, tmp/f'trial_{len(TRIALS)}')
    for rel, content in files.items():
        p = lab/rel
        if content is None:
            p.unlink(missing_ok=True)
        else:
            write(p, content if isinstance(content, str) else json.dumps(content, ensure_ascii=False, indent=1))
    code, out = run_check(lab)
    caught = [l.strip() for l in out.splitlines() if needle and needle in l]
    shown = all(m in out for m in must)
    ok = ((code == 0 and '구조 검사 통과' in out) if expect_pass else (code != 0 and bool(caught))) and shown
    TRIALS.append({'랩': LAB[key].name, '시험': name, '통과_기대': expect_pass, 'exit': code, '기대대로': ok,
                   '잡은_줄': caught[:3] if not expect_pass else [], '기준_입력_줄': [l for l in out.splitlines() if l.startswith('기준 입력')],
                   '출력_끝': out.splitlines()[-3:] if expect_pass else []})
    if not ok:
        fail(f'검사기 {LAB[key].name} 「{name}」: 기대대로 아님(exit {code}, 꼭 있을 줄 {list(must)} {"있음" if shown else "없음"})\n{out[:1500]}')


TRIALS = []


def table_edit(text, fn):
    rs = list(csv.DictReader(text.splitlines()))
    fn(rs)
    import io
    buf = io.StringIO()
    w = csv.DictWriter(buf, CR.HEADER, lineterminator='\n')
    w.writeheader()
    w.writerows(rs)
    return buf.getvalue()


def first(rs, **kv):
    return next(r for r in rs if all(r[k] == v for k, v in kv.items()))


def renamed(rs):
    """내 조건표를 쓰는 학생: 같은 규칙에 내 ID(R → C)를 붙인 판."""
    for r in rs:
        r['rule_id'] = 'C' + r['rule_id'][1:]


TABLE_DAMAGES = [
    ('`>`인데 경계 「예」', lambda rs: first(rs, rule_id='R2').update(boundary_included='예'), 'boundary_included(예)가 operator >'),
    ('감점 금액 없음', lambda rs: [r.update(penalty_manwon='') for r in rs if r['rule_id'] == 'R2' and r['action'] == 'SOP-COOL-11'], 'PENALTY 행에 penalty_manwon이 없습니다'),
    ('경고에 금액', lambda rs: [r.update(penalty_manwon='5') for r in rs if r['rule_id'] == 'R3' and r['action'] == 'SOP-COOL-11'], 'PENALTY가 아닌 행에 penalty_manwon'),
    ('한 묶음 안 결과 다름', lambda rs: first(rs, rule_id='R1', action='SOP-COOL-11', condition_index='2').update(result='WARN'), '같은 묶음'),
    ('목록 입력에 ==', lambda rs: first(rs, rule_id='R5', action='SOP-COOL-11', condition_index='2').update(operator='=='), '목록 입력 skill_code에는 has_other_than만'),
]


def renamed_ids(value):
    """결과 JSON 안의 규칙 ID(R1 ~ R5)를 내 조건표의 ID(C1 ~ C5)로."""
    return json.loads(re.sub(r'"R([1-5])"', r'"C\1"', json.dumps(value, ensure_ascii=False)))


def checker_trials(tmp, judged):
    base_sop, base_table = json.loads(CR.sop_json(*CR.BASE)), CR.table_csv('가')
    my_table = table_edit(base_table, renamed)
    # 통합 03-2
    k = 'integrated-03-criteria'
    trial(k, tmp, '강사 참조(지점1 가 · 지점2 가)', {'결과/sop.json': base_sop, '결과/조건표.csv': base_table}, True, must=['기준 입력: 입력/graph.json'])
    def sop_damage(fn):
        d = copy.deepcopy(base_sop)
        fn(d)
        return d
    S = lambda d, i: next(s for s in d['sops'] if s['id'] == i)
    sop_cases = [
        ('모델에 없는 ID(팬이 없는 HYD-04의 팬)', lambda d: S(d, 'SOP-COOL-11')['model_refs']['components'].append('HYD-04:fan'), '모델에 없는 ID HYD-04:fan'),
        ('센서 자리에 구성 요소 ID', lambda d: S(d, 'SOP-COOL-11')['model_refs']['sensors'].append('HYD-01:cooler'), 'sensors 자리에 Component'),
        ('같은 SOP 두 번', lambda d: d['sops'].append(copy.deepcopy(S(d, 'SOP-COOL-14'))), 'SOP-COOL-14가 2번'),
        ('수행 단계 순서 건너뜀', lambda d: S(d, 'SOP-COOL-12')['steps'][2].update({'order': 4}), '수행 단계(steps)의 순서가 1부터 차례가 아닙니다'),
        ('없는 원인으로 ADDRESSES', lambda d: d['relations'].append({'type': 'ADDRESSES', 'from': 'SOP-COOL-13', 'to': 'cause:pump-seal-wear', 'source': 'HM-8.4'}), 'cause:pump-seal-wear이 sop.json causes에 없습니다'),
        ('관계 이름 오타', lambda d: d['relations'][0].update(type='MITIGATE_BY'), 'type MITIGATE_BY'),
        ('없는 규칙 ID 참조', lambda d: S(d, 'SOP-COOL-11')['apply_conditions'][0].update({'rules': ['R9']}), '조건표에 없는 규칙 R9'),
    ]
    for name, fn, needle in sop_cases:
        trial(k, tmp, name, {'결과/sop.json': sop_damage(fn), '결과/조건표.csv': base_table}, False, needle)
    for name, fn, needle in TABLE_DAMAGES:
        trial(k, tmp, name, {'결과/sop.json': base_sop, '결과/조건표.csv': table_edit(base_table, fn)}, False, needle)
    graph = json.loads((LAB[k]/'입력/graph.json').read_text(encoding='utf-8'))
    my_graph = {**graph, 'nodes': [n for n in graph['nodes'] if n['props']['id'] != 'HYD-03:fan'],
                'rels': [r for r in graph['rels'] if 'HYD-03:fan' not in (r.get('a'), r.get('b'))]}
    trial(k, tmp, '내 모델(결과/내_입력/graph.json)로 보고 그대로 통과', {'결과/sop.json': base_sop, '결과/조건표.csv': base_table, '결과/내_입력/graph.json': graph},
          True, must=['기준 입력: 결과/내_입력/graph.json'])
    trial(k, tmp, '내 모델에 없는 ID(내 모델에서 HYD-03:fan을 뺌)', {'결과/sop.json': base_sop, '결과/조건표.csv': base_table, '결과/내_입력/graph.json': my_graph},
          False, '모델에 없는 ID HYD-03:fan', must=['기준 입력: 결과/내_입력/graph.json'])
    trial(k, tmp, '내 입력 폴더에 모델이 없으면 제공 모델로 본다고 찍음', {'결과/sop.json': base_sop, '결과/조건표.csv': base_table, '결과/내_입력/README.md': '내 모델 자리\n'},
          True, must=['기준 입력: 입력/graph.json — 결과/내_입력/에 graph.json이 없어 제공 입력으로 봅니다'])
    # 실전 02-5
    k = 'practical-02-conditions'
    trial(k, tmp, '강사 참조(지점2 가)', {'결과/조건표.csv': base_table}, True)
    for name, fn, needle in TABLE_DAMAGES:
        trial(k, tmp, name, {'결과/조건표.csv': table_edit(base_table, fn)}, False, needle)
    # 통합 03-3
    res, rv = judged[BASE_POLICY]
    sv = J.student_view(res)
    k = 'integrated-03-judge'
    trial(k, tmp, '강사 참조(지점3 가 · 지점4 가)', {'결과/result.json': sv}, True, must=['기준 입력: 입력/조건표.csv'])
    inc = meta_incident()
    def jd(fn):
        d = copy.deepcopy(sv)
        fn(d)
        return {'결과/result.json': d}
    E = lambda d, i: next(e for e in d['events'] if e['id'] == i)
    C = lambda e, s: next(c for c in e['candidates'] if c['sop'] == s)
    ex_case, ex_sop = excluded_pick(sv)
    tri = next(e['id'] for e in sv['events'] if len(e['ranking']) >= 3)
    def tie(d):
        e = E(d, tri)
        a, b = e['ranking'][1]['sop'], e['ranking'][2]['sop']
        C(e, b)['comparison'] = copy.deepcopy(C(e, a)['comparison'])
        e['ranking'][2]['total'] = e['ranking'][1]['total']
    def unexplained(d):
        c = C(E(d, inc), 'SOP-COOL-14')
        c['comparison'] = None
        E(d, inc)['ranking'] = [r for r in E(d, inc)['ranking'] if r['sop'] != 'SOP-COOL-14']
    judge_cases = [
        ('사례 하나 빠짐', lambda d: d['events'].pop(5), '사례 · 순서가 다릅니다'),
        ('제외 후보에 비교값', lambda d: C(E(d, ex_case), ex_sop).update(comparison={'cost': 1, 'production': 1, 'quality': 0, 'energy': 0, 'penalty': 0, 'total': 2}), '유지가 아닌 후보(제외)에 비교값'),
        ('보류 후보가 순위에', lambda d: E(d, inc)['ranking'].append({'rank': 4, 'sop': 'SOP-COOL-12', 'total': 999.0}), 'ranking에는 비교값이 있는 후보가 모두 한 번씩'),
        ('합계에 감점을 빠뜨림(합계 ≠ 성분 합)', lambda d: C(E(d, inc), 'SOP-COOL-11')['comparison'].update(total=round(C(E(d, inc), 'SOP-COOL-11')['comparison']['total'] - 20, 2)), '네 손실과 감점의 합'),
        ('같은 합계에 1 · 2 · 3', tie, '같은 합계는 같은 순위'),
        ('이유 없는 null', lambda d: C(E(d, inc), 'SOP-COOL-12')['missing_reasons'].pop('forecast_ts1'), 'forecast_ts1가 null인데 왜 없는지가 없습니다'),
        ('없는 규칙 ID', lambda d: C(E(d, inc), 'SOP-COOL-11')['warnings'][0].update(rule_id='R9'), '기준 조건표에 없는 규칙 · 후보 R9'),
        ('견주지 않은 유지 후보에 까닭 없음', unexplained, 'no_comparison_reason에 까닭이 필요합니다'),
        ('선택 이유 없음', lambda d: E(d, inc)['selection'].update(reason=''), 'selection.reason'),
        ('MPa를 bar로 바꾸지 않음', lambda d: [c['inputs'].update(forecast_ps1=16.73) for c in d['events'][0]['candidates'] if c['inputs']['forecast_ps1'] is not None], '계약 단위 bar의 범위'),
        ('팬 연속 시간을 분 그대로', lambda d: [c['inputs'].update(fan100_hours=1440.78) for c in E(d, inc)['candidates']], '계약 단위 h의 범위'),
    ]
    for name, fn, needle in judge_cases:
        trial(k, tmp, name, jd(fn), False, needle)
    trial(k, tmp, '내 조건표(결과/내_입력/조건표.csv, 규칙 ID C1 ~ C5)로 보고 통과', {'결과/result.json': renamed_ids(sv), '결과/내_입력/조건표.csv': my_table},
          True, must=['기준 입력: 결과/내_입력/조건표.csv'])
    trial(k, tmp, '내 조건표를 두고 제공 조건표의 규칙 ID로 낸 결과', {'결과/result.json': sv, '결과/내_입력/조건표.csv': my_table},
          False, '기준 조건표에 없는 규칙 · 후보 R', must=['기준 입력: 결과/내_입력/조건표.csv'])
    trial(k, tmp, '내 조건표의 열 이름이 계약과 다름', {'결과/result.json': sv, '결과/내_입력/조건표.csv': my_table.replace('rule_id,action', 'id,sop', 1)},
          False, '열 이름이 계약(rule_id · action …)과 다릅니다', must=['기준 입력: 결과/내_입력/조건표.csv'])
    # 실전 03-2
    k = 'practical-03-review'
    md = J.review_md(rv)
    trial(k, tmp, '강사 참조(지점3 가 · 지점4 가)', {'결과/조치검토결과.json': rv, '결과/조치검토결과.md': md}, True,
          must=['기준 입력: 입력/조건표.csv', '기준 입력: 입력/sop.json'])
    def rd(fn, text=md):
        d = copy.deepcopy(rv)
        fn(d)
        return {'결과/조치검토결과.json': d, '결과/조치검토결과.md': text}
    I = lambda d, i: next(x for x in d['events'] if x['id'] == i)
    K = lambda x, s: next(c for c in x['candidates'] if c['sop'] == s)
    review_cases = [
        ('검토 의견의 1위에 제외 후보', lambda d: I(d, ex_case)['review'].update(top=[ex_sop]), f'review.top의 {ex_sop}는 비교값이 있는 유지 후보가 아닙니다'),
        ('추가 확인 빈칸', lambda d: K(I(d, inc), 'SOP-COOL-12').update(checks=[]), '추가로 확인할 값(checks)에 없습니다'),
        ('승인 역할 다름', lambda d: K(I(d, inc), 'SOP-COOL-14')['approval'].update(role='운전원'), '승인 역할 운전원이 기준 sop.json의 설비보전팀장과 다릅니다'),
        ('사례 하나 빠짐', lambda d: d['events'].pop(3), '사례 · 순서가 다릅니다'),
        ('미확인에 빠진 이유 없음', lambda d: [r.pop('missing_reason') for r in K(I(d, inc), 'SOP-COOL-12')['reasons'] if r['result'] == '미확인'], '미확인에는 missing_inputs와 missing_reason'),
    ]
    for name, fn, needle in review_cases:
        trial(k, tmp, name, rd(fn), False, needle)
    cut = re.sub(rf'^## {re.escape(inc)} .*$', '## 사건 절', md, flags=re.M)
    trial(k, tmp, 'MD 절 빠짐', rd(lambda d: None, cut), False, f'조치검토결과.md에 {inc}의 절 제목이 없습니다')
    my_rv = renamed_ids(rv)
    trial(k, tmp, '내 조건표(결과/내_입력/조건표.csv)로 보고 통과', {'결과/조치검토결과.json': my_rv, '결과/조치검토결과.md': md, '결과/내_입력/조건표.csv': my_table},
          True, must=['기준 입력: 결과/내_입력/조건표.csv', '기준 입력: 입력/sop.json — 결과/내_입력/에 sop.json이 없어 제공 입력으로 봅니다'])
    trial(k, tmp, '내 조건표를 두고 제공 조건표의 규칙 ID로 낸 결과', {'결과/조치검토결과.json': rv, '결과/조치검토결과.md': md, '결과/내_입력/조건표.csv': my_table},
          False, '기준 조건표에 없는 규칙 · 후보 R', must=['기준 입력: 결과/내_입력/조건표.csv'])


def excluded_pick(sv):
    for e in sv['events']:
        for c in e['candidates']:
            if c['status'] == '제외' and any(x['status'] == '유지' for x in e['candidates']):
                return e['id'], c['sop']
    raise RuntimeError('제외 후보가 있는 사례가 없음')


def meta_incident():
    return DC_META['incident']


# ───────────── 7. 학생 폴더 경계 ─────────────
TRAPS = ['팬을 최대로 올리는 두 조치', '1,440분은', 'HM-8.6을 단계', '지금 설정이 이어질', '지금 상태가 이어질', '끊긴 것으로 본다', '재전송이다', '몇천 배']   # 함정의 답 문장
LAB_ANSWERS = {   # 그 랩이 정할 지점의 답 문장 · 사건 비교 합계(학생 폴더 어디에도 없어야 한다, K-28 · K-149)
    'integrated-03-criteria': ['원문 미확인', 'HYD-04는 뺐', '수냉식이라 핀 세척 대상 아님', '설명 문장대로', '옛 판단 시스템이 대상 빈칸'] + TRAPS,
    'practical-02-conditions': ['원문 미확인', '설명 문장대로', '옛 판단 시스템이 대상 빈칸'] + TRAPS,
    'integrated-03-judge': [*J.GAP_TEXT.values(), *J.WARN_TEXT.values(), '경고는 사유로 보존', '이어진 것으로 본다', '경고 없는 후보끼리', '쓸 수 있지만'] + TRAPS,
    'practical-03-review': [*J.GAP_TEXT.values(), *J.WARN_TEXT.values(), '경고는 사유로 보존', '이어진 것으로 본다', '경고 없는 후보끼리', '쓸 수 있지만'] + TRAPS,
}
REFERENCE_NAMES = {'criteria.py', 'judge_actions.py', 'run_reference.py', 'result.json', '조치검토결과.json', '조치검토결과.md', 'expected_results.json',
                   '요구사항_참조.md', '판단기록_참조.md', '완성본_안내.md'}


def boundary(totals):
    for key, folder in LAB.items():
        for p in folder.rglob('*'):
            if not p.is_file():
                continue
            if p.name in REFERENCE_NAMES:
                fail(f'{folder.name}: 학생 폴더에 강사 참조 파일 {p.relative_to(folder)}')
            if p.suffix not in ('.md', '.py', '.json', '.txt', '.csv', '.html') or p.parent.name == '자료' and p.suffix == '.csv':
                continue
            text = p.read_text(encoding='utf-8')
            rel = p.relative_to(folder).as_posix()
            if rel.startswith('입력/'):
                continue            # 앞 단계 강사 검증 판(K-48)
            for w in LAB_ANSWERS[key]:
                if w in text:
                    fail(f'{folder.name}/{rel}: 이 랩이 정할 지점의 답 문장 「{w}」')
            for t in totals:
                if f'{t:.2f}' in text and rel != '자료/metrics/지표_정의.md':
                    fail(f'{folder.name}/{rel}: 사건 비교 합계 {t:.2f}')
            for word in ('reference', '강사 참조', '완성본 위치'):
                if word in text:
                    fail(f'{folder.name}/{rel}: 강사 자리를 가리키는 말 「{word}」')


# ───────────── 8. 학생용 완성본(실습 폴더와 따로 받는 묶음, 기본 갈래) ─────────────
COMPLETED = HERE/'completed'
STAMP = (2026, 1, 1, 0, 0, 0)
GUIDE_HEAD = ('ZIP 전체를 실습 폴더와 다른 새 폴더에 풀고, 이 문서가 있는 폴더를 VS Code에서 연 뒤 터미널에서 아래 명령을 실행합니다. '
              'Python 3 표준 라이브러리만 쓰고, AI 계정 · 인터넷 접속 없이 실행됩니다. `결과/`에 들어 있는 파일은 이 명령을 실행해 얻은 것과 같습니다.')


def completed_target(key):
    lab = LAB[key]
    return lab.parents[1]/'완성본'/f'{lab.name}_학생용완성본.zip', f'{lab.name}_학생용완성본'


def md_rows(head, rows):
    return CR.md_table(head, rows)


def fill_template(title, sections):
    """build_labs.req_template의 절 이름 그대로, 칸을 채운 판(제공 빈 틀 표시 없이)."""
    out = [f'# {title}', '']
    for name, body in sections:
        out += [f'## {name}', '', body, '']
    return '\n'.join(out).rstrip() + '\n'


def criteria_requirements(memo, checks):
    """통합 03-2 완성본의 결과/요구사항.md — 기본 갈래(지점1 가 · 지점2 가)."""
    groups = {}
    for p2 in CR.P2:
        table = Path(tempfile.mkdtemp())/'t.csv'
        table.write_text(CR.table_csv(p2), encoding='utf-8')
        groups[p2] = J.load_table(table)
    sub = []
    picked = [TRIP_CASE, HOT_CASE]
    for cid, x in [('사건', memo)] + [(c, checks[c]) for c in picked]:
        for sop, v in x.items():
            j = J.evaluate(sop, v, groups['가'])
            other = {p2: J.evaluate(sop, v, groups[p2])['status'] for p2 in ('나', '다')}
            hits = [h['rule_id'] for k in ('warnings', 'penalties', 'exclusions') for h in j[k]]
            diff = [f'{p2}였다면 {st}' for p2, st in other.items() if st != j['status']]
            sub.append([f'{cid} / {sop}', ' · '.join(hits) or '—',
                        ' · '.join(f'{h["rule_id"]} {kind}' for kind, key in (('경고', 'warnings'), ('감점', 'penalties'), ('제외', 'exclusions')) for h in j[key]) or '없음',
                        ' · '.join(f'{u["rule_id"]}({", ".join(u["missing"])})' for u in j['unknown']) or '—',
                        ('3단계 기대와 같음' if cid == '사건' else f'{j["status"]}') + ('; 출처가 확인되지 않는 기준 ' + ', '.join(diff) if diff else '')])
    return fill_template('요구사항', [
        ('목표와 질문', '현행 HM-8 1.1판의 냉각 계통 조치 일곱 개를 SOP 구조와 조건표로 정리해 고장 유형 · 원인과 2회차에 만든 설비 모델의 ID에 잇고, '
                       '10월 27일 HYD-02 경보에서 야간 운전원이 할 수 있는 조치를 원문 근거로 답한다(START.md 「해결할 질문」 1 ~ 3).'),
        ('이 답을 쓰는 사람과 쓰는 곳', '설비보전팀장 — 판단 시스템에 조치 기준을 올릴 때. 야간 운전원 — 사건에서 쓸 수 있는 조치를 볼 때.'),
        ('사용할 자료와 기준일', '현행 원문 `자료/HM-8_매뉴얼.md`(1.1판, 2026-09-01 시행), 옛 판 `자료/HM-8_1.0판_매뉴얼.md`, `자료/판단시스템_결정표_내보내기.txt`, `자료/작업지시_이력.csv`, '
                             '`입력/graph.json`(설비 모델), `자료/사건_기록_HYD-02_1027.md` · `자료/확인_사례.csv`. 기준일 2026-10-28.'),
        ('지킬 조건', '- 원문에 없는 기준값 · 단계를 만들지 않는다(작업기준 2절).\n- 모델에 없는 대상에는 새 ID를 만들지 않는다.\n- 항목마다 원문 출처를 단다.'),
        ('정한 것', md_rows(['지점(종류)', '고른 것', '근거(파일 · 줄)', '이 선택으로 바뀌는 답'], [
            ['적용 범위', 'HYD-01 ~ 03에만 건다(HYD-04는 뺌)', '설비_대장.csv HYD-04 비고 「HPP-45A 후속형. 수냉식 열교환기」; graph.json HYD-04 구성 요소 · 센서; 작업지시_이력.csv HYD-04 냉각수측 스케일; HM-8에 적용 범위 문장 없음',
             'sop.json의 모델 참조(model_refs) — HYD-04 ID 없음, not_linked에 까닭'],
            ['출처가 확인되지 않는 기준', '옛 시스템이 건 그대로 네 후보에 제외로 옮기고, 이유 칸에 작업지시 후보와의 어긋남을 밝힘',
             '판단시스템_결정표_내보내기.txt rule:ts1-hard(출처 ks:sr-04) · rule:trip-reset-only(출처 HM-9.4) — HM-8 1.1 · 1.0에 같은 문장 없음; HM-8.3 인터록 65 ℃ 이상',
             '확인 사례의 트립 · 예측 65 ℃ 이상 사례(아래 대입) — 사건은 바뀌지 않음']])),
        ('기대 답과 실제 결과', md_rows(['질문 · 물은 대상', '원자료에서 먼저 찾은 기대 답(파일 · 줄)', '실제 결과', '고친 점 · 다시 확인'], [
            ['1 SOP-COOL-11의 다섯 칸', 'HM-8.5 SOP-COOL-11 단계 1 ~ 3, 승인 운전원, HM-8.6 회복 판정, HM-8.8 금지와 제한', 'sop.json의 SOP-COOL-11과 같음', '—'],
            ['3 사건 네 후보', '11 경고 R3 · 감점 R2, 12 감점 R2 · 예측 없음, 13 · 14 맞은 규칙 없음', '아래 「사건 · 확인 사례 대입」과 같음', '—']])),
        ('설비마다 걸었음 · 뺐음', md_rows(['설비', '걸었음 · 뺐음', '까닭(모델 · 대장 줄)'], CR.asset_scope('가'))),
        ('판단 시스템 결정표 대조', md_rows(['내보내기 행', '처리', '까닭', '근거(파일 · 줄)'], CR.export_treatment('가'))),
        ('사건 · 확인 사례 대입', md_rows(['사례 / 후보', '맞은 규칙', '결과(경고 · 감점 · 제외)', '확인할 수 없는 조건과 까닭', '기대와 같은가 · 다른 선택이었다면'], sub)),
        ('저장 기록', '- 기준일: 2026-10-28\n- 저장 시점: 2026-10-28(저장한 뒤 다시 열어 `python check.py` · `python 결과/trace_sources.py` 출력이 같음)\n- 확인하지 못한 점: 설비안전규정 SR-04 · HM-9.4 원문은 제공 자료에 없어 확인하지 못했다. HYD-04의 냉각 정비 지침은 제조사 자료가 필요하다.'),
    ])


def conditions_record_completed(checks):
    """실전 02-5 완성본의 결과/판단기록.md — 기본 갈래(지점2 가)."""
    table = Path(tempfile.mkdtemp())/'t.csv'
    table.write_text(CR.table_csv('가'), encoding='utf-8')
    groups = J.load_table(table)
    sub, approve = [], []
    for cid, cs in checks.items():
        for sop, x in cs.items():
            j = J.evaluate(sop, x, groups)
            sub.append([cid, sop, ' · '.join(h['rule_id'] for k in ('warnings', 'penalties', 'exclusions') for h in j[k]) or '—',
                        ' · '.join(h['rule_id'] for h in j['warnings']) or '—', ' · '.join(f'{h["penalty_manwon"]:g}' for h in j['penalties']) or '—',
                        ' · '.join(h['rule_id'] for h in j['exclusions']) or '—', ' · '.join(f'{u["rule_id"]}({", ".join(u["missing"])})' for u in j['unknown']) or '—',
                        {'제외': '빠짐', '보류': '판단 보류', '유지': '남음'}[j['status']], ' · '.join(sorted({h['source_section'] for k in ('warnings', 'penalties', 'exclusions') for h in j[k]})) or '—'])
            if j['status'] == '유지':
                approve.append([cid, sop, '설비보전팀장' if sop == 'SOP-COOL-14' else '운전원', 'HM-8.7' if sop == 'SOP-COOL-14' else f'HM-8.5 {sop} 승인'])
    return fill_template('판단 기록', [
        ('목표와 질문', '제공 SOP(HM-8 1.1판)의 경고 · 감점 · 제외 조건을 조건표로 옮기고, 판단 시스템 결정표와 출처를 견주고, 사건과 확인 사례에서 각 후보가 남는지 · 빠지는지 · 무엇이 아직 모르는 값인지와 남은 후보의 승인 역할을 답한다.'),
        ('이 답을 쓰는 사람과 쓰는 곳', '야간 운전원 — 경보가 났을 때 어느 조치가 남고 빠지는지, 남은 조치를 누가 승인하는지 볼 때.'),
        ('사용할 자료와 기준일', '`자료/HM-8_매뉴얼.md`(1.1판, 2026-09-01 시행), `자료/작업기준.md`, `자료/판단시스템_결정표_내보내기.txt`, `자료/사건_기록_HYD-02_1027.md`, `자료/확인_사례.csv`. 기준일 2026-10-28.'),
        ('지킬 조건', '- 조건표의 행마다 원문 출처를 단다.\n- 사례에 대는 기능은 규칙을 코드에 다시 적지 않고 `결과/조건표.csv`에서 읽는다.\n- 남은 후보를 실행 승인처럼 적지 않는다.'),
        ('정한 것', md_rows(['지점(종류)', '고른 것', '근거(파일 · 줄)', '이 선택으로 바뀌는 답'], [
            ['출처가 확인되지 않는 기준', '옛 시스템이 건 그대로 네 후보에 제외로 옮기고, 이유 칸에 작업지시 후보와의 어긋남을 밝힘',
             '판단시스템_결정표_내보내기.txt rule:ts1-hard(출처 ks:sr-04) · rule:trip-reset-only(출처 HM-9.4) — HM-8 1.1에 같은 문장 없음',
             f'트립 사례 {TRIP_CASE} — 네 후보 모두 제외, 예측 65 ℃ 이상 사례 {HOT_CASE} — SOP-COOL-14 제외']])),
        ('기대 답과 실제 결과', md_rows(['질문 · 물은 대상', '원자료에서 먼저 찾은 기대 답(파일 · 줄)', '실제 결과', '고친 점 · 다시 확인'], [
            ['2 사건 네 후보', '11 경고 R3 · 감점 R2 → 남음, 12 감점 R2 · R3 · R4 알 수 없음(예측 없음) → 판단 보류, 13 · 14 맞은 규칙 없음 → 남음', '사례 대조 표의 사건 줄과 같음', '—'],
            [f'2 트립 사례 {TRIP_CASE}', '원격 셋 R5 제외, 14도 R5 제외(옛 규칙을 대상 빈칸 그대로) → 모두 빠짐', '사례 대조 표와 같음', '—']])),
        ('확인 사례 대조', md_rows(['사례', '후보', '맞은 규칙', '경고', '감점(만원)', '제외 사유', '미확인과 까닭', '남는가 · 빠지는가', '원문 근거'], sub)),
        ('남은 후보와 실행 승인', md_rows(['사례', '남은 후보', '승인 역할', '승인 근거(파일 · 줄)'], approve)),
        ('저장 기록', '- 기준일: 2026-10-28\n- 저장 시점: 2026-10-28(저장한 뒤 다시 열어 `python check.py` · `python 결과/apply_conditions.py` 출력이 같음)\n- 확인하지 못한 점: 설비안전규정 SR-04 · HM-9.4 원문은 제공 자료에 없어 확인하지 못했다.'),
    ])


def judge_expectations(res, meta):
    """판정 랩 완성본의 결과/기대결과.md — 기대 칸은 두 번째 구현(oracle_case)이 원천에서 따로 낸 값, 실제 칸은 판정 기능의 출력."""
    cases = {c['id']: c for c in meta['cases']}
    kinds = ['정상', '경계 55', '운전 중 예측 65 이상', '팬 1,440분 경계', '모드 수동', '트립', '모두 제외', 'PLC 끊김', 'PLC bad', '예측 거부', '전달 실패', '120초 지남', '오더 실패', '카운터 끊김', '사건']
    rows_, done = [], set()
    for kind in kinds:
        e = next((x for x in res['events'] if kind in cases[x['id']]['categories'] and x['id'] not in done), None)
        if e is None:
            continue
        done.add(e['id'])
        out, ranks, top = oracle_case(cases[e['id']], '가', BASE_POLICY)
        for c in e['candidates']:
            o = out[c['sop']]
            want = f'{o["status"]}' + (f' {o["total"]:.2f}' if o['total'] is not None else '') + (' ' + ' · '.join(f'{k} {",".join(v)}' for k, v in o['hits'].items() if v) if any(o['hits'].values()) else '') + (f' 미확인 {",".join(o["unknown"])}' if o['unknown'] else '')
            got = f'{c["status"]}' + (f' {c["comparison"]["total"]:.2f}' if c['comparison'] else '')
            src = ', '.join(sorted({h['source_section'] for k in ('warnings', 'penalties', 'exclusions') for h in c[k]} | {u['source_section'] for u in c['unknown']})) or '—'
            same = o['status'] == c['status'] and (o['total'] is None) == (c['comparison'] is None) and (o['total'] is None or abs(o['total'] - c['comparison']['total']) < 0.005)
            rows_.append([f'{e["id"]} / {c["sop"]}', kind, ', '.join(f'{k}={v}' for k, v in c['inputs'].items() if k in ('forecast_ts1', 'fan100_hours', 'plc_mode', 'plc_state')),
                          want, src, got, '같음' if same else '다름'])
            if not same:
                fail(f'완성본 기대결과 {e["id"]} {c["sop"]}: 기대 {want} / 실제 {got}')
    inc = next(x for x in res['events'] if x['id'] == meta['incident'])
    hand = [[f'{inc["id"]} / {c["sop"]}', J.LOSS_NAME[k] if k in J.LOSS_NAME else '감점', f'{c["comparison"][k]:.2f}', f'{c["comparison"][k]:.2f}', '같음']
            for c in inc['candidates'] if c['comparison'] for k in ('cost', 'production', 'quality', 'energy', 'penalty')]
    text = expect_doc_sections(res)
    return text.replace('{CASES}', md_rows(['사례 / 후보', '사례 종류', '원천 행과 판단 입력', '기대 판정 · 이유(실행 전)', '근거(규칙 · 원문 절)', '실제 결과', '같음 / 다른 까닭과 고친 점'], rows_)) \
               .replace('{HAND}', md_rows(['사례 / 후보', '지표', '손계산', '프로그램', '같은가'], hand))


def expect_doc_sections(res):
    dec = md_rows(['입력', '원천과 만든 방법', '근거(파일 · 절)'], [[d['item'], d['decision'], d['basis']] for d in res['decisions']])
    return ('# 기대 결과와 실제 대조\n\n'
            '기대 칸은 프로그램을 실행하기 전에 원천 기록 · 조건표 · 원문으로 구한 것이고, 실제 칸은 실행한 뒤에 적었다.\n\n'
            '- 기대 칸을 쓴 시각(실행 전): 2026-10-28, 프로그램을 실행하기 전 — 원천 기록 · 조건표 · 원문으로 구함\n- 실행한 명령과 실행 시각: `python 결과/judge_actions.py . 결과` — 2026-10-28, 기대 칸을 쓴 뒤\n\n'
            '## 목표와 질문\n\n경보마다 네 후보를 조건표로 판정하고 주어진 비교 산식으로 견주어, 사건과 지난 30일 경보의 판정 · 순위 · 선택 이유를 낸다.\n\n'
            '## 이 답을 쓰는 사람과 쓰는 곳\n\n야간 운전원 · 설비보전팀장 — 경보 때 쓸 수 있는 후보와 1위, 먼저 확인할 값을 볼 때.\n\n'
            '## 사용할 자료와 기준일\n\n`입력/조건표.csv` · `입력/sop.json`, `자료/`의 원천 네 개와 오더 현황 · 비교 산식. 기준일 2026-10-28.\n\n'
            '## 지킬 조건\n\n- 규칙은 조건표에서 읽는다.\n- 빈 값을 0이나 앞 값으로 채우지 않는다.\n- 비교 순위와 선택 이유를 실행 승인처럼 적지 않는다.\n\n'
            '## 정한 것\n\n' + md_rows(['지점(종류)', '고른 것', '근거(파일 · 줄)', '이 선택으로 바뀌는 답'], [
                ['빈 값의 뜻', J.GAP_TEXT[GAP[BASE_POLICY[0]]], '수집_설명.md 팬_운전_카운터(10분 주기 기록); PLC_상태_수신.csv 판정 요청 전 팬 설정 100 %', '사건 SOP-COOL-11 · 12의 팬 연속 시간과 감점 R2(값 없음이면 보류)'],
                ['쓰는 사람에 따라 갈리는 답', J.WARN_TEXT[WARN[BASE_POLICY[1]]], 'HM-8.6 「다른 조치와 비교한다」; 지표_정의.md 품질 손실(예측 55 ℃ 이상)', '사건 순위의 SOP-COOL-11(경고 R3)']]) + '\n\n'
            '## 판단 입력을 만든 방법\n\n' + dec + '\n\n'
            '## 사례 대조\n\n{CASES}\n\n'
            '## 손계산 대조\n\n{HAND}\n\n'
            '## 저장 기록\n\n- 기준일: 2026-10-28\n- 저장 시점: 2026-10-28(저장한 뒤 다시 열어 같은 명령의 출력과 `python check.py` 출력이 같음)\n- 확인하지 못한 점: 사건의 SOP-COOL-12 예측은 판정 요청을 다시 해야 받을 수 있다.\n')


def completed_guide(key, title, command, look):
    return f'# {title} — 학생용 완성본\n\n{GUIDE_HEAD}\n\n```text\n{command}\npython check.py\n```\n\n{look}\n\n이 완성본이 따른 「정한 것」은 결과 기록 파일의 「정한 것」 표에 있습니다. 다른 선택을 하면 결과가 달라질 수 있으니, 내 실습에서는 원문을 열어 내 선택과 근거로 정합니다.\n'


def build_completed(tmp, judged, checks, memo, expected):
    res, rv = judged[BASE_POLICY]
    cases_meta = DC_META
    plans = {
        'integrated-03-criteria': dict(
            files={'결과/sop.json': CR.sop_json(*CR.BASE), '결과/조건표.csv': CR.table_csv('가'), '결과/요구사항.md': criteria_requirements(memo, checks),
                   '결과/설비_연결_기준.json': json.dumps({'decision': '정한 것(적용 범위): HYD-01 ~ 03에만 건다', 'sops': {
                       s: {'assets': CR.model_ref(s, '가')['assets'], 'components': CR.MODEL[s][0], 'sensors': CR.MODEL[s][1], 'not_linked': CR.model_ref(s, '가')['not_linked']}
                       for s, *_ in CR.SOPS}}, ensure_ascii=False, indent=2) + '\n'},
            code={'결과/link_model_ids.py': COMPLETED/'link_model_ids.py', '결과/trace_sources.py': COMPLETED/'trace_sources.py'},
            commands=[['결과/link_model_ids.py'], ['결과/trace_sources.py']], outputs=['결과/sop.json', '결과/출처_대조.md'],
            command='python 결과/link_model_ids.py\npython 결과/trace_sources.py',
            look='`결과/sop.json`은 냉각 계통 조치 일곱 개의 SOP 구조 · 관계 · 설비 모델 참조, `결과/조건표.csv`는 판단 조건, `결과/요구사항.md`는 정한 것과 대조 기록입니다. '
                 '`link_model_ids.py`는 설비 모델에서 절차마다 걸 ID를 찾아 모델 참조를 채우고, `trace_sources.py`는 항목마다 원문 줄을 찾아 `결과/출처_대조.md`에 나란히 적습니다(원문에서 찾지 못한 출처는 끝에 따로).'),
        'practical-02-conditions': dict(
            files={'결과/조건표.csv': CR.table_csv('가'), '결과/판단기록.md': conditions_record_completed(checks)},
            code={'결과/apply_conditions.py': COMPLETED/'apply_conditions.py'},
            commands=[['결과/apply_conditions.py']], outputs=['결과/사례_대조.md'],
            command='python 결과/apply_conditions.py',
            look='`결과/조건표.csv`는 경고 · 감점 · 제외 조건, `결과/판단기록.md`는 정한 것 · 확인 사례 대조 · 남은 후보와 실행 승인입니다. '
                 '`apply_conditions.py`는 조건표를 확인 사례에 대어 후보마다 맞은 규칙과 알 수 없는 규칙을 `결과/사례_대조.md`에 적습니다.'),
        'integrated-03-judge': dict(
            files={'결과/result.json': json.dumps(J.student_view(res), ensure_ascii=False, indent=1) + '\n', '결과/기대결과.md': judge_expectations(res, cases_meta)},
            code={'결과/judge_actions.py': HERE/'judge_actions.py'},
            commands=[['결과/judge_actions.py', '.', '결과']], outputs=['결과/result.json'],
            command='python 결과/judge_actions.py . 결과',
            look='`judge_actions.py`는 원천 네 개에서 판단 입력을 만들고, `입력/조건표.csv`로 후보를 판정하고, `자료/metrics/지표_정의.md`의 식으로 견주어 `결과/result.json`을 씁니다. '
                 '`결과/기대결과.md`의 기대 칸과 사건의 순위 · 선택 이유를 견주어 보세요.'),
        'practical-03-review': dict(
            files={'결과/조치검토결과.json': json.dumps(rv, ensure_ascii=False, indent=1) + '\n', '결과/조치검토결과.md': J.review_md(rv),
                   '결과/기대결과.md': judge_expectations(res, cases_meta).replace('python 결과/judge_actions.py . 결과', 'python 결과/judge_actions.py . 결과 --review')},
            code={'결과/judge_actions.py': HERE/'judge_actions.py'},
            commands=[['결과/judge_actions.py', '.', '결과', '--review']], outputs=['결과/조치검토결과.json', '결과/조치검토결과.md'],
            command='python 결과/judge_actions.py . 결과 --review',
            look='`judge_actions.py`는 원천 네 개에서 판단 입력을 만들고, `입력/조건표.csv`로 판정 · 비교한 뒤 `입력/sop.json`의 승인 역할 · 실행 전 확인을 붙여 '
                 '`결과/조치검토결과.json` · `.md`를 씁니다. `조치검토결과.md`의 사건 절만 읽고 후보마다 판정 · 까닭 · 승인 역할과 먼저 확인할 값을 말해 보세요.'),
    }
    report = {}
    for key, plan in plans.items():
        target, name = completed_target(key)
        folder = Path(tmp)/'completed'/name
        shutil.copytree(LAB[key], folder)
        for rel, text in plan['files'].items():
            write(folder/rel, text)
        for rel, src in plan['code'].items():
            write(folder/rel, Path(src).read_text(encoding='utf-8'))
        if key == 'practical-02-conditions':      # 동봉 결과는 동봉 코드를 실행해 얻은 것
            run_py(folder, *plan['commands'][0])
        if key == 'integrated-03-criteria':
            run_py(folder, *plan['commands'][1])
        write(folder/'완성본_안내.md', completed_guide(key, BJ.TITLES[key], plan['command'], plan['look']))
        start = (folder/'START.md').read_text(encoding='utf-8')
        head, rest = start.split('\n', 1)
        write(folder/'START.md', head + '\n\n완성한 결과를 실행하려면 [완성본 안내](완성본_안내.md)를 여세요. 아래는 이 결과가 푸는 원래 과제입니다.\n' + rest)
        files = {p.relative_to(folder).as_posix(): p.read_bytes() for p in sorted(folder.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
        # 새 폴더에서 안내의 명령을 다시 실행 — 동봉한 결과와 같은 바이트, 학생 검사기 통과(K-58)
        fresh = Path(tmp)/'completed_run'/name
        for rel, data in files.items():
            (fresh/rel).parent.mkdir(parents=True, exist_ok=True)
            (fresh/rel).write_bytes(data)
        outs = []
        for cmd in plan['commands']:
            code, out = run_py(fresh, *cmd)
            outs.append(out.splitlines()[-1] if out else '')
            if code != 0:
                fail(f'완성본 {name}: {" ".join(cmd)} 실패\n{out[:1500]}')
        for rel in plan['outputs']:
            if (fresh/rel).read_bytes() != files[rel]:
                fail(f'완성본 {name}: 안내의 명령을 다시 실행한 {rel}이 동봉한 파일과 다름')
        code, out = run_check(fresh)
        if code != 0 or '구조 검사 통과' not in out:
            fail(f'완성본 {name}: 학생 검사기가 통과시키지 않음\n{out[:1500]}')
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as z:
            for rel, data in files.items():
                info = zipfile.ZipInfo(f'{name}/{rel}', STAMP)
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, data)
        with zipfile.ZipFile(io.BytesIO(buf.getvalue())) as z:
            if {n.split('/', 1)[1]: z.read(n) for n in z.namelist()} != files:
                fail(f'완성본 {name}: ZIP 안 경로 · 바이트가 묶은 폴더와 다름')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(buf.getvalue())
        report[name] = {'경로': target.relative_to(BJ.OUT).as_posix(), '파일수': len(files), 'sha256': hashlib.sha256(buf.getvalue()).hexdigest(),
                        '명령': plan['command'], '실행_출력_끝': outs, '검사기': out.splitlines()[-2] if out else ''}
    expected['학생용_완성본'] = report
    return report


# ───────────── 사건 갈래표 ─────────────
NEXT = {   # 1위 후보 → 답을 쓰는 사람의 다음 행동(HM-8 승인 줄 · 후보_설정.csv)
    'SOP-COOL-11': '운전원이 SOP-COOL-11(팬 100 % 유지 — 이미 그 상태) 승인을 검토하고 15분 재관측 — 예측상 경보가 이어질 수 있음',
    'SOP-COOL-12': '운전원이 SOP-COOL-12(팬 100 % · 부하 80 %) 승인을 검토하고 15분 재관측',
    'SOP-COOL-13': '운전원이 SOP-COOL-13(부하 70 % · 야간 핀 세척 작업지시) 승인을 검토',
    'SOP-COOL-14': '야간 운전원이 설비보전팀장에게 SOP-COOL-14(정지 · 핀 세척, 정지 3 h) 승인을 요청',
    '': '견줄 후보가 없어 설비보전팀장을 부르고 냉각 뒤 복귀를 판단'}


def next_action(e):
    top = [r['sop'] for r in e['ranking'] if r['rank'] == 1]
    act = NEXT[top[0] if top else '']
    gap = [c['sop'] for c in e['candidates'] if c['status'] == '보류' and any('fan100_hours' in u['missing'] for u in c['unknown'])]
    if gap:
        act += f' — 그 전에 팬 연속 시간(카운터 기록 끊김)을 PLC 팬 이력에서 다시 받아 {" · ".join(gap)}의 판정을 끝냄'
    return top, act


def incident_table(judged, hand_rows, recomputed, chain_rec, expected):
    inc = DC_META['incident']
    lines = ['# 사건 갈래표 — 10월 27일 HYD-02 쿨러 성능 저하 경보', '',
             f'run_reference.py가 실제로 돌린 값이다(경보 {inc}). 대본 · 가이드가 넘겨받는 「판단이 갈리는 지점과 확인할 사례」(코딩랩.md K맥-10). 학생 폴더에 넣지 않는다.', '',
             '## 판정 랩(통합 03-3 · 실전 03-2) — 지점3 × 지점4, 입력 = 지점1 가 · 지점2 가', '',
             f'- 지점3(빈 값의 뜻 · 판단 입력의 정보 부족 처리): 가 = {J.GAP_TEXT[GAP["가"]]} / 나 = {J.GAP_TEXT[GAP["나"]]}',
             f'- 지점4(쓰는 사람에 따라 갈리는 답 · 허용 후보 비교): 가 = {J.WARN_TEXT[WARN["가"]]} / 나 = {J.WARN_TEXT[WARN["나"]]}', '']
    body = []
    for pol in POLICIES:
        res, _ = judged[pol]
        e = next(x for x in res['events'] if x['id'] == inc)
        top, act = next_action(e)
        st = ' · '.join(f'{c["sop"][-2:]} {c["status"]}' + ('(견주지 않음)' if c['status'] == '유지' and not c['comparison'] else '') for c in e['candidates'])
        body.append([pol[0], pol[1], st, ', '.join(f'{r["rank"]}위 {r["sop"]} {r["total"]:.2f}' for r in e['ranking']) or '없음', ', '.join(top) or '없음', act])
    lines.append(CR.md_table(['지점3', '지점4', '사건 판정', '순위(만원)', '1위', '야간 운전원 · 설비보전팀장의 다음 행동'], body))
    base, _ = judged[BASE_POLICY]
    e = next(x for x in base['events'] if x['id'] == inc)
    cnt = next(c for c in DC_META['cases'] if c['id'] == inc)['inputs']['counter']
    lines += ['', f'사건의 팬 카운터 마지막 기록: {cnt[1]} 「{cnt[3]}」 {cnt[2]}분 — 판정 요청까지 주기(10분)를 넘게 다음 기록이 없다(그 사이 주기 기록 한 줄이 수집에서 빠짐). '
              'PLC 팬 설정은 판정 요청 전 3분 동안 100 %.',
              '사건 판정(기본 갈래 가 · 가): ' + '; '.join(f'{c["sop"]} {c["status"]}' + (f' 합계 {c["comparison"]["total"]:.2f}' if c['comparison'] else '')
                                                    + (' 경고 ' + '·'.join(h['rule_id'] for h in c['warnings']) if c['warnings'] else '')
                                                    + (' 감점 ' + '·'.join(h['rule_id'] for h in c['penalties']) if c['penalties'] else '')
                                                    + (' 미확인 ' + '·'.join(u['rule_id'] for u in c['unknown']) if c['unknown'] else '') for c in e['candidates']) + '.',
              f'SOP-COOL-12를 다시 계산하면 예측 유온 {recomputed:.2f} ℃(강사 참조에만) — 판정 요청을 다시 해 예측을 받으면 12가 보류에서 풀린다.', '']
    # 지점마다 다음 행동이 바뀌는 이력 사례(사건 밖)
    lines += ['## 지점이 바꾸는 이력 사례(사건 밖, 1위가 바뀌는 경보)', '']
    body = []
    for name, a_pol, b_pol in [('지점3', ('가', '가'), ('나', '가')), ('지점4', ('가', '가'), ('가', '나'))]:
        ra, rb = judged[a_pol][0], judged[b_pol][0]
        for ea, eb in zip(ra['events'], rb['events']):
            ta, tb = next_action(ea)[0], next_action(eb)[0]
            if ta != tb and ea['id'] != inc:
                body.append([name, ea['id'], ', '.join(ta) or '없음', ', '.join(tb) or '없음'])
    lines.append(CR.md_table(['지점', '경보', '가의 1위', '나의 1위'], body or [['—', '없음', '', '']]))
    expected['지점이_바꾸는_사례'] = body
    lines += ['', '## 손계산 — 구성안 4절 설계 목표와 실행 값', '',
              CR.md_table(['후보', '설계 예측 ℃', '실행 예측 ℃', '설계 합계', '손계산(아는 값)', '엔진', '생성기', '손계산 성분(만원)'], hand_rows), '',
              '## 조건 랩 갈래 — 지점2(트립 · 예측 65 이상 사례에서 갈린다, 사건은 같다)', '']
    body = []
    for key, v in chain_rec.items():
        body.append([key, ', '.join(v['모두_제외']) or '없음', ' · '.join(f'{s[-2:]} {st}' for s, st in v['트립_사례'].items()), ' · '.join(f'{s[-2:]} {st}' for s, st in v['예측65_사례'].items())])
    lines.append(CR.md_table(['조건표 갈래 → 판정 랩', '모두 제외 사례', f'트립 사례 {TRIP_CASE}', f'예측 65 이상 사례 {HOT_CASE}'], body))
    lines += ['', '지점2 가는 옛 규칙 R4 · R5를 대상 빈칸 그대로 작업지시 후보(SOP-COOL-14)에도 건다 — 조건표의 이유 칸이 「작업지시는 제어 명령이 아니어서 이 이유와 맞지 않는다」를 밝힌다. '
              '판정 랩의 모두 제외 사례는 이 갈래(판정 랩 입력)에서만 생긴다.', '',
              '## 조건 랩 갈래 — 지점1(통합 03-2, 적용 범위)', '',
              CR.md_table(['갈래', 'HYD-04', '설비보전팀장의 다음 행동'], [
                  ['가', '뺐음 — 수냉식 후속형, HM-8에 범위 문장 없음', 'HYD-04 냉각 경보에는 판단 시스템 후보를 올리지 않고 제조사에 HPP-45B 냉각 정비 지침을 요청'],
                  ['나', 'SOP-COOL-13(4단계 확인 필요) · 15와 냉각 성능 판정을 건다', 'HYD-04 냉각 경보에 부하 감산 · 환기 후보를 올리고, 열교환기 세척 SOP를 만들도록 정비 기술 담당에 요청']])]
    write(HERE/'사건_갈래표.md', '\n'.join(lines) + '\n')


def main():
    global DC_META, TRIP_CASE, HOT_CASE
    files, DC_META = DC.build()
    meta_file = json.loads((HERE/'원자료_메타.json').read_text(encoding='utf-8'))
    if meta_file != json.loads(json.dumps(DC_META, ensure_ascii=False)):
        fail('원자료_메타.json이 지금 생성기 판과 다름 — build_judgement_labs.py로 다시 만든다')
    cats = {c['id']: c['categories'] for c in DC_META['cases']}
    TRIP_CASE = next(cid for cid, k in cats.items() if '트립' in k)
    HOT_CASE = next(cid for cid, k in cats.items() if '운전 중 예측 65 이상' in k)
    if BRANCHES.exists():
        shutil.rmtree(BRANCHES)
    expected = {'원자료_판': {'seed': DC_META['seed'], '사건': DC_META['incident'], '사례_수': len(DC_META['cases'])}}
    print('1. 자료 · 입력 바이트')
    same_bytes(files)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        print('2. 조건 랩 갈래(통합 03-2 6 · 실전 02-5 3)와 학생 검사기')
        checks = condition_branches(files, tmp, expected)
        print('3. 판정 갈래 4와 학생 검사기')
        judged = judge_branches(tmp, expected)
        print('   랩 사슬: 조건 랩 강사 참조 갈래 → 판정 랩 입력')
        chain_rec = chain(tmp, expected)
        print('4. 두 번째 구현 대조')
        engine = {}
        for p2 in CR.P2:
            lab = copy_lab('integrated-03-judge', tmp/f'oracle_{p2}')
            shutil.copy(BRANCHES/f'조치기준_가-{p2}'/'조건표.csv', lab/'입력/조건표.csv')
            for pol in POLICIES:
                engine[(p2, pol)] = J.run(lab, policy=jp(pol))
        n1 = oracle_compare(DC_META, engine)
        n2 = oracle_check_cases(DC_META, checks)
        print(f'   판정 · 비교 · 순위 {n1}건(지점2 3 × 지점3 · 4 4 × 사례 {len(DC_META["cases"])} × 후보 4), 확인 사례 판정 {n2}건')
        expected['두_번째_구현'] = {'판정_랩_후보': n1, '확인_사례_후보': n2, '불일치': len([f for f in failures if f.startswith('oracle')])}
        print('5. 손계산')
        hand_rows, recomputed = hand_check(files['사건_기록_HYD-02_1027.md'], judged[BASE_POLICY][0], DC_META, expected)
        print('6. 검사기 고의 손상')
        checker_trials(tmp, judged)
        caught = sum(1 for t in TRIALS if not t['통과_기대'] and t['기대대로'])
        damaged = sum(1 for t in TRIALS if not t['통과_기대'])
        print(f'   손상 {damaged}건 중 {caught}건 잡음, 통과해야 할 입력(강사 참조 · 내 입력 폴더) {sum(1 for t in TRIALS if t["통과_기대"] and t["기대대로"])}/{sum(1 for t in TRIALS if t["통과_기대"])}')
        print('8. 학생용 완성본(기본 갈래) 묶기 · 새 폴더에서 다시 실행')
        for name, r in build_completed(tmp, judged, checks, memo_inputs(files['사건_기록_HYD-02_1027.md']), expected).items():
            print(f'   {r["경로"]} · 파일 {r["파일수"]}개 · {r["sha256"][:12]} · {r["검사기"]}')
    dump(HERE/'검사기_확인.json', TRIALS)
    print('7. 학생 폴더 경계')
    inc_tot = [v for s, v in ((s, d['합계'] if d['합계'] is not None else d['아는_값_합계']) for s, d in DC_META['incident_totals'].items())]
    boundary(inc_tot)
    incident_table(judged, hand_rows, recomputed, chain_rec, expected)
    expected['실패'] = failures
    dump(HERE/'expected_results.json', expected)
    print(f'갈래 {len(list(BRANCHES.iterdir()))}개 폴더(조치 기준 6 · 조건표 3 · 판정 기본 1) + 판정 갈래 4(expected_results.json)')
    print('완료 — 불일치 0' if not failures else f'불일치 {len(failures)}건')
    return 0 if not failures else 1


DC_META, TRIP_CASE, HOT_CASE = None, None, None

if __name__ == '__main__':
    sys.exit(main())
