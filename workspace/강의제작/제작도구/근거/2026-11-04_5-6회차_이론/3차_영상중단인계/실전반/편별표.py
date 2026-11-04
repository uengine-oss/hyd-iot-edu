"""편별 표(길이 · 장 범위 · 강조 수 · 말머리 · 장넘김 · 자막 대조 · 소리/화면 길이 · 크기 · 강조본 소리 같음)를 찍는다. 저장소 루트에서: python3 편별표.py"""
import json, re, subprocess, hashlib
from pathlib import Path
ROOT = Path("/home/user/hyd-iot-edu"); W = Path(__file__).resolve().parents[2]; G = Path(__file__).parent / "로그"
KEYS = ["05회차_01", "05회차_04", "05회차_06", "05회차_08", "06회차_01", "06회차_02", "06회차_03"]
def probe(f, s):
    o = subprocess.run(["ffprobe", "-v", "error", "-select_streams", s, "-show_entries", "stream=duration", "-of", "csv=p=0", str(f)], capture_output=True, text=True).stdout.strip()
    return float(o) if o else None
def audio_md5(f):
    return hashlib.md5(subprocess.run(["ffmpeg", "-v", "error", "-i", str(f), "-map", "0:a", "-f", "s16le", "-"], capture_output=True).stdout).hexdigest()
def mmss(x): return f"{int(x // 60)}:{x % 60:04.1f}"
rows = ["| 영상 | 장 | 길이(강조본) | 강조 | 말머리 잘림 | 장넘김 못 맞춤/기대 | 자막 = 대본 | 소리 · 화면 길이 차 | 크기 | 강조 전 · 뒤 소리 |", "|---|---|---:|---:|---:|---:|---|---:|---:|---|"]
for k in KEYS:
    key = f"실전반_{k}"; d = W / "영상출력" / key
    v = next((d / "영상").glob("*.mp4")); e = d / "강조" / v.name
    t = next((d / "_작업" / "영상_자막_기록").glob("*_시간표.md")).read_text(encoding="utf-8")
    sl = re.findall(r"^\| (\d+)(?:~(\d+))? \|", t, re.M); rng = f"{sl[0][0]}~{sl[-1][1] or sl[-1][0]}"
    cfg = ROOT / f"workspace/강의제작/제작도구/구성/실전반/{k[:4]}/강조_{v.stem}.json"
    nm = len(json.loads(cfg.read_text(encoding="utf-8"))["표시"])
    mm = re.search(r"앞이 말소리인 자리 (\d+)", (G / f"{key}_말머리.txt").read_text()).group(1)
    jn = re.search(r"기대 (\d+) .*못 맞춘 기대 (\d+)", (G / f"{key}_장넘김.txt").read_text())
    sub = subprocess.run(["python3", str(Path(__file__).parent / "자막대조.py"), k], capture_output=True, text=True).stdout.strip().split(": ", 1)[1]
    f = e if e.exists() else v
    va, vv = probe(f, "a:0"), probe(f, "v:0")
    same = (audio_md5(v) == audio_md5(e)) if e.exists() else "강조본 없음"
    rows.append(f"| {v.stem} | {rng} | {mmss(vv)} | {nm} | {mm} | {jn.group(2)}/{jn.group(1)} | {sub} | {abs(va - vv):.2f}초 | {f.stat().st_size / 2**20:.1f} MiB | {'같음(MD5)' if same is True else same} |")
print("\n".join(rows))
