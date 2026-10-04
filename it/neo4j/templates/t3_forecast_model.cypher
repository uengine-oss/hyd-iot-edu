// Runtime model selection is explicit asset metadata, separate from Forecast design references.
MATCH (a:Asset {code: $asset})
RETURN a.id AS asset_id, a.code AS asset,
       a.forecastModel AS model_id, a.forecastRevision AS model_revision,
       a.forecastScope AS scope, a.forecastHorizonS AS horizon_s
