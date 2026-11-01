"""워커만 부르는 내부 경로의 공용 확인 — 실행기 인증 파일(_key)과 살아 있는 점유(_claim). 포털 경로에는 붙이지 않는다.
쓰는 곳: 수업 경계 판정(course_policy) · 로컬 중계 관문(course_model)."""
import math
import os
import time
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException


def _key() -> str:
    """워커 인증 파일(compose 가 process · 워커에 같은 자리를 준다 — HYD_WORKER_RUNTIME_KEY_FILE 한 곳)."""
    path = os.getenv("HYD_WORKER_RUNTIME_KEY_FILE")
    if not path:
        raise HTTPException(503, "실행 연결 인증 파일 자리(HYD_WORKER_RUNTIME_KEY_FILE)가 설정되지 않았습니다")
    key_file = Path(path)
    try:
        key = key_file.read_text(encoding="utf-8").strip()
    except OSError:
        raise HTTPException(503, "실행 연결 인증 파일이 준비되지 않았습니다") from None
    if len(key) < 32:
        raise HTTPException(503, "실행 연결 인증 파일이 올바르지 않습니다")
    return key


def _claim(runtime, body):
    tenant = body.get("tenant_id")
    if tenant != runtime.tenant_id:
        raise HTTPException(403, "실행 연결의 교육 공간이 일치하지 않습니다")
    row = runtime.repo.get_workitem(str(body.get("todo_id") or ""))
    consumer = body.get("consumer")
    if not row or row.get("tenant_id") != tenant or not consumer or row.get("consumer") != consumer or \
            row.get("status") != "IN_PROGRESS" or row.get("draft_status") != "STARTED":
        raise HTTPException(409, "현재 담당 실행기가 시작한 단계에서만 연결할 수 있습니다")
    lease = row.get("lease_until")
    try:
        if isinstance(lease, str) and ('T' in lease or 'Z' in lease):
            lease = datetime.fromisoformat(lease.replace('Z', '+00:00'))
        if isinstance(lease, datetime) and lease.tzinfo is None:
            raise ValueError('lease timezone missing')
        until = lease.timestamp() if isinstance(lease, datetime) else float(lease)
        if not math.isfinite(until):
            raise ValueError('invalid lease')
    except (TypeError, ValueError):
        raise HTTPException(409, "현재 실행 단계의 유효한 임대 시간이 없습니다") from None
    if until <= time.time():
        raise HTTPException(409, "현재 실행 단계의 임대 시간이 만료되었습니다")
    return row
