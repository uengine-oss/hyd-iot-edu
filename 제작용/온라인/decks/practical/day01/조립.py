"""실전반 온라인 1회차 덱 MD를 통합반 1회차 원고에서 조립한다(덱.md D-125).

python 제작용/온라인/decks/practical/day01/조립.py

1회차는 두 과정 공통이다 — 표지 「과정」 칸의 과정 이름만 바꾸고, 화면 · 발표자 노트는 통합반 원고 그대로 옮긴다(손으로 고치지 않는다).
덱이 쓰는 그림은 이 폴더로 복사하고 해시를 맞춘다. 장마다 화면 해시를 단원대응.json에 남긴다.
확정 덱이라 PPTX는 다시 빌드하지 않는다(덱.md D요-23) — 노트가 바뀌면 커밋본 PPTX에 노트 칸만 주입한다.
"""
from pathlib import Path
import hashlib, json, re, shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
SRC = ROOT / '제작용/온라인/decks/integrated/day01/통합반_01일차.md'
OUT = HERE / '실전반_01일차.md'
HEADER = '<!-- 조립.py 생성: 통합반 1회차 원고(화면 · 노트)를 그대로 옮긴 공통 1회차. 직접 고치지 않고 통합반 원고를 고친 뒤 다시 조립한다. -->\n'


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def screen(block: str) -> str:
    s = block.split('### 화면 내용', 1)[1].split('### 화면 구성', 1)[0]
    return re.sub(r'^- 노트:.*\n?', '', s, flags=re.M).strip()


def main() -> None:
    text = SRC.read_text('utf8')
    cover = '- 과정: 통합반 1회차 · '
    if text.count(cover) != 1:
        raise SystemExit(f'{SRC}: 표지 「{cover}」가 한 번이 아니다')
    text = text.replace(cover, '- 과정: 실전반 1회차 · ')
    blocks = re.split(r'(?=^## SLIDE )', text, flags=re.M)[1:]
    slides = []
    for n, b in enumerate(blocks, 1):
        if not b.startswith(f'## SLIDE {n:02d} — '):
            raise SystemExit(f'{SRC}: {n}장 머리가 「## SLIDE {n:02d} — 」가 아니다')
        assets = []
        for rel in re.findall(r'^- 그림: (.+)$', b, re.M):
            src, dst = SRC.parent / rel.strip(), HERE / rel.strip()
            if not src.exists():
                raise SystemExit(f'{SRC}: {n}장 그림 없음 {src}')
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            if sha(src.read_bytes()) != sha(dst.read_bytes()):
                raise SystemExit(f'{dst}: 복사본 해시가 다르다')
            assets.append({'path': rel.strip(), 'sha256': sha(dst.read_bytes())})
        slides.append({'slide': n, 'title': b.splitlines()[0].split(' — ', 1)[1],
                       'screen_sha256': sha(screen(b).encode()), 'assets': assets})
    OUT.write_text(HEADER + text, encoding='utf8', newline='\n')
    (HERE / '단원대응.json').write_text(json.dumps(
        {'source': SRC.relative_to(ROOT).as_posix(), 'source_sha256': sha(SRC.read_bytes()), 'slides': slides},
        ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print(f'{len(slides)}장 조립: 화면 · 노트 = 통합반 원고, 그림 {sum(len(s["assets"]) for s in slides)}개 해시 일치')


if __name__ == '__main__':
    main()
