"""통합반10 및 실전반7의 문서만 동기화. 시작 근거는 읽기 전용."""
from helpers import *
IP=C/'산출물/교재/대본/통합반_온라인/10회차';PP=D/'산출물/교재/대본/실전반_온라인/07회차'
edits=[]
def change(p,a,b,reason):
 s=p.read_text('utf8')
 if a not in s:
  assert b in s,(p,a)
  return
 write(p,s.replace(a,b));edits.append(dict(path=str(p),before=a,after=b,reason=reason))
# 이미 검토한 실전반의 조건 설명을 원본 이론에도 반영한다. 본론은 삭제하지 않는다.
for a,b in [
 ('실제 실습은 별도 빈 파일이다.','실습 진행 대본은 별도로 관리한다.'),
 ('별도 빈 실습 파일','별도 실습 대본'),
 ('구별하세요.','구별하겠습니다.'),
 ('이 실습을 마치면 정기 점검의 처리 건 하나가 끝까지 간 기록으로 남고,','이 실습에서는 정기 점검의 승인·거절 처리 기록을 남기고,'),
 ('가용 재고가 1개에서 7개로 올라가고, 결과 보고가 입고 완료로 남아야 해요.','제시된 시작 조건과 6개 발주안을 그대로 사용했다면 가용 재고가 1개에서 7개로 올라가고, 결과 보고가 입고 완료로 남아야 해요. 시작 재고나 승인 수량이 달랐다면 그 값으로 기대 재고를 계산해 실제 입고 기록과 대조합니다.'),
 ('직접 그린 두 프로세스가 모두 처리 건을 끝까지 보낸 셈이고,','직접 그린 두 프로세스의 진행 결과와 미확인이 기록으로 남고,'),
 ('다음 시간부터 정기 점검 작도와 실행,','이제 정기 점검 작도와 실행,'),
 ('여러분이 보낸 것과 같은 모양으로','강사가 확인한 기록과 비교할 수 있도록'),
 ('여러분의 처리 건과 다른 건 그래서예요.','실습의 처리 건과 다른 건 그래서예요.')]:
 for p in IP.glob('*_이론_*.md'):
  if a in p.read_text('utf8'):change(p,a,b,'실전반7과 조건·미확인·진행 표현 정합성')
for folder in [IP,PP]:
 for a,b,reason in [
 ('학생별 환경을 쓰거나 진행 순서와 되돌릴 시점을 운영자와 맞춥니다.','강사에게 배정된 환경을 확인하고 진행 순서와 되돌릴 시점을 운영자와 맞춥니다.','강사 직접 수행과 공용 환경 영향 보존'),
 ('여러분의 실행은 조건과 응답 시점에 따라 달라질 수 있어요.','수업에서 확인할 실행은 조건과 응답 시점에 따라 달라질 수 있어요.','사전 수집 예시와 수업 결과 구분'),
 ('기록을 놓고 비교해 보세요.','기록을 놓고 비교해 보겠습니다.','강사 직접 비교'),
 ('여러분이 화면에서 직접 연결한 흐름이라면','강사가 화면에서 직접 연결한 흐름이라면','강사 직접 수행'),
 ('각자의 작은 업무 주제에 적용해서','강사가 정한 작은 업무 주제에 적용해서','개별 학생 수행을 가정하지 않는 연결')]:
  for p in folder.glob('*_이론_*.md'):
   if a in p.read_text('utf8'):change(p,a,b,reason)
# 먼저 실전반 랩을 보완한 뒤, 같은 배정의 통합반에 회차·앞 파일을 맞춘다.
labchanges={
 '02_실습_정기점검작도.md':[
 ('앞 회차에 만든 cooling.bpmn을 input에 복사해 보존하고,','앞 회차에서 마지막으로 저장·내보낸 냉각 대응 BPMN(cooling-draft.bpmn)을 input에 복사해 판본과 요소 대응표를 함께 보존하고,'),
 ('output/pm-planning.bpmn으로 저장하고','어긋난 연결이나 종류가 있으면 해당 항목을 고친 뒤 승인·거절·지연 경로를 다시 따라가겠습니다. output/pm-planning.bpmn으로 저장하고')],
 '03_실습_정기점검실행.md':[
 ('현재 포털의 설정 폼을 우선 사용하며','내 그림에 맞춘 연결 값은 output/pm-planning.mapping.json에도 기록하고 포털 설정과 대조하겠습니다. 현재 포털의 설정 폼을 우선 사용하며'),
 ('권한 있는 역할로 승인하겠습니다. 승인 기록,','현재 근거와 권한·정비 조건이 충족될 때 권한 있는 역할로 승인하겠습니다. 부족하면 보류 사유를 남기고 승인한 경우에만 다음을 확인합니다. 승인 기록,'),
 ('별도로 준비된 동등한 교육용 건에서는 사유를 적어 거절하겠습니다.','거절 경로를 확인할 별도 교육용 건은 앞 건의 오더와 자원 예약 변화가 섞이지 않도록 시작 상태와 대상을 먼저 확인합니다. 업무상 거절 사유가 있는 건에서 그 근거를 적어 거절하겠습니다. 조건을 마련하지 못하면 이 경로는 미확인으로 남기며 정상 설정을 훼손하지 않습니다.'),
 ('정의·판본·경보·처리 건과 승인/거절,','설정과 기록이 다르면 실제 문제의 위치와 사유를 찾아 필요한 항목만 수정하고 저장·재검사하겠습니다. 이미 배포한 정의는 이전 결과를 보존하고 새 판본과 별도 사건으로 재확인합니다. 오더가 이미 만들어졌으면 중복 생성하지 않도록 남은 공지·보고부터 확인합니다.\n\nBPMN·매핑·요소 대응표를 저장하고 다시 열어 포털의 정의·판본과 맞추겠습니다. 정의·판본·경보·처리 건과 승인/거절,')],
 '04_실습_재고보충작도.md':[
 ('element-map.md에 내 요소 ID를 적고','실제 누락이나 잘못된 선이 있으면 고치고 승인·거절·지연의 세 경로를 다시 확인합니다. element-map.md에 내 요소 ID를 적고')],
 '05_실습_재고보충실행.md':[
 ('내 요소 ID에 맞춰 설정을 저장하고','내 요소 ID에 맞춘 설정을 output/spare-purchase.mapping.json과 포털에 저장하고'),
 ('권한 있는 역할로 승인한 뒤 발주 번호와 수량,','공급사 승인 여부와 금액별 전결 범위, 품질 경고까지 확인하겠습니다. 현재 역할의 권한과 업무 조건이 충족될 때 승인하고, 전결 범위를 넘거나 근거가 부족하면 필요한 승인 절차 또는 보류를 기록합니다. 승인한 경우에는 발주 번호와 수량,'),
 ('별도로 준비된 동등한 교육용 건에서 거절 사유를 남기겠습니다.','거절 경로를 확인할 별도 교육용 건은 앞 건의 발주·입고로 바뀐 재고와 섞이지 않도록 시작 상태와 대상을 먼저 확인합니다. 업무상 거절 사유가 있는 건에서 그 근거를 남기겠습니다. 조건을 마련하지 못하면 해당 경로는 미확인으로 두겠습니다.'),
 ('시작 값, 승인 내용, 발주·입고·처리 건 ID와 판본,','기대와 다른 기록은 실제 입력·매핑·승인 내용과 연결해 원인을 찾겠습니다. 고칠 항목이 있으면 이전 결과를 보존하고 설정 수정·저장·재검사를 거쳐 새 판본과 별도 사건으로 재확인합니다. 이미 생성된 발주를 다시 만드는 방식으로 입고 실패를 고치지 않겠습니다.\n\nBPMN·매핑·요소 대응표를 저장한 뒤 다시 열어 포털 설정과 맞추겠습니다. 시작 값, 승인 내용, 발주·입고·처리 건 ID와 판본,')]
}
for name,changes in labchanges.items():
 for a,b in changes:change(PP/name,a,b,'앞 결과·승인 조건·실제 문제 수정·재확인·저장 재열기 보완')
 text=(PP/name).read_text('utf8').replace('실전반 7회차','통합반 10회차').replace('냉각 대응 BPMN(cooling-draft.bpmn)','냉각 대응 BPMN(cooling.bpmn)')
 assert not (IP/name).read_text('utf8').strip(),'빈 통합반 랩만 작성한다'
 write(IP/name,text);edits.append(dict(path=str(IP/name),before='',after=text,reason='동일 배정 실습을 통합반 앞 산출물·회차에 맞춰 신규 작성'))
cfg=json.loads((IP/'구성.json').read_text('utf8'))
for u in cfg['units']:
 if '실습' in u['file']:u['kind']='practice';u['status']='문서 작성·실행 및 캡처 미검증'
cfg['playback']='1~37장 → 실습02~05 → 38~61장 전체 흐름·복습·용어·퀴즈.'
write(IP/'구성.json',json.dumps(cfg,ensure_ascii=False,indent=2)+'\n')
# 화면37은 실전반에서 이미 검토한 조건 명시를 동일하게 적용한다.
deck=C/'만들기/decks/integrated/day10/통합반_10일차.md'
change(deck,'가용 재고가 / 1개에서 7개로, / 결과 보고: 입고 완료','시작 값·승인 수량으로 대조 / 예: 가용 재고 1→7개 / 결과 보고: 입고 완료','예시 재고의 조건을 화면에도 명시')
p=C/'산출물/교재/PPTX/통합반_온라인/통합반_10일차.pptx';out=io.BytesIO()
with zipfile.ZipFile(p) as z:
 r=E.fromstring(z.read('ppt/slides/slide37.xml'));n=0
 for e in r.iter('{http://schemas.openxmlformats.org/drawingml/2006/main}t'):
  if e.text in ['가용 재고가','1개에서 7개로,']:e.text={'가용 재고가':'시작 값·승인 수량으로 대조','1개에서 7개로,':'예: 가용 재고 1→7개'}[e.text];n+=1
 assert n==2
 with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as w:
  for item in z.infolist():w.writestr(item,E.tostring(r,xml_declaration=True,encoding='UTF-8',standalone=True) if item.filename=='ppt/slides/slide37.xml' else z.read(item))
p.write_bytes(out.getvalue())
write(EV/'finish10-edits.json',json.dumps(edits,ensure_ascii=False,indent=2))
copies=[]
for root,course,day,folder,practical in [(C,'통합반',10,IP,False),(D,'실전반',7,PP,True)]:
 patch_notes(folder,61,root/f'만들기/decks/{"practical" if practical else "integrated"}/day{day:02}/{course}_{day:02}일차.md',root/f'산출물/교재/PPTX/{course}_온라인/{course}_{day:02}일차.pptx')
 index=[f'# {course} {day}회차 실습 자료\n\n자료의 문서·정적 검증만 완료했다. 실제 실습·실행·캡처는 미수행이며 결과는 수업에서 직접 기록한다.\n']
 for idx,src in enumerate(sorted(folder.glob('*_실습_*.md')),1):
  name=src.stem.split('_실습_')[1];lab=root/f'산출물/실습/{course}_온라인/{day:02}일차_실습{idx}_{name}'
  if not practical:
   original=D/f'산출물/실습/실전반_온라인/07일차_실습{idx}_{name}/코드'
   assert not lab.exists(),lab
   for f in original.rglob('*'):
    if f.is_file():
     dest=lab/'코드'/f.relative_to(original);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dest);copies.append(dict(source=str(f),destination=str(dest),sha256=hashlib.sha256(f.read_bytes()).hexdigest()))
  text=src.read_text('utf8');write(lab/'강사대본.md',text);pdf(speech(text),lab/'강사대본.pdf')
  links=''.join('<li><a href="'+html.escape(f.relative_to(lab).as_posix(),quote=True)+'">'+html.escape(f.relative_to(lab).as_posix())+'</a></li>' for f in sorted((lab/'코드').rglob('*')) if f.is_file())
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
write(EV/'finish10-pdf-check.json',json.dumps(checks,ensure_ascii=False,indent=2));write(EV/'finish10-copies.json',json.dumps(copies,ensure_ascii=False,indent=2))
print('통합반10·실전반7 문서 생성 완료, 문서 검증·렌더 확인은 다음 단계. 실습 실행 없음.')
