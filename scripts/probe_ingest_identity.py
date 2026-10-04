"""Exercise preview/commit/graph/SQL with two real PostgreSQL schemas.

Creates only unique audit schemas/batches and removes exactly those in finally.
"""
import json
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import argparse

import psycopg
from psycopg import sql
from neo4j import GraphDatabase


def api(path, body=None, method=None):
    req = urllib.request.Request('http://localhost:8080' + path,
        data=None if body is None else json.dumps(body).encode(),
        headers={'Content-Type': 'application/json'}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default='.evidence/reaudit/ingest-identity-live.json')
    args = parser.parse_args()
    suffix = uuid.uuid4().hex[:12]
    schemas = ['reaudit_' + suffix + '_east', 'reaudit_' + suffix + '_west']
    datasource = 'reaudit_' + suffix
    batches, report = [], {'checks': {}, 'schemas': schemas, 'datasource': datasource}
    dest = Path(args.out)
    def check(name, passed, detail=None):
        report['checks'][name] = {'passed': bool(passed), 'detail': detail}
        dest.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(name, 'PASS' if passed else 'FAIL', flush=True)
        assert passed, name
    try:
        with psycopg.connect('postgresql://postgres:postgres@localhost:54322/postgres', autocommit=True) as conn:
            for schema, value in zip(schemas, (2, 20)):
                conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
                conn.execute(sql.SQL('CREATE TABLE {}."Order.Items" (asset text, "Net,Value" numeric, note text default \'a,b;--z\')').format(sql.Identifier(schema)))
                conn.execute(sql.SQL('INSERT INTO {}."Order.Items"(asset,"Net,Value") VALUES (%s,%s)').format(sql.Identifier(schema)), ('AUDIT-01', value))
        ddl = '\n'.join(f'CREATE TABLE "{s}"."Order.Items" (asset text, "Net,Value" numeric, note text default \'a,b;--z\');' for s in schemas)
        status, plan = api('/api/kg/ddl/preview', {'filename': 'changed-company.sql', 'text': ddl, 'datasource': datasource, 'catalog': 'postgres'})
        check('preview_two_schemas', status == 200 and len(plan.get('inputs', [])) == 6, plan)
        check('unique_physical_ids_and_variables', len({i['id'] for i in plan['inputs']}) == 6 and len({i['variable'] for i in plan['inputs']}) == 6)
        batches.append(plan['batch'])
        status, saved = api('/api/kg/ddl/commit', plan)
        check('actual_graph_commit', status == 200 and saved.get('inputs') == 6, saved)
        container = json.loads(subprocess.check_output(['docker', 'inspect', 'hyd-iot-edu-neo4j-1']))[0]
        settings = dict(item.split('=', 1) for item in container['Config']['Env'])
        with GraphDatabase.driver('bolt://localhost:7687', auth=tuple(settings['NEO4J_AUTH'].split('/', 1))) as driver:
            with driver.session() as session:
                rows = session.run('MATCH (i:InputData {datasource:$ds}) RETURN i.schema AS schema, i.catalog AS catalog, i.variable AS variable', ds=datasource).data()
        check('graph_preserves_connection_schema', len(rows) == 6 and {r['schema'] for r in rows} == set(schemas) and all(r['catalog'] == 'postgres' for r in rows), rows)
        chosen = [i for i in plan['inputs'] if i['column'] == 'Net,Value']
        status, generated = api('/api/kg/rules/sql', {'tests': [{'variable': i['variable'], 'operator': '<', 'value': 8} for i in chosen]})
        check('api_sql_keeps_both_sources', status == 200 and len(generated.get('queries', [])) == 2 and not generated['unmapped'], generated)
        actual = []
        with psycopg.connect('postgresql://postgres:postgres@localhost:54322/postgres') as conn:
            for query in generated['queries']:
                params = dict(query['params'], asset='AUDIT-01')
                result = conn.execute(query['sql'], params).fetchall()
                actual.append({'schema': query['schema'], 'rows': [[str(v) for v in row] for row in result]})
        check('real_postgres_values_change_result', [len(r['rows']) for r in actual] == [1, 0], actual)
        broken = dict(plan, inputs=[dict(plan['inputs'][0], schema='wrong-schema')])
        status, error = api('/api/kg/ddl/commit', broken)
        check('modified_identity_rejected', status == 400, error)
        status, error = api('/api/kg/rules/sql', {'tests': [{'variable': chosen[0]['variable'], 'operator': '> 0; DROP TABLE t;--', 'value': 3}]})
        check('invalid_operator_rejected', status == 400, error)
    finally:
        report['cleanup'] = []
        for batch in batches:
            status, result = api('/api/kg/ingests/' + urllib.parse.quote(batch, safe=''), method='DELETE')
            report['cleanup'].append({'batch': batch, 'status': status, 'result': result})
        with psycopg.connect('postgresql://postgres:postgres@localhost:54322/postgres', autocommit=True) as conn:
            for schema in schemas:
                assert schema.startswith('reaudit_' + suffix + '_')
                conn.execute(sql.SQL('DROP SCHEMA IF EXISTS {} CASCADE').format(sql.Identifier(schema)))
        report['temporary_schemas_removed'] = True
        dest.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
