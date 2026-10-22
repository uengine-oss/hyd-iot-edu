"""재생 모드 끝까지 검사(실제 브라우저, 서비스 스택 없이 정적 서버만). 계약: 문서/시스템/참조/재생모드.md

  .venv/bin/python scripts/replay_e2e.py [사례 id] [--live http://127.0.0.1:8088/]
  → .evidence/replay/e2e-<사례>-<시각>.json (항목별 판정 · 근거) · 화면

검사 항목
  1 사례 고르기 화면에서 시작한다. 재생 모드 표시와 「저장된 실행 기록」 안내가 보인다
  2 정해진 입력이 아니면 거절한다(「나」를 고르지 않고 주입) · 진행 그대로
  3 순서 밖 행동을 거절한다(다른 설비 버튼 · 승인 단계의 거절) · 진행 그대로
  4 안내서의 행동을 순서대로 하면 끝까지 간다(완주). 녹화의 마지막 상태가 화면에 보인다
  5 새로 고침해도 진행이 남는다
  6 「처음부터 다시 하기」가 이 사례의 진행 · 포털 저장 값만 지운다(실제 실행용 저장 값은 그대로)
  7 사례끼리 진행이 섞이지 않는다(같은 녹화를 다른 id 로 둔 시험용 사본 사례)
  8 브라우저가 정적 서버 밖으로 보낸 요청이 0건이다(AI · 설비 · 그래프 서비스 모두). 막은 시도는 따로 센다
  --live 를 주면 9 재생 없이 연 실제 포털이 서비스를 직접 부르고 재생 표시가 없는지(회귀)도 본다.
"""
from __future__ import annotations

import argparse
import functools
import gzip
import http.server
import json
import os
import shutil
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
WWW = ROOT / "it" / "portal" / "www"
OUT = ROOT / ".evidence" / "replay"
CHROME = os.environ.get("PW_CHROMIUM")   # Playwright 판과 맞는 브라우저가 따로 있을 때만 그 실행 파일 경로를 준다


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve(root: Path):
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(root)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("case", nargs="?", default="s01-lab3-cooler")
    ap.add_argument("--live")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    stem = f"e2e-{a.case}-{datetime.now().strftime('%Y%m%dT%H%M%S')}"
    # 시험용 사본: 같은 녹화를 다른 id 로 하나 더 둔다(7번 사례 분리). 저장소는 건드리지 않는다
    tmp = Path(tempfile.mkdtemp(prefix="replay-e2e-"))
    site = tmp / "www"
    shutil.copytree(WWW, site)
    index = json.loads((site / "replay" / "cases.json").read_text(encoding="utf-8"))
    entry = next(c for c in index["cases"] if c["id"] == a.case)
    twin = dict(entry, id=a.case + "-twin", title=entry["title"] + " (시험용 사본)")
    index["cases"].append(twin)
    # 13번(자유 글 칸): 같은 녹화에 첫 행동의 by(누른 사람 이름)를 자유 글 칸으로 둔 시험용 안내서
    g = json.loads((site / "replay" / entry["guide"]).read_text(encoding="utf-8"))
    first = next(i for i in g["items"] if i["kind"] == "action")
    first["match"]["free"] = ["by"]
    (site / "replay" / "cases" / "e2e-free.guide.json").write_text(json.dumps(g, ensure_ascii=False), encoding="utf-8")
    index["cases"].append(dict(entry, id=a.case + "-free", title=entry["title"] + " (자유 글 칸 시험)", guide="cases/e2e-free.guide.json"))
    (site / "replay" / "cases.json").write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    guide = json.loads((site / "replay" / entry["guide"]).read_text(encoding="utf-8"))
    rec_path = site / "replay" / entry["recording"]
    rec = json.loads(gzip.decompress(rec_path.read_bytes()) if rec_path.suffix == ".gz" else rec_path.read_bytes())
    httpd, base = serve(site)
    origin = urlparse(base).netloc
    results, outside = [], []

    def check(no, name, ok, evidence):
        results.append({"no": no, "name": name, "ok": bool(ok), "evidence": evidence})
        print(f"{'통과' if ok else '실패'} {no} {name} — {evidence}", flush=True)

    with sync_playwright() as p:
        b = p.chromium.launch(**({"executable_path": CHROME} if CHROME else {}))
        ctx = b.new_context(viewport={"width": 1440, "height": 1000})
        # 실제 실행용 포털이 남긴 「나」(재생과 섞이면 안 된다)
        ctx.add_init_script("try { if (!localStorage.getItem('hyd.me')) localStorage.setItem('hyd.me', 'user:lee-prod'); } catch (e) {}")
        ctx.on("request", lambda r: outside.append(f"{r.method} {r.url}") if urlparse(r.url).scheme in ("http", "https", "ws", "wss") and urlparse(r.url).netloc != origin else None)
        pg = ctx.new_page()
        pg.set_default_timeout(20000)
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        st = lambda: pg.evaluate("window.hydReplay.state()")
        msg = lambda: pg.locator(".replay-msg").inner_text()
        tab = lambda name: (pg.locator(f'.rail nav button[data-tab="{name}"]').click(), pg.wait_for_timeout(1200))

        def fast_forward():
            btn = pg.locator(".replay-actions button", has_text="기다리지 않고 넘기기")
            if btn.count():
                btn.first.click()
                pg.wait_for_timeout(2500)

        blocked_before = []
        try:
            # 1 시작
            pg.goto(base + "/replay/index.html")
            pg.locator("button", has_text="시작하기").first.click()
            pg.wait_for_function("window.hydReplay && window.hydReplay.state().done === 0")
            pg.wait_for_selector(".replay-panel")
            panel = pg.locator(".replay-panel").inner_text()
            check(1, "재생 시작 · 재생 표시", "재생 모드" in panel and "저장된 실행 기록" in panel and pg.locator(".env-badge").inner_text().startswith("재생 모드"),
                  panel.splitlines()[:3])
            pg.screenshot(path=str(OUT / f"{stem}-1-start.png"))

            acts = [i for i in guide["items"] if i["kind"] == "action"]
            # 2 정해진 입력이 아님: 「나」 없이 주입
            tab("scenario")
            pg.wait_for_timeout(1500)
            pg.locator('#units .unit[data-asset="HYD-01"] [data-act="degrade"]').click()
            pg.wait_for_timeout(1500)
            check(2, "정해진 입력이 아니면 거절", st()["done"] == 0 and "정해진 입력" in msg(), msg())
            # 3 순서 밖 행동: 다른 설비의 업무 버튼
            other = pg.locator('#units .unit[data-asset="HYD-02"] [data-act="biz-start"]')
            other.click()
            pg.wait_for_timeout(1500)
            check(3, "순서 밖 행동 거절(HYD-02 정기 점검)", st()["done"] == 0 and "지금 할 행동은" in msg(), msg())
            pg.screenshot(path=str(OUT / f"{stem}-3-refused.png"))

            # 4 완주: 안내서의 행동을 순서대로
            tab("inbox")
            pg.select_option("[data-inbox-me]", "user:kim-op")
            pg.wait_for_timeout(1500)
            tab("scenario")
            pg.wait_for_timeout(1500)
            pg.locator('#units .unit[data-asset="HYD-01"] [data-act="degrade"]').click()
            pg.wait_for_timeout(1500)
            ok_inject = st()["done"] == 1
            # 5 새로 고침 뒤 진행 유지
            pg.reload()
            pg.wait_for_function("window.hydReplay && window.hydReplay.state().done !== undefined")
            pg.wait_for_timeout(1500)
            check(5, "새로 고침 뒤 진행 유지", st()["done"] == 1, st())
            fast_forward()
            tab("instances")
            pg.wait_for_timeout(2000)
            pg.screenshot(path=str(OUT / f"{stem}-4a-before-approval.png"))
            # 승인 단계: 처리 건 · 작업 id 는 녹화의 승인 요청 경로에서 읽는다(화면이 보여 주는 것과 같다)
            approve = rec["actions"][1]["key"]
            wid = approve.split("/api/todolist/")[1].split("/")[0]
            # 그 승인 작업이 들어 있는 처리 건(녹화 전 스택에 남아 있던 다른 처리 건과 섞지 않는다)
            inst_id = next(k.split("/")[-1] for k, v in rec["frames"].items()
                           if k.startswith("process/api/instances/") and k.count("/") == 3 and "?" not in k and wid in rec["bodies"][v[-1][2]])
            pg.evaluate(f"window.hydInstancesOpenTask('{inst_id}', '{wid}')")
            pg.locator("#tdGo").wait_for(timeout=20000)
            pg.wait_for_timeout(2000)
            refused_reject = None
            if pg.locator("#tdRejectCard").count():
                pg.locator("#tdReason").fill("시험: 재생에서 거절이 막히는지")
                pg.locator("#tdRejectCard").click()
                pg.wait_for_timeout(1500)
                refused_reject = st()["done"] == 1 and "지금 할 행동은" in msg()
                check(3, "순서 밖 행동 거절(승인 단계의 거절)", refused_reject, msg())
            go = pg.locator("#tdGo")
            # 정해진 입력이 아님: 추천안(생산관리자 승인 사항)을 그대로 승인
            if not go.is_disabled():
                go.click()
                pg.wait_for_timeout(1500)
                check(2, "정해진 입력이 아니면 거절(추천안 그대로 승인)", st()["done"] == 1 and "정해진 입력" in msg(), msg())
                pg.locator("#tdGo").wait_for(timeout=20000)
            pg.evaluate("document.querySelectorAll('#todoPanel details').forEach(d => d.open = true)")
            pg.locator('#todoPanel input[name=hopt][value="skill:fan-max"], #todoPanel [data-ap-back="skill:fan-max"]').first.click()
            pg.wait_for_timeout(800)
            go = pg.locator("#tdGo")
            if go.is_disabled() and pg.locator("#tdPreview").count():
                pg.locator("#tdPreview").click()
                for _ in range(20):
                    pg.wait_for_timeout(500)
                    if not go.is_disabled():
                        break
            pg.screenshot(path=str(OUT / f"{stem}-4b-approval.png"))
            go.click()
            pg.wait_for_timeout(2000)
            done_after = st()["done"]
            for _ in range(3):
                fast_forward()
            pg.evaluate(f"window.hydInstancesSelect('{inst_id}')")
            pg.wait_for_timeout(3000)
            final_status = json.loads(rec["bodies"][rec["frames"][f"process/api/instances/{inst_id}"][-1][2]])["instance"]["status"]
            detail = pg.locator("#instDetail").inner_text()
            # 남은 설명 · 화면 단계를 학생처럼 하나씩 넘긴다(화면이면 열고 확인)
            for _ in range(30):
                primary = pg.locator(".replay-actions button.primary")
                if not primary.count():
                    break
                primary.first.click()
                pg.wait_for_timeout(700)
            panel = pg.locator(".replay-panel").inner_text()
            check(4, "완주(주입 → 승인 → 녹화 끝 상태)", ok_inject and done_after == len(acts) and "모두 마쳤습니다" in panel,
                  {"done": done_after, "actions": len(acts), "recorded_final_status": final_status, "detail_head": detail.splitlines()[:4]})
            pg.screenshot(path=str(OUT / f"{stem}-4c-end.png"))
            tab("trends")   # 그래프 서비스 틀은 막혀야 한다(8번에서 바깥 요청 0건으로 확인)
            pg.wait_for_timeout(1500)
            blocked_before = st()["blocked"]
            frame_text = pg.locator("#pTs1").get_attribute("srcdoc") or ""

            # 7 사례 분리: 사본 사례는 처음 상태
            pg.goto(base + f"/index.html?replay={a.case}-twin")
            pg.wait_for_function("window.hydReplay && window.hydReplay.state().done !== undefined")
            pg.wait_for_timeout(1000)
            twin_state = st()
            twin_me = pg.evaluate("localStorage.getItem('hyd.me')")
            check(7, "사례끼리 진행 · 저장 값 분리", twin_state["done"] == 0 and twin_me is None, {"twin_done": twin_state["done"], "twin_me": twin_me})

            # 6 처음부터 다시 하기
            pg.goto(base + f"/index.html?replay={a.case}")
            pg.wait_for_function("window.hydReplay && window.hydReplay.state().done !== undefined")
            pg.wait_for_timeout(1000)
            before = st()["done"]
            pg.locator(".replay-more summary").click()
            pg.locator(".replay-more button", has_text="처음부터 다시 하기").click()
            pg.wait_for_function("window.hydReplay && window.hydReplay.state().done === 0")
            pg.wait_for_timeout(1000)
            me_in_case = pg.evaluate("localStorage.getItem('hyd.me')")
            live_me = pg.evaluate("""(() => { const f = document.createElement('iframe'); f.src = 'about:blank'; document.body.append(f);
                                       const v = f.contentWindow.localStorage.getItem('hyd.me'); f.remove(); return v; })()""")
            check(6, "처음부터 다시 하기(이 사례만 초기화)", before == len(acts) and st()["done"] == 0 and me_in_case is None and live_me == "user:lee-prod",
                  {"before": before, "after": st()["done"], "case_me": me_in_case, "live_me": live_me})

        except Exception as e:  # noqa: BLE001 — 흐름이 끊겨도 8번(바깥 요청)은 판정한다
            check(0, "흐름이 중간에 끊김", False, f"{type(e).__name__}: {str(e)[:300]}")
            pg.goto(base + f"/index.html?replay={a.case}")
            pg.wait_for_timeout(1500)
            frame_text = None   # 그래프 틀 확인 전에 끊김
        # 8 바깥 요청 0건
        blocked = blocked_before + st()["blocked"]
        check(8, "정적 서버 밖 요청 0건(막은 시도는 따로)", not outside and (frame_text is None or "재생 모드" in frame_text),
              {"outside": outside[:10], "blocked_attempts": len(blocked), "blocked_kinds": sorted({x["how"] for x in blocked}),
               "grafana_frame": (frame_text or "확인 못 함")[:80]})

        # 13 자유 글 칸: 어떤 글이든 받고, 이어지는 결과가 강사 글로 녹화된 것임을 알린다
        pg.goto(base + f"/index.html?replay={a.case}-free")
        pg.wait_for_function("window.hydReplay && window.hydReplay.state().done === 0")
        tab("inbox")
        pg.select_option("[data-inbox-me]", "user:kim-op")
        pg.wait_for_timeout(1000)
        tab("scenario")
        pg.locator('#units .unit[data-asset="HYD-01"] [data-act="degrade"]').click()
        pg.wait_for_timeout(1500)
        check(13, "자유 글 칸은 받고 강사 글로 녹화됐음을 알림", st()["done"] == 1 and "강사가 쓴 「김운전」" in msg(), msg())

        # 10 · 11 · 12 키 없는 시작의 기본은 재생(바깥 요청 판정과 섞이지 않게 새 창에서)
        side = b.new_context(viewport={"width": 1280, "height": 900})
        sp = side.new_page()
        if not a.live:
            sp.goto(base + "/index.html")
            sp.wait_for_url("**/replay/index.html?from=service", timeout=15000)
            check(10, "서비스가 없으면 경고와 함께 재생으로", "연결할 수 없습니다" in sp.locator("#fromLive").inner_text(), sp.url)
        def worker_off(route):
            path = urlparse(route.request.url).path
            body = {"mode": "instance", "agent_bridge": "off", "definition": "anomaly_response"} if path == "/api/process/mode" else \
                   {"reachable": False, "agent_orch": "cliagents", "error": "ConnectionRefusedError"} if path == "/api/agents/status" else None
            return route.fulfill(status=200, json=body) if body is not None else route.abort()
        sp.route("http://127.0.0.1:8080/**", worker_off)
        sp.goto(base + "/index.html")
        sp.wait_for_url("**/replay/index.html?from=worker", timeout=15000)
        check(11, "워커 경로인데 키(워커)가 없으면 경고와 함께 재생으로", "AI 키(워커)" in sp.locator("#fromLive").inner_text(), sp.url)
        sp.locator("#fromLive a").click()
        sp.wait_for_timeout(5000)
        check(12, "「그래도 실제 실행으로 열기」는 재생으로 되돌리지 않는다", "/index.html?live=1" in sp.url and "/replay/" not in sp.url and not sp.locator(".replay-panel").count(), sp.url)
        side.close()

        # 9 실제 실행 경로 회귀
        if a.live:
            seen = []
            live = ctx.new_page()
            live.on("request", lambda r: seen.append(r.url))
            live.goto(a.live)
            live.wait_for_timeout(5000)
            has_panel = live.locator(".replay-panel").count()
            hyd = live.evaluate("typeof window.hydReplay")
            ports = sorted({urlparse(u).port for u in seen if urlparse(u).port})
            check(9, "재생 없이 연 포털은 서비스를 직접 부른다", not has_panel and hyd == "undefined" and 8080 in ports and 8000 in ports,
                  {"panel": has_panel, "hydReplay": hyd, "ports": ports})
        b.close()
    httpd.shutdown()
    shutil.rmtree(tmp, ignore_errors=True)
    report = {"case": a.case, "recording": rec["id"], "page_errors": errors, "results": results}
    (OUT / f"{stem}.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    bad = [r for r in results if not r["ok"]]
    print(f"{len(results) - len(bad)}/{len(results)} 통과 · 화면 오류 {len(errors)} · {OUT.relative_to(ROOT) / (stem + '.json')}")
    return 1 if bad or errors else 0


if __name__ == "__main__":
    sys.exit(main())
