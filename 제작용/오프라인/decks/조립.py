"""오프라인 이론 덱 조립: 온라인 덱의 장을 오프라인 회차 범위로 다시 묶는다.

python3 제작용/오프라인/decks/조립.py 제작용/오프라인/decks/integrated/off01

폴더의 구성.json(장 순서)과 새장.md(표지 · 학습목표 · 목차 · 간지 · 실습 연결 등 새로 쓴 장)로
<폴더>/<이름>.md를 만든다. 온라인 장은 화면 내용을 그대로 옮기고, 그림 경로만 새 위치에 맞추며,
노트의 [다음]은 다음 장이 온라인에서도 바로 다음 장일 때만 원 구절을 두고, 순서가 바뀐 곳은 구성.json의 next
(새 장은 새장.md 노트의 [다음])에 적은 구절을 쓴다. 노트를 고칠 곳은 구성.json의 note_edits로만 바꾼다.
간지 번호는 새 순서대로 다시 매긴다. 구성.json의 note_end(글머리 목록)는 마지막 장(정답과 판단 기준) 노트의
[다음] 앞에 덧붙인다. 오프라인에는 대본이 없으므로 실습과 다음 회차로 잇는 말은 이 자리에만 둔다.
"""
from pathlib import Path
import json, os, re, sys

ROOT = Path(__file__).resolve().parents[3]
ONLINE = ROOT / '제작용/온라인/decks'
COURSE = {'integrated': '통합반', 'practical': '실전반'}


def blocks(text, head):
    parts = re.split(rf'(?=^{head})', text, flags=re.M)
    return parts[0], parts[1:]


def section(block, name):
    m = re.search(rf'^### {name}\n(.*?)(?=^### |\Z)', block, re.M | re.S)
    return m.group(1).strip('\n') if m else ''


def title_of(block):
    return re.match(r'## (?:SLIDE \d+|NEW \S+) — (.*)', block).group(1).strip()


def next_phrase(i, items):
    # [다음]은 다음 장으로 잇는 한 구절이다(덱.md D-114). 다음 장이 온라인에서도 바로 다음 장이면 원 구절을 두고,
    # 순서가 바뀐 곳은 구성.json의 next(새 장은 새장.md 노트의 [다음])에 적은 구절을 쓴다. 없으면 멈춘다.
    x = items[i]
    if i + 1 == len(items):
        return '[다음] 실습으로'
    if 'next' in x['it']:
        return f"[다음] {x['it']['next']}"
    own = re.search(r'\[다음\][^\n]*$', x['screen'], re.M)
    if 'new' in x['it']:
        if own:
            return own.group(0)
    else:
        nx = items[i + 1].get('src')
        if own and nx and nx == (x['src'][0], x['src'][1] + 1):
            return own.group(0)
    raise SystemExit(f"{i + 1}장 「{x['title']}」: 다음 장 「{items[i + 1]['title']}」으로 잇는 [다음] 구절이 없다 "
                     f"(재사용 장은 구성.json의 next, 새 장은 새장.md 노트 끝의 [다음])")


def main():
    folder = Path(sys.argv[1]).resolve()
    spec = json.loads((folder / '구성.json').read_text('utf8'))
    _, news = blocks((folder / '새장.md').read_text('utf8'), '## NEW ')
    new = {re.match(r'## NEW (\S+)', b).group(1): b for b in news}
    srcs = {}
    items = []
    for it in spec['slides']:
        if 'new' in it:
            b = new.pop(it['new'])
            items.append(dict(title=title_of(b), screen=section(b, '화면 내용'), layout=section(b, '화면 구성'),
                              basis=section(b, '제작 기준'), it=it))
            continue
        src = it['src']
        course, day = src.split('/')
        md = ONLINE / course / day / f"{COURSE[course]}_{day[3:]}일차.md"
        if md not in srcs:
            srcs[md] = {int(re.match(r'## SLIDE (\d+)', b).group(1)): b for b in blocks(md.read_text('utf8'), '## SLIDE ')[1]}
        b = srcs[md][it['n']]
        screen = section(b, '화면 내용')
        def fig(m):
            p = (md.parent / m.group(1)).resolve()
            assert p.is_file(), f'{src} {it["n"]}장 그림 없음: {m.group(1)}'
            return f"- 그림: {os.path.relpath(p, folder)}"
        screen = re.sub(r'^- 그림: (.+)$', fig, screen, flags=re.M)
        for old, rep in it.get('note_edits', []):
            assert screen.count(old) == 1, f'{src} {it["n"]}장 노트 고칠 곳이 한 번이 아님: {old}'
            screen = screen.replace(old, rep)
        edits = '; '.join(f'「{o}」→「{r}」' for o, r in it.get('note_edits', []))
        basis = f"[출처] 온라인 {COURSE[course]} {int(day[3:])}회차 {it['n']}장. 화면은 원 장 그대로" + \
                (f", 노트 고침: {edits}" if edits else ", 노트는 원 장 그대로") + \
                (f", [다음]은 새 순서의 구절 「{it['next']}」" if 'next' in it else '') + '.'
        items.append(dict(title=title_of(b), screen=screen, layout=section(b, '화면 구성'), basis=basis, it=it,
                          src=(src, it['n'])))
    assert not new, f'새장.md에 쓰이지 않은 장: {list(new)}'
    out = [f"# {spec['title']}\n\n{spec['intro']}\n"]
    sec = 0
    for i, x in enumerate(items):
        screen = x['screen']
        if re.search(r'^- 유형: 간지$', screen, re.M) and re.search(r'^- 번호: ', screen, re.M):
            sec += 1
            screen = re.sub(r'^- 번호: .*$', f'- 번호: {sec:02d}', screen, flags=re.M)
        nxt = next_phrase(i, items)
        if i + 1 == len(items):
            assert x['title'] == '정답과 판단 기준', f"마지막 장이 정답과 판단 기준이 아님: {x['title']}"
            assert spec.get('note_end'), '구성.json에 note_end(실습 · 다음 회차 연결)가 없음'
            nxt = ' / '.join([f'· {t}' for t in spec['note_end']] + [nxt])
            x['basis'] += ' 노트 끝에 실습과 다음 회차로 잇는 말(구성.json note_end)을 덧붙였다.'
        if not re.search(r'^- 노트: ', screen, re.M):
            raise SystemExit(f"{i + 1}장 「{x['title']}」 노트 없음")
        screen = re.sub(r'^(- 노트: .*?)(?: / )?\[다음\][^\n]*$', lambda m: f"{m.group(1)} / {nxt}", screen, flags=re.M) \
            if '[다음]' in screen else re.sub(r'^(- 노트: .*)$', lambda m: f"{m.group(1)} / {nxt}", screen, flags=re.M)
        out.append(f"## SLIDE {i + 1:02d} — {x['title']}\n### 화면 내용\n{screen}\n\n### 화면 구성\n{x['layout'] or '해당 유형의 기본 배치를 따른다.'}\n\n### 제작 기준\n{x['basis']}\n")
    dest = folder / spec['md']
    dest.write_text('\n'.join(out), 'utf8')
    print(dest.relative_to(ROOT), len(items), '장')


if __name__ == '__main__':
    main()
