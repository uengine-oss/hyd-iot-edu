# K1 · 독립 노트북 내 사례

## 계약과 범위

NOW K1, K-capstone.md, capstone-lab.md §5.2 G6을 읽었다. G6의 사례는 처리 건이 아니라 학생이 만든 흐름·에이전트·MCP·스킬을 묶는 구성이다. 최신 사용자의 자율 구현 지시에 따라 꼬리표 입력 위치와 모양을 정했다. 기존 ‘사용자 결정 필요’는 이 구현의 중단 조건이 아니다.

포털 관리 화면의 ‘내 사례 · 출발본…’ 펼침에서 해당 자산에 사례 이름 하나를 붙인다. 1~60자, 앞뒤 공백 제거, NFC 정규화, 제어 문자 거절. 빈 이름 저장은 꼬리표만 제거한다. 사례 목록 필터와 사례 파일 받기를 같은 화면에 둔다. 기준 자산에는 붙일 수 없다. 공용 서버 학생 인증·소유권·tenant 의미는 추가하지 않았다.

정본은 `hyd_student_case_tags(tenant_id,kind,asset_id,label)`이다. migration `20261012000052_student_case_tags.sql`을 추가했으며 실제 스택 적용은 메인이 맡는다. anon/authenticated 직접 접근은 열지 않는다. MemoryRepo와 PostgreSQL을 지원하고 테넌트 삭제 시 cascade한다.

## 보존과 내보내기

- `GET /api/config/cases`: 학생 구성의 표시 이름·종류·꼬리표와 사례 목록.
- `PUT /api/config/cases/tag`: `{kind,asset_id,label}`. 기존 사용자 자산인지 확인하며 구성 가져오기·되돌리기와 같은 잠금을 사용한다.
- `GET /api/config/export?case=<사례 이름>`: 기존 출발본 형식을 유지한다. 해당 사례 자산과 그 자산이 참조하는 학생 에이전트·스킬·서버를 함께 담는다. 고른 흐름의 단계 배정·배포·역할 분장을 보존한다. 기준 흐름 운영 판본 변경은 사례 범위에 포함하지 않는다. 도구 제한이 없는 에이전트는 등록 학생 서버 전부가 의존성이며 함께 담은 이름과 개수를 표시한다.
- 기존 전체 내보내기도 `case_tags`를 보존한다. 이전 파일에 이 칸이 없으면 꼬리표 없는 출발본으로 읽는다. 가져오기 전 꼬리표 대상/중복/형식을 검증하고, 적용 뒤 실제 태그와 대조한다. 가져오기 실패 시 원래 구성과 꼬리표를 되돌린다. 비밀값 마스킹을 새로 구현하지 않고 기존 내보내기 경로를 쓴다.
- 자산 단독 삭제와 각 되돌리기에서 꼬리표를 정리한다. 이름을 재사용한 새 자산이 이전 꼬리표를 물려받지 않는다. 구성 파일은 실행 이력 내보내기가 아니다. 사례 파일을 불러오는 동작도 기존처럼 현재 학생 구성 전체를 되돌리고 그 파일로 복원하며 병합 가져오기가 아니다.

## 참고와 UI

앞선 포털 작업에서 확인한 ProcessGPT 최신 Vue HEAD `867e8cf944b265a3383e442a48710ff66e1ab3c9`의 실제 PgField/PgAlert/PgCard와 WorkItem/InstanceOutput, ProcessGPT 모노레포 및 ontology-studio를 참고했다. HYD는 독립 노트북 수업 출발본이라는 목적이므로 별도 소유권 기능 대신 구성 묶음만 추가했다. 기존 카드·입력·메시지 컴포넌트를 사용한다. 내부 식별자는 API/파일에서 그대로 보존하지만 목록은 이름·한글 종류를 표시한다.

## 검증 중 기록

- 기존 B6 전체 내보내기·가져오기: 30 passed/1 skipped, 24.59초. 독립 PostgreSQL DSN 미지정 skip.
- K1 독립 API: 9 passed/1 skipped, 3.64초. 유효하지 않은 꼬리표 보존·기준 보호·테넌트 분리·의존성/비밀값/실제 가져오기 왕복·실패 rollback·네 종류 단독 삭제 및 이름 재사용 확인. 추가 PG 시험은 새 저장소 연결에서 지속성과 실패 원자성을 검사하며 별도 버릴 DB DSN이 필요하다.
- K1 Chromium: 2 passed, 4.73초. 실제 생산 shell/CSS와 실제 FastAPI로 태그 저장 실패 입력 보존→저장→재마운트→사례 필터→파일 실제 다운로드 및 JSON 대조→태그 제거를 수행했다. 초기 시험은 관리 화면을 잘못된 탭 이름으로 열어 hidden 요소 timeout 두 건이 발생했다. 실제 admin 탭과 구성 펼침을 여는 동선으로 고쳤으며 기대값/timeout은 완화하지 않았다.
- 캡처는 루트 `.evidence/overnight-20261012/k1/student-case-{1440,1024}.png`. 실제 외부 서비스·LLM 실행 기록이 아닌 독립 API/브라우저 검증이다.
- 최종 새 가상환경 관련 묶음: `python -m pytest tests/test_student_cases.py tests/test_student_cases_ui.py tests/test_b6_config_bundle.py tests/test_b1_agent_authoring.py tests/test_b2_mcp_registry.py tests/test_backend_remaining.py tests/test_portal_remaining_ui.py tests/test_portal_approval_ui.py tests/test_portal_flows_ui.py -q -n 4 --tb=short` → **126 passed, 4 skipped, 46.00초, exit 0**. skip은 지정하지 않은 독립 PG DSN들이다. 로그 `.evidence/overnight-20261012/k1/pytest-k1-related.log`.
- 두 새 JS는 `node --check` 통과, `git diff --check` 오류 없음. 최신 캡처에서 관리 탭·전체 제품 CSS·한글 이름·선택 사례 파일 받기 상태를 직접 확인했다.

## 메인 실제 검증 순서

1. 본 migration을 버릴 DB 또는 승인된 현행 DB에 적용한 뒤 process를 새 코드로 재빌드한다. 기존 회귀나 학생 실행 중에는 재시작하지 않는다.
2. 독립 DB 주소를 `HYD_BACKEND_PG_DSN`으로 지정하고 `python -m pytest tests/test_student_cases.py -q`로 PG 저장 원자성과 별도 연결 지속성 확인. 실제 자산 생성/삭제는 이 시험의 MemoryRepo에서만 하며 PG 시험은 고유 시험 tenant 생성·정리만 한다.
3. 관리 → ‘내 사례 · 출발본…’ → 학생 자산에 이름 저장 → 사례 필터 → ‘이 사례 파일 받기’. 다운로드 JSON의 case_tags, 의존성, 원문 BPMN/정의, 비밀값 마스킹을 확인한다.
4. 실제 학생 자료의 되돌리기/가져오기는 메인의 범위·잠금 판단 아래 수행한다. API 독립 시험의 성공을 실제 스택 적용/실제 학생 완주로 보고하지 않는다.

## 실제 PostgreSQL·독립 검토에서 찾은 결함과 수정

- 메인의 독립 PostgreSQL 실행에서 replace 원자성 시험이 실패했다. PgRepo 연결은 autocommit=True인데 연결 context만 사용하여 두 번째 INSERT 실패 뒤 첫 번째 값이 남았다. `Store.replace`에 명시적 `c.transaction()`을 추가했다. 기존 기대값을 유지한 메인 재실행은 **1 passed, 1.13초**(`k1-pg-fixed`). 최초 실패 `k1-pg.log/xml`도 보존한다.
- Sol 독립 검토는 전 문자열을 참조로 읽던 선택 내보내기가 설명문·persona 등에 우연히 같은 이름이 있을 때 다른 사례를 포함함을 발견했다. 전 문자열 탐색을 없애고 schema의 task.agent/tools/skills, config/service.server, 단계 배정 agent_id, agent.tools/skills만 추적한다. 설명·지시문·이름·식별자·도구 인자에 같은 문자열을 넣은 음성 회귀와 실제 server 칸을 선언했을 때 포함되는 양성 회귀를 추가했다. 수정 후 K1 API/브라우저 **12 passed/1 skipped, 7.26초**.
- 메인 통보 기준 실제 스택 K1 Chromium은 태그 저장→필터→다운로드 원문(흐름1·에이전트1·서버1) 대조→태그 제거가 통과했다. console0, 1440/1024px 수평 넘침0. 근거 `.evidence/overnight-20261012/k1-live/`의 PNG·student-case.json·checks.json. 메인의 실제 PostgreSQL migration52 적용/이미지 재빌드 뒤 검증이며, 이 작성 에이전트가 라이브 API를 조작한 것은 아니다.

## U10 상단 도구 표시 후속

실제 화면에서 상단 최근 도구 이벤트가 학생 서버 내부 이름을 표시함을 확인했다. 새 `toolNames.js`는 기존 `/api/agent-authoring/options`와 `/api/mcp/selectable`의 저장된 서버 설명 및 도구 title/description을 읽는다. 실제 도구 연결·목록 탐색·도구 실행을 추가하지 않는다. 확인된 한글 표시 이름을 사용하고 표준 `UI.toolName` 번역은 보존한다.

표시 이름이 없으면 ‘도구 실행 중’으로 표시하고 펼침에 원문 식별자와 이름 미확인 사유를 둔다. metadata 요청 실패는 ‘실제 도구 실행 결과와는 별개’로 명시한다. 실제 tool 종료/실패 이벤트는 별도 상태를 표시한다. 뒤늦게 도착한 이름 응답이 더 최신 이벤트를 덮지 않는다.

`tests/test_tool_names_ui.py` 3개 Chromium 시험이 **3 passed, 4.24초**. 처음 EventSource 시험 대역의 class 대입식을 Playwright가 callable로 실행하여 3개 실패했고, 함수로 감싸는 harness 수정 뒤 통과했다. 제품 조건이나 기대값은 완화하지 않았다. 표준 번역, 저장된 이름, 내부 ID의 기본 표시 제외와 펼침 원문, metadata 실패와 실제 실패 구분, 늦은 응답 오염 방지를 검증한다. `tool-display-{1440,1024}.png`를 직접 확인했고 수평 넘침은 없다. 생산 CSS와 header/event renderer를 사용한 독립 화면이며 본문 홈 기능을 모두 기동한 실제 스택 캡처는 아니다.

모든 후속 수정 뒤 새 가상환경에서 `tests/test_student_cases.py tests/test_student_cases_ui.py tests/test_tool_names_ui.py -q --tb=short` → **15 passed, 1 skipped, 11.26초, exit 0**. 이 실행의 PG DSN은 미지정이라 1skip이며 실제 PG 결과는 위 메인 실행과 구분한다. 최종 로그 `k1/pytest-k1-tool-final.log`.

## 선택 내보내기·URL 비밀값 추가 회귀

독립 검토에서 작업지시·구매 처리의 `config.mail.server` 및 컴파일된 `service.mail.server`가 의존성에서 빠짐을 발견했다. 해당 선언 필드만 추적에 추가했다. 도구 인자 속 같은 이름은 여전히 연결로 취급하지 않는다. 초안 매핑과 등록된 정의 각각에 대한 회귀가 포함 여부를 검사한다.

HTTP MCP 주소의 쿼리 비밀값이 전체·선택 내보내기에 그대로 포함되는 결함도 수정했다. 기존 비밀 키 판정을 적용하여 해당 값만 `${HYD_SECRET:url.query.순번}`으로 치환한다. 일반 매개변수의 원문·순서·빈 값은 유지하고 반복 비밀 키는 서로 다른 입력 칸을 갖는다. 가져오기는 누락 시 기존 `needs_secrets` 오류로 아무것도 바꾸지 않으며, 입력한 비밀값을 URL 인코딩해서 복원한다. 내부 실패 복원용 `include_secrets=True` 원본은 유지한다.

실제 로컬 시험 HTTP MCP를 등록하여 canary 비노출, 두 export 경로, 특수문자·한글 비밀값의 복원, 입력 누락 시 422와 기존 상태 보존, 공식 import 뒤 verified 대조를 검사했다. 새 fixture의 저장 메서드 이름 오류 1건을 실제 `upsert_proc_def` 계약으로 바로잡았다. 이후 새 가상환경 `python -m pytest -q tests/test_student_cases.py tests/test_b6_config_bundle.py -p no:cacheprovider` → **43 passed, 2 skipped, 37.88초, exit 0**. 2skip은 독립 PG DSN 미지정이다. 이 결과는 앞선 실제 스택 K1 캡처 이후 코드에 대한 독립 시험이며 추가 라이브 재빌드 결과를 뜻하지 않는다.

## 메인 최종 소스·실제 PG 확정 결과

K1 메일 의존 및 URL query 비밀값 두 수정 후 독립 PG DSN을 지정한 메인 검사 `k1-pg-final.log/xml`은 **17 passed,18.91초**다. 전체 확정 소스 `pytest-final-source.log/xml`은 **2275 passed·21 skipped·64 warnings,195.06초**이며 두 수정이 포함됐다. 이 문서 담당도 두 로그의 마지막 줄을 직접 읽었다.

앞선 `k1-live/checks.json`의 실제 스택 태그 저장/필터/파일 다운로드/제거,1 flow·1 agent·1 MCP export 및1440/1024 PNG는 검증 시점 그대로 보존한다. 마지막 두 수정 전 캡처를 이후 코드에 대한 실제 재실행이라고 주장하지 않는다. 구성 꼬리표는 학생 로그인·소유권 인증과 다르며 전체 학생 구성 교체 방식의 import 계약은 유지한다.
