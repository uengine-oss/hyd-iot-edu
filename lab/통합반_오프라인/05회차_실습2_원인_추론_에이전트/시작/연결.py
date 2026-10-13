"""사내 AI 서버에 묻는다. 접속 정보는 이 폴더의 접속_정보.txt 에서 읽는다.

    python 연결.py     접속이 되는지 본다
"""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

_환경_경로 = Path(__file__).resolve().parent / "접속_정보.txt"


def _환경():
    if not _환경_경로.exists():
        raise SystemExit("접속_정보.txt 파일이 없다. 받은 폴더에서 다시 가져온다.")
    값 = {}
    for 줄 in _환경_경로.read_text(encoding="utf-8").splitlines():
        줄 = 줄.strip()
        if 줄 and not 줄.startswith("#") and "=" in 줄:
            이름, 내용 = 줄.split("=", 1)
            값[이름.strip()] = 내용.strip().strip("\"'")
    for 이름 in ("OPENAI_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        if not 값.get(이름):
            raise SystemExit(f"접속_정보.txt 의 {이름} 이 비어 있다. 받은 값을 등호 뒤에 적고 저장한다.")
    return 값


def 묻기(대화, 도구=None):
    """대화(메시지 목록)를 보내고 답(메시지 한 건)을 돌려준다. 도구를 주면 그 가운데서 골라 부를 수 있다."""
    환경 = _환경()
    보냄 = {"model": 환경["LLM_MODEL"], "messages": 대화, "temperature": 0, "max_tokens": 3000}
    보냄.update(json.loads(환경.get("LLM_EXTRA_BODY") or "{}"))
    if 도구:
        보냄["tools"] = 도구
    요청 = urllib.request.Request(
        환경["OPENAI_BASE_URL"].rstrip("/") + "/chat/completions",
        data=json.dumps(보냄).encode("utf-8"),
        headers={"Authorization": "Bearer " + 환경["LLM_API_KEY"], "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(요청, timeout=120) as 응답:
            return json.loads(응답.read())["choices"][0]["message"]
    except urllib.error.HTTPError as 오류:
        까닭 = {401: "키가 맞지 않는다", 403: "키에 권한이 없다", 404: "주소나 모델 이름이 맞지 않는다"}.get(오류.code, "서버가 요청을 받지 않았다")
        raise SystemExit(f"묻지 못했다({오류.code}): {까닭}. 접속_정보.txt 의 값을 다시 본다.")
    except urllib.error.URLError:
        raise SystemExit("서버에 닿지 못했다. 네트워크와 접속_정보.txt 의 OPENAI_BASE_URL 을 다시 본다.")


if __name__ == "__main__":
    답 = 묻기([{"role": "user", "content": "한 문장으로 인사해 주세요."}])
    print("연결됨 ·", _환경()["LLM_MODEL"])
    print("받은 답:", (답.get("content") or "").strip())
    sys.exit(0)
