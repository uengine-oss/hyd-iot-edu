-- Instructor-managed service only. Student deployments cannot confer upstream
-- model access by editing their own copy of these tables.
CREATE TABLE IF NOT EXISTS hyd_classroom_grants (
    key_hash text PRIMARY KEY,
    subject text NOT NULL,
    scope text NOT NULL,
    policy jsonb NOT NULL,
    enabled boolean NOT NULL DEFAULT true,
    expires_at timestamptz NOT NULL,
    calls bigint NOT NULL DEFAULT 0 CHECK (calls >= 0),
    input_bytes bigint NOT NULL DEFAULT 0 CHECK (input_bytes >= 0),
    output_tokens bigint NOT NULL DEFAULT 0 CHECK (output_tokens >= 0)
);
CREATE TABLE IF NOT EXISTS hyd_classroom_runs (
    id uuid PRIMARY KEY,
    key_hash text NOT NULL REFERENCES hyd_classroom_grants(key_hash),
    request_key text NOT NULL,
    action text NOT NULL,
    input_hash text NOT NULL,
    policy_hash text NOT NULL,
    state text NOT NULL CHECK (state IN ('RESERVED','RUNNING','DONE','FAILED','EXPIRED')),
    created_at timestamptz NOT NULL DEFAULT now(),
    deadline timestamptz NOT NULL,
    calls bigint NOT NULL DEFAULT 0,
    input_bytes bigint NOT NULL DEFAULT 0,
    output_tokens bigint NOT NULL DEFAULT 0,
    result_ref text,
    work_ref text,
    cache_key text,
    UNIQUE(key_hash, request_key)
);
CREATE INDEX IF NOT EXISTS hyd_classroom_runs_active ON hyd_classroom_runs(key_hash, state, deadline);
REVOKE ALL ON hyd_classroom_grants, hyd_classroom_runs FROM PUBLIC, anon, authenticated;
ALTER TABLE hyd_classroom_grants ENABLE ROW LEVEL SECURITY;
ALTER TABLE hyd_classroom_runs ENABLE ROW LEVEL SECURITY;
