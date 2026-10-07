"""Re-export of the shared read-only SQL guard. The guard itself lives in common/hydcommon/sql_read.py (one implementation
for enterprise-mcp `query` and the agent's mcp_tsdb); this module keeps the `enterprise_mcp.sql_guard` import path the
tests, docs and server use."""
from hydcommon.sql_read import MAX_ROWS, READ_FUNCTIONS, SqlRejected, guard

__all__ = ["MAX_ROWS", "READ_FUNCTIONS", "SqlRejected", "guard"]
