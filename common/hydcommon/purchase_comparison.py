"""Source-defined purchasing cost, independent of physical plant forecasts."""
from .words import particle
import json
import math
import re
from decimal import Decimal


#: 비용식의 수치 칸 → 그 수치의 단위 종류(금액 = 만 원 기준 · 비율 = 0~1)와 사람이 읽는 이름
FIELDS={'loss_per_failure':'money','inspection_threshold':'ratio','inspection_cost':'money'}
FIELD_TEXT={'loss_per_failure':'불량 1건 손실','inspection_threshold':'전수 검사 불량률 기준','inspection_cost':'전수 검사 비용'}
_NUMBER=r'(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)'
_MONEY=re.compile(_NUMBER+r'\s*(억|천만|백만|만)?\s*(원|KRW|won)',re.I)
_RATIO=re.compile(_NUMBER+r'\s*(%|퍼센트|percent)',re.I)
_SCALE={'':1/10000,'만':1,'백만':100,'천만':1000,'억':10000}


def quoted_numbers(quote):
    """원문 인용에 적힌 금액(만 원 기준 — 「250만 원」 · 「2,500,000원」 · 「2.5백만 원」 · 「600,000 KRW」)과 비율(「10 %」 → 0.1)."""
    number=lambda text:float(text.replace(',',''))
    return {'money':{number(n)*_SCALE[unit] for n,unit,_ in _MONEY.findall(quote)},
            'ratio':{number(n)/100 for n,_ in _RATIO.findall(quote)}}


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
    # 수치마다 「원문 인용 안에 그 수치가 그 단위로 적혀 있는가」를 본다(금액은 만 원으로, 비율은 % 로 맞춰). 전에는 수업 문서 PR-07 의 문장
    # 모양(「불량 1건 손실 … 만 원」 · 「불량률이 … %」 · 「전수 검사 비용 … 만 원」)만 받아, 같은 수치를 다른 말로 적은 구매 기준서는 정책이
    # 통째로 빠졌다. 어느 금액이 어느 칸인지(뜻)는 검토하는 사람이 인용과 나란히 보고 확인한다.
    found=quoted_numbers(anchor['quote'])
    for field,kind in FIELDS.items():
        if not any(math.isclose(value[field],x,rel_tol=1e-9,abs_tol=1e-9) for x in found[kind]):
            shown=FIELD_TEXT[field]+' '+(f"{value[field]*100:g} %" if kind=='ratio' else f"{value[field]:g}만 원")
            seen=' · '.join(f"{x*100:g} %" if kind=='ratio' else f"{x:g}만 원" for x in sorted(found[kind])) or '없음'
            raise ValueError(f"구매 비교 수치가 원문 인용과 다릅니다: {field} — {shown}{particle(shown, '이')} 인용에 없습니다(인용에서 읽은 "
                             f"{'비율' if kind=='ratio' else '금액'}: {seen})")
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
