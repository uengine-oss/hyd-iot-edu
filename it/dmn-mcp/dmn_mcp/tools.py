"""The deterministic L8 engine (it/agent/agentsvc: card · cards · decide · tools) as callable tools.

ProcessGPT's principle "repeated judgments become DMN rules; the LLM gathers and explains" (process-gpt README,
Deterministic Regularization). Claude Code calls these to get rule results it must not re-derive by itself.
Nothing here writes to a plant or an enterprise system; `submit_decision` posts the ranked cards to the process
service, which is the agent's only write (same as the legacy agent service).
"""
from __future__ import annotations

import psycopg

from agentsvc import card as cardlib, decide as decidelib, llm
from agentsvc.tools import mcp_kg, mcp_prom, mcp_tsdb
from agentsvc.tools.prometheus import Prometheus


def ok(document) -> dict:
    """The result envelope the WMS sample's MCP uses: {"result": "ok", "document": …}."""
    return {"result": "ok", "document": document}


def error(kind: str, message: str) -> dict:
    """kind: INVALID (bad input) | UNKNOWN (engine / graph / network)."""
    return {"result": "error", "error_kind": kind, "message": message}


def enveloped(fn):
    """Wrap a tool so the agent always gets the same envelope and never a stack trace."""
    def run(*a, **kw):
        try:
            return ok(fn(*a, **kw))
        except (KeyError, ValueError, TypeError) as e:
            return error("INVALID", f"{type(e).__name__}: {str(e)[:300]}")
        except psycopg.Error as e:
            # Invalid generated SQL can be repaired from the current metadata;
            # unavailable source/timeouts must not become a normal empty result.
            return error('INVALID' if (e.sqlstate or '').startswith('42') else 'UNKNOWN',
                         f"{type(e).__name__}: {str(e)[:300]}")
        except Exception as e:  # noqa: BLE001
            return error("UNKNOWN", f"{type(e).__name__}: {str(e)[:300]}")
    run.__name__, run.__doc__ = fn.__name__, fn.__doc__
    return run


class DmnTools:
    def __init__(self, kg: mcp_kg.KnowledgeGraph | None = None, tsdb: mcp_tsdb.TimeSeriesDB | None = None):
        self.kg = kg or mcp_kg.KnowledgeGraph()
        self.tsdb = tsdb or mcp_tsdb.TimeSeriesDB()
        self.registry = decidelib.DecisionRegistry()
        self.prometheus = Prometheus()

    # ---- task:diagnose
    def diagnose(self, asset: str, pattern: str) -> dict:
        """Data trust → T1 cause candidates → evidence SQL → ranked causes → T2 SOP skills → guide card (with citations)."""
        fresh = mcp_prom.freshness(self.tsdb, asset)
        alert = {"asset": asset, "pattern": pattern}
        if not fresh["ok"]:
            return {"withheld": True, "freshness": fresh, "card": None, "reason": f"데이터 신뢰 불가: {fresh['reason']}"}
        t1 = self.kg.t1_causes(pattern, asset)
        evidence = [e for r in t1 for e in (r.get("evidence") or [])]
        results = self.tsdb.evaluate(evidence, asset)
        causes = cardlib.rank_causes(t1, results)
        assessment = cardlib.evidence_status(causes)
        if assessment['withheld']:
            return dict(withheld=True, freshness=fresh, top_cause=None, failure_mode=None,
                        card=None, causes=causes, evidence_status=assessment, reason=assessment['reason'])
        t2 = {causes[0]["id"]: self.kg.t2_skills(causes[0]["id"])} if causes else {}
        card = cardlib.build_card(None, alert, causes, t2, fresh)
        return {"withheld": False, "freshness": fresh, "evidence_status": assessment, "top_cause": causes[0]["id"] if causes else None,
                "failure_mode": causes[0].get("failureModeId") if causes else None,
                "causes": [{"id": c["id"], "name": c["name"], "score": c["score"], "prior": c["prior"],
                            "evidence": c["evidence"]} for c in causes],
                "card": card}

    # ---- rules and facts (task:candidates · task:compliance)
    def dmn_rules(self, decision: str | None = None) -> list[dict]:
        rows = self.kg.dmn()
        return [r for r in rows if decision is None or r["decision"] == decision]

    def inputs(self) -> list[dict]:
        return self.kg.inputs()

    def timeseries_schema(self):
        return self.tsdb.describe_schema()

    def timeseries_query(self, sql):
        return self.tsdb.query(sql)

    def forecast_actions(self, asset: str, actions: list[dict], horizon_s: float = 900) -> dict:
        """Read current model inputs and forecast supplied actions; no execution."""
        from agentsvc.forecasting import current
        return current(self.kg, asset, actions, horizon_s)

    def gather_facts(self, asset: str, pattern: str, cause: str, failure_mode: str) -> dict:
        known = {"pattern": pattern, "cause": cause, "failure_mode": failure_mode}
        facts, provenance = decidelib.gather_facts(self.kg.inputs(), asset, known, self.tsdb)
        return {"facts": facts, "provenance": provenance}

    # ---- task:rank
    def evaluate_cards(self, asset: str, pattern: str, cause: str, failure_mode: str, overrides: dict | None = None) -> dict:
        """Run dec:action-candidates → dec:compliance → dec:rank-actions with forecasts, BSC trade-offs and precedents. No submission."""
        c = self._cause(cause, failure_mode)
        return decidelib.decide(self.kg, self.registry, self.tsdb, asset, pattern, c, origin={"kind": "mcp", "pattern": pattern},
                                overrides=overrides or None, do_submit=False)

    def submit_decision(self, asset: str, pattern: str, cause: str, failure_mode: str, incident: str, alert_id: str | None = None,
                        overrides: dict | None = None, process_scope: dict | None = None) -> dict:
        """Same evaluation, then POST the ranked cards to the process service (the agent's only write). Returns id · status · recommended."""
        c = self._cause(cause, failure_mode)
        origin = {"kind": "alert", "alertId": alert_id, "incident": incident, "pattern": pattern, "cause": cause, "failureMode": failure_mode}
        if process_scope is not None:
            origin['process_scope'] = dict(process_scope)
        rec = decidelib.decide(self.kg, self.registry, self.tsdb, asset, pattern, c, origin=origin, overrides=overrides or None, do_submit=True)
        res = rec.get("result") or {}
        return {"id": rec["id"], "status": rec["status"], "recommended": rec.get("recommended"), "explanation": rec.get("explanation"),
                "cards": [{"rank": o["rank"], "id": o["id"], "sopId": o["sopId"], "name": o["name"], "feasible": o["feasible"], "score": o["score"],
                           "approver": (o.get("approver") or {}).get("name")} for o in res.get("options", [])],
                "error": rec.get("error")}

    def precedents(self, failure_mode: str) -> list[dict]:
        return self.kg.precedents(failure_mode)

    def tradeoffs(self, skill_ids: list[str]) -> list[dict]:
        return self.kg.tradeoffs(skill_ids)

    @staticmethod
    def _cause(cause: str, failure_mode: str) -> dict:
        """The shape decide.decide() expects for the top cause. Names are only used in explanation text, so ids suffice here."""
        return {"id": cause, "name": cause, "failureModeId": failure_mode, "failureMode": failure_mode}

    def health(self) -> dict:
        return {"neo4j": self.kg.ping(), "llm": llm.available()}
