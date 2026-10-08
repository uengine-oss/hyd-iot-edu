# 원본(ProcessGPT·온톨로지 레포) 대비 HYD에 빠진 것 — TODO 기록 (2026-10-08, 작업 A 1단계)

**이 문서는 할 일 기록이다. 구현하지 않았다.** 구현 순서·범위는 이 목록을 본 뒤 따로 견적·승인한다(GOAL "2026-10-08 작업 A 인수조건" DoD 2).
실라버스 세션 B는 이 목록의 기능이 "개발되었다고 가정"하고 단원을 짤 수 있다(HANDOFF_실라버스교재 §7). 학생 자료에는 "개발 예정"으로 표시한다.

**어떻게 찾았나(사용자 10-08 "구멍이 있는지 봐야 해, What-if는 예시일 뿐, 회의 내용을 잘 봐, 레포 보고 가져오면 좋을 기능을 넓게")**
- 원본 레포 47개 목록(`sources/repository-map/repository_urls.txt`) 중 관련 레포를 실제로 클론해 코드를 읽었다(비공개 포함). 레포·커밋·파일:줄은 부록 A~C의 1절과 표의 "원본 근거" 칸.
- 갈래 4개를 나눠 읽었다: A 업무 흐름 플랫폼(부록 A) · B 에이전트·툴·MCP·스킬(부록 B) · C 온톨로지·데이터·전략(부록 C) · D 회의 원문 1~461행 전수 대조(부록 D, 회의 요구 55행).
- 근거 규칙(사용자 확정): 회의 근거는 `sources/meeting-2.txt` 하나. `meeting-1.txt`는 다른 사업 자료라 근거로 쓰지 않는다. Text2SQL 전용 엔진은 목록에 넣지 않는다(HYD는 에이전트가 스키마·메트릭을 보고 SQL·PromQL을 직접 만듦).
- "지금 HYD" 칸은 HYD 코드에서 확인한 것이다(파일:줄은 부록 표). 크기는 모두 **예상**이다. 원본 서비스는 실행하지 않았다(코드 읽기 근거).
- 사람이 대조한 것: 각 갈래의 핵심 주장 일부를 원문으로 다시 확인했다 — 워커가 정의의 `skills`를 읽고 쓰지 않음(`it/agent-worker/worker/context.py:89`, runner 사용 0), 고정한 cliagents `7c7a392`에 `add_skill` 있음(`src/cliagents/artifacts.py:115`), 프롬프트가 에이전트 이름·역할만 씀(`worker/prompt.py:158-160`), 경보 흐름이 환경변수 파일로 고정(`it/process/procsvc/instance_mode.py:39`), 회의 인용 L63-67·L136-138·L405-406·L448 원문 일치.

## 1. 한눈에 보기 (쉬운 말)

강의 가치: 상 = 한 막의 중심이 될 만함 · 중 = 한 장면 · 하 = 곁가지. 만들기 크기(예상): 작음 = 기존 기능에 조금 · 중간 = 새 기능 한 덩어리 · 큼 = 새 층·새 엔진.

| 번호 | 쉽게 말하면 (수강생이 해 보는 것) | 회의에서 나온 말인가 (meeting-2 줄) | 지금 HYD | 강의 가치 | 만들기 크기 | 참고할 원본 레포 |
|---|---|---|---|---|---|---|
| **P. 업무 흐름(프로세스) 플랫폼** | | | | | | |
| P1 | 말이나 문서로 업무 흐름을 만들고, 실제로 돌려 보며 고친다 | 예 (448, 436) | 사람이 JSON을 손으로 씀 | 상 | 중간 | bpmn-process-generation-skill, process-gpt-vue3, completion |
| P2 | 흐름에 "이 입력이면 이렇게 끝나야 한다"는 시험을 걸어 두고, 고칠 때마다 자동으로 확인한다 | 예 (136-138) | 없음 | 상 | 중간 | completion `test_mode.py`, vue3 단위 시험 패널 |
| P3 | 흐름을 바꿀 때 초안 → 검토·승인 → 배포 순서로 하고, 무엇이 바뀌었는지 설명받고 되돌린다 | 예 (448) | 판본 등록만 됨. 경보는 고정 파일 흐름만 씀 | 상 | 중간 | process-gpt DB, vue3 검토 게시판 |
| P4 | 판단 규칙표를 말로 만들고, 규칙마다 시험해서 맞는지 확인한다 | 예 (23-24, 301-302) | 규칙 엔진은 있으나 만들기·시험 화면 없음 | 상 | 중간 | vue3 DMN 생성기·규칙 시험기 |
| P5 | AI가 여러 번 한 일을 코드로 굳혀, 다음부터는 AI 없이 같은 결과를 낸다(비용·시간 비교) | 아니오 | 없음 | 상 | 큼 | completion `deterministic_generator.py` |
| P6 | 끝난 처리 건을 모아 어디서 오래 걸리는지(병목), 재작업, AI 대 사람 시간을 본다 | 예 (434-435) | 건별 화면만 있음 | 중 | 중간 | process-gpt-analytic |
| P7 | 매일·매주 정해진 때에 흐름이 저절로 시작되게 한다(예방 점검) | 아니오 | 경보·수동 시작만 | 중 | 작음~중간 | process-gpt pg_cron, vue3 일정 생성기 |
| P8 | 흐름 안에 작은 계산 코드 작업을 넣는다 | 아니오 | 없음 | 중 | 중간 | completion `code_executor.py` |
| P9 | 큰 흐름 안에 작은 흐름을 넣고, 설비 수만큼 나눠 돌린다 | 아니오 | 없음(이전 결정으로 범위 밖) | 중 | 큼 | completion 하위 흐름 처리 |
| P10 | 사람에게 가는 알림을 알림함·메신저로 받고 버튼만 누른다 | 예 (405-406, 417-420, 426) | 알림을 저장만 함 | 중 | 작음~중간 | process-gpt 알림, vue3 알림함 |
| P11 | 조직도·역할을 만들고, 흐름의 역할에 실제 사람을 연결·위임한다 | 예 (406, 413) | 일부(역할 바인딩만) | 중 | 중간 | vue3 조직도 생성기, 위임 이력 |
| P12 | 처리 건을 내용으로 자동 분류해 자주 오는 유형과 비슷한 과거 건을 본다 | 예 (7-8) | 일부 | 하 | 중간 | process-gpt-instance-classifier |
| P13 | 업무 흐름을 대·중·소 체계도로 정리한다 | 아니오 | 없음 | 하 | 작음 | vue3 업무 체계도 |
| P14 | 검증된 흐름 묶음을 마켓에서 가져다 고쳐 쓴다 | 아니오 | 없음 | 하 | 작음 | vue3 마켓플레이스 |
| P15 | 처리 건을 칸반·간트·달력으로 보고 채팅으로 협업한다 | 아니오 | 없음 | 하 | 중간 | vue3 칸반·채팅 |
| **A. 에이전트·툴(MCP)·스킬** | | | | | | |
| A1 | AI가 따를 작업 요령(스킬 문서)을 직접 써서 붙이면, AI가 일하는 순서가 바뀌는 것을 본다 | 예 (132-135, 399-404) | 없음(정의에 적어도 버려짐) | 상 | 작음 | process-gpt-cli-agent `core/skills.py`, cliagents |
| A2 | 에이전트를 직접 만든다: 이름·역할·목표·쓸 도구·스킬·모델을 정해 업무 단계에 배정 | 예 (146-156, 172, 434-435) | 이름·역할 한 줄만 쓰임 | 상 | 중간 | vue3 에이전트 설정 화면, cli-agent 서브에이전트 |
| A3 | 직접 만든 도구 서버(MCP)를 등록하고, 붙이기 전에 제대로 연결되는지 검사한다 | 예 (88-96, 105-112, 123-138) | DB에 손으로 넣음, 검사 없음 | 상 | 중간 | process-gpt-mcp-validator, vue3 MCP 설정 |
| A4 | 업무 시스템 자체를 도구(MCP)로 만들어, 대화 중인 AI가 흐름을 시작·조회하게 한다 | 아니오 | 없음 | 중~상 | 작음~중간 | base-agent `process-gpt-mcp` |
| A5 | 쌓인 처리 기록에서 AI가 규칙·스킬 개선안을 내고, 사람이 승인해야만 반영된다 | 예 (7-8, 448) | 일부(선례만 읽음) | 상 | 큼 | process-gpt-agent-feedback |
| A6 | 스킬이 정말 도움이 되는지, 있을 때와 없을 때를 같은 시험으로 채점해 비교한다 | 예 (136-138) | 없음 | 상 | 중간 | process-gpt-deepagents 스킬 평가 |
| A7 | 규칙·스킬을 바꾸기 전에 예전 사례를 바꾸기 전·후로 돌려 "망가진 게 없나" 확인한다 | 예 (448) | 강사용 시험만 있음 | 상 | 중간 | deepagents `pr_verification.py` |
| A8 | 업무 AI와 똑같은 설정으로 바로 대화해 시험하고, 알려 준 것을 기억하는지 본다 | 예 (93-96) | 없음 | 중 | 중간 | completion `agent_chat.py` |
| A9 | 일하는 중인 AI에게 멈추지 않고 지시를 덧붙인다 | 아니오 | 없음(취소·질문만) | 중 | 중간 | agent-sdk `steering.py` |
| A10 | "이런 에이전트가 필요해"라고 말하면 AI가 에이전트 설정 초안을 자동으로 만든다 | 아니오 | 없음 | 중 | 작음 | vue3 에이전트 생성기 |
| A11 | 같은 일을 Claude Code·Codex 등 다른 AI로 돌려 비용·시간·결과를 비교한다 | 아니오 | 일부 | 중하 | 작음~중간 | vue3 에이전트 모니터, llm-factory |
| A12 | 도구 서버 비밀번호를 설정과 분리해 안전하게 둔다 | 아니오 | 일부(시드에 평문) | 하~중 | 작음 | vue3 비밀값 설정 |
| A13 | 외부 AI 에이전트에게 일을 맡긴다(A2A) | 아니오 | 없음 | 하 | 중간 | process-gpt-a2a-orch |
| **O. 온톨로지·데이터·전략** | | | | | | |
| O1 | 환율·부품값·조치를 바꿔 몇 주 동안 가동률·비용·이익이 어떻게 변하는지 시뮬레이션한다(What-if) | 예 (374-378, 386-413) | 부호만 있음 | 상 | 큼 | ontologic `what-if-simulator` |
| O2 | 처리 기록에서 KPI 실제 값을 계산해 목표 대비 달성률을 본다 | 예 (5-10) | 목표값만 있음 | 상 | 중간 | process-gpt-strategy |
| O3 | 목표에 못 미친 KPI에서 원인 업무·조치·설비로 거슬러 올라간다 | 예 (5-8) | 없음 | 상 | 중간 | process-gpt-strategy |
| O4 | 여러 종류 DB를 옮기지 않고 한 창구로 묶어 묻는다(데이터 패브릭) | 예 (63-67, 438-447) | 없음 | 상 | 큼 | ontologic `data-fabric` |
| O5 | 온톨로지 클래스를 DB 표에 묶어, 클래스가 자기 데이터를 직접 가져오게 한다 | 예 (51-58, 63-67) | 일부 | 상 | 중간 | ontologic spec 001 |
| O6 | AI와 대화하며 회사 목표·지표 지도(BSC)를 만들고, 틀린 곳을 기준으로 짚는다 | 예 (1-14, 6, 28) | 일부(미리 넣어 둔 지도) | 상 | 중간 | process-gpt-strategy-skill |
| O7 | "답하고 싶은 질문"을 먼저 적으면 AI가 온톨로지 초안을 내고, 고친 뒤 실제로 답이 나오는지 확인한다 | 예 (1-14, 253-271, 284) | 일부 | 상 | 중간 | ontology-studio |
| O8 | 이름이 암호 같은 옛 DB에서 AI가 뜻과 관계를 복원하고, 사람이 승인한다 | 예 (286-293, 253-271) | 없음 | 상 | 큼 | robo-data-catalog, ontologic spec 008 |
| O9 | 데이터가 어디서 나와 어디로 흘러가는지(계보) 그래프로 보고, 틀린 값을 거꾸로 따라간다 | 아니오 | 없음 | 상(조건부) | 중간 | robo-data-analyzer |
| O10 | 매뉴얼에 나온 값이 DB의 어느 칸에 있는지 AI가 후보를 내고, 애매하면 사람이 고른다 | 예 (51-58, 63-67) | 일부 | 중 | 중간 | ontologic |
| O11 | 데이터로 "무엇이 무엇을 움직이나" 후보를 찾고, 가설로만 표시해 사람이 판정한다 | 예 (386-413) | 없음 | 중 | 큼 | what-if-simulator `causal_discovery` |
| O12 | What-if 계수를 과거 데이터로 맞춰 보고 오차로 믿을 만한지 판정한다 | 아니오 | 없음 | 중 | 중간 | what-if-simulator |
| O13 | 문서에서 뽑은 지식이 품질 점수에 따라 자동 적재·검토 대기·보류로 나뉜다 | 아니오 | 일부 | 중 | 중간 | ontology-studio quality |
| O14 | 전략 목표마다 실행 과제를 두고 실제 업무 흐름으로 잇는다 | 예 (5) | 없음 | 중 | 작음~중간 | process-gpt-strategy |
| O15 | 역할마다 볼 수 있는 데이터가 다르고 민감한 칸은 가려지며, AI에게도 똑같이 걸린다 | 아니오 | 일부 | 중 | 중간 | robo-data-security-guard |
| O16 | KPI 성과에 어떤 사람·AI가 얼마나 기여했는지 계산한다 | 아니오 | 없음 | 중 | 중간 | process-gpt-strategy |
| O17 | 온톨로지에서 대시보드가 자동으로 만들어진다 | 예 (434) | 없음 | 중 | 중간 | ontology-studio |
| O18 | 여러 시스템에서 같은 설비가 다른 코드로 들어와도 "같다"고 묶는다 | 아니오 | 없음 | 중~하 | 중간 | ontologic |
| O19 | 현장 용어의 동의어를 용어집으로 관리해, AI가 다른 말로 물어도 같은 데이터를 찾는다 | 아니오 | 일부 | 하 | 작음 | process-gpt-glossary |
| **M. 회의 원문에서 찾은 구멍 (위와 겹치지 않는 것)** | | | | | | |
| M1 | 같은 경보를 AI에 여러 번 던져 진단·조치 카드를 정답표로 채점하고, 온톨로지를 고치기 전·후로 나아졌는지 숫자로 본다 | 예 (136-138 "온톨로지가 잘 구성됐는지 체크하는 방법") | 매뉴얼 골든 질문·강사용 검사만 | 상 | 중간 | process-gpt-deepagents 스킬 평가(A6과 짝) |
| M2 | 부품 견적·제품 원가·에너지 사용량을 회사 DB에서 읽는다("값은 DB에, 그래프엔 위치만" 원칙을 예외 없이) | 예 (63-67, 75-79, 375-377) | 펌프 씰·팬 베어링 견적이 그래프에만 있음 | 중 | 작음 | process-gpt-strategy `ontology_sync.py` |
| M3 | 포털에서 지금 어떤 AI 일꾼이 무슨 작업을 잡고 있는지 본다 | 예 (202-214, 434-435) | API는 있으나 화면에서 안 부름 | 중 | 작음 | process-gpt-vue3 에이전트 모니터 |
| M4 | 과정 후반에 같은 쿨러 사건을 실제 ProcessGPT 제품에서 돌려, 직접 만든 부품이 제품의 어디에 해당하는지 본다 | 예 (172) | 대응표 설명뿐 | 중 | 큼 | process-gpt-completion, vue3 |
| M5 | HYD 틀을 다른 설비 하나에 옮겨 적용해 보며 현장에 쓰려면 무엇을 바꿔야 하는지 본다 | 예 (456-457) | 없음 | 하 | 중간 | ontology-studio |

## 2. 이미 TODO·진행 중인 것과의 관계

- 이미 `TODO.md`에 있는 것: 금전 손익 비교(회의 L350-353·L385-388) — 이 표에 다시 넣지 않음. What-if = O1(+O11·O12 계수·인과). 교재 1차 초안 — 그대로.
- `verification/2026-10-08/value-gaps.md` 10개 대응: #1→M1·A6 · #2→O6 · #3→O2·O3 · #4→A5 · #5 로트 처분(회의 meeting-2 직접 발언 없음, 대표발언 2차 인용만 — 그대로 유지) · #6→O4 · #7→O8 · #8→P1·P3 · #9→P5 · #10→O11.
- 회의 갈래에서 위 표와 같은 것: "사고 기록 → 규칙 개선 승인 순환" = A5 · "흐름을 바꾸면 다음 경보부터 적용" = P3(경보가 고정 파일만 씀 — `instance_mode.py:39`, 결함에 가까움) · "담당자별 알림·할 일" = P10.
- 랩업(막마다 Claude Code로 만들어 보기)은 목록이 아니라 작업 A 3단계(DoD 4)에서 진행.
- 기존 결정과 부딪히는 것(넣을지 사용자 결정): O4 데이터 패브릭 — HANDOFF §2 "후반 설명만"(사용자 10-08 "개발 가정"으로 바뀜, §2 갱신 필요) · O11 인과 발견 — TODO What-if "인과 자동 발견 이식은 하지 않는다" · P9 하위 흐름·다중 인스턴스 — DECISIONS 95 "범위 밖".

## 3. 갈래별 추천 상위 (각 부록 마지막 절 요약)

- 업무 흐름: P1 말로 흐름 만들기 → P2 흐름 시험(SDD) → P3 변경 관리·다음 경보부터 적용 → P4 규칙 만들기·시험 → P5 AI 일을 코드로 굳히기.
- 에이전트·툴: A1 스킬 붙이기(가장 작음) → A3 MCP 등록·검사 → A2 에이전트 만들기 → A7 바꾸기 전·후 회귀 → A6 스킬 채점.
- 온톨로지·데이터: O1 What-if(+O12) → O2·O3 KPI 실적·역추적 → O5→O4 클래스-표 바인딩 후 데이터 패브릭 → O7·O6 스키마·전략맵 만드는 과정 → O8·O9 옛 DB 뜻 복원·계보.
- 회의 구멍: M1 AI 판단 채점 → P3 → A5 → M2 부품 견적 DB로 → M3 에이전트 현황 화면.

## 부록 A — 업무 흐름(프로세스) 플랫폼 상세 (P1~P15 = 아래 표 #1~#15)

작성 2026-10-08, 읽기 전용 조사(저장소 파일 변경 없음). 갈래 G1 = 정의 생성·편집·버전·배포·폼, 엔진(스크립트·서브프로세스·다중 인스턴스·정기 시작), 시험 실행, 고착화, 인스턴스 분석, 알림·채팅·일정, 조직·역할, 마켓플레이스·체계도.
G2(에이전트·툴·MCP)·G3(온톨로지·데이터·전략)와 겹치는 것은 "→G2/G3" 한 줄로만 표시. **크기는 모두 예상**(착수 전 조사로 다시 정한다).
조사 기준(코디네이터 10-08): 회의 근거는 `docs/handoff/sources/meeting-2.txt`만(1~461행). meeting-1은 근거로 쓰지 않음. Text2SQL 전용 엔진은 목록에서 제외. 행마다 레포@커밋·경로.

### 1. 읽은 것 / 못 읽은 것

#### 원본 레포 (클론 위치 `/tmp/claude-0/refs/<repo>`, 비공개 3개는 `/home/user/<repo>`에 받고 refs로 복사)

| 레포(지도 번호) | 커밋(전체 SHA, 커밋일) | 읽은 파일:줄 |
|---|---|---|
| process-gpt (C01) | 6084127a57e013ae319331ba9a04bb97ef8aa961 (10-08) | `docker-infra/volumes/db/init.sql` 테이블 목록 전수(L130~3424), L273~334(proc_def·arcv·version·form_def), L439~512(delegation_history·chat_rooms·chats·calendar·user_permissions), L513~539(marketplace), L556~595(project·task_dependency), L1756~1790(register_cron_job/pg_cron) |
| process-gpt-vue3 (C02) | a4f0a851a5e2680c860ed4e2ccf73ad8e1ee7dec (10-08) | `src/router/MainRoutes.ts` 전체 라우트 전수(L28~773), `src/components/ai/` 생성기 47개 목록 + ProcessDefinitionGenerator·ExecutableProcessGenerator L39~61·FormDesignGenerator L41~74·DmnGenerator L16~23·ConditionRuleGenerator L20·CronRuleGenerator L47·SubprocessRuleGenerator L34·BpmnDiffGenerator L7·49·OrganizationChartGenerator L16, `components/api/ProcessGPTBackend.ts` L3565~3580(dryRun 빈 구현)·L3826~3835(알림 구독)·L5759~5866(마켓)·L11635~11680(test API), `components/apps/definition-map/TestProcess.vue` L905~916, `ProcessUnitTestPanel.vue` L391~411·L638~690, `views/review-board/ProcessReviewBoard.vue` L1~40, `views/process-hierarchy/VersionComparison.vue` L1~45, `views/analytics/BottleneckAnalysis.vue` L1~20·L260~330, `views/apps/chat/Chats.vue` L747~758, `components/scheduler/ScheduleList.vue` 전문, `supabase/migrations/20260130000001_proc_def_comments_approval.sql` L36~85, `20260213000001_kpi_review_board.sql` 머리 |
| process-gpt-completion (C03) | b272c9ab458f3ca3e18fe286e4e770d291b99e89 (10-01, 이미 있던 클론 재사용) | 루트 파일 목록·크기, `test_mode.py` L1~30·L505, `validate_improve.py` L1~12·L294, `dashboard_api.py` L1~10·L1350~1353, `operational_board_api.py` L1~10·L584~609, `work_history.py` 머리, `deterministic_generator.py` L1~30·함수 목록, `polling_service/workitem_processor.py` L1188·L1397·L1659·L1901·L1928·L3787·L4431·L5026(함수 위치), `polling_service/database.py` L2171, `polling_service/code_executor.py` L1~41 |
| process-gpt-agent-sdk (C07) | 4d8f3b6c872bd37cf669788dbba2ccc0eb7c0f67 (10-08) | `processgpt_agent_sdk/function.sql` L1~80(DRAFT/COMPLETE 집기) — G2 영역이라 확인만 |
| process-gpt-session-router (C08, 비공개) | a5edf5cce9d3449d5e7ac3c3c27e1f47b69ad3b3 (09-18) | `README.md` L1~40 |
| process-gpt-k8s (C06, 비공개) | 3022aaf946505dfdc7d2d70f794b344423100d4d (10-08) | 디렉터리·`deployments/` 목록(fcm-service·keda·n8n·session-router 등) |
| process-gpt-infra-docker (C05) | 9e854852f1a0143f5234273fc2314f307be4c48d (10-06) | 클론만(기존 REFERENCE_ADOPTION C05 결론 재사용) |
| process-gpt-gateway (C04) | 2567edc18a22ce70f96bf0fda0bf774c7aa8c162 (04-02) | 클론만(인프라, G1 기능 없음) |
| bpmn-process-generation-skill (D01) | f8c4b6d55b921817fa4ab9e088e77956fccdf75f (07-26) | `SKILL.md` L1~40(5단계 표), `references/` 00~12 목록, `scripts/`(validate_process.py·save_to_supabase.py), `evals/evals.json` 존재 |
| process-gpt-docs.github.io (D03) | ad6944ffb48f84c53c8d6bc7e5a4f9e04e216b15 (07-26) | `content/ko/advanced-features/` 17개 제목 전수 + simulation·multi-instance·process-marketplace·deterministic-regularization·reference-info·admin-guide·user-guide·feedback-system·dmn 본문, `tutorial/tutorial-lv1·lv3` 본문, lv2·4·5 제목 |
| process-gpt-bpmn-extractor (T02) | c7992ce95e90492647411980a3034653784137e6 (08-04) | `src/pdf2bpmn/` 모듈 목록, `validation/process_validator.py`(1,315줄, 기존 T02 조사 재사용) |
| process-gpt-analytic (P01, 비공개) | a6dbb1acfff9fa58d1aad05d745a00343d43d5ea (07-26) | `backend/app/main.py` 라우트 전수(L118~1058), 모듈 목록 |
| process-gpt-instance-classifier (P02) | 384a6ff277f10d789868b0f9c8c72dcb998a84ed (07-08) | `app/server.py` 라우트(L51~259), 모듈 목록 |
| process-gpt-agent-feedback (P04) | 84d2a0e3535d43e8b311e9068503d9d5dc3d9a4f (09-23) | 다시 읽지 않음(teachable 3 결론 재사용) |
| process-gpt-sample-app-wms (D05) | 8ba09f4420ba04d094a0fc4a05c72bc38b0b8a52 (07-31) | `scripts/` 목록, `install_processgpt_integration.py` L20·L185·L503~527(정의를 코드로 설치) |
| process-gpt-mobile (X01) | 0fa1143876710c5fb351a55eccb31a9e35e8becb (09-30) | `README.md` L1~15(웹뷰 껍데기+푸시) |
| process-gpt-crewai-action (X03) | ecdf8debfe92f779841eaff807fcd5cac9003e61 (04-02) | 파일 목록(→G2) |

#### HYD (기준선, 커밋 6033768f93dfaf1dc866985f9e769688c32bf7e5)
`docs/handoff/verification/2026-10-08/value-gaps.md`·`teachable-candidates.md` 전문, `REPO_GAP.md` 전문, `REFERENCE_ADOPTION.md` 머리 + C01·C02·C03·C07·C08·D01·D03·T02·P01·P02·X03 행, `HANDOFF_실라버스교재.md` §7, `sources/meeting-2.txt` 1~461행, `sources/repository-map/REPOSITORY_MAP.md` C01~C08·P01~P04·D01~D05·X01~X03, `docs/definition-authoring.md` 전문, `it/process/procsvc/` 라우트 전수(main.py·instance_mode.py·manual_api.py), `engine.py` L1~110·L270~345, `instances.py` L685~720, `instance_mode.py` L39·L131·L562~889, `definition_registry.py` 함수 목록, `procdb.py` L113~177·L402~430·L724~760, `it/portal/www/` 파일 목록·`index.html` 메뉴 L19~34·`definitionRegistry.js` 전문 함수·`flow.js`·`instanceSteps.js`·`liveStream.js`·`taskDeferral.js` 머리, `it/agent-worker/worker/` 목록·DRAFT 처리 주석.

#### 못 읽은 것
- process-gpt-completion은 10-01 클론(b272c9a)을 재사용했다. 이후 커밋의 변경은 **미확인**.
- vue3 화면은 코드만 읽고 띄워 보지 않았다(화면 동작 **미검증**). 특히 ProcessGPT 모드의 `dryRun`/`startAndComplete`는 빈 구현(ProcessGPTBackend.ts:3565~3580)이라 "시뮬레이션 모드"가 ProcessGPT 백엔드에서 어디까지 실제로 도는지는 **미확인** — 단위 테스트(`/completion/test/*`)는 completion `test_mode.py`에 실물 확인.
- 체크포인트(체크리스트) 완료 판정: 문서(tutorial-lv3 L35~51)와 `deterministic_generator.py` 머리는 "폴링이 체크포인트를 평가"한다고 쓰나, REPO_GAP §3은 "코드상 주석 처리"라 기록 — 상충, **미확인**(표에서 뺌).
- process-gpt-k8s의 fcm-service·agent-router 소스: 매니페스트만 있음(REFERENCE_ADOPTION "확인 불가"와 같음).

### 2. 표 — HYD에 빠진 G1 기능 (가치 순)

판정: **빠짐** = HYD에 해당 기능 없음, **얕음** = 일부만 있음. 레포 표기 `레포@짧은SHA 경로:줄`(전체 SHA는 1절).

| # | 빠진 기능 (수강생이 ~해서 ~를 알아보기) | 원본 근거 | HYD 현재 | 판정 | 강의 가치 | 구현 크기(예상) | 랩업 후보 | 회의 근거 줄 | value-gaps/teachable 대응 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **말·문서로 실행 가능한 업무 흐름(정의+폼+참조정보)을 만들고, 엔진에 실제로 돌려 고쳐지는 것을 보며 "프로세스를 코드 없이 바꾼다"를 알아보기** | process-gpt-vue3@a4f0a85 `src/components/ai/ProcessDefinitionGenerator.js:13-14`·`ExecutableProcessGenerator.js:39-61`(실행 엔진용 정의 변환)·`FormDesignGenerator.js:41-74`(폼 자동 생성), `src/router/MainRoutes.ts:126-137`(정의·폼 채팅 화면); process-gpt-completion@b272c9a `validate_improve.py:1-12,294`(초안을 실제 엔진 /initiate·/complete로 돌려 추적 + LLM 보정 루프); bpmn-process-generation-skill@f8c4b6d `SKILL.md` 5단계 표(컨설팅→JSON→스킬·DMN 후보→폼·참조정보→자체검증 최대 2회); process-gpt-bpmn-extractor@c7992ce `src/pdf2bpmn/validation/process_validator.py`(1,315줄); process-gpt-docs@ad6944f `content/ko/advanced-features/admin-guide.md:9-50`(PDF·화이트보드 이미지→BPMN, 폼·데이터 링크 자동) | 사람이 JSON을 손으로 작성(`docs/definition-authoring.md:1-19`), 등록 API `it/process/procsvc/instance_mode.py:587`, 정적 검사 `definition_registry.py:14,196,234`, 포털 파일 등록 `it/portal/www/definitionRegistry.js:51,61`. 생성기·폼 생성·실행 추적 보정 없음 | 얕음 | **상** — meeting-2 L448의 ProcessGPT 존재 이유를 학생 손으로 확인, 이후 단원(시험·변경관리·고착화)의 출발점 | 중간 — 생성은 D01 스킬을 Claude Code에 그대로 쓰고, HYD 등록기 형식 변환(save_to_supabase.py flatten 모양은 A116에서 수용)·등록 거부 사유를 되먹이는 왕복 절차·예제 3개 | Claude Code에 D01 스킬을 붙여 "정기 점검 결과 검토" 흐름을 말로 만들고 → `POST /api/process/definitions`의 400 사유를 다시 넣어 고치고 → 실행해 콘솔에 단계 전이 로그 | L448 "프로세스들을 자유롭게 바꾸고… 프로세스피티 같은게 필요", L436 "구현하다 보면 프로세스 gpt가 되어 버립니다" | value-gaps 8, teachable 4 (실행 추적 검증·폼 생성·문서 입력은 확장분) |
| 2 | **업무 흐름을 실제 데이터에 손대지 않고 시험 실행하고, "이 입력이면 이 경로로 끝나야 한다"는 시험 사례를 등록해 고칠 때마다 자동 확인하며 명세 먼저(SDD)의 효과를 알아보기** | process-gpt-completion@b272c9a `test_mode.py:1-18`(/test/initiate·complete·cleanup, 운영과 같은 SUBMITTED→폴링 경로, Given=선행 활동 출력 심기), `:505`(라우트 등록); process-gpt-vue3@a4f0a85 `src/components/apps/definition-map/ProcessUnitTestPanel.vue:391-411,638-690`(사례 저장 `unitTests/<정의>.unit`·실행·정리), `designer/bpmnModeling/bpmn/panel/UnitTestCaseEditor.vue`(539줄)·`UserTaskUnitTest.vue`(809줄), `apps/definition-map/TestProcess.vue:905-916`(simulation:true 시작), `components/api/ProcessGPTBackend.ts:11635-11680`; process-gpt-docs@ad6944f `content/ko/advanced-features/simulation.md:8-28`(시뮬레이션: 에이전트가 시험값 생성, 분리된 데이터), `:30-50`(피드백 채팅으로 폼 수정), `:52-54`(단위 테스트=회귀 차단) | 강사용 통합 시험 스크립트만(`scripts/scenario_instance_test.py`·`scenario_pump_fan_test.py`), 정의별 시험 사례 등록·실행 API·화면 없음. 등록 때 정적 검사만(`definition_registry.py:196,234`). 정의 v1/v2 분기 비교는 수동 실습(`definition-authoring.md:5-19`) | 빠짐 | **상** — 랩업 계약의 마지막 단계 SDD(HANDOFF_실라버스교재 §7)를 업무 흐름 수준에서 그대로 보여 줌. "에이전트가 상황을 던졌을 때 끝까지 하는가"를 반복 가능한 시험으로 바꿈 | 중간 — 시험 사례 JSON 형식·`/api/process/definitions/{id}/tests` 실행기(기존 엔진·MemoryRepo 재사용 가능: `instances.py` 머리 "MemoryRepo and fakes")·결과 표. 에이전트 작업은 고정 출력으로 대체(LLM 비용 0) | 명세(시험 사례 3건: 정상·지연 타임아웃·반려)를 먼저 쓰고 Claude Code로 정의에 "재관측" 단계를 추가 → 시험 3건 통과·기존 시험 불변을 콘솔로 확인 | L136-138 "그런 상황을 던졌을 때… 진단 판단을 정확히 하고 액션까지 수행하는지를 모니터링" | 신규 (value-gaps 1은 AI 결과 채점, 이것은 흐름 회귀 시험) |
| 3 | **흐름 변경을 초안→검토·승인→배포로 관리하고, 판본 차이를 말로 설명받고 되돌려 보며 "규칙·흐름을 누가 언제 바꿨나"를 통제하는 법을 알아보기** (배포 = 경보가 여는 기본 흐름을 등록 판본으로 바꿔 끼우기 포함) | process-gpt@6084127 `docker-infra/volumes/db/init.sql:304-321`(proc_def_version: parent_version·source_todolist_id·is_draft·diff·message); process-gpt-vue3@a4f0a85 `supabase/migrations/20260130000001_proc_def_comments_approval.sql:36-85`(draft→review→approved_level1·2→confirmed/rejected, 코멘트·이력), `src/views/review-board/ProcessReviewBoard.vue:14-22`(검토 권한·자기검토 금지), `MergeRequestBoard.vue`(910줄), `src/views/process-hierarchy/VersionComparison.vue:42`(이전 판본 되돌리기), `src/components/ai/BpmnDiffGenerator.js:7,49`(비기술자용 변경 설명), `CommitMessageGenerator.js`, `src/router/MainRoutes.ts:680,720-750`; process-gpt@6084127 `init.sql:2982,3015`(resource_pull_requests·reviews) | 판본 불변·같은 판본 재등록 409·판본 선택 실행(`docs/definition-authoring.md:13-19`), 판본 목록 API(`instance_mode.py:572-587`). 경보 시작 흐름은 환경변수 파일로 고정(`instance_mode.py:39` DEFINITION_FILE, `:131`) → 새 판본을 등록해도 경보가 쓰지 않음. 검토·승인 상태·차이 설명·되돌리기 없음 | 얕음 | **상** — L448 "룰을 관리하기 위해"의 실제 장면, "승인 전 조회만, 사람 승인 1회 뒤 실행"(HANDOFF §3) 원칙을 정의 변경에도 적용 | 중간 — 판본 상태 열·승인 API·"현재 배포 판본" 포인터(경보 시작이 읽음)·차이 계산(정의 JSON diff + LLM 설명은 선택) | Claude Code로 "배포 판본 포인터" API와 시험(포인터 바꾸면 다음 경보부터 새 흐름, 기존 처리 건은 옛 판본 유지)을 명세→구현 | L448 "이런 프로세스들을 자유롭게 바꾸고 룰을 관리하기 위해서" | value-gaps 8의 "경보가 고정 파일" 부분 + 신규(검토·승인·차이·되돌리기) |
| 4 | **판단 규칙(결정표)을 말·표·그림으로 만들고, 규칙별 시험 사례로 검증한 뒤 흐름의 규칙 작업에 연결해 "AI 판단 대신 규칙으로 고정"을 알아보기** (→G3: 규칙이 온톨로지 층에 저장되는 부분은 G3) | process-gpt-vue3@a4f0a85 `src/components/ai/DmnGenerator.js:16-23`(텍스트·이미지→DMN 1.3 XML 생성/수정), `src/router/MainRoutes.ts:151-157,242-253`(DMN 채팅·업무 규칙 화면), `src/components/business-rules/BusinessRuleTestRunner.vue`(548줄, 규칙 시험 실행); process-gpt-docs@ad6944f `content/ko/advanced-features/dmn.md:14,26-42`(자연어 정책→결정표 예시) | 결정론 규칙 엔진은 있음(`it/agent/agentsvc/cards.py`, 규칙은 `it/neo4j/v2/instances.cypher`·`it/neo4j/templates/t3_dmn.cypher`), 순위 정책 수정 API(`procsvc/main.py:1185`). 규칙을 말로 생성·결정표 편집기·규칙 단위 시험 화면 없음(규칙은 cypher 템플릿으로 작성) | 얕음 | **상** — 랩업 대상 "판단 규칙"(HANDOFF_실라버스교재 §7)에 직접 대응. 회의가 말한 "룰 태스크→디시전 테이블" 구조를 학생이 직접 채움 | 중간 — 생성은 Claude Code가 cypher/JSON 결정표 작성, HYD는 등록 검증(UNIQUE hitPolicy, A115 A11)·규칙 시험 실행기만 추가 | 자연어 정책("납기 3일 이내면 정지 대신 감속")을 Claude Code로 결정표 행으로 만들고 → 시험 사례 4개(경계값 포함)로 평가 → 같은 경보의 카드 순위가 바뀌는 것을 콘솔 로그로 확인 | L23-24 "룰타스크… 디씨전 테이블로 들어가게", L301-302 "디엠엔 룰들… 규칙에 해당하는 쿼리를 생성하게끔" | 신규 (value-gaps 4는 피드백→개정안, 이것은 규칙 작성·시험) |
| 5 | **같은 에이전트 작업을 여러 번 돌린 기록을 파이썬 코드로 굳혀 다음부터 AI 없이 실행하고, 비용·시간·결과 흔들림 차이로 "언제 에이전트, 언제 규칙"을 알아보기** (자연어 분기 조건→코드 변환 포함) | process-gpt-completion@b272c9a `deterministic_generator.py:1-30`(DONE 확정 순간 작업 이력→코드), `:126`(ran_deterministic_code), `work_history.py` 머리(런타임 무관 행위 정규화: mcp_call·shell·file_write…), `polling_service/database.py:2171`(freeze_on_done 훅), `deterministic_signature.py`(2,046줄); process-gpt-vue3@a4f0a85 `src/components/ai/ConditionRuleGenerator.js:20`("rule-to-code compiler"); process-gpt-docs@ad6944f `content/ko/advanced-features/deterministic-regularization.md:8-22`(케이스 뱅크→검증 사례→코드 대체) | 없음 — 결정론 DMN 엔진은 있으나 에이전트 실행 이력을 코드로 굳히는 단계 없음(REPO_GAP §1 13 "후반 설명"). 워커 이벤트 모양은 `it/agent-worker/worker/events.py` | 빠짐 | **상** — 에이전트 운영비·재현성이라는 현업 질문에 실물로 답함 | 큼 — 이력 정규화·코드 생성·되돌림 조건(입력이 달라지면 다시 에이전트)·검증. 레포 코드 규모 3천 줄+ | 펌프 진단 작업 이벤트 3회분을 Claude Code에 주고 "같은 도구 호출 순서를 재현하는 파이썬 함수"를 만들게 한 뒤, 다음 경보에서 LLM 호출 0으로 같은 결과·소요 시간 비교 | 회의 언급 없음 | value-gaps 9, teachable 7 |
| 6 | **완료된 처리 건 기록을 모아 병목 단계·재작업·에이전트 대 사람 처리 시간·지연 업무를 집계해 보고 "어디를 고치면 빨라지나"를 알아보기** | process-gpt-analytic@a6dbb1a `backend/app/main.py:614`(bottleneck)·`:675`(rework)·`:726`(workload)·`:842`(agent-vs-human)·`:899`(fte-heatmap)·`:1006`(인스턴스 타임라인), `backend/app/etl.py`(스타 스키마); process-gpt-completion@b272c9a `dashboard_api.py:1350-1353`(executive-summary·process-analytics·governance-quality), `operational_board_api.py:1-10`(병목 Top10·좀비 프로세스·지연/미결 업무); process-gpt-vue3@a4f0a85 `src/views/analytics/BottleneckAnalysis.vue:1-5`(Camunda Optimize식 병목, BPMN 위 표시)·`src/router/MainRoutes.ts:685-701` | 건별 이벤트·실시간 스트림·인스턴스 단계 화면은 있음(`it/portal/www/liveStream.js`·`instanceSteps.js`·`flow.js`). 여러 건 집계(병목·재작업률·에이전트/사람 비교) 없음 | 빠짐 | **중** — 측정 개념은 좋으나 기술은 SQL 집계 위주. "에이전트 대 사람" 비교는 과정 주제와 직결 | 중간 — 읽기 전용 집계 SQL 4~5개(todolist·events)·포털 탭 하나. 레포의 전체 UPSERT·f-string SQL은 따르지 않음(REFERENCE_ADOPTION P01) | Claude Code로 todolist에서 "활동별 평균 대기·처리 시간, 에이전트/사람 구분" SQL과 작은 MCP 도구를 만들어 에이전트에게 "어디가 병목이야?"를 묻고 도구 호출을 콘솔로 확인 | L434-435 "에이전트들이 지금 동작하고 있다… 프로세스 인스턴스들 모니터링 하는 화면" | teachable 8 |
| 7 | **정해진 주기(매일·매주)에 업무 흐름이 저절로 시작되게 걸어 보고, 경보로 시작하는 흐름과 일정으로 시작하는 흐름의 차이를 알아보기** (예: 정기 예방 점검) | process-gpt@6084127 `docker-infra/volumes/db/init.sql:1756-1790`(register_cron_job, pg_cron), `:1698`(cron_job_run_log); process-gpt-vue3@a4f0a85 `src/components/ai/CronRuleGenerator.js:47`(자연어→cron), `src/components/scheduler/ScheduleList.vue:4-23`, `src/router/MainRoutes.ts:257`; process-gpt-completion@b272c9a `polling_service/workitem_processor.py:1901`(중간 타이머 cron 등록) | 시작은 경보 RAISE(메시지 시작)와 수동 시작뿐(`instance_mode.py:694-696`), 경계 타이머는 폴링이 due_date를 봄(HANDOFF.md L71 "pg_cron 타이머 축소") | 빠짐 | **중** — 설비 보전의 "사후 대응 vs 예방 점검"을 흐름 시작 방식으로 보여 줌 | 작음~중간 — 정의에 timer startEvent(주기) 허용·엔진 폴링 루프에서 다음 시각 계산·중복 시작 방지 키(기존 이벤트 ID 409 재사용) | Claude Code로 "매 시뮬 1시간마다 오일 상태 점검" timer 시작 정의와 엔진 확장을 만들고 20배속에서 3회 시작·중복 0을 콘솔 로그로 확인 | 회의 언급 없음 (L193 "이벤트가 올 때… 트리거"는 이벤트 시작만) | 신규 |
| 8 | **흐름 안에 작은 계산 코드 작업(스크립트 작업)을 넣어 엔진이 실행하게 하고, 사람·에이전트·규칙·시스템 외에 "코드 작업"이 언제 맞는지 알아보기** | process-gpt-completion@b272c9a `polling_service/workitem_processor.py:1659`(_execute_script_tasks), `polling_service/code_executor.py:18-41`(허용/거부 목록 실행); process-gpt-vue3@a4f0a85 `src/components/ai/ScriptGenerator.js`(77줄)·`GPTScriptGenerator.js`; process-gpt-docs@ad6944f `content/ko/advanced-features/admin-guide.md:136-145`(프롬프트→파이썬 스크립트 생성) | scriptTask 유형은 인식(`engine.py:34-35`)하나 서비스 실행기는 도구 3개 고정(`instances.py:693-694` incident:command·reobserve·WO_CREATE, 그 외 "unsupported service tool") | 빠짐 | **중** — task 단위(시스템·에이전트·규칙·사람·현장) 구분(CLAUDE.md §4)에 "결정론 계산"을 붙여 고착화(#5)의 착지점이 됨 | 중간 — 안전한 실행 경계(별도 프로세스·시간 제한·읽기 전용 입력)가 핵심. PLC 경로와 분리 필수 | Claude Code로 "잔여 수명 = 임계치까지 남은 시간" 계산 스크립트 작업을 정의에 추가 → 입력·출력 변수와 실행 로그를 콘솔로 확인(제어 명령 경로는 건드리지 않음) | 회의 언급 없음 | 신규 |
| 9 | **한 처리 건 안에서 하위 흐름을 묶고 대상 수만큼 병렬로 펼쳐(설비 3대 각각 점검) 부모·자식 처리 건이 어떻게 이어지는지 알아보기** | process-gpt-completion@b272c9a `polling_service/workitem_processor.py:1188-1657`(_process_sub_processes, adHoc·callActivity 매퍼), `:1397`(resolve_multi_instance_count); process-gpt-vue3@a4f0a85 `src/components/ai/SubprocessRuleGenerator.js:34`(개수 기준 키 선택), `src/router/MainRoutes.ts:502-503`(call-activity 관리); process-gpt-docs@ad6944f `content/ko/advanced-features/multi-instance.md:10-20` | 없음 — subProcess/callActivity는 로드 단계에서 거부(`engine.py:106-109`), 등록도 거부. DECISIONS.md 95(L495) "서브프로세스·다중 인스턴스는 이번 범위 밖(사용자 결정)" | 빠짐 | **중** — BPMN 핵심 개념이나 HYD 사례(경보 1건=설비 1대)에서 필요가 약함 | 큼 — 엔진 분기·부모 대기(PENDING)·투영·화면·재작업 상호작용 | - (사용자 결정 변경이 먼저) | 회의 언급 없음 | teachable 12 (**충돌**: DECISIONS 95) |
| 10 | **사람에게 가는 알림을 알림함·메일·메신저로 받아 보고 "에이전트는 알리고 사람은 버튼만"을 끝까지 따라가 알아보기** | process-gpt@6084127 `docker-infra/volumes/db/init.sql:335`(notifications); process-gpt-vue3@a4f0a85 `src/views/notifications/NotificationsPage.vue`(239줄), `src/components/api/ProcessGPTBackend.ts:3826-3835`(실시간 구독), `src/router/MainRoutes.ts:754`; process-gpt-completion@b272c9a `polling_service/smtp_handler.py`(메일), `fcm_client.py`(푸시); process-gpt-mobile@0fa1143 `README.md:1-15`(앱 껍데기·푸시) | notifications 행만 저장(`it/supabase/migrations/20261003000001_process_engine.sql:234`, `procsvc/procdb.py:760`), 조회 API·포털 알림함 없음(포털 JS에 notification 참조 0). HANDOFF.md L102 "알림 채널은 포털 할일 목록으로 닫힘" | 얕음 | **중** — 장면은 좋지만 한 회차를 채우기엔 얇음 | 작음~중간 — 알림 조회 API·포털 배지, 외부 채널은 로컬 Mattermost 웹훅 하나 | Claude Code로 "사람 작업이 열리면 웹훅으로 링크를 보내는" 알림 소비자를 만들고 승인 링크→포털 승인까지 확인(버튼으로 직접 제어 금지) | L405-406 "특정 유저에게 alert", L417-420 "노티를 받을 수 있는 툴… metamost", L426 "노트까지만 주고 유저가 그냥 이 버튼을 누른다" | teachable 9 |
| 11 | **조직도와 역할을 말로 만들고 흐름의 레인(역할)에 실제 사람을 연결·위임해 보며 "승인 권한이 어디서 오는가"를 알아보기** (→G3: 조직이 온톨로지 클래스로 들어가는 부분) | process-gpt-vue3@a4f0a85 `src/components/ai/OrganizationChartGenerator.js:16`(채팅으로 조직도·입사·부서 이동), `src/views/work-assignment/WorkAssignment.vue:6`(업무분장: 레인↔조직), `src/router/MainRoutes.ts:94-117`; process-gpt@6084127 `init.sql:439-452`(delegation_history 위임), `:501-511`(user_permissions 정의별 읽기·쓰기·배포); process-gpt-docs@ad6944f `content/ko/advanced-features/user-guide.md:51-56`(실행 시 역할 지정), `admin-guide.md:148-175` | 사용자 시드·정의의 roles endpoint·역할 바인딩(`engine.py:293`), 승인 역할은 온톨로지 APPROVED_BY로 403 검사(REPO_GAP §1 사람 작업 제출). 조직도 편집·실행 시 역할 지정 화면·위임·정의별 배포 권한 없음 | 얕음 | **중** — "사람 승인 1회"의 주체를 조직에서 끌어오는 구조를 보여 줌 | 중간 — 사용자·팀 테이블 확장, 시작 시 role_bindings 입력, 위임 이력 | - (G3 조직 온톨로지 랩업과 합치는 편이 나음) | L406 "어떤 특정 유저에게 alert", L413 "그 휴먼이 둘 중에 하나를 선택" | 신규 |
| 12 | **처리 건을 요청 내용으로 자동 분류해 자주 오는 유형 Top 목록과 비슷한 과거 건·그 결과를 보고 "선례가 판단을 돕는 방식"을 알아보기** | process-gpt-instance-classifier@384a6ff `app/server.py:87`(toplist)·`:115`(similar)·`:259`(recluster), `app/cluster.py`(BERTopic); process-gpt-vue3@a4f0a85 `src/components/apps/instance-classifier/InstanceTopList.vue`(297줄), `src/router/MainRoutes.ts:44` | 선례는 선언 규칙 기반 DecisionCase→CHOSE 비율(`it/neo4j/templates/t3_precedents.cypher`), 경보 패턴은 AnomalyPattern 선언 규칙(REFERENCE_ADOPTION P02) | 얕음 | **하** — HYD 경보는 유형이 선언돼 있어 분류 필요가 약함 | 중간 — 임베딩·kNN(pgvector) | - | L7-8 "사고가 있었을 때 좋지 않은 일도 남겨서 향후… 피드백" | teachable "회의 언급 없음 블록" 표(인스턴스 자동 분류) |
| 13 | **업무 흐름을 대·중·소(메가·메이저·서브) 체계도로 정리해 회사 전체에서 이 흐름의 위치를 알아보기** | process-gpt-vue3@a4f0a85 `src/router/MainRoutes.ts:161-195`(definition-map mega/major/sub), `:445-458`(process-architecture·hierarchy), `src/views/process-hierarchy/ProcessHierarchy.vue`(5,561줄); process-gpt-docs@ad6944f `content/ko/tutorial/tutorial-lv1.md:83-89` | 정의 목록만(`instance_mode.py:572`), 체계도 없음. BSC→프로세스 층은 온톨로지에 있음(→G3) | 빠짐 | **하** — HYD 정의가 4~5개라 체계가 얕음 | 작음 | - | 회의 언급 없음 | 신규 |
| 14 | **검증된 흐름 묶음(정의+폼)을 마켓에서 검색해 가져와 바로 고쳐 쓰고, 내 흐름을 올려 공유하는 재사용을 알아보기** | process-gpt@6084127 `init.sql:513-539`(proc_def_marketplace·form_def_marketplace); process-gpt-vue3@a4f0a85 `src/components/ProcessDefinitionMarketPlace.vue`(754줄), `src/components/api/ProcessGPTBackend.ts:5759-5866`; process-gpt-docs@ad6944f `content/ko/advanced-features/process-marketplace.md:10-50` | 예제 정의 파일 폴더(`docs/examples/*.json`)와 등록 API뿐 | 빠짐 | **하** — 재사용 개념은 #1·#3에서 충분히 설명됨 | 작음 | - | 회의 언급 없음 | 신규 |
| 15 | **처리 건 업무를 칸반·간트·달력으로 보고 담당자끼리 채팅·멘션으로 협업하는 화면을 알아보기** | process-gpt-vue3@a4f0a85 `src/components/apps/todolist/KanbanBoard.vue`·`GanttChart.vue`, `src/views/apps/chat/Chats.vue:747-758`(멘션), `src/router/MainRoutes.ts:34,79-85`; process-gpt@6084127 `init.sql:459-499`(chat_rooms·chats·calendar), `:584-593`(task_dependency); process-gpt-docs@ad6944f `content/ko/advanced-features/user-guide.md:79-103` | 처리 건 목록·단계·내 할일·질문 답변(`it/portal/www/instances.js`·`hitl.js`), 칸반·간트·달력·채팅 없음 | 빠짐 | **하** — 범용 협업 UI, 온톨로지·에이전트 학습과 거리 멂(포털 추가 원칙 "카드 하나에 행동 1개"와도 충돌) | 중간 | - | 회의 언급 없음 | 신규 |

G2·G3로 넘기는 것(한 줄씩):
- 에이전트 초안(DRAFT) → 사람이 고쳐 제출하는 화면 →G2 (원본 process-gpt-vue3@a4f0a85 `src/components/apps/todolist/FormWorkItem.vue:936-964`, process-gpt-agent-sdk@4d8f3b6 `processgpt_agent_sdk/function.sql:72-74`; HYD 워커는 DRAFT 저장만 `it/agent-worker/worker/main.py:4`, 포털 표시 없음).
- 피드백 → 규칙·스킬·정의 개정안·승인(P04, 문서 `feedback-system.md:14`) →G2/G3, value-gaps 4·teachable 3에 이미 있음.
- 채팅 대화 맥락으로 전문 에이전트 초대(에이전트 라우터, `admin-guide.md:53-56`) →G2.
- KPI 목표·KPI 대시보드·전략 보드(`MainRoutes.ts:573-574,695-706`, `kpi_review_board.sql`) →G3 (value-gaps 3).
- 업무 앱을 MCP로 붙이기(sample-app-wms) →G2(HYD enterprise MCP로 이미 충족, REPO_GAP §1).

### 3. "HYD에 이미 있음"으로 뺀 것 (근거)

| 원본 기능 | 원본 근거 | HYD 근거 |
|---|---|---|
| 정의 등록·판본 불변·판본 선택 실행·같은 판본 재등록 거부 | process-gpt@6084127 `init.sql:304-321` | `it/process/procsvc/instance_mode.py:572-587`, `docs/definition-authoring.md:13-19`(409·404) |
| 정적 연결성 검사(고아 노드·게이트웨이 없는 분기) | process-gpt-bpmn-extractor@c7992ce `validation/process_validator.py` | `procsvc/definition_registry.py:196,234`(A096·A115) |
| 참조 정보(이전 단계 출력 중 전달할 항목 선택, 컨텍스트 엔지니어링) | process-gpt-docs@ad6944f `reference-info.md:10-30` | `inputData`·`inputBindings`(`procsvc/input_bindings.py`, `definition-authoring.md` "처음 실행할 때부터 특정 입력 출처를 기다리기") |
| 작업 재작업(되돌려 다시 하기)·보상 | process-gpt-docs@ad6944f `rework.md`, completion `compensation.py` | `procsvc/rework.py`·`rework_runtime.py`·`effect_compensation.py`, API `instance_mode.py:626-675`(REFERENCE_ADOPTION D03: HYD가 더 깊음) |
| 병렬 분기·합류, 배타 게이트웨이 priority/default, 경계 타이머 | completion@b272c9a `workitem_processor.py:4138-4431` | `engine.py`(A100 병렬 합류, DECISIONS 95) |
| 사람 작업 폼 렌더·제출(폼 계약) | process-gpt@6084127 `init.sql:323-334` form_def | 정의 안 `forms.<id>.fields_json`, 포털 `it/portal/www/instances.js:109`, `/api/todolist/{wid}/submit`(`instance_mode.py:731`) |
| 인스턴스 진행 단계·BPMN 그림·작업 이력 | process-gpt-vue3@a4f0a85 `src/shared/instanceSteps.js`, `InstanceHistoryViewer.vue` | `it/portal/www/instanceSteps.js`(원본 이식)·`flow.js`(A122 정의→SVG)·`liveStream.js`(SSE) |
| 실행 중 에이전트 취소·사람 질문/답변으로 재개 | vue3 `FormWorkItem.vue:954-964`, cli-agent `hitl.py` | `instance_mode.py:759`(cancel)·`:860`(human-response), `it/agent-worker/worker/hitl.py` |
| 워커 큐·임대·회수 | agent-sdk@4d8f3b6 `function.sql` | 마이그레이션 `20261007000018_worker_lease.sql`·`..21_claim_count_reclaim_only.sql`(REFERENCE_ADOPTION C07) |
| 감사 기록 조회 | vue3 `src/views/admin/tabs/AuditTrail.vue` | `procsvc/main.py:659` `/api/audit` |
| 업무 앱을 코드로 정의 설치 | sample-app-wms@8ba09f4 `scripts/install_processgpt_integration.py:185,503-527` | 정의 JSON 등록 API(`instance_mode.py:587`)·`docs/examples/*.json` |
| 문서→지식(인제스천)·골든 퀘스천 | bpmn-extractor, ontology-studio | `procsvc/manual_*.py`, A092~A119 (→G3) |

### 4. 가져오면 안 되는 것 (이유)

| 대상 | 원본 근거 | 이유 |
|---|---|---|
| K8s 배포·KEDA·세션 라우터(대화별 런너 Pod) | process-gpt-k8s@3022aaf `deployments/`·`keda/`, process-gpt-session-router@a5edf5c `README.md:1-40` | 단일 호스트 compose 강의 환경(REFERENCE_ADOPTION C06·C08). 라우터가 푸는 문제(여러 Pod의 대화 소유권)가 HYD에 없음 |
| 모바일 앱·FCM 푸시 | process-gpt-mobile@0fa1143, completion `fcm_client.py`, k8s `fcm-service-deployment.yaml` | Firebase 외부 계정 필요, 알림은 #10의 포털·로컬 웹훅으로 충분(teachable 표 2) |
| 결제·크레딧·사용량 과금 테이블 | process-gpt@6084127 `init.sql:691-845`(payment·credit·usage) | 유료 결제, 요구 없음 |
| 자연어 분기 조건을 LLM이 실행 때마다 평가 | completion `workitem_processor.py:2377`(`_evaluate_sequence_conditions`), docs `tutorial-lv3.md:30`(문서도 결정론 규칙 권장) | HYD 결정론 원칙(HANDOFF.md L71 "자연어 시퀀스 조건의 LLM 평가 축소"). 대신 #5의 "자연어→코드 변환 후 고정"은 가져올 만함 |
| LLM 인스턴스 이름 짓기 | completion `semantic_naming.py` | 비용, 규칙 이름으로 충분(REPO_GAP §1 축소) |
| 분석 서비스의 전체 테이블 UPSERT ETL·f-string SQL·자연어 SQL 질의 | process-gpt-analytic@a6dbb1a `backend/app/etl.py`, `main.py:168`(/api/query/natural)·`text2sql.py` | 부분 실패를 성공으로 기록·주입 위험(REFERENCE_ADOPTION P01), Text2SQL 전용 엔진은 목록 제외 기준(코디네이터 ②). #6은 읽기 전용 SQL 몇 개로 |
| 관리 콘솔 운영 기능(수정 잠금·휴지통·메뉴 설정·용어 설정·도입률 대시보드) | process-gpt-vue3@a4f0a85 `src/router/MainRoutes.ts:512-668` | SaaS 운영 기능, 강의 가치 낮음 |
| 음성 채팅·콜봇·문서/슬라이드 생성 | completion `callbot_api.py`·`audio_transcribe.py`, docs `voice-chat.md` | 유료 실시간 API, 설비 판단 경로 아님(teachable 표 2 A09) |
| 제품 전체 스택 기동 | process-gpt-infra-docker@9e85485 | LiteLLM 뒤 유료 키·서비스 다수 전제(DECISIONS 101) |
| n8n 워크플로 | process-gpt-k8s@3022aaf `deployments/n8n.yaml` | 매니페스트만, 제품 기능 연결 미확인 |

### 5. 상위 5개 추천과 이유

1. **#1 말·문서 → 실행 가능한 흐름 생성 + 엔진 실행 검증 루프** — meeting-2 L448이 말한 ProcessGPT의 존재 이유를 학생이 VS Code 터미널에서 직접 해 본다. D01 스킬과 HYD 등록기(A116에서 제품 모양 수용)가 이미 있어 크기 대비 효과가 가장 크고, 뒤의 #2·#3·#5의 재료가 된다.
2. **#2 흐름 시험 실행·시험 사례(회귀)** — 실라버스 마지막 랩업인 SDD("명세 먼저, 기존 기능을 깨지 않고 추가")를 업무 흐름 수준에서 그대로 실습하게 해 준다. 원본은 운영과 같은 엔진 경로로 Given→기대 경로를 검증(`test_mode.py`)하고, HYD 엔진은 MemoryRepo로 이미 시험 가능한 구조라 중간 크기로 된다. 회의 L136-138의 "상황을 던져 끝까지 하는지 본다"를 반복 가능한 시험으로 바꾼다.
3. **#3 흐름 변경 관리(초안→승인→배포·차이 설명·되돌리기, 경보 기본 흐름 교체)** — L448 "룰을 관리하기 위해"의 실제 장면이다. 지금은 새 판본을 등록해도 경보가 고정 파일(`instance_mode.py:39`)을 써서 "바꾼 흐름이 다음 경보부터 쓰인다"를 보여 줄 수 없다. 사람 승인 원칙(HANDOFF §3)을 정의 변경에도 적용하는 장면이 된다.
4. **#4 판단 규칙을 말로 만들고 규칙 시험으로 검증** — 랩업 대상 "판단 규칙"(HANDOFF_실라버스교재 §7)에 바로 맞고, 회의 L23-24·L301-302가 말한 룰 태스크→결정표 구조를 학생 손으로 채운다. 결정론 엔진·등록 검증(A115 A11)이 이미 있어 생성·시험만 붙이면 된다.
5. **#5 결정론 고착화(반복 에이전트 실행 → 코드)** — 크기는 크지만 "언제 에이전트, 언제 규칙"이라는 현업 질문에 비용·시간·흔들림 숫자로 답하는 유일한 블록이다. #8(스크립트 작업)을 먼저 만들면 굳힌 코드의 실행 자리가 생겨 크기가 줄어든다.

차순위: #6 프로세스 분석(에이전트 대 사람·병목, 회의 L434-435), #7 정기 시작(예방 점검 시나리오, 작음), #10 알림(작음, 회의 L405-426).

## 부록 B — 에이전트·툴·MCP·스킬 상세 (A1~A13 = 아래 표 #1~#13)

HYD 기준 커밋: `6033768` (/home/user/hyd-iot-edu). 저장소 파일은 고치지 않았다. 원본 클론: `/tmp/claude-0/refs/<repo>`(--depth 1, 커밋은 아래 표기).
적용한 기준(코디네이터 10-08): 회의 근거는 `meeting-2.txt`만 쓴다(meeting-1은 근거로 쓰지 않음). Text2SQL 전용 엔진은 목록에 넣지 않는다. 행마다 레포·커밋·경로를 단다.

**용어 주의(이 갈래의 함정):** HYD에서 "스킬"은 두 가지다. ① 온톨로지 `Skill` 노드 = 조치 방법(SOP) — 포털 "조치 방법" 화면(`it/portal/www/hitl.js:167-210`)과 `/api/kg/skills`(`it/process/procsvc/main.py:980,995`)가 다룬다. ② 에이전트 스킬 = Claude Code가 읽는 `SKILL.md` 묶음 — ProcessGPT의 스킬 관리·피드백 학습이 다루는 것은 이쪽이다. 아래 표의 "스킬"은 ②다.

### 1. 읽은 것 / 못 읽은 것

#### HYD 기준선
- `docs/handoff/verification/2026-10-08/value-gaps.md`, `teachable-candidates.md` 전문
- `docs/handoff/REPO_GAP.md` 전문, `REFERENCE_ADOPTION.md` A01~A09·C04·D04·T01·T03·T04·T07·T08·X03~X08·P04 행, `REFERENCE_ADOPTION.json`(repositories 이름 확인)
- `docs/handoff/HANDOFF_실라버스교재.md` §7(70~78행), `docs/handoff/sources/meeting-2.txt` 1~461행
- `docs/handoff/sources/repository-map/repository_urls.txt`(47개), `REPOSITORY_MAP.md` A01~A09·T01~T08·P04·D04·X03~X08 절
- HYD 코드: `it/agent-worker/worker/{runner.py 1-260, bridge.py 전문, workspace.py 전문, settings.py 전문, context.py 80-91, prompt.py 150-161, events.py 전문, main.py 65-117}`, `it/agent-worker/requirements.txt`(cliagents 7c7a392 고정), `it/agent/agentsvc/llm.py` 전문, `it/dmn-mcp/dmn_mcp/server.py` 34-117(도구 13), `it/enterprise-mcp/enterprise_mcp/server.py` 33-87(도구 9), `it/supabase/migrations/20261003000001_process_engine.sql` 44-70(tenants·users), `it/supabase/seed.sql` 54-86(tenants.mcp·users·form_def 시드), `it/process/procsvc/instance_mode.py` 689-692(`/api/agents/status`)·쓰기 API 전수(grep), `it/portal/www/hitl.js` 167-210, `liveStream.js` 8-103, `instances.js` 459-465

#### 원본 레포(실제 코드 열람)
| ID | 레포 | 커밋 | 읽은 파일:줄 |
|---|---|---|---|
| A01 | process-gpt-deepagents | faedeaa | README 1-60, `core/` 모듈 목록, `core/agents/steering.py` 1-30, `core/agents/skill_eval_gate.py` 1-20, `core/agents/skill_creator_subagents.py` 1-12, `core/agents/subagents.py` 1-60·93, `core/skills/pr_verification.py` 1-25, `core/skills/dmn_scenarios.py` 1-10, `core/api/skills_router.py` 100-1100(grep: extends·PR·owner) |
| A02 | process-gpt-base-agent-langchain-react | e566a60 | `process-gpt-mcp/src/process_gpt_mcp/server.py` 902-2084(도구 12개 이름), `process_start.py` 1-25, `src/work_assistant_agent/mcp_client.py` 105-175 |
| A03 | process-gpt-a2a-orch | ad5e937 | README 1-30, `src/` 구조 |
| A04 | process-gpt-codex | cede40e | README 1-25, `managed_skills/` 목록 |
| A05 | process-gpt-cli-agent | 0a0e3d3 | README 1-30, `executor.py` 100-200, `core/skills.py` 1-271 전문, `core/subagents.py` 1-60·83·122, `api/skills.py` 40-92, `server.py` 25-90 |
| A06 | cliagents | 7c7a392(HYD 고정과 같음) | `src/cliagents/artifacts.py` 113-143(`add_skill`·`add_role_agent`) |
| A07/A08/A09 | openai-deep-research / deep-research / react-voice-agent | 49ddcd9 / 8a343e2 / 999ca2b | README 머리 |
| C02 | process-gpt-vue3 | a4f0a85 | `src/components/ui/field/AgentField.vue` 4-170·270-300·482-501, `ui/AgentCreateDialog.vue` 1-210, `mixins/AgentCrudMixin.vue` 78-79·300-309, `pages/account-settings/MCPServer.vue`(grep 1-370), `MCPEnvSecret.vue` 9-54, `services/McpValidatorService.js` 전문, `components/ai/OrganizationAgentGenerator.js` 1-40, `AgentKnowledgeManagement.vue`(grep), `AgentChatLearning.vue` 28-52, `AgentToolPriority.vue` 13-121, `SkillGitHistory.vue`(grep), `SkillPrDetail.vue` 58-132, `views/markdown/AgentMonitor.vue` 200-290, `ui/agentEventTimeline.js` 1-30, `ProcessDefinitionMarketPlace.vue` 505-540, `api/ProcessGPTBackend.ts` 스킬 경로(grep) |
| C03 | process-gpt-completion | b272c9a | `agent_chat.py` 15-53, `mem0_agent_client.py` 150-199 |
| C04 | process-gpt-gateway | 2567edc | 파일 목록(CreditValidationFilter 등) |
| C07 | process-gpt-agent-sdk | 4d8f3b6 | `processgpt_agent_sdk/steering.py` 함수 목록(304-352) |
| D04 | process-gpt-agents.github.io | cdc78f0 | `src/views/marketplace/*.vue`(agent 문자열 0건 — 템플릿 랜딩뿐) |
| P04 | process-gpt-agent-feedback | 84d2a0e | `core/feedback_batch_manager.py` 12-20·76-82·318-401·494-503, `core/skill_api_client.py` 함수 목록, `skills/skill-creator/` 목록 |
| T01 | process-gpt-memento | 659ab9f | README 1-40, API 라우트 목록 |
| T03 | process-gpt-office-mcp | 7e95c6e | 파일 목록 |
| T04 | process-gpt-mcp-validator | cf220bf | `src/mcp_validator/validator.py` 51-154, `api.py` 86-190, `models.py` 70-78 |
| T07 | process-gpt-claude-skills | 456d56f | `packages/backend/src/claude_skills_mcp_backend/mcp_handlers.py` 140-235, `http_server.py` 492-610·780-1025(도구 이름) |
| T08 | process-gpt-computer-use | 174adf6 | 파일 목록 |
| X03/X04/X05 | crewai-action / crewai-deep-research / langchain-react | ecdf8de / 49e2b12 / 16e1f38 | README 머리 |
| X06 | process-gpt-browser-use | 6aeaa42 | README 머리, 파일 목록 |
| X07 | process-gpt-agent-utils | 5dbd7e0 | `tools/safe_tool_loader.py` 1-30, `a2a_client_tool.py`·`knowledge_manager.py` 클래스 목록 |
| X08 | process-gpt-llm-factory | a32e57e | `llm_factory/factory.py` 1-90 |

비공개 4개(deepagents·base-agent·codex·llm-factory)와 browser-use는 처음 공개 클론이 거부되어 `add_repo`로 세션에 붙인 뒤 받았다.
**못 읽은 것 / 미확인:** deepagents `executor.py`(2,562줄)·`core/skills/tools.py`(3,323줄) 본문, agent-feedback `core/dmn_xml.py`·`feedback_processor.py` 본문, vue3 `SkillsManagement.vue`(1,519줄)·`AgentChat.vue` 본문, a2a-orch 실행 코드 본문 — 표 판정에 필요한 범위(모듈 머리말·함수 목록·라우트)만 읽었다. 원본 서비스는 하나도 실행하지 않았다(동작은 코드 근거, 실측 아님).

### 2. 빠진 기능 표 (가치 순)

크기 표기는 예상이다: 작음 = 기존 모듈에 함수·API 1~2개, 중간 = 새 API + 포털 카드/스크립트 한 덩어리, 큼 = 새 서비스·새 저장 모델·여러 층.

| # | 빠진 기능(가치 문장) | 원본 근거(레포@커밋/파일:줄) | HYD 현재(파일:줄) | 판정 | 강의 가치 | 구현 크기(예상) | 랩업 후보(콘솔에서 확인할 것) | 회의 근거 줄 | value-gaps/teachable 대응 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **수강생이 에이전트 스킬(SKILL.md)을 직접 써서 업무 작업에 붙여, 같은 경보에서 에이전트의 조회 순서·판단 근거가 바뀌는 것을 알아보기** | cli-agent@0a0e3d3 `core/skills.py:69-134`(시스템·테넌트·git 스킬을 모아 CLI 고유 위치 `.claude/skills/<name>/SKILL.md`로 기록, 못 온 스킬은 이름과 이유로 보고), `executor.py:141-180`(활동 `skills` 선언 → 번들 → provision → 실패 notice), `api/skills.py:43-92`(.md/.zip 업로드·목록·삭제, 테넌트 네임스페이스·zip 경로 탐색 거부); cliagents@7c7a392 `artifacts.py:115-122` `add_skill` | **정의의 `skills`를 읽기만 하고 버린다**: `it/agent-worker/worker/context.py:89`가 `skills`를 꺼내지만 `runner.py:106-136`은 `agent_config`·`tools`만 쓰고 `workspace.provision`(`workspace.py:286-292`)은 CONSTITUTION만 기록. 스킬 업로드·목록 API 0건(`procsvc` 쓰기 API 전수 grep) | 빠짐 | **상** — 랩업 계약의 "에이전트·툴을 만들어 붙여 써 본다"의 가장 짧은 경로이고, 지식(온톨로지)과 절차(스킬)를 나누는 개념 단원이 된다 | **작음** — HYD가 고정한 cliagents 커밋이 이미 `add_skill` 지원(`it/agent-worker/requirements.txt` 2행), `provision`에 번들 추가 + 스킬 폴더 설정 + 빠진 스킬 notice | VS Code Claude Code로 `skills/hyd-cooler-check/SKILL.md`("쿨러 경보면 먼저 enterprise.cmms_history로 최근 정비를 보고…")를 쓰고 진단 활동에 `skills:["hyd-cooler-check"]` → 쿨러 경보 1건 → `<job>.events.jsonl` tail에서 tool_start 순서가 스킬대로 바뀌었는지, 실행 폴더에 `.claude/skills/…`가 생겼는지 | L132-135("스킬을 읽어다가 알아서 쭉 진행"), L399-404("스킬이라고 봤을 때 그 데이터는 supabase에 들어 있다는 사실만 있다면 알아서") — 회의의 "스킬"이 SOP인지 SKILL.md인지는 문맥상 모호 | 신규 |
| 2 | **수강생이 에이전트를 하나 정의(이름·역할·목표·페르소나·쓸 MCP·스킬·모델)해 업무 단계에 배정하고, 정의가 실제 실행 설정으로 바뀌는 것을 알아보기**(+ 전문 에이전트를 서브에이전트로 두어 각자 다른 MCP만 쥐게 하기) | vue3@a4f0a85 `ui/field/AgentField.vue:45-170`(유형 agent/a2a/pgagent, role·goal·persona·tools·skills·provider/model), `ui/AgentCreateDialog.vue:57-90,178-189`(팀 배정 저장), `mixins/AgentCrudMixin.vue:78-79,300-309`(users 행 is_agent·agent_type); cli-agent@0a0e3d3 `core/subagents.py:23-60`(에이전트 행 → CLI 네이티브 서브에이전트, MCP는 서브에이전트에만 붙임), `:83`·`:122`(정의 기록·위임 지시), `executor.py:136-170`; deepagents@faedeaa `core/agents/subagents.py:38-93`(tool_filters) | 에이전트는 SQL 시드 1행(`it/supabase/seed.sql:66-72` `sys:agent`, tools 문자열). 열은 제품과 같지만(`migrations/20261003000001_process_engine.sql:53-70` goal·persona·model·tools) **실행에 쓰는 것은 이름·역할 한 줄뿐**(`worker/prompt.py:156-160`); persona·tools·model 미사용, 서브에이전트 0. 등록 API·화면 없음(쓰기 API 전수 grep; `/api/users`는 조회 `instance_mode.py:884`) | 얕음 | **상** — 사용자 10-08 요구 "에이전트 생성…ProcessGPT처럼"의 본체. "에이전트 = 프로필 + 도구 + 스킬 + 모델" 구조를 학생이 손으로 조립 | **중간** — users 쓰기 API·포털 카드 1개 + 워커가 배정 에이전트 행을 실행 설정으로 변환(cliagents `add_role_agent` 지원, `artifacts.py:127-143`) | Claude Code로 "정비 이력 전담 에이전트" users 행 + 활동 배정을 만들게 하고 경보 1건 → 콘솔에서 서브에이전트 위임(Task 도구 호출)과 그 에이전트가 enterprise MCP만 쓰는지 확인 | L146-156("우리 에이전트 딥에이전트…클로드 코드를 써도"), L172("후반에는 우리 걸 써서 플랫폼을"), L434-435(어떤 에이전트들이 동작하는지) | 신규(teachable "회의 언급 없음" 멀티 에이전트 행을 프로필 정의로 확장) |
| 3 | **수강생이 직접 만든 MCP 서버를 테넌트 도구로 등록하고, 붙이기 전에 연결·도구 목록을 검증해 "붙었는데 왜 안 쓰지"를 스스로 가려내기**(+ 에이전트별 도구 단위 허용) | mcp-validator@cf220bf `src/mcp_validator/validator.py:51-154`(서버별 initialize+list_tools+timeout → success/partial/failed), `api.py:86-190`(`/validate`·설정 예시); vue3@a4f0a85 `pages/account-settings/MCPServer.vue:4-111,176-211`(서버 목록·켜기/끄기·JSON 편집기·검증 결과), `services/McpValidatorService.js:22-41`, `ui/field/AgentField.vue:93-118`(검증 결과에서 도구를 골라 `tool_filters`), `AgentToolPriority.vue:13-121` | `tenants.mcp`는 SQL 시드로만(`seed.sql:57-64`), 등록·수정 API·화면 0. 검증기 없음 — 서버 다운은 실행 뒤 FAILED로 드러남(REFERENCE_ADOPTION T04). 도구 허용은 워커 전역 `--allowedTools`(`settings.py:358-359,419`)와 활동 단위 서버 선택(`bridge.py:52-64`)뿐 | 얕음 | **상** — 랩업 "MCP 만들어 붙이기"의 마지막 고리(등록·검증)가 지금은 SQL 손편집+재기동. 회의가 MCP 붙이기를 가장 길게 말함 | **중간** — tenants.mcp 읽기/쓰기 API + `fastmcp.Client`로 initialize·list_tools 검증 + 포털 카드(또는 CLI 스크립트) | Claude Code로 FastMCP `hyd-maint` 서버(도구 1~2개)를 만들고 검증 스크립트로 tools 목록 확인 → 등록 → 활동 `tools:["hyd-maint"]` → 콘솔에서 `mcp__hyd-maint__…` 호출과 응답 확인; 일부러 포트를 틀려 검증이 failed를 내는 것도 확인 | L88-96, L105-112(학생에게 MCP 동작 방식 설명), L123-138(MCP를 하나 더 붙인다, 두 MCP 설정 후 진단·액션 모니터링), L189-191, L397-398 | 신규(teachable 표 3 "실행 전 MCP 점검(T04)"은 실행 시점, 이것은 등록 시점 검증) |
| 4 | **수강생이 프로세스 엔진 자체를 MCP 도구로 감싸, 대화하던 에이전트가 프로세스 목록을 보고 인스턴스를 시작하고 할 일을 조회하게 만들어 "에이전트가 프로세스를 부른다"를 알아보기** | base-agent@e566a60 `process-gpt-mcp/src/process_gpt_mcp/server.py:902-2084`(`ask_user`·`get_process_list`·`get_process_detail`·`get_form_fields`·`execute_process`·`get_instance_list`·`get_todolist`·`get_organization` 등 12도구), `process_start.py:1-25`(첫 단계에서만 시작·10분 내 같은 실행 중복 방지 — "프롬프트만으로는 모델이 어기는 것을 막을 수 없다") | 엔진은 HTTP API만(`instance_mode.py:694` `/api/instances/start`, `/api/todolist`). HYD MCP 3개(neo4j·enterprise·hyd-dmn)에 프로세스 도구 0 | 빠짐 | **중~상** — 짧은 MCP 실습 중 HYD 시스템 전체(엔진·포털)와 바로 이어지는 것. 중복 시작을 서버에서 막는 설계 교훈이 분명 | **작음~중간** — 기존 HTTP API를 감싸는 FastMCP 서버(도구 3~4개) + 중복 방지 | VS Code Claude Code에서 "HYD process MCP"(list_definitions·start_instance·list_todolist)를 만들어 `.mcp.json`에 붙이고 "HYD-02에 쿨러 경보 인스턴스를 시작해" → 콘솔 tool 호출, 포털 인스턴스 1건, 같은 요청 반복 시 새 인스턴스가 안 생기는지 | 회의 직접 언급 없음(간접: L175-178 서버가 Claude Code를 불러 통합 UI, L436 "구현하다 보면 ProcessGPT가 된다") | 신규 |
| 5 | **수강생이 쌓인 처리 피드백에서 에이전트가 스킬·DMN 규칙·프로세스 정의 개정안을 만들고, 대상별로 사람이 승인해야만 반영되는 학습 순환을 돌려 보기** | agent-feedback@84d2a0e `core/feedback_batch_manager.py:12-20`(대상 SKILL/DMN_RULE/PROCESS_DEFINITION 독립 승인), `:76-82`(활동별 5건 또는 3일 배치), `:318-401`(대상 실재 확인·배치 처리), `:494-503`(승인된 SKILL만 개선 파이프라인); vue3@a4f0a85 `ui/ProcessFeedback.vue`(245줄)·`ui/SkillProposalReviewModal.vue`(388줄) | 선례 읽기·검토자 판정·순위 정책 영수증까지(value-gaps #4 "일부"), 개정안 생성·대상별 승인 단계 없음. P04 "보류"(REFERENCE_ADOPTION P04: 적용 결과 응답 결함 기록) | 얕음 | **상** — 회의 6계층의 마지막 층과 "룰을 관리하기 위해 ProcessGPT" | **큼** — 배치 수집·분류 작업 정의·제안 저장·대상별 승인·판본 적용(결함 2건은 따라 하지 않음) | Claude Code로 "추천과 다른 카드를 고른 사례 3건 → DMN 행 개정안 JSON" 에이전트 작업 정의를 쓰고 실행 → 콘솔에서 precedents·dmn_rules 호출과 제안 JSON, 승인 전 순위 불변·승인 뒤 순위 변화 | L7-8(사고를 남겨 향후 피드백), L448(룰을 관리하기 위해) | value-gaps #4 = teachable 1-3 (G3와 겹침 — 여기서는 "에이전트가 스킬을 개정"하는 쪽만) |
| 6 | **수강생이 매뉴얼 일부에서 스킬을 만들고, 같은 시험 문항을 스킬 있음/없음으로 돌려 채점해 "이 스킬이 정말 도움이 되나"를 숫자로 판정하기** | deepagents@faedeaa `core/agents/skill_creator_subagents.py:1-12`(skill-creator·rule-extractor(문서 60/40 분할)·test-runner(스킬 유무 실행)·evaluator(grader로 assertion 채점)), `core/agents/skill_eval_gate.py:1-20`("테스트 0건" 실측 → 완료 거부·턴 종료 되돌림); agent-feedback@84d2a0e `skills/skill-creator/scripts/run_eval.py`·`aggregate_benchmark.py` | 스킬 작성 자체가 없음(#1). 채점은 매뉴얼 골든 퀘스천만(`procsvc/manual_golden.py`, REPO_GAP §6 B3) | 빠짐 | **상** — value-gaps #1("AI 결과를 기준표로 채점")을 에이전트 스킬에 적용. 남긴 40%를 시험지로 쓰는 홀드아웃 개념이 교육적 | **중간** — 시험 문항 파일 + 두 조건 실행 스크립트 + 채점 스크립트(서버 대조 또는 LLM 채점) | Claude Code로 HM-9 매뉴얼 60%에서 스킬을, 40%에서 문항 5개를 만들고 eval 스크립트로 스킬 유무 2회 실행 → 콘솔에 문항별 통과/실패와 합계, 스킬 없을 때보다 나아졌는지 | L136-138(MCP 두 개를 주고 진단·액션까지 정확한지 모니터링해 온톨로지가 잘 됐는지 체크) | value-gaps #1 연장(신규 측면: 스킬 A/B) |
| 7 | **수강생이 스킬·규칙을 바꾼 뒤, 병합 전에 보관된 시나리오를 변경 전·후 두 판으로 돌려 "기존 동작을 깼는가"를 확인하고 나서만 반영하기** | deepagents@faedeaa `core/skills/pr_verification.py:1-25`(base·head 각각 실행·같은 기준 채점·`broken` 산출, 오케스트레이션은 코드가 결정론적으로), `core/skills/dmn_scenarios.py:1-10`(규칙 표 회귀 케이스는 변경 전 기준), `core/api/skills_router.py:515-605,747-805`(스킬 파일 수정 → 브랜치·PR); vue3@a4f0a85 `SkillPrDetail.vue:58-132`(diff·병합 버튼 옆 검증), `SkillGitHistory.vue`(커밋·브랜치) | 회귀는 강사용 스크립트(`scripts/scenario_instance_test.py`·run_regression), 규칙 변경은 순위 정책 수정 영수증(`/api/kg/ranking-policy/{rule}` `procsvc/main.py:1185`)·카드 미리보기(`/decision-preview`). 변경 전·후 자동 대조와 병합 게이트 없음 | 얕음 | **상** — 랩업 계약의 마지막 SDD("명세 먼저, 기존 기능을 깨지 않고 추가")와 같은 생각을 업무 규칙에 적용 | **중간** — 시나리오 보관(JSON) + 두 판 평가 + 차이 보고 스크립트. git PR 화면은 불필요 | Claude Code로 DMN 순위 규칙 한 행을 고치는 브랜치를 만들고 `verify_change.py`(변경 전·후 각각 dmn-mcp `evaluate_cards`를 시나리오 5건에 실행)를 돌려 콘솔에 "깨진 시나리오 n건"과 바뀐 카드 | L448(룰을 관리하기 위해) | 신규(value-gaps #4의 "승인 → 반영" 앞단 안전장치) |
| 8 | **수강생이 업무 에이전트와 같은 MCP·스킬·작업 규칙으로 바로 대화해 시험하고, "학습 모드"로 알려 준 사실이 다음 답에 쓰이는지 확인하기** | completion@b272c9a `agent_chat.py:28-41`(is_learning_mode 분기), `mem0_agent_client.py:150-199`(학습 모드면 메모리 저장·중복 판정, 질문 모드면 검색해 답); vue3@a4f0a85 `AgentChatLearning.vue:28-52`, `AgentKnowledgeManagement.vue`(에이전트별 저장 지식 목록·삭제); cli-agent@0a0e3d3 `server.py:90` `/chat/stream`(같은 실행체로 채팅) | 업무 에이전트와 대화하는 경로 없음 — 워커는 todolist 폴링만(`worker/main.py:1-7`). 에이전트 메모리 없음(선례는 그래프 `precedents` 도구 `dmn-mcp/server.py:111-112`) | 빠짐 | **중** — 회의는 "Claude Code에 질의해 보라"고 했고 랩 환경이 이미 콘솔 Claude Code라 채팅 화면 가치는 낮다. 남는 가치는 "업무 에이전트와 똑같은 설정으로 시험"과 메모리 개념 | **중간** — 실행 폴더를 만들어 주는 시험 스크립트(CONSTITUTION·.mcp.json·스킬 동일 구성 후 대화형 Claude Code) / 메모리 저장소까지면 큼 | `python scripts/agent_try.py diagnose`(가칭)로 업무 에이전트와 같은 폴더를 만들고 그 안에서 `claude` 실행 → "HYD-02 쿨러 원인은?" → 콘솔 tool 호출이 워커 실행과 같은지 | L93-96(Claude Code에 MCP를 설정하고 질의해 보면 조치 방법을 설명하는 것을 목격) | teachable "회의 언급 없음" 장기 메모리 행과 일부 |
| 9 | **수강생이 돌고 있는 에이전트에게 실행을 끊지 않고 지시를 덧붙여(스티어링) 계획이 어떻게 바뀌는지 알아보기** | agent-sdk@4d8f3b6 `processgpt_agent_sdk/steering.py:304-352`(대화별 지시 대기열·수락·적용 이벤트); deepagents@faedeaa `core/agents/steering.py:1-30`(모델 호출 직전에만 얹어 도구를 끊지 않음, 턴 종료 직전 재확인) | 취소(`runner.py:207-212`)와 사람 질문·응답 재개(`hitl.py`, `runner.py:126-133`)만. 실행 중 지시 없음(REPO_GAP §1-13 "스티어링 후반 설명") | 빠짐 | **중** — HITL을 "멈추고 묻기"에서 "가는 중에 고치기"로 넓히는 개념. 단 Claude Code headless는 턴 중 입력 주입이 없어 HYD 구현은 "턴 경계에서 resume" 근사가 됨(cliagents 지원 여부 미확인) | **중간** — 지시 저장 API + 워커가 다음 resume 턴에 붙임 | 장기 실행 작업 중 curl로 "원인 후보에서 센서 고장도 확인해" 지시 → 콘솔에서 다음 턴 프롬프트에 지시가 붙고 추가 도구 호출이 생기는지 | 회의 언급 없음 | 신규 |
| 10 | **수강생이 "이런 일을 하는 에이전트가 필요해"라고 말로 쓰면 AI가 프로필(역할·목표·페르소나·필요한 MCP) 초안을 만들고, 사람이 고쳐 저장하는 흐름을 알아보기** | vue3@a4f0a85 `components/ai/OrganizationAgentGenerator.js:1-40`(등록된 MCP 도구 목록을 프롬프트에 넣어 name·role·goal·persona·tools JSON 생성), `ui/field/AgentField.vue:4-11,482-501`(생성 결과를 폼에 채움) | 없음 | 빠짐 | **중** — #2와 묶으면 "AI가 초안, 사람이 확정" 원칙을 에이전트 설계에 적용. 단독 가치는 작음 | **작음**(#2가 있다는 전제) | Claude Code에 "등록된 MCP 목록(tenants.mcp)을 읽고 '부품 발주 검토 에이전트' users 행 JSON을 만들어" → 없는 MCP 이름을 지어내는지 검사 스크립트로 확인 | 회의 언급 없음 | 신규 |
| 11 | **수강생이 같은 업무 단계를 다른 실행체(Claude Code·Codex·경량 ReAct)로 돌려 비용 등급·시간·결과를 비교하고, 단계별 실행체를 고르는 기준을 알아보기** | vue3@a4f0a85 `views/markdown/AgentMonitor.vue:200-290`(orchestration 선택지 deepagents·codex·cliagents·langchain-react·deep-research와 비용 등급 high/medium/low); llm-factory@a32e57e `llm_factory/factory.py:21-69`(openai·azure·anthropic·ollama 공급자 전환) | 활동 단위 CLI·모델 선택은 있음(`runner.py:106-112`, Codex+GPU 모델 서버 `settings.py:395-401`), 서술 LLM 공급자 전환(`agentsvc/llm.py:11-13`). 실행체 간 비교 기록·비용 집계 없음(토큰은 events `usage`로만, `liveStream.js:56`) | 얕음 | **중하** — 비교 자체는 좋으나 유료 키 필요, 검증 1회 원칙과 부딪힘 | **작음~중간** — 같은 경보 2회 실행 + events usage 집계 스크립트 | 같은 진단 활동을 `agentConfig.agent_cli=claude-code`/`codex`로 1회씩 → 콘솔에 실행 시간·토큰·제출 결과 차이 표 | 회의 언급 없음 | value-gaps #9·teachable 1-8 일부(비용 측정) |
| 12 | **수강생이 MCP 서버의 비밀값(DB 비밀번호 등)을 설정 본문과 분리해 등록하고, 실행 폴더에 비밀이 남지 않는 것을 확인하기** | vue3@a4f0a85 `pages/account-settings/MCPEnvSecret.vue:9-54,94-144`(환경 변수·시크릿 별도 목록 편집) | `tenants.mcp` 시드에 Neo4j 비밀번호 평문(`seed.sql:60`). 실행 뒤 `.mcp.json`에서 env 제거(`bridge.py:28-49`, A096)·비밀 env 차단(`env_guard.py`)은 있음 | 얕음 | **하~중** — 보안 개념 한 꼭지, 단원 하나는 안 됨 | **작음** | 시크릿 참조 형식으로 등록 → 실행 후 워크스페이스 grep으로 비밀 문자열 0건 확인 | 회의 언급 없음 | 신규 |
| 13 | **수강생이 외부 A2A 에이전트(에이전트 카드·엔드포인트)를 등록해 업무 단계를 위임하고, 비동기 수락과 완료가 다르다는 것을 알아보기** | a2a-orch@ad5e937 README 1-30(executor/webhook receiver 분리, 수락≠완료); vue3@a4f0a85 `ui/field/AgentField.vue:25-36`(a2a 유형: endpoint·카드 조회); agent-utils@5dbd7e0 `tools/a2a_client_tool.py:110-173` | 없음 | 빠짐 | **하** — 설비 판단 경로 밖, 외부 에이전트 요구 없음(REFERENCE_ADOPTION A03) | **중간** | (권장하지 않음) 로컬 샘플 A2A 서버에 위임하고 콘솔에서 accepted→completed 이벤트 순서 확인 | 회의 언급 없음 | teachable "회의 언급 없음" A2A 행 |

### 3. "HYD에 이미 있음"으로 뺀 것

| 원본 기능 | HYD 근거 |
|---|---|
| CLI 코딩 에이전트에 업무 작업 위임(Claude Code·Codex), 실행 단위 워크스페이스, 형식 계약·교정 | `it/agent-worker/worker/runner.py:105-202`, `workspace.py:271-292`, `outcome.py` |
| 테넌트 MCP → 실행별 `.mcp.json`(stdio·HTTP), Codex 인라인 설정 | `bridge.py:108-146` |
| 활동 단위 MCP 서버 선택 | `bridge.py:52-64`(A095) |
| 활동 단위 CLI·모델·권한 선택(제품 키 철자 전부) | `runner.py:37-41,106-112` |
| 도구 호출 기록·실시간 표시(시작·끝 짝, 소요 ms) | `events.py:18-19,37-40`, `liveStream.js:8-103`, `instances.js:459-465`; 원본 이벤트 전부는 실행 폴더 `<job_id>.events.jsonl`(`runner.py:156-157,237-240`). **주의:** 워커 표준 출력에는 도구 호출이 한 줄씩 찍히지 않는다(제출·실패·일시정지만 `runner.py:202,330,338`). 랩업의 "콘솔 로그로 툴 호출 보기"는 jsonl tail 또는 로그 한 줄 추가로 충족 — 원본 대비 격차가 아니라 HYD 표시 방식 문제라 표에서 뺐다 |
| 사람 질문(HITL)·권한 요청 일시정지·응답 재개, 취소, 임대 | `hitl.py`, `runner.py:126-133,207-229,300-338` |
| 에이전트 현황(어떤 워커가 무엇을 하는지)·CLI 인증 상태 | `procsvc/instance_mode.py:689-692`, `worker/main.py:65-83` |
| 비밀 환경 변수 차단·실행 뒤 MCP env 제거 | `env_guard.py`, `bridge.py:28-49` |
| 업무 MCP 서버(DMN 진단·규칙·시계열·PromQL·카드·예측·제출·선례 / 업무 DB 9도구) | `it/dmn-mcp/dmn_mcp/server.py:34-117`, `it/enterprise-mcp/enterprise_mcp/server.py:33-87` |
| DMN 도구(제품 agent-utils `dmn_rule_tool`) | HYD 결정론 엔진이 더 강함(REFERENCE_ADOPTION X07) |
| LLM 공급자 전환(llm-factory) | `agentsvc/llm.py:11-13`(서술), `settings.py:395-401`(Codex 모델 서버) — 제품 X08과 같은 역할(REFERENCE_ADOPTION X08) |
| 조치 방법(온톨로지 Skill=SOP) 목록·편집·신규 | `it/portal/www/hitl.js:167-210`, `procsvc/main.py:980,995` — 에이전트 SKILL.md와 다른 것(표 #1) |

### 4. 가져오면 안 되는 것

| 대상(레포@커밋) | 이유 |
|---|---|
| 스킬 검색 MCP 서버 claude-skills@456d56f(`find_helpful_skills` 임베딩 top-k, `mcp_handlers.py:147-235`) | Claude Code가 `.claude/skills`의 description만 먼저 읽고 본문은 필요할 때 읽는 부분 로딩을 이미 한다. 표 #1이 되면 별도 임베딩 서버는 중복. 엔진이 권한 검사를 안 함(REFERENCE_ADOPTION T07) |
| deepagents@faedeaa 실행체 전체(LangGraph 딥에이전트·Docker 샌드박스 `core/sandbox/docker_sandbox.py` 840줄) | 회의는 "Claude Code를 써도 된다"(L154-156). 프레임워크 교체 근거 없음, Docker 데몬·memento·LLM 키 전제. 가져올 것은 개념(#6·#7)뿐 |
| 범용 ReAct·CrewAI 실행체(base-agent@e566a60 본체, crewai-action@ecdf8de, langchain-react@16e1f38) | 실행체 교체 근거 없음(REFERENCE_ADOPTION A02·X03). base-agent에서는 `process-gpt-mcp`의 도구 설계(#4)만 참고 |
| 딥리서치(openai-deep-research@49ddcd9, deep-research@8a343e2, crewai-deep-research@49e2b12)·음성(react-voice-agent@999ca2b)·브라우저(browser-use@6aeaa42)·computer-use@174adf6·office-mcp@7e95c6e·codex@cede40e 문서 작업 | 설비 판단 경로 밖, 유료 API(OpenAI Realtime·Tavily)·k8s·VNC 전제, 요구 0건(REFERENCE_ADOPTION A07~A09·T03·T08·X06) |
| 게이트웨이 크레딧·JWT 서브도메인 테넌트(gateway@2567edc `CreditValidationFilter.java`) | 단일 테넌트 교육 환경, 결제 요구 없음(REFERENCE_ADOPTION C04) |
| 에이전트 마켓플레이스(agents.github.io@cdc78f0) | 랜딩 화면뿐, 백엔드 없음(REFERENCE_ADOPTION D04; marketplace 뷰에 agent 항목 0). vue3의 마켓플레이스는 **프로세스 정의** 패키지 설치(`ProcessDefinitionMarketPlace.vue:509-520`) — G1 소관 |
| 스킬 git 저장소·PR 화면 전체(vue3 `SkillGitHistory.vue` 889줄, deepagents `skills_router.py` PR 경로) | 교육에 git 원격 저장소·권한 관리가 과함. #7은 "변경 전·후 비교 게이트" 개념만 로컬 브랜치로 |
| agent-feedback 결함 경로(`core/learning_committers/skill_committer.py:155-157,197-206` 예외를 "건너뜀"으로 COMPLETED) | REFERENCE_ADOPTION P04에 기록된 결함 — #5 구현 시 따라 하지 않음 |
| mem0 장기 메모리 자체(completion `mem0_agent_client.py`) | 임베딩·벡터 저장소·키 필요. #8은 시험 대화까지만 권장, 메모리는 선례 그래프(`precedents`)로 대체 가능 |
| 겹침(한 줄): 결정론 고착화(completion `deterministic_generator.py`, deepagents `core/deterministic/`) | G1/G3 소관(value-gaps #9, teachable 1-7) |

### 5. 상위 5개 추천

1. **#1 에이전트 스킬 작성·주입** — 구현이 가장 작고(HYD가 고정한 cliagents에 `add_skill`이 이미 있음, 워커는 `skills`를 읽고 버리는 중), 랩업 "에이전트·툴을 만들어 붙여 써 본다"의 첫 장면이 된다. #2·#5·#6·#7이 모두 이것을 전제로 한다.
2. **#3 MCP 등록·검증** — 회의가 가장 길게 설명한 "MCP를 하나 더 붙인다"(L123-138)를 학생이 끝까지(만들기→검증→등록→사용) 하게 하는 마지막 고리. 지금은 SQL 손편집과 재기동이라 랩업이 끊긴다.
3. **#2 에이전트 정의(프로필·도구·스킬·모델)와 서브에이전트** — 사용자 10-08 "에이전트 생성…ProcessGPT처럼"의 본체. DB 열은 이미 제품과 같아서 "정의가 실행 설정이 되는" 변환만 만들면 된다.
4. **#7 변경 전·후 회귀 검증 게이트** — 실라버스 마지막 SDD 랩업("기존 기능을 깨지 않고 추가")과 같은 생각을 업무 규칙·스킬 변경에 적용해, 승인(사람)과 검증(코드)의 역할 분담을 보여 준다. HYD 회귀 스크립트·dmn-mcp를 재사용하므로 중간 크기.
5. **#6 스킬 A/B 채점** — 대표가 요구한 "AI 결과를 평가할 수 있어야"(value-gaps #1)를 에이전트 스킬에 적용한 실물. 매뉴얼 60/40 분할·스킬 유무 비교는 학생이 콘솔 숫자로 바로 판정할 수 있다.

차순위: #5 피드백 학습 순환(가치 상, 크기 큼 — #1·#7 뒤에 두면 구현 위험이 줄어듦), #4 프로세스 엔진 MCP(작고 시스템 전체와 이어짐).

## 부록 C — 온톨로지·데이터·전략 상세 (O1~O19 = 아래 표 #1~#19)

(2026-10-08 작성 완료. 서브에이전트 G3, 저장소 파일 수정 없음)

조사 기준(코디네이터 10-08 추가 지시 반영): ① 회의 근거는 `docs/handoff/sources/meeting-2.txt`(HYD 1~461행)뿐. meeting-1.txt는 다른 사업 개념 자료라 요구 근거로 쓰지 않음. ② Text2SQL 전용 엔진 이식은 목록에서 제외(HYD는 에이전트가 스키마·메트릭을 보고 SQL·PromQL을 직접 만듦). neo4j-text2sql·robo-data-text2sql은 카탈로그·리니지 등 다른 기능 근거로만 봄. ③ 행마다 원본 커밋 SHA와 경로.

### 1. 읽은 것 / 못 읽은 것

#### HYD 기준선 (저장소 HEAD 6033768, 2026-10-08)
- `docs/handoff/verification/2026-10-08/value-gaps.md` 전체, `teachable-candidates.md` 전체, `TODO.md` 1~50행
- `docs/handoff/REPO_GAP.md` 전체, `REFERENCE_ADOPTION.md` O01~O05·P03·D02·T05·T06 행(50·51·56·58~64행)
- `docs/handoff/sources/meeting-2.txt` 1~30·60~70·250~290·436~450행(키워드 grep으로 1~461행 전체 훑음)
- `it/neo4j/v2/schema.json`(클래스 46·관계 72 목록·핵심 속성), `scripts/ontology_v2.py`(머리·함수 목록·`kpi_role_integrity` 432~462)
- `it/process/procsvc/ingest.py` 1~25, `kgadmin.py` 1~20, `ddl_sync.py` 1~20, `main.py` `/api/kg/*` 라우트 목록(954~1121)
- `it/portal/www/index.html` 탭(20~34), `enterprise.js` `loadGraph`(53~93), `hitl.js` 지식 관리 API 호출(180~611)

**못 읽은 것:** `docs/회의자료/대표발언_20261001_온톨로지_정리본.md` — 이 클라우드 체크아웃에 `docs/회의자료/` 폴더가 없음(`find`로 0건). 대표발언 인용은 value-gaps.md·teachable-candidates.md에 옮겨 적힌 문구로만 씀(2차 인용 표시).

#### 원본 레포 (클론 위치 `/tmp/claude-0/refs/`, depth 1)

| 레포 | 커밋 | 읽은 것 |
|---|---|---|
| ontology-studio (O01) | `20afcde` (2026-10-08) | README 1~80, `backend/src/modules/{ontology,ontology_runtime,release,quality,board,document_indexing}/*.py` 모듈 머리말 전부, `skills/ontology-build/SKILL.md` 101~212, `skills/ontology-brief-draft/SKILL.md` 1~40, `frontend/src/features/ontology/*.vue` 목록·줄수 |
| ontologic (O02) | `e72adf1` (2026-08-13) | `specs/README.md` 전체(001~009 상태표), `specs/001.../spec.md` 요구 FR-001~029 제목(143~225), `003.../spec.md` US2·US4(85~160), `008.../spec.md` US2~US4(126~200), `what-if-simulator/PRD.md` 1~80, `simulation_engine.py` 90~120·204~320·395~440, 모듈 8개 머리말, `api/main.py` 라우트 목록 |
| ontologic/data-fabric (서브모듈 jinyoung/robo-data-fabric) | `af48f15` (2026-03-27) | `README_UI.md` 1~50, `backend/app/routers/{datasources,query}.py` 라우트 목록(다종 소스 등록·스키마·샘플·`/extract-metadata`·materialized table), 서비스 줄수 |
| robo-data-catalog | `cf41148` (2026-09-22) | README 1~70(공유 그래프 계약·API), `enrichment/{description,foreign_keys,orchestrator}.py`·`lineage/sql_extract.py`·`search/semantic.py`·`integrations/data_fabric.py` 머리말·심볼, `specs/` 목록 |
| robo-data-analyzer | `3039549` (2026-09-22, main; ontologic 고정 브랜치는 `refactor` — 미대조) | README 1~50, `pipeline/meaning/` 목록·rule 심볼 |
| robo-insight-domain-layer (ontologic `domain-layer`) | `11de767` (2026-04-09) | `PRD-schema.md` 1~40, `app/` 파일 줄수, `services/whatif/{simulation_engine,model_validator,feature_view_builder,correlation_engine}.py`·`data_source_linker.py`·`schema_generator.py`·`deep_agents/layer_agents.py` 머리말, `routers/whatif.py` 라우트(471~1546), `models/ontology.py` 3~445 KPI 레이어 |
| robo-data-glossary (ontologic 서브모듈) | `b6fac84` (2026-03-27) | README 1~40 |
| process-gpt-glossary (T06) | `6a29cd9` (2026-04-23) | README 1~50, `supabase/init/10-app-schema.sql` 50~51, `backend/service/glossary_bulk_service.py` 함수 목록·544~580 |
| robo-data-security-guard (ontologic `data-secure-guard`) | `a3b7707` (2026-01-27) | README 1~60(RBAC API·Go MySQL 와이어 게이트웨이·감사 로그) |
| ontologic/data-platform-olap (서브모듈 아님, ontologic 트리 안 폴더) | `e72adf1` | README 1~40(AI Pivot Studio, Mondrian 큐브·자연어 피벗), `backend/app` 목록 |
| ontological-db (O03) | `3179cc7` (2026-08-24) | README 136~164(spec 001~011 상태표) |
| ontological-db-enterprise-custom (O04) | `2fd0ac2` (2026-09-28) | README 목차(O03과 같음), `specs/` 목록(O03과 동일 11개), `docs/00~08` 목록 |
| process-gpt-knowledge-graph (O05) | `47ca723` (2024-02-15) | 전체(파일 2개: `.gitignore`, `README.md` 한 줄 `# process-gpt-knowledge-graph`) |
| process-gpt-strategy (P03) | `1db85d3` (2026-07-26) | README 6~21·95~160, `app/{measurement,impact_analysis,contribution,chat,strategy_ops,survey}.py` 머리말·함수 목록(줄 번호) |
| process-gpt-strategy-skill (D02) | `f4d050d` (2026-07-26) | `SKILL.md` 목차·317~343·389~410, `references/validation-checklist.md` 목차 |
| process-gpt-visionparser (T05) | `8cf53d3` (2026-07-31) | 파일 목록 39개, README 1~25 |
| process-gpt-vue3 `ontology/` | `a4f0a85` (2026-10-08) | `ontology/SCHEMA.md` 목차·56~64(Strategy 레이어)·102~136·191~205(Governance 보류) |

**못 읽은 것 / 미확인**
- ontologic 서브모듈 `robo-data-frontend`·`agent-scheduler`·`node-local-agent-scheduler`·`infra`·`antlr-code-parser`·`process-gpt-bpmn-extractor`: G3 핵심이 아니어서 초기화하지 않음(미확인). `domain-layer`·`robo-data-analyzer`·`data-secure-guard`는 서브모듈 경로 초기화는 실패했으나 같은 레포를 `add_repo` 후 단독 clone해서 읽음(위 표).
- robo-data-analyzer는 ontologic이 고정한 `refactor` 브랜치가 아니라 `main` HEAD를 읽음 — 고정 커밋과 다를 수 있음.
- neo4j-text2sql·robo-data-text2sql(`25ab12a`): 코디네이터 지시 ②에 따라 엔진은 대상 아님. 카탈로그·리니지 근거로 쓸 부분이 robo-data-catalog에 이미 있어 본문은 다시 읽지 않음.
- `docs/회의자료/대표발언_20261001_온톨로지_정리본.md`: 체크아웃에 없음(위).

### 2. 표 — HYD에 빠진 기능 (가치 순)

표기: 원본 근거는 `레포@커밋:경로:줄`. 크기는 모두 **예상**(작음 = 기존 기능에 데이터·검사 한 덩어리, 중간 = 새 계산 + 화면 한 덩어리, 큼 = 새 층·새 원천·새 엔진). "대표발언"은 체크아웃에 원문이 없어 value-gaps.md에 옮겨 적힌 문구를 2차 인용한 것이다.

| # | 빠진 기능 (가치 문장) | 원본 근거 | HYD 현재 | 판정 | 강의 가치 | 구현 크기(예상) | 랩업 후보 | 회의 근거 줄 | value-gaps / teachable |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **수강생이 환율·부품가·외기 온도·조치 선택을 바꿔 몇 주 동안 가동률·생산량·비용·이익이 시간에 따라 어떻게 엇갈리는지 시뮬레이션해서, 상충의 "크기와 시점"을 알아보기** (What-if: 인과 지도 위 시간 루프·지연·누적 변수·시나리오 비교) | ontologic@e72adf1:`what-if-simulator/simulation_engine.py:204-275`(월 단위 시간 루프·노드 갱신·trace), `:290-305`(엣지 lag 반영), `:395-440`(Stock 변수 누적·감가), `edge_based_simulation.py:48-67,424,681`(엣지별 소형 모델·`explain_path`); robo-insight-domain-layer@11de767:`app/services/whatif/simulation_engine.py:1-15,124,331`(온톨로지 그래프 위 증분 DAG 전파, lag Day0~+3, `compare_scenarios`), `app/routers/whatif.py:1183,1277,1406-1546`(simulate·compare-scenarios·시나리오 저장/재실행) | 구조만 있음: `it/neo4j/v2/instances.cypher:552-564`(ExternalVariable 4개 + INFLUENCES sign·strength·condition), `docs/bsc-conditions.md:5-20`(경로 부호 곱·high/medium/low 정성 가중, "확률·금액·실측 영향량이 아니다"), `it/agent/agentsvc/forecasting.py`·`instances.cypher:568-580`(설비 물리 평형값 Forecast, horizon `steady-state`). 시간축 지표 시뮬레이션 0 | 얕음 | **상** — 대표가 든 환율·부품가 예(2차)와 납기 vs 설비 상충(L386-413)을 숫자로 굴려 "온톨로지를 왜 만드나"에 답함. 사용자 10-08 "있으면 엄청 좋은데 누락" | **큼** — 계수·지연 속성 추가, 루프 엔진, 시나리오 저장, 결과 차트. 레포 엔진은 판매 도메인 수식이 코드에 박혀 있음(`simulation_engine.py:395-440`) → HYD 변수로 새로 써야 함 | INFLUENCES에 `coef`·`lagWeeks`를 붙이고 `simulate(scenario, weeks=12)`가 주마다 지표 4개를 갱신해 콘솔 표·trace를 찍는 스크립트를 Claude Code로 만들기(같은 입력=같은 결과 단위 시험 포함) | meeting-2 L374-378(주문량·원가·부품별 원가·에너지 효율 데이터), L386-413(납기 vs 설비 상충) | TODO.md "다음 할 일 10-08" ②; teachable 1-5; value-gaps 머리 "이미 기록" |
| 2 | **수강생이 처리 기록·업무 DB에서 KPI 실적을 자동 계산해 목표 대비 달성률과 측정 이력을 보고, "지표가 이름표가 아니라 숫자"임을 알아보기** | process-gpt-strategy@1db85d3:`app/measurement.py:1-8`(그래프 KPI → 실행 데이터로 current_value·이력), `:118`(`_fetch_external_value` 외부 값), `:135`(`compute_kpi_value`: instance_count·avg_duration_hours·form_value_sum·survey_score·manual), `:224,284`(`record_measurement`·`measure_all`); README 6~13; process-gpt-vue3@a4f0a85:`ontology/SCHEMA.md:62`(KPI current_value·last_measured_at) | Measure에 목표·계산식·임계값만: `it/neo4j/v2/schema.json:117-`(Measure 속성 id·formula·target·thresholdWarn/Crit), `instances.cypher:29-34`; `docs/ontology/schema-v2.md:99`가 "목표 대비 실적 시계열"을 명시적으로 뺌. 코드에 current_value·achievement 0건(grep) | 빠짐 | **상** — 대표 계층(KPI가 맨 위, 2차)의 꼭대기가 숫자가 되어야 #1·#3·금전 손익의 "무엇이 나아졌나"를 잴 기준이 생김 | **중간** — Measure.formula 해석기 + 처리 건(`bpm_proc_inst`/todolist)·업무 DB·Timescale 집계 + 측정 이력 노드/테이블 + 포털 표 1개 | `msr:downtime`·`msr:op-profit` 두 지표의 formula를 처리 건·업무 DB에서 계산해 `Measure.actual`과 이력 행을 쓰는 `measure_all.py`를 만들고 콘솔에 목표 대비 %를 찍기 | meeting-2 L5-10(최상위 BSC·목표·measure를 맵으로) | value-gaps #3(앞 절반) |
| 3 | **수강생이 목표에 못 미친 KPI에서 출발해 그 지표를 움직이는 업무·조치·설비·담당으로 거슬러 올라가 원인 후보 순위를 보고, 결과→원인 추적을 알아보기** | process-gpt-strategy@1db85d3:`app/impact_analysis.py:1-20`(결정적 역추적, LLM은 "진단 후보"만 덧붙임), `:219`(`_collect_kpi_downstream`), `:394`(`_rank_candidates`), `:456`(`impact_kpi`), `:509`(`impact_strategy` 전략 하향·스킬 개선점); README 119~122 | 방향이 앞으로만: dmn-mcp `tradeoffs(skill_ids)`(`it/dmn-mcp/dmn_mcp/tools.py:135`)가 조치→AFFECTS→INFLUENCES→Measure(`docs/bsc-conditions.md:7`). 지표에서 거꾸로 가는 질의·순위 없음 | 빠짐 | **상** — 같은 그래프를 반대로 걸으면 "왜 이번 달 가동률이 떨어졌나"에 답함. #2 실적이 있어야 의미 | **중간** — Cypher 역방향 질의 + 처리 건 지표(지연·재작업·실패) 결합 순위 + 화면 1개(#2 선행) | 미달 Measure 하나를 받아 INFLUENCES·AFFECTS·Task·Role을 역으로 걷고 처리 건 지연으로 점수 매긴 원인 후보 Top 5를 출력하는 MCP 도구 `impact_kpi`를 만들어 에이전트가 콘솔에서 부르게 하기 | meeting-2 L5-8(BSC→프로세스→리소스 계층, 사고 기록을 피드백으로) | value-gaps #3(뒤 절반) |
| 4 | **수강생이 회사 DB가 한 종류가 아닌 현장(예: 업무 DB + 두 번째 종류 DB)에서 데이터를 옮기지 않고 한 창구로 묶어 조회하고, 온톨로지가 "그 값이 어디에 있나"를 안내하는 역할을 알아보기** (데이터 패브릭: 다종 원천 등록·스키마 탐색·교차 뷰) | ontologic/data-fabric(jinyoung/robo-data-fabric)@af48f15:`backend/app/routers/datasources.py:56,134,247,401-475,552`(접속 시험·원천 유형·등록·스키마/테이블/샘플·메타 추출), `routers/query.py:18,32`(통합 SQL·materialized table), `README_UI.md:5-12`(MySQL·PostgreSQL·Neo4j·MongoDB 등); ontology-studio@20afcde:`backend/src/modules/ontology/datafabric_client.py:1-15`(이름으로만 원천 참조, 자격증명 미보유), `skills/ontology-build/SKILL.md:160-164`(여러 원천에 걸친 클래스는 미리보기→`datasource_view_create`); robo-data-catalog@cf41148:`integrations/data_fabric.py:34,238-280` | 원천마다 따로: 업무 DB(Supabase 1종)·Timescale·Prometheus를 각자 MCP로 읽음(`docs/enterprise-catalog.md:1-5`, InputData `datasource` 속성 `schema.json:1250`). 두 번째 종류 DB·통합 창구 없음. HANDOFF §2는 "구현하지 않고 후반 설명"(teachable 1-1 인용) | 빠짐 | **상** — 회의가 "다음 확장"으로 지목, 사용자 10-08 개발 가정 대상 | **큼** — 두 번째 DB 컨테이너·페더레이션 계층(MindsDB 또는 Trino/FDW)·카탈로그 등록 + 에이전트 경로 변경. HANDOFF §2 확정 방향 변경 선행 | 두 번째 DB(예: MySQL "CMMS")를 compose에 띄우고 postgres_fdw 또는 작은 페더레이션 MCP로 설비 코드를 조인하는 뷰를 만든 뒤, 에이전트가 InputData의 datasource를 보고 그 창구로 질의하는 로그를 콘솔에서 확인 | meeting-2 L63-67(그래프에는 "값이 어느 DB에 있다"는 링크만), L438-447(현장 DB는 오라클·SAP 등 여럿 → 데이터 패브릭으로 확장) | teachable 1-1; value-gaps #6 |
| 5 | **수강생이 온톨로지 클래스(설비·정비이력 등)를 테이블에 묶고 그 클래스의 "행위"(정해진 매개변수 SQL)를 등록해, 그래프에 값을 복사하지 않고도 클래스가 자기 데이터를 가져오는 구조를 알아보기** (가상 클래스 바인딩·행위·SQL 안전 3중 방어) | ontologic@e72adf1:`specs/001-datasource-backed-virtual-classes/spec.md:159-225`(FR-005~029: 바인딩=허용 목록, 저장 전 스모크 실행, 타입 렌더, 행 상한, 테이블 범위, 기밀, 답변에 그래프+데이터 근거); ontology-studio@20afcde:`backend/src/modules/ontology/datasource_exec.py:1-15,233,424,458,501`(타입 바인딩·템플릿 검증·LIMIT), `datasource_api.py`, `publish.py:1-25`(가상 클래스를 그래프 제약으로만 발행, 인스턴스 0건), `frontend/src/features/ontology/DataSourceBindingPanel.vue`(614줄) | 컬럼 단위 포인터만: InputData가 datasource/catalog/schema/table/column/assetColumn을 가짐(`schema.json:1192-1260`), "설비 1행·단일 컬럼" 계약(`docs/enterprise-catalog.md` A068 절), 규칙 임계→SQL(`it/process/procsvc/main.py:1121-1135` `/api/kg/rules/sql`). 클래스↔테이블 바인딩·저장된 행위·스모크 실행 없음 | 얕음 | **상** — "현황값은 그래프에 안 넣고 DB 링크만"(L63-67)을 클래스 단위로 완성. #4의 실제 손잡이 | **중간** — Asset/Part/Supplier 등 3클래스 바인딩 + 행위 레지스트리 + 스모크 실행 + MCP 도구 1개 | `Part` 클래스를 `ent.parts`에 바인딩하고 행위 `price_by_supplier(part_id)`를 등록(저장 전 스모크 실행·행 상한)한 뒤 에이전트가 Cypher가 아닌 행위 호출로 부품가를 읽는 콘솔 로그 보기 | meeting-2 L51-58(규칙 변수 a·b·c 값은 DB에서), L63-67 | teachable 1-1 일부; value-gaps #6 일부 |
| 6 | **수강생이 AI와 대화(되묻기)하며 회사 목표·지표·인과 화살표(BSC 전략맵)를 직접 만들고, 검증 4항(고립 목표·운영 과업 오인·역행 화살표·측정 불가 목표)으로 AI 초안의 틀린 곳을 짚어 보기** | process-gpt-strategy-skill@f4d050d:`SKILL.md:167-182`(소크라테스식 제약), `:228-282`(하향식 초안→구체화), `:317-343`(검증 4항·Mermaid·최종 승인), `references/validation-checklist.md:6-40`; process-gpt-strategy@1db85d3:`app/chat.py:1-12,487`(채팅 편집은 타입드 툴콜만, REST와 같은 `strategy_ops` 경로) | 지도는 미리 넣음(`instances.cypher:29-56`). 검증은 일부만: 관점 소속·역행 금지(`scripts/probe_semantic_links.py:72-74` Q16/Q17), 선행·후행 역할(`scripts/ontology_v2.py:432-462`). 대화형 생성·"운영 과업 오인" 검사·채팅 편집 없음 | 얕음 | **상** — 회의 첫머리가 이 스키마 정리(L1-14), 대표 "AI한테 스무고개… 스키마를 만들어 달라"(2차) | **중간** — 스킬 문서 이식(HYD 도메인 질문) + 검증 4항 중 빠진 2항 코드화 + 그래프 쓰기 도구(승인 뒤) | D02 스킬을 HYD용으로 고쳐 Claude Code와 인터뷰해 유압 공장 전략맵 초안을 받고, `ontology_v2.py validate`에 "운영 과업 오인·측정 불가 목표" 검사 2개를 추가해 초안의 오류를 잡기 | meeting-2 L1-14(6계층·최상위 BSC·목표/measure), L28 | value-gaps #2 |
| 7 | **수강생이 "답하고 싶은 질문"(골든 퀘스천)을 먼저 적으면 AI가 클래스·관계 초안을 내고, 편집 화면에서 고친 뒤 질문을 실제로 돌려 스키마가 답하는지 확인해 보기** (스키마 AI 초안 + 스키마 편집기 + 질문 주도 검증) | ontology-studio@20afcde:`skills/ontology-brief-draft/SKILL.md:1-40`(소스를 보고 의도·골든 퀘스천 초안), `skills/ontology-build/SKILL.md:105-127`(Phase 1 질문→클래스·관계·질의 경로 `_schema_design.json`), `:170-175`(Phase 3 질문 실제 실행, FAIL이면 최대 3회 되돌림), `frontend/src/features/ontology/OntologySchemaPanel.vue:217-325`(클래스·관계 추가·삭제), `OntologyBuildBriefPanel.vue`; robo-insight-domain-layer@11de767:`app/routers/ontology.py:670`(`/generate`), `app/services/schema_generator.py:166,210,375`(문서→스키마, 피드백 반영, 다층 생성), `deep_agents/layer_agents.py:1-3`(레이어별 추출 에이전트) | 스키마는 사람이 `it/neo4j/v2/schema.json`을 직접 고치고 `scripts/ontology_v2.py gen/validate/queries`(`:1-8`)로 산출·검사. 포털 편집은 조치 방법(Skill)만(`main.py:980-995`, `hitl.js:266-267`). 골든 퀘스천은 매뉴얼 배치에만(`manual_golden.py`, REPO_GAP §6 B3) | 얕음 | **상** — 회의 "스키마는 경험 있는 자가 만들어 놓고"(L270)의 그 "만드는 과정" 자체를 실습. 랩업 계약의 "온톨로지 스키마" 막과 직결 | **중간** — 스키마 초안 스킬(HYD 출발본) + 질문 실행 검증 루프 + (선택) 포털 스키마 편집 카드 | 골든 퀘스천 3개("이 부품 공급사 납기는?" 등)를 주고 Claude Code가 `schema.json`에 클래스·관계를 추가한 뒤 `gen`→`load`→`queries`로 세 질문이 답하는지 PASS/FAIL을 콘솔로 보기 | meeting-2 L1-14, L253-271(스키마는 정해 두고 인스턴스는 인제스천), L284(클리어하고 다시) | 신규(value-gaps #2를 BSC 밖 전체 스키마로 넓힌 것) |
| 8 | **수강생이 테이블·컬럼 이름이 코드이고 FK도 없는 옛 DB에서, 저장 프로시저·샘플 값을 근거로 AI가 뜻과 테이블 관계를 복원하게 하고 사람이 승인해 카탈로그로 만드는 과정을 알아보기** (레거시 메타데이터 증강) | ontologic@e72adf1:`specs/008-legacy-metadata-to-ontology/spec.md:101-172`(US1 코드명 대조군, US2 프로시저·샘플로 설명 복원·추론 관계를 "추론"으로 구별·정답지 수치, US3 증강 메타로 테이블 찾기·충돌은 사람에게); robo-data-catalog@cf41148:`enrichment/description.py:1-10,39`(샘플 기반 설명, 기존 설명 보존), `enrichment/foreign_keys.py:1,49`(FK 추론), `enrichment/orchestrator.py:120`; robo-data-analyzer@3039549(main):`README.md:7-17`(DDL·파서 사실→호출·테이블 접근·업무 의미), `pipeline/meaning/` | 깨끗한 DDL과 주석만 적재: `it/process/procsvc/ingest.py:1-15`("HYD's limited DDL adapter"), `docs/enterprise-catalog.md:1-20`(주석 보존·검토 적재), 주석 변경 감지 `ddl_sync.py:1-15`. 코드 해석·설명 생성·FK 추론 없음 | 빠짐 | **상** — 현장 DB 현실(코드명·FK 없음)을 다루는 유일한 실습, 자동화는 추출까지·승인은 사람이라는 원칙을 보여 줌 | **큼** — 코드명 예제 DB·프로시저 픽스처 + 증강 작업(LLM) + 정답지 대조 + 승인 화면 | `TB01/C001` 식 코드명 테이블 3개와 프로시저 2개를 만들고, Claude Code가 프로시저 조인·주석을 읽어 컬럼 설명·추론 FK 제안 JSON을 내면 정답지와 대조해 맞춘 비율을 출력 | meeting-2 L286-293(기존 DDL에서 출발해야 런타임 SQL이 동작), L253-271 | value-gaps #7; teachable 1-2 |
| 9 | **수강생이 업무 DB의 SQL(프로시저·적재 쿼리)에서 "이 데이터가 어디서 나와 어디로 흘러가 누가 쓰나"(읽기·쓰기·흐름) 계보를 뽑아 그래프로 보고, 값이 틀렸을 때 거꾸로 따라가 보기** (데이터 리니지) | robo-data-catalog@cf41148:`lineage/sql_extract.py:1-20,74,394`(INSERT/MERGE 타겟·SELECT/JOIN 소스 → READS·WRITES·DATA_FLOWS_TO), `lineage/queries.py`, README "계보" API(`GET /robo/lineage/`, `POST /robo/lineage/analyze/`), "공유 그래프 계약"(_owner로 소유 구분) | 원천 출처만: InputData·System의 `source_id`·`ingest_batch`·`_ingest_history`(`schema.json` InputData 속성), 매뉴얼 KnowledgeSource sha256·extractor. 테이블 간 흐름·SQL 계보 0건(grep lineage 0) | 빠짐 | **상(조건부)** — CLAUDE.md §4 "시스템 문서는 데이터 리니지(출생→변환→저장→소비)가 목적"과 맞닿음. 회의 직접 언급은 없음 | **중간** — sqlglot(HYD 이미 의존, `ingest.py:24`)으로 SQL 파싱 → 관계 투영 + 지식 지도 열 1개 | `it/supabase/migrations`의 뷰·함수 SQL을 sqlglot으로 파싱해 `(:Table)-[:DATA_FLOWS_TO]->(:Table)`을 만들고, "생산 실적 뷰가 어느 원천 테이블에서 오나"를 Cypher로 콘솔 출력 | 회의 언급 없음(meeting-2 1~461) | teachable 1-2 일부(리니지 부분) |
| 10 | **수강생이 매뉴얼이 말한 변수(예: 냉각수 출구 온도·부품 납기)가 회사 DB의 어느 테이블·컬럼에 있는지 AI가 후보를 점수와 근거로 제시하게 하고, 확신이 낮거나 겹치면 사람이 고르는 "역바인딩"을 해 보기** | ontology-studio@20afcde:`backend/src/modules/ontology/entity_matcher.py:1-15`(컬럼 0.6·타입 0.2·이름 0.2, 이름이 가장 약한 신호), `:203,330,346,358`(`score_table`·`score_entity`·`_verdict`·`match_all`), `doc_ontology.py:1-12,47,106`(문서 엔티티→테이블 미리보기·적용), `frontend/.../BindingCandidatePanel.vue`; ontologic@e72adf1:`specs/008.../spec.md:149-172`(US3 충돌·근거 부족은 자동 바인딩 안 함); robo-insight-domain-layer@11de767:`app/services/data_source_linker.py:157,239,520`(노드별 원천 자동 추천·확정) | 사람이 고름: DDL 미리보기에서 강사가 컬럼 선택(`docs/enterprise-catalog.md` "원천 변경을 반영하는 순서" 2~4), 규칙 변수와 InputData `variable` 이름을 손으로 맞춤(`ingest.py:6-10`) | 얕음 | **중** — L51-58 "변수 값이 어디에 연결되나"를 자동 후보+사람 승인으로 보여 줌. #5·#8과 이어짐 | **중간** — 점수 함수 이식(HYD 이름 체계) + 미리보기 응답에 후보·근거 + 포털 카드 1개 | DMN 규칙이 TESTS하는 변수 목록과 `describe_catalog` 결과를 받아 컬럼·타입·이름 점수로 후보 Top 3와 판정(자동/사람확인/충돌)을 내는 함수를 만들고 콘솔 표로 보기 | meeting-2 L51-58, L63-67 | 신규 |
| 11 | **수강생이 센서·처리 기록에서 통계(시차 상관·Granger)로 "무엇이 무엇을 움직이나" 후보를 찾고, 그것을 단언이 아닌 "가설"로 표시해 사람이 승인·거부·방향 반전하며, 사람이 그린 상충 지도와 대조해 보기** | ontology-studio@20afcde:`backend/src/modules/ontology/causal_ontology.py:1-12`(통계는 제안·사람이 결정, 재실행해도 판정 보존), `:92,296,341`(`discover`·`decide`·`apply`), `provenance.py:1-12`(전략별 출처), `frontend/.../CausalEdgeReviewPanel.vue:1-30`(가설 배지·승인 행만 승격); ontologic@e72adf1:`specs/003-ontology-build-strategies/spec.md:85-116,142-160`(US2 방법·강도·p값·시차, 거부 보존, US4 구조 위 인과 덧붙임); `what-if-simulator/causal_discovery.py:117,195,275`; robo-insight-domain-layer@11de767:`app/services/whatif/correlation_engine.py:1-15` | 상충 부호는 사람이 선언(`docs/bsc-conditions.md`, `instances.cypher:555-564`). 가설/단언 구분·데이터 검증 없음 | 빠짐 | **중** — 상충 지도를 데이터로 의심하는 태도. 단 TODO.md 10-08 What-if 범위가 "인과 자동 발견 이식은 하지 않는다"로 정해 둠 → 별도 결정 필요 | **큼** — 시계열 데이터 충분성(20배속 시뮬 기록), statsmodels 의존, 검토 화면 | Timescale의 TS1·외기·팬 속도 기록으로 시차 상관·Granger를 돌려 후보 엣지(방법·p값·lag)를 JSON으로 내고, 사람이 그린 INFLUENCES와 일치/불일치 표를 콘솔에 찍기 | meeting-2 L386-413(상충 판단) — 인과 발견 자체는 회의 언급 없음 | value-gaps #10; teachable 1-5 인과 발견 부분 |
| 12 | **수강생이 What-if의 영향 계수를 기록 데이터로 추정하고 앞 기간으로 학습·뒤 기간으로 검증(walk-forward)해서, 시뮬레이션 숫자를 믿어도 되는지 오차로 판정해 보기** | ontologic@e72adf1:`what-if-simulator/model_validation.py:1-14,155,171,387`(hold-out·잔차·엣지 함수 검증), `edge_based_simulation.py:188`(`setup_edge_models`); robo-insight-domain-layer@11de767:`app/services/whatif/model_validator.py:1-12,154,372`(Ridge·GB·RF expanding window, 체인 전체 검증), `feature_view_builder.py:1-6`(dataSource를 시간키로 JOIN, lag/delta/rolling 파생 뷰), `routers/whatif.py:732,884`(train-models·validate) | 계수 자체가 없음(strength high/medium/low 정성, `docs/bsc-conditions.md:13`). TODO DoD 4 "계수마다 출처, 출처 없는 계수 0건"만 정해 둠 | 빠짐 | **중** — #1을 "그럴듯한 숫자"에서 "검증된 숫자"로. AI 결과 평가(value-gaps #1)와 같은 태도 | **중간** — 시계열 피처 뷰 + 회귀 1종 + 백테스트 리포트(#1 선행) | 시뮬 기록에서 "팬 속도→TS1" 계수를 선형회귀로 추정하고 앞 70 %로 학습·뒤 30 %로 MAE를 찍어, 계수 노드에 `source=data, mae=…`를 적는 스크립트 | 회의 언급 없음 | 신규(TODO What-if DoD 4와 연결) |
| 13 | **수강생이 문서·표에서 뽑은 지식이 그래프에 바로 들어가지 않고 신뢰도 점수·스키마 형상 검사·원천 데이터 품질 규칙(결측·범위·중복·참조)을 지나 자동 적재/검수 대기/보류함으로 갈리는 것을 보고, "어떤 지식을 믿고 넣나"를 판단해 보기** (추출·원천 품질 게이트) | ontology-studio@20afcde:`backend/src/modules/quality/__init__.py:1-5`, `confidence.py:1-12,208,219`(S_c = G_onto × m_vocab × combine), `gate.py:1-8`(hard→DLQ, soft→검수), `shapes.py:1-12`(스키마에서 SHACL 형상 자동 생성), `expectations.py:1-12,70,196`(not_null·between·unique·in_set·fk), `lint.py:1-5`(고립 노드), `pipeline.py`, `ingest_gate.py:1-8`(그래프 쓰기 단일 진입점·actor/source/reason); `skills/ontology-build/SKILL.md:128-147,177-181` | 사람 검토 중심: 매뉴얼 미리보기·인용 검사·검토 커밋(`manual_review.py:1-5`, `hitl.js:516`), 스키마 준수 `validate`(`ontology_v2.py:330`)·`integrity`(`:399`)·쓰지 않는 요소 보고(`:464`), 골든 퀘스천(`manual_golden.py`), DDL 드리프트(`ddl_sync.py`). 점수 기반 분기·원천 데이터 품질 규칙·보류함 없음 | 얕음 | **중** — 인제스천(L253-285)을 "넣기"에서 "걸러 넣기"로. 데이터 품질은 패브릭의 한 축 | **중간** — expectation 5종 + 보류함 테이블 + 포털 카드 1개(점수식은 선택) | `ent` 업무 DB의 정비 이력 테이블에 not_null·between·fk 규칙 3개를 선언해 돌리고, 위반 행을 보류함 JSON으로 빼 콘솔에 원인 코드별 건수를 찍기 | 회의 직접 언급 없음(인제스천 L253-285 맥락) | 신규(value-gaps #1 "AI 결과 평가"의 인제스천 쪽) |
| 14 | **수강생이 전략목표마다 실행 과제(Initiative)를 두고 그 과제를 실제 업무 프로세스로 잇는 것(전략 → 과제 → 프로세스 후보 → 정의 생성)을 보고, 전략이 문서로 끝나지 않고 실행되는 길을 알아보기** | process-gpt-vue3@a4f0a85:`ontology/SCHEMA.md:63`(Initiative 상태·진척률·기한), `:131-133`(DRIVES·SOURCED_FROM·REALIZED_BY); process-gpt-strategy@1db85d3:`app/strategy_ops.py:235,244`(`_link_kpi_process`·`_link_initiative_process`); process-gpt-strategy-skill@f4d050d:`SKILL.md:389-433`(확정 전략 → 노드당 프로세스 후보 1~3 → `bpmn-process-generation-skill` 호출) | Process -ACHIEVES-> Objective만(`schema.json` 관계 목록). Initiative는 `docs/ontology/schema-v2.md:99`에서 "쓰지 않아 뺀 것" | 빠짐 | **중** — BSC 층과 프로세스 층을 잇는 마지막 고리. 프로세스 정의 생성(G1)과 겹침 | **작음~중간** — 클래스 1개·관계 2개·인스턴스 몇 개 + validate 규칙(G1 정의 생성은 별도) | `schema.json`에 Initiative·DRIVES·REALIZED_BY를 추가하고 "야간 세척 체계화" 과제를 기존 프로세스에 잇는 인스턴스를 넣어 `validate`·질의로 목표→과제→프로세스 경로를 출력 | meeting-2 L5(최상위 BSC 다음 프로세스) | 신규(G1 "자연어→프로세스 정의"와 한 줄 겹침) |
| 15 | **수강생이 같은 회사 데이터라도 역할마다 볼 수 있는 원천·테이블·컬럼이 다르고 민감 컬럼은 가려지며 모든 조회가 감사 기록으로 남는 것을 보고, 데이터 권한이 AI 에이전트에도 똑같이 걸리는지 확인해 보기** | robo-data-security-guard@a3b7707:`README.md:7-20`(RBAC 데이터소스→스키마→테이블 계층, 쿼리 재작성으로 LIMIT·컬럼 필터, 감사 로그), 아키텍처 도식 22~60; ontologic@e72adf1:`specs/001.../spec.md:184`(FR-014 PII 컬럼 제외), `:202-212`(FR-020~024 자격증명 미보유·SQL 미노출·로그에 접속 정보 없음) | 원천 단위 한 겹: 전용 읽기 계정 `hyd_enterprise_reader` + SQL guard(ent·읽기 전용)(`docs/enterprise-catalog.md:3-5`), 승인 전 에이전트는 조회만(CLAUDE.md §4). 역할별 테이블·컬럼 권한·마스킹·조회 감사 없음(grep PII 0) | 얕음 | **중** — 패브릭의 "권한" 축. 에이전트에 어떤 데이터를 줄지 판단하는 실무 감각 | **중간** — Supabase RLS·컬럼 권한 정책 + 역할별 연결 + 조회 감사 테이블(Go 게이트웨이는 안 가져옴) | 업무 DB에 정비원/생산관리자 역할을 만들고 RLS·컬럼 GRANT로 원가 컬럼을 막은 뒤, 같은 질문을 두 역할 연결로 돌려 결과 차이와 감사 행을 콘솔로 비교 | 회의 언급 없음(meeting-2 1~461) | 신규 |
| 16 | **수강생이 KPI 실적에 어떤 사람·에이전트·업무가 얼마나 기여했는지(가중 기여도)를 처리 기록에서 계산해 보고, 에이전트를 성과로 평가하는 기준을 알아보기** | process-gpt-strategy@1db85d3:`app/contribution.py:1-12`(KPI 측정과 같은 필터로 완료 인스턴스·todolist 수행 이력), `:170`(`kpi_contribution`), `:195`(전략 중요도 가중), `:279-319`(KPI·전략·수행자별 API) | 없음(처리 건·이벤트·트레이스는 있으나 KPI와 잇는 집계 없음 — teachable 1-8 "집계 없음") | 빠짐 | **중** — 에이전트 운영(G1/G2 옵스)과 BSC를 잇는 숫자. #2 선행 | **중간** — #2 위에 todolist 수행자 집계 1개 | #2의 실적 계산에 todolist `username`·agent_mode를 붙여 지표별 사람/에이전트 기여 비율 표를 콘솔에 출력 | 회의 언급 없음 | 신규(teachable 1-8과 한 줄 겹침) |
| 17 | **수강생이 만든 온톨로지와 골든 퀘스천에서 대시보드가 자동으로 구성되고(위젯 종류는 규칙이 결정, AI는 클래스 선택만), 말로 고친 변경은 diff를 사람이 승인해야 적용되는 것을 보기** | ontology-studio@20afcde:`backend/src/modules/board/compose.py:1-20,197`(골든 퀘스천 → 대시보드, 에이전트/엔진/결정적 코드 분업), `widget_map.py:1-8`(결정적 위젯 판정·근거 표시), `ask.py:1-8`(자연어→패치, 사람 승인), `query_gen.py:1-8`(집계는 서버, 값은 params); ontologic@e72adf1:`specs/006-visualization-and-report/spec.md:582-666`(차트·리포트, Draft) | 고정 대시보드: Grafana(`it/grafana/build_dashboard.py:110-113`)·포털 탭. 온톨로지에서 생성·자연어 편집 없음 | 빠짐 | **중** — KPI 실적(#2)을 보여 줄 화면을 "AI가 만들고 사람이 승인"하는 패턴으로 | **중간** — 위젯 규칙표 + Grafana JSON 생성 또는 포털 카드 | Measure 목록에서 단위·방향·frequency로 패널 종류를 정하는 규칙 함수를 만들고 Grafana 대시보드 JSON을 생성해 import, 판정 근거를 콘솔로 출력 | meeting-2 L434(자동으로 도는 에이전트 모니터링 화면) — 간접 | 신규 |
| 18 | **수강생이 ERP의 설비 코드와 정비 시스템의 설비 코드처럼 여러 원천에서 같은 개체가 다른 키로 들어올 때, 덮어쓰지 않고 "같다(SAME_AS)" 판단만 남기고 값 충돌은 검수로 보내는 식별자 해소를 해 보기** | ontology-studio@20afcde:`backend/src/modules/quality/identity.py:1-12,65,90,203,226`(식별 속성·이름 정규화 점수, 자동/검수 경계, 충돌 감지·해소), `ontology_runtime/entity_resolution.py:1-25`(말→키 후보 생성·재순위·판정) | 원천 1개라 문제 없음: 물리 식별(datasource/catalog/schema/table/column)로 InputData 동일성 유지(`ingest.py:12-14`). SAME_AS 0건 | 빠짐 | **중~하** — #4 다종 DB를 하면 바로 생기는 문제. 단독 가치는 낮음 | **중간** — 두 번째 원천(#4) 전제 | 두 원천의 설비 마스터를 읽어 이름 정규화·식별 속성 점수로 SAME_AS 후보와 값 충돌 목록을 콘솔에 출력(승인 전 그래프 미반영) | 회의 언급 없음 | 신규(#4 후속) |
| 19 | **수강생이 현장 용어(예: "토출압"·"PS1"·"펌프 압력")의 동의어와 정의를 용어집에서 승인 상태로 관리하고, 에이전트가 동의어로 물어도 같은 입력 데이터를 찾는 것을 보기** | process-gpt-glossary@6a29cd9:`supabase/init/10-app-schema.sql:50-51`(status Draft 기본·synonyms 배열), `backend/service/glossary_bulk_service.py:544-580`(엑셀/CSV 구조를 LLM으로 분석·휴리스틱 폴백); robo-data-glossary@b6fac84:`README.md:7-12`(LLM 용어 자동 추출) | 일부 있음: Measure·StateVariable·ExternalVariable `aliases`(`schema.json:134,567,656,834,882`), 스키마 프롬프트 aliases, 포털 명칭표 `names.json`. InputData 동의어·용어 승인 흐름 없음(REPO_GAP §6 B8 "선택·미착수") | 얕음 | **하** — 이미 aliases가 엔티티 인식을 맡음. 수업 3시간을 채우기 어려움 | **작음** — InputData aliases + 검색 1개 | InputData에 aliases를 추가하고 "토출압"으로 물었을 때 `in:ps1`을 찾는 질의를 Claude Code로 만들고 queries에 넣기 | 회의 언급 없음 | teachable 표3 "작은 것" |

G1·G2와 겹치는 것(한 줄씩): #14의 "프로세스 정의 생성"은 G1, #16의 에이전트 성과 집계는 G1/G2 옵스, 런타임 엔티티 해소(말→키, ontology-studio `ontology_runtime/entity_resolution.py`)와 문서 벡터 색인·하이브리드 RAG(`document_indexing/`)는 G2 영역이라 표에서 뺐다.

### 3. "HYD에 이미 있음"으로 뺀 것

| 원본 기능 | 원본 근거 | HYD 근거 | 메모 |
|---|---|---|---|
| 스키마 한 곳에서 제약·OWL·에이전트용 스키마 설명을 만들고 그래프가 스키마를 지키는지 검사 | ontology-studio@20afcde:`backend/src/modules/ontology/publish.py:1-25`(네이티브 스키마 투영), ontological-db@3179cc7 README 148(spec 006 RDF/OWL/SHACL 부분) | `scripts/ontology_v2.py:1-8`(gen·load·validate·queries), `:42`(제약), `:71`(TTL), `:122`(프롬프트), `:330`(validate), `:399`(integrity), `:464`(쓰지 않는 요소 보고) | 같은 역할. 차이 있음, 유지 |
| 지식 그래프 화면(층별 보기·한 경로 집중) | ontology-studio@20afcde:`frontend/src/features/ontology/OntologyGraphPanel.vue:222-226`(이웃 노드 펼치기); process-gpt-strategy@1db85d3 README 114~117(`/api/ontology/graph`·neighbors) | `it/portal/www/index.html:27`(지식 지도 탭), `enterprise.js:7,53-93`(스키마 층=열, 이상 패턴→증상→고장→원인→조치 경로 집중), agent `/api/ontology/graph`(`it/agent/agentsvc/main.py:245`) | 이웃 점진 펼치기만 없음 — 세부라 표에서 뺌 |
| 원천 변경분 증분 반영(멱등, 없는 대상에 연결 안 함) | process-gpt-strategy@1db85d3:`app/ontology_sync.py`(927줄) | `it/process/procsvc/ddl_sync.py:1-15`·`scm_sync.py`(docstring에 출처), `/api/kg/ddl/sync`·`/api/kg/scm/sync`(`main.py:1045,1054`) | REFERENCE_ADOPTION 56행 |
| 인제스천을 빼고 다시 하기(클리어·되돌리기) | ontology-studio `release/`·스키마 삭제 | `DELETE /api/kg/ingests/{batch}`(`main.py:1103`), 매뉴얼 배치 rollback(`hitl.js:414`) | meeting-2 L284 요구 충족 |
| 문서 인제스천 + 인용 위치 + 문서별 골든 퀘스천 | ontology-studio@20afcde:`frontend/.../GoldenQuestionReviewPanel.vue`, `skills/ontology-build/SKILL.md:170-175` | `procsvc/manual_golden.py`, `manual_locate.py`, `manual_review.py`(REPO_GAP §6 B2·B3) | 매뉴얼 범위만. 스키마 전체 질문 검증은 표 #7 |
| DDL 인제스천(주석 보존·검토 적재)과 주석·타입 드리프트 감지 | robo-data-catalog@cf41148 README "공유 그래프 계약"(설명 보존) | `procsvc/ingest.py:1-15`, `ddl_sync.py:1-15`(OK/MISSING/TYPE_CHANGED/COMMENT_CHANGED), `docs/enterprise-catalog.md` | 메타 "증강"은 없음 → 표 #8 |
| BSC 상충 부호·조건 평가 | (원본에 없음 — REFERENCE_ADOPTION 56: strategy엔 sign·조건 경로 계산 없음) | `docs/bsc-conditions.md:5-20`, dmn-mcp `tradeoffs`(`tools.py:135`) | HYD 자체 고안 |
| 선행·후행 KPI 역할과 전략맵 검증 2항(고립·역행) | process-gpt-strategy-skill@f4d050d:`references/validation-checklist.md:6-31` | `scripts/ontology_v2.py:432-462`(kpi_role_integrity), `scripts/probe_semantic_links.py:72-74`(Q16·Q17) | 나머지 2항·대화형 생성은 표 #6 |
| 외부 변수 클래스와 조치별 예측 노드 | ontologic@e72adf1:`what-if-simulator/PRD.md` 6.1 Driver 노드 | `schema.json:1496`(ExternalVariable), `instances.cypher:552-580`(환율·외기·전력 단가·수요, Forecast 9개) | 구조는 있음, 시간 시뮬레이션은 표 #1 |
| 읽기 전용 온톨로지 MCP(출처 반환) | ontology-studio@20afcde:`backend/src/modules/ontology_mcp/server.py` | hyd-dmn 13도구·Neo4j MCP·enterprise MCP(REPO_GAP §5 "HYD가 넓음") | G2와 공유 |
| 지식 변경 감사(누가·왜·전후) | ontology-studio@20afcde:`quality/ingest_gate.py:1-8`(actor/source/reason) | `schema.json` KnowledgeEdit(actor·kind·reason·before·result) | 같은 역할 |
| 엔티티 인식용 별칭 | process-gpt-glossary synonyms | Measure·StateVariable·ExternalVariable `aliases`, `schema_prompt.md` | InputData 동의어만 없음 → 표 #19(하) |
| 실행 기록의 그래프 투영(인스턴스·작업 항목) | process-gpt-vue3@a4f0a85:`ontology/SCHEMA.md:91-101`(Execution 레이어) | `schema.json` ProcessInstance·WorkItem·ExecutionProjection·CaseProjection | REPO_GAP §1 |
| 문서 OCR | process-gpt-visionparser@8cf53d3:`executors/executor.py`(전면 래스터화 VLM) | `procsvc/manual_sources.py`(텍스트 레이어 + 빈 페이지 OCR_REQUIRED 차단) | REFERENCE_ADOPTION 50행: 빈 페이지만 OCR이 후보, 작은 것 |

### 4. 가져오면 안 되는 것

| 대상 | 원본 근거 | 이유 |
|---|---|---|
| Neo4j → ontological-db(공개·enterprise) 교체 | ontological-db@3179cc7 README 145(spec 003 "`UNION` not yet"), O04@2fd0ac2 specs 동일 11개 | HYD 감사 질의·queries.cypher가 UNION·shortestPath·FOREACH를 씀 → 교체 시 감사가 거짓 통과(REFERENCE_ADOPTION 60~61) |
| process-gpt-knowledge-graph | O05@47ca723 파일 2개(README 한 줄) | 구현 없음 |
| What-if 레포 엔진 통째(MindsDB·판매 도메인 수식) | ontologic@e72adf1:`what-if-simulator/simulation_engine.py:395-440`(BRAND_EQUITY·LOYALTY 수식이 코드에 박힘), `mindsdb_connector.py`; domain-layer `whatif/mindsdb_model_factory` | 도메인 수식이 하드코딩이라 HYD엔 쓸 데가 없고 MindsDB 스택이 무겁다. 구조(시간 루프·lag·누적 변수·trace)만 HYD 변수로 새로 쓴다(TODO.md 10-08 "레포 통째 이식 안 함") |
| MindsDB 기반 data-fabric 서버 그대로 | ontologic/data-fabric@af48f15 `README_UI.md:49-51`(MindsDB 서버 전제) | 강의 PC 메모리(Docker 4 GB 기준, CLAUDE.md §5)에 서비스 하나 더 + MindsDB. 페더레이션은 postgres_fdw 등 가벼운 길로(표 #4 랩업) — 단 이건 크기 판단이며 확정은 착수 조사 때 |
| Go MySQL 와이어 보안 게이트웨이 | robo-data-security-guard@a3b7707 README 14~17 | HYD 업무 DB는 PostgreSQL(Supabase) — RLS·컬럼 GRANT로 같은 걸 보여 줄 수 있음(표 #15) |
| Text2SQL 전용 엔진 | neo4j-text2sql·robo-data-text2sql@25ab12a | 코디네이터 지시 ②: HYD는 에이전트가 스키마·메트릭을 보고 SQL·PromQL을 직접 만듦 |
| 전면 래스터화 VLM OCR | process-gpt-visionparser@8cf53d3 | 실물 PDF 텍스트 레이어로 10/10, VLM 호출 비용(REFERENCE_ADOPTION 50) |
| 설문 기반 정성 KPI 자동 발행 | process-gpt-strategy@1db85d3:`app/survey.py:1-8,199` | 설비 사례에 응답자·요구 없음. 가치 낮음 |
| 비즈니스 모델 캔버스(BMC) | process-gpt-strategy@1db85d3:`app/strategy_ops.py:138-158`, process-gpt-strategy-skill@f4d050d `references/bmc-*.md` | 유압 설비 강의 범위 밖. 전략맵(표 #6)만으로 충분 |
| OLAP 피벗 스튜디오 | ontologic/data-platform-olap `README.md:1-25` | Mondrian 큐브·자연어 피벗은 Text2SQL과 겹치고 KPI 실적(표 #2)로 충분. 실행 통계 분석은 G1(P01) |
| 결과 서술 LLM(data literacy) | ontologic@e72adf1:`what-if-simulator/data_literacy.py:1-14` | 숫자는 결정적 코드, 서술은 기존 에이전트가 함. 같은 입력 = 같은 순위 원칙(TODO.md) |
| KGE 링크 예측·누락 값 보정 제안 | ontology-studio@20afcde:`quality/kge.py:1-10`, `imputation.py:1-12` | 수십~수백 노드 그래프에서 의미 약함. "지어내지 않는다"는 원칙과 충돌 위험 |
| 온톨로지 패키지 내보내기·가져오기, 개발→운영 배포 | ontologic@e72adf1:`specs/009-ontology-export-import/spec.md`(Draft), ontology-studio `release/api.py:1-8` | 단일 강의 환경. 가치 하 |
| 질의 결과를 온톨로지 객체로 등록 | ontologic@e72adf1:`specs/008.../spec.md` US4 | Text2SQL 결과 객체화라 지시 ②와 겹침, 해피패스 데이터가 쌓일 위험 |
| Governance 레이어(Review·ResourcePR·Terminology) | process-gpt-vue3@a4f0a85:`ontology/SCHEMA.md:110-119,191-205`(원본도 "보류") | 원본도 미배포 |

### 5. 상위 5개 추천

1. **#1 What-if 시간 시뮬레이션(+#12 계수 검증을 그 안의 한 활동으로)** — 사용자가 10-08에 직접 "엄청 좋은데 누락"이라 했고, HYD에 외부 변수·INFLUENCES 부호·조건이 이미 있어 "부호 → 계수·지연 → 시간 루프"로 한 단계씩 올리는 수업 흐름이 자연스럽다. 회의 L386-413의 납기 vs 설비 상충을 숫자로 보여 준다.
2. **#2 KPI 실적 자동 측정 + #3 결과→원인 역추적** — 지금 지표 21개(value-gaps #3 인용)는 목표값만 있는 이름표다. 실적이 생겨야 What-if·금전 손익이 "무엇이 나아졌나"를 잴 수 있다. process-gpt-strategy 고정 코드(`measurement.py:135`, `impact_analysis.py:456`)가 그대로 참고가 되고 크기는 중간이다.
3. **#5 가상 클래스 바인딩·행위 → #4 다종 DB 한 창구(데이터 패브릭)** — 회의가 "다음 확장"으로 지목한 유일한 큰 블록(L63-67, L438-447)이고 사용자가 개발 가정 대상으로 꼽았다. #5(중간)를 먼저 하면 #4(큼)가 "두 번째 원천을 붙여도 에이전트 코드는 안 바뀐다"는 장면으로 짧아진다. HANDOFF §2 방향 변경이 선행 조건이다.
4. **#7 골든 퀘스천 → 스키마 AI 초안 → 질문 실행 검증 (+#6 BSC 대화형 생성·검증 4항)** — 회의 첫머리(L1-14)가 스키마 정리였고 랩업 계약의 "온톨로지 스키마" 막에 바로 들어간다. 지금 HYD는 완성된 schema.json을 받기만 하므로 "만드는 과정"이 비어 있다.
5. **#8 레거시 메타데이터 증강 (+#9 리니지)** — 현장 DB(코드명·FK 없음)를 다루는 유일한 실습이며 "자동화는 추출까지, 승인은 사람" 원칙을 보여 준다. ontologic spec 008·robo-data-catalog 코드가 시나리오 그대로다. 리니지는 CLAUDE.md §4의 데이터 리니지 목적과 맞닿아 같은 회차에 붙이기 좋다.

차순위: #10 문서 변수→테이블 역바인딩(중간 크기로 #5·#8을 잇는다), #13 품질 게이트, #11 인과 가설(TODO가 범위 밖으로 정해 둬 사용자 결정 필요).

## 부록 D — 회의 원문(meeting-2 1~461행) 전수 대조 (M1~M5 = 표 B #1·#6·#7·#9·#11)

- 근거: `docs/handoff/sources/meeting-2.txt` 1~461행만. 462행부터는 다른 업무(양성원 보고)라 뺐다. meeting-1은 쓰지 않았다.
- 대표발언 정리본(`docs/회의자료/…정리본.md`)은 이 클라우드 체크아웃에 없다. value-gaps.md에 옮겨 적힌 문구를 쓸 때만 "대표발언(2차 인용)"으로 표시했다.
- 화자: 1~30행은 화자 표기가 없다(문맥상 스키마 발표자 = 박용주로 추정, HANDOFF §1-1). 31행부터는 장진영(대표)과 용주 박(이사)이다.
- 판정은 코드와 데이터를 직접 보고 내렸다. 문서 주장만으로 "있음" 판정을 하지 않았다. 컨테이너는 띄우지 않았다. 실행 근거는 기존 sessions·HANDOFF의 "검증됨" 기록을 인용했다.
- 판정 표기: 충족 / 일부 / 없음 / 의도(=의도적으로 안 함)

### 표 A — 회의 요구 전수

| 줄 | 화자 | 회의가 말한 것(요약) | HYD 근거(파일:줄) | 판정 | 비고 |
|---|---|---|---|---|---|
| 4~9 | 발표자(박용주 추정) | 6계층 온톨로지(BSC 최상위·프로세스·리소스·진단·조치(스킬·DMN)·사고 기록), 36클래스·66관계 | `it/neo4j/v2/schema.json` layers 7개·classes 46개(Perspective/Objective/Measure … Incident/DecisionCase) | 충족 | 지금은 46클래스(운영 기록층 추가). R01 |
| 7~8 | 발표자 | 사고 인스턴스와 좋지 않은 일까지 남겨 **향후 피드백**에 넣는다 | `it/process/procsvc/case_projection.py:38` DecisionCase MERGE, `common/hydcommon/ranking-default.json:9` `precedent = 1.5*precedent_share`, `cards.py:133` | **일부** | 기록하고 "과거 같은 선택 비율"을 점수에 쓰는 데까지만 된다. 기록에서 규칙·SOP 개선안을 만들고 승인받는 순환은 없다 → 표 B #2 |
| 10~12 | 발표자 | 맵 메뉴에서 클래스·노드 관계를 그래프로 보여 줌 | `it/portal/www/index.html:27` "지식 지도" 탭, sessions/05·06 | 충족 | |
| 14~16 | 발표자 | OMG BPMN/DMN 전체가 아니라 교육 시나리오에 맞춘 약식·최소 클래스 | schema.json process/skill 계층(Process·FlowNode·Event·Task·Gateway / Decision·DecisionTable·Rule) | 충족 | |
| 19~22 | 발표자 | 프로세스가 설비를 지원하는 관계, 이벤트·태스크 종류(룰·서비스·휴먼) | `instances.cypher:486`(task:compliance businessRule), `it/process/definitions/anomaly_response_v22.json` activities(userTask·serviceTask) | 충족 | |
| 23~26 | 발표자 | 룰태스크 → 디시전 → 디시전테이블 → 룰, 진단부터 조치 완료까지 | `instances.cypher:409~455`(dec:compliance·dt:compliance·rule:*), `cards.py:68` hit policy | 충족 | |
| 27 | 발표자 | 클래스 기반으로 테스트하며 돌려 보는 중 | `scripts/ontology_v2.py gen/load/validate/queries`(HANDOFF §4) | 충족 | |
| 29~30 | 발표자 | 시나리오를 잡아 실라버스·교재 작업 | `docs/curriculum-75h.md`, `docs/sessions/01~25`, `docs/실라버스_추천안_통합44h_실전32h.md` | **일부** | 교재 1차 초안은 착수 전이다(`TODO.md:44~47`). 교재 본문은 레포 밖에 있다(`sessions/25:10`) |
| 34~35 | 장진영 | 설비 진단(쿨러 성능 저하 등)에 실제 값이 들어가야 | 쿨러·펌프·팬 시나리오, `it/dmn-mcp/dmn_mcp/tools.py:57~77` diagnose(신선도→원인→증거 SQL) | 충족 | |
| 43~55 | 장진영 | when-then 조건 변수 a·b·c의 값을 시계열 DB나 적재 DB에서 가져와야 | `instances.cypher:521` 작업별 InputData, `dmn_mcp/server.py:53` gather_facts, `agentsvc/decide.py`(InputData -SOURCED_FROM-> 출처별 조회) | 충족 | R05 |
| 63~67 | 장진영 | 그래프에는 "값이 어느 DB에 있다"는 링크만 두고, 값은 가져와 동적으로 진단. 데이터 패브릭까지 안 가더라도 | sessions/09 3단계(InputData는 표·열 이름만), `procsvc/scm_sync.py:1~10` | **일부** | 원칙은 지킨다. 다만 펌프 씰·팬 베어링 견적(가격·고장률·납기)이 업무 DB에 없고 그래프 시드에만 있다(`instances.cypher:176~179`, `it/supabase/seed.sql:43~48`에는 쿨러 코어 1종뿐). scm_sync도 "그래프에만 있는 견적은 그대로 두고 보고만" 한다 → 표 B #6 |
| 71~79 | 용주 박 / 장진영 | 기준정보는 Neo4j에, 실황(시간에 따라 바뀌는 값)은 따로 | ExternalVariable은 출처만 있고 값은 없음(`instances.cypher:552~554`), 센서 값은 TimescaleDB | 충족 | 63~67행 비고의 예외 1건 |
| 84 | 용주 박 | 메시지를 구독해 본문의 이상을 보고 조치 | `agentsvc/main.py` Kafka alerts 구독, process `/api/source-events`(`procsvc/main.py:517~532`) | 충족 | |
| 88~96 | 장진영 | 에이전트에 지식을 주려면 Neo4j가 제공하는 MCP를 연결. Claude Code/Desktop에 설정하고 "이상 시 조치방법은?"을 물어 탐색 과정을 직접 목격 | `seed.sql:59~60` `mcp-neo4j-cypher@0.4.1`(공식, READ_ONLY), sessions/07 1~5단계 검증됨(`.evidence/a148/58/`) | 충족 | Desktop 대신 Claude Code·Codex로 했다 |
| 105~112 | 장진영 | MCP 동작 방식을 학생에게 설명: 툴이 스키마를 먼저 주고, 에이전트가 Cypher를 만들어 부서·프로세스·이상 패턴·스킬 연결을 찾는다 | sessions/07(get_neo4j_schema → read_neo4j_cypher), schema.json OrgUnit·AnomalyPattern·Skill | 충족 | R03 |
| 120~122 | 장진영 | ① 지식 받기 ② 질의에 맞는 온톨로지 탐색 ③ 파악 | 위와 같음 | 충족 | |
| 123~135 | 장진영 | MCP를 하나 더(Supabase 또는 시계열 DB, 예: Influx). 에이전트가 스키마를 보고 "쿨러 팬 진동" 쿼리를 동적으로 만들어 조건을 판정하고 조치까지 진행 | `dmn_mcp/server.py:58~88` timeseries_schema·timeseries_query·prometheus_*, `enterprise_mcp/server.py:75~93` describe_schema·describe_catalog·query, sessions/12 | **일부** | 질문 정의 3종(sessions/12)에서는 에이전트가 SQL·PromQL을 직접 만든다. 경보 처리 본 경로의 진단은 그래프에 미리 적힌 `Evidence.sql`(`instances.cypher:254`)을 결정론 도구가 실행한다(`tools.py:63~66`). HANDOFF §2 3행의 의도된 설계라 §3에 적었다 |
| 136~138 | 장진영 | **온톨로지가 잘 짜였는지 확인하는 방법**: Neo4j MCP와 기간계 MCP 두 개를 붙이고 상황을 던져, 진단·판단이 정확한지와 액션까지 하는지 모니터링 | 질문 정의의 기대값 대조 `scripts/probe_{timeseries,business,rule}_questions.py`(강사용), 매뉴얼 골든 질문(`procsvc/manual_api.py:151~157`) | **일부** | 사건 단위로 "AI 진단·카드가 정답과 맞았나"를 채점하는 장치가 없다. 온톨로지를 고치기 전후의 정확도 비교도 없다 → 표 B #1. 액션은 HANDOFF §3에 따라 승인을 거쳐서만 나간다(의도) |
| 142~156 | 용주 박 / 장진영 | 우리 에이전트가 아니어도 된다. 강의 중에는 Claude Code/Desktop 같은 딥에이전트를 쓴다 | 워커 cliagents → Claude Code(`it/agent-worker/worker/runner.py`), Codex 어댑터(`codex_provider.py`) | 충족 | R07 |
| 164 | 장진영 | 지금은 우리 제품을 안 쓴다(강의를 망치면 안 되니까) | HYD 자체 구현, 제품의 데이터 모양만 따름(HANDOFF §2 1행) | 충족 | |
| 172 | 장진영 | **과정 후반에는 우리 플랫폼을 써서 학생에게 락인** | sessions/24(대응표·그림. 16행에 "제품 UI 실행 — 설명으로 대체"), DECISIONS 101·108(제품 completion 엔진의 HYD 2.2 실제 구동은 미검증 경계) | **일부** | 대응표 설명만 있다. 학생이 실제 ProcessGPT로 같은 시나리오를 돌리는 회차는 없다 → 표 B #9 |
| 173~174 | 장진영 | 일반 딥에이전트면 다 된다. Claude Code로 시험해 봤다 | 실제 Claude Code 워커로 쿨러 완주(HANDOFF §9 A140~ 42/42) | 충족 | |
| 175~178 | 장진영 | 플랫폼에 통합하려면 서버가 Claude Code를 서브프로세스(stdin/stdout)로 부르고 결과를 화면에 뿌린다 | `worker/runner.py`, cliagents `--print --output-format stream-json`, 포털 `liveStream.js`(tool_usage 6곳)·`instances.js`(3곳) | 충족 | R08 |
| 187~188, 222 | 장진영 | 그 정도 내용이면 75시간을 채울 수 있나 | `docs/curriculum-75h.md` 25회×3h, sessions 25개 | 충족 | 실라버스 추천안은 44h/32h로 다시 짜는 중(사용자 결정 대기) |
| 189~191 | 장진영 | 이상 징후 값이 Prometheus 등에 있으면 그걸 조회하는 MCP를 에이전트에 붙인다 | `dmn_mcp/server.py:70~88` prometheus_metadata/series/query, DECISIONS 58 | 충족 | |
| 192~193 | 장진영 | 원래 그림: Prometheus나 SCADA 쪽 이벤트가 오면 에이전트가 트리거된다 | Python detector → Kafka alerts → 인스턴스 시작. Prometheus 경보는 플랫폼용 2개뿐(`it/prometheus/rules.yml`), Alertmanager 없음 | 의도 | DECISIONS 106·107(대역 유지, 제품 교체 보류) |
| 198 | 용주 박 | SCADA는 독립 | `ot/fuxa`, cmd-gateway 분리 | 충족 | |
| 202~214 | 장진영 | 동적 트리거는 회사 cli 에이전트 라이브러리(서브프로세스)로. 웹 서버가 결과를 받아 **에이전트가 떠 있는 것을 보여 준다** | cliagents 채택(HANDOFF §2 2행), `/api/agents/status`(`procsvc/instance_mode.py:689~692`) | **일부** | 워커 상태 API는 있지만 포털에서 부르는 곳이 0건이다(`it/portal/www`에서 `agents/status` 검색 결과 없음). 처리 건 화면은 작업 진행만 보여 준다 → 표 B #7 |
| 230~232 | 장진영 | 분량은 온톨로지·에이전트 쪽을 크게, SCADA 쪽은 적게 | OT 회차는 sessions 01~04뿐(4/25) | 충족 | |
| 236~238 | 용주 박 | 시나리오 기반으로 가되 기술은 딥다이브·설명문으로 채운다 | sessions 각 회차의 "설명/실습/정리" | 충족 | |
| 242~245 | 장진영 | 이 구조에는 문서 기반 RAG 비중이 작다(문서를 소화해 온톨로지를 만들었다면 모를까) | 문서→SOP 인제스천은 있고 벡터 RAG는 없음 | 의도 | teachable 표1-6에서도 제외됨 |
| 253~254, 262, 270~271 | 장진영 | 온톨로지는 인제스천이 만든다(회사 DB 스키마·SOP 문서 → 인스턴스, 스키마는 경험자가 정함). **인제스천 과정을 알려줘야** | sessions/09, `procsvc/ingest.py`·`manual_extraction.py`, `procsvc/main.py:1020~1097` DDL preview/sync/commit | 충족 | R02. 실제 매뉴얼 규모 실측 A092~A094 |
| 279~285 | 장진영 / 용주 박 | "존재하나요?" → "그냥 만들었다. 인제스천한 걸 빼서 비우고 다시. UI는 만들어 봐라. 테스트는 안 해봤다" | 되돌리기 `procsvc/main.py:1103` DELETE ingests, `manual_api.py:161` rollback, 포털 DDL·매뉴얼 절(sessions/09 5단계) | 충족 | |
| 289~293 | 장진영 | 이 과정도 Claude Code로. DB(DDL)에서 출발해야 런타임 T2SQL이 돈다 | 매뉴얼 추출 = 워커 작업(sessions/09 7단계), DDL 적재 → InputData, `procsvc/ddl_sync.py` | 충족 | DDL 적재 자체는 결정론 파서다(차이 있음, 유지) |
| 301~302 | 장진영 | DMN 규칙 조건에 맞는 쿼리를 만들어야 에이전트가 상황을 판별하고 조치한다 | `procsvc/main.py:1121` `/api/kg/rules/sql`, `docs/examples/rule-question-v1.json`, probe_rule_questions | 충족 | R06 |
| 310~318 | 장진영 / 용주 박 | 원천이 문서만인가, DDL도 들어가나? 지금 설계에는 시계열 DB만 있다 | 업무 RDB(Supabase `ent`) 추가, `it/supabase/migrations/20261003000002_enterprise.sql` | 충족 | |
| 322~336 | 장진영 / 용주 박 | 일반 DB는 T2SQL, 시계열 DB는 그 DB의 질의(메트릭 쿼리) | enterprise `query`, timeseries_query(SQL), prometheus_query(PromQL) | 충족 | Text2SQL 전용 엔진은 넣지 않는다(사용자 확정) |
| 340~349 | 장진영 | Prometheus 메타정보(지표·관계)를 LLM에 주어 "팬 진동이 얼마 이상 몇 초 지속"을 묻는 PromQL을 만든다 | prometheus_metadata, HANDOFF A087 PromQL 시점 6/6 | 일부(차이 유지) | VS1(팬 진동)은 Prometheus 지표에 없다(Gauge 정의에 VS1 없음, DECISIONS 58 "없는 VS1 지표를 만들지 않는다"). 같은 질문은 TimescaleDB SQL로 한다(sessions/12 1단계). 회의도 "프로메테우스로 올릴 것 같으면"이라는 조건부 발언이라 차이로 기록하고 유지 |
| 350~353 | 장진영 | 고객·재무가 섞인 복합 상황을 판단하려면 일반 RDB가 있어야 한다. 재무현황은 RDB에 있다 | ent: customer_tier·penalty_per_h·failure_cost·claim_cost(`20261003000002_enterprise.sql:40~49`) | **일부** | 고객 등급과 계약 손실 단가는 있다. 재무현황(예산·손익 실적)과 제품 원가 표는 없다 → 표 B #5·#6 |
| 361~367 | 장진영 | 현장은 시계열도 RDB에 둔다. TSDB/Prometheus는 상황 인지·트리거 경로에만, Kafka로 연결 | TimescaleDB(=PostgreSQL), Redpanda(Kafka) | 충족 | |
| 375~377 | 장진영 | 제조기업 일반 데이터: 주문량, 원가, **부품별 원가**, **에너지 효율**, 규제 관련 표 | production_orders(remaining_qty·hour_value, `…enterprise.sql:22`), parts·suppliers(`:88~104`, 시드는 쿨러 코어 1종), energy_demand(`:106`, 계약·수요 kW), 규제 = KnowledgeSource SR-04·PR-07 + dt:compliance(`instances.cypher:183~184,439~455`) | **일부** | 부품 원가는 3종 중 1종만 업무 DB에 있다. 에너지는 피크 수요만 있고 효율(원단위 kWh/개)은 없다. 제품 원가 표도 없다 → 표 B #6 |
| 385~388 | 장진영 | 에이전트가 매뉴얼을 읽고 판단 관점을 정한다. 상충 예: 납기 신뢰가 더 중요하면 장비가 고장 나든 말든 일단 돌린다 | ranking `delivery` 항(due·penalty·production keep/reduce/stop, `ranking-default.json:10`), skill:fan-max "생산 유지"(`instances.cypher:274`), rule:fan-24h 감점(`:451`), sessions/23 | 충족 | 비교는 단위 없는 점수다. 돈(원) 비교는 TODO 금전 손익 |
| 396~404 | 장진영 | 설비 상태뿐 아니라 납기일도 봐야 한다. Supabase MCP가 붙고, 스킬에는 "데이터는 Supabase에 있다"는 사실만. 트리거 → Neo4j MCP로 매뉴얼 → Supabase 납기 → 설비 상태 → 판단 | task:rank 지시문 "업무 DB(Supabase MCP)에서 납기·계약·재고"(v22 정의), InputData SOURCED_FROM System, `seed.sql:61` enterprise MCP | 충족 | R04 |
| 405~406 | 장진영 | 전체 프로세스를 돌려 **특정 사용자에게 알림** | 사람 작업은 역할로 배정하고 승인할 때 역할을 검사(403). notifications는 에이전트가 질문할 때만 쓴다(`agent-worker/worker/runner.py:320`) | **일부** | 포털 "내 차례"는 사용자를 구분하지 않고 사람 IN_PROGRESS 작업을 모두 보여 준다(`it/portal/www/instances.js:77~100`). notifications 표를 읽는 화면이 없다 → 표 B #8 |
| 410~413 | 용주 박 | 계획 정지 vs 납기를 위해 팬을 과도하게 올려 밤새 운전. 두 대안 중 사람이 하나를 고르면 그대로 실행 | 쿨러: fan-max(유지)·fan-max-derate·derate-night-clean·wo-cooler-clean(정지·세척), 팬: planned-stop(`instances.cypher:274~298`), task:select | 충족 | R09 |
| 417~420 | 장진영 | 알림을 받을 도구가 필요하다(UI에 넣든 Mattermost 같은 오픈소스 내부 알림이든). HITL 포털을 만들어야 | 포털 HITL(`hitl.js`, 처리 건 "내 차례") | 충족(포털) / 외부 채널은 의도 | 외부 채널은 HANDOFF §6 "알림 채널 → 포털 할일 목록으로 닫힘". 코드에서 mattermost·slack·webhook 0건 |
| 422~423 | 장진영 | Supabase로 만들면 금방. 시나리오 전체를 돌리려면 거기까지 가야 한다 | 쿨러 42/42·펌프 40/40·팬 34/34 완주(`TODO.md:64`) | 충족 | |
| 424~426 | 장진영 | SCADA까지 연결하면 액션 단계까지 갈 수 있지만, 알림까지만 주고 사용자가 버튼을 누른다 | 승인 → action.cmd → cmd-gateway → PLC ACK(`procsvc/machine.py`) | 충족 | |
| 430 | 용주 박 | 직접 제어는 현장에서 | HANDOFF §3 2행, rule:auto-mode(REMOTE_AUTO에서만, `instances.cypher:443`), cmd-gateway 검증 5종 | 충족 | |
| 434~435 | 장진영 | 에이전트가 자동으로 돌면 **어떤 에이전트가 지금 동작 중인지** 보는 모니터링 화면, 프로세스 인스턴스 모니터링 화면 | 처리 건 탭(`instances.js`), SSE `/api/events/stream`(`instance_mode.py:599`), `/api/agents/status`(포털 미사용) | **일부** | 인스턴스 모니터링은 충족. 에이전트(워커) 현황 패널은 없다 → 표 B #7 |
| 436 | 장진영 | 구현하다 보면 ProcessGPT가 된다 | 정의 JSON·todolist/events 열 이름·cliagents(HANDOFF §2) | 충족 | |
| 437~438 | 장진영 | 학생이 데이터를 알아야 한다. **맨땅에서 여러 오픈소스로 구성요소를 이해하는 시간**(미니멀) | `docs/enterprise-catalog.md`, sessions. 랩업(바이브 코딩)은 GOAL 작업 A DoD 4로 진행 중 | **일부** | 랩업 출발본·정답 검증은 아직 끝나지 않았다(`GOAL.md:10`) |
| 438~447 | 장진영 / 용주 박 | 그것만으로는 부족하다. 현장 DB는 Oracle·SAP ERP 등 여러 종 → 데이터 패브릭이 필요하다는 시나리오로 자연스럽게 확장 | sessions/24 4단계(그림), 업무 DB 1종 | 의도 | HANDOFF §2 마지막 행 "구현하지 않고 후반 설명만". value-gaps #6·teachable 1은 이 결정과 충돌한다(재개 시 사용자 확인) |
| 448 | 장진영 | **프로세스를 자유롭게 바꾸고 룰을 관리**하려면 ProcessGPT 같은 게 필요하다. 기본 모델을 만들고 다음 확장으로 | 정의 등록·버전(`instance_mode.py:572~598`), 랭킹 정책 PUT(`procsvc/main.py:1185`), BSC 조건 PUT(`:1170`) | **일부** | 룰은 API로 바꿀 수 있다. 프로세스는 새로 등록해도 경보 경로가 환경변수로 고정된 파일 하나만 쓴다(`instance_mode.py:39,128`). 말로 정의를 만드는 기능도 없다 → 표 B #3 |
| 456~457 | 장진영 | 학생 교육이면서 나중에 기업 컨설팅 내용이기도 하니 다용도로 쓸 생각으로 만들 것 | 마스터 가이드·기능 보고서(`docs/보고서/`), 시스템 설명 문서 | 일부(미확인) | 다른 회사·설비로 옮겨 쓰는 틀(새 설비 추가 절차, 온톨로지 템플릿 재사용 안내)은 찾지 못했다. 강의 가치 하 → 표 B #11 |

표 A 집계: 55행 = 충족 36 · 충족(포털)/외부 채널 의도 1 · 일부 13 · 일부(차이 유지) 1 · 일부(미확인) 1 · 의도 3. "없음"은 0행이다. 회의가 이름을 대 말한 블록은 모두 어떤 형태로든 있다. 구멍은 "있지만 회의가 말한 끝까지 가지 않은 것"에 몰려 있다.

### 표 B — 구멍만, 가치 순

정렬: 강의 가치 상 → 중 → 하. 같은 등급 안에서는 회의 발언이 직접적이고 아직 아무 목록에도 없는 것을 앞에 두었다. 크기는 코드를 읽고 어림한 값이다(작음 = 기존 기능에 데이터·화면 한 조각, 중간 = 새 계산·화면 한 덩어리, 큼 = 새 층·새 엔진).

| # | 구멍(수강생이 ~해서 ~를 알아보기) | 회의 근거 줄 | HYD 현재 | 강의 가치 | 구현 크기 | 참고할 원본 레포 | 기존 목록 대응 |
|---|---|---|---|---|---|---|---|
| 1 | **수강생이 같은 경보를 여러 번 AI에 던져 진단·조치 카드를 정답표와 대조해 채점해서, 온톨로지를 고치기 전후에 AI 판단이 실제로 나아졌는지 숫자로 알아보기** | 136~138("온톨로지가 잘 구성됐는지 체크하는 방법은 … 진단 판단을 정확히 하고 액션까지 수행하는지 모니터링") | 질문 정의 3종의 기대값 대조 스크립트(`scripts/probe_*_questions.py`, 강사용)와 매뉴얼 골든 질문(`manual_api.py:151~157`)뿐이다. 사건 진단·카드를 정답 기준으로 채점하는 장치와 "관계 하나를 빼면 진단이 틀어지는가" 비교가 없다 | 상 | 중간 | process-gpt-mcp-validator(본문 미확인), neo4j-text2sql 품질 게이트(value-gaps 인용, 소유 조직 미확인) | value-gaps #1(대표발언(2차 인용) §11), TODO 추가 빈자리 1 |
| 2 | **수강생이 처리 끝난 사고·판단 기록을 모아 규칙·SOP 개선안을 만들고 사람이 승인하게 해서, 다음 같은 경보의 판단이 실제로 바뀌는지 알아보기** | 7~8("좋지 않은 일도 남겨서 향후 … 피드백"), 448("룰을 관리하기 위해") | DecisionCase 기록(`case_projection.py:38`)과 선례 비율 점수(`ranking-default.json:9`)까지만 있다. 기록 → 개선 제안 → 승인 → 규칙 반영 단계가 없다 | 상 | 큼 | process-gpt-agent-feedback(`core/feedback_proposal_routes.py`, REFERENCE_ADOPTION P04) | value-gaps #4, teachable 3, TODO 추가 빈자리 4 |
| 3 | **수강생이 업무 흐름(정의)을 고치거나 말로 만들어 등록해서, 다음 경보부터 새 흐름으로 처리 건이 열리는지 알아보기** | 448("이런 프로세스들을 자유롭게 바꾸고 … 프로세스GPT 같은 게 필요") | 정의 등록·버전 API는 있다(`instance_mode.py:572~598`). 경보 경로는 환경변수로 고정된 파일 하나만 쓴다(`instance_mode.py:39,128` `PROCESS_DEFINITION_FILE` 기본 v22). 등록 정의는 수동 시작에만 쓰인다. 말 → 정의 생성은 없다 | 상 | 중간(경보가 등록 최신 버전을 쓰게 하는 것은 작음, 말 → 정의 생성은 중간) | bpmn-process-generation-skill(D01), process-gpt-bpmn-extractor, process-gpt-completion(`process_definition.py`) | value-gaps #8, teachable 4, TODO 추가 빈자리 8 |
| 4 | **수강생이 맨 폴더에서 Claude Code로 온톨로지 적재·MCP·규칙·에이전트 툴을 직접 만들어 붙여서, 시스템 부품이 어떻게 만들어지는지 콘솔 로그로 알아보기** | 437~438("미니멀 학생들이 맨땅에서 구성요소들을 여러 오픈 소스들을 가지고 이해하는 시간") | 시스템을 돌려 보는 회차는 25개 다 있다. 랩업 출발본·정답 검증은 진행 중이다(`GOAL.md:10` DoD 4). 실라버스 추천안은 [직접 만들기] 확정이 4단원 하나다 | 상 | 중간 | cliagents, process-gpt-sample-app-wms(MCP 서버 모양), process-gpt-claude-skills(본문 미확인) | GOAL 작업 A DoD 4(진행 중) |
| 5 | **수강생이 "납기 때문에 계속 돌리기 vs 세우고 고치기"를 계약 위약금·고장 비용·생산 가치로 원 단위 손익으로 비교해서, 어느 입력이 바뀌면 권고가 뒤집히는지 알아보기** | 350~353(재무 등 복합 상황 → RDB), 385~388(납기 신뢰 vs 장비 고장), 410~413(계획 정지 vs 팬 과부하 밤샘 운전) | 대안·사람 선택·납기 항은 있다(`ranking-default.json:10`, sessions/23). 비교는 단위 없는 점수 합산이고 원 단위 손익·뒤집힘 경계는 없다 | 상 | 중간 | process-gpt-strategy(달성률·기여도) | TODO "다음 할 일" 금전 손익(①) — 중복, 대응 번호만 |
| 6 | **수강생이 부품 3종 견적·제품 원가·에너지 원단위를 업무 DB에서 읽어서, "값은 원천에, 그래프에는 어디 있는지만"이라는 원칙이 예외 없이 지켜지는지 알아보기** | 63~67, 75~79(값은 DB에, 그래프엔 링크), 375~377(주문량·원가·부품별 원가·에너지 효율·규제) | 업무 DB `ent.parts`·`suppliers`는 쿨러 코어 1종뿐이다(`seed.sql:43~48`). 펌프 씰·팬 베어링 견적은 그래프 시드에만 있다(`instances.cypher:176~179`). scm_sync는 이것을 "그래프에만 있음"으로 보고만 한다(`scm_sync.py:9~10`). 제품 원가 표·에너지 효율(kWh/개) 열이 없다(`…enterprise.sql:88~113`) | 중 | 작음 | process-gpt-strategy `ontology_sync.py`(이미 따름), process-gpt-sample-app-wms(스키마·RPC) | 신규(금전 손익 TODO의 입력 데이터와 겹침) |
| 7 | **수강생이 포털에서 지금 어떤 에이전트(워커)가 무슨 작업을 잡고 있는지 보면서, 이벤트 하나에 에이전트가 떠서 일하고 내려가는 모습을 알아보기** | 202~214("에이전트가 뭔가 떠 있는 걸 보여줄"), 434~435("어떤 에이전트들이 지금 동작하고 있다 … 모니터링 하는 화면") | API `/api/agents/status`는 있다(`instance_mode.py:689~692`, 워커 /health·/agents). 포털에서 쓰는 곳이 0건이다. 워커 URL도 하나만 본다(`instance_mode.py:465~479`) | 중 | 작음 | process-gpt-vue3, process-gpt-analytic(P01) | 신규(teachable 8 "에이전트 옵스"의 일부) |
| 8 | **수강생이 승인 역할의 담당자로 들어가 자기에게 온 알림과 할 일만 보면서, 에이전트가 특정 사람을 불러 세우는 흐름을 알아보기** | 405~406("어떤 특정 유저에게 alert"), 417~420(노티 받을 툴, HITL 포털) | 포털 "내 차례"는 사용자를 구분하지 않는다(`instances.js:77~100`). notifications 표는 에이전트 질문 때만 쓰고(`runner.py:320`) 읽는 화면이 없다. 외부 채널(Mattermost 등)은 안 하기로 했다(HANDOFF §6) | 중 | 작음~중간 | process-gpt-vue3(알림·할 일함), process-gpt-mobile(X01, 푸시) | teachable 9 |
| 9 | **수강생이 과정 후반에 같은 쿨러 시나리오를 실제 ProcessGPT 제품에서 돌려서, 직접 만든 부품이 제품의 어느 부품과 같은지 알아보기** | 172("가계후반에는 우리걸 써가지고 … 우리 플랫폼에 대한거를 좀 락인") | sessions/24는 대응표·그림만 있다(16행 "제품 UI 실행 — 설명으로 대체"). 제품 엔진이 HYD 2.2 정의를 실제로 돌리는지는 미검증 경계다(DECISIONS 101·108) | 중 | 큼 | process-gpt-completion, process-gpt-vue3, process-gpt-infra-docker | 신규(AUDIT R13 일부) |
| 10 | **수강생이 실라버스 흐름대로 교재를 혼자 읽고 따라가면서, 각 장면에서 무엇을 확인해야 하는지 알아보기** | 29~30("시나리오 잡아서 … 신라부스랑 교재 작업") | 회차 문서 25개는 있다. 교재 1차 초안은 착수 전이다(`TODO.md:44~47`). 자가 평가 문항은 레포 밖에 있다(`sessions/25:10`) | 중 | 중간 | — | TODO 교재 1차 초안 |
| 11 | **수강생(또는 컨설턴트)이 HYD 틀을 새 설비 하나에 옮겨 적용해 보면서, 기업 현장에 그대로 쓰려면 무엇을 바꿔야 하는지 알아보기** | 456~457("나중에 기업한테 컨설팅 하는 내용이기도 … 다용도의 활용도") | 새 설비·새 고장을 넣는 절차서나 템플릿 재사용 안내를 찾지 못했다(미확인). 실라버스 교재 HANDOFF:51에 "새 고장 하나를 Claude Code로 넣어 끝까지" 랩업 후보가 있다 | 하 | 중간 | ontology-studio(인제스천·스키마 재사용) | 신규(랩업 후보와 겹침) |

표 B에서 뺀 것(구멍 아님, 근거 확인): Text2SQL 전용 엔진(사용자 확정), What-if 시뮬레이션(TODO 기존. 회의 meeting-2 1~461행에는 직접 발언이 없고 근거는 대표발언(2차 인용) §1·§4), KPI 실적·역추적(value-gaps #3, 근거가 대표발언(2차 인용) §1뿐이라 meeting-2로는 확인 못 함), 로트 처분(value-gaps #5, 대표발언(2차 인용) §9 근거. 참고로 `ent.lot_dispositions`(HOLD/RELEASE) 표(`…enterprise.sql:128~131`)와 기업 목업의 `skill:hold-lot` 실행(`entsim/state.py:17`)은 있다. 다만 v2 온톨로지 스킬에는 없고 v1 시드(`it/neo4j/v1/seed_enterprise.cypher`)에만 있다).

### 3. "의도적으로 안 함"으로 판정한 것과 근거

| 회의 줄 | 회의가 말한 것 | HYD에서 안 하는 것 | 근거 |
|---|---|---|---|
| 63~67, 438~447 | 다종 DB(Oracle·SAP ERP) → 데이터 패브릭으로 확장 | 패브릭 구현, 두 번째 종류 DB 연결 | HANDOFF §2 마지막 행 "데이터 패브릭은 구현하지 않고 후반 설명만"(회의 63~67 "패브릭까지 안 가더라도", 447 "확장 시나리오"). sessions/24 16행. value-gaps #6·teachable 1이 이 결정과 충돌하므로 재개하려면 사용자 확인이 필요하다(TODO 추가 빈자리 6, DECISIONS 107) |
| 192~193 | Prometheus·SCADA 이벤트가 에이전트를 트리거 | Prometheus 경보 → Alertmanager → 트리거. 지금은 Python detector → Kafka 경로다 | DECISIONS 106(현 구조 유지, 대역임을 문서에 적음), 107(OpenPLC·Flink·Alertmanager 교체 방향은 정했으나 보류) |
| 417~420 | Mattermost 같은 내부 알림 툴 | 외부 알림 채널 | HANDOFF §6 "알림 채널 → 포털 할일 목록으로 닫힘"(이력은 DECISIONS). 단 "특정 사용자에게"(406)의 포털 안 사용자 구분은 별개 구멍이다(표 B #8) |
| 242~245 | 문서 기반 RAG 비중이 작다 | 벡터 RAG·하이브리드 라우팅 | 회의 스스로 비중이 작다고 말함. teachable 표1-6에서 제외, value-gaps "가치 단위로 보지 않아 뺀 것" |
| 123~135, 301~302 (경보 본 경로 한정) | 에이전트가 규칙 조건을 보고 질의를 동적으로 만든다 | 경보 처리 진단은 그래프의 `Evidence.sql`을 결정론 도구가 실행한다(`dmn_mcp/tools.py:57~77`, `instances.cypher:254`) | HANDOFF §2 3행 "반복 판단은 DMN·규칙으로 결정론화, LLM은 수집·설명". 동적 생성은 질문 정의 3종(sessions/12)·`/api/kg/rules/sql`로 보여 준다. 수강생이 "본 경로에서는 왜 미리 적힌 질의를 쓰나"를 묻게 되므로 교재에 이유 한 줄이 필요하다 |
| 136~138("액션까지 수행") | 범용 에이전트가 진단 뒤 액션까지 직접 수행 | 에이전트·워커·MCP의 직접 제어 | HANDOFF §3 1·2행(사람 승인 전 실행 금지, PLC 명령은 process Incident 경로로만), 회의 424~430("노트까지만 주고 유저가 버튼", "직접 제어는 현장") |
| 340~349 | Prometheus에 올린다면 PromQL로 "팬 진동 몇 초 지속" | VS1 Prometheus 지표 생성 | DECISIONS 58 "없는 VS1 지표를 만들지 않는다". 같은 질문은 TimescaleDB SQL로 한다. 회의 발언이 조건부라 "차이 있음, 유지" |
| 289~293 | 인제스천도 Claude Code로 | DDL 적재를 LLM 대신 결정론 파서로 | 매뉴얼(SOP) 추출은 워커(Claude Code) 작업이다. DDL은 구조가 정해진 입력이라 파서로 한다. 실제 결함도 회의 미충족도 아니므로 "차이 있음, 유지" |

### 4. 놓치면 안 될 상위 5개와 이유

1. **표 B #1 — AI 진단·카드를 정답표로 채점해 온톨로지 품질을 판정하기(136~138).** 회의가 "온톨로지가 잘 됐는지 체크하는 방법"이라고 이름 붙여 말한 유일한 검증 절차다. 지금은 강사용 기대값 스크립트와 매뉴얼 골든 질문뿐이다. 수강생이 자기가 고친 온톨로지가 판단을 낫게 했는지 확인할 길이 없다. 기존 probe·골든 틀을 사건 판단으로 넓히면 되어 크기는 중간이다.
2. **표 B #3 — 프로세스를 바꾸면 다음 경보부터 그 흐름이 쓰이기(448).** 회의가 "프로세스를 자유롭게 바꾸고 룰을 관리"하는 것을 ProcessGPT가 필요한 이유로 들었다. 그런데 경보 경로가 환경변수 파일 하나에 묶여 있다(`instance_mode.py:39,128`). 등록 화면은 있는데 경보에는 반영되지 않아, 수강생이 "바꿨는데 왜 그대로지?"를 겪는 결함에 가깝다. 앞 절반(경보가 등록 최신 버전을 쓰기)은 작은 작업이다.
3. **표 B #2 — 사고 기록을 다음 판단 개선으로 되먹이기(7~8, 448).** 회의 첫머리 6계층 설명의 마지막 층이 존재하는 이유가 "향후 피드백"이다. 지금은 선례 비율 점수 하나뿐이라 층의 목적이 화면에서 닫히지 않는다. 원본 레포(process-gpt-agent-feedback)가 있어 따라 만들 근거가 분명하다.
4. **표 B #6 — 부품 견적·원가·에너지 효율을 업무 DB로 옮기기(63~67, 75~79, 375~377).** 회의가 가장 길게 강조한 원칙이 "값은 DB에, 그래프엔 위치만"이다. 펌프 씰·팬 베어링 견적이 그래프 시드에만 있는 것은 그 원칙의 반례다. 수강생이 sessions/09 3단계에서 "그래프엔 값이 없다"를 확인하는데, 부품 견적에서 반례를 만나게 된다. 작음 크기로 고칠 수 있고, TODO 금전 손익의 입력 데이터도 함께 채워진다.
5. **표 B #7·#8 — 지금 동작 중인 에이전트 현황, 담당자별 알림·할 일(202~214, 405~406, 434~435).** 회의가 화면으로 보여 주자고 한 두 장면이다. API·표(`/api/agents/status`, notifications)는 이미 있는데 포털이 읽지 않는다. 둘 다 작은 작업으로 "이벤트 → 에이전트가 뜬다 → 특정 사람에게 간다"를 눈으로 보이게 한다.

(참고: 랩업(#4)과 금전 손익(#5)은 가치가 상이지만 이미 GOAL 작업 A DoD 4와 TODO에 올라 있어 상위 5에서 뺐다.)
