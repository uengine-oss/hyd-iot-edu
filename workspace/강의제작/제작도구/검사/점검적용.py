"""되풀이 · 순서 점검 목록을 대본 · 덱 노트에 적용하고 고침 기록을 쓴다. 판단은 하지 않는다 — 찾지 못하면 좌표와 함께 실패한다.
언제: 점검자(`의뢰/의뢰_순서되풀이점검.md`)의 목록과 작업자(`의뢰/의뢰_고침.md`)의 판정이 나온 뒤. 시험으로 실패 0을 본 뒤 실행은 한 번.
명령: <py> workspace/강의제작/제작도구/검사/점검적용.py <묶기|시험|실행|정리> <작업 폴더> <과정> <NN> [--목록 통합반_01] [--대본만] [--심각만] [--루트 폴더]

  묶기    작업자가 볼 입력(걸린 장 + 앞뒤 경계 문단)을 입력/작업_<덱>.md에 만든다. 입력/<덱>.md(장묶기.py 출력)가 있어야 한다
  시험    쓰지 않고 판정대로 적용되는지만 본다
  실행    적용하고 <작업 폴더>/고침기록/<과정>_<NN>.md를 쓴다
  정리    --기준 커밋과 견줘 고치며 생긴 겹공백 · 빈 표시만 지운다(<작업 폴더>는 안 쓴다)
  --목록 통합반_01 --대본만   같은 판정을 다른 과정 대본에 적용(공통 회차)
  --심각만   목록의 심각도가 「심각」이 아닌 항목은 판정과 상관없이 보류한다(음성 전 규칙 — 의뢰 틀)
  --루트   산출물 · 원고가 있는 저장소 루트(기본 이 저장소). 시험은 사본 폴더로

입력: <작업 폴더>/점검/<덱>.json, <작업 폴더>/판정/<덱>.json, 덱 = <과정>_<NN>
판정 꼴: {"판정":{"T3-01":{"처리":"적용"}, "T3-02":{"처리":"수정","후":"…","노트후":"…","까닭":"…"},
                  "T3-03":{"처리":"보류","까닭":"…"}, "T3-04":{"처리":"포함","대상":"T3-03"}},
          "노트추가":[{"장":14,"노트전":"…","노트후":"…","까닭":"…"}]}
"""
import argparse, json, re, subprocess, sys
from pathlib import Path

DECK = {"통합반": "integrated", "실전반": "practical"}
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


def bundle(W, name, src):
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
            out.append(json.dumps({k: it.get(k) for k in ("번호", "종류", "심각도", "파일", "줄", "어긋남", "근거", "고침", "전", "후", "노트전", "노트후", "글자증감")}, ensure_ascii=False))
    p = W / "입력" / f"작업_{name}.md"
    p.write_text("\n".join(out), "utf8", newline="\n")
    print(p, p.stat().st_size, "항목", len(src["고칠것"]))


def apply(a, W, name, src, script_dir, deck_md, write):
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
        if a.serious and it.get("심각도") != "심각":
            v = {"처리": "보류", "까닭": f"심각도 {it.get('심각도') or '없음'} — 음성 전에는 심각만 고친다"}
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
            if it.get("노트전") and not a.script_only:
                deck = note_replace(deck, it["장"], it["노트전"], note_after, it["번호"])
        except ValueError as e:
            errs.append(str(e))
            continue
        cell = lambda s: (s or "").replace("|", "\\|").replace("\r", "").replace("\n", " / ")
        rec.append(f"| {it['번호']} | {it['파일'] if it.get('전') else '노트'} · {it['장']}장 | {it['어긋남']} | {it['근거']} | {cell(it.get('전'))} | {cell(after)} | {cell(v.get('까닭'))} |")
    if not a.script_only:
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
        if not a.script_only:
            deck_md.write_bytes(deck.encode("utf8"))
        out = W / "고침기록"
        out.mkdir(exist_ok=True)
        (out / f"{a.course}_{a.nn}.md").write_text(
            f"# 고침 기록 — {a.course} {a.nn}회차(S-37 · S-76)\n\n| 번호 | 대상 | 어긋남 | 근거 | 전 | 후 | 까닭 |\n|---|---|---|---|---|---|---|\n" + "\n".join(rec) + "\n",
            "utf8", newline="\n")
        print("썼다", out / f"{a.course}_{a.nn}.md")


def tidy(root, course, nn, base):
    """고치며 생긴 찌꺼기만 정리: 낭독 줄의 겹공백 · 줄끝 공백, 3줄 이상 빈 줄, 뒤에 낭독 없는 빈 표시(> [핵심|풀이|보충]). 기준 판에 없던 것만 건드린다."""
    top = Path(__file__).resolve().parents[4]
    for p in sorted((root / f"workspace/강의제작/산출물/{course}/이론/{nn}회차/대본").glob("*.md")):
        raw = p.read_bytes().decode("utf8"); nl = "\r\n" if "\r\n" in raw else "\n"
        rel = p.relative_to(root).as_posix()
        r = subprocess.run(["git", "show", f"{base}:{rel}"], capture_output=True, cwd=top)
        if r.returncode:
            sys.exit(f"기준 {base}에 {rel}이 없다")
        old = r.stdout.decode("utf8")
        if old == raw:
            continue
        t, o = raw.replace("\r\n", "\n"), old.replace("\r\n", "\n")
        keep = set(o.split("\n"))
        t = "\n".join(l if l in keep or l.startswith((">", "#", "|")) else re.sub(r"(?<=\S)  +(?=\S)", " ", l).strip() for l in t.split("\n"))
        t = re.sub(r"^> \[(?:핵심|풀이|보충)\]\n+(?=(?:> \[(?:핵심|풀이|보충)\]|---|#))", "", t, flags=re.M)
        if not re.search(r"\n{3,}", o):
            t = re.sub(r"\n{3,}", "\n\n", t)
        new = t.replace("\n", nl)
        if new != raw:
            p.write_bytes(new.encode("utf8")); print("정리", course, nn, p.name, "글자", len(new) - len(raw))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("일", choices=["묶기", "시험", "실행", "정리"])
    ap.add_argument("work")
    ap.add_argument("course", choices=sorted(DECK))
    ap.add_argument("nn")
    ap.add_argument("--목록", dest="list")
    ap.add_argument("--대본만", dest="script_only", action="store_true")
    ap.add_argument("--심각만", dest="serious", action="store_true")
    ap.add_argument("--기준", dest="base", help="정리가 견줄 고치기 전 커밋")
    ap.add_argument("--루트", dest="root", default=str(Path(__file__).resolve().parents[4]))
    a = ap.parse_args()
    W, root = Path(a.work), Path(a.root)
    if a.일 == "정리":
        if not a.base:
            ap.error("정리는 --기준이 필요하다")
        return tidy(root, a.course, a.nn, a.base)
    name = a.list or f"{a.course}_{a.nn}"
    src = json.loads((W / "점검" / f"{name}.json").read_text("utf8"))
    script_dir = root / f"workspace/강의제작/산출물/{a.course}/이론/{a.nn}회차/대본"
    deck_md = root / f"workspace/강의제작/제작도구/온라인/decks/{DECK[a.course]}/day{a.nn}/{a.course}_{a.nn}일차.md"
    if a.일 == "묶기":
        bundle(W, name, src)
    else:
        apply(a, W, name, src, script_dir, deck_md, a.일 == "실행")


if __name__ == "__main__":
    main()
