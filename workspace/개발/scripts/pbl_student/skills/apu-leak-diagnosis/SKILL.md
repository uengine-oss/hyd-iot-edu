---
name: apu-leak-diagnosis
description: 지하철 공기 공급 장치(APU) 공기 누설 의심 경보 — 설비 데이터와 정비 매뉴얼로 누설인지 헛경보인지 가르고, 매뉴얼의 절차 번호로 정비안을 낸다
---
# APU 공기 누설 판단

언제 쓰나: 경보 「공기 누설 의심」(패턴 APU_AIR_LEAK) 하나를 받았을 때.

지키는 것
- 숫자와 절차 번호는 도구가 돌려준 값과 지식 지도에서 읽은 것만 쓴다. 읽지 못한 값을 짐작해 채우지 않는다.
- 도구 서버(apu-ops)를 부를 수 없거나 지식 지도에서 이 설비의 매뉴얼 지식을 찾지 못하면, 무엇을 읽지 못했는지 적고 판단을 보류한다.
- 정비 기록 쓰기(record_maintenance)는 부르지 않는다. 사람이 승인한 뒤 흐름의 「정비 기록 등록」 단계가 쓴다.

## 차례

1. 경보 근거를 읽는다. `alert.evidence` 의 `data_time`(감지한 데이터 시각), `windows`(15분 창 넷 — 부하 운전 비율 `load_ratio`, 오일 온도 `oil_temp_c`, 표본 수 `samples`), `rule`(감지 규칙).
2. 지금 설비 값을 읽는다(도구 서버 apu-ops).
   - `apu_status` — 지금 시각의 마지막 값과 최근 15분 요약.
   - `apu_windows(hours=2)` — 최근 두 시간의 15분 창: 부하 운전 비율 `load_ratio`, 부하 기동 횟수 `load_starts`, 오일 온도, 모터 전류, 저장 탱크 최소 압력 `reservoirs_bar_min`, 저압 신호 비율 `lps_ratio`, 오일 부족 비율 `oil_level_low_ratio`.
   - 필요하면 `apu_readings`(한 시간 이내의 원시 값), `failure_reports`(회사 고장 보고), `maintenance_log`(최근 정비 기록).
3. 매뉴얼 지식을 읽는다(지식 지도 neo4j). `get_neo4j_schema` 로 이름을 확인한 뒤 `read_neo4j_cypher` 로 이 설비 매뉴얼에서 적재된 고장 유형 「공기 누설」과 그 원인 · 증거 · 조치 방법을 읽는다. 예:

   ```cypher
   MATCH (f:FailureMode) WHERE f.name CONTAINS '공기 누설'
   OPTIONAL MATCH (c:Cause)-[:CAUSES]->(f)
   OPTIONAL MATCH (c)-[:EVIDENCED_BY]->(e:Evidence)
   OPTIONAL MATCH (f)-[r:MITIGATED_BY|REMEDIED_BY]->(s:Skill)
   OPTIONAL MATCH (s)-[:ADDRESSES]->(a:Cause)
   RETURN f.id AS failure_mode, f.name AS name,
          collect(DISTINCT {cause: c.name, evidence: e.name, tag: e.tag, window: e.windowSeconds, note: e.note}) AS causes,
          collect(DISTINCT {sop: s.sopId, name: s.name, relation: type(r), addresses: a.name}) AS procedures
   ```

   증거에 「판단 엔진이 평가하지 않는다」는 비고가 있으면, 그 증거가 읽는 신호(tag)의 값을 2에서 읽은 도구 서버 값으로 직접 견준다.
   조치 방법의 단계가 필요하면 `(:Skill)-[:HAS_STEP]->(:Step)` 을 읽는다.
4. 판정한다. 3에서 읽은 증거의 기준을 2에서 읽은 지금 값에 견준다.
   - **공기 누설**: 누설 원인의 증거 기준을 지금 값이 만족하고, 경보 뒤에도 그 상태가 이어진다.
   - **헛경보**: 경보 뒤 부하 운전 비율이 평소 수준으로 돌아왔거나, 높은 부하가 일시적인 까닭(오래 멈춘 뒤 저장 탱크를 채움 등)으로 설명되고 누설 원인의 증거 기준을 만족하지 않는다.
   - **판단 보류**: 설비 값이나 매뉴얼 지식을 읽지 못했다.
5. 정비안을 결과 값 `proposal` 하나로 낸다.

   ```json
   {"verdict": "공기 누설",
    "summary": "무엇을 보고 그렇게 판정했는지 한두 문장",
    "evidence": [{"what": "최근 2시간 15분 창의 부하 운전 비율", "value": 0.99, "source": "apu_windows", "data_time": "2020-07-15 15:45:00"}],
    "options": [{"slot": "A", "title": "누설 시험과 누설 위치 찾기", "sop": "SOP-APU-11", "action": "차량 기지에서 누설 시험으로 누설 위치를 찾는다", "reason": "왜 이 절차인지"}],
    "recommended": "A",
    "losers": [{"slot": "B", "why": "왜 지금은 이 안이 아닌지"}]}
   ```

   - `verdict` 는 「공기 누설」 · 「헛경보」 · 「판단 보류」 가운데 하나다.
   - 공기 누설이면 `recommended` 는 매뉴얼이 정한 차례에 맞는 첫 조치다. 다른 절차는 `options` 에 두고 `losers` 에 왜 지금은 아닌지 적는다.
   - 헛경보면 `recommended` 를 null 로 두고 `summary` 를 「헛경보 — 정비하지 않고 반려를 권합니다」로 시작해 근거를 잇는다. `options` 에는 그래도 누설이라면 할 첫 절차 하나를 둔다(사람이 다르게 판단하면 고를 수 있게).
   - 판단 보류면 `recommended` 를 null, `options` 를 빈 목록으로 두고 `summary` 에 무엇을 읽지 못했는지 적는다.
   - `sop` 에는 지식 지도에서 읽은 절차 번호만 쓴다. `slot` 은 A, B, C … 처럼 안마다 다르게 둔다.
