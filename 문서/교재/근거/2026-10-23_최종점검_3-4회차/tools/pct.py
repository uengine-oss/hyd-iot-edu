"""낭독 줄의 「N %」를 확정 회차 표기 「N퍼센트」로 바꾼다. 통합반 5 · 6회차는 실전반 4회차와 같은 문단만 바꾼다.
    python3 pct.py <제안 폴더 proposed> [회차 묶음: 3 | 4]
"""
import re, sys
from pathlib import Path
P = Path(sys.argv[1]); G = sys.argv[2]
def spoken(l): return l.strip() and not l.startswith((">", "#", "---", "|"))
def conv(l): return re.sub(r"(\d)\s*%", r"\1퍼센트", l)
own = {"3": ["통합반/03회차", "통합반/04회차", "실전반/03회차"], "4": ["실전반/04회차"]}[G]
shared = set()
n = 0
for d in own:
    for f in sorted((P / d).glob("*.md")):
        ls = f.read_text("utf-8").split("\n")
        shared |= {l for l in ls if spoken(l) and "%" in l}
        new = [conv(l) if spoken(l) else l for l in ls]; n += sum(a != b for a, b in zip(ls, new))
        f.write_text("\n".join(new), "utf-8")
if G == "4":
    for d in ["통합반/05회차", "통합반/06회차"]:
        for f in sorted((P / d).glob("*.md")):
            ls = f.read_text("utf-8").split("\n")
            new = [conv(l) if spoken(l) and l in shared else l for l in ls]; n += sum(a != b for a, b in zip(ls, new))
            f.write_text("\n".join(new), "utf-8")
print("바꾼 줄", n)
