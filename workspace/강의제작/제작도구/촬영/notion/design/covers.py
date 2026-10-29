from PIL import Image, ImageDraw
from pathlib import Path
import math
out=Path(__file__).parent
for kind in ['notion','agent','signal','knowledge']:
 im=Image.new('RGB',(1200,600),'#edf1f3');d=ImageDraw.Draw(im)
 navy='#395769'; faint='#d3dde2'; paper='#fbfaf5'; accent='#b58d5c'
 d.ellipse((330,30,870,570),fill='#e1e8eb')
 for x in range(60,1200,40):
  for y in range(60,600,40): d.ellipse((x,y,x+2,y+2),fill=faint)
 if kind=='notion':
  d.rounded_rectangle((425,130,785,490),20,fill=paper,outline=navy,width=5)
  d.rounded_rectangle((390,100,750,460),20,fill=paper,outline=navy,width=5)
  d.rectangle((390,100,440,460),fill=navy)
  for y,w in [(175,200),(225,240),(265,200),(305,240),(345,160)]:d.line((480,y,480+w,y),fill=navy if y==175 else faint,width=9 if y==175 else 5)
  d.polygon([(660,100),(700,100),(700,170),(680,155),(660,170)],fill=accent)
 elif kind=='agent':
  points=[(600,300),(420,160),(790,160),(420,440),(790,440)]
  for p in points[1:]:d.line((600,300,*p),fill=navy,width=5)
  for i,(x,y) in enumerate(points):
   r=65 if i==0 else 44;d.rounded_rectangle((x-r,y-r,x+r,y+r),16,fill=navy if i==0 else paper,outline=navy,width=5)
   if i==0:
    for ox in [-22,22]:d.ellipse((x+ox-5,y-7,x+ox+5,y+3),fill=paper)
   else:d.ellipse((x-8,y-8,x+8,y+8),fill=accent)
 elif kind=='signal':
  d.rounded_rectangle((350,120,850,465),20,fill=paper,outline=navy,width=5)
  for y in range(185,450,60):d.line((380,y,820,y),fill=faint,width=2)
  pts=[(380,335),(430,330),(470,345),(510,320),(550,335),(595,205),(640,350),(680,325),(730,335),(780,310),(820,320)]
  d.line(pts,fill=navy,width=6,joint='curve');d.ellipse((581,191,609,219),fill=accent)
  d.line((500,500,700,500),fill=navy,width=5)
 elif kind=='knowledge':
  d.polygon([(365,150),(565,175),(600,200),(635,175),(835,150),(835,430),(635,455),(600,480),(565,455),(365,430)],fill=paper,outline=navy,width=5)
  d.line((600,200,600,475),fill=navy,width=5)
  for y in [235,285,335,385]:
   d.line((405,y,555,y+20),fill=faint,width=5);d.line((645,y+20,795,y),fill=faint,width=5)
  d.polygon([(720,165),(758,160),(758,265),(738,250),(720,270)],fill=accent)
 im.save(out/(kind+'.png'))
