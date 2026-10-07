"""Agent run registry: one run per alertId (duplicate RAISE messages never start a second reasoning run)."""
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
    status: str = "RUNNING"          # RUNNING | SUBMITTED | EVALUATED (instance mode: read-only evaluation, no submit) | REJECTED_BY_GUARDRAIL | WITHHELD | FAILED
    started: str = field(default_factory=now_iso)
    ended: str | None = None
    steps: list[dict] = field(default_factory=list)
    card: dict | None = None
    incident_id: str | None = None
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
                "incidentId": self.incident_id, "error": self.error, "evaluation": self.evaluation}


class RunRegistry:
    def __init__(self, keep: int = 200):
        self.keep = keep
        self._runs: OrderedDict[str, Run] = OrderedDict()
        self._by_alert: dict[str, str] = {}
        self._seq = 0
        self._lock = RLock()

    def create_if_new(self, alert: dict) -> Run | None:
        with self._lock:
            return self._create_if_new(alert)

    def _create_if_new(self, alert: dict) -> Run | None:
        aid = alert.get("alertId")
        if not aid or aid in self._by_alert:
            return None
        self._seq += 1
        run = Run(id=f"RUN-{self._seq:04d}", alert_id=aid, asset=alert.get("asset", "?"), alert=alert)
        self._runs[run.id] = run
        self._by_alert[aid] = run.id
        while len(self._runs) > self.keep:
            old_id, old = self._runs.popitem(last=False)
            if self._by_alert.get(old.alert_id)==old_id:
                self._by_alert.pop(old.alert_id, None)
        return run

    def force_new(self, alert: dict) -> Run:
        """Explicit fresh evaluation for the same alert, with a unique run ID."""
        with self._lock:
            self._by_alert.pop(alert.get("alertId"), None)
            return self._create_if_new(alert)

    def get(self, run_id: str) -> Run | None:
        with self._lock:
            return self._runs.get(run_id)

    def by_alert(self, alert_id: str) -> Run | None:
        with self._lock:
            rid = self._by_alert.get(alert_id)
            return self._runs.get(rid) if rid else None

    def all(self) -> list[Run]:
        with self._lock:
            return list(reversed(self._runs.values()))
