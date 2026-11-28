// 07편 녹화 밖 되돌리기: SEG=<구간> ./run.sh reset wg-reset.mjs — 그 구간의 시작 상태를 만든다(SEG=wg-01은 처음부터: 촬영 폴더를 ZIP 그대로 · 새 대화 · 터미널 하나). 하는 일과 차례는 wg-state.mjs 머리말과 판정/녹화모듈_07.md.
const {resetTo} = await import('./wg-state.mjs');
if (!process.env.SEG) throw Error('SEG=<구간 이름> 를 준다 — 예: SEG=wg-02c ./run.sh reset wg-reset.mjs (segs/wg-reset.mjs)');
await resetTo(process.env.SEG);
