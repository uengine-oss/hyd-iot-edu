"""Apply only additive CEP metadata, atomically validating the resulting graph catalog."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'it/detector'), str(ROOT/'common'), str(ROOT/'scripts')]
from neo4j import GraphDatabase
from det.patterns import compile_catalog
from det.pattern_source import QUERY, read_patterns
from ontology_v2 import split_statements


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--uri', default='bolt://127.0.0.1:7687')
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=False)
    def save(name, value):
        (out/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str),encoding='utf8')
    with GraphDatabase.driver(args.uri, auth=('neo4j','hydpass123'), connection_timeout=5) as driver:
        with driver.session() as session:
            before = [r.data() for r in session.run("""MATCH (p:AnomalyPattern)
                WHERE p.id IN ['pattern:cooler-degradation','pattern:pump-leakage','pattern:fan-vibration','pattern:overheat-trip']
                OPTIONAL MATCH (p)-[t:TESTS]->(i:InputData)
                RETURN properties(p) AS pattern, collect({id:i.id,variable:i.variable,test:properties(t)}) AS tests
                ORDER BY pattern.id""")]
            save('before', before)
            if len(before) != 4:
                raise RuntimeError('expected four existing source patterns; no changes applied')
            def migrate(tx):
                for statement in split_statements((ROOT/'it/neo4j/v2/detector-patterns.cypher').read_text(encoding='utf8')):
                    tx.run(statement).consume()
                rows = [dict(r['pattern'],tests=r['tests']) for r in tx.run(QUERY, scope='production')]
                compiled = compile_catalog(rows)
                for code in ('COOLER_DEGRADATION','PUMP_LEAKAGE','FAN_VIBRATION'):
                    if code not in compiled:raise RuntimeError('missing existing pattern '+code)
                return rows
            save('committed', session.execute_write(migrate))
        rows = read_patterns(driver)
        save('reread', rows)
        print(json.dumps({code:p.describe() for code,p in compile_catalog(rows).items()},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
