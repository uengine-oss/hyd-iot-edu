"""대본·자료·배포 묶음 생성. 학생 코드·실습·포털 실행 없음."""
from helpers import *
import csv
from labs import namesI,namesP,blank
old=D/'산출물/실습/실전반_온라인/02일차_실습5_조치조건표'
raw=C/'산출물/실습/통합반_오프라인'
docs=raw/'04회차_실습2_지식_추출/코드/문서'
source_manifest=[]
def copy(src,dest):
 dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest)
 source_manifest.append(dict(source=str(src),destination=str(dest),sha256=hashlib.sha256(src.read_bytes()).hexdigest()))
targets='sop_id,reference_skill_id,name,kind,codes,source_section\nSOP-COOL-11,skill:fan-max,팬 최대 운전,control,FAN_SET,HM-8.5\nSOP-COOL-12,,팬 최대 운전과 부하 80 %,control,FAN_SET;LOAD_SET,HM-8.5\nSOP-COOL-13,,부하 70 %와 야간 핀 세척,control,LOAD_SET;WO_CREATE,HM-8.5\nSOP-COOL-14,,쿨러 핀 세척,workorder,WO_CREATE,HM-8.7\n'
# Input scenarios, not execution results. The same facts are compared against each candidate.
cases='case,candidate_sops,forecast_ts1_C,forecast_ps1_bar,plc_mode,plc_state,fan100_hours\nA,SOP-COOL-11;SOP-COOL-13,54.9,165,REMOTE_AUTO,RUNNING,0\nB,SOP-COOL-11;SOP-COOL-13,54.9,165,REMOTE_AUTO,RUNNING,23.9\nC,SOP-COOL-11;SOP-COOL-13,55,165,REMOTE_AUTO,RUNNING,24\nD,SOP-COOL-11;SOP-COOL-13,55.1,165,REMOTE_AUTO,RUNNING,24.1\nE,SOP-COOL-11;SOP-COOL-13,54,164.9,REMOTE_AUTO,RUNNING,24\nF,SOP-COOL-11;SOP-COOL-13,56,160,REMOTE_MANUAL,TRIP,30\nG,SOP-COOL-11;SOP-COOL-13,54,170,REMOTE_MANUAL,RUNNING,0\nH,SOP-COOL-11;SOP-COOL-13,,170,REMOTE_AUTO,RUNNING,0\nI,SOP-COOL-11;SOP-COOL-13,56,170,REMOTE_AUTO,RUNNING,30\nJ,SOP-COOL-11;SOP-COOL-13,54,165.1,REMOTE_AUTO,RUNNING,24\nK,SOP-COOL-11;SOP-COOL-13,,160,REMOTE_MANUAL,RUNNING,0\n'
for root,folder,course,names in [(C,I,'통합반',namesI),(D,P,'실전반',namesP)]:
 index=[f'# {course} 3회차 실습 자료\n\n자료를 다운로드하고 압축을 푼 뒤 VS Code에서 폴더를 연다. 실제 실습·캡처는 미수행이며 결과 기록은 수업에서 작성한다.\n']
 for idx,name in enumerate(names,1):
  lab=root/f'산출물/실습/{course}_온라인/03일차_실습{idx}_{name}';code=lab/'코드';code.mkdir(parents=True,exist_ok=True)
  text=(folder/f'{idx+3:02}_실습_{name}.md').read_text('utf8');write(lab/'강사대본.md',text)
  write(code/'README.md',f'# {name}\n\n안내.html과 강사대본.md를 따라 작성한다. 완성 코드·결과를 제공하지 않는다.\n\n입력: source/의 배포 원문, input/에 직접 복사한 앞 회차 결과. 출력: output/의 직접 작성한 파일. 실제 환경 주소와 DB명은 수업 담당자가 제공한다.\n')
  write(code/'input/README.md','앞 회차의 직접 작성 결과를 복사한다. 인증 정보는 저장하지 않는다.\n');write(code/'output/README.md','대본에 따라 직접 만든 산출물을 저장한다. 빈 폴더는 완료 결과가 아니다.\n')
  if name=='조치결과비교':
   write(code/'comparison.md',blank+'\n| 시험 | 기준 입력 | 바꾼 한 항목 | 제외·경고·감점 | 점수 | 손익 | 근거 | 원본 불변 |\n|---|---|---|---|---|---|---|---|\n| | | | | | | | |\n')
   write(code/'kpi.csv','asset,margin_C,period,source\nHYD-01,2.53,동일24시간,통합반3_38장\nHYD-02,16.72,동일24시간,통합반3_38장\nHYD-03,14.55,동일24시간,통합반3_38장\n')
  if name in ['조치기준만들기','판단기능만들기']:
   for f in ['HM-8_매뉴얼.md','작업기준.md','규칙_원문.txt']:copy(old/f,code/'source'/f)
   write(code/'targets.csv',targets);write(code/'cases.csv',cases);write(code/'id-map.csv','sop_id,existing_model_id,source,review_note\n')
   write(code/'failuremodes.csv','reference_id,name,component,symptoms,source_section\nfm:cooler-performance-loss,쿨러 냉각 성능 상실,오일 쿨러,유온 상승;냉각 효율 저하,HM-8.4\n')
   write(code/'expected.md',blank+'\n| 사례·후보 | 예상 경고 | 예상 감점 | 예상 제외 | 누락·보류 | 근거 | 실제 결과 |\n|---|---|---|---|---|---|---|\n| | | | | | | |\n')
   write(code/'rules.csv','rule_id,action,input,operator,value,unit,result,penalty_만원,reason,source_section\n')
   write(code/'source/적용범위.md','# 입력과 적용 범위\n\n작업기준.md는 실전반2에서 쓴 팬 최대 운전 중심 입력이다. 다른 후보는 targets.csv의 SOP ID와 HM-8 원문의 적용 범위를 대조해 행을 확장한다. 기존 모델 ID는 id-map.csv에 적는다. reference_skill_id 빈칸은 임의로 채우지 않는다.\n\n팬 감점은 SOP-COOL-11·12에만, 원격 모드 제외는 SOP-COOL-11~13에 적용한다. 압력·트립 규칙은 첨부 구조화 발췌를 근거로 쓴다. 작업지시와 제어의 kind를 구별한다. 실행 코드는 목록이므로 FAN_SET 포함 여부와 RESET 외 코드 존재를 목록으로 판정한다.\n\ncases.csv는 경계·누락·복수 규칙 비교용 입력이며 실제 사건 기록이 아니다. 모든 후보의 예측값을 같게 놓아 규칙 적용 대상만 비교한다. C3의 팬 24시간 수행 제한과 감점 조건은 별개이며 후보 유지가 실행 허가는 아니다.\n')
   if name=='판단기능만들기':
    for f in (raw/'03회차_실습4_조치_선택_근거/코드/지표').iterdir():
     if f.is_file():copy(f,code/'metrics'/f.name)
    copy(raw/'03회차_실습3_판단_기능/코드/입력/판정_요청.json',code/'metrics/판정_요청.json')
    write(code/'metrics/경로와비교기준.md','# 제공 지표 자료의 연결\n\n지표_정의.md는 원본 설명을 보존했다. 그 문서의 지표/는 현재 metrics/, 입력/판정_요청.json은 metrics/판정_요청.json에 해당한다. 결과/판정_결과.json은 제공하지 않는다. 직접 만든 함수에 후보별 예측값을 넣어 계산한 output/result.json을 사용한다. 원본 요청의 RUN은 이번 사례의 RUNNING과 같은 정상 상태 표기로 명시 변환하며 TRIP과 구별한다.\n\n경계 테스트 cases.csv와 손실 비교용 판정_요청.json을 섞지 않는다. 손실 비교에서는 요청 C01의 후보별 예측값으로 별도 평가한다. 네 손실의 합과 감점 금액은 교육용 비교 기준이며 HYD 일곱 성분 점수와 다르다. 현재 값 조회나 현장 예측 검증 결과로 보지 않는다.\n')
  if name in ['매뉴얼검토','지식추출','그래프반영']:
   for f in docs.iterdir():
    if f.is_file():copy(f,code/'source'/f.name)
   copy(docs/'문서_목록.csv',code/'source/documents.csv')
   write(code/'review.md',blank+'\n| 후보 | 문서·판본·구간 | 원문 | 문제·수정 | 채택·수정·제외·보류 | 검토자 | 실제 확인 |\n|---|---|---|---|---|---|---|\n| | | | | | | |\n')
   if name=='지식추출':write(code/'prompt.md','# 추출 지시문 작성\n\n## 대상과 출력 형식\n\n## 원문 보존·금지 사항\n\n## 기존 ID와 매핑\n\n## 인용과 경고\n')
   if name=='그래프반영':write(code/'mapping.md',blank+'\n| 후보 ID | 기존 대상 ID | 관계·방향 | 스키마 근거 | 미해결 |\n|---|---|---|---|---|\n| | | | | |\n')
  # Guide is plain-text-safe HTML, links are local and validated.
  files=sorted(f for f in code.rglob('*') if f.is_file());links=''.join('<li><a href="'+html.escape(f.relative_to(lab).as_posix(),quote=True)+'">'+html.escape(f.relative_to(lab).as_posix())+'</a></li>' for f in files)
  css='body{font:17px/1.8 "Malgun Gothic",sans-serif;max-width:980px;margin:40px auto;padding:0 24px;color:#22303e}h1{font-size:28px}h2{margin-top:32px;font-size:23px}aside{background:#f0f4f7;padding:14px}p,aside{white-space:pre-wrap}'
  segments=[]
  for para in text.strip().split('\n\n'):
   tag='h1' if para.startswith('# ') else 'h2' if para.startswith('## ') else 'aside' if para.startswith('>') else 'p'
   segments.append('<'+tag+'>'+html.escape(re.sub(r'^(?:#{1,2} |> ?)', '',para))+'</'+tag+'>')
  write(lab/'안내.html','<!doctype html><html lang="ko"><meta charset="utf-8"><title>'+name+'</title><style>'+css+'</style><h2>작업 자료</h2><ul>'+links+'</ul>'+''.join(segments)+'</html>')
  reading=speech(text);write(folder/'낭독본'/f'{idx+3:02}_실습_{name}.md',reading);pdf(reading,lab/'강사대본.pdf')
  with zipfile.ZipFile(lab.with_suffix('.zip'),'w',zipfile.ZIP_DEFLATED) as z:
   for f in sorted(lab.rglob('*')):
    if f.is_file():z.write(f,f.relative_to(lab).as_posix())
  index.append(f'## 실습 {idx} — {name}\n\n[자료 ZIP]({lab.name}.zip) · [진행 안내]({lab.name}/안내.html) · [대본 PDF]({lab.name}/강사대본.pdf)\n')
 write(root/f'산출물/실습/{course}_온라인/03회차_실습_안내.md','\n'.join(index))
patch_notes()
merge(C,I,False);merge(D,P,True)
for folder,course in [(I,'통합반'),(P,'실전반')]:
 pdf((folder.parent/'낭독본'/f'{course}_03일차_낭독본.md').read_text('utf8'),folder.parent/f'{course}_03일차_대본.pdf')
 alltext='\n\n'.join(speech(f.read_text('utf8')) for f in sorted(folder.glob('*_실습_*.md')));write(folder/'실습_낭독합본.md',alltext);pdf(alltext,folder/f'{course}_03일차_실습대본.pdf')
write(EV/'pdf-check.json',json.dumps(checks,ensure_ascii=False,indent=2))
write(EV/'source-materials.json',json.dumps(source_manifest,ensure_ascii=False,indent=2))
print('documents complete',len(checks),'PDFs; lab execution: none')
