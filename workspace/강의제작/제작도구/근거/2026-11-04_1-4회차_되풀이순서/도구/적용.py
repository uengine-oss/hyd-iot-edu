"""점검 목록을 대본 · 덱 노트에 적용하고 고침 기록을 쓴다. 판단은 하지 않는다 — 찾지 못하면 좌표와 함께 실패한다.

  python 적용.py 묶기 <과정> <NN>                     작업자가 볼 입력(걸린 장 + 앞뒤 경계 문단)을 만든다
  python 적용.py 시험 <과정> <NN>                     쓰지 않고 판정대로 적용되는지만 본다
  python 적용.py 실행 <과정> <NN>                     적용하고 고침기록/<과정>_<NN>.md 를 쓴다
  python 적용.py 실행 실전반 01 --목록 통합반_01 --대본만   같은 판정을 다른 과정 대본에 적용(공통 1회차)

입력: 점검/<과정>_<NN>.json, 판정/<과정>_<NN>.json
판정 꼴: {"판정":{"T3-01":{"처리":"적용"}, "T3-02":{"처리":"수정","후":"…","노트후":"…","까닭":"…"},
                  "T3-03":{"처리":"보류","까닭":"…"}, "T3-04":{"처리":"포함","대상":"T3-03"}},
          "노트추가":[{"장":14,"노트전":"…","노트후":"…","까닭":"…"}]}
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
W = HERE.parent
ROOT = W.parents[1]
DECK = {"통합반": "integrated", "실전반": "practical"}
ap = argparse.ArgumentParser()
ap.add_argument("일", choices=["묶기", "시험", "실행"])
ap.add_argument("과정")
ap.add_argument("회차")
ap.add_argument("--목록")
ap.add_argument("--대본만", action="store_true")
a = ap.parse_args()
name = a.목록 or f"{a.과정}_{a.회차}"
src = json.loads((W / "점검" / f"{name}.json").read_text("utf8"))
script_dir = ROOT / f"workspace/강의제작/산출물/{a.과정}/이론/{a.회차}회차/대본"
deck_md = ROOT / f"workspace/강의제작/제작도구/온라인/decks/{DECK[a.과정]}/day{a.회차}/{a.과정}_{a.회차}일차.md"
BLOCK = re.compile(r"^## \[SLIDE (\d+)(?:~(\d+))?\].*$", re.M)


def script_blocks(text):
    """(시작, 끝, a, b) 구획 범위. 끝은 다음 # 제목 또는 파일 끝."""
    out = []
    for m in BLOCK.finditer(text):
        nx = re.compile(r"^#", re.M).search(text, m.end())
        out.append((m.end(), nx.start() if nx else len(text), int(m.group(1)), int(m.group(2) or m.group(1))))
    return out


def replace_in_block(text, slide, old, new, tag):
    nl = "\r\n" if "\r\n" in text else "\n"
    old_n, new_n = old.replace("\r\n", "\n").replace("\n", nl), new.replace("\r\n", "\n").replace("\n", nl)
    hits = [b for b in script_blocks(text) if b[2] <= slide <= b[3]]
    if len(hits) != 1:
        raise ValueError(f"{tag}: 장 {slide} 구획이 {len(hits)}개")
    s, e, *_ = hits[0]
    body = text[s:e]
    if body.count(old_n) != 1:
        raise ValueError(f"{tag}: 장 {slide}에서 「{old[:50]}…」가 {body.count(old_n)}번 찾아진다")
    return text[:s] + body.replace(old_n, new_n, 1) + text[e:]


def note_replace(deck, slide, old, new, tag):
    m = re.search(rf"^## SLIDE 0*{slide} — .*?(?=^## SLIDE |\Z)", deck, re.M | re.S)
    if not m:
        raise ValueError(f"{tag}: 덱에 장 {slide}가 없다")
    block = m.group(0)
    nm = re.search(r"^- 노트:.*$", block, re.M)
    if not nm or nm.group(0).count(old) != 1:
        raise ValueError(f"{tag}: 장 {slide} 노트에서 「{old[:50]}…」가 {nm.group(0).count(old) if nm else 0}번 찾아진다")
    if "\n" in new:
        raise ValueError(f"{tag}: 노트후에 줄바꿈이 있다(노트는 한 줄)")
    return deck[: m.start() + nm.start()] + nm.group(0).replace(old, new, 1) + deck[m.start() + nm.end():]


def bundle():
    """걸린 장 전체 + 앞 장 끝 문단 + 다음 장 첫 문단."""
    inp = (W / "입력" / f"{name}.md").read_text("utf8")
    parts = re.split(r"(?m)^=====\n", inp)[1:]
    meta = []
    for p in parts:
        h = re.match(r"# 장 (\d+)(?:~(\d+))?", p)
        meta.append((int(h.group(1)), int(h.group(2) or h.group(1)), p))
    touched = {}
    for it in src["고칠것"]:
        touched.setdefault(it["장"], []).append(it)
    out = [f"# 작업 입력 — {name}\n"]
    for i, (x, y, p) in enumerate(meta):
        items = [it for s in range(x, y + 1) for it in touched.get(s, [])]
        if not items:
            continue
        if i:
            lines = [l for l in meta[i - 1][2].split("[낭독]")[-1].splitlines() if l.startswith("L")]
            out.append(f"\n----- 앞 장({meta[i-1][0]}) 끝 문단: {lines[-1] if lines else ''}")
        out.append("\n" + p.rstrip())
        if i + 1 < len(meta):
            lines = [l for l in meta[i + 1][2].split("[낭독]")[-1].splitlines() if l.startswith("L")]
            out.append(f"----- 다음 장({meta[i+1][0]}) 첫 문단: {lines[0] if lines else ''}")
        out.append("\n>>> 이 장의 고칠 항목")
        for it in items:
            out.append(json.dumps({k: it.get(k) for k in ("번호", "종류", "파일", "줄", "어긋남", "근거", "고침", "전", "후", "노트전", "노트후", "글자증감")}, ensure_ascii=False))
    p = W / "입력" / f"작업_{name}.md"
    p.write_text("\n".join(out), "utf8", newline="\n")
    print(p, p.stat().st_size, "항목", len(src["고칠것"]))


def apply(write):
    jd = json.loads((W / "판정" / f"{name}.json").read_text("utf8"))
    verdict = jd["판정"]
    files = {p.name: p.read_bytes().decode("utf8") for p in script_dir.glob("*.md")}
    deck = deck_md.read_bytes().decode("utf8")
    errs, rec, ct = [], [], {"적용": 0, "수정": 0, "보류": 0, "포함": 0}
    missing = [it["번호"] for it in src["고칠것"] if it["번호"] not in verdict]
    if missing:
        sys.exit(f"{name}: 판정 없는 항목 {missing}")
    for it in src["고칠것"]:
        v = verdict[it["번호"]]
        kind = v["처리"]
        ct[kind] += 1
        if kind in ("보류", "포함"):
            rec.append(f"| {it['번호']} | {it['장']} | {kind} | {it['어긋남']} | {v.get('까닭') or v.get('대상')} |  |  |")
            continue
        after = v.get("후", it.get("후") or "")
        note_after = v.get("노트후", it.get("노트후") or "")
        try:
            if it.get("전"):
                if it["파일"] not in files:
                    raise ValueError(f"{it['번호']}: 파일 {it['파일']} 없음")
                files[it["파일"]] = replace_in_block(files[it["파일"]], it["장"], it["전"], after, it["번호"])
            if it.get("노트전") and not a.대본만:
                deck = note_replace(deck, it["장"], it["노트전"], note_after, it["번호"])
        except ValueError as e:
            errs.append(str(e))
            continue
        cell = lambda s: (s or "").replace("|", "\\|").replace("\r", "").replace("\n", " / ")
        rec.append(f"| {it['번호']} | {it['파일'] if it.get('전') else '노트'} · {it['장']}장 | {it['어긋남']} | {it['근거']} | {cell(it.get('전'))} | {cell(after)} | {cell(v.get('까닭'))} |")
    if not a.대본만:
        for i, n in enumerate(jd.get("노트추가", [])):
            try:
                deck = note_replace(deck, n["장"], n["노트전"], n["노트후"], f"노트추가{i}")
                rec.append(f"| 노트추가 | 노트 · {n['장']}장 | 대본을 고쳐 노트가 어긋남 | {n.get('까닭','')} | {n['노트전']} | {n['노트후']} |  |")
            except ValueError as e:
                errs.append(str(e))
    print(name, ct, "실패", len(errs))
    for e in errs:
        print(" ", e)
    if errs:
        sys.exit(1)
    if write:
        for n, t in files.items():
            (script_dir / n).write_bytes(t.encode("utf8"))
        if not a.대본만:
            deck_md.write_bytes(deck.encode("utf8"))
        out = W / "고침기록"
        out.mkdir(exist_ok=True)
        (out / f"{a.과정}_{a.회차}.md").write_text(
            f"# 고침 기록 — {a.과정} {a.회차}회차(S-37 · S-76)\n\n| 번호 | 대상 | 어긋남 | 근거 | 전 | 후 | 까닭 |\n|---|---|---|---|---|---|---|\n" + "\n".join(rec) + "\n",
            "utf8", newline="\n")
        print("썼다", out / f"{a.과정}_{a.회차}.md")


if a.일 == "묶기":
    bundle()
else:
    apply(a.일 == "실행")
