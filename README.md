# assets — 강의 자료 브랜치

이 브랜치는 소스 코드 · 규칙 문서와 이력을 공유하지 않는 자료 전용 브랜치다(main과 병합하지 않는다).

- 코드 · 규칙 문서 · 산출물 원고 · 영상 상태 표는 main에 있다(영상 상태 표: main `course/videos/README.md`).
- 이 브랜치에는 학생이 노션에서 여는 강의 영상과 그 자막 · 시간표 · 편집 재료(`course/videos/`), 이론 영상을 크레딧 없이 다시 만드는 음성 캐시(`제작용/기존제작/tools/video/음성_저장/`)만 둔다. 경로는 main 폴더에서 도구가 읽는 자리와 같다.
- 노션의 영상 링크는 이 브랜치 커밋의 `raw.githubusercontent.com` 주소를 가리킨다. 그래서 이력을 다시 쓰지 않는다(rebase · 강제 push · 브랜치 삭제 금지).
- main 폴더에 꺼내 쓰기: `git archive origin/assets | tar -x -C <main 폴더>` (두 자리 모두 main에서 git이 무시한다).
- 공개 저장소라 이 브랜치도 공개다. 키 · 개인 정보 · 매뉴얼 PDF(저작물)를 올리지 않는다.
