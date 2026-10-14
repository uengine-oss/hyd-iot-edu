#!/usr/bin/env bash
# 맥락 세션의 아스트라(gpt-6-astra)를 이어서 부르고, 레포를 직접 고치게 한다(2_기준 45-1번).
#
#   bash production/tools/deck/아스트라세션.sh <세션 ID | new> <요청문 파일> <답 파일> [첨부 그림 ...]
#
# - 사용자 계정 Codex로 부른다. API 키 · 다른 주소 환경변수는 빼고 넘긴다.
# - 쓰기는 레포와 /tmp뿐(workspace-write), 네트워크는 끈다. 검사는 .venv-deck의 빌더 --check로 한다(설치는 4_만드는_법).
# - new를 주면 새 세션으로 시작한다(일마다 새 세션: 긴 대화를 이어 쓰는 비용을 줄인다).
set -euo pipefail
cd "$(dirname "$0")/../../.."
[ $# -ge 3 ] || { echo "사용: $0 <세션 ID | new> <요청문> <답> [그림 ...]" >&2; exit 2; }
sid=$1 req=$2 out=$3; shift 3
img=(); for f in "$@"; do img+=(-i "$f"); done
opts=(-m gpt-6-astra -c model_reasoning_effort="high" -c sandbox_mode="workspace-write"
      -c sandbox_workspace_write.network_access=false -o "$out")
run=(env -u OPENAI_API_KEY -u OPENAI_BASE_URL -u REAL_OPEN_API_KEY -u LLM_API_KEY codex exec)
if [ "$sid" = new ]; then
  "${run[@]}" -C "$PWD" "${opts[@]}" "${img[@]}" - < "$req"
else
  "${run[@]}" resume "$sid" - "${opts[@]}" "${img[@]}" < "$req"
fi
