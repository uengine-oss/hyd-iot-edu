"""학생 결과의 JSON 구조 검사. 생성·수정·DB 접속을 하지 않는다."""
from pathlib import Path
import json,sys
root=Path(__file__).resolve().parent
errors=[]
try:
    schema=json.loads((root/'결과/schema.json').read_text(encoding='utf-8-sig'))
    graph=json.loads((root/'결과/graph.json').read_text(encoding='utf-8-sig'))
    if not isinstance(schema,dict) or not schema:errors.append('스키마 정의가 비어 있습니다.')
    nodes=graph.get('nodes',[]);rels=graph.get('rels',[])
    if not nodes or not rels:errors.append('노드 또는 관계가 비어 있습니다.')
    ids=[]
    for n in nodes:
        id=n.get('props',{}).get('id')
        if not isinstance(id,str) or not id:errors.append('문자열 id가 없는 노드가 있습니다.')
        elif id in ids:errors.append('중복 id: '+id)
        ids.append(id)
        if not isinstance(n.get('labels'),list) or not n['labels']:errors.append('종류가 없는 노드: '+str(id))
    seen=set()
    for r in rels:
        key=(r.get('type'),r.get('a'),r.get('b'))
        if not isinstance(key[0],str) or not key[0]:errors.append('관계 이름이 없습니다.')
        if key[1] not in ids or key[2] not in ids:errors.append('없는 관계 끝점: '+str(key))
        if key in seen:errors.append('중복 관계: '+str(key))
        seen.add(key)
except (OSError,ValueError,TypeError,AttributeError) as e:
    errors.append(str(e))
if errors:
    print('구조 확인 필요\n'+'\n'.join(errors));sys.exit(1)
print(f'구조 검사 통과: 노드 {len(nodes)}개, 관계 {len(rels)}개. 원자료의 의미·단위·질문별 답은 별도로 대조하세요.')
