@echo off
rem 실습 프로그램 6개를 버전과 관계없이 기존 설치 유지, 없는 것만 설치(1~6번. Arduino IDE 제외, XG5000은 직접) - 더블클릭. 관리자 권한을 물은 뒤 scripts\install_windows.ps1을 실행한다(없는 것만 winget으로 설치).
chcp 65001 >nul
cd /d "%~dp0"
net session >nul 2>&1
if errorlevel 1 (
  echo 관리자 권한이 필요합니다. 묻는 창이 뜨면 「예」를 누르세요.
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install_windows.ps1"
