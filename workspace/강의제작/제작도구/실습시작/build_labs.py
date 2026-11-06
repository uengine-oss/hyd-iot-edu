"""온라인 2회차 실습3 · 4(두 과정) 학생 폴더 · ZIP · 패키지 목록과 강사 참조 모델(reference/)을 만든다.

2회차 실습3 · 4 원자료는 data_session2.py가 만든다(가상 사례, 고정 시드). 네 랩은 단계 랩 틀(design_lab · graph_lab → build_lab)로 만들고,
단계 하나가 START.md 「진행 단계」 한 줄과 가이드(랩 폴더 밖 `<랩>_guide.html`) 한 절이 된다. 틀은 lab_frame.py.
reference_model()의 반환 형식(schema dict, {'nodes':[{labels,props}], 'rels':[{type,a,b,props}]})은
3회차 랩(build_judgement_labs · build_session3_documents)이 import하므로 유지한다.
"""
from pathlib import Path
import ast
import csv
import hashlib
import html
import json
import re
import io
import shutil

import data_session2 as D
import lab_frame as F
from lab_package import GUIDE_CSS as CSS, entry, pack, register   # pack은 build_common · build_session3_*도 여기서 가져간다(build_judgement_labs는 lab_package에서 직접)

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT/'workspace/강의제작/산출물'
TOOLS = Path(__file__).resolve().parent
TEACHER = TOOLS/'reference'
COURSES = [('통합반','integrated'),('실전반','practical')]
LAB3 = '02일차_실습3_온톨로지설계'
LAB4 = '02일차_실습4_그래프구현과검증'
VERSION = '2026-11-05-lab-v16'
LAB_VERSION = {'integrated-02-ontology': '2026-11-06-lab-v18', 'integrated-02-graph': '2026-11-06-lab-v17-terms'}   # 통합반 실습3 v17은 학생 몫을 판단 규칙 + 규칙 밖 행으로 줄인 판(리허설 50L 뒤), v18과 실습4 terms는 클래스 정의 · 지식 그래프 이름을 2회차 이론과 맞춘 판

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

def resolve_part(text,model,key,parts,cross,link=True):
    """교체부품 칸 → 사내 품번. 품번·교차표로 풀고, 품명만 있거나 비어 있으면 같은 모델의 쓰는곳으로 푼다(메모 2·5절).
    link=False(통합반 갈래 C)면 품번 · 교차표로 풀리지 않는 칸은 잇지 않는다(None)."""
    t=text.strip()
    m=re.search(r'\((P-[A-Z0-9-]+)\)',t)
    if m:return m.group(1)
    if t in parts:return t
    hits=sorted({c['사내품번'] for c in cross if c['다른표기']==t})
    if len(hits)==1:return hits[0]
    if not link:return None
    cand=[p for p,row in parts.items() if model_match(model,row['적용모델']) and NAME_ALIAS.get(row['쓰는곳'],'pump-a' if row['쓰는곳']=='주 펌프 A' else ('pump' if row['쓰는곳']=='펌프' else None))==key]
    if len(cand)==1:return cand[0]
    if not t and not cand:return None
    raise ValueError(f'교체부품을 풀지 못함: {text!r} {model} {key} 후보={cand}')

def number(text):
    m=re.match(r'\s*(-?\d+(?:\.\d+)?)',text or '')
    return float(m.group(1)) if m else None

def blank_unit_basis(folder=None):
    """단위 칸이 빈 센서 줄마다 그 단위의 근거 줄: 같은 모델(설비 대장) · 같은 태그로 단위가 적힌 줄 가운데 정상값 · 한계 · 한계구분까지 같은 줄.
    근거가 없거나 단위가 갈리면 멈춘다 — 강사 참조는 단위를 짐작하지 않는다(작업 규칙 3 · 4, 통합 실습3 7단계).
    반환: {센서 id: {'line': 빈 줄 번호, 'basis': [근거 줄 번호 …], 'unit': 단위}}. 줄 번호는 편집기에 보이는 번호(머리줄이 1행)."""
    model={a['설비코드']:a['모델'] for a in rows('설비_대장.csv',folder) if a['상태']!='코드 통합'}
    sensors=list(enumerate(rows('센서_목록.csv',folder),2))
    out={}
    for line,s in sensors:
        if s['단위']:continue
        same=[(n,r) for n,r in sensors if r['단위'] and r['태그']==s['태그'] and model[r['설비코드']]==model[s['설비코드']]
              and (r['정상값'],r['한계'],r['한계구분'])==(s['정상값'],s['한계'],s['한계구분'])]
        units={r['단위'] for _,r in same}
        if len(units)!=1:raise ValueError(f'{s["설비코드"]}:{s["태그"]} 센서_목록.csv {line}행: 단위 칸이 비었고 근거 줄이 없거나 단위가 갈림 {sorted(units)} — 미확인으로 둘지 정한다')
        out[s['설비코드']+':'+s['태그']]={'line':line,'basis':[n for n,_ in same],'unit':units.pop()}
    return out

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
        pid=resolve_part(c['교체부품'],model,key,parts,cross,link=branch!='C')
        if pid:rel('USES_PART',cid,pid,source_text=c['교체부품'] or '(빈칸: 같은 모델 공용 근거)')
    seen=set();basis=blank_unit_basis()
    for s in rows('센서_목록.csv'):
        aid=s['설비코드'];sid=aid+':'+s['태그']
        if sid in seen:continue                 # 점검표에서 다시 옮겨 적은 같은 센서
        seen.add(sid);model=models[aid]
        q='quantity:'+WHAT_ALIAS[s['재는것']];qunit=D.QUANTITIES[q][1]
        raw=s['단위'] or basis[sid]['unit'];unit,factor=UNIT.get(raw,(raw,1))   # 빈 단위 칸은 근거 줄의 단위로만(blank_unit_basis)
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

# 강사 참조 갈래. 통합반 B = 같은 제조사 품번의 다른 사내 품번을 SAME_ITEM_AS로 잇는다. C = A(따로)에서 빈 칸 · 품명만 적힌 교체부품 칸을 예비품 목록으로 잇지 않는다.
# 실전반 A = 조건부 승인을 승인으로 봄 + PR-07 7.4는 SCM 등록대로(갈래 ㄱ, 빈 조건 = 조건 없음). B = 조건부 승인을 비승인으로(ㄱ).
# 실전반 ㄴ · ㄷ = A에 더해 7.4(불량률 기준 초과 승인 공급사)를 ㄴ 정보로 붙임 · ㄷ 미결(확인 요청)로 표시. 실전반의 설비·부품 부분은 통합반 A와 같다.
# 실습4 갈래는 실습3 갈래와 따로, 실습4 입력/ 모델(LAB4_INPUT_BRANCH) 위에서 돌린다(verify_reference.py):
# 통합반 수정본 갈래(「시점과 상태」) 남김 = 불용 설비를 상태로 남김 · 삭제 = 불용 설비를 전용 하위 대상(구성 요소 · 센서)과 함께 지움.
# 실전반 조회 갈래(「쓰는 사람에 따라 갈리는 답」) ㄱ = 승인 여부 · 단가 · 불량률 · 납기만 돌려줌 · ㄴ = PR-07 7.4 정보(입고 검사 · 비교 가산 비용)를 함께 돌려줌.
REFERENCE_BRANCHES = {'통합반': ['A', 'B', 'C'], '실전반': ['A', 'B', 'ㄴ', 'ㄷ']}
BRANCH_DIRS = {'A': '', 'B': '갈래B', 'C': '갈래C', 'ㄴ': '갈래ㄴ', 'ㄷ': '갈래ㄷ'}
LAB4_INPUT_BRANCH = {'통합반': 'A', '실전반': 'ㄴ'}     # 실습4 입력/의 앞 단계 완성 모델
LAB4_CHANGE_BRANCHES = ['남김', '삭제']                  # 통합반만(실전반 실습4 행에는 수정본 반영이 없다)
LAB4_QUERY_BRANCHES = {'ㄱ': 'A', 'ㄴ': 'ㄴ'}            # 실전반 실습4 조회 갈래 → 같은 열을 내는 실습3 기대 답의 키
APPROVED_STATUS = {'A': ('승인', '조건부 승인'), 'B': ('승인',), 'ㄴ': ('승인', '조건부 승인'), 'ㄷ': ('승인', '조건부 승인')}
PR74_LINE = next(i for i, x in enumerate(D.pr07_excerpt().splitlines(), 1) if '전수 검사 비용' in x)   # 발췌에서 7.4 마지막 줄
PR74_SOURCE = D.line_ref(D.PR07_FILE, PR74_LINE) + '(7.4)'
PRACTICAL_BRANCH_README = ('# 실전반 강사 참조 갈래\n\n'
    '실습3: 루트 = 갈래 A(조건부 승인 = 승인) · PR-07 7.4 갈래 ㄱ(SCM 등록대로) / `갈래B/` = 조건부 승인 = 비승인 · ㄱ / '
    '`갈래ㄴ/` = A · 7.4를 정보로 표시(실습4 `입력/` 모델) / `갈래ㄷ/` = A · 7.4 미결(확인 요청). 기대 답은 `기대답.json`의 같은 키(A · B · ㄴ · ㄷ).\n\n'
    '실습3 「학생이 정할 것」과 갈래: 「조건이 붙은 승인」 = A(승인) · B(비승인), 「빈 값의 뜻」(SCM 등록의 빈 조건 칸) = ㄱ(조건 없음) · ㄷ(미결), '
    '「쓰는 사람에 따라 갈리는 답」(PR-07 7.4 정보) = ㄱ(SCM 등록만) · ㄴ(7.4 정보 함께). 확인 사례 「출처마다 다른 승인 정보」는 결정 지점이 아니다 — '
    f'`{D.PR07_FILE}` 7.3({next(i for i, x in enumerate(D.pr07_excerpt().splitlines(), 1) if "SCM 구매 포털의 등록을 따른다" in x)}행) 「공급사의 승인 여부는 SCM 구매 포털의 등록을 따른다」가 답을 주므로 모든 갈래가 `{D.AVL_FILE}`와 기준일을 따른다'
    '(견적표 「승인공급사」 칸과 어긋나는 예: A정밀 · P-ACC-BLD — 견적표 「예」, SCM 등록 유효기한 2026-08-31 경과). '
    '모든 갈래의 SUPPLIES에 값의 출처(quote_source · approval_source · as_of — 실습3 9단계)가 있고, 실습4 `입력/` 모델에 그대로 간다.\n\n'
    '실습4 조회 갈래(「쓰는 사람에 따라 갈리는 답」): `갈래ㄴ/` 모델(실습4 `입력/`) 위에서 ㄱ = 승인 여부 · 단가 · 불량률 · 납기만 돌려줌(기대 답 `A`의 공급 조건 열) · '
    'ㄴ = PR-07 7.4 정보를 함께 돌려줌(기대 답 `ㄴ`). 실행 결과는 `../session2_검증.json`의 `offline` → `실전반` → `실습4`와 `neo4j` → `실전반` → `실습4`.\n')

def student_schema(schema):
    """갈래 표시는 제작용이라 학생 입력에 두지 않는다."""
    return {k: v for k, v in schema.items() if k != 'branch'}

def supply_part(nodes,rels,branch='A'):
    """실습3 「값마다 출처 남기기」까지 한 완성 상태: 견적 값은 쓴 견적 줄(quote_source), 승인 값은 SCM 등록 줄(approval_source), 판단 시점은 기준일(as_of)."""
    parts={p['품번']:p for p in rows('예비품_목록.csv')}
    avl={(r['공급사'],r['품번']):(line,r) for line,r in enumerate(rows(D.AVL_FILE),2)}
    best={}
    for line,q in enumerate(rows(D.QUOTE_FILE),2):
        pid=q['품번'] if q['품번'] in parts else next(p for p,row in parts.items() if row['품명']==q['품번'])
        sup=next(k for k in D.SUPPLIERS if q['공급사'].startswith(k))
        if q['유효기한']<D.REF_DATE:continue          # 만료 견적은 조건으로 쓰지 않는다
        prev=best.get((sup,pid))
        if prev is None or q['견적일']>prev[1]['견적일']:best[(sup,pid)]=(line,q)
    for sup in sorted({s for s,_ in best}):nodes.append({'labels':['Supplier'],'props':{'id':'supplier:'+sup,'name':sup}})
    for (sup,pid),(line,q) in sorted(best.items()):
        a_line,a=avl.get((sup,pid),(None,None))
        status=a['승인상태'] if a else '미등록'
        if a and a['유효기한'] and a['유효기한']<D.REF_DATE:status='유효기한 경과'
        ok=status in APPROVED_STATUS[branch]
        condition=(a['조건'] if a else '') or None
        fail=q['불량률'];lead=q['납기(일)']
        defect=float(fail.rstrip('%'))/100 if fail.endswith('%') else float(fail)
        props=dict(approved=ok,approval_status=status,condition=condition,
            price_manwon=float(q['단가(만원)']),defect_rate=defect,defect_rate_original=None if re.fullmatch(r'\d+(\.\d+)?',fail) else fail,
            lead_days=int(lead[:-1])*7 if lead.endswith('주') else int(lead),lead_days_original=None if lead.isdigit() else lead,   # 실습3 8단계: 바꾼 값은 원래 표기를 남긴다
            min_order_qty=int(q['최소주문수량']),
            supplier_part_no=q['공급사품번'],quote_date=q['견적일'],valid_until=q['유효기한'],
            quote_source=D.line_ref(D.QUOTE_FILE,line),approval_source=D.line_ref(D.AVL_FILE,a_line) if a else None,as_of=D.REF_DATE)
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
        props={'approved':'boolean','approval_status':'string','condition':'string','price_manwon':'number','defect_rate':'number','defect_rate_original':'string',
               'lead_days':'integer','lead_days_original':'string','min_order_qty':'integer','supplier_part_no':'string','quote_date':'string','valid_until':'string',
               'quote_source':'string','approval_source':'string','as_of':'string'}
        if branch=='ㄴ':props.update(inspection='string',compare_extra_manwon='number',rule_source='string')
        if branch=='ㄷ':props.update(pending_check='string')
        relation_defs['SUPPLIES']={'from':'Supplier','to':'Part','cardinality':'N:M','note':'공급사·품번마다 유효한 최신 견적 하나','properties':props}
    constraints=['id는 전체 그래프에서 고유. 구성요소·센서는 설비코드:이름, 부품은 사내 품번','이관 기록(코드 통합)·철거 실물·점검표 중복 행은 대상을 새로 만들지 않는다',
                 'limit 생략은 0과 다르다. normal 생략은 미확인','단위는 Quantity 기준 단위로 맞추고 바꾼 경우 source_unit을 남긴다']
    if supply:constraints+=['승인 여부는 승인공급사_목록(SCM 등록)과 기준일로 정한다','만료 견적은 SUPPLIES로 쓰지 않는다',
                            '공급사 이름은 승인공급사_목록의 이름이다(견적표의 공급사 칸은 그 이름으로 시작한다)',
                            '단가는 만원, 불량률은 0~1 비율, 납기는 일로 맞추고, 바꾼 불량률 · 납기는 원래 표기를 defect_rate_original · lead_days_original로 남긴다',
                            f'값마다 출처를 남긴다: quote_source = 쓴 견적의 {D.QUOTE_FILE} 줄, approval_source = {D.AVL_FILE}의 등록 줄, as_of = 기준일']
    # 실습4 입력 모델(갈래 ㄴ)의 schema가 학생에게 간다 — 「함께 남긴다」처럼 실습4 결정(돌려줄지)을 미리 정하는 말 없이, 값이 어디서 왔는지만 적는다(코딩랩.md K-4).
    if supply and branch=='ㄴ':constraints.append(f'inspection · compare_extra_manwon · rule_source는 구매 기준서 PR-07 7.4 문장(rule_source 줄)에서 온 값이고, 그 절에 걸리는 승인 공급사 쌍(불량률 {D.PR74_RATE_PCT} % 초과)에만 있다')
    if supply and branch=='ㄷ':constraints.append('SCM 등록에 조건이 없는데 구매 기준서 PR-07 7.4에 걸리는 승인 공급사 쌍은 pending_check로 확인 필요를 남긴다(approved는 SCM 등록대로)')
    return {'classes':definitions,'relations':relation_defs,'identity':'id는 전체 그래프에서 고유.','branch':branch,'constraints':constraints}

def reference_model(supply=False,branch='A'):
    """원자료끼리 대조한 근거로 만든 강사 참조 모델(반환 형식 유지). 갈래는 REFERENCE_BRANCHES 위 주석."""
    nodes,rels=base_graph('A' if supply else branch)
    if supply:supply_part(nodes,rels,branch)
    return schema_for(supply,branch),{'nodes':nodes,'rels':rels}

def page(title,intro,sections,blocks=False):
    """blocks=True면 복사 블록(lab_frame.block)의 모양과 복사 단추 스크립트를 함께 싣는다."""
    nav=''.join(f'<a href="#s{i}">{i:02d} {html.escape(t)}</a>' for i,(t,_) in enumerate(sections,1))
    body=''.join(f'<section id="s{i}"><h2>{i:02d} {html.escape(t)}</h2>{content}</section>' for i,(t,content) in enumerate(sections,1))
    style,script=(F.STEP_CSS,F.COPY_JS) if blocks else ('','')
    return f'<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>{CSS}{style}</style><main><small>HYD · 실습 가이드</small><h1>{title}</h1><p>{intro}</p><nav>{nav}</nav>{body}</main>{script}</html>'

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

# RULES는 아직 단계 랩 틀로 바뀌지 않은 3회차 랩(build_session3_documents · build_session3_whatif)이 import한다. 단계 랩의 작업 규칙은 lab_frame.STEP_RULES.

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

def graph_format(change):
    """실습4 결과 형식. 수정본 반영이 있는 랩(통합반)만 수정문 줄을 둔다."""
    return ('## 결과 형식\n\n`결과/`에 아래 파일을 둡니다. 파일 안에서 무엇을 어떤 문장으로 쓸지는 직접 정합니다.\n\n'
            '- `결과/load.cypher`(또는 적재 코드): 모델 파일의 대상과 관계를 랩 DB에 넣습니다. 같은 파일을 다시 실행해도 됩니다.\n'
            + ('- `결과/update.cypher`(또는 수정 코드): 수정본의 줄을 이미 넣은 그래프에 반영합니다.\n' if change else '')
            + '- `결과/query.cypher`: 질문마다 조회문 하나. 조회문 위에 어느 질문의 조회인지 주석(`// 질문 1`)으로 적습니다.\n'
            '- `결과/검증_기록.md`: 「제공 빈 틀」의 칸대로 채웁니다.\n')

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


def graph_counts(change):
    """실습4 확인 기록의 개수 표. 수정본 반영이 있는 랩(통합반)만 수정본 두 줄을 둔다."""
    return ('## 적재 · 다시 적재' + (' · 수정본' if change else '') + '\n\n| 단계 | 노드 수 | 관계 수 | 확인한 것 |\n|---|---|---|---|\n'
            '| 첫 적재 | | | |\n| 같은 적재 다시 | | | |\n' + ('| 수정본 반영 | | | |\n| 같은 수정본 다시 | | | |\n' if change else '') + '\n')

# ───────────── 실습4(그래프 구현과 검증) — 두 과정 ─────────────
# 통합 실습4 12단계의 입력 = 포털 실습 「설비 지식의 구조와 연결 관계 탐색하기」에서 펼쳐 본 기준 지도(설비 HYD-01 → 오일 쿨러 → 센서 → 상태 변수).
# 랩은 포털 없이 돈다(코딩랩.md K-2) — 포털이 실제로 적재하는 main 시드와 포털 화면의 관계 이름에서 뽑아 가이드 그 단계에 표로 싣는다. 사진은 본 촬영 때 더한다.
PORTAL_SEED = 'it/neo4j/v2/instances.cypher'
PORTAL_LABELS = 'it/portal/www/enterprise.js'     # 화면의 관계 이름(RELATION_KO)
PORTAL_ASSET, PORTAL_COMPONENT = 'asset:hyd-01', 'comp:cooler'


def cypher_list(text):
    """시드의 Cypher 목록 글(작은따옴표 문자열 · 숫자 · null · true · false)을 파이썬 값으로."""
    words = {'null': 'None', 'true': 'True', 'false': 'False'}
    parts = re.split(r"('(?:[^'\\]|\\.)*')", text)
    return ast.literal_eval(''.join(x if x.startswith("'") else re.sub(r'\b(null|true|false)\b', lambda m: words[m.group(1)], x) for x in parts))


def portal_map():
    """포털 기준 지도의 대상 · 속성 · 관계. 시드의 UNWIND 문(MERGE 한 종류 + 그 문이 잇는 관계)을 그대로 읽는다."""
    from lab_package import system_root
    root = system_root()
    seed = (root/PORTAL_SEED).read_text(encoding='utf-8')
    ko = dict(re.findall(r"(\w+): '([^']*)'", re.search(r'const RELATION_KO = \{(.*?)\};', (root/PORTAL_LABELS).read_text(encoding='utf-8'), re.S).group(1)))
    nodes, rels = {}, []
    for label in ['Asset', 'Component', 'Sensor', 'StateVariable', 'Part']:
        m = re.search(r'UNWIND (\[\[[^;]*?\]\]) AS r\s+MERGE \((\w+):' + label + r' \{id: r\[0\]\}\)([^;]*);', seed)
        if not m:
            raise ValueError(f'{PORTAL_SEED}에서 {label}을 만드는 문을 찾지 못했습니다.')
        items, var, rest = cypher_list(m.group(1)), m.group(2), m.group(3)
        sets = [(k, int(i), suffix) for k, i, suffix in re.findall(var + r"\.(\w+) = r\[(\d+)\](?: \+ '([^']*)')?", rest)]
        ends = {v: int(i) for v, i in re.findall(r'\((\w+):\w+ \{id: r\[(\d+)\]\}\)', rest)}
        each = re.search(r'UNWIND (\[[^\]]*\]) AS (\w+)', rest)
        for row in items:
            nodes[row[0]] = {'label': label, **{k: (row[i] + suffix if suffix else row[i]) for k, i, suffix in sets}}
            for a, rtype, b in re.findall(r'MERGE \((\w+)\)-\[:(\w+)\]->\((\w+)\)', rest):
                if each and a not in ends and a != var:           # UNWIND 목록의 대상마다(설비 → 구성 요소)
                    rels += [(x, rtype, row[0]) for x in cypher_list(each.group(1))]
                else:
                    rels.append((row[0] if a == var else row[ends[a]], rtype, row[0] if b == var else row[ends[b]]))
    return nodes, rels, ko


def portal_table():
    """통합 실습4 12단계 가이드의 기준 지도 표. 포털 지식 지도는 고른 설비 하나만 그린다(main `it/neo4j/templates/t0_graph_nodes.cypher` ·
    `t0_graph_edges.cypher`의 설비 조건) — 그래서 HYD-01에서 오일 쿨러를 펼쳐 본 길(설비 → 쿨러 → 센서 → 상태 변수)의 관계만 싣고,
    다른 설비가 같은 쿨러에 이어지는 것은 포털 실습에서 설비를 바꿔 본 한 줄로, 길 밖의 관계(교체 부품 · 증상 · 데이터 출처 등)는 싣지 않았다고 적는다."""
    nodes, rels, ko = portal_map()
    sensors = list(dict.fromkeys(b for a, t, b in rels if a == PORTAL_COMPONENT and t == 'MONITORED_BY'))   # 시드 순서(유온 센서가 먼저)
    path = [PORTAL_ASSET, PORTAL_COMPONENT, *sensors, *dict.fromkeys(b for s in sensors for a, t, b in rels if a == s and t == 'OBSERVES')]
    on_path = [(a, t, b) for a, t, b in rels if a in path and b in path]      # 다른 설비(HYD-02 · 03)는 길에 없어 함께 빠진다
    switched = 'asset:hyd-02'                                                   # 포털 실습에서 설비 칸을 바꿔 본 설비(대본 05_실습_지식지도탐색 3절)
    if (switched, 'HAS_COMPONENT', PORTAL_COMPONENT) not in rels:
        raise ValueError(f'{PORTAL_SEED}에서 {switched} → {PORTAL_COMPONENT}(HAS_COMPONENT)를 찾지 못했습니다 — 가이드의 설비 바꾸기 문장을 다시 봅니다.')
    shown = {'Asset': ['code'], 'Component': ['name'], 'Sensor': ['tag'], 'StateVariable': ['name']}   # 이 단계는 식별자 · 방향을 견주므로 대상을 알아볼 값 하나만
    kind = {'Asset': '설비', 'Component': '구성 요소', 'Sensor': '센서', 'StateVariable': '상태 변수'}

    def value(v):
        return ' · '.join(v) if isinstance(v, list) else ('true' if v is True else 'false' if v is False else str(v))

    def links(i):
        out = []
        incoming = sorted({(t, a) for a, t, b in on_path if b == i})
        outgoing = sorted({(t, b) for a, t, b in on_path if a == i})
        for t, group in [(t, [a for tt, a in incoming if tt == t]) for t in dict.fromkeys(t for t, _ in incoming)]:
            out.append(f'들어오는 「{ko[t]}」({t}): ' + ' · '.join(f'<code>{html.escape(a)}</code> → 이것' for a in group))
        for t, group in [(t, [b for tt, b in outgoing if tt == t]) for t in dict.fromkeys(t for t, _ in outgoing)]:
            out.append(f'나가는 「{ko[t]}」({t}): ' + ' · '.join(f'이것 → <code>{html.escape(b)}</code>' for b in group))
        return '<br>'.join(out)
    rows_ = ''.join(f'<tr><td>{kind[nodes[i]["label"]]}</td><td><code>{html.escape(i)}</code></td>'
                    f'<td>{"<br>".join(f"<code>{k}</code> {html.escape(value(nodes[i][k]))}" for k in shown[nodes[i]["label"]] if nodes[i].get(k) is not None)}</td><td>{links(i)}</td></tr>'
                    for i in path)
    return ('<p><b>포털 기준 지도</b> 포털 실습에서 HYD-01의 오일 쿨러를 펼쳐 본 지식 지도 가운데 설비 → 쿨러 → 센서 → 상태 변수 길의 식별자 · 관계입니다. '
            '「 」는 화면의 관계 이름, 괄호는 저장된 이름, →는 방향(시작 → 끝)입니다.</p>'
            f'<table><tr><th>종류</th><th>식별자(id)</th><th>알아볼 값</th><th>관계와 방향</th></tr>{rows_}</table>'
            f'<p>포털 실습에서 본 것처럼 설비 칸을 {html.escape(nodes[switched]["code"])}로 바꾸면 <code>{switched}</code>에서 같은 <code>{PORTAL_COMPONENT}</code>로 '
            f'「{ko["HAS_COMPONENT"]}」 관계가 이어지고, 그 아래 센서 · 상태 변수도 이 표와 같은 노드입니다.</p>')

def provided_basis(practical):
    """실습4 입력/자료_검토.md — 제공된 모델이 원자료를 어떻게 처리했는지(이번 실습의 결과가 아님)."""
    lines = ['# 제공된 모델의 자료 처리 근거', '',
             '이 모델(schema.json · graph.json)은 원자료와 현장 메모로 만든 설계 단계의 완성 모델입니다. 이번 실습의 적재 · 조회 결과가 아닙니다. 처리 기준은 schema.json의 constraints에 적혀 있습니다.', '',
             '- 설비: 「코드 통합」 이관 기록은 대상을 새로 만들지 않고 legacy_codes로 남겼습니다. 구성 요소는 기능 자리 기준 ID이고 실물 교체는 serial로 남겼습니다(철거 행 제외).',
             '- 센서: 같은 설비 · 태그의 점검표 재기입 행은 하나로 두었습니다. 단위는 물리량 기준 단위로 맞추고 바꾼 경우 source_unit을 남겼습니다. 계산값 · 설정값은 kind로 구별했습니다. 한계가 없으면 limit을 생략했습니다.',
             *[f'- 센서 {sid}: `입력/자료/센서_목록.csv` {b["line"]}행은 단위 칸이 비어 있어, 같은 모델 · 같은 태그로 정상값 · 한계까지 같은 줄({" · ".join(f"{n}행" for n in b["basis"])})을 근거로 단위를 {b["unit"]}로 두었습니다.'
               for sid, b in blank_unit_basis().items()],
             '- 부품: 교체부품 칸의 품명 · 표기 변형 · 제조사 품번은 품번 교차표와 예비품 목록의 적용 모델 · 쓰는곳으로 사내 품번에 이었습니다. 같은 규격의 다른 사내 품번은 따로 두었습니다.']
    if practical:
        # 7.4를 「붙였다」고 풀어 쓰면 실습4 결정 지점(조회에 함께 돌려줄지)이 한쪽으로 기운다(리허설 — 코딩랩.md K-4). 값이 어디서 왔는지만 적는다.
        lines.append('- 공급: 공급사 · 품번마다 기준일에 유효한 최신 견적 하나를 SUPPLIES로 두었습니다. 공급사 이름은 승인공급사_목록(SCM 등록)의 이름입니다(견적표의 공급사 칸은 그 이름으로 시작합니다). '
                     '승인 여부는 승인공급사_목록과 기준일로 정했습니다(조건부 승인은 approved=true, 조건은 condition). '
                     '단가는 만원, 불량률은 0~1 비율, 납기는 일로 맞추고, 바꾼 불량률 · 납기는 원래 표기를 defect_rate_original · lead_days_original로 남겼습니다.')
        lines.append(f'- 출처: SUPPLIES마다 값이 온 곳을 남겼습니다 — quote_source = 그 쌍에 쓴 견적의 `입력/자료/{D.QUOTE_FILE}` 줄(견적일은 quote_date), '
                     f'approval_source = `입력/자료/{D.AVL_FILE}`의 등록 줄, as_of = 승인 · 유효기한을 판단한 기준일, rule_source = inspection · compare_extra_manwon 값이 온 `입력/자료/{D.PR07_FILE}` 줄. 줄 번호는 편집기에 보이는 번호(머리줄이 1행)입니다.')
    return '\n'.join(lines) + '\n'


# ───────────── 단계 랩(오프라인 50분 판) — 틀은 lab_frame, 학생 몫은 결과/의 정할 자리, 일반 로직은 제공 코드 ─────────────
# 구성안: 작업/2026-11-04_코딩랩-온톨로지파트-재개/구성안50_2회차.md, 계약: 공용틀_계약.md. 단계 · 힌트에는 값과 판단 지점의 답을 쓰지 않는다(K-4) —
# 답은 가이드의 「정답 보기」(F.A, 랩 폴더 밖)에만 둔다.
H, S, A, paste, ask_ai = F.H, F.S, F.A, F.paste, F.ask_ai
SHOW = F.SHOW_CMD
CHOSEN_ROW = ' 사람마다 갈릴 선택은 `결과/정한_것.csv`에 한 줄씩 적습니다.'
NEXT_LAB = {'통합반': '설계한 온톨로지를 그래프 DB에 구현하고 검증하기', '실전반': '부품의 사용 설비와 공급 정보를 조회하는 그래프 구현하기'}
AFTER_LAB = {'통합반': '작업 절차와 판단 조건을 연결해 조치 기준 만들기', '실전반': '작업 기준의 복합 조건과 예외를 조치 조건표로 표현하기'}
SOURCES = f'원자료. CSV 8개(설비 대장 · 구성 요소 · 센서 · 예비품 · 품번 교차표 · 공급 조건 · 승인 공급사 · 입고 이력), 현장 메모{{}}. 기준일은 {D.REF_DATE}입니다.'
RULES_LINE = '`AGENTS.md` · `.github/copilot-instructions.md` · `CLAUDE.md` — Codex와 GitHub Copilot이 지키는 작업 규칙(세 파일이 같은 내용). 학생도 함께 읽습니다.'
SHOW_LINE = '`show_result.py` · `lab_steps.py` — 결과 화면을 만드는 제공 코드. `python show_result.py`가 단계마다 `결과/보기.html`을 다시 씁니다. 바꾸지 않습니다.'
CLASS_LINK = '종류(이론의 클래스 — 대상의 갈래)'


def expect_hint(cols, what, form=''):
    return H(f'{what}의 기대 답을 원자료에서 먼저 찾아 적는다(결과 화면이 이 표와 실제 답을 견준다)',
             '`자료/` 원문 줄, START.md 질문, 2단계 근거 줄',
             f'AI의 답을 옮기지 않는다. 열({", ".join(cols)})은 그대로, 근거는 파일:줄.' + (f' 값의 꼴: {form}.' if form else ''),
             '`결과/기대_답.csv`의 행, 결정 지점마다 `결과/정한_것.csv` 한 줄',
             'AI가 파일을 바꾸지 않고 근거 줄을 되짚고, 3단계 칸에 내 표가 보인다')


# ───────────── 통합반 02-3 ─────────────
def design_integrated():
    import session2_answers as ANS
    course = '통합반'
    title = '현장 정보를 체계화하는 온톨로지 직접 설계하기'
    save = (f'`결과/`의 정할 자리 · `schema.json` · `graph.json` · `정한_것.csv` · `요구사항.md`를 함께 보관합니다. '
            f'다음 실습 「{NEXT_LAB[course]}」은 이 판본이나 제공 모델로 시작합니다. ' + F.USB)
    a = ANS.integrated_design('A')
    b = ANS.integrated_design('B')
    steps = [
        S('폴더와 출발점 확인', '시작',
          '탐색기에서 `입력/` · `자료/` · `결과/` · START.md를 열고, 터미널에서 `python show_result.py`로 결과 화면을 처음 엽니다.',
          '질문 셋과 이 답을 쓰는 사람을 확인합니다.',
          '결과 화면 1단계 칸에 원자료 파일과 행 수가 보이고 3단계부터 「비어 있음」이며, `결과/`에는 빈 틀(첫 줄 「제공 빈 틀」)만 있습니다.',
          cmd=SHOW, why=F.WHY_START, differ=F.DIFFER_START),
        S('파일을 바꾸지 않고 자료 파악', '① 파악',
          'AI에게 파일을 바꾸지 말고, 내가 고른 설비 하나의 구성 요소 · 센서 · 교체 부품에 관한 줄을 자료마다 파일 · 줄로 짚게 하고, 그 줄을 직접 엽니다.',
          '같은 장치 · 센서를 다르게 적은 곳, 빈 칸 · 다른 표기, 두 번 나온 대상처럼 자료끼리 다른 곳을 묻습니다.',
          F.EVIDENCE_LOOK + ' 질문 1 ~ 3에 쓸 자료를 내 말로 댈 수 있습니다.',
          H('고른 설비의 근거 줄을 자료마다 모은다', '`자료/` 전체, `입력/관계그림.json`, START.md 질문',
            '파일을 바꾸지 않는다. 해석보다 파일 · 줄을 먼저.', '「파일:줄 · 말하는 것」 목록, 자료끼리 다른 곳 목록', '짚은 줄 몇 개를 직접 연다'),
          why='모델에는 원자료에 있는 것만 담으므로, 합의하지 않은 해석으로 AI가 만들기 전에 자료부터 봅니다.', differ=F.DIFFER_LOOK),
        S('요구와 기대 답 정하기', '② 요구',
          ('`결과/요구사항.md`에 질문 · 쓰는 사람 · 기준일 · 지킬 조건을, `결과/기대_답.csv`에 고른 설비에서 센서가 붙은 구성 요소 셋의 센서(질문 1), 같은 물리량을 재는 센서 한 묶음(질문 2), '
           '함께 쓰는 부품 · 다른 표기 · 없는 품번 하나씩의 사용 설비(질문 3)를 원자료에서 찾아 적습니다. 질문 1 항목은 지금은 원자료 이름으로 적고 5단계에서 고칩니다. '
           '결정 지점은 `결과/정한_것.csv`에 적습니다.' + F.REQ_AFTER),
          F.ASK_DECIDE, F.REQ_EVIDENCE + ' 3단계 칸에 내 표가 보입니다.',
          expect_hint(ANS.EXPECT_COLUMNS_DESIGN, '질문 1 ~ 3', ANS.EXPECT_EXPLAIN_DESIGN),
          cmd=SHOW, why=F.WHY_REQ, differ=F.DIFFER_REQ.format(rec='결과/기대_답.csv'),
          answer=A('기대 답은 원자료에서 찾은 값이고, 결과 화면이 이 표와 모델의 답을 견줍니다. 아래는 HYD-01 · 유온 · 공용 부품과 다른 표기 · 없는 품번의 예이고, 결정 지점은 두 갈래 가운데 하나를 근거와 함께 고릅니다.',
                   paste('결과/기대_답.csv', expect_design_text()),
                   paste('결과/정한_것.csv — 갈래: 따로 · 이음', chosen_text(ANS.integrated_chosen('A'))),
                   paste('결과/정한_것.csv — 갈래: 한 물품 · 이음', chosen_text(ANS.integrated_chosen('B'))),
                   paste('결과/정한_것.csv — 갈래: 따로 · 잇지 않음', chosen_text(ANS.integrated_chosen('C'))),
                   apply={'결과/기대_답.csv': expect_design_text(), '결과/정한_것.csv': chosen_text(ANS.integrated_chosen('A'))})),
        S('판단① ID와 관계 방향 정하기', '③ 계획 · 판단',
          '`결과/설계.csv`에 대상(설비 · 구성 요소 · 센서 · 물리량 · 부품)마다 ID를 지을 원자료 열을, `결과/관계.csv`에 연결마다 관계 이름과 시작 쪽을 적고 `python show_result.py`를 실행합니다.',
          '같은 태그가 여러 설비에 있을 때 ID가 겹치지 않게 짓는 법과 관계의 시작 · 끝을 정하고, 「ID가 겹치는 원자료 행」이 같은 대상의 겹침인지 원문 줄로 가립니다.' + CHOSEN_ROW,
          '4단계 칸에 내 표가 보이고, 「ID가 겹치는 원자료 행」에 남은 것이 모두 같은 대상이 두 번 나온 행입니다.',
          H('대상마다 ID를 짓는 열과 관계의 방향을 정한다', '`자료/` 세 목록의 열 이름, `입력/관계그림.json`, 현장 메모',
            'ID는 대상 하나만 가리킨다. 열은 {열} 꼴, 관계 이름은 영어 대문자.', '`결과/설계.csv` · `결과/관계.csv`의 행', '「서로 다른 ID 수」를 원자료 행 수와, 겹친 행을 원문과 견준다'),
          cmd=SHOW,
          why=(f'모델은 {CLASS_LINK} · 대상(이론의 인스턴스 — 그 클래스에 속하는 개별 대상) · 속성 · 관계로 짭니다. ID는 대상 하나만 가리키고, 관계에는 방향과 연결 수(1:1 · 1:N · N:M)가 있습니다.'),
          differ='다른 대상이 한 ID로 겹치면 ID에 대상을 가르는 열을 더합니다.',
          answer=A('설비는 설비코드, 구성 요소 · 센서는 설비코드를 앞에 붙여 짓고(같은 이름이 여러 설비에 있음), 관계는 포함하는 쪽에서 시작합니다.',
                   paste('결과/설계.csv', a['결과/설계.csv']), paste('결과/관계.csv — 갈래: 따로', a['결과/관계.csv']), paste('결과/관계.csv — 갈래: 한 물품', b['결과/관계.csv']),
                   apply={'결과/설계.csv': a['결과/설계.csv'], '결과/관계.csv': a['결과/관계.csv']})),
        S('판단② 같은 장치 이름과 겹친 행 정하기', '④ ~ ⑥ 판단 · 대조 · 고침',
          ('`결과/name_rules.py`의 `same_device` · `group_name`에 같은 장치로 볼 내 기준을 AI와 쓰고, `결과/행_처리.csv`에 겹치거나 기준일에 살아 있지 않은 행의 처리를 적은 뒤 `python show_result.py`를 실행합니다. '
           '제공 코드가 모든 구성 요소 행 짝에 내 기준을 물어 묶고 묶음마다 이름 하나를 씁니다. 기준이 묶지 못한 같은 장치만 `결과/이름.csv`에 적습니다.'),
          ('같은 장치로 볼 근거(현장 메모 · 모델 · 계통 · 붙은 태그 · 교체 부품)와 옛 기록 · 철거 · 옮겨 적은 행의 처리를 원문 줄로 정합니다. '
           '묶음 표는 줄마다 열지 않고, 섞인 것과 묶이지 않은 이름만 봅니다.' + CHOSEN_ROW),
          ('5단계 칸의 묶음에 다른 장치가 섞이지 않았고, 묶이지 않은 이름마다 그대로 둘지 이름 표에 적을지 말할 수 있으며, 설비별 원자료 행 · 만든 수의 차이를 원자료 행으로 설명할 수 있습니다. '
           '`결과/기대_답.csv` 질문 1 항목을 이 단계에서 정한 이름으로 고쳤습니다(9단계는 이 이름으로 짝을 맞춥니다).'),
          H('같은 장치로 볼 기준을 함수로 쓰고, 기준 밖 이름과 겹친 행 · 옛 행의 처리를 정한다',
            '`결과/name_rules.py` 설명, 구성 요소 · 센서(붙은곳) · 예비품(쓰는곳) 목록, 설비 대장, 현장 메모, 4단계의 겹친 행',
            '함수 머리는 그대로. 근거 있는 짝만 같은 장치로. 처리는 빼기 · 하나로:<남길 행> · 옛 코드:<설비코드>. 근거는 파일:줄.',
            '두 함수 본문, `결과/행_처리.csv`의 행, 필요하면 `결과/이름.csv`의 행', '5단계 묶음 · 묶이지 않은 이름 표와 설비별 수를 원자료와 견준다'),
          cmd=SHOW,
          why='같은 장치를 다르게 적은 행과 다른 장치를 비슷하게 적은 행을 가려야 대상이 두 번 생기거나 섞이지 않습니다.',
          differ=('다른 장치가 섞였으면 그 두 행을 AI에게 전해 기준을 고칩니다. 「ID … 가 이미 있습니다」는 행 처리 표에 한 줄을 더하고, '
                  '「… 붙은곳 … 이 … 의 구성 요소에 없습니다」는 그 붙은곳이 같은 설비의 구성 요소와 같은 이름이 되게 고칩니다.'),
          answer=A('같은 모델에서 같은 센서 태그가 붙은 자리와 같은 교체 부품을 쓰는 자리를 같은 장치로 보고(계통이 다르면 따로 — 후속 모델의 수냉 열교환기는 부품이 달라 따로), 그 기준이 묶지 못한 이름만 이름 표에 적고, 옛 코드 · 철거 · 점검표에서 옮겨 적은 행을 처리합니다.',
                   paste('결과/name_rules.py', a['결과/name_rules.py']), paste('결과/이름.csv', a['결과/이름.csv']), paste('결과/행_처리.csv', a['결과/행_처리.csv']))),
        S('판단③ 같은 물리량 묶기', '④ ~ ⑥ 판단 · 대조 · 고침',
          ('`결과/quantity_rules.py`의 `same_quantity` · `quantity_name` · `kind_of`에 같은 물리량으로 볼 기준과 종류(실측 · 계산값 · 설정값)를 가르는 기준을 AI와 쓰고 `python show_result.py`를 실행합니다. '
           '기준과 다르게 둘 재는것만 `결과/물리량.csv`에 적습니다.'),
          '다른 태그를 같은 물리량으로 묶을 근거(계장태그 칸 — 현장 메모 4절 포함)와, 같은 태그 · 루프라도 다른 것을 재는 행이 있는지 비고 · 메모로 묻고, 계산값 · 설정값을 가를 칸을 정합니다.',
          ('6단계 「물리량마다 묶인 센서」에 3단계의 내 묶음이 그대로 있고 다른 것을 재는 센서가 섞이지 않았으며, 종류 수를 비고 · 수집방식 칸으로 설명할 수 있습니다. '
           '`결과/기대_답.csv` 질문 2의 물을_값이 이 단계에서 정한 물리량 이름과 같습니다(다르면 그 이름으로 고쳐 적습니다 — 9단계는 이 이름으로 묻습니다).'),
          H('같은 물리량과 센서 종류를 가르는 기준을 함수로 쓴다', '`결과/quantity_rules.py` 설명, `자료/센서_목록.csv`(재는것 · 태그 · 계장태그 · 수집방식 · 비고), 현장 메모 4절',
            '함수 머리는 그대로. 근거 있는 것만 묶는다. 계산값 · 설정값을 실측과 섞지 않는다.', '세 함수 본문, 필요하면 `결과/물리량.csv`의 행', '6단계 묶음 표를 3단계 기대 답과 견준다'),
          cmd=SHOW,
          why='태그는 설비마다 붙인 이름이라, 재는 것(물리량)을 따로 두어야 이름이 달라도 같은 것을 재는 센서를 모을 수 있습니다.',
          differ=F.FIX_LOOP,
          answer=A('재는것이 같거나, 한일유압 설비에서 태그가 같거나, 계장태그의 기능 글자와 루프가 같으면 같은 물리량으로 묶고, 비고 「계기 없음」은 계산값, 수집방식 「설정값」은 설정값입니다. 수냉 열교환기의 냉각수 유량은 같은 태그 · 같은 루프라도 다른 회로라 이름 표로 따로 둡니다.',
                   paste('결과/quantity_rules.py', a['결과/quantity_rules.py']), paste('결과/물리량.csv', a['결과/물리량.csv']))),
        S('판단④ 단위와 빈 칸 정하기', '④ ~ ⑥ 판단 · 대조 · 고침',
          '`결과/unit_rules.py`의 `base_unit` · `blank_unit`에 기준 단위를 고르는 기준과 빈 단위 칸을 채우는 기준을 AI와 쓰고 `python show_result.py`를 실행합니다. 기준과 다르게 둘 것만 `결과/단위.csv`에 적습니다.',
          '빈 단위 칸을 알려 주는 다른 줄이 있는지, 어떤 줄이면 같은 단위로 볼지 묻고, 빈 한계 · 정상값이 0이 아니라 값 없음 · 미확인으로 남는지 봅니다.',
          '7단계 칸에 물리량별 기준 단위와 원래 → 바꾼 값이 보이고, 빈 단위 칸은 근거 줄로 채웠거나 미확인입니다.',
          H('기준 단위와 빈 단위 칸을 정하는 기준을 함수로 쓴다', '`결과/unit_rules.py` 설명, `자료/센서_목록.csv`(단위 · 정상값 · 한계 · 한계구분), 6단계 결과',
            '함수 머리는 그대로. 단위를 짐작하지 않는다 — 근거가 없으면 미확인. 빈 칸을 0으로 채우지 않는다.', '두 함수 본문, 필요하면 `결과/단위.csv`의 행', '7단계 표의 원래 · 바꾼 값을 원자료 줄과 견준다'),
          cmd=SHOW,
          why='단위가 다른 값을 그대로 견주면 몇십 배 어긋나고, 빈 칸은 「값 없음 · 미확인 · 0」에 따라 뜻이 다릅니다. 환산은 제공 코드가 합니다.',
          differ='「바꾸는 법을 모릅니다」가 나오면 기준 단위와 표기 차이(대소문자 등)를 원문으로 봅니다.',
          answer=A('물리량마다 원자료에서 가장 많이 쓴 단위를 기준으로 두고, 단위 칸이 빈 줄은 같은 모델 · 같은 태그 · 같은 정상값 · 한계의 줄이 말하는 단위로 채웁니다. 이 기준으로 모두 정해지므로 `결과/단위.csv`는 비워 둡니다.',
                   paste('결과/unit_rules.py', a['결과/unit_rules.py']))),
        S('판단⑤ 교체 부품과 같은 규격 정하기', '④ ~ ⑥ 판단 · 대조 · 고침',
          '`결과/part_rules.py`의 `find_part` · `same_item`을 AI와 채우고 `python show_result.py`를 실행합니다. 괄호 속 품번 · 사내 품번 · 교차표로 풀리는 칸은 제공 코드가 먼저 풀고, 못 푼 행에서만 내 함수를 부릅니다.',
          '빈 칸 · 품명만 적힌 행을 예비품 목록(적용모델 · 쓰는곳)으로 이을지와 같은 규격의 다른 사내 품번을 한 물품으로 볼지, 두 지점 모두 `결과/정한_것.csv`의 결정대로 함수가 답하게 합니다. AI가 결정을 대신하면 돌려보냅니다.',
          '8단계 칸에서 공용 부품의 사용 설비가 기대 답과 같고, 「내 판단 함수가 이은 행」마다 품번을 원자료로 말할 수 있으며, 같은 규격 표의 「한 물품으로」가 내 결정과 같습니다.',
          H('못 푼 교체부품 칸을 잇는 판단과 같은 규격을 한 물품으로 볼지의 판단을 함수로 쓴다', '`결과/part_rules.py` 설명, `자료/예비품_목록.csv` · `품번_교차표.csv`, `결과/정한_것.csv`',
            '함수 머리는 그대로. 근거 없이 품번을 잇지 않는다. 결정은 `결과/정한_것.csv`대로.', '두 함수 본문(품번 또는 None, True 또는 False)', '「내 판단 함수가 이은 행」을 원자료와 견주고, 결정을 바꾸면 바뀌는 설비 수를 본다'),
          cmd=SHOW,
          why='부품은 사내 품번 하나로 한 번만 만들어야 「이 부품을 어느 설비가 쓰나」의 답이 흩어지지 않습니다. 두 번호를 같은 부품으로 볼지는 쓰는 사람의 일에 따라 달라 3단계 결정대로 합니다.',
          differ='사용 설비가 다르면 그 구성 요소 행과 교체부품 칸 글을 AI에게 전해 함수를 고칩니다.',
          answer=A('잇기로 정했으면 못 푼 행은 같은 모델에 적용되고 쓰는곳이 같은 구성 요소인 예비품이 하나일 때 그것으로 잇고, 잇지 않기로 정했으면 잇지 않습니다. 두 결정 지점은 내가 정한 갈래를 씁니다.',
                   paste('결과/part_rules.py — 갈래: 따로 · 이음', ANS.part_rules_answer(False)), paste('결과/part_rules.py — 갈래: 한 물품 · 이음', ANS.part_rules_answer(True)),
                   paste('결과/part_rules.py — 갈래: 따로 · 잇지 않음', ANS.part_rules_answer(False, False)),
                   apply={'결과/part_rules.py': ANS.part_rules_answer(False)})),
        S('물어보고 기대 답과 대조', '⑤ 대조',
          '`python show_result.py`로 9단계 칸에서 내 기대 답과 모델에 물은 답을 줄마다 견줍니다.',
          '「다름」 · 「실제 없음」 · 「기대 밖」 줄마다 기대 답과 4 ~ 8단계 판단 가운데 무엇이 틀렸는지 원문 줄로 가립니다.',
          '9단계 줄이 모두 「같음」이거나, 다른 줄마다 까닭을 `결과/요구사항.md` 「기대 답과 실제 결과」에 적었습니다.',
          H('모델만으로 답이 나오는지 내 기대 답과 견준다', '9단계 표, `결과/기대_답.csv`, 원자료 줄',
            '기대 답을 결과에 맞춰 고치지 않는다(원자료와 달랐을 때만 근거와 함께).', '「다름」 줄마다 까닭과 고친 곳', '고친 뒤 같은 줄을 다시 본다'),
          cmd=SHOW,
          why='제공 코드는 `결과/graph.json`만 읽어 답하므로 빠진 연결이 드러납니다. 모델에 없는 품번(「없음」)과 쓰는 설비가 없는 부품(「쓰는 설비 없음」)이 구별돼야 결과를 믿고 씁니다.',
          differ=F.FIX_LOOP,
          answer=A('항목 이름은 내가 5단계에서 정한 구성 요소 이름과 같게 적어야 짝이 맞습니다. 다른 줄은 그 행의 원자료와 앞 단계 표를 함께 엽니다.',
                   ask_ai('결과 화면 9단계에서 「다름」인 줄을 하나씩 들어, 내 기대 답의 근거 줄과 모델이 그 답을 만든 앞 단계 표의 줄을 나란히 짚어 줘. 파일은 바꾸지 마.'))),
        S('구조 검사', '⑤ ⑥ 대조 · 고침',
          '10단계 칸의 구조 검사(`python check.py`) 출력을 봅니다.',
          '검사가 짚은 문제가 어느 대상 · 관계 · 정할 자리에서 왔는지 묻습니다.',
          '10단계 칸에 「구조 검사 통과」가 있고, 「참고」 줄의 관계 수를 원자료의 붙은 곳과 견주어 설명할 수 있습니다.',
          H('구조 문제와 기록의 빈자리를 찾아 고친다', '`python check.py` 출력', '검사 기준 · 원자료 · 제공 파일을 바꾸지 않는다', '고친 정할 자리와 다시 실행한 출력', '고친 뒤 9단계 표를 다시 본다'),
          cmd='python check.py',
          why='구조 검사는 ID 겹침 · 관계 끝 · 스키마 밖 종류 · 제공 파일 · 정한_것 근거 꼴 같은 모양만 봅니다. 값이 맞는지는 9단계가 봅니다.',
          differ='「구조 확인 필요」 아래 줄마다 어느 정할 자리에서 왔는지 AI에게 짚게 해 고칩니다.',
          answer=A('구조 검사가 짚는 것은 대개 정한_것.csv의 빈 칸이나 근거 꼴입니다. 고른 것마다 파일:줄을 적습니다.',
                   paste('결과/정한_것.csv — 갈래: 따로(예)', chosen_text(ANS.integrated_chosen('A'))))),
        S('저장하고 다시 열기', '⑦ 저장 · 다시 열기',
          '모두 저장하고 폴더를 닫았다 다시 연 뒤 `python show_result.py`를 다시 실행하고, `결과/요구사항.md` 끝에 기준일 · 저장 시점 · 확인하지 못한 점을 적습니다.',
          '확인하지 못한 점을 정합니다.',
          '다시 연 뒤에도 단계 띠와 9단계 표가 같고, `결과/`의 정할 자리 · 모델 두 파일 · `정한_것.csv` · `요구사항.md`가 채워져 있습니다.',
          cmd=SHOW, why=F.WHY_SAVE, differ=F.DIFFER_SAVE),
    ]
    return dict(
        title=title, course=course, rec='결과/요구사항.md', readonly='`입력/` · `자료/` · 제공 파일(`show_result.py` · `lab_steps.py` · `model_tool.py` · `check.py`)이', decide_step=2,
        goal=['포털 지식 지도에서 오일 쿨러와 거기 붙은 센서가 어떻게 이어지는지 따라가 봤습니다. 이번에는 그 연결을 직접 만듭니다. '
              f'유압 설비 7대의 대장 · 구성 요소 · SCADA 태그 · 예비품 자료를 {CLASS_LINK} · 속성 · 관계로 짠 온톨로지에 맞춰 지식 그래프로 정리해, 설비별 센서와 여러 설비가 함께 쓰는 부품을 답하게 합니다. '
              '자료는 같은 센서 이름이 여러 설비에 쓰이고, 같은 장치를 다르게 부르며, 줄이 겹치거나 칸이 비어 있습니다. 읽기 · 환산 · 계약 꼴 · 물어보기는 제공 코드가 하고, '
              '나는 결과가 갈리는 판단(ID와 관계 방향, 같은 장치 · 물리량으로 볼 근거, 빈 칸의 뜻, 같은 규격을 한 물품으로 볼지)을 정합니다.',
              F.STAGE_LINE.format(what='설계')],
        make='만들 것: `결과/`의 정할 자리(판단 표 · 판단 함수)와 그것으로 제공 코드가 만드는 스키마와 지식 그래프(`결과/schema.json` · `결과/graph.json`), `결과/기대_답.csv` · `결과/정한_것.csv` · `결과/요구사항.md`.',
        start=['`자료/` — ' + SOURCES.format('') + ' 이번 질문에 쓰는 것은 설비 · 구성 요소 · 센서 · 예비품 · 품번 자료이고, 공급 · 입고 자료는 이번 질문 밖입니다.',
               '`입력/관계그림.json` — 1회차에 ARROWS로 그린 관계 그림(설비 · 구성 요소 · 센서와 증상 · 원인 · 조치). 이번에는 그 가운데 설비 · 센서 · 부품 쪽을 원자료 전체로 구체화합니다.',
               '`결과/` — 정할 자리(첫 줄에 「제공 빈 틀」이 있는 표 · 함수 파일)와 기록. 모델(스키마 · 인스턴스)은 정할 자리를 채운 뒤 제공 코드가 씁니다.',
               '`model_tool.py` — 원자료와 정할 자리를 읽어 모델을 쓰고 모델에 물어보는 제공 코드(바꾸지 않습니다). `check.py` — 구조 검사.',
               SHOW_LINE, RULES_LINE],
        user='아래 질문의 답은 보전팀이 설비별 센서를 찾고, 교체할 부품을 어느 설비와 함께 준비할지 정할 때 씁니다. 같은 부품을 구매팀은 호환 후보를 찾을 때, 창고는 품목별 재고를 셀 때 조회합니다.',
        questions=['설비별로 어떤 구성 요소에 어떤 센서 · 계산값 · 설정값이 붙어 있는가?',
                   '각 센서가 재는 물리량과 단위 · 정상값 · 한계(위로 넘는지, 아래로 떨어지는지)는 무엇인가? 설비마다 태그 이름이 달라도 같은 물리량을 재는 센서를 함께 찾을 수 있는가?',
                   '교체 부품별로 그 부품을 쓰는 설비와 구성 요소는 무엇인가? 다른 표기로 적힌 품번, 제조사 규격 번호, 원자료에 없는 품번으로 물으면 결과가 어떻게 구별되는가?'],
        decide=[('쓰는 사람에 따라 갈리는 답', '같은 규격(제조사 품번)으로 등록된 서로 다른 사내 품번을 한 물품으로 볼지 — 그 규격이나 한쪽 품번으로 물었을 때 나와야 할 답이 호환 후보를 찾는 사람과 품목별 재고를 세는 사람에게 같은지'),
                ('빈 칸의 뜻', '교체부품 칸이 비었거나 품명만 적힌 행을 예비품 목록(적용모델 · 쓰는곳)으로 이어 그 부품을 쓰는 설비로 볼지, 원자료가 품번을 말하지 않았으니 잇지 않을지')],
        outside=['공급 조건 · 입고 이력을 모델에 넣는 일', '그래프 DB에 적재하고 조회하는 일(다음 실습)', '부품 재고 수량을 세거나 발주를 정하는 일'],
        formats=[FORMAT], steps=steps,
        cases=['같은 태그 이름이 여러 설비에 있는 경우', '이름이 다른데 같은 것을 재는 태그', '같은 장치를 다르게 부른 이름', '같은 대상이 두 번 나온 행',
               f'기준일({D.REF_DATE})에 살아 있지 않은 기록(옛 코드 · 철거된 실물)',
               '비어 있는 칸(단위 · 교체부품 · 정상값)', '단위 표기가 다른 값', '계기 없는 계산값과 설정값', '여러 설비가 함께 쓰는 부품과 한 설비만 쓰는 부품',
               '품번 대신 품명 · 다른 표기로 적힌 칸', '같은 규격(제조사 품번)으로 등록된 다른 사내 품번', '원자료에 없는 품번', '같은 정할 자리로 다시 실행한 결과'],
        commands='python show_result.py\npython check.py',
        done=('형식 검사나 실행 성공만으로 완료하지 않습니다. 결과 화면 9단계에서 질문마다 원자료에서 먼저 적은 기대 답과 모델의 답이 맞고, `결과/정한_것.csv`의 지점마다 근거 줄과 그 선택으로 바뀌는 답을 설명할 수 있으면 완료입니다. '
              '고친 점과 확인하지 못한 점은 `결과/요구사항.md`에 짧게 남깁니다.'),
        save=save, reopen='결과 화면의 단계 띠와 9단계 대조 표, `요구사항.md`의 기준일 · 저장 시점 · 확인하지 못한 점',
        tree=F.tree(LAB3, [('.github/', '작업 규칙'), ('결과/', '정할 자리 · 기록'), ('입력/', '1회차 관계 그림(읽기만)'),
                           ('자료/', '원자료(읽기만)'), ('AGENTS.md', '작업 규칙'), ('check.py', '구조 검사'), ('CLAUDE.md', '작업 규칙'),
                           ('lab_steps.py', '결과 화면 단계(제공)'), ('model_tool.py', '모델 쓰기 · 물어보기(제공)'), ('show_result.py', '결과 화면(제공)'), ('START.md', '과제와 진행 단계'), ('준비_안내.md', '처음 볼 곳')]),
        lead='원자료로 스키마와 지식 그래프를 만들되 결과가 갈리는 판단만 내가 정하고, 판단마다 결과 화면에서 원자료와 대조합니다.',
        need='VS Code와 Python, 로그인해 둔 Codex 또는 GitHub Copilot.',
        terms=('**계산값**은 계기 없이 다른 값으로 계산한 값, **설정값**은 사람이 정해 넣는 목표 값, **사내 품번**은 우리 회사 번호, **제조사 규격 번호**(제조사 품번)는 만든 회사의 번호, '
               '**기준일**은 자료를 뽑은 날, **정할 자리**는 `결과/`에서 첫 줄에 「제공 빈 틀」이 있는 파일입니다.'),
        guide_extra={0: ['terminal', 'result'], 1: ['ai', 'review']}, guide_after={9: ['check_stop']},
        provided=['model_tool.py'], kind='design_integrated', answers={'A': a, 'B': b},
        ai_wait=(3.2, '리허설 50L2 실측 — v17, 2026-11-05'),
        files={'결과/요구사항.md': F.req_template('요구사항'), '결과/정한_것.csv': F.CHOSEN_TEMPLATE,
               '결과/기대_답.csv': F.blank_csv(ANS.EXPECT_COLUMNS_DESIGN, ANS.EXPECT_EXPLAIN_DESIGN),
               **{f'결과/{n}': F.blank_csv(ANS.DESIGN_COLUMNS[n], ANS.DESIGN_EXPLAIN[n]) for n in ANS.DESIGN_COLUMNS},
               '결과/part_rules.py': ANS.PART_RULES_BLANK, '결과/name_rules.py': ANS.NAME_RULES_BLANK,
               '결과/quantity_rules.py': ANS.QUANTITY_RULES_BLANK, '결과/unit_rules.py': ANS.UNIT_RULES_BLANK,
               '결과/README.md': '정할 자리(첫 줄에 「제공 빈 틀」이 있는 파일)를 채우고 `python show_result.py`를 실행하면 제공 코드가 이 폴더에 schema.json · graph.json과 결과 화면 보기.html을 씁니다.\n다시 열 때는 `python show_result.py`를 다시 실행해 결과 화면의 단계 띠와 9단계 대조 표를 봅니다.\n',
               '입력/README.md': '1회차에 ARROWS로 그린 관계 그림(관계그림.json)입니다. 이번 모델의 출발 그림으로 보고, 이 폴더는 읽기만 합니다.\n'})


def chosen_text(rows):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator='\n')
    for r in rows:
        w.writerow(r)
    return F.CHOSEN_TEMPLATE + buf.getvalue()


def expect_design_text():
    """통합 02-3 기대 답 예 — 강사 참조 A 모델(원자료끼리 대조해 만든 것)에서 뽑은 HYD-01 질문 1, 유온 질문 2, 공용 · 다른 표기 · 없는 품번 질문 3."""
    import session2_answers as ANS
    _, graph = reference_model(False, 'A')
    label = {n['props']['id']: n['labels'][0] for n in graph['nodes']}
    props = {n['props']['id']: n['props'] for n in graph['nodes']}
    rows = []
    comp_sensors = {}
    for r in graph['rels']:
        if r['type'] == 'MONITORED_BY' and r['a'].startswith('HYD-01'):
            name = '설비 전체' if label[r['a']] == 'Asset' else props[r['a']]['name']
            comp_sensors.setdefault(name, []).append(props[r['b']]['tag'])
    for name, tags in sorted(sorted(comp_sensors.items()), key=lambda x: -len(x[1]))[:3]:   # 질문 1은 구성 요소 셋
        rows.append(['1', 'HYD-01', name, ' · '.join(sorted(tags)), '자료/센서_목록.csv:2~21 붙은곳 칸'])
    members = sorted(r['a'] for r in graph['rels'] if r['type'] == 'OBSERVES' and r['b'] == 'quantity:TS1')
    rows.append(['2', D.QUANTITIES['quantity:TS1'][0], '', ' · '.join(members), '자료/센서_목록.csv 재는것 · 계장태그 칸'])
    for code, row_hint in [('P-FAN-BRG', '자료/구성요소_목록.csv 교체부품 칸'), ('RF-10', '자료/품번_교차표.csv'), ('P-PMP-SEAL-X', '원자료에 없음')]:
        hits = [i for i, p in props.items() if label[i] == 'Part' and (i == code or code in p.get('other_codes', []))]
        if not hits:
            rows.append(['3', code, '', '없음', row_hint])
        for pid in hits:
            assets = sorted({r2['a'] for r in graph['rels'] if r['type'] == 'USES_PART' and r['b'] == pid for r2 in graph['rels'] if r2['type'] == 'HAS_COMPONENT' and r2['b'] == r['a']})
            rows.append(['3', code, pid, ' · '.join(assets), row_hint])
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator='\n')
    w.writerow(ANS.EXPECT_COLUMNS_DESIGN)
    for r in rows:
        w.writerow(r)
    return f'# {F.MARK} — {ANS.EXPECT_EXPLAIN_DESIGN}\n' + buf.getvalue()


# ───────────── 실전반 02-3 ─────────────
def design_practical():
    import session2_answers as ANS
    course = '실전반'
    title = '설비·부품·공급 정보를 연결하는 온톨로지 설계하기'
    save = (f'`결과/`의 정할 자리 · `schema.json` · `graph.json` · `정한_것.csv` · `요구사항.md`를 함께 보관합니다. '
            f'다음 실습 「{NEXT_LAB[course]}」은 이 판본이나 제공 모델로 시작합니다. ' + F.USB)
    steps = [
        S('폴더와 출발점 확인', '시작',
          '탐색기에서 `입력/` · `자료/` · `결과/` · START.md를 열고 `python show_result.py`로 결과 화면을 엽니다. 다음 실습 폴더도 받아 그 폴더에서 `python lab_db.py`를 먼저 켜 둡니다.',
          '질문 셋과 이 답을 쓰는 사람(구매 담당)을 확인합니다.',
          '1단계 칸에 제공 모델의 종류별 개수(공급사 종류는 아직 없음)와 원자료 행 수가 보이고, 3단계부터 「비어 있음」입니다.',
          cmd=SHOW, why='제공 모델에 무엇이 없는지 알아야 공급 정보를 더할 자리를 정합니다. 다음 실습의 랩 DB는 처음 켜는 데 오래 걸립니다.',
          differ=F.DIFFER_START),
        S('파일을 바꾸지 않고 자료 파악', '① 파악',
          'AI에게 파일을 바꾸지 말고 펌프 축 씰 키트에 관한 줄을 자료마다 파일 · 줄로 짚게 하고, 그 줄을 직접 엽니다.',
          '공급 조건 · 승인 · 비교 기준이 어느 자료에 있는지, 자료끼리 다르게 말하는 곳, 구매 기준서 7.4가 더 보게 하는 것을 묻습니다.',
          F.EVIDENCE_LOOK + ' 질문 1 · 2에 쓸 자료를 내 말로 댈 수 있습니다.',
          H('펌프 축 씰 키트의 근거 줄을 자료마다 모은다', '`자료/` 전체, `입력/graph.json`, START.md 질문',
            '파일을 바꾸지 않는다. 해석보다 파일 · 줄을 먼저.', '「파일:줄 · 말하는 것」 목록, 자료끼리 다른 곳 목록', '짚은 줄 몇 개를 직접 연다'),
          why='공급 조건이 견적표 · 승인 목록 · 기준서에 흩어져 있어, 한 자료만 보면 어긋난 곳을 놓칩니다.', differ=F.DIFFER_LOOK),
        S('요구와 기대 답 정하기', '② 요구',
          ('`결과/요구사항.md`에 질문 · 쓰는 사람 · 기준일 · 지킬 조건을, `결과/기대_답.csv`에 질문 1(사용 설비) · 질문 2(기준일의 세 공급 조건) · 질문 3(다른 표기 · 없는 품번)의 기대 답을 '
           '원자료에서 찾아 적고, 결정 지점 셋을 `결과/정한_것.csv`에 적습니다.' + F.REQ_AFTER),
          F.ASK_DECIDE, F.REQ_EVIDENCE + ' 3단계 칸에 내 표가 보입니다.',
          expect_hint(ANS.EXPECT_COLUMNS_SUPPLY, '질문 1 ~ 3', ANS.EXPECT_EXPLAIN_SUPPLY), cmd=SHOW, why=F.WHY_REQ, differ=F.DIFFER_REQ.format(rec='결과/기대_답.csv'),
          answer=A('질문 2의 답은 「승인 · 단가 · 불량률 · 납기」 꼴로 적습니다. 결정 지점은 갈래마다 바뀌는 답이 다르니 근거 줄을 열어 고릅니다.',
                   paste('결과/기대_답.csv', expect_supply_text()),
                   paste('결과/정한_것.csv — 갈래: 승인 · 조건 없음 · 7.4 함께', chosen_text(ANS.practical_chosen('ㄴ'))),
                   paste('결과/정한_것.csv — 갈래: 승인 · 조건 없음 · 네 값만', chosen_text(ANS.practical_chosen('A'))),
                   paste('결과/정한_것.csv — 갈래: 조건부 승인은 비승인', chosen_text(ANS.practical_chosen('B'))),
                   paste('결과/정한_것.csv — 갈래: 빈 조건은 미결', chosen_text(ANS.practical_chosen('ㄷ'))),
                   apply={'결과/기대_답.csv': expect_supply_text(), '결과/정한_것.csv': chosen_text(ANS.practical_chosen('ㄴ'))})),
        S('판단① 기준일에 쓸 견적 정하기', '④ ~ ⑥ 판단 · 대조 · 고침',
          '`결과/quote_rule.py`의 `use_quote`를 AI와 채우고 `python show_result.py`를 실행합니다. 공급사 이름 · 품번 · 단위 맞추기와 출처는 제공 코드가 합니다.',
          '같은 쌍에 견적이 여럿이거나 기한이 걸린 줄을 어떻게 할지와 근거 줄을 정합니다. 가장 싼 줄 고르기는 범위 밖입니다.' + CHOSEN_ROW,
          '4단계 칸에서 「씀 · 기준일에 안 씀」의 합이 견적 줄 수와 같고, 펌프 축 씰 키트 세 쌍이 기대 답과 같으며, 「8%」 · 「2주」는 원래 표기와 함께 보입니다.',
          H('쌍마다 기준일에 쓸 견적 줄을 고르는 판단을 함수로 쓴다', '`결과/quote_rule.py` 설명, `자료/공급_조건.csv`(견적일 · 유효기한), 현장 메모 6절',
            '함수 머리는 그대로. 쌍마다 줄 하나 또는 None. 점수 · 순위로 고르지 않는다.', '본문을 채운 `use_quote`', '「견적 줄마다 간 곳」을 견적일 · 유효기한과 견준다'),
          cmd=SHOW, why=('같은 공급사 · 부품에 견적이 여러 번 있으면 기준일에 쓸 것은 하나여야 고르는 사람이 같은 조건을 봅니다. 어느 줄을 왜 골랐는지 남겨야 나중에 그 선택을 다시 볼 수 있습니다. '
                         '기한 지난 줄을 빼느냐, 가장 늦은 줄을 쓰느냐에 따라 4단계 표의 단가 · 납기 · 견적일이 쌍마다 달라집니다.'), differ=F.FIX_LOOP,
          answer=A('기준일에 유효기한이 지난 견적은 빼고, 남은 줄 가운데 견적일이 가장 늦은 줄을 씁니다.', paste('결과/quote_rule.py', ANS.QUOTE_RULE_ANSWER))),
        S('판단② 승인과 함께 볼 것 정하기', '④ ~ ⑥ 판단 · 대조 · 고침',
          '`결과/approval_rule.py`의 `approval` · `buyer_info`를 `결과/정한_것.csv`의 세 결정대로 AI와 채우고 `python show_result.py`를 실행합니다.',
          ('출처마다 다른 승인 정보와 기한 지난 등록은 어느 자료를 따랐는지, 조건부 승인 · 빈 조건 · 함께 볼 정보가 내 결정대로 처리됐는지 쌍마다 근거 줄로 묻습니다. '
           'AI가 결정을 대신하면 돌려보냅니다.'),
          '5단계 칸에서 펌프 축 씰 키트의 승인 표시마다 결정과 근거 줄을 짚을 수 있고, 같은 결정이 다른 쌍에도 같게 적용됐습니다.',
          H('쌍마다 승인 여부와 고르는 사람이 함께 볼 정보를 붙이는 판단을 함수로 쓴다',
            '`결과/approval_rule.py` 설명, `자료/승인공급사_목록.csv`, 공급_조건의 승인공급사 칸, 구매 기준서 발췌, `결과/정한_것.csv`',
            '결정은 `결과/정한_것.csv`대로. 미결은 미결로 두고 값을 지어내지 않는다. 고르기 · 점수는 넣지 않는다.',
            '본문을 채운 `approval` · `buyer_info`', '5단계 표에서 펌프 축 씰 키트 · 쿨러 코어 · 어큐뮬레이터 블래더의 승인 칸을 원자료 줄과 견준다'),
          cmd=SHOW, why=('승인 여부는 그 부품을 그 공급사에서 사도 되는지를 정하는 값이라, 출처마다 다르게 적혀 있으면 어느 것을 따랐는지가 결과의 뜻을 바꿉니다. 3단계에서 정한 결정은 모든 쌍에 같은 방식으로 적용합니다. '
                         '조건부 승인을 승인으로 담느냐 비승인으로 담느냐에 따라 5단계 표의 approved가 바뀌고, 함께 볼 정보를 남기면 그 쌍에 속성 칸이 더 생깁니다.'), differ=F.FIX_LOOP,
          answer=A('승인 여부는 SCM 등록(기준서 7.3)과 기준일의 유효기한으로 정합니다. 세 결정 지점의 갈래마다 함수가 다르니 내가 고른 갈래를 씁니다.',
                   paste('결과/approval_rule.py — 갈래: 승인 · 조건 없음 · 7.4 함께', ANS.approval_rule_answer('ㄴ')),
                   paste('결과/approval_rule.py — 갈래: 승인 · 조건 없음 · 네 값만', ANS.approval_rule_answer('A')),
                   paste('결과/approval_rule.py — 갈래: 조건부 승인은 비승인', ANS.approval_rule_answer('B')),
                   paste('결과/approval_rule.py — 갈래: 빈 조건은 미결', ANS.approval_rule_answer('ㄷ')),
                   apply={'결과/approval_rule.py': ANS.approval_rule_answer('ㄴ')})),
        S('물어보고 대조 · 구조 검사', '⑤ ⑥ 대조 · 고침',
          '`python show_result.py`로 6단계 칸의 기대 답 ↔ 모델의 답과 구조 검사 출력을 봅니다.',
          '「다름」 줄마다 기대 답과 4 · 5단계 판단 가운데 무엇이 틀렸는지 원문 줄로 가립니다.',
          '6단계 줄이 모두 「같음」이거나 다른 까닭을 `요구사항.md`에 적었고, 「구조 검사 통과」가 있습니다.',
          H('모델만으로 답이 나오는지 견주고 구조를 검사한다', '6단계 칸, `결과/기대_답.csv`, `python check.py` 출력',
            '기대 답을 결과에 맞춰 고치지 않는다. 검사 기준 · 제공 파일을 바꾸지 않는다.', '「다름」 줄마다 까닭과 고친 곳', '고친 뒤 다시 실행한다'),
          cmd=SHOW, why=('모델이 질문에 답하는지는 모델만 읽어 확인해야 빠진 연결이 드러납니다. 비슷한 이름의 다른 품번 · 예전 품번 · 없는 품번이 서로 구별돼야 구매 담당이 엉뚱한 부품의 조건을 보지 않습니다.'), differ=F.FIX_LOOP,
          answer=A('항목은 질문 1이 사내 품번, 질문 2가 「사내 품번/공급사」입니다. 다른 줄은 그 쌍의 견적 · 승인 줄을 함께 엽니다.',
                   ask_ai('결과 화면 6단계에서 「다름」인 줄마다 내 기대 답의 근거 줄과 그 쌍의 견적 · 승인 원자료 줄을 나란히 짚어 줘. 파일은 바꾸지 마.'))),
        S('저장하고 다시 열기', '⑦ 저장 · 다시 열기',
          '모두 저장하고 폴더를 닫았다 다시 연 뒤 `python show_result.py`를 다시 실행하고, `요구사항.md` 끝에 기준일 · 저장 시점 · 확인하지 못한 점을 적은 뒤 다음 실습 폴더로 갑니다.',
          '확인하지 못한 점을 정합니다.', '다시 연 뒤에도 단계 띠와 6단계 표가 같습니다.',
          cmd=SHOW, why=F.WHY_SAVE, differ=F.DIFFER_SAVE),
    ]
    return dict(
        title=title, course=course, rec='결과/요구사항.md', readonly='`입력/` · `자료/` · 제공 파일(`show_result.py` · `lab_steps.py` · `supply_tool.py` · `check.py`)이', decide_step=2,
        goal=['포털 지식 지도에서 부품을 쓰는 설비를 찾을 때, 연결이 있다는 것과 살 수 있는 조건이 확보됐다는 것은 달랐습니다. 이번에는 제공된 설비 · 부품 모델에 견적 · 승인 · 품번 자료를 이어, '
              '부품마다 쓰는 설비와 공급사별 조건을 답하게 합니다. 단위 · 출처 · 계약 꼴은 제공 코드가 하고, 나는 어느 견적을 쓰고 승인을 어떻게 담고 무엇을 함께 남길지 정합니다. 공급사를 고르는 것은 구매 담당입니다.',
              F.STAGE_LINE.format(what='설계')],
        make='만들 것: `결과/`의 판단 함수 두 파일과 그것으로 제공 코드가 확장하는 모델(`결과/schema.json` · `결과/graph.json`), `결과/기대_답.csv` · `결과/정한_것.csv` · `결과/요구사항.md`.',
        start=['`입력/schema.json` · `입력/graph.json` — 제공된 설비 · 부품 모델. 설비 7대 · 구성 요소 · 센서 · 부품과 그 연결이 들어 있고, 공급 정보는 아직 없습니다.',
               '`자료/` — ' + SOURCES.format(', 구매 기준서 발췌'),
               '`결과/` — 정할 자리(첫 줄에 「제공 빈 틀」이 있는 함수 · 표 파일)와 기록.',
               '`supply_tool.py` — 공급 정보를 모델에 더하고 물어보는 제공 코드(바꾸지 않습니다). `check.py` — 구조 검사.', SHOW_LINE, RULES_LINE],
        user='아래 질문의 답은 구매 담당이 다음 발주에서 공급사를 비교할 때 씁니다. 고르는 것은 구매 담당입니다.',
        questions=['펌프 축 씰 키트를 쓰는 설비는 어디인가?',
                   f'기준일({D.REF_DATE})에 펌프 축 씰 키트를 어느 공급사에서 어떤 조건(승인 여부 · 단가 · 불량률 · 납기)으로 살 수 있고, 각 값은 어느 파일 · 어느 줄에서 왔는가?',
                   '이름이 비슷한 다른 품번, 예전 품번이나 다른 표기, 원자료에 없는 품번으로 물으면 결과가 서로 구별되는가?'],
        decide=[('조건이 붙은 승인', '승인 목록에 조건을 달아 등록된 쌍을 승인 여부(참 · 거짓)에 어떻게 담고, 그 조건을 구매 담당에게 어떻게 보여 줄지'),
                ('빈 값의 뜻', '비어 있는 칸을 「없음」으로 읽을지 「적지 않음」으로 읽을지'),
                ('쓰는 사람에 따라 갈리는 답', '구매 담당이 공급사를 비교할 때 함께 봐야 할 것이 자료에 있으면, 그것을 모델에 어떻게 남길지')],
        outside=['공급사를 고르거나 점수 · 순위를 매기는 일', '입고 이력으로 실측 납기를 계산하는 일', '그래프 DB에 적재하고 조회하는 일(다음 실습)',
                 '제공된 설비 · 부품 모델의 설비 · 구성 요소 · 센서 · 부품 부분을 고치는 일(이상한 곳은 `결과/요구사항.md`에 적습니다)'],
        formats=[FORMAT, SUPPLY_FORMAT], steps=steps,
        cases=['같은 공급사 · 부품의 견적이 여러 줄인 경우', '기준일에 기한이 지난 기록(견적 · 승인 등록)', '같은 공급사를 다르게 적은 이름',
               '출처마다 다른 승인 정보', '기준서에 나오는 기준값과 같거나 가까운 값', '단위 · 표기가 줄마다 다른 값', '품번 칸의 표기가 줄마다 다른 경우',
               '이름이 비슷한 다른 품번 · 예전 품번 · 다른 표기 · 원자료에 없는 품번', '같은 정할 자리로 다시 실행한 결과'],
        commands='python show_result.py\npython check.py',
        done=('형식 검사나 실행 성공만으로 완료하지 않습니다. 결과 화면 6단계에서 질문마다 원자료에서 먼저 적은 기대 답과 모델의 답이 맞고, `결과/정한_것.csv`의 지점마다 근거 줄과 그 선택으로 바뀌는 답을 설명할 수 있으면 완료입니다. '
              '고친 점과 확인하지 못한 점은 `결과/요구사항.md`에 짧게 남깁니다.'),
        save=save, reopen='결과 화면의 단계 띠와 6단계 대조 표, `요구사항.md`의 기준일 · 저장 시점 · 확인하지 못한 점',
        tree=F.tree(LAB3, [('.github/', '작업 규칙'), ('결과/', '정할 자리 · 기록'), ('입력/', '제공 모델(읽기만)'),
                           ('자료/', '원자료(읽기만)'), ('AGENTS.md', '작업 규칙'), ('check.py', '구조 검사'), ('CLAUDE.md', '작업 규칙'),
                           ('lab_steps.py', '결과 화면 단계(제공)'), ('show_result.py', '결과 화면(제공)'), ('START.md', '과제와 진행 단계'), ('supply_tool.py', '제공 코드'), ('준비_안내.md', '처음 볼 곳')]),
        lead='제공 모델에 공급 조건을 더하되, 어느 견적을 쓰고 승인을 어떻게 담을지만 내가 정하고 결과 화면에서 원자료와 대조합니다.',
        need='VS Code와 Python, 로그인해 둔 Codex 또는 GitHub Copilot, 다음 실습의 랩 DB를 켤 Docker Desktop.',
        terms=('**승인 공급사**는 구매팀이 사도 된다고 등록한 공급사, **불량률**은 입고 물량 가운데 불량 비율, **납기**는 주문부터 받기까지 날수, **기준일**은 자료를 뽑은 날, '
               '**정할 자리**는 `결과/`에서 첫 줄에 「제공 빈 틀」이 있는 파일입니다.'),
        guide_extra={0: ['terminal', 'result'], 1: ['ai', 'review']}, guide_after={5: ['check_stop']},
        provided=['supply_tool.py'], kind='design_practical', ai_wait=(5.9, '리허설 50L 실측 — 2026-11-05'),
        files={'결과/요구사항.md': F.req_template('요구사항'), '결과/정한_것.csv': F.CHOSEN_TEMPLATE,
               '결과/기대_답.csv': F.blank_csv(ANS.EXPECT_COLUMNS_SUPPLY, ANS.EXPECT_EXPLAIN_SUPPLY),
               '결과/quote_rule.py': ANS.QUOTE_RULE_BLANK, '결과/approval_rule.py': ANS.APPROVAL_RULE_BLANK,
               '결과/README.md': '정할 자리(첫 줄에 「제공 빈 틀」이 있는 파일)를 채우고 `python show_result.py`를 실행하면 제공 코드가 이 폴더에 schema.json · graph.json과 결과 화면 보기.html을 씁니다.\n다시 열 때는 `python show_result.py`를 다시 실행해 결과 화면의 단계 띠와 6단계 대조 표를 봅니다.\n',
               '입력/README.md': '제공된 설비 · 부품 모델입니다(schema.json · graph.json). 설비 7대 · 구성 요소 · 센서 · 부품과 그 연결이 있고, 공급 정보는 없습니다. 이 폴더는 읽기만 합니다.\n'})


def expect_supply_text():
    """실전 02-3 기대 답 예 — 강사 참조 ㄴ 모델(실습4 입력과 같은 결정)에서."""
    import session2_answers as ANS
    _, graph = reference_model(True, 'ㄴ')
    label = {n['props']['id']: n['labels'][0] for n in graph['nodes']}
    props = {n['props']['id']: n['props'] for n in graph['nodes']}
    owner = {r['b']: r['a'] for r in graph['rels'] if r['type'] == 'HAS_COMPONENT'}
    rows = []
    for code, q in [('P-PMP-SEAL', '1'), ('P-PMP-SEAL', '2'), ('PS-4510', '1'), ('P-PMP-SEAL-HT', '1'), ('P-PMP-SEAL-X', '1')]:
        hits = [i for i, p in props.items() if label[i] == 'Part' and (i == code or code in p.get('other_codes', []))]
        if not hits:
            rows.append([q, code, '', '없음', '원자료에 없음'])
        for pid in hits:
            if q == '1':
                assets = sorted({owner[r['a']] for r in graph['rels'] if r['type'] == 'USES_PART' and r['b'] == pid})
                rows.append([q, code, pid, ' · '.join(assets), '자료/구성요소_목록.csv 교체부품 칸 · 자료/품번_교차표.csv'])
            else:
                for r in sorted((r for r in graph['rels'] if r['type'] == 'SUPPLIES' and r['b'] == pid), key=lambda r: r['a']):
                    p = r['props']
                    rows.append([q, code, f'{pid}/{props[r["a"]]["name"]}', f'{"승인" if p["approved"] else "비승인"} · {p["price_manwon"]:g} · {p["defect_rate"]:g} · {p["lead_days"]}',
                                 f'자료/{p["quote_source"].replace(" ", ":").replace("행", "")} · 자료/{(p.get("approval_source") or "").replace(" ", ":").replace("행", "")}'])
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator='\n')
    w.writerow(ANS.EXPECT_COLUMNS_SUPPLY)
    for r in rows:
        w.writerow(r)
    return f'# {F.MARK} — {ANS.EXPECT_EXPLAIN_SUPPLY}\n' + buf.getvalue()


# ───────────── 실습4(그래프 구현과 검증) — 두 과정 ─────────────
def graph_lab(course):
    import session2_answers as ANS
    practical = course == '실전반'
    change = not practical
    title = '부품의 사용 설비와 공급 정보를 조회하는 그래프 구현하기' if practical else '설계한 온톨로지를 그래프 DB에 구현하고 검증하기'
    model = '설비 · 부품 · 공급 모델' if practical else '설비 · 센서 · 부품 모델'
    change_dir = f'입력/자료_변경분/{D.CHANGE_DATE}_수정본/'
    input_graph = reference_model(practical, LAB4_INPUT_BRANCH[course])[1]
    load_text = ANS.load_answer(input_graph)
    q_rules = (' 물을 값(품번)은 $ 자리 하나로 받는다.' if practical else ' 물을 값(설비 코드 · 품번)은 $ 자리 하나로 받는다.')
    s_tree = S('폴더와 출발점 · 랩 DB 켜기', '시작',
               ('탐색기에서 `입력/` · `결과/` · START.md를 열고 `python lab_db.py`로 이 폴더 전용 랩 DB를 켠 뒤 `python show_result.py`로 결과 화면을 엽니다.'
                + (' 「설비·부품·공급 정보를 연결하는 온톨로지 설계하기」 1단계에서 이미 켰으면 `python show_result.py`부터 합니다.' if practical else '')),
               '주소가 `127.0.0.1`의 이 폴더 전용인지 보고, 내 모델과 제공 모델 가운데 무엇을 쓸지 정합니다.',
               '「랩 DB 준비 완료」가 나오고, 1단계 칸에 모델 파일 개수와 랩 DB 개수(처음 0)가 나란히 보입니다.',
               cmd='python lab_db.py\npython show_result.py',
               why='처음에 비어 있어야 뒤에서 센 개수가 모두 이번에 넣은 것입니다.',
               differ='「랩 DB 꺼짐」이면 `python lab_db.py`를 다시 실행합니다(이전 작업이면 전에 넣은 개수가 맞음).')
    s_look = S('파일을 바꾸지 않고 자료 파악', '① 파악',
               'AI에게 파일을 바꾸지 말고 `입력/graph.json`의 종류별 대상 · 관계 수와 '
               + ('수정본 줄마다 가리키는 대상과 원자료(`입력/자료/`)의 같은 행을' if change else '펌프 축 씰 키트에 닿는 관계와 그 값의 원자료 줄을')
               + ' 파일 · 줄로 짚게 하고, 그 줄을 직접 엽니다.',
               ('수정본이 무엇을 바꾸는지(이름 · 상태 · 값 · 줄 삭제)와 제공 모델의 ID가 무엇으로 지어졌는지 묻습니다.' if change else
                '제공 모델의 ID와 공급 조건 관계에 붙은 속성(값과 출처)을 묻습니다.'),
               F.EVIDENCE_LOOK + (' 종류별 대상 수와 수정본 줄 수를 내 말로 댈 수 있습니다.' if change else ' 펌프 축 씰 키트에 닿는 관계를 내 말로 댈 수 있습니다.'),
               H('적재할 모델' + ('과 수정본을' if change else '을') + ' 파악한다', '`입력/schema.json` · `graph.json` · `자료_검토.md`, ' + (f'`{change_dir}`' if change else '`입력/자료/`'),
                 '파일을 바꾸지 않는다. 파일 · 줄과 개수를 먼저.', '종류별 개수 표, ' + ('수정본 줄마다 「대상 · 바뀌는 것 · 원자료 행」' if change else '관계와 값의 원자료 줄 목록'),
                 '개수를 1단계 표와 견주고 ' + ('수정본 줄 몇 개를 연다' if change else '출처 줄 몇 개를 연다')),
               why='적재가 맞았는지는 모델 파일에 무엇이 몇 개 있는지 먼저 알아야 셀 수 있습니다.', differ=F.DIFFER_LOOK)
    expect_rows = graph_expect_rows(course, input_graph)
    s_req = S('요구와 기대 답 정하기', '② 요구',
              ('`결과/검증_기록.md`에 질문 · 쓰는 사람 · 지킬 조건을, `결과/기대_답.csv`에 질문마다 물을 값 · 볼 열 · 원자료에서 찾은 기대 답('
               + ('펌프 축 씰 키트의 사용 설비와 세 공급 조건, 다른 표기 · 없는 품번' if practical else '설비 하나의 센서 · 교체 부품, 공용 부품 하나의 사용 설비')
               + ')을 적고, 결정 지점을 `결과/정한_것.csv`에 적습니다.' + F.REQ_AFTER),
              F.ASK_DECIDE, F.REQ_EVIDENCE + ' 3단계 칸에 내 표가 보입니다.',
              expect_hint(ANS.GRAPH_EXPECT_COLUMNS, '질문', ANS.GRAPH_EXPECT_EXPLAIN[course]), cmd=SHOW, why=F.WHY_REQ, differ=F.DIFFER_REQ.format(rec='결과/기대_답.csv'),
              answer=A('볼_열은 내 조회가 돌려줄 열 이름입니다(정답 보기의 조회문을 쓰면 아래 이름). 결정 지점은 갈래마다 바뀌는 답을 보고 고릅니다.',
                       paste('결과/기대_답.csv', graph_expect_text(expect_rows, course)),
                       *[paste(f'결과/정한_것.csv — 갈래: {g}', chosen_text([row])) for g, row in graph_chosen(course).items()],
                       apply={'결과/기대_답.csv': graph_expect_text(expect_rows, course), '결과/정한_것.csv': chosen_text([graph_chosen(course)[k] for k in default_graph_branch(course)])}))
    s_load = S('판단① 적재문 쓰기', '③ 계획 · ④ 구현',
               ('`결과/load.cypher`에 종류 · 관계마다 문장 하나(위에 `// 넣을 것: <종류 또는 관계>`, 행은 `$rows`)를 AI와 쓰고 `python show_result.py`를 실행합니다. '
                '행을 넘겨 실행하고 개수를 세는 것은 제공 코드가 합니다.' + ('' if change else ' 같은 적재를 한 번 더 해 늘지 않는지도 봅니다.')),
               (('같은 대상을 무엇으로 알아볼지(MERGE의 열쇠)와, 다시 적재할 때 이미 있는 대상의 값을 어떻게 할지 고릅니다 — 수정본으로 바뀐 값을 지킬지, 모델 파일(원자료) 값으로 통째로 되돌릴지. '
                 '고른 것을 내 말로 AI에게 말하면 AI가 문장으로 옮깁니다. ' if change else '같은 대상을 무엇으로 알아볼지(MERGE의 열쇠)를 정합니다. ')
                + 'ID와 관계의 시작 · 끝이 그래프의 무엇이 되는지도 내 말로 설명합니다.'),
               '4단계 칸의 「모델 파일 ↔ 랩 DB 개수」가 모두 「같음」이고' + ('' if change else ' 한 번 더 적재해도 늘지 않으며') + ', 문장마다 넘긴 행 수가 보입니다.',
               H('모델의 대상과 관계를 랩 DB에 옮기는 적재 문장을 종류 · 관계마다 쓴다', '`입력/schema.json`(종류 · 관계 · 방향), `결과/load.cypher` 첫 줄, 2단계 개수 표',
                 '이 랩 DB에만. 전체 삭제문 금지. 행은 $rows(노드는 속성 묶음, 관계는 a · b · props). 다시 실행해도 늘지 않게.'
                 + (' 다시 적재 때 값: 수정본 값을 지키면 {change_no}단계에서 고친 값이 그대로 남고, 원자료 값으로 통째로 되돌리면 결과 화면이 매번 적재 → 수정 순서로 돌아 {change_no}단계에서 다시 고쳐진다 — '
                    '어느 쪽이든 다시 열어도({save_no}단계) {change_no}단계 바뀐 노드 · 관계 수가 같아야 하고, 일부만 덮어써 수정본이 더한 값이 남으면 그 수가 줄어든다.' if change else ''),
                 '`결과/load.cypher`의 문장들', '4단계 개수 견줌과 한 번 더 실행한 뒤의 개수'),
               cmd=SHOW, why=WHY_G_PLAN, differ='개수가 다르거나 늘면 그 문장이 같은 대상을 무엇으로 알아보는지 AI에게 짚게 해 고칩니다.',
               answer=A('노드는 id로 MERGE하고 값은 처음 만들 때만 넣습니다(ON CREATE SET — 다시 적재해도 수정본이 고친 값을 되돌리지 않게). 관계는 양 끝 id로 찾은 뒤 같은 방식으로 MERGE합니다.',
                        paste('결과/load.cypher', load_text)))
    s_again = S('같은 적재 다시 실행', '⑤ 대조',
                '`python show_result.py`를 한 번 더 실행해 5단계 칸에서 같은 적재 전후의 개수를 봅니다.',
                '늘었으면 어느 대상이 왜 늘었는지 묻습니다.',
                '5단계 칸에 「늘어남 · 사라짐 · 값 바뀜 없음」이 보입니다.',
                H('같은 적재를 다시 해도 늘지 않는지 확인한다', '5단계 칸', '전체를 지우고 다시 넣지 않는다', '전후 개수와 `검증_기록.md` 개수 표', '두 번째 개수를 첫 실행과 견준다'),
                cmd=SHOW,
                why='다시 넣을 때마다 늘면 같은 설비가 둘로 보입니다.',
                differ='늘었으면 4단계 문장을 고치고 늘어난 대상만 지운 뒤 다시 실행합니다.',
                answer=A('4단계 정답의 적재문이면 두 번째 실행에서 늘어나는 것이 없습니다.', ask_ai('결과 화면 5단계의 전후 개수를 보고, 늘어난 종류가 있으면 load.cypher의 어느 문장 때문인지 짚어 줘. 파일은 바꾸지 마.')))
    queries = graph_queries(course)
    if practical:
        q_steps = [
            S('판단② 사용 설비와 공급 조건 조회', '④ ~ ⑥ 구현 · 대조 · 고침',
              '`결과/query.cypher`에 `// 질문 1` 조회(품번 하나 → 사용 설비 · 구성 요소와 공급사별 공급 조건, 승인 상태 · 출처 포함)를 AI와 쓰고 `python show_result.py`를 실행합니다.',
              '비승인 공급사를 어떻게 구별해 보일지와, `결과/정한_것.csv`의 결정대로 네 값 말고 무엇을 함께 돌려줄지 AI에게 말합니다. AI가 결정을 대신하면 돌려보냅니다.',
              '5단계 대조 표가 「같음」이고, 사용 설비 세 대와 세 공급 조건이 출처 줄과 함께 보이며, 비승인 공급사가 구별됩니다.',
              H('부품 하나의 사용 설비와 공급 조건을 한 번에 돌려주는 조회를 쓴다', '랩 DB 그래프, `입력/schema.json`의 방향, `결과/정한_것.csv` · `기대_답.csv`',
                '조회만. 출처는 그래프의 값을. 고르기 · 순위 금지. 결정대로.' + q_rules, '`// 질문 1` 조회와 결과 화면 표', '5단계 대조 표와 출처 몇 개의 원자료 줄'),
              cmd=SHOW,
              why=('공급 조건은 공급사와 부품 사이 관계의 값이라, 부품에서 설비 쪽과 공급사 쪽 두 길을 따라가야 한 번에 나옵니다. 무엇을 함께 돌려줄지는 이 결과를 쓰는 사람이 공급사를 무엇으로 견주는지에 따라 정하고, '
                   '7.4 정보를 함께 돌려주면 5단계 표에 입고 검사 · 비교 가산 비용 열이 더 생깁니다. ' + F.WHY_TABLE),
              differ=F.FIX_LOOP,
              answer=A('두 갈래 가운데 내 결정에 맞는 조회를 씁니다. 결과는 Neo4j Browser에 같은 조회를 붙여 넣어 표(Table)로도 볼 수 있습니다.',
                       paste('결과/query.cypher — 갈래: 네 값만', ANS.query_text([queries[1]['ㄱ']])), paste('결과/query.cypher — 갈래: 7.4 정보 함께', ANS.query_text([queries[1]['ㄴ']])),
                       apply={'결과/query.cypher': ANS.query_text([queries[1]['ㄴ']])})),
            S('판단③ 다른 표기와 없는 품번 구별', '④ ~ ⑥ 구현 · 대조 · 고침',
              '`결과/query.cypher`에 `// 질문 2` 조회(정식 · 예전 품번 · 다른 표기로 같은 부품을 찾고, 비슷한 다른 품번 · 없는 품번을 구별)를 더하고 `python show_result.py`를 실행합니다.',
              '원자료에 없는 품번에 무엇을 돌려줄지(0줄 또는 「없는 품번」 한 줄) 정합니다.',
              '6단계 대조 표가 「같음」이고, 예전 품번 · 다른 표기로 물어도 정식 품번과 같으며, 비슷한 다른 품번과 없는 품번이 구별됩니다.',
              H('어떻게 적어 물어도 같은 부품을 찾고 없는 것은 없다고 돌려주는 조회를 쓴다', '5단계 조회, 부품 속성, `결과/기대_답.csv`',
                '없는 품번에 값을 지어내지 않는다. 비슷한 다른 품번을 합치지 않는다.' + q_rules, '`// 질문 2` 조회와 결과 화면 표', '6단계 대조 표'),
              cmd=SHOW,
              why=('같은 부품을 예전 품번이나 다른 표기로 적은 자료가 있어, 정식 품번으로만 찾으면 다른 표기로 물은 사람은 「없음」을 받습니다. MATCH가 찾지 못하면 결과 줄이 0개로 나오므로, 없는 품번을 어떻게 보일지 함께 정해야 합니다.'),
              differ=F.FIX_LOOP,
              answer=A('부품의 다른 표기 목록(other_codes)으로도 찾고, OPTIONAL MATCH로 없는 품번도 한 줄을 돌려줍니다.',
                       paste('결과/query.cypher', ANS.query_text([queries[1]['ㄴ'], queries[2]]))))]
    else:
        q_steps = [
            S('판단② 설비별 센서 조회', '④ ~ ⑥ 구현 · 대조 · 고침',
              '`결과/query.cypher`에 `// 질문 1` 조회(설비 하나 → 구성 요소별 센서와 물리량 · 단위 · 한계, 구성 요소 · 센서 id 포함)를 AI와 쓰고 `python show_result.py`를 실행합니다.',
              '설비에 바로 붙은 센서와 한계 없는 센서를 어떻게 보일지 정합니다.',
              '6단계 대조 표가 「같음」이고, 한계 없는 센서가 0이 아니라 빈 값입니다.',
              H('설비 하나의 구성 요소별 센서를 조회한다', '랩 DB 그래프, `입력/schema.json`의 방향, `결과/기대_답.csv`',
                '조회만. 없는 한계를 0으로 보이지 않는다.' + q_rules, '`// 질문 1` 조회와 결과 화면 표(id 포함 — 10단계에서 씀)', '6단계 대조 표를 원자료 행과 견준다'),
              cmd=SHOW, why='MATCH는 관계의 종류 · 방향을 따라가므로 스키마와 다른 방향이면 비어 나옵니다.', differ=F.FIX_LOOP,
              answer=A('설비에서 구성 요소를 거치거나(1단계) 바로(0단계) 센서로 가는 길을 한 조회로 씁니다.', paste('결과/query.cypher', ANS.query_text([queries[1]])))),
            S('판단③ 설비별 교체 부품 조회', '④ ~ ⑥ 구현 · 대조 · 고침',
              '`결과/query.cypher`에 `// 질문 2` 조회(설비 하나 → 구성 요소마다 교체 부품)를 더하고 `python show_result.py`를 실행합니다.',
              '교체 부품이 없는 구성 요소를 빼는지 빈 칸으로 남기는지 정합니다.',
              '7단계 대조 표가 「같음」이고, 교체 부품 없는 구성 요소가 정한 대로 보입니다.',
              H('설비 하나의 구성 요소마다 교체 부품을 조회한다', '랩 DB 그래프, `결과/기대_답.csv`',
                '조회만. 없는 품번을 지어내지 않는다.' + q_rules, '`// 질문 2` 조회와 결과 화면 표', '7단계 대조 표를 교체부품 칸과 견준다'),
              cmd=SHOW,
              why='MATCH는 끝까지 이어지는 줄만 돌려주므로 교체 부품 없는 구성 요소는 빠집니다.', differ=F.FIX_LOOP,
              answer=A('부품 쪽을 OPTIONAL MATCH로 두면 교체 부품이 없는 구성 요소도 빈 칸으로 남습니다.', paste('결과/query.cypher', ANS.query_text([queries[1], queries[2]])))),
            S('판단④ 부품의 사용 설비 조회', '④ ~ ⑥ 구현 · 대조 · 고침',
              '`결과/query.cypher`에 `// 질문 3` 조회(품번이나 표기 하나 → 쓰는 설비 · 구성 요소)를 더하고 `python show_result.py`를 실행합니다. 설비 상태는 `결과/정한_것.csv`의 결정대로 반영합니다.',
              '다른 표기 · 없는 품번에 무엇을 돌려줄지 정하고, 가동이 아닌 설비가 「시점과 상태」 결정대로 보이는지 묻습니다(보전팀은 지금 가동하는 설비의 예비품을 준비합니다). AI가 결정을 대신하면 돌려보냅니다.',
              '8단계 대조 표가 「같음」이고, 가동이 아닌 설비의 모습(빠짐 · 상태와 함께)이 내 결정과 맞으며, 없는 품번이 구별됩니다.',
              H('부품 하나를 쓰는 설비와 구성 요소를 조회한다', '랩 DB 그래프(설비 상태 포함), `결과/정한_것.csv` · `기대_답.csv`',
                '조회만. 없는 품번에 값을 지어내지 않는다. 상태는 결정대로.' + q_rules, '`// 질문 3` 조회와 결과 화면 표', '8단계 대조 표'),
              cmd=SHOW,
              why='부품에서 거꾸로 따라가면 쓰는 설비가 모이고, 설비 상태는 조건(WHERE)이나 돌려줄 값으로 씁니다.',
              differ=F.FIX_LOOP,
              answer=A('두 갈래 가운데 내 결정에 맞는 조회를 씁니다.',
                       paste('결과/query.cypher — 갈래: 상태와 함께', ANS.query_text([queries[1], queries[2], ANS.QUERY_PART_USAGE['상태와 함께']])),
                       paste('결과/query.cypher — 갈래: 가동 설비만', ANS.query_text([queries[1], queries[2], ANS.QUERY_PART_USAGE['빠짐']])),
                       apply={'결과/query.cypher': ANS.query_text([queries[1], queries[2], ANS.QUERY_PART_USAGE['상태와 함께']])}))]
    s_change = S('판단⑤ 수정본 반영하기', '④ ~ ⑥ 구현 · 대조 · 고침',
                 '`결과/update.cypher`에 수정본 줄마다 필요한 대상 · 관계만 고치는 문장을 AI와 쓰고 `python show_result.py`를 실행합니다. 전후 비교와 같은 수정 한 번 더는 제공 코드가 합니다.',
                 '불용으로 바뀐 설비를 `결과/정한_것.csv`의 「불용 결정 설비」 결정대로 반영했는지, 「삭제」 줄이 원자료의 어느 행을 가리키고 그래프에서 무엇을 바꿔야 하는지 묻습니다. AI가 결정을 대신하면 돌려보냅니다.',
                 '9단계 바뀜을 수정본 줄로 설명할 수 있고, 실제 센서가 사라지지 않았으며, 이름이 바뀐 설비의 ID가 그대로이고, 한 번 더 해도 바뀌지 않습니다.',
                 H('전체를 지우지 않고 수정본이 고친 것만 반영한다', f'`{change_dir}`, `입력/자료/`의 같은 행, `결과/정한_것.csv`',
                   '전체 삭제문 금지. ID를 바꾸지 않는다. 결정대로. 문장은 ;로 끝낸다.', '`결과/update.cypher`의 문장들', '9단계 바뀜 표를 수정본 줄과 견준다'),
                 cmd=SHOW,
                 why=('전체를 지우고 다시 넣으면 이 ID에 걸린 연결이 끊깁니다. 값은 ID로 찾아 SET으로 고치고, DETACH DELETE 전에는 걸린 대상을 먼저 조회합니다.'),
                 differ='설명할 수 없는 바뀜이나 사라진 실제 대상이 있으면, 바뀐 대상 목록과 수정본 줄을 함께 전해 고칩니다.',
                 answer=A('「삭제」 줄은 같은 센서를 점검표에서 옮겨 적은 중복 행 정리라 그래프의 센서는 그대로 둡니다. 불용 결정 설비는 결정 갈래대로 남기거나 지웁니다.',
                          paste('결과/update.cypher — 갈래: 상태로 남김', ANS.UPDATE_INTEGRATED['남김']), paste('결과/update.cypher — 갈래: 하위 대상과 지움', ANS.UPDATE_INTEGRATED['삭제']),
                          apply={'결과/update.cypher': ANS.UPDATE_INTEGRATED['남김']}))
    s_portal = S('포털 기준 지도와 비교', '⑤ 대조',
                 '10단계 칸의 「내 그래프 — HYD-01에서 시작하는 관계」와 아래 포털 기준 지도 표를 나란히 보고, 식별자와 관계의 시작 · 끝을 `결과/검증_기록.md`에 적습니다. 포털은 다시 열지 않습니다.',
                 '어디서 같고 다른지, 다른 곳은 어느 쪽 설계에서 왔는지 적습니다.',
                 '설비 · 쿨러 · 센서마다 두 쪽의 식별자와 방향이 기록 표에 있고, 다른 까닭을 말할 수 있습니다.',
                 H('내 그래프와 포털 기준 지도의 식별자 · 관계 방향을 견준다', '아래 기준 지도 표, 10단계 칸', '포털 DB에 접속하지 않는다. 두 표로만 적는다.',
                   '「대상 · 포털 · 내 그래프 · 같음/다름 · 까닭」 표', '표의 줄마다 두 표를 다시 본다'),
                 cmd=SHOW,
                 why='두 시스템이 다른 식별자 · 방향으로 그리면 결과를 이을 때 같은 대상인지 알 수 없습니다.', differ='두 표와 기록이 다르면 그 줄을 고칩니다.',
                 answer=A('관계 이름(HAS_COMPONENT · MONITORED_BY · OBSERVES)과 방향은 같습니다. 다른 곳은 식별자 꼴(포털은 소문자 접두어 — 내 그래프는 설비코드를 붙인 ID), '
                          '포털의 구성 요소 · 센서(comp:cooler · sen:ts1)는 여러 설비가 한 노드를 함께 쓰고 내 그래프는 설비마다 따로 둔다는 점, 구성 요소 다음 단계(포털은 상태 변수, 내 그래프는 물리량)입니다.',
                          ask_ai('결과 화면 10단계의 내 그래프 관계와 가이드의 포털 기준 지도 표를 줄마다 견줘, 식별자와 관계 방향이 같은 곳 · 다른 곳을 표로 짚어 줘. 파일은 바꾸지 마.')))
    reopen_step = 6 if practical else 8
    files_kept = '적재 · 수정 · 조회' if change else '적재 · 조회'
    dates = '기준일 · 수정본 날짜' if change else '기준일'
    s_save = S('저장하고 다시 열기', '⑦ 저장 · 다시 열기',
               f'{files_kept} 파일과 기록을 저장하고 폴더를 닫았다 다시 연 뒤 `python lab_db.py` · `python show_result.py`를 실행하고, 기록 끝에 {dates} · 저장 시점 · 확인하지 못한 점을 적습니다.',
               '확인하지 못한 점을 정합니다.',
               f'다시 연 뒤에도 단계 띠와 {reopen_step}단계 대조 표' + (', 9단계 표(바뀐 노드 · 관계 수)' if change else '') + '가 같고, `검증_기록.md`의 개수 표 · 「기대 답과 실제 결과」가 실제 값으로 채워져 있습니다.',
               cmd='python lab_db.py\npython show_result.py',
               why=F.WHY_SAVE,
               differ=('포트가 바뀔 수 있으니 열어 둔 Neo4j Browser 탭은 닫고 새 창을 씁니다. 「이 PC의 Docker에 없습니다」면 새 빈 DB라 적재부터 다시 됩니다.'))
    if practical:
        steps = [s_tree, s_look, s_req, s_load, *q_steps, s_save]
    else:
        steps = [s_tree, s_look, s_req, s_load, s_again, *q_steps, s_change, s_portal, s_save]
        # 적재 단계 힌트가 가리키는 단계 번호는 이 랩의 실제 차례에서 잇는다
        s_load['hint'] = {k: v.format(change_no=steps.index(s_change) + 1, save_no=steps.index(s_save) + 1) for k, v in s_load['hint'].items()}
    user = ('아래 질문의 답은 보전 · 구매 담당이 예비품을 쓰는 설비와 공급사별 조건을 함께 볼 때 씁니다. 고르는 것은 구매 담당입니다.' if practical else
            '아래 질문의 답은 보전팀이 지금 가동하는 설비의 예비품 준비를 정할 때 씁니다.')
    questions = (['세 설비가 함께 쓰는 펌프 축 씰 키트를 어느 설비 · 구성 요소에서 쓰고, 기준일의 세 공급 조건(승인 여부 · 단가 · 불량률 · 납기)은 무엇이며 각 값은 어느 파일 · 어느 줄에서 왔는가?',
                  '이름이 비슷한 다른 품번, 예전 품번이나 다른 표기, 원자료에 없는 품번으로 물으면 결과가 서로 구별되는가? 비승인 공급사는 승인 상태와 함께 구별되는가?',
                  '같은 적재를 다시 실행해도 대상과 관계가 늘지 않는가?'] if practical else
                 ['설비별로 어떤 구성 요소에 어떤 센서 · 계산값 · 설정값이 붙어 있고, 각 센서의 물리량 · 단위 · 한계는 무엇인가?',
                  '설비별로 구성 요소마다 어떤 교체 부품이 들어가고, 여러 설비가 함께 쓰는 부품은 어느 설비 · 구성 요소에서 쓰는가? 다른 표기로 적힌 품번이나 원자료에 없는 품번으로 물으면 결과가 어떻게 구별되는가?',
                  '수정본을 반영한 뒤에도 같은 ID가 유지되고, 같은 적재를 다시 실행해도 대상과 관계가 늘지 않는가?',
                  '포털 실습에서 본 기준 지도와 견주면 내 그래프의 식별자 · 관계 방향이 어디서 같고 어디서 다른가?'])
    decide = ([('쓰는 사람에 따라 갈리는 답', '구매 담당이 공급사를 비교할 때 승인 여부 · 단가 · 불량률 · 납기 말고도 함께 봐야 할 것이 모델에 있으면, 그것을 조회 결과에 함께 돌려줄지와 어떻게 보일지')] if practical else
              [('시점과 상태', '설비 대장의 상태와 수정본에서 바뀐 상태를 그래프에 어떻게 반영하고, 「지금 가동하는 설비」를 묻는 부품의 사용 설비 조회에 어떻게 드러낼지(답에서 빠지는지, 상태와 함께 보이는지)'),
               ('불용 결정 설비', '수정본이 불용으로 바꾼 설비를 상태만 바꿔 남길지, 그 설비에만 딸린 구성 요소 · 센서와 함께 그래프에서 지울지')])
    outside = (['공급사를 고르거나 점수 · 순위를 매기는 일', '입고 이력으로 실측 납기를 세는 일'] if practical else ['공급 조건 · 입고 이력의 적재와 조회']) + \
              ['모델의 종류 · 속성 · 관계 정의를 새로 바꾸는 일(이상한 곳은 `결과/검증_기록.md`에 적습니다)', '포털 DB에 접속하거나 포털 자료를 랩 DB에 넣는 일']
    cases = (['세 설비가 함께 쓰는 부품', '비슷한 이름의 다른 품번', '예전 품번 · 다른 표기', '원자료에 없는 품번', '비승인 · 조건이 붙은 공급사', '공급사 이름 표기(견적표 · 승인 목록)',
              '같은 적재 두 번'] if practical else
             ['설비별 구성 요소 · 센서 개수', '한계 방향과 한계 없음', '설비에 바로 붙은 센서', '설비별 교체 부품과 교체 부품이 없는 구성 요소', '공용 부품과 전용 부품',
              '상태가 가동이 아닌 설비도 쓰는 공용 부품', '다른 표기 · 없는 품번',
              '수정본의 이름 변경 · 상태 변경 · 값 보완 · 줄 삭제가 바꾸는 그래프의 대상 · 관계', '반영 뒤 원자료와 다시 센 개수 · 값(「삭제」 줄이 걸린 설비 포함)',
              '같은 적재 두 번 · 같은 수정 두 번'])
    my_model = ('내 모델은 고를 때만 `결과/내_모델/`에 복사해 씁니다(형식 · ID가 맞는지 먼저 보고, 다르면 내 정의로 조회). 없어도 제공 모델로 끝까지 합니다.')
    after = AFTER_LAB[course]
    save = (f'{files_kept} 파일과 `검증_기록.md` · `정한_것.csv` · `기대_답.csv`를 함께 보관합니다. 기록에는 반영한 자료의 {"기준일과 수정본 날짜를" if change else "기준일을"} 적습니다. '
            + (f'다음 실습 「{after}」는 이 설비 모델의 ID에 작업 절차와 판단 조건을 잇습니다. 그 실습도 제공된 모델로 시작할 수 있으므로 이 결과는 골라서 가져갑니다. ' if not practical else
               f'다음 실습 「{after}」는 제공된 자료로 시작하므로 이 결과는 참고로 보관합니다. ') + F.USB)
    record = F.req_template('실습 확인 기록', graph_counts(change) + (
        '' if practical else
        '## 포털 기준 지도와 비교\n\n| 대상 | 포털의 식별자 · 관계 방향 | 내 그래프의 식별자 · 관계 방향 | 같음 · 다름 | 다른 까닭 |\n|---|---|---|---|---|\n| | | | | |\n\n'))
    record = record.replace('## 사용할 자료와 기준일\n\n', f'## 사용한 입력과 랩 DB\n\n- 사용한 모델(제공된 모델 · 내 모델):\n- 랩 DB 주소(인증값 제외):\n- {dates}:\n\n')
    record = record.replace('- 기준일:\n', f'- {dates}:\n')
    design = design_integrated() if not practical else design_practical()
    files = {'결과/검증_기록.md': record, '결과/정한_것.csv': F.CHOSEN_TEMPLATE,
             '결과/기대_답.csv': F.blank_csv(ANS.GRAPH_EXPECT_COLUMNS, ANS.GRAPH_EXPECT_EXPLAIN[course]),
             '결과/load.cypher': ANS.LOAD_BLANK, '결과/query.cypher': ANS.QUERY_BLANK,
             '결과/README.md': (f'정할 자리(적재문 · 조회문{" · 수정문" if change else ""} · 기대 답 표)를 채우고 `python show_result.py`를 실행하면 제공 코드가 랩 DB에 실행하고 결과 화면 보기.html을 씁니다. 내 모델을 쓰면 결과/내_모델/에 복사해 둡니다.\n'
                                f'다시 열 때는 `python lab_db.py`로 랩 DB를 다시 켜고 `python show_result.py`를 실행합니다.\n'),
             '입력/README.md': f'제공된 {model}(schema.json · graph.json), 그 원자료(자료/), ' + ('기준일 뒤 수정본(자료_변경분/), ' if change else '') + '제공된 모델의 질문(요구사항.md)과 자료 처리 근거(자료_검토.md)입니다. 이 폴더는 읽기만 합니다.\n',
             '입력/요구사항.md': '# 제공된 모델이 답하는 질문\n\n' + '\n'.join('- ' + q for q in design['questions']) + '\n',
             '입력/자료_검토.md': provided_basis(practical)}
    if change:
        files['결과/update.cypher'] = ANS.UPDATE_BLANK
    return dict(
        title=title, course=course, rec='결과/검증_기록.md', readonly='`입력/`(원자료' + (' · 수정본' if change else '') + ' 포함) · 제공 파일(`show_result.py` · `lab_steps.py` · `lab_cypher.py` · `lab_db.py` · `check.py`)이', decide_step=2,
        goal=[('「설비·부품·공급 정보를 연결하는 온톨로지 설계하기」에서는 부품마다 쓰는 설비와 공급사별 조건을 모델에 넣었습니다. ' if practical else
               f'「현장 정보를 체계화하는 온톨로지 직접 설계하기」에서는 설비 · 센서 · 부품을 {CLASS_LINK} · 속성 · 관계로 정의해 모델을 만들었습니다. ')
              + f'이번에는 제공된 {model}(또는 내 모델)을 이 폴더 전용 랩 DB(그래프 DB)에 적재하고, 질문마다 조회문을 만들어 원자료와 대조합니다. '
              + '파일 읽기 · 실행 · 개수 세기 · 전후 비교는 제공 코드가 하고, 나는 같은 대상을 알아보는 열쇠와 조회가 돌려줄 것' + (', 수정본 반영' if change else '') + '을 정해 문장으로 씁니다.',
              F.STAGE_LINE.format(what='구현과 검증')],
        make='만들 것: 적재문(`결과/load.cypher`), 질문별 조회문(`결과/query.cypher`), ' + ('수정본을 반영하는 수정문(`결과/update.cypher`), ' if change else '') + '`결과/기대_답.csv` · `결과/정한_것.csv` · `결과/검증_기록.md`.',
        start=[f'`입력/schema.json` · `입력/graph.json` — 제공된 {model}. ' + (
                   '설비 7대 · 구성 요소 · 센서 · 부품 · 공급사와 그 연결이 들어 있고, 공급 조건마다 승인 여부 · 단가 · 불량률 · 납기와 값마다 출처가 붙어 있습니다. 그 밖에 붙은 속성은 `입력/schema.json`에서 봅니다.' if practical else
                   '설비 7대 · 구성 요소 · 센서 · 물리량 · 부품과 그 연결이 들어 있습니다.'),
               f'`입력/자료/` — 그 모델의 원자료(기준일 {D.REF_DATE}).' + (f' `{change_dir}` — 기준일 뒤 담당자들이 고친 줄만 모은 수정본.' if change else ''),
               '`입력/요구사항.md` · `입력/자료_검토.md` — 제공된 모델이 답하는 질문과 자료 처리 근거.',
               '`lab_db.py` — 이 폴더 전용 랩 DB를 켜는 도구. `lab_cypher.py` — 적재 · 조회 문장을 랩 DB에 실행하고 세는 제공 도구. `check.py` — 제공 파일 · 기록 검사.',
               SHOW_LINE, '`결과/` — 정할 자리(첫 줄에 「제공 빈 틀」이 있는 문장 · 표 파일)와 기록.', RULES_LINE, my_model],
        tools=[], user=user, questions=questions, decide=decide, outside=outside,
        formats=[graph_format(change)], steps=steps, cases=cases,
        commands='python lab_db.py\npython show_result.py\npython check.py',
        done=('형식 검사나 실행 성공만으로 완료하지 않습니다. 결과 화면에서 질문마다 원자료에서 먼저 적은 기대 답과 실제 조회 결과가 맞고, '
              + ('같은 적재 · 같은 수정을' if change else '같은 적재를') + ' 다시 해도 개수가 같으며, '
              '`결과/정한_것.csv`의 지점마다 근거 줄과 그 선택으로 바뀌는 답을 설명할 수 있으면 완료입니다. 고친 점과 확인하지 못한 점은 `결과/검증_기록.md`에 짧게 남깁니다.'),
        save=save, reopen=f'결과 화면의 단계 띠와 {reopen_step}단계 대조 표, `검증_기록.md`의 {dates} · 저장 시점 · 확인하지 못한 점',
        tree=F.tree(LAB4, [('.github/', '작업 규칙'), ('결과/', '정할 자리 · 기록'),
                           ('입력/', '제공 모델 · 원자료' + (' · 수정본' if change else '') + '(읽기만)'),
                           ('AGENTS.md', '작업 규칙'), ('check.py', '검사'), ('CLAUDE.md', '작업 규칙'), ('lab_cypher.py', '적재 · 조회 실행(제공)'),
                           ('lab_db.py', '랩 DB 켜기'), ('lab_steps.py', '결과 화면 단계(제공)'), ('show_result.py', '결과 화면(제공)'), ('START.md', '과제와 진행 단계'), ('준비_안내.md', '처음 볼 곳')]),
        lead=(f'{model}을 이 폴더 전용 그래프 DB에 적재하고 ' + ('부품의 사용 설비와 공급 조건을 돌려주는 조회문을 원자료와 대조합니다.' if practical else
              '질문마다 조회문을 원자료와 대조하며, 수정본 반영 뒤 ID와 개수를 확인하고 포털 기준 지도와 견줍니다.')),
        need='VS Code와 Python, 로그인해 둔 Codex 또는 GitHub Copilot, 랩 DB를 켤 Docker Desktop.',
        terms=('**적재**는 모델 파일의 대상과 관계를 그래프 DB에 넣는 일' + (', **수정본**은 기준일 뒤 고친 줄만 모은 자료' if change else '')
               + ', **정할 자리**는 `결과/`에서 첫 줄에 「제공 빈 틀」이 있는 파일입니다.'),
        first_more=[my_model],
        guide_extra=({0: ['docker'], 1: ['run_approve']} if practical else
                     {0: ['terminal', 'docker', 'result'], 1: ['ai', 'review', 'run_approve'], steps.index(s_portal): [portal_table()]}),
        tools_from=design_practical()['title'] if practical else None,   # 실전 한 칸의 둘째 랩 — 도구 사용법은 앞 랩 가이드
        guide_after={0: ['db', '<p><b>그래프 모양</b> 적재 뒤 Neo4j Browser에 <code>MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 50</code>을 붙여 넣고 <b>Run</b>을 누릅니다.</p>', 'db_stuck']},
        provided=['lab_cypher.py', 'lab_db.py'], kind='graph_practical' if practical else 'graph_integrated', change=change,
        ai_wait=(8.55, '리허설 50L 실측 — 2026-11-05') if practical else (7.1, '리허설 50L 실측 — 2026-11-05'),
        files=files)


WHY_G_PLAN = ('스키마의 종류(이론의 클래스) 이름은 그래프의 레이블이 되고, 대상 하나(이론의 인스턴스)를 저장한 것이 노드입니다. ID는 노드의 속성, 관계 정의의 시작 · 끝은 관계의 방향이 됩니다. '
              'CREATE는 실행할 때마다 새로 만들고, MERGE는 같은 것이 있으면 찾고 없으면 만듭니다. 그래서 다시 실행해도 늘지 않으려면 무엇으로 「같은 것」을 알아볼지 먼저 정해야 합니다. '
              '다시 넣을 때 값을 덮어쓰면 수정본으로 고친 값이 되돌아가고, 처음 만들 때만 넣으면 그대로 남습니다.')


def default_graph_branch(course):
    """정답 보기의 apply에 쓰는 강사 참조 기본 갈래(정한_것.csv 행들)."""
    return ['ㄴ'] if course == '실전반' else ['상태와 함께', '수정본 남김']


def graph_chosen(course):
    if course == '실전반':
        return {'ㄴ': ['쓰는 사람에 따라 갈리는 답', '7.4 정보를 함께 돌려줌', '입력/자료/구매기준서_PR-07_발췌.md:30', 'A정밀 줄에 입고 전수 검사 · +20만 원 칸이 붙음'],
                'ㄱ': ['쓰는 사람에 따라 갈리는 답', '승인 여부 · 단가 · 불량률 · 납기만', '입력/자료/구매기준서_PR-07_발췌.md:27', 'A정밀 줄은 35만 원 · 0.12만 보임']}
    return {'상태와 함께': ['시점과 상태', '빼지 않고 상태와 함께', '입력/자료/설비_대장.csv:9', 'P-RTN-FLT 사용 설비가 HYD-07(예비 · 불용)을 상태와 함께 다섯 대'],
            '가동 설비만': ['시점과 상태', '가동 설비만', '입력/자료/설비_대장.csv:9', 'P-RTN-FLT 사용 설비가 가동 네 대'],
            '수정본 남김': ['불용 결정 설비', '상태로 남김', f'입력/자료_변경분/{D.CHANGE_DATE}_수정본/설비_대장_변경.csv:3', 'HYD-07이 「불용(매각 예정)」으로 남음'],
            '수정본 지움': ['불용 결정 설비', '하위 대상과 지움', f'입력/자료_변경분/{D.CHANGE_DATE}_수정본/설비_대장_변경.csv:3', 'HYD-07과 그 구성 요소 · 센서가 사라짐']}


def graph_queries(course):
    import session2_answers as ANS
    return ANS.QUERY_PRACTICAL if course == '실전반' else ANS.QUERY_INTEGRATED


def graph_expect_rows(course, graph):
    """실습4 기대 답 예 — 입력 모델(강사 참조)에서. 볼_열은 정답 보기 조회문이 돌려주는 열."""
    label = {n['props']['id']: n['labels'][0] for n in graph['nodes']}
    props = {n['props']['id']: n['props'] for n in graph['nodes']}
    rows = []
    if course == '실전반':
        sup = sorted(props[r['a']]['name'] for r in graph['rels'] if r['type'] == 'SUPPLIES' and r['b'] == 'P-PMP-SEAL')
        rows.append(['1', 'P-PMP-SEAL', 'supplier', ' · '.join(sup), '입력/자료/공급_조건.csv:2 · 3 · 4'])
        rows.append(['2', 'PS-4510', 'found_by', ' · '.join(['다른 표기'] * len(sup)), '입력/자료/품번_교차표.csv'])
        rows.append(['2', 'P-PMP-SEAL-X', 'found_by', '원자료에 없는 품번', '원자료에 없음'])
        return rows
    owner = {r['b']: r['a'] for r in graph['rels'] if r['type'] == 'HAS_COMPONENT'}
    tags = sorted(props[r['b']]['tag'] for r in graph['rels'] if r['type'] == 'MONITORED_BY' and (r['a'] == 'HYD-01' or owner.get(r['a']) == 'HYD-01'))
    rows.append(['1', 'HYD-01', 'tag', ' · '.join(tags), '입력/자료/센서_목록.csv:2~21'])
    parts = sorted(r['b'] for r in graph['rels'] if r['type'] == 'USES_PART' and owner.get(r['a']) == 'HYD-07')
    comps = [r['b'] for r in graph['rels'] if r['type'] == 'HAS_COMPONENT' and r['a'] == 'HYD-07']
    rows.append(['2', 'HYD-07', 'part', ' · '.join(parts + ['없음'] * (len(comps) - len(parts))), '입력/자료/구성요소_목록.csv:66~70'])
    users = sorted({owner[r['a']] for r in graph['rels'] if r['type'] == 'USES_PART' and r['b'] == 'P-RTN-FLT'})
    rows.append(['3', 'RF-10', 'asset', ' · '.join(users), '입력/자료/품번_교차표.csv · 구성요소_목록.csv 교체부품 칸'])
    rows.append(['3', 'P-PMP-SEAL-X', 'note', '원자료에 없는 품번', '원자료에 없음'])
    return rows


def graph_expect_text(rows, course):
    import session2_answers as ANS
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator='\n')
    w.writerow(ANS.GRAPH_EXPECT_COLUMNS)
    for r in rows:
        w.writerow(r)
    return f'# {F.MARK} — {ANS.GRAPH_EXPECT_EXPLAIN[course]}\n' + buf.getvalue()


LABS = {3: lambda course: design_practical() if course == '실전반' else design_integrated(), 4: graph_lab}


def checker_for(folder, L):
    """check.py — 제공 파일 보호(계약 6) · 정한_것.csv 칸 검사(계약 5), 설계 랩은 그 뒤에 모델 구조 검사."""
    guard = F.provided_guard(folder, ['show_result.py', 'lab_steps.py', *L['provided']])
    head = ('"""제공 파일 · 기록 · 결과 구조 검사. 생성 · 수정 · DB 접속을 하지 않는다. 답이 맞는지는 보지 않는다 — 결과 화면에서 기대 답과 견준다."""\n'
            'from pathlib import Path\nimport sys\n' + guard + F.CHOSEN_CHECK +
            '_root = Path(__file__).resolve().parent\n_pre = provided_errors(_root) + chosen_errors(_root)\n'
            "for _e in _pre:\n    print('확인 필요: ' + _e)\n")
    if L['kind'].startswith('graph'):
        return head + "if _pre:\n    sys.exit(1)\nprint('제공 파일 · 기록 검사 통과. 질문별 답은 결과 화면에서 기대 답과 견줍니다.')\n"
    body = CHECKER_SUPPLY if L['kind'] == 'design_practical' else CHECKER
    body = body.replace("if errors:\n    print(f'구조 확인 필요", "errors=_pre+errors\nif errors:\n    print(f'구조 확인 필요", 1)
    body = body.replace("if missing:\n", "if missing:\n    if _pre:sys.exit(1)\n", 1)
    return head + body


def build_lab(folder, L):
    """START · 작업 규칙 · 준비 안내 · 제공 코드 · 정할 자리 빈 틀 · check.py, 그리고 랩 폴더 밖 가이드."""
    import session2_steps as STEPS
    F.write_rules(folder)
    for name, text in L['files'].items():
        F.write(folder/name, text)
    for name, src in {'model_tool.py': 'session2_model_tool.py', 'supply_tool.py': 'session2_supply_tool.py', 'lab_cypher.py': 'lab_cypher.py'}.items():
        if name in L['provided']:
            F.write(folder/name, (TOOLS/src).read_text(encoding='utf-8'))
    if 'lab_db.py' in L['provided']:
        F.write(folder/'lab_db.py', (TOOLS/'lab_db.py').read_text(encoding='utf-8'))
    F.write_provided(folder, STEPS.render(L['kind'], L['title'], [s['name'] for s in L['steps']], L.get('change', False)))
    F.write(folder/'START.md', F.step_start(L))
    F.write(folder/'준비_안내.md', '# 실습 준비\n\nVS Code에서 이 파일이 들어 있는 폴더를 연 뒤 [START.md](START.md)의 목표와 질문을 확인하세요. 단계별 안내는 「실습 시작」 도구가 이 폴더 옆에 내려 둔 가이드(노션 「가이드문서」에도 있음)에 있습니다.\n')
    F.write(folder/'check.py', checker_for(folder, L))
    F.write_guide(folder, F.step_guide(L), L.get('ai_wait'))


def clean_generated(folder):
    """이 생성기가 쓰는 자리를 새로 만든다 — 옛 판의 생성물(자료 · 입력 자료 · 결과 빈 틀 · 옛 가이드 · 제공 파일)을 지운다. 학생 작업 폴더가 아니라 산출물 폴더다."""
    reset_generated(folder)
    result = folder/'결과'
    if result.is_dir():
        shutil.rmtree(result)
    for name in ['guide.html', '안내.html', 'check.py', 'model_tool.py', 'supply_tool.py', 'lab_cypher.py', 'show_result.py', 'lab_steps.py']:
        (folder/name).unlink(missing_ok=True)


def main():
    import sys as _sys
    only = None
    if '--lab' in _sys.argv:
        only = _sys.argv[_sys.argv.index('--lab') + 1]
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
            lab_id = f'{slug}-02-' + ('ontology' if number == 3 else 'graph')
            if only and only != lab_id:
                continue
            folder = OUT/course/'실습/02회차/랩'/name
            L = LABS[number](course)
            keep_drawing = (folder/'입력/관계그림.json').read_bytes() if (folder/'입력/관계그림.json').is_file() else None
            clean_generated(folder)
            for sub in ['입력', '결과']:
                (folder/sub).mkdir(parents=True, exist_ok=True)
            if number == 3:
                if practical:
                    D.write_sources(folder/'자료', practical=True)
                    dump(folder/'입력/schema.json', student_schema(base_schema)); dump(folder/'입력/graph.json', base_graph)
                    (folder/'입력/관계그림.json').unlink(missing_ok=True)
                elif keep_drawing is None:
                    raise FileNotFoundError('1회차 관계 그림 입력이 없습니다: ' + str(folder))
                else:
                    (folder/'입력/관계그림.json').write_bytes(keep_drawing)
            else:
                schema, graph = reference_model(practical, LAB4_INPUT_BRANCH[course])
                dump(folder/'입력/schema.json', student_schema(schema)); dump(folder/'입력/graph.json', graph)
                D.write_sources(folder/'입력/자료', practical)
                if not practical:
                    D.write_changes(folder/'입력/자료_변경분'/f'{D.CHANGE_DATE}_수정본')
            build_lab(folder, L)
            pack(folder)
            catalog.append(entry(lab_id, course, '온라인 02회차', L['title'], LAB_VERSION.get(lab_id, VERSION), folder))
    register(catalog)
    print(f'2회차 설계 · 구현 랩 {len(catalog)}개, ZIP {len(catalog)}개, 가이드(폴더 밖) {len(catalog)}개 생성')


if __name__ == '__main__':
    main()
