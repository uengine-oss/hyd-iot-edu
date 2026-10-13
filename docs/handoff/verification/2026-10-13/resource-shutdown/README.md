# HYD 리소스 정지 — 2026-10-13

사용자 요청 ‘리소스 다 내리셈’에 따라 HYD/Supabase 컨테이너 29개를 정지했다. 앱을 먼저 정지한 뒤 데이터 서비스를 정지했고, 실행 컨테이너 0을 확인한 뒤 Docker Desktop도 종료했다. Windows 관련 프로세스 0, 포털8080/8088·워커8097/8098·DB54322/55757 수신 포트0, 실행 중 WSL 배포판0이다.

컨테이너·이미지·데이터 볼륨·키 파일·작업 트리는 삭제하지 않았다. 다른 프로젝트 실행 컨테이너는 없었고 본인 LIVE_LOCK은 해제했다. 실제 상태는 [최종 확인](verified-result.json)과 [Windows 독립 확인](native-proof.json)이다.

Docker Desktop 종료 명령은 성공했지만 이어서 CLI status는 Desktop이 없어 조회할 수 없다고 반환했다. 첫 검사 결과를 [원본](initial-cli-status-result.json)으로 보존했다. 정상 종료를 다시 실행하거나 status 검사를 무시하지 않고 Windows 프로세스·수신 포트·실행 WSL 부재로 최종 종료를 확인했다.

이전 포털 배포 기록의 healthy/29개 실행은 정지 전 상태다. 현재 포털은 열리지 않으며 재개할 때 NOW.md 2절을 따른다. Docker Desktop과 스택을 자동 재기동하지 않는다.
