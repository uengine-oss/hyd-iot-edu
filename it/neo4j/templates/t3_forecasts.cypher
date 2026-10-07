// T3-d — 조치별 설계 목표 예측 (parameter: $cause): 이 원인이 있을 때 각 스킬을 실행하면 상태 변수가 어디로 가는가
// 쓰임: 수업·질의 예시 전용. 에이전트(agentsvc·dmn-mcp)는 이 템플릿을 호출하지 않는다 — 카드의 예측값은 설비 모델
// (hydcommon.forecast, 바인딩 t3_forecast_model)로 현재 설비 상태에서 계산한다(forecasting.candidates). Forecast 노드는
// 인스턴스 시드의 '설계 목표값'(f.method)으로 남아 있으며 판단 입력이 아니다.
MATCH (f:Forecast)-[:GIVEN]->(:Cause {id: $cause}), (f)-[:FORECASTS]->(v:StateVariable)
OPTIONAL MATCH (f)-[:ASSUMES]->(s:Skill)
RETURN s.id AS skill, v.id AS variable, v.name AS variableName, f.value AS value, f.unit AS unit, f.method AS method, f.id AS id
