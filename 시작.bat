@echo off
rem 실습 스택 켜기 - 더블클릭. Git for Windows의 bash로 scripts\start_all.sh를 실행한다.
chcp 65001 >nul
cd /d "%~dp0"
set "GITBASH=%ProgramFiles%\Git\bin\bash.exe"
if not exist "%GITBASH%" set "GITBASH=%ProgramFiles(x86)%\Git\bin\bash.exe"
if not exist "%GITBASH%" (
  echo Git for Windows가 없습니다. 설치 목록의 Git을 설치한 뒤 다시 실행하세요.
  pause
  exit /b 1
)
"%GITBASH%" scripts/start_all.sh
echo.
pause
