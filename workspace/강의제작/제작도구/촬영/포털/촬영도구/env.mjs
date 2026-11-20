// 포털 · Neo4j 녹화 도구가 함께 쓰는 환경 고르기 한 곳. Playwright 모듈을 여는 파일(browser · take · ctrl · dry · look · check, neo4j의 prep · record_graph_lesson)은 모두 여기서 받는다.
// 환경은 HYD_ENV(cloud | pc)로 고르고, 주지 않으면 리눅스는 cloud(클라우드 VM), Windows는 pc(이 PC)다. 환경마다 다른 값은 이 폴더 config.json의 그 환경 칸에만 둔다(Playwright 모듈 자리).
// 화면 값 · CDP 포트는 환경이 아니라 도구마다 다르므로 각 도구 config.json의 viewport · cdp에 있다. 셸 쪽 환경(파이썬 · 경로 꼴 · 브라우저 띄우기)은 env.sh가 갖는다.
import {createRequire} from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const HERE=fileURLToPath(new URL('.',import.meta.url));
export const ENV=process.env.HYD_ENV||(process.platform==='win32'?'pc':'cloud');
// Playwright 모듈: 환경변수 PLAYWRIGHT_MODULE이 먼저, 없으면 config.json 그 환경 칸의 playwright(상대 경로는 이 폴더 기준). 자리가 없거나 그 폴더가 없으면 자리를 대며 멈춘다.
export function playwright(){
 const profile=JSON.parse(fs.readFileSync(HERE+'config.json','utf8'))[ENV];
 const p=process.env.PLAYWRIGHT_MODULE||profile?.playwright;
 if(!p)throw Error(`Playwright 자리 없음: 포털/촬영도구/config.json의 환경 칸 「${ENV}」.playwright 또는 환경변수 PLAYWRIGHT_MODULE — HYD_ENV는 cloud 또는 pc (env.mjs)`);
 const abs=path.isAbsolute(p)?p:path.resolve(HERE,p);
 if(!fs.existsSync(abs))throw Error(`Playwright 없음: ${abs} — 그 폴더의 부모의 부모에서 npm i playwright && npx playwright install chromium (포털 촬영준비 「이 PC Playwright」 길 1)`);
 return createRequire(import.meta.url)(abs);
}
