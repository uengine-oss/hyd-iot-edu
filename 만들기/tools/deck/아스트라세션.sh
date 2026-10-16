#!/usr/bin/env bash
# 맥락 세션의 아스트라(gpt-6-astra)를 이어서 부르고, 레포를 직접 고치게 한다(2_기준 45-1번).
#
#   bash 만들기/tools/deck/아스트라세션.sh <세션 ID | new> <요청문 파일> <답 파일> [첨부 그림 ...]
#
# - 사용자 계정 Codex로 부른다. API 키 · 다른 주소 환경변수는 빼고 넘긴다.
# - 쓰기는 레포와 /tmp(workspace-write), 네트워크는 켠다(외부 자료 검색). 검사는 .venv-deck의 빌더 --check로 한다. 커밋 · push는 세션이 확인한 뒤에 한다.
# - 같은 세션 ID를 이어 쓴다. new는 새 세션을 명시적으로 원할 때만 쓴다.
# - .astra/의 재개 안내만 붙인다. 원문 전체·계정 정보·도구 출력을 요청마다 복사하지 않는다.
set -euo pipefail
cd "$(dirname "$0")/../../.."
[ $# -ge 3 ] || { echo "사용: $0 <세션 ID | new> <요청문> <답> [그림 ...]" >&2; exit 2; }
sid=$1 req=$2 out=$3; shift 3
[ -r "$req" ] || { echo "요청문을 읽을 수 없다: $req" >&2; exit 2; }
img=(); for f in "$@"; do img+=(-i "$f"); done
opts=(-m gpt-6-astra -c model_reasoning_effort="high" -c sandbox_mode="workspace-write"
      -c sandbox_workspace_write.network_access=true -o "$out")
run=(env -u OPENAI_API_KEY -u OPENAI_BASE_URL -u REAL_OPEN_API_KEY -u LLM_API_KEY codex exec)
prompt() {
  printf '%s\n\n' '작업 재개 진입점은 .astra/README.md와 .astra/state.json이다. 최신 사용자 요청이 우선한다. 처음이거나 맥락이 흐리면 안내와 필요한 원문으로 복구하고, 이미 이해한 동일 자료는 반복 출력하지 않는다. 커밋·push는 하지 않는다. 작업 계약(사용자 확정, 2026-10-16): 아스트라는 레포의 덱 · 대본을 직접 쓰지 않는다. 지금 판을 읽고 고칠 것만 수정안 목록(고칠것.json, 고칠것넣기.py 꼴)으로 내고, 세션이 그대로 넣고 빌드 검사만 한다. 4~9회차의 아스트라 윤문 · 검증 · 기준 점검은 지금 하지 않는다. 1~3회차가 확정된 뒤 회차 차례대로 한다(한꺼번에 하면 앞 회차가 바뀔 때 다시 고쳐야 하므로). 견적만 물으면 파일을 고치지 않는다.'
  cat -- "$req"
}
if [ "$sid" = new ]; then
  prompt | "${run[@]}" -C "$PWD" "${opts[@]}" "${img[@]}" -
else
  prompt | "${run[@]}" resume "$sid" - "${opts[@]}" "${img[@]}"
fi
