"""온라인 2회차 실습3 · 4(두 과정) 학생 폴더 · ZIP · 패키지 목록과 강사 참조 모델(reference/)을 만든다.

2회차 실습3 · 4 원자료는 data_session2.py가 만든다(가상 사례, 고정 시드). 네 랩은 단계 랩 틀(design_lab · graph_lab → build_lab)로 만들고,
단계 하나가 START.md 「진행 단계」 한 줄과 guide.html 한 절이 된다.
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

import data_session2 as D
from lab_package import GUIDE_CSS as CSS, entry, pack, register   # pack은 build_common · build_conditions · build_session3_*도 여기서 가져간다

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT/'workspace/강의제작/산출물'
TOOLS = Path(__file__).resolve().parent
TEACHER = TOOLS/'reference'
COURSES = [('통합반','integrated'),('실전반','practical')]
LAB3 = '02일차_실습3_온톨로지설계'
LAB4 = '02일차_실습4_그래프구현과검증'
VERSION = '2026-11-03-lab-v9'

def write(path, text):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(text,encoding='utf-8',newline='\n')

def dump(path, value):
    write(path,json.dumps(value,ensure_ascii=False,indent=2)+'\n')

def rows(name, folder=None):
    path=(folder or D.SOURCE)/name
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

# ───────────── 강사 참조 해석(원자료의 표기를 자료끼리 대조한 근거 — 같은 모델 · 계통 · 교체부품 · 태그 — 로 푼다) ─────────────
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

# 강사 참조 갈래. 통합반 B = 같은 제조사 품번의 다른 사내 품번을 SAME_ITEM_AS로 잇는다.
# 실전반 A = 조건부 승인을 승인으로 봄 + PR-07 7.4는 SCM 등록대로(갈래 ㄱ, 빈 조건 = 조건 없음). B = 조건부 승인을 비승인으로(ㄱ).
# 실전반 ㄴ · ㄷ = A에 더해 7.4(불량률 기준 초과 승인 공급사)를 ㄴ 정보로 붙임 · ㄷ 미결(확인 요청)로 표시. 실전반의 설비·부품 부분은 통합반 A와 같다.
# 실습4 수정본 갈래(「시점과 상태」)는 실습3 갈래와 따로, 실습4 입력/ 모델(LAB4_INPUT_BRANCH) 위에서 돌린다:
# 남김 = 불용 설비를 상태로 남김 · 삭제 = 불용 설비를 전용 하위 대상(구성 요소 · 센서)과 함께 지움(verify_reference.py).
REFERENCE_BRANCHES = {'통합반': ['A', 'B'], '실전반': ['A', 'B', 'ㄴ', 'ㄷ']}
BRANCH_DIRS = {'A': '', 'B': '갈래B', 'ㄴ': '갈래ㄴ', 'ㄷ': '갈래ㄷ'}
LAB4_INPUT_BRANCH = {'통합반': 'A', '실전반': 'ㄴ'}     # 실습4 입력/의 앞 단계 완성 모델
LAB4_CHANGE_BRANCHES = ['남김', '삭제']
APPROVED_STATUS = {'A': ('승인', '조건부 승인'), 'B': ('승인',), 'ㄴ': ('승인', '조건부 승인'), 'ㄷ': ('승인', '조건부 승인')}
PR74_SOURCE = f'{D.PR07_FILE} 7.4'
PRACTICAL_BRANCH_README = ('# 실전반 강사 참조 갈래\n\n'
    '실습3: 루트 = 갈래 A(조건부 승인 = 승인) · PR-07 7.4 갈래 ㄱ(SCM 등록대로) / `갈래B/` = 조건부 승인 = 비승인 · ㄱ / '
    '`갈래ㄴ/` = A · 7.4를 정보로 표시(실습4 `입력/` 모델) / `갈래ㄷ/` = A · 7.4 미결(확인 요청). 기대 답은 `기대답.json`의 같은 키(A · B · ㄴ · ㄷ).\n\n'
    '실습4 수정본 갈래: `갈래ㄴ/` 모델 위에서 불용 설비를 상태로 남김 · 전용 하위 대상과 함께 삭제. 실행 결과는 `../session2_검증.json`의 `neo4j` → `실전반` → `실습4`.\n')

def student_schema(schema):
    """갈래 표시는 제작용이라 학생 입력에 두지 않는다."""
    return {k: v for k, v in schema.items() if k != 'branch'}

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
        ok=status in APPROVED_STATUS[branch]
        condition=(a['조건'] if a else '') or None
        fail=q['불량률'];lead=q['납기(일)']
        defect=float(fail.rstrip('%'))/100 if fail.endswith('%') else float(fail)
        props=dict(approved=ok,approval_status=status,condition=condition,
            price_manwon=float(q['단가(만원)']),defect_rate=defect,
            lead_days=int(lead[:-1])*7 if lead.endswith('주') else int(lead),min_order_qty=int(q['최소주문수량']),
            supplier_part_no=q['공급사품번'],quote_date=q['견적일'],valid_until=q['유효기한'])
        if branch in ('ㄴ','ㄷ') and ok and round(defect*100,6)>D.PR74_RATE_PCT:
            if branch=='ㄴ':
                props.update(inspection='입고 전수 검사',compare_extra_manwon=float(D.PR74_EXTRA_MANWON),rule_source=PR74_SOURCE)
            elif not condition:
                props.update(pending_check=f'SCM 등록에는 조건이 없고 {PR74_SOURCE}는 입고 전수 검사 · 비교 비용 +{D.PR74_EXTRA_MANWON}만 원 — 등록 확인 필요')
        rels.append({'type':'SUPPLIES','a':'supplier:'+sup,'b':pid,'props':{k:v for k,v in props.items() if v is not None}})

def schema_for(supply,branch):
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
    if not supply and branch=='B':relation_defs['SAME_ITEM_AS']={'from':'Part','to':'Part','cardinality':'N:1','properties':{'maker_part_no':'string'},'note':'같은 제조사 품번인 다른 사내 품번'}
    if supply:
        definitions['Supplier']={'meaning':'견적을 낸 공급사','required':{'id':'string','name':'string'}}
        props={'approved':'boolean','approval_status':'string','condition':'string','price_manwon':'number','defect_rate':'number','lead_days':'integer',
               'min_order_qty':'integer','supplier_part_no':'string','quote_date':'string','valid_until':'string'}
        if branch=='ㄴ':props.update(inspection='string',compare_extra_manwon='number',rule_source='string')
        if branch=='ㄷ':props.update(pending_check='string')
        relation_defs['SUPPLIES']={'from':'Supplier','to':'Part','cardinality':'N:M','note':'공급사·품번마다 유효한 최신 견적 하나','properties':props}
    constraints=['id는 전체 그래프에서 고유. 구성요소·센서는 설비코드:이름, 부품은 사내 품번','이관 기록(코드 통합)·철거 실물·점검표 중복 행은 대상을 새로 만들지 않는다',
                 'limit 생략은 0과 다르다. normal 생략은 미확인','단위는 Quantity 기준 단위로 맞추고 바꾼 경우 source_unit을 남긴다']
    if supply:constraints+=['승인 여부는 승인공급사_목록(SCM 등록)과 기준일로 정한다','만료 견적은 SUPPLIES로 쓰지 않는다']
    if supply and branch=='ㄴ':constraints.append(f'구매 기준서 PR-07 7.4에 걸리는 승인 공급사 쌍(불량률 {D.PR74_RATE_PCT} % 초과)은 입고 검사 조건 · 비교 가산 비용 · 근거 절을 함께 남긴다')
    if supply and branch=='ㄷ':constraints.append('SCM 등록에 조건이 없는데 구매 기준서 PR-07 7.4에 걸리는 승인 공급사 쌍은 pending_check로 확인 필요를 남긴다(approved는 SCM 등록대로)')
    return {'classes':definitions,'relations':relation_defs,'identity':'id는 전체 그래프에서 고유.','branch':branch,'constraints':constraints}

def reference_model(supply=False,branch='A'):
    """원자료끼리 대조한 근거로 만든 강사 참조 모델(반환 형식 유지). 갈래는 REFERENCE_BRANCHES 위 주석."""
    nodes,rels=base_graph('A' if supply else branch)
    if supply:supply_part(nodes,rels,branch)
    return schema_for(supply,branch),{'nodes':nodes,'rels':rels}

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

# RULES는 아직 단계 랩 틀로 바뀌지 않은 랩(실전 2회차 조건표 · 3회차)이 import해 줄 단위로 고쳐 쓴다. 그 랩들이 단계 틀로 바뀌면 STEP_RULES로 옮기고 지운다.
# STEP_RULES = 코딩랩.md K-47의 열 항목(⑧은 K-47 문장 그대로, ⑩은 같은 뜻을 학생 말로 — 「K-111 다섯 요소」는 다섯 이름으로 풀고, 단계가 무엇인지는 아래 줄에 적었다). 두 과정 실습3 · 4가 함께 쓰므로 과제 해결 방법은 적지 않는다.
STEP_RULES='''# 실습 작업 규칙

이 폴더에서 일하는 AI(Codex · GitHub Copilot)가 지키는 규칙입니다. 학생도 함께 읽습니다.

1. `입력/`과 `자료/`는 읽기만 함 — 고치거나 지우거나 덮어쓰지 않음.
2. 새 코드와 결과는 `결과/` 아래에만 만듦.
3. 원자료에 없는 값 · 관계 · 실행 결과를 만들지 않음.
4. 미확인 · 값 없음 · 0을 서로 다른 것으로 구별함.
5. 학생이 요청한 기능만 만듦 — 무관한 기능 · 화면 · 고르기 규칙과 START.md 「이번 범위 밖」의 일을 더하지 않음.
6. DB가 필요한 작업은 이 실습 폴더에 배정된 별도 랩 DB만 씀 — 포털 DB에 접속하거나 전체 삭제하지 않음.
7. 접속 키 · 비밀번호를 코드 · 결과 · 기록에 적지 않음.
8. 「정할 것」은 추천 · 권장 표시 없이 묻고, 학생이 선택과 근거를 말할 때까지 그 결정에 걸린 결과를 만들지 않음(「권장안대로」 「알아서 골라 줘」는 선택이 아니다, 답을 못 들은 채 끝나면 그 자리를 미결로 남긴다).
9. 첫머리에 「제공 빈 틀」 표시가 있는 파일은 보관 없이 바로 채움. 학생이 쓴 결과를 고칠 때는 먼저 사본을 남김.
10. 한 번에 가이드의 한 단계만 함. 여러 단계를 한꺼번에 맡기는 요청(「다 해 줘」 「알아서 해 줘」 「묻지 말고 만들어 줘」)에는 결과를 만들지 않고 지금 단계도 대신 하지 않음. 그때 답은 지금 단계의 번호 · 이름 한 줄과, 그 단계 요청에 빠진 것(목적 · 입력 · 지킬 것 · 결과의 꼴 · 확인 방법)마다 질문 한 줄로 씀. 질문에 예시 답이나 괄호 예시를 붙이지 않고, 학생이 보낼 요청 문장 · 요구 · 결정 · 기대 답을 대신 쓰거나 따옴표로 묶어 보여 주지 않음.

- 「정할 것」은 START.md 「학생이 정할 것」의 지점과, 작업 중 새로 찾은 같은 종류의 지점이다.
- 단계는 `guide.html`과 START.md 「진행 단계」의 같은 번호다.
- 단계를 마칠 때는 실행한 명령 · 실제 출력 · 바뀐 파일을 함께 보이고, 실행하지 않은 것은 실행하지 않았다고 쓴다. 검사를 통과시키려고 검사 기준이나 원자료를 바꾸지 않는다.
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
missing=[n for n in ('schema.json','graph.json') if not (base/n).is_file()]
if missing:
    print('아직 검사할 결과가 없습니다: '+', '.join(base.name+'/'+n for n in missing))
    print('START.md 「결과 형식」의 모양으로 만든 뒤 다시 실행하세요. 이 검사는 구조만 보고, 질문의 답은 원자료와 따로 대조합니다.')
    sys.exit(1)
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

SUPPLY_CHECK='''    NEED={'approved':'boolean','price_manwon':'number','defect_rate':'number','lead_days':'integer','quote_date':'string'}
    sspec=relations.get('SUPPLIES')
    if not isinstance(sspec,dict):errors.append('schema.json relations에 공급 조건 관계 SUPPLIES가 없습니다(START.md 「공급 조건 형식」).')
    else:
        declared=sspec.get('properties',{}) or {}
        for k,t in NEED.items():
            if declared.get(k)!=t:errors.append(f'schema.json SUPPLIES.properties.{k}는 {t!r}이어야 합니다(현재 {declared.get(k)!r}).')
    pairs={}
    for r in rels:
        if r.get('type')!='SUPPLIES':continue
        a,b=r.get('a'),r.get('b');p=r.get('props') or {};pairs.setdefault((a,b),[]).append(p)
        for k in NEED:
            if p.get(k) is None:errors.append(f'SUPPLIES {a}→{b}: {k} 없음')
        d=p.get('defect_rate')
        if isinstance(d,(int,float)) and not isinstance(d,bool) and not 0<=d<=1:errors.append(f'SUPPLIES {a}→{b}: defect_rate={d}는 0~1 범위 밖입니다.')
    for (a,b),ps in sorted(pairs.items(),key=str):
        if len(ps)>1:errors.append(f'SUPPLIES {a}→{b}가 {len(ps)}개: 공급사 · 부품 쌍마다 하나만 둡니다(START.md 「공급 조건 형식」).')
    if not pairs:errors.append('graph.json에 SUPPLIES 관계가 없습니다.')
    else:
        yes=sum(1 for ps in pairs.values() for p in ps if p.get('approved') is True);no=sum(1 for ps in pairs.values() for p in ps if p.get('approved') is False)
        print(f'참고: SUPPLIES 쌍 {len(pairs)}개(approved=true {yes}개, false {no}개). 쌍마다 고른 견적과 승인 근거는 원자료 줄과 따로 대조하세요.')
'''

CHECK_ANCHOR='except (OSError,ValueError,TypeError,AttributeError) as e:'
assert CHECKER.count(CHECK_ANCHOR)==1
CHECKER_SUPPLY=CHECKER.replace(CHECK_ANCHOR,SUPPLY_CHECK+CHECK_ANCHOR)


FORMAT='''## 결과 형식

`check.py`와 다음 실습이 읽는 모양입니다. 무엇을 종류·속성·관계로 둘지는 직접 정합니다.

- `결과/schema.json`: `{"classes": {종류: {"meaning": 뜻, "required": {속성: 자료형}, "optional": {속성: 자료형}}}, "relations": {관계: {"from": 종류 또는 [종류…], "to": 종류, "cardinality": "1:N" 등, "properties": {속성: 자료형}}}}`
- 자료형은 `string`·`number`·`integer`·`boolean`·`list` 중 하나이거나, 허용 값 목록(예: `["upper", "lower"]`)입니다.
- `결과/graph.json`: `{"nodes": [{"labels": [종류], "props": {"id": 고유 ID, …}}], "rels": [{"type": 관계, "a": 시작 id, "b": 끝 id, "props": {…}}]}`
- 같은 두 대상 사이에 같은 관계를 여러 개 두려면 그 관계의 props에 `id`를 붙입니다.
'''

SUPPLY_FORMAT = '''### 공급 조건 형식(다음 실습의 조회가 읽는 모양)

- 공급사에서 부품으로 가는 관계 `SUPPLIES` 하나가 그 공급사 · 부품 쌍의 기준일 견적 조건 하나와 그 공급사의 승인 여부입니다. 같은 쌍에 `SUPPLIES`를 둘 이상 두지 않습니다. 기준일에 쓸 조건이 없는 쌍은 이 관계를 두지 않고, 그 사정을 `결과/자료_검토.md`에 남깁니다.
- `SUPPLIES`에 반드시 둘 속성: `approved`(boolean, 승인 공급사인지), `price_manwon`(number, 만원), `defect_rate`(number, 0~1 비율), `lead_days`(integer, 일), `quote_date`(string, 견적일). 그 밖의 속성(출처 · 조건 · 원래 표기 등)은 직접 정합니다.
- 견적 · 승인 이력을 함께 남기려면 다른 종류나 관계로 둡니다(선택).
'''

GRAPH_FORMAT = '''## 결과 형식

`결과/`에 아래 파일을 둡니다. 파일 안에서 무엇을 어떤 문장으로 쓸지는 직접 정합니다.

- `결과/load.cypher`(또는 적재 코드): 모델 파일의 대상과 관계를 랩 DB에 넣습니다. 같은 파일을 다시 실행해도 됩니다.
- `결과/update.cypher`(또는 수정 코드): 수정본의 줄을 이미 넣은 그래프에 반영합니다.
- `결과/query.cypher`: 질문마다 조회문 하나. 조회문 위에 어느 질문의 조회인지 주석(`// 질문 1`)으로 적습니다.
- `결과/검증_기록.md`: 「제공 빈 틀」의 칸대로 채웁니다.
'''

# 두 과정은 각각 첫 설계 랩에서 도구를 배운다. 아래 문장은 가이드의 해당 단계에 쓴다.
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
LAB_CONNECT = ('「랩 DB 준비 완료」가 나오면 열린 Browser의 Protocol에서 bolt://를 선택하고 Connection URL에는 출력 주소의 127.0.0.1:포트 부분만 넣습니다. '
               'Database user는 neo4j, Password는 비워 두고 Connect를 누릅니다. 연결 정보는 `랩_연결.json`에도 저장됩니다. '
               'AI가 명령 실행 승인을 요청하면 이 폴더의 적재 · 조회 명령이고 주소가 `랩_연결.json`의 주소와 같은지 먼저 확인하세요.')
COUNT_QUERY = 'MATCH (n) RETURN labels(n)[0] AS 종류, count(*) AS 개수 ORDER BY 종류'
SAVE_KEY = '파일을 고친 뒤에는 Ctrl+S로 저장합니다. 탭 이름 옆 점(●)이 사라지면 저장된 것입니다.'
COMPLETED_NOTE = 'AI 계정이 없으면 실습 폴더와 따로 받는 학생용 완성본 묶음(계정이 없는 학생이 결과를 확인하는 용도)으로 결과를 확인하세요.'

TOOLS_DESIGN = [
    '**VS Code**: 왼쪽 탐색기에서 이 폴더의 파일을 엽니다. 처음 열 때 「이 폴더의 작성자를 신뢰합니까」가 나오면 신뢰를 누릅니다. CSV를 누르면 표 글자 그대로 보이고, 고친 파일은 `Ctrl+S`로 저장합니다.',
    '**터미널**: 메뉴 「터미널 → 새 터미널」로 아래쪽에 엽니다. 이 폴더에서 열리는지 맨 앞 경로를 확인하고 `python check.py`처럼 명령을 입력합니다.',
    '**Codex(AI)**: 왼쪽 막대의 Codex 아이콘을 눌러 채팅 창을 엽니다. 입력하기 전에 채팅 창 위쪽 탭이 Codex인지 확인합니다(옆의 Chat 탭은 GitHub Copilot이라 로그인 창이 뜹니다). 요청을 입력하면 이 폴더의 파일을 읽고, 허락하면 파일을 만들거나 명령을 실행합니다. AI가 「완료」라고 해도 실제 파일과 실행 출력으로 확인합니다.',
    '**편집 승인 창**: AI가 파일을 고치려 하면 「Allow ChatGPT to edit the following file?」 창이 뜹니다. 창에 적힌 파일 경로가 `결과/` 아래인지 보고 「Allow once」(이번 한 번 허용)를 누릅니다. `입력/`·`자료/`의 파일이거나 요청하지 않은 파일이면 「Deny」(거부)를 누르고 이유를 채팅으로 알립니다.',
    '**질문 카드**: AI가 정하기 전에 물어야 할 지점에서는 채팅에 질문 카드(선택지와 직접 입력 칸)가 뜰 수 있습니다. 선택지에 「(권장)」이 붙어 있어도 AI의 추천일 뿐입니다. 원자료의 근거 줄을 열어 확인한 뒤 고르거나, 직접 입력 칸에 내 결정과 근거를 적고 보냅니다.',
]
TOOLS_GRAPH = {
    '통합반': [
        '**랩 DB**: 이 폴더 전용으로 켜는 그래프 DB(이 실습에서는 Neo4j)입니다. 포털 DB와 분리돼 있어 지우거나 다시 적재해도 포털에 영향이 없습니다. `python lab_db.py`가 Docker로 켜고 Neo4j Browser를 엽니다.',
        '**Neo4j Browser**: 위쪽 입력 칸에 Cypher를 붙여 넣고 실행(▶)합니다. 결과는 그래프 또는 표(Table)로 볼 수 있고, 표가 원자료와 대조하기 쉽습니다.',
        '수백 개의 대상을 손으로 적재문에 옮기지 않습니다. AI에게 모델 파일을 읽어 적재문이나 적재 코드를 만들게 하고, 실행 결과의 개수로 확인합니다.',
        '**명령 실행 승인 창**: AI가 Docker나 랩 DB 주소에 접속하는 명령을 실행하려 하면 이 폴더 밖 실행을 허락할지 묻는 창이 뜹니다. 명령이 `python lab_db.py` · 이 폴더의 적재 · 조회 명령이고 주소가 `127.0.0.1`의 랩 DB인지 보고 「Allow once」, 아니면 「Deny」를 누릅니다.',
    ],
    '실전반': [
        '**랩 DB**: `python lab_db.py`가 이 폴더 전용 그래프 DB(이 실습에서는 Neo4j)를 Docker로 켜고 Browser를 엽니다. 포털 DB와 분리돼 있습니다. Browser 입력 칸에 Cypher를 넣어 실행하고 표(Table)로 원자료와 대조합니다. 수백 개 대상은 AI가 모델 파일에서 적재문을 만들게 합니다.',
        '**명령 실행 승인 창**: AI가 Docker · 랩 DB 명령을 실행하려 하면 폴더 밖 실행 승인 창이 뜹니다. 명령이 `python lab_db.py` · 이 폴더의 적재 · 조회이고 주소가 `127.0.0.1` 랩 DB일 때만 「Allow once」를 누릅니다.',
    ]}


PICTURE_TYPES = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg', '.avif', '.tif', '.tiff'}


def student_photos(folder, provenance, headings):
    """이 랩의 학생 화면만 출처·판본과 맞춘다. 사진의 절(section)은 가이드의 단계 이름(headings) 가운데 하나다. 불일치 파일은 손대지 않는다."""
    prefix = '산출물/' + folder.relative_to(OUT).as_posix() + '/images/'
    photos = {}
    for record in provenance:
        target = record['target'].removeprefix('workspace/강의제작/')
        if not target.startswith(prefix) or record.get('kind') != '학생 실습 화면':
            continue
        name = 'images/' + target[len(prefix):]
        if (name in photos or record.get('section') not in headings or not record.get('caption')
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


# ───────────── 단계 랩 — 단계 하나가 START.md 「진행 단계」 한 줄과 guide.html 한 절이 된다 ─────────────
# 코딩랩.md K-46 · K-47 · K-52 · K-111 · K-149. 단계 · 힌트에는 값과 판단 지점의 답을 쓰지 않는다(K-28).

def H(목적, 입력, 지킬것, 꼴, 확인):
    return {'목적': 목적, '입력': 입력, '지킬 것': 지킬것, '결과의 꼴': 꼴, '확인 방법': 확인}

def S(name, stage, do, ask, evidence, hint=None, cmd=''):
    return dict(name=name, stage=stage, do=do, ask=ask, hint=hint, cmd=cmd, evidence=evidence)

STAGE_LINE = '과정은 온톨로지 → 에이전트 → 프로세스 순서로 올라갑니다. 이 실습은 첫 단계인 온톨로지의 {what}를 맡습니다.'
STEP_INTRO = '한 번에 한 단계씩 갑니다. 단계마다 결과를 확인한 뒤 다음 단계로 갑니다. 단계마다 정하거나 물을 것, 요청에 담을 것, 판단할 증거는 `guide.html`의 같은 번호에 있습니다.'
SEVEN = '이 순서는 바이브 코딩 일곱 단계 — 파일을 바꾸지 않고 파악 → 요구와 기대 답을 내 말로 → 계획 검토 → 작게 구현 → 원자료와 대조 → 고침 → 저장하고 다시 열기 — 를 따릅니다.'
BACKTICK = '요청에 파일 이름을 쓸 때는 `결과/schema.json`처럼 백틱(`)으로 감쌉니다. 채팅 입력이 밑줄(_)을 서식으로 바꾸기 때문입니다.'
DECIDE_INTRO = ('원자료만으로는 하나로 정해지지 않아, 근거를 찾아 내가 정해야 결과를 업무에 쓸 수 있는 지점이 있습니다. 이번 자료에는 아래 종류의 지점이 있습니다. '
                '어느 행 · 어느 절이 해당하는지는 탐색에서 직접 찾고, 지점마다 고른 것 · 근거(파일 · 줄) · 그 선택으로 바뀌는 답을 `{rec}` 「정한 것」 표에 적습니다.')
DECIDE_AI = 'AI에게 이 지점을 대신 정하게 하지 않습니다. AI가 고를 것을 내놓거나 「권장」을 붙여도 그대로 따르지 말고, 원문 줄을 열어 내 선택과 근거를 말합니다. 못 정한 지점은 미결로 남깁니다.'
ASK_DECIDE = '지점마다 내 선택과 근거를 말합니다. AI가 고를 것을 내놓거나 「권장」을 붙이면 따르지 말고 원문 줄을 다시 열어 내 말로 정합니다. 못 정한 지점은 미결로 적습니다.'
EVIDENCE_LOOK = 'AI가 짚은 줄을 열었을 때 그 내용이 실제로 있습니다. 편집 승인 창이 뜨지 않았고 AI의 답에 바꾼 파일이 없습니다.'
FIX_LOOP = '다르면 입력 · 기대 · 실제를 함께 전해 고친 뒤 같은 확인을 다시 합니다.'
USB = '재부팅 전에 이 실습 폴더를 USB 또는 개인 클라우드에 복사합니다. 자동으로 되살려 주지 않습니다.'

def tree(name, rows):
    width = max(len(k) for k, _ in rows) + 2
    lines = [f'{name}/'] + [('└ ' if i == len(rows) - 1 else '├ ') + k.ljust(width) + v for i, (k, v) in enumerate(rows)]
    return '\n'.join(lines)

def req_template(record_title, extra_sections=''):
    return (f'# {record_title}\n\n> 제공 빈 틀입니다. 보관하지 말고 바로 채웁니다.\n\n## 목표와 질문\n\n## 이 답을 쓰는 사람과 쓰는 곳\n\n## 사용할 자료와 기준일\n\n## 지킬 조건\n\n'
            '## 정한 것\n\n| 지점(종류) | 고른 것 | 근거(파일 · 줄) | 이 선택으로 바뀌는 답 |\n|---|---|---|---|\n| | | | |\n\n'
            '## 기대 답과 실제 결과\n\n| 질문 · 물은 대상 | 원자료에서 먼저 찾은 기대 답(파일 · 줄) | 실제 결과 | 고친 점 · 다시 확인 |\n|---|---|---|---|\n| | | | |\n\n'
            + extra_sections +
            '## 저장 기록\n\n- 기준일:\n- 저장 시점:\n- 확인하지 못한 점:\n')

REVIEW_TEMPLATE = '# 원자료 대조\n\n> 제공 빈 틀입니다. 보관하지 말고 바로 채웁니다.\n\n| 자료 · 행 | 확인한 문제 또는 근거 | 선택한 처리 | 결과 확인 |\n|---|---|---|---|\n'
GRAPH_COUNTS = ('## 적재 · 다시 적재 · 수정본\n\n| 단계 | 노드 수 | 관계 수 | 확인한 것 |\n|---|---|---|---|\n'
                '| 첫 적재 | | | |\n| 같은 적재 다시 | | | |\n| 수정본 반영 | | | |\n| 같은 수정본 다시 | | | |\n\n')


def step_start(L):
    rec = L['rec']
    b = [f'# {L["title"]}', '## 목표', *L['goal'], L['make'], '## 출발점', '\n'.join('- ' + x for x in L['start'])]
    if L.get('tools'):
        b += ['## 처음 쓰는 도구', '\n'.join('- ' + x for x in L['tools'])]
    b += ['## 해결할 질문', L['user'], '\n'.join(f'{i}. {q}' for i, q in enumerate(L['questions'], 1)),
          '## 학생이 정할 것', DECIDE_INTRO.format(rec=rec), '\n'.join(f'- **{k}** — {v}' for k, v in L['decide']), DECIDE_AI,
          '## 이번 범위 밖', '\n'.join('- ' + x for x in L['outside']) + '\n\n자료에 있어도 이번 결과에 만들지 않습니다.',
          *[f.strip() for f in L['formats']],
          '## 진행 단계', STEP_INTRO, '\n'.join(f'{i}. **{s["name"]}** — {s["do"]}' for i, s in enumerate(L['steps'], 1)), SEVEN, BACKTICK,
          '## 확인', '확인할 사례의 종류(어느 행이 해당하는지는 원자료에서 직접 찾습니다):', '\n'.join('- ' + x for x in L['cases']),
          '실행 명령:', '```\n' + L['commands'] + '\n```',
          f'바뀐 파일 확인: AI가 단계를 마칠 때마다 바뀐 파일 목록을 봅니다. {L["readonly"]} 바뀌지 않았는지, 요청하지 않은 파일이 생기지 않았는지 확인합니다. 편집 승인 창에서는 경로가 `결과/` 아래일 때만 허용합니다.',
          '## 완료 판정', L['done'], '## 저장과 다음 실습', L['save']]
    return '\n\n'.join(b) + '\n'


def inline(text):
    """START와 같은 문장을 가이드에 쓴다: 백틱은 <code>, **굵게**는 <b>."""
    t = html.escape(text)
    t = re.sub(r'`([^`]+)`', r'<code>\1</code>', t)
    return re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', t)


def step_html(s, extra='', last=False):
    parts = [f'<p><b>할 일</b> {inline(s["do"])}</p>', extra, f'<p><b>정하거나 물을 것</b> {inline(s["ask"])}</p>']
    if s['hint']:
        rows_ = ''.join(f'<tr><th>{html.escape(k)}</th><td>{inline(v)}</td></tr>' for k, v in s['hint'].items())
        parts.append(f'<p><b>요청에 담을 것</b> 아래 다섯 가지를 내 말로 채워 요청을 짭니다. 값은 원자료에서 내가 찾습니다.</p><table>{rows_}</table>')
    if s['cmd']:
        parts.append(f'<p><b>명령</b></p><pre>{html.escape(s["cmd"])}</pre>')
    else:
        parts.append('<p><b>명령</b> 없음 — 이 단계는 탐색기 · 편집기 · AI 채팅에서 합니다.</p>')
    parts.append(f'<p class="check"><b>판단할 증거</b> {inline(s["evidence"])}{"" if last else " 확인한 뒤 다음 단계로 갑니다."}</p>')
    return ''.join(parts)


def step_guide(L, photos):
    rec = L['rec']
    first = (''.join(f'<p>{inline(x)}</p>' for x in L['goal']) + f'<p>{inline(L["user"])}</p>'
             + '<p><b>받은 폴더</b> VS Code 왼쪽 탐색기에 이렇게 보입니다.</p>' + f'<pre>{html.escape(L["tree"])}</pre>'
             + f'<p>{OPEN_DESIGN}</p><p>{COMPLETED_NOTE}</p>')
    first += '<p><b>해결할 질문</b></p><ol>' + ''.join(f'<li>{inline(q)}</li>' for q in L['questions']) + '</ol>'
    decide = ('<p><b>학생이 정할 것 — 지점의 종류</b> ' + inline(DECIDE_INTRO.format(rec=rec)) + '</p><ul>'
              + ''.join(f'<li><b>{html.escape(k)}</b> — {inline(v)}</li>' for k, v in L['decide']) + f'</ul><p>{inline(DECIDE_AI)}</p>')
    extras = dict(L.get('guide_extra', {}))
    extras[L['decide_step']] = extras.get(L['decide_step'], '') + f'<p>{inline(SAVE_KEY)}</p>' + decide
    sections = []
    for i, s in enumerate(L['steps']):
        last = i == len(L['steps']) - 1
        body = (first if i == 0 else '') + step_html(s, extras.get(i, ''), last)
        if last:
            body += (f'<p><b>저장 위치</b> 이 실습 폴더의 <code>결과/</code></p><p><b>다시 열어 볼 것</b> {inline(L["reopen"])}</p>'
                     f'<p><b>다음 실습에 넘길 판본</b> {inline(L["save"])}</p>')
        for picture, record in photos.items():
            if record['section'] == s['name']:
                caption = html.escape(record['caption'])
                body += f'<figure><img src="{html.escape(picture, quote=True)}" alt="{caption}"><figcaption>{caption}</figcaption></figure>'
        sections.append((s['name'], body))
    return page(L['title'], inline(L['goal'][0]), sections)


def build_lab(folder, L, photos):
    """START · 작업 규칙 · 가이드 · 준비 안내 · L['files']를 쓴다. 결과/의 학생 파일은 L['files']에 든 빈 틀만 덮어쓴다."""
    for path in [folder/'AGENTS.md', folder/'.github/copilot-instructions.md', folder/'CLAUDE.md']:
        write(path, STEP_RULES)
    for name, text in L['files'].items():
        write(folder/name, text)
    write(folder/'START.md', step_start(L))
    write(folder/'준비_안내.md', '# 실습 준비\n\nVS Code에서 이 파일이 들어 있는 폴더를 연 뒤 [START.md](START.md)의 목표와 질문을 확인하세요. 단계별 안내는 [guide.html](guide.html)에 있습니다.\n')
    guide = step_guide(L, photos)
    write(folder/'guide.html', guide)
    write(folder/'안내.html', guide)


# ───────────── 실습3(설계) — 두 과정 ─────────────
NEXT_LAB = {'통합반': '설계한 온톨로지를 그래프 DB에 구현하고 검증하기', '실전반': '부품의 사용 설비와 공급 정보를 조회하는 그래프 구현하기'}
AFTER_LAB = {'통합반': '작업 절차와 판단 조건을 연결해 조치 기준 만들기', '실전반': '작업 기준의 복합 조건과 예외를 조치 조건표로 표현하기'}
DESIGN_TREE_TAIL = [('AGENTS.md', 'Codex 작업 규칙'), ('check.py', '구조 검사'), ('CLAUDE.md', '작업 규칙(같은 내용)'),
                    ('guide.html', '이 가이드'), ('START.md', '이번 과제와 진행 단계'), ('안내.html', '이 가이드와 같은 파일'), ('준비_안내.md', '폴더를 연 뒤 볼 곳')]
GRAPH_TREE_TAIL = [('AGENTS.md', 'Codex 작업 규칙'), ('CLAUDE.md', '작업 규칙(같은 내용)'), ('guide.html', '이 가이드'), ('lab_db.py', '이 폴더 전용 랩 DB 켜기'),
                   ('START.md', '이번 과제와 진행 단계'), ('안내.html', '이 가이드와 같은 파일'), ('준비_안내.md', '폴더를 연 뒤 볼 곳')]
SOURCES = f'원자료. CSV 8개(설비 대장 · 구성 요소 · 센서 · 예비품 · 품번 교차표 · 공급 조건 · 승인 공급사 · 입고 이력), 현장 메모{{}}. 기준일은 {D.REF_DATE}입니다.'   # 실전반만 구매 기준서 발췌
RULES_LINE = '`AGENTS.md` · `.github/copilot-instructions.md` · `CLAUDE.md` — Codex와 GitHub Copilot이 지키는 작업 규칙(세 파일이 같은 내용). 학생도 함께 읽습니다.'


def design_lab(course):
    if course == '실전반':
        return design_practical()
    title = '현장 정보를 체계화하는 온톨로지 직접 설계하기'
    save = (f'`결과/schema.json` · `결과/graph.json`을 한 쌍으로, 만든 코드 · 확인 코드 · `요구사항.md` · `자료_검토.md`와 함께 보관합니다. '
            f'다음 실습 「{NEXT_LAB[course]}」에서는 이 판본을 쓰거나 제공된 설비 · 센서 · 부품 모델로 시작할 수 있습니다. ' + USB)
    steps = [
        S('폴더와 출발점 확인', '시작',
          'VS Code 탐색기에서 이 폴더의 `입력/` · `자료/` · `결과/` · START.md를 열어 각 자리의 역할과 이번 질문을 확인합니다.',
          '이번 질문 세 개와, 이 답을 쓰는 사람이 누구인지 확인합니다.',
          '탐색기에서 네 자리를 찾았고, `결과/`에 아직 `schema.json` · `graph.json`이 없다는 것을 확인했습니다. 관계 그림에 있는 종류 몇 개와 그 사이 관계를 말할 수 있습니다.'),
        S('파일을 바꾸지 않고 자료 파악', '① 파악',
          'AI에게 파일을 바꾸지 말고, 내가 고른 설비 하나의 구성 요소 · 센서 · 교체 부품에 관한 줄을 자료마다 찾아 파일 · 줄로 짚어 달라고 합니다. 짚은 줄을 직접 엽니다.',
          '같은 장치나 센서를 자료마다 다르게 적은 곳, 칸이 비었거나 표기가 다른 곳처럼 자료끼리 말이 달라 보이는 곳이 있는지 묻습니다.',
          EVIDENCE_LOOK + ' 질문 1 ~ 3에 쓸 자료가 무엇인지 내 말로 말할 수 있습니다.',
          H('고른 설비에 관한 근거 줄을 자료마다 모은다. 아직 아무것도 만들지 않는다.',
            '`자료/` 전체, `입력/관계그림.json`, START.md 「해결할 질문」',
            '파일을 바꾸지 않는다. 해석보다 파일 · 줄 번호를 먼저 받는다.',
            '「파일 · 줄 · 그 줄이 말하는 것」 목록과, 자료끼리 말이 달라 보이는 곳 목록',
            '짚은 줄 가운데 몇 개를 내가 직접 열어 같은 내용인지 본다')),
        S('요구와 기대 답 정하기', '② 요구',
          '질문 · 이 답을 쓰는 사람 · 기준일 · 지킬 조건과, 고른 설비의 구성 요소별 센서와 여러 설비가 함께 쓰는 부품 하나의 사용 설비를 원자료에서 직접 찾아 기대 답으로 `결과/요구사항.md`에 내 말로 적습니다. 「학생이 정할 것」의 지점마다 고른 것과 근거 줄을 적습니다.',
          ASK_DECIDE,
          '기대 답마다 파일 · 줄이 붙어 있습니다. 「정한 것」 표의 지점마다 고른 것 · 근거 · 바뀌는 답이 채워져 있거나 미결로 적혀 있습니다. AI의 되짚기가 내 요구와 같습니다.',
          H('내가 정한 요구를 AI가 같은 뜻으로 이해하게 한다',
            '2단계에서 연 근거 줄, `결과/요구사항.md`(제공 빈 틀)',
            '기대 답은 내가 원자료에서 찾은 값으로 적는다(AI의 답을 옮기지 않는다). 「학생이 정할 것」은 내가 고른다.',
            '`요구사항.md`의 칸 — 목표와 질문, 이 답을 쓰는 사람, 자료와 기준일, 지킬 조건, 「정한 것」 표, 「기대 답과 실제 결과」 표',
            'AI에게 `요구사항.md`를 자기 말로 되짚게 하고, 내 뜻과 다른 곳을 고친다')),
        S('설계 계획 검토', '③ 계획',
          '설비 · 구성 요소 · 센서 · 물리량 · 부품을 어떤 종류 · 속성 · 관계로 둘지, ID를 무엇으로 지을지 AI의 계획을 받아 검토하고, 5 ~ 9단계의 구현 순서에 동의합니다. 아직 파일을 만들지 않습니다.',
          '같은 태그 이름이 여러 설비에 있을 때 ID가 겹치지 않게 짓는 법, 관계의 방향과 연결 수, 단위를 맞출 기준을 정합니다. 「정한 것」 표의 결정을 어느 종류 · 관계에 반영할지 정합니다.',
          '질문마다 계획의 어느 관계 · 속성으로 답하는지 짚을 수 있습니다. 같은 이름의 태그가 다른 설비에 있어도 ID가 겹치지 않습니다. 계획에 내가 동의했습니다.',
          H('만들기 전에 모델의 모양과 ID 짓는 법을 합의한다',
            'START.md 「결과 형식」, `입력/관계그림.json`, `결과/요구사항.md`',
            '「정한 것」 표를 반영한다. 「이번 범위 밖」은 넣지 않는다.',
            '종류 · 속성(자료형 · 필수 여부) · 관계(방향 · 연결 수)의 표, ID 짓는 법, 구현 순서',
            '질문 1 ~ 3을 하나씩 계획에 대어 보아 어느 관계 · 속성으로 답하는지 짚게 한다')),
        S('구현 ① 설비와 구성 요소 만들기', '④ ~ ⑥ 구현 · 대조 · 고침',
          '설비 대장과 구성 요소 목록에서 설비 · 구성 요소 대상과 그 사이 관계를 만드는 코드를 `결과/`에 만들고 실행합니다.',
          '대장에 남은 옛 기록, 같은 장치를 다른 이름으로 적은 행을 어떻게 처리했는지와 그렇게 본 근거 줄을 묻습니다.',
          '설비마다 구성 요소 수와 원자료 행 수의 차이를 원자료의 행으로 설명할 수 있습니다. 바뀐 파일이 `결과/` 아래뿐입니다.',
          H('설비와 그 안의 구성 요소를 대상으로 만들고 잇는다',
            '`자료/설비_대장.csv` · `자료/구성요소_목록.csv` · `자료/현장_메모.md`, 4단계 계획',
            '같은 장치로 볼 근거가 있는 이름만 하나로 묶는다. 코드는 `결과/`에 두고 `자료/`는 읽기만 한다.',
            '설비 · 구성 요소 대상과 그 관계(`결과/schema.json` · `결과/graph.json`의 일부)',
            '설비마다 구성 요소 수를 원자료 행 수와 나란히 세어 달라고 하고, 다른 곳은 어느 행인지 보여 달라고 한다'),
          'python 결과/<만든 코드 이름>.py'),
        S('구현 ② 센서와 물리량 잇기', '④ ~ ⑥ 구현 · 대조 · 고침',
          '센서 목록의 줄마다 센서 대상을 만들어 붙은 곳(구성 요소 또는 설비)과 재는 물리량에 잇는 기능을 더하고 실행합니다.',
          '같은 태그 이름이 다른 설비에 있을 때, 같은 설비 · 태그가 여러 줄일 때, 붙은 곳 이름이 대장 이름과 다를 때 각각 어떻게 처리됐는지 묻습니다.',
          '고른 설비의 구성 요소별 센서가 내가 먼저 적은 기대 답과 같습니다. 센서 수와 원자료 행 수의 차이를 원자료의 행으로 설명할 수 있습니다. ' + FIX_LOOP,
          H('센서를 붙은 곳과 재는 물리량에 잇는다',
            '`자료/센서_목록.csv` · `자료/현장_메모.md`, 5단계의 설비 · 구성 요소',
            '계산값 · 설정값을 실측 센서와 구별한다. 붙은 곳을 찾지 못한 줄은 억지로 잇지 않고 목록으로 남긴다.',
            '센서 대상(태그 · 종류 구별)과 붙은 곳 · 물리량 관계, 잇지 못한 줄 목록',
            '고른 설비의 구성 요소마다 붙은 센서를 원자료 행과 하나씩 대조하고, 태그 이름이 다른데 같은 물리량을 재는 센서를 모아 보여 달라고 한다'),
          'python 결과/<만든 코드 이름>.py'),
        S('구현 ③ 단위와 한계 맞추기', '④ ~ ⑥ 구현 · 대조 · 고침',
          '센서마다 단위 · 정상값 · 한계 · 한계 방향을 물리량의 기준 단위로 맞춰 넣고, 바꾼 값은 원래 표기를 남기는 기능을 더하고 실행합니다.',
          '단위가 비었거나 다르게 적힌 줄, 한계가 빈 줄을 값 없음 · 미확인 · 0 가운데 무엇으로 둘지 정합니다.',
          '표기가 달랐던 줄마다 바꾼 값과 원래 표기가 맞습니다. 비어 있던 값이 내가 정한 뜻(값 없음 · 미확인)으로 남아 있습니다.',
          H('값을 정해진 단위로 맞추고, 비어 있는 값의 뜻을 구별해 남긴다',
            '`자료/센서_목록.csv`, 6단계 결과',
            '원래 표기를 지우지 않는다. 단위를 알 수 없는 값은 짐작하지 않고 미확인으로 둔다. 빈 칸을 0으로 채우지 않는다.',
            '단위 · 정상값 · 한계 · 한계 방향과 바꾼 값의 원래 표기',
            '표기가 다른 줄과 빈 칸이 있는 줄을 모두 찾아 원래 표기와 바꾼 값을 나란히 보여 달라고 하고, 그 줄을 원자료에서 연다'),
          'python 결과/<만든 코드 이름>.py'),
        S('구현 ④ 교체 부품 잇기', '④ ~ ⑥ 구현 · 대조 · 고침',
          '구성 요소마다 교체 부품을 사내 품번 하나에 잇고, 예전 품번 · 다른 표기를 부품에 남기는 기능을 더하고 실행합니다.',
          '이 단계의 결과는 내 결정에 따라 달라집니다. 같은 규격의 다른 사내 품번에 「정한 것」 표의 결정이 그대로 적용됐는지, 칸이 비었거나 품명만 적힌 행을 어느 근거 줄로 이었는지 묻습니다. AI가 결정을 대신 정하려 하면 돌려보내고 내 선택과 근거를 다시 말합니다.',
          '공용 부품이 모델에 하나로 있고 사용 설비가 기대 답과 같습니다. 잇지 못한 행마다 이유를 원자료에서 말할 수 있습니다. 결정을 바꾸면 무엇이 바뀌는지 말할 수 있습니다.',
          H('구성 요소와 사내 품번을 잇고, 다른 표기로도 품번을 찾을 수 있게 한다',
            '`자료/구성요소_목록.csv` · `자료/예비품_목록.csv` · `자료/품번_교차표.csv`, 「정한 것」 표',
            '「정한 것」 표의 결정대로 한다. 근거 없이 품번을 짐작해 잇지 않고, 잇지 못한 행은 목록으로 남긴다. 같은 부품을 설비마다 따로 만들지 않는다.',
            '구성 요소 → 부품 관계, 부품의 다른 표기, 잇지 못한 행 목록',
            '공용 부품 하나의 사용 설비를 기대 답과 나란히 놓고, 같은 결정이 다른 부품 몇 개에도 같은 방식으로 적용됐는지 본다'),
          'python 결과/<만든 코드 이름>.py'),
        S('구현 ⑤ 질문으로 물어보기', '④ ⑤ 구현 · 대조',
          '설비 코드나 품번 · 표기 하나를 받아 `결과/graph.json`에서 구성 요소별 센서, 또는 그 부품을 쓰는 설비 · 구성 요소를 보여 주는 확인 코드를 만들고 실행합니다.',
          '원자료에 없는 품번, 제조사 규격 번호로 물었을 때 무엇을 보여 줄지(값 없음과 미확인, 후보가 여럿일 때) 정합니다.',
          '고른 설비의 센서와 공용 부품의 사용 설비가 기대 답과 같습니다. 물음마다 결과가 서로 구별되고, 규격 번호로 물은 결과가 「정한 것」 표의 결정과 맞습니다. 다시 실행해도 같습니다. ' + FIX_LOOP,
          H('모델만으로 질문 1 ~ 3의 답이 나오는지 직접 물어본다',
            '`결과/graph.json`, `요구사항.md`의 「기대 답과 실제 결과」 표',
            '모델(결과 파일)만 읽는다 — 원자료를 다시 읽어 답을 만들지 않는다. 없는 품번에 값을 지어내지 않는다.',
            '설비 코드나 품번 · 표기 하나를 받아 결과를 보여 주는 확인 코드와 그 출력',
            '고른 설비, 공용 부품, 다른 표기, 제조사 규격 번호, 원자료에 없는 품번으로 실행하고, 두 번 실행해 같은지 본다'),
          'python 결과/<확인 코드 이름>.py <설비 코드 또는 품번>'),
        S('구조 검사와 고치기', '⑤ ⑥ 대조 · 고침',
          '터미널에서 구조 검사를 실행하고, 나온 문제를 고친 뒤 9단계 확인을 다시 합니다.',
          '검사가 짚은 문제가 결과 파일의 어느 대상 · 관계인지 묻습니다.',
          '「구조 검사 통과」 줄이 나옵니다. 「참고」 줄이 보여 주는 관계 개수(설비에 바로 붙은 센서가 있으면 그 개수도)를 원자료의 붙은 곳과 견주어 설명할 수 있습니다. 고친 뒤에도 9단계 결과가 같습니다. 검사 통과는 구조만 본 것이고, 질문의 답은 내가 대조한 기록으로 판단합니다.',
          H('구조 문제를 찾아 고친다', '`python check.py`의 출력', '검사 기준과 원자료를 바꾸지 않는다', '고친 파일 목록과 다시 실행한 출력', '고친 뒤 9단계의 물음을 다시 실행한다'),
          'python check.py'),
        S('저장하고 다시 열기', '⑦ 저장 · 다시 열기',
          '결과 파일을 모두 저장하고 VS Code에서 폴더를 닫았다 다시 연 뒤 9단계 명령을 다시 실행합니다. `요구사항.md` 끝에 기준일 · 저장 시점 · 확인하지 못한 점을 적습니다.',
          '확인하지 못한 점으로 무엇을 남길지 정합니다.',
          '다시 연 뒤에도 9단계 출력이 같습니다. `결과/`에 모델 두 파일 · 코드 · 기록 두 파일이 있습니다.',
          cmd='python 결과/<확인 코드 이름>.py <설비 코드 또는 품번>'),
    ]
    return dict(
        title=title, rec='결과/요구사항.md', readonly='`입력/` · `자료/`가', decide_step=2,
        goal=['포털 지식 지도에서 오일 쿨러와 거기 붙은 센서가 어떻게 이어지는지 따라가 봤습니다. 이번에는 그 연결을 직접 만듭니다. '
              '창원1공장 유압 설비 7대의 대장 · 구성 요소 · SCADA 태그 · 예비품 자료를 하나의 설비 지식 모델(종류 · 속성 · 관계)로 정리해, 설비별 센서와 여러 설비가 함께 쓰는 부품을 답하게 합니다.',
              '자료는 시스템마다 따로 내보낸 것이라 같은 센서 이름이 여러 설비에 쓰이고, 같은 장치를 사람마다 다르게 부르며, 줄이 겹치거나 칸이 비어 있습니다. '
              '손으로 다 맞춰 볼 수 없는 양이므로 AI와 코드로 처리하고 결과는 원자료와 대조합니다. 대상마다 겹치지 않는 ID를 주고 단위와 관계 방향을 정해 두어야, 누가 같은 질문을 해도 같은 답이 나옵니다.',
              STAGE_LINE.format(what='설계 — 질문으로 범위를 정하고, 종류 · 속성 · 관계를 정의해 원자료로 모델을 만드는 일 — ')],
        make='만들 것: 설비 지식 모델의 스키마(종류 · 속성 · 관계의 정의)와 인스턴스(실제 대상과 관계), 원자료에서 그것을 만드는 코드와 모델에 물어보는 확인 코드, `결과/요구사항.md` · `결과/자료_검토.md`.',
        start=['`자료/` — ' + SOURCES.format('') + ' 이번 질문에 쓰는 것은 설비 · 구성 요소 · 센서 · 예비품 · 품번 자료이고, 공급 · 입고 자료는 이번 질문 밖입니다.',
               '`입력/관계그림.json` — 1회차에 ARROWS로 그린 관계 그림(설비 · 구성 요소 · 센서와 증상 · 원인 · 조치). 이번에는 그 가운데 설비 · 센서 · 부품 쪽을 원자료 전체로 구체화합니다.',
               '`결과/` — 이번에 만든 것을 두는 자리. 「제공 빈 틀」 `요구사항.md` · `자료_검토.md`가 있고, 모델(스키마 · 인스턴스)은 아직 없습니다.',
               RULES_LINE],
        tools=TOOLS_DESIGN,
        user='이 답은 보전팀이 설비별 센서를 찾고, 교체할 부품을 어느 설비와 함께 준비할지 정할 때 씁니다. 같은 부품을 구매팀은 호환 후보를 찾을 때, 창고는 품목별 재고를 셀 때 조회합니다.',
        questions=['설비별로 어떤 구성 요소에 어떤 센서 · 계산값 · 설정값이 붙어 있는가?',
                   '각 센서가 재는 물리량과 단위 · 정상값 · 한계(위로 넘는지, 아래로 떨어지는지)는 무엇인가? 설비마다 태그 이름이 달라도 같은 물리량을 재는 센서를 함께 찾을 수 있는가?',
                   '교체 부품별로 그 부품을 쓰는 설비와 구성 요소는 무엇인가? 다른 표기로 적힌 품번, 제조사 규격 번호, 원자료에 없는 품번으로 물으면 결과가 어떻게 구별되는가?'],
        decide=[('쓰는 사람에 따라 갈리는 답', '같은 규격(제조사 품번)으로 등록된 서로 다른 사내 품번을 한 물품으로 볼지 — 그 규격이나 한쪽 품번으로 물었을 때 나와야 할 답이 호환 후보를 찾는 사람과 품목별 재고를 세는 사람에게 같은지')],
        outside=['공급 조건 · 입고 이력을 모델에 넣는 일', '그래프 DB에 적재하고 조회하는 일(다음 실습)', '부품 재고 수량을 세거나 발주를 정하는 일'],
        formats=[FORMAT], steps=steps,
        cases=['같은 태그 이름이 여러 설비에 있는 경우', '이름이 다른데 같은 것을 재는 태그', '같은 장치를 다르게 부른 이름', '같은 대상이 두 번 나온 행',
               f'기준일({D.REF_DATE})에 살아 있지 않은 기록(옛 코드 · 철거된 실물)',
               '비어 있는 칸(단위 · 교체부품 · 정상값)', '단위 표기가 다른 값', '계기 없는 계산값과 설정값', '여러 설비가 함께 쓰는 부품과 한 설비만 쓰는 부품',
               '품번 대신 품명 · 다른 표기로 적힌 칸', '같은 규격(제조사 품번)으로 등록된 다른 사내 품번', '원자료에 없는 품번', '같은 코드를 다시 실행한 결과'],
        commands='python check.py\npython 결과/<만든 코드 이름>.py\npython 결과/<확인 코드 이름>.py <설비 코드 또는 품번>',
        done=('형식 검사나 실행 성공만으로 완료하지 않습니다. 질문마다 원자료에서 먼저 적은 기대 답과 실제 결과가 맞고, 「정한 것」마다 근거 줄과 그 선택으로 바뀌는 답을 설명할 수 있으면 완료입니다. '
              '고친 점과 확인하지 못한 점은 `결과/요구사항.md`에 짧게 남깁니다.'),
        save=save, reopen='9단계 확인 코드의 출력, `요구사항.md`의 기준일 · 저장 시점 · 확인하지 못한 점',
        tree=tree(LAB3, [('.github/', 'Copilot 작업 규칙'), ('결과/', '이번에 만들 것(요구사항.md · 자료_검토.md 빈 틀)'), ('입력/', '1회차에 그린 관계 그림(읽기만)'),
                         ('자료/', '원자료 CSV 8개 · 현장 메모(읽기만)'), *DESIGN_TREE_TAIL]),
        guide_extra={1: f'<p>{OPEN_AI}</p>', 4: f'<p>{OPEN_TERMINAL} {REVIEW_EDIT}</p>'},
        files={'check.py': CHECKER,'결과/요구사항.md': req_template('요구사항'), '결과/자료_검토.md': REVIEW_TEMPLATE,
               '결과/README.md': '이번 과제의 모델(schema.json · graph.json), 모델을 만든 코드와 모델에 물어보는 확인 코드, 요구사항.md, 자료_검토.md를 여기에 저장합니다.\n다시 열 때는 요구사항.md의 기준일 · 저장 시점과 확인 코드의 출력을 함께 봅니다.\n',
               '입력/README.md': '1회차에 ARROWS로 그린 관계 그림(관계그림.json)입니다. 이번 모델의 출발 그림으로 보고, 이 폴더는 읽기만 합니다.\n'})


def design_practical():
    title = '설비·부품·공급 정보를 연결하는 온톨로지 설계하기'
    save = (f'`결과/schema.json` · `결과/graph.json`을 한 쌍으로, 만든 코드 · 확인 코드 · `요구사항.md` · `자료_검토.md`와 함께 보관합니다. '
            f'다음 실습 「{NEXT_LAB["실전반"]}」에서는 이 판본을 쓰거나 제공된 설비 · 부품 · 공급 모델로 시작할 수 있습니다. ' + USB)
    steps = [
        S('폴더와 출발점 확인', '시작',
          'VS Code 탐색기에서 이 폴더의 `입력/` · `자료/` · `결과/` · START.md를 열어 각 자리의 역할과 이번 질문을 확인합니다.',
          '이번 질문 세 개와, 이 답을 쓰는 사람이 누구인지 확인합니다.',
          '탐색기에서 네 자리를 찾았고, `입력/schema.json`의 관계 목록에 공급사와 이어지는 관계가 아직 없다는 것을 파일에서 확인했습니다.'),
        S('파일을 바꾸지 않고 자료 파악', '① 파악',
          'AI에게 파일을 바꾸지 말고, 펌프 축 씰 키트에 관한 줄을 자료마다 찾아 파일 · 줄로 짚어 달라고 합니다. 짚은 줄을 직접 엽니다.',
          '어느 자료가 공급 조건 · 승인 · 비교 기준을 말하는지, 같은 대상을 두고 자료끼리 다르게 말하는 곳이 있는지 묻습니다.',
          'AI가 짚은 줄을 열었을 때 그 내용이 실제로 있습니다. 질문 1 · 2에 쓸 자료가 무엇인지 내 말로 말할 수 있습니다. 편집 승인 창이 뜨지 않았고 AI의 답에 바꾼 파일이 없습니다.',
          H('펌프 축 씰 키트에 관한 근거 줄을 자료마다 모은다. 아직 아무것도 만들지 않는다.',
            '`자료/` 전체, `입력/graph.json`, START.md 「해결할 질문」',
            '파일을 바꾸지 않는다. 해석보다 파일 · 줄 번호를 먼저 받는다.',
            '「파일 · 줄 · 그 줄이 말하는 것」 목록과, 자료끼리 말이 달라 보이는 곳 목록',
            '짚은 줄 가운데 몇 개를 내가 직접 열어 같은 내용인지 본다')),
        S('요구와 기대 답 정하기', '② 요구',
          '질문 · 이 답을 쓰는 사람 · 기준일 · 지킬 조건과, 질문 1 · 2의 기대 답을 원자료에서 직접 찾아 `결과/요구사항.md`에 내 말로 적습니다. 「학생이 정할 것」의 지점마다 고른 것과 근거 줄을 적습니다.',
          ASK_DECIDE,
          '기대 답마다 파일 · 줄이 붙어 있습니다. 「정한 것」 표의 지점마다 고른 것 · 근거 · 바뀌는 답이 채워져 있거나 미결로 적혀 있습니다. AI의 되짚기가 내 요구와 같습니다.',
          H('내가 정한 요구를 AI가 같은 뜻으로 이해하게 한다',
            '2단계에서 연 근거 줄, `결과/요구사항.md`(제공 빈 틀)',
            '기대 답은 내가 원자료에서 찾은 값으로 적는다(AI의 답을 옮기지 않는다). 「학생이 정할 것」은 내가 고른다.',
            '`요구사항.md`의 칸 — 목표와 질문, 이 답을 쓰는 사람, 자료와 기준일, 지킬 조건, 「정한 것」 표, 「기대 답과 실제 결과」 표',
            'AI에게 `요구사항.md`를 자기 말로 되짚게 하고, 내 뜻과 다른 곳을 고친다')),
        S('설계 계획 검토', '③ 계획',
          '공급 정보를 모델의 어느 종류 · 속성 · 관계로 둘지 AI의 계획을 받아 검토하고, 5 ~ 10단계의 구현 순서에 동의합니다. 아직 파일을 만들지 않습니다.',
          '「결과 형식」이 정해 둔 것과 내가 정할 것을 나눕니다. 「정한 것」 표의 결정(승인 정보 · 출처 등)을 어느 속성에 둘지 정합니다.',
          '질문마다 계획의 어느 관계 · 속성으로 답하는지 짚을 수 있습니다. 계획에 공급사 고르기 · 점수 같은 범위 밖 기능이 없습니다. 계획에 내가 동의했습니다.',
          H('만들기 전에 공급 정보를 둘 모양을 합의한다',
            'START.md 「결과 형식」, `입력/schema.json`, `결과/요구사항.md`',
            '제공된 설비 · 부품 모델의 종류 · ID · 관계를 유지한다. 「정한 것」 표를 반영한다. 「이번 범위 밖」은 넣지 않는다.',
            '더할 종류 · 속성(자료형 · 필수 여부) · 관계(방향 · 연결 수)의 표와 구현 순서',
            '질문 1 ~ 3을 하나씩 계획에 대어 보아 어느 관계 · 속성으로 답하는지 짚게 한다')),
        S('구현 ① 공급사 대상 만들기', '④ ~ ⑥ 구현 · 대조 · 고침',
          '견적 자료와 승인 공급사 목록에 나오는 공급사를 하나씩 공급사 대상으로 만드는 코드를 `결과/`에 만들고 실행합니다.',
          '표기가 다른데 같은 회사로 볼 근거가 무엇인지 묻고, 근거가 있는 것만 하나로 묶습니다.',
          '표기 하나하나가 대상 하나에 붙었고 남은 표기가 없습니다. 한 대상에 묶인 표기가 같은 회사라는 근거를 원자료에서 말할 수 있습니다. 바뀐 파일이 `결과/` 아래뿐입니다.',
          H('자료에 나오는 공급사를 하나씩 공급사 대상으로 만든다',
            '`자료/공급_조건.csv` · `자료/승인공급사_목록.csv`, 4단계 계획',
            '같은 회사로 볼 근거가 있는 표기만 하나로 묶는다. 코드는 `결과/`에 두고 `입력/` · `자료/`는 읽기만 한다.',
            '공급사 대상 목록(ID · 이름 · 원자료에 적힌 표기들)',
            '두 파일의 공급사 칸 표기를 모두 모아, 표기마다 어느 대상에 붙었는지 표로 보여 달라고 한다'),
          'python 결과/<만든 코드 이름>.py'),
        S('구현 ② 기준일에 쓸 견적 조건 잇기', '④ ~ ⑥ 구현 · 대조 · 고침',
          '공급사 · 부품 쌍마다 기준일에 쓸 견적 조건 하나를 `SUPPLIES` 관계로 잇는 기능을 더하고 실행합니다.',
          '같은 쌍에 줄이 여럿이거나 기한이 걸린 줄을 어떻게 처리했는지와 그렇게 본 근거 줄을 묻습니다.',
          '세 갈래 줄 수의 합이 견적 자료의 줄 수와 같습니다. 펌프 축 씰 키트의 공급사와 값이 내가 먼저 적은 기대 답과 같습니다. 부품 대상의 수가 제공된 설비 · 부품 모델과 같습니다.',
          H('공급사 · 부품 쌍마다 기준일에 쓸 견적 조건 하나를 잇는다',
            '`자료/공급_조건.csv`, 5단계의 공급사 대상, `입력/graph.json`의 부품',
            '기준일에 쓸 줄을 고른 근거를 남긴다. 부품은 제공된 설비 · 부품 모델의 ID에 잇고 새 부품 대상을 만들지 않는다. 이을 근거가 없는 줄은 억지로 잇지 않는다.',
            '쌍마다 관계 하나(「공급 조건 형식」의 다섯 속성)와, 잇지 않은 줄의 목록 · 이유',
            '견적 줄을 「이었음 · 기준일에 쓰지 않음 · 잇지 못함」으로 나눠 세게 하고, 펌프 축 씰 키트의 쌍을 `요구사항.md`의 기대 답과 나란히 놓는다'),
          'python 결과/<만든 코드 이름>.py'),
        S('구현 ③ 승인 정보 붙이기', '④ ~ ⑥ 구현 · 대조 · 고침',
          '`SUPPLIES`마다 `approved`와, 4단계에서 정한 승인 정보 속성을 「정한 것」 표의 결정대로 붙이고 실행합니다.',
          '이 단계의 결과는 내 결정에 따라 달라집니다. AI가 결정을 대신 정하려 하면 돌려보내고 내 선택과 근거를 다시 말합니다.',
          '펌프 축 씰 키트의 승인 표시마다 결정과 근거 줄을 짚을 수 있습니다. 같은 결정이 다른 쌍에도 같은 방식으로 적용됐습니다. 결정을 바꾸면 무엇이 바뀌는지 말할 수 있습니다.',
          H('쌍마다 승인 여부와, 고르는 사람이 알아야 할 승인 관련 정보를 붙인다',
            '`자료/승인공급사_목록.csv`, `자료/공급_조건.csv`의 승인 칸, `자료/구매기준서_PR-07_발췌.md`, 「정한 것」 표',
            '「정한 것」 표의 결정대로 한다. 미결인 지점은 미결로 표시하고 값을 지어내지 않는다. 고르기 · 점수는 넣지 않는다.',
            '`approved`와 4단계에서 정한 승인 정보 속성(상태 · 조건 · 근거 출처 등)',
            '펌프 축 씰 키트의 공급사마다 승인 표시가 어느 결정 · 어느 줄에서 나왔는지 보여 달라고 하고, 같은 종류의 다른 쌍 몇 개에도 같은 결정이 적용됐는지 본다'),
          'python 결과/<만든 코드 이름>.py'),
        S('구현 ④ 단위 맞추기', '④ ~ ⑥ 구현 · 대조 · 고침',
          '단가 · 불량률 · 납기를 「공급 조건 형식」의 단위로 맞추고, 바꾼 값은 원래 표기를 남기는 기능을 더하고 실행합니다.',
          '원래 표기를 어느 속성에 남길지 정합니다.',
          '표기가 달랐던 줄마다 바꾼 값과 원래 표기가 맞습니다. ' + FIX_LOOP,
          H('값을 정해진 단위로 맞추고, 바꾼 값의 원래 표기를 남긴다',
            '6 · 7단계 결과, `자료/공급_조건.csv`',
            '원래 표기를 지우지 않고 남긴다. 단위를 알 수 없는 값은 짐작하지 않고 미확인으로 둔다.',
            '단가 · 불량률 · 납기 값과 바꾼 값의 원래 표기',
            '표기가 다른 줄을 모두 찾아 원래 표기와 바꾼 값을 나란히 보여 달라고 하고, 그 줄을 원자료에서 연다'),
          'python 결과/<만든 코드 이름>.py'),
        S('구현 ⑤ 값마다 출처 남기기', '④ ~ ⑥ 구현 · 대조 · 고침',
          '`SUPPLIES`의 값마다 어느 파일 · 어느 날짜 자료에서 왔는지 남기는 기능을 더하고 실행합니다.',
          '출처를 어느 속성에 어떤 수준(파일 · 줄 · 날짜)으로 남길지 정합니다.',
          '질문 2의 값 하나하나에서 출처를 따라가 원자료 줄에 닿습니다. ' + FIX_LOOP,
          H('값마다 어디서 왔는지 남긴다',
            '6 ~ 8단계 결과, `자료/공급_조건.csv` · `자료/승인공급사_목록.csv`',
            '원자료에 있는 파일 · 날짜만 출처로 적는다. 출처를 찾지 못한 값은 짐작하지 않고 미확인으로 둔다.',
            '값마다 출처(파일 · 날짜)',
            '질문 2의 값 몇 개를 골라 출처를 따라가 원자료 줄을 직접 연다'),
          'python 결과/<만든 코드 이름>.py'),
        S('구현 ⑥ 품번으로 물어보기', '④ ⑤ 구현 · 대조',
          '품번이나 표기 하나를 받아 `결과/graph.json`에서 사용 설비 · 구성 요소와 공급 조건(출처 포함)을 보여 주는 확인 코드를 만들고 실행합니다.',
          '원자료에 없는 품번으로 물었을 때 무엇을 보여 줄지(값 없음과 미확인을 어떻게 구별할지) 정합니다.',
          '펌프 축 씰 키트가 모델에 하나로 있고 사용 설비가 기대 답과 같습니다. 네 가지 물음의 결과가 서로 구별됩니다. 다시 실행해도 같습니다. ' + FIX_LOOP,
          H('모델만으로 질문 1 ~ 3의 답이 나오는지 직접 물어본다',
            '`결과/graph.json`, `요구사항.md`의 「기대 답과 실제 결과」 표',
            '모델(결과 파일)만 읽는다 — 원자료를 다시 읽어 답을 만들지 않는다. 없는 품번에 값을 지어내지 않는다.',
            '품번이나 표기 하나를 받아 결과를 보여 주는 확인 코드와 그 출력',
            '펌프 축 씰 키트, 이름이 비슷한 다른 품번, 예전 품번이나 다른 표기, 원자료에 없는 품번 네 가지로 실행하고, 두 번 실행해 같은지 본다'),
          'python 결과/<확인 코드 이름>.py <품번>'),
        S('구조 검사와 고치기', '⑤ ⑥ 대조 · 고침',
          '터미널에서 구조 검사를 실행하고, 나온 문제를 고친 뒤 10단계 확인을 다시 합니다.',
          '검사가 짚은 문제가 결과 파일의 어느 대상 · 관계인지 묻습니다.',
          '「구조 검사 통과」 줄이 나옵니다. 「참고」 줄의 관계 개수를 원자료의 줄 수와 견주어 설명할 수 있습니다. 고친 뒤에도 10단계 결과가 같습니다. 검사 통과는 구조만 본 것이고, 질문의 답은 내가 대조한 기록으로 판단합니다.',
          H('구조 문제를 찾아 고친다', '`python check.py`의 출력', '검사 기준과 원자료를 바꾸지 않는다', '고친 파일 목록과 다시 실행한 출력', '고친 뒤 10단계의 네 가지 물음을 다시 실행한다'),
          'python check.py'),
        S('저장하고 다시 열기', '⑦ 저장 · 다시 열기',
          '결과 파일을 모두 저장하고 VS Code에서 폴더를 닫았다 다시 연 뒤 10단계 명령을 다시 실행합니다. `요구사항.md` 끝에 기준일 · 저장 시점 · 확인하지 못한 점을 적습니다.',
          '확인하지 못한 점으로 무엇을 남길지 정합니다.',
          '다시 연 뒤에도 10단계 출력이 같습니다. `결과/`에 모델 두 파일 · 코드 · 기록 두 파일이 있습니다.',
          cmd='python 결과/<확인 코드 이름>.py <품번>'),
    ]
    return dict(
        title=title, rec='결과/요구사항.md', readonly='`입력/` · `자료/`가', decide_step=2,
        goal=['포털 지식 지도에서 한 부품을 쓰는 설비를 찾아보며, 연결이 있다는 것과 그 부품을 실제로 살 수 있는 조건이 확보됐다는 것은 다르다는 것을 확인했습니다. '
              '이번에는 그 공급 조건을 직접 모델에 넣습니다. 제공된 설비 · 부품 모델에 구매팀의 견적 · 승인 · 품번 자료를 연결해, 부품마다 쓰는 설비와 공급사별 조건을 함께 답하는 모델로 확장합니다.',
              '같은 부품이라도 어느 공급사에서 어떤 조건으로 살 수 있는지는 시점과 출처에 따라 달라집니다. 그래서 값마다 어느 자료의 언제 값인지 남겨야 고르는 사람이 믿고 쓸 수 있습니다. '
              '이 모델은 공급사를 골라 주지 않습니다. 고르는 사람이 고를 때 필요한 정보를 찾아 주는 구조입니다.',
              STAGE_LINE.format(what='설계 — 질문으로 범위를 정하고, 종류 · 속성 · 관계를 정의해 원자료로 모델을 만드는 일 — ')],
        make=('만들 것: 공급 정보를 더한 스키마(종류 · 속성 · 관계의 정의)와 인스턴스(실제 대상과 관계), 원자료에서 그것을 만드는 코드와 모델에 물어보는 확인 코드, '
              '`결과/요구사항.md` · `결과/자료_검토.md`.'),
        start=['`입력/schema.json` · `입력/graph.json` — 제공된 설비 · 부품 모델. 설비 7대 · 구성 요소 · 센서 · 부품과 그 연결이 들어 있고, 공급 정보는 아직 없습니다.',
               '`자료/` — ' + SOURCES.format(', 구매 기준서 발췌'),
               '`결과/` — 이번에 만든 것을 두는 자리. 「제공 빈 틀」 `요구사항.md` · `자료_검토.md`가 있습니다.',
               RULES_LINE],
        user='이 답은 구매 담당이 다음 발주에서 공급사를 비교할 때 씁니다. 고르는 것은 구매 담당입니다.',
        questions=['펌프 축 씰 키트를 쓰는 설비와 구성 요소는 어디인가?',
                   f'기준일({D.REF_DATE})에 펌프 축 씰 키트를 어느 공급사에서 어떤 조건(승인 여부 · 단가 · 불량률 · 납기)으로 살 수 있고, 각 값은 어느 파일 · 어느 날짜 자료에서 왔는가?',
                   '이름이 비슷한 다른 품번, 예전 품번이나 다른 표기, 원자료에 없는 품번으로 물으면 결과가 서로 구별되는가?'],
        decide=[('출처끼리 부딪치는 권위', '같은 공급사 · 부품을 두 자료가 다르게 말할 때 무엇을 따르고, 구매 담당에게 어떻게 보여 줄지'),
                ('빈 값의 뜻', '비어 있는 칸을 「없음」으로 읽을지 「적지 않음」으로 읽을지'),
                ('쓰는 사람에 따라 갈리는 답', '구매 담당이 공급사를 비교할 때 함께 봐야 할 것이 자료에 있으면, 그것을 모델에 어떻게 남길지')],
        outside=['공급사를 고르거나 점수 · 순위를 매기는 일', '입고 이력으로 실측 납기를 계산하는 일', '그래프 DB에 적재하고 조회하는 일(다음 실습)',
                 '제공된 설비 · 부품 모델의 설비 · 구성 요소 · 센서 · 부품 부분을 고치는 일(이상한 곳은 `결과/자료_검토.md`에 적습니다)'],
        formats=[FORMAT, SUPPLY_FORMAT], steps=steps,
        cases=['같은 공급사 · 부품의 견적이 여러 줄인 경우', '기준일에 기한이 지난 기록(견적 · 승인 등록)', '같은 공급사를 다르게 적은 이름',
               '출처마다 다른 승인 정보', '기준서에 나오는 기준값과 같거나 가까운 값', '단위 · 표기가 줄마다 다른 값', '품번 칸의 표기가 줄마다 다른 경우',
               '이름이 비슷한 다른 품번 · 예전 품번 · 다른 표기 · 원자료에 없는 품번', '같은 코드를 다시 실행한 결과'],
        commands='python check.py\npython 결과/<만든 코드 이름>.py\npython 결과/<확인 코드 이름>.py <품번>',
        done=('형식 검사나 실행 성공만으로 완료하지 않습니다. 질문마다 원자료에서 먼저 적은 기대 답과 실제 결과가 맞고, 「정한 것」마다 근거 줄과 그 선택으로 바뀌는 답을 설명할 수 있으면 완료입니다. '
              '고친 점과 확인하지 못한 점은 `결과/요구사항.md`에 짧게 남깁니다.'),
        save=save, reopen='10단계 확인 코드의 출력, `요구사항.md`의 기준일 · 저장 시점 · 확인하지 못한 점',
        tree=tree(LAB3, [('.github/', 'Copilot 작업 규칙'), ('결과/', '이번에 만들 것(요구사항.md · 자료_검토.md 빈 틀)'), ('입력/', '제공된 설비 · 부품 모델(읽기만)'),
                         ('자료/', '원자료 CSV 8개 · 현장 메모 · 구매 기준서 발췌(읽기만)'), *DESIGN_TREE_TAIL]),
        guide_extra={1: f'<p>{OPEN_AI}</p>', 4: f'<p>{OPEN_TERMINAL} {REVIEW_EDIT}</p>'},
        files={'check.py': CHECKER_SUPPLY, '결과/요구사항.md': req_template('요구사항'), '결과/자료_검토.md': REVIEW_TEMPLATE,
               '결과/README.md': '이번 과제의 모델(schema.json · graph.json), 모델을 만든 코드와 모델에 물어보는 확인 코드, 요구사항.md, 자료_검토.md를 여기에 저장합니다.\n다시 열 때는 요구사항.md의 기준일 · 저장 시점과 확인 코드의 출력을 함께 봅니다.\n',
               '입력/README.md': '제공된 설비 · 부품 모델입니다(schema.json · graph.json). 설비 7대 · 구성 요소 · 센서 · 부품과 그 연결이 있고, 공급 정보는 없습니다. 이 폴더는 읽기만 합니다.\n'})


# ───────────── 실습4(그래프 구현과 검증) — 두 과정 ─────────────
def provided_basis(practical):
    """실습4 입력/자료_검토.md — 제공된 모델이 원자료를 어떻게 처리했는지(이번 실습의 결과가 아님)."""
    lines = ['# 제공된 모델의 자료 처리 근거', '',
             '이 모델(schema.json · graph.json)은 원자료와 현장 메모로 만든 설계 단계의 완성 모델입니다. 이번 실습의 적재 · 조회 결과가 아닙니다. 처리 기준은 schema.json의 constraints에 적혀 있습니다.', '',
             '- 설비: 「코드 통합」 이관 기록은 대상을 새로 만들지 않고 legacy_codes로 남겼습니다. 구성 요소는 기능 자리 기준 ID이고 실물 교체는 serial로 남겼습니다(철거 행 제외).',
             '- 센서: 같은 설비 · 태그의 점검표 재기입 행은 하나로 두었습니다. 단위는 물리량 기준 단위로 맞추고 바꾼 경우 source_unit을 남겼습니다. 계산값 · 설정값은 kind로 구별했습니다. 한계가 없으면 limit을 생략했습니다.',
             '- 부품: 교체부품 칸의 품명 · 표기 변형 · 제조사 품번은 품번 교차표와 예비품 목록의 적용 모델 · 쓰는곳으로 사내 품번에 이었습니다. 같은 규격의 다른 사내 품번은 따로 두었습니다.']
    if practical:
        lines.append('- 공급: 공급사 · 품번마다 기준일에 유효한 최신 견적 하나를 SUPPLIES로 두었습니다. 승인 여부는 승인공급사_목록(SCM 등록)과 기준일로 정했습니다(조건부 승인은 approved=true, 조건은 condition). '
                     f'구매 기준서 PR-07 7.4(불량률이 {D.PR74_RATE_PCT} %를 넘는 승인 공급사는 발주 때 입고 전수 검사, 비교 비용 +{D.PR74_EXTRA_MANWON}만 원)에 걸리는 쌍에는 그 정보를 inspection · compare_extra_manwon · rule_source로 붙였습니다.')
    return '\n'.join(lines) + '\n'


def graph_lab(course):
    practical = course == '실전반'
    title = '부품의 사용 설비와 공급 정보를 조회하는 그래프 구현하기' if practical else '설계한 온톨로지를 그래프 DB에 구현하고 검증하기'
    model = '설비 · 부품 · 공급 모델' if practical else '설비 · 센서 · 부품 모델'
    change_dir = f'입력/자료_변경분/{D.CHANGE_DATE}_수정본/'
    s_tree = S('폴더와 출발점 확인', '시작',
               f'VS Code 탐색기에서 `입력/`(제공된 모델 · 원자료 · 수정본) · `결과/` · `lab_db.py` · START.md를 열어 각 자리의 역할과 이번 질문을 확인합니다.',
               '이번 질문과, 이 답을 쓰는 사람이 누구인지 확인합니다. 내가 만든 모델을 쓸지 제공된 모델을 쓸지 정합니다.',
               f'탐색기에서 다섯 자리를 찾았습니다. `{change_dir}`에 어떤 파일이 있는지 말할 수 있습니다.')
    s_db = S('랩 DB 켜기', '시작',
             '터미널에서 `python lab_db.py`를 실행해 이 폴더 전용 랩 DB를 켜고, 열린 Neo4j Browser에 연결합니다.',
             '출력된 주소가 `127.0.0.1`의 이 폴더 전용 주소인지 확인합니다.',
             '「랩 DB 준비 완료」와 주소가 나왔고, Browser에서 개수 조회가 빈 결과(이 폴더 전용 DB가 아직 비어 있음)를 보입니다.',
             cmd='python lab_db.py')
    s_look = S('파일을 바꾸지 않고 자료 파악', '① 파악',
               f'AI에게 파일을 바꾸지 말고, `입력/graph.json`에 어떤 종류의 대상과 관계가 몇 개 있는지와 수정본의 줄마다 그래프의 어느 대상을 가리키는지 파일 · 줄로 짚어 달라고 합니다. 짚은 줄을 직접 엽니다.',
               '수정본에서 무엇이 바뀌는지(이름 · 상태 · 값 · 줄 삭제), 제공된 모델의 ID가 무엇으로 지어졌는지 묻습니다.' + (' 입고 이력에서 한 발주가 여러 줄인 곳이 있는지도 묻습니다.' if practical else ''),
               EVIDENCE_LOOK + ' 종류별 대상 수와 수정본의 줄 수를 내 말로 말할 수 있습니다.',
               H('적재할 모델과 수정본을 파악한다. 아직 아무것도 만들지 않는다.',
                 '`입력/schema.json` · `입력/graph.json` · `입력/자료_검토.md`, `' + change_dir + '`' + (', `입력/자료/입고_이력.csv`' if practical else ''),
                 '파일을 바꾸지 않는다. 해석보다 파일 · 줄 번호와 개수를 먼저 받는다.',
                 '종류별 대상 수 · 관계 수 표, 수정본 줄마다 「가리키는 대상 · 바뀌는 것」 목록',
                 '개수 몇 개와 수정본 줄 몇 개를 내가 직접 파일에서 세어 본다'))
    req_do = ('질문 · 이 답을 쓰는 사람 · 지킬 조건과, ' +
              ('펌프 축 씰 키트의 사용 설비와 세 공급 조건, 공급사 하나의 지난 발주별 납기, ' if practical else '설비 하나의 구성 요소별 센서와 공용 부품 하나의 사용 설비, ') +
              '수정본 반영 뒤 달라져야 할 것을 원자료에서 직접 찾아 기대 답으로 `결과/검증_기록.md`에 적습니다. 「학생이 정할 것」의 지점마다 고른 것과 근거 줄을 적습니다.')
    s_req = S('요구와 기대 답 정하기', '② 요구', req_do, ASK_DECIDE,
              '기대 답마다 파일 · 줄이 붙어 있습니다. 「정한 것」 표의 지점마다 고른 것 · 근거 · 바뀌는 답이 채워져 있거나 미결로 적혀 있습니다. AI의 되짚기가 내 요구와 같습니다.',
              H('내가 정한 요구를 AI가 같은 뜻으로 이해하게 한다',
                '3단계에서 연 근거 줄, `결과/검증_기록.md`(제공 빈 틀)',
                '기대 답은 내가 원자료에서 찾은 값으로 적는다(AI의 답을 옮기지 않는다). 「학생이 정할 것」은 내가 고른다.',
                '`검증_기록.md`의 칸 — 목표와 질문, 이 답을 쓰는 사람, 사용한 입력, 지킬 조건, 「정한 것」 표, 「기대 답과 실제 결과」 표',
                'AI에게 `검증_기록.md`를 자기 말로 되짚게 하고, 내 뜻과 다른 곳을 고친다'))
    s_plan = S('적재 계획 검토', '③ 계획',
               '대상과 관계를 어떤 문장으로 어떤 순서로 넣을지 AI의 계획을 받아 검토합니다. 스키마의 ID와 관계 방향이 그래프의 노드 · 관계로 어떻게 옮겨지는지 짚습니다. 아직 파일을 만들지 않습니다.',
               '스키마의 ID가 노드의 무엇이 되고, 관계의 시작 · 끝이 어느 쪽이 되는지 내 말로 설명합니다. 같은 적재를 다시 실행해도 대상이 늘지 않으려면 무엇이 필요한지 묻습니다.',
               '노드의 ID와 관계 방향이 스키마와 어떻게 대응하는지 표로 짚을 수 있습니다. 계획에 전체 삭제문이 없습니다. 계획에 내가 동의했습니다.',
               H('만들기 전에 적재 방법과 순서를 합의한다',
                 '`입력/schema.json`, 3단계의 개수 표, START.md 「결과 형식」',
                 '이 폴더의 랩 DB에만 넣는다. 전체 삭제문을 쓰지 않는다. ID를 바꾸지 않는다. 「이번 범위 밖」은 넣지 않는다.',
                 f'종류 · 관계마다 「무엇으로 같은 대상을 알아보는지 · 넣는 순서」 표와 6 ~ {11 if practical else 12}단계 순서',
                 '스키마의 관계 하나를 골라 그 관계가 노드 · 관계로 어떻게 옮겨지는지 예로 들어 설명하게 한다'))
    s_load = S('구현 ① 적재하기', '④ ~ ⑥ 구현 · 대조 · 고침',
               '모델 파일의 대상과 관계를 랩 DB에 넣는 적재문(또는 적재 코드)을 `결과/`에 만들고 실행합니다.',
               '종류별 노드 수와 관계 수를 입력 파일과 견줍니다.',
               '종류별 노드 수와 관계 수가 모델 파일에서 센 수와 같습니다. 바뀐 파일이 `결과/`(와 랩 DB를 켤 때 생긴 `랩_연결.json`)뿐입니다. ' + FIX_LOOP,
               H('모델 파일의 대상과 관계를 랩 DB에 그대로 옮긴다',
                 '`입력/schema.json` · `입력/graph.json`(또는 내 모델), 5단계 계획, `랩_연결.json`의 주소',
                 '이 폴더의 랩 DB에만 넣는다. 전체 삭제문을 쓰지 않는다. 대상 수백 개를 손으로 옮기지 않고 파일에서 만든다.',
                 '`결과/load.cypher` 또는 적재 코드와 실행 출력',
                 '종류별 노드 수 · 관계 수를 모델 파일에서 센 수와 나란히 보여 달라고 한다'),
               'Browser에서 결과/load.cypher 실행, 또는 python 결과/<적재 코드 이름>.py')
    s_again = S('같은 적재 다시 실행', '⑤ 대조',
                '같은 적재를 한 번 더 실행하고 종류별 개수를 첫 실행과 비교합니다.',
                '개수가 달라진 종류가 있으면 어느 대상이 늘었는지와 그 까닭을 묻습니다.',
                '두 번째 실행 뒤에도 종류별 노드 수 · 관계 수가 첫 실행과 같습니다. 고친 적이 있으면 무엇을 고쳤는지 기록에 있습니다.',
                H('같은 적재를 다시 실행해도 대상과 관계가 늘지 않는지 확인한다',
                  '6단계 적재문, 6단계의 개수',
                  '개수를 맞추려고 전체를 지우고 다시 넣지 않는다',
                  '첫 적재 · 다시 적재의 노드 · 관계 수 표(`검증_기록.md`)',
                  '두 번째 실행 뒤 종류별 개수를 첫 실행과 나란히 놓는다'),
                'Browser에서 같은 적재 다시 실행')
    s_change = S('구현 ⑤ 수정본 반영하기', '④ ~ ⑥ 구현 · 대조 · 고침',
                 '수정본의 줄마다 필요한 대상 · 관계만 고치는 수정문(또는 수정 코드)을 `결과/`에 만들고 실행합니다.',
                 '이 단계의 결과는 내 결정에 따라 달라집니다. 상태가 바뀐 설비를 「정한 것」 표의 결정대로 반영했는지, 「삭제」 줄이 그래프에서 무엇을 바꿨는지 묻습니다. AI가 결정을 대신 정하려 하면 돌려보내고 내 선택과 근거를 다시 말합니다.',
                 '반영 전후 개수 변화를 수정본의 줄 하나하나로 설명할 수 있습니다. 「삭제」 줄이 걸린 설비의 센서 수를 원자료 행과 다시 세어, 실제로 있는 센서가 사라지지 않았는지 확인했습니다. 이름이 바뀐 설비의 ID가 그대로입니다. 같은 수정문을 다시 실행해도 개수가 같습니다. 조회를 다시 실행한 「지금 가동하는 설비」 답이 「정한 것」과 맞습니다.',
                 H('전체를 지우지 않고 수정본이 고친 것만 그래프에 반영한다',
                   f'`{change_dir}`, 「정한 것」 표, 6단계 이후의 조회문',
                   '전체 삭제문을 쓰지 않는다. ID를 바꾸지 않는다. 「정한 것」 표의 결정대로 한다.',
                   '`결과/update.cypher` 또는 수정 코드, 반영 전후의 노드 · 관계 수와 바뀐 대상 목록',
                   '반영 전후 개수 변화를 수정본의 줄로 설명하게 하고, 같은 수정을 한 번 더 실행해 개수를 비교한다'),
                 'Browser에서 결과/update.cypher 실행, 또는 python 결과/<수정 코드 이름>.py')
    if practical:
        query_steps = [
            S('구현 ② 사용 설비와 공급 조건 조회', '④ ~ ⑥ 구현 · 대조 · 고침',
              '품번 하나를 받아 그 부품을 쓰는 설비 · 구성 요소와 공급사별 공급 조건(승인 상태 · 출처 포함)을 돌려주는 조회문을 `결과/query.cypher`에 만들고 실행합니다.',
              '비승인 공급사를 결과에서 어떻게 구별해 보일지, 어떤 속성을 함께 돌려줄지 정합니다.',
              '펌프 축 씰 키트의 사용 설비와 세 공급 조건이 내가 먼저 적은 기대 답과 같고, 비승인 공급사가 승인 상태와 함께 구별됩니다. ' + FIX_LOOP,
              H('부품 하나의 사용 설비와 공급 조건을 한 번에 돌려준다',
                '랩 DB의 그래프, `입력/schema.json`의 관계 방향, 「기대 답과 실제 결과」 표',
                '조회만 한다(그래프를 바꾸지 않는다). 공급사를 고르거나 순위를 매기지 않는다.',
                '조회문과 Table 결과(설비 · 구성 요소, 공급사마다 승인 상태 · 단가 · 불량률 · 납기 · 출처)',
                '펌프 축 씰 키트의 결과를 기대 답과 줄마다 나란히 놓는다'),
              'Browser에서 결과/query.cypher의 조회 실행'),
            S('구현 ③ 다른 표기와 없는 품번 구별', '④ ~ ⑥ 구현 · 대조 · 고침',
              '예전 품번 · 다른 표기로 물어도 같은 부품을 찾고, 이름이 비슷한 다른 품번과 원자료에 없는 품번을 구별해 돌려주게 조회를 고치고 실행합니다.',
              '원자료에 없는 품번으로 물었을 때 무엇을 돌려줄지(빈 결과와 미확인을 어떻게 구별할지) 정합니다.',
              '예전 품번 · 다른 표기로 물은 결과가 정식 품번과 같고, 이름이 비슷한 다른 품번과 없는 품번의 결과가 서로 구별됩니다. ' + FIX_LOOP,
              H('품번을 어떻게 적어 물어도 같은 부품을 찾고, 없는 것은 없다고 돌려준다',
                '8단계 조회문, `입력/graph.json`의 부품 속성, `입력/자료/품번_교차표.csv`',
                '없는 품번에 값을 지어내지 않는다. 비슷한 이름의 다른 품번을 같은 부품으로 합치지 않는다.',
                '고친 조회문과 네 가지 물음(정식 품번 · 예전 품번이나 다른 표기 · 비슷한 다른 품번 · 없는 품번)의 결과',
                '네 가지 물음을 실행해 결과를 서로 견주고, 기대 답과 나란히 놓는다'),
              'Browser에서 결과/query.cypher의 조회 실행'),
            S('구현 ④ 실측 납기 세기', '④ ~ ⑥ 구현 · 대조 · 고침',
              '`입력/자료/입고_이력.csv`에서 펌프 축 씰 키트의 공급사별 실측 납기를 세는 코드를 `결과/`에 만들고 실행해, 견적 납기와 나란히 놓습니다.',
              '이 단계의 결과는 내 결정에 따라 달라집니다. 나눠 들어온 발주와 아직 다 들어오지 않은 발주에 「정한 것」 표의 결정이 그대로 적용됐는지 묻습니다.',
              '공급사 하나의 발주별 납기가 내가 먼저 손으로 센 기대 답과 같습니다. 나눠 들어온 발주를 결정대로 셌습니다. 견적 납기와 실측 납기의 차이를 공급사별로 말할 수 있습니다.',
              H('지난 입고로 공급사별 실측 납기를 세어 견적 납기와 견준다',
                '`입력/자료/입고_이력.csv` · `입력/자료/품번_교차표.csv`, 「정한 것」 표, 8단계 조회의 견적 납기',
                '「정한 것」 표의 결정대로 센다. 입고일이 없는 줄에 날짜를 지어내지 않는다. 공급사를 고르지 않는다.',
                '공급사마다 「견적 납기 · 센 발주 수 · 실측 납기(평균 · 최대) · 근거 줄」 표',
                '공급사 하나의 발주를 내가 손으로 센 값과 코드 결과를 나란히 놓고, 결정을 바꾸면 무엇이 바뀌는지 본다'),
              'python 결과/<납기 코드 이름>.py')]
    else:
        query_steps = [
            S('구현 ② 설비별 센서 조회', '④ ~ ⑥ 구현 · 대조 · 고침',
              '설비 하나를 받아 구성 요소별 센서와 그 물리량 · 단위 · 한계를 돌려주는 조회를 `결과/query.cypher`에 만들고 실행합니다.',
              '설비에 바로 붙은 센서를 구성 요소의 센서와 어떻게 함께 보일지, 한계가 없는 센서를 어떻게 보일지 정합니다.',
              '고른 설비의 구성 요소별 센서가 내가 먼저 적은 기대 답과 같습니다. ' + FIX_LOOP,
              H('설비 하나의 구성 요소별 센서를 조회한다',
                '랩 DB의 그래프, `입력/schema.json`의 관계 방향, 「기대 답과 실제 결과」 표',
                '조회만 한다(그래프를 바꾸지 않는다). 한계가 없는 값을 0으로 보이지 않는다.',
                '조회문과 Table 결과',
                '고른 설비 하나로 실행해 원자료 행과 하나씩 대조한다'),
              'Browser에서 결과/query.cypher의 조회 실행'),
            S('구현 ③ 같은 물리량 센서 묶음 조회', '④ ~ ⑥ 구현 · 대조 · 고침',
              '물리량 하나를 받아 태그 이름이 달라도 그 물리량을 재는 센서를 설비마다 모으는 조회를 더하고 실행합니다.',
              '물리량을 무엇으로 받을지(이름 · ID), 결과에 설비 · 태그 · 단위 가운데 무엇을 함께 돌려줄지 정합니다.',
              '고른 물리량 하나의 센서 묶음이 내가 먼저 적은 기대 답과 같습니다. ' + FIX_LOOP,
              H('태그 이름이 달라도 같은 물리량을 재는 센서를 모아 조회한다',
                '랩 DB의 그래프, `입력/schema.json`의 관계 방향, 「기대 답과 실제 결과」 표',
                '조회만 한다(그래프를 바꾸지 않는다).',
                '조회문과 Table 결과',
                '고른 물리량 하나로 실행해 원자료 행과 하나씩 대조하고, 다른 물리량으로도 한 번 실행한다'),
              'Browser에서 결과/query.cypher의 조회 실행'),
            S('구현 ④ 부품의 사용 설비 조회', '④ ~ ⑥ 구현 · 대조 · 고침',
              '품번이나 표기 하나를 받아 그 부품을 쓰는 설비 · 구성 요소를 돌려주는 조회를 더하고 실행합니다.',
              '다른 표기 · 원자료에 없는 품번으로 물었을 때 무엇을 돌려줄지(빈 결과와 미확인을 어떻게 구별할지) 정합니다.',
              '공용 부품의 사용 설비가 기대 답과 같고, 다른 표기로 물은 결과가 정식 품번과 같으며, 없는 품번의 결과가 구별됩니다. ' + FIX_LOOP,
              H('부품 하나를 쓰는 설비와 구성 요소를 조회한다',
                '랩 DB의 그래프, `입력/graph.json`의 부품 속성, 「기대 답과 실제 결과」 표',
                '조회만 한다. 없는 품번에 값을 지어내지 않는다.',
                '조회문과 세 가지 물음(공용 부품 · 다른 표기 · 없는 품번)의 Table 결과',
                '세 가지 물음을 실행해 기대 답과 나란히 놓는다'),
              'Browser에서 결과/query.cypher의 조회 실행')]
    s_portal = S('포털 지식 지도와 비교', '⑤ 대조',
                 '포털 지식 지도에서 설비 → 쿨러 → 센서를 따라가고, 랩 DB에서 같은 역할을 하는 대상의 ID와 관계의 시작 · 끝을 `결과/검증_기록.md`에 나란히 적습니다. 포털을 열 수 없으면 이 단계는 미확인으로 남깁니다.',
                 '어디서 같고 어디서 다른지, 다른 곳은 어느 쪽 설계에서 온 차이인지 내 말로 적습니다.',
                 '설비 · 쿨러 · 센서마다 두 쪽의 ID와 관계 방향이 표에 있고, 다른 곳의 까닭을 말할 수 있습니다.',
                 H('내 그래프와 포털 지식 지도의 식별자 · 관계 방향을 견준다',
                   '포털 지식 지도 화면, 8단계 조회 결과, `입력/schema.json`',
                   '포털 DB에 접속하거나 포털 자료를 랩 DB에 넣지 않는다. 같은지 다른지는 화면과 조회 결과로만 적는다.',
                   '「대상 · 포털의 ID와 관계 방향 · 내 그래프의 ID와 관계 방향 · 같음/다름 · 다른 까닭」 표',
                   '표의 줄마다 포털 화면과 내 조회 결과를 다시 열어 같은 내용인지 본다'))
    reopen_step = 9 if practical else 10   # 부품 조회 단계
    s_save = S('저장하고 다시 열기', '⑦ 저장 · 다시 열기',
               f'적재 · 수정 · 조회 파일과 검증 기록을 저장하고, VS Code에서 폴더를 닫았다 다시 연 뒤 랩 DB를 다시 켜고 {reopen_step}단계 조회를 다시 실행합니다. 기록 끝에 기준일 · 수정본 날짜 · 저장 시점 · 확인하지 못한 점을 적습니다.',
               '확인하지 못한 점과 남은 확인 사항으로 무엇을 남길지 정합니다.',
               f'다시 연 뒤에도 {reopen_step}단계 조회 결과가 같습니다. `결과/`에 적재 · 수정 · 조회 파일과 검증 기록이 있습니다.',
               cmd='python lab_db.py')
    if practical:
        steps = [s_tree, s_db, s_look, s_req, s_plan, s_load, s_again, *query_steps, s_change, s_save]
    else:
        steps = [s_tree, s_db, s_look, s_req, s_plan, s_load, s_again, *query_steps, s_change, s_portal, s_save]
    user = ('이 답은 보전 · 구매 담당이 지금 가동하는 설비의 예비품 수요와 공급사별 조건을 볼 때 씁니다. 고르는 것은 구매 담당입니다.' if practical else
            '이 답은 보전팀이 지금 가동하는 설비의 예비품 준비를 정할 때 씁니다.')
    questions = (['세 설비가 함께 쓰는 펌프 축 씰 키트를 어느 설비 · 구성 요소에서 쓰고, 기준일의 세 공급 조건(승인 여부 · 단가 · 불량률 · 납기)은 무엇이며 각 값은 어느 파일 · 어느 날짜 자료에서 왔는가?',
                  '이름이 비슷한 다른 품번, 예전 품번이나 다른 표기, 원자료에 없는 품번으로 물으면 결과가 서로 구별되는가? 비승인 공급사는 승인 상태와 함께 구별되는가?',
                  '견적 납기와 지난 입고의 실측 납기는 공급사별로 얼마나 다른가?',
                  '수정본을 반영한 뒤에도 같은 ID가 유지되고, 같은 적재를 다시 실행해도 대상과 관계가 늘지 않는가?'] if practical else
                 ['설비별로 어떤 구성 요소에 어떤 센서 · 계산값 · 설정값이 붙어 있고, 각 센서의 물리량 · 단위 · 한계는 무엇인가? 태그 이름이 달라도 같은 물리량을 재는 센서를 함께 찾을 수 있는가?',
                  '교체 부품별로 그 부품을 쓰는 설비와 구성 요소는 무엇인가? 다른 표기로 적힌 품번이나 원자료에 없는 품번으로 물으면 결과가 어떻게 구별되는가?',
                  '수정본을 반영한 뒤에도 같은 ID가 유지되고, 같은 적재를 다시 실행해도 대상과 관계가 늘지 않는가?',
                  '포털 지식 지도에서 같은 대상을 찾아보면 내 그래프와 식별자 · 관계 방향이 어디서 같고 어디서 다른가?'])
    decide = [('시점과 상태', '수정본에서 상태가 바뀐 설비를 그래프에 어떻게 반영하고, 「지금 가동하는 설비」를 묻는 답에 어떻게 드러낼지(답에서 빠지는지, 상태와 함께 보이는지)')]
    if practical:
        decide.append(('세는 법', '나눠 들어온 발주의 실측 납기를 어느 입고로 셀지, 아직 다 들어오지 않은 발주를 어떻게 둘지'))
    outside = (['공급사를 고르거나 점수 · 순위를 매기는 일'] if practical else ['공급 조건 · 입고 이력의 적재와 조회']) + \
              ['모델의 종류 · 속성 · 관계 정의를 새로 바꾸는 일(이상한 곳은 `결과/검증_기록.md`에 적습니다)', '포털 DB에 접속하거나 포털 자료를 랩 DB에 넣는 일']
    cases = (['세 설비가 함께 쓰는 부품', '비슷한 이름의 다른 품번', '예전 품번 · 다른 표기', '원자료에 없는 품번', '비승인 · 조건이 붙은 공급사', '공급사 이름 표기(견적표 · 승인 목록 · 입고 이력)',
              '나눠 들어온 입고와 아직 다 들어오지 않은 발주'] if practical else
             ['설비별 구성 요소 · 센서 개수', '태그 이름이 달라도 같은 물리량', '한계 방향과 한계 없음', '설비에 바로 붙은 센서', '공용 부품과 전용 부품', '다른 표기 · 없는 품번']) + \
            ['수정본의 이름 변경 · 상태 변경 · 값 보완 · 줄 삭제가 바꾸는 그래프의 대상 · 관계', '반영 뒤 원자료와 다시 센 개수 · 값(「삭제」 줄이 걸린 설비 포함)',
             '같은 적재 두 번 · 같은 수정 두 번']
    my_model = ('내 모델을 쓸 때: 제공 입력은 그대로 두고 내 `schema.json` · `graph.json`을 `결과/내_모델/`에 복사해 씁니다. 만든 날짜 · 질문 · 파일 형식 · ID가 이번 입력과 맞는지 먼저 보고, '
                '관계 이름이나 방향이 다르면 내 모델의 정의로 조회합니다. 내 모델이 없어도 제공된 모델로 끝까지 할 수 있습니다.')
    after = AFTER_LAB[course]
    save = ('적재 · 수정 · 조회 파일과 `검증_기록.md`를 함께 보관합니다. 기록에는 반영한 자료의 기준일과 수정본 날짜를 적습니다. '
            + (f'다음 실습 「{after}」는 이 설비 모델의 ID에 작업 절차와 판단 조건을 잇습니다. 그 실습도 제공된 모델로 시작할 수 있으므로 이 결과는 골라서 가져갑니다. ' if not practical else
               f'다음 실습 「{after}」는 제공된 자료로 시작하므로 이 결과는 참고로 보관합니다. ') + USB)
    record = req_template('실습 확인 기록', GRAPH_COUNTS + (
        '## 견적 납기와 실측 납기\n\n| 공급사 | 견적 납기(일) | 센 발주 수 | 실측 납기(평균 · 최대) | 근거(파일 · 줄) |\n|---|---|---|---|---|\n| | | | | |\n\n' if practical else
        '## 포털 지식 지도와 비교\n\n| 대상 | 포털의 ID · 관계 방향 | 내 그래프의 ID · 관계 방향 | 같음 · 다름 | 다른 까닭 |\n|---|---|---|---|---|\n| | | | | |\n\n'))
    record = record.replace('## 사용할 자료와 기준일\n\n', '## 사용한 입력과 랩 DB\n\n- 사용한 모델(제공된 모델 · 내 모델):\n- 랩 DB 주소(인증값 제외):\n- 기준일 · 수정본 날짜:\n\n')
    record = record.replace('- 기준일:\n', '- 기준일 · 수정본 날짜:\n')
    design = design_lab(course)
    return dict(
        title=title, rec='결과/검증_기록.md', readonly='`입력/`(원자료 · 수정본 포함)이', decide_step=3,
        goal=[('「설비·부품·공급 정보를 연결하는 온톨로지 설계하기」에서는 부품마다 쓰는 설비와 공급사별 조건을 모델에 넣었습니다. ' if practical else
               '「현장 정보를 체계화하는 온톨로지 직접 설계하기」에서는 설비 · 센서 · 부품을 종류 · 속성 · 관계로 정의해 모델을 만들었습니다. ')
              + f'이번에는 제공된 {model}(또는 내가 만든 모델)을 이 폴더 전용 랩 DB(그래프 DB)에 적재하고, 질문마다 조회문을 만들어 원자료와 대조합니다. 스키마의 ID와 관계 방향이 그래프의 노드 · 관계로 어떻게 옮겨지는지 직접 봅니다.',
              ('조회가 돌려준 공급 조건을 구매 담당이 믿고 쓰려면 승인되지 않은 공급사가 승인된 것처럼 섞이지 않고 값마다 출처가 따라와야 합니다. 이 조회는 공급사를 골라 주지 않습니다. 고르는 사람이 볼 정보를 돌려줍니다. ' if practical else '')
              + '그래프에 넣은 자료는 한 번으로 끝나지 않습니다. 수정본이 들어오면 전체를 지우고 다시 넣지 않고 필요한 대상만 고쳐야 다른 곳에서 쓰던 ID와 연결이 그대로 남고, 같은 적재를 다시 실행해도 대상이 늘지 않아야 믿고 다시 돌릴 수 있습니다.',
              STAGE_LINE.format(what='구현과 검증 — 설계한 모델을 그래프 DB에 옮기고, 질문에 실제로 답하는지 원자료와 대조하는 일 — ')],
        make=('만들 것: 모델을 랩 DB에 넣는 적재문(또는 적재 코드), 질문별 조회문, 수정본을 반영하는 수정문, '
              + ('입고 이력으로 실측 납기를 세는 코드, ' if practical else '') + '`결과/검증_기록.md`.'),
        start=[f'`입력/schema.json` · `입력/graph.json` — 제공된 {model}. ' + (
                   '설비 7대 · 구성 요소 · 센서 · 부품 · 공급사와 그 연결이 들어 있고, 공급 조건마다 승인 여부 · 단가 · 불량률 · 납기와 구매 기준서 7.4에 걸리는 쌍의 입고 검사 정보가 붙어 있습니다.' if practical else
                   '설비 7대 · 구성 요소 · 센서 · 물리량 · 부품과 그 연결이 들어 있습니다.'),
               f'`입력/자료/` — 그 모델의 원자료(기준일 {D.REF_DATE}). `{change_dir}` — 기준일 뒤 담당자들이 고친 줄만 모은 수정본.',
               '`입력/요구사항.md` · `입력/자료_검토.md` — 제공된 모델이 답하는 질문과 자료 처리 근거.',
               '`lab_db.py` — 이 폴더 전용 랩 DB를 켜는 도구. `결과/` — 이번에 만든 것을 두는 자리(「제공 빈 틀」 `검증_기록.md`).',
               RULES_LINE, my_model],
        tools=TOOLS_GRAPH[course], user=user, questions=questions, decide=decide, outside=outside,
        formats=[GRAPH_FORMAT], steps=steps, cases=cases,
        commands='python lab_db.py' + ('\npython 결과/<납기 코드 이름>.py' if practical else '') + '\n(적재 · 수정 · 조회문은 열린 Neo4j Browser에서 실행하거나, 만든 코드로 실행합니다)',
        done=('형식 검사나 실행 성공만으로 완료하지 않습니다. 질문마다 원자료에서 먼저 적은 기대 답과 실제 조회 결과가 맞고, 같은 적재 · 같은 수정을 다시 해도 개수가 같으며, '
              '「정한 것」마다 근거 줄과 그 선택으로 바뀌는 답을 설명할 수 있으면 완료입니다. 고친 점과 확인하지 못한 점은 `결과/검증_기록.md`에 짧게 남깁니다.'),
        save=save, reopen=f'{reopen_step}단계 조회 결과, `검증_기록.md`의 기준일 · 수정본 날짜 · 저장 시점 · 확인하지 못한 점',
        tree=tree(LAB4, [('.github/', 'Copilot 작업 규칙'), ('결과/', '이번에 만들 것(검증_기록.md 빈 틀)'),
                         ('입력/', f'제공된 {model} · 원자료(자료/) · 수정본(자료_변경분/) (읽기만)'), *GRAPH_TREE_TAIL]),
        guide_extra={1: f'<p>{OPEN_TERMINAL}</p><p>{inline(LAB_CONNECT)}</p><p><b>개수 조회</b> Browser 위쪽 입력 칸에 붙여 넣고 실행합니다.</p><pre>{html.escape(COUNT_QUERY)}</pre>',
                     2: f'<p>{OPEN_AI}</p>', 5: f'<p>{REVIEW_EDIT}</p>'},
        files={'결과/검증_기록.md': record,
               '결과/README.md': '적재문(또는 적재 코드), 수정문, 조회문, 검증_기록.md를 여기에 저장합니다. 내 모델을 쓰면 결과/내_모델/에 복사해 둡니다.\n다시 열 때는 랩 DB를 다시 켜고 검증_기록.md의 기준일 · 수정본 날짜와 조회 결과를 함께 봅니다.\n',
               '입력/README.md': f'제공된 {model}(schema.json · graph.json), 그 원자료(자료/), 기준일 뒤 수정본(자료_변경분/), 제공된 모델의 질문(요구사항.md)과 자료 처리 근거(자료_검토.md)입니다. 이 폴더는 읽기만 합니다.\n',
               '입력/요구사항.md': '# 제공된 모델이 답하는 질문\n\n' + '\n'.join('- ' + q for q in design['questions']) + '\n',
               '입력/자료_검토.md': provided_basis(practical)})


LABS = {3: design_lab, 4: graph_lab}


def main():
    provenance = json.loads((TOOLS/'capture-provenance.json').read_text(encoding='utf-8'))
    D.write_sources()
    for course, _ in COURSES:
        for branch in REFERENCE_BRANCHES[course]:
            schema, graph = reference_model(course == '실전반', branch)
            dest = TEACHER/course/BRANCH_DIRS[branch]
            dump(dest/'schema.json', schema); dump(dest/'graph.json', graph)
    write(TEACHER/'실전반/README.md', PRACTICAL_BRANCH_README)
    base_schema, base_graph = reference_model()
    catalog = []
    for course, slug in COURSES:
        practical = course == '실전반'
        for number, name in [(3, LAB3), (4, LAB4)]:
            folder = OUT/course/'실습/02회차/랩'/name
            L = LABS[number](course)
            photos = student_photos(folder, provenance, [s['name'] for s in L['steps']])
            reset_generated(folder)
            for sub in ['입력', '결과']:
                (folder/sub).mkdir(parents=True, exist_ok=True)
            if number == 3:
                if practical:   # 통합반 실습3의 자료/(D.SOURCE)는 맨 앞 D.write_sources()가 쓴다
                    D.write_sources(folder/'자료', practical=True)
                    # 제공된 설비 · 부품 모델. 갈래 표시는 제작용이라 학생 입력에 두지 않는다
                    dump(folder/'입력/schema.json', student_schema(base_schema)); dump(folder/'입력/graph.json', base_graph)
                    (folder/'입력/관계그림.json').unlink(missing_ok=True)   # START가 쓰지 않는 파일(K-24)
                elif not (folder/'입력/관계그림.json').is_file():
                    raise FileNotFoundError('1회차 관계 그림 입력이 없습니다: ' + str(folder))
            else:
                shutil.copy2(TOOLS/'lab_db.py', folder/'lab_db.py')
                schema, graph = reference_model(practical, LAB4_INPUT_BRANCH[course])
                dump(folder/'입력/schema.json', student_schema(schema)); dump(folder/'입력/graph.json', graph)
                D.write_sources(folder/'입력/자료', practical)
                D.write_changes(folder/'입력/자료_변경분'/f'{D.CHANGE_DATE}_수정본', practical)
            build_lab(folder, L, photos)
            pack(folder)
            catalog.append(entry(f'{slug}-02-' + ('ontology' if number == 3 else 'graph'), course, '온라인 02회차', L['title'], VERSION, folder))
    register(catalog)
    print('두 과정 설계·구현 시작본 4개, ZIP 4개 생성')


if __name__ == '__main__':
    main()
