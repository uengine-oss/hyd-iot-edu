@echo off
rem Docker Desktop, VS Code, Node.js, Git, Python, WSL이 없거나 수업 기준(scripts\versions.txt)보다 낮으면 설치/업데이트. 같거나 높으면 유지.
chcp 65001 >nul
cd /d "%~dp0.."
net session >nul 2>&1
if errorlevel 1 (
  echo 관리자 권한이 필요합니다. 묻는 창이 뜨면 「예」를 누르세요.
  powershell -NoProfile -Command "try { Start-Process -FilePath '%~f0' -Verb RunAs -ErrorAction Stop } catch { exit 1 }"
  if errorlevel 1 (
    echo.
    echo 관리자 승인을 받지 못해 설치를 시작하지 않았습니다. 설치.bat을 다시 실행하고 묻는 창에서 「예」를 누르세요.
    pause
    exit /b 1
  )
  exit /b
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\scripts\install_windows.ps1"
