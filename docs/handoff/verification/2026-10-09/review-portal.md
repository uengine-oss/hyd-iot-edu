# 포털 프런트 검토·보강 (merge-preview, 2026-10-09)

범위: `git diff 7fa5664..HEAD -- it/portal/www` (10개 파일). 점검표 A~D 기준.
형식: 발견 → 분류(결함 / 의도된 차이 / 오해 / 근거 부족) → 조치(파일:줄) → 검증.

## 0. 진행 상태
- [x] 점검표·헌법·프로젝트 CLAUDE.md 통독, diff 10개 파일 전문 읽기 완료
- [x] 수정 · 화면 검증 완료 (커밋 안 함 — 코디네이터가 커밋)

## 1. 발견 (수정 전, 줄 번호는 HEAD 88b64d6 기준)

| # | 파일:줄 | 발견 | 점검표 | 분류 |
|---|---|---|---|---|
| F1 | caseRecord.js:738-741 | `agentsList()` 가 `/api/agents` 실패를 `catch (_) { rows = [] }` 로 삼킴 → AI 일꾼의 목표 · 스킬 · 도구가 "없음"처럼 보이고 다시 읽지도 않음 | A2 폴백 금지 | 결함 |
| F2 | caseRecord.js:88-89, 243-245, 593 | 판단(`/api/decisions`)을 읽는 중인데도 "판단 …을 읽지 못했습니다"로 보임(로딩 = 실패 혼동), 실제 실패 때는 사유(`ext.decision.error`)를 버림. 판단 id 원문을 그대로 노출 | B 상태 구분 · D 내부 id | 결함 |
| F3 | caseRecord.js:391 | 사건(`/api/incidents`)도 같은 문제: 읽는 중 · 실패 · 사건 번호 없음이 한 문장, 실패 사유 버림. 명령 단계가 아닌 확인 단계(재관측)는 사건 실패를 아예 알리지 않음 | B · A2 | 결함 |
| F4 | caseRecord.js:244 `${ctx.d === null ? '' : ''}`, 429-431 `const act = TR() ? '' : ''; void act;`, 596 `void evs;`(안 쓰는 인자), 503 같은 값 두 갈래 삼항 | 죽은 코드 | C | 결함(청결) |
| F5 | caseRecord.js:582 | 같은 `find(task_started)` 를 한 줄에서 두 번 | C 중복 | 결함(청결) |
| F6 | caseRecord.js:36,592,656,610-611,739,777,787,805 | 매직 넘버(220 · 1500 · 600 · 12000 · 60000 · 3000 · 500 · 4000). 1500 은 서버 `instances.py:45 EVENTS_WINDOW` 와 같은 값인데 이름 없이 복사 | C | 결함(청결) |
| F7 | instances.js:342-351 `ensureRecord` | 처리 건을 바꿀 때마다 새 컨트롤러를 `keep=true` 로 `hydRecord.mounted` 에 넣고 옛것을 빼지 않음 → SSE 이벤트마다 · 원문 받기 때마다 지난 처리 건들까지 다시 그림(누수) | 근본 결함 | 결함 |
| F8 | enterprise.js:55-63 `loadNamespaces` | `catch (e) { /* 목록이 없으면 수업 기준만 */ }` — 이름 공간 목록 실패를 삼킴. 강사는 학생 이름 공간이 "없는" 것인지 "못 읽은" 것인지 모름. 또 한 번 읽으면 "다시 읽기"로도 새로 적재한 학생 이름 공간이 안 뜸. 라벨 `s01 · 23` 의 숫자 뜻이 없음 | A2 · B | 결함 |
| F9 | agents.js:415 | 역할 만들기 성공 알림에 내부 id `(${r.id})` 노출 | D 내부 id | 결함 |
| F10 | agents.js:418-420 | 역할 지우기가 확인 없이 바로 DELETE(되돌릴 수 없음) | D UI · 안전 | 결함 |
| F11 | mcp.js 비밀 값 지우기 | 확인 없이 바로 DELETE, 성공 알림 없음(실패만 알림) | B · D | 결함 |
| F12 | mcp.js readConfirm 알림 | 도구 원래 이름(`read_neo4j_cypher` 등)을 그대로 씀 — 같은 화면은 `toolLabel()` 로 한국어 이름을 씀 | D 영문 잔재 · C 기존 헬퍼 재사용 | 결함 |
| F13 | plainWords.js:206,213 | 사전 함수가 예상 밖 모양에 던지면 `catch (_) {}` 로 삼키고 일반 요약으로 감. 화면에는 원본 값이 그대로 남으므로 정보 손실은 없지만 사전 결함이 보이지 않음 | A2 | 결함(경미) — 콘솔 경고로 드러냄 |
| F14 | plainWords.js:68 | `(/^[%℃]/.test(u) ? ' ' : ' ')` 두 갈래가 같음 | C 죽은 조건 | 결함(청결) |
| F15 | caseRecord.js:610, 627 · plainWords.js:123 | JSON 해석 실패 시 원문 글자로 보임 | A2 | 의도된 차이 — 원문을 그대로 보이므로 숨기는 것이 없음, 유지 |
| F16 | plainWords.js:9,237 localStorage try/catch | 원래 이름 보기 설정 저장 실패 시 기본값 | A2 | 의도된 차이 — 화면 편의 설정, 유지 |
| F17 | caseRecord.js 전체 XSS | 데이터가 들어가는 자리 전부 `e()`/`esc`/`UI.chipText`(이스케이프함)/`W().id`(esc) 경유 확인. `why(o)` 추천안 갈래만 이스케이프 없이 넣는데 `hydApprove.reasons()` 가 이미 `e()` 한 HTML 을 돌려줌(approvalCard.js:25-37) | 보안 | 오해 — 문제 없음 |
| F18 | mcp.js 비밀 값 | 값 입력은 `type=password autocomplete=off`, 목록 응답(mcp_secrets.py:274-278)에 값이 없음, 화면 · 알림 어디에도 값 출력 없음 | D 비밀값 | 문제 없음 |
| F19 | caseRecord.js:860 `wireBus` | liveStream.js 가 뒤에 실리므로 500 ms 재시도로 붙음 | — | 의도된 차이, 유지 |
| F20 | 실행 중 스택 | process(8080)·agent(8091)가 이 브랜치 이전 이미지라 `/api/roles`·`/api/mcp/secrets`·`/api/ontology/namespaces` 가 404 | — | 근거 부족 → 화면의 "실패" 상태 확인에만 씀, 성공 경로는 미검증 |

### 화면을 띄워 보고 더 찾은 것 (수정 전 첫 캡처에서)

| # | 위치 | 발견 | 분류 |
|---|---|---|---|
| F21 | caseRecord.js humanStep | 판단의 승인 이력(처리 건 전체 것)이 승인 카드가 아닌 다른 사람 단계(책임자 확인)에도 붙어, 같은 승인이 두 번 그려짐("김운전 … 승인" ×2, 실제 9단계는 이생산의 책임자 확인) | 결함 — 블랙박스 반대(틀린 기록) |
| F22 | caseRecord.js humanStep | 승인한 사람이 `user:jung-buy` 원문으로 보임(승인 화면에서 "나"를 고르면 id 로 저장) | 결함 — 내부 id |
| F23 | caseRecord.js humanStep · systemStep | 판단을 못 읽었는데도 "추천안 그대로 승인", 사건을 못 읽은 끝난 처리 건에 "설비의 응답을 기다립니다" — 모르는 것을 단정 | 결함 — 해피패스 단정 |
| F24 | caseRecord.js 문장 전반 | 조사 오류("[재고 보충] 버튼가", "‘긴급 발주’을", "‘축 씰 마모’로"는 맞지만 받침 무시 일괄) · 재관측 문장 "지켜본 뒤 값 — 기준 …" (잰 값 모를 때 "값" 자리표시) · 기준 기호 `>=` 원문 | 결함 — 쉬운 한국어 |
| F25 | plainWords.js | 경보 값 `loadsp`, 규칙 `PLC.state == 'RUN' … LoadSP >= 80` 이 영문 그대로(사전에 구동 설정값 없음) | 결함 — 영문 잔재 |
| F26 | app.js requestJ | 서버 기본 문구 "Not Found" 등이 실패 사유로 그대로 보임(새 화면의 실패 상태에서 확인) | 결함 — 영문 잔재(근본: 공용 요청 함수) |
| F27 | index.html | enterprise.js · agents.js · mcp.js 가 바뀌었는데 `?v=` 판 표시가 그대로 | 결함(경미) — nginx 가 no-cache 라 실해는 적음, 관례대로 올림 |
| F28 | mcp.js confirmForm | `UI.field` 가 hint 를 다시 이스케이프하는데 hint 안에서 `esc(t.name)` → 이중 이스케이프 | 결함(경미) |

## 2. 조치 (파일:줄은 작업본 기준)

- F1 · F2 · F3: caseRecord.js:42-48 상수 · `extState`(번호 없음 / 읽는 중 / 실패 / 성공), :103-108 `ctx.read`, :257-260 대안 칸(읽는 중 · 실패 사유), :455-468 `ackMissing` · `incidentGap`, :612-641 `gapsOf`(판단 · 사건 · AI 일꾼 설정 · 사람 이름 실패 사유), :777-784 `sharedList`(실패를 던짐), :845-868 `fetchExt`(실패하면 4초마다 다시 읽기). 
- F4 · F5 · F6: 죽은 코드 3곳 삭제, `startedData` 로 중복 제거, 매직 넘버 → `SENTENCE_MAX_CHARS · NOTE_MAX_CHARS · RAW_MAX_CHARS · EVENTS_WINDOW(서버 상수와 연결 주석) · OLDER_PAGE_ROWS · LIVE_MAX_ROWS · EXT_REFRESH_MS · SHARED_TTL_MS`.
- F7: instances.js:345 옛 컨트롤러를 `hydRecord.mounted` 에서 뺌.
- F8: enterprise.js:55-77 `loadNamespaces(force)` — 실패 사유를 고르기 칸 안 비활성 줄 + title 로, "다시 읽기"에 다시 읽음, 고른 이름 공간이 사라지면 알림 후 수업 기준으로, 라벨 "s01 · 항목 23개", 목록이 비면 "학생 이름 공간 없음".
- F9 · F10: agents.js:415 알림에서 id 제거, :418-422 역할 지우기 확인 대화상자(서버 거절 조건까지 안내 — agent_authoring.py:487-502 와 대조).
- F11 · F12 · F28: mcp.js 비밀 값 지우기 확인(쓰는 서버 이름 포함) · 성공 알림 · 빈 이름 검사, 읽기 확인 알림 · 안내에 `serverLabel/toolLabel` 재사용, 이중 이스케이프 제거.
- F13 · F14: plainWords.js 사전 실패를 `console.warn`(도구 이름 포함)으로 드러냄 — 화면은 원래 값을 그대로 보이므로 일반 요약 유지(의도된 차이), 같은 두 갈래 삼항 제거.
- F21: caseRecord.js humanStep — 승인 카드 단계가 따로 있으면 판단 승인 이력은 그 단계에만.
- F22: `/api/inbox/users` 사람 이름을 처리 건 이름표(caseNames)에 넣고 승인자 · 전달 기록 · 시스템 기록의 `by` 를 이름으로. 사람 이름 목록 실패는 "기록에 없는 것"에 사유. 사전에 없는 `user:` 는 "사용자 …".
- F23: 판단 모르면 "추천안 그대로/대신" 말을 빼고 칩도 중립색. 사건 모르면 "읽는 중 / 읽지 못해 알 수 없음 / 응답 기록 없음" 으로 가름.
- F24: plainWords.js `W.josa(word, '을/를'|'이/가'|'은/는'|'으로/로')`(한글 받침 · 숫자 · 영문 · % 끝소리), caseRecord.js 문장 10곳에 적용, `reobsBasis` 로 모르는 값 말 빼기, `W.criterion` 기호 ≥ ≤.
- F25: plainWords.js 값 사전 `loadsp · fanspeedsp · valvesp`(이름은 it/neo4j/v2/instances.cypher:139 Actuator), `W.rule` 태그에 구동 설정값 · `PLC.state == 'X'` → "설비 상태 운전 중".
- F26: app.js `HTTP_DEFAULT_DETAIL` — 프레임워크 기본 영문 문구만 한국어 + 상태 번호로(서버가 준 한국어 사유는 그대로).
- F27: index.html 바뀐 7개 스크립트 `?v=20261009-a161rv`.

## 3. 검증

| 검사 | 방법 | 결과 |
|---|---|---|
| 문법 | `node --check` agents · app · caseRecord · enterprise · instances · mcp · plainWords | 검증됨 (7/7) |
| 실패 사유가 보이는가 + 뮤테이션 | `.evidence/a161-review-portal/readfail.js`: 판단 500 · 에이전트 503 · 사건 500 으로 바꿔 끼우고 처리 기록 글에서 사유 3개 + 거짓 단정 2개 부재 확인. 고치기 전(HEAD 사본, 포트 8712)과 작업본(8711) 둘 다 돌림 | HEAD: 5항목 모두 false(exit 1) → 작업본: 모두 true(exit 0). 검사가 결함을 잡음 — 검증됨 |
| 컨트롤러 누수 + 뮤테이션 | `leak.js`: 처리 건 3건을 오가며 `hydRecord.mounted.size` | HEAD 6 → 작업본 1 — 검증됨 |
| 조사 고르기 + 뮤테이션 | `josa_test.js` 15건, `return without` 으로 깨뜨린 사본 | 통과 15/15, 깨뜨린 사본 5건 실패 — 검증됨 |
| 화면 1440 · 390 | `shots.js`(GET 만 허용, 쓰기 요청은 abort). 끝난 예비품 처리 건 · 끝난 쿨러(미달) 처리 건 · 진행 중 처리 건 · 읽기 실패 · 지식 지도 이름 공간 · MCP 비밀 값 · 에이전트 역할 만들기/지우기 확인 → 16장 + `screen-facts.json` | 검증됨. 처리 기록 글에 `role: · user: · task:` 등 내부 id 0건, 콘솔 오류는 일부러 실패시킨 요청뿐. 남은 영문: 스킬 파일 이름(spare-purchase-planning · SKILL.md), 부품 번호(P-PMP-SEAL), 제품 이름(CMMS · Claude Code · Inbucket) — 실제 이름이라 유지 |
| 새 API 성공 경로 | 실행 중 process · agent 가 이 브랜치 전 이미지라 `/api/roles`·`/api/mcp/secrets`·`/api/ontology/namespaces` 404 | **미검증** — 이름 공간 목록 성공은 응답을 바꿔 끼워 라벨만 확인("s01 · 항목 23개"), 역할 지우기는 응답에 시험 역할을 넣어 확인 대화상자까지만(DELETE 는 막음) |
| 서버 정리 | 정적 서버 8711 · 8712 종료, LISTEN 없음 확인 | 검증됨 |

## 4. 남긴 것 (범위 밖 · 미결)

- instances.js:32 `catch (e) { I.instances = []; }` 는 이번 diff 밖 기존 코드라 손대지 않음 — 처리 건 목록 실패가 "처리 건 없음"으로 보일 수 있음(결함 의심, 별도 처리 권고).
- 스킬 이름 · 부품 번호 · 명령/작업지시 번호는 원문 유지(사람이 이 번호로 다른 시스템을 찾음).
- 승인 이력이 여러 번인 판단(재승인)에서 승인 카드 단계가 여럿이면 각 단계는 `approvals` 행(todo_id)으로 짝지어지고, 짝이 없는 옛 흐름만 판단 이력의 마지막 승인을 씀 — 옛 흐름에서 승인 단계가 둘 이상이면 여전히 같은 이력을 보일 수 있음(근거 부족: 그런 처리 건 실물 없음).
