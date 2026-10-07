"""The A9 SQL-rule judge (scripts/judge_sql_rules_from_traces.py) is checked on hand-made traces that break each rule,
so a PASS on the real traces means the rules were followed, not that the judge is blind."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("judge_sql_rules", ROOT / "scripts" / "judge_sql_rules_from_traces.py")
judge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(judge)


def _start(tool, tid, **inp):
    return {"kind": "tool_start", "tool": tool, "tool_input": inp, "tool_use_id": tid, "is_error": False, "text": ""}


def _end(tool, tid, ok=True, text=None):
    body = text if text is not None else json.dumps({"result": "ok" if ok else "error", "document": {}} if ok else
                                                     {"result": "error", "error_kind": "INVALID", "message": "column x does not exist"})
    return {"kind": "tool_end", "tool": tool, "tool_input": None, "tool_use_id": tid, "is_error": False, "text": body}


Q, CAT = "mcp__enterprise__query", "mcp__enterprise__describe_catalog"


def test_conforming_run_passes_every_rule():
    events = [_start(CAT, "a"), _end(CAT, "a"),
              _start(Q, "b", sql="select order_id from ent.production_orders where asset = 'HYD-01'"), _end(Q, "b")]
    v = judge.judge_events(events)
    assert v["applicable"] and set(v["rules"].values()) == {"PASS"} and v["sql_calls"] == 1 and v["repairs"] == 0


def test_no_sql_run_is_not_applicable():
    v = judge.judge_events([_start("mcp__hyd-dmn__dmn_rules", "a"), _end("mcp__hyd-dmn__dmn_rules", "a")])
    assert not v["applicable"] and set(v["rules"].values()) == {"N/A"}


def test_schema_after_or_without_sql_fails_r1():
    late = [_start(Q, "b", sql="select 1"), _end(Q, "b"), _start(CAT, "a"), _end(CAT, "a")]
    assert judge.judge_events(late)["rules"]["R1_schema_first"] == "FAIL"
    assert judge.judge_events([_start(Q, "b", sql="select 1"), _end(Q, "b")])["rules"]["R1_schema_first"] == "FAIL"
    # hyd-dmn's timeseries_schema counts as the schema step for timeseries_query
    ts = [_start("mcp__hyd-dmn__timeseries_schema", "s"), _end("mcp__hyd-dmn__timeseries_schema", "s"),
          _start("mcp__hyd-dmn__timeseries_query", "q", sql="select time, value from tag_1s limit 5"), _end("mcp__hyd-dmn__timeseries_query", "q")]
    assert judge.judge_events(ts)["rules"]["R1_schema_first"] == "PASS"


def test_two_statements_or_non_select_fail_r2():
    for sql in ["select 1; select 2", "delete from ent.assets", "explain select 1", ""]:
        v = judge.judge_events([_start(CAT, "a"), _end(CAT, "a"), _start(Q, "b", sql=sql), _end(Q, "b")])
        assert v["rules"]["R2_single_select"] == "FAIL", sql
    assert judge.judge_sql_text("with x as (select 1) select * from x")["single_select"]


def test_comments_and_trailing_semicolon_fail_r3_but_quoted_values_do_not():
    for sql in ["-- 납기\nselect 1", "select 1 /* c */", "select 1;"]:
        assert judge.judge_events([_start(CAT, "a"), _end(CAT, "a"), _start(Q, "b", sql=sql), _end(Q, "b")])["rules"]["R3_no_comment_semicolon"] == "FAIL", sql
    ok = judge.judge_sql_text("select 'a -- b; c' as note from ent.assets")
    assert ok["no_comment"] and ok["no_semicolon"] and ok["single_select"]


def test_more_than_two_repairs_after_errors_fail_r4():
    def run(n_repairs):
        ev = [_start(CAT, "a"), _end(CAT, "a"), _start(Q, "q0", sql="select bad"), _end(Q, "q0", ok=False)]
        for i in range(n_repairs):
            ev += [_start(Q, f"q{i + 1}", sql="select bad"), _end(Q, f"q{i + 1}", ok=False)]
        return judge.judge_events(ev)
    assert run(2)["rules"]["R4_fixes_le_2"] == "PASS" and run(2)["repairs"] == 2
    assert run(3)["rules"]["R4_fixes_le_2"] == "FAIL" and run(3)["repairs"] == 3 and run(3)["failed_calls"] == 4
    # a re-query after a *successful* call is not a repair
    ev = [_start(CAT, "a"), _end(CAT, "a")] + [x for i in range(5) for x in (_start(Q, f"q{i}", sql="select 1"), _end(Q, f"q{i}"))]
    assert judge.judge_events(ev)["repairs"] == 0
    # is_error on the tool_end also counts as a failed call
    ev = [_start(CAT, "a"), _end(CAT, "a"), _start(Q, "q0", sql="select 1"), dict(_end(Q, "q0", text="timeout"), is_error=True),
          _start(Q, "q1", sql="select 1"), _end(Q, "q1")]
    assert judge.judge_events(ev)["repairs"] == 1


def test_directory_summary_counts_runs_and_renders(tmp_path):
    good = [_start(CAT, "a"), _end(CAT, "a"), _start(Q, "b", sql="select 1"), _end(Q, "b")]
    bad = [_start(Q, "b", sql="select 1;"), _end(Q, "b")]
    d = tmp_path / "runs"; d.mkdir()
    (d / "r1-run-x.events.jsonl").write_text("\n".join(json.dumps(e) for e in good), encoding="utf-8")
    (d / "r2-run-y.events.jsonl").write_text("\n".join(json.dumps(e) for e in bad), encoding="utf-8")
    report = judge.judge_dirs([d])
    s = report["summary"]
    assert s["runs"] == 2 and s["applicable"] == 2 and s["R1_schema_first"] == "1/2" and s["R3_no_comment_semicolon"] == "1/2" and s["all_pass"] is False
    text = judge.render(report)
    assert "| runs/r1 |" in text and "all_pass=False" in text
