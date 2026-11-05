"""2회차 네 랩 「정답 보기」 재생 — 가이드의 정답 토글 내용(apply)을 새 랩 사본에 단계 차례로 써 넣고 `python show_result.py`를 돌려,
단계마다 상태가 「채움」(오류 · 비어 있음 0)이 되고 그 결과가 강사 참조와 같은 답인지 본다(요청문 DoD 11). 강사 참조 영역이며 학생 ZIP에 넣지 않는다.

통합 02-3 = 토글로 만든 graph.json의 답(설비별 구성 요소 · 센서 태그, 물리량 묶음, 설비별 교체 부품, 품번 물음)이 갈래 A · B · C 기대 답과 같은지.
실전 02-3 = 토글로 만든 SUPPLIES가 갈래 A · B · ㄴ · ㄷ 참조 graph.json의 SUPPLIES와 같은지(쌍 · 속성 전부).
실습4 두 랩 = 실제 랩 DB(lab_db.py — Docker 필요)에서 적재 · 조회 · 수정이 오류 없이 돌고 결과 화면 대조 표가 모두 「같음」인지(--no-db면 건너뜀).
사용: python reference/session2_toggle_replay.py [--no-db] [--keep]   → reference/session2_정답재생.json
"""
from pathlib import Path
from collections import defaultdict
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent
sys.path.insert(0, str(TOOLS))
import build_labs as B            # noqa: E402
import data_session2 as D         # noqa: E402
import session2_answers as ANS    # noqa: E402

REPORT = HERE / 'session2_정답재생.json'
PY = sys.executable


def run_show(folder):
    p = subprocess.run([PY, 'show_result.py', '--no-open'], cwd=folder, capture_output=True, text=True, encoding='utf-8', errors='replace',
                       env={**os.environ, 'PYTHONUTF8': '1'})
    states = dict(re.findall(r'^(\d\d) .+?: (.+)$', p.stdout, re.M))
    return p.returncode, states, p.stdout + p.stderr


def apply(folder, files):
    for rel, text in files.items():
        (folder / rel).write_text(text, encoding='utf-8', newline='\n')


def replay(L, folder, override=None):
    """단계 차례로 apply → show_result. 단계마다 (번호, 그 단계 상태, 종료 코드). override = {경로: 글} 마지막에 덮어쓸 갈래."""
    log = []
    for i, s in enumerate(L['steps'], 1):
        if s.get('answer'):
            apply(folder, s['answer']['apply'])
        if override and i == len(L['steps']):
            apply(folder, override)
        rc, states, out = run_show(folder)
        log.append({'step': i, 'name': s['name'], 'state': states.get(f'{i:02d}'), 'rc': rc})
    rc, states, out = run_show(folder)
    return log, rc, states, out


def copy_lab(course, name, root):
    dest = root / f'{course}_{name}'
    shutil.copytree(B.OUT / course / '실습/02회차/랩' / name, dest)
    return dest


def design_answers(graph):
    """토글로 만든 통합 02-3 모델의 답 — verify_reference.expected와 같은 꼴(구성 요소는 기준 키로 바꿔 견줌)."""
    key_of = {v: k for k, v in B.CANON_NAME.items()} | {'수냉 열교환기': 'cooler'}
    label = {n['props']['id']: n['labels'][0] for n in graph['nodes']}
    props = {n['props']['id']: n['props'] for n in graph['nodes']}
    owner, by = {}, defaultdict(list)
    for r in graph['rels']:
        by[r['type']].append(r)
        if r['type'] == 'HAS_COMPONENT':
            owner[r['b']] = r['a']
    sensors = defaultdict(lambda: defaultdict(list))
    for r in by['MONITORED_BY']:
        if label[r['a']] == 'Asset':
            sensors[r['a']]['(설비 전체)'].append(props[r['b']]['tag'])
        else:
            sensors[owner[r['a']]][key_of[props[r['a']]['name']]].append(props[r['b']]['tag'])
    qname = {v[0]: k for k, v in D.QUANTITIES.items()}
    members = defaultdict(set)
    for r in by['OBSERVES']:
        members[qname[props[r['b']]['name']]].add(r['a'])
    parts = defaultdict(dict)
    for r in by['HAS_COMPONENT']:
        parts[r['a']][key_of[props[r['b']]['name']]] = next((u['b'] for u in by['USES_PART'] if u['a'] == r['b']), None)
    return {'sensors_by_asset': {a: {k: sorted(v) for k, v in sorted(d.items())} for a, d in sorted(sensors.items())},
            'quantity_members': {k: sorted(v) for k, v in sorted(members.items())},
            'parts_by_asset': {a: dict(sorted(d.items())) for a, d in sorted(parts.items())},
            'same_item': sorted((r['a'], r['b']) for r in by['SAME_ITEM_AS'])}


def reference_answers(branch):
    _, graph = B.reference_model(False, branch)
    label = {n['props']['id']: n['labels'][0] for n in graph['nodes']}
    props = {n['props']['id']: n['props'] for n in graph['nodes']}
    owner, by = {}, defaultdict(list)
    for r in graph['rels']:
        by[r['type']].append(r)
        if r['type'] == 'HAS_COMPONENT':
            owner[r['b']] = r['a']
    sensors = defaultdict(lambda: defaultdict(list))
    for r in by['MONITORED_BY']:
        if label[r['a']] == 'Asset':
            sensors[r['a']]['(설비 전체)'].append(props[r['b']]['tag'])
        else:
            sensors[owner[r['a']]][r['a'].split(':', 1)[1]].append(props[r['b']]['tag'])
    members = defaultdict(set)
    for r in by['OBSERVES']:
        members[r['b']].add(r['a'])
    parts = defaultdict(dict)
    for r in by['HAS_COMPONENT']:
        parts[r['a']][r['b'].split(':', 1)[1]] = next((u['b'] for u in by['USES_PART'] if u['a'] == r['b']), None)
    return {'sensors_by_asset': {a: {k: sorted(v) for k, v in sorted(d.items())} for a, d in sorted(sensors.items())},
            'quantity_members': {k: sorted(v) for k, v in sorted(members.items())},
            'parts_by_asset': {a: dict(sorted(d.items())) for a, d in sorted(parts.items())},
            'same_item': sorted((r['a'], r['b']) for r in by['SAME_ITEM_AS'])}


def diff(a, b, path=''):
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b), key=str):
            out += [f'{path}/{k}: 한쪽에만 있음'] if (k not in a or k not in b) else diff(a[k], b[k], f'{path}/{k}')
        return out
    return [] if a == b else [f'{path}: 토글 {a!r} ≠ 참조 {b!r}']


def supply_rels(graph):
    return {(r['a'], r['b']): r['props'] for r in graph['rels'] if r['type'] == 'SUPPLIES'}


def main():
    no_db = '--no-db' in sys.argv
    report, bad = {}, []
    root = Path(tempfile.mkdtemp(prefix='s2replay-', dir=os.environ.get('HYD_REPLAY_DIR') or None))
    try:
        L = B.design_integrated()
        # 통합 02-3 — 갈래 A(토글 apply 그대로 — 관계.csv에 부품-부품 줄 없음), B(한 물품 · 이음 — 관계.csv 부품-부품 줄과 part_rules 갈래 B), C(따로 · 잇지 않음)
        b_files = ANS.integrated_design('B')
        for branch, override in [('A', None), ('B', {'결과/part_rules.py': b_files['결과/part_rules.py'], '결과/관계.csv': b_files['결과/관계.csv'], '결과/정한_것.csv': B.chosen_text(ANS.integrated_chosen('B'))}),
                                 ('C', {'결과/part_rules.py': ANS.part_rules_answer(False, False), '결과/정한_것.csv': B.chosen_text(ANS.integrated_chosen('C'))})]:
            folder = copy_lab('통합반', B.LAB3, root)
            folder = folder.rename(folder.with_name(folder.name + branch))
            log, rc, states, out = replay(L, folder, override)
            graph = json.loads((folder / '결과/graph.json').read_text(encoding='utf-8'))
            d = diff(design_answers(graph), reference_answers(branch))
            differ = len(re.findall(r'data-st="(다름|실제 없음|기대 밖)"', (folder / '결과/보기.html').read_text(encoding='utf-8'))) if branch == 'A' else 0
            ok = rc == 0 and all(x['state'] in ('채움', '볼 것 없음', '결과 보기') for x in log) and not d and differ == 0
            report[f'통합반/실습3/{branch}'] = {'steps': log, 'final_rc': rc, 'mismatch': d, 'compare_rows_not_same': differ}
            if not ok:
                bad.append(f'통합반/실습3/{branch}: rc {rc}, 상태 {[(x["step"], x["state"]) for x in log if x["state"] not in ("채움", "볼 것 없음", "결과 보기")]}, 불일치 {d[:5]}\n{out[-1500:]}')
        # 실전 02-3 — 갈래 ㄴ(apply), A · B · ㄷ(approval_rule 갈래)
        L = B.design_practical()
        for branch in ['ㄴ', 'A', 'B', 'ㄷ']:
            folder = copy_lab('실전반', B.LAB3, root)
            folder = folder.rename(folder.with_name(folder.name + branch))
            override = None if branch == 'ㄴ' else {'결과/approval_rule.py': ANS.approval_rule_answer(branch)}
            log, rc, states, out = replay(L, folder, override)
            graph = json.loads((folder / '결과/graph.json').read_text(encoding='utf-8'))
            mine, ref = supply_rels(graph), supply_rels(B.reference_model(True, branch)[1])
            d = diff({f'{a}→{b}': p for (a, b), p in mine.items()}, {f'{a}→{b}': p for (a, b), p in ref.items()})
            base_same = [n for n in graph['nodes'] if 'Supplier' not in n['labels']] == B.reference_model()[1]['nodes']
            differ = len(re.findall(r'data-st="(다름|실제 없음|기대 밖)"', (folder / '결과/보기.html').read_text(encoding='utf-8'))) if branch == 'ㄴ' else 0
            ok = rc == 0 and all(x['state'] in ('채움', '볼 것 없음', '결과 보기') for x in log) and not d and base_same and differ == 0
            report[f'실전반/실습3/{branch}'] = {'steps': log, 'final_rc': rc, 'mismatch': d, 'base_nodes_same': base_same, 'compare_rows_not_same': differ}
            if not ok:
                bad.append(f'실전반/실습3/{branch}: rc {rc}, 상태 {[(x["step"], x["state"]) for x in log if x["state"] not in ("채움", "볼 것 없음", "결과 보기")]}, 불일치 {d[:5]}\n{out[-1500:]}')
        if not no_db:
            for course in ['통합반', '실전반']:
                L = B.graph_lab(course)
                folder = copy_lab(course, B.LAB4, root)
                up = subprocess.run([PY, 'lab_db.py', '--no-open'], cwd=folder, capture_output=True, text=True, encoding='utf-8', errors='replace')
                if up.returncode:
                    bad.append(f'{course}/실습4: lab_db.py 실패 {up.stdout[-500:]} {up.stderr[-500:]}')
                    continue
                try:
                    log, rc, states, out = replay(L, folder)
                    page = (folder / '결과/보기.html').read_text(encoding='utf-8')
                    differ = len(re.findall(r'data-st="(다름|실제 없음|기대 밖)"', page))
                    ok = rc == 0 and all(x['state'] in ('채움', '볼 것 없음', '결과 보기') for x in log) and differ == 0
                    report[f'{course}/실습4'] = {'steps': log, 'final_rc': rc, 'compare_rows_not_same': differ}
                    if not ok:
                        bad.append(f'{course}/실습4: rc {rc}, 상태 {[(x["step"], x["state"]) for x in log if x["state"] not in ("채움", "볼 것 없음", "결과 보기")]}, 대조 다른 줄 {differ}\n{out[-2500:]}')
                finally:
                    state = json.loads((folder / '랩_연결.json').read_text(encoding='utf-8'))
                    subprocess.run(['docker', 'rm', '-f', '-v', state['container']], capture_output=True)
    finally:
        if '--keep' not in sys.argv:
            shutil.rmtree(root, ignore_errors=True)
        else:
            print('사본:', root)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    for k, v in report.items():
        print(k, 'rc', v['final_rc'], '불일치', len(v.get('mismatch', [])), '대조 다른 줄', v.get('compare_rows_not_same', '-'))
    if bad:
        print('\n'.join(bad))
        sys.exit('정답 재생 불일치')
    print('정답 재생: 모든 갈래에서 단계 상태 채움 · 강사 참조와 같은 답')


if __name__ == '__main__':
    main()
