"""학생 결과의 구조·자료형 검사. 생성·수정·DB 접속을 하지 않는다.
사용: python check.py            (결과/schema.json·graph.json)
      python check.py 폴더        (다른 폴더의 schema.json·graph.json)
"""
from pathlib import Path
import json,sys
root=Path(__file__).resolve().parent
base=Path(sys.argv[1]) if len(sys.argv)>1 else root/'결과'
errors=[];warnings=[]
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
    uniq=sorted(set(warnings));print(f'참고 {len(uniq)}건(정의와 다른 속성 등):');print('\n'.join('  '+w for w in uniq[:12])+('\n  …' if len(uniq)>12 else ''))
if errors:
    print(f'구조 확인 필요 {len(errors)}건');print('\n'.join(errors[:40])+('\n…' if len(errors)>40 else ''));sys.exit(1)
print(f'구조 검사 통과: 노드 {len(nodes)}개, 관계 {len(rels)}개. 원자료의 의미·단위·질문별 답은 별도로 대조하세요.')
