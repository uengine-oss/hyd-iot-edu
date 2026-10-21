@echo off
rem Docker Desktop, VS Code, Node.js, Git만 없는 경우 설치. Python과 WSL은 설치하지 않는다. 기존 프로그램은 버전과 관계없이 유지한다.
chcp 65001 >nul
cd /d "%~dp0"
net session >nul 2>&1
if errorlevel 1 (
  echo 관리자 권한이 필요합니다. 묻는 창이 뜨면 「예」를 누르세요.
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install_windows.ps1"
