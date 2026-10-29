"""LLM 서버(OpenAI 호환 API)에 요청을 보낸다. 접속 정보는 이 폴더의 .env 에서 읽는다.

    python llm_client.py     연결되는지 본다
"""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

_ENV = Path(__file__).resolve().parent / ".env"


def _settings():
    if not _ENV.exists():
        raise SystemExit(".env 파일이 없다. 받은 폴더에서 다시 가져온다.")
    settings = {}
    for line in _ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            settings[key.strip()] = value.strip().strip("\"'")
    for key in ("OPENAI_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        if not settings.get(key):
            raise SystemExit(f".env 의 {key} 가 비어 있다. 받은 값을 등호 뒤에 적고 저장한다.")
    return settings


def _reason(error):
    """서버가 거절한 까닭을 고칠 곳으로 옮긴다. LiteLLM 중계 서버는 오류 본문에 종류(type)와 설명(message)을 적는다."""
    try:
        detail = json.loads(error.read().decode("utf-8")).get("error") or {}
    except ValueError:
        detail = {}
    kind, message = str(detail.get("type")), str(detail.get("message"))
    if error.code == 401 and message.startswith("litellm.AuthenticationError"):
        return "내 키는 통과했지만 중계 서버 뒤쪽의 키가 맞지 않는다. 내 .env 문제가 아니니 강사에게 알린다"
    if error.code == 401:
        return ".env 의 LLM_API_KEY 가 받은 키와 다르다"
    if kind == "key_model_access_denied" or "Invalid model name" in message:
        return ".env 의 LLM_MODEL 이 서버에 없는 이름이다. 받은 모델 이름을 적는다"
    if error.code == 404:
        return ".env 의 OPENAI_BASE_URL 이 받은 주소와 다르다. 끝이 /v1 인지 본다"
    if error.code == 429:
        return "서버가 지금 요청을 받지 못한다. 1분 뒤 다시 실행하고, 같으면 강사에게 알린다"
    return "서버가 요청을 받지 않았다. 강사에게 알린다"

def chat(messages, tools=None):
    """대화(메시지 목록)를 보내고 답(메시지 한 건)을 돌려준다. 도구를 주면 그 가운데서 골라 부를 수 있다."""
    settings = _settings()
    body = {"model": settings["LLM_MODEL"], "messages": messages, "temperature": 0, "max_completion_tokens": 3000}
    if tools:
        body["tools"] = tools
    request = urllib.request.Request(
        settings["OPENAI_BASE_URL"].rstrip("/") + "/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": "Bearer " + settings["LLM_API_KEY"], "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read())["choices"][0]["message"]
    except urllib.error.HTTPError as error:
        raise SystemExit(f"묻지 못했다({error.code}): {_reason(error)}.")
    except urllib.error.URLError:
        raise SystemExit("서버에 닿지 못했다. 네트워크와 .env 의 OPENAI_BASE_URL 을 다시 본다.")


if __name__ == "__main__":
    reply = chat([{"role": "user", "content": "한 문장으로 인사해 주세요."}])
    print("연결됨 ·", _settings()["LLM_MODEL"])
    print("받은 답:", (reply.get("content") or "").strip())
    sys.exit(0)
