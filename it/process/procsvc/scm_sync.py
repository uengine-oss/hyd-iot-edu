"""A089 (R05 · DoD 4, 회의 L63~79): SCM master data the rules read from the graph follows the business database.

The graph holds a copy of supplier facts (Supplier.avl drives rule:avl; Part -SUPPLIED_BY-> Supplier carries the quote)
that was seeded once and never synced: ent.suppliers already had sup:c for the cooler core while the graph did not, and
an AVL withdrawal in SCM would have left the graph saying "approved". Following process-gpt-strategy `ontology_sync`
(poll the source, apply only the difference, MERGE idempotently, remove what the source removed, never link to a missing
target), ent is the owner:
- every ent supplier → Supplier {id} name · avl (MERGE),
- quotes of the parts ent holds → SUPPLIED_BY price · failRate · leadDays; such an edge with no source row is removed,
- quotes of parts ent does not hold (graph seed only) are left alone and reported, not deleted.
"""
from __future__ import annotations

SUPPLIERS_SQL = "select id, name, avl, part_no, price, fail_rate, lead_d from ent.suppliers order by id"
GRAPH_SUPPLIERS_Q = "MATCH (s:Supplier) RETURN s.id AS id, s.name AS name, s.avl AS avl"
GRAPH_QUOTES_Q = """MATCH (p:Part)-[x:SUPPLIED_BY]->(s:Supplier)
RETURN p.partNo AS part, s.id AS supplier, x.price AS price, x.failRate AS failRate, x.leadDays AS leadDays"""
GRAPH_PARTS_Q = "MATCH (p:Part) RETURN p.partNo AS part"
SET_SUPPLIER_Q = "UNWIND $rows AS r MERGE (s:Supplier {id: r.id}) SET s.name = r.name, s.avl = r.avl RETURN count(s) AS n"
SET_QUOTE_Q = """UNWIND $rows AS r MATCH (p:Part {partNo: r.part}), (s:Supplier {id: r.supplier})
MERGE (p)-[x:SUPPLIED_BY]->(s) SET x.price = r.price, x.failRate = r.failRate, x.leadDays = r.leadDays RETURN count(x) AS n"""
DELETE_QUOTE_Q = """UNWIND $rows AS r MATCH (:Part {partNo: r.part})-[x:SUPPLIED_BY]->(:Supplier {id: r.supplier}) DELETE x RETURN count(*) AS n"""


def _num(v):
    return None if v is None else float(v)


def plan(source: list[dict], graph_suppliers: list[dict], graph_quotes: list[dict], graph_parts: set[str]) -> dict:
    """Pure: the writes that make the graph match ent, plus what is reported but not touched."""
    have = {s['id']: s for s in graph_suppliers}
    suppliers = {}
    for r in source:
        suppliers[r['id']] = {'id': r['id'], 'name': r['name'], 'avl': bool(r['avl'])}
    set_suppliers = [s for s in suppliers.values()
                     if s['id'] not in have or have[s['id']].get('avl') is not s['avl'] or have[s['id']].get('name') != s['name']]
    owned = {r['part_no'] for r in source}
    want = {(r['part_no'], r['id']): {'part': r['part_no'], 'supplier': r['id'], 'price': _num(r['price']),
                                       'failRate': _num(r['fail_rate']), 'leadDays': r['lead_d']} for r in source}
    current = {(q['part'], q['supplier']): q for q in graph_quotes}
    set_quotes, missing_part = [], []
    for key, q in want.items():
        if q['part'] not in graph_parts:
            missing_part.append(key)                         # no dangling edge to a part the ontology does not have
            continue
        c = current.get(key)
        if c is None or (_num(c.get('price')), _num(c.get('failRate')), c.get('leadDays')) != (q['price'], q['failRate'], q['leadDays']):
            set_quotes.append(q)
    delete_quotes = [{'part': p, 'supplier': s} for (p, s) in current if p in owned and (p, s) not in want]
    graph_only = sorted(f'{p}/{s}' for (p, s) in current if p not in owned)
    return {'set_suppliers': set_suppliers, 'set_quotes': set_quotes, 'delete_quotes': delete_quotes,
            'missing_part': [f'{p}/{s}' for p, s in missing_part], 'graph_only': graph_only}


def sync(q, connect) -> dict:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(SUPPLIERS_SQL)
        cols = [d.name for d in cur.description]
        source = [dict(zip(cols, row)) for row in cur.fetchall()]
    p = plan(source, q(GRAPH_SUPPLIERS_Q), q(GRAPH_QUOTES_Q), {r['part'] for r in q(GRAPH_PARTS_Q)})
    if p['set_suppliers']:
        q(SET_SUPPLIER_Q, rows=p['set_suppliers'])
    if p['set_quotes']:
        q(SET_QUOTE_Q, rows=p['set_quotes'])
    if p['delete_quotes']:
        q(DELETE_QUOTE_Q, rows=p['delete_quotes'])
    return {'source_rows': len(source), 'changed': len(p['set_suppliers']) + len(p['set_quotes']) + len(p['delete_quotes']), **p}
