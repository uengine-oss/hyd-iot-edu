"""PostgreSQL business SELECT contract, adapted from neo4j-text2sql SQLGuard.

AST validation complements (never replaces) a dedicated DB reader, read-only
transactions and timeouts. CTEs resolve in their own scope; physical tables are
qualified to ent. SQL string contents are data, not keywords to strip.
"""
from __future__ import annotations

import sqlglot
from sqlglot import exp
from sqlglot.optimizer.normalize_identifiers import normalize_identifiers
from sqlglot.optimizer.scope import traverse_scope

MAX_ROWS = 200
# Deliberate SQL-call surface: aggregates, numeric/text/date/JSON operations.
# Unknown/application/system functions require an explicit contract extension.
READ_FUNCTIONS = frozenset("""
ABS AVG CEIL CEILING FLOOR ROUND TRUNC MOD POWER SQRT EXP LN LOG SIGN
COUNT SUM MIN MAX STDDEV STDDEV_POP STDDEV_SAMP VARIANCE VAR_POP VAR_SAMP
COALESCE NULLIF GREATEST LEAST CASE IF CAST TRY_CAST AND OR NOT
LOWER UPPER LENGTH CHAR_LENGTH CHARACTER_LENGTH OCTET_LENGTH
CONCAT CONCAT_WS SUBSTRING LEFT RIGHT TRIM LTRIM RTRIM REPLACE SPLIT_PART
POSITION STR_POSITION STRPOS STARTS_WITH ENDS_WITH LIKE ILIKE
DATE_TRUNC TIMESTAMP_TRUNC EXTRACT DATE_PART CURRENT_DATE CURRENT_TIMESTAMP
CURRENT_TIME NOW AGE TO_CHAR TO_DATE TO_TIMESTAMP DATE_ADD DATE_SUB DATEDIFF
ROW_NUMBER RANK DENSE_RANK LAG LEAD FIRST_VALUE LAST_VALUE NTILE
BOOL_AND BOOL_OR LOGICAL_AND LOGICAL_OR ARRAY_AGG STRING_AGG GROUP_CONCAT
JSON_EXTRACT JSON_EXTRACT_SCALAR JSONB_EXTRACT JSONB_EXTRACT_SCALAR
JSON_BUILD_OBJECT JSONB_BUILD_OBJECT JSON_AGG JSONB_AGG
""".split())


class SqlRejected(ValueError):
    pass


def guard(sql: str, max_rows: int = MAX_ROWS, *, schema: str = 'ent', tables=None, functions=READ_FUNCTIONS) -> str:
    """Return one normalized SELECT/UNION, with an outer row limit; reject effects."""
    if not isinstance(sql, str) or not sql.strip() or len(sql) > 64000:
        raise SqlRejected('a nonempty SQL statement of at most 64000 characters is required')
    if type(max_rows) is not int or not 1 <= max_rows <= MAX_ROWS:
        raise SqlRejected('invalid row limit')
    try:
        statements = sqlglot.parse(sql, read='postgres')
        if len(statements) != 1 or not isinstance(statements[0], (exp.Select, exp.SetOperation)):
            raise SqlRejected('one SELECT or SELECT set operation only')
        tree = normalize_identifiers(statements[0], dialect='postgres')
        forbidden = (exp.Insert, exp.Update, exp.Delete, exp.Create, exp.Drop,
                     exp.Alter, exp.Command, exp.Into, exp.Lock, exp.Copy,
                     exp.Grant, exp.Revoke, exp.Transaction)
        for node in tree.walk():
            if isinstance(node, forbidden):
                raise SqlRejected(f'operation is not a business read: {node.key}')
            if isinstance(node, exp.DataType) and node.this == exp.DataType.Type.USERDEFINED:
                raise SqlRejected('user-defined cast types are not allowed')
            if isinstance(node, exp.Func):
                name = node.name.upper() if isinstance(node, exp.Anonymous) else node.sql_name()
                if name not in functions:
                    raise SqlRejected(f'function is not permitted: {name}')
                if isinstance(node.parent, exp.Dot) and node.parent.this.name != 'pg_catalog':
                    raise SqlRejected('application-qualified functions are not allowed')
        # Scope distinguishes physical tables from CTE and derived-table names.
        for scope in traverse_scope(tree):
            for _, source in scope.selected_sources.values():
                if isinstance(source, exp.Table):
                    if (not isinstance(source.this, exp.Identifier) or source.catalog
                            or source.db not in ('', schema) or (tables is not None and source.name not in tables)):
                        raise SqlRejected(f'only permitted physical tables in the {schema} schema are allowed')
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
        raise SqlRejected(f'unsupported or invalid SQL: {exc}') from exc
