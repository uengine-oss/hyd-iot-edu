"""온라인 덱의 판본 연결을 잰다: 원고 · PPTX 장 수, 노트 일치, 대본 [SLIDE] 덮음, 구성.json slide_count · pptx_sha256, 이론 파일별 촬영 안내·본문·구성의 장 범위와 파일 순서.
언제: 덱 · 대본 · 노트를 고친 뒤 커밋 전, 굽기 전. 읽기만 한다.
명령: <py> workspace/강의제작/제작도구/검사/판본검사.py <덱키 …(통합3 실전4)>   # 전부 일치면 종료 0, 어긋나면 1
      <py> workspace/강의제작/제작도구/검사/판본검사.py 실전2 --원본 덱 81-99   # fetch 후 실전 2~8회 한 단원의 수동 원본 근거와 origin/workspace를 비교한다. 일반 판본검사와 별도로 실행한다.
원본대응.json의 확인단원 예: {"단계":"덱","실전장":[81,99],"상태":"확정","근거":"원본 단원 판정 위치 — 확인한 내용","원본":[{"커밋":"<원격에 올린 커밋 SHA>","경로":"<저장소 기준 통합반 원고 경로>","장":[20,35]}]}.
실전 고유 응용·전환만 있는 경우 검토자가 구분을 "고유"로 적고 빈 원본 배열과 실제 근거를 남긴다. 확인단원은 목록이고, 기존의 자동 대응 후보는 이 목록을 대신할 수 없다.
"""
import hashlib, json, posixpath, re, subprocess, sys, zipfile
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


def source_slice(ref, path, span, stage, allowed):
    """지정 장의 원문과 그 장에서 직접 가리킨 그림만 추적한다."""
    if (not isinstance(span, list) or len(span) != 2 or
            not all(type(n) is int for n in span) or not 1 <= span[0] <= span[1]):
        raise ValueError(f"{path}: 원본 장 범위를 확인한다")
    deck = stage == "덱"
    pattern = (r"^workspace/강의제작/제작도구/온라인/decks/integrated/day(\d\d)/통합반_\1일차\.md$" if deck
               else r"^workspace/강의제작/산출물/통합반/이론/(\d\d)회차/대본/[^/]+\.md$")
    match = re.fullmatch(pattern, path) if isinstance(path, str) else None
    if not match:
        raise ValueError(f"{path}: {stage}의 통합반 정본 경로가 아니다")
    if int(match[1]) not in allowed:
        raise ValueError(f"{path}: 공통 대응표의 통합 {sorted(allowed)}회차 밖이다")
    source = git_read("show", f"{ref}:{path}")
    marker = r"^## SLIDE (\d+) — .*?$" if deck else r"^## \[SLIDE (\d+)(?:~(\d+))?\].*?$"
    headings = list(re.finditer(marker, source, re.M))
    slides, notes, covered, pictures = [], [], [], set()
    for i, head in enumerate(headings):
        a = int(head[1])
        b = a if deck or not head[2] else int(head[2])
        if b < span[0] or a > span[1]:
            continue
        if b < a or a < span[0] or b > span[1]:
            raise ValueError(f"{path}: {a}~{b}장 발화 범위를 온전히 지정한다")
        end = headings[i + 1].start() if i + 1 < len(headings) else len(source)
        body = source[head.end():end]
        if not deck:
            body = re.split(r"^#{1,2} ", body, maxsplit=1, flags=re.M)[0]
        if deck:
            screen, _, criteria = body.partition("\n### 제작 기준")
            lines = screen.splitlines()
            notes.append(([line for line in lines if line.startswith("- 노트:")], criteria.strip()))
            body = "\n".join(line for line in lines if not line.startswith("- 노트:"))
        slides.append(head[0] + "\n" + body.strip())
        covered.extend(range(a, b + 1))
        if deck:
            for figure in re.findall(r"^- 그림:[ \t]*(.+)$", body, re.M):
                pictures.add(posixpath.normpath(posixpath.join(posixpath.dirname(path), figure.strip())))
    if not covered or len(covered) != span[1] - span[0] + 1 or any(n != span[0] + i for i, n in enumerate(covered)):
        raise ValueError(f"{ref} {path}: {span[0]}~{span[1]}장을 확인할 수 없다")
    pictures = {p: git_read("rev-parse", "--verify", f"{ref}:{p}").strip() for p in pictures}
    return slides, pictures, notes


def git_read(*args):
    # git show/ref는 마지막 fetch의 원격 추적 판을 읽는다. 얕은 이력 등 확인 불가도 닫지 않는다.
    result = subprocess.run(["git", *args], cwd=W.parent.parent, capture_output=True)
    if result.returncode:
        raise ValueError(f"git {' '.join(args)} 확인 불가. 원격 판과 필요한 이력을 받은 뒤 대조한다")
    return result.stdout.decode("utf-8")


def source_days(practical_day):
    """공통 지침의 대응표에서 한 실전 회차가 참조하는 통합 회차를 읽는다."""
    common = (W / "지침/공통.md").read_text(encoding="utf8")
    header = "| 실전 온라인 회차 | 통합 온라인 회차 | 적용 범위 |"
    parts = common.split(header)
    if len(parts) != 2:
        raise ValueError("공통 지침의 실전·통합 온라인 대응표를 확인한다")
    hits = []
    for line in parts[1].strip().splitlines():
        if not line.startswith("|"):
            break
        row = re.fullmatch(r"\|\s*(\d+)\s*\|\s*(\d+(?:\s*,\s*\d+)*)\s*\|[^|]+\|", line)
        if row and int(row[1]) == practical_day:
            hits.append({int(n) for n in row[2].split(",")})
    if len(hits) != 1:
        raise ValueError(f"공통 지침의 실전 {practical_day}회차 대응 행을 하나로 확인할 수 없다")
    return hits[0]


def check_sources(key, stage, piece):
    practical = re.fullmatch(r"실전([2-8])", key)
    match = re.fullmatch(r"(\d+)(?:-(\d+))?", piece)
    if not practical or stage not in ("덱", "대본") or not match:
        raise ValueError("사용법: 판본검사.py 실전2 --원본 덱|대본 81-99")
    span = [int(match[1]), int(match[2] or match[1])]
    if not 1 <= span[0] <= span[1]:
        raise ValueError("실전반 장 범위를 확인한다")
    path = W / f"제작도구/구성/실전반/0{practical[1]}회차/원본대응.json"
    count = json.loads(path.with_name("구성.json").read_text(encoding="utf8")).get("slide_count")
    if type(count) is not int or span[1] > count:
        raise ValueError(f"실전반 장 {span}이 현재 구성의 {count}장 범위에 들지 않는다")
    data = json.loads(path.read_text(encoding="utf8"))
    records = [r for r in data.get("확인단원", [])
               if isinstance(r, dict) and r.get("단계") == stage and r.get("실전장") == span]
    if len(records) != 1:
        raise ValueError(f"{path.name}: 해당 {stage} 단원의 수동 확인 기록이 하나여야 한다. 기존 유사도·구성표만으로는 확정할 수 없다")
    record = records[0]
    if (record.get("상태") != "확정" or not isinstance(record.get("근거"), str)
            or not record["근거"].strip() or not isinstance(record.get("원본"), list)):
        raise ValueError(f"{path.name}: 확정된 원본과 검토 근거를 확인한다")
    allowed = source_days(int(practical[1]))
    if not record["원본"]:
        if record.get("구분") != "고유":
            raise ValueError("원본 없는 단원은 검토자가 실전 고유의 응용·전환으로 구분하고 그 근거를 적는다")
        print(f"{key} {stage} {piece}: 고유 단원의 검토 근거가 있음. 의미와 실라버스 범위는 검토자가 확인한다.")
        return
    if record.get("구분") == "고유":
        raise ValueError("참조 원본이 있는 단원을 원본 없는 고유 단원으로 지정했다")
    tip = git_read("rev-parse", "--verify", "refs/remotes/origin/workspace^{commit}").strip()
    for src in record["원본"]:
        commit = src["커밋"]
        if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-fA-F]{7,40}", commit):
            raise ValueError("근거의 원본 커밋 SHA를 확인한다")
        commit = git_read("rev-parse", "--verify", f"{commit}^{{commit}}").strip()
        git_read("merge-base", "--is-ancestor", commit, tip)
        origin, pages = src["경로"], src["장"]
        before = source_slice(commit, origin, pages, stage, allowed)
        after = source_slice(tip, origin, pages, stage, allowed)
        changed = [name for name, old, new in zip(("원문", "그림", "노트·제작 근거"), before, after) if old != new]
        if changed:
            raise ValueError(f"{origin} {pages}: {', '.join(changed)} 변경. 이번 단원에 영향이 있는지 현재 원본판에서 확인한다")
    print(f"{key} {stage} {piece}: 원본 범위 일치 ({tip[:10]}). 의미 대응과 진행 중인 수정 여부는 검토자가 확인한다.")


if "--원본" in sys.argv:
    if len(sys.argv) != 5 or sys.argv[2] != "--원본":
        sys.exit(__doc__)
    try:
        check_sources(sys.argv[1], sys.argv[3], sys.argv[4])
    except (OSError, KeyError, TypeError, AttributeError, ValueError) as error:
        sys.exit(f"원본 대조 미확인 — {error}")
    sys.exit(0)

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
