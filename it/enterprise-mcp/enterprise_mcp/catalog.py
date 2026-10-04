"""Live, reader-visible PostgreSQL metadata; no inferred business meanings.

DDL is a query/ingestion snapshot, not a backup (indexes, policies, partition
bounds, view definitions and source data are not exported).
"""
CATALOG_SQL = """
select jsonb_build_object('catalog', current_database(), 'schema', 'ent',
  'relations', coalesce(jsonb_agg(relation order by name), '[]'::jsonb))
from (
 select c.relname as name, jsonb_build_object(
   'name', c.relname, 'kind', c.relkind, 'comment', obj_description(c.oid, 'pg_class'),
   'columns', coalesce((select jsonb_agg(jsonb_build_object(
     'name', a.attname, 'type', format_type(a.atttypid, a.atttypmod),
     'nullable', not a.attnotnull, 'default', pg_get_expr(d.adbin, d.adrelid),
     'identity', a.attidentity, 'generated', a.attgenerated,
     'comment', col_description(c.oid, a.attnum)) order by a.attnum)
     from pg_attribute a left join pg_attrdef d on d.adrelid=a.attrelid and d.adnum=a.attnum
     where a.attrelid=c.oid and a.attnum>0 and not a.attisdropped), '[]'::jsonb),
   'constraints', coalesce((select jsonb_agg(jsonb_build_object(
     'name', k.conname, 'type', k.contype, 'definition', pg_get_constraintdef(k.oid)) order by k.conname)
     from pg_constraint k where k.conrelid=c.oid and k.contype in ('p','u','f','c','x')), '[]'::jsonb)
 ) as relation
 from pg_class c join pg_namespace n on n.oid=c.relnamespace
 where n.nspname='ent' and c.relkind in ('r','p','v','m','f')
   and has_schema_privilege(n.oid, 'USAGE') and has_table_privilege(c.oid, 'SELECT')
) metadata
"""


def quote(name):
    return '"' + name.replace('"', '""') + '"'


def literal(value):
    # PostgreSQL standard strings; the source DB's text remains data.
    return "'" + value.replace("'", "''") + "'"


def render(catalog):
    statements = ['-- Reader-visible ent metadata. Query/ingestion snapshot, not a database backup.']
    for table in catalog['relations']:
        target = quote(catalog['schema']) + '.' + quote(table['name'])
        columns = []
        for c in table['columns']:
            field = quote(c['name']) + ' ' + c['type']
            if c.get('identity'):
                field += ' generated ' + ('always' if c['identity']=='a' else 'by default') + ' as identity'
            elif c.get('generated'):
                field += ' generated always as (' + c['default'] + ') stored'
            elif c.get('default') is not None:
                field += ' default ' + c['default']
            if not c['nullable']:
                field += ' not null'
            columns.append('  ' + field)
        if table['kind'] not in ('r','p'):
            # Do not invent a CREATE TABLE for a view, materialized view, or
            # foreign relation. Structured metadata preserves its real kind.
            import json
            statements.append('-- non-table relation ' + json.dumps(
                {'name':table['name'],'kind':table['kind'],'columns':table['columns']},ensure_ascii=False))
            continue
        columns.extend('  constraint '+quote(c['name'])+' '+c['definition'] for c in table['constraints'])
        statements.append('create table '+target+' (\n'+',\n'.join(columns)+'\n);')
        if table['comment'] is not None:
            statements.append('comment on table '+target+' is '+literal(table['comment'])+';')
        for c in table['columns']:
            if c['comment'] is not None:
                statements.append('comment on column '+target+'.'+quote(c['name'])+' is '+literal(c['comment'])+';')
    return '\n\n'.join(statements)
