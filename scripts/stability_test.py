"""Destructive-to-demo-state resilience checks; run after scenario_test.py on the local stack.

Stops/restarts only this Compose project's DB, sink, process and enterprise simulator.
All injected records have a unique STABILITY prefix. Never prints API credentials.
"""
import asyncio
import argparse
import copy
import json
from pathlib import Path
import subprocess
import time
import uuid

import httpx
import psycopg
from aiokafka import AIOKafkaProducer

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "STABILITY-" + uuid.uuid4().hex[:10]
P, E = "http://localhost:8080", "http://localhost:8095"
client = httpx.Client(timeout=15)
results = []


def check(name, ok, detail=""):
    results.append({"check": name, "ok": bool(ok), "detail": detail})
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}", flush=True)
    if not ok:
        raise AssertionError(name)


def compose(*args):
    r = subprocess.run(["docker", "compose", *args], cwd=ROOT, capture_output=True, text=True, timeout=120)
    if r.returncode:
        raise RuntimeError(f"compose {args} failed: {r.stderr[-500:]}")


def wait(fn, timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            value = fn()
            if value:
                return value
        except (httpx.HTTPError, psycopg.Error):
            pass
        time.sleep(.5)
    raise TimeoutError("condition not met")


def healthy(port):
    return client.get(f"http://localhost:{port}/healthz").status_code == 200


def sql(query, params=()):
    with psycopg.connect("postgresql://hyd:hyd@localhost:5432/hyd", connect_timeout=3) as conn:
        return conn.execute(query, params).fetchall()


async def inject_tags(start=0, count=40):
    producer = AIOKafkaProducer(bootstrap_servers="localhost:19092")
    await producer.start()
    try:
        for n in range(start, start + count):
            record = {"asset": "HYD-01", "name": PREFIX, "v": n}
            await producer.send_and_wait("plant.tag", json.dumps(record).encode(), key=b"HYD-01")
        await producer.send_and_wait("plant.tag", b"not-json", key=b"\xff")
        await producer.send_and_wait("plant.tag", json.dumps({"asset": "HYD-01", "name": PREFIX, "v": "bad-number"}).encode())
    finally:
        await producer.stop()


def database_recovery():
    compose("stop", "timescaledb")
    try:
        asyncio.run(inject_tags())
        wait(lambda: client.get("http://localhost:8094/healthz").status_code == 503, 30)
        check("DB outage is unhealthy", True)
        # Kill before a DB commit: Kafka must retain the unacknowledged records.
        compose("restart", "connect-sink")
    finally:
        compose("start", "timescaledb")
    wait(lambda: healthy(8094))
    count = lambda: sql("SELECT count(*),count(DISTINCT value) FROM tag_1s WHERE name=%s", (PREFIX,))[0]
    wait(lambda: count() == (40, 40))
    check("DB outage + sink restart preserve all 40 records exactly once", count() == (40, 40), str(count()))
    # Replay committed Kafka data deliberately: durable DB offsets must suppress duplicates.
    compose("stop", "connect-sink")
    try:
        compose("exec", "-T", "redpanda", "rpk", "group", "seek", "connect-sink", "--to", "start")
    finally:
        compose("start", "connect-sink")
    wait(lambda: healthy(8094))
    asyncio.run(inject_tags(start=40, count=1))
    wait(lambda: count() == (41, 41))
    check("Kafka replay reaches new marker without duplicating committed rows", count() == (41, 41), str(count()))


def process_recovery():
    old = client.get(P + "/api/incidents").json()
    source = next(i for i in old if i["state"] == "CLOSED")
    card = client.get(P + "/api/incidents/" + source["id"]).json()["card"]
    card = copy.deepcopy(card)
    card["alert"]["alertId"] = PREFIX
    created = client.post(P + "/api/incidents", json=card)
    created.raise_for_status()
    iid = created.json()["id"]
    compose("restart", "process")
    wait(lambda: healthy(8080))
    pending = client.get(P + "/api/incidents/" + iid).json()
    check("pending approval survives process restart", pending["state"] == "AWAITING_APPROVAL")
    check("closed incident survives process restart", client.get(P + "/api/incidents/" + source["id"]).json()["state"] == "CLOSED")
    decisions = client.get(P + "/api/decisions").json()
    reference = next(d for d in decisions if (d.get("origin") or {}).get("incident") == source["id"]
                     and d["scenario"]["id"] == "sc:delivery-vs-maintenance")
    payload = client.get(P + "/api/decisions/" + reference["id"]).json()
    payload.update(id=PREFIX, origin={"incident": iid}, asset=card["alert"]["asset"])
    client.post(P + "/api/decisions", json=payload).raise_for_status()
    hitl = {"decision": PREFIX, "option": "opt:sc1-derate", "by": PREFIX, "role": "role:prod-mgr", "fan_pct": 999}
    bad = client.post(P + f"/api/incidents/{iid}/decide", json=hitl)
    check("invalid HITL parameters preserve pending approval", bad.status_code == 400 and
          client.get(P + "/api/decisions/" + PREFIX).json()["state"] == "PENDING_APPROVAL")
    hitl.update(fan_pct=100, role="role:operator")
    bad = client.post(P + f"/api/incidents/{iid}/decide", json=hitl)
    check("HITL role denial preserves pending approval", bad.status_code == 403 and
          client.get(P + "/api/decisions/" + PREFIX).json()["state"] == "PENDING_APPROVAL")
    hitl.update(role="role:prod-mgr")
    # Genuine command path on the simulator; immediately restart before re-observation completes.
    approved = client.post(P + f"/api/incidents/{iid}/decide", json=hitl)
    approved.raise_for_status()
    check("corrected HITL request executes after rejected input", approved.json()["decision"]["state"] == "EXECUTED")
    cmd = approved.json()["cmd"]["cmdId"]
    compose("restart", "process")
    wait(lambda: healthy(8080))
    restored = client.get(P + "/api/incidents/" + iid).json()
    check("inflight restart preserves command and escalates without replay",
          restored["state"] == "ESCALATED" and restored["reason"] == "PROCESS_RESTART_REVIEW" and restored["cmdId"] == cmd,
          restored["state"])
    denied = client.post(P + f"/api/incidents/{iid}/approve", json={"actions": [{"code": "FAN_BOOST", "fan_pct": 100}]})
    check("reapproval after restart is rejected", denied.status_code == 400)
    client.post("http://localhost:8000/api/reset").raise_for_status()


def enterprise_recovery():
    request = {"decision": PREFIX, "option": "stability", "skill": "skill:schedule-maintenance", "asset": "HYD-01", "params": {}}
    first = client.post(E + "/api/exec", json=request)
    first.raise_for_status()
    compose("restart", "enterprise-sim")
    wait(lambda: healthy(8095))
    second = client.post(E + "/api/exec", json=request)
    check("enterprise retry after restart returns same transaction", first.json() == second.json(), first.json()["ref"])
    txs = client.get(E + "/api/transactions").json()
    check("enterprise work order is not executed twice", sum(t["decision"] == PREFIX for t in txs) == 1)
    conflict = client.post(E + "/api/exec", json=dict(request, params={"window": "changed"}))
    check("conflicting idempotency input is rejected", conflict.status_code == 400)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--process-only", action="store_true")
    args = parser.parse_args()
    started = time.monotonic()
    try:
        runs = client.get("http://localhost:8091/api/agent/runs").json()
        cards = [client.get("http://localhost:8091/api/agent/runs/" + r["id"]).json().get("card") or {}
                 for r in runs if r["status"] == "SUBMITTED"]
        sources = [c.get("summarySource") for c in cards]
        check("real model used inside the E2E pipeline", any(s and s != "template" for s in sources), str(sources))
        if not args.process_only:
            database_recovery()
        process_recovery()
        if not args.process_only:
            enterprise_recovery()
        for port in (8000, 8080, 8090, 8091, 8092, 8093, 8094, 8095):
            wait(lambda port=port: healthy(port))
        check("all 8 application services recovered", True)
    finally:
        output = ROOT / ".evidence" / ("hitl-recovery.json" if args.process_only else "stability.json")
        output.parent.mkdir(exist_ok=True)
        output.write_text(json.dumps({"id": PREFIX, "seconds": round(time.monotonic()-started, 2), "checks": results}, indent=2), encoding="utf-8")
        client.close()
