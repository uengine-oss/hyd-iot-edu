"""Integrate current top/table while preserving the former top as dated historical scope."""
from pathlib import Path

report = Path('D:/work/작업보고/2026-10-12.md')
text = report.read_text(encoding='utf-8-sig')
marker = '[debug](D:/work/claude-skills/skills/debug/SKILL.md)'
prior, remainder = text.split(marker, 1)
assert '후속 최종 준비 — F27 실제 화면 판정 대기' not in text
current = '''# 2026-10-12 HYD 포털·업무 기능 작업 보고

후속 최종 준비 — F27 실제 화면 판정 대기. 구매 처리 기록·긴 정비 입력·보류/대체 상태의 UI6파일 수정을 새 계약10개·관련32개·실제C21항목으로 각각 확인했다. 첫57/59 실제 검사와 넓힌60통과·2실패 원문을 보존하며 통과 수를 중복 합산하지 않는다. 완료 판본은 `k3-and-record-followup/completed-source-manifest.json`으로 고정했고 이후 F27 변경에는 그 통과를 확대하지 않는다.

긴 도구 출력 F27은 원문9개 보호 GET·길이/SHA/cut=false·JSON 확인과 backend 집중22개+공유원문1개까지 진행했다. 기존69개는 초기67통과·2실패·3경고, UTF8 환경 보완 뒤 원문fold1통과, VM 단독load1통과의 별도 실행이다. deliberate legacy repr 복원9실패는 부정 검사가 결함을 잡았다는 증거다. UI중간실패/중단과 최초경고를 보존하며 최종 안정 판본·실제 화면 해소는 아직 기다린다.

K3 준비27통과·Authlib 폐기예고1이며 실제 OAuth/Google읽기·초대·등록값 기반 실행용 사본0이다. [후속 검증 기록](D:/work/study/hyd-iot-edu/.claude/worktrees/codex-portal-20261011/docs/handoff/verification/2026-10-12/k3-and-record-followup/README.md)과 [NOW](D:/work/study/hyd-iot-edu/.claude/worktrees/codex-portal-20261011/docs/handoff/NOW.md)에 범위와 잔여를 기록한다. 최종 Git 반영·배포/캡처 판본은 루트의 후속 결과를 기록할 때 갱신한다. 이전 a617be3/61bca69 push 결과는 아래 당시 기록으로 보존한다.

| 사용자 요구 | 현재 확인한 작업·증거 | 판정·남은 조건 |
|---|---|---|
| 구매·정비 처리 기록과 읽을 수 있는 값/상태 | UI6파일 새10·관련32·실제C21, 원래추천/현재OEM승인 분리·소스SHA·업무 저장값 불변 | 이전203항목은 놓친 결함이 있어 화면 정상 근거로 확대하지 않음. F27 실제 소비자 화면 해소 대기 |
| 긴 도구 출력의 블랙박스 해소 | 저장원문9개 보호GET·길이/SHA/cut검증, backend22+공유원문1, deliberate legacy9실패, 기존69의 분리후속 | F27 UI 중간결과는 최종 통과가 아님. 표시행 자동 원문조회/검증/업무 의미와 root 실제캡처가 필요 |
| 실제 A/B/C와 최종 실라버스 | A 미달 프로세스COMPLETED·incident_closed=false, B 실제재고/기한으로PENDING, C 교육용ERP 순정6개330만원 발주·합격입고·가용7·COMPLETED | 최종XLSX 온라인95행은 물리복구 성공을 필수라고 쓰지 않음. A 부정종결도 실습 근거이며 경보해제로 부풀리지 않음. B 진짜자료 준비 필요 |
| 실제 회의와 외부 MCP | 실제 계약 기반 K3 helper27통과·원본보존·runtime실행키, 원래 예시 유지 | 등록/인증된 Calendar·Drive·실제자료·주관자승인·초대/응답 미검증 |
| UIUX 참고·전체 시각 판정 | 참고 나란한PNG4이미지로드·9참조존재·console/pageerror0, root부분시각확인 | 정본173쌍 ledger coverage는 UNVERIFIED(0이라고 단정하지 않음). 부분22PNG/46화면/203검사는 대체근거가 아님. 전체사용자시각승인 남음 |
| 효율·기록·보호 | 이전전체2673은 당시판본만, 신규LLM/업무재완주/전체재실행0, 기존실패·경고·사용자원문 보존 | 교재/lecture-deck·원본볼륨·과거판단 불변. 메인/하위/워커 Sol6.1만. 새확인코드결함은 F27 외에 만들지 않음 |
| 실행환경 | 실제18:59 KST 읽기전용 상태 running29·LIVE_LOCK없음·8097없음 | 이 시각 snapshot이며 후속 root배포/최종읽기 상태로 갱신 필요. 서비스는 사용자 열람용 유지 |

<details><summary>2026-10-12 phase2 최종 요약 — 후속 PNG 정정·F27 전의 당시 범위</summary>

'''
report.write_text(current + prior + '\n</details>\n\n' + marker + remainder, encoding='utf-8')
print('Current report top/table integrated; former top and all user/history text preserved.')
