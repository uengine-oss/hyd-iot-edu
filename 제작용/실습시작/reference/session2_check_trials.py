"""2회차 실습3(두 반) 학생 검사기(check.py) 고의 손상 시험. 강사 참조 영역이며 학생 ZIP에 넣지 않는다.

학생 시작본 폴더를 임시로 복사하고, 강사 참조 모델(갈래 A·B)과 그 모델을 일부러 망가뜨린 입력을 결과/에 넣어
실제 check.py를 실행한다. 원본은 건드리지 않는다. 기대대로가 아니면 좌표(시험 이름·출력)와 함께 exit 1.
사용: python session2_check_trials.py   → reference/session2_검사기_고의손상.json
"""
from pathlib import Path
import copy
import json
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LABS = {'통합반': ROOT/'산출물/통합반/실습/02회차/랩/02일차_실습3_온톨로지설계',
        '실전반': ROOT/'산출물/실전반/실습/02회차/랩/02일차_실습3_온톨로지설계'}
OUT = HERE/'session2_검사기_고의손상.json'


def load(course, branch='A'):
    d = HERE/course/('갈래B' if branch == 'B' else '')
    return json.loads((d/'schema.json').read_text(encoding='utf-8')), json.loads((d/'graph.json').read_text(encoding='utf-8'))


def run(folder, schema, graph):
    (folder/'결과/schema.json').write_text(json.dumps(schema, ensure_ascii=False), encoding='utf-8')
    (folder/'결과/graph.json').write_text(json.dumps(graph, ensure_ascii=False), encoding='utf-8')
    p = subprocess.run([sys.executable, 'check.py'], cwd=folder, capture_output=True, text=True, encoding='utf-8', env={'PYTHONUTF8': '1', 'SYSTEMROOT': 'C:\\Windows'})
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
    add('통합반', '원본 A', noop, True, ['구조 검사 통과', 'MONITORED_BY: Asset → Sensor 4개'])
    add('통합반', '원본 B(SAME_ITEM_AS)', noop, True, ['구조 검사 통과', 'SAME_ITEM_AS: Part → Part 1개'], branch='B')
    add('실전반', '원본 A', noop, True, ['구조 검사 통과', 'SUPPLIES 쌍 21개, 관계 21개(approved=true 18개, false 3개)'])
    add('실전반', '원본 B(조건부 승인=비승인)', noop, True, ['구조 검사 통과'], branch='B')
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
    add('통합반', '13 센서를 설비에 조용히 붙임(정보로 드러남)', fallback, True, ['구조 검사 통과', 'MONITORED_BY: Asset → Sensor'], ['MONITORED_BY: Asset → Sensor 4개'])

    # 리허설 2 실전 2-3: 공급 조건 출력 계약
    def dup_pair(s, g):
        r = copy.deepcopy(rel(g, 'SUPPLIES', 'supplier:A정밀', 'P-FAN-BRG')); r['props']['id'] = 'quote-2026-07-01'; r['props']['quote_date'] = '2026-07-01'
        g['rels'].append(r)
    add('실전반', '14 같은 쌍에 SUPPLIES 둘(재견적 둘 다 보존)', dup_pair, False, ['SUPPLIES supplier:A정밀→P-FAN-BRG가 2개'])
    add('실전반', '15 approved 없음(결정 누락)', lambda s, g: rel(g, 'SUPPLIES', 'supplier:A정밀', 'P-CLR-CORE')['props'].pop('approved'), False, ['approved 없음'])
    add('실전반', '16 schema의 approved를 글자로 정의', lambda s, g: s['relations']['SUPPLIES']['properties'].update(approved='string'), False, ["SUPPLIES.properties.approved는 'boolean'"])
    add('실전반', '17 SUPPLIES 관계 이름 다름', lambda s, g: (s['relations'].update(QUOTED=s['relations'].pop('SUPPLIES')), [r.update(type='QUOTED') for r in g['rels'] if r['type'] == 'SUPPLIES']), False, ['공급 조건 관계 SUPPLIES가 없습니다'])
    add('실전반', '18 불량률 % 숫자', lambda s, g: rel(g, 'SUPPLIES', 'supplier:C트레이딩', 'P-RTN-FLT')['props'].update(defect_rate=8), False, ['0~1 비율'])
    add('실전반', '19 승인 상태를 글자로만 둠(approved 대신 status)', lambda s, g: [r['props'].pop('approved') for r in g['rels'] if r['type'] == 'SUPPLIES'], False, ['approved 없음'])
    add('통합반', '20 통합반 검사기에는 공급 계약 검사가 없음', noop, True, [], ['SUPPLIES'])
    return T


def main():
    records, bad = [], []
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        for course, lab in LABS.items():
            shutil.copytree(lab, tmp/course)
        for course, name, branch, fn, ok, want, absent in trials():
            schema, graph = load(course, branch)
            fn(schema, graph)
            code, out = run(tmp/course, schema, graph)
            good = (code == 0) == ok and all(w in out for w in want) and not any(a in out for a in absent)
            records.append({'반': course, '시험': name, '갈래': branch, 'exit': code, '통과_기대': ok, '기대대로': good, '출력': out.splitlines()[-12:]})
            if not good:
                bad.append(f'{course} [{name}] 기대 {"통과" if ok else "실패"} {want} 없어야 {absent}, 실제 exit {code}: {out[-600:]}')
    OUT.write_text(json.dumps(records, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(f'2회차 실습3 검사기 시험 {sum(r["기대대로"] for r in records)}/{len(records)} 기대대로 → {OUT.name}')
    if bad:
        print('\n'.join(bad))
        sys.exit(1)


if __name__ == '__main__':
    main()
