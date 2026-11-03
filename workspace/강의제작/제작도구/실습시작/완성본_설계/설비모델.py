"""설비 대장·현장 메모와 센서·부품 목록을 읽어 그래프를 만든다."""
import csv
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / '자료'
rules = json.loads((HERE / '표기_기준.json').read_text(encoding='utf-8'))
NAME_ALIAS = rules['구성요소_별칭']
CANON_NAME = rules['구성요소_이름']
WHAT_ALIAS = rules['물리량_별칭']
UNIT = rules['단위_환산']
QUANTITIES = rules['물리량_단위']

def rows(name):
    with (DATA / name).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


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

def base_graph():
    nodes=[];rels=[];index={}
    def node(label,id,**props):
        if id in index:raise ValueError('중복 id '+id)
        index[id]=len(nodes);nodes.append({'labels':[label],'props':{'id':id,**{k:v for k,v in props.items() if v is not None}}})
    def rel(type,a,b,**props):rels.append({'type':type,'a':a,'b':b,'props':{k:v for k,v in props.items() if v is not None}})
    parts={p['품번']:p for p in rows('예비품_목록.csv')};cross=rows('품번_교차표.csv')
    for pid,p in parts.items():
        alt=sorted({c['다른표기'] for c in cross if c['사내품번']==pid})
        node('Part',pid,name=p['품명'],other_codes=alt)
    quantity_ids = {'quantity:'+WHAT_ALIAS[s['재는것']] for s in rows('센서_목록.csv')}
    for qid in sorted(quantity_ids):
        name,unit = QUANTITIES[qid]
        node('Quantity',qid,name=name,unit=unit)
    assets=rows('설비_대장.csv');models={}
    for a in assets:
        if a['상태']=='코드 통합':continue
        legacy=[x['설비코드'] for x in assets if x['상태']=='코드 통합' and x['기능위치']==a['기능위치'] and x['일련번호']==a['일련번호']]
        models[a['설비코드']]=a['모델']
        node('Asset',a['설비코드'],name=a['설비명'],model=a['모델'],maker=a['제조사'],serial=a['일련번호'],functional_location=a['기능위치'],
             installed=a['설치일'],status=a['상태'],legacy_codes=legacy or None)
    components = rows('구성요소_목록.csv')
    model_keys = {}
    for component in components:
        if '철거' not in component['비고']:
            model_keys.setdefault(models[component['설비코드']], set()).add(NAME_ALIAS.get(component['구성요소'], 'pump'))
    comps={}
    for c in components:
        if '철거' in c['비고']:continue
        aid=c['설비코드'];model=models[aid]
        keys=model_keys[model]
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
        q='quantity:'+WHAT_ALIAS[s['재는것']];qunit=QUANTITIES[q][1]
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
        else:rel('MONITORED_BY',aid+':'+comp_key(place,model_keys[model]),sid)
        rel('OBSERVES',sid,q)
    return nodes,rels
