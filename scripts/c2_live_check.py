"""C2 라이브 확인 (강사 PC · 메인 스택을 건드리지 않음): 버리는 DB(c2_check, scripts/c2_scratch_db.sh)에 붙인 enterprise-sim(Supabase 백엔드)과
effects-mcp 를 이 PC 에서 따로 띄우고, 작은 SMTP 받는 곳(Inbucket 대역)으로 메일을 받아 C 경로의 부품을 실제로 부른다.

  1. 수업 원인 버튼: POST /erp/spare/issue → 가용이 재주문점 아래로
  2. ERP 재고 감시(business_monitor.scan_once)가 enterprise-sim 을 읽어 경보 한 건을 만든다 (같은 회차는 한 번)
  3. 승인 경로의 금액 확정(effect_parts.purchase_quote) — ERP 견적으로 330만 원
  4. ERP 발주(ent.exec_skill procure-part, 금액 · AVL 재확인) — 비AVL 은 거절
  5. 승인 뒤 MCP 호출(mcp_check.call_effect) → effects-mcp send_mail(SMTP) · add_calendar_entry · record_case, 같은 키 재호출은 replayed
  6. 입고 확인(receive-goods) → 재고 회복, 재고 이동 원장
  7. enterprise-mcp 읽기 도구(spare_stock · part_quotes · maintenance_windows)를 전용 읽기 계정으로

사용: python scripts/c2_live_check.py <증거 폴더>   (스크립트가 띄운 프로세스는 끝날 때 모두 내린다)
"""
from __future__ import annotations

import json
import os
import socket
import socketserver
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / ".evidence" / "a161-c2")
OUT.mkdir(parents=True, exist_ok=True)
PY = sys.executable
DB = os.getenv("C2_SCRATCH_DB", "c2_check")
DB_HOSTPORT = os.getenv("C2_DB_HOSTPORT", "127.0.0.1:54322")
# 관리 계정 DSN(비밀번호를 파일에 적지 않음). 강사 PC 에서 호스트 포트 인증이 막히면 Supabase 망 안 컨테이너에서 돌린다(c2-execution.md).
DSN = os.getenv("C2_ADMIN_DSN") or f"postgresql://postgres:postgres@{DB_HOSTPORT}/{DB}"
READER = f"postgresql://hyd_enterprise_reader:hyd-enterprise-read-local@{DB_HOSTPORT}/{DB}"
ENT, MCP, SMTP = 18095, 18197, 12525
for p in ("common", "it/process", "it/enterprise-sim", "it/enterprise-mcp", "it/effects-mcp"):
    sys.path.insert(0, str(ROOT / p))
log: list[dict] = []


def step(name, data):
    log.append({"step": name, "data": data})
    print(f"== {name}\n{json.dumps(data, ensure_ascii=False, default=str)[:600]}")


# ---------------------------------------------------------------- 작은 SMTP 받는 곳 (Inbucket 대역 — 받은 메일을 파일로)
MAILS: list[str] = []


class SmtpHandler(socketserver.StreamRequestHandler):
    def handle(self):
        w = lambda s: self.wfile.write((s + "\r\n").encode())
        w("220 c2-sink")
        data_mode, buf = False, []
        for raw in self.rfile:
            line = raw.decode("utf-8", "replace").rstrip("\r\n")
            if data_mode:
                if line == ".":
                    MAILS.append("\n".join(buf)); buf, data_mode = [], False; w("250 queued")
                else:
                    buf.append(line[1:] if line.startswith("..") else line)
                continue
            cmd = line.split(" ", 1)[0].upper()
            if cmd in ("EHLO", "HELO"):
                w("250 c2-sink")
            elif cmd == "DATA":
                data_mode = True; w("354 end with .")
            elif cmd == "QUIT":
                w("221 bye"); return
            else:
                w("250 ok")


def wait_port(port, t=20):
    end = time.time() + t
    while time.time() < end:
        try:
            socket.create_connection(("127.0.0.1", port), 0.5).close(); return
        except OSError:
            time.sleep(0.3)
    raise RuntimeError(f"port {port} did not open")


def http(method, path, body=None, port=ENT):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")


def main():
    procs = []
    smtp = socketserver.ThreadingTCPServer(("127.0.0.1", SMTP), SmtpHandler)
    threading.Thread(target=smtp.serve_forever, daemon=True).start()
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(str(ROOT / p) for p in ("common", "it/enterprise-sim", "it/effects-mcp")))
    try:
        procs.append(subprocess.Popen([PY, "-m", "uvicorn", "entsim.main:app", "--port", str(ENT), "--log-level", "info"],
                                      env=dict(env, ENTERPRISE_BACKEND="supabase", SUPABASE_DSN=DSN), cwd=ROOT))
        procs.append(subprocess.Popen([PY, "-m", "effects_mcp.server"], cwd=ROOT,
                                      env=dict(env, MCP_PORT=str(MCP), SMTP_HOST="127.0.0.1", SMTP_PORT=str(SMTP),
                                               ENTERPRISE_URL=f"http://127.0.0.1:{ENT}", EFFECTS_STATE_PATH=str(OUT / "effects-live.sqlite3"))))
        wait_port(ENT); wait_port(MCP)
        from procsvc import business_monitor, effect_parts, mcp_check

        status, body = http("POST", "/erp/spare/reset", {})
        if status != 200:
            raise RuntimeError(f"enterprise-sim 초기화 실패 {status}: {str(body)[:300]}")
        step("0 재고 초기화", body["records"])
        status, issued = http("POST", "/erp/spare/issue", {"part_no": "P-PMP-SEAL", "qty": 1, "reason": "수업 원인: 타 라인 긴급 사용", "by": "instructor"})
        step("1 예비품 출고 버튼", {"status": status, "detail": issued["transaction"]["detail"], "facts": issued["stock"]["facts"]})
        read = lambda name, params: http("GET", "/erp/spare_stock")[1]
        seen: set = set()
        alerts = business_monitor.scan_once(read, seen)
        step("2 ERP 재고 감시 경보", alerts)
        seen.update(a["alertId"] for a in alerts)
        step("2b 같은 회차 다시 읽기", {"new_alerts": business_monitor.scan_once(read, seen)})
        quotes = http("GET", "/scm/quotes?part=P-PMP-SEAL")[1]["records"]
        option = {"actions": [{"code": "PR_CREATE", "value": "sup:b"}]}
        quote = effect_parts.purchase_quote(option, {"alert": alerts[0]}, quotes)
        step("3 승인 경로 금액 확정", quote)
        bad = http("POST", "/api/exec", {"decision": "C2-LIVE-bad", "skill": "skill:procure-part", "asset": "HYD-03", "by": "buyer",
                                         "params": {"supplier": "sup:c", "part_no": "P-PMP-SEAL", "qty": 6}})
        step("4a 비AVL 발주 거절", {"status": bad[0], "body": str(bad[1])[:200]})
        dec = f"C2-LIVE-{int(time.time())}"
        status, po = http("POST", "/api/exec", {"decision": dec, "skill": "skill:procure-part", "asset": "HYD-03", "by": "buyer",
                                                "params": {"supplier": quote["approved_supplier"], "part_no": quote["approved_part_no"],
                                                           "qty": quote["approved_qty"], "amount": quote["approved_amount"], "part": "펌프 축 씰 키트"}})
        step("4 ERP 발주", {"status": status, "ref": po["ref"], "detail": po["detail"], "after": po["after"]})
        spec = mcp_check.normalize({"type": "url", "url": f"http://127.0.0.1:{MCP}/mcp", "transport": "streamable_http"})
        tools = mcp_check.check(spec)
        step("5a effects-mcp 도구 목록", [(t["name"], t["annotations"], t["callable"]) for t in tools["tools"]])
        key = f"{dec}:mail"
        mail = mcp_check.call_effect(spec, "send_mail", {"to": "supplier@hyd.local", "subject": f"[발주] P-PMP-SEAL 6개 {po['ref']}",
                                                         "body": f"B-OEM 귀중, 펌프 축 씰 키트 6개 발주합니다. 금액 330만원. 발주 {po['ref']}"},
                                     idempotency_key=key)
        again = mcp_check.call_effect(spec, "send_mail", {"to": "supplier@hyd.local", "subject": "재시도", "body": "x"}, idempotency_key=key)
        step("5b 승인 뒤 메일 (SMTP)", {"first": mail["result"], "retry_same_key": again["result"], "smtp_received": len(MAILS)})
        cal = mcp_check.call_effect(spec, "add_calendar_entry", {"asset": "HYD-03", "title": "씰 키트 입고 예정", "wo_ref": po["ref"],
                                                                 "starts_at": po["after"]["expected_at"]}, idempotency_key=f"{dec}:cal")
        rec = mcp_check.call_effect(spec, "record_case", {"title": "씰 키트 재고 보충", "body": "재주문점 이탈 → B-OEM 6개 발주", "asset": "HYD-03"},
                                    idempotency_key=f"{dec}:case")
        step("5c CMMS 일정 · 처리 건 기록", {"calendar": cal["result"], "case": rec["result"]})
        portal = mcp_check.call(spec, "send_mail", {"to": "x@y.z", "subject": "s", "body": "b"})
        step("5d 포털 '써 보기' 경로는 쓰기 도구를 거절", {"status": portal["status"], "error": portal.get("error")})
        status, gr = http("POST", "/api/exec", {"decision": dec, "skill": "skill:receive-goods", "asset": "HYD-03", "by": "process",
                                                "params": {"ref": po["ref"]}})
        step("6 입고 확인", {"status": status, "detail": gr["detail"], "stock": http("GET", "/erp/spare_stock?part=P-PMP-SEAL")[1]["facts"],
                         "po": http("GET", f"/erp/purchase_orders/{po['ref']}")[1]["facts"]["status"]})
        step("6b 재고 이동 원장", http("GET", "/erp/spare_stock?part=P-PMP-SEAL")[1]["movements"][:4])
        from enterprise_mcp.tools import EnterpriseTools
        from hydcommon.enterprise import reader_connection
        et = EnterpriseTools(lambda: reader_connection(READER))
        step("7 enterprise-mcp 읽기 (전용 읽기 계정)", {"spare_stock": et.read("spare_stock", part="P-PMP-SEAL")["document"]["facts"],
                                                       "quotes": et.read("part_quotes", part="P-PMP-SEAL")["document"]["records"],
                                                       "windows": et.read("maintenance_windows", asset="HYD-02")["document"]["records"][:2]})
        (OUT / "live-mail.eml").write_text(MAILS[0] if MAILS else "", encoding="utf-8")
        http("POST", "/erp/spare/reset", {})
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(10)
            except subprocess.TimeoutExpired:
                p.kill()
        smtp.shutdown()
        (OUT / "live-check.json").write_text(json.dumps(log, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
