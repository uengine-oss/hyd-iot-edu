@echo off
rem 실습 스택 점검 - 더블클릭(시작.bat이 「완료」된 뒤). 서비스 응답 · 쿨러 사건 한 바퀴 · 5회차 실습 중계 서버 연결을 자동으로 확인한다(scripts\check_windows.ps1).
chcp 65001 >nul
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\check_windows.ps1"
