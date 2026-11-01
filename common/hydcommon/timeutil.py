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
