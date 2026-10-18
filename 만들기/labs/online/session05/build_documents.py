"""배포 문서와 입력자료 생성. 원본 학생 코드는 복사·정적 검사만 한다."""
from helpers import *
from labs import namesI,namesP,blank
raw=C/'산출물/실습/통합반_오프라인';docs=raw/'04회차_실습2_지식_추출/코드/문서';source_manifest=[]
def copy(src,dest):
 dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest);source_manifest.append(dict(source=str(src),destination=str(dest),sha256=hashlib.sha256(src.read_bytes()).hexdigest()))
def copytree(src,dest):
 for f in src.rglob('*'):
  if f.is_file() and '__pycache__' not in f.parts:copy(f,dest/f.relative_to(src))
for root,folder,course,names,numbers in [(C,I,'통합반',namesI,[3,4,5,6]),(D,P,'실전반',namesP,[2,3,5,7])]:
 index=[f'# {course} 5회차 실습 자료\n\nZIP을 다운로드·압축 해제하고 VS Code에서 코드 폴더를 연다. 실제 실행·캡처는 미수행이다. 결과 기록은 수업에서 작성한다.\n']
 for idx,name in enumerate(names,1):
  lab=root/f'산출물/실습/{course}_온라인/05일차_실습{idx}_{name}';code=lab/'코드';code.mkdir(parents=True,exist_ok=True)
  text=(folder/f'{numbers[idx-1]:02}_실습_{name}.md').read_text('utf8');write(lab/'강사대본.md',text)
  write(code/'README.md',f'# {name}\n\n안내.html과 강사대본.md를 따른다. source는 제공 입력, input은 앞 단계 결과를 직접 넣을 자리, output은 수업에서 직접 만든 결과를 저장할 자리다. 빈 폴더나 기록 양식은 완료 결과가 아니다. 인증값을 자료에 넣지 않는다.\n')
  write(code/'input/README.md','대본에 지정한 앞 단계 결과를 복사하고 판본·ID·스키마를 확인한다.\n');write(code/'output/README.md','수업에서 직접 작성한 결과를 저장한다. 실행 결과는 제공하지 않는다.\n')
  write(code/'review.md',blank+'\n| 대상 | 원문·입력 근거 | 예상 | 실제 | 수정·재확인 | 미확인 |\n|---|---|---|---|---|---|\n| | | | | | |\n')
  if name=='업무에이전트구성':write(code/'design.md','# 에이전트 설정 기록\n\n## 목표와 역할\n\n## 지침과 멈춤 조건\n\n## 서버와 허용 도구\n\n## 기본 제공 항목과 변경점\n')
  if name=='원인추론과점검계획':
   src=raw/'05회차_실습2_원인_추론_에이전트/코드'
   copytree(src/'ontology',code/'source/ontology');copytree(src/'cases',code/'source/cases');copytree(docs,code/'source/manuals')
   write(code/'expected.md',blank+'\n| 사례 | 후보 ID | 필요한 증거 | 예상 상태 | 추가 점검 | 실제 결과 |\n|---|---|---|---|---|---|\n| | | | | | |\n')
  if name=='품질대응카드':
   src=raw/'05회차_실습4_품질_대응_카드/코드'
   for sub in ['접수','기준','자료']:copytree(src/sub,code/'source'/sub)
  if name=='센서이상시각화':
   write(code/'source/데이터_설명.md','# 교육용 가상 입력\n\n이 CSV는 자료 제작 시 작성한 가상 입력이다. 실제 측정·조회·실행 결과가 아니다. 시간대는 +09:00, 온도 TS1은 degC, 압력 PS1은 bar이다. 09:03 온도는 누락이다. 연속 유효 관측의 상승과 누락 처리·단위 분리를 연습하며, 경보 판정·원인 추론의 증거로 쓰지 않는다. 실제 교육 환경 조회 자료를 사용하면 별도 input에 저장하고 기간·태그·시간대·출처를 기록한다.\n')
   rows=['timestamp,equipment,tag,value,unit']
   for m,(temp,pressure) in enumerate([(40,100),(42,102),(45,101),(None,104),(49,107),(46,103)]):
    for tag,value,unit in [('TS1',temp,'degC'),('PS1',pressure,'bar')]:rows.append(f'2026-10-01T09:{m:02}:00+09:00,HYD-TRAIN,{tag},{"" if value is None else value},{unit}')
   write(code/'source/sensor_training.csv','\n'.join(rows)+'\n')
  if name in ['확인질문과재처리','명세에따른요구사항추가','기존기능과추가기능검증']:
   src=raw/'07회차_실습3_명세로_요구사항_추가/코드'
   for sub in ['입력','사람','온톨로지']:copytree(src/sub,code/'source'/sub)
  if name=='명세에따른요구사항추가':
   copytree(src/'사례',code/'source/기존_비교기록/사례')
   copy(src/'검증/변경_전/요청_처리.json',code/'source/기존_비교기록/검증/변경_전/요청_처리.json')
   copy(src/'결과/점검_계획.json',code/'source/기존_비교기록/결과/점검_계획.json')
   copy(src/'검증/견주기.py',code/'source/기존_비교기록/검증/견주기.py')
   write(code/'source/기존_비교기록/README.md','# 제공된 기존 비교 기록\n\n원본 교재에 있던 과거 비교 사례다. 이번 제작에서 실행하거나 재현하지 않았다. 사례/읽는_법.md를 따라 기존 출력·변경 출력·바뀐 파일을 읽기만 한다. 이번 프로젝트의 성공·실패 증거로 사용하지 않는다.\n')
   write(code/'spec.md','# 명세 작성\n\n## 목표\n\n## 입력\n\n## 출력 계약\n\n## 금지 조건\n\n## 긴급 조건과 유효성\n\n## 수용 기준\n')
  if name=='기존기능과추가기능검증':write(code/'scenarios.md','# 시나리오 작성\n\n| 사례 | Given | When | Then | 명세 근거 |\n|---|---|---|---|---|\n| 일반 | | | | |\n| 긴급 | | | | |\n| 누락 | | | | |\n| 거절 | | | | |\n| 경계 | | | | |\n')
  files=sorted(f for f in code.rglob('*') if f.is_file());links=''.join('<li><a href="'+html.escape(f.relative_to(lab).as_posix(),quote=True)+'">'+html.escape(f.relative_to(lab).as_posix())+'</a></li>' for f in files)
  css='body{font:17px/1.8 "Malgun Gothic",sans-serif;max-width:980px;margin:40px auto;padding:0 24px;color:#22303e}h1{font-size:28px}h2{margin-top:32px;font-size:23px}aside{background:#f0f4f7;padding:14px}p,aside{white-space:pre-wrap}'
  segments=[]
  for para in text.strip().split('\n\n'):
   tag='h1' if para.startswith('# ') else 'h2' if para.startswith('## ') else 'aside' if para.startswith('>') else 'p'
   segments.append('<'+tag+'>'+html.escape(re.sub(r'^(?:#{1,2} |> ?)', '',para))+'</'+tag+'>')
  write(lab/'안내.html','<!doctype html><html lang="ko"><meta charset="utf-8"><title>'+name+'</title><style>'+css+'</style><h2>작업 자료</h2><ul>'+links+'</ul>'+''.join(segments)+'</html>')
  reading=speech(text);write(folder/'낭독본'/f'{numbers[idx-1]:02}_실습_{name}.md',reading);pdf(reading,lab/'강사대본.pdf')
  with zipfile.ZipFile(lab.with_suffix('.zip'),'w',zipfile.ZIP_DEFLATED) as z:
   for f in sorted(lab.rglob('*')):
    if f.is_file():z.write(f,f.relative_to(lab).as_posix())
  index.append(f'## 실습 {idx} — {name}\n\n[자료 ZIP]({lab.name}.zip) · [진행 안내]({lab.name}/안내.html) · [대본 PDF]({lab.name}/강사대본.pdf)\n')
 write(root/f'산출물/실습/{course}_온라인/05회차_실습_안내.md','\n'.join(index))
patch_notes();merge(C,I,False);merge(D,P,True)
for folder,course in [(I,'통합반'),(P,'실전반')]:
 pdf((folder.parent/'낭독본'/f'{course}_05일차_낭독본.md').read_text('utf8'),folder.parent/f'{course}_05일차_대본.pdf')
 alltext='\n\n'.join(speech(f.read_text('utf8')) for f in sorted(folder.glob('*_실습_*.md')));write(folder/'실습_낭독합본.md',alltext);pdf(alltext,folder/f'{course}_05일차_실습대본.pdf')
write(EV/'pdf-check.json',json.dumps(checks,ensure_ascii=False,indent=2));write(EV/'source-materials.json',json.dumps(source_manifest,ensure_ascii=False,indent=2))
print('documents complete',len(checks),'PDFs; no lab execution')
