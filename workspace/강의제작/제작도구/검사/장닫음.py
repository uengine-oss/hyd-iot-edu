"""이론 덱의 닫힌 장 장부 — 검토자가 통과를 준 장을 내용 해시(화면 · 노트 · 그 장 대본 낭독)로 적고(명령 이름은 `닫음` — 사용자 확정이 아니다), 닫히지 않은 장만 뽑는다. 장 번호가 밀려도 내용이 같으면 닫힌 그대로. 대본이 모든 장을 덮어야 돈다.
실라버스·사실표·지침은 해시에 들어가지 않는다. 개편이나 상위 자료가 바뀐 일은 hyd-task 0-5대로 영향받는 장을 더한다.
언제: 고칠 장을 고를 때 · 영상 일 전 확인(상태)과 대본 단원 검토에서 통과한 장을 적을 때(닫음).
명령: <py> workspace/강의제작/제작도구/검사/장닫음.py <통합반|실전반> <NN> 상태 [--오프라인]
      <py> workspace/강의제작/제작도구/검사/장닫음.py <통합반|실전반> <NN> 닫음 --검토자 이름 (--전부 | --장 1-5,9) [--오프라인]
장부: 제작도구/구성/<과정>/NN회차/장닫음.json(오프라인은 장닫음_오프라인.json).
"""
import argparse, hashlib, json, posixpath, re, sys, zipfile
from pathlib import Path
from lxml import etree

ROOT = Path(__file__).resolve().parents[4]
W = ROOT / "workspace/강의제작"
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
PR = "{http://schemas.openxmlformats.org/package/2006/relationships}"


def sha(b):
    return hashlib.sha256(b).hexdigest()


def rels(z, part):
    d, f = posixpath.split(part)
    name = f"{d}/_rels/{f}.rels"
    if name not in z.namelist():
        return {}
    return {r.get("Id"): (r.get("Type").rsplit("/", 1)[-1], posixpath.normpath(posixpath.join(d, r.get("Target"))))
            for r in etree.fromstring(z.read(name)).iter(PR + "Relationship") if r.get("TargetMode") != "External"}


def screen_hash(z, part, n):
    """쪽 번호 글자는 장을 끼우면 저절로 바뀌므로 뺀다. rId는 파트마다 달라지므로 그림 바이트로 잰다."""
    root = etree.fromstring(z.read(part))
    numbers = [t for t in root.iter(A + "t") if (t.text or "").strip() == str(n)]
    if numbers:
        numbers[-1].text = ""
    rel = rels(z, part)
    body = re.sub(rb'r:(embed|link|id)="[^"]+"', b"", etree.tostring(root, method="c14n"))
    media = sorted(sha(z.read(t)) for k, t in rel.values() if k in ("image", "media", "audio", "video"))
    return sha(body + "".join(media).encode())


def note_text(z, part):
    for kind, target in rels(z, part).values():
        if kind == "notesSlide":
            root = etree.fromstring(z.read(target))
            lines = []
            for sp in root.iter(P + "sp"):
                ph = sp.find(f"{P}nvSpPr/{P}nvPr/{P}ph")
                if ph is not None and ph.get("type") == "body":
                    lines.append("\n".join("".join(t.text or "" for t in p.iter(A + "t")) for p in sp.iter(A + "p")))
            return "\n".join(lines)
    return ""


def script_text(folder):
    """강의영상.py가 낭독하는 글과 같은 기준으로 장마다 대본을 모은다."""
    out = {}
    for f in sorted(folder.glob("*.md")) if folder else []:
        parts = re.split(r"^## \[SLIDE ([0-9~]+)\].*$", f.read_text("utf8"), flags=re.M)
        for i in range(1, len(parts), 2):
            first, last = int(parts[i].split("~")[0]), int(parts[i].split("~")[-1])
            t = re.split(r"^#{1,2} ", parts[i + 1], flags=re.M)[0]
            t = re.sub(r"^---\s*$|^>.*$|^\|.*$", "", t, flags=re.M).replace("**", "").strip()
            for n in range(first, last + 1):
                out[n] = t
    return out


def read_deck(pptx, folder):
    z = zipfile.ZipFile(pptx)
    rel = rels(z, "ppt/presentation.xml")
    ids = etree.fromstring(z.read("ppt/presentation.xml")).find(P + "sldIdLst")
    scripts = script_text(folder)
    deck = {}
    for n, s in enumerate(ids, 1):
        part = rel[s.get(R + "id")][1]
        deck[n] = sha("\n".join([screen_hash(z, part, n), note_text(z, part), scripts.get(n, "")]).encode())
    if folder and (missing := [n for n in deck if n not in scripts]):
        sys.exit(f"장닫음: 대본이 덮지 않는 장 {missing} ({folder})")
    return deck


def paths(a):
    base = W / "산출물" / a.과정
    if a.오프라인:
        pptx = base / "이론_오프라인" / f"{a.회차}회차" / f"{a.과정}_오프라인_{a.회차}회차.pptx"
        folder, name = None, "장닫음_오프라인.json"
    else:
        pptx = base / "이론" / f"{a.회차}회차" / f"{a.과정}_{a.회차}일차.pptx"
        folder, name = base / "이론" / f"{a.회차}회차" / "대본", "장닫음.json"
    return (Path(a.pptx) if a.pptx else pptx), (Path(a.대본) if a.대본 else folder), \
        (Path(a.장부) if a.장부 else W / "제작도구/구성" / a.과정 / f"{a.회차}회차" / name)


def pick(spec, deck):
    out = set()
    for piece in spec.split(","):
        lo, _, hi = piece.partition("-")
        out |= set(range(int(lo), int(hi or lo) + 1))
    if bad := sorted(out - set(deck)):
        sys.exit(f"장닫음: 덱에 없는 장 {bad}")
    return sorted(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("과정"); ap.add_argument("회차"); ap.add_argument("일", choices=["상태", "닫음"])
    ap.add_argument("--오프라인", action="store_true"); ap.add_argument("--검토자"); ap.add_argument("--전부", action="store_true")
    ap.add_argument("--장"); ap.add_argument("--pptx"); ap.add_argument("--대본"); ap.add_argument("--장부")
    a = ap.parse_args()
    pptx, folder, book = paths(a)
    deck = read_deck(pptx, folder)
    done = json.loads(book.read_text("utf8")) if book.exists() else {}
    if a.일 == "닫음":
        if not a.검토자 or a.전부 == bool(a.장):
            sys.exit("장닫음: 닫음에는 --검토자와, --전부 또는 --장 하나가 필요하다")
        for n in (sorted(deck) if a.전부 else pick(a.장, deck)):
            done[deck[n]] = a.검토자
        book.parent.mkdir(parents=True, exist_ok=True)
        book.write_text(json.dumps(dict(sorted(done.items())), ensure_ascii=False, indent=0) + "\n", "utf8", newline="")
    todo = [n for n, h in deck.items() if h not in done]
    print(f"{pptx.name}: {len(deck)}장 · 닫힘 {len(deck) - len(todo)} · 볼 장 {len(todo)}")
    if todo:
        print("볼 장:", ",".join(map(str, todo)))


if __name__ == "__main__":
    main()
