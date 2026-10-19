"""Preserve dashed semantics as explicit geometry; safe to run repeatedly."""
from pathlib import Path
import re,math,sys
here=Path(__file__).parent
folder=Path(sys.argv[1]) if len(sys.argv)>1 else (here if here.name=='figures' else here/'output/만들기/decks/integrated/day11/figures')
assert folder.is_dir(),folder
def convert(m):
 tag,attrs=m.groups();a=dict(re.findall(r'([\w-]+)="([^"]*)"',attrs));dash=list(map(float,a['stroke-dasharray'].split()));assert len(dash)==2
 parts=[]
 if tag=='circle':
  cx,cy,r=(float(a[k]) for k in ('cx','cy','r'));length=2*math.pi*r
  point=lambda t:(cx+r*math.cos(t/r),cy+r*math.sin(t/r))
  if a.get('fill','none')!='none':parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{a["fill"]}" stroke="none"/>')
 else:
  if tag=='rect':
   x,y,w,h=(float(a[k]) for k in ('x','y','width','height'));rx=float(a.get('rx',0));ry=float(a.get('ry',rx));pts=[]
   for cx,cy,start in [(x+w-rx,y+ry,-90),(x+w-rx,y+h-ry,0),(x+rx,y+h-ry,90),(x+rx,y+ry,180)]:
    for i in range(17):
     ang=math.radians(start+i*90/16);pts.append((cx+rx*math.cos(ang),cy+ry*math.sin(ang)))
   pts.append(pts[0])
   if a.get('fill','none')!='none':parts.append('<rect '+' '.join(f'{k}="{a[k]}"' for k in ('x','y','width','height','rx','ry','fill') if k in a)+' stroke="none"/>')
  elif tag=='line':pts=[(float(a['x1']),float(a['y1'])),(float(a['x2']),float(a['y2']))]
  else:
   assert tag=='path' and not re.search(r'[A-KN-Za-kn-z]',a['d']),a
   nums=list(map(float,re.findall(r'-?\d+(?:\.\d+)?',a['d'])));pts=list(zip(nums[::2],nums[1::2]))
  lengths=[math.dist(x,y) for x,y in zip(pts,pts[1:])];length=sum(lengths)
  def point(t):
   for (x,y),(xx,yy),d in zip(pts,pts[1:],lengths):
    if d and t<=d:return x+(xx-x)*t/d,y+(yy-y)*t/d
    t-=d
   return pts[-1]
 segments=[];t=0
 while t<length:
  end=min(t+dash[0],length);steps=max(1,math.ceil(end-t));xy=[point(t+(end-t)*i/steps) for i in range(steps+1)]
  segments.append('M '+' L '.join(f'{x:.3f},{y:.3f}' for x,y in xy));t+=sum(dash)
 style=' '.join(f'{k}="{v}"' for k,v in a.items() if k in ['stroke','stroke-width','stroke-linecap','stroke-linejoin'])
 parts.append('<path d="'+' '.join(segments)+'" fill="none" '+style+'/>');return '\n'.join(parts)
count=0;files=[]
for p in folder.glob('*.svg'):
 s=p.read_text(encoding='utf8');s,n=re.subn(r'<(circle|path|rect|line)\b([^>]*stroke-dasharray="[^"]+"[^>]*)/>',convert,s)
 assert 'stroke-dasharray' not in s,p
 if n:p.write_text(s,encoding='utf8');count+=n;files.append(p.name)
print('Explicit dashed geometry:',count,'in',len(files),'SVG files')
