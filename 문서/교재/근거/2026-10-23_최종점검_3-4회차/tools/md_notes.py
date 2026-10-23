"""덱 원고 MD의 장마다 `- 노트:` 줄을 대본의 낭독 문단으로 바꾼다(기준_이론대본 87번: 노트 = 현행 분할 대본).
대본 → 노트 글은 2026-10-22 notes.py와 같은 규칙(낭독 문단을 공백 하나로 잇고, `SLIDE NN~MM` 묶음의 뒤 장은 첫 장을 가리킨다).

    python3 md_notes.py <대본 폴더> <덱 원고 MD 입력> <출력 MD>
"""
import re
import sys
from pathlib import Path

HEAD = re.compile(r"^## \[SLIDE ([0-9~]+)\].*$", re.M)


def expected(folder):
    out = {}
    for f in sorted(Path(folder).glob("*.md")):
        t = f.read_text("utf-8")
        for m in HEAD.finditer(t):
            nxt = re.compile(r"^#{1,2} ", re.M).search(t, m.end())
            body = t[m.end():nxt.start() if nxt else len(t)]
            paras = []
            for p in re.split(r"\n\s*\n", body):
                lines = [x for x in p.split("\n") if x.strip() and not re.match(r"^(>|---\s*$|\|)", x)]
                if lines: paras.append(" ".join(x.strip() for x in lines).replace("**", ""))
            parts = m.group(1).split("~"); first, last = int(parts[0]), int(parts[-1])
            out[first] = " ".join(paras)
            for k in range(first + 1, last + 1):
                out[k] = f"{first}~{last}장 통합 발화는 {first}장 발표자 노트를 따른다."
    return out


exp = expected(sys.argv[1])
src = Path(sys.argv[2]).read_text("utf-8").split("\n")
out, cur, changed = [], None, []
for ln in src:
    m = re.match(r"^## SLIDE (\d+)", ln)
    if m: cur = int(m.group(1))
    if cur in exp and ln.startswith("- 노트:"):
        new = f"- 노트: {exp[cur]}"
        if new != ln: changed.append(cur)
        ln = new
    out.append(ln)
Path(sys.argv[3]).write_text("\n".join(out), "utf-8")
miss = sorted(set(exp) - {int(x) for x in re.findall(r"^## SLIDE (\d+)", "\n".join(src), re.M)})
print(f"노트를 바꾼 장 {len(changed)}: {changed}" + (f" · 원고에 없는 장 {miss}" if miss else ""))
