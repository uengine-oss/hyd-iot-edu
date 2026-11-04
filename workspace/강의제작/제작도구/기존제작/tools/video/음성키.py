"""음성 키를 읽어 계정을 조회하거나 명령 하나를 그 환경으로 돌린다. 키 값은 어디에도 찍지 않는다.

    ELEVENLABS_KEY_FILE=<키 파일> <py> workspace/강의제작/제작도구/기존제작/tools/video/음성키.py 계정 <음성 ID>
    ELEVENLABS_KEY_FILE=<키 파일> <py> workspace/강의제작/제작도구/기존제작/tools/video/음성키.py 실행 <명령 …>

- 계정: 읽기 전용이다. 등급 · 남은 크레딧 · 그 음성의 이름과 종류를 찍는다. 계정에 그 음성이 없으면 실패한다.
- 실행: 그 명령만 ELEVENLABS_API_KEY가 있는 환경으로 돌리고 종료 코드를 그대로 돌려준다. 비용은 그 명령이 정한다(영상.md V-4).
- 키: 환경변수 ELEVENLABS_API_KEY가 있으면 그것, 없으면 ELEVENLABS_KEY_FILE이 가리키는 파일 안의 sk_ 꼴 문자열 하나다.
  없거나 둘 이상이면 개수만 말하고 멈춘다. 공개 저장소이므로 키 파일 경로를 코드 · 문서 · 커밋에 적지 않는다.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

USE = "사용: 음성키.py 계정 <음성 ID> | 음성키.py 실행 <명령 …>"


def key():
    k = os.environ.get("ELEVENLABS_API_KEY")
    if k:
        return k
    p = os.environ.get("ELEVENLABS_KEY_FILE")
    if not p:
        sys.exit("키 없음: 환경변수 ELEVENLABS_API_KEY나 ELEVENLABS_KEY_FILE(키 파일 경로)을 준다")
    try:
        s = open(p, encoding="utf-8", errors="replace").read()
    except OSError as e:
        sys.exit(f"ELEVENLABS_KEY_FILE을 열지 못했다: {type(e).__name__}")
    m = re.findall(r"\bsk_[A-Za-z0-9]+", s)
    if len(m) != 1:
        sys.exit(f"ELEVENLABS_KEY_FILE 안의 sk_ 꼴 키가 하나가 아니라 {len(m)}개다")
    return m[0]


def get(path, k):
    r = urllib.request.Request("https://api.elevenlabs.io" + path, headers={"xi-api-key": k})
    try:
        return json.load(urllib.request.urlopen(r, timeout=60))
    except urllib.error.HTTPError as e:
        sys.exit(f"{path}: 응답 코드 {e.code}")


if len(sys.argv) < 3 or sys.argv[1] not in ("계정", "실행"):
    sys.exit(USE)
if sys.argv[1] == "계정":
    k = key()
    u = get("/v1/user/subscription", k)
    print({n: u.get(n) for n in ("tier", "character_count", "character_limit", "next_character_count_reset_unix", "status")})
    print("남은 크레딧", u["character_limit"] - u["character_count"])
    v = [x for x in get("/v1/voices", k)["voices"] if x["voice_id"] == sys.argv[2]]
    if not v:
        sys.exit(f"음성 {sys.argv[2]}: 이 계정에 없다")
    print("음성", [(x["name"], x["category"]) for x in v])
else:
    exe = shutil.which(sys.argv[2])   # Windows의 프로세스 생성은 빗금 쓴 상대 경로(.venv314/Scripts/python.exe)를 못 찾는다
    if not exe:
        sys.exit(f"{sys.argv[2]}: 실행 파일이 없다")
    sys.exit(subprocess.run([os.path.abspath(exe), *sys.argv[3:]], env=dict(os.environ, ELEVENLABS_API_KEY=key())).returncode)
