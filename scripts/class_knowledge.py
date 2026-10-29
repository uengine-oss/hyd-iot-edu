"""수업용 기본 지식: 검토를 마친 수업 문서 셋(HM-8 · PM-02 · PR-07)의 지식을 포털 지식 관리와 같은 API로 처음 한 번 넣는다.

    python scripts/class_knowledge.py ensure        # 시작 스크립트가 부른다. 이미 적재된 문서는 건너뛴다(두 번째 실행은 아무것도 바꾸지 않음)
    python scripts/class_knowledge.py status        # 문서마다 적재 여부만 본다

왜(사용자 결정 2026-10-25): 학생 PC의 시작 지식(구조판)에는 고장 · 원인 · 조치가 없어 4회차 인제스천보다 앞선
판단 · What-if 실습이 후보 0개였다. 그래서 검토본을 처음부터 넣고, 4회차 인제스천은 같은 문서를 다시 올려 과정을 배우는 실습(문서 개정)으로 둔다.
AI를 부르지 않는다 — 모든 PC가 같은 지식으로 시작한다(it/neo4j/class-knowledge/<문서>.json, 검토 기록 review 포함).
원문(it/portal/www/samples/)이 검토본을 만든 판과 다르면(sha256) 넣지 않고 멈춘다 — 다른 글에 옛 인용을 붙이지 않는다.
원문 판본 id(source_id)는 PC마다 새로 생긴다. 원문 sha256이 같으면 글자 위치도 같으므로, 검토본 인용(anchor)의 판본 id만 새 것으로 바꿔 넣는다
(서버가 인용 글자 · 위치를 다시 대조한다 — manual_review.validate).
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = os.environ.get("PROCESS_URL", "http://127.0.0.1:8080")
SEEDS = ROOT / "it" / "neo4j" / "class-knowledge"
ORIGINALS = ROOT / "it" / "portal" / "www" / "samples"   # 포털이 학생에게 내주는 수업 문서와 같은 파일
ORDER = ("HM-8", "PM-02", "PR-07")                   # 적재 순서: 쿨러 → 정기 정비 → 구매(뒤 문서가 앞 문서의 고장 유형 · 부품을 쓴다)


def call(method: str, path: str, body=None, timeout: float = 120):
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        try:
            detail = json.loads(detail).get("detail", detail)
        except ValueError:
            pass
        raise SystemExit(f"{method} {path} → {e.code}: {str(detail)[:800]}")


def load_seed(doc: str) -> dict:
    seed = json.loads((SEEDS / f"{doc}.json").read_text(encoding="utf-8"))
    raw = (ORIGINALS / seed["filename"]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != seed["sha256"]:
        raise SystemExit(f"{doc}: 원문 {seed['filename']} 이 검토본을 만든 판과 다릅니다 — it/neo4j/class-knowledge/{doc}.json 을 새 원문으로 다시 검토해야 합니다")
    seed["_raw"] = raw
    return seed


def loaded(seed: dict) -> dict | None:
    """이 파일의 현재 적재분. 학생이 4회차에 개정을 적재했어도 같은 문서이므로 건너뛴다."""
    for row in call("GET", "/api/kg/manuals") or []:
        if row.get("current") and row.get("filename") == seed["filename"]:
            return row
    return None


def rebased(value, source_id: str):
    """검토본 안의 모든 인용(anchor)의 판본 id 를 이 PC의 원문 판본 id 로."""
    if isinstance(value, dict):
        out = {k: rebased(v, source_id) for k, v in value.items()}
        if "source_id" in out and {"page", "start", "end", "quote"} <= out.keys():
            out["source_id"] = source_id
        return out
    if isinstance(value, list):
        return [rebased(v, source_id) for v in value]
    return value


def commit(seed: dict) -> dict:
    preview = call("POST", "/api/kg/manuals/preview", {"filename": seed["filename"], "data": base64.b64encode(seed["_raw"]).decode()})
    if not preview["source_id"].endswith(":" + seed["sha256"]):
        raise SystemExit(f"{seed['doc']}: 올린 원문의 sha256 이 검토본과 다릅니다({preview['source_id']})")
    sid = preview["source_id"]
    body = {"source_id": sid, "document_id": preview["document_id"], "filename": preview["filename"],
            "batch": preview["batch"], "previous_batch": preview.get("previous_batch"),
            "sections": rebased(seed["sections"], sid), "procedures": rebased(seed["procedures"], sid), "links": rebased(seed["links"], sid),
            "knowledge": rebased(seed["knowledge"], sid), "by": seed["by"], "review_method": seed["review_method"], "reviewed": True}
    return call("POST", "/api/kg/manuals/commit", body, timeout=300)


def main(argv: list[str]) -> int:
    if argv[1:] not in (["ensure"], ["status"]):
        print("사용: class_knowledge.py ensure | status", file=sys.stderr)
        return 2
    for doc in ORDER:
        seed = load_seed(doc)
        row = loaded(seed)
        if row:
            print(f"{doc}: 이미 적재됨 — 건너뜀 (배치 {row.get('batch')})")
            continue
        if argv[1] == "status":
            print(f"{doc}: 아직 적재 안 됨")
            continue
        out = commit(seed)
        print(f"{doc}: 수업용 기본 지식 적재 — 절차 {out.get('procedures')} · 단계 {out.get('steps')} (배치 {out.get('batch')})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
