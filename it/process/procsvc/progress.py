"""오래 걸리는 요청의 진행 기록 — 요청 하나가 끝나기 전에 「지금 어느 단계인가」를 화면이 읽는다(블랙박스 금지).

쓰는 쪽(판단 채점 실행 · 에이전트 시험 비교 · 출발본 불러오기와 기준으로 되돌리기 · 도구 서버 연결 검사)은 요청 본문의 request_id
(화면이 만든 UUID)로 기록을 열고, **실제 일의 경계에서만** 단계의 시작 · 끝 · 실패를 적는다. 퍼센트 · 타이머로 흉내 낸 진행은 없다.

    work = progress.tracked(body.get("request_id"), "config_reset", lambda p: reset_all(…, progress=p))   # 요청을 받은 자리에서 기록을 연다
    await loop.run_in_executor(None, work)     # 일이 도는 자리(실행기 스레드) — 예외로 끝나면 하는 중이던 단계와 기록이 실패로 남는다
    …일하는 함수 안에서:
        p.plan([("check", "진행 중인 처리 건 확인"), ("item:0", "쿨러 성능 저하")])   # 단계는 알게 된 때에 뒤에 붙인다
        p.start("check"); …; p.done("check", "막는 처리 건 없음")

    GET /api/progress/{request_id} → {state: none | running | done | failed, steps: [{key, label, state: wait | run | ok | fail, note,
                                      started_at, ended_at}], error, …}
        none = 이 번호의 기록이 없다(요청이 아직 닿지 않았거나, 끝난 뒤 KEEP_DONE_S 가 지나 지워졌다). 404 가 아니다 — 화면은 요청을 보낸
        직후부터 읽는다.

request_id 없이 온 요청은 기록 없이 돈다(begin 이 아무것도 적지 않는 SILENT 를 돌려준다 — 부르는 코드는 갈라 쓰지 않는다).
기록은 이 프로세스의 메모리에만 있다(process 는 한 프로세스다). 일은 실행기 스레드에서, 읽기는 이벤트 루프에서 하므로 모든 읽기 · 쓰기는
잠금 하나(_LOCK) 안에서 한다. 새지 않게: 끝난 기록은 KEEP_DONE_S 뒤, 손대지 않은 기록은 STALE_S 뒤 지우고, 기록 수는 MAX_RECORDS(넘으면 끝난
것부터, 그다음 오래된 것부터 지운다), 한 기록의 단계 수는 MAX_STEPS 까지다.
"""
from __future__ import annotations

import threading
import time
import uuid
from datetime import datetime, timezone

KEEP_DONE_S = 300.0          # 끝난 기록을 남겨 두는 시간 — 화면이 마지막 상태를 읽고도 남는다
STALE_S = 3600.0             # 이만큼 아무도 적지 않은 기록은 버려진 것으로 본다(요청이 실행기에 닿기 전에 죽은 경우)
MAX_RECORDS = 64
MAX_STEPS = 400
NOTE_CHARS = 300
NONE_TEXT = "이 요청의 진행 기록이 없습니다 — 요청이 아직 서버에 닿지 않았거나, 끝난 지 오래되어 지워졌습니다"

_LOCK = threading.Lock()
_RECORDS: dict[str, dict] = {}        # 넣은 순서 = 오래된 순서
clock = time.monotonic                # 만료를 재는 시계(시험이 바꿔 끼운다)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _rid(request_id) -> str:
    """request_id 는 UUID 여야 한다 — 아무 글자나 받아 기록 열쇠로 쓰지 않는다."""
    try:
        return str(uuid.UUID(str(request_id)))
    except (ValueError, AttributeError, TypeError):
        from fastapi import HTTPException
        raise HTTPException(400, "request_id: 화면이 만든 요청 번호(UUID)여야 합니다") from None


def reason_of(exc: BaseException) -> str:
    """예외에서 사람이 읽을 사유 한 줄(이 서비스의 예외들은 reason · message · detail 에 사유를 싣는다)."""
    for attr in ("reason", "message", "detail"):
        v = getattr(exc, attr, None)
        if isinstance(v, dict):
            v = v.get("reason")
        if isinstance(v, str) and v.strip():
            return v.strip()
    args = getattr(exc, "args", ())
    return (str(args[0]) if args else "") or type(exc).__name__


def _sweep(now: float) -> None:
    for rid in [r for r, rec in _RECORDS.items()
                if (rec["ended"] is not None and now - rec["ended"] > KEEP_DONE_S) or now - rec["touched"] > STALE_S]:
        del _RECORDS[rid]


def _evict() -> None:
    while len(_RECORDS) > MAX_RECORDS:
        ended = next((r for r, rec in _RECORDS.items() if rec["ended"] is not None), None)
        del _RECORDS[ended if ended is not None else next(iter(_RECORDS))]


class Progress:
    """진행 기록 하나에 적는 손잡이. record 가 없으면(SILENT) 아무것도 적지 않는다."""

    def __init__(self, record: dict | None):
        self._r = record

    def _edit(self, change) -> None:
        if self._r is None:
            return
        with _LOCK:
            change(self._r)
            self._r["touched"], self._r["updated_at"] = clock(), _now()

    @staticmethod
    def _step(rec: dict, key: str) -> dict:
        for s in rec["steps"]:
            if s["key"] == key:
                return s
        raise KeyError(f"진행 기록에 없는 단계입니다: {key}")

    @staticmethod
    def _set(step: dict, state: str, note, label) -> None:
        now = _now()
        if state == "run":
            step.update(started_at=now, ended_at=None)
        else:
            step.update(started_at=step["started_at"] or now, ended_at=now)
        step["state"] = state
        if note is not None:
            step["note"] = str(note)[:NOTE_CHARS]
        if label is not None:
            step["label"] = str(label)[:NOTE_CHARS]

    def plan(self, steps) -> None:
        """단계를 뒤에 붙인다: [(key, label), …]. 같은 열쇠 두 번 · MAX_STEPS 초과는 ValueError."""
        def change(rec):
            have = {s["key"] for s in rec["steps"]}
            for key, label in steps:
                if key in have:
                    raise ValueError(f"진행 기록에 같은 단계가 두 번 있습니다: {key}")
                if len(rec["steps"]) >= MAX_STEPS:
                    raise ValueError(f"진행 단계가 너무 많습니다(최대 {MAX_STEPS}개) — 한 번에 하는 일을 줄이세요")
                have.add(key)
                rec["steps"].append({"key": key, "label": str(label)[:NOTE_CHARS], "state": "wait", "note": "", "started_at": None, "ended_at": None})
        self._edit(change)

    def start(self, key: str, note=None, *, label=None) -> None:
        self._edit(lambda rec: self._set(self._step(rec, key), "run", note, label))

    def done(self, key: str, note=None, *, label=None) -> None:
        self._edit(lambda rec: self._set(self._step(rec, key), "ok", note, label))

    def fail(self, key: str, note=None) -> None:
        self._edit(lambda rec: self._set(self._step(rec, key), "fail", note, None))

    def note(self, key: str, note) -> None:
        """하는 중인 단계의 한 줄(무엇을 하고 있는지 · 몇 번째인지)을 바꾼다."""
        self._edit(lambda rec: self._step(rec, key).update(note=str(note)[:NOTE_CHARS]))

    def fail_running(self, reason) -> None:
        """하는 중이던 단계를 모두 실패로(그 일을 하다 멈췄다)."""
        def change(rec):
            for s in rec["steps"]:
                if s["state"] == "run":
                    self._set(s, "fail", reason, None)
        self._edit(change)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        def change(rec):
            if exc is not None:
                reason = reason_of(exc)[:NOTE_CHARS]
                for s in rec["steps"]:
                    if s["state"] == "run":
                        self._set(s, "fail", reason, None)
                rec.update(state="failed", error=reason)
            else:
                rec["state"] = "done"
            rec["ended"], rec["ended_at"] = clock(), _now()
        self._edit(change)
        return False


SILENT = Progress(None)


def begin(request_id, kind: str, steps=()) -> Progress:
    """요청의 진행 기록을 연다. request_id 가 없으면 SILENT. UUID 가 아니면 400, 이미 있는 번호면 409."""
    if request_id is None or request_id == "":
        return SILENT
    rid = _rid(request_id)
    now = clock()
    with _LOCK:
        _sweep(now)
        if rid in _RECORDS:
            from fastapi import HTTPException
            raise HTTPException(409, "같은 요청 번호의 진행 기록이 이미 있습니다 — 같은 요청을 두 번 보냈습니다")
        rec = {"request_id": rid, "kind": kind, "state": "running", "error": None, "steps": [], "started_at": _now(), "updated_at": _now(),
               "ended_at": None, "touched": now, "ended": None}
        _RECORDS[rid] = rec
        _evict()
    p = Progress(rec)
    p.plan(steps)
    return p


def tracked(request_id, kind: str, work, steps=()):
    """기록을 열고(request_id 가 없으면 SILENT), 그 기록 안에서 work(progress) 를 돌릴 함수를 돌려준다. 네 동작의 HTTP 라우트가 쓰는 한 길:
    기록 열기(400 · 409)는 요청을 받은 자리에서, 일과 끝 표시(끝 · 실패)는 돌려준 함수를 부르는 자리(실행기 스레드)에서 한다."""
    p = begin(request_id, kind, steps)

    def run():
        with p:
            return work(p)
    return run


def read(request_id) -> dict:
    rid = _rid(request_id)
    with _LOCK:
        _sweep(clock())
        rec = _RECORDS.get(rid)
        if rec is None:
            return {"request_id": rid, "state": "none", "kind": None, "error": None, "steps": [], "started_at": None, "updated_at": None,
                    "ended_at": None, "note": NONE_TEXT}
        out = {k: rec[k] for k in ("request_id", "kind", "state", "error", "started_at", "updated_at", "ended_at")}
        out["steps"] = [dict(s) for s in rec["steps"]]
        return out


def register(app) -> None:
    @app.get("/api/progress/{request_id}")
    async def progress_of(request_id: str):
        return read(request_id)
