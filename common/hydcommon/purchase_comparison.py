"""Source-defined purchasing cost, independent of physical plant forecasts."""
import json
import math
import re
from decimal import Decimal


def policy(value):
    if isinstance(value,str):value=json.loads(value)
    if not isinstance(value,dict) or type(value.get('version')) is not int or value.get('version')!=1:
        raise ValueError('구매 총비용 비교의 검토된 원문 정책이 없습니다')
    result=dict(value)
    for field in ('loss_per_failure','inspection_threshold','inspection_cost'):
        x=value.get(field)
        if type(x) not in (int,float) or not math.isfinite(x) or x<0:
            raise ValueError('구매 총비용 정책의 실제 수치가 필요합니다: '+field)
    if not 0<=value['inspection_threshold']<=1:
        raise ValueError('전수 검사 불량률 기준은 0부터1 사이입니다')
    anchor=value.get('anchor')
    if not isinstance(anchor,dict) or not anchor.get('source_id') or not anchor.get('quote'):
        raise ValueError('구매 총비용 정책의 원문 판본과 인용이 필요합니다')
    quote=anchor['quote']
    patterns={'loss_per_failure':r'불량\s*1건\s*손실.*?([\d.]+)\s*만\s*원',
              'inspection_threshold':r'불량률이\s*([\d.]+)\s*%',
              'inspection_cost':r'전수\s*검사\s*비용\s*([\d.]+)\s*만\s*원'}
    for field,pattern in patterns.items():
        found=re.search(pattern,quote)
        expected=float(found[1])/(100 if field=='inspection_threshold' else 1) if found else None
        if expected is None or expected!=value[field]:
            raise ValueError('구매 비교 수치가 원문 인용과 다릅니다: '+field)
    return result


def compare(skill,facts):
    contract=policy(skill.get('purchase_comparison_policy'))
    if contract['anchor']['source_id']!=skill.get('source_id'):
        raise ValueError('구매 비교 정책과 SOP의 원문 판본이 다릅니다')
    part=facts.get('purchase_part')
    if not part or part not in (skill.get('parts') or []):
        raise ValueError('구매 비교의 실제 부품이 검토된 원문 범위에 없습니다')
    actions=[a for a in skill.get('actions') or [] if a.get('code')=='PR_CREATE']
    if len(actions)!=1 or not actions[0].get('value'):
        raise ValueError('구매 비교에는 확정된 공급사 발주 Action 하나가 필요합니다')
    supplier=actions[0]['value'];quote=(facts.get('spare_quotes') or {}).get(supplier)
    if not isinstance(quote,dict) or type(quote.get('avl')) is not bool:
        raise ValueError('구매 비교의 실제 공급사 견적·AVL을 확인할 수 없습니다')
    values={**quote,'quantity':facts.get('need_qty'),'need_by_days':facts.get('need_by_days')}
    for field in ('price','fail_rate','lead_d','quantity','need_by_days'):
        x=values.get(field)
        if type(x) not in (int,float) or not math.isfinite(x) or x<0:
            raise ValueError('구매 비교의 실제 필수 수치를 확인할 수 없습니다: '+field)
    if values['quantity']<=0 or not 0<=values['fail_rate']<=1:
        raise ValueError('구매 비교의 수량 또는 불량률 범위가 올바르지 않습니다')
    dec=lambda x:Decimal(str(x))
    amount=dec(values['price'])*dec(values['quantity'])
    failure=dec(values['quantity'])*dec(values['fail_rate'])*dec(contract['loss_per_failure'])
    inspection=dec(contract['inspection_cost']) if quote['avl'] and values['fail_rate']>contract['inspection_threshold'] else Decimal(0)
    if not all(math.isfinite(float(x)) for x in (amount,failure,inspection,amount+failure+inspection)):
        raise ValueError('구매 총비용 계산값은 유한한 실제 금액이어야 합니다')
    return dict(part=part,supplier=supplier,quantity=values['quantity'],unit_price=values['price'],fail_rate=values['fail_rate'],
        purchase_amount=float(amount),expected_failure_cost=float(failure),inspection_cost=float(inspection),
        total_cost=float(amount+failure+inspection),lead_days=values['lead_d'],need_by_days=values['need_by_days'],
        lead_slack_days=values['need_by_days']-values['lead_d'],avl=quote['avl'],policy=contract,source_id=skill['source_id'])
