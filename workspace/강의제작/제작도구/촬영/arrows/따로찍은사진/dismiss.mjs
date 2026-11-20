// 새 브라우저의 첫 안내 창(쿠키 안내 · Help)을 닫는다 — run.sh restore 앞에 한 번(녹화 밖).
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const {chromium}=require('/opt/node22/lib/node_modules/playwright');
const b=await chromium.connectOverCDP('http://127.0.0.1:9334');
const p=b.contexts()[0].pages().find(x=>x.url().includes('arrows.app'));
const ck=p.locator('text=Use necessary cookies only');if(await ck.count())await ck.first().click();
await p.waitForTimeout(500);
const d=p.locator('button:has-text("Done")');if(await d.count())await d.first().click();
await p.waitForTimeout(500);
console.log(JSON.stringify({url:p.url(),modal:await p.locator('.ui.page.modals.dimmer.visible.active').count()}));
process.exit(0);
