"""현재 분할 대본과 랩 자료에서만 파생물을 생성한다. 옛 콘텐츠 조립기는 실행하지 않는다."""
from pathlib import Path
import sys,importlib.util,json,re,html,zipfile,hashlib,shutil
D=Path('D:/work/study/hyd-portal-latest-20261014');C=Path('D:/work/study/hyd-integrated-recovered-20261018');EV=D/'.evidence/online-revision-20261019'
sys.argv=[__file__,str(C)]
spec=importlib.util.spec_from_file_location('doc_helpers',D/'만들기/labs/online/finalize20261019/helpers.py');H=importlib.util.module_from_spec(spec);spec.loader.exec_module(H);H.EV=EV
# 현재 문서만 합치는 기존 도구를 과정명에 맞춰 사용한다. 학생 코드는 로드하지 않는다.
merge_source=(D/'만들기/tools/deck/실전분할대본합치기.py').read_text('utf8')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
rows=[];pairs=[];pdfs=[]
for root,course,total in [(C,'통합반',11),(D,'실전반',8)]:
 baseline=json.loads((root/'.evidence/online-revision-20261019/before.json').read_text('utf8'))
 for day in range(1,total+1):
  folder=root/f'산출물/교재/대본/{course}_온라인/{day:02}회차';cfg=json.loads((folder/'구성.json').read_text('utf8'))
  labscripts=[folder/u['file'] for u in cfg['units'] if u['kind']=='practice']
  guide=root/f'산출물/실습/{course}_온라인/{day:02}회차_실습_안내.md';oldguide=guide.read_text('utf8')
  labdirs=sorted([p for p in guide.parent.glob(f'{day:02}일차_실습*') if p.is_dir() and p.name in oldguide],key=lambda p:int(re.search('실습(\d+)',p.name)[1]))
  assert len(labscripts)==len(labdirs),(folder,len(labscripts),len(labdirs))
  theory_changed=any(sha(f)!=baseline.get(f.relative_to(root).as_posix()) for f in folder.glob('*_이론_*.md'))
  if theory_changed:
   H.patch_notes(folder,cfg['slide_count'],root/f'만들기/decks/{"integrated" if course=="통합반" else "practical"}/day{day:02}/{course}_{day:02}일차.md',root/f'산출물/교재/PPTX/{course}_온라인/{course}_{day:02}일차.pptx')
  for u in cfg['units']:
   if u['kind']=='practice':u['status']='랩·가이드 내용·순서 정합 확정 · 촬영 발화·전환·속도 튜닝 가능 · 실행 미수행'
  # 노트 갱신된 해시 보존
  cfg['pptx_sha256']=sha(root/f'산출물/교재/PPTX/{course}_온라인/{course}_{day:02}일차.pptx')
  H.write(folder/'구성.json',json.dumps(cfg,ensure_ascii=False,indent=2)+'\n')
  namespace={'__name__':'document_merge'};exec(compile(merge_source.replace('실전반',course),'<document-merge>','exec'),namespace);namespace['build'](folder)
  merged=folder.parent/f'{course}_{day:02}일차_대본.md';H.write(merged,re.sub(r'\]\((\d{2}_[^/)]+\.md)\)',rf']({day:02}회차/\1)',merged.read_text('utf8')))
  # 구성표의 재현 명령은 이번 공통 생성기로 통일한다.
  configtable=folder/'구성표.md';s=configtable.read_text('utf8');s=re.sub(r'재생성: `[^`]+`',f'재생성: 실전반 최신 루트에서 `python 만들기/labs/online/revision20261019/sync.py` (두 과정의 현재 분할 원본과 랩 자료 사용)',s);H.write(configtable,s)
  if theory_changed:
   dest=folder.parent/f'{course}_{day:02}일차_대본.pdf';H.pdf((folder.parent/f'낭독본/{course}_{day:02}일차_낭독본.md').read_text('utf8'),dest);pdfs.append(str(dest))
   duplicate=folder.parent/'PDF'/dest.name
   if duplicate.exists():shutil.copy2(dest,duplicate)
  index=[f'# {course} {day}회차 실습 자료\n\n온라인은 강사가 직접 진행한다. HTML은 제작 참고이며 학생에게 가이드를 제공하는 전제가 아니다. 실제 실행·캡처 미수행. 분량은 낭독 추정과 별도이며 목표 시간을 채우지 않는다.\n']
  for src,lab in zip(labscripts,labdirs):
   text=src.read_text('utf8');H.write(lab/'강사대본.md',text);H.write(folder/'낭독본'/src.name,H.speech(text));H.pdf(H.speech(text),lab/'강사대본.pdf');pdfs.append(str(lab/'강사대본.pdf'))
   files=[f for f in lab.rglob('*') if f.is_file() and f.suffix not in ['.html','.pdf','.zip'] and f.name not in ['강사대본.md'] and '__pycache__' not in f.parts and f.suffix!='.pyc']
   links=''.join('<li><a href="'+html.escape(f.relative_to(lab).as_posix(),quote=True)+'">'+html.escape(f.relative_to(lab).as_posix())+'</a></li>' for f in sorted(files))
   blocks=[]
   for para in text.strip().split('\n\n'):
    tag='h1' if para.startswith('# ') else 'h2' if para.startswith('## ') else 'aside' if para.startswith('>') else 'p'
    blocks.append('<'+tag+'>'+html.escape(re.sub(r'^(?:#{1,2} |> ?)', '',para))+'</'+tag+'>')
   out='<!doctype html><html lang="ko"><meta charset="utf-8"><title>'+html.escape(lab.name)+'</title><style>body{font:17px/1.8 "Malgun Gothic",sans-serif;max-width:980px;margin:40px auto;padding:0 24px;color:#22303e}h1{font-size:28px}h2{margin-top:32px;font-size:23px}aside{background:#f0f4f7;padding:14px}p,aside{white-space:pre-wrap}</style><p>제작 참고용 · 학생 가이드 제공 전제 없음 · 실제 실행 및 이미지 촬영 미수행</p><details><summary>작업 자료</summary><ul>'+links+'</ul></details>'+''.join(blocks)+'</html>'
   hfiles=list(lab.glob('*.html')) or [lab/'안내.html']
   for hp in hfiles:H.write(hp,out)
   zpaths=[lab.with_suffix('.zip'),guide.parent/'다운로드'/(lab.name+'.zip')];zpaths=[p for p in zpaths if p.exists()] or [lab.with_suffix('.zip')]
   for zp in zpaths:
    with zipfile.ZipFile(zp) as z:
     names=[n for n in z.namelist() if not n.endswith('/')];prefix=lab.name+'/' if names and all(n.startswith(lab.name+'/') for n in names) else ''
    with zipfile.ZipFile(zp,'w',zipfile.ZIP_DEFLATED) as z:
     for f in sorted(lab.rglob('*')):
      if f.is_file() and '__pycache__' not in f.parts and f.suffix!='.pyc':z.write(f,prefix+f.relative_to(lab).as_posix())
   index.append(f'## {src.stem.split("_실습_")[-1]}\n\n[ZIP]({zpaths[0].relative_to(guide.parent).as_posix()}) · [제작 참고]({hfiles[0].relative_to(guide.parent).as_posix()}) · [대본 PDF]({lab.name}/강사대본.pdf)\n')
   pairs.append(dict(script=str(src),lab=str(lab),zips=list(map(str,zpaths))))
  H.write(guide,'\n'.join(index))
  spoken='\n\n'.join(H.speech(p.read_text('utf8')) for p in labscripts);H.write(folder/'실습_낭독합본.md',spoken);dest=folder/f'{course}_{day:02}일차_실습대본.pdf';H.pdf(spoken,dest);pdfs.append(str(dest))
  # 기존 별도 실습 PDF가 다른 이름이면 바이트 동기화한다.
  for other in folder.glob('*.pdf'):
   if other!=dest and '실습' in other.name:shutil.copy2(dest,other)
  rows.append(dict(course=course,day=day,labs=len(labscripts),slides=cfg['slide_count'],theory_changed=theory_changed))
  print(course,day,'synced',flush=True)
H.write(EV/'sync.json',json.dumps(dict(sessions=rows,pairs=pairs,pdfs=pdfs,pdf_checks=H.checks),ensure_ascii=False,indent=2))
print('completed',len(pairs),'labs',len(pdfs),'PDF originals')
