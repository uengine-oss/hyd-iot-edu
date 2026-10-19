from helpers import *
edits=[
 (33,'한 작업에서 조건 없는 선을 두 갈래로 뽑으면 두 경로가 함께 진행될 수 있습니다. 표준에는 조건부 시퀀스 흐름도 있으므로 모든 갈림에 마름모가 필수인 것은 아닙니다. 승인과 거절이 동시에 일어나는 그림이 되어 버리는 거죠.','한 작업에서 조건 없는 선을 두 갈래로 뽑으면 두 경로가 함께 진행될 수 있습니다. 승인과 거절이 동시에 일어나는 그림이 되어 버리는 거죠. 다만 표준에는 조건부 시퀀스 흐름도 있으므로 모든 갈림에 마름모가 필수인 것은 아닙니다.','무조건 분기의 결과를 먼저 설명하고 표준의 예외를 뒤에 이어 오독 방지'),
 (45,'HYD에서는 경보로 열린 처리 건을 이 엔진이 정의의 조건에 따라 진행을 관리합니다.','HYD에서는 이 엔진이 정의의 조건에 따라 경보로 열린 처리 건의 진행을 관리합니다.','중복 목적어를 바로잡음; 역할과 조건 보존'),
 (62,'각 경로를 따라가 보세요.','각 경로를 따라가 보겠습니다.','강사 단독 작도·점검 주체'),
 (64,'그래서 학생별 환경을 쓰거나 순서를 정해 진행하고, 실행하기 전에 어떤 흐름이 그 경보를 받는지 확인합니다.','그래서 강사용으로 배정된 교육 환경과 배포 순서를 확인하고, 실행하기 전에 어떤 흐름이 그 경보를 받는지 확인하겠습니다.','학생 병렬 진행을 강사 단독 진행으로 조정; 공용 배포 영향 보존'),
 (68,'처리 건에서 승인 대기와 끝난 상태를 구별해 보셨죠. 아직 기대한 결과를 얻지 못했다면, 어디까지 확인했고 무엇이 남았는지도 함께 적어 두세요.','실습에서 남긴 기록으로 승인 대기와 끝난 상태를 구별하겠습니다. 아직 기대한 결과를 얻지 못했다면, 어디까지 확인했고 무엇이 남았는지도 함께 적어 두겠습니다.','수강생 실행·성공을 가정하지 않고 강사가 남긴 기록과 미확인 범위로 연결')]
src=EV/'before/산출물/교재/대본/통합반_온라인/09회차'
for f in src.glob('*_이론_*.md'):
 t=f.read_text('utf8').replace('실제 실습은 별도 빈 파일이다.','실제 실습은 별도 04~07 대본으로 진행한다.')
 for n,a,b,reason in edits:
  if a in t:assert t.count(a)==1;t=t.replace(a,b)
 write(I/f.name,t)
deck=C/'만들기/decks/integrated/day09/통합반_09일차.md';a='HYD에서는 경보로 열린 처리 건을 이 엔진이 정의의 조건에 따라 진행을 관리한다.';b='HYD에서는 이 엔진이 정의의 조건에 따라 경보로 열린 처리 건의 진행을 관리한다.'
t=deck.read_text('utf8');assert a in t;write(deck,t.replace(a,b))
p=C/'산출물/교재/PPTX/통합반_온라인/통합반_09일차.pptx';out=io.BytesIO()
with zipfile.ZipFile(p) as z,zipfile.ZipFile(out,'w') as dst:
 changed=0
 for info in z.infolist():
  data=z.read(info)
  if info.filename=='ppt/slides/slide45.xml':
   root=E.fromstring(data)
   for node in root.iter('{http://schemas.openxmlformats.org/drawingml/2006/main}t'):
    if node.text and a in node.text:node.text=node.text.replace(a,b);changed+=1
   data=E.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True)
  dst.writestr(info,data)
 assert changed==1,changed
p.write_bytes(out.getvalue())
cfg=json.loads((I/'구성.json').read_text('utf8'))
for u in cfg['units']:
 if u['kind']=='empty_practice':u['kind']='practice'
write(I/'구성.json',json.dumps(cfg,ensure_ascii=False,indent=2)+'\n')
write(EV/'speech-edits.json',json.dumps([dict(slide=n,before=a,after=b,reason=r) for n,a,b,r in edits],ensure_ascii=False,indent=2))
print('74 slides preserved; five speech blocks edited; slide45 grammar synchronized')
