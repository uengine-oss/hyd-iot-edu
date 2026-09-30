"""Record the explanation video by actually running the scenario in a browser (Playwright, 1280x720) and muxing narration.

    python video/narration.py          # once: TTS audio + docs/video/narration.md
    python video/record_demo.py        # ~9 min: drives the portal / FUXA / Grafana / Neo4j, writes docs/video/hyd-iot-edu-demo.mp4

Requires the full stack up (docker compose up -d). Restarts agent+process first so the incident list starts empty.
"""
import asyncio
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).parent))
from scenes import SCENES  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "video"
AUDIO = json.loads((DOCS / "audio" / "meta.json").read_text(encoding="utf-8"))
H = "http://localhost"
PORTAL, FUXA, GRAFANA, NEO4J, CONSOLE = f"{H}:8088", f"{H}:1881", f"{H}:3000", f"{H}:7474", f"{H}:8085"
PLANT, DETECTOR, PROCESS, AGENT, ENT = f"{H}:8000", f"{H}:8092", f"{H}:8080", f"{H}:8091", f"{H}:8095"
W, HGT = 1280, 720


def get(url):
    with urllib.request.urlopen(url, timeout=5) as r:
        return json.loads(r.read())


def post(url, data=None):
    req = urllib.request.Request(url, data=json.dumps(data or {}).encode(), headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read() or b"{}")


def ffmpeg():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


CAPTION_JS = """(text) => {
  let d = document.getElementById('__cap');
  if (!d) { d = document.createElement('div'); d.id = '__cap';
    d.style.cssText = 'position:fixed;left:0;right:0;bottom:0;z-index:2147483647;padding:14px 28px;background:rgba(27,36,48,.94);color:#fff;'
      + 'font:600 21px/1.4 "IBM Plex Sans KR","Malgun Gothic",sans-serif;letter-spacing:-0.01em;box-shadow:0 -2px 12px rgba(0,0,0,.25)';
    document.body.appendChild(d); }
  d.textContent = text; }"""


class Recorder:
    def __init__(self, page, t0):
        self.page, self.t0, self.timeline, self.current = page, t0, [], ""

    async def caption(self, text):
        self.current = text
        try:
            await self.page.evaluate(CAPTION_JS, text)
        except Exception:  # noqa: BLE001
            pass

    async def goto(self, url, wait=3000):
        """Navigate and immediately re-apply the scene caption (a navigation destroys the injected overlay)."""
        await self.page.goto(url, wait_until="load", timeout=60000)
        await self.caption(self.current)
        await self.page.wait_for_timeout(wait)
        await self.caption(self.current)

    async def scene(self, sc, action):
        start = time.monotonic() - self.t0
        print(f"[{start:6.1f}s] {sc['id']}", flush=True)
        await self.caption(sc["caption"])
        await action()
        await self.caption(sc["caption"])
        need = max(sc["min_s"], AUDIO[sc["id"]]["duration"] + 1.0)
        elapsed = time.monotonic() - self.t0 - start
        if need > elapsed:
            await self.page.wait_for_timeout(int((need - elapsed) * 1000))
        self.timeline.append({"id": sc["id"], "start": round(start, 2)})


async def wait_until(fn, timeout, every=1.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            v = fn()
            if v:
                return v
        except Exception:  # noqa: BLE001
            pass
        await asyncio.sleep(every)
    return None


def det(asset="HYD-01"):
    return get(f"{DETECTOR}/api/detector/state")["assets"].get(asset, {})


def open_incident(asset):
    for inc in get(f"{PROCESS}/api/incidents"):
        if inc["asset"] == asset and not inc["terminal"]:
            return inc
    return None


async def run():
    print("restarting agent/process for a clean incident list ...")
    subprocess.run(["docker", "compose", "restart", "agent", "process"], cwd=ROOT, capture_output=True)
    # Redpanda Console is an optional ('tools') profile in the light stack: run it only for the recording
    console_was_up = subprocess.run(["docker", "ps", "-q", "-f", "name=hyd-iot-edu-redpanda-console"], capture_output=True, text=True).stdout.strip() != ""
    import os, re
    env_profiles = re.search(r"^COMPOSE_PROFILES=(.*)$", (ROOT / ".env").read_text(encoding="utf-8"), re.M)
    tools_env = dict(os.environ, COMPOSE_PROFILES=(env_profiles.group(1).strip() if env_profiles else "ot,backbone") + ",tools")
    if not console_was_up:
        subprocess.run(["docker", "compose", "up", "-d", "redpanda-console"], cwd=ROOT, capture_output=True, env=tools_env)
        await asyncio.sleep(5)
    post(f"{PLANT}/api/reset")
    post(f"{ENT}/api/reset")
    await asyncio.sleep(12)
    tmp = DOCS / "_rec"
    tmp.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport={"width": W, "height": HGT}, record_video_dir=str(tmp), record_video_size={"width": W, "height": HGT},
                                        locale="ko-KR")
        page = await ctx.new_page()
        t0 = time.monotonic()
        R = Recorder(page, t0)
        S = {s["id"]: s for s in SCENES}
        inc_id = {"v": None}

        async def intro():
            await R.goto(f"{PORTAL}/?present=1", 5000)
        await R.scene(S["intro"], intro)

        async def layers():
            await page.evaluate("hydApp.selectTab('home')")
            await page.wait_for_timeout(1500)
            for y in (300, 600, 900):
                await page.evaluate(f"document.querySelector('main').scrollTo({{top:{y},behavior:'smooth'}})")
                await page.wait_for_timeout(1500)
        await R.scene(S["layers"], layers)

        async def fuxa():
            await R.goto(FUXA, 7000)
        await R.scene(S["fuxa"], fuxa)

        async def console():
            await R.goto(f"{CONSOLE}/topics", 4000)
        await R.scene(S["console"], console)

        async def inject():
            await R.goto(f"{PORTAL}/?present=1", 2500)
            await page.evaluate("hydApp.selectTab('scenario')")
            await page.wait_for_timeout(1500)
            post(f"{PLANT}/api/time_scale", {"scale": 10})   # slower physics so the operator has time before the 65 C trip
            await page.locator('[data-asset="HYD-01"] button[data-act="degrade"]').click()
        await R.scene(S["inject"], inject)

        async def rising():
            await wait_until(lambda: det().get("phase") == "RAISED", 150)
            await page.wait_for_timeout(1500)
        await R.scene(S["rising"], rising)

        async def fuxa_alarm():
            await R.goto(FUXA, 7000)
        await R.scene(S["fuxa_alarm"], fuxa_alarm)

        async def agent():
            inc = await wait_until(lambda: open_incident("HYD-01"), 90)
            inc_id["v"] = inc["id"] if inc else None
            await R.goto(f"{PORTAL}/?present=1", 2000)
            await page.evaluate(f"hydApp.selectIncident('{inc_id['v']}')")
            await page.wait_for_timeout(3000)
            for y in (250, 700, 1200):
                await page.evaluate(f"document.querySelector('main').scrollTo({{top:{y},behavior:'smooth'}})")
                await page.wait_for_timeout(5000)
        await R.scene(S["agent"], agent)

        async def neo4j():
            """Log in to Neo4j Browser (neo4j / hydpass123), run the T2-style path query, show the table view, then the enterprise path."""
            q1 = ("MATCH p=(c:Cause {id:'cause:cooler-fin-fouling'})-[:MITIGATED_BY|REMEDIED_BY]->(:Action)-[:FOLLOWS]->(:Procedure)"
                  "-[:HAS_STEP]->(:Step)-[:REFERS_TO]->(:ManualSection) RETURN p")
            q2 = ("MATCH p=(s:Scenario {id:'sc:part-procurement'})-[:HAS_OPTION]->(:Option)-[:IMPACTS]->(:KPI)-[:OWNED_BY]->(:Department) RETURN p")

            async def run_query(q):
                ed = page.locator(".cm-content").first
                await ed.click()
                await page.keyboard.press("Control+A")
                await page.keyboard.press("Delete")
                await page.keyboard.type(q, delay=4)
                await page.wait_for_timeout(600)
                await page.keyboard.press("Control+Enter")
                await page.wait_for_selector("[data-testid='result-view-graphViz'], [data-testid='nvl-parent']", timeout=20000)
                await page.wait_for_timeout(2500)
                zoom = page.get_by_role("button", name="Zoom in")
                for _ in range(2):                           # bigger nodes so labels and relationship names are legible
                    if await zoom.count():
                        await zoom.last.click()
                        await page.wait_for_timeout(400)
                await R.caption(R.current)

            post(f"{PLANT}/api/time_scale", {"scale": 3})     # the Neo4j walk-through takes ~50 s: keep TS1 below the 65 C trip meanwhile
            try:
                await R.goto(f"{NEO4J}/browser/", 1500)
                await page.wait_for_selector("input[type=password], [data-testid='connection-status-indicator-success']", timeout=30000)
                await page.wait_for_timeout(800)
                if await page.locator("input[type=password]").count():
                    await page.fill("input[type=password]", "hydpass123")
                    await page.get_by_test_id("connection-form-submit").click()
                    await page.wait_for_selector("[data-testid='connection-status-indicator-success']", timeout=20000)
                    await page.wait_for_timeout(2000)
                for _ in range(3):                          # "Work in tabs" feature tour popovers
                    d = page.get_by_role("button", name="Dismiss")
                    if not await d.count():
                        break
                    try:
                        await d.first.click(timeout=3000)
                    except Exception:  # noqa: BLE001  (popover still animating / covered)
                        await page.keyboard.press("Escape")
                    await page.wait_for_timeout(700)
                await R.caption(R.current)
                await run_query(q1)
                await page.wait_for_timeout(6000)
                tab = page.get_by_role("tab", name="Table")
                if not await tab.count():
                    tab = page.get_by_text("Table", exact=True)
                if await tab.count():
                    await tab.first.click()
                    await page.wait_for_timeout(5000)
                    g = page.get_by_role("tab", name="Graph")
                    if not await g.count():
                        g = page.get_by_text("Graph", exact=True)
                    if await g.count():
                        await g.first.click()
                        await page.wait_for_timeout(1000)
                await run_query(q2)
                await page.wait_for_timeout(7000)
            except Exception as e:  # noqa: BLE001
                raise SystemExit(f"neo4j scene failed: {e}")
        await R.scene(S["neo4j"], neo4j)

        async def approve():
            await R.goto(f"{PORTAL}/?present=1", 2000)
            await page.evaluate(f"hydApp.selectIncident('{inc_id['v']}')")
            await page.wait_for_timeout(2500)
            btn = page.locator("#btnApprove")
            if await btn.count():
                await btn.scroll_into_view_if_needed()
                await page.wait_for_timeout(2500)
                await btn.click()
            else:
                post(f"{PROCESS}/api/incidents/{inc_id['v']}/approve", {"approvedBy": "OP-17", "actions": [{"code": "FAN_BOOST", "fan_pct": 100}, {"code": "REDUCE_LOAD", "load_pct": 80}]})
            post(f"{PLANT}/api/time_scale", {"scale": 30})   # faster physics for recovery / re-observation
            ok = await wait_until(lambda: get(f"{PLANT}/api/state")["units"]["HYD-01"]["status"]["fan_pct"] == 100, 20)
            if not ok:
                raise SystemExit("approval did not reach the PLC — check cmd-gateway log")
            await page.wait_for_timeout(2500)
        await R.scene(S["approve"], approve)

        async def process():
            await page.evaluate("document.querySelector('main').scrollTo({top:0,behavior:'smooth'})")
            await page.wait_for_timeout(1500)
        await R.scene(S["process"], process)

        async def grafana():
            await R.goto(f"{GRAFANA}/d/hyd-trend/hyd?orgId=1&var-asset=HYD-01&from=now-5m&to=now&refresh=5s&kiosk&theme=light", 8000)
        await R.scene(S["grafana"], grafana)

        async def closed():
            await R.goto(f"{PORTAL}/?present=1", 2000)
            await page.evaluate(f"hydApp.selectIncident('{inc_id['v']}')")
            await page.wait_for_timeout(2000)
            await wait_until(lambda: get(f"{PROCESS}/api/incidents/{inc_id['v']}")["terminal"], 150)
            await page.wait_for_timeout(3000)
        await R.scene(S["closed"], closed)

        # ---------------- L7 ~ L9: ontology-grounded enterprise decisions ----------------
        async def scroll_to(sel):
            await page.evaluate(f"(document.querySelector({json.dumps(sel)}) || document.body).scrollIntoView({{behavior:'smooth', block:'start'}})")

        async def l79_intro():
            await R.goto(f"{PORTAL}/?present=1", 2500)
            await page.evaluate("hydApp.selectTab('home')")
            await page.wait_for_timeout(800)
            await page.evaluate("document.querySelector('.focusbox').scrollIntoView({behavior:'smooth', block:'center'})")
            await page.wait_for_timeout(2500)
        await R.scene(S["l79_intro"], l79_intro)

        async def l79_linked():
            await page.evaluate(f"hydApp.selectIncident('{inc_id['v']}')")
            await wait_until(lambda: len([d for d in get(f"{PROCESS}/api/decisions") if (d.get("origin") or {}).get("incident") == inc_id["v"]]) >= 3, 30)
            await page.wait_for_timeout(3000)
            await scroll_to("#incDecisions")
            await page.wait_for_timeout(3000)
        await R.scene(S["l79_linked"], l79_linked)

        async def l79_map():
            await page.evaluate("hydApp.selectTab('ontology')")
            await page.wait_for_timeout(4000)
            await page.select_option("#ontoFocus", "sc:part-procurement")
            await page.wait_for_timeout(3500)
            node = page.locator(".o-node[data-id='pol:avl']")
            if await node.count():
                await node.scroll_into_view_if_needed()
                await page.wait_for_timeout(1500)
                await node.click()
                await page.wait_for_timeout(2500)
        await R.scene(S["l79_map"], l79_map)

        async def l79_decide():
            await page.evaluate("hydApp.selectTab('decision')")
            await page.wait_for_timeout(2500)
            await page.locator(".scn").nth(1).locator("button").click()
            await wait_until(lambda: True, 1)
            await page.wait_for_selector(".mtx", timeout=30000)
            await page.wait_for_timeout(1500)
            await scroll_to(".versus")
            await page.wait_for_timeout(5000)
            await scroll_to(".mtx-wrap")
            await page.wait_for_timeout(3000)
        await R.scene(S["l79_decide"], l79_decide)

        async def l79_persp():
            await scroll_to(".persp")
            await page.wait_for_timeout(1500)
            await page.click(".persp button[data-p='dept:purchasing']")
            await page.wait_for_timeout(5000)
            await page.click(".persp button[data-p='enterprise']")
            await page.wait_for_timeout(2500)
        await R.scene(S["l79_persp"], l79_persp)

        async def l79_approve():
            dec = next((d for d in get(f"{PROCESS}/api/decisions") if (d.get("origin") or {}).get("incident") == inc_id["v"]
                        and (d.get("scenario") or {}).get("id") == "sc:delivery-vs-maintenance"), None)
            if not dec:
                print("no alert-generated decision found; skipping approval clicks")
                return
            await page.evaluate(f"hydEnt.ent.decSel = '{dec['id']}'; hydApp.selectTab('process')")
            await page.wait_for_selector("#decRole", timeout=20000)
            await page.wait_for_timeout(3000)
            await page.select_option("#decRole", "role:operator")
            await page.fill("#decBy", "OP-17")
            await page.wait_for_timeout(1500)
            await page.click("[data-approve='opt:sc1-stop']")
            await page.wait_for_timeout(4500)                                    # 403 message shown
            await page.select_option("#decRole", "role:prod-mgr")
            await page.fill("#decBy", "이생산")
            await page.wait_for_timeout(1500)
            await page.click("[data-approve='opt:sc1-derate']")
            ok = await wait_until(lambda: get(f"{PROCESS}/api/decisions/{dec['id']}")["state"] == "EXECUTED", 20)
            if not ok:
                raise SystemExit("enterprise decision was not executed — check process / enterprise-sim logs")
            await page.wait_for_timeout(3500)
        await R.scene(S["l79_approve"], l79_approve)

        async def l79_systems():
            await scroll_to("#sysBoards")
            await page.wait_for_timeout(4000)
        await R.scene(S["l79_systems"], l79_systems)

        async def negative():
            await R.goto(f"{PORTAL}/?present=1", 2000)
            await page.evaluate("hydApp.selectTab('scenario')")
            await page.wait_for_timeout(1000)
            await page.locator('[data-asset="HYD-02"] button[data-act="mode"][data-mode="REMOTE_MANUAL"]').click()
            await page.wait_for_timeout(800)
            await page.locator('[data-asset="HYD-02"] button[data-act="degrade"]').click()
        await R.scene(S["negative"], negative)

        async def rejected():
            inc = await wait_until(lambda: open_incident("HYD-02"), 150)
            if inc:
                post(f"{PROCESS}/api/incidents/{inc['id']}/approve", {"approvedBy": "OP-17", "actions": [{"code": "FAN_BOOST", "fan_pct": 100}, {"code": "REDUCE_LOAD", "load_pct": 80}]})
                await page.wait_for_timeout(4000)
                await page.evaluate("document.querySelector('#gwLog').scrollIntoView({behavior:'smooth'})")
                await page.wait_for_timeout(6000)
                await wait_until(lambda: get(f"{PROCESS}/api/incidents/{inc['id']}")["terminal"], 60)
                await page.evaluate(f"hydApp.selectIncident('{inc['id']}')")
                await page.wait_for_timeout(3000)
        await R.scene(S["rejected"], rejected)

        async def outro():
            post(f"{PLANT}/api/fault", {"asset": "HYD-02", "type": "restore", "ramp_sim_s": 30})
            post(f"{PLANT}/api/mode", {"asset": "HYD-02", "mode": "REMOTE_AUTO"})
            post(f"{PLANT}/api/time_scale", {"scale": 20})
            await R.goto(f"{PORTAL}/?present=1", 3000)
        await R.scene(S["outro"], outro)

        await page.wait_for_timeout(1500)
        video = page.video
        await ctx.close()
        webm = Path(await video.path())
        await browser.close()
    if not console_was_up:
        subprocess.run(["docker", "compose", "rm", "-sf", "redpanda-console"], cwd=ROOT, capture_output=True, env=tools_env)
    (DOCS / "timeline.json").write_text(json.dumps(R.timeline, ensure_ascii=False, indent=1), encoding="utf-8")
    mux(webm, R.timeline)


def mux(webm: Path, timeline: list[dict]):
    out = DOCS / "hyd-iot-edu-demo.mp4"
    cmd = [ffmpeg(), "-y", "-i", str(webm)]
    filters, labels = [], []
    for i, t in enumerate(timeline, start=1):
        a = AUDIO[t["id"]]["file"]
        cmd += ["-i", str(ROOT / a)]
        filters.append(f"[{i}:a]adelay={int(t['start'] * 1000)}|{int(t['start'] * 1000)}[a{i}]")
        labels.append(f"[a{i}]")
    filters.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0[aout]")
    cmd += ["-filter_complex", ";".join(filters), "-map", "0:v", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", "-r", "25",
            "-c:a", "aac", "-b:a", "128k", str(out)]
    print("muxing ...", flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(r.stderr[-2000:])
        raise SystemExit("ffmpeg failed")
    print("wrote", out, f"{out.stat().st_size // (1024 * 1024)} MB")


if __name__ == "__main__":
    asyncio.run(run())
