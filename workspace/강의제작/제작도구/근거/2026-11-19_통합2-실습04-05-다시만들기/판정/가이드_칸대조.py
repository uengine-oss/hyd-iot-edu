"""04 안내 문서의 쿼리 칸을 글자로 대조한다(읽기만 한다). 저장소 루트에서:
    PYTHONUTF8=1 .venv314/Scripts/python.exe 작업/2026-11-19_통합2-실습04-05-다시만들기/판정/가이드_칸대조.py
견주는 것 다섯: ① 확정 대본 제작 확인용 「안내 문서 칸」 표 ② 길뚫기/q04_결과.txt에 찍힌 실제로 돌린 쿼리(11-1 · 11-2 · 11-3은 「검토 뒤 바꾼 쿼리」의 새 판)
③ 생성 원고 통합반_관계조회_칸.json ④ 생성된 guide.html · 안내.html의 절마다의 Cypher 복사 블록(차례까지) ⑤ 기본문법_연습.cypher.
그리고 대본 발화가 부르는 「안내 문서 N번(의 첫 · 마지막) 칸」과 조작 칸의 「칸 N-M」이 같은 절 · 같은 차례인지 본다. 어긋나면 종료 코드 1."""
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
W = Path(__file__).resolve().parents[1]
LAB = ROOT/'workspace/강의제작/산출물/통합반/실습/02회차/랩/02일차_실습1_관계조회'
SCRIPT = ROOT/'workspace/강의제작/산출물/통합반/실습/02회차/대본/04_실습_관계조회.md'
bad = []


def script_cells():
    rows = {}
    for line in SCRIPT.read_text(encoding='utf-8').splitlines():
        m = re.match(r'\| (\d+-\d+) \| (.*?) \| .* \| g\d+', line)
        if m:
            rows[m.group(1)] = m.group(2)
    def code(cell):
        return '\n'.join(re.findall(r'`([^`]*)`', cell)).replace('&#124;', '|')
    out = {}
    for k, v in rows.items():
        if k == '5-2':
            out[k] = code(rows['5-1'])
        elif k == '11-2':
            base = code(rows['11-1']).split('\n')
            out[k] = '\n'.join([base[0], re.findall(r'`([^`]*)`', v)[0]] + base[1:])
        else:
            out[k] = code(v)
    return out


def run_cells():
    """q04_결과.txt: `[이름]` 줄 다음부터 `  -> ` 줄 앞까지가 돌린 쿼리. 같은 칸이 여러 번이면 「새 판」이 이긴다."""
    text = (W/'길뚫기/q04_결과.txt').read_text(encoding='utf-8').splitlines()
    found, i = {}, 0
    while i < len(text):
        m = re.fullmatch(r'\[(\d+-\d+)( 새 판|\(같은 쿼리 다시\))?\]', text[i])
        if m:
            j = i + 1
            while not text[j].startswith('  -> '):
                j += 1
            key, new = m.group(1), m.group(2) == ' 새 판'
            if new or key not in found:
                found[key] = ('\n'.join(text[i+1:j]), text[j][5:])
            i = j
        i += 1
    return found


def page_cells(path):
    """[(절 번호, [그 절의 Cypher 블록 글자])] — 절 제목의 두 자리 번호로 읽는다."""
    text = path.read_text(encoding='utf-8')
    out = []
    for number, body in re.findall(r'<section id="s\d+"><h2>(\d+) .*?</h2>(.*?)</section>', text, re.S):
        blocks = re.findall(r'<div class="block cypher"><p class="kind">.*?</p><pre><code>(.*?)</code></pre>', body, re.S)
        out.append((int(number), [html.unescape(x) for x in blocks]))
    return out


script = script_cells()
ran = run_cells()
spec = {c['id']: c['query'] for c in json.loads((ROOT/'workspace/강의제작/제작도구/촬영/neo4j/통합반_관계조회_칸.json').read_text(encoding='utf-8'))['cells']}
ids = list(script)
print(f'대본 표 칸 {len(script)}개: {" ".join(ids)}')
if list(spec) != ids:
    bad.append(f'원고 칸 차례가 대본 표와 다르다: {list(spec)}')
for k in ids:
    if spec.get(k) != script[k]:
        bad.append(f'{k}: 원고 ≠ 대본 표')
    if k not in ran:
        bad.append(f'{k}: q04_결과.txt에 돌린 기록이 없다')
    elif ran[k][0] != script[k]:
        bad.append(f'{k}: 돌린 쿼리 ≠ 대본 표\n--- 돌린 것\n{ran[k][0]}\n--- 대본\n{script[k]}')
for name in ('guide.html', '안내.html'):
    cells = page_cells(LAB/name)
    flat = {}
    for number, blocks in cells:
        for order, text in enumerate(blocks, 1):
            flat[f'{number}-{order}'] = text
    if list(flat) != ids:
        bad.append(f'{name}: 절-차례 {list(flat)} ≠ 대본 표 {ids}')
    for k in ids:
        if flat.get(k) != script[k]:
            bad.append(f'{name} {k}: 블록 글자 ≠ 대본 표')
    print(f'{name}: 절 {len(cells)}개, 절마다 칸 수 ' + ' · '.join(f'{n:02d}절 {len(b)}' for n, b in cells))
if (LAB/'guide.html').read_bytes() != (LAB/'안내.html').read_bytes():
    bad.append('guide.html과 안내.html의 바이트가 다르다')
cy = (LAB/'기본문법_연습.cypher').read_text(encoding='utf-8')
parts = re.split(r'\n// (\d+-\d+)\n', cy)
in_file = {parts[i]: parts[i+1].strip('\n') for i in range(1, len(parts), 2)}
if list(in_file) != ids or any(in_file[k] != script[k] for k in ids):
    bad.append('기본문법_연습.cypher의 칸이 대본 표와 다르다')

# 대본이 소리 내 부르는 절 번호 ↔ 조작 칸의 「칸 N-M」
spoken = []
for line in SCRIPT.read_text(encoding='utf-8').splitlines():
    m = re.match(r'\| (g\d+) \| (.*?) \| (.*) \|$', line)
    if not m:
        continue
    cue, say, act = m.groups()
    cell = re.search(r'칸 (\d+-\d+)(?: 아래)? ?\[복사\]', act)
    if not cell:
        continue
    said = re.search(r'안내 문서(?:에서)? (\d+)번(?:의)? ?(첫 칸|마지막 칸|칸)?', say) or re.search(r'(?<![\d-])(\d+)번의 (첫 칸|마지막 칸)', say)
    spoken.append((cue, cell.group(1), (said.group(1), said.group(2) or '') if said else None))
last = {}
for k in ids:
    last[k.split('-')[0]] = k
for cue, cell, said in spoken:
    if said is None:
        continue            # 「다음 칸」 · 말없이 복사 — 차례는 위 절-차례 대조가 본다
    sec, which = said
    want = {'첫 칸': f'{sec}-1', '마지막 칸': last.get(sec), '칸': f'{sec}-1', '': f'{sec}-1'}[which]
    if which == '칸' and last.get(sec) != f'{sec}-1':
        bad.append(f'{cue}: 「{sec}번 칸」이라고만 불렀는데 그 절에 칸이 여럿이다')
    if want != cell:
        bad.append(f'{cue}: 말은 {sec}번 {which} → {want}, 조작 칸은 {cell}')
print('대본의 복사 조작 ' + str(len(spoken)) + '번(칸 차례): ' + ' '.join(c for _, c, _ in spoken))
if [c for _, c, _ in spoken] != ids:
    bad.append(f'대본이 복사하는 칸 차례 ≠ 표: {[c for _, c, _ in spoken]}')
print('말로 절 번호를 부른 큐: ' + ', '.join(f'{cue}=「{s[0]}번 {s[1]}」→{cell}' for cue, cell, s in spoken if s))
print('실행 결과(q04_결과.txt):')
for k in ids:
    print(f'  {k}: {ran[k][1][:150] if k in ran else "-"}')
print('어긋남 ' + str(len(bad)) + '건')
for b in bad:
    print('  ' + b)
sys.exit(1 if bad else 0)
