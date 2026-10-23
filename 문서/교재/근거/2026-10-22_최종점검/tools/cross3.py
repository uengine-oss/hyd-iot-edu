"""실전반 2회차 04편의 바뀐 문단을, 같은 덱 장을 쓰는 통합반 3회차 대본의 같은 문단에 옮긴다(줄 단위).

    python3 cross3.py <앞 차수 실전반 04> <이번 실전반 04> <통합반 3회차 기준 폴더> <출력 폴더> [건너뛸 줄 앞머리 …]

바뀌기 전 문단이 통합반 3회차 파일에 정확히 한 번 있을 때만 옮긴다. 실전반에서만 맞는 변경은 「건너뛸 줄 앞머리」로 뺀다.
"""
import difflib
import sys
from pathlib import Path

old_p, new_p, base3, out3 = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
skip = sys.argv[5:]
a, b = old_p.read_text("utf-8").split("\n"), new_p.read_text("utf-8").split("\n")
texts = {f.name: f.read_text("utf-8").split("\n") for f in base3.glob("*.md")}
log = []
for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
    if op == "equal": continue
    blk, new = a[i1:i2], b[j1:j2]
    if not any(x.strip() for x in blk): continue
    head = next(x for x in blk if x.strip())
    if any(s in "\n".join(blk) for s in skip):
        log.append(f"건너뜀(실전반 전용) {head[:50]}"); continue
    hits = [(n, i) for n, ls in texts.items() for i in range(len(ls) - len(blk) + 1) if ls[i:i + len(blk)] == blk]
    if len(hits) == 1:
        n, i = hits[0]; texts[n] = texts[n][:i] + new + texts[n][i + len(blk):]
        log.append(f"옮김 → 통합반 3회차 {n}: {head[:50]}")
    elif len(hits) > 1:
        sys.exit(f"! 같은 문단이 여러 곳: {head[:50]}")
out3.mkdir(parents=True, exist_ok=True)
for n, ls in texts.items():
    (out3 / n).write_text("\n".join(ls), "utf-8")
print("\n".join(log))
print(f"옮김 {sum(x.startswith('옮김') for x in log)}")
