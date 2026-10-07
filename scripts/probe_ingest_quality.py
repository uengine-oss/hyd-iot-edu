"""A077 — extraction quality on harder inputs through the real Claude Code extraction task (meeting L253~302).

    .venv314/Scripts/python scripts/probe_ingest_quality.py .evidence/reaudit/a077-ingest-<n> [fixture ...]

Uploads each fixture, starts the real agent extraction (task:extract-manual via the host worker), waits for the
result and records what the agent proposed. The checks below are *expectations written before the run* for the two
shipped fixtures; a failed check is a measured defect of the extraction, not of the probe. Nothing is committed to
the graph here; review/commit is a separate human step.
"""
import base64
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
import urllib.error
import urllib.request

PROCESS = "http://127.0.0.1:8080"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT = [ROOT / "tests/fixtures/manuals/HM-9_oil-degradation-manual.md", ROOT / "tests/fixtures/manuals/two-page-manual.pdf"]


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
    except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as e:
        # A094: the service may restart during a long run (segmented extractions take an hour); polling must survive it
        return 0, {"transient": str(e)[:200]}


def expectations(filename, preview, pages):
    """Return list of (name, ok, detail). Written against the fixture text, before running."""
    secs = {s["ref"]: s for s in preview["sections"]}
    procs = {p["id"]: p for p in preview["procedures"]}
    out = []
    if filename.startswith("HM-9"):
        out.append(("all_four_sections_found", {"HM-9.1", "HM-9.2", "HM-9.3", "HM-9.4"} <= set(secs), sorted(secs)))
        out.append(("numbered_sop_oil_21_with_six_steps", "SOP-OIL-21" in procs and len(procs["SOP-OIL-21"]["steps"]) == 6,
                    {k: len(v["steps"]) for k, v in procs.items()}))
        prose = [p for p in procs.values() if p["section"] == "HM-9.2"]
        out.append(("unnumbered_prose_procedure_in_9_2_proposed", bool(prose) and len(prose[0]["steps"]) >= 4,
                    [(p["id"], len(p["steps"])) for p in prose]))
        out.append(("retired_sop_oil_20_not_proposed", "SOP-OIL-20" not in procs and not any(p["section"] == "HM-9.4" for p in procs.values()), sorted(procs)))
        step_text = " ".join(s["text"] for p in procs.values() for s in p["steps"])
        out.append(("prohibitions_kept_in_steps", "40 ℃ 이상에서는 배유하지 않는다" in step_text and "다른 점도 등급을 섞지 않는다" in step_text, None))
        out.append(("table_criteria_kept_in_section_excerpt", "0.5 초과" in (secs.get("HM-9.1", {}).get("excerpt") or ""), None))
        text = json.dumps(preview, ensure_ascii=False)
        out.append(("approval_role_surfaced", "정비 관리자" in text, None))
        out.append(("registration_id_warning_for_prose_sop", any("등록" in w or "원문에 없" in w for w in preview["warnings"]), preview["warnings"]))
    elif filename.startswith("HM-FULL"):
        import re
        text_all = "\n".join(pg["text"] for pg in pages)
        want_secs = set(re.findall(r"^## (HM-\d+\.\d+)", text_all, re.M)); want_sops = set(re.findall(r"^### (SOP-HM\d+-\d+)", text_all, re.M))
        out.append(("every_numbered_section_found", want_secs <= set(secs), {"missing": sorted(want_secs - set(secs))[:20], "found": len(secs), "wanted": len(want_secs)}))
        out.append(("every_sop_found_with_its_id", want_sops <= set(procs), {"missing": sorted(want_sops - set(procs))[:20], "found": len(procs), "wanted": len(want_sops)}))
        steps_wanted = {m.group(1): len(re.findall(r"^\d+\. ", m.group(2), re.M)) for m in re.finditer(r"^### (SOP-HM\d+-\d+)[^\n]*\n((?:(?!^#).*\n?)*)", text_all, re.M)}
        bad = {k: (len(procs[k]["steps"]), n) for k, n in steps_wanted.items() if k in procs and len(procs[k]["steps"]) != n}
        out.append(("step_counts_match_the_numbered_lists", not bad, dict(list(bad.items())[:15])))
        out.append(("retired_sop_old_01_not_proposed", "SOP-OLD-01" not in procs and not any("OLD" in k for k in procs), sorted(k for k in procs if "OLD" in k)))
        # A092: content checks are the quality measure; the cited-character ratio is kept as information only
        # (prose-heavy manuals cite 20 % and lose nothing — a092-ingest-large-1)
        conds = re.findall(r"^### (SOP-HM\d+-\d+)[^\n]*\n([^\n]+)\n", text_all, re.M)
        whole = json.dumps(preview, ensure_ascii=False)
        out.append(("every_sop_precondition_preserved", all(c[:20] in whole for _, c in conds), {"sops": len(conds), "lost": [s for s, c in conds if c[:20] not in whole][:10]}))
        avl_src = text_all.count("승인 공급사(AVL)"); avl_kept = sum(1 for p in procs.values() for s in p["steps"] if "AVL" in s["text"])
        out.append(("avl_prohibition_kept_in_steps", avl_kept >= avl_src, {"source": avl_src, "kept": avl_kept}))
        out.append(("every_section_excerpt_carries_its_criteria", all("기준" in s["excerpt"] or "인터록" in s["excerpt"] for s in secs.values()), None))
        out.append(("coverage_ratio_recorded", True, preview.get("coverage")))
    elif filename.startswith("HM-REV"):
        # A094 round trip: the document was generated from the live ontology (scripts/reverse_extract_manual.py), so the
        # extraction should give back exactly the sections and SOPs the ontology holds (ids, step counts, order).
        import re
        text_all = "\n".join(pg["text"] for pg in pages)
        want_secs = set(re.findall(r"^## (HM-\d+\.\d+) ", text_all, re.M))
        sops = {m.group(1): len(re.findall(r"^\d+\. ", m.group(2), re.M)) for m in re.finditer(r"^### (SOP-[A-Z0-9-]+) [^\n]*\n((?:(?!^#).*\n?)*)", text_all, re.M)}
        out.append(("all_14_manual_sections_found", want_secs <= set(secs), {"missing": sorted(want_secs - set(secs)), "found": len(secs)}))
        out.append(("all_16_sops_found_with_their_ids", set(sops) <= set(procs), {"missing": sorted(set(sops) - set(procs)), "found": len(procs)}))
        bad = {k: (len(procs[k]["steps"]), n) for k, n in sops.items() if k in procs and len(procs[k]["steps"]) != n}
        out.append(("step_counts_match_the_ontology", not bad, bad))
        first = {k: procs[k]["steps"][0]["text"] for k in sops if k in procs}
        out.append(("first_steps_quote_the_ontology_text", all(re.search(r"^### " + re.escape(k) + r"[^\n]*\n[^\n]*\n1\. " + re.escape(v.rstrip(".")), text_all, re.M) for k, v in first.items()), None))
        out.append(("no_sop_invented_from_rule_or_evidence_tables", not any(p["section"].startswith(("dt:", "evd:", "in:", "fm:")) or "결정표" in p["name"] for p in procs.values()), [p["id"] for p in procs.values() if "결정표" in p["name"]]))
        out.append(("retired_raise_pressure_sop_flagged_or_absent", "SOP-PMP-03" not in procs or any("구 절차" in w or "폐지" in w or "SOP-PMP-03" in w for w in preview["warnings"]), None))
        out.append(("coverage_ratio_recorded", True, preview.get("coverage")))
    elif filename.startswith("EHU40"):
        # A094: a real manufacturer manual (Daikin ECORICH EHU40 operation manual PDF, 80 pages, English). Written from
        # the extracted text before the run: chapter 13 holds the maintenance procedures with "1) 2) 3)" step lists.
        import re
        body = "\n".join(pg["text"] for pg in pages[5:])
        heads = sorted(set(re.findall(r"^(1[1-3]\.\d+(?:\.\d+)?) ", body, re.M)))
        text = json.dumps(preview, ensure_ascii=False)
        hit = [h for h in heads if any(h in s["ref"] or (s["title"] or "").startswith(h) for s in preview["sections"])]
        # run 1 (a094-ingest-real-ehu40): panel/parameter description sections (11.x, 12.2~12.5) were left out on purpose with a
        # page review saying "설명 표로 절차 없음" — that is the contract (sections carry procedures/criteria), so the measured
        # expectation is: every chapter-13 heading is a section, and 11~12 headings are reported, not required.
        heads13 = [h for h in heads if h.startswith("13.")]
        out.append(("every_chapter_13_heading_becomes_a_section", all(h in hit for h in heads13), {"missing": [h for h in heads13 if h not in hit], "found_11_12": len([h for h in hit if not h.startswith("13.")]), "headings_11_12": len(heads) - len(heads13)}))
        hangul = [p["id"] for p in procs.values() if any(re.search("[가-힣]", s["text"]) for s in p["steps"])]
        out.append(("steps_keep_the_source_language_english", not hangul, hangul[:10]))          # run 1: segments 2·3 translated 110 steps into Korean
        out.append(("no_correction_round_was_needed", not (preview.get("extraction") or {}).get("segments") or all(s.get("generation", 0) == 0 for s in preview["extraction"]["segments"]) and not any(preview.get("warnings_corrections") or []), None))
        maint = [p for p in procs.values() if any(k in (p["name"] + " " + p["section"]) for k in ("13.5", "13.6", "13.7", "13.8", "13.9", "13.10", "Cooler", "Strainer", "Breather", "Safety Valve", "Throttle"))]
        out.append(("maintenance_instructions_13_5_to_13_10_become_procedures", len(maint) >= 5, [(p["id"], p["section"], len(p["steps"])) for p in maint][:12]))
        cooler = [p for p in procs.values() if "13.5.1" in p["section"] or "Removing the oil cooler" in p["name"] or "13.5" in p["section"] and "Remov" in p["name"]]
        out.append(("removing_the_oil_cooler_has_its_three_numbered_steps", any(len(p["steps"]) >= 3 for p in cooler), [(p["id"], len(p["steps"])) for p in cooler]))
        toc = {p["anchor"]["page"] for p in procs.values()} & {3, 4}
        out.append(("no_procedure_anchored_in_the_table_of_contents", not toc, sorted(toc)))
        startup = [p for p in procs.values() if "Chapter 5" in p["section"] or "STARTING UP" in (p["name"] + p["section"]).upper()]
        out.append(("chapter_5_startup_overview_is_not_a_fabricated_sop_or_is_flagged", not startup or any("5" in w and ("개요" in w or "참조" in w or "overview" in w.lower()) for w in preview["warnings"]), [p["id"] for p in startup]))
        out.append(("safety_shutoff_precondition_preserved_somewhere", "shut off the source power" in text.lower() or "shut off the source power supply" in text.lower(), None))
        out.append(("registration_ids_flagged_in_warnings", any("등록" in w or "원문에 없" in w for w in preview["warnings"]), len(preview["warnings"])))
        out.append(("coverage_ratio_recorded", True, preview.get("coverage")))
    elif filename.startswith("two-page"):
        p1, p2 = pages[0]["text"], pages[1]["text"]
        out.append(("two_sections_with_distinct_refs", len(secs) >= 2 and len({s["ref"] for s in preview["sections"]}) == len(preview["sections"]), sorted(secs)))
        fan = [p for p in procs.values() if p["anchor"]["page"] == 1]
        pump = [p for p in procs.values() if p["anchor"]["page"] == 2]
        out.append(("one_procedure_per_page", len(fan) >= 1 and len(pump) >= 1, {k: v["anchor"]["page"] for k, v in procs.items()}))
        out.append(("steps_anchored_on_their_own_page", all(s["anchor"]["page"] == p["anchor"]["page"] for p in procs.values() for s in p["steps"]), None))
        out.append(("pump_steps_quote_page_two_text", all(s["anchor"]["quote"] in p2 for p in pump for s in p["steps"]) if pump else False, None))
        out.append(("page_reviews_cover_both_pages", {r["page"] for r in preview["page_reviews"]} == {1, 2}, None))
    return out


DEADLINE_S = int(os.environ.get("PROBE_DEADLINE_S", "7200"))      # A094: segmented runs of a real manual take ~1 h on one worker


def main():
    out = Path(sys.argv[1])
    collect = sys.argv[2:5] if len(sys.argv) > 2 and sys.argv[2] == "--collect" else None   # --collect <source_id> <instance>: attach to a run already started
    out.mkdir(parents=True, exist_ok=collect is not None)
    files = [Path(a) for a in sys.argv[2:]] or DEFAULT
    report = {"started": datetime.now(timezone.utc).isoformat(), "fixtures": {}, "scope": __doc__}
    def save(n, v): (out / (n + ".json")).write_text(json.dumps(v, ensure_ascii=False, indent=2, default=str), encoding="utf8")
    if collect:
        _, sid, pid = collect; root = "/api/kg/manuals/sources/" + sid
        s, source = http(root); assert s == 200, (s, source)
        files = [Path(source["filename"])]
    for f in files:
        tag = f.name; t0 = time.monotonic()
        if collect:
            print(tag, "collecting", pid, flush=True)
        else:
            s, up = http("/api/kg/manuals/preview", {"filename": f.name, "data": base64.b64encode(f.read_bytes()).decode()})
            assert s == 200, (s, up)
            sid = up["source_id"]; root = "/api/kg/manuals/sources/" + sid
            s, source = http(root); assert s == 200
            save(tag + ".source", source); save(tag + ".structured-preview", up)
            rid = str(uuid.uuid4())
            s, inst = http(root + "/extractions", {"request_id": rid}); assert s == 200, (s, inst)
            pid = inst["instance"]; print(tag, "extraction", pid, "segments", inst.get("segments"), flush=True)
        end = time.monotonic() + DEADLINE_S
        last = None
        while time.monotonic() < end:
            s, res = http(root + "/extractions/" + pid)
            if s == 200 and res["status"] in ("DONE", "FAILED", "CANCELLED", "PENDING") and (res["preview"] or res["status"] != "DONE"):
                break
            if s == 200 and res.get("progress") != last:
                last = res.get("progress"); print(tag, "progress", last, datetime.now().strftime("%H:%M:%S"), flush=True)
            time.sleep(5)
        else:
            res = {"status": "TIMEOUT"}
        elapsed = round(time.monotonic() - t0, 1)
        save(tag + ".extraction", res)
        entry = {"source_id": sid, "instance": pid, "status": res.get("status"), "elapsed_s": elapsed, "log": res.get("log"),
                 "corrections": res.get("corrections"), "coverage": (res.get("preview") or {}).get("coverage"), "conflicts": (res.get("preview") or {}).get("conflicts"), "checks": []}
        if res.get("preview"):
            pv = res["preview"]
            entry["summary"] = {"sections": [x["ref"] for x in pv["sections"]], "procedures": {p["id"]: len(p["steps"]) for p in pv["procedures"]},
                                "warnings": pv["warnings"], "page_reviews": pv["page_reviews"]}
            for name, ok, detail in expectations(tag, pv, source["pages"]):
                entry["checks"].append({"name": name, "passed": bool(ok), "detail": detail})
                print(("PASS " if ok else "FAIL ") + tag + " " + name + ("" if detail is None else "  " + json.dumps(detail, ensure_ascii=False, default=str)[:200]), flush=True)
        else:
            print("NO PREVIEW", tag, res.get("status"), str(res.get("log"))[:300], flush=True)
        report["fixtures"][tag] = entry; save("result", report)
    report["finished"] = datetime.now(timezone.utc).isoformat(); save("result", report)
    total = sum(len(e["checks"]) for e in report["fixtures"].values()); passed = sum(c["passed"] for e in report["fixtures"].values() for c in e["checks"])
    print(f"checks passed {passed}/{total}", flush=True)


if __name__ == "__main__":
    main()
