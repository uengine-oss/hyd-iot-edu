"""Preserve actual instance/events and CLI sessions; never invent a pass verdict."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import shutil
import urllib.request


def business_error(event):
    """A successful MCP transport can still return a business-error envelope."""
    output = event.get("data", {}).get("output")
    if isinstance(output, dict):
        envelope = output.get("structured_content", output)
        return isinstance(envelope, dict) and envelope.get("result") == "error"
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("instance")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    dest = Path(args.out)
    dest.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen("http://localhost:8080/api/instances/" + args.instance) as response:
        view = json.load(response)
    (dest / "instance.json").write_text(json.dumps(view, ensure_ascii=False, indent=2), encoding="utf-8")
    events = view["events"]
    ended = {(e.get("job_id"), e.get("data", {}).get("tool_use_id"))
             for e in events if e["event_type"] == "tool_usage_finished"}
    sessions = {e.get("data", {}).get("session_id") for e in events}
    sessions.update((w.get("output") or {}).get("cliagents_session_id") for w in view["workitems"]
                    if isinstance(w.get("output"), dict))
    sessions.discard(None)
    cli_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    copied = []
    for sid in sorted(sessions):
        for src in (cli_home / "sessions").rglob(f"*{sid}.jsonl"):
            target = dest / src.name
            shutil.copyfile(src, target)
            copied.append({"session": sid, "file": target.name, "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
    summary = {
        "instance": args.instance,
        "status": view["instance"]["status"],
        "end_event": view["instance"].get("end_event"),
        "workitems": [{k: w.get(k) for k in ("activity_id", "status", "draft_status", "retry", "consumer")} for w in view["workitems"]],
        "event_counts": dict(Counter(e["event_type"] for e in events)),
        "tools": dict(Counter(e.get("data", {}).get("tool") for e in events if e["event_type"] == "tool_usage_started")),
        "tool_errors": [e for e in events if e["event_type"] == "tool_usage_finished" and e.get("data", {}).get("is_error")],
        "business_tool_errors": [e for e in events if e["event_type"] == "tool_usage_finished" and business_error(e)],
        "unmatched_tool_starts": [e for e in events if e["event_type"] == "tool_usage_started"
                                  and (e.get("job_id"), e.get("data", {}).get("tool_use_id")) not in ended],
        "error_count_scope": "Recorded MCP is_error and explicit result:error envelopes. Truncated payloads need raw CLI trace review.",
        "sessions": copied,
    }
    (dest / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": summary["status"], "events": summary["event_counts"], "tools": summary["tools"], "sessions": len(copied)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
