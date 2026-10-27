"""Fixed classroom handover reads, shared by gateway and CLI permission checks."""

HANDOVER_READS = {
    'neo4j': ('get_neo4j_schema', 'read_neo4j_cypher'),
    'enterprise': ('describe_catalog', 'describe_schema', 'query'),
    # inputs only reads t3_inputs: InputData and its source/variable metadata.
    'hyd-dmn': ('inputs', 'timeseries_schema', 'timeseries_query'),
}


def handover_read(server, name):
    return name in HANDOVER_READS.get(server, ())


# Ordinary classroom questions may inspect domain reasoning as well as the
# handover's source data. Submission tools are deliberately not present.
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
