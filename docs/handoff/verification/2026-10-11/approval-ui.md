# 승인 · 거절 · 반려 · 지연 UI 검증 (2026-10-11)

작업 트리 `codex-portal-20261011`. U1~U3 및 이 화면 범위 U10. API·엔진·판단 값·승인 카드 고정 fixture는 수정하지 않았다. 커밋·push는 메인 통합 담당 범위다.

## 구현

- `instances.js`: 활동 `outputData`에 `approval`이 있는 경우에만 [거절]을 표시한다. 사유는 앞뒤 공백을 제거한 1~2000 유니코드 문자, 담당자·역할을 확인하고 기존 `POST /api/todolist/{id}/reject-card`를 호출한다. 승인/거절 요청 중 두 버튼과 입력을 잠그고 중복 요청을 막는다. 403/500 뒤 사유·담당자·역할·선택 값을 보존한다.
- 승인 지연은 알림만 표시한다. 작업/이벤트/변수 변경을 poll 서명에 포함해 알림만 추가되어도 화면을 갱신한다. 카운트다운은 1초마다 글자만 갱신하므로 입력을 다시 만들지 않는다. 전체 갱신 때도 입력 포커스·선택 범위·펼침을 보존한다.
- `resultReport.js`: 반려를 별도 판정으로 표시하며, 단순 완료나 정상으로 표현하지 않는다. 시스템이 한 일에서 정의의 타이머/이벤트를 제외해 승인 대기 자체를 실행 중이라고 안내하던 문제를 고쳤다.
- `caseRecord.js`·`trace.js`: 반려 칩, 거절한 담당자·사유·승인 뒤 조치 없음이 처리 기록과 실시간 단계에 나온다. 기록 머리의 반려도 위험색이다. 지연 알림 시스템 단계에 이름만 보고 붙던 ‘승인’ 행동 칩을 제거했다.
- `ui.js`·`plainWords.js`: 승인 여부/결정 사유/결과 보고 출력 키를 한국어로 표시하고, 처리 기록에서 이름을 찾지 못한 `agent:*`·`user:*`를 일반명으로 표시한다. **전역 `UI.who()`의 원래 id 반환 계약은 유지**한다. 공통 필드 라벨은 입력 id에 연결했다. 지연 요약에 붙은 해당 사건의 내부 경보 번호는 표시 문장에서만 제외하며 원본 데이터는 보존한다.
- `app.js`: 업무 경보의 직전 결과가 반려이면 반려 칩을 표시한다. B/C 업무 표시가 켜진 채 남는 서버 의미를 바꾸지 않는다.
- `index.html`: 이번 수정 JS/CSS의 캐시 키를 `20261011-portal`로 갱신했다.

## 실제 Chromium 시험

`tests/test_portal_approval_ui.py`는 실제 `index.html` 전체 템플릿과 모든 production CSS, 실제 app navigation, `instances.js` 전체 load/render 흐름, 요청 helper, 승인 카드·결과·처리 기록·실시간·흐름도 renderer를 읽는다. `section#view-instances` 및 원래 좌우 목록/상세 배치를 유지한다. 관련 모듈만 실행하는 격리 데이터 시험이며 제품 테스트 전용 export·응답 값 조작은 없다. Playwright 라우팅으로 FastAPI의 실제 `instance_mode` 경로를 호출하고, `test_approval_stage.opened`의 MemoryRepo 엔진·실제 Incident·판단 권한 검사를 사용한다. 설비/업무 외부 효과는 기존 시험 대역이다.

| 확인 | 결과 |
|---|---|
| A/B/C × 1440/1024: 거절 → 반려 결과·사유·처리 기록·실시간 줄 | 통과 |
| 반려 뒤 설비 명령·업무 처리·메일·실행 기록 0건 | 통과 |
| 빈 사유/2001자: 요청 전 차단 | 통과 |
| 실제 권한 403, 주입한 서버 500: 입력·역할 보존, 다시 제출 | 통과 |
| A/B/C 실제 지연 타이머 → 승인 작업 열림 → 화면에서 승인 가능 | 통과 |
| 승인·거절 동시 이벤트루프 중복 click 각각 요청 1개 | 통과 |
| 작업 상태 변화 없이 이벤트만 추가: 정상 poll 갱신, 입력·선택 범위 보존 | 통과 |
| 브라우저 pageerror, 가로 넘침 | 캡처 시 0건 |

최종 실행 로그: `<루트>/.evidence/portal-20261011/approval-browser-tests.log`: **11 passed (55.19초)**. 실제 index 템플릿·모든 CSS·navigation·흐름도 renderer로 교체한 최종 시험이다. Screenshot 시험은 새 행 애니메이션이 끝난 뒤 캡처한다. API poll이 이미 실행 중일 때 다음 poll/갱신 완료를 기다린 뒤 지연 표시를 검사한다.

처리 기록 반려 카드로 스크롤한 보조 재촬영: 같은 반려 검사 **6 passed, 5 deselected (35.99초)**, `approval-record-capture.log`. 기록 머리의 원래 화면도 `-overview.png`로 보존했다.

실행:

```powershell
$env:PYTHONUTF8='1'
$env:PATH='C:/Program Files/LibreOffice/program;' + $env:PATH
$env:APPROVAL_UI_EVIDENCE='D:/work/study/hyd-iot-edu/.evidence/portal-20261011'
& D:/work/study/hyd-iot-edu/.venv314/Scripts/python.exe -m pytest tests/test_portal_approval_ui.py -q
```

## 읽은 참고와 비교

- 최신 ProcessGPT UI clone `867e8cf`: `src/ds/components/PgField.vue`의 라벨·입력·힌트, `PgAlert.vue`의 상태 알림, `PgCard.vue`의 제목/내용/행동 위계. `src/components/apps/todolist/WorkItem.vue`의 작업 제목/상태, `InstanceOutput.vue`의 결과 카드와 좁은 폭 표시 원칙을 읽었다. [소스](https://github.com/uengine-oss/process-gpt-vue3/tree/867e8cf).
- [ProcessGPT 모노레포](https://github.com/uengine-oss/process-gpt)와 [ontology-studio](https://github.com/uengine-oss/ontology-studio)의 로컬 최신 참조 README도 읽었다. 이 범위는 승인 UI이므로 그 프로젝트들의 서비스 전체 화면을 실행했다고 주장하지 않는다.
- [Dify History & Logs](https://docs.dify.ai/en/guides/workflow/debug-and-preview/history-and-logs)의 실제 기존 문서 이미지 `.evidence/a121/refs/dify-history-logs-{2,3}.png`와 우리 실제 브라우저 화면을 나란히 배치했다. 원본 이미지는 수정하지 않았다.
- 비교 페이지 `<루트>/.evidence/portal-20261011/approval-comparison.html`, 그 브라우저 캡처 `approval-comparison.png`. 페이지에 각 이미지 출처와 시험 범위를 표시했다.

우리 원본 캡처: `approval-c3_{cooling,pm,spare}-{request,rejected-result,rejected-record,rejected-live}-{1440,1024}.png`, `approval-c3_{cooling,pm,spare}-delayed-1440.png`, `approval-c3_pm-{permission-error,server-error}-1440.png`. 승인/지연 패널 전체 높이를 읽는 보조 캡처는 같은 이름의 `-panel.png`다. 원래 포털 내부 스크롤·좌우 목록/상세·셸을 유지하며 해당 영역으로 스크롤해 캡처했다.

직접 읽은 화면에서 역할 공백, 승인 전 잘못된 실행 안내, 반려 머리칩 초록, 내부 에이전트 id 노출을 찾아 수정했다. 최종 캡처로 역할 표시·지연 알림·반려 사유·입력 보존·좁은 화면 줄바꿈을 확인했다.

## 한계

- 이 시험은 실제 포털 템플릿/스타일/관련 renderer + FastAPI + MemoryRepo 통합이다. 전체 서비스 연결, 실제 LLM, Neo4j, Supabase, 설비·업무 시스템을 함께 끝까지 돌린 라이브 완주가 아니다. 외부 지식 그래프 조회는 fixture 지원 범위 밖이라 실패 상태로 남는다.
- 승인 뒤 A의 실제 설비 응답/회복까지 새 브라우저 시험에서 재현한 것은 아니다. 여기서는 승인 수신과 설비 명령 전달 전이를 확인했고 기존 엔진 시험이 정상 종결까지 검증한다.
- 이번 Windows의 실제 포털 스택 read-only 화면 검증과 전역 pytest 수치는 메인 통합 기록에 별도 기재한다. Mac의 이전 구조판/사람 검토 근거를 이 환경에서 재생성한 것으로 취급하지 않는다.
- UIUX 계약의 최종 사용자 캡처 승인은 아직 받지 않았다. 구현·시험·캡처 완료와 사용자 최종 승인을 구분한다.
