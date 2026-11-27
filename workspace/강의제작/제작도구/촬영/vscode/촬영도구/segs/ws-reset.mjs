// 5분 예시: 녹화 밖 상태 맞춤 — 첫 페이지(웹 VS Code)에 LABS.ws 폴더를 열고 편집기 · 터미널을 닫고 Codex 새 대화로 둔다(lab-common.mjs resetLab).
// resetLab이 output/을 지우므로, 이 뒤에 녹화 밖에서 그 폴더에서 python run.py design을 돌려 첫 구간(결과 화면)의 화면을 만든다.
const {resetLab} = await import('./lab-common.mjs');
await resetLab('ws', {reload: true});
