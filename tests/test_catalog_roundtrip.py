"""Source identity and meaning survive metadata -> DDL -> selected inputs."""
from copy import deepcopy

import pytest

from enterprise_mcp.catalog import render
from procsvc.ingest import parse_ddl, plan


def catalog():
    return {'catalog':'postgres','schema':'ent','relations':[
        {'name':'Order "book"','kind':'r','comment':"MES: O'Brien;\norigin /* x */",'constraints':[],
         'columns':[{'name':'select','type':'numeric(10,3)','nullable':False,'default':'0',
                     'comment':"hours (h); O'Brien\nactual source"}]}]}


def test_source_comments_and_quoted_identity_roundtrip():
    data=catalog(); table=parse_ddl(render(data))[0]
    assert (table.schema,table.name,table.comment)==('ent','Order "book"',data['relations'][0]['comment'])
    c=table.columns[0]
    assert (c.name,c.type,c.comment,c.default,c.nullable)==('select','numeric(10,3)',data['relations'][0]['columns'][0]['comment'],'0',False)


def test_view_is_not_misrepresented_as_a_physical_table():
    data=catalog(); view=deepcopy(data['relations'][0]);view.update(name='current orders',kind='v')
    data['relations'].append(view)
    assert [t.name for t in parse_ddl(render(data))]==['Order "book"']


def test_comment_clear_and_duplicate_follow_statement_order():
    ddl='''create table ent.t (x text /* inline */);
    comment on column ent.t.x is 'first'; comment on column ent.t.x is NULL;
    comment on table ent.t is 'old'; comment on table ent.t is 'new';'''
    table=parse_ddl(ddl)[0]
    assert table.comment=='new' and table.columns[0].comment==''


def test_comments_do_not_guess_schema_or_case():
    ddl='''create table ent."T" ("X" text);
    comment on column public."T"."X" is 'another source';
    comment on column ent."T"."X" is 'correct source';'''
    assert parse_ddl(ddl)[0].columns[0].comment=='correct source'
    with pytest.raises(ValueError,match='주석 대상 열'):
        parse_ddl('create table ent.t (x text); comment on column ent.t.y is \'missing\';')


def test_comments_never_execute_quoted_sql():
    data=catalog();data['relations'][0]['comment']="'; DROP TABLE ent.t; --"
    assert parse_ddl(render(data))[0].comment=="'; DROP TABLE ent.t; --"


def test_selected_input_keeps_units_and_complete_source_meaning():
    data=catalog(); source=data['relations'][0]['columns'][0]['comment']
    result=plan(parse_ddl(render(data)),filename='catalog.sql',batch='test')
    assert result['inputs'][0]['name']==source
