# 실제 학생 동선 검사기

`scripts/probe_overnight_student.py`는 메인만 라이브 잠금 아래 실행한다. 작성자는 라이브 실행하지 않았다. HTTP 요청·응답 전부, checks.json, summary.json, 생성 리소스 owned.json을 `--out`에 남기고 실패 시 exit 1을 반환한다. 고유 접두사는 `overnight-20261012-<8자리>`다. 전체 구성 reset, DB 직접 수정, 가짜 워커 출력 주입은 없다. 생성 자원은 자동으로 전체 삭제하지 않고 메인의 확인·좁힌 정리 대상으로 남긴다.

예시 명령(루트의 Python 사용):

```powershell
D:/work/study/hyd-iot-edu/.venv314/Scripts/python.exe scripts/probe_overnight_student.py --process http://127.0.0.1:8080 --mcp-url http://host.docker.internal:8311/mcp --out D:/work/study/hyd-iot-edu/.evidence/overnight-20261012/student-live
```

실제 소스 계약은 `agent_authoring_api.py`, `agent_authoring.py`, `ask.py`, `mcp_registry.py`, `mcp_api.py`, `flows_api.py`, `bpmn_import.py`, `instances.py`, `instance_mode.py`, `mcp_calls.py`, `students/_template/mcp_table_reader/server.py`를 확인했다. 기존 `scripts/probe_v_student_paths.py`와 `tests/test_capstone_g3_mcp_extract.py`의 호출·읽기 추출 계약을 참고했다. ProcessGPT 모노레포와 ontology-studio의 로컬 README도 확인했으며 두 제품의 개요를 HYD API 계약으로 대신하지 않았다.

| 단계 | 요구하는 실제 증거 |
|---|---|
| U18 MCP | streamable_http 등록·재연결 검사, attendee의 email/required/response 실제 read_rows, where meeting_id=s00:meeting-q3, 비어 있지 않은 DB 결과 |
| U17 작성 | 학생 이름·역할·목표·연결 도구·work_rules 저장값. 현재 키 hyd-plant를 저장한 뒤 null 공통규칙으로 수정해 개인 업무와 설비 규칙을 혼동하지 않음 |
| U17 질문 | 실제 `/ask` 완료, 서버가 실제 도구 기록과 대조한 kind=answered·verified evidence, 대상 서버의 실제 read_rows 입력, MCP 호출 기록 |
| U21 흐름 | 직접 시작 → 학생 에이전트 읽기 → 결과 보고 → 종료. 등록 전 검사 통과, 실제 에이전트·보고 DONE, 해당 작업의 성공한 read_rows trace, 응답 이메일이 실제 summary에 포함 |
| U9·F2 | 읽기 MCP 결과에 존재하지 않는 추출 경로로 실제 시스템 실패 유도 → PENDING → 실행 중 단일 흐름 삭제 409 → `/close` → COMPLETED/closed-by-human 및 작업 CANCELLED → 단일 흐름 삭제·404·projection_pending=0 |

시스템 PENDING 검사는 **K4 에이전트 PENDING 검사가 아니다**. graph projection의 API 큐 결과는 Neo4j 노드 부재 증명과 구분하며 메인의 실제 그래프 대조가 추가로 필요하다. U21은 로컬 표를 읽는 예제이며 Google 일정 확정·메일 발송 성공을 주장하지 않는다. K3 인증 문제를 이 예제로 닫지 않는다.

작성 검증: Python 컴파일과 `--help` 정상. 두 생성 BPMN을 실제 `bpmn_import.parse_bpmn/check`로 오프라인 검사해 모두 problems=[]를 확인했다. 첫 검사에서 outcome `조회 완료`는 허용 enum이 아니라 거절됐고 `정상`으로 고쳐 다시 확인했다. HTTP나 워커 실제 통과 결과는 아직 없다.

## 이후 메인의 실제 실행 결과

증거 루트는 `.evidence/overnight-20261012/`다. 위 「실제 결과 없음」은 작성 시점이며 이후 결과는 아래와 같다. 사용자가 Claude 주간 한도 이후 Codex 워커 전환과 통상 구현 판단의 자율 진행을 승인했다.

- `student-live`: U18 실제 MCP 등록·검사·반환 행·입력 일치 4 checks, U17 프로필·업무 규칙 2 checks 통과. ask는 검사기가 UUID가 아닌 request_id를 전송해 400이었다. `ask.py`의 uuid.UUID 검사와 실제 `ask.js`의 randomUUID 계약을 확인하여 검사기를 UUID로 고쳤으며 owned.json에 기록한다. 이 요청 형식 오류는 제품 워커 실패와 별개다.
- 같은 실행의 U21 실제 Claude 워커는 주간 한도로 RunFailed였다. 안내 리셋 시각은 10월 14일 00:00 Asia/Seoul이었다. root가 실제 실패 task를 `/close`로 닫았고 task CANCELLED·instance COMPLETED·end_event=closed-by-human이었다. 미도달 Report도 설계대로 CANCELLED이며 실행되지 않았다. root 임시 검사에서 Report TODO를 기대한 assert는 검사 기대 오류였고 제품을 바꾸지 않았다. 원문은 `failed-agent-close.json`이다.
- 이어서 U9는 실제 잘못된 extract로 시스템 PENDING → 실행 중 삭제 409 → close → 단일 삭제 → GET 404·projection_pending=0까지 통과했다. 실제 Neo4j `deleted-flow-graph.json`에는 ProcessVersion/Instance가 없고 ExecutionProjection fence 한 개만 남았다. 이 fence는 지연된 투영 재생성을 막는 정상 tombstone이다.
- `student-live` 전체 summary는 실패로 보존한다. 일부 통과를 전체 성공으로 바꾸지 않는다.
- `student-codex`: U17 결과 unanswerable, U21 Read·Report DONE이지만 실제 MCP trace가 없어 검사 실패다. 작업 종료 상태만으로 성공으로 판정하지 않는다. 이 실행은 Claude Read 도구 전용 포인터가 Codex에 전달되어 실제 작업 본문을 읽지 못하는 F15를 드러냈다.
- F15는 Codex 최초·재개·교정에 전체 UTF-8 본문을 stdin으로 전달하도록 고쳤고 관련 86개 시험이 통과했다(`backend-remaining.md`, `codex-transport-tests.log`). 실제 Codex 학생 동선은 재검증 중이다.
- K4 자율보류는 아직 완료가 아니다. 모델 본문에 `__deferred__`가 있어도 실제 task가 DONE이면 PENDING 재현이 아니며, 실제 한도 실패 task 닫기 성공과 구분한다.

검사기의 기술 ID Read·Report·BrokenRead는 유지하고 신규 BPMN 화면 이름은 각각 「참석 응답 읽기」「조회 결과 보고」「읽기 결과 경로 확인」으로 바꿨다. 생성 agent·흐름·처리 건 이름도 한국어이며 개인 흐름 대기는 명시적 종료 상태만 인정한다. 이미 저장된 이전 증거를 변경하지 않는다.

## stdin 수정 후 실제 성공

메인 실행 `student-codex-stdin/summary.json`은 **18 checks 모두 PASS**다. 문서 담당도 passed=true 원문을 확인했다. U17 실제 MCP 호출과 검증된 근거 답변, U18 읽기·연결, U21 실제 에이전트 도구 trace와 Report DONE, U9 실제 시스템 PENDING 닫기, F2 단일 삭제·projection queue 검사를 통과했다. 과거 실패한 두 실행 summary는 보존한다. 이 성공은 Google 외부 쓰기나 자율보류 K4의 성공을 뜻하지 않는다.

성공 후 구조화된 MCP 인자의 질문 근거 계약과 폼별 교정을 더 엄격하게 수정했다(F16, 관련 F17 포함 179개 시험). 따라서 위 18개 실제 통과를 후속 모든 변경의 live 검증으로 소급하지 않는다.

## release 실제 재검증

최신 Windows Codex adapter와 엄격한 서버 alias/인자 대조 적용 후 root의 `student-release/summary.json`은 **18 checks 모두 PASS, exit0**다. 실제 ask verified 근거·read_rows 입력/기록·개인 흐름 DONE·시스템 PENDING 닫기·F2 projection_pending0을 재확인했다. 이는 앞선 stdin 성공을 소급한 결과가 아니라 별도 실제 재실행 결과다. F3 HM-8은 실제 제안이 생성됐으나 사람 검토/적재 전이다. 사용자 최신 Sol6.1 전용 지시로 Astra PM-02는 공식 cancel했고 Sol PM-02·PR-07 실제 제안이 모두 생성됐다. 두 문서 사람 검토 준비는 `manual-review-packet.md`에 연결한다. student-release 성공은 이 매뉴얼 적재나 실제 B 완주를 대신하지 않는다.

## K4 실제 Sol 6.1 자율보류와 공식 종료

후속 메인 실행 `k4-live/summary.json`은 **7 checks 모두 PASS, exit0**다. 실제 Sol6.1은 등록 MCP의 read_rows 반환에서 customer@example.com이 required=true·response=none임을 확인하고 `__deferred__`로 보류했다. 해당 작업에 속한 성공한 도구 trace와 UNKNOWN 사유/실제 행을 대조했다.

실제 agent task PENDING과 소유 대상이 그대로임을 재확인한 뒤 공식 close를 호출했다. 처리 건은 COMPLETED/closed-by-human, agent 및 미도달 Report는 CANCELLED이며 업무 결과 보고는 실행하지 않았다. `k4-live.log`와 closed-instance 원문을 보존했다. 이는 이전 RunFailed 닫기나 시스템 PENDING 검사를 소급한 것이 아닌 실제 자율보류 에이전트의 별도 실행이다. B의 열린 incident close409나 외부 일정 확정과 구분한다.

PR-07 후속 신규2.4 실제 Sol 재추출은 COMPLETED/6절차21단계이며 기존2.3 정의 불변을 확인했다. 이는 학생18 checks나 매뉴얼 사람 검토/적재 성공으로 소급하지 않는 별도 실제 실행이다.

## U15 실제 사용자 설명 언어 대조

보존된 실제 실행 표본을 별도로 읽었다. `student-release/personal-agent-detail.json`의 진행 설명과 결과 요약, `ask-final.json`의 질문 답변은 한국어다. `k4-live/pending-agent-detail.json`의 진행 설명과 필수 참석자 미응답으로 보류한 사유도 한국어다. `worker-sol-only.log`의 PM-02 실행 진행 설명(35·60·75행)과 최종 PR-07 2.4 진행 설명(156·191·228행) 역시 한국어다.

남은 영문은 실제 도구 이름·서버 이름·JSON 필드·반환값·자료 인용이다. 이를 다른 값으로 바꿔 표시하지 않았다. CLI의 shell_snapshot/auth_storage 경고는 진단 로그이며 모델의 사용자 진행 설명과 구분했다. 확인한 실제 표본에서 영어 설명문은 발견하지 못했다. 이는 지시 추가만의 주장이나 모든 미래 출력에 대한 보증이 아니라, 위 실행 원문을 대조한 결과다.
