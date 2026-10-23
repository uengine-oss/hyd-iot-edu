"""변경목록에서 한쪽 과정 전용 표시가 붙은 행의 「후」(없으면 「전」) 글을 모아 merge4.py의 건너뛸 문자열 JSON을 만든다.
    python3 skips.py <점검 폴더> <출력 json> <점검자 …>
"""
import json, re, sys
from pathlib import Path
F, OUT, WHO = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3:]
res = {"to_실전반3": [], "to_통합반56": []}
for w in WHO:
    p = F / w / "변경목록.md"
    for line in p.read_text("utf-8").splitlines():
        if not line.startswith("|") or re.match(r"^\|[\s\-:|]+\|?$", line): continue
        c = [x.strip() for x in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
        if len(c) < 7 or c[0] in ("번호", "#"): continue
        why = " ".join(c[6:])
        key = "to_실전반3" if "[통합반 전용]" in why else "to_통합반56" if "[실전반 전용]" in why else None
        if not key: continue
        txt = (c[5] or c[4]).replace("\\|", "|").strip().strip("`")
        if not txt or txt.startswith("(") or txt in ("—", "-"): txt = c[4].replace("\\|", "|").strip().strip("`")
        res[key].append((w, c[0], txt))
json.dump({k: [t for _, _, t in v] for k, v in res.items()}, open(OUT, "w"), ensure_ascii=False, indent=1)
for k, v in res.items():
    for w, n, t in v: print(k, w, n, t[:60])
