"""Notion learning portal artwork. Original geometric illustrations, no external assets."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import json

ROOT=Path(__file__).parent
OUT=ROOT/'assets';OUT.mkdir(exist_ok=True)
FONT='C:/Windows/Fonts/malgun.ttf'
BOLD='C:/Windows/Fonts/malgunbd.ttf'
PALETTES={
 'knowledge':('#EDF4F2','#25665E','#C5DCD6','지식 그래프','KNOWLEDGE'),
 'agent':('#F0EFF6','#615783','#D8D3E6','AI 에이전트','AGENT'),
 'process':('#F7F1E8','#8B6538','#E7D5BA','업무 프로세스','PROCESS')}
def font(n,bold=False):return ImageFont.truetype(BOLD if bold else FONT,n)
def motif(d,kind,cx,cy,s=1):
 bg,ink,soft,*_=PALETTES[kind]
 def xy(x,y):return (int(cx+x*s),int(cy+y*s))
 def line(pts,fill=ink,w=5):d.line([xy(*p) for p in pts],fill=fill,width=max(1,int(w*s)),joint='curve')
 def box(x,y,w,h,fill='white',r=12):
  a=xy(x,y);b=xy(x+w,y+h);d.rounded_rectangle((*a,*b),radius=int(r*s),fill=fill,outline=ink,width=max(1,int(4*s)))
 def node(x,y,r,fill):
  a=xy(x-r,y-r);b=xy(x+r,y+r);d.ellipse((*a,*b),fill=fill,outline=ink,width=max(1,int(4*s)))
 if kind=='knowledge':
  pts=[(-126,-65),(0,-95),(123,-50),(-98,92),(38,101),(0,0)]
  for a,b in [(0,5),(1,5),(2,5),(3,5),(4,5),(0,1),(2,4)]:line([pts[a],pts[b]],soft,8)
  for i,(x,y) in enumerate(pts):node(x,y,31 if i==5 else 18,ink if i==5 else 'white')
  node(0,0,9,'white')
 elif kind=='agent':
  for a,b in [((-115,-70),(-45,-25)),((113,-70),(45,-25)),((-115,80),(-45,25)),((113,80),(45,25))]:line([a,b],soft,8)
  box(-54,-47,108,94,ink,22)
  # a focused reasoning core rather than a repeated robot face
  line([(-23,0),(0,-22),(23,0),(0,22),(-23,0)],'white',5)
  for x,y in [(-150,-100),(85,-100),(-150,50),(85,50)]:box(x,y,66,57)
  line([(-134,-81),(-100,-81)],ink,4);line([(-134,-67),(-112,-67)],ink,4)
  line([(99,-74),(110,-62),(136,-87)],ink,4)
  line([(-133,79),(-125,70),(-116,86),(-104,73)],ink,4)
  line([(99,76),(108,85),(135,64)],ink,4)
 else:
  line([(-155,0),(-76,0)],soft,8)
  line([(0,0),(65,0),(65,-76),(119,-76)],soft,8)
  line([(0,0),(65,0),(65,76),(119,76)],soft,8)
  node(-164,0,23,'white')
  pts=[xy(-45,-40),xy(-5,0),xy(-45,40),xy(-85,0)]
  d.polygon(pts,fill=ink)
  line([(-58,0),(-48,11),(-29,-12)],'white',4)
  box(112,-105,74,58);box(112,47,74,58,soft)
  line([(128,-76),(170,-76)],ink,4)
  line([(130,75),(140,85),(166,65)],ink,4)

def cover(course,n,kind,subtitle):
 bg,ink,soft,title,en=PALETTES[kind]
 im=Image.new('RGB',(1440,720),bg);d=ImageDraw.Draw(im)
 # All text and pictograms remain within the gallery/page-cover crop safe zone.
 d.rounded_rectangle((95,210,103,510),4,fill=ink)
 d.text((140,221),f'{course.upper()}  /  {n:02d}',font=font(27,True),fill=ink)
 d.text((135,276),title,font=font(57,True),fill='#27343B')
 d.text((140,364),subtitle,font=font(29),fill=ink)
 d.text((140,435),en,font=font(20),fill=ink)
 d.ellipse((925,164,1325,564),fill=soft)
 d.ellipse((945,184,1305,544),fill=bg)
 motif(d,kind,1125,365,.98)
 im.save(OUT/f'{course}-{n:02d}.png',optimize=True)

def home(course):
 im=Image.new('RGB',(1800,600),'#F3F2EE');d=ImageDraw.Draw(im)
 d.text((170,222),'HYD',font=font(90,True),fill='#27343B')
 d.text((180,344),'PHYSICAL AI  /  '+course.upper(),font=font(23),fill='#69736F')
 for i,kind in enumerate(PALETTES):
  x=790+i*325;bg,ink,soft,*_=PALETTES[kind]
  d.rounded_rectangle((x-131,162,x+131,438),30,fill=bg)
  motif(d,kind,x,300,.59)
  if i<2:d.line((x+142,300,x+173,300),fill='#C8CECA',width=3)
 im.save(OUT/f'home-{course}.png',optimize=True)

integrated=[('knowledge','데이터에서 판단과 조치까지'),('knowledge','클래스 · 관계 · 스키마'),('knowledge','안전 조건 · 성과 비교'),('knowledge','문서에서 신뢰할 근거로'),('agent','근거를 읽고 작업하기'),('agent','스킬 · MCP · 도구 연결'),('agent','사람의 승인 · 요구사항'),('agent','변경 · 검증 · 완성'),('process','역할 · 분기 · 업무 흐름'),('process','정비에서 구매까지'),('process','내 주제로 완성하기')]
applied=[('knowledge','데이터에서 판단과 조치까지'),('knowledge','지식 구조 · 조치 조건'),('knowledge','성과 비교 · 근거 추출'),('agent','업무 수행 · 도구 활용'),('agent','협업 · 명세 · 검증'),('process','설비 대응 흐름 완성'),('process','정비 · 구매 · 실행 검증'),('process','내 주제에 응용하기')]
for course,rows in [('integrated',integrated),('applied',applied)]:
 home(course)
 for n,(kind,title) in enumerate(rows,1):cover(course,n,kind,title)
for kind,(bg,*_) in PALETTES.items():
 im=Image.new('RGB',(480,480),bg);d=ImageDraw.Draw(im);motif(d,kind,240,240,1.05);im.save(OUT/f'icon-{kind}.png',optimize=True)
# Contact sheet for visual review, not a deployable asset.
sheet=Image.new('RGB',(1080,780),'white')
for i,p in enumerate([OUT/'home-integrated.png',OUT/'integrated-02.png',OUT/'integrated-05.png',OUT/'integrated-09.png']):
 im=Image.open(p);im.thumbnail((540,390));sheet.paste(im,((i%2)*540,(i//2)*390))
sheet.save(ROOT/'preview.png')
print('Created',len(list(OUT.glob('*.png'))),'assets')
