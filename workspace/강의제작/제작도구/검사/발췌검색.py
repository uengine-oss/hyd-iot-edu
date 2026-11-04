"""학생 발췌 · ZIP · 목록(실습 산출물)에서 이론 덱 장 번호를 가리키는 곳을 찾는다. 읽기만 한다.
언제: 이론 덱의 장 번호가 바뀌었을 때 — 실습 쪽 발췌가 옛 번호를 가리키는지 찾는다.
명령: <py> workspace/강의제작/제작도구/검사/발췌검색.py <출력 파일> <회차 …(03 04 05)>
"""
import re, sys, zipfile
from pathlib import Path

R = Path(__file__).resolve().parents[2] / "산출물"
if len(sys.argv) < 3:
    sys.exit(__doc__)
pat = re.compile(r"(?:SLIDE\s*\d+|\d+\s*(?:~\s*\d+\s*)?장(?![가-힣]))")
out = []
for c in ["통합반", "실전반"]:
    for n in sys.argv[2:]:
        base = R / c / "실습" / f"{int(n):02d}회차"
        if not base.exists():
            continue
        for f in sorted(base.rglob("*")):
            if f.suffix in (".md", ".html", ".json") and f.is_file():
                t = f.read_text("utf8", errors="replace")
                hits = [m.group(0) for m in pat.finditer(t)]
                if hits and ("발췌" in f.name or "교재" in t[:600] or "덱" in t[:600]):
                    out.append(f"{f.relative_to(R)}\t{sorted(set(hits))[:20]}")
            if f.suffix == ".zip":
                with zipfile.ZipFile(f) as z:
                    for i in z.namelist():
                        if "발췌" in i:
                            t = z.read(i).decode("utf8", "replace"); hits = [m.group(0) for m in pat.finditer(t)]
                            out.append(f"ZIP {f.relative_to(R)}\t{i}\t{sorted(set(hits))[:20]}")
Path(sys.argv[1]).write_text("\n".join(out), "utf8"); print(len(out)); print("\n".join(x[:200] for x in out[:50]))
