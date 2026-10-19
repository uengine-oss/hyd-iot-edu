"""문서·입력자료·배포 ZIP만 생성한다. 생성된 질의와 실습은 실행하지 않는다."""
from pathlib import Path
import sys,json,re,zipfile,hashlib,shutil,html,io,importlib.util
from lxml import etree as E
from reportlab.platypus import SimpleDocTemplate,Paragraph,HRFlowable
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pypdf import PdfReader
import pypdfium2 as pdfium
from PIL import Image,ImageDraw
D=Path(__file__).resolve().parents[4];C=Path(sys.argv[1]);EV=D/'.evidence/session02';EV.mkdir(exist_ok=True)
I=C/'산출물/교재/대본/통합반_온라인/02회차';P=D/'산출물/교재/대본/실전반_온라인/02회차'
def write(p,s):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s,encoding='utf8')
def speech(t):return '\n'.join(l.replace('**','') for l in t.splitlines() if not l.startswith(('>','---'))).strip()+'\n'
def theory_notes(folder):
 notes={}
 for f in sorted(folder.glob('*_이론_*.md')):
  for b in re.split(r'(?=^## \[SLIDE )',f.read_text('utf8'),flags=re.M)[1:]:
   m=re.match(r'## \[SLIDE (\d+)(?:~(\d+))?\]',b);a=int(m[1]);z=int(m[2] or m[1]);text=' '.join(l.strip().replace('**','') for l in b.splitlines()[1:] if l.strip() and not l.startswith(('>','#','---')))
   for n in range(a,z+1):notes[n]=text if n==a else f'{a}~{z}장 통합 발화는 {a}장 발표자 노트를 따른다.'
 return notes
def patch_notes():
 notes=theory_notes(I);deck=C/'만들기/decks/integrated/day02/통합반_02일차.md'
 blocks=re.split(r'(?=^## SLIDE )',deck.read_text('utf8'),flags=re.M)
 for n in range(1,73):
  blocks[n]=re.sub(r'^- 노트:.*\n?','',blocks[n],flags=re.M).replace('### 화면 구성','- 노트: '+notes[n]+'\n### 화면 구성',1)
 write(deck,''.join(blocks))
 path=C/'산출물/교재/PPTX/통합반_온라인/통합반_02일차.pptx';before=path.read_bytes();updates={};ns={'a':'http://schemas.openxmlformats.org/drawingml/2006/main','p':'http://schemas.openxmlformats.org/presentationml/2006/main'};REL='http://schemas.openxmlformats.org/package/2006/relationships';OFF='http://schemas.openxmlformats.org/officeDocument/2006/relationships/';CT='http://schemas.openxmlformats.org/package/2006/content-types'
 serial=lambda x:E.tostring(x,xml_declaration=True,encoding='UTF-8',standalone=True)
 with zipfile.ZipFile(io.BytesIO(before)) as z:
  ct=E.fromstring(z.read('[Content_Types].xml'));nn=max(int(re.search(r'notesSlide(\d+)',n)[1]) for n in z.namelist() if re.fullmatch(r'ppt/notesSlides/notesSlide\d+\.xml',n))+1
  for n in range(1,73):
   rp=f'ppt/slides/_rels/slide{n}.xml.rels';rels=E.fromstring(z.read(rp));found=[r for r in rels if r.get('Type')==OFF+'notesSlide']
   if found:idx=int(re.search(r'notesSlide(\d+)',found[0].get('Target'))[1]);data=z.read(f'ppt/notesSlides/notesSlide{idx}.xml')
   else:
    idx=nn;nn+=1;rid=max(int(r.get('Id')[3:]) for r in rels)+1;E.SubElement(rels,'{'+REL+'}Relationship',Id=f'rId{rid}',Type=OFF+'notesSlide',Target=f'../notesSlides/notesSlide{idx}.xml');updates[rp]=serial(rels);data=z.read('ppt/notesSlides/notesSlide1.xml');nr=E.fromstring(z.read('ppt/notesSlides/_rels/notesSlide1.xml.rels'))
    for r in nr:
     if r.get('Type')==OFF+'slide':r.set('Target',f'../slides/slide{n}.xml')
    updates[f'ppt/notesSlides/_rels/notesSlide{idx}.xml.rels']=serial(nr);E.SubElement(ct,'{'+CT+'}Override',PartName=f'/ppt/notesSlides/notesSlide{idx}.xml',ContentType='application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml');updates['[Content_Types].xml']=serial(ct)
   root=E.fromstring(data);body=root.xpath('//p:sp[p:nvSpPr/p:nvPr/p:ph[@type="body"]]/p:txBody',namespaces=ns)[0]
   for p in list(body):
    if p.tag=='{'+ns['a']+'}p':body.remove(p)
   p=E.SubElement(body,'{'+ns['a']+'}p');r=E.SubElement(p,'{'+ns['a']+'}r');E.SubElement(r,'{'+ns['a']+'}t').text=notes[n];updates[f'ppt/notesSlides/notesSlide{idx}.xml']=serial(root)
  out=io.BytesIO()
  with zipfile.ZipFile(out,'w') as dst:
   for item in z.infolist():dst.writestr(item,updates.pop(item.filename,z.read(item)))
   for name,data in updates.items():dst.writestr(name,data)
 path.write_bytes(out.getvalue());cfg=json.loads((I/'구성.json').read_text('utf8'));cfg['pptx_sha256']=hashlib.sha256(path.read_bytes()).hexdigest();write(I/'구성.json',json.dumps(cfg,ensure_ascii=False,indent=2)+'\n')
patch_notes()
# 공통 입력자료. 예제 그래프는 기준 시드의 조회용 부분집합이며 측정 결과가 아니다.
nodes=[dict(labels=['Asset'],props=dict(id='asset:hyd-01',code='HYD-01',name='유압 파워팩'))];rels=[]
for ident,name in [('cooler','오일 쿨러'),('fan','쿨러 팬'),('pump-a','주 펌프 (A)'),('pump-b','예비 펌프 (B)'),('motor','구동 모터'),('tank','작동유 탱크')]:
 nodes.append(dict(labels=['Component'],props=dict(id='comp:'+ident,name=name)));rels.append(dict(type='HAS_COMPONENT',a='asset:hyd-01',b='comp:'+ident,props={}))
for tag,name,comp,unit,normal,limit in [('TS1','유온','cooler','℃',48,65),('CE','냉각 효율','cooler','%',84,None),('PS1','토출 압력','pump-a','bar',182,130),('FS1','유량','pump-a','l/min',9,None),('VS1','팬 진동','fan','mm/s',.6,2)]:
 sid='sen:'+tag.lower();vid='sv:'+tag.lower();nodes.extend([dict(labels=['Sensor'],props=dict(id=sid,name=name+' 센서',tag=tag,unit=unit,isVirtual=tag=='CE')),dict(labels=['StateVariable'],props=dict(id=vid,name=name,unit=unit,normal=normal,limit=limit))]);rels.extend([dict(type='MONITORED_BY',a='comp:'+comp,b=sid,props={}),dict(type='OBSERVES',a=sid,b=vid,props={})])
graph=dict(nodes=nodes,rels=rels)
def val(x):
 if x is None:return 'null'
 if isinstance(x,bool):return str(x).lower()
 if isinstance(x,str):return "'"+x.replace('\\','\\\\').replace("'","\\'")+"'"
 return str(x)
loader=['// 교육용 별도 랩 DB에만 적용. HYD 기준 DB에 실행하지 않는다.']
for label in ['Asset','Component','Sensor','StateVariable']:loader.append(f'CREATE CONSTRAINT lab02_{label.lower()}_id IF NOT EXISTS FOR (n:{label}) REQUIRE n.id IS UNIQUE;')
for n in nodes:
 p=n['props'];loader.append('MERGE (n:'+n['labels'][0]+' {id:'+val(p['id'])+'}) SET n += {'+', '.join(k+':'+val(v) for k,v in p.items())+'};')
for r in rels:loader.append('MATCH (a {id:'+val(r['a'])+'}), (b {id:'+val(r['b'])+'}) MERGE (a)-[:'+r['type']+']->(b);')
blank='# 실습 확인 기록\n\n- 작업 폴더:\n- 자료 판본:\n- 사용한 주소·DB (인증값 제외):\n- 확인 시각:\n- 작성한 파일:\n- 원자료 근거:\n- 실제 확인 결과:\n- 수정 전·후와 이유:\n- 확인하지 못한 점:\n\n'
materials=[
 {'준비_안내.md':'# 관계 조회 준비\n\n강사가 제공하는 별도 랩 Neo4j DB와 접속 정보를 사용한다. 기존 HYD DB가 아니다. 접속 주소와 DB명은 배포 담당자가 수업 전에 제공한다. 인증값은 이 파일에 쓰지 않는다.\n\n예제_그래프.json은 it/neo4j/v2/instances.cypher의 HYD-01·구성 요소·계측 채널을 뽑은 교육용 부분집합이다. 시계열 실측값이 아니다. 예제_적재.cypher를 빈 랩 DB에 한 문장씩 적용한 뒤 조회한다. 이미 준비된 DB에는 식별자를 확인하고 기존 데이터와 섞지 않는다. 실습3~4의 직접 설계한 그래프는 다른 DB에 둔다.\n\n예제에는 1개 설비, 6개 구성 요소, 5개 센서, 5개 상태 변수와 16개 관계가 있다. 쿨러 센서는 TS1·CE, 주 펌프 센서는 PS1·FS1, 팬 센서는 VS1이다. 나머지 구성 요소는 이 부분집합에서 센서가 없다. 이것은 입력자료 정의이며 실행 검증 결과가 아니다.\n', '예제_그래프.json':json.dumps(graph,ensure_ascii=False,indent=2),'예제_적재.cypher':'\n'.join(loader)+'\n','조회_작성.cypher':'// 1. 쿨러의 센서 속성 조회\n\n// 2. 같은 패턴의 노드와 관계 반환\n\n// 3. HYD-01에서 물리량과 한계 조회\n\n// 4. 한계가 있는 행만 필터링\n\n// 5. 구성 요소별 서로 다른 센서 집계\n','조회_기록.md':blank+'| 구성 요소 ID | 센서 ID 목록 | 손으로 센 수 | 질의 결과 | 차이 원인 |\n|---|---|---|---|---|\n| | | | | |\n'},
 {'준비_안내.md':'# 기준 지식 탐색 준비\n\n강사가 제공한 HYD 포털의 읽기 화면을 연다. 실습1 예제 DB와 별개다. 기준 지식이 로드된 판본·주소는 수업 담당자가 제공한다. 편집·실행·명령 승인은 하지 않는다. 화면에 없는 관계는 추측하지 말고 미확인으로 기록한다. 대상 이름만 아니라 ID·클래스·관계 방향을 확인한다.\n','탐색_기록.md':blank+'| 출발 ID·종류 | 관계·방향 | 도착 ID·종류 | 속성·근거 | 확인 위치 |\n|---|---|---|---|---|\n| | | | | |\n'},
 {'준비_안내.md':'# 온톨로지 설계 입력\n\n자료 폴더의 현장 원자료에서 출발한다. 완성 스키마나 그래프는 제공하지 않는다. 결과/schema.json과 결과/graph.json을 직접 만든다. 예제 그래프의 공통 구성 모델과 달리 이번 질문은 실제 개별 설비의 센서를 구별하므로 구성 요소·센서 ID에 설비 코드를 포함한다. 예비품은 SKU로 공유한다.\n\n질문: 설비별 구성 요소의 센서는 무엇인가? 센서가 읽는 물리량·단위·한계는 무엇인가? 여러 설비가 공유하는 교체 부품은 무엇인가? 공급 조건은 별도 확장을 위한 원자료로 보존하며 이번 세 질문의 필수 산출물은 아니다.\n\ngraph.json은 nodes:[{labels:[종류],props:{id:고유값,...}}], rels:[{type:관계,a:출발id,b:도착id,props:{...}}]로 작성한다. HAS_COMPONENT, MONITORED_BY, OBSERVES, HAS_PART의 방향과 끝점은 스키마에 명시한다. 종류·필수 속성·형·단위·허용값·카디널리티를 정의한다.\n\nTS1 중복, 별칭, 숫자·단위가 섞인 값, 누락 단위는 현장 메모와 대조하고 처리 근거를 기록한다. 근거 없는 값을 채우지 않는다.\n','설계_검토표.md':blank+'| 질문 | 원자료·행 | 클래스·속성·관계 | 식별자 기준 | 제약 | 보완·미확인 |\n|---|---|---|---|---|---|\n| | | | | | |\n','결과/README.md':'이 폴더에 직접 작성한 schema.json과 graph.json을 저장한다. 완료 파일은 제공하지 않는다.\n'},
 {'준비_안내.md':'# 그래프 구현 준비\n\n실습3 결과/schema.json, graph.json을 이 폴더의 입력/에 복사한다. 강사가 제공한 별도 빈 랩 DB를 사용한다. 실습1 예제 DB나 HYD 기준 DB에 적재하지 않는다. 원본과 오류 검토용 사본을 구별하고 기존 DB 전체 삭제 명령을 사용하지 않는다.\n\nCopilot에 두 입력을 지정해 적재.cypher와 조회.cypher를 만들도록 요청한다. 레이블별 id 유일 제약, id 기준 MERGE, 값 갱신, 관계 끝점 MATCH를 확인한다. 생성문을 검토한 후 랩 DB에만 실행하는 수업 흐름이다. 이 제작에서는 실행하지 않았다.\n\n존재·형·단위·끝점·카디널리티와 원자료의 의미를 함께 확인한다. 제약 저장 성공만으로 의미가 맞다고 하지 않는다. 오류_검토용.json에서 관계의 물리량을 바꿔 발견·수정하는 활동은 파일 검토로 하고 잘못된 사본은 DB에 넣지 않는다.\n','입력/README.md':'실습3의 schema.json과 graph.json을 복사한다.\n','검증_기록.md':blank+'| 질문·검사 | 예상 근거 | 실제 조회 결과 | 수정과 재확인 |\n|---|---|---|---|\n| 설비별 구성 요소·센서 | | | |\n| 물리량·단위·한계 | | | |\n| 공유 부품 | | | |\n| 재적재 전·후 노드·관계 수 | | | |\n| 잘못된 물리량 관계 발견·복구 | | | |\n'},
 {'조건표_입력틀.csv':'rule_id,action,input,operator,value,unit,result,reason,source_section\n'}]

# 이론과 같은 원문 규칙을 제공한다. 임의의 온도·압력 제외 규칙을 만들지 않는다.
materials[4]['작업기준.md']='''# 조치 조건표 — 원문에서 옮기는 작업 기준

대상 후보는 팬 최대 운전(skill:fan-max, kind=control, 실행 코드=FAN_SET)이다. 자료의 예측값은 조치 후 예상값이며 현재 측정값과 다르다. 사례 표에는 이 후보의 실행 코드 하나만 적었다. 실제 시스템의 skill_code는 실행 코드 목록이며 이 후보는 FAN_SET 하나를 가진다. 실제 설비 조작·평가 함수 실행은 하지 않는다.

## 1. 원문과 규칙의 역할
HM-8_매뉴얼.md의 작업 순서·완료 조건·금지와 제한을 읽는다. 규칙_원문.txt는 저장소 it/neo4j/v2/instances.cypher에서 발췌한 구조화 규칙이다. 규칙에 기록된 HM-3.2·HM-7.5 등의 참조명은 시드 판본의 출처 식별자다. 첨부 HM-8 절 번호와 같다고 바꾸지 않는다. 문장과 구조화 결과를 대조하고, 판본 간 차이는 검토 기록에 남긴다.

## 2. 작성할 조건
- R1 / rule:ts1-warn: forecast_ts1 >= 55 ℃ → WARN. 팬 최대 운전·팬 감속에 적용. 예측 유온이 높아 경보 해제 실패 가능. 시드 출처 HM-7.5; 첨부 HM-8.6에서도 회복 기준 확인.
- R2 / rule:ps1-warn: forecast_ps1 < 165 bar → WARN. 조치 후 저압 경보 지속 가능. 시드 출처 HM-5.2. 첨부 HM-8에 압력 원문은 없으므로 압력 규칙의 근거는 규칙 발췌로 한정한다.
- R3 / rule:auto-mode: skill_kind == control AND plc_mode != REMOTE_AUTO → EXCLUDE. 원격 제어는 원격 자동에서만. 시드 출처 HM-3.2; 첨부 HM-8.5·8.8에도 같은 제한.
- R4 / rule:trip-reset-only: plc_state == TRIP AND skill_code != RESET → EXCLUDE. 트립 중 리셋 외 제어 불가. 시드 출처 HM-9.4. 팬 최대 운전은 리셋이 아니다.
- R5 / rule:fan-24h: fan100_hours > 24 h → PENALTY 20 (만원). 팬 최대 운전 계열에 적용. 시드 출처 HM-7.3; 첨부 HM-8.8은 24시간 초과 수명 손실을 감점한다. HM-8.5의 수행 시간 제한도 별도로 남긴다.

## 3. 결과 수집과 미확인 입력
맞는 경고·감점·제외를 모두 모은다. 제외가 있으면 후보에서 빼고, 없으면 후보를 유지하되 경고·감점과 수행 조건을 함께 남긴다. 후보 유지는 실행 허가가 아니다. 원문 SOP의 시간 제한·승인·수행 시점 재확인을 지운 채 감점만으로 작업을 허가하지 않는다.

이 수업의 검토 기록에서는 입력이 빠진 규칙을 미확인으로 표시한다. 알려진 제외 사유가 있으면 제외하면서 누락 항목도 남기고, 제외가 없더라도 필요한 입력이 빠졌으면 최종 허용 판단은 보류한다. 이는 검토 절차이며 HYD 함수의 누락값 처리를 실행해 검증한 결과가 아니다.

## 4. 현장 작업과 분리
핀 세척은 HM-8.7의 정지·LOCAL·잠금·현장 승인·세척·재가동 확인 절차를 따른다. 원격 조치가 제외돼도 현장 작업이 자동 허용되지 않는다. 이번 실습은 조건표와 판단 기록만 작성한다.
'''
seed=(C/'it/neo4j/v2/instances.cypher').read_text('utf8').splitlines();picked=[]
for i,line in enumerate(seed):
 if any("['rule:"+k+"'" in line for k in ['auto-mode','ts1-warn','ps1-warn','fan-24h','trip-reset-only']):picked.extend([f'// instances.cypher:{i+1}',line,seed[i+1],''])
materials[4]['규칙_원문.txt']='\n'.join(picked)
materials[4]['HM-8_매뉴얼.md']=(C/'산출물/실습/통합반_오프라인/03회차_실습1_결정표/코드/문서/HM-8_쿨러팬_정비매뉴얼.md').read_text('utf8')
materials[4]['사례_입력.csv']='case,forecast_ts1_C,forecast_ps1_bar,plc_mode,plc_state,fan100_hours,skill_kind,skill_code\nA,54.9,165,REMOTE_AUTO,RUNNING,24,control,FAN_SET\nB,55,165,REMOTE_AUTO,RUNNING,24,control,FAN_SET\nC,55.1,165,REMOTE_AUTO,RUNNING,24.1,control,FAN_SET\nD,54,164.9,REMOTE_AUTO,RUNNING,23.9,control,FAN_SET\nE,54,165.1,REMOTE_AUTO,RUNNING,24,control,FAN_SET\nF,56,160,REMOTE_MANUAL,TRIP,30,control,FAN_SET\nG,54,170,REMOTE_AUTO,TRIP,0,control,FAN_SET\nH,,170,REMOTE_AUTO,RUNNING,0,control,FAN_SET\nI,,160,REMOTE_MANUAL,RUNNING,0,control,FAN_SET\n'
materials[4]['판단기록_입력틀.md']=blank+'| 사례 | 일치 규칙 | 경고 | 감점 | 제외 사유 | 후보 유지·제외·보류 | 미확인 | 원문 근거 |\n|---|---|---|---|---|---|---|---|\n| | | | | | | | |\n'
materials[2]['준비_안내.md']=materials[2]['준비_안내.md'].replace('HAS_PART','USES_PART')
materials[2]['결과/요구사항.md']='# 질문과 모델 범위\n\n1. 설비별 구성 요소의 센서는?\n2. 물리량·단위·한계는?\n3. 공유하는 교체 부품은?\n\n## 식별자와 범위 선택\n\n## 원자료 근거와 예상 답\n'
materials[2]['결과/자료_검토.md']=materials[2]['설계_검토표.md']
raw=C/'산출물/실습/통합반_오프라인/02회차_실습1_온톨로지_스키마/코드/자료'
for f in raw.iterdir():
 if f.is_file():materials[2]['자료/'+f.name]=f.read_text('utf-8-sig')
pdfmetrics.registerFont(TTFont('Malgun','C:/Windows/Fonts/malgun.ttf'));pdfmetrics.registerFont(TTFont('MalgunBold','C:/Windows/Fonts/malgunbd.ttf'))
body=ParagraphStyle('body',fontName='Malgun',fontSize=11,leading=18.5,spaceAfter=8,wordWrap='CJK',splitLongWords=True,allowWidows=0,allowOrphans=0)
head=ParagraphStyle('head',parent=body,fontName='MalgunBold',fontSize=12,leading=19,spaceBefore=17,spaceAfter=7,keepWithNext=True,textColor=colors.HexColor('#1f4e79'))
title=ParagraphStyle('title',parent=head,fontSize=16,leading=25,spaceBefore=0)
checks=[]
def pdf(md,out):
 story=[];expected=[]
 for para in md.strip().split('\n\n'):
  para=para.strip()
  if not para:continue
  text=re.sub(r'^#{1,3} ','',para);expected.append(text);style=title if para.startswith('# ') else head if para.startswith(('## ','### ')) else body
  story.append(Paragraph(html.escape(text).replace('\n','<br/>'),style))
 def footer(c,doc):c.setFont('Malgun',8);c.setFillColor(colors.HexColor('#777777'));c.drawRightString(A4[0]-50,28,f'{doc.page}')
 out.parent.mkdir(parents=True,exist_ok=True);SimpleDocTemplate(str(out),pagesize=A4,leftMargin=51,rightMargin=51,topMargin=57,bottomMargin=51,title=out.stem,author='').build(story,onFirstPage=footer,onLaterPages=footer)
 pages=[]
 for i,p in enumerate(PdfReader(out).pages,1):
  lines=p.extract_text().splitlines()
  if lines and lines[0].strip()==str(i):lines=lines[1:]
  pages.append('\n'.join(lines))
 norm=lambda s:re.sub(r'\s+','',s)
 assert norm('\n'.join(expected))==norm('\n'.join(pages)),('PDF text mismatch',out)
 checks.append(dict(file=str(out),pages=len(pages),exact_text_match=True))
 render(out,EV/'renders'/('-'.join(out.parts[-3:]).replace('.pdf','')))
def render(path,folder):
 folder.mkdir(parents=True,exist_ok=True);doc=pdfium.PdfDocument(path);thumbs=[]
 for i in range(len(doc)):
  im=doc[i].render(scale=1).to_pil().convert('RGB');im.save(folder/f'{i+1:03}.png');im.thumbnail((360,500));thumbs.append(im)
 for start in range(0,len(thumbs),12):
  sheet=Image.new('RGB',(1480,1580),'#dce1e6');d=ImageDraw.Draw(sheet)
  for j,im in enumerate(thumbs[start:start+12]):
   x=10+(j%4)*370;y=25+(j//4)*520;sheet.paste(im,(x,y));d.text((x,y-17),str(start+j+1),fill='black')
  sheet.save(folder/f'contact-{start//12+1:02}.png')
 return len(doc)
def merge(root,folder,practical):
 tool=root/('만들기/tools/deck/실전분할대본합치기.py' if practical else '만들기/tools/deck/분할대본합치기.py')
 spec=importlib.util.spec_from_file_location('merge',tool);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.build(folder)
merge(C,I,False);merge(D,P,True)
css='body{font:17px/1.8 "Malgun Gothic",sans-serif;max-width:960px;margin:40px auto;padding:0 24px;color:#22303e}h1{font-size:28px}h2{margin-top:38px;font-size:23px}aside{background:#f0f4f7;padding:14px;white-space:pre-wrap}p{white-space:pre-wrap}'
for root,folder,course,num in [(C,I,'통합반',4),(D,P,'실전반',5)]:
 scripts=sorted(folder.glob('*_실습_*.md'));assert len(scripts)==num
 combined=[]
 for idx,f in enumerate(scripts,1):
  text=f.read_text('utf8');reading=speech(text);write(folder/'낭독본'/f.name,reading);combined.append(reading)
  short=['관계조회','지식지도탐색','온톨로지설계','그래프구현과검증','조치조건표'][idx-1];lab=root/f'산출물/실습/{course}_온라인/02일차_실습{idx}_{short}';lab.mkdir(parents=True,exist_ok=True)
  write(lab/'강사대본.md',text)
  for name,data in materials[idx-1].items():write(lab/name,data)
  segments=[]
  for para in text.strip().split('\n\n'):
   if para.startswith('# '):tag='h1';para=para[2:]
   elif para.startswith('## '):tag='h2';para=para[3:]
   elif para.startswith('>'):tag='aside';para=para.lstrip('> ')
   else:tag='p'
   segments.append(f'<{tag}>'+html.escape(para)+f'</{tag}>')
  write(lab/'안내.html','<!doctype html><html lang="ko"><meta charset="utf-8"><title>'+html.escape(short)+'</title><style>'+css+'</style>'+''.join(segments)+'</html>')
  pdf(reading,lab/'강사대본.pdf')
  # ZIP 내부 상대 경로·바이트를 즉시 대조.
  archive=lab.with_suffix('.zip');files=sorted(f for f in lab.rglob('*') if f.is_file())
  with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
   for f in files:z.write(f,f.relative_to(lab).as_posix())
  with zipfile.ZipFile(archive) as z:
   assert z.testzip() is None
   assert sorted(z.namelist())==sorted(f.relative_to(lab).as_posix() for f in files)
   for f in files:assert z.read(f.relative_to(lab).as_posix())==f.read_bytes()
 readingfile=folder.parent/'낭독본'/f'{course}_02일차_낭독본.md'
 pdf(readingfile.read_text('utf8'),folder.parent/f'{course}_02일차_대본.pdf')
 allpractice='\n\n'.join(combined);write(folder/'실습_낭독합본.md',allpractice);pdf(allpractice,folder/f'{course}_02일차_실습대본.pdf')
write(EV/'pdf-check.json',json.dumps(checks,ensure_ascii=False,indent=2))
print('PDF text verified',len(checks),'files; 9 ZIPs verified; lab execution: none')
