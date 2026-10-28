"""제공 빈 틀 — 점검 요청 기능의 시나리오 검증 골격.

`코드/output/scenarios.md`에 실행 전에 적은 기대 결과를 시험마다 단언(assert)으로 옮깁니다.
판정 코드를 쓰지 않은 시험은 「미구현」으로 실패합니다. 시험을 더 나누거나 이름을 바꿔도 됩니다.

랩 폴더(START.md가 있는 폴더)에서 실행합니다. pytest가 없어도 됩니다.

    python 코드/output/tests/test_점검요청.py
    python -m unittest discover -s 코드/output/tests -v

검사하는 프로젝트는 `코드/output/점검요청/`(코드/input/점검요청을 복사해 고치는 사본)입니다.
"""
from __future__ import annotations

import copy
import json
import os
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True  # __pycache__를 만들지 않는다

랩_코드 = Path(__file__).resolve().parents[2]  # 코드/
프로젝트 = Path(os.environ.get("CHECK_PROJECT") or 랩_코드 / "output" / "점검요청")
원자료 = 랩_코드 / "source"
새_대상 = 원자료 / "새_대상"
변경_전_결과_파일 = 랩_코드 / "input" / "점검요청" / "결과" / "점검_요청.json"

if not (프로젝트 / "점검_요청.py").exists():
    raise SystemExit(f"검사할 프로젝트가 없습니다: {프로젝트} — START.md 작업 순서 1(복사)을 먼저 하세요")
sys.path.insert(0, str(프로젝트))

import 도구  # noqa: E402
import 점검_요청  # noqa: E402
from 점검_요청 import 처리한다  # noqa: E402


# ── 입력을 만드는 도우미(설정만 한다 · 판정하지 않는다) ──────────────────────

class 시험_자료(점검_요청.자료):
    """원자료를 읽은 뒤 시험용 사례 · 요청 · 답변 · 결정을 끼워 넣은 자료.
    입력=새_대상, 사람=새_대상이면 새 대상 묶음을 읽는다."""

    def __init__(self, 사례들=(), 요청들=None, 답변들=None, 결정들=None, 입력=None, 사람=None):
        super().__init__(원자료, 입력, 사람)
        self._시험_사례 = {s["번호"]: s for s in 사례들}
        if 요청들 is not None:
            self.요청들 = 요청들
        if 답변들 is not None:
            self.답변들 = 답변들
        if 결정들 is not None:
            self.결정들 = 결정들

    def 사례(self, 번호):
        return self._시험_사례.get(번호) or super().사례(번호)

    def 사례_목록(self):
        더한 = [{k: s.get(k) for k in ("번호", "설비", "경보_패턴", "판단_시각")} for s in self._시험_사례.values()]
        return super().사례_목록() + 더한


def 원자료_요청(번호, 자료_=None):
    """요청 파일에서 요청 한 건과 그 자료 → (요청, 자료). 자료를 주지 않으면 원자료(source/)."""
    자료_ = 자료_ or 시험_자료()
    return next(q for q in 자료_.요청들 if q["번호"] == 번호), 자료_


def 쿨러_경보_요청(평균, 신선도=True, 표본=True, 번호="T01", 설비="HYD-01", 답변들=None, 결정들=None):
    """원자료 S01을 본뜬 시험용 쿨러 경보 사례 한 건(TS1 120초 평균 · 신선도 · 표본만 바꿈)과
    그 사례를 적은 요청 한 건 → (요청, 자료). 평균=None이면 값 없음."""
    사례 = copy.deepcopy(점검_요청.자료(원자료).사례("S01"))
    사례.update(번호=번호, 설비=설비)
    if not 신선도:
        사례["freshness"] = {"tag": "TS1", "age_s": 185.0, "max_age_s": 60, "ok": False}
    for r in 사례["readings"]:
        if (r["tag"], r["aggregate"], r["windowSeconds"]) == ("TS1", "avg", 120):
            r["value"] = 평균
            if not 표본:
                r["coverage"] = {"samples": 70, "max_gap_s": 9.0, "limit_s": 3, "covered": False}
    요청 = {"번호": f"{번호}-요청", "받은_시각": 사례["판단_시각"], "요청자": "시험", "요청자_역할": "운전원",
           "설비": 설비, "경보_패턴": "COOLER_DEGRADATION", "사례": 번호, "요청_글": "시험용 요청"}
    return 요청, 시험_자료([사례], 요청들=[요청], 답변들=답변들 or [], 결정들=결정들 or [])


class _조회_실패_자료(시험_자료):
    def 사례(self, 번호):
        raise 도구.조회_오류("센서 입력을 읽지 못함(시험용)")

    def 사례_목록(self):
        raise 도구.조회_오류("센서 입력을 읽지 못함(시험용)")


def 도구_오류_자료():
    """센서 사례를 물으면 도구.조회_오류를 내는 자료(센서 조회 실패를 흉내 낸다)."""
    return _조회_실패_자료()


def 변경_전_결과():
    """코드/input/점검요청/결과/점검_요청.json(고치기 전 판본의 결과) → {요청 번호: 결과}."""
    return {r["요청"]: r for r in json.loads(변경_전_결과_파일.read_text(encoding="utf-8"))}


# ── 시나리오 ─────────────────────────────────────────────────────────────
# scenarios.md의 줄마다 Given(입력 · 자료) → When(처리한다) → Then(단언)을 옮긴다.
# null은 `is None`으로 따로 검사한다.

class 시나리오(unittest.TestCase):
    def test_일반(self):
        self.fail("미구현: scenarios.md 「일반」 줄의 기대 결과를 단언으로 옮기세요")

    def test_긴급(self):
        self.fail("미구현: scenarios.md 「긴급」 줄의 기대 결과를 단언으로 옮기세요")

    def test_경계값(self):
        self.fail("미구현: scenarios.md 「경계값」 줄의 기대 결과를 단언으로 옮기세요")

    def test_정보_누락(self):
        self.fail("미구현: scenarios.md 「정보 누락」 줄의 기대 결과를 단언으로 옮기세요")

    def test_거절(self):
        self.fail("미구현: scenarios.md 「거절」 줄의 기대 결과를 단언으로 옮기세요")

    def test_도구_오류(self):
        self.fail("미구현: scenarios.md 「도구 오류」 줄의 기대 결과를 단언으로 옮기세요")

    def test_회귀(self):
        self.fail("미구현: 고친 뒤 원자료의 기존 요청이 변경 전 결과와 계약 항목에서 같은지 단언으로 옮기세요")

    def test_새_대상(self):
        self.fail("미구현: scenarios.md 「새 대상」 줄의 기대 결과를 단언으로 옮기세요")


if __name__ == "__main__":
    unittest.main(verbosity=2)
