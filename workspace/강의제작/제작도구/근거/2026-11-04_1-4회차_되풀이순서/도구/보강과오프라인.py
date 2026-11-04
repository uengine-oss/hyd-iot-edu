"""통합 2회차 21장 보강(S-14) · 노트 · off02 커밋본 복원과 노트만 주입."""
import io
import re
import subprocess
import zipfile
from pathlib import Path

from pptx import Presentation

W = Path("작업/2026-11-04_1-4회차-이론-되풀이-순서")
S = Path("workspace/강의제작/산출물/통합반/이론/02회차/대본/01_이론_클래스와인스턴스.md")
ANCHOR = "지금 이 모델이 답하려는 질문에서는 나눌 까닭이 없다는 겁니다."
ADD = " 답해야 할 질문이 늘면 판단이 달라질 수도 있어요. 압력 센서에만 교정 기록과 그 기록을 잇는 관계가 필요해졌다고 해 봅시다. 그때는 갖는 정보와 맺는 관계가 달라졌으니, 같은 기준으로 다시 따져 클래스를 나눌지 정합니다. 반대로 필요한 정보가 그대로라면 클래스를 늘리지 않아요."
t = S.read_bytes().decode("utf8")
assert t.count(ANCHOR) == 1, "보강 자리"
S.write_bytes(t.replace(ANCHOR, ANCHOR + ADD).encode("utf8"))
D = Path("workspace/강의제작/제작도구/온라인/decks/integrated/day02/통합반_02일차.md")
t = D.read_bytes().decode("utf8")
m = re.search(r"^## SLIDE 21 — .*?(?=^## SLIDE )", t, re.M | re.S)
nm = re.search(r"^- 노트:.*?(?= / \[다음\])", m.group(0), re.M)
assert nm, "21장 노트 [다음]"
new = m.group(0)[: nm.end()] + " / · 질문이 늘어 어떤 센서에만 필요한 정보 · 관계가 생기면 같은 기준으로 다시 따진다" + m.group(0)[nm.end():]
D.write_bytes((t[: m.start()] + new + t[m.end():]).encode("utf8"))
r = W / "고침기록/통합반_02.md"
r.write_text(r.read_text("utf8") + f"| 보강 | 01_이론_클래스와인스턴스.md · 21장 | 행이 배정 50분보다 10.3분 짧아짐(S-14) | 실라버스 17행 「언제 새로운 클래스를 정의하고…」, 앞 문장의 「이 모델의 질문 범위에서는」 | {ANCHOR} | {ANCHOR}{ADD} | 새 조건을 더하는 설명(가정임을 문장 안에서 밝힘). 노트 21장에 한 줄 |\n", "utf8", newline="\n")

# off02: 커밋본 PPTX 복원 후 노트만
md = Path("workspace/강의제작/제작도구/오프라인/decks/practical/off02/실전반_오프라인_02회차.md")
pp = Path("workspace/강의제작/산출물/실전반/이론_오프라인/02회차/실전반_오프라인_02회차.pptx")
base = subprocess.run(["git", "show", f"7e85bdd4:{pp.as_posix()}"], capture_output=True, check=True).stdout
pp.write_bytes(base)
notes = {}
for b in re.split(r"(?=^## SLIDE )", md.read_text("utf8"), flags=re.M)[1:]:
    n = int(re.match(r"## SLIDE (\d+)", b).group(1))
    x = re.search(r"^- 노트:\s*(.*)$", b, re.M)
    notes[n] = (x.group(1).strip() if x else "").replace(" / ", "\n")
prs = Presentation(str(pp))
norm = lambda s: re.sub(r"\s+", " ", s.replace("\x0b", "\n")).strip()
changed = {}
for i, sl in enumerate(prs.slides, 1):
    if norm(sl.notes_slide.notes_text_frame.text) != norm(notes[i]):
        sl.notes_slide.notes_text_frame.text = notes[i]
        changed[str(sl.notes_slide.part.partname).lstrip("/")] = i
print("off02 노트 다른 장", sorted(changed.values()))
if changed:
    tmp = io.BytesIO()
    prs.save(tmp)
    with zipfile.ZipFile(tmp) as z:
        new = {n: z.read(n) for n in changed}
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(base)) as zi, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zo:
        for info in zi.infolist():
            zo.writestr(info, new.get(info.filename, zi.read(info.filename)))
    pp.write_bytes(out.getvalue())
