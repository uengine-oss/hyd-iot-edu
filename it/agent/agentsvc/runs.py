"""Agent run registry: 읽기 평가 실행(/api/agent/evaluate) 기록 — 실행마다 새 id, 최근 keep 개만 둔다."""
from dataclasses import dataclass, field
from collections import OrderedDict
from threading import RLock

from hydcommon.timeutil import now_iso


@dataclass
class Run:
    id: str
    alert_id: str
    asset: str
    alert: dict
    status: str = "RUNNING"          # RUNNING | EVALUATED (read-only evaluation, no submit) | REJECTED_BY_GUARDRAIL | WITHHELD | FAILED
    started: str = field(default_factory=now_iso)
    ended: str | None = None
    steps: list[dict] = field(default_factory=list)
    card: dict | None = None
    error: str | None = None
    evaluation: dict | None = None

    def step(self, name: str, output=None, status: str = "DONE", note: str | None = None) -> dict:
        s = {"name": name, "status": status, "t": now_iso(), "note": note, "output": output}
        self.steps.append(s)
        return s

    def finish(self, status: str, error: str | None = None) -> None:
        self.status, self.ended, self.error = status, now_iso(), error

    def to_dict(self) -> dict:
        return {"id": self.id, "alertId": self.alert_id, "asset": self.asset, "status": self.status,
                "started": self.started, "ended": self.ended, "steps": self.steps, "card": self.card,
                "error": self.error, "evaluation": self.evaluation}


class RunRegistry:
    def __init__(self, keep: int = 200):
        self.keep = keep
        self._runs: OrderedDict[str, Run] = OrderedDict()
        self._seq = 0
        self._lock = RLock()

    def new(self, alert: dict) -> Run:
        """같은 경보라도 평가할 때마다 새 실행(새 id)."""
        with self._lock:
            self._seq += 1
            run = Run(id=f"RUN-{self._seq:04d}", alert_id=alert.get("alertId"), asset=alert.get("asset", "?"), alert=alert)
            self._runs[run.id] = run
            while len(self._runs) > self.keep:
                self._runs.popitem(last=False)
            return run

    def get(self, run_id: str) -> Run | None:
        with self._lock:
            return self._runs.get(run_id)

    def all(self) -> list[Run]:
        with self._lock:
            return list(reversed(self._runs.values()))
