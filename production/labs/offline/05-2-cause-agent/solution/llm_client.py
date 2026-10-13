"""LLM 서버(OpenAI 호환 API)에 요청을 보낸다. 접속 정보는 이 폴더의 .env 에서 읽는다.

    python llm_client.py     연결되는지 본다

.env 가 없으면 서버를 부르지 않고, recorded/replies.json 에 저장해 둔 서버의 답을 순서대로 돌려준다(재생).
도구 실행, 호출 기록, 대조는 재생에서도 실제로 돈다. 저장된 것과 다른 요청에는 답하지 못한다.
"""
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

_ENV = Path(__file__).resolve().parent / ".env"
_RECORDED = Path(__file__).resolve().parent / "recorded" / "replies.json"
_notified = False


def _settings():
    if not _ENV.exists():
        raise SystemExit(".env 파일이 없다. .env.example 을 복사해 이름을 .env 로 바꾸고 받은 값을 적는다.")
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


def _key(messages):
    """저장과 재생에 쓰는 열쇠. 처음 두 메시지(지시와 사례)와 지금까지 받은 답의 수로 요청을 가린다."""
    head = json.dumps(messages[:2], ensure_ascii=False, sort_keys=True)
    turn = sum(1 for m in messages if m.get("role") == "assistant")
    return f"{hashlib.sha256(head.encode('utf-8')).hexdigest()[:16]}:{turn}"


def _replay(messages):
    global _notified
    if not _notified:
        print("[재생] .env 가 없어 서버를 부르지 않고, 저장해 둔 실행 기록을 재생합니다.")
        _notified = True
    recorded = json.loads(_RECORDED.read_text(encoding="utf-8")) if _RECORDED.exists() else {}
    reply = recorded.get(_key(messages))
    if reply is None:
        raise SystemExit("[재생] 저장된 기록에 없는 요청입니다. 설정이나 사례를 바꾸면 재생할 수 없습니다. 실제로 실행하려면 .env 에 접속 정보를 넣습니다.")
    return reply


def chat(messages, tools=None):
    """대화(메시지 목록)를 보내고 답(메시지 한 건)을 돌려준다. 도구를 주면 그 가운데서 골라 부를 수 있다."""
    if not _ENV.exists():
        return _replay(messages)
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
            reply = json.loads(response.read())["choices"][0]["message"]
        if os.environ.get("LLM_RECORD") == "1":   # 재생에 쓸 답을 저장한다
            recorded = json.loads(_RECORDED.read_text(encoding="utf-8")) if _RECORDED.exists() else {}
            recorded[_key(messages)] = {k: reply.get(k) for k in ("role", "content", "tool_calls") if reply.get(k) is not None}
            _RECORDED.parent.mkdir(exist_ok=True)
            _RECORDED.write_text(json.dumps(recorded, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        return reply
    except urllib.error.HTTPError as error:
        reason = {401: "키가 맞지 않는다", 403: "키에 권한이 없다", 404: "주소나 이름이 맞지 않는다"}.get(error.code, "서버가 요청을 받지 않았다")
        raise SystemExit(f"묻지 못했다({error.code}): {reason}. .env 의 값을 다시 본다.")
    except urllib.error.URLError:
        raise SystemExit("서버에 닿지 못했다. 네트워크와 .env 의 OPENAI_BASE_URL 을 다시 본다.")


if __name__ == "__main__":
    if not _ENV.exists():
        print("[재생] .env 가 없습니다. python agent.py 를 실행하면 저장해 둔 실행 기록을 재생합니다.")
        sys.exit(0)
    reply = chat([{"role": "user", "content": "한 문장으로 인사해 주세요."}])
    print("연결됨 ·", _settings()["LLM_MODEL"])
    print("받은 답:", (reply.get("content") or "").strip())
    sys.exit(0)
