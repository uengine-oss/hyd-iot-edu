from datetime import datetime, timezone, timedelta


def now() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return to_iso(now())


def to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def parse_iso(s: str) -> datetime:
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def plus_seconds(dt: datetime, seconds: float) -> datetime:
    return dt + timedelta(seconds=seconds)
