@echo off
rem 강사 AI 응답 저장(영상 녹화 아님) - 더블클릭. 온라인(키 없는) 학생이 받을 AI 단계 결과를 실제 AI로 한 바퀴 진행하며 저장한다(scripts\record_replay.sh).
chcp 65001 >nul
cd /d "%~dp0"
setlocal
set "GITBASH="
for %%B in ("%ProgramFiles%\Git\bin\bash.exe" "%ProgramFiles(x86)%\Git\bin\bash.exe" "%LOCALAPPDATA%\Programs\Git\bin\bash.exe") do if exist "%%~B" set "GITBASH=%%~B"
if not defined GITBASH for /f "delims=" %%G in ('where git.exe 2^>nul') do if exist "%%~dpG..\bin\bash.exe" set "GITBASH=%%~dpG..\bin\bash.exe"
if not defined GITBASH (
  echo Git Bash를 찾지 못했습니다. 설치.bat으로 Git for Windows 설치를 확인하세요.
  pause
  exit /b 1
)
"%GITBASH%" scripts/record_replay.sh %*
set "HYD_EXIT=%ERRORLEVEL%"
echo.
pause
exit /b %HYD_EXIT%
