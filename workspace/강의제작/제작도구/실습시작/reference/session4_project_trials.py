"""강사 참조 — 문서 지식 네 새 프로젝트(build_session4_projects.py)의 갈래 실행 · 검사기 고의 손상 · 받은 ZIP 첫 실행. 학생 폴더 · ZIP에 넣지 않는다. AI 호출 없음.

옛 구조의 강사 참조(reference/session3_docs/run_reference.py)와 같은 갈래(fills.py)와 같은 판정을 새 경로에서 돌린다:
1. 추출 갈래 — 두 반 × 지점5(가 · 나 · 다) × 지점6(가 · 나) = 12. 갈래마다 정할 자리(fills.py, 경로만 옮김)를 시작 폴더 사본에 넣고 run1 응답 기록으로
   `python run.py trial · extract · review · rules (· collect | other)`를 돌린다. 본다: R4의 맞는 정도 = 지점5의 뜻, 제조사 지침의 「사내 기준이 정하지 않은 항목」 줄의 결정 = 지점6의 뜻,
   검토 결과 구조 검사 통과, 그리고 옛 구조 갈래 산출(reference/session3_docs/갈래/추출_*)과 경로만 다르고 같은지(실행 시각 칸 빼고).
2. 그래프 갈래 — 두 반 × 지점7(가 · 나) = 4, 실제 Neo4j(사본마다 `python run.py db`, 끝나면 컨테이너를 지운다). 본다: 정기 점검표 지식이 핀 세척에 이어지는지 = 지점7의 뜻,
   같은 적재를 다시 해도 수가 같음, 검사기에서 기록 칸 말고 남은 것 0, 옛 구조 갈래의 내보내기(갈래/그래프_*/지식_내보내기.json)와 경로만 다르고 같은지.
3. 검사기 고의 손상 — 학생용 완성본(기본 갈래)을 풀어 손상 하나씩: `python run.py check`가 종료 코드 1과 그 손상의 글을 낸다.
4. 받은 시작 ZIP을 새 폴더에 풀어 `python run.py --no-open`이 오류 없이 결과 화면을 쓴다.
사용: python session4_project_trials.py <--dest 부모 폴더> [--out <판정 JSON>] [--skip-graph]
"""
from __future__ import annotations

from pathlib import Path
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent
sys.path[:0] = [str(TOOLS), str(HERE / 'session3_docs')]
import build_session4_projects as S  # noqa: E402
import fills as FL  # noqa: E402

OLD = HERE / 'session3_docs/갈래'
UNDEFINED_LINES = [105, 107, 114, 116]          # 제조사 지침에서 사내 기준이 정하지 않은 항목의 줄(run_reference.py와 같은 값)
BAD = []


def fail(msg):
    BAD.append(msg)
    print('불일치: ' + msg)


def run(folder, *args, ok=None):
    env = dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1')
    return subprocess.run([sys.executable, *args], cwd=folder, capture_output=True, text=True, encoding='utf-8', errors='replace', env=env, timeout=1800)


def same_text(a, b):
    return S.same_content(a, b)


def starter(parent, key):
    return parent / S.LABS[key]['course'] / S.LABS[key]['name']


def fresh_copy(src, dst):
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns('__pycache__', 'output'))
    return dst


def extract_branches(parent, tmp):
    rows = []
    for key in ('integrated-04-extract', 'practical-03-extract'):
        practical = key == 'practical-03-extract'
        course = S.LABS[key]['course']
        for p5 in FL.P5:
            for p6 in FL.P6:
                name = f'추출_{course}_{p5}-{p6}'
                folder = fresh_copy(starter(parent, key), tmp / name / S.LABS[key]['name'])
                S.seed_extract(folder)
                S.put_slots(folder, FL.extract_files(p5, p6, practical))
                try:
                    S.seed_trial(folder)
                    for action in ('trial', 'extract', 'review', 'rules') + (('collect',) if practical else ('other',)):
                        S.act(folder, action)
                except RuntimeError as e:
                    fail(f'{name}: {e}')
                    continue
                reviews = {p.name: json.loads(p.read_text(encoding='utf-8')) for p in sorted((folder / 'output/reviews').glob('*.json'))}
                r4 = [l['match'] for d in reviews.values() for l in d['rule_links'] if l['rule_id'] == 'R4']
                want = {'가': '일치', '나': '불일치', '다': '보류'}[p5]
                if r4 != [want]:
                    fail(f'{name}: R4 맞는 정도 {r4} — 지점5 {p5}는 {want}')
                oem = reviews.get('OEM-HPP45A-MM_C_review.json', {'candidates': []})
                got = sorted({c['decision'] for c in oem['candidates'] if c['line_start'] in UNDEFINED_LINES and c['decision'] != '제외'})
                want6 = ['보류'] if p6 == '가' else ['채택']
                if got != want6:
                    fail(f'{name}: 사내 기준이 정하지 않은 제조사 항목의 결정 {got} — 지점6 {p6}는 {want6}')
                c = run(folder, '-m', 'app.utils.check', *[f'output/reviews/{n}' for n in reviews])
                if c.returncode:
                    fail(f'{name}: 검토 결과 구조 검사 실패\n{c.stdout[-1500:]}')
                legacy = {}
                for p in sorted((OLD / name / '검토').glob('*.json')):
                    new = folder / 'output/reviews' / S.convert(p.name)
                    legacy[new.name] = new.is_file() and same_text(S.convert(p.read_text(encoding='utf-8')), new.read_text(encoding='utf-8'))
                if practical:
                    old_sel = OLD / name / '선택작업_조건.json'
                    legacy['selected_task.json'] = same_text(S.convert(old_sel.read_text(encoding='utf-8')), (folder / 'output/selected_task.json').read_text(encoding='utf-8'))
                if not legacy or not all(legacy.values()):
                    fail(f'{name}: 옛 구조 갈래 산출과 다름 {legacy}')
                counts = {}
                for d in reviews.values():
                    for x in d['candidates']:
                        counts[x['decision']] = counts.get(x['decision'], 0) + 1
                rows.append({'branch': name, 'R4': r4, 'undefined_oem': got, 'decisions': counts, 'check_rc': c.returncode, 'same_as_legacy': legacy})
                print(f'{name}: R4 {r4} · 제조사 미정 항목 {got} · 결정 {counts} · 옛 갈래와 같음 {all(legacy.values())}')
    return rows


def graph_branches(parent, tmp):
    rows = []
    for key in ('integrated-04-graph', 'practical-03-card'):
        practical = key == 'practical-03-card'
        course = S.LABS[key]['course']
        order = ['db', 'load', 'other'] + (['card', 'scope'] if practical else ['query', 'more', 'scope']) + ['export']
        for p7 in FL.P7:
            name = f'그래프_{course}_{p7}'
            folder = fresh_copy(starter(parent, key), tmp / name / S.LABS[key]['name'])
            S.put_slots(folder, FL.graph_files(p7, practical))
            try:
                for action in order:
                    S.act(folder, action)
                first = S.blocks(folder)
                again = [b for b in json.loads((folder / 'output/result.json').read_text(encoding='utf-8'))['blocks']]
                S.act(folder, 'other')
                diff = [b for b in S.blocks(folder) if b['kind'] == 'diff']
                if not diff or diff[0]['rows']:
                    fail(f'{name}: 같은 적재를 한 번 더 했을 때 수가 바뀜 {diff[0]["rows"] if diff else "(전후 표 없음)"}')
                S.act(folder, 'export')
                snap = json.loads((folder / 'output/knowledge_export.json').read_text(encoding='utf-8'))
                linked = [r for r in snap['rels'] if str(r['a']).startswith('PM-02@2.0:') and r['b'] == S.TASK]
                if bool(linked) != (p7 == '가'):
                    fail(f'{name}: 정기 점검표 지식이 핀 세척에 이어진 관계 {len(linked)}개 — 지점7 {p7}')
                c = run(folder, '-m', 'app.utils.check')
                rest = [l for l in c.stdout.splitlines() if l.startswith('  - ') and 'build_record.md' not in l]
                if rest:
                    fail(f'{name}: 검사기에서 기록 칸 말고 남은 것 {rest[:5]}')
                old = OLD / name / '지식_내보내기.json'
                same = same_text(S.model_names(S.convert(old.read_text(encoding='utf-8'))), (folder / 'output/knowledge_export.json').read_text(encoding='utf-8'))
                if not same:
                    fail(f'{name}: 옛 구조 갈래 내보내기와 다름')
                cards = {}
                for p in sorted((OLD / name).glob('작업확인카드_*.md')):
                    new = folder / 'output' / S.convert(p.name)
                    cards[new.name] = new.is_file() and S.convert(p.read_text(encoding='utf-8')) == new.read_text(encoding='utf-8')
                if cards and not all(cards.values()):
                    fail(f'{name}: 옛 구조 갈래 카드와 다름 {cards}')
                rows.append({'branch': name, 'nodes': len(snap['nodes']), 'rels': len(snap['rels']), 'pm02_to_task': len(linked),
                             'remaining_questions': len(snap['remaining_questions']), 'check_rest': rest, 'export_same_as_legacy': same, 'cards_same_as_legacy': cards})
                print(f'{name}: 노드 {len(snap["nodes"])} · 관계 {len(snap["rels"])} · 핀 세척에 이은 정기 점검표 지식 {len(linked)} · 옛 갈래와 같음 {same}')
            except RuntimeError as e:
                fail(f'{name}: {e}')
            finally:
                removed = S.drop_db(folder)
                if removed:
                    rows.append({'branch': name, 'container_removed': removed})
    return rows


C = 'app/features/decisions.csv'
DAMAGE_EXTRACT = [
    ('정한_것 근거가 파일:줄이 아님', C, lambda t: t.replace('data/contract.md:41', 'data/contract.md 4절'), '근거에 파일:줄이 없습니다'),
    ('제공 코드를 고침', 'app/utils/extract.py', lambda t: t + '\n# 고침\n', '제공 파일이 바뀌었습니다'),
    ('결정 표에 없는 결정 말', 'app/features/review_decisions.csv', lambda t: t.replace(',채택,', ',승인,', 1), '정할 자리'),
    ('조건 대조의 맞는 정도가 계약 값이 아님', 'app/features/rule_links.csv', lambda t: t.replace(',일치,', ',맞음,', 1) if ',일치,' in t else t.replace(',불일치,', ',안 맞음,', 1), '정할 자리'),
    ('검토 결과의 인용 한 글자', 'output/reviews/HM-8_1.1_review.json', lambda t: t.replace('"quote": "1. 설비를 정지하고', '"quote": "1. 설비을 정지하고', 1), 'HM-8_1.1_review.json 계약 오류'),
    ('검토 결과의 결정과 상태가 어긋남', 'output/reviews/SR-04_2024_review.json', lambda t: t.replace('"status": "pending"', '"status": "approved"', 1), 'SR-04_2024_review.json 계약 오류'),
]
DAMAGE_GRAPH = [
    ('연결 규칙에 모델에 없는 ID', 'app/features/link_rules.csv', lambda t: t.replace('SOP-COOL-14 SOP-COOL-15', 'SOP-COOL-14 SOP-COOL-99', 1), '정할 자리'),
    ('제공 결과 화면을 고침', 'app/utils/actions.py', lambda t: t + '\n# 고침\n', '제공 파일이 바뀌었습니다'),
    ('내보내기에 끝점 없는 관계', 'output/knowledge_export.json', lambda t: t.replace('"rels": [', '"rels": [{"type": "X", "a": "nope-a", "b": "nope-b", "props": {}},', 1), '끝점이 없는 관계'),
    ('고른 것 빈 칸', C, lambda t: t.rstrip('\n') + '\n빈 지점,,,\n', '빈 칸'),
    ('내보내기에 같은 id의 노드 둘', 'output/knowledge_export.json', lambda t: t.replace('"nodes": [', '"nodes": [{"labels": ["Asset"], "props": {"id": "HYD-01"}},', 1), '같은 id의 노드'),
    ('적재 파일에 전체 삭제', 'output/load.cypher', lambda t: t + 'MATCH (n) DETACH DELETE n;\n', '전체를 지우는 문장'),
    ('적재 파일에 보류 후보', 'output/load.cypher', lambda t: t + 'MERGE (k:`Knowledge` {id: "HM-9@1.0:HM-9-M008"});\n', '승인(approved)이 아닌 후보 id'),
]   # 관계 방향은 제공 코드가 정해 쓴다(지식 → 대상) — 정할 자리로는 방향을 바꿀 수 없어 손상 시험에 두지 않는다(옛 참조와 같음)
DAMAGE_CARD = [('카드 제목 하나 없음', 'output/work_card_SOP-COOL-14.md', lambda t: t.replace('## 승인', '## 승인자', 1), '제목')]


def damage_trials(parent, tmp, keys):
    out = []
    for key in keys:
        graph = S.LABS[key]['kind'] == 'graph'
        practical = S.LABS[key]['course'] == '실전반'
        archive = starter(parent, key).parent / (S.LABS[key]['name'] + '-completed.zip')
        work = tmp / ('dmg-' + key)
        with zipfile.ZipFile(archive) as z:
            z.extractall(work)
        folder = work / S.LABS[key]['name']
        cases = DAMAGE_EXTRACT if not graph else DAMAGE_GRAPH + (DAMAGE_CARD if practical else [])
        try:
            if graph:
                for action in ['db', 'load', 'other', 'more'] if not practical else ['db', 'load', 'other']:
                    S.act(folder, action)
            base = run(folder, '-m', 'app.utils.check')
            if base.returncode:
                fail(f'{key}: 손상 전 완성본이 구조 검사를 통과하지 않음\n{base.stdout[-1500:]}')
            for name, rel, change, marker in cases:
                p = folder / rel
                before = p.read_bytes()
                p.write_text(change(before.decode('utf-8')), encoding='utf-8', newline='\n')
                if p.read_bytes() == before:
                    fail(f'{key} 손상 「{name}」: 바꿀 글을 찾지 못함(손상이 들어가지 않음)')
                    continue
                c = run(folder, '-m', 'app.utils.check')
                caught = c.returncode == 1 and marker in c.stdout
                out.append({'lab': key, 'damage': name, 'file': rel, 'caught': caught, 'rc': c.returncode})
                if not caught:
                    fail(f'{key} 손상 「{name}」을 검사기가 잡지 않음(rc {c.returncode})\n{c.stdout[-800:]}')
                p.write_bytes(before)
            after = run(folder, '-m', 'app.utils.check')
            out.append({'lab': key, 'damage': '(되돌린 뒤)', 'caught': after.returncode == 0, 'rc': after.returncode})
        finally:
            if graph:
                out.append({'lab': key, 'container_removed': S.drop_db(folder)})
    return out


def starter_zips(parent, tmp):
    out = []
    for key in sorted(S.LABS):
        archive = starter(parent, key).with_suffix('.zip')
        work = tmp / ('zip-' + key)
        with zipfile.ZipFile(archive) as z:
            z.extractall(work)
            names = z.namelist()
        folder = work / S.LABS[key]['name']
        r = run(folder, 'run.py', '--no-open')
        got = json.loads((folder / 'output/result.json').read_text(encoding='utf-8'))['blocks']
        errs = [b for b in got if b['kind'] == 'error']
        ok = r.returncode == 0 and not errs and S.LABS[key]['name'] + '_guide.html' in names and not any(n.startswith(S.LABS[key]['name'] + '/output/') for n in names)
        if not ok and not (S.LABS[key]['kind'] == 'graph' and S.LABS[key]['course'] == '실전반'):
            fail(f'{key}: 받은 ZIP 첫 실행 rc {r.returncode} · 오류 {errs[:1]}')
        out.append({'lab': key, 'zip': archive.name, 'entries': len(names), 'first_command_rc': r.returncode, 'blocks': len(got), 'errors': len(errs)})
    return out


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--dest', type=Path, required=True, help='build_session4_projects.py --dest로 만든 부모 폴더(완성본 ZIP 포함)')
    p.add_argument('--out', type=Path)
    p.add_argument('--skip-graph', action='store_true')
    a = p.parse_args(argv)
    parent = a.dest.resolve()
    with tempfile.TemporaryDirectory(prefix='s4trials-', dir=S.WORK) as t:
        tmp = Path(t)
        result = {'kind': '강사 참조 갈래 · 검사기 고의 손상 · 받은 ZIP 첫 실행(새 프로젝트 경로) — 학생 AI 시험 아님',
                  'extract_branches': extract_branches(parent, tmp),
                  'graph_branches': [] if a.skip_graph else graph_branches(parent, tmp),
                  'damage': damage_trials(parent, tmp, [k for k in sorted(S.LABS) if not (a.skip_graph and S.LABS[k]['kind'] == 'graph')]),
                  'starter_zips': starter_zips(parent, tmp)}
    result['mismatches'] = BAD
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(result, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    dmg = [d for d in result['damage'] if 'damage' in d and d['damage'] != '(되돌린 뒤)']
    print(f'추출 갈래 {len(result["extract_branches"])} · 그래프 갈래 {sum(1 for r in result["graph_branches"] if "nodes" in r)} · 고의 손상 {sum(d["caught"] for d in dmg)}/{len(dmg)} 잡음 · 시작 ZIP {len(result["starter_zips"])}')
    print('불일치 0' if not BAD else f'불일치 {len(BAD)}')
    return 1 if BAD else 0


if __name__ == '__main__':
    sys.exit(main())
