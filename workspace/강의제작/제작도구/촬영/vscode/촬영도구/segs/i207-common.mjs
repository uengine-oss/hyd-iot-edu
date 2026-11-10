// 통합 2회차 07편 구간들이 함께 쓰는 짚기 도구(터미널 줄 · 결과 화면 칸). 조작 층은 ../ui.mjs.
export const LAB = 'D:/HYD-Practice/i207p-505d6d69/graph-lab';
export const PAGE = 'file:///' + LAB + '/output/result.html';
// 터미널에서 글이 text를 담은 마지막 줄의 앞쪽 — terminal.integrated.gpuAcceleration이 off여야 한다(촬영준비 길 4).
export const termLine = (c, ctx, text) => c.serial(() => ctx.p.evaluate(text => {
 const rows = document.querySelector('.terminal-wrapper .xterm-rows');
 if (!rows) throw Error('터미널 줄을 DOM에서 읽을 수 없음 — terminal.integrated.gpuAcceleration을 off로');
 const l = [...rows.children].filter(d => d.textContent.includes(text)).pop();
 if (!l) throw Error('터미널 줄 없음: ' + text);
 const b = l.getBoundingClientRect(); return {x: b.x + 120, y: b.y + b.height / 2};
}, text));
// 결과 화면 표에서 첫 칸 글이 name인 줄의 n번째 칸
export const cell = (c, ctx, name, n = 0) => c.serial(() => ctx.p.evaluate(({name, n}) => {
 const tr = [...document.querySelectorAll('tr')].filter(r => r.cells[0]?.textContent.trim() === name);
 if (tr.length !== 1) throw Error('표 줄이 ' + tr.length + '개: ' + name);
 const b = tr[0].cells[n].getBoundingClientRect(); return {x: b.x + 30, y: b.y + b.height / 2};
}, {name, n}));
