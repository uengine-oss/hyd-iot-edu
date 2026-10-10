"""T4 학생 업무 표 읽기 MCP 서버 출발본 (전체 과정 랩업 G5 — docs/handoff/verification/2026-10-09/capstone-lab.md 5.2 · 6.1).

내 업무 표(Postgres 스키마 stu_<내ID>)를 에이전트가 읽게 하는 서버. 읽기만 한다 — 도구 셋 모두 readOnlyHint=true 표시라
포털 도구(MCP) 화면의 연결 검사를 바로 통과하고, 에이전트 도구로 고를 수 있다(쓰기는 사람 승인 뒤 process 몫).
뼈대는 수업 업무 DB 서버(it/enterprise-mcp/enterprise_mcp/server.py)와 같다: FastMCP · streamable HTTP · {result, document} 봉투 ·
읽기 전용 트랜잭션 · 시간 제한 · 전용 읽기 계정 확인 · /healthz. 고칠 곳은 환경 변수뿐이다(스키마 이름 · 접속 · 포트).

  pip install "fastmcp==2.13.0.2" "psycopg[binary]==3.2.3" "uvicorn[standard]==0.34.0"
  STUDENT_DSN=postgresql://stu_s01_reader:<암호>@127.0.0.1:54322/postgres STUDENT_SCHEMA=stu_s01 MCP_PORT=8311 python server.py
  포털 도구(MCP) → 서버 등록: HTTP, 주소 http://host.docker.internal:8311/mcp — 접속 암호는 이 서버의 환경 변수(STUDENT_DSN)에만
  있고 포털 설정에는 들어가지 않는다. 서버에 토큰 헤더를 두려면 포털 헤더에 ${SECRET:이름} 을 쓴다(G2).
  STUDENT_DSN · STUDENT_SCHEMA 는 기본값이 없다 — 빠졌거나 T3 DDL 의 자리표시자 암호(change-me) 그대로면 뜨지 않고 이유를 말한다.

도구
  list_tables()                                   내 스키마의 표 · 뷰와 주석
  describe_table(table)                           칸 이름 · 자료형 · 주석 · 기본 키
  read_rows(table, columns?, where?, limit?)      행 읽기. where 는 {칸: 값} 같음 조건만(AND), 값은 매개변수로 — SQL 문장을 받지 않는다
표 · 칸 이름은 그때그때 시스템 목록(pg_class · pg_attribute)에서 읽은 이름과 대조한다(목록에 없는 이름은 거절). STUDENT_TABLES 를 주면 그 표만.
"""
from __future__ import annotations

import os
import re
from typing import Annotated, Any, Callable

import psycopg
from psycopg import sql
from pydantic import Field

MAX_ROWS = 200                      # read_rows 한 번에 돌려주는 최대 행 수
TIMEOUT_MS = 5000                   # 문장 하나의 시간 제한(밀리초)
CONNECT_TIMEOUT_S = 5               # 접속 시간 제한(초)
ERROR_TEXT_MAX = 200                # 오류 봉투에 싣는 DB 메시지 최대 글자 수
DEFAULT_PORT = 8311
PLACEHOLDER_PASSWORD = "change-me"  # T3 DDL(table.sql)의 자리표시자 암호
SCHEMA_RE = re.compile(r"^stu_[a-z0-9_]{1,40}$")
READ = {"readOnlyHint": True, "destructiveHint": False}        # MCP ToolAnnotations — 포털 · 워커 게이트가 읽기 도구로 인정하는 표시


def ok(document) -> dict:
    return {"result": "ok", "document": document}


def error(kind: str, message: str) -> dict:
    """kind: INVALID(입력 거절) | UNKNOWN(DB · 연결) — 수업 업무 DB 서버와 같은 낱말."""
    return {"result": "error", "error_kind": kind, "message": message}


class Rejected(ValueError):
    pass


def _first_line(e: Exception) -> str:
    text = str(e)
    return text.splitlines()[0][:ERROR_TEXT_MAX] if text else type(e).__name__


def config_from_env(env=os.environ) -> dict:
    """서버 설정. 계약 값(STUDENT_DSN · STUDENT_SCHEMA)이 없으면 기본값으로 뜨지 않고 무엇을 넣을지 말하며 멈춘다."""
    missing = [k for k in ("STUDENT_DSN", "STUDENT_SCHEMA") if not env.get(k)]
    if missing:
        raise SystemExit(f"환경 변수 {' · '.join(missing)} 가 없습니다 — 예: STUDENT_DSN=postgresql://stu_s01_reader:<암호>@127.0.0.1:54322/postgres "
                         "STUDENT_SCHEMA=stu_s01")
    if f":{PLACEHOLDER_PASSWORD}@" in env["STUDENT_DSN"]:
        raise SystemExit(f"STUDENT_DSN 의 암호가 T3 DDL 자리표시자({PLACEHOLDER_PASSWORD}) 그대로입니다 — table.sql 에서 바꾼 암호를 넣으세요")
    return {"dsn": env["STUDENT_DSN"], "schema": env["STUDENT_SCHEMA"],
            "allowed": [t.strip() for t in env.get("STUDENT_TABLES", "").split(",") if t.strip()],
            "port": int(env.get("MCP_PORT") or DEFAULT_PORT)}


def connect_reader(dsn: str):
    """읽기 전용 계정인지 확인한 연결. 슈퍼유저 · 역할 만들기 · DB 만들기 · RLS 우회 권한이 있으면 거절한다(수업 hydcommon.enterprise 와 같은 규칙)."""
    conn = psycopg.connect(dsn, autocommit=False, connect_timeout=CONNECT_TIMEOUT_S)
    try:
        row = conn.execute("select rolsuper, rolcreaterole, rolcreatedb, rolbypassrls from pg_roles where rolname = current_user").fetchone()
        if row != (False, False, False, False):
            raise RuntimeError("읽기 전용 계정으로 접속해야 합니다 (T3 DDL 의 stu_<ID>_reader) — 지금 계정에 슈퍼유저 · 역할 · DB 만들기 · RLS 우회 권한이 있습니다")
        conn.rollback()
        return conn
    except Exception:
        conn.close()
        raise


class TableReader:
    """도구의 실제 일. connect 는 연결을 돌려주는 함수(시험은 가짜 연결을 넣는다)."""

    def __init__(self, connect: Callable[[], Any], schema: str, allowed: list[str] | None = None,
                 timeout_ms: int = TIMEOUT_MS, max_rows: int = MAX_ROWS):
        if not isinstance(schema, str) or not SCHEMA_RE.match(schema):
            raise SystemExit(f"STUDENT_SCHEMA={schema!r} — stu_<내ID> 꼴이어야 합니다")
        self.connect, self.schema, self.allowed = connect, schema, list(allowed or [])
        self.timeout_ms, self.max_rows = timeout_ms, max_rows

    def _begin(self, cur) -> None:
        cur.execute("set transaction read only")
        cur.execute(sql.SQL("set local statement_timeout = {}").format(sql.Literal(int(self.timeout_ms))))

    def _tables(self, cur) -> dict[str, dict]:
        cur.execute("select c.relname, case c.relkind when 'v' then 'view' else 'table' end, obj_description(c.oid, 'pg_class') "
                    "from pg_class c join pg_namespace n on n.oid = c.relnamespace "
                    "where n.nspname = %s and c.relkind in ('r', 'v', 'p') order by c.relname", (self.schema,))
        out = {name: {"name": name, "kind": kind, "comment": comment} for name, kind, comment in cur.fetchall()}
        return {k: v for k, v in out.items() if not self.allowed or k in self.allowed}

    def _columns(self, cur, table: str) -> list[dict]:
        cur.execute("select a.attname, format_type(a.atttypid, a.atttypmod), col_description(a.attrelid, a.attnum), "
                    "coalesce((select true from pg_index i where i.indrelid = a.attrelid and i.indisprimary and a.attnum = any(i.indkey)), false) "
                    "from pg_attribute a join pg_class c on c.oid = a.attrelid join pg_namespace n on n.oid = c.relnamespace "
                    "where n.nspname = %s and c.relname = %s and a.attnum > 0 and not a.attisdropped order by a.attnum",
                    (self.schema, table))
        return [{"name": n, "type": t, "comment": c, "primary_key": bool(pk)} for n, t, c, pk in cur.fetchall()]

    def _table(self, cur, table) -> str:
        tables = self._tables(cur)
        if not isinstance(table, str) or table not in tables:
            raise Rejected(f"'{table}' 표가 {self.schema} 에 없습니다 (있는 표: {', '.join(tables) or '없음'})")
        return table

    def _limit(self, limit) -> int:
        if limit is None:
            return self.max_rows
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= self.max_rows:
            raise Rejected(f"limit 은 1~{self.max_rows} 사이 정수여야 합니다 (지금 {limit!r})")
        return limit

    def list_tables(self) -> dict:
        with self.connect() as conn, conn.cursor() as cur:
            self._begin(cur)
            return ok({"schema": self.schema, "tables": list(self._tables(cur).values())})

    def describe_table(self, table: str) -> dict:
        with self.connect() as conn, conn.cursor() as cur:
            self._begin(cur)
            name = self._table(cur, table)
            return ok({"schema": self.schema, "table": name, "columns": self._columns(cur, name)})

    def read_rows(self, table: str, columns: list[str] | None = None, where: dict | None = None, limit: int | None = None) -> dict:
        n = self._limit(limit)
        if columns is not None and not (isinstance(columns, list) and all(isinstance(c, str) for c in columns)):
            raise Rejected(f"columns 는 칸 이름 목록이어야 합니다 (지금 {columns!r})")
        if where is not None and not isinstance(where, dict):
            raise Rejected("where 는 {칸 이름: 값} 객체여야 합니다")
        with self.connect() as conn, conn.cursor() as cur:
            self._begin(cur)
            name = self._table(cur, table)
            known = [c["name"] for c in self._columns(cur, name)]
            pick = list(dict.fromkeys(columns or known))
            unknown = [c for c in pick + list((where or {}).keys()) if c not in known]
            if unknown:
                raise Rejected(f"{name} 에 없는 칸: {', '.join(map(str, unknown))} (있는 칸: {', '.join(known)})")
            stmt = sql.SQL("select {cols} from {schema}.{table}").format(
                cols=sql.SQL(", ").join(sql.Identifier(c) for c in pick), schema=sql.Identifier(self.schema), table=sql.Identifier(name))
            params: list = []
            if where:
                stmt += sql.SQL(" where ") + sql.SQL(" and ").join(
                    sql.SQL("{} is not distinct from %s").format(sql.Identifier(k)) for k in where)
                params += list(where.values())
            stmt += sql.SQL(" limit %s")
            params.append(n + 1)                    # 한 행 더 읽어 잘렸는지 안다
            cur.execute(stmt, params)
            rows = cur.fetchall()
        more = len(rows) > n
        return ok({"schema": self.schema, "table": name, "columns": pick, "rows": [dict(zip(pick, r)) for r in rows[:n]],
                   "row_count": min(len(rows), n), "truncated": more})


def guarded(fn):
    """거절은 INVALID, DB · 연결 · 계정 문제는 UNKNOWN 봉투로. 그 밖의 예외는 삼키지 않고 그대로 올린다(도구 오류로 보인다)."""
    def run(*a, **kw):
        try:
            return fn(*a, **kw)
        except Rejected as e:
            return error("INVALID", str(e))
        except (psycopg.Error, RuntimeError, OSError) as e:
            return error("UNKNOWN", f"database: {_first_line(e)}")
    return run


def build(reader: TableReader):
    """FastMCP 서버. 도구 이름 · 설명은 에이전트가 읽는 글이다 — 내 업무 말로 고쳐도 된다(이름은 쓰기 낱말 없이)."""
    from fastmcp import FastMCP
    mcp = FastMCP(f"student-table-reader-{reader.schema}", instructions=(
        f"내 업무 표({reader.schema})를 읽는 도구다. 읽기만 한다 — 바꾸는 일은 사람이 승인한 뒤 시스템 task 가 한다. "
        "먼저 list_tables 로 표를, describe_table 로 칸을 보고 read_rows 로 필요한 행만 읽는다."))

    @mcp.tool(annotations=READ)
    def list_tables() -> dict:
        """내 업무 스키마의 표 · 뷰 목록과 주석."""
        return guarded(reader.list_tables)()

    @mcp.tool(annotations=READ)
    def describe_table(table: Annotated[str, Field(description="표 이름 (list_tables 결과)")]) -> dict:
        """표의 칸 이름 · 자료형 · 주석 · 기본 키."""
        return guarded(reader.describe_table)(table)

    @mcp.tool(annotations=READ)
    def read_rows(table: Annotated[str, Field(description="표 이름")],
                  columns: Annotated[list[str] | None, Field(description="읽을 칸(비우면 전부)")] = None,
                  where: Annotated[dict[str, Any] | None, Field(description="{칸: 값} 같음 조건(AND). 비우면 조건 없음")] = None,
                  limit: Annotated[int | None, Field(description=f"최대 행 수 1~{MAX_ROWS} (비우면 {MAX_ROWS})")] = None) -> dict:
        """표의 행 읽기 — {result: ok, document: {columns, rows, row_count, truncated}}. 거절은 error_kind INVALID, DB 오류는 UNKNOWN."""
        return guarded(reader.read_rows)(table, columns, where, limit)

    @mcp.custom_route("/healthz", methods=["GET"])
    async def healthz(_request):
        from starlette.responses import JSONResponse
        try:
            with reader.connect() as c:
                readonly = c.execute("show transaction_read_only").fetchone()[0]
            return JSONResponse({"ok": True, "schema": reader.schema, "session_read_only": readonly})
        except (psycopg.Error, RuntimeError, OSError) as e:
            return JSONResponse({"ok": False, "error": _first_line(e)}, status_code=503)

    return mcp


if __name__ == "__main__":
    cfg = config_from_env()
    server = build(TableReader(lambda: connect_reader(cfg["dsn"]), cfg["schema"], cfg["allowed"]))
    server.run(transport="http", host="0.0.0.0", port=cfg["port"], path="/mcp", uvicorn_config={"ws": "none"})
