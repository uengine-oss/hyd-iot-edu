from helpers import *
from labs import names
source_manifest=[]
def copy(src,dst):
 dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);source_manifest.append(dict(source=str(src),destination=str(dst),sha256=hashlib.sha256(src.read_bytes()).hexdigest()))
def form(code,name,heads):write(code/name,'# '+name+'\n\n빈 작성 양식이다. 실제 작성·실행 결과는 수업에서 기록한다.\n\n'+'\n\n'.join('## '+h+'\n' for h in heads)+'\n')
index=['# 통합반 9회차 실습 자료\n\n직접 그린 승인 절차를 긴급 대응으로 확장하고, 시스템 연결과 실제 처리 기록 확인까지 이어 간다. 아래 ZIP의 reference는 제공 예제, 코드/input은 앞 실습 결과를 넣는 자리, output은 직접 작성한 결과를 저장하는 자리다. 이번 제작에서는 실제 실행하지 않았다.\n']
api='''# 실행 연결 계약과 확인 순서

이 문서는 저장소 it/process/procsvc/flows_api.py와 it/portal/www/flows.js를 정적으로 대조한 수업용 절차다. 이번 제작에서 API를 호출하지 않았다. 준비된 교육 환경의 주소·인증을 사용하고 화면에서 같은 항목을 입력할 수 있으면 API를 별도로 호출할 필요가 없다.

1. POST /api/flows/import: xml은 작성한 BPMN의 XML 문자열, file_name은 파일명, definition_id는 자신의 정의 ID, start_patterns는 ["COOLER_DEGRADATION"]이다. 기존 기준 정의를 덮어쓰지 않는다.
2. GET /api/flows/catalog로 부품·역할·에이전트 목록을 확인하고 GET /api/flows/{id}로 동일 초안의 parsed와 mapping을 읽는다. {id}는 실제 정의 ID로 바꾼다.
3. 참조 mapping의 tasks·flows·timers 키를 내 요소 ID에 대응시켜 output/mapping.json을 작성한다. agent는 실제 기존 에이전트 ID, role은 준비된 승인 역할과 대조한다. start.kind는 alert, start.patterns는 위 경보 배열이다.
4. PUT /api/flows/{id}/mapping의 본문은 {"mapping": <실제 JSON 객체>}이다. 꺾쇠 표기는 설명이며 그대로 전송하지 않는다. 파일 경로 문자열로 대신하지 않는다. GET으로 저장된 매핑을 다시 읽어 작성 파일과 대조한다.
5. POST /api/flows/{id}/check에 같은 mapping 객체를 보낸다. check.ok와 check.problems의 where·field·reason을 읽고 발견한 원인을 수정해 재검사한다. 이 검사 요청 자체는 매핑을 저장하지 않는다. 억지 오류 시연을 위해 정상 부품·조건을 삭제하지 않는다.
6. POST /api/flows/{id}/register에 같은 mapping 객체를 보내거나 이미 저장된 매핑을 사용한다. 반환된 definition_id·version과 deployed:false를 기록한다. 등록과 배포는 별개다. 포털에서 판본을 선택해 배포하고 경보 경로를 다시 읽는다. 실행·권한·실제 호출 성공은 후속 실습의 기록으로 확인한다.

매핑의 제공 예: 승인 조건 approval == "승인", 회복 조건 recovered == true, 반대편은 default:true, 승인 지연 타이머 PT10M. 보고의 {work_order.ref} 등은 결과 변수 참조다. 입력 누락이나 미실행을 성공 값으로 채우지 않는다. 공용 환경은 배정된 배포 범위를 확인하며 전체 사용자 배포를 초기화하는 기능을 이 절차에 포함하지 않는다.
'''
for idx,name in enumerate(names,1):
 lab=C/f'산출물/실습/통합반_온라인/09일차_실습{idx}_{name}';code=lab/'코드'
 write(code/'README.md',f'# {name}\n\n안내.html의 순서로 직접 작업한다. source는 제공 업무 입력, input은 앞 실습의 실제 결과, output은 이번에 작성할 결과다. 빈 양식은 실행 결과가 아니다. 코드 폴더 밖 reference는 비교용 참조이며 직접 만든 결과와 구별한다.\n')
 write(code/'.github/copilot-instructions.md','실제 명세·그림·설정 파일을 근거로 돕는다. 원문에서 확인하지 않은 ID·실행 결과·승인·회복·완료를 만들지 않는다. 앞 실습 결과와 제공 참조를 구별한다. 문제를 지적할 때 파일과 요소 ID를 적는다. 정상 자료를 일부러 망가뜨려 실패 장면을 만들지 않는다.\n')
 write(code/'input/README.md','대본에서 지정한 앞 실습 결과를 이곳에 복사하고 원본 위치와 판본을 적는다.\n')
 write(code/'output/README.md','직접 작성한 파일과 실제 확인 기록을 저장한다. 제공 성공 결과는 없다.\n')
 form(code,'input/previous-work.md',['원래 프로젝트와 파일 위치','판본·정의·에이전트 ID','이번에 복사한 결과','미확인'])
 form(code,'review.md',['입력과 기대','실제로 확인한 파일·요소·기록','차이와 원인','수정·재확인','저장·재열기','미확인'])
 form(code,'element-map.md',['참조 ID와 직접 작성한 ID','요소 이름·종류·레인','입출력과 연결 근거'])
 if idx==1:
  write(code/'source/request.md','# 정비 요청 승인 절차 — 작도 입력\n\n정비 요청 한 건을 받아 담당자가 확인한다. 담당자의 결정에 따라 승인 종료 또는 반려 종료로 닫는다. 요청·담당자 확인·승인 여부·두 끝을 그림에 나타낸다. 이 입력에는 실제 요청번호·담당자 계정·승인 결과가 없다. 이번 작업은 업무 그림을 작성·저장·다시 여는 범위이며 실행 성공 기록이 아니다.\n')
 else:
  for f,new in [('cooling-emergency.bpmn','cooling-emergency.bpmn'),('cooling-emergency.mapping.json','mapping.json')]:copy(C/'students/flows'/f,lab/'reference'/new)
  copy(C/'만들기/decks/integrated/day09/figures/흐름_전체.svg',lab/'reference/flow.svg')
  write(lab/'reference/README.md','# 제공 참조\n\nBPMN·매핑은 최신 통합반 저장소 students/flows의 바이트 그대로 복사했다. flow.svg는 이번 이론의 구조 그림이며 글자 라벨은 덱과 함께 읽는다. 이번 수업에서 직접 만든 결과나 새 실행 기록이 아니다. 실제 작업에서는 내 그림 요소 ID·실제 에이전트·역할·부품·판본과 대조한다.\n')
  form(code,'condition-plan.md',['승인 분기의 변수·연산·값','회복 분기의 변수·연산·값','두 기본 흐름','타이머 붙은 작업·중단 여부·기한'])
 if idx==3:
  write(code/'source/api-contract.md',api)
  form(code,'inspection.md',['초안과 판본','실제 문제 위치·field·reason','수정과 저장','재검사 응답','아직 확인하지 못한 실행 연결'])
  form(code,'deployment-record.md',['교육 환경과 배포 범위','정의 ID와 등록 판본','등록 응답','배포 시각·선택된 경보 경로','원래 열린 건과 새 사건의 구분'])
 if idx==4:
  write(code/'source/baseline-comparison.md','# 구조 비교 기준\n\n기준 흐름은 여러 에이전트 단계와 중단형 타이머, 수업 참조 흐름은 에이전트 한 단계와 비중단형 승인 지연 알림을 사용한다. 둘은 과거·미래 버전 관계가 아니다. 실제 교육 환경에서는 현재 배포 정의의 구조와 판본을 확인한다. 이 설명은 이번 실행 결과가 아니다.\n')
  form(code,'output/evidence-index.md',['사건 ID·시각과 처리 건 ID','정의·판본·배포와의 대응','에이전트 제출과 승인 대기','승인 접수·전달과 명령 기록','유온·경보 해제·작업지시·보고','끝 이벤트와 실제 결말','기준 흐름과 비교','수정 전후 판본과 재확인','미실행 경로·남은 확인'])
 text=(I/f'{idx+3:02}_실습_{name}.md').read_text('utf8');write(lab/'강사대본.md',text)
 files=sorted(f for base in [code,lab/'reference'] for f in base.rglob('*') if f.is_file())
 links=''.join('<li><a href="'+html.escape(f.relative_to(lab).as_posix(),quote=True)+'">'+html.escape(f.relative_to(lab).as_posix())+'</a></li>' for f in files)
 css='body{font:17px/1.8 "Malgun Gothic",sans-serif;max-width:980px;margin:40px auto;padding:0 24px;color:#22303e}h1{font-size:28px}h2{margin-top:32px;font-size:23px}aside{background:#f0f4f7;padding:14px}p,aside{white-space:pre-wrap}'
 sections=[]
 for para in text.strip().split('\n\n'):
  tag='h1' if para.startswith('# ') else 'h2' if para.startswith('## ') else 'aside' if para.startswith('>') else 'p'
  sections.append('<'+tag+'>'+html.escape(re.sub(r'^(?:#{1,2} |> ?)', '',para))+'</'+tag+'>')
 write(lab/'안내.html','<!doctype html><html lang="ko"><meta charset="utf-8"><title>'+name+'</title><style>'+css+'</style>'+''.join(sections)+'<h2>작업 자료</h2><ul>'+links+'</ul></html>')
 reading=speech(text);write(I/'낭독본'/f'{idx+3:02}_실습_{name}.md',reading);pdf(reading,lab/'강사대본.pdf')
 with zipfile.ZipFile(lab.with_suffix('.zip'),'w',zipfile.ZIP_DEFLATED) as z:
  for f in sorted(lab.rglob('*')):
   if f.is_file():z.write(f,f.relative_to(lab).as_posix())
 index.append(f'## 실습{idx} — {name}\n\n[자료 ZIP]({lab.name}.zip) · [진행 안내]({lab.name}/안내.html) · [대본 PDF]({lab.name}/강사대본.pdf)\n')
write(C/'산출물/실습/통합반_온라인/09회차_실습_안내.md','\n'.join(index))
patch_notes();merge(C,I,False)
merged=I.parent/'통합반_09일차_대본.md'
write(merged,re.sub(r'\]\((\d{2}_[^/)]+\.md)\)',r'](09회차/\1)',merged.read_text('utf8')))
pdf((I.parent/'낭독본/통합반_09일차_낭독본.md').read_text('utf8'),I.parent/'통합반_09일차_대본.pdf')
alltext='\n\n'.join(speech(f.read_text('utf8')) for f in sorted(I.glob('*_실습_*.md')));write(I/'실습_낭독합본.md',alltext);pdf(alltext,I/'통합반_09일차_실습대본.pdf')
write(EV/'pdf-check.json',json.dumps(checks,ensure_ascii=False,indent=2));write(EV/'source-materials.json',json.dumps(source_manifest,ensure_ascii=False,indent=2))
print('6 document PDFs,4 labs; no lab execution')
