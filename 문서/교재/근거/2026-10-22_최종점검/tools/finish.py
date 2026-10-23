"""merge.py 뒤에 돌린다(2회차). 통합하는 세션의 수정과, 같은 덱 장을 쓰는 통합반 3회차 대본의 같은 문장 맞춤.

    python3 finish.py <저장소 루트> <final2 폴더>

1. 통합 수정: 점검자 사이 경계 · 일관성 때문에 통합하는 세션이 넣는 것. 제안본(proposed/)에 바로 적용한다.
2. 같은 문장 맞춤: 점검자 D(실전반 04편)의 변경 가운데 근거에 [통합반03회차 동일: 파일 SLIDE NN]이 붙은 행을
   통합반 3회차 대본에 똑같이 적용해 proposed/통합반_03회차/에 둔다. 실전반에서만 맞는 변경(EXCLUDE)은 옮기지 않는다.
둘 다 바꾸기 전 글이 정확히 한 번 있어야 한다. 기록은 <final2>/통합/변경목록.md.
"""
import re
import sys
from pathlib import Path

ROOT, F2 = Path(sys.argv[1]), Path(sys.argv[2])
P = F2 / "proposed"
rows = []

OWN = [  # (과정, 파일, SLIDE, 구분, 전, 후, 근거)
    ("통합반", "02_이론_스키마설계.md", "머리 `>`", "결함-표기",
     "> 이론에 실습 간지·설명을 포함한다. 제목과 제작 표시는 낭독하지 않는다.",
     "> 제작용: PPTX 22~37장. 이 구간에는 실습 간지·설명이 없다(실습 1~4의 간지·설명은 03_이론_그래프저장과조회의 58~65장). 제목과 제작 표시는 낭독하지 않는다.",
     "낭독하지 않는 제작 표시. 이 파일(22~37장)에는 실습 간지·설명이 없다. 점검자 A가 01편 머리를 같은 꼴로 고쳤고(A 1번) 점검자 B가 같은 문제를 의심으로 남김(B 의심) — 세 파일 머리를 맞춤."),
    ("통합반", "03_이론_그래프저장과조회.md", "머리 `>`", "결함-표기",
     "> 이론에 실습 간지·설명을 포함한다. 제목과 제작 표시는 낭독하지 않는다.",
     "> 제작용: PPTX 38~72장. 실습 1~4의 간지·설명(58~65장)을 포함한다. 제목과 제작 표시는 낭독하지 않는다.",
     "낭독하지 않는 제작 표시. 01 · 02편 머리와 같은 꼴(대응 장 범위)로 맞춤. 내용은 그대로 맞음."),
    ("실전반", "04_이론_작업절차와판단조건.md", "66", "결함-시작끝",
     "지식을 구조로 만들었으니, 아홉 번째 단원에서는 작업 절차와 수행 조건을 연결하겠습니다.",
     "이번 시간에는 지금까지 만든 지식 구조에 작업 절차와 판단 조건을 연결합니다. 먼저 아홉 번째 단원에서는 작업 절차와 수행 조건을 보겠습니다.",
     "04편은 따로 찍는 촬영 구간의 첫 문장이다(66~107). 기준 97-1 「개별 구간은 「이번 시간에는 …」」, 49. 점검자 A(01편 끝 · 목차) · B(02편 처음 · 끝) · C(03편 처음)가 같은 기준으로 고쳤고, 통합반 3회차 02편 16장도 「이번 시간에는 …」으로 연다. 점검자 D는 회차 전체가 함께 정할 일로 보고 의심으로 남겼던 것을 이 기준에 맞춰 넣음(문구는 D의 안)."),
    ("실전반", "04_이론_작업절차와판단조건.md", "105", "결함-표기",
     "승인 직전에 현장 모드가 수동으로 바뀌었습니다.",
     "승인 직전에 운전 모드가 원격 수동으로 바뀌었습니다.",
     "71장은 운전 모드를 원격 자동 · 원격 수동 · 현장 제어로 세웠다(s-071). 「현장 모드가 수동」은 둘 중 무엇인지 흐리다(기준_이론덱 92 같은 대상 같은 말). 정답(2번, 원격 조치 제외)은 그대로. 덱 105장 부제의 같은 말도 함께 고친다(덱 수정 목록). 이전 점검 B9 · 점검자 D 의심."),
]
for course, name, slide, cat, old, new, why in OWN:
    f = P / course / name
    t = f.read_text("utf-8")
    if t.count(old) != 1: sys.exit(f"{course} {name}: 바꾸기 전 글이 {t.count(old)}번 있다: {old[:40]}")
    f.write_text(t.replace(old, new), "utf-8")
    rows.append(("통합-" + str(len(rows) + 1), f"{course}/{name}", slide, cat, old, new, why))

# 같은 문장 맞춤: D → 통합반 3회차
EXCLUDE = {"2"}   # 77장 끝 문단 삭제: 통합반 3회차에서는 01편의 끝 예고라 옮기지 않는다(그쪽은 촬영 구간 끝)
d = (F2 / "D" / "변경목록.md").read_text("utf-8")
d = d[d.find("| 번호"):d.find("## 이전 점검 대조")]
src3 = ROOT / "산출물/통합반/이론/03회차/대본"
out3 = P / "통합반_03회차"; out3.mkdir(parents=True, exist_ok=True)
texts = {f.name: f.read_text("utf-8") for f in src3.glob("*.md")}
for line in d.splitlines():
    if not line.startswith("|") or re.match(r"^\|[\s\-:|]+\|?$", line): continue
    c = [x.strip() for x in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
    if len(c) < 7 or c[0] == "번호" or c[0] in EXCLUDE: continue
    tag = re.search(r"\[통합반03회차 동일: (\S+\.md) SLIDE ([0-9 ·]+)\]", c[6])
    if not tag: continue
    name, old, new = tag.group(1), c[4], c[5]
    if texts[name].count(old) != 1: sys.exit(f"통합반 3회차 {name}: D {c[0]}번 원문이 {texts[name].count(old)}번 있다")
    texts[name] = texts[name].replace(old, new)
    rows.append((f"맞춤-D{c[0]}", f"통합반_03회차/{name}", tag.group(2).strip(), "같은문장맞춤", old, new,
                 f"실전반 2회차 04편 {c[2]}장(점검자 D {c[0]}번, {c[3]})과 같은 덱 장 · 같은 문장 — 두 과정 같은 문장 유지(요청문 인수조건 2, 인계 §2-3)."))
for name, t in texts.items():
    (out3 / name).write_text(t, "utf-8")

(F2 / "통합").mkdir(exist_ok=True)
md = ["# 통합하는 세션의 변경 — 2회차", "", "| 번호 | 파일 | SLIDE | 구분 | 전 | 후 | 근거 |", "|---|---|---|---|---|---|---|"]
md += ["| " + " | ".join(x.replace("|", "\\|") for x in r) + " |" for r in rows]
(F2 / "통합" / "변경목록.md").write_text("\n".join(md) + "\n", "utf-8")
print(f"통합 수정 {len(OWN)}건, 통합반 3회차 같은 문장 맞춤 {len(rows) - len(OWN)}건")
