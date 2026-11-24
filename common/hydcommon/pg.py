"""PostgreSQL 연결을 맺는 한 곳 — 업무 DB · 시계열 DB 에 연결하는 서비스 코드는 이 connect 를 지난다. 예외: 설비 기록 저장기
(it/connect-sink/app/main.py)는 비동기 연결(psycopg.AsyncConnection.connect)을 스스로 맺고 끊기면 자기 고리에서 다시 맺는다.

2026-11-23 14:11 포털의 GET /api/todolist/<id> 가 raw 500 으로 끝났다 — 호스트 망이 잠깐 늦어 연결 한 번이 시간 초과였고(업무 DB 는
재시작 0, 바로 뒤 0.01초에 닿음) 다시 맺어 보지 않았다. 같은 꼴은 2026-10-07(process A108 · A120)에도 있었다. 연결이 맺어지기 전에는
문장을 하나도 보내지 않았으므로 다시 맺어도 같은 일이 두 번 실행되지 않는다. 그래서 맺는 순간의 일시 오류만 여기서 다시 맺어 보고,
그래도 안 되면 학생이 읽는 문장이 든 DbUnreachable 로 실패한다. 맺어진 뒤의 오류(문장 실행 중)는 여기를 지나지 않으므로 다시 하지 않는다.

예산의 근거 — 포털의 읽기 요청은 8초 뒤 스스로 끊는다(it/portal/www/app.js requestJ). 그 안에 「닿지 않는다」는 답(503)이 가야 하므로
한 번의 연결 기다림은 3초(전에는 5초, 평소 연결은 0.01초), 다 합쳐 7초다: 시간 초과로 실패하면 3 + 0.3 + 3 = 6.3초에 두 번,
바로 거절되면(망 닿지 않음 · 연결 거부) 0.3 · 0.7 · 1.5초 쉬며 2.5초 동안 네 번 맺어 보고 그친다.
서버가 답했지만 이 연결을 받지 않은 것(계정 · 암호가 틀림, 없는 DB · 계정 — REFUSALS)은 다시 맺어도 같아 다시 시도하지 않고 그 까닭을 말하는
DbRefused 로 곧장 실패한다(전에는 2.5초 동안 네 번 다시 한 뒤 「지금 연결되지 않습니다. 잠시 뒤 다시 해 보세요」만 보였다).
백그라운드 고리(process 의 _alert_policy_retrying · _receive_retrying · instance_mode.retry_startup, enterprise-sim 의 시작 기다림)는
이 위에서 저마다 더 길게 다시 시도한다 — 그 고리의 한 번이 전의 5초에서 길어야 약 6.3초가 될 뿐이다.
"""
import logging
import time

import psycopg

#: 일시 장애로 보는 오류(연결 · 잠금 · 시간 초과) — 이 기준은 여기 한 곳(process 의 기동 다시 시도, enterprise-sim 의 503 이 같이 쓴다)
TRANSIENT: tuple = (psycopg.OperationalError, psycopg.InterfaceError)
#: 서버가 답했지만 이 연결을 받지 않았다(다시 맺어도 같다) — 서버가 보낸 FATAL 문장의 낱말(모두 들어 있어야 한다) → 학생이 읽는 까닭.
#: psycopg 3.3 은 세션이 열리기 전의 실패에 SQLSTATE 를 싣지 않는다(2026-11-24 이 PC 업무 DB 실측 — 틀린 암호 · 없는 계정 · 없는 DB 모두
#: sqlstate None) — 그래서 이 시스템의 서버(Supabase · TimescaleDB 의 PostgreSQL, 영어로 말한다)가 쓰는 문장으로 가른다. 서버가 일시 장애로 내는
#: FATAL(the database system is starting up · too many clients already 등)은 여기 없다 — 그런 것은 전과 같이 다시 맺어 본다.
REFUSALS = (
    (('password authentication failed',), '계정 또는 암호가 맞지 않습니다'),      # 28P01 — 없는 계정도 서버가 이 문장으로 숨긴다
    (('database "', 'does not exist'), '연결하려는 데이터베이스가 없습니다'),        # 3D000
    (('role "', 'does not exist'), '연결하려는 계정이 없습니다'),                    # 28000(암호 없이 받는 설정에서)
    (('no pg_hba.conf entry',), '이 주소 · 계정의 연결을 받지 않게 설정돼 있습니다'),  # 28000
    (('is not permitted to log in',), '그 계정은 로그인할 수 없게 돼 있습니다'),     # 28000
    (('permission denied for database',), '그 계정에는 이 데이터베이스에 연결할 권한이 없습니다'),   # 42501
)
CONNECT_TIMEOUT_S = 3
CONNECT_BUDGET_S = 7.0
CONNECT_PAUSES_S = (0.3, 0.7, 1.5)
log = logging.getLogger("hyd.pg")


def unreachable_text(name: str) -> str:
    """그래도 닿지 않을 때 학생이 읽는 문장. name: 화면이 부르는 이름 — 「… DB」로 끝난다(업무 DB · 시계열 DB, 조사가 그 끝소리에 맞춰 있다)."""
    return f'{name}에 지금 연결되지 않습니다. 잠시 뒤 다시 해 보세요. 계속 이러면 시작 파일을 다시 실행하거나, 점검 파일로 {name}가 켜져 있는지 확인하세요.'


def refused_text(name: str, reason: str) -> str:
    """서버가 연결을 받지 않았을 때 학생이 읽는 문장(name 은 unreachable_text 와 같다). 다시 해도 같으므로 「잠시 뒤」를 말하지 않는다."""
    return (f'{name}가 이 연결을 받지 않았습니다 — {reason}. 다시 해도 같습니다. 시작 파일을 다시 실행하고, 그래도 같으면 이 문장을 '
            f'강사에게 알려 주세요.')


def refusal(exc: BaseException) -> str | None:
    """연결 실패가 서버의 거절(REFUSALS)이면 그 까닭, 아니면(닿지 않음 · 시간 초과 · 일시 장애) None."""
    low = str(exc).lower()
    return next((reason for words, reason in REFUSALS if all(w in low for w in words)), None)


class DbUnreachable(psycopg.OperationalError):
    """DB 연결을 예산 안에 맺지 못했다. psycopg.OperationalError 의 한 갈래라 일시 장애를 다시 시도하는 고리는 전과 같이 잡는다.
    detail = 학생이 읽는 문장, __cause__ = 마지막 연결 오류(까닭을 원문으로 가르는 쪽 — hydcommon.fabric.failure_reason — 이 본다)."""

    def __init__(self, detail: str, cause: BaseException):
        super().__init__(f"{detail} ({type(cause).__name__}: {str(cause)[:300]})")
        self.detail = detail


class DbRefused(DbUnreachable):
    """서버가 답했지만 이 연결을 받지 않았다(REFUSALS) — 다시 맺지 않았다. DbUnreachable 의 한 갈래라 그것을 다루는 자리(answer_unreachable 의 503,
    까닭을 원문으로 가르는 hydcommon.fabric.failure_reason, 백그라운드 고리)가 그대로 받고, detail 은 참 까닭(refused_text)이다."""


def connect(dsn: str, *, name: str = '업무 DB', **options):
    """PostgreSQL 연결 하나. options 는 psycopg.connect 에 그대로 간다(autocommit · row_factory · options …). 연결 기다림은 호출자가
    정하지 않는다."""
    started, pauses, attempt = time.monotonic(), iter(CONNECT_PAUSES_S), 0
    while True:
        attempt += 1
        try:
            connection = psycopg.connect(dsn, connect_timeout=CONNECT_TIMEOUT_S, **options)
        except TRANSIENT as exc:
            if (reason := refusal(exc)) is not None:
                log.error("%s refused the connection (attempt %d): %s", name, attempt, str(exc)[:300])
                raise DbRefused(refused_text(name, reason), exc) from exc
            pause = next(pauses, None)
            if pause is None or time.monotonic() - started + pause + CONNECT_TIMEOUT_S > CONNECT_BUDGET_S:
                log.error("%s unreachable after %d connection attempts / %.1f s: %s: %s", name, attempt,
                          time.monotonic() - started, type(exc).__name__, str(exc)[:300])
                raise DbUnreachable(unreachable_text(name), exc) from exc
            log.warning("%s connection attempt %d failed (%s); retrying in %.1f s", name, attempt, type(exc).__name__, pause)
            time.sleep(pause)
            continue
        if attempt > 1:
            log.info("%s reachable on connection attempt %d (%.1f s)", name, attempt, time.monotonic() - started)
        return connection


def answer_unreachable(app) -> None:
    """FastAPI 앱이 DbUnreachable(DbRefused 포함 — detail 이 참 까닭)을 raw 500 대신 503 + {"detail": 학생이 읽는 문장} 으로 답하게 한다 —
    경로마다가 아니라 앱 한 곳.
    연결이 맺어진 뒤의 오류는 DbUnreachable 이 아니라서 여기로 오지 않고 전과 같이 그 서비스가 다룬다."""
    from fastapi.responses import JSONResponse

    async def unreachable(request, exc):
        log.warning("%s %s: database unreachable — answering 503", request.method, request.url.path)
        return JSONResponse(status_code=503, content={"detail": exc.detail})
    app.add_exception_handler(DbUnreachable, unreachable)
