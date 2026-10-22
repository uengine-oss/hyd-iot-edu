@echo off
rem Docker Desktop, VS Code, Node.js, Git이 없거나 수업 기준보다 낮으면 설치/업데이트. 같거나 높으면 유지. Python 3.14.7 및 WSL 2.7.12.0도 포함.
chcp 65001 >nul
cd /d "%~dp0"
net session >nul 2>&1
if errorlevel 1 (
  echo 관리자 권한이 필요합니다. 묻는 창이 뜨면 「예」를 누르세요.
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install_windows.ps1"
