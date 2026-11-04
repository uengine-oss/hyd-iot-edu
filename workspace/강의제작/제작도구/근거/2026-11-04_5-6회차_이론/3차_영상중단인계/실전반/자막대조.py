"""자막 = 대본 대조(순서대로). 저장소 루트에서: python3 자막대조.py <편 키 …>   예: 05회차_01
- 대본: 강의영상.py의 slides_text(낭독할 글)를 장 차례로 이은 글, 자막: 영상출력/실전반_<키>/_작업/영상_자막_기록/*.srt를 차례로 이은 글.
  둘을 공백을 빼고 글자 그대로 견준다(빠진 · 바뀐 · 순서가 다른 문장이 있으면 첫 어긋난 자리를 찍는다).
- 자막 줄이 문장 단위인지: 자막 한 줄이 문장 끝 부호(. ? !, 닫는 따옴표 앞 포함)로 끝나는지 센다.
"""
import importlib.util, re, sys
from pathlib import Path
ROOT = Path("/home/user/hyd-iot-edu"); W = Path(__file__).resolve().parents[2]
sys_argv = sys.argv[1:]; sys.argv = ["x", "_", "_"]
spec = importlib.util.spec_from_file_location("lv", ROOT / "workspace/강의제작/제작도구/기존제작/tools/video/강의영상.py")
M = importlib.util.module_from_spec(spec); spec.loader.exec_module(M)
norm = lambda s: re.sub(r"\s+", "", s)
bad = 0
for key in sys_argv:
    n, p = key.split("_")
    script = sorted((ROOT / f"workspace/강의제작/산출물/실전반/이론/{n}/대본").glob(f"{p}_*.md"))[0]
    a = norm("".join(t for _, _, t in M.slides_text(script)))
    srt = sorted((W / "영상출력" / f"실전반_{key}" / "_작업" / "영상_자막_기록").glob("*.srt"))[0]
    lines = [" ".join(b.split("\n")[2:]) for b in re.split(r"\n\n+", srt.read_text(encoding="utf-8").strip())]
    b = norm("".join(lines))
    ends = sum(bool(re.search(r"[.?!][’”」』]?$", x.strip())) for x in lines)
    if a == b:
        print(f"{key}: 같음 · 자막 {len(lines)}줄 · 문장 끝으로 끝나는 줄 {ends}/{len(lines)}")
    else:
        bad += 1; i = next(k for k in range(min(len(a), len(b)) + 1) if k == min(len(a), len(b)) or a[k] != b[k])
        print(f"{key}: 다름 — {i}번째 글자부터 대본 「{a[i:i+40]}」 · 자막 「{b[i:i+40]}」")
sys.exit(1 if bad else 0)
