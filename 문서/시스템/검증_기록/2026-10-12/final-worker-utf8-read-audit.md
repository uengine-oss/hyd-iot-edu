# F22 — Windows 작업 파일 UTF-8 읽기 감사

실제 C 실행의 한국어 깨짐은 **BOM 없는 UTF-8 작업 파일을 Windows PowerShell5.1의 기본 CP949로 읽은 현상**으로 재현했다. 파일 쓰기, 등록 스킬 stdin, 이벤트 저장의 문자 재변환이 원인이 아니다. 감사자는 제품을 수정하지 않았고 기록을 해독해 바꾸거나 BOM을 붙이지 않았다. 이후 root의 prompt 수정과 관련 회귀 결과를 아래에 구분해 기록한다.

## 실제 파일·명령·기록 대조

증거는 루트 `.evidence/final-completion-20261012/C-actual-case.json`이다. C 처리 건은 `c3_spare.01a60b8d-284d-422b-96db-113dda3dd43f`, 작업은 `83459be8-7f6b-48d4-a35b-bd0f318e99fa`다. 실제 tool_usage_started의 명령은 다음과 같으며 Encoding이 없다.

```powershell
"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" -Command 'Get-Content -Raw context/task.json'
```

현재 보존된 실제 파일은 활성 작업 트리의 `.evidence/workspace/hyd/83459be8-7f6b-48d4-a35b-bd0f318e99fa/context/task.json`이다. 같은 파일을 읽기만 하며 다음을 직접 대조했다.

| 경계 | 확인 결과 |
|---|---|
| 실제 파일 바이트 | 시작7B-0A-20, BOM 없음. SHA-256 `015A1AB1EC68D4F084990C180D30E5CBFF26E33BA548AE91E48C172E9A0AC9AC` |
| 명시적 UTF-8 읽기 | activity_name=`발주안 제안`, query의 판단/지시/입력 한국어 정상. ConvertFrom-Json 성공 |
| PowerShell 기본 읽기 | PowerShell5.1.26100.9444, Encoding.Default.CodePage949/ks_c_5601-1987. activity_name=`諛쒖＜???쒖븞`이며 ConvertFrom-Json도 실패 |
| 실제 이벤트의 도구 출력 | activity_name=`諛쒖＜???쒖븞`, 동일 파일의 기본 읽기 결과와 문자열이 정확히 일치 |
| 콘솔 출력 인코딩 | 이 재현의 Console.OutputEncoding은 이미utf-8. 콘솔 인코딩을 바꾸는 것만으로 기본 파일 읽기의CP949를 해결하지 못함 |
| task_started | task_description의 한국어는 정상. shell이 읽기 전의 작업 원문/이벤트 경로와 구분 |

실패한 ConvertFrom-Json은 읽기 재현 중의 파싱 실패이며 제품/파일을 변경한 결과가 아니다. 원본 C의 깨진 도구 기록은 당시 실제 모델이 받은 반환을 나타내므로 그대로 보존한다. 문자열에 이미 대체 문자가 들어간 뒤의 재해독을 원문 복구나 검증으로 쓰지 않는다.

## 코드 경계와 빠진 지시

[workspace.py](../../../../it/agent-worker/worker/workspace.py)22~42행의 Utf8DirectorySink는 content.encode('utf-8')를 바이너리로 원자적 저장한다. provision의 schema_prompt.md와 task.json(130~131행)도 이 sink를 사용한다. 기존 LF 바이트 보존·경로/링크 탈출 거절 계약이 원문을 정확히 쓰므로 여기에 BOM이나 Windows 전용 재인코딩을 넣을 이유가 없다.

[runner.py](../../../../it/agent-worker/worker/runner.py)124~148행은 실제 row/query/form을 task.json에 넣고, Codex에는 등록 스킬 snapshot/실제 파일/hash가 일치한 본문을 stdin에 추가한다. [codex_provider.py](../../../../it/agent-worker/worker/codex_provider.py)27~46행은 전체 prompt를 UTF-8 바이트로 임시 stdin에 전달한다. 이 경로에는 Get-Content 기본 인코딩이 끼지 않는다.

Codex provider의 ArtifactLayout은 constitution 파일을 AGENTS.md로 내보낸다. 실제 AGENTS.md는 등록 작업 규칙과 작업 공간/결과 계약을 갖고 있었지만 Windows의 명시적 UTF-8 읽기 지시는 없었다. 당시 [prompt.py](../../../../it/agent-worker/worker/prompt.py)의 작업 공간 절도 schema_prompt 경로만 안내하고 출력 파일에는 UTF-8을 요구했으나 **입력 파일을 읽는 Encoding을 명시하지 않았다.** 모델이 task.json을 추가로 읽을 때 이 틈으로 기본 Get-Content를 선택했다.

설치된 `cliagents/providers/codex.py`의 command_execution 종료 처리는 aggregated_output 문자열을 TOOL_END의text/tool_output으로 그대로 전달한다. [events.py](../../../../it/agent-worker/worker/events.py)39~54/253행도 이를 길이 제한만 적용해 기록하며 CP949↔UTF-8 재인코딩을 하지 않는다. 실제 기록과 독립 기본 읽기가 일치하므로 표시/기록 계층에서 문자를 재해독하는 수정은 잘못된 경계다.

## root 수정과 정확한 검증 범위

root는 공통 FILE_READ_RULE을 prompt.py의 **최초 실행·사람 응답 재개·재시작·형식 교정**에 삽입했다. 등록 헌법/AGENTS 정본, 스킬 본문·snapshot·hash·원본 파일 바이트는 변경하지 않았다. 지시의 핵심은 다음과 같다.

```powershell
Get-Content -Raw -Encoding UTF8 -LiteralPath 'context/task.json'
```

```python
Path(...).read_text(encoding='utf-8')
```

원본에 BOM을 붙이거나 깨진 문자열을 재해독해 작업 내용을 추정하지 말라고 명시한다. 모든 진입 경로에 공통 지시를 넣어 새 실행에만 보완되고 재개/교정에서는 다시 빠지는 일을 방지했다. 개인 PowerShell/Codex 설정이나 작업 권한을 넓히는 변경은 없다.

새 [test_worker_utf8_reads.py](../../../../tests/test_worker_utf8_reads.py)는 네 prompt 진입점의 동일 읽기 계약을 검사한다. 실제 Windows PowerShell subprocess는 BOM 없는 한국어 task.json을 명시 UTF8로 읽는다. ConvertFrom-Json 뒤 activity_name/query와 숫자 need_qty=6을 검사하고 원본 바이트 불변을 확인한다. 이 시험의 Console.OutputEncoding은 **테스트 출력 캡처를 UTF-8로 고정하기 위한 자식 프로세스 설정**이다. 실제 제품의 입력 문제를 콘솔 설정만으로 고쳤다는 뜻은 아니다.

`worker-utf8-final.log`의 최종 결과를 직접 읽었다: **33 passed·2 warnings,5.41초,exit0**. 새 실제 PowerShell 읽기와 기존 Codex stdin/등록 스킬/a161 관련 묶음이다. 여러 번 실행한 AI가 모두 수정 지시를 따랐다는 실험이 아니며, 새로운 지시 아래 실제 C/B AI 행동을 재실행해 확인한 결과로 소급하지 않는다. 당시 C/B의 지식 부족 PENDING은 별도다.

## 의미 있는 회귀 계약과 후속 실제 확인

| 확인할 계약 | 잡아야 할 실패 |
|---|---|
| 원본 바이트·BOM·LF·스킬 hash 불변 | 읽기 해결을 이유로 artifact나 등록 스킬을 다르게 저장하는 수정 |
| 초기/재개/재시작/교정 동일 FILE_READ_RULE | 한 실행 경로에서 지시가 사라져 같은 기본 읽기를 다시 선택함 |
| 실제 PowerShell UTF8→JSON→한국어/숫자 값 일치 | 문자열만 보이지만 파싱이나 업무 값이 달라짐 |
| Codex prompt UTF8 stdin·기존 skill snapshot 대조 | 긴 작업 본문 포인터로 되돌리거나 inline 스킬을 바꾸는 회귀 |
| 실제 도구 입력/반환과 이벤트 보존 | 깨진 과거 기록을 후처리해 모델이 정상 원문을 읽은 것처럼 표시함 |

다음 실제 작업에서 모델이 파일을 읽는다면 tool_usage_started에 Encoding UTF8이 있고 반환 한국어/JSON 값이 원본과 일치하는지 확인해야 한다. 모델이 stdin만으로 완료해 추가 파일 읽기를 하지 않았다면 그것은 정상 입력 경로의 별도 결과이며 PowerShell 읽기 행동을 검증했다고 주장하지 않는다. 보류/근거 부족은 업무 지식 문제와 구분하고 이 인코딩 수정만으로 C 발주 완주를 선언하지 않는다.

ProcessGPT 모노레포의 문맥/단계 감사와 ontology-studio의 작업 공간/원문 전달 흐름을 참고했다. HYD context.py는 ProcessGPTRequestContext.prepare_context와 같은 form/users/sources/feedback 묶음을 명시하고 workspace/prompt는 cli-agent 작업 공간·provider별 artifact 계약을 따른다. 이 Windows CP949 문제를 upstream도 자동 해결한다거나 같은 수정이 있다고 주장하지 않는다. 실제 바이트→읽기→도구 반환→기록의 경계 증거가 이번 수정의 근거다.
