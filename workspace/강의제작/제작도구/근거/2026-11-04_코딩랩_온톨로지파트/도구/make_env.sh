#!/usr/bin/env bash
# 학생이 「강의에서 받은 접속 세 줄」을 .env에 붙여 넣는 동작을 대신한다. 값은 출력하지 않는다.
# 쓰는 법: make_env.sh <실습 폴더>  (.env.example 이 있는 폴더)
set -euo pipefail
LAB=$(cd "$1" && pwd)
KEYF=/root/.claude/uploads/476059fc-242d-55b3-911f-45e453197017/001cc594-gnu-class-key.txt
[ -f "$LAB/.env.example" ] || { echo "[make_env] $LAB/.env.example 없음"; exit 1; }
grep -E '^(OPENAI_BASE_URL|LLM_API_KEY|LLM_MODEL)=' "$KEYF" | tr -d '\r' > "$LAB/.env"
echo "[make_env] $LAB/.env 에 세 줄을 넣었습니다(이름: $(cut -d= -f1 "$LAB/.env" | tr '\n' ' '))"
