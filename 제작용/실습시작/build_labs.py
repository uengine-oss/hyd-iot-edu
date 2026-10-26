"""온라인2 독립 시작본과 오프라인1 진입 가이드. 강사 모델은 제작용에만 생성."""
from pathlib import Path
import csv
import hashlib
import html
import json
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'산출물'
TEACHER = ROOT/'제작용/실습시작/reference'
COURSES = [('통합반','integrated'),('실전반','practical')]
LAB3 = '02일차_실습3_온톨로지설계'
LAB4 = '02일차_실습4_그래프구현과검증'

def write(path, text):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(text,encoding='utf-8')

def dump(path, value):
    write(path,json.dumps(value,ensure_ascii=False,indent=2)+'\n')

def rows(name):
    path=OUT/'통합반/실습/02회차/랩'/LAB3/'자료'/name
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def reference_model(supply=False):
    """원자료의 명시된 동일 모델/별칭 근거로 만든 강사 참조 모델."""
    nodes=[];rels=[]
    def node(label,id,**props):nodes.append({'labels':[label],'props':{'id':id,**props}})
    def rel(type,a,b,**props):rels.append({'type':type,'a':a,'b':b,'props':props})
    components=[('cooler','오일 쿨러'),('fan','쿨러 팬'),('pump-a','주 펌프 (A)'),('pump-b','예비 펌프 (B)'),('motor','구동 모터'),('tank','작동유 탱크')]
    channels={'TS1':('cooler','유온','℃',48,65,'upper',False),'CE':('cooler','냉각 효율','%',84,None,None,True),'PS1':('pump-a','토출 압력','bar',182,130,'lower',False),'FS1':('pump-a','유량','L/min',9,None,None,False),'VS1':('fan','팬 진동','mm/s',0.6,2.0,'upper',False)}
    part_map={'P-PMP-SEAL':'pump-a','P-FAN-BRG':'fan','P-CLR-CORE':'cooler'}
    for p in rows('예비품_목록.csv'):node('Part',p['품번'],name=p['품명'])
    for tag,(_,quantity,unit,*_) in channels.items():node('Quantity','quantity:'+tag,name=quantity,unit=unit)
    for asset in rows('설비_대장.csv'):
        aid=asset['설비코드'];node('Asset',aid,name=asset['설비명'])
        for key,name in components:
            cid=aid+':'+key;node('Component',cid,name=name);rel('HAS_COMPONENT',aid,cid)
        for tag,(component,quantity,unit,normal,limit,direction,derived) in channels.items():
            sid=aid+':'+tag
            props={'tag':tag,'normal':normal,'unit':unit,'derived':derived}
            if limit is not None:props.update(limit=limit,limit_direction=direction)
            node('Sensor',sid,**props);rel('MONITORED_BY',aid+':'+component,sid);rel('OBSERVES',sid,'quantity:'+tag)
        for sku,comp in part_map.items():rel('USES_PART',aid+':'+comp,sku)
    if supply:
        names=[]
        for record in rows('공급_조건.csv'):
            name=record['공급사'];sid='supplier:'+name.split(' ')[0]
            if sid not in names:node('Supplier',sid,name=name);names.append(sid)
            rel('SUPPLIES',sid,record['품번'],approved=record['승인공급사']=='예',price_manwon=float(record['단가(만원)']),defect_rate=float(record['불량률']),lead_days=int(record['납기(일)']))
    definitions={
      'Asset':{'meaning':'개별 설비','required':{'id':'string','name':'string'}},
      'Component':{'meaning':'개별 설비에 속한 구성요소','required':{'id':'string','name':'string'}},
      'Sensor':{'meaning':'설비별 물리 또는 계산 계측 채널','required':{'id':'string','tag':'string','unit':'string','normal':'number','derived':'boolean'},'optional':{'limit':'number','limit_direction':['upper','lower']}},
      'Quantity':{'meaning':'측정하는 물리량 종류','required':{'id':'string','name':'string','unit':'string'}},
      'Part':{'meaning':'공용으로 주문하는 부품 품목','required':{'id':'string','name':'string'}}}
    relation_defs={'HAS_COMPONENT':{'from':'Asset','to':'Component','cardinality':'1:N'},'MONITORED_BY':{'from':'Component','to':'Sensor','cardinality':'1:0..N'},'OBSERVES':{'from':'Sensor','to':'Quantity','cardinality':'N:1'},'USES_PART':{'from':'Component','to':'Part','cardinality':'N:0..N'}}
    if supply:
        definitions['Supplier']={'meaning':'견적을 제공한 공급사','required':{'id':'string','name':'string'}}
        relation_defs['SUPPLIES']={'from':'Supplier','to':'Part','cardinality':'N:M','properties':{'approved':'boolean','price_manwon':'number','defect_rate':'number','lead_days':'integer'}}
    schema={'classes':definitions,'relations':relation_defs,'identity':'id는 전체 그래프에서 고유. 구성요소와 계측 채널은 설비별, 부품은 품번별.','constraints':['각 Component는 Asset 하나에 속함','각 Sensor는 Component 하나와 Quantity 하나에 연결','derived=true인 CE는 물리 계기를 뜻하지 않음','limit 생략은 0과 다름']}
    return schema,{'nodes':nodes,'rels':rels}

CSS='''*{box-sizing:border-box}body{margin:0;background:#f4f6f3;color:#20342f;font:17px/1.8 "Malgun Gothic",sans-serif}main{max-width:1000px;margin:auto;padding:52px 28px}h1{font-size:36px;line-height:1.35}h2{font-size:25px;line-height:1.45;margin:0 0 18px}section{background:white;border:1px solid #dce5df;border-radius:16px;padding:30px;margin:24px 0}a{color:#176554;text-underline-offset:4px}nav{display:flex;gap:14px;flex-wrap:wrap}nav a,.button{display:inline-block;background:#e2eee7;padding:8px 16px;border-radius:8px}p{margin:12px 0}li{margin:8px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#edf2ef;padding:18px;border-radius:8px;font-size:15px}code{font-family:Consolas,monospace}table{border-collapse:collapse;width:100%}td,th{padding:12px;border-bottom:1px solid #dce5df;text-align:left;vertical-align:top}img{max-width:100%;height:auto}small{color:#607269}.check{border-left:4px solid #32886a;padding:12px 18px;background:#edf6ef}details{border-top:1px solid #dce5df;margin-top:18px;padding-top:12px}summary{cursor:pointer}'''

def page(title,intro,sections):
    nav=''.join(f'<a href="#s{i}">{i:02d} {html.escape(t)}</a>' for i,(t,_) in enumerate(sections,1))
    body=''.join(f'<section id="s{i}"><h2>{i:02d} {html.escape(t)}</h2>{content}</section>' for i,(t,content) in enumerate(sections,1))
    return f'<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>{CSS}</style><main><small>HYD · 실습 가이드</small><h1>{title}</h1><p>{intro}</p><nav>{nav}</nav>{body}</main></html>'

RULES='''# 실습 작업 규칙

- START.md의 이번 과제와 자료를 먼저 확인한다. 요구가 모호하면 필요한 질문을 한다.
- 입력/와 자료/는 보존한다. 새 코드와 산출물은 결과/에 작성한다.
- 원자료에 없는 값·관계·실행 결과를 만들지 않는다. 미확인과 값 없음, 0을 구별한다.
- 학생이 정한 요구와 제약 안에서 구현한다. 무관한 서비스·대시보드·선정 규칙을 추가하지 않는다.
- 실행한 명령, 실제 결과, 남은 미확인을 구별한다. 검사 통과를 위해 검사 기준이나 원자료를 바꾸지 않는다.
- DB 작업은 안내된 별도 랩 주소만 사용한다. 포털 DB와 시스템 파일을 수정하거나 전체 삭제하지 않는다.
- 접속 키·비밀번호를 코드나 결과 기록에 넣지 않는다. 개인 GitHub·commit·push는 요구하지 않는다.
- 결과 파일을 덮어쓸 변경 전에는 기존 작업을 별도 보관한다.
'''

CHECKER='''"""학생 결과의 JSON 구조 검사. 생성·수정·DB 접속을 하지 않는다."""
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
    print('구조 확인 필요\\n'+'\\n'.join(errors));sys.exit(1)
print(f'구조 검사 통과: 노드 {len(nodes)}개, 관계 {len(rels)}개. 원자료의 의미·단위·질문별 답은 별도로 대조하세요.')
'''

QUESTIONS={
'통합반':['설비별 구성 요소에는 어떤 센서가 연결되어 있는가?','센서의 물리량·단위·정상값·한계는 무엇인가?','같은 교체 부품을 사용하는 설비는 무엇인가?'],
'실전반':['선택한 부품을 사용하는 설비와 구성 요소는 무엇인가?','그 부품의 공급사별 승인 여부·단가·불량률·납기는 무엇인가?','원자료에 없는 품번을 조회했을 때 결과 없음이 구별되는가?']}

def pack(folder):
    archive=folder.with_suffix('.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for file in sorted(folder.rglob('*')):
            if file.is_file() and '__pycache__' not in file.parts and file.name!='.env':
                z.write(file,file.relative_to(folder.parents[2]))
    return archive

def main():
    # 이전 작업의 실제 캡처·가이드를 정확한 경로로 재사용. 확정 원본 JSON/영상은 변경하지 않음.
    for course,_ in COURSES:
        schema,graph=reference_model(course=='실전반')
        dump(TEACHER/course/'schema.json',schema);dump(TEACHER/course/'graph.json',graph)
    base_schema,base_graph=reference_model()
    catalog=[]
    for course,slug in COURSES:
        practical=course=='실전반';questions=QUESTIONS[course]
        for number,name in [(3,LAB3),(4,LAB4)]:
            folder=OUT/course/'실습/02회차/랩'/name
            for sub in ['입력','결과']: (folder/sub).mkdir(exist_ok=True)
            write(folder/'AGENTS.md',RULES)
            write(folder/'.github/copilot-instructions.md',RULES)
            write(folder/'CLAUDE.md',RULES)
            if number==3:
                if not (folder/'입력/관계그림.json').is_file():
                    raise FileNotFoundError('이전 단계 관계 그림 입력이 없습니다: '+str(folder))
                if practical:
                    dump(folder/'입력/schema.json',base_schema);dump(folder/'입력/graph.json',base_graph)
                    memo=folder/'자료/현장_메모.md'
                    write(memo,memo.read_text(encoding='utf-8-sig').replace('이번 정리에 넣을지는 판단해 주세요.','이번 정리에서 부품별 사용 설비와 함께 조회할 필수 자료입니다.').replace('전부 답할 수 있어야 하는 것은 아니고, 무엇부터 담을지 정하실 때 참고해 주세요.','이번 과제의 필수 질문은 START.md에서 확인해 주세요.'))
                title='부품의 사용 설비와 공급 정보를 연결하기' if practical else '현장 자료를 질문에 답하는 모델로 만들기'
                intro='제공된 설비·센서·부품 모델을 읽고, 공급 조건을 연결한 모델을 만듭니다. 공급사 선정·점수화는 하지 않습니다.' if practical else '현장 목록과 관계 그림을 대조해 설비별 센서와 공유 부품을 구별하는 모델을 만듭니다.'
                start='입력/의 이전 모델을 출발점으로 사용합니다. 공급 정보는 아직 연결되어 있지 않습니다.' if practical else '자료/의 CSV·현장 메모와 입력/관계그림.json에서 출발합니다. 이번 스키마·인스턴스는 아직 작성되지 않았습니다.'
                command='python check.py'
                outputs='결과/schema.json, 결과/graph.json, 결과/요구사항.md, 결과/자료_검토.md'
                work='공급 조건을 어디에 표현할지 정하고, 기존 설비·부품 연결을 유지하면서 모델을 확장하세요. 같은 공급사라도 부품에 따라 조건이 다름을 반영하세요.' if practical else '종류와 개별 대상을 나누고, 식별자·속성의 자료형·필수 여부·관계 방향·연결 수를 정의하세요. 그 정의로 원자료의 인스턴스를 만드세요.'
                write(folder/'check.py',CHECKER)
            else:
                shutil.copy2(ROOT/'제작용/실습시작/lab_db.py',folder/'lab_db.py')
                schema,graph=reference_model(practical)
                dump(folder/'입력/schema.json',schema);dump(folder/'입력/graph.json',graph)
                source=OUT/course/'실습/02회차/랩'/LAB3/'자료'
                shutil.copytree(source,folder/'입력/자료',dirs_exist_ok=True)
                write(folder/'입력/요구사항.md','# 제공 시작 모델의 질문\n\n'+'\n'.join('- '+q for q in questions)+'\n')
                write(folder/'입력/자료_검토.md','# 제공 모델의 자료 처리 근거\n\n현장_메모.md의 동일 모델·별칭·중복 설명을 적용했다. HYD-01 TS1의 중복 행은 하나로, 같은 태그의 다른 설비 센서는 별개로 표현했다. HYD-02 PS1의 숫자와 단위를 분리했다. HYD-03 VS1의 단위는 동일 모델 설명과 다른 두 설비의 mm/s에서 보완했다. CE는 계산 채널이다. 한계가 없는 CE·FS1은 limit 속성을 생략했다. HYD-03 주 펌프의 부품은 메모 2·5절의 공용 부품 근거를 사용했다. 이는 학습용 참조 설계이며 학생의 이번 적재·조회 결과가 아니다.\n')
                title='부품별 사용 설비와 공급 조건 조회하기' if practical else '모델을 그래프에 적재하고 질문으로 검증하기'
                intro='앞 단계의 완성 모델에서 출발해 적재·조회 로직을 직접 작성합니다.'
                start='입력/에 앞 단계 완성 모델과 원자료가 있습니다. 이전 개인 결과 없이 시작할 수 있습니다. 개인 모델을 쓰려면 제공 입력을 보존하고 별도 폴더에 복사하세요.'
                command='python lab_db.py\nNeo4j Browser에서 작성한 적재문 실행 → 조회문 실행 → 같은 적재문 재실행'
                outputs='결과/load.cypher, 결과/query.cypher, 결과/검증_기록.md'
                work='AI와 적재·조회문을 작성하세요. 같은 입력을 두 번 적재해도 대상과 관계가 늘지 않아야 합니다. 이름이 바뀌어도 같은 ID의 대상은 유지되어야 합니다. 전체 삭제문은 사용하지 마세요.'
            qlist='\n'.join(f'{i}. {q}' for i,q in enumerate(questions,1))
            body=f'# {title}\n\n{intro}\n\n## 출발점\n\n{start}\n\n## 이번에 해결할 질문\n\n{qlist}\n\n## 작업\n\n{work}\n\nAI에게 전달할 목표·입력·제약·확인 방법을 먼저 자기 말로 정리하세요. 관련 자료를 함께 읽고, 필요한 만큼 계획을 확인한 뒤 구현하세요. 결과는 직접 실행해 원자료와 대조하세요.\n\n## 저장할 결과\n\n{outputs}\n\n## 확인\n\n{command}\n\n형식 검사나 실행 성공만으로 완료하지 않습니다. 질문별 원자료의 행과 실제 답을 대조하고, 수정한 점·확인하지 못한 점을 짧게 남기세요.\n\n## 저장과 다음 실습\n\n결과 폴더를 저장하고 다시 열어 확인하세요. 재부팅 전에 보관할 결과는 USB 또는 개인 클라우드에 복사하세요. 다음 실습도 독립 시작본을 제공하므로 개인 결과는 선택 입력입니다.\n'
            write(folder/'START.md',body);write(folder/'준비_안내.md',body)
            write(folder/'결과/README.md','이번 과제의 모델과 구현 결과를 여기에 저장합니다.\n')
            if number==3:
                write(folder/'결과/요구사항.md','# 이번에 만들 결과\n\n## 목표와 질문\n\n## 사용할 자료와 범위\n\n## 지켜야 할 조건\n\n## 확인할 입력과 기대 결과\n')
                write(folder/'결과/자료_검토.md','# 원자료 대조\n\n| 자료·행 | 확인한 문제 또는 근거 | 선택한 처리 | 결과 확인 |\n|---|---|---|---|\n')
                write(folder/'결과/README.md','이번 과제의 모델과 구현 결과를 여기에 저장합니다.\n')
            write(folder/'입력/README.md',start+'\n')
            qs=''.join(f'<li>{html.escape(q)}</li>' for q in questions)
            expected='<li>설비가 다른 TS1은 구별되고 HYD-01의 중복 행은 하나로 처리됩니다.</li><li>CE가 물리 센서로 잘못 설명되지 않고, 한계 없음과 0이 구별됩니다.</li><li>공용 부품은 품번으로 연결되며 사용 설비를 따라갈 수 있습니다.</li>'
            if practical:expected='<li>P-PMP-SEAL의 사용 설비는 HYD-01·02·03입니다.</li><li>공급 조건 3행을 원자료와 대조합니다. 비승인 공급사도 승인 여부를 표시해 구별합니다.</li><li>다른 부품은 그 부품의 조건을 반환하고, 없는 품번은 결과 없음으로 나타납니다.</li><li>가격·납기로 공급사를 자동 선정하지 않습니다.</li>'
            if number==4:expected+='<li>같은 입력을 재적재해도 노드·관계 수가 늘지 않습니다.</li>'
            next_link='../'+(LAB4 if number==3 else LAB3)+'/guide.html'
            sections=[('시작하기',f'<p>{start}</p><p>VS Code에서 <a href="START.md">START.md</a>를 열고 이번 요구를 확인하세요.</p><pre>입력/   이전 단계 자료\n자료/   현장 원자료(설계 실습)\n결과/   이번에 만들 결과\nAGENTS.md   작업 규칙</pre>'),('요구 정하기',f'<ol>{qs}</ol><p>자료에서 답의 근거를 찾고 AI에 전달할 목표와 제약을 정리하세요.</p>'),('AI와 만들기',f'<p>{work}</p><p>한 기능의 결과를 확인한 뒤 다음 작업을 요청하세요. 수정 요청에는 입력·기대 결과·실제 결과를 함께 전달하세요.</p><details><summary>요청을 정리할 때 볼 항목</summary><p>만들 결과 / 참고할 자료 / 바꾸지 않을 범위 / 성공을 확인할 사례</p></details>'),('결과 확인하기',f'<pre>{html.escape(command)}</pre><ul>{expected}</ul><p class="check">원자료와 실제 결과를 대조하세요. AI의 완료 메시지는 실행 결과를 대신하지 않습니다.</p>'),('저장하기',f'<p>{outputs}</p><p>저장한 파일을 다시 열어 내용을 확인하고, 보관할 결과를 USB 또는 개인 클라우드에 복사하세요.</p><p>다음 실습은 시작 도구에서 새로 선택합니다. 개인 결과를 가져오지 않아도 시작할 수 있습니다.</p>')]
            if number==4:
                sections[0]=(sections[0][0],sections[0][1]+'<p>터미널에서 아래 명령을 실행하세요. Docker가 실행 중이어야 합니다.</p><pre>python lab_db.py</pre><p>「랩 DB 준비 완료」가 나오면 열린 Browser의 Protocol에서 bolt://를 선택하고 Connection URL에는 출력 주소의 127.0.0.1:포트 부분만 넣으세요. Database user는 neo4j, Password는 비워 두고 Connect를 누릅니다. 연결 정보는 랩_연결.json에도 저장됩니다.</p>')
                figures='<p>공유 부품 조회 예시입니다. 각 품번의 사용 설비를 원자료와 대조하세요.</p><img src="images/part-usage.png" alt="세 부품 각각에 HYD-01, HYD-02, HYD-03이 조회된 실제 Neo4j 결과">'
                if practical:
                    figures+='<p>P-PMP-SEAL의 공급 조건입니다. 승인 여부와 함께 단가(만원), 불량률, 납기(일)를 확인하세요. 0.12는 12%입니다.</p><img src="images/supplier-conditions.png" alt="P-PMP-SEAL의 공급사 3곳과 승인 여부, 단가, 불량률, 납기 조회 결과">'
                sections[3]=(sections[3][0],sections[3][1]+figures)
            write(folder/'guide.html',page(title,intro,sections))
            write(folder/'안내.html',page(title,intro,sections))
            archive=pack(folder)
            relative=archive.relative_to(ROOT).as_posix()
            catalog.append({'id':f'{slug}-02-'+('ontology' if number==3 else 'graph'),'course':course,'session':'온라인 02회차','title':title,'version':'2026-10-26-lab-v2','folder':f'02회차/랩/{name}','path':relative,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()})
    dump(ROOT/'제작용/실습시작/package-index.json',{'labs':catalog})
    # 오프라인1은 두 과정 공통이며 실전 온라인2 공급 확장을 요구하지 않는다.
    for course,_ in COURSES:
        sections=[('관계 그림 만들기','<p>쿨러에서 센서·고장·원인·조치로 관련 대상을 묶어 확장합니다. 각 화살표를 문장으로 읽고 JSON을 저장하세요.</p><p><a class="button" href="랩/01일차_실습4_관계그림/가이드.html">ARROWS 단계별 사진 가이드</a></p>'),('최소 모델 만들기','<p>설비 목록과 관계 그림을 대조해 개별 대상을 구분하고 종류·속성·관계의 정의와 예시 데이터를 만드세요.</p><p><a href="../../../../통합반/실습/02회차/랩/02일차_실습3_온톨로지설계/guide.html">공통 모델 작업 안내</a></p><p class="check">설비가 다른 같은 이름의 센서가 합쳐지지 않았는지, 부품의 품번과 연결 방향이 맞는지 확인합니다.</p>'),('랩 그래프에서 확인하기','<p>강사가 준비한 별도 랩 DB에서 제공 적재 절차를 실행하고, 설비·센서·부품 질문의 결과를 원자료와 대조합니다.</p><p>연결 주소와 제공 적재 절차는 리허설 후 이 위치에 연결합니다.</p>'),('기준 지도와 비교하기','<p>학교 PC에 준비된 HYD 포털의 지식 지도를 열고 설비를 선택하세요. 구성요소와 센서의 연결을 개인 모델과 비교합니다.</p><p class="check">같은 의미를 어떤 종류·속성·방향으로 표현했는지 설명할 수 있으면 됩니다. 개인 모델은 포털에 자동 반영되지 않습니다.</p>'),('모델과 질문 보완하기','<p>질문에 답하지 못한 관계·속성을 원자료에서 찾아 보완하세요. 영향을 받은 질문과 기존 질문을 다시 실행하고 결과를 저장하세요.</p>'),('저장하고 이어가기','<p>관계도 JSON, schema.json, graph.json, 질의와 확인 결과를 한 작업 폴더에 보관하세요. 재부팅 전에 USB 또는 개인 클라우드로 복사하고 복사본을 다시 열어 확인하세요.</p><p>다음 실습은 제공 시작본으로도 시작할 수 있습니다.</p>')]
        write(OUT/course/'실습/01회차/오프라인_가이드.html',page('설비 정보를 관계와 모델로 표현하기','관계 그림을 만들고 모델로 정리한 뒤, 질문의 답을 원자료와 비교합니다.',sections))
    print('두 과정 설계·구현 시작본 4개, ZIP 4개, 오프라인1 가이드 초안 생성')

if __name__=='__main__':main()
