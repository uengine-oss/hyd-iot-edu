# 실제 완료 조건 후속 대조 — 2026-10-12

이 기록은 기존 성공·실패를 유지하면서 남은 요구가 제품 결함인지, 이미 존재하는 실제 근거인지, 외부 업무/인증 준비인지 구분한다. 기존 시험과 전체 회귀를 반복하지 않았다. U10의 새 문서 선택 동선은 최종 실제 GET 전용 native18항목 통과·쓰기/오류0·소스 불변을 확인하여 해당 변경 검증을 완료했다.

## 요구별 현재 판정

| 요구 | 실제 확인 근거 | 판정과 남은 조건 |
|---|---|---|
| U10 문서 지정/재검토 | 새 named selector·기본 현재 판본·동명/미상 문서/원문 전용 선택과 preview 중 변경 잠금, 정확한 preview source 유지 구현. 최종 실제GET native18항목 통과·쓰기/오류0·소스 불변 | **해당 변경 검증 완료**. source 변경은 index.html/hitl.js/새 선택 시험3경로만. 새 실제 업로드·적재·LLM 실행을 했다고 주장하지 않음 |
| U16 공식 원문 검토/적재 화면 | HM-8/PM-02/PR-07 실제 승인 기록과 현재 installed history1440/1024, 현재 GET의12체크 | 공식3종 실제 적재 화면 하위조건은 확인됨. Codex 사용자 위임 검토이며 사람이 검토한 척하지 않음. 사용자 최종 시각 인수는 별도 |
| U16 과거173쌍 기록 | immutable Git의 numbered/source SHA/after SHA/observation173개 ledger 복구 | **historical ledger173/173 FOUND**. 지정된 옛 PNG 폴더는 조사 경로에서 없음. 이번에173PNG를 모두 다시 읽었거나 현재 소스로173화면을 재승인한 것이 아님 |
| U20 실제 A/B/C | A 부정 결과 프로세스COMPLETED/incident_closed=false, B 실제PENDING, C 교육용ERP 발주·입고·가용7/COMPLETED | 최종 실라버스 온라인95행은 물리복구 성공을 필수로 하지 않으므로 A는 유효한 부정종결. B를 임의 재고로 해피패스로 바꾸지 않음. 외부회의·전체운영인수는 별도 |
| F3 정비 원문/적용 정책 | 공식3종 source/history와 PM-02 실제 원문 GET→정비 차례→재고 연결 | 원문 적재/현재 정책 근거 확인. B 필터 미확인은 조회 mapping 결함이 아니라 실제 ERP master/stock 부재이며 작동유 미상은8,000h 묶음에만 추가 적용 |
| F12 기동 지연/고아 문서 | [기존 원인 대조](../final-manual-infrastructure-audit.md): 옛16분 컨테이너 생성 대기와 현재seed59.719291초/read-back17/0, 현재 원천80개 접두어match0 | 조사 완료. 옛16분의 원인을 해결했다고 주장하지 않으며 이번에seed/삭제/전체시험을 반복하지 않음 |
| F13 운영 수용 범위 | local read-only 설정/학생 흐름과 기존 실제A/B/C·F27 소비자 검증 | 로컬 기능 범위는 근거 있음. 외부 계정/회의실·수업 운영·전체사용자시각인수는 검증되지 않음 |
| K3 실제 Google회의 | 현재 ChatGPT Drive앱 인증 읽기 성공, HYD등록5개 Google0, 최초 회의 설계는 실제Google일정→확인→보고 요구 | **실제HYD Google 인증·실행 미검증**. 앱 연결은 HYD 인증 handoff가 아니며 generic/local 성공으로 대체하지 않음 |

## 실제 화면과 기존 검증 범위

공식3종 현재 installed history [1440 PNG](../final-delegated/knowledge-history-1440.png)·[1024 PNG](../final-delegated/knowledge-history-1024.png)는 루트가 원래 이미지를 열어 확인했다. 초안 제안 화면과 실제 적재 화면을 혼동하지 않는다. [current-installed-manual-proof.json](current-installed-manual-proof.json)은 현재 GET200/31 history rows에서 공식3종 각4개, 총12체크를 보존하며 [collect-current-manuals.py](collect-current-manuals.py)는 수집 방법을 남긴다.

[과거173 ledger](visual-gates/historical-173-ledger.json)와 [대조 audit](visual-gates/visual-gates-audit.json)은 복구된 당시 기록이다. 앞선 “173ledger UNVERIFIED”는 이 후속 조사로 **과거 기록 FOUND**로 정정한다. 현재 전체173시각 재검토나 사용자 인수까지 완료되었다는 뜻은 아니다. 기존 F27 및 이전 실패/경고/별도 범위는 [앞선 후속 기록](../k3-and-record-followup/README.md)을 그대로 사용한다. native96과Trace14를 합산하지 않고 source807동결을 새 전체2673회귀로 표현하지 않는다.

## U10 실제 native와 첫 실패 보존

[native 최종 결과](manual-selection/native-final/result.json)는18항목 모두 통과했고 source3개 SHA가 시작/끝 동일하다. [문서 이름 선택1440](manual-selection/native-final/form-named-document-1440.png)·[preview 잠금1024](manual-selection/native-final/form-review-document-locked-1024.png)를 루트가 직접 열어 확인했다. 나머지1024/1440PNG, initial-options, 실제 preview identity도 원본 그대로 보존하며 [copy-provenance.json](manual-selection/copy-provenance.json)에11파일 source/bytes/SHA 일치를 기록했다.

[집중 시험 당시 결과](manual-selection/result.json)는 첫1실패/20통과/1건너뜀33.10초와 비동기 초기 history loading 경합 원인을 보존한다. 이후4통과6.31초·관련8통과12.34초·upload identity1통과2.34초·선택 범위5통과/2deselected7.36초는 겹치는 별도 범위로 합산하지 않는다. 잘못된 nearest node 호출로 시험0인 기록도 남긴다. 이 수정은 테스트가 실제 초기 loading을 기다리게 한 것이며 제품 fallback을 넣지 않았다. [GET 전용 driver](manual-selection/native-readonly.py)·[로그](manual-selection/native-readonly.log)·[spec](manual-selection/spec.md)를 함께 보존했다. 현재 업무/모델 pending 상태는 그대로이며 새 적재/worker/LLM/전체시험은0이다.

## B 실제 재고와 업무 준비

[lineage 조사](b-stock-lineage/README.md), [현재 actual lineage](b-stock-lineage/actual-B-package-lineage.json), [saved checks](b-stock-lineage/saved-lineage-checks.json)은 실제8개GET/ERP 표와 소스 계약을 대조한다. PM-02 전체 원문 GET은 로컬 증거에만 보존했고 저장소에는 [SHA/절 anchor 증명](b-stock-lineage/PM-02-original-source-proof.json)만 남긴다.

HYD-02 단독4,000h는 씰1·필터1·작동유 샘플 분석이며 작동유 교환이 아니다. HYD-03 포함8,000h 묶음에는 추가 작동유 교환이 있으나 실제 번호/양은 미상이다. 씰 available7은 확인되었으나 `P-RTN-FLT`의 실제 master/stock 행은 없다. 이름이 비슷한 부품으로 대체하거나 미상을0/가능으로 바꾸지 않는다. 단독안에 묶음의 작동유 요건을 얹지 않는다. 현재 HYD-02 운전시간은 연기 상한도 넘어섰으며 이 GET 비교를 새 승인 결과로 취급하지 않는다.

현재 포털의 데이터 패브릭 reader로 parts/spare_stock/task_standards를 읽을 수 있다. 신규 필터의 검증한 ERP 품목·실물/예약/입고예정·가용·가격/기준값이 준비되어야 실제 B 재평가와 승인/실행을 할 수 있다. 최소 필요1개는 실제 보유량1을 임의 입력해도 된다는 근거가 아니다. C 씰 구매 반복/재고 초기화는 새 필터 행을 공급하지 않는다.

## K3의 외부 조건과 구현 가능 범위

[K3 조사](k3-auth/findings.md), [실제 등록 상태](k3-auth/runtime-boundary.json), [실제 도구 목록](k3-auth/registered-capabilities.json), [개인정보 없는 앱 인증 boolean](k3-auth/connector-auth-state.json)을 보존한다. Googleprofile 원문·개인정보·토큰은 포함하지 않는다.

최초 설계는 업무 표 MCP와 Google MCP를 별도 요구했고 실제 회의 한 건을 요구했다. generic 제공 서버 등록 실습은 독립적으로 가능하지만 기존U21과 같으며 Google K3를 대신할 수 없다. 학생 포털 로그인이나 각 학생의 GCP 프로젝트가 공통 필수조건은 아니다. 강사가 선택한 실제 MCP 주소/실행 환경, 그 서버의 적법한 인증, 실제 자료·캘린더·회의실 접근이 필요하다. 현재 연결된 ChatGPT 앱에는 HYD용 endpoint/credential handoff 도구가 없고 워커는 개인 앱을 상속하지 않는다.

외부 상태 없이 가능한 일은 기존 설정 계약 설명·실제 schema가 주어졌을 때 매핑 사본 준비·서버별 OAuth 연결 UI/adapter의 구체적 설계다. 실제 등록/인증 읽기/승인된 초대·응답 확인은 provider endpoint와 외부 계정 권한이 준비된 후에 가능하다. 임의 토큰 요구·개인 앱 토큰 추출·앱 격리 해제·가짜 참석 수락·generic mock 대체를 하지 않는다. 준비27pass는 재실행하지 않았다.

## 증거 복사와 한계

[portable-evidence-manifest.json](portable-evidence-manifest.json)은27개 명시 파일의 원본 경로/bytes/SHA256와 byte-exact 복사를 기록한다. 원문 전체와 과거 거대한 소스 manifest는 중복하지 않는다. U10 최종 native11파일은 별도 copy-provenance로 추가했으며 과거 manifest를 덮지 않았다. 최종 제품 source manifest와 NOW는 루트가 관리한다. 포털의 현재 pending 모델/업무상태를 임의 변경하지 않았다. 이번 문서 통합은 새 워커·LLM·외부 쓰기·앱 설치·권한 요청을 포함하지 않는다.

증거 폴더의 `.gitattributes`는 원본 CRLF를 Git이 바꾸지 않도록 보존한다. 첫 스테이징의25개 바이트 불일치를 발견해 증거 경로만 다시 스테이징했고 불일치0을 확인했다. CRLF를 일반 공백으로 검사하지 않으며 원본 수집 스크립트 `b-stock-lineage/read_catalog.py`의 마지막 빈 줄 경고1개는 원본 SHA 보존을 위해 유지한다. 제품/NOW의 공백 검사는 별도다.

## 현재 판본과 참고 비교

[현재 source808 동결](source-manifest.json)·[변경0 확인](source-verification.json)은 이전 F27 source807 이후 제품 변경이 문서 선택3경로임을 기록한다. 과거 전체2673개 결과를 현재 전체 회귀 결과로 승격하지 않는다. [참고/실제 화면 나란히 보기](reference-comparison.html)·[캡처](reference-comparison.png)·[이미지4개 렌더 결과](reference-comparison-result.json)를 보존했다. 루트가 비교PNG를 직접 확인했다. ProcessGPT 쪽은 원본 컴포넌트를 컴파일한 비교용 폼이며 전체 앱 캡처라고 주장하지 않는다.

새 선택 시험의 [메모리 결함 주입](manual-selection/fault-injection/result.json)은 선택을 새 문서로 초기화했을 때 기존 새 시험32행이 예상대로 실패함을 확인했다(1실패2.33초). 제품3파일 SHA는 불변이며 첫 수집경로 오류도 보존한다. 구현 당시 보존 비교 문서를 참고했고, ProcessGPT 모노레포README와 ontology-studio FilePanel 원본 파일 직접 확인은 후속 검토에서 수행했다. 원본 파일을 수정 전에 읽었다는 주장으로 바꾸지 않는다.
