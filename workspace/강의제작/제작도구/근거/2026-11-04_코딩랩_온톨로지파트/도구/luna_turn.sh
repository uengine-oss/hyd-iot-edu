#!/usr/bin/env bash
# 학생 경로 리허설에서 루나(Codex CLI + 강의 중계 LiteLLM coding)에게 한 턴을 보낸다.
# 쓰는 법: luna_turn.sh <실습 폴더> <프롬프트 파일> [new|resume]
#   new    = 새 대화(첫 턴), resume = 같은 실습 폴더의 마지막 대화를 이어감(기본)
# 출력: 루나의 마지막 답(학생이 채팅에서 보는 것). 전체 기록은 <실습 폴더>/../luna_log/ 에 턴마다 남는다.
# 키 값은 출력하지 않는다. CODEX_HOME은 /tmp 밖(apply_patch 도우미 때문에)에 실습 폴더마다 하나.
set -euo pipefail
LAB=$(cd "$1" && pwd); PROMPT_FILE=$2; MODE=${3:-resume}
S=/tmp/claude-0/-home-user-hyd-iot-edu/476059fc-242d-55b3-911f-45e453197017/scratchpad
KEYF=/root/.claude/uploads/476059fc-242d-55b3-911f-45e453197017/001cc594-gnu-class-key.txt
CODEX=$S/codex/node_modules/.bin/codex
NAME=$(basename "$(dirname "$LAB")")_$(basename "$LAB")
CH=/root/.hyd-rehearse/$NAME
mkdir -p "$CH" "$(dirname "$LAB")/luna_log"
BASE=$(sed -n 's/^OPENAI_BASE_URL=//p' "$KEYF" | tr -d '\r')
if [ ! -f "$CH/config.toml" ]; then
  cat > "$CH/config.toml" <<EOF
model = "coding"
model_provider = "litellm"
model_reasoning_effort = "medium"
sandbox_mode = "workspace-write"

[model_providers.litellm]
name = "LiteLLM (course relay)"
base_url = "$BASE"
env_key = "LITELLM_KEY"
wire_api = "responses"
EOF
fi
export CODEX_HOME=$CH LITELLM_KEY=$(sed -n 's/^LLM_API_KEY=//p' "$KEYF" | tr -d '\r')
N=$(ls "$(dirname "$LAB")/luna_log" | grep -c '^turn[0-9]*\.prompt\.txt$' || true); N=$((N+1))
LOG=$(dirname "$LAB")/luna_log/turn$(printf %02d $N).log
LAST=$(dirname "$LAB")/luna_log/turn$(printf %02d $N).last.txt
cp "$PROMPT_FILE" "$(dirname "$LAB")/luna_log/turn$(printf %02d $N).prompt.txt"
cd "$LAB"
if [ "$MODE" = new ]; then
  timeout 1500 "$CODEX" exec --skip-git-repo-check -s workspace-write -o "$LAST" "$(cat "$PROMPT_FILE")" < /dev/null > "$LOG" 2>&1 || echo "[luna_turn] 종료 코드 $? — $LOG 확인" >&2
else
  timeout 1500 "$CODEX" exec --skip-git-repo-check -c sandbox_mode='"workspace-write"' resume --last -o "$LAST" "$(cat "$PROMPT_FILE")" < /dev/null > "$LOG" 2>&1 || echo "[luna_turn] 종료 코드 $? — $LOG 확인" >&2
fi
grep -A1 '^tokens used' "$LOG" | tail -1 | sed 's/^/[토큰] /' >&2 || true
if [ -s "$LAST" ]; then cat "$LAST"; echo; else echo "[luna_turn] 마지막 답 파일이 비었습니다 — $LOG"; tail -30 "$LOG"; fi
