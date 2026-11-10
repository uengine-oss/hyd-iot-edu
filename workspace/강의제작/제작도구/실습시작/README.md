# 학생 랩 ZIP과 독립 시작본

학생은 클래스룸 그 회차의 실습 자료에서 해당 ZIP을 내려받아 압축을 풀고, 랩 폴더를 VS Code의 「파일 → 폴더 열기」로 연다. 코딩 랩 ZIP에는 랩 폴더 옆에 가이드(`<랩>_guide.html`)가 함께 들어 있어, 학생은 가이드를 브라우저로 열고 AI는 VS Code로 연 랩 폴더만 읽는다(가이드.md P-3). 일반 웹 링크는 PC 명령을 실행하지 않는다. 학교 기본 설치에 Python·VS Code가 있어야 하며 DB 실습은 Docker가 필요하다.

이어서 할 때는 같은 랩 폴더를 다시 열고, ZIP을 새로 풀면 고친 파일이 없는 새 폴더가 된다. 학생 개인 Git 설정은 사용하지 않는다. VS Code 신뢰 설정은 바꾸지 않는다.

## 생성

랩 하나를 고치면 그 랩의 생성기 하나만 돌리고(아래 표), 이어서 검사한다. 다른 랩 ZIP은 다시 만들지 않는다.

시스템 코드(main의 `ot/` · `common/` · `it/`)를 읽는 생성기(`data_conditions.py`와 그것을 부르는 `build_judgement_labs.py` · `reference/session3/run_reference.py`, `data_documents.py`와 그것을 부르는 `build_document_labs.py` · `build_session3_documents.py`, 포털 기준 지도를 시드에서 읽는 `build_labs.py`와 그것을 부르는 `session2_completed.py`)는 `lab_package.system_root()` 한 곳으로 위치를 찾는다. workspace만 받은 곳에서는 `git worktree add ../main main` 뒤 `HYD_MAIN_ROOT=../main`을 붙여 돌린다.

```powershell
python workspace/강의제작/제작도구/실습시작/<표의 생성기>     # 폴더만 고쳤으면 lab_package.py <랩 폴더> --version <새 판>
python workspace/강의제작/제작도구/실습시작/verify_packages.py [<ZIP 또는 랩 폴더> …]
```

- 학생 ZIP은 `lab_package.py` 한 곳이 쓴다. 항목 시각을 고정하고 경로를 소문자 순서로 넣어, 같은 PC(같은 zlib)에서는 내용이 같으면 바이트도 같다 — 바뀐 랩만 `package-index.json`의 해시가 바뀐다. 이 방식 전에 묶은 ZIP은 다음에 다시 묶을 때 한 번 줄끝(CRLF→LF)과 시각 때문에 해시가 바뀐다.
- 폴더만 고친 랩은 `lab_package.py <랩 폴더> --version <새 판>`으로 그 ZIP과 목록 항목 하나만 고친다(생성기의 다른 변경이 딸려 오지 않는다). 새 ZIP이 `verify_packages.check_zip`을 통과할 때만 바꿔 끼우고, 바이트가 바뀌는데 판 이름이 없으면 멈춘다. START.md 랩은 `start_guides/build.py`로 묶는다.
- `verify_packages.py`는 `package-index.json`의 ZIP(해시 · 시작 파일 · 가이드 링크 · 정답 경계)과 학생 ZIP 전부(`산출물/*/실습/*/랩/*.zip` — 랩 폴더와 경로 · 바이트, 강사 대본 · 제작 지시 문구 · `.env`, ZIP 안 링크)를 본다. 결과는 `작업/검사/package-verification.json`.
- 학생 배포는 가이드 P-14와 배포 지침에 따라 클래스룸에서 한다. 제작 검증은 올린 커밋에 고정된 ZIP과 현재 폴더를 대조한다.
- 단계 랩(2회차 설계 · 구현, 냉각 경보 조치 판단 네 랩)의 학생 사진은 해당 랩의 `images/`에 보존한다. 감독이 확인한 사진을 `capture-provenance.json`에 `kind: 학생 실습 화면`, 가이드의 절 이름(`section`), 설명(`caption`), 대상 · 원본 경로와 SHA-256, 잘라 쓴 경우 좌표로 등록한다. `build_labs.py` · `build_judgement_labs.py`는 해당 절에 사진을 넣고 ZIP과 대조한다. 출처가 없거나 해시가 다른 사진은 그대로 보존하고 빌드를 멈춘다.

| 학생 ZIP(두 과정 합) | 생성기(`제작도구/` 기준, 이름만 있으면 이 폴더) | 지금 |
|---|---|---|
| 통합반 02회차 온톨로지 설계 | `build_session2_projects.py ontology --apply --completed`(검증 사본은 `--dest 작업/검사/<새 폴더>`), 참조·손상·새 ZIP 시험 `reference/session2_project_trials.py <랩 폴더>` | v20-project. `ontology-lab/`·같은 이름 ZIP·옆의 가이드를 함께 생성한다. 학생용 완성본은 `완성본/ontology-lab-completed.zip`으로 따로 쓴다. 기존 `build_labs.py`는 이 랩을 재생성하지 않는다. |
| 이전 구조 02회차: 통합반 그래프 · 실전반 설계/그래프 (3) | `build_labs.py [--lab <id>]`(틀 `lab_frame.py`, 제공 코드 원본 `session2_model_tool.py` · `session2_supply_tool.py` · `lab_cypher.py` · `show_result.py`, 결과 화면 단계 `session2_steps.py`, 정답 보기 `session2_answers.py`). 강사 참조 `verify_reference.py`, 정답 보기 재생 `reference/session2_toggle_replay.py`, 검사기 고의 손상 `reference/session2_check_trials.py` | v16(2026-11-05), 통합반 실습3만 v17(판단 규칙 함수 + 규칙 밖 행 표, `LAB_VERSION`) — 가이드는 랩 폴더 밖 `랩/<랩>_guide.html`, `package-index.json`에 `guide_file`. 통합반 온톨로지는 제외한다. 나머지는 `--lab`로 지정한다(다른 과정 참조 모델을 쓰는 기존 동작은 실행 전 확인). 지금 ZIP 해시로 `package-index.json`에 등록됨 |
| 02회차 실습1 관계조회 · 실습2 지식지도탐색 (4) | `build_common.py [--course 과정] [--lab relations\|map]` | 관계조회는 `--lab relations`로 두 과정의 관계조회 폴더 · ZIP과 `package-index.json` 두 항목만 쓴다(판 `2026-11-06-relations-marked`, 사진은 먼저 `촬영/neo4j/사진_만들기.py`). `--lab` 없이 돌리면 지식지도탐색도 다시 써서 그 랩의 START.md를 지우고 가이드를 생성기 판으로 되돌린다 |
| 냉각 경보 조치 판단 — 통합반 03회차 실습2 조치기준만들기 · 실습3 판단기능만들기, 실전반 02회차 실습5 조치조건표 · 03회차 실습2 판단기능만들기 (4) | `build_judgement_labs.py [--lab …] [--check]`(원자료 `data_conditions.py` — 30일 궤적, 고정 시드. 단계 · 작업 규칙 · 가이드 · 결과 화면 틀은 `lab_frame.py`, 학생 폴더의 제공 코드는 `judgement_tools/`(condition_tools · judge_tools · sop_tools) 바이트 그대로, 판정 랩 `입력/`은 `reference/session3/criteria.py`의 강사 검증 판). 강사 참조 갈래 · 판단 표 채움 · 두 번째 구현 대조 · 손계산 · 검사기 고의 손상 · 랩 사슬 · 정답 토글 재생은 `reference/session3/run_reference.py` | 구현50 판(2026-11-05): 학생은 `결과/`의 정할 자리만 채우고 `python show_result.py`가 결과 화면을 쓴다. 가이드는 랩 폴더 옆 `<랩>_guide.html`(정답 보기 토글). 판 이름 `2026-11-05-lab50`으로 `package-index.json`에 등록됨 |
| 03회차 실습1 조치결과비교 (2) | `build_session3_whatif.py` | |
| 문서 지식 — 통합반 04회차 실습2 문서지식추출 · 실습3 그래프반영과검증, 실전반 03회차 실습4 지식추출 · 실습5 그래프반영 (4) | `build_document_labs.py [--lab …] [--check]`(문서 자료 `data_documents.py` — 문서 열 개 · 문서 목록, 두 반 같은 바이트. 추출 랩 `입력/`은 3회차 판정 랩 입력 · 강사 판 결과와 같은 바이트, 그래프 랩 `입력/`은 2회차 실습4 입력 · 3회차 판 · 추출 랩의 강사 판 검토 결과 — `reference/session3_docs/branches.py`가 강사 추출 실행 `강사_추출/run1`(수업 모델 답)의 후보로 만들고, 추출 학생용 완성본의 `결과/검토`와 같은 바이트다. 수업 모델 연결 도구는 `lab_llm.py` 한 곳 — 학생 폴더에 `llm_client.py`로, 랩 DB는 `lab_db.py` 그대로). 강사 참조 갈래(추출 6 + 내 입력 6, 그래프 지점7 둘 × 두 반 — 실제 Neo4j) · 기대 항목 · 두 번째 구현 · 검사기 고의 손상 · 장난감 기준은 `reference/session3_docs/run_reference.py`, 강사 추출 실행(수업 모델 — 저장소 밖 사본에서 학생 추출 코드 `completed/extract_candidates.py`를 돌림, `--keep`으로 `강사_추출/`에 고정)은 `reference/session3_docs/instructor_extract.py` | 구현50 판(2026-11-05): 학생은 `결과/`의 정할 자리만 채우고 `python show_result.py`가 결과 화면을 쓴다. 가이드는 랩 폴더 옆 `<랩>_guide.html`(정답 보기 토글, 틀 `lab_frame.py`). 네 랩 모두 판 이름 `2026-11-05-lab50`으로 `package-index.json`에 등록됨 |
| 03회차 실전반 실습3 매뉴얼검토 (1) | `build_session3_documents.py` | 도구(포털) 실습. 돌리면 `자료/원문`이 `data_documents.py`의 지금 판(1.2판 개정 요청 초안 포함)으로 바뀐다 — 실라버스 행에 맞추는 일과 함께 가이드 산출물이 한다 |
| 04~10회차 START.md가 있는 랩 (29) | `온라인/labs/online/start_guides/build.py <랩 폴더> …`, 검사만 `--check` | 실전반 04회차 실습2의 `코드/.env` 틀은 동기화에서 빠지므로 틀이 있는 PC에서 묶는다 |
| 통합반 05~08회차 (16) | 없음 — START.md를 쓴 뒤 `start_guides/build.py` | ZIP에 강사 대본(`NN회차/대본/*_실습_*.md`)과 제작 안내가 들어 있다(검사 실패) |
| shift-handover — 통합반 11회차 · 실전반 08회차 (2) | `기존제작/labs/build_handover_package.py`(`안내.html`도 이것이 만든다) | ZIP 루트가 `shift-handover/`(다른 ZIP은 `NN회차/랩/<랩>/`)이고 ZIP 안 README.md가 폴더보다 옛 판이다 — 루트 형식을 정한 뒤 묶는다(`lab_package`는 다른 루트를 만나면 멈춘다) |
| 01회차 오프라인_모델과질문 (2) | 없음 — `lab_package.py` | |
| 01회차 실습1 학습노트 (2) | `촬영/notion/build.py` | 보관 — 생성기로 다시 만들지 않는다. 폴더를 고쳤으면 `lab_package.py`로 그 ZIP만 다시 묶는다(가이드.md 「함정」) |
| 01회차 실습2 실행환경 · 실습3 전체과정관찰 (4) | 없음 | 보관 — 생성기로 다시 만들지 않는다. 폴더를 고쳤으면 `lab_package.py`로 그 ZIP만 다시 묶는다(가이드.md 「함정」) |
| 01회차 실습4 관계그림 (2) | `촬영/arrows/build_ontology.py` · `build_student_guide.py`, `pack_arrows.py` | 보관 — 생성기로 다시 만들지 않는다. 폴더를 고쳤으면 `lab_package.py`로 그 ZIP만 다시 묶는다(가이드.md 「함정」) |
| 이전 구조 02회차 완성본: 실전반 실습3 · 두 과정 실습4 (3) | `session2_completed.py [--check]` | 랩 ZIP과 따로 받는다(package-index 밖). 실습 폴더에 정답 보기 기본 갈래를 넣고 `python show_result.py --no-open`을 돌린 판(실습4는 스크립트가 띄운 랩 DB에서 — Docker 필요). `--check` = 두 번 만들어 같은 바이트 · 새 폴더에서 check.py 통과 |
| 냉각 경보 조치 판단 완성본 (4) — 통합반 03회차 실습2 · 3, 실전반 02회차 실습5 · 03회차 실습2 | `reference/session3/run_reference.py` 8절(기본 갈래 — 정답 토글의 채움을 넣고 `python show_result.py`) | 랩 ZIP과 따로 받는다(package-index 밖). 새 폴더에서 `python show_result.py`를 다시 돌려 동봉 결과 · 결과 화면과 같은 바이트, 학생 검사기 통과를 확인한다 |
| 문서 지식 완성본 (4) — 통합반 04회차 실습2 · 3, 실전반 03회차 실습4 · 5 | `reference/session3_docs/completed.py [--model-run <폴더>] [--again-run <폴더>] [--no-neo4j]` | 랩 ZIP과 따로 받는다(package-index 밖). 추출 둘은 고정한 강사 추출 실행 `reference/session3_docs/강사_추출/run1`(instructor_extract.py `--keep` — 학생 추출 코드 `completed/extract_candidates.py` · 요청 글 · 응답 기록 · 후보)에 검토를 걸어 만들고, 같은 요청을 새 폴더에서 한 번 더 보낸 `run2`와의 차이를 검토 기록에 적는다. 폴더 표지(`결과/폴더_표지.txt`)는 넣지 않아, 완성본 폴더 · 학생 폴더에서 코드를 실행해도 `llm_client.py`가 그 응답 기록을 다시 쓰지 않는다. 고정한 실행이 없으면 문장 규칙 후보로 만든 임시판이다(`check.py`가 후보 파일마다 model_run 줄을 냄). 그래프 둘은 `run_reference.py` 4의 기본 판 산출을 넣고 새 폴더에서 안내의 명령을 실제 Neo4j로 다시 돌려 내보내기 바이트 · 학생 검사기 통과를 확인한다 |
| 01회차 `오프라인1_가이드.zip` (2) | `build_offline.py` · `build_guide_bundle.py --draft 작업/<작업>/오프라인1_제공물검수` | 풀고 `가이드열기.html`을 연다(정본 HTML · 참조 이미지 · 자료를 묶고 내부 링크를 확인). 지금은 검수 출력만 — 정본을 바꾸지 않는다 |

## 새 프로젝트 구조의 공용 API

구조와 학생 문서 범위는 `코딩랩.md` K-5~K-7이 정한다. 기존 START 랩은 해당 담당의 이전 때까지 기존 생성·검사 경로를 유지한다.

- `project_layout.write_metadata(folder, title, purpose, command="python run.py", extra_rules="")`: 짧은 루트 README, Codex AGENTS, VS Code 표시 설정을 쓴다. AGENTS는 보이고 .vscode와 실행 캐시만 숨긴다. 다른 AI 도구의 규칙 파일은 만들지 않는다. extra_rules는 랩별 작업 경계이며 정답·단계표·제작 지시를 넣지 않는다.
- 생성기는 원자료를 `data`, 학생 구현을 `app/features`, 제공 화면을 `app/ui`, 일반 처리를 `app/utils`에 쓰고 루트 `run.py`를 제공한다. output은 실행 때 만들며 시작 ZIP에 넣지 않는다.
- `lab_package.pack(folder)`는 run.py와 app/features가 있는 새 프로젝트를 영문 프로젝트 이름 하나 아래에 묶고 가이드는 그 옆에 둔다. 기존 랩의 ZIP 루트는 유지한다.
- `lab_package.entry(..., guide_steps=[s["name"] for s in lab_definition["steps"]])`는 새 구조에 layout=project를 붙인다. 가이드 순서는 학생 START 파일 대신 생성기 정의와 대조한다. `register`는 해당 id의 항목만 갱신한다.
- `verify_packages.py <ZIP 또는 폴더>`는 지정한 패키지와 그 목록 항목만 검사한다. 인수가 없으면 기존처럼 전체 목록·학생 ZIP·오프라인 링크를 검사한다.
- 구조·과제 검증은 구별한다. `reference/project_layout_trials.py`는 새 ZIP의 파일 역할·안내 중복·실행 결과 유출·영문 루트·가이드 바이트와 기존 2회차 ZIP 호환을 검사한다. 학생 AI 수행이나 DB 결과 검증을 대신하지 않는다.

## 제공 범위

- 온라인2 설계: 원자료·규칙·요구·빈 결과 틀. 실전반에는 앞 단계 설비/센서/부품 모델이 있고 공급 연결은 학생이 작성한다.
- 온라인2 그래프: 앞 단계 완성 모델 + `lab_db.py` 환경 준비. 이번 적재·조회 로직은 제공하지 않는다.
- 오프라인1 적재: 승인 편성의 제공 절차에 따라 `offline_load.py`와 질문을 제공한다. 온라인 구현 ZIP에 넣지 않는다. 설비 3대 작은 모델(노드 44 · 관계 57, 커밋 160f846a의 `reference/통합반`에서 고정, 온라인 2회차 모델 `data_session2.py`와 별개)의 정본은 두 과정 `01일차_오프라인_모델과질문/입력/`의 `graph.json` · `schema.json`이다.
- 통합반 조치 기준 · 실전반 조건표: 원문 · 판단 시스템 결정표 내보내기 · 사건 메모(실전반은 확인 사례, 통합반은 설비 모델 · 작업 이력도), 빈 결과 틀, 구조 검사, 학생용 START · 가이드. SOP 구조 · 조건표 · 기록은 학생이 작성한다.
- 통합반 판단 기능 · 실전반 조치 검토 결과: 조건 랩의 강사 검증 판(조건표 · SOP 구조)을 `입력/`에, 판단 입력의 원천 네 개 · 오더 현황 · 비교 산식 · 원문 · 수집 설명, 빈 기대 결과 틀, 구조 검사, 학생용 START · 가이드. 판단 입력 만들기 · 판정 · 비교 · 선택 이유(실전반은 검토 결과)는 학생이 구현한다. 구조 검사는 `결과/내_입력/`에 학생 자신의 앞 결과가 있으면 그것을 기준으로 보고 어느 파일을 봤는지 찍는다.
- 통합반 문서 지식 추출 · 실전반 지식 추출: 문서 열 개와 문서 목록, 조치 판단 랩의 강사 검증 판(조건표 · SOP 구조)과 판정 결과를 `입력/`에, 값이 빈 `.env.example`과 수업 모델 연결 도구 `llm_client.py`(응답 기록 · 같은 요청 다시 안 보냄 · 폴더 상한 · 키가 없으면 보낼 글만 남기고 멈춤), 입출력 계약, 빈 검토 기록 틀, 구조 검사, 학생용 START. 요청 글 · 문서 읽기 · 나누기 · 응답을 후보로 · 인용 위치 찾기 · 검토(실전반은 이 사건의 작업의 조건 모으기도)는 학생이 구현한다. 강사가 저장한 응답은 넣지 않는다.
- 통합반 그래프 반영과 검증 · 실전반 그래프 반영(작업 확인 카드): 설비 모델 · 조건표 · SOP 구조 · 추출 랩의 검토 결과(실전반은 조치 검토 결과 · 이 사건의 작업의 조건도)를 `입력/`에, 원문과 문서 목록을 `자료/`에, `lab_db.py`와 앞 단계 판 적재 · 적재 파일 실행 · 세기 · 내보내기 도구 `lab_cypher.py`, 입출력 계약, 빈 구축 기록 틀, 구조 검사, 학생용 START. 스키마 확장 · 문서 · 판 · 절 · 승인 후보 적재와 기존 ID 연결 · 조회(실전반은 작업 확인 카드도)는 학생이 구현한다.
- `reference/`와 `verify_reference.py`는 강사 제작용이며 학생 ZIP 밖에 둔다. 학생 ZIP 하나로 장난감 시험(코딩랩.md K-3 · 「길」 6)을 돌리는 도구는 `reference/ai_toy_test.py`, 학생 경로 리허설(「길」 7)의 폴더 준비 · AI 턴 · `.env` 채우기는 `reference/prepare_rehearsal.py` · `rehearsal_turn.sh` · `fill_lab_env.sh`다(쓰는 법은 각 파일 머리).

## 실행과 촬영의 구분

`lab_db.py`는 폴더별 새 컨테이너와 자동 배정된 루프백 포트를 사용한다. `랩_연결.json`의 ID와 컨테이너 라벨이 일치할 때만 재사용한다. 포털 DB에 접속하지 않는다. 이미지 최초 다운로드·Docker 기동·학교 네트워크는 별도 조건이다. `NEO4J_AUTH=none`은 새 로컬 교육 컨테이너에만 적용하며 외부 주소에 바인딩하지 않는다.

실행 근거와 미확인은 제작·검증 근거를 따른다. Python 함수·DB 검증과 학생 AI 수행, 데스크톱 화면 확인, 음성 포함 영상 완성은 서로 다른 판정이다.

새 가이드 본문은 개별 생성기에서 작성하고 `lab_frame.step_page(title, lead, sections)`로 목차·절·복사를 붙인다. `command_block`·`answer_html`은 재사용하되 기존 `step_guide`의 고정 안내를 넣지 않는다. `guide_cost`와 `write_guide`에는 `ai_turns=요청 횟수`를 넘겨 자연문 본문도 대기 시간을 추정한다. 실측 `ai_wait`를 넘기면 그 값을 우선하며 새 판의 실측으로 오인하지 않는다. 정답 토글에 CSV 행을 넣지 않는 새 가이드는 손행·근거행이 자동 집계되지 않으므로, 랩 정의의 실제 사람 작업을 별도로 더해 계획에 기록한다.
