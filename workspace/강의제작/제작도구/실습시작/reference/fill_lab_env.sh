#!/usr/bin/env bash
# 언제: 모델을 부르는 코딩 랩의 리허설 · 장난감 시험에서, 학생이 강의에서 받은 키를 .env의 LLM_API_KEY= 뒤에 붙여 넣는 동작을 대신할 때.
# 쓰는 법: KEY_FILE=<LLM_API_KEY=… 줄이 든 파일(저장소 밖)> fill_lab_env.sh <실습 폴더>   — 가이드대로 .env.example을 복사해 .env를 먼저 만든다
# .env의 접속 주소 · 모델 이름 줄은 그대로 두고, 등호 뒤가 빈 LLM_API_KEY= 줄 하나만 채운다. 값은 출력 · 기록하지 않는다. 시험이 끝나면 그 .env(또는 폴더째)를 지운다.
set -euo pipefail
[ -n "${KEY_FILE:-}" ] && [ -f "$KEY_FILE" ] || { echo "[fill_lab_env] KEY_FILE이 없다" >&2; exit 2; }
LAB=$(cd "$1" && pwd)
[ -f "$LAB/.env" ] || { echo "[fill_lab_env] $LAB/.env 없음 — 가이드대로 .env.example을 복사해 .env를 먼저 만든다" >&2; exit 1; }
KEY_LINE=$(grep -m1 -E '^LLM_API_KEY=.+' "$KEY_FILE" | tr -d '\r') || { echo "[fill_lab_env] KEY_FILE에 값이 든 LLM_API_KEY= 줄이 없다" >&2; exit 1; }
EMPTY=$(tr -d '\r' < "$LAB/.env" | grep -c -E '^LLM_API_KEY=[[:space:]]*$' || true)
[ "$EMPTY" = 1 ] || { echo "[fill_lab_env] $LAB/.env 에 등호 뒤가 빈 LLM_API_KEY= 줄이 ${EMPTY}개다 — 하나여야 한다(.env.example을 다시 복사한다)" >&2; exit 1; }
tr -d '\r' < "$LAB/.env" | KEY_LINE="$KEY_LINE" awk '/^LLM_API_KEY=[[:space:]]*$/ { print ENVIRON["KEY_LINE"]; next } { print }' > "$LAB/.env.filled"
mv "$LAB/.env.filled" "$LAB/.env"
echo "[fill_lab_env] $LAB/.env 의 LLM_API_KEY 한 줄을 채웠다(이름: $(grep -E '^[A-Z_]+=' "$LAB/.env" | cut -d= -f1 | tr '\n' ' '))"
