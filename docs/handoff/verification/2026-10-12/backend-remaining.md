# 2026-10-12 backend remaining verification

작성 범위: Astra backend writer. 제품 코드와 단위·실제 PostgreSQL 계약 검사이며, 외부 LLM 성공 또는 전체 실스택 완료를 뜻하지 않는다. NOW/HANDOFF와 라이브 조작은 메인 담당이다.

## 수정과 확인

- **F1 MCP 노출**: Claude bridge가 이전 작업의 `.mcp.json` 서버를 보존하던 것을 이번 작업의 정확한 서버 집합으로 재작성한다. `--mcp-config`와 `--strict-mcp-config`, `ENABLE_CLAUDEAI_MCP_SERVERS=false`를 매 실행에 적용한다. 구독 로그인용 CLAUDE_CONFIG_DIR는 이전처럼 이동하지 않는다. allowedTools는 허용 목록이지 도구 발견 격리 수단이 아니므로 strict 옵션을 별도로 적용한다. 참고: 실제 `refs/ontology-studio/backend/src/modules/agent_session/cliagents_backend.py` 203–224의 strict MCP 실행 방식, [Claude CLI reference](https://code.claude.com/docs/en/cli-reference), [environment variables](https://code.claude.com/docs/en/env-vars). 실제 호스트 LLM 도구목록 확인은 메인 증거와 구분한다.
- **F2/U9 흐름 삭제와 투영**: DELETE `/api/flows/{id}?by=...`는 학생 흐름 하나의 초안·판본을 제거한다. 기본 흐름403, 없음404, 진행중409. 완료 처리 건은 숨김으로 변경하면서 durable projection outbox를 갱신한다. graph 장애 시 source 삭제를 성공처럼 graph 성공으로 표시하지 않고 `projection_pending`을 돌려준다. tombstone은 인스턴스와 작업을 삭제하고, 원천 판본이 없고 사용 중인 인스턴스가 없는 실행 판본·FlowNode만 정리한다. revision fence는 보존한다. `cleanup_removed_definitions`는 매 reconciliation에서 source 없는 ProcessVersion을 다시 찾아 기존 숨김 인스턴스·큐가 없던 잔재·인스턴스 없는 판본도 복구한다. 의미 온톨로지 Process/FlowNode는 대상이 아니다. 등록된 모든 불변판본은 후보에서 제외한다(`list_definitions.prod_version`은 SQL의 `version AS prod_version`으로 운영 포인터가 아님).
- **U9/K4 단계 닫기**: 기존 close API에 실제 pinned definition의 serviceTask/PENDING을 추가했다. 살아 있는 서비스 작업, 사람 작업, 진행 중 Incident는 거절한다. 사유·원 실패 로그·시도 기록을 보존하고 CANCELLED/closed-by-human으로 닫으며 업무 성공으로 바꾸지 않는다. close 전체에 기존 instance transition lock/transaction을 적용했다. 실제 PG에서 3회 실패→PENDING→사람 닫기 확인. 에이전트 자율보류의 LLM 라이브 재현은 메인 담당이다.
- **F5 미제출 DEC 404**: 모든 판단 시도는 EVAL로 시작하고 process 제출 성공 후 registry identity를 DEC로 전환한다. guardrail 거절, 후보 없음, 제출 연결 실패는 EVAL로 남는다. registry에는 같은 시도의 옛 별칭을 남기지 않는다. 실제 제출 카드 payload id와 반환 id 일치는 기존 시험 그대로 통과한다.
- **F6 비설비 동의 재확인**: 물리 명령을 포함하는 카드에만 plant forecast의 입력/모델/시간 경과 동의 검사를 적용한다. 구매 요청 등 업무 거래는 설비 조치를 허가하지 않는다는 `hydcommon.forecast.predict` 계약과 맞춘다. 업무 카드 내용·공급사·정책·순위·필수 사실 재평가는 그대로 적용한다. 업무 요청에서 카드값이 그대로인데 예측 입력만 달라진 경우 허용, 공급사 변경은 거절, 설비 명령은 입력 변경 시 거절하는 검증을 추가했다. 순위/규정에 실제 영향이 생긴 forecast 값은 여전히 새 검토 대상이다.
- **F8 저장결과 경계**: arbitrary 부모 폴더명이 tool-results인 것만으로 파일을 읽지 않는다. 신뢰하는 실행 컨텍스트의 config home/project/workdir/session에서 허용 디렉터리를 계산하며 컨텍스트가 없으면 읽지 않는다. 다른 작업·세션·위장 tool-results와 심볼릭링크 탈출은 거절한다. 원문 저장 실패는 기존 UI 원문 미보존 안내로 남는다. 실제 CLI 저장 디렉터리 구조는 로컬 폴더명만 대조했고 사용자 파일 본문은 읽지 않았다.
- **F9 clean dev**: 개발 환경에서 service requirements 두 개를 단순 합치던 계약을 수정했다. fastmcp가 요구하는 pydantic과 process 이미지의 오래된 pin은 같은 venv에서 충돌한다. dev 환경은 검증한 FastAPI/Pydantic/MCP/Psycopg 조합을 명시하고 fastmcp, 고정 SHA cliagents, openpyxl, PyYAML, pytest-xdist 등을 포함한다. 각 Docker service의 독립 requirements는 바꾸지 않았다. 새 Python3.14 venv에 requirements-dev만 설치, pip check 정상, 전체 2211개 수집 성공(이후 새 검증이 추가됨). 메인도 별도 clean venv에서 독립 재현했다. cliagents SHA 변경·site-packages 패치 없음.
- **U14 업무 규칙**: options.work_rules와 agent card.work_rules/work_rules_detail이 work_rules.py 정본을 사용한다. API 모델에 빠졌던 work_rules 저장을 연결했다. 필드 누락 시 기존값 유지, null은 공통 규칙만, 모르는 키는 저장 거절. DB에 남은 사라진 키는 오류와 원 키를 표시하고 다른 업무로 대체하지 않는다. 기존 constitution 바이트는 변경하지 않았다.
- **U15 한국어 설명**: Claude의 매 실행 system prompt에 한국어 진행 설명 지시를 추가하고 사람 답변 재개·형식 수정 요청에도 유지한다. private reasoning 언어나 모델의 실제 준수를 보증하는 변경은 아니다. 기존 CLAUDE.md 규칙 원문은 그대로다.
- **추가 PG 실제 결함**: JSONB는 extract 객체 키 순서를 재정렬하므로 MCP outputData 배열을 `[receipt, *extract.keys()]`와 순서 비교하던 validator가 저장 후 배포를 거절했다. 주결과 첫 칸, 정확한 필드 집합, 중복 금지는 유지하고 추출 객체의 무의미한 순서만 제거했다. 실제 PG 실패 추적 검사에서 발견·재현했고 수정 후 배포와 세 번의 실패 기록·닫기가 통과했다.

## 실제 검증

- `tests/test_backend_pg_contracts.py`: 독립 새 DB 55322, 테스트마다 임시 tenant를 만든 뒤 그 tenant만 정리. 3 passed. 업무규칙 insert/update/omit/clear, vault 값 회전·tenant 경계·metadata 비노출, 실패 시도 3회 event 유지, SQLite audit 영속, unknown events cursor404, asset 필터, 서비스 PENDING 닫기. 실행 환경 `HYD_BACKEND_PG_DSN`.
- 기존 B1/B6 PostgreSQL 2시험: 2 passed. B1 fixture에 메모리 fixture와 같은 연결검사 도장을 추가하고 변경한 tenant MCP를 finalizer에서 원복한다. 기존 기대값은 그대로다. B6 duplicate는 앞선 실패가 남긴 학생 스킬 영향이었으며 정상 cleanup 후 재현되지 않았다.
- `tests/test_backend_remaining.py` 신규 계약 및 worker/trace/close/MCP extract/cards/forecast/projection/import 관련 묶음: **204 passed, 2 skipped**. 로그 `.evidence/overnight-20261012/backend-related.log`(repo root 기준). skip은 Windows symlink 권한과 기존 선택 실행 조건이다.
- F6 두 회귀와 F14 실제 평가 합산 검증 + PG3: 6 passed.
- 실제 Neo4j 삭제·고아 복구는 `tests/test_flow_projection_cleanup.py`, `HYD_CLEANUP_NEO4J_URI`/`HYD_CLEANUP_NEO4J_PASSWORD`로 독립 그래프에서 실행한다. 메인이 독립 Neo4j 7787에서 **3 passed (12.27초)** 확인했다. 증거는 `.evidence/overnight-20261012/flow-cleanup-neo4j.log`/XML이다. 라이브 그래프 전체 삭제를 하지 않고 테스트 tenant만 정리한다.

## 기존 시험 변경 이유

- test_worker의 env 없음/이전 MCP서버 merge 유지 기대는 발견된 노출 결함 자체였다. strict 인자·개인 도구 disable env·빈 선택 시 이전서버 제거를 명시 검증하도록 강화했다.
- test_a161_trace_gaps 성공 fixture만 실제 호출의 config/project/session/tool-results 위치로 옮겼다. 원문 hash·본문·보존·API 권한 기대값은 전부 그대로다.
- B1 PG 준비에 정상 연결검사 도장을 추가한 것은 이미 적용된 생산 게이트를 통과할 유효 fixture를 구성한 것이며, 거절 기대를 지우거나 서비스 검사를 느슨하게 하지 않았다.

## F11/F14 근거와 남는 범위

F11 보고서의 2026-10-09 당시 A정밀 추천을 현재 남은 문제로 쓰던 문장을 당시 기록으로 명시하고, 2026-10-10 live-final 3-5의 B-OEM 추천 2.82/A정밀 1.32/비AVL 제외로 연결했다.

F14 `tests/fixtures/a_cards_before.json`은 실제 엔진 응답이 아니라 `tests/test_live_leftovers_cards.py`의 수동 A 카드 데이터를 옛 renderer로 그린 화면 회귀 고정본이다. card(score=3.38, parts=P())처럼 총점과 성분을 별도로 상수 입력해서 0.52/0.02 차이가 생겼다. production `ranking.score`는 반올림한 scoreParts 합으로 score를 산출한다. golden은 보존했고 실제 cards.evaluate의 정상/감점/제외/정지 조건에서 공개 성분 합과 총점 일치를 검증했다. 고정본을 계산 교육자료로 쓰지 말아야 한다.

F3/F4/F7 live/F10 및 LLM 완주는 메인 담당. F12의 기동 지연은 이번 메인 새 kg-seed 실측 60초와 과거16분 주장을 구분한다. F13은 최신 사용자가 밤새 전체 처리를 명시하여 학생 동선 검증은 다시 유효하며 메인이 수행한다. 제품 참조는 위 ontology-studio의 실제 CLI 격리 구현과 ProcessGPT 모노레포 README의 deterministic/LLM 혼합 실행·단계별 감사·MCP 격리 원칙 및 .gitmodules의 completion/cli-agent 분리를 확인했다. 이 clone의 미초기화 submodule 구현을 직접 읽었다고 주장하지 않는다. JSONB 순서 문제나 HYD pending/삭제 계약을 원본 제품의 기능이라고 주장하지 않는다.


후속 PG 공유환경 결함: `test_agent_trials_api`의 PG 시험도 FakeWorld MCP stub을 `tenants.hyd.mcp`에 남겼다. 원래 값을 finalizer로 복구하도록 수정했으며, 이미 오염된 버릴 DB 55322의 public.hyd MCP 한 칸만 seed.sql JSON 정본으로 복구했다(5서버; stu_s00 미변경). 서비스 gate나 기대값은 바꾸지 않았다. 이 원인 때문에 초기 성공한 B1/B6 두 시험만으로 다른 PG 시험 뒤의 반복 실행까지 입증할 수 없었음을 구분한다.

후속 PG4 serial 검증: B1 → BPMN import → Trial → B6 순으로 **4 passed (37.77초)**. `.evidence/overnight-20261012/backend-pg-four.log`. Trial stub 원복을 포함하므로 앞선 두 시험 단독 성공보다 넓은 공유환경 재현을 확인했다.


## F15 Codex 긴 지시 전달 (추가 실제 발견)

메인 live에서 Codex가 작업 본문 대신 Claude Read 도구 전용 `context/prompt.md` 포인터만 받는 결함을 발견했다. `runner._deliver_prompt`는 Codex 최초·재개·교정에 전체 본문을 유지하고, `codex_provider.stream_with_prompt_stdin`이 프로세스 경계에서 UTF-8 임시 입력파일을 stdin으로 연결한다. CLI 인자는 `-` 하나이며 임계치 상향·shell 권한 확대·공용 config 변경이 없다. seekable 파일은 pipe write 정체 없이 EOF를 제공하고 완료·시작실패·취소 시 닫힌다. cliagents parser와 기존 controlled_stream의 프로세스 트리/취소/오류 수집을 그대로 사용한다. MCP 선택/required/read-only 필터 인자도 유지한다.

설치 CLI 0.162.0-alpha.17.2에서 기존 WorkerCodexProvider의 exec 옵션 → resume → session → `-` 배열을 실제 `--help`로 검증해 exit0 및 stdin 지원 설명을 확인했다. 기존 resume 인자 배치 자체에는 추가 수정이 필요하지 않았다. 근거: 루트 `.evidence/overnight-20261012/codex-resume-help.json`.

실제 자식 프로세스로 32K를 넘는 한글·따옴표·CRLF 본문 SHA-256 일치, EOF 도착, 최초/재개, read-only 및 MCP 격리 옵션 보존, 시작 실패의 임시파일 정리를 검증했다. 실제 Runner 교정 왕복에서는 낮은 임계치에도 최초 업무/스키마/폼과 교정 폼이 원문으로 전달됨을 검증했다. 신규 fixture는 처음 빈 필수 guide_card로 거절되어 유효 추천 내용으로 준비를 바로잡았으며 제품 검사는 그대로다.

`python -m pytest tests/test_codex_prompt_transport.py tests/test_worker.py tests/test_manual_extraction.py tests/test_worker_process_control.py -q`: **86 passed (12.32초)**. 근거: 루트 `.evidence/overnight-20261012/codex-transport-tests.log`. 이는 stdin/워커 단위·실제 자식프로세스 검증이며, 실제 Codex 모델의 MCP 사용·업무 완주는 메인이 별도로 재시도한다. 이전 live의 UNKNOWN/교정 뒤 DONE을 성공으로 산정하지 않는다.


## F16 질문의 구조화된 MCP 근거와 폼별 교정

메인의 stdin 적용 live는 최종 18개 검사에 통과했다. 따라서 이번 변경을 완주 실패라고 기록하지 않는다. 다만 실제 일반 MCP `list_tables`·`describe_table`·`read_rows` 호출 뒤 객체형 evidence.query가 문자열 전용 validator에서 거절되고, 질문 교정에 manual proposal/anchor/page_reviews 안내를 보내는 결함은 남아 있었다.

`ask.validate_answer`는 query에 기존 질의 문자열 또는 실제 MCP 인자 JSON 객체를 받는다. `{}`는 무인자 호출을 명시하며 누락/null과 구별한다. 검증은 성공 완료된 실제 호출의 서버/도구 이름부터 일치시킨 다음 전체 인자 객체를 비교한다. 키순서만 무시하고 중첩 값·bool/number/string·배열순서·누락·추가를 구별한다. 문자열 SQL/Cypher/PromQL 사용은 유지하되 실제 sql/query/cypher/promql 인자의 **전체 문자열**과 대조한다(양끝 공백/마지막 세미콜론만 허용). 이전 substring·대소문자 통합·모든 문자열 leaf 검사는 다른 WHERE/리터럴/테이블 인자를 질의 증거로 잘못 인정하므로 제거했다. result 요약의 의미가 맞다는 자동 판정은 하지 않으며 verified는 실제 도구와 입력 호출을 찾았다는 뜻이다. 없는/실패한/아직 실행 중인 호출은 증거가 아니다.

`result_correction.py`는 ask/manual proposal/golden report/legacy meanings 폼별 오류 안내를 공급한다. bounded 3회 교정·같은 세션·이전 제출·오류 이력·최종 PENDING은 유지한다. 일반 필드 형태 검사도 해당 correctable 폼에서 교정 루프로 들어가게 했다. immutable ask_agent 1.0 정의를 덮지 않고 worker Context가 pinned form_contract를 전달해 최초 및 교정 prompt에 구조화인자 계약을 명시한다.

참고: ProcessGPT 모노레포 README의 단계별 감사·피드백 원칙을 확인했고 ontology-studio `backend/src/modules/agent_session/cliagents_backend.py`의 raw MCP namespace→표시이름과 tool-call 이벤트 보존 구현을 읽었다. HYD 근거 검증은 표시명만 쓰면 서버가 다른 동명 도구를 혼동하므로 서버/도구까지 보존한다. 이것을 upstream에 있는 동일 검증 구현이라고 주장하지 않는다.

## F17 추출의 실행기 하드코딩 제거

`manual_extraction.definition()`의 2.2 활동은 `agentConfig.cli=claude-code`로 고정되어 배포 CLI_AGENT=codex를 무시했다. 다른 기본 workflow/서비스의 provider 고정을 검색했고 같은 패턴은 이 한 곳이었다. 새 **2.3** 판본에서 활동 provider 고정만 제거했다. 신규 추출은 배포가 선택한 worker CLI를 따르며 오류 시 다른 provider로 자동 우회하지 않는다. 기존 2.2 immutable 정의·진행 건은 보존하므로 과거 pinned 작업을 소급 변경하지 않는다.

검증: `tests/test_ask_evidence_contract.py`에서 실제 Runner→MemoryRepo events→engine→ask view의 일반 MCP 증거 및 교정·재개·3회 PENDING, 엄격한 부정사례를 확인했다. `tests/test_extraction_provider.py`는 Codex/Claude 배포 각각 새2.3 선택 및 DONE, 기존2.2 원본 보존을 검증한다(모델 출력은 test double).

`python -m pytest tests/test_ask_evidence_contract.py tests/test_b5_ask.py tests/test_extraction_provider.py tests/test_manual_extraction.py tests/test_manual_golden.py tests/test_legacy_meaning.py tests/test_codex_prompt_transport.py tests/test_worker.py -q`: **179 passed, 2 warnings (6.89초)**. 루트 `.evidence/overnight-20261012/ask-provider-tests.log`. 기존 기대값/고정본은 변경하지 않았다. 실제 LLM 신규2.3 추출 및 변경 후 스택 검증은 메인 담당이며 여기서는 수행하지 않았다.


## F18 시작 실패의 핵심 진단과 live 검사 대기

메인 B-reject 실제 실행에서 required Neo4j MCP의 uvx 부재로 CLI exit1이 났다. 앞선 credential-store warning이 길어서 runner._fail의 앞600자 절단에 Fatal 꼬리가 사라지는 결함이 있었다. `worker/diagnostics.py`는 URL userinfo·Bearer·password/secret/token/API key 표식을 먼저 가리고, 제한된 길이에 시작 부분과 마지막 원인을 함께 보존한다. controlled_stream의 stderr 저장·경고와 runner의 오류 이벤트가 같은 함수를 쓴다. 이는 알려진 자격증명 표현을 가리는 처리이며 모든 임의 문자열의 비밀 여부를 판별한다고 주장하지 않는다.

`scripts/approval_stage_live.py::wait_approval`가 engine PENDING만 보며 IN_PROGRESS+draft_status FAILED를 900초 기다리던 부분을 수정했다. FAILED/CANCELLED는 즉시 미완 exit2이며 성공 조건이나 기대값은 변하지 않았다.

`tests/test_worker_failure_diagnostics.py`는 실제 Runner 저장 이벤트의 Fatal 꼬리/길이/자격증명 제거와 probe가 sleep 없이 exit2 하는 것을 검증한다. 기존 워커 프로세스 취소·Codex stdin 회귀 포함 **55 passed (2.62초)**, 루트 `.evidence/overnight-20261012/worker-diagnostics-tests.log`. root live 스택/데이터는 건드리지 않았다.


## F19 Codex 등록 스킬의 본문 전달

메인 B 실제 실행에서 Codex가 등록된 pm-schedule-planning 스킬 파일을 읽으려 했지만 read-only/approval-never 세션의 셸 정책에서 거절되어 보류했다. 거절된 셸을 다시 실행하거나 권한을 넓히지 않았다. 제품이 제공할 등록 업무 문맥을 파일 도구 없이 제공하도록 바꿨다.

Codex만 `agent.instructions(skills_inline=True)`가 경로를 출처 표시로 설명하고 필수 파일읽기 문구를 제거한다. 새 `worker/skill_context.py`는 이번 작업에 배정된 tenant_skills snapshot을 동일 provider renderer로 만들고, 실제 provision SKILL.md UTF-8 바이트 및 기존 skills_provided SHA-256과 모두 일치하는지 확인한다. 일치한 전체 본문·출처·해시를 stdin prompt에 넣는다. 최초 실행·형식교정·사람답변 재개에 모두 제공하고, 파일 바꿔치기/본문 불일치는 CLI 호출 전 거절한다. `_provided_skills`는 read_text newline 변환 대신 실제 UTF-8 바이트를 해시해 CRLF 원문도 정확히 기록한다.

skills_provided/task_started metadata에 `delivery=prompt`, `verified_registered_content=true`를 남기되 skill_used나 tool 호출을 지어내지 않는다. 등록본문을 보냈다는 것은 실제 모델이 스킬 절차를 준수했다는 성공 판정이 아니다. Claude 기존 파일/Skill 도구 계약은 그대로다. MCP·sandbox·approval 정책은 변경하지 않았다.

`tests/test_codex_skill_context.py`의 최초/교정/사람응답 재개, 등록 renderer↔prompt↔audit 해시 일치, 파일 변경 실패, CRLF 원문 보존과 기존 워커/스킬추적/Codex stdin 검사를 합쳐 **75 passed, 2 warnings (3.40초)**. 루트 `.evidence/overnight-20261012/codex-skill-context-tests.log`. 실제 모델 B 재시도는 메인 소유다.


## F4 실제 Neo4j + HTTP 수정/되돌리기 보호

신규 `tests/test_manual_revision_http_neo4j.py`는 기존 empty-graph guard fixture와 임시 SQLite 원문 저장소, 실제 FastAPI TestClient 및 **독립 bolt://127.0.0.1:7787**을 사용한다. 7687 운영 그래프는 접근하지 않았다. HTTP preview 업로드→검토 body→commit으로 등록한 뒤 실제 case_projection의 DecisionCase CHOSE를 기록하여 다음을 검증했다.

- 사용된 Skill을 제거하는 revision commit HTTP409에 정확한 노드·CHOSE 건수 안내. 첫 배치 rollback도 같은409.
- 살아남는 Skill의 revision 및 rollback HTTP200에서 동일 elementId와 CHOSE 보존, 원래 Step 본문 복구. 이전 배치를 먼저 되돌리려는 요청은409.
- 새 판본에서 추가한 Skill이 사용된 뒤 해당 revision 배치를 rollback하면409.
- 모든 거절 전후 전체 node/relationship elementId·properties, 문서 head/snapshot, batch 및 ingestion lock을 비교해 부분쓰기 없음. 실패에 성공 audit를 남기지 않음.

신규 snapshot 첫 구현은 Neo4j DateTime을 JSON으로 직렬화하려다 실패했다. 그래프 native 값 자체를 비교하도록 시험 지원코드만 고쳤으며 보호 assert를 삭제/완화하지 않았다. 제품 결함은 발견되지 않아 테스트만 추가했다.

실행: `HYD_MANUAL_NEO4J_URI=bolt://127.0.0.1:7787 HYD_MANUAL_NEO4J_PASSWORD=<독립시험암호> python -m pytest tests/test_manual_revision_http_neo4j.py tests/test_manual_revision_history.py -q --junitxml=.../manual-http-neo4j.xml` (PowerShell에서는 각 `$env:` 설정 후 실행). **16 passed (8.98초)** — 기존13 + 새HTTP3. 루트 `.evidence/overnight-20261012/manual-http-neo4j.log`와 XML. fixture가 시작 시 노드0을 확인하고 끝난 후 시험 그래프를 정리했다.

## F16 추가 실제 Codex 서버 별칭

실제 `student-complete/ask-final.json`에서 이벤트의 서버 `overnight-20261012-3721fe7d-table/read_rows`와 Codex가 증거에 쓴 `mcp__overnight_20261012_3721fe7d_table__read_rows`가 이름 변환만 달랐다. 전체 인자는 동일했지만 이전 엄격 비교가 거절했다. 서버 부분의 hyphen→underscore 광고명 변환만 결정적으로 허용하고 도구 이름과 전체 인자 대조는 유지했다. 같은 광고명+인자가 서로 다른 실제 서버에 동시에 해당하면 모호하므로 거절한다. 같은 실제 서버/도구 반복 호출은 허용한다. substring 대조로 돌아가지 않았다.

실제 trace의 서버명·read_rows 인자를 신규 회귀에 넣었고, 다른 tool/server/인자 및 alias충돌 부정사례와 함께 **37 passed (1.63초)**. 루트 `ask-alias-tests.log`. 원래 live trace를 현재 verdict로 오프라인 재검증한 `ask-alias-realtrace-replay.json`은 실제 성공3call에 evidence3 모두 verified=true다. 이는 재실행된 LLM 성공 주장이 아니라 보존된 실제 trace의 verifier 재검증이며, 재빌드 후 actual probe는 메인이 수행한다.


## F17 버전 검사 정합 및 Windows Codex 실행별 샌드박스

전체 회귀의 남은 c1 실패는 의도적으로 2.3으로 올린 추출 계약을 기존 시험이 여전히 2.2로 고정한 것이었다. `test_c1_knowledge`를 새2.3 및 활동provider 고정 없음으로 명시 갱신했으며 knowledge/catalog/인용/조건분리 검사는 유지했다. `test_extraction_provider`의 실제 등록2.2 snapshot 불변과 새2.3 Codex/Claude 선택 검사를 함께 통과시켜 판본보존을 생략하지 않았다.

메인의 `.evidence/overnight-20261012/sandbox-smoke/stdout.jsonl`에서 `--ignore-user-config --sandbox workspace-write -c windows.sandbox="elevated"` 조합이 실제 작업폴더 파일 생성·읽기에 성공한 것을 확인했다. 개인설정 차단으로 Windows backend 선택도 사라지는 호환 문제를 제품 adapter에서 보완했다. WorkerCodexProvider는 **win32 + WORKSPACE_WRITE에만** 실행별 `-c windows.sandbox="elevated"`를 넣는다. 기존 서명된 Windows bounded backend를 고르는 것이며 `--sandbox workspace-write`와 개인config차단·apps차단·명시MCP 구성은 유지한다. readonly/Linux/macOS에는 추가하지 않는다. 새 환경변수나 개인config 수정은 없고 backend가 없으면 실행실패로 남는다. yolo·danger-full-access 우회는 추가하지 않는다.

새 `tests/test_codex_windows_sandbox.py`는 운영체제3 × 권한2 × 최초/재개2 조합, 원래 request 불변·옵션순서·격리유지를 검사한다. 기존 c1/추출판본/실제stdin/스킬본문/worker 회귀 포함 **104 passed (3.84초)**: 루트 `windows-sandbox-adapter-tests.log`. 실제 설치CLI에 adapter가 생성한 workspace-write resume 명령 + --help를 전달해 exit0/빈stderr도 확인했다: `windows-sandbox-adapter-help.json`. 실제 모델 파일실행 smoke는 메인 증거이며, 이 adapter 적용 뒤 live 업무 재실행은 메인이 수행한다.

## F20 구매·재고 업무의 원문 절차 범위 (수정·검증 진행)

실제 Sol 6.1 / 추출2.3 PR-07 결과가 procedures=[]·warnings8로 끝났다. 원문은 SOP-PUR-11/12/13 각 5단계를 명시한다. 원인은 manual_extraction.INSTRUCTION의 정비 한정 문장과 "운전·점검·정비·고장 조치 장만 / 애매하면 제외" 범위다. 같은 지시의 work_order(작업지시·발주)·PR_CREATE 지원과 모순되어, 모델이 구매/발주를 범위 밖으로 판단한 경고를 남겼다. 업무범위 추가 질문이 필요한 결함이 아니라 이미 확정된 A/B/C 지원 계약을 빠뜨린 추출 지시 결함이다. 실제 task.json의 skills=[]이므로 배정 스킬의 범위 지시가 원인은 아니다. worker prompt/context/skill_context와 폼별 교정 지시도 읽었으며 추가 정비 한정은 없었다.

새2.4에서 원문에 명시된 운전·점검·정비·고장 조치와 구매·발주·입고·재고 관리 업무의 실행 절차를 포함한다. 문서 제목이나 장 이름이 정비가 아니라는 이유만으로 제외하지 않는다. 설치·배선·시운전·반입/양중 제외, 원문 조건·수치·순서·승인 보존, 임의 단계 금지, 별도 사람 검토, 추출 상한·페이지/인용/형식 검사는 유지한다. 수정 전2.3 정의 및 git의 기존2.2 정의를 고정 시험 자료로 캡처하고, 등록된 두 판본과 진행2.3 건을 바꾸지 않는 회귀 검증을 추가한다. 단위 시험 및 실제 재추출 결과는 아래에 이어 기록한다. 라이브 스택/compose/추출은 root만 관리한다.

2.3 고정 자료는 root가 실제 API에서 읽은 `manual-definition-2.3.json`과 객체 전체가 일치했다. 2.2는 이 Windows DB에 미등록(실제 API404)이므로 git 원본 정의로 캡처했다. `test_extraction_provider`는 현재2.4를 복사해 옛판으로 이름 붙이던 대역을 두 역사 snapshot 및 고정 SHA-256 검사로 교체한다. 두 판본 변경 거절, 기존2.3 진행 작업의 query/pinned Context 불변 및 구/신 결과 읽기를 검증한다. 첫 실행 **78 passed/1 failed**는 신규 시험이 worker 1회 poll에 두 작업을 요청한 잘못된 가정이었다(`test_extraction_provider.py:81`). worker는 1회에 한 작업을 claim하므로 두 번 poll하여 두 판본을 모두 완료하도록 시험만 수정했다. 기존 상한·보호 assert를 완화하지 않았다.

수정 후 `tests/test_extraction_scope.py tests/test_extraction_provider.py tests/test_c1_knowledge.py tests/test_manual_extraction.py`: **79 passed (5.35초)**. 루트 `.evidence/overnight-20261012/extraction-24-tests.log/xml`. 신규 scope 시험은 실제 PR-07 원문의 PUR-11/12/13 각5단계와 300만 원·AVL 금지 조건 및 승인 문장을 pinned input/완료 제안에서 확인하고, 검토자 기록 없이는 적재 검토를 거절한다. CLI 출력은 명시적 test double이며 실제 모델 추출 성공을 의미하지 않는다. 제품 소스가 안정됐음을 root에 알렸고 실제2.4 재추출은 root가 수행한다. 다음은 기존 worker·구간추출·원문 인용·사람 검토 계약을 함께 검증한다.

참고 설계는 ProcessGPT 모노레포 BX의 existing_context/원문 evidence/HITL와 ontology-studio의 target_schema·문서별 인덱싱·batch_ingest 흐름(저장소 기존 대조 기록 `2026-10-09/c1-knowledge.md` 5절)이다. HYD의 현재 서비스·버전 고정 입력 → 에이전트 제안 → 별도 사람 검토 → 적재 구조를 유지했다. 이번 업무 범위는 HYD의 확정 A/B/C 계약에 맞춘 변경이며 upstream에 같은 정비/구매 규칙이 있다는 주장은 하지 않는다.

기존 worker·Codex stdin/등록 스킬·구간추출·원문 저장·인용·사람 검토·골든/의미 폼까지 확대 검증 **247 passed, 2 warnings (11.53초)**. 루트 `extraction-24-regression.log/xml`; 경고는 기존 FastAPI on_event deprecation이다. 별도 메모리 변이 검증은 정확한 옛2.3 instruction을 새 계약에 넣었을 때 신규 scope 검사가 실패하는 것을 확인했다(`extraction-24-scope-mutation.json`); 제품 파일·라이브는 변경하지 않았다. 최초 변이 스크립트는 PowerShell stdin의 한글 문자열 교체가 적용되지 않아 변이 발생 assert가 실패했고, 옛 정의 파일을 UTF-8로 읽는 방식으로 수정했다. 첫 단위/변이 실패 요약은 `extraction-24-first-failures.json`에 보존했다.

## F21 지식 지도에 노출된 내부 투영·적재 기록 (수정·검증 진행)

root의 실제 API 조회에서 ExecutionProjection420·CaseProjection428·KnowledgeEdit50·ManualIngestionDocument27·ManualIngestionBatch31개가 지식 지도에 포함되어 높이가 약33000px가 됐다. Process 이름 번역 문제로 판정하지 않는다. `t0_graph_nodes/edges`는 이미 ProcessVersion/ProcessInstance/WorkItem/IngestionControl/IngestionBatch 및 버전 소유 FlowNode를 제외하며, 주석도 지도는 업무 지식·사례이고 실행 버전/작업은 인스턴스 화면에서 조회한다고 정한다. schema.json의 위 다섯 클래스는 모두 standard="내부 기록", 설명은 잠금·멱등 영수증·적재 판본 머리다. 새 내부 메타데이터 클래스 추가 시 지도 조회의 제외 목록을 갱신하지 않은 결함이다.

노드와 관계 양끝 조회에서 다섯 내부 클래스도 동일하게 제외한다. Incident/DecisionCase/ManualSection/KnowledgeSource와 학생 추가 클래스·이름 공간 규칙은 유지한다. 스키마·DB 자료·화면 renderer는 수정하지 않는다. schema의 내부 기록 클래스가 모든 조회 끝점 제외 목록에 포함되는 회귀, API 응답 계약과 독립 bolt://127.0.0.1:7787 실제 Cypher/API 검증을 추가한다. 독립 DB도 시작 빈 그래프를 확인하고 본 시험 표식으로 만든 노드만 정리한다. 운영7687·compose는 root만 관리한다.

첫 실행 `tests/test_knowledge_map_internal_records.py tests/test_capstone_g4_namespace.py`: **16 passed, 2 warnings (6.78초)**, 루트 `knowledge-map-internal-tests.log/xml`. 독립7787의 실제 Neo4j driver→KnowledgeGraph 실제 t0 템플릿→`/api/ontology/graph` TestClient를 사용했다. 내부10종을 수업 기준/학생ns 및 ManualSection과 복수 라벨로 만들고, 내부→업무/업무→내부 관계 둘 다 제외함을 확인한다. 업무 사례·원문/판단 근거·학생 Meeting/StudentNote 및 학생→기준 다리 관계는 남고, 다른 학생/설비·버전 소유 FlowNode는 제외된다. fixture의 시작 빈 그래프 guard와 종료 자기 UUID 표식 노드 정리가 통과했다. 스키마에 내부 클래스가 추가되면 제외 목록 계약이 실패하므로 같은 누락을 다시 조용히 만들 수 없다. 제품 템플릿이 안정됐음을 root에 알렸다.

추가로 다섯 신규 제외만 메모리에서 제거한 옛 query를 같은 실제 fixture에 실행해 노드와 관계 양끝에서 내부 기록 누출이 재현되는지 확인한다. 이 변이는 제품 파일·운영 그래프를 바꾸지 않는다. ProcessGPT/ontology-studio의 지식 모델·문서 근거와 실행 인스턴스 구분은 기존 참고 대조(`c1-knowledge.md` 5절, `REPO_GAP.md`)에 따른다. 내부 잠금/영수증 라벨 및 정확한 제외 목록은 HYD 구현의 책임이며 참고 서비스에 동일 라벨이 있다는 주장은 하지 않는다.

옛 query 누출을 실제 DB에서 재현한 후 새 query가 내부 노드·양방향 관계를 모두 제외하는 부정/정상 검증까지 포함해 **45 passed, 3 skipped, 4 warnings (5.52초)**. 루트 `knowledge-map-internal-regression.log/xml`. 건너뜀3개는 별도 HYD_CLEANUP_NEO4J_URI 미설정의 기존 flow cleanup 시험이며 새 지도 실제7787 시험 두 건은 통과했다. 경고는 기존 FastAPI on_event deprecation이다. 제품 diff whitespace 검사도 통과했다. 운영 API/화면 재조회는 root의 안전한 배포 시점에 수행하며 이 단위/독립 DB 결과로 최종 화면 완료를 선언하지 않는다. KnowledgeGraph.template은 최초 조회 내용을 메모리에 cache하므로 운영 agent 재시작 후 조회가 필요하다.
