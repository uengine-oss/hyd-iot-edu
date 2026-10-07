// T3-h — 판단 입력 데이터와 출처 (DMN InputData -SOURCED_FROM-> System | Sensor, -REPRESENTS-> 상태 변수 · 성과 지표)
// 에이전트는 어떤 사실을 어디서 가져올지 이 목록으로 정한다 (BPMN 데이터 연결성).
MATCH (i:InputData)
OPTIONAL MATCH (i)-[:SOURCED_FROM]->(src)
OPTIONAL MATCH (i)-[:REPRESENTS]->(v)
RETURN i.id AS id, i.name AS name, i.variable AS variable, i.typeRef AS typeRef,
       i.datasource AS datasource, i.catalog AS catalog, i.schema AS schema,
       i.table AS table, i.column AS column, i.assetColumn AS assetColumn, i.sqlType AS sqlType, i.derive AS derive, i.sourceState AS sourceState, i.sourceLiveType AS sourceLiveType,
       src.id AS source, coalesce(src.name, src.id) AS sourceName, labels(src)[0] AS sourceKind, src.tag AS tag,
       v.id AS represents, v.name AS representsName
ORDER BY i.id
