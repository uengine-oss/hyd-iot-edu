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

---

# 3차 — F-1 · F-2 · F-3 수정 반영 뒤(스택 02:09Z 재빌드, 8090310) 다시 (2026-10-10 11:10~)

## 3-1. neo4j 구조판 · 시드 — 검증됨
- 11:10:23 neo4j → c3 볼륨(`neo4j-structure-up3.log`), kg-seed 구조판 exit 0, 25초(`kg-seed-structure3.log`). process StartedAt 02:09:19Z, RestartCount 0.

## 3-2. PR-07 적재 — 검증됨 (200, 판단 이력 유지)
- 적재 전 `skill:sop-pur-13` CHOSE 3건 elementId(`chose-before.txt`): 관계 `5:…:1736`(DEC-1009-006-c5bd) · `5:…:1459`(DEC-1009-010-618d) · `5:…:1803`(DEC-1009-030-84ab), 스킬 노드 `4:…:432`.
- 추출 059b0927 결과 다시 읽기(`extraction-059b-reread.json`): `conflicts` **[]**(F-1 수정 효과), `knowledge_conflicts` [], `previous_batch` 0092c109. 새 추출 불필요.
- 11:11:17 `commit PR-07 --review review3-PR-07.json` → **200**(`commit4-PR-07.log`, `ingest4-PR-07.json`). 영수증 `history_kept` = `[{node: "Skill skill:sop-pur-13", type: "CHOSE", count: 3}]`, 새 배치 `6d921c06-…`.
- 적재 뒤(`kg-after-commit4.txt`): CHOSE 3건의 관계 · 사례 · 스킬 elementId가 **적재 전과 같다**(제자리 갱신). 문서 head = `6d921c06…`. `rule:pur*` 6개 = 제안의 6개(옛 배치에만 있던 규칙 0 — 옛 5개는 같은 id로 제자리 갱신, 새로 `rule:pur-penalty-full-inspection` `supplier_fail_rate > 0.1 and supplier_avl == true` PENALTY 20 → msr:cost, APPLIES_TO 11 · 12 · 13). `skill:sop-pur-13 -CONSISTS_OF {value: "sup:c"}-> action:purchase-request`.

## 3-3. 흐름 배포 · 워커 — 검증됨
- 11:11:50 `c3_flows.py deploy` → c3_cooling · c3_pm · c3_spare 사전 검사 ok, 판 4 배포(`flows-deploy.log`).
- 워커 1개(PID 94132, 8097, `worker3.log`, `PYTHON=../agent-afd136e4b22934cb9/.venv/bin/python bash scripts/run_worker_host.sh`).

## 3-4. 포털 버튼 완주 A → B → C (한 건씩, 승인 1회) — 검증됨
구동: 세션 스크래치 `final/run_final.py`(C3 run_live.py 기반: 포털 버튼 클릭 → 처리 건 대기 → 승인 task 를 포털에서 열어 승인자 역할로 [승인] 클릭 → 끝까지). 증거 `.evidence/a161-final/live/`.

| | 처리 건 | 버튼 → 처리 건 | 에이전트 | 승인 대기* | 승인 → 끝(시스템) | 버튼 → 끝 | 결과 |
|---|---|---|---|---|---|---|---|
| A [쿨러 열화 주입] (김운전 · 운전원) | c3_cooling.4f93a9d0… | 43.5초 | 94.4초(도구 10) | 13.2초 | 63.7초(명령 0.9 · 재관측 60.0 · 작업지시 0.8 · 보고 0.3) | 214.8초 | 정상, WO-1010-C058 |
| B [정기 점검] (박정비 · 설비보전팀장) | c3_pm.a49bb840… | 1.6초 | 64.7초(도구 13) | 39.4초* | 1.1초(오더 · 메일 0.8 · 보고 0.3) | 105.2초* | 정상, WO-1010-2E26 · 메일 1통 |
| C [재고 보충] (정구매 · 구매 담당) | c3_spare.4af595fb… | 1.6초 | 51.8초(도구 9) | 16.2초 | 1.5초(발주 · 메일 0.2 · 입고 0.9 · 보고 0.3) | 75.3초 | 입고 완료, PR-1010-E7ED · GR-1010-71A8 |

\* 승인 대기는 캡처(1440 · 390) 시간 포함 — 사람 손 시간이 아니다. B는 승인 직전에 구동 스크립트를 멈추고(캡처 결함 수정, 아래 3-5) 같은 처리 건에 다시 붙어(resume) 승인했으므로 승인 대기 39.4초 · 버튼 → 끝 105.2초가 늘었다(처리 건 기록 시각 기준: T_agent 02:17:54.9 → 02:18:59.6, T_approve → 02:19:38.9, 끝 02:19:40.1).
- 표시: B · C 끝난 뒤 `/api/scenario/status` alert **false**(표시 꺼짐, `B-5-after-1440.png` · `C-5-after-1440.png`) → [초기화](박정비 · 정구매) 뒤 둘 다 **true**(`R-B-after-reset-1440.png` · `R-C-after-reset-1440.png`).
- A: [쿨러 복구](김운전) "HYD-01 쿨러 복구 · 열화로 열린 처리 건에 기록" — 복구 누름이 같은 A 처리 건 기록(`SCENARIO_BUTTON`, `restores: PRESS-ec25a7d4735f`)으로 붙음(`A-8-after-restore-1440.png`).
- 재관측 값 흐름(A): 60초 동안 유온 61.4 → 51.5 ℃, 기준 55 ℃ 아래 58 %, 경보 해제 예, 관측 연장 1회 — 처리 기록 5단계에 그래프 · 수치로 보임.
- **G9**: A 에이전트 작업 폴더 `.evidence/workspace/hyd/67b1b15d-…/CLAUDE.md` 와 `tests/fixtures/constitution_hyd_2fbefff.md` `cmp` 같음.

## 3-5. C 판단 대조 (c-knowledge-gap 5절 6) — 검증됨, 기대와 일치
`C-decision.json`(DEC-1010-006-b837):

| 카드 | 공급사 사실 | 점수 | 점수 성분 | 규정 결과 | 기대 |
|---|---|---|---|---|---|
| SOP-PUR-11 순정(OEM) | fail_rate 0.02 · AVL 예 · 330만 원 | **2.82 · 1위(추천)** | bsc 0 · warn −0.5 · delivery 1.32 · forecast 2 | 경고 `po_amount > 300`만 | 추천 ✓ (기대 점수 약 1.82와 다른 것은 BSC: 새 추출의 득실이 "부품 품질 ↑ · 재고량 ↑"라 4차의 −1이 0이 됨) |
| SOP-PUR-12 대체 승인(A정밀) | fail_rate **0.12** · AVL 예 · 210만 원 | 1.32 · 2위 | bsc −1 · **penalty −1.0** | 감점 `rule:pur-penalty-full-inspection` 20 | 감점 · 약 1.32 ✓ |
| SOP-PUR-13 최단 납기(C트레이딩) | fail_rate 0.3 · AVL 아니요 · 120만 원 | 2.32(제외) | — | **feasible false**, 위반 `rule:avl` · `rule:pur-exclude-non-avl` | 제외 ✓ |

- `expected_defect_cost` 결정 문서 어디에도 없음, 카드 사실에 `supplier_fail_rate` 있음.
- 참고: 처리 건 변수에 다른 판단 id `DEC-1010-005-cc60`(GET 404)이 함께 보임 — 에이전트가 판단을 두 번 낸 흔적으로 보이나 원인 미확인(근거 부족).

## 3-6. 처리 기록 화면(caseRecord) 점검 — A · B · C 1440 · 390
캡처: `X-7-record-{1440,390}.png`(기본) · `X-7-record-open-{1440,390}.png`('모두 펼치기' + 모든 접기 열고 원문 불러온 뒤 전체 높이) · `X-7-record-text.txt`(화면 글). 승인 화면 `X-3-approval-{1440,390}.png`. 수정 전 캡처는 `live/before-fix/`.

| 볼 것 | A | B | C |
|---|---|---|---|
| 시작 단계 | '센서 경보로 시작' + 수업 버튼 기록 줄([쿨러 열화 주입] 김운전, 수정 뒤 누른 시각 11:12:25) · 경보 규칙 · 들어온 값 | '수업 버튼으로 시작' · 누른 사람 박정비 · 누른 시각 · 근거 값 | '수업 버튼으로 시작' · 정구매 · 시각 · 재고 값 |
| 가져온 값과 출처 | 36건(값 · 시스템 · 읽은 방법) | 같은 표 | 같은 표 |
| 지식 그래프 경로 · 스킬 | 경보 → 증상 → 고장 유형 ← 원인, 원인 → 고장 유형 → 완화 조치, 스킬 cooling-emergency-response 읽음 1 | 스킬 pm-schedule-planning | 스킬 spare-purchase-planning |
| 도구 호출 입력/출력 | 물음 · 받음 한 줄씩, 긴 원문(13,763자 · 128,466자)은 '원문 보관' → 펼치면 event-payloads로 불러옴 | 같음 | 같음 |
| 경쟁 안과 진 이유 | 4개(추천 팬 최대 운전, 짐 2 · 짐 1) 점수 차 · 감점 문장 | 4개(추천 단독 시행, 짐 지금 정지 오더 손실 감점, 제외 미루기 · 두 대 묶기) | 3개(추천 OEM, 짐 A정밀 불량률 감점 문장, 제외 13 AVL) |
| 승인 · 실행 · 확인 | 김운전 11:14:56, 승인 순간 다시 확인한 값, 명령 CMD-1010-0001 응답, 재관측 그래프, 작업지시 | 박정비, 정비 오더 · 공지 메일(받는 사람 · 제목 · 본문) | 정구매, ERP 발주 · 메일, 입고 · 재고 반영(가용 7 ≥ 2) |
| '설비 명령 없음' · '이 흐름의 끝' | 해당 없음(설비 흐름) | 있음 | 있음 |
| 기록에 없는 것 | 2줄(모델 안쪽 생각 · 로그인 없음) | 3줄(+메일 읽음 여부) | 3줄 |

**찾은 화면 결함과 조치**(포털, 근본 수정 · 캐시 `20261010-lf1` · `node --check` · 관련 시험 `test_c3_bc_review` · `test_capstone_g7_card` · `test_u1_task_detail` 20 통과, `test_worker -k instances` 1 통과):

| # | 결함 | 원인(파일:줄, 수정 전) | 조치 | 확인 |
|---|---|---|---|---|
| P-1 | A 시작 단계의 수업 버튼 줄 시각이 누른 때(11:12:25)가 아니라 처리 건에 붙인 때(11:13:09) | `caseRecord.js:172` 버튼 기록 줄 t0 = 기록 줄 timestamp(`rowsOf` 57-83의 sys 줄) | 버튼 기록 줄은 `data.at`(누른 시각) | 다시 캡처: A 11:12:25 · B 11:17:54 · C 11:21:25 |
| P-2 | 결과 보고 '보고에 실은 값'의 승인자가 `user:kim-op` · `user:jung-buy` | `caseRecord.js:615` approved_role 만 이름으로 바꿈 | approved_by 도 `W().who` | 김운전 · 정구매 |
| P-3 | C 카드별 사실(공급사 불량률 · 발주 금액 · 납기 여유 · AVL)이 화면 어디에도 없음 — 결정 표는 "후보마다 계산"이라고만 적음(블랙박스) | `caseRecord.js:338-358` altHtml 이 카드의 `facts`를 그리지 않음 | 결정 수준에서 비어 있는 사실만 카드마다 "이 안의 값" 한 줄(이름표 있는 것만), `plainWords.js` 에 `supplier_avl` 이름표 | C: "공급사 불량률(비율) 0.02 / 0.12 / 0.3 · 승인 공급사(AVL) 예/예/아니요 · 발주 금액 330/210/120 만원" |
| P-4 | 승인 화면 '승인하면 시스템이 구매 요청 **sup:b**' | `enterprise.js:262-263` actionLabel 이 값 id 를 그대로 | 값은 `UI.idText`(숫자는 그대로) | node vm 으로 실제 파일 렌더: 수정 전 `sup:b`, 수정 뒤 "B-OEM (순정)"(`C-approval-card-render-{before,after}.json`) |
| P-5 | 승인 화면 '지식 그래프 근거 **skill:sop-pur-11** → 부품 품질'(B: skill:sop-pm-11) | `approvalCard.js:42` 경로 첫 노드(이 안의 스킬)를 정적 사전 `names.json` 에서 찾음 — 문서 적재 스킬은 사전에 없음 | 첫 노드가 이 안이면 카드 이름 | 수정 뒤 "순정(OEM) 공급사 표준 발주 → 부품 품질" |
| P-6 | '가용 재고 -1 개'(실제 가용은 1개, 값은 가용 − 재주문점) | `plainWords.js:45` spare_gap 이름표가 '가용 재고' — 온톨로지 `in:spare-gap` '예비품 가용 재고 − 재주문점' | 이름표 '가용 재고 − 재주문점' | C 기록 화면 |
| P-7 | 처리 건 목록 카드 칩 **E_end** | `instances.js:38` 이름 사전에 활동만 넣고 이벤트 이름은 뺌, `:338` 칩이 id 로 떨어짐 | 이름 사전에 이벤트 이름도, 칩은 그 이름 먼저 | 목록 글에 E_end 없음 · '끝'(`L-list-after-fix-1440.png`) |
| P-8 | 승인 화면 캡처가 승인 카드 위쪽을 잘라 찍음 | 시험 도구(구동 스크립트) — 안쪽 스크롤 칸이 내려간 채 전체 페이지 캡처 | 캡처 전 모든 스크롤 0 · 높이 다시 잼. A 승인 캡처(`A-3-approval-*`)는 수정 전이라 위쪽 잘림 — B · C는 온전 | `B-3` · `C-3-approval-1440.png` |

**백엔드 · 보고만**(고치지 않음):
- B-1 수업 버튼 기록 이름 중복 "수업 버튼 [쿨러 열화 주입] — 김운전 김운전": `it/process/procsvc/scenario_buttons.py:129` 가 `name`에 누른 사람을 넣고 `by`도 따로 실어, 포털의 일반 줄 그리기(`caseRecord.js:741` sysDetail · `trace.js:179`)가 `by`를 한 번 더 붙인다. 이름에서 사람을 빼는 쪽이 근본(다른 기록 줄과 같은 꼴).
- B-2 B 공지 메일 본문에 `(승인 user:park-maint)` — 흐름 정의의 메일 본문 틀 `scripts/c3_flows.py:104` `"… (승인 {approved_by})"`가 사람 id 변수를 넣음(화면은 보낸 원문을 그대로 보여 줄 뿐). 받는 사람에게 가는 글이라 이름 변수가 필요(흐름 · 부품 쪽 결정).
- B-3 C 판단 id 두 개(`DEC-1010-005-cc60` 404) — 근거 부족, 위 3-5.
- 사소(유지): 출처 칩이 "PR-7.6 PR-7.6 발주 절차"처럼 절 번호를 두 번 보임(ref + 번호를 품은 제목).

## 3-7. 회귀 1회(빌드 없이, 기준 복원 뒤) — 검증됨
- 기준 복원 먼저: 실행 중 처리 건 0 → 흐름 `POST /api/flows/deploy-reset`(c3_cooling · c3_pm · c3_spare 경보 경로에서 내림, 운영 = 기준 흐름 anomaly_response 2.2, `flows-deploy-reset-api.json`) → neo4j 원래 볼륨(전체판 FailureMode 7, `neo4j-back3.log`) → 설비 `POST :8000/api/reset`. 워커 1개 그대로.
  - **내 실수 하나**: 처음에 `c3_flows.py deploy-reset`을 불렀는데 이 스크립트에는 그런 명령이 없어 `deploy`처럼 동작해 세 흐름 판 5를 한 번 더 등록 · 배포했다(내용은 판 4와 같음, `flows-deploy-reset.log`). 곧바로 위 API로 되돌렸다. 스크립트가 모르는 명령을 배포로 처리하는 것은 도구 결함(`scripts/c3_flows.py:167-176` — check/export 말고는 모두 배포).
- 11:34:13 `scenario_instance_test.py --worker` → **ALL PASS 40/40**, exit 0, 11:40:13 끝(6분, `reg-cooler.log`). process StartedAt 02:09:19Z · RestartCount 0(전후 같음, `reg-before.txt`).
- 참고: 회귀의 `/api/reset`(업무 실행 초기화)이 라이브 완주의 업무 행(WO · PR · GR)을 보관 표로 옮긴다(C3 7.3과 같음). 처리 건 기록은 남는다.

## 3-8. 정리 — 검증됨
- 워커 `pkill -f worker.main` → 프로세스 0, 8097/8098 LISTEN 0.
- 실행 중 처리 건 0. 잔재 검사 `cleanup_residue_instances.py --before 2026-10-10T02:41Z`(dry run) → 0건(숨길 것 없음, 백업 `residue-final/backup.json`). 앞 2차의 한도 잔재 1건은 이미 숨김(8-2).
- 설비 초기화 200. B · C 표시 켜짐(수업 시작 상태). 흐름 운영 = 기준 흐름(c3 흐름 0). neo4j 원래 볼륨(전체판). 구조판 볼륨 `hyd-iot-edu_neo4j-data-c3`는 남김(PR-07 새 판 6d921c06 적재 상태).
- 고친 파일(커밋 안 함): `it/portal/www/caseRecord.js` · `approvalCard.js` · `enterprise.js` · `plainWords.js` · `instances.js` · `index.html`(캐시 `20261010-lf1`), 이 문서.
