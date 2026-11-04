"""이론 산출물(덱 · 대본노트 · 영상 · 오프라인 덱)의 인수전표.json(schema 3)을 판정 파일 · 지침 틀 · 산출물 해시로 조립한다.

    PYTHONUTF8=1 .venv314/Scripts/python.exe workspace/강의제작/제작도구/검사/전표만들기.py <작업 폴더>
        [--온라인 키=과정:회차 ...] [--오프라인 키=과정:회차 ...] [--옛폴더 옛경로=새경로] [--출력 경로]
    예: … 전표만들기.py 작업/2026-11-04_7회차 --온라인 통합7=통합반:07 실전5=실전반:05 --오프라인 오7통합=통합반:07

<작업 폴더>/판정/ 의 재료:
- <키>.json: {"reviewer", "artifacts": {"<산출물 id>-덱": [기준...], "<산출물 id>-대본노트": [기준...]}, "더한 작성자"(선택)}. 온라인 키마다 덱 · 대본노트 산출물 둘이 된다.
- 오프라인 <키>.json: {"reviewer", "artifacts": {"<아무 이름>": [기준...]}}. 덱 산출물 하나가 된다.
- 영상_<키>.json(있으면 이론 영상 산출물을 더한다): {"reviewer", "criteria": [기준...], "kind"(선택 — 인수검사 머리말)}.
- 감독확인.json(선택): {"<산출물 id>": {"<기준 id>": {"status","reason","evidence":[{"path","locator"}]}}} — 고친 뒤 · 게시 뒤 확인이 판정을 덮는다.
- 근거경로.json(선택): {"옛 근거 경로": "지금 경로"}.
기준 하나는 {"id","status","reason","evidence":[{"path","locator"}]}이고 그 지침의 행과 공통.md에서 그 지침에 드는 행이 전부 있어야 한다(`인수검사.py --틀`이 그 목록이다).
row_sha256은 지금 지침에서, 근거 sha256은 지금 파일에서 계산한다. 지침에 없는 행, 빠진 행, 없는 근거 파일은 멈춘다.
근거 칸 처리: 위치를 비운 근거는 「파일 전체」, 한 칸에 「 · 」로 이은 경로는 나눠 달고, 폴더는 그 안 파일 목록 · 해시를 적은 판정/폴더근거/ 파일로 바꾼다.
--옛폴더: 일을 닫으며 작업 폴더를 옮긴 뒤 조립할 때 쓴다. 옛경로 아래 근거를 새경로로 바꾸고, 올리지 않은 렌더 그림 · 고치기 전 사본은 새경로/판정의 해시 목록(렌더_미리보기_해시.txt · 변경전_해시.txt)을 근거로 단다.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

from 인수검사 import ROOT, criteria_of

G = "workspace/강의제작/지침/"
S = "workspace/강의제작/산출물/"
C = "workspace/강의제작/제작도구/"
FOLDER = {"통합반": "integrated", "실전반": "practical"}


def sha(p):
    f = ROOT / p
    if not f.is_file():
        sys.exit(f"근거 · 파일 없음: {p}")
    return hashlib.sha256(f.read_bytes()).hexdigest()


def pairs(values, label):
    """키=과정:회차 → {키: (과정, 회차)}."""
    out = {}
    for value in values or []:
        key, _, rest = value.partition("=")
        course, _, nn = rest.partition(":")
        if not key or course not in FOLDER or not nn.isdigit():
            sys.exit(f"{label} 「{value}」: 키=과정:회차 꼴이 아님(과정은 {sorted(FOLDER)})")
        out[key] = (course, nn.zfill(2))
    return out


def read_json(path, default=None):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    if default is None:
        sys.exit(f"판정 파일 없음: {path}")
    return default


class Builder:
    def __init__(self, work, old, new):
        self.work, self.old, self.new = work, old, new
        self.moved_paths = read_json(work / "판정/근거경로.json", {})
        self.override = read_json(work / "판정/감독확인.json", {})
        self.list_dir = work / "판정/폴더근거"
        self.rows = {}

    def rows_of(self, guide, kinds):
        key = (guide, tuple(kinds or ()))
        if key not in self.rows:
            rows, problems = criteria_of(ROOT / G / guide, ROOT, kinds)
            if problems:
                sys.exit(f"{guide}: " + "; ".join(problems))
            self.rows[key] = rows
        return self.rows[key]

    def moved(self, e):
        p = str(e["path"])
        if not self.old or not p.startswith(self.old):
            return e
        tail = p[len(self.old):]
        if "/렌더/" in p:
            return dict(e, path=self.new + "판정/렌더_미리보기_해시.txt", locator=f"{tail} · {e.get('locator', '')}")
        if "/변경전/" in p:
            return dict(e, path=self.new + "판정/변경전_해시.txt", locator=f"{tail} · {e.get('locator', '')}")
        return dict(e, path=self.new + tail)

    def evidence(self, e):
        if not str(e.get("locator") or "").strip():
            e = dict(e, locator="파일 전체")
        p = self.moved_paths.get(e["path"], e["path"]).rstrip("/")
        p = self.moved_paths.get(p, p)
        d = Path(p) if Path(p).is_absolute() else ROOT / p
        if d.is_dir():
            self.list_dir.mkdir(parents=True, exist_ok=True)
            lines = [f"{hashlib.sha256(x.read_bytes()).hexdigest()}  {x.relative_to(d).as_posix()}" for x in sorted(d.rglob("*")) if x.is_file()]
            name = self.list_dir / (hashlib.sha1(p.encode()).hexdigest()[:12] + ".txt")
            name.write_text(f"# 폴더 근거: {p}\n" + "\n".join(lines) + "\n", encoding="utf-8")
            rel = name.relative_to(ROOT).as_posix()
            return dict(e, path=rel, locator=f"폴더 {p} · {e.get('locator', '')}", sha256=sha(rel))
        if Path(p).is_absolute():
            if not d.is_file():
                sys.exit(f"근거 · 파일 없음: {p}")
            return dict(e, path=p, sha256=hashlib.sha256(d.read_bytes()).hexdigest())
        return dict(e, path=p, sha256=sha(p))

    def criteria(self, items, guide, aid, kinds=None):
        rows = self.rows_of(guide, kinds)
        out, seen = [], set()
        for x in items:
            if x["id"] not in rows:
                sys.exit(f"{aid}: {x['id']}는 지금 {guide} · 공통.md(그 지침에 드는 절)에 없는 행" + (f"(종류 {kinds})" if kinds else ""))
            y = dict(x, **self.override.get(aid, {}).get(x["id"], {}))
            y["row_sha256"] = rows[x["id"]]
            y["evidence"] = [self.evidence(self.moved(dict(e, path=q.strip()))) for e in y.get("evidence", []) for q in str(e["path"]).split(" · ")]
            out.append(y)
            seen.add(x["id"])
        missing = set(rows) - seen
        if missing:
            sys.exit(f"{aid}: {guide} · 공통.md 행이 빠짐 {sorted(missing)[:10]} 등 {len(missing)}개 — `인수검사.py --틀`의 전 행을 판정한다")
        return out

    def artifact(self, aid, guide, files, authors, reviewer, items, kinds=None):
        art = {"id": aid, "guideline": {"path": G + guide}}
        if kinds:
            art["kind"] = kinds
        art.update({"files": [{"path": f, "sha256": sha(f)} for f in files], "authors": authors, "reviewer": reviewer,
                    "criteria": self.criteria(items, guide, aid, kinds)})
        return art

    def online(self, key, course, nn):
        d = read_json(self.work / f"판정/{key}.json")
        deck = f"{C}온라인/decks/{FOLDER[course]}/day{nn}/{course}_{nn}일차.md"
        pptx = f"{S}{course}/이론/{nn}회차/{course}_{nn}일차.pptx"
        scripts = sorted(f"{S}{course}/이론/{nn}회차/대본/{p.name}" for p in (ROOT / S / course / "이론" / f"{nn}회차" / "대본").glob("*.md"))
        comp = [f"{C}구성/{course}/{nn}회차/구성.json", f"{C}구성/{course}/{nn}회차/구성표.md"]
        authors = [f"작업자-온라인-{key}"] + d.get("더한 작성자", [])
        by_kind = {k.rsplit("-", 1)[1]: v for k, v in d["artifacts"].items()}   # 검토자가 쓴 이름(05 · 5)과 상관없이 덱 · 대본노트로 고른다
        arts = []
        for kind, guide, files in (("덱", "덱.md", [pptx, deck] + comp), ("대본노트", "대본.md", scripts + [deck, pptx])):
            if kind not in by_kind:
                sys.exit(f"판정/{key}.json: artifacts에 「…-{kind}」가 없음 — 있는 것 {sorted(d['artifacts'])}")
            arts.append(self.artifact(f"{course}-온라인-{int(nn)}-{kind}", guide, files, authors, f"{d['reviewer']} · 고친 항목은 감독 확인", by_kind[kind]))
        video = self.work / f"판정/영상_{key}.json"
        if video.exists():
            arts.append(self.video(read_json(video), key, course, nn))
        return arts

    def video(self, d, key, course, nn):
        files = []
        for p in sorted((ROOT / S / "영상" / course).glob(f"{course}_{nn}회차_0*_이론_*.mp4")):
            files += [f"{S}영상/{course}/{p.name}", f"{S}영상/_작업/영상_자막_기록/{p.stem}.srt", f"{S}영상/_작업/영상_자막_기록/{p.stem}_시간표.md",
                      f"{C}구성/{course}/{nn}회차/강조_{p.stem}.json"]
        kinds = d.get("kind")
        kinds = [kinds] if isinstance(kinds, str) else kinds
        return self.artifact(f"{course}-온라인-{int(nn)}-영상", "영상.md", files, ["감독(합성 · 강조)", f"작업자-강조-{key}"], d["reviewer"], d["criteria"], kinds)

    def offline(self, key, course, nn):
        d = read_json(self.work / f"판정/{key}.json")
        if len(d["artifacts"]) != 1:
            sys.exit(f"판정/{key}.json: 오프라인 판정의 artifacts는 하나여야 한다 — {sorted(d['artifacts'])}")
        items = next(iter(d["artifacts"].values()))
        pptx = f"{S}{course}/이론_오프라인/{nn}회차/{course}_오프라인_{nn}회차.pptx"
        md = f"{C}오프라인/decks/{FOLDER[course]}/off{nn}/{course}_오프라인_{nn}회차.md"
        return self.artifact(f"{course}-오프라인-{int(nn)}-덱", "덱.md", [pptx, md], [f"작업자-오프라인-{course}"], f"{d['reviewer']} · 고친 항목은 감독 확인", items)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("work", metavar="작업폴더")
    ap.add_argument("--온라인", dest="online", nargs="*", metavar="키=과정:회차")
    ap.add_argument("--오프라인", dest="offline", nargs="*", metavar="키=과정:회차")
    ap.add_argument("--옛폴더", dest="old", metavar="옛경로=새경로")
    ap.add_argument("--출력", dest="out", help="기본 <작업 폴더>/인수전표.json")
    a = ap.parse_args()
    work = Path(a.work).resolve()
    if not work.is_relative_to(ROOT) or not (work / "판정").is_dir():
        sys.exit(f"작업 폴더 {a.work}: 저장소 안에 있고 판정/ 폴더가 있어야 한다")
    old, new = "", ""
    if a.old:
        old, _, new = a.old.partition("=")
        if not old or not new:
            sys.exit(f"--옛폴더 「{a.old}」: 옛경로=새경로 꼴이 아님")
        old, new = old.rstrip("/") + "/", new.rstrip("/") + "/"
    online, offline = pairs(a.online, "--온라인"), pairs(a.offline, "--오프라인")
    if not online and not offline:
        sys.exit("--온라인 · --오프라인 중 하나는 있어야 한다")
    b = Builder(work, old, new)
    arts = [art for key, (course, nn) in online.items() for art in b.online(key, course, nn)]
    arts += [b.offline(key, course, nn) for key, (course, nn) in offline.items()]
    out = Path(a.out) if a.out else work / "인수전표.json"
    out.write_text(json.dumps({"schema_version": 3, "required_artifacts": [x["id"] for x in arts], "artifacts": arts}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{out} · 산출물 {len(arts)}개")


if __name__ == "__main__":
    main()
