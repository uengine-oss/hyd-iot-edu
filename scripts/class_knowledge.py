"""수업용 기본 지식: 강사 서명 추출 묶음의 HM-8 · PM-02 · PR-07 검토본을 포털 지식 관리와 같은 API로 넣는다 — 시작 7단계가 부른다.

    python scripts/class_knowledge.py ensure        # 이 PC의 process(포트 표 .hyd-runtime/ports.json 의 8080 자리)

왜(사용자 결정 2026-10-25): 학생 PC의 시작 지식(구조판)에는 고장 · 원인 · 조치가 없어 4회차 인제스천보다 앞선 판단 · What-if 실습이
후보 0개였다. 그래서 검토본을 처음부터 넣고, 4회차 인제스천은 같은 문서를 다시 올려 과정을 배우는 실습(문서 개정)으로 둔다.

정본은 하나다(결정 2026-10-30): 4회차 재적재가 AI 없이 내는 강사 서명 묶음 it/process/procsvc/course_extractions.json. 여기서도 그
묶음의 제안(절 · 절차 · 지식)과 절차마다 검토한 연결(제안의 link)을 그대로 넣는다 — 4회차에 같은 문서를 제안 그대로 검토 완료하면
같은 지식이다. 묶음의 서명은 process 가 켜질 때 확인한다(틀리면 process 가 뜨지 않는다 — 이 스크립트는 표준 라이브러리만 쓴다).
원문(it/portal/www/samples/)이 묶음의 판과 다르면(sha256) 넣지 않고 멈춘다 — 다른 글에 옛 인용을 붙이지 않는다.
원문 판본 id(source_id)는 PC마다 새로 생긴다. 원문 sha256이 같으면 글자 위치도 같으므로 인용의 판본 id만 이 PC의 것으로 바꿔 넣는다
(서버가 인용 글자 · 위치를 다시 대조한다 — manual_review.validate).

이미 적재된 문서: 지금 판의 판 표시(provided_revision — 이 스크립트만 싣는다)가 지금 묶음 판이면 그대로 둔다. 옛 묶음 판 · 지운 시작
사본(옛 it/neo4j/class-knowledge)이 넣은 판이면 개정으로 지금 묶음을 넣는다. 학생이 다시 넣은 판(다른 담당)은 그대로 둔다.
"""
from __future__ import annotations

import base64
import hashlib
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

import prepare_ports   # 같은 scripts 폴더(시작 파일이 이 폴더의 스크립트로 부른다)

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "it" / "process" / "procsvc" / "course_extractions.json"
ORIGINALS = ROOT / "it" / "portal" / "www" / "samples"   # 포털이 학생에게 내주는 수업 문서와 같은 파일
ORDER = ("HM-8", "PM-02", "PR-07")                   # 적재 순서: 쿨러 → 정기 정비 → 구매(뒤 문서가 앞 문서의 고장 유형 · 부품을 쓴다)
#: 문서 등록 이력의 담당자 칸에 보이는 글 — 사람 이름이 아니라 「시작할 때 들어 있는 판」이라는 대상을 말한다. 어느 판인지는 이 글이 아니라
#: 적재 기록의 판 표시(provided_revision = 서명 묶음의 revision)가 가린다.
PROVIDED_BY = "기본 제공"
# 지운 시작 지식 사본(it/neo4j/class-knowledge, 2026-10-25 판)이 넣은 판의 담당 — 그 판은 다음 시작 때 묶음으로 바꿔 넣는다
OLD_SEED_BY = "수업용 기본 지식 검토 — 사용자가 위임한 AI(2026-10-25, 원문 대조)"


class Stop(RuntimeError):
    """넣지 않고 멈추는 까닭(학생 · 강사가 읽을 문장). status = process 가 거절한 HTTP 상태(닿지 못했으면 None)."""

    def __init__(self, text: str, status: int | None = None):
        super().__init__(text)
        self.status = status


def reviewed(bundle: Path = BUNDLE, originals: Path = ORIGINALS, order: tuple = ORDER) -> list[dict]:
    """묶음에서 적재 순서대로 [{doc, filename, sha256, raw, proposal, review_method, by}]. order = 읽을 문서(기본은 시작이 넣는 셋)."""
    payload = json.loads(bundle.read_text(encoding="utf-8"))["payload"]
    out = []
    for doc in order:
        entries = [(sha, e) for sha, e in payload["documents"].items() if e["filename"].split("_")[0] == doc]
        if len(entries) != 1:
            raise Stop(f"{doc}: 강사 서명 묶음({bundle.name})에 이 문서의 검토본이 {len(entries)}개입니다(하나여야 합니다)")
        sha, entry = entries[0]
        raw = (originals / entry["filename"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != sha:
            raise Stop(f"{doc}: 원문 {entry['filename']} 이 강사 서명 묶음의 판과 다릅니다 — 강사가 새 원문으로 묶음을 다시 만들어야 합니다")
        out.append(dict(doc=doc, filename=entry["filename"], sha256=sha, raw=raw, proposal=entry["proposal"],
                        review_method=entry["origin"]["review_method"], by=PROVIDED_BY, revision=payload["revision"]))
    return out


def rebased(value, source_id: str):
    """제안 안의 모든 인용의 판본 id 를 이 PC의 원문 판본 id 로(제공 문서 캐시 manual_approved_cache.start 와 같은 규칙)."""
    if isinstance(value, dict):
        return {k: source_id if k == "source_id" else rebased(v, source_id) for k, v in value.items()}
    if isinstance(value, list):
        return [rebased(v, source_id) for v in value]
    return value


def commit_body(item: dict, preview: dict) -> dict:
    """미리보기(이 PC의 원문 판본 · 새 배치 · 지금 판) + 묶음 제안 → 적재 요청(4회차에 제안 그대로 검토 완료한 것과 같은 내용)."""
    sid = preview["source_id"]
    proposal = rebased(item["proposal"], sid)
    return {"source_id": sid, "document_id": preview["document_id"], "filename": preview["filename"],
            "batch": preview["batch"], "previous_batch": preview.get("previous_batch"),
            "sections": proposal["sections"],
            "procedures": [{k: v for k, v in p.items() if k != "link"} for p in proposal["procedures"]],
            "links": {p["id"]: p["link"] for p in proposal["procedures"] if p.get("link") is not None},
            "knowledge": proposal.get("knowledge"), "by": item["by"], "review_method": item["review_method"],
            # 판 표시는 시작의 적재(검토 방식을 싣는 적재)에만 — 같은 묶음 제안을 포털의 검토처럼 넣는 요청(검토 방식 없음)은 기본 제공 판이 아니다
            **({"provided_revision": item["revision"]} if item.get("review_method") else {}), "reviewed": True}


def decide(item: dict, current: dict | None) -> str:
    """'load'(처음) · 'revise'(옛 기본 제공 판 → 지금 묶음) · 'keep'(지금 묶음 판) · 'student'(학생이 다시 넣은 판 — 건드리지 않음).
    기본 제공 판인가는 적재 기록의 칸으로 가린다: 판 표시(provided_revision)가 지금 묶음 판이면 keep, 판 표시가 다르거나 없는데 검토 방식
    (review_method — 포털의 검토 화면은 보내지 않는다)이 실려 있으면 앞 판의 기본 제공 판이라 revise. 담당자 칸의 글로 가르지 않는다 —
    학생이 담당자 칸에 같은 글을 적으면 기본 제공 판으로 읽혔다. 예외 하나: 지운 시작 사본(2026-10-25 판)은 칸 없이 담당 글만 남겼다."""
    if current is None:
        return "load"
    if current.get("provided_revision") == item["revision"]:
        return "keep"
    if current.get("provided_revision") or current.get("review_method") or str(current.get("by") or "") == OLD_SEED_BY:
        return "revise"
    return "student"


def ensure(call) -> list[str]:
    """call(method, path, body) → 응답 JSON(거절은 Stop). 돌려줌 = 문서마다 한 줄.
    먼저 업무 DB 의 공급사 · 견적을 그래프로 한 번 옮긴다(G3a-25) — 구매 기준(PR-07)의 의미 검사가 그 공급 관계를 읽는다. 그래프에 없는
    부품의 견적이 남으면 적재 전에 그 좌표로 멈춘다."""
    synced = call("POST", "/api/kg/scm-sync", None) or {}
    if synced.get("missing_part"):
        raise Stop("업무 DB 의 견적이 지식 그래프에 없는 부품을 가리킵니다(부품/공급사: " + ", ".join(synced["missing_part"]) +
                   ") — 시작 파일을 다시 실행해 기본 지식(kg-seed)을 넣은 뒤 이어 갑니다")
    lines = []
    for item in reviewed():
        current = next((row for row in call("GET", "/api/kg/manuals", None) or []
                        if row.get("current") and row.get("filename") == item["filename"]), None)
        what = decide(item, current)
        if what == "keep":
            lines.append(f"{item['doc']}: 지금 기본 제공 판이 적재돼 있음 — 그대로 둠 (배치 {current.get('batch')})")
            continue
        if what == "student":
            lines.append(f"{item['doc']}: 이 PC에서 다시 적재한 판(담당 {current.get('by')})이라 그대로 둠 (배치 {current.get('batch')})")
            continue
        upload = {"filename": item["filename"], "data": base64.b64encode(item["raw"]).decode()}
        if what == "revise":
            upload["document_id"] = current["document_id"]       # 같은 문서의 개정(새 문서로 올리면 같은 SOP · 지식 id 가 두 문서에 겹친다)
        preview = call("POST", "/api/kg/manuals/preview", upload)
        if not str(preview.get("source_id", "")).endswith(":" + item["sha256"]):
            raise Stop(f"{item['doc']}: 올린 원문의 sha256 이 묶음과 다릅니다({preview.get('source_id')})")
        try:
            out = call("POST", "/api/kg/manuals/commit", commit_body(item, preview))
        except Stop as exc:
            if what != "revise" or exc.status != 409:
                raise
            # 옛 시작 판 뒤에 이 문서의 지식이 바뀌었다(수강생의 고치기 등) — 그 변경을 덮지 않는다. 시작은 이어 간다(지식은 옛 판)
            lines.append(f"{item['doc']}: [주의] 앞 판의 기본 제공 판을 지금 판으로 바꾸지 못해 앞 판을 그대로 둠 — {exc}. "
                         "포털의 지식 › 문서 등록에서 이 문서를 다시 올려 적재하면 지금 판의 내용이 됩니다")
            continue
        how = "앞 판의 기본 제공 판을 지금 판으로 바꿈" if what == "revise" else "기본 제공 지식 적재"
        lines.append(f"{item['doc']}: {how} — 절차 {out.get('procedures')} · 단계 {out.get('steps')} (배치 {out.get('batch')})")
    return lines


def http_call(api: str):
    def call(method: str, path: str, body=None):
        data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
        req = urllib.request.Request(api + path, data=data, method=method, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            try:
                detail = json.loads(detail).get("detail", detail)
            except (ValueError, AttributeError):
                pass
            raise Stop(f"{method} {path} → {e.code}: {str(detail)[:800]}", e.code) from None
        except (urllib.error.URLError, OSError) as e:
            raise Stop(f"처리 엔진({api})에 닿지 않습니다: {e}") from None
    return call


def main(argv: list[str]) -> int:
    if argv[1:] != ["ensure"]:
        print("사용: class_knowledge.py ensure", file=sys.stderr)
        return 2
    try:
        api = f"http://127.0.0.1:{prepare_ports.saved_port(ROOT, 8080)}"
        for line in ensure(http_call(api)):
            print(line)
    except (Stop, prepare_ports.PrepareError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
