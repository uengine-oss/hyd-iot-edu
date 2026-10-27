import fs from 'node:fs/promises';
// 경로는 실행 시 넘긴다. 공간·페이지·DB는 사전 확인된 실제 값만 사용한다.
if(!globalThis.HYD_CONFIG_PATH)throw Error('Set HYD_CONFIG_PATH to an absolute JSON path');
globalThis.HYD_RECORDING=JSON.parse(await fs.readFile(globalThis.HYD_CONFIG_PATH,'utf8'));
await import('./record_graph_lesson.mjs');
