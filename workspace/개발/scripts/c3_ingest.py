"""C3 조립: 수업 문서 A(HM-8) → B(PM-02) → C(PR-07)를 실제 워커(LLM)로 추출하고, 명시 검토 기록을 적용해 그래프에 적재한다.
포털 지식 관리 화면과 같은 API · 같은 적재 본문({...미리보기, links, knowledge, by, reviewed: true})을 쓴다.

검토 없이는 적재하지 않는다(실라버스 OL7 "사람이 확인한 것만 지식에 잇는다"). 사용자가 Codex에 검토를 명시 위임한 경우
검토 방식과 신원을 별도로 기록하며, 사람이 직접 검토했다고 표시하지 않는다. 2026-10-10 전에는 이 스크립트가 제안을 손대지 않고
reviewed=true · 지어낸 검토자 이름으로 적재했고, 라이브 4차 C 판단은 그 검토되지 않은 지식(SOP-PUR-13 → A정밀 오연결)으로 돌았다.

  1) 추출만  .venv/bin/python workspace/개발/scripts/c3_ingest.py extract PR-07 [HM-8 PM-02] [--reuse]
             → 작업/c3_ingest/proposal-<문서>.json (제안 전체: 절차 · 연결 · 지식 · 경고). 적재하지 않는다.
             --reuse 는 같은 원문의 끝난 추출을 다시 쓴다. 시드 구조(판단 입력)나 추출 지시 판본이 바뀌었으면 쓰지 않는다 —
             옛 추출은 옛 목록(ontology_catalog)을 보고 만든 것이다. 같은 내용의 어느 원문 판본에서도 끝난 추출을 못 찾으면
             새로 추출하지 않고 멈춘다. 같은 추출을 다시 적재할 때도 --reuse 로 미리보기를 새로 받는다 — 옛 proposal 파일의
             배치 id 는 첫 적재에 쓰여 「배치 ID가 이미 다른 내용/상태로 사용됐습니다」로 거부된다.
  2) 적재    .venv/bin/python workspace/개발/scripts/c3_ingest.py commit PR-07 --review <검토 기록.json>
             → 작업/c3_ingest/ingest-<문서>.json (영수증 · 적용한 검토 변경 · 원문 좌표)

검토 기록(문서 하나에 파일 하나, proposal-<문서>.json 을 원문과 대조한 뒤 실제 검토 방식·신원으로 쓴다):
  {"doc": "PR-07", "by": "실제 검토 신원", "extraction": "<proposal 의 extraction.instance>", "warnings_read": true,
   "links": {"SOP-…": {"set": {"actions": [...]}, "reason": "왜 고치나", "quote": "근거 원문 문장"}},
   "drop":  {"rule:…": {"reason": "…", "quote": "…"}},
   "add":   {"rules": [{…지식 항목 (anchor 대신 quote)…, "reason": "…"}]}}
고칠 것이 없으면 links · drop · add 를 빼고 warnings_read 만 true 로 둔다(그대로 검토한 결정도 기록한다).
"""
from __future__ import annotations

import base64
from copy import deepcopy
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

API = os.environ.get("PROCESS_URL", "http://127.0.0.1:8080")
ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "작업" / "c3_ingest"
DOCS = {"HM-8": "HM-8_cooler-fan-manual.md", "PM-02": "PM-02_powerpack-pm-checklist.md", "PR-07": "PR-07_spare-parts-standard.md"}
LINK_FIELDS = ("failureMode", "relation", "kind", "approver", "actions", "addresses", "affects", "scope", "executable", "parts", "supplier_policy", "maintenance_policy", "purchase_comparison_policy")
PROCEDURE_FIELDS = ('steps', 'existing_skill_id', 'reference_contract_sha256')
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


def _checked_coordinates(source, value, where):
    """An existing repeated sentence needs its exact verified source coordinates."""
    if not isinstance(value, dict) or value.get('source_id') != source['source_id']:
        raise ReviewError(f'{where}: 원문 좌표의 자료가 다릅니다')
    page, start, end = (value.get(k) for k in ('page', 'start', 'end'))
    if any(type(v) is not int for v in (page, start, end)) or not 1 <= page <= len(source['pages']):
        raise ReviewError(f'{where}: 원문 페이지와 문자 좌표가 필요합니다')
    text = source['pages'][page - 1]['text']
    if not 0 <= start < end <= len(text) or text[start:end] != value.get('quote'):
        raise ReviewError(f'{where}: 원문 좌표와 인용문이 일치하지 않습니다')
    return dict(source_id=source['source_id'], page=page, start=start, end=end, quote=value['quote'])


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
    procedures = deepcopy(preview['procedures'])
    own_links = preview.get('links') or {}
    links = {p['id']: deepcopy(own_links[p['id']] if p['id'] in own_links else p.get('link') or {}) for p in procedures}
    knowledge = {k: [dict(x) for x in (preview.get("knowledge") or {}).get(k) or []] for k in KNOWLEDGE_KINDS}
    changes = []
    for sop, change in (review.get('procedures') or {}).items():
        where = f'{key} {sop} 원문 절차 검토'
        procedure = next((p for p in procedures if p['id'] == sop), None)
        fields = change.get('set') if isinstance(change, dict) else None
        if procedure is None or not isinstance(fields, dict) or not fields or set(fields) - set(PROCEDURE_FIELDS):
            raise ReviewError(f'{where}: 제안에 있는 절차와 허용 검토 필드({PROCEDURE_FIELDS})가 필요합니다')
        reason, at = _reason(change, where), anchor(source, change.get('quote'), where)
        checked = deepcopy(fields)
        if 'steps' in checked:
            steps = checked['steps']
            if not isinstance(steps, list) or not steps:
                raise ReviewError(f'{where}: 원문 단계 목록이 필요합니다')
            checked_steps = []
            for order, step in enumerate(steps, 1):
                if (not isinstance(step, dict) or step.get('order') != order or type(step.get('order')) is not int
                        or step.get('text') != step.get('quote') or not isinstance(step.get('manual'), str)):
                    raise ReviewError(f'{where}: 연속 번호·정확한 원문 텍스트·절 식별자가 필요합니다')
                original = next((s for s in procedure['steps'] if s.get('order') == order
                                 and (s.get('anchor') or {}).get('quote') == step.get('quote')
                                 and s.get('manual') == step['manual']), None)
                step_at = (_checked_coordinates(source, original['anchor'], f'{where} 단계{order}') if original
                           else anchor(source, step.get('quote'), f'{where} 단계{order}'))
                checked_steps.append(dict(order=order, text=step['text'], manual=step['manual'], anchor=step_at))
            checked['steps'] = checked_steps
        before = {k: deepcopy(procedure.get(k)) for k in checked}
        procedure.update(checked)
        changes.append(dict(kind='procedure', target=sop, before=before, after=deepcopy(checked), reason=reason, anchor=at))
    for sop, change in (review.get("links") or {}).items():
        where = f"{key} {sop} 연결"
        if sop not in {p["id"] for p in preview["procedures"]}:
            raise ReviewError(f"{where}: 제안에 없는 SOP 입니다")
        fields = change.get("set") if isinstance(change, dict) else None
        if not isinstance(fields, dict) or not fields or set(fields) - set(LINK_FIELDS):
            raise ReviewError(f"{where}: set 은 연결 필드({', '.join(LINK_FIELDS)}) 중 하나 이상이어야 합니다")
        reason, at = _reason(change, where), anchor(source, change.get("quote"), where)
        before = {k: links.get(sop, {}).get(k) for k in fields}
        fields = deepcopy(fields)
        links[sop] = dict(links.get(sop) or {}, **fields)
        changes.append(dict(kind="link", target=sop, before=before, after=deepcopy(fields), reason=reason, anchor=at))
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
    method = review.get('method', 'human-reviewed')
    if method not in ('human-reviewed', 'user-delegated-ai-review'):
        raise ReviewError(f'{key}: 검토 수행 방식(method)이 지원 계약과 다릅니다')
    body = dict(deepcopy(preview), procedures=procedures, links=links, knowledge=knowledge, by=by.strip(), reviewed=True,
                method=preview.get('method') or method, review_method=method)
    return body, changes


def loaded_document(fname: str) -> str | None:
    """그래프에 지금 적재된(current) 같은 파일의 문서 id. 다시 뽑을 때 이 id 로 올려야 같은 문서의 새 판이 된다 — 포털 지식 관리의
    [개정] 버튼과 같은 계약(hitl.js data-manual-revise → preview document_id). 없이 올리면 새 문서가 생겨, 적재가 옛 문서가 소유한
    절차를 덮어쓰지 못하고 409 로 거절된다(manual_graph._validate_targets, 2026-10-10 라이브)."""
    st, rows = call("GET", "/api/kg/manuals")
    if st != 200:
        raise SystemExit(f"적재 이력 읽기 실패 {st}: {rows}")
    ids = sorted({r["document_id"] for r in rows if r.get("current") and r.get("filename") == fname})
    if len(ids) > 1:
        raise SystemExit(f"{fname}: 지금 적재된 문서가 {len(ids)}개입니다({', '.join(ids)}) — 어느 판을 개정할지 정할 수 없습니다")
    return ids[0] if ids else None


def _source_document(source: dict) -> str | None:
    """원문 판본이 속한 문서 id. 목록 행의 document_id, 없으면 source_id(manual:<문서>:<sha256>)에서 읽는다."""
    if source.get("document_id"):
        return source["document_id"]
    parts = str(source.get("source_id") or "").split(":")
    return parts[1] if len(parts) == 3 and parts[0] == "manual" else None


def finished_extraction(key: str, fname: str, sha: str, document_id: str | None = None) -> tuple[str, dict]:
    """--reuse: 같은 파일 · 같은 내용(sha256)의 원문 판본 가운데 최근 판본부터, 미리보기가 나오는(원문 검증을 통과한) 추출을 찾는다.
    원문을 올릴 때마다 판본 id(source_id)가 새로 생기므로 이번에 올린 판본만 보면 끝난 추출을 못 찾는다. 단계를 닫아 끝낸 추출도
    처리 건 상태는 COMPLETED 라 상태만 보지 않는다. 못 찾으면 새 추출을 시작하지 않고 멈춘다(2026-10-23 리허설: 검토 없는 새 추출이 돌았다).
    document_id(지금 적재된 문서, loaded_document)가 있으면 그 문서의 판본만 본다 — 같은 파일을 「새 문서」로 다시 올린 다른 문서의
    추출을 고르면 적재가 지금 문서가 소유한 절차를 덮어쓰지 못해 409 로 거절된다(audit2 I4)."""
    sources, offset = [], 0
    while offset is not None:
        st, page = call("GET", f"/api/kg/manuals/sources?limit=100&offset={offset}")
        if st != 200:
            raise SystemExit(f"{key} 원문 목록 읽기 실패 {st}: {page}")
        sources += [s for s in page["items"] if s.get("filename") == fname and s.get("sha256") == sha
                    and (document_id is None or _source_document(s) == document_id)]
        offset = page.get("next_offset")
    for s in sources:                                        # 최근 판본부터(목록이 created_at 내림차순)
        st, runs = call("GET", f"/api/kg/manuals/sources/{s['source_id']}/extractions")
        if st != 200:
            raise SystemExit(f"{key} 추출 이력 읽기 실패 {st}: {runs}")
        for run in runs.get("items") or []:
            st, res = call("GET", f"/api/kg/manuals/sources/{s['source_id']}/extractions/{run['proc_inst_id']}")
            if st == 200 and res.get("preview"):
                return s["source_id"], {"instance": run["proc_inst_id"], "reused": True}
    scope = f"지금 적재된 문서 {document_id}의 " if document_id else ""
    raise SystemExit(f"{key}: --reuse 로 다시 쓸 끝난 추출이 없습니다({scope}같은 내용 {sha[:12]}… 원문 판본 {len(sources)}개 확인). "
                     "새로 추출하려면 --reuse 없이 실행하세요")


def extract(key: str, reuse: bool) -> dict:
    fname = DOCS[key]
    raw = (ROOT / "문서/시스템/참조/수업_문서_원문" / fname).read_bytes()
    loaded = loaded_document(fname)
    st, pv = call("POST", "/api/kg/manuals/preview",
                  {"filename": fname, "data": base64.b64encode(raw).decode(), "document_id": loaded})
    if st != 200:
        raise SystemExit(f"{key} preview failed {st}: {pv}")
    sid = pv["source_id"]
    inst = None
    if reuse:
        sid, inst = finished_extraction(key, fname, sid.rsplit(":", 1)[1], loaded)
    else:
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
    # A conflict changes the meaning of the reviewed body. Report it unchanged;
    # only a new, source-anchored explicit review may remove/reuse knowledge.
    dropped = [change['target'] for change in changes if change['kind'] == 'drop']
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
