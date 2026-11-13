// 환경 고르기 한 곳. 환경마다 다른 값(화면 값 · CDP 포트 · Playwright 자리 · 헤드리스 여부)은 config.json의 환경 칸(cloud · pc)에만 둔다.
// 환경은 ARROWS_ENV(cloud | pc)로 고르고, 주지 않으면 리눅스는 cloud, Windows는 pc다. ego(이 PC의 ego 브라우저)는 전역 taskSpace가 있을 때 ctrl.mjs가 config의 ego 칸을 쓴다.
import {createRequire} from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
export const HERE=fileURLToPath(new URL('.',import.meta.url));
export const CFG=JSON.parse(fs.readFileSync(HERE+'config.json','utf8'));
export const ENV=process.env.ARROWS_ENV||(process.platform==='win32'?'pc':'cloud');
export const PROFILE=CFG[ENV];
if(!PROFILE?.metrics||!PROFILE?.cdp)throw Error(`config.json에 환경 칸 「${ENV}」(cdp · metrics)가 없다 — ARROWS_ENV는 cloud 또는 pc (촬영도구/env.mjs)`);
// Playwright 모듈: 환경변수 PLAYWRIGHT_MODULE이 먼저, 없으면 그 환경 칸의 playwright(상대 경로는 이 폴더 기준). 못 찾으면 자리와 함께 멈춘다.
export function playwright(){
 const p=process.env.PLAYWRIGHT_MODULE||PROFILE.playwright;if(!p)throw Error(`Playwright 자리 없음: config.json ${ENV}.playwright 또는 환경변수 PLAYWRIGHT_MODULE (촬영도구/env.mjs)`);
 const abs=path.isAbsolute(p)?p:path.resolve(HERE,p);
 if(!fs.existsSync(abs))throw Error(`Playwright 없음: ${abs} — 그 폴더의 부모의 부모에서 npm i playwright && npx playwright install chromium (촬영준비 길 1)`);
 return createRequire(import.meta.url)(abs);
}
