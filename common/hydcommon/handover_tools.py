"""Fixed classroom handover reads, shared by gateway and CLI permission checks."""

HANDOVER_READS = {
    'neo4j': ('get_neo4j_schema', 'read_neo4j_cypher'),
    'enterprise': ('describe_catalog', 'describe_schema', 'query'),
    # inputs only reads t3_inputs: InputData and its source/variable metadata.
    'hyd-dmn': ('inputs', 'timeseries_schema', 'timeseries_query'),
}


def handover_read(server, name):
    return name in HANDOVER_READS.get(server, ())
