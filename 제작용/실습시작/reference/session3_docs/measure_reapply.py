"""강사 참조: 다른 문서 재적용 실측 — 추출 함수 1판(HM-8에 맞춘 규칙)과 2판(재적용 뒤 고친 규칙)을 같은 기대 목록으로 잰다.

기대 목록은 원문을 사람이 읽고 정한 것이다(아래 EXPECT). 잰 것:
  - 단계 누락: 원문 `###` 절차의 번호 단계 중 같은 절차·번호의 step 후보가 없는 것(원문 구조에서 자동으로 셈)
  - 기준값 누락: 기대 기준값(절·값·단위) 중 맞는 unit_value 후보가 없는 것
  - 조건 누락: 기대 조건(절·종류·인용 조각) 중 같은 종류이면서 인용에 그 조각이 있는 후보가 없는 것(종류가 다르면 누락으로 셈)
  - 참조 누락: 기대 참조(인용 조각 → 참조 ID) 중 refs에 그 ID가 없는 것
  - 근거 없는 생성: unit_value 후보 중 원문의 기준값이 아닌 것(기대 기준값 목록에 없음) — 이름 속 수치·환산·호기·문서 번호 등
  - 계약 위반: 학생 시작본과 같은 검사기(check_candidates.check)가 낸 오류 수
결과: 재적용_실측.md, 재적용_실측.json
"""
from pathlib import Path
import importlib.util
import json
import re
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import extract_reference as v2  # noqa: E402
import extract_v1_hm8 as v1  # noqa: E402

U = {'℃': 'C', '°C': 'C', 'operating hours': 'h', '운전시간': 'h', 'h': 'h', 'minutes': 'min', '분': 'min', 'weeks': 'wk', '주': 'wk',
     'months': 'mo', '개월': 'mo', '시간': 'hr'}


def unit(u):
    return U.get(u, u)


# 절, 값, 단위(정규화). 언어를 가리지 않는 기준값. 'en'·'ko' 표시는 그 언어 원문에만 있는 것.
EXPECT = {
    'OEM-HPP45A-MM': {
        'values': [('1', 0, 'psi'), ('1', 40, 'C'), ('2', 150, 'h'), ('2', 1000, 'h'), ('2', 6, 'mo', 'en'), ('2', 4000, 'h'), ('2', 2000, 'h'),
                   ('2', 12, 'mo'), ('2', 2000, 'h'), ('2', 8000, 'h'), ('2', 10, 'µm'), ('2', 125, 'µm'),
                   ('3', 25, 'psi'), ('3', 30, 'C'), ('3', 0, 'psi'), ('3', 10, 'µm'), ('3', 35, 'N·m'), ('3', 10, 'min'), ('3', 10, 'psi'),
                   ('4', 1450, 'psi'), ('4', 20, 'C'), ('4', 2, 'wk'), ('4', 100, 'h'), ('4', 200, 'psi'), ('4', 50, 'h'), ('4', 4, 'wk'),
                   ('4', 200, 'h'), ('4', 90, '%'), ('4', 0, 'psi'), ('4', 20, 'C'), ('4', 90, '%'), ('5', 70, 'C'), ('6', 15, 'min')],
        'also': [('5', 158, '°F'), ('2', 1, '회')],   # 원문에 있으나 별도 기준이 아닌 것(같은 기준의 환산·「월 1회」) — 근거 없는 생성으로 세지 않음
        'conds': [('1', 'precondition', 'Before opening any hydraulic line', '열기 전에 펌프를 세우고'),
                  ('1', 'prohibition', 'Do not open the circuit until', '회로를 열지 않는다'),
                  ('1', 'prohibition', 'Never loosen a fitting', '피팅을 풀지 않는다'),
                  ('1', 'precondition', 'Allow the fluid to cool below 40', '40 °C 아래로 식힌다'),
                  ('3', 'prohibition', 'are not valid', '지시기 값은 쓰지 않는다'),
                  ('3', 'precondition', 'confirm that the gauge reads 0 psi', '압력계가 0 psi인지 확인한다'),
                  ('3', 'prohibition', 'Do not clean and reuse', '다시 쓰지 않는다'),
                  ('3', 'precondition', 'If metal particles are visible', '금속 입자가 보이면'),
                  ('3', 'completion', 'must be below 10 psi', '10 psi 미만이어야 한다'),
                  ('4', 'prohibition', 'Never charge with oxygen', '충전하지 않는다'),
                  ('4', 'prohibition', 'Use dry nitrogen only', '건조 질소만 쓴다'),
                  ('4', 'precondition', 'fallen by more than 200 psi', '200 psi 넘게 떨어졌으면'),
                  ('4', 'precondition', 'Recharge if the precharge is below 90', '90 % 미만이면 재충전한다'),
                  ('4', 'precondition', 'must read 0 psi before the charging kit', '충전 키트를 연결하기 전에'),
                  ('4', 'precondition', 'If the corrected value is below 90', '보정한 값이 명판 값의 90 % 미만이면'),
                  ('4', 'completion', 'Record the corrected value', '보정한 값과 날짜'),
                  ('6', 'completion', 'confirm that there are no leaks', '누유가 없는지 확인한다'),
                  ('6', 'completion', 'must be within the limits', '시운전 기록의 한계 안에')],
        'refs': [('safety steps in Section 1', '1', '1절의 안전 조치', '1')],
    },
    'PM-02': {
        'values': [('PM-2.3', 2000, 'h'), ('PM-2.3', 10, '%'), ('PM-2.3', 1800, 'h'), ('PM-2.3', 2200, 'h'), ('PM-2.4', 1950, 'h'), ('PM-2.4', 50, 'h'),
                   ('PM-2.5', 1800, 'h'), ('PM-2.5', 2200, 'h'), ('PM-2.5', 2200, 'h'), ('PM-2.5', 24, 'hr'), ('PM-2.5', 80, '만 원'), ('PM-2.5', 4, '명'),
                   ('PM-2.5', 4, '명'), ('PM-2.5', 60, '만 원'), ('PM-2.5', 3, '개'), ('PM-2.5', 2, '개'), ('PM-2.5', 2, '개'), ('PM-2.5', 4, '명'),
                   ('PM-2.5', 2, '개'), ('PM-2.6', 0, 'bar'), ('PM-2.9', 90, '%'), ('PM-2.9', 15, 'min'), ('PM-2.9', 178, 'bar'), ('PM-2.9', 8.8, 'l/min'),
                   ('PM-2.9', 1.2, 'mm/s'), ('PM-2.10', 2000, 'h'), ('PM-2.10', 1, 'min'), ('PM-2.10', 165, 'bar'), ('PM-2.10', 1, 'min'),
                   ('PM-2.10', 8.0, 'l/min'), ('PM-2.10', 165, 'bar')],
        'also': [('PM-2.2', 10000, 'h'), ('PM-2.2', 12000, 'h'), ('PM-2.2', 16000, 'h')],   # 시행 차례 목록의 일부(보류 대상)
        'conds': [('PM-2.3', 'prohibition', '허용 오차 상한을 넘기는 일정은 잡지 않는다'), ('PM-2.3', 'completion', '시행 기록에는'),
                  ('PM-2.4', 'prohibition', '낮에 생산 중인 설비는 세우지 않는'), ('PM-2.5', 'precondition', '허용 오차 하한 1,800 h 이상이면'),
                  ('PM-2.5', 'prohibition', '그 시간까지 기다리지 않는다'), ('PM-2.5', 'prohibition', '미루지 않는다'),
                  ('PM-2.5', 'precondition', '4명보다 적으면'), ('PM-2.5', 'precondition', '3개 미만이면'),
                  ('PM-2.5', 'prohibition', '정기 정비를 시행하지 않는다'), ('PM-2.5', 'precondition', '두 대를 묶으려면'),
                  ('PM-2.6', 'prohibition', '확인하기 전에는 배관을 열지 않는다'), ('PM-2.6', 'precondition', '0 bar인지 확인한 뒤에만'),
                  ('PM-2.9', 'completion', '15분 시운전해'), ('PM-2.9', 'completion', '계수기를 0으로 되돌리고'),
                  ('PM-2.9', 'prohibition', '정비 오더를 닫지 않는다')],
        'refs': [('2,000 h 정기 점검의 1~6단계', 'SOP-PM-21'), ('4,000 h 정기 점검의 1~3단계', 'SOP-PM-22'), ('잠금을 풀고 PM-2.9', 'PM-2.9')],
    },
    'HI-01': {
        'values': [], 'also': [],
        'conds': [('HI-1', 'prohibition', '교체하지 않고'), ('HI-1.1', 'precondition', '조회가 실패하면'),
                  ('HI-1.2', 'precondition', '조회에 성공한 경우에만'), ('HI-1.2', 'precondition', '정비 완료라고 적혀 있어도'),
                  ('HI-1.3', 'prohibition', '임의의 부품을 관련 부품으로 지정하지 않는다'), ('HI-1.3', 'prohibition', '도착 완료라고 보고하지 않는다'),
                  ('HI-1.4', 'prohibition', '기록을 대신하지 않는다')],
        'refs': [],
    },
}
FILES = {'OEM-HPP45A-MM': 'OEM-HPP45A-MM_maintenance-excerpt.md', 'PM-02': 'PM-02_powerpack-pm-checklist.md', 'HI-01': 'HI-01_shift-inspection-supplement.md'}


def checker():
    """학생 시작본과 같은 검사기를 이 폴더의 자료로 불러온다."""
    tmp = Path(tempfile.mkdtemp())
    sys.path.insert(0, str(HERE.parents[1]))
    import build_session3_documents as b
    (tmp / 'check_candidates.py').write_text(b.CHECKER, encoding='utf-8')
    shutil.copytree(HERE / '자료', tmp / '자료')
    spec = importlib.util.spec_from_file_location('chk', tmp / 'check_candidates.py')
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod, tmp


def steps(md):
    out, proc = [], None
    for line in md.splitlines():
        m = re.match(r'^###\s+(\S+)', line)
        if m:
            proc = m.group(1); continue
        if line.startswith('## '):
            proc = None; continue
        s = re.match(r'^(\d+)\.\s', line)
        if proc and s:
            out.append((proc, int(s.group(1))))
    return out


def measure(result, doc, lang, md, chk, tmp):
    e = EXPECT[doc]
    cands = result['candidates']
    got_steps = {(c['procedure'], c.get('order')) for c in cands if c['kind'] == 'step'}
    want_steps = steps(md)
    miss_steps = [s for s in want_steps if s not in got_steps]
    pool = [(c['section'], c['value'], unit(c['unit'])) for c in cands if c['kind'] == 'unit_value']
    want = [v for v in e['values'] if len(v) == 3 or v[3] == lang]
    left = list(pool)
    miss_vals = []
    for v in want:
        key = (v[0], v[1], v[2])
        if key in left:
            left.remove(key)
        else:
            miss_vals.append(key)
    also = [(a[0], a[1], a[2]) for a in e['also']]
    ungrounded = [k for k in left if k not in also and not any((k[0], k[1], k[2]) == w[:3] for w in want)]
    miss_conds = []
    for item in e['conds']:
        sec, kind = item[0], item[1]
        frag = item[2] if len(item) == 3 else (item[2] if lang == 'en' else item[3])
        if not any(c['section'] == sec and c['kind'] == kind and frag in c['quote'] for c in cands):
            miss_conds.append(f'{sec} {kind} 「{frag}」')
    miss_refs = []
    for r in e['refs']:
        frag, rid = (r[0], r[1]) if len(r) == 2 or lang == 'en' else (r[2], r[3])
        if not any(frag in c['quote'] and rid in c['refs'] for c in cands):
            miss_refs.append(f'「{frag}」→{rid}')
    path = tmp / f'{doc}_{lang}.json'
    path.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
    errors, _ = chk.check(path)
    return {'후보': len(cands), '단계 기대': len(want_steps), '단계 누락': len(miss_steps), '기준값 기대': len(want), '기준값 누락': len(miss_vals),
            '조건 기대': len(e['conds']), '조건 누락': len(miss_conds), '참조 기대': len(e['refs']), '참조 누락': len(miss_refs),
            '근거 없는 생성': len(ungrounded), '계약 위반': len(errors),
            '사례': {'단계 누락': miss_steps[:6], '기준값 누락': miss_vals[:8], '조건 누락': miss_conds[:8], '참조 누락': miss_refs,
                   '근거 없는 생성': ungrounded[:8], '계약 위반': errors[:4]}}


def main():
    chk, tmp = checker()
    rows, data = [], {}
    for doc, name in FILES.items():
        path = HERE / '자료/원문' / name
        md = path.read_text(encoding='utf-8')
        langs = ['en', 'ko'] if doc == 'OEM-HPP45A-MM' else ['ko']
        for lang in langs:
            for label, fn in [('1판(HM-8에 맞춤)', lambda: v1.extract(path, doc)), ('2판(재적용 뒤 수정)', lambda: v2.extract(path, doc, lang))]:
                if label.startswith('1판') and lang == 'en':
                    continue   # 1판에는 언어 선택이 없다(두 언어 줄을 모두 문장으로 읽음) — ko 행 하나로 잰다
                m = measure(fn(), doc, lang, md, chk, tmp)
                key = f'{doc} {lang if doc == "OEM-HPP45A-MM" else ""} {label}'.replace('  ', ' ')
                data[key] = m
                rows.append(f'| {doc} | {lang if doc == "OEM-HPP45A-MM" else "-"} | {label} | {m["후보"]} | {m["단계 누락"]}/{m["단계 기대"]} | {m["기준값 누락"]}/{m["기준값 기대"]} | {m["조건 누락"]}/{m["조건 기대"]} | {m["참조 누락"]}/{m["참조 기대"]} | {m["근거 없는 생성"]} | {m["계약 위반"]} |')
    head = ['# 다른 문서 재적용 실측', '', '`python measure_reapply.py`가 만든 파일이다. 같은 기대 목록(원문을 사람이 읽고 정함)으로 1판과 2판을 잰다. 누락은 「누락 수/기대 수」.', '',
            '| 문서 | 인용 언어 | 추출 함수 | 후보 | 단계 누락 | 기준값 누락 | 조건 누락 | 참조 누락 | 근거 없는 생성 | 계약 위반 |', '|---|---|---|---|---|---|---|---|---|---|']
    lines = head + rows + ['', '## 사례(앞부분)', '']
    for k, m in data.items():
        lines.append(f'### {k}')
        for kk, vv in m['사례'].items():
            if vv:
                lines.append(f'- {kk}: {vv}')
        lines.append('')
    (HERE / '재적용_실측.md').write_text('\n'.join(lines), encoding='utf-8')
    (HERE / '재적용_실측.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print('\n'.join(head[-2:] + rows))
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    main()
