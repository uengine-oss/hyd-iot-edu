"""통합반 1회차 문서만 재생성. 시스템·브라우저·학생 코드는 실행하지 않는다.
분할대본합치기.py를 먼저 실행한다. 원본: 01회차 분할 MD, day01 덱 MD.
"""
from pathlib import Path
import re,json,hashlib,zipfile,io,copy,html
from lxml import etree as E
from reportlab.platypus import SimpleDocTemplate,Paragraph,PageBreak
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pypdf import PdfReader
import pypdfium2 as pdfium
from PIL import Image,ImageDraw

R=Path(__file__).resolve().parents[3]
F=R/'산출물/교재/대본/통합반_온라인/01회차'
B=F.parent
EV=R/'.evidence/integrated01-review';EV.mkdir(parents=True,exist_ok=True)
deck=R/'만들기/decks/integrated/day01/통합반_01일차.md'
config=json.loads((F/'구성.json').read_text('utf8'))
theory=[u for u in config['units'] if u['kind']=='pptx']
practice=[u for u in config['units'] if u['kind']=='practice']
blocks=re.split(r'(?=^## SLIDE )',deck.read_text('utf8'),flags=re.M)
assert len(blocks)==79
notes={}
for u in theory:
    for block in re.split(r'(?=^## \[SLIDE )',(F/u['file']).read_text('utf8'),flags=re.M)[1:]:
        m=re.match(r'## \[SLIDE (\d+)(?:~(\d+))?\]',block)
        speech=' '.join(s.strip().replace('**','') for s in block.splitlines()[1:] if s.strip() and not s.startswith(('>','#','---')))
        for n in range(int(m[1]),int(m[2] or m[1])+1):
            notes[n]=speech if n==int(m[1]) else f'{m[1]}~{m[2]}장 통합 발화는 {m[1]}장 발표자 노트를 따른다.'
for n in range(1,79):
    if re.search(r'^- 노트:',blocks[n],re.M):blocks[n]=re.sub(r'^- 노트:.*$',lambda m:'- 노트: '+notes[n],blocks[n],flags=re.M)
    else:blocks[n]=blocks[n].replace('### 화면 구성','- 노트: '+notes[n]+'\n\n### 화면 구성',1)
deck.write_text(''.join(blocks),encoding='utf8')

# ZIP의 바뀐 XML만 교체하여 그림·배치·테마를 보존한다.
path=R/'산출물/교재/PPTX/통합반_온라인/통합반_01일차.pptx'
before=path.read_bytes();out=io.BytesIO();changed=[]
NS={'a':'http://schemas.openxmlformats.org/drawingml/2006/main','p':'http://schemas.openxmlformats.org/presentationml/2006/main'}
REL='http://schemas.openxmlformats.org/package/2006/relationships'
OFF='http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
CT='http://schemas.openxmlformats.org/package/2006/content-types'
serial=lambda root:E.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True)
updates={};note_to_slide={};slide_to_note={}
with zipfile.ZipFile(io.BytesIO(before)) as z:
    content=E.fromstring(z.read('[Content_Types].xml'))
    nextnote=max(int(re.search(r'notesSlide(\d+)',n)[1]) for n in z.namelist() if re.fullmatch(r'ppt/notesSlides/notesSlide\d+\.xml',n))+1
    for n in range(1,79):
        relpath=f'ppt/slides/_rels/slide{n}.xml.rels';rels=E.fromstring(z.read(relpath))
        found=[r for r in rels if r.get('Type')==OFF+'notesSlide']
        if found:nn=int(re.search(r'notesSlide(\d+)',found[0].get('Target'))[1])
        else:
            nn=nextnote;nextnote+=1
            rid=max(int(r.get('Id')[3:]) for r in rels)+1
            E.SubElement(rels,'{'+REL+'}Relationship',Id=f'rId{rid}',Type=OFF+'notesSlide',Target=f'../notesSlides/notesSlide{nn}.xml')
            updates[relpath]=serial(rels)
            updates[f'ppt/notesSlides/notesSlide{nn}.xml']=z.read('ppt/notesSlides/notesSlide1.xml')
            nr=E.fromstring(z.read('ppt/notesSlides/_rels/notesSlide1.xml.rels'))
            for rel in nr:
                if rel.get('Type')==OFF+'slide':rel.set('Target',f'../slides/slide{n}.xml')
            updates[f'ppt/notesSlides/_rels/notesSlide{nn}.xml.rels']=serial(nr)
            E.SubElement(content,'{'+CT+'}Override',PartName=f'/ppt/notesSlides/notesSlide{nn}.xml',ContentType='application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml')
        note_to_slide[nn]=n;slide_to_note[n]=nn
    if updates:updates['[Content_Types].xml']=serial(content)
replacements={43:[('파일 편집과 터미널 작업을 하는 도구이다','파일을 열고 편집하며'),('파일 편집과 실행을 한곳에서 진행한다','터미널에서 명령을 실행한다'),('HYD 서비스와 랩 코드를 작성하는 프로그래밍 언어이다','HYD의 자체 서비스와 일부 랩에 쓰는 언어이다')],45:[('쿨러 사건의 처리 기록','교재 예시의 처리 기록')],47:[('경보는 조건을 벗어났다는 사실만 알리므로, 조치를 정하려면','교재에 보관한 사건 기록이다. 경보 뒤'),('을 먼저 가려야 한다.','을 가려 조치를 정하고, 조치 뒤 변화를 확인한다.')]}
with zipfile.ZipFile(io.BytesIO(before)) as z,zipfile.ZipFile(out,'w') as dst:
    entries=z.infolist()+[zipfile.ZipInfo(n) for n in updates if n not in z.namelist()]
    for item in entries:
        original=z.read(item.filename) if item.filename in z.namelist() else b''
        data=updates.get(item.filename,original)
        m=re.fullmatch(r'ppt/notesSlides/notesSlide(\d+)\.xml',item.filename)
        sm=re.fullmatch(r'ppt/slides/slide(\d+)\.xml',item.filename)
        if m:
            n=note_to_slide[int(m[1])];root=E.fromstring(data)
            for sp in root.findall('.//p:sp',NS):
                ph=sp.find('.//p:ph',NS)
                if ph is not None and ph.get('type')=='body':
                    tx=sp.find('p:txBody',NS); assert tx is not None
                    for para in list(tx.findall('a:p',NS)):tx.remove(para)
                    para=E.SubElement(tx,'{'+NS['a']+'}p');run=E.SubElement(para,'{'+NS['a']+'}r');E.SubElement(run,'{'+NS['a']+'}t').text=notes[n]
            data=E.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True)
        elif sm and int(sm[1]) in replacements:
            root=E.fromstring(data)
            for old,new in replacements[int(sm[1])]:
                texts=root.findall('.//a:t',NS)
                hits=[t for t in texts if old in (t.text or '')]
                if hits:
                    assert len(hits)==1,(sm[1],old)
                    hits[0].text=hits[0].text.replace(old,new)
                else:assert any(new in (t.text or '') for t in texts),(sm[1],old,'not found')
            data=E.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True)
        if original!=data:changed.append(item.filename)
        dst.writestr(item,data)
with zipfile.ZipFile(io.BytesIO(out.getvalue())) as z:
    assert z.testzip() is None
    for n in range(1,79):
        root=E.fromstring(z.read(f'ppt/notesSlides/notesSlide{slide_to_note[n]}.xml'))
        assert notes[n] in ''.join(root.xpath('//a:t/text()',namespaces=NS))
path.write_bytes(out.getvalue())
(EV/'pptx-check.json').write_text(json.dumps({'slides':78,'notes_match':True,'changed_parts':changed,'all_other_zip_parts_preserved':True},ensure_ascii=False,indent=2),encoding='utf8')

# 실습 자료의 빈칸은 입력용이다. 실측값과 완성 그림을 만들지 않는다.
L=R/'산출물/실습/통합반_온라인'
names=['01일차_실습1_학습노트','01일차_실습2_실행환경','01일차_실습3_전체과정관찰','01일차_실습4_관계그림']
legacy=['day01-1-notion','day01-2-run-system','day01-3-full-flow','day01-4-draw-relations']
templates=[
{'학습노트_입력틀.md':'# 학습노트 입력틀\n\n## 개념 정리\n- 제목:\n- 분야:\n- 이해도:\n- 작성일:\n- 내 설명:\n- 참고 자료와 해당 부분:\n- 비교 후 고친 내용:\n- 다음에 확인할 것:\n\n## 참고 자료\n- 문서·판본·장:\n- 첨부 또는 링크:\n\n## 실습 결과\n- 한 작업:\n- 실제 확인 결과:\n- 관련 개념 링크:\n- 남은 점:\n'},
{'환경_확인표.md':'# 환경 확인표\n\n| 역할·서비스 | 실행 상태·종료 코드 | 접속·응답 확인 | 확인 시각 | 남은 문제 |\n|---|---|---|---|---|\n| 업무 저장소 | | | | |\n| 상시 서비스 | | | | |\n| 초기화 작업 | | | | |\n| 프로세스 | | | | |\n| 호스트 워커 한 개 | | | | |\n| 포털·계측 갱신 | | | | |\n\n확인한 항목만 채운다. 준비됨·Up만으로 전체 정상이라고 결론 내리지 않는다.\n',
'환경_준비_안내.md':'''# 수업용 실행 환경 준비

이 ZIP은 확인 자료이며 HYD 시스템 전체 배포본이 아니다. 강사가 제공한 HYD 프로젝트를 별도 창에서 연다. 프로젝트 루트에 compose.yaml, it/supabase, scripts/run_worker_host.sh가 있는지 확인한다.

이 대본은 Windows Git Bash와 호스트 워커 한 개를 사용하는 구성을 기준으로 썼다. 시작 전 배포 담당자가 수업용 데이터·프로세스·계정·인증을 마련해야 한다. 기본 structure 시드는 진단 지식이 비어 있을 수 있으므로 쿨러 원인·증거·조치 지식과 처리 흐름이 준비됐는지 확인한다. 빈 구조판으로 사건 성공을 약속하지 않는다. 기존 볼륨을 지우거나 시드 판만 바꾸어 해결하지 않는다.

프로젝트의 문서/시스템/참조/RUNBOOK.md와 compose.yaml을 대조한다. PROCESS_MODE=instance, ENTERPRISE_BACKEND=supabase, AGENT_BRIDGE=off, WORKER_URL=http://host.docker.internal:8097, TIME_SCALE=20의 수업 설정을 확인한다. 인증값은 별도 비공개로 준비한다. 키를 확인표·화면·질문에 붙이지 않는다.

Compose에는 ot, backbone, detect, knowledge, agent, enterprise, process, cliagents 프로필을 함께 지정한다. 호스트 워커를 쓰므로 agent-worker 컨테이너의 scale은 0으로 둔다. 일부 프로필만 지정하여 의존 서비스가 빠지지 않도록 한다. 이 명령 구성은 문서·compose.yaml 대조 결과이며 이번에 실행한 결과가 아니다.

호스트 워커가 이미 동작하면 추가로 실행하지 않는다. Docker Desktop 엔진, Supabase, Compose 서비스, 호스트 워커 순서로 확인한다. 서비스 이름·초기화 종료 코드·API 응답·포털 계측 갱신을 함께 본다. 포털의 고정 서비스 개수나 특정 정상값만으로 성공을 판정하지 않는다.

기본 주소는 포털 http://127.0.0.1:8088, 프로세스 상태 http://127.0.0.1:8080/healthz, 호스트 워커 http://127.0.0.1:8097/health 이다. 배포 주소가 다르면 제공된 값을 쓴다. 이번 문서 작업에서는 접속하지 않았다.
'''},
{'근거_연결표.md':'# 근거 연결표\n\n관찰한 사건 번호:\n\n| 출발 기록 ID | 참조 항목 이름 | 참조 값 | 도착 기록 ID | 확인 위치·시각 | 판정 |\n|---|---|---|---|---|---|\n| 작업지시: | | | 판단: | | |\n| 판단: | | | 사건: | | |\n| 사건: | | | 경보: | | |\n\n참조 값과 도착 기록의 식별자를 실제로 대조한다. 원기록에서 확인할 수 없으면 미확인으로 둔다.\n',
'관찰_기록.md':'# 쿨러 사건 관찰 기록\n\n- 설비·사건 ID·관찰 시각:\n- 경보 당시 값과 시각:\n- 원인 후보·판별 기준:\n- 판별에 쓴 태그·집계 구간·실제 값:\n- 추천안·대안과 선택 이유:\n- 승인 전 명령 기록 유무:\n- 승인 기록·명령 ID:\n- 같은 명령에 대한 ACK:\n- 재관측 구간·유온·경보 상태·완화 판정:\n- 핀 세척 작업지시 ID·현재 상태:\n- 확인하지 못한 항목:\n\n교재의 과거 예시와 지금 관찰한 값을 섞지 않는다. 작업지시 등록은 정비 완료와 다르다.\n'},
{'대상_목록.md':'# 관계 그림의 대상\n\nHYD-01 유압 파워팩, 오일 쿨러, 유온 센서, 유온 상승, 쿨러 냉각 성능 상실, 쿨러 핀 오염, 팬 구동 불량, 팬 최대 운전, 쿨러 핀 세척, 팬 점검.\n\n증거: 냉각 효율 CE의 최근 30초 평균, 팬 진동 VS1의 최근 2분 평균.\n\n종류·이름을 나누어 표시하고 매뉴얼에 맞춰 관계를 작성한다. 같은 증거를 쓰더라도 원인별 조건을 구별한다. 조치 후보에는 적용 원인과 근거를 표시한다.\n',
'관계_검토표.md':'# 관계 검토표\n\n| 출발 대상·종류 | 관계 이름 | 도착 대상·종류 | 문장으로 읽기 | 원문 근거·조건 | 수정할 점 |\n|---|---|---|---|---|---|\n| | | | | | |\n\n- 핀 오염의 두 증거와 근본 조치:\n- 팬 구동 불량의 증거와 점검:\n- 공통 고장 유형:\n- 원인별 적용 조건:\n- JSON 재열기 확인:\n'}]
templates[3]['매뉴얼_발췌.md']=(R/'만들기/labs/online/day01-4-draw-relations/매뉴얼_발췌_원본.md').read_text('utf8')
css='body{font:17px/1.8 "Malgun Gothic",sans-serif;max-width:960px;margin:40px auto;padding:0 24px;color:#22303e}h1{font-size:28px}h2{margin-top:38px;font-size:23px}aside{background:#f0f4f7;padding:14px;margin:12px 0;font-size:14px;white-space:pre-wrap}p{white-space:pre-wrap}.screen{border:1px dashed #8294a5;padding:20px;color:#526578}'
def render_html(title,segments):
    return '<!doctype html><html lang="ko"><meta charset="utf-8"><title>'+html.escape(title)+'</title><style>'+css+'</style><h1>'+html.escape(title)+'</h1>'+''.join(segments)+'</html>'
for i,u in enumerate(practice):
    folder=L/names[i];folder.mkdir(parents=True,exist_ok=True)
    text=(F/u['file']).read_text('utf8')
    for name,t in templates[i].items():(folder/name).write_text(t,encoding='utf8')
    nums=[[5,6,7,8,9,11],[13,40,41,43],[30,37,39,45],[49,50,63,64,65,67,68,71]][i]
    excerpt='# 통합반 1회차 교재 화면 발췌\n\n현재 덱 원고의 해당 장이다. 그림은 PPTX 같은 장을 참조한다. 실행 결과가 아니다.\n\n'
    for n in nums:
        screen=blocks[n].split('### 화면 구성')[0]
        screen=re.sub(r'^- 노트:.*$','',screen,flags=re.M)
        excerpt+=screen+'\n'
    (folder/'참고_교재_발췌.md').write_text(excerpt,encoding='utf8')
    sections=[];rs=[];screens=[]
    for j,part in enumerate(re.split(r'(?=^## )',text,flags=re.M)[1:],1):
        title,body=part.split('\n',1);title=title[3:];cues=[];speech=[]
        sections.append('<h2>'+html.escape(title)+'</h2>')
        for para in body.strip().split('\n\n'):
            if para.startswith('>'):
                cues.append(re.sub(r'^> ?','',para,flags=re.M));sections.append('<aside>'+html.escape(cues[-1])+'</aside>')
            elif para.strip():speech.append(para);sections.append('<p>'+html.escape(para)+'</p>')
        sections.append('<div class="screen">화면 빈자리: '+html.escape(title)+' — 해당 작업과 확인 결과. 아직 캡처하지 않음.</div>')
        screens.append(f'{j}. {title}: 해당 조작과 결과가 보이는 화면. 미촬영.')
        rs.append({'제목':title,'하는 것':cues,'대본':speech})
    (folder/'가이드.html').write_text(render_html(names[i],['<p>강사 진행용. 조작·입력·분기는 비낭독이며 실제 결과를 확인할 때만 확인 발화를 사용한다. 실습 실행·캡처 미검증.</p>']+sections),encoding='utf8')
    (folder/'채울_화면.md').write_text('# 필요한 화면 — 빈자리\n\n'+'\n'.join(screens)+'\n',encoding='utf8')
    old=R/'만들기/labs/online'/legacy[i]
    d={'회차':f'통합반 온라인 1회차 · 실습 {i+1}','제목':text.splitlines()[0][2:],'한 줄':'자료 다운로드부터 결과물 저장·확인까지 강사가 직접 진행한다.','수정 원본':str((F/u['file']).relative_to(R)),'촬영 전에':['분할 MD가 원본이다. 이 JSON과 HTML을 직접 수정하지 않는다.','실습·캡처 미검증. 분량은 내용에 따라 정하고 고정 시간에 맞추지 않는다.'],'구간':rs}
    (old/'runsheet.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    (old/'runsheet.html').write_text(render_html(d['제목'],sections),encoding='utf8')
    (old/'README.md').write_text('# 통합반 1회차 실습 진행표\n\n수정 원본: `'+d['수정 원본']+'`. 재생성: `python 만들기/labs/online/day01-review-build.py`. 이전 시간 배정·script_polish.json은 이 생성 경로에서 사용하지 않는다. 새 발화는 분할 원본에서만 수정한다.\n',encoding='utf8')
    dl=L/'다운로드';dl.mkdir(exist_ok=True)
    with zipfile.ZipFile(dl/(names[i]+'.zip'),'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(folder.iterdir()):
            if p.is_file():z.write(p,names[i]+'/'+p.name)
    with zipfile.ZipFile(dl/(names[i]+'.zip')) as z:
        assert z.testzip() is None
        for p in folder.iterdir():
            if p.is_file():assert z.read(names[i]+'/'+p.name)==p.read_bytes()
(L/'01회차_실습_안내.md').write_text('# 통합반 1회차 실습 안내\n\n각 ZIP을 내려받아 압축을 풀고 VS Code로 폴더를 연다. 가이드의 조작과 확인을 따라 결과물을 만든다. 실제 실습·화면 캡처는 아직 하지 않았다.\n\n'+'\n'.join(f'- [실습 {i+1}: {name}](다운로드/{name}.zip) · [가이드]({name}/가이드.html)' for i,name in enumerate(names))+'\n\n실습 2는 별도 HYD 프로젝트와 수업용 설정·지식·흐름·인증이 필요하다. ZIP에 시스템 전체나 완료된 관측 기록은 들어 있지 않다. 실습 3은 포털에서 새 사건을 관찰해 빈 연결표를 채운다. 참조가 확인되지 않으면 미확인으로 남긴다. 실습 4는 매뉴얼의 판별 기준과 점검 절을 구별한다.\n',encoding='utf8')

# 분할 원본에서 생성된 낭독본 / 조작 표시를 포함한 실습 대본의 PDF.
pdfmetrics.registerFont(TTFont('Malgun','C:/Windows/Fonts/malgun.ttf'))
pdfmetrics.registerFont(TTFont('MalgunBold','C:/Windows/Fonts/malgunbd.ttf'))
body=ParagraphStyle('body',fontName='Malgun',fontSize=11,leading=18.5,wordWrap='CJK',spaceAfter=8,allowWidows=0,allowOrphans=0)
heading=ParagraphStyle('heading',parent=body,fontName='MalgunBold',fontSize=12,leading=19,spaceBefore=12,keepWithNext=True)
title=ParagraphStyle('title',parent=heading,fontSize=16,leading=24)
cue=ParagraphStyle('cue',parent=body,fontSize=9,leading=14,textColor=colors.HexColor('#526578'),backColor=colors.HexColor('#f0f4f7'),borderPadding=4)
def build_pdf(texts,target,tag):
    story=[];expected=[]
    for i,text in enumerate(texts):
        if i:story.append(PageBreak())
        for chunk in text.strip().split('\n\n'):
            chunk=chunk.strip()
            if not chunk or chunk=='---':continue
            if chunk.startswith('# '):content=chunk[2:];style=title
            elif chunk.startswith('## '):content=chunk[3:];style=heading
            elif chunk.startswith('>'):content=re.sub(r'^> ?','',chunk,flags=re.M);style=cue
            else:content=chunk;style=body
            content=content.replace('**','').replace('`','');expected.append(content)
            story.append(Paragraph(html.escape(content).replace('\n','<br/>'),style))
    def footer(c,d):c.setFont('Malgun',8);c.drawRightString(A4[0]-51,28,str(d.page))
    target.parent.mkdir(parents=True,exist_ok=True)
    SimpleDocTemplate(str(target),pagesize=A4,leftMargin=51,rightMargin=51,topMargin=56,bottomMargin=51,title=target.stem).build(story,onFirstPage=footer,onLaterPages=footer)
    actual=[]
    for i,p in enumerate(PdfReader(target).pages,1):
        lines=p.extract_text().splitlines()
        if lines and lines[0].strip()==str(i):lines=lines[1:]
        if lines and lines[-1].strip()==str(i):lines=lines[:-1]
        actual.append('\n'.join(lines))
    norm=lambda t:re.sub(r'\s+','',t)
    assert norm('\n'.join(expected))==norm('\n'.join(actual)),tag+' text mismatch'
    render=EV/tag;render.mkdir(exist_ok=True);pdf=pdfium.PdfDocument(target);thumbs=[]
    for i in range(len(pdf)):
        im=pdf[i].render(scale=1.3).to_pil().convert('RGB');im.save(render/f'page-{i+1:02}.png');im.thumbnail((360,510));thumbs.append(im)
    for start in range(0,len(thumbs),9):
        sheet=Image.new('RGB',(1120,1610),'#d8dce1');draw=ImageDraw.Draw(sheet)
        for k,im in enumerate(thumbs[start:start+9]):
            x=10+k%3*370;y=25+k//3*530;sheet.paste(im,(x,y));draw.text((x,y-17),str(start+k+1),fill='black')
        sheet.save(render/f'contact-{start//9+1}.png')
    return {'pages':len(pdf),'exact_text_match':True,'file':str(target)}
results=[build_pdf([(B/'낭독본/통합반_01일차_낭독본.md').read_text('utf8')],B/'PDF/통합반_01일차_대본.pdf','theory-pdf'),build_pdf([(F/u['file']).read_text('utf8') for u in practice],B/'PDF/통합반_01일차_실습대본.pdf','practice-pdf')]
(EV/'pdf-check.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(results,ensure_ascii=False));print('PPTX notes, 4 guides, 4 ZIPs, 2 PDFs generated; no practice execution')

config['pptx_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
(F/'구성.json').write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
