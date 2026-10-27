"""검사기 고의 손상 시험 — 학생 시작본과 같은 check_candidates.py·check_card.py·lab_cypher.py가 망가뜨린 입력을 잡는지 본다.

정상 입력은 강사 참조 결과(검토결과·추출결과·실습5_실행/결과의 카드)이다. 각 시험은 정상 입력을 한 곳만 망가뜨린다.
기대: 정상 입력은 통과(rc 0), 망가뜨린 입력은 rc 1과 해당 오류 문구. 결과: 시험결과.md
사용: python run_tests.py
"""
from pathlib import Path
import copy
import json
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
REF = HERE.parent
ROOT = REF.parents[2].parent if (REF.parents[2] / "산출물").exists() is False else REF.parents[2]
LAB4 = ROOT / '산출물/실전반/실습/03회차/랩/03일차_실습4_지식추출'
LAB5 = REF / '실습5_실행'
PY = sys.executable


def run(cwd, *args):
    r = subprocess.run([PY, *args], cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace', env={**__import__('os').environ, 'PYTHONUTF8': '1'})
    return r.returncode, r.stdout + r.stderr


def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def cand_tests():
    hm8 = load(REF / '검토결과/HM-8_검토.json')
    oem = load(REF / '추출결과/OEM-HPP45A-MM_후보.json')
    def first(d, kind):
        return next(i for i, c in enumerate(d['candidates']) if c['kind'] == kind)
    t = []
    def case(name, base, change, expect):
        d = copy.deepcopy(base); change(d); t.append((name, d, expect))
    s = first(hm8, 'step'); u = first(hm8, 'unit_value')
    case('01_인용글자변경', hm8, lambda d: d['candidates'][s].__setitem__('quote', d['candidates'][s]['quote'].replace('LOCAL', 'REMOTE')), '그대로 없음')
    case('02_인용다른절', hm8, lambda d: d['candidates'][s].__setitem__('section', 'HM-8.3'), '그대로 없음')
    case('03_원문없는인용', hm8, lambda d: d['candidates'][s].__setitem__('quote', '팬 속도를 120 %로 올린다.'), '원문 어디에도 없음')
    case('04_해시지어냄', hm8, lambda d: d.__setitem__('source_sha256', '0' * 64), 'source_sha256')
    case('05_종류오류', hm8, lambda d: d['candidates'][s].__setitem__('kind', 'action'), '알 수 없는 kind')
    case('06_값텍스트없음', hm8, lambda d: d['candidates'][u].__setitem__('value_text', '99 ℃ 이상'), 'value_text')
    case('07_비교기호오류', hm8, lambda d: d['candidates'][u].__setitem__('comparator', '이상'), 'comparator')
    case('08_범위최대값없음', hm8, lambda d: (d['candidates'][u].__setitem__('comparator', 'range'), d['candidates'][u].pop('value_max', None)), 'value_max')
    case('09_없는절차', hm8, lambda d: d['candidates'][s].__setitem__('procedure', 'SOP-COOL-99'), '없는 절차')
    case('10_중복후보', hm8, lambda d: d['candidates'].append(dict(d['candidates'][s], id='DUP-1')), '이미 있음')
    case('11_단계번호없음', hm8, lambda d: d['candidates'][s].pop('order'), 'order')
    case('13_검토상태불일치', hm8, lambda d: d['candidates'][s].__setitem__('status', 'pending'), 'status는 approved')
    case('14_수정전값없음', hm8, lambda d: next(c for c in d['candidates'] if c['decision'] == '수정').pop('before'), 'before')
    case('15_이유없음', hm8, lambda d: d['candidates'][s].__setitem__('reason', ''), 'reason')
    case('16_누락인용지어냄', hm8, lambda d: d['missing'][0].__setitem__('quote', '없는 문장이다.'), 'missing')
    case('17_필드없음', hm8, lambda d: d['candidates'][s].pop('refs'), '필수 필드 없음')
    case('18_문서식별자불일치', hm8, lambda d: (d.__setitem__('doc_id', 'HM-7'), [c.__setitem__('doc_id', 'HM-7') for c in d['candidates']]), '문서_목록의 식별자')
    case('19_문서목록에없는파일', hm8, lambda d: d.__setitem__('source_file', 'HM-8_rev1.2_draft.md'), '파일이 없습니다')
    s2 = next(i for i, c in enumerate(oem['candidates']) if c['kind'] == 'step')
    case('12_추출직후승인', oem, lambda d: d['candidates'][s2].__setitem__('status', 'approved'), 'status는 pending')
    case('20_OEM없는절차', oem, lambda d: d['candidates'][s2].__setitem__('procedure', 'T-3.9'), '없는 절차')
    case('21_번역줄을다른절로', oem, lambda d: d['candidates'][s2].__setitem__('section', '4'), '그대로 없음')
    case('22_order가참거짓', oem, lambda d: d['candidates'][s2].__setitem__('order', True), 'order')
    return sorted(t)


def main():
    lines = ['# 검사기 고의 손상 시험 결과', '', '`python run_tests.py`가 만든 파일. 정상 입력을 한 곳만 망가뜨려 학생 시작본과 같은 검사기로 실행했다.', '',
             '| 시험 | 검사기 | rc | 기대 문구 | 잡음 |', '|---|---|---|---|---|']
    ok_all = True
    work = Path(tempfile.mkdtemp())
    lab4 = work / 'lab4'
    shutil.copytree(LAB4, lab4)
    for f in sorted((REF / '검토결과').glob('*.json')) + sorted((REF / '추출결과').glob('*.json')):
        rc, out = run(lab4, 'check_candidates.py', str(f))
        lines.append(f'| 정상 {f.parent.name}/{f.name} | check_candidates | {rc} | 통과 | {"예" if rc == 0 else "아니오(오탐)"} |'); ok_all &= rc == 0
    for name, data, expect in cand_tests():
        p = HERE / f'{name}.json'
        p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
        rc, out = run(lab4, 'check_candidates.py', str(p))
        hit = rc == 1 and expect in out
        ok_all &= hit
        lines.append(f'| {name} | check_candidates | {rc} | {expect} | {"예" if hit else "아니오"} |')
    # 단계 점검: 빈 학생 몫 칸 경고
    rc, out = run(lab4, 'check_candidates.py')
    hit = rc == 1 and '완료 아님' in out and '빈 칸' in out
    lines.append(f'| 23_단계점검_빈시작본 | check_candidates(인자 없음) | {rc} | 완료 아님·빈 칸 | {"예" if hit else "아니오"} |'); ok_all &= hit
    # 리허설 2 실전 3-4 제안 1: 검토가 모두 보류(approved 0)면 완료 아님, 모두 채택·누락 0이면 정보
    hm8 = json.loads((REF / '검토결과/HM-8_검토.json').read_text(encoding='utf-8'))
    (lab4 / '결과/검토').mkdir(parents=True, exist_ok=True)
    (lab4 / '결과/후보').mkdir(parents=True, exist_ok=True)
    shutil.copy2(REF / '추출결과/HM-8_후보.json', lab4 / '결과/후보/HM-8.json')
    stage_cases = [('정상 검토(채택·수정·보류 섞임)', hm8, None, ['approved 후보가 없습니다', '모든 후보가 「채택」']),
                   ('30_검토가모두보류', 'pending', 'approved 후보가 없습니다', []),
                   ('31_모두채택·누락0(정보)', 'all', '모든 후보가 「채택」이고 누락 기록이 0개', [])]
    for name, mode, expect, absent in stage_cases:
        d = copy.deepcopy(hm8)
        if mode == 'pending':
            for c in d['candidates']:
                c.update(decision='보류', status='pending', reason='미검토')
        elif mode == 'all':
            for c in d['candidates']:
                c.update(decision='채택', status='approved')
                c.pop('before', None)
            d['missing'] = []
        (lab4 / '결과/검토/HM-8_검토.json').write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding='utf-8')
        rc, out = run(lab4, 'check_candidates.py')
        hit = (expect is None or expect in out) and not any(a in out for a in absent)
        ok_all &= hit
        lines.append(f'| {name} | check_candidates(인자 없음) | {rc} | {expect or "해당 문구 없음"} | {"예" if hit else "아니오"} |')
    # 실습5 카드 검사기
    lab5 = work / 'lab5'
    shutil.copytree(LAB5, lab5, ignore=shutil.ignore_patterns('__pycache__'))
    good = (lab5 / '결과/작업확인카드_SOP-COOL-14.md').read_text(encoding='utf-8')
    rc, out = run(lab5, 'check_card.py')
    base = rc == 0 and '작업확인카드_SOP-COOL-14.md: 형식 통과' in out
    lines.append(f'| 정상 카드 5개 | check_card | {rc} | 통과 | {"예" if base else "아니오(오탐)"} |'); ok_all &= base
    card_cases = [
        ('24_카드제목없음', good.replace('## 지난 시행 기록', '## 지난 기록'), '「## 지난 시행 기록」 없음'),
        ('25_카드인용변경', good.replace('「고압수는 쓰지 않는다.」', '「고압수는 써도 된다.」'), '그대로 없는 인용'),
        ('26_카드없는작업지시', good.replace('WO-2026-04161', 'WO-2026-09999'), '없는 작업지시'),
        ('27_카드항목인용없음', good.replace('- 고압수는 쓰지 않는다. — HM-8.7 「고압수는 쓰지 않는다.」', '- 고압수는 쓰지 않는다. — HM-8.7'), '인용」이 없음'),
        ('28_카드빈절', __import__('re').sub(r'(## 승인\n\n)- .*\n', r'\1', good), '아래가 비어 있음'),
    ]
    for name, text, expect in card_cases:
        (lab5 / '결과/작업확인카드_SOP-COOL-14.md').write_text(text, encoding='utf-8')
        (HERE / f'{name}.md').write_text(text, encoding='utf-8')
        rc, out = run(lab5, 'check_card.py')
        hit = rc == 1 and expect in out
        ok_all &= hit
        lines.append(f'| {name} | check_card | {rc} | {expect} | {"예" if hit else "아니오"} |')
    (lab5 / '결과/작업확인카드_SOP-COOL-14.md').write_text(good, encoding='utf-8')
    wipe = HERE / '29_전체삭제.cypher'
    wipe.write_text('MATCH (k:Knowledge) SET k.x = 1;\nMATCH (n) DETACH DELETE n;\n', encoding='utf-8')
    load = (lab5 / '결과/load.cypher').read_text(encoding='utf-8')
    (lab5 / '결과/load.cypher').write_text(load + 'MATCH (n) DETACH DELETE n;\n', encoding='utf-8')
    rc, out = run(lab5, 'check_card.py')
    hit = rc == 1 and '전체 삭제문' in out
    lines.append(f'| 29_적재문에전체삭제(check_card) | check_card | {rc} | 전체 삭제문 | {"예" if hit else "아니오"} |'); ok_all &= hit
    rc, out = run(lab5, 'lab_cypher.py', 'run', str(wipe))
    hit = rc == 1 and '전체 삭제문' in out and '-- 1/' not in out
    lines.append(f'| 29_전체삭제(lab_cypher run, 첫 문장도 실행 안 함) | lab_cypher | {rc} | 전체 삭제문 | {"예" if hit else "아니오"} |'); ok_all &= hit
    shutil.rmtree(work, ignore_errors=True)
    lines += ['', f'결론: {"모든 손상을 잡았고 정상 입력은 통과했다" if ok_all else "잡지 못한 손상 또는 오탐이 있다 — 위 표"}.']
    (HERE / '시험결과.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines))
    sys.exit(0 if ok_all else 1)


if __name__ == '__main__':
    main()
