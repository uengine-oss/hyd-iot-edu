"""2회차 실습3(두 반) 학생 검사기(check.py) 고의 손상 시험. 실전반은 「공급 조건 형식」 계약과 갈래 A · B · ㄴ · ㄷ 원본을 함께 본다. 강사 참조 영역이며 학생 ZIP에 넣지 않는다.

학생 시작본 폴더를 임시로 복사하고, 강사 참조 모델(갈래 A·B)과 그 모델을 일부러 망가뜨린 입력을 결과/에 넣어
실제 check.py를 실행한다. 원본은 건드리지 않는다. 기대대로가 아니면 좌표(시험 이름·출력)와 함께 exit 1.
사용: python session2_check_trials.py   → reference/session2_검사기_고의손상.json
"""
from pathlib import Path
import copy
import argparse
import os
import json
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
LABS = {'통합반': ROOT/'workspace/강의제작/산출물/통합반/실습/02회차/랩/ontology-lab',
        '실전반': ROOT/'workspace/강의제작/산출물/실전반/실습/02회차/랩/02일차_실습3_온톨로지설계'}
OUT = HERE/'session2_검사기_고의손상.json'


BRANCH_DIRS = {'A': '', 'B': '갈래B', 'C': '갈래C', 'ㄴ': '갈래ㄴ', 'ㄷ': '갈래ㄷ'}   # build_labs.BRANCH_DIRS와 같은 자리


def load(course, branch='A'):
    d = HERE/course/BRANCH_DIRS[branch]
    return json.loads((d/'schema.json').read_text(encoding='utf-8')), json.loads((d/'graph.json').read_text(encoding='utf-8'))


def run(folder, schema, graph):
    project = (folder/'run.py').is_file()
    output = folder / ('output' if project else '결과')
    output.mkdir(exist_ok=True)
    for name, value in [('schema.json', schema), ('graph.json', graph)]:
        path = output/name
        if value is None:
            path.unlink(missing_ok=True)       # 결과를 아직 만들지 않은 상태
        else:
            path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    p = subprocess.run([sys.executable, *(['-m', 'app.utils.check'] if project else ['check.py'])], cwd=folder, capture_output=True, text=True, encoding='utf-8', env={**os.environ, 'PYTHONUTF8': '1'})
    return p.returncode, (p.stdout + p.stderr).strip()


def rel(graph, t, a=None, b=None):
    return next(r for r in graph['rels'] if r['type'] == t and (a is None or r['a'] == a) and (b is None or r['b'] == b))


def node(graph, id):
    return next(n for n in graph['nodes'] if n['props']['id'] == id)


def trials():
    """(반, 이름, 갈래, 손상 함수(schema, graph), 통과 기대, 나와야 할 글, 없어야 할 글)"""
    T = []

    def add(course, name, fn, ok, want=(), absent=(), branch='A'):
        T.append((course, name, branch, fn, ok, list(want), list(absent)))
    noop = lambda s, g: None
    add('통합반', '원본 A', noop, True, ['구조 검사 통과', 'MONITORED_BY: Asset → Sensor 4개', 'Component를 거치지 않고 Asset에 바로 붙은 Sensor 4개(MONITORED_BY)'])
    add('통합반', '원본 B(SAME_ITEM_AS)', noop, True, ['구조 검사 통과', 'SAME_ITEM_AS: Part → Part 1개'], branch='B')
    add('실전반', '원본 A', noop, True, ['구조 검사 통과', 'SUPPLIES: Supplier → Part 21개'])
    add('실전반', '원본 B(조건부 승인=비승인)', noop, True, ['구조 검사 통과'], branch='B')
    add('실전반', '원본 ㄴ(PR-07 7.4 정보 표시)', noop, True, ['구조 검사 통과', 'SUPPLIES: Supplier → Part 21개'], branch='ㄴ')
    add('실전반', '원본 ㄷ(PR-07 7.4 미결 표시)', noop, True, ['구조 검사 통과', 'SUPPLIES: Supplier → Part 21개'], branch='ㄷ')
    # 공통 구조(이전 12종을 다시 실행할 수 있게 옮김)
    add('통합반', '1 중복 id', lambda s, g: g['nodes'].append(copy.deepcopy(node(g, 'P-PMP-SEAL'))), False, ['중복 id: P-PMP-SEAL'])
    add('통합반', '2 없는 끝점', lambda s, g: g['rels'].append({'type': 'USES_PART', 'a': 'HYD-01:pump-a', 'b': 'P-PMP-SEAL-X', 'props': {}}), False, ['없는 관계 끝점'])
    add('통합반', '3 중복 관계', lambda s, g: g['rels'].append(copy.deepcopy(rel(g, 'HAS_COMPONENT', 'HYD-01', 'HYD-01:cooler'))), False, ['중복 관계'])
    add('실전반', '4 approved 글자', lambda s, g: rel(g, 'SUPPLIES', 'supplier:A정밀', 'P-ACC-BLD')['props'].update(approved='예'), False, ['참/거짓 자리에 글자'])
    add('통합반', '5 숫자에 단위', lambda s, g: node(g, 'HYD-02:PS1')['props'].update(limit='130 bar'), False, ['숫자 자리에 글자'])
    add('통합반', '6 필수 속성 없음', lambda s, g: node(g, 'HYD-01:TS1')['props'].pop('unit'), False, ['필수 속성 unit 없음'])
    add('통합반', '7 관계 방향 반대', lambda s, g: g['rels'].append({'type': 'USES_PART', 'a': 'HYD-04:pump-a', 'b': 'HYD-04:pump-b', 'props': {}}), False, ['USES_PART 끝 종류가 다름'])
    add('통합반', '8 스키마에 없는 종류', lambda s, g: g['nodes'].append({'labels': ['Sensr'], 'props': {'id': 'HYD-01:X'}}), False, ['스키마에 없는 종류 Sensr'])
    add('통합반', '9 허용 값 밖', lambda s, g: node(g, 'HYD-01:PS1')['props'].update(limit_direction='하한'), False, ['허용 값'])
    add('실전반', '10 납기 소수', lambda s, g: rel(g, 'SUPPLIES', 'supplier:A정밀', 'P-ACC-BLD')['props'].update(lead_days=2.5), False, ['lead_days=2.5'])
    add('통합반', '11 빈 그래프', lambda s, g: (g['nodes'].clear(), g['rels'].clear()), False, ['노드 또는 관계가 비어'])
    add('통합반', '12 스키마 형식 다름', lambda s, g: s['relations'].pop('HAS_COMPONENT'), False, ['스키마에 없는 관계 HAS_COMPONENT'])

    # 리허설 2: 구성요소를 못 찾은 센서를 조용히 설비에 붙인 모델 — 구조는 통과하지만 분포 정보로 드러난다
    def fallback(s, g):
        owner = {r['b']: r['a'] for r in g['rels'] if r['type'] == 'HAS_COMPONENT'}
        for r in g['rels']:
            if r['type'] == 'MONITORED_BY' and r['a'] in owner and not r['a'].startswith(('HYD-01:',)):
                r['a'] = owner[r['a']]
    add('통합반', '13 센서를 설비에 조용히 붙임(정보로 드러남)', fallback, True, ['구조 검사 통과', 'MONITORED_BY: Asset → Sensor', 'Component를 거치지 않고 Asset에 바로 붙은 Sensor'], ['MONITORED_BY: Asset → Sensor 4개', '바로 붙은 Sensor 4개('])

    # 보강 3: 관계 방향을 반대로(센서 → 붙은 곳) 정의한 모델에서도 설비에 바로 붙은 센서가 드러난다
    def reverse_fallback(s, g):
        fallback(s, g)
        spec = s['relations'].pop('MONITORED_BY')
        s['relations']['ATTACHED_TO'] = {**spec, 'from': 'Sensor', 'to': spec['from']}
        for r in g['rels']:
            if r['type'] == 'MONITORED_BY':
                r.update(type='ATTACHED_TO', a=r['b'], b=r['a'])
    add('통합반', '21 방향 반대(Sensor → Asset/Component)에서도 설비 직결 센서가 드러남', reverse_fallback, True, ['구조 검사 통과', 'Component를 거치지 않고 Asset에 바로 붙은 Sensor', '(ATTACHED_TO)'], ['바로 붙은 Sensor 4개('])

    # 결과를 아직 만들지 않은 상태: 검사는 오류 추적 대신 결과 형식을 안내하고 실패로 끝난다
    add('통합반', '20 결과 없음', lambda s, g: None, False, ['아직 검사할 결과가 없습니다'], ['Traceback'])
    add('실전반', '20 결과 없음', lambda s, g: None, False, ['아직 검사할 결과가 없습니다'], ['Traceback'])

    # 실전반 「공급 조건 형식」(다음 실습의 조회가 읽는 계약): SUPPLIES 하나 = 공급사 · 부품 쌍의 기준일 조건 하나와 다섯 속성
    def rename_relation(schema, graph):
        schema['relations']['QUOTED'] = schema['relations'].pop('SUPPLIES')
        for relation in graph['rels']:
            if relation['type'] == 'SUPPLIES':
                relation['type'] = 'QUOTED'

    def second_quote(schema, graph):
        extra = copy.deepcopy(rel(graph, 'SUPPLIES', 'supplier:B-OEM', 'P-PMP-SEAL'))
        extra['props'].update(id='old-quote', price_manwon=58.0, quote_date='2026-04-03')
        graph['rels'].append(extra)

    def status_only(schema, graph):
        schema['relations']['SUPPLIES']['properties'].pop('approved')
        for relation in graph['rels']:
            if relation['type'] == 'SUPPLIES':
                relation['props'].pop('approved')

    def missing_declared_field(schema, graph):
        schema['relations']['SUPPLIES']['required'] = ['quote_date']
        rel(graph, 'SUPPLIES')['props'].pop('quote_date')

    add('실전반', '14 같은 쌍에 SUPPLIES 둘(재견적 둘 다 보존)', second_quote, False, ['supplier:B-OEM→P-PMP-SEAL가 2개'])
    add('실전반', '15 approved 없음(결정 누락)', lambda s, g: rel(g, 'SUPPLIES', 'supplier:A정밀', 'P-PMP-SEAL')['props'].pop('approved'), False, ['supplier:A정밀→P-PMP-SEAL: approved 없음'])
    add('실전반', '16 schema의 approved를 글자로 정의', lambda s, g: s['relations']['SUPPLIES']['properties'].update(approved='string'), False, ["SUPPLIES.properties.approved는 'boolean'"])
    add('실전반', '17 SUPPLIES 관계 이름 다름', rename_relation, False, ['공급 조건 관계 SUPPLIES가 없습니다'])
    add('실전반', '18 불량률 % 숫자', lambda s, g: rel(g, 'SUPPLIES', 'supplier:A정밀', 'P-PMP-SEAL')['props'].update(defect_rate=12.0), False, ['defect_rate=12.0는 0~1 범위 밖'])
    add('실전반', '19 승인 상태를 글자로만 둠(approved 대신 status)', status_only, False, ['approved 없음'])
    add('실전반', '22 내 스키마에서 필수로 선언한 근거 날짜 누락', missing_declared_field, False, ['필수 속성 quote_date 없음'])
    return T


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--course', choices=list(LABS))
    parser.add_argument('--out', type=Path, default=OUT)
    args = parser.parse_args()
    labs = {c: p for c, p in LABS.items() if not args.course or c == args.course}
    records, bad = [], []
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        for course, lab in labs.items():
            shutil.copytree(lab, tmp/course)
        for course, name, branch, fn, ok, want, absent in trials():
            if course not in labs:
                continue
            schema, graph = load(course, branch)
            fn(schema, graph)
            if name.endswith('결과 없음'):
                schema = graph = None
            code, out = run(tmp/course, schema, graph)
            good = (code == 0) == ok and all(w in out for w in want) and not any(a in out for a in absent)
            records.append({'반': course, '시험': name, '갈래': branch, 'exit': code, '통과_기대': ok, '기대대로': good, '출력': out.splitlines()[-12:]})
            if not good:
                bad.append(f'{course} [{name}] 기대 {"통과" if ok else "실패"} {want} 없어야 {absent}, 실제 exit {code}: {out[-600:]}')
        # 공용 검사(lab_frame.provided_guard · CHOSEN_CHECK) — 실습3 · 4 네 폴더 모두: 제공 파일을 바꾸거나 정한_것.csv 칸이 비면 잡는가
        labs4 = {c: ROOT/f'workspace/강의제작/산출물/{c}/실습/02회차/랩'/('graph-lab' if c == '통합반' else '02일차_실습4_그래프구현과검증') for c in labs}
        chosen_head = '# 제공 빈 틀\n지점,고른_것,근거,바뀌는_답\n'
        file_trials = [
            ('F1 제공 파일 바뀜', lambda f: (f/'show_result.py').write_text((f/'show_result.py').read_text(encoding='utf-8') + '\n# 바꿈\n', encoding='utf-8'), ['제공 파일이 바뀌었습니다: show_result.py']),
            ('F2 제공 파일 없음', lambda f: (f/'lab_steps.py').unlink(), ['제공 파일이 없습니다: lab_steps.py']),
            ('F3 정한 것 근거 꼴', lambda f: (f/'결과/정한_것.csv').write_text(chosen_head + '시점,하나,원문 보고 정함,바뀜\n', encoding='utf-8'), ['근거에 파일:줄이 없습니다']),
            ('F4 정한 것 빈 칸', lambda f: (f/'결과/정한_것.csv').write_text(chosen_head + '시점,,자료/a.csv:3,\n', encoding='utf-8'), ['빈 칸 고른_것, 바뀌는_답']),
            ('F5 정한 것 열 이름', lambda f: (f/'결과/정한_것.csv').write_text('지점,고른 것,근거,바뀌는 답\n', encoding='utf-8'), ['열 이름이']),
            ('F0 손대지 않음(통과)', lambda f: None, [])]
        for course in labs:
            for which, src in [('실습3', LABS[course]), ('실습4', labs4[course])]:
                for name, fn, want in file_trials:
                    dest = tmp/f'{course}_{which}_{name.split()[0]}'
                    shutil.copytree(src, dest)
                    project = (dest/'run.py').is_file()
                    if which == '실습3' or project:
                        schema, graph = load(course, 'A' if course == '통합반' else 'ㄴ')
                        for n, v in [('schema.json', schema), ('graph.json', graph)]:
                            target = dest/('output' if project else '결과')/n
                            target.parent.mkdir(exist_ok=True)
                            target.write_text(json.dumps(v, ensure_ascii=False), encoding='utf-8')
                    if project:
                        class Mapped:
                            def __truediv__(self, rel):
                                return dest / {'show_result.py':'run.py', 'lab_steps.py':'app/utils/actions.py', '결과/정한_것.csv':'app/features/decisions.csv'}.get(rel, rel)
                        fn(Mapped())
                        want=[w.replace('show_result.py','run.py').replace('lab_steps.py','app/utils/actions.py') for w in want]
                    else:
                        fn(dest)
                    p = subprocess.run([sys.executable, *(['-m', 'app.utils.check'] if project else ['check.py'])], cwd=dest, capture_output=True, text=True, encoding='utf-8', env={**os.environ, 'PYTHONUTF8': '1'})
                    out = (p.stdout + p.stderr).strip()
                    ok = not want
                    good = (p.returncode == 0) == ok and all(w in out for w in want)
                    records.append({'반': course, '시험': f'{which} {name}', '갈래': '-', 'exit': p.returncode, '통과_기대': ok, '기대대로': good, '출력': out.splitlines()[-6:]})
                    if not good:
                        bad.append(f'{course} {which} [{name}] 기대 {want}, 실제 exit {p.returncode}: {out[-600:]}')
    args.out.write_text(json.dumps(records, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    print(f'2회차 검사기 시험 {sum(r["기대대로"] for r in records)}/{len(records)} 기대대로 → {args.out.name}')
    if bad:
        print('\n'.join(bad))
        sys.exit(1)


if __name__ == '__main__':
    main()
