"""새 프로젝트 구조(build_session3_projects.py)의 냉각 경보 조치 판단 네 랩 — 강사 참조 갈래 · 랩 사슬 · 검사기 고의 손상 · 완성본 새 폴더 실행 · 옛 판 대조. 학생 ZIP에 넣지 않는다.

사용: HYD_MAIN_ROOT=<main 체크아웃> python project_trials.py <네 프로젝트가 든 --dest 폴더> --out <판정 폴더>
기준은 기존 강사 참조와 같다: 같은 생성기 정의로 임시 폴더에 기존 구조 랩을 만들고, 같은 갈래를 기존 엔진(criteria.py · judge_actions.py · 기존 제공 코드)과
새 프로젝트의 학생 경로(app/features 채움 → python run.py <기능>)로 각각 돌려, 경로 · 파일 이름 변환 말고는 결과가 같은지 본다.
1. 옛 판 대조: 원자료 · 빈 틀 · 제공 코드 · 검사기 본문이 기존 정의를 변환한 것과 같은 바이트인가, 설비 모델이 통합02 그래프 랩 제공 모델과 같은 바이트인가.
2. 조치 기준 갈래 6(지점1 × 지점2) · 조건표 갈래 3: SOP 구조의 뜻(run_reference.sop_meaning)과 사례 판정이 기존 엔진과 같은가, 검사기가 통과시키는가.
3. 판정 갈래 4(지점3 × 지점4) × 두 랩: output/judgement.json · action_review.json · .md가 judge_actions.py 출력의 변환과 같은 바이트인가. 랩 사슬(조건 랩 갈래 → 내 입력).
4. 검사기 고의 손상(ID 중복 · 끝점 없음 · 관계 방향 · 계약 어긋남, 내 입력 포함). 5. 완성본을 새 폴더에 풀어 다시 실행. 6. 학생 폴더 경계 · 가이드 명령 · 토글.
어긋나면 「불일치」 줄을 찍고 종료 코드 1 — 결과를 맞추지 말고 원인을 고친다.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import copy
import csv
import hashlib
import html
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
import build_session3_projects as N  # noqa: E402
import run_reference as RR  # noqa: E402

BJ, CR, J, CT, SOP = N.BJ, N.CR, RR.J, RR.CT, RR.SOP
failures, report = [], {}
_ns = {}
exec(N.SHORT_SRC, _ns)
short = _ns['short']          # 새 결과 화면의 판정 한 칸 표기(기존 condition_tools.short의 뜻 그대로, 사유 낱말 겹침만 뺌)
CANDIDATES = ['SOP-COOL-11', 'SOP-COOL-12', 'SOP-COOL-13', 'SOP-COOL-14']


def fail(msg):
    failures.append(msg)
    print('불일치:', msg)


def sha(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode('utf-8')).hexdigest()


def run(folder, *args):
    p = subprocess.run([sys.executable, '-B', *args], cwd=folder, capture_output=True, text=True, encoding='utf-8', errors='replace',
                       env={'PYTHONUTF8': '1', 'PATH': '/usr/bin:/bin', 'SYSTEMROOT': 'C:\\Windows'})
    return p.returncode, (p.stdout + p.stderr).strip()


def feature(folder, cmd):
    code, out = run(folder, 'run.py', cmd, '--no-open')
    if code:
        fail(f'{folder.name}: python run.py {cmd} exit {code}\n{out[:1500]}')
    return json.loads((folder/'output/result.json').read_text(encoding='utf-8'))['blocks']


def check(folder):
    return run(folder, '-m', 'app.utils.check')


def table_rows(blocks, title):
    b = next((b for b in blocks if b.get('title') == title), None)
    if b is None:
        fail(f'결과 화면에 「{title}」 표가 없음')
        return []
    return [[str(x) for x in r] for r in b['rows']]


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8', newline='\n')


def fresh(src, tmp, name):
    dst = Path(tmp)/name/src.name
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns('output', '__pycache__'))
    return dst


def cases_judged(lab, kinds):
    """기존 구조 랩에서 사건 · 확인 사례 판정(기존 결과 화면 judged와 같은 계산) → {(사례, 후보): 판정 dict}."""
    groups = CT.load_table(lab/'결과/조건표.csv')
    memo = (lab/'자료'/BJ.MEMO).read_text(encoding='utf-8')
    cases = CT.case_inputs(lab/'자료/확인_사례.csv', kinds)
    incident = next(cid for cid in cases if cid in memo)
    out = {(incident, s): CT.evaluate(s, x, groups) for s, x in CT.memo_inputs(memo, kinds).items()}
    out.update({(cid, s): CT.evaluate(s, x, groups) for cid, cs in cases.items() if cid != incident for s, x in cs.items()})
    return out


# ───────────── 1. 옛 판 대조 ─────────────
def parity(dest, olds, files):
    rec = {}
    for key, (old, L) in olds.items():
        conv, folder = N.converter(key), dest/N.PROJECT[key]
        r = rec[N.PROJECT[key]] = {'원자료': {}, '빈 틀': {}, '제공 코드': {}}
        raw = N.converter(key, prose=False)
        for name, core in BJ.DATA[key]:
            p = folder/'data'/raw(name)
            same = p.is_file() and p.read_text(encoding='utf-8') == raw(files[core])
            r['원자료'][name + ' → ' + p.relative_to(folder).as_posix()] = {'옛 sha256': sha(files[core])[:16], '새 sha256': sha(p.read_bytes())[:16], '변환과 같음': same}
            if not same:
                fail(f'{folder.name}: {p.relative_to(folder)}이 원자료 코어 {core}의 변환과 다름')
        for name, text in L['files'].items():
            if name.startswith('결과/') and not name.endswith('README.md'):
                p = folder/conv(name)
                same = p.is_file() and p.read_text(encoding='utf-8') == conv(text)
                r['빈 틀'][name + ' → ' + conv(name)] = {'옛 sha256': sha(text)[:16], '새 sha256': sha(p.read_bytes())[:16] if p.is_file() else None, '변환과 같음': same}
                if not same:
                    fail(f'{folder.name}: 빈 틀 {conv(name)}이 기존 {name}의 변환과 다름')
        for name in BJ.PROVIDED[key]:
            old_text = (BJ.PROVIDED_SRC/name).read_text(encoding='utf-8')
            new_text = (folder/'app/utils'/name).read_text(encoding='utf-8')
            changed = [(a, b) for a, b in zip(old_text.splitlines(), new_text.splitlines()) if a != b]
            only_paths = len(old_text.splitlines()) == len(new_text.splitlines()) and all(
                conv(a).replace('from condition_tools import', 'from app.utils.condition_tools import') == b for a, b in changed)
            r['제공 코드'][name] = {'줄 수': len(new_text.splitlines()), '바뀐 줄': len(changed), '바뀐 줄이 경로 · 이름 변환뿐': only_paths}
            if not only_paths:
                fail(f'{folder.name}: 제공 코드 {name}에 경로 · 이름 변환 밖의 변경')
        doc, parts = BJ.CHECKS[key]
        body = conv(''.join(parts))
        for a, b in N.check_messages(key):     # 안내 글 셋만 바꾼다(판정 줄은 그대로)
            body = body.replace(a, b)
        r['검사기 본문'] = {'기존 본문 변환이 새 check.py에 그대로 있음': body in (folder/'app/utils/check.py').read_text(encoding='utf-8'), '본문 줄 수': len(body.splitlines())}
        if not r['검사기 본문']['기존 본문 변환이 새 check.py에 그대로 있음']:
            fail(f'{folder.name}: 검사기 본문이 기존 알고리즘의 변환과 다름')
        if key == 'integrated-03-criteria':
            graph_lab = N.F.OUT/'통합반/실습/02회차/랩/graph-lab/data/model'
            r['설비 모델'] = {n: {'sha256': sha((folder/'data/model'/n).read_bytes())[:16],
                                 '통합02 graph-lab 제공 모델과 같은 바이트': (graph_lab/n).is_file() and (graph_lab/n).read_bytes() == (folder/'data/model'/n).read_bytes()}
                             for n in ('schema.json', 'graph.json')}
            old_graph = json.loads((old/'입력/graph.json').read_text(encoding='utf-8'))
            r['설비 모델']['기존 입력/graph.json과 노드 · 관계 수'] = [len(old_graph['nodes']), len(old_graph['rels'])]
    report['옛_판_대조'] = rec


# ───────────── 2. 조치 기준 · 조건표 갈래 ─────────────
def criteria_branches(dest, olds, tmp):
    key = 'integrated-03-criteria'
    conv, starter, (old0, _) = N.converter(key), dest/N.PROJECT[key], olds[key]
    rec = {}
    for p1 in CR.P1:
        for p2 in CR.P2:
            name = f'{p1}-{p2}'
            raw = {'결과/조건_분류.csv': CR.csv_text(CR.CLASS_HEADER, CR.classify_rows(p2)), '결과/관계.csv': CR.csv_text(CR.REL_HEADER, CR.relation_rows()),
                   '결과/설비_연결_기준.csv': CR.csv_text(CR.LINK_HEADER, CR.link_rows(p1)), '결과/조건표.csv': CR.table_csv(p2)}
            new = fresh(starter, tmp, f'criteria_{name}')
            old = Path(tmp)/f'criteria_old_{name}'/old0.name
            shutil.copytree(old0, old)
            for rel, text in raw.items():
                write(new/conv(rel), conv(text))
                write(old/rel, text)
            feature(new, 'classify')
            got = RR.sop_meaning(json.loads((new/'output/sop.json').read_text(encoding='utf-8')))
            want = RR.sop_meaning(json.loads(conv(json.dumps(CR.sop_doc(p1, p2), ensure_ascii=False))))
            diff = [k for k in want if got.get(k) != want[k]]
            if diff:
                fail(f'조치 기준 갈래 {name}: 새 sop.json의 뜻이 criteria.sop_doc과 다름 {diff}')
            blocks = feature(new, 'provenance')
            doc, _, _ = SOP.build(old)
            by = {s['id']: s for s in doc['sops']}
            kinds = {c: (by[c]['kind'], by[c]['codes']) if c in by else (None, []) for c in CANDIDATES}
            want_rows = [[c, s, conv(short(v))] for (c, s), v in cases_judged(old, kinds).items()]
            got_rows = table_rows(blocks, '사례 · 후보마다 판정')
            if got_rows != want_rows:
                fail(f'조치 기준 갈래 {name}: 사례 판정이 기존 엔진과 다름 {[(a, b) for a, b in zip(got_rows, want_rows) if a != b][:3]}')
            code, out = check(new)
            if code:
                fail(f'조치 기준 갈래 {name}: 검사기 exit {code}\n{out[:1500]}')
            st = [r[2].split(' ')[0] for r in got_rows]
            rec[name] = {'sop 뜻 다름': diff, '사례 판정 기존과 같음': got_rows == want_rows, '판정 수': {w: sum(x.startswith(w) for x in st) for w in ('유지', '제외', '보류')},
                         '검사기': f'exit {code}'}
    report['조치_기준_갈래'] = rec

    key = 'practical-02-conditions'
    conv, starter, (old0, _) = N.converter(key), dest/N.PROJECT[key], olds[key]
    rec = {}
    targets = {r['sop_id']: (r['kind'], [x for x in r['codes'].split(';') if x]) for r in CT.read_csv(old0/'자료/targets.csv')}
    for p2 in CR.P2:
        raw = {'결과/조건표.csv': CR.table_csv(p2), '결과/승인.csv': CR.csv_text(CR.APPROVAL_HEADER, CR.approval_rows())}
        new = fresh(starter, tmp, f'conditions_{p2}')
        old = Path(tmp)/f'conditions_old_{p2}'/old0.name
        shutil.copytree(old0, old)
        for rel, text in raw.items():
            write(new/conv(rel), conv(text))
            write(old/rel, text)
        blocks = feature(new, 'rules')
        want_rows = [[c, s, conv(short(v))] for (c, s), v in cases_judged(old, targets).items()]
        got_rows = table_rows(blocks, '사건 · 확인 사례 — 후보마다 맞은 규칙과 알 수 없는 규칙')
        if got_rows != want_rows:
            fail(f'조건표 갈래 {p2}: 사례 판정이 기존 엔진과 다름')
        feature(new, 'approvals')
        code, out = check(new)
        if code:
            fail(f'조건표 갈래 {p2}: 검사기 exit {code}\n{out[:1500]}')
        rec[p2] = {'사례 판정 기존과 같음': got_rows == want_rows, '사례 · 후보 줄': len(got_rows), '검사기': f'exit {code}'}
    report['조건표_갈래'] = rec


# ───────────── 3. 판정 갈래와 랩 사슬 ─────────────
def judge_fill(new, conv, pol):
    gap, warned = RR.jp(pol)
    write(new/'app/features/gap_rule.py', conv(BJ.gap_file(gap)))
    write(new/'app/features/compare_rule.py', conv(BJ.compare_file(warned)))
    write(new/'app/features/decisions.csv', conv(BJ.chosen_csv([list(r[:4]) for r in J.choice_rows(gap, warned)])))


def judge_branches(dest, olds, tmp):
    rec = {}
    sop_doc = json.loads(CR.sop_json(*CR.BASE))
    for pol in RR.POLICIES:
        name = '-'.join(pol)
        for key, cmd in (('integrated-03-judge', 'write'), ('practical-03-review', 'compare')):
            conv, starter, (old, _) = N.converter(key), dest/N.PROJECT[key], olds[key]
            res = J.run(old, policy=RR.jp(pol))
            new = fresh(starter, tmp, f'{key}_{name}')
            judge_fill(new, conv, pol)
            feature(new, cmd)
            if key == 'integrated-03-judge':
                want = {'output/judgement.json': conv(json.dumps(J.student_view(res), ensure_ascii=False, indent=1) + '\n')}
            else:
                rv = J.review(res, sop_doc, J.load_table(old/'입력/조건표.csv'))
                want = {'output/action_review.json': conv(json.dumps(rv, ensure_ascii=False, indent=1) + '\n'), 'output/action_review.md': conv(J.review_md(rv))}
            same = {rel: (new/rel).is_file() and (new/rel).read_text(encoding='utf-8') == text for rel, text in want.items()}
            for rel, ok in same.items():
                if not ok:
                    fail(f'판정 갈래 {name} {N.PROJECT[key]}: {rel}이 judge_actions.py 출력의 변환과 다름')
            code, out = check(new)
            if code:
                fail(f'판정 갈래 {name} {N.PROJECT[key]}: 검사기 exit {code}\n{out[:1500]}')
            top = {e['id']: [r['sop'] for r in e['ranking'] if r['rank'] == 1] for e in res['events']}
            rec[f'{N.PROJECT[key]} {name}'] = {'기존 출력 변환과 같은 바이트': same, '검사기': f'exit {code}', '경보 수': len(res['events']),
                                               '1위가 있는 경보 수': sum(1 for v in top.values() if v)}
    report['판정_갈래'] = rec


def chain(dest, olds, tmp):
    rec = {}
    pairs = [('integrated-03-judge', p1, p2) for p1 in CR.P1 for p2 in CR.P2] + [('practical-03-review', None, p2) for p2 in CR.P2]
    for key, p1, p2 in pairs:
        conv, starter, (old0, _) = N.converter(key), dest/N.PROJECT[key], olds[key]
        name = f'{p1}-{p2}' if p1 else p2
        old = Path(tmp)/f'chain_old_{key}_{name}'/old0.name
        shutil.copytree(old0, old)
        mine = {'조건표.csv': CR.table_csv(p2)}
        if p1:
            mine['sop.json'] = CR.sop_json(p1, p2)
        for n, text in mine.items():
            write(old/'결과/내_입력'/n, text)
        res = J.run(old, old/'결과/내_입력/조건표.csv', policy=J.BASE_POLICY)
        new = fresh(starter, tmp, f'chain_{key}_{name}')
        for n, text in mine.items():
            write(new/'app/features/criteria'/N.converter(key)(n), conv(text))
        judge_fill(new, conv, RR.BASE_POLICY)
        feature(new, 'write' if key == 'integrated-03-judge' else 'compare')
        if key == 'integrated-03-judge':
            ok = (new/'output/judgement.json').read_text(encoding='utf-8') == conv(json.dumps(J.student_view(res), ensure_ascii=False, indent=1) + '\n')
        else:
            rv = J.review(res, json.loads((old/'입력/sop.json').read_text(encoding='utf-8')), J.load_table(old/'결과/내_입력/조건표.csv'))
            ok = (new/'output/action_review.json').read_text(encoding='utf-8') == conv(json.dumps(rv, ensure_ascii=False, indent=1) + '\n')
        code, out = check(new)
        if not ok:
            fail(f'랩 사슬 {name} → {N.PROJECT[key]}: 내 입력으로 낸 결과가 기존 엔진 출력의 변환과 다름')
        if code or 'app/features/criteria/condition_table.csv (내 입력)' not in out:
            fail(f'랩 사슬 {name} → {N.PROJECT[key]}: 검사기 exit {code} 또는 내 입력을 기준으로 보지 않음\n{out[:1200]}')
        rec[f'{"통합 " + name if p1 else "실전 " + name} → {N.PROJECT[key]}'] = {'기존 출력과 같음': ok, '검사기': f'exit {code}'}
    report['랩_사슬'] = rec


# ───────────── 4. 검사기 고의 손상 ─────────────
def edit_json(path, fn):
    d = json.loads(path.read_text(encoding='utf-8'))
    fn(d)
    path.write_text(json.dumps(d, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


def edit_csv(path, fn):
    lines = path.read_text(encoding='utf-8').splitlines(keepends=True)
    head = [l for l in lines if l.lstrip().startswith('#')]
    rows = list(csv.reader(io.StringIO(''.join(l for l in lines if not l.lstrip().startswith('#')))))
    rows = fn(rows)
    buf = io.StringIO()
    csv.writer(buf, lineterminator='\n').writerows(rows)
    path.write_text(''.join(head) + buf.getvalue(), encoding='utf-8')


def swap_first(d, kind):
    r = next(r for r in d['relations'] if r['type'] == kind)
    r['from'], r['to'] = r['to'], r['from']


def first_kept(d):
    return next(c for e in d['events'] for c in e['candidates'] if c.get('comparison'))


def damages():
    def cut_node(path):
        def fn(d):
            d['nodes'] = [n for n in d['nodes'] if n['props']['id'] != 'HYD-01:fan']
        return fn
    return {
        'action-criteria-lab': [
            ('고장 유형 ID 중복', lambda f: edit_json(f/'output/sop.json', lambda d: d['failure_modes'].append(dict(d['failure_modes'][0]))), '번 있습니다'),
            ('SOP ID 중복', lambda f: edit_json(f/'output/sop.json', lambda d: d['sops'].append(copy.deepcopy(d['sops'][0]))), '1번이어야 합니다'),
            ('관계 끝점 없음', lambda f: edit_json(f/'output/sop.json', lambda d: d['relations'][0].update(to='cause:none')), '에 없습니다'),
            ('관계 방향 거꾸로', lambda f: edit_json(f/'output/sop.json', lambda d: swap_first(d, 'MITIGATED_BY')), '시작'),
            ('모델에 없는 ID', lambda f: edit_json(f/'output/sop.json', lambda d: d['sops'][0]['model_refs']['assets'].append('HYD-99')), '모델에 없는 ID'),
            ('조건표 경계 표시 어긋남', lambda f: edit_csv(f/'app/features/condition_table.csv', lambda rs: [rs[0]] + [[*r[:8], '아니오' if r[5] in ('>=', '<=') else r[8], *r[9:]] for r in rs[1:]]), 'boundary_included'),
            ('내 모델에서 쓰인 ID가 빠짐', lambda f: (shutil.copytree(f/'data/model', f/'app/features/model'), edit_json(f/'app/features/model/graph.json', cut_node(None))), '모델에 없는 ID HYD-01:fan'),
        ],
        'condition-table-lab': [
            ('승인 후보 중복', lambda f: edit_csv(f/'app/features/approvals.csv', lambda rs: rs + [rs[1]]), '두 줄 이상'),
            ('계약에 없는 입력', lambda f: edit_csv(f/'app/features/condition_table.csv', lambda rs: [rs[0], [*rs[1][:4], 'forecast_ts9', *rs[1][5:]], *rs[2:]]), '계약에 없는 input'),
            ('조건표 경계 표시 어긋남', lambda f: edit_csv(f/'app/features/condition_table.csv', lambda rs: [rs[0]] + [[*r[:8], '아니오' if r[5] in ('>=', '<=') else r[8], *r[9:]] for r in rs[1:]]), 'boundary_included'),
        ],
        'judgement-lab': [
            ('경보 중복', lambda f: edit_json(f/'output/judgement.json', lambda d: d['events'].append(copy.deepcopy(d['events'][0]))), 'RAISE 행과 사례'),
            ('후보 순서 바뀜', lambda f: edit_json(f/'output/judgement.json', lambda d: d['events'][0]['candidates'].reverse()), '후보 목록 · 순서'),
            ('합계 어긋남', lambda f: edit_json(f/'output/judgement.json', lambda d: first_kept(d)['comparison'].update(total=first_kept(d)['comparison']['total'] + 5)), '합계 total'),
            ('내 조건표의 규칙 이름이 다름', lambda f: write(f/'app/features/criteria/condition_table.csv', (f/'data/criteria/condition_table.csv').read_text(encoding='utf-8').replace('R1,', 'R1x,')), '기준 조건표에 없는 규칙'),
        ],
        'action-review-lab': [
            ('경보 절 제목 없음', lambda f: write(f/'output/action_review.md', re.sub(r'^## .*$', '## 절', (f/'output/action_review.md').read_text(encoding='utf-8'), flags=re.M)), '절 제목이 없습니다'),
            ('승인 역할 어긋남', lambda f: edit_json(f/'output/action_review.json', lambda d: d['events'][0]['candidates'][0]['approval'].update(role='아무개')), '승인 역할'),
            ('경보 중복', lambda f: edit_json(f/'output/action_review.json', lambda d: d['events'].append(copy.deepcopy(d['events'][0]))), 'RAISE 행과 사례'),
        ],
    }


def checker_trials(done, tmp):
    rec = {}
    for name, trials in damages().items():
        base = done[name]
        code, out = check(base)
        rec[name] = {'손상 없음': f'exit {code}'}
        if code or '구조 검사 통과' not in out:
            fail(f'{name} 완성본: 손상 전 검사기 통과 아님\n{out[:1200]}')
        for label, damage, needle in trials:
            f = Path(tmp)/'damage'/name/re.sub(r'\W+', '_', label)/name
            shutil.copytree(base, f)
            damage(f)
            code, out = check(f)
            caught = code != 0 and needle in out
            rec[name][label] = {'exit': code, '잡음': caught, '찾은 줄': next((l.strip() for l in out.splitlines() if needle in l), '')}
            if not caught:
                fail(f'{name} 손상 「{label}」: 검사기가 잡지 않음(exit {code})\n{out[:1200]}')
    report['검사기_고의_손상'] = rec


# ───────────── 5. 완성본 새 폴더 실행 ─────────────
def completed_runs(dest, tmp):
    done, rec = {}, {}
    for key, project in N.PROJECT.items():
        archive = dest/(project + '-completed.zip')
        target = Path(tmp)/'completed_fresh'
        with zipfile.ZipFile(archive) as z:
            z.extractall(target)
            packed = {n: z.read(n) for n in z.namelist() if n.startswith(project + '/output/')}
        folder = target/project
        shutil.rmtree(folder/'output')
        outs = {}
        for cmd in N.RUNS[key]:
            code, out = run(folder, 'run.py', cmd, '--no-open')
            outs[cmd] = code
            if code:
                fail(f'{project} 완성본 새 폴더: python run.py {cmd} exit {code}\n{out[:1200]}')
        same = {n.split('/', 1)[1]: (folder/n.split('/', 1)[1]).read_bytes() == data for n, data in packed.items()}
        for n, ok in same.items():
            if not ok and not n.endswith(('result.html', 'result.json')):
                fail(f'{project} 완성본 새 폴더: 다시 실행한 {n}이 동봉한 파일과 다름')
        marks = []
        for cmd in [c for c in N.RUNS[key] if c not in ('check',)]:
            text = json.dumps(feature(folder, cmd), ensure_ascii=False)
            marks.append((cmd, text.count('"다름"') + text.count('"실제 없음"')))
        code, out = check(folder)
        if code or '구조 검사 통과' not in out:
            fail(f'{project} 완성본 새 폴더: 검사기 통과 아님\n{out[:1200]}')
        rec[project] = {'zip sha256': sha(archive.read_bytes()), '명령 exit': outs, '동봉 결과와 같은 바이트': same, '기대 ↔ 실제 다른 줄': dict(marks), '검사기': f'exit {code}'}
        done[project] = folder
    report['완성본_새_폴더'] = rec
    return done


# ───────────── 6. 학생 폴더 경계 · 가이드 · 사람 분 ─────────────
def boundary_and_guide(dest, olds):
    rec = {}
    for key, project in N.PROJECT.items():
        folder, r = dest/project, {}
        hits = []
        for p in sorted(folder.rglob('*')):
            rel = p.relative_to(folder).as_posix()
            if not p.is_file() or rel.startswith('data/criteria/') or (rel.startswith('data/') and p.suffix == '.csv'):
                continue
            if p.name in RR.REFERENCE_NAMES:
                hits.append(f'{rel}: 강사 참조 파일 이름')
            text = p.read_text(encoding='utf-8-sig')
            hits += [f'{rel}: 「{w}」' for w in RR.LAB_ANSWERS[key] if w in text]
            hits += [f'{rel}: 「{w}」' for w in ('reference', '강사 참조', '완성본 위치') if w in text]
        r['경계 위반'] = hits
        for h in hits:
            fail(f'{project}: 학생 폴더 경계 {h}')
        guide = (dest/(project + '_guide.html')).read_text(encoding='utf-8')
        sections = re.findall(r'<section id="s\d+"><h2>\d+ (.*?)</h2>(.*?)</section>', guide, re.S)
        commands = set(re.findall(r"^\s+'([a-z]+)': \(", (folder/'app/utils/actions.py').read_text(encoding='utf-8'), re.M))
        steps = []
        for name, body in sections:
            used = re.findall(r'python run\.py(?: ([a-z]+))?', html.unescape(body))
            bad = [c for c in used if c and c not in commands]
            if bad:
                fail(f'{project} 가이드 「{html.unescape(name)}」: 없는 기능 {bad}')
            steps.append({'단계': html.unescape(name), '명령': sorted({('python run.py ' + c).strip() for c in used}), '정답 토글': body.count('class="answer"')})
        r['가이드 단계'] = steps
        r['복사 블록 · 단추'] = [guide.count('class="block '), guide.count('class="copy"')]
        first_block = guide.find('class="block ')
        r['첫 블록 앞에 손으로 치지 않는 까닭'] = '오타를 줄이도록' in guide[:first_block]
        r['링크'] = re.findall(r'href="([^"#][^"]*)"', guide)
        L = olds[key][1]
        rows = ev = 0
        for rel, text in N.base_answers(key, L).items():
            if rel.endswith('.csv'):
                body = [x for x in text.splitlines() if x.strip() and not x.lstrip().startswith('#')]
                rows += max(len(body) - 1, 0)
                ev += max(len(body) - 1, 0) if body and '근거' in body[0].split(',') else 0
        cost = N.F.guide_cost(guide)
        r['사람 분(K-1)'] = {'토글 밖 글자 · 명령 · AI 요청 힌트': [cost['글자'], cost['명령'], cost['AI_대기_출처']],
                            '기본 갈래 채움의 손 행 · 근거 행': [rows, ev], '손 행 · 근거 행 분': round(rows * N.F.ROW_MIN + ev * N.F.EVIDENCE_MIN, 1)}
        rec[project] = r
    report['경계_가이드'] = rec


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('dest', type=Path)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    dest = a.dest.resolve()
    files, _ = N.DC.build()
    N.WORK.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=N.WORK, prefix='trials-') as tmp:
        tmp = Path(tmp)
        olds = {}
        for key in N.PROJECT:
            old = tmp/'old'/BJ.LABS[key].name
            olds[key] = (old, N.old_lab(key, files, old))
        parity(dest, olds, files)
        criteria_branches(dest, olds, tmp)
        judge_branches(dest, olds, tmp)
        chain(dest, olds, tmp)
        done = completed_runs(dest, tmp)
        checker_trials(done, tmp)
        boundary_and_guide(dest, olds)
    report['불일치'] = failures
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out/'project_trials.json').write_text(json.dumps(report, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(f'불일치 {len(failures)}건 — {a.out/"project_trials.json"}')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
