"""Dedicated reader connections — the business reader (MCP · current-source verification) and the time-series reader
(data fabric) are checked the same way: the connection must be that unprivileged role, or it is refused."""
import psycopg


class ReaderRoleRefused(RuntimeError):
    """The connection is not the dedicated unprivileged reader. `role` = required, `actual` = what the DSN logged in as.
    Callers that show a person a sentence judge by this type (hydcommon.fabric.failure_reason), never by its text."""
    def __init__(self, role, actual):
        super().__init__(f'{role} required: this connection is {actual or "unknown"} — use the dedicated unprivileged reader')
        self.role, self.actual = role, actual


def reader_connection(dsn, role='hyd_enterprise_reader'):
    """A read connection that is exactly `role` without superuser · createrole · createdb · bypassrls; anything else raises."""
    conn = psycopg.connect(dsn, autocommit=False, connect_timeout=5)
    try:
        row = conn.execute('select current_user, rolsuper, rolcreaterole, rolcreatedb, rolbypassrls '
                           'from pg_roles where rolname=current_user').fetchone()
        if row != (role, False, False, False, False):
            raise ReaderRoleRefused(role, row[0] if row else None)
        conn.rollback()
        return conn
    except Exception:
        conn.close()
        raise
