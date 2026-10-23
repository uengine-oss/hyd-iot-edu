"""시험 전체 공통 설정.

업무 시뮬레이터(entsim/main.py)는 가져올 때 `ENTERPRISE_BACKEND`를 읽어 백엔드를 정한다. 강의 배포본 값(supabase)이 셸에
export 돼 있으면 메모리 백엔드를 전제한 시험이 실제 업무 DB를 쓴다 — 2026-10-23 점검: `/api/reset`(업무 DB 초기화)과 작업지시
생성을 부르는 시험이 있다. 시험 모듈을 가져오기 전에 메모리 백엔드로 고정한다. Supabase 백엔드 시험은 그 백엔드를 직접 만든다.
"""
import os

os.environ["ENTERPRISE_BACKEND"] = "memory"
