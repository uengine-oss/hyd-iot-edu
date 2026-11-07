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

from 삽화_기본 import BLUE, LIGHT, NAVY, SKY, WHITE, circle, dots, rect  # noqa: E402

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


def main() -> None:
    (HERE / '감산별_완료시점.svg').write_text(finish_time(), encoding='utf-8')


if __name__ == '__main__':
    main()
