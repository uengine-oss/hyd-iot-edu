#!/usr/bin/env bash
# 클라우드 세션에서 .env 가 없으면 .env.example 로 만든다(로컬에서는 바로 끝난다).
# 비밀값·환경별 값(LLM 키·주소 등)은 claude.ai/code 환경 설정의 환경변수로 넣는다.
# compose.yaml 은 ${VAR:-기본값} 으로만 읽으므로 셸 환경변수가 .env 보다 우선한다.
[ "${CLAUDE_CODE_REMOTE:-}" = "true" ] || exit 0
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
if [ ! -f .env ] && [ -f .env.example ]; then
  cp .env.example .env
  echo "[hyd 클라우드] .env 가 없어 .env.example 로 만들었다. LLM 키·주소는 환경 설정의 환경변수로 들어온다."
fi
