import asyncio, sys
from playwright.async_api import async_playwright
ASSET, ACT, ME, SHOT = sys.argv[1:5]
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={"width": 1440, "height": 1000})
        await ctx.add_init_script(f"try {{ localStorage.setItem('hyd.me','{ME}') }} catch (e) {{}}")
        pg = await ctx.new_page(); await pg.goto('http://127.0.0.1:8088/'); await pg.wait_for_timeout(2500)
        await pg.evaluate("selectTab('scenario')"); await pg.wait_for_timeout(2500)
        await pg.locator(f'#units .unit[data-asset="{ASSET}"] [data-act="{ACT}"]').click(); await pg.wait_for_timeout(3000)
        print(ASSET, ACT, '->', await pg.locator('#scenarioMsg').inner_text())
        await pg.wait_for_timeout(3000)
        await (await pg.query_selector('#view-scenario')).screenshot(path=SHOT)
        await b.close()
asyncio.run(main())
