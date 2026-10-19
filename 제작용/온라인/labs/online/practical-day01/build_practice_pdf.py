"""실습 촬영 대본 네 개를 묶어 PDF로 만들고 텍스트·렌더를 검증한다."""
from pathlib import Path
from html import escape
import re, json
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pypdf import PdfReader
import pypdfium2 as pdfium
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[4]
BASE=ROOT/'산출물/교재/대본/실전반_온라인'
FILES=['02_실습_학습노트.md','04_실습_실행환경.md','06_실습_전체과정관찰.md','08_실습_관계그림.md']
pdfmetrics.registerFont(TTFont('Malgun','C:/Windows/Fonts/malgun.ttf'))
pdfmetrics.registerFont(TTFont('MalgunBold','C:/Windows/Fonts/malgunbd.ttf'))
body=ParagraphStyle('body',fontName='Malgun',fontSize=10.5,leading=17,wordWrap='CJK',spaceAfter=7)
cue=ParagraphStyle('cue',parent=body,fontSize=9,leading=14,textColor=colors.HexColor('#526578'),backColor=colors.HexColor('#f0f4f7'),borderPadding=5)
heading=ParagraphStyle('heading',parent=body,fontName='MalgunBold',fontSize=12,leading=19,spaceBefore=10,keepWithNext=True)
title=ParagraphStyle('title',parent=heading,fontSize=16,leading=24)
story=[];expected=[]
for i,name in enumerate(FILES):
    if i:story.append(PageBreak())
    text=(BASE/'01회차'/name).read_text('utf-8')
    for chunk in text.strip().split('\n\n'):
        chunk=chunk.strip()
        if not chunk or chunk=='---':continue
        if chunk.startswith('# '):content=chunk[2:];style=title
        elif chunk.startswith('## '):content=chunk[3:];style=heading
        elif chunk.startswith('>'):content=re.sub(r'^>\s?','',chunk,flags=re.M);style=cue
        else:content=chunk;style=body
        content=content.replace('**','').replace('`','')
        expected.append(content)
        story.append(Paragraph(escape(content).replace('\n','<br/>'),style))
def footer(canvas,doc):
    canvas.setFont('Malgun',8);canvas.drawRightString(A4[0]-18*mm,10*mm,str(doc.page))
out=BASE/'실전반_01일차_실습대본.pdf'
SimpleDocTemplate(str(out),pagesize=A4,leftMargin=18*mm,rightMargin=18*mm,topMargin=18*mm,bottomMargin=18*mm,title='실전반 온라인 1회차 실습 촬영 대본').build(story,onFirstPage=footer,onLaterPages=footer)
actual=[]
for i,page in enumerate(PdfReader(out).pages,1):
    lines=page.extract_text().splitlines()
    if lines and lines[0].strip()==str(i):lines=lines[1:]
    if lines and lines[-1].strip()==str(i):lines=lines[:-1]
    actual.append('\n'.join(lines))
norm=lambda s:re.sub(r'\s+','',s)
assert norm('\n'.join(expected))==norm('\n'.join(actual)), '실습 대본 PDF 텍스트 불일치'
ev=ROOT/'.evidence/practical01/practice-script-render';ev.mkdir(exist_ok=True)
pdf=pdfium.PdfDocument(out);thumbs=[]
for i in range(len(pdf)):
    im=pdf[i].render(scale=1.3).to_pil().convert('RGB');im.save(ev/f'page-{i+1:02}.png');im.thumbnail((360,510));thumbs.append(im)
for start in range(0,len(thumbs),9):
    sheet=Image.new('RGB',(1120,1610),'#d8dce1');d=ImageDraw.Draw(sheet)
    for k,im in enumerate(thumbs[start:start+9]):
        x=10+k%3*370;y=25+k//3*530;sheet.paste(im,(x,y));d.text((x,y-17),str(start+k+1),fill='black')
    sheet.save(ev/f'contact-{start//9+1}.png')
(ev/'check.json').write_text(json.dumps({'pages':len(pdf),'scripts':4,'exact_text_match':True},indent=2),encoding='utf-8')
print(f'{len(pdf)} pages, 4 scripts, exact text match')
