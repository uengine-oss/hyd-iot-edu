-- Reverse RPC for a managed agent reading its student's current local state.
-- Only the instructor executor creates requests. Students can return a result
-- for their own active run; neither side supplies an arbitrary destination URL.
CREATE TABLE IF NOT EXISTS hyd_classroom_tool_io (
    id uuid PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES hyd_classroom_runs(id),
    call_id text NOT NULL,
    tool text NOT NULL,
    arguments jsonb NOT NULL,
    input_bytes bigint NOT NULL CHECK (input_bytes > 0),
    state text NOT NULL DEFAULT 'WAITING' CHECK (state IN ('WAITING','DONE','FAILED')),
    result jsonb,
    result_hash text,
    result_bytes bigint NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    UNIQUE(run_id, call_id)
);
CREATE INDEX IF NOT EXISTS hyd_classroom_tool_io_pending ON hyd_classroom_tool_io(run_id,state,created_at,id);
REVOKE ALL ON hyd_classroom_tool_io FROM PUBLIC, anon, authenticated;
ALTER TABLE hyd_classroom_tool_io ENABLE ROW LEVEL SECURITY;
