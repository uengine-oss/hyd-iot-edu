# 실제 캡처·참고 비교 — 2026-10-12

근거 루트는 `D:/work/study/hyd-iot-edu/.evidence/overnight-20261012/`다. 아래 실제 스택 캡처·실제 컴포넌트 시험 렌더·fixture 화면을 구분한다. 이미지를 저장한 사실은 해당 화면의 준비 검사 통과나 사용자 최종 시각 승인과 다르다. 교재 파일은 수정하지 않았다.

## 전체46화면

[live-release](D:/work/study/hyd-iot-edu/.evidence/overnight-20261012/live-release/)에는 23개 탭의 1440/1024 캡처 46장이 있다. `console.json`은 console/pageerror 0·ignored 0이며 `layout.json`은 문서폭 넘침 0이다. ontology 1440의 SVG/하위 요소 경계 초과 12개와 `residue.json`의 영문/내부 이름 잔여는 보존한다. 따라서 잘림 없음·완전 국문화·UIUX 최종 승인으로 쓰지 않는다.

## U16·K2 상세 캡처

최신 실제 캡처는 [target-capture-final](D:/work/study/hyd-iot-edu/.evidence/overnight-20261012/target-capture-final/)이다. `checks.json`의 시스템·에이전트·조치 방법·매뉴얼 목록·개인 처리 기록·질문 결과·학생 지식 상세 **7개 기능 준비 검사 모두 passed=true**, 각 horizontal_overflow=false를 확인했다. `student-graph.json`(42588바이트)과 학생 상세 PNG도 보존했다. 다만 전체 `summary.json`은 passed=false이며 검사기 exit1이다. 원인은 3종 health의 no-cors 요청 ERR_ABORTED 반복으로, 기능 통과와 네트워크 결과를 함께 기록한다. CDP 진단은 3개 fetch가 10~19ms에 fulfilled opaque(status 0·body 없음)로 끝나고 health 12/12·console 0임을 확인했다. loadingFailed의 canceled=true에는 blockedReason/CORS가 없고 4초 timeout 전이다. no-cors 응답 본문의 취소로 분석했으며 본문 없는 opaque 응답을 제품 오류나 timeout으로 판정하지 않는다. 따라서 전체 캡처 검사 전부 통과·모든 요청 오류0이라고 쓰지 않는다.

K2는 메인이 공식 T2 loader로 `overnight-k2-20261012` namespace에 실제 65 nodes·107 relationships를 적재했고, 실제 Cypher 질문9개 모두 답함을 확인했다. 해당 이름 공간 선택→실제 학생 항목 상세는 최신 캡처에서 통과했다. 이후 공식 wipe로 그 이름 공간의65개 노드만 지웠고 cleanup.json의 remaining=0을 확인했다. `load.log`·`ask.log`·`wipe.log`와 [cleanup.json](D:/work/study/hyd-iot-edu/.evidence/overnight-20261012/k2-example/cleanup.json)이 근거다. 기준 그래프나 다른 학생 자료를 학생 캡처로 대신하지 않았다. 이후 UI에서 이 시험 이름 공간이 없는 것은 확인한 정리 결과다.

학생 namespace가 없었던 첫 시도와 조치 방법/매뉴얼 locator 오류는 아래 이력으로 보존한다. U16은 필요한 실제 화면 원본을 확보했지만 F3의 새 제안 사람 검토/적재 완료나 사용자 시각 승인까지 뜻하지 않는다. 최종 UI 이름 표시 관련 독립 브라우저 묶음은 `pytest-ui-names-complete.log` **36 passed,33.07초**다. 이 후속 결과는 앞선 전체2275개 시험과 코드 기준을 구분한다.

### 첫 캡처의 실패 이력

실제 `target-capture.py`는 읽기 전용으로 실제 API/DOM을 확인했고 데이터를 합성하지 않았다. [summary.json](D:/work/study/hyd-iot-edu/.evidence/overnight-20261012/target-capture/summary.json)은 첫 실행에서 7장 저장·전체 passed=false·준비 검사 4통과/3미완료다. `checks.json`에 URL·화면 텍스트·가로폭·조건 실패, `responses.json`에 실제 응답, `errors.json`에 요청 실패를 보존했다. 외부 서비스 health 요청의 ERR_ABORTED도 원문에 남아 있어 전체 오류 0이라고 쓰지 않는다. 이후 locator 수정과 공식 학생 namespace 준비로 최신 기능7개 준비 검사를 통과했다.

| 이미지 | 준비 검사 | 범위·남은 확인 |
|---|---|---|
| [system-1440.png](D:/work/study/hyd-iot-edu/.evidence/overnight-20261012/target-capture/system-1440.png) | 통과 | 실제 시스템 구성. 일부 health 요청 abort는 별도 원문에 남음 |
| [agents-ready-1440.png](D:/work/study/hyd-iot-edu/.evidence/overnight-20261012/target-capture/agents-ready-1440.png) | 통과 | 실제 에이전트 목록/선택 상세 준비 |
| [personal-case-record-1440.png](D:/work/study/hyd-iot-edu/.evidence/overnight-20261012/target-capture/personal-case-record-1440.png) | 통과 | 실제 student-release 로컬 읽기 흐름의 단계·MCP·Report. 개인 처리 건 JSON도 보존 |
| [question-result-1440.png](D:/work/study/hyd-iot-edu/.evidence/overnight-20261012/target-capture/question-result-1440.png) | 통과 | 실제 완료 질문과 verified MCP 근거. question.json 보존 |
| [skill-method-1440.png](D:/work/study/hyd-iot-edu/.evidence/overnight-20261012/target-capture/skill-method-1440.png) | 미완료 | `#view-skills [data-pick-skill]` 선택 locator 20초 timeout. 실패 캡처를 선택 상세 성공으로 쓰지 않음 |
| [manual-sources-1440.png](D:/work/study/hyd-iot-edu/.evidence/overnight-20261012/target-capture/manual-sources-1440.png) | 미완료 | 매뉴얼 준비 조건 20초 timeout. 원문 목록·적재 이력 준비와 실제 사람 검토/적재는 별도 |
| [student-knowledge-detail-1440.png](D:/work/study/hyd-iot-edu/.evidence/overnight-20261012/target-capture/student-knowledge-detail-1440.png) | 미완료 | 첫 실행에 요청 학생 namespace 없음. 기준 노드를 학생 상세로 대신하지 않았다. 이후 공식 T2 namespace 적재/상세 검사/정리로 확인했으며 최초 부재는 외부 차단이 아니었음 |

K2의 실제 bpmn.io 3개·오류 0 및 생성 구성 export/reset/import/export differences=[]는 별도 통과 기록이다. 학생 지식 상세는 위 첫 실행의 실패 이후 공식 T2 loader를 사용한 실제 load→ask→browser→wipe로 확인했다. 첫 이미지와 최신 성공 이미지를 구분한다.

## Dify 실제 처리 기록 비교

최신 [비교 HTML](D:/work/study/hyd-iot-edu/.evidence/overnight-20261012/dify-live-record-comparison-final.html) · [비교 PNG](D:/work/study/hyd-iot-edu/.evidence/overnight-20261012/dify-live-record-comparison-final.png) · [검증 JSON](D:/work/study/hyd-iot-edu/.evidence/overnight-20261012/dify-live-record-comparison-final-checks.json). 오른쪽은 `target-capture-final/personal-case-record-1440.png`이며 초기 비교 HTML/PNG/검증 JSON도 기존 파일명 그대로 보존했다.

왼쪽은 기존 보존 Dify 공식 History and Logs의 `a121/refs/dify-history-logs-2.png`, 오른쪽은 위 준비 검사를 통과한 실제 HYD 개인 처리 기록이다. 새 제품 그림을 만들지 않고 원본 두 PNG를 동일한 폭의 열에 배치해 Playwright로 HTML을 캡처했다. 원본 SHA-256 전후 동일, 이미지 2개 로드·pageerror 0·문서 가로 넘침 없음을 확인했다. 참고 원출처는 [Dify 공식 문서](https://docs.dify.ai/en/guides/workflow/debug-and-preview/history-and-logs)다.

Dify의 결과/상세/추적 탭과 HYD의 처리 목록/단계 상태/걸린 시간/도구/보고 본문을 나란히 확인할 수 있다. 동일 앱·완전히 동일한 디자인·사용자 승인을 주장하지 않는다. HYD 본문은 실제 read_rows 영문 키와 등록 이름을 보존하며 이 캡처로 U10/U15 완료를 선언하지 않는다.

기존 [fixture 비교 HTML](D:/work/study/hyd-iot-edu/.evidence/portal-20261012/ui/reference-comparison.html) · [fixture 비교 PNG](D:/work/study/hyd-iot-edu/.evidence/portal-20261012/ui/reference-comparison.png)는 생산 index/CSS/렌더 함수와 합성 오류 fixture의 독립 Chromium 화면이다. fixture 명시를 그대로 유지했으며 새 실제 비교로 출처를 덮지 않았다.

## ProcessGPT 실제 컴포넌트 비교

[비교 HTML](D:/work/study/hyd-iot-edu/.evidence/portal-20261011/flow-processgpt-comparison.html) · [비교 PNG](D:/work/study/hyd-iot-edu/.evidence/portal-20261011/flow-processgpt-comparison.png). 참고는 Vue3 `867e8cf`의 실제 PgCard/PgField/PgAlert/PgTextField/PgButton 원본을 Vue SFC compiler로 렌더했고 HYD는 실제 포털 폼/MemoryAPI를 연결했다. 전체 ProcessGPT 실행 앱이나 HYD 설비 완주 캡처가 아니다. 레이아웃/입력/오류 알림의 비교 근거로 연결한다.

## 메인 생성 자원 정리와 보존된 증거

`cleanup-owned.log/results.json`은 own manifests로 확인한 대상에만 38개 공식 API 요청을 수행했고 모두 성공했다(이미 없는 404 허용). 흐름 11대상(이미 삭제 포함)·에이전트 5·MCP 5를 정리했으며 질문 목록도 모두 이번 작업 소유임을 확인한 후 reset했다. 기존 학생 자료의 전체 구성 reset이나 DB 수동 삭제는 수행하지 않았다. 실제 student-release/K1/K4의 API 원문·로그·PNG는 증거로 보존하지만 생성 자산과 질문은 현재 제품 목록에 더 이상 남아 있지 않다.

처음 실패한 HM-8 추출5317d3aa…도 공식 close로 COMPLETED/closed-by-human을 확인했다(`failed-extraction-close.json`). 실제 B의 열린 incident/PENDING은 보존한다. 이 문장의 작성 당시에는 서비스 종료 확인 전이었다. 이후 최종 정리를 아래 근거로 확인했다.

health의 CDP 진단은 `cdp-health-probe/result.json`·events.json·errors.json에 보존한다. raw ERR_ABORTED가 남은 전체 캡처 summary passed=false/exit1은 지우거나 성공으로 고치지 않았다. 기능 7개 pass와 health 12/12 진단을 별도로 기록한다.

## F21·이름 표시 후속 최종 6화면

[ui-f21-final](D:/work/study/hyd-iot-edu/.evidence/overnight-20261012/ui-f21-final/)은 ontology/flows/agents 각1440/1024, 총6화면이며 검사기 exit0이다. console/pageerror0·ignored0·문서폭=viewport를 직접 확인했다. ontology/flows 잔여 검색은0이고 agents에는 과거에 작성한 read_only 시험명1건을 보존했다. 특정 시험명 하나를 위한 번역은 최종 검토에서 제거했다(`pytest-ui-name-review.log`:3pass).

F21 실제 API는1592→636으로956개 내부 메타데이터를 조회에서 제외했다. DB 저장수는420/428/50/27/31로 불변이며 업무 사례와 출처는 유지된다. 캡처 문서 높이는10731/10804px지만 UNLOCK_CSS로 지도 스크롤 제한을 해제한 결과다. 실제 일반 화면의 문서 높이는900px이며 SVG 경계12개를 접근 불가한 잘림으로 판정하지 않는다.

최신6화면과 이전46화면 전수 캡처·target7개 기능 준비 검사를 각각 보존한다. Dify 최신 비교는 target-capture-final의 실제 처리 기록 원본이다. F21 지도 변경을 이유로 새 제품 시안을 만들지 않았다. 최종 사용자 시각 판정은 별도다.

## SVG 내부 스크롤 실제 접근 검증

`ontology-scroll-probe/result.json`과 rightmost-selected-1440/1024.png에서 의도된 지도 내부 스크롤을 확인했다. 실제1440/1024 폭의 지도는1111/711px·scrollWidth1354px·overflowX/Y=auto·maxHeight648px이며 일반 DOM의 documentHeight는900px다. 약10k 캡처 높이는 UNLOCK_CSS로 내부 스크롤을 펼친 결과다.

두 폭 모두 오른쪽 외기 온도 노드까지 가로 이동한 뒤 클릭해 상세 제목·aria-selected=true·nodeFullyWithinMap=true를 확인했다. Enter로 선택 해제도 통과했다. role=region·tabIndex0·가로/세로 이동 안내 ariaLabel이 있다. 이 probe는 pageerror만 감시했고 오류0이었다. console0은 별도 ui-f21-final의 증거이며 이 probe가 console listener까지 가졌다고 쓰지 않는다.

SVG 경계 초과12개는 접근 불가한 잘림의 증거가 아니며 의도된 스크롤 영역의 경계값이다. 전체 지도 PNG와 실제 상호작용 가능성을 구분하고 사용자 시각 판정은 별도로 남긴다.

## 최종 서비스 정리 — 02:53 KST 확인

`services-off.json`은 runningContainers=[]·listeners=[]이고 `cleanup-final.json`은 Docker Desktop/backend 프로세스0·liveLockExists=false다. compose·독립 Neo4j·학생 MCP8311·두 Supabase를 종료했고 Supabase는 backup=true로 데이터를 보존했다. 볼륨 및 작업 트리를 삭제하지 않았다. 본인 LIVE_LOCK의 내용을 보관한 뒤 해제했다.

독립 Supabase 첫 종료는 PATH에 docker가 빠져 실패했고 PATH 보완 후 재실행했다. main Supabase 첫 --workdir it/supabase는 project_id_filter=supabase로 대상이 달랐으며 Docker 실측 후 --workdir it로 hyd-iot-edu를 종료했다. 실패/재시도 원본 로그를 보존한다.

종료 전 `final-scenario-state.json`의 실제 B는 RUNNING1/에이전트 PENDING이며 열린 incident와 함께 보존했다. 실제 시나리오 완주나 지식 부족 해소를 주장하지 않는다. 코드 반영 해시는 git log와 최종 보고를 참조한다.
