"""연습용 DB(센서 현재 값) 연결."""
from __future__ import annotations

import psycopg
from psycopg.rows import dict_row

from labkit.settings import db_settings


def connect() -> psycopg.Connection:
    """`with connect() as conn: conn.execute(...)` 로 쓴다. 줄은 사전으로 나온다."""
    return psycopg.connect(**db_settings(), row_factory=dict_row, connect_timeout=5)
