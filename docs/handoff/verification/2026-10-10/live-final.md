# 최종 라이브 확인 — C 지식 공백 수정 반영 뒤 A · B · C 완주와 처리 기록 화면 (2026-10-10)

작업 위치: merge-preview 워크트리(HEAD d5d73a9). 증거: `.evidence/a161-final/`. 진행 중 — 절마다 덧붙임.
절차 근거: `c-knowledge-gap.md` 5절, `2026-10-09/c3-assembly.md` 7절, `review-c3-bc.md`.

## 1. neo4j 구조판 볼륨 · 시드 구조 재적용 — 검증됨

- 06:02 neo4j를 이 작업 트리 기준, 볼륨 `hyd-iot-edu_neo4j-data-c3`로 다시 띄움: `docker compose -p hyd-iot-edu -f compose.yaml -f .evidence/a161-final/neo4j-c3.override.yaml up -d --no-deps --wait neo4j`
  (덮어쓰기 파일은 C3 때 것 사본, `volumes: !override ["neo4j-data-c3:/data"]`). 원래 볼륨 `hyd-iot-edu_neo4j-data`는 그대로 남음. process 재시작 없음(StartedAt 20:58:13Z, RestartCount 0).
- `SEED_EDITION=structure … run --rm --no-deps kg-seed` exit 0, "kg-seed done (structure)" (`kg-seed-structure.log`).
- 확인(`kg-check-structure.txt`): `dec:compliance -REQUIRES_INPUT-> in:supplier-fail-rate` 변수 `supplier_fail_rate`. FailureMode 2(구조판). 앞 4차 적재의 PR-07 규칙 5개가 남아 있음(불량률 규칙 없음 — 재적재 전).
- `GET /api/kg/manuals/catalog`의 `dt:compliance` 입력에 `in:supplier-fail-rate`("후보 공급사 불량률 (견적, 0~1)") 있음(`catalog.json`).

## 2. PR-07 재추출 → 검토 → 적재 — 추출 검증됨, 적재 실패(409) → 지시대로 여기서 멈춤

### 2.1 워커를 먼저 띄움(순서 조정)
추출 task는 cliagents 워커가 수행한다(`it/process/procsvc/manual_extraction.py:72-74` `orchestration='cliagents'`, `agentConfig.cli='claude-code'`).
그래서 3단계의 호스트 워커를 06:03에 먼저 띄웠다: `PYTHON=../agent-afd136e4b22934cb9/.venv/bin/python bash scripts/run_worker_host.sh` → 8097 LISTEN(`worker.log`). 흐름 배포는 하지 않았다.

### 2.2 재추출(재사용 없음) — 검증됨
- `c3_ingest.py extract PR-07`(`--reuse` 없음) 06:03:43 → 140.6초, 새 추출 `manual_source_extraction.3b9e9133-…`, `reused_extraction: false`
  (`proposal-PR-07.json`, `extract-PR-07.log`). 절차 3 · 경고 15 · 규칙 7.
- **LLM이 지시 2.1을 따랐다(고치기 전 원본 그대로)**:
  - `SOP-PUR-13` link `actions[0].value` = **`sup:c`**. 경고 원문: "단계 1 '리드타임이 가장 짧은 공급사'를 그대로 적용하면 … 펌프 축 씰 키트 · 쿨러 코어는 sup:c(C트레이딩 …, AVL 아님) … 단계 2의 AVL 조건은 값 고르기에 미리 적용하지 않고 dt:compliance EXCLUDE 규칙(rule:pr-exclude-urgent-non-avl)으로 옮겼다".
  - 불량률 규칙 **생성**: `rule:pr-penalty-high-fail-rate-inspection` — `dt:compliance` · `PENALTY` · `in:supplier-fail-rate > 0.1` · 감점 20 · `penalizes msr:cost` · `applies_to` SOP-PUR-11/12/13.
  - "불량률 입력이 없어 규칙으로 만들지 않았다" 경고 **없음**. 남은 관련 경고: 불량 기대비용(수량 × 불량률 × 250) 총비용 식은 고정 감점이 아니라 규칙으로 안 만듦(c-knowledge-gap 2절 "이번에 안 함"과 같은 판단), 감점 대상 지표가 없어 msr:cost로 제안.
  - SOP-PUR-11 → `sup:b`, SOP-PUR-12 → `sup:a`. 중복: `rule:pr-exclude-urgent-non-avl`(13만)은 `rule:pr-exclude-non-avl-supplier`(셋)의 부분집합.
- 검토 기록 `review-PR-07.json`: `by` = "검증 대역(Claude, 메인 지시) — 사람 아님", 원문 대조 뒤 고칠 것 없음(`links`/`drop`/`add` 없음, `warnings_read: true`), 메모에 LLM 원본 결과를 적음.

### 2.3 적재 — 실패(409), 우회하지 않음
- 06:07:13 `c3_ingest.py commit PR-07 --review …` → **HTTP 409** `"Skill skill:sop-pur-11: 다른 원천/기존 지식이 소유합니다. 덮어쓰지 않았습니다"` (`commit-PR-07.log`, `ingest-PR-07.json`).
  그래프는 그대로(트랜잭션 롤백 — `rule:pr-*` 0개, SOP-PUR-11~13 소유 문서 그대로 `…:339d914c…`, `kg-after-409.txt`).
- **원인(파일:줄)** — c-knowledge-gap 5절 5의 가정("같은 문서의 앞 배치 0092c109…는 재적재가 대체한다", `manual_graph.py:250-257` 스냅숏 검사)까지 가지도 못했다. 재추출이 **다른 문서**로 들어갔다:
  - `scripts/c3_ingest.py:127` `extract()`가 `/api/kg/manuals/preview`에 `{"filename", "data"}`만 보내고 `document_id`를 넘기지 않는다.
  - `it/process/procsvc/manual_sources.py:132-133` `document_id`가 없으면 `str(uuid4())`로 **새 문서**를 만든다. 같은 원문(sha256 `7cb1c01da48c…`)이 문서 두 개로 보관됨: `339d914c…`(10-09 11:24, 4차 적재 · 배치 0092c109 ACTIVE)와 `b7379c5e…`(10-10 06:03, 이번) — `sources.txt`.
  - 그래서 제안의 `previous_batch`가 `None`, `conflicts`에 SOP-PUR-11/12/13이 `kind: other_document`로 이미 나와 있었다(`manual_graph.py:148-154` `sop_conflicts`) — 적재 때 `manual_graph.py:165-166` `_validate_targets`가 409.
  - `c3_ingest.py:172-176`의 409 재시도는 `knowledge_conflicts`(지식 id 충돌)만 다루고 SOP 소유 충돌은 다루지 않는다(맞는 동작 — 남의 SOP를 덮으면 안 된다).
- **분류**: 결함(시험 도구 `scripts/c3_ingest.py`) — 재추출이 "같은 문서의 새 판"이 되도록 앞 문서의 `document_id`를 넘겨야 한다. 백엔드(`manual_sources` · `manual_graph`)는 계약대로 동작했다(같은 SOP를 다른 문서가 덮어쓰지 못하게 막음).
  수업 경로(포털 지식 관리)가 같은 문서를 다시 올릴 때 `document_id`를 넘기는지는 확인하지 않았다(미검증).
- **고치지 않았다**(지시: 409면 멈춰 보고, 백엔드 · 도구 결함은 메인 판단). 고치는 방향(제안): `extract`가 원천 목록(`GET /api/kg/manuals/sources`)에서 같은 파일 이름의 문서를 찾거나 `--document <id>` 인자를 받아 preview에 `document_id`를 넘김 →
  `manual_sources.py:134-143`가 같은 sha256이면 옛 원천(`manual:339d914c…:7cb1c01…`)을 그대로 돌려줌 → 그 원천에 새 추출(재사용 없음) → `previous_batch` = 0092c109 → `manual_graph.commit`의 스냅숏 검사(5절 5의 두 번째 409 가능성)로 넘어감.
  지금 남은 새 문서 `b7379c5e…`(원천 · 추출 제안, 그래프 적재 없음)는 지우지 않았다.

## 3~7. 미검증 — 2절 409로 멈춤
흐름 배포 · A · B · C 포털 완주 · 처리 기록 화면 캡처 · C 판단 대조 · 회귀는 하지 않았다. C는 지금 지식(불량률 규칙 없음 · 13 → A정밀)으로 돌면 4차와 같은 판단이 나오므로 대조 의미가 없다.

## 8. 정리 — 검증됨
- 워커: `pkill -f worker.main` → 프로세스 0, 8097/8098 LISTEN 없음.
- 실행 중 처리 건 0(`/api/instances` RUNNING 0). 흐름은 배포하지 않아 deploy-reset 불필요. 설비 · 업무 값은 건드리지 않음(B · C 표시 켜짐 그대로).
- neo4j 원래 볼륨 `hyd-iot-edu_neo4j-data`(전체판, FailureMode 7)로 이 작업 트리 compose로 다시 띄움(`neo4j-back.log`). 구조판 볼륨 `hyd-iot-edu_neo4j-data-c3`는 남김(이번 시드 구조 MERGE로 `in:supplier-fail-rate` 들어간 상태). process 재시작 없음(RestartCount 0).
- 시험 잔재: 이번에 만든 처리 건은 추출 1건(완료, 정상 기록)뿐이라 숨기지 않음.

---

# 2차 — 409 원인 수정(e556be3, `c3_ingest.py` `loaded_document`) 뒤 다시 (2026-10-10 09:21~)

## 2-1. neo4j 구조판 다시 · 시드 재적용 — 검증됨
- 09:21:47 neo4j → `hyd-iot-edu_neo4j-data-c3`(`neo4j-structure-up2.log`). kg-seed 구조판 exit 0(`kg-seed-structure2.log`) — 다만 `compose run`이 컨테이너를 띄우기까지 약 16분 걸렸다(09:21 → 09:37, 원인 미확인, 시드 자체는 수십 초).
- `in:supplier-fail-rate` 변수 `supplier_fail_rate`, FailureMode 2. `GET /api/kg/manuals` current: PR-07 = 문서 `339d914c…` 배치 `0092c109…`, PM-02 `f164900f…`, HM-8 `6179f156…`.
- 1차의 고아 문서 `b7379c5e…`(원천 · 추출 제안만, 그래프 적재 없음)는 지우지 않음.

## 2-2. 워커 · 재추출 — 1회차는 워커 LLM 세션 한도로 끊김
- 09:38:11 워커 기동(PID 40362, 8097, `worker2.log`). 09:38:19 `c3_ingest.py extract PR-07`(재사용 없음) → 추출 `manual_source_extraction.ac6fbae5-…`.
- 워커 로그: 09:38:23 실행 시작 → 첫 도구 호출 09:54:21(16분 무응답) → 09:54:47 그래프 읽기 뒤 무응답 →
  **10:22:29 `RunFailed: You've hit your session limit · resets 10:30am (Asia/Seoul)`** — 워커가 쓰는 Claude Code CLI 세션 한도.
- 그 추출 처리 건은 task `866a2c12…`가 IN_PROGRESS인 채 RUNNING으로 남음. `POST /api/todolist/{wid}/cancel`은 409 "워커가 실행 중인 에이전트 작업(STARTED)만 취소할 수 있습니다" — 실패한 task를 끝낼 API가 없다(잔재, 8단계에서 숨김 처리). 폴링하던 스크립트는 멈춤(pkill).
- 10:3x 한도 풀린 뒤 `--reuse` 없이 한 번 다시 실행(`extract3-PR-07.log`).

## 2-3. 재추출 2회차 — 검증됨 (같은 문서의 새 판)
- 10:32:14 `extract PR-07`(재사용 없음) → 115.6초, 추출 `manual_source_extraction.059b0927-…` (`extract3-PR-07.log`, `proposal3-PR-07.json`).
- 원천 `manual:339d914c…:7cb1c01…` — **같은 문서**(e556be3 수정 효과). `previous_batch` = **`0092c109…`** ✓. `knowledge_conflicts` 없음.
- `conflicts`에는 SOP-PUR-11/12/13이 여전히 `other_document`로 나오지만 owner가 `…:339d914c…` = **자기 문서**다 → 표시 결함(아래 발견 F-1). 적재 검사와는 별개.
- **LLM 원본(고치기 전)**: SOP-PUR-13 → **`sup:c`**(경고: "단계 1의 선택 기준만 적용 … sup:c는 승인 공급사가 아니므로 단계 2 조건은 rule:pur-exclude-non-avl(EXCLUDE)이 이 절차를 제외하게 했다").
  불량률 규칙 **생성**: `rule:pur-penalty-full-inspection` = `in:supplier-fail-rate > 0.1` AND `in:supplier-avl == true`, PENALTY 20, `msr:cost`, 세 SOP(원문 "불량률이 10 %를 넘는 **승인** 공급사에"와 맞음). 11 → sup:b, 12 → sup:a. 규칙 6개(id는 옛 배치와 같은 `rule:pur-*` 체계).
  "불량률 입력이 없어 규칙으로 만들지 않았다" 경고 없음.
- 검토 기록 `review3-PR-07.json`(by "검증 대역(Claude, 메인 지시) — 사람 아님", 고칠 것 없음, 원본 결과 메모).

## 2-4. 적재 — 실패(409, 스냅숏 검사) → 지시대로 멈춤
- 10:34:41 `commit PR-07 --review review3-PR-07.json` → **409 "적재 뒤 속성/규칙/실행 등의 참조가 바뀌었습니다. 변경 내용을 먼저 조정하세요"** (`manual_graph.py:255-256`, `commit3-PR-07.log`, `ingest3-PR-07.json`). 그래프 그대로(문서 head 0092c109 유지).
- 무엇이 바뀌었나(읽기 전용 비교 `snapshot-diff-PR-07.txt`, 스크립트는 `_snapshot`과 같은 범위를 SET 없이 읽음): 노드 31 = 31, 관계 기록 87 → 지금 **90**. 늘어난 3개 모두
  `(:DecisionCase)-[:CHOSE]->(:Skill {id:'skill:sop-pur-13'})` — `case:DEC-1009-006-c5bd`, `case:DEC-1009-010-618d`, `case:DEC-1009-030-84ab`(10-09 C 완주들의 판단 기록 투영이 고른 스킬).
- **분류**: c-knowledge-gap 5절 5가 예고한 경우 그대로 — 설계상 충돌(결함이라기보다 결정 필요). 문서 개정은 문서가 소유한 노드를 지우고 다시 만드는데(`_replace`), 실행 이력(판단 기록)이 그 스킬을 가리키면 이력이 끊기므로 막는다. 
  배치 되돌리기(`/rollback`)도 같은 검사를 받는지는 확인 안 함. 메인이 정할 것: ① 판단 기록이 가리키는 스킬은 지우지 않고 속성 · 관계만 바꾸는 개정 경로, ② 구조판 볼륨의 지난 C 판단 기록 투영을 정리하고 다시 적재, ③ 기타.
- 이 409 때문에 3~7단계(흐름 배포 · A · B · C 완주 · 처리 기록 캡처 · C 대조 · 회귀)는 **미검증**. 구동 · 캡처 스크립트는 준비됨(세션 스크래치 `final/run_final.py`, `final/record_shot.py` — 승인 · 처리 기록을 뷰포트를 내용 높이로 늘려 전체 캡처, '모두 펼치기' 뒤 캡처 · 화면 글 텍스트 저장).

## 발견
| # | 발견 | 분류 | 위치 |
|---|---|---|---|
| F-1 | 추출 제안의 `conflicts`가 자기 문서가 소유한 SOP를 "다른 문서(other_document)"로 표시 — 날 document_id를 넘기는데 그래프의 `_manual_document`는 `테넌트 해시:document_id`다. 바로 아래 knowledge_conflicts(61-63행)는 해시 키를 넘긴다. 개정 때 검토 화면이 거짓 경고를 보일 수 있음(포털 화면 확인 안 함) | 결함(백엔드, 고치지 않음) | `it/process/procsvc/manual_api.py:58-59` → `manual_graph.py:148-154` |
| F-2 | 개정 적재가 실행 이력 참조(`DecisionCase -CHOSE-> Skill`)로 막힘 | 설계 충돌(결정 필요) | `manual_graph.py:255-256` |
| F-3 | 워커 LLM이 세션 한도로 실패한 에이전트 task를 끝낼 API가 없다 — `/api/todolist/{wid}/cancel`은 STARTED만 받아 409, 처리 건이 RUNNING으로 남음(잔재 정리 스크립트로 숨김) | 결함(가시성 · 운영, 고치지 않음) | `instance_mode.py:1060-1070`, 워커 `runner.py:412-421 _fail` |
| F-4 | `compose run kg-seed`가 컨테이너를 띄우기까지 약 16분(09:21 → 09:37) | 근거 부족(원인 미확인) | `kg-seed-structure2.log` |
| F-5 | 워커 LLM 첫 도구 호출까지 16분, 이후 28분 무응답 뒤 한도 실패 — 한도 직전 지연으로 보임 | 환경(한도) | `worker2.log` |

## 8-2. 정리 — 검증됨
- 워커 `pkill -f worker.main` → 프로세스 0, 8097/8098 LISTEN 없음.
- 한도로 끊긴 추출 처리 건 `manual_source_extraction.ac6fbae5-…` 숨김: `cleanup_residue_instances.py --before 2026-10-10T01:40Z --apply`(1건 · todo 1 · 그래프 투영 1, 백업 `residue-extract-limit/backup.json`). RUNNING 처리 건 0.
- neo4j 원래 볼륨 `hyd-iot-edu_neo4j-data`(전체판, FailureMode 7)로 되돌림(`neo4j-back2.log`). 구조판 볼륨 c3 남김(새 판 원천 · 추출은 Supabase에, 그래프는 0092c109 그대로). process 재시작 0.
- 흐름 배포 안 했음(deploy-reset 불필요). 설비 · 업무 값 안 건드림. 고아 문서 `b7379c5e…` 그대로(기록만).
- 고친 코드 파일 없음.

## 정정 (메인, 10-10)

- F-3 "실패한 에이전트 task를 끝낼 API가 없다"는 틀린 진단이었다. `POST /api/todolist/{wid}/close`(포털 '단계 닫기', instances.close_agent_task)가 IN_PROGRESS + draft FAILED를 끝낸다. `/cancel`은 실행 중(STARTED) 실행을 멈추는 요청이라 거절이 맞다. 실제 결함은 추출 결과 API가 멈춘 실행을 '진행 중'으로 보고한 것 — ced4dee에서 고침(`manual-revision-fix.md` 4절).
- F-1(278b722) · F-2(8429c29: 판단 이력은 지우지 않고 남는 노드는 제자리 개정) 고침. 라이브 재확인은 캡스톤 갈래 합친 뒤 한 번에.
