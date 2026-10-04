from procsvc.skill_graph import fingerprint, stamp


def test_review_ignores_incidental_row_order_but_preserves_procedure_order():
    row={'id':'skill:one','failureModes':[{'id':'b'},{'id':'a'}],
         'steps':[{'order':1,'text':'stop'},{'order':2,'text':'repair'}],
         'actions':[{'code':'STOP'},{'code':'REPAIR'}]}
    revision=stamp([row])[0]['revision']
    assert stamp([dict(row,failureModes=list(reversed(row['failureModes'])))])[0]['revision']==revision
    assert stamp([dict(row,actions=list(reversed(row['actions'])))])[0]['revision']!=revision
    assert stamp([dict(row,steps=list(reversed(row['steps'])))])[0]['revision']!=revision


def test_receipt_identity_preserves_ordered_create_input():
    assert fingerprint({'steps':['stop','repair']})!=fingerprint({'steps':['repair','stop']})
