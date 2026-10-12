# 공개 처리 과정 스트림 감사·수정

기준은 앞선 전체 2,673개 통과/16개 건너뜀의 소스 판본이다. 이번 변경 뒤 전체 시험을 다시 실행하지 않았다. 사용자 요구의 공개 설명·도구·근거·추천·실행·확인 과정과 모델 비공개 내부 추론을 구분한다.

## 원인과 수정 경계

기존 worker/events.py의 ASSISTANT_TEXT는 저장 대상이 아닌 text 이벤트였다. runner.emit은 저장 가능한 이벤트만 record_events로 전달하므로 공개 문장은 도구/결과 경계의 NoteBuffer.flush 전에는 DB와 SSE에 도달하지 않았다. 경계 기록도 1,500자에서 절단됐다.

runner는 최초 공개 문장을 즉시 저장하며 이어지는 공개 문장을 최대 4Hz로 전체 누적 snapshot에 저장한다. 도구·결과·실패·스트림 종료 경계는 전문 snapshot을 강제 저장한다. run UUID / message_id / sequence로 단계·실행을 구분한다. 진행 중 snapshot의 type은 public_text, 확정 문단은 기존 text이며 기존 문단별 기록 계약을 보존한다. 결과와 같은 마지막 문장은 빈 완료 snapshot으로 대체하여 최종 답변을 두 번 표시하지 않는다. THINKING은 DB/SSE 이벤트로 생성하지 않는다.

같은 task/job/run/message의 최고 sequence만 화면에 표시한다. trace/taskDetail/caseRecord/liveStream이 같은 reducer를 소비하므로 중복 도착·순서 역전·재접속 시 같은 문장은 하나다. 전문 snapshot 덕분에 앞 delta를 놓친 재접속도 받은 최신 전문을 복원한다. 공개 문장 원문은 절단하지 않으며 긴 설명은 기존 접기 안에서 끝까지 접근한다. 색상·CSS·새 화면 구조는 바꾸지 않았다.

매 token 전체 snapshot을 저장하면 N² 저장량이 발생하므로 첫 문장 즉시/이어지는 입력 250ms 간격/경계 강제 저장으로 빈도를 제한했다. 입력이 없는 동안 새 내용은 없으며 남은 공개 내용은 종료·실패 경계에서 보존한다. 1,000개 고빈도 2자 delta 시험은 첫 2자와 마지막 2,000자, 총 2개 snapshot/2,002자를 저장했다. 이는 실제 장시간 모델 실행의 최대 저장량 측정은 아니다.

## 검증과 남은 범위

최초 관련 시험은 68개 통과였다. 확대 시험에서 기존 문단 기록에 snapshot이 중복되는 회귀 1개가 발견됐다(79개 통과). 최초 실패 `F/pytest-public-stream-final.log`를 보존하고 public_text 진행 이벤트와 text 확정 기록을 구분했다. 기존 기대값을 변경하지 않았다. 최신 집중 결과는 `F/pytest-public-stream-final3.log`이다. MemoryRepo의 실제 runner→record_events, 실제 SSE generator, 실제 portal JavaScript reducer를 검증했다. 긴 공개 전문·실패·최종 결과 중복 제거·고빈도 저장량·재연결·여러 실행·역순/중복·비공개 추론 제외를 포함한다. 메인 DB 쓰기·워커 실행·배포는 하지 않았다. 실제 모델 공개 문장 도착→native DOM→경계 전 PNG 검증은 root의 단일 실제 실행과 watcher 소유이며 이 시험으로 대체하지 않는다.

| 요구 | 현재 증거/판정 |
|---|---|
| 공개 assistant 설명 실시간·전문 | 새 생산자/SSE/소비자 집중 시험 검증됨; 실제 모델/화면 지연 실측 미검증 |
| 도구 입력·출력·근거·추천·승인·실행·확인 | 기존 DB/SSE/trace 기록 배선 존재. 큰 도구 반환은 event_payloads와 caseRecord 원문 페이지로 보존. 추가 수정에서 도구 입력 전문도 동일 journal의 full_input으로 보관하며 방향을 명시하고, 이벤트 입력 원안도 유지한다. 일반 trace/taskDetail/caseRecord의 원문 fold 글자 절단을 제거했다. 짧은 요약만 축약한다. 추가 25개 집중 시험으로 긴 입력·출력 끝문자, 저장 실패의 원문 유지 및 기존 payload 접근 경계를 검증했다 |
| bpmn.io 학생 등록/매핑/검사/실행 | NOW K2 및 U7/U8 기존 실제 왕복·등록 증거. U20 실제 A 미달 종결과 B/C 보류 이력은 업무 성공과 구분; root 현재 적재 후 실행 결과 확정 전 |
| 실라버스 학생 도구·개인 흐름 | NOW U17/U18/U21 실제 로컬 MCP·Codex 실행 증거. U19 독립 노트북 역할 선택은 공용 로그인 구축이 아니며 Google 외부 인증 완료와도 별개 |
| 최신 ProcessGPT UI 비교 | 정확한 refs checkout 두 묶음을 확인했다. reaudit/references-latest의 Vue3 9b7391e, 모노레포 6ad9db6, studio 6a229be는 현재 원격보다 오래됐다. portal-20261011/refs의 모노레포6084127·studio20afcde는 origin HEAD와 일치, Vue3 867e8cf는 현재265580f보다 오래됐다. Vue3 최신 원격 객체를 읽어 관련 EventTimeline diff를 확인했다: cliagents 완료 작업을 Markdown으로 보는 분기 2줄 추가이며 공개 delta 구조 변경이 아니다. 해당 최신 diff, shared/agentTimeline의 tool_use_id별 짝짓기, PgToolSteps 세로 단계, 모노레포 README 및 studio ContextPanel의 스킬/참조파일 분리 표시를 직접 읽었다. ContextPanel과 PgToolSteps는 두 checkout 간 차이 없다. 새 화면 디자인이나 픽셀 일치 완료를 주장하지 않는다 |

F는 `D:/work/study/hyd-iot-edu/.evidence/delegated-review-20261012`다. 배포 전 소스 SHA는 별도 `public-stream-source-sha.json`에 저장한다.

공개 스트림 집중 결과는 **87개 통과, 8.21초**(`pytest-public-stream-final3.log`)이다. 그 뒤 입출력 원문 추가 부분만 **25개 통과, 2.48초**(`pytest-tool-verbatim-first.log`) 검증했다. 기존 전체 회귀를 반복하지 않았다. 관련 trace/taskDetail/caseRecord/liveStream의 index 캐시 키도 새 판본으로 올렸다. 실제 LLM 업무 가이드 경로의 회사 frentis-ai-model/OpenAI 호환 endpoint와 CLI 작업의 승인된 Codex/Sol 실행은 서로 다르며, 모든 포털 AI가 GPU에서 실행된다고 주장하지 않는다.
