"""인수 판정 틀을 내고, 채운 판정 파일에 빠진 규칙 · 없는 규칙 · 불통과 · 미확인 · 빈 근거가 있으면 실패한다(내용 판정은 검토자 몫).
언제: 검토자에게 판정 틀을 줄 때(--틀), 완료 보고 전(--완료).
명령: <py> workspace/강의제작/제작도구/검사/인수검사.py --틀 <일> [--대상 "통합반 3회차 덱"] > <작업 폴더>/판정/<이름>.json
      <py> workspace/강의제작/제작도구/검사/인수검사.py --완료 <판정.json …> · --자가시험
일: 실라버스 · 덱 · 대본 · 영상 · 코딩랩 · 가이드. 판정 대상 = 그 일 문서 `## 반드시`의 규칙(D-n 등) + 공통.md 규칙(C-n).
판정 파일: {"일": "덱", "대상": "…", "판정": {"D-1": {"상태": "통과|불통과|해당 없음|미확인", "근거": "파일:위치 — 까닭"}}}
"""
import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

from 재편검사 import GUIDES, ROOT, WORKS, rule_ids

STATES = ("통과", "불통과", "해당 없음", "미확인")


def template(guide_dir, work, target=""):
    if work not in WORKS:
        raise ValueError(f"일 「{work}」 — {' · '.join(WORKS)} 중 하나")
    ids = rule_ids(guide_dir, work)
    if not any(i[0] != "C" for i in ids):
        raise ValueError(f"{guide_dir / (work + '.md')}: `## 반드시`에 번호 규칙이 없음")
    return {"일": work, "대상": target, "판정": {i: {"상태": "미확인", "근거": ""} for i in ids}}


def problems(guide_dir, path):
    """판정 파일 하나의 문제 목록(빈 목록 = 완료)."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        work, rows = data["일"], data["판정"]
        want = rule_ids(guide_dir, work) if work in WORKS else None
    except (OSError, ValueError, KeyError, TypeError) as e:
        return [f"{path}: 판정 파일을 읽지 못함 — {e}"]
    if want is None:
        return [f"{path}: 일 「{work}」 — {' · '.join(WORKS)} 중 하나"]
    if not isinstance(rows, dict):
        return [f"{path}: 「판정」은 {{규칙: {{상태, 근거}}}}"]
    out = [f"{path}: {i} 판정 없음" for i in want if i not in rows]
    out += [f"{path}: {i}는 지금 지침에 없는 규칙" for i in rows if i not in want]
    for i, row in rows.items():
        if i not in want:
            continue
        state = row.get("상태") if isinstance(row, dict) else None
        if state not in STATES:
            out.append(f"{path}: {i} 상태 「{state}」 — {' · '.join(STATES)}")
        elif state in ("불통과", "미확인"):
            out.append(f"{path}: {i} {state}")
        if not (isinstance(row, dict) and str(row.get("근거", "")).strip()):
            out.append(f"{path}: {i} 근거 없음(통과는 파일:위치, 해당 없음은 까닭)")
    return out


def selftest():
    tmp = Path(tempfile.mkdtemp())
    g = tmp / "지침"
    g.mkdir()
    (g / "공통.md").write_text("# 공통\n\n## 반드시\n1. **C-1. 공** — 판정: 본다\n2. **C-2. 통** — 판정: 본다\n", encoding="utf-8")
    (g / "덱.md").write_text("# 덱\n\n## 반드시\n1. **D-1. 덱** — 판정: 본다\n   세부\n2. **D-2. 둘** — 판정: 본다\n\n## 길\n1. 만든다\n", encoding="utf-8")
    (g / "대본.md").write_text("# 대본\n\n## 반드시\n\n## 길\n1. 쓴다\n", encoding="utf-8")
    cases = []
    t = template(g, "덱", "통합반 3회차 덱")
    cases.append(("틀 = 그 일 규칙 + 공통 규칙, 길 번호는 빠짐", list(t["판정"]) == ["D-1", "D-2", "C-1", "C-2"], list(t["판정"])))
    for name, args in (("없는 일", ("코딩 랩",)), ("규칙이 없는 일 문서", ("대본",))):
        try:
            template(g, *args)
            cases.append((f"틀: {name} → 실패", False, "통과함"))
        except ValueError as e:
            cases.append((f"틀: {name} → 실패", True, e))

    def judged(change=None):
        d = json.loads(json.dumps(t))
        for row in d["판정"].values():
            row.update({"상태": "통과", "근거": "a.md:1 — 맞음"})
        if change:
            change(d)
        p = tmp / "판정.json"
        p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        return problems(g, p)

    cases.append(("다 채운 판정 통과", judged() == [], judged()))
    cases.append(("해당 없음 + 까닭 통과", judged(lambda d: d["판정"]["D-2"].update({"상태": "해당 없음", "근거": "이 덱에 그림 없음"})) == [], ""))
    for name, change, expect in (
        ("규칙 빠짐", lambda d: d["판정"].pop("C-2"), "C-2 판정 없음"),
        ("없는 규칙", lambda d: d["판정"].update({"D-9": {"상태": "통과", "근거": "x"}}), "D-9는 지금 지침에 없는"),
        ("불통과", lambda d: d["판정"]["D-1"].update({"상태": "불통과"}), "D-1 불통과"),
        ("미확인", lambda d: d["판정"]["C-1"].update({"상태": "미확인"}), "C-1 미확인"),
        ("모르는 상태", lambda d: d["판정"]["C-1"].update({"상태": "대충"}), "상태 「대충」"),
        ("빈 근거", lambda d: d["판정"]["D-2"].update({"근거": " "}), "D-2 근거 없음"),
        ("일 이름 오타", lambda d: d.update({"일": "덱스"}), "일 「덱스」"),
    ):
        got = judged(change)
        cases.append((f"완료: {name} → 실패", any(expect in x for x in got), got[:2]))
    (g / "덱.md").write_text((g / "덱.md").read_text(encoding="utf-8").replace("2. **D-2. 둘** — 판정: 본다\n", "2. **D-2. 둘** — 판정: 본다\n3. **D-3. 셋** — 판정: 본다\n"), encoding="utf-8")
    cases.append(("지침에 규칙이 늘면 옛 판정은 실패", any("D-3 판정 없음" in x for x in judged()), judged()[:2]))
    shutil.rmtree(tmp)
    for name, ok, detail in cases:
        print(f"{'통과' if ok else '실패'}: {name}" + ("" if ok else f" — {detail}"))
    bad = sum(not c[1] for c in cases)
    print(f"자가시험 {len(cases)}건 · 실패 {bad}")
    return bad == 0


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--틀", dest="work", metavar="일")
    ap.add_argument("--대상", default="")
    ap.add_argument("--완료", dest="done", nargs="+", metavar="판정.json")
    ap.add_argument("--자가시험", dest="selftest", action="store_true")
    a = ap.parse_args()
    guide_dir = ROOT / GUIDES
    if a.selftest:
        return 0 if selftest() else 1
    if a.work:
        try:
            work = Path(a.work).stem if a.work.endswith(".md") else a.work   # 지침 경로로 줘도 같다
            print(json.dumps(template(guide_dir, work, a.대상), ensure_ascii=False, indent=1))
        except ValueError as e:
            sys.exit(str(e))
        return 0
    if a.done:
        found = [x for p in a.done for x in problems(guide_dir, p)]
        print("\n".join(found + [f"인수검사: 판정 파일 {len(a.done)}개 · 문제 {len(found)}"]))
        return 1 if found else 0
    ap.error("--틀 <일> · --완료 <판정.json …> · --자가시험 중 하나")


if __name__ == "__main__":
    sys.exit(main())
