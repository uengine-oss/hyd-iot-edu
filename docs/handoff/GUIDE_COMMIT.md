# 진단 가이드 저장과 태스크 완료 — A034

상태: 수정·배포 완료, 전체549검사와 실제 PG/SQLite7검사 통과. 배포 후 실제 Codex 경로도 `a034-codex/`에서42/42 exit0으로 확인했다.

## 실제 결함과 근거

`anomaly_response.9c8ee1ba-e7e3-41e3-a73d-e3823c721269`는 Codex 진단·후보·규정·순위 네 작업을 DONE으로 표시했다. MCP21시작/21종료, 현재 검토까지 성공했으나 생산관리자 승인에서 `action FAN_SET is not on the guide card`로 거절되어26/27 exit1이었다. 승인 영수증과 PLC 명령은 없었다. `.evidence/reaudit/a032-codex-durable/`에 검사 종료코드, 태스크 원문, 실제 Incident/decision, 네 Codex 세션을 보존했다.

진단 출력 guide_card에는 FAN_SET/LOAD_SET/WO_CREATE가 있었지만 alert는 asset/pattern만 포함했다. `update_incident_card`가 생략된 alertId를 충돌로 거절했다. `process_workitem`은 이 필수 저장을 PG DONE 뒤의 post-commit 효과로 예약해 오류를 로그만 남기고 삼켰다. 따라서 다음 작업은 진행했지만 Incident는 빈 초기 카드였다. 테스트를 완화하거나 승인 검사에서 가이드 대조를 제거하지 않는다.

## 변경 계약

- 프로세스가 소유한 Incident 식별자에 진단 가이드를 결합한다. 생략된 경보 식별 필드는 원래 경보를 유지한다. 명시된 ID/설비/패턴/사건의 충돌과 없는 Incident는 거절한다. 원천 evidence는 에이전트 출력으로 교체하지 않는다.
- 가이드 저장 성공 후 PG의 DONE/다음 작업을 commit한다. 저장 실패는 기존 엔진의 오류/재시도 경로로 남기며 다음 작업을 열지 않는다.
- SQLite 성공 뒤 PG 실패는 두 저장소의 부분 완료다. 원래 worker output을 재처리하여 같은 가이드를 다시 저장한다. 이 경로는 승인이나 PLC 명령을 발행하지 않는다. 두 DB 전체 원자성을 주장하지 않는다.
- 다른 post-commit 투영/외부효과의 일반 outbox까지 해결한 변경은 아니다.

## 실행 증거와 경계

| 확인 | 실제 결과 |
|---|---|
| 수정 전 신규 재현 | 4failed/4passed, a034-guide-red.xml |
| 수정 후 관련 검사 | 77passed/기존경고2, a034-guide-unit.xml |
| 전체 검사 | 549passed/기존경고3, a034-regression.xml |
| 실제 PG/SQLite | 7/7 exit0, a034-guide-live/ |
| 새 Codex 전체 경로 | a034-codex/, 42/42 exit0 |

실제 저장소 검사는 `scripts/probe_guide_commit.py`가 이전 실제 Codex 출력을 별도 tenant에 재사용했다. SQLite 쓰기 실패와 PG 저장 실패를 각각 주입하고, SQLite 파일을 닫았다 열고 새 런타임으로 재처리했다. 라이브 Codex 재호출, 운영 컨테이너 강제 종료, 물리적 회복 검사를 대신하지 않는다. 격리 tenant `a034-guide-c1f92fe155`와 SQLite는 보존했다.

이전 실패 시나리오와 후속 OVERHEAT 경보는 원문을 보존하고 시험 설비 reset 뒤 명시적인 검토 메모로 각각 ev:escalated/ev:review-recorded 종료했다. 물리적 회복 성공으로 세지 않는다. 워커 PID6932와 자식 종료를 PowerShell로 확인했고 개인 config SHA는 불변이었다.

다음은 a034-codex의 실제 승인→PLC→재관측→CMMS→그래프를 확인하고 워커/기본 환경을 복원하는 것이다. 이후 EVENT_INBOX의 운영 수신·처리·재시도 연결을 이어간다.


실제Codex 결과: b9a9245a…/INC-1004-01-0765, 네작업321초, MCP25시작/25종료·명시오류0·네세션. 승인DELIVERED1회, CMD-1004-0001-76b3의PLC ACK, 재관측608초, 실제CMMS WO-1004-4227뒤Incident/인스턴스/graph종결. 워커16124자식종료·PowerShell0·개인config불변확인. 이후A033연결코드는별도배포되어그변경의실제회귀는별도로수행한다.
