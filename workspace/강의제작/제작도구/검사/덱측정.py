"""덱의 전체·이론 본문 장 수를 구분한다. 온라인은 장마다 유형 · 레이아웃 · 메시지 · 그림 · 대본 어림 낭독 시간을 JSON으로 내고, 대본이 덮지 못한 장과 긴 장도 찍는다.
언제: 덱 재편 전후, 장별 점검 · 시간 배분을 판단할 때. 읽기만 하고 음성을 부르지 않는다.
명령: <py> workspace/강의제작/제작도구/검사/덱측정.py <출력.json> <덱키 …(통합3 실전4)> [--오프라인]
"""
import argparse, json, re, sys
from pathlib import Path

W = Path(__file__).resolve().parents[2]   # workspace/강의제작
sys.dont_write_bytecode = True
sys.path.insert(0, str(W / "제작도구/촬영"))
from 시간계산 import load_coef, script_slides, slide_seconds  # noqa: E402

COURSE = {"통합": ("통합반", "integrated"), "실전": ("실전반", "practical")}


def script_marks_review(folder, number, title):
    header = rf"^# \[마무리\][^\n]*\n\s*^## \[SLIDE 0*{number}\][ \t]+{re.escape(title)}[ \t]*$"
    return any(re.search(header, f.read_text(encoding="utf-8"), re.M) for f in folder.glob("*.md"))


def theory_count(slides, sections, rows, online, review_marked):
    """D-2의 도입·마무리 자리를 확인한 뒤, 간지의 구분과 구성 행으로 본문 후보를 센다."""
    total = len(slides)
    if total < 11 or list(slides) != list(range(1, total + 1)):
        return "이론 본문 미확인 (D-2 장 번호·순서 확인)"
    titles = [slide["title"] for slide in slides.values()]
    if (slides[1]["type"] != "표지" or titles[1:3] != ["학습목표", "목차"]
            or titles[-6:-4] != ["오늘 다룬 핵심 개념과 주요 용어 정리", "Review Quiz: 핵심 흐름 되짚어보기"]
            or not all(t.startswith(f"Quiz {i}.") for i, t in enumerate(titles[-4:-1], 1))
            or titles[-1] != "정답과 판단 기준"):
        return "이론 본문 미확인 (D-2 도입·복습·퀴즈 자리 확인)"
    known = 0
    unknown = [] if review_marked else [total - 6]
    misplaced = []
    kind = ""
    for n in range(4, total - 6):  # 용어 장 바로 앞 복습부터는 마무리다.
        if slides[n]["type"] == "간지":
            kind = sections.get(n, "")
            continue
        slide = slides[n]
        if (slide["type"] in ("표지", "목차", "퀴즈", "복습", "용어 정리", "정답", "학습목표")
                or slide["title"] in (titles[1], titles[2], titles[-6], titles[-5], titles[-1])
                or re.match(r"^(?:Quiz \d+\.|복습\s*[:：])", slide["title"])):
            misplaced.append(n)
            continue
        is_theory = kind in ("이론", "이론 · 실습")
        if kind not in ("이론", "이론 · 실습", "실습") or not slides[n]["type"]:
            unknown.append(n)
            continue
        if rows:
            matches = [r["kind"] for r in rows if r["slides"][0] <= n <= r["slides"][1]]
            if len(matches) != 1 or not matches[0].startswith("이론" if is_theory else "실습"):
                unknown.append(n)
                continue
        known += is_theory
    review = " (정규 온라인 같은 편성의 D-1 재설계 검토)" if online and known + len(unknown) < 50 else ""
    if unknown or misplaced:
        count = f"{known}~{known + len(unknown)}" if unknown else str(known)
        reason = []
        if unknown:
            reason.append(f"역할 미확인 {sorted(unknown)}")
        if misplaced:
            reason.append(f"D-2 자리 확인 {misplaced}")
        return f"이론 본문 {count}장 ({' · '.join(reason)}){review}"
    return f"이론 본문 {known}장{review}"


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("output", metavar="출력.json")
parser.add_argument("keys", nargs="+", metavar="덱키")
parser.add_argument("--오프라인", action="store_true", dest="offline")
args = parser.parse_args()
k = None if args.offline else load_coef()
out = {}
for name in args.keys:
    m = re.fullmatch(r"(통합|실전)(\d+)", name)
    if not m:
        sys.exit(f"{name}: 덱키는 통합3 · 실전10 꼴이다")
    c, dk = COURSE[m[1]]; nn = f"{int(m[2]):02d}"
    md = W / (f"제작도구/오프라인/decks/{dk}/off{nn}/{c}_오프라인_{nn}회차.md" if args.offline
              else f"제작도구/온라인/decks/{dk}/day{nn}/{c}_{nn}일차.md")
    sd = W / f"산출물/{c}/이론/{nn}회차/대본"
    cfg = W / f"제작도구/구성/{c}/{nn}회차/구성.json"
    rows = json.loads(cfg.read_text(encoding="utf-8")).get("rows", []) if not args.offline and cfg.is_file() else []
    if not md.is_file():
        sys.exit(f"{md}: 덱 원고가 없다")
    parts = re.split(r"(?m)^## SLIDE (\d+) — (.*)$", md.read_text(encoding="utf-8"))
    review_number = (len(parts) - 1) // 3 - 6  # D-2의 복습 뒤에는 용어·퀴즈·정답 여섯 장이 온다.
    slides = {}; sections = {}; review_marked = False
    for i in range(1, len(parts), 3):
        n = int(parts[i]); title = parts[i + 1].strip(); body = parts[i + 2]
        if n in slides:
            sys.exit(f"{name}: 장 번호 {n} 중복")
        ty = re.search(r"(?m)^- 유형:[ \t]*(.+)$", body); lay = re.search(r"(?m)^레이아웃:\s*(.+)$", body); msg = re.search(r"(?m)^- 메시지:\s*(.+)$", body); fig = re.search(r"(?m)^- 그림:\s*(.+)$", body)
        slides[n] = dict(title=title, type=ty.group(1).strip() if ty else "", layout=lay.group(1).strip() if lay else "", msg=msg.group(1).strip() if msg else "", fig=fig.group(1).strip() if fig else "", sec=None, file="")
        if ty and ty.group(1).strip() == "간지":
            kind = re.search(r"(?m)^- 구분:[ \t]*(.+)$", body)
            sections[n] = kind.group(1).strip() if kind else ""
        if n == review_number:
            review_marked = title.startswith("복습:") or bool(re.search(r"(?:^|[ /·])복습(?: 장| 자리| 한 장|[(:：])", body, re.M))
            if not review_marked and not args.offline:
                review_marked = script_marks_review(sd, n, title)
            if not review_marked and args.offline:
                plan = md.with_name("구성.json")
                items = json.loads(plan.read_text(encoding="utf-8")).get("slides", []) if plan.is_file() else []
                item = items[n - 1] if 0 < n <= len(items) else {}
                src = re.fullmatch(r"(integrated|practical)/day(\d{2})", item.get("src", ""))
                if src and "n" in item:
                    source_course = "통합반" if src[1] == "integrated" else "실전반"
                    source_scripts = W / f"산출물/{source_course}/이론/{src[2]}회차/대본"
                    review_marked = script_marks_review(source_scripts, item["n"], title)
    out[name] = slides
    print(name, f"전체 {len(slides)}장 ·", theory_count(slides, sections, rows, not args.offline, review_marked))
    if args.offline:
        continue
    cover = set()
    for f in sorted(sd.glob("*.md")):
        for n, (text, share, title) in script_slides(f.read_text(encoding="utf-8")).items():
            s = slide_seconds(text, k) / share if share > 1 else slide_seconds(text, k)
            if n in slides:
                slides[n]["sec"] = round(s, 1); slides[n]["file"] = f.name[:2]
            cover.add(n)
    miss = [n for n in slides if n not in cover]; extra = [n for n in cover if n not in slides]
    tot = sum(v["sec"] or 0 for v in slides.values())
    print(name, len(slides), "장", round(tot / 60, 1), "분 대본미덮음", miss, "덱에없음", extra)
    print("  2분초과", [(n, v["sec"]) for n, v in slides.items() if (v["sec"] or 0) >= 120])
    print("  유형분포", {ty: sum(1 for v in slides.values() if v["type"] == ty) for ty in sorted({v["type"] for v in slides.values()})})
with open(args.output, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=0)
