"""윤문 요청문 파일 하나를 아스트라(gpt-6-astra)에 보내고 답을 파일로 받는다. API 키로 부른다.

    python3 production/tools/deck/아스트라.py <요청문 파일> <결과 파일>

- 키는 환경변수 REAL_OPEN_API_KEY에서 읽고, 출력하지 않는다. 없으면 멈춘다.
- OpenAI Responses API(https://api.openai.com/v1/responses)를 부른다. OPENAI_BASE_URL은 쓰지 않는다(다른 서버를 가리킬 수 있다).
- 실패하면 상태 코드와 응답 앞부분을 찍고 멈춘다. 결과가 비어 있어도 멈춘다.
"""
import json
import os
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

MODEL = "gpt-6-astra"


def main():
    req_file, out_file = Path(sys.argv[1]), Path(sys.argv[2])
    key = os.environ.get("REAL_OPEN_API_KEY")
    if not key:
        sys.exit("[실패] 환경변수 REAL_OPEN_API_KEY가 없다")
    body = {"model": MODEL, "input": req_file.read_text(encoding="utf-8"), "reasoning": {"effort": "medium"}}
    req = urllib.request.Request("https://api.openai.com/v1/responses", data=json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    cafile = os.environ.get("SSL_CERT_FILE") or os.environ.get("REQUESTS_CA_BUNDLE")
    ctx = ssl.create_default_context(cafile=cafile) if cafile else ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=900, context=ctx) as r:
            d = json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"[실패] 응답 {e.code}: {e.read().decode(errors='replace')[:400]}")
    text = "".join(c.get("text", "") for o in d.get("output", []) if o.get("type") == "message"
                   for c in o.get("content", []) if c.get("type") == "output_text")
    if not text.strip():
        sys.exit(f"[실패] 답이 비어 있다: {json.dumps(d, ensure_ascii=False)[:400]}")
    out_file.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
    u = d.get("usage") or {}
    print(f"{out_file} — 모델 {d.get('model', MODEL)} · 입력 {u.get('input_tokens')} · 출력 {u.get('output_tokens')} 토큰")


if __name__ == "__main__":
    main()
