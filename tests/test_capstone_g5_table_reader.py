"""G5 키트 (전체 과정 랩업 — docs/handoff/verification/2026-10-09/capstone-lab.md 5.2 · 6.1 T3 · T4): 학생 업무 표 읽기 MCP 서버 출발본.

수업 스택에 붙이지 않는 출발본(students/_template/mcp_table_reader/server.py)이다. 여기서는 가짜 연결로 본다:
도구 셋이 모두 readOnlyHint=true 라 포털 연결 검사 · 워커 게이트의 읽기 판정(mcp_check.read_only_verdict)을 통과하는가,
읽기 전용 트랜잭션 · 시간 제한을 거는가, 표 · 칸 이름을 목록과 대조하고 값은 매개변수로 넘기는가(SQL 문장을 받지 않는다).
"""
import asyncio
import importlib.util
from pathlib import Path

import pytest

from procsvc import mcp_check

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("student_table_reader", ROOT / "students" / "_template" / "mcp_table_reader" / "server.py")
srv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(srv)

TABLES = [("attendee", "table", "참석자와 응답"), ("meeting", "table", "준비하는 회의")]
COLUMNS = {"meeting": [("id", "text", None, True), ("name", "text", None, False), ("room_seats", "integer", "좌석 수", False)],
           "attendee": [("meeting_id", "text", None, True), ("email", "text", None, True), ("response", "text", None, False)]}
ROWS = [("lead@example.com", "accepted"), ("customer@example.com", "none")]       # select "email", "response" 의 행


class FakeCur:
    def __init__(self, log):
        self.log, self.result = log, []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, stmt, params=None):
        text = stmt if isinstance(stmt, str) else stmt.as_string(None)
        self.log.append((text, params))
        if "from pg_class" in text:
            self.result = TABLES
        elif "from pg_attribute" in text:
            self.result = COLUMNS[params[1]] if params[0] == "stu_s00" else []
        elif text.startswith("select") and "stu_s00" in text:
            self.result = ROWS[: params[-1]]
        else:
            self.result = []

    def fetchall(self):
        return list(self.result)


class FakeConn:
    def __init__(self, log):
        self.log = log

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def cursor(self):
        return FakeCur(self.log)


@pytest.fixture
def reader():
    log = []
    r = srv.TableReader(lambda: FakeConn(log), "stu_s00")
    r.log = log
    return r


def test_every_tool_is_marked_read_only_and_passes_the_portal_read_verdict(reader):
    tools = asyncio.run(srv.build(reader).get_tools())
    assert sorted(tools) == ["describe_table", "list_tables", "read_rows"]
    for name, tool in tools.items():
        notes = tool.annotations.model_dump(exclude_none=True)
        ok, why = mcp_check.read_only_verdict({"name": name, "annotations": notes})
        assert ok, (name, why)


def test_reads_run_in_a_read_only_time_boxed_transaction(reader):
    out = reader.list_tables()
    assert out == {"result": "ok", "document": {"schema": "stu_s00", "tables": [
        {"name": "attendee", "kind": "table", "comment": "참석자와 응답"}, {"name": "meeting", "kind": "table", "comment": "준비하는 회의"}]}}
    assert reader.log[0][0] == "set transaction read only" and "statement_timeout = 5000" in reader.log[1][0]
    assert reader.describe_table("meeting")["document"]["columns"][2] == {"name": "room_seats", "type": "integer", "comment": "좌석 수", "primary_key": False}


def test_read_rows_quotes_names_binds_values_and_reports_truncation(reader):
    out = reader.read_rows("attendee", columns=["email", "response"], where={"meeting_id": "s00:meeting-q3"}, limit=1)
    text, params = reader.log[-1]
    assert text == 'select "email", "response" from "stu_s00"."attendee" where "meeting_id" is not distinct from %s limit %s'
    assert params == ["s00:meeting-q3", 2]                                          # 값은 매개변수, 한 행 더 읽어 잘림을 안다
    assert out["document"]["rows"] == [{"email": "lead@example.com", "response": "accepted"}] and out["document"]["truncated"] is True


@pytest.mark.parametrize("call,phrase", [
    (lambda r: r.read_rows("ent_secret"), "표가 stu_s00 에 없습니다"),
    (lambda r: r.read_rows("meeting", columns=["id; drop table x"]), "없는 칸"),
    (lambda r: r.read_rows("meeting", where={"pwd": "x"}), "없는 칸: pwd"),
    (lambda r: r.read_rows("meeting", limit=500), "limit 은 1~200"),
    (lambda r: r.read_rows("meeting", limit=0), "limit 은 1~200"),                      # 0 을 몰래 최대로 바꾸지 않는다
    (lambda r: r.read_rows("meeting", limit="5"), "limit 은 1~200 사이 정수"),
    (lambda r: r.read_rows("meeting", limit=True), "limit 은 1~200 사이 정수"),
    (lambda r: r.read_rows("meeting", columns="name"), "columns 는 칸 이름 목록"),
    (lambda r: r.read_rows("meeting", where="id = 1"), "where 는"),
    (lambda r: r.read_rows('meeting" ; drop table x; --'), "표가 stu_s00 에 없습니다"),
])
def test_unknown_names_and_bad_inputs_are_refused_before_any_select(reader, call, phrase):
    out = srv.guarded(call)(reader)
    assert out["result"] == "error" and out["error_kind"] == "INVALID" and phrase in out["message"]
    assert not any(t.startswith("select") and "stu_s00" in t for t, _ in reader.log)


def test_only_listed_tables_and_a_student_schema_name():
    log = []
    r = srv.TableReader(lambda: FakeConn(log), "stu_s00", allowed=["meeting"])
    assert [t["name"] for t in r.list_tables()["document"]["tables"]] == ["meeting"]
    assert srv.guarded(r.read_rows)("attendee")["error_kind"] == "INVALID"
    with pytest.raises(SystemExit):
        srv.TableReader(lambda: None, "ent")                                         # 수업 업무 스키마(ent)는 이 서버로 읽지 않는다


def test_ddl_template_makes_a_select_only_reader_for_the_same_schema():
    ddl = (ROOT / "students" / "_template" / "table.sql").read_text(encoding="utf-8")
    assert "create schema if not exists stu_s00" in ddl and "nosuperuser nocreaterole nocreatedb nobypassrls" in ddl
    assert "grant select on all tables in schema stu_s00 to stu_s00_reader" in ddl
    assert "grant insert" not in ddl.lower() and "grant all" not in ddl.lower()


def test_a_columns_query_binds_schema_and_table_as_values():
    log = []
    r = srv.TableReader(lambda: FakeConn(log), "stu_s00")
    r.describe_table("meeting")
    text, params = next((t, p) for t, p in log if "from pg_attribute" in t)
    assert params == ("stu_s00", "meeting") and "meeting" not in text            # 표 이름도 문장이 아니라 값으로


def test_no_limit_means_the_named_maximum_and_duplicate_columns_are_read_once(reader):
    out = reader.read_rows("attendee", columns=["email", "email", "response"])
    assert reader.log[-1][1] == [srv.MAX_ROWS + 1] and out["document"]["columns"] == ["email", "response"]


class BrokenConn(FakeConn):
    def cursor(self):
        cur = FakeCur(self.log)

        def boom(stmt, params=None):
            raise srv.psycopg.errors.QueryCanceled("canceling statement due to statement timeout\nCONTEXT: x")
        cur.execute = boom
        return cur


def test_database_failures_come_back_as_unknown_with_the_reason():
    r = srv.TableReader(lambda: BrokenConn([]), "stu_s00")
    out = srv.guarded(r.list_tables)()
    assert out == {"result": "error", "error_kind": "UNKNOWN", "message": "database: canceling statement due to statement timeout"}

    def refuse():
        raise srv.psycopg.OperationalError("connection refused")
    assert srv.guarded(srv.TableReader(refuse, "stu_s00").read_rows)("meeting")["message"] == "database: connection refused"


class RoleConn:
    def __init__(self, row):
        self.row, self.closed = row, False

    def execute(self, q):
        return self

    def fetchone(self):
        return self.row

    def rollback(self):
        pass

    def close(self):
        self.closed = True


def test_a_privileged_account_is_refused_and_its_connection_closed(monkeypatch):
    conns = []

    def fake_connect(dsn, **kw):
        assert kw["connect_timeout"] == srv.CONNECT_TIMEOUT_S
        conns.append(RoleConn((True, False, False, False)))                         # 슈퍼유저
        return conns[-1]
    monkeypatch.setattr(srv.psycopg, "connect", fake_connect)
    with pytest.raises(RuntimeError, match="읽기 전용 계정으로 접속해야"):
        srv.connect_reader("postgresql://postgres@x/db")
    assert conns[-1].closed
    monkeypatch.setattr(srv.psycopg, "connect", lambda dsn, **kw: RoleConn((False, False, False, False)))
    assert srv.connect_reader("postgresql://stu_s00_reader@x/db").row == (False, False, False, False)


def test_the_server_does_not_start_without_its_contract_settings():
    with pytest.raises(SystemExit, match="STUDENT_DSN · STUDENT_SCHEMA 가 없습니다"):
        srv.config_from_env({})
    with pytest.raises(SystemExit, match="자리표시자"):
        srv.config_from_env({"STUDENT_DSN": "postgresql://stu_s00_reader:change-me@127.0.0.1:54322/postgres", "STUDENT_SCHEMA": "stu_s00"})
    cfg = srv.config_from_env({"STUDENT_DSN": "postgresql://stu_s01_reader:pw@h/db", "STUDENT_SCHEMA": "stu_s01", "STUDENT_TABLES": "meeting, attendee"})
    assert cfg == {"dsn": "postgresql://stu_s01_reader:pw@h/db", "schema": "stu_s01", "allowed": ["meeting", "attendee"], "port": srv.DEFAULT_PORT}


def test_ddl_example_rows_walk_the_unhappy_branches():
    ddl = (ROOT / "students" / "_template" / "table.sql").read_text(encoding="utf-8")
    assert "'customer_review', null, 4)" in ddl                                     # 고객 회의인데 좌석 4 < 6 (좌석 미달)
    assert "'customer@example.com', true, 'none')" in ddl                           # 필수 참석자 무응답(미확정 가지)
