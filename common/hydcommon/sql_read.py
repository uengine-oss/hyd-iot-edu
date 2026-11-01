"""PostgreSQL read-only SELECT contract, adapted from neo4j-text2sql SQLGuard.

AST validation complements (never replaces) a dedicated DB reader, read-only transactions and timeouts. CTEs resolve in their
own scope; physical tables are qualified to the source's schema. SQL string contents are data, not keywords to strip.

Function names are compared the way sqlglot normalises them (postgres dialect), not as typed: TO_CHAR is TIME_TO_STR,
TO_DATE STR_TO_DATE, TO_TIMESTAMP STR_TO_TIME / UNIX_TO_TIME, DATE_TRUNC TIMESTAMP_TRUNC, POSITION · STRPOS STR_POSITION,
BOOL_AND LOGICAL_AND, STRING_AGG GROUP_CONCAT, JSON_AGG J_S_O_N_ARRAY_AGG, VAR_POP VARIANCE_POP, NOW CURRENT_TIMESTAMP.
Some sqlglot "functions" are syntax, not calls, and are part of an ordinary read: EXISTS (…), ARRAY[…] (and = ANY(ARRAY[…])),
`~` / `!~` (REGEXP_LIKE), jsonb `?` (JSONB_CONTAINS), `@>` (ARRAY_CONTAINS_ALL), CASE, CAST.
A cast may only name a built-in type: object-identifier types (::regclass · ::regproc · ::regrole …) would reveal which
system objects exist, so any type sqlglot does not know as a standard type is refused.
Refusals are SqlRejected with a sentence that names what was refused (agents and students read it).
"""
from __future__ import annotations

import sqlglot
from sqlglot import exp
from sqlglot.optimizer.normalize_identifiers import normalize_identifiers
from sqlglot.optimizer.scope import traverse_scope

MAX_ROWS = 200
# Deliberate SQL-call surface: aggregates, numeric/text/date/JSON operations — in sqlglot's normalised names (module docstring).
# Unknown/application/system functions require an explicit contract extension.
READ_FUNCTIONS = frozenset("""
ABS AVG CEIL FLOOR ROUND TRUNC POWER SQRT EXP LN LOG SIGN
COUNT SUM MIN MAX STDDEV STDDEV_POP STDDEV_SAMP VARIANCE VARIANCE_POP PERCENTILE_CONT PERCENTILE_DISC
COALESCE NULLIF GREATEST LEAST
LOWER UPPER LENGTH OCTET_LENGTH CONCAT CONCAT_WS SUBSTRING LEFT RIGHT TRIM REPLACE SPLIT_PART STR_POSITION STARTS_WITH
TIMESTAMP_TRUNC EXTRACT CURRENT_DATE CURRENT_TIMESTAMP CURRENT_TIME AGE TIME_TO_STR STR_TO_DATE STR_TO_TIME UNIX_TO_TIME
ROW_NUMBER RANK DENSE_RANK LAG LEAD FIRST_VALUE LAST_VALUE NTILE
LOGICAL_AND LOGICAL_OR ARRAY_AGG GROUP_CONCAT
JSON_EXTRACT JSON_EXTRACT_SCALAR JSONB_EXTRACT JSONB_EXTRACT_SCALAR JSON_BUILD_OBJECT JSONB_BUILD_OBJECT J_S_O_N_ARRAY_AGG JSONB_AGG
JSON_ARRAY_LENGTH JSONB_ARRAY_LENGTH
""".split())
TIMESERIES_FUNCTIONS = READ_FUNCTIONS | {'TIME_BUCKET'}       # the TimescaleDB readers (tag_1s · feat_1s · tag_1m)
SYNTAX = (exp.And, exp.Or, exp.Not, exp.Case, exp.If, exp.Cast, exp.TryCast, exp.Exists, exp.Array, exp.RegexpLike, exp.JSONBContains, exp.ArrayContainsAll)
_FORBIDDEN = (exp.Insert, exp.Update, exp.Delete, exp.Create, exp.Drop, exp.Alter, exp.Command, exp.Into, exp.Lock, exp.Copy,
              exp.Grant, exp.Revoke, exp.Transaction)


class SqlRejected(ValueError):
    pass


def guard(sql: str, max_rows: int = MAX_ROWS, *, schema: str = 'ent', tables=None, functions=READ_FUNCTIONS) -> str:
    """Return one normalized SELECT/UNION, with an outer row limit; reject effects."""
    if not isinstance(sql, str) or not sql.strip() or len(sql) > 64000:
        raise SqlRejected('조회문(SQL) 한 개가 필요합니다(64,000자 이하)')
    if type(max_rows) is not int or not 1 <= max_rows <= MAX_ROWS:
        raise SqlRejected(f'행 수 한도는 1~{MAX_ROWS} 사이 정수여야 합니다')
    try:
        statements = sqlglot.parse(sql, read='postgres')
        if len(statements) != 1 or not isinstance(statements[0], (exp.Select, exp.SetOperation)):
            raise SqlRejected('SELECT 조회 하나(또는 UNION 으로 묶은 SELECT)만 쓸 수 있습니다')
        tree = normalize_identifiers(statements[0], dialect='postgres')
        for node in tree.walk():
            if isinstance(node, _FORBIDDEN):
                raise SqlRejected(f'읽기가 아닌 동작은 쓸 수 없습니다: {node.key}')
            if isinstance(node, exp.DataType) and (not isinstance(node.this, exp.DataType.Type)
                                                   or node.this == exp.DataType.Type.USERDEFINED):
                raise SqlRejected(f'기본 자료형이 아닌 형식으로 바꿀 수 없습니다: {node.sql(dialect="postgres")}')
            if isinstance(node, exp.Func) and not isinstance(node, SYNTAX):
                name = node.name.upper() if isinstance(node, exp.Anonymous) else node.sql_name()
                if name not in functions:
                    raise SqlRejected(f'허용되지 않은 함수입니다: {name}')
                if isinstance(node.parent, exp.Dot) and node.parent.this.name != 'pg_catalog':
                    raise SqlRejected('함수 앞에 스키마 이름을 붙일 수 없습니다')
        # Scope distinguishes physical tables from CTE and derived-table names.
        for scope in traverse_scope(tree):
            for _, source in scope.selected_sources.values():
                if isinstance(source, exp.Table):
                    if (not isinstance(source.this, exp.Identifier) or source.catalog
                            or source.db not in ('', schema) or (tables is not None and source.name not in tables)):
                        raise SqlRejected(f'{schema} 스키마의 허용된 표만 읽을 수 있습니다: {source.sql(dialect="postgres")}')
                    source.set('db', exp.to_identifier(schema))
        limit = tree.args.get('limit')
        value = (limit.args.get('count') if isinstance(limit, exp.Fetch) else limit.expression) if limit is not None else None
        count = max_rows
        if isinstance(value, exp.Literal) and value.is_int:
            count = min(max_rows, max(0, int(value.this)))
        tree = tree.limit(count)
        return tree.sql(dialect='postgres', comments=False)
    except SqlRejected:
        raise
    except (sqlglot.errors.SqlglotError, ValueError, TypeError) as exc:
        raise SqlRejected(f'읽을 수 없는 SQL 입니다: {exc}') from exc
