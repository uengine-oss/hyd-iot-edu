"""처리 기록 탭 캡처: record_shot.py KEY INST ME OUT — 1440 · 390, '모두 펼치기' 뒤 전체 높이. 화면 글도 텍스트로 남긴다."""
import asyncio, json, sys
from playwright.async_api import async_playwright
KEY, INST, ME, OUT = sys.argv[1:5]
async def tall(pg, path):
    vw = pg.viewport_size
    await pg.evaluate("() => { window.scrollTo(0, 0); for (const el of document.querySelectorAll('*')) if (el.scrollTop > 0) el.scrollTop = 0; }")
    h = await pg.evaluate("""() => { let h = document.documentElement.scrollHeight; for (const el of document.querySelectorAll('#instDetail, #instDetail *')) { const r = el.getBoundingClientRect(); h = Math.max(h, r.bottom + window.scrollY, el.scrollHeight + r.top + window.scrollY); } return Math.ceil(h) + 40; }""")
    await pg.set_viewport_size({"width": vw["width"], "height": min(max(h, vw["height"]), 32000)})
    await pg.evaluate("() => { window.scrollTo(0, 0); for (const el of document.querySelectorAll('*')) if (el.scrollTop > 0) el.scrollTop = 0; }")
    await pg.wait_for_timeout(1500)
    await pg.screenshot(path=path, full_page=True)
    await pg.set_viewport_size(vw)
    return h
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for w, hgt, tag in ((1440, 1000, "1440"), (390, 844, "390")):
            ctx = await b.new_context(viewport={"width": w, "height": hgt}, device_scale_factor=2 if w < 500 else 1)
            await ctx.add_init_script(f"try {{ localStorage.setItem('hyd.me','{ME}') }} catch (e) {{}}")
            pg = await ctx.new_page(); errs = []
            pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
            pg.on("pageerror", lambda e: errs.append(str(e)))
            await pg.goto('http://127.0.0.1:8088/'); await pg.wait_for_timeout(2500)
            await pg.evaluate("selectTab('instances')"); await pg.wait_for_timeout(1500)
            await pg.evaluate(f"window.hydInstancesSelect('{INST}')"); await pg.wait_for_timeout(5000)
            await pg.locator('[data-inst-tab="record"]').first.click(); await pg.wait_for_timeout(3500)
            h0 = await tall(pg, f"{OUT}/{KEY}-7-record-{tag}.png")
            allb = pg.locator('#instRecord [data-cr-all]').first
            if await allb.count():
                await allb.click(); await pg.wait_for_timeout(2500)
            await pg.evaluate("document.querySelectorAll('#instRecord details').forEach(d => d.open = true)")
            await pg.wait_for_timeout(5000)   # event-payloads 원문 불러오기
            h1 = await tall(pg, f"{OUT}/{KEY}-7-record-open-{tag}.png")
            if tag == "1440":
                txt = await pg.locator('#instRecord').inner_text()
                open(f"{OUT}/{KEY}-7-record-text.txt", "w").write(txt)
            print(tag, "heights", h0, h1, "console errors", errs[:5])
            await ctx.close()
        await b.close()
asyncio.run(main())
