"""C3 조립: 수업 문서 A(HM-8) → B(PM-02) → C(PR-07)를 실제 워커(LLM) 추출 → 검토 승인 → 그래프 적재한다. 포털 지식 관리 화면과 같은 API ·
같은 적재 본문({...미리보기, links: 제안 그대로, by, reviewed: true})을 쓴다. 문서마다 걸린 시간과 영수증을 .evidence/a161-c3/ingest-*.json 에 남긴다.

  .venv/bin/python scripts/c3_ingest.py [HM-8 PM-02 PR-07]
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

API = os.environ.get("PROCESS_URL", "http://127.0.0.1:8080")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".evidence" / "a161-c3"
DOCS = {"HM-8": "HM-8_cooler-fan-manual.md", "PM-02": "PM-02_powerpack-pm-checklist.md", "PR-07": "PR-07_spare-parts-standard.md"}


def call(method, path, body=None, timeout=120):
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode(errors="replace")[:3000]}


def ingest(key: str) -> dict:
    fname = DOCS[key]
    raw = (ROOT / "docs" / "samples" / fname).read_bytes()
    t0 = time.monotonic()
    st, pv = call("POST", "/api/kg/manuals/preview", {"filename": fname, "data": base64.b64encode(raw).decode()})
    assert st == 200, pv
    sid = pv["source_id"]
    # 같은 원문의 추출이 이미 끝났으면(중간에 끊긴 실행) 그 결과를 다시 쓴다 — LLM 추출을 두 번 하지 않는다
    st, prev = call("GET", f"/api/kg/manuals/sources/{sid}/extractions")
    done = [x for x in (prev.get("items") or []) if x.get("status") == "COMPLETED"] if st == 200 else []
    if done:
        inst = {"instance": done[0]["proc_inst_id"], "reused": True}
    else:
        st, inst = call("POST", f"/api/kg/manuals/sources/{sid}/extractions", {"request_id": str(uuid.uuid4())})
        assert st == 200, inst
    t_start = time.monotonic()
    while True:
        st, res = call("GET", f"/api/kg/manuals/sources/{sid}/extractions/{inst['instance']}")
        if res.get("preview"):
            break
        if res.get("status") in ("FAILED", "CANCELLED") or time.monotonic() - t_start > 1800:
            raise SystemExit(f"{key} extraction did not finish: {json.dumps(res, ensure_ascii=False)[:1500]}")
        time.sleep(5)
    t_extracted = time.monotonic()
    preview = res["preview"]
    links = {p["id"]: p["link"] for p in preview["procedures"] if p.get("link")}
    body = dict(preview, links=links, by="[C3 조립] 실제 추출 검토", reviewed=True)
    st, receipt = call("POST", "/api/kg/manuals/commit", body)
    dropped = []
    if st == 409 and preview.get("knowledge_conflicts"):
        # C1 §3.4: 이미 있는 id 는 항목을 빼고 그 id 를 참조한다
        ids = {c["id"] for c in preview["knowledge_conflicts"]}
        kn = {k: [x for x in v if x.get("id") not in ids] for k, v in (preview.get("knowledge") or {}).items()}
        dropped = sorted(ids)
        st, receipt = call("POST", "/api/kg/manuals/commit", dict(body, knowledge=kn))
    t_done = time.monotonic()
    rec = {"doc": key, "source_id": sid, "instance": inst["instance"], "segments": inst.get("segments"), "reused_extraction": bool(inst.get("reused")), "commit_status": st,
           "dropped_conflicts": dropped, "seconds": {"extract": round(t_extracted - t_start, 1), "commit": round(t_done - t_extracted, 1),
                                                    "total": round(t_done - t0, 1)},
           "procedures": len(preview["procedures"]), "links": len(links),
           "knowledge": {k: len(v) for k, v in (preview.get("knowledge") or {}).items()}, "receipt": receipt}
    (OUT / f"ingest-{key}.json").write_text(json.dumps(dict(rec, preview=preview), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: rec[k] for k in ("doc", "commit_status", "seconds", "procedures", "links", "knowledge", "dropped_conflicts")}, ensure_ascii=False))
    if st != 200:
        print(json.dumps(receipt, ensure_ascii=False)[:2500])
    return rec


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for key in sys.argv[1:] or list(DOCS):
        if ingest(key)["commit_status"] != 200:
            sys.exit(1)
