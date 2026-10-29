"""git 트리(브랜치 · 커밋)에 키가 들어 있는지 찾는다. 공개 브랜치에 올리기 전에 돌린다.

    python workspace/secret_scan.py <브랜치|커밋> [--key-file 경로 ...]

- 모든 텍스트 파일에서 알려진 키 꼴(ElevenLabs · OpenAI · Anthropic · GitHub · Notion · AWS)과 개인 키 블록을 찾는다.
- 설정 파일(.env · .md · .json · .yaml · .toml · .ini · .cfg · .txt)에서는 값이 든 `…KEY= / …TOKEN= / …SECRET= / …PASSWORD=` 줄도 찾는다.
  코드 파일의 변수 대입(`token = uuid4()` 등)은 키 꼴로만 판정한다.
- `.env` 파일에서 이름에 KEY · TOKEN · SECRET · PASSWORD가 든 변수에 값이 있으면 찾는다(빈 틀 · 모델 이름 같은 일반 설정은 통과).
- 값에 test · fake · dummy · example · placeholder · change · your · literal 이 들어 있으면 시험용 가짜로 보고 뺀다.
- `--key-file`(또는 환경변수 HYD_ELEVENLABS_KEY_FILE · HYD_VSCODE_TOKEN_FILE)을 주면 그 파일의 실제 값이 들어 있는지도 견준다.
  값은 이 프로세스 안에서만 읽고 어디에도 찍지 않는다(걸린 곳은 경로 · 줄 번호만).
- 일부러 둔 로컬 기본값은 그 줄에 `키검사: 허용`과 까닭을 적으면 뺀다(외부 서비스 키에는 쓰지 않는다).
- `.zip`은 열어서 안의 파일도 같은 규칙으로 본다(학생 패키지 ZIP 속 `.env` · 설정). 걸린 곳은 `묶음.zip!안/경로:줄`로 찍는다.
- 걸린 곳이 하나라도 있으면 종료 코드 1, 없으면 0.
"""
import io, os, re, subprocess, sys, zipfile

KEY_SHAPES = [
    ("ElevenLabs 키", re.compile(rb"\bsk_[0-9a-f]{40,}\b")),
    ("OpenAI 키", re.compile(rb"\bsk-(?:proj-)?[A-Za-z0-9_\-]{20,}")),
    ("Anthropic 키", re.compile(rb"\bsk-ant-[A-Za-z0-9_\-]{20,}")),
    ("GitHub 토큰", re.compile(rb"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}|\bgithub_pat_[A-Za-z0-9_]{30,}")),
    ("Notion 토큰", re.compile(rb"\b(?:secret|ntn)_[A-Za-z0-9]{40,}")),
    ("AWS 키", re.compile(rb"\bAKIA[0-9A-Z]{16}\b")),
    ("개인 키", re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
]
KEY_LINE = re.compile(rb"(?im)^[ \t]*(?:export[ \t]+)?[A-Z0-9_]*(?:API_KEY|TOKEN|SECRET|PASSWORD)[ \t]*[=:][ \t]*[\"']?([^\s\"'#]{8,})")
ENV_VALUE = re.compile(rb"(?im)^[ \t]*(?:export[ \t]+)?[A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD)[A-Z0-9_]*[ \t]*=[ \t]*[\"']?([^\s\"'#]+)")
FAKE = re.compile(rb"(?i)test|fake|dummy|example|placeholder|change|your|literal|<|\$\{")
ALLOW = re.compile(r"키검사:\s*허용".encode())   # 일부러 둔 로컬 기본값 줄에 까닭과 함께 단다
CONFIG = (".md", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".txt", ".conf", ".properties")
BINARY = (".mp4", ".mp3", ".wav", ".flac", ".webm", ".png", ".jpg", ".jpeg", ".gif", ".pdf", ".pptx", ".xlsx", ".docx")


def is_env(name):
    base = name.rsplit("/", 1)[-1]
    return base == ".env" or (base.startswith(".env.") and base != ".env.example")


def git(*a):
    return subprocess.run(["git", "-c", "core.quotepath=false", *a], capture_output=True, check=True).stdout


def line_of(body, pos):
    return body.count(b"\n", 0, pos) + 1


def scan(name, body, secrets):
    """한 파일(또는 ZIP 안 한 파일)에서 걸린 곳 수를 센다."""
    if name.lower().endswith(".zip"):
        hits = 0
        with zipfile.ZipFile(io.BytesIO(body)) as z:
            for info in z.infolist():
                if not info.is_dir() and not info.filename.lower().endswith(BINARY):
                    hits += scan(f"{name}!{info.filename}", z.read(info), secrets)
        return hits
    found = []
    allowed = {line_of(body, m.start()) for m in ALLOW.finditer(body)}
    for label, rx in KEY_SHAPES:
        found += [(m.start(), label) for m in rx.finditer(body) if not FAKE.search(m.group(0))]
    if is_env(name):
        found += [(m.start(), ".env에 든 값") for m in ENV_VALUE.finditer(body) if not FAKE.search(m.group(1))]
    elif name.lower().endswith(CONFIG):
        found += [(m.start(), "값이 든 키 줄") for m in KEY_LINE.finditer(body) if not FAKE.search(m.group(1))]
    for f, v in secrets:
        if v in body:
            found.append((body.index(v), f"키 파일({os.path.basename(f)})의 실제 값"))
    hits = 0
    for pos, label in found:
        if line_of(body, pos) in allowed and not label.startswith("키 파일"):
            continue
        print(f"{name}:{line_of(body, pos)}: {label}"); hits += 1
    return hits


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    ref, key_files = args[0], []
    while "--key-file" in args:
        i = args.index("--key-file"); key_files.append(args[i + 1]); del args[i:i + 2]
    key_files += [os.environ[v] for v in ("HYD_ELEVENLABS_KEY_FILE", "HYD_VSCODE_TOKEN_FILE") if os.environ.get(v)]
    secrets = []
    for f in key_files:
        if not os.path.isfile(f):
            sys.exit(f"키 파일이 없다: {f}")
        v = open(f, "rb").read().strip()
        if len(v) < 8:
            sys.exit(f"키 파일 값이 너무 짧다: {f}")
        secrets.append((f, v))
    files = []
    for e in filter(None, git("ls-tree", "-r", "-z", ref).split(b"\0")):
        meta, path = e.split(b"\t", 1)
        name = path.decode("utf-8", "replace")
        if not name.lower().endswith(BINARY):
            files.append((name, meta.split()[2].decode()))
    hits = 0
    # 파일마다 git을 부르면 수천 개에서 몇 분이 걸린다 — cat-file --batch 하나로 읽는다
    cat = subprocess.Popen(["git", "cat-file", "--batch"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    for name, sha in files:
        cat.stdin.write(sha.encode() + b"\n"); cat.stdin.flush()
        size = int(cat.stdout.readline().split()[2])
        body = cat.stdout.read(size); cat.stdout.read(1)
        hits += scan(name, body, secrets)
    print(f"{ref}: 걸린 곳 {hits}")
    sys.exit(1 if hits else 0)


if __name__ == "__main__":
    main()
