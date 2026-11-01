// T3-d — 설비가 쓰는 예측 모델(parameter: $asset 설비 코드). 카드의 조치 후 예측값은 이 모델 · 판으로 그때의 설비 상태에서 계산한다(agent forecasting).
MATCH (a:Asset {code: $asset})
RETURN a.id AS asset_id, a.code AS asset,
       a.forecastModel AS model_id, a.forecastRevision AS model_revision,
       a.forecastScope AS scope, a.forecastHorizonS AS horizon_s
