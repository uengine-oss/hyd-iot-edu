"""Dedicated business reader shared by MCP and current-source verification."""
import psycopg


def reader_connection(dsn):
    conn = psycopg.connect(dsn, autocommit=False, connect_timeout=5)
    try:
        row = conn.execute('select current_user, rolsuper, rolcreaterole, rolcreatedb, rolbypassrls '
                           'from pg_roles where rolname=current_user').fetchone()
        if row != ('hyd_enterprise_reader', False, False, False, False):
            raise RuntimeError('enterprise requires the dedicated unprivileged reader role')
        conn.rollback()
        return conn
    except Exception:
        conn.close()
        raise
