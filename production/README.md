# production — 제작용

교육 산출물([`course/`](../course/README.md))을 만드는 데 쓰는 것을 모았다. 수업에는 쓰지 않는다. 기준과 인계 문서, 사실표, 실라버스는 [`문서/교재/`](../문서/교재/1_목적과_방향.md)에 있다.

| 폴더 | 내용 |
|---|---|
| `decks/` | 덱 원고(MD), 그림, 조립 스크립트. 통합반 대본의 원문과 1차 윤문본, 검사 기록도 일차 폴더에 함께 있다. 안내는 `decks/README.md` |
| `labs/` | 랩의 틀(`STRUCTURE.md`), 랩마다의 완성본 · 실행 기록 · 가이드 생성 도구(`offline/`), 온라인 실습 영상의 촬영 대본(`online/`, `build_runsheet.py`), 아직 새 틀로 옮기지 않은 랩 열아홉 묶음(`바꾸기_전/`). 안내는 `labs/README.md` |
| `tools/deck/` | 대본 시간 계산, 시트 변환, 노션 덱 스타일 맞춤 |
| `tools/video/` | 강의 영상(`강의영상.py`), 대본 윤문(`윤문.py`, `윤문2.py`), 장마다 쉴 자리(`쉼_저장/`) |
| `dist/` | 덱 38개를 과정별로 묶은 배포용 zip |

## 폴더 이름

| 과정 | 폴더 | 단위 |
|---|---|---|
| 통합반 온라인 | `integrated` | `day01` … `day11` |
| 실전반 온라인 | `practical` | `day01` … `day08` |
| 통합반 오프라인 | `integrated-offline` | `session01` … `session10` |
| 실전반 오프라인 | `practical-offline` | `session01` … `session09` |

폴더는 영어로, 덱 · 대본 · 원고의 파일 이름은 한글(`통합반_05일차.md`)로 둔다. 그림 폴더는 `figures/`다.

## 산출물이 나오는 곳

| 만드는 것 | 원고 | 도구 | 나오는 곳 |
|---|---|---|---|
| 덱 PPTX | `decks/<과정>/<단위>/…md` | `.claude/skills/hyd-course-deck/scripts/재조립.py --build` | `course/slides/<과정>/` |
| 조립 덱의 원고 | 통합반 원고 + `새장_….md` | 각 폴더의 `조립.py` | 같은 폴더의 `…md` |
| 최종 대본 | `course/scripts/integrated/…_윤문2.md`를 직접 고친다 | 고친 문단만 모아 한 번 윤문한다(`문서/교재/4_만드는_법.md` 3부 2절) | `course/scripts/integrated/` |
| 실습 촬영 대본 | `labs/online/<폴더>/runsheet.json` | `labs/build_runsheet.py` | 같은 폴더의 `runsheet.html` |
| 강의 영상 | `course/scripts/` + `course/slides/` | `tools/video/강의영상.py` | 저장소 밖 |
| 랩 가이드 | `labs/offline/<랩>/build_guide.py` | 같은 파일 | `course/labs/offline/<랩>/guide.html` |
| 배포 zip | `course/slides/` | `.claude/skills/hyd-course-deck/scripts/배포묶음.py` | `dist/교재_전체.zip` |
