"""PostgreSQL CREATE TABLE metadata. Parse SQL structure, never execute uploads.

Uses SQLGlot at the version pinned by the reference neo4j-text2sql repository.
Connection identity belongs to the caller, not the uploaded filename.
"""
from __future__ import annotations

import re
import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError
from sqlglot.tokens import TokenType


def identifier(node: exp.Identifier) -> str:
    return node.name if node.args.get('quoted') else node.name.lower()


def quoted(name: str) -> str:
    if not isinstance(name, str) or not name or '\x00' in name:
        raise ValueError('비어 있거나 잘못된 SQL 식별자')
    return '"' + name.replace('"', '""') + '"'


def display_identifier(name: str) -> str:
    return name if re.fullmatch(r'[a-z_][a-z0-9_]*', name) else quoted(name)


def statement_groups(text: str):
    """Token boundaries preserve semicolons inside literals and quoted names."""
    try:
        tokens = sqlglot.tokenize(text, read='postgres')
    except SqlglotError as error:
        raise ValueError(f'DDL 구문 오류: {error}') from error
    groups, current = [], []
    for token in tokens:
        if token.token_type == TokenType.SEMICOLON:
            if current:
                groups.append(current)
            current = []
        else:
            current.append(token)
    if current:
        groups.append(current)
    return groups


def create_tables(text: str):
    """Yield supported table ASTs; other migration statements are not executed."""
    for group in statement_groups(text):
        if group[0].token_type != TokenType.CREATE:
            continue
        # CREATE [TEMPORARY|UNLOGGED] TABLE. Other CREATE types are irrelevant.
        head = [t.text.upper() for t in group[:4]]
        if 'TABLE' not in head:
            continue
        source = text[group[0].start:group[-1].end + 1]
        try:
            tree = sqlglot.parse_one(source, read='postgres')
        except SqlglotError as error:
            raise ValueError(f'DDL 구문 오류: {error}') from error
        if not isinstance(tree, exp.Create) or tree.kind != 'TABLE' or not isinstance(tree.this, exp.Schema):
            raise ValueError('열 정의가 있는 CREATE TABLE만 지원합니다')
        if not isinstance(tree.this.this, exp.Table) or tree.args.get('expression'):
            raise ValueError('CREATE TABLE AS는 지원하지 않습니다')
        header = next((t.comments for t in group if t.token_type == TokenType.L_PAREN), [])
        yield tree.this, ' '.join(c.strip() for c in header)


def source_comments(text: str):
    """Explicit PostgreSQL COMMENT ON TABLE/COLUMN, including clear (IS NULL)."""
    for group in statement_groups(text):
        if len(group)<3 or group[0].token_type!=TokenType.COMMENT or group[2].text.upper() not in ('TABLE','COLUMN'):
            continue
        source=text[group[0].start:group[-1].end+1]
        clear=group[-1].token_type==TokenType.NULL
        # SQLGlot 27.24.2 rejects valid COMMENT ... IS NULL. Parse the same
        # target with an empty literal, then retain the explicit clear marker.
        if clear: source=text[group[0].start:group[-1].start]+"''"
        try:
            tree=sqlglot.parse_one(source,read='postgres')
        except SqlglotError as error:
            raise ValueError(f'원천 주석 구문 오류: {error}') from error
        value=tree.args.get('expression')
        if not isinstance(tree,exp.Comment) or not isinstance(value,exp.Literal) or not value.is_string:
            raise ValueError('원천 주석은 문자열 또는 NULL이어야 합니다')
        target=tree.this
        if target.args.get('catalog'):
            raise ValueError('주석의 데이터베이스는 연결 정보로 지정하세요')
        schema=identifier(target.args['db']) if target.args.get('db') else 'public'
        kind=tree.args['kind'].upper()
        table=identifier(target.this if kind=='TABLE' else target.args['table'])
        column=identifier(target.this) if kind=='COLUMN' else None
        yield schema,table,column,'' if clear else value.this
