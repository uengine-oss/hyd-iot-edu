// 실전 2회차 08편(그래프 구현과 검증): 녹화 밖 상태 맞춤 — p208-01 시작 화면을 만든다(녹화하지 않는다).
// 부르기: ego-browser nodejs -e "await import('file:///<이 파일>?<판>')" < /dev/null
// 하는 일은 lab-common.mjs의 resetLab(LABS의 촬영 폴더 열기 · 신뢰 · 터미널 닫기 · README.md 하나 · 폴더 접기 · output/ · 실행 캐시 지우기, 이 폴더의 랩 DB가 있으면 그 컨테이너 하나를 볼륨과 함께 지우기).
// 원자료 · app/features · AGENTS.md · README.md는 건드리지 않는다. 학생 파일을 바꾼 구간 뒤에는 쓰지 않는다(그때는 ZIP을 새로 푼다).
const {resetLab} = await import('./lab-common.mjs');
await resetLab('p208');
