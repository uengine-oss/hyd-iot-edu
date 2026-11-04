# 촬영 — 여러 도구 공통

규칙은 [영상](../../지침/영상.md), 도구마다의 길 · 값 · 함정은 그 도구 `촬영준비.md`. 여기는 둘 이상의 도구에 같은 것만 둔다. 새로 뚫은 길 · 함정 · 바뀐 값은 그 자리를 고쳐 쓴다(날짜 · 경위 없이).

## 길 — ego로 찍는 도구(ARROWS · Notion · Neo4j · 웹 VS Code · 포털 지식 지도)

1. 준비 — ego lite 설치 · 로그인은 사용자가 한다. 설치된 `ego-browser skill` 출력을 끝까지 읽는다(API는 설치 버전 우선). 공간은 이름으로 `taskSpace(<이름>)`(번호는 바뀐다). 다른 세션과 같은 공간 · 페이지를 함께 쓰지 않고 다른 공간으로 옮겨 다니지 않는다. ego 창을 최소화하지 않고 녹화 탭을 앞에 둔다(앞 탭에서만 프레임이 온다).
2. 시작 화면 — 1920×1080 프레임 · UI 150%가 시작값이고, 대표 화면을 실제 녹화 프레임으로 읽어 본다. 이전 시연 흔적을 정리하고(DB 데이터 삭제가 아니다) 첫 프레임을 본다. 촬영 전용 문서 · 페이지 하나에서 이어 쓰고, 재시도마다 사본을 늘리거나 최종본을 덮지 않는다. 물리 마우스 · 키보드 · 전경 창은 쓰지 않는다.
3. 스크립트 부르기 — UTF-8 `.mjs`, `node --check` 뒤 `ego-browser nodejs -e "await import('file:///<절대경로>.mjs?<판>')" < /dev/null`(같은 주소는 다시 실행되지 않아 판 표시를 바꾼다). 도구의 `run.sh`가 이것과 바쁨 검사(`BUSY:`) · 부하 검사(화상회의 · 여유 메모리 3 GB) · 시간 초과(`TMO`) 정리를 한다.
4. 녹화 — 스크립트마다 시작에서 `Emulation.setDeviceMetricsOverride`(도구 값, 한 도구 안에서 안 바꿈), `Page.startScreencast` 프레임을 받는 즉시 저장 · ACK. 리듬은 도구가 한다: 모든 ego 호출은 직렬 큐 하나, 표시 포인터(SVG를 `element.animate`)와 실제 입력(같은 경로 단계별 `mouse.move`)이 함께 가고 실제 입력이 끝날 때까지 화살표를 목표에 고정, 움직이는 대상은 150ms 간격 두 번 같은 위치일 때 출발, 조작은 행동 문장 끝 약 250ms 전, 다음 음성은 행동 종료 + 250ms.
5. 대상 찾기 — 웹 페이지(Notion · 포털 · Neo4j 입력)는 보이는 DOM 요소 · 정확한 글로 찾고 클릭 직전 위치를 다시 읽는다(화면 밖 요소를 고정 좌표로 누르지 않음). 캔버스(ARROWS · Neo4j 그래프 · bpmn.io)는 그리기 함수를 감싸 대상 위치를 기록하고, 배치 순서는 녹화 전에 계산해 큐에 고정한다.
6. 사용자와 주고받기 — 사용자가 배치 · 입력하면 녹화를 멈추고 `task.handOff()` → 사용자 → `takeOverTaskSpace(<번호>)`. 결과는 앱의 저장 데이터로 읽는다. 「Control of this task space is with the user」면 「계속」을 받은 뒤 되찾는다.
7. 상태 맞추기 — 이전 끝 상태는 저장한 `end-state.json` 데이터를 가져와 맞춘다. 실행 취소는 마지막 수단(포커스 · 글자 단위 기록 때문에 다른 내용을 잃는다).
8. 기록 — 구간마다 `end-state.json` · `timing.json`, 원본은 그 도구 `config.json`의 `work`(`작업/촬영/<도구>/`, 이 PC 전용). take는 매번 새 이름, 실패 take는 남기되 합성에 쓰지 않고, 합성 출력 이름도 새로.

## 자료

| 무엇 | 값 · 경로 |
|---|---|
| 도구 | 포털(클라우드 Playwright · 로컬 ego) [포털/](포털/촬영준비.md) · Neo4j Browser [neo4j/](neo4j/촬영준비.md) · ARROWS [arrows/](arrows/촬영준비.md) · Notion [notion/](notion/촬영준비.md) · 웹 VS Code [vscode/](vscode/촬영준비.md) · 설치 구간(사용자 원본) [환경세팅/](환경세팅/촬영준비.md). bpmn.io는 처음 찍을 때 `bpmn/촬영준비.md`를 같은 꼴(길 · 자료 · 함정)로 만든다 |
| 음성 | ElevenLabs `eleven_v4`, 「안치윤」 `1PdAOcPlPTz12RwMyFVp`, stability 0.5 · similarity_boost 0.75, `mp3_44100_128`. 캐시 `<큐 id>.mp3` · `.json`(text · duration_ms), 같은 문장은 다시 만들지 않는다 |
| 음성 키 | 포털 · Neo4j는 환경변수 `ELEVENLABS_API_KEY`, ARROWS · Notion · VS Code는 `HYD_ELEVENLABS_KEY_FILE`이 가리키는 파일(Git Bash `export HYD_ELEVENLABS_KEY_FILE='<키 파일 경로>'`). 값을 찍거나 남기지 않는다 |
| 시간 | [시간계산.py](시간계산.py) `estimate <큐>` · [시간계수.json](시간계수.json) |
| 검사 · 잇기 | [포털/촬영도구/](포털/촬영도구/)의 `verify.py` · `scenes.py` · `listen.py` · `join.py` · `cut.py` — 어느 도구 영상에나 쓴다 |
| ffmpeg(이 PC) | PATH에 없다 — `FFMPEG="$(python -c 'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())')"` 또는 `CLAUDE.md` 6절의 WinGet 경로 |

## 함정

- 명령이 출력 없이 멈춤 → 끊어도 스크립트는 ego `NodeService`에서 계속 돈다. 그 utility 프로세스만 끄고(창 · 탭 유지) 실제로 실행됐는지 앱 상태로 본다.
- 스크립트가 조용히 멈춤 · 고친 파일 미반영 · 셸 안에서만 멈춤 → 문법 오류(`node --check`) · 같은 `file:///` 주소 · stdin 대기(`< /dev/null`).
- 해상도 · 배율이 다음 호출에서 풀림 → 모든 스크립트 시작에서 metrics. 1080p인데 글자가 작음 → UI 배율 · 대상 확대 · 패널 폭을 고친다(압축 품질 문제가 아니다).
- 이동 중 프레임 공백 · 휘청 → 큐 점유 · 녹화 중 무거운 작업 · CPU 경쟁을 본다. fps · 복제 프레임으로 숨기지 않는다.
- 1~2초 정지 · 시간 초과가 갑자기 반복 → 화상회의 · 메모리 부족. 멈추고 부하가 사라진 뒤 멈춘 큐부터.
- 앞 구간 실패인데 다음 구간이 돎 → 연속은 실패하면 멈추는 `chain.sh`로만.
- 합성 영상이 내레이션보다 짧아 끝인사가 잘림 → concat 끝 줄에도 같은 framerate, 합성 뒤 끝 시각을 잰다. 보정 이미지 뒤 프레임 누락 → concat에 이미지 코덱을 섞지 않는다.
- EPERM 상태 파일 충돌 → 같은 공간 중복 실행. 사용자 클릭이 안 먹음 → 에이전트가 쥐고 있다(`handOff`).
- 시간 초과로 끊긴 명령이 ego 안에서 계속 돌아 상태를 바꿨다 → 끊은 뒤에는 저장 데이터로 상태를 확인하고 찍는다.
