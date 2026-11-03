"""2회차 실습3의 수강생용 완성본을 새 작업 폴더에서 실행·검사한 뒤 별도 ZIP으로 묶는다.

`결과/요구사항.md`는 학생 시작본의 「제공 빈 틀」(build_labs.req_template)과 같은 칸으로 채운다. 「정한 것」은 완성본의 갈래(build_labs.LAB4_INPUT_BRANCH —
다음 실습 `입력/` 모델과 같은 결정)와 그 근거 줄, 「기대 답과 실제 결과」는 기대 답을 원자료 줄에서, 실제 결과를 완성 모델을 실행한 출력에서 따로 가져와
둘이 같은지 이 스크립트가 확인한다(다르면 멈춘다). 같은 명령을 두 번 실행해 결과 파일이 같은 바이트인지도 본다.
"""
import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import build_labs as labs

ROOT = labs.OUT
TOOLS = Path(__file__).resolve().parent / '완성본_설계'
LAB = '02일차_실습3_온톨로지설계'
D = labs.D
COMMAND = 'python -B -X utf8 결과/모델실행.py'
MISSING = 'P-ZZZ-999'                     # 어느 원자료에도 없는 품번(확인 사례 「원자료에 없는 품번」)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def student_files(folder):
    files = {}
    for path in sorted(folder.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts:
            if path.name.startswith('.env'):
                raise ValueError('환경 파일을 포함하지 않는 설계 실습만 묶을 수 있습니다.')
            files[path.relative_to(folder).as_posix()] = digest(path.read_bytes())
    return files


class Source:
    """완성본 폴더의 원자료를 줄 번호와 함께 읽는다(편집기에 보이는 번호 — 머리줄이 1행)."""
    def __init__(self, folder):
        self.folder = folder / '자료'

    def rows(self, name, keep=lambda r: True):
        with (self.folder/name).open(encoding='utf-8-sig', newline='') as stream:
            return [(i, r) for i, r in enumerate(csv.DictReader(stream), 2) if keep(r)]

    def line(self, name, needle):
        found = [i for i, x in enumerate((self.folder/name).read_text(encoding='utf-8').splitlines(), 1) if needle in x]
        if len(found) != 1:
            raise ValueError(f'{name}에서 「{needle}」 줄이 {len(found)}개입니다.')
        return found[0]


def ref(name, nums):
    """파일과 줄 번호. 이어지는 줄(셋 이상)은 「a ~ b」로 줄인다."""
    nums, parts = sorted(set(nums)), []
    for n in nums:
        if parts and parts[-1][1] == n - 1:
            parts[-1][1] = n
        else:
            parts.append([n, n])
    return f'`{name}` ' + ' · '.join(f'{a} ~ {b}' if b - a >= 2 else ' · '.join(str(x) for x in range(a, b + 1)) for a, b in parts) + '행'


def ask(folder, code):
    """완성본 확인 코드를 품번 하나로 실행해 찾은 결과(목록)를 돌려준다."""
    proc = subprocess.run([sys.executable, '-B', '-X', 'utf8', str(folder/'결과/모델실행.py'), code], cwd=folder, text=True, encoding='utf8', capture_output=True)
    if proc.returncode:
        raise ValueError(proc.stdout + proc.stderr)
    mark = f'조회한 표기: {code} · '          # 구조 검사 출력 뒤에 이 줄과 찾은 결과(JSON)가 나온다
    if proc.stdout.count(mark) != 1:
        raise ValueError(proc.stdout)
    body = proc.stdout.split(mark, 1)[1].split('\n', 1)[1]
    return json.loads(body.rsplit('\n전체 질문 결과', 1)[0])


def table(head, rows_):
    return '| ' + ' | '.join(head) + ' |\n|' + '---|' * len(head) + '\n' + ''.join('| ' + ' | '.join(r) + ' |\n' for r in rows_)


def same(expected, actual, what):
    if expected != actual:
        raise ValueError(f'완성본 {what}: 원자료에서 찾은 기대 답 {expected!r} ≠ 실제 결과 {actual!r}')
    return '같음'


def integrated(folder, result, src):
    """통합반 — 갈래 A(같은 규격의 두 사내 품번을 따로 둠). 반환: (정한 것 줄, 기대 답 줄, 자료 검토 줄, 확인하지 못한 점)."""
    by_part = result['부품별 사용처']
    spec = src.rows('품번_교차표.csv', lambda r: r['다른표기'] == '6205-2RS')
    spec_parts = sorted(r['사내품번'] for _, r in spec)
    stock = src.rows('예비품_목록.csv', lambda r: r['품번'] in spec_parts)
    memo = src.line('현장_메모.md', '합칠지')
    users = {p: by_part[p]['사용 설비'] for p in spec_parts}
    merged = sorted(set().union(*users.values()))
    decided = [['쓰는 사람에 따라 갈리는 답(같은 제조사 품번의 다른 사내 품번)',
                '두 사내 품번을 따로 둔다 — 사내 품번 · 예전 품번으로 물으면 그 품번만, 제조사 품번으로 물으면 같은 규격 후보 둘을 함께 보인다',
                f'{ref("품번_교차표.csv", [i for i, _ in spec])}(같은 제조사 품번), {ref("예비품_목록.csv", [i for i, _ in stock])}(적용 모델 · 등록이 다름), `현장_메모.md` {memo}행(합칠지 검토 중)',
                ', '.join(f'{p} → {" · ".join(users[p])}' for p in spec_parts) + f'. 한 물품으로 합치면 두 품번 모두 {" · ".join(merged)}']]
    # 질문 1: 고른 설비 HYD-01의 구성 요소별 센서 — 원자료의 붙은곳 이름을 표기 기준(같은 장치 · 같은 태그)으로 풀어 견준다.
    model = {r['설비코드']: r['모델'] for _, r in src.rows('설비_대장.csv')}
    keys = {k for k, *_ in D.MODEL_COMPONENTS[model['HYD-01']]}
    rows01 = src.rows('센서_목록.csv', lambda r: r['설비코드'] == 'HYD-01')
    expected = {}
    for _, r in rows01:
        place = '(설비 전체)' if r['붙은곳'] == '설비 전체' else labs.comp_key(r['붙은곳'], keys)
        expected.setdefault(place, set()).add(r['태그'])
    expected = {k: sorted(v) for k, v in sorted(expected.items())}
    actual = {(p.split(':', 1)[1] if ':' in p else '(설비 전체)'): sorted(x['태그'] for x in items) for p, items in result['설비별 센서']['HYD-01'].items()}
    actual = dict(sorted(actual.items()))
    dup = [i for i, r in rows01 if r['비고'] == '점검표에서 옮겨 적음']
    q1 = ['질문 1 · HYD-01 구성 요소별 센서',
          f'{ref("센서_목록.csv", [i for i, _ in rows01])} — 붙은 곳 {len(expected)}곳에 센서 {sum(map(len, expected.values()))}개(' + ', '.join(f'{k} {"·".join(v)}' for k, v in expected.items())
          + f'). {ref("센서_목록.csv", dup)}은 점검표에서 다시 옮겨 적은 같은 센서',
          f'구성 요소별 센서가 기대 답과 같음(붙은 곳 {len(actual)}곳, 센서 {sum(map(len, actual.values()))}개, `결과/질문별_결과.json` 「설비별 센서」)', same(expected, actual, 'HYD-01 센서')]
    # 질문 2: 태그 이름이 달라도 같은 물리량(유온)을 재는 센서
    ts1 = src.rows('센서_목록.csv', lambda r: labs.WHAT_ALIAS.get(r['재는것']) == 'TS1')
    exp_ts1 = sorted({r['설비코드'] + ':' + r['태그'] for _, r in ts1})
    act_ts1 = sorted(x['센서'] for x in result['물리량별 센서']['유온'])
    q2 = ['질문 2 · 유온을 재는 센서(태그 이름이 다른 것 포함)',
          f'{ref("센서_목록.csv", [i for i, _ in ts1])}의 「재는것」(' + ' · '.join(sorted({r["재는것"] for _, r in ts1})) + f') — {len(exp_ts1)}개: ' + ' · '.join(exp_ts1),
          f'「물리량별 센서」의 유온 묶음 {len(act_ts1)}개가 기대 답과 같음', same(exp_ts1, act_ts1, '유온 묶음')]
    # 질문 2: 단위 칸이 빈 줄 — 근거 줄로만 채운다(build_labs.blank_unit_basis와 같은 기준)
    basis = labs.blank_unit_basis(src.folder)
    unit_rows, review = [], []
    for sid, b in basis.items():
        aid, tag = sid.split(':')
        got = next(x['단위'] for items in result['설비별 센서'][aid].values() for x in items if x['태그'] == tag)
        unit_rows.append([f'질문 2 · {aid} {tag}의 단위', f'`센서_목록.csv` {b["line"]}행은 단위 칸이 빔 → 같은 모델 · 같은 태그로 정상값 · 한계가 같은 {ref("센서_목록.csv", b["basis"])}의 단위 {b["unit"]}',
                          f'{got}', same(b['unit'], got, f'{sid} 단위') + ' — 채운 근거는 `결과/자료_검토.md`'])
        review.append(f'- 단위 칸이 빈 `센서_목록.csv` {b["line"]}행({sid})은 짐작하지 않고, 같은 모델 · 같은 태그로 정상값 · 한계까지 같은 {ref("센서_목록.csv", b["basis"])}을 근거로 {b["unit"]}로 두었습니다. 근거 줄이 없었다면 미확인으로 남깁니다.')
    # 질문 3: 공용 부품 · 다른 표기 · 제조사 규격 번호 · 없는 품번
    seal = src.rows('구성요소_목록.csv', lambda r: '철거' not in r['비고'] and ('PMP-SEAL' in r['교체부품'] and 'HT' not in r['교체부품'] and '22' not in r['교체부품']))
    shared = src.rows('예비품_목록.csv', lambda r: r['품번'] == 'P-PMP-SEAL')
    blank = src.rows('구성요소_목록.csv', lambda r: r['설비코드'] in ('HYD-01', 'HYD-02', 'HYD-03') and labs.NAME_ALIAS.get(r['구성요소']) == 'pump-a' and not r['교체부품'])
    exp_seal = sorted({r['설비코드'] for _, r in seal + blank})
    q3 = [['질문 3 · 공용 부품 P-PMP-SEAL',
           f'{ref("구성요소_목록.csv", [i for i, _ in seal])}(품번 · 표기 변형), {ref("구성요소_목록.csv", [i for i, _ in blank])}(교체부품 칸 빔 — {ref("예비품_목록.csv", [i for i, _ in shared])} 「{shared[0][1]["비고"]}」) → ' + ' · '.join(exp_seal),
           ' · '.join(by_part['P-PMP-SEAL']['사용 설비']), same(exp_seal, by_part['P-PMP-SEAL']['사용 설비'], 'P-PMP-SEAL 사용 설비')]]
    alias = src.rows('품번_교차표.csv', lambda r: r['다른표기'] == 'PMP-SEAL')
    found = ask(folder, 'PMP-SEAL')
    q3.append(['질문 3 · 다른 표기 PMP-SEAL', f'{ref("품번_교차표.csv", [i for i, _ in alias])} → ' + alias[0][1]['사내품번'],
               ' · '.join(f'{x["품번"]}({" · ".join(x["사용 설비"])})' for x in found), same([alias[0][1]['사내품번']], [x['품번'] for x in found], 'PMP-SEAL')])
    found = ask(folder, '6205-2RS')
    q3.append(['질문 3 · 제조사 규격 번호 6205-2RS', f'{ref("품번_교차표.csv", [i for i, _ in spec])} → 같은 규격 후보 둘 ' + ' · '.join(spec_parts),
               '후보 ' + ' · '.join(f'{x["품번"]}({" · ".join(x["사용 설비"])})' for x in found), same(spec_parts, sorted(x['품번'] for x in found), '6205-2RS')])
    found = ask(folder, MISSING)
    q3.append([f'질문 3 · 원자료에 없는 품번 {MISSING}', '어느 자료에도 없음', f'일치하는 품번 {len(found)}개(빈 목록 — 「없음」으로 구별)', same([], found, MISSING)])
    i_motor = src.rows('센서_목록.csv', lambda r: r['설비코드'] == 'HYD-06' and r['태그'] == 'I_MOTOR')
    unknown = [f'HYD-06 I_MOTOR의 정상값({ref("센서_목록.csv", [i for i, _ in i_motor])} 「{i_motor[0][1]["비고"]}」)은 미확인으로 남겼다',
               f'6205-2RS의 두 사내 품번을 합칠지는 구매팀이 검토 중이다(`현장_메모.md` {memo}행)']
    return decided, [q1, q2, *unit_rows, *q3], review, unknown


def practical(folder, result, src, graph):
    """실전반 — 갈래 ㄴ(조건부 승인 = 승인, 빈 조건 칸 = 조건 없음, PR-07 7.4 정보를 함께 남김)."""
    avl = src.rows(D.AVL_FILE)
    cond = [(i, r) for i, r in avl if r['조건']]
    seal_avl = [(i, r) for i, r in avl if r['품번'] == 'P-PMP-SEAL']
    rule_73 = src.line(D.PR07_FILE, 'SCM 구매 포털의 등록을 따른다')
    rule_74 = src.line(D.PR07_FILE, '전수 검사 비용')
    price_only = src.line(D.PR07_FILE, '단가만 보지 않는다')
    supply = {r['a'].split(':', 1)[1] + '→' + r['b']: r['props'] for r in graph['rels'] if r['type'] == 'SUPPLIES'}
    c_pair = f'{cond[0][1]["공급사"]}→{cond[0][1]["품번"]}'
    flagged = sorted(k for k, p in supply.items() if p.get('inspection'))
    decided = [
        ['조건이 붙은 승인', '조건부 승인도 승인 공급사(approved 참)로 두고, 조건은 condition에 그대로 보인다',
         f'{ref(D.AVL_FILE, [i for i, _ in cond])}(「{cond[0][1]["승인상태"]}」 · 「{cond[0][1]["조건"]}」), `{D.PR07_FILE}` {rule_73}행(승인 여부는 SCM 등록을 따름)',
         f'{c_pair}: approved {str(supply[c_pair]["approved"]).lower()} · 조건 「{supply[c_pair].get("condition")}」. 비승인으로 보면 이 쌍이 승인 공급사에서 빠진다'],
        ['빈 값의 뜻', '승인 목록의 빈 조건 칸은 조건이 없는 것으로 읽는다(condition을 두지 않음)',
         f'{ref(D.AVL_FILE, [i for i, r in seal_avl if r["승인상태"] == "승인"])}(조건 칸 빔), {ref(D.AVL_FILE, [i for i, _ in cond])}(조건을 적은 예)',
         '펌프 축 씰 키트의 승인 두 쌍에 조건이 없다. 「적지 않음」으로 읽으면 그 쌍에 등록 확인 요청이 붙는다'],
        ['쓰는 사람에 따라 갈리는 답', '구매 기준서 7.4에 걸리는 승인 공급사 쌍에 입고 검사 · 비교 가산 비용 · 근거 줄을 함께 남긴다',
         f'`{D.PR07_FILE}` {price_only}행(단가만 보지 않는다) · {rule_74}행(7.4)',
         ' · '.join(flagged) + f'에 입고 전수 검사 · 비교 +{D.PR74_EXTRA_MANWON}만 원. 남기지 않으면 단가 · 불량률만 보인다']]
    by_part = result['부품별 사용처']
    seal = src.rows('구성요소_목록.csv', lambda r: '철거' not in r['비고'] and ('PMP-SEAL' in r['교체부품'] and 'HT' not in r['교체부품'] and '22' not in r['교체부품']))
    shared = src.rows('예비품_목록.csv', lambda r: r['품번'] == 'P-PMP-SEAL')
    blank = src.rows('구성요소_목록.csv', lambda r: r['설비코드'] in ('HYD-01', 'HYD-02', 'HYD-03') and labs.NAME_ALIAS.get(r['구성요소']) == 'pump-a' and not r['교체부품'])
    exp_seal = sorted({r['설비코드'] for _, r in seal + blank})
    rows_ = [['질문 1 · 펌프 축 씰 키트를 쓰는 설비',
              f'{ref("구성요소_목록.csv", [i for i, _ in seal])}(품번 · 표기 변형), {ref("구성요소_목록.csv", [i for i, _ in blank])}(교체부품 칸 빔 — {ref("예비품_목록.csv", [i for i, _ in shared])} 「{shared[0][1]["비고"]}」) → ' + ' · '.join(exp_seal),
              ' · '.join(by_part['P-PMP-SEAL']['사용 설비']), same(exp_seal, by_part['P-PMP-SEAL']['사용 설비'], '사용 설비')]]
    quotes = {i: r for i, r in src.rows(D.QUOTE_FILE)}
    for row in by_part['P-PMP-SEAL']['공급 조건']:
        q = quotes[int(row['quote_source'].split()[1][:-1])]
        a = next((r for i, r in avl if r['공급사'] == row['공급사'] and r['품번'] == 'P-PMP-SEAL'), None)
        exp = [q['단가(만원)'], q['불량률'], q['납기(일)'], a['승인상태'] if a else '미등록']
        rows_.append([f'질문 2 · {row["공급사"]}',
                      f'`{row["quote_source"].split()[0]}` {row["quote_source"].split()[1]}(견적일 {q["견적일"]}): {q["단가(만원)"]}만 원 · 불량률 {q["불량률"]} · 납기 {q["납기(일)"]}일, `{row["approval_source"].split()[0]}` {row["approval_source"].split()[1]}: {exp[3]}',
                      f'approved {str(row["approved"]).lower()} · {row["price_manwon"]:g}만 원 · {row["defect_rate"]:g} · {row["lead_days"]}일 · 출처 {row["quote_source"]} · {row["approval_source"]} · 기준일 {row["as_of"]}'
                      + (f' · {row["inspection"]} +{row["compare_extra_manwon"]:g}만 원({row["rule_source"]})' if row.get('inspection') else ''),
                      same([float(exp[0]), float(exp[1]), int(exp[2]), exp[3]], [row['price_manwon'], row['defect_rate'], row['lead_days'], row['approval_status']], row['공급사'])])
    ht = src.rows('예비품_목록.csv', lambda r: r['품번'] == 'P-PMP-SEAL-HT')
    found = ask(folder, 'P-PMP-SEAL-HT')
    rows_.append(['질문 3 · 이름이 비슷한 다른 품번 P-PMP-SEAL-HT', f'{ref("예비품_목록.csv", [i for i, _ in ht])}(「{ht[0][1]["비고"]}」) → 다른 부품, 적용 모델 {ht[0][1]["적용모델"]}',
                  ' · '.join(f'{x["품번"]}({" · ".join(x["사용 설비"])})' for x in found), same(['P-PMP-SEAL-HT'], [x['품번'] for x in found], 'P-PMP-SEAL-HT')])
    old = src.rows('품번_교차표.csv', lambda r: r['다른표기'] == 'PS-4510')
    found = ask(folder, 'PS-4510')
    rows_.append(['질문 3 · 예전 품번 PS-4510', f'{ref("품번_교차표.csv", [i for i, _ in old])}(「{old[0][1]["표기종류"]}」) → {old[0][1]["사내품번"]}',
                  ' · '.join(f'{x["품번"]}({" · ".join(x["사용 설비"])}, 공급 조건 {len(x["공급 조건"])}개)' for x in found), same([old[0][1]['사내품번']], [x['품번'] for x in found], 'PS-4510')])
    found = ask(folder, MISSING)
    rows_.append([f'질문 3 · 원자료에 없는 품번 {MISSING}', '어느 자료에도 없음', f'일치하는 품번 {len(found)}개(빈 목록 — 공급 조건이 없는 부품의 「공급 조건: []」과 다른 모양)', same([], found, MISSING)])
    review = []
    for i, q in sorted(quotes.items()):
        key = next((k for k, p in supply.items() if p['quote_source'] == f'{D.QUOTE_FILE} {i}행'), None)
        p = supply.get(key, {})
        for col, prop, value in [('불량률', 'defect_rate_original', 'defect_rate'), ('납기(일)', 'lead_days_original', 'lead_days')]:
            if prop in p:
                review.append(f'- `{D.QUOTE_FILE}` {i}행의 {col} 「{q[col]}」 표기는 공급 조건 형식의 단위로 {p[value]:g}로 맞추고 원래 표기를 {prop}에 남겼습니다.')
    used = {int(p['quote_source'].split()[1][:-1]) for p in supply.values()}
    raw = [(i, col) for i in sorted(used) for col in ('불량률', '납기(일)') if not re.fullmatch(r'\d+(\.\d+)?', quotes[i][col])]
    if len(review) != len(raw):
        raise ValueError(f'완성본: 단위를 바꾼 견적 줄 {raw}과 원래 표기를 남긴 줄 {len(review)}개가 다릅니다.')
    expired = [i for i, q in quotes.items() if q['품번'] == 'P-CLR-PLT']
    unknown = ['견적의 납기는 견적서 값이다 — 입고 실측과 견주는 일은 이번 범위 밖이라 하지 않았다',
               f'P-CLR-PLT는 기준일에 유효한 견적이 없어({ref(D.QUOTE_FILE, expired)} 유효기한 경과) 공급 조건 관계가 없다']
    return decided, rows_, review, unknown


def bundle(course, workspace):
    is_supply = course == '실전반'
    session = ROOT / course / '실습/02회차'
    source = session / '랩' / LAB
    name = f'{course}_{LAB}_완성본'
    destination = session / '완성본' / (name+'.zip')
    before = student_files(source)
    folder = workspace/name
    shutil.copytree(source, folder)
    out = folder/'결과'
    shutil.copyfile(TOOLS/'모델실행.py', out/'모델실행.py')
    branch = labs.LAB4_INPUT_BRANCH[course]     # 실전반 완성본 = 갈래 ㄴ(다음 실습 입력/ 모델과 같은 결정)
    schema = labs.student_schema(labs.schema_for(is_supply, branch))
    if is_supply:
        base_constraints = labs.schema_for(False, 'A')['constraints']
        schema = {'classes': {'Supplier': schema['classes']['Supplier']}, 'relations': {'SUPPLIES': schema['relations']['SUPPLIES']},
                  'constraints': [c for c in schema['constraints'] if c not in base_constraints]}
        shutil.copyfile(TOOLS/'공급조건.py', out/'공급조건.py')
        purpose = '부품을 쓰는 설비·구성 요소를 찾고, 기준일의 유효 견적과 SCM 승인 상태, 값마다 출처를 함께 확인합니다.'
        decision = (f'공급 조건은 {D.REF_DATE} 기준으로 공급사·사내 품번별 가장 최근 유효 견적 한 건을 씁니다. SCM 등록 상태를 기준으로 승인과 조건부 승인을 포함하고 조건·기한을 함께 보존합니다. 비승인 상태도 견적과 구별해 남깁니다. '
                    f'구매 기준서 PR-07 7.4(불량률이 {D.PR74_RATE_PCT} %를 넘는 승인 공급사는 발주 때 입고 전수 검사, 비교 비용 +{D.PR74_EXTRA_MANWON}만 원)는 승인 여부를 바꾸지 않고, 걸리는 쌍에 입고 검사 · 비교 가산 비용 · 근거 줄로 붙입니다.')
    else:
        shutil.copyfile(TOOLS/'설비모델.py', out/'설비모델.py')
        dump(out/'표기_기준.json', {'구성요소_별칭': labs.NAME_ALIAS, '구성요소_이름': labs.CANON_NAME,
             '물리량_별칭': labs.WHAT_ALIAS, '단위_환산': labs.UNIT, '물리량_단위': D.QUANTITIES})
        purpose = '설비별 센서와 물리량, 단위·한계, 같은 부품을 쓰는 설비·구성 요소를 확인합니다.'
        decision = ('센서는 설비코드와 태그로, 부품은 사내 품번으로 구분합니다. 제조사 품번이 두 사내 품번에 걸리면 둘 다 표시합니다. 물리량의 기준 단위로 환산하고, '
                    '단위 칸이 빈 줄은 근거 줄이 있을 때만 그 단위로 채웁니다. 한계가 없는 채널에는 값을 채우지 않습니다.')
    dump(out/'설계_기준.json', schema)
    (out/'README.md').write_text('# 실행 결과\n\n모델실행.py가 자료를 읽어 schema.json, graph.json과 질문별_결과.json을 만듭니다. 명령을 실행할 때마다 이 세 파일을 다시 작성합니다.\n', encoding='utf-8')
    help_text = f'''# {course} 2회차 온톨로지 설계 완성본

{purpose} ZIP 전체를 별도 폴더에 풀고, 이 문서가 있는 폴더에서 터미널을 열어 실행하세요. Python 3 표준 라이브러리를 사용합니다. AI 계정이나 그래프 DB 접속 없이 실행할 수 있습니다.

```text
{COMMAND}
```

기본 조회는 펌프 씰 품번 P-PMP-SEAL입니다. 다른 품번 또는 품명을 마지막에 붙이면 그 대상의 사용처를 확인합니다.

```text
{COMMAND} P-PMP-SEAL-HT
{COMMAND} NO-SUCH-PART
```

먼저 구조 검사의 출력을 보고, 부품을 쓰는 설비·구성 요소와 표시된 품번을 자료에서 찾아 확인하세요. 결과/질문별_결과.json에는 전체 설비의 센서·측정 항목과 부품별 사용처가 있습니다. 결과/요구사항.md에는 정한 것과 질문마다 원자료에서 먼저 찾은 기대 답 · 실제 결과가, 결과/자료_검토.md에는 원자료와 비교할 위치가 있습니다.
'''
    (folder/'완성본_안내.md').write_text(help_text, encoding='utf-8')
    intro = (folder/'START.md').read_text(encoding='utf-8')
    (folder/'START.md').write_text(intro.split('\n', 1)[0]+'\n\n완성한 모델을 실행하려면 [완성본 안내](완성본_안내.md)를 여세요. 아래는 이 모델이 푸는 원래 과제입니다.\n'+intro.split('\n', 1)[1], encoding='utf-8')
    runs = []
    for _ in range(2):      # 같은 명령을 두 번 — 결과 파일이 같은 바이트여야 저장 · 다시 실행이 같은 결과다
        proc = subprocess.run([sys.executable, '-B', '-X', 'utf8', str(out/'모델실행.py')], cwd=folder, text=True, encoding='utf8', capture_output=True)
        if proc.returncode:
            raise ValueError(proc.stdout + proc.stderr)
        runs.append({n: digest((out/n).read_bytes()) for n in ['schema.json', 'graph.json', '질문별_결과.json']})
    if runs[0] != runs[1]:
        raise ValueError('같은 명령을 두 번 실행한 결과 파일이 다릅니다.')
    result = json.loads((out/'질문별_결과.json').read_text(encoding='utf-8'))
    graph = json.loads((out/'graph.json').read_text(encoding='utf-8'))
    src = Source(folder)
    decided, answers, review_extra, unknown = practical(folder, result, src, graph) if is_supply else integrated(folder, result, src)
    for code in ['P-PMP-SEAL']:          # 마지막 실행은 기본 품번 — 결과 파일이 안내와 같은 상태로 남는다
        ask(folder, code)
    if {n: digest((out/n).read_bytes()) for n in runs[0]} != runs[0]:
        raise ValueError('품번 조회가 결과 파일을 바꿨습니다.')
    L = labs.design_lab(course)
    requirement = (
        f'# 요구사항\n\n## 목표와 질문\n\n{purpose}\n\n' + ''.join(f'{i}. {q}\n' for i, q in enumerate(L['questions'], 1))
        + f'\n## 이 답을 쓰는 사람과 쓰는 곳\n\n{L["user"]}\n\n'
        + f'## 사용할 자료와 기준일\n\n- `자료/`의 원자료(기준일 {D.REF_DATE})' + (', `입력/`의 제공된 설비 · 부품 모델' if is_supply else '') + '\n\n'
        + '## 지킬 조건\n\n- 원자료는 읽기만 하고, 만든 것은 `결과/`에 둔다.\n- 원자료에 없는 값을 만들지 않고, 미확인 · 값 없음 · 0을 구별한다.\n'
        + f'- {decision}\n\n'
        + '## 정한 것\n\n' + table(['지점(종류)', '고른 것', '근거(파일 · 줄)', '이 선택으로 바뀌는 답'], decided) + '\n'
        + '## 기대 답과 실제 결과\n\n' + table(['질문 · 물은 대상', '원자료에서 먼저 찾은 기대 답(파일 · 줄)', '실제 결과', '고친 점 · 다시 확인'], answers) + '\n'
        + f'## 저장 기록\n\n- 기준일: {D.REF_DATE}\n- 저장 시점: {D.REF_DATE} 자료로 만든 판(같은 명령 `{COMMAND}`을 두 번 실행해 `결과/schema.json` · `graph.json` · `질문별_결과.json`이 같은 바이트)\n'
        + '- 확인하지 못한 점: ' + ' '.join(x + '.' for x in unknown) + '\n')
    (out/'요구사항.md').write_text(requirement, encoding='utf-8')

    def relevant(file, predicate):
        return [f'{file} {i}행' for i, row in src.rows(file, predicate)]
    lines = ['# 원자료에서 확인한 내용', '', decision, '']
    if is_supply:
        for row in result['부품별 사용처']['P-PMP-SEAL']['공급 조건']:
            extra = f" {row['rule_source']}에 따라 {row['inspection']}, 비교 비용 +{row['compare_extra_manwon']:g}만원." if row.get('inspection') else ''
            lines.append(f"- {row['공급사']}: {row['quote_source']}의 견적, {row['approval_source']}의 {row['approval_status']}. 단가 {row['price_manwon']}만원, 불량률 {row['defect_rate']:g}(비율), 납기 {row['lead_days']}일.{extra}")
        lines.extend(review_extra)
        lines.extend(['', '기간이 지난 견적과 같은 쌍의 이전 견적은 결과/견적_제외근거.json에서 확인합니다.'])
    else:
        lines.extend(['- 이관 코드와 현재 실물은 기능위치·일련번호로 대조했습니다. '+', '.join(relevant('설비_대장.csv', lambda x: x['상태'] == '코드 통합')),
                      '- 철거 기록은 현재 설치된 구성 요소와 나눴습니다. '+', '.join(relevant('구성요소_목록.csv', lambda x: '철거' in x['비고'])),
                      '- W와 kPa로 온 값은 kW와 bar로 환산했습니다. '+', '.join(relevant('센서_목록.csv', lambda x: x['단위'] in ('W', 'kPa'))),
                      *review_extra,
                      '- 공용 부품의 사용 설비: '+', '.join(result['부품별 사용처']['P-PMP-SEAL']['사용 설비'])+'. 예비품_목록.csv와 품번_교차표.csv에서 해당 품번과 대체 표기를 찾고 구성요소_목록.csv의 사용처와 비교합니다.'])
    (out/'자료_검토.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    assert before == student_files(source)
    package_files = student_files(folder)
    temp = workspace/(name+'.zip')
    with zipfile.ZipFile(temp, 'w') as archive:
        for rel in package_files:
            entry = zipfile.ZipInfo(name+'/'+rel, (2026, 1, 1, 0, 0, 0)); entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, (folder/rel).read_bytes())
    with zipfile.ZipFile(temp) as archive:
        assert archive.testzip() is None
        assert {n.split('/', 1)[1]: digest(archive.read(n)) for n in archive.namelist()} == package_files
    destination.parent.mkdir(parents=True, exist_ok=True)
    os.replace(temp, destination)
    print(f'{destination} · {len(package_files)}개 파일 · {digest(destination.read_bytes())}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--course', choices=['통합반', '실전반'], required=True)
    parser.add_argument('--work', required=True, type=Path)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=args.work) as temp:
        bundle(args.course, Path(temp).resolve())
