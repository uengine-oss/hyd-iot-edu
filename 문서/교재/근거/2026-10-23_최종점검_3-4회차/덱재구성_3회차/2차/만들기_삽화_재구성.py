"""통합반 3회차 덱 재구성(표 → 삽화)에 쓰는 새 삽화(SVG). 글자는 넣지 않는다(라벨은 덱 MD의 요소로 얹는다).

그림 조각 · 선 굵기 · 색은 같은 폴더(또는 저장소 day03/figures)의 `삽화_기본.py` · `만들기_삽화.py`에서만 가져온다.
축척은 지식 그래프 그림과 같은 1213 × 540(본문 12.13 × 5.4인치, 1인치 = 100).
사용: python 만들기_삽화_재구성.py   → 이 폴더에 SVG를 쓴다
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.dont_write_bytecode = True       # 저장소의 그림 폴더에 __pycache__를 만들지 않는다
HERE = Path(__file__).resolve().parent
REPO_FIGS = Path("/Users/uengine/agent-provider/안치윤/hyd-iot-edu/제작용/온라인/decks/integrated/day03/figures")
sys.path.insert(0, str(HERE))
sys.path.append(str(REPO_FIGS))      # 저장소 밖(스크래치)에서 돌릴 때 기존 조각을 읽는다

from 삽화_기본 import (BLUE, GREY, LIGHT, NAVY, NORM, ON, PALE, SKY, WHITE, arrow, circle, fan, g, line,  # noqa: E402
                    monitor, plc, radiator, rect, server)
from 만들기_삽화 import check_mark, cross_mark, nozzle, pump, selector  # noqa: E402

KW, KH = 1213, 540


def _svg(o: list[str]) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {KW} {KH}" width="{KW}" height="{KH}">\n'
            + "\n".join(o) + "\n</svg>\n")


# ───────────────────────── 9장: 운전 모드 셋 × 후보 두 종류 ─────────────────────────
# 위: 모드마다 선택 스위치(modes()의 selector)와 그 모드에서 설비를 움직이는 쪽(상위 시스템 · 운전 화면 · 현장 패널).
# 아래: 원격 제어 후보(팬 · 펌프)와 정비 작업지시 후보(쿨러 핀 · 세척)가 그 모드에서 남는지(체크) 빠지는지(가위표).
MODE_X = (540, 805, 1070)
MODE_W = 232
ROW_Y = (388, 484)


def modes_matrix() -> str:
    o: list[str] = []
    # 왼쪽 위: 운전 모드 스위치 자체(바늘 없이 세 자리만) — 라벨 「운전 모드 · plc_mode」를 얹는 자리
    o.append(circle(64, 66, 30, fill=WHITE, stroke=NAVY))
    for a in (-140, -90, -40):
        ra = math.radians(a)
        o.append(circle(64 + 43 * math.cos(ra), 66 + 43 * math.sin(ra), 5, fill=WHITE, stroke=NAVY, sw=2.5))
    for i, x in enumerate(MODE_X):
        case = i == 0           # 쿨러 사건 당시의 모드
        o.append(rect(x - MODE_W / 2, 8, MODE_W, 524, 14, fill=PALE if case else LIGHT,
                      stroke=SKY if case else "none", sw=2.5 if case else 0))
        o += selector(x, 64, i, ON if case else NORM, r=30)
    # 왼쪽 가운데: 체크 · 가위표의 뜻(범례) — 라벨 「후보에 남는다」 「후보에서 빠진다」를 얹는 자리
    o += check_mark(64, 196, 20) + cross_mark(64, 262, 20)
    o += g(MODE_X[0], 212, 0.68, server(0, 0, ON))
    o += g(MODE_X[1], 210, 0.68, monitor(0, 0, ON, "hmi"))
    o += g(MODE_X[2], 212, 0.68, plc(0, 0, ON))
    o.append(line(20, 326, KW - 20, 326, stroke=GREY, sw=2))
    # 줄 머리: 원격 제어(팬 · 펌프), 정비 작업지시(쿨러 핀 · 세척)
    o += fan(50, ROW_Y[0], 30, ON, rot=20, hot=True) + pump(118, ROW_Y[0], NORM, 24)
    o += radiator(14, ROW_Y[1] - 27, 70, 54, ON, fins=7, r=6) + g(124, ROW_Y[1], 0.8, nozzle(0, 0, ON))
    for i, x in enumerate(MODE_X):
        o += check_mark(x, ROW_Y[0], 28) if i == 0 else cross_mark(x, ROW_Y[0], 28)
        o += check_mark(x, ROW_Y[1], 28)
    return _svg(o)


# ───────────────────────── 27장: 결정표의 누락 · 중복 · 상충을 수직선 셋으로 ─────────────────────────
# 가로축은 조치 후 예측 유온. 55 ℃ = 520, 1 ℃ = 65(57 ℃ = 650, 58 ℃ = 715, 59 ℃ = 780, 60 ℃ = 845).
# 막대 = 규칙 한 행이 맞는 구간(연파랑 = 통과 · 경고, 회색 = 제외), 점선 칸 = 어느 행도 맞지 않는 구간,
# 축 아래 = 시험 입력(가위표 = 맞는 행 없음, 채운 원 = 두 행이 함께 맞음). 맨 아래 띠는 HYD가 잡는 것(글은 덱 라벨).
X0, X1 = 290, 1190
BAR_H, LV_GAP = 36, 4
ROWS = {"missing": 54, "dup": 225, "conflict": 396}


def _t(c: float) -> float:
    return 520 + (c - 55) * 65


def _axis(ay, ticks):
    out = [arrow([(X0, ay), (X1, ay)], NAVY, sw=4, size=14)]
    out += [line(x, ay - 10, x, ay + 10, sw=4) for x in ticks]
    return out


def _bar(ay, x0, x1, level=0, fill=PALE, stroke=NAVY, dash=None):
    top = ay - 12 - BAR_H - level * (BAR_H + LV_GAP)
    return rect(x0, top, x1 - x0, BAR_H, 9, fill=fill, stroke=stroke, sw=3.5, stroke_dasharray=dash)


def _probe(ay, x, hit_none: bool):
    out = [line(x, ay + 12, x, ay + 26, stroke=NAVY, sw=2.5, stroke_dasharray="5 5")]
    out += cross_mark(x, ay + 44, 17) if hit_none else [circle(x, ay + 44, 17, fill=SKY, sw=3.5)]
    return out


def numline_defects() -> str:
    o: list[str] = []
    a = ROWS["missing"]                         # 55 ℃ 미만: 통과 · 60 ℃ 이상: 제외 → 57 ℃는 어느 행도 맞지 않는다
    o += _axis(a, (_t(55), _t(60)))
    o += [_bar(a, X0 + 8, _t(55)), _bar(a, _t(60), X1 - 8, fill=GREY),
          _bar(a, _t(55), _t(60), fill=WHITE, stroke=BLUE, dash="9 8")]
    o += _probe(a, _t(57), True)
    for kind in ("dup", "conflict"):             # 55 ℃ 이상: 경고 · 58 ℃ 이상: 경고(중복) / 제외(상충) → 59 ℃
        a = ROWS[kind]
        if kind == "conflict":                  # 서로 다른 답이 겹치는 자리(막대 뒤에 깐다 — numline("conflict")와 같은 꼴)
            o.append(rect(_t(58) - 8, a - 12 - 2 * BAR_H - LV_GAP - 8, X1 - _t(58) + 4, 2 * BAR_H + LV_GAP + 16, 12,
                          fill=LIGHT, stroke=BLUE, sw=3.5))
        o += _axis(a, (_t(55), _t(58)))
        o += [_bar(a, _t(55), X1 - 8, level=1), _bar(a, _t(58), X1 - 8, level=0, fill=PALE if kind == "dup" else GREY)]
        o += _probe(a, _t(59), False)
    o.append(rect(20, 466, KW - 40, 70, 12, fill=LIGHT, stroke="none", sw=0))
    return _svg(o)


def main():
    out = {"운전모드_후보.svg": modes_matrix(), "수직선_결함.svg": numline_defects()}
    for name, text in out.items():
        assert "<text" not in text
        (HERE / name).write_text(text, encoding="utf-8")
    print("wrote", ", ".join(out))


if __name__ == "__main__":
    main()
