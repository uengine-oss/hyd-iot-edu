#!/bin/bash
# 언제: 클라우드 환경(claude.ai/code → 환경 편집 → Setup script)이 세션 VM을 준비할 때. 세션이 이 PC와 같은 훅 · 지침 · 도구로 시작한다.
# 명령: bash workspace/개발/scripts/cloud_setup.sh
#   세션을 main으로 시작하면 이 파일이 아직 없다 — 그 칸에는: git fetch -q --depth 1 origin workspace && git show FETCH_HEAD:workspace/개발/scripts/cloud_setup.sh | bash
# 하는 일: 렌더 · 영상 도구 → (main 체크아웃이면) workspace 브랜치 파일을 제자리에 풀고 로컬 workspace 끝을 맞춤(= 동기화.py pull 결과, .claude 훅이 세션 시작부터 켜진다)
#   → 제작용 파이썬 패키지 · Playwright 크로미움. 공용 헌법 · 스킬은 세션마다 .claude/hooks/cloud-bootstrap.sh 훅이 받는다.
# 늘 0으로 끝낸다(0이 아니면 세션이 안 뜬다). 실패는 ~/.claude/CLAUDE.md에 적어 Claude가 사용자에게 먼저 알리게 한다.
cd "$(dirname "$0")" 2>/dev/null
ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
LOG=/tmp/cloud_setup.log
fail=""
step() {
  "$@" >"$LOG" 2>&1 || fail="$fail
- $* 실패: $(tail -n 2 "$LOG" | tr '\n' ' ')"
}

step apt-get update -qq
step apt-get install -y -qq --no-install-recommends ffmpeg poppler-utils libreoffice-impress fonts-noto-cjk

if [ -z "$ROOT" ]; then
  fail="$fail
- 저장소 폴더를 찾지 못했다(현재 $(pwd)) — workspace 풀기 · 파이썬 패키지를 건너뜀"
else
  cd "$ROOT"
  if [ "$(git rev-parse --abbrev-ref HEAD)" != workspace ] && [ ! -f workspace/동기화.py ]; then
    IDX=$(mktemp -u)
    step git fetch -q --depth 1 origin +refs/heads/workspace:refs/remotes/origin/workspace
    # 따로 색인으로 풀어 main의 색인은 그대로 둔다. 브랜치 맨 앞 README.md(그 브랜치 소개)는 main의 README를 덮지 않게 뺀다.
    step env GIT_INDEX_FILE="$IDX" git checkout origin/workspace -- workspace .claude .codex CLAUDE.md AGENTS.md
    step git update-ref refs/heads/workspace origin/workspace
    rm -f "$IDX"
  fi
  REQ=workspace/requirements-dev.txt
  if [ -f "$REQ" ] && sed -n '/개발 · 제작 도구만/,$p' "$REQ" > /tmp/req.txt && [ -s /tmp/req.txt ]; then
    step pip install -q --break-system-packages -r /tmp/req.txt   # 서비스 요구 파일(-r ../it/…) 줄은 빼고 제작 도구 줄만
    step python3 -m playwright install --with-deps chromium
  else
    fail="$fail
- $ROOT/$REQ 의 「개발 · 제작 도구만」 줄을 찾지 못해 파이썬 도구를 깔지 않았다"
  fi
fi

NOTE="$HOME/.claude/CLAUDE.md"
mkdir -p "$HOME/.claude"
if [ -n "$fail" ]; then
  printf '# 클라우드 셋업 실패 — 사용자에게 먼저 알린다(cloud_setup.sh가 쓴다)\n%s\n' "$fail" > "$NOTE"
elif head -n 1 "$NOTE" 2>/dev/null | grep -q 'cloud_setup.sh가 쓴다'; then
  rm -f "$NOTE"
fi
exit 0
