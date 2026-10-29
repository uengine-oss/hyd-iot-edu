@echo off
rem 실습 스택 켜기 - 더블클릭. Git for Windows의 bash로 scripts\start_all.sh를 실행한다.
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
"%GITBASH%" scripts/start_all.sh
set "HYD_EXIT=%ERRORLEVEL%"
echo.
pause
exit /b %HYD_EXIT%
