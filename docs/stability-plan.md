# 안정성 개선 — 2026-10-01

요청: 실제 E2E로 hyd-iot-edu 안정성을 높인다. 로컬 리소스 재구성 및 .env OpenAI 키 사용이 승인되었다.

기준: 변경 전 Git clean, 단위 124개 통과. 기존 기록은 2026-09-30의 59개 통합 검사이며 이번 실행의 증거로 대체하지 않는다.

수용 기준:
- Docker 기동 후 경보 → 근거 카드 → 역할 승인 → PLC ACK → 회복/종결 및 기업 시스템 연계가 실제 서비스에서 통과한다.
- DB 중단 중 Kafka 입력을 유실하지 않고 복구 후 적재한다. DB 성공 전 소비 위치를 확정하지 않는다.
- process 재시작 후 승인 대기 및 완료 기록을 보존한다. 실행 도중 재시작된 명령은 자동 재발행하지 않고 명시적으로 에스컬레이션한다.
- 잘못된 HITL 입력이 결정을 먼저 승인해 버리지 않으며, 다른 incident의 결정 사용과 중복 실행을 거부한다.
- OpenAI 호환 API의 실제 응답을 확인하고, 오류·빈 응답·시간 초과에는 템플릿을 사용한다.
- 포탈 실제 화면과 장애 주입 결과를 기록한다.

검증 경계: 로컬 시뮬레이터와 기업 시스템 목업. GCP LiteLLM 배포 자체 및 실제 PLC/기업 시스템은 이 로컬 검증과 구분한다.

## 구현과 검증

| 문제 | 개선 | 실제 근거 |
|---|---|---|
| DB 실패 시 배치를 버리고 Kafka 소비 위치가 먼저 확정됨 | DB 데이터+소비 위치를 한 트랜잭션으로 저장, 성공 뒤 Kafka commit, 재연결·재처리 | DB 중단 + sink 재시작 후 40/40개 복구. Kafka 처음부터 재처리하고 새 표식 추가 후 41개, 서로 다른 값 41개. 소비 지연 0 확인 |
| ACK가 명령 레코드보다 먼저 도착하면 기록 누락 가능 | ACK 먼저 upsert, 명령 도착 시 상세 필드 보충 | 실제 sink 컨테이너와 DB에서 ACK→명령 순서로 처리하여 DONE과 명령 메타데이터가 함께 남음을 확인. 시험 트랜잭션은 rollback. [로그](../.evidence/ack-order.log) |
| process 재시작 시 승인·인시던트 기록 소멸 | SQLite 전용 볼륨, 발행 전 상태 저장, 불확실한 실행은 재시작 후 에스컬레이션 | 승인 대기·종료 기록 유지, 진행 중 cmdId 유지 + PROCESS_RESTART_REVIEW, 재승인 거부 |
| 기업 시스템 재시작·중복 호출 시 작업 중복 | 실행 상태 영속화 + decision/skill별 멱등 처리 | 재시작 후 동일 트랜잭션 반환, 작업지시 1개, 다른 입력 재사용 400 |
| 잘못된 HITL 설정이 결정을 먼저 승인 상태로 바꿈 | 연결된 인시던트·상태·파라미터를 검증한 후 승인 확정 | 잘못된 팬 값·다른 인시던트·중복 제출 회귀 테스트 |
| Anthropic 전용 요약, 긴 네트워크 대기 | OpenAI 호환 API 및 LiteLLM base URL 지원, 8초 timeout, 실패 시 템플릿 | gpt-4o-mini 실제 응답. 전체 E2E 4개 카드 중 모델 2개·템플릿 2개. 연결 거부 시 템플릿 복귀도 실행 확인 |
| 수집 서비스 연결 실패를 신뢰 가능으로 해석 | 연결 실패 시 추론 보류 판정 | 최신 DB 데이터가 있어도 수집 주소 연결 실패 시 ok=false, ingest unavailable |
| 기동 의존성 누락 | agent가 KG seed·DB sink·process·enterprise 준비 후 시작, 장기 서비스 restart 정책 | Compose 실제 기동 및 8개 앱 health 확인 |

실행 환경: Windows / Docker Desktop Linux, Python 3.12, TIME_SCALE=20, DAQ_PROFILE=lite. 시각은 로컬 2026-10-01, 로그의 UTC는 2026-09-30이다.

- 변경 전: 단위 124 통과, 전체 E2E 59/59 (337초).
- 개선 후: 단위 135 통과. 전체 E2E 59/59 (345초).
- 최종 이미지 추가 확인: `scenario_test.py --quick --require-llm` 46/46 (169초). 실제 `gpt-4o-mini` 요약을 필수 조건으로 삼아 카드→승인→ACK→회복·종결→기업 시스템·지식 관리까지 통과. [원문 로그](../.evidence/llm-e2e.log).
- 장애 주입: 12/12 (91.2초). [JSON](../.evidence/stability.json), [원문 로그](../.evidence/stability.log).
- HITL 실제 API 추가 회귀: `stability_test.py --process-only` 9/9. 잘못된 팬 값 400·권한 부족 403 뒤에도 승인 대기 유지, 수정한 요청 EXECUTED, 재시작 후 에스컬레이션 및 재승인 거부. [JSON](../.evidence/hitl-recovery.json), [원문](../.evidence/hitl-recovery.log). 기존 장애 시험과 겹치는 항목이 있으므로 두 수를 독립 검사 수로 합산하지 않는다.
- [전체 E2E](../.evidence/final-e2e.log), [단위 테스트](../.evidence/unit.log), [LLM 연결 실패](../.evidence/live-llm-fallback.log), [데이터 신뢰 판정](../.evidence/live-data-trust.log).
- 실제 브라우저: 스킬 카탈로그 표시, 전사 판단 실행 및 부서 관점 전환, 운전원 정지안 승인 거부, 생산관리자 승인→CMMS DONE, 온톨로지·Cypher 표시. [권한 거부](../.evidence/ui-denied.png), [승인 결과](../.evidence/ui-approved.png), [판단 화면](../.evidence/decision-perspective.png), [지식 지도](../.evidence/ui-ontology.png).

## 재현과 남은 경계

후속 UI 점검(2026-10-01): [UI 검증 기록](ui-stability-review.md). 자동 갱신 입력 소실·배율 불일치·잘림·복구 후 잔여 오류·매뉴얼 미리보기·FUXA ACK 잔존 등 16항목을 수정하고, UI 승인 팬95/부하70→ACK DONE→CLOSED를 실행했다. 최종 단위136개, 모델 필수 E2E46/46(171초) 통과. 앞선 API 검증을 모든 UI의 검증으로 확대하지 않는다.

```powershell
uv venv --python 3.12 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements-dev.txt
docker compose up -d --build
.venv/Scripts/python -m pytest -q
.venv/Scripts/python scripts/scenario_test.py --require-llm
.venv/Scripts/python scripts/stability_test.py
```

키는 Git 제외된 `.env`에만 두며 `.env.example`에는 값이 없다. LLM 필수 시험에는 실제 키가 필요하다. API 계약은 [OpenAI 공식 문서](https://developers.openai.com/api/reference/resources/chat)를 확인했다. GCP LiteLLM은 호환 주소 설정 경로만 마련했으며 해당 배포를 호출하거나 수정하지 않았다.

이 검증은 수 분 단위의 로컬 장애 복구 시험이다. 장시간 부하·호스트 전원 단절·디스크 손상·실제 장비/ERP·운영 인증/SSO 검증은 아니다. agent 트레이스, detector 상태, 게이트웨이 중복 기록은 메모리이며 MQTT→Kafka 이전의 수집 공백과 큐 초과 유실은 별도 경계다. LLM 설명의 모든 문장이 자동으로 사실 검증되는 것은 아니다.

`process-data`, `enterprise-data`와 기존 DB 볼륨을 삭제하면 상태가 사라진다. Kafka 토픽만 삭제·재생성하고 기존 sink 체크포인트를 그대로 사용하는 것은 지원하지 않는다. 처음부터 초기화할 때는 프로젝트 DB/토픽 볼륨을 함께 초기화해야 한다.

동시에 다른 세션이 만든 `docs/마스터_가이드.html`, PDF, `docs/src/`는 이번 변경에 포함하지 않는다. 이 자료는 커밋 a676a11 기준이라는 표시를 유지하고 있다. 현재 운영 동작은 README와 이 기록을 참조한다. 커밋·외부 배포는 수행하지 않았다.
