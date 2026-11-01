"""읽기 평가 실행 한 번(/api/agent/evaluate — 판단 채점이 부른다)의 기록. 응답으로만 돌려주고 이 서비스에 쌓지 않는다.

예전에는 최근 200개를 메모리에 두고 `/api/agent/runs` 로 냈는데, 그것을 읽던 사건 화면(경보마다 돌던 옛 자동 파이프라인 시절)은
실제 처리 건과 이어지지 않아 채점 실행을 「분석만 있음」 사건으로 섞어 보였다(검진 G1-07 · W2-05). 판단 채점은 응답을 받아 자기 기록
(eval_runs)에 남기고, 처리 건의 AI 처리 과정은 처리 기록이 정본이다.
"""
import uuid
from dataclasses import dataclass, field

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

    @classmethod
    def new(cls, alert: dict) -> "Run":
        """같은 경보라도 평가할 때마다 새 실행(새 id)."""
        return cls(id=f"RUN-{uuid.uuid4().hex[:12]}", alert_id=alert.get("alertId"), asset=alert.get("asset", "?"), alert=alert)

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
