"""학생가이드.json의 photos[]가 가리키는 순간을 게시본 촬영판(작업/촬영/notion/Notion_학습노트_v12d)에서 PNG로 뽑는다.
언제: 학생 가이드의 사진 순간(큐 · 시점 · 차이)을 고쳤을 때. 뽑은 프레임은 build_student_guide.py --frames <작업 폴더>/프레임 이 쓴다.
쓰는 법(ffmpeg가 PATH에 있어야 한다, 출력은 GUIDE_WORK 환경 변수의 작업 폴더에 쓴다):
      GUIDE_WORK=<작업 폴더> <py> 가이드_프레임뽑기.py [사진 id …]   (없으면 전부 → 프레임/)
      GUIDE_WORK=<작업 폴더> <py> 가이드_프레임뽑기.py --at <MM:SS.mmm> <이름>   (후보 프레임 하나 → 후보/)
      GUIDE_WORK=<작업 폴더> <py> 가이드_프레임뽑기.py --sheet <이름> <png …>   (보기용 2x2 모음 → 보기/)"""
import json, subprocess, sys, os
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[5]
if not os.environ.get('GUIDE_WORK'): raise SystemExit('GUIDE_WORK=<작업 폴더>를 준다(저장소의 작업/ 아래)')
HERE = Path(os.environ['GUIDE_WORK']).resolve()
SRC = ROOT/'workspace/강의제작/제작도구/촬영/notion/학생가이드.json'
V = ROOT/'작업/촬영/notion/Notion_학습노트_v12d'
_mp4 = sorted(V.glob('*_1080p.mp4'))
if len(_mp4) != 1: raise SystemExit(f'{V}: *_1080p.mp4가 하나여야 한다(지금 {len(_mp4)}개)')
MP4 = _mp4[0]
OUT = HERE/'프레임'

def ms(t):
    m, s = t.split(':'); return round((int(m)*60 + float(s))*1000)

def timeline():
    ct = json.loads((V/'verification.json').read_text(encoding='utf-8'))['cue_timeline']
    out = {}
    for i, c in enumerate(ct):
        d = {'speech_start': ms(c['speech'][0]), 'speech_end': ms(c['speech'][1])}
        if c.get('action'):
            d['action_end'] = ms(c['action'][1])
            if c.get('commit'): d['commit'] = ms(c['commit'])
        if i+1 < len(ct): d['next_start'] = ms(ct[i+1]['speech'][0])
        out[c['id']] = d
    return out

def grab(t_ms, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{t_ms/1000:.3f}', '-i', str(MP4),
                    '-frames:v', '1', str(dest)], check=True)

def photo_time(p, tl):
    c = tl.get(p['cue'])
    if c is None: raise SystemExit(f"{p['id']}: 큐 {p['cue']}가 cue_timeline에 없다")
    if p['at'] not in c: raise SystemExit(f"{p['id']}: 큐 {p['cue']}에 {p['at']}이 없다")
    return c[p['at']] + p['offset_ms']

def main():
    a = sys.argv[1:]
    if a and a[0] == '--at':
        grab(ms(a[1]), HERE/'후보'/(a[2]+'.png')); return
    if a and a[0] == '--sheet':
        ims = [Image.open(x).convert('RGB').resize((960, 540), Image.LANCZOS) for x in a[2:6]]
        sheet = Image.new('RGB', (1920, 1080), 'white')
        for k, im in enumerate(ims): sheet.paste(im, ((k % 2)*960, (k//2)*540))
        (HERE/'보기').mkdir(exist_ok=True); sheet.save(HERE/'보기'/(a[1]+'.jpg'), quality=88); return
    tl = timeline(); data = json.loads(SRC.read_text(encoding='utf-8')); rows = []
    for s in data['steps']:
        for p in s['photos']:
            if a and p['id'] not in a: continue
            t = photo_time(p, tl); grab(t, OUT/(p['id']+'.png'))
            rows.append({'id': p['id'], 'cue': p['cue'], 'at': p['at'], 'offset_ms': p['offset_ms'], 'time_ms': t})
    log = HERE/'뽑기_기록.json'
    old = json.loads(log.read_text(encoding='utf-8')) if log.exists() else {}
    old.update({r['id']: r for r in rows})
    log.write_text(json.dumps(dict(sorted(old.items())), ensure_ascii=False, indent=1)+'\n', encoding='utf-8')
    print(len(rows), '장')

if __name__ == '__main__': main()
