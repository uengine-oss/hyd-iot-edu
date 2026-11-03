"""실전반 3회차 덱의 새 삽화(SVG). 글자는 넣지 않는다(라벨은 덱 MD의 요소로 얹는다).

그림 조각 · 선 굵기 · 색은 통합반 3회차 figures의 `삽화_기본.py` · `만들기_삽화.py`에서만 가져온다(그 파일은 고치지 않는다).
사용: python 만들기_삽화.py   → 이 폴더에 SVG를 쓴다
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.dont_write_bytecode = True       # 저장소의 그림 폴더에 __pycache__를 만들지 않는다
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / 'integrated' / 'day03' / 'figures'))

from 삽화_기본 import BLUE, LIGHT, NAVY, PALE, SKY, WHITE, arrow, circle, dots, line, rect  # noqa: E402
from 만들기_삽화 import check_mark, cross_mark  # noqa: E402

KW, KH = 1213, 540


def _svg(o: list[str]) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {KW} {KH}" width="{KW}" height="{KH}">\n'
            + "\n".join(o) + "\n</svg>\n")


# ───────────────── 감산과 정지가 납기를 넘기는 계산 ─────────────────
# 값: 남은 1,500 ea · 시간당 300 ea · 설계 부하 90 % · 납기까지 5.98 h · 핀 세척 정지 3 h (it/agent/agentsvc/whatif.py card_money, ent.* 시드).
T0, PX = 250, 112          # 0 h의 x, 1 h의 픽셀
DUE = 5.98
ROWS = ((98, 0, 5.00), (222, 0, 1500 / (300 * 80 / 90)), (346, 0, 1500 / (300 * 70 / 90)), (470, 3.0, 8.00))
BAR_H = 38


def x_of(h: float) -> float:
    return T0 + PX * h


def finish_time() -> str:
    o: list[str] = []
    for y, stop, end in ROWS:
        if stop:      # 정지 구간: 생산하지 않는 시간
            o.append(rect(T0, y - BAR_H / 2, PX * stop, BAR_H, 10, fill=LIGHT, stroke=NAVY, sw=3.5))
        a = x_of(stop)
        b = min(x_of(end), x_of(DUE))
        o.append(rect(a, y - BAR_H / 2, b - a, BAR_H, 10, fill=SKY, stroke=BLUE, sw=3.5))
        if end > DUE:     # 납기를 넘긴 구간
            o.append(rect(x_of(DUE), y - BAR_H / 2, x_of(end) - x_of(DUE), BAR_H, 8, fill=NAVY, stroke=NAVY, sw=3.5))
        o.append(circle(x_of(end), y, 10, fill=WHITE, stroke=NAVY if end > DUE else BLUE, sw=3.5))
    o += dots(x_of(DUE), 44, x_of(DUE), 510, color=NAVY, gap=15, r=3.4)
    return _svg(o)


# ───────────────── 충돌 직전까지 남겼을 때와 전체 취소 ─────────────────
CHIPS = ((462, True), (632, True), (802, False), (972, False))
CHIP_W, CHIP_H = 150, 70


def _empty(x: float, y: float, w: float, h: float) -> list[str]:
    o = dots(x, y, x + w, y, color=NAVY, gap=14, r=2.6)
    o += dots(x, y + h, x + w, y + h, color=NAVY, gap=14, r=2.6)
    o += dots(x, y, x, y + h, color=NAVY, gap=14, r=2.6)
    o += dots(x + w, y, x + w, y + h, color=NAVY, gap=14, r=2.6)
    return o


def partial_or_cancel() -> str:
    o: list[str] = []
    # 왼쪽: 이번 묶음 — 네 칸이 모두 찬 상자
    o.append(rect(30, 120, 200, 300, 16, fill=LIGHT, stroke=NAVY, sw=4))
    for i in range(4):
        o.append(rect(48, 178 + i * 57, 164, 48, 8, fill=SKY if i < 2 else PALE, stroke=BLUE, sw=3))
    # 가운데: 충돌을 발견한 지점에서 두 갈래
    o.append(line(230, 270, 340, 270, stroke=NAVY, sw=4))
    o.append(circle(352, 270, 12, fill=BLUE, stroke=NAVY, sw=3.5))
    o.append(arrow([(364, 270), (418, 270), (418, 150), (436, 150)], NAVY, 4))
    o.append(arrow([(418, 270), (418, 410), (436, 410)], BLUE, 4))
    # 오른쪽 위: 일부만 남긴 상태 — 앞 두 칸만 차고 뒤 두 칸은 비었다
    o.append(rect(438, 28, 748, 214, 16, fill=WHITE, stroke=NAVY, sw=4))
    y = 112
    for x, full in CHIPS:
        if full:
            o.append(rect(x, y, CHIP_W, CHIP_H, 10, fill=SKY, stroke=BLUE, sw=3.5))
        else:
            o += _empty(x, y, CHIP_W, CHIP_H)
            o += cross_mark(x + CHIP_W / 2, y + CHIP_H + 32, 15)
    # 오른쪽 아래: 전체 취소 — 이번 묶음은 없고 기존 지식은 그대로
    o.append(rect(438, 298, 748, 214, 16, fill=PALE, stroke=BLUE, sw=4))
    o.append(rect(462, 382, 660, 70, 10, fill=WHITE, stroke=BLUE, sw=3.5))
    o += check_mark(1152, 417, 18)
    return _svg(o)


def main() -> None:
    (HERE / '감산별_완료시점.svg').write_text(finish_time(), encoding='utf-8')
    (HERE / '일부반영과_전체취소.svg').write_text(partial_or_cancel(), encoding='utf-8')


if __name__ == '__main__':
    main()
