"""fuxa-init: wait for FUXA, then upload project.json through POST /api/project (no auth in student edition).

Idempotent: FUXA keeps no volume here, so every `docker compose up` re-uploads the same project.
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error

FUXA = os.getenv("FUXA_URL", "http://fuxa:1881")
PROJECT = os.getenv("FUXA_PROJECT", "/work/project.json")


def wait_ready(timeout=180):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen(f"{FUXA}/api/settings", timeout=5) as r:
                if r.status == 200:
                    return True
        except Exception as e:  # noqa: BLE001
            print(f"waiting for FUXA ({e.__class__.__name__}) ...", flush=True)
        time.sleep(3)
    return False


def upload():
    body = open(PROJECT, "rb").read()
    req = urllib.request.Request(f"{FUXA}/api/project", data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status


if __name__ == "__main__":
    if not wait_ready():
        print("FUXA not reachable", file=sys.stderr)
        sys.exit(1)
    prj = json.load(open(PROJECT, encoding="utf-8"))
    print(f"uploading FUXA project '{prj['name']}' ({len(prj['devices'])} device(s), {len(prj['alarms'])} alarms)")
    for attempt in range(5):
        try:
            print("POST /api/project ->", upload())
            break
        except urllib.error.HTTPError as e:
            print("upload failed:", e.code, e.read()[:200], file=sys.stderr)
            time.sleep(3)
        except Exception as e:  # noqa: BLE001
            print("upload error:", e, file=sys.stderr)
            time.sleep(3)
    else:
        sys.exit(1)
    # FUXA restarts its runtime after a project upload; confirm the device came back
    time.sleep(3)
    try:
        with urllib.request.urlopen(f"{FUXA}/api/project", timeout=10) as r:
            data = json.loads(r.read())
            print("project now has views:", [v.get("name") for v in data.get("hmi", {}).get("views", [])])
    except Exception as e:  # noqa: BLE001
        print("verify skipped:", e)
    print("fuxa-init done")
