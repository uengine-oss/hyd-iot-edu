"""학생 화면으로 가는 글에 있으면 안 되는 말 — 한 곳. 화면 순회(test_portal_ui.py)와 서버 응답 · 처리 기록을 훑는 시험(test_student_words.py ·
test_ai_replay.py · test_decide.py)이 이 표를 함께 쓴다. 소스 글자를 찾는 데 쓰지 않는다 — 실제 응답 · 실제 처리 기록 · 실제 화면의 글만 댄다.

  JARGON       내부어(설정 이름 · 영문 경보 코드 · 표 이름 · 사람 원래 id · 실행기 제품 이름) — UIUX_PLAN 2절
  WORKER_TALK  작업자끼리 쓰는 말(CLAUDE.md 5절 · 요청문 인수조건 18 · 23). 재생 모드의 안내 「AI 키가 없을 때 쓰는 재생 모드에서는 …」의
               「재생 모드」는 계약이 정한 말이라 여기 없다. 「수업」 · 「실습」은 대상을 말하지 않는 말이라 넣는다(가상 설비 3기에만 되는 것은
               「가상 설비 3기에 적용됩니다」 꼴로 말한다). 「PBL 단계」처럼 단계 정책(course_policy)이 내는 말은 그 담당의 몫이라 넣지 않았다.
"""
import re

JARGON = re.compile(r'(AI_MODE|AGENT_BRIDGE|PROCESS_MODE|LLM_API_KEY|RunFailed|Traceback|\.env\b|tenants\.mcp|tenant_\w+|is_agent|users 표|'
                    r'Claude Code|Inbucket|provenance|API 키|undefined|NaN|\[object Object\]|\bnull\b|'
                    r'COOLER_DEGRADATION|PUMP_LEAKAGE|FAN_VIBRATION|OIL_ANALYSIS|PM_DUE|SPARE_BELOW_MIN|HTTP \d{3}|status \d{3}|설비 시간 배율|'
                    r'\buser:[a-z]|\b(?:sys|inst|td|proc|nav|trace|inc|dec|kn|plant|main)\.[A-Za-z가-힣]|워커|폴링|기동 시드|프로세스 id|흐름 id|인스턴스|CANCELLED)')

WORKER_TALK = re.compile(r'(강사|녹화|수업|실습|시나리오 ?[ABC]\b|\bC3\b|미니판|지식 관리|REMOTE_AUTO|REMOTE_MANUAL)')
