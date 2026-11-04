"""1회차 06 도구 실습의 공통 학생 가이드 · ZIP 생성. 사진은 사진_만들기.py가 게시본 영상에서 뽑는다.
--draft <작업 폴더>: 초안만, --apply: 사진 확인이 다 된 뒤 두 과정 정본 폴더 · ZIP을 바꿔 끼운다."""
from pathlib import Path
import argparse,hashlib,html,json,re,shutil,sys,zipfile
from markdown_it import MarkdownIt
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[4];LAB='01일차_실습3_전체과정관찰';OUT=ROOT/'workspace/강의제작/산출물';SOURCE=HERE/'학생가이드_원고.md';MANIFEST=HERE/'전체과정_학생가이드_사진근거.json'

HASHED={}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def sha_once(p):
 HASHED.setdefault(p,sha(p));return HASHED[p]
def render(draft=False):
 text=SOURCE.read_text('utf8');manifest=json.loads(MANIFEST.read_text('utf8'));photos=manifest['photos'];ids=re.findall(r'<!-- PHOTO:([^ ]+) -->',text);assert len(ids)==len(set(ids)) and set(ids)==set(photos),'원고와 사진 근거가 다릅니다';assets={};pending=[]
 def replace(m):
  k=m[1];x=photos[k];path=ROOT/x['path'];source=ROOT/x['source'] if x.get('source') else None
  if not x.get('verified'):pending.append(k)
  if path.is_file() and x.get('sha256')==sha(path) and (draft or x.get('verified')):
   if source is None or not source.is_file() or sha_once(source)!=x.get('source_sha256'):raise ValueError('사진 원본 판본 불일치: '+k)
   name='images/'+path.name;assets[name]=path;cap=html.escape(x.get('caption',x['required_scene']));return f'<figure><a href="{html.escape(name)}"><img src="{html.escape(name)}" alt="{cap}" loading="lazy"></a><figcaption>{cap}</figcaption></figure>'
  return '<aside class="pending">미촬영: '+html.escape(x['required_scene'])+'<br>확인: '+html.escape(x['check'])+'</aside>'
 text=re.sub(r'<!-- PHOTO:([^ ]+) -->',replace,text);chunks=re.split(r'^## (.+)$',text,flags=re.M);intro=chunks[0];title=intro.splitlines()[0][2:];intro=intro.split('\n',1)[1];md=MarkdownIt('commonmark',{'html':True}).enable('table');nav=[];sections=[]
 for i in range(1,len(chunks),2):
  n=(i+1)//2;heading=html.escape(chunks[i]);nav.append(f'<a href="#step{n}">{heading}</a>');sections.append(f'<section id="step{n}"><h2>{heading}</h2>{md.render(chunks[i+1])}</section>')
 css="""body{font:17px/1.75 'Malgun Gothic',sans-serif;color:#23313d;margin:0;background:#f6f8f9}header,main{max-width:1100px;margin:auto;padding:24px}header{background:white}nav{position:sticky;top:0;background:white;border-bottom:1px solid #ccd6dc;padding:12px;display:flex;gap:18px;overflow-x:auto}nav a{white-space:nowrap;color:#174f72}section{scroll-margin-top:5rem;background:white;margin:24px 0;padding:24px;border-radius:12px}figure{margin:18px 0}img{display:block;max-width:100%;height:auto;border:1px solid #ccd6dc}figcaption{font-size:.9em;color:#445761}table{border-collapse:collapse;width:100%}th,td{border:1px solid #b9c6cf;padding:9px;vertical-align:top}.pending{background:#fff5dc;border-left:4px solid #a36b16;padding:14px} @media(max-width:700px){header,main{padding:12px}section{padding:15px}table{display:block;overflow-x:auto}}"""
 page=f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>{css}</style></head><body><header><p>1회차 · 두 과정 공통</p><h1>{html.escape(title)}</h1>{md.render(intro)}</header><nav aria-label="실습 순서">{"".join(nav)}</nav><main>{"".join(sections)}</main></body></html>';return page,assets,pending

def write(destination,page,assets):
 destination.mkdir(parents=True,exist_ok=True);(destination/'가이드.html').write_text(page,'utf8')
 for name,src in assets.items():target=destination/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,target)
 shutil.copyfile(HERE/'참고_교재_발췌_원고.md',destination/'참고_교재_발췌.md')

def main():
 ap=argparse.ArgumentParser();mode=ap.add_mutually_exclusive_group(required=True);mode.add_argument('--draft',type=Path);mode.add_argument('--apply',action='store_true');args=ap.parse_args()
 if args.apply:
  manifest=json.loads(MANIFEST.read_text('utf8'));photos=manifest['photos']
  missing=[k for k,v in photos.items() if not v.get('verified') or not v.get('source_sha256') or (v.get('source_type')=='video' and v.get('seconds') is None)]
  if missing:raise SystemExit('사진의 확인 또는 출처 시각이 미확인: '+', '.join(missing))
  page,assets,pending=render(draft=False)
  if pending or len(assets)!=len(photos):raise SystemExit('사진 누락: 정본을 바꾸지 않았습니다')
  sys.path.insert(0,str(HERE.parents[1]/'실습시작'))
  from lab_package import pack
  for course in ('통합반','실전반'):
   target=OUT/course/'실습/01회차/랩'/LAB
   if target.exists():shutil.rmtree(target)
   write(target,page,assets);pack(target)
  print('두 과정 가이드 · ZIP 적용');return
 dest=args.draft.resolve()
 if not dest.is_relative_to((ROOT/'작업').resolve()):ap.error('초안은 작업 폴더 안에만 둡니다')
 page,assets,pending=render(draft=True)
 for course in ('통합반','실전반'):
  folder=dest/course/LAB;write(folder,page,assets)
  with zipfile.ZipFile(dest/course/(LAB+'_검수용.zip'),'w',zipfile.ZIP_DEFLATED) as archive:
   for path in sorted(folder.rglob('*')):
    if path.is_file():archive.write(path,Path('01회차/랩')/LAB/path.relative_to(folder))
 (dest/'검수상태.json').write_text(json.dumps({'guide_source':SOURCE.relative_to(ROOT).as_posix(),'source_sha256':sha(SOURCE),'photos_total':len(assets)+len([x for x in pending if not (ROOT/json.loads(MANIFEST.read_text('utf8'))['photos'][x]['path']).is_file()]),'pending':pending,'note':'검수용 초안'},ensure_ascii=False,indent=2)+'\n','utf8');print('draft',dest,'available',len(assets),'pending',len(pending))
if __name__=='__main__':main()
