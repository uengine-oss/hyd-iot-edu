-- hyd-iot-edu TimescaleDB schema (v3 section 5.3, student edition)
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- 1 Hz tags (TS1..TS4, PS1..PS6, EPS1, FS1..2, VS1, CE, CP, SE, FanSpeedSP, LoadSP)
CREATE TABLE tag_1s (
  time  timestamptz NOT NULL,
  asset text        NOT NULL,
  name  text        NOT NULL,
  value double precision
);
SELECT create_hypertable('tag_1s', 'time', chunk_time_interval => INTERVAL '6 hours');
CREATE INDEX tag_1s_asset_name_time ON tag_1s (asset, name, time DESC);

-- 1 s wave features + anomaly score (the "ONNX autoencoder" slot)
CREATE TABLE feat_1s (
  time   timestamptz NOT NULL,
  asset  text        NOT NULL,
  sensor text        NOT NULL,
  mean   double precision,
  rms    double precision,
  slope  double precision,
  score  double precision
);
SELECT create_hypertable('feat_1s', 'time', chunk_time_interval => INTERVAL '6 hours');
CREATE INDEX feat_1s_asset_sensor_time ON feat_1s (asset, sensor, time DESC);

-- alerts: RAISE inserts, CLEAR updates (id-based upsert)
CREATE TABLE alerts (
  alert_id   text PRIMARY KEY,
  asset      text,
  pattern    text,
  severity   text,
  state      text,
  raised_at  timestamptz,
  cleared_at timestamptz,
  evidence   jsonb
);

-- actions: approved action.cmd + PLC ACK (from plant.status)
CREATE TABLE actions (
  cmd_id      text PRIMARY KEY,
  incident    text,
  asset       text,
  actions     jsonb,
  approved_by text,
  issued_at   timestamptz,
  expires_at  timestamptz,
  ack_result  text,
  ack_reason  text,
  ack_at      timestamptz
);

-- audit: approvals, rejections (with gateway reason), process events
CREATE TABLE audit (
  id       bigserial PRIMARY KEY,
  time     timestamptz NOT NULL DEFAULT now(),
  incident text,
  actor    text,
  event    text,
  detail   jsonb
);
CREATE INDEX audit_time ON audit (time DESC);

-- 1 minute continuous aggregate (v3: "연속 집계 1분")
CREATE MATERIALIZED VIEW tag_1m WITH (timescaledb.continuous) AS
  SELECT time_bucket('1 minute', time) AS bucket, asset, name,
         avg(value) AS avg, min(value) AS min, max(value) AS max
  FROM tag_1s GROUP BY bucket, asset, name
  WITH NO DATA;
SELECT add_continuous_aggregate_policy('tag_1m',
  start_offset => INTERVAL '1 hour', end_offset => INTERVAL '1 minute', schedule_interval => INTERVAL '1 minute');
SELECT add_retention_policy('tag_1s', INTERVAL '3 days');     -- 경량: 원시 1초 값은 3일, 1분 집계(tag_1m)는 30일
SELECT add_retention_policy('feat_1s', INTERVAL '3 days');
SELECT add_retention_policy('tag_1m', INTERVAL '30 days');

-- 경량: 2시간 지난 원시값은 압축 (설비·태그별 세그먼트, 보통 10배 이상 줄어든다). 압축된 청크도 그대로 조회된다.
ALTER TABLE tag_1s SET (timescaledb.compress, timescaledb.compress_segmentby = 'asset, name', timescaledb.compress_orderby = 'time DESC');
ALTER TABLE feat_1s SET (timescaledb.compress, timescaledb.compress_segmentby = 'asset, sensor', timescaledb.compress_orderby = 'time DESC');
SELECT add_compression_policy('tag_1s', INTERVAL '2 hours');
SELECT add_compression_policy('feat_1s', INTERVAL '2 hours');

-- read-only account for Grafana / MCP tools
CREATE ROLE grafana LOGIN PASSWORD 'grafana';
GRANT CONNECT ON DATABASE hyd TO grafana;
GRANT USAGE ON SCHEMA public TO grafana;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO grafana;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO grafana;
