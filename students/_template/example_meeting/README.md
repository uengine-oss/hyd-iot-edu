# T8 예시 묶음 — 고객사 분기 리뷰 회의 준비 (강사 시연용 참고)

정답이 아니라 막힌 학생이 볼 완성 예다. 설계: `docs/handoff/verification/2026-10-09/capstone-lab.md` 3절.
회사 "가온상사", 사람 이름, 메일(example.com), 드라이브 · 캘린더 id 는 모두 가상이다. 시연 ID 는 `demo`(T1 · T3 의 `s00` 과 섞이지 않게).

| 파일 | 단계 | 내용 | 검사 |
|---|---|---|---|
| `docs/d1.md · d2.md · d3.md` | 1 | 회의 운영 규칙 · 준비 절차(SOP) · 지난 회의록 예시본. 문서마다 "답할 질문" 3개 | — |
| `schema.json` | 2 | 학생 업무 사전(Meeting · Customer · Attendee · AgendaItem · Document · PrepGuide)과 v2 다리 관계 | `python scripts/ontology_v2.py check-extra --extra students/_template/example_meeting/schema.json` |
| `graph.json` · `questions.cypher` | 3 | 이름 공간 demo 의 지식(규칙 6 · 원문 절 · 단계 5 · 입력 자리 9 · 회의 1건), 값 노드 없음. 문서의 "답할 질문" 9개를 옮긴 질의 | `python students/_template/load_graph.py check --dir students/_template/example_meeting`(그래프 없이) → `load` → `ask` → 되돌리기 `wipe`(T2) |
| `table.sql` | 4 | 업무 표 `stu_demo`(meeting_request · attendee · room) · 읽기 전용 계정 · 예시 행 | T3 형식 대조(시험) |
| `agent/agent.json · SKILL.md · proposal.example.json` | 6 | 포털 에이전트 칸 값, 요령, 결과 값 예 | 시험: 승인 카드 칸 이름 약속 |
| `flow.bpmn · mapping.json` | 7 · 8 | 레인 3 · task 9 · 승인 1(+지연 타이머) · 분기 2(승인? · 필수 참석자 전원 수락?) 그림과 부품 매핑 | bpmn.io 파서 경고 0, 포털 가져오기 파서로 읽힘 |

## 지는 안 · 미달 가지 (해피패스 아님)
- 내일 10시 — 자료 공유 48시간(D1 2) 위반 제외 · 목 14시 — 필수 참석자 불가(D1 1) 제외 · 같은 시간 4인실 A — 6인 규칙(D1 4) 제외 · 다음 주 화 15시 — 요청 마감 넘김 감점.
- 필수 참석자 박임원(가상) 시험 계정으로 거절 또는 무응답 → "미확정" 보고. 승인을 4시간 미루면 "승인 지연" 알림만, 일정은 안 만든다.
- 주관자가 반려(사유 필수) → "승인?" 분기의 반려 선 → "반려" 보고로 끝난다. 일정 등록으로 가는 선은 `approval == '승인'` 하나뿐이다.

## 강사가 채울 곳 (결과 경로는 강사가 채움)
| 자리 | 지금 | 채우는 법 |
|---|---|---|
| 서버 `gcal` · 도구 `create_event` · `get_event` | 설계 문서의 자리 이름 | 강사가 고른 구글 서버의 실제 이름(T5 표) |
| `extract` 결과 경로(`event_id` Text · `all_required_accepted` Boolean) | `<…>` 자리 → 가져오기가 경로를 읽을 수 없다고 거절 | 그 서버로 도구를 한 번 불러 본 결과 모양에서 경로를 적는다(예: `attendees.0.status`). 전원 수락 여부를 참/거짓으로 돌려주지 않는 서버면 확인 단계를 내 MCP 서버(T4)나 에이전트 task로 바꾼다 |
| 흐름 → 지식 그래프 Task 투영 | graph.json 에는 Process(`demo:proc:qbr-prep`)만 | 판본 등록 뒤 `scripts/project_student_flow.py`(G8). 투영은 Process 를 `<ns>:proc:<흐름 id>` 로 만든다 — 흐름을 가져올 때 흐름 id 를 `qbr-prep` 로 적어야 graph.json 의 Process(회의 · 요령이 이어진 노드)와 같은 노드가 된다. 다른 id 로 가져오면 Process 가 둘이 된다 |
| 에이전트 도구 `gdrive` · `gcal` | `agent.json` 의 tools 에 적혀 있음 | 포털에 등록되지 않은 서버 이름이 있으면 에이전트 만들기가 "등록되지 않은 도구 서버입니다"로 거절된다. 구글 서버를 먼저 등록(T5)하거나, 등록 전에는 tools 를 `neo4j` · `my-biz` 로 줄여 만든 뒤 나중에 더한다 |

## 구글 서버 없이 돌리면 (2026-10-10 실측)
캘린더 도구가 없으면 에이전트는 시간 후보를 지어내지 않고 "빈 시간을 조회하지 못해 후보를 낼 수 없습니다"로 **보류**한다(단계가 멈춘다). 드라이브 없이는 자료 요약이 "확인 못 함"이 된다.
끝까지 돌리려면 캘린더 · 드라이브 서버(T5)가 필요하다. 기록: `docs/handoff/verification/2026-10-10/K-capstone.md` 5.3.

승인 부품 `human:approve`(G1, 반려 가지 포함)와 `extract` · `effect: false`(G3)는 포털에 있다. 지금 가져오면 나오는 거절 3줄(위 경로 자리 두 칸과 그 값을 쓰는 분기 조건)은 `tests/test_capstone_kit.py` 에 기대값으로 적혀 있다.
