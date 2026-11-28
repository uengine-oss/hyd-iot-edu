// 07편 녹화 밖 사본: SEG=<구간> ./run.sh reset wg-save.mjs — 그 구간을 녹화해 받아들인 직후의 랩 폴더 · 화면 상태를 촬영 폴더 옆 _<구간>/에 남긴다(다음 구간의 되돌리기가 쓴다). 화면을 바꾸지 않는다.
const {saveState} = await import('./wg-state.mjs');
if (!process.env.SEG) throw Error('SEG=<구간 이름> 를 준다 — 예: SEG=wg-02c ./run.sh reset wg-save.mjs (segs/wg-save.mjs)');
await saveState(process.env.SEG);
