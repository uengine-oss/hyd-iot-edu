# 남은 꼬리 전수 조사 — 2026-10-08 (읽기 전용)

목적: 사용자 "IoT 교체 제외하고 남은 작업 없이 다 완료돼야 한다. 부분 완료 금지"에 맞춰 인계 문서에 흩어진 "남은 것·미검증·미결·대기·후속·보류·못 고친 것·나중에·(사용자 결정)·미실측·미확인"을 한 표로 모은다. 코드·문서·컨테이너는 바꾸지 않았다(이 파일만 작성).

분류: **A** 제작자가 지금 닫을 수 있음(유료·토큰·학생 대역 사유 포함) / **B** 사용자 몫(다른 사람의 로그인·결제·외부 전송·다른 기기처럼 제작자가 못 하는 것) / **D** 제외(DECISIONS 107 IoT·SCADA 교체, AI 층 굵직한 블록 후보, 다른 항목으로 이미 닫힘 — 닫은 항목 표기).
크기: S 30분 · M 반나절 · L 하루. "닫는 방법"은 제작자 제안이며 실행 결과가 아니다. 출처 줄 번호는 2026-10-08 현재 파일 기준.

## 읽은 범위

| 파일 | 읽은 범위 |
|---|---|
| `docs/handoff/HANDOFF.md`(1,128줄) | 1~1128 전부(나눠 읽음) |
| `GOAL.md`·`PROGRESS.md`·`UIUX.md`·`REBUILD.md` | 전문 |
| `QA.md` | 240~309 전문(10-07 절), 1~239는 제목만. **10-08 절은 없음**(검색 0건) |
| `UIUX_PLAN.md` | 1~35, 270~293 전문 + 키워드 줄 |
| `REPO_GAP.md` | 101~155(§3·§5·§6) 전문, 1~100은 제목만 |
| `MANUAL_INGESTION.md` | 키워드 줄(3·7·9·13·17·19·25·26·33·48·50·56·62·64·66·68·81) |
| `REFERENCE_ADOPTION.md` | 1~98 |
| `DECISIONS.md` | 100~107 전문, 1~99는 제목(+96·97 줄) |
| `docs/RUNBOOK.md`·`docs/sessions/README.md` | 전문 |
| `docs/curriculum-75h.md` | 1~28, 120~166(§4·§5·§7) |
| `docs/sessions/01~25` | "미검증·미확인·실패·배속·현재 시스템에 없음" 줄과 해당 증거 절 |
| `README.md` | 1~139 |
| `.evidence/a131/분석.md` | 전문 |
| `.evidence/a122/` | `console.json`·`layout.json`(요약), `clicks/`·`crops/` 목록 |
| `.evidence/a132/` | `facts.json`·`form-check.txt`·`console.json` |
| 추가로 읽은 것 | `TODO.md` 전문, `docs/src/arch_internal.py`의 불일치 메모 36줄(221~228·385~395·570~576·705~714), `verification/2026-10-08/teachable-candidates.md` 표 1·1차 추천, `docs/PROJECT_STATUS.md` 머리 |
| 못 읽음 | `AUDIT.md`, `USER_UTTERANCES.md`(10-08 검색만, 0건), `verification/2026-10-07/r13-*`·`r14-*` 조별 보고서 본문 |

확인을 위해 읽기만 한 코드: `it/portal/www/ui.js:216`(목록 페이지 나눔 존재), `instances.js:537`(폐기 요청 ID는 보내나 sessionStorage 없음), `layers.js:20,34`, `tests/test_guardrail.py`·`test_stability.py` 파일 끝(빈 줄 없음), `procsvc` DELETE 라우트(`main.py:1098` 하나뿐 — 스킬 삭제 API 없음), `compose.yaml:376`(`PROCESS_MEMDEBUG` 기본 0).

## 표

| 번호 | 항목 | 출처 | 종류 | 왜 남았나(원문 인용) | 닫는 방법 | 크기 | 분류 |
|---|---|---|---|---|---|---|---|
| 1 | DoD 4 UI 판정: UIUX.md 인수 조건 1~5를 화면별로 판정하고 "됐다" 상태로 닫기 | HANDOFF:3, :106, :283(A091), :297(A084); GOAL:16, :33; UIUX.md:40-47; PROGRESS:24(R12), :60 | UI | "DoD 4(UI)만 사용자 "됐다" 대기" · "사람이 눈으로 보는 검수는 캡처를 내가 보는 것으로 대체 — 사용자 직접 확인 필요" | 사용자가 기준(UIUX.md 1~6)을 줬으므로 제작자가 `scripts/ui_capture_all_tabs.py --full --crops`로 현재 배포를 1440·1024 캡처 → 조건 1~5 항목별 판정표(`.evidence/<A>/uiux-judge.md`) → 미달은 `ui.js`·`components.css` 수정 뒤 1회 재캡처. 사용자에게는 판정표와 캡처를 보고 | M | A |
| 2 | UIUX_PLAN §7 캡처 결함 F1~F10의 처리 결과 기록 없음 | UIUX_PLAN:278-291; HANDOFF:200(A122 기록에 F별 결과 없음) | UI | "캡처에서 찾은 결함 (코드 수정 때 같이 고칠 것)" — A122 기록에는 F1~F10별 처리 여부가 없음(F10 FUXA `optional`은 `layers.js:20`에서 반영 확인) | `.evidence/a122/crops` 캡처와 대조해 F1~F10 해결/잔존 표 작성, 잔존분 수정 | S | A |
| 3 | 화면에 데이터 원문 노출: 레거시 판단 `fm:…` 이름·annotation 없는 규칙 id·단계 로그 영문 | HANDOFF:200 | UI | "못 고친 것(데이터 원문): 레거시 판단의 `fm:…` 이름·annotation 없는 규칙 id·단계 로그 영문" | `ui.js`에 id→그래프 name 조회 표시, 단계 로그 코드→한글 사전(`UI.terms`) 추가, 내부 용어 0 재확인 | M | A |
| 4 | 1024px에서 흐름도(정의 SVG) 가로 스크롤 | HANDOFF:200; `.evidence/a122/layout.json` process-1024 overflow(svg right 1257) | UI | "1024에서 흐름도는 가로 스크롤" | `flow.js` viewBox·노드 간격을 폭에 맞춤(또는 1024에서 세로 배치), `layout.json` overflow 0 재확인 | S | A |
| 5 | 회차 화면 캡처 미검증: 03(EMQX·Grafana 화면·WebSocket 구독)·05(포털 강조)·06(층 칩)·18(포털 Execution 표) | sessions/03:28, 05:27, 06:24, 18:25; sessions/README:15,16,28,37 | UI | "화면 캡처는 이번에 만들지 않았고 화면이 읽는 API·Cypher로 대체했다" · "포털 층 칩 화면은 캡처 없이 진행해 **미검증**" | 4개 화면을 Playwright로 캡처해 `.evidence/sessions/<NN>/`에 추가, 각 회차 "증거" 절 갱신(읽기 전용 캡처) | M | A |
| 6 | 포털이 꺼진 선택 서비스(FUXA 1881 `/api/settings`, Redpanda Console 8085)에 프로브해 콘솔 `ERR_CONNECTION_REFUSED` | `.evidence/a122/console.json`(24화면 중 22), `.evidence/a132/console.json`; `layers.js:20,34`; HANDOFF:1038(10-03 관찰) | UI | 검사기가 "ignored"로 분류해 오류 0으로 셈 — "(이번 변경 무관, 미수정)" | 선택 서비스 프로브를 `no-cors` 1회·실패 시 조용히 "꺼짐" 표시(또는 프로필 꺼짐이면 생략), 콘솔 무시 목록 없이 0 확인 | S | A |
| 7 | 기업 거래 before/after와 계약 변경 범위의 포털 노출 | DECISIONS:503(97); PROGRESS:16(R04) | UI | "포털 거래 표시는 그대로이며 before/after 노출은 후속 후보" · "계약 전체 변경 범위의 포털 노출은 남음" | `enterprise.js` 거래 표에 접기 "변경 전·후"(transactions.before/after) 추가, 캡처 | S | A |
| 8 | 승인 폐기·효과 보상/확인 요청의 응답 유실 복구(요청 ID 보존) 없음 | HANDOFF:667(A045); `instances.js:537`(request_id 전송, sessionStorage 없음 — 직접 확인) | UI | "포털 취소 응답유실의 요청ID 보존도 이어서 검토한다" | `instanceRework.js`의 pending 저장·재확인 패턴을 `instances.js` 폐기와 `instanceEffects.js` 보상/확인에 적용, 브라우저에서 응답 버림 시험 1회 | S | A |
| 9 | 실시간 스트림: legacy 모드 `/api/events/stream` 409에서 재연결 안 됨(브라우저 실측 미확인) | docs/src/arch_internal.py:575 | UI | "브라우저 규격상 200이 아닌 응답은 재연결하지 않고 … 티커는 '끊김 · 재연결 중'에 머문다(브라우저 실측 미확인)" | `liveStream.js`가 409면 "실시간 꺼짐(legacy)" 표시, 아니면 백오프 재연결; 주석 정정 | S | A |
| 10 | 타임라인에 60초 넘는 공백을 "대기 구간"으로 표시(P01 채택 후보) | REFERENCE_ADOPTION:52(P01) | UI | "후보 추가: 60초 넘는 간격을 대기 구간으로 표시(timeline_service.py:301-310)" | 처리 건 기록 탭 타임라인에 간격 표시 추가, 또는 미채택 결정을 채택표에 기록 | S | A |
| 11 | 업무 DB 옛 고정값 열(due_in_h·alt_free_h·ship_in_h·night_in_h·last_clean_days·cleans_60d·days_ago) 미삭제 | HANDOFF:293(A086) | 코드 | "옛 열 DROP은 실행 도구가 "되돌릴 수 없는 로컬 파괴"로 거절해 우회하지 않고 덧붙이기로 바꿨다" | DECISIONS 103(삭제 위임)으로 RPC·seed·검사기 참조 0 확인 뒤 DROP 마이그레이션 추가·적용·`schema_migrations` 기록, 빈 DB 전체 적용 재확인 | S | A |
| 12 | `renew_task_lease`가 부모 인스턴스를 먼저 잠그지 않음(잠금 순서 규칙과 불일치) | arch_internal.py:708; DECISIONS 31(부모 먼저 잠금) | 코드 | "renew_task_lease는 부모를 잠그지 않고 todolist를 바로 UPDATE한다(부모 updated_at 트리거가 뒤따름). PgRepo도 _workitem_connection 없이 호출" | A021 잠금 순서 재현기로 갱신·엔진 전이 경합 시험 → 마이그레이션에서 부모 `for update` 선행(또는 교착 불가 근거 기록) | M | A |
| 13 | `store.py` incidents·book dict를 이벤트 루프와 스레드 풀이 잠금 없이 변경 | arch_internal.py:572; HANDOFF:893(A032 같은 계열 결함) | 코드 | "보호 대상은 SQLite 연결뿐이다. incidents·book dict 자체는 이벤트 루프와 스레드 풀이 잠금 없이 함께 바꾼다" | `test_store_concurrency`에 루프+스레드 동시 변경 반례 추가 → 변경 경로 잠금 | M | A |
| 14 | `PROCESS_MODE=instance`+`PROCESS_REPO=memory` 조합이 기동 단계에서 실패(코드상, 실행 미확인) | arch_internal.py:571 | 코드 | "MemoryRepo에는 _conn이 없다 … 시작 단계에서 실패한다(실행 미확인)" | 단위 시험으로 기동 재현 → MemoryRepo 지원 또는 명시 거부 메시지, docstring 정정 | S | A |
| 15 | `tests/test_entsim.py` 전체 실행 순서 의존 실패 원인 미조사 | HANDOFF:186, :192; .evidence/a131/분석.md:52-53, :81 | 코드 | "test_entsim 순서 플레이크 1건은 단독 통과, 미조사" · "원인 미조사" | `pytest -p no:randomly` 순서 이분 탐색으로 공유 상태(모듈 전역 data) 찾고 픽스처 격리, 전체 1회 통과 | M | A |
| 16 | enterprise-sim 멱등 충돌이 백엔드에 따라 400(memory)/409(supabase) | arch_internal.py:574 | 코드 | "백엔드에 따라 같은 충돌의 상태 코드가 다르다" | memory 백엔드도 409로 통일, 시험 | S | A |
| 17 | `engine.Definition.load`가 subProcess/callActivity를 파일 직접 로드에서 허용(실행 분기 0) | REFERENCE_ADOPTION:29(C03) | 코드 | "engine.py L87이 subProcess/callActivity를 허용하지만 실행 분기 0건 — … 파일 직접 로드에만 해당(기록)" | load에서도 등록기와 같은 미지원 유형 거부, 시험 1 | S | A |
| 18 | 시작 이벤트 직후 gateway의 새 제어 토큰·도달 근거 없는 과거 CANCELLED 작업 "명시 보류" | HANDOFF:337(A071); PROGRESS:23(R11 "시작gateway·과거도달근거") | 코드 | "시작 이벤트 직후 gateway의 새 제어 토큰·도달근거 없는 과거 CANCELLED작업은 명시보류" | `probe_rework_conditions.py`에 두 반례 추가 → 지원 구현 또는 거부 사유를 `docs/rework-conditions.md` 계약으로 고정 | M | A |
| 19 | 분기 조건 변수 검사가 "게이트웨이 앞 활동의 outputData"보다 약함 | REFERENCE_ADOPTION:61(D01) | 코드 | "조건 변수 검사가 '앞선 활동의 필드'보다 약함(그대로)" | `definition_registry`에서 조건 변수 생산 활동이 게이트웨이로 가는 경로 위에 있는지 검사, 시험 | S | A |
| 20 | 정의 변경 draft 판본 모양(is_draft·parent_version·requester/reviewer) 미채택 후보 | HANDOFF:271(A095 후보 3); REFERENCE_ADOPTION:55(P04) | 코드 | "후보 3건(… 정의 변경 draft 판본 모양)은 기록만" | `proc_def_version` draft 열·등록 API draft→승인 흐름 구현, 또는 미채택 결정을 DECISIONS에 기록 | M | A |
| 21 | 매뉴얼 구간 경계에서 잘린 SOP 이어붙이기 없음(경고만) | HANDOFF:269(A096 후속 후보 T02); REFERENCE_ADOPTION:45 | 코드 | "남은 경계: 구간 경계에서 잘린 SOP 이어붙이기 없음(경고로만)" | `manual_segments.merge`에 경계 경고가 붙은 같은 절/SOP의 결정적 결합 규칙 + 합성 경계 문서 시험 | M | A |
| 22 | 스캔 PDF OCR(빈 페이지만 OCR로 채우는 분기) 없음 | HANDOFF:275(A094), :311(A077); PROGRESS:14(R02); REFERENCE_ADOPTION:48(T05); QA:273(B8 OCR); MANUAL_INGESTION:26, :81 | 코드 | "미검증: 스캔 PDF(OCR)" · "스캔 PDF OCR은 유료라 보류" | `manual_sources.extract`의 OCR_REQUIRED 페이지만 OCR(로컬 엔진 또는 GPU 서버 VLM)로 채우는 분기·추출기 태그, 스캔 PDF 1건 실측(유료 사유는 A) | L | A |
| 23 | B4 범위 고정: 추출 정의에 "SOP로 삼을 장"(설치·배선 6~9장 포함 여부) 명시 | HANDOFF:206; PROGRESS:65; MANUAL_INGESTION:50; REPO_GAP:150 | 코드 | "범위 고정을 원하면 정의에 "SOP로 삼을 장"을 명시(사용자 결정)" | 업계 기준(정비 SOP=운전·점검·정비 절차, 설치·배선은 범위 밖)으로 제작자가 정해 추출 정의 새 판에 범위 한 줄, DECISIONS 기록(사용자 10-07 "업계 답 있는 설계는 스스로") | S | A |
| 24 | 참조 중인 SOP를 별도 판본으로 병행 유지하는 이행 없음 | MANUAL_INGESTION:64 | 코드 | "참조 중인 SOP를 별도 판본으로 병행 유지하는 제품 수준 이행은 후속" | 개정 시 과거 판단이 참조하는 SOP 판본 보존 계약 시험 1개 → 구현 또는 범위 결정 기록 | M | A |
| 25 | 매뉴얼 적재와 감사 Kafka의 원자적 outbox, 전체 graph outbox | MANUAL_INGESTION:66; PROGRESS:23(R11 "전체graph outbox") | 코드 | "감사 Kafka와의 원자적 outbox는 범위 밖이다" · "전체graph outbox … 남음" | 적재 영수증→감사 발행 outbox 추가, 또는 범위 밖 근거를 DECISIONS에 기록(A043·A044 outbox와 구분) | M | A |
| 26 | 지식 재투영이 테넌트 원천 전체를 20건씩 다시 투영(변경 영향 선별 없음) | HANDOFF:611(A048) | 코드 | "변경 영향만 선별하는 최적화는 후속이다" | `knowledge_projection`에 변경 노드→영향 원천 선별, 시험; 또는 현 규모 비용 측정 뒤 불필요 판정 기록 | M | A |
| 27 | 실행 단위 범용 tool registry·검증, tenant MCP 설정의 가변(mutable) 경계 | REBUILD:19, :20 | 코드 | "범용 registry/검증은 후속" · "기존1.0 legacy-live와 tenant MCP의 mutable 경계는 남아 있다" | tenants.mcp를 인스턴스 시작 시 판본 고정(또는 변경 이력)하고 미지원 tool 사전 거부 시험; 범위 판단 기록 | M | A |
| 28 | InputData 동의어 배열과 동의어 포함 검색(B8 중 동의어) | REPO_GAP:152(B8 "선택·미착수"); REFERENCE_ADOPTION:49(T06); HANDOFF:271(A095 "입력 동의어 검색") | 코드 | "B8 \| InputData 동의어·OCR·본문 검색 \| 선택 \| 미착수" | `schema.json` InputData.synonyms 선언·gen, dmn-mcp `inputs`·enterprise `describe_catalog` 검색에 동의어 매칭, 시험 | M | A |
| 29 | 업무 데이터(MES·ERP·CMMS·QMS) 허용 나이 계약 없음 | HANDOFF:295(A085) | 코드 | "업무 데이터의 허용 나이는 계약에 없어 승인 차단 기준은 만들지 않았다" | 원천별 최대 나이를 정책 데이터로 추가하거나, A086 anchor 비교로 충분하다는 판정을 DECISIONS에 기록 | S | A |
| 30 | 배율: REVIEW_POLICY v2의 1배속 완주 미검증, 13회차 원래 장면(쿨러+실제 워커) 미검증, 임의 배율 해상도 자동 설계 미구현 | HANDOFF:186(A129), :535(A055); sessions/13:27; sessions/README:23, :49 | 코드 | "미검증: 1배속 실제 완주" · "1배속·2배속 실행과 쿨러로 하는 원래 장면은 이번에 하지 않음 — 미검증" · "임의 배율 해상도 자동 설계는 미구현" | 20배속 기본(10-08)이므로 `forecasting` 경과 계산을 TIME_SCALE 1·20 단위 시험으로 확인, 13회차 장면은 팬 경보로 확정(쿨러는 20배속 80초 트립), 지원 배율을 DECISIONS에 기록 | S | A |
| 31 | 작업자 상시 지시의 SQL 규칙 4줄(A9)을 에이전트가 지키는지 미검증 | HANDOFF:218; REPO_GAP:142; PROGRESS:19(R07) | 측정 | "에이전트가 실제로 지키는지는 LLM 실행이 필요해 미검증" | 새 LLM 실행 없이 A115 이후 실행(reg-a130 rule 15/15·business 21/21·timeseries 18/18)의 도구 trace에서 4규칙(스키마 먼저·SELECT 1문장·주석/세미콜론 없음·고치기 ≤2) 판정 스크립트 | S | A |
| 32 | 워커 `_pause`가 `remember()` 반환값을 버려 알림 중복 가능(미실측) | REFERENCE_ADOPTION:39(A05) | 코드 | "`_pause`가 remember() 반환값을 버려 알림 중복 가능(runner 244, 미실측)" | 반환값 처리 + 중복 알림 시험 | S | A |
| 33 | `evaluate_cards`에 진단 출처 없는 원인 인수를 줄 때의 강제 미증명 | HANDOFF:557(A053) | 코드 | "직접 evaluate_cards 인수의 진단 출처 강제까지 증명하지 않는다" | dmn-mcp `evaluate_cards`가 diagnose 결과 근거 없는 cause를 표시/거부하는지 시험, 필요 시 구현 | S | A |
| 34 | 판단 코드에 남은 고정 경로(`gather_facts` sys:* API 분기·`ranking.FEATURES` 파생 특징·decide.py 출처별 엔드포인트) | HANDOFF:309(A078); arch_internal.py:387 | 코드 | "남는 코드 영역: `gather_facts`의 sys:* API 분기, `ranking.FEATURES` 파생 특징" | System 노드에 endpoint 속성을 두어 데이터화, 또는 코드 고정 이유를 DECISIONS에 기록 | M | A |
| 35 | DMZ·sink·MCP·compose 동작 불일치 메모 묶음: sink_batch_age_seconds 미기록(224), cmd-gateway 감사 checks 이름 불일치(226), connect-ingest `/healthz` 항상 200(227), 비객체 페이로드 예외(228, 미확인), enterprise-mcp 봉투 불일치·DB 오류 예외 그대로(390), agent·dmn-mcp 미사용 env(392), ENTERPRISE_READ_DSN extra_hosts 없음(395, 미확인), 워커 ALLOWED_TOOLS 기본값 compose 불일치(711) | arch_internal.py:224, :226-228, :390, :392, :395, :711 | 코드 | 각 줄 원문 예: "connect-ingest … ok 키를 넘기지 않아 Kafka·MQTT가 끊겨도 항상 200이다" · "paho 스레드가 이를 어떻게 처리하는지는 미확인" | 파일별 수정 + 단위 시험, 미확인 2건은 재현 시험(목록 페이로드 1건, extra_hosts 없는 이름 해석) | M | A |
| 36 | 독스트링·주석이 동작과 다른 나머지 메모(221·222·223·225·385·386·388·389·391·393·394·570·573·576·705·706·707·709·710·713·714) | arch_internal.py 해당 줄 | 문서 | 예: "dmn-mcp server.py:4 도구 목록은 8개지만 실제 등록은 13개" · "KnowledgeGraph.forecasts()는 어디서도 호출되지 않는다" | 각 파일의 docstring·주석 정정(동작 무변경), 죽은 코드(t3_forecasts 호출부)는 제거 또는 사용처 기록 | M | A |
| 37 | Measure의 leading/lagging 역할(kpiRole) 없음 | REFERENCE_ADOPTION:62(D02); PROGRESS:25; HANDOFF:251 | 코드 | "Measure leading/lagging 역할(kpiRole) 없음 → 전문가 결정 후보" | 업계 BSC 기준으로 제작자가 정해(사용자 "전문가 질문은 네가 조사해서 정해라", A098) `schema.json` 선언·지표 21개 값·gen·validate·감사 문항 1개 | M | A |
| 38 | 배포 파일 불변 조건 pytest(127.0.0.1 바인딩·메모리 상한·프로필·healthcheck) | REFERENCE_ADOPTION:32(C06); PROGRESS:25 | 코드 | "후보: 배포 파일 불변 조건을 pytest로 고정(HYD compose.yaml 검사 유무 미확인)" | `tests/test_compose_contract.py` 추가(깨뜨려 확인) | S | A |
| 39 | kg-seed 적재 뒤 되읽기 단언 | REFERENCE_ADOPTION:59(O04) | 코드 | "작은 후보: seed 뒤 되읽기 단언" | seed 끝에 노드·관계 수와 `ontology_v2.py validate` 단언 | S | A |
| 40 | `docs/src/arch_internal.py` 낡은 서술(712 check_auth — A129로 추가됨, 시간 배율 설명 "20배속 기본") 및 위 35·36 처리 뒤 메모 정리 | HANDOFF:108(§7), :186 | 문서 | "그 세션이 종료돼 전달 못 함 — docs/src를 다음에 만지는 사람이 고친다" | 712줄 등 해소된 메모 삭제·배율 서술 갱신 → `python docs/src/master_build.py` 재생성 확인(35·36 뒤) | S | A |
| 41 | HWPX/DOCX 매뉴얼 변환기(T03) 조건부 후보 | REFERENCE_ADOPTION:46 | 문서 | "HWPX/DOCX 매뉴얼이 오면 변환기를 manual_sources 분기로 붙일 조건부 후보(요구 0건이라 보류)" | 요구 0건 근거로 미채택 확정을 채택표·DECISIONS에 기록(또는 docx 분기 구현) | S | A |
| 42 | 참고 레포 미확정 연결 4건(agent-router 소스·mcp-proxy 소스·fcm-service 전달·PAL) | REFERENCE_ADOPTION:77-80 | 문서 | "소스 레포/커밋은 아직 미확정이다" · "필요 기능과 소유 레포가 확인될 때까지 미확정으로 유지한다" | 공개 레포 검색·이미지 라벨로 소스 확인 또는 "확인 불가(근거)"로 닫기 | S | A |
| 43 | C05 미열람 파일(kong.yml, init.sql DDL 본문) | REFERENCE_ADOPTION:31 | 문서 | "미열람: kong.yml, init.sql DDL 본문" | 고정 커밋에서 두 파일 열람해 채택표 갱신 | S | A |
| 44 | QA·USER_UTTERANCES에 10-08 절 없음(DECISIONS 106·107, 굵직한 블록 질문 등) | QA.md(10-08 검색 0건), USER_UTTERANCES.md(0건) | 문서 | 10-08 결정은 DECISIONS 106·107과 HANDOFF 포인터에만 있음 | 10-08 발화 원문·확정 답 절 추가(근거: `D:/work/작업보고/2026-10-08.md`, DECISIONS 106·107) | S | A |
| 45 | MANUAL_INGESTION 낡은 문장(실제 추출 미검증·에이전트 작업 미수행) | MANUAL_INGESTION:3, :13, :81 | 문서 | "실제 Codex 일반문서 추출은 아직 미검증이다" · "실제 에이전트 작업은 현재 수행하지 않았다" | A073·A077·A094·A119 실측으로 현행 절을 맨 위에, 옛 문장은 이력 표시 | S | A |
| 46 | REBUILD.md가 2026-10-04 상태 그대로 | REBUILD:3-22 | 문서 | "2026-10-04 현재 작업 설계" | 머리에 "이력 문서, 현재는 GOAL·HANDOFF" 표시 또는 미결 문장 현행화 | S | A |
| 47 | README·PROJECT_STATUS·TODO가 10-05~10-07 새벽 상태(README는 legacy `scenario_test.py`·"HITL 조치 카드" 메뉴·OpenAI 기본 LLM 안내) | README.md:3, :14, :24, :118; docs/PROJECT_STATUS.md:3(2026-10-06); TODO.md:26-44 | 문서 | README: "현재 … [프로젝트 현황](docs/PROJECT_STATUS.md)을 먼저 확인하세요(2026-10-05, A071)" · TODO: "다음 세션 순서: (1) A093 …" | README를 instance 모드·RUNBOOK·sessions·회귀 러너·현 메뉴명·GPU 내부 LLM으로 갱신, PROJECT_STATUS·TODO는 현행화 또는 이력 표시(`scenario_test.py`는 legacy 전용이라는 A115 기록 반영) | M | A |
| 48 | 커리큘럼 §4 "호스트 워커 회차(12~14)는 2배속을 권장"(10-08 규칙 위반)과 §5 표가 A128 결과 미반영 | curriculum:124, :135-140 | 문서 | "호스트 워커 회차(12~14)는 2배속을 권장한다" · "14회차 … 미검증(DoD 1)" · "가림 … 인스턴스 모드 증거 없음" | 2배속 권장 삭제(20배속 기본), §5를 A127·A128 결과로 갱신(14·16·22·21 검증됨, 12 정의 3종 있음) | S | A |
| 49 | 기능 보고서(2026-10-07) 현행화 — A122 새 화면·A129~A134 미반영, 사용자 검토는 선택 | HANDOFF:107, :243(A110) | 문서 | "기능 보고서 … 검토 후 고칠 곳 지시(선택)" | 묶음 3 캡처 뒤 `docs/보고서/build_feature_report.py` 원고에 10-08 상태·새 화면 반영해 재생성 | M | A |
| 50 | 포털 클릭으로 실제 선택·승인 제출 미실행(회귀는 API) | HANDOFF:200(A122), :297(A084) | UI | "승인·결정 버튼 실제 제출은 안 함(회귀에서)" · "포털을 사람이 직접 눈으로 본 것은 아님(헤드리스 클릭·캡처)" | 경보 1건에서 Playwright로 선택 폼 제출→ACK·종결까지 1회(`ui_capture_all_tabs.py --decide`) | S | A |
| 51 | 골든 퀘스천 화면 미검증 3가지: 실제 POST→진행 중/교정 중→완료 전환, 보고 없는 배치의 폼, 실패 칩 | HANDOFF:190(A132); `.evidence/a132/form-check.txt`("golden POSTs sent: 0") | UI | "미검증: 실제 골든 POST(유료 에이전트 실행이라 안 보냄)→진행 중/교정 중→완료 전환, 보고 없는 배치 폼, 실패 칩" | 호스트 워커 1개로 HM-9 배치에 질문 1개 POST·폴링 전환 캡처, 보고 없는 배치 폼 캡처, 실패 칩은 실행 취소로 재현(유료 사유는 A) | M | A |
| 52 | 사람 질문 카드(`humanQuestionText`) 화면 캡처 미검증 | HANDOFF:221(A12); REPO_GAP:145; sessions/README:50; curriculum:138 | UI | "화면 캡처 확인은 질문 이벤트가 있어야 해서 미검증" · "포털 질문 카드 캡처는 미검증" | 14회차 try2 정의로 HUMAN_ASKED 1건 만들어 질문 카드·스트림 캡처 | S | A |
| 53 | 워커 `/agents?check_auth=1` 실제 CLI 프로브, `permission: read_only` 정규화의 실제 실행 미검증 | HANDOFF:186(A129) | 측정 | "미검증: … read_only 정규화의 실제 실행, 프로브의 실제 CLI" | 호스트 워커에서 `curl …/agents?check_auth=1`(claude·codex), read_only 정의 1건 실행해 MCP 호출 성공 확인 | S | A |
| 54 | 워커 같은 세션 형식 교정 루프(A087 `format_correction`) 실제 발동 미검증 | HANDOFF:285(A090), :291(A087) | 측정 | "아직 실제로 발동시키지 못한 것: 워커의 형식 교정 루프(A087)는 단위 시험만" · "실제 발동은 미검증" | 출력 키 타입을 엄격히 둔 시험 정의로 위반을 유도해 워커 1회, `task_*` 이벤트의 교정 회차 확인 | M | A |
| 55 | 재작업 세대의 에이전트 작업을 실제 워커로 수행(지금은 대역 워커) | PROGRESS:19(R07); HANDOFF:148(A072) | 측정 | "재작업 세대의 실제 에이전트 미검증" · "세대1의 에이전트 작업은 … 대역 워커(Codex/Claude Code 실행 아님)" | `probe_effect_compensation.py`를 `AGENT_BRIDGE=off`+호스트 워커로 1회 | M | A |
| 56 | 변경 지식(새 SOP 적재)→실제 워커 판단 경로 | PROGRESS:26(R14); HANDOFF:593(A050) | 측정 | "변경지식의 새 Codex 경로는 남음" · "사람 편집/재작업과 변경 지식 전체 회귀" | `probe_knowledge_to_judgment.py`를 워커 경로로 1회(Claude Code; Codex는 DECISIONS 69로 기록만) | M | A |
| 57 | PG 전체 백업·여러 업무 DB 재해 복구·투영 단독 훼손 자동 탐지 미검증 | HANDOFF:603(A049) | 측정 | "PG 전체 백업/여러 업무 DB 재해 복구·투영 단독 훼손 자동탐지는 미검증이다" | pg_dump→별도 DB 복원→투영 재대조 1회, 투영 노드 하나 훼손 뒤 탐지 여부 확인(없으면 점검 추가) | M | A |
| 58 | 07회차 2·3·5단계(학생 CLI에 Neo4j MCP 붙여 질문·호출 순서) | sessions/07:28; sessions/README:17, :45; curriculum:21, :136; HANDOFF:198 | 측정 | "2·3·5단계(학생이 `claude`/`codex` CLI를 띄워 질문하고 호출 순서를 보는 것)는 돌리지 않았다 — 미검증" | 제작자 claude CLI에 `.evidence/sessions/07/01_mcp_json.json`을 붙여 2·3·5 실행·기록(토큰 사유는 A) | S | A |
| 59 | 09회차 적재(commit)·적재 뒤 질의·SQL 실행 결과·되돌리기·등록·등록 직후 골든 | sessions/09:29-30; sessions/README:19; HANDOFF:198 | 측정 | "공유 그래프를 바꾸므로 하지 않음 — **미검증**" | 시험 배치로 commit→SQL 실행→골든 POST→되돌리기→`ontology_v2.py validate` 1회(리소스 정리는 위임됨) | M | A |
| 60 | 12회차 2·3단계(업무·규칙 질문)와 4·5단계 | sessions/12:28; sessions/README:22; HANDOFF:198("12-2·3") | 측정 | "2·3단계(업무 · 규칙 질문)와 4·5단계는 하지 않음 — 미검증" | `docs/examples/business-question-v1.json`·`rule-question-v1.json` 등록·실행, 4·5단계 1회 | M | A |
| 61 | 14회차 1·2단계(가드레일·코드 수정 실험)·5단계(CLI별 차이)·6단계(실행 중 취소) | sessions/14:26; sessions/README:24; HANDOFF:198("14 가드레일 실험") | 측정 | "1·2단계(가드레일 · 코드 수정 실험), 5단계(CLI별 차이), 6단계(실행 중 취소)는 이번에 하지 않음 — 미검증" | 회차 절차대로 1회씩, 6단계는 `probe_cancel_running_task.py` 결과를 회차 증거로 연결 | M | A |
| 62 | 19회차(쿨러 완주) 회차 증거가 "실패 2회"로 남음 | sessions/19:28; sessions/README:29 | 측정 | "**실패 2회**. … 명령 직전 재검사에서 같은 사유로 명령 작업이 PENDING … 설비 과열 트립" | A129 수정(정책 v2·`--fresh-review` 기본) 뒤 19회차 `run.py` 1회 재실행, 표 갱신 | S | A |
| 63 | 23회차 2단계(DB에서 납기를 바꾼 뒤 판단 실행) | sessions/23:27; sessions/README:33 | 측정 | "2단계의 "DB에서 납기를 바꾼 뒤 판단 실행"은 하지 않음 — 미검증" | MES `due_at` 변경→판단→원복 1회 | S | A |
| 64 | RUNBOOK 10분 기동 실측 | GOAL:18, :35; RUNBOOK:3, :99; HANDOFF:202; PROGRESS:62; curriculum:20, :134 | 운영 | "10분 안 기동 시간: **미실측**" | `docker compose stop`·`supabase stop`·Docker Desktop(WSL) 재시작 뒤 RUNBOOK §1~§2 "24개 Up"까지 시간 측정(재부팅 대체임을 명기), 숫자 기입 | M | A |
| 65 | RUNBOOK 워커 `/health` 응답 키·워커 기동 명령 미검증 | RUNBOOK:64; HANDOFF:202(A124 "미검증 2") | 운영 | "워커 `/health`는 `"status":"ok"`(워커 응답 키는 10-07 대조 때 워커가 꺼져 있어 미검증)" | 워커 켜고 두 명령 실행, RUNBOOK 대조표 갱신 | S | A |
| 66 | process 메모리: 긴 core 회귀의 장시간 RSS, MEMDEBUG 끈 기준 RSS, 인스턴스 뷰 수천 회 증가 | HANDOFF:192(A131); .evidence/a131/분석.md:74-80 | 측정 | "미검증: 긴 core 회귀의 장시간 RSS, MEMDEBUG 끈 기준 RSS" · "(수천 회)는 미측정" | `PROCESS_MEMDEBUG=0`(compose 기본)으로 재생성 → 마지막 회귀 동안 RSS 로그 + hammer 2,000회 1회(10분 넘음 → 먼저 알림) | M | A |
| 67 | 처리 완료 투영 아웃박스 정리 `--apply` 미실행(dry-run만) | HANDOFF:202(A124), :224, :1125; RUNBOOK:77; `.evidence/a124/`(prune-dry만) | 운영 | "`--apply`는 회귀 뒤" · "정리는 선택" | 회귀 없는 시점에 `prune_projection_outbox.py --older-than-days 1 --apply`, 정지 상태 `--vacuum` 1회 | S | A |
| 68 | 잔재: 감지기 2배속/1배속 상태 파일(`detector-scale2/1.sqlite3`), 옛 규칙으로 등록된 시험 정의 판본(independent-reviews-* 등) | HANDOFF:176, :215(A6) | 운영 | "2배속/1배속 상태 파일 … 볼륨에 남아 있다" · "이미 등록된 시험 정의 판본 … DB에 남아 있음" | 백업 후 삭제(DECISIONS 103 위임), validate | S | A |
| 69 | 명령 경로 보안 확인: Kafka·MQTT 무인증 상태에서 `action.cmd`에 직접 쓰기 가능한지, cmd-gateway가 명령 출처(승인 기록)를 대조하는지 | DECISIONS:550(107 "보안 확인 항목"); HANDOFF:59(§3 절대 규칙) | 측정 | "세 겹 검사(사람 승인·관문·PLC)는 v3 그대로이나 출처 검증은 미확인" | 시험 클라이언트로 승인 없는 명령 1건을 `action.cmd`에 발행해 관문·PLC 동작 관찰 → 통과하면 cmd-gateway에 승인 원장 대조 추가. (107의 교체 작업이 아니라 현 구조의 §3 규칙 확인이라 A로 둠) | M | A |
| 70 | 복합 실패 범위(가속·동시 장애) 미정 | PROGRESS:20(R08), :22(R10) | 측정 | "가속/복합실패 전체 범위 남음" · "복합실패·새Codex·직접UI 남음" | 범위를 2조합(process 재시작+DB 일시 단절, 워커 사망+승인 대기)으로 정의해 각 1회, 범위는 DECISIONS에 기록 | M | A |
| 71 | DoD 3: 제품 엔진(completion)이 HYD 2.2 정의를 실제 구동하는 시험 | GOAL:32; PROGRESS:23, :59; REPO_GAP:155; REFERENCE_ADOPTION:29; DECISIONS:521(101) | 측정 | "제품 엔진이 HYD 2.2 정의를 실제 구동하는 시험은 모델 파싱으로 대신했고 실제 구동은 미검증으로 남긴다" | process-gpt-completion b272c9a를 스크래치에 받아 polling_service를 로컬 Supabase 별도 테넌트에 붙이고 v22 등록→인스턴스 시작→userTask+agentMode 행이 열리는지 1회 | L | A |
| 72 | 3배 문서(HM-FULL3) 정의 1.8 재실측, HM-FULL 절 발췌 편차(4/66·14/198) 재확인 | HANDOFF:206(A119), :277(A093); PROGRESS:14 | 측정 | "HM-FULL3 재실측(80,000자면 3구간 예상·실측 아님)" · "excerpt가 … 승인 모드 문단 — 내용 손실 아님, 발췌 선택 편차로 기록" | 1회 실측(80분 안팎 → 먼저 알림)으로 구간 수·발췌 검사 기록, 또는 문서의 "3구간 예상" 문구 삭제 | M | A |
| 73 | 회차 문서 낡은 문장: README 13행 "2배속 권장", 20회차 `standby_ready` NULL(마이그레이션 23으로 해소), 01회차 "0.5 ℃(forecasting.py 11·100~103행)"(A129 정책 v2), 16회차 "학생 절차 미검증"↔README "검증됨" 불일치 | sessions/README:49, :53, :26; sessions/20:22; sessions/01:28; sessions/16:28 | 문서 | "20배속 쿨러는 네 작업 전에 트립 — 2배속 권장(커리큘럼 §4)" · "2026-10-07 제작자 DB 값이 NULL이다" | 묶음 5의 회차 재실행과 함께 문장 정정 | S | A |
| 74 | RUNBOOK 정정: claude 2.1.250→실측 2.1.292, ps1 기본 Codex(DECISIONS 69 워커는 Claude Code), 배율 변경 시 감지기 상태 경로(`DETECTOR_STATE_PATH`) 절차 없음, Smart App Control "사용자 결정"→DECISIONS 96 | RUNBOOK:14, :44, :73; HANDOFF:160, :202(A127 관찰) | 문서 | "이전에 2배속 전환 시 실제로 필요한 이 절차가 문서에 없었으므로 운영 문서에 적어야 한다" · "관찰: `claude` 2.1.292(RUNBOOK 2.1.250과 다름)" | RUNBOOK 해당 줄 정정(64·65 실측과 같은 편집) | S | A |
| 75 | HANDOFF·GOAL·PROGRESS 마감: 머리 "최종 갱신 … A115"·§0 30초 브리핑(A072 시점)·§7 정리(GOAL DoD 7 조건)·DoD 표·PROGRESS "남은 작업" 표(10-07 A123 기준) | HANDOFF:5, :12-16, :104-109; GOAL:19, :26-36; PROGRESS:3, :51-65 | 문서 | GOAL DoD 7: "HANDOFF §6 미결정·§7 외부 대기가 "사용자 눈으로 판정할 것" 외에 비어 있다" — §7에 docs/src 서술·워커 기동 메모가 남음 | 모든 묶음 결과로 머리·§0·§7·DoD 표·PROGRESS 표를 한 번에 현행화(워커 기동 메모는 RUNBOOK으로) | S | A |
| 76 | 그래프 고아 Skill 2개(`skill:sop-fan-11`·`sop-fan-12`, 소유 배치 없음) 삭제 | HANDOFF:3, :196(A133), :198(A128) | 운영 | "삭제는 자동 모드 분류기가 거부 → 사용자 실행" · "삭제 전까지 팬 시나리오 1위 카드는 이 SOP" | 사용자가 HANDOFF:196의 `cypher-shell … DETACH DELETE` 1줄 + `ontology_v2.py validate` 실행(스킬 삭제 API가 없어 제품 경로 대안 없음 — `procsvc` DELETE는 `/api/kg/ingests/{batch}`뿐). 뒤에 제작자가 팬 판단 1위 변화 확인 | S | B |
| 77 | 학생 PC(제작자 PC가 아닌 다른 Windows·macOS)에서의 기동·Smart App Control·libpq 재현 | RUNBOOK:100; PROGRESS:62; curriculum:134 | 운영 | "학생 PC(제작자 PC가 아닌 다른 Windows·macOS)에서의 Smart App Control·libpq 문제 재현 여부" | 다른 기기 1대에서 RUNBOOK 수행(제작자 접근 불가 기기) | M | B |
| 78 | 학생 코딩 에이전트 계정·사용량 운영(7·12~14회차) | curriculum:135 | 운영 | "**미결**: 학생 계정 · 사용량 운영 … 학생 환경을 보증하지 않음" | 운영 측이 학생 계정(구독/API 키)·한도 결정 | S | B |
| 79 | 교재·시수·평가: 25회차 자가 평가 문항(교재, 저장소 밖), 교재 11장 펌프·팬 절, 시수 실측, 수료 기준 | sessions/README:57; curriculum:3-5, :144, :145; HANDOFF:1112(C5) | 문서 | "교재 작업과 시수 확정은 회의가 정한 담당(박용주 이사, 교재 집필진)에게 있다" · "수료 기준은 운영 측 결정" | 교재 담당·운영 측 작업(GOAL 10-06 범위 정정으로 시스템 목표 밖), 시스템 쪽 캡처는 `.evidence/a120/` 제공 | — | B |
| 80 | IoT·SCADA 층 제품 교체(A135 Kafka Connect·A136 Alertmanager+Mailpit·A137 OpenPLC+EdgeX·A138 Flink·A139 라우터) | DECISIONS:546-551(107); HANDOFF:3, :101, :1119, :1123 | 코드 | "IoT는 진행하지 말고 보류, 일단 원래 목표까지만" | 제외(DECISIONS 107) | — | D |
| 81 | 회의 AI 층 굵직한 블록 후보 12개(데이터 패브릭·자연어→정의·피드백 루프·What-if·레거시 메타데이터 증강·하이브리드 RAG·RPA 고착화·에이전트 옵스·알림 채널·LLM 프록시·워커 풀·하위 프로세스) | teachable-candidates.md:13-24, :66-72; DECISIONS:552 | 코드 | "같이 보류: 회의 AI 층 굵직한 블록 후보 12개" | 제외(AI 블록 후보) | — | D |
| 82 | 본문·의미 검색(B8의 "본문 검색"), memento 검색 품질(T01), 선례 사유 텍스트 유사검색(P02), "매뉴얼 의미 검색" | REPO_GAP:125, :152; REFERENCE_ADOPTION:44, :53, :97 | 코드 | "검색 품질(memento 검색 자체)은 여전히 미채택" · ""매뉴얼 의미 검색"… 미구현(B8 선택)" | 제외 — 81의 #6 하이브리드 RAG와 같은 블록 | — | D |
| 83 | 서브프로세스·다중 인스턴스·다른 오케스트레이션 | PROGRESS:23(R11 "범위 밖"); REPO_GAP:122; REFERENCE_ADOPTION:94 | 코드 | "서브프로세스·다중 인스턴스·다른 오케스트레이션 **없음**" | 제외 — 81의 #12 하위 프로세스 | — | D |
| 84 | What-if 인과 그래프·DDL 매처 0점 시험(O02 보류 후보) | REFERENCE_ADOPTION:57 | 코드 | "보류 후보 2(코드명 DDL에서 매처 0점 시험 설계·what-if 인과 그래프)" | 제외 — 81의 #5 What-if·#2 레거시 메타데이터 증강 | — | D |
| 85 | 데이터 패브릭 구현 | HANDOFF:54(§2); sessions/24:16; curriculum:27 | 코드 | "데이터 패브릭은 **구현하지 않고** 후반 설명만" | 제외 — 81의 #1(재개 시 §2 변경 확인 필요, DECISIONS 107) | — | D |
| 86 | 알림 채널(Mattermost 등) | HANDOFF:36(§1 항목 10), :100(§6) | 코드 | "과거 항목(… 알림 채널 …)은 … 포털 할일 목록 … 으로 각각 닫혔다" | 제외 — §6에서 닫힘, 81의 #9 | — | D |
| 87 | 내부 LLM: gpt-6 루나 비교·LiteLLM 전환·키 줄 관리 | HANDOFF:174, :176, :180, :313, :320; QA:254; GOAL:77 | 운영 | "LiteLLM 전환 시점 → **해소**(A073 정정 …; 키 줄은 사용자가 관리, 미결 아님)" | 제외 — GOAL:77로 닫힘(사용자 "일단은 GPU로", GPU 요약 1.1 s 실측 HANDOFF:320), 81의 #10 | — | D |
| 88 | GPU 모델 JSON 닫힘 누락(2/2) | HANDOFF:170, :174 | 측정 | "두 번 모두 바깥 객체의 닫는 중괄호 하나가 빠진 잘린 JSON" | 제외 — 추출은 Claude Code 워커·결과 파일(A119 B1)로, 내부 요약은 thinking 끔(HANDOFF:320)으로 닫힘 | — | D |
| 89 | Smart App Control 끄기 | HANDOFF:253; PROGRESS:65; QA:301 | 운영 | "Smart App Control 끄기는 일방향 스위치라 사용자 결정(결정 96)" | 제외 — 끄지 않음 확정, `scripts/host_libpq.sh`로 해결(QA:301, DECISIONS:497) | — | D |
| 90 | 정의 1.8 같은 매뉴얼 2회 재현성 | HANDOFF:206; PROGRESS:14 | 측정 | "1.8 동일 정의 2회 재현성(지시로 생략)" | 제외 — DECISIONS 104 적용 예(반복 검증 금지)로 닫힘 | — | D |
| 91 | 승인 전달 실패 뒤 경보 해제된 인스턴스의 종결 경로 없음(adbf8350·7ab5b15f) | HANDOFF:154(A072), :297(A084 d) | 코드 | "제품은 실패한 사람 작업을 다시 열거나 해제 이벤트로 종결해야 한다. 이번 범위에서 수정하지 않았고" | 제외 — A074 `abort_to`·하우스키핑(HANDOFF:315)과 A084 `_command_never_issued`(HANDOFF:297)로 닫힘 | — | D |
| 92 | 재관측 CLEAR 경쟁(기준 안인데 CLEAR 늦어 MITIGATION_FAILED) | HANDOFF:172, :176 | 코드 | "미결 결함 후보(R10/R11) … 연장을 한 번만 허용하는 현 설계 … 다음에 재검토" | 제외 — A074 `REOBSERVE_MAX_EXTENSIONS=3`·1배속 42/42(HANDOFF:315)로 닫힘 | — | D |
| 93 | 시험 잔재 RUNNING(10-03~04 23건·A108 9건·추출 실패 3·내 할일 에스컬레이션 22건·7ab5b15f 검토) | HANDOFF:176, :247, :295, :301, :315, :317 | 운영 | "잔재(삭제는 승인 필요): … RUNNING 인스턴스 9건" | 제외 — A115 `cleanup_residue_instances.py --apply` 57건(HANDOFF:224)·A131 잔재 0(분석.md:72)으로 닫힘 | — | D |
| 94 | 라이브 DB `standby_ready` NULL | HANDOFF:184(A120); PROGRESS:26 | 운영 | "사실(미수정): 라이브 DB `ent.maintenance_profiles.standby_ready` NULL" | 제외 — A133 마이그레이션 23(HANDOFF:196)으로 닫힘(문서 낡은 문장은 73) | — | D |
| 95 | 가림 흐름 인스턴스 모드 완주·팬 100 % 인터록 장면·14회차 Claude Code 질문·16회차 시간초과 학생 절차 | GOAL:137; PROGRESS:26; curriculum:138-140 | 측정 | "가림(부하 70 % → MITIGATION_FAILED)은 인스턴스 모드 증거 없음, 21회차 팬 100 % 인터록 장면은 검사 없음" | 제외 — A128 22·21·14(try2)·16(timeout2) 검증(HANDOFF:198, sessions/README:24-32)으로 닫힘(문서는 48) | — | D |
| 96 | 12회차 학생용 질문 정의 3종 "추가 중" | curriculum:24, :137 | 문서 | "`docs/examples/`에 추가 중 — **DoD 1**" | 제외 — A127 3종 validate OK(HANDOFF:202)로 닫힘(문서는 48) | — | D |
| 97 | 이상 확인·승인 목록이 사건 195건을 전부 그려 14,000px | HANDOFF:200(A122 후속) | UI | "최근 20건+더 보기로 수정 지시(A122 후속)" | 제외 — `ui.js:216` 페이지 나눔 반영(직접 확인), a122 layout incidents-1440 3,783px | — | D |
| 98 | A121: 재기동 중 찍힌 캡처 재촬영·사람 작업 폼 실제 화면 미캡처 | HANDOFF:204; PROGRESS:60 | UI | "재캡처 필요, 사람 작업 폼 실제 화면 미캡처(할 일 없을 때)" | 제외 — A122 전 탭 재캡처·`clicks/inst-todo-form.png`로 닫힘 | — | D |
| 99 | 골든 퀘스천 보고의 포털 표시 | HANDOFF:208(A118); REFERENCE_ADOPTION:56 | UI | "**미결:** 포털 표시는 UI/UX 단계에서" | 제외 — A132(HANDOFF:190)로 닫힘(남은 화면 상태는 51) | — | D |
| 100 | 서버 인용 위치로 교정 횟수가 줄어드는지 | HANDOFF:210(A117) | 측정 | "미검증: 실제 LLM 추출에서 교정 횟수가 줄어드는지는 B1 뒤 EHU40 재측정에서 함께 확인" | 제외 — A119 EHU40 교정 0(HANDOFF:206)으로 닫힘 | — | D |
| 101 | A116 쿨러 회귀 `reg-a116` 결과 "아래" 미기재 | HANDOFF:212 | 측정 | "쿨러 42 회귀(`reg-a116`) 결과 아래." | 제외 — `reg-a116/cooler-42`를 sessions/16:28이 근거로 사용, DoD 5 18/18(A134)로 닫힘 | — | D |
| 102 | 미커밋 74개·커밋/push 사용자 지시 대기 | HANDOFF:182, :313; GOAL:77 | 운영 | "커밋은 사용자 지시 시" | 제외 — b4cfabb push 이후 단계마다 커밋(GOAL:77) | — | D |
| 103 | `git diff --check` EOF 빈 줄(test_guardrail.py:114·test_stability.py:157) | HANDOFF:404, :665, :841, :903, :918 | 코드 | "이 WIP는 수정하지 않았다" | 제외 — 현재 두 파일 끝에 빈 줄 없음(직접 확인) | — | D |
| 104 | 전문가 질문 3건·감사 Q04·Q10·Q15 기준 | HANDOFF:265, :295; GOAL:77 | 문서 | "Q15 … 감사 기준은 사용자 확인 전까지 그대로" | 제외 — A098·A099·A101(감사 22/22, validate 0)로 닫힘 | — | D |
| 105 | A096 후속 후보(실행 중 취소·lease·조건 변수 검사·before/after·골든 보고) | HANDOFF:269 | 코드 | "후속 후보(코드 미반영, 채택표에 근거 기록)" | 제외 — A097·A099·A103·A118로 닫힘(T02는 21) | — | D |
| 106 | T04 실행 전 MCP 점검 | HANDOFF:251(A106); PROGRESS:25 | 코드 | "후속 후보(실행 전 initialize/list_tools 점검)" | 제외 — A113 "제품 방식 아님 … 후속 후보에서 내림"(REFERENCE_ADOPTION:47) | — | D |
| 107 | ontology-studio 방식(에이전트 생성 파서+batch 적재) 채택 여부 | HANDOFF:233(A112) | 코드 | "**미결(사용자 결정):** studio 방식 … 으로 맞출지 vs 유지" | 제외 — A119 B4 "하지 않음"(DECISIONS 101)으로 닫힘 | — | D |
| 108 | schema.json 런타임 속성 미선언(validate 5,785건) | HANDOFF:285(A090) | 코드 | "다음 작업: 런타임 속성을 schema.json에 선언하고 validate를 통과시킨다" | 제외 — A092·A101 validate 0으로 닫힘 | — | D |
| 109 | A081~A085 "남은 것"(PromQL·규칙 질의, 작업 닫기 API, PromQL 시점 충실도, 포털 수동 확인, 납기 시각 모델) | HANDOFF:295, :299, :303 | 측정 | "남은 것: PromQL·규칙 기반 질의의 같은 방식 측정, 사람이 멈춘 에이전트 작업 … 닫는 API 없음" | 제외 — A082·A083·A084·A086·A087로 닫힘 | — | D |
| 110 | A004~A071 기록의 미결 문장(새 Codex 실행·직접 UI·47레포 깊은 채택·효과 보상·의존 스케줄러·실제 문서 추출·graph outbox·R02/R06 일반화) | HANDOFF:337, :354, :369, :384, :395, :401, :418, :432, :438, :446, :452, :485, :497, :523, :557, :569, :581, :593, :617, :627, :639, :681, :693, :702, :712, :727, :738, :758, :770, :797, :808, :825, :843, :901, :957; PROGRESS:19, :22 | 문서 | 예: "새Codex/직접UI 차단은 우회하지 않고 R02실제추출·R06변경질의·R13깊은채택도 유지한다" | 제외 — A072(보상)·A043/A044(outbox)·A062~A064·A071(스케줄러)·A073/A077/A094/A119(추출)·A074 실제 Claude Code 완주(Codex는 DECISIONS 69로 기록만)·A106(46행)·A122(UI)로 닫힘. 남은 갈래는 이 표 18·25·55·56에 따로 둠 | — | D |
| 111 | 감지기 미결(A054 팬 VS1 경사 창·A055 TESTS↔cep 분리·A057 원천 조회 시간 제한·bootstrap 정리) | HANDOFF:511, :535, :545 | 코드 | "detector source query의 실행 시간 제한과 bootstrap 예외 시 store 정리도 후속 견고성 항목" | 제외 — A055·A056/A057·A060(14/14, 4/4)으로 닫힘(임의 배율 해상도는 30) | — | D |
| 112 | lease 갱신·여러 워커 동시 claim 미검증, 워커 여러 개 벽시계 단축 미실측 | REFERENCE_ADOPTION:95; HANDOFF:277(A093) | 측정 | "lease 갱신·여러 pod 동시 claim은 HYD 단일 워커라 미검증" · "벽시계 시간은 워커를 여러 개 띄우면 줄어든다(… 미실측)" | 제외 — A094 두 워커 동시 claim·A097/A114 임대 6/6으로 닫힘, 처리량 확장은 81의 #11 워커 풀 | — | D |
| 113 | A026 SOP 반례(다른 문서 같은 절 ref가 같은 ID, 검증 전 MERGE) | HANDOFF:981 | 코드 | "실제Neo4j변경은하지않았고미수정이다" | 제외 — A026 `manual_api`·`manual_review`·`manual_graph` 교체(MANUAL_INGESTION:19)로 닫힘 | — | D |
| 114 | A014 정의 등록·시작 API/UI, 폼 계약 버전 고정 | HANDOFF:1003 | 코드 | "정의 등록·시작 API/UI, 폼 계약 버전 고정은 아직 후속이다" | 제외 — A016·A017(REBUILD:19)로 닫힘 | — | D |
| 115 | A021 timer 200개 한도·일반 stale 30분·외부 state/outbox 원자성 | HANDOFF:976; REBUILD:15, :18 | 코드 | "일반stale30분/5분점검과 외부state/outbox 원자성은 남아 있다" | 제외 — A021 timer 수정·A097 lease·A043/A044 outbox로 닫힘 | — | D |
| 116 | B11·D3·D4·D5·C1~C4 "컨테이너 미검증" 목록(Supabase 마이그레이션·PgRepo·FastMCP·Claude Code 실제 호출·펌프/팬·레거시 회귀) | HANDOFF:1039, :1048, :1050, :1051, :1096, :1098, :1099, :1108 | 측정 | "**미검증(컨테이너 필요, 사용자가 컨테이너를 멈춰 둔 상태)**" | 제외 — E 블록(HANDOFF:1053~)·F·A072/A074·A120 실행으로 닫힘 | — | D |

## 개수

- A: 75개(1~75)
- B: 4개(76~79)
- D: 37개(80~116)

## A 항목 병렬 묶음

원칙: 같은 파일·같은 라이브 자원은 한 묶음. 묶음 1~4는 단위 시험·읽기 전용 캡처만 하고 컨테이너 재배포·회귀·설비 상태 변경은 하지 않는다. 라이브 스택 상태를 바꾸는 것과 최종 회귀는 묶음 5가 묶음 1~3 병합 뒤 직렬로 한다. HANDOFF·GOAL·PROGRESS·RUNBOOK·`docs/sessions/`는 묶음 5만 고친다(각 묶음은 자기 결과를 `.evidence/<A번호>/`와 짧은 보고로 넘김).

| 묶음 | 만지는 곳 | 항목 | 모델 | 예상 |
|---|---|---|---|---|
| 1 엔진·process·업무 DB | `it/process/**`, `it/supabase/migrations/**`, `it/enterprise-sim/**`, 관련 `tests/` | 11~27, 36 중 procsvc·entsim 독스트링(570·573·705~707·709·710·713·714) | fable | 2일 (22 OCR이 L) |
| 2 에이전트·MCP·워커·DMZ·온톨로지 스키마 | `it/agent/**`, `it/dmn-mcp/**`, `it/enterprise-mcp/**`, `it/agent-worker/**`, `dmz/**`, `it/connect-sink/**`, `it/neo4j/v2/**`, `compose.yaml`, `common/hydcommon/**`, 관련 `tests/` | 28~35, 36 중 나머지(221~223·225·385·386·388·389·391·393·394), 37~39 | fable | 1.5일 |
| 3 포털 UI | `it/portal/www/**`, `scripts/ui_capture_*.py` | 1~10, 36 중 576(`instances.js` 머리 주석) | fable(판정표는 메인이 캡처를 눈으로 확인) | 1.5일 |
| 4 문서·조사 | `docs/src/**`, `docs/handoff/{QA,USER_UTTERANCES,MANUAL_INGESTION,REBUILD,REFERENCE_ADOPTION,DECISIONS}.md`, `README.md`, `docs/PROJECT_STATUS.md`, `TODO.md`, `docs/curriculum-75h.md`, `docs/보고서/**` | 40~49 (40은 묶음 1·2 뒤, 49는 묶음 3 캡처 뒤) | opus | 1일 |
| 5 라이브 직렬(배포→실행→회귀→마감) | 실행 스택 전체·호스트 워커·`.evidence/**`, `docs/RUNBOOK.md`, `docs/sessions/**`, `docs/handoff/{HANDOFF,GOAL,PROGRESS}.md` | 묶음 1~3 병합·재배포 → 50~72(측정·회차 재실행·운영 정리, 10분 넘는 64·66·72는 먼저 알림) → 73~75 → 마지막에 core 12+worker 6 회귀 1회. 76은 사용자 1줄 실행 뒤 확인 | fable | 3일 |

순서: 1·2·3·4 동시 → 5 직렬. 76~79(B)는 사용자에게 한 번에 전달.
