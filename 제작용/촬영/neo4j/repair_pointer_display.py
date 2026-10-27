"""Correct only displayed pointer motion in stationary UI; retain recorded endpoints and time.
Does not reconstruct browser frames, clicks, graph interaction or missing UI states.
"""
from pathlib import Path
import argparse, json, numpy as np
from PIL import Image, ImageDraw
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('motion_report',type=Path);parser.add_argument('output',type=Path);parser.add_argument('--motion',type=int,action='append',required=True);args=parser.parse_args()
out=args.output.resolve();out.mkdir(exist_ok=False)
items=json.loads(args.motion_report.read_text(encoding='utf-8'));report=[]
for item in items:
 if item['index'] not in args.motion:continue
 fs=sorted(item['frames'],key=lambda f:f['at']);m=item['motion'];idx=item['index']
 box=(max(0,int(min(m['from']['x'],m['x'])*1.25)-10),max(0,int(min(m['from']['y'],m['y'])*1.25)-10),min(1920,int(max(m['from']['x'],m['x'])*1.25)+35),min(1080,int(max(m['from']['y'],m['y'])*1.25)+45))
 arrays=np.stack([np.asarray(Image.open(f['path']).crop(box)) for f in fs]);clean=np.median(arrays,axis=0).astype('uint8')
 points=[];max_residual=0
 for f,arr in zip(fs,arrays):
  mask=np.max(np.abs(arr.astype(int)-clean.astype(int)),axis=2)>45
  pending=set(zip(*np.where(mask)));groups=[]
  while pending:
   seed=pending.pop();stack=[seed];component=[seed]
   while stack:
    yy,xx=stack.pop()
    for q in [(yy-1,xx),(yy+1,xx),(yy,xx-1),(yy,xx+1)]:
     if q in pending:pending.remove(q);stack.append(q);component.append(q)
   if len(component)>=12:
    ys,xs=zip(*component);groups.append((len(component),(slice(min(ys),max(ys)+1),slice(min(xs),max(xs)+1))))
  assert groups,(idx,f['at'])
  # The arrow's black contour is connected and larger than JPEG residuals.
  count,sl=max(groups,key=lambda x:x[0]);y,x=sl
  assert x.stop-x.start<=31 and y.stop-y.start<=42,(idx,'not pointer',sl)
  # Include complete arrow raster; other changed pixels must be only JPEG noise.
  rect=(max(0,x.start-3),max(0,y.start-3),min(clean.shape[1],x.stop+4),min(clean.shape[0],y.stop+4))
  residual=mask.copy();residual[rect[1]:rect[3],rect[0]:rect[2]]=False
  residual=int(residual.sum());max_residual=max(max_residual,residual)
  assert residual<45,(idx,'UI changes outside cursor',residual)
  points.append({'at':f['at'],'x':float(x.start+box[0]),'y':float(y.start+box[1]),'rect':rect,'path':f['path']})
 # Restore one verified static background region; outside the region preserve each source frame.
 # Use the actual arrow pixels from a frame with a white background, with a conservative shape mask.
 arrow=Image.new('RGBA',(100,136));draw=ImageDraw.Draw(arrow)
 shape=[(4,4),(4,100),(28,80),(48,124),(68,116),(48,72),(88,72)]
 draw.polygon(shape,fill='white');draw.line(shape+[shape[0]],fill='#111111',width=7,joint='curve')
 arrow=arrow.resize((25,34),Image.Resampling.LANCZOS)
 start=fs[0]['at'];end=fs[-1]['at'];new=[]
 times=np.arange(start,end,1000/30).tolist()+[end]
 for j,at in enumerate(times):
  before=max((f for f in fs if f['at']<=at),key=lambda f:f['at'])
  im=Image.open(before['path']).convert('RGB');im.paste(Image.fromarray(clean),(box[0],box[1]))
  x=float(np.interp(at,[p['at'] for p in points],[p['x'] for p in points]));y=float(np.interp(at,[p['at'] for p in points],[p['y'] for p in points]))
  im.paste(arrow,(round(x)-1,round(y)-1),arrow)
  path=out/f'm{idx}-{j:03}.jpg';im.save(path,quality=98,subsampling=0)
  new.append({'at':at,'path':str(path),'x':x,'y':y})
 sheet=Image.new('RGB',(1920,((len(new)+3)//4)*240),'#ddd');draw=ImageDraw.Draw(sheet)
 for j,f in enumerate(new):
  im=Image.open(f['path']).crop(box);im.thumbnail((480,210));x=j%4*480;y=j//4*240;sheet.paste(im,(x,y+25));draw.text((x+5,y+4),f"{f['at']/1000:.3f}",fill='black')
 sheet.save(out/f'proof-{idx}.jpg')
 report.append({'index':idx,'cue':item['cue'],'start':start,'end':end,'original_gap_ms':item['gap'],'max_nonpointer_changed_pixels':max_residual,'box':box,'observed_pointer_positions':points,'frames':new,'method':'pointer-display-only; temporal median from actual stationary UI; linear interpolation between observed arrow positions; original time retained'})
(out/'repair.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=lambda v:v.item()),encoding='utf-8')
print([{k:v for k,v in x.items() if k not in ['frames','observed_pointer_positions']} for x in report])
