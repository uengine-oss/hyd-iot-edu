// 실전 3-1 포털 구간 공통 조작: 카드·접기·표 행을 글자로 찾고, 본문(main#content)을 부드럽게 굴려 화면 안에 둔다.
// 포털 녹화 공간(VP 1536x864 dsf1.5)은 ego 150 %라 CSS 화면이 1024x576이다. 「화면 안」은 본문 영역의 실제 높이로 판정한다(2026-10-28 실측).
export function portal(ctx, c) {
 const free = { x: 900, y: 300 };   // 본문 오른쪽 여백 — 굴리기 전 화살표 자리
 // q = {sel, text, within, exact}: within 카드 제목(h3) 안에서, sel 중 글자가 text로 시작(exact면 같음)하는 보이는 요소 하나.
 const locate = (q) => ctx.serial(() => ctx.p.evaluate(({ sel, text, within, exact }) => {
  let root = document;
  if (within) {
   const cards = [...document.querySelectorAll('section.card')].filter((s) => s.querySelector('h3')?.textContent.trim() === within && s.checkVisibility());
   if (cards.length !== 1) return { error: `card ${within} matched ${cards.length}` };
   root = cards[0];
  }
  const norm = (e) => e.textContent.replace(/\s+/g, ' ').trim();
  const es = [...root.querySelectorAll(sel)].filter((e) => e.checkVisibility() && (text == null || (exact ? norm(e) === text : norm(e).startsWith(text))));
  if (es.length !== 1) return { error: `${within ?? ''} ${sel} ${text ?? ''} matched ${es.length}` };
  const b = es[0].getBoundingClientRect(), m = document.querySelector('main#content'), mr = m.getBoundingClientRect();
  return { x: b.x + Math.min(b.width / 2, 160), y: b.y + b.height / 2, top: m.scrollTop + b.y - mr.y, h: b.height, my: mr.y, mh: m.clientHeight };
 }, q)).then((r) => { if (r.error) throw Error(r.error); return r; });
 const p = {};
 // 대상 중심이 본문 영역 위아래 40px 안쪽이 아니면, 본문 높이의 at 비율 자리에 오도록 굴린다.
 p.show = async (q, at = 0.45) => {
  let r = await locate(q);
  if (r.y < r.my + 40 || r.y > r.my + r.mh - 40) { await c.scrollTo('main#content', Math.max(0, r.top - r.mh * at)); r = await locate(q); }
  if (r.y < r.my + 10 || r.y > r.my + r.mh - 10) throw Error(`${q.sel} ${q.text ?? ''}: 굴린 뒤에도 화면 밖(y ${Math.round(r.y)})`);
  return r;
 };
 p.hover = async (q, at) => { const r = await p.show(q, at); await c.move(r.x, r.y); return r; };
 p.click = async (q, at) => { const r = await p.hover(q, at); await c.gate(); await ctx.serial(() => ctx.p.mouse.click(r.x, r.y)); await ctx.sleep(150); };
 p.top = () => c.scrollTo('main#content', 0);
 p.loaded = (n = 4) => ctx.waitFor(new Function(`return !!document.querySelector('[data-wi-tab]') && document.querySelectorAll('.stack-list > section.card').length>=${n} && !document.querySelector('#wiLoad')?.disabled`), 120000);
 p.free = free;
 return p;
}
