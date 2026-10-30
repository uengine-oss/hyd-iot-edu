"""main · workspace 두 브랜치와 작업 폴더를 다룬다. 체크아웃 · 색인을 건드리지 않고 브랜치를 바꾸지 않는다.

    python workspace/동기화.py 시작 "제목"                     # 작업/<오늘>_<제목>/ 에 스펙.md · 기록.md 틀을 만든다
    python workspace/동기화.py status                       # 작업 폴더 · 로컬 작업 자료와 workspace 끝의 차이
    python workspace/동기화.py commit "메시지" [main 경로 ...]  # workspace에 지금 모습을 커밋 + (경로를 주면) main에 그 경로만 커밋
    python workspace/동기화.py push                         # 두 브랜치 키 검사 0 확인 뒤 git push origin main workspace
    python workspace/동기화.py 정리 [--실행]                  # 스펙.md에 「상태: 확정」인 작업 폴더를 지운다(--실행 없으면 목록만)
    python workspace/동기화.py pull                         # origin/workspace를 받아 제자리에 푼다(로컬과 다른 파일이 있으면 멈춤)

- 작업 하나 = 작업/<날짜>_<제목>/ 폴더 하나(이 PC 전용, 어느 브랜치에도 올리지 않음). 확정되면 최종본은 workspace/강의제작/산출물/로
  바꿔 끼우고, 다시 만들 재료(큐 · 음성 캐시 등)는 workspace/강의제작/제작도구/로 옮긴 뒤 commit · push · 정리한다.
  작업/_로컬/ 은 공개하면 안 되는 개인 자료 자리다(강사 실명 배정본 등) — 정리하지 않는다.
- workspace 브랜치 = 아래 PATHS의 지금 모습 그대로다(덧붙이기가 아니다 — 로컬에서 지운 파일은 다음 커밋에서 빠진다).
  경로는 저장소 루트 기준 그대로라 받으면 같은 자리에 풀린다. 브랜치 맨 앞 README.md만 이 도구가 만든다.
- 늘 빼는 것: `.env` 전부(`.env.example`은 넣음), 캐시, 엑셀 옆 `.inspect.ndjson`.
- main은 이 자리들을 `.gitignore`로 무시한다. main 쪽은 준 경로만 커밋한다(같은 체크아웃의 다른 작업이 섞이지 않게).
- commit 때 산출물에 같은 것의 이전 판(이름 끝 v1 · 날짜 · 사본)이 보이면 경고한다 — 최신 하나만 둔다.
- 노션 영상 링크가 workspace 커밋을 가리키므로 커밋은 늘 앞 커밋 위에 쌓는다(이력을 다시 쓰지 않음, 강제 push 없음).
- 공개 저장소다. 커밋마다 키 검사(secret_scan.py) 0이어야 브랜치에 붙는다.
"""
import datetime, hashlib, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _toplevel():
    # 저장소 루트는 git에게 묻는다 — 새 PC에서 이 파일을 루트에 꺼내 돌려도 같은 루트가 나온다
    r = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=HERE, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"{HERE}: git 저장소 안이 아니다 — 저장소 폴더 안에서 돌린다")
    return Path(r.stdout.strip())


ROOT = _toplevel()
BRANCH = "workspace"
SCAN = ROOT / "workspace" / "secret_scan.py"
WORK = ROOT / "작업"
PATHS = ["workspace", ".claude", "CLAUDE.md", "AGENTS.md"]
SKIP_DIRS = {"__pycache__", ".pytest_cache", "node_modules", "worktrees"}
SKIP_FILES = {".claude/settings.local.json"}
OLD_VERSION = re.compile(r"(?:[_-]v\d+|[_-]\d{8}|[_ -]?사본\d*| \(\d+\))$", re.I)
README = """# workspace — 작업 자료 브랜치

학생이 받는 코드는 main 브랜치다. 이 브랜치는 강의를 만들고 시스템을 고치는 사람이 쓰는 작업 자료 전부다.

- 어디부터: [workspace/README.md](workspace/README.md) — 하려는 일 → 읽을 문서 하나.
- 받기(새 PC, main을 clone한 폴더에서, Git Bash): `git fetch origin workspace` → `git show origin/workspace:workspace/동기화.py > 동기화.py` → `python 동기화.py pull` → `rm 동기화.py`.
  PowerShell의 `>`는 인코딩을 바꿀 수 있어 쓰지 않는다.
- 경로는 저장소 루트 기준 그대로다. main과 병합하지 않는다. 이력을 다시 쓰지 않는다(노션 영상 링크가 이 브랜치 커밋을 가리킨다).
- 공개 저장소다. 키 · 개인 정보 · 실물 매뉴얼 PDF를 올리지 않는다.
"""
SPEC = """# {title}

- 시작: {day} · 상태: 진행
- 확정되면 이 줄의 상태를 「확정」으로 바꾸고 `python workspace/동기화.py 정리 --실행`으로 이 폴더를 지운다.

## 의도
(왜 · 누구에게 무엇이 좋아지나)

## 범위
(하는 것 / 하지 않는 것)

## 읽을 문서
(workspace/README.md 색인에서 고른 문서 하나 + 촬영이면 그 도구의 촬영준비 하나)

## 인수 조건
(그 문서의 인수 조건 표에서 이번에 판정할 행 · 판정 방법)
"""
LOG = """# {title} — 기록

덧붙이지 않고 고쳐 쓴다. 지금 상태 · 남은 일 · 막힌 것만 둔다(지난 경위는 지운다).

## 지금
- {day} 시작

## 남은 일
-

## 결과가 들어갈 자리
- 최종본: workspace/강의제작/산출물/…
- 재료: workspace/강의제작/제작도구/…
"""


def git(*a, env=None, inp=None):
    r = subprocess.run(["git", "-c", "core.quotepath=false", *a], cwd=ROOT, env=env, input=inp, capture_output=True)
    if r.returncode:
        sys.exit(f"git {' '.join(a[:3])}: {r.stderr.decode('utf-8', 'replace').strip()}")
    return r.stdout.decode("utf-8", "replace")


def is_env(name):
    base = name.rsplit("/", 1)[-1]
    return base == ".env" or (base.startswith(".env.") and base != ".env.example")


def local_files():
    main = set(git("ls-files").splitlines())
    files = []
    for top in PATHS:
        p = ROOT / top
        if p.is_file():
            cand = [p]
        elif p.is_dir():
            cand = [f for f in p.rglob("*") if f.is_file() and not SKIP_DIRS & set(f.relative_to(ROOT).parts)]
        else:
            continue
        for f in cand:
            rel = f.relative_to(ROOT).as_posix()
            if rel in main or rel in SKIP_FILES or is_env(rel) or rel.endswith((".pyc", ".inspect.ndjson")):
                continue
            files.append(rel)
    if not any(f.startswith("workspace/") for f in files):
        sys.exit(f"{ROOT / 'workspace'}: 작업 자료가 없다 — 먼저 `python workspace/동기화.py pull`")
    return sorted(files)


def old_versions(files):
    """산출물 안에서 같은 폴더 · 같은 이름에 판 꼬리만 다른 파일 묶음."""
    groups = {}
    for f in files:
        if not f.startswith("workspace/강의제작/산출물/"):
            continue
        p = Path(f)
        groups.setdefault((p.parent.as_posix(), OLD_VERSION.sub("", p.stem), p.suffix), []).append(f)
    return [g for g in groups.values() if len(g) > 1]


def tip(ref=f"refs/heads/{BRANCH}"):
    return git("rev-parse", "--verify", "-q", ref).strip()


def build_tree(files):
    with tempfile.TemporaryDirectory() as d:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(d) / "index"))
        git("read-tree", "--empty", env=env)
        listfile = Path(d) / "list"
        listfile.write_text("\n".join(files) + "\n", encoding="utf-8")
        git("-c", "core.autocrlf=false", "add", "-f", f"--pathspec-from-file={listfile}", env=env)
        readme = git("hash-object", "-w", "--stdin", inp=README.encode("utf-8")).strip()
        git("update-index", "--add", "--cacheinfo", f"100644,{readme},README.md", env=env)
        return git("write-tree", env=env).strip()


def scan(ref):
    return subprocess.run([sys.executable, str(SCAN), ref], cwd=ROOT).returncode == 0


def tasks():
    return sorted(p for p in WORK.glob("[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]_*") if p.is_dir()) if WORK.is_dir() else []


def state(task):
    spec = task / "스펙.md"
    m = re.search(r"상태:\s*(\S+)", spec.read_text(encoding="utf-8")) if spec.is_file() else None
    return m.group(1) if m else "스펙 없음"


def start(title):
    name = re.sub(r"[\\/:*?\"<>|\s]+", "-", title.strip()).strip("-")
    if not name:
        sys.exit("제목이 비었다")
    day = datetime.date.today().isoformat()
    d = WORK / f"{day}_{name}"
    if d.exists():
        sys.exit(f"이미 있다: {d.relative_to(ROOT).as_posix()}")
    d.mkdir(parents=True)
    (d / "스펙.md").write_text(SPEC.format(title=title.strip(), day=day), encoding="utf-8")
    (d / "기록.md").write_text(LOG.format(title=title.strip(), day=day), encoding="utf-8")
    print(f"만듦 {d.relative_to(ROOT).as_posix()}/스펙.md · 기록.md")


def status():
    for t in tasks():
        print(f"작업 {t.name} · 상태 {state(t)}")
    t = tip()
    remote = set(git("ls-tree", "-r", "--name-only", t).splitlines()) - {"README.md"}
    local = set(local_files())
    print(f"workspace {t[:8]} · 로컬 {len(local)}개 · workspace {len(remote)}개 · 로컬에만 {len(local - remote)} · workspace에만 {len(remote - local)}")
    for f in sorted(local - remote)[:20]: print(f"  로컬에만      {f}")
    for f in sorted(remote - local)[:20]: print(f"  workspace에만 {f}")


def commit(msg, main_paths):
    files = local_files()
    for g in old_versions(files):
        print("경고 — 이전 판이 함께 있다(최신 하나만 둔다): " + " · ".join(g))
    t = tip()
    tree = build_tree(files)
    if tree == git("rev-parse", f"{t}^{{tree}}").strip():
        print("workspace: 바뀐 것이 없다 — 커밋하지 않는다")
    else:
        body = msg + "\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n"
        c = git("commit-tree", tree, "-p", t, inp=body.encode("utf-8")).strip()
        if not scan(c):
            sys.exit(f"키 검사에 걸렸다 — {c[:8]}를 workspace에 붙이지 않았다(위 목록을 고친 뒤 다시)")
        git("update-ref", f"refs/heads/{BRANCH}", c, t)
        print(f"workspace {t[:8]} → {c[:8]}")
    if main_paths:
        commit_main(msg + "\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n", main_paths)


def commit_main(body, paths):
    """main에 준 경로만 커밋한다(같은 체크아웃의 다른 작업이 섞이지 않게). HEAD에서 시작한 따로 색인에 그 경로만 작업 트리 모습으로
    넣고, 실행 권한은 진짜 색인의 값(`git update-index --chmod=+x`)을 따른다 — `git commit -- 경로`는 HEAD에서 새로 만든 색인에
    파일을 더해, core.filemode=false인 Windows에서 새 파일을 늘 100644로 커밋했다(setup/*.command 두 번). 커밋 뒤 진짜 색인의
    그 경로를 새 커밋에 맞춘다."""
    staged = {}
    for entry in filter(None, git("ls-files", "-s", "-z", "--", *paths).split("\0")):
        meta, path = entry.split("\t", 1)
        staged[path] = meta.split()[0]
    head = git("rev-parse", "HEAD").strip()
    with tempfile.TemporaryDirectory() as d:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(d) / "index"))
        git("read-tree", head, env=env)
        git("add", "-A", "--", *paths, env=env)            # 줄끝 · 속성은 `git commit`과 같은 설정(.gitattributes)대로
        for path in [p for p, mode in staged.items() if mode == "100755"]:
            git("update-index", "--chmod=+x", "--", path, env=env)
        tree = git("write-tree", env=env).strip()
    if tree == git("rev-parse", f"{head}^{{tree}}").strip():
        print("main: 준 경로에 바뀐 것이 없다 — 커밋하지 않는다")
        return
    c = git("commit-tree", tree, "-p", head, inp=body.encode("utf-8")).strip()
    git("update-ref", "HEAD", c, head)
    git("reset", "-q", "--", *paths)
    print(git("show", "--stat", "--format=main %h %s", "HEAD"))


def push():
    for ref in ("main", BRANCH):
        if not scan(ref):
            sys.exit(f"{ref}: 키 검사에 걸렸다 — push하지 않았다")
    print(git("push", "origin", "main", BRANCH))
    # 이 저장소의 fetch 설정은 main만 받는다 — 두 브랜치를 이름으로 받아 와야 origin/workspace가 새 값이 된다
    git("fetch", "-q", "origin", "+refs/heads/main:refs/remotes/origin/main", f"+refs/heads/{BRANCH}:refs/remotes/origin/{BRANCH}")
    for ref in ("main", BRANCH):
        print(ref, git("rev-list", "--left-right", "--count", f"{ref}...origin/{ref}").strip())


def clean(run):
    done = [t for t in tasks() if state(t) == "확정"]
    for t in tasks():
        if t not in done:
            print(f"남김 {t.name}(상태 {state(t)})")
    for t in done:
        if run:
            shutil.rmtree(t)
            print(f"지움 {t.name}")
        else:
            print(f"지울 것 {t.name} — `정리 --실행`으로 지운다")
    if not done:
        print("확정된 작업 폴더가 없다")


def pull():
    git("fetch", "-q", "origin", f"+refs/heads/{BRANCH}:refs/remotes/origin/{BRANCH}")
    ref = f"refs/remotes/origin/{BRANCH}"
    blobs = {}
    for e in filter(None, git("ls-tree", "-r", "-z", ref).split("\0")):
        meta, n = e.split("\t", 1)
        if n != "README.md":
            blobs[n] = meta.split()[2]

    def blob_sha(p):                                   # git hash-object와 같은 값(파일마다 git을 부르지 않으려고)
        data = p.read_bytes()
        return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()
    clash = [n for n in blobs if (ROOT / n).exists() and blob_sha(ROOT / n) != blobs[n]]
    if clash:
        sys.exit("로컬이 workspace와 다른 파일이 있어 덮어쓰지 않는다(먼저 commit하거나 그 파일을 치운다):\n  " + "\n  ".join(clash[:50]))
    # Windows tar는 한글 경로를 못 푼다 — cat-file --batch로 파일을 직접 꺼낸다
    cat = subprocess.Popen(["git", "cat-file", "--batch"], cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    written = 0
    for n in blobs:
        cat.stdin.write(f"{ref}:{n}\n".encode("utf-8")); cat.stdin.flush()
        size = int(cat.stdout.readline().split()[2])
        data = cat.stdout.read(size); cat.stdout.read(1)
        p = ROOT / n
        if p.exists():
            continue                                   # 위에서 같은 내용임을 확인했다
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data); written += 1
    cat.stdin.close(); cat.wait()
    git("update-ref", f"refs/heads/{BRANCH}", git("rev-parse", ref).strip())
    print(f"origin/{BRANCH} {git('rev-parse', '--short', ref).strip()} → 작업 자료 {len(blobs)}개(새로 쓴 것 {written})")


if __name__ == "__main__":
    cmd, args = sys.argv[1:2], sys.argv[2:]
    if cmd == ["시작"] and args: start(" ".join(args))
    elif cmd == ["status"]: status()
    elif cmd == ["commit"] and args: commit(args[0], args[1:])
    elif cmd == ["push"]: push()
    elif cmd == ["정리"]: clean("--실행" in args)
    elif cmd == ["pull"]: pull()
    else: sys.exit(__doc__)
