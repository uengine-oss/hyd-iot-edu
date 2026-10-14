"""윤문 요청문 파일 하나를 아스트라(gpt-6-astra)에 보내고 답을 파일로 받는다.

    python3 production/tools/deck/아스트라.py <요청문 파일> <결과 파일>          # 사용자 ChatGPT 계정(Codex CLI)으로
    python3 production/tools/deck/아스트라.py --api <요청문 파일> <결과 파일>    # API 키로

- 기본은 Codex CLI(`codex exec`)를 사용자 계정 로그인으로 부른다. 로그인은 세션마다 `codex login --device-auth`로 한다
  (로그인 정보는 ~/.codex에만 남고 저장소에 들어가지 않는다). 로그인이 없으면 멈춘다. API 키 경로로 넘어가지 않는다.
  빈 임시 폴더에서 읽기 전용으로 돌려 저장소를 읽거나 고치지 않게 한다. 사용자 설정 파일과 규칙 파일은 읽지 않는다.
- `--api`: 키를 환경변수 REAL_OPEN_API_KEY에서 읽고(출력하지 않는다) OpenAI Responses API를 부른다. OPENAI_BASE_URL은 쓰지 않는다.
- 실패하면 원인을 찍고 멈춘다. 결과가 비어 있어도 멈춘다.
"""
import json
import os
import shutil
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

MODEL = "gpt-6-astra"


def by_codex(req_file: Path, out_file: Path):
    if not shutil.which("codex"):
        sys.exit("[실패] codex가 없다. npm install -g @openai/codex 뒤 codex login --device-auth로 로그인한다")
    st = subprocess.run(["codex", "login", "status"], capture_output=True, text=True)
    if st.returncode or "Logged in" not in (st.stdout + st.stderr):
        sys.exit(f"[실패] codex 로그인이 없다(codex login --device-auth): {(st.stdout + st.stderr).strip()[:200]}")
    t0 = time.time()
    with tempfile.TemporaryDirectory() as work:
        r = subprocess.run(["codex", "exec", "--skip-git-repo-check", "--ephemeral", "--ignore-user-config", "--ignore-rules",
                            "-s", "read-only", "-C", work, "-m", MODEL, "-c", 'model_reasoning_effort="medium"',
                            "-o", str(out_file.resolve()), "-"],
                           input=req_file.read_text(encoding="utf-8"), capture_output=True, text=True, timeout=1800)
    if r.returncode:
        sys.exit(f"[실패] codex exec 종료 {r.returncode}: {(r.stderr or r.stdout)[-600:]}")
    if not out_file.exists() or not out_file.read_text(encoding="utf-8").strip():
        sys.exit(f"[실패] 답이 비어 있다: {(r.stderr or r.stdout)[-400:]}")
    text = out_file.read_text(encoding="utf-8")
    out_file.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
    used = [ln for ln in (r.stdout + r.stderr).splitlines() if ln.strip().replace(",", "").isdigit()]
    print(f"{out_file} — 모델 {MODEL}(Codex 계정) · 토큰 {used[-1] if used else '?'} · {time.time() - t0:.0f}초")


def by_api(req_file: Path, out_file: Path):
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


def main():
    args = sys.argv[1:]
    api = args[:1] == ["--api"]
    if api:
        args = args[1:]
    if len(args) != 2:
        sys.exit(__doc__)
    (by_api if api else by_codex)(Path(args[0]), Path(args[1]))


if __name__ == "__main__":
    main()
