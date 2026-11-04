"""장별점검.md를 영상 시간표 실측 · 최종 강조 설정으로 다시 쓴다. 저장소 루트에서: python3 작업/…/도구/장별점검_생성.py [--있는것만]
- 바탕: 지금 장별점검.md의 장마다 「학생이 따라갈 화면 속 대상」 · 「넣지 않은 까닭」(음성 전 어림 판).
- 길이: 영상출력/<덱키>_<편>/_작업/영상_자막_기록/*_시간표.md의 장 구획 음성(쉼 포함) 초. 묶음(NN~MM)은 둘째 장 시작 시각으로 나눈다.
- 강조: workspace/강의제작/제작도구/구성/<과정>/<NN>회차/강조_*.json의 장별 표시 수, 계획 수는 <덱키>/강조계획.json.
- 강조가 0인 장에는 까닭이 있어야 한다: 바탕 표의 까닭, 없으면 렌더/강조확인/<덱키>/뺀목록.txt(뺀 강조의 까닭), 없으면 도구/장별까닭.json {"덱키": {"장": "까닭"}}.
  까닭이 없는 장이 하나라도 있으면 쓰지 않고 목록을 내고 멈춘다. --있는것만: 시간표가 없는 편은 길이를 「—」로 두고 진행(시험용, 결과 파일 이름 장별점검_시험.md).
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
W = Path(__file__).resolve().parents[1]
G = ROOT / "workspace/강의제작/제작도구/구성"
DECKS = {"통합3": ("통합반", "03", ["01", "02", "03"], 74), "실전3": ("실전반", "03", ["01", "02", "03"], 80),
         "통합4": ("통합반", "04", ["01", "02"], 72), "실전4": ("실전반", "04", ["01", "02", "03"], 81)}
partial = "--있는것만" in sys.argv


def base_rows(text, key):
    sec = re.search(rf"^## {key}\n(.*?)(?=^## |\Z)", text, re.S | re.M).group(1)
    rows = {}
    for m in re.finditer(r"^\| (?:\*\*)?(\d+)(?:\*\*)? \| [\d—]+ \|(.*?)\|(.*?)\|(.*?)\|$", sec, re.M):
        rows[int(m.group(1))] = {"대상": m.group(2).strip(), "까닭": m.group(4).strip()}
    return rows


def lengths(key, part):
    out = {}
    for p in part:
        t = sorted((W / "영상출력" / f"{key}_{p}" / "_작업" / "영상_자막_기록").glob("*_시간표.md"))
        if not t:
            if partial: continue
            sys.exit(f"{key}_{p}: 시간표가 없다 — 영상을 다 구운 뒤 돌린다")
        for m in re.finditer(r"^\| (\d+)(?:~(\d+))? \| (\d+):(\d+)(?: \(SLIDE \d+부터 (\d+):([\d.]+)\))? \| ([\d.]+) \|", t[0].read_text(encoding="utf-8"), re.M):
            a, b, total = int(m.group(1)), m.group(2), float(m.group(7))
            if b:
                first = int(m.group(5)) * 60 + float(m.group(6)) - (int(m.group(3)) * 60 + int(m.group(4)))
                out[a], out[int(b)] = round(first), round(total - first)
            else:
                out[a] = round(total)
    return out


def counts(files):
    c = {}
    for f in files:
        for m in json.loads(Path(f).read_text(encoding="utf-8"))["표시"]:
            c[int(m["장"])] = c.get(int(m["장"]), 0) + 1
    return c


def main():
    src = W / "장별점검_어림판.md"   # 바탕(대상 · 음성 전 까닭)은 어림판에서 — 생성한 판을 다시 바탕으로 쓰면 까닭이 굳는다
    text = src.read_text(encoding="utf-8")
    dropped = {}
    for key in DECKS:   # 덱 작업자가 쓴 뺀목록(계획번호|편|장|대상|까닭) — 장의 까닭을 모두 「 · 」로 잇는다
        f = W / "렌더/강조확인" / key / "뺀목록.txt"
        if not f.exists(): sys.exit(f"{f}: 없다 — 강조 다시 고르기가 끝난 뒤 돌린다")
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                _, _, s, _, why = line.split("|", 4)
                lst = dropped.setdefault((key, int(s)), [])
                if why.strip() not in lst: lst.append(why.strip())
    extra_p = W / "도구/장별까닭.json"
    extra = json.loads(extra_p.read_text(encoding="utf-8")) if extra_p.exists() else {}
    out, missing = ["# 장별점검 — 네 온라인 덱 전 장(영상 시간표 실측 · 최종 강조 설정)", ""], []
    for key, (course, nn, part, n) in DECKS.items():
        base, ln = base_rows(text, key), lengths(key, part)
        final = counts(sorted((G / course / f"{nn}회차").glob("강조_*.json")))
        plan = counts([W / key / "강조계획.json"])
        long = sum(1 for s in range(1, n + 1) if ln.get(s, 0) > 120)
        total = sum(ln.values())
        out += [f"## {key}", "", f"# {course} {int(nn)}회차 온라인 덱 — 장별 점검표({n}장)", "",
                f"길이(초)는 영상 시간표의 장 구획 길이(쉼을 넣은 음성, 실측)다. 굵은 장은 2분이 넘는다({long}장). 합계 {total / 60:.1f}분. "
                "강조 수는 최종 강조 설정(`workspace/강의제작/제작도구/구성/" + f"{course}/{nn}회차/강조_*.json`)의 표시 수이고, "
                "좌표를 맞추며 계획에서 뺀 것이 있으면 「계획 k」를 함께 적는다.", "",
                "| 장 | 길이(초) | 학생이 따라갈 화면 속 대상 | 강조 | 넣지 않은 까닭 |", "|---|---:|---|---|---|"]
        for s in range(1, n + 1):
            if s not in base: sys.exit(f"{key} {s}장: 바탕 표에 행이 없다")
            sec = ln.get(s)
            if sec is None and not partial: sys.exit(f"{key} {s}장: 시간표에 장이 없다")
            f, p = final.get(s, 0), plan.get(s, 0)
            mark = f"있음({f})" if f else "없음"
            if p and p != f: mark += f" · 계획 {p}"
            why = ""
            if not f:
                why = base[s]["까닭"] or " · ".join(dropped.get((key, s), [])) or extra.get(key, {}).get(str(s), "")
                if not why: missing.append(f"{key} {s}장(길이 {sec}초, 계획 {p})")
            label = f"**{s}**" if sec and sec > 120 else str(s)
            out.append(f"| {label} | {sec if sec is not None else '—'} | {base[s]['대상']} | {mark} | {why} |")
        out.append("")
    if missing:
        sys.exit("강조가 없는데 까닭이 없는 장 — 도구/장별까닭.json에 적는다:\n  " + "\n  ".join(missing))
    dst = W / ("장별점검_시험.md" if partial else "장별점검.md")
    dst.write_text("\n".join(out), encoding="utf-8")
    print(f"썼다 {dst.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
