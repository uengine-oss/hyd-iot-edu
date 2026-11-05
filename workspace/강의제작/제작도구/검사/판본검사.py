"""온라인 덱의 판본 연결을 잰다: 원고 · PPTX 장 수, 노트 일치, 대본 [SLIDE] 덮음, 구성.json slide_count · pptx_sha256, 이론 파일별 촬영 안내·본문·구성의 장 범위와 파일 순서.
언제: 덱 · 대본 · 노트를 고친 뒤 커밋 전, 굽기 전. 읽기만 한다.
명령: <py> workspace/강의제작/제작도구/검사/판본검사.py <덱키 …(통합3 실전4)>   # 전부 일치면 종료 0, 어긋나면 1
"""
import hashlib, json, posixpath, re, sys, zipfile
from pathlib import Path
from lxml import etree as E

W = Path(__file__).resolve().parents[2]   # workspace/강의제작
COURSE = {"통합": ("통합반", "integrated"), "실전": ("실전반", "practical")}
NS = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main", "a": "http://schemas.openxmlformats.org/drawingml/2006/main", "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}


def order(z):
    pres = E.fromstring(z.read("ppt/presentation.xml"))
    rels = {r.get("Id"): r.get("Target") for r in E.fromstring(z.read("ppt/_rels/presentation.xml.rels"))}
    return [posixpath.normpath("ppt/" + rels[s.get("{%s}id" % NS["r"])].lstrip("/").replace("ppt/", "")) for s in pres.find("p:sldIdLst", NS)]


def note(z, part):
    rp = posixpath.dirname(part) + "/_rels/" + posixpath.basename(part) + ".rels"
    for r in E.fromstring(z.read(rp)):
        if r.get("Type").endswith("/notesSlide"):
            x = E.fromstring(z.read(posixpath.normpath(posixpath.join(posixpath.dirname(part), r.get("Target")))))
            b = x.xpath('.//p:sp[p:nvSpPr/p:nvPr/p:ph[@type="body"]]/p:txBody', namespaces=NS)
            return " ".join("".join(p.xpath(".//a:t/text()", namespaces=NS)) for p in b[0].findall("a:p", NS)) if b else ""
    return ""


def norm(s):
    return re.sub(r"\s+", " ", s.replace(" / ", " ").replace("\x0b", " ")).strip()


def script_ranges(directory, config_dir, units):
    files = sorted(directory.glob("*.md"))
    theory = [unit for unit in units if unit.get("kind") == "pptx"]
    paths = [(config_dir / unit.get("file", "")).resolve() for unit in theory]
    issues = []
    if paths != [f.resolve() for f in files]:
        issues.append(f"이론 파일·순서: 실제 {[f.name for f in files]}, 구성 {[u.get('file') for u in theory]}")
    ranges = {path: unit.get("slides") for path, unit in zip(paths, theory)}
    cover, heads = [], []
    for f in files:
        s = f.read_text("utf8")
        numbers = []
        for x in re.finditer(r"(?m)^## \[SLIDE (\d+)(?:~(\d+))?\]", s):
            first, last = int(x[1]), int(x[2] or x[1])
            if last < first:
                issues.append(f"{f.name}: 본문 [SLIDE {first}~{last}] 역순")
            numbers.extend(range(first, last + 1))
        cover.extend(numbers)
        actual = [numbers[0], numbers[-1]] if numbers else None
        guide = re.search(r"(?ms)^## 촬영 전 안내[^\n]*\n(.*?)(?=^#|\Z)", s)
        header = re.search(r"(?m)^(?:대응 덱:[^\n]*?\.pptx\)|(?:대응 덱 )?장 범위:)[ \t]*"
                           r"(\d+)(?:[ \t]*[~–-][ \t]*(\d+))?[ \t]*장", guide[1]) if guide else None
        span = [int(header[1]), int(header[2] or header[1])] if header else None
        heads.append((f.name[:2], span))
        declared = ranges.get(f.resolve())
        if not actual or span != actual or declared != actual:
            issues.append(f"{f.name}: 촬영 안내 {span}, 본문 {actual}, 구성 {declared}")
    return cover, heads, issues


if len(sys.argv) < 2:
    sys.exit(__doc__)
ok = True
for k in sys.argv[1:]:
    m = re.fullmatch(r"(통합|실전)(\d+)", k)
    if not m:
        sys.exit(f"{k}: 덱키는 통합3 · 실전10 꼴이다")
    c, cp = COURSE[m[1]]; n = f"{int(m[2]):02d}"
    md = W / f"제작도구/온라인/decks/{cp}/day{n}/{c}_{n}일차.md"; px = W / f"산출물/{c}/이론/{n}회차/{c}_{n}일차.pptx"; sd = W / f"산출물/{c}/이론/{n}회차/대본"; cj = W / f"제작도구/구성/{c}/{n}회차/구성.json"
    t = md.read_text("utf8"); blocks = re.split(r"(?m)^## SLIDE (\d+) — .*$", t); nums = [int(x) for x in blocks[1::2]]
    notes = {int(blocks[i]): (re.search(r"(?m)^- 노트: (.*)$", blocks[i + 1]) or [0, ""])[1] for i in range(1, len(blocks), 2)}
    z = zipfile.ZipFile(px); o = order(z); diff = [i + 1 for i, p in enumerate(o) if norm(note(z, p)) != norm(notes.get(i + 1, ""))]
    cfg = json.loads(cj.read_text("utf8")); sha = hashlib.sha256(px.read_bytes()).hexdigest()
    cover, heads, issues = script_ranges(sd, cj.parent, cfg.get("units", []))
    res = dict(원고장=len(nums), 번호연속=nums == list(range(1, len(nums) + 1)), PPTX장=len(o), 노트다른장=diff, 대본덮음=cover == list(range(1, len(nums) + 1)), 구성장수=cfg.get("slide_count"), 구성해시일치=cfg.get("pptx_sha256") == sha, 대본머리=heads, 편별어긋남=issues, sha=sha[:12])
    print(k, res)
    ok &= res["원고장"] == res["PPTX장"] == res["구성장수"] and not diff and res["대본덮음"] and res["구성해시일치"] and res["번호연속"] and not issues
print("전부 일치" if ok else "어긋남 있음"); sys.exit(0 if ok else 1)
