"""강사 참조 — 문서 지식 네 랩(통합 04-2 · 04-3, 실전 03-4 · 03-5)의 갈래 실행 · 정답 재생 · 검사기 고의 손상. 학생 폴더 · ZIP에 넣지 않는다.

학생 폴더는 정할 자리 + 제공 코드다. 그래서 갈래 실행은 갈래마다 정할 자리(fills.py)를 새 사본에 써 넣고 제공 흐름(`python show_result.py --no-open`)을 돌려,
갈래를 가르는 값이 갈래의 뜻대로 나오는지 본다 — 학생과 같은 코드 · 같은 명령이다. 모델은 부르지 않는다(강사 추출 실행 run1의 응답 기록, replay.py).
1. 정답 재생 — 가이드의 정답 토글을 단계마다 적용하면 그 단계가 채워지는지(replay.py).
2. 추출 갈래 — 두 반 × 지점5(가 · 나 · 다) × 지점6(가 · 나) = 12. 본다: R4의 맞는 정도가 지점5의 뜻(가 일치 · 나 불일치 · 다 보류), 제조사 지침의 「사내 기준이 정하지 않은 항목」 줄의 결정이
   지점6의 뜻(가 보류 · 나 채택), 검토 결과 · 선택작업 조건의 구조 검사 통과. 산출: 갈래/추출_<반>_<지점5>-<지점6>/.
3. 그래프 갈래 — 두 반 × 지점7(가 · 나) = 4, 실제 Neo4j(사본마다 lab_db.py --no-open). 본다: 정기 점검표 예정된 정비 시간 지식이 핀 세척에 이어지는지가 지점7의 뜻(가 있음 · 나 없음),
   같은 적재를 다시 해도 수가 같음, 검사기에서 기록 칸 말고 남은 것 0. 산출: 갈래/그래프_<반>_<지점7>/.
4. 검사기 고의 손상 — 기본 갈래 완성 상태 사본에 손상 하나씩: check.py가 종료 코드 1과 그 손상의 글을 낸다.
산출: 사건_갈래표.md · 검사기_확인.json. 어긋나면 「불일치」를 찍고 종료 코드 1 — 결과를 맞추지 말고 원인을 고친다.
사용: HYD_MAIN_ROOT=<main 체크아웃> python run_reference.py [--skip-graph] [--lab <랩 키> …]
--lab을 주면 그 랩만 돌리고 결과를 찍기만 한다(사건_갈래표.md · 검사기_확인.json은 네 랩을 모두 돌린 실행만 다시 쓴다).
"""
from __future__ import annotations

from pathlib import Path
import argparse
import json
import re
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parents[1]
sys.path[:0] = [str(HERE), str(TOOLS)]
import build_document_labs as BD  # noqa: E402
import fills as FL  # noqa: E402
import replay as RP  # noqa: E402

OUTDIR = HERE/'갈래'
UNDEFINED_LINES = [105, 107, 114, 116]          # 제조사 지침 T-7.1에서 사내 기준이 정하지 않은 항목의 줄(fills.decisions)
BAD = []


def fail(msg):
    BAD.append(msg)
    print('불일치: ' + msg)


def keep(folder, dst, rels):
    if dst.exists():
        shutil.rmtree(dst)
    for rel in rels:
        for p in sorted(folder.glob(rel)):
            if p.is_file():
                t = dst/p.relative_to(folder/'결과')
                t.parent.mkdir(parents=True, exist_ok=True)
                t.write_bytes(p.read_bytes())


def fill(folder, files):
    for name, text in files.items():
        (folder/'결과'/name).write_text(text, encoding='utf-8', newline='\n')


def extract_branches(tmp, keys=('integrated-04-extract', 'practical-03-extract')):
    rows = []
    for key in keys:
        practical = key == 'practical-03-extract'
        course = '실전반' if practical else '통합반'
        for p5 in FL.P5:
            for p6 in FL.P6:
                name = f'추출_{course}_{p5}-{p6}'
                folder = RP.copy_lab(BD.LABS[key], tmp/name)
                RP.seed_extract(folder)
                fill(folder, FL.extract_files(p5, p6, practical))
                RP.seed_trial(folder)
                r = RP.run(folder, 'show_result.py', '--no-open')
                if r.returncode:
                    fail(f'{name}: show_result 종료 코드 {r.returncode}\n{r.stdout[-1500:]}')
                    continue
                reviews = {p.name: json.loads(p.read_text(encoding='utf-8')) for p in sorted((folder/'결과/검토').glob('*.json'))}
                r4 = [l['match'] for d in reviews.values() for l in d['rule_links'] if l['rule_id'] == 'R4']
                want = {'가': '일치', '나': '불일치', '다': '보류'}[p5]
                if r4 != [want]:
                    fail(f'{name}: R4 맞는 정도 {r4} — 지점5 {p5}는 {want}')
                oem = reviews.get('OEM-HPP45A-MM_C_검토.json', {'candidates': []})
                got = sorted({c['decision'] for c in oem['candidates'] if c['line_start'] in UNDEFINED_LINES and c['decision'] != '제외'})
                want6 = ['보류'] if p6 == '가' else ['채택']
                if got != want6:
                    fail(f'{name}: 사내 기준이 정하지 않은 제조사 항목의 결정 {got} — 지점6 {p6}는 {want6}')
                c = RP.run(folder, 'check.py', *[f'결과/검토/{n}' for n in reviews])
                if c.returncode:
                    fail(f'{name}: 검토 결과 구조 검사 실패\n{c.stdout[-1500:]}')
                sel = {}
                if practical:
                    s = json.loads((folder/'결과/선택작업_조건.json').read_text(encoding='utf-8'))
                    sel = {k: len(s[k]) for k in ('preparation', 'prohibitions', 'completion', 'remaining_questions', 'sop_diff')}
                counts = {}
                for d in reviews.values():
                    for x in d['candidates']:
                        counts[x['decision']] = counts.get(x['decision'], 0) + 1
                hits = []
                data = json.loads((folder/'입력'/BD.JUDGED[key]).read_text(encoding='utf-8'))
                for e in data['events']:
                    for x in e['candidates']:
                        if x['sop'] == BD.TASK and x['status'] == '제외' and 'R4' in ({y.get('rule_id') for y in x.get('exclusions', [])} | {y.get('rule_id') for y in x.get('reasons', []) if y.get('result') == 'EXCLUDE'}):
                            hits.append(e['id'])
                rows.append((name, counts, r4[0] if r4 else '-', ', '.join(hits) if p5 == '나' else '그대로', sel))
                keep(folder, OUTDIR/name, ['결과/검토/*.json', '결과/선택작업_조건.json', '결과/정한_것.csv', '결과/조건_대조.csv', '결과/검토_결정.csv'])
                print(f'{name}: R4 {r4} · 결정 {counts}' + (f' · 선택작업 {sel}' if sel else ''))
    return rows


def graph_branches(tmp, keys=('integrated-04-graph', 'practical-03-card')):
    rows = []
    for key in keys:
        practical = key == 'practical-03-card'
        course = '실전반' if practical else '통합반'
        for p7 in FL.P7:
            name = f'그래프_{course}_{p7}'
            folder = RP.copy_lab(BD.GLABS[key], tmp/name)
            RP.run(folder, 'lab_db.py', '--no-open', check=True)
            try:
                fill(folder, FL.graph_files(p7, practical))
                outs = [RP.run(folder, 'show_result.py', '--no-open') for _ in range(2)]
                if any(o.returncode for o in outs):
                    fail(f'{name}: show_result 종료 코드 {[o.returncode for o in outs]}\n{outs[-1].stdout[-1500:]}')
                    continue
                snap = json.loads((folder/'결과/지식_내보내기.json').read_text(encoding='utf-8'))
                linked = [r for r in snap['rels'] if str(r['a']).startswith('PM-02@2.0:') and r['b'] == BD.TASK]
                if bool(linked) != (p7 == '가'):
                    fail(f'{name}: 정기 점검표 지식이 핀 세척에 이어진 관계 {len(linked)}개 — 지점7 {p7}')
                c = RP.run(folder, 'check.py')
                rest = [l for l in c.stdout.splitlines() if l.startswith('  - ') and '구축_기록.md' not in l]
                if rest:
                    fail(f'{name}: 검사기에서 기록 칸 말고 남은 것 {rest[:5]}')
                rows.append((name, len(snap['nodes']), len(snap['rels']), len(linked), len(snap['remaining_questions'])))
                keep(folder, OUTDIR/name, ['결과/*.json', '결과/*.csv', '결과/*.cypher', '결과/작업확인카드_*.md'])
                print(f'{name}: 노드 {len(snap["nodes"])} · 관계 {len(snap["rels"])} · 핀 세척에 이은 정기 점검표 지식 {len(linked)}')
            finally:
                RP.drop_db(folder)
    return rows


DAMAGE_EXTRACT = [
    ('정한_것 근거가 파일:줄이 아님', '결과/정한_것.csv', lambda t: t.replace('입출력_계약.md:41', '입출력_계약.md 4절'), '근거에 파일:줄이 없습니다'),
    ('제공 코드를 고침', 'doc_extract.py', lambda t: t + '\n# 고침\n', '제공 파일이 바뀌었습니다'),
    ('결정 표에 없는 결정 말', '결과/검토_결정.csv', lambda t: t.replace(',채택,', ',승인,', 1), '정할 자리'),
    ('조건 대조의 맞는 정도가 계약 값이 아님', '결과/조건_대조.csv', lambda t: t.replace(',일치,', ',맞음,', 1) if ',일치,' in t else t.replace(',불일치,', ',안 맞음,', 1), '정할 자리'),   # 실전 기본 갈래는 R4 불일치 · R5 원문 없음뿐
    ('검토 결과의 인용 한 글자', '결과/검토/HM-8_1.1_검토.json', lambda t: t.replace('"quote": "1. 설비를 정지하고', '"quote": "1. 설비을 정지하고', 1), 'HM-8_1.1_검토.json 계약 오류'),
    ('검토 결과의 결정과 상태가 어긋남', '결과/검토/SR-04_2024_검토.json', lambda t: t.replace('"status": "pending"', '"status": "approved"', 1), 'SR-04_2024_검토.json 계약 오류'),
]
DAMAGE_GRAPH = [
    ('연결 규칙에 모델에 없는 ID', '결과/연결_규칙.csv', lambda t: t.replace('SOP-COOL-14 SOP-COOL-15', 'SOP-COOL-14 SOP-COOL-99', 1), '정할 자리'),
    ('제공 결과 화면을 고침', 'lab_steps.py', lambda t: t + '\n# 고침\n', '제공 파일이 바뀌었습니다'),
    ('내보내기에 끝점 없는 관계', '결과/지식_내보내기.json', lambda t: t.replace('"rels": [', '"rels": [{"type": "X", "a": "nope-a", "b": "nope-b", "props": {}},', 1), '끝점이 없는 관계'),
    ('고른 것 빈 칸', '결과/정한_것.csv', lambda t: t.rstrip('\n') + '\n빈 지점,,,\n', '빈 칸'),
    ('내보내기에 같은 id의 노드 둘', '결과/지식_내보내기.json', lambda t: t.replace('"nodes": [', '"nodes": [{"labels": ["Asset"], "props": {"id": "HYD-01"}},', 1), '같은 id의 노드'),
    ('적재 파일에 전체 삭제', '결과/load.cypher', lambda t: t + 'MATCH (n) DETACH DELETE n;\n', '전체를 지우는 문장'),
    ('적재 파일에 보류 후보', '결과/load.cypher', lambda t: t + 'MERGE (k:`Knowledge` {id: "HM-9@1.0:HM-9-M008"});\n', '승인(approved)이 아닌 후보 id'),
]   # 관계 방향은 제공 코드가 정해 쓴다(지식 → 대상) — 정할 자리로는 방향을 바꿀 수 없어 손상 시험에 두지 않는다


def damage_trials(tmp, keys=None):
    out = []
    for key, cases in (('integrated-04-extract', DAMAGE_EXTRACT), ('practical-03-extract', DAMAGE_EXTRACT),
                       ('integrated-04-graph', DAMAGE_GRAPH), ('practical-03-card', DAMAGE_GRAPH + [('카드 제목 하나 없음', '결과/작업확인카드_SOP-COOL-14.md', lambda t: t.replace('## 승인', '## 승인자', 1), '제목')])):
        if keys is not None and key not in keys:
            continue
        graph = key in BD.GLABS
        res, folder = RP.replay(key, tmp/f'dmg_{key}', keep_db=True)
        try:
            for name, rel, change, marker in cases:
                p = folder/rel
                before = p.read_bytes()
                p.write_text(change(before.decode('utf-8')), encoding='utf-8', newline='\n')
                if p.read_bytes() == before:
                    fail(f'{key} 손상 「{name}」: 바꿀 글을 찾지 못함(손상이 들어가지 않음)')
                    continue
                c = RP.run(folder, 'check.py')
                caught = c.returncode == 1 and marker in c.stdout
                out.append({'lab': key, 'damage': name, 'caught': caught})
                if not caught:
                    fail(f'{key} 손상 「{name}」을 검사기가 잡지 않음(rc {c.returncode})\n{c.stdout[-800:]}')
                p.write_bytes(before)
        finally:
            if graph:
                RP.drop_db(folder)
    return out


def table_md(replays, ext, graphs, damages):
    lines = ['# 사건 갈래표 — 문서 지식 네 랩(강사 참조)', '', '사건: 10월 27일 01:59 HYD-02 쿨러 성능 저하 경보의 판정 뒤에 남은 근본 조치 — 쿨러 핀 세척(SOP-COOL-14) 작업지시 전.',
             '갈래마다 정할 자리(fills.py)를 새 사본에 써 넣고 학생과 같은 제공 흐름(`python show_result.py --no-open`)을 돌린 결과다. 모델은 부르지 않는다(강사 추출 실행 run1의 응답 기록).', '',
             '## 정답 보기 재생', '', '| 랩 | 단계 | 상태 |', '|---|---|---|']
    lines += [f'| {k} | {i:02d} {n} | {s} |' for k, res in replays for i, n, s, _ in res]
    lines += ['', '## 지점5 조건의 근거 · 지점6 사내 문서와 제조사 지침(추출 랩)', '', '| 갈래 | 결정 수 | R4 맞는 정도 | R4를 빼면 SOP-COOL-14 제외가 풀리는 지난 판정 | 선택작업 조건(실전) |', '|---|---|---|---|---|']
    lines += [f'| {n} | {c} | {r4} | {h} | {s or "—"} |' for n, c, r4, h, s in ext]
    lines += ['', '손익: 지점5 가 = 실측 · 운전 중 원문을 예측 · 작업지시 규칙의 근거로 굳힘(감사 때 범위 문제) / 나 = 예측 유온 작업지시 단독 후보가 비교에 들어옴 / 다 = 회신까지 출처 미확인.',
              '지점6 가 = 공기 세척으로 회복하지 않으면 미달로 끝나고 코어 상태를 보지 않음 / 나 = 사내 승인 없는 기준으로 정지 시간 · 코어 비용이 늘고 완료 판단이 두 갈래.', '',
              '## 지점7 다른 문서의 조건(그래프 랩)', '', '| 갈래 | 노드 | 관계 | 핀 세척에 이은 정기 점검표 지식 | 남은 질문 |', '|---|---|---|---|---|']
    lines += [f'| {n} | {a} | {b} | {c} | {d} |' for n, a, b, c, d in graphs]
    lines += ['', '손익: 가 = 세척이 다음 예정된 정비 시간까지 늦어질 수 있음(그동안 팬 100 %) / 나 = 생산 중이면 납기가 걸린 오더를 세울 수 있음.', '',
              '## 검사기 고의 손상', '', '| 랩 | 손상 | 잡음 |', '|---|---|---|'] + [f'| {d["lab"]} | {d["damage"]} | {"잡음" if d["caught"] else "못 잡음"} |' for d in damages]
    return '\n'.join(lines) + '\n'


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--skip-graph', action='store_true')
    p.add_argument('--lab', action='append', choices=sorted(BD.LABS) + sorted(BD.GLABS))
    a = p.parse_args(argv)
    only = a.lab
    if OUTDIR.exists() and not only:
        shutil.rmtree(OUTDIR)            # 옛 설계의 갈래 산출이 남지 않게(이력은 git)
    with tempfile.TemporaryDirectory(prefix='doc_ref_') as t:
        tmp = Path(t)
        replays = []
        for key in [k for k in sorted(BD.LABS) + ([] if a.skip_graph else sorted(BD.GLABS)) if not only or k in only]:
            res, _ = RP.replay(key, tmp/'replay')
            replays.append((key, res))
            for i, n, s, log in res:
                if s not in ('채움', '볼 것 없음', '결과 보기'):
                    fail(f'{key} {i:02d} {n}: 정답 재생 상태 {s}\n{log[-1200:]}')
        ext = extract_branches(tmp, [k for k in sorted(BD.LABS) if not only or k in only])
        graphs = [] if a.skip_graph else graph_branches(tmp, [k for k in sorted(BD.GLABS) if not only or k in only])
        damages = damage_trials(tmp, only) if not a.skip_graph else []
    if only:
        print(f'정답 재생 {sum(len(r) for _, r in replays)}단계 · 추출 갈래 {len(ext)} · 그래프 갈래 {len(graphs)} · 고의 손상 {sum(d["caught"] for d in damages)}/{len(damages)} 잡음 — {", ".join(only)}만(표는 다시 쓰지 않음)')
        print('불일치 0' if not BAD else f'불일치 {len(BAD)}')
        return 1 if BAD else 0
    (HERE/'사건_갈래표.md').write_text(table_md(replays, ext, graphs, damages), encoding='utf-8', newline='\n')
    (HERE/'검사기_확인.json').write_text(json.dumps(damages, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    print(f'정답 재생 {sum(len(r) for _, r in replays)}단계 · 추출 갈래 {len(ext)} · 그래프 갈래 {len(graphs)} · 고의 손상 {sum(d["caught"] for d in damages)}/{len(damages)} 잡음')
    print('불일치 0' if not BAD else f'불일치 {len(BAD)}')
    return 1 if BAD else 0


if __name__ == '__main__':
    sys.exit(main())
