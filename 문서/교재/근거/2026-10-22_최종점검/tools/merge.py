"""점검자 출력을 모아 제안본을 만든다. 저장소는 읽기만 한다.

    python3 merge.py <저장소 루트> <결과 폴더> <회차 01 · 02> [기준 폴더(앞 차수 제안본, 과정별 하위 폴더)]

- 통합반: 점검자 사본을 그대로 쓴다.
- 실전반: 점검자의 실전반 사본(없으면 실전반 원본)을 바탕으로, 통합반에서 바뀐 문단을 줄 단위로 옮긴다.
  대본은 문단 하나가 한 줄이다. 통합반 원본 → 제안본의 줄 차이(바꿈 · 지움 · 넣음)마다, 바뀌기 전 줄 묶음이
  실전반 바탕에 정확히 한 번 있으면 같은 변경을 적용한다. 없으면(과정마다 다른 문장) 건너뛰고, 여러 번 있으면 멈춘다.
  실전반에만 고친 문장(점검자 사본)은 통합반 쪽이 그 줄을 바꾸지 않았으면 그대로 남는다. 둘 다 같은 줄을 다르게 바꿨으면 알린다.
- 같은 회차의 다른 실전반 파일에도 같은 줄이 있으면(예: 통합반 03 퀴즈 = 실전반 04 퀴즈) 그 파일에도 옮긴다.
결과: <폴더>/proposed/<과정>/<파일>, 옮긴 · 건너뛴 기록을 출력한다.
"""
import difflib
import sys
from pathlib import Path

ROOT, F2, NN = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
SRC = ({c: Path(sys.argv[4]) / c for c in ("통합반", "실전반")} if len(sys.argv) > 4   # 다음 차수: 앞 차수 제안본을 기준으로
       else {c: ROOT / f"산출물/{c}/이론/{NN}회차/대본" for c in ("통합반", "실전반")})
AGENTS = {"02": {("통합반", "01"): "A", ("통합반", "02"): "B", ("통합반", "03"): "C",
                  ("실전반", "01"): "A", ("실전반", "03"): "C", ("실전반", "04"): "D"},
          "01": {("통합반", "01"): "E", ("통합반", "02"): "F", ("통합반", "03"): "G"}}
AGENT = AGENTS[NN]


def agent_copy(course, name):
    k = AGENT.get((course, name[:2]))
    p = F2 / k / course / name if k else None
    return p.read_text("utf-8") if p and p.exists() else None


def find_block(lines, block):
    n = len(block)
    return [i for i in range(len(lines) - n + 1) if lines[i:i + n] == block]


out = F2 / "proposed"
for c in ("통합반", "실전반"): (out / c).mkdir(parents=True, exist_ok=True)
log = []
patches = []   # (통합반 파일, 원본 줄 묶음, 제안 줄 묶음, 앞 줄)
for f in sorted(SRC["통합반"].glob("*.md")):
    new = agent_copy("통합반", f.name)
    if new is None: sys.exit(f"통합반 {f.name}: 점검자 사본이 없다")
    (out / "통합반" / f.name).write_text(new, "utf-8")
    a, b = f.read_text("utf-8").split("\n"), new.split("\n")
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == "equal": continue
        old_blk, new_blk = a[i1:i2], b[j1:j2]
        if not any(x.strip() for x in old_blk):   # 넣기(또는 빈 줄만 바뀜): 앞의 내용 있는 줄을 닻으로 쓴다
            k = i1 - 1
            while k >= 0 and not a[k].strip(): k -= 1
            anchor = a[k:i1] if k >= 0 else None
            patches.append((f.name, old_blk, new_blk, anchor))
        else:
            patches.append((f.name, old_blk, new_blk, None))

bases = {}
for f in sorted(SRC["실전반"].glob("*.md")):
    bases[f.name] = (agent_copy("실전반", f.name) or f.read_text("utf-8")).split("\n")
orig_p = {f.name: f.read_text("utf-8").split("\n") for f in SRC["실전반"].glob("*.md")}

for tname, old_blk, new_blk, anchor in patches:
    done = False
    for pname, lines in bases.items():
        if anchor is None:
            hits = find_block(lines, old_blk)
            if len(hits) > 1:
                sys.exit(f"! {tname} → 실전반 {pname}: 같은 줄 묶음이 {len(hits)}번 있다 — 손으로 정한다: {old_blk[0][:40]}")
            if len(hits) == 1:
                i = hits[0]; bases[pname] = lines[:i] + new_blk + lines[i + len(old_blk):]
                log.append(f"옮김 {tname} → 실전반 {pname}: {next((x for x in old_blk if x.strip()), '')[:50]}"); done = True
        else:
            hits = find_block(lines, anchor)
            if len(hits) == 1:
                i = hits[0] + len(anchor)
                if lines[i:i + len(old_blk)] == old_blk:
                    bases[pname] = lines[:i] + new_blk + lines[i + len(old_blk):]
                    log.append(f"옮김(넣기) {tname} → 실전반 {pname}: {next((x for x in new_blk if x.strip()), '')[:50]}"); done = True
    if not done:
        # 실전반 원본에는 있었는데 바탕(점검자 사본)에서 이미 바뀐 줄인가 = 두 과정이 같은 줄을 따로 고침
        clash = [p for p, ol in orig_p.items() if any(x.strip() for x in old_blk) and find_block(ol, old_blk)]
        if clash: log.append(f"! 충돌 {tname}: 실전반 {clash} 점검자가 같은 줄을 따로 고쳤다 — 손으로 맞춘다: {next((x for x in old_blk if x.strip()), '')[:50]}")
        else: log.append(f"건너뜀(실전반에 없는 문장) {tname}: {next((x for x in old_blk + new_blk if x.strip()), '')[:50]}")

for pname, lines in bases.items():
    (out / "실전반" / pname).write_text("\n".join(lines), "utf-8")
print("\n".join(log))
print(f"합계: 통합반 변경 묶음 {len(patches)}개 · 옮김 {sum(x.startswith('옮김') for x in log)} · 건너뜀 {sum(x.startswith('건너뜀') for x in log)} · 충돌 {sum(x.startswith('!') for x in log)}")
