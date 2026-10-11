# archive — 끝난 작업의 기록 (2026-10-11 정리)

지금 유효한 상태와 남은 일은 `../NOW.md` 한 문서에 있다. 여기 문서는 지난 경위·옛 계획·옛 실라버스다. 지우지 않고 `git mv`로 옮겼다(이력 보존). 옛 실라버스 기준 문서는 5일차 이후 내용을 「정해진 것」으로 쓰지 않는다 — 기준은 `1~4일차 실라버스 확정안.xlsx`뿐이다.
이 폴더로 옮기면서, 현행 문서(CLAUDE.md · README.md · TODO.md · HANDOFF.md · AUDIT.md · QA.md · docs/sessions/README.md 등)의 경로는 고쳤다. `DECISIONS.md` · `UIUX_PLAN.md` · `verification/` 안의 문서는 고치지 않아 옛 경로가 남아 있을 수 있다(여기서 같은 이름을 찾는다).

| 문서 | 무엇이었고 왜 보관했나 |
|---|---|
| GOAL.md | 2026-10 초 "완주 목표"와 DoD 7개, 작업 B 인수조건. 구현·검증이 끝났고 현재 상태는 NOW.md |
| HANDOFF_실라버스교재.md | 10-08 실라버스·교재 인계(§7 랩업 계약만 CLAUDE.md §4에 요약돼 있고 NOW.md 5절에도 있음, §10 슬라이드 인계는 `슬라이드/제작기준.md`로 대체) |
| 실라버스.md · 실라버스.xlsx · 실라버스_설계용_시스템설명.md | 옛 실라버스(통합·실전 4형식, 75시간 25회차 전제) 초안과 설계용 시스템 설명. 사용자가 1~4일차 확정안으로 갈아엎는 중이라 5일차 이후를 기준으로 쓰지 않는다 |
| PROJECT_STATUS.md | 10-06~08 시점 개발 현황 표(DoD 상태). NOW.md가 대체 |
| PROGRESS.md | A044~A123 진척 평가 점수(기록용). 끝남 |
| REBUILD.md | 구현 교체 순서와 수용 조건(10-04~05 설계). 이력 문서 |
| REWORK.md | 새 판단·실패 승인 폐기 설계(A035~A042, 구현·검증 끝) |
| ALERT_ROUTING.md | A032 경보 지원 범위와 사람 검토 계약. 구현 끝, 코드와 시험이 정본 |
| APPROVAL_RECOVERY.md | A025 승인 저장과 외부 실행 복구 설계. 구현·검증 끝 |
| CURRENT_APPROVAL.md | A027 현재 조건으로 승인 검증. 구현 끝 |
| DECISION_REVIEWS.md | A031 변경 조치의 예측 검토와 사람 승인. 구현 끝 |
| EVENT_INBOX.md | 원천 이벤트 접수와 재시작 복구 계약. 구현 끝 |
| FORECAST_MODEL.md | A030 예측 모델 입력 계약. 구현 끝 |
| GUIDE_COMMIT.md | A034 진단 가이드 저장과 태스크 완료. 구현 끝 |
| MANUAL_INGESTION.md | A026 문서 원천·검토·적재 계약. 구현 끝, 제약 요지는 NOW.md 5절(사람 검토 기록 필수) |
| WORK_ORDER_RECOVERY.md | A028 작업지시와 종결. 구현 끝 |
| REFERENCE_ADOPTION.md · .json | A066 참고 레포 채택 대조(고정 스냅샷). 끝남 |
| REPOSITORY_REVIEW.md | 저장소 지도 관련성 검토(초기 조사). 끝남 |
| REPORT_BRIEF.md | 기능 보고서 설계서(A109, 제작은 A110에 끝남) |
| 작업보고_2026-10-08_초안.md | 10-08 클라우드 세션 작업 A 보고 초안 |
| USER_UTTERANCES.md · USER_UTTERANCES_20261008_대응표.md · USER_UTTERANCES_CODEX_20261004.md | 사용자 발화 원문과 반영 위치. 내용은 고치지 않았고 결정은 DECISIONS.md에 있다 |

## 남겨 둔 것 (옮기지 않음)
- `../REPO_GAP.md` · `../AUDIT.md` — 코드 주석(`it/process/procsvc/engine.py` · `instances.py` · `ingest.py`, 마이그레이션 SQL)이 경로를 가리켜 두었다.
- `../HANDOFF.md` — 현재 사실·규칙(§2 · §3)과 코드·compose 주석이 가리킨다. `../QA.md` — 확정 답의 중복 여부를 판정하지 못했다.
