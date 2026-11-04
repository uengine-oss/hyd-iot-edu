"""강조 안(한 줄 = 표시 하나)을 강조표시.py 설정 json으로 바꾼다. 좌표는 장 그림의 글줄 · 도형에서 계산한다(장글.py).
    python3 강조만들기.py <안.txt> <쉼목록.json> <출력 강조.json>
안 줄: 장|문|낱말|끝|모양|목표|대상     (# 뒤는 주석, 빈 줄 무시)
  문 · 끝 = 그 장 구획의 문장 번호(쉼목록의 문장 목록, 0부터). 끝이 비면 그 장 말이 끝날 때 지운다. 낱말이 비면 문장의 첫 어절.
  목표: 찾:글[@n]  — 글줄에서 찾은 낱말 상자(n번째)      칸:S3[,S4]  — PPTX 도형 상자(여럿이면 합친 상자)
        줄:L5[,L6] — 글줄 상자                           상:x1,y1,x2,y2 / 점:x,y,rx,ry / 화:x1,y1,x2,y2 — 직접 좌표
  모양별 여백: 띠 = 글 상자 좌우 8 · 위아래 6(「띠-」는 좌우 6 · 위아래 2 — 줄 간격이 좁은 곳), 밑줄 = 글 상자 그대로(도구가 7px 밑에 긋는다), 네모 = 상자 바깥 8, 동그라미 = 상자를 감싸는 타원(+16)."""
import json, sys, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import 장글 as G

plan, lst, out = Path(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text()), Path(sys.argv[3])
deck = None; marks = []
sents = {}
for o in lst: sents[(o["대본"][:2] + "_" + o["대본"].split("/")[1][:2], int(o["장"].split("~")[0]))] = o["문장"]
part = None
for ln, line in enumerate(plan.read_text(encoding="utf-8").splitlines(), 1):
    line = line.split("#", 1)[0].rstrip()
    if not line.strip(): continue
    if line.startswith("덱 "): deck = line.split()[1]; part = deck.split("_")[1][:2] + "_" + line.split()[2]; continue
    f = [x.strip() for x in line.split("|")]
    if len(f) != 7: sys.exit(f"{plan}:{ln}: 칸이 일곱이 아님")
    n, i, word, j, shape, tgt, what = int(f[0]), int(f[1]), f[2], f[3], f[4], f[5], f[6]
    S = sents.get((part, n)) or sys.exit(f"{plan}:{ln}: {part} {n}장의 문장 목록이 없음")
    m = {"장": n, "문장": S[i], "낱말": word or S[i].split()[0]}
    if word and word not in S[i]: sys.exit(f"{plan}:{ln}: 낱말 「{word}」이 문장 「{S[i]}」에 없음")
    if j:
        if int(j) <= i: sys.exit(f"{plan}:{ln}: 끝 문장이 시작 문장보다 앞")
        m["끝문장"] = S[int(j)]
    tight = shape == "띠-"
    if tight: shape = "띠"
    m["모양"] = shape
    kind, val = tgt.split(":", 1)
    if kind == "찾":
        ph, nth = (val.rsplit("@", 1) + ["1"])[:2] if "@" in val else (val, "1")
        box, cnt = G.find(deck, n, ph, int(nth))
    elif kind == "칸":
        ss = G.shapes(deck, n); bs = [ss[int(x.strip()[1:])]["상자"] for x in val.split(",")]
        box = [min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs)]
    elif kind == "줄":
        ls = G.lines(deck, n); bs = [ls[int(x.strip()[1:])]["상자"] for x in val.split(",")]
        box = [min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs)]
    elif kind in ("상", "점", "화"):
        box = [int(v) for v in val.split(",")]
    else: sys.exit(f"{plan}:{ln}: 모르는 목표 {kind}")
    x1, y1, x2, y2 = box[:4] if kind != "점" else (0, 0, 0, 0)
    if shape == "띠": m["상자"] = box if kind == "상" else ([x1 - 6, y1 - 2, x2 + 6, y2 + 2] if tight else [x1 - 8, y1 - 6, x2 + 8, y2 + 6])
    elif shape == "밑줄": m["상자"] = box
    elif shape == "네모": m["상자"] = [x1 - 8, y1 - 8, x2 + 8, y2 + 8] if kind != "상" else box
    elif shape == "동그라미":
        if kind == "점": m["중심"], m["반지름"] = box[:2], box[2:]
        else: m["중심"], m["반지름"] = [round((x1 + x2) / 2), round((y1 + y2) / 2)], [round((x2 - x1) / 2 * 1.12 + 16), round((y2 - y1) / 2 * 1.12 + 16)]
    elif shape == "화살표":
        if kind != "화": sys.exit(f"{plan}:{ln}: 화살표는 화: 좌표로")
        m["시작"], m["끝"] = box[:2], box[2:]
    else: sys.exit(f"{plan}:{ln}: 모르는 모양 {shape}")
    m["대상"] = what
    marks.append(m)
# 같은 때 셋 이상 겹침 검사(문장 번호 기준)
by = {}
for k, m in enumerate(marks):
    S = sents[(part, m["장"])]; a = S.index(m["문장"]); b = S.index(m["끝문장"]) if "끝문장" in m else len(S)
    by.setdefault(m["장"], []).append((a, b, k))
errs = []
for n, iv in by.items():
    for a, b, k in iv:
        at0 = marks[k]["문장"].find(marks[k]["낱말"]) == 0   # 문장 첫머리에서 그리면, 그 문장에서 지워지는 표시가 사라지는 0.25초 동안 함께 보인다
        on = [x for x in iv if x[0] <= a < x[1] or (at0 and x[1] == a)]
        if len(on) > 2: errs.append(f"{n}장 문장 {a}(표시 {k + 1}「{marks[k]['낱말']}」)에서 표시 {len(on)}개가 함께 보임 — 문장 첫머리에서 그리면 지워지는 표시와 겹친다, 낱말을 뒤로")
if errs: sys.exit("\n".join(errs))
out.write_text(json.dumps({"표시": marks}, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{out.name}: 표시 {len(marks)}개 · 장 {len(by)}개")
