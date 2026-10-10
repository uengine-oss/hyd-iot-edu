# T8 예시 묶음 — 고객사 분기 리뷰 회의 준비 (강사 시연용 참고)

정답이 아니라 막힌 학생이 볼 완성 예다. 설계: `docs/handoff/verification/2026-10-09/capstone-lab.md` 3절.
회사 "가온상사", 사람 이름, 메일(example.com), 드라이브 · 캘린더 id 는 모두 가상이다. 시연 ID 는 `demo`(T1 · T3 의 `s00` 과 섞이지 않게).

| 파일 | 단계 | 내용 | 검사 |
|---|---|---|---|
| `docs/d1.md · d2.md · d3.md` | 1 | 회의 운영 규칙 · 준비 절차(SOP) · 지난 회의록 예시본. 문서마다 "답할 질문" 3개 | — |
| `schema.json` | 2 | 학생 업무 사전(Meeting · Customer · Attendee · AgendaItem · Document · PrepGuide)과 v2 다리 관계 | `python scripts/ontology_v2.py check-extra --extra students/_template/example_meeting/schema.json` |
| `graph.json` | 3 | 이름 공간 demo 의 지식(규칙 6 · 원문 절 · 단계 5 · 입력 자리 9 · 회의 1건). 값 노드 없음 | 시험이 `validate_ns`(= `validate --extra` 의 검사 함수)로 위반 0 확인 |
| `table.sql` | 4 | 업무 표 `stu_demo`(meeting_request · attendee · room) · 읽기 전용 계정 · 예시 행 | T3 형식 대조(시험) |
| `agent/agent.json · SKILL.md · proposal.example.json` | 6 | 포털 에이전트 칸 값, 요령, 결과 값 예 | 시험: 승인 카드 칸 이름 약속 |
| `flow.bpmn · mapping.json` | 7 · 8 | 레인 3 · task 8 · 승인 1(+지연 타이머) · 분기 1 그림과 부품 매핑 | bpmn.io 파서 경고 0, 포털 가져오기 파서로 읽힘 |

## 지는 안 · 미달 가지 (해피패스 아님)
- 내일 10시 — 자료 공유 48시간(D1 2) 위반 제외 · 목 14시 — 필수 참석자 불가(D1 1) 제외 · 같은 시간 4인실 A — 6인 규칙(D1 4) 제외 · 다음 주 화 15시 — 요청 마감 넘김 감점.
- 필수 참석자 박임원(가상) 시험 계정으로 거절 또는 무응답 → "미확정" 보고. 승인을 4시간 미루면 "승인 지연" 알림만, 일정은 안 만든다.

## 아직 끝까지 돌릴 수 없는 곳 (G1 · G3 합친 뒤 가져오기 검사)
| 자리 | 지금 | 필요한 것 |
|---|---|---|
| 주관자 승인 `human:approve` | 포털 부품 목록에 없음 → 가져오기 거절 | G1 일반 승인 부품(승인 뒤 `approved_option` 값). 반려 가지도 G1 과 함께 그린다 |
| 일정 등록 · 응답 확인 `svc:mcp-call` 의 `extract` · `effect: false` | 결과가 영수증 하나뿐 → `event_id` · `all_required_accepted` 값이 안 생겨 거절 | G3 결과 추출 |
| 서버 `gcal` · 도구 `create_event` · `get_event` · 결과 경로 | 설계 문서의 자리 이름 | 강사가 고른 구글 서버의 실제 이름(T5 표) |
| 흐름 → 지식 그래프 Task 투영 | graph.json 에는 Process 만 | 판본 등록 뒤 `scripts/project_student_flow.py`(G8) |

지금 가져오면 나오는 거절 6줄은 `tests/test_capstone_kit.py` 에 기대값으로 적혀 있다. G1 · G3 이 합쳐지면 그 시험이 깨지고, 그때 "거절 0"으로 바꾼다.
