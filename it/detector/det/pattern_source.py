"""Read the held-pattern catalog with its TESTS, and every pattern's display name, in one Neo4j transaction."""
from neo4j import unit_of_work

QUERY = """
MATCH (p:AnomalyPattern) WHERE p.detectionMode = 'held'
OPTIONAL MATCH (p)-[test:TESTS]->(i:InputData)
WITH p, collect(CASE WHEN test IS NULL THEN null ELSE
  {variable:i.variable, operator:test.operator, value:test.value} END) AS tests
RETURN properties(p) AS pattern, tests ORDER BY p.id
"""
NAMES = "MATCH (p:AnomalyPattern) WHERE p.code IS NOT NULL RETURN p.code AS code, p.name AS name ORDER BY p.code"


def read_patterns(driver, database='neo4j', timeout=5.0):
    """(held pattern rows, {code: display name}) — the names cover the PLC-trip patterns the detector raises too."""
    @unit_of_work(timeout=timeout)
    def read(tx):
        rows = [dict(record['pattern'], tests=record['tests']) for record in tx.run(QUERY)]
        names = {record['code']: record['name'] for record in tx.run(NAMES) if isinstance(record['name'], str) and record['name']}
        return rows, names
    with driver.session(database=database) as session:
        return session.execute_read(read)
