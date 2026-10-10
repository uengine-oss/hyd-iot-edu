# K 갈래 — 캡스톤(전체 과정 랩업) 이어가기 (K-20261010-capstone)

> 2026-10-10 · 브랜치 `K-20261010-capstone`(작업 브랜치 5e30f4f에서 갈라짐) · 작업 트리 `.claude/worktrees/K-20261010-capstone`
> 근거: `NOW.md` 3.4, 설계 `verification/2026-10-09/capstone-lab.md`, 구현 기록 `cap-g1g7.md` · `cap-g3g9.md` · `cap-kit.md`, 검토 `2026-10-09/review-scripts-kit.md`
> 증거: 루트 `.evidence/k-capstone/`(gitignore — 이 PC에만 있다)
> 형식: 발견 → 분류(결함 / 의도된 차이 / 오해 / 근거 부족) → 조치(파일:줄) → 검증(검증됨 / 실패 / 미검증 / 해당 없음)

## 합칠 때 옮길 것
- (작업하며 채움)

## 0. 시작
- 통독: 프로젝트 CLAUDE.md, NOW.md 전체, REVIEW_CHECKLIST.md, capstone-lab.md, cap-g1g7.md, cap-g3g9.md, cap-kit.md, review-scripts-kit.md, `students/_template/` 전체.
- 시작 상태(실측): 브랜치 5e30f4f, `.evidence/LIVE_LOCK` 없음, 그래프 볼륨 `hyd-iot-edu_neo4j-data`(전체판), 8097 듣는 워커 없음, `/api/scenario/status` B running null.
- 사용자는 외출 중 — 사용자 결정이 필요한 것은 하지 않고 끝의 "사용자가 할 일 · 결정할 일"에 모은다.

## 1. T2 — 학생 지식 적재 · 되돌리기 · 꼭 답할 질문 검사 틀 (잠금 없이)
- 발견: `students/_template/` 에 T2 가 없어 T8 `graph.json` 을 그래프에 넣는 길이 없었다(설계 6.1 T2, 6.2 "마친 뒤 정리"의 ns 단위 삭제가 손 질의). 분류: 미구현.
- 조치(커밋 040eecb):
  - `students/_template/load_graph.py` — `check`(그래프 없이 파일 검사) · `load` · `ask` · `wipe`, 폴더는 `--dir`(기본 = 스크립트 폴더).
    - 적재는 한 트랜잭션: ① 내 파일의 id 를 남(수업 기준 · 다른 이름 공간)이 쓰고 있으면 거절 ② 다리 끝(파일에 없는 끝점)은 그래프에 있는 수업 기준 노드만 ③ 쓰기 전 파일 행을 `ontology_v2.validate_ns` 로 검사 ④ MERGE(값은 매개변수) ⑤ 커밋 전에 그래프를 다시 읽어 같은 검사 + 같은 id 중복 + 수업 기준 노드 수 변화 → 하나라도 걸리면 되돌림.
    - 되돌리기는 `MATCH (n {ns: $ns}) DETACH DELETE n` 만. 지울 것이 0개면 실패(빈 성공 금지), 내 접두어 id 가 남으면 실패, 수업 기준 노드 수가 달라지면 되돌림. 흐름 투영(G8) 노드도 함께 지워지므로 종류별 개수를 보여 준다.
    - 질문은 `it/neo4j/v2/queries.cypher` 형식(`ontology_v2.parse_queries` 재사용), `$ns` 필수, 읽기 전용 세션, 0행 = 못 답함.
  - `students/_template/graph.json` · `questions.cypher`(T1 예시 s00 의 가장 작은 조각), `example_meeting/questions.cypher`(D1~D3 의 "답할 질문" 9개), `example_meeting/README.md` 한 줄.
  - 영역 밖 최소 수정(F 영역 `scripts/ontology_v2.py`): 그래프 읽기를 `read_rows(ses)` 로 꺼냄 — 같은 읽기를 커밋 전 검사에 쓰려는 것(질의 두 벌 방지). 동작 변화 없음.
- 검증됨(단위): `tests/test_capstone_t2_load_graph.py` 31개. 뮤테이션 15개(ns 강제 · 접두어 강제 · 덮어쓰기 · 다리 끝 ns/존재 · 쓰기 전 검사 · 빈 되돌리기 · 질문 $ns · 0행 · 중복 id · 남은 접두어 · 양 끝 밖 관계 · 레이블 낱말 · 예전 적재분 알림) — 14개 잡힘, M8(지우는 문장이 ns 를 안 가림)은 살아남음: 가짜 트랜잭션이 문장을 이름으로만 알아보기 때문. 문장 글자 고정 시험을 더해 다시 → 잡힘. 문장의 뜻은 2절 라이브에서 실측.

## 2. 라이브 — T2 적재 · `validate --extra` · 질문 · 지식 지도 (잠금 18:26~)
잠금: `.evidence/LIVE_LOCK` 에 한 줄 쓰고 시작. 시작 전 그래프(전체판 볼륨 `hyd-iot-edu_neo4j-data`): 노드 965(이름 공간 0) · 관계 2348.
증거 `.evidence/k-capstone/t2/01-load-ask.log` · `02-base-validate-with-student.log` · `03-base-validate-after-fix.log`, `map/`.
- 검증됨: 적재 전 `validate --extra` · `wipe` · `ask` 는 모두 FAIL(0개 노드 / 되돌릴 것 없음 / 9문항 0행). `load` → "노드 65 · 관계 107 적재, 수업 기준 노드 965 그대로", 그래프 1030 · 2455. 다시 `load` → 같은 수(멱등).
- 검증됨: `python scripts/ontology_v2.py validate --uri bolt://127.0.0.1:7687 --extra students/_template/example_meeting/schema.json` → "checked 65 nodes, 107 relationships … PASS"(review-scripts-kit 7절의 미검증 항목).
- 검증됨: `ask` 9문항 모두 답함(예: "미결 이슈는 몇 건인가" → open_issues 3, "4인실에서 고객 회의" → room_capacity < 6 EXCLUDE · 읽는 자리 room.capacity).
- **발견(결함) — 학생 지식을 적재하면 수업 기준 검사가 깨진다.** 적재 뒤 `ontology_v2.py validate`(--extra 없음)가 FAIL 124건, 124건 모두 demo 노드(스키마에 없는 레이블 Attendee … · 속성 ns · 학생 관계). 적재 전 같은 그래프는 위반 0. 설계 3.3 이 안 다를 고른 이유("반 전체 validate 가 학생마다 흔들리지 않게")와 반대 동작.
  - 조치 `scripts/ontology_v2.py` `base_scope` + `cmd_validate`: 수업 기준 검사는 이름 공간 없는 노드와 그 노드끼리의 관계만 본다. 뺀 것은 이름 공간별 개수로 한 줄 알린다("namespace 'demo': 65 nodes skipped here — checked by validate --extra …") — 조용히 빼지 않는다. 학생 노드 검사는 `--extra` 몫(변화 없음).
  - 검증됨(라이브): 고친 뒤 같은 그래프에서 "checked 965 nodes, 2348 relationships … PASS" + 건너뜀 한 줄. 단위 시험 `test_the_base_check_skips_student_nodes_and_says_how_many`, 뮤테이션 3개(다리 관계 남김 · 학생 노드 남김 · 건너뛴 수 안 셈) 모두 잡힘.
- 검증됨(지식 지도, review-scripts-kit 7절 미검증 항목): `GET :8091/api/ontology/namespaces` → `[{"ns":"demo","nodes":65}]`, `…/graph?asset=HYD-01&ns=demo` → 노드 65 · 관계 107(전부 ns demo), 기본 보기는 487 · 970 그대로(학생 노드 0). 브라우저(playwright 1440): 이름 공간 고르기에 "demo · 항목 65개", 고르면 "항목 65 · 연결 107 · 규칙 6 · 성과 지표 3", 층 칩에 "내 업무 개념", 콘솔 오류 0 — `map/map-1-base.png` · `map-2-ns-demo.png` · `map-2-ns-demo-text.txt`.
  - U 에 넘길 것(결함 아님 · 기존 동작): 규칙 카드가 `demo:rule:after-due` 처럼 id 로 보인다. 수업 기준 규칙도 같다(`rule:dx-cooler` — Rule 에 name 속성이 없어 id 가 이름 자리에 온다). 화면에 내부 id 를 내지 않는다는 원칙과 어긋남.
  - 미검증: 지도에서 항목을 눌렀을 때의 상세(자동 클릭이 "보이지 않는 요소"로 실패 — 지도 안 가로 스크롤 밖). 손으로는 확인하지 않았다.
- 조치(작은 것): `load_graph.py` 가 Neo4j 드라이버 알림(없는 레이블 · 속성 경고 수십 줄)을 끈다 — 빈 이름 공간에 질문을 돌리면 경고가 결과를 덮었다. 틀린 이름은 검사 위반이나 0행으로 드러난다.
