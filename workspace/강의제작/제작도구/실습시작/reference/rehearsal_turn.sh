#!/usr/bin/env bash
# 언제: 코딩 랩 학생 경로 리허설(코딩랩.md 길 7)에서 학생 역 AI(Codex + 학생처럼 ChatGPT 계정으로 로그인 + config.toml의 모델)에게 한 턴을 보낼 때.
# 쓰는 법: rehearsal_turn.sh <실습 폴더> <프롬프트 파일> [new|resume]   — 첫 턴 new, 이후 resume
# 필요한 환경 변수: CODEX_BIN(Codex CLI 실행 파일 — 예: npm i --prefix <폴더> @openai/codex@0.166.0 뒤 <폴더>/node_modules/.bin/codex)
#                  CODEX_HOME(사용자가 `codex login`해 둔 시험용 폴더 — 이 PC는 D:/HYD-Practice/_codex_luna. 플러그인 · 컴퓨터 제어가 켜진 기본 ~/.codex는 쓰지 않는다)
# resume --last는 실습 폴더(cwd)별로 이어지므로 여러 리허설이 같은 CODEX_HOME을 써도 섞이지 않는다.
# 기록은 실습 폴더 옆 luna_log/turnNN.{prompt.txt,log,last.txt}. 실습 폴더는 저장소 밖 · Temp 밖에 둔다(코딩랩.md 「함정」).
set -euo pipefail
[ -n "${CODEX_BIN:-}" ] && [ -x "$CODEX_BIN" ] || { echo "[rehearsal_turn] CODEX_BIN이 없거나 실행할 수 없다" >&2; exit 2; }
[ -n "${CODEX_HOME:-}" ] && [ -f "$(cygpath -u "$CODEX_HOME" 2>/dev/null || echo "$CODEX_HOME")/auth.json" ] || { echo "[rehearsal_turn] CODEX_HOME에 로그인이 없다 — 사용자에게 그 폴더로 codex login을 부탁한다" >&2; exit 2; }
LAB=$(cd "$1" && pwd); PROMPT_FILE=$(cd "$(dirname "$2")" && pwd)/$(basename "$2"); MODE=${3:-resume}
LOGDIR=$(dirname "$LAB")/luna_log
mkdir -p "$LOGDIR"
# 학생 명령(lab_db.py · show_result.py)이 사용자 화면에 브라우저를 띄우지 않게: 아무것도 안 하는 프로그램을 브라우저로 둔다
export BROWSER='C:\Program Files\Git\usr\bin\true.exe'
N=$(ls "$LOGDIR" | grep -c '^turn[0-9]*\.prompt\.txt$' || true); N=$((N+1))
LOG=$LOGDIR/turn$(printf %02d $N).log
LAST=$LOGDIR/turn$(printf %02d $N).last.txt
cp "$PROMPT_FILE" "$LOGDIR/turn$(printf %02d $N).prompt.txt"
cd "$LAB"
if [ "$MODE" = new ]; then
  timeout 1500 "$CODEX_BIN" exec --skip-git-repo-check -s workspace-write -o "$(cygpath -w "$LAST")" "$(cat "$PROMPT_FILE")" < /dev/null > "$LOG" 2>&1 || echo "[rehearsal_turn] 종료 코드 $? — $LOG 확인" >&2
else
  timeout 1500 "$CODEX_BIN" exec --skip-git-repo-check -c sandbox_mode='"workspace-write"' resume --last -o "$(cygpath -w "$LAST")" "$(cat "$PROMPT_FILE")" < /dev/null > "$LOG" 2>&1 || echo "[rehearsal_turn] 종료 코드 $? — $LOG 확인" >&2
fi
grep -m1 '^model:' "$LOG" | sed 's/^/[모델] /' >&2 || true
grep -A1 '^tokens used' "$LOG" | tail -1 | sed 's/^/[토큰] /' >&2 || true
if [ -s "$LAST" ]; then cat "$LAST"; echo; else echo "[rehearsal_turn] 마지막 답 파일이 비었다 — $LOG"; tail -30 "$LOG"; exit 1; fi
