# ego 웹 실습 촬영 예제

절차·검증 범위·설정·다른 에이전트용 요청문은 [촬영 가이드](../../../문서/교재/방법_ego_실습영상_촬영.md)에 있다.

이 폴더는 성공한 arrows 포인터 샘플에서 PC별 경로와 장면 값을 분리한 시작 예제다. 범용 녹화 프로그램이나 50분 검증 완료판이 아니다. 코드 구문 검사와 기존 캡처를 사용한 오프라인 인코딩만 확인했다. 이식판 실제 UI 실행·다른 PC 재현은 후속 확인 대상이다.

1. `recording.config.example.json`을 `recording.config.json`으로 복사한다.
2. ego 스킬로 작업 공간을 준비하고 실제 `spaceId`, `pageLabel`, 새 절대 출력 폴더를 설정한다.
3. arrows의 테스트 노드가 선택됐는지 snapshot과 화면으로 확인한다. Caption/radius의 input 순서를 확인한다. 다른 사이트에 이 입력 번호를 재사용하지 않는다.
4. `ego-browser nodejs -e "await import('file:///C:/ego-recording/record-arrows.mjs')"`를 실제 파일 위치로 바꿔 실행한다. `.mjs`는 ego 런타임용이며 일반 `node`로 직접 실행하지 않는다.
5. `node encode.cjs C:/recordings/ego-run-001 C:/tools/ffmpeg.exe`로 인코딩한다. FFmpeg 인수를 생략하면 PATH의 `ffmpeg`를 사용한다.
6. `arrows-ego-smooth-test.mp4`와 `report.json`을 확인한다. 완료 후 에이전트가 현재 작업 공간을 `finish({keep:[page.label]})`로 정리한다. 사용자 소유의 다른 탭은 닫지 않는다.

`frames.jsonl`은 중간 기록 보존용이다. 정상 종료 시 `smooth-timing.json`이 생성된다. 강제 종료 복구 인코더는 아직 제공하지 않는다. 입력 오류 시 후속 작업을 임의로 계속하지 않는다. 출력 폴더는 새 폴더만 허용한다.

설정 예제에는 비밀키가 없다. 실제 설정 파일은 Git 제외다. 녹화 결과는 저장소 밖 또는 로컬 `.evidence`에 둔다.
