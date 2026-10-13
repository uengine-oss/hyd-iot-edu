"""PR7.4 total cost from immutable source, actual quotes, and exact Part scope."""
from copy import deepcopy
from pathlib import Path
import pytest
from agentsvc import cards
from hydcommon.purchase_comparison import compare, policy
from test_cards import DMN,R,T,FC
from test_purchase_scope_model import runtime_skill
from test_purchase_part_route import part_pipeline
from test_purchase_candidate_scope import pipeline

SOURCE=Path(__file__).resolve().parents[1]/'문서/시스템/참조/수업_문서_원문/PR-07_spare-parts-standard.md'
QUOTE=SOURCE.read_text(encoding='utf-8').split('## PR-7.4 공급사 비교 기준\n')[1].split('## PR-7.5')[0].strip()
def contract():
    return dict(version=1,loss_per_failure=250,inspection_threshold=.1,inspection_cost=20,
                anchor=dict(source_id='source',quote=QUOTE))
def data():
    skills={}
    for supplier in ('a','b','c'):
        k=runtime_skill();k.update(skillId='skill:'+supplier,sopId='SOP-'+supplier,purchase_comparison_policy=contract())
        k['actions'][0]['value']='sup:'+supplier
        skills[k['skillId']]=k
    facts=dict(pattern='SPARE_BELOW_MIN',purchase_part='part:kit',need_qty=6,need_by_days=6,
               order_due_h=3,order_penalty_per_h=100,
               spare_quotes={'sup:a':dict(price=35,fail_rate=.12,lead_d=3,avl=True),
                   'sup:b':dict(price=55,fail_rate=.02,lead_d=5,avl=True),
                   'sup:c':dict(price=30,fail_rate=.18,lead_d=1,avl=False)})
    rules=[R('dec:action-candidates','r:buy','SELECT',[T('pattern','==','SPARE_BELOW_MIN')],list(skills)),
           R('dec:compliance','r:avl','EXCLUDE',[T('supplier_avl','==',False)]),
           R('dec:compliance','r:lead','WARN',[T('lead_slack_days','<',0)]),
           deepcopy(DMN[3]),deepcopy(DMN[-1])]
    return skills,facts,rules
def run(skills,facts,rules,forecast=40):
    fc={sid:{'sv:ts1':dict(variableName='유온',value=forecast,unit='℃',method='physical',id='fc')} for sid in skills}
    return cards.evaluate(rules,skills,facts,fc,[],[],{}, {sid:dict(error='no physical model') for sid in skills},evaluation_mode='execution')
def test_original_source_410_vs_360_and_avl_exclusion():
    skills,facts,rules=data();before=deepcopy((skills,facts,rules));r=run(skills,facts,rules)
    assert r['recommended']=='skill:b'
    options={o['id']:o for o in r['options']}
    assert options['skill:a']['economicComparison']['total_cost']==410
    assert options['skill:b']['economicComparison']['total_cost']==360
    assert options['skill:c']['feasible'] is False
    assert options['skill:b']['scoreParts']=={'purchase_total_cost':-360}
    assert options['skill:b']['forecast']==[]
    assert (skills,facts,rules)==before
    assert '비교 총비용 360만 원' in r['explanation']
def test_physical_values_cannot_change_purchase_rank_or_cost():
    skills,facts,rules=data();a=run(skills,facts,rules,40)
    facts.update(order_due_h=0,order_penalty_per_h=99999,hot_lot_claim=999,hot_lot_qty=999)
    b=run(skills,facts,rules,999)
    assert [(o['id'],o['score'],o['feasible']) for o in a['options']]==[(o['id'],o['score'],o['feasible']) for o in b['options']]
@pytest.mark.parametrize('change',['price','quantity','fail_rate','lead','avl'])
def test_actual_quote_changes_are_recomputed(change):
    skills,facts,rules=data();old=run(skills,facts,rules)
    if change=='price':facts['spare_quotes']['sup:a']['price']=1
    if change=='quantity':facts['need_qty']=1
    if change=='fail_rate':facts['spare_quotes']['sup:a']['fail_rate']=0
    if change=='lead':facts['spare_quotes']['sup:b']['lead_d']=7
    if change=='avl':facts['spare_quotes']['sup:b']['avl']=False
    new=run(skills,facts,rules)
    assert new['options']!=old['options']
    if change in ('price','fail_rate','avl'):assert new['recommended']=='skill:a'
    if change=='lead':assert next(o for o in new['options'] if o['id']=='skill:b')['warnings']
@pytest.mark.parametrize('field',['price','fail_rate','lead_d','avl'])
def test_missing_actual_quote_never_falls_back(field):
    skills,facts,rules=data();facts['spare_quotes']['sup:a'].pop(field)
    with pytest.raises(ValueError):run(skills,facts,rules)
def test_source_numbers_and_scope_cannot_be_fabricated():
    skills,facts,rules=data()
    for field in ('loss_per_failure','inspection_threshold','inspection_cost'):
        bad=contract();bad[field]=0
        with pytest.raises(ValueError):policy(bad)
    skills['skill:a'].pop('purchase_comparison_policy')
    with pytest.raises(ValueError):run(skills,facts,rules)
    skills,facts,rules=data();facts['purchase_part']='part:other'
    with pytest.raises(ValueError):compare(skills['skill:a'],facts)

def test_nonapproved_supplier_does_not_claim_source_inspection_and_cross_source_rejects():
    skills,facts,rules=data()
    assert compare(skills['skill:c'],facts)['inspection_cost']==0
    skills['skill:a']['purchase_comparison_policy']['anchor']['source_id']='other-source'
    with pytest.raises(ValueError,match='원문 판본'):run(skills,facts,rules)
def test_purchase_does_not_require_or_apply_physical_ranking_table():
    skills,facts,rules=data();rules=[r for r in rules if r['decision']!='dec:rank-actions']
    assert run(skills,facts,rules)['recommended']=='skill:b'

def test_review_policy_anchor_survives_source_graph_and_rejects_false_quote(tmp_path):
    import json
    from procsvc import manual_review,manual_graph
    from procsvc.manual_sources import ManualSources
    from test_purchase_scope_model import TEXT,link
    archive=ManualSources(tmp_path/'manuals.sqlite')
    source=archive.save('hyd','purchase.md',(TEXT+'\n'+QUOTE).encode())
    body=manual_review.proposal(source)
    pc=contract();start=source['pages'][0]['text'].index(QUOTE)
    pc['anchor']=dict(source_id=source['source_id'],page=1,start=start,end=start+len(QUOTE),quote=QUOTE)
    body.update(by='test:source-contract',reviewed=True,links={'SOP-PUR-11':dict(link(),purchase_comparison_policy=pc)})
    original=deepcopy(body);plan=manual_review.validate(archive,'hyd',body)
    skill=next(n['props'] for n in manual_graph.desired(plan)['nodes'] if 'Skill' in n['labels'])
    preserved=json.loads(skill['purchase_comparison_policy'])
    assert preserved['loss_per_failure']==250 and preserved['anchor']['source_id']==source['source_id']
    assert source['pages'][0]['text'][preserved['anchor']['start']:preserved['anchor']['end']]==QUOTE
    assert body==original
    body['links']['SOP-PUR-11']['purchase_comparison_policy']['anchor']['quote']=QUOTE+' invented'
    with pytest.raises(ValueError):manual_review.validate(archive,'hyd',body)

def test_current_preview_preserves_history_and_actual_cost_change_blocks_approval(part_pipeline,monkeypatch):
    from agentsvc import approval,decide,forecasting
    from dmn_mcp.tools import enveloped
    tools,skills,facts,_,_,submitted=part_pipeline
    monkeypatch.setattr(decide,'gather_facts',lambda inputs,asset,known,tsdb,**kwargs:(dict(deepcopy(facts),**known),[]))
    monkeypatch.setattr(tools.kg,'purchase_part',lambda number:dict(id='part:kit',partNo=number,name='씰 키트'),raising=False)
    monkeypatch.setattr(tools.kg,'roles',lambda:[dict(id='role:purchasing',level=1,name='구매 담당',deptName='구매')])
    monkeypatch.setattr(forecasting,'candidates',lambda *args:pytest.fail('purchase must not read physical forecasts'))
    result=enveloped(tools.submit_purchase)('HYD-03','P-KIT','INC-C')
    assert result['result']=='ok',result
    original=deepcopy(submitted[0]);before=deepcopy(original)
    preview=approval.preview(tools.kg,tools.tsdb,original,'skill:purchase',{})
    assert original==before and preview['options'][0]['economicComparison']['total_cost']==27
    assert approval.assess(tools.kg,tools.tsdb,preview,'skill:purchase','role:purchasing')['allowed']
    facts['spare_quotes']['sup:b']['fail_rate']=.12
    report=approval.assess(tools.kg,tools.tsdb,preview,'skill:purchase','role:purchasing')
    assert not report['allowed'] and any('economicComparison' in reason for reason in report['reasons'])
