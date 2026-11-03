"""실전2의 카디널리티·저장소 경로·속성 그래프. 글자는 MD/native 라벨이다."""
from pathlib import Path
import math
FIG=Path(__file__).resolve().parent
NAVY="#13294B";BLUE="#1A6FC4";SKY="#5CB8F2"
def svg(nodes,edges,rects=[]):
 a=['<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="500" viewBox="0 0 1200 500"><defs><marker id="a" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="#1A6FC4"/></marker><marker id="r" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="#C94D55"/></marker></defs>']
 for x,y,w,h in rects:a.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="#F2F5F9" stroke="#D3D9E1"/>')
 for i,j,bad,new in edges:
  x,y,r=nodes[i];xx,yy,rr=nodes[j];dx=xx-x;dy=yy-y;d=math.hypot(dx,dy);x+=dx*r/d;y+=dy*r/d;xx-=dx*rr/d;yy-=dy*rr/d;col='#C94D55' if bad else BLUE;dash='stroke-dasharray="8 6"' if new else ''
  pts=[(x,y),(xx,yy)]
  if i==10 and j==13:pts=[(700,268),(700,257),(1100,257),(1100,268)]
  for (px,py),(qx,qy) in zip(pts,pts[1:]):
   dd=math.hypot(qx-px,qy-py);ux=(qx-px)/dd;uy=(qy-py)/dd
   segs=[(0,dd)] if not new else [(v,min(v+8,dd)) for v in range(0,int(dd),14)]
   for lo,hi in segs:a.append(f'<path d="M{px+ux*lo},{py+uy*lo} L{px+ux*hi},{py+uy*hi}" fill="none" stroke="{col}" stroke-width="2.4"/>')
  px,py=pts[-2];qx,qy=pts[-1];dd=math.hypot(qx-px,qy-py);ux=(qx-px)/dd;uy=(qy-py)/dd
  a.append(f'<path d="M{qx},{qy} L{qx-14*ux+6*uy},{qy-14*uy-6*ux} L{qx-14*ux-6*uy},{qy-14*uy+6*ux} Z" fill="{col}"/>')
  if bad:
   mx=(x+xx)/2;my=(y+yy)/2;a.append(f'<path d="M{mx-7},{my-7} L{mx+7},{my+7} M{mx+7},{my-7} L{mx-7},{my+7}" stroke="{col}" stroke-width="3"/>')
 for x,y,r in nodes:a.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#E7F3FD" stroke="{BLUE}" stroke-width="2"/>')
 a.append('</svg>');return ''.join(a)
nodes=[(100,145,50),(350,145,50),(500,205,50),(700,145,50),(900,95,50),(900,205,50),(1100,145,50),(100,335,50),(350,400,50),(100,445,50),(700,335,50),(900,305,50),(900,435,50),(1100,335,50),(700,445,50),(1100,445,50)]
edges=[(0,1,False,False),(2,1,True,True),(3,4,False,False),(3,5,False,False),(6,4,True,True),(7,8,False,False),(9,8,False,True),(10,11,False,False),(10,12,False,False),(10,13,False,False),(14,11,False,False),(10,15,False,True)]

f=FIG/'카디널리티_네형태.svg'
nodes=[(x,y,60) for x,y,r in nodes]
for i,v in {1:(350,145,80),2:(500,195,60),4:(900,60,55),5:(900,185,60),7:(100,320,50),8:(350,390,80),9:(100,440,50),10:(700,320,52),11:(900,440,52),12:(900,320,52),13:(1100,320,52),14:(700,440,52),15:(1100,440,52)}.items():nodes[i]=v
f.write_text(svg(nodes,edges),'utf8')
f=FIG/'식별자_저장소경로.svg';rects=[(20,140,245,140),(325,140,245,140),(630,140,245,140),(935,140,245,140),(25,335,550,90),(625,335,550,90)];sh=['<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="500" viewBox="0 0 1200 500">']
for x,y,w,hh in rects:sh.append(f'<rect x="{x}" y="{y}" width="{w}" height="{hh}" rx="14" fill="#E7F3FD" stroke="{SKY}" stroke-width="2"/>')
for x in [270,575,880]:sh.append(f'<path d="M{x},205 L{x+45},205 M{x+35},195 L{x+45},205 L{x+35},215" fill="none" stroke="{BLUE}" stroke-width="3"/>')
sh.append('</svg>');f.write_text(''.join(sh),'utf8')
nodes=[(180,130,65),(600,130,85),(180,365,65),(600,365,65)];f=FIG/'속성그래프_저장모양.svg';f.write_text(svg(nodes,[(0,1,False,False),(2,3,False,False)],[(850,20,325,455)]),'utf8')
