# 캡스톤 강사 키트 T0 · T5 · T6 · T7 · T8 (cap-kit 갈래)

> 2026-10-10 · 브랜치 cap-kit(merge-preview 2fbefff에서 갈라짐) · 근거 설계: `docs/handoff/verification/2026-10-09/capstone-lab.md`(c2f2188 원문 그대로 이 브랜치에 넣음)
> 범위: 출발본(키트)만. `it/` 아래 제품 코드 변경 없음. docker · 라이브 스택 · 워커 사용 없음.

## 0. 시작
- 통독: 설계 문서 전문(2절 · 2.1 · 3절 · 5.2 G1~G10 · 6.1), 점검표, 공용 헌법, 프로젝트 CLAUDE.md.
- 기존 출발본 확인: `students/_template/schema.json`(T1), `table.sql`(T3), `mcp_table_reader/server.py`(T4). T2(적재 · 되돌리기 스크립트 틀)는 `students/_template/` 에 없음 — 범위 밖(이번 과제는 T0 · T5 · T6 · T7 · T8), 기록만.
- 설계 문서를 `docs/handoff/verification/2026-10-09/capstone-lab.md` 로 넣음(`git show c2f2188:` 그대로, diff 0 확인).

## 1. 만든 것 (모두 `students/_template/`)
| 출발본 | 파일 | 요점 |
|---|---|---|
| T0 | `case_card.md` | 빈 카드 7칸 + 판정 체크 5개, 3절 예시를 채운 한 장(지는 안 2 · 미달 가지 거절 · 무응답 · 승인 지연) |
| T5 | `google_mcp.md` | 비밀 값 넣는 자리(`${SECRET:GOOGLE_TOKEN}`, `HYD_SECRET_<이름>`), 주소형 헤더 · 명령형 환경변수 자리, 읽기 · 강사 확인 읽기 · 쓰기 판정표(`mcp_check.read_only_verdict` · `confirmable` 규칙 그대로), 구글 도구 이름은 빈칸 |
| T6 | `agent/goal.md`, `agent/SKILL.md` | 목표 문장 틀 · 포털 칸 표 · 막혔을 때, SKILL.md 틀(절차 5단계 · 규칙으로 빼기 표 · 결과 칸 `proposal.options[].slot·reason·score` · `recommended` · `losers[].slot·why` · `docs[].title·link`) |
| T7 | `flow.bpmn` | 레인 3(담당자 · 에이전트 · 시스템), 시작 · 에이전트 · 승인(userTask) · 시스템 2 · 분기 · 결과 보고 2 · 끝, task 이름 비움, DI 전부 |
| T8 | `example_meeting/` | D1~D3 예시 문서, `schema.json`(ns demo), `graph.json`(65노드 · 107관계), `table.sql`(stu_demo, 3.4 표 3개), `agent/agent.json · SKILL.md · proposal.example.json`, `flow.bpmn`, `mapping.json`, `README.md` |

## 2. 의심 장부 (설계 문서 ↔ 실물)
| 발견 | 분류 | 조치 |
|---|---|---|
| 설계 3.3 "Skill · Step: skill:<ID>:qbr-prep" — v2 `Skill.kind` 는 `control · work_order` 뿐 | 설계 근거 부족(확정 스키마 변경 0 조건과 충돌) | 학생 클래스 `PrepGuide`(layer skill) + 다리 `GUIDE_STEP → v2 Step`, `GUIDES → Process` |
| 설계 3.3 `Process-[:ACTS_ON]->Meeting` — ACTS_ON 은 v2 관계라 학생 재정의 불가(check_extra 거절) | 설계 근거 부족 | T1 과 같은 이름 `Meeting-[:PREPARED_BY_PROCESS]->Process` |
| 설계 3.3 Meeting `title!` — 학생 클래스는 id · name 필수(check_extra) | 의도된 차이 | name 을 회의 제목으로 |
| 설계 D1 규칙 5개, 3.5 4안 "due_by 넘김 감점"의 근거 규칙이 D1 에 없음 | 근거 부족 | D1 6 "요청 마감 넘김 감점"을 더해 규칙 6개(EXCLUDE 5 · PENALTY 1) |
| T1 · T3 예시(Meeting/AgendaItem/Material, 표 meeting/attendee)는 3절보다 줄인 모양 | 의도된 차이(T1 · T3 은 형식 틀) | T8 은 3.3 · 3.4 그대로, ns/스키마 `demo`/`stu_demo` 로 갈라 섞이지 않게. T1 · T3 은 고치지 않음 |
| D3 회의록의 KnowledgeSource.kind — v2 enum(manual · regulation · policy · strategy)에 회의록 자리 없음 | 의도된 차이 | manual 로 둠 |
| `effect_parts.validate` 는 svc:mcp-call 설정의 모르는 칸(`extract` · `effect`)을 거절하지 않고 무시한다 | 결함 후보(G3 갈래 몫, it/ 수정 금지) | 지금 가져오기에서 extract 는 조용히 버려지고, 값 연결 검사가 대신 거절함을 시험에 기대값으로 적음. G3 에서 모르는 칸 거절 권고 |
| `students/_template/` 에 T2(적재 · 되돌리기 스크립트 틀)가 없다 | 범위 밖 | graph.json 을 Neo4j 에 넣는 경로는 미검증으로 남김 |

## 3. 검증
- `tests/test_capstone_kit.py` 15개 통과(검증됨). 관련 시험 `tests/test_capstone_*.py` 82개 통과.
- bpmn.io 파서(`bpmn-moddle` 8.1.0, `/Users/uengine/process-gpt/services/frontend/node_modules` 읽기만): T7 · T8 그림 경고 0, DI 22 · 29개. 일부러 끊은 선 → `unresolved reference` 경고 1 (검사가 잡음 확인).
- 포털 가져오기 파서: T7 은 `parse_bpmn` 문제 0, 효과 없는 부품으로 채우면 `check` ok(등록 검사 포함). T8 은 `parse_bpmn` 문제 0, `check` 는 G1 · G3 거절 6줄만 — 시험 기대값 `EXPECTED_BEFORE_G1_G3`(G1 · G3 합친 뒤 가져오기 검사).
- 스키마: `ontology_v2.py check-extra --extra .../example_meeting/schema.json` PASS, `validate_ns`(= `validate --extra` 의 검사 함수)로 graph.json 위반 0, 확정 스키마 `it/neo4j/v2/schema.json` 변경 0.
- 뮤테이션 4회(모두 잡힘 후 원복 · cmp 동일): ① T7 DI 도형 하나 지움 → DI 시험 실패 ② 승인 부품을 `task:select` 로 → G1 · G3 기대값 시험 2개 실패 ③ graph.json 노드 ns 지움 → 이름 공간 시험 실패 ④ T5 비밀 이름을 소문자로 → 비밀 규칙 시험 실패.

## 4. 미검증
- 실제 bpmn.io 화면(demo.bpmn.io)에서 열기 — 같은 파서(bpmn-moddle)로만 확인.
- Neo4j 적재 뒤 `validate --extra` CLI(라이브 Neo4j 없음, T2 없음), DDL 실제 실행(Supabase 미기동), 포털 등록 · 구글 연결 · 한 건 완주 — docker · 라이브 스택 금지 범위.
- 구글 서버 · 도구 이름과 결과 경로(T5 표 · mapping.json 의 자리) — 강사가 서버를 고른 뒤 채울 칸.
