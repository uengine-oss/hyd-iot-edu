"""언제: 다 쓴 대본(이론 · 실습)을 바깥 모델(OpenAI, 기본 gpt-6.2-astra)에 적대 검토와 윤문 제안으로 보낼 때(대본 「함정」 바깥 윤문 도구 줄).
받은 제안은 그대로 붙여 넣지 않는다. 작업자가 골라 그 대목을 앞뒤와 이어 다시 쓴다.

쓰는 법(저장소 루트에서):
  OPENAI_KEY_FILE=<키 파일> <py> workspace/강의제작/제작도구/검사/바깥검토.py \
      --지시 <지시.md> [--사실 <사실.md>] --글 <글.md> --출력 <폴더> [--모델 gpt-6.2-astra]

- 키는 환경변수 OPENAI_API_KEY 또는 OPENAI_KEY_FILE(키 한 줄, 또는 `이름=값` 줄이 든 파일)로만 받는다.
  키 값과 키 파일 경로는 출력하거나 파일에 적지 않는다.
- 지시와 사실은 instructions로, 글은 input으로 Responses API(https://api.openai.com/v1/responses)에 보낸다.
  사실은 「앞에서 배운 것 · 바꾸면 안 되는 이름」을 적은 한 장이다.
- 출력 폴더에 요청.json(키 없음) · 응답.json · 결과.md를 쓰고, 이미 있으면 멈춘다(덮어쓰지 않는다).
- 유료 호출이다. 보내기 전에 글자 수를 찍고, 끝나면 응답의 토큰 수를 찍는다.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

URL = 'https://api.openai.com/v1/responses'


def key():
    value = os.environ.get('OPENAI_API_KEY', '').strip()
    if value:
        return value
    path = os.environ.get('OPENAI_KEY_FILE', '').strip()
    if not path:
        sys.exit('바깥검토: 키가 없다 — 환경변수 OPENAI_API_KEY 또는 OPENAI_KEY_FILE을 준다.')
    p = Path(path)
    if not p.is_file():
        sys.exit('바깥검토: OPENAI_KEY_FILE이 가리키는 파일이 없다.')
    lines = [x.strip() for x in p.read_text(encoding='utf-8-sig').splitlines() if x.strip() and not x.strip().startswith('#')]
    for line in lines:
        if '=' in line:
            name, val = line.split('=', 1)
            if name.strip() in ('OPENAI_API_KEY', 'OPENAI_KEY'):
                return val.strip().strip('"').strip("'")
    if len(lines) == 1 and '=' not in lines[0]:
        return lines[0]
    sys.exit('바깥검토: 키 파일에서 키를 찾지 못했다 — 키 한 줄이거나 OPENAI_API_KEY=… 줄이어야 한다.')


def read(path, what):
    p = Path(path)
    if not p.is_file():
        sys.exit(f'바깥검토: {what} 파일이 없다 — {path}')
    text = p.read_text(encoding='utf-8-sig').strip()
    if not text:
        sys.exit(f'바깥검토: {what} 파일이 비었다 — {path}')
    return text


def output_text(resp):
    parts = []
    for item in resp.get('output', []):
        if item.get('type') != 'message':
            continue
        for c in item.get('content', []):
            if c.get('type') == 'output_text':
                parts.append(c.get('text', ''))
    return '\n'.join(parts).strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--지시', required=True)
    ap.add_argument('--사실')
    ap.add_argument('--글', required=True)
    ap.add_argument('--출력', required=True)
    ap.add_argument('--모델', default='gpt-6.2-astra')
    a = ap.parse_args()

    out = Path(a.출력)
    for name in ('요청.json', '응답.json', '결과.md'):
        if (out / name).exists():
            sys.exit(f'바깥검토: {out / name}이 이미 있다 — 새 폴더를 준다(덮어쓰지 않는다).')
    instructions = read(a.지시, '지시')
    if a.사실:
        instructions += '\n\n## 바꾸면 안 되는 것과 앞에서 배운 것\n\n' + read(a.사실, '사실')
    text = read(a.글, '글')
    body = {'model': a.모델, 'instructions': instructions, 'input': text}
    secret = key()
    print(f'바깥검토: {a.모델}에 보냄 — 지시 {len(instructions):,}자 · 글 {len(text):,}자', flush=True)

    req = urllib.request.Request(URL, json.dumps(body, ensure_ascii=False).encode('utf-8'),
                                 {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + secret})
    try:
        with urllib.request.urlopen(req, timeout=900) as r:
            raw = r.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        sys.exit(f'바깥검토: HTTP {e.code} — {e.read().decode("utf-8", "replace")[:2000]}')
    except (urllib.error.URLError, TimeoutError) as e:
        sys.exit(f'바깥검토: 연결 실패 — {e}. 크레딧이 차감됐는지 확인하기 전에는 다시 보내지 않는다.')
    resp = json.loads(raw)
    result = output_text(resp)
    if not result:
        sys.exit(f'바깥검토: 응답에 글이 없다 — 상태 {resp.get("status")}, 응답 앞부분 {raw[:1500]}')

    out.mkdir(parents=True, exist_ok=True)
    (out / '요청.json').write_text(json.dumps(body, ensure_ascii=False, indent=1), encoding='utf-8', newline='')
    (out / '응답.json').write_text(json.dumps(resp, ensure_ascii=False, indent=1), encoding='utf-8', newline='')
    (out / '결과.md').write_text(result + '\n', encoding='utf-8', newline='')
    u = resp.get('usage') or {}
    print(f'바깥검토: 받음 — 상태 {resp.get("status")} · 입력 {u.get("input_tokens")} · 출력 {u.get("output_tokens")} 토큰 · 결과 {out / "결과.md"}')


if __name__ == '__main__':
    main()
