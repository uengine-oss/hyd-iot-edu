"""L9 knowledge administration (pure): manual -> SOP ingestion parser and skill edit validation.

Humans maintain the knowledge map (ontology v2) through the process service (the agent stays read-only):
  - upload a maintenance manual (Markdown / text / PDF text) -> ManualSection nodes + one Skill (= SOP) per procedure with
    its Step nodes, matched to the failure mode a person picks in the preview,
  - edit skills (name, description, approver) or add a new SOP skill matched to a failure mode.

Manual format the parser understands (PDF text works too, headings do not need '#'):
    ## HM-8.1 쿨러 팬 벨트 점검          <- section: ref + title, following plain lines = excerpt
    ### SOP-FAN-01 쿨러 팬 점검 절차      <- optional explicit procedure id + name
    1. 설비를 정지한다.                  <- numbered lines = steps (1. or 1) ), linked to the enclosing section
Numbered lines without an explicit SOP heading become procedure 'SOP-<section ref>' named after the section.
"""
from __future__ import annotations

import re

SECTION_RE = re.compile(r"^\s*#{0,4}\s*([A-Z]{1,6}-\d+(?:\.\d+)*)\s+(.+?)\s*$")
SOP_RE = re.compile(r"^\s*#{0,4}\s*(SOP-[A-Z0-9]+(?:-[A-Z0-9]+)*)\s+(.+?)\s*$")
STEP_RE = re.compile(r"^\s*(\d{1,2})[.)]\s+(.+?)\s*$")
TITLE_RE = re.compile(r"^\s*#\s+(.+?)\s*$")


def _tokens(s: str) -> set[str]:
    return {t for t in re.split(r"[\s·,()/\-]+", s or "") if t and t not in {"절차", "작업지시", "매뉴얼", "및"}}   # one-syllable words (팬, 핀) matter


def parse_manual(text: str, filename: str, actions: list[dict] | None = None) -> dict:
    sections: list[dict] = []
    procs: dict[str, dict] = {}
    order: list[str] = []
    title = None
    cur_sec = None
    cur_proc = None
    for raw in (text or "").splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        m = SOP_RE.match(line)
        if m:
            cur_proc = procs.setdefault(m.group(1), {"id": m.group(1), "name": m.group(2), "section": cur_sec["ref"] if cur_sec else None, "steps": []})
            if m.group(1) not in order:
                order.append(m.group(1))
            continue
        m = SECTION_RE.match(line)
        if m and not STEP_RE.match(line):
            cur_sec = {"ref": m.group(1), "title": m.group(2), "excerpt": ""}
            sections.append(cur_sec)
            cur_proc = None
            continue
        m = STEP_RE.match(line)
        if m:
            if cur_proc is None:
                pid = f"SOP-{cur_sec['ref']}" if cur_sec else "SOP-UPLOAD"
                cur_proc = procs.setdefault(pid, {"id": pid, "name": cur_sec["title"] if cur_sec else filename, "section": cur_sec["ref"] if cur_sec else None, "steps": []})
                if pid not in order:
                    order.append(pid)
            cur_proc["steps"].append({"order": len(cur_proc["steps"]) + 1, "text": m.group(2), "manual": cur_sec["ref"] if cur_sec else None})
            continue
        m = TITLE_RE.match(line)
        if m and not sections:
            title = m.group(1)
            continue
        if cur_sec is not None and cur_proc is None and len(cur_sec["excerpt"]) < 200:
            cur_sec["excerpt"] = (cur_sec["excerpt"] + " " + line.strip().lstrip("#").strip()).strip()[:200]
    procedures = [procs[i] for i in order if procs[i]["steps"]]
    for p in procedures:
        p["stepCount"] = len(p["steps"])
        if actions:
            name_t = _tokens(p["name"])
            sec_t = _tokens(next((s["title"] for s in sections if s["ref"] == p["section"]), ""))
            # a procedure's own name counts double; a manual procedure is maintenance work, so ties go to work-order actions
            score = lambda a: (2 * len(name_t & _tokens(a["name"])) + len(sec_t & _tokens(a["name"])), a.get("kind") == "work_order")
            best = max(actions, key=score)
            p["suggestedAction"] = best["id"] if score(best)[0] else None
    warnings = []
    if not sections:
        warnings.append("매뉴얼 절 제목(예: 'HM-8.1 쿨러 팬 벨트 점검')을 찾지 못했다.")
    if not procedures:
        warnings.append("번호 매긴 절차 단계(예: '1. 설비를 정지한다.')를 찾지 못했다.")
    return {"filename": filename, "title": title, "sections": sections, "procedures": procedures, "warnings": warnings}


SOP_ID_RE = re.compile(r"^SOP-[A-Z0-9]+(?:-[A-Z0-9]+)*$")


def validate_skill(body: dict, create: bool = False) -> dict:
    """Skill edit (name, description, approver). A new skill (create=True) is an SOP matched to a failure mode
    (ontology v2: Skill.sopId, Skill -HAS_STEP-> Step ≥ 1, FailureMode -MITIGATED_BY|REMEDIED_BY-> Skill ≥ 1)."""
    name = str(body.get("name") or "").strip()
    if not name:
        raise ValueError("스킬 이름이 비어 있다")
    if len(name) > 80:
        raise ValueError("스킬 이름은 80자 이내")
    out = {"name": name, "description": str(body.get("description") or "").strip()[:500]}
    if body.get("approver"):
        out["approver"] = str(body["approver"])
    if not create:
        # A075: a reviewer may (re)link an existing skill to a failure mode; the candidate rules of that failure mode then
        # offer the skill (meeting L253~302: ingested knowledge must reach the runtime judgment).
        if body.get("failureMode"):
            relation = body.get("relation") or "REMEDIED_BY"
            if relation not in ("MITIGATED_BY", "REMEDIED_BY"):
                raise ValueError("고장 유형과의 관계는 MITIGATED_BY(즉시 완화) 또는 REMEDIED_BY(근본 조치)")
            out.update(failureMode=str(body["failureMode"]).strip(), relation=relation)
        return out
    sop = str(body.get("sopId") or "").strip().upper()
    if not SOP_ID_RE.match(sop):
        raise ValueError("SOP 번호는 'SOP-FAN-05'처럼 SOP-로 시작해야 한다")
    steps = body.get("steps") or []
    if isinstance(steps, str):
        steps = steps.splitlines()
    steps = [str(s).strip() for s in steps if str(s).strip()]
    if not steps:
        raise ValueError("SOP 단계가 하나 이상 있어야 한다 (한 줄에 한 단계)")
    if not str(body.get("failureMode") or "").strip():
        raise ValueError("조치 방법은 고장 유형에 매칭되어야 한다 (failureMode)")
    kind = body.get("kind") or "work_order"
    if kind not in ("control", "work_order"):
        raise ValueError("스킬 종류는 control 또는 work_order")
    relation = body.get("relation") or "REMEDIED_BY"
    if relation not in ("MITIGATED_BY", "REMEDIED_BY"):
        raise ValueError("고장 유형과의 관계는 MITIGATED_BY(즉시 완화) 또는 REMEDIED_BY(근본 조치)")
    out.update(sopId=sop, steps=steps[:30], failureMode=str(body["failureMode"]).strip(), kind=kind, relation=relation)
    return out


def skill_id(sop_id: str) -> str:
    """One skill per SOP: the id follows the SOP number (skill:sop-fan-05)."""
    return "skill:" + re.sub(r"[^a-z0-9-]+", "-", sop_id.lower()).strip("-")
