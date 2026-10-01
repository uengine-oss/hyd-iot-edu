# 통합 시나리오 테스트 결과 (scripts/scenario_test.py)

> 아래는 **2026-09-30 초기 검증 기록**이다. 이후 안정성·UI 개선의 실행별 결과와 캡처는 저장소 밖의 로컬 HTML에 보관한다. 현재 코드의 재검증 방법은 [README](../README.md)의 검사 명령을 따른다.

실행: 2026-09-30 (L7~L9 고도화 + 경량 구성 + HITL 조치 의사결정 · 선례 환류 · 스킬 카탈로그 · 매뉴얼 인제스천 적용 뒤), TIME_SCALE=20, DAQ_PROFILE=lite, COMPOSE_PROFILES=ot,backbone,detect,knowledge,agent,enterprise,process

```
== 0. 서비스 상태
  [PASS] plant-sim healthy  {"mqtt": true}
  [PASS] cmd-gateway healthy  {"mqtt": true, "kafka": true}
  [PASS] detector healthy  {"kafka": true}
  [PASS] agent healthy  {"kafka": true, "neo4j": true}
  [PASS] process healthy  {"kafka": true}
  [PASS] connect-ingest healthy  {"mqtt": true, "kafka": true}
  [PASS] connect-sink healthy  {"db": true, "kafka": true}
  [PASS] enterprise-sim healthy  {}

== 1. 초기화 → 쿨러 열화 주입 (HYD-01)
  [PASS] PLC REMOTE_AUTO · RUN  TS1=48.0
  [PASS] fault injected  {"asset": "HYD-01", "kind": "cooler_degradation", "target_health": 0.43, "ramp_sim_s": 300.0}

== 2. L4 탐지 → alerts RAISE → OT 알람 중계
  [PASS] detector RAISED  after 38s TS1=56.93 CE=36.1 score=1.0
  [PASS] cmd-gateway relayed alert to OT  alerts_relayed=45

== 3. L8 에이전트: 온톨로지 T1/T2 + 증거 → 가이드 카드
  [PASS] agent run finished  status=SUBMITTED after 2s
  [PASS] freshness ok  1.1
  [PASS] T1 returned 4 cause candidates  ['cause:cooler-fin-fouling', 'cause:fan-underperformance', 'cause:hydraulic-overload', 'cause:high-ambient']
  [PASS] top cause = cooler fin fouling  scores=[('cause:cooler-fin-fouling', 0.5), ('cause:fan-underperformance', 0.1), ('cause:hydraulic-overload', 0.0409), ('cause:high-ambient', 0.0273)]
  [PASS] recommended FAN_BOOST, REDUCE_LOAD, COOLER_CLEAN_WO  ['FAN_BOOST', 'REDUCE_LOAD', 'COOLER_CLEAN_WO']
  [PASS] SOP steps + manual refs attached  
  [PASS] guardrail passed  {"violations": []}
  [PASS] citations present  35 ids
  [PASS] L7→L8: ontology linked this alert to enterprise decision scenarios  [('고객 납기 vs 설비 보전', 'SUBMITTED', '감속 운전 + 야간 세척'), ('교체 부품 구매: 구매단가 vs 전사 이익', 'SUBMITTED', 'B-OEM (순정) 구매'), ('과열 구간 생산 로트: 규정 vs 납기', 'SUBMITTED', '자동차 로트 격리 + ERP 완제품 재고로 대체 출하')]

== 4. L9 프로세스: 승인 → action.cmd → 게이트웨이 검증 → cmd/auto → PLC ACK
  [PASS] incident AWAITING_APPROVAL  INC-0930-01-4909 AWAITING_APPROVAL
  [PASS] approve accepted  {"cmdId": "CMD-0930-0001-1c85", "asset": "HYD-01", "incident": "INC-0930-01-4909", "source": "HITL", "actions": [{"code": "FAN_BOOST", "fan_pct": 100}, {"code":
  [PASS] PLC ACK DONE → RE_OBSERVING  state=RE_OBSERVING ack={'result': 'DONE', 'reason': None, 'interlock': 'PASS', 't': '2026-09-30T06:55:45.188Z'} after 4.2s
  [PASS] gateway decision PASS  {"t": "2026-09-30T06:55:45.176Z", "cmdId": "CMD-0930-0001-1c85", "asset": "HYD-01", "incident": "INC-0930-01-4909", "ok": true, "check": "PASS", "reason": null}
  [PASS] PLC applied fan 100 / load 80  fan=100.0 load=80.0 cmdId=CMD-0930-0001-1c85

== 5. 회복 → alerts CLEAR → 재관측 통과 → 작업지시 → 종결
  [PASS] detector CLEAR (IDLE)  after 44s TS1=51.38
  [PASS] incident CLOSED  state=CLOSED reason=None after 7s
  [PASS] work order created  {"id": "WO-INC-0930-01-4909", "code": "COOLER_CLEAN_WO", "name": "\ucfe8\ub7ec \ud540 \uc138\ucc99 \uc791\uc5c5\uc9c0\uc2dc", "actionId": "act:cooler-clean-wo", "sop": "SOP-COOL-02", "t": "2026-09-30T06:56:42.971Z"}
  [PASS] history order  ['GUIDE_RECEIVED', 'AWAITING_APPROVAL', 'CMD_ISSUED', 'AWAITING_ACK', 'ACKED', 'RE_OBSERVING', 'RESOLVED', 'WORK_ORDER_CREATED', 'CLOSED']

== 5b. L7 → L8 → L9: 경보에서 자동 기동된 전사 판단 → 역할 승인 → 기업 시스템 실행
  [PASS] process received decisions for the incident  [('sc:delivery-vs-maintenance', 'PENDING_APPROVAL', 'opt:sc1-derate'), ('sc:part-procurement', 'PENDING_APPROVAL', 'opt:sc2-b'), ('sc:quality-hold', 'PENDING_APPROVAL', 'opt:sc3-substitute')]
  [PASS] SC1 recommends derate + night cleaning (not stop, not continue)  전사 관점 권고는 '감속 운전 + 야간 세척'입니다 (전사 합계 -62만원). 현장 판단 선례: 지난 같은 판단에서 9건(90 %)이 이 안을 골랐고, 그만큼 점수에 반영했습니다. 차선 'HYD-02로 물량 이관 +
  [PASS] SC1 'continue' excluded by HARD policy 65 ℃  
  [PASS] SC1 maintenance dept prefers a different option  {"dept:maintenance": "opt:sc1-transfer", "dept:plant": "opt:sc1-derate", "dept:production": "opt:sc1-derate", "dept:quality": "opt:sc1-derate", "dept:sales": "opt:sc1-derate", "enterprise": "opt:sc1-derate"}
  [PASS] operator may not approve a plant stop (needs 공장장)  {"detail":"승인 권한 없음: '즉시 정지 · 쿨러 세척'은(는) 공장장 이상이 승인해야 한다"}
  [PASS] approved → CMMS work order executed, PLC part left to HITL  {"skill:schedule-maintenance": "DONE", "skill:cooling-adjust": "VIA_HITL"}
  [PASS] SC2 enterprise picks OEM while purchasing prefers the cheap supplier  
  [PASS] ERP purchase request + CMMS work order in enterprise systems  [('sys:erp', 'PR-0930-6CB7'), ('sys:cmms', 'WO-0930-2D9F')]
  [PASS] audit has DECISION_SUBMITTED/DENIED/APPROVED/SKILL_EXECUTED  
  [PASS] decision case written to the ontology (Decision -DECIDED-> Option, -FOR-> Incident)  "opt:sc1-derate", "INC-0930-01-4909"

== 5c. 지식 관리 (L9 → L7): 스킬 카탈로그 · 매뉴얼 인제스천 · HITL 선례 환류
  [PASS] skill catalog lists 8+ skills with description and detail  ['냉각 즉시 제어 (팬 ↑ · 부하 ↓)', '전력 수요 제어 (공조 · 부하)', '로트 격리 · 전수검사', '부품 구매요청']
  [PASS] skill shows system · approver · policy from the ontology  
  [PASS] manual preview: 2 sections, 2 SOPs, 8 steps  [('SOP-FAN-01', 'act:fan-inspect-wo'), ('SOP-FAN-02', 'act:fan-inspect-wo')]
  [PASS] manual committed to the ontology  {"upload": "UP-20260930T065731", "sections": 2, "procedures": 2, "steps": 8, "links": {"SOP-FAN-01": "act:fan-inspect-wo", "SOP-FAN-02": "act:fan-inspect-wo"}}
  [PASS] next decision reads the human precedent written in 5b  {"opt:sc1-derate": {"n": 10, "reasons": ["OEM 납기 우선, 야간 정비창에 세척 인력 확보", "OEM 납기 우선, 야간 정비창에 세척 인력 확보"]}, "opt:sc1-stop": {"n": 1, "reasons": []}}

== 6. L5 저장소 확인 (TimescaleDB via docker exec)
  [PASS] alerts row RAISE→CLEAR  CLEAR|2026-09-30 06:55:30.724+00|2026-09-30 06:56:33.299+00
  [PASS] actions row with ACK DONE  CMD-0930-0001-1c85|DONE|OP-17
  [PASS] audit rows for incident  15 rows
  [PASS] feat_1s has anomaly scores  

== 7. 부정 시나리오: REMOTE_MANUAL 모드에서는 게이트웨이가 거부 → 에스컬레이션
  [PASS] HYD-02 RAISED  after 35s
  [PASS] incident for HYD-02  INC-0930-02-296a
  [PASS] gateway REJECTED with MODE  {"t": "2026-09-30T06:58:28.275Z", "cmdId": "CMD-0930-0002-1e49", "asset": "HYD-02", "incident": "INC-0930-02-296a", "ok": false, "check": "MODE", "reason": "PLC mode is REMOTE_MANUAL (REMOTE_AUTO required)"}
  [PASS] incident ESCALATED (ACK_TIMEOUT)  ESCALATED ACK_TIMEOUT after 29s
  [PASS] process audit has ACK_TIMEOUT  
  [PASS] Kafka audit → TimescaleDB has cmd-gateway CMD_REJECTED  check='MODE'

== 8. 부정 시나리오: 조치 없이 방치 → 65 ℃ 인터록 트립 → OVERHEAT_TRIP → RESET
  [PASS] PLC tripped at >65 C  after 50s TS1=63.64
  [PASS] detector OVERHEAT_TRIP alert  
  [PASS] RESET rejected while hot  {"cmdId": "FUXA-1790751607832", "result": "REJECTED", "reason": "RESET_TOO_HOT", "applied": {}}
  [PASS] RESET accepted below 55 C  {"cmdId": "FUXA-1790751619546", "result": "DONE", "reason": null, "applied": {"Reset": 1.0}}

ALL PASS — 59/59 checks in 352s
```

단위 테스트: `python -m pytest -q` → 124 passed in 0.97s

## L7~L9 전사 판단 확인 (같은 날)

- 5b절이 경보에서 자동 기동된 전사 판단 3건(납기 vs 보전, 교체 부품 구매, 과열 로트)을 검증한다: 권고안, HARD 규정 제외, 부서별 1위 차이, 운전원의 정지안 승인 거부(403), 생산관리자·공장장 승인 → CMMS 작업지시 · ERP 구매요청 실행, 즉시 제어 스킬은 VIA_HITL, 감사 이벤트, 온톨로지 Decision 기록.
- 5c절은 스킬 카탈로그(8종, 설명 · 상세 · 연결), 예시 매뉴얼 미리보기와 적재(절 2 · SOP 2 · 단계 8), 5b절의 사람 결정이 다음 판단의 선례로 읽히는지를 검증한다.
- 포탈 화면(메인, 온톨로지 지식 지도와 매뉴얼 업로드, 스킬 카탈로그 편집 · 저장, 전사 의사결정, HITL 조치 의사결정 패널과 BPMN 흐름도, 업무 프로세스)은 Playwright로 조작하며 스크린샷으로 확인했다. HITL 패널에서 운전원의 결정은 권한 부족으로 거부되고, 생산관리자의 결정은 PLC 명령과 CMMS 작업지시로 실행됐다.
- 경량화 측정(20초 평균): 메모리 합계 약 2.1 GB → 1.4 GB, Kafka plant.tag 71 → 12건/초, plant.wave 11 → 0건/초, feat.1s 15 → 3건/초.
