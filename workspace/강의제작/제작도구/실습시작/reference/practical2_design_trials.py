"""실전반 2회차 설계 랩(공장 규모 + 구매팀 응용)의 강사 참조 시험 — 갈래마다 정답 내용을 새 사본에 넣고 실제로 실행해 판정한다. AI 호출 없음.

판정(통합반 시험 reference/session2_project_trials.py와 같은 틀 · 같은 학생 조건):
- 설비 쪽 갈래 A · B · C · E마다 만든 모델 전체를 독립 기대 값(session2_factory_answers.literal — 자료 생성기의 정의에서 바로 센 값)과 견주고, 결과 화면의 대조가 줄마다 같음이다.
  결정 지점마다 갈래가 다르면 그 질문의 답이 실제로 다르다.
- 구매팀 응용: 셋째 결정의 갈래 셋(늦은 줄 · 이른 줄 · 줄마다)마다 공급사 · 견적을 담은 모델을 독립 기대 값(purchase_literal)과 견주고, 질문 5의 답이 갈래마다 실제로 다르다.
- 공장 규모 자료에만 있는 사실과 응용에서, 그럴듯하지만 틀린 선택을 하면 결과가 따라 바뀐다(wrong_choices) — 걸리는 것은 자료의 사실뿐이다.
- 모델을 망가뜨리면(ID 중복 · 끝점 없음 · 관계 방향) 구조 검사가 잡고, 학생 ZIP과 완성본 ZIP을 새 폴더에 풀어 명령이 돈다.
사용: python reference/practical2_design_trials.py <ontology-lab 폴더> [--out <결과 json>]
"""
from pathlib import Path
import argparse
import copy
import csv
import io
import json
import shutil
import sys
import tempfile
import zipfile

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_labs as B
import data_session2 as D
import session2_answers as A
import session2_factory_answers as FA
import session2_project as P
import verify_reference as V
from lab_package import ROOT
import session2_project_trials as T

ACTIONS = ['sources', 'expected', 'classes', 'properties', 'relations', 'names', 'quantities', 'parts', 'query', 'check']
SUPPLY_ACTIONS = ['supply', 'check', 'query', 'purchase']
UNIT = lambda u: 'L/min' if u == 'l/min' else u      # 같은 단위의 두 표기


def fill(folder, branch, supply=None, **changes):
    files = FA.design(branch, supply, **changes)
    files['결과/정한_것.csv'] = B.chosen_text(FA.chosen(branch, supply))
    files['결과/기대_답.csv'] = FA.expect_text(branch, supply)
    T.put(folder, files, True)
    return files


def new_copy(starter, work, name):
    target = work / name
    shutil.copytree(starter, target, ignore=shutil.ignore_patterns('__pycache__', 'output'))
    return target


def compare_rows(folder):
    return [r for block in T.blocks(folder, 'query') if block['kind'] == 'compare' for r in block['rows']]


def model_answers(branch, graph):
    """학생 꼴 모델을 literal과 같은 꼴로 읽는다 — 구성 요소 이름은 그 설비 모델의 품목 키(build_labs.comp_key), 물리량 이름은 강사 참조의 이름표로 되짚는다."""
    pol = B.POLICY[branch]
    qid_of = {name: qid for qid, (name, _) in B.quantities_of(pol).items()}
    label = {n['props']['id']: n['labels'][0] for n in graph['nodes']}
    props = {n['props']['id']: n['props'] for n in graph['nodes']}
    by = {}
    for r in graph['rels']:
        by.setdefault(r['type'], []).append(r)
    owner = {r['b']: r['a'] for r in by['HAS_COMPONENT']}
    key = lambda cid: B.comp_key(props[cid]['name'], {k for k, *_ in D.MODEL_COMPONENTS[props[owner[cid]]['model']]})
    sensors, members, sprops, parts, units = {}, {}, {}, {a: {} for a, l in label.items() if l == 'Asset'}, {}
    for r in by['MONITORED_BY']:
        sensors.setdefault(owner[r['a']], {}).setdefault(key(r['a']), []).append(props[r['b']]['tag'])
    for r in by.get('ASSET_MONITORED_BY', []):
        sensors.setdefault(r['a'], {}).setdefault('(설비 전체)', []).append(props[r['b']]['tag'])
    for r in by['OBSERVES']:
        qid, s = qid_of[props[r['b']]['name']], props[r['a']]
        members.setdefault(qid, []).append(r['a'])
        sprops[r['a']] = [qid, UNIT(s.get('unit')), s.get('normal'), s.get('limit'), {'상한': 'upper', '하한': 'lower'}.get(s.get('limit_direction'))]
    for cid, aid in owner.items():
        parts[aid][key(cid)] = next((r['b'] for r in by['USES_PART'] if r['a'] == cid), None)
    for r in by.get('INSTALLED_UNIT', []):
        units.setdefault(f'{owner[r["a"]]}:{key(r["a"])}', []).append([props[r['b']]['serial'], r['props']['current']])
    return {'sensors_by_asset': {a: {k: sorted(v) for k, v in sorted(d.items())} for a, d in sorted(sensors.items())},
            'quantity_members': {k: sorted(v) for k, v in sorted(members.items())}, 'sensor_props': dict(sorted(sprops.items())),
            'parts_by_asset': {a: dict(sorted(d.items())) for a, d in sorted(parts.items())}, 'units': {k: sorted(v) for k, v in sorted(units.items())}}


def supply_answers(graph):
    """모델의 견적을 {(공급사, 사내 품번): 답 글}로 — 기준일에 유효기한이 남은 견적만, 한 쌍에 여럿이면 견적일 차례."""
    props = {n['props']['id']: n['props'] for n in graph['nodes']}
    offers = {r['b']: r['a'] for r in graph['rels'] if r['type'] == 'OFFERS'}
    out = {}
    for r in graph['rels']:
        if r['type'] != 'QUOTES_PART':
            continue
        q = props[r['a']]
        if q['valid_until'] < D.REF_DATE:
            continue
        out.setdefault((props[offers[r['a']]]['name'], props[r['b']]['part_no']), []).append(
            (q['quote_date'], ' · '.join([q['approval'], '%g' % q['price_manwon'], '%g' % q['defect_rate'], '%g' % q['lead_days']])))
    return {k: ' / '.join(x[1] for x in sorted(v)) for k, v in out.items()}


def base(starter, work):
    records, answers = [], {}
    for branch in FA.BRANCHES:
        new = new_copy(starter, work, 'new-' + branch)
        fill(new, branch)
        for action in ACTIONS:
            (work / f'{branch}-{action}.txt').write_text(T.command(new, 'run.py', action, '--no-open'), encoding='utf-8')
        graph = json.loads((new / 'output/graph.json').read_text(encoding='utf-8'))
        exp = FA.literal(branch)
        exp['sensor_props'] = {k: [v[0], UNIT(v[1]), *v[2:]] for k, v in exp['sensor_props'].items()}
        got = model_answers(branch, graph)
        gap = V.diff(exp, got)
        assert not gap, (branch, gap[:8] if isinstance(gap, list) else gap)
        rows = compare_rows(new)
        assert rows and all(r['state'] == '같음' for r in rows), (branch, [r for r in rows if r['state'] != '같음'])
        original = (new / 'output/graph.json').read_bytes()
        T.command(new, 'run.py', 'parts', '--no-open')
        assert original == (new / 'output/graph.json').read_bytes(), (branch, '같은 빈 틀로 다시 만든 모델이 다름')
        answers[branch] = {r['key']: r['cells'][0][1] for r in rows}
        linked = sum(1 for a in got['parts_by_asset'].values() for p in a.values() if p)
        records.append({'branch': branch, 'policy': B.POLICY[branch][2:], 'nodes': len(graph['nodes']), 'relations': len(graph['rels']), 'model_equals_literal': True,
                        'repeat_equal': True, 'answers_same_rows': len(rows), 'components_linked_to_part': linked,
                        'components_not_linked': sum(len(a) for a in got['parts_by_asset'].values()) - linked})
        if branch == 'A':
            for label in ('duplicate-id', 'missing-endpoint', 'reverse-direction'):
                broken = copy.deepcopy(graph)
                if label == 'duplicate-id':
                    broken['nodes'].append(copy.deepcopy(broken['nodes'][0]))
                elif label == 'missing-endpoint':
                    broken['rels'][0]['b'] = 'missing-endpoint'
                else:
                    broken['rels'][0]['a'], broken['rels'][0]['b'] = broken['rels'][0]['b'], broken['rels'][0]['a']
                (new / 'output/graph.json').write_text(json.dumps(broken, ensure_ascii=False), encoding='utf-8')
                out = T.command(new, 'run.py', 'check', '--no-open', ok=False)
                assert '구조 확인 필요' in out, out
                T.command(new, 'run.py', 'parts', '--no-open')
                T.command(new, 'run.py', 'check', '--no-open')
                records.append({'broken': label, 'rejected': True, 'parts_then_check_recovers': True})
    for point, index in (('구성 요소 자리와 그 실물', 2), ('같은 물리량의 범위', 3)):
        for x, y in (('A', 'B'), ('A', 'C'), ('C', 'E'), ('B', 'E')):
            px, py = B.POLICY[x], B.POLICY[y]
            if px[index] != py[index] and all(px[i] == py[i] for i in (2, 3) if i != index):
                changed = sorted(k for k in set(answers[x]) | set(answers[y]) if answers[x].get(k) != answers[y].get(k))
                assert changed, (point, x, y, '갈래가 달라도 답이 같음')
                records.append({'decision': point, 'branches': [x, y], 'changed_answers': {k: [answers[x].get(k), answers[y].get(k)] for k in changed}})
    return records


def supply(starter, work):
    records, answers = [], {}
    for mode in FA.SUPPLY_BRANCHES:
        new = new_copy(starter, work, 'supply-' + mode.replace(' ', ''))
        fill(new, 'E', mode)
        for action in SUPPLY_ACTIONS:
            (work / f'supply-{mode}-{action}.txt').write_text(T.command(new, 'run.py', action, '--no-open'), encoding='utf-8')
        graph = json.loads((new / 'output/graph.json').read_text(encoding='utf-8'))
        got, exp = supply_answers(graph), FA.purchase_literal(mode)
        assert got == exp, (mode, {k: (exp.get(k), got.get(k)) for k in set(exp) | set(got) if exp.get(k) != got.get(k)})
        base_got = model_answers('E', graph)      # 공급을 더해도 설비 쪽 모델은 그대로다
        base_exp = FA.literal('E')
        base_exp['sensor_props'] = {k: [v[0], UNIT(v[1]), *v[2:]] for k, v in base_exp['sensor_props'].items()}
        assert not V.diff(base_exp, base_got), mode
        rows = compare_rows(new)
        assert rows and all(r['state'] == '같음' for r in rows), (mode, [r for r in rows if r['state'] != '같음'])
        table = next(b for b in T.blocks(new, 'purchase') if b['kind'] == 'table')
        assert all(r[5].count('.csv:') == 2 for r in table['rows'] if r[3] and ' / ' not in r[4]), (mode, '조회 결과의 근거 줄')
        quotes = sum(1 for n in graph['nodes'] if n['labels'] == ['Quote'])
        answers[mode] = {r['key']: r['cells'][0][1] for r in rows if r['key'].startswith('5 |')}
        records.append({'supply_branch': mode, 'nodes': len(graph['nodes']), 'relations': len(graph['rels']), 'quotes': quotes,
                        'suppliers': sum(1 for n in graph['nodes'] if n['labels'] == ['Supplier']), 'pairs_equal_literal': len(got),
                        'answers_same_rows': len(rows), 'purchase_table_rows': len(table['rows']),
                        'asked_pair': answers[mode].get(f'5 | {FA.ASKED_PART} | {FA.ASKED_PART}/A정밀')})
    told = {m: a[f'5 | {FA.ASKED_PART} | {FA.ASKED_PART}/A정밀'] for m, a in answers.items()}
    assert len(set(told.values())) == 3, ('셋째 결정의 갈래가 달라도 구매팀 질문의 답이 같음', told)
    records.append({'decision': FA.DECISION_POINTS[2], 'changed_answer': told})
    return records


def stop(folder, action, *needles):
    out = T.command(folder, 'run.py', action, '--no-open', ok=False)
    for n in needles:
        assert n in out, (action, n, out[-800:])
    return out.strip().splitlines()[1][:160] if len(out.strip().splitlines()) > 1 else out[:160]


def wrong_choices(starter, work):
    """그럴듯하지만 틀린 선택 — 자료는 한 글자도 바꾸지 않는다(끝의 고의 손상 하나만 자료 사본을 바꾼다)."""
    records = []
    f = FA.facts()

    def case(name, run, **changes):
        new = new_copy(starter, work, 'wrong-' + name)
        fill(new, 'E', changes.pop('supply', None), **changes)
        records.append({'wrong': name, 'result': run(new)})

    def findings(new, kind, count):
        T.command(new, 'run.py', 'parts', '--no-open')
        out = T.command(new, 'run.py', 'check', '--no-open', ok=False)
        cards = [i for b in json.loads((new / 'output/result.json').read_text(encoding='utf-8'))['blocks'] if b['kind'] == 'cards' and '어긋나는' in b['title'] for i in b['items']]
        hit = [c for c in cards if c['title'] == kind]
        assert hit and hit[0]['badge'] == f'{count}곳', (kind, [(c['title'], c['badge']) for c in cards], out[-400:])
        return f'검증 실패 — {kind} {count}곳'

    drop = lambda name: (lambda rows: [r for r in rows if r[0] != name])
    # 설비에 바로 붙는 센서를 잇는 관계를 두지 않음 → 그 줄을 짚고 멈춤
    case('no-asset-sensor-relation', lambda n: stop(n, 'quantities', f'sensors.csv:{f["wide"][0]}', '설비 전체'), relations=drop('ASSET_MONITORED_BY'))
    # 센서마다 구성 요소가 적어도 하나(통합반 자료에서는 맞던 선택) → 설비 전체 센서 넷이 걸림
    case('sensor-needs-component', lambda n: findings(n, '「적어도 하나」인데 관계가 없는 대상', len(f['wide'])),
         relations=lambda rows: [[*r[:5], '종료마다', r[6]] if r[0] == 'MONITORED_BY' else r for r in rows])
    # 단위를 필수로(통합반 자료에서는 맞던 선택) → 단위 칸이 빈 줄이 걸림
    case('unit-required', lambda n: findings(n, '필수 속성이 빈 행', len(f['blank_unit'])),
         properties=lambda rows: [[*r[:4], '예', *r[5:]] if r[:2] == ['센서', 'unit'] else r for r in rows])
    # 다시 적힌 센서 줄을 처리하지 않음 → 겹친 식별자로 멈춤
    first, again = f['repeats'][0]
    case('repeated-sensor-row-kept', lambda n: stop(n, 'quantities', f'sensors.csv:{again}', '이미 있습니다'), rows=lambda rows: [r for r in rows if r[0] != '센서_목록.csv'])

    def other_row(new):      # 다시 적힌 줄 가운데 다른 쪽을 뺌 → 한계구분이 빈 줄이 남아 질문 2의 값이 달라짐
        T.command(new, 'run.py', 'parts', '--no-open')
        bad = [r for r in compare_rows(new) if r['state'] != '같음']
        assert bad and all(r['key'].startswith('2 |') for r in bad), bad      # 남긴 줄은 재는것을 다른 말로 적었고 한계구분이 비어 있다 — 내 규칙이 그 이름을 모르면 다른 물리량이 된다
        return f'질문 2 대조 {len(bad)}줄이 같음이 아님 — ' + ' / '.join(f'{r["key"]}: {r["state"]}(기대 「{r["cells"][0][0]}」 · 실제 「{r["cells"][0][1]}」)' for r in bad)
    case('repeated-sensor-other-row-dropped', other_row, rows=lambda rows: [[r[0], first, *r[2:]] if r[0] == '센서_목록.csv' else r for r in rows])

    def lone_cards(folder):
        """넣기 전 검증 화면의 「관계가 하나도 이어지지 않은 인스턴스」 카드에 나온 것들."""
        return [i['title'] for b in T.blocks(folder, 'check') if b['kind'] == 'cards' and '이어지지 않은 인스턴스' in b['title'] for i in b['items']]

    def legacy(new):      # 옛 코드 설비 줄을 그대로 둠 → 멈추지는 않지만, 넣기 전 검증 화면이 아무것도 이어지지 않은 그 설비를 사실로 짚는다(같은 설비인지는 말하지 않는다)
        T.command(new, 'run.py', 'parts', '--no-open')
        graph = json.loads((new / 'output/graph.json').read_text(encoding='utf-8'))
        assets = [n['props']['id'] for n in graph['nodes'] if n['labels'] == ['Asset']]
        lone = [a for a in assets if not any(a in (r['a'], r['b']) for r in graph['rels'])]
        shown = lone_cards(new)
        same = all(r['state'] == '같음' for r in compare_rows(new))
        right = new_copy(starter, work, 'right-for-legacy')      # 옳게 뺀 사본에는 그 설비가 카드에 없다
        fill(right, 'E')
        T.command(right, 'run.py', 'parts', '--no-open')
        clean = lone_cards(right)
        old_code = dict(B.numbered('설비_대장.csv'))[f['legacy'][0]]['설비코드']
        assert len(assets) == len(D.ASSETS) + 1 and lone == [old_code] and same, (assets, lone)
        assert any(f'「{old_code}」' in x and x.startswith('설비') for x in shown), shown
        assert not any(old_code in x for x in clean) and len(shown) == len(clean) + 1, (shown, clean)
        return (f'멈추지 않고 기대 답 대조도 같음이지만, 넣기 전 검증 화면의 「관계가 하나도 이어지지 않은 인스턴스」 카드가 {len(shown)}개로 늘고 {next(x for x in shown if old_code in x)}을 짚음 '
                f'— 설비 {len(assets)}대(자료의 설비는 {len(D.ASSETS)}대). 옳게 뺀 사본의 카드는 {len(clean)}개({" · ".join(clean) or "없음"})이고 그 설비가 없다')
    case('legacy-asset-row-kept', legacy, rows=lambda rows: [r for r in rows if r[0] != '설비_대장.csv'])

    # ── 구매팀 응용
    quote = lambda keep: (lambda rows: [r for r in rows if r[0] != D.QUOTE_FILE or keep(r)])
    (pair, lines), = f['several'].items()
    case('quotes-no-row-rules', lambda n: stop(n, 'supply', f'{P.NAMES[D.QUOTE_FILE]}:', '이미 있습니다'), supply='늦은 줄', rows=quote(lambda r: False))
    case('quotes-only-expired-dropped', lambda n: stop(n, 'supply', f'{P.NAMES[D.QUOTE_FILE]}:{max(lines)}', '이미 있습니다'), supply='늦은 줄', rows=quote(lambda r: r[1] in f['expired']))

    def no_valid_until(new):      # 유효기한을 속성으로 담지 않음 → 기준일로 거를 수 없어 답하지 못함
        T.command(new, 'run.py', 'supply', '--no-open')
        rows = [r for r in compare_rows(new) if r['key'].startswith('5 |')]
        stuck = [r for r in rows if '답할 수 없음' in r['cells'][0][1] or r['state'] != '같음']
        assert stuck and any('유효기한' in r['cells'][0][1] for r in rows) or any('유효기한' in str(b) for b in T.blocks(new, 'query')), rows[:3]
        return f'질문 5 대조 {len(rows)}줄 가운데 {len([r for r in rows if r["state"] != "같음"])}줄이 같음이 아님 — 「답할 수 없음(견적 클래스에 「유효기한」 칸을 담은 속성이 없음)」'
    case('quote-without-valid-until', no_valid_until, supply='늦은 줄', properties=lambda rows: [r for r in rows if r[:2] != ['견적', 'valid_until']])

    def expired_kept(new):      # 받은 날마다 따로 두면서 기한 지난 견적도 그대로 담음 → 질문 5는 유효기한으로 걸러 답이 같다
        T.command(new, 'run.py', 'supply', '--no-open')
        graph = json.loads((new / 'output/graph.json').read_text(encoding='utf-8'))
        quotes = sum(1 for n in graph['nodes'] if n['labels'] == ['Quote'])
        assert quotes == len(D.QUOTES) and supply_answers(graph) == FA.purchase_literal('줄마다')
        assert all(r['state'] == '같음' for r in compare_rows(new))
        return f'견적 {quotes}건(기한 지난 {len(f["expired"])}건 포함)이 모두 들어가고, 질문 5는 유효기한으로 걸러 기대 답과 같음'
    case('per-date-with-expired-kept', expired_kept, supply='줄마다')

    def only_supplier(new):      # 공급사 클래스만 적고 견적은 적지 않음
        text = (new / 'app/features/classes.csv').read_text(encoding='utf-8')
        (new / 'app/features/classes.csv').write_text('\n'.join(x for x in text.splitlines() if not x.startswith('견적,')) + '\n', encoding='utf-8', newline='\n')
        return stop(new, 'relations', '공급 조건을 담으려면')
    case('supplier-without-quote', only_supplier, supply='늦은 줄')

    def decision_blank(new):
        path = new / 'app/features/decisions.csv'
        lines_ = path.read_text(encoding='utf-8').splitlines()
        path.write_text('\n'.join(lines_[:-1] + [FA.DECISION_POINTS[2] + ',,,']) + '\n', encoding='utf-8', newline='\n')
        return stop(new, 'supply', 'decisions.csv', FA.DECISION_POINTS[2])
    case('supply-decision-blank', decision_blank, supply='늦은 줄')

    def status_from_quote_sheet(new):      # 승인 상태 대신 견적표의 「승인공급사」 칸을 담음 → SCM 등록과 다른 줄에서 답이 달라짐
        T.command(new, 'run.py', 'supply', '--no-open')
        rows = [r for r in compare_rows(new) if r['key'].startswith('5 |')]
        bad = [r for r in rows if r['state'] != '같음']
        assert bad and all('/' in r['key'].split('|')[2] for r in bad), rows[:3]
        return f'질문 5 대조 {len(rows)}줄 가운데 {len(bad)}줄 다름 — 예: {bad[0]["key"]} 기대 「{bad[0]["cells"][0][0]}」 · 실제 「{bad[0]["cells"][0][1]}」'
    case('approval-from-quote-sheet', status_from_quote_sheet, supply='늦은 줄',
         properties=lambda rows: [[r[0], r[1], '승인공급사', *r[3:]] if r[:2] == ['견적', 'approval'] else r for r in rows])

    # 고의 손상(자료 사본만): 한계 칸의 단위 글이 그 행의 단위 칸과 다르면 수로 읽지 않는다 — 단위가 붙은 값을 아무 글이나 떼고 읽는 것이 아님을 본다
    def other_unit(new):
        path = new / 'data/sensors.csv'
        text = path.read_text(encoding='utf-8')
        assert text.count('130 bar') == 1
        path.write_text(text.replace('130 bar', '130 psi'), encoding='utf-8', newline='')
        return findings(new, '자료형에 맞지 않는 값', 1)
    case('damaged-limit-with-other-unit', other_unit)
    return records


def packages(starter, work):
    records = []
    archive = starter.with_suffix('.zip')
    for name, path, actions in (('new-zip', archive, ['sources']),
                                ('completed-zip', next(p for p in (starter.parent / 'ontology-lab-completed.zip', starter.parent.parent / '완성본/ontology-lab-completed.zip') if p.is_file()), SUPPLY_ACTIONS)):
        target = work / name
        with zipfile.ZipFile(path) as z:
            z.extractall(target)
        folder = target / 'ontology-lab'
        for action in actions:
            T.command(folder, 'run.py', action, '--no-open')
        rec = {'package': name, 'actions': actions}
        if name == 'completed-zip':
            rows = compare_rows(folder)
            assert rows and all(r['state'] == '같음' for r in rows), [r for r in rows if r['state'] != '같음']
            rec['answers_same_rows'] = len(rows)
        else:
            T.command(folder, 'run.py', 'check', '--no-open', ok=False)      # 받은 그대로는 아직 검사할 결과가 없다
        records.append(rec)
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('lab', type=Path)
    parser.add_argument('--out', type=Path, default=ROOT / '작업/검사/session2-projects/practical-ontology-results.json')
    args = parser.parse_args()
    starter = args.lab.resolve()
    D.require('실전반')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=args.out.parent, prefix='practical-trial-') as temp:
        work = Path(temp)
        records = T.student_condition_selftest(starter, work, 'sources')
        records += base(starter, work) + supply(starter, work) + wrong_choices(starter, work) + packages(starter, work)
    args.out.write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{len(records)}개 실행 대조 통과 — {args.out}')


if __name__ == '__main__':
    main()
