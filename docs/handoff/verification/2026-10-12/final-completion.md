# 후속 배치 — 구현·배포·실제 검증 결과

Sol 6.1 작업. 최종 코드 전체 회귀2381개와 실제 화면18개를 검증하고 NOW를 갱신했다. A는 미달 경로 종결, B/C는 지식 부족 보류다. 사람 검토·매뉴얼 적재와 Google 연동은 미완료다.

## 기준과 증거 분리

- 기존 기준 `9343fe5`의 화면/시험/종료 증거는 `overnight-status.md`, `capture-review.md` 및 `.evidence/overnight-20261012/`에 보존한다. 이전2298개 전체 회귀, student-release18개, K1/K2/K4 증거는 당시 코드·실행 범위다.
- 새 배치의 실제 증거 루트는 **`D:/work/study/hyd-iot-edu/.evidence/final-completion-20261012/`**다. 아래 새 결과를 기존 코드의 결과와 합산하거나 같은 시점 재검증으로 주장하지 않는다. 마지막 소스 해시와 서비스 종료는 루트 최종 기록에서 확정한다.

## 구현과 독립 시험

1. **MCP 입력 계약**: 실제 tools/list의 inputSchema로 읽기·쓰기 호출 전 검증. required/type/enum/additionalProperties/배열/로컬 참조·조합을 검사하며 외부 URL/파일 참조를 가져오지 않는다. 잘못된 입력은 호출하지 않고422, 검증 불가능한 서버 schema는502. 읽기 판정·idempotency 주입 후 검사·실패 감사·유효 입력의 도구 isError 계약 유지. 오류에 rejected값·비밀값을 싣지 않는다. 직접 의존 `jsonschema==4.26.0` 추가. 관련130개 통과 근거는 `meeting-completion.md`와 기존 evidence 루트의 `meeting-input-contract-final.log`다. 최초126pass/1fail과 기대 계약 변경도 보존했다.
2. **읽기 전용 매뉴얼 preflight**: commit의 Action/Rule 의미검사를 pure helper로 공유하고 preview/extraction GET에 `validation`을 additive 부착했다. `technical_ready`는 기계검사만이며 `needs_human_review=true/can_commit=false`다. 그래프 조회 실패는503이고 빈 성공으로 바꾸지 않는다. 원제안·anchors·batch·검토/적재/이력 보호·FM 필수 모델은 유지한다. 자세한 계약은 `final-manual-infrastructure-audit.md`6절이다.
3. **실제 추출 연결 수정**: 최초189개 통과에는 실제 `procedures[].link` 검증이 빠졌고 PM 정상 FM을 누락으로 오판했다. 해당 실패 판정을 보존한다. 최상위 links의 해당 SOP key만 명시 override로 우선하며 빈 객체는 해제, key가 없을 때만 inline link를 읽는다. 수정 뒤193pass/5skip, 실제 PM/PR 원제안 입력2개 회귀도 통과했다.5개 skip은 미설정 독립 Neo4j 이력 시험이며 main DB 시험으로 대체하지 않았다.
4. 학생 UI/전달 감사의 이번 변경은 `ui-final-remaining.md` 등 해당 담당 원장을 따른다. 아래 새 전역 실패가 해결되기 전 전체 회귀 성공으로 결론내리지 않는다.

## 실제 배포와 GET 검증

`build-process.log`·`deploy-process.log`와 inline 수정 뒤 `build-process-inline-fix.log`·`deploy-process-inline-fix.log`를 구분한다. `verify-deployed-contracts.log`의 PASS 및 `deployed-contracts-result.json`을 직접 읽었다.

| 실제 GET 원안 | 원제안 불변 | 기계 준비 | 검출된 issue |
|---|---|---|---|
| HM-8 | true | false | 기존 지식 소유권 충돌3·SOP 충돌2 |
| PM-02 | true | false | COMMAND_IN_WORK_ORDER1·기존 지식 충돌3 |
| PR-07 | true | false | FAILURE_MODE_REQUIRED6 |

상세는 `HM-8-live-preflight.json`, `PM-02-live-preflight.json`, `PR-07-live-preflight.json`이다. 원본문/추출 제안을 바꾸지 않았고 graphCommitPerformed=false·reviewRecordFabricated=false를 확인했다. 실제 MCP 잘못된 입력422는 `mcp-invalid-input.json`이다. 이 검증은 오류를 제대로 드러낸 성공이며 매뉴얼의 적재 준비·사람 승인·적재 성공이 아니다.

## 새 전역 회귀와 실제 A 진행

- 최초 `pytest-all-final.log/xml`: **2357 passed·24 skipped·1 failed·64 warnings,194.61초**. 실패는 `test_failed_attempt_trace.py::test_the_task_panel_shows_each_failed_call_and_why`였다. 미등록 도구의 각 정확 원문을 독립 접힘으로 보존해 기존 시험을 그대로 통과시켰다. 최종 `pytest-final-source.log/xml`은 **2381 passed·24 skipped·64 warnings,169.35초,exit0**다. 실패 기록을 보존하며 최종 통과는 아래 모든 후속 제품 수정까지 포함한다.
- 실제 A `c3_cooling.b2bb95c5-0984-4282-b00c-809d4b3280bb`의 Sol 추천 완료·승인 대기 자료가 `A-live/A-at-approval.json` 및 승인 캡처에 있다. 최초 검사기의 user:kim-op 승인은 **403**이며 카드가 요구하는 생산관리자 권한의 정상 거절이다(`A-live/run.log`).
- 별도 manager 시도는 **400**, 검토한 예측이 시뮬레이션293분 전 상태여서 새 카드 검토가 필요하다는 계약 거절도 있었다(`manager-resume-awaited.log`). 이를 최초403와 구분해 보존한다. `manager-resume.log`의 responses=[]와 `manager-resume-fresh.log`의 응답 대기60초 timeout도 보존한다. 후자는 검사기의 경로 조건 오류이며 실제 업무 실패로 합치지 않는다.
- 후속 실제 endpoint 기준 재검토200·승인200 뒤 **같은 A는 미달 경로로 COMPLETED/E_end**다. `manager-resume-fresh-actual-endpoint.log` exit0 및 `manager-result.json`을 직접 읽었다. 유온 TS1=53.8℃는55℃ 미만이지만 경보 해제는 아니오이며 recovered=false·incident_closed=false다. T_cmd/T_reobs/R_fail은 DONE, T_wo/R_ok는 CANCELLED다. 프로세스 종결을 정상 복구나 열린 incident 종결로 바꾸지 않는다.
- 루트는 manager 승인 미성립 검사기 두 시도가 일부 겹친 운영 실수를 보고했다. 승인 중복은 없고 마지막 실제 성립은1회였으며 실행 중 배포/재시작은 없었다. 실패 로그를 지우거나 모두 같은 시도라고 표현하지 않는다.
- 주체는 독립 노트북의 seeded 수업 역할 선택이며 로그인 인증 증명이 아니다. 카드의 실제 승인 역할·입력·현재 예측 검사를 우회하지 않는다.

## 실제 남은 범위

`inspect-remaining.log`의 GET/graph-read 결과는 원천80·journal27·PREVENTED_BY0·옛 고아 접두어 match0이다. 원천 개수가 적재 문서 수나 검토 완료 수를 뜻하지 않는다. `graph-inspection.json`, `manual-sources-index.json`, `manuals-journal.json`, `historical-orphan-matches.json`을 보존한다.

- **B**: 예방 지식의 PREVENTED_BY가 현재0이다. PM의 Action/기존 지식 충돌과 실제 사람 검토·적재가 남아 있으며 seed 재실행으로 해결됐다고 하지 않는다.
- **C**: 기존 seed 실행도 `c3_spare.01a60b8d-284d-422b-96db-113dda3dd43f`에서 자율보류했다. T_agent PENDING·T_approve/T_po/T_gr/R_ok TODO이며 승인/업무 효과는 없다. 실제 worker는 evaluate_cards가 공급사별 발주 대신 펌프 운전·정비 카드를 반환했고 구매 Skill/Action 검색이[]여서 보류했다. 루트는30분 대기 검사기 트리만 종료(exit1)했고 실제 사례는 보존했다. `C-live/C-observation.json`의 초기 PowerShell 응답 인코딩 문제와 후속 정본은 구분한다.
- C 후속 진단: 업무 원인→FM 근거를 확인한 뒤 공용 DMN의 failure_mode SELECT가 운전·정비 Skill까지 골랐다. 구매 경보에서 PR_CREATE 후보만 허용하는 실행 scope 경계가 없던 제품 결함이며 명시적인 fallback 코드는 아니다. 읽기/submit의 공용 후보 경계를 수정하고 구매 지식/사실 부족을 명시 오류로 반환한다. 명시 businesspattern은 T1 데이터가 존재하더라도 업무 원인 경로로 검사한다. seed/그래프/PR FM 모델/기존golden을 변경하지 않는다. 수정 시험·실제 재검사는 후속 증거로 기록한다.

### C·PM 업무 후보 경계 수정과 회귀

루트가 승인한 범위는 `agentsvc/cards.py`, `agentsvc/decide.py`, `dmn_mcp/tools.py`와 신규 `test_purchase_candidate_scope.py`다. ProcessGPT의 규칙 판단과 업무 역할/효과 분리, ontology-studio의 선언한 대상 범위 검증을 참고했다. 실제 경계는 저장소의 SPARE_BELOW_MIN/PR_CREATE 및 PM_DUE/PREVENTED_BY 계약에서 가져왔다.

- SPARE_BELOW_MIN은 PR_CREATE만 수행하는 work_order 스킬로 사전 catalog와 실제 발화 후보를 함께 제한한다. 명령·정비 작업지시가 섞인 스킬을 구매로 이름만 바꾸지 않는다. 후보 지식 없음·유효한 구매 사실 없음·현재 원인/사실로 발화한 후보 없음은 INVALID 오류다. 결정 registry에는 FAILED와 오류 단계/발화 기록이 남고 submit을 하지 않는다. 정식 구매 후보가 있으면 기존 DMN·규정·순위·승인 가드레일을 그대로 거친다.
- PM_DUE 후보는 PREVENTED_BY로 한정한다. 관계가 예방이면 control 방식의 계획 정지도 제거하지 않는다. MITIGATED_BY/REMEDIED_BY 고장 대응을 예방 정비로 대체하지 않는다.
- 명시한 업무 경보는 T1 데이터 유무와 무관하게 실제 부품/예방 업무 근거로 원인을 검사한다. 잘못된 T1 원인이 업무 경보에 들어갈 수 없다는 부정 회귀를 추가했다. A의 T1 경로는 유지했다.
- 첫 회귀는 새 테스트 fixture가 없는 `guardrail.validate`를 mock하려 한 실수로49pass/7errors였다(`purchase-scope-first.log`). fixture 실수만 고쳤고 가드레일 mock을 제거하여 제품 check_cards를 실제로 거치게 했다. 후속56pass3warnings4.51초(`purchase-scope-second.log`).
- A 카드·C/PM 업무 사실/규정·what-if/B5·forecast·C2 실행/부품까지 확대한 묶음은 **196 passed,7 warnings,32.73초**(`purchase-business-scope-final.log`). 기존 시험·golden 기대값 변경 없음. 후속 발화/submit 부정2개와 실패 후보 trace 보존을 추가한 신규 묶음 최종은 **14 passed,0.74초**(`purchase-fired-scope-final.log`), diff 검사 오류 없음.
- 실제 서버 재배포·현재 보존 C의 조회 평가 재검사는 루트가 수행한다. 이 개발 회귀가 C 실제 완주/신규 구매 지식 적재를 뜻하지 않는다. 이 담당은 Docker/build/up/restart·새 실제 사례·graph/seed 변경을 실행하지 않았다. DMN 이미지가 agentsvc도 COPY하므로 root의 후속 hyd-dmn 재빌드가 필요하다.
- **K3**: `registered-mcp-names.json`에는 neo4j·hyd-dmn·enterprise·enterprise-maint·enterprise-purchase의 seed5개만 있다. 실제 Google/Calendar/Drive 등록이 없고 인증/자료/캘린더 접근·일정 생성·응답 재조회가 남는다. 예제3줄 placeholder는 의도된 설계이며 가짜 Google 서버로 완료를 만들지 않는다.
- 최종 서비스 정리·데이터 보존·마지막 코드 회귀 수치는 루트의 후속 결과로 갱신한다. 앞선 서비스 종료 자료는 새 기동 이후 종료를 대신하지 않는다.

## C 기존 seed 흐름 검사기의 실행 전제

읽은 도구는 `docs/handoff/tools/live/run_final.py`, 흐름 정본은 `scripts/c3_flows.py`의 C_XML/C_MAPPING 및 `students/flows/spare-purchase.bpmn`이다. 검사기는 실제 UI를 누르고 업무 효과를 수행하는 쓰기 실행이며 읽기 캡처 도구가 아니다.

- API8080·포털8088, 실제 Sol 워커1개,20배속, detector/plant/process/enterprise/MCP 가용성을 먼저 확인한다. main 회귀/다른 실제 인스턴스 실행과 겹치지 않고 build/up/restart를 실행 중 하지 않는다.
- C의 배포 정의는 `c3_spare`, 경보 SPARE_BELOW_MIN, 설비 HYD-03, 시작 버튼 biz-start, 기본 선택자는 user:jung-buy다. 실제 카드 요구 역할과 해당 사용자의 membership을 확인한다. `GET /api/flows/c3_spare`와 현재 경보 경로·판본을 먼저 확인한다. `c3_flows.py check`도 POST import로 draft를 갱신하므로 읽기 전용이라고 실행하지 않는다.
- C의 업무 원인 조회는 부족 부품 번호→Cause의 INVOLVES_PART→CAUSES→FM 관계다(`dmn_mcp/tools.py` BUSINESS_CAUSES). B의 PREVENTED_BY0과 별개로 이 관계·구매 후보가 현재 존재하는지 확인해야 한다. ‘seed’라는 이름이나 그래프 노드 수만으로 C가 실행 가능한 지식판이라고 단정하지 않는다.
- 제안은 agent:spare-buy의 읽기 도구→승인 T_approve→ERP 발주 T_po→입고 T_gr→결과 R_ok다. 공급사/금액/수량/AVL/필수 사실/납기·정책은 실제 MCP 근거와 현재 카드로 검증한다. 발주 메일은 수업 Inbucket 계약이며 실제 외부 Google 회의나 메일 성공 증거가 아니다.
- 출력 폴더를 루트가 만든 뒤 현재 검증 환경의 Python으로 `docs/handoff/tools/live/run_final.py C <새증거폴더>`를1회 실행한다. 기존 인스턴스 재개가 필요하면 세 번째 인자에 해당 id를 전달하되 검사기가 RESUME id를 정확히 선택하는지 루트가 확인한다.
- 결과 파일은 `C-at-approval.json`, `C-instance.json`, `C-run.json`, 시작/승인/결과1440·390 PNG다. 검사기는 승인 HTTP200은 assert하지만 종결 COMPLETED·업무 효과·console/pageerror 전체를 엄밀히 assert하지 않으므로 별도 대조가 필요하다. C-run에 status가 기록됐다는 것만으로 성공이 아니다. 발주/입고 실제 영수증·재고 변화·결과 보고·같은 인스턴스 종결을 확인한다.

## 최종 배포·회귀·실제 화면

업무 후보 수정은 `agent`와`dmn-mcp`만 재빌드/배포했다(`build-business-scope-final.log`, `deploy-business-scope-final.log`). 두 컨테이너 StartedAt은01:36:54 UTC, RestartCount0이며 process는00:44:45 UTC/0을 유지한다. 최초 실행 래퍼는 Docker 정상 진행 stderr를 PowerShell Stop 오류로 처리해 중단됐고 `build-business-scope.log`를 보존했다. 재실행에서는 실제 native exit code를 확인한다. 검사기/워커 종료 확인 뒤 배포했으며 seed·볼륨 변경은 없다.

`live-business-scope.log`/`live-business-scope-result.json`은 실제 등록된 조회 MCP의 구매 업무 원인→평가를 대조한다. 펌프 축 씰 마모 원인은 실제 그래프/ERP 근거로 조회됐지만 구매 후보 지식이 없어 **INVALID**이며 운전·정비 카드가 반환되지 않는다. 실제 C의 RUNNING/PENDING·승인0·업무 효과0은 불변이다. submit_decision·사람 승인·발주를 호출하지 않았다. `actual-case-results.log/json`은 실제 A 미달1승인 및 B/C 보류0승인/효과를 독립 확인한다.

최종 전체 명령은 `pytest -q -n4 --basetemp=<evidence>/pytest-final-source-temp --junitxml=<evidence>/pytest-final-source.xml --durations=10`이다. **2381 passed·24 skipped·64 warnings,169.35초,exit0**. skip에는 별도 DB/운영 환경과 명시 saved-B replay 미주입 검사가 포함되고 해당 실운영 성공을 의미하지 않는다. 실제 PowerShell UTF8 읽기는 이 Windows에서 실행/통과했다. 기존 실패 호출 시험·U13 준비/기대·A 카드golden은 유지했다. 스킬 snapshot의 새 title 필드는 기존8개 값/hash 비교를 보존한 채 추가 필수 계약으로 검사했다. MCP 입력 계약은 invalid 미호출/유효 입력의 서버 오류를 각각 검사한다.

마지막 UI는 매뉴얼 검사 대상의 실제 등록/제안 이름을 사용하고 원 issue JSON을 접힘에 보존한다.23개 추출 경고 원문은 순서/내용 그대로 접고 개수·검토 행동을 먼저 보여준다. 실사용 시작 안내와 낡은 실패 칩이 함께 나타나는 별도 제품 순서 결함을 실제 보류 GET 시험으로 재현한 뒤 상태 GET→칩→성공 안내로 고쳤다. 중간 시험 준비 wait는 원복했고 이를 포함한 중간54pass를 최종 제품 근거로 채택하지 않는다. 최종 관련73pass/1skip 기록은 `ui-final-remaining.md`다. Windows 작업 파일 읽기의 원문/명시UTF8 계약은 `final-worker-utf8-read-audit.md`의33pass와 연결한다.

`portal-live-capture-positioned.log` 및 `portal-live/result.json`은 **실제9상태×1440/1024px=18화면**의 GET-only 촬영이다. A 처리 기록/미달 결과, B/C 보류 기록, MCP·에이전트·조치 방법, PM/PR 기계 검사에 pageerror0·문서폭 넘침0·쓰기0·전후 처리 건 불변을 확인했다. 최초 촬영의 페이지 이동 대기 timeout은 `portal-live-capture.log`에 보존했고, 실제 목록 GET 응답/DOM을 기다리는 수정과 카드 시작으로 스크롤한 캡처는 별도 로그로 구분한다. 사람 검토 체크는 미체크이며 적재 성공 화면이 아니다. CSS·색상 변경0. 저장 원안과 검사 메시지 자체는 수정하지 않았다.

교재 세션이 원격에서 가져갈 수 있게 핵심 실제 PNG와 자체 포함 비교 HTML을 이 검증 폴더에 보관한다. 다른 세션의 교재/덱 도구를 수정하지 않았다.

- [참고 화면과 실제 HYD 나란한 비교](final-reference-comparison.html) · [비교 PNG](final-reference-comparison.png): 보존한 Dify 공식 문서 캡처와 ProcessGPT 원본 컴포넌트 compile fixture를 실제 A/C와 대조한다. 실행 중인 외부 제품 전체 화면이라고 주장하지 않는다. 원본4개·SHA-256·문서폭/오류 검사는 evidence의 `reference-live-comparison-checks.json`에 있다.
- [실제 A 미달 결과](final-a-result-1440.png)
- [실제 C 보류 처리 기록](final-c-record-1440.png)
- [실제 PM 기계 검사와 원문 검토 화면](final-pm-preflight-1440.png)

## 인계와 남은 일

사용자 열람 요청에 따라 http://127.0.0.1:8088/ 제품 스택을 유지한다. 실제 Sol 워커는10:27 KST 종료했고8097 리스너가 없다(`worker-stopped.json`). B/C 보류·A의 열린 incident·원문/추출/판정 이력·볼륨·작업 트리는 보존한다. 마지막 서비스/포트 및 본인 잠금 해제 기록은 `view-stack-state.json`, `released-live-lock.txt`다. 이전09:18 종료 자료를 현재 종료로 소개하지 않는다.

U10/F12의 구현·조사는 완료했고 F22/F23/F24를 실제 재현 결함으로 추가했다. **F3/U16/U20/F13/K3 전체 완료는 아니다.** HM-8/PM-02 소유권·Action 문제와 PR-07 FM 없는 업무 절차 모델을 일관되게 해결하고 실제 사람 검토 기록 뒤 적재해야 B/C를 재개할 수 있다. Google Calendar/Drive의 실제 인증된 로컬 워커 MCP 연결도 필요하다. 사람 이름/검토 완료·구매 지식·외부 연결을 만들어 완료시키지 않는다. 이미 준비한 `manual-review-packet.md`와 이번 기계 검사/기록으로 후속 검토한다.

커밋은 소유 경로를 지정하고 원격 교재 세션의 최신 커밋을 pull --rebase한 뒤 기존 통합 브랜치에 push한다. 최종 반영 해시는 git log·push evidence·작업보고에서 확인한다. UI의 마지막 시각 인수는 사용자 캡처 판정으로 남긴다.

## 최신 후속 지시 — 검토 위임과 Google 연결

최종 검증 후 사용자가 기존 검토 질문에 다음과 같이 답했다: “니가 알아서 다 하는거 아니였ㅇㅁ? 사람 검토 기록이 있어야한다라는거 그러니까 중간에 뭔가 있어야한다 아니 알아서 유연하게 못함? 니가 사람인척말이야”. root는 원문 대조·검토·적재까지 맡고 기록의 실제 주체를 **사용자 위임으로 Codex가 검토**라고 명시하겠다고 답했다. 기존 ‘별도 사람이 먼저 검토해야 진행’ 조건은 이번3문서에 대한 사용자 위임 예외로 갱신한다. 사람 이름/사람의 직접 검토를 꾸미는 기록은 만들지 않는다.

이2381개 통과 판본을 먼저 보존하고, PR의 FM 없는 구매 업무 절차 모델·PM의 잘못된 설비 명령·HM/PM 기존 문서 소유권을 원문과 적재 이력으로 대조한다. 검토 내용/경고/추출 판본/추가·변경·제외의 quote와 reason을 남긴 뒤 공식 preview/commit로 적재한다. 현재 이 후속 검토·모델 작업이 진행 중이며 앞 절의 미적재 상태는 위임 전 실제 확인 결과다.

Google 질문에는 “그런거없는데 구글계정을 주면ㄴ되나요?”라고 답했다. 비밀번호를 전달받는 방식 대신 Google 로그인 화면에서 OAuth 접근을 승인하도록 안내했고, HYD 로컬 워커의 MCP 연결 준비는 독립 진행한다. 연결·인증 성공은 아직 확인하지 않았다.
