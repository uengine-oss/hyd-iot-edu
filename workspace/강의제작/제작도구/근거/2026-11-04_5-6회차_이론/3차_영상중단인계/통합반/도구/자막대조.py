"""자막(.srt)과 대본의 낭독 글을 순서대로 견준다 — 빠진 · 바뀐 · 더한 글자가 없고 자막 한 줄이 한 문장인지.
    python3 자막대조.py <대본.md> <자막.srt>
낭독 글은 강의영상.py의 slides_text(음성을 만든 글 그대로), 견줄 때 띄어쓰기 · 줄바꿈은 뺀다."""
import importlib.util, re, sys
from pathlib import Path
V = Path(__file__).resolve().parents[5] / "workspace/강의제작/제작도구/기존제작/tools/video"
spec = importlib.util.spec_from_file_location("lv", V / "강의영상.py"); lv = importlib.util.module_from_spec(spec); spec.loader.exec_module(lv)
script, srt = sys.argv[1], Path(sys.argv[2]).read_text(encoding="utf-8")
want = "".join(re.sub(r"\s+", "", t) for _, _, t in lv.slides_text(script))
subs = [" ".join(b.split("\n")[2:]) for b in re.split(r"\n\n+", srt.strip()) if len(b.split("\n")) >= 3]
got = "".join(re.sub(r"\s+", "", s) for s in subs)
same = want == got
i = next((k for k in range(min(len(want), len(got))) if want[k] != got[k]), min(len(want), len(got)))
bad = [s for s in subs if not re.search(r"[.?!][’”』」)]*$", s.strip())]   # 문장 끝 부호로 끝나지 않는 자막 = 문장이 쪼개진 자리
print(f"자막 {len(subs)}줄 · 대본 글자 {len(want)} · 자막 글자 {len(got)} · {'같음' if same else f'다름(첫 차이 {i}번째 글자: 대본 「{want[i:i+20]}」 / 자막 「{got[i:i+20]}」)'} · 문장 끝이 아닌 자막 {len(bad)}줄")
for s in bad[:10]: print("  쪼개짐?", s)
sys.exit(0 if same and not bad else 1)
