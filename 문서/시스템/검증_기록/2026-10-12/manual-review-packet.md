# 매뉴얼 실제 추출 제안 — 사람 검토 준비

추출 제안과 원문을 비교한 자료다. **사람 검토 기록이나 적재 완료가 아니다.** `reviewed=true`를 설정하지 않았고 그래프 적재·규칙 실행·승인을 수행하지 않았다. NOW §5의 확정 규칙은 **“지식 적재는 사람 검토 기록이 있어야 한다.”**다. 따라서 아래 식별자·승인 역할·생략된 근거·추론을 먼저 확인할 수 있도록 원문과 제안을 묶었다. 추출·검토 준비 작업은 계속 진행한다.

최신 사용자 지시로 현재 모든 작업·실제 워커는 **Sol 6.1만** 사용한다. HM-8은 모델 전환 전에 완료된 Astra 제안이며 Sol이 원문/저장 계약을 읽어 대조했다. PM-02 Astra 작업은 공식 취소 및 close로 `COMPLETED/closed-by-human` 처리했고 Sol로 PM-02·PR-07 새 추출을 진행한다. 이전 모델 결과의 출처를 Sol 추출로 바꾸지 않는다.

## HM-8 원문·실제 제안

- 원문: [HM-8_cooler-fan-manual.md](../../../samples/HM-8_cooler-fan-manual.md), HM-8.1~8.8의 교육용 예시. 산업 설비 공통 기준이나 새 시나리오 계약으로 읽지 않는다.
- 실제 제안: [proposal-HM-8.json](D:/work/study/hyd-iot-edu/.claude/worktrees/codex-portal-20261011/.evidence/a161-c3/proposal-HM-8.json).
- 실제 추출: `manual_source_extraction.394d8cab-ecf9-4927-8b64-8e5116374dc1`, 287초, 제안 READY. 원문절8·절차8·단계27·warnings18·rules3·causes3·evidence0·failure_modes1.
- 원문의 명시 SOP7개 모두 포함했고 각 절차의 단계 번호 중복은 없다. 추가 `SOP-HM8-6`은 원문에 없는 등록 제안 번호다. coverage0.981은 인용 문자 비율이며 지식 모델 완결성이나 사람 승인 점수가 아니다.
- preview는 기존 `SOP-FAN-11/12` admin_knowledge 및 seed의 고장/원인 충돌도 보고한다. 아래와 함께 대상 소유자·개정 여부를 확인해야 한다.

## 적재 전 판단할 네 묶음

| 묶음 | 원문 구절·조건 | 실제 제안 및 경고 | 판단할 내용 |
|---|---|---|---|
| 1. 기존 스킬 동일성·승인 역할 | HM-8.5의 COOL-11/12/13 모두 **“승인: 운전원.”** HM-8.7의 작업지시 승인은 설비보전팀장. 원문 번호 COOL-11~15 | 제안은 `existing_skill_id=skill:fan-max`, `skill:fan-max-derate`, `skill:derate-night-clean`, `skill:wo-cooler-clean`, `skill:wo-ventilation`을 함께 둔다. 경고는 기존 참조가 새 중복 등록을 뜻하지 않는다고 설명하지만 실제 manual_graph 저장은 이 필드를 읽지 않고 절차id에서 새 skill_id를 만든다. 현재 기준은 COOL-01~05이며 COOL-02/03 승인자는 생산관리자다 | 기존01~05 개정인지 별도11~15 등록인지 결정할 근거가 필요하다. 원문 운전원과 기존 생산관리자 충돌을 숨기거나 번호/역할을 자동 덮어쓰지 않는다. 제안 필드만으로 동일 노드 개정이라고 보장하지 않는다 |
| 2. 원인 판정 증거4개 | HM-8.4: 핀 오염은 CE30초 평균<70% **및** VS1 120초 평균<0.9mm/s. 외기 고온은 TS4 120초 평균≥35℃. 팬 구동 불량은 VS1 120초 평균≥0.9mm/s | `knowledge.evidence=[]`. 경고는 필수 숫자 가중치의 원문 근거가 없어4항목을 제외했고 조건은 excerpt/anchor에 보존했다고 설명한다. 원문 사전확률0.6/0.2/0.2를 증거 가중치로 바꾸지 않았다. 시간 평균 입력도 기존 결정표에 없어 순간값으로 바꾸지 않았다 | 가중치 및 실제 관측/질의 경로가 확인돼야 구조화 증거로 보완할 수 있다. CE1순위 선택 규칙이 이 네 증거 충족이나 원인 진단을 대신한다는 해석은 금지한다 |
| 3. 수명 감점·최소 부하 규칙 | HM-8.8: **“이미 24시간을 넘겼다면”** 팬 최대 조치에20만원 감점. **“펌프 부하를 60 % 미만으로 설정하지 않는다.”** | 경고는 감점 대상 지표와 후보 부하 입력이 없어 규칙 제안에서 제외했다고 밝힌다. excerpt/anchor에는 원문 조건을 보존했다. 정확히24시간을 초과로 바꾸거나 지표/입력을 임의 생성하지 않았다 | 감점 지표·연속 운전 시간 입력·후보 설정값 입력의 실제 의미와 출처를 확인해야 한다. 원문이 남아 있다는 것과 규칙 엔진에 등록·집행된 상태를 구분한다 |
| 4. FAN 작업지시 추론·회복 단계 누락 | HM-8.1/2는 수동 점검·벨트교체 절차이며 승인 역할·작업지시 발행 방식은 명시하지 않는다. HM-8.6은 **“조치 뒤 15분 동안 TS1이 55 ℃ 미만이고 경보가 해제된 상태가 유지”**될 때 성공 | FAN-11/12 `link.kind=work_order`는 원문에 없는 제안이다. warnings는 역할·발행 방식 미상을 밝힌다. 추가 SOP-HM8-6의steps에는 예측값 비교와 미달 보고만 있고 성공 조건의15분 유지 확인은 단계로 빠져 excerpt에만 남는다. 회복 경고는 성공 조건을 설명한다 | FAN 작업지시 종류를 추론 그대로 승인할지 근거를 보완할지 확인한다. 회복 성공 조건을 원문대로 단계/검증에 보존할지 확인한다. 과거에 제외한 시운전·미달 기능을 새 시나리오 요구로 되살리지는 않는다 |

기존 승인 역할·번호의 소스 근거는 [instances.cypher](../../../../it/neo4j/v2/instances.cypher)의 `skill:fan-max`~`skill:wo-ventilation` 행이다. 실제 그래프 상태와 쓰기 보호는 메인의 조회/HTTP preview로 다시 확인한다. 제안에 있는 경고는 누락·추론을 알리는 근거이며 해당 누락이 이미 해결됐다는 표시가 아니다.

## 원문·제안 검토 순서

1. source_id/anchor가 가리키는 HM-8 원문과 인용 구절을 대조한다. 명시 SOP7개와 추가1개를 구분한다.
2. 번호·기존 노드·승인 역할과 admin/seed 충돌에 대한 처리 방향을 기록한다. DecisionCase 판단 이력을 지우지 않는 개정/rollback 보호를 유지한다.
3. 구조화 evidence와 두 제한 규칙의 미등록 이유, FAN 작업지시 추론 및 회복 성공 확인 단계 누락을 검토한다. 미상 값을 채웠다면 근거를 따로 기록한다.
4. 이 검토 자료를 실제 사람 검토 기록으로 바꾸는 단계와 적재는 별도로 수행한다. 새 제안·자동시험·원문 대조만으로 reviewed/commit하지 않는다.

## PM-02 실제 Sol 제안과 원문 대조

원문은 [PM-02_powerpack-pm-checklist.md](../../../samples/PM-02_powerpack-pm-checklist.md), 실제 제안은 [proposal-PM-02.json](D:/work/study/hyd-iot-edu/.claude/worktrees/codex-portal-20261011/.evidence/a161-c3/proposal-PM-02.json)이다. 실제 Sol 6.1 추출 `manual_source_extraction.914896d0-e074-4359-a6e9-66be38267201`의 READY 제안을 02:29:09 KST에 확인했다(246.4초·warnings 23·rules 8·causes 2·evidence 0). Sol 읽기 담당이 절10·절차8·단계33을 대조했다. 명시 SOP7개와 번호 없는 시운전 확인을 절차로 만든 `SOP-PM2-9`가 포함된다. 단계 번호 중복·원문 단계 누락·원문 밖 단계는 없지만, 다음 지식/실행 연결 문제는 별도다.

| 묶음 | 원문 구절·조건 | 실제 제안 및 경고 | 판단할 내용 |
|---|---|---|---|
| 1. 즉시 정지의 분류와 command | PM-2.5 SOP-PM-12의 **“생산 중인 오더를 멈추고 설비를 정지한다.”** 뒤 정비 오더 발행·생산팀 공지·부품 출고. 현장 절차는 PLC 실행 승인이라고 명시하지 않음 | `link.kind=work_order`에 `action:controlled-stop` command(value=null)가 포함된다. 경고11은 PLC 자원/수치 미상·현장 절차가 명령 승인 아님을 밝힌다. 실제 [manual_knowledge.py](../../../../it/process/procsvc/manual_knowledge.py)385행은 command를 control 스킬에만 허용하므로 이 조합 그대로는 commit에서 거절된다 | 작업지시와 명령을 어떤 실제 연결로 모델링할지 원문/권한을 검토해야 한다. 검증을 약화하거나 kind만 바꿔 통과시키지 않는다. 추출 READY는 commit 가능성 검증 완료가 아님 |
| 2. 오염 원인의 같은 ID·다른 문맥 | PM-2.10의 작동유 오염은 펌프 체적 효율 저하에 연결·prior0.3 | `cause:particle-contamination`은 기존 작동유 열화 연결·prior0.25와 같은 ID다. 경고19가 별칭 대응·기존 관계·사전확률 충돌을 밝힌다. preview knowledge_conflicts도 seed 소유권을 보고한다 | 문서별 문맥과 기존 노드의 동일성·개정 범위를 사람 검토로 확인한다. 같은 ID를 이용해 고장 연결/확률을 조용히 바꾸지 않는다 |
| 3. 60초 압력/유량 근거 | PM-2.10: 최근1분 PS1 평균<165bar, 최근1분 FS1 평균<8.0l/min | evidence=[]이며 경고20은 원문에 가중치가 없다고 설명한다. 기존 씰 마모 증거의120초·0.6/0.4를 원문60초나 오염 근거에 대입하지 않았다 | 증거 가중치·실제 질의 경로를 검토해야 구조화 증거가 된다. excerpt·경고의 원문 보존을 실제 evidence 등록 완료로 표시하지 않는다 |
| 4. 비교 조건·정비 실행 범위 | PM-2.5의 납기24시간 안인 오더가 있는데 즉시 정지하면80만원 감점, 묶음 대상은 같은 기종·운전시간≥하한. PM-2.1/6~9의 누적 시행 차례·패키지·시운전 합격 뒤 계수기 초기화 | 경고7/8은 즉시 정지 감점 지표·다른 설비 조건 입력 부족을 밝힌다. 경고3/18은 패키지 누적 선택 및15분 PS1/FS1/VS1 동시 합격·계수기 reset에 필요한 입력/실행 연결 미구현을 설명한다. 계수기 reset을 인터록 reset으로 바꾸지 않았다 | 문장/steps가 원문대로 있다는 사실과 정비 패키지 선택·현장 실행·합격 판정·계수기 초기화의 실제 구현을 구분한다. 기존 B 시나리오에서 제외한 시운전·미달 기능을 새 필수 업무로 추론하지 않는다 |

위 첫 묶음의 commit 거절은 제품이 현재 보호 계약대로 이질적인 command/스킬 종류를 거절한다는 뜻이다. 검토가 끝나기 전에 적재 실패를 숨기거나 제안이 실행 가능한 것으로 소개하지 않는다. PM-02도 사람이 검토하지 않았으며 reviewed/commit/그래프 적재 전이다.

## PR-07 신규2.4 실제 Sol 제안 — 구매 절차 범위 수정 완료

첫2.3 제안에서 구매 SOP가0개였던 원인은 제품 추출 지시의 범위 결함이었다. 제품이 확정 B/C 업무 문서를 정비·운전 장으로 한정한 부분을 신규2.4에서 고쳤으며 사용자가 다시 범위를 결정해야 하는 중단 조건으로 남기지 않는다. 기존2.3 정의/진행 건은 소급 변경하지 않았다.

실제 Sol 6.1 재추출 `manual_source_extraction.e7d00281-5325-4b26-ab7f-21e2e31ffd74`는 **COMPLETED/2.4**이며 [extraction24-live-proof.json](D:/work/study/hyd-iot-edu/.evidence/overnight-20261012/extraction24-live-proof.json)에서 previous_definition_unchanged=true를 확인했다. 실제 결과는 [proposal-PR-07.json](D:/work/study/hyd-iot-edu/.claude/worktrees/codex-portal-20261011/.evidence/a161-c3/proposal-PR-07.json):224.5초·절7·SOP6·단계21·warnings14·rules7·causes/evidence/failure_modes0이다. [manual-extraction-sol24-ready.log](D:/work/study/hyd-iot-edu/.evidence/overnight-20261012/manual-extraction-sol24-ready.log)와 Sol 원문 대조로 확인했다.

PUR-11/12/13 각5단계는 원문 그대로이며 추가 승인 단계는 없다. 추가 `SOP-PR7-1`(부품 선정/재고 관리1행), `SOP-PR7-4`(총비용 비교·납기 경고·검사 강화3행), `SOP-PR7-7`(입고 합격 확인·지연 보고2행)도 원문 행위만 갖고 ID/단계 중복은 없다. warnings1/2/4는 추가 번호가 원문 SOP 번호가 아닌 원문 등장 순서의 등록 제안 번호임을 밝힌다. 정책/검증 행위를 별도 SOP로 적재할지에 대한 의미 검토와 추출 범위 결함의 수정은 다른 문제다.

| 묶음 | 원문·제안 확인 결과 | 적재 전 판단·제한 |
|---|---|---|
| 1. 고장 유형이 없는 구매/정책 절차 | 6개 절차의 link.failureMode/relation은 모두null. 원문에 고장 유형 연결이 없고 구매/재고·정책·검증 행위다 | 실제 `manual_review.py`→`kgadmin.validate_skill(create=True)` 경로는 새 스킬에 failureMode를 요구한다. 빈칸 그대로는 commit 불가이며 임의 고장 유형을 채우지 않는다. 추출 본문 누락을 해결한 사실과 현재 적재 모델의 필수 연결을 구분한다 |
| 2. 부품별 공급사와 고정 action | PUR-11의sup:b·PUR-12의sup:a는 원문 공급사 이름이 아니라 현재3개 부품의 견적 대조 결과다(warning9). PUR-13 actions=[]는 부품마다 최단 공급사가 다르기 때문이다(warning10) | 부품별 실제 견적을 고정 공급사값으로 사용할지 검토한다. 전체 최단 선정 뒤 AVL 확인이라는 원문 순서를 유지하며 AVL 먼저 필터해 대체 공급사를 고르지 않았다. 고정값/빈 actions만으로 C 자동 완주가 충분하다고 하지 않는다 |
| 3. 구매요청·발주·검사·입고의 실제 연결 | warning11은 PR_CREATE가 ERP 발주 전체·검사·입고를 대신하지 않음을 밝힌다. 원문 발주3개와 정책/검증3개는 구조화했다 | 원문 행위가 실제 업무 시스템 객체/승인/입고 처리에 연결되는 범위를 검토한다. SOP 단계가 있다는 이유로 실제 발주·입고 완료를 주장하지 않는다 |
| 4. 비용·분할·입고 조건 | rules7은 발주3개 범위·AVL·300만원 초과WARN·납기WARN·불량률>10% WARN와20만원PENALTY를 제안한다. warning13은 건별 검사비/월 비용 지표 대응, warnings6/12는 분할·입고 자동 조건의 입력 부족을 밝힌다 | 비용 단위·집계와 실제 분할 여부/로트/검사 합격/입고 지연 입력을 확인한다. 구조화 규칙이 실제 판정·보고·검사를 실행한 뜻은 아니다 |

신규 범위/판본 계약79개와 기존 워커·원문 저장·인용·사람 검토를 포함한 확대247개 시험이 통과했다(`extraction-24-tests.log/xml`, `extraction-24-regression.log/xml`). CLI test double 시험과 위 실제 Sol 실행은 별도 증거다. 실제 제안이 READY여도 사람 검토·그래프 적재는 수행하지 않았다.

첫2.4 시도는 process 재빌드 직후 준비 전 GET에서 RemoteDisconnected가 났고 쓰기 전에 종료했다(`manual-extraction-sol24.log`). healthz 정상 확인 후 위 성공을 별도로 실행했다. 최초 실패와 성공을 합치거나 실패 로그를 없애지 않았다.

## PR-07 첫2.3 실제 Sol 제안 — 범위 결함의 보존 이력

원문은 [PR-07_spare-parts-standard.md](../../../samples/PR-07_spare-parts-standard.md), 실제 제안은 [proposal-PR-07-v2.3.json](D:/work/study/hyd-iot-edu/.claude/worktrees/codex-portal-20261011/.evidence/a161-c3/proposal-PR-07-v2.3.json)이다. 실제 Sol 6.1 추출 `manual_source_extraction.cffcc252-1fc9-442d-873a-9c40b31d105e`이 완료됐고 READY 제안 파일 23201바이트를 확인했다. 절7·절차0·단계0·warnings8·rules5이며 causes/evidence/failure_modes는0이다. 사람 검토·적재 전이다.

| 묶음 | 원문 구절·조건 | 실제 제안 및 경고 | 판단할 내용 |
|---|---|---|---|
| 1. 구매 SOP 추출 범위 | PR-7.6은 PUR-11/12/13의 명시 SOP3개와 각각5단계를 갖는다. **“정비를 언제 어떻게 할지는 정비 지침에 따라 따로 판단한다.”** | procedures=[]다. 경고1 및 page_review는 구매·발주 절차가 운전/점검/정비/고장조치 범위에 속하는지 불명확하여 지시대로 제외했다고 밝힌다. 번호·순서·승인 문장은 PR-7.6 excerpt에 보존했다 | 실제 원문에 절차가 없는 것과 추출 범위에 따라 구조화 절차를 제외한 것을 구분한다. C 발주 지식을 재추출·적재 완료로 표시하지 않는다. 범위 판단을 검토에 남긴다 |
| 2. ERP 발주와 구매요청 연결 | PR-7.6은 ERP 발주 작성·금액 확인·통지·입고 검사를 명시한다 | 경고4는 ERP 발주를 기존 PR_CREATE 구매요청 코드로 대응시키는 제안이라고 밝힌다. 규칙은 구매요청 코드 검사로 범위를 제한한다 | 발주와 구매요청의 실제 객체/단계가 같은지 검토한다. 코드 제한만으로 실제 ERP 발주 구현이나 원문 절차 실행을 보장하지 않는다 |
| 3. 건별 검사 비용과 월 지표 | PR-7.4: 불량률>10% 공급사에는 전수 검사·비교 비용20만원 추가 | 경고5는 PENALTY로 표현했지만 총비용 지표가 월 단위여서 건별 비용과 집계의 대응을 검토해야 한다고 밝힌다 | 비용의 단위·집계 범위를 확인한다. 감점 제안을 검사 실행/완료로 표시하지 않는다 |
| 4. 비교·재고·입고 조건 | 재주문점/목표 재고, 총비용과 불량1건250만원 손실, 분할 발주 금지, 로트/검사 합격/납기 지연 보고. 긴급 절차는 전체 견적 최단 납기 공급사 선택 **뒤** AVL 검사 | 경고6은 수량·예약분·로트·합격·분할·입고 지연 입력이 없어 일부 조건을 원문에만 보존한다고 밝힌다. 경고7은 승인 공급사부터 먼저 걸러 선택하는 순서로 바꾸지 않았다. 경고3은300만원 초과를 추가 보고로 읽고 구매 담당 승인1회를 유지한다 | 원문 보존과 실행 가능한 입력/규칙/업무 절차 구현을 구분한다. 승인 횟수·공급사 선택 순서·실제 재고/입고 의미를 자동 보완하거나 바꾸지 않는다 |

**후속 결과:** 위 신규2.4 실제 Sol 재추출에서 구매 절차 누락을 해결했다. 최초2.3 제안의 절차0과 원문 보존은 범위 결함의 이력으로 남기며 현재 사용자 판단 대기로 되살리지 않는다.

세 문서 실제 추출 로그는 [manual-extraction-sol.log](D:/work/study/hyd-iot-edu/.evidence/overnight-20261012/manual-extraction-sol.log)와 모델 전환 전 HM-8의 `manual-extraction-windows.log`에 남아 있다. 추출 제안 생성3건과 사람이 검토한 지식 적재0건은 서로 다른 상태다.

취소 경위는 [astra-cancel.json](D:/work/study/hyd-iot-edu/.evidence/overnight-20261012/astra-cancel.json)과 [astra-close.json](D:/work/study/hyd-iot-edu/.evidence/overnight-20261012/astra-close.json)에 보존한다. 현재 실제 B는 causes=[]·PREVENTED_BY 부재로 자율보류이며 HM-8 제안 생성으로 B 지식 부족이 해소됐다고 주장하지 않는다.
