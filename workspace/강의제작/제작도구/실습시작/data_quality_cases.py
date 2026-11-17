"""접수·출하·정정·검사·조사의 시간 관계를 가진 교육용 품질 원자료 생성. 모델 호출 없음."""
from pathlib import Path
from datetime import datetime, timedelta
import hashlib
import json
import random
import re
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OLD = ROOT / 'workspace/강의제작/산출물/통합반/실습/05회차/랩/05일차_실습3_품질대응카드/코드/source'
PRODUCTS = {'FG-AUTO-7':'유압 브래킷', 'FG-IND-3':'매니폴드', 'FG-AUTO-9':'실린더 블록', 'P-CLR-CORE':'쿨러 코어'}


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')


def rows(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(v, ensure_ascii=False)+'\n' for v in values), encoding='utf-8', newline='\n')


def build(destination, report):
    began=time.perf_counter(); destination=Path(destination); destination.mkdir(parents=True, exist_ok=True)
    old_receipts=json.loads((OLD/'접수/불량_접수.json').read_text(encoding='utf-8-sig'))
    old_cases=json.loads((OLD/'자료/원인_분석_대장.json').read_text(encoding='utf-8-sig'))
    old_rules=json.loads((OLD/'기준/분류_기준.json').read_text(encoding='utf-8-sig'))
    receipts=[]; messages=[]; lots=[]; shipments=[]; attachments=[]; investigations=[]
    def receipt(identity, at, product, lot, sender, channel, text, discovery=None):
        receipts.append({'id':identity,'received_at':at,'product':product,'lot':lot,'sender':sender,'channel':channel,
                         'discovered_at':discovery,'text':text})
    def message(identity, target, at, kind, text, attachments_ids=None):
        messages.append({'id':identity,'receipt_id':target,'recorded_at':at,'kind':kind,'sender':'品質確認窓口'.replace('品質','품질').replace('確認窓口',' 확인 창구'),
                         'text':text,'attachment_ids':attachments_ids or []})
    def attachment(identity, receipt_id, at, filename, content):
        attachments.append({'id':identity,'receipt_id':receipt_id,'received_at':at,'filename':filename,'content':content})
    legacy_product={'Q02':'FG-IND-3','Q09':'FG-AUTO-7','Q10':'FG-AUTO-7'}
    for row in old_receipts:
        product=re.search(r'(?:FG|P)-[A-Z]+-[A-Z0-9]+',row['본문']); lot=re.search(r'L-\d{4}-[A-Z]\d{2}',row['본문'])
        receipt(row['번호'],row['접수_시각']+':00+09:00', product.group() if product else legacy_product.get(row['번호']),lot.group() if lot else None,
                row['보낸_곳'],row['경로'],row['본문'])
    # 기존 원문의 사건을 보존한다. 새 기록은 별도 시각과 출처로 추가하고 기존 주장에 덮어쓰지 않는다.
    for case in old_cases:
        investigations.append({'id':case['분석_번호']+'-01','case_id':case['분석_번호'],
            'recorded_at':(case['종결일'] or '2026-10-07')+'T17:00:00+09:00','status':case['상태'],
            'receipt_ids':case['접수'],'scope':'등록된 접수에서 조사한 현품에 한함. 다른 접수의 적용 여부는 별도 확인.',
            'cause_statement':case['원인'],'evidence_statement':case['근거'],'department':'품질팀'})
    for n,lot,product,qty in [('A12','L-0923-A12','FG-AUTO-7',1800),('A17','L-0930-A17','FG-AUTO-7',800),('G05','L-0930-G05','FG-IND-3',720),('G09','L-0930-G09','FG-IND-3',320),('A19','L-0926-A19','FG-AUTO-9',480),('G03','L-0923-G03','FG-IND-3',480),('A21','L-0930-A21','FG-AUTO-9',640)]:
        lots.append({'id':lot,'product':product,'produced_at':'2026-09-'+('23' if '0923' in lot else '26' if '0926' in lot else '30')+'T16:00:00+09:00',
                     'quantity':qty,'unit':'개','production_record':'생산관리 로트 마감 기록 '+n})
    shipments.extend([
        {'id':'SHIP-1002-01','lot':'L-0923-A12','product':'FG-AUTO-7','shipped_at':'2026-10-02T08:00:00+09:00','recipient':'가나자동차','quantity':900,'container_ids':['BOX-A12-01','BOX-A12-02'],'unit':'개'},
        {'id':'SHIP-1004-02','lot':'L-0923-A12','product':'FG-AUTO-7','shipped_at':'2026-10-04T08:00:00+09:00','recipient':'가나자동차','quantity':900,'container_ids':['BOX-A12-03','BOX-A12-04'],'unit':'개'}])
    attachment('ATT-Q01-M','Q01','2026-10-05T09:12:00+09:00','incoming_measurement.csv',
               {'description':'입고 검사에서 분리한 14개 측정 성적서','sample_ids':['A12-I'+str(i) for i in range(1,15)],'quantity_kind':'불량 현품','quantity':14,'measured_mm':[12.06]*14,'lower_mm':11.97,'upper_mm':12.03,'container_id':'BOX-A12-01'})
    attachment('ATT-Q02-C','Q02','2026-10-07T16:20:00+09:00','surface_analysis.txt',
               {'description':'분리한 12개 변색 부위에 세척액 성분 잔류. 건조시간 기록 누락 구간과 일치. 방청유 성분은 확인하지 못함.','receipt_id':'Q02','quantity':12})
    message('MSG-Q11-01','Q11','2026-10-08T15:30:00+09:00','보완','끼워지지 않은 현품 3개는 조립 라인에서 따로 보관 중입니다. 입고 검사에서 분리한 14개와 같은 현품인지는 현품표를 확인 중입니다. 도장 두께 의견은 측정 전 의견이며 도장 측정표는 없습니다.')
    message('MSG-Q11-02','Q11','2026-10-09T09:20:00+09:00','정정','앞 메일의 라인 정지 20분은 해당 교대 전체 기록입니다. 이번 3개로 멈춘 시간은 별도 집계 전입니다. 사진을 첨부했다고 전화했지만 업로드 실패로 파일은 도착하지 않았습니다.')
    receipt('Q13','2026-10-09T10:10:00+09:00','FG-AUTO-7','L-0923-A12','가나자동차 조립 라인','고객 메일',
            '오후조 준비 중 FG-AUTO-7 L-0923-A12 두 개가 체결되지 않습니다. 현품표의 상자 번호는 다시 확인하겠습니다. 어제 접수한 3개와 같은 현품인지 교대 인수인계 메모에 구분이 없습니다. 내경 이상이라는 의견과 상대 부품 간섭 의견이 함께 있습니다.')
    message('MSG-Q13-01','Q13','2026-10-09T14:00:00+09:00','보완','받은 제품은 10월 4일 출하분으로 들었지만 납품표를 아직 보내지 못했습니다. 현품을 겹쳐 센 수량인지 확인 전입니다. 2개와 3개를 합한 불량 수량은 아직 보고하지 않았습니다.')
    message('MSG-Q03-01','Q03','2026-10-09T11:30:00+09:00','보완','FG-IND-3 현품 로트는 L-0930-G09이고 젖은 현품은 2개입니다. 압력 유지 시험은 아직 하지 않았습니다. 고객이 말한 씰 조립 원인은 확인 전입니다.')
    message('MSG-Q03-02','Q03','2026-10-10T09:00:00+09:00','정정','닦은 뒤 같은 압력에서 다시 보니 새어 나온 흔적은 없었습니다. 처음 묻어 있던 액체의 성분 검사는 진행 중입니다. 최초 누유 신고를 없애지 말고 이 확인 시각을 함께 남겨 주세요.')
    attachment('ATT-Q03-T','Q03','2026-10-10T09:10:00+09:00','repeat_pressure.txt',{'description':'현품 2개의 반복 압력 유지 시험에서 새어 나오는 액체는 관찰하지 않음. 시험 1회이며 액체 성분·장기 기밀은 미확인.','quantity':2,'unit':'개'})
    message('MSG-Q08-01','Q08','2026-10-08T13:00:00+09:00','정정','한 상자의 46개는 육안 계수였습니다. 포장 내부를 다시 확인하여 48개로 정정합니다. 다른 품번 라벨 두 상자는 그대로여서 현품표 확인을 요청합니다.')
    attachment('ATT-Q08-L','Q08','2026-10-08T13:05:00+09:00','label_register.csv',{'description':'현품 FG-IND-3 / 붙어 있는 라벨 FG-AUTO-7, 두 상자. 상자별 실물 48개.','quantity_kind':'상자','quantity':2})
    # 생산·출하·표본 검사에서 생긴 서로 다른 관측. 동일 로트의 다른 출하/검사 시점은 별도 접수다.
    rng=random.Random(260710); start=datetime(2026,7,12,8,30); templates=[
      ('장착면 측정', '도면 8.00 ±0.05 mm에 대해 측정값 {value:.3f} mm. {bad}개를 분리했습니다. 가공 공구 영향이라는 의견은 조사 전입니다.',8.0,.05),
      ('표면 확인','표면에 {surface}이 보인 {bad}개를 분리했습니다. 운송 또는 공정 중 발생 여부는 확인 중이며 기름이 새는 현상은 관찰하지 않았습니다.',None,None),
      ('압력 유지','압력을 유지하는 동안 포트 주변이 젖은 현품 {bad}개를 보관 중입니다. 씰 때문이라는 현장 의견이 있으나 분해하지 않았습니다.',None,None),
      ('유로 검사','유로 내부에 {material}이 남은 {bad}개를 확인했습니다. 세척 기록과 현품을 비교 중입니다.',None,None),
      ('포장 확인','현품표와 주문 품번이 맞지 않는 상자 {bad}개입니다. 제품 총수량과 상자 수량은 구별해서 기록했습니다.',None,None),
      ('입고 외관','공급사에서 받은 쿨러 코어의 핀에 눌림 {bad}개. 성적서에는 이상 없음으로 적혀 있어 포장·입고 시각을 확인 중입니다.',None,None)]
    for i in range(53):
        at=start+timedelta(hours=i*39+int(rng.random()*7)); product=list(PRODUCTS)[i%4]
        lot=f'L-{at:%m%d}-{chr(65+i%3)}{i+30:02d}'; quantity=rng.choice([240,360,480,720,960]); sample=rng.choice([20,32,50,80]); bad=rng.randrange(1,8)
        lots.append({'id':lot,'product':product,'produced_at':at.isoformat()+'+09:00','quantity':quantity,'unit':'개','production_record':f'생산관리 마감 {at:%m%d}-{i%2+1}교대'})
        shipment_id=f'SHIP-{at:%m%d}-{i+20:03d}'; shipment_at=at+timedelta(hours=18)
        shipments.append({'id':shipment_id,'lot':lot,'product':product,'shipped_at':shipment_at.isoformat()+'+09:00','recipient':'다라산업' if i%2 else '가나자동차','quantity':quantity//2,'unit':'개','container_ids':[f'BOX-{i+30}-A',f'BOX-{i+30}-B']})
        kind=5 if product=='P-CLR-CORE' else i%5; name,template,target,tolerance=templates[kind]
        value=8+rng.choice([.021,.049,.057,.063,.076]); surface=rng.choice(['얕은 선 자국','얼룩','모서리 눌림']); material=rng.choice(['금속 조각','검은 잔류물','가느다란 칩'])
        first=f'QI-{at:%m%d}-{i+20:03d}'; received=at+timedelta(hours=29)
        text=(f'{product} 로트 {lot}, 전체 {quantity}개 중 표본 {sample}개를 확인했습니다. '+template.format(value=value,bad=bad,surface=surface,material=material)+f' 발견 작업은 {name}입니다.')
        sender='구매팀 입고 검사' if kind==5 else ('가나자동차 수입검사' if i%2==0 else '생산팀 공정 검사')
        receipt(first,received.isoformat()+'+09:00',product,lot,sender,'입고 검사' if kind==5 else '검사 메모',text,at.isoformat()+'+09:00')
        attachment_id=f'ATT-{first}-M'
        content={'description':f'{name} 원기록','lot':lot,'shipment_id':shipment_id,'sample_count':sample,'isolated_count':bad,'lot_total':quantity,'unit':'개','container_id':f'BOX-{i+30}-A'}
        if target is not None: content.update(measured_mm=value,nominal_mm=target,tolerance_mm=tolerance)
        else: content['observation']=template.format(value=value,bad=bad,surface=surface,material=material)
        if i%4!=0:
            attachment(attachment_id,first,(received+timedelta(hours=2)).isoformat()+'+09:00','inspection_record.json',content)
            message(f'MSG-{first}-01',first,(received+timedelta(hours=2)).isoformat()+'+09:00','보완','검사 원기록을 보냅니다. 검사 수량과 분리 수량, 전체 로트 수량은 각각 기록한 값입니다.',[attachment_id])
        else:
            message(f'MSG-{first}-01',first,(received+timedelta(hours=2)).isoformat()+'+09:00','보완','사진을 첨부했다고 적었으나 내부 메신저 링크만 보냈습니다. 파일 전달은 아직 완료되지 않았습니다.')
        second=f'QI-{at:%m%d}-{i+20:03d}B'; second_at=received+timedelta(hours=9+i%3)
        if i%3==0:
            receipt(second,second_at.isoformat()+'+09:00',product,lot,sender,'전화 메모',f'{first}에서 분리한 현품 {bad}개의 위치를 보완합니다. BOX-{i+30}-A에 있으며 추가 불량 보고가 아닙니다. 품번 {product}, 로트 {lot}.')
        elif i%3==1:
            receipt(second,second_at.isoformat()+'+09:00',product,lot,'다라산업 조립 라인','고객 메일',f'{product} {lot} 조립 중 맞물리지 않는 현품이 있습니다. {first} 번호를 전달받았으나 같은 현품인지, 이전 선별에서 나온 물량인지 모릅니다. 납품표와 현품표를 보내기 전이며 수량 집계 중입니다.')
        else:
            receipt(second,second_at.isoformat()+'+09:00',product,lot,sender,'검사 메모',f'{product} {lot}의 BOX-{i+30}-B를 검사했습니다. 앞 BOX-{i+30}-A의 {bad}개는 포함하지 않았습니다. 이번 표본 {sample+10}개 중 모서리 눌림 {max(1,bad-1)}개와 현품표 훼손 1개를 확인했습니다.')
        third=f'QI-{at:%m%d}-{i+20:03d}C'; third_at=received+timedelta(hours=27)
        receipt(third,third_at.isoformat()+'+09:00',product,lot,sender,'보완 메일',f'{first} 검사 기록을 보완합니다. 최초 분리 수량 {bad}개 중 '+(f'{bad-1}개는 다시 확인할 필요가 있습니다. 계측기 영점 기록을 찾는 중입니다.' if i%4==0 else '아직 재검사하지 않은 현품이 있습니다. 최초 추정 원인은 확정하지 않았습니다.')+' 이 메일은 새 발견 수량을 보고하는 것이 아닙니다.')
        if i%5==0:
            message(f'MSG-{first}-02',first,(received+timedelta(hours=30)).isoformat()+'+09:00','정정',f'최초 {sample}개는 표본 수이고 불량 수가 아닙니다. 분리한 {bad}개 중 재검사에서 {max(0,bad-2)}개만 같은 증상이 보였습니다. 원래 현품은 남겨 두었고 나머지는 원인 확인 전입니다.')
        case=f'CA-{at:%y%m}-{i+20:03d}'
        investigations.append({'id':case+'-01','case_id':case,'recorded_at':(received+timedelta(hours=4)).isoformat()+'+09:00','status':'접수','receipt_ids':[first],
             'scope':f'{first}에서 BOX-{i+30}-A에 분리한 현품 {bad}개','cause_statement':None,'evidence_statement':'원기록과 현품 일치 여부를 확인할 예정','department':'품질팀'})
        status='종결' if i%4==2 else '진행'
        investigations.append({'id':case+'-02','case_id':case,'recorded_at':(received+timedelta(hours=52)).isoformat()+'+09:00','status':status,'receipt_ids':[first],
             'scope':f'{first}에서 BOX-{i+30}-A에 분리한 현품. 다른 상자·새 증상은 조사 대상에 넣지 않았음.',
             'cause_statement':('취급 중 현품 접촉 흔적과 포장 분리재 손상이 현품 위치와 일치함' if kind in [1,5] else '재검사한 해당 현품에서 작업 기록 누락 구간과 이상이 일치함') if status=='종결' else '원기록·운송·작업 조건을 비교 중이며 원인 미확정',
             'evidence_statement':'현품표와 조사 대상 일치 확인, 조사 결과 기록' if status=='종결' else '공급사 회신 또는 비교 측정이 끝나지 않음','department':'품질팀'})
    requests=[{'request_id':'QR-Q11','seed_receipts':['Q11'],'as_of':'2026-10-09T16:00:00+09:00','recipient':'품질팀','question':'새 조립 문제와 관련된 접수·조사를 찾아 품질 대응 카드와 조사 요청 초안을 만든다.'},
              {'request_id':'QR-Q03','seed_receipts':['Q03'],'as_of':'2026-10-10T12:00:00+09:00','recipient':'품질팀','question':'고객의 최초 신고와 뒤의 확인을 함께 읽고 현재 확인할 내용과 대응 초안을 만든다.'},
              {'request_id':'QR-Q08','seed_receipts':['Q08'],'as_of':'2026-10-09T16:00:00+09:00','recipient':'품질팀','question':'포장 접수와 정정 기록을 반영해 품질 대응 카드와 담당 부서의 확인 내용을 만든다.'}]
    for r in receipts:
        if r['id'].startswith('QI-') and not r['id'].endswith(('B','C')):
            as_of=datetime.fromisoformat(r['received_at'])+timedelta(days=3)
            requests.append({'request_id':'QR-'+r['id'],'seed_receipts':[r['id']],'as_of':as_of.isoformat(),'recipient':'품질팀','question':'연결할 접수와 조사 범위를 확인하고 후속 업무 초안을 만든다.'})
    rules={'title':'품질 업무 분류와 역할','status':'교육용 업무 기준','types':[{ 'code':v['코드'],'name':v['이름'],'required_information':v['확인_정보'],'correction_department':v['조치_부서'],'correction_example':v['기본_조치']} for v in old_rules['유형']],
           'authority':['원인 미확정 또는 유형 미정인 조사는 품질팀이 받는다.','원인이 확인된 조사 대상의 시정 조치는 해당 유형의 조치 부서가 검토한다.','검토 전 초안만 작성하며 연락·등록·출하 승인·시정 조치 실행은 하지 않는다.'],
           'meaning':['치수는 도면 또는 상대 부품과 관련된 크기·맞춤 문제다.','외관은 표면·모서리 상태의 문제다.','누유·기밀은 액체 또는 압력 유지와 관련된 문제다.','이물·오염은 제품 내부나 표면의 불필요한 물질이다.','포장·표시는 상자·포장·라벨·납품 수량의 문제다.','구매품은 사내에서 사 온 부품·원자재가 대상인 문제다. 고객이 우리 제품을 받은 검사는 공급사의 사내 입고와 다르다.']}
    for name,values in [('receipts',receipts),('messages',messages),('attachments',attachments),('lots',lots),('shipments',shipments),('investigations',investigations),('requests',requests)]:
        rows(destination/(name+'.jsonl'),values)
    dump(destination/'classification.json',rules)
    notes='''# 품질 기록의 출처와 시점

이 자료는 교육용 가상 기록이다. 7월부터 10월까지의 생산·출하·접수·검사·보완·조사 기록을 묶었다. 원문에 적힌 의견과 별도 조사에서 확인한 내용을 구별한다.

접수 원문은 receipts.jsonl에, 뒤의 연락·정정은 messages.jsonl에 있다. 같은 접수의 정정도 원문을 덮어쓰지 않는다. attachments.jsonl은 실제 도착한 파일의 내용이다. 파일 이름이 원문에 언급되어도 이 목록에 없으면 받은 파일은 아니다. 사진 파일은 이 묶음에 제공하지 않는다.

lots.jsonl은 생산 단위, shipments.jsonl은 그중 출하한 물량이다. 출하 수량·검사 수량·분리 수량을 합쳐 불량 수량으로 보지 않는다. 접수 시각과 발견 시각이 다를 수 있다. 시각이 없는 사실은 시각 미확인으로 남긴다.

investigations.jsonl은 조사 상태가 바뀔 때마다 새 기록을 남긴다. case_id는 조사 번호이고 receipt_ids와 scope는 그 기록이 다룬 대상이다. 진행 중의 원인 문장은 조사 중인 가설이다. 종결 기록도 적힌 대상의 원인만 확인한다. 요청의 as_of 뒤 기록은 당시 판단의 근거가 아니다.

# 이번에 품질팀이 필요한 것

품질팀은 새 접수 주변의 관련 접수와 지난 조사 기록을 읽고, 담당 부서가 조사에 착수할 대응 카드 초안을 받으려 한다. 아직 동일 사건인지 확인되지 않은 접수들이 나왔을 때 조사 요청을 어떤 단위로 보내고 어디까지 함께 확인할지는 정해지지 않았다. 이 운영 요구는 자료에 있는 사실만으로 정해지지 않으므로 요청자에게 근거와 요구를 확인해야 한다. 개별 접수의 수량·원인·회신 대상이 같다는 승인은 아니다.

classification.json은 업무 분류명과 부서 권한이다. 개인 담당자는 배정하지 않았다. 사건 연결과 조사 요청 단위는 구별하며, 원자료 밖의 연결을 확정 사실로 등록하지 않는다.
'''
    (destination/'field_notes.md').write_text(notes,encoding='utf-8-sig',newline='\n')
    counts={name:len(values) for name,values in [('receipts',receipts),('messages',messages),('attachments',attachments),('lots',lots),('shipments',shipments),('investigations',investigations),('requests',requests)]}
    files={p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in destination.iterdir() if p.is_file() and p.name!='manifest.json'}
    manifest={'title':'교육용 품질 접수 원자료','default_request':'QR-Q11','counts':counts,'files':files,'period':{'first':min(r['received_at'] for r in receipts),'last':max(m['recorded_at'] for m in messages)},'fictional':True}
    dump(destination/'manifest.json',manifest)
    duplicate_text=len(receipts)-len({r['text'] for r in receipts})
    result={'elapsed_seconds':round(time.perf_counter()-began,6),'counts':counts,'files':files,'duplicate_receipt_texts':duplicate_text,
            'source_files':{str(p.relative_to(ROOT)):sha(p) for p in [OLD/'접수/불량_접수.json',OLD/'자료/원인_분석_대장.json',OLD/'기준/분류_기준.json']},
            'reuse':'원문 접수 12건과 조사 5건의 사건 내용·번호를 유지. 개인 담당자 필드는 복사하지 않음. 업무 기준은 6유형과 부서 권한만 재사용.',
            'generation_basis':'생산 로트→분할 출하→표본 검사→새 접수/동일 현품 보완/다른 상자 관측→정정→조사 상태 이력. 동일 숫자 목표를 맞추기 위한 복제 없음.',
            'model_calls':0}
    dump(Path(report),result); return result
