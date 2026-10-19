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
D=Path(__file__).resolve().parents[4];C=Path(sys.argv[1]);EV=D/'.evidence/session07';I=C/'산출물/교재/대본/통합반_온라인/07회차';P=D/'산출물/교재/대본/실전반_온라인/07회차'
pdfmetrics.registerFont(TTFont('Malgun','C:/Windows/Fonts/malgun.ttf'));pdfmetrics.registerFont(TTFont('MalgunBold','C:/Windows/Fonts/malgunbd.ttf'))
body=ParagraphStyle('body',fontName='Malgun',fontSize=11,leading=18.5,spaceAfter=8,wordWrap='CJK',splitLongWords=True,allowWidows=0,allowOrphans=0)
head=ParagraphStyle('head',parent=body,fontName='MalgunBold',fontSize=12,leading=19,spaceBefore=17,spaceAfter=7,keepWithNext=True,textColor=colors.HexColor('#1f4e79'))
title=ParagraphStyle('title',parent=head,fontSize=16,leading=25,spaceBefore=0)
checks=[]
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
 notes=theory_notes(I);deck=C/'만들기/decks/integrated/day07/통합반_07일차.md'
 blocks=re.split(r'(?=^## SLIDE )',deck.read_text('utf8'),flags=re.M)
 for n in range(1,61):
  blocks[n]=re.sub(r'^- 노트:.*\n?','',blocks[n],flags=re.M).replace('### 화면 구성','- 노트: '+notes[n]+'\n### 화면 구성',1)
 write(deck,''.join(blocks))
 path=C/'산출물/교재/PPTX/통합반_온라인/통합반_07일차.pptx';before=path.read_bytes();updates={};ns={'a':'http://schemas.openxmlformats.org/drawingml/2006/main','p':'http://schemas.openxmlformats.org/presentationml/2006/main'};REL='http://schemas.openxmlformats.org/package/2006/relationships';OFF='http://schemas.openxmlformats.org/officeDocument/2006/relationships/';CT='http://schemas.openxmlformats.org/package/2006/content-types'
 serial=lambda x:E.tostring(x,xml_declaration=True,encoding='UTF-8',standalone=True)
 with zipfile.ZipFile(io.BytesIO(before)) as z:
  ct=E.fromstring(z.read('[Content_Types].xml'));nn=max(int(re.search(r'notesSlide(\d+)',n)[1]) for n in z.namelist() if re.fullmatch(r'ppt/notesSlides/notesSlide\d+\.xml',n))+1
  for n in range(1,61):
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
  im=doc[i].render(scale=1).to_pil().convert('RGB');im.save(folder/f'{i+1:03}.png');im.thumbnail((580,310));thumbs.append(im)
 for start in range(0,len(thumbs),9):
  sheet=Image.new('RGB',(1800,1050),'#dce1e6');d=ImageDraw.Draw(sheet)
  for j,im in enumerate(thumbs[start:start+9]):
   x=10+(j%3)*600;y=25+(j//3)*350;sheet.paste(im,(x,y));d.text((x,y-17),str(start+j+1),fill='black')
  sheet.save(folder/f'contact-{start//9+1:02}.png')
 return len(doc)

def merge(root,folder,practical):
 tool=root/('만들기/tools/deck/실전분할대본합치기.py' if practical else '만들기/tools/deck/분할대본합치기.py')
 spec=importlib.util.spec_from_file_location('merge',tool);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.build(folder)
