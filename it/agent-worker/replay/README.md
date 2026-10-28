# 저장된 AI 응답(강사가 실제 AI로 진행하며 저장)

키 없는 PC(온라인 학생)의 AI 워커가 재생하는 응답이다. 업무 하나에 파일 하나(`<업무 해시>.json.gz`).

- 만드는 법: 강사가 `AI응답저장.bat`(`bash scripts/record_replay.sh`) 한 번 — 실제 AI로 포털 실습 01~13 · 90을 진행하며 저장한다.
- 쓰는 법: 학생은 `.env`의 `LLM_API_KEY`를 비운 채 `시작.bat` — 워커가 `AI_MODE=replay`로 켜져 이 폴더를 읽는다.
- 목록: `docker compose exec agent-worker python -m worker.ai_replay`

동작 · 규칙 · 보안은 `문서/시스템/참조/재생모드.md`.
