"""Real read-only Neo4j timeout and connection reuse checks; no plant changes."""
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / p) for p in ('common', 'it/agent', 'it/detector')]
os.environ.setdefault('NEO4J_URI', 'bolt://127.0.0.1:7687')
os.environ.setdefault('KG_TEMPLATES', str(ROOT / 'it/neo4j/templates'))

from agentsvc.tools.mcp_kg import KnowledgeGraph
from det import pattern_source


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=False)
    checks = []
    kg = KnowledgeGraph()
    original = pattern_source.QUERY
    slow = 'UNWIND range(1, 1000000000) AS x RETURN sum(sin(x)) AS total'
    try:
        for name, invoke in (
            ('agent_transaction_timeout', lambda: kg._run('_timeout_probe')),
            ('catalog_transaction_timeout', lambda: pattern_source.read_patterns(kg.driver)),
        ):
            kg._cache['_timeout_probe'] = slow
            pattern_source.QUERY = slow
            started = time.monotonic()
            try:
                invoke()
            except Exception as exc:
                elapsed = time.monotonic() - started
                code = getattr(exc, 'code', '')
                checks.append(dict(name=name, passed='TransactionTimedOut' in code and elapsed < 15,
                                   elapsed=elapsed, error=type(exc).__name__, code=code))
            else:
                checks.append(dict(name=name, passed=False, error='query was not terminated'))
            finally:
                pattern_source.QUERY = original
        rows = pattern_source.read_patterns(kg.driver)
        checks.append(dict(name='catalog_recovers_after_timeout', passed=len(rows) >= 3, count=len(rows)))
        rows = kg.patterns()
        checks.append(dict(name='agent_recovers_after_timeout', passed=len(rows) >= 3, count=len(rows)))
    finally:
        pattern_source.QUERY = original
        kg.driver.close()
        (out / 'checks.json').write_text(json.dumps(checks, indent=2), encoding='utf-8')
    print(json.dumps(checks, indent=2))
    return 0 if checks and all(c['passed'] for c in checks) else 1


if __name__ == '__main__':
    raise SystemExit(main())
