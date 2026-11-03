"""온라인2 독립 시작본. 강사 모델은 제작용에만 생성.

2회차 실습3·4 원자료는 data_session2.py가 만든다(교육용 가상 사례, 고정 시드).
reference_model()의 반환 형식(schema dict, {'nodes':[{labels,props}], 'rels':[{type,a,b,props}]})은
3회차 랩(build_session3_judgement·documents)이 import하므로 유지한다.
"""
from pathlib import Path
import csv
import hashlib
import html
import json
import re
import shutil
import zipfile

import data_session2 as D

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT/'workspace/강의제작/산출물'
TEACHER = ROOT/'workspace/강의제작/제작도구/실습시작/reference'
COURSES = [('통합반','integrated'),('실전반','practical')]
LAB3 = '02일차_실습3_온톨로지설계'
LAB4 = '02일차_실습4_그래프구현과검증'
VERSION = '2026-11-02-lab-v7'

def write(path, text):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(text,encoding='utf-8')

def dump(path, value):
    write(path,json.dumps(value,ensure_ascii=False,indent=2)+'\n')

def rows(name, folder=None):
    path=(folder or D.SOURCE)/name
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

# ───────────── 강사 참조 해석(원자료의 표기를 현장 메모 근거로 푼다) ─────────────
NAME_ALIAS={'오일 쿨러':'cooler','쿨러':'cooler','열교환기':'cooler','오일 쿨러(공랭)':'cooler','수냉 열교환기':'cooler',
    '쿨러 팬':'fan','팬':'fan','송풍기':'fan','주 펌프 (A)':'pump-a','유압 펌프':'pump-a','주 펌프 A':'pump-a','A 펌프':'pump-a',
    '예비 펌프 (B)':'pump-b','스탠바이 펌프':'pump-b','메인 펌프':'pump','구동 모터':'motor','모터':'motor','커플링':'coupling','축 커플링':'coupling',
    '작동유 탱크':'tank','탱크':'tank','리저버':'tank','오일 탱크':'tank','리턴 필터':'rtn-filter','흡입 스트레이너':'strainer','석션 스트레이너':'strainer',
    '전환 밸브':'valve','방향 전환 밸브':'valve','방향 제어 밸브':'valve','솔레노이드 밸브':'valve','어큐뮬레이터':'accumulator','축압기':'accumulator',
    '제어반':'cabinet','제어 판넬':'cabinet'}
CANON_NAME={'cooler':'오일 쿨러','fan':'쿨러 팬','pump-a':'주 펌프 (A)','pump-b':'예비 펌프 (B)','pump':'메인 펌프','motor':'구동 모터','coupling':'커플링',
    'tank':'작동유 탱크','rtn-filter':'리턴 필터','strainer':'흡입 스트레이너','valve':'전환 밸브','accumulator':'어큐뮬레이터','cabinet':'제어반'}
WHAT_ALIAS={'유온':'TS1','오일 온도':'TS1','작동유 온도':'TS1','쿨러 출구 유온':'TS2','탱크 유온':'TS3','탱크 온도':'TS3','제어반 내부 온도':'TS4',
    '토출 압력':'PS1','펌프 압력':'PS1','메인 압력':'PS1','시스템 압력':'PS2','리턴 라인 압력':'PS3','필터 차압':'PS4','파일럿 압력':'PS5','파일럿 후단 압력':'PS6',
    '모터 출력':'EPS1','유량':'FS1','토출 유량':'FS1','메인 유량':'FS1','냉각 회로 유량':'FS2','냉각수 유량':'CW-FLOW','팬 진동':'VS1','진동':'VS1',
    '냉각 효율':'CE','쿨러 효율':'CE','냉각 동력':'CP','시스템 효율':'SE','팬 속도 설정값':'FanSpeedSP','부하 설정값':'LoadSP','모터 전류':'I_MOTOR','탱크 레벨':'LVL'}
UNIT={'l/min':('L/min',1),'L/min':('L/min',1),'W':('kW',0.001),'kPa':('bar',0.01)}

def comp_key(text,keys):
    key=NAME_ALIAS.get(text.strip())
    if key is None and text.strip()=='펌프':key='pump-a' if 'pump-a' in keys else 'pump'
    if key not in keys:raise ValueError(f'구성요소 이름을 풀지 못함: {text!r} (후보 {sorted(keys)})')
    return key

def model_match(model,applies):
    if applies=='전 모델':return True
    head,*rest=applies.split('·');prefix=head.rsplit('-',1)[0]+'-'
    return model in [head,*[prefix+x for x in rest]]

def resolve_part(text,model,key,parts,cross):
    """교체부품 칸 → 사내 품번. 품번·교차표로 풀고, 품명만 있거나 비어 있으면 같은 모델의 쓰는곳으로 푼다(메모 2·5절)."""
    t=text.strip()
    m=re.search(r'\((P-[A-Z0-9-]+)\)',t)
    if m:return m.group(1)
    if t in parts:return t
    hits=sorted({c['사내품번'] for c in cross if c['다른표기']==t})
    if len(hits)==1:return hits[0]
    cand=[p for p,row in parts.items() if model_match(model,row['적용모델']) and NAME_ALIAS.get(row['쓰는곳'],'pump-a' if row['쓰는곳']=='주 펌프 A' else ('pump' if row['쓰는곳']=='펌프' else None))==key]
    if len(cand)==1:return cand[0]
    if not t and not cand:return None
    raise ValueError(f'교체부품을 풀지 못함: {text!r} {model} {key} 후보={cand}')

def number(text):
    m=re.match(r'\s*(-?\d+(?:\.\d+)?)',text or '')
    return float(m.group(1)) if m else None

def base_graph(branch='A'):
    nodes=[];rels=[];index={}
    def node(label,id,**props):
        if id in index:raise ValueError('중복 id '+id)
        index[id]=len(nodes);nodes.append({'labels':[label],'props':{'id':id,**{k:v for k,v in props.items() if v is not None}}})
    def rel(type,a,b,**props):rels.append({'type':type,'a':a,'b':b,'props':{k:v for k,v in props.items() if v is not None}})
    parts={p['품번']:p for p in rows('예비품_목록.csv')};cross=rows('품번_교차표.csv')
    for pid,p in parts.items():
        alt=sorted({c['다른표기'] for c in cross if c['사내품번']==pid})
        node('Part',pid,name=p['품명'],other_codes=alt)
    for qid,(name,unit) in D.QUANTITIES.items():node('Quantity',qid,name=name,unit=unit)
    assets=rows('설비_대장.csv');models={}
    for a in assets:
        if a['상태']=='코드 통합':continue
        legacy=[x['설비코드'] for x in assets if x['상태']=='코드 통합' and x['기능위치']==a['기능위치'] and x['일련번호']==a['일련번호']]
        models[a['설비코드']]=a['모델']
        node('Asset',a['설비코드'],name=a['설비명'],model=a['모델'],maker=a['제조사'],serial=a['일련번호'],functional_location=a['기능위치'],
             installed=a['설치일'],status=a['상태'],legacy_codes=legacy or None)
    comps={}
    for c in rows('구성요소_목록.csv'):
        if '철거' in c['비고']:continue
        aid=c['설비코드'];model=models[aid]
        keys={k for k,*_ in D.MODEL_COMPONENTS[model]}
        key=comp_key(c['구성요소'],keys);cid=aid+':'+key
        name='수냉 열교환기' if (model=='HPP-45B' and key=='cooler') else CANON_NAME[key]
        if cid in comps:raise ValueError('구성요소 중복 '+cid)
        comps[cid]=(aid,model,key)
        node('Component',cid,name=name,group=c['계통'],serial=c['일련번호'] or None,aliases=[c['구성요소']] if c['구성요소']!=name else None)
        rel('HAS_COMPONENT',aid,cid)
        pid=resolve_part(c['교체부품'],model,key,parts,cross)
        if pid:rel('USES_PART',cid,pid,source_text=c['교체부품'] or '(빈칸: 같은 모델 공용 근거)')
    seen=set()
    for s in rows('센서_목록.csv'):
        aid=s['설비코드'];sid=aid+':'+s['태그']
        if sid in seen:continue                 # 점검표에서 다시 옮겨 적은 같은 센서
        seen.add(sid);model=models[aid]
        q='quantity:'+WHAT_ALIAS[s['재는것']];qunit=D.QUANTITIES[q][1]
        raw=s['단위'];unit,factor=UNIT.get(raw,(raw or qunit,1))
        if unit!=qunit:raise ValueError(f'{sid} 단위 {raw} → 물리량 {q} {qunit}')
        normal=number(s['정상값']);limit=number(s['한계'])
        kind='derived' if '계기 없음' in s['비고'] else ('setpoint' if '설정값' in s['수집방식'] else 'measured')
        hz=number(s['표본주기'])
        props=dict(tag=s['태그'],instrument_tag=s['계장태그'] or None,unit=unit,kind=kind,derived=kind=='derived',
                   normal=None if normal is None else round(normal*factor,6),limit=None if limit is None else round(limit*factor,6),
                   limit_direction={'상한':'upper','하한':'lower'}.get(s['한계구분']),sample_hz=hz,collection=s['수집방식'] or None,
                   source_unit=raw if factor!=1 else None)
        node('Sensor',sid,**props)
        place=s['붙은곳']
        if place=='설비 전체':rel('MONITORED_BY',aid,sid)
        else:rel('MONITORED_BY',aid+':'+comp_key(place,{k for k,*_ in D.MODEL_COMPONENTS[model]}),sid)
        rel('OBSERVES',sid,q)
    if branch=='B':   # 같은 제조사 품번(규격)인 다른 사내 품번을 같은 물품으로 잇는다
        by={}
        for c in cross:
            if c['표기종류']=='제조사 품번':by.setdefault(c['다른표기'],set()).add(c['사내품번'])
        for code,ids in sorted(by.items()):
            ids=sorted(ids)
            for other in ids[1:]:rel('SAME_ITEM_AS',other,ids[0],maker_part_no=code)
    return nodes,rels

def supply_part(nodes,rels,branch='A'):
    parts={p['품번']:p for p in rows('예비품_목록.csv')}
    avl={(r['공급사'],r['품번']):r for r in rows('승인공급사_목록.csv')}
    best={}
    for q in rows('공급_조건.csv'):
        pid=q['품번'] if q['품번'] in parts else next(p for p,row in parts.items() if row['품명']==q['품번'])
        sup=next(k for k in D.SUPPLIERS if q['공급사'].startswith(k))
        if q['유효기한']<D.REF_DATE:continue          # 만료 견적은 조건으로 쓰지 않는다
        prev=best.get((sup,pid))
        if prev is None or q['견적일']>prev['견적일']:best[(sup,pid)]=q
    for sup in sorted({s for s,_ in best}):nodes.append({'labels':['Supplier'],'props':{'id':'supplier:'+sup,'name':D.SUPPLIERS[sup]}})
    for (sup,pid),q in sorted(best.items()):
        a=avl.get((sup,pid))
        status=a['승인상태'] if a else '미등록'
        if a and a['유효기한'] and a['유효기한']<D.REF_DATE:status='유효기한 경과'
        ok={'A':status in ('승인','조건부 승인'),'B':status=='승인'}[branch]
        fail=q['불량률'];lead=q['납기(일)']
        rels.append({'type':'SUPPLIES','a':'supplier:'+sup,'b':pid,'props':{k:v for k,v in dict(
            approved=ok,approval_status=status,condition=(a['조건'] if a else '') or None,
            price_manwon=float(q['단가(만원)']),defect_rate=float(fail.rstrip('%'))/100 if fail.endswith('%') else float(fail),
            lead_days=int(lead[:-1])*7 if lead.endswith('주') else int(lead),min_order_qty=int(q['최소주문수량']),
            supplier_part_no=q['공급사품번'],quote_date=q['견적일'],valid_until=q['유효기한']).items() if v is not None}})

def schema_for(supply,branch):
    S={'type':'string'}
    definitions={
      'Asset':{'meaning':'개별 설비(설비코드 기준). 기능위치·실물 일련번호를 속성으로 둔다','required':{'id':'string','name':'string','model':'string','status':'string'},
               'optional':{'maker':'string','serial':'string','functional_location':'string','installed':'string','legacy_codes':'list'}},
      'Component':{'meaning':'설비 안의 정비 가능 품목. 기능 자리 기준 ID(설비코드:품목)로, 실물 교체는 serial로 남긴다','required':{'id':'string','name':'string','group':'string'},
                   'optional':{'serial':'string','aliases':'list'}},
      'Sensor':{'meaning':'설비별 계측 채널. 실측·계산값·설정값을 kind로 구별','required':{'id':'string','tag':'string','unit':'string','kind':['measured','derived','setpoint'],'derived':'boolean'},
                'optional':{'normal':'number','limit':'number','limit_direction':['upper','lower'],'instrument_tag':'string','sample_hz':'number','collection':'string','source_unit':'string'}},
      'Quantity':{'meaning':'재는 물리량 종류와 기준 단위','required':{'id':'string','name':'string','unit':'string'}},
      'Part':{'meaning':'사내 품번 하나로 관리하는 부품 품목','required':{'id':'string','name':'string'},'optional':{'other_codes':'list'}}}
    relation_defs={'HAS_COMPONENT':{'from':'Asset','to':'Component','cardinality':'1:N'},
        'MONITORED_BY':{'from':['Component','Asset'],'to':'Sensor','cardinality':'1:0..N','note':'설비 전체에 붙은 계산값(SE)은 Asset에서'},
        'OBSERVES':{'from':'Sensor','to':'Quantity','cardinality':'N:1'},
        'USES_PART':{'from':'Component','to':'Part','cardinality':'N:0..1','properties':{'source_text':'string'}}}
    if branch=='B':relation_defs['SAME_ITEM_AS']={'from':'Part','to':'Part','cardinality':'N:1','properties':{'maker_part_no':'string'},'note':'같은 제조사 품번인 다른 사내 품번'}
    if supply:
        definitions['Supplier']={'meaning':'견적을 낸 공급사','required':{'id':'string','name':'string'}}
        relation_defs['SUPPLIES']={'from':'Supplier','to':'Part','cardinality':'N:M','note':'공급사·품번마다 유효한 최신 견적 하나',
            'properties':{'approved':'boolean','approval_status':'string','condition':'string','price_manwon':'number','defect_rate':'number','lead_days':'integer',
                          'min_order_qty':'integer','supplier_part_no':'string','quote_date':'string','valid_until':'string'}}
    constraints=['id는 전체 그래프에서 고유. 구성요소·센서는 설비코드:이름, 부품은 사내 품번','이관 기록(코드 통합)·철거 실물·점검표 중복 행은 대상을 새로 만들지 않는다',
                 'limit 생략은 0과 다르다. normal 생략은 미확인','단위는 Quantity 기준 단위로 맞추고 바꾼 경우 source_unit을 남긴다']
    if supply:constraints+=['승인 여부는 승인공급사_목록(SCM 등록)과 기준일로 정한다','만료 견적은 SUPPLIES로 쓰지 않는다']
    return {'classes':definitions,'relations':relation_defs,'identity':'id는 전체 그래프에서 고유.','branch':branch,'constraints':constraints}

def reference_model(supply=False,branch='A'):
    """원자료 + 현장 메모 근거로 만든 강사 참조 모델(반환 형식 유지)."""
    # 갈래: 통합반(supply=False) B = 같은 제조사 품번의 다른 사내 품번을 SAME_ITEM_AS로 잇는다.
    #       실전반(supply=True) B = 조건부 승인을 승인으로 보지 않는다. 실전반의 설비·부품 부분은 통합반 A와 같다.
    nodes,rels=base_graph('A' if supply else branch)
    if supply:supply_part(nodes,rels,branch)
    return schema_for(supply,'A' if supply else branch)|{'branch':branch},{'nodes':nodes,'rels':rels}

CSS='''*{box-sizing:border-box}body{margin:0;background:#f4f6f3;color:#20342f;font:17px/1.8 "Malgun Gothic",sans-serif}main{max-width:1000px;margin:auto;padding:52px 28px}h1{font-size:36px;line-height:1.35}h2{font-size:25px;line-height:1.45;margin:0 0 18px}section{background:white;border:1px solid #dce5df;border-radius:16px;padding:30px;margin:24px 0}a{color:#176554;text-underline-offset:4px}nav{display:flex;gap:14px;flex-wrap:wrap}nav a,.button{display:inline-block;background:#e2eee7;padding:8px 16px;border-radius:8px}p{margin:12px 0}li{margin:8px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#edf2ef;padding:18px;border-radius:8px;font-size:15px}code{font-family:Consolas,monospace}table{border-collapse:collapse;width:100%}td,th{padding:12px;border-bottom:1px solid #dce5df;text-align:left;vertical-align:top}img{max-width:100%;height:auto}small{color:#607269}.check{border-left:4px solid #32886a;padding:12px 18px;background:#edf6ef}details{border-top:1px solid #dce5df;margin-top:18px;padding-top:12px}summary{cursor:pointer}'''

def page(title,intro,sections):
    nav=''.join(f'<a href="#s{i}">{i:02d} {html.escape(t)}</a>' for i,(t,_) in enumerate(sections,1))
    body=''.join(f'<section id="s{i}"><h2>{i:02d} {html.escape(t)}</h2>{content}</section>' for i,(t,content) in enumerate(sections,1))
    return f'<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>{CSS}</style><main><small>HYD · 실습 가이드</small><h1>{title}</h1><p>{intro}</p><nav>{nav}</nav>{body}</main></html>'

RULES='''# 실습 작업 규칙

- 처음에는 파일을 바꾸지 않고, 학생이 해결하려는 업무와 관련 자료를 파악한다. 결과를 바꾸는 선택이 남아 있으면 근거가 있는 행을 짚고 학생에게 묻는다. 이미 정한 사항은 다시 묻지 않는다.
- 입력/와 자료/는 보존한다. 새 코드와 산출물은 결과/에 작성한다.
- 원자료에 없는 값·관계·실행 결과를 만들지 않는다. 미확인과 값 없음, 0을 구별한다.
- 학생이 정한 요구와 제약 안에서 구현한다. 무관한 서비스·대시보드·선정 규칙을 추가하지 않는다.
- 실행한 명령, 실제 결과, 남은 미확인을 구별한다. 검사 통과를 위해 검사 기준이나 원자료를 바꾸지 않는다.
- 완료를 알릴 때는 실행한 명령과 실제 출력, 바뀐 파일 목록을 함께 보여 준다. 실행하지 않은 것은 실행하지 않았다고 쓴다.
- DB 작업은 안내된 별도 랩 주소만 사용한다. 포털 DB와 시스템 파일을 수정하거나 전체 삭제하지 않는다.
- 접속 키·비밀번호를 코드나 결과 기록에 넣지 않는다. 개인 GitHub·commit·push는 요구하지 않는다.
- 학생이 작성한 결과를 바꿀 때만 보관한다. 제공된 빈 틀(첫머리에 「제공 빈 틀」 표시가 있는 파일, 열 이름만 있는 CSV, 내용 없는 JSON)은 보관 없이 채운다.
- 학생이 정한 목표·근거·제약과 첫 확인 사례를 짧게 되짚어 계획을 제안한다. 학생이 방향에 동의한 뒤 구현한다. 실행 중 새 선택이 필요할 때만 해당 근거를 들어 다시 상의하고, 답할 수 없는 것은 미결로 남긴다. 결과 기록에는 판단 이유와 그 선택으로 달라진 답을 남긴다.
- START.md 「이번 범위 밖」의 일(다음 실습에서 할 일 포함)은 만들지 않는다.
'''

CHECKER='''"""학생 결과의 구조·자료형 검사. 생성·수정·DB 접속을 하지 않는다.
사용: python check.py            (결과/schema.json·graph.json)
      python check.py 폴더        (다른 폴더의 schema.json·graph.json)
"""
from pathlib import Path
import json,sys
root=Path(__file__).resolve().parent
base=Path(sys.argv[1]) if len(sys.argv)>1 else root/'결과'
errors=[];warnings=[];nodes=[];rels=[];labels_by_id={}
BOOL_WORDS={'예','아니오','true','false','True','False','Y','N','yes','no','승인','비승인'}
def kind_of(v):
    return 'boolean' if isinstance(v,bool) else 'integer' if isinstance(v,int) else 'number' if isinstance(v,float) else 'string' if isinstance(v,str) else 'list' if isinstance(v,list) else type(v).__name__
def check_value(where,key,value,spec):
    if value is None:return
    if isinstance(spec,list):
        if value not in spec:errors.append(f'{where} {key}={value!r}: 허용 값 {spec} 밖')
        return
    k=kind_of(value)
    ok={'string':k=='string','number':k in('integer','number'),'integer':k=='integer','boolean':k=='boolean','list':k=='list'}.get(spec)
    if ok is None:warnings.append(f'스키마의 자료형 이름을 모름: {spec} ({where} {key})');return
    if not ok:
        hint=''
        if spec=='boolean' and isinstance(value,str) and value.strip() in BOOL_WORDS:hint=' — 참/거짓 자리에 글자가 들어 있음'
        if spec in('number','integer') and isinstance(value,str):hint=' — 숫자 자리에 글자(단위 포함 여부 확인)'
        errors.append(f'{where} {key}={value!r}: {spec} 이어야 함, 실제 {k}{hint}')
def labels_ok(actual,expected):
    allowed=expected if isinstance(expected,list) else [expected]
    return any(x in allowed for x in actual)
try:
    schema=json.loads((base/'schema.json').read_text(encoding='utf-8-sig'))
    graph=json.loads((base/'graph.json').read_text(encoding='utf-8-sig'))
    classes=schema.get('classes') if isinstance(schema,dict) else None
    relations=schema.get('relations') if isinstance(schema,dict) else None
    if not isinstance(classes,dict) or not classes or not isinstance(relations,dict) or not relations:
        errors.append('schema.json에 classes·relations가 없습니다(START.md 결과 형식 참고).');classes=classes or {};relations=relations or {}
    nodes=graph.get('nodes',[]);rels=graph.get('rels',[])
    if not nodes or not rels:errors.append('노드 또는 관계가 비어 있습니다.')
    labels_by_id={}
    for n in nodes:
        props=n.get('props',{}) if isinstance(n,dict) else {}
        id=props.get('id')
        if not isinstance(id,str) or not id:errors.append('문자열 id가 없는 노드가 있습니다.');continue
        if id in labels_by_id:errors.append('중복 id: '+id)
        labs=n.get('labels')
        if not isinstance(labs,list) or not labs:errors.append('종류가 없는 노드: '+id);labs=[]
        labels_by_id[id]=labs
        for lab in labs:
            spec=classes.get(lab)
            if spec is None:errors.append(f'스키마에 없는 종류 {lab}: {id}');continue
            req=spec.get('required',{});opt=spec.get('optional',{})
            for key,t in req.items():
                if key not in props:errors.append(f'{lab} {id}: 필수 속성 {key} 없음')
                else:check_value(f'{lab} {id}',key,props[key],t)
            for key,v in props.items():
                if key in req:continue
                if key in opt:check_value(f'{lab} {id}',key,v,opt[key])
                else:warnings.append(f'{lab}에 정의되지 않은 속성 {key} ({id})')
    seen=set()
    for r in rels:
        t=r.get('type');a=r.get('a');b=r.get('b');props=r.get('props',{}) or {}
        if not isinstance(t,str) or not t:errors.append('관계 이름이 없습니다.');continue
        key=(t,a,b,props.get('id'))
        if a not in labels_by_id or b not in labels_by_id:errors.append('없는 관계 끝점: '+str((t,a,b)));continue
        if key in seen:errors.append('중복 관계: '+str((t,a,b)))
        seen.add(key)
        spec=relations.get(t)
        if spec is None:errors.append(f'스키마에 없는 관계 {t}: {a} → {b}');continue
        if 'from' in spec and not labels_ok(labels_by_id[a],spec['from']):errors.append(f'{t} 시작 종류가 다름: {a} {labels_by_id[a]} (정의 {spec["from"]})')
        if 'to' in spec and not labels_ok(labels_by_id[b],spec['to']):errors.append(f'{t} 끝 종류가 다름: {b} {labels_by_id[b]} (정의 {spec["to"]})')
        pspec=spec.get('properties',{})
        for k in spec.get('required',[]):
            if k not in props:errors.append(f'{t} {a}→{b}: 필수 속성 {k} 없음')
        for k,v in props.items():
            if k in pspec:check_value(f'{t} {a}→{b}',k,v,pspec[k])
            elif k!='id':warnings.append(f'{t}에 정의되지 않은 속성 {k}')
except (OSError,ValueError,TypeError,AttributeError) as e:
    errors.append(str(e))
if warnings:
    uniq=sorted(set(warnings));print(f'참고 {len(uniq)}건(정의와 다른 속성 등):');print('\\n'.join('  '+w for w in uniq[:12])+('\\n  …' if len(uniq)>12 else ''))
spread={}
for r in rels if isinstance(rels,list) else []:
    a,b=r.get('a'),r.get('b')
    if a in labels_by_id and b in labels_by_id:
        k=(r.get('type'),'/'.join(labels_by_id[a]),'/'.join(labels_by_id[b]));spread[k]=spread.get(k,0)+1
if spread:
    print('참고: 관계마다 어느 종류에서 어느 종류로 이어졌는지(원자료의 행 수·붙은 곳과 대조하세요)')
    for (t,x,y),n in sorted(spread.items()):print(f'  {t}: {x} → {y} {n}개')
    # 같은 관계가 포함하는 쪽(위)과 포함되는 쪽(아래)에 함께 붙는 종류가 있으면, 아래를 거치지 않고 위에 바로 붙은 대상을 따로 센다.
    # 관계 방향은 학생이 정하므로(센서→설비로 둘 수도 있음) 붙음은 양쪽 방향으로 본다. 포함(위→아래)은 정의된 방향 그대로.
    contain={(x,y) for (t,x,y) in spread if x!=y}
    touch={(t,x,y) for (t,x,y) in spread}|{(t,y,x) for (t,x,y) in spread}
    direct={}
    for (t,top,s) in sorted(touch):
        mids=[mid for (t2,mid,s2) in touch if t2==t and s2==s and mid not in (top,s) and (top,mid) in contain]
        if not mids:continue
        per={}
        for r in rels:
            a,b=r.get('a'),r.get('b');la,lb='/'.join(labels_by_id.get(a,[])),'/'.join(labels_by_id.get(b,[]))
            if r.get('type')!=t:continue
            if (la,lb)==(top,s):per.setdefault(a,[]).append(b)
            elif (la,lb)==(s,top):per.setdefault(b,[]).append(a)
        if per:direct[(t,top,s,'/'.join(sorted(mids)))]=per
    for (t,top,s,mids),per in sorted(direct.items()):
        print(f'참고: {mids}를 거치지 않고 {top}에 바로 붙은 {s} {sum(len(v) for v in per.values())}개({t}). 원자료의 붙은곳이 정말 {top} 전체인 행인지 대조하세요.')
        print('  '+', '.join(f'{a} {len(v)}개' for a,v in sorted(per.items())[:12])+(' …' if len(per)>12 else ''))
if errors:
    print(f'구조 확인 필요 {len(errors)}건');print('\\n'.join(errors[:40])+('\\n…' if len(errors)>40 else ''));sys.exit(1)
print(f'구조 검사 통과: 노드 {len(nodes)}개, 관계 {len(rels)}개. 원자료의 의미·단위·질문별 답은 별도로 대조하세요.')
'''

QUESTIONS={
'통합반':['설비별로 어떤 구성 요소에 어떤 센서·계산값·설정값이 붙어 있는가?',
          '각 센서가 재는 물리량과 단위·정상값·한계(위로 넘는지, 아래로 떨어지는지)는 무엇인가? 설비마다 태그 이름이 달라도 같은 물리량을 재는 센서를 함께 찾을 수 있는가?',
          '교체 부품별로 그 부품을 쓰는 설비와 구성 요소는 무엇인가? 다른 표기로 적힌 품번이나 원자료에 없는 품번으로 물으면 결과가 어떻게 구별되는가?'],
'실전반':['선택한 부품을 쓰는 설비와 구성 요소는 무엇인가?',
          '그 부품의 공급사별 승인 여부·단가·불량률·납기는 무엇이고, 각 값은 어느 파일·어느 날짜 자료에서 왔는가?',
          '비슷한 이름의 다른 품번, 예전 품번이나 다른 표기, 원자료에 없는 품번으로 물었을 때 결과가 서로 구별되는가?']}
# 실습4에서만 질문에 붙이는 업무 맥락. 이 답을 누가 무엇에 쓰는지만 적고, 수정본의 상태 변경을 어떻게 다룰지는 적지 않는다.
LAB4_CONTEXT={'통합반':(2,' 보전팀은 이 답으로 지금 가동하는 설비의 예비품 준비를 정한다.'),
              '실전반':(0,' 보전·구매 담당은 이 답으로 지금 가동하는 설비의 예비품 수요를 본다.')}
def lab4_questions(course):
    qs=list(QUESTIONS[course]);i,extra=LAB4_CONTEXT[course]
    head,sep,tail=qs[i].partition('? ')
    qs[i]=(head+'?'+extra+' '+tail) if sep else qs[i]+extra
    if course == '실전반':
        qs[0] = '세 설비가 함께 쓰는 펌프 축 씰 키트를 어느 설비·구성요소에서 쓰며, 기준일의 세 공급 조건은 어떤 근거로 구별할 수 있는가? ' + extra.strip()
    else:
        qs.append('포털 기준 지도에서 같은 대상을 찾아보면 내 모델과 식별자·관계 방향이 어디서 같고 어디서 다른가?')
    return qs+LAB4_EXTRA[course]
LAB4_EXTRA={'통합반':['수정본을 반영한 뒤에도 같은 ID가 유지되고, 다시 적재해도 대상과 관계가 늘지 않는가?'],
            '실전반':['견적 납기와 지난 입고의 실측 납기는 공급사별로 얼마나 다른가?','수정본을 반영한 뒤에도 같은 ID가 유지되고, 다시 적재해도 대상과 관계가 늘지 않는가?']}

FORMAT='''## 결과 형식

`check.py`와 다음 실습이 읽는 모양입니다. 무엇을 종류·속성·관계로 둘지는 직접 정합니다.

- `결과/schema.json`: `{"classes": {종류: {"meaning": 뜻, "required": {속성: 자료형}, "optional": {속성: 자료형}}}, "relations": {관계: {"from": 종류 또는 [종류…], "to": 종류, "cardinality": "1:N" 등, "properties": {속성: 자료형}}}}`
- 자료형은 `string`·`number`·`integer`·`boolean`·`list` 중 하나이거나, 허용 값 목록(예: `["upper", "lower"]`)입니다.
- `결과/graph.json`: `{"nodes": [{"labels": [종류], "props": {"id": 고유 ID, …}}], "rels": [{"type": 관계, "a": 시작 id, "b": 끝 id, "props": {…}}]}`
- 같은 두 대상 사이에 같은 관계를 여러 개 두려면 그 관계의 props에 `id`를 붙입니다.
'''

# 두 과정은 각각 첫 설계 랩에서 도구를 배운다. 네 문장은 안내 HTML의 해당 행동에도 쓴다.
OPEN_DESIGN = ('왼쪽 탐색기(Explorer) 맨 위에서 이 실습의 폴더 이름을 확인하세요. '
               '가운데 편집기에 START.md 탭이 열려 있으면 이번 질문을 읽으세요. '
               '탭이 보이지 않으면 탐색기에서 START.md를 누르면 됩니다.')
OPEN_AI = ('활동 표시줄에서 사용하는 AI의 아이콘을 열고 패널 제목에서 Codex 또는 GitHub Copilot을 확인하세요. '
           '패널 아래 입력칸에 이번 질문을 자기 말로 적고 보냅니다. 첫 요청에서는 파일을 바꾸지 말고 근거 행을 찾아 달라고 하세요. '
           '답변에 나온 파일을 왼쪽 탐색기에서 열어 가운데 편집기의 실제 행을 읽습니다.')
REVIEW_EDIT = ('편집 승인을 묻는 경우 경로와 변경 내용을 확인합니다. '
               '결과/ 안에서 요청한 변경만 허용하세요. AI가 선택을 물으면 자료의 행을 확인하고 판단 이유를 답합니다.')
OPEN_TERMINAL = ('메뉴에서 터미널 → 새 터미널(Terminal → New Terminal)을 선택하세요. '
                 '아래쪽 터미널에 이번 실습 폴더의 경로와 입력 커서가 보이면 다음 명령을 쓰고 Enter를 누릅니다. '
                 '출력 마지막 줄을 읽고 질문에 대한 실제 답은 원자료 행과 따로 대조하세요.')
LAB_DB_UI = ('터미널에서 python lab_db.py를 실행하고 「랩 DB 준비 완료」와 이 폴더에 배정된 주소를 확인하세요. '
             '열린 Neo4j Browser 위쪽에 조회문을 넣고 실행한 뒤 Table에서 행을 읽습니다. '
             'AI가 명령 실행 승인을 요청하면 이 폴더의 적재·조회 명령과 랩_연결.json의 주소가 일치하는지 먼저 확인하세요.')

def steps_text(rec, number):
    first = OPEN_AI if number == 3 else 'AI 채팅에서 입력 파일과 수정본을 확인하고, 파일을 고치기 전에 처음 대조할 행을 짚어 보세요.'
    permission = ' ' + REVIEW_EDIT if number == 3 else ''
    db = '## 구현 실습에서 쓸 도구\n\n' + LAB_DB_UI + '\n\n' if number == 4 else ''
    return (db + '## 진행 방법\n\n'
        f'1. {first}\n'
        f'2. 목표·입력·지킬 조건과 내가 정한 결정을 자기 말로 `{rec}`에 적으세요. 자료를 읽는 방식에 따라 답이 달라지는 지점을 하나 이상 찾아, 무엇으로 정했고 근거가 어느 파일·줄인지 함께 적습니다. 구현 전에 질문별 기대 답을 원자료에서 몇 개 직접 찾아 둡니다.\n'
        f'3. AI가 이해한 목적과 계획을 읽으세요. 앞에서 찾은 행에 적용하면 어떤 답이 나와야 하는지 서로 맞춘 뒤 구현을 맡깁니다. 다음 요청에는 방금 내린 결정과 확인에 필요한 파일·실행 결과만 짚어 주세요.{permission}\n'
        '4. 완료 보고에는 실행한 명령과 출력 원문을 붙여 달라고 요청하세요. 바뀐 파일도 확인합니다. 입력/·자료/는 바뀌지 않아야 합니다.\n'
        '5. 적어 둔 기대 답과 실제 결과를 대조하고, 다르면 입력·기대·실제를 함께 전달해 고치세요. 고친 뒤에는 내가 예로 든 행만 맞았는지가 아니라 같은 종류의 다른 행에도 통하는지 다시 세어 달라고 합니다.\n\n'
        '요청에 파일 이름을 쓸 때는 `결과/schema.json`처럼 백틱(`)으로 감쌉니다. 채팅 입력이 밑줄(_)을 서식으로 바꾸기 때문입니다.\n')

def start_text(course,number,questions):
    practical=course=='실전반'
    qlist='\n'.join(f'{i}. {q}' for i,q in enumerate(questions,1))
    if number==3 and not practical:
        title='현장 정보를 체계화하는 온톨로지 직접 설계하기'
        goal='포털 지도에서 오일 쿨러와 센서가 어떻게 연결되는지 살펴봤습니다. 이번에는 창원1공장 유압 설비 7대의 대장·구성요소·SCADA 태그·예비품 자료를 하나의 설비 지식 모델(종류·속성·관계)로 정리합니다. 손으로 다 맞춰 볼 수 없는 양이므로 AI와 코드로 처리하고, 원자료와 자동으로 대조해 확인합니다.'
        start='`자료/`의 CSV 8개와 `현장_메모.md`, `입력/관계그림.json`(앞 단계에서 그린 관계)에서 출발합니다. 이번 모델(스키마·인스턴스)은 아직 없습니다. 공급·입고 자료는 이번 질문 밖이며 모델에 넣지 않아도 됩니다.'
        work='종류와 개별 대상을 나누고 식별자·속성의 자료형·필수 여부·관계 방향·연결 수를 정의한 뒤, 그 정의로 원자료 전체의 인스턴스를 만듭니다. 원자료를 읽어 대상을 만드는 코드는 `결과/`에 두어 다시 실행할 수 있게 합니다. 자료를 정리하며 내린 처리는 `결과/자료_검토.md`에 자료·행 단위로 남깁니다.'
        cases='같은 태그 이름이 여러 설비에 있는 경우 / 이름이 다른데 같은 것을 재는 태그 / 같은 장치를 다르게 부른 이름 / 같은 대상이 두 번 나온 행 / 비어 있는 칸(단위·교체부품·정상값) / 단위 표기가 다른 값 / 계기 없는 계산값과 설정값 / 여러 설비가 함께 쓰는 부품과 한 설비만 쓰는 부품 / 품번 대신 품명·다른 표기로 적힌 칸 / 원자료에 없는 품번'
        decide=('- 같은 규격(제조사 품번)으로 등록된 서로 다른 사내 품번을 한 물품으로 볼지, 그 규격으로 물었을 때 무엇이 나와야 하는지\n'
                '- 교체부품 칸이 비었거나 품번이 아닌 글(품명·규격명)로 적힌 행을 어느 사내 품번에 연결할지, 연결하지 않을지\n'
                '- 그 밖에 탐색에서 찾은, 자료를 읽는 방식에 따라 답이 갈리는 곳')
        outside='공급 조건·입고 이력의 모델링, 그래프 DB 적재와 조회(다음 실습)'
        outputs='`결과/schema.json`, `결과/graph.json`, `결과/요구사항.md`, `결과/자료_검토.md`, 모델을 만든 코드'
        command='python check.py'
    elif number==3:
        title='설비·부품·공급 정보를 연결하는 온톨로지 설계하기'
        goal='포털 지도에서는 펌프에서 씰 키트와 공급사를 찾았습니다. 이번에는 제공된 설비·부품 모델에 구매팀의 견적·승인·품번 자료를 연결해, 부품별 사용 설비와 공급 조건을 함께 답하는 모델로 확장합니다. 공급사를 고르거나 점수화하지는 않습니다.'
        start='`입력/schema.json`·`graph.json`은 설비 7대·구성요소·센서·부품까지 정리된 앞 단계 완성 모델입니다. 공급 정보는 아직 연결되어 있지 않습니다. `자료/`에 원자료 전체(견적·승인 공급사·품번 교차표·입고 이력 포함)가 있습니다.'
        work='공급 자료를 모델의 어디에 어떤 종류·속성·관계로 둘지 정하고, 기존 설비·부품 연결과 ID를 유지하면서 모델을 확장합니다. 여러 설비가 함께 쓰는 품번 하나를 골라, 모델에서 그 품목이 몇 개이고 어느 설비에서 그 품목으로 이어지는지 원자료와 대조합니다. 값마다 단위와 출처(파일·날짜)를 남기고, 원자료에서 공급 정보를 만드는 코드를 `결과/`에 둡니다. 자료를 정리하며 내린 처리는 `결과/자료_검토.md`에 남깁니다.'
        cases='같은 대상의 여러 기록(같은 쌍·같은 품목이 여러 줄이나 여러 파일에 나오는 경우) / 출처마다 다른 값이나 표기 / 비슷한 이름의 다른 품번과 원자료에 없는 품번'
        decide=('- 기준일에 제시할 조건을 어떤 기록에서 가져올지, 다른 날짜나 조건의 기록은 어떻게 구분할지\n'
                '- 출처마다 승인 표시가 다르거나 조건·기한이 붙었을 때 구매 담당자에게 무엇을 보여 줄지\n'
                '- 그 밖에 탐색에서 찾은, 자료를 읽는 방식에 따라 답이 갈리는 곳')
        outside='입고 이력과 실측 납기(다음 실습), 공급사 선정·점수화, 그래프 DB 적재와 조회'
        outputs='`결과/schema.json`, `결과/graph.json`, `결과/요구사항.md`, `결과/자료_검토.md`, 공급 정보를 만든 코드'
        command='python check.py'
    else:
        title='부품의 사용 설비와 공급 정보를 조회하는 그래프 구현하기' if practical else '설계한 온톨로지를 그래프 DB에 구현하고 검증하기'
        goal=('앞 단계 완성 모델(설비·부품·공급)을 별도 랩 DB에 적재하고, 부품별 사용 설비와 공급 조건을 반환하는 조회를 만듭니다. 수정본 반영과 반복 적재에서 중복이 생기지 않는지 확인합니다.' if practical else
              '앞 단계 완성 모델을 별도 랩 DB에 적재하고, 질문마다 조회를 만들어 원자료와 대조합니다. 수정본을 반영하고 다시 적재해도 같은 ID가 유지되고 중복이 생기지 않는지 확인합니다.')
        start='`입력/schema.json`·`graph.json`은 앞 단계 완성 모델이고, `입력/자료/`는 그 원자료, `입력/자료_변경분/`은 기준일 뒤 들어온 수정본입니다. 이전 개인 결과 없이 시작할 수 있습니다. 개인 모델을 쓰려면 제공 입력을 보존하고 작업 사본에 옮기세요. 모델을 만든 시점과 질문, 파일 형식 및 ID가 이번 입력과 맞는지 보고, 관계 이름이나 방향이 다르면 개인 모델의 정의로 조회하세요.'
        work=('적재(모델 → DB)와 조회를 작성합니다. 같은 입력을 두 번 적재해도 대상과 관계가 늘지 않아야 하고, 이름이 바뀌어도 같은 ID의 대상은 유지되어야 합니다. 전체 삭제문은 쓰지 않고, 수정본은 필요한 대상만 고쳐 반영합니다.'
              ' 세 설비가 함께 쓰는 펌프 축 씰 키트의 품번을 원자료에서 찾아 사용 설비와 공급 조건 세 행을 조회하고, 다른 품번·없는 품번도 조회합니다. 비승인 공급사는 승인 상태와 함께 구별해 보여 줍니다. 실측 납기는 `입력/자료/입고_이력.csv`에서 계산합니다.' if practical else
              '적재(모델 → DB)와 조회를 작성합니다. 같은 입력을 두 번 적재해도 대상과 관계가 늘지 않아야 하고, 이름이 바뀌어도 같은 ID의 대상은 유지되어야 합니다. 전체 삭제문은 쓰지 않고, 수정본은 필요한 대상만 고쳐 반영합니다. 포털 지식 지도에서 설비 → 쿨러 → 센서를 따라가고, 자기 모델에서 같은 역할을 하는 대상의 ID와 관계의 시작·끝을 검증 기록에 나란히 적습니다. 공용 부품의 사용 설비를 원자료와 대조하고, 다른 품번과 원자료에 없는 품번도 조회해 결과를 구별합니다.')
        cases=('공용 부품 / 비슷한 이름의 다른 품번 / 예전 품번·다른 표기 / 원자료에 없는 품번 / 비승인·조건이 붙은 공급사 / 나눠 들어온 입고 / 수정본의 이름 변경·상태 변경·값 보완 / 같은 적재 두 번' if practical else
               '설비별 구성 요소·센서 개수 / 태그 이름이 달라도 같은 물리량 / 한계 방향과 한계 없음 / 공용 부품과 전용 부품 / 다른 표기·없는 품번 / 수정본의 이름 변경·상태 변경·값 보완 / 같은 적재 두 번')
        cases+=' / 공급사 이름 표기(견적표·승인 목록·입고 이력)' if practical else ''
        outputs='`결과/load.cypher`(또는 적재 코드), `결과/query.cypher`, `결과/검증_기록.md`'
        command='python lab_db.py'
        decide=('- 수정본에서 상태가 바뀐 설비를 그래프에 어떻게 반영하고, 질문의 답(지금 가동하는 설비 기준)에 어떻게 드러낼지\n'
                +('- 나눠 들어온 발주의 실측 납기를 어느 입고로 셀지\n' if practical else '')
                +'- 그 밖에 탐색에서 찾은, 자료를 읽는 방식에 따라 답이 갈리는 곳')
        outside='공급사 선정·점수화' if practical else '공급 조건·입고 이력의 적재와 조회'
    rec='결과/요구사항.md' if number==3 else '결과/검증_기록.md'
    fmt=FORMAT if number==3 else ''
    extra=''
    if decide:
        extra+=(f'## 학생이 정할 것\n\n원자료만으로 하나로 정해지지 않아 학생이 근거를 찾아 정하는 지점입니다. 어느 행이 해당하는지는 탐색에서 직접 찾고, 정한 내용·근거 줄·바뀌는 답을 `{rec}` 결정 표에 적습니다. AI는 이 지점을 정하기 전에 학생에게 묻습니다.\n\n{decide}\n\n')
    if outside:
        extra+=f'## 이번 범위 밖\n\n{outside}. 자료에 있어도 이번 결과에 만들지 않습니다.\n\n'
    browser_step = '열린 Neo4j Browser에서 적재문을 실행하고 노드와 관계의 개수를 확인하세요. 같은 적재문을 다시 실행해 개수를 비교하세요. 조회 결과를 기록한 뒤 수정본을 반영하고, 같은 조회에서 어떤 행이 달라졌는지 확인하세요.' if number == 4 else ''
    folder_step = OPEN_DESIGN + '\n\n' if number == 3 else ''
    check_step = OPEN_TERMINAL + '\n\n' if number == 3 else ''
    handoff = ('결과/schema.json과 결과/graph.json을 한 쌍으로, 요구사항·자료 검토 기록과 함께 보관하세요. '
               '사용한 원자료 기준일과 저장 시점을 기록하고 복사본을 다시 열어 같은 업무 질문을 확인하세요. '
               '다음 구현 실습에서는 이 판본을 선택하거나 제공된 모델로 시작할 수 있습니다.'
               if number == 3 else '적재·조회 파일과 검증 기록을 함께 보관하세요. 기록에는 반영한 자료의 기준일과 수정본 날짜를 적고, 복사본에서 같은 품번의 조회 결과를 다시 확인하세요.')
    body=(f'# {title}\n\n{goal}\n\n## 출발점\n\n{folder_step}{start}\n\n## 이번에 해결할 질문\n\n{qlist}\n\n## 작업\n\n{work}\n\n'
          f'## 확인할 사례의 종류\n\n{cases}\n\n어느 행이 해당하는지는 원자료에서 직접 찾습니다.\n\n{extra}{fmt}\n{steps_text(rec, number)}\n'
          f'## 저장할 결과\n\n{outputs}\n\n## 확인\n\n{check_step}```\n{command}\n```\n\n'
          + (browser_step+'\n\n' if browser_step else '') +
          '## 완료 판정\n\n형식 검사나 실행 성공만으로 완료하지 않습니다. 질문마다 원자료의 행과 실제 답을 대조하고, 내가 정한 결정에 따라 답이 어떻게 달라지는지 설명할 수 있어야 합니다. 수정한 점과 확인하지 못한 점을 짧게 남깁니다.\n\n'
          f'## 저장과 다음 실습\n\n{handoff} 재부팅 전에 작업 폴더를 USB 또는 개인 클라우드에 복사하세요.\n')
    return title,goal,start,work,cases,outputs,command,browser_step,body,handoff

def pack(folder):
    archive=folder.with_suffix('.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for file in sorted(folder.rglob('*')):
            if file.is_file() and '__pycache__' not in file.parts and file.name!='.env':
                z.write(file,file.relative_to(folder.parents[2]))
    return archive

GUIDE_HEADINGS = ('시작하기', '요구 정하기', 'AI와 만들기', '결과 확인하기', '저장하기')
PICTURE_TYPES = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg', '.avif', '.tif', '.tiff'}


def student_photos(folder, provenance):
    """이 랩의 학생 화면만 출처·판본과 맞춘다. 불일치 파일은 손대지 않는다."""
    prefix = '산출물/' + folder.relative_to(OUT).as_posix() + '/images/'
    photos = {}
    for record in provenance:
        target = record['target'].removeprefix('workspace/강의제작/')
        if not target.startswith(prefix) or record.get('kind') != '학생 실습 화면':
            continue
        name = 'images/' + target[len(prefix):]
        if (name in photos or record.get('section') not in GUIDE_HEADINGS or not record.get('caption')
                or Path(name).suffix.lower() not in {'.png', '.jpg', '.jpeg', '.webp'}
                or not record.get('source') or not re.fullmatch('[0-9a-f]{64}', record.get('source_sha256', ''))):
            raise ValueError(f'{target}: 학생 화면의 출처·절·설명 또는 중복 항목을 확인하세요.')
        photos[name] = record
    actual = {p.relative_to(folder).as_posix() for p in folder.rglob('*')
              if p.is_file() and (p.is_relative_to(folder/'images') or p.suffix.lower() in PICTURE_TYPES)}
    if actual != set(photos):
        raise ValueError(f'{folder}: 학생 화면 목록과 다른 파일 {sorted(actual ^ set(photos))}')
    for name, record in photos.items():
        if hashlib.sha256((folder/name).read_bytes()).hexdigest() != record['sha256']:
            raise ValueError(f'{folder/name}: 학생 화면의 해시가 다릅니다.')
    return photos


def reset_generated(folder):
    """이 생성기가 만드는 자리만 새로 만든다. 결과/의 학생 파일은 건드리지 않는다."""
    for sub in ['자료','입력/자료','입력/자료_변경분']:
        p=folder/sub
        if p.is_dir() and p.resolve()!=D.SOURCE.resolve():shutil.rmtree(p)
    for old in ['검증_기록.md','설계_검토표.md']:   # 옛 판의 폴더 루트 빈 틀(결과/로 옮김)
        if (folder/old).is_file():(folder/old).unlink()

def main():
    provenance = json.loads(Path(__file__).with_name('capture-provenance.json').read_text(encoding='utf-8'))
    photos = {(course, name): student_photos(OUT/course/'실습/02회차/랩'/name, provenance)
              for course, _ in COURSES for name in (LAB3, LAB4)}
    D.write_sources()
    for course,_ in COURSES:
        practical=course=='실전반'
        for branch in ['A','B']:
            schema,graph=reference_model(practical,branch)
            dest=TEACHER/course if branch=='A' else TEACHER/course/'갈래B'
            dump(dest/'schema.json',schema);dump(dest/'graph.json',graph)
    base_schema,base_graph=reference_model()
    catalog=[]
    for course,slug in COURSES:
        practical=course=='실전반'
        for number,name in [(3,LAB3),(4,LAB4)]:
            folder=OUT/course/'실습/02회차/랩'/name
            reset_generated(folder)
            for sub in ['입력','결과']: (folder/sub).mkdir(parents=True,exist_ok=True)
            write(folder/'AGENTS.md',RULES)
            write(folder/'.github/copilot-instructions.md',RULES)
            write(folder/'CLAUDE.md',RULES)
            questions=QUESTIONS[course] if number==3 else lab4_questions(course)
            title,goal,start,work,cases,outputs,command,browser_step,body,handoff=start_text(course,number,questions)
            if number==3:
                if not (folder/'입력/관계그림.json').is_file():
                    raise FileNotFoundError('이전 단계 관계 그림 입력이 없습니다: '+str(folder))
                if (folder/'자료').resolve()!=D.SOURCE.resolve():shutil.copytree(D.SOURCE,folder/'자료')
                if practical:
                    dump(folder/'입력/schema.json',base_schema);dump(folder/'입력/graph.json',base_graph)
                write(folder/'check.py',CHECKER)
                write(folder/'결과/요구사항.md','# 이번에 만들 결과\n\n> 제공 빈 틀입니다. 보관하지 말고 바로 채웁니다.\n\n## 목표와 질문\n\n## 사용할 자료와 범위\n\n## 지켜야 할 조건\n\n## 내가 정한 결정\n\n| 답이 갈리는 지점 | 정한 내용 | 근거(파일·행) | 바뀌는 답 |\n|---|---|---|---|\n| | | | |\n\n## 확인할 입력과 기대 결과\n')
                write(folder/'결과/자료_검토.md','# 원자료 대조\n\n> 제공 빈 틀입니다. 보관하지 말고 바로 채웁니다.\n\n| 자료·행 | 확인한 문제 또는 근거 | 선택한 처리 | 결과 확인 |\n|---|---|---|---|\n')
                write(folder/'결과/README.md','이번 과제의 모델(schema.json, graph.json)과 모델을 만든 코드, 요구사항.md, 자료_검토.md를 여기에 저장합니다.\n')
                write(folder/'입력/README.md',start.replace('`','')+'\n')
            else:
                shutil.copy2(ROOT/'workspace/강의제작/제작도구/실습시작/lab_db.py',folder/'lab_db.py')
                schema,graph=reference_model(practical)
                dump(folder/'입력/schema.json',schema);dump(folder/'입력/graph.json',graph)
                shutil.copytree(D.SOURCE,folder/'입력/자료')
                D.write_changes(folder/'입력/자료_변경분'/f'{D.CHANGE_DATE}_수정본',practical)
                write(folder/'입력/요구사항.md','# 제공 시작 모델의 질문\n\n'+'\n'.join('- '+q for q in QUESTIONS[course])+'\n')
                write(folder/'입력/자료_검토.md','# 제공 모델의 자료 처리 근거\n\n'
                      '이 모델은 강사가 원자료와 현장 메모로 만든 앞 단계 완성본이다. 학생의 이번 적재·조회 결과가 아니다. 처리 기준은 schema.json의 constraints에 적혀 있다.\n\n'
                      '- 설비: 「코드 통합」 이관 기록은 대상을 새로 만들지 않고 legacy_codes로 남겼다. 구성요소는 기능 자리 기준 ID이고 실물 교체는 serial로 남겼다(철거 행 제외).\n'
                      '- 센서: 같은 설비·태그의 점검표 재기입 행은 하나로 두었다. 단위는 물리량 기준 단위로 맞추고 바꾼 경우 source_unit을 남겼다. 계산값·설정값은 kind로 구별했다. 한계가 없으면 limit을 생략했다.\n'
                      '- 부품: 교체부품 칸의 품명·표기 변형·제조사 품번은 품번 교차표와 예비품 목록의 적용 모델·쓰는곳으로 사내 품번에 연결했다.\n'
                      +('- 공급: 공급사·품번마다 기준일에 유효한 최신 견적 하나를 SUPPLIES로 두었다. 승인 여부는 승인공급사_목록과 기준일로 정했다(조건부 승인은 approved=true, 조건은 condition).\n' if practical else ''))
                write(folder/'입력/README.md',start.replace('`','')+'\n')
                write(folder/'결과/README.md','적재문(또는 적재 코드), 조회문, 검증_기록.md를 여기에 저장합니다.\n')
                write(folder/'결과/검증_기록.md','# 실습 확인 기록\n\n> 제공 빈 틀입니다. 보관하지 말고 바로 채웁니다.\n\n- 확인 시각 / 사용한 랩 DB 주소(인증값 제외):\n- 작성한 파일:\n\n## 내가 정한 결정\n\n| 답이 갈리는 지점 | 정한 내용 | 근거(파일·행) | 바뀌는 답 |\n|---|---|---|---|\n| | | | |\n\n'
                     '## 질문별 대조\n\n| 질문·검사 | 원자료에서 먼저 찾은 기대 답 | 실제 조회 결과 | 수정과 재확인 |\n|---|---|---|---|\n| | | | |\n\n'
                     '## 적재·재적재·수정본\n\n| 단계 | 노드 수 | 관계 수 | 확인한 것 |\n|---|---|---|---|\n| 첫 적재 | | | |\n| 같은 적재 다시 | | | |\n| 수정본 반영 | | | |\n\n## 확인하지 못한 점\n')
            write(folder/'START.md',body)
            write(folder/'준비_안내.md','# 실습 준비\n\nVS Code에서 이 파일이 들어 있는 폴더를 연 뒤 [START.md](START.md)의 출발점과 질문을 확인하세요.\n')
            qs=''.join(f'<li>{html.escape(q)}</li>' for q in questions)
            principle='<li>질문마다 원자료에서 먼저 찾은 기대 답과 실제 결과를 나란히 적습니다.</li><li>자료를 읽는 방식에 따라 답이 갈리는 지점은 내가 정한 결정과 근거 행을 함께 남깁니다.</li><li>값이 없음·미확인·0을 구별합니다.</li>'
            if number==4:principle+='<li>같은 입력을 다시 적재해도 노드·관계 수가 늘지 않습니다. 수정본 반영 뒤의 개수 변화는 수정본의 행으로 설명할 수 있어야 합니다.</li><li>수정본의 「삭제」 줄을 반영한 뒤에는 그 설비의 센서 수를 원자료의 행과 다시 세어, 실제로 있는 센서가 사라지지 않았는지 확인합니다.</li><li>상태가 바뀐 설비가 질문의 답에 어떻게 나오는지(빠지는지, 상태와 함께 나오는지)를 결정 표의 결정과 대조합니다.</li>'
            if number==3 and not practical:principle+='<li>붙은곳 이름이 대장 이름과 다른 설비 하나를 골라, 구성요소마다 붙은 센서를 원자료 행과 하나씩 대조합니다. <code>python check.py</code>가 끝에 보여 주는 「관계마다 어느 종류에서 어느 종류로」 개수도 원자료의 붙은곳과 견줍니다.</li><li>같은 규격으로 등록된 다른 사내 품번이 있으면, 그 규격으로 물었을 때 나와야 할 결과를 먼저 정하고 근거 줄과 함께 결정 표에 적습니다.</li>'
            if number==3 and practical:principle+='<li>한 품번의 조회 결과에서 비용·납기·승인 상태가 어느 자료의 어느 날에 나온 값인지 찾아보세요. 다른 품번이나 다른 날짜로 물었을 때 무엇이 달라져야 할지 먼저 적고 확인하세요.</li>'
            if practical:principle+='<li>가격·납기로 공급사를 자동 선정하지 않습니다.</li>'
            next_link='../'+(LAB4 if number==3 else LAB3)+'/guide.html'
            tree='입력/   앞 단계 결과·완성 모델\n'+('자료/   현장 원자료(CSV 8개·현장 메모)\n' if number==3 else '입력/자료/   원자료 · 입력/자료_변경분/   수정본\n')+'결과/   이번에 만들 결과\nAGENTS.md   AI 작업 규칙'
            open_step = OPEN_DESIGN if number == 3 else '열린 구현 실습 폴더의 START.md와 입력/graph.json을 확인하세요.'
            ai_step = OPEN_AI + ' ' + REVIEW_EDIT if number == 3 else 'AI 채팅에서 이번 입력과 적재·조회 계획을 확인한 뒤, 질문 하나씩 요청하고 바뀐 파일을 엽니다.'
            terminal_step = OPEN_TERMINAL if number == 3 else '앞에서 연결한 이 폴더 전용 랩 DB의 주소를 다시 확인하세요.'
            sections=[('시작하기',f'<p>{html.escape(goal)}</p><p>{html.escape(start.replace("`",""))}</p><p>{open_step} <a href="START.md">이번 실습의 질문과 완료 조건</a>을 확인하세요. AI 계정 없이 결과를 확인하려면 실습 폴더와 별도로 제공되는 학생용 완성본 ZIP을 받으세요.</p><pre>{html.escape(tree)}</pre>'),
                      ('요구 정하기',f'<ol>{qs}</ol><p>자료에서 답의 근거를 찾고, AI에 전달할 목표·제약·내가 정한 결정을 정리하세요. 확인할 사례의 종류: {html.escape(cases)}.</p>'),
                      ('AI와 만들기',f'<p>{html.escape(work)}</p><p>{ai_step} 완료 보고에는 실행 출력 원문을 붙여 달라고 요청합니다. 파일 이름은 백틱(`)으로 감싸 입력하세요.</p><p>AI에게 요청할 때에는 누가 쓸 결과인지, 어떤 자료와 결정을 따를지, 어느 사례로 확인할지 자기 말로 전하세요.</p>'),
                      ('결과 확인하기',f'<p>{terminal_step}</p>'+ (f'<p>{html.escape(browser_step)}</p>' if browser_step else f'<pre>{html.escape(command)}</pre>') +f'<ul>{principle}</ul><p class="check">원자료와 실제 결과를 대조하세요. AI의 완료 메시지는 실행 결과를 대신하지 않습니다.</p>'),
                      ('저장하기',f'<p>{html.escape(outputs.replace("`",""))}</p><p>{html.escape(handoff)} 재부팅 전에 작업 폴더를 USB 또는 개인 클라우드에 복사하세요.</p>')]
            if number==4:
                sections[0]=(sections[0][0],sections[0][1]+'<p>터미널에서 아래 명령을 실행하세요. Docker가 실행 중이어야 합니다.</p><pre>python lab_db.py</pre><p>「랩 DB 준비 완료」가 나오면 열린 Browser의 Protocol에서 bolt://를 선택하고 Connection URL에는 출력 주소의 127.0.0.1:포트 부분만 넣으세요. Database user는 neo4j, Password는 비워 두고 Connect를 누릅니다. 연결 정보는 랩_연결.json에도 저장됩니다.</p>')
                sections[3]=(sections[3][0],sections[3][1]+'<p>개수 확인 예: <code>MATCH (n) RETURN labels(n)[0] AS 종류, count(*) ORDER BY 종류</code>. 조회 결과는 Browser의 Table 보기로 원자료의 행과 대조합니다.</p>')
            headings = [heading for heading, _ in sections]
            for picture, record in photos[course, name].items():
                index = headings.index(record['section'])
                heading, content = sections[index]
                caption = html.escape(record['caption'])
                src = html.escape(picture, quote=True)
                sections[index] = (heading, content + f'<figure><img src="{src}" alt="{caption}"><figcaption>{caption}</figcaption></figure>')
            guide = page(title,html.escape(goal),sections)
            write(folder/'guide.html',guide)
            write(folder/'안내.html',guide)
            archive=pack(folder)
            relative=archive.relative_to(ROOT).as_posix()
            catalog.append({'id':f'{slug}-02-'+('ontology' if number==3 else 'graph'),'course':course,'session':'온라인 02회차','title':title,'version':VERSION,'folder':f'02회차/랩/{name}','path':relative,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()})
    index = ROOT/'workspace/강의제작/제작도구/실습시작/package-index.json'
    manifest = json.loads(index.read_text(encoding='utf-8')) if index.exists() else {'labs': []}
    updates = {item['id']: item for item in catalog}
    manifest['labs'] = [updates.pop(item['id'], item) for item in manifest['labs']]
    manifest['labs'].extend(updates.values())
    dump(index, manifest)
    print('두 과정 설계·구현 시작본 4개, ZIP 4개 생성')

if __name__=='__main__':main()
