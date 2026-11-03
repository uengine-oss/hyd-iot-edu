"""실전반 온라인 1회차 덱 MD를 통합반 1회차 원고에서 조립한다(덱.md D-125).

python workspace/강의제작/제작도구/온라인/decks/practical/day01/조립.py

1회차는 두 과정 공통이다 — 표지 「과정」 칸의 과정 이름만 바꾸고, 화면 · 발표자 노트는 통합반 원고 그대로 옮긴다(손으로 고치지 않는다).
그림 · 라벨은 통합반 1회차 figures/를 상대 경로로 가리킨다(사본을 두지 않는다).
확정 덱이라 PPTX는 다시 빌드하지 않는다(덱.md D요-23) — 노트가 바뀌면 커밋본 PPTX에 노트 칸만 주입한다.
"""
from pathlib import Path
import os, re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[6]
SRC = ROOT / 'workspace/강의제작/제작도구/온라인/decks/integrated/day01/통합반_01일차.md'
OUT = HERE / '실전반_01일차.md'
HEADER = '<!-- 조립.py 생성: 통합반 1회차 원고(화면 · 노트)를 그대로 옮긴 공통 1회차. 직접 고치지 않고 통합반 원고를 고친 뒤 다시 조립한다. -->\n'


def main() -> None:
    text = SRC.read_text('utf8')
    cover = '- 과정: 통합반 1회차 · '
    if text.count(cover) != 1:
        raise SystemExit(f'{SRC}: 표지 「{cover}」가 한 번이 아니다')
    text = text.replace(cover, '- 과정: 실전반 1회차 · ')
    blocks = re.split(r'(?=^## SLIDE )', text, flags=re.M)[1:]
    for n, b in enumerate(blocks, 1):
        if not b.startswith(f'## SLIDE {n:02d} — '):
            raise SystemExit(f'{SRC}: {n}장 머리가 「## SLIDE {n:02d} — 」가 아니다')
        for rel in re.findall(r'^- (?:그림|라벨(?=: .+\.json$)): (.+)$', b, re.M):
            if not (SRC.parent / rel.strip()).is_file():
                raise SystemExit(f'{SRC}: {n}장 그림 없음 {SRC.parent / rel.strip()}')
    text, figs = re.subn(r'^- (그림|라벨(?=: .+\.json$)): (.+)$',
                         lambda m: f"- {m.group(1)}: {Path(os.path.relpath(SRC.parent / m.group(2).strip(), HERE)).as_posix()}",
                         text, flags=re.M)
    OUT.write_text(HEADER + text, encoding='utf8', newline='\n')
    print(f'{len(blocks)}장 조립: 화면 · 노트 = 통합반 원고, 그림 · 라벨 {figs}곳은 통합반 1회차 figures/를 가리킨다')


if __name__ == '__main__':
    main()
