# 실제 B 재평가·승인·업무 완료 — 추가 증거

앞선 [적용 인덱스](evidence-index.md)는 당시 B 재평가 진행 중 기록으로 보존한다. 이후 루트의 실제 B Sol6.1 재평가1회와 위임 검토/승인이 진행되어 같은 처리 건은 COMPLETED가 되었다. 이 phase2 문서 복사에서 추가 모델·업무 실행은0이다. 실제 실행1회와 증거 정리0회를 혼동하지 않는다.

## 원래 기록을 유지한 실제 실행

- [B-reassessment-accepted.json](B-reassessment-accepted.json)·[B-actual-before-approval.json](B-actual-before-approval.json)은 같은 B의 새 재평가 수락과 승인 전 실제 상태다. 승인 전 원본GET은836,186bytes이며 명시 요청 범위로 그대로 복사했다. 원본 사건 전체의 불필요한 다른 대형사본이나 worker stderr/credential은 복사하지 않았다.
- [B-approval-request.json](B-approval-request.json)·[B-approval-accepted.json](B-approval-accepted.json)은 사용자 위임 Codex의 교육 실습 승인이다. 사람으로 사칭하지 않고 물리 정비 완료 승인과도 구분한다.
- [B-business-completion-proof.json](B-business-completion-proof.json)은 실제COMPLETED, 소스 범위 HYD-02 단독4,000h 오더 등록·생산팀 공지를 기록한다. 재검토 시 씰 available7/필터2에서 각각1개씩 예약하여 가용6/1이 되었다. 이는 교육 ERP의 실제 실행 효과이며 물리 정비가 끝났다는 뜻은 아니다.
- [B-original-history-preserved.json](B-original-history-preserved.json)은 과거58이벤트 값의 exact 보존·원래보류 유지·새94이벤트를 확인한다. report의 incident_closed=false는 보고의 종결조치값이고 현재 incident CLOSED와 구분한다. 실제 기존 SMTP 영수증·원문 영문 메일은 유지했고 재발송/본문 덮기0이다.
- [authoritative-backend-restored.json](authoritative-backend-restored.json)·[receipt-localization-applied.json](receipt-localization-applied.json)은 authoritative backend와 한국어 영수증 처리를 기록한다. 표시 의미를 개선하면서 과거영수증/메일 원문을 바꾸지 않는다. [worker-owned-stopped.json](worker-owned-stopped.json)은 이번 소유 워커 종료 근거이며 추가 작업을 계속 실행한다는 뜻이 아니다.

## 최초 same-job live 캡처 실패를 보존

[watch-B-live/result.json](watch-B-live/result.json)의 passed=false와 finalCaptures 빈 목록을 그대로 보존한다. [armed.json](watch-B-live/armed.json)·[errors.jsonl](watch-B-live/errors.jsonl)·[sse-frames.jsonl](watch-B-live/sse-frames.jsonl)·[sse-connections.jsonl](watch-B-live/sse-connections.jsonl), [공개문장 PNG1](watch-B-live/B-public-before-completion-1.png)·동일이름metadata가 당시 증거다. 공개문장 PNG1을 얻었지만 **최초 same-job public+tool PNG 전체 획득은 실패**했다. 나중에 저장된 history/COMPLETED를 읽을 수 있다는 성공으로 최초 live 캡처 실패를 덮지 않는다. 루트가 새로 검증 중인 final native 폴더는 이 복사에 포함하지 않았다.

## 영수증 의미 수정과 PostgreSQL 실제 검증

[ui-positive-fix/result.json](ui-positive-fix/result.json)은 실제completed 영수증2개 JS 소비계약과 관련case-record1통과/8deselected0.86초의 command/stdout/stderr 원문을 담는다. 별도 unit 로그 파일이 없는 해당 결과는 result의 출력을 근거로 사용한다. 이 범위는 이전전체2673/UI18/F27재실행이 아니다.

[verify-pg-receipt-first.py](ui-positive-fix/verify-pg-receipt-first.py)는 처음 Memory window를 PostgreSQL에 사용하여 거절된 수집기 오류의 원문이다. PostgreSQL이 잘못된window를 production INVALID로 거절한 것을 제품 결함이나 성공 실행으로 보고하지 않는다. 기대값/원천정책은 바꾸지 않았다. [최종PGscript](ui-positive-fix/verify-pg-receipt.py)는 실제 PostgreSQL pm_status/readstock으로 plan을 만들어 원래positive조건을 통과했다. [pg-receipt-result.json](ui-positive-fix/pg-receipt-result.json)은 실제production function의 과거영수증 exact replay/향후한국어detail/예약1개씩/기존행불변/반복migration불변을 확인했고 모든시험효과를 rollback했다. [bootstrap.json](ui-positive-fix/bootstrap.json)·[bootstrap.log](ui-positive-fix/bootstrap.log)·[bootstrap.py](ui-positive-fix/bootstrap.py)와 [isolated-db-cleanup.json](ui-positive-fix/isolated-db-cleanup.json)은 격리DB 준비/정리를 보존한다. 운영DB쓰기/모델0이라는 PG검증 제한은 루트의 별도 운영 적용·Sol실행과 시간/범위를 구분한다.

SHA 종류도 구분한다. PG result의 `migration_sha256=c88e417b6eefd2aeedf378400a7f2c1e55716f762675f98e9f6affd18a2fa40f`는 Python read_text가CRLF를LF로 정규화한 **실제 실행 SQL 텍스트**의 SHA다. source/result와 receipt-localization-applied.file_sha256의 `78505041e629395f7690f8d1091269b57951e63af151a144f4c949fd075b64c2`는 **원본 migration 파일 bytes** SHA다. 두 값은 서로 다른 대상을 가리키며 raw파일불일치로 취급하지 않는다. 원문 result metadata는 수정하지 않고 이 노트로 설명한다.

## 정확 복사와 남은 범위

[phase2-copy-manifest.json](phase2-copy-manifest.json)은26파일·원본경로/bytes/SHA256/복사후동일을 기록한다. [source-final-delta.json](source-final-delta.json)·[runtime-B-final-source-manifest.json](runtime-B-final-source-manifest.json)은 이 실행의 source 범위이며 앞선 manifest를 덮지 않는다. 최종 source 전체동결/README/NOW/일일보고/새 native판정은 루트가 담당한다.

교육 ERP 결손은 공식fixture 준비·실제B작업 등록/공지까지 진전되었으나 Google OAuth·실제회의실·초대/응답확인 K3는 완료되지 않았다. 이 증거 복사는 Google조사 재실행·추가앱권한·계정credential조회·제품수정·라이브호출·스테이징을 포함하지 않는다.
