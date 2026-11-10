"""새 실전02 프로젝트(ontology-lab · graph-lab)를 실제 실행해 옛 판과의 결과, 강사 참조 갈래, 검사기 고의 손상, 새 ZIP · 완성본을 대조한다.
AI 호출 없음. 그래프는 이 시험이 새로 띄운 별도 랩 DB(Docker)에서 돌리고, 끝나면 그 컨테이너만 지운다.

사용: python reference/practical2_project_trials.py <ontology-lab 폴더> <graph-lab 폴더> --out <결과 폴더>
     (두 폴더 옆에 생성기가 묶은 <랩>.zip과 --completed의 <랩>-completed.zip이 있어야 한다)
갈래: 설계 = build_labs.REFERENCE_BRANCHES['실전반'](ㄴ · A · B · ㄷ — 대응은 reference/실전반/README.md),
     그래프 = build_labs.LAB4_QUERY_BRANCHES(ㄱ · ㄴ — 7.4 정보를 빼고 · 함께 돌려줌, 입력 모델은 갈래 ㄴ).
"""
from pathlib import Path
import argparse
import copy
import json
import shutil
import sys
import tempfile
import zipfile

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import build_labs as B                     # noqa: E402
import build_practical2_projects as BP     # noqa: E402
import data_session2 as D                  # noqa: E402
import session2_answers as A               # noqa: E402
import verify_reference as V               # noqa: E402
from lab_package import ROOT               # noqa: E402
from reference.session2_project_trials import command   # noqa: E402
from reference.session2_graph_trials import docker, instance, normalized   # noqa: E402
import reference.session2_check_trials as CT   # noqa: E402

BACK = {'supply_terms.csv': D.QUOTE_FILE, 'approved_suppliers.csv': D.AVL_FILE, BP.PR07: D.PR07_FILE}


def converted(value):
    return json.loads(BP.convert(json.dumps(value, ensure_ascii=False)))


def back(value):
    text = json.dumps(value, ensure_ascii=False)
    for new, old in BACK.items():
        text = text.replace(new, old)
    return json.loads(text)


def blocks(folder, action, ok=True):
    out = command(folder, 'run.py', action, '--no-open', ok=ok)
    return out, json.loads((folder / 'output/result.json').read_text(encoding='utf-8'))['blocks']


def all_same(items):
    compare = [b for b in items if b['kind'] == 'compare']
    assert compare and all(r['state'] == '같음' for b in compare for r in b['rows']), compare
    return sum(len(b['rows']) for b in compare)


def supply_rels(graph):
    return {(r['a'], r['b']): r['props'] for r in graph['rels'] if r['type'] == 'SUPPLIES'}


def copy_project(starter, target):
    shutil.copytree(starter, target, ignore=shutil.ignore_patterns('__pycache__', 'output', '.lab_connection.json'))
    return target


# ───────────── 설계 랩 ─────────────
def legacy_fixture(work):
    """옛 실전 실습3 시작본을 같은 계산 원본(build_labs · session2_supply_tool)으로 다시 만든다 — 옛 산출물 폴더를 읽지 않는다."""
    old = work / 'legacy-fixture'
    D.write_sources(old / '자료', practical=True)
    shutil.copyfile(HERE / 'session2_supply_tool.py', old / 'supply_tool.py')
    schema, graph = B.reference_model()
    B.dump(old / '입력/schema.json', B.student_schema(schema))
    B.dump(old / '입력/graph.json', graph)
    for name, text in B.design_practical()['files'].items():
        if name.startswith('결과/'):
            B.write(old / name, text)
    return old


def answer_files(branch):
    return {'결과/quote_rule.py': A.QUOTE_RULE_ANSWER, '결과/approval_rule.py': A.approval_rule_answer(branch),
            '결과/정한_것.csv': B.chosen_text(A.practical_chosen(branch)), '결과/기대_답.csv': BP.expect_supply_text()}


def ontology(starter, graph_starter, work, logs):
    records = []
    old = legacy_fixture(work)
    next_input = json.loads((graph_starter / 'data/model/graph.json').read_text(encoding='utf-8'))
    base = B.reference_model()[1]
    for branch in B.REFERENCE_BRANCHES['실전반']:
        new = copy_project(starter, work / ('new-' + branch))
        legacy = work / ('old-' + branch)
        shutil.copytree(old, legacy)
        files = answer_files(branch)
        BP.put(new, files)
        for name, text in files.items():
            B.write(legacy / name, text)
        command(legacy, '-c', "import supply_tool as M; M.write_model(M.pairs('승인')[0])")
        actions = ['sources', 'expected', 'quotes', 'approval', 'query', 'check'] if branch == 'ㄴ' else ['approval', 'check']
        for action in actions:
            out, result = blocks(new, action)
            logs[f'ontology-{branch}-{action}'] = out
            if action == 'query':
                compared = all_same(result)
                assert any(b['kind'] == 'note' and '구조 검사 통과' in b['text'] for b in result)
        for name in ('schema.json', 'graph.json'):
            expected = converted(json.loads((legacy / '결과' / name).read_text(encoding='utf-8')))
            actual = json.loads((new / 'output' / name).read_text(encoding='utf-8'))
            assert actual == expected, (branch, name, '이전 전후 불일치')
        legacy_graph = json.loads((legacy / '결과/graph.json').read_text(encoding='utf-8'))
        reference = B.reference_model(True, branch)[1]
        assert supply_rels(legacy_graph) == supply_rels(reference), (branch, '강사 참조와 공급 조건 다름')
        assert [n for n in legacy_graph['nodes'] if 'Supplier' not in n['labels']] == base['nodes'], (branch, '제공 모델 부분이 바뀜')
        mismatch = V.diff(V.expected('실전반', branch), V.answers_from_graph('실전반', branch, legacy_graph))
        assert not mismatch, (branch, mismatch[:5])
        original = (new / 'output/graph.json').read_bytes()
        command(new, 'run.py', 'approval', '--no-open')
        assert original == (new / 'output/graph.json').read_bytes()
        graph = json.loads(original)
        record = {'branch': branch, 'nodes': len(graph['nodes']), 'relations': len(graph['rels']), 'supplies': len(supply_rels(graph)),
                  'approved_true': sum(p['approved'] for p in supply_rels(graph).values()),
                  'extra_props': sorted({k for p in supply_rels(graph).values() for k in p} - {k for p in supply_rels(B.reference_model(True, 'A')[1]).values() for k in p}),
                  'legacy_equal': True, 'reference_supply_equal': True, 'reference_answers_equal': True, 'repeat_equal': True}
        if branch == 'ㄴ':
            record['query_rows_same'] = compared
            # 다음 랩(그래프)의 제공 입력은 이 갈래의 결과와 같은 대상 · 관계다(K-9 — 계약)
            record['next_lab_input_same_items'] = normalized(graph) == normalized(next_input)
            assert record['next_lab_input_same_items'], '설계 랩 기본 갈래 결과와 그래프 랩 제공 모델이 다름'
            record['guide_style_expected'] = guide_style_ontology(new, logs)
        records.append(record)
    return records


# ───────────── 검사기 고의 손상(옛 시험 목록을 새 경로에서) ─────────────
def checker_trials(starter, graph_starter, work):
    records, bad = [], []
    folder = copy_project(starter, work / 'check-ontology')
    for course, name, branch, fn, ok, want, absent in CT.trials():
        if course != '실전반':
            continue
        schema, graph = CT.load(course, branch)
        fn(schema, graph)
        if name.endswith('결과 없음'):
            schema = graph = None
        code, out = CT.run(folder, schema, graph)
        want = [w.replace('python check.py', 'python run.py check') for w in want]
        good = (code == 0) == ok and all(w in out for w in want) and not any(a in out for a in absent)
        records.append({'랩': 'ontology-lab', '시험': name, '갈래': branch, 'exit': code, '통과_기대': ok, '기대대로': good, '출력': out.splitlines()[-6:]})
        if not good:
            bad.append(f'ontology [{name}] 기대 {"통과" if ok else "실패"} {want}, 실제 exit {code}: {out[-600:]}')
    head = '# 제공 빈 틀\n지점,고른_것,근거,바뀌는_답\n'
    file_trials = [
        ('F1 제공 파일 바뀜', lambda f: (f / 'run.py').write_text((f / 'run.py').read_text(encoding='utf-8') + '\n# 바꿈\n', encoding='utf-8'), ['제공 파일이 바뀌었습니다: run.py']),
        ('F2 제공 파일 없음', lambda f: (f / 'app/utils/actions.py').unlink(), ['제공 파일이 없습니다: app/utils/actions.py']),
        ('F3 정한 것 근거 꼴', lambda f: (f / 'app/features/decisions.csv').write_text(head + '지점,하나,원문 보고 정함,바뀜\n', encoding='utf-8'), ['근거에 파일:줄이 없습니다']),
        ('F4 정한 것 빈 칸', lambda f: (f / 'app/features/decisions.csv').write_text(head + '지점,,data/a.csv:3,\n', encoding='utf-8'), ['빈 칸 고른_것, 바뀌는_답']),
        ('F5 정한 것 열 이름', lambda f: (f / 'app/features/decisions.csv').write_text('지점,고른 것,근거,바뀌는 답\n', encoding='utf-8'), ['열 이름이']),
        ('F0 손대지 않음(통과)', lambda f: None, [])]
    model = CT.load('실전반', 'ㄴ')
    for lab, src in (('ontology-lab', starter), ('graph-lab', graph_starter)):
        for name, fn, want in file_trials:
            dest = copy_project(src, work / f'file-{lab}-{name.split()[0]}')
            (dest / 'output').mkdir()
            for n, v in zip(('schema.json', 'graph.json'), model):
                (dest / 'output' / n).write_text(json.dumps(v, ensure_ascii=False), encoding='utf-8')
            fn(dest)
            code, out = CT.run(dest, *model)
            good = (code == 0) == (not want) and all(w in out for w in want)
            records.append({'랩': lab, '시험': name, '갈래': '-', 'exit': code, '통과_기대': not want, '기대대로': good, '출력': out.splitlines()[-6:]})
            if not good:
                bad.append(f'{lab} [{name}] 기대 {want}, 실제 exit {code}: {out[-600:]}')
    return records, bad


# ───────────── 그래프 랩 ─────────────
def table_rows(block):
    """결과 화면 표 칸(사람이 읽는 글: 값 없음 「없음」, 목록 「 · 」, 참거짓 True · False)을 값으로 되읽는다."""
    def value(x):
        if not isinstance(x, str):
            return x
        if x == '없음':
            return None
        if x in ('True', 'False'):
            return x == 'True'
        if ' · ' in x:
            return [value(v) for v in x.split(' · ')]
        try:
            return json.loads(x)
        except ValueError:
            return x
    return [dict(zip(block['columns'], [value(x) for x in row])) for row in block['rows']]


def graph(starter, work, logs):
    records = []
    model = json.loads((starter / 'data/model/graph.json').read_text(encoding='utf-8'))
    reference = B.reference_model(True, B.LAB4_INPUT_BRANCH['실전반'])[1]
    assert model == converted(reference), '제공 모델이 옛 판 입력(갈래 ㄴ)과 다름'
    assert not V.diff(V.expected('실전반', 'ㄴ'), V.answers_from_graph('실전반', 'ㄴ', back(model)))
    korean = work / 'source-rows'
    korean.mkdir()
    for new, old in BACK.items():
        shutil.copyfile(starter / 'data' / new, korean / old)
    source_mismatch = V.source_rows(back(model), korean)
    assert not source_mismatch, source_mismatch[:5]
    records.append({'provided_model_equal_legacy_input': True, 'reference_answers_equal': True, 'source_rows_mismatch': 0,
                    'nodes': len(model['nodes']), 'relations': len(model['rels'])})
    for branch, key in B.LAB4_QUERY_BRANCHES.items():
        folder = copy_project(starter, work / ('graph-' + branch) / starter.name)
        command(folder, 'run.py', '--no-open')
        empty = command(folder, 'run.py', 'load', '--no-open', ok=False)
        assert '실행할 문장이 없습니다' in empty
        BP.fill_graph(folder, branch)
        with instance(folder) as state:
            logs[f'graph-{branch}-load'], _ = blocks(folder, 'load')
            blocks(folder, 'export')
            initial = json.loads((folder / 'output/graph.json').read_text(encoding='utf-8'))
            assert normalized(initial) == normalized(model)
            logs[f'graph-{branch}-repeat'], _ = blocks(folder, 'repeat')
            blocks(folder, 'export')
            assert normalized(initial) == normalized(json.loads((folder / 'output/graph.json').read_text(encoding='utf-8')))
            logs[f'graph-{branch}-usage'], usage = blocks(folder, 'usage')
            usage_rows = all_same(usage)
            seal = table_rows(next(b for b in usage if b['kind'] == 'table' and '「P-PMP-SEAL」' in b['title']))
            columns = set(seal[0])
            extra = {'inspection', 'compare_extra_manwon', 'rule_source'}
            assert (extra <= columns) if branch == 'ㄴ' else not (extra & columns), (branch, sorted(columns))
            got = sorted(V.supply_row(key, r['supplier'], r['approved'], r['price_manwon'], r['defect_rate'], r['lead_days'], r.get('compare_extra_manwon'), False) for r in seal)
            want = V.expected('실전반', key)['probes']['P-PMP-SEAL']['supply']
            assert got == want, (branch, got, want)
            assert sorted(seal[0]['assets'] if isinstance(seal[0]['assets'], list) else [seal[0]['assets']]) == V.expected('실전반', key)['probes']['P-PMP-SEAL']['assets']
            logs[f'graph-{branch}-aliases'], aliases = blocks(folder, 'aliases')
            alias_rows = all_same(aliases)
            blocks(folder, 'export')
            logs[f'graph-{branch}-check'], _ = blocks(folder, 'check')
            record = {'branch': branch, 'expected_key': key, 'initial_nodes': len(initial['nodes']), 'initial_rels': len(initial['rels']),
                      'repeat_same': True, 'usage_compare_rows_same': usage_rows, 'aliases_compare_rows_same': alias_rows,
                      'P-PMP-SEAL_supply': got, 'P-PMP-SEAL_assets': seal[0]['assets'], 'extra_columns': sorted(extra & columns), 'check': 'pass'}
            if branch == 'ㄴ':
                saved = (folder / 'output/graph.json').read_bytes()
                for broken in ('duplicate-id', 'missing-endpoint', 'reverse-direction'):
                    damaged = copy.deepcopy(json.loads(saved))
                    if broken == 'duplicate-id':
                        damaged['nodes'].append(copy.deepcopy(damaged['nodes'][0]))
                    elif broken == 'missing-endpoint':
                        damaged['rels'][0]['b'] = 'not-in-graph'
                    else:
                        damaged['rels'][0]['a'], damaged['rels'][0]['b'] = damaged['rels'][0]['b'], damaged['rels'][0]['a']
                    (folder / 'output/graph.json').write_text(json.dumps(damaged), encoding='utf-8')
                    assert '구조 확인 필요' in command(folder, 'run.py', 'check', '--no-open', ok=False)
                    records.append({'broken_export': broken, 'rejected': True})
                (folder / 'output/graph.json').write_bytes(saved)
                docker('stop', state['container'])
                blocks(folder, 'db')
                blocks(folder, 'export')
                assert normalized(json.loads((folder / 'output/graph.json').read_text(encoding='utf-8'))) == normalized(initial)
                all_same(blocks(folder, 'usage')[1])
                state_path = folder / '.lab_connection.json'
                original = state_path.read_bytes()
                state_path.write_text(json.dumps(state | {'id': 'wrong-owner'}), encoding='utf-8')
                try:
                    assert '이 폴더의 랩 DB가 아닙니다' in command(folder, 'run.py', 'status', '--no-open', ok=False)
                finally:
                    state_path.write_bytes(original)
                record |= {'restart_preserves_graph': True, 'wrong_owner_rejected': True, 'empty_feature_rejected': True}
                record['guide_style_expected'] = guide_style_graph(folder, logs)
                record['new_db_path'] = new_db(folder, state, initial, logs)
            records.append(record)
        print('그래프 갈래 ' + branch + ' 실행·정리 통과', flush=True)
    return records


def guide_style_ontology(folder, logs):
    """가이드 03단계 꼴대로 사람이 적을 법한 기대 답(원자료 그대로의 소수 「0.30」, 견적표 공급사 표기, 없는 품번 항목 「없음」)도 「같음」인지 본다."""
    path = folder / 'app/features/expected.csv'
    original = path.read_text(encoding='utf-8')
    text = (original.replace('비승인 · 20 · 0.3 · 1', '비승인 · 20.0 · 0.30 · 1').replace('P-PMP-SEAL/A정밀,', 'P-PMP-SEAL/A정밀 (저가),')
            .replace('P-PMP-SEAL-X,,없음', 'P-PMP-SEAL-X,없음,없음'))
    assert text.count('· 0.30 ·') == 1 and '(저가)' in text and 'P-PMP-SEAL-X,없음,없음' in text, '기대 답 예의 꼴이 바뀌었습니다'
    path.write_text(text, encoding='utf-8')
    out, result = blocks(folder, 'query')
    logs['ontology-guide-style-query'] = out
    rows = all_same(result)
    path.write_text(text.replace('승인 · 35', '참 · 35'), encoding='utf-8')
    _, wrong = blocks(folder, 'query', ok=True)
    assert any(r['state'] != '같음' for b in wrong if b['kind'] == 'compare' for r in b['rows']), '승인 낱말이 다른데 같음으로 나옴'
    path.write_text(original, encoding='utf-8')
    return {'rows_same': rows, 'number_supplier_missing_normalized': True, 'wrong_word_detected': True}


def guide_style_graph(folder, logs):
    """가이드 04 · 06단계대로: 한 물을 값에 볼_열 여럿(목록 열 assets 포함), 아직 볼_열을 비운 줄, 같은 짝 두 줄."""
    path = folder / 'app/features/expected.csv'
    original = path.read_text(encoding='utf-8')
    columns = '질문,물을_값,볼_열,기대_답,근거\n'
    head, body = original.split(columns, 1)
    head += columns
    extra = '1,P-PMP-SEAL,assets,HYD-01 · HYD-02 · HYD-03,data/components.csv:4 · 17 · 29\n'
    path.write_text(head + body + extra, encoding='utf-8')
    out, result = blocks(folder, 'usage')
    logs['graph-guide-style-usage'] = out
    rows = all_same(result)
    assert rows == 2, rows
    path.write_text(head + '1,P-PMP-SEAL,,HYD-01 · HYD-02 · HYD-03,data/components.csv:4\n', encoding='utf-8')
    _, blank = blocks(folder, 'usage')
    assert any(b['kind'] == 'note' and '볼_열이 비어' in b['text'] for b in blank), blank
    blocks(folder, 'expected')
    path.write_text(head + body + body.splitlines()[0] + '\n', encoding='utf-8')
    dup, _ = blocks(folder, 'usage', ok=False)
    assert '두 줄' in dup, dup
    path.write_text(original, encoding='utf-8')
    return {'multi_columns_rows_same': rows, 'list_column_joined': True, 'blank_column_noted': True, 'duplicate_pair_stopped': True}


def new_db(folder, state, initial, logs):
    """컨테이너가 없어진 뒤(다른 PC로 옮김 · 지워짐) 같은 폴더의 db가 새 빈 랩 DB를 만들고, 저장한 적재로 같은 결과가 나오는지."""
    docker('rm', '-f', '-v', state['container'])
    out, _ = blocks(folder, 'db')
    logs['graph-new-db'] = out
    assert '새로 만든 랩 DB라 비어 있습니다' in out, out
    _, status = blocks(folder, 'status')
    table = next(b for b in status if b['kind'] == 'table')
    assert all(row[2] == 0 for row in table['rows']), table['rows'][:3]
    blocks(folder, 'load')
    blocks(folder, 'export')
    assert normalized(json.loads((folder / 'output/graph.json').read_text(encoding='utf-8'))) == normalized(initial)
    all_same(blocks(folder, 'usage')[1])
    return {'renewed_empty': True, 'reload_same_graph': True, 'usage_same': True}


# ───────────── 받은 ZIP · 완성본 ─────────────
def fresh(starter, work, logs):
    records = []
    received = work / ('received-' + starter.name)
    with zipfile.ZipFile(starter.with_suffix('.zip')) as archive:
        archive.extractall(received)
    folder = received / starter.name
    assert not (folder / 'output').exists()
    assert (received / (starter.name + '_guide.html')).read_bytes() == (starter.parent / (starter.name + '_guide.html')).read_bytes()
    out, data = blocks(folder, 'sources')
    assert data and not any(b['kind'] == 'error' for b in data)
    records.append({'lab': starter.name, 'fresh_starter': True, 'first_command': 'python run.py --no-open', 'actual_blocks': len(data), 'guide_beside_project': True})
    archive = starter.parent / (starter.name + '-completed.zip')
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        assert not any(n.endswith(('_guide.html', '.lab_connection.json')) or '__pycache__' in n for n in names)
        z.extractall(work / ('received-completed-' + starter.name))
    folder = work / ('received-completed-' + starter.name) / starter.name
    before = {name: (folder / 'output' / name).read_bytes() for name in ('graph.json', 'schema.json')}
    if starter.name == 'ontology-lab':
        for action in ('approval', 'check'):
            logs['completed-ontology-' + action], _ = blocks(folder, action)
        logs['completed-ontology-query'], result = blocks(folder, 'query')
        rows = all_same(result)
        assert all((folder / 'output' / name).read_bytes() == data for name, data in before.items())
        records.append({'lab': starter.name, 'fresh_completed': True, 'regenerated_models_equal': True, 'query_rows_same': rows, 'check': 'pass'})
    else:
        with instance(folder):
            for action in ('load', 'export', 'check'):
                logs['completed-graph-' + action], _ = blocks(folder, action)
            exported = json.loads((folder / 'output/graph.json').read_text(encoding='utf-8'))
            assert normalized(exported) == normalized(json.loads(before['graph.json']))
            usage = all_same(blocks(folder, 'usage')[1])
            aliases = all_same(blocks(folder, 'aliases')[1])
        records.append({'lab': starter.name, 'fresh_completed': True, 'export_equal_packed_output': True, 'usage_rows_same': usage, 'aliases_rows_same': aliases, 'check': 'pass'})
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ontology', type=Path)
    parser.add_argument('graph', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    base = BP.WORK.resolve()
    base.mkdir(parents=True, exist_ok=True)
    args.out.mkdir(parents=True, exist_ok=True)
    logs = {}
    with tempfile.TemporaryDirectory(prefix='trials-', dir=base) as temp:
        work = Path(temp).resolve()
        assert work.is_relative_to(base) and work != base
        onto, graph_lab = args.ontology.resolve(), args.graph.resolve()
        report = {'kind': '강사 코드 실행 · 옛 판 대조 · 실제 별도 DB; 학생 AI 시험 · GUI 시험 아님'}
        report['ontology'] = ontology(onto, graph_lab, work, logs)
        print(f"설계 랩 {len(report['ontology'])}갈래 통과", flush=True)
        checks, bad = checker_trials(onto, graph_lab, work)
        (args.out / 'check-trials.json').write_text(json.dumps(checks, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        print(f'검사기 시험 {sum(r["기대대로"] for r in checks)}/{len(checks)} 기대대로', flush=True)
        if bad:
            print('\n'.join(bad))
            sys.exit(1)
        report['graph'] = graph(graph_lab, work, logs)
        report['fresh'] = fresh(onto, work, logs) + fresh(graph_lab, work, logs)
        report['created_containers_removed'] = True   # instance()가 나올 때마다 그 컨테이너의 라벨을 확인해 지우고 남지 않았는지 단언한다
    (args.out / 'trials-results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (args.out / 'trials-outputs.json').write_text(json.dumps(logs, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print('참조 · 손상 · 받은 ZIP · 완성본 시험 통과 →', args.out)


if __name__ == '__main__':
    main()
