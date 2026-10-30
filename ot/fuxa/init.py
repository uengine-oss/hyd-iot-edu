"""fuxa-init: wait for FUXA, then upload project.json through POST /api/project (no auth in student edition).

FUXA 에는 볼륨이 없어 컨테이너를 새로 만들면 빈 프로젝트로 뜬다. 그래서 시작할 때마다 저장소의 화면(ot/fuxa/project.json)을 다시
올린다 — FUXA 화면에서 손으로 고친 내용은 다음 시작에 덮어써진다(수업 실습은 FUXA 화면을 고치지 않는다 — 실라버스 대조 2026-10-30).
화면을 바꾸려면 project.json 을 고친다(생성기는 workspace 브랜치 workspace/개발/scripts/build_fuxa_project.py).
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
