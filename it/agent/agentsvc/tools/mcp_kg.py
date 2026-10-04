"""mcp-kg (read-only): whitelisted Cypher templates against the Neo4j ontology v2.

In the full architecture this is a separate MCP server container; the student edition keeps the same
whitelist discipline (only template files can run, parameters only) inside the agent process.
  T1 원인 후보 · 증거   T2 고장 유형별 조치 방법(스킬 = SOP)   T3 DMN 규칙 · 입력 출처 · BSC 상충 · 예측 · 선례 · 역할   T0 지식 지도
"""
import os
from pathlib import Path

from neo4j import GraphDatabase, unit_of_work

TEMPLATES = Path(os.getenv("KG_TEMPLATES", "/srv/templates"))


class KnowledgeGraph:
    def __init__(self):
        uri = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
        user, pwd = os.getenv("NEO4J_AUTH", "neo4j/hydpass123").split("/", 1)
        self.driver = GraphDatabase.driver(uri, auth=(user, pwd),
                                          connection_timeout=3, connection_acquisition_timeout=5,
                                          max_transaction_retry_time=0)
        self._cache: dict[str, str] = {}

    def template(self, name: str) -> str:
        if name not in self._cache:
            text = (TEMPLATES / f"{name}.cypher").read_text(encoding="utf-8")
            self._cache[name] = "\n".join(l for l in text.splitlines() if not l.strip().startswith("//"))
        return self._cache[name]

    def _run(self, name: str, **params) -> list[dict]:
        # Bound database work; callers retain UNKNOWN/retry semantics on failure.
        q = self.template(name)
        @unit_of_work(timeout=5.0)
        def read(tx):
            return [r.data() for r in tx.run(q, **params)]
        with self.driver.session() as s:
            return s.execute_read(read)

    # ---- T1 / T2: diagnosis and the failure mode's SOP skills
    def t1_causes(self, pattern: str, asset: str) -> list[dict]:
        return self._run("t1_causes", pattern=pattern, asset=asset)

    def t2_skills(self, cause_id: str) -> list[dict]:
        return self._run("t2_skills", cause=cause_id)

    # ---- T3: decision context (DMN rules, inputs, BSC trade-offs, forecasts, precedents)
    def skills(self, ids: list[str]) -> list[dict]:
        return self._run("t3_skills", ids=ids)

    def dmn(self) -> list[dict]:
        return self._run("t3_dmn")

    def inputs(self) -> list[dict]:
        return self._run("t3_inputs")

    def tradeoffs(self, ids: list[str]) -> list[dict]:
        return self._run("t3_tradeoffs", ids=ids)

    def forecasts(self, cause: str) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for r in self._run("t3_forecasts", cause=cause):
            if r.get("skill"):
                out.setdefault(r["skill"], {})[r["variable"]] = r
        return out

    def forecast_model(self, asset: str) -> dict:
        rows = self._run('t3_forecast_model', asset=asset)
        if len(rows) != 1:
            raise ValueError('asset requires exactly one explicit forecast model binding')
        return rows[0]

    def precedents(self, failure_mode: str) -> list[dict]:
        return self._run("t3_precedents", failureMode=failure_mode)

    def roles(self) -> list[dict]:
        return self._run("t3_roles")

    def suppliers(self) -> dict[str, dict]:
        return {r["id"]: r for r in self._run("t3_suppliers")}

    # ---- T0: portal knowledge map
    def patterns(self) -> list[dict]:
        return self._run("t0_patterns")

    def graph(self, asset: str) -> dict:
        return {"nodes": self._run("t0_graph_nodes", asset=asset), "edges": self._run("t0_graph_edges", asset=asset)}

    def template_text(self, name: str) -> str:
        return (TEMPLATES / f"{name}.cypher").read_text(encoding="utf-8")

    def ping(self) -> bool:
        try:
            @unit_of_work(timeout=5.0)
            def read(tx):
                return tx.run("RETURN 1").single()
            with self.driver.session() as s:
                s.execute_read(read)
            return True
        except Exception:  # noqa: BLE001
            return False
