"""fuxa-init: wait for FUXA, upload project.json through POST /api/project (no auth in student edition), then read the project
back and stop with exit 1 unless FUXA now serves the uploaded screens and MQTT device.

FUXA 에는 볼륨이 없어 컨테이너를 새로 만들면 빈 프로젝트로 뜬다. 그래서 시작할 때마다 저장소의 화면(ot/fuxa/project.json)을 다시
올린다 — FUXA 화면에서 손으로 고친 내용은 다음 시작에 덮어써진다(수업 실습은 FUXA 화면을 고치지 않는다 — 실라버스 대조 2026-10-30).
화면을 바꾸려면 project.json 을 고친다(생성기는 workspace 브랜치 workspace/개발/scripts/build_fuxa_project.py).
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

FUXA = os.getenv("FUXA_URL", "http://fuxa:1881")
PROJECT = os.getenv("FUXA_PROJECT", "/work/project.json")


def wait_ready(timeout=180):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen(f"{FUXA}/api/settings", timeout=5) as r:
                if r.status == 200:
                    return True
        except (urllib.error.URLError, OSError) as e:
            print(f"waiting for FUXA ({e.__class__.__name__}) ...", flush=True)
        time.sleep(3)
    return False


def upload(body: bytes) -> int:
    req = urllib.request.Request(f"{FUXA}/api/project", data=body, method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status


def served() -> dict:
    with urllib.request.urlopen(f"{FUXA}/api/project", timeout=10) as r:
        return json.loads(r.read())


def summary(project: dict) -> tuple:
    """What must survive the upload: the screen names and the MQTT devices (id · broker address)."""
    views = sorted(v.get("name") for v in (project.get("hmi") or {}).get("views") or [])
    devices = sorted((d.get("id"), (d.get("property") or {}).get("address")) for d in (project.get("devices") or {}).values())
    return views, devices


def main(pause: float = 3.0) -> int:
    """pause: seconds between upload retries and read-backs (FUXA restarts its runtime after an upload)."""
    if not wait_ready():
        print("FUXA not reachable", file=sys.stderr)
        return 1
    body = open(PROJECT, "rb").read()
    prj = json.loads(body)
    print(f"uploading FUXA project '{prj['name']}' ({len(prj['devices'])} device(s), {len(prj['alarms'])} alarms)")
    for attempt in range(5):
        try:
            print("POST /api/project ->", upload(body))
            break
        except urllib.error.HTTPError as e:
            print("upload failed:", e.code, e.read()[:200], file=sys.stderr)
        except (urllib.error.URLError, OSError) as e:
            print("upload error:", e, file=sys.stderr)
        time.sleep(pause)
    else:
        return 1
    # FUXA restarts its runtime after a project upload; read it back until it serves what was uploaded
    want = summary(prj)
    for attempt in range(10):
        time.sleep(pause)
        try:
            got = summary(served())
        except (urllib.error.URLError, OSError, ValueError) as e:
            print("read back failed:", e, file=sys.stderr)
            continue
        if got == want:
            print("FUXA serves views", got[0], "devices", got[1])
            print("fuxa-init done")
            return 0
        print("FUXA does not serve the uploaded project yet:", got, file=sys.stderr)
    print("FUXA did not keep the uploaded project (views/devices differ) — see the fuxa container log", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
