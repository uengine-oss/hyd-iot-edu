#!/bin/bash
# 언제: 클라우드 환경(claude.ai/code → 환경 편집 → 설정 스크립트)이 새 세션 VM을 준비할 때. 도구만 깐다 — 저장소 위치에 기대지 않는다.
# 명령(설정 스크립트 칸에 이 한 줄):
#   git clone -q --depth 1 --filter=blob:none --no-checkout -b workspace https://github.com/uengine-oss/hyd-iot-edu.git /tmp/hydws && git -C /tmp/hydws show HEAD:workspace/개발/scripts/cloud_setup.sh | bash
# 까닭(공식 문서 cloud-environments · web-quickstart): 설정 스크립트의 작업 폴더는 정해져 있지 않고(저장소 밖에서 돌아 「not a git repository」로 실패한 적 있다),
#   결과는 파일 시스템 스냅샷으로 캐시되며 저장소는 세션마다 새로 받는다. 그래서 workspace 파일 풀기는 여기서 하지 않는다 —
#   세션을 workspace 브랜치로 시작하면 그 브랜치의 .claude 훅이 처음부터 돈다(CLAUDE.md 7절).
# 늘 0으로 끝낸다(0이 아니면 세션이 안 뜬다). 실패는 ~/.claude/CLAUDE.md에 적어 Claude가 사용자에게 먼저 알리게 한다(클라우드는 그 파일을 읽는다).
SRC=/tmp/hydws                      # 위 한 줄이 받아 둔 workspace 브랜치(파일 내용은 필요할 때만 받는 얕은 복제)
LOG=/tmp/cloud_setup.log
fail=""
step() {
  "$@" >"$LOG" 2>&1 || fail="$fail
- $* 실패: $(tail -n 2 "$LOG" | tr '\n' ' ')"
}

step apt-get update -qq
step apt-get install -y -qq --no-install-recommends ffmpeg poppler-utils libreoffice-impress fonts-noto-cjk

if git -C "$SRC" show HEAD:workspace/requirements-dev.txt > /tmp/req-all.txt 2>"$LOG"; then
  sed -n '/개발 · 제작 도구만/,$p' /tmp/req-all.txt > /tmp/req.txt   # 서비스 요구 파일(-r ../it/…) 줄은 빼고 제작 도구 줄만
  if [ -s /tmp/req.txt ]; then
    step pip install -q --break-system-packages -r /tmp/req.txt
    step python3 -m playwright install --with-deps chromium
  else
    fail="$fail
- requirements-dev.txt에서 「개발 · 제작 도구만」 줄을 찾지 못해 파이썬 도구를 깔지 않았다"
  fi
else
  fail="$fail
- $SRC 에서 requirements-dev.txt를 읽지 못했다: $(tail -n 1 "$LOG") — 설정 스크립트 칸의 한 줄(git clone … /tmp/hydws)이 먼저 돌았는지 본다"
fi

NOTE="$HOME/.claude/CLAUDE.md"
mkdir -p "$HOME/.claude"
if [ -n "$fail" ]; then
  printf '# 클라우드 셋업 실패 — 사용자에게 먼저 알린다(cloud_setup.sh가 쓴다)\n%s\n' "$fail" > "$NOTE"
elif head -n 1 "$NOTE" 2>/dev/null | grep -q 'cloud_setup.sh가 쓴다'; then
  rm -f "$NOTE"
fi
exit 0
