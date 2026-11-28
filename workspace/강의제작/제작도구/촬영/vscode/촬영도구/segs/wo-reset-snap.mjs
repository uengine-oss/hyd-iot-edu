// 06-2편 녹화 밖: 촬영 폴더(LABS.wo)의 app/features · output을 사본 자리 D:/HYD-Practice/wvp-<해시>/_wo-<구간>/에 남긴다(ws의 _3장끝/ 본보기). 녹화 브라우저를 쓰지 않는다.
// 부르기: SEG=<구간> ./run.sh reset wo-reset-snap.mjs — 구간 = 00(06-1 끝, wo-01 앞) 또는 첫 페이지 구간 이름(01 · 02a …). 그 구간의 좋은 take를 받아들인 직후에 부른다.
// 앞 사본과 견줘 바뀐 파일을 찍고, 읽기 부탁(파일은 바꾸지 말라고 한 R1 · R3 · R5 · R8 · R10 · R12 · R14 · R16) 구간에서 app/features가 바뀌었으면 멈춘다 — Codex가 부탁을 어긴 것이라 그 답을 보고 정한다.
import fs from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {LABS} from './lab-common.mjs';
import {SEGS, SNAP} from './wo-common.mjs';

const seg = process.env.SEG ?? '';
const order = ['00', ...SEGS.filter(s => s.page === 0).map(s => s.name)];
if (!order.includes(seg)) throw Error('SEG=' + seg + ' — 사본은 00 또는 첫 페이지 구간(' + order.join(' · ') + ')에만 남긴다 (segs/wo-reset-snap.mjs)');
const LAB = LABS.wo.dir, to = SNAP + '/_wo-' + seg;
const READS = ['R1', 'R3', 'R5', 'R8', 'R10', 'R12', 'R14', 'R16'];
const files = async root => { const out = {}; for (const d of ['app/features', 'output']) { let names = []; try { names = await fs.readdir(root + '/' + d); } catch { continue; } for (const n of names) { if (n === '__pycache__') continue; const b = await fs.readFile(root + '/' + d + '/' + n); out[d + '/' + n] = createHash('sha256').update(b).digest('hex').slice(0, 12); } } return out; };
const now = await files(LAB);
if (!Object.keys(now).some(k => k.startsWith('app/features/'))) throw Error(LAB + '/app/features가 없음 (segs/wo-reset-snap.mjs)');
await fs.rm(to, {recursive: true, force: true}); await fs.mkdir(to, {recursive: true});
for (const d of ['app/features', 'output']) await fs.cp(LAB + '/' + d, to + '/' + d, {recursive: true, filter: s => !s.replace(/\\/g, '/').includes('__pycache__')}).catch(e => { if (d !== 'output') throw e; });
const back = order.slice(0, order.indexOf(seg)).reverse();
let prev = null; for (const b of back) { try { await fs.access(SNAP + '/_wo-' + b); prev = b; break; } catch { } }
const before = prev ? await files(SNAP + '/_wo-' + prev) : {};
const changed = Object.keys({...before, ...now}).filter(k => before[k] !== now[k]).sort();
console.log(JSON.stringify({snap: to, prev: prev ? '_wo-' + prev : null, changed}));
const ask = SEGS.find(s => s.name === seg)?.ask;
if (READS.includes(ask) && changed.some(k => k.startsWith('app/features/'))) throw Error('구간 ' + seg + '(' + ask + ' — 파일은 바꾸지 말라고 한 읽기 부탁)에서 app/features가 바뀜: ' + changed.join(', ') + ' — 그 답을 보고 정한다(사본은 남겼다) (segs/wo-reset-snap.mjs)');
