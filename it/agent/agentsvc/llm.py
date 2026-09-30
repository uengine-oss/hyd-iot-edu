"""Optional LLM narrative (the LiteLLM/model-gateway slot). The pipeline never depends on it.

No ANTHROPIC_API_KEY  -> deterministic Korean template sentence (card.template_summary)
ANTHROPIC_API_KEY set -> Claude rewrites the card into a 3-sentence operator brief; the card JSON is the only
                          source of truth and the model is told it may not invent causes, actions or numbers.
"""
import json
import logging
import os

log = logging.getLogger("agent.llm")
MODEL = os.getenv("LLM_MODEL", "claude-opus-5")

SYSTEM = ("당신은 유압설비 운전원을 돕는 조치 가이드 작성자입니다. 주어진 가이드 카드 JSON만 근거로 삼고, "
          "카드에 없는 원인·조치·수치를 절대 추가하지 마세요. 한국어 3문장: ① 무슨 경보와 증거인지 ② 가장 유력한 원인과 근거 "
          "③ 권장 조치(파라미터 포함)와 그 후속 작업지시. 명령을 직접 내리라는 표현은 쓰지 않습니다(승인은 운전원 몫).")


def available() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def summarize(card: dict, fallback: str) -> tuple[str, str]:
    """Return (summary, source) where source is 'template' or the model id."""
    if not available():
        return fallback, "template"
    try:
        import anthropic
    except ImportError:
        log.warning("anthropic SDK not installed; using template summary")
        return fallback, "template"
    client = anthropic.Anthropic()
    slim = {k: card[k] for k in ("alert", "causes", "recommended", "freshness") if k in card}
    try:
        resp = client.beta.messages.create(
            model=MODEL,
            max_tokens=1024,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=SYSTEM,
            messages=[{"role": "user", "content": "가이드 카드 JSON:\n" + json.dumps(slim, ensure_ascii=False)}],
        )
        if resp.stop_reason == "refusal":
            log.warning("model declined; using template summary")
            return fallback, "template"
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        return (text or fallback), MODEL
    except anthropic.RateLimitError:
        log.warning("rate limited; using template summary")
    except anthropic.APIStatusError as e:
        log.warning("API error %s: %s; using template summary", e.status_code, e.message)
    except anthropic.APIConnectionError:
        log.warning("network error; using template summary")
    return fallback, "template"
