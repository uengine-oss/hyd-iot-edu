"""언제: 코딩 랩 학생 경로 리허설(코딩랩.md 길 7) 폴더를 준비할 때 — ZIP을 새 폴더에 풀고, 랩 옆 가이드를 「토글 뺀 본문」과 「단계별 정답 토글」로 나눠 둔다.
쓰는 법: python prepare_rehearsal.py <리허설 폴더(없어야 함)> <학생 ZIP> [<학생 ZIP> …]   — 가이드는 각 ZIP 옆 <랩>_guide.html
학생 역은 가이드_본문.txt만 읽고, 막힌 단계에서만 정답_토글/NN.txt를 연다(원본 HTML은 토글이 함께 읽혀 리허설이 무효가 된다).
"""
import hashlib, html, re, shutil, sys
from pathlib import Path
from ai_toy_test import RULE_FILES, unpack


def text_of(fragment):
    fragment = re.sub(r'<(script|style)\b.*?</\1>', '', fragment, flags=re.S)
    fragment = re.sub(r'<br\s*/?>|</(p|li|h\d|tr|pre|div|section)>', '\n', fragment)
    lines = [html.unescape(re.sub(r'<[^>]+>', '', l)).strip() for l in fragment.splitlines()]
    return '\n'.join(l for l in lines if l) + '\n'


def split_guide(guide, out):
    page = guide.read_text(encoding='utf-8')
    toggles = out/'정답_토글'
    toggles.mkdir()
    sections = re.split(r'(?=<section id="s\d+")', page)
    body = []
    for sec in sections:
        m = re.match(r'<section id="s(\d+)"', sec)
        found = re.findall(r'<details\b.*?</details>', sec, flags=re.S)
        if found:
            if not m:
                raise SystemExit(f'{guide}: 단계 절 밖에 정답 토글이 있다 — 나눌 수 없음')
            (toggles/f'{int(m.group(1)):02d}.txt').write_text(''.join(text_of(d) for d in found), encoding='utf-8', newline='\n')
        body.append(re.sub(r'<details\b.*?</details>', '\n[정답 보기 — 막히면 정답_토글/이 단계 번호.txt]\n', sec, flags=re.S))
    (out/'가이드_본문.txt').write_text(text_of(''.join(body)), encoding='utf-8', newline='\n')
    return len(list(toggles.iterdir()))


def check_root(root):
    for parent in [root, *root.parents]:
        hit = [n for n in RULE_FILES if (parent/n).exists()]
        if hit:
            raise SystemExit(f'{parent}에 {hit} — 학생 AI가 함께 읽는다, 다른 곳에 둔다')


def prepare_bundle(z, root):
    guide = z.with_name(z.stem + '_guide.html')
    if not guide.is_file():
        raise SystemExit(f'{guide}가 없다 — 같은 판의 가이드가 필요하다')
    tmp = root/'_unpack'
    if tmp.exists():
        raise SystemExit(f'{tmp}가 이미 있다 — 이전 준비 결과를 먼저 확인한다')
    base = unpack(z, tmp)
    name = Path(base).name if base else z.stem
    lab = root/name
    out = root/f'{name}_가이드'
    if lab.exists() or out.exists():
        raise SystemExit(f'{name}: 같은 이름의 랩이나 가이드가 이미 있다 — 덮어쓰지 않는다')
    shutil.move(str(tmp), str(lab))
    out.mkdir()
    n = split_guide(guide, out)
    print(f'{name}: ZIP {hashlib.sha256(z.read_bytes()).hexdigest()[:12]} · 가이드 {hashlib.sha256(guide.read_bytes()).hexdigest()[:12]} · 토글 {n}단계 → {out}')
    return lab, out


def main():
    if len(sys.argv) < 3:
        raise SystemExit('prepare_rehearsal.py <새 리허설 폴더> <학생 ZIP> [<학생 ZIP> …]')
    root = Path(sys.argv[1]).resolve()
    check_root(root)
    if root.exists():
        raise SystemExit(f'{root}가 이미 있다 — 새 이름을 준다')
    root.mkdir(parents=True)
    for z in map(Path, sys.argv[2:]):
        prepare_bundle(z, root)


if __name__ == '__main__':
    main()
