// 통합 2회차 06-1편(VS Code 랩 시작하기): 녹화 밖 상태 맞춤 — 그 편의 웹 VS Code 첫 화면을 만든다(녹화하지 않는다).
// 부르기: ./run.sh reset wv-reset.mjs (녹화 브라우저가 떠 있어야 한다 — ./run.sh up)
// 하는 일은 lab-common.mjs의 resetLab: LABS.wv 촬영 폴더 열기 · 신뢰 · 터미널 닫기 · 편집기 모두 닫기(README.md가 없는 랩) · 폴더 접기 · output/ · 실행 캐시 지우기 · Codex 새 대화.
// reload: 리허설이 남긴 Codex 대화 대신 새 대화 화면으로 돌아오게 창을 새로 고친다(지난 대화는 녹화 전에 따로 보관한다 — 촬영준비 길 4).
const {resetLab} = await import('./lab-common.mjs');
await resetLab('wv', {reload: true});
