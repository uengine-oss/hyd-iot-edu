"""UTC time helpers and the simulation speed every service reads the same way."""
import math
import os
from datetime import datetime, timezone, timedelta


def now() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return to_iso(now())


def to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def parse_iso(s: str) -> datetime:
    """ISO 8601 text -> aware UTC datetime. A value without an offset is read as UTC (the process's own stored times).
    Anything but text is a ValueError (not AttributeError), so every caller's `except ValueError` covers bad input."""
    if not isinstance(s, str):
        raise ValueError(f"ISO time text required, got {type(s).__name__}")
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


#: 학생 화면의 시각은 한국 시각이다(포털이 브라우저 시간대로 적는다 — 수업 PC 는 한국). 서버가 문장 속에 시각을 넣을 때도 같은 시각으로 적는다
#: (2026-11-25 감사: 「11-24 10:57」(UTC)이 바로 옆 처리 건 시각 「오후 08:37」(한국)보다 앞서 보여 최고 유온이 사건 전에 난 것처럼 읽혔다)
KOREA = timezone(timedelta(hours=9))


def korea_text(value) -> str:
    """시각(ISO 글 · datetime) → 문장에 넣는 한국 시각 「MM-DD HH:MM」. 읽을 수 없는 값은 받은 글 그대로(지어내지 않는다)."""
    try:
        dt = parse_iso(value) if isinstance(value, str) else value.astimezone(timezone.utc)
    except (ValueError, AttributeError):
        return str(value)
    return dt.astimezone(KOREA).strftime("%m-%d %H:%M")


def plus_seconds(dt: datetime, seconds: float) -> datetime:
    return dt + timedelta(seconds=seconds)


def time_scale(env=None) -> float:
    """TIME_SCALE (simulated seconds per wall second). compose passes it to every service that runs simulated time; there is
    no code default, so a service started without it stops with the variable's name instead of silently running at 20x."""
    raw = (os.environ if env is None else env).get("TIME_SCALE")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise ValueError(f"TIME_SCALE must be a number (compose.yaml gives it to this service), got {raw!r}") from None
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"TIME_SCALE must be a finite number above 0, got {raw!r}")
    return value
