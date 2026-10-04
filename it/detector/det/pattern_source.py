"""Read the entire held-pattern catalog and TESTS in one Neo4j transaction."""
from neo4j import unit_of_work

QUERY = """
MATCH (p:AnomalyPattern) WHERE p.detectionMode = 'held' AND coalesce(p.detectorScope, 'production') = $scope
OPTIONAL MATCH (p)-[test:TESTS]->(i:InputData)
WITH p, collect(CASE WHEN test IS NULL THEN null ELSE
  {variable:i.variable, operator:test.operator, value:test.value} END) AS tests
RETURN properties(p) AS pattern, tests ORDER BY p.id
"""


def read_patterns(driver, database='neo4j', scope='production', timeout=5.0):
    @unit_of_work(timeout=timeout)
    def read(tx):
        return [dict(record['pattern'], tests=record['tests']) for record in tx.run(QUERY, scope=scope)]
    with driver.session(database=database) as session:
        return session.execute_read(read)
