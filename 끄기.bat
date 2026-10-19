@echo off
rem 실습 스택 끄기 - 더블클릭. 데이터는 지우지 않는다.
chcp 65001 >nul
cd /d "%~dp0"
set "GITBASH=%ProgramFiles%\Git\bin\bash.exe"
if not exist "%GITBASH%" set "GITBASH=%ProgramFiles(x86)%\Git\bin\bash.exe"
if not exist "%GITBASH%" (
  echo Git for Windows가 없습니다.
  pause
  exit /b 1
)
"%GITBASH%" scripts/stop_all.sh
echo.
pause
