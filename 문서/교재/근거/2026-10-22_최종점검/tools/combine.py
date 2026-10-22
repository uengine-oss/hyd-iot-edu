"""두 차수 변경목록에서 본표 행(7칸 이상, 구분이 알려진 값)만 모아 한 표로. python3 combine.py <출력> <목록1> [<목록2> 접두어=3차-]"""
import re, sys
from pathlib import Path
CAT = re.compile(r"^(결함|윤문|이음윤문|의심반영|쉬운설명|같은문장맞춤)")
out = ["| 번호 | 파일 | SLIDE | 구분 | 전 | 후 | 근거 |", "|---|---|---|---|---|---|---|"]
for i, f in enumerate(sys.argv[2:]):
    for line in Path(f).read_text("utf-8").splitlines():
        if not line.startswith("|") or re.match(r"^\|[\s\-:|]+\|?$", line): continue
        c = [x.strip() for x in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
        if len(c) >= 7 and CAT.match(c[3]):
            c[0] = ("3차-" if i else "") + c[0]
            out.append("| " + " | ".join(c[:7]) + " |")
Path(sys.argv[1]).write_text("\n".join(out) + "\n", "utf-8")
print(sys.argv[1], len(out) - 2, "행")
