// T3-d — 조치별 예측 (parameter: $cause): 이 원인이 있을 때 각 스킬을 실행하면 상태 변수가 어디로 가는가
MATCH (f:Forecast)-[:GIVEN]->(:Cause {id: $cause}), (f)-[:FORECASTS]->(v:StateVariable)
OPTIONAL MATCH (f)-[:ASSUMES]->(s:Skill)
RETURN s.id AS skill, v.id AS variable, v.name AS variableName, f.value AS value, f.unit AS unit, f.method AS method, f.id AS id
