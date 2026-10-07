"""A089: supplier master data the rules read from the graph follows ent (process-gpt-strategy ontology_sync pattern)."""
from decimal import Decimal

from procsvc import scm_sync

SOURCE = [dict(id='sup:a', name='A', avl=False, part_no='P-CLR-CORE', price=Decimal('180'), fail_rate=Decimal('0.12'), lead_d=3),
          dict(id='sup:b', name='B', avl=True, part_no='P-CLR-CORE', price=Decimal('260'), fail_rate=Decimal('0.02'), lead_d=5),
          dict(id='sup:c', name='C', avl=False, part_no='P-CLR-CORE', price=Decimal('120'), fail_rate=Decimal('0.20'), lead_d=2)]
GRAPH_SUPPLIERS = [dict(id='sup:a', name='A', avl=True), dict(id='sup:b', name='B', avl=True), dict(id='sup:c', name='C', avl=False)]
GRAPH_QUOTES = [dict(part='P-CLR-CORE', supplier='sup:a', price=180, failRate=0.12, leadDays=3),
                dict(part='P-CLR-CORE', supplier='sup:b', price=250, failRate=0.02, leadDays=5),
                dict(part='P-CLR-CORE', supplier='sup:x', price=99, failRate=0.5, leadDays=9),     # ent no longer has it
                dict(part='P-PMP-SEAL', supplier='sup:b', price=55, failRate=0.02, leadDays=5)]    # part ent does not hold


def test_plan_applies_only_differences_and_never_deletes_what_ent_does_not_own():
    p = scm_sync.plan(SOURCE, GRAPH_SUPPLIERS, GRAPH_QUOTES, {'P-CLR-CORE', 'P-PMP-SEAL'})
    assert p['set_suppliers'] == [{'id': 'sup:a', 'name': 'A', 'avl': False}]                         # AVL withdrawn in SCM
    assert {(q['supplier'], q['price']) for q in p['set_quotes']} == {('sup:b', 260.0), ('sup:c', 120.0)}  # changed + missing
    assert p['delete_quotes'] == [{'part': 'P-CLR-CORE', 'supplier': 'sup:x'}]
    assert p['graph_only'] == ['P-PMP-SEAL/sup:b'] and p['missing_part'] == []


def test_no_edge_to_a_part_the_ontology_lacks_and_second_plan_is_empty():
    p = scm_sync.plan(SOURCE, GRAPH_SUPPLIERS, [], set())
    assert p['set_quotes'] == [] and len(p['missing_part']) == 3
    synced = [dict(part=r['part_no'], supplier=r['id'], price=float(r['price']), failRate=float(r['fail_rate']), leadDays=r['lead_d']) for r in SOURCE]
    again = scm_sync.plan(SOURCE, [dict(id=r['id'], name=r['name'], avl=r['avl']) for r in SOURCE], synced, {'P-CLR-CORE'})
    assert not again['set_suppliers'] and not again['set_quotes'] and not again['delete_quotes']
