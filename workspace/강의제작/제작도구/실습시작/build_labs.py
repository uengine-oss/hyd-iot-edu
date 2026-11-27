"""온라인 2회차 실습3 · 4(두 과정)의 랩 정의 · 원자료 해석 · 정답과 강사 참조 모델(reference/)을 둔다.

2회차 실습3 · 4 원자료는 data_session2.py가 만든다(가상 사례, 고정 시드). 통합반은 실습 랩 규모, 실전반은 공장 규모이고(코딩랩 K-3),
통합반 것은 `with data_session2.for_course('통합반'):` 안에서 부른다. 랩 정의(design_integrated · graph_lab)는
새 프로젝트 생성기(build_session2_projects.py — 실전반 몫은 session2_factory*.py)가 입력으로 쓰고, 학생 폴더 · ZIP · package-index는 그 생성기가 쓴다.
이 파일을 직접 돌리면(`--reference`) 강사 참조 모델만 쓰고, 그 밖에는 새 생성기 이름을 대며 멈춘다.
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

def write(path, text):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(text,encoding='utf-8',newline='\n')

def dump(path, value):
    write(path,json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def rows(name, folder=None):
    if folder is None:
        return list(csv.DictReader(io.StringIO(D.source_texts()[name])))
    with (folder/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def numbered(name):
    """원자료 행과 편집기에 보이는 줄 번호(머리줄이 1행)."""
    return list(enumerate(rows(name), 2))


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
UNIT={'l/min':('L/min',1),'L/min':('L/min',1),'W':('kW',0.001),'kPa':('bar',0.01),'MPa':('bar',10)}

def comp_key(text,keys):
    key=NAME_ALIAS.get(text.strip())
    if key is None and text.strip()=='펌프':key='pump-a' if 'pump-a' in keys else 'pump'
    if key not in keys:raise ValueError(f'구성요소 이름을 풀지 못함: {text!r} (후보 {sorted(keys)})')
    return key

def model_match(model,applies):
    if applies=='전 모델':return True
    head,*rest=applies.split('·');prefix=head.rsplit('-',1)[0]+'-'
    return model in [head,*[prefix+x for x in rest]]

# 설비 판단의 강사 참조 갈래(REFERENCE_BRANCHES 위 주석): (같은 규격의 다른 사내 품번, 품번이 적히지 않은 교체부품 칸, 구성 요소 자리와 그 실물, 같은 물리량의 범위).
# 앞 둘은 모든 갈래가 「따로 · 이음」이다 — 통합반 결정 지점은 뒤 둘뿐이고(실습 랩 규모에는 앞 둘이 갈릴 자료가 없다), 실전반 제공 모델은 E 하나다.
POLICY = {'A': ('따로', '이음', '한 대상', '종류'), 'B': ('따로', '이음', '한 대상', '자리'), 'C': ('따로', '이음', '나눔', '종류'), 'E': ('따로', '이음', '나눔', '자리')}


def policy(branch, supply=False):
    """그 갈래의 설비 판단. 공급 갈래(실전반)는 제공 설비 모델의 판단(PROVIDED_BRANCH) 위에 선다."""
    return POLICY['E' if supply or branch not in POLICY else branch]


def legacy_rows(assets):
    """설비 대장의 옛 코드 줄: 다른 줄과 기능위치 · 일련번호가 같고 가동 중이 아닌 줄 → {옛 코드: 지금 코드}. 상태 글자로 정하지 않는다(M1)."""
    out = {}
    for a in assets:
        same = [x for x in assets if x is not a and x['기능위치'] == a['기능위치'] and x['일련번호'] == a['일련번호']]
        if same and a['상태'] != '가동' and any(x['상태'] == '가동' for x in same):
            out[a['설비코드']] = next(x['설비코드'] for x in same if x['상태'] == '가동')
    return out


def spare_key(row):
    """예비품 목록 쓰는곳 칸 → 구성 요소 키."""
    return NAME_ALIAS.get(row['쓰는곳'], 'pump-a' if row['쓰는곳'] == '주 펌프 A' else ('pump' if row['쓰는곳'] == '펌프' else None))


def resolve_part(text,model,key,parts,cross,mode='이음',siblings=()):
    """교체부품 칸 → 사내 품번(str) · None(잇지 않음) · 후보 목록(list — 확인 필요).
    품번 · 교차표로 풀리는 칸은 갈래와 상관없이 그 품번이다. 풀리지 않는 칸(빈칸 · 품명만)은 같은 모델에 적용되고 쓰는곳이 같은 예비품(후보)으로 본다:
    mode '이음' = 후보가 하나면 잇고, 여럿이면 같은 모델의 다른 설비가 그 자리에 적은 품번(siblings)이 후보 하나를 가리킬 때만 잇는다.
    mode '확인' = 품명만 있고 후보가 하나면 잇고, 빈칸이거나 후보가 여럿이면 후보를 확인 필요로 남긴다. mode '안 이음' = 잇지 않는다."""
    t=text.strip()
    m=re.search(r'\((P-[A-Z0-9-]+)\)',t)
    if m:return m.group(1)
    if t in parts:return t
    hits=sorted({c['사내품번'] for c in cross if c['다른표기']==t})
    if len(hits)==1:return hits[0]
    if mode=='안 이음':return None
    cand=sorted(p for p,row in parts.items() if model_match(model,row['적용모델']) and spare_key(row)==key)
    if not cand:
        if t:raise ValueError(f'교체부품을 풀지 못함: {text!r} {model} {key} — 후보 없음')
        return None
    if mode=='확인' and (not t or len(cand)>1):return cand
    if len(cand)==1:return cand[0]
    used=sorted({s for s in siblings if s in cand})
    if len(used)==1:return used[0]
    raise ValueError(f'교체부품을 풀지 못함: {text!r} {model} {key} 후보={cand} 같은 모델 설비가 쓰는 것={used}')

def number(text):
    m=re.match(r'\s*(-?\d+(?:\.\d+)?)',text or '')
    return float(m.group(1)) if m else None

def blank_unit_basis(folder=None):
    """단위 칸이 빈 센서 줄마다 그 단위의 근거 줄: 같은 모델(설비 대장) · 같은 태그로 단위가 적힌 줄 가운데 정상값 · 한계 · 한계구분까지 같은 줄.
    근거가 없거나 단위가 갈리면 멈춘다 — 강사 참조는 단위를 짐작하지 않는다(작업 규칙 3 · 4, 통합 실습3 7단계).
    반환: {센서 id: {'line': 빈 줄 번호, 'basis': [근거 줄 번호 …], 'unit': 단위}}. 줄 번호는 편집기에 보이는 번호(머리줄이 1행)."""
    assets=rows('설비_대장.csv',folder);old=legacy_rows(assets)
    model={a['설비코드']:a['모델'] for a in assets if a['설비코드'] not in old}
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

def recorded():
    """원자료에 실제로 있는 것 — 참조 모델과 그 스키마는 원자료에 있는 속성 · 시작 종류 · 제약만 둔다(공장 규모에는 다 있고, 통합반 실습 랩 규모에는 하나도 없다).
    kinds = 계산값 · 설정값 센서(실측뿐이면 kind를 두지 않는다), asset_sensors = 설비 전체에 붙은 센서, legacy = 옛 코드 줄,
    sensor_repeats = 같은 설비 · 태그를 다시 적은 행, sensor_meta = 계장태그 · 표본주기 · 수집방식 칸."""
    sensors = rows('센서_목록.csv')
    keys = [(s['설비코드'], s['태그']) for s in sensors]
    return dict(kinds=any('계기 없음' in s['비고'] or ('수집방식' in s and '설정값' in s['수집방식']) for s in sensors),
                asset_sensors=any(s['붙은곳'] == '설비 전체' for s in sensors),
                legacy=bool(legacy_rows(rows('설비_대장.csv'))),
                sensor_repeats=len(keys) != len(set(keys)),
                sensor_meta=bool(sensors) and '계장태그' in sensors[0])


def quantities_of(pol):
    """그 판단의 물리량 {id: (이름, 기준 단위)} — 붙은 자리까지면 측정 지점 물리량(D.QUANTITIES), 재는 값의 종류면 D.QUANTITY_KINDS."""
    if pol[3]=='자리':return dict(D.QUANTITIES)
    return {k: (n, u) for k, n, u in dict.fromkeys(D.QUANTITY_KINDS.values())}


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
    for qid,(name,unit) in quantities_of(policy(branch)).items():node('Quantity',qid,name=name,unit=unit)
    assets=rows('설비_대장.csv');models={};old=legacy_rows(assets)
    for a in assets:
        if a['설비코드'] in old:continue
        legacy=[x for x,now in old.items() if now==a['설비코드']]
        models[a['설비코드']]=a['모델']
        node('Asset',a['설비코드'],name=a['설비명'],model=a['모델'],maker=a['제조사'],serial=a['일련번호'],functional_location=a['기능위치'],
             installed=a['설치일'],status=a['상태'],legacy_codes=legacy or None)
    comps={};pol=policy(branch);mode=pol[1];split=pol[2]=='나눔';removed=[]
    comp_rows=rows('구성요소_목록.csv')
    def ckey(c):return comp_key(c['구성요소'],{k for k,*_ in D.MODEL_COMPONENTS[models[c['설비코드']]]})
    explicit={}   # 같은 모델의 다른 설비가 그 자리에 품번으로 적은 것(갈래 '이음'의 후보 여럿 풀기)
    for c in comp_rows:
        if '철거' in c['비고']:continue
        model=models[c['설비코드']];pid=resolve_part(c['교체부품'],model,ckey(c),parts,cross,mode='안 이음')
        if pid:explicit.setdefault((model,ckey(c)),[]).append((c['설비코드'],pid))
    for c in comp_rows:
        aid=c['설비코드'];model=models[aid]
        key=ckey(c);cid=aid+':'+key
        if '철거' in c['비고']:removed.append((cid,c));continue
        name='수냉 열교환기' if (model=='HPP-45B' and key=='cooler') else CANON_NAME[key]
        if cid in comps:raise ValueError('구성요소 중복 '+cid)
        comps[cid]=(aid,model,key)
        node('Component',cid,name=name,group=c['계통'],serial=None if split else (c['일련번호'] or None),aliases=[c['구성요소']] if c['구성요소']!=name else None)
        rel('HAS_COMPONENT',aid,cid)
        if split and c['일련번호']:
            node('Unit','unit:'+c['일련번호'],serial=c['일련번호'])
            rel('INSTALLED_UNIT',cid,'unit:'+c['일련번호'],current=True)
        pid=resolve_part(c['교체부품'],model,key,parts,cross,mode=mode,siblings=[p for a,p in explicit.get((model,key),[]) if a!=aid])
        if isinstance(pid,list):
            for k in pid:rel('CANDIDATE_PART',cid,k,source_text=c['교체부품'] or '(빈칸)')
        elif pid:rel('USES_PART',cid,pid,source_text=c['교체부품'] or '(빈칸: 같은 모델 공용 근거)')
    for cid,c in removed:   # 철거된 실물: 갈래 D(자리와 실물을 나눔)만 지난 실물로 남기고, 한 대상 갈래는 대상을 만들지 않는다
        if split:
            if cid not in comps:raise ValueError(f'철거 실물의 자리 {cid}가 구성 요소에 없음')
            node('Unit','unit:'+c['일련번호'],serial=c['일련번호'])
            rel('INSTALLED_UNIT',cid,'unit:'+c['일련번호'],current=False)
    seen=set();basis=blank_unit_basis();kinds=recorded()['kinds']   # 실측 센서뿐인 자료(실습 랩 규모)는 kind · derived를 두지 않는다
    for s in rows('센서_목록.csv'):
        aid=s['설비코드'];sid=aid+':'+s['태그']
        if sid in seen:continue                 # 점검표에서 다시 옮겨 적은 같은 센서
        seen.add(sid);model=models[aid]
        q='quantity:'+WHAT_ALIAS[s['재는것']]
        if pol[3]=='자리' and q=='quantity:TS1' and s['붙은곳']!='설비 전체' and comp_key(s['붙은곳'],{k for k,*_ in D.MODEL_COMPONENTS[model]})=='tank':
            q='quantity:TS3'   # 붙은 자리까지: 탱크에 붙은 유온계는 탱크 유온
        if pol[3]=='종류':q=D.QUANTITY_KINDS[q][0]   # 재는 값의 종류: 자리는 센서가 붙은 구성 요소가 말한다
        qunit=quantities_of(pol)[q][1]
        raw=s['단위'] or basis[sid]['unit'];unit,factor=UNIT.get(raw,(raw,1))   # 빈 단위 칸은 근거 줄의 단위로만(blank_unit_basis)
        if unit!=qunit:raise ValueError(f'{sid} 단위 {raw} → 물리량 {q} {qunit}')
        normal=number(s['정상값']);limit=number(s['한계'])
        instrument,how,cycle=(s[k] if k in s else '' for k in ('계장태그','수집방식','표본주기'))   # 실습 랩 규모 센서 목록에는 이 세 칸이 없다(D.SENSOR_COLS)
        kind='derived' if '계기 없음' in s['비고'] else ('setpoint' if '설정값' in how else 'measured')
        hz=number(cycle)
        props=dict(tag=s['태그'],instrument_tag=instrument or None,unit=unit,kind=kind if kinds else None,derived=(kind=='derived') if kinds else None,
                   normal=None if normal is None else round(normal*factor,6),limit=None if limit is None else round(limit*factor,6),
                   limit_direction={'상한':'upper','하한':'lower'}.get(s['한계구분']),sample_hz=hz,collection=how or None,
                   source_unit=raw if factor!=1 else None)
        node('Sensor',sid,**props)
        place=s['붙은곳']
        if place=='설비 전체':rel('MONITORED_BY',aid,sid)
        else:rel('MONITORED_BY',aid+':'+comp_key(place,{k for k,*_ in D.MODEL_COMPONENTS[model]}),sid)
        rel('OBSERVES',sid,q)
    if pol[0]=='한 물품':   # 같은 제조사 품번(규격)인 다른 사내 품번을 같은 물품으로 잇는다
        by={}
        for c in cross:
            if c['표기종류']=='제조사 품번':by.setdefault(c['다른표기'],set()).add(c['사내품번'])
        for code,ids in sorted(by.items()):
            ids=sorted(ids)
            for other in ids[1:]:rel('SAME_ITEM_AS',other,ids[0],maker_part_no=code)
    return nodes,rels

# 강사 참조 갈래. 통합반(실습 랩 규모) 결정 지점 둘 — 구성 요소 자리와 그 실물 · 같은 물리량의 범위 — 의 네 조합:
# A = 한 대상(일련번호는 구성 요소의 속성, 철거 실물은 대상 없음) · 재는 값의 종류(세 온도가 작동유 온도 하나 — 자리는 붙은 구성 요소). B = 한 대상 · 붙은 자리까지(유온 · 쿨러 출구 유온 · 탱크 유온이 따로).
# C = 나눔(Unit, 지난 실물 남김) · 재는 값의 종류. E = 나눔 · 붙은 자리까지 — 두 과정 그래프 랩 · 실전반 설계 랩의 제공 설비 모델(PROVIDED_BRANCH).
# 실전반 A = 조건부 승인을 승인으로 봄 + PR-07 7.4는 SCM 등록대로(갈래 ㄱ, 빈 조건 = 조건 없음). B = 조건부 승인을 비승인으로(ㄱ).
# 실전반 ㄴ · ㄷ = A에 더해 7.4(불량률 기준 초과 승인 공급사)를 ㄴ 정보로 붙임 · ㄷ 미결(확인 요청)로 표시. 실전반의 설비·부품 부분은 통합반 A와 같다.
# 실습4 갈래는 실습3 갈래와 따로, 실습4 입력/ 모델(GRAPH_LAB_INPUT) 위에서 돌린다(통합반 reference/session2_graph_trials.py · 실전반 verify_reference.py):
# 통합반 수정본 갈래(「불용 결정 설비」) 남김 = 불용 설비를 상태로 남김 · 삭제 = 불용 설비를 전용 하위 대상(구성 요소 · 실물 · 센서)과 함께 지움.
# 실전반 조회 갈래(「쓰는 사람에 따라 갈리는 답」) ㄱ = 승인 여부 · 단가 · 불량률 · 납기만 돌려줌 · ㄴ = PR-07 7.4 정보(입고 검사 · 비교 가산 비용)를 함께 돌려줌.
REFERENCE_BRANCHES = {'통합반': ['A', 'B', 'C', 'E'], '실전반': ['A', 'B', 'ㄴ', 'ㄷ', 'ㄹ', 'ㅁ']}
BRANCH_DIRS = {'A': '', 'B': '갈래B', 'C': '갈래C', 'E': '갈래E', 'ㄴ': '갈래ㄴ', 'ㄷ': '갈래ㄷ', 'ㄹ': '갈래ㄹ', 'ㅁ': '갈래ㅁ'}
# 실전반 결정 지점 「기준일에 유효한 견적이 여럿인 쌍」의 갈래: ㄹ · ㅁ은 승인 판단이 ㄴ이고 견적 갈래만 다르다. 그 밖의 갈래는 늦게 받은 견적(D.QUOTE_MODES[0]).
QUOTE_BRANCH = {'ㄹ': ('ㄴ', D.QUOTE_MODES[1]), 'ㅁ': ('ㄴ', D.QUOTE_MODES[2])}


def supply_branch(branch):
    """공급 갈래 → (승인 판단 갈래, 견적 갈래)."""
    return QUOTE_BRANCH.get(branch, (branch, D.QUOTE_MODES[0]))

GRAPH_LAB_INPUT = {'통합반': 'E', '실전반': 'ㄴ'}     # 2회차 그래프 랩 data/model의 앞 단계 완성 모델 — 두 과정 같은 설비 판단(갈래 E, 실전반은 그 위에 공급 ㄴ)
PROVIDED_BRANCH = 'E'                                  # 두 과정 2회차의 제공 설비 모델 판단(실전반 설계 랩의 제공 모델 · 공급 모델의 바탕 · 통합반 그래프 랩)
# 3 · 4회차 생성기가 받는 설비 모델은 2026-11-12 보강 전 판으로 고정한다(reference/2회차_이전판 — 그때 생성기로 만든 그대로).
# 그 회차를 다시 만드는 작업이 새 2회차 결과(GRAPH_LAB_INPUT)를 받을지 정한다 — 그때까지 2회차 밖 랩이 말없이 바뀌지 않게 한다.
FROZEN = TEACHER/'2회차_이전판'


def frozen_model(practical=False):
    """3 · 4회차 생성기용: 보강 전 2회차 설비 모델(통합반 갈래 A, 실전반 공급 갈래 ㄴ). 반환 형식은 reference_model과 같다."""
    name = '실전반' if practical else '통합반'
    return (json.loads((FROZEN/f'{name}_schema.json').read_text(encoding='utf-8')),
            json.loads((FROZEN/f'{name}_graph.json').read_text(encoding='utf-8')))


def frozen_assets_csv():
    """3 · 4회차 생성기용: 보강 전 설비 대장 CSV 글."""
    return (FROZEN/'설비_대장.csv').read_text(encoding='utf-8')
LAB4_QUERY_BRANCHES = {'ㄱ': 'A', 'ㄴ': 'ㄴ'}            # 실전반 실습4 조회 갈래 → 같은 열을 내는 실습3 기대 답의 키
APPROVED_STATUS = {'A': ('승인', '조건부 승인'), 'B': ('승인',), 'ㄴ': ('승인', '조건부 승인'), 'ㄷ': ('승인', '조건부 승인')}
PR74_LINE = next(i for i, x in enumerate(D.pr07_excerpt().splitlines(), 1) if '전수 검사 비용' in x)   # 발췌에서 7.4 마지막 줄
PR74_SOURCE = D.line_ref(D.PR07_FILE, PR74_LINE) + '(7.4)'
PRACTICAL_BRANCH_README = ('# 실전반 강사 참조 갈래\n\n'
    '실습3: 루트 = 갈래 A(조건부 승인 = 승인) · PR-07 7.4 갈래 ㄱ(SCM 등록대로) / `갈래B/` = 조건부 승인 = 비승인 · ㄱ / '
    '`갈래ㄴ/` = A · 7.4를 정보로 표시(실습4 `입력/` 모델) / `갈래ㄷ/` = A · 7.4 미결(확인 요청) / `갈래ㄹ/` = ㄴ · 먼저 받은 견적 / `갈래ㅁ/` = ㄴ · 견적 확인 필요. 기대 답은 `기대답.json`의 같은 키(A · B · ㄴ · ㄷ · ㄹ · ㅁ).\n\n'
    f'「기준일에 유효한 견적이 여럿인 쌍」(`{D.QUOTE_FILE}` 8 · 9행, A정밀 · P-FAN-BRG — 7월 견적의 기한 안에 10월 재견적) = {D.QUOTE_MODES[0]}(ㄱ · ㄴ · ㄷ · A · B — 10월 줄) · '
    f'{D.QUOTE_MODES[1]}(ㄹ — 7월 줄, 발주 때 7월 조건을 요구) · {D.QUOTE_MODES[2]}(ㅁ — 두 줄 모두 쓰지 않아 그 쌍이 비교에서 빠짐, 공급사에 어느 견적이 유효한지 확인). 원자료(현장 메모 6절 · PR-07 발췌)는 어느 줄을 쓸지 정하지 않는다.\n\n'
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
    branch,quote_mode=supply_branch(branch)
    parts={p['품번']:p for p in rows('예비품_목록.csv')}
    avl={(r['공급사'],r['품번']):(line,r) for line,r in enumerate(rows(D.AVL_FILE),2)}
    live={}
    for line,q in enumerate(rows(D.QUOTE_FILE),2):
        pid=q['품번'] if q['품번'] in parts else next(p for p,row in parts.items() if row['품명']==q['품번'])
        sup=next(k for k in D.SUPPLIERS if q['공급사'].startswith(k))
        if q['유효기한']<D.REF_DATE:continue          # 만료 견적은 조건으로 쓰지 않는다
        live.setdefault((sup,pid),[]).append((line,q))
    best={}
    for k,quotes in live.items():                    # 유효한 견적이 여럿인 쌍은 견적 갈래대로(D.QUOTE_MODES)
        if len(quotes)==1:best[k]=quotes[0]
        elif quote_mode==D.QUOTE_MODES[0]:best[k]=max(quotes,key=lambda x:x[1]['견적일'])
        elif quote_mode==D.QUOTE_MODES[1]:best[k]=min(quotes,key=lambda x:x[1]['견적일'])
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
    pol=policy(branch,supply);split=pol[2]=='나눔';place=pol[3]=='자리'
    rec=recorded()   # 원자료에 없는 것(계산값 · 설정값, 설비 전체 센서, 계장태그, 옛 코드 줄, 점검표 재기입 행)의 속성 · 시작 종류 · 제약은 두지 않는다
    definitions={
      'Asset':{'meaning':'개별 설비(설비코드 기준). 기능위치·실물 일련번호를 속성으로 둔다','required':{'id':'string','name':'string','model':'string','status':'string'},
               'optional':{'maker':'string','serial':'string','functional_location':'string','installed':'string',**({'legacy_codes':'list'} if rec['legacy'] else {})}},
      'Component':({'meaning':'설비 안의 정비 가능 품목이 놓인 자리. 기능 자리 기준 ID(설비코드:품목)이고, 그 자리에 달린 실물은 Unit','required':{'id':'string','name':'string','group':'string'},
                    'optional':{'aliases':'list'}} if split else
                   {'meaning':'설비 안의 정비 가능 품목. 기능 자리 기준 ID(설비코드:품목)로, 실물 교체는 serial로 남긴다','required':{'id':'string','name':'string','group':'string'},
                    'optional':{'serial':'string','aliases':'list'}}),
      'Sensor':{'meaning':'설비별 계측 채널'+('. 실측·계산값·설정값을 kind로 구별' if rec['kinds'] else ''),
                'required':{'id':'string','tag':'string','unit':'string',**({'kind':['measured','derived','setpoint'],'derived':'boolean'} if rec['kinds'] else {})},
                'optional':{'normal':'number','limit':'number','limit_direction':['upper','lower'],
                            **({'instrument_tag':'string','sample_hz':'number','collection':'string'} if rec['sensor_meta'] else {}),'source_unit':'string'}},
      'Quantity':{'meaning':'재는 물리량과 기준 단위. 붙은 자리가 다르면 다른 물리량(쿨러 쪽 유온 · 탱크 유온)' if place else '재는 값의 종류(무엇의 어떤 값)와 기준 단위. 어디에 붙었는지는 센서가 붙은 구성 요소가 말한다','required':{'id':'string','name':'string','unit':'string'}},
      'Part':{'meaning':'사내 품번 하나로 관리하는 부품 품목','required':{'id':'string','name':'string'},'optional':{'other_codes':'list'}}}
    if split:definitions['Unit']={'meaning':'일련번호가 붙은 실물 한 대(그 자리에 지금 달린 것 · 전에 달렸다가 철거된 것)','required':{'id':'string','serial':'string'}}
    # 카디널리티는 이론의 표기(시작 쪽 수:끝 쪽 수, 각 쪽은 많아야 몇 개) — 1:N = 시작 하나에 끝 여럿, 끝 하나에는 시작 하나. 학생 검사기가 이 수를 그래프와 견준다.
    relation_defs={'HAS_COMPONENT':{'from':'Asset','to':'Component','cardinality':'1:N'},
        'MONITORED_BY':({'from':['Component','Asset'],'to':'Sensor','cardinality':'1:N','note':'설비 전체에 붙은 계산값(SE)은 Asset에서'} if rec['asset_sensors'] else
                        {'from':'Component','to':'Sensor','cardinality':'1:N'}),
        'OBSERVES':{'from':'Sensor','to':'Quantity','cardinality':'N:1'},
        'USES_PART':{'from':'Component','to':'Part','cardinality':'N:1','properties':{'source_text':'string'}}}
    if split:
        relation_defs['INSTALLED_UNIT']={'from':'Component','to':'Unit','cardinality':'1:N','properties':{'current':'boolean'},'note':'current=true가 지금 달린 실물, false가 철거된 실물'}
    if pol[1]=='확인':
        relation_defs['CANDIDATE_PART']={'from':'Component','to':'Part','cardinality':'N:M','properties':{'source_text':'string'},'note':'원자료가 하나로 정하지 않아 확인이 필요한 교체 부품 후보'}
    if pol[0]=='한 물품':relation_defs['SAME_ITEM_AS']={'from':'Part','to':'Part','cardinality':'N:1','properties':{'maker_part_no':'string'},'note':'같은 제조사 품번인 다른 사내 품번'}
    if supply:
        definitions['Supplier']={'meaning':'견적을 낸 공급사','required':{'id':'string','name':'string'}}
        props={'approved':'boolean','approval_status':'string','condition':'string','price_manwon':'number','defect_rate':'number','defect_rate_original':'string',
               'lead_days':'integer','lead_days_original':'string','min_order_qty':'integer','supplier_part_no':'string','quote_date':'string','valid_until':'string',
               'quote_source':'string','approval_source':'string','as_of':'string'}
        ab,quote_mode=supply_branch(branch)
        if ab=='ㄴ':props.update(inspection='string',compare_extra_manwon='number',rule_source='string')
        if ab=='ㄷ':props.update(pending_check='string')
        note={D.QUOTE_MODES[0]:'공급사·품번마다 기준일에 유효한 견적 하나(여럿이면 견적일이 가장 늦은 줄)',D.QUOTE_MODES[1]:'공급사·품번마다 기준일에 유효한 견적 하나(여럿이면 견적일이 가장 이른 줄)',
              D.QUOTE_MODES[2]:'공급사·품번마다 기준일에 유효한 견적 하나(여럿인 쌍은 확인 전까지 두지 않음)'}[quote_mode]
        relation_defs['SUPPLIES']={'from':'Supplier','to':'Part','cardinality':'N:M','note':note,'properties':props}
    skip=[x for x,on in (('옛 코드 줄(같은 기능위치 · 일련번호)',rec['legacy']),('점검표 중복 행',rec['sensor_repeats'])) if on]
    removed=('철거된 실물은 그 자리의 지난 실물(INSTALLED_UNIT current=false)로 남긴다' if split else
             '철거 실물 행' + ('도' if skip else '은') + ' 대상을 새로 만들지 않는다')
    constraints=['id는 전체 그래프에서 고유. 구성요소·센서는 설비코드:이름, 부품은 사내 품번' + (', 실물은 unit:일련번호' if split else ''),
                 ('·'.join(skip) + '은 대상을 새로 만들지 않는다. ' if skip else '') + removed,
                 'limit 생략은 0과 다르다. normal 생략은 미확인','단위는 Quantity 기준 단위로 맞추고 바꾼 경우 source_unit을 남긴다']
    if pol[1]=='확인':constraints+=['교체부품 칸이 비었거나 같은 모델 · 같은 쓰는곳의 예비품이 둘 이상이면 USES_PART로 정하지 않고 후보마다 CANDIDATE_PART로 남긴다']
    if supply:constraints+=['승인 여부는 승인공급사_목록(SCM 등록)과 기준일로 정한다','만료 견적은 SUPPLIES로 쓰지 않는다',
                            '공급사 이름은 승인공급사_목록의 이름이다(견적표의 공급사 칸은 그 이름으로 시작한다)',
                            '단가는 만원, 불량률은 0~1 비율, 납기는 일로 맞추고, 바꾼 불량률 · 납기는 원래 표기를 defect_rate_original · lead_days_original로 남긴다',
                            f'값마다 출처를 남긴다: quote_source = 쓴 견적의 {D.QUOTE_FILE} 줄, approval_source = {D.AVL_FILE}의 등록 줄, as_of = 기준일']
    # 실습4 입력 모델(갈래 ㄴ)의 schema가 학생에게 간다 — 「함께 남긴다」처럼 실습4 결정(돌려줄지)을 미리 정하는 말 없이, 값이 어디서 왔는지만 적는다(코딩랩.md K-4).
    ab=supply_branch(branch)[0] if supply else branch
    if supply and ab=='ㄴ':constraints.append(f'inspection · compare_extra_manwon · rule_source는 구매 기준서 PR-07 7.4 문장(rule_source 줄)에서 온 값이고, 그 절에 걸리는 승인 공급사 쌍(불량률 {D.PR74_RATE_PCT} % 초과)에만 있다')
    if supply and ab=='ㄷ':constraints.append('SCM 등록에 조건이 없는데 구매 기준서 PR-07 7.4에 걸리는 승인 공급사 쌍은 pending_check로 확인 필요를 남긴다(approved는 SCM 등록대로)')
    return {'classes':definitions,'relations':relation_defs,'identity':'id는 전체 그래프에서 고유.','branch':branch,'constraints':constraints}

def reference_model(supply=False,branch='A'):
    """원자료끼리 대조한 근거로 만든 강사 참조 모델(반환 형식 유지). 갈래는 REFERENCE_BRANCHES 위 주석."""
    nodes,rels=base_graph(PROVIDED_BRANCH if supply else branch)
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
    # 카디널리티(시작 쪽 수:끝 쪽 수) — 「1」 쪽은 많아야 하나. 그래프의 실제 연결 수가 적은 수를 넘으면 그 대상을 짚는다.
    ONE={'1','0..1'};MANY={'N','M','0..N','1..N','*'}
    out_n={};in_n={}
    for r in rels:
        t=r.get('type');a=r.get('a');b=r.get('b')
        if t in relations and a in labels_by_id and b in labels_by_id:
            out_n.setdefault((t,a),set()).add(b);in_n.setdefault((t,b),set()).add(a)
    for t,spec in relations.items():
        card=spec.get('cardinality') if isinstance(spec,dict) else None
        if card in (None,''):continue
        sides=str(card).replace(' ','').split(':')
        if len(sides)!=2 or not all(x in ONE|MANY for x in sides):
            errors.append(f'schema.json {t}의 cardinality 「{card}」: 1:1 · 1:N · N:1 · N:M 꼴로 씁니다.');continue
        for side,count,word in [(sides[1],out_n,'시작 하나에 끝이'),(sides[0],in_n,'끝 하나에 시작이')]:
            if side not in ONE:continue
            over=sorted((x,len(v)) for (tt,x),v in count.items() if tt==t and len(v)>1)
            if over:errors.append(f'{t} 카디널리티 {card} 어긋남: {word} 많아야 하나인데 둘 이상인 대상 {len(over)}개 — '+', '.join(f'{x} {n}개' for x,n in over[:5])+(' …' if len(over)>5 else ''))
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


CHECK_ANCHOR='except (OSError,ValueError,TypeError,AttributeError) as e:'
assert CHECKER.count(CHECK_ANCHOR)==1


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
    """실습4 결과 형식. 수정본 반영이 있는 랩(통합반)만 수정 쿼리 줄을 둔다."""
    return ('## 결과 형식\n\n`결과/`에 아래 파일을 둡니다. 파일 안에서 무엇을 어떤 문장으로 쓸지는 직접 정합니다.\n\n'
            '- `결과/load.cypher`(또는 적재 코드): 모델 파일의 대상과 관계를 랩 DB에 넣습니다. 같은 파일을 다시 실행해도 됩니다.\n'
            + ('- `결과/update.cypher`(또는 수정 코드): 수정본의 줄을 이미 넣은 그래프에 반영합니다.\n' if change else '')
            + '- `결과/query.cypher`: 질문마다 Cypher 쿼리 하나. 쿼리 위에 어느 질문의 쿼리인지 주석(`// 질문 1`)으로 적습니다.\n'
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


def graph_counts(change):
    """실습4 확인 기록의 개수 표. 수정본 반영이 있는 랩(통합반)만 수정본 두 줄을 둔다."""
    return ('## 적재 · 다시 적재' + (' · 수정본' if change else '') + '\n\n| 단계 | 노드 수 | 관계 수 | 확인한 것 |\n|---|---|---|---|\n'
            '| 첫 적재 | | | |\n| 같은 적재 다시 | | | |\n' + ('| 수정본 반영 | | | |\n| 같은 수정본 다시 | | | |\n' if change else '') + '\n')

# ───────────── 실습4(그래프 구현과 검증) — 두 과정 ─────────────
# 통합 실습4 12단계의 입력 = 포털 실습 「설비 지식의 구조와 연결 관계 탐색하기」에서 펼쳐 본 기준 지도(설비 HYD-01 → 오일 쿨러 → 센서 → 상태 변수).
# 랩은 포털 없이 돈다(코딩랩.md K-2) — 포털이 실제로 적재하는 main 시드와 포털 화면의 관계 이름에서 뽑아 랩의 제공 입력(data/reference_map.json)으로 주고, 비교 기능의 결과 화면이 띄운다.
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


def portal_reference():
    """그래프 랩 비교 기능(compare)의 기준 지도 — 랩의 제공 입력 `data/reference_map.json`. 포털 지식 지도는 고른 설비 하나만 그린다(main `it/neo4j/templates/t0_graph_nodes.cypher` ·
    `t0_graph_edges.cypher`의 설비 조건) — 그래서 포털 실습에서 HYD-01의 오일 쿨러를 펼쳐 본 길(설비 → 쿨러 → 센서 → 상태 변수)과, 설비 칸을 HYD-02로 바꿔 본 한 줄만 담는다.
    결과 화면이 내 그래프 표 아래에 띄운다 — 영상은 가이드를 띄우지 않으므로 견줄 표가 가이드에만 있으면 안 된다(사용자 2026-11-20 「결과 화면에 띄워」)."""
    nodes, rels, ko = portal_map()
    sensors = list(dict.fromkeys(b for a, t, b in rels if a == PORTAL_COMPONENT and t == 'MONITORED_BY'))   # 시드 순서(유온 센서가 먼저)
    path = [PORTAL_ASSET, PORTAL_COMPONENT, *sensors, *dict.fromkeys(b for s in sensors for a, t, b in rels if a == s and t == 'OBSERVES')]
    on_path = [(a, t, b) for a, t, b in rels if a in path and b in path]      # 다른 설비(HYD-02 · 03)는 길에 없어 함께 빠진다
    switched = 'asset:hyd-02'                                                   # 포털 실습에서 설비 칸을 바꿔 본 설비(대본 05_실습_지식지도탐색 3절)
    if (switched, 'HAS_COMPONENT', PORTAL_COMPONENT) not in rels:
        raise ValueError(f'{PORTAL_SEED}에서 {switched} → {PORTAL_COMPONENT}(HAS_COMPONENT)를 찾지 못했습니다 — 기준 지도의 설비 바꾸기 줄을 다시 봅니다.')
    shown = {'Asset': 'code', 'Component': 'name', 'Sensor': 'tag', 'StateVariable': 'name'}   # 대상을 알아볼 값 하나
    kind = {'Asset': '설비', 'Component': '구성 요소', 'Sensor': '센서', 'StateVariable': '상태 변수'}
    ids = [*path, switched]
    missing = [i for i in ids if nodes[i].get(shown[nodes[i]['label']]) is None]
    if missing:
        raise ValueError(f'{PORTAL_SEED}: 알아볼 값이 없는 대상 {missing}')
    return {'설명': '포털 실습의 지식 지도에서 HYD-01의 오일 쿨러를 펼쳐 본 길(설비 → 쿨러 → 센서 → 상태 변수)과, 설비를 HYD-02로 바꾸면 같은 쿨러로 이어지는 관계',
            '대상': [{'id': i, '종류': kind[nodes[i]['label']], '알아볼 값': str(nodes[i][shown[nodes[i]['label']]])} for i in ids],
            '관계': [{'시작': a, '관계': t, '화면 이름': ko[t], '끝': b} for a, t, b in [*on_path, (switched, 'HAS_COMPONENT', PORTAL_COMPONENT)]]}


def blank_pump_basis():
    """제공 모델이 교체부품 칸이 빈 HYD-03 주 펌프를 이은 근거 — 원자료의 다른 칸(같은 모델의 예비품 · 입고 이력 비고)으로 밝힌다(H3)."""
    comp = next(i for i, c in enumerate(rows('구성요소_목록.csv'), 2) if c['설비코드'] == 'HYD-03' and c['구성요소'] == '주 펌프 A')
    spare = next(i for i, p in enumerate(rows('예비품_목록.csv'), 2) if p['품번'] == 'P-PMP-SEAL')
    place = next(a['기능위치'] for a in rows('설비_대장.csv') if a['설비코드'] == 'HYD-03')
    receipt = next(i for i, r in enumerate(rows('입고_이력.csv'), 2) if place in r['비고'] and r['품번'] == 'P-PMP-SEAL')
    return (f'- HYD-03 주 펌프: `입력/자료/구성요소_목록.csv` {comp}행은 교체부품 칸이 비어 있습니다. 같은 모델(HPP-45A)의 주 펌프에 적용되는 예비품이 '
            f'`입력/자료/예비품_목록.csv` {spare}행 P-PMP-SEAL 하나뿐이고, `입력/자료/입고_이력.csv` {receipt}행 비고의 정비 예약 기능위치 {place}가 설비 대장의 HYD-03이라 P-PMP-SEAL로 이었습니다.')


def provided_basis(practical):
    """실습4 입력/자료_검토.md — 제공된 모델이 원자료를 어떻게 처리했는지(이번 실습의 결과가 아님)."""
    if not practical:
        D.require('통합반')
        removed = [i for i, c in enumerate(rows('구성요소_목록.csv'), 2) if '철거' in c['비고']]
        other = sorted({f'{raw} → {unit}' for s in rows('센서_목록.csv') for raw, (unit, factor) in [(s['단위'], UNIT.get(s['단위'], (s['단위'], 1)))] if factor != 1})
        return '\n'.join([
            '# 제공된 모델의 자료 처리 근거', '',
            '이 모델(schema.json · graph.json)은 원자료와 현장 메모로 만든 설계 단계의 완성 모델입니다. 이번 실습의 적재 · 조회 결과가 아닙니다. 처리 기준은 schema.json의 constraints에 적혀 있습니다.', '',
            '- 구성 요소와 실물: 구성 요소(Component)는 설비 안의 구성 요소 자리이고, 구성 요소 목록에 일련번호가 적힌 장치는 실물(Unit)로 따로 두었습니다. '
            f'INSTALLED_UNIT의 current가 true면 지금 달린 실물, false면 철거된 실물입니다(`입력/자료/구성요소_목록.csv` {" · ".join(f"{i}행" for i in removed)}).',
            '- 이름: 설비마다 다르게 적은 구성 요소 이름은 하나로 맞추고, 원자료 이름은 aliases에 남겼습니다.',
            '- 센서와 물리량: 같은 물리량은 붙은 자리까지 같아야 묶었습니다(쿨러 쪽 유온, 쿨러 출구 유온, 탱크 유온이 따로). '
            'HYD-07의 현장 지시계는 붙은 자리의 물리량에 두었고(탱크의 유온계는 탱크 유온, 펌프의 압력계는 토출 압력), '
            'HYD-04의 FS2는 냉각수 유량이라 작동유를 재는 냉각 회로 유량과 따로 두었습니다. '
            f'단위는 물리량 기준 단위로 맞추고 바꾼 센서에는 source_unit을 남겼습니다({" · ".join(other)}). 한계가 없으면 limit을 생략했습니다.',
            '- 부품: 교체부품 칸의 예전 품번 · 줄여 쓴 표기 · 제조사 품번은 품번 교차표로 사내 품번에 이었고, 그 표기들은 부품의 other_codes에 남겼습니다.']) + '\n'
    lines = ['# 제공된 모델의 자료 처리 근거', '',
             '이 모델(schema.json · graph.json)은 원자료와 현장 메모로 만든 설계 단계의 완성 모델입니다. 이번 실습의 적재 · 조회 결과가 아닙니다. 처리 기준은 schema.json의 constraints에 적혀 있습니다.', '',
             '- 설비: 다른 줄과 기능위치 · 일련번호 · 설치일이 같고 가동 중이 아닌 옛 코드 줄은 대상을 새로 만들지 않고 legacy_codes로 남겼습니다.',
             '- 구성 요소와 실물: 구성 요소(Component)는 설비 안의 구성 요소 자리이고, 구성 요소 목록에 일련번호가 적힌 장치는 실물(Unit)로 따로 두었습니다. '
             'INSTALLED_UNIT의 current가 true면 지금 달린 실물, false면 철거된 실물입니다.',
             '- 센서: 같은 설비 · 태그의 점검표 재기입 행은 하나로 두었습니다. 단위는 물리량 기준 단위로 맞추고 바꾼 경우 source_unit을 남겼습니다. 계산값 · 설정값은 kind로 구별했습니다. 한계가 없으면 limit을 생략했습니다. '
             '같은 물리량은 재는 값의 종류와 붙은 계통까지 같아야 묶었습니다(탱크에 붙은 유온계는 탱크 유온, 쿨러 입구와 출구 유온은 따로).',
             *[f'- 센서 {sid}: `입력/자료/센서_목록.csv` {b["line"]}행은 단위 칸이 비어 있어, 같은 모델 · 같은 태그로 정상값 · 한계까지 같은 줄({" · ".join(f"{n}행" for n in b["basis"])})을 근거로 단위를 {b["unit"]}로 두었습니다.'
               for sid, b in blank_unit_basis().items()],
             '- 부품: 교체부품 칸의 품명 · 표기 변형 · 제조사 품번은 품번 교차표와 예비품 목록의 적용 모델 · 쓰는곳으로 사내 품번에 이었습니다. 같은 규격의 다른 사내 품번은 따로 두었습니다. '
             '같은 모델 · 같은 쓰는곳의 예비품이 둘 이상이면 같은 모델의 다른 설비가 그 구성 요소에 적은 품번으로 이었습니다.',
             blank_pump_basis()]
    if practical:
        # 7.4를 「붙였다」고 풀어 쓰면 실습4 결정 지점(조회에 함께 돌려줄지)이 한쪽으로 기운다(리허설 — 코딩랩.md K-4). 값이 어디서 왔는지만 적는다.
        lines.append('- 공급: 공급사 · 품번마다 기준일에 유효한 최신 견적 하나를 SUPPLIES로 두었습니다. 공급사 이름은 승인공급사_목록(SCM 등록)의 이름입니다(견적표의 공급사 칸은 그 이름으로 시작합니다). '
                     '승인 여부는 승인공급사_목록과 기준일로 정했습니다(조건부 승인은 approved=true, 조건은 condition). '
                     '단가는 만원, 불량률은 0~1 비율, 납기는 일로 맞추고, 바꾼 불량률 · 납기는 원래 표기를 defect_rate_original · lead_days_original로 남겼습니다.')
        lines.append(f'- 출처: SUPPLIES마다 값이 온 곳을 남겼습니다 — quote_source = 그 쌍에 쓴 견적의 `입력/자료/{D.QUOTE_FILE}` 줄(견적일은 quote_date), '
                     f'approval_source = `입력/자료/{D.AVL_FILE}`의 등록 줄, as_of = 승인 · 유효기한을 판단한 기준일, rule_source = inspection · compare_extra_manwon 값이 온 `입력/자료/{D.PR07_FILE}` 줄. 줄 번호는 편집기에 보이는 번호(머리줄이 1행)입니다.')
    return '\n'.join(lines) + '\n'


# ───────────── 단계 랩(오프라인 50분 판) — 틀은 lab_frame, 학생 몫은 결과/의 정할 자리, 일반 로직은 제공 코드 ─────────────
# 계약: 공용틀_계약.md. 단계 · 힌트에는 값과 판단 지점의 답을 쓰지 않는다(K-4) —
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
    """통합반 설계 랩 정의 — 빈 틀과 결정 지점. 단계와 가이드 문장은 session2_project_guides.ontology가 갖는다."""
    import session2_answers as ANS
    D.require('통합반')
    return dict(title='설비 정보를 체계화하는 온톨로지 직접 설계하기', course='통합반', kind='design_integrated', steps=[],
                files={'결과/정한_것.csv': decision_template(ANS.DECISION_POINTS),
                       '결과/기대_답.csv': F.blank_csv(ANS.EXPECT_COLUMNS_DESIGN, ANS.EXPECT_EXPLAIN_DESIGN),
                       **{f'결과/{n}': F.blank_csv(ANS.DESIGN_COLUMNS[n], ANS.DESIGN_EXPLAIN[n]) for n in ANS.DESIGN_COLUMNS},
                       '결과/quantity_rules.py': ANS.QUANTITY_RULES_BLANK})   # 같은 모델의 구성 요소 이름 맞추기는 제공 코드가 한다(session2_model_tool.name_map)


def chosen_text(rows):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator='\n')
    for r in rows:
        w.writerow(r)
    return F.CHOSEN_TEMPLATE + buf.getvalue()


EXPECT_ASSET, EXPECT_UNIT_ASSET = 'HYD-01', 'HYD-02'          # 기대 답 예가 묻는 설비(구성 요소별 센서 · 교체 이력이 있는 구성 요소 자리)
EXPECT_SENSORS = ('HYD-01:TS1', 'HYD-03:PS1', 'HYD-07:TI-1')    # 값을 견주는 센서(둘째는 같은 값을 다른 단위로 적은 줄, 셋째는 손으로 읽는 현장 지시계)
EXPECT_CODES = ('P-PMP-SEAL', 'PS-4510', 'RF-10', 'P-PMP-SEAL-X')   # 사내 품번 · 예전 품번 · 줄여 쓴 표기 · 원자료에 없는 품번


def expect_design_text(branch='A'):
    """통합 02-3 기대 답 — 그 갈래의 판단을 생성 정답 구조(data_session2.TRUTH, verify_reference.expected)에 적용해 원자료 쪽에서 만든다.
    강사 참조 모델(reference_model)을 읽지 않는다 — 모델을 자기 자신과 견주지 않기 위해서다. 질문 1 = 설비 하나의 구성 요소 셋의 센서와 교체 이력이 있는 구성 요소 자리의 실물,
    질문 2 = 쿨러 쪽 유온을 담은 물리량 묶음과 센서 값 둘, 질문 3 = 사내 품번 · 다른 표기 · 없는 품번."""
    import session2_answers as ANS
    import verify_reference as V
    D.require('통합반')
    exp = V.expected('통합반', branch)
    pol = policy(branch)
    names = quantities_of(pol)
    comps = list(enumerate(rows('구성요소_목록.csv'), 2))
    line = {(s['설비코드'], s['태그']): i for i, s in enumerate(rows('센서_목록.csv'), 2)}
    own = sorted(i for (code, _), i in line.items() if code == EXPECT_ASSET)
    rows_ = []
    per = exp['sensors_by_asset'][EXPECT_ASSET]
    for key, tags in sorted(sorted(per.items(), key=lambda x: CANON_NAME[x[0]]), key=lambda x: -len(x[1]))[:3]:   # 질문 1은 구성 요소 셋
        rows_.append(['1', EXPECT_ASSET, CANON_NAME[key], ' · '.join(sorted(tags)), f'자료/센서_목록.csv:{own[0]}~{own[-1]} 붙은곳 칸'])
    key = D.REMOVED_PUMP[1]
    serial_lines = [i for i, c in comps if c['설비코드'] == EXPECT_UNIT_ASSET and c['일련번호']]
    serials = (' · '.join(f'{s}({"지금" if current else "지난"})' for s, current in sorted(exp['units'][f'{EXPECT_UNIT_ASSET}:{key}'], key=lambda x: not x[1]))
               if pol[2] == '나눔' else D.SERIALS[(EXPECT_UNIT_ASSET, key)])
    rows_.append(['1', EXPECT_UNIT_ASSET, CANON_NAME[key] + ' 실물', serials, '자료/구성요소_목록.csv:' + ' · '.join(map(str, serial_lines)) + ' 일련번호 · 비고 칸'])
    props = exp['sensor_props']
    q = props[EXPECT_SENSORS[0]][0]
    rows_.append(['2', names[q][0], '', ' · '.join(exp['quantity_members'][q]), '자료/센서_목록.csv 태그 · 재는것 · 붙은곳 칸'])
    for sid in EXPECT_SENSORS:
        q, unit, normal, limit, direction, _ = props[sid]
        value = ' · '.join([unit, '없음' if normal is None else '%g' % normal, '없음' if limit is None else '%g' % limit, {'upper': '상한', 'lower': '하한'}.get(direction, '없음')])
        rows_.append(['2', names[q][0], sid, value, f'자료/센서_목록.csv:{line[tuple(sid.split(":"))]} 단위 · 정상값 · 한계 · 한계구분 칸'])
    for code in EXPECT_CODES:
        found = exp['probes'][code]
        if found is None:
            rows_.append(['3', code, '', '없음', '자료/예비품_목록.csv · 자료/품번_교차표.csv에 없음'])
            continue
        cross = [i for i, c in enumerate(rows('품번_교차표.csv'), 2) if c['다른표기'] == code]
        rows_.append(['3', code, found['part'], ' · '.join(found['assets']) or '쓰는 설비 없음',
                      (f'자료/품번_교차표.csv:{cross[0]} · ' if cross else '') + '자료/구성요소_목록.csv 교체부품 칸'])
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator='\n')
    w.writerow(ANS.EXPECT_COLUMNS_DESIGN)
    for r in rows_:
        w.writerow(r)
    return f'# {F.MARK} — {ANS.EXPECT_EXPLAIN_DESIGN}\n' + buf.getvalue()


def decision_template(points):
    """정한_것.csv 빈 틀 — 머리(lab_frame.CHOSEN_TEMPLATE 한 곳)와 결정 지점 줄. 고른_것 · 근거 · 바뀌는_답은 비워 두고, 그 결정을 쓰는 단계의 제공 코드가 빈 줄을 짚고 멈춘다."""
    return F.CHOSEN_TEMPLATE + ''.join(f'{p},,,\n' for p in points)


# ───────────── 실습4(그래프 구현과 검증) — 두 과정 ─────────────
def graph_integrated():
    """통합반 그래프 랩 정의 — 빈 틀과 결정 지점. 단계와 가이드 문장은 session2_project_guides.graph가 갖는다."""
    import session2_answers as ANS
    D.require('통합반')
    course = '통합반'
    return dict(title='설계한 온톨로지를 그래프 DB에 구현하고 검증하기', course=course, kind='graph_integrated', change=True, steps=[],
                files={'결과/정한_것.csv': decision_template(GRAPH_POINTS[course]),
                       '결과/기대_답.csv': F.blank_csv(ANS.GRAPH_EXPECT_COLUMNS, ANS.GRAPH_EXPECT_EXPLAIN[course]),
                       **ANS.BLANKS_INTEGRATED})


def graph_lab(course):
    """통합반 그래프 랩 정의. 실전반은 같은 정의에 얹는다(session2_factory_graph.graph_lab)."""
    if course != '통합반':
        raise ValueError('실전반 그래프 랩 정의는 session2_factory_graph.graph_lab()입니다.')
    return graph_integrated()


WHY_G_PLAN = ('스키마의 종류(이론의 클래스) 이름은 그래프의 레이블이 되고, 대상 하나(이론의 인스턴스)를 저장한 것이 노드입니다. ID는 노드의 속성, 관계 정의의 시작 · 끝은 관계의 방향이 됩니다. '
              'CREATE는 실행할 때마다 새로 만들고, MERGE는 같은 것이 있으면 찾고 없으면 만듭니다. 그래서 다시 실행해도 늘지 않으려면 무엇으로 「같은 것」을 알아볼지 먼저 정해야 합니다. '
              '다시 넣을 때 값을 덮어쓰면 수정본으로 고친 값이 되돌아가고, 처음 만들 때만 넣으면 그대로 남습니다.')


GRAPH_POINTS = {'통합반': ['불용 결정 설비', '목록에서 빠진 센서']}   # 그래프 랩 정한_것.csv의 지점 줄(graph_chosen의 지점)


def retired_change_line():
    """통합반 수정본에서 불용 결정 설비 줄(파일:줄) — 결정 「불용 결정 설비」의 원문 줄이자 그 결정으로 바뀌는 기대 답의 근거."""
    retired = D.LAB_RETIRED[0]
    return f'입력/자료_변경분/{D.CHANGE_DATE}_수정본/설비_대장_변경.csv:{next(i for i, r in enumerate(D.changes()["설비_대장_변경.csv"], 2) if r[1] == retired)}'


def graph_chosen(course):
    if course != '통합반':
        raise ValueError('실전반 그래프 랩의 결정 기록 참조 답은 session2_factory_graph.chosen()입니다.')
    retired, status = D.LAB_RETIRED
    where = retired_change_line()
    kept = sorted(a for a, t in D.TRUTH['assets'].items() if a != retired and GRAPH_SHARED_PART in t['components'].values())
    if retired not in {a for a, t in D.TRUTH['assets'].items() if GRAPH_SHARED_PART in t['components'].values()}:
        raise ValueError(f'{GRAPH_SHARED_PART}를 불용 결정 설비 {retired}가 쓰지 않아 두 갈래의 바뀌는 답이 같습니다 — GRAPH_SHARED_PART를 다시 고릅니다.')
    code, tag, note = D.LAB_SENSOR_REMOVED
    gone = f'입력/자료_변경분/{D.CHANGE_DATE}_수정본/센서_변경.csv:{next(i for i, r in enumerate(D.changes()["센서_변경.csv"], 2) if r[0] == "삭제")}'
    # 근거 칸 = 내 이유와, 그 결정을 좌우해 열어 본 원문 줄(lab_frame.CHOSEN_TEMPLATE). 갈래마다 결정 지점 둘의 줄(GRAPH_POINTS['통합반']의 차례)
    return {'남김': [['불용 결정 설비', '상태로 남김', f'매각 전까지는 공장에 있는 설비라 기록을 지우지 않으려고 — {where}',
                    f'{GRAPH_SHARED_PART} 사용 설비에 {retired}이 「{status}」 상태로 남음 — 보전팀은 매각 전까지 그 설비에 어떤 예비품이 들어갔는지 그래프에서 봄'],
                   ['목록에서 빠진 센서', '상태로 남김', f'그 자리에 센서가 있었다는 것과 지금은 떼어 냈다는 것을 그래프에서 바로 보려고 — {gone}',
                    f'질문 1에서 {code}의 {tag} 줄이 「떼어 냄」 상태로 나옴(센서의 상태 속성을 스키마에 더함) — 운전은 그 자리의 값이 지금은 오지 않는다는 것을 그래프에서 봄']],
            '삭제': [['불용 결정 설비', '하위 대상과 지움', f'보전팀이 묻는 것은 지금 가동하는 설비의 예비품이라 쓰지 않을 설비는 답에서 빼려고 — {where}',
                    f'{GRAPH_SHARED_PART} 사용 설비가 {" · ".join(kept)} — 보전팀은 남은 설비 몫만 예비품을 준비하고, {retired}의 지난 기록은 CMMS에서 찾음'],
                   ['목록에서 빠진 센서', '지움', f'운전이 묻는 것은 지금 값이 오는 센서라 떼어 낸 센서는 답에서 빼려고 — {gone}',
                    f'질문 1에서 {code}의 {tag} 줄이 나오지 않음 — 운전은 지금 붙어 있는 센서만 받고, 떼어 낸 이력은 정비 기록에서 찾음']]}


GRAPH_SHARED_PART = 'P-CPL-ELM'           # 통합반 그래프 랩 기대 답과 결정 지점이 묻는 공용 부품(불용 결정 설비도 쓴다)
# 기대 답이 묻는 값(설비 · 다른 표기 · 없는 품번). 다른 표기 셋은 쓰는 설비가 다 다르다 — RF-10은 다섯 대 모두, PS-4510은 HPP-45A 세 대, HI-GS-22는 불용 결정 설비 하나
GRAPH_ASK = {'sensors': 'HYD-01', 'parts': 'HYD-02', 'aliases': ('RF-10', 'PS-4510', 'HI-GS-22'), 'missing': 'P-PMP-SEAL-X'}


def graph_expect_rows(course, graph):
    """실습4 기대 답 예 — 입력 모델(강사 참조)에서. 볼_열은 정답 보기 쿼리가 돌려주는 열."""
    label = {n['props']['id']: n['labels'][0] for n in graph['nodes']}
    props = {n['props']['id']: n['props'] for n in graph['nodes']}
    rows = []
    D.require('통합반')
    owner = {r['b']: r['a'] for r in graph['rels'] if r['type'] == 'HAS_COMPONENT'}
    comp_lines = {a: [i for i, c in numbered('구성요소_목록.csv') if c['설비코드'] == a] for a in D.TRUTH['assets']}
    sensor_lines = {a: [i for i, s in numbered('센서_목록.csv') if s['설비코드'] == a] for a in D.TRUTH['assets']}
    a = GRAPH_ASK['sensors']
    tags = sorted(props[r['b']]['tag'] for r in graph['rels'] if r['type'] == 'MONITORED_BY' and (r['a'] == a or owner.get(r['a']) == a))
    rows.append(['1', a, 'tag', ' · '.join(tags), f'입력/자료/센서_목록.csv:{sensor_lines[a][0]}~{sensor_lines[a][-1]}'])
    a = GRAPH_ASK['parts']
    parts = sorted(r['b'] for r in graph['rels'] if r['type'] == 'USES_PART' and owner.get(r['a']) == a)
    comps = [r['b'] for r in graph['rels'] if r['type'] == 'HAS_COMPONENT' and r['a'] == a]
    rows.append(['2', a, 'part', ' · '.join(parts + ['없음'] * (len(comps) - len(parts))), f'입력/자료/구성요소_목록.csv:{comp_lines[a][0]}~{comp_lines[a][-1]} 교체부품 칸 · 입력/자료/품번_교차표.csv'])

    def users(code):
        ids = [i for i, p in props.items() if label[i] == 'Part' and (i == code or code in p.get('other_codes', []))]
        return sorted({owner[r['a']] for r in graph['rels'] if r['type'] == 'USES_PART' and r['b'] in ids})
    shared = users(GRAPH_SHARED_PART)
    rows.append(['3', GRAPH_SHARED_PART, 'status', ' · '.join(props[x]['status'] for x in shared), '입력/자료/구성요소_목록.csv 교체부품 칸 · 입력/자료/설비_대장.csv 상태 칸'])
    for code in GRAPH_ASK['aliases']:
        rows.append(['3', code, 'asset', ' · '.join(users(code)), '입력/자료/품번_교차표.csv · 입력/자료/구성요소_목록.csv 교체부품 칸'])
    rows.append(['3', GRAPH_ASK['missing'], 'note', '원자료에 없는 품번', '입력/자료/예비품_목록.csv · 입력/자료/품번_교차표.csv에 없음'])
    return rows


def graph_expect_text(rows, course):
    import session2_answers as ANS
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator='\n')
    w.writerow(ANS.GRAPH_EXPECT_COLUMNS)
    for r in rows:
        w.writerow(r)
    return f'# {F.MARK} — {ANS.GRAPH_EXPECT_EXPLAIN[course]}\n' + buf.getvalue()


MIGRATED = {   # 2회차 네 랩은 새 프로젝트 구조로 바뀌었다 — 이 생성기는 학생 폴더 · ZIP · package-index를 쓰지 않는다
    'integrated-02-ontology': 'build_session2_projects.py ontology --apply [--completed]',
    'integrated-02-graph': 'build_session2_projects.py graph --apply [--completed]',
    'practical-02-ontology': 'build_session2_projects.py ontology --course 실전반 --apply [--completed]',
    'practical-02-graph': 'build_session2_projects.py graph --course 실전반 --apply [--completed]',
}


def main():
    """`--reference`일 때만 강사 참조 모델(reference/<과정>/ 갈래별 schema · graph)을 쓴다. 학생 랩은 MIGRATED의 새 생성기가 만든다."""
    import sys as _sys
    if '--reference' not in _sys.argv:
        raise SystemExit('build_labs.py는 2회차 학생 랩을 만들지 않습니다. 랩은 새 생성기로 만듭니다:\n'
                         + '\n'.join(f'  {lab_id}: {how}' for lab_id, how in MIGRATED.items())
                         + '\n강사 참조 모델만 다시 쓰려면 python build_labs.py --reference')
    for course, _ in COURSES:
        with D.for_course(course):
            for branch in REFERENCE_BRANCHES[course]:
                schema, graph = reference_model(course == '실전반', branch)
                dest = TEACHER/course/BRANCH_DIRS[branch]
                dump(dest/'schema.json', schema); dump(dest/'graph.json', graph)
    write(TEACHER/'실전반/README.md', PRACTICAL_BRANCH_README)
    print('강사 참조 모델을 썼습니다: ' + ', '.join(f'{c} {REFERENCE_BRANCHES[c]}' for c, _ in COURSES))


if __name__ == '__main__':
    main()
