"""비밀값 가림 한 곳 — 워커가 남기는 모든 것(처리 기록 · 결과 · 보류 · 도구 원문 · 알림 · 실행 추적 · AI 응답 저장)은 남기기 직전 여기를 지난다.

  hide(value, secrets)   이번 실행이 아는 비밀값(도구 서버 설정의 비밀 · 실행 토큰 · 워커 환경의 비밀)을 그대로 · JSON 이스케이프된 꼴 모두 가린다
  HiddenRepo(repo, …)    업무 DB에 쓰는 메서드의 인자를 hide 한 뒤 넘긴다(Runner 가 점유 하나 동안 이 저장소로만 쓴다)
  excerpt(text, limit)   오류 글: 알려진 값 + 이름 모양(URL 비밀번호 · Bearer · password=…)까지 가리고 길이를 줄인다
가림 표시는 process 쪽과 같은 mcp_secrets.REDACTED 다.
"""
from __future__ import annotations

import json
import os
import re

from procsvc.mcp_secrets import REDACTED, REDACT_MIN

from . import env_guard


def _env_secrets(environ) -> list[str]:
    """워커가 켜질 때(자식 프로세스 환경 정리 전) 보이는 비밀 환경 변수 값 — env_guard 가 지우는 이름 · HYD_SECRET_*."""
    blocked = set(env_guard.secret_keys(environ))
    return [v for k, v in environ.items() if (k in blocked or k.upper().startswith(env_guard.SECRET_PREFIX)) and len(v) >= 8]


ENV_SECRETS = _env_secrets(os.environ)      # main 이 env_guard.scrub 하기 전에 이 모듈을 읽는다(runner → diagnostics)


def secret_forms(values) -> list[str]:
    """가릴 글 조각: 값 그대로, JSON 안에 들어간 꼴, 「Bearer <토큰>」 같은 값의 토큰 조각. 긴 것부터."""
    out = set()
    for value in values or ():
        if not isinstance(value, str) or len(value) < REDACT_MIN:
            continue
        out.add(value)
        out.add(json.dumps(value, ensure_ascii=False)[1:-1])
        out.update(piece for piece in value.split()[1:] if len(piece) >= 8)
    return sorted((f for f in out if len(f) >= REDACT_MIN), key=len, reverse=True)


def hide(value, secrets):
    forms = secret_forms(secrets)
    if not forms:
        return value

    def walk(v):
        if isinstance(v, str):
            for form in forms:
                if form in v:
                    v = v.replace(form, REDACTED)
            return v
        if isinstance(v, dict):
            return {walk(k) if isinstance(k, str) else k: walk(x) for k, x in v.items()}
        if isinstance(v, (list, tuple)):
            return type(v)(walk(x) for x in v)
        return v
    return walk(value)


class HiddenRepo:
    """업무 DB 쓰기의 인자를 가린 뒤 넘긴다. 읽기 · 나머지 메서드는 그대로(같은 저장소 객체)."""
    _WRITES = {'record_events': (0,), 'save_task_result': (1,), 'update_workitem': (0,), 'store_event_payload': (0,),
               'insert_notification': (0,)}

    def __init__(self, repo, secrets: list[str]):
        self._repo, self._secrets = repo, secrets      # secrets 는 실행 중에 늘어난다(실행 토큰) — 같은 목록을 본다

    def __getattr__(self, name):
        target = getattr(self._repo, name)
        positions = self._WRITES.get(name)
        if positions is None:
            return target

        def write(*args, **kwargs):
            args = [hide(a, self._secrets) if i in positions else a for i, a in enumerate(args)]
            if 'payload' in kwargs:
                kwargs['payload'] = hide(kwargs['payload'], self._secrets)
            return target(*args, **kwargs)
        return write


_URL = re.compile(r'(?i)([a-z][a-z0-9+.-]*://)[^\s/@]+:[^\s/@]+@')
_BEARER = re.compile(r'(?i)(\bBearer\s+)[^\s,;"\']+')
_KV = re.compile(r'''(?ix)(\b(?:[a-z0-9_]*(?:password|passwd|secret|token|api_key|apikey)[a-z0-9_]*)["']?\s*[:=]\s*)(?:"[^"]*"|'[^']*'|[^\s,;}]+)''')


def excerpt(value, limit=800, secrets=()):
    text = hide(str(value), list(secrets) + ENV_SECRETS)
    text = _URL.sub(r'\1' + REDACTED + '@', text)
    text = _BEARER.sub(r'\1' + REDACTED, text)
    text = _KV.sub(r'\1' + REDACTED, text)
    if len(text) <= limit:
        return text
    marker = '\n… [중간 생략] …\n'
    head = max(1, (limit - len(marker)) // 4)
    return text[:head] + marker + text[-(limit - len(marker) - head):]
