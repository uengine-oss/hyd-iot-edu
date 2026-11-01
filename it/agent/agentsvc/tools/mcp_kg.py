"""mcp-kg (read-only): whitelisted Cypher templates against the Neo4j ontology v2.

In the full architecture this is a separate MCP server container; the student edition keeps the same
whitelist discipline (only template files can run, parameters only) inside the agent process. The same holds for the
sibling modules mcp_tsdb · mcp_prom · mcp_ent: the `mcp_` prefix names the role, not a protocol (requirements have no
mcp/fastmcp). The MCP servers Claude Code actually connects to are it/dmn-mcp and it/enterprise-mcp.
  T1 원인 후보 · 증거   T2 고장 유형별 조치 방법(스킬 = SOP)   T3 DMN 규칙 · 입력 출처 · BSC 상충 · 선례 · 역할 · 예측 모델 바인딩   T0 지식 지도
Forecast values are not read from the graph: forecasting.candidates runs the explicit simulator model (hydcommon.forecast)
against the fresh plant snapshot; the graph only binds which model/revision an asset uses (t3_forecast_model).
"""
import os
from pathlib import Path

from neo4j import unit_of_work

from hydcommon import graphdb



def templates() -> Path:
    """템플릿 폴더(KG_TEMPLATES — 이미지는 /srv/templates). 부를 때 읽는다."""
    return Path(os.getenv("KG_TEMPLATES", "/srv/templates"))


class KnowledgeGraph:
    def __init__(self):
        # 드라이버는 한 곳(hydcommon.graphdb.connect — 주소 · 인증 · 「없는 이름」 알림 끔 · 끊긴 풀 연결 거름, 결정 2). 이 서비스의 한도만 준다:
        # 연결 3초 · 풀에서 꺼내기 5초 · 재시도 없음(bounded — 실패는 부르는 쪽이 UNKNOWN 으로 다룬다).
        self.driver = graphdb.connect(connection_timeout=3, connection_acquisition_timeout=5, max_transaction_retry_time=0)
        self._cache: dict[str, str] = {}
        self.ping_error: str | None = None

    def template(self, name: str) -> str:
        if name not in self._cache:
            text = (templates() / f"{name}.cypher").read_text(encoding="utf-8")
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
    def t1_causes(self, pattern: str) -> list[dict]:
        """경보 패턴 → 증상 → 고장 유형 → 원인 후보 + 증거 규칙. 설비는 묻지 않는다(고장 지식은 설비 형식 공통 — 템플릿에 $asset 없음)."""
        return self._run("t1_causes", pattern=pattern)

    def t2_skills(self, cause_id: str) -> list[dict]:
        return self._run("t2_skills", cause=cause_id)

    # ---- T3: decision context (DMN rules, inputs, BSC trade-offs, forecasts, precedents)
    def skills(self, ids: list[str]) -> list[dict]:
        return self._run("t3_skills", ids=ids)

    def purchase_part(self, part_no: str) -> dict:
        rows = self._run('t3_purchase_part', partNo=part_no)
        if len(rows) != 1:
            raise ValueError('ERP 부품 번호에 대응하는 실제 Part가 없거나 중복되었습니다')
        return rows[0]

    def dmn(self) -> list[dict]:
        return self._run("t3_dmn")

    def inputs(self) -> list[dict]:
        return self._run("t3_inputs")

    def tradeoffs(self, ids: list[str]) -> list[dict]:
        return self._run("t3_tradeoffs", ids=ids)

    def forecast_model(self, asset: str) -> dict:
        rows = self._run('t3_forecast_model', asset=asset)
        if len(rows) != 1:
            raise ValueError('asset requires exactly one explicit forecast model binding')
        return rows[0]

    def precedents(self, failure_mode: str) -> list[dict]:
        return self._run("t3_precedents", failureMode=failure_mode)

    def roles(self) -> list[dict]:
        return self._run("t3_roles")

    def perspectives(self) -> list[dict]:
        """B5: BSC 관점과 그 관점의 성과 지표(Measure -MEASURES-> Objective -IN_PERSPECTIVE-> Perspective)."""
        return self._run("t3_perspectives")

    def suppliers(self) -> dict[str, dict]:
        return {r["id"]: r for r in self._run("t3_suppliers")}

    # ---- T0: portal knowledge map
    def patterns(self) -> list[dict]:
        return self._run("t0_patterns")

    def graph(self, asset: str, ns: str = "") -> dict:
        """ns (G4): 학생 이름 공간 — 비면 수업 기준(ns 없는 노드)만, 학생 ID 면 그 학생 노드와 바로 닿는 기준 노드."""
        return {"nodes": self._run("t0_graph_nodes", asset=asset, ns=ns or ""), "edges": self._run("t0_graph_edges", asset=asset, ns=ns or "")}

    def namespaces(self) -> list[dict]:
        return self._run("t0_namespaces")

    def template_text(self, name: str) -> str:
        return (templates() / f"{name}.cypher").read_text(encoding="utf-8")

    def ping(self) -> bool:
        """지금 그래프에 닿는가(5초 한도). 닿지 못하면 False 이고 그 까닭은 ping_error 에 남는다 — 상태 확인이 그대로 보인다."""
        try:
            @unit_of_work(timeout=5.0)
            def read(tx):
                return tx.run("RETURN 1").single()
            with self.driver.session() as s:
                s.execute_read(read)
            self.ping_error = None
            return True
        except Exception as e:  # noqa: BLE001 — 닿지 못한 모든 까닭이 상태 확인의 답이다(까닭을 남긴다)
            self.ping_error = f"{type(e).__name__}: {str(e)[:200]}"
            return False
