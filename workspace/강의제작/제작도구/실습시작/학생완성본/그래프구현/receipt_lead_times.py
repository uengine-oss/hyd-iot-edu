"""각 발주에서 전체 발주수량을 채운 첫 날까지를 실측 납기로 쓴다."""
from collections import defaultdict
from datetime import date
from graph_model import rows, supplier_id


def compare_lead_times(source, offers, product, aliases):
    orders = defaultdict(list)
    for line, row in enumerate(rows(source / '자료/입고_이력.csv'), 2):
        if row['품번'] in {product, *aliases} and row['입고일']:
            orders[supplier_id(row['공급사']),row['발주번호']].append((line,row))
    result=[]
    for offer in offers:
        supplier=offer['supplier']; samples=[]
        for (sid,po), arrivals in orders.items():
            if sid!=supplier:continue
            total=0
            for line,row in sorted(arrivals,key=lambda pair:pair[1]['입고일']):
                total+=int(row['입고수량'])
                if total>=int(row['발주수량']):
                    days=(date.fromisoformat(row['입고일'])-date.fromisoformat(row['발주일'])).days
                    samples.append({'order':po,'observed_days':days,'receipt_csv_line':line});break
        mean=round(sum(x['observed_days'] for x in samples)/len(samples),2) if samples else None
        result.append({'supplier':supplier,'quote_days':offer['quoted_days'],'mean_completion_days':mean,'mean_minus_quote_days':round(mean-offer['quoted_days'],2) if mean is not None else None,'completed_orders':samples})
    return result
