#!/usr/bin/env bash
# 언제: 모델을 부르는 코딩 랩의 리허설 · 장난감 시험에서, 학생이 강의에서 받은 접속 세 줄을 .env에 붙여 넣는 동작을 대신할 때.
# 쓰는 법: KEY_FILE=<강의 접속 세 줄이 든 파일(저장소 밖)> fill_lab_env.sh <실습 폴더>   — 가이드대로 .env.example을 복사해 .env를 먼저 만든다
# 값은 출력 · 기록하지 않는다. 시험이 끝나면 그 .env(또는 폴더째)를 지운다.
set -euo pipefail
[ -n "${KEY_FILE:-}" ] && [ -f "$KEY_FILE" ] || { echo "[fill_lab_env] KEY_FILE이 없다" >&2; exit 2; }
LAB=$(cd "$1" && pwd)
[ -f "$LAB/.env" ] || { echo "[fill_lab_env] $LAB/.env 없음 — 가이드대로 .env.example을 복사해 .env를 먼저 만든다" >&2; exit 1; }
grep -E '^(OPENAI_BASE_URL|LLM_API_KEY|LLM_MODEL)=' "$KEY_FILE" | tr -d '\r' > "$LAB/.env"
[ "$(grep -c '=' "$LAB/.env")" = 3 ] || { echo "[fill_lab_env] KEY_FILE에서 세 줄을 다 찾지 못했다" >&2; exit 1; }
echo "[fill_lab_env] $LAB/.env 에 세 줄을 넣었다(이름: $(cut -d= -f1 "$LAB/.env" | tr '\n' ' '))"
