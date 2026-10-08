"""hyd-dmn MCP: FastMCP server (streamable HTTP) wrapping the deterministic judgment engine.

    docker: NEO4J_URI · NEO4J_AUTH · TSDB_DSN · DAQ_PROFILE · PROCESS_URL · ENTERPRISE_URL · ENTERPRISE_READ_DSN ·
            INGEST_URL · PROMETHEUS_URL   MCP_PORT=8198
    tools : diagnose · dmn_rules · inputs · gather_facts · timeseries_schema · timeseries_query ·
            prometheus_metadata · prometheus_series · prometheus_query · evaluate_cards · forecast_actions ·
            submit_decision · precedents · tradeoffs · fabric_query   (15; submit_decision is the only write)
"""
from __future__ import annotations

import os
from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from .tools import DmnTools, enveloped

mcp = FastMCP("hyd-dmn", instructions=(
    "유압설비 교육 공장의 결정론 판단 엔진이다. 원인 진단(diagnose)은 후보 원인의 사전 확률 × 실제 증거 가중치로 순위를 매긴다. "
    "조치 판단은 온톨로지 v2 의 DMN 결정표 dec:action-candidates(COLLECT) · dec:compliance(COLLECT) · dec:rank-actions(UNIQUE)를 "
    "실제 사실에 대어 같은 입력이면 같은 결과를 낸다. dec:diagnose-cause 규칙(rule:dx-*)은 진단 근거를 설명하는 지식이며 이 엔진이 평가하지 않는다. "
    "규칙을 임의로 해석하지 말고 이 도구의 결과를 인용하라. "
    "submit_decision 만 쓰기이며(process /api/decisions), 설비 명령은 어디서도 나가지 않는다. 모든 도구는 {result: ok|error, document} 봉투로 답한다."))
tools = DmnTools()
READ = {"readOnlyHint": True, "destructiveHint": False}       # MCP ToolAnnotations — 포털 도구 써 보기는 readOnlyHint=true 만 부른다 (procsvc/mcp_check.py)
WRITE = {"readOnlyHint": False, "destructiveHint": False}     # submit_decision: process 에 카드 묶음을 쓴다(설비 명령 아님)

Asset = Annotated[str, Field(description="설비 코드 (HYD-01 | HYD-02 | HYD-03)")]
Pattern = Annotated[str, Field(description="이상 패턴 코드 (예: COOLER_DEGRADATION, PUMP_LEAKAGE, FAN_VIBRATION)")]
Cause = Annotated[str, Field(description="원인 노드 id (예: cause:cooler-fin-fouling)")]
FailureMode = Annotated[str, Field(description="고장 유형 노드 id (예: fm:cooling-loss)")]
Overrides = Annotated[dict | None, Field(description="가정 실험용 사실 덮어쓰기 (예: {\"plc_mode\": \"REMOTE_MANUAL\"}). 보통 비움")]


@mcp.tool(annotations=READ)
def diagnose(asset: Asset, pattern: Pattern) -> dict:
    """원인 진단: 신선도→후보(T1)→증거 SQL→순위→SOP/가이드. withheld=true이면 근거 미확인 또는 지지 근거 없음이므로 원인을 임의로 골라 후속 조치 판단을 하지 않는다. 원천/규칙을 확인한 뒤 재조회하거나 사람 확인을 요청한다. Evidence의 PASS/FAIL/UNKNOWN과 오류 근거를 보존한다."""
    return enveloped(lambda: tools.diagnose(asset, pattern))()


@mcp.tool(annotations=READ)
def dmn_rules(decision: Annotated[str | None, Field(description="판단 id 로 거르기 (dec:action-candidates 등). 비우면 전체")] = None) -> dict:
    """DMN 결정표의 규칙들: 임계값 검사(TESTS), 출력, 적용 대상, 근거 출처."""
    return enveloped(lambda: tools.dmn_rules(decision))()


@mcp.tool(annotations=READ)
def inputs() -> dict:
    """판단 입력 데이터(InputData)와 그 출처 시스템 · 센서 (어느 사실을 어디서 가져오는가)."""
    return enveloped(lambda: tools.inputs())()


@mcp.tool(annotations=READ)
def gather_facts(asset: Asset, pattern: Pattern, cause: Cause, failure_mode: FailureMode) -> dict:
    """규칙이 검사할 사실을 온톨로지가 정한 출처(시계열 · PLC 상태 · MES 등)에서 실제로 가져온다. 값마다 어디서 어떻게 얻었는지 provenance 를 함께 준다."""
    return enveloped(lambda: tools.gather_facts(asset, pattern, cause, failure_mode))()


@mcp.tool(annotations=READ)
def timeseries_schema() -> dict:
    """센서 원천 TimescaleDB의 실제 테이블/열/타입과 최근5분 관측 설비·태그 목록. 먼저 읽고 SQL을 생성한다. 센서 단위/의미는 온톨로지 inputs와 대조한다."""
    return enveloped(tools.timeseries_schema)()


@mcp.tool(annotations=READ)
def timeseries_query(sql: Annotated[str, Field(description="timeseries_schema로 확인한 public.tag_1s/feat_1s/tag_1m 대상 PostgreSQL SELECT. 시간범위·설비·태그를 명시하고 지속 조건에는 관측 간격/누락/신선도를 함께 검사한다.")]) -> dict:
    """에이전트가 생성한 센서 SQL을 실제 읽기 전용 원천에 실행한다. 최대200행/5초. 빈 결과는 정상0행이며 조건 불일치·미관측은 질의 의미에 따라 구분한다. 쓰기/원천 밖/미허용 함수는 거절한다."""
    return enveloped(lambda: tools.timeseries_query(sql))()


@mcp.tool(annotations=READ)
def prometheus_metadata(metric: str | None = None) -> dict:
    """Prometheus가 수집한 지표 HELP/type/unit. metric은 정확한 이름(생략 시 목록). truncated면 목록 일부다. 생성 지표 up 등은 metadata에 없을 수 있어 prometheus_series로 확인한다. 현재 HYD는 플랫폼 지표이며 센서 태그를 추정하지 않는다."""
    return enveloped(lambda: tools.prometheus.metadata(metric))()


@mcp.tool(annotations=READ)
def prometheus_series(selector: str, start: float | None = None, end: float | None = None) -> dict:
    """실제 지표/레이블 집합 탐색. selector는 Prometheus series selector. start/end는 Unix초(둘 다 생략 시 최근5분), 최대24시간/200시리즈. 시리즈 존재는 해당 구간의 실제 관측값 존재를 보증하지 않는다."""
    return enveloped(lambda: tools.prometheus.series(selector, start, end))()


@mcp.tool(annotations=READ)
def prometheus_query(expression: str, at: float | None = None, start: float | None = None,
                     end: float | None = None, step: float | None = None) -> dict:
    """메타데이터 확인 후 생성한 PromQL 읽기 실행. at=Unix초 단일시점(기본 현재), 또는 start/end/step초 모두 지정한 구간. 5초/24시간/200시리즈/20000점 제한. 빈 벡터·0·오류를 구분한다. 지속 조건은 timestamp/누락/관측간격까지 검사한다. 경고와 NaN/Inf를 보존한다."""
    return enveloped(lambda: tools.prometheus.query(expression, at, start, end, step))()


@mcp.tool(annotations=READ)
def evaluate_cards(asset: Asset, pattern: Pattern, cause: Cause, failure_mode: FailureMode, overrides: Overrides = None) -> dict:
    """후보 선택 → 규정 판정(제외 · 감점 · 경고) → 예측 · BSC 상충 · 선례 → 순위. 제출하지 않는다 (task:candidates · task:compliance 용)."""
    return enveloped(lambda: tools.evaluate_cards(asset, pattern, cause, failure_mode, overrides))()


@mcp.tool(annotations=READ)
def forecast_actions(asset: Asset, actions: Annotated[list[dict], Field(description="검토할 원자 조치 목록: kind=command, code, value. 예: FAN_SET=100, LOAD_SET=80")],
                     horizon_s: Annotated[float, Field(description="예측할 시뮬레이션 시간(초)", gt=0, le=86400)] = 900) -> dict:
    """현재 설비의 명시된 교육용 모델 입력으로 조치 후 온도·압력·진동을 예측한다. 입력/가정/범위/인터록 가능성을 반환한다. 실행·승인·카드 제출은 하지 않으며 미지원 모델/조치/오래된 입력이면 오류다."""
    return enveloped(lambda: tools.forecast_actions(asset, actions, horizon_s))()


@mcp.tool(annotations=WRITE)
def submit_decision(asset: Asset, pattern: Pattern, cause: Cause, failure_mode: FailureMode,
                    incident: Annotated[str, Field(description="이 인스턴스의 Incident id (task.json inputs.incident)")],
                    alert_id: Annotated[str | None, Field(description="경보 id")] = None, overrides: Overrides = None,
                    process_scope: Annotated[dict | None, Field(description="context/task.json의 process_scope 객체를 그대로 전달: tenant/instance/workitem/generation/version/consumer")] = None) -> dict:
    """순위를 매긴 조치 카드 묶음을 process 에 제출한다 (사람이 고를 카드). 에이전트의 유일한 쓰기. 돌려준 id 가 decision_id 다."""
    return enveloped(lambda: tools.submit_decision(asset, pattern, cause, failure_mode, incident, alert_id, overrides, process_scope))()


@mcp.tool(annotations=READ)
def precedents(failure_mode: FailureMode) -> dict:
    """같은 고장 유형에서 사람이 과거에 고른 카드(DecisionCase) 통계."""
    return enveloped(lambda: tools.precedents(failure_mode))()


@mcp.tool(annotations=READ)
def tradeoffs(skill_ids: Annotated[list[str], Field(description="스킬 id 목록")]) -> dict:
    """스킬 → 첫 BSC 지표까지 개별 경로/관계/소유자/원문 조건과 명시 조건식. 목록만으로 조건이 참이라고 가정하지 않는다. evaluate_cards의 tradeoffEvaluation이 현재 사실/후보 예측으로 TRUE/FALSE/UNKNOWN을 판정한다."""
    return enveloped(lambda: tools.tradeoffs(skill_ids))()


@mcp.tool
def fabric_query(asset: Asset,
                 query: Annotated[str, Field(description="asset(설비 하나로 두 원천의 연결된 값 합치기) | " + " | ".join(
                     f"{k}({v['title']})" for k, v in CROSS_QUERIES.items()) + " | sql(원천별 SELECT 직접 작성)")] = "asset",
                 limit: Annotated[int, Field(description="원천 조회마다 최대 행 수 (1~200)", ge=1, le=200)] = 50,
                 sql: Annotated[dict | None, Field(description=f"query=sql 일 때만: {{'{ENT}': 'ent 스키마 SELECT', '{TS}': 'tag_1s/feat_1s/tag_1m SELECT'}}. "
                                                               "%(asset)s 로 설비 코드를 받는다. 쓰기 · 다른 스키마 · 다중 문장은 연결 전에 거절")] = None) -> dict:
    """데이터 패브릭(읽기 전용): 업무 DB(Supabase ent: 주문 · 계약 · 정비 · 품질)와 시계열 DB(TimescaleDB: 센서 1초 기록)를 한 질문으로 묶는다. 값마다 출처(원천 · 표 · 열 · 조건 · 실행 SQL · 관측 시각)를 준다. 한 원천이 실패하면 partial=true 와 그 사유, 둘 다 실패하면 error. 전용 읽기 계정 · 읽기 전용 트랜잭션 · 5초 · 행 제한."""
    return enveloped(lambda: tools.fabric_query(asset, query, limit, sql))()


@mcp.custom_route("/healthz", methods=["GET"])
async def healthz(_request):
    from starlette.responses import JSONResponse
    h = tools.health()
    return JSONResponse({"ok": h["neo4j"], **h}, status_code=200 if h["neo4j"] else 503)


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=int(os.getenv("MCP_PORT", "8198")), path="/mcp", uvicorn_config={"ws": "none"})
