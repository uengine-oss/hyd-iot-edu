"""수업 AI 단계가 쓸 수 있는 조회 도구 허용 목록 한 곳 — 교대 인수인계 초안(워커의 --allowedTools, worker/settings.handover_allowed_tools)과
「에이전트에게 질문」(질문 전용 MCP 창구, worker/question_tools). 판단 제출 · 발주 같은 쓰기 도구는 어느 목록에도 없다 — 목록 밖 도구는 허용되지 않는다."""

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
        'diagnose', 'dmn_rules', 'gather_facts', 'prometheus_metadata',
        'prometheus_series', 'prometheus_query', 'evaluate_cards',
        'read_evaluation_evidence', 'forecast_actions', 'business_causes',
        'purchase_context', 'evaluate_purchase', 'precedents', 'tradeoffs', 'fabric_query'),
}


def question_read(server, name):
    return name in QUESTION_READS.get(server, ())
