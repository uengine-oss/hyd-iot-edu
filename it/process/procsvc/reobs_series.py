"""A161-G3: the recovery tag's values during the re-observation window, kept small enough to live on the Incident.

The verdict used to keep one number ("TS1 51.6 < 55.0" in the history note), so the case record could not show whether the
value fell steadily, crossed the line at the last second, or bounced. The timer now reads the window's 1 s rows from
TimescaleDB (tag_1s) and keeps at most MAX_POINTS of them: each point is the mean of an equal slice of the window, stamped with
the slice's last time, and the window's real min · max · first · last are kept beside it so sampling never hides an extreme.

Shape (Incident.reobs_series → to_dict()["reobsSeries"], also the work-order re-observation event's reading.series):
    {"tag": "TS1", "op": "<", "limit": 55.0, "criterion": "TS1 < 55.0", "from": iso, "to": iso,
     "samples": 45, "points": [{"t": iso, "v": 53.1}, …], "min": …, "max": …, "first": …, "last": …,
     "inside_last": true, "inside_share": 0.8, "step_s": 1.0, "after": "command" | "work_order", "extensions": 0}
A window that could not be read (TimescaleDB down, no window start) is still recorded — samples 0 with `error` saying why
(unavailable) — so "no values" and "values not read" never look the same on the case record. The verdict does not wait for it.
Pure functions only; the I/O (main.tag_series) is the caller's.
"""
from __future__ import annotations

from typing import Iterable

MAX_POINTS = 60
MAX_ROWS = 7200          #: rows read for one window at most (the window is 45 s at 20×, 900 s at 1×, plus extensions)


def inside(value: float | None, op: str, limit: float) -> bool:
    if value is None:
        return False
    return value < limit if op == "<" else value >= limit if op == ">=" else value > limit if op == ">" else value <= limit


def sample(rows: list[tuple[str, float]], max_points: int = MAX_POINTS) -> list[dict]:
    """[(iso, value)] oldest first → at most max_points {"t", "v"}; the last point is always the last real reading."""
    if len(rows) <= max_points:
        return [{"t": t, "v": round(float(v), 4)} for t, v in rows]
    out = []
    n = len(rows)
    for i in range(max_points):
        lo, hi = i * n // max_points, (i + 1) * n // max_points
        chunk = rows[lo:hi]
        if not chunk:
            continue
        out.append({"t": chunk[-1][0], "v": round(sum(float(v) for _, v in chunk) / len(chunk), 4)})
    out[-1] = {"t": rows[-1][0], "v": round(float(rows[-1][1]), 4)}
    return out


def build(rows: Iterable[tuple[str, float]], *, tag: str, op: str, limit: float, since: str | None, until: str | None,
          after: str, extensions: int = 0, max_points: int = MAX_POINTS) -> dict:
    rows = [(str(t), float(v)) for t, v in rows if v is not None]
    values = [v for _, v in rows]
    series = {"tag": tag, "op": op, "limit": limit, "criterion": f"{tag} {op} {limit}", "from": since, "to": until,
              "samples": len(rows), "points": sample(rows, max_points), "after": after, "extensions": extensions,
              "min": None, "max": None, "first": None, "last": None, "inside_last": False, "inside_share": None,
              "step_s": None}
    if values:
        series.update(min=round(min(values), 4), max=round(max(values), 4), first=round(values[0], 4), last=round(values[-1], 4),
                      inside_last=inside(values[-1], op, limit),
                      inside_share=round(sum(1 for v in values if inside(v, op, limit)) / len(values), 3))
        if len(series["points"]) > 1 and len(rows) > 1:
            series["step_s"] = round(len(rows) / len(series["points"]), 2)     # raw rows per point (1 s rows → seconds per point)
    return series


def unavailable(error: str, *, tag: str, op: str, limit: float, since: str | None, until: str | None, after: str,
                extensions: int = 0) -> dict:
    """The record of a window whose values could not be read: same shape, no points, and the reason."""
    return dict(build([], tag=tag, op=op, limit=limit, since=since, until=until, after=after, extensions=extensions), error=error)


def window_start(history: list[dict]) -> str | None:
    """When the current re-observation began: the last RE_OBSERVING entry of the Incident history."""
    for h in reversed(history or []):
        if h.get("state") == "RE_OBSERVING":
            return h.get("t")
    return None
