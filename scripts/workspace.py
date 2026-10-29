"""workspace 브랜치(코드 없는 강의 자료 브랜치)를 브랜치를 바꾸지 않고 다룬다.

    python scripts/workspace.py status            # 로컬 자료와 workspace 끝의 차이
    python scripts/workspace.py commit "메시지"   # 로컬 자료로 workspace 위에 새 커밋(키 검사 0이어야 함, push는 하지 않음)
    python scripts/workspace.py pull              # origin/workspace를 받아 로컬 자료 자리에 푼다(덮어쓰지 않을 파일이 있으면 멈춤)

- 자료 자리는 아래 PATHS 두 곳이고, main에서는 git이 무시한다. 경로는 main 폴더에서 도구가 읽는 자리와 같다.
- workspace는 main과 이력을 공유하지 않고 병합하지 않는다. 노션 영상 링크가 workspace 커밋을 가리키므로
  커밋은 늘 앞 커밋 위에 쌓고(이력을 다시 쓰지 않음) 브랜치를 지우지 않는다.
- 공유 체크아웃이라 체크아웃 · 색인을 건드리지 않는다(임시 색인 GIT_INDEX_FILE로 커밋을 만든다).
- push는 사람이 정한다: `git push origin workspace`.
"""
import hashlib, os, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATHS = ["course/videos", "제작용/기존제작/tools/video/음성_저장"]
KEEP_MAIN = {"course/videos/README.md", "course/videos/.gitignore"}   # main이 추적하는 안내 — workspace에는 넣지 않는다
BRANCH = "workspace"


def git(*a, env=None, inp=None):
    r = subprocess.run(["git", "-c", "core.quotepath=false", *a], cwd=ROOT, env=env, input=inp, capture_output=True)
    if r.returncode:
        sys.exit(f"git {' '.join(a[:3])}: {r.stderr.decode('utf-8', 'replace').strip()}")
    return r.stdout.decode("utf-8", "replace")


def local_files():
    out = git("ls-files", "-o", "-i", "--exclude-standard", "--", *PATHS)
    files = [f for f in out.splitlines() if f and f not in KEEP_MAIN]
    if not files:
        sys.exit(f"로컬 자료가 없다: {PATHS} — 먼저 `python scripts/workspace.py pull`")
    return files


def tip():
    return git("rev-parse", "--verify", "-q", f"refs/heads/{BRANCH}").strip()


def status():
    t = tip()
    remote = set(git("ls-tree", "-r", "--name-only", t).splitlines()) - {"README.md"}
    local = set(local_files())
    print(f"workspace {t[:8]} · 로컬 {len(local)}개 · workspace {len(remote)}개")
    for f in sorted(local - remote): print(f"  로컬에만  {f}")
    for f in sorted(remote - local): print(f"  workspace에만  {f}")


def commit(msg):
    t = tip()
    readme = git("rev-parse", f"{t}:README.md").strip()
    with tempfile.TemporaryDirectory() as d:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(d) / "index"))
        git("read-tree", "--empty", env=env)
        listfile = Path(d) / "list"
        listfile.write_text("\n".join(local_files()) + "\n", encoding="utf-8")
        git("-c", "core.autocrlf=false", "add", "-f", f"--pathspec-from-file={listfile}", env=env)
        git("update-index", "--add", "--cacheinfo", f"100644,{readme},README.md", env=env)
        tree = git("write-tree", env=env).strip()
    if tree == git("rev-parse", f"{t}^{{tree}}").strip():
        sys.exit("바뀐 것이 없다 — 커밋하지 않는다")
    c = git("commit-tree", tree, "-p", t, inp=(msg + "\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n").encode()).strip()
    scan = subprocess.run([sys.executable, str(ROOT / "scripts" / "secret_scan.py"), c], cwd=ROOT)
    if scan.returncode:
        sys.exit(f"키 검사에 걸렸다 — {c[:8]}를 workspace에 붙이지 않았다(위 목록을 고친 뒤 다시)")
    git("update-ref", f"refs/heads/{BRANCH}", c, t)
    print(f"workspace {t[:8]} → {c[:8]} (push: git push origin {BRANCH})")


def pull():
    git("fetch", "-q", "origin", f"+refs/heads/{BRANCH}:refs/remotes/origin/{BRANCH}")
    ref = f"refs/remotes/origin/{BRANCH}"
    blobs = {}
    for e in filter(None, git("ls-tree", "-r", "-z", ref).split("\0")):
        meta, n = e.split("\t", 1)
        if n != "README.md":
            blobs[n] = meta.split()[2]
    names = list(blobs)
    def blob_sha(p):                                   # git hash-object와 같은 값(파일마다 git을 부르지 않으려고)
        data = p.read_bytes()
        return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()
    clash = [n for n in names if (ROOT / n).exists() and blob_sha(ROOT / n) != blobs[n]]
    if clash:
        sys.exit("로컬이 workspace와 다른 파일이 있어 덮어쓰지 않는다(먼저 commit하거나 그 파일을 치운다):\n  " + "\n  ".join(clash))
    # Windows tar는 한글 경로를 못 푼다 — cat-file --batch로 파일을 직접 꺼낸다
    cat = subprocess.Popen(["git", "cat-file", "--batch"], cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    written = 0
    for n in names:
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
    print(f"origin/{BRANCH} {git('rev-parse', '--short', ref).strip()} → 로컬 자료 {len(names)}개(새로 쓴 것 {written})")


if __name__ == "__main__":
    cmd = sys.argv[1:2]
    if cmd == ["status"]: status()
    elif cmd == ["commit"] and len(sys.argv) > 2: commit(sys.argv[2])
    elif cmd == ["pull"]: pull()
    else: sys.exit(__doc__)
