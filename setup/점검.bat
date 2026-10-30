@echo off
rem 실습 스택 점검 - 더블클릭(시작.bat이 「완료」된 뒤). 서비스 응답 · 쿨러 사건 한 바퀴(승인 뒤 실행까지) · 강의 중계 연결을 자동으로 확인한다(scripts\check_all.sh).
chcp 65001 >nul
cd /d "%~dp0.."
setlocal
set "GITBASH="
for %%B in ("%ProgramFiles%\Git\bin\bash.exe" "%ProgramFiles(x86)%\Git\bin\bash.exe" "%LOCALAPPDATA%\Programs\Git\bin\bash.exe") do if exist "%%~B" set "GITBASH=%%~B"
if not defined GITBASH for /f "delims=" %%G in ('where git.exe 2^>nul') do if exist "%%~dpG..\bin\bash.exe" set "GITBASH=%%~dpG..\bin\bash.exe"
if not defined GITBASH (
  echo Git Bash를 찾지 못했습니다. 설치.bat으로 Git for Windows 설치를 확인하세요.
  pause
  exit /b 1
)
"%GITBASH%" scripts/check_all.sh
set "HYD_EXIT=%ERRORLEVEL%"
echo.
pause
exit /b %HYD_EXIT%
