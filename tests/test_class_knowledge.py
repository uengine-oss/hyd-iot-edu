"""수업용 기본 지식(scripts/class_knowledge.py · it/neo4j/class-knowledge/): 처음 한 번만 넣고, 원문이 바뀌면 멈추고, 인용 판본 id 를 이 PC 것으로 바꾼다.
2026-10-25 결정(문서/교재/5_결정_기록.md): 구조판 시작 상태에서 4회차 인제스천 전 판단 · What-if 실습의 후보가 0개였다."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _mod():
    spec = importlib.util.spec_from_file_location("class_knowledge", ROOT / "scripts" / "class_knowledge.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["class_knowledge"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("doc", ["HM-8", "PM-02", "PR-07"])
def test_each_seed_matches_its_original_and_is_a_reviewed_full_body(doc):
    seed = json.loads((ROOT / "it/neo4j/class-knowledge" / f"{doc}.json").read_text(encoding="utf-8"))
    raw = (ROOT / "문서/시스템/참조/수업_문서_원문" / seed["filename"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == seed["sha256"]
    assert seed["review_method"] == "user-delegated-ai-review" and seed["review"]            # 누가 어떻게 검토했는지 남긴다
    text = raw.decode("utf-8")
    anchors = []
    def walk(v):
        if isinstance(v, dict):
            if {"page", "start", "end", "quote"} <= v.keys():
                anchors.append(v)
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
    walk([seed["sections"], seed["procedures"], seed["knowledge"]])
    assert anchors and all(text[a["start"]:a["end"]] == a["quote"] for a in anchors)          # 모든 인용이 원문 그 자리 글자
    assert {p["id"] for p in seed["procedures"]} == set(seed["links"]) | {p["id"] for p in seed["procedures"] if p["id"] not in seed["links"]}


def test_candidate_rules_cover_the_three_class_scenarios():
    rules = {doc: json.loads((ROOT / "it/neo4j/class-knowledge" / f"{doc}.json").read_text(encoding="utf-8"))["knowledge"]["rules"]
             for doc in ("HM-8", "PM-02", "PR-07")}
    def selects(doc, pattern):
        return any(r["table"] == "dt:action-candidates" and r["effect"] == "SELECT" and
                   any(t["input"] == "in:pattern" and t["value"] == pattern for t in r["tests"]) for r in rules[doc])
    assert selects("HM-8", "COOLER_DEGRADATION") and selects("PM-02", "PM_DUE") and selects("PR-07", "SPARE_BELOW_MIN")


def test_ensure_skips_loaded_documents_and_commits_the_rest_with_rebased_anchors(monkeypatch, capsys):
    mod = _mod()
    calls = []
    def fake(method, path, body=None, timeout=120):
        calls.append((method, path, body))
        if path == "/api/kg/manuals":
            return [{"current": True, "filename": "HM-8_cooler-fan-manual.md", "batch": "b-hm8"}]
        if path == "/api/kg/manuals/preview":
            sha = hashlib.sha256((mod.ORIGINALS / body["filename"]).read_bytes()).hexdigest()
            return {"source_id": f"manual:new-doc:{sha}", "document_id": "new-doc", "filename": body["filename"], "batch": "11111111-1111-1111-1111-111111111111"}
        if path == "/api/kg/manuals/commit":
            return {"procedures": len(body["procedures"]), "steps": 1, "batch": body["batch"]}
        raise AssertionError(path)
    monkeypatch.setattr(mod, "call", fake)
    assert mod.main(["x", "ensure"]) == 0
    commits = [b for m, p, b in calls if p == "/api/kg/manuals/commit"]
    assert [b["filename"] for b in commits] == ["PM-02_powerpack-pm-checklist.md", "PR-07_spare-parts-standard.md"]   # HM-8 은 이미 있음
    for b in commits:
        sid = b["source_id"]
        assert json.dumps(b["procedures"]).count(sid) and "manual:" + "new-doc" in sid
        assert all(a["source_id"] == sid for p in b["procedures"] for a in [p["anchor"]] + [s["anchor"] for s in p["steps"]])
    assert "HM-8: 이미 적재됨" in capsys.readouterr().out


def test_ensure_refuses_a_changed_original(monkeypatch, tmp_path):
    mod = _mod()
    (tmp_path / "HM-8_cooler-fan-manual.md").write_text("바뀐 원문", encoding="utf-8")
    monkeypatch.setattr(mod, "ORIGINALS", tmp_path)
    with pytest.raises(SystemExit, match="검토본을 만든 판과 다릅니다"):
        mod.load_seed("HM-8")


def test_unknown_command_is_refused_without_calls(monkeypatch):
    mod = _mod()
    monkeypatch.setattr(mod, "call", lambda *a, **k: (_ for _ in ()).throw(AssertionError("called")))
    assert mod.main(["x"]) == 2 and mod.main(["x", "load"]) == 2


def test_b_and_c_seeds_carry_the_reviewed_policies_their_agents_need():
    """2026-10-25 수업 한 바퀴: 정책이 빠진 검토본으로 B 에이전트는 사람에게 적용 범위를 묻고 멈췄고, C 에이전트는 「검토된 원문 정책이 없습니다」로 보류했다."""
    sys.path.insert(0, str(ROOT / "common"))
    from hydcommon import maintenance_policy, purchase_comparison
    pm = json.loads((ROOT / "it/neo4j/class-knowledge/PM-02.json").read_text(encoding="utf-8"))["links"]
    pr = json.loads((ROOT / "it/neo4j/class-knowledge/PR-07.json").read_text(encoding="utf-8"))["links"]
    scopes = {sop: maintenance_policy.policy(pm[sop]["maintenance_policy"])["scope"] for sop in ("SOP-PM-11", "SOP-PM-12", "SOP-PM-13", "SOP-PM-14")}
    assert scopes == {"SOP-PM-11": "single", "SOP-PM-12": "single", "SOP-PM-13": "single", "SOP-PM-14": "bundle"}
    for sop in ("SOP-PUR-11", "SOP-PUR-12", "SOP-PUR-13"):
        assert purchase_comparison.policy(pr[sop]["purchase_comparison_policy"])["loss_per_failure"] == 250


def test_pm02_seed_has_the_pump_cause_evidence_the_manual_defines():
    """2026-10-25 수업 한 바퀴: 증거 0개 검토본으로 펌프 내부 누설 진단이 [다시 평가] 뒤에도 보류했다(원문 PM-2.10 의 PS1 · FS1 기준)."""
    ev = {e["cause"]: e for e in json.loads((ROOT / "it/neo4j/class-knowledge/PM-02.json").read_text(encoding="utf-8"))["knowledge"]["evidence"]}
    assert (ev["cause:pump-shaft-seal-wear"]["tag"], ev["cause:pump-shaft-seal-wear"]["threshold"]) == ("PS1", 165)
    assert (ev["cause:hydraulic-oil-contamination"]["tag"], ev["cause:hydraulic-oil-contamination"]["threshold"]) == ("FS1", 8.0)
