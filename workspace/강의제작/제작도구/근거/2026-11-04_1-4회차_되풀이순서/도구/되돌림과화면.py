"""감독 처리: 도구 사정으로 바뀐 글자 되돌리기, 화면 항목 P2-22, 화면 구성 줄 P3-08 · P3-34."""
import glob
import io
import re
import zipfile
from pathlib import Path

W = Path("작업/2026-11-04_1-4회차-이론-되풀이-순서")


def once(path, old, new):
    b = open(path, "rb").read().decode("utf8")
    if b.count(old) != 1:
        return False
    open(path, "wb").write(b.replace(old, new).encode("utf8"))
    return True


for old, new in [("맨 아래 줄은 값을 어떻게 얻느냐입니다.", "마지막 줄은 값을 어떻게 얻느냐입니다."), ("마지막 줄 ORDER BY는 결과의 순서를 정합니다.", "마지막 줄의 ORDER BY는 결과의 순서를 정합니다.")]:
    hit = [p for p in glob.glob("workspace/강의제작/산출물/통합반/이론/02회차/대본/*.md") if once(p, old, new)]
    print("되돌림", old[:12], len(hit))
    r = W / "고침기록/통합반_02.md"
    r.write_text(r.read_text("utf8").replace(old, new), "utf8", newline="\n")

# P2-22 덱 MD와 PPTX 화면 글자
D2 = "workspace/강의제작/제작도구/온라인/decks/practical/day02/실전반_02일차.md"
A = "여러 행이 함께 맞을 때, 값을 모를 때, 행끼리 부딪칠 때의 처리와 남길 근거를 정한다"
B = "여러 행이 함께 맞을 때, 행끼리 부딪칠 때, 값을 모를 때의 처리와 남길 근거를 정한다"
print("P2-22 MD", once(D2, A, B))
P = Path("workspace/강의제작/산출물/실전반/이론/02회차/실전반_02일차.pptx")
src = P.read_bytes()
out = io.BytesIO()
hits = []
with zipfile.ZipFile(io.BytesIO(src)) as zi, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zo:
    for info in zi.infolist():
        data = zi.read(info.filename)
        if re.fullmatch(r"ppt/slides/slide\d+\.xml", info.filename) and A.encode("utf8") in data:
            hits.append(info.filename)
            data = data.replace(A.encode("utf8"), B.encode("utf8"))
        zo.writestr(info, data)
print("P2-22 PPTX", hits)
if len(hits) != 1:
    raise SystemExit("부제가 슬라이드 XML 한 곳에서 찾아지지 않았다(글자가 나뉘었을 수 있다)")
P.write_bytes(out.getvalue())

# 화면 구성 줄(화면에 나가지 않는 칸)을 노트 [짚을 곳]과 맞춘다
D3 = "workspace/강의제작/제작도구/온라인/decks/practical/day03/실전반_03일차.md"
t = open(D3, "rb").read().decode("utf8")
for n in (11, 47):
    m = re.search(rf"^## SLIDE {n} — .*?(?=^## SLIDE )", t, re.M | re.S)
    b = m.group(0)
    nt = re.search(r"^- 노트: \[짚을 곳\] (.*?)(?: / |\r?$)", b, re.M).group(1).strip()
    lay = re.search(r"^### 화면 구성\r?\n(.*?)\r?$", b, re.M)
    print(n, "화면 구성:", lay.group(1)[:80], "→", nt[:80])
    nb = b[: lay.start(1)] + nt + "." + b[lay.end(1):]
    t = t[: m.start()] + nb + t[m.end():]
open(D3, "wb").write(t.encode("utf8"))
