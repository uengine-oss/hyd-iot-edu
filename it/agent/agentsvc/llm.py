"""Optional bounded OpenAI-compatible or Anthropic narrative; failures use the template."""
import json
import logging
import os

log = logging.getLogger("agent.llm")
PROVIDER = os.getenv("LLM_PROVIDER", "auto")
if PROVIDER == "auto":
    PROVIDER = "openai" if os.getenv("OPENAI_API_KEY") else "anthropic"
MODEL = os.getenv("LLM_MODEL") or ("gpt-4o-mini" if PROVIDER == "openai" else "claude-sonnet-4-6")
SYSTEM = ("당신은 유압설비 운전원을 돕는 조치 가이드 작성자입니다. 주어진 가이드 카드 JSON만 근거로 삼고, "
          "카드에 없는 원인·조치·수치를 절대 추가하지 마세요. 한국어 3문장: 경보와 증거, 원인과 근거, "
          "권장 조치와 후속 작업지시. 승인은 운전원 몫이며 직접 명령하지 마세요.")


def available() -> bool:
    return bool(os.getenv("OPENAI_API_KEY") if PROVIDER == "openai" else
                os.getenv("ANTHROPIC_API_KEY") if PROVIDER == "anthropic" else False)


def summarize(card: dict, fallback: str) -> tuple[str, str]:
    if not available():
        return fallback, "template"
    slim = {k: card[k] for k in ("alert", "causes", "recommended", "freshness") if k in card}
    prompt = "가이드 카드 JSON: " + json.dumps(slim, ensure_ascii=False)
    try:
        timeout = max(1.0, min(float(os.getenv("LLM_TIMEOUT_SECONDS", "8")), 30.0))
        if PROVIDER == "openai":
            import urllib.request
            base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
            body = {"model": MODEL, "messages": [{"role": "system", "content": SYSTEM},
                    {"role": "user", "content": prompt}], "max_completion_tokens": 600}
            req = urllib.request.Request(base + "/chat/completions", data=json.dumps(body).encode(),
                headers={"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"], "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as response:
                choice = json.load(response)["choices"][0]
            if choice.get("finish_reason") != "stop" or choice["message"].get("refusal"):
                return fallback, "template"
            text = choice["message"].get("content")
        else:
            import anthropic
            with anthropic.Anthropic(timeout=timeout, max_retries=0) as client:
                response = client.messages.create(model=MODEL, max_tokens=600, system=SYSTEM,
                    messages=[{"role": "user", "content": prompt}])
            if response.stop_reason != "end_turn":
                return fallback, "template"
            text = "".join(b.text for b in response.content if b.type == "text")
        if isinstance(text, str) and text.strip():
            return text.strip(), MODEL
    except Exception as exc:
        # Proxies may include secrets in error bodies/URLs; log only the exception class.
        log.warning("LLM unavailable (%s); using template", type(exc).__name__)
    return fallback, "template"
