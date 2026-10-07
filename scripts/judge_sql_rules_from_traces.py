"""A144 (sweep item 31): did the worker's agents actually follow the four "SQL을 직접 쓸 때" rules of the standing
instruction (it/agent-worker/worker/workspace.py CONSTITUTION, A115 A9)? Judged from the recorded tool traces of real
runs — no new LLM execution. Input: run directories holding `*.events.jsonl` (cliagents ExecEvent rows as written by
worker/runner._stream).

  python scripts/judge_sql_rules_from_traces.py --out .evidence/a144/a9-sql-rules \
      .evidence/reaudit/reg-a130-worker/rule-questions .evidence/reaudit/reg-a130-worker/business-questions ...

Rules (one verdict per run, each rule PASS/FAIL/N/A):
  R1 schema first   — before the first SQL tool call (enterprise query / hyd-dmn timeseries_query) the same run called a
                      schema tool (enterprise describe_catalog / describe_schema, hyd-dmn timeseries_schema / inputs).
  R2 one SELECT     — every SQL argument is a single SELECT/WITH statement (no second statement).
  R3 no comments/;  — no `--` / `/* */` comment and no trailing semicolon in any SQL argument.
  R4 fixes ≤ 2      — after a SQL tool answered with an error (envelope result=error or is_error), the agent re-ran SQL at
                      most twice in that run (the instruction allows at most two repairs).
N/A: the run issued no SQL tool call at all.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

SQL_TOOLS = {"mcp__enterprise__query": "sql", "mcp__hyd-dmn__timeseries_query": "sql"}
SCHEMA_TOOLS = {"mcp__enterprise__describe_catalog", "mcp__enterprise__describe_schema",
                "mcp__hyd-dmn__timeseries_schema", "mcp__hyd-dmn__inputs"}
COMMENT_RE = re.compile(r"--|/\*")


def _strip_strings(sql: str) -> str:
    """Remove quoted literals so a `--` or `;` inside a value is not mistaken for syntax."""
    return re.sub(r"'(?:[^']|'')*'", "''", sql)


def judge_sql_text(sql: str) -> dict:
    """R2/R3 on one statement: {'single_select': bool, 'no_comment': bool, 'no_semicolon': bool}."""
    body = _strip_strings(sql or "")
    stripped = body.strip()
    head = stripped.split(None, 1)[0].upper() if stripped else ""
    inner = stripped.rstrip(";").strip()
    return {"single_select": head in ("SELECT", "WITH") and ";" not in inner,
            "no_comment": COMMENT_RE.search(body) is None,
            "no_semicolon": not stripped.endswith(";")}


def _tool_end_failed(ev: dict) -> bool:
    if ev.get("is_error"):
        return True
    text = ev.get("text") or ""
    try:
        doc = json.loads(text)
    except (ValueError, TypeError):
        return False
    return isinstance(doc, dict) and doc.get("result") == "error"


def judge_events(events: list[dict]) -> dict:
    """One run's verdict from its ExecEvent rows (dicts with kind/tool/tool_input/text/is_error/tool_use_id)."""
    sql_calls, schema_before_first_sql, saw_sql = [], False, False
    pending: dict[str, dict] = {}
    repairs, last_failed = 0, False
    schema_seen = False
    for ev in events:
        kind, tool = ev.get("kind"), ev.get("tool")
        if kind == "tool_start":
            if tool in SCHEMA_TOOLS:
                schema_seen = True
            if tool in SQL_TOOLS:
                sql = (ev.get("tool_input") or {}).get(SQL_TOOLS[tool]) or ""
                if not saw_sql:
                    saw_sql, schema_before_first_sql = True, schema_seen
                if last_failed:
                    repairs += 1
                last_failed = False
                call = {"tool": tool, "sql": sql, "verdict": judge_sql_text(sql), "failed": None}
                sql_calls.append(call)
                if ev.get("tool_use_id"):
                    pending[ev["tool_use_id"]] = call
        elif kind == "tool_end" and tool in SQL_TOOLS:
            call = pending.pop(ev.get("tool_use_id"), None) or (sql_calls[-1] if sql_calls else None)
            if call is not None:
                call["failed"] = _tool_end_failed(ev)
                last_failed = bool(call["failed"])
    if not sql_calls:
        return {"applicable": False, "sql_calls": 0, "rules": {"R1_schema_first": "N/A", "R2_single_select": "N/A",
                                                               "R3_no_comment_semicolon": "N/A", "R4_fixes_le_2": "N/A"},
                "repairs": 0, "failed_calls": 0, "calls": []}
    r2 = all(c["verdict"]["single_select"] for c in sql_calls)
    r3 = all(c["verdict"]["no_comment"] and c["verdict"]["no_semicolon"] for c in sql_calls)
    return {"applicable": True, "sql_calls": len(sql_calls),
            "rules": {"R1_schema_first": "PASS" if schema_before_first_sql else "FAIL",
                      "R2_single_select": "PASS" if r2 else "FAIL",
                      "R3_no_comment_semicolon": "PASS" if r3 else "FAIL",
                      "R4_fixes_le_2": "PASS" if repairs <= 2 else "FAIL"},
            "repairs": repairs, "failed_calls": sum(1 for c in sql_calls if c["failed"]),
            "calls": [{"tool": c["tool"], "sql": c["sql"][:400], "failed": c["failed"], **c["verdict"]} for c in sql_calls]}


def read_events(path: Path) -> list[dict]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def judge_dirs(dirs: list[Path]) -> dict:
    report = {"runs": [], "summary": {}}
    for d in dirs:
        for f in sorted(d.glob("*.events.jsonl")):
            verdict = judge_events(read_events(f))
            report["runs"].append({"dir": d.name, "file": f.name, **verdict})
    applicable = [r for r in report["runs"] if r["applicable"]]
    rules = ["R1_schema_first", "R2_single_select", "R3_no_comment_semicolon", "R4_fixes_le_2"]
    report["summary"] = {"runs": len(report["runs"]), "applicable": len(applicable),
                         "sql_calls": sum(r["sql_calls"] for r in applicable),
                         **{k: f"{sum(1 for r in applicable if r['rules'][k] == 'PASS')}/{len(applicable)}" for k in rules},
                         "all_pass": all(all(r["rules"][k] == "PASS" for k in rules) for r in applicable) if applicable else None}
    return report


def render(report: dict) -> str:
    rules = ["R1_schema_first", "R2_single_select", "R3_no_comment_semicolon", "R4_fixes_le_2"]
    lines = ["| run | SQL calls | failed | repairs | R1 schema first | R2 one SELECT | R3 no comment/; | R4 fixes ≤ 2 |",
             "|---|---:|---:|---:|---|---|---|---|"]
    for r in report["runs"]:
        lines.append(f"| {r['dir']}/{r['file'].split('-run-')[0]} | {r['sql_calls']} | {r['failed_calls']} | {r['repairs']} | "
                     + " | ".join(r["rules"][k] for k in rules) + " |")
    s = report["summary"]
    lines.append("")
    lines.append(f"runs {s['runs']} (applicable {s['applicable']}, SQL calls {s['sql_calls']}) — "
                 + " · ".join(f"{k} {s[k]}" for k in rules) + f" — all_pass={s['all_pass']}")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dirs", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    report = judge_dirs(args.dirs)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    text = render(report)
    (args.out / "result.md").write_text(text, encoding="utf-8")
    print(text)
    return 0 if report["summary"]["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
