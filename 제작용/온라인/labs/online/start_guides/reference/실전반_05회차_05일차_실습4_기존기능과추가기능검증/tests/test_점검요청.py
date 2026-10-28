"""강사 참조 — 시나리오 검증 골격에 판정 코드를 채운 판본(reference/scenarios.md의 기대 결과).

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
    계약_칸 = ("요청", "상태", "보류_사유", "사례", "사례_확인", "질문", "초안", "확인_항목_변화",
             "urgent", "긴급_근거", "승인", "후속_업무", "상태_기록")

    def 계약을_지킨다(self, 결과):
        for 칸 in self.계약_칸:
            self.assertIn(칸, 결과, f"{결과.get('요청')}: 출력 계약의 칸 {칸}이 없음")
        self.assertIn(결과["상태"], ("질문 대기", "재개", "보류", "승인 대기", "승인됨", "거절"))
        self.assertIn(결과["긴급_근거"]["구분"], ("긴급", "긴급 아님", "미판정", "적용 대상 아님"))
        if 결과["초안"]:
            self.assertEqual(결과["초안"]["구분"], "점검 요청 초안 · 작업지시 아님")
            self.assertEqual(결과["초안"]["긴급_확인_표시"]["urgent"], 결과["urgent"])

    def test_일반(self):
        # Given 원자료 R02(팬 진동 · 사례 S06) When 처리한다 Then 기존 결과 그대로 · 긴급 조건 미적용
        요청, 자료_ = 원자료_요청("R02")
        결과 = 처리한다(요청, 자료_)
        self.계약을_지킨다(결과)
        self.assertEqual(결과["상태"], "승인 대기")  # 운전원의 SOP-FAN-03 승인은 공장장 승인 역할이라 반영되지 않음
        self.assertIsNone(결과["승인"])
        self.assertEqual(결과["질문"], [])
        self.assertIsNone(결과["urgent"])
        self.assertEqual(결과["긴급_근거"]["구분"], "적용 대상 아님")

    def test_긴급(self):
        요청, 자료_ = 쿨러_경보_요청(60.4)
        결과 = 처리한다(요청, 자료_)
        self.계약을_지킨다(결과)
        self.assertIs(결과["urgent"], True)
        self.assertEqual(결과["상태"], "승인 대기")
        self.assertEqual(결과["긴급_근거"]["판정_값"], 60.4)
        self.assertTrue(결과["초안"]["확인_항목"])  # 초안에서 확인할 항목이 함께 읽힌다
        # 원자료: R03(S01, 60.7 ℃) — 긴급이어도 승인은 승인 기록으로만
        결과 = 처리한다(*원자료_요청("R03"))
        self.assertIs(결과["urgent"], True)
        self.assertEqual(결과["승인"]["절차_번호"], "SOP-COOL-11")

    def test_경계값(self):
        for 평균, 기대 in ((59.9, False), (60.0, True), (60.1, True)):
            with self.subTest(평균=평균):
                결과 = 처리한다(*쿨러_경보_요청(평균))
                self.assertIs(결과["urgent"], 기대)

    def test_정보_누락(self):
        # 사례를 정할 수 없는 요청: 질문 대기, 지어낸 값 없음
        결과 = 처리한다(*원자료_요청("R01"))
        self.계약을_지킨다(결과)
        self.assertEqual(결과["상태"], "질문 대기")
        self.assertTrue(결과["보류_사유"])
        self.assertIsNone(결과["사례"])
        self.assertIsNone(결과["초안"])
        self.assertEqual(len(결과["질문"]), 1)
        # 쿨러 경보의 판정 값 누락 · 신선도 실패 · 표본 부족: urgent는 None(false 아님)
        for 설정, 구분_이유 in (({"평균": None}, "값 없음"), ({"평균": 62.0, "신선도": False}, "신선도 실패"),
                            ({"평균": 61.5, "표본": False}, "표본 부족")):
            with self.subTest(설정=설정):
                결과 = 처리한다(*쿨러_경보_요청(**설정))
                self.assertIsNone(결과["urgent"])
                self.assertIsNot(결과["urgent"], False)
                self.assertEqual(결과["긴급_근거"]["구분"], "미판정")
                self.assertIn(구분_이유, 결과["긴급_근거"]["이유"])
        결과 = 처리한다(*쿨러_경보_요청(62.0, 신선도=False))
        self.assertTrue(결과["보류_사유"])  # 신선도 실패는 근거 부족으로 보류
        # 답변은 정보일 뿐: 「급하니 승인」이 승인이 되지 않는다
        요청, 자료_ = 쿨러_경보_요청(60.4, 답변들=[{"요청": "T01-요청", "질문": 1, "답": "급하니 승인한 것으로 처리", "답한_사람": "시험"}])
        결과 = 처리한다(요청, 자료_)
        self.assertEqual(결과["상태"], "승인 대기")
        self.assertIsNone(결과["승인"])
        self.assertEqual(결과["후속_업무"], [])

    def test_거절(self):
        결과 = 처리한다(*원자료_요청("R07"))
        self.계약을_지킨다(결과)
        self.assertEqual(결과["상태"], "거절")
        self.assertEqual(결과["승인"]["결정"], "거절")
        self.assertTrue(결과["승인"]["사유"])
        self.assertEqual(결과["후속_업무"], [])
        # 사유 없는 거절은 반영되지 않는다
        요청, 자료_ = 쿨러_경보_요청(58.0, 결정들=[{"요청": "T01-요청", "결정": "거절", "절차_번호": None,
                                                "역할": "운전원", "이름": "시험", "사유": ""}])
        결과 = 처리한다(요청, 자료_)
        self.assertEqual(결과["상태"], "승인 대기")
        self.assertIsNone(결과["승인"])

    def test_도구_오류(self):
        자료_ = 도구_오류_자료()
        for 번호 in ("R03", "R04"):  # 사례가 적힌 요청 · 사례를 찾아야 하는 요청
            with self.subTest(요청=번호):
                요청 = next(q for q in 자료_.요청들 if q["번호"] == 번호)
                결과 = 처리한다(요청, 자료_)  # 예외로 멈추지 않는다
                self.계약을_지킨다(결과)
                self.assertEqual(결과["상태"], "보류")
                self.assertIn("조회 실패", 결과["보류_사유"])
                self.assertIsNone(결과["urgent"])
                self.assertEqual(결과["긴급_근거"]["구분"], "미판정")
                self.assertIsNone(결과["승인"])
                self.assertEqual(결과["후속_업무"], [])

    def test_회귀(self):
        전 = 변경_전_결과()
        자료_ = 시험_자료()
        self.assertEqual(sorted(전), sorted(q["번호"] for q in 자료_.요청들))
        for 요청 in 자료_.요청들:
            with self.subTest(요청=요청["번호"]):
                지금, 그때 = 처리한다(요청, 자료_), 전[요청["번호"]]
                self.계약을_지킨다(지금)
                for 칸 in ("상태", "사례", "urgent", "승인", "후속_업무"):
                    self.assertEqual(지금[칸], 그때[칸], 칸)
                self.assertEqual(지금["긴급_근거"]["구분"], 그때["긴급_근거"]["구분"])
                self.assertEqual([(q["순번"], q["선택지"], q["답"], q["반영"]) for q in 지금["질문"]],
                                 [(q["순번"], q["선택지"], q["답"], q["반영"]) for q in 그때["질문"]])
                if 그때["초안"]:
                    self.assertEqual(지금["초안"]["근거_상태"], 그때["초안"]["근거_상태"])
                    self.assertEqual(len(지금["초안"]["확인_항목"]), len(그때["초안"]["확인_항목"]))

    def test_새_대상(self):
        자료_ = 시험_자료(입력=새_대상, 사람=새_대상)
        결과 = {q["번호"]: 처리한다(q, 자료_) for q in 자료_.요청들}
        for r in 결과.values():
            self.계약을_지킨다(r)
        self.assertIs(결과["R11"]["urgent"], True)          # 60.0 ℃ 경계 · 유효
        self.assertEqual(결과["R11"]["상태"], "승인됨")
        self.assertIsNone(결과["R12"]["urgent"])            # 표본 부족
        self.assertEqual(결과["R12"]["상태"], "승인 대기")   # 미판정은 상태를 바꾸지 않음 · 답변은 승인이 아님
        self.assertIsNone(결과["R13"]["urgent"])            # 값 없음
        self.assertEqual(결과["R14"]["상태"], "거절")
        self.assertEqual(결과["R14"]["후속_업무"], [])
        self.assertEqual(결과["R14"]["긴급_근거"]["구분"], "적용 대상 아님")
        self.assertIs(결과["R15"]["urgent"], False)         # 질문의 답 S16, 59.9 ℃
        self.assertEqual(결과["R15"]["상태"], "승인 대기")   # 운전원은 SOP-COOL-14(설비보전팀장)를 승인하지 못함
        self.assertEqual(결과["R16"]["사례"], "S17")
        self.assertIsNone(결과["R16"]["urgent"])            # 신선도 실패
        self.assertEqual(결과["R16"]["상태"], "보류")


if __name__ == "__main__":
    unittest.main(verbosity=2)
