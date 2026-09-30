// T3-b 대안: Option -USES_SKILL-> Skill(-EXECUTED_VIA-> System, -EXECUTED_IN-> BusinessProcess, -IMPLEMENTS-> Action)
//            Option -IMPACTS{expr}-> KPI ; Option -APPROVED_BY-> Role ; Option -BUYS_FROM-> Supplier
MATCH (s:Scenario {id: $scenario})-[:HAS_OPTION]->(o:Option)
OPTIONAL MATCH (o)-[:APPROVED_BY]->(r:Role)
OPTIONAL MATCH (o)-[:BUYS_FROM]->(sp:Supplier)
RETURN o.id AS id, o.name AS name, o.description AS description, o.params AS params,
       CASE WHEN r IS NULL THEN null ELSE {id: r.id, name: r.name, level: r.level} END AS approver,
       CASE WHEN sp IS NULL THEN null ELSE {id: sp.id, name: sp.name, avl: sp.avl} END AS supplier,
       COLLECT { MATCH (o)-[:USES_SKILL]->(k:Skill)-[:EXECUTED_VIA]->(sy:System)
                 MATCH (k)-[:EXECUTED_IN]->(bp:BusinessProcess)
                 RETURN {id: k.id, name: k.name, description: k.description, category: k.category, system: sy.id, systemName: sy.name, process: bp.id, processName: bp.name,
                         actions: COLLECT { MATCH (k)-[:IMPLEMENTS]->(a:Action) RETURN a.id }} } AS skills,
       COLLECT { MATCH (o)-[i:IMPACTS]->(k:KPI) RETURN {kpi: k.id, expr: i.expr, note: i.note} } AS impacts
ORDER BY o.id
