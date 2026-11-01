"""git 에 키가 들어 있는지 찾는다. 공개 브랜치에 올리기 전에 돈다(workspace/동기화.py 의 commit · push 가 부른다).

    python workspace/secret_scan.py <브랜치|커밋>            # 그 커밋의 트리 전부(지금 모습 점검)
    python workspace/secret_scan.py <앞>..<뒤>               # 앞에 없던 커밋마다 새로 들어온 파일 판과 그 커밋 메시지(커밋 전 검사)
    python workspace/secret_scan.py <브랜치> --올릴것         # origin 에 아직 없는 커밋 전부(push 전 검사 — 처음 올리는 브랜치는 이력 전부)
        [--key-file 경로 ...]

- 검사 단위: push 는 끝 트리가 아니라 그 사이 커밋 하나하나를 본다 — 키를 넣은 커밋 뒤에 지우는 커밋을 더해도 앞 커밋이 이력으로 공개되기 때문이다.
- 모든 텍스트에서 알려진 키 꼴(ElevenLabs · OpenAI · Anthropic · GitHub · Notion · AWS)과 개인 키 블록을 찾는다.
- 코드가 아닌 모든 텍스트(설정 · 문서 · 셸 · 배치 · SQL · `.env.example` …)에서 값이 든 `…API_KEY / …TOKEN / …SECRET / …PASSWORD` 이름 줄을
  찾는다(`이름=값` · `이름: 값` · JSON `"이름": "값"` · 목록 `- 이름=값` · `export` · `set` · `$env:`). 이름은 대문자(환경 변수 꼴)만,
  `${SECRET:이름}` · `${이름:-기본}` 같은 자리표시와 낱말뿐인 값(변수 이름)은 값으로 보지 않는다. 코드 파일(CODE)의 대입은 키 꼴과 아래
  실제 값 견주기로만 본다(`token = uuid4()` · 테스트의 가짜 값을 키로 세지 않게).
- `.env` 파일에서는 이름에 KEY · TOKEN · SECRET · PASSWORD 가 든 변수에 값이 있으면 찾는다(빈 틀 · 모델 이름 같은 일반 설정은 통과).
- 값에 test · fake · dummy · example · placeholder · change · your · literal 이 들어 있으면 시험용 가짜로 보고 뺀다.
- 실제 값 견주기: 저장소 루트 `.env` 의 KEY · TOKEN · SECRET · PASSWORD 이름 값(강의 중계 키 · 이 PC 확인 값)과 `--key-file`(또는 환경 변수
  HYD_ELEVENLABS_KEY_FILE · HYD_VSCODE_TOKEN_FILE)의 값이 들어 있는지도 본다 — 키 꼴이 바뀌어도 잡힌다. 값은 이 프로세스 안에서만 읽고
  어디에도 찍지 않는다(걸린 곳은 경로 · 줄 번호만). `.env` 는 시작과 같은 해석기(scripts/hyd_env.py)로 읽는다.
- 일부러 둔 로컬 기본값은 그 줄에 `키검사: 허용`과 까닭을 적으면 뺀다(외부 서비스 키 · 실제 값 견주기에는 쓰지 않는다).
- `.zip` · `.gz`(AI 녹화)는 풀어서 안의 파일도 같은 규칙으로 본다. 걸린 곳은 `묶음.zip!안/경로:줄` · `녹화.json.gz!:줄`로 찍는다.
- 걸린 곳이 하나라도 있으면 종료 코드 1, 없으면 0. git 이 그 이름을 모르면 까닭을 내고 2.
"""
import gzip, io, os, re, subprocess, sys, zipfile
from pathlib import Path

KEY_SHAPES = [
    ("ElevenLabs 키", re.compile(rb"\bsk_[0-9a-f]{40,}\b")),
    ("OpenAI 키", re.compile(rb"\bsk-(?:proj-)?[A-Za-z0-9_\-]{20,}")),
    ("Anthropic 키", re.compile(rb"\bsk-ant-[A-Za-z0-9_\-]{20,}")),
    ("GitHub 토큰", re.compile(rb"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}|\bgithub_pat_[A-Za-z0-9_]{30,}")),
    ("Notion 토큰", re.compile(rb"\b(?:secret|ntn)_[A-Za-z0-9]{40,}")),
    ("AWS 키", re.compile(rb"\bAKIA[0-9A-Z]{16}\b")),
    ("개인 키", re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
]
# 이름 줄: 대문자 환경 변수 이름 · 따옴표 · 목록 · export/set/$env: 머리, = 또는 : 뒤의 값(8자 이상, 식 · 호출은 아래 is_literal 이 거른다)
KEY_LINE = re.compile(rb"(?<![A-Za-z0-9_{])(?:\$env:)?[\"']?([A-Z0-9_]*(?:API_KEY|TOKEN|SECRET|PASSWORD))[\"']?[ \t]*[=:][ \t]*[\"']?([^\s\"'#,;]{8,})")
ENV_VALUE = re.compile(rb"(?im)^[ \t]*(?:export[ \t]+)?[A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD)[A-Z0-9_]*[ \t]*=[ \t]*[\"']?([^\s\"'#]+)")
FAKE = re.compile(rb"(?i)test|fake|dummy|example|placeholder|change|your|literal|<|\$\{|\$\(")
ALLOW = re.compile(r"키검사:\s*허용".encode())   # 일부러 둔 로컬 기본값 줄에 까닭과 함께 단다
SECRET_NAME = re.compile(r"KEY|TOKEN|SECRET|PASSWORD")
CODE = (".py", ".js", ".mjs", ".ts", ".jsx", ".tsx", ".css", ".html", ".htm")
BINARY = (".mp4", ".mp3", ".wav", ".flac", ".webm", ".png", ".jpg", ".jpeg", ".gif", ".pdf", ".pptx", ".xlsx", ".docx",
          ".ico", ".woff", ".woff2", ".ttf", ".otf")


def is_env(name):
    base = name.rsplit("/", 1)[-1]
    return base == ".env" or (base.startswith(".env.") and base != ".env.example")


def is_literal(body, m):
    """이름 줄의 값이 글자 그대로의 값인가 — 식(`os.environ[`, `getenv(`) · 변수 치환 · 템플릿이면 아니다."""
    value, after = m.group(2), body[m.end(2):m.end(2) + 1]
    shown = value.decode("utf-8", "replace")
    return (after not in (b"(", b"[") and not FAKE.search(value) and not re.search(rb"[(\[{$%]", value)
            and not re.fullmatch(rb"[A-Za-z_]+", value)            # 낱말뿐 = 변수 · 상수 이름
            and not set(shown) <= set("*＊•●·"))                   # 화면에 가린 값(******** · ＊＊＊＊)


def git(*a, check=True):
    r = subprocess.run(["git", "-c", "core.quotepath=false", *a], capture_output=True)
    if check and r.returncode:
        sys.stderr.write(f"git {' '.join(a)}: {r.stderr.decode('utf-8', 'replace').strip() or '이 이름 · 범위를 git 이 모른다'}\n")
        sys.exit(2)
    return r.stdout


def line_of(body, pos):
    return body.count(b"\n", 0, pos) + 1


def scan(name, body, secrets):
    """한 파일(또는 묶음 안 한 파일 · 커밋 메시지)에서 걸린 곳 수를 센다. 걸린 곳은 경로:줄만 찍는다."""
    lower = name.lower()
    if lower.endswith(".zip"):
        hits = 0
        with zipfile.ZipFile(io.BytesIO(body)) as z:
            for info in z.infolist():
                if not info.is_dir() and not info.filename.lower().endswith(BINARY):
                    hits += scan(f"{name}!{info.filename}", z.read(info), secrets)
        return hits
    if lower.endswith(".gz"):
        return scan(f"{name}!", gzip.decompress(body), secrets)
    found = []
    allowed = {line_of(body, m.start()) for m in ALLOW.finditer(body)}
    for label, rx in KEY_SHAPES:
        found += [(m.start(), label, True) for m in rx.finditer(body) if not FAKE.search(m.group(0))]
    if not lower.endswith(CODE):
        found += [(m.start(), "값이 든 키 이름 줄", True) for m in KEY_LINE.finditer(body) if is_literal(body, m)]
    if is_env(name):
        found += [(m.start(), ".env에 든 값", True) for m in ENV_VALUE.finditer(body) if not FAKE.search(m.group(1))]
    for label, value in secrets:
        start = body.find(value)
        while start >= 0:
            found.append((start, f"{label}의 실제 값", False))
            start = body.find(value, start + 1)
    hits, seen = 0, set()
    for pos, label, can_allow in sorted(found):
        line = line_of(body, pos)
        if (can_allow and line in allowed) or (line, label) in seen:
            continue
        seen.add((line, label))
        print(f"{name}:{line}: {label}"); hits += 1
    return hits


def env_secrets(root: Path):
    """저장소 루트 .env 의 비밀 이름 값(8자 이상) — 시작과 같은 해석기로 읽는다."""
    env = root / ".env"
    if not env.is_file():
        return []
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import hyd_env
    try:
        values = hyd_env.read(env)
    except (hyd_env.EnvFileError, UnicodeDecodeError) as exc:     # 글에 값은 들어가지 않는다(줄 번호 · 이름 · 바이트 위치)
        sys.exit(f"{env}: 읽지 못해 실제 값 견주기를 할 수 없다 — {exc}")
    return [(f".env의 {k}", v.encode("utf-8")) for k, v in values.items() if SECRET_NAME.search(k) and len(v.strip()) >= 8]


def tree_files(ref):
    """(경로, 블롭) — 그 커밋의 트리 전부."""
    out = []
    for e in filter(None, git("ls-tree", "-r", "-z", ref).split(b"\0")):
        meta, path = e.split(b"\t", 1)
        if meta.split()[1] == b"blob":
            out.append((path.decode("utf-8", "replace"), meta.split()[2].decode()))
    return out


def range_files(*rev):
    """(경로, 블롭) — 범위(git rev-list 인자)의 커밋마다 새로 들어온 · 바뀐 파일 판(지운 것 제외), 그리고 커밋 목록."""
    commits = git("rev-list", "--reverse", *rev, "--").decode().split()     # -- : 브랜치 workspace 와 폴더 workspace/ 가 같은 이름이다
    out = []
    for c in commits:
        tokens = git("diff-tree", "-r", "-z", "-m", "--no-renames", "--no-commit-id", "--root", c).split(b"\0")
        i = 0
        while i < len(tokens):
            if tokens[i].startswith(b":"):
                meta, path = tokens[i].split(), tokens[i + 1].decode("utf-8", "replace")
                if meta[4] != b"D" and meta[1] not in (b"160000",):
                    out.append((path, meta[3].decode()))
                i += 2
            else:
                i += 1
    return list(dict.fromkeys(out)), commits


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    key_files = []
    while "--key-file" in args:
        i = args.index("--key-file"); key_files.append(args[i + 1]); del args[i:i + 2]
    pending = "--올릴것" in args
    if pending:
        args.remove("--올릴것")
    ref = args[0]
    key_files += [os.environ[v] for v in ("HYD_ELEVENLABS_KEY_FILE", "HYD_VSCODE_TOKEN_FILE") if os.environ.get(v)]
    secrets = []
    for f in key_files:
        if not os.path.isfile(f):
            sys.exit(f"키 파일이 없다: {f}")
        v = open(f, "rb").read().strip()
        if len(v) < 8:
            sys.exit(f"키 파일 값이 너무 짧다: {f}")
        secrets.append((f"키 파일({os.path.basename(f)})", v))
    secrets += env_secrets(Path(git("rev-parse", "--show-toplevel").decode().strip()))
    if pending:
        git("rev-parse", "--verify", "-q", f"{ref}^{{commit}}")
        files, commits = range_files(ref, "--not", "--remotes=origin")
    elif ".." in ref:
        files, commits = range_files(ref)
    else:
        git("rev-parse", "--verify", "-q", f"{ref}^{{commit}}")
        files, commits = tree_files(ref), []
    files = [(n, s) for n, s in files if not n.lower().endswith(BINARY)]
    hits = 0
    # 파일마다 git 을 부르면 수천 개에서 몇 분이 걸린다 — cat-file --batch 하나로 읽는다
    cat = subprocess.Popen(["git", "cat-file", "--batch"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    for name, sha in [(n, s) for n, s in files] + [(f"커밋 {c[:8]} 메시지", c) for c in commits]:
        cat.stdin.write(sha.encode() + b"\n"); cat.stdin.flush()
        kind, size = cat.stdout.readline().split()[1:3]
        body = cat.stdout.read(int(size)); cat.stdout.read(1)
        if kind == b"commit":
            body = body.split(b"\n\n", 1)[-1]
        hits += scan(name, body, secrets)
    cat.stdin.close(); cat.wait()
    what = f"커밋 {len(commits)}개의 새 파일 판 {len(files)}개" if pending or ".." in ref else f"파일 {len(files)}개"
    print(f"{ref}: {what} · 걸린 곳 {hits}")
    sys.exit(1 if hits else 0)


if __name__ == "__main__":
    main()
