"""통합02 설계 랩(실습 랩 규모)의 강사 참조 시험 — 갈래마다 정답 내용을 새 사본에 넣고 실제로 실행해 판정한다. AI 호출 없음.

판정(한 기능을 여기 한 곳에서):
- 갈래 A · B · C · E마다 만든 모델(output/graph.json) 전체를 생성 정답 구조(data_session2.TRUTH → verify_reference.expected)와 견준다.
- 갈래마다 결과 화면의 대조(기대 답 ↔ 모델에 물은 답)가 줄마다 같음이고, 결정 지점마다 갈래가 다르면 그 질문의 답이 실제로 다르다.
- 식별자 틀을 달리한 사본(갈래 E에 session2_answers.OTHER_IDS — 설비 · 부품에 머리를 붙이고 센서 · 구성 요소의 꼴을 바꿈)도 같은 기대 답(설비 코드 · 품번으로 묻는 줄)과
  줄마다 같음이고 그 답이 갈래 E와 같으며, 모델을 설비 코드 · 사내 품번 · 태그로 되짚으면 생성 정답 구조와 같다. 질문 1의 항목을 원자료 이름으로 적어도 다른 이름으로 찾아 같음이다.
- 스키마 표의 선택을 바꾸면 결과가 따라 바뀐다(schema_choices): 필수 · 적어도 하나 · 자료형 · 단위 · 카디널리티 · 빠진 속성 · 식별자에 쓴 빈 칸, 내가 더한 질문 4의 둘째 바퀴.
  관계의 화살표는 거꾸로 그어도(카디널리티 · 적어도 하나를 함께 뒤집으면) 답이 같고, 화면이 그 줄을 거꾸로 읽은 문장으로 보인다. 카디널리티는 자료보다 넓게 적어도 어긋남이 아니다.
- 빈 틀을 일부러 망가뜨리면(카디널리티 · 지난 실물 · 물리량 이름 · 빈 결정 · 처리 안 한 철거 줄 · 한 물리량에 섞인 단위) 제공 코드가 그 줄을 짚고 멈추고,
  교체부품 칸의 표기를 교차표에 없는 글로 바꾸면 잇지 않고 화면에 보인다. 모델을 망가뜨리면(ID 중복 · 끝점 없음 · 관계 방향) 구조 검사가 잡는다.
- 학생 ZIP과 완성본 ZIP을 새 폴더에 풀어 첫 명령과 재실행이 된다.
- 모든 실행은 학생 조건(command — UTF-8 모드 꺼짐 · cp949 파이프 · 받는 쪽은 UTF-8로 읽음)으로 돌고, 글자표 결함을 되살린 사본을 그 조건이 잡는다(student_condition_selftest).
사용: python reference/session2_project_trials.py <ontology-lab 폴더>
"""
from pathlib import Path
import argparse
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import build_labs as B
import data_session2 as D
import session2_answers as A
import session2_project as P
import verify_reference as V
from lab_package import ROOT

ACTIONS = ['sources', 'expected', 'classes', 'properties', 'relations', 'names', 'quantities', 'parts', 'query', 'check']


# 학생 조건 — 한국어 Windows의 학생 PC에서 Codex가 명령을 대신 돌릴 때와 같다(2026-11-25 실측, 코딩랩.md 「함정」): 파이썬 UTF-8 모드가 꺼져 있고
# 출력은 콘솔이 아닌 파이프이며(파이썬이 cp949로 쓴다), 받는 쪽은 그 바이트를 UTF-8로 읽는다. 이 PC의 작업 환경은 PYTHONUTF8=1이라, 이 값을 끄지 않으면 결함이 가려진다.
# PYTHONWARNDEFAULTENCODING은 제공 코드가 글자표를 적지 않고 파일을 열거나 자식 프로세스를 읽는 곳을 EncodingWarning으로 드러낸다.
STUDENT = {'PYTHONUTF8': '0', 'PYTHONIOENCODING': 'cp949', 'PYTHONWARNDEFAULTENCODING': '1', 'PYTHONDONTWRITEBYTECODE': '1'}


def command(folder, *args, ok=True, student=True):
    """랩 명령 하나를 학생 조건(STUDENT)으로 돌린다. 2회차 강사 참조 시험(두 반)의 모든 실행이 이 함수를 거친다.
    출력이 UTF-8이 아니거나, 글자표 오류로 멈추거나, 글자표를 적지 않은 입출력이 있으면 실패다.
    student=False는 학생 랩이 아닌 계산(옛 판과 대조하려고 강사 코드로 다시 만드는 모델)에만 쓴다 — 그 실행은 이 PC의 UTF-8 모드로 돈다."""
    result = subprocess.run([sys.executable, *args], cwd=folder, capture_output=True,
                            env=os.environ | (STUDENT if student else {'PYTHONUTF8': '1', 'PYTHONDONTWRITEBYTECODE': '1'}))
    raw = result.stdout + result.stderr
    try:
        output = raw.decode('utf-8')
    except UnicodeDecodeError as e:
        raise AssertionError((str(folder), args, f'출력이 UTF-8이 아닙니다({e}) — 학생 PC에서 AI가 대신 실행하면 한글이 깨집니다', raw[:300]))
    for mark in ('UnicodeEncodeError', 'UnicodeDecodeError', 'EncodingWarning', '�'):
        if mark in output:
            raise AssertionError((str(folder), args, f'학생 조건에서 글자표 문제({mark!r})', output[-1500:]))
    if (result.returncode == 0) != ok:
        raise AssertionError((str(folder), args, result.returncode, output))
    return output


def student_condition_selftest(starter, work, action=None):
    """자가시험 — 글자표 결함을 일부러 되살린 사본(제공 파일에서 lab_frame.UTF8_OUT을 지우고 구조 검사를 UTF-8 모드 없이 띄움)을 command가 잡는가.
    못 잡으면 학생 조건 시험이 없는 것과 같다. 고친 랩 그대로의 사본은 같은 명령을 통과해야 한다."""
    import lab_frame as F
    records = []
    for name, files, args in (('run.py-without-utf8-output', {'run.py': F.UTF8_OUT}, ('run.py', *([action] if action else []), '--no-open')),
                              ('check-child-without-utf8', {'app/utils/actions.py': "'-X', 'utf8', ", 'app/utils/check.py': F.UTF8_OUT}, ('run.py', 'check', '--no-open')),
                              ('check.py-direct-without-utf8-output', {'app/utils/check.py': F.UTF8_OUT}, ('-m', 'app.utils.check'))):
        good, broken = work / f'selftest-{name}-good', work / f'selftest-{name}'
        for copy in (good, broken):
            shutil.copytree(starter, copy, ignore=shutil.ignore_patterns('__pycache__', 'output', '.lab_connection.json'))
        for path, piece in files.items():
            text = (broken / path).read_text(encoding='utf-8')
            assert text.count(piece) == 1, (name, path, '되살릴 자리를 찾지 못함')
            (broken / path).write_text(text.replace(piece, ''), encoding='utf-8', newline='\n')
        fails = args[-1] != '--no-open' or 'check' in args      # 받은 그대로의 랩에서 구조 검사는 「아직 검사할 결과가 없습니다」로 끝난다(종료 1)
        command(good, *args, ok=not fails)
        try:
            command(broken, *args, ok=not fails)
        except AssertionError as e:
            reason = e.args[0][2]
            if not (isinstance(reason, str) and ('글자표' in reason or 'UTF-8' in reason)):      # 종료 코드가 달라 실패한 것은 잡은 것이 아니다
                raise AssertionError((name, '되살린 글자표 결함이 글자표 판정이 아닌 다른 까닭으로 실패함', e.args[0]))
            records.append({'selftest': name, 'caught': reason[:80]})
        else:
            raise AssertionError((name, '되살린 글자표 결함을 학생 조건 시험이 잡지 못함'))
    return records


def evidence_trial(folder):
    """기대 답 표의 근거 칸을 일부러 틀린 줄로 바꿔 넣으면 기대 답 화면과 질문 대조 화면이 그 줄(파일:줄)을 짚는가 — 두 반 설계 랩이 같이 쓴다. 채운 랩 폴더(모델까지 만든 사본)에서 돌리고 기대 답 표는 되돌린다.
    답 값은 그대로 두므로 질문 대조의 줄은 여전히 모두 같음이다(값 대조만으로는 잡히지 않는 결함이라는 뜻). 맞는 줄을 한 줄씩 적은 근거는 하나도 걸리지 않아야 한다.
    가이드는 기대 답 화면(expected)을 앞 단계에서만 실행하게 하므로, 뒤 단계에서 더한 줄은 질문 대조 화면(query)이 같은 카드로 짚어야 한다(받기 시험 v63 가14)."""
    import csv, io
    path = folder / 'app/features/expected.csv'
    kept = path.read_bytes()
    lines = kept.decode('utf-8').splitlines()
    head = next(i for i, x in enumerate(lines) if x.strip() and not x.lstrip().startswith('#'))
    rows = list(csv.reader(io.StringIO('\n'.join(lines[head + 1:]))))
    at = lambda i: str(head + 2 + i)      # 그 줄의 편집기 줄 번호
    table = lambda n: list(enumerate(csv.DictReader(io.StringIO((folder / 'data' / n).read_text(encoding='utf-8-sig'))), 2))
    sensors, comps, alias, spare = table('sensors.csv'), table('components.csv'), table('part_aliases.csv'), table('spare_parts.csv')
    cards = lambda action='expected': {c['title'].rsplit(':', 1)[1]: json.dumps(c['lines'], ensure_ascii=False) for b in blocks(folder, action)
                                       if b['kind'] == 'cards' and b['title'].startswith('근거로 적은 줄이 맞지 않는') for c in b['items']}
    first = blocks(folder, 'expected')[0]
    assert first['state'] == 'info' and not cards(), ('맞게 쓴 참조 기대 답의 근거가 걸림', first, cards())
    asked = blocks(folder, 'query')
    assert asked[0]['state'] == 'ok' and '근거로 적은 줄' not in asked[0]['detail'] and not cards('query'), ('맞게 쓴 참조 기대 답의 근거가 질문 대조에서 걸림', asked[0])
    words = lambda part: {part} | {r['다른표기'] for _, r in alias if r['사내품번'] == part} | {r['품명'] for _, r in spare if r['품번'] == part}
    wrong, right, used = {}, {}, set()

    def pick(test):
        i = next(i for i, r in enumerate(rows) if i not in used and test(r))
        used.add(i)
        return i, rows[i]
    tags = lambda r: r[3].split(' · ')
    q1 = lambda r: r[0] == '1' and r[3] != '없음' and not r[2].endswith('실물') and any(s['설비코드'] == r[1] and s['태그'] not in tags(r) for _, s in sensors)
    i, r = pick(q1)      # 그 설비의 센서 줄이지만 답에 없는 태그의 줄(한 줄 밀린 줄 번호)
    wrong[i] = (f"data/sensors.csv:{next(n for n, s in sensors if s['설비코드'] == r[1] and s['태그'] not in tags(r))}", '적힌 줄이 아닙니다')
    i, r = pick(q1)
    right[i] = 'data/sensors.csv:' + ' · '.join(str(n) for n, s in sensors if s['설비코드'] == r[1] and s['태그'] in tags(r))
    q2 = lambda r: r[0] == '2' and ':' in r[2]
    line_of = lambda r: next(n for n, s in sensors if f"{s['설비코드']}:{s['태그']}" == r[2])
    i, r = pick(q2)      # 그 센서가 아닌 줄
    wrong[i] = (f"data/sensors.csv:{next(n for n, s in sensors if n > line_of(r) and f'{s['설비코드']}:{s['태그']}' != r[2])}", '의 줄이 없습니다')
    i, r = pick(q2)      # 그 센서의 줄과 함께 같은 물리량의 다른 센서 줄을 댄 근거(기준 단위의 근거)는 맞는 근거다 — 리허설 학생 역이 실제로 이렇게 적었다
    right[i] = f"sensors.csv:{line_of(r)} · {next(n for n, s in sensors if f'{s['설비코드']}:{s['태그']}' != r[2])}"
    q3 = lambda r: r[0] == '3' and r[2]
    carries = lambda c, r: any(w and w in v for w in words(r[2]) | {r[1]} for v in c.values())
    i, r = pick(q3)      # 그 부품을 적지 않은 구성 요소 줄
    wrong[i] = (f'data/components.csv:{next(n for n, c in comps if not carries(c, r))}', '적힌 줄이 아닙니다')
    i, r = pick(q3)      # 그 부품을 적은 구성 요소 줄과, 답에 적은 설비의 설비 대장 줄
    right[i] = (f'data/components.csv:{next(n for n, c in comps if carries(c, r))} · '
                f"data/equipment.csv:{next(n for n, a in table('equipment.csv') if a['설비코드'] in r[3].split(' · '))}")
    rest = [i for i in range(len(rows)) if i not in used]
    wrong[rest[0]] = ('data/없는_표.csv:3', '없는 파일')
    wrong[rest[1]] = (f'data/sensors.csv:{len(sensors) + 500}', '줄까지입니다')
    wrong[rest[2]] = ('data/components.csv:1', '자료가 적힌 줄이 아닙니다')
    used.update(rest[:3])
    quotes = folder / 'data/supply_terms.csv'
    q5 = lambda r: r[0] == '5' and '/' in r[2]
    if quotes.is_file() and any(q5(r) for r in rows):      # 실전반: 그 부품의 견적이지만 다른 공급사의 줄
        name = lambda text: text.split('(')[0].strip()
        offers = table('supply_terms.csv')
        i, r = pick(lambda r: q5(r) and any(name(o['공급사']) != r[2].split('/')[1] and o['품번'] in words(r[2].split('/')[0]) for _, o in offers))
        part, supplier = r[2].split('/')
        wrong[i] = (f"data/supply_terms.csv:{next(n for n, o in offers if name(o['공급사']) != supplier and o['품번'] in words(part))}", f'공급사 「{supplier}」의 줄이 아닙니다')
        i, r = pick(q5)
        part, supplier = r[2].split('/')
        right[i] = f"data/supply_terms.csv:{next(n for n, o in offers if name(o['공급사']) == supplier and o['품번'] in words(part))}"
    for i, v in {**{i: v[0] for i, v in wrong.items()}, **right}.items():
        rows[i][4] = v
    buf = io.StringIO()
    csv.writer(buf, lineterminator='\n').writerows(rows)
    path.write_text('\n'.join(lines[:head + 1]) + '\n' + buf.getvalue(), encoding='utf-8', newline='\n')
    try:
        hit, first = cards(), blocks(folder, 'expected')[0]
        assert first['state'] == 'warn' and f'근거로 적은 줄이 맞지 않는 줄 {len(wrong)}곳' in first['text'], first
        assert set(hit) == {at(i) for i in wrong}, (sorted(hit), sorted(at(i) for i in wrong), '걸려야 할 줄만 걸려야 함 — 맞는 줄을 적은 줄: ' + ' · '.join(at(i) for i in right))
        for i, (cited, said) in wrong.items():
            assert said in hit[at(i)] and cited.split('/')[-1] in hit[at(i)], (cited, said, hit[at(i)])
        asked = blocks(folder, 'query')
        answers = [r['state'] for b in asked if b['kind'] == 'compare' for r in b['rows']]
        assert answers and all(s == '같음' for s in answers), '근거 칸만 바꿨는데 질문 대조가 달라짐'
        # 질문 대조 화면도 같은 줄을 같은 글로 짚고(대조 표보다 먼저), 답이 모두 같아도 결론 줄이 초록 「맞음」으로 끝나지 않는다
        again = cards('query')
        assert again == hit, (sorted(again), sorted(hit), '질문 대조 화면의 근거 카드가 기대 답 화면과 다름')
        assert asked[0]['state'] == 'warn' and f'근거로 적은 줄이 맞지 않는 기대 답 줄 {len(wrong)}곳' in asked[0]['detail'], asked[0]
        kinds = [(b['kind'], b.get('title', '')[:8]) for b in asked]
        assert kinds.index(('cards', '근거로 적은 줄')) < next(i for i, k in enumerate(kinds) if k[0] == 'compare'), kinds
        # 카드의 문장은 「 · 」에서 배지로 갈리지 않고 한 문장으로 그려진다(받기 시험 v63 가16 ①). 영문 · 숫자로 끝난 표기 뒤의 조사는 「이나(나)」
        page = (folder / 'output/result.html').read_text(encoding='utf-8')
        whole = '그 부품의 사내 품번 · 다른 표기 · 품명이 적힌 줄이 아닙니다'
        assert whole in page and page.count(whole) == sum(v.count(whole) for v in hit.values()), '근거 카드의 문장이 화면에서 조각으로 갈림'
        import re
        assert not re.search(r'[A-Za-z0-9]」나 그 부품', page) and ('」이나(나) 그 부품' in page or '」나 그 부품' in page or '」이나 그 부품' in page), '물은 표기 뒤의 조사'
    finally:
        path.write_bytes(kept)
    assert not cards() and not cards('query')
    return {'wrong_evidence_lines_pointed': len(wrong), 'right_single_line_evidence_not_pointed': len(right), 'query_rows_still_same': len(answers),
            'query_screen_points_same_lines': len(again), 'query_verdict': asked[0]['state'], 'cited': [v[0] for v in wrong.values()]}


def put(folder, files, convert=False):
    for name, text in files.items():
        target = folder / (P.convert(name) if convert else name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(P.convert(text) if convert else text, encoding='utf-8', newline='\n')


def blocks(folder, action):
    command(folder, 'run.py', action, '--no-open')
    return json.loads((folder / 'output/result.json').read_text(encoding='utf-8'))['blocks']


def model_answers(branch, graph):
    """학생 꼴 모델(output/graph.json)을 verify_reference.expected와 같은 꼴로 읽는다 — 구성 요소 이름은 그 설비 모델의 품목 키(build_labs.comp_key),
    물리량 이름은 강사 참조의 이름표(quantities_of)로 되짚는다."""
    pol = B.policy(branch)
    qid_of = {name: qid for qid, (name, _) in B.quantities_of(pol).items()}
    label = {n['props']['id']: n['labels'][0] for n in graph['nodes']}
    props = {n['props']['id']: n['props'] for n in graph['nodes']}
    by = {}
    for r in graph['rels']:
        by.setdefault(r['type'], []).append(r)
    owner = {r['b']: r['a'] for r in by['HAS_COMPONENT']}
    key = lambda cid: B.comp_key(props[cid]['name'], {k for k, *_ in D.MODEL_COMPONENTS[props[owner[cid]]['model']]})
    comp = lambda cid: f'{owner[cid]}:{key(cid)}'
    sensors, members, sprops, parts, units = {}, {}, {}, {a: {} for a, l in label.items() if l == 'Asset'}, {}
    for r in by['MONITORED_BY']:
        sensors.setdefault(owner[r['a']], {}).setdefault(key(r['a']), []).append(props[r['b']]['tag'])
    for r in by['OBSERVES']:
        qid, s = qid_of[props[r['b']]['name']], props[r['a']]
        members.setdefault(qid, []).append(r['a'])
        sprops[r['a']] = [qid, s['unit'], s.get('normal'), s.get('limit'), {'상한': 'upper', '하한': 'lower'}.get(s.get('limit_direction')), None]   # 학생 꼴 모델은 kind를 두지 않는다 — 실측뿐인 실습 랩 규모의 기대 답도 None
    for cid, aid in owner.items():
        parts[aid][key(cid)] = next((r['b'] for r in by['USES_PART'] if r['a'] == cid), None)
    for r in by.get('INSTALLED_UNIT', []):
        units.setdefault(comp(r['a']), []).append([props[r['b']]['serial'], r['props']['current']])
    serials = {comp(c): p['serial'] for c, p in props.items() if label[c] == 'Component' and 'serial' in p}
    return {'sensors_by_asset': {a: {k: sorted(v) for k, v in sorted(d.items())} for a, d in sorted(sensors.items())},
            'quantity_members': {k: sorted(v) for k, v in sorted(members.items())}, 'sensor_props': dict(sorted(sprops.items())),
            'parts_by_asset': {a: dict(sorted(d.items())) for a, d in sorted(parts.items())},
            'units': {k: sorted(v) for k, v in sorted(units.items())}}, serials


def ontology(starter, work):
    records, answers = [], {}
    for branch in B.REFERENCE_BRANCHES['통합반']:
        new = work / ('new-' + branch)
        shutil.copytree(starter, new, ignore=shutil.ignore_patterns('__pycache__', 'output'))
        files = A.integrated_design(branch)
        files['결과/정한_것.csv'] = B.chosen_text(A.integrated_chosen(branch))
        files['결과/기대_답.csv'] = B.expect_design_text(branch)
        put(new, files, True)
        for action in ACTIONS:
            (work / f'{branch}-{action}.txt').write_text(command(new, 'run.py', action, '--no-open'), encoding='utf-8')
        graph = json.loads((new / 'output/graph.json').read_text(encoding='utf-8'))
        exp = V.expected('통합반', branch)
        got, serials = model_answers(branch, graph)
        gap = V.diff({k: exp[k] for k in got}, got)
        assert not gap, (branch, gap)
        split = B.policy(branch)[2] == '나눔'      # 한 대상 갈래는 지금 달린 실물의 일련번호만 구성 요소 속성으로 남는다
        assert serials == ({} if split else {f'{a}:{k}': s for (a, k), s in D.SERIALS.items()}), (branch, serials)
        rows = [r for block in blocks(new, 'query') if block['kind'] == 'compare' for r in block['rows']]
        assert rows and all(r['state'] == '같음' for r in rows), (branch, [r for r in rows if r['state'] != '같음'])
        original = (new / 'output/graph.json').read_bytes()
        command(new, 'run.py', 'parts', '--no-open')
        assert original == (new / 'output/graph.json').read_bytes(), (branch, '같은 빈 틀로 다시 만든 모델이 다름')
        answers[branch] = {r['key']: r['cells'][0][1] for r in rows}
        records.append({'branch': branch, 'policy': B.policy(branch)[2:], 'nodes': len(graph['nodes']), 'relations': len(graph['rels']),
                        'model_equals_truth': True, 'repeat_equal': True, 'answers_same_rows': len(rows), 'answers': answers[branch]})
        if branch == 'E':
            records.append(other_identifiers(starter, work, answers['E'], exp))
        if branch == 'A':
            records += field_damage(new, files)
            records += schema_choices(new, branch)
            for label in ('duplicate-id', 'missing-endpoint', 'reverse-direction'):
                broken = copy.deepcopy(graph)
                if label == 'duplicate-id':
                    broken['nodes'].append(copy.deepcopy(broken['nodes'][0]))
                elif label == 'missing-endpoint':
                    broken['rels'][0]['b'] = 'missing-endpoint'
                else:
                    broken['rels'][0]['a'], broken['rels'][0]['b'] = broken['rels'][0]['b'], broken['rels'][0]['a']
                (new / 'output/graph.json').write_text(json.dumps(broken, ensure_ascii=False), encoding='utf-8')
                out = command(new, 'run.py', 'check', '--no-open', ok=False)
                assert '구조 확인 필요' in out, out
                command(new, 'run.py', 'parts', '--no-open')
                command(new, 'run.py', 'check', '--no-open')
                assert (new / 'output/graph.json').read_bytes() == original
                records.append({'broken': label, 'rejected': True, 'parts_then_check_recovers': True})
    # 결정 지점마다: 그 지점만 다른 두 갈래의 답이 실제로 다르다(같으면 결정 지점이 아니다)
    for point, index in (('구성 요소 자리와 그 실물', 2), ('같은 물리량의 범위', 3)):
        for x, y in (('A', 'B'), ('A', 'C'), ('C', 'E'), ('B', 'E')):
            px, py = B.policy(x), B.policy(y)
            if px[index] != py[index] and all(px[i] == py[i] for i in (2, 3) if i != index):
                changed = sorted(k for k in set(answers[x]) | set(answers[y]) if answers[x].get(k) != answers[y].get(k))
                assert changed, (point, x, y, '갈래가 달라도 답이 같음')
                records.append({'decision': point, 'branches': [x, y], 'changed_answers': {k: [answers[x].get(k), answers[y].get(k)] for k in changed}})
    return records


def standard_ids(graph):
    """식별자 틀을 달리한 모델을 설비 코드 · 사내 품번 · 설비코드:태그로 되짚은 사본 — 식별자의 꼴과 상관없이 같은 대상 · 같은 연결인지 model_answers로 견주려고."""
    label = {n['props']['id']: n['labels'][0] for n in graph['nodes']}
    props = {n['props']['id']: n['props'] for n in graph['nodes']}
    owner = {r['b']: r['a'] for r in graph['rels'] if r['type'] == 'HAS_COMPONENT'}
    place = {r['b']: r['a'] for r in graph['rels'] if r['type'] == 'MONITORED_BY'}
    new = {}
    for i, l in label.items():
        if l == 'Asset':
            new[i] = props[i]['code']
        elif l == 'Part':
            new[i] = props[i]['part_no']
        elif l == 'Sensor':
            new[i] = f"{props[owner[place[i]]]['code']}:{props[i]['tag']}"
    assert len(set(new.values())) == len(new), '되짚은 식별자가 겹침'
    out = copy.deepcopy(graph)
    for n in out['nodes']:
        n['props']['id'] = new.get(n['props']['id'], n['props']['id'])
    for r in out['rels']:
        r['a'], r['b'] = new.get(r['a'], r['a']), new.get(r['b'], r['b'])
    return out


def other_identifiers(starter, work, same_as, exp):
    """식별자 틀을 달리한 사본 — 갈래 E의 판단 그대로, 식별자만 다른 꼴로 짓는다. 기대 답은 갈래 E의 것(설비 코드 · 품번으로 묻는 줄)을 그대로 쓰되
    교체 이력이 있는 구성 요소 자리의 항목은 그 설비의 원자료 이름으로 적는다(학생이 원자료 이름으로 적는 길)."""
    branch = 'E'
    new = work / 'new-other-ids'
    shutil.copytree(starter, new, ignore=shutil.ignore_patterns('__pycache__', 'output'))
    files = A.integrated_design(branch, ids=A.OTHER_IDS)
    files['결과/정한_것.csv'] = B.chosen_text(A.integrated_chosen(branch))
    (_, _, removed), = A.removed_rows()
    canon = B.CANON_NAME[D.REMOVED_PUMP[1]] + ' 실물'
    text = B.expect_design_text(branch)
    assert text.count(',' + canon + ',') == 1 and removed['구성요소'] + ' 실물' != canon, (canon, removed['구성요소'])
    files['결과/기대_답.csv'] = text.replace(',' + canon + ',', ',' + removed['구성요소'] + ' 실물,')
    put(new, files, True)
    for action in ACTIONS:
        (work / f'other-ids-{action}.txt').write_text(command(new, 'run.py', action, '--no-open'), encoding='utf-8')
    graph = json.loads((new / 'output/graph.json').read_text(encoding='utf-8'))
    ids = {n['props']['id'] for n in graph['nodes']}
    assert all(n['props']['id'] != n['props']['code'] for n in graph['nodes'] if n['labels'] == ['Asset']), '설비 식별자가 설비 코드와 같음 — 틀이 달라지지 않음'
    assert not ids & {'HYD-01', 'P-PMP-SEAL', 'HYD-01:TS1'}, sorted(ids)[:5]
    got, _ = model_answers(branch, standard_ids(graph))
    gap = V.diff({k: exp[k] for k in got}, got)
    assert not gap, ('other-ids', gap)
    rows = [r for block in blocks(new, 'query') if block['kind'] == 'compare' for r in block['rows']]
    assert rows and all(r['state'] == '같음' for r in rows), [r for r in rows if r['state'] != '같음']
    answers = {r['key']: r['cells'][0][1] for r in rows}
    assert answers == same_as, {k: (answers.get(k), same_as.get(k)) for k in set(answers) | set(same_as) if answers.get(k) != same_as.get(k)}
    command(new, 'run.py', 'check', '--no-open')
    return {'other_identifiers': A.OTHER_IDS, 'policy': B.policy(branch)[2:], 'model_equals_truth_by_field_values': True, 'answers_same_rows': len(rows),
            'answers_equal_branch': branch, 'item_written_with_raw_name': removed['구성요소'] + ' 실물', 'check': 'pass'}


def field_damage(folder, files):
    """빈 틀과 원자료를 일부러 망가뜨린다 — 제공 코드가 그 줄을 짚고 멈추는지(또는 잇지 않고 화면에 보이는지)."""
    out = []
    rel = P.convert(files['결과/관계.csv'])
    rules = P.convert(files['결과/quantity_rules.py'])
    (gone, now, _), = A.removed_rows()
    stops = {
        'cardinality-too-tight': ('app/features/relations.csv', rel.replace('HAS_COMPONENT,가진다,설비,구성 요소,1:N', 'HAS_COMPONENT,가진다,설비,구성 요소,1:1'), 'names', 'relations.csv:3: HAS_COMPONENT 카디널리티 1:1'),
        'cardinality-unknown': ('app/features/relations.csv', rel.replace('OBSERVES,잰다,센서,물리량,N:1', 'OBSERVES,잰다,센서,물리량,여럿'), 'relations', '카디널리티 「여럿」'),
        'relation-between-unlinked-classes': ('app/features/relations.csv', rel.replace('OBSERVES,잰다,센서,물리량,N:1', 'OBSERVES,잰다,설비,물리량,N:1'), 'relations', '이을 수 있는 짝은'),
        'relation-without-reading': ('app/features/relations.csv', rel.replace('OBSERVES,잰다,센서,물리량,N:1', 'OBSERVES,,센서,물리량,N:1'), 'relations', '읽는_말 칸이 비었습니다'),
        'at-least-one-unknown': ('app/features/relations.csv', rel.replace('OBSERVES,잰다,센서,물리량,N:1,시작마다', 'OBSERVES,잰다,센서,물리량,N:1,예'), 'relations', '적어도_하나 「예」'),
        'decision-without-file-line': ('app/features/decisions.csv', '\n'.join('같은 물리량의 범위,종류로 묶음,한 번에 모아 보려고,온도 센서가 한 묶음' if x.startswith('같은 물리량의 범위,') else x for x in P.convert(files['결과/정한_것.csv']).split('\n')),
                                       'quantities', '근거에 파일:줄이 없습니다'),
        'question-marks-instead-of-korean': ('app/features/classes.csv', P.convert(files['결과/클래스.csv']).replace('센서,' + A.MEANING['센서'] + ',', '센서,?? ??? ?? ?? ?? ??,'), 'classes', 'classes.csv:5: 한글이 「?」로 깨진 채 저장됐습니다'),
        'class-without-meaning': ('app/features/classes.csv', P.convert(files['결과/클래스.csv']).replace('센서,' + A.MEANING['센서'] + ',', '센서,,'), 'classes', '의미 칸이 비었습니다'),
        'property-column-not-in-table': ('app/features/properties.csv', P.convert(files['결과/속성.csv']).replace('센서,tag,태그,', '센서,tag,태그번호,'), 'properties', '원자료_칸 「태그번호」'),
        'identifier-from-blank-cell': ('app/features/classes.csv', P.convert(files['결과/클래스.csv']).replace('{설비코드}:{구성요소}', '{설비코드}:{구성요소}:{일련번호}'), 'names', '일련번호 칸이 이 행에서 비었습니다'),
        'past-unit-without-split': ('app/features/row_rules.csv', P.convert(files['결과/행_처리.csv']).replace(',빼기,', f',지난 실물:{now},'), 'names', '「지난 실물」은 구성 요소 자리와 그 실물을 나눌 때'),
        'removed-row-not-handled': ('app/features/row_rules.csv', '\n'.join(P.convert(files['결과/행_처리.csv']).split('\n')[:2]) + '\n', 'names', f'components.csv:{now}: 식별자 「'),
        'quantity-name-collision': ('app/features/quantity_rules.py', rules.replace("    return value_kind(members[0])\n", "    return '온도'\n"), 'quantities', '같은 물리량 이름 「온도」'),
        'units-mixed-in-one-quantity': ('app/features/quantity_rules.py', rules.replace('    return value_kind(a) == value_kind(b)', '    return True'), 'quantities', '바꾸는 법을 모릅니다'),
        'comma-overflow-in-classes': ('app/features/classes.csv', P.convert(files['결과/클래스.csv']).replace('설비코드 칸 — 설비마다 하나', '설비코드 칸, 설비마다 하나'), 'classes', 'classes.csv:3: 칸 수(5)'),
        'comma-overflow-in-expected': ('app/features/expected.csv', P.convert(files['결과/기대_답.csv']).replace(',없음,', ',없음,,', 1), 'expected', '보다 많습니다'),
        'empty-decision': ('app/features/decisions.csv', '\n'.join('같은 물리량의 범위,,,' if x.startswith('같은 물리량의 범위,') else x for x in P.convert(files['결과/정한_것.csv']).split('\n')),
                           'quantities', 'decisions.csv:'),
    }
    for name, (path, broken, action, want) in stops.items():
        target = folder / path
        original = target.read_bytes()
        assert broken != original.decode('utf-8'), (name, '손상이 적용되지 않음')
        target.write_text(broken, encoding='utf-8', newline='\n')
        try:
            text = command(folder, 'run.py', action, '--no-open', ok=False)
            assert want in text, (name, text[-600:])
        finally:
            target.write_bytes(original)
        if name == 'empty-decision':
            assert '같은 물리량의 범위' in text, text[-600:]
        out.append({'damage': name, 'stopped_with': want})
    # 표를 UTF-8이 아닌 글자표(cp949)로 저장하면: 조용히 바꿔 읽지 않고 그 파일:줄과 할 일을 한국어로 말하며 멈춘다(영어 codec 오류가 나오지 않는다)
    for name, path, action in (('classes-saved-as-cp949', 'app/features/classes.csv', 'classes'), ('expected-saved-as-cp949', 'app/features/expected.csv', 'expected'),
                               ('rules-saved-as-cp949', 'app/features/quantity_rules.py', 'quantities')):
        target = folder / path
        original = target.read_bytes()
        target.write_bytes(original.decode('utf-8').encode('cp949', errors='replace'))
        try:
            text = command(folder, 'run.py', action, '--no-open', ok=False)
            assert path + ':' in text and 'UTF-8로 저장되지 않은 글자가 있습니다' in text and 'codec' not in text, (name, text[-600:])
        finally:
            target.write_bytes(original)
        out.append({'damage': name, 'stopped_with': 'UTF-8로 저장되지 않은 글자가 있습니다', 'file_and_line': True})
    # 규칙 코드가 아직 빈 틀이면: 빈 오류 글이 아니라 무엇이 비었는지 말한다. 물리량 단계는 그 단계의 결정만 본다(자리와 실물 결정이 비어 있어도 돈다)
    target = folder / 'app/features/quantity_rules.py'
    original = target.read_bytes()
    target.write_text(P.convert(A.QUANTITY_RULES_BLANK), encoding='utf-8', newline='\n')
    try:
        text = command(folder, 'run.py', 'quantities', '--no-open')
        assert '아직 비어 있습니다' in text and 'quantity_rules.py' in text and 'same_quantity' in text, text[-400:]
    finally:
        target.write_bytes(original)
    out.append({'damage': 'blank-quantity-rules', 'says_what_is_blank': True})
    target = folder / 'app/features/decisions.csv'
    original = target.read_bytes()
    target.write_text('\n'.join('구성 요소 자리와 그 실물,,,' if x.startswith('구성 요소 자리와 그 실물,') else x for x in original.decode('utf-8').split('\n')), encoding='utf-8', newline='\n')
    try:
        command(folder, 'run.py', 'quantities', '--no-open')
        text = command(folder, 'run.py', 'parts', '--no-open', ok=False)
        assert 'decisions.csv:' in text and '구성 요소 자리와 그 실물' in text, text[-400:]
    finally:
        target.write_bytes(original)
    out.append({'damage': 'other-decision-empty', 'quantities_runs': True, 'model_writing_stops': True})
    # 교차표에 없는 표기: 짐작해 잇지 않고 「사내 품번을 찾지 못한 교체부품 칸」에 보인다. 그 부품의 사용 설비에서 그 설비가 빠져 대조가 「다름」이 된다.
    target = folder / 'data/components.csv'
    original = target.read_bytes()
    assert original.count(b',RF-10,') == 1
    target.write_bytes(original.replace(b',RF-10,', b',RF-99,'))
    try:
        lost = next(b for b in blocks(folder, 'parts') if b['kind'] == 'table' and '찾지 못한' in b['title'])
        assert len(lost['rows']) == 1 and 'RF-99' in json.dumps(lost['rows'], ensure_ascii=False), lost
        states = [r['state'] for b in blocks(folder, 'query') if b['kind'] == 'compare' for r in b['rows']]
        assert '다름' in states, states
    finally:
        target.write_bytes(original)
    out.append({'damage': 'part-code-not-in-alias-table', 'shown_unlinked': 1, 'answer_marked_different': True})
    command(folder, 'run.py', 'parts', '--no-open')
    return out


def schema_choices(folder, branch):
    """스키마 표에서 고른 것마다 결과가 따라오는가 — 갈래 A의 정답 사본에서 한 줄씩 바꿔 실행하고 되돌린다(자료는 바꾸지 않는다).
    걸리는 것은 모두 원자료에 원래 있는 사실이다: 한계가 빈 센서 행, 교체부품 칸이 빈 모터 행, 날짜로 적힌 설치일, 다른 단위로 적힌 한 줄."""
    import csv, io
    out = []
    features = folder / 'app/features'
    kept = {n: (features / n).read_bytes() for n in ('classes.csv', 'properties.csv', 'relations.csv', 'expected.csv', 'quantity_rules.py', 'row_rules.csv')}
    text = lambda n: kept[n].decode('utf-8')
    raw = lambda n: list(csv.DictReader(io.StringIO((folder / 'data' / n).read_text(encoding='utf-8-sig'))))
    sensors, comps, assets = raw('sensors.csv'), raw('components.csv'), raw('equipment.csv')
    states = lambda: [(r['key'], r['state'], r['cells'][0][1]) for b in blocks(folder, 'query') if b['kind'] == 'compare' for r in b['rows']]

    def tried(name, files, run):
        for n, t in files.items():
            assert t != text(n), (name, n, '바꾼 것이 적용되지 않음')
            (features / n).write_text(t, encoding='utf-8', newline='\n')
        try:
            out.append({'schema_choice': name, **run()})
        finally:
            for n, b in kept.items():
                (features / n).write_bytes(b)
            command(folder, 'run.py', 'parts', '--no-open')

    def cards(action, title):
        return [c for b in blocks(folder, action) if b['kind'] == 'cards' and b['title'].startswith(title) for c in b['items']]

    def required_limit():      # 한계를 필수로 정하면 한계 칸이 빈 센서 행이 모두 걸리고, 넣기 전 검증이 통과하지 못한다
        empty = sum(1 for r in sensors if not r['한계'])
        hit = cards('properties', '원자료와 어긋나는 속성')
        assert len(hit) == 1 and f'필수인데 빈 행 {empty}' in hit[0]['badge'], hit
        command(folder, 'run.py', 'parts', '--no-open')
        found = cards('parts', '원자료가 내 스키마 표와 어긋나는 곳')
        assert found and found[0]['badge'] == f'{empty}곳' and 'properties.csv:' in found[0]['lines'][0][1], found
        failed = command(folder, 'run.py', 'check', '--no-open', ok=False)
        assert '필수 속성 limit 없음' in failed, failed[-400:]
        return {'rows_caught': empty, 'check_fails': True}
    tried('limit-required', {'properties.csv': text('properties.csv').replace('센서,limit,한계,수,아니오,', '센서,limit,한계,수,예,')}, required_limit)

    def at_least_one_part():      # 구성 요소마다 부품이 적어도 하나라고 정하면 교체부품 칸이 빈 구성 요소가 걸린다
        empty = sum(1 for r in comps if not r['교체부품'])
        command(folder, 'run.py', 'parts', '--no-open')
        found = cards('parts', '원자료가 내 스키마 표와 어긋나는 곳')
        assert found and found[0]['badge'] == f'{empty}곳' and 'relations.csv:' in found[0]['lines'][0][1], found
        failed = command(folder, 'run.py', 'check', '--no-open', ok=False)
        assert '적어도 하나 어긋남' in failed and f'{empty}개' in failed, failed[-400:]
        return {'components_without_part': empty, 'check_fails': True}
    tried('uses-part-at-least-one', {'relations.csv': text('relations.csv').replace('USES_PART,쓴다,구성 요소,부품,N:M,없음,', 'USES_PART,쓴다,구성 요소,부품,N:M,시작마다,')}, at_least_one_part)

    def narrower_cardinality():      # 참조 답은 이론대로 N:M이다. 지금 자료에서 센 N:1로 적어도 받는다 — 둘 다 경고 없이 서고 넣기 전 검증을 통과한다(자료의 개수에 맞추라고 하지 않는다)
        first = blocks(folder, 'parts')
        assert first[0]['state'] == 'ok' and '넓게' not in json.dumps(first, ensure_ascii=False), first[0]
        command(folder, 'run.py', 'check', '--no-open')
        return {'verdict': first[0]['state'], 'check': 'pass'}
    base = blocks(folder, 'parts')
    assert base[0]['state'] == 'ok' and '넓게' not in json.dumps(base, ensure_ascii=False), base[0]      # N:M(참조 답) — 경고 없음
    tried('uses-part-n-to-1-as-counted-in-data', {'relations.csv': text('relations.csv').replace('USES_PART,쓴다,구성 요소,부품,N:M,', 'USES_PART,쓴다,구성 요소,부품,N:1,')}, narrower_cardinality)

    def too_tight():      # 「많아야 하나」로 정한 쪽에 실제로 둘 이상 이어지면 그 관계 표 줄과 원자료 줄을 짚고 멈춘다
        stopped = command(folder, 'run.py', 'parts', '--no-open', ok=False)
        assert 'relations.csv:' in stopped and 'USES_PART 카디널리티 1:1' in stopped and 'components.csv:' in stopped, stopped[-400:]
        return {'model_stops': True}
    tried('uses-part-1-to-1', {'relations.csv': text('relations.csv').replace('USES_PART,쓴다,구성 요소,부품,N:M,', 'USES_PART,쓴다,구성 요소,부품,1:1,')}, too_tight)

    def id_without_asset_code():      # 센서 식별자에서 설비 코드를 빼면 같은 태그의 센서가 한 식별자로 겹치고, 모델을 만들다 그 줄에서 멈춘다
        shown = blocks(folder, 'classes')
        clash = [c for b in shown if b['kind'] == 'cards' and b['title'] == '식별자가 겹친 곳' for c in b['items'] if c['badge'] == '센서']
        tags = [r['태그'] for r in sensors]
        want = len({t for t in tags if tags.count(t) > 1})
        assert shown[0]['state'] == 'warn' and len(clash) == want > 1, (shown[0], len(clash), want)
        stopped = command(folder, 'run.py', 'quantities', '--no-open', ok=False)
        assert 'sensors.csv:' in stopped and '이미 있습니다' in stopped, stopped[-400:]
        return {'identifiers_clashing': want, 'model_stops': True}
    tried('sensor-identifier-without-asset-code', {'classes.csv': text('classes.csv').replace('{설비코드}:{태그}', '{태그}')}, id_without_asset_code)

    def rule_by_written_name():      # 물리량 규칙을 「재는것 글자가 같으면 같다」로만 쓰면 사람마다 다르게 적은 이름이 따로 갈려 묶음 수와 질문 2의 답이 달라진다
        written = len({r['재는것'] for r in sensors})
        groups = next(b for b in blocks(folder, 'quantities') if b['kind'] == 'gather')
        assert len(groups['rows']) == written, (len(groups['rows']), written)
        command(folder, 'run.py', 'parts', '--no-open')
        off = [x for x in states() if x[1] != '같음']
        assert off and all(k.startswith('2 |') for k, _, _ in off), off
        return {'quantities': written, 'rows_different': len(off)}
    tried('quantity-rule-by-written-name-only', {'quantity_rules.py': "def same_quantity(a, b):\n    return a['재는것'] == b['재는것']\n\n\ndef quantity_name(members):\n    return members[0]['재는것']\n"}, rule_by_written_name)

    before = states()
    assert before and all(state == '같음' for _, state, _ in before), before

    def reversed_direction():      # 화살표를 거꾸로 긋고 카디널리티 · 적어도 하나를 함께 뒤집으면: 질문의 답은 그대로다(찾을 때는 거꾸로 따라가도 된다). 화면은 그 줄을 거꾸로 읽은 문장으로 보인다
        said = [dict(c['lines'])['문장으로 읽기'] for c in cards('relations', '관계마다 내가 정한 것') if c['badge'] == 'HAS_COMPONENT']
        assert len(said) == 1 and said[0].startswith('구성 요소 「') and '→ 가진다 → 설비 「' in said[0], said
        command(folder, 'run.py', 'parts', '--no-open')
        command(folder, 'run.py', 'check', '--no-open')
        got = states()
        assert got == before, [x for x in got if x not in before]
        return {'sentence_shown': said[0], 'answers_unchanged': len(got), 'model_and_check_pass': True}
    tried('has-component-reversed', {'relations.csv': text('relations.csv').replace('HAS_COMPONENT,가진다,설비,구성 요소,1:N,종료마다,', 'HAS_COMPONENT,가진다,구성 요소,설비,N:1,시작마다,')}, reversed_direction)

    def reversed_only_arrow():      # 화살표만 거꾸로 긋고 카디널리티를 그대로 두면: 「구성 요소 하나에 설비 여럿」이 되어 원자료의 실제 연결에서 걸린다
        stopped = command(folder, 'run.py', 'names', '--no-open', ok=False)
        assert 'relations.csv:3: HAS_COMPONENT 카디널리티 1:N' in stopped and '많아야 하나인데' in stopped, stopped[-400:]
        return {'model_stops_on': 'relations.csv:3'}
    tried('has-component-reversed-cardinality-kept', {'relations.csv': text('relations.csv').replace('HAS_COMPONENT,가진다,설비,구성 요소,1:N,종료마다,', 'HAS_COMPONENT,가진다,구성 요소,설비,1:N,종료마다,')}, reversed_only_arrow)

    def alias_not_kept():      # 구성 요소의 다른 이름을 속성으로 담지 않으면: 원자료 이름으로 적은 기대 답 줄은 찾지 못하고, 그 줄이 까닭을 말한다
        command(folder, 'run.py', 'parts', '--no-open')
        off = [x for x in states() if x[1] != '같음']
        assert len(off) == 1 and raw_name in off[0][0] and '「다른이름」 칸을 담은 속성이 없어' in off[0][2], off
        return {'rows_different': 1, 'row_says_why': True}
    (_, _, removed), = A.removed_rows()
    canon, raw_name = B.CANON_NAME[D.REMOVED_PUMP[1]] + ' 실물', removed['구성요소'] + ' 실물'
    assert text('expected.csv').count(',' + canon + ',') == 1 and canon != raw_name
    with_raw_name = text('expected.csv').replace(',' + canon + ',', ',' + raw_name + ',')
    tried('component-aliases-not-in-schema', {'properties.csv': '\n'.join(x for x in text('properties.csv').split('\n') if not x.startswith('구성 요소,aliases,')), 'expected.csv': with_raw_name}, alias_not_kept)

    def raw_name_found():      # 다른 이름을 담았으면 원자료 이름으로 적은 줄도 같은 구성 요소로 찾는다
        got = states()
        assert all(state == '같음' for _, state, _ in got), [x for x in got if x[1] != '같음']
        return {'all_rows_same': len(got)}
    tried('expected-item-written-with-raw-name', {'expected.csv': with_raw_name}, raw_name_found)

    def missing_property():      # 답에 필요한 원자료 칸을 담은 속성이 스키마에 없으면 그 질문은 답할 수 없다
        command(folder, 'run.py', 'parts', '--no-open')
        got = states()
        assert any('답할 수 없음(센서 클래스에 「태그」' in answer for _, _, answer in got), got
        return {'unanswerable_rows': sum('답할 수 없음' in a for _, _, a in got)}
    tried('sensor-tag-not-in-schema', {'properties.csv': '\n'.join(x for x in text('properties.csv').split('\n') if not x.startswith('센서,tag,태그,')) + ''}, missing_property)

    def unit_as_written():      # 센서의 수를 적힌 그대로 담으면 다른 단위로 적힌 줄의 값이 기준 단위로 적은 기대 답과 달라진다
        command(folder, 'run.py', 'parts', '--no-open')
        mixed = cards('quantities', '한 물리량에 단위가 섞여 담겼습니다')
        got = [x for x in states() if x[1] != '같음']
        assert mixed and got and all('MPa' in answer for _, _, answer in got), (mixed, got)
        return {'quantities_with_mixed_units': len(mixed), 'rows_different': len(got)}
    tried('sensor-numbers-as-written', {'properties.csv': text('properties.csv').replace(',수,아니오,기준 단위,', ',수,아니오,적힌 그대로,')}, unit_as_written)

    # 둘째 바퀴 — 새 질문(질문 4): 가동 중인 설비 가운데 가장 먼저 설치한 것. 기대 답은 원자료(설비 대장)에서 따로 세고, 세 질문만 보던 스키마에는 설치일 속성이 없다.
    assert '설비,installed,' not in text('properties.csv'), '세 질문만 답하는 참조 스키마에 둘째 바퀴의 속성이 미리 들어 있음'
    running = [r for r in assets if r['상태'] == '가동']
    first = min(r['설치일'] for r in running)
    want = ' · '.join(sorted(r['설비코드'] for r in running if r['설치일'] == first))
    asked = A.lap_question()
    assert asked[3] == want, (asked, want)
    line = P.convert(','.join(asked)) + '\n'
    lap_row = ','.join(A.LAP_ROW)
    assert lap_row.startswith('설비,installed,설치일,날짜,')
    with_lap = text('properties.csv') + P.convert(lap_row) + '\n'
    q4 = lambda: next((state, answer) for k, state, answer in states() if k.startswith('4 |'))
    without = text('properties.csv')
    lap = {}

    def wrong_type():      # 날짜로 적힌 칸을 수로 정하면 그 값이 수로 읽히지 않는다
        hit = cards('properties', '원자료와 어긋나는 속성')
        assert len(hit) == 1 and f'수로 읽을 수 없는 값 {len(assets)}' in hit[0]['badge'], hit
        command(folder, 'run.py', 'parts', '--no-open')
        assert '이어야 함' in command(folder, 'run.py', 'check', '--no-open', ok=False)
        return {'values_not_readable': len(assets), 'check_fails': True}
    tried('installed-as-number', {'properties.csv': with_lap.replace('설비,installed,설치일,날짜,', '설비,installed,설치일,수,')}, wrong_type)

    def asked_by_column_name():      # 물을_값에 속성 이름 대신 원자료 칸 이름을 적으면: 멈추지 않고 그 줄이 까닭을 말한다
        got = q4()
        assert got[0] != '같음' and '답할 수 없음(설비 클래스에 속성 「설치일」이 없음 — 물을_값과 항목에는 원자료 칸 이름이 아니라' in got[1], got
        return {'answer': got[1]}
    tried('second-lap-asked-with-column-name', {'expected.csv': text('expected.csv') + line.replace('설비.installed 가장 이른', '설비.설치일 가장 이른')}, asked_by_column_name)

    def unreadable_question():      # 꼴을 읽지 못하는 질문 4는 기대 답 표의 그 줄을 짚고 멈춘다
        stopped = command(folder, 'run.py', 'query', '--no-open', ok=False)
        assert f'expected.csv:{len(text("expected.csv").splitlines()) + 1}: 질문 4의 물을_값' in stopped, stopped[-400:]
        return {'stopped_with_line': True}
    tried('second-lap-question-not-readable', {'expected.csv': text('expected.csv') + line.replace('설비.installed 가장 이른', '가장 먼저 설치한 설비')}, unreadable_question)

    def no_property():
        command(folder, 'run.py', 'parts', '--no-open')
        lap['없음'] = q4()
        assert lap['없음'][0] != '같음' and '답할 수 없음(설비 클래스에 속성 「installed」' in lap['없음'][1], lap
        return {'answer': lap['없음'][1]}
    tried('second-lap-property-missing', {'expected.csv': text('expected.csv') + line}, no_property)

    def as_text():
        command(folder, 'run.py', 'parts', '--no-open')
        lap['글자'] = q4()
        assert lap['글자'][0] != '같음' and '견줄 수 없음' in lap['글자'][1] and '글자' in lap['글자'][1], lap
        return {'answer': lap['글자'][1]}
    tried('second-lap-date-kept-as-text', {'properties.csv': with_lap.replace('설비,installed,설치일,날짜,', '설비,installed,설치일,글자,'), 'expected.csv': text('expected.csv') + line}, as_text)

    def as_date():
        command(folder, 'run.py', 'parts', '--no-open')
        got = states()
        assert got and all(state == '같음' for _, state, _ in got), [x for x in got if x[1] != '같음']
        assert next(answer for k, _, answer in got if k.startswith('4 |')) == want
        command(folder, 'run.py', 'check', '--no-open')
        return {'answer': want, 'all_rows_same': len(got), 'check': 'pass'}
    tried('second-lap-date', {'properties.csv': with_lap, 'expected.csv': text('expected.csv') + line}, as_date)

    # 기대 답 줄의 꼴이 틀리면: 기대 답 화면이 그 줄(파일:줄)과 「무엇을 어느 칸에」를 짚고, 질문 대조도 같은 카드를 먼저 보인다. 꼴이 맞는 참조 답은 한 줄도 걸리지 않는다
    form_cards = lambda action: {c['title'].rsplit(':', 1)[1]: json.dumps(c['lines'], ensure_ascii=False) for b in blocks(folder, action) if b['kind'] == 'cards' and b['title'].startswith('꼴이 맞지 않는') for c in b['items']}
    clean = blocks(folder, 'expected')
    assert clean[0]['state'] == 'info' and not form_cards('expected'), clean[0]
    base = len(text('expected.csv').splitlines())
    qname = next(r[1] for r in csv.reader(io.StringIO(text('expected.csv'))) if r and r[0] == '2')
    sensor = f"{sensors[0]['설비코드']}:{sensors[0]['태그']}"

    def bad_form():
        hit = form_cards('expected')
        first = blocks(folder, 'expected')[0]
        assert first['state'] == 'bad' and '꼴이 맞지 않는 줄 4곳' in first['text'] and set(hit) == {str(base + 1), str(base + 2), str(base + 3), str(base + 4)}, (first, hit)
        # 조사는 받침에 맞게 — 받침 없는 값 뒤에 「이」를 붙이지 않는다(받기 시험 가10)
        assert '항목 「없는 구성 요소」는 구성 요소 목록' in hit[str(base + 3)] and '항목 「없는 구성」은 구성 요소 목록' in hit[str(base + 4)] and not any('」이 ' in v for v in hit.values()), hit
        assert '설비코드:태그가 아닙니다' in hit[str(base + 1)] and '항목 칸을 비우고' in hit[str(base + 1)], hit
        assert '물리량 이름이 아니라' in hit[str(base + 2)] and '구성 요소 이름이 아닙니다' in hit[str(base + 3)], hit
        assert set(form_cards('query')) == set(hit)
        lost = [k for k, state, _ in states() if state == '실제 없음']
        assert len(lost) >= 2, lost      # 꼴이 틀린 줄은 대조에서 「실제 없음」이 된다 — 그 까닭을 위 카드가 말한다
        return {'lines_pointed': sorted(hit), 'query_shows_same_card': True, 'rows_not_found_in_model': len(lost), 'particle_follows_final_consonant': True}
    tried('expected-rows-in-wrong-form', {'expected.csv': text('expected.csv') + f'2,{qname},센서 목록,{sensor},x\n2,{sensor},{qname},℃ · 48 · 65 · 상한,x\n1,{assets[0]["설비코드"]},없는 구성 요소,TS1,x\n1,{assets[0]["설비코드"]},없는 구성,TS1,x\n'}, bad_form)
    # 기대 답의 근거 줄을 틀린 줄로 적으면: 답 값은 맞아 질문 대조는 같음이지만, 기대 답 화면이 그 줄을 원자료에 대어 짚는다
    out.append({'schema_choice': 'expected-evidence-lines-wrong', **evidence_trial(folder)})

    # 속성 표 · 관계 표를 적기 전에 실행하면: 멈추지 않고, 누가 세어도 같은 개수(칸마다 빈 줄 · 클래스 짝마다 이어짐)를 원자료에서 세어 보인다
    def before_tables():
        shown = blocks(folder, 'properties')
        cols = next(b for b in shown if b['kind'] == 'table')
        blank = {(r[0], r[1]): r[3] for r in cols['rows']}
        assert shown[0]['state'] == 'info' and '아직 적지 않았습니다' in shown[0]['text'], shown[0]
        for (kind, col), name in ((('센서', '한계'), 'sensors.csv'), (('구성 요소', '교체부품'), 'components.csv')):      # 화면의 빈 줄 수 = 원자료에서 따로 센 수
            assert blank[(kind, col)] == sum(1 for r in raw(name) if not r[col].strip()), (kind, col, blank[(kind, col)])
        links = {c['title']: {x[0]: x[1] for x in c['lines']} for b in blocks(folder, 'relations') if b['kind'] == 'cards' for c in b['items']}
        no_part = sum(1 for r in comps if not r['교체부품'].strip())
        assert links['구성 요소 · 부품']['부품이 하나도 없는 구성 요소'].startswith(f'{no_part}곳'), links['구성 요소 · 부품']
        assert links['설비 · 구성 요소']['구성 요소 하나에 이어진 설비'] == '가장 많은 곳 1개', links
        # 같은 수인 곳이 여럿이면 하나만 대지 않고 모두 댄다(받기 시험 v63 가15) — 설비마다 구성 요소 자리 수를 원자료에서 따로 센다
        seats = {}
        for r in comps:
            seats.setdefault(r['설비코드'], set()).add(r['구성요소'])
        top = max(len(v) for v in seats.values())
        tied = sorted(a for a, v in seats.items() if len(v) == top)
        assert len(tied) > 1, ('구성 요소가 가장 많은 설비가 하나뿐 — 이 시험의 전제가 깨짐', tied)
        assert links['설비 · 구성 요소']['설비 하나에 이어진 구성 요소'] == f'가장 많은 곳 {top}개 — ' + ', '.join(tied), links['설비 · 구성 요소']
        return {'blank_limit_rows': blank[('센서', '한계')], 'components_without_part': no_part, 'pairs_shown': sorted(links), 'assets_with_most_components': tied}
    tried('tables-not-written-yet', {'properties.csv': '\n'.join(text('properties.csv').splitlines()[:2]) + '\n', 'relations.csv': '\n'.join(text('relations.csv').splitlines()[:2]) + '\n'}, before_tables)

    # 모델에 담지 않기로 한 줄(행 처리의 「빼기」)은 속성 화면의 빈 줄에도 세지 않는다 — 속성 화면(표를 적기 전 · 뒤)과 넣기 전 검증이 같은 줄을 본다(받기 시험 v63 나6)
    gone = next(n for n, r in enumerate(sensors, 2) if not r['한계'])      # 한계 칸이 빈 센서 줄 하나를 빼기로 적는다
    empty = sum(1 for r in sensors if not r['한계'])
    rule = text('row_rules.csv').rstrip('\n') + f'\nsensors.csv,{gone},빼기,시험\n'

    def dropped_after():      # 표를 적은 뒤: 한계를 필수로 → 속성 화면의 빈 행 수 = 넣기 전 검증에서 걸리는 줄 수(뺀 줄은 둘 다 세지 않음)
        hit = cards('properties', '원자료와 어긋나는 속성')
        assert len(hit) == 1 and f'필수인데 빈 행 {empty - 1}' in hit[0]['badge'] and f'sensors.csv:{gone},' not in dict(map(tuple, hit[0]['lines']))['빈 원자료 행'] + ',', hit
        command(folder, 'run.py', 'parts', '--no-open')
        found = cards('parts', '원자료가 내 스키마 표와 어긋나는 곳')
        assert found and found[0]['badge'] == f'{empty - 1}곳', found
        return {'dropped_row': f'sensors.csv:{gone}', 'blank_rows_on_properties_screen': empty - 1, 'rows_caught_before_load': empty - 1}
    tried('dropped-row-not-counted-as-blank', {'row_rules.csv': rule, 'properties.csv': text('properties.csv').replace('센서,limit,한계,수,아니오,', '센서,limit,한계,수,예,')}, dropped_after)

    def dropped_before():      # 표를 적기 전: 센서 줄 수와 한계 칸의 빈 줄 수에서 뺀 줄이 빠진다
        cols = next(b for b in blocks(folder, 'properties') if b['kind'] == 'table')
        row = next(r for r in cols['rows'] if (r[0], r[1]) == ('센서', '한계'))
        assert (row[2], row[3]) == (len(sensors) - 1, empty - 1) and f'sensors.csv:{gone},' not in row[4] + ',', row
        assert '적은 줄은 뺌' in cols['note'], cols['note']
        return {'sensor_rows_counted': row[2], 'blank_limit_rows': row[3]}
    tried('dropped-row-not-counted-before-tables', {'row_rules.csv': rule, 'properties.csv': '\n'.join(text('properties.csv').splitlines()[:2]) + '\n'}, dropped_before)
    command(folder, 'run.py', 'check', '--no-open')
    return out


def fresh_packages(starter, work):
    records = []
    with zipfile.ZipFile(starter.with_suffix('.zip')) as archive:
        archive.extractall(work / 'received')
    folder = work / 'received' / starter.name
    assert not (folder / 'output').exists()
    command(folder, 'run.py', '--no-open')
    data = json.loads((folder / 'output/result.json').read_text(encoding='utf-8'))
    assert data['action'] == 'sources' and data['blocks']
    assert not any(block['kind'] == 'error' for block in data['blocks'])
    # 받은 그대로는 빈 틀이 비어 있어, 모델을 만드는 기능이 채울 파일을 짚고 멈춘다(빈 틀을 실행된 것처럼 보이지 않는다)
    stopped = command(folder, 'run.py', 'names', '--no-open', ok=False)
    assert 'app/features/classes.csv' in stopped, stopped[-400:]
    # 모델을 만들기 전에 질문별 대조를 실행하면 만들 명령을 대고 멈춘다(파이썬 원문 오류 · 학생 PC의 절대 경로가 화면에 남지 않는다)
    early = command(folder, 'run.py', 'query', '--no-open', ok=False)
    assert '아직 모델이 없습니다' in early and 'python run.py parts' in early, early[-400:]
    assert 'Errno' not in early and str(work.anchor) not in early and str(folder.parent.name) not in early, early[-400:]
    assert not (folder / 'app/features/name_rules.py').exists(), '구성 요소 이름 맞추기는 제공 코드가 한다 — 학생 빈 틀이 남아 있음'
    records.append({'fresh_starter': True, 'first_command': 'python run.py --no-open', 'actual_blocks': len(data['blocks']), 'blank_feature_stops': True, 'query_before_model_stops_with_next_command': True})
    # 완성본은 검증 사본에서는 랩 폴더 옆에, 정본에서는 회차의 완성본/ 폴더에 있다
    archive = next((p for p in (starter.parent / (starter.name + '-completed.zip'), starter.parent.parent / '완성본' / (starter.name + '-completed.zip')) if p.exists()), None)
    if archive:
        with zipfile.ZipFile(archive) as z:
            z.extractall(work / 'received-completed')
        folder = work / 'received-completed' / starter.name
        before = {name: (folder / 'output' / name).read_bytes() for name in ('graph.json', 'schema.json')}
        for action in ('parts', 'query', 'check'):
            command(folder, 'run.py', action, '--no-open')
        assert all((folder / 'output' / name).read_bytes() == data for name, data in before.items())
        rows = [r for block in blocks(folder, 'query') if block['kind'] == 'compare' for r in block['rows']]
        asked = sorted({r['key'].split(' |')[0] for r in rows})
        assert asked == ['1', '2', '3', '4'] and all(r['state'] == '같음' for r in rows), (asked, [r for r in rows if r['state'] != '같음'])      # 완성본은 가이드의 끝 상태(둘째 바퀴의 질문 4까지)
        records.append({'fresh_completed': True, 'regenerated_models_equal': True, 'check': 'pass', 'questions_answered': asked, 'rows_same': len(rows)})
    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('folder', type=Path)
    args = parser.parse_args()
    base = (ROOT / '작업/검사/session2-projects').resolve()
    base.mkdir(parents=True, exist_ok=True)
    with D.for_course('통합반'), tempfile.TemporaryDirectory(prefix='trials-', dir=base) as temp:
        work = Path(temp).resolve()
        assert work.is_relative_to(base) and work != base
        records = student_condition_selftest(args.folder.resolve(), work)
        records += ontology(args.folder.resolve(), work)
        records += fresh_packages(args.folder.resolve(), work)
        report = base / 'ontology-results.json'
        report.write_text(json.dumps({'kind': '강사 참조 실행; 학생 AI 시험 아님', 'records': records}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{len(records)}개 실행 대조 통과: {report}')


if __name__ == '__main__':
    main()
