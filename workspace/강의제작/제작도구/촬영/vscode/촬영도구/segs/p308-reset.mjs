// 실전 3회차 08편(작업 확인 카드): 녹화 밖 상태 맞춤 — p308-01 시작 화면을 만든다(녹화하지 않는다).
// 부르기: ego-browser nodejs -e "await import('file:///<이 파일>?<판>')" < /dev/null
// 하는 일은 lab-common.mjs의 resetLab(LABS의 촬영 폴더 열기 · 신뢰 · 터미널 닫기 · README.md 하나 · 폴더 접기 · output/ · 실행 캐시 지우기, 이 폴더의 랩 DB 컨테이너 하나를 볼륨과 함께 지우기),
// 그리고 04구간이 고친 app/features/build_record.md를 같은 ZIP에서 다시 꺼낸다. 원자료 · 다른 학생 파일은 건드리지 않는다.
const {resetLab} = await import('./lab-common.mjs');
await resetLab('p308', {restore: ['app/features/build_record.md'], top: ['app/features/build_record.md']});   // 04가 고치고 굴려 내린다
