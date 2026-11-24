"""수업 AI 단계가 쓸 수 있는 조회 도구 허용 목록 한 곳 — 교대 인수인계 초안(단계 계약 → 허용 조회 도구, procsvc/agents_store.FIXED_READS — 워커가 서버에서 받아 --allowedTools 로)과
「에이전트에게 질문」(질문 전용 MCP 창구, worker/question_tools). 판단 제출 · 발주 같은 쓰기 도구는 어느 목록에도 없다 — 목록 밖 도구는 허용되지 않는다.
기본 제공 도구 서버의 이름도 이곳 한 곳이 갖는다(process 의 등록 규칙 · agent 의 판단 실험이 같은 이름표를 읽는다)."""

#: 기본 제공 도구 서버(seed.sql 의 tenants.mcp) — 학생은 같은 이름으로 등록 · 수정 · 삭제할 수 없다(procsvc/mcp_registry).
#: 업무 계열(BUSINESS_SERVERS)은 업무 DB 를 읽는 서버와 C2 로 그것을 보전용 · 구매용으로 나눈 둘이다. 이름 꼴(「enterprise-」로 시작)로 가리지 않는다 —
#: 학생이 「enterprise-stock」처럼 지은 자기 서버를 기본 제공 업무 서버로 보면, 판단 실험이 그 서버 대신 기본 제공 업무 시스템을 읽는다(검진 N12).
BUSINESS_SERVERS = ('enterprise', 'enterprise-maint', 'enterprise-purchase')
BASE_SERVERS = ('neo4j', 'enterprise', 'hyd-dmn', 'enterprise-maint', 'enterprise-purchase')

HANDOVER_READS = {
    'neo4j': ('get_neo4j_schema', 'read_neo4j_cypher'),
    'enterprise': ('describe_catalog', 'describe_schema', 'query'),
    # inputs only reads t3_inputs: InputData and its source/variable metadata.
    'hyd-dmn': ('inputs', 'timeseries_schema', 'timeseries_query'),
}


# 질문은 인계 원천 데이터에 더해 판단 근거(진단 · 규칙 · 예측)까지 읽을 수 있다.
QUESTION_READS = {
    **HANDOVER_READS,
    'hyd-dmn': HANDOVER_READS['hyd-dmn'] + (
        'diagnose', 'dmn_rules', 'gather_facts', 'evaluate_cards',
        'read_evaluation_evidence', 'forecast_actions', 'business_causes',
        'purchase_context', 'evaluate_purchase', 'precedents', 'tradeoffs', 'fabric_query'),
}


def question_read(server, name):
    return name in QUESTION_READS.get(server, ())
