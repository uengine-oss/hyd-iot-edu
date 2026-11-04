"""덱마다 장별 점검표(장 · 길이 · 화면 속 대상 · 강조 · 넣지 않은 까닭)를 쓴다. 강조가 없는 장에 까닭이 없으면 멈춘다.
언제: 음성 전에는 --어림(대본 시간 계수), 영상을 구운 뒤에는 시간표 실측으로. 덱마다 점검표 만드는 스크립트를 다시 짜지 않으려고 쓴다.
명령: <py> workspace/강의제작/제작도구/검사/장별점검_생성.py <덱키 …(통합3 실전4)> --출력 장별점검.md [--어림] [--바탕 어림판.md] [--시간표 폴더 …] [--계획 틀] [--뺀목록 틀] [--까닭 장별까닭.json] [--있는것만]

- 길이: 시간표(기본 산출물/영상/_작업/영상_자막_기록/, --시간표 폴더들 아래에서 먼저 찾음)의 장 구획 음성(쉼 포함) 초. 묶음(NN~MM)은 둘째 장 시작 시각으로 나눈다. --어림이면 대본 시간 계수.
- 강조: 구성/<과정>/<NN>회차/강조_*.json의 장별 표시 수, --계획 틀(예 작업/x/{덱}/강조계획.json)이 있으면 계획 수를 함께 적는다.
- 대상 · 까닭: --바탕(같은 표가 `## 덱키` 절 아래 있는 판, 음성 전 판을 준다 — 생성한 판을 다시 바탕으로 쓰면 까닭이 굳는다). 없으면 대상 = 덱 제목 + 계획의 대상.
- 강조가 0인 장의 까닭: 바탕 표, --뺀목록 틀(한 줄 = 계획번호|편|장|대상|까닭), --까닭 파일({"덱키": {"장": "까닭"}}) 순서. 하나도 없는 장이 있으면 쓰지 않고 목록을 내고 멈춘다.
- --있는것만: 시간표가 없는 편은 길이를 「—」로 둔다(시험용).
"""
import argparse, json, re, sys
from pathlib import Path

G = Path(__file__).resolve().parents[2]   # workspace/강의제작
ROOT = G.parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(G / "제작도구/촬영"))
from 시간계산 import load_coef, script_slides, slide_seconds  # noqa: E402

COURSE = {"통합": ("통합반", "integrated"), "실전": ("실전반", "practical")}


def deck_of(key):
    m = re.fullmatch(r"(통합|실전)(\d+)", key)
    if not m:
        sys.exit(f"{key}: 덱키는 통합3 · 실전10 꼴이다")
    course, dk = COURSE[m[1]]; nn = f"{int(m[2]):02d}"
    md = G / f"제작도구/온라인/decks/{dk}/day{nn}/{course}_{nn}일차.md"
    sd = G / f"산출물/{course}/이론/{nn}회차/대본"
    if not md.exists() or not sd.is_dir():
        sys.exit(f"{key}: {md} 또는 {sd}가 없다")
    return course, nn, md, sd


def base_rows(text, key):
    m = re.search(rf"^## {key}\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    if not m:
        return {}
    rows = {}
    for r in re.finditer(r"^\| (?:\*\*)?(\d+)(?:\*\*)? \| [\d—]+ \|(.*?)\|(.*?)\|(.*?)\|$", m.group(1), re.M):
        rows[int(r.group(1))] = {"대상": r.group(2).strip(), "까닭": r.group(4).strip()}
    return rows


def lengths(course, nn, sd, folders, partial):
    out = {}
    for sc in sorted(sd.glob("*.md")):
        name = f"{course}_{nn}회차_{sc.stem}_시간표.md"
        t = next((f for d in folders for f in sorted(Path(d).rglob(name))), None)
        if t is None:
            if partial: continue
            sys.exit(f"{name}: {[str(d) for d in folders]} 아래에 시간표가 없다 — 영상을 다 구운 뒤 돌리거나 --어림을 준다")
        for m in re.finditer(r"^\| (\d+)(?:~(\d+))? \| (\d+):(\d+)(?: \(SLIDE \d+부터 (\d+):([\d.]+)\))? \| ([\d.]+) \|", t.read_text(encoding="utf-8"), re.M):
            a, b, total = int(m.group(1)), m.group(2), float(m.group(7))
            if b:
                first = int(m.group(5)) * 60 + float(m.group(6)) - (int(m.group(3)) * 60 + int(m.group(4)))
                out[a], out[int(b)] = round(first), round(total - first)
            else:
                out[a] = round(total)
    return out


def estimates(sd):
    k = load_coef(); out = {}
    for f in sorted(sd.glob("*.md")):
        for n, (text, share, _) in script_slides(f.read_text(encoding="utf-8")).items():
            out[n] = round(slide_seconds(text, k) / share if share > 1 else slide_seconds(text, k))
    return out


def counts(files):
    c, targets = {}, {}
    for f in files:
        for m in json.loads(Path(f).read_text(encoding="utf-8"))["표시"]:
            s = int(m["장"])
            c[s] = c.get(s, 0) + 1
            targets.setdefault(s, []).append(m.get("대상", ""))
    return c, targets


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("keys", nargs="+")
    ap.add_argument("--출력", dest="out", required=True)
    ap.add_argument("--어림", dest="rough", action="store_true")
    ap.add_argument("--바탕", dest="base")
    ap.add_argument("--시간표", dest="sides", nargs="*", default=[])
    ap.add_argument("--계획", dest="plan")
    ap.add_argument("--뺀목록", dest="drop")
    ap.add_argument("--까닭", dest="extra")
    ap.add_argument("--있는것만", dest="partial", action="store_true")
    a = ap.parse_args()
    text = Path(a.base).read_text(encoding="utf-8") if a.base else ""
    extra = json.loads(Path(a.extra).read_text(encoding="utf-8")) if a.extra else {}
    folders = [Path(x) for x in a.sides] + [G / "산출물/영상/_작업/영상_자막_기록"]
    out = [("# 장별점검 — 온라인 덱 전 장(" + ("대본 시간 어림 · 음성 전" if a.rough else "영상 시간표 실측 · 최종 강조 설정") + ")"), ""]
    missing = []
    for key in a.keys:
        course, nn, md, sd = deck_of(key)
        titles = {int(n): t.replace(" / ", " ") for n, t in re.findall(r"(?m)^## SLIDE (\d+) — (.*)$", md.read_text(encoding="utf-8"))}
        n = len(titles)
        base = base_rows(text, key)
        ln = estimates(sd) if a.rough else lengths(course, nn, sd, folders, a.partial)
        final, _ = counts(sorted((G / f"제작도구/구성/{course}/{nn}회차").glob("강조_*.json")))
        plan, ptargets = {}, {}
        if a.plan and Path(a.plan.format(덱=key)).exists():
            plan, ptargets = counts([a.plan.format(덱=key)])
        dropped = {}
        if a.drop and Path(a.drop.format(덱=key)).exists():
            for line in Path(a.drop.format(덱=key)).read_text(encoding="utf-8").splitlines():
                if line.strip():
                    _, _, s, _, why = line.split("|", 4)
                    lst = dropped.setdefault(int(s), [])
                    if why.strip() not in lst: lst.append(why.strip())
        long = sum(1 for s in range(1, n + 1) if ln.get(s, 0) > 120)
        total = sum(ln.values())
        kind = "대본 시간 계수로 잰 어림이다(음성 전)" if a.rough else "영상 시간표의 장 구획 길이(쉼을 넣은 음성, 실측)다"
        out += [f"## {key}", "", f"# {course} {int(nn)}회차 온라인 덱 — 장별 점검표({n}장)", "",
                f"길이(초)는 {kind}. 굵은 장은 2분이 넘는다({long}장). 합계 {total / 60:.1f}분. "
                "강조 수는 최종 강조 설정(`workspace/강의제작/제작도구/구성/" + f"{course}/{nn}회차/강조_*.json`)의 표시 수이고, "
                "좌표를 맞추며 계획에서 뺀 것이 있으면 「계획 k」를 함께 적는다.", "",
                "| 장 | 길이(초) | 학생이 따라갈 화면 속 대상 | 강조 | 넣지 않은 까닭 |", "|---|---:|---|---|---|"]
        for s in range(1, n + 1):
            if s not in titles:
                sys.exit(f"{key} {s}장: 덱 원고에 장이 없다")
            sec = ln.get(s)
            if sec is None and not a.partial:
                sys.exit(f"{key} {s}장: {'대본' if a.rough else '시간표'}에 장이 없다")
            f, p = final.get(s, 0), plan.get(s, 0)
            mark = f"있음({f})" if f else "없음"
            if p and p != f: mark += f" · 계획 {p}"
            row = base.get(s, {})
            target = row.get("대상") or (titles[s] + (": " + " → ".join(ptargets[s]) if ptargets.get(s) else ""))
            why = ""
            if not f:
                why = row.get("까닭") or " · ".join(dropped.get(s, [])) or extra.get(key, {}).get(str(s), "")
                if not why: missing.append(f"{key} {s}장(길이 {sec}초, 계획 {p})")
            label = f"**{s}**" if sec and sec > 120 else str(s)
            out.append(f"| {label} | {sec if sec is not None else '—'} | {target} | {mark} | {why} |")
        out.append("")
    if missing:
        sys.exit(f"강조가 없는데 까닭이 없는 장 {len(missing)}곳 — --까닭 파일에 적는다:\n  " + "\n  ".join(missing))
    Path(a.out).write_text("\n".join(out), encoding="utf-8", newline="\n")
    print(f"썼다 {a.out}")


if __name__ == "__main__":
    main()
