"""인수전표.json(schema 2)을 판정 파일 · 지침 틀 · 산출물 해시로 조립한다. 저장소 루트에서: python3 작업/…/도구/전표만들기.py
- 판정: 판정/<덱키>.json(덱 · 대본, 검토-<덱키>), 판정/오<N><과정>.json(오프라인 덱), 판정/영상_<덱키>.json(영상, 검토-영상-<덱키>).
- 감독이 채우는 칸: 판정/감독확인.json {"<산출물 id>": {"<기준 id>": {"status","reason","evidence":[{"path","locator"}]}}} — 고친 뒤 · 게시 뒤 확인.
- row_sha256은 지금 지침에서 `인수검사.py --틀`과 같은 식으로, 근거 sha256은 지금 파일에서 계산한다(없는 근거 파일이면 멈춘다).
"""
import hashlib, importlib.util, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
W = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ik", ROOT / "workspace/강의제작/제작도구/검사/인수검사.py")
IK = importlib.util.module_from_spec(spec); spec.loader.exec_module(IK)
G = "workspace/강의제작/지침/"
S = "workspace/강의제작/산출물/"
C = "workspace/강의제작/제작도구/"


MOVED = json.loads((W / "판정/근거경로.json").read_text(encoding="utf-8")) if (W / "판정/근거경로.json").exists() else {}   # 옛 근거 경로 → 지금 경로
LIST = W / "판정/폴더근거"


def sha(p):
    f = ROOT / p
    if not f.is_file(): sys.exit(f"근거 · 파일 없음: {p}")
    return hashlib.sha256(f.read_bytes()).hexdigest()


def ev(e):
    """근거 하나: 옮겨진 경로는 지금 경로로, 폴더는 그 안 파일 목록 · 해시를 적은 근거 파일로 바꾼다."""
    if not str(e.get("locator") or "").strip(): e = dict(e, locator="파일 전체")   # 검토자가 위치를 비운 근거는 파일 전체를 본 것
    p = MOVED.get(e["path"], e["path"]).rstrip("/") if e["path"] in MOVED or e["path"].rstrip("/") in MOVED else e["path"].rstrip("/")
    p = MOVED.get(p, p)
    d = Path(p) if Path(p).is_absolute() else ROOT / p
    if d.is_dir():
        LIST.mkdir(parents=True, exist_ok=True)
        lines = [f"{hashlib.sha256(x.read_bytes()).hexdigest()}  {x.relative_to(d).as_posix()}" for x in sorted(d.rglob("*")) if x.is_file()]
        name = LIST / (hashlib.sha1(p.encode()).hexdigest()[:12] + ".txt")
        name.write_text(f"# 폴더 근거: {p}\n" + "\n".join(lines) + "\n", encoding="utf-8")
        return dict(e, path=name.relative_to(ROOT).as_posix(), locator=f"폴더 {p} · {e.get('locator', '')}", sha256=sha(name.relative_to(ROOT).as_posix()))
    if Path(p).is_absolute():
        if not d.is_file(): sys.exit(f"근거 · 파일 없음: {p}")
        return dict(e, path=p, sha256=hashlib.sha256(d.read_bytes()).hexdigest())
    return dict(e, path=p, sha256=sha(p))


def rows(g):
    return {c[0]: hashlib.sha256(" | ".join(c).encode("utf-8")).hexdigest() for _, c in IK.acceptance_rows(ROOT / G / g)}


ROWS = {g: rows(g) for g in ("덱.md", "대본.md", "영상.md")}
ON = {"통합3": ("통합반", "03", "integrated/day03/통합반_03일차.md"), "실전3": ("실전반", "03", "practical/day03/실전반_03일차.md"),
      "통합4": ("통합반", "04", "integrated/day04/통합반_04일차.md"), "실전4": ("실전반", "04", "practical/day04/실전반_04일차.md")}
OFF = {"오3통합": ("통합반", "03", "integrated/off03"), "오4통합": ("통합반", "04", "integrated/off04"), "오3실전": ("실전반", "03", "practical/off03"),
       "오4실전": ("실전반", "04", "practical/off04"), "오5실전": ("실전반", "05", "practical/off05")}
override = json.loads((W / "판정/감독확인.json").read_text(encoding="utf-8")) if (W / "판정/감독확인.json").exists() else {}


def crit(items, g, aid):
    out, seen = [], set()
    for x in items:
        if x["id"] not in ROWS[g]: sys.exit(f"{aid}: {x['id']}는 지금 {g}에 없는 행")
        o = override.get(aid, {}).get(x["id"])
        y = dict(x, **o) if o else dict(x)
        y["row_sha256"] = ROWS[g][x["id"]]
        y["evidence"] = [ev(e) for e in y.get("evidence", [])]
        out.append(y); seen.add(x["id"])
    miss = set(ROWS[g]) - seen
    if miss: sys.exit(f"{aid}: {g} 행이 빠짐 {sorted(miss)[:10]}")
    return out


arts = []
for key, (course, nn, md) in ON.items():
    d = json.loads((W / f"판정/{key}.json").read_text(encoding="utf-8"))
    deck = f"{C}온라인/decks/{md}"
    pptx = f"{S}{course}/이론/{nn}회차/{course}_{nn}일차.pptx"
    scripts = sorted(f"{S}{course}/이론/{nn}회차/대본/{p.name}" for p in (ROOT / S / course / "이론" / f"{nn}회차" / "대본").glob("*.md"))
    comp = [f"{C}구성/{course}/{nn}회차/구성.json", f"{C}구성/{course}/{nn}회차/구성표.md"]
    authors = [f"작업자-온라인-{key}"] + (["감독(57 · 69장 줄바꿈)"] if key == "실전4" else [])
    for kind, g, files in (("덱", "덱.md", [pptx, deck] + comp), ("대본노트", "대본.md", scripts + [deck, pptx])):
        aid = f"{course}-온라인-{int(nn)}-{kind}"
        items = d["artifacts"][aid]
        arts.append({"id": aid, "guideline": {"path": G + g}, "files": [{"path": f, "sha256": sha(f)} for f in files],
                     "authors": authors, "reviewer": f"{d['reviewer']} · 고친 항목은 감독 확인", "criteria": crit(items, g, aid)})
    v = W / f"판정/영상_{key}.json"
    if v.exists():
        dv = json.loads(v.read_text(encoding="utf-8"))
        aid = f"{course}-온라인-{int(nn)}-영상"
        vids = sorted((ROOT / S / "영상" / course).glob(f"{course}_{nn}회차_0*_이론_*.mp4"))
        files = []
        for p in vids:
            files += [f"{S}영상/{course}/{p.name}", f"{S}영상/_작업/영상_자막_기록/{p.stem}.srt", f"{S}영상/_작업/영상_자막_기록/{p.stem}_시간표.md",
                      f"{C}구성/{course}/{nn}회차/강조_{p.stem}.json"]
        arts.append({"id": aid, "guideline": {"path": G + "영상.md"}, "files": [{"path": f, "sha256": sha(f)} for f in files],
                     "authors": ["감독(합성 · 강조)", f"작업자-강조-{key}"], "reviewer": dv["reviewer"], "criteria": crit(dv["criteria"], "영상.md", aid)})
for key, (course, nn, folder) in OFF.items():
    d = json.loads((W / f"판정/{key}.json").read_text(encoding="utf-8"))
    (src, items), = d["artifacts"].items()
    aid = f"{course}-오프라인-{int(nn)}-덱"
    pptx = f"{S}{course}/이론_오프라인/{nn}회차/{course}_오프라인_{nn}회차.pptx"
    md = f"{C}오프라인/decks/{folder}/{course}_오프라인_{nn}회차.md"
    arts.append({"id": aid, "guideline": {"path": G + "덱.md"}, "files": [{"path": f, "sha256": sha(f)} for f in (pptx, md)],
                 "authors": [f"작업자-오프라인-{course}"], "reviewer": f"{d['reviewer']} · 고친 항목은 감독 확인", "criteria": crit(items, "덱.md", aid)})
out = {"schema_version": 2, "required_artifacts": [a["id"] for a in arts], "artifacts": arts}
(W / "인수전표.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"인수전표.json · 산출물 {len(arts)}개")
