#!/bin/bash
# 클라우드 환경의 「셋업 스크립트」 칸에 이 파일 내용을 그대로 붙여 넣는다(claude.ai/code → 환경 편집 → Setup script).
# 세션마다 설치를 되풀이하지 않게 VM을 한 번 준비한다. 약 5분 안에 끝나면 스냅샷으로 저장되어 약 7일 재사용된다.
# 0이 아닌 값으로 끝나면 세션이 안 뜨므로 늘 0으로 끝내되, 실패는 ~/.claude/CLAUDE.md에 적어 Claude가 사용자에게 먼저 알리게 한다.
REQ_URL="${HYD_REQ_URL:-https://raw.githubusercontent.com/uengine-oss/hyd-iot-edu/workspace/workspace/requirements-dev.txt}"
fail=""
step() {
  if ! "$@" >/tmp/cloud_setup.log 2>&1; then
    fail="$fail
- $1 실패: $(tail -n 1 /tmp/cloud_setup.log)"
  fi
}

step apt-get update -qq
step apt-get install -y -qq --no-install-recommends ffmpeg poppler-utils libreoffice-impress fonts-noto-cjk

# 서비스 요구 파일(-r ../it/…)은 main에 있어 빼고, 제작 도구 줄만 깐다
if curl -fsSL "$REQ_URL" -o /tmp/req_all.txt; then
  sed -n '/개발 · 제작 도구만/,$p' /tmp/req_all.txt > /tmp/req.txt
  if [ -s /tmp/req.txt ]; then
    step pip install -q --break-system-packages -r /tmp/req.txt
  else
    fail="$fail
- $REQ_URL: 「개발 · 제작 도구만」 줄을 찾지 못해 파이썬 도구를 깔지 않았다"
  fi
else
  fail="$fail
- $REQ_URL 받기 실패"
fi

mkdir -p "$HOME/.claude"
cat > "$HOME/.claude/CLAUDE.md" <<'EOF'
# 이 환경 공통(셋업 스크립트가 쓴다)

저장소가 uengine-oss/hyd-iot-edu이고 지금 브랜치가 main이면, 규칙 · 스킬 · 작업 자료는 workspace 브랜치에 있어 아직 안 읽혔다. 일을 시작하기 전에 둘 중 하나로 받는다.
- 시스템 코드도 읽거나 돌리는 일(덱 · 대본 사실 대조, 촬영): main 그대로 `git fetch origin workspace` → `git show origin/workspace:workspace/동기화.py > 동기화.py` → `python3 동기화.py pull` → `rm 동기화.py`.
- 글 · 문서만 고치는 일: `git fetch origin workspace:workspace` → `git switch workspace`.
그 뒤 `CLAUDE.md`를 읽고 `bash .claude/hooks/cloud-bootstrap.sh`를 돌린다. 남은 일은 `workspace/강의제작/남은일.md`. 도구(ffmpeg · poppler · LibreOffice · 제작용 파이썬 패키지)는 이미 깔려 있다.
EOF
if [ -n "$fail" ]; then
  { echo; echo "## 셋업 실패 — 사용자에게 먼저 알린다"; echo "$fail"; } >> "$HOME/.claude/CLAUDE.md"
fi
exit 0
