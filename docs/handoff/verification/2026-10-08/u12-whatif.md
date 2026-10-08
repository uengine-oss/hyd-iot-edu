# U12 · A7 손익 · What-if · 규칙 바꿔 보기 (2026-10-08 밤, 시험 실행만)

범위: 메인 `TODO.md` 확정 TODO §0 · §1 **A7**(실라버스 33 · 35 · 36행) · 실험 **E1**(값 → 경계값) · **E2**(규칙 가중치 · 감점) · §2 **L17** 행
("조치 판단 규칙 · A7 E2 · A10") · 아래쪽 "다음 할 일 — What-if"의 의도 · DoD 1~4.
완료 기준(TODO): 손익이 업무 DB 값에서 계산, 경계값에서 실제 순위 변경, 원본 불변. 마이그레이션 `20261008000037`.

## 1. 원본 근거 (읽기만)

| 원본 | 파일:줄 (고정 커밋) | 원본이 하는 일 | HYD에서 한 것 |
|---|---|---|---|
| ontologic `what-if-simulator` | `edge_based_simulation.py:48-79` (`e72adf1`) | 간선 하나 = `EdgeModel`(극성 ± · 지연 · 계수), 효과 = 계수 × 부호 × (원인 값 − 기준) | 조치 → 설비 값 → 지표를 **영향 계수**로 잇는다. 계수마다 출처 종류(데이터 · 문서 · 가정)를 붙인다 |
| 같은 곳 | `edge_based_simulation.py:424-470` | 시나리오의 시간 단계(기본 12개월) 루프, 환율 · 판가 전가율 등 driver 값을 단계마다 넣고 위상 순서로 노드 갱신 | **주 단위**(1~12주) 루프, 변수 **하나**만 바꾼 결과를 기준과 나란히 |
| 같은 곳 | `api/main.py:397-420` | 데이터로 영향 함수 추정(`estimate_influence_functions`) + MindsDB 모델 | 넣지 않음 — 인과 자동 발견 · 학습 함수 · MindsDB 제외(TODO "레포 통째 이식 하지 않음") |
| ontology-studio | `backend/src/modules/ontology/causal_client.py:1-12` (`20afcde`) | 온톨로지 서비스는 계산하지 않고 domain-layer What-if API에 행을 보냄 | 별도 서비스 없이 에이전트 서비스 안의 순수 모듈(`whatif.py`)로 — "가볍게" |
| process-gpt-vue3 | `src/router/MainRoutes.ts` (`867e8cf`) — What-if · 시뮬레이션 라우트 0건 | 제품 화면에 What-if 없음 | 화면 배치만 vue3식(요약 → 탭 → 접기) |

## 2. HYD와의 차이 (① 결함인가 ② 회의 · 계약 요구를 못 채우는가)
- 원본은 계수를 데이터로 학습한다. HYD는 **업무 DB 필드 · 지식 그래프 · 설비 모델 문서 · 명시 가정**에서 계수를 가져와 출처 종류를 화면에 보인다.
  학습 데이터(월별 KPI 이력)가 HYD에 없으므로 학습하면 근거 없는 수가 된다 — 차이 있음, 유지.
- 원본은 월 단위 · 환율 driver. HYD는 사건 한 건의 조치 비교라 **납기까지의 손익(①)** 과 **주 단위(③)** 두 시간 축을 둔다. 회의 L386~413(가치의 상충)을 돈으로 보이는 것이 목적.
- 원본은 정책 순위가 없다. HYD는 기존 판단(정책 점수 순위, `cards.evaluate`)을 **그대로 다시 부르고**, 손익 순위를 옆에 둔다. 두 1순위가 다르면 "가치의 상충"으로 표시.

## 3. 구조와 데이터 리니지
```
지식 그래프(T3 규칙 · 스킬 · 상충 경로) ─┐
시계열 · PLC 상태(예측 입력)            ├─ decide.decide(capture=…) ─ 기준 묶음(bundle, 메모리 세션 WI-…)
업무 DB InputData(납기 · 위약금 · 로트)  ─┘                                 │
업무 DB 읽기 GET: /mes/orders · /erp/contract · /cmms/history · /qms/lots ·    │
  /ems/demand · /cmms/tasks(새) · /scm/suppliers?part=…  ─ whatif.load_money_facts ─ money facts(값마다 시스템 · 필드 · 경로)
                                                                             ▼
POST /api/agent/whatif            기준: evaluate(bundle, mf) → 카드별 판단 순위 · 정책 점수 · 손익(원) · 손익 순위 · 요약
POST /api/agent/whatif/{id}/try    시험값 · 규칙 시험값 → 사본 사실 · 사본 정책으로 cards.evaluate 재호출 + 손익 재계산
POST /api/agent/whatif/{id}/boundaries  축(시험값 8개 + 순위 항목 가중치 7개 + 감점 규칙)마다 격자 훑기 → 이분 → 그 값으로 재계산 확인
POST /api/agent/whatif/{id}/weeks  카드 하나 · 값 하나 → 주별 가동률 · 생산량 · 매출 · 비용 · 이익 · 누적 이익 + 계수 표
POST /api/agent/decide(기존)       카드마다 money 추가(업무 DB를 못 읽으면 moneyError 사유, 0을 넣지 않음)
                                                                             ▼
포털 whatif.js(#/whatif, window.hydWhatif.mount) · enterprise.js 조치 카드의 "예상 손익" 접기(hydWhatif.moneyFold)
```
- 실패 · 분기: 업무 DB 읽기 실패 → 기준 생성 503 + "업무 DB를 읽지 못했습니다 (경로): 사유". 값 하나가 없으면 그 값을 쓰는 항목만 **미확인**(합계 없음 · 손익 순위 제외 · 사유 표시).
  잘못된 시험값 · 규칙 → 400 + 한국어 사유. 세션이 없으면(에이전트 재시작) 404 "다시 불러오세요".
- 원본 불변: 세션을 만들 때 묶음 + 업무 DB 값의 지문을 저장하고, 시험 응답마다 다시 계산해 다르면 500(결과를 쓰지 않음). 쓰기 경로(POST `/api/exec` 등) 호출 0.

## 4. ① 카드별 손익 (`whatif.card_money`, 기간 = 납기까지 남은 시간 H, 비용은 음수, 원 = 만원 × 10,000)

| 항목 | 식 | 출처(업무 DB 필드 · 문서 · 가정) |
|---|---|---|
| 생산 감소 | 시간당 생산 가치 × (H × (1 − 부하/90) + 작업 정지 h) | MES `hour_value` · `due_in_h`, 카드 부하 명령(LOAD_SET), 설계 부하 90 %(설비 모델), CMMS 표준 작업 `stop_h` |
| 납기 지연 위약금 | 위약금/h × max(0, 정지 h + 잔량 ÷ (생산 속도 × 부하/90) − H) | ERP `penalty_per_h`, MES `remaining_qty` · `rate_per_h` · `due_in_h` |
| 품질 클레임 위험 | 예측 유온 ≥ 55 ℃이고 출하 대기 로트 > 0이면 불량 확률 × 클레임 | QMS `auto_defect_p` · `auto_claim` · `auto_qty`, 카드 예측 유온, 매뉴얼 HM-7.5 55 ℃ |
| 고장 위험 | 원인이 남는 카드만 고장 비용 × H ÷ MTBF (근본 조치 카드 0) | ERP `failure_cost`, CMMS `mtbf_h`, 가정(원인 유지 시 고장 확률) |
| 정비 작업비 | 카드 작업지시(WO_CREATE)의 표준 작업비 합 | CMMS 표준 작업 `labor_cost`(쿨러 핀 세척은 설비별 `clean_cost`) |
| 부품비 | 표준 작업의 필요 부품 × (구매요청 공급사 견적, 없으면 표준단가) × (1 + 부품값 %) × (1 + 환율 % × 1.0) | SCM `price`/`std_price`, 시험값, 가정(환율 1 % → 수입 부품값 1 %, 방향은 그래프 ext:fx → msr:part-price +) |
| 에너지비(팬) | 팬 변화 %p × 팬 최대 추가 kW ÷ 40 %p × H × 전력 단가 | EMS `fan_boost_kw` · `energy_rate`, 설비 모델 정상 팬 60 % |

손익 순위 = 규정상 가능하고 모든 항목이 계산된 카드 중 합계가 큰(덜 잃는) 순, 동점이면 판단 순위.
시드(쿨러 HYD-01, 납기 6 h) 결과: 팬 최대 + 부하 80 % −373,532원(1위) · 팬 최대 −1,543,605원 · 부하 70 % + 야간 세척 −6,735,397원 · 쿨러 핀 세척(규정상 제외) −5,860,000원.

**업무 DB에 없던 값 → 마이그레이션 `20261008000037_cmms_task_standards.sql`(추가만)**: `ent.task_standards`(SOP별 정지 h · 작업비 · 필요 부품, 쿨러 핀 세척은
`maintenance_profiles`를 따름) · `ent.cmms_tasks(asset)` 읽기 RPC · 부품 표준단가 2행(씰 50만원 · 베어링 25만원). RLS 읽기 정책 · `hyd_enterprise_reader` 권한 포함 →
enterprise-mcp `query`/`describe_catalog`로도 보인다. memory 백엔드(`entsim/data.py`)에 같은 값 · `GET /cmms/tasks`.
같이 고친 것: memory `scm_suppliers`가 부품을 거르지 않아 씰을 물으면 코어 견적을 돌려주던 것 → Supabase 함수처럼 그 부품 견적만, 모르는 부품은 404.
차이 있음, 유지: 그래프의 씰 · 베어링 공급사 견적(`SUPPLIED_BY`)은 `ent.suppliers` 키가 공급사 하나당 한 부품이라 업무 DB에 넣지 않고 표준단가만 둔다.

## 5. ② 값 바꿔 보기 · 경계값 (`whatif.find_boundaries`)
- 시험값: 납기 · 위약금 · 클레임(판단 사실 `order_due_h` · `order_penalty_per_h` · `hot_lot_claim`에도 같이 들어가 **판단 순위도 다시 계산**), 시간당 생산 가치 · 고장 비용 · MTBF · 부품값 % · 환율 % · 전력 단가(손익만).
- 경계값: 축마다 범위(기본 0 ~ 기준 × 10, % 축은 고정 범위)를 40칸으로 훑어 1순위를 구하고, 카드마다 기준값에서 가장 가까운 "그 카드가 1순위가 되는 칸"(1순위 카드는 "1순위를 잃는 칸")을 찾아 이분(40회) →
  보기 좋은 자리로 반올림하되 바뀐 쪽에 남기고 → **그 값으로 다시 계산해 1순위가 실제로 바뀐 것만** 보고한다(`verified`).
- 시드 결과 예: 손익 — 클레임 3,000만원 → 662만원 이하이면 손익 1순위 '팬 최대', 납기 5.95 h → 27.01 h 이상이면 '팬 최대', 시간당 생산 가치 50 → 225.1만원 이상이면 '팬 최대'.
  판단 — 순위 항목 '예측' 가중치 1 → 0.277배 이하이면 '부하 70 % + 야간 세척', '성과 지표' 가중치 3.458배 이상이면 '팬 최대'. (시드 묶음에서 납기 · 위약금 · 클레임 하나만으로는 판단 1순위가 바뀌지 않음 — 화면에 "바꾸는 값이 없습니다")
- 화면: 카드마다 "1순위가 바뀌는 값" 접기, 줄마다 "이 값으로 계산" → 그 시험값으로 다시 계산해 요약에 "1순위가 …에서 바뀌었습니다".

## 6. ③ 몇 주 What-if (`whatif.weeks`) — 영향 계수와 출처 종류

| 계수 | 값(시드) | 종류 |
|---|---|---|
| 조치 부하 · 팬 변화 (조치 → 설비 값) | 카드 명령 / 시험값 | 문서(온톨로지 스킬 명령) |
| 부하 1 %당 생산 수량 (설비 값 → 생산량) | 300 ÷ 90 ea/h | 데이터(MES) |
| 수량 1개당 생산 가치 (생산량 → 매출) | 50 ÷ 300 만원/ea | 데이터(MES) |
| 작업 정지 시간 (첫 주, 조치 → 가동률) | 표준 작업 h | 데이터(CMMS) |
| MTBF · 주별 고장 확률(= 주 운전 h ÷ MTBF) | 1,400 h · 0.086 | 데이터 · 가정 |
| 고장 1회 비용 · 고장 시 정지 시간 | 900만원 · 근본 조치 표준 작업 h | 데이터(ERP · CMMS) + 가정 |
| 팬 1 %p당 전력 · 전력 단가 | 6 ÷ 40 kW · 0.015만원/kWh | 데이터(EMS) |
| 주 운전 시간 | 120 h | 가정(바꿀 수 있음) |
| 근본 조치 뒤 복귀 · 완화 설정 유지 | 규칙 | 가정 |

주마다: 가동률 = (주 h − 정지 − 고장 확률 × 고장 정지 h) ÷ 주 h, 생산량 = 속도 × 부하/90 × 운전 h, 매출 = 생산량 × 개당 가치, 비용 = 에너지 + 고장 위험 + (첫 주) 작업비 · 부품비 · 품질 · 위약금, 이익 = 매출 − 비용.
완화 카드는 설정과 고장 위험이 기간 내내, 근본 조치 카드는 첫 주만. 난수 · 현재 시각 없음 → 같은 입력 같은 결과(시험).
시드 예: '팬 최대 + 부하 80 %' 4주 누적 이익 +209,359,402원, 부하 80 → 70 %이면 +182,175,592원(−27,183,810원).

## 7. ④ 규칙 바꿔 보기 (`whatif.check_policy` · `apply_policy`)
- 순위 정책 항목 하나의 가중치 k(−10 ~ 10): 그 항목 식을 `k * (식)`으로 감싼 **사본**을 `ranking.validate`(같은 안전 식 검사)로 다시 검사한 뒤 계산.
- 감점 규칙 하나의 감점(0 ~ 1000): `dec:compliance` PENALTY 규칙 사본의 `penalty`만 바꿈. 없는 항목 · 감점 규칙이 아닌 규칙은 400.
- L17 랩업(위험 조치 빼는 판단 규칙)과 비교: 랩업에서 만든 규칙의 효과를 포털에서 가중치 · 감점으로 흉내 내 같은 1순위 변화가 나오는지 본다(정답은 강사가 수업에서 유도, 코드에 없음).

## 8. 바꾼 파일
- 새 파일: `it/agent/agentsvc/whatif.py`, `it/portal/www/whatif.js`, `it/supabase/migrations/20261008000037_cmms_task_standards.sql`, `tests/test_whatif.py`, 이 문서.
- 최소 수정: `it/agent/agentsvc/main.py`(엔드포인트 4개 + decide에 손익), `it/agent/agentsvc/decide.py`(`capture` 인자 — 판단 입력 묶음을 넘김),
  `common/hydcommon/ranking.py`(검사한 식 트리 캐시 `lru_cache` — 경계값 탐색 34 s → 1.4 s, 동작 같음),
  `it/enterprise-sim/entsim/{data,main,supabase_backend}.py`(`/cmms/tasks`, 부품별 SCM), `it/portal/www/enterprise.js`(카드 손익 접기 1줄 · 손익 오류 1줄),
  `it/portal/www/index.html`(스크립트 1줄 — 셸 U7의 `#view-whatif` · `whatifView` 사용).

## 9. 시험 결과
- `tests/test_whatif.py` 15건: 손익 항목이 업무 DB 값(엔터프라이즈 시뮬레이터 실제 HTTP 계약)에서 계산 · 모든 항목 출처 · 화면 문장에 영문 id 0 / 값이 빠지면 0이 아니라 미확인 /
  부품 표준단가 · 환율 시험값 / 기존 판단 순위 그대로 / **모든 경계값을 그 값으로 다시 계산해 1순위가 실제로 바뀌고, 경계 바로 앞은 원래 1순위** / 클레임 경계 /
  시험값 · 규칙 검사 사유 / 가중치 하나로 판단 순위 변경(E2) / 감점 하나는 그 규칙이 걸린 카드 점수만 / **원본 묶음 · 정책 · 업무 DB 불변, 쓰기 호출 0, 거래 기록 0** /
  주별 결과 결정성 · 지표 4개 이상 · 계수마다 출처 / 완화 vs 근본 조치 / CMMS 표준 작업 계약(memory · supabase · 마이그레이션) / 에이전트 API 끝까지 / decide 손익 · 업무 DB 장애 사유.
- 일부러 깨뜨리기(돌연변이 4건 모두 잡힘): 시간당 가치를 상수로 → 1 실패, 경계값을 바뀌기 전 쪽으로 → 3 실패, 정책 사본 없이 원본 수정 → 4 실패, 미확인을 0으로 합산 → 1 실패.
- 전체 `pytest -q`: **1299 passed**(기준 1284 + 15).
- 브라우저(Playwright, 시드 묶음을 쓰는 에이전트 API + 정적 포털, docker 없음): 불러오기 → 요약 · 4탭, 경계값 "이 값으로 계산" → 손익 1순위 변경 표시, 원래대로 → 기준, 주별 계산, 규칙 가중치 '예측' 0배 → 판단 1순위 변경 + "가치의 상충",
  조치 판단 규칙 화면 카드 4장 모두 "예상 손익" 접기, 화면 영문 id 0, 콘솔 오류 0. 캡처 · 스크립트 `.evidence/u12-whatif/`(worktree).

## 10. 라이브 확인 경로 (합친 뒤, 메인 통합 검증 때)
1. 마이그레이션 적용(`cd it/supabase && npx -y supabase start` 또는 `supabase migration up`), `ENTERPRISE_BACKEND=supabase`로 enterprise-sim · agent 재기동.
2. `curl -s localhost:8095/cmms/tasks?asset=HYD-01` → 4행(쿨러 핀 세척 source=maintenance_profiles).
3. `curl -s -XPOST localhost:8091/api/agent/whatif -H 'content-type: application/json' -d '{"asset":"HYD-01","pattern":"COOLER_DEGRADATION"}'` → `cards[].money.complete`, `original.unchanged`.
4. 포털 `#/whatif` → 불러오기 → 카드별 손익 · 경계값 "이 값으로 계산" · 몇 주 · 규칙. 조치 판단 규칙 화면 카드의 "예상 손익" 접기.
5. 확인 후 `curl localhost:8095/api/transactions`에 What-if로 생긴 기록 0.

## 11. 남은 것 · 미검증
- 라이브 Neo4j · 시계열 · Supabase에서의 실행은 미검증(이 단위는 docker 금지). 마이그레이션 SQL은 정적 시험(문자열)만 — 적용은 통합 검증에서.
- 실제 그래프의 펌프 · 팬 후보로 경계값이 나오는지는 라이브에서 확인 필요(시드 묶음은 쿨러).
- enterprise-mcp 고정 읽기(7개)에 `cmms_tasks`는 넣지 않음 — `query`/`describe_catalog`로 표가 보인다.
- HANDOFF §9 · 실라버스 33 · 35 · 36 "개발 예정" 지우기는 메인이 합칠 때.

## 12. 비유와 스스로 판정할 체크 질문
- 비유: 경계값은 "저울이 기우는 추의 무게"다 — 추(시험값)를 얼마 올리면 저울(1순위)이 반대로 기우는지 실제로 올려 보고 적는다.
- 체크 질문: ① 카드의 손익 항목마다 업무 DB 어느 화면 · 어느 값에서 왔는지 출처 칸만 보고 말할 수 있나? ② 경계값 "이 값으로 계산"을 눌렀을 때 요약의 1순위가 정말 바뀌나?
  ③ 몇 주 What-if의 계수 중 "가정"인 것은 무엇이고, 그 가정을 바꾸면(주 운전 시간) 결론이 뒤집히나? ④ "원래대로" 뒤 승인과 실행 화면 · 업무 DB 거래 기록에 아무것도 늘지 않았나?
