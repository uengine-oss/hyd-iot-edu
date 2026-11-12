from pathlib import Path
import sys
import hashlib as _h
_PROVIDED = {
 "app/ui/render.py": "f2a80ab6f2d359d26b9610dadab032638decd2496da7a9aac143a1a704320c64",
 "app/utils/actions.py": "1427a63f3bff40a2718d8623e1527e69b2385a001c66bf1af0fc8de1af4bcdeb",
 "app/utils/cypher.py": "02627ba39d8713a8964e2c761777813bc6215fb0c991f3a63cf21ea9cc76d9b0",
 "app/utils/db.py": "0c15bbfc33696a8d804884ec9485b4e19b6d407a74424288c954be978260f76a",
 "app/utils/results.py": "1c5b0596745e9ac1e9b7f06d84c7463d99720597edcf46801d32a51e640ae86b",
 "run.py": "a2be7676a114229a2f866a562d53df8f281f5acba64e724816df9cb0a78f1878"
}
def provided_errors(root):
    out = []
    for name, digest in _PROVIDED.items():
        p = root / name
        if not p.is_file():
            out.append(f'제공 파일이 없습니다: {name} — 받은 ZIP의 것으로 되돌리세요.')
        elif _h.sha256(p.read_bytes()).hexdigest() != digest:
            out.append(f'제공 파일이 바뀌었습니다: {name} — 받은 ZIP의 것으로 되돌리세요.')
    return out
def chosen_errors(root):
    """app/features/decisions.csv — 빈 칸 · 근거 꼴(파일:줄)만 본다. 고른 것이 맞는지는 보지 않는다."""
    import csv, io, re
    p = root / 'app/features' / 'decisions.csv'
    if not p.is_file():
        return ['app/features/decisions.csv가 없습니다 — 받은 ZIP의 빈 틀을 지우지 않습니다.']
    lines = [x for x in p.read_text(encoding='utf-8-sig').splitlines() if x.strip() and not x.lstrip().startswith('#')]
    rows = list(csv.DictReader(io.StringIO('\n'.join(lines))))
    need = ['지점', '고른_것', '근거', '바뀌는_답']
    if not lines or [c.strip() for c in csv.reader([lines[0]]).__next__()] != need:
        return ['app/features/decisions.csv: 열 이름이 ' + ','.join(need) + '이어야 합니다.']
    out = []
    for n, r in enumerate(rows, 1):
        empty = [c for c in need if not (r.get(c) or '').strip()]
        if empty:
            out.append(f'app/features/decisions.csv {n}번째 행: 빈 칸 ' + ', '.join(empty) + '(못 정했으면 고른_것에 「미결」).')
        elif not re.search(r'[^\s:]+:\d+', r['근거']):
            out.append(f'app/features/decisions.csv {n}번째 행: 근거에 파일:줄이 없습니다.')
    return out
_root = Path(__file__).resolve().parents[2]
_pre = provided_errors(_root) + chosen_errors(_root)
"""학생 결과의 구조·자료형 검사. 생성·수정·DB 접속을 하지 않는다.
사용: python check.py            (output/schema.json·graph.json)
      python check.py 폴더        (다른 폴더의 schema.json·graph.json)
"""
from pathlib import Path
import json,sys
root=Path(__file__).resolve().parents[2]
base=Path(sys.argv[1]) if len(sys.argv)>1 else root/'output'
errors=[];warnings=[];nodes=[];rels=[];labels_by_id={}
missing=[n for n in ('schema.json','graph.json') if not (base/n).is_file()]
if missing:
    print('아직 검사할 결과가 없습니다: '+', '.join(base.name+'/'+n for n in missing))
    print('python run.py export로 그래프를 저장한 뒤 다시 실행하세요. 이 검사는 구조만 보고, 질문의 답은 원자료와 따로 대조합니다.')
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
        errors.append('schema.json에 classes·relations가 없습니다.');classes=classes or {};relations=relations or {}
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
    uniq=sorted(set(warnings));print(f'참고 {len(uniq)}건(정의와 다른 속성 등):');print('\n'.join('  '+w for w in uniq[:12])+('\n  …' if len(uniq)>12 else ''))
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
errors = _pre + errors
if errors:
    print(f'구조 확인 필요 {len(errors)}건');print('\n'.join(errors[:40])+('\n…' if len(errors)>40 else ''));sys.exit(1)
print(f'구조 검사 통과: 노드 {len(nodes)}개, 관계 {len(rels)}개. 원자료의 의미·단위·질문별 답은 별도로 대조하세요.')
