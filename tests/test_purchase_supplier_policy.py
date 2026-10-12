"""Dynamic source policies bind real quotes without rewriting the original SOP."""
from copy import deepcopy

import pytest

from hydcommon.skill_scope import purchase_shape, resolve_supplier
from procsvc import manual_graph, manual_knowledge
from dmn_mcp.tools import enveloped
from test_purchase_scope_model import source_proposal, catalog, checked_plan, link, runtime_skill
from test_purchase_part_route import part_pipeline
from test_purchase_candidate_scope import pipeline
from agentsvc import cards, approval, decide, guardrail
from procsvc import effect_parts
from test_cards import R, T, DMN, FC


def quotes():
    return {'sup:a':dict(name='A정밀 (대체)',price=10,lead_d=3,fail_rate=.06,avl=True),
            'sup:b':dict(name='B-OEM (순정)',price=20,lead_d=5,fail_rate=.02,avl=True),
            'sup:c':dict(name='C트레이딩',price=9,lead_d=1,fail_rate=.12,avl=False)}


def policy_skill(policy):
    skill=runtime_skill()
    skill.update(supplier_policy=policy,supplierParts=[],
                 partSuppliers=[dict(part='part:kit',supplier=s) for s in quotes()])
    skill['actions'][0]['value']=None
    return skill


@pytest.mark.parametrize('policy,supplier',[('oem','sup:b'),('lowest_approved','sup:a'),('fastest_quote','sup:c')])
def test_policy_resolves_real_quote_preserves_source_and_fastest_unapproved(policy,supplier):
    skill=policy_skill(policy); facts=dict(purchase_part='part:kit',spare_part_no='P-KIT',spare_quotes=quotes())
    original=deepcopy((skill,facts))
    bound=resolve_supplier(skill,facts)
    assert bound['actions'][0]['value']==supplier
    assert bound['resolvedSupplier']['quoteSet']==facts['spare_quotes']
    assert bound['resolvedSupplier']['quote']['avl'] is (supplier!='sup:c')
    assert (skill,facts)==original


@pytest.mark.parametrize('change', ['missing_quotes','missing_relation','tied','unknown_oem','bad_avl','fixed_together'])
def test_policy_never_guesses_missing_or_ambiguous_source(change):
    skill=policy_skill('fastest_quote');facts=dict(purchase_part='part:kit',spare_quotes=quotes())
    if change=='missing_quotes':facts['spare_quotes']={}
    if change=='missing_relation':skill['partSuppliers']=[]
    if change=='tied':facts['spare_quotes']['sup:a']['lead_d']=1
    if change=='unknown_oem':
        skill['supplier_policy']='oem';facts['spare_quotes']['sup:b']['name']='arbitrary OEM'
    if change=='bad_avl':facts['spare_quotes']['sup:c']['avl']='false'
    if change=='fixed_together':skill['actions'][0]['value']='sup:b'
    with pytest.raises(ValueError):resolve_supplier(skill,facts)


def test_policy_shape_reference_and_fixed_modes_are_distinct():
    body=link();body.update(supplier_policy='oem');body['actions'][0]['value']=None
    assert purchase_shape(body,source_backed=True)['supplier_policy']=='oem'
    for invalid in [dict(body,executable=False,actions=[]),dict(body,actions=[dict(action='action:purchase-request',value='sup:b')])]:
        with pytest.raises(ValueError):purchase_shape(invalid,source_backed=True)
    assert 'supplier_policy' not in purchase_shape(link(),source_backed=True)


def test_policy_survives_source_plan_graph_and_current_catalog_validation(source_proposal,catalog):
    archive,_,body=source_proposal
    body['links']['SOP-PUR-11']['supplier_policy']='oem'
    body['links']['SOP-PUR-11']['actions'][0]['value']=None
    catalog['parts'][0]['suppliers'][0]['name']='B-OEM (순정)'
    plan=checked_plan(archive,body,catalog)
    snap=manual_graph.desired(plan)
    skill=next(n['props'] for n in snap['nodes'] if 'Skill' in n['labels'])
    assert skill['supplier_policy']=='oem'
    assert next(r['props'] for r in snap['edges'] if r['type']=='CONSISTS_OF').get('value') is None
    catalog['parts'][0]['suppliers']=[]
    assert 'PURCHASE_SUPPLIER_PART_MISMATCH' in {i['code'] for i in manual_knowledge.graph_semantics(plan,catalog)[1]}


@pytest.mark.parametrize('submit',[False,True])
def test_actual_pipeline_policy_binding_is_in_submitted_action_and_evidence(part_pipeline,submit):
    tools,skills,facts,_,_,submitted=part_pipeline
    skills['skill:purchase'].update(policy_skill('oem'))
    facts['spare_quotes']=quotes()
    result=enveloped(tools.submit_purchase if submit else tools.evaluate_purchase)('HYD-03','P-KIT',*(('INC-C',) if submit else ()))
    assert result['result']=='ok',result
    option=result['document']['result']['options'][0]
    assert option['actions'][0]['value']=='sup:b'
    assert option['resolvedSupplier']['id']=='sup:b'
    assert skills['skill:purchase']['actions'][0]['value'] is None
    if submit: assert submitted[0]['options'][0]['resolvedSupplier']==option['resolvedSupplier']


def test_fastest_policy_keeps_losing_unapproved_alternative_for_compliance():
    skill=policy_skill('fastest_quote')
    rules=deepcopy(DMN)+[R('dec:action-candidates','rule:purchase','SELECT',
                          [T('pattern','==','SPARE_BELOW_MIN')],['skill:purchase']),
                         R('dec:compliance','rule:avl','EXCLUDE',[T('supplier_avl','==',False)])]
    facts=dict(pattern='SPARE_BELOW_MIN',purchase_part='part:kit',spare_part_no='P-KIT',
               spare_quotes=quotes(),need_qty=2,need_by_days=6)
    result=cards.evaluate(rules,{'skill:purchase':skill},facts,FC,[],[],{})
    option=result['options'][0]
    assert option['actions'][0]['value']=='sup:c'
    assert any(v['rule']=='rule:avl' for v in option['violations'])
    assert result['recommended'] is None


def test_approval_matches_binding_and_requires_new_evaluation_when_any_quote_changes():
    skill=resolve_supplier(policy_skill('oem'),dict(purchase_part='part:kit',spare_part_no='P-KIT',spare_quotes=quotes()))
    rows=[dict(supplier=s,**q) for s,q in quotes().items()]
    values=dict(part_no='P-KIT',need_qty=2)
    approved=effect_parts.purchase_quote(skill,values,rows)
    assert approved['approved_supplier']=='sup:b' and approved['approved_amount']==40
    rows[0]['price']=1
    with pytest.raises(ValueError,match='변경'):effect_parts.purchase_quote(skill,values,rows)
    rows=[dict(supplier=s,**q) for s,q in quotes().items()]
    skill['actions'][0]['value']='sup:a'
    with pytest.raises(ValueError,match='증거'):effect_parts.purchase_quote(skill,values,rows)


def test_three_original_parts_are_preserved_and_each_policy_binds_per_part():
    skill=policy_skill('fastest_quote')
    skill['parts']=['part:pump-seal','part:fan-bearing','part:cooler-core']
    skill['partSuppliers']=[dict(part=p,supplier=s) for p in skill['parts'] for s in ('sup:a','sup:b')]
    skill['partSuppliers'].append(dict(part='part:pump-seal',supplier='sup:c'))
    original=deepcopy(skill)
    for part in skill['parts']:
        qs=quotes()
        if part!='part:pump-seal':qs.pop('sup:c')
        bound=resolve_supplier(skill,dict(purchase_part=part,spare_quotes=qs))
        assert bound['actions'][0]['value']==('sup:c' if part=='part:pump-seal' else 'sup:a')
    assert skill==original


def test_policy_purchase_preview_and_final_assessment_keep_explicit_part_route(part_pipeline,monkeypatch):
    tools,skills,facts,_,_,submitted=part_pipeline
    skills['skill:purchase'].update(policy_skill('oem'));facts['spare_quotes']=quotes()
    monkeypatch.setattr(decide,'gather_facts',lambda inputs,asset,known,tsdb,**kwargs:(dict(deepcopy(facts),**known),[]))
    monkeypatch.setattr(tools.kg,'purchase_part',lambda number:dict(id='part:kit',partNo=number,name='씰 키트'),raising=False)
    monkeypatch.setattr(tools.kg,'roles',lambda:[dict(id='role:purchasing',name='구매 담당',level=1,deptName='구매')])
    result=enveloped(tools.submit_purchase)('HYD-03','P-KIT','INC-C')
    assert result['result']=='ok',result
    original=deepcopy(submitted[0])
    preview=approval.preview(tools.kg,tools.tsdb,original,'skill:purchase',None)
    assert preview['options'][0]['resolvedSupplier']['id']=='sup:b'
    report=approval.assess(tools.kg,tools.tsdb,preview,'skill:purchase','role:purchasing')
    assert report['allowed'],report['reasons']
    facts['spare_quotes']['sup:a']['price']=1
    report=approval.assess(tools.kg,tools.tsdb,preview,'skill:purchase','role:purchasing')
    assert not report['allowed'] and any('resolvedSupplier' in r or 'policy_sha256' in r for r in report['reasons'])
    tampered=deepcopy(original);tampered['origin']['part']['id']='part:other'
    with pytest.raises(ValueError,match='현재 지식'):approval.preview(tools.kg,tools.tsdb,tampered,'skill:purchase',None)


def test_reference_manual_edges_and_old_options_cannot_become_execution():
    ref=runtime_skill();ref.update(kind='reference',executable=False)
    for pattern in ['SPARE_BELOW_MIN','COOLER_DEGRADATION','PM_DUE']:
        assert cards.scoped_skills(pattern,{'skill:reference':ref},'part:kit')=={}
    option=dict(ref,id='skill:reference',selectedBy=['malicious-rule'])
    assert guardrail.check_cards(dict(options=[option],recommended=None))
    with pytest.raises(ValueError,match='참고'):effect_parts.purchase_action(option)
