"""명시한 촬영 manifest로 정상 구간 선택·검증·합성. 미디어/실행값은 Git 밖에 둔다.
python lesson_pipeline.py <manifest.json> select|check|encode
"""
from pathlib import Path
import argparse, csv, hashlib, io, json, os, sys

def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))

def save(p, value):
    Path(p).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

def select(m, base):
    selected=[]
    for i, part in enumerate(m['takes']):
        source=base/part['take']; t=read(source/'timing.json')
        start=t['frames'][part['start_frame']]['time'] if 'start_frame' in part else part.get('start_ms', 0); end=part.get('end_ms', t['duration'])
        if part.get('from_cue'):
            start=next(a['time']-250 for a in t['actions'] if a['id']==part['from_cue'])
        if part.get('before_cue'):
            end=next(a['time']-250 for a in t['actions'] if a['id']==part['before_cue'])
        if t['error'] and 'end_ms' not in part and 'before_cue' not in part:
            raise ValueError(f"{source.name}: 오류 구간의 명시적 종료 지점 필요")
        assert 0<=start<end<=t['duration']
        for a in t['actions']:
            assert not a['time']<start<a['time']+a['duration'], a['id']
            assert not a['time']<end<a['time']+a['duration'], a['id']
        dest=base/(m['name']+f'-selected-{i:02}')
        dest.mkdir(exist_ok=True)
        actual=[f for f in t['frames'] if start<=f['time']<end]
        previous=[f for f in t['frames'] if f['time']<start]
        if previous and (not actual or actual[0]['time']>start): actual.insert(0,previous[-1])
        assert actual, source
        out={**t,'start':t['start']+start,'duration':end-start,'error':None,
             'source_range':{'take':source.name,'start_ms':start,'end_ms':end,'error':t['error']}}
        out['frames']=[{**f,'file':os.path.relpath(source/f['file'],dest).replace('\\','/'),'time':f['time']-start} for f in actual]
        out['motions']=[{**x,'start':x['start']-start,'end':x['end']-start} for x in t['motions'] if start<=x['start'] and x['end']<=end]
        out['actions']=[]
        for a in t['actions']:
            if not start<=a['time']<end: continue
            a=dict(a)
            for key in ['time','runAt','resultReady','clickAt','selectionReady','actionStart','actionEnd','commit']:
                if a.get(key) is not None: a[key]-=start
            out['actions'].append(a)
        save(dest/'timing.json',out)
        (dest/'end-state.json').write_bytes((source/'end-state.json').read_bytes())
        selected.append(dest.name)
    save(base/(m['name']+'-selection.json'),selected)
    return selected

def check(m, base, repo):
    spec=read(repo/m['cues']); selected=read(base/(m['name']+'-selection.json'))
    actions=[]; frames=[]; motions=[]; offset=0
    for name in selected:
        t=read(base/name/'timing.json'); assert not t['error']
        for a in t['actions']:
            a=dict(a)
            for k in ['time','runAt','resultReady','clickAt','selectionReady','actionStart','actionEnd','commit']:
                if a.get(k) is not None: a[k]+=offset
            actions.append(a)
        frames.extend({**f,'time':max(0,f['sourceTimestamp']*1000-t['start'])+offset,'path':str(base/name/f['file'])} for f in t['frames'])
        motions.extend({**x,'start':x['start']+offset,'end':x['end']+offset} for x in t['motions'])
        offset+=t['duration']
    assert [a['id'] for a in actions]==[c['id'] for c in spec['cues']], '큐 누락·중복·순서'
    for i,(a,c) in enumerate(zip(actions,spec['cues'])):
        meta=read(base/m['audio']/(a['id']+'.json'))
        assert a['text']==c['text']==meta['text'], a['id']
        assert a['duration']==meta['duration_ms'], a['id']
        if a['op'] in ['run','runSummary']:
            assert a['resultVerified'] and a['runAt']<a['time']+a['duration'], a['id']
            assert actions[i+1]['time']>=a['resultReady'], a['id']
        if a['op'] in ['node','edge']:
            assert a['selectionVerified'] and c['verify'] in a['details'], a['id']
            assert actions[i+1]['time']>=a['selectionReady'], a['id']
    download=Path(next(a['download'] for a in actions if a.get('download')))
    rows=list(csv.DictReader(io.StringIO(download.read_text(encoding='utf-8-sig'))))
    assert any(x['name']==spec['saved_title'] and x['query']==spec['saved_query'] for x in rows)
    png=Path(next(a['png'] for a in actions if a.get('png')))
    assert png.read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
    gaps=[]
    for x in motions:
        times=[f['time'] for f in frames if x['start']<=f['time']<=x['end']]
        gap=max(b-a for a,b in zip([x['start']]+times,times+[x['end']]))
        if gap>=100: gaps.append({**x,'gap_ms':gap})
    report={'duration_s':offset/1000,'cues':len(actions),'queries':sum(a['op'] in ['run','runSummary'] for a in actions),
            'selections':sum(a['op'] in ['node','edge'] for a in actions),'movement_over100ms':gaps,
            'csv':str(download),'csv_sha256':hashlib.sha256(download.read_bytes()).hexdigest(),
            'png':str(png),'not_verified':['전체 청취','사용자 재생','장면별 가독성·이음매 직접 확인']}
    save(base/(m['name']+'-qa.json'),report)
    print({k:v for k,v in report.items() if k not in ['movement_over100ms','not_verified']})
    print('움직임 100ms 이상 조사 대상:',len(gaps))
    return selected

def encode(m, base, repo):
    selected=check(m,base,repo)
    tool=repo/'제작용/촬영/arrows/촬영도구'
    sys.path.insert(0,str(tool)); import common
    common.WORK=base; os.environ['FFMPEG']=m['ffmpeg']
    target=base/m['name']/(m['name']+'_안치윤_1080p.mp4')
    if target.exists(): raise FileExistsError(f'기존 영상 보존: {target}. 새 name을 사용하세요.')
    sys.argv=['encode.py',m['name'],*selected]
    source=(tool/'encode.py').read_text(encoding='utf-8')
    source=source.replace("audio = base / 'audio'",'audio = base / '+repr(m['audio']))
    source=source.replace("'-crf', '18'","'-crf', '16'")
    source=source.replace('1920x1080 JPEG85 screencast (CSS 1536x864, arrows radius 70)',m['source_description'])
    begin=source.index("for stream in ('v', 'a'):");end=source.index('def stamp(ms):',begin)
    source=source[:begin]+'''probe=Path(ff).with_name('ffprobe.exe')
streams=json.loads(subprocess.check_output([str(probe),'-v','error','-show_streams','-of','json',str(mp4)],text=True))['streams']
for stream in streams:
    if abs(float(stream['duration'])-total)>0.1:
        raise RuntimeError('영상/음성 길이 불일치: '+str(stream['duration'])+' vs '+str(total))
'''+source[end:]
    exec(compile(source,str(tool/'encode.py'),'exec'),{'__name__':'__main__'})

def capture(m, base, repo):
    """합성에 쓴 동일 구간에서 단계 사진·검수판·이음매를 추출한다."""
    from PIL import Image, ImageDraw
    selected=check(m,base,repo); actions=[]; frames=[]; seams=[]; offset=0
    for name in selected:
        t=read(base/name/'timing.json')
        if offset: seams.append(offset)
        actions.extend({**a,'time':a['time']+offset} for a in t['actions'])
        frames.extend({**f,'time':max(0,f['sourceTimestamp']*1000-t['start'])+offset,'path':base/name/f['file']} for f in t['frames'])
        offset+=t['duration']
    def frame(at):
        return max((f for f in frames if f['time']<=at),key=lambda f:f['time'])
    provenance=[]
    for item in m.get('captures',[]):
        a=next(a for a in actions if a['id']==item['cue']); f=frame(a['time']+a['duration']*.7)
        im=Image.open(f['path']); crop=item.get('crop',[0,0,im.width,im.height]); dest=repo/item['path']
        dest.parent.mkdir(parents=True,exist_ok=True); im.crop(crop).save(dest,quality=92)
        provenance.append({'image':item['path'],'cue':a['id'],'source':str(f['path']),'crop':crop,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()})
    save(base/(m['name']+'-captures.json'),provenance)
    review=[a for a in actions if a['op'] in ['details','graphTalk','mapTour','savedResult','outro','result','graphResult','summaryTalk']]
    for batch in range((len(review)+3)//4):
        sheet=Image.new('RGB',(1920,1160),'white'); draw=ImageDraw.Draw(sheet)
        for i,a in enumerate(review[batch*4:(batch+1)*4]):
            im=Image.open(frame(a['time']+a['duration']*.7)['path']); im.thumbnail((960,540));x=i%2*960;y=i//2*580
            sheet.paste(im,(x,y+25));draw.text((x+5,y+5),a['id']+' '+a['op'],fill='black')
        sheet.save(base/(m['name']+f'-review-{batch}.jpg'))
    sheet=Image.new('RGB',(1920,max(1,len(seams))*565),'white'); draw=ImageDraw.Draw(sheet)
    for i,at in enumerate(seams):
        for j,delta in enumerate([-200,200]):
            im=Image.open(frame(at+delta)['path']); im.thumbnail((960,540));sheet.paste(im,(j*960,i*565+25))
            draw.text((j*960+5,i*565+5),f'{at/1000:.3f}s {delta:+}ms',fill='black')
    sheet.save(base/(m['name']+'-seams.jpg'))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('manifest',type=Path);p.add_argument('action',choices=['select','check','capture','encode']);args=p.parse_args()
    m=read(args.manifest);base=Path(m['evidence']).resolve();repo=Path(m['repo']).resolve()
    assert base.is_dir() and repo.is_dir()
    if args.action=='select': select(m,base)
    elif args.action=='check': check(m,base,repo)
    elif args.action=='capture': capture(m,base,repo)
    else: encode(m,base,repo)
