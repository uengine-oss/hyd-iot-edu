# 24. 여기서 제품으로: ProcessGPT와 데이터 패브릭 (6부, 180분: 설명 90 / 실습 60 / 정리 30)

## 이번에 할 것 / 끝나면 보이는 것
이 수업에서 만든 구성요소가 제품(ProcessGPT)의 어느 부품에 해당하는지 대응표를 완성하고, 회사 DB가 Oracle · SAP · Influx로 갈릴 때 무엇이 더 필요한지(데이터 패브릭) 그림으로 그린다.
끝나면 대응표 1장과 확장 그림 1장이 남는다.

## 준비
- 읽을 것: `docs/handoff/HANDOFF.md` §2 "확정된 방향"(정의 JSON · todolist/events 열 이름 · cliagents 워커 · Execution 레이어가 제품과 같은 모양), `docs/handoff/REFERENCE_ADOPTION.md`(부품별 참고 레포 · 채택 경계), `docs/student-guide.md` §6(학생용 ↔ 실제 제품 교체 지점), `docs/handoff/verification/2026-10-07/r14-summary.md` C절(HYD 쪽이 나아 유지한 것).
- 데이터 패브릭은 **구현하지 않고 설명만**(HANDOFF §2 마지막 행, 회의 L63~67·L447).

## 실행 장면
1. [표] 왼쪽 열에 이번 과정의 부품(정의 JSON · 인스턴스/작업 표 · 워커 · MCP 3개 · 규칙 엔진 · 포털 · 투영) → 오른쪽에 제품 레포 이름(process-gpt-completion · agent-sdk `todolist/events` · process-gpt-cli-agent · sample-app-wms MCP · 결정론 평가기 · process-gpt-vue3 · ontology SCHEMA.md Execution 레이어) → [확인] 각 행에 "같은 모양인 것 / HYD가 더한 것" 한 칸(HANDOFF §2 · r14 C절에서 근거).
2. [화면] 포털 **프로세스 인스턴스** → 아무 완료 실행 → [관찰] 작업 행의 `agent_orch=cliagents`, 상태 이름, 이벤트 유형이 agent-sdk 스키마와 같음 → [확인] "이 표가 그대로 ProcessGPT의 todolist"(화면 안내문)를 대응표 근거로.
3. [화면] 정의 등록 화면의 2.2 정의(`anomaly_response_v22.json`) → [관찰] 에이전트 활동이 `userTask + agentMode + orchestration` 모양(A116) → [확인] 제품 설계기가 만든 정의가 여기서 돌고, 여기 정의가 제품에서 거부되지 않는 이유 한 줄.
4. [그림] 지금은 업무 DB 한 종(Supabase ent)인데 Oracle(ERP) · SAP · InfluxDB(시계열)로 갈리면: 원천별 MCP/커넥터, 메타데이터 카탈로그, 공통 질의층이 어디에 끼는지 → [확인] 9회차의 "DDL → InputData → SOURCED_FROM → System" 구조가 어떻게 확장되는지 표시.
5. [정리] "현재 시스템에 없음 — 설명으로 대체": 데이터 패브릭 실행, 다종 DB 연결, 제품 UI 실행. 여기서는 그림과 말로만.

## 막혔을 때
- 레포 원문이 필요하면 `.evidence/reaudit/references-latest/<레포>`(없으면 `bash scripts/refs_latest.sh`, 네트워크 필요).

## 증거
- 해당 없음(실행 장면이 아니라 설명 · 작성 회차). 대응표의 근거 문서는 위 "준비"의 네 파일.
- `.evidence/sessions/24/`: 해당 없음.
