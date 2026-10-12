# U16/U20/F13 수용 범위 대조 — 2026-10-12

기존 원증거만 재사용했다. 새 캡처·시험·HTTP·LLM·업무 실행은 없다. 최신 NOW 6행 및 U16/U20/F13을 우선하며, 앞선 감사에서 B 재고를 외부 사용자 자료 부족으로 분류한 결론은 승계하지 않는다. 현재 B는 공식 교육 초기값 보완 후 작업지시·부품 예약·생산 공지·결과 보고까지 COMPLETED다. 이는 물리 정비 완료나 계수기 초기화 주장이 아니다.

| 기능/요구 | 학생 화면 | 구현·시험·실행 원증거 | 현재 판정 / 남은 증거 |
|---|---|---|---|
| U16 공식 HM-8/PM-02/PR-07 등록 | 지식 관리의 현재 판본·등록 이력, 1440/1024 | final-delegated/knowledge-history PNG·JSON; accepted 3문서와 current-installed-manual-proof 12체크 | 실제 적재 화면 하위조건 확인. 추출 초안 화면과 구분. 검토 주체는 사용자 위임 Codex이며 사용자 최종 시각 승인은 별도 |
| U10 개정할 문서 선택 | 현재 문서 이름 선택, 원문 재열기, 검토 중 선택 잠금 | completion-audit/manual-selection/native-final/result.json: 실제 GET 18체크 PASS; 새 선택 시험·무음 NEW 초기화 역실험 | 구현 및 해당 동선 확인. 정확한 ID는 값에 보존하고 기본 화면에서는 이름으로 선택. 다시 적재할 필요 없음 |
| U13/F27 실제 도구 반환 해석 | 처리 기록·흐름·개별 작업의 도구 결과와 원문 | k3-and-record-followup/F27-native-3-result.json: 96체크 PASS; 보존 원문 9개 exact bytes; backend 23 및 역실험 | 해당 소비자 범위 확인. source807 검증을 현재 전체 시험으로 확대하지 않음. source812 보고 문구 변경은 별도의 8PNG 근거로 보완 |
| U16 전반 카드·폼·명칭/가독성 | 원래 9기능의 폭·상중하·상세·오류 상태 | Git 8b44088의 historical-173-ledger.json: 번호173·전후SHA173·전후관찰173; 현재 부분 캡처·참고 비교 | 과거 원장 FOUND. 현재 173PNG 재검수나 전체 사용자 시각 인수는 아님. CLAUDE 최신 범위 규칙에 따라 과거 전수 GOAL을 새 전체 재촬영 조건으로 되살리지 않음 |
| 실라버스 온라인94/95 A | 가져오기/매핑·판단·승인·PLC·효과 확인·종료 | portal-syllabus.md; phase1 실제 A COMPLETED, 재관측 recovered=false/미달, incident_closed=false | 유효한 부정 결과를 관찰할 수 있음. 95행은 실제 사건 실행·완료·추적을 요구하며 물리 복구 성공을 별도 필수로 적지 않음. 성공용 물리값이나 재완주를 추가할 근거 없음 |
| 온라인102 B | 가져오기·PM 정책·승인·정비 요청·공지·보고 | education-fixture-correction/B-business-completion-proof.json 및 NOW6; 신규 Memory/PG 12PASS·기존PG1PASS·필터 행 누락 역실험1 예상FAIL | 실제 교육 업무 종료 확인. 초기 필터 결손은 제품 초기자료 결함이었고 057로 해결. 현재 씰/필터 각각1 예약. 8,000h 작동유 미상·묶음 인원·연기 상한은 정당한 거절을 유지 |
| 온라인104 C | 구매 판단·위임 승인·발주·공지·입고·재고·종료 | final-delegated/C-business-completion-proof.json: OEM6/330만원·합격 입고·가용7·COMPLETED | 실제 종료 확인. 당시 A 추천과 현재 OEM 선택/정책을 혼동하지 않음. 반복 구매·입고 검증 불필요 |
| 최신 B 결과 의미 | 한국어 결과·보고 상세·접은 원문 | native-B-final/result.json 6PNG + raw-tail-result.json 2PNG, 전후 source812/API 불변; 실제 incident GET200 | 영어는 기본 요약에서 제거되고 원문에는 그대로 보존. 보고의 종결 동작 없음과 현재 사건 종결을 분리. 아래 명칭 한 곳의 source812 누락은 수정 진행 중 |
| 온라인49/60 U17/U18 | 에이전트 이름/목표/도구·질문·MCP 등록/읽기/근거 | NOW U17/U18 및 기존 student-codex-stdin 실제18 checks; portal-syllabus.md | 로컬 등록·읽기 실습 근거 있음. 읽기 성공을 Google OAuth나 외부 쓰기 증거로 바꾸지 않음 |
| 온라인69 U19 | 내 작업함·역할·승인/거절·권한 제한 | 기존 실제 엔진·Chromium의 역할403/입력 보존/승인200 증거 및 NOW U19 | 역할 실습 범위 확인. 공용 학생 로그인 구축은 현재 요구 범위가 아님. 외부 계정 인증과 별도 |
| 온라인115 U21 | 작은 개인 흐름 작성·등록·실행·결과 | NOW U21/student-codex-stdin 실제 읽기 흐름 DONE; 실패 단계 닫기/단일 삭제18 checks | 지원하는 로컬 읽기 예제 완료. Google 초대·참석 수락 확인까지 완료한 것이 아님 |
| K3 실제 Google 회의 | 회의 흐름 가져오기·MCP 도구 연결·담당자 확인·결과 | meeting-completion.md의 입력 계약130, K3 준비27, google-connection.md 및 이번 Google 가져오기 준비 갈래 | 실제 OAuth 앱 등록·본인 동의·인증된 서버 읽기·초대·확인 실행 미증명. 일반 프로토콜 시험/ChatGPT 앱 연결은 HYD 인증을 대체하지 않음. 서버 URI를 사용자에게 조사하라고 요구할 이유 없음 |
| 네 시트 수업 운영 | 학생별/순차 배포, 제작 실습·Notion 학습노트 | portal-syllabus.md의 운영 행122/124,101/103,101/103,92/94 및 VS Code 제작 범위 | 강사 리허설·학생 실행시간·외부 파일/Git/시간 MCP 설치/권한 등 운영 증거가 별도. 포털 신기능 결함 목록으로 전환하지 않음. Notion 학습노트는 필수지만 MCP 연동은 권한 확인 때만, 수기 정리 허용 |

각 숫자는 독립 범위다. 과거 173쌍 원장, F27 96체크, 문서 선택 18체크, 학생 흐름 18체크, 최종 B 8PNG를 합산하지 않는다. 전체2673개는 당시 판본이며 이번 제품 변경의 전체 회귀라고 쓰지 않는다. 새 B watcher의 공개PNG1/SSE 이후 DOM 분리 실패도 그대로 보존한다. 저장된 최신 도구/완료 화면은 라이브 중간 PNG를 대신하지 않는다.

현재 증거에서 확인한 좁은 표시 누락은 하나다. source812의 B-final-report-detail-1440/1024 PNG에는 일반 보고 상세에 `남긴 번호 작업지시 WO-B6F6633D2BF9E6FA`가 나온다. `caseRecord.js:687`의 `work_order: '작업지시'`가 원인이다. UIUX.md 인수 조건1은 작업지시를 사용자 기본 화면에서 바꾸거나 숨기라고 하며 UIUX_PLAN.md D1은 정비 요청을 제안한다. 원문 접기와 다른 일반 표시이므로 현재 문구 계약의 실제 누락이다. 루트가 해당 표시 수정을 배정했으며 후속 소스 동결/영향 상세1440·1024만 확인하면 된다. 원문 ID나 저장 업무 값을 바꿀 이유는 없다. 이 감사는 후속 수정이 이미 검증됐다고 쓰지 않는다.

그 밖의 U16/U20/F13 열린 체크박스만으로 미구현 기능을 추정할 근거는 없다. 공식 적재·A 부정 종결·B/C 교육 업무 종료·로컬 학생 동선은 각각 유효한 원증거가 있다. 남은 종결 조건은 위 명칭 수정의 영향 화면, Google의 실제 인증/외부 업무 증명, 전체 수업 운영 리허설, 그리고 UIUX.md 조건6의 사용자가 캡처를 보고 하는 최종 시각 판정이다. 시각 승인은 Codex 위임 원문 검토·자동검사·참고 이미지 동등성으로 대신하지 않는다.

참고 원본은 ProcessGPT 모노레포의 업무/서비스 분리, 최신 보존 Vue `PgToolStep.vue`의 이름·진행 표시, Dify 보존 실행 기록 PNG의 요약/원문 구분, ontology-studio의 파일 출처/교육용 제조 예제 계약이다. 직접 읽은 cached Vue HEAD는 9b7391e이며 원격 최신 실행 판본이라는 주장은 하지 않는다. 원래 source812 비교 PNG와 참조 SHA를 재사용하고 다른 제품의 화면을 HYD와 픽셀 동등하거나 인증 동등하다고 표시하지 않는다.

Google identity update: root registered the real preparation agent and organizer role; identity-create-result.json and after GET originals preserve this. Configuration absence is no longer a blocker. Google calls and flow execution remain zero; actual authenticated external execution is unproved.

Final narrow native proof: native-labels/result.json ok=true. Both 1440/1024 detail PNGs were inspected; the source812 label gap is resolved with the required Korean maintenance-order display. Raw report stays folded and equals stored original; source, API bytes and business remain unchanged, writes/errors zero. Earlier collector incorrectly banned the required term; original failures are preserved separately and the corrected decision uses already captured DOM/PNGs, without another live run.
