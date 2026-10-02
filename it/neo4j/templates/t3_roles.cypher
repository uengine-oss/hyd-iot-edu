// T3-f — 역할과 직급 (승인 권한 판정용)
MATCH (r:Role) OPTIONAL MATCH (r)-[:MEMBER_OF]->(d:OrgUnit)
RETURN r.id AS id, r.name AS name, r.level AS level, d.name AS deptName ORDER BY r.level, r.id
