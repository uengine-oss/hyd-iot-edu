MATCH p = (f:FailureMode {id: 'fm:cooler-cooling-performance-loss'})-[:MITIGATED_BY]->(:Skill)-[:HAS_STEP]->(:Step)-[:REFERS_TO]->(:ManualSection)-[:PART_OF]->(:KnowledgeSource)
RETURN p;
