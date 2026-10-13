"""C3 B·C 단순화 라이브 완주 — 포털 화면 버튼으로 시나리오 하나를 끝까지(실제 워커). 한 번에 하나.

  run_final.py A|B|C OUTDIR
"""
import asyncio
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone

from playwright.async_api import async_playwright

API = "http://127.0.0.1:8080"
PORTAL = "http://127.0.0.1:8088/"
KEY, OUT = sys.argv[1], sys.argv[2]
SPEC = {"A": {"asset": "HYD-01", "act": "degrade", "def": "c3_cooling", "me": "user:kim-op"},
        "B": {"asset": "HYD-02", "act": "biz-start", "def": "c3_pm", "me": "user:park-maint"},
        "C": {"asset": "HYD-03", "act": "biz-start", "def": "c3_spare", "me": "user:jung-buy"}}[KEY]
LOG = []


def log(msg):
    line = f"{datetime.now().strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    LOG.append(line)


def get(path):
    with urllib.request.urlopen(API + path, timeout=20) as r:
        return json.loads(r.read())


async def shot(pg, name, sel=None, full=False):
    path = f"{OUT}/{KEY}-{name}.png"
    if sel:
        try:
            el = await pg.query_selector(sel)
            await el.screenshot(path=path, timeout=8000)
        except Exception:  # noqa: BLE001
            await pg.screenshot(path=path, full_page=True)
    else:
        await pg.screenshot(path=path, full_page=full)
    log(f"shot {path}")


async def tall(pg, name, sel="#instDetail"):
    """뷰포트를 내용 높이로 늘린 뒤 전체 페이지 캡처 — 승인 카드 · 처리 기록이 아래에서 잘리지 않게."""
    vw = pg.viewport_size
    await pg.evaluate("() => { window.scrollTo(0, 0); for (const el of document.querySelectorAll('*')) if (el.scrollTop > 0) el.scrollTop = 0; }")
    h = await pg.evaluate("""(sel) => { const el = document.querySelector(sel); let h = document.documentElement.scrollHeight;
        if (el) { let p = el; while (p) { h = Math.max(h, p.scrollHeight + (p.getBoundingClientRect().top || 0)); p = p.parentElement; } }
        return Math.ceil(h) + 40; }""", sel)
    await pg.set_viewport_size({"width": vw["width"], "height": min(max(h, vw["height"]), 30000)})
    await pg.evaluate("() => { window.scrollTo(0, 0); for (const el of document.querySelectorAll('*')) if (el.scrollTop > 0) el.scrollTop = 0; }")
    await pg.wait_for_timeout(1200)
    path = f"{OUT}/{KEY}-{name}.png"
    await pg.screenshot(path=path, full_page=True)
    await pg.set_viewport_size(vw)
    log(f"shot {path} (h={h})")


async def open_tab(pg, tab):
    await pg.evaluate(f"selectTab('{tab}')")
    await pg.wait_for_timeout(2500)


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 1440, "height": 1000})
        await ctx.add_init_script(f"try {{ localStorage.setItem('hyd.me', '{SPEC['me']}') }} catch (e) {{}}")
        pg = await ctx.new_page()
        mob = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        await mob.add_init_script(f"try {{ localStorage.setItem('hyd.me', '{SPEC['me']}') }} catch (e) {{}}")
        pm = await mob.new_page()
        await pg.goto(PORTAL); await pg.wait_for_timeout(2000)
        await open_tab(pg, "scenario")
        await pg.wait_for_timeout(2500)
        await shot(pg, "1-start-1440", "#view-scenario")
        await pm.goto(PORTAL); await pm.wait_for_timeout(2000); await open_tab(pm, "scenario"); await pm.wait_for_timeout(2500)
        await shot(pm, "1-start-390", full=True)
        before = {i["proc_inst_id"] for i in get("/api/instances?limit=50")}
        t0 = time.time()
        RESUME = sys.argv[3] if len(sys.argv) > 3 else None
        FINISH = len(sys.argv) > 4
        if RESUME:
            before.discard(RESUME)
        btn = pg.locator(f'#units .unit[data-asset="{SPEC["asset"]}"] [data-act="{SPEC["act"]}"]')
        if not RESUME:
            await btn.click()
            log(f"clicked {SPEC['asset']} {SPEC['act']}")
        else:
            log(f"resume {RESUME}")
        await pg.wait_for_timeout(1500)
        log("message: " + (await pg.locator('#scenarioMsg').inner_text()))
        inst_id = None
        while time.time() - t0 < 600:
            new = [i for i in get("/api/instances?limit=50") if i["proc_inst_id"] not in before and i.get("proc_def_id") == SPEC["def"]]
            if new:
                inst_id = new[0]["proc_inst_id"]; break
            await asyncio.sleep(2)
        assert inst_id, "no instance"
        t_start = time.time()
        log(f"instance {inst_id} after {t_start - t0:.1f}s")
        await shot(pg, "2-started-1440", "#view-scenario")
        # 승인 task 를 기다린다
        approve = None
        while time.time() - t_start < 1800:
            d = get(f"/api/instances/{inst_id}")
            agent_done = any(w["activity_id"] == "T_agent" and w["status"] in ("DONE", "COMPLETED") for w in d["workitems"])
            approve = next((w for w in d["workitems"] if w["activity_id"] == "T_approve" and w["status"] in ("TODO", "IN_PROGRESS")), None) if agent_done else None
            if approve or d["instance"]["status"] != "RUNNING":
                break
            await asyncio.sleep(3)
        assert approve, f"no approval task: {json.dumps(d['instance'], ensure_ascii=False)[:400]}"
        t_ready = time.time()
        log(f"approval ready after {t_ready - t_start:.1f}s (agent)")
        await open_tab(pg, "instances")
        await pg.evaluate(f"window.hydInstancesOpenTask('{inst_id}', '{approve['id']}')")
        await pg.locator('#tdGo').wait_for(timeout=20000)
        await pg.wait_for_timeout(1500)
        OPEN_CARD = "() => { const go = document.querySelector('#tdGo'); let p = go; while (p && !(p.querySelectorAll && p.querySelectorAll('details').length)) p = p.parentElement; while (p && p.parentElement && !p.parentElement.id) p = p.parentElement; (p || document).querySelectorAll('details').forEach(d => d.open = true); }"
        await pg.evaluate(OPEN_CARD); await pg.wait_for_timeout(1500)
        await tall(pg, "3-approval-1440")
        await open_tab(pm, "instances")
        await pm.evaluate(f"window.hydInstancesOpenTask('{inst_id}', '{approve['id']}')")
        await pm.wait_for_timeout(4000)
        await pm.evaluate(OPEN_CARD); await pm.wait_for_timeout(1500)
        await tall(pm, "3-approval-390")
        json.dump(get(f"/api/instances/{inst_id}"), open(f"{OUT}/{KEY}-at-approval.json", "w"), ensure_ascii=False, indent=1, default=str)
        go = pg.locator('#tdGo')
        await go.wait_for(timeout=20000)
        if await go.is_disabled():
            await pg.locator('#tdPreview').click()
            for _ in range(30):
                await pg.wait_for_timeout(1000)
                if not await go.is_disabled():
                    break
            await shot(pg, "3b-reviewed-1440", full=True)
        t_ready_seen = time.time()
        t_click = time.time()
        resp = {}
        async def on_resp(r):
            if '/select' in r.url and r.request.method == 'POST':
                resp['status'] = r.status; resp['body'] = (await r.text())[:300]
        pg.on('response', on_resp)
        await go.click()
        await pg.wait_for_timeout(2500)
        log(f"approved via portal -> {resp}")
        assert resp.get('status') == 200, resp
        await pg.wait_for_timeout(3000)
        status = None
        while time.time() - t_click < 1200:
            d = get(f"/api/instances/{inst_id}")
            status = d["instance"]["status"]
            if status != "RUNNING":
                break
            await asyncio.sleep(3)
        t_done = time.time()
        log(f"instance {status} {t_done - t_click:.1f}s after approval")
        await pg.evaluate(f"window.hydInstancesSelect('{inst_id}')")
        await pg.wait_for_timeout(5000)
        await shot(pg, "4-result-1440", "#instDetail")
        await open_tab(pm, "instances")
        await pm.evaluate(f"window.hydInstancesSelect('{inst_id}')")
        await pm.wait_for_timeout(5000)
        await shot(pm, "4-result-390", "#instDetail")
        await open_tab(pg, "scenario")
        await pg.wait_for_timeout(4000)
        await shot(pg, "5-after-1440", "#view-scenario")
        status_after = get("/api/scenario/status")
        d = get(f"/api/instances/{inst_id}")
        json.dump(d, open(f"{OUT}/{KEY}-instance.json", "w"), ensure_ascii=False, indent=1, default=str)
        rec = {"scenario": KEY, "instance": inst_id, "status": status, "end_event": d["instance"].get("end_event"),
               "seconds": {"button_to_instance": round(t_start - t0, 1), "agent_to_approval": round(t_ready - t_start, 1),
                           "approval_wait": round(t_click - t_ready, 1), "approval_to_done": round(t_done - t_click, 1), "total_button_to_done": round(t_done - t0, 1)},
               "steps": [{"id": w["activity_id"], "name": w["activity_name"], "status": w["status"], "start": w.get("start_date"),
                          "end": w.get("end_date")} for w in d["workitems"]],
               "scenario_status_after": status_after.get("scenarios", {}).get(KEY), "log": LOG}
        json.dump(rec, open(f"{OUT}/{KEY}-run.json", "w"), ensure_ascii=False, indent=1)
        print(json.dumps(rec["seconds"]), rec["status"], rec["end_event"])
        await b.close()


asyncio.run(main())
