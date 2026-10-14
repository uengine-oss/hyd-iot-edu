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


def chat(messages, tools=None):
    """대화(메시지 목록)를 보내고 답(메시지 한 건)을 돌려준다. 도구를 주면 그 가운데서 골라 부를 수 있다."""
    settings = _settings()
    body = {"model": settings["LLM_MODEL"], "messages": messages, "temperature": 0, "max_tokens": 3000}
    body.update(json.loads(settings.get("LLM_EXTRA_BODY") or "{}"))
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
        reason = {401: "키가 맞지 않는다", 403: "키에 권한이 없다", 404: "주소나 이름이 맞지 않는다"}.get(error.code, "서버가 요청을 받지 않았다")
        raise SystemExit(f"묻지 못했다({error.code}): {reason}. .env 의 값을 다시 본다.")
    except urllib.error.URLError:
        raise SystemExit("서버에 닿지 못했다. 네트워크와 .env 의 OPENAI_BASE_URL 을 다시 본다.")


if __name__ == "__main__":
    reply = chat([{"role": "user", "content": "한 문장으로 인사해 주세요."}])
    print("연결됨 ·", _settings()["LLM_MODEL"])
    print("받은 답:", (reply.get("content") or "").strip())
    sys.exit(0)
