# 포탈 세부 UI 점검 (2026-10-01)

## 추가 사용자 관점 점검 · 체크포인트 이후

사용자가 정렬·여백은 예시이며 전체 UI/UX를 엄격하게 검증하라고 범위를 넓혔다. 이전 안정성·UI 작업은 `a4a8691`로 먼저 커밋했다. 다른 세션의 마스터 가이드 HTML/PDF와 docs/src는 그대로 남겼다.

| 화면 / 동작 | 추가 발견 및 보완 |
|---|---|
| 첫 화면 | 도식 바깥 여백, 텍스트 실측 기반 노드 좌우 패딩, AI/Agent 줄 간격. 첫 화면에서 바로 설비 상태를 확인하는 버튼. 넓은 화면에서 본문 중심 정렬, 단계 카드 버튼 기준선 통일 |
| 설비 도식 | 세 설비 모두 유온과 CE 텍스트 경계가 겹침 → CE 위치 분리 |
| BPMN | 축소로 작은 글씨, 상자에 가려진 기업 스킬 분기 설명 → 읽기 크기·키보드 가로 이동·전체 보기 전환, 분기 라벨을 선과 상자 밖에 배치. 범례 줄바꿈 단위 유지 |
| 온톨로지 | 글자 수 기준으로 자른 한글 이름 10개가 상자 밖 → 실제 렌더 폭 기준 생략, 전체 이름은 툴팁·상세에 유지. 검색 결과 수·0건 표시와 첫 결과 위치 이동. 노드 선택 후 키보드 포커스 유지, 설비 변경 시 이전 속성 제거 |
| 목록 / 상세 | 긴 판단 목록에 맞춰 상세 영역이 수천 px 늘어나 빈 공간 발생 → 목록 내부 스크롤. 좁은 데스크톱에서는 승인 상세를 목록 아래 전체 폭으로 표시 |
| 폼 / 카드 | 입력창 글꼴·패딩·테두리 일관화. 시나리오 실행 버튼 기준선·줄바꿈, 승인 버튼·긴 이력·시스템 표 줄바꿈 보정 |
| 판단 실행 / 승인 | 결과로 스크롤, 승인·반려 처리 중 표시와 중복 클릭 방지, 빈 반려 사유 안내. 다른 판단 선택 시 이전 승인 양식을 읽는 중 표시로 교체 |
| 갱신 중 조작 | 목록 자동 갱신 시 포커스 BODY로 이탈하는 현상 재현 → 불필요한 재생성 방지, 변경 시 선택·스크롤·포커스 복원. 늦게 도착한 트레이스가 승인 입력을 다시 그릴 때도 입력 포커스와 텍스트 선택 유지 |
| 현재 상태 표현 | 설비 연결 실패 시 홈의 과거 수치를 현재 값으로 남기지 않음. 유온 기준을 전체 정상 판정처럼 표현하지 않음. 시간 배율 설명에 실제 수치 표시 |

### 화면 검사 근거

- [검사 스크립트](../scripts/ui_layout_audit.py): 9개 포탈 화면 × 1920×1080 / 1440×900 / 1262×624 / 1024×768 × 상단·중간·하단 = **108개 화면 상태**. 상세 인시던트·판단 결과·선택 노드·긴 스킬 이름을 포함한다.
- [기하 검사 결과](../.evidence/ux-audit/final/geometry.json): SVG 글자 겹침 0, 노드 밖 라벨 0, 페이지 가로 넘침 0, 보이는 조작 대상 중심점 검사 2,777회에서 가림 0, JS 예외 0. 같은 대상의 다른 상태를 중복 포함하므로 2,777개의 고유 버튼이라는 뜻은 아니다. 의도적으로 겹친/분리한 SVG로 검사기 자체도 확인했다.
- [수정 전 화면](../.evidence/ux-audit/before/) / [수정 후 화면](../.evidence/ux-audit/final/). BPMN은 좌우 끝·전체 보기 화면도 캡처했다. SVG 경계 검사는 실제 화면 검토와 병행했으며 모든 HTML 요소 쌍의 전수 검사라고 주장하지 않는다.
- 최초 조작 회귀의 포커스·반려 안내 실패는 [원본 로그](../.evidence/ux-audit/regression-first-failure.log)에 보존했다. 기하 검사 최초의 다중 행 링크 중앙점·스크롤바 위 후보는 실제 요소 사각형을 사용하도록 검사기를 교정했다. 최초 검사 스크립트의 h2 다중 매칭도 제품 결함과 구분했다.

조작 회귀는 추가 검사를 포함해 **11/11 통과**했다. 실제 스킬 저장·복원, 매뉴얼 적재, 네 전사 시나리오, 역할 거부, 입력·포커스 유지, 연결 실패/복구, 검색과 BPMN 전체 보기, Grafana 다섯 패널을 포함한다. [로그](../.evidence/ux-audit/regression.log).

실제 UI 파이프라인 **INC-1001-11-22f3**도 결함 주입 → 운전원 거부 → 생산관리자 팬95/부하70 승인 → PLC ACK DONE → **CLOSED**까지 통과했다. [로그](../.evidence/ux-audit/pipeline.log), [요청·응답·이력](../.evidence/ux-audit/pipeline.json). FUXA 모드·정상 입력·범위 거부·LOCAL 거부·복구·세 화면 폭 재검증도 통과했고 시험 전 값으로 복원했다. [FUXA 로그](../.evidence/ux-audit/fuxa.log), [결과](../.evidence/ux-audit/fuxa.json). 마지막 앱 8개 health는 모두 200이다. 이번 변경은 UI와 검사 코드이며 앞선 백엔드 단위136·실제 LLM E2E46/46은 이전 검증 근거로 구분한다.

범위는 Chromium 데스크톱·로컬 시뮬레이터이며 모바일, 다른 브라우저, 스크린리더, 실제 PLC/ERP/GCP 및 장시간 부하를 포함하지 않는다.

## 이전 점검 · 체크포인트 a4a8691

이하 16항목과 실행 결과는 첫 점검 당시 기록이다. 추가 수정·현재 재검증은 위 절을 따른다. 기존 검사기의 `.evidence/ui-review/` 결과 경로는 재실행 시 최신 결과로 갱신된다. 이번 결과는 별도로 `.evidence/ux-audit/`에도 보존했다.

대상: http://localhost:8088, 로컬 Docker 시뮬레이터. 기존 화면 구성과 디자인을 유지하면서 눈에 보이는 오류와 조작 결함을 재현·수정한다. 장기 안정성 보증과 구분한다.

## 발견 기록

### UI-01 · 스킬 편집 중 탭 이동하면 작성 내용 소실 (medium)

스킬 이름을 수정하거나 새 스킬 이름을 작성 → 전사 시나리오 탭 → 스킬 탭 복귀. 기존 값 또는 빈 양식으로 되돌아온다. 기존 스킬과 새 스킬에서 각각 재현했다. 저장하지 않은 임시 입력을 탭 이동만으로 잃는다.

- [입력](../.evidence/ui-review/draft-entered.png), [복귀 후 소실](../.evidence/ui-review/draft-lost.png)
- [수정 전 조작 영상](../.evidence/ui-review/before.webm)

### UI-02 · 기존 가이드 카드 거부 사유가 자동 갱신 때 소실 (medium)

이상 확인 → HYD-01 → 하단 가이드 카드의 거부 사유 입력 → 3초 대기. 입력창이 빈 문자열로 돌아온다. 두 번 재현했다. 위쪽 새 HITL 패널과 별개인 기존 승인 양식이다.

- [입력](../.evidence/ui-review/reject-entered.png), [3초 후](../.evidence/ui-review/reject-lost.png), [영상](../.evidence/ui-review/before.webm)

### UI-03 · 스크롤 후 탭 이동 시 새 화면 제목이 화면 밖 (medium)

긴 인시던트 상세를 아래로 읽은 뒤 모니터링 탭을 누르면 이전 스크롤 위치가 남아 새 화면의 제목·설비 선택이 보이지 않는다. 스크롤 시 사이드바 상단도 잘린다.

- [전환 직후](../.evidence/ui-review/trends-before.png), [영상](../.evidence/ui-review/before.webm)

## 검증 결과

### 추가 재현 및 수정

| ID | 문제 | 근거 / 수정 |
|---|---|---|
| UI-04 (medium) | 시간 배율 5 설정 뒤 새로고침하면 선택창은 20, 상단은 5 | [수정 전](../.evidence/ui-review/scale-mismatch.png). 서버 값을 선택창에도 동기화. 탐지·재관측은 별도 시작 설정이라는 설명으로 교정 |
| UI-05 (medium) | 스킬 편집의 긴 프로세스 선택창이 오른쪽 화면을 밀어냄 | [수정 전](../.evidence/ui-review/skills-overflow-before.png). grid 최소폭·폼 최대폭 보정, 좁은 데스크톱에서 관계 입력 줄바꿈 |
| UI-06 (medium) | 설비 연결 실패 후 복구하면 오류 문구가 카드 1칸으로 남아 HYD-03이 다음 줄로 밀림 | 장애를 브라우저에서 주입한 뒤 [복구 화면](../.evidence/ui-review/recovery-before.png)에서 발견. 오류 자리 제거 후 3카드 재생성. 회귀 검사에 자식 수 검증 추가 |
| UI-07 (low) | 원인 점수 0.04가 0.0 / 4로 줄바꿈 | [발견 화면](../.evidence/ui-review/numeric-wrap-before.png). 숫자 셀 줄바꿈 금지 |
| UI-08 (low) | 감사 상세에 `&quo`처럼 잘린 HTML entity가 노출 | [수정 전](../.evidence/ui-review/incident-form-before.png). 원문을 자른 후 HTML escape |
| UI-09 (medium) | 압력 그래프에 100 Hz 실측 파형이라고 표시하지만 화면 값은 임의 합성 파형 | 실화면의 파형과 표시 확인 후 구현 추적. 실제 PS1의 화면 수집값만 저장·표시하고 1초 간격 추이라고 명시 |
| UI-10 (low) | L9 금액 표에 단위가 빠지고 좁은 셀의 헤더가 잘게 줄바꿈 | [수정 전](../.evidence/ui-review/process-before.png). 만원 단위와 표 내부 가로 스크롤 추가 |
| UI-11 (medium) | 업로드 파일을 바꿔도 이전 파일 미리보기·적재 버튼 유지 | 샘플 매뉴얼 미리보기 → README 선택으로 2회 재현. [영상](../.evidence/ui-review/manual-stale.webm), [화면](../.evidence/ui-review/manual-stale-preview.png). 파일 변경 시 무효화, 읽기·적재 진행 표시, 완료 버튼 재클릭 방지 |
| UI-12 (medium) | FUXA 3번째 설비가 화면 밖으로 나감, 메뉴 글자가 배경과 같은 흰색, 값에 단위 누락·`##.##` 노출 | [수정 전](../.evidence/ui-review/fuxa-before.png) → [1024px 수정 후](../.evidence/ui-review/fuxa-1024-after.png). SVG 비율 유지 축소, 기존 색상에서 글자 대비만 교정, 단위·빈 값·입력 안내·중립 모드 선택 추가 |
| UI-13 (medium) | FUXA에서 거부 후 정상 명령 DONE이어도 이전 `MODE_MISMATCH`가 남음 | [실패 원문](../.evidence/ui-review/fuxa-stale-ack-before.json): API reason=null인데 화면은 MODE_MISMATCH. FUXA MQTT가 null 갱신을 무시하여 발생. MQTT에 표시용 reason_display를 추가하고 FUXA를 연결. 원래 reason 계약은 null 유지. [수정 후](../.evidence/ui-review/fuxa.json)는 화면 `–` |
| UI-14 (low) | 1024px 아키텍처 설명이 한두 글자씩 세로로 늘어남 | [전](../.evidence/ui-review/architecture-wrap-before.png) → [후](../.evidence/ui-review/architecture-wrap-after.png). 긴 링크·설명이 같은 카드 안에서 줄바꿈 |
| UI-15 (low) | 상태 배지가 많은 설비의 HYD-01 이름과 탐지 단계가 잘게 줄바꿈 | [전](../.evidence/ui-review/asset-name-wrap-before.png) → [후](../.evidence/ui-review/asset-name-wrap-after.png). 설비 이름·단계를 유지하고 배지만 다음 줄로 이동 |
| UI-16 (medium) | 기존 브라우저가 새로고침 뒤에도 이전 JS·CSS를 사용 | 실행 브라우저에서 새 requestJ 함수가 undefined이고 이전 CSS 규칙임을 확인. 자산 버전 URL + nginx no-cache로 재검증하도록 수정 |

직접 조작을 재현한 증거와 해당 코드의 원인 분석을 구분했다. 추가로 API 오류의 객체 문자열 노출, 중복 클릭의 피드백 부재, 늦은 응답이 다른 설비 선택을 덮는 경로를 보완했다. 상태 표시를 매번 비우지 않도록 했고, 구성요소의 연결 응답을 전체 파이프라인 정상이라고 표현하지 않도록 문구를 고쳤다. 서비스 연결 실패는 0건·정상 상태와 구분한다.

## 실제 검증

- **포탈 9개 화면 × 3개 폭**: 1440×900, 1262×624, 1024×768. 주요 조작을 포함한 브라우저 검사 10개 묶음 통과. 스킬 입력 유지·실제 저장 및 원문 복원, 승인 폼·포커스 유지, 연결 실패/복구, 지식 지도 검색·강조·설비 선택, Cypher 9종, 매뉴얼 미리보기·실제 적재, 전사 판단 4종·부서 관점, 역할 거부, Grafana 5패널을 실행했다. [스크립트](../scripts/ui_regression.py), [로그](../.evidence/ui-review/run.log), [결과](../.evidence/ui-review/results.json).
- **실제 UI 파이프라인 완주**: 결함 주입 → 새 인시던트 `INC-0930-05-0901` → 운전원 거부 → 생산관리자로 팬 95%·부하 70% 승인 → 요청 본문 일치 → PLC ACK DONE → CLOSED. [스크립트](../scripts/ui_pipeline.py), [기록](../.evidence/ui-review/pipeline.json), [종결 화면](../.evidence/ui-review/pipeline-closed.png), [영상 폴더](../.evidence/ui-review/pipeline-video/).
- **FUXA 실제 조작**: 모드 전환, 팬 80 입력·적용, 150 범위 거부, LOCAL에서 명령 거부, 다시 정상 입력 후 이전 오류 사라짐, 3개 화면 폭. 팬 값·모드는 시험 전 값으로 복원. [스크립트](../scripts/ui_fuxa.py), [기록](../.evidence/ui-review/fuxa.json), [로그](../.evidence/ui-review/fuxa.log).
- **최종 백엔드 회귀**: 단위 136개 통과(기존 FastAPI deprecation 경고 2개). 실제 gpt-4o-mini 필수 E2E 46/46, 171초. [단위](../.evidence/ui-review/unit.log), [E2E](../.evidence/ui-review/e2e-final.log). 앞선 전체 59/59·장애 주입 결과는 [안정성 기록](stability-plan.md)에 보존했다.
- **실패 기록도 보존**: 첫 브라우저 검사 9/10은 Grafana selector가 설치 버전과 달랐던 검사 오류. UI 파이프라인 초기 시도는 Playwright 인수 형식 오류·이전 인시던트를 보고 기다린 검사 오류였다. 수정 후 새 인시던트를 목록에서 클릭하여 완주했다. FUXA 재시험 중 SVG inner_text 사용 오류를 text_content로 수정한 뒤 실제 ACK 잔존 결함을 재현·수정했다.

## 재실행과 경계

```powershell
.venv/Scripts/python scripts/ui_regression.py
.venv/Scripts/python scripts/ui_pipeline.py
.venv/Scripts/python scripts/ui_fuxa.py
.venv/Scripts/python scripts/scenario_test.py --quick --require-llm
```

동시에 실행하지 않는다. 시뮬레이터 상태를 초기화하고 테스트 판단·감사·매뉴얼 이력 등을 남긴다. 스킬 내용과 FUXA 설정값은 복원한다. 브라우저는 Chromium이며 Playwright Chromium 설치와 실행 중인 로컬 Compose가 필요하다. FUXA 프로젝트 변경은 `python ot/fuxa/build_project.py` 후 `docker compose run --rm --no-deps fuxa-init`으로 반영한다. MQTT 표시 필드 변경은 plant-sim 재빌드가 필요하다.

화면의 배치·색 체계·탭 순서·승인 절차를 재설계하지 않았다. 모든 해상도·브라우저·키보드/보조기기 조합 또는 모든 입력값의 전수 검증은 아니다. 모바일은 검증 범위가 아니다. 시간 표시는 일부 기존 UTC 기록 방식을 유지한다. 로컬 시뮬레이터와 기업 시스템 목업의 반복 실행 근거이며, 다시간 부하·실제 PLC/ERP·GCP LiteLLM 운영 안정성을 보증하지 않는다.
