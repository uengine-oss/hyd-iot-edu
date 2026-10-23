"""바뀐 덱 장의 전 · 후 그림을 줄여 한 폴더에 모으고, 보고서에 넣을 HTML · MD 조각을 만든다.

    python3 deck_pairs.py <전 렌더 폴더> <후 렌더 폴더> <장 목록 "5,7,8"> <그림 출력 폴더> <조각 출력 접두어> [장별 설명 tsv: 장<TAB>설명]

그림 출력 폴더 이름이 보고서 파일 옆의 상대 경로가 된다(HTML · MD가 같은 폴더에 있어야 한다).
"""
import html
import sys
from pathlib import Path
from PIL import Image

before, after, nums, outdir, pref = Path(sys.argv[1]), Path(sys.argv[2]), [int(x) for x in sys.argv[3].split(",") if x], Path(sys.argv[4]), Path(sys.argv[5])
notes = {}
if len(sys.argv) > 6:
    for ln in Path(sys.argv[6]).read_text("utf-8").splitlines():
        if "\t" in ln: k, v = ln.split("\t", 1); notes[int(k)] = v
outdir.mkdir(parents=True, exist_ok=True)


def find(d, n):
    for p in d.glob("*.png"):
        tail = p.stem.rsplit("-", 1)[-1]
        if tail.isdigit() and int(tail) == n: return p
    raise SystemExit(f"{d}: {n}장 그림 없음")


H, M = [], []
for n in nums:
    pair = []
    for tag, d in (("전", before), ("후", after)):
        im = Image.open(find(d, n)).convert("RGB"); im.thumbnail((1000, 1000))
        name = f"s{n:02d}_{tag}.jpg"; im.save(outdir / name, quality=82); pair.append(name)
    rel = outdir.name
    note = notes.get(n, "")
    H.append(f"<section><h3>{n}장 <span class=muted>{html.escape(note)}</span></h3><div class=pair>"
             f"<div><div class=lab>전</div><img src='{rel}/{pair[0]}' style='width:100%;border:1px solid var(--line)'></div>"
             f"<div><div class=lab>후</div><img src='{rel}/{pair[1]}' style='width:100%;border:1px solid var(--line)'></div></div></section>")
    M += [f"### {n}장" + (f" — {note}" if note else ""), "", f"| 전 | 후 |", "|---|---|", f"| ![전]({rel}/{pair[0]}) | ![후]({rel}/{pair[1]}) |", ""]
Path(f"{pref}.html").write_text("\n".join(H), "utf-8")
Path(f"{pref}.md").write_text("\n".join(M), "utf-8")
print(len(nums), "장", outdir)
