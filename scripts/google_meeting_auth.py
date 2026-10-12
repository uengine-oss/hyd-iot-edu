"""Run the meeting MCP's local browser OAuth helper (no secrets in arguments)."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "students" / "_template" / "google_meeting_mcp"))
from auth import main

if __name__ == "__main__":
    raise SystemExit(main())
