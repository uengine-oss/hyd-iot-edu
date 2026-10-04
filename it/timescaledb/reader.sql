-- Dedicated sensor-query principal. Apply to existing databases without reset.
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='hyd_timeseries_reader') THEN
    CREATE ROLE hyd_timeseries_reader LOGIN PASSWORD 'hyd-timeseries-read-local';
  END IF;
END $$;
ALTER ROLE hyd_timeseries_reader SET default_transaction_read_only=on;
ALTER ROLE hyd_timeseries_reader SET statement_timeout='5s';
GRANT CONNECT ON DATABASE hyd TO hyd_timeseries_reader;
GRANT USAGE ON SCHEMA public TO hyd_timeseries_reader;
GRANT SELECT ON public.tag_1s,public.feat_1s,public.tag_1m TO hyd_timeseries_reader;
