# U11 · A8 KPI 실적 · 역추적 (2026-10-08 밤, 읽기 전용)

범위: `TODO.md` 확정 TODO §1 A8(실라버스 16·52행, 짝 랩업 L8 "BSC KPI·상충"), §2 L7·L8 행 "지식 지도 · A8 KPI".
완료 기준(TODO): 손계산과 일치, 원천 없는 지표는 사유. 마이그레이션 없음(읽기만 하므로 `…36` 미사용).

## 1. 원본 근거 (process-gpt-vue3 @ `scratchpad/refs-A/process-gpt-vue3`, 읽기만)
| 원본 | 파일:줄 | HYD에서 가져온 것 |
|---|---|---|
| KPI 대시보드 라우트 | `src/router/MainRoutes.ts:695-696` (`/analytics/kpi` → `views/analytics/KPIDashboard.vue`) | 목표 대비 달성률 카드 · 달성률 막대 |
| 전략 보드 라우트 | `src/router/MainRoutes.ts:705-706` (`/strategy-board` → `views/strategy/StrategyBoard.vue`) | 관점 → 목표 → 지표 묶음, 목표 간 연결(받치는 목표) |
| 관리 › KPI 목표 | `src/router/MainRoutes.ts:573-574` (`kpi-targets` → `KpiIndicatorManager.vue`) | 넣지 않음 — 목표값은 온톨로지 Measure.target 고정(스키마 고정) |
| 달성률 계산 | `src/views/analytics/KPIDashboard.vue:141-153` (목표 달성도 평균) | 지표별 달성률(방향 UP/DOWN 고려), 평균은 내지 않음 |

## 2. HYD와의 차이 (① 결함인가 ② 회의·계약 요구를 못 채우는가)
- vue3는 strategy 서비스가 달성률을 받아 그리기만 한다. HYD에는 그런 서비스가 없어 **실적을 직접 계산**한다(원천 3곳). 차이 있음, 요구(A8 "처리 기록·업무 DB로 실적") 때문에 필요.
- vue3는 목표 편집이 있다. HYD는 스키마·기준 데이터 고정이라 **읽기 전용**. 차이 있음, 유지.
- vue3에는 미달 역추적이 없다. HYD는 온톨로지 INFLUENCES · AFFECTS · SUPPORTS와 처리 기록으로 **원인 처리 건 · 조치 · 설비**를 고른다(A8 요구).
- 평균 종합 달성도는 내지 않는다 — 계산 불가 지표가 많아 평균이 거짓 인상을 준다.

## 3. 구조와 데이터 리니지
```
지식 그래프 Measure(목표값·방향·식·kpiRole) ─┐
시계열 DB tag_1m · alerts ────────────────────┼─ procsvc/kpi.py report() ─ GET /api/kpi ─ portal kpi.js (관점→목표→지표 카드)
업무 DB ent.* · 처리 기록 bpm_proc_inst ───────┘        └ trace() ─ GET /api/kpi/trace?measure= ─ "원인 찾기" 패널 (#/instances/<id>)
```
- 실패 · 분기: 원천 하나가 실패하면 그 원천을 쓰는 지표만 `조회 실패 — 사유`(0을 내지 않음). 그래프가 죽으면 지표 목록·목표값이 없으므로 화면 전체가 503 + 사유.
- 시계열 · 업무 DB는 읽기 전용 트랜잭션(쓰기 시도 시 `cannot execute INSERT in a read-only transaction` — 실측), 그래프는 `execute_read`.
- 시간: 시계열은 벽시계, MTBF의 시간은 설비 시간(벽시계 × `TIME_SCALE` 20).

## 4. 지표별 계산 정의 표 (`kpi.py` `DEFINITIONS`, 21개)
| 지표 | 원천 표 · 열 | 식 / 계산 불가 사유 |
|---|---|---|
| 설비 가동률 (목표 95 %) | 시계열 `tag_1m`(TS1 관측 분) · `alerts`(pattern `*_TRIP` 발생~해제) | 100 × Σ(관측 분 − 보호 정지 분) ÷ Σ 관측 분, 기간 경계로 자름 |
| 평균 고장 간격 (2000 h) | 같은 표 | Σ 운전 시간(설비 h) ÷ 기간 안에 시작한 보호 정지 수; 0건이면 "기록 없음 — 운전 N h 동안 고장 0건" |
| 인터록 여유 (10 ℃) | 그래프 StateVariable.limit(이 지표에 INFLUENCES) · Sensor.tag, 시계열 `tag_1m.max` | 한계 − 기간 최고값, 설비 중 최솟값 |
| 전력 사용량 | `tag_1m` EPS1 avg(kW) | Σ 평균 kW × 24 (팬 전력 태그 없음) |
| 에너지비 | EPS1 + `ent.energy_demand.energy_rate` | kWh/일 × 30 × 요율 |
| 보전비 | `ent.work_orders`(취소 제외) + `ent.maintenance_profiles.clean_cost` | 세척 작업만 비용 원천 → 나머지는 **부분 실적 + 사유** |
| 부품 구매비 · 부품 단가 · 부품 품질 | `ent.purchase_requests` + `ent.suppliers`·`ent.parts` | 견적 부품 = 요청 부품일 때만 단가(요청 1건 = 1개); 아니면 부분 실적 + 사유 |
| 재고량 | `ent.fg_inventory.fg_stock` | Σ 현재값(이력 없음 → 기간 무관) |
| 판단 선례 축적 | `bpm_proc_inst.variables_data.chosen_skill` | 기간 처리 건 중 사람이 조치를 고른 건 수 |
| 영업이익 · 총비용 | 그래프 `Measure.formula` 문자열 | 식을 풀어 구성 지표 실적으로 계산, 하나라도 못 하면 계산 불가(구성 지표 이름·상태 나열) |
| 매출 | — | 판매·매출 원장 없음(hour_value는 계획값, shipments는 단가 없음) |
| 재고 보관비 | — | 보관 단가 열 없음 |
| 지체상금 · 납기 준수율 | — | 오더 완료·출하 시각 없음(due_at·penalty_per_h만) |
| 품질 클레임 | — | 클레임 접수 표 없음 |
| 브랜드 신뢰 | — | 설문·평가 원천 없음 |
| 생산량 | — | 생산 카운터 태그·MES 실적 없음(LoadSP는 설정값) |
| 작동유 잔여 수명 | — | 산화도·수분·교환 기록 없음(TS1은 요인일 뿐) |

판정: 목표 있음 → 달성/미달 + 달성률(UP: 실적÷목표, DOWN: 목표÷실적, 목표 0이면 0 이하만 100 %), 목표 없음 → "목표 없음", 원천 일부만 → "부분 실적"(달성 판정 안 함).

## 5. 역추적 (`trace()`)
1. 그래프: `(x)-[:INFLUENCES*1..4]->(지표)` 경로마다 부호의 곱 → 상태 변수·지표별 "오르면 개선/악화/경로마다 다름"과 경로 문장.
2. 경로의 상태 변수를 보는 이상 패턴(TESTS → InputData → REPRESENTS), 흔드는 원인(DISTURBS), 움직이는 조치(AFFECTS — 좋은/나쁜 경로를 모두 표시).
3. 처리 기록(같은 기간): 지표를 깎은 기록(보호 정지 경보 · 최고 유온 시각)과 경보 id 일치 / 그 시각에 열려 있던 처리 건 / 관련 패턴 / 관련 원인 / 나쁜 경로가 있는 조치를 사유로 붙임. 순서 = 깎은 크기 → 경보 당사자 → 근거 수 → 최근.
4. 설비: 설비별 실적 미달 먼저. 걸린 목표(SUPPORTS)는 접기. 각 처리 건은 `#/instances/<id>` 링크(화면에 id 문자열은 안 보임).

## 6. 바꾼 파일
- 새 파일: `it/process/procsvc/kpi.py`(계산 · 역추적 · 라우트), `it/portal/www/kpi.js`(`window.hydKpi.mount(el)`), `it/portal/www/kpi.css`, `tests/test_kpi.py`.
- 최소 수정: `it/process/procsvc/main.py`(+5줄 `kpi.register`), `it/portal/www/index.html`(메뉴 버튼 1 · `#view-kpi > #kpiView` · css/js 각 1줄). U7 셸 재편 시 `hydKpi.mount(el)`만 부르면 된다(kpi.js는 `#view-kpi`가 열리면 스스로 mount).

## 7. 시험
- `tests/test_kpi.py` 18개: 시드 cypher를 읽어 만든 가짜 그래프 + 알려진 기록으로 **손계산 일치**(가동률 3260/3600 = 90.56 %, 달성률 95.3 %; MTBF 1086.67 h ÷ 2 = 543.3 h; 여유 65 − 66.2 = −1.2; 전력 201.6 kWh/일; 에너지비 90.72 만원/월; 재고 1200; 선례 3), 계산 불가 사유 8개 + 합성 지표 구성 이름, 부분 실적, **일부러 깨뜨리기**(시계열 끊김 → 그 지표만 "조회 실패 — connection refused", 처리 기록만 끊김, 그래프 끊김 → 503 사유, 빈 기록 → "기록 없음" 사유), 기간 필터가 모든 원천에 닿음, 역추적 순서·사유·링크, 라우트 GET 3개뿐 · 404/400/503, process 앱에 마운트, node로 화면 그리기(카드 21 · 원인 찾기 3 · 영문 id 노출 0).
- 전체 `pytest -q`: **1302 passed**(기준 1284 + 18).
- 실제 SQL 경로: 임시 PostgreSQL 16에 Supabase 마이그레이션 25개 + seed 적용, 시계열 표(tag_1m · alerts 같은 열)와 기간 밖 · 취소 · 삭제 행을 섞어 넣고 `PgSources`로 계산 → 11개 지표 손계산과 **모두 일치**, 역추적 순서 동일, 쓰기 거부, 없는 표 · 끊긴 연결 사유 확인. 화면은 같은 API에 붙여 Playwright로 캡처. 증거 `.evidence/a8-kpi/`(live_sql.log · live_sql_report.json · kpi_overview.png · kpi_trace_availability.png · kpi_mobile.png). 임시 DB · 서버는 끄고 지움.
- 하지 않은 것: Neo4j 실물에 Cypher 실행(가짜 그래프로 대신), compose 라이브(메인 통합 검증에서).

## 8. 남은 확인 (통합 검증 때)
- 라이브: 처리 건 몇 개 돌린 뒤 `GET :8080/api/kpi?period=1h`에서 가동률 · 선례가 움직이는지, `/api/kpi/trace?measure=msr:availability`의 처리 건 링크가 U7 해시 라우팅으로 열리는지.
- 체크 질문(사용자 판정용): ① 계산 불가 10개의 사유가 "업무 DB에 그 열이 정말 없다"와 맞는가 ② 보호 정지(트립)만 고장으로 세는 MTBF 정의가 수업 의도와 맞는가 ③ 보전비를 세척 비용만 아는 "부분 실적"으로 두는 것이 맞는가(다른 작업 비용 열을 업무 DB에 둘지는 스키마 결정).
