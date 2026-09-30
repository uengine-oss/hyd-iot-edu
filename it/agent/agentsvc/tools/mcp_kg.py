"""mcp-kg (read-only): whitelisted Cypher templates T1/T2 against the Neo4j ontology.

In the full architecture this is a separate MCP server container; the student edition keeps the same
whitelist discipline (only template files can run, parameters only) inside the agent process.
"""
import os
from pathlib import Path

from neo4j import GraphDatabase

TEMPLATES = Path(os.getenv("KG_TEMPLATES", "/srv/templates"))


class KnowledgeGraph:
    def __init__(self):
        uri = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
        user, pwd = os.getenv("NEO4J_AUTH", "neo4j/hydpass123").split("/", 1)
        self.driver = GraphDatabase.driver(uri, auth=(user, pwd))
        self._cache: dict[str, str] = {}

    def template(self, name: str) -> str:
        if name not in self._cache:
            text = (TEMPLATES / f"{name}.cypher").read_text(encoding="utf-8")
            self._cache[name] = "\n".join(l for l in text.splitlines() if not l.strip().startswith("//"))
        return self._cache[name]

    def _run(self, name: str, **params) -> list[dict]:
        with self.driver.session() as s:
            return [r.data() for r in s.run(self.template(name), **params)]

    def t1_causes(self, pattern: str, asset: str) -> list[dict]:
        return self._run("t1_causes", pattern=pattern, asset=asset)

    def t2_actions(self, cause_id: str, asset: str) -> list[dict]:
        return self._run("t2_actions", cause=cause_id, asset=asset)

    # ---- T3: enterprise decision context (L7 -> L8) ----
    def scenario_context(self, scenario: str) -> dict:
        rows = self._run("t3_scenario", scenario=scenario)
        if not rows or not rows[0].get("scenario"):
            raise KeyError(scenario)
        return {"scenario": rows[0], "options": self._run("t3_options", scenario=scenario),
                "kpis": self._run("t3_kpis"), "policies": self._run("t3_policies", scenario=scenario),
                "precedents": {r["option"]: {"n": r["n"], "reasons": r["reasons"]} for r in self._run("t3_precedents", scenario=scenario)}}

    def triggers(self, ids: list[str]) -> list[dict]:
        return self._run("t3_triggers", ids=ids)

    def roles(self) -> list[dict]:
        return self._run("t3_roles")

    def scenarios(self) -> list[dict]:
        return self._run("t0_scenarios")

    def graph(self, asset: str) -> dict:
        return {"nodes": self._run("t0_graph_nodes", asset=asset), "edges": self._run("t0_graph_edges", asset=asset)}

    def template_text(self, name: str) -> str:
        return (TEMPLATES / f"{name}.cypher").read_text(encoding="utf-8")

    def ping(self) -> bool:
        try:
            with self.driver.session() as s:
                s.run("RETURN 1").single()
            return True
        except Exception:  # noqa: BLE001
            return False
