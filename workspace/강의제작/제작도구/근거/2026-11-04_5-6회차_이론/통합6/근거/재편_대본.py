"""통합반 6회차 대본 재편: 변경전/ 대본 세 편 + 새 덱 MD 제목에서 새 대본 세 편을 만든다.
python3 작업/2026-11-04_5-6회차-이론/통합6/근거/재편_대본.py [구성표.md]   — 구성표를 주면 01편 「이 회차의 구성」 표를 그 값으로 넣는다
"""
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
W = ROOT / '작업/2026-11-04_5-6회차-이론/통합6'
DECK = ROOT / 'workspace/강의제작/제작도구/온라인/decks/integrated/day06/통합반_06일차.md'
OUTD = ROOT / 'workspace/강의제작/산출물/통합반/이론/06회차/대본'
sys.path.insert(0, str(W / '근거'))
from 재편_내용 import ORDER  # noqa: E402
from 재편_대본내용 import NARR_EDITS, DROP_PARAS, NARR_REPLACE, NEW_NARR, PRACTICE  # noqa: E402

FILES = ['01_이론_재사용가능한업무지침.md', '02_이론_외부도구연결원리.md', '03_이론_연결안전과실습안내.md']

# 옛 대본 구획
old = {}
for f in FILES:
    lines = (W / '변경전' / f).read_text(encoding='utf-8').split('\n')
    cur, buf = None, []
    for ln in lines + ['---']:
        m = re.match(r'^## \[SLIDE (\d+)(?:~(\d+))?\] ', ln)
        if m:
            cur, buf = int(m.group(1)), []
            continue
        if cur is not None and (ln.strip() == '---' or ln.startswith('# ') or ln.startswith('## ')):
            old[cur] = '\n'.join(buf).strip()
            cur = None
            continue
        if cur is not None:
            buf.append(ln)
assert len([k for k in old if k <= 57 or k >= 66]) == 64, sorted(old)

titles = {int(m.group(1)): m.group(2).replace(' / ', ' ') for m in re.finditer(r'^## SLIDE (\d+) — (.*)$', DECK.read_text(encoding='utf-8'), re.M)}
assert len(titles) == 78


def rep(text, pairs, where):
    for a, b in pairs:
        n = text.count(a)
        if n != 1:
            raise SystemExit(f'{where}: 「{a[:50]}」 {n}번')
        text = text.replace(a, b)
    return text


def body(new_no):
    kind, key = ORDER[new_no - 1]
    if kind == 'new':
        return NEW_NARR[key].strip()
    if key in NARR_REPLACE:
        return NARR_REPLACE[key].strip()
    t = old[key]
    if key in DROP_PARAS:
        i = t.find(DROP_PARAS[key])
        assert i >= 0, (key, DROP_PARAS[key])
        if key == 66:   # 한 줄만 지운다
            j = t.index('\n', i)
            t = (t[:i] + t[j + 1:]).strip()
        else:
            t = t[:i].strip()
    return rep(t, NARR_EDITS.get(key, []), f'옛 {key} 대본').strip()


def slide(n):
    return f'## [SLIDE {n:02d}] {titles[n]}\n\n{body(n)}\n\n---\n'


def head(title, rng, note):
    return (f'# 통합반 6회차 — {title}\n\n> 분할 수정 원본. 제목·표·제작 표시는 낭독하지 않는다.\n\n'
            f'## 촬영 전 안내 — 낭독하지 않음\n\n대응 덱: [통합반_06일차.pptx](../통합반_06일차.pptx) {rng}장. {note}\n')


def tail(items):
    return '# 촬영 본문 끝\n\n## 제작 확인용 — 낭독하지 않음\n\n' + '\n'.join(f'- {x}' for x in items) + '\n'


ROW = {59: ('업무 수행 방법을 재사용 가능한 능력으로 만들기', 35), 60: ('AI가 여러 시스템의 기능을 사용하는 원리 이해하기', 30),
       61: ('여러 도구를 연결할 때 지켜야 할 안전 기준 이해하기', 20)}

table = ''
if len(sys.argv) > 1:
    t = Path(sys.argv[1]).read_text(encoding='utf-8')
    rows = [ln for ln in t.split('\n') if ln.startswith('|')]
    i = rows.index('| 구분 | 실라버스 행 | 배정 | 장 | 낭독 추정 |')
    waits = {}
    for f in FILES:
        cur = None
        for ln in (OUTD / f).read_text(encoding='utf-8').split('\n'):
            m = re.match(r'^## \[SLIDE (\d+)', ln)
            if m: cur = int(m.group(1))
            m = re.match(r'^> \[대기 (\d+)초\]', ln)
            if m and cur: waits[cur] = waits.get(cur, 0) + int(m.group(1))
    out = ['| 구분 | 실라버스 제목 | 원래 배정 | 해당 SLIDE | 낭독 추정 | 학습 대기 |', '|---|---|---:|---|---:|---:|']
    for ln in rows[i + 2:]:
        c = [x.strip() for x in ln.strip('|').split('|')]
        a, b = (int(x) for x in c[3].split('~'))
        out.append(f'| {c[0]} | {c[1]} | {c[2]} | {c[3]} | {c[4]} | {sum(v for k, v in waits.items() if a <= k <= b)}초 |')
    table = '\n## 이 회차의 구성\n\n' + '\n'.join(out) + '\n'

# 01편
p = [head(ROW[59][0], '1~25', '이론 02편은 26장에서 연다.') + table, '\n# [도입] 표지 · 학습목표 · 목차\n\n']
p += [slide(n) + '\n' for n in range(1, 4)]
p.append(f'# [이론] {ROW[59][0]} · {ROW[59][1]}분\n\n')
p += [slide(n) + '\n' for n in range(4, 26)]
p.append(tail(['노트에 없는 말을 더한 곳과 근거: 없음 — 대본의 예와 까닭은 대응 덱 각 장의 화면 · 노트 · 제작 기준을 따른다. 23장 넷째 줄의 「이번 경보에만 부하를 낮추지 말라는 조건」은 문장 안에서 가정으로 밝힌 예다.',
               '뜻을 못 찾은 값: 없음.', '덱과 어긋나 보이는 곳: 없음(장 렌더 대조는 맑은 고딕 렌더 뒤 미확인).', '학습 대기: 없음.']))
(OUTD / FILES[0]).write_text(''.join(p), encoding='utf-8')

# 02편
p = [head(ROW[60][0], '26~45', '이론 03편은 46장에서 연다.'), '\n', f'# [이론] {ROW[60][0]} · {ROW[60][1]}분\n\n']
p += [slide(n) + '\n' for n in range(26, 46)]
p.append(tail(['노트에 없는 말을 더한 곳과 근거: 없음 — 대응 덱 각 장의 제작 기준을 따른다. 40장의 「결과 파일을 검사하는 작은 도구」는 `it/agent-worker/worker/result_check.py`(stdio 창구)다.',
               '뜻을 못 찾은 값: 없음.', '덱과 어긋나 보이는 곳: 없음(장 렌더 대조는 맑은 고딕 렌더 뒤 미확인).', '학습 대기: 없음.']))
(OUTD / FILES[1]).write_text(''.join(p), encoding='utf-8')

# 03편
p = [head(ROW[61][0], '46~78', '62~71장은 실습 다섯의 간지 · 설명 묶음이고, 71장 뒤에 실습을 진행한 다음 72장에서 다시 촬영한다.'), '\n',
     f'# [이론] {ROW[61][0]} · {ROW[61][1]}분\n\n']
p += [slide(n) + '\n' for n in range(46, 62)]
for (a, b), row, title, kind, minutes, text in PRACTICE:
    assert titles[a] == title, (titles[a], title)
    p.append(f'# [실습] {title} · {minutes}분 (대본은 연결 멘트만)\n\n## [SLIDE {a}~{b}] 실습: {title}\n\n> [핵심]\n\n{text.strip()}\n\n'
             f'> [제작: 실습 연결] {a}~{b}장 묶음은 간지의 첫 문장 뒤 설명 장으로 전환한다.\n\n')
    if row == 66:
        p.append('> [제작: 실습 삽입] 71장 설명 뒤 `workspace/강의제작/산출물/통합반/실습/06회차/대본/`의 실습 대본 04~07을 순서대로 진행한다(62행 포털 스킬 실습의 실습 대본은 아직 없다). 실제 확인한 결과만 발화한다.\n\n')
    p.append('---\n\n')
p.append('# [마무리] 복습 · 용어 정리 · 퀴즈\n\n> [제작: 재개] 실습을 마친 뒤 72장부터 다시 촬영한다.\n\n')
p += [slide(n) + '\n' for n in range(72, 79)]
p.append(tail(['노트에 없는 말을 더한 곳과 근거: 없음 — 대응 덱 각 장의 제작 기준을 따른다.',
               '뜻을 못 찾은 값: 없음.', '덱과 어긋나 보이는 곳: 없음(장 렌더 대조는 맑은 고딕 렌더 뒤 미확인).',
               '학습 대기: 72장 15초, 75 · 76 · 77장 각 20초, 총 75초.']))
(OUTD / FILES[2]).write_text(''.join(p), encoding='utf-8')
print('대본 세 편을 썼다')
