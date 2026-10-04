# 업무 DB 원천 메타데이터와 DDL 적재

`hyd-enterprise` MCP의 `describe_catalog`는 현재 연결된 PostgreSQL의 `ent` 메타데이터를 읽는다. 응답 `document`에는 실제 database 이름, schema, relation 이름/kind, 컬럼의 SQL 타입·정밀도·nullable·default·identity/generated·주석과 선언된 PK/UNIQUE/FK/CHECK/EXCLUDE 제약이 있다. `kind`는 일반 테이블 r, 파티션 테이블 p, 뷰 v, 구체화 뷰 m, 외부 테이블 f를 구분한다. 없는 주석은 null이다. 테이블 이름으로 업무 의미를 만들어 채우지 않는다.

전용 `hyd_enterprise_reader`가 SELECT할 수 있는 테이블/뷰만 나온다. 추가 원천은 해당 계정의 SELECT/RLS 정책부터 준비한다. 이 조회는 DB 관리 권한을 추가하거나 SQL guard의 ent/읽기 전용 범위를 확대하지 않는다. 연결 오류는 `result:error, error_kind:UNKNOWN`이며, 성공한 빈 `relations`와 다르다.

`describe_schema`는 같은 현재 메타데이터를 인용 식별자가 있는 DDL 문자열로 제공한다. 테이블·컬럼 주석은 `COMMENT ON`으로 보존하며, 뷰/외부 테이블을 CREATE TABLE로 위장하지 않는다. 이는 **조회와 테이블 인제스천에 필요한 스냅샷**이다. 인덱스, 권한/RLS, 파티션 경계, 뷰 정의, 사용자 정의 타입의 CREATE문, 데이터까지 복원하는 백업이 아니다. 제약 문자열이 보인다는 사실만으로 HYD가 그 관계의 업무 의미를 추론·검증한 것은 아니다.

## 원천 변경을 반영하는 순서

1. 새 업무 조건을 조회하기 전 `describe_catalog` 또는 `describe_schema`로 실제 표·열·단위/설명·관계를 확인한다. 값은 별도 `query` SELECT로 읽는다. 소스 주석이 없는 경우 불확실성을 유지한다.
2. DDL을 `/api/kg/ddl/preview`에 `text`, `filename`, `selection`, `systems`, `datasource`, `catalog`와 함께 보낸다. 원천 연결·물리 표/열·업무 시스템 선택을 검토한다. API의 업무 시스템 힌트는 확인할 후보이며 물리 식별자와 별개다.
3. 미리보기의 배치를 `/api/kg/ddl/commit`으로 적재한다. 동일 배치의 재요청은 그래프에 저장된 영수증을 돌려준다. 응답 유실 시 새 배치를 추정 생성하기 전에 기존 배치를 재확인한다. 목록 `/api/kg/ingests`는 그래프의 영속 이력이다.
4. InputData의 물리 식별자와 variable을 사용해 Rule TESTS 또는 `/api/kg/rules/sql`의 tests를 연결한다. 반환된 매개변수 SQL은 지정 원천의 읽기 연결에서 실행한다. 생성된 SQL 문자열만으로 조건 충족을 주장하지 않는다.
5. DB 주석/DDL이 바뀌면 다시 조회·미리보기·검토 후 새 배치로 적재한다. 물리 원천이 같으면 InputData ID는 유지되고 새 이름/설명이 기록된다. 최신 배치를 `/api/kg/ingests/{batch}` DELETE로 되돌리면 이전 소유 상태가 복원된다. 다른 작성자의 변경과 충돌하면 검토해야 하며 강제 삭제하지 않는다.

`COMMENT ON TABLE/COLUMN`의 문자열·줄바꿈·따옴표·IS NULL 제거를 파싱한다. 입력 이름을 주석의 첫 괄호 앞에서 잘라 단위나 조건을 잃지 않는다. 미리보기에서 선택한 컬럼의 원문 주석 전체가 InputData 이름에 들어간다. 테이블 CREATE가 없는 다른 객체의 COMMENT문은 이 테이블 적재 대상이 아니다. 업로드 SQL은 실행하지 않는다.

## 검증과 범위

### 물리 InputData의 현재 값과 승인 재검사 (A068)

`t3_inputs`와 DMN MCP `inputs`는 저장된 datasource/catalog/schema/table/column/assetColumn/sqlType을 전달한다. 판단과 승인 재검사는 `hyd-enterprise`의 `ent` 원천을 `ENTERPRISE_READ_DSN`에 등록된 전용 `hyd_enterprise_reader`로 읽는다. agent와 dmn-mcp에 같은 연결을 설정한다. 물리 입력에 파이프라인의 과거 값이 있어도 현재 DB를 다시 읽는다. 표·열은 식별자로 인용하고 설비 값은 매개변수로 전달한다.

현재 지원 계약은 명시한 assetColumn에 해당 설비의 행이 정확히 하나 있는 단일 컬럼이다. 0행·2행 이상·NULL·등록되지 않은 원천·DB 이름 불일치·출처 누락·조회 오류는 미확인이다. 같은 변수에 여러 입력/출처가 연결되어도 선택하지 않고 미확인으로 남긴다. 문자열을 숫자나 불리언으로 추측 변환하지 않으며 현재 DB 값의 타입과 typeRef가 다르면 미확인이다. 숫자 정밀도는 전달 문자열에 보존한다. 기존 규칙의 수치 비교는 float 기반이므로 임의 정밀도 수학을 보증하지 않는다.

선택한 카드의 후보/준수/순위 규칙이 참조하는 물리 입력은 값과 출처·설명을 승인 근거에 포함한다. 같은 숫자라도 컬럼이나 설명이 바뀌면 기존 카드로 승인하지 않고 새 판단 검토를 요구한다. 이 검사는 조치 실행 권한을 직접 부여하지 않는다. 사람이 process의 정상 선택 경로에서 승인한 뒤 기존 명령 경로가 진행된다.

자동 조인·집계·단위 변환·업무 용어 확정이나 LLM 질의 생성을 대체하는 기능은 아니다. 여러 주문 중 어떤 행을 쓸지 같은 업무 선택은 명시적으로 모델링해야 한다. 기존 의미 변수의 RPC 조회와 enterprise MCP의 SQL 생성/조회 경로도 별도로 유지한다. DB 값·온톨로지·PLC 사이의 분산 트랜잭션을 제공하는 것은 아니며 명령 직전 재검사를 계속 사용한다.

`scripts/probe_physical_facts.py --out <새 증거 폴더>`는 실제 PG의 고유 시험 컬럼을 HTTP로 적재하고 실제 Neo4j 규칙과 연결한 후 배포 DMN MCP·agent 승인 재검사를 확인한다. 명령·사건 제출 없이 시험 원천과 규칙만 사용한다. 최종 실제14항목은 `.evidence/reaudit/a068-live-final/`에 있다. 직접 시험 변경한 InputData 속성을 원래 적재 계약으로 복원한 뒤 정상 배치 삭제 API로 정리한다. 처음 검사의 잘못된 ManualSection 라벨과 보호 검사 409, 정확한 배치 복구는 `a068-live-first/`에 보존한다.

A067의 `scripts/probe_enterprise_catalog.py --out <새 증거 폴더>`는 고유한 시험 테이블/뷰만 생성한다. 실제 PG → 배포된 HTTP MCP → DDL 파싱 → 배포된 process preview/commit → Neo4j 물리 출처 → 규칙 SQL 실제 조회 → 주석 변경 재적재/배치 재요청/두 단계 되돌리기의 **18항목**을 확인했다. 시험 DB 객체와 소유 InputData는 정리됐고 IngestionBatch의 영수증은 남는다. 결과는 `.evidence/reaudit/a067-live-verified/`다. 실제 Codex의 새 SQL 생성·의미 해석과 직접 UI 조작은 이 검사에 포함하지 않는다.

실패 원본도 보존한다. 기존 describe_schema는 따옴표가 필요한 식별자를 잘못 출력했고 정밀도/주석/키 관계가 빠졌다. 수정 후 HTTP 적재에서 발견한 `uploads` NameError는 그래프 커밋 뒤 500을 반환했다. 해당 실제 배치를 조회·정상 되돌린 기록은 `a067-live-final/after-500-*.json`이다. 현재 적재 이력은 기존 그래프 원장을 사용한다.

근거: 회의2 253~302행, robo-data-catalog `cf41148d`의 `contracts/schema.py`·`api/schema.py`·`graph/schema_queries.py`(물리/논리 설명·원천/소유 경계), process-gpt-glossary 고정 스냅샷의 `glossary_manage_service.py`258~310(실제 PostgreSQL 용어 저장), [PostgreSQL 15 메타데이터 함수](https://www.postgresql.org/docs/15/functions-info.html). T06 API 주석은 Neo4j를 언급하지만 이 저장 구현은 PostgreSQL이다. 제품의 용어 상태 값이 존재한다는 이유로 검토 권한이나 자동 의미 연결까지 구현됐다고 보지 않는다. HYD는 참고 제품의 전체 glossary/catalog를 이식하지 않았다.
