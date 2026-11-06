"""main 체크아웃에 겹쳐 둔 workspace 브랜치와 작업 폴더를 다룬다(체크아웃 · 그 색인 · 브랜치는 건드리지 않는다).
언제: 작업 폴더를 열 때 · 올리기 전후(순서 pull → commit → 바로 push) · 세션 시작 훅.
명령: PYTHONUTF8=1 .venv314/Scripts/python.exe workspace/동기화.py <아래 하나>
    시작 "제목"                         작업/<오늘>_<제목>/에 스펙.md · 기록.md 틀(클라우드는 커밋되는 근거/<오늘>_<제목>/에 — CLAUDE.md 7절)
    status                            로컬 작업 자료와 workspace 끝의 차이
    commit "메시지" [main 경로 …] [--만 workspace 경로 … | --만 --파일 <목록>]
                                      workspace = 지금 모습 그대로(--만이면 준 경로만), main = 준 경로만. origin이 앞서면 멈춘다.
                                      지침 · .claude · CLAUDE.md · AGENTS.md · workspace/README.md가 바뀌면 재편검사 오류 0일 때만 붙는다
    push                              origin에 없는 두 브랜치 커밋마다 키 검사 0일 때만 push, 끝에 이력 크기(7 GB 넘으면 경고)
    pull                              origin/workspace를 받아 제자리에 푼다. 이 PC가 손대지 않은 파일만 원격 판으로 바꾸고, 이 PC 판(미커밋 ·
                                      올리지 않은 커밋)은 디스크에 둔다 — 갈라졌으면 로컬 끝을 origin으로 옮기고 그 커밋 파일은 다음 commit에 들어간다.
                                      둘 다 바꾼 파일이 있으면 아무것도 쓰지 않고 멈춘다
    세션                               세션 시작 훅: 열린 작업 폴더 · origin보다 뒤처졌는지
    정리 [--실행]                       스펙.md 「상태: 확정」 작업 폴더를 지운다(--실행 없으면 목록만). 폴더 밖의 문서가 그 폴더를 가리키면 지우지 않는다
- 빼는 것: .env 전부(.env.example은 넣음) · main 추적 파일 · 캐시 · node_modules · worktrees · 슬라이드/ · 조각_저장/ · .claude/settings.local.json · .inspect.ndjson.
- 이력은 다시 쓰지 않는다(노션 링크가 커밋을 가리킨다) · 강제 push 없음 · 100 MiB 넘는 파일이 든 커밋은 만들지 않는다.
"""
import contextlib, datetime, os, re, shutil, subprocess, sys, tempfile
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
RULES_CHECK = ROOT / "workspace" / "강의제작" / "제작도구" / "검사" / "재편검사.py"
RULE_DOCS = ("workspace/강의제작/지침/", ".claude/")   # 이 아래가 바뀌면 커밋 때 재편검사를 돌린다(사실표 · 설계서도 지침 폴더 안)
RULE_FILES = {"CLAUDE.md", "AGENTS.md", "workspace/README.md"}
SIZE_LIMIT = 7_000_000_000
WORK = ROOT / "작업"
CLOUD_WORK = ROOT / "workspace" / "강의제작" / "제작도구" / "근거"   # 클라우드 작업 폴더의 부모 — VM이 회수돼도 커밋으로 남는다(CLAUDE.md 7절)
REF_SUFFIXES = {".md", ".json", ".py", ".sh", ".txt", ".csv", ".yaml", ".yml", ".mjs", ".js", ".html"}
PATHS = ["workspace", ".claude", ".codex/hooks.json", "CLAUDE.md", "AGENTS.md"]
SKIP_DIRS = {"__pycache__", ".pytest_cache", "node_modules", "worktrees", "슬라이드", "조각_저장"}   # 둘 다 도구가 다시 만든다
SKIP_FILES = {".claude/settings.local.json"}
GITHUB_FILE_LIMIT, GITHUB_FILE_WARN = 100 * 1024 ** 2, 50 * 1024 ** 2
INDEX_CFG = ("-c", "core.autocrlf=false", "-c", "core.splitIndex=false", "-c", "core.fsmonitor=false")   # 따로 색인은 이 PC 설정과 상관없이 늘 이 값으로
OLD_VERSION = re.compile(r"(?:[_-]v\d+|[_-]\d{8}|[_ -]?사본\d*| \(\d+\))$", re.I)
README = """# workspace — 작업 자료 브랜치

학생이 받는 코드는 main 브랜치다. 이 브랜치는 강의를 만들고 시스템을 고치는 사람이 쓰는 작업 자료 전부다.

- 어디부터: [workspace/README.md](workspace/README.md) — 하려는 일 → 읽을 문서 하나.
- 받기(새 PC, main을 clone한 폴더에서, Git Bash): `git fetch origin workspace` → `git show origin/workspace:workspace/동기화.py > 동기화.py` → `PYTHONUTF8=1 python 동기화.py pull` → `rm 동기화.py`.
  PowerShell의 `>`는 인코딩을 바꿀 수 있어 쓰지 않는다.
- 경로는 저장소 루트 기준 그대로다. main과 병합하지 않는다. 이력을 다시 쓰지 않는다(노션 영상 링크가 이 브랜치 커밋을 가리킨다).
- 공개 저장소다. 키 · 개인 정보 · 실물 매뉴얼 PDF를 올리지 않는다.
"""
SPEC = """# {title}

- 시작: {day} · 상태: 진행
- 확정되면 이 줄의 상태를 「확정」으로 바꾸고 `<py> workspace/동기화.py 정리 --실행`으로 이 폴더를 지운다(클라우드는 지운 것을 커밋한다).

## 의도
(왜 · 누구에게 무엇이 좋아지나)

## 하는 일
(하는 것 · 빼는 것과 까닭)

## 읽을 문서
(workspace/README.md 색인에서 고른 일 문서 — 덱 → 대본 → 영상처럼 단계가 이어지면 단계마다 하나 — 와 촬영이면 촬영/README.md와 그 도구의 촬영준비)

## 인수 조건
(그 문서의 인수 조건에서 이번에 판정할 규칙 · 행과 판정 방법)
"""
LOG = """# {title} — 기록

덧붙이지 않고 고쳐 쓴다. 지금 상태 · 남은 일 · 막힌 것만 둔다(지난 경위는 지운다).

## 지금
- {day} 시작(순서 · 지금 위치 · 다음 행동)

## 이름표
(첫 조각 전에 `앞회차.py`가 찍은 과정 용어 장부에서 이 일이 받을 이름과, 새로 풀 이름 · 처음 장 · 쓰지 않을 말 — hyd-task 3-1)

## 조각 메모
(닫힌 조각마다 다음 조각이 받을 것만 — hyd-task 3-1)

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


def local_files(need=True):
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
    if need and not any(f.startswith("workspace/") for f in files):
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


def rev(ref):
    """있으면 커밋 id, 없으면 ''(새 PC의 로컬 workspace 처럼)."""
    r = subprocess.run(["git", "rev-parse", "--verify", "-q", f"{ref}^{{commit}}"], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def is_ancestor(a, b):
    return subprocess.run(["git", "merge-base", "--is-ancestor", a, b], cwd=ROOT).returncode == 0


def fetch_origin():
    """origin의 workspace 끝 커밋. 이 저장소의 fetch 설정은 main만 받으므로 이름으로 받아 온다."""
    git("fetch", "-q", "origin", f"+refs/heads/{BRANCH}:refs/remotes/origin/{BRANCH}")
    return rev(f"refs/remotes/origin/{BRANCH}")


def check_sizes(old_tree, new_tree):
    """새 트리가 넣는 파일 판의 크기 — GitHub 한도를 넘으면 커밋 전에 이름과 크기로 멈춘다."""
    blobs = {}
    for line in git("diff-tree", "-r", "--no-renames", old_tree, new_tree).splitlines():
        meta, path = line.split("\t", 1)
        if meta.split()[3] != "0" * 40:
            blobs[path] = meta.split()[3]
    if not blobs:
        return
    sizes = dict(zip(blobs, map(int, git("cat-file", "--batch-check=%(objectsize)", inp="\n".join(blobs.values()).encode() + b"\n").split())))
    mib = lambda n: f"{n / 1024 ** 2:.1f} MiB"
    for path, size in sizes.items():
        if GITHUB_FILE_WARN < size <= GITHUB_FILE_LIMIT:
            print(f"경고 — GitHub 가 경고하는 크기(50 MiB 초과): {path} {mib(size)}")
    big = [f"{path} {mib(size)}" for path, size in sizes.items() if size > GITHUB_FILE_LIMIT]
    if big:
        sys.exit("GitHub 는 100 MiB 넘는 파일이 든 push 를 거절한다(이력은 다시 쓰지 않으므로 커밋하지 않았다) — 줄이거나 git 밖으로 옮긴다:\n  "
                 + "\n  ".join(big))


def synced_index(files, d):
    """files + 이 도구가 만드는 README.md를 담은 색인을 임시 폴더 d에 두고 그 환경을 돌려준다(commit · status · pull이 같이 쓴다).
    이 PC 전용 사본(.git/hyd-workspace.index)에서 시작해 stat이 바뀐 파일만 다시 해시한다 — 줄끝은 늘 core.autocrlf=false + .gitattributes,
    .gitattributes가 사본보다 새로우면 처음부터. 사본은 복사해 쓰고 끝나면 갈아 끼우므로 여러 세션이 함께 돌아도 lock이 부딪치지 않고,
    늦게 쓴 쪽이 이겨도 남는 것은 캐시뿐이다(내용 판정은 git의 stat 비교가 지킨다)."""
    keep = ROOT / git("rev-parse", "--git-path", "hyd-workspace.index").strip()
    index, attrs = Path(d) / "index", ROOT / ".gitattributes"
    env = dict(os.environ, GIT_INDEX_FILE=str(index))
    with contextlib.suppress(OSError):                 # 사본이 없으면 빈 색인에서(mtime을 지켜야 git이 같은 초에 고친 파일을 다시 본다)
        if not attrs.exists() or keep.stat().st_mtime > attrs.stat().st_mtime:
            shutil.copy2(keep, index)
    have = subprocess.run(["git", *INDEX_CFG, "ls-files", "-z"], cwd=ROOT, env=env, capture_output=True)
    if have.returncode:                                # 깨진 사본은 버린다
        index.unlink(missing_ok=True)
        old = set()
    else:
        old = set(filter(None, have.stdout.decode("utf-8", "replace").split("\0")))
    gone = sorted(old - set(files) - {"README.md"})    # 로컬에서 지웠거나 빼는 자리가 된 파일
    if gone:
        git(*INDEX_CFG, "update-index", "--force-remove", "-z", "--stdin", env=env, inp="".join(p + "\0" for p in gone).encode("utf-8"))
    if files:
        git(*INDEX_CFG, "update-index", "--add", "-z", "--stdin", env=env, inp="".join(p + "\0" for p in files).encode("utf-8"))
    readme = git("hash-object", "-w", "--stdin", inp=README.encode("utf-8")).strip()
    git("update-index", "--add", "--cacheinfo", f"100644,{readme},README.md", env=env)
    part = keep.with_name(f"{keep.name}.{os.getpid()}")
    with contextlib.suppress(OSError):                 # 못 갈아 끼우면(다른 세션이 읽는 중인 Windows 등) 다음에 다시 해시할 뿐이다
        shutil.copy2(index, part)
        os.replace(part, keep)
    with contextlib.suppress(OSError):
        part.unlink(missing_ok=True)
    return env


def raw_blobs(paths):
    """{경로: 파일 바이트 그대로의 블롭}(--no-filters, 객체를 쓰지 않음). 없는 파일은 뺀다."""
    have = [p for p in paths if (ROOT / p).is_file()]
    if not have:
        return {}
    return dict(zip(have, git("hash-object", "--no-filters", "--stdin-paths", inp=("\n".join(have) + "\n").encode("utf-8")).split()))


def branch_bytes(now, *branches):
    """now {경로: 블롭} 가운데 어느 브랜치 판과도 다른 것을 파일 바이트 그대로 다시 해시해, 한 판과 같으면 그 판의 블롭으로 바꾼 사본.
    브랜치에 정규화 전 바이트(CRLF 등)로 들어간 파일은 .gitattributes(text=auto eol=lf)로 해시하면 블롭이 달라진다 — 이 PC가 고친 것이 아니므로
    status는 「내용 다름」으로, pull은 「이 PC에서 고침」으로, commit은 줄끝만 바꾼 판으로 다루지 않는다."""
    odd = [n for n, b in now.items() if any(n in br for br in branches) and not any(br.get(n) == b for br in branches)]
    out = dict(now)
    for n, b in raw_blobs(odd).items():
        if any(br.get(n) == b for br in branches):
            out[n] = b
    return out


def keep_branch_bytes(env, branch, names):
    """색인에서 branch_bytes가 브랜치 판으로 본 이름을 그 블롭으로 되돌린다(커밋 트리가 줄끝만 바꾼 판을 담지 않게)."""
    now = {n: b for n, b in index_blobs(env).items() if n in set(names)}
    fix = {n: b for n, b in branch_bytes(now, branch).items() if b != now[n]}
    if fix:
        modes = {}
        for e in filter(None, git("ls-files", "-s", "-z", "--", *fix, env=env).split("\0")):
            meta, n = e.split("\t", 1)
            modes[n] = meta.split()[0]
        git(*INDEX_CFG, "update-index", "--index-info", env=env, inp="".join(f"{modes[n]} {b}\t{n}\n" for n, b in fix.items()).encode("utf-8"))
    return env


def index_blobs(env):
    """{경로: 블롭} — synced_index가 만든 색인의 판."""
    out = {}
    for e in filter(None, git("ls-files", "-s", "-z", env=env).split("\0")):
        meta, n = e.split("\t", 1)
        out[n] = meta.split()[1]
    return out


def build_tree(files, t):
    with tempfile.TemporaryDirectory() as d:
        return git("write-tree", env=keep_branch_bytes(synced_index(files, d), tree_blobs(t), files)).strip()


def scan(*args):
    return subprocess.run([sys.executable, str(SCAN), *args], cwd=ROOT).returncode == 0


def tasks():
    """열린 작업 폴더: 작업/<날짜>_<제목>/와, 스펙.md가 있는 근거/<날짜>_<제목>/(클라우드 작업 폴더 — 스펙 없는 근거 폴더는 인계 자료다)."""
    pat = "[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]_*"
    here = [p for p in WORK.glob(pat) if p.is_dir()] if WORK.is_dir() else []
    cloud = [p for p in CLOUD_WORK.glob(pat) if (p / "스펙.md").is_file()] if CLOUD_WORK.is_dir() else []
    return sorted(here + cloud, key=lambda p: p.name)


def state(task):
    spec = task / "스펙.md"
    m = re.search(r"상태:\s*(\S+)", spec.read_text(encoding="utf-8")) if spec.is_file() else None
    return m.group(1) if m else "스펙 없음"


def start(title):
    name = re.sub(r"[\\/:*?\"<>|\s]+", "-", title.strip()).strip("-")
    if not name:
        sys.exit("제목이 비었다")
    day = datetime.date.today().isoformat()
    cloud = os.environ.get("CLAUDE_CODE_REMOTE") == "true"
    d = (CLOUD_WORK if cloud else WORK) / f"{day}_{name}"
    if d.exists():
        sys.exit(f"이미 있다: {d.relative_to(ROOT).as_posix()}")
    d.mkdir(parents=True)
    (d / "스펙.md").write_text(SPEC.format(title=title.strip(), day=day), encoding="utf-8")
    (d / "기록.md").write_text(LOG.format(title=title.strip(), day=day), encoding="utf-8")
    print(f"만듦 {d.relative_to(ROOT).as_posix()}/스펙.md · 기록.md")
    if cloud:
        print(f"클라우드: 이 폴더(스펙 · 기록 · 판정 · 텍스트 실행 출력)는 조각을 닫을 때마다 커밋 · push한다. 렌더 · 영상 출력 같은 큰 중간 파일은 작업/{d.name}/에 둔다")


def behind_note(local, origin):
    """로컬 끝이 origin보다 뒤면 경고 한 줄. 클라우드 세션이 함께 올리므로 아래 차이가 옛 기준일 수 있다."""
    n = int(git("rev-list", "--count", f"{local}..{origin}").strip())
    return f"⚠ origin이 {n}커밋 앞선다({local[:8]} → {origin[:8]}) — 아래 차이는 옛 기준이다. 먼저 pull" if n else ""


def status():
    for t in tasks():
        print(f"작업 {t.name} · 상태 {state(t)}")
    t = tip()
    note = behind_note(t, fetch_origin())
    if note:
        print(note)
    remote = set(git("ls-tree", "-r", "--name-only", t).splitlines()) - {"README.md"}
    files = local_files()
    local = set(files)
    changed = changed_files(t, local & remote, files)
    print(f"workspace {t[:8]} · 로컬 {len(local)}개 · workspace {len(remote)}개 · 로컬에만 {len(local - remote)} · workspace에만 {len(remote - local)} · 내용 다름 {len(changed)}")
    for f in sorted(local - remote)[:20]: print(f"  로컬에만      {f}")
    for f in sorted(remote - local)[:20]: print(f"  workspace에만 {f}")
    for f in changed[:20]: print(f"  내용 다름     {f}")


def changed_files(t, names, files):
    """names 가운데 브랜치 끝과 내용(블롭)이 다른 로컬 파일. 커밋과 같은 색인(synced_index)으로 견주므로 바뀐 파일만 다시 해시하고,
    그 판은 .git에 쓰인다(다음 commit이 다시 쓰지 않는다)."""
    tree = tree_blobs(t)
    with tempfile.TemporaryDirectory() as d:
        now = index_blobs(keep_branch_bytes(synced_index(files, d), tree, names))
    return [f for f in sorted(names) if now[f] != tree.get(f)]


def split_only(args):
    """commit 인자를 (main 경로, --만 뒤의 workspace 경로 또는 None)으로 나눈다."""
    if "--만" not in args:
        return args, None
    i = args.index("--만")
    paths = args[i + 1:]
    if paths[:1] == ["--파일"]:          # 경로가 많아 명령 줄 길이를 넘을 때: 한 줄에 한 경로인 목록 파일
        if len(paths) != 2:
            sys.exit("--만 --파일 뒤에는 목록 파일 하나만 준다")
        paths = [l.strip() for l in Path(paths[1]).read_text(encoding="utf-8").splitlines() if l.strip()]
    if not paths:
        sys.exit("--만 뒤에 올릴 workspace 경로가 없다")
    return args[:i], [a.replace("\\", "/").rstrip("/") for a in paths]


def build_tree_only(t, paths, files):
    """브랜치 끝의 트리에서 준 경로만 지금 모습으로 바꾼다. 준 경로가 어느 쪽에도 없으면 멈춘다."""
    inside = lambda f, p: f == p or f.startswith(p + "/")
    remote = git("ls-tree", "-r", "--name-only", "-z", t).split("\0")
    add = []
    for p in paths:
        here = [f for f in files if inside(f, p)]
        if not here and not any(inside(f, p) for f in remote):
            sys.exit(f"--만 {p}: 로컬에도 workspace 브랜치에도 없다")
        add += here
    with tempfile.TemporaryDirectory() as d:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(d) / "index"))
        git("read-tree", t, env=env)
        gonelist = Path(d) / "paths"          # 경로가 많으면 명령 줄 길이(Windows 32k)를 넘으므로 목록 파일로 넘긴다
        gonelist.write_text("\n".join(paths) + "\n", encoding="utf-8")
        git("rm", "-r", "-q", "-f", "--cached", "--ignore-unmatch", f"--pathspec-from-file={gonelist}", env=env)
        if add:
            listfile = Path(d) / "list"
            listfile.write_text("\n".join(add) + "\n", encoding="utf-8")
            git("-c", "core.autocrlf=false", "add", "-f", f"--pathspec-from-file={listfile}", env=env)
            keep_branch_bytes(env, tree_blobs(t), add)
        return git("write-tree", env=env).strip()


def check_rules(old, new):
    """규칙 문서가 바뀐 커밋이면 재편검사가 오류 0이어야 붙는다 — 모양 · 없는 번호 · 사본 · 끊긴 경로가 브랜치에 올라가지 않게."""
    names = git("diff-tree", "-r", "--name-only", "-z", old, new).split("\0")
    if not any(n.startswith(RULE_DOCS) or n in RULE_FILES for n in names):
        return
    r = subprocess.run([sys.executable, str(RULES_CHECK)], cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace")
    if r.returncode:
        sys.exit(f"{r.stdout}{r.stderr}\n재편검사에 걸렸다 — 커밋하지 않았다(위 목록을 고친 뒤 다시)")


def repo_size_note():
    """push 뒤 저장소 이력 크기. 이력은 줄지 않으므로 커지는 것을 세션마다 보이게 한다(CLAUDE.md 2절의 7GB 기준)."""
    size = int(git("rev-list", "--disk-usage", "--objects", f"origin/{BRANCH}").strip())
    note = f"workspace 이력 {size / 1e9:.2f} GB"
    if size > SIZE_LIMIT:
        note += f" — {SIZE_LIMIT / 1e9:.0f} GB를 넘었다. 새 영상을 Release로 옮길지 사용자에게 묻는다"
    return note


def session_note():
    """세션 시작 때 훅이 부른다: 이 세션이 묻지 않고 알아야 할 것만 낸다. 고치는 것은 없다."""
    print("[세션 시작] 작업 순서는 스킬 hyd-task, 남은 일의 정본은 workspace/강의제작/남은일.md, 읽을 문서는 workspace/README.md 표다.")
    print("뚫은 길 · 함정 · 바뀐 값은 일을 끝내기 전에 그 문서 자리에 고쳐 쓴다(hyd-task 4절).")
    names = [t.name for t in tasks()]
    if names:
        print(f"이 PC의 작업 폴더 {len(names)}개(사용자 범위와 맞는 것의 스펙.md · 기록.md부터 읽는다): " + " · ".join(names))
    try:
        note = behind_note(tip(), fetch_origin())
    except SystemExit as e:                     # git()이 실패를 sys.exit로 낸다 — 시작을 막지 않고 못 본 것을 그대로 알린다
        print(f"origin과 견주지 못했다: {e}")
        return
    print(note or "이 PC의 workspace는 origin과 같거나 앞선다.")


def commit(msg, args):
    main_paths, only = split_only(args)
    if not is_ancestor(fetch_origin(), tip()):
        sys.exit(f"origin의 {BRANCH}가 이 PC보다 앞서 있다(다른 세션이 올렸다) — 커밋하지 않았다. 먼저 pull 한 뒤 다시")
    files = local_files()
    for g in old_versions(files):
        print("경고 — 이전 판이 함께 있다(최신 하나만 둔다): " + " · ".join(g))
    t = tip()
    tree = build_tree_only(t, only, files) if only else build_tree(files, t)
    if tree == git("rev-parse", f"{t}^{{tree}}").strip():
        print("workspace: 바뀐 것이 없다 — 커밋하지 않는다")
    else:
        check_sizes(f"{t}^{{tree}}", tree)
        check_rules(f"{t}^{{tree}}", tree)
        c = git("commit-tree", tree, "-p", t, inp=(msg.rstrip("\n") + "\n").encode("utf-8")).strip()
        if not scan(f"{t}..{c}"):
            sys.exit(f"키 검사에 걸렸다 — {c[:8]}를 workspace에 붙이지 않았다(위 목록을 고친 뒤 다시)")
        git("update-ref", f"refs/heads/{BRANCH}", c, t)
        print(f"workspace {t[:8]} → {c[:8]}")
    if main_paths:
        commit_main(msg.rstrip("\n") + "\n", main_paths)


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
    check_sizes(f"{head}^{{tree}}", tree)
    c = git("commit-tree", tree, "-p", head, inp=body.encode("utf-8")).strip()
    if not scan(f"{head}..{c}"):
        sys.exit(f"키 검사에 걸렸다 — {c[:8]}를 main에 붙이지 않았다(위 목록을 고친 뒤 다시)")
    git("update-ref", "HEAD", c, head)
    git("reset", "-q", "--", *paths)
    print(git("show", "--stat", "--format=main %h %s", "HEAD"))


def push():
    for ref in ("main", BRANCH):
        if not scan(ref, "--올릴것"):
            sys.exit(f"{ref}: 올릴 커밋에서 키 검사에 걸렸다 — push하지 않았다. 그 커밋은 이력으로 공개되므로 키를 지우는 커밋을 더해서는 풀리지 않는다 — "
                     f"올리지 않은 커밋을 다시 만들거나(강제 push 없음), 이미 퍼졌으면 그 키를 바꾼다")
    print(git("push", "origin", "main", BRANCH))
    # 이 저장소의 fetch 설정은 main만 받는다 — 두 브랜치를 이름으로 받아 와야 origin/workspace가 새 값이 된다
    git("fetch", "-q", "origin", "+refs/heads/main:refs/remotes/origin/main", f"+refs/heads/{BRANCH}:refs/remotes/origin/{BRANCH}")
    for ref in ("main", BRANCH):
        print(ref, git("rev-list", "--left-right", "--count", f"{ref}...origin/{ref}").strip())
    print(repo_size_note())


def referrers(task):
    """작업 폴더 밖의 규칙 · 작업 자료 가운데 이 폴더 경로(작업/<이름> · 근거/<이름>)를 적은 파일 — 지우면 그 링크가 끊긴다."""
    key, out = f"{task.parent.name}/{task.name}", []
    for top in (ROOT / "workspace", ROOT / ".claude", ROOT / "CLAUDE.md", ROOT / "AGENTS.md"):
        files = [top] if top.is_file() else (f for f in top.rglob("*") if f.is_file()) if top.is_dir() else []
        for f in files:
            # 같은 작업의 짝 폴더(작업/<이름> · 근거/<이름>)는 함께 지우므로 밖으로 세지 않는다
            if f.suffix in REF_SUFFIXES and not any(p.name == task.name for p in f.parents) and not SKIP_DIRS & set(f.parts):
                with contextlib.suppress(OSError, UnicodeDecodeError):
                    if key in f.read_text(encoding="utf-8"):
                        out.append(f.relative_to(ROOT).as_posix())
    return out


def clean(run):
    done = [t for t in tasks() if state(t) == "확정"]
    for t in tasks():
        if t not in done:
            print(f"남김 {t.name}(상태 {state(t)})")
    for t in done:
        refs = referrers(t)
        if refs:
            print(f"못 지움 {t.name} — 폴더 밖에서 가리킨다(정본에 쓸 것은 정본 자리로 옮기고 링크를 지운 뒤 다시): " + " · ".join(refs[:10]))
            continue
        if run:
            shutil.rmtree(t)
            print(f"지움 {t.name}")
        else:
            print(f"지울 것 {t.name} — `정리 --실행`으로 지운다")
    if not done:
        print("확정된 작업 폴더가 없다")


def tree_blobs(ref):
    """{경로: 블롭} — 브랜치 맨 앞 README.md(이 도구가 만드는 것)는 뺀다."""
    out = {}
    for e in filter(None, git("ls-tree", "-r", "-z", ref).split("\0")):
        meta, n = e.split("\t", 1)
        if n != "README.md" and meta.split()[1] == "blob":
            out[n] = meta.split()[2]
    return out


def worktree_blobs(paths):
    """{경로: 지금 파일을 git 에 넣으면 될 블롭} — 커밋(build_tree)과 같은 설정(core.autocrlf=false + .gitattributes)으로 계산한다.
    이 PC의 git 설정(Windows 기본 autocrlf=true)을 따르면 줄끝만 다른 같은 파일을 「고친 판」으로 본다. 없는 파일은 뺀다."""
    have = [p for p in paths if (ROOT / p).is_file()]
    if not have:
        return {}
    out = git("-c", "core.autocrlf=false", "hash-object", "--stdin-paths", inp=("\n".join(have) + "\n").encode("utf-8")).split()
    return dict(zip(have, out))


def pull():
    remote, local = fetch_origin(), rev(f"refs/heads/{BRANCH}")
    if not remote:
        sys.exit(f"origin 에 {BRANCH} 브랜치가 없다")
    if local == remote:
        print(f"workspace {local[:8]} = origin — 받을 것이 없다")
        return
    if local and is_ancestor(remote, local):
        sys.exit(f"로컬 workspace({local[:8]})가 origin 보다 앞서 있다 — 받을 것이 없고, 올리지 않은 커밋은 push 로 올린다")
    fork = local if not local or is_ancestor(local, remote) else git("merge-base", local, remote).strip()
    mine, theirs = (tree_blobs(local) if local else {}), tree_blobs(remote)
    base = tree_blobs(fork) if fork else {}
    names = sorted(set(theirs) | set(mine) | set(base))
    with tempfile.TemporaryDirectory() as d:          # 작업 자료는 커밋과 같은 색인의 판, 그 밖(빼는 자리 · main 파일)은 바로 해시
        known = index_blobs(synced_index(local_files(need=False), d))
    now = branch_bytes({n: known[n] for n in names if n in known} | worktree_blobs([n for n in names if n not in known]), mine, theirs, base)
    write, delete, clash = [], [], []
    for n in names:
        cur, old, new, was = now.get(n), mine.get(n), theirs.get(n), base.get(n)
        if cur == new or new == was:
            continue                                   # 이미 원격 판이거나 원격이 안 바꿈 — 이 PC의 판(미커밋 · 올리지 않은 커밋)은 디스크에 그대로 둔다
        if cur == old == was and (local or cur is None):
            (delete if new is None else write).append(n)   # 이 PC는 손대지 않았고 원격이 바꿈(새 PC는 없는 파일 전부)
        elif new is None:
            clash.append(f"{n} — 원격에서 지웠는데 이 PC(디스크 · 올리지 않은 커밋)에서 바꿨다")
        elif cur is None:
            clash.append(f"{n} — 이 PC에서 지웠는데 원격에서 고쳤다")
        else:
            clash.append(f"{n} — 이 PC 판과 원격 판이 둘 다 바뀌었다")
    if clash:
        sys.exit("겹치는 파일이 있어 아무것도 쓰지 않았다. 이 PC의 판을 작업 폴더에 복사해 두고 그 파일을 원격 판(`git show origin/workspace:<경로>`, 원격이 지웠으면 치움)으로 "
                 "바꾼 뒤 다시 받아 두 판을 합친다:\n  " + "\n  ".join(clash[:50]))
    # Windows tar는 한글 경로를 못 푼다 — cat-file --batch로 파일을 직접 꺼낸다
    cat = subprocess.Popen(["git", "cat-file", "--batch"], cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    for n in write:
        cat.stdin.write(f"{theirs[n]}\n".encode()); cat.stdin.flush()
        size = int(cat.stdout.readline().split()[2])
        data = cat.stdout.read(size); cat.stdout.read(1)
        p = ROOT / n
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    cat.stdin.close(); cat.wait()
    for n in delete:
        (ROOT / n).unlink()
    git("update-ref", f"refs/heads/{BRANCH}", remote, *([local] if local else []))
    print(f"workspace {local[:8] or '(없음)'} → origin {remote[:8]} — 쓴 파일 {len(write)} · 지운 파일 {len(delete)}")
    if fork != local:                                  # 갈라졌던 경우: 올리지 않은 커밋은 브랜치에서 빠지고 그 파일은 디스크에 남아 다음 commit에 들어간다
        print(f"올리지 않은 커밋(브랜치에서 빠짐, `git show <id>`로 볼 수 있음 — 메시지는 다음 commit에 다시 쓴다):\n" + git("log", "--format=  %h %s", f"{fork}..{local}"))
        print("그 커밋이 바꾼 파일(디스크에 그대로, 다음 commit에 들어간다 — --만이면 이 경로를 준다):\n  " + "\n  ".join(git("diff", "--name-only", fork, local).splitlines()))


if __name__ == "__main__":
    cmd, args = sys.argv[1:2], sys.argv[2:]
    if cmd and cmd[0] in ("status", "commit", "push", "pull") and git("rev-parse", "--abbrev-ref", "HEAD").strip() == BRANCH:
        sys.exit(f"{BRANCH} 브랜치 체크아웃에서는 {cmd[0]}을 쓰지 않는다 — 이 도구는 main 체크아웃에 {BRANCH}를 겹쳐 쓰는 PC 전용이다. 클라우드 세션은 CLAUDE.md 7절의 일반 git으로 한다")
    if cmd == ["시작"] and args: start(" ".join(args))
    elif cmd == ["status"]: status()
    elif cmd == ["commit"] and args: commit(args[0], args[1:])
    elif cmd == ["push"]: push()
    elif cmd == ["정리"]: clean("--실행" in args)
    elif cmd == ["pull"]: pull()
    elif cmd == ["세션"]: session_note()
    else: sys.exit(__doc__)
