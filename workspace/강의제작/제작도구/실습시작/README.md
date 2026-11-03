# 실습 시작 도구와 독립 시작본

학생 진입은 `index.html` → `실습시작.zip` 다운로드 → 압축 해제 → `실습시작.cmd` 실행이다. 일반 웹 링크는 PC 명령을 실행하지 않는다. 학교 기본 설치에 Python·VS Code가 있어야 하며 DB 실습은 Docker가 필요하다. 현재 개발 PC에서만 확인했고 학교 초기화 이미지의 포함 여부는 미확인이다.

기본 작업 위치는 사용자가 선택한 `D:/HYD-Practice`다. `settings.json`에서 바꿀 수 있다. 새 시작은 UUID를 붙인 별도 폴더, 이전 작업 열기는 기록된 기존 폴더를 사용한다. 학생 개인 Git 설정은 사용하지 않는다. VS Code 신뢰 설정은 바꾸지 않는다.

## 생성

랩 하나를 고치면 그 랩의 생성기 하나만 돌리고(아래 표), 이어서 시작 도구를 묶고 검사한다. 다른 랩 ZIP은 다시 만들지 않는다.

```powershell
python workspace/강의제작/제작도구/실습시작/<표의 생성기>     # 폴더만 고쳤으면 lab_package.py <랩 폴더> --version <새 판>
python workspace/강의제작/제작도구/실습시작/build_launcher.py [--base-url <주소>]
python workspace/강의제작/제작도구/실습시작/verify_packages.py [<ZIP 또는 랩 폴더> …]
python workspace/강의제작/제작도구/실습시작/test_launcher.py
```

- 학생 ZIP은 `lab_package.py` 한 곳이 쓴다. 항목 시각을 고정하고 경로를 소문자 순서로 넣어, 같은 PC(같은 zlib)에서는 내용이 같으면 바이트도 같다 — 바뀐 랩만 `package-index.json` · `catalog.json`의 해시가 바뀐다. 이 방식 전에 묶은 ZIP은 다음에 다시 묶을 때 한 번 줄끝(CRLF→LF)과 시각 때문에 해시가 바뀐다.
- 폴더만 고친 랩은 `lab_package.py <랩 폴더> --version <새 판>`으로 그 ZIP과 목록 항목 하나만 고친다(생성기의 다른 변경이 딸려 오지 않는다). 새 ZIP이 `verify_packages.check_zip`을 통과할 때만 바꿔 끼우고, 바이트가 바뀌는데 판 이름이 없으면 멈춘다. START.md 랩은 `start_guides/build.py`로 묶는다.
- `verify_packages.py`는 `package-index.json`의 ZIP(해시 · 시작 파일 · 가이드 링크 · 정답 경계)과 학생 ZIP 전부(`산출물/*/실습/*/랩/*.zip` — 랩 폴더와 경로 · 바이트, 강사 대본 · 제작 지시 문구 · `.env`, ZIP 안 링크)를 본다. 결과는 `작업/검사/package-verification.json`.
- 기본 주소는 로컬 검증 서버 `http://127.0.0.1:8765`다. 공개 배포 시 패키지를 먼저 게시하고, 해당 커밋에서 `산출물/`이 바로 아래에 있는 디렉터리의 raw URL을 `build_launcher.py --base-url`에 넣어 시작 도구를 묶는다. `catalog.json`은 SHA-256으로 ZIP 판본을 확인한다. 게시 커밋과 해시는 함께 고정하고, 주소만 바꾸고 검증 없이 게시 완료로 표시하지 않는다. `launcher.py` · `실습시작.cmd` · `settings.json`은 손으로 고치는 원본이다.
- 2회차 설계 · 구현의 학생 사진은 해당 랩의 `images/`에 보존한다. 감독이 확인한 사진을 `capture-provenance.json`에 `kind: 학생 실습 화면`, 가이드의 절 이름(`section`), 설명(`caption`), 대상 · 원본 경로와 SHA-256, 잘라 쓴 경우 좌표로 등록한다. `build_labs.py`는 해당 절에 사진을 넣고 ZIP과 대조한다. 출처가 없거나 해시가 다른 사진은 그대로 보존하고 빌드를 멈춘다.

| 학생 ZIP(두 과정 합) | 생성기(`제작도구/` 기준, 이름만 있으면 이 폴더) | 지금 |
|---|---|---|
| 02회차 실습3 온톨로지설계 · 실습4 그래프구현과검증 (4) | `build_labs.py` | 같다 — 생성기 `VERSION` · `package-index.json` · `catalog.json` · ZIP이 모두 v11. 돌리면 네 랩이 함께 다시 묶인다 |
| 02회차 실습1 관계조회 · 실습2 지식지도탐색 (4) | `build_common.py [--course 과정] [--lab relations\|map]` | 같다 — 돌리면 관계조회는 Neo4j로 바로 열리는 판이 되고 두 랩의 START.md가 지워진다 |
| 실전반 02회차 실습5 조치조건표 (1) | `build_conditions.py` | 실행 불가 — `data_conditions.py:150`이 main에 없는 `plantsim.thermal.equilibrium_ts1`을 부른다 |
| 03회차 실습1 조치결과비교 (2) | `build_session3_whatif.py` | |
| 03회차 통합반 실습2 · 3, 실전반 실습2 (3) | `build_session3_judgement.py` | 실행 불가(같은 까닭) |
| 03회차 실전반 실습3 · 4 · 5 (3) | `build_session3_documents.py` | |
| 04~10회차 START.md가 있는 랩 (29) | `온라인/labs/online/start_guides/build.py <랩 폴더> …`, 검사만 `--check` | 실전반 04회차 실습2의 `코드/.env` 틀은 동기화에서 빠지므로 틀이 있는 PC에서 묶는다 |
| 통합반 04회차 실습2 · 3, 05~08회차 (18) | 없음 — START.md를 쓴 뒤 `start_guides/build.py` | ZIP에 강사 대본(`NN회차/대본/*_실습_*.md`)과 제작 안내가 들어 있다(검사 실패) |
| shift-handover — 통합반 11회차 · 실전반 08회차 (2) | `기존제작/labs/build_handover_package.py`(`안내.html`도 이것이 만든다) | ZIP 루트가 `shift-handover/`(다른 ZIP은 `NN회차/랩/<랩>/`)이고 ZIP 안 README.md가 폴더보다 옛 판이다 — 루트 형식을 정한 뒤 묶는다(`lab_package`는 다른 루트를 만나면 멈춘다) |
| 01회차 오프라인_모델과질문 (2) | 없음 — `lab_package.py` | |
| 01회차 실습1 학습노트 (2) | `촬영/notion/build.py` | 보관 — 다시 묶지 않음 |
| 01회차 실습2 실행환경 · 실습3 전체과정관찰 (4) | 없음 | 보관 — 다시 묶지 않음 |
| 01회차 실습4 관계그림 (2) | `촬영/arrows/build_ontology.py` · `build_student_guide.py`, `pack_arrows.py` | 보관 — 다시 묶지 않음. `pack_arrows.py:11-14`는 폴더의 `채울_화면.md` · `예상시간.md` 때문에 늘 멈춘다 |
| 02회차 완성본 실습3 (2) · 실습4 (2) | `build_design_solution.py --course 과정 --work <작업 폴더>` · `학생완성본/그래프구현/build_package.py <과정>` | 랩 ZIP과 따로 받는다(package-index 밖) |
| 01회차 `오프라인1_가이드.zip` (2) | `build_offline.py` · `build_guide_bundle.py --draft 작업/<작업>/오프라인1_제공물검수` | 풀고 `가이드열기.html`을 연다(정본 HTML · 참조 이미지 · 자료 · 시작 도구를 묶고 내부 링크를 확인). 지금은 검수 출력만 — 정본을 바꾸지 않는다. 시작 도구를 새로 묶은 뒤 이 묶음도 다시 본다 |

## 제공 범위

- 온라인2 설계: 원자료·규칙·요구·빈 결과 틀. 실전반에는 앞 단계 설비/센서/부품 모델이 있고 공급 연결은 학생이 작성한다.
- 온라인2 그래프: 앞 단계 완성 모델 + `lab_db.py` 환경 준비. 이번 적재·조회 로직은 제공하지 않는다.
- 오프라인1 적재: 승인 편성의 제공 절차에 따라 `offline_load.py`와 질문을 제공한다. 온라인 구현 ZIP에 넣지 않는다. 설비 3대 작은 모델(노드 44 · 관계 57, 커밋 160f846a의 `reference/통합반`에서 고정, 온라인 2회차 모델 `data_session2.py`와 별개)의 정본은 두 과정 `01일차_오프라인_모델과질문/입력/`의 `graph.json` · `schema.json`이다.
- 실전반 조건표: 기존 원문·사례·입력틀, 학생용 START·가이드. 결과 조건표와 판단 기록은 학생이 작성한다.
- `reference/`와 `verify_reference.py`는 강사 제작용이며 학생 ZIP 밖에 둔다. 학생 ZIP 하나로 장난감 시험(코딩랩.md K요-14)을 돌리는 도구는 `reference/ai_toy_test.py`다(쓰는 법은 그 파일 머리).

## 실행과 촬영의 구분

`lab_db.py`는 폴더별 새 컨테이너와 자동 배정된 루프백 포트를 사용한다. `랩_연결.json`의 ID와 컨테이너 라벨이 일치할 때만 재사용한다. 포털 DB에 접속하지 않는다. 이미지 최초 다운로드·Docker 기동·학교 네트워크는 별도 조건이다. `NEO4J_AUTH=none`은 새 로컬 교육 컨테이너에만 적용하며 외부 주소에 바인딩하지 않는다.

실행 근거와 미확인은 제작·검증 근거를 따른다. Python 함수·DB 검증과 학생 AI 수행, 데스크톱 화면 확인, 음성 포함 영상 완성은 서로 다른 판정이다.
