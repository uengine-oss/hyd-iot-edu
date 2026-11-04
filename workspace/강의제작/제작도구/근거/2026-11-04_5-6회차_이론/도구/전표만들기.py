"""5 · 6회차 이론(덱 · 대본 · 오프라인 덱) 인수전표.json(schema 2)을 판정 파일 · 지침 틀 · 산출물 해시로 조립한다. 저장소 루트에서: python3 workspace/강의제작/제작도구/근거/2026-11-04_5-6회차_이론/도구/전표만들기.py
- 판정: 판정/<덱키>.json(덱 · 대본, 검토-<덱키>), 판정/오<N><과정>.json(오프라인 덱), 영상은 이 일의 범위 밖.
- 감독이 채우는 칸: 판정/감독확인.json {"<산출물 id>": {"<기준 id>": {"status","reason","evidence":[{"path","locator"}]}}} — 고친 뒤 · 게시 뒤 확인.
- row_sha256은 지금 지침에서 `인수검사.py --틀`과 같은 식으로, 근거 sha256은 지금 파일에서 계산한다(없는 근거 파일이면 멈춘다).
"""
import hashlib, importlib.util, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
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


WORK = "작업/2026-11-04_5-6회차-이론/"   # 검토 때의 작업 폴더 — 근거는 이 폴더(근거/2026-11-04_5-6회차_이론/)로 옮겼다
HERE = W.relative_to(ROOT).as_posix() + "/"


def moved(e):
    """작업 폴더 경로를 근거 폴더로 바꾼다. 커밋하지 않은 렌더 그림 · 고치기 전 사본은 그 해시 목록 파일을 근거로 단다."""
    p = str(e["path"])
    if not p.startswith(WORK): return e
    if "/렌더/" in p: return dict(e, path=HERE + "판정/렌더_미리보기_해시.txt", locator=f"{p[len(WORK):]} · {e.get('locator', '')}")
    if "/변경전/" in p: return dict(e, path=HERE + "판정/변경전_해시.txt", locator=f"{p[len(WORK):]} · {e.get('locator', '')}")
    return dict(e, path=HERE + p[len(WORK):])


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


ROWS = {g: rows(g) for g in ("덱.md", "대본.md")}
ON = {"온5통합": ("통합반", "05", "integrated/day05/통합반_05일차.md"), "온6통합": ("통합반", "06", "integrated/day06/통합반_06일차.md"),
      "온5실전": ("실전반", "05", "practical/day05/실전반_05일차.md"), "온6실전": ("실전반", "06", "practical/day06/실전반_06일차.md")}
OFF = {"오5통합": ("통합반", "05", "integrated/off05"), "오6통합": ("통합반", "06", "integrated/off06"),
       "오6실전": ("실전반", "06", "practical/off06"), "오7실전": ("실전반", "07", "practical/off07")}
override = json.loads((W / "판정/감독확인.json").read_text(encoding="utf-8")) if (W / "판정/감독확인.json").exists() else {}


def crit(items, g, aid):
    out, seen = [], set()
    for x in items:
        if x["id"] not in ROWS[g]: sys.exit(f"{aid}: {x['id']}는 지금 {g}에 없는 행")
        o = override.get(aid, {}).get(x["id"])
        y = dict(x, **o) if o else dict(x)
        y["row_sha256"] = ROWS[g][x["id"]]
        y["evidence"] = [ev(moved(dict(e, path=q.strip()))) for e in y.get("evidence", []) for q in str(e["path"]).split(" · ")]   # 검토자가 한 칸에 여러 경로를 「 · 」로 이은 근거는 나눠 단다
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
    authors = [f"작업자-온라인-{key}"]
    byk = {k.rsplit("-", 1)[1]: v for k, v in d["artifacts"].items()}   # 검토자가 쓴 이름(05 · 5)과 상관없이 덱 · 대본노트로 고른다
    for kind, g, files in (("덱", "덱.md", [pptx, deck] + comp), ("대본노트", "대본.md", scripts + [deck, pptx])):
        aid = f"{course}-온라인-{int(nn)}-{kind}"
        items = byk[kind]
        arts.append({"id": aid, "guideline": {"path": G + g}, "files": [{"path": f, "sha256": sha(f)} for f in files],
                     "authors": authors, "reviewer": f"{d['reviewer']} · 고친 항목은 감독 확인", "criteria": crit(items, g, aid)})
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
