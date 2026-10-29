# workspace — 작업 자료 브랜치

학생이 받는 코드는 main 브랜치다. 이 브랜치는 강의를 만들고 시스템을 고치는 사람이 쓰는 작업 자료 전부다.

- 어디부터: [workspace/README.md](workspace/README.md) — 하려는 일 → 읽을 문서 하나.
- 받기(새 PC, main을 clone한 폴더에서, Git Bash): `git fetch origin workspace` → `git show origin/workspace:workspace/동기화.py > 동기화.py` → `python 동기화.py pull` → `rm 동기화.py`.
  PowerShell의 `>`는 인코딩을 바꿀 수 있어 쓰지 않는다.
- 경로는 저장소 루트 기준 그대로다. main과 병합하지 않는다. 이력을 다시 쓰지 않는다(노션 영상 링크가 이 브랜치 커밋을 가리킨다).
- 공개 저장소다. 키 · 개인 정보 · 실물 매뉴얼 PDF를 올리지 않는다.
