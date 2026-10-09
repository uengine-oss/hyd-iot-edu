"""C3 조립: 수업 문서 A(HM-8) → B(PM-02) → C(PR-07)를 실제 워커(LLM)로 추출하고, 사람이 남긴 검토 기록을 적용해 그래프에 적재한다.
포털 지식 관리 화면과 같은 API · 같은 적재 본문({...미리보기, links, knowledge, by, reviewed: true})을 쓴다.

검토 없이는 적재하지 않는다(실라버스 OL7 "사람이 확인한 것만 지식에 잇는다"). 2026-10-10 전에는 이 스크립트가 제안을 손대지 않고
reviewed=true · 지어낸 검토자 이름으로 적재했고, 라이브 4차 C 판단은 그 검토되지 않은 지식(SOP-PUR-13 → A정밀 오연결)으로 돌았다.

  1) 추출만  .venv/bin/python scripts/c3_ingest.py extract PR-07 [HM-8 PM-02] [--reuse]
             → .evidence/a161-c3/proposal-<문서>.json (제안 전체: 절차 · 연결 · 지식 · 경고). 적재하지 않는다.
             --reuse 는 같은 원문의 끝난 추출을 다시 쓴다. 시드 구조(판단 입력)나 추출 지시 판본이 바뀌었으면 쓰지 않는다 —
             옛 추출은 옛 목록(ontology_catalog)을 보고 만든 것이다.
  2) 적재    .venv/bin/python scripts/c3_ingest.py commit PR-07 --review <검토 기록.json>
             → .evidence/a161-c3/ingest-<문서>.json (영수증 · 적용한 검토 변경 · 원문 좌표)

검토 기록(문서 하나에 파일 하나, 사람이 proposal-<문서>.json 을 원문과 대조한 뒤 쓴다):
  {"doc": "PR-07", "by": "검토한 사람", "extraction": "<proposal 의 extraction.instance>", "warnings_read": true,
   "links": {"SOP-…": {"set": {"actions": [...]}, "reason": "왜 고치나", "quote": "근거 원문 문장"}},
   "drop":  {"rule:…": {"reason": "…", "quote": "…"}},
   "add":   {"rules": [{…지식 항목 (anchor 대신 quote)…, "reason": "…"}]}}
고칠 것이 없으면 links · drop · add 를 빼고 warnings_read 만 true 로 둔다(그대로 승인도 사람의 결정으로 남긴다).
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
LINK_FIELDS = ("failureMode", "relation", "kind", "approver", "actions", "addresses", "affects")
KNOWLEDGE_KINDS = ("failure_modes", "causes", "evidence", "rules")
EXTRACTION_TIMEOUT_S = 1800


class ReviewError(ValueError):
    """검토 기록이 없거나 제안 · 원문과 맞지 않는다 — 적재하지 않는다."""


def call(method, path, body=None, timeout=120):
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode(errors="replace")[:3000]}


def anchor(source: dict, quote: str, where: str) -> dict:
    """원문 좌표: 인용문이 문서 전체에서 정확히 한 곳에 있어야 한다(검토 화면 · 적재 검사와 같은 기준)."""
    if not isinstance(quote, str) or not quote.strip():
        raise ReviewError(f"{where}: 근거 원문 문장(quote)이 필요합니다")
    hits = [(p["page"], p["text"].find(quote)) for p in source["pages"] if quote in p["text"]]
    if len(hits) != 1 or source["pages"][hits[0][0] - 1]["text"].count(quote) != 1:
        raise ReviewError(f"{where}: 인용문이 원문에 한 번만 있어야 합니다 ({len(hits)}쪽에서 찾음): {quote[:80]}")
    page, start = hits[0]
    return dict(source_id=source["source_id"], page=page, start=start, end=start + len(quote), quote=quote)


def _reason(change: dict, where: str) -> str:
    reason = change.get("reason") if isinstance(change, dict) else None
    if not isinstance(reason, str) or not reason.strip():
        raise ReviewError(f"{where}: 검토 사유(reason)가 필요합니다")
    return reason.strip()


def apply_review(key: str, preview: dict, source: dict, review: dict) -> tuple[dict, list[dict]]:
    """사람의 검토 기록을 추출 제안에 적용해 적재 본문을 만든다. 순수 함수 — 네트워크 없음.
    반환: (적재 본문, 적용한 변경 목록[무엇 · 사유 · 원문 좌표]). 맞지 않는 기록은 ReviewError(좌표 포함)로 거부한다."""
    if not isinstance(review, dict) or review.get("doc") != key:
        raise ReviewError(f"{key}: 이 문서의 검토 기록이 아닙니다(doc={review.get('doc') if isinstance(review, dict) else None!r})")
    by = review.get("by")
    if not isinstance(by, str) or not by.strip():
        raise ReviewError(f"{key}: 검토한 사람(by)이 필요합니다")
    instance = (preview.get("extraction") or {}).get("instance")
    if review.get("extraction") != instance:
        raise ReviewError(f"{key}: 검토 기록의 추출 {review.get('extraction')!r} 과 제안의 추출 {instance!r} 이 다릅니다 — 다른 제안을 검토했습니다")
    if review.get("warnings_read") is not True:
        raise ReviewError(f"{key}: 추출 경고 {len(preview.get('warnings') or [])}개를 읽었다는 표시(warnings_read: true)가 필요합니다")
    links = {p["id"]: dict(p["link"]) for p in preview["procedures"] if p.get("link")}
    knowledge = {k: [dict(x) for x in (preview.get("knowledge") or {}).get(k) or []] for k in KNOWLEDGE_KINDS}
    changes = []
    for sop, change in (review.get("links") or {}).items():
        where = f"{key} {sop} 연결"
        if sop not in {p["id"] for p in preview["procedures"]}:
            raise ReviewError(f"{where}: 제안에 없는 SOP 입니다")
        fields = change.get("set") if isinstance(change, dict) else None
        if not isinstance(fields, dict) or not fields or set(fields) - set(LINK_FIELDS):
            raise ReviewError(f"{where}: set 은 연결 필드({', '.join(LINK_FIELDS)}) 중 하나 이상이어야 합니다")
        reason, at = _reason(change, where), anchor(source, change.get("quote"), where)
        before = {k: links.get(sop, {}).get(k) for k in fields}
        links[sop] = dict(links.get(sop) or {}, **fields)
        changes.append(dict(kind="link", target=sop, before=before, after=fields, reason=reason, anchor=at))
    for item_id, change in (review.get("drop") or {}).items():
        where = f"{key} {item_id} 빼기"
        kind = next((k for k in KNOWLEDGE_KINDS if any(x.get("id") == item_id for x in knowledge[k])), None)
        if kind is None:
            raise ReviewError(f"{where}: 제안 지식에 없는 id 입니다")
        reason, at = _reason(change, where), anchor(source, change.get("quote"), where)
        knowledge[kind] = [x for x in knowledge[kind] if x.get("id") != item_id]
        changes.append(dict(kind="drop", target=item_id, reason=reason, anchor=at))
    for kind, items in (review.get("add") or {}).items():
        if kind not in KNOWLEDGE_KINDS or not isinstance(items, list):
            raise ReviewError(f"{key} 더하기: 지식 종류는 {', '.join(KNOWLEDGE_KINDS)} 중 하나의 목록입니다({kind!r})")
        for item in items:
            where = f"{key} {item.get('id') if isinstance(item, dict) else item!r} 더하기"
            if not isinstance(item, dict) or not item.get("id") or any(x.get("id") == item["id"] for x in knowledge[kind]):
                raise ReviewError(f"{where}: id 가 있고 제안에 없는 항목이어야 합니다")
            reason, at = _reason(item, where), anchor(source, item.get("quote"), where)
            added = {k: v for k, v in item.items() if k not in ("quote", "reason")}
            knowledge[kind].append(dict(added, anchor=at))
            changes.append(dict(kind="add", target=item["id"], reason=reason, anchor=at))
    body = dict(preview, links=links, knowledge=knowledge, by=by.strip(), reviewed=True)
    return body, changes


def extract(key: str, reuse: bool) -> dict:
    fname = DOCS[key]
    raw = (ROOT / "docs" / "samples" / fname).read_bytes()
    st, pv = call("POST", "/api/kg/manuals/preview", {"filename": fname, "data": base64.b64encode(raw).decode()})
    if st != 200:
        raise SystemExit(f"{key} preview failed {st}: {pv}")
    sid = pv["source_id"]
    inst = None
    if reuse:
        st, prev = call("GET", f"/api/kg/manuals/sources/{sid}/extractions")
        done = [x for x in (prev.get("items") or []) if x.get("status") == "COMPLETED"] if st == 200 else []
        inst = {"instance": done[0]["proc_inst_id"], "reused": True} if done else None
    if inst is None:
        st, inst = call("POST", f"/api/kg/manuals/sources/{sid}/extractions", {"request_id": str(uuid.uuid4())})
        if st != 200:
            raise SystemExit(f"{key} extraction start failed {st}: {inst}")
    t_start = time.monotonic()
    while True:
        st, res = call("GET", f"/api/kg/manuals/sources/{sid}/extractions/{inst['instance']}")
        if res.get("preview"):
            break
        if res.get("status") in ("FAILED", "CANCELLED") or time.monotonic() - t_start > EXTRACTION_TIMEOUT_S:
            raise SystemExit(f"{key} extraction did not finish: {json.dumps(res, ensure_ascii=False)[:1500]}")
        time.sleep(5)
    preview = res["preview"]
    rec = {"doc": key, "source_id": sid, "instance": inst["instance"], "reused_extraction": bool(inst.get("reused")),
           "segments": inst.get("segments"), "extract_seconds": round(time.monotonic() - t_start, 1), "preview": preview}
    path = OUT / f"proposal-{key}.json"
    path.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"doc": key, "proposal": str(path.relative_to(ROOT)), "extraction": preview["extraction"]["instance"],
                      "procedures": len(preview["procedures"]), "warnings": len(preview.get("warnings") or []),
                      "knowledge": {k: len(v) for k, v in (preview.get("knowledge") or {}).items()}}, ensure_ascii=False))
    return rec


def commit(key: str, review_path: Path) -> int:
    proposal_path = OUT / f"proposal-{key}.json"
    if not proposal_path.exists():
        raise ReviewError(f"{key}: 추출 제안 {proposal_path.relative_to(ROOT)} 이 없습니다 — 먼저 extract 로 추출하고 검토하세요")
    rec = json.loads(proposal_path.read_text(encoding="utf-8"))
    review = json.loads(review_path.read_text(encoding="utf-8"))
    st, source = call("GET", f"/api/kg/manuals/sources/{rec['source_id']}")
    if st != 200:
        raise SystemExit(f"{key} source read failed {st}: {source}")
    body, changes = apply_review(key, rec["preview"], source, review)
    t0 = time.monotonic()
    st, receipt = call("POST", "/api/kg/manuals/commit", body)
    dropped = []
    if st == 409 and rec["preview"].get("knowledge_conflicts"):
        # C1 §3.4: 이미 있는 id 는 항목을 빼고 그 id 를 참조한다(빠진 id 는 영수증 dropped_conflicts 에 남는다)
        ids = {c["id"] for c in rec["preview"]["knowledge_conflicts"]}
        dropped = sorted(ids)
        st, receipt = call("POST", "/api/kg/manuals/commit",
                           dict(body, knowledge={k: [x for x in v if x.get("id") not in ids] for k, v in body["knowledge"].items()}))
    out = {"doc": key, "source_id": rec["source_id"], "instance": rec["instance"], "commit_status": st, "by": body["by"],
           "review_file": str(review_path), "review_changes": changes, "dropped_conflicts": dropped,
           "seconds": {"extract": rec.get("extract_seconds"), "commit": round(time.monotonic() - t0, 1)},
           "procedures": len(body["procedures"]), "links": len(body["links"]),
           "knowledge": {k: len(v) for k, v in body["knowledge"].items()}, "receipt": receipt, "preview": rec["preview"]}
    (OUT / f"ingest-{key}.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("doc", "commit_status", "by", "review_changes", "knowledge", "dropped_conflicts")}, ensure_ascii=False))
    if st != 200:
        print(json.dumps(receipt, ensure_ascii=False)[:2500])
    return st


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in ("extract", "commit"):
        print(__doc__)
        return 2
    mode, rest = argv[0], argv[1:]
    reuse = "--reuse" in rest
    review = Path(rest[rest.index("--review") + 1]) if "--review" in rest else None
    keys = [a for a in rest if a in DOCS]
    unknown = [a for a in rest if a not in DOCS and a not in ("--reuse", "--review") and (review is None or a != str(review))]
    if unknown or not keys:
        print(f"문서 이름은 {', '.join(DOCS)} 중에서 고릅니다(알 수 없음: {unknown})")
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    if mode == "extract":
        for key in keys:
            extract(key, reuse)
        return 0
    if review is None or len(keys) != 1:
        print("commit 은 문서 하나와 그 문서의 검토 기록(--review 파일)을 받습니다")
        return 2
    try:
        return 0 if commit(keys[0], review) == 200 else 1
    except ReviewError as exc:
        print(f"적재하지 않음 — {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
