# 실습 랩 (제작용)

학생에게 나가는 것은 `산출물/실습/`에 있고, 여기에는 그것을 만드는 데 쓰는 것을 둔다. 기준은 `문서/교재/2_기준.md` 6절, 만드는 법과 지금 상태는 `문서/교재/4_만드는_법.md` 3부에 있다.

| 무엇 | 내용 |
|---|---|
| `STRUCTURE.md` | 랩의 폴더와 이름의 틀. 모든 랩이 이 틀을 쓴다 |
| `offline/<랩>/` | 오프라인 랩의 강사용 폴더. 완성본(`solution/`), 실행 기록(`record/`), 가이드를 만드는 `build_guide.py`, 넣을 화면 목록(`screenshots.md`) |
| `offline/guide.css` | 가이드 공통 스타일 |
| `online/dayNN-M-주제/` | 온라인 실습 영상의 촬영 대본. `runsheet.json`이 원본이고 `runsheet.html`을 만든다 |
| `build_runsheet.py`, `runsheet.css` | 촬영 대본을 만드는 도구 |
| `바꾸기_전/` | 아직 새 틀로 옮기지 않은 랩 19묶음. 목록은 `바꾸기_전/README.md`. 새 틀로 옮길 때마다 여기서 뺀다 |

## 지금 있는 것

| 폴더 | 실습 |
|---|---|
| `offline/05-2-cause-agent` | 통합반 오프라인 5회차 실습 2 「설비 이상 원인을 추론하는 에이전트 직접 제작하기」(50분). 새 틀의 본보기 |
| `online/day01-1-notion` | 통합반 온라인 1일차 실습 1, Notion 학습노트(50분) |
| `online/day01-2-run-system` | 1일차 실습 2, 실행 환경(30분) |
| `online/day01-3-full-flow` | 1일차 실습 3, 포털 전체 과정(20분) |
| `online/day01-4-draw-relations` | 1일차 실습 4, 관계 그리기(30분) |
