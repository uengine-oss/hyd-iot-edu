"""조회된 공급 조건을 견적 원문 및 제품별 승인 등록 행에 잇는다."""
from graph_model import rows,supplier_id


def fraction(value):
    return float(value[:-1]) / 100 if value.endswith('%') else float(value)


def lead_days(value):
    return int(value[:-1]) * 7 if value.endswith('주') else int(value)


def with_sources(source, offers):
    changes,=(source/'자료_변경분').glob('*수정본')
    for offer in offers:
        quoted=[];registered=[]
        for path in [source/'자료/공급_조건.csv', changes/'공급_조건_변경.csv']:
            for line,row in enumerate(rows(path),2):
                if (row['품번']==offer['part'] or row['공급사품번']==offer['supplier_part_no']) and supplier_id(row['공급사'])==offer['supplier'] and row['견적일']==offer['quoted_on']:
                    quoted.append({'file':path.relative_to(source).as_posix(),'line':line,'quote_date':row['견적일'],'price_manwon':float(row['단가(만원)']),'defect_rate':fraction(row['불량률']),'lead_days':lead_days(row['납기(일)'])})
        for path in [source/'자료/승인공급사_목록.csv',changes/'승인공급사_변경.csv']:
            for line,row in enumerate(rows(path),2):
                if row['품번']==offer['part'] and supplier_id(row['공급사'])==offer['supplier']:
                    registered.append({'file':path.relative_to(source).as_posix(),'line':line,'approval_status':row['승인상태'],'approved_on':row['승인일'] or None,'condition':row['조건'] or None,'valid_until':row['유효기한'] or None})
        if not quoted or not registered:raise ValueError('공급 조건 근거를 찾지 못했습니다: '+offer['supplier'])
        evidence=quoted[-1];assert (evidence['price_manwon'],evidence['defect_rate'],evidence['lead_days'])==(offer['price_manwon'],offer['defect_rate'],offer['quoted_days'])
        offer['quote_evidence']=evidence;offer['approval_evidence']=registered[-1]
    return offers
