"""마지막 손질 결과(<묶음>2)를 제안본 위에 모아 최종본을 만든다. 저장소는 읽지 않는다(제안본 기준).

    python3 merge4b.py <점검 폴더 final4> <3 | 4> [건너뛸 문자열 JSON]

- 4: 실전반 4회차 = 제안본 + D2(01 1~28) + E2(01 29~59) + F2(02 · 03 82~101) + G2(03 102~132).
     그다음 실전반 4회차 제안본 → 최종본 변경을 통합반 5 · 6회차 제안본에 옮긴다(to_통합반56 건너뜀).
- 3: 통합반 3회차 = A2, 통합반 4회차 = B2(01) · C2(02), 실전반 3회차 = A2(01) · B2(02) · C2(03)의 실전반 손질본에
     통합반 3 · 4회차 제안본 → 최종본 변경을 옮긴다(to_실전반3 건너뜀).
결과: <final4>/final/<과정>/<NN>회차/
"""
import json
import sys
from pathlib import Path

sys.argv, _argv = sys.argv[:1] + ["/dev/null", "/dev/null", "/dev/null"], sys.argv   # merge4의 함수만 쓴다
F4 = Path(_argv[1]); G = _argv[2]
SKIP = json.loads(Path(_argv[3]).read_text("utf-8")) if len(_argv) > 3 else {}
src = Path(__file__).with_name("merge4.py").read_text("utf-8")
ns = {}
exec(compile(src.split("\nlog = []\n")[0], "merge4", "exec"), ns)   # 함수 정의까지만
combine, patches, propagate = ns["combine"], ns["patches"], ns["propagate"]
PROP, OUT = F4 / "proposed", F4 / "final"


def read(d): return {f.name: f.read_text("utf-8").split("\n") for f in sorted(d.glob("*.md"))}


def copy(who, course, nn, name): return (F4 / f"{who}2" / course / f"{nn}회차" / name).read_text("utf-8").split("\n")


def save(course, nn, files):
    d = OUT / course / f"{nn}회차"; d.mkdir(parents=True, exist_ok=True)
    for n, ls in files.items(): (d / n).write_text("\n".join(ls), "utf-8")


log = []
if G == "4":
    p4 = read(PROP / "실전반" / "04회차"); s4 = {}
    for n, a in p4.items():
        if n.startswith("01"): s4[n] = combine(n, a, [("D2", copy("D", "실전반", "04", n), (1, 28)), ("E2", copy("E", "실전반", "04", n), (29, 59))])
        elif n.startswith("02"): s4[n] = combine(n, a, [("F2", copy("F", "실전반", "04", n), (60, 81))])
        else: s4[n] = combine(n, a, [("F2", copy("F", "실전반", "04", n), (82, 101)), ("G2", copy("G", "실전반", "04", n), (102, 132))])
    # 통합반 5 · 6회차는 실전반 4회차와 같은 문단만 맞춘다(사용자: 「반 단위로 해야 하는 거면 5회차도 … 어쩔 수 없고」)
    t56o = {f"05/{n}": ls for n, ls in read(PROP / "통합반" / "05회차").items()} | {f"06/{n}": ls for n, ls in read(PROP / "통합반" / "06회차").items()}
    t56 = {k: list(v) for k, v in t56o.items()}
    log += propagate("통합반 5·6회차", patches(p4, s4), t56, t56o, SKIP.get("to_통합반56", []))
    save("실전반", "04", s4)
    save("통합반", "05", {k[3:]: v for k, v in t56.items() if k.startswith("05/")})
    save("통합반", "06", {k[3:]: v for k, v in t56.items() if k.startswith("06/")})
else:
    p3, p4 = read(PROP / "통합반" / "03회차"), read(PROP / "통합반" / "04회차")
    t3 = {n: copy("A", "통합반", "03", n) for n in p3}
    t4 = {n: copy("B" if n.startswith("01") else "C", "통합반", "04", n) for n in p4}
    ps3 = read(PROP / "실전반" / "03회차")
    s3 = {n: copy({"01": "A", "02": "B", "03": "C"}[n[:2]], "실전반", "03", n) for n in ps3}
    log += propagate("실전반 3회차", patches(p3, t3) + patches(p4, t4), s3, ps3, SKIP.get("to_실전반3", []))
    save("통합반", "03", t3); save("통합반", "04", t4); save("실전반", "03", s3)
print("\n".join(log))
print(f"합계: 옮김 {sum(x.startswith('옮김') for x in log)} · 건너뜀 {sum(x.startswith('건너뜀') for x in log)} · 충돌 {sum(x.startswith('!') for x in log)}")
