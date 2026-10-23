"""실전반 4회차 최종 변경 가운데 통합반 5 · 6회차의 같은 문단에 옮길 것을 목록으로 만든다(통합반 파일은 고치지 않는다).

    python3 later56.py <저장소 루트> <점검 폴더 final4> <건너뛸 문자열 JSON> <출력 md> [손으로 맞출 것 md]

사용자 「3 4만 해라」(2026-10-23): 통합반 5 · 6회차는 그 회차를 점검할 때 이 목록을 반영한다.
"""
import difflib
import json
import re
import sys
from pathlib import Path

ROOT, F4, SKIPF, OUT = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
MANUAL = Path(sys.argv[5]).read_text("utf-8") if len(sys.argv) > 5 else ""
sys.argv = sys.argv[:1] + ["/dev/null"] * 3
ns = {}
exec(compile(Path(__file__).with_name("merge4.py").read_text("utf-8").split("\nlog = []\n")[0], "merge4", "exec"), ns)
patches, propagate, slide_of = ns["patches"], ns["propagate"], ns["slide_of"]
P = ROOT / "산출물"


def read(d): return {f.name: f.read_text("utf-8").split("\n") for f in sorted(d.glob("*.md"))}


s4o, s4 = read(P / "실전반/이론/04회차/대본"), read(F4 / "final/실전반/04회차")
t56o = {f"05/{n}": ls for n, ls in read(P / "통합반/이론/05회차/대본").items()} | {f"06/{n}": ls for n, ls in read(P / "통합반/이론/06회차/대본").items()}
t56 = {k: list(v) for k, v in t56o.items()}
log = propagate("통합반 5·6회차", patches(s4o, s4), t56, t56o, json.loads(SKIPF.read_text("utf-8")).get("to_통합반56", []))
md = ["# 통합반 5 · 6회차에 옮길 변경 — 실전반 4회차 최종 점검(2026-10-23)에서", "",
      "사용자 「3 4만 해라」로 이번에는 통합반 5 · 6회차 파일을 고치지 않았다. 아래는 실전반 4회차에서 고친 문단 가운데 통합반 5 · 6회차에 같은 문단이 있는 것이다. 그 회차를 점검할 때 그쪽 앞뒤와 장 그림으로 다시 확인한 뒤 반영한다. 「전」은 지금 통합반 대본의 문장, 「후」는 실전반 4회차 최종 문장이다.", ""]
if MANUAL.strip(): md += ["## 손으로 맞출 것(자동 대응에서 빠진 곳 · 다른 과정 이음새)", "", MANUAL.strip(), ""]
n = 0
for k in sorted(t56o):
    a, b = t56o[k], t56[k]
    if a == b: continue
    sl = slide_of(a)
    md += [f"## 통합반 {k[:2]}회차 · {k[3:]}", ""]
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == "equal": continue
        old = [x for x in a[i1:i2] if x.strip()]; new = [x for x in b[j1:j2] if x.strip()]
        if not old and not new: continue
        n += 1
        md += [f"### {n}. SLIDE {sl[max(i1 - (1 if i1 == i2 else 0), 0)]}", "", "- 전: " + (" / ".join(old) or "(없음 — 넣기)"), "- 후: " + (" / ".join(new) or "(지움)"), ""]
md += ["## 옮기지 않은 것(실전반 전용 · 대상에 없는 문장)", ""] + [f"- {x}" for x in log if not x.startswith("옮김")]
OUT.write_text("\n".join(md) + "\n", "utf-8")
print(OUT, "옮길 변경", n, "· 건너뜀", sum(not x.startswith("옮김") for x in log))
