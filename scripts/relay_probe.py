"""강의 중계 연결 확인 — process 컨테이너 안에서 돈다. 시작 8단계와 점검이 `docker compose exec -T process python - [--call]` 로 이 파일을 넘긴다.

process 의 중계 관문(it/process/procsvc/course_model.py)이 실제로 쓰는 값 — 컨테이너 환경의 LLM_RELAY_URL · LLM_API_KEY — 과
수업 모델(같은 컨테이너의 GET /api/course-access 의 model)로, 관문의 주소 규칙(course_model.relay_url)과 관문의 HTTP 클라이언트
(course_model.relay_client — 믿는 인증서 · 프록시 설정까지 같다)를 그대로 써서(사본 없음) 관문과 같은 머리글(x-api-key)로 묻는다.
그래서 .env 를 셸 · PowerShell 이 따로 해석하지 않고 컨테이너가 받은 값 그대로를 재고, 실제 AI 호출이 실패할 망에서는 확인도 실패한다.
키는 출력하지 않는다.
  기본   GET <주소>/v1/models — 키가 받아들여지고 수업 모델이 목록에 있는가(비용 없음, 중계가 쉬다 깨면 첫 연결이 느려 세 번까지)
  --call POST <주소>/v1/messages — 수업 모델로 아주 짧은 답 하나(관문이 부르는 바로 그 길)
출력: 한 줄 JSON {"ok": 참/거짓, "code": 짧은 판정, "message": 학생이 읽는 문장}. 종료 코드 0 = 연결됨, 1 = 실패.
표준 라이브러리 + process 이미지의 procsvc · httpx(작업 폴더 /srv — `python -` 의 sys.path 첫 칸)만 쓴다.
"""
from __future__ import annotations

import asyncio
import json
import os
import ssl
import sys
import time
import urllib.request

import httpx

from procsvc.course_ledger import Denied
from procsvc.course_model import relay_client, relay_url

PROCESS = 'http://127.0.0.1:8080'
OFFLINE = '그동안 포털의 AI 단계(판단 · 제안, 에이전트에게 질문)만 막히고 나머지 실습은 그대로 할 수 있습니다.'
KEY_LINE = '.env 의 LLM_API_KEY= 뒤에 수업에서 받은 키를 앞뒤 공백 · 따옴표 없이 넣었는지 확인하고 시작 파일을 다시 실행하세요.'
REFUSED = {
    401: '강의 중계가 이 키를 받지 않습니다. ' + KEY_LINE,
    403: '이 키가 막혔거나 수업 모델을 쓸 수 없습니다. 강사에게 알려 주세요. ' + OFFLINE,
    404: '강의 중계 주소가 맞지 않습니다. 강사에게 알려 주세요. ' + OFFLINE,
    429: '강의 중계가 잠시 바쁘거나 이 키의 사용 한도에 닿았습니다. 1분 뒤 다시 해 보고, 계속되면 강사에게 알려 주세요. ' + OFFLINE,
}
UNTRUSTED = ('강의 중계의 보안 인증서를 확인하지 못해 연결하지 않았습니다 — 이 PC의 인터넷(학교 · 회사망 등)이 암호화 연결을 중간에서 다시 '
             '서명하는 것 같습니다. 이 인터넷에서는 AI 단계가 실제로 돌지 않습니다. 다른 인터넷(예: 휴대폰 핫스팟)에 연결한 뒤 시작 파일을 다시 '
             '실행하거나 강사에게 알려 주세요. ' + OFFLINE)


def result(ok: bool, code: str, message: str) -> dict:
    return {'ok': ok, 'code': code, 'message': message}


def url_problem(url: str) -> str | None:
    """관문(course_model.relay_url)이 받아들이지 않는 주소면 그 까닭."""
    try:
        relay_url(url)
    except Denied:
        return '강의 중계 주소가 비었거나 받을 수 없는 주소입니다(https, 또는 이 PC 안 주소만). 강사에게 알려 주세요. ' + OFFLINE
    return None


def certificate_refused(exc: BaseException | None) -> bool:
    """연결 실패의 원인 사슬에 인증서 확인 실패가 있는가 — 다시 물어도 같은 결과라 바로 판정한다."""
    while exc is not None:
        if isinstance(exc, ssl.SSLCertVerificationError):
            return True
        exc = exc.__cause__ or exc.__context__
    return False


def ask(base: str, key: str, model: str, *, call: bool = False, attempts: int = 3, timeout: float = 30,
        wait: float = 5, sleep=time.sleep) -> dict:
    """주소 검사를 통과한 base 로 관문의 클라이언트(relay_client)로 묻는다. 네트워크 · 5xx 는 세 번까지, 401 · 403 · 404 · 429 와
    인증서 확인 실패는 바로 판정."""
    headers = {'x-api-key': key, 'Authorization': f'Bearer {key}', 'anthropic-version': '2023-06-01',
               'Content-Type': 'application/json'}
    if call:
        method, path = 'POST', '/v1/messages'
        body = json.dumps({'model': model, 'max_tokens': 16, 'messages': [{'role': 'user', 'content': 'Reply with exactly: OK'}]}).encode()
    else:
        method, path, body = 'GET', '/v1/models', None

    async def once() -> tuple[int, bytes]:
        async with relay_client(timeout) as client:
            response = await client.request(method, base.rstrip('/') + path, headers=headers, content=body)
            return response.status_code, response.content

    last = '응답 없음'
    for attempt in range(1, attempts + 1):
        try:
            status, raw = asyncio.run(once())
            if status == 200:
                data = json.loads(raw or b'{}')
                break
            if status in REFUSED:
                return result(False, str(status), REFUSED[status])
            last = f'응답 {status}'
        except httpx.RequestError as exc:         # 연결 · 시간 초과 · 깨진 응답(관문이 relay_failed 로 거절하는 것들)
            if certificate_refused(exc):
                return result(False, 'tls', UNTRUSTED)
            last = type(exc).__name__
        except ValueError as exc:                # 200 인데 JSON 이 아님 — 중계가 깨어나는 중일 수 있어 다시 묻는다
            last = type(exc).__name__
        if attempt < attempts:
            sleep(wait)
    else:
        return result(False, 'unreachable', f'강의 중계에 닿지 않습니다({last}). 인터넷 연결을 확인하고 시작 파일을 다시 실행하세요. ' + OFFLINE)
    if call:
        text = ''.join(part.get('text', '') for part in data.get('content') or [] if isinstance(part, dict)).strip()
        if not text:
            return result(False, 'empty', f'강의 중계가 수업 모델({model})의 답을 비워 보냈습니다. 강사에게 알려 주세요. ' + OFFLINE)
        return result(True, 'answered', f'연결됨 · 수업 모델 {model} · 답 「{text[:40]}」')
    listed = {row.get('id') for row in data.get('data') or [] if isinstance(row, dict)}
    if model not in listed:
        return result(False, 'model', f'이 키로는 수업 모델({model})을 쓸 수 없습니다. 강사에게 알려 주세요. ' + OFFLINE)
    return result(True, 'listed', f'강의 중계 연결됨 · 수업 모델 {model}')


def course_model(process: str = PROCESS, timeout: float = 10) -> str:
    with urllib.request.urlopen(process + '/api/course-access', timeout=timeout) as response:
        model = json.loads(response.read()).get('model')
    if not model:
        raise ValueError('수업 모델 이름이 비었습니다')
    return model


def main(argv: list[str], environ=os.environ) -> int:
    if argv[1:] not in ([], ['--call']):
        print(json.dumps(result(False, 'usage', '사용: relay_probe.py [--call]'), ensure_ascii=False))
        return 2
    key, url = environ.get('LLM_API_KEY', '').strip(), environ.get('LLM_RELAY_URL', '').strip()
    if not key:
        out = result(False, 'no-key', '키가 없어 강의 중계를 부르지 않습니다. ' + KEY_LINE)
    elif problem := url_problem(url):
        out = result(False, 'url', problem)
    else:
        try:
            model = course_model()
        except (OSError, ValueError) as exc:
            out = result(False, 'course', f'처리 엔진에서 수업 모델 이름을 읽지 못했습니다({type(exc).__name__}). 시작 파일을 다시 실행하세요.')
        else:
            out = ask(url, key, model, call=argv[1:] == ['--call'])
    print(json.dumps(out, ensure_ascii=False))
    return 0 if out['ok'] else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
