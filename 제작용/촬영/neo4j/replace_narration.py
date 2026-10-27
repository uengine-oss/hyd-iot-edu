"""정지 설명 구간의 음성 교체. 실제 조작의 속도·순서는 유지하고 끝 정지만 조절한다.
python replace_narration.py source_manifest.json new_cues.json new_audio_folder new_name
원본 timing/미디어는 보존한다. 결과 manifest를 lesson_pipeline.py로 검사·합성한다.
"""
from pathlib import Path
import json,sys,os,copy
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
m=read(sys.argv[1]);base=Path(m['evidence']);repo=Path(m['repo']);spec=read(sys.argv[2]);audio=sys.argv[3];name=sys.argv[4]
by_id={c['id']:c for c in spec['cues']};parts=[];edits=[]
for i,source_name in enumerate(read(base/(m['name']+'-selection.json'))):
 source=base/source_name;t=read(source/'timing.json');out=copy.deepcopy(t);changes=[]
 for j,a in enumerate(t['actions']):
  meta=read(base/audio/(a['id']+'.json'))
  assert meta['text']==by_id[a['id']]['text']
  if meta['text']==a['text'] and meta['duration_ms']==a['duration']:continue
  assert a['op'] in ['query','result','details','intro','outro'],a['id']
  delta=meta['duration_ms']-a['duration'];boundary=t['actions'][j+1]['time']-250 if j+1<len(t['actions']) else t['duration']
  cut_start=boundary+min(0,delta)
  last_motion=max([v['end'] for v in t['motions'] if a['time']<=v['start']<boundary]+[a['time']])
  assert cut_start>last_motion+1000,(a['id'],'would cut actual operation')
  changes.append({'id':a['id'],'boundary':boundary,'cut_start':cut_start,'delta':delta,'last_motion':last_motion,'old_duration':a['duration'],'new_duration':meta['duration_ms']})
 def mapped(v):
  return v+sum(c['delta'] for c in changes if v>=c['boundary'])
 dest=base/(name+f'-edit-{i:02}');dest.mkdir(exist_ok=False)
 out['frames']=[]
 for f in t['frames']:
  x=f['sourceTimestamp']*1000-t['start']
  if any(c['cut_start']<=x<c['boundary'] for c in changes if c['delta']<0):continue
  y=mapped(x);out['frames'].append({**f,'file':os.path.relpath(source/f['file'],dest).replace('\\','/'),'time':y,'captureTimestamp':f.get('captureTimestamp',f['sourceTimestamp']),'sourceTimestamp':(t['start']+y)/1000})
 for a in out['actions']:
  for k in ['time','runAt','resultReady','clickAt','selectionReady','actionStart','actionEnd','commit']:
   if a.get(k) is not None:a[k]=mapped(a[k])
  meta=read(base/audio/(a['id']+'.json'));a['text']=meta['text'];a['duration']=meta['duration_ms']
 for v in out['motions']:v['start']=mapped(v['start']);v['end']=mapped(v['end'])
 out['duration']=mapped(t['duration']);out['editorial_narration_changes']=changes;out['original_timing']=str(source/'timing.json')
 save(dest/'timing.json',out);(dest/'end-state.json').write_bytes((source/'end-state.json').read_bytes());parts.append({'take':dest.name});edits.extend(changes)
m.update(name=name,cues=str(Path(sys.argv[2]).resolve()),audio=audio,takes=parts);save(base/(name+'-manifest.json'),m);save(base/(name+'-narration-edits.json'),edits)
print(json.dumps(edits,ensure_ascii=False))
