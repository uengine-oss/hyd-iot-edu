"""A075/A079 — ingested knowledge reaches the runtime judgment (A079: the reviewed impact link makes the SOP reach the BSC) (meeting L253~302, L301): real HTTP + Neo4j + DMN MCP.

    .venv314/Scripts/python scripts/probe_knowledge_to_judgment.py .evidence/reaudit/a075-k2j-<n>

1. Upload a small manual whose SOP id does not exist yet, preview it with the structured parser, and commit it with a
   reviewer link to a failure mode. 2. The graph must hold the skill, its failure-mode relation and an OUTPUTS edge from the
   failure mode's dec:action-candidates rule. 3. The DMN service (the same tool the agents call) must list the new SOP among
   the evaluated cards for that failure mode. 4. Rolling the batch back removes the skill and the rule edge, and the DMN
   cards no longer list it. 5. The admin re-link API (PUT /api/kg/skills/{id} with failureMode) is replayed on an existing
   admin-registered skill and must be idempotent. Nothing is left behind except the archived source and the batch receipts.
"""
import base64
import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

PROCESS = "http://127.0.0.1:8080"
FM = "fm:bearing-degradation"
SOP = "SOP-TEST-91"
MANUAL = f"""# 시험 매뉴얼 (A075, 지식→판단 검증용)

## HT-1.1 팬 베어링 임시 점검
진동이 기준을 넘으면 아래 절차를 따른다.

### {SOP} 팬 베어링 임시 점검 절차
1. 설비를 정지하고 LOCAL로 전환한다.
2. 베어링 하우징 온도를 측정한다 (60 ℃ 이하).
3. 결과를 CMMS에 기록한다.
"""


def http(path, data=None, method=None):
    req = urllib.request.Request(PROCESS + path, data=None if data is None else json.dumps(data, ensure_ascii=False).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method=method or ("POST" if data is not None else "GET"))
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            return e.code, json.loads(body)
        except ValueError:
            return e.code, {"raw": body.decode(errors="replace")[:300]}


def cypher(q):
    r = subprocess.run(["docker", "exec", "hyd-iot-edu-neo4j-1", "cypher-shell", "-u", "neo4j", "-p", "hydpass123", "--format", "plain", q],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    return r.stdout.strip().splitlines()[1:] if r.returncode == 0 else ["ERR " + r.stderr[-200:]]


def dmn_cards(fm, cause):
    code = ("import asyncio,json\nfrom fastmcp import Client\nasync def run():\n"
            "    async with Client('http://127.0.0.1:8198/mcp',timeout=120) as c:\n"
            "        e=await c.call_tool('evaluate_cards',{'asset':'HYD-01','pattern':'FAN_VIBRATION','cause':%r,'failure_mode':%r})\n"
            "        print(next(x.text for x in e.content if x.type=='text'))\nasyncio.run(run())" % (cause, fm))
    r = subprocess.run(["docker", "exec", "hyd-iot-edu-dmn-mcp-1", "python", "-c", code], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    out = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "{}"
    d = json.loads(out)
    doc = d.get("document") or d
    doc["options"] = ((doc.get("result") or {}).get("options")) or doc.get("options") or []   # evaluated cards live under result
    return doc


def main():
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=False)
    report = {"started": datetime.now(timezone.utc).isoformat(), "checks": {}, "scope": __doc__}
    def save(n, v): (out / (n + ".json")).write_text(json.dumps(v, ensure_ascii=False, indent=2, default=str), encoding="utf8")
    def check(name, ok, detail=None):
        report["checks"][name] = {"passed": bool(ok), "detail": detail}; save("result", report)
        print(("PASS " if ok else "FAIL ") + name + ("" if detail is None else "  " + json.dumps(detail, ensure_ascii=False, default=str)[:240]), flush=True)
        assert ok, name
    def ok(path, data=None, method=None):
        s, v = http(path, data, method); assert s in (200, 201), (path, s, v); return v

    assert not cypher(f"MATCH (k:Skill {{sopId:'{SOP}'}}) RETURN k.id;"), "test SOP already in the graph"
    up = ok("/api/kg/manuals/preview", {"filename": "a075-test-manual.md", "data": base64.b64encode(MANUAL.encode("utf-8")).decode()}); save("preview", up)
    procs = {p["id"]: p for p in up["procedures"]}
    check("structured_preview_found_the_test_sop", SOP in procs and len(procs[SOP]["steps"]) == 3, {"procedures": list(procs), "batch": up["batch"]})
    body = {"reviewed": True, "by": "[회귀 검사] A075 검토자", "source_id": up["source_id"], "batch": up["batch"], "previous_batch": up.get("previous_batch"),
            "method": up["method"], "sections": up["sections"], "procedures": up["procedures"],
            "links": {SOP: {"failureMode": FM, "relation": "REMEDIED_BY", "kind": "work_order", "approver": "role:maint-mgr",
                            "affects": [{"target": "sv:bearing-wear", "sign": "-", "note": "A079: 점검으로 마모 진행을 늦춘다"}]}}}
    receipt = ok("/api/kg/manuals/commit", body); save("commit-receipt", receipt)
    check("commit_receipt_names_the_candidate_rules", receipt["candidate_activation"] == {FM: ["rule:cand-fan"]} and receipt["procedures"] == 1, receipt["candidate_activation"])
    sid = "skill:sop-test-91"
    rows = cypher(f"MATCH (r:Rule)-[o:OUTPUTS]->(k:Skill {{id:'{sid}'}}) RETURN r.id, o._manual_document IS NOT NULL;")
    fm_rows = cypher(f"MATCH (f:FailureMode)-[x:REMEDIED_BY]->(k:Skill {{id:'{sid}'}}) RETURN f.id;")
    check("graph_has_skill_failure_mode_and_rule_output_edge", any("rule:cand-fan" in r for r in rows) and any(FM in r for r in fm_rows), {"outputs": rows, "fm": fm_rows})
    aff = cypher(f"MATCH (k:Skill {{id:'{sid}'}})-[a:AFFECTS]->(t) RETURN t.id, a.sign, a._manual_document IS NOT NULL;")
    check("reviewed_impact_is_an_affects_edge_owned_by_the_batch", any("sv:bearing-wear" in r and "-1" in r for r in aff), aff)
    cards = dmn_cards(FM, "cause:fan-bearing-wear"); save("dmn-cards-after-commit", cards)
    mine = next((o for o in cards.get("options") or [] if o.get("sopId") == SOP or o.get("id") == sid), None)
    check("ingested_sop_now_scores_bsc_gain_or_loss_through_its_impact", mine is not None and (mine.get("scoreParts") or {}).get("bsc") not in (None, 0, 0.0),
          {"scoreParts": (mine or {}).get("scoreParts"), "gains": [(g.get("measure"), g.get("sign")) for g in (mine or {}).get("gains") or []][:4]})
    listed = [o.get("sopId") for o in cards.get("options") or []] + [x for x in [SOP] if SOP in (cards.get("explanation") or "")]
    check("dmn_cards_now_include_the_ingested_sop", SOP in (cards.get("explanation") or "") or SOP in listed, {"status": cards.get("status"), "explanation": (cards.get("explanation") or "")[:200]})
    rb = ok(f"/api/kg/manuals/batches/{receipt['batch']}/rollback", {"by": "[회귀 검사] A075 검토자"}); save("rollback", rb)
    gone = cypher(f"MATCH (k:Skill {{id:'{sid}'}}) RETURN k.id;")
    edge_gone = cypher(f"MATCH (:Rule)-[o:OUTPUTS]->(k:Skill {{id:'{sid}'}}) RETURN o;")
    check("rollback_removes_skill_and_rule_edge", not gone and not edge_gone, {"status": rb.get("status")})
    cards2 = dmn_cards(FM, "cause:fan-bearing-wear"); save("dmn-cards-after-rollback", cards2)
    check("dmn_cards_no_longer_include_it", SOP not in (cards2.get("explanation") or "") and SOP not in [o.get("sopId") for o in cards2.get("options") or []])
    # 5. admin re-link API on an admin-registered skill (idempotent replay). A156: the probe registers its own skill through the
    # admin create API instead of relying on skill:sop-fan-11 — that node existed only on one PC's graph (left by an earlier
    # admin registration, HANDOFF A133 "orphan Skill to delete") and is absent from a fresh seed. The fixture is removed at the end.
    fixture = "skill:sop-test-92"
    def drop_fixture():
        cypher(f"MATCH (k:Skill {{id:'{fixture}'}}) OPTIONAL MATCH (k)-[:HAS_STEP]->(st:Step) DETACH DELETE k, st;")
    drop_fixture()                                   # a run interrupted after creating it must not make this one fail
    try:
        made = ok("/api/kg/skills", {"name": "A156 시험 조치(관리자 등록)", "description": "[회귀 검사] 시험용 조치 — 끝나면 지운다",
                                     "sopId": "SOP-TEST-92", "steps": ["팬 베어링 소음 확인", "정비 요청 등록"], "failureMode": FM,
                                     "kind": "work_order", "relation": "REMEDIED_BY", "approver": "role:maint-mgr", "by": "[회귀 검사] A075 검토자",
                                     "request_id": str(uuid.uuid4())}); save("admin-create-fixture", made)
        skills = {s["id"]: s for s in ok("/api/kg/skills")}
        cur = skills[fixture]
        r = ok(f"/api/kg/skills/{fixture}", {"name": cur["name"], "description": cur["description"], "approver": (cur.get("approver") or {}).get("id"),
                                             "failureMode": FM, "relation": "REMEDIED_BY", "revision": cur["revision"], "by": "[회귀 검사] A075 검토자", "request_id": str(uuid.uuid4())}, method="PUT")
        save("relink-admin-fixture", r)
        check("admin_relink_keeps_rule_output_for_existing_skill", any(x["id"] == "rule:cand-fan" for x in r["rules"]) and [f["id"] for f in r["failureModes"]] == [FM],
              {"rules": [x["id"] for x in r["rules"]], "failureModes": [f["id"] for f in r["failureModes"]]})
    finally:
        drop_fixture()
    check("admin_fixture_removed", not cypher(f"MATCH (k:Skill {{id:'{fixture}'}}) RETURN k.id;"))
    report["finished"] = datetime.now(timezone.utc).isoformat(); save("result", report)
    print(f"ALL PASS: {len(report['checks'])} checks", flush=True)


if __name__ == "__main__":
    main()
