"""Apply reviewed narration replacements and pointer-only corrections to preserved takes.

Never changes actual browser operations. Time changes are allowed only in an idle
cue tail, after recorded motion/operation events. Emits a new derived take and
manifest; old media is preserved. Pointer repairs must have separately inspected
provenance, not invented browser results.
"""
from pathlib import Path
import argparse,copy,json,shutil

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')

def prepare(manifest,cues,audio,name,repairs):
 m=read(manifest);base=Path(m['evidence']);selected=read(base/(m['name']+'-selection.json'))
 dest=base/(name+'-derived');dest.mkdir(exist_ok=False)
 actions=[];frames=[];motions=[];offset=0;sources=[]
 keys=['time','runAt','resultReady','clickAt','selectionReady','actionStart','actionEnd','commit']
 for part in selected:
  folder=base/part;t=read(folder/'timing.json');assert not t['error']
  sources.append({'take':part,'offset':offset,'duration':t['duration']})
  for a in t['actions']:
   a=copy.deepcopy(a)
   for k in keys:
    if a.get(k) is not None:a[k]+=offset
   actions.append(a)
  frames += [dict(f,file=str((folder/f['file']).resolve()).replace('\\','/'),time=max(0,f['sourceTimestamp']*1000-t['start'])+offset) for f in t['frames']]
  motions += [dict(x,start=x['start']+offset,end=x['end']+offset) for x in t['motions']]
  offset+=t['duration']
 spec=read(cues);assert [a['id'] for a in actions]==[c['id'] for c in spec['cues']]
 edits=[]
 for a,c in zip(actions,spec['cues']):
  meta=read(base/audio/(a['id']+'.json'));assert meta['text']==c['text']
  if meta['text']==a['text']:
   assert meta['duration_ms']==a['duration'];continue
  old_end=a['time']+a['duration'];new_end=a['time']+meta['duration_ms'];cut=min(old_end,new_end)
  assert not any(x['start']<old_end and x['end']>cut for x in motions),'Cannot trim actual motion'
  assert all(a.get(k,0)<=cut for k in keys if k!='time' and a.get(k) is not None),'Cannot trim operation'
  edits.append({'id':a['id'],'old_text':a['text'],'new_text':meta['text'],'old_end':old_end,'cut':cut,'delta':new_end-old_end,'old_duration':a['duration'],'new_duration':meta['duration_ms']})
 def kept(t):return not any(e['delta']<0 and e['cut']<t<e['old_end'] for e in edits)
 def mapped(t):return t+sum(e['delta'] for e in edits if e['old_end']<=t)
 original_frames=sorted(frames,key=lambda x:x['time']);repair=read(repairs)
 for rp in repair:
  assert rp['max_nonpointer_changed_pixels']<45
  assert not any(x['op'] in ['run','runSummary','node','edge'] and x['time']<=rp['start']<=x['time']+x['duration'] for x in actions),'Pointer correction crosses actual UI interaction'
  frames=[f for f in frames if not rp['start']<=f['time']<=rp['end']]
  frames += [{'file':f['path'].replace('\\','/'),'time':f['at'],'pointer_display_corrected':True} for f in rp['frames']]
 frames=[dict(f,time=mapped(f['time']),sourceTimestamp=mapped(f['time'])/1000) for f in frames if kept(f['time'])]
 frames.sort(key=lambda x:x['time'])
 # ffmpeg concat uses the first image codec for the stream; mixing PNG/JPEG
 # silently drops correction frames. Require a uniform raster format.
 assert len({Path(f['file']).suffix.lower() for f in frames})==1,'Mixed image codecs: convert repairs to the source format first'
 for a,c in zip(actions,spec['cues']):
  for k in keys:
   if a.get(k) is not None:a[k]=mapped(a[k])
  meta=read(base/audio/(a['id']+'.json'));a['text']=meta['text'];a['duration']=meta['duration_ms']
 for x in motions:x['start']=mapped(x['start']);x['end']=mapped(x['end'])
 total=offset+sum(e['delta'] for e in edits)
 for a,b in zip(actions,actions[1:]):assert a['time']+a['duration']<=b['time'],a['id']
 save(dest/'timing.json',{'start':0,'duration':total,'frames':frames,'actions':actions,'motions':motions,'error':None,'derived_from':sources,'narration_edits':edits,'pointer_display_repairs':str(Path(repairs).resolve()),'result':'derived media; original browser actions retained'})
 shutil.copy2(base/selected[-1]/'end-state.json',dest/'end-state.json')
 new={**m,'name':name,'cues':str(Path(cues).resolve()),'audio':audio,'takes':[{'take':dest.name}],'source_description':'1920x1080 JPEG95 original browser actions; reviewed narration edits; 2 pointer-display-only corrections on stationary UI; no speed changes','captures':[]}
 save(base/(name+'-manifest.json'),new)
 save(base/(name+'-edits.json'),{'sources':sources,'narration_edits':edits,'duration_ms':total,'pointer_repairs':str(Path(repairs).resolve()),'original_motion_gap_report':str(base/(m['name']+'-qa.json'))})
 print(json.dumps({'name':name,'seconds':total/1000,'voice_edits':len(edits),'pointer_repairs':len(repair)},ensure_ascii=False))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('manifest');p.add_argument('cues');p.add_argument('audio');p.add_argument('name');p.add_argument('repairs');a=p.parse_args();prepare(a.manifest,a.cues,a.audio,a.name,a.repairs)
