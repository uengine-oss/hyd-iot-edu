from helpers import *
IP=C/'산출물/교재/대본/통합반_온라인/11회차';PP=D/'산출물/교재/대본/실전반_온라인/08회차';edits=[]
def change(p,a,b,reason):
 s=p.read_text('utf8');assert a in s,(p,a);write(p,s.replace(a,b));edits.append(dict(path=str(p),before=a,after=b,reason=reason))
for a,b in [
 ('실제 실습은 별도 빈 파일이다.','실습 진행 대본은 별도로 관리한다.'),
 ('각자의 작은 업무로 직접 만들어 봅니다.','강사가 고른 작은 업무로 직접 만들어 봅니다.'),
 ('각자에게 친숙한 작은 업무 하나를 골라서','친숙한 작은 업무 하나를 제가 골라서'),
 ('다음 시간에는 이 추천안이','이어서 이 추천안이'),
 ('각자의 업무 위에서요.','강사가 고른 회의 준비 업무 위에서요.'),
 ('먼저 각자에게 친숙한 작은 업무 하나를 고르게 돼요.','먼저 강사가 친숙한 작은 업무 하나를 고릅니다.'),
 ('뒤의 실습에서는 이 명세부터 적습니다.','실제 실습에서는 이 명세부터 적겠습니다.'),
 ('별도 빈 파일이며','별도 진행 대본이며'),
 ('실습과 시연을 마친 뒤 다시 모였습니다.','실습과 시연에서 남긴 기록으로 돌아왔습니다.'),
 ('학습 노트에는 완성한 결과뿐 아니라 아직 확인하지 못한 것도 구분해 두세요.','학습 노트에는 완성한 결과와 아직 확인하지 못한 것을 구분해 두겠습니다.')]:
 for p in IP.glob('*_이론_*.md'):
  if a in p.read_text('utf8'):change(p,a,b,'실전반8과 강사 직접 수행·학습 시점·미확인 구분 정합성')
for folder in [IP,PP]:
 p=folder/'02_이론_제안과업무완료.md'
 change(p,'정상 종료로 닫혔습니다. 승인만으로 정상 종료가 보장되는 건 아니에요. 회복 기준을 충족하지 못하면 미달 결과를 남기는 다른 경로로 갑니다. 결과 보고는 정상이고요.','정상 종료로 닫혔고 결과 보고도 정상이었습니다. 승인만으로 정상 종료가 보장되는 건 아니에요. 회복 기준을 충족하지 못하면 미달 결과를 남기는 다른 경로로 갑니다.','정상 사례와 미달 예외 뒤의 결과 보고 문장을 올바른 대상에 연결')
for name,a,b in [
 ('04_실습_지식구조.md','VS Code에서 앞 실습의 작업 공간을 열겠습니다. 명세와 source/docs를 보존하고, 실제 작성 파일은 output에 둡니다.','VS Code에서 이번 코드 폴더를 열고, 앞 실습의 spec.md·request.md와 출처 목록을 input에 복사하겠습니다. 이번 ZIP의 빈 양식으로 앞에서 작성한 명세를 덮어쓰지 않습니다. source/docs를 앞 명세에서 읽은 문서와 대조하고 실제 작성 파일은 output에 둡니다.'),
 ('04_실습_지식구조.md','수업에서 파일을 students의 전용 작업 폴더로 옮기고','수업에서 output에 작성한 schema.json·graph.json·questions.cypher와 source/templates/load_graph.py를 students의 전용 작업 폴더로 복사하고'),
 ('05_실습_제안에이전트.md','VS Code에서 앞 단계의 명세·스키마·인스턴스·조회 기록이 있는 작업 공간을 열겠습니다.','VS Code에서 이번 코드 폴더를 열고 앞 단계의 명세·스키마·인스턴스·조회 기록을 input에 복사하겠습니다. 앞에서 완성한 파일은 보존하고 이번 빈 양식으로 덮어쓰지 않습니다.'),
 ('06_실습_흐름실행.md','VS Code에서 앞 실습의 같은 프로젝트를 열겠습니다. 에이전트 ID와 출력 계약을 input에 가져옵니다.','VS Code에서 이번 코드 폴더를 열고 앞 실습의 명세·에이전트 정의·ID·출력 계약을 input에 가져옵니다. 같은 업무의 이어지는 판본으로 관리하고 앞 결과는 보존합니다.')]:
 change(PP/name,a,b,'ZIP별 자료 위치와 앞 결과 이어 쓰기를 구체화하고 빈 양식 덮어쓰기 방지')
for p in PP.glob('*_실습_*.md'):
 dest=IP/p.name;assert not dest.read_text('utf8').strip();s=p.read_text('utf8').replace('실전반 8회차','통합반 11회차');write(dest,s);edits.append(dict(path=str(dest),before='',after=s,reason='동일 배정의 여섯 실습을 통합반11에 신규 작성'))
cfg=json.loads((IP/'구성.json').read_text('utf8'))
for u in cfg['units']:
 if '실습' in u['file']:u['kind']='practice';u['status']='문서 작성·실행 및 캡처 미검증'
cfg['playback']='이론① 1~21장 → 이론② 22~57장(실습·시연 여섯 묶음 안내 포함) → 실제 실습03~08 → 이론② 58~64장 재개(복습·퀴즈·과정 마무리).'
write(IP/'구성.json',json.dumps(cfg,ensure_ascii=False,indent=2)+'\n')
for root,course,kind,day in [(C,'통합반','integrated',11),(D,'실전반','practical',8)]:
 a='이 실습을 마치면 내 에이전트를 단계로 둔 흐름이 등록되고, 그 흐름으로 열린 처리 건의 기록이 남는다.';b='준비된 연결로 흐름을 등록·실행하고, 처리 건의 실제 결과와 미확인 범위를 구분해 기록한다.'
 change(root/f'만들기/decks/{kind}/day{day:02}/{course}_{day:02}일차.md',a,b,'화면48도 실제 연결·실행 확인을 조건으로 명시')
 p=root/f'산출물/교재/PPTX/{course}_온라인/{course}_{day:02}일차.pptx';out=io.BytesIO()
 with zipfile.ZipFile(p) as z:
  r=E.fromstring(z.read('ppt/slides/slide48.xml'));found=0
  for e in r.iter('{http://schemas.openxmlformats.org/drawingml/2006/main}t'):
   if e.text==a:e.text=b;found+=1
  assert found==1
  with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as w:
   for item in z.infolist():w.writestr(item,E.tostring(r,xml_declaration=True,encoding='UTF-8',standalone=True) if item.filename=='ppt/slides/slide48.xml' else z.read(item))
 p.write_bytes(out.getvalue())
write(EV/'finish11-edits.json',json.dumps(edits,ensure_ascii=False,indent=2))
copies=[]
for root,course,day,folder,practical in [(C,'통합반',11,IP,False),(D,'실전반',8,PP,True)]:
 patch_notes(folder,64,root/f'만들기/decks/{"practical" if practical else "integrated"}/day{day:02}/{course}_{day:02}일차.md',root/f'산출물/교재/PPTX/{course}_온라인/{course}_{day:02}일차.pptx')
 index=[f'# {course} {day}회차 실습 자료\n\n문서·정적 검증 범위이며 실제 실습·실행·캡처는 미수행이다. 결과는 수업에서 직접 확인하고 기록한다.\n']
 for idx,src in enumerate(sorted(folder.glob('*_실습_*.md')),1):
  name=src.stem.split('_실습_')[1];lab=root/f'산출물/실습/{course}_온라인/{day:02}일차_실습{idx}_{name}'
  if not practical:
   original=D/f'산출물/실습/실전반_온라인/08일차_실습{idx}_{name}';assert not lab.exists(),lab
   for sub in ['코드','reference']:
    for f in (original/sub).rglob('*'):
     if f.is_file():
      dest=lab/f.relative_to(original);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dest);copies.append(dict(source=str(f),destination=str(dest),sha256=hashlib.sha256(f.read_bytes()).hexdigest()))
  text=src.read_text('utf8');write(lab/'강사대본.md',text);pdf(speech(text),lab/'강사대본.pdf')
  files=[f for sub in ['코드','reference'] for f in (lab/sub).rglob('*') if f.is_file()]
  links=''.join('<li><a href="'+html.escape(f.relative_to(lab).as_posix(),quote=True)+'">'+html.escape(f.relative_to(lab).as_posix())+'</a></li>' for f in sorted(files))
  segments=[]
  for para in text.strip().split('\n\n'):
   tag='h1' if para.startswith('# ') else 'h2' if para.startswith('## ') else 'aside' if para.startswith('>') else 'p'
   segments.append('<'+tag+'>'+html.escape(re.sub(r'^(?:#{1,2} |> ?)', '',para))+'</'+tag+'>')
  write(lab/'안내.html','<!doctype html><html lang="ko"><meta charset="utf-8"><title>'+name+'</title><style>body{font:17px/1.8 "Malgun Gothic",sans-serif;max-width:980px;margin:40px auto;padding:0 24px;color:#22303e}h1{font-size:28px}h2{margin-top:32px;font-size:23px}aside{background:#f0f4f7;padding:14px}p,aside{white-space:pre-wrap}</style><h2>작업 자료</h2><ul>'+links+'</ul>'+''.join(segments)+'</html>')
  with zipfile.ZipFile(lab.with_suffix('.zip'),'w',zipfile.ZIP_DEFLATED) as z:
   for f in sorted(lab.rglob('*')):
    if f.is_file():z.write(f,f.relative_to(lab).as_posix())
  index.append(f'## 실습 {idx} — {name}\n\n[자료 ZIP]({lab.name}.zip) · [진행 안내]({lab.name}/안내.html) · [대본 PDF]({lab.name}/강사대본.pdf)\n')
 write(root/f'산출물/실습/{course}_온라인/{day:02}회차_실습_안내.md','\n'.join(index))
 merge(root,folder,practical)
 merged=folder.parent/f'{course}_{day:02}일차_대본.md';write(merged,re.sub(r'\]\((\d{2}_[^/)]+\.md)\)',rf']({day:02}회차/\1)',merged.read_text('utf8')))
 pdf((folder.parent/f'낭독본/{course}_{day:02}일차_낭독본.md').read_text('utf8'),folder.parent/f'{course}_{day:02}일차_대본.pdf')
 alltext='\n\n'.join(speech(f.read_text('utf8')) for f in sorted(folder.glob('*_실습_*.md')));write(folder/'실습_낭독합본.md',alltext);pdf(alltext,folder/f'{course}_{day:02}일차_실습대본.pdf')
write(EV/'finish11-pdf-check.json',json.dumps(checks,ensure_ascii=False,indent=2));write(EV/'finish11-copies.json',json.dumps(copies,ensure_ascii=False,indent=2))
print('통합반11·실전반8 문서 생성 완료. 정적 검사·PDF 검토 이어서, 실제 실행 없음.')
