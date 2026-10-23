"""3 · 4회차 점검자 사본을 모아 제안본을 만든다. 저장소는 읽기만 한다.

    python3 merge4.py <저장소 루트> <점검 폴더(A~G가 있는 곳)> <출력 폴더> [건너뛸 문자열 JSON]

- 한 파일을 두 점검자가 장 범위로 나눠 맡은 곳(실전반 4회차 01 = D 1~28 + E 29~59, 03 = F 82~101 + G 102~132)은
  원본 대비 각자의 변경을 모은다. 변경이 맡은 범위 밖이거나 서로 겹치면 멈춘다.
- 통합반 3 · 4회차의 바뀐 문단을 실전반 3회차에, 실전반 4회차의 바뀐 문단을 통합반 5 · 6회차에 줄 단위로 옮긴다.
  바뀌기 전 줄 묶음이 대상 파일에 정확히 한 번 있으면 같은 변경을 적용한다(넣기는 앞의 내용 있는 줄을 닻으로).
  건너뛸 문자열 JSON {"to_실전반3": [...], "to_통합반56": [...]}: 바뀌기 전 · 후 묶음에 그 문자열이 있으면 옮기지 않는다(한쪽 과정 전용 변경).
"""
import difflib
import json
import re
import sys
from pathlib import Path

ROOT, REV, OUT = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
SKIP = json.loads(Path(sys.argv[4]).read_text("utf-8")) if len(sys.argv) > 4 else {}
P = ROOT / "산출물"
HEAD = re.compile(r"^## \[SLIDE (\d+)")


def src(course, nn):
    return {f.name: f.read_text("utf-8").split("\n") for f in sorted((P / course / "이론" / f"{nn}회차" / "대본").glob("*.md"))}


def slide_of(lines):
    cur, out = 0, []
    for ln in lines:
        m = HEAD.match(ln)
        if m: cur = int(m.group(1))
        out.append(cur)
    return out


def ops(a, b):
    return [o for o in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes() if o[0] != "equal"]


def combine(name, orig, parts):
    """parts: [(점검자, 사본 줄, (첫 장, 끝 장))] → 원본에 각자의 범위 안 변경만 모아 적용"""
    sl = slide_of(orig)
    edits = []
    for who, copy, (lo, hi) in parts:
        for op, i1, i2, j1, j2 in ops(orig, copy):
            s = sl[i1 - 1] if i1 == i2 else sl[i1]
            s2 = sl[max(i1, i2 - 1)]
            if not (lo <= s <= hi and lo <= s2 <= hi):
                sys.exit(f"! {name}: 점검자 {who}가 맡은 범위({lo}~{hi}) 밖 SLIDE {s}을 바꿨다: {(orig[i1] if i1 < len(orig) else '')[:50]}")
            edits.append((i1, i2, copy[j1:j2], who))
    edits.sort()
    for x, y in zip(edits, edits[1:]):
        if y[0] < x[1]: sys.exit(f"! {name}: {x[3]} · {y[3]} 변경이 겹친다")
    out = list(orig)
    for i1, i2, new, _ in reversed(edits): out[i1:i2] = new
    return out


def patches(orig_files, new_files):
    res = []
    for name, a in orig_files.items():
        b = new_files[name]
        for op, i1, i2, j1, j2 in ops(a, b):
            old_blk, new_blk = a[i1:i2], b[j1:j2]
            anchor = None
            if not any(x.strip() for x in old_blk):
                k = i1 - 1
                while k >= 0 and not a[k].strip(): k -= 1
                anchor = a[k:i1] if k >= 0 else None
            res.append((name, old_blk, new_blk, anchor))
    return res


def find(lines, blk):
    n = len(blk)
    return [i for i in range(len(lines) - n + 1) if lines[i:i + n] == blk]


def propagate(label, pats, targets, target_orig, skip):
    """옮길 자리를 모두 바탕(옮기기 전) 파일에서 먼저 찾은 뒤, 파일마다 뒤에서부터 한꺼번에 적용한다(문단 순서 바꿈도 그대로 옮겨진다)."""
    log, plan = [], {}
    for tname, old_blk, new_blk, anchor in pats:
        head = next((x for x in old_blk + new_blk if x.strip()), "")[:50]
        if any(s in "\n".join(old_blk + new_blk) for s in skip):
            log.append(f"건너뜀(한쪽 전용) {tname}: {head}"); continue
        done = False
        for pname, lines in targets.items():
            if anchor is None:
                hits = find(lines, old_blk)
                if len(hits) > 1: sys.exit(f"! {tname} → {label} {pname}: 같은 줄 묶음이 {len(hits)}번: {head}")
                if hits:
                    plan.setdefault(pname, []).append((hits[0], hits[0] + len(old_blk), new_blk, head))
                    log.append(f"옮김 {tname} → {label} {pname}: {head}"); done = True
            else:
                hits = find(lines, anchor)
                if len(hits) == 1:
                    i = hits[0] + len(anchor)
                    if lines[i:i + len(old_blk)] == old_blk:
                        plan.setdefault(pname, []).append((i, i + len(old_blk), new_blk, head))
                        log.append(f"옮김(넣기) {tname} → {label} {pname}: {head}"); done = True
        if not done:
            clash = [p for p, ol in target_orig.items() if any(x.strip() for x in old_blk) and find(ol, old_blk)]
            log.append(f"! 충돌 {tname} → {label} {clash}: 대상 점검자가 같은 줄을 따로 고쳤다: {head}" if clash
                       else f"건너뜀(대상에 없는 문장) {tname}: {head}")
    for pname, eds in plan.items():
        eds.sort(key=lambda x: (x[0], x[1]))
        for x, y in zip(eds, eds[1:]):
            if y[0] < x[1]: sys.exit(f"! {label} {pname}: 옮길 변경이 겹친다: {x[3]} / {y[3]}")
        lines = list(targets[pname])
        for i1, i2, new, _ in reversed(eds): lines[i1:i2] = new
        targets[pname] = lines
    return log


def copy_of(who, course, name):
    return (REV / who / course / name).read_text("utf-8").split("\n")


def save(course, nn, files):
    d = OUT / course / f"{nn}회차"; d.mkdir(parents=True, exist_ok=True)
    for n, ls in files.items(): (d / n).write_text("\n".join(ls), "utf-8")


log = []
# 통합반 3회차 = A
t3o = src("통합반", "03")
t3 = {n: copy_of("A", "통합반", n) for n in t3o}
# 실전반 2회차 04편과의 「공유 줄 고정」 검사는 뺐다(2026-10-23 실전반 2회차 재편 — 이제 공유가 아니다)
# 통합반 4회차 = B(01) · C(02)
t4o = src("통합반", "04")
t4 = {n: copy_of("B" if n.startswith("01") else "C", "통합반", n) for n in t4o}
# 실전반 3회차 = A(01) · B(02) · C(03)의 실전반 전용 변경 + 통합반 3 · 4회차 변경 옮기기
s3o = src("실전반", "03")
s3 = {n: copy_of({"01": "A", "02": "B", "03": "C"}[n[:2]], "실전반", n) for n in s3o}
pats = patches(t3o, t3) + patches(t4o, t4)
log += propagate("실전반 3회차", pats, s3, s3o, SKIP.get("to_실전반3", []))
# 실전반 4회차 = D+E(01) · F(02) · F+G(03)
s4o = src("실전반", "04")
s4 = {}
for n, a in s4o.items():
    if n.startswith("01"): s4[n] = combine(n, a, [("D", copy_of("D", "실전반", n), (1, 28)), ("E", copy_of("E", "실전반", n), (29, 59))])
    elif n.startswith("02"): s4[n] = combine(n, a, [("F", copy_of("F", "실전반", n), (60, 81))])
    else: s4[n] = combine(n, a, [("F", copy_of("F", "실전반", n), (82, 101)), ("G", copy_of("G", "실전반", n), (102, 132))])
# 통합반 5 · 6회차 = 실전반 4회차 변경 옮기기
t5o, t6o = src("통합반", "05"), src("통합반", "06")
t56o = {f"05/{n}": ls for n, ls in t5o.items()} | {f"06/{n}": ls for n, ls in t6o.items()}
t56 = {k: list(v) for k, v in t56o.items()}
log += propagate("통합반 5·6회차", patches(s4o, s4), t56, t56o, SKIP.get("to_통합반56", []))

save("통합반", "03", t3); save("통합반", "04", t4); save("실전반", "03", s3); save("실전반", "04", s4)
save("통합반", "05", {k[3:]: v for k, v in t56.items() if k.startswith("05/")})
save("통합반", "06", {k[3:]: v for k, v in t56.items() if k.startswith("06/")})
print("\n".join(log))
print(f"합계: 옮김 {sum(x.startswith('옮김') for x in log)} · 건너뜀 {sum(x.startswith('건너뜀') for x in log)} · 충돌 {sum(x.startswith('!') for x in log)}")
