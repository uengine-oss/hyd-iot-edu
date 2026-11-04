"""통합반 5 · 6회차 온라인 덱 장별점검(장 · 길이 · 화면 속 대상 · 강조 · 넣지 않은 까닭)을 영상 시간표 실측과 최종 강조 설정으로 쓴다.
3 · 4회차 근거 `도구/장별점검_생성.py`의 꼴(표 머리 · 2분 넘는 장 굵게 · 강조가 없는 장은 까닭 필수)을 따른다.
    python3 장별점검.py [--있는것만]     (저장소 루트에서)
- 길이: 영상출력/통합반_NN회차_PP/_작업/영상_자막_기록/*_시간표.md의 장 구획(쉼 포함) 초. 묶음(NN~MM)은 둘째 장 시작 시각으로 나눈다.
- 강조 수 · 대상: workspace/강의제작/제작도구/구성/통합반/NN회차/강조_*.json(장마다 표시 수, 대상은 표시의 「대상」을 차례로).
- 강조가 없는 장: 도구/장별까닭.json {"통합5": {"장": [대상, 까닭]}}. 없으면 쓰지 않고 멈춘다."""
import json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[5]; T = Path(__file__).resolve().parents[1]; W = T.parents[1]
G = ROOT / "workspace/강의제작/제작도구/구성/통합반"
DECKS = {"통합5": ("05", ["01", "02"], 77), "통합6": ("06", ["01", "02", "03"], 78)}
partial = "--있는것만" in sys.argv
why = json.loads((T / "도구/장별까닭.json").read_text(encoding="utf-8"))

def lengths(nn, part):
    out = {}
    for p in part:
        t = sorted((W / "영상출력" / f"통합반_{nn}회차_{p}" / "_작업" / "영상_자막_기록").glob("*_시간표.md"))
        if not t:
            if partial: continue
            sys.exit(f"{nn}_{p}: 시간표가 없다")
        for m in re.finditer(r"^\| (\d+)(?:~(\d+))? \| (\d+):(\d+)(?: \(SLIDE \d+부터 (\d+):([\d.]+)\))? \| ([\d.]+) \|", t[0].read_text(encoding="utf-8"), re.M):
            a, b, total = int(m.group(1)), m.group(2), float(m.group(7))
            if b:
                first = int(m.group(5)) * 60 + float(m.group(6)) - (int(m.group(3)) * 60 + int(m.group(4)))
                out[a], out[int(b)] = round(first), round(total - first)
            else: out[a] = round(total)
    return out

out, missing = ["# 장별점검 — 통합반 5 · 6회차 온라인 덱 전 장(영상 시간표 실측 · 최종 강조 설정)", ""], []
for key, (nn, part, n) in DECKS.items():
    ln = lengths(nn, part); marks = {}
    for f in sorted((G / f"{nn}회차").glob("강조_*.json")):
        for m in json.loads(f.read_text(encoding="utf-8"))["표시"]: marks.setdefault(int(m["장"]), []).append(m)
    long = [s for s in range(1, n + 1) if ln.get(s, 0) > 120]
    out += [f"## {key}", "", f"통합반 {int(nn)}회차 온라인 덱 {n}장. 길이(초)는 영상 시간표의 장 구획 길이(쉼을 넣은 음성, 실측)다. 굵은 장은 2분이 넘는다({len(long)}장). "
            f"합계 {sum(ln.values()) / 60:.1f}분. 강조 수는 최종 강조 설정(`workspace/강의제작/제작도구/구성/통합반/{nn}회차/강조_*.json`)의 표시 수, 대상은 표시가 짚는 차례다.", "",
            "| 장 | 길이(초) | 학생이 따라갈 화면 속 대상 | 강조 | 넣지 않은 까닭 |", "|---|---:|---|---|---|"]
    for s in range(1, n + 1):
        sec = ln.get(s)
        if sec is None and not partial: sys.exit(f"{key} {s}장: 시간표에 장이 없다")
        ms = marks.get(s, [])
        if ms: target, mark, reason = " → ".join(m.get("대상", "") for m in ms), f"있음({len(ms)})", ""
        else:
            w = why.get(key, {}).get(str(s))
            if not w: missing.append(f"{key} {s}장(길이 {sec}초)"); continue
            target, mark, reason = w[0], "없음", w[1]
        label = f"**{s}**" if sec and sec > 120 else str(s)
        out.append(f"| {label} | {sec if sec is not None else '—'} | {target} | {mark} | {reason} |")
    out.append("")
if missing: sys.exit("강조가 없는데 까닭이 없는 장 — 도구/장별까닭.json에 적는다:\n  " + "\n  ".join(missing))
dst = T / ("장별점검_시험.md" if partial else "장별점검.md")
dst.write_text("\n".join(out), encoding="utf-8"); print(f"썼다 {dst.relative_to(ROOT)}")
