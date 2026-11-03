"""덱 원고(화면 내용 · 노트)와 대본 낭독에 나온 식별자가 지금 시스템에 있는지 잰다.
이름이 있는지만 판정한다. 값 · 설명 · 쓰임은 판정하지 않으므로 통과해도 내용은 따로 본다.

    <py> workspace/강의제작/제작도구/검사/식별자대조.py <덱 원고 · 대본 …> [--틀린예 이름 …] [--컨테이너 이름] [--출력 결과.json]

판정 기준
- 그래프 이름(`rule:…` 꼴 id, `SOP-…` · `P-…` · `HM-8.1` 꼴 절 번호, `Sensor {`의 레이블): 떠 있는 그래프에 있어야 한다.
  코드는 보지 않는다 — 코드 대조는 주석에 남은 옛 이름까지 걸려 지워진 이름을 놓친다.
- 대문자 이름(`HAS_COMPONENT` · `LLM_API_KEY`): 그래프의 관계 · 코드 값이면 통과, 아니면 코드에 있는지 보고 「코드에만」으로 따로 찍는다
  (관계 이름인지 설정 이름인지 글자만으로 갈리지 않아 눈으로 볼 몫이다).
- 소문자 이름(`evaluate_cards`) · 문서 번호(`HM-8` · `PM-02`): 그래프나 코드(`it` `ot` `dmz` `common`)에 있어야 한다.
- 일부러 틀린 예(없는 이름을 보이는 장의 `HAS_PART` · `sen:zz9`)는 `--틀린예`로 준다. 그 이름이 실제로 있으면 표시가 낡은 것이라 실패한다.

종료 코드: 0 전부 있음 · 1 없는 이름 있음(파일:줄) · 2 판정 못 함(그래프 없음 · 조회 실패 · id 0개 · 덱 원고도 대본도 아닌 파일). 조용히 통과하지 않는다.

그래프: `.hyd-runtime/project.json`의 compose 이름이거나 이 체크아웃에서 띄운 neo4j 컨테이너를 쓰고, 조회는 `--access-mode read`다.
없으면 떠 있는 neo4j를 찍고 실패한다. 그 그래프로 보려면 `--컨테이너`로 밝히고, 다른 체크아웃의 스택이면 시드 파일(`it/neo4j/v2/*.cypher`)이 이 체크아웃과 같을 때만 쓴다.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
ID_KEYS = ("id", "code", "partNo", "sopId", "ref", "typeRef", "tag")
KNOWN_PREFIX = {"rule", "fm", "sym", "cause", "comp", "asset", "sen", "sv", "pattern", "msr", "dt", "dec", "ks", "skill", "part", "kpi", "act", "step", "sec", "ms"}
CODE_ROOTS = ("it", "ot", "dmz", "common")
CODE_SUFFIX = {".cypher", ".json", ".py", ".md", ".yaml", ".yml", ".js", ".html", ".ttl", ".sql", ".mjs", ".txt"}
# 파이썬의 \b는 한글도 글자로 쳐서 조사가 붙은 이름(`HAS_PART는`)을 놓친다. 영문 · 숫자만 경계로 본다.
L, R = r"(?<![A-Za-z0-9_])", r"(?![A-Za-z0-9_])"
PREFIXED = re.compile(L + r"([a-z]{2,12}):([a-z0-9][a-z0-9_\-]*)")
REF = re.compile(L + r"(?:SOP-[A-Z]+-\d+|P-[A-Z]{2,}-[A-Z0-9\-]+|(?:HM|PM|PR)-\d+\.\d+)" + R)
DOC = re.compile(L + r"(?:HM|PM|PR|SR)-\d+(?!\.\d)" + R)
UPPER = re.compile(L + r"[A-Z]+_[A-Z_]{3,}" + R)
LABEL = re.compile(L + r"[A-Z][a-zA-Z]+(?=\s*\{)")
LOWER = re.compile(L + r"[a-z]+_[a-z0-9_]{2,}" + R)


def stop(msg):
    print(f"판정 못 함: {msg}")
    sys.exit(2)


def run(*c, **kw):
    return subprocess.run(c, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180, **kw)


def scope_lines(path):
    """판정 대상 줄을 (줄 번호, 글)로 돌려준다. 덱 원고는 `### 화면 내용` 칸(노트 포함), 대본은 `# 촬영 본문 끝` 앞."""
    if not path.is_file():
        stop(f"{path}: 파일 없음")
    lines = path.read_text("utf-8").splitlines()
    if "### 화면 내용" in lines:
        inside = False
        for n, l in enumerate(lines, 1):
            if l.startswith("## ") or l.startswith("### "):
                inside = l == "### 화면 내용"
            elif inside:
                yield n, l
    elif any(l.startswith("## [SLIDE") for l in lines):
        for n, l in enumerate(lines, 1):
            if l.strip() == "# 촬영 본문 끝":
                return
            yield n, l
    else:
        stop(f"{path}: 덱 원고(`### 화면 내용`)도 대본(`## [SLIDE`)도 아니다")


def compose_name():
    f = ROOT / ".hyd-runtime" / "project.json"
    return json.loads(f.read_text("utf-8")).get("compose") if f.is_file() else None


def same_dir(a, b):
    try:
        return bool(a) and os.path.samefile(a, b)
    except OSError:
        return False


def find_container(explicit):
    """(컨테이너, compose 프로젝트, 띄운 폴더). 이 체크아웃의 것이 아니면 멈춘다 — 다른 판의 그래프로 통과하면 안 된다."""
    fmt = '{{.Names}}\t{{.Label "com.docker.compose.project"}}\t{{.Label "com.docker.compose.project.working_dir"}}'
    r = run("docker", "ps", "--filter", "label=com.docker.compose.service=neo4j", "--format", fmt)
    if r.returncode:
        stop(f"docker에 물을 수 없다 — {r.stderr.strip()[:200]}")
    rows = [tuple((l.split("\t") + ["", ""])[:3]) for l in r.stdout.splitlines() if l.strip()]
    if explicit:
        hit = [x for x in rows if x[0] == explicit]
        if not hit:
            stop(f"컨테이너 {explicit}: 떠 있는 neo4j가 아니다. 떠 있는 것: {[x[0] for x in rows] or '없음'}")
        return hit[0]
    want = compose_name()
    mine = [x for x in rows if x[1] == want or same_dir(x[2], ROOT)]
    if len(mine) == 1:
        return mine[0]
    if not mine:
        stop(f"이 체크아웃의 그래프가 떠 있지 않다(project.json의 compose: {want}). 떠 있는 neo4j: {[(x[0], x[2]) for x in rows] or '없음'}. "
             "그 그래프로 볼 거면 --컨테이너 이름으로 밝힌다")
    stop(f"이 체크아웃의 neo4j가 둘 이상이다: {[x[0] for x in mine]}. --컨테이너로 고른다")


def check_seed_same(container, workdir):
    """다른 체크아웃의 스택이면 시드 파일이 같을 때만 쓴다. 다르면 이 체크아웃의 판정이 아니다."""
    if same_dir(workdir, ROOT):
        return
    other = Path(workdir) / "it" / "neo4j" / "v2" if workdir else None
    if not other or not other.is_dir():
        stop(f"컨테이너 {container}: 띄운 폴더({workdir or '없음'})를 열 수 없어 시드 판을 대조하지 못한다")
    for f in sorted((ROOT / "it" / "neo4j" / "v2").glob("*.cypher")):
        g = other / f.name
        if not g.is_file() or g.read_bytes().replace(b"\r\n", b"\n") != f.read_bytes().replace(b"\r\n", b"\n"):   # 체크아웃마다 줄바꿈만 다를 수 있다
            stop(f"컨테이너 {container}: 시드 {f.name}이 이 체크아웃과 다르다({workdir})")
    print(f"그래프: {container} — 다른 체크아웃({workdir})의 스택, 시드 파일은 이 체크아웃과 같음")


def graph(container):
    """읽기 전용으로 그래프 이름 집합을 읽는다. 암호는 컨테이너 환경에서 그 안에서만 쓴다."""
    keys = ",".join(f"'{k}'" for k in ID_KEYS)
    q = (f"MATCH (n) UNWIND [k IN [{keys}] WHERE n[k] IS NOT NULL | toString(n[k])] AS v RETURN DISTINCT 'id' AS kind, v "
         "UNION CALL db.relationshipTypes() YIELD relationshipType AS v RETURN 'rel' AS kind, v "
         "UNION CALL db.labels() YIELD label AS v RETURN 'label' AS kind, v "
         "UNION CALL db.propertyKeys() YIELD propertyKey AS v RETURN 'key' AS kind, v;")
    try:
        r = run("docker", "exec", "-i", container, "sh", "-c",
                'cypher-shell -u neo4j -p "${NEO4J_AUTH#neo4j/}" --format plain --access-mode read', input=q)
    except subprocess.TimeoutExpired:
        stop(f"컨테이너 {container}: 조회가 시간 안에 끝나지 않았다")
    if r.returncode:
        stop(f"컨테이너 {container}: 조회 실패 — {r.stderr.strip()[:200]}")
    g = {"id": set(), "rel": set(), "label": set(), "key": set()}
    for m in re.finditer(r'^"(id|rel|label|key)", "(.*)"$', r.stdout, flags=re.M):
        g[m[1]].add(m[2])
    if not g["id"]:
        stop(f"컨테이너 {container}: 그래프에 id가 하나도 없다(시드 전)")
    return g


def seeding(project):
    r = run("docker", "ps", "--filter", f"label=com.docker.compose.project={project}", "--filter", "label=com.docker.compose.service=kg-seed",
            "--filter", "status=running", "--format", "{{.Names}}")
    return bool(r.stdout.strip())


def code_corpus():
    r = run("git", "-c", "core.quotepath=false", "ls-files", *CODE_ROOTS, cwd=ROOT)
    if r.returncode:
        stop(f"git ls-files 실패 — {r.stderr.strip()[:200]}")
    parts = []
    for f in r.stdout.splitlines():
        p = ROOT / f
        if p.suffix in CODE_SUFFIX and p.is_file() and p.stat().st_size < 3_000_000:
            parts.append(p.read_text("utf-8", errors="ignore"))
    if not parts:
        stop("코드 파일을 하나도 읽지 못했다")
    return "\n".join(parts)


def main():
    ap = argparse.ArgumentParser(description="식별자가 지금 시스템에 있는지 잰다(이름만)")
    ap.add_argument("files", nargs="+")
    ap.add_argument("--틀린예", dest="wrong", nargs="*", default=[], help="일부러 틀린 예로 쓴 이름")
    ap.add_argument("--컨테이너", dest="container", help="쓸 neo4j 컨테이너 이름")
    ap.add_argument("--출력", dest="out", help="결과 JSON 경로")
    a = ap.parse_args()

    # 그래프가 없으면 파일을 읽기 전에 멈춘다
    container, project, workdir = find_container(a.container)
    check_seed_same(container, workdir)
    g = graph(container)
    if project and seeding(project):
        print(f"주의: {project}의 kg-seed가 아직 도는 중이다. 없음으로 나온 이름은 시드가 끝난 뒤 다시 본다")
    code = code_corpus()
    prefixes = KNOWN_PREFIX | {v.split(":")[0] for v in g["id"] if re.fullmatch(r"[a-z]{2,12}:.+", v)}

    seen, wrong_hit = {}, set()
    def note(name, kind, where):
        if name in a.wrong:
            wrong_hit.add(name)
        else:
            seen.setdefault((kind, name), []).append(where)

    for f in a.files:
        path = Path(f)
        for n, l in scope_lines(path):
            where = f"{f}:{n}"
            for m in PREFIXED.finditer(l):
                if m[1] in prefixes:
                    note(f"{m[1]}:{m[2].rstrip('-')}", "그래프 id", where)
            for m in REF.finditer(l):
                note(m[0], "그래프 id", where)
            for m in LABEL.finditer(l):
                note(m[0], "그래프 레이블", where)
            for m in UPPER.finditer(l):
                note(m[0], "대문자", where)
            for m in DOC.finditer(l):
                note(m[0], "문서", where)
            for m in LOWER.finditer(l):
                note(m[0], "소문자", where)

    missing, code_only, count = {}, {}, {}
    for (kind, name), places in seen.items():
        count[kind] = count.get(kind, 0) + 1
        if kind == "그래프 id":
            ok = name in g["id"]
        elif kind == "그래프 레이블":
            ok = name in g["label"]
        elif kind == "대문자":
            ok = name in g["rel"] or name in g["id"] or name in g["key"]
            if not ok and name in code:
                code_only[name] = places
                continue
        else:   # 소문자 · 문서 번호는 그래프의 노드가 아니라서 코드까지 본다
            ok = name in g["key"] or name in g["id"] or name in code
        if not ok:
            missing[f"{kind} {name}"] = places

    stale = sorted(n for n in a.wrong if n in g["id"] or n in g["rel"] or n in g["label"] or n in g["key"] or n in code)
    print(f"그래프 {container} · 이름 수 " + " · ".join(f"{k} {v}" for k, v in sorted(count.items())) + f" · 틀린 예로 뺀 것 {sorted(wrong_hit)}")
    for n, places in sorted(code_only.items()):
        print(f"  코드에만(그래프 관계 아님, 눈으로 볼 것) {n} — {places[0]}" + (f" 외 {len(places) - 1}곳" if len(places) > 1 else ""))
    for n, places in sorted(missing.items()):
        print(f"  없음 {n} — " + ", ".join(places[:5]) + (f" 외 {len(places) - 5}곳" if len(places) > 5 else ""))
    for n in stale:
        print(f"  틀린 예로 표시했는데 실제로 있음 {n}")
    print(f"없음 {len(missing)} · 코드에만 {len(code_only)} · 낡은 틀린 예 {len(stale)}")
    if a.out:
        Path(a.out).write_text(json.dumps({"그래프": container, "없음": missing, "코드에만": code_only, "낡은 틀린 예": stale}, ensure_ascii=False, indent=1), "utf-8")
    sys.exit(1 if missing or stale else 0)


if __name__ == "__main__":
    main()
