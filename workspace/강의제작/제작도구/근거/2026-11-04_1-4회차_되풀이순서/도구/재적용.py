"""사용자 지시 「심각한 것만」: 커밋본으로 복원한 뒤 가림/심각.json 항목만 다시 적용한다."""
import glob
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

W = Path("작업/2026-11-04_1-4회차-이론-되풀이-순서")
BASE = "7e85bdd4"
PY = sys.executable
DECKS = [("통합반", "01"), ("통합반", "02"), ("통합반", "03"), ("통합반", "04"), ("실전반", "02"), ("실전반", "03"), ("실전반", "04")]
ALL = DECKS + [("실전반", "01")]
DK = {"통합반": "integrated", "실전반": "practical"}
env = dict(os.environ, PYTHONUTF8="1")


def run(*a):
    r = subprocess.run(a, capture_output=True, env=env)
    return r.returncode, (r.stdout + r.stderr).decode("utf8", "replace")


def restore(p):
    p = str(p).replace("\\", "/")
    r = subprocess.run(["git", "show", f"{BASE}:{p}"], capture_output=True)
    if r.returncode:
        sys.exit(f"커밋본에 없다: {p}")
    if not os.path.exists(p) or open(p, "rb").read() != r.stdout:
        open(p, "wb").write(r.stdout)
        return 1
    return 0


ct = 0
offs = [("integrated", n) for n in ("01", "02", "03", "04")] + [("practical", n) for n in ("01", "02", "03", "04", "05")]
for c, n in ALL:
    for f in glob.glob(f"workspace/강의제작/산출물/{c}/이론/{n}회차/대본/*.md"):
        ct += restore(f)
    ct += restore(f"workspace/강의제작/제작도구/온라인/decks/{DK[c]}/day{n}/{c}_{n}일차.md")
    ct += restore(f"workspace/강의제작/산출물/{c}/이론/{n}회차/{c}_{n}일차.pptx")
    ct += restore(f"workspace/강의제작/제작도구/구성/{c}/{n}회차/구성.json")
    ct += restore(f"workspace/강의제작/제작도구/구성/{c}/{n}회차/구성표.md")
for k, n in offs:
    name = {"integrated": "통합반", "practical": "실전반"}[k]
    ct += restore(f"workspace/강의제작/제작도구/오프라인/decks/{k}/off{n}/{name}_오프라인_{n}회차.md")
    ct += restore(f"workspace/강의제작/산출물/{name}/이론_오프라인/{n}회차/{name}_오프라인_{n}회차.pptx")
print("커밋본으로 복원한 파일", ct)

# 판정: 심각 아님 → 보류. 첫 판정은 판정_전체/에 보관
serious = json.load(open(W / "가림/심각.json", encoding="utf8"))
(W / "판정_전체").mkdir(exist_ok=True)
for c, n in DECKS:
    name = f"{c}_{n}"
    keep = W / "판정_전체" / f"{name}.json"
    if not keep.exists():
        shutil.copy(W / "판정" / f"{name}.json", keep)
    jd = json.load(open(keep, encoding="utf8"))
    items = {x["번호"]: x for x in json.load(open(W / "점검" / f"{name}.json", encoding="utf8"))["고칠것"]}
    s = serious[name]
    for k, v in jd["판정"].items():
        if k not in s:
            jd["판정"][k] = {"처리": "보류", "까닭": "심각 아님 — 사용자 지시(심각한 것만, 의도 제외)로 남김"}
    slides = {items[k]["장"] for k in s}
    jd["노트추가"] = [x for x in jd.get("노트추가", []) if x["장"] in slides]
    json.dump(jd, open(W / "판정" / f"{name}.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
    code, out = run(PY, str(W / "도구/적용.py"), "실행", c, n)
    print(out.strip().split("\n")[0][:120] if code == 0 else out[:1500])
    if code:
        sys.exit(f"{name} 적용 실패")

code, out = run(PY, str(W / "도구/적용.py"), "실행", "실전반", "01", "--목록", "통합반_01", "--대본만")
print("실전1", out.strip().split("\n")[0][:100])
code, out = run(PY, "workspace/강의제작/제작도구/온라인/decks/practical/day01/조립.py")
print(out.strip()[:100])
print(run(PY, str(W / "도구/찌꺼기.py"))[1].count("정리"), "파일 찌꺼기 정리")


def once(path, old, new):
    b = open(path, "rb").read().decode("utf8")
    if b.count(old) == 1:
        open(path, "wb").write(b.replace(old, new).encode("utf8"))
        return True
    return False


# 도구 사정으로 바뀐 글자 되돌리기(그 항목이 살아 있을 때만)
for old, new in [("맨 아래 줄은 값을 어떻게 얻느냐입니다.", "마지막 줄은 값을 어떻게 얻느냐입니다."), ("마지막 줄 ORDER BY는 결과의 순서를 정합니다.", "마지막 줄의 ORDER BY는 결과의 순서를 정합니다.")]:
    hit = [p for p in glob.glob("workspace/강의제작/산출물/통합반/이론/02회차/대본/*.md") if once(p, old, new)]
    r = W / "고침기록/통합반_02.md"
    r.write_text(r.read_text("utf8").replace(old, new), "utf8", newline="\n")
    print("글자 되돌림", old[:10], len(hit))

# 화면 쪽 항목
print("P2-22 심각", "P2-22" in serious["실전반_02"], "| P3-08", "P3-08" in serious["실전반_03"], "| P3-34", "P3-34" in serious["실전반_03"])

# 통합 1 낭독 = 실전 1
print(run(PY, str(W / "도구/본문대조.py"))[1].strip()[:200])
