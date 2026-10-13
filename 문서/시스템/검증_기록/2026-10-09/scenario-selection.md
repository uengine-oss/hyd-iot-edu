# 세 시나리오 다시 고르기 — 열린 조사 · 안 겹치게 (2026-10-09)

작성 2026-10-09. **읽기 전용 조사 · 추천**이다. 코드 · 시드 · 정의 · 다른 문서는 바꾸지 않았고 커밋하지 않았다.
앞선 `scenario-research.md`는 이미 고른 A/B/C 를 검증만 한 **제약 조사**였다. 이 문서는 후보를 넓게 펼친 뒤 처음부터 다시 고른다.

**사용자 요구(이번 지시)**: "다시 조사해봐, 안 겹치게." → **겹치지 않음을 1순위 기준**으로 둔다.
세 시나리오 사이에 ⓐ 시작 신호 출처 ⓑ 업무 목적 ⓒ BPMN 모양 ⓓ 에이전트 판단 종류 ⓔ MCP · 도구 묶음 ⓕ 스킬 · 문서 ⓖ 승인자 역할 — 7축이 겹치면 안 된다. 겹치는 칸은 이유를 대거나, 못 대면 그 조합을 버린다.

**고정 조건(바꾸지 않음)**: 같은 설비(유압 파워팩 HYD-01~03) · 같은 구조 · 온톨로지 스키마 v2(같은 양식 추가 확장은 분명히 값어치가 있을 때만, 명시) · 엔진 부분집합(task · 배타/병렬 분기 · 경계 타이머 · 칸 · 반복, 하위 프로세스 · 중간 이벤트 없음) · 사람은 승인만 · 승인 뒤 쓰기는 시스템 task · 시작은 자동(수업 버튼이 원인을 만든다) · 실행 → 확인 → 종결 · task 6~10.

**비유 한 줄**: 같은 차 세 대를 둔 정비소에서 "누가 알려 주나"가 셋이다 — **계기판 경고등**(A), **주행거리계**(B), **부품 창고 선반**(C). 알려 주는 쪽이 다르면 하는 일 · 결재하는 사람 · 쓰는 서류가 자연히 달라진다.

---

## 0. 결론 먼저

| | 추천 조합 | 차점 조합 |
|---|---|---|
| A | **긴급 대응** — HYD-01 쿨러 과열 (센서 경보) | 같음 |
| B | **정기 정비** — HYD-02 운전시간 2,000 h 도래 (CMMS 운전시간 계수기) ← **바뀜** | 같음 |
| C | **예비품 구매** — 씰 키트 재고 < 재주문점 (ERP 재고) | **입고 검사 · 공급사 품질** — 납품된 씰 키트 로트 검사 불합격 의심 (QMS 입고 검사) |
| 7축 겹침 | 0칸 (부분 겹침 3칸, 모두 이유 있음 · 줄이는 방법 있음 — §4) | 0칸 (부분 겹침 2칸 — §5) |
| 왜 이 순서 | 학생이 한 문장으로 알아듣고, 지금 시드(공급사 3곳 · AVL · 단가↔품질 상충)를 그대로 쓰며, 구현 부담이 가장 작다 | 판단은 더 풍부하지만 로트 · 검사 데이터가 새로 필요하고, "산 물건이 있어야" 시작되므로 단독 수업 버튼이 덜 자연스럽다 |

**솔직한 판정**
- **지금의 A · C 는 이미 최선 쪽이다.** 넓게 펼쳐 봐도 A(센서 → 즉시 시정)와 C(재고 → 조달)를 이기는 후보가 없었다. 두 개 다 "누가 알려 주나"가 가장 선명하고, 근거 자료(ISA-18.2, SAP MM 재주문점)가 가장 두껍다.
- **B 만 바꾼다.** 지금 B(펌프 효율 저하 = 예지 정비)는 시작 신호가 **센서**라 A 와 ⓐ 시작 출처 · ⓔ 도구(diagnose · timeseries) · ⓓ 판단 종류(진단)가 겹친다. EN 13306 도 상태 기반 · 예지 정비를 "측정값이 기준을 넘을 때"로 정의하므로, 아무리 다르게 꾸며도 A 와 같은 뿌리다.
- **새 B = 운전시간 기반 정기 정비(예정 정비)**. 시작은 사람 · 센서가 아니라 **CMMS 계획 스케줄러**다(SAP IP10/IP30 · Maximo PM 크론). 에이전트가 하는 일은 "무엇이 고장났나"가 아니라 **"언제 · 무엇을 묶어서 · 허용 오차 안에서 당길까 미룰까"**다. 이 판단은 A · C 어디에도 없다.

---

## 1. 조사 방법과 한계

- 네 갈래로 나눠 웹 조사를 했다(정비 시작 방식 · MRO 구매/품질 · 오일/교정/안전 · 에너지/경보/산업 AI 사례). 근거는 §9 출처 목록, 갈래별 원 노트는 세션 임시 폴더에만 있다(레포 밖).
- 표준 원문(ISA-18.2, EN 13306, ISO 10012)은 유료라 2차 요약으로 읽었다 **[2차]**. 업체 블로그 · 보도자료 수치는 **[업체]** 로 표시한다.
- **못 찾은 것**: Rexroth · Parker · Eaton · HYDAC · Yuken 파워팩 매뉴얼 원문(403/404). 정비 주기는 Atos 파워팩 매뉴얼(MAN-C-012)과 Valmet 예시에 기댄다. 정기 정비를 얼마나 미뤄도 되는지에 대한 권위 있는 규칙은 없었다(SAP 허용 오차 · shift factor 는 회사가 정하는 설정값).
- 저장소는 읽기만 했다: `ot/plant-sim/plantsim/{main,plant}.py`, `it/enterprise-sim/entsim/data.py`, `it/process/procsvc/{bpmn_import,human_alert}.py`, `it/neo4j/v2/{instances,knowledge_a098}.cypher`, `it/neo4j/v2/schema_prompt.md`, `docs/ontology/{class-table,schema-v2}.md`, 앞선 `scenario-research.md`.

---

## 2. 후보 16개 — 실제로는 어떻게 돌아가나

| # | 후보 (한 문장) | 누가 알려 주나 (시작) | 실무에서 하는 일 (근거) | 승인자 | 닫힘 확인 |
|---|---|---|---|---|---|
| 1 | **센서 이상 긴급 대응** — 유온이 올라 설비가 서기 전에 식힌다 | 탐지기(OT 센서) | 경보는 "정해진 시간 안의 운전원 조치"를 요구한다(ISA-18.2 [2차]). SAP 긴급 작업은 선별 · 승인을 건너뛰고 바로 오더가 된다(SAP Learning) | 운전원 | 경보 해제 · 유온 정상 |
| 2 | **운전시간 · 달력 정기 정비** — 2,000시간마다 하는 정기 점검을 언제 할지 정한다 | CMMS 계획 스케줄러(운전시간 계수기 · 달력) | 계수기 측정점(IK01/IK11) → 계획(IP41/IP42) → 스케줄(IP10/IP30)이 호출 기간 안에 오더를 만든다. 허용 오차 · shift factor · 완료 요건이 다음 날짜를 정한다(SAP Help · SAP 블로그). 파워팩 정비표: 작동유 2,000~3,000 h 또는 1년, 필터는 막힘 표시 · 최소 1년, 어큐뮬레이터 프리차지 3개월, 쿨러 청소 6개월, 커플링 1년 교체, **보증 기간 중 정기 점검 기록 의무**(Atos MAN-C-012) | 정비(보전) 책임자 | 작업 완료 확인 · 시운전 · **계수기 리셋과 다음 기한** |
| 3 | **상태 기반 · 예지 정비** — 펌프 효율이 서서히 떨어져 언제 고칠지 정한다 (지금 B) | 탐지기(센서 추세) | P-F 간격 안에서 계획한다. ISA-18.2 로는 "즉시 조치 경보"가 아닌 "평가가 필요한 알림"(alert)이다 [2차] | 정비 책임자 | 압력 · 유량 회복 |
| 4 | **예비품 재주문 구매** — 씰 키트가 바닥나기 전에 사 둔다 (지금 C) | ERP 재고(재주문점) | MRP 유형 VB: 재고+입고 예정 < 재주문점이면 구매요청. 금액 특성으로 결재 전략이 갈린다 → 발주 → 입고(101) → 3자 대조(SAP Community · SAP Help). 중요 예비품은 결품 비용을 기준으로 둔다 [업체] | 구매 담당 → 금액 초과 시 팀장 | 입고 확인 |
| 5 | **오일 분석 결과 처리** — 외부 분석소 보고서가 기준을 넘으면 조치를 정한다 | 외부 분석소 보고서(포털 · API) | ISO 4406 목표(비례 밸브 17/15/12 등, Mobil 표), 수분 ~500 ppm 조치점(Eaton), 재채취 → 필터 카트 → 교환 → 재채취(Machinery Lubrication). POLARIS 는 결과를 CMMS 에 시간 단위 동기화하고 심각도로 작업지시를 만든다 [업체] | 정비 책임자 [추론] | 재채취 결과 (수일) |
| 6 | **전력 피크 관리** — 오후 피크가 계약전력을 넘지 않게 부하를 나눈다 | EMS 수요 예측 | 요금은 15분 평균 최대 수요로 정해진다 [업체]. 한국 전기공급약관: 최대수요전력 12개월 중 최대가 요금적용전력 [2차 · 사본] | 생산관리자 [추론] | 15분 수요 확인 |
| 7 | **LOTO · 작업 허가** — 정비 전에 잔압을 빼고 잠근다 | 사람(작업 요청) | OSHA 1910.147: 저장 에너지 해제 · 격리 확인, 잠근 사람만 해제. 유압은 어큐뮬레이터 배출 · 실린더 양쪽 0 확인 | 허가 발행자 / 수행자 (HSG250) | 현장 확인 |
| 8 | **교대 인수인계** — 다음 조에 넘길 내용을 정리한다 | 시계(교대 시각) | 준비 → 대면 교환 → 교차 확인 3단계(HSE). 승인 관문이 아니라 소통 절차다 | 없음 (서명 확인) | 약함 |
| 9 | **긴급 오더 설비 배정** — 급한 주문을 어느 설비에 맡길지 정한다 | MES 오더 변경 | APS 재일정. 상용 사례 근거 약함(학술 위주) | 생산관리자 | 오더 진행 |
| 10 | **입고 검사 · 공급사 품질** — 들어온 부품에 불량이 섞였으면 받을지 돌려보낼지 정한다 | QMS 입고 검사 로트 (납품 도착) | 입고 때 검사 로트(유형 01) 자동 생성 → 사용 결정 → 품질 통지 → 차단 재고 → 반품(122) · 8D 요청 → 검사 강도 재설정(SAP Help 11단계). 공급사 회신 14일 · 격리 24~48 h(Keysight 등 회사 예) | 품질 책임자 | 반품 · 차단 해제 · 대체 입고 |
| 11 | **보증 클레임** — 보증 기간 안에 고장 난 펌프 비용을 공급사에 청구한다 | 사람(고장 부품 발견) | 기간 · 구매 증빙 확인 → RMA → 분해 금지 반송 14~30일 → 공급사 판정 2~3주 → 크레딧/거절. 핵심 판단은 결함 vs 오염 · 마모(ISO 4406 기록) | 구매 · 품질 | 크레딧 (외부 판정, 수주) |
| 12 | **경보 합리화** — 너무 자주 울리는 경보의 기준을 고친다 | 경보 통계(30일 KPI) | 운전원당 시간당 ~6건, 채터링 0, 상위 10개 ≤ 1~5 %. 기준 변경은 MOC 승인 → 경보 마스터 DB 갱신(ISA-18.2/EEMUA [2차]) | 제어 · 공정 엔지니어 (MOC) | 다음 기간 경보 수 |
| 13 | **계측기 교정 · 기준 이탈** — 온도 센서가 틀렸으면 지난 데이터 영향까지 따진다 | 교정 달력 또는 센서 간 불일치 | as-found/as-left, 격리, 지난 양호 교정까지 소급 영향 평가(ISO 9001 7.1.5.2 [2차] · ISO 10012) | 품질 · 계측 책임자 | 재교정 · 영향 종결 |
| 14 | **누유 · 유출 대응** — 기름이 새면 막고 신고 여부를 정한다 | 탱크 레벨 / 사람 발견 | 수면 유막이면 즉시 신고(40 CFR 110), SPCC 1,000 gal / 42 gal×2회 보고(40 CFR 112.4) | 환경 · 안전 책임자 | 정화 확인 (연방 기준 없음) |
| 15 | **변경관리(MOC)** — 다른 공급사 부품 · 설정으로 바꿀 때 영향을 검토한다 | 사람(변경 요청) | 같은 규격 교체(replacement in kind)는 면제, 아니면 MOC · 가동 전 안전 검토(OSHA 1910.119(l)). 유압 설비는 대개 PSM 대상이 아니어서 회사 규정 [추론] | 변경 위원회 | 가동 전 검토 |
| 16 | **폭염 예보 사전 대응** — 내일 35 ℃ 예보에 대비해 미리 냉각을 손본다 | 외부 기상 예보 | 외기 고온은 쿨러 용량 부족 원인(Machinery Lubrication). 시드에 외부 변수 · 예측 클래스와 EMS 외기 35 ℃ 값이 있다 | 생산관리자 | 다음날 유온 |

산업 AI 사례(근거, 모두 [업체]): SAP 협력사 Joule Studio 에이전트는 작업지시를 만들기 전에 사용자 확인을 받는다. Cognite Atlas AI 는 "사람이 목표를 정하고 에이전트가 제안"하며 Aker BP 는 원인 분석 시간 70 % 이상 단축을 주장한다. Coupa Navi 는 구매요청 작성 · 입찰 평가를 하고, Verusen 은 MRO 재고 정책 추천을 설명한다. Honeywell 운전 보조는 경보 5~10분 전 예측(파일럿)을 한다. **경보 합리화 MOC 초안 · 피크 감발 결정 · 인수인계 허가 점검을 하는 공개 사례는 찾지 못했다.** "에이전트가 분석 · 제안, 사람이 승인"은 업계가 실제로 택한 모양과 맞는다.

---

## 3. 점수표

**채점**: 5 = 아주 좋음, 1 = 나쁨. ⑧ 구현 부담은 **5 = 부담 작음**. **⓪ 비중복**은 축(anchor)인 A 와의 7축 겹침 정도다(A 자신은 "—"). ⓪이 2 이하면 다른 점수와 무관하게 B · C 자리에서 탈락한다(1순위 기준).

| # | 후보 | ⓪ A와 비중복 | ① 시작 신호 구분 | ② 흐름 차이 | ③ 판단 풍부 | ④ 스키마 v2 | ⑤ 한 문장 이해 | ⑥ 수업 버튼 | ⑦ 닫고 확인 | ⑧ 구현 부담(5=작음) | ①~⑧ 합 | 판정 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 센서 긴급 대응 (A) | — | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | **40** | **유지 (축)** |
| 2 | 운전시간 정기 정비 | **5** | 5 | 5 | 4 | 4 | 5 | 4 | 4 | 3 | **34** | **B 채택** |
| 3 | 예지 정비 (지금 B) | 2 | 2 | 3 | 5 | 5 | 3 | 5 | 4 | 3 | 30 | 탈락(시작 · 도구 · 판단이 A 와 겹침) |
| 4 | 예비품 재주문 구매 (지금 C) | **5** | 5 | 5 | 4 | 4 | 5 | 4 | 4 | 3 | **34** | **C 채택** |
| 5 | 오일 분석 결과 | 3 | 5 | 3 | 4 | 5 | 4 | 4 | 2 | 4 | 31 | 보류(사용자가 "작동유 안 해도" 함 · 진단 사슬이 A 와 같음 · 재채취 확인이 수일) |
| 6 | 전력 피크 관리 | 2 | 4 | 3 | 5 | 4 | 4 | 4 | 4 | 4 | 32 | 탈락(PLC 감발 → 재관측이 A 와 같은 모양, 승인자 생산관리자가 A 상급자와 같음) |
| 7 | LOTO 작업 허가 | 4 | 2 | 4 | 2 | 2 | 3 | 2 | 3 | 2 | 20 | 탈락(사람이 시작 · 현장 행위가 본체 → "사람은 승인만" 위반) |
| 8 | 교대 인수인계 | 4 | 4 | 2 | 2 | 3 | 5 | 3 | 1 | 4 | 24 | 탈락(승인 · 효과 · 닫힘 확인이 없다) |
| 9 | 긴급 오더 설비 배정 | 2 | 4 | 3 | 4 | 3 | 5 | 5 | 3 | 3 | 30 | 탈락(부하 명령 · 생산관리자가 A 와 겹침, 정비 과정이 아님) |
| 10 | 입고 검사 · 공급사 품질 | **5** | 4 | 4 | 4 | 3 | 4 | 4 | 4 | 2 | 29 | **차점 C** |
| 11 | 보증 클레임 | 4 | 3 | 3 | 4 | 2 | 3 | 3 | 2 | 2 | 22 | 탈락(외부 판정까지 수주 · 보증 속성 없음) |
| 12 | 경보 합리화 | 3 | 3 | 4 | 4 | 4 | 3 | 3 | 4 | 2 | 27 | 보류(온톨로지 수정이 행동을 바꾸는 좋은 교재지만 경보 · 탐지기 축이 A 와 겹침 → 랩업 소재로 권장 §7) |
| 13 | 계측기 교정 | 3 | 3 | 3 | 4 | 2 | 3 | 4 | 3 | 2 | 24 | 탈락(달력 시작이 새 B 와 겹치고, 교정 클래스 없음) |
| 14 | 누유 · 유출 | 3 | 2 | 3 | 3 | 2 | 5 | 2 | 3 | 1 | 21 | 탈락(시뮬레이터에 레벨 없음 · 법규 신고가 사람 몫) |
| 15 | 변경관리 MOC | 4 | 2 | 4 | 4 | 2 | 2 | 2 | 3 | 2 | 21 | 탈락(사람이 시작 · 노베이스에게 추상적) |
| 16 | 폭염 예보 대응 | 2 | 4 | 3 | 4 | 5 | 4 | 4 | 3 | 3 | 30 | 탈락(쿨러 · 냉각 주제가 A 와 같음) |

**읽는 법**
- 합계만 보면 오일 분석(31) · 피크(32)도 높다. 그러나 1순위 기준 ⓪에서 걸린다. 피크는 "부하를 낮추는 PLC 명령 → 재관측" 이 A 의 뼈대 그대로이고, 오일은 진단 사슬(패턴 → 증상 → 원인)과 `diagnose` 도구가 A 와 같다.
- 예지 정비(지금 B)는 판단이 가장 풍부한(③ 5) 후보다. 그러나 시작이 센서라 ⓪ 2 로 탈락한다. **판단의 풍부함은 새 B 에 일부 옮겨 온다**(허용 오차 · 생산 · 부품 · 묶음의 네 근거가 서로 부딪친다, §4.B).
- 경보 합리화는 점수보다 교육 가치가 크다. 다만 경보 · 탐지기 축이 A 와 겹치므로 세 시나리오 밖의 **랩업 소재**로 권한다(§7).

---

## 4. 추천 조합 — A 긴급 대응 · B 정기 정비 · C 예비품 구매

### 4.0 세트로 보면 왜 가장 선명한가

| 학생이 묻는 것 | A | B | C |
|---|---|---|---|
| **누가 알려 주나** | 설비 센서 (지금 이상하다) | 정비 달력 · 운전시간 계수기 (때가 됐다) | 창고 재고 (곧 모자란다) |
| **무엇을 하나** | 지금 식힌다 (복구) | 날짜를 잡아 미리 고친다 (예방) | 사 둔다 (조달) |
| **시간 단위** | 분 | 일 (정비창) | 일~주 (리드타임) |
| **에이전트가 답하는 질문** | 무엇이 잘못됐고 지금 무엇을? | 언제 · 무엇을 묶어서? | 얼마나 · 어디서 · 얼마에? |
| **결재하는 사람** | 현장 운전원 | 설비보전팀장 | 구매 담당 (+ 구매팀장) |
| **확인하는 것** | 유온 · 경보 | 시운전 값 · 계수기 리셋 | 입고 |

세 질문(무엇/언제/어디서·얼마)은 공장 업무의 세 갈래(운전 · 보전 · 구매)와 그대로 겹친다. 노베이스가 "같은 설비인데 왜 셋이 다르지?"를 묻지 않는다.

### 4.A 긴급 대응 — HYD-01 쿨러 과열 (유지)

- **한 문장**: "쿨러가 막혀 기름이 뜨거워지니, 설비가 서기 전에 식힌다."
- **시작**: 센서 경보 `COOLER_DEGRADATION` (기존 held 패턴). 수업 버튼 = plant-sim `POST /api/fault {asset:HYD-01, type:cooler_degradation}` (있음).
- **에이전트 판단**: 원인(핀 오염 / 외기 고온 / 팬 고장)을 증거로 가리고, 즉시 완화 3안을 예측 유온 · 납기 · 팬 수명 · 전력으로 비교한다. 팬만 최대로 하면 예측 유온이 해제 기준을 못 넘을 수 있다(WARN). 부하를 70 %로 줄이면 OEM 납기를 놓친다. 그래서 1안이 손익으로 이긴다.
- **승인**: 운전원(카드 승인, 경계 타이머 10분 → 생산관리자).
- **승인 뒤**: PLC 명령 → 15분 재관측 → (정상) 핀 세척 작업지시 → 끝 / (미회복) 생산관리자 확인.
- **확인**: TS1 < 55 ℃ · 경보 해제.
- 앞선 설계(`scenario-research.md` §5.A)를 그대로 쓴다. 바뀌는 것은 하나다. 후속 작업지시는 **CMMS 에 "통지"만 남기는 인계**로 정의하고, 날짜 잡기는 B 의 일이라고 수업에서 말한다(§4.4 연결 이야기).

### 4.B 정기 정비 — HYD-02 운전시간 2,000 h 도래 (새로 바뀜)

- **한 문장**: "2,000시간마다 하는 정기 점검 때가 됐으니, 생산을 덜 잃는 날로 날짜를 잡아 미리 고친다."
- **왜 이 업무가 실제로 있나**: SAP · Maximo 모두 운전시간 계수기 계획이 사람 요청 없이 오더를 만들고, 허용 오차 · shift factor 로 날짜를 옮긴다. 파워팩 OEM 매뉴얼은 시간 · 개월 단위 점검표를 주고, 보증 기간 중 기록을 의무로 둔다(Atos). 24/7 운전에서 3개월 ≈ 2,000 h 는 이 문서의 환산이며 OEM 수치가 아니다.
- **시작 (누가 알려 주나 = CMMS)**: CMMS 계획 스케줄러가 "HYD-02 운전시간 1,950 h / 주기 2,000 h, 호출 기간 진입"을 낸다. 경보 계약은 B7 사람 입력 경보처럼 같은 모양에 `source: "cmms"`, 패턴 `PM_DUE` 로 넣는다.
  - **수업 버튼**: "운전시간 빨리 감기(+300 h)" — 업무 DB 계수기를 올리는 버튼. 실제 운전시간은 plant RUN 시간 × 배속으로 함께 쌓인다.
- **에이전트 판단 (근거 넷이 서로 부딪친다)**:
  1. **기한 · 허용 오차**: 2,000 h ± 10 %(교육용 회사 설정) → 2,200 h 를 넘기면 보증 기록 요건 위반(EXCLUDE).
  2. **생산**: HYD-02 일반 오더 잔량 800, 납기 20 h. HYD-03 OEM 오더 납기 3 h(MES).
  3. **묶음**: HYD-03 도 1,880 h 로 호출 기간에 가깝다. 같은 정비창에 묶으면 인력 · 생산 용량이 모자라고(PENALTY), 따로 하면 정지가 두 번 생긴다.
  4. **부품**: 패키지에 씰 키트 1 · 리턴 필터 1이 든다. 출고하면 씰 키트 가용 재고가 재주문점 아래로 내려간다(WARN → C 예고).
  - **제안**: "오늘 밤 정비창(9 h 뒤)에 HYD-02 단독 2,000 h 패키지 시행. HYD-03 은 허용 오차 안에서 다음 창으로 미룸. 씰 키트 출고 시 재주문점 이하 — 구매 경보 예정."
  - **지는 대안**: 지금 바로 정지(오더 손실 · 시간당 보상), 허용 오차 밖으로 미루기(EXCLUDE), 두 대 묶기(PENALTY).
- **승인**: 설비보전팀장(`role:maint-mgr`, 있음). 한 번이다.
- **승인 뒤 (시스템)**: **병렬 분기**로 셋을 동시에 한다 — CMMS 정비 오더 발행(정비창 포함) ∥ 자재 출고 예약(씰 키트 · 필터) ∥ 생산팀 공지. 합류한 뒤 정비창까지 대기 → 정비 실행(모사: LOTO · 교체 · plant 복구) → 시운전 확인.
- **확인 · 닫힘**: 시운전 15분 동안 PS1 ≥ 178 · FS1 ≥ 8.8 · VS1 정상이면 **계수기 리셋 · 다음 기한 4,000 h 기록** → 종결. 기준 미달이면 공장장(`role:plant-mgr`, 있음)이 확인한다(확인만). A 의 상급자(생산관리자)와 겹치지 않게 공장장으로 둔다.
- **BPMN (주 경로 task 11 — 병렬 3갈래 포함 · 실패 가지 1 · 분기: 병렬 1 + 배타 1 · 칸 4)**

| # | 작업 | 종류 | 칸 |
|---|---|---|---|
| S | 정기 정비 도래 (CMMS) | 메시지 시작 `PM_DUE` | — |
| 1 | 패키지 · 기한 확인 | 에이전트 | 정기 정비 계획 에이전트 |
| 2 | 생산 · 부품 · 묶음 검토 | 에이전트 | 〃 |
| 3 | 정비 일정 제안 | 에이전트 · rank | 〃 |
| 4 | 일정 승인 | 사람 · select_card | 설비보전팀장 |
| P+ | 동시 진행 | 병렬 분기 | — |
| 5a/5b/5c | 정비 오더 발행 / 자재 출고 예약 / 생산팀 공지 | 서비스 ×3 | 시스템 |
| P- | 합류 | 병렬 합류 | — |
| 6 | 정비창까지 대기 | 서비스 · 시간 대기 | 시스템 |
| 7 | 정비 실행 (모사) | 서비스 · plant 복구 | 시스템 |
| 8 | 시운전 확인 | 서비스 · 재관측 변형 | 시스템 |
| G | 기준 통과? | 배타 | — |
| 9 | 계수기 리셋 · 완료 기록 → 끝 | 서비스 | 시스템 |
| 10 | 공장장 확인 (미달 가지) → 끝 | 사람 | 공장장 |

  1 · 2 를 에이전트 task 하나로 합치면 주 경로가 10이 된다(범위 6~10 안). 수업 기본본은 합친 판을 권한다.

- **온톨로지 매핑**
  - 패키지 · 단계: Skill(kind work_order, SOP-PM-2000 · SOP-PM-8000) `-HAS_STEP->` Step(잔압 해제 확인 · 필터 교체 · 프리차지 점검 …) `-REFERS_TO->` ManualSection(OEM 정비표 절).
  - **주기 · 허용 오차는 문장이 아니라 관계**: Rule `TESTS {>=, 2000, h}` → InputData `in:hours-since-pm`(SOURCED_FROM sys:cmms), EXCLUDE 규칙 `TESTS {>, 2200}`. 둘 다 DERIVED_FROM ManualSection 이다. 스키마 규칙("임계값은 관계로")과 맞는다.
  - 생산 · 부품: InputData `in:order-due`(있음) · `in:standby-ready`(있음) · `in:spare-available`(새 인스턴스) · `in:next-window-h`.
  - 부품: Component `-USES_PART->` Part(part:pump-seal, 있음) + 리턴 필터 Part(새 **인스턴스**).
  - **스키마에서 걸리는 곳과 확장 판단(명시)**:
    - Skill 은 고장 유형에 `MITIGATED_BY|REMEDIED_BY` 로 매칭돼야 한다(필수). 그런데 정기 정비는 "생긴 고장을 없애는" 것이 아니라 "고장을 미리 막는" 것이다(EN 13306 예방 정비).
    - (가) 확장 없이 `REMEDIED_BY` 에 잇는다 — 정의 문장("근본적으로 없애는 조치")과 뜻이 어긋난다. 노베이스에게 틀린 관계 이름을 가르치게 된다.
    - (나) **같은 양식 추가 확장 1건 — `(:FailureMode)-[:PREVENTED_BY {_manual_document}]->(:Skill)` N:M, "고장 유형을 미리 막는 정기 정비"(준용 EN 13306 preventive maintenance · ISO 14224 PM).** 필수 조건을 `MITIGATED_BY|REMEDIED_BY|PREVENTED_BY` 로 넓히면 된다.
    - **권고: (나).** 관계 하나로 "시정 · 예방"의 차이가 그래프에 드러나고, 그 차이가 A · B 를 가르는 수업 포인트 자체다. 바꿀 파일은 앞선 문서 §5.C 확장 목록과 같다(schema.json · schema_prompt.md · constraints · seed_checks · class-table · schema-v2 · svg · 시험).
    - 시작 패턴 `PM_DUE` 가 증상(Symptom)에 이어지지 않는 문제는 C 의 `SPARE_BELOW_MIN` 과 같다. 앞선 결정 1(되읽기 단언을 `held`/`plc-trip` 패턴으로 좁힘)을 B · C 에 함께 적용한다. AnomalyPattern 이름이 "이상 패턴"이라 정기 도래와는 어감이 맞지 않는다는 점은 수업에서 "감시 규칙"이라고 부르기로 하고, 클래스는 늘리지 않는다.
- **에이전트 · MCP · 스킬 · 문서**
  - 에이전트: **정기 정비 계획 에이전트** — "기한 안에서 생산 손실이 가장 작은 정비창을 고르고, 부품 영향을 미리 알린다".
  - MCP(읽기): CMMS 계획 · 계수기 · 백로그, MES 오더, CMMS 자재 키트 상태. 재고는 ERP 를 직접 읽지 않고 CMMS 키트 상태로만 본다(C 와 도구를 가르기 위해).
  - 에이전트 스킬: `pm-window-planning` — "기한 · 허용 오차부터 쓰고, 정비창 후보마다 생산 손실 · 부품 영향을 표로 보인다".
  - 문서: **OEM 정기 점검표(교육용, Atos 형식 참고)** — 2,000 h · 4,000 h · 8,000 h 패키지 표, 허용 오차 규정, LOTO 잔압 해제 단계, 시운전 기준.

### 4.C 예비품 구매 — 씰 키트 재고 < 재주문점 (유지)

- **한 문장**: "씰 키트가 곧 모자라니, 규정에 맞고 총비용이 가장 낮은 곳에서 사 둔다."
- **시작**: ERP 재고 감시 `SPARE_BELOW_MIN` (`source: "erp"`). 수업 버튼 = "자재 출고(씰 키트 −2)". 이야기에서는 B 의 출고가 자연스럽게 이 경보를 낸다.
- **에이전트 판단**: 필요량(목표 재고 − 가용 − 입고 예정, 쓰이는 곳)을 산정하고 공급사 셋을 비교한다. 시드 값: A정밀 35만 원 · 불량 12 % · 2일 / B-OEM 55만 원 · 2 % · 5일 / C트레이딩 20만 원 · 30 % · 1일 · 비AVL. 총비용에 불량 기대비용을 더하고, BSC 상충(단가↓ ↔ 품질↓ → 클레임)과 규정(비AVL 금지 · 금액 전결)을 함께 본다.
  - 지는 대안: A정밀은 싸지만 불량 기대비용이 크다. C트레이딩은 비AVL 이라 EXCLUDE 된다.
- **승인**: 구매 담당(새 Role 인스턴스). 300만 원을 넘으면 구매팀장이 추가 승인한다(배타 분기).
- **승인 뒤**: ERP 발주 → 공급사 · 입고 부서 메일 → 입고 대기(경계 타이머: 납기 초과 → 지연 통보).
- **확인**: 입고 확인(ERP).
- 앞선 설계(§5.C)를 그대로 쓴다.

### 4.4 한 공장 이야기로 잇기 (선택, 각 시나리오는 단독으로도 시작된다)

> **월요일 오후** HYD-01 쿨러가 막혀 유온이 오른다(A) → 팬 최대 + 부하 80 % 로 식히고, 핀 세척은 CMMS 통지로 남긴다.
> **수요일** HYD-02 가 운전시간 2,000 h 에 닿는다(B) → 에이전트가 HYD-03 OEM 납기를 피해 HYD-02 만 오늘 밤 정비창에 넣고, 씰 키트를 출고한다.
> **수요일 밤** 출고로 씰 키트가 재주문점 아래가 된다(C) → B-OEM 에 발주하고, 금액이 300만 원을 넘어 구매팀장이 추가 승인한다 → 금요일 입고.

연결은 **데이터로만** 일어난다(A 의 통지가 CMMS 백로그에 남고, B 의 출고가 ERP 재고를 바꾼다). 흐름끼리 서로 부르지 않으므로 엔진 부분집합(하위 프로세스 · 중간 이벤트 없음)을 지킨다.

### 4.5 겹침 행렬 — 추천 조합

칸: **없음** = 다름 / **부분** = 겹치지만 이유 있음(줄이는 방법 병기) / **겹침** = 기각 사유.

| 축 | A × B | A × C | B × C |
|---|---|---|---|
| ⓐ 시작 출처 | 없음 (OT 센서 탐지기 vs CMMS 계획 스케줄러) | 없음 (센서 vs ERP 재고) | 없음 (CMMS 계수기 vs ERP 재고) |
| ⓑ 업무 목적 | 없음 (기능 복구 vs 고장 예방) | 없음 (복구 vs 조달) | 없음 (예방 vs 조달) |
| ⓒ BPMN 모양 | 없음 — A: 승인 타이머 → 명령 → 재관측 → 회복 배타 / B: 승인 → **병렬** 3갈래 → 대기 → 실행 → 시운전 배타 | 없음 — C: 승인 → **금액 배타 + 2차 승인** → 발주 → 입고 경계 타이머 | 없음 (병렬 동시 실행 vs 금액 2단 결재). 둘 다 "대기"가 있지만 B 는 정비창 시각, C 는 공급사 리드타임이다 |
| ⓓ 판단 종류 | 없음 (진단 + 즉시 완화 선택 vs 일정 · 묶음 최적화) | 없음 (진단 vs 공급원 · 수량 선택) | 없음 (언제 vs 어디서 · 얼마) |
| ⓔ MCP · 도구 | **부분** — A 도 MES 오더(납기)를 읽고 B 도 MES 오더(생산 일정)를 읽는다. 이유: 생산 영향은 두 판단 모두의 근거다. 줄이는 법: A 는 `hyd-dmn`(diagnose · forecast_actions)이 주 도구고 MES 는 보조임을 수업에서 구분하거나, A 의 납기 근거를 InputData(`in:order-due`)로만 받는다 | 없음 (hyd-dmn · SCADA vs neo4j 부품 · 공급사 경로 · SCM · ERP 재고) | **부분** — 지금 `enterprise` MCP 하나에 CMMS · MES · SCM · ERP 도구가 모두 있어, **서버 단위로는** 같다. 이유: 서버 안 도구 거르기(X12)가 없다. 줄이는 법: enterprise MCP 를 업무 시스템별로 두 개(보전 = CMMS · MES / 구매 = ERP · SCM)로 나누면 겹침이 사라진다(권장) |
| ⓕ 스킬 · 문서 | 없음 (쿨러 과열 대응 절 · SOP-COOL vs OEM 정기 점검표 · SOP-PM) | 없음 (SOP-COOL vs 구매 규정 PR-07 · SOP-PUR) | **부분** — 같은 Part(씰 키트)를 가리킨다. 이유: B 가 쓰고 C 가 채우는 **연결점**이며, 문서 · SOP · 규칙은 다르다(정비표 vs 구매 규정) |
| ⓖ 승인자 | 없음 (운전원 → 생산관리자 vs 설비보전팀장 → 공장장) | 없음 (운전원 vs 구매 담당 → 구매팀장) | 없음 |
| (참고) 쓰기 시스템 | **부분** — A 의 후속 통지와 B 의 정비 오더가 둘 다 CMMS 에 쓴다. 이유: A 는 인계(통지), B 는 계획 오더 발행으로 트랜잭션이 다르다. 줄이는 법: A 의 후속을 CMMS 통지(`WO_CREATE` 상태 "요청")로, B 를 오더 발행(window 포함)으로 구분 | 없음 | 없음 (CMMS vs ERP) |

**판정**: 기각 사유인 "겹침" 칸은 0이다. 부분 3칸은 모두 이유가 있고, 하나(ⓔ B×C)는 MCP 를 나누면 사라진다.

---

## 5. 차점 조합 — A 긴급 대응 · B 정기 정비 · C′ 입고 검사 · 공급사 품질

- **C′ 한 문장**: "새로 들어온 씰 키트에 불량이 섞인 것 같으니, 받을지 · 조건부로 쓸지 · 돌려보낼지 정한다."
- **시작**: QMS 입고 검사 로트(납품 도착 시 자동 생성 — SAP 검사 유형 01). 수업 버튼 = "B-OEM 아닌 A정밀 로트 20개 납품, 표본 5개 중 1개 치수 이탈".
- **판단**: 표본 결과 vs 합격 기준, 공급사 이력(failRate 0.12), 결품 위험(가용 재고 · 다음 정비창), 비용(반품 · 재발주 · 검사 강화)을 따진다.
  - 대안: 전량 합격 / 특채(전수 선별 뒤 사용) / 반품 + 8D 요청.
  - 상충: 반품하면 결품 위험, 받으면 품질 클레임이다.
- **승인**: 품질팀장(`role:quality-mgr`, 있음).
- **승인 뒤**: QMS 사용 결정 → (반품) 반품 전표 + 공급사 8D 요청 메일 ∥ 대체 입고 요청 → 대체 로트 입고 확인 / (특채) 선별 결과 확인 → 종결.
- **스키마**: Part · Supplier(avl) · SUPPLIED_BY{failRate} · msr:part-quality · msr:quality-claim 은 있다. 로트 · 검사 결과는 클래스 없이 InputData(SOURCED_FROM sys:qms)로 표현할 수 있다. 확장은 필요 없다.

| 축 | A × B | A × C′ | B × C′ |
|---|---|---|---|
| ⓐ 시작 | 없음 | 없음 (센서 vs 납품 · 검사) | 없음 (계수기 vs 납품) |
| ⓑ 목적 | 없음 | 없음 (복구 vs 품질 판정) | 없음 (예방 vs 품질 판정) |
| ⓒ BPMN | 없음 | 없음 (C′: 3갈래 배타 — 합격/특채/반품) | 없음 |
| ⓓ 판단 | 없음 | 없음 (진단 vs 합부 · 처분) | 없음 |
| ⓔ 도구 | 부분 (MES, §4.5 와 같음) | 없음 (QMS · SCM) | 없음 |
| ⓕ 문서 | 없음 | 없음 (수입 검사 기준 · 8D 절차) | **부분** — 같은 Part(씰 키트), 이유는 §4.5 와 같음 |
| ⓖ 승인자 | 없음 | 없음 (품질팀장) | 없음 |

**왜 차점인가**
1. **단독 시작이 덜 자연스럽다.** 사지 않은 물건은 검사할 수 없으니, 이야기상 C(구매) 다음에 오는 업무다. 수업 버튼이 "납품"을 만들어야 한다.
2. **구현이 더 크다.** 입고 · 로트 · 검사 결과 표, QMS 엔드포인트, 반품 효과 부품이 모두 새로 필요하다. 지금 `qms_lots` 는 완제품 로트뿐이다.
3. **닫힘이 외부에 달린다.** 대체 로트 입고 또는 공급사 8D 회신(회사 예 14일)을 기다려야 한다.
4. 대신 판단은 C 보다 풍부하다(③ 4, 대안 셋 · 상충 둘). **C 를 하고 나서 심화 과제나 랩업으로 C′ 를 두는 것**을 권한다.

**검토했지만 차점으로도 못 쓴 조합**
- **A · B(정기) · 경보 합리화**: 경보 합리화의 시작(30일 경보 통계)과 도구(탐지기 · 패턴)가 A 와 부분 이상 겹친다(ⓐ · ⓔ).
- **A · 피크 관리 · C**: 피크는 ⓒ BPMN(명령 → 재관측)과 ⓖ 승인자(생산관리자)가 A 와 겹친다.
- **A · 오일 분석 · C**: 오일은 ⓓ 진단 사슬 · `diagnose` 도구가 A 와 겹친다. 사용자도 이미 "작동유 같은 건 안 해도 된다"고 했다(`실라버스의 문제.txt`).

---

## 6. 지금 A/B/C 와 달라지는 것

| | 지금 | 추천 | 바뀌는 이유 |
|---|---|---|---|
| A | 쿨러 과열 긴급 대응 | 같음 (후속 작업지시를 "CMMS 통지 = 보전에 넘김"으로 명확히) | B 와 CMMS 쓰기 겹침 줄이기 |
| B 주제 | 예지 정비 — 펌프 효율 저하 | **정기 정비 — 운전시간 2,000 h 도래** | 시작 출처를 센서 → CMMS 로 옮겨 A 와 겹침 제거 |
| B 시작 | 새 센서 패턴 `PUMP_DEGRADATION_EARLY` | `PM_DUE` (출처 cmms, 경보 계약 재사용) | |
| B 판단 | 잔여 수명 외삽 vs 리드타임 vs 정비창 | 기한 · 허용 오차 vs 생산 vs 묶음 vs 부품 영향 | 진단이 빠지고 일정 판단만 남음 |
| B BPMN | 직선(예약 → 공지 → 대기 → 실행 → 재관측) | **병렬 분기**(오더 ∥ 자재 예약 ∥ 공지) → 대기 → 실행 → 시운전 | 엔진이 지원하는 병렬을 한 번 쓰게 됨(세 흐름이 서로 다른 분기를 하나씩 보여 줌) |
| B 확인 | 압력 · 유량 회복 | 시운전 기준 + **계수기 리셋 · 다음 기한** | |
| B 확인 실패 담당 | 생산관리자 | 공장장 | A 상급자와 겹침 제거 |
| B 온톨로지 | 진단 사슬 + Forecast | 정비표 Skill · 주기/허용 오차 Rule · (확장) PREVENTED_BY | 확장 1건 권고(§4.B) |
| C | 예비품 구매 | 같음 (시작이 B 출고와 이야기로 이어짐) | — |
| MCP | enterprise 하나 | enterprise 를 보전용 · 구매용 둘로 나누기 권장 | ⓔ B×C 겹침 제거 |
| 펌프 효율 저하 소재 | B 본체 | 버리지 않는다: 이미 있는 `pump_leakage` 결함은 A 형 긴급 대응 회귀 시험(`scenario_pump_fan_test.py`)에 남는다 | |

---

## 7. 수업 구성에 주는 뜻 (짧게)

- 세 시나리오가 **같이 출발해 같이 도착**할 수 있다(사용자 메모의 바람). 막마다 같은 동작(문서 적재 → 에이전트 → BPMN)을 하되, 결과물이 셋 다 다르다.
  - 온톨로지 막: A 는 진단 사슬, B 는 주기 · 허용 오차 규칙과 PREVENTED_BY, C 는 공급사 · 상충 · 금액 규칙.
  - 에이전트 막: 셋이 각각 무엇/언제/어디서·얼마를 묻는다.
  - BPMN 막: A 는 타이머 · 재관측, B 는 병렬, C 는 금액 분기 · 2차 승인.
- **경보 합리화**는 세 시나리오 밖의 **랩업 소재**로 좋다. "에이전트가 경보 통계를 보고 기준값 변경을 제안 → 승인 → 온톨로지 TESTS 값 수정 → 탐지기가 다시 읽음(poll_catalog) → 다음 기간 경보 수 확인." 온톨로지를 고치면 시스템 행동이 바뀐다는 것을 보여 주는 SDD 과제로 맞다. 단, 경보 기준 완화는 실무에서 MOC 대상이라고 함께 가르친다.

---

## 8. 구현 영향 (지금 A/B/C 대비 증감)

**줄어드는 것 (예지 B 를 버려서)**
- 새 센서 패턴 `PUMP_DEGRADATION_EARLY`, 추세 외삽 도구(`hyd-prognostics` 선택 서버), 효율 재관측이 "명령 없이 작업지시로 닫힌 사건"에서 도는지 확인(X7의 일부).

**같이 쓰는 것 (앞선 문서 §10 번호)**
- X1 업무 DB 감시기: C 의 ERP 재고 감시를 **"업무 표 기준값 감시기" 하나로 일반화**하면 B(CMMS 계수기)와 C(ERP 재고)가 같은 코드로 시작된다. 출처 값만 `cmms` / `erp` 로 다르다. B7 `human_alert` 와 같은 경보 계약을 쓴다.
- X2 승인 뒤 MCP 알림, X5 시간 대기, X6 plant 복구 모사 — B 에 그대로 필요하다.
- X4 작업지시에 정비창(window) 전달 — B 의 정비 오더 발행에 필요하다.

**새로 생기는 것 (B)**
1. 업무 DB: `ent.pm_plans`(설비 · 패키지 · 주기 h · 허용 오차 %) · `ent.run_counters`(설비별 운전시간 · 마지막 정비 h) + 수업 버튼 "운전시간 +N h" + enterprise-sim/MCP 읽기 도구(`cmms_pm_plans`, `cmms_counters`).
2. 계수기 증가: plant RUN 시간 × 배속을 계수기에 더하는 작은 작업(또는 버튼만으로 증가 — 교육용으로는 버튼만으로 충분).
3. 효과 부품 둘: 자재 출고 예약(ERP 예약 → C 의 가용 재고를 실제로 줄임), 계수기 리셋 · 완료 기록(CMMS).
4. 시운전 확인: 경보 없이 연 사건에서 "기준값 N분 유지" 재관측 변형. 기존 `incident:reobserve` 의 회복 기준을 패턴별 계약에 `PM_DUE` 용으로 하나 더한다(B7 `policy` 와 같은 방식).
5. 병렬 분기: 가져오기는 이미 지원한다(`bpmn_import.py`). 병렬 가지 안의 효과 부품이 모두 승인 뒤에 있으므로 안전 검사(B3) 조건을 만족한다. **실제 병렬 실행 시험은 아직 없다 — 확인 필요.**
6. 온톨로지: `PREVENTED_BY` 확장(권고) · 정비표 Skill/Rule 은 B 문서 적재로 넣는다. 적재 확장(K1~K3)은 앞선 문서와 같다.
7. 에이전트 시험 실행 목록에 `PM_DUE` 추가(X11).

**규모 감각**: 예지 B 대비 새 코드는 비슷하거나 약간 작다. 센서 · 예측 쪽 일이 빠지고 업무 DB 표 · 효과 부품 둘이 늘어난다. 가장 큰 공통 일(적재 확장 K1~K3, 승인 뒤 MCP 부품 X2)은 그대로다.

**사용자가 정할 것**
1. B 를 운전시간 정기 정비로 바꾸는가(권고: 예).
2. `PREVENTED_BY` 확장을 하는가(권고: 예. 안 하면 REMEDIED_BY 로 대신하되 정의와 어긋남을 수업에서 밝힌다).
3. enterprise MCP 를 보전용 · 구매용으로 나누는가(권고: 예. 아니면 X12 도구 거르기).
4. B 확인 실패 담당을 공장장으로 두는가(A 의 생산관리자와 분리).

---

## 9. 출처

[2차] 2차 요약 · [업체] 업체 주장 · [포럼] 커뮤니티 글.

**정비 시작 · 정기 정비 · 예지**
- SAP Learning, Modeling Maintenance Processing (반응 4HH · 예방 4HI, 긴급 작업은 선별 생략): https://learning.sap.com/courses/exploring-business-processes-in-sap-s-4hana-asset-management/modelling-maintenance-processing_b8e0e043-315c-42e3-bc4f-7f0dfaa12325
- SAP Learning, Scheduling a Time-Based Strategy Plan: https://learning.sap.com/courses/exploring-preventive-maintenance-in-sap-s-4hana-asset-management/scheduling-a-time-based-strategy-plan
- SAP Help, Scheduling Parameters (shift factor · 허용 오차 · 호출 기간 · 완료 요건): https://help.sap.com/doc/2194c1536ca9b54ce10000000a174cb4/1610%20002/en-US/b515c253d0a4b54ce10000000a174cb4.html
- SAP Community 블로그, Scheduling parameters in maintenance plan [포럼]: https://blogs.sap.com/t5/enterprise-resource-planning-blogs-by-members/scheduling-parameters-in-maintenance-plan/ba-p/13573122
- SAP Community, counter-based maintenance planning [포럼]: https://answers.sap.com/t5/enterprise-resource-planning-q-a/counter-based-maintenance-planning/qaq-p/9900989
- Oxmaint, SAP PM 예방 정비 설정 체크리스트(500/1000/2000 h 패키지 예) [업체]: https://oxmaint.com/sap-integration/sap-pm-preventive-maintenance-setup-checklist
- IBM Support, Maximo 시간 + 계수기 PM: https://www.ibm.com/support/pages/node/1112139
- Atos MAN-C-012 파워팩 매뉴얼 (작동유 2,000~3,000 h · 필터 · 프리차지 3개월 · 쿨러 6개월 · 보증 중 기록 의무): https://www.atos.com/tables/french/MAN-C-012.pdf
- DGUV IFA BIA 5031-2 (호스 교체 6년): https://www.dguv.de/ifa/forschung/projektverzeichnis/bia_5031-2.jsp
- Reliabilityweb, Work Order Completion: https://reliabilityweb.com/tips/article/work_order_completion
- Reliamag, P-F curve: https://reliamag.com/articles/what-is-a-p-f-curve/
- Oxmaint community, 기회 정비(DNV 인용) [포럼]: https://community.oxmaint.com/discussion-forum/maximizing-plant-maintenance-efficiency-through-opportunity-based-pm-scheduling
- Tractian, maintenance window [업체]: https://tractian.com/en/glossary/maintenance-window

**구매 · 입고 검사 · 보증**
- SAP Community, MRP type VB [포럼]: https://answers.sap.com/questions/5375545/mrp-type-vb.html
- SAP Community, PR release process [포럼]: https://community.sap.com/t5/enterprise-resource-planning-q-a/pr-release-process/qaq-p/4482145
- SAP Community, MRBR price/qty/quality [포럼]: https://answers.sap.com/questions/7309087/mrbr-price-qty-and-quality.html
- IBM docs, Maximo item reorder 추천: https://www.ibm.com/docs/en/SS3KH6/iot-mmio-docs/using/item_rec.html
- Oxmaint, 예비품 중요도 · 결품 방지 [업체]: https://oxmaint.com/industries/manufacturing-plant/manufacturing-stockout-prevention-for-maintenance-parts
- Guru99, SAP QM 품질 통지: https://www.guru99.com/quality-notification-sap-qm.html
- Keysight RCCA Guideline (공급사 회신 기한): https://about.keysight.com/en/supplier/KeysightRCCA_Guideline.pdf
- Applied, Parker warranty [2차]: https://content.applied.com/parker-warranty
- Milnor, Warranty claims: https://milnor.com/technical-knowledge-base/bulletins/maintenance-2/warranty-claims
- Coupa 보도 (구매 에이전트) [업체]: https://www.coupa.com/newsroom/coupas-newest-release-expands-agentic-ai-collaboration-and-orchestration-capabilities/
- MDM, Verusen MRO 에이전트 [업체]: https://www.mdm.com/news/technology/technology-provider-news/verusen-launches-explainable-ai-agent-to-boost-mro-optimization/

**오일 · 교정 · 안전 · 유출 · MOC**
- HYDAC ISO 4406 포스터: https://www.hydac.com/media/local_resources_usa/downloads/services/hyd1811-2050_iso_poster_pn2091838_printer.pdf
- Eaton, Water in Oil: https://www.crossco.com/wp-content/uploads/2019/07/Eaton_Water_in_Oil1.pdf
- Machinery Lubrication, What to Do When Your Oil Analysis Results Go South: https://www.machinerylubrication.com/Articles/Print/1106?id=1106
- Machinery Lubrication, Setting Limits and Targets: https://www.machinerylubrication.com/Articles/Print/28520?id=28520
- In Compliance, As-found out of tolerance: https://incompliancemag.com/as-found-out-of-tolerance-what-to-do-next/
- Emerson, 압력 전송기 교정 주기 계산: https://d1-live.emerson.com/documents/automation/technical-note-how-to-calculate-pressure-transmitter-calibration-intervals-en-7432098.pdf
- EPA SPCC 유출 보고 fact sheet: https://19january2021snapshot.epa.gov/sites/static/files/2014-06/documents/spccfactsheetspillreportingdec06-1.pdf
- HSE HSG250 (작업 허가 역할): https://www.hse.gov.uk/pubns/books/hsg250.htm
- AIChE MOC 발표: https://aiche.org/sites/default/files/community/258271/aiche-community-site-page/258701/moc-dallasaicheapril242012.pdf
- (앞선 문서) OSHA 1910.147: https://www.osha.gov/laws-regs/regulations/standardnumber/1910/1910.147/

**에너지 · 경보 · 인수인계 · 산업 AI**
- Elum Energy, demand charges [업체]: https://elum-energy.com/blog/demand-charges-explained-how-utilities-calculate-peak-power-costs/
- DOE ISO 50001 eGuide: https://www1.eere.energy.gov/manufacturing/eguide/iso_step_5_1.html
- Process Online, ISA-18.2 Part 1/2 [2차]: https://www.processonline.com.au/content/software-it/article/improving-alarm-management-with-isa-18-2-part-1-37009763 · https://www.processonline.com.au/articles/65390-Improving-alarm-management-with-ISA-18-2-Part-2
- Emerson, alarm management: https://www.emerson.com/documents/automation/alarm-management-en-57058.pdf
- HSE, shift handover: https://www.hse.gov.uk/humanfactors/topics/shift-handover.htm
- Honeywell 운전 보조 출시 [업체]: https://www.honeywell.com/us/en/press/2026/03/honeywell-unveils-commercial-launch-of-ai-powered-control-room-assistant-following-successful-pilot
- IBM Maximo Assistant [업체]: https://www.ibm.com/new/announcements/introducing-maximo-assistant-an-ai-resource-for-teams
- Cognite Atlas AI docs [업체]: https://docs.cognite.com/cdf/atlas_ai/concepts
- Aker BP × Cognite [업체]: https://akerbp.com/aker-bp-leverages-cognite-atlas-ai-to-pioneer-an-ai-first-future-in-exploration-and-production/
- AI Business, Microsoft 공장 에이전트 [업체]: https://aibusiness.com/generative-ai/microsoft-launches-new-ai-agents-for-factory-automation-hannover-messe-2025
- Automation.com, Siemens Industrial Copilot [업체]: https://www.automation.com/en-us/products/march-2025/siemens-industrial-copilot-generative-ai

**확인 못 한 것**: 파워팩 OEM 매뉴얼 원문(Rexroth · Parker · Eaton · HYDAC · Yuken), 정기 정비 연기 한도에 대한 권위 있는 규칙, SAP 정비 승인자 역할 이름(설정에 따라 다름), KEPCO 공식 약관 원문(계절 적용 여부가 출처마다 다름), ISA-18.2 원문의 승인자 규정.
