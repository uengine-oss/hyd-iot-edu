# 센서 메타데이터와 생성 질의

센서 원천은 TimescaleDB다. 현재 Prometheus는 서비스 상태와 detector가 내보내는 최신 TS1 온도·이상점수를 수집한다. 팬 진동(VS1) 지표는 현재 exporter에 없으므로 임의로 지표명을 만들면 안 된다. `mcp_prom.freshness`는 PromQL 실행기가 아니라 TimescaleDB 최신값과 수집기 health를 확인하는 함수다.

hyd-dmn MCP의 `timeseries_schema()`로 실제 public.tag_1s/feat_1s/tag_1m 열·타입과 최근5분에 관측된 설비·태그 목록을 읽는다. 목록은200개까지이며 초과 여부를 반환한다. 최근에 관측되지 않았다고 센서가 없다고 단정하지 않는다. 단위·업무 의미와 규칙은 `inputs`/`dmn_rules` 및 온톨로지 관계를 함께 읽는다.

에이전트가 만든 PostgreSQL SELECT는 `timeseries_query(sql)`에 전달한다. 결과에는 실제 실행 SQL, 원천명, 열·행·행 수가 있다. 최대200행에 도달했는지도 표시한다. `time_bucket`, 집계, CTE와 window 함수를 사용할 수 있다. tag_1m은 지연된1분 집계이므로 원시 지속 시간 판정을 대신하지 않는다. 기존 Evidence SQL도 같은 AST 검사와 전용 읽기 연결을 사용하며 `%(asset)s` 매개변수를 보존한다.

“최근30초 동안 진동이 임계값을 넘었다”는 조건을 관측값 평균만으로 판정하지 않는다. 생성 질의는 관측 수, 첫/마지막 시각, 최대 관측 간격, 최신값 나이와 임계값 검사를 함께 반환해야 한다. 허용 간격·신선도·필요 구간은 해당 규칙에서 정한다. DAQ의 lite 모드는 변화 보고이므로 행 수만으로 연속 관측 시간을 추정하지 않는다. A051의 질의 검사는 이 정보를 조회한 것이며 보편적인 지속 시간 판정기를 구현한 것은 아니다.

정상 조회의0행, SQL 형식/없는 열 등의 `INVALID`, 연결/실행 시간 초과 등의 `UNKNOWN`을 구분한다. 오류를 조건 false나 관측0으로 변환하지 않는다. 원천 밖 표, 쓰기, 미허용 함수는 실행 전에 거절한다. AST 검사는 DB 권한을 대신하지 않는다.

기존 Evidence의 스칼라 비교도 A053부터 `status=PASS|FAIL|UNKNOWN`, `passed=true|false|null`로 구분한다. NULL/빈값은 `reason=NO_DATA`, 질의 실패는 `reason=QUERY_ERROR`와 error_kind/error를 보존한다. 단일 유한 수치만 비교하며 반올림은 표시 단계에서만 한다. 미확인 대안이 있으면 원인 순위를 확정하지 않고, 전부 조건 불일치라면 `UNSUPPORTED`로 보류한다. MCP diagnose는 `withheld=true`와 근거를 반환하고 레거시/수동 판단은 후속 추천을 중단한다. 수동 API의 근거 미충족은409, 원천 연결 실패는503이다. 원천/규칙을 고친 뒤 재조회하며 근거가 없을 때 원인을 임의 선택하지 않는다. 이는 평균값 SQL의 구간 누락을 자동 검증한다는 뜻은 아니다.

DB 계정은 `hyd_timeseries_reader`다. 센서3표 SELECT만 부여하고 읽기 전용 세션·5초 statement timeout을 적용한다. compose의 agent/dmn-mcp는 `TSDB_READ_DSN`을 `TSDB_DSN`으로 전달한다. 쓰기 서비스의 PG_DSN으로 자동 대체하지 않는다. 새 DB 초기화에는 `it/timescaledb/reader.sql`이 포함된다. 기존 DB에는 reset 없이 다음을 적용한 뒤 agent/dmn-mcp를 갱신한다.

```powershell
Get-Content -Raw it/timescaledb/reader.sql | docker compose exec -T timescaledb psql -U hyd -d hyd -v ON_ERROR_STOP=1
```

실제 검증 A051: 전체743, 실제 TimescaleDB13, 가동 MCP9. 조건 변경·빈 결과·잘못된 열·원천 밖/쓰기 거절·연결 실패·Timescale 집계·기존 Evidence 진단·기업 SQL 복합조건을 확인했다. 질의는 검사기가 작성했으며 새 Codex 생성 검증은 아니다.

## Prometheus 메타데이터와 PromQL

hyd-dmn의 `prometheus_metadata(metric?)`로 실제 HELP/type/unit을 받고 `prometheus_series(selector, start?, end?)`로 레이블 집합을 확인한다. metadata 목록은200개까지이며 `truncated`를 확인한다. 이름은 정확히 지정할 수 있다. 자동 생성 지표 `up` 등은 metadata에 없어도 series에 있으므로 빈 metadata로 부재를 단정하지 않는다. series는 기본 최근5분 또는 Unix초 start/end의 최대24시간 구간이다. 등록된 series만으로 실제 관측 유무를 판정하지 않는다.

`prometheus_query(expression, at?)`는 단일 시점, `prometheus_query(expression, start, end, step)`는 구간 질의다. 시각·간격은 초 단위 숫자다. 구간은24시간/시리즈당1100평가시점 이내, 응답은200시리즈/20000점/2MB 이내이며 초과 시 부분 성공으로 자르지 않고 질의를 좁히도록 오류를 반환한다. PromQL 자체 lookback 기간을24시간으로 제한한다는 뜻은 아니다. 서버 실행 timeout은5초, HTTP timeout은8초다. 현재 배포2.55.1의 API를 사용하며 신버전 `limit` 매개변수 지원을 가정하지 않는다. [공식 HTTP API](https://prometheus.io/docs/prometheus/latest/querying/api/)의 query/query_range/series/metadata 응답을 보존한다.

응답의 `data.resultType`과 `data.result`를 함께 읽는다. 빈 벡터와 값0, NaN/Inf 문자열은 다른 결과다. Prometheus의 warnings/infos도 보존한다. 문법·실행 불가 질의는 `INVALID`, 연결/시간초과/원천 이상은 `UNKNOWN`이다. Prometheus 서버가 꺼져도 TSDB freshness로 조용히 대체하지 않는다.

`up`은 수집 성공 여부이고 `time()-timestamp(up)`은 scrape 관측 나이다. detector_ts1은 마지막 이벤트 값을 반복 노출할 수 있으므로 최근 scrape가 센서 원천의 최근 관측을 증명하지 않는다. 센서의 지속 조건에는 TimescaleDB 원천 시각/누락/DAQ 정책을 함께 확인해야 한다. 구간 query의 평가시각도 원천 관측시각을 대신하지 않는다.

기동: compose의 기존 프로필을 포함한 `COMPOSE_PROFILES`에 `monitor,cliagents`를 추가하고 `docker compose up -d --no-deps prometheus dmn-mcp`를 실행한다. 코드를 바꿨으면 dmn-mcp를 먼저 빌드한다. 별도 새 서버 URL이 필요하면 compose의 dmn-mcp `PROMETHEUS_URL`을 배포 설정으로 바꾼다. 사용자가 도구 인수로 임의 URL이나 쓰기 경로를 전달할 수 없다.

A052의 실제 MCP17항목과 원천 중지→UNKNOWN→재시작 복구를 확인했다(`scripts/probe_prometheus_mcp.py --outage`). 메타데이터에서 발견한 지표·레이블로 조건을 구성해 같은 시점의 임계값 변경을 검증했다. 새 Codex 질의 생성이나 보편적 지속조건 판정 완료를 뜻하지 않는다.

## CEP의 관측 시간과 공백

A054 감지기는 입력별 event timestamp/quality를 확인한다. 허용 나이와 간격은 DAQ의 wall-clock heartbeat + `OBSERVATION_GRACE_S`(기본2초)이며 TIME_SCALE로 나누지 않는다. 패턴의 hold 시간과 경사 창은 기존대로 시뮬레이션 초다. 관측 공백·미확인 입력은 CANDIDATE를 IDLE로, CLEARING을 기존 경보의 RAISED로 되돌린다. 데이터가 없다는 이유로 경보를 해제하지 않는다. 미래/충돌 시각과 비수치·불량 품질도 보류하며 늦은 과거 기록이 최신 관측을 덮지 않는다.

`GET :8092/api/detector/state`의 `observations`에는 원천 시각·품질·현재 wall 나이/허용 나이가 있고, `data_quality_at_last_tick`은 마지막 TS1 평가 시점의 입력 유효성이다. 마지막 평가가 VALID여도 현재 입력이 계속 신선하다는 뜻은 아니다. Prometheus의 `detector_input_event_timestamp_seconds`로 원천 event 시각을 별도로 읽을 수 있다. `detector_pattern_inputs_valid`도 마지막 평가의 값이다.

A055부터 lite의 TS1·CE·PS1·FS1·VS1·LoadSP는 매초 보고한다. 이전 VS1 변화보고/10초 heartbeat는20배속60sim초 경사 창(3wall초)에 부족했다. 경사 창의 관측2개 미만은 계속 UNKNOWN이며 입력값을 보간해 지속조건을 채우지 않는다. 실제 TimescaleDB에서 추가4태그×3설비가 최근60초 각60관측으로 저장되는 것을 확인했다(`a055-daq-samples.json`). 고정1초 표본 사이의 물리적 연속성까지 보증하지 않으며 임의 배율/규칙의 해상도 자동 설계는 미구현이다.

## 운영 감지 정의 변경과 복구

A057부터 감지기는 Neo4j의 `AnomalyPattern` 중 `detectionMode='held'`, `detectorScope='production'`(생략 시 production)를 읽는다. `TESTS` 관계의 비교 조건을 AND로 실행하며 `rule`은 설명문이다. `clearRule`, `holdSeconds`, `clearHoldSeconds`, `slopeWindowSeconds`, `code`, `severity`도 같은 정의다. 메타데이터와 TESTS 변경은 한 Neo4j 트랜잭션으로 저장한다. 새 코드는 같은 엔진으로 평가하지만, 지원하지 않는 태그/연산 또는 DAQ 해상도가 부족한 정의는 거절한다. `detectorScope`는 배포 분리용이며 접근권한 경계가 아니다.

15초마다 원천을 갱신한다. 즉시 반영하려면 `POST :8092/api/detector/patterns/reload`, 결과 확인은 `GET :8092/api/detector/patterns`다. 응답에는 원천 준비/오류와 적용 정의SHA, 설비별 경보 상태가 있다. 카탈로그 전체 검증에 실패하면 기존 정의를 임의 기본값으로 대체하지 않고 health503·새 경보 보류로 전환한다. 이미 발생한 경보는 발생 당시 정의로 해제하며, 정의를 삭제/편집했다고 경보를 없애지 않는다. 원천 복구 후 새 후보는 hold를 다시 채운다.

`detector-data` 볼륨의 SQLite에 경보ID·고정 정의·처리offset·미전송 경보를 함께 저장한다. 재시작 때 관측과 진행 중 hold는 초기화하고 신선한 입력을 기다린다. 경보는 broker ACK 뒤 완료 표시하므로 중단 위치에 따라 같은ID/상태가 재전송될 수 있다. 소비자는 중복을 처리해야 한다. 저장된 scope·TIME_SCALE·DAQ_PROFILE·관측 grace가 현재 설정과 다르면 기동을 거절한다. 이때 DB/볼륨을 삭제해서 통과시키지 말고 활성 경보를 고려한 명시적 상태 이전을 수행해야 한다. 자동 이전 도구는 아직 없다.

CEP의60sim초와 Evidence SQL의 `interval '2 minutes'`는 다른 시계다. 후자는 실제 DB 시각의2분이며 TIME_SCALE로 자동 축소하지 않는다. 실제 A057 펌프 경보 직후에는2분 평균에 정상 구간이 포함되어 근거FAIL/진단WITHHELD가 발생했다. A059에서는 이 결과를 진단 작업의 PENDING으로 저장하고 명시 재평가를 연결했다. 펌프는 보류→새 관측 구간→재평가→별도 승인→PLC·재관측·정비 종결17항목을 실제 확인했다. 상세 증거와 남은 검증은 HANDOFF §9를 따른다.

## 진단 보류와 명시 재평가

포털의 **프로세스 인스턴스**에서 대상 인스턴스를 고르면 보류 사유와 원천 관측을 볼 수 있다. 조회 실패/미관측은 UNKNOWN, 관측은 있으나 조건을 뒷받침하지 않으면 UNSUPPORTED다. 원천 복구·새 측정 등을 확인하고 요청자와 사유를 입력해 **현재 원천으로 다시 평가**를 누른다. 결과가 여전히 부족하면 새 근거와 함께 다시 보류된다. 재평가는 조치 승인이 아니며, 새 조치가 제안되면 별도 검토·선택 단계가 필요하다.

API는 `POST /api/todolist/{workitem_id}/reassess`이며 JSON은 현재 `draft._deferral.id`를 담은 `deferral_id`, 새 요청 식별자 `request_id`, `by`, `reason`이다. 같은 요청의 응답을 잃었으면 동일한 본문/ID로 재접수한다. 다른 내용으로 같은ID를 쓰거나 다른 보류 세대에 적용하면409다. 포털은 응답 유실 시 같은 요청의 접수 확인 버튼을 유지한다. 이것은 자동 승인이나 자동 반복 평가가 아니다.

`PROCESS_MODE=instance, AGENT_BRIDGE=legacy`에서는 process가 작업을 점유하고 agent의 읽기 평가 API를 호출한다. 점유·만료·응답을 PG에 저장하며, 만료 후 교체된 점유의 늦은 결과는 거절한다. 저장된 응답은 재시작 뒤 같은 판단ID로 접수한다. Codex 워커도 공통 보류 계약에 연결했으나 A059의 실제 실행 검증은 레거시 평가기이며 최신 Codex 실행 증거로 세지 않는다. 큰 원천 추적은 명시적으로 축약될 수 있으며 `trace_truncated`, 원본 길이/해시를 확인한다.
