// T0 — 이상 패턴 목록과 그 고장 유형 (포탈의 강조 경로 · 판단 실행 선택지)
MATCH (p:AnomalyPattern)
OPTIONAL MATCH (p)-[:DETECTS]->(:Symptom)-[:INDICATES]->(fm:FailureMode)<-[:CAUSES]-(:Cause)
RETURN p.id AS id, p.code AS code, p.name AS name, collect(DISTINCT fm.name) AS failureModes ORDER BY p.id
