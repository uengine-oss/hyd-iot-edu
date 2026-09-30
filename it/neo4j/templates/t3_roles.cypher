// T3-f 역할과 직급: 승인 권한 판단용 (Role -MEMBER_OF-> Department)
MATCH (r:Role)-[:MEMBER_OF]->(d:Department)
RETURN r.id AS id, r.name AS name, r.level AS level, d.id AS dept, d.name AS deptName ORDER BY r.level DESC, r.id
