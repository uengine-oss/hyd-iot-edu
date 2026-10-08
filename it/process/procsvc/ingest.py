"""Ingestion (pure): a company's DB schema (DDL) becomes ontology instances — 회의 2번 (원문2 L253~293).

    "스키마는 경험 있는 자가 만들어 놓고, 인스턴스는 그 회사의 DB 와 SOP 문서로 인제스천한다. 그 과정을 학생에게 알려줘야 한다.
     역으로 인제스천된 것을 빼서 클리어하고 다시 할 수 있어야 한다. DDL 이 있어야 런타임의 T2SQL 도 동작한다."

What the DDL gives the ontology (schema.json, skill layer): one System per source system (MES · ERP · CMMS …, zone IT) and one
InputData per column the lecturer selects, linked InputData -SOURCED_FROM-> System. The InputData's `variable` is the name
the DMN rules test (TESTS), so a rule's threshold can be turned into a SQL query against the very table it came from
(회의 6번, L301~302: "규칙에 해당하는 쿼리를 생성").

This is HYD's limited DDL adapter, not ontology-studio's extraction pipeline.
ontology-studio batch_ingest uses nodes/relationships with _source_id; the
source_id and the graph_ingest ownership journal are HYD conventions. SQLGlot parses PostgreSQL
DDL; physical identity follows datasource/catalog/schema/table/column.
See docs/handoff/AUDIT.md A003/A004 for verified scope and remaining SOP/connection work.
"""
from __future__ import annotations

import re
import hashlib
import json
import uuid
from urllib.parse import quote
from sqlglot import exp
from .ddl import create_tables, identifier, quoted, display_identifier, source_comments
from dataclasses import dataclass, field
from datetime import datetime, timezone

# SQL type → DMN typeRef (InputData.typeRef). A115 (r14 A10): matched on the base type name, not a substring — `interval`
# and `point` contain "int" and were read as numbers. An interval is a duration (no reader accepts it, so a binding to one
# is refused instead of read as a wrong number); an array or json is an object; an unknown type stays a string.
_TYPE_NAMES = {
    "boolean": ("boolean", "bool"),
    "number": ("smallint", "integer", "int", "int2", "int4", "int8", "bigint", "smallserial", "serial", "bigserial", "serial2",
               "serial4", "serial8", "numeric", "decimal", "real", "float", "float4", "float8", "double", "double precision"),
    "date": ("date", "timestamp", "timestamptz", "timestamp with time zone", "timestamp without time zone", "datetime",
             "time", "timetz", "time with time zone", "time without time zone"),
    "object": ("json", "jsonb", "array"),
}
_TYPE_MAP = {name: ref for ref, names in _TYPE_NAMES.items() for name in names}


def type_ref_of(sql_type: str) -> str:
    t = " ".join(re.sub(r"\([^)]*\)", " ", (sql_type or "").lower()).split())
    if t.endswith("[]"):
        return "object"
    if t.startswith("interval"):
        return "duration"
    return _TYPE_MAP.get(t, "string")
# table comment prefix / name hint → System node (existing ontology ids where the v2 instances have them)
_SYSTEM_HINTS = (("MES", "sys:mes", "MES"), ("ERP", "sys:erp", "ERP"), ("CMMS", "sys:cmms", "CMMS"), ("QMS", "sys:qms", "QMS"),
                 ("SCM", "sys:scm", "SCM"), ("EMS", "sys:ems", "EMS"), ("SCADA", "sys:scada", "SCADA"), ("HISTORIAN", "sys:historian", "Historian"))
_AUDIT_COLUMNS = {"created_at", "updated_at", "deleted_at", "id", "uuid"}


@dataclass
class Column:
    name: str
    type: str
    nullable: bool = True
    default: str | None = None
    comment: str = ""
    references: str | None = None
    primary_key: bool = False

    @property
    def type_ref(self) -> str:
        return type_ref_of(self.type)


@dataclass
class Table:
    schema: str
    name: str
    comment: str = ""
    columns: list[Column] = field(default_factory=list)

    @property
    def qualified(self) -> str:
        return f"{display_identifier(self.schema)}.{display_identifier(self.name)}" if self.schema else display_identifier(self.name)

    @property
    def system_hint(self) -> tuple[str, str] | None:
        """(system id, name) from the table comment ('-- MES: …') or the table name."""
        head = (self.comment or "").split(":")[0].strip().upper()
        for key, sid, name in _SYSTEM_HINTS:
            if head == key or (not head and key.lower() in self.name.lower()):
                return sid, name
        return None


# ---------------------------------------------------------------- DDL
def parse_ddl(text: str) -> list[Table]:
    """PostgreSQL table definitions, including quoted identifiers and literals."""
    tables = []
    identities = set()
    for tree, comment in create_tables(text):
        ref = tree.this
        if ref.args.get("catalog"):
            raise ValueError("PostgreSQL DDL의 데이터베이스는 연결 정보로 지정하세요")
        schema = identifier(ref.args["db"]) if ref.args.get("db") else "public"
        table = Table(schema=schema, name=identifier(ref.this), comment=comment)
        key = (table.schema, table.name)
        if key in identities:
            raise ValueError(f"중복 테이블 정의: {table.qualified}")
        identities.add(key)
        names = set()
        primary = set()
        for constraint in tree.expressions:
            if isinstance(constraint, exp.PrimaryKey):
                primary.update(identifier(c) for c in constraint.expressions)
            elif isinstance(constraint, exp.Constraint):
                for pk in constraint.find_all(exp.PrimaryKey):
                    primary.update(identifier(c) for c in pk.expressions)
        for node in tree.expressions:
            if not isinstance(node, exp.ColumnDef):
                continue
            name = identifier(node.this)
            if name in names:
                raise ValueError(f"중복 열 정의: {table.qualified}.{name}")
            names.add(name)
            constraints = [c.args["kind"] for c in node.args.get("constraints", [])]
            pk = name in primary or any(isinstance(c, exp.PrimaryKeyColumnConstraint) for c in constraints)
            default = next((c.this.sql(dialect="postgres") for c in constraints if isinstance(c, exp.DefaultColumnConstraint)), None)
            reference = next((c.this.sql(dialect="postgres").replace(" (", "(") for c in constraints if isinstance(c, exp.Reference)), None)
            kind = node.args.get("kind")
            if kind is None:
                raise ValueError(f"열 형식이 없습니다: {name}")
            sql_type = kind.sql(dialect="postgres").lower().replace(", ", ",")
            sql_type = sql_type.replace("decimal", "numeric")
            table.columns.append(Column(name, sql_type,
                nullable=not pk and not any(isinstance(c, exp.NotNullColumnConstraint) for c in constraints),
                default=default, references=reference, primary_key=pk,
                comment=" ".join(c.strip() for c in (node.comments or []))))
        if not table.columns:
            raise ValueError(f"열이 없는 테이블: {table.qualified}")
        tables.append(table)
    by_identity={(t.schema,t.name):t for t in tables}
    for schema,name,column,comment in source_comments(text):
        table=by_identity.get((schema,name))
        if table is None:
            continue  # Comments for other, existing objects in a migration.
        if column is None:
            table.comment=comment
        else:
            found=next((c for c in table.columns if c.name==column),None)
            if found is None:
                raise ValueError(f'주석 대상 열이 DDL에 없습니다: {schema}.{name}.{column}')
            found.comment=comment
    return tables


# ---------------------------------------------------------------- plan: tables → System · InputData
def default_selection(tables: list[Table]) -> dict[str, list[str]]:
    """Which columns become InputData unless the lecturer edits the preview: business values, not keys or audit stamps."""
    out = {}
    for t in tables:
        cols = [c.name for c in t.columns if not c.primary_key and not c.references and c.name not in _AUDIT_COLUMNS]
        if cols:
            out[t.qualified] = cols
    return out


def new_batch_id(kind: str = "ddl", now: datetime | None = None) -> str:
    return f"ingest:{kind}:{(now or datetime.now(timezone.utc)).strftime('%Y%m%dT%H%M%SZ')}:{uuid.uuid4().hex[:12]}"


def physical_identity(datasource: str, catalog: str, schema: str, table: str, column: str) -> tuple[str, str]:
    parts = (datasource, catalog, schema, table, column)
    if any(not isinstance(p, str) or not p or "\x00" in p for p in parts):
        raise ValueError("원천·데이터베이스·스키마·테이블·열 식별자가 모두 필요합니다")
    canonical = json.dumps(parts, ensure_ascii=False, separators=(",", ":"))
    return "in:db:" + ":".join(quote(p, safe="") for p in parts), "db_" + hashlib.sha256(canonical.encode()).hexdigest()[:24]


def _table_option(options: dict, table: Table, tables: list[Table], default):
    if table.qualified in options:
        return options[table.qualified]
    if table.name in options:
        if sum(t.name == table.name for t in tables) != 1:
            raise ValueError(f"모호한 테이블 이름: {table.name}; 스키마를 지정하세요")
        return options[table.name]
    return default


def plan(tables: list[Table], *, filename: str, batch: str, selection: dict[str, list[str]] | None = None,
         systems: dict[str, str] | None = None, datasource: str = "hyd-enterprise", catalog: str = "postgres") -> dict:
    """Keep physical identity independent of the document and semantic System."""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", datasource or "") or not catalog:
        raise ValueError("유효한 원천 연결 이름과 데이터베이스가 필요합니다")
    selection = selection if selection is not None else default_selection(tables)
    systems = systems or {}
    allowed = {t.qualified for t in tables} | {t.name for t in tables}
    if (set(selection) | set(systems)) - allowed:
        raise ValueError("DDL에 없는 테이블 선택")
    out_systems, inputs, warnings, previews = {}, [], [], []
    for t in tables:
        cols = _table_option(selection, t, tables, [])
        if len(cols) != len(set(cols)):
            raise ValueError(f"중복 선택 열: {t.qualified}")
        hint = t.system_hint
        sid = _table_option(systems, t, tables, hint[0] if hint else "sys:db-" + datasource)
        previews.append({"table": t.qualified, "schema": t.schema, "name": t.name, "comment": t.comment,
                         "system": sid, "columns": [c.name for c in t.columns], "selected": cols})
        if not cols:
            continue
        if not sid or not isinstance(sid, str):
            raise ValueError(f"출처 시스템이 없습니다: {t.qualified}")
        sname = hint[1] if hint and sid == hint[0] else sid.split(":", 1)[-1].upper()
        if not hint and sid.startswith("sys:db-"):
            warnings.append(f"{t.qualified}: 업무 시스템을 확인하세요 ({sid})")
        out_systems.setdefault(sid, {"id": sid, "name": sname, "zone": "IT", "source_id": f"{filename}#{t.qualified}"})
        by_name = {c.name: c for c in t.columns}
        for cname in cols:
            if cname not in by_name:
                raise ValueError(f"{t.qualified}.{cname}: DDL 에 없는 열")
            c = by_name[cname]
            iid, variable = physical_identity(datasource, catalog, t.schema, t.name, c.name)
            item = {"id": iid, "name": input_name(c.comment, t.name, c.name),
                "typeRef": c.type_ref, "variable": variable, "system": sid, "datasource": datasource, "catalog": catalog,
                "schema": t.schema, "table": t.name, "column": c.name, "sqlType": c.type,
                "assetColumn": "asset" if "asset" in by_name else None,
                "source_id": f"{filename}#{t.qualified}.{display_identifier(c.name)}"}
            if is_point_in_time(c.type):
                # A086: a business time (납기 일시 · 출하 일시) reaches the rules as signed hours from now, computed at read
                item.update(typeRef="number", derive=DERIVE_HOURS, name=input_name(c.comment, t.name, c.name, derive=True))
            inputs.append(item)
    return {"batch": batch, "filename": filename, "datasource": datasource, "catalog": catalog,
            "systems": list(out_systems.values()), "inputs": inputs, "warnings": warnings, "tables": previews}


DERIVE_HOURS = "hours_from_now"


def input_name(comment: str, table: str, column: str, *, derive: bool = False) -> str:
    """The InputData name an ingestion gives a column: its comment (the business meaning), else "table column"; a time
    column read as hours from now says so. ddl_sync compares it with the live comment (A115 COMMENT_CHANGED)."""
    name = comment or f"{table} {column}"
    return f"{name} (지금부터 h)" if derive else name


def is_point_in_time(sql_type: str) -> bool:
    return "timestamp" in (sql_type or "").lower()


def derived_sql(src: dict) -> str:
    """The SQL expression a rule tests for this input: the column, or for a point in time its signed hours from now."""
    col = quoted(src["column"])
    if src.get("derive") == DERIVE_HOURS:
        return f"round((extract(epoch from ({col} - now())) / 3600)::numeric, 2)"
    if src.get("derive") is not None:
        raise ValueError("지원하지 않는 입력 환산")
    return col


# ---------------------------------------------------------------- commit contract
def validate_plan(p: dict) -> None:
    if not isinstance(p.get("batch"), str) or not p["batch"] or not isinstance(p.get("filename"), str):
        raise ValueError("배치와 원본 파일 이름이 필요합니다")
    systems = {}
    for item in p["systems"]:
        if set(item) - {"id", "name", "zone", "source_id"}:
            raise ValueError("허용되지 않은 시스템 속성")
        if not all(isinstance(item.get(k), str) and item[k] for k in ("id", "name", "source_id")) or item.get("zone") not in ("IT", "OT"):
            raise ValueError("시스템 식별자/이름/영역/출처를 확인하세요")
        if item["id"] in systems:
            raise ValueError("중복 시스템")
        systems[item["id"]] = item
    seen = set()
    required = ("id", "name", "typeRef", "variable", "datasource", "catalog", "schema", "table", "column", "sqlType", "source_id", "system")
    for item in p["inputs"]:
        if set(item) - set(required) - {"assetColumn", "derive", "represents", "meaningReview"}:
            raise ValueError("허용되지 않은 입력 속성")
        # A9: REPRESENTS target and the review that approved the meaning (main.py checks the review itself)
        for opt in ("represents", "meaningReview"):
            if opt in item and item[opt] is not None and (not isinstance(item[opt], str) or not item[opt]):
                raise ValueError(f"{opt} 값을 확인하세요")
        if "derive" in item and (item["derive"] != DERIVE_HOURS or not is_point_in_time(item.get("sqlType") or "") or item.get("typeRef") != "number"):
            raise ValueError("시각 열만 '지금부터 시간(h)'으로 환산할 수 있습니다")
        if not all(isinstance(item.get(k), str) and item[k] for k in required):
            raise ValueError("입력 데이터의 필수 속성을 확인하세요")
        if item.get("assetColumn") is not None and (not isinstance(item["assetColumn"], str) or not item["assetColumn"]):
            raise ValueError("자산 식별 열을 확인하세요")
        key, variable = physical_identity(*(item[k] for k in ("datasource", "catalog", "schema", "table", "column")))
        if item["id"] != key or item["variable"] != variable or item["system"] not in systems:
            raise ValueError("미리보기의 원천 식별자/변수/시스템이 일치하지 않습니다. 다시 미리보기를 실행하세요")
        if key in seen:
            raise ValueError("중복 입력 데이터")
        seen.add(key)


# ---------------------------------------------------------------- 회의 6번: a rule's threshold tests → the SQL that checks them
def tests_to_sql(tests: list[dict], inputs: dict[str, dict], *, asset_column: str = "asset") -> dict:
    """A parameterized SELECT per physical table/connection, never execute it here."""
    grouped, unmapped = {}, []
    for test in tests:
        src = inputs.get(test.get("variable"))
        if not src or not src.get("table"):
            unmapped.append(test.get("variable"))
            continue
        if not src.get("schema"):
            raise ValueError("원천 스키마가 없는 입력은 다시 적재해야 합니다")
        key = (src.get("datasource"), src.get("catalog"), src["schema"], src["table"])
        if not key[0] or not key[1]:
            raise ValueError("원천 연결/데이터베이스가 없는 입력은 다시 적재해야 합니다")
        grouped.setdefault(key, []).append((src, test))
    queries = []
    for (datasource, catalog, schema, table), rows in grouped.items():
        fields, conditions, params = [], [], {"asset": "<asset>"}
        asset_fields = {src.get("assetColumn", asset_column) for src, _ in rows}
        if len(asset_fields) != 1 or None in asset_fields:
            raise ValueError(f"{schema}.{table}: 자산 식별 열을 명시해야 합니다")
        asset = quoted(asset_fields.pop())
        for src, test in rows:
            col = derived_sql(src)
            fields.append(col)
            op = _sql_op(test.get("operator") or "==")
            value = test.get("value")
            if value is None:
                if op not in ("=", "<>"):
                    raise ValueError("NULL은 같음/다름 연산자만 지원합니다")
                conditions.append(f"{col} IS {'NOT ' if op == '<>' else ''}NULL")
            else:
                if not isinstance(value, (str, bool, int, float)):
                    raise ValueError("SQL 조건 값은 단일 값이어야 합니다")
                param = f"v{len(params) - 1}"
                params[param] = value
                conditions.append(f"{col} {op} %({param})s")
        target = f"{quoted(schema)}.{quoted(table)}"
        selected = ", ".join(dict.fromkeys([asset] + fields))
        queries.append({"datasource": datasource, "catalog": catalog, "schema": schema, "table": table,
            "sql": f"select {selected} from {target} where {asset} = %(asset)s and " + " and ".join(conditions),
            "params": params, "explain": f"{datasource}/{catalog}/{schema}.{table}: 조건 {len(rows)}개를 원천 연결에서 확인"})
    return {"queries": queries, "unmapped": unmapped}


def _sql_op(op: str) -> str:
    ops = {"==": "=", "=": "=", "!=": "<>", "<>": "<>", "<": "<", "<=": "<=", ">": ">", ">=": ">="}
    if op not in ops:
        raise ValueError(f"지원하지 않는 SQL 연산자: {op}")
    return ops[op]
