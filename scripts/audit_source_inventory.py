"""Capture source provenance for the meeting/repository audit without changing source repositories."""
from __future__ import annotations

import hashlib
import io
import json
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HANDOFF = ROOT / "docs/handoff"
SOURCES = HANDOFF / "sources"
EVIDENCE = ROOT / ".evidence/reaudit/2026-10-04-baseline"
ARCHIVE = ROOT.parent / "HYD_R2_FINAL_ALL_2026-10-03.zip"
REFS = Path(r"C:\Users\roede\AppData\Local\Temp\claude\d--work-study\952d3c36-79d1-411d-8a6b-ca449642fa1c\scratchpad\refs")
SESSION = Path(r"C:\Users\roede\.codex\sessions\2026\10\04\rollout-2026-10-04T01-57-47-01a102b3-4e6e-7ab0-8b76-18bbc4bf8b91.jsonl")


def git(path: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(path), *args], capture_output=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise RuntimeError(f"git {args}: {result.stderr}")
    return result.stdout.strip()


def write_new(path: Path, data: bytes) -> None:
    if path.exists():
        if path.read_bytes() != data:
            raise RuntimeError(f"Baseline already exists with different contents: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def main() -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    # Snapshot the pre-audit handoff before its current contract is updated.
    backup = EVIDENCE / "handoff-before.zip"
    if not backup.exists():
        with zipfile.ZipFile(backup, "w", zipfile.ZIP_DEFLATED) as z:
            for p in sorted(HANDOFF.glob("*.md")):
                z.write(p, p.name)
            z.write(ROOT / "AGENTS.md", "AGENTS.md")
    manifest = {"date_kst": "2026-10-04", "archive": str(ARCHIVE),
                "archive_sha256": hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(), "files": []}
    with zipfile.ZipFile(ARCHIVE) as z:
        for suffix, output in [("_1.txt", "meeting-1.txt"), ("_2.txt", "meeting-2.txt")]:
            name = next(n for n in z.namelist() if n.endswith(suffix))
            data = z.read(name)
            write_new(SOURCES / output, data)
            manifest["files"].append({"member": name, "local": output, "sha256": hashlib.sha256(data).hexdigest()})
        nested = next(n for n in z.namelist() if "Repository_Map" in n)
        with zipfile.ZipFile(io.BytesIO(z.read(nested))) as atlas:
            for name in atlas.namelist():
                if not name.endswith((".md", ".json", ".txt")):
                    continue
                relative = Path(*Path(name).parts[1:])
                if ".." in relative.parts or relative.is_absolute():
                    raise ValueError(name)
                data = atlas.read(name)
                write_new(SOURCES / "repository-map" / relative, data)
                manifest["files"].append({"member": nested + "!" + name, "local": "repository-map/" + relative.as_posix(),
                                          "sha256": hashlib.sha256(data).hexdigest()})
    write_new(SOURCES / "provenance.json", (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode())
    inventory = {"hyd_head": git(ROOT, "rev-parse", "HEAD"), "refs_root": str(REFS), "repositories": []}
    for path in sorted(REFS.iterdir()):
        if not (path / ".git").exists():
            continue
        inventory["repositories"].append({"name": path.name, "path": str(path), "head": git(path, "rev-parse", "HEAD"),
            "origin": git(path, "remote", "get-url", "origin"), "status": git(path, "status", "--porcelain=v1")})
    write_new(EVIDENCE / "repository-snapshots.json", (json.dumps(inventory, ensure_ascii=False, indent=2) + "\n").encode())
    write_new(EVIDENCE / "hyd-status.txt", (git(ROOT, "status", "--porcelain=v1") + "\n").encode())
    utterances = []
    for line in SESSION.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        payload = row.get("payload", {})
        if row.get("type") != "response_item" or payload.get("role") != "user":
            continue
        for item in payload.get("content", []):
            text = item.get("text", "")
            if text.startswith(("# AGENTS.md instructions", "<external_codex_apps_open_page>")):
                continue
            if "## My request:\n" in text:
                text = text.split("## My request:\n", 1)[1]
            utterances.append({"timestamp": row.get("timestamp"), "text": text})
    # Preserve duplicate utterances; repetition is part of the user's actual conversation.
    write_new(EVIDENCE / "user-utterances.json", (json.dumps(utterances, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({"source_files": len(manifest["files"]), "reference_repositories": len(inventory["repositories"]),
                      "utterances": len(utterances), "hyd_head": inventory["hyd_head"]}))


if __name__ == "__main__":
    main()
