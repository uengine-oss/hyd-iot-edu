"""재생 사례 녹화 드라이버 — 실제 스택에 붙은 포털을 녹화 모드(?replay-record=)로 열고, 안내서의 강사 행동을 화면 조작으로 한 번 수행한 뒤
녹화를 내려받는다. 계약: 문서/시스템/참조/재생모드.md

  .venv/bin/python scripts/replay_record.py s01-lab3-cooler [--portal http://127.0.0.1:8088/]
  → .evidence/replay/<사례>-<시각>.raw.json (원녹화) · 같은 이름의 .log · 단계별 화면
  이어서: .venv/bin/python scripts/replay_case.py build <원녹화> <사례>

강사가 손으로 녹화할 때는 포털 주소 뒤에 ?replay-record=<사례> 를 붙여 열고, 안내서대로 조작한 뒤 재생 안내 카드의 [녹화 저장]을 누른다.
이 드라이버는 그 조작을 자동으로 한 것이다. 사례마다 함수 하나다. 시작 전에 스택이 강의 배포본 값으로 떠 있어야 하고,
다른 진행 중 처리 건이 없어야 한다(녹화에 섞인다).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".evidence" / "replay"
CHROME = os.environ.get("PW_CHROMIUM")   # Playwright 판과 맞는 브라우저가 따로 있을 때만 그 실행 파일 경로를 준다
API = "http://127.0.0.1:8080"


def get(path):
    with urllib.request.urlopen(API + path, timeout=20) as r:
        return json.loads(r.read())


class Run:
    def __init__(self, page, stem):
        self.pg, self.stem, self.t0, self.lines = page, stem, time.time(), []

    def log(self, msg):
        line = f"{time.time() - self.t0:7.1f}s {msg}"
        print(line, flush=True)
        self.lines.append(line)

    def tab(self, name, wait=1.5):
        self.pg.locator(f'.rail nav button[data-tab="{name}"]').click()
        self.pg.wait_for_timeout(int(wait * 1000))

    def shot(self, name):
        self.pg.screenshot(path=str(OUT / f"{self.stem}-{name}.png"))

    def detail_tabs(self, wait):
        """처리 건 상세의 탭(진행 상황 · 처리 기록 · 결과 · 단계 표)을 차례로 연다. 보이지 않는 탭은 건너뛴다."""
        for k in ("flow", "record", "result", "log"):
            b = self.pg.locator(f'#instDetail [data-inst-tab="{k}"]:visible')
            if b.count():
                b.first.click(timeout=5000)
                self.pg.wait_for_timeout(int(wait * 1000))
            else:
                self.log(f"탭 {k} 이 보이지 않아 건너뜀")

    def browse(self, tabs, seconds):
        """기다리는 동안 안내서에 나오는 화면을 돌아가며 연다(학생이 그 시점에 열어도 응답이 있게)."""
        end = time.time() + seconds
        while time.time() < end:
            for t in tabs:
                self.tab(t, 1.2)


def case_s01_lab3_cooler(run: Run):
    pg = run.pg
    before = {i["proc_inst_id"] for i in get("/api/instances?limit=50")}
    running = [i["proc_inst_id"] for i in get("/api/instances?limit=50") if i.get("status") == "RUNNING"]
    if running:
        raise AssertionError(f"진행 중인 처리 건이 있어 녹화에 섞인다: {running}")
    with urllib.request.urlopen("http://127.0.0.1:8000/api/state", timeout=10) as r:
        ts1 = json.loads(r.read())["units"]["HYD-01"]["tags"]["TS1"]
    if ts1 >= 52:
        raise AssertionError(f"HYD-01 유온 {ts1} ℃ — 정상으로 돌아온 뒤 녹화한다")
    run.browse(["main", "scenario", "incidents", "instances"], 6)
    run.tab("inbox")
    pg.select_option("[data-inbox-me]", "user:kim-op")
    pg.wait_for_timeout(2000)
    run.log("나 = 김운전(운전원)")
    run.tab("scenario", 3)
    run.shot("1-normal")
    pg.locator('#units .unit[data-asset="HYD-01"] [data-act="degrade"]').click()
    run.log("HYD-01 쿨러 열화 주입")
    inst = None
    t_start = time.time()
    while time.time() - t_start < 600 and not inst:
        run.browse(["scenario", "incidents", "instances", "inbox"], 4)
        new = [i for i in get("/api/instances?limit=50") if i["proc_inst_id"] not in before]
        inst = new[0]["proc_inst_id"] if new else None
    assert inst, "처리 건이 열리지 않았다"
    run.log(f"처리 건 {inst}")
    run.shot("2-instance")
    # 진단 · 추천 화면을 승인 전에 한 번 연다(학생이 승인 전에 여는 화면의 응답을 녹화해 둔다)
    run.tab("instances", 1)
    pg.evaluate(f"window.hydInstancesSelect('{inst}')")
    pg.wait_for_timeout(1500)
    run.detail_tabs(0.8)
    approve, reassessed = None, False
    while time.time() - t_start < 900 and not approve:
        d = get(f"/api/instances/{inst}")
        if d["instance"]["status"] != "RUNNING":
            raise AssertionError(f"승인 전에 처리 건이 끝났다: {d['instance']['status']}")
        deferred = next((w for w in d["workitems"] if w["status"] == "PENDING" and (w.get("draft") or {}).get("_deferral")), None)
        if deferred and not reassessed:
            # 비해피 가지: 진단이 「근거 부족 · 보류」로 멈추면 강사가 사유를 적고 재평가를 요청한다(승인으로 넘기지 않는다)
            run.log(f"진단 보류: {deferred['draft']['_deferral']['reason']}")
            run.tab("instances", 1)
            pg.evaluate(f"window.hydInstancesSelect('{inst}')")
            box = pg.locator(f'[data-deferral-task="{deferred["id"]}"]')
            box.wait_for(timeout=20000)
            run.shot("2b-deferred")
            box.locator("[data-reassess-by]").fill("김운전")
            box.locator("[data-reassess-reason]").fill("경보 뒤 관측이 더 쌓였으니 원천을 다시 조회해 평가합니다")
            box.locator("[data-reassess]").click()
            reassessed = True
            run.log("재평가 요청")
        active = set(d["instance"].get("current_activity_ids") or [])
        approve = next((w for w in d["workitems"] if w["activity_id"] == "task:select" and (w["status"] == "IN_PROGRESS" or (w["status"] == "TODO" and "task:select" in active))), None)
        if not approve:
            pg.wait_for_timeout(1000)
    assert approve, "승인 작업이 오지 않았다"
    run.log(f"승인 작업 {approve['id']} · {approve['activity_name']}")
    # 선택 기한(20배속 약 30초) 안에 고른다. 추천안은 생산관리자 승인 사항이라 운전원은 자기 권한의 「팬 최대」를 고른다
    pg.evaluate(f"window.hydInstancesOpenTask('{inst}', '{approve['id']}')")
    go = pg.locator("#tdGo")
    go.wait_for(timeout=20000)
    pg.evaluate("document.querySelectorAll('#todoPanel details').forEach(d => d.open = true)")
    pick = pg.locator('#todoPanel input[name=hopt][value="skill:fan-max"], #todoPanel [data-ap-back="skill:fan-max"]').first
    pick.click()
    pg.wait_for_timeout(800)
    run.log("팬 최대 고름")
    if go.is_disabled() and pg.locator("#tdPreview").count():
        pg.locator("#tdPreview").click()
        run.log("검토본 만들기")
        for _ in range(20):
            pg.wait_for_timeout(500)
            if not go.is_disabled():
                break
    run.shot("4-approval")
    go.click()
    for _ in range(20):
        pg.wait_for_timeout(500)
        w = next(x for x in get(f"/api/instances/{inst}")["workitems"] if x["id"] == approve["id"])
        if w["status"] not in ("TODO", "IN_PROGRESS"):
            break
    if w["status"] in ("TODO", "IN_PROGRESS", "CANCELLED"):
        raise AssertionError(f"승인이 접수되지 않았다({w['status']}): {pg.locator('#todoPanel').inner_text()[:400]}")
    run.log(f"승인 → 선택 작업 {w['status']}")
    t_click = time.time()
    status = "RUNNING"
    while time.time() - t_click < 900 and status == "RUNNING":
        pg.evaluate(f"window.hydInstancesSelect('{inst}')")
        run.browse(["instances", "incidents", "scenario"], 4)
        status = get(f"/api/instances/{inst}")["instance"]["status"]
    run.log(f"처리 건 상태 {status}")
    # 끝난 뒤 근거를 거슬러 읽는 화면: 처리 건 상세의 탭들, 이상 확인 · 조치의 사건, 내 작업함
    pg.evaluate(f"window.hydInstancesSelect('{inst}')")
    pg.wait_for_timeout(2500)
    run.detail_tabs(2)
    run.shot("5-result")
    run.browse(["incidents", "instances", "inbox", "scenario", "main"], 12)
    return {"instance": inst, "status": status}


CASES = {"s01-lab3-cooler": case_s01_lab3_cooler}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("case", choices=sorted(CASES))
    ap.add_argument("--portal", default="http://127.0.0.1:8088/")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    stem = f"{a.case}-{datetime.now().strftime('%Y%m%dT%H%M%S')}"
    with sync_playwright() as p:
        b = p.chromium.launch(**({"executable_path": CHROME} if CHROME else {}))
        ctx = b.new_context(viewport={"width": 1440, "height": 1000})
        pg = ctx.new_page()
        pg.set_default_timeout(20000)
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(a.portal + f"?replay-record={a.case}")
        pg.wait_for_timeout(3000)
        run = Run(pg, stem)
        result, failure = None, None
        try:
            result = CASES[a.case](run)
        except Exception as e:  # noqa: BLE001 — 녹화는 어떤 경우에도 저장하고, 실패는 그대로 알린다
            failure = f"{type(e).__name__}: {e}"
            run.log("실패: " + failure[:500])
        rec = pg.evaluate("window.hydReplay.exportRecording()")
        raw = OUT / f"{stem}.raw.json"
        raw.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
        run.log(f"원녹화 {raw.relative_to(ROOT)} ({raw.stat().st_size:,} 바이트) · 읽기 {len(rec['frames'])}종 · 쓰기 {len(rec['writes'])}건 · 화면 오류 {len(errors)}")
        (OUT / f"{stem}.log").write_text("\n".join(run.lines + [json.dumps(result, ensure_ascii=False)] + errors) + "\n", encoding="utf-8")
        b.close()
    print(raw)
    return 1 if failure else 0


if __name__ == "__main__":
    sys.exit(main())
