# 경보 지원 범위와 사람 검토

A032 현재 계약. 회의의 이벤트 실행·사람 선택·현재 원천 요구(R08/R10/R11)와 사용자의 변경 시나리오 요구를 구현하는 경계다. 회의가 아래 패턴명/임계값을 지정한 것은 아니다. ProcessGPT의 정의/버전/작업 실행 구조는 기존 REPO_GAP·DEFINITION_REGISTRY 근거를 사용하며, 물리 회복 기준은 HYD 설비 계약이다.

## 변경 이유

이전 `trip_alert`는 PLC 사유가 LOW_PRESSURE/HIGH_VIBRATION이어도 OVERHEAT_TRIP으로 발행했고, 사유 누락을 OVERTEMP로 채웠다. `recovery_for`는 알 수 없는 패턴에도 TS1<55를 반환했다. 이 조합은 압력·진동 트립을 냉각기 진단/회복으로 설명할 수 있는 결함이었다.

## 실행 계약

새 기본 정의 `anomaly_response@2.1`의 `alertPolicy`가 지원 패턴과 회복 기준을 지정한다. 기존 2.0 바이트/진행 인스턴스를 덮지 않는다.

| 입력 패턴 | 회복 확인 | 접수 경로 |
|---|---|---|
| COOLER_DEGRADATION | CLEAR와 TS1<55 | 진단·후보·규칙·순위 네 작업 및 사람 선택 |
| PUMP_LEAKAGE | CLEAR와 PS1>=165 | 같은 정의 엔진 |
| FAN_VIBRATION | CLEAR와 VS1<1.2 | 같은 정의 엔진 |
| OVERHEAT_TRIP / LOW_PRESSURE_TRIP / HIGH_VIBRATION_TRIP / PLC_TRIP / 기타·누락 | 회복 기준 없음 | alert_triage@1.0 사람 검토 |

PLC 트립 사유 OVERTEMP/LOW_PRESSURE/HIGH_VIBRATION은 각각 위의 명시 코드로 매핑한다. 알 수 없는 사유와 누락은 PLC_TRIP으로 표시하며 실제 원문 사유를 evidence.trip에 보존한다. CLEAR는 같은 ID와 원래 패턴/사유를 유지한다. 추측한 사유를 만들지 않는다.

사건은 생성 당시 패턴/회복 기준/정의 버전을 저장한다. 이후 새 정의 등록이나 재시작이 이미 열린 사건의 임계값을 바꾸지 않는다. 기존 저장 사건은 세 정상 패턴에 한해 명시 legacy 기준을 사용하고 미지원 패턴의 기본 센서를 만들지 않는다. 새 패턴을 정상 경로로 보내려면 명시 기준을 가진 새 정의와 해당 진단·규칙·조치 근거를 준비해야 한다. 정의에 이름만 추가했다고 실제 에이전트 진단/제어까지 지원되는 것은 아니다.

사람 검토 정의에는 명령 선택, 서비스, 에이전트 작업이 허용되지 않는다. 원천 경보가 작업의 읽기 전용 입력으로 전달되며 검토자는 현장 확인 내용을 기록한다. 작업은 `ev:review-recorded`로 끝나고 사건은 `ESCALATED / UNSUPPORTED_ALERT_PATTERN`을 유지한다. 원천 CLEAR는 관측 기록이며 정상 회복/명령 승인/CMMS 발행을 뜻하지 않는다.

늦은 가이드/결정은 기존 경보 ID의 설비/패턴을 바꾸거나 사람 검토 사건을 정상 조치로 승격할 수 없다. 에이전트는 `/api/alerts/policy`에서 미지원 경보를 확인하면 추론 전에 WITHHELD로 종료한다. 사람 작업 입력 API는 정의의 inputData로 범위를 제한한다. 사용자 인증/운영 권한 전반의 완성 증거는 아니다.

## 검증 상태

- 첫 전체 검사: `a032-first.log/xml`, 501 passed / 4 failed. 잘못된 기본값 기대 2개 및 패턴 없는 정의 버전 fixture 2개를 수정했다.
- 관련 검사: `a032-targeted.log/xml`, 65 passed. PLC 사유/CLEAR 보존, 미지원 경보의 사람 검토, 원천 변경 거부, 저장 복구, 새 패턴 기준, 부적합 fallback/임계값을 확인했다.
- 전체 검사: `a032-all.log/xml`, 527 passed / 경고 3. 포털 JS 구문 검사 통과. 단위 검사와 구문 검사는 실제 실행/화면 클릭의 대체 증거가 아니다.
- 실제 첫 실행 `a032-triage-live`는 15개 확인 후 검사기의 목록 card=null 접근 때문에 exit1. 상세 API로 수정했다.
- 재검사 `a032-triage-verified`는 16개 확인 후 실제 동시 저장 오류로 exit1. 저압 Incident 생성 중 다른 경보가 목록에 추가되어 `Store.save`의 `asdict` 반복이 실패했고 PG 인스턴스가 rollback됐다. `a032-concurrent-process-failure.log`와 두 스레드 재현 검사 `a032-store-red` 1 failed를 보존한다.
- 저장 락 안에서 목록 멤버십을 고정하고 직렬화와 기록을 순서화했다. 전체 `a032-all-final` 528 passed. 다른 사건 목록 조회 보강 후 `a032-source-final` 관련 66 passed.
- 수정 후 실제 `a032-triage-fixed` **45/45 exit0**: Kafka 미지원 경보/중복/늦은 결과 거부, process SIGKILL/start, 세 설비 동시 물리 고장, PLC 원인별 경보/사람 검토 입력, agent 추론 전 WITHHELD, 원래 ID/패턴의 CLEAR, 검토 완료 후 ESCALATED 유지. 새 Codex나 포털 클릭 검사는 아니다.
- 앞선 두 실패 시험의 10건은 `a032-failed-fixtures-before/review.json`에 보존했다. 한 orphan 사건만 원문으로 명시 재접수했고, 미지원 사건은 사람 검토, 두 정상 패턴의 잔여 시험은 에스컬레이션 확인으로 종결했다.
- 정상 쿨러 20배속 첫 시도는 현재 예측 악화로 승인 보류(24/25 exit1), 새 검토본 시도도 접수 후 전달에서 현재 TS1 예측 악화로 FAILED(검사 중단 exit-1)였다. 두 경우 명령은 없었다. `a032-normal-first-failure.json`과 `a032-normal-review-failure.json`을 보존했다. 실패 승인은 임의 완료 처리하지 않고 후속 폐기/재검토 구현의 실제 미결 사례로 유지한다. 세 서비스 모두5배속으로 맞춘 검사는 42/42 exit0로 PLC ACK/재관측/실제 CMMS WO-1004-B2B5/ev:closed까지 통과했다(`a032-normal-scale5.log`, `a032-normal-scale5-final.json`).
- 이 수정은 전체 상태를 두 DB 사이에서 원자적으로 만드는 기능이 아니다. 시작 이벤트의 durable inbox/재시도·그래프/감사 outbox는 후속이며, 예외나 종료 시 자동 유실 복구가 모두 구현됐다고 설명하지 않는다. 이번 orphan 사건은 원문을 보존해 명시 재접수했다.
- 별도 그래프 조회에서 45/45 검사가 다루지 않았던 Process/Incident 연결 누락을 발견했다(`a032-triage-graph.json`). 실제 Process seed와 생성 시 사건 원문 투영, 사건 연결 누락 경고를 추가했다. 관련50passed/경고2(`a032-graph-unit.xml`). 기존 네 시험은 실제 원문/PG 이력으로 명시 복구하고 재조회했다(`a032-graph-repaired.json`).
- 수정 배포 뒤 새 실제 Kafka/세 PLC/재시작/사람 검토/그래프 경로 **49/49 exit0**(`a032-triage-graph-live/`). 모든 검토가 proc:alert-triage 및 실제 Incident/Asset/완료 작업과 연결되고 투영 경고가 없음을 확인했다. 미래 그래프 장애의 자동 재전달은 아직 미구현이다.
- 20배속 펌프/팬/경보 가림 회귀 **37/37 exit0**(`a032-pump-fan/`). PS1/VS1 기준 정상 종결과 CLEAR 뒤 PS1=156.99<165 실패 에스컬레이션·작업지시 취소를 확인했다. CMMS standby_ready=true는 명시 시험 fixture이며 원래 NULL 복원을 검증했다.
- 새 Codex 첫 실제 검사는 Neo4j MCP 초기화60초timeout으로 첫작업FAILED였다(a032-codex-first-failure). 워커/시험자식 종료0·설비reset을 확인했다. 이후 같은 설정의 Codex 단독 세 MCP 조회/동일세션재개/도구실패0/config불변은통과했다(a032-codex-standalone). 두번째실제2배속시나리오는실행중이며최종미정이다. 브라우저도구가No browser is available을반환해실제포털클릭은미검증이다. 일반재작업/전체강의검수도미완료다.

증거 경로는 저장소 `.evidence/reaudit/`이다.
