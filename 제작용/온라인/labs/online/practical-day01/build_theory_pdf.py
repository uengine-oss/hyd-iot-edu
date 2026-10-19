from pathlib import Path
from html import escape
import re,json
from reportlab.platypus import SimpleDocTemplate,Paragraph,HRFlowable
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pypdf import PdfReader
import pypdfium2 as pdfium
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[4]
ev=ROOT/'.evidence/practical01-close';ev.mkdir(parents=True,exist_ok=True)
base=ROOT/'산출물/교재/대본/실전반_온라인'
src=base/'낭독본/실전반_01일차_낭독본.md';out=base/'실전반_01일차_대본.pdf'
pdfmetrics.registerFont(TTFont('Malgun','C:/Windows/Fonts/malgun.ttf'));pdfmetrics.registerFont(TTFont('MalgunBold','C:/Windows/Fonts/malgunbd.ttf'))
body=ParagraphStyle('body',fontName='Malgun',fontSize=11,leading=18.5,spaceAfter=3*mm,wordWrap='CJK',splitLongWords=True,allowWidows=0,allowOrphans=0)
heading=ParagraphStyle('heading',parent=body,fontName='MalgunBold',fontSize=12,leading=18,textColor=colors.HexColor('#1f4e79'),spaceBefore=7*mm,spaceAfter=2*mm,keepWithNext=True)
title=ParagraphStyle('title',parent=heading,fontSize=16,leading=24,textColor=colors.HexColor('#1a1a1a'),spaceBefore=0,spaceAfter=6*mm)
text=src.read_text(encoding='utf8');story=[]
for para in text.strip().split('\n\n'):
 para=para.strip()
 if not para:continue
 if para.startswith('# '):
  rule=HRFlowable(width='100%',thickness=1.2,color=colors.HexColor('#1a1a1a'),spaceAfter=3*mm);rule.keepWithNext=True
  story += [Paragraph(escape(para[2:]),title),rule]
 elif para.startswith('## '):story.append(Paragraph(escape(para[3:]),heading))
 else:story.append(Paragraph(escape(para),body))
def footer(c,doc):
 c.setFont('Malgun',8);c.setFillColor(colors.HexColor('#777777'));c.drawRightString(A4[0]-18*mm,10*mm,str(doc.page))
SimpleDocTemplate(str(out),pagesize=A4,leftMargin=18*mm,rightMargin=18*mm,topMargin=20*mm,bottomMargin=18*mm,title='실전반 1회차 - 낭독 대본',author='').build(story,onFirstPage=footer,onLaterPages=footer)
pages=[p.extract_text() for p in PdfReader(out).pages];clean=[]
for i,p in enumerate(pages,1):
 lines=p.splitlines()
 if lines and lines[0].strip()==str(i):lines=lines[1:]
 clean.append('\n'.join(lines))
norm=lambda s:re.sub(r'\s+','',s)
assert norm(re.sub(r'^#{1,2} ','',text,flags=re.M))==norm('\n'.join(clean)),'PDF text mismatch'
assert text.count('## [SLIDE ')==74
assert not any(s in '\n'.join(clean) for s in ['[제작:','[대기','[핵심]','[풀이]','[보충]'])
pdf=pdfium.PdfDocument(out);render=ev/'script-render';render.mkdir(exist_ok=True);thumbs=[]
for i in range(len(pdf)):
 img=pdf[i].render(scale=1.3).to_pil().convert('RGB');img.save(render/f'page-{i+1:02}.png');img.thumbnail((360,510));thumbs.append(img)
for start in range(0,len(thumbs),9):
 sheet=Image.new('RGB',(1120,1610),'#d8dce1');d=ImageDraw.Draw(sheet)
 for k,img in enumerate(thumbs[start:start+9]):
  x=10+k%3*370;y=25+k//3*530;sheet.paste(img,(x,y));d.text((x,y-17),str(start+k+1),fill='black')
 sheet.save(render/f'contact-{start//9+1}.png')
(ev/'pdf-check.json').write_text(json.dumps(dict(pages=len(pdf),slide_blocks=74,slide_coverage=78,exact_reading_text_match=True),indent=2),encoding='utf8')
print(len(pdf),'PDF pages; exact text match')


