# 최종 부분 검증과 실제 업무 결과

2026-10-12. 전체 고정 판본 시험은 **2673 passed / 16 skipped / 21 warnings**다. 이후 제품 변경은 전체 시험을 반복하지 않고 각각의 집중 로그·소스 SHA로 확인했다. 최종 phase2는 제품/시험 source800개, 전체 판본 이후 delta36개다. 시험 수는 중첩되므로 합산하지 않는다.

실제 배포 화면의 마지막 GET 확인은 [result.json](result.json)의 **203항목 통과**다. 여기에는 화면 파일 SHA 대조와 B/C/지식 화면의 표시·문서폭·사례/검토 원장 불변 확인이 포함된다. pageerrors/consoleErrors/blockedWrites는0이다. requestFailures의 health no-cors/화면 이동 ERR_ABORTED는 원본에 보존했으며 모든 네트워크 요청 성공이라고 쓰지 않는다. 이전 health 응답 본문 취소 분석과 달리 이번 `/api/config/cases` 취소도 실제 기록으로 남기며 서비스 장애라고 단정하지 않는다. 제품/API를 수정하거나 실패 수를 숨겨 통과시킨 검사가 아니다.

## 화면

- [참고 화면과 실제 화면 나란히 보기](reference-delegated-comparison.html): Dify 공식 문서·보존 ProcessGPT 업무 목록·Vue 원본 컴포넌트의 출처를 각각 구분한다. 옛 모노레포 PNG를 현재 최신 앱 실행 화면으로 표시하지 않는다. 원격 최신 소스는 모노레포6084127 / Vue265580f / ontology-studio20afcde를 확인했다. 보존 Vue867e8cf 이후 관련 차이는 오류 설명·CLI 마크다운 플러그인이며 PgToolStep은 같다. compile 화면은 전체 앱 실행 화면이 아니다.
- [B 정비 진단](B-pm-HYD-02-1440.png): 4,000시간 패키지, 누적12,000시간, 필터 실제 재고 미확인·상한을 기본 표시한다. **보류 당시 평가 근거**를 현재 승인된 실행으로 바꾸지 않는다.
- [C 실제 입고 결과](C-status-1440.png): 교육용 ERP 입고6·현재고9·가용7·합격 로트·발주/입고 번호를 표시한다.
- [검토·개정 이력](knowledge-history-1440.png): 사용자 위임 Codex 표시를 사람 직접 검토로 꾸미지 않는다. 원래 추출 제안 화면에 현재 검토 연결을 주입하지 않았다.

원본 A 미달 종결 화면은 phase1의 유효한 결과를 그대로 보존했다. 최종 부분 캡처가 A를 다시 검사한 것처럼 표시하지 않는다. 1440/1024 화면과 원본 위치·SHA는 [evidence-provenance.json](evidence-provenance.json)에 있다. 참고 화면과 기능·화면 종류가 다른 부분은 캡션으로 명시하며 전체 픽셀 일치·사용자 시각 인수를 주장하지 않는다.

## 실행과 실시간

C는 원문 구매 경제 정책의 공식 개정 후 현재 비교 **OEM360 / A410만원**과 미AVL 제외를 확인했다. 기존 DEC의 잘못된 A추천은 보존했다. 명시 위임 선택 이후 실제 발주 PR-1012-FE8A·6개330만원, 합격 입고 GR-1012-C42C·LOT-261012-654, 재고가용7과 COMPLETED를 [업무 영수증](C-business-completion-proof.json)으로 확인했다. 기대손실 포함 비교금액과 발주금액을 구분한다. 외부 실제 공급사 거래가 아니다.

B의 실제 Sol6.1 평가1회는 필요한 실제 재고를 확인할 수 없고 연기안은 상한을 넘어서 PENDING이다. [실시간 결과](stream-B-result.json)는 freshFrames23·privateEvents0이며 같은 job의 공개 문장과 도구가 평가 보류 전에 표시됐다. [공개 문장](stream-B-B-public-before-agent-assessment-end-1.png)·[도구](stream-B-B-tool-before-agent-assessment-end-2.png)는 **평가 종료 전** 증거이며 업무 완료 증거가 아니다. 과거 C 도구 PNG의 잘못된 실행 행 선택은 [원래 정정](../first-stream-capture-review.md)대로 무효다.

WO_RESCHEDULE 예측 등록 수정 후 [현재 MCP 평가](B-current-after-forecast-proof.json)는 모델 오류0이며 네 후보의 실제 재고/기한 제외 사유와 저장된 B 불변을 확인했다. 공식 MCP 호출은1회다. 최초 검사 driver의 document.options 가정은 실제 producer의 document.result.options와 달라 KeyError였으며, 저장 응답을 다시 검사해 추가 MCP 호출0이다.

## 실패 보존과 판정 한계

첫 구매 집중 검사130통과/1실패와 후속 잘못된 시험 경로, 새 UI fixture의 DOM wrapper 누락, [첫 실제 최종 화면 실패](first-final-capture-failed-result.json)는 보존했다. fixture 입력/캡처 선택자를 실제 계약에 맞춰 고쳤으며 기존 회귀 기대값·골든·실패 기록을 성공으로 바꾸지 않았다.

후속 성공은 공개 스트림87, 긴 도구 입출력25, 구매 신규16, schema16, UI78/15, 예측73, 보류 UI46의 각 집중 범위다. 사용자 요청대로 전체 재실행0·추가 B LLM 재실행0이다. 소스 판본은 [phase2 SHA](final-runtime-phase2-source-manifest.json)와 [검증 범위](final-runtime-phase2-verification-coverage.json)로 구분한다.

남은 것은 B 실제 부품/재고 자료에 따른 업무 완료, 인증된 외부 Calendar/Drive MCP·실제 회의 K3, 전체 화면의 사용자 시각 인수다. U16/U20/F13을 전체 완료로 변경하지 않는다. UIUX.md 인수 조건6은 “사용자가 캡처를 보고 ‘됐다’고 해야 완료”이며 자동 검사는 전제 조건이다. 학생 포털 로그인이나 GCP 프로젝트를 공통 필수로 추가하지 않았다. 서비스는 포털8088에서 열어 두고 AI 작업을 가져가는 owned 워커8097은 종료했다.
