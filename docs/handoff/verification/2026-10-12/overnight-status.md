# 2026-10-12 전체 잔여 작업 상태

기록일은 Asia/Seoul 기준이다. 사용자 최신 지시 「아예 싹 다 밤새 진행 / 목표 설정」에 따라 NOW의 열린 UI·기능·종합 랩 항목 전체를 추적한다. 시작 기준은 작업 트리 `codex-portal-20261011`의 `41e21cd`이며 처음에는 Sol 6.1 읽기·Astra 쓰기로 시작했으나 **최신 사용자 지시로 현재 모든 작업·워커는 Sol 6.1만 사용한다**. 교재와 `.claude/skills/lecture-deck/`는 수정하지 않는다. 커밋·push와 최종 완료 판정은 메인이 담당한다.

이 문서는 착수 상태와 이후 메인이 확인한 결과를 구분해 기록한다. **진행 중은 성공을 뜻하지 않는다.** 이전 증거는 재현 출발점이며 이번 최종 코드 검증을 대신하지 않는다. 표의 차단 원인도 작업을 멈췄다는 뜻이 아니라 해당 완료 주장에 필요한 조건이다. 사용자 시각 판정, 실제 LLM 실행, MemoryRepo·단위 시험, 독립 DB 검증을 구분한다.

담당 묶음은 UI `approval_write`, 백엔드 `flows_write`, 실제 스택·독립 DB·최종 통합 검증 `root`다. 문서 담당은 결과를 수신하고 메인이 확인한 뒤 표를 갱신한다. 시작 당시 root가 독립 Supabase 프로젝트 `hyd-iot-edu-verify20261012`(55320~55329)와 Neo4j `hyd-verify-neo4j-20261012`(Bolt 7787)를 준비 중이었다. 기동 성공·마이그레이션 성공으로 미리 기록하지 않는다. 기존 수업 데이터 볼륨은 변경하지 않는다.

## UI 항목 전수표

### 최신 확인된 검증과 실제 상태

| 범위 | 확인 결과 | 실제 증거와 제한 |
|---|---|---|
| 전체 소스 회귀 | **2275 passed·21 skipped·64 warnings·195.06초,exit0** | `pytest-final-source.log/xml`; K1 메일 의존·URL query 비밀값 최종 두 수정 포함. 후속 UI 변경까지 소급하지 않음 |
| 실제 학생 동선 | **student-release18 checks 모두 PASS,exit0** | 최신 Windows adapter·엄격 MCP alias/전체 인자 대조 적용 후 별도 실행. 질문 verified·읽기 입력/기록·개인 흐름 DONE·시스템 PENDING close·F2 projection_pending0 |
| K1 독립 PostgreSQL | **17 passed,18.91초** | `k1-pg-final.log/xml`. 명시 transaction 원자성 및 최종 선택 export·URL 비밀값 회귀 포함 |
| K1 실제 브라우저 | 태그 저장→사례 필터→파일 받기→태그 제거 통과 | `k1-live/checks.json`·1440/1024 PNG·student-case.json. export 흐름1·에이전트1·MCP1, errors=[]; 마지막 두 코드 수정 후 실제 재빌드 증거와는 구분 |
| F4 실제 Neo4j·HTTP | **16 passed,8.98초** | `manual-http-neo4j.log/xml`; 독립Bolt7787, 기존13+HTTP3. DecisionCase 이력 보호·409·rollback·부분쓰기 없음·시험 그래프 정리 |
| 이전 포털46화면 | console/pageerror0·ignored0·문서폭 넘침0 | `live-release/console.json`·layout.json·residue.json. ontology SVG 경계 초과12개·영문/내부 이름 잔여를 보존. 문서폭0은 SVG 잘림 없음이나 최종 사용자 시각 승인이 아님 |
| 상세 실제 캡처 | **최신 기능 준비7개 모두pass·가로넘침false** | `target-capture-final/checks.json`·student-graph.json·PNG. 전체summary passed=false/exit1:3종health no-cors ERR_ABORTED 반복, HTTP200/up/console0 및CDP fulfilled opaque10~19ms 확인. 본문취소진단이며검사기summary는수정하지않음. 첫target4pass/3미완 로그도 보존 |
| F3 HM-8 | 실제 추출 제안 생성 | 활성 작업 트리 `.evidence/a161-c3/proposal-HM-8.json`:8 procedures·18 warnings. 모델 전환 전 Astra 결과. 사람이 검토하지 않았으며 적재 전 |
| F3 PM-02·PR-07 | Sol6.1 PM-02·PR-07 제안 생성 | Astra PM-02는 사용자 전용 모델 지시에 따라 공식 cancel 후 close(`astra-close.json`:COMPLETED/closed-by-human). `manual-extraction-sol.log`에서 첫 PM-02·PR-07 제안을 생성했고 PR-07은 신규2.4로 실제 Sol 재추출COMPLETED/6SOP21단계를 확인했고 실제 worker model=gpt-6.1-sol을 메인이 확인했다. 기존 미완 로그도 보존. 추출·검토·적재를 서로 구분 |
| 실제 B | **자율보류 PENDING** | 실제 MCP는 정상 실행했지만 causes=[]·PREVENTED_BY 없음. 열린 incident 때문에 close409 정상. 현재 A/B/C 완주를 완료했다고 쓰지 않음 |
| K4 | **실제 Sol6.1 자율보류→공식 close 7 checks 모두 PASS,exit0** | `k4-live/summary.json`·k4-live.log. 실제 customer 필수 미응답/read_rows trace·self-deferred PENDING·close 전 소유/상태 대조·기술 종료/미도달 Report CANCELLED·업무 보고 미실행 |
| 스택·통합 | 02:53 KST 서비스 종료·본인 LIVE_LOCK 해제 | K1 수정 포함 process 재빌드02:23:44 KST·RestartCount0, 추출2.4 process 재빌드02:38:52 KST. 최종 서비스 정리 완료. 코드 반영 해시는 git log와 최종 보고 참조. 원격 추가 교재 변경은 메인이 통합하며 이 작업에서 교재 수정 없음 |

문서 담당은 위 전체 pytest·K1 PG·F4 로그의 마지막 결과와 student-release18개 passed, k1-live checks, target-capture 결과를 직접 확인했다. 이번 결과와 이전 macOS A/B/C 완주, 10-11 Windows 종료를 구분한다.

### 이전 실패와 중간 성공 기록

`pytest-all`의1 failed·2206 passed·17 skipped는 승인 폴링이 view/taskView를 먼저 null로 지운 경합이었다. 시험 로더에서 이전 동작을 복원하면2개 회귀가 실패했고, 제품 수정 후 승인13개·UI34개가 통과했다. `pytest-final`2213/17/64(151.29초)는 이후 변경 전 결과다.

`pytest-complete`2258/18/1은 신규 추출2.3에 대한 옛2.2 고정 기대였으며 새2.3와 기존2.2 immutable 보존을 함께 검증하도록 갱신했다. `pytest-release`2272/21/64(184.55초)는 K1 마지막 두 수정과 동시에 실행돼 중간 결과다. 현재 전체 기준은 위2275이며 모든 최초 실패 로그는 보존했다.

F16·F17 질문 근거/폼별 교정/추출provider179개, F18 시작 실패 진단55개, F19 등록 스킬 본문/해시75개, Windows bounded sandbox adapter104개의 세부는 `backend-remaining.md`를 따른다. F19 실제 B 도구 실행 정상은 업무 완주와 구분한다. HM-8 첫 Windows 파일 쓰기 실패 후 `workspace-write` 및 개인설정 차단을 유지한 실행별 backend 선택을 적용했다.

### 현재 실제 B 시나리오 복구

실제 B-reject 시작 실패 뒤 메인이 환경을 복구했다. 기존 main DB 기준 users는 10→21(기존 학생 3 포함), role_members 0→6, skills 0→3, agent_skills 0→3으로 공식 seed의 public 부분을 적용했다. tenant MCP는 누락된 정비/구매만 추가했고 기존 ent 데이터·tenant 설정 전체를 덮지 않았다. 초기의 「기존 수업 볼륨 변경 없음」은 독립 DB 검증 단계의 범위이며, 이후 이 공식 기준 누락 보완을 숨기지 않는다.

uvx가 없어 required Neo4j MCP가 시작하지 못했다. 같은 mcp-neo4j-cypher 0.4.1·fastmcp 2.13.0.2를 별도 venv와 서명된 Python으로 실행하며 DB의 원래 Neo4j 명령 snapshot을 보관했다. 기존 실패 처리 건에는 열린 incident가 있어 `/close` 409가 정상이고, 제품 rework-preview 및 재작업 API 200으로 재진단 중이다. 종료/복원/시나리오 성공은 아직 선언하지 않는다.

이전 기록 경로는 이 문서 기준 `../2026-10-10/` 또는 명시한 날짜를 뜻한다. 최신 사용자는 Claude 주간 한도 뒤 Codex 전환과 통상 구현 판단 자율 진행을 승인했다. 따라서 구현 기대값 충돌은 실제 계약·원천 보존·회귀로 판단하며, 검증 결과 없이 성공으로 바꾸지는 않는다. 최신 수치와 상세 캡처 결과는 상단 표와 capture-review.md가 기준이며 후속 재검증은 계속한다.

UI U5·U6·U9~U14는 `portal-remaining.md`에 구현 및 자동검증을 기록했다. 승인·잔여 UI·흐름 독립 Chromium 묶음은 최종 수정 후 34 passed이며, 사람 이름·역할 이름·원천 ID 보존·다른 사건 오염 방지 등 관련 기록 회귀는 49 passed다. U15는 지시·표시 수정과 실제 모델 준수를 구분한다. 아래 표의 실제 캡처·학생 동선 잔여가 이 시험만으로 닫히지는 않는다. 사용자가 구현 판단을 위임한 사실과 실제 캡처에 대한 시각 판정은 구분한다.

| 항목 | 착수 상태 / 담당 | 기존 증거·확인 대상 | 완료에 필요한 검증 또는 차단 원인 |
|---|---|---|---|
| U5 복구 지령 변화 | 구현·자동검증 / UI | `F-keep.md`, `final-verify.md`; `data.setpoints.before/after` | 실제 복구 기록에서 팬·부하 변경 전후를 한국어로 표시한 캡처 |
| U6 A 재시작 안내 | 구현·자동검증 / UI·root | NOW 3절: 복구 후 감지기 해제 약 65초의 이전 실측 | 거절·무응답 후 대기 상태 안내와 실제 다시 시작 가능한 시점 검증 |
| U9 단계 닫기·흐름 삭제 | 구현·자동·실제 API 확인 / UI·백엔드·root | `student-live`: 실제 missing extract PENDING → 실행 중 삭제 409 → close → 단일 삭제·404·projection_pending=0 | UI 실제 캡처 및 최종 시각 판정과 별도. 실제 실패를 성공 결과로 바꾸지 않음 |
| U10 내부 값 노출 | 진행 중 / UI | `K-capstone.md`, NOW 세부 목록 | 역할·흐름·시작 값·승인 선택·도구 한글·규칙 이름의 각 표시를 캡처로 확인 |
| U11 B·C 업무 화면 | 구현·독립 브라우저/회귀 확인 / UI | `HANDOFF.md` 기존 273행, `review-c3-bc.md` | 정비·구매 값에 맞는 카드·결과 보고 및 A 회귀, 사용자 시각 판정 |
| U12 보상·검토 기록 | 구현·자동검증 / UI | `review-c3-bc.md` 4절 | 단계 없는 `EFFECT_COMPENSATION`·`EFFECT_REVIEW`를 실제 이벤트 입력으로 표시 |
| U13 실패·빈 값 표시 | 진행 중 / UI·백엔드 | `2026-10-09/review-backend.md`, `review-c3-bc.md`, `cap-g3g9.md`; 전일 skills null 오류·incidents.filter 오류 | 재관측·스킬 설치·목록 읽기 실패·상태 조회·MCP 반환·실패 시도별 확인. 전일 오류 2종 재현/수정/브라우저 확인 |
| U14 업무 규칙 | 구현·PG/학생 동선 확인 / UI·백엔드 | `cap-g3g9.md` 5절 ② | 에이전트 work_rules 저장값과 표시 일치; PG 저장 경로는 F7 |
| U15 영어 혼잣말 | 진행 중 / UI·백엔드·root | `2026-10-09/u1-uiux.md` 7절 결함 16·17 | 워커 지시와 실제 발화 확인; 문구만 수정해서 LLM 결과 완료 주장 금지 |
| U16 교재용 화면 증거 | 진행 중 / UI·root | 전일 `portal-20261011.md` 46화면 캡처 | 수정 후 시스템·지식 지도·조치·매뉴얼 적재 후 관리·질의 1440폭 캡처. 교재 파일 자체는 수정하지 않음 |
| U17 학생 에이전트 | 실제 학생 동선 통과 / UI·root | student-codex-stdin 18 checks 중 프로필·규칙·실제 MCP·근거 답변 | 이전 실패는 보존. 성공 이후 F16 후속 엄격 계약은 별도 검증 |
| U18 MCP 실습 | 실제 MCP·워커 호출 확인 / UI·root | 학생 서버 등록·재연결·read_rows 반환·입력 일치·에이전트 연결·호출 기록 | student-codex-stdin 통과. 외부 Google 서버까지 검증한 뜻 아님 |
| U19 역할·승인 실습 | 진행 중 / UI·root | 69행; 전일 `approval-ui.md` 실제 엔진/MemoryRepo 검증 | 학생 역할 선택과 권한 부족 403, 승인·거절 후 상태. 로그인 인증 증명과 혼동하지 않음 |
| U20 A·B·C 학생 흐름 | 진행 중 / UI·백엔드·root | 94·95·102·104행; 전일 `flows-ui.md` 매핑 UI→API 저장 대조 | 검사·등록·배포·담당/대기/결과, 실제 스택 완주. mapping.json/API 허용 경로 유지 |
| U21 개인 예제 | 실제 로컬 읽기 흐름 통과 / UI·root | student-codex-stdin 실제 도구 trace·응답 내용·Read/Report DONE | 이전 한도/근거 없는 DONE 실패는 보존. 외부 쓰기·K3 성공 주장 없음 |

U1~U4·U7·U8은 전일 구현·자동검증 완료이며 이번 잔여표에서 제외했다. 사용자 캡처 시각 판정 대기와 최종 변경 뒤 회귀 필요는 그대로다.

## 기능·환경 항목 전수표

| 항목 | 착수 상태 / 담당 | 기존 증거·확인 대상 | 완료에 필요한 검증 또는 차단 원인 |
|---|---|---|---|
| F1 개인 연결 도구 노출 | 현재 Codex 경로 격리·실제 학생 도구 실행 확인 / 백엔드·root | run-local 등록 도구·ignore-user-config·apps=false·명시MCP·student-release18 checks | 과거 Claude 개인 연결 live는 현재 Sol 전용 지시 밖. Codex 경로의 필수 미완으로 남기지 않음 |
| F2 삭제 뒤 그래프 투영 | 구현·실제 그래프 확인 / 백엔드·root | flow-cleanup-neo4j 3 passed; deleted-flow-graph.json: ProcessVersion/Instance 없음 | ExecutionProjection fence 1개는 늦은 투영 재생성을 막는 정상 tombstone이며 삭제 잔재 결함으로 세지 않음 |
| F3 매뉴얼 재추출·검토·적재 | HM-8·Sol PM-02/PR-07 제안 생성 / root | 신규2.3·기존2.2 보존; 활성 작업 트리 proposal-HM-8.json·astra-cancel.json | HM-8 Astra 결과는 전환 전 생성. PM-02 Astra 취소 기록 보존. 실제 사람 검토/적재 미완료, reviewed 기록을 대신 만들지 않음 |
| F4 개정·rollback 보호 | 실제 그래프·HTTP 검증 완료 / 백엔드·root | manual-http-neo4j.log/xml 16 passed·8.98초 | 기존13+실제HTTP3, 판정 이력 보호·409·rollback 확인. fixture 자체 정리 |
| F5 미제출 DEC 상세 | 구현·계약 회귀 통과 / 백엔드·root | `live-leftovers.md` 5절 | 가드레일 거절·후보 없음 경로 재현, 404를 감추지 않고 식별자/상세 계약 검증 |
| F6 C 승인 재확인 | 구현·설비/업무 의존 회귀 통과 / 백엔드·root | `live-leftovers.md`; 기존에는 코드 추정 | 승인 전후 설비 값 변화와 업무 값 변화 각각 재현. C 업무 판단의 실제 의존성을 확인 |
| F7 PG 경로 | 실제 독립 PG 확인 / 백엔드·root | backend-pg.xml 3 passed·5.3초; backend-pg-four.log B1→BPMN→Trial→B6 순차 4 passed | 임시 tenant 정리와 Trial stub 원복 포함. 관련 실제 계약 범위는 backend-remaining.md, 전체 최종 회귀는 별도 |
| F8 worker 파일 경계 | 구현·경로/링크 경계 회귀 통과 / 백엔드 | 같은 기록 3-5절 | tool-results 경로·허용 workspace·경로 탈출/링크 회귀. 정상 도구 결과 읽기 유지 |
| F9 깨끗한 시험 환경 | 새 환경 설치·전체 회귀 통과 / 백엔드·root | clean-install-final.log·pytest-final-source.log/xml | 새 환경2275pass/21skip. skip·환경 의존 조건과 임의 기존venv 성공을 구분 |
| F10 새 Supabase DB | 메인 확인: 신규 DB 검증 통과 / root | `fresh-migrations.txt`, `supabase-configured-start.log`: 42 SQL files, max 20261010000051, 시작 exit 0, seed ent.assets 3·users 18 | 독립 프로젝트 hyd-iot-edu-verify20261012, DB 55322. 처음 기본 설정으로 띄운 별도 시도는 정지·보존했고 nested supabase/config와 --workdir로 정상 설정 재검증 |
| F11 C 공급자 보고 | 보고 문구·당시 B-OEM 근거 연결 확인 / 문서·root | `docs/보고서/2026-10-09_HYD_시나리오_3개.md` 기존 221행, `live-final.md` 3-5 | B-OEM 근거와 보고 문구 대조 후 수정 검토. 본 문서 담당의 현재 수정 범위 밖이므로 메인 확인 필요 |
| F12 부족한 운영 근거 | full seed 부분 검증 / root | `kg-seed.log`: full seed exit 0, 59.719291초, readback 17 checks·0 failed | 16분 지연은 재현되지 않음. 과거 지연 원인·고아 문서·전체판 검사기 전제는 별도 잔여 |
| F13 옛 통합 검증·보고 | 진행 중 / root | HANDOFF 기존 §9 312·313행 | 최신 전수 진행 지시 아래 학생 직접 작성 완주/현황 보고를 U20·U21과 통합해 유효 범위 판정 |
| F14 순위 점수 내역 | 원인 확인·자동검증 / 백엔드 | backend-remaining.md: 수동 렌더 fixture의 독립 상수 score/parts 차이; 실제 ranking.score 성분 합 검증 | golden 보존. 고정본을 실제 계산 교육자료로 사용하지 않음 |
| F15 Codex 긴 작업 본문 | 구현·86개 시험·학생 live 18 checks 통과 / 백엔드·root | codex-transport-tests.log, student-codex-stdin/summary.json | 이전 student-codex 실패 결과 유지. 후속 F16 근거 강화는 별도 |
| F16 질문 근거·폼별 교정 | 구현·자동검증 완료 / 백엔드 | ask-provider-tests.log 179 passed 묶음 | 실제 서버/도구·전체 인자 일치, 타입/키/배열순서 보존. result 요약 의미까지 검증됐다는 뜻 아님 |
| F17 추출 provider | 새 2.3 구현·자동검증 완료 / 백엔드 | 같은 179 passed 묶음 | 기존 2.2 보존. 실제 새 추출·사람 검토 적재는 F3 |
| F18 시작 실패 진단 | 구현·자동검증 완료 / 백엔드 | worker-diagnostics-tests.log 55 passed | Fatal 꼬리·가림·FAILED 즉시 미완 종료. B 실제 재진단 진행 중 |
| F19 등록 스킬 본문 | 구현·75개 시험·실제 B 도구실행 / 백엔드·root | 등록 snapshot/실제 제공파일/audit SHA-256 일치 후 stdin 전달 | 실제 B는 지식 부족으로 자율보류. 스킬 전달 성공과 업무 완료를 구분 |

## 종합 랩 항목 전수표

| 항목 | 착수 상태 / 담당 | 기존 증거·확인 대상 | 완료에 필요한 검증 또는 차단 원인 |
|---|---|---|---|
| K1 학생 사례 구분 | 구현·최종 독립PG·실제브라우저 검증 / UI·root | k1-pg-final17 passed·18.91초; k1-live1440/1024 export1flow·1agent·1MCP | 메일 의존·URL query 비밀값 수정 포함 전체2275pass. 실제 브라우저는 마지막 두 수정 이전임을 구분. 아래 제안은 착수 이력이며 현재 계약은 student-cases.md |
| K2 학생 지도·BPMN·구성 | 실제 학생지식 상세·왕복 검증 완료 / UI·root | bpmn-io3개/오류0·구성differences=[]·k2-example load65nodes/107rels·ask9pass·최신studentdetail | root 생성 자원만 검증. 공식namespace wipe65개·cleanupremaining0. target기능7pass와healthabort전체exit1을 구분 |
| K3 회의 준비 실제 실행 | 진행 중 / root | `students/_template/example_meeting/README.md`, `K-capstone.md` | Google 인증 미확보. 결과 경로 자리 3줄과 서버 응답 계약 점검은 진행 가능; 외부 실제 완주는 인증 필요 |
| K4 PENDING 에이전트 닫기 | 실제 Sol6.1 자율보류 및 close 검증 완료 / 백엔드·root | k4-live/summary.json7 checks 모두 PASS·k4-live.log | 필수 customer 미응답 실제 trace→PENDING→close→COMPLETED/closed-by-human·agent와 미도달 Report CANCELLED. 일정 확정/업무 보고는 미실행. B incident보호 close409와 별도 |

## K1 착수 시 설계안 기록 — 이후 구현은 student-cases.md

확인한 현재 계약은 다음과 같다. `it/process/procsvc/inbox.py`는 로그인 없음과 브라우저의 「나」 선택을 명시한다. `check_actor`는 `user:*`와 역할 구성원 관계를 검사하며, 선택한 사용자 값 자체를 인증된 신원으로 보장하지 않는다. `instance_mode.py`의 tenant는 서버 환경 `TENANT_ID`로 정해진다. `agent_authoring.py`의 `origin='user'`는 기준/사용자 작성 구분이며 학생 소유권이 아니다. `config_bundle.py` 내보내기·가져오기·되돌리기는 tenant의 학생 작성 구성 전체를 다룬다.

그래프는 `students/_template/load_graph.py`에서 `ns`, 같은 값의 id 접두어, 타 이름공간 덮어쓰기 거절, 기준 노드에만 허용하는 다리 관계를 이미 검사한다. 이것도 그래프 분류·충돌 방지 계약이며 로그인 기반 접근 통제라고 부르지 않는다.

이 계약에 맞는 기본 제안은 **학생별 독립 스택 + 학생당 한 활성 사례**다. 예를 들어 학생 폴더 `students/s01/`, 그래프 `ns='s01'`, 노드 id `s01:…`, 업무 스키마 `stu_s01`을 맞춘다. 기준 그래프의 ns 없음과 seed 구성은 그대로 둔다. 포털의 「나」는 승인 역할 실습에만 쓰고, 사례 소유자를 인증하는 값으로 쓰지 않는다. 공유 서버에서 학생별 보안을 제공한다는 주장은 하지 않는다.

착수 당시 코드로 실행할 수 있던 사례 보관 절차는 학생 스택에서 진행 중 작업을 끝내고 `/api/config/export`로 그 스택의 학생 구성 전체를 내보낸 뒤, 그래프 원본·스키마·질의와 함께 사례 폴더에 보관하는 것이다. 비밀 값은 기존 자리표시자 계약을 따른다. 기존 `/api/config/import`는 전체 학생 구성을 대체하므로 다른 활성 사례와 병합하는 기능으로 소개하지 않는다. 구성 reset과 그래프 ns wipe는 대상/복원본을 확인한 해당 학생 스택에서만 수행한다. 이 운영안만 있던 착수 시점에는 「내 사례」 UI 꼬리표·필터·사례별 export가 없었다. 이후 실제 구현/검증은 상단 표와 student-cases.md를 따른다.

여러 사례를 한 학생 스택에서 관리할 때의 구체적인 후속 구현 계약은 아래처럼 제안한다. 새 소스나 마이그레이션은 이번 문서 작업에서 만들지 않는다.

| 결정점 | 제안 |
|---|---|
| 사례 식별 | `case_id='s01-meeting'`, 표시 이름 `회의 준비`, 그래프 이름공간 `ns='s01'`; 사례와 학생 ns를 별도 개념으로 유지 |
| 누가 설정 | 해당 독립 스택의 학생이 사례를 먼저 만들고 활성 사례를 고름. 자동으로 브라우저 「나」에서 owner를 유추하지 않음 |
| 언제 부착 | 신규 사용자 에이전트·스킬·MCP·흐름 생성 시 활성 case_id 저장. 처리 건은 시작한 흐름의 case_id를 스냅샷으로 상속 |
| 기존 자료 | seed는 「수업 기준」, 기존 origin=user이며 태그 없는 것은 「미분류」. 이름 유사도로 자동 이관하지 않음 |
| 목록 | 「수업 기준 / 선택 사례 / 미분류 / 전체」를 명시. 사례 필터는 분류이며 권한 경계로 설명하지 않음 |
| 참조·내보내기 | 사례가 직접 소유한 객체와 참조 목록을 함께 내보냄. 기준 객체는 참조만, 다른 사례 객체 의존은 사전 오류로 보여줌. 비밀 값은 기존 가림 계약 유지 |
| 되돌리기·삭제 | 진행 중 해당 사례 처리 건, 다른 사례의 참조가 있으면 사전 거절. 공용 객체를 연쇄 삭제하지 않음 |
| 검증 | 두 사례+seed+미분류에서 필터·export/import 왕복·다른 사례 보존·실행 중 거절·비밀값 없음·잘못된 case_id 거절을 확인 |

**아래는 착수 시 설계안의 미확정 경위다.** 이후 사용자의 통상 구현 판단 위임으로 독립 노트북의 구성 꼬리표·필터·선택 export를 구현했으며 사용자 결정 대기가 현재 중단 조건은 아니다. 공용 서버 인증·소유권 격리는 별도 범위다. 당시 검토한 결정은 한 학생 스택에 복수 사례를 동시에 둘지, 그리고 공용 서버 인증·소유권 격리까지 요구할지였다. 독립 스택/순차 배포는 최종 실라버스가 이미 허용한다. 공용 서버 소유권 격리를 선택하면 검증된 로그인 주체와 서버 측 owner 강제, 모든 조회·쓰기·되돌리기·내보내기 경로의 권한 검사가 먼저 필요하므로 현재 「나」 선택만으로 구현됐다고 간주할 수 없다. 이 결정 대기와 무관하게 다른 UI·기능 검증은 계속 진행한다.

## 결과 수신 후 갱신

위 추가 증거 경로의 루트는 `D:/work/study/hyd-iot-edu/.evidence/overnight-20261012/`다. 문서 담당도 fresh-migrations 마지막 51행, Neo4j 13 passed 로그, full seed exit 0 로그를 직접 읽었다. 세부 실행·캡처 판정은 메인 확인 결과로 구분한다. 학생 MCP 8311 health는 root가 `schema=stu_s00`, `session_read_only=on`을 확인했다. UI 참고 process-gpt-vue3 원격 HEAD는 `867e8cf944b265a3383e442a48710ff66e1ab3c9`로 기존과 같다.

학생 실행 단계별 결과는 `student-probe.md`를 따른다. student-live/student-codex 실패·student-codex-stdin18개 성공·후속 student-release18개 성공을 별도 실행으로 보존한다. 최종 코드 전체 수치와 상세 캡처 상태는 이 문서 상단 표가 기준이다.

실제 캡처 원본·Dify 비교·ProcessGPT 비교와 U16/K2 잔여는 `capture-review.md`에 모은다. 각 성공 주장에는 로그/JSON/PNG와 실제 DB/LLM 여부를 연결한다. 현재 `D:/work/작업보고/2026-10-12.md`는 진행 보고이며 서비스 정리는 확인했다. 코드 반영 해시는 git log와 최종 보고를 참조한다.

HM-8 원문·실제 제안의 식별자/승인 역할 충돌, 구조화 evidence4개 및 제한 규칙의 미등록, FAN 작업지시 추론·회복 성공 단계 누락은 `manual-review-packet.md`에 준비했다. 사람이 검토한 기록이나 적재 완료로 간주하지 않는다.

PM-02·PR-07 실제 Sol 추출 제안도 생성됐다. 첫 PR-07은 제품 지시의 범위 결함으로 procedures=[]를 반환했다. 신규2.4의 실제 Sol 재추출에서6절차21단계를 확인했고 기존2.3 정의 불변을 확인했다. 전체3건 제안 생성은 F3 사람 검토/적재 완료를 뜻하지 않는다.

## 메인 생성 자원 정리와 보존된 증거

`cleanup-owned.log/results.json`은 own manifests로 확인한 대상에만 38개 공식 API 요청을 수행했고 모두 성공했다(이미 없는 404 허용). 흐름 11대상(이미 삭제 포함)·에이전트 5·MCP 5를 정리했으며 질문 목록도 모두 이번 작업 소유임을 확인한 후 reset했다. 기존 학생 자료의 전체 구성 reset이나 DB 수동 삭제는 수행하지 않았다. 실제 student-release/K1/K4의 API 원문·로그·PNG는 증거로 보존하지만 생성 자산과 질문은 현재 제품 목록에 더 이상 남아 있지 않다.

처음 실패한 HM-8 추출5317d3aa…도 공식 close로 COMPLETED/closed-by-human을 확인했다(`failed-extraction-close.json`). 실제 B의 열린 incident/PENDING은 보존한다. 이 문장의 작성 당시에는 서비스 종료 확인 전이었다. 이후 최종 정리를 아래 근거로 확인했다.

health의 CDP 진단은 `cdp-health-probe/result.json`·events.json·errors.json에 보존한다. raw ERR_ABORTED가 남은 전체 캡처 summary passed=false/exit1은 지우거나 성공으로 고치지 않았다. 기능 7개 pass와 health 12/12 진단을 별도로 기록한다.

## 후속 F20·F21 코드 검증

F20은 구매 SOP 제외를 사용자 판단 대기가 아닌 제품 추출 지시 결함으로 확정해 신규2.4에서 수정했다. 실제 `extraction24-live-proof.json`은 COMPLETED/2.4·previous_definition_unchanged=true·procedures6을 확인한다. 새 PR-07은 절7·절차6·단계21·warnings14·rules7이며 실제 Sol 실행224.5초다. 원문 PUR-11/12/13 각5단계와 추가 정책/검증3절차를 구분한다. 고장 유형 연결·공급사 고정·검사비 단위·발주/입고 연결 쟁점 및 사람 검토/적재 전 상태는 manual-review-packet.md를 따른다. 첫2.3 절차0 및 최초2.4 준비 전 GET 실패도 보존했다.

F21은 내부 ExecutionProjection·CaseProjection·KnowledgeEdit·ManualIngestionDocument·ManualIngestionBatch가 지식 지도에 포함된 제품 query 누락을 수정했다. 스키마·DB 기록을 삭제하거나 Process 이름을 임의 번역한 변경이 아니다. 기존 업무 사례/원문/학생 항목과 관계를 유지한 독립Neo4j/API 회귀45pass·3skip·4warnings(5.52초)를 확인했고 운영 agent 재시작 후 실제 API1592→636 및최신6화면을검증했다. 내부5종DB저장수는420/428/50/27/31로불변이며사례/원문지식이유지된다. 전역2275 수치에 이 후속 코드까지 소급하지 않는다.

## F21 운영 배포와 최종6화면 확정

`f21-before.json`→`f21-after.json`에서 실제 그래프 API 노드는1592→636이다. 내부5종956개를조회에서제외했으며DB저장수ExecutionProjection420·CaseProjection428·KnowledgeEdit50·ManualIngestionDocument27·ManualIngestionBatch31은전후동일하다. Incident187·DecisionCase99·ManualSection18·KnowledgeSource7도유지했다. 내부기록을삭제하거나사례/출처지식을가린것이아니다.

첫검사helper는Docker DNSneo4j:7687을호스트에서사용해실패했고명시localhost7687로고쳤다. before의label_counts={}는실제응답label키를labels로잘못읽은검사문제이며원본을보존했다. after에서는실제label필드와업무지식존재assert로검사했다. helper실패를운영배포성공으로대체하지않으며노드수/DB수보존과최종label확인을각각근거로쓴다.

`ui-f21-final`은ontology/flows/agents의1440/1024 총6화면,exit0다. console/pageerror0·ignored0·문서폭=viewport를확인했다. ontology/flows의residue는0이고agents의기존작성명read_only1건은원문을유지했다. ontologySVG경계초과12개는남아있고문서높이는10731/10804px다. 이6화면은F21/이름표시최신검증이며이전46화면전체를동일시점재캡처했다고주장하지않는다. 전체국문화·사용자시각승인은별도다. SVG경계값은후속실제스크롤검증으로접근가능함을확인했다.

## SVG 내부 스크롤 실제 접근 검증

`ontology-scroll-probe/result.json`과 rightmost-selected-1440/1024.png에서 의도된 지도 내부 스크롤을 확인했다. 실제1440/1024 폭의 지도는1111/711px·scrollWidth1354px·overflowX/Y=auto·maxHeight648px이며 일반 DOM의 documentHeight는900px다. 약10k 캡처 높이는 UNLOCK_CSS로 내부 스크롤을 펼친 결과다.

두 폭 모두 오른쪽 외기 온도 노드까지 가로 이동한 뒤 클릭해 상세 제목·aria-selected=true·nodeFullyWithinMap=true를 확인했다. Enter로 선택 해제도 통과했다. role=region·tabIndex0·가로/세로 이동 안내 ariaLabel이 있다. 이 probe는 pageerror만 감시했고 오류0이었다. console0은 별도 ui-f21-final의 증거이며 이 probe가 console listener까지 가졌다고 쓰지 않는다.

SVG 경계 초과12개는 접근 불가한 잘림의 증거가 아니며 의도된 스크롤 영역의 경계값이다. 전체 지도 PNG와 실제 상호작용 가능성을 구분하고 사용자 시각 판정은 별도로 남긴다.

## 최종 서비스 정리 — 02:53 KST 확인

`services-off.json`은 runningContainers=[]·listeners=[]이고 `cleanup-final.json`은 Docker Desktop/backend 프로세스0·liveLockExists=false다. compose·독립 Neo4j·학생 MCP8311·두 Supabase를 종료했고 Supabase는 backup=true로 데이터를 보존했다. 볼륨 및 작업 트리를 삭제하지 않았다. 본인 LIVE_LOCK의 내용을 보관한 뒤 해제했다.

독립 Supabase 첫 종료는 PATH에 docker가 빠져 실패했고 PATH 보완 후 재실행했다. main Supabase 첫 --workdir it/supabase는 project_id_filter=supabase로 대상이 달랐으며 Docker 실측 후 --workdir it로 hyd-iot-edu를 종료했다. 실패/재시도 원본 로그를 보존한다.

종료 전 `final-scenario-state.json`의 실제 B는 RUNNING1/에이전트 PENDING이며 열린 incident와 함께 보존했다. 실제 시나리오 완주나 지식 부족 해소를 주장하지 않는다. 코드 반영 해시는 git log와 최종 보고를 참조한다.
