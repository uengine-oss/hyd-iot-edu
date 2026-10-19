from helpers import *
source_manifest=[]
def copy(src,dst):
 dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
 source_manifest.append(dict(source=str(src),destination=str(dst),sha256=hashlib.sha256(src.read_bytes()).hexdigest()))
def tree(src,dst):
 for f in src.rglob('*'):
  if f.is_file() and '__pycache__' not in f.parts and f.name!='.env':copy(f,dst/f.relative_to(src))
def jwrite(path,obj):write(path,json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def form(code,name,headings):write(code/name,'# '+name+'\n\n빈 작성 양식. 실제 결과와 근거는 수업에서 작성한다.\n\n'+'\n\n'.join('## '+x+'\n' for x in headings)+'\n')
def materials(name,code):
 if name in ['행동기준작성','반복검증','오류수정과회귀']:
  src=C/'산출물/실습/통합반_오프라인/07회차_실습4_시나리오_회귀_검증/코드'
  for rel in ['spec.md','검증/시나리오.json','검증/견주기.py','긴급_기준.json']:copy(src/rel,code/'source/reference'/rel)
  write(code/'source/README.md','# 기존 예제 참조\n\n이전 교재의 시나리오·명세·비교 도구다. 현재 수업에서 실행한 결과가 아니다. 실제 작업은 통합반7에서 만든 프로젝트를 이어 사용한다. 견주기.py는 차이를 나열하는 도구이며 합격 판정이나 에이전트 실행을 하지 않는다. 참조 요청 번호·필드와 현재 명세를 대조한 뒤 사용한다.\n')
  form(code,'input/previous-work.md',['앞 프로젝트 위치와 판본','명세·입력·조회 자료·설정 위치','기존 결과와 이번 결과의 구별'])
  form(code,'scenarios.md',[f'{x} — Given / When / Then / 입력 / 기대 상태 / 출력 계약 / 근거 위치' for x in ['일반 정비','긴급 정비','필수 정보 누락','승인 거절','도구 오류']])
  form(code,'execution-plan.md',['실제 시작 명령과 입력 전달','결과 저장 위치','조회 자료·설정·판본','반복 횟수와 이유','실행 불가·건너뜀 조건'])
  form(code,'result-review.md',['시나리오별 기대·실제·근거 파일','표현 차이·계약 위반·실행 실패·미확인','수정과 재확인'])
  form(code,'change-review.md',['실패 원출력과 기대 근거','원인·수정 위치·변경 이유','수정한 경우 재검증','전체 회귀 결과·미확인'])
 if name=='교대인수인계':
  # 스키마는 저장소 이벤트/업무 DB 형태를 사용한다. 값은 새로 만든 교육용 입력이다.
  jwrite(code/'source/events.json',[dict(alertId='EDU-S08-E01',asset='HYD-01',pattern='COOLER_DEGRADATION',severity='HIGH',state='RAISE',t='2026-10-18T09:00:00+09:00',evidence={'values':{'TS1':55.71,'CE':46.2}})])
  jwrite(code/'source/maintenance.json',[dict(asset='HYD-01',wo='EDU-S08-W01',task='쿨러 핀 세척',performed_at='2026-10-17T15:00:00+09:00')])
  jwrite(code/'source/parts.json',[dict(part_no='P-RTN-FLT',on_hand=2,reserved=0,on_order=0,reorder_point=1,target_stock=2,reserved_for='HYD-02',base_on_hand=2,base_reserved=0,need_by_days=None)])
  write(code/'source/source-contract.md','# 세 출처의 스키마와 준비 자료\n\n모든 행은 이번 제작에서 작성한 수업용 가상 입력이다. 실제 조회 결과·현재 재고·이번 실행 결과가 아니다. 이벤트는 alertId/asset/pattern/severity/state/t/evidence 구조, 정비 이력은 it/supabase/seed.sql의 ent.maintenance_history(asset,wo,task,performed_at), 부품은 같은 파일의 ent.spare_stock 필드 구조를 따른다.\n\n이벤트의 t는 사건 시각, performed_at은 정비 수행 시각이다. 부품 파일에는 관측·갱신 시각이 없으므로 현재 재고라고 단정하지 않는다. 조회 시각은 제공하지 않았으므로 수업에서 실제로 읽은 시각을 별도 기록한다. 과거 정비 이력이 이후 경보의 해소나 현재 작업 완료를 증명하지 않는다. HYD-02용 부품을 HYD-01 경보에 근거 없이 연결하지 않는다. 새 경보의 작업지시·미완료 요청 여부는 앞 실습 결과 또는 추가 근거가 없으면 미확인이다.\n')
  form(code,'handover-plan.md',['대상과 기간','세 출처별 원래 키·연결 조건','사건/갱신 시각과 조회 시각','앞 실습 미확인과 자료 판본'])
  form(code,'output/handover.md',['완료 작업과 근거','미완료 요청과 근거','주의 사항·시각·충돌·미확인','추가 확인할 담당과 항목'])
 if name in ['업무명세','지식구조','제안에이전트','흐름실행']:
  source=D/'students/_template';ref=code.parent/'reference/example_meeting'
  tree(source/'example_meeting',ref)
  tree(source/'example_meeting/docs',code/'source/docs')
  for rel in ['schema.json','graph.json','questions.cypher','load_graph.py','case_card.md','agent/goal.md','agent/SKILL.md']:
   copy(source/rel,code/'source/templates'/rel)
  write(code/'source/runtime-guide.md','# 실제 작업 위치와 명령\n\n제공 load_graph.py는 단독 배포 프로그램이 아니라 HYD 저장소의 scripts/ontology_v2.py를 사용하는 참조 도구다. 수업에서는 HYD 저장소의 students/<내이름공간>/에 작성 파일과 load_graph.py를 둔다. <내이름공간>을 실제 값으로 바꾼 뒤 저장소 루트에서 다음 순서를 사용한다. 이 문서 제작에서는 명령을 실행하지 않았다.\n\n1. python students/<내이름공간>/load_graph.py check\n2. 준비된 DB 접속 환경에서 python students/<내이름공간>/load_graph.py load\n3. python students/<내이름공간>/load_graph.py ask\n\n정적 검사와 DB 적재·조회 결과를 구분한다. 참조 example_meeting의 demo는 예시다. 실제 작업 ns와 모든 id 접두어·질의 매개변수를 같은 값으로 맞춘다. 기준 스키마와 다른 작업은 보존한다.\n\nreference는 코드 폴더 밖의 참고 완성 예다. gcal/gdrive, 에이전트 ID, extract 경로에는 실제 연결을 확인해 채울 자리가 있다. 이 예제를 그대로 가져오면 등록을 보장하지 않는다. 이번 작은 업무는 명세에 정한 읽기·제안·사람 확인·보고만 구성하며 외부 일정 생성은 완료로 적지 않는다.\n')
  form(code,'spec.md',['요청과 입력','정보원과 출처','산출물 계약','사람 확인과 권한','완료·보류·거절 조건','범위 밖의 쓰기'])
  form(code,'request.md',['업무 요청 한 건','확인된 자료','미확인 값'])
  form(code,'element-map.md',['내 요소 ID와 종류','담당·부품·입출력','분기와 종료 결과','실제 연결과 남은 자리'])
  form(code,'agent/goal.md',['목표','출력 계약','읽기 도구와 권한','보류 조건'])
  form(code,'agent/SKILL.md',['원문 확인','지식 조회','근거 대조','제안 또는 보류'])
 if name=='ProcessGPT시연':
  write(code/'source/product-sources.md','# 제품 시연의 문헌 근거\n\n공식 저장소: https://github.com/uengine-oss/process-gpt\n\n2026-10-18 문헌 확인: BPMN 기반 다중 에이전트 조율과 자연어 프로세스 설계를 소개한다. 소개된 기능과 수업 계정에서 실제로 확인한 기능을 구분한다. 화면·실행·권한·연결은 이번 제작에서 검증하지 않았다.\n')
  form(code,'observation.md',['접속 대상·판본·권한·시각','HYD 대응 — 지식·에이전트·정의·인스턴스·사람 작업','실제로 확인한 기록','문헌에만 있는 항목','차이·미확인·재확인'])
 if name=='지식자산화':form(code,'knowledge-note.md',['내 문장으로 쓴 개념','참고 자료와 원문 절','명세·지식·에이전트·흐름 산출물','검증 결과와 미확인','실제 Notion 페이지·첨부 링크','저장 후 다시 열기 확인'])
