"""강조 설정을 영상을 굽지 않고 검사한다 — 강조표시.py의 plan()(문장 · 낱말 · 끝문장 찾기, 화면 밖 좌표)을 그대로 돌리고,
같은 때 떠 있는 표시(지우는 0.25초 포함)의 최대 수와 그리는 때 · 지우는 때를 찍는다.
    python3 강조검사.py <강조 전 영상.mp4> <강조.json>"""
import importlib.util, json, sys
from pathlib import Path
V = Path(__file__).resolve().parents[5] / "workspace/강의제작/제작도구/기존제작/tools/video"
spec = importlib.util.spec_from_file_location("emph", V / "강조표시.py"); E = importlib.util.module_from_spec(spec); spec.loader.exec_module(E)
video = Path(sys.argv[1]); rec = video.parent.parent / "_작업" / "영상_자막_기록"
E.ALIGN = list(E.alignments())
marks = E.plan(json.loads(Path(sys.argv[2]).read_text(encoding="utf-8")), E.read_srt(rec / f"{video.stem}.srt"), E.read_slides(rec / f"{video.stem}_시간표.md"))
ev = sorted([(m["start"], 1) for m in marks] + [(m["end"] + E.FADE, -1) for m in marks])
cur = top = 0
for t, d in ev:
    cur += d; top = max(top, cur)
short = [m for m in marks if m["end"] - m["start"] < 1.5]
print(f"표시 {len(marks)}개 · 같은 때 최대 {top}개(지우는 0.25초 포함) · 1.5초 안에 지워지는 표시 {len(short)}개")
for m in short: print(f"  짧음: {m['장']}장 {m['start']:.1f}~{m['end']:.1f}초 {m['모양']} {m.get('대상','')}")
sys.exit(0 if top <= 2 else 1)
