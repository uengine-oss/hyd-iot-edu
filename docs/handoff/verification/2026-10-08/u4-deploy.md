# U4 — 흐름 판본 배포 → 다음 경보부터 적용 (TODO 4)

작업 B 단위 U4, 2026-10-08. 화면 기준: process-gpt-vue3 `ProcessDefinitionVersionManager.vue`(판본 목록 · "반영 버전" 표시 · `prod_version` 조회 · 반영 요청), `utils/bpmnDiff.ts`(added/removed/modified + 항목별 before/after + 연결 from/to), `views/process-hierarchy/VersionComparison.vue`. 결재 흐름(review-board·my-inbox)은 범위 밖(메인 보충 지시: 사유 입력 + 배포 이력으로 충분).

## 만든 것

| 층 | 파일 | 내용 |
|---|---|---|
| DB | `it/supabase/migrations/20261008000044_definition_deployment.sql` | `proc_def_deployment`(tenant·정의·판본·이전 판본·action seed/deploy/rollback·actor·reason·created_at) + 백필(기존 `proc_def.prod_version`을 첫 `seed` 기록으로, 포인터 값은 그대로). `proc_def.prod_version`의 뜻이 "마지막 등록 판본"에서 **"운영(배포) 판본"**으로 바뀜 |
| 저장소 | `procsvc/procdb.py` | `upsert_proc_def`가 더 이상 `prod_version`을 건드리지 않음(새 행은 null). 추가: `deployed_version`, `record_deployment`(Pg: `for update` + 이력 insert 한 트랜잭션), `list_deployments`; `list_definitions`/`get_proc_def(version=)`에 `registered_at`(`"timeStamp"`) |
| 엔진 | `procsvc/instances.py` | `InstanceRuntime.__init__`: 기동 정의가 운영 판본과 다를 때만 `seed` 기록(같으면 아무것도 안 씀). `deployed_definition()`, `definition_status()`, `deploy_definition()`(사람·사유 필수, 없는 판본 LookupError, `validate_definition` 실패 ValueError, 이미 운영 중 ValueError, 감사 `DEFINITION_DEPLOYED`), `rollback_definition()`(이력 최신 행의 `previous_version`), `compare_definitions()`. **`alert_policy()`가 `self.defn` 대신 운영 판본을 읽음** → `on_alert_raise`가 배포 판본으로 연다 |
| 비교 | `procsvc/definition_diff.py`(신규) | 정의 상단(이름·설명·온톨로지·경보 정책)·단계·이벤트·분기점·연결·변수·역할·폼의 추가/삭제/변경을 한국어 한 줄 + 항목별 before→after(연결은 출발→도착 이름) |
| 기동 | `procsvc/instance_mode.py` | `_bootstrap_definition`: 파일(`PROCESS_DEFINITION_FILE`)은 운영 판본이 없을 때만 시드, 있으면 DB의 그 판본으로 기동. 라우트 `GET …/{id}/versions`, `GET …/{id}/compare`, `POST …/{id}/deploy`, `POST …/{id}/rollback`; `GET /api/process/definition`이 운영 판본 원문, `/api/process/mode`에 `deployed_version`, `/api/process/definitions` 행에 `deployed`·`deployed_version`·`registered_at` |
| 포털 | `it/portal/www/definitionDeploy.js`(신규), `index.html` 관리 탭 패널 "흐름 판본 배포 · 비교 · 되돌리기 — 다음 경보부터 적용" | 정의 선택 → 운영 판본 카드(경보 진입 여부) → 판본 카드(운영 중 / 배포 가능 / 검사 실패+사유 접기, 행동 1개 "이 판본 배포", 보조 "운영 판본과 비교") → 판본 비교(기준·대상 → 추가/삭제/변경 수 + 변경 목록, 항목 before→after 표) → 배포 이력 접기. 담당자·사유 필수, 되돌리기 버튼은 이전 판본이 있을 때만. `UI.card/chipText/fold/section/empty` 재사용, 영문 id는 정의 id·판본 문자열만 |
| 문서 | `docs/definition-authoring.md`(판본 배포 절), `docs/sessions/README.md:51`, `docs/sessions/16-….md:15`, `docs/curriculum-75h.md:99·140`(「PROCESS_DEFINITION_FILE 고정」 문구를 배포 절차로 정정), `scripts/probe_definition_versions.py`(복제 표에 `proc_def_deployment`) | |

## 시험

`tests/test_definition_deploy.py` 8개(MemoryRepo):
1. 시드 1회 + 등록은 포인터를 안 움직임(`prod_version` 2.2 유지, 판본 목록·deployable·rollback 없음)
2. **A 처리 건 열림 → B 배포 → 새 경보는 B(활동 이름 '원인 진단 (B)', version 2.3-test), A 처리 건은 A로 종결(ev:escalated, 모든 작업 version 2.2), B 처리 건도 B로 종결**
3. 검사 실패 판본(forms 없음) 배포 거부(ValueError '검사를 통과하지 못한'), 없는 판본 LookupError, 이미 운영 중·빈 사유 거부
4. 되돌리기: B → A, 다음 경보 A, 이력 [rollback, deploy, seed] + actor·reason, 다시 되돌리면 B
5. 재기동: `_bootstrap_definition`이 파일(2.2) 대신 DB 운영 판본(2.3-test)을 읽고 두 번째 seed를 남기지 않음
6. `definition_diff.compare`: 추가 5·삭제 1·변경 2, 문장·항목·flow
7. HTTP: versions(404)·compare(404)·deploy(422/404/409/200)·`/api/instances/start`(alert)가 B·rollback 두 번·이력 4
8. MemoryRepo 배포 기록의 미등록 판본 거부

전체 `.venv/bin/python -m pytest -q`: **1292 passed**(120 s). `node --check definitionDeploy.js` OK.

## 메인이 라이브로 확인할 것

1. 마이그레이션 000044(B4에서 000028 → 000044로 재번호) 적용(`cd it/supabase && npx -y supabase db reset` 또는 migration up) → `select id, prod_version from proc_def; select * from proc_def_deployment;` — anomaly_response 2.2 + seed 1행(백필).
2. process 재기동 → 로그 `instance mode: definition anomaly_response@2.2`, `GET /api/process/mode`의 `deployed_version`.
3. 포털 관리 → 흐름 판본 배포: `anomaly_response_v22.json`을 복사해 version `2.3`·`ev:select-timeout` timer `PT5M`으로 등록(위 패널) → 아래 패널에서 "운영 판본과 비교"(변경 2: 시간 제한·설명) → 담당자·사유 입력 → "이 판본 배포".
4. 쿨러 결함 주입 1건 → 처리 건 상세의 정의 판본이 2.3, 선택 시간초과가 20배속 벽시계 15 s. 배포 전에 열어 둔 처리 건은 2.2로 끝까지(선택 → ACK → WO → 종결).
5. 되돌리기 → 다음 경보 2.2. 이력 3행. `docker compose restart process` 뒤에도 `deployed_version` 유지(파일로 되돌아가지 않음).
6. `scripts/scenario_instance_test.py`(쿨러) 회귀 — `self.defn`을 쓰던 `find_by_alert`는 정의 id만 쓰므로 영향 없음. 원천 접수 재처리(`proc_inst_source`)는 접수 당시 판본 고정(기존 시험 test_source_delivery 통과).

## 알려진 한계·메모

- 배포 전 승인 단계 없음(요청→승인 1단계는 시간 남으면). 배포 즉시 다음 경보부터.
- 운영 판본 포인터는 정의 id 단위이고 경보 진입 정의 id는 기동 파일의 id(`anomaly_response`)로 고정 — 다른 id의 정의를 경보 진입으로 바꾸는 기능은 없다(`alertPolicy.unsupported`의 `alert_triage@1.0`은 정의 안에 핀).
- `proc_def.definition`은 여전히 "마지막 등록 원문"(제품의 작업본 의미)이고 `prod_version`만 운영 포인터다. 기존 시험 `test_definition_versions::test_versions_are_immutable…`이 이 의미를 고정한다.
- `InstanceRuntime` 생성자는 기동 정의를 운영 판본으로 기록한다(없거나 다를 때). 시험·프로브가 "새 런타임 = 새 판본으로 경보" 를 기대하는 기존 계약을 유지하기 위한 것이고, 서비스 기동(`instance_mode.build`)은 `_bootstrap_definition`이 DB 운영 판본을 먼저 읽으므로 파일이 포인터를 덮지 않는다.
- Pg 경로(`record_deployment`·백필 SQL)는 컨테이너 금지로 이 세션에서 실행하지 못했다 — 위 1·2가 그 검증이다.
