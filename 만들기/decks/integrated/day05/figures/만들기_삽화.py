"""통합반 5일차 삽화(SVG)를 만든다. 글자는 넣지 않는다(라벨은 덱 MD의 요소로 얹는다).

화풍(선 굵기 · 색 · 그림 조각)은 1일차의 `만들기_삽화.py`를 복사한 `삽화_기본.py`에서 가져온다.
사용: python 만들기_삽화.py            → 이 폴더에 SVG를 쓴다
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from 삽화_기본 import (BLUE, GREY, LIGHT, NAVY, NORM, OFF, ON, PALE, SKY, WHITE, St, agent_icon,  # noqa: E402
                    approve_icon, arrow, bell, book_icon, circle, cylinder_db, dots, g, graph_icon, head, line, path,
                    poly, rect, svg)


# ───────────────────────── 작은 그림 조각 (5일차에서 새로 쓰는 것) ─────────────────────────

def doc(cx, cy, st: St, w=64, h=84, lines=5, mark=None):
    """문서 한 장. 오른쪽 위 귀가 접힌다. mark번째 줄을 강조한다."""
    x, y, f = cx - w / 2, cy - h / 2, 16
    o = [path(f"M {x},{y} L {x + w - f},{y} L {x + w},{y + f} L {x + w},{y + h} L {x},{y + h} Z", fill=st.fill, stroke=st.line),
         path(f"M {x + w - f},{y} L {x + w - f},{y + f} L {x + w},{y + f}", stroke=st.line, sw=2.5)]
    step = (h - 34) / max(lines - 1, 1)
    for i in range(lines):
        ly = y + 24 + i * step
        hot = mark is not None and i == mark
        o.append(line(x + 10, ly, x + w - (22 if i == lines - 1 else 10), ly, stroke=BLUE if hot and st is ON else st.line,
                      sw=5 if hot else 2.5))
    return o


def lock(cx, cy, st: St, s=1.0):
    return [path(f"M {cx - 9 * s},{cy - 4 * s} L {cx - 9 * s},{cy - 12 * s} A {9 * s} {9 * s} 0 0 1 {cx + 9 * s},{cy - 12 * s} L {cx + 9 * s},{cy - 4 * s}",
                 stroke=st.line, sw=3),
            rect(cx - 14 * s, cy - 4 * s, 28 * s, 22 * s, 4, fill=st.accent, stroke=st.line, sw=3),
            circle(cx, cy + 6 * s, 2.6 * s, fill=st.line, stroke=st.line, sw=1)]


def magnifier(cx, cy, st: St, r=17):
    return [circle(cx, cy, r, fill=st.fill, stroke=st.line),
            line(cx + r * 0.72, cy + r * 0.72, cx + r * 1.55, cy + r * 1.55, stroke=st.line, sw=5)]


def check_badge(cx, cy, st: St, r=17):
    return [circle(cx, cy, r, fill=st.accent, stroke=st.line),
            path(f"M {cx - r * 0.47},{cy} L {cx - r * 0.1},{cy + r * 0.38} L {cx + r * 0.52},{cy - r * 0.36}", stroke=st.line, sw=4)]


def bubble(cx, cy, st: St, w=110, h=74):
    """말풍선: 모델이 내는 글."""
    x, y = cx - w / 2, cy - h / 2
    o = [path(f"M {x + 12},{y} L {x + w - 12},{y} Q {x + w},{y} {x + w},{y + 12} L {x + w},{y + h - 12} Q {x + w},{y + h} {x + w - 12},{y + h} "
              f"L {x + 44},{y + h} L {x + 24},{y + h + 20} L {x + 26},{y + h} L {x + 12},{y + h} Q {x},{y + h} {x},{y + h - 12} "
              f"L {x},{y + 12} Q {x},{y} {x + 12},{y} Z", fill=st.fill, stroke=st.line)]
    for i, dy in enumerate((-16, 0, 16)):
        o.append(line(x + 18, cy + dy, x + w - (40 if i == 2 else 18), cy + dy, stroke=st.line, sw=3))
    return o


def table_icon(cx, cy, st: St, w=96, h=76, rows=4, cols=3, hot=None):
    """업무 DB의 표. hot = (행, 열) 한 칸을 강조한다."""
    x, y = cx - w / 2, cy - h / 2
    rh, cw = h / rows, w / cols
    o = [rect(x, y, w, h, 6, fill=st.fill, stroke=st.line), rect(x, y, w, rh, 6, fill=st.accent, stroke=st.line)]
    if hot:
        o.append(rect(x + hot[1] * cw, y + hot[0] * rh, cw, rh, 0, fill=st.soft, stroke=st.line, sw=2))
    for r_ in range(1, rows):
        o.append(line(x, y + r_ * rh, x + w, y + r_ * rh, stroke=st.line, sw=2))
    for c_ in range(1, cols):
        o.append(line(x + c_ * cw, y, x + c_ * cw, y + h, stroke=st.line, sw=2))
    return o


def wrench(cx, cy, st: St, s=1.0):
    """도구: 스패너."""
    a = math.radians(-45)
    ux, uy = math.cos(a), math.sin(a)
    hx, hy = cx + 22 * s * ux, cy + 22 * s * uy
    tx, ty = cx - 30 * s * ux, cy - 30 * s * uy
    return [line(tx, ty, hx, hy, stroke=st.line, sw=11 * s),
            line(tx, ty, hx, hy, stroke=st.accent, sw=5 * s),
            circle(hx + 10 * s * ux, hy + 10 * s * uy, 17 * s, fill=st.accent, stroke=st.line),
            poly([(hx + 6 * s * ux - 7 * s * uy, hy + 6 * s * uy + 7 * s * ux), (hx + 34 * s * ux - 7 * s * uy, hy + 34 * s * uy + 7 * s * ux),
                  (hx + 34 * s * ux + 7 * s * uy, hy + 34 * s * uy - 7 * s * ux), (hx + 6 * s * ux + 7 * s * uy, hy + 6 * s * uy - 7 * s * ux)],
                 fill=st.fill),
            circle(tx, ty, 5 * s, fill=st.fill, stroke=st.line, sw=2.5)]


def cards(cx, cy, st: St):
    """추천안: 겹친 카드 넷, 맨 앞 장에 표시."""
    o = []
    for i in (3, 2, 1):
        o.append(rect(cx - 44 + i * 9, cy - 50 - i * 8, 80, 100, 8, fill=LIGHT if st is not OFF else WHITE, stroke=st.line, sw=3))
    o += [rect(cx - 44, cy - 50, 80, 100, 8, fill=st.fill, stroke=st.line),
          rect(cx - 34, cy - 40, 60, 16, 4, fill=st.accent, stroke=st.line, sw=2.5),
          line(cx - 32, cy - 10, cx + 24, cy - 10, stroke=st.line, sw=2.5), line(cx - 32, cy + 6, cx + 24, cy + 6, stroke=st.line, sw=2.5),
          line(cx - 32, cy + 22, cx + 4, cy + 22, stroke=st.line, sw=2.5)]
    o += check_badge(cx + 26, cy + 38, st, r=13)
    return o


def stop_sign(cx, cy, st: St, r=30):
    pts = [(cx + r * math.cos(math.radians(22.5 + 45 * i)), cy + r * math.sin(math.radians(22.5 + 45 * i))) for i in range(8)]
    return [poly(pts, fill=st.accent, stroke=st.line, sw=3.5), line(cx - r * 0.5, cy, cx + r * 0.5, cy, stroke=st.line, sw=7)]


def clock(cx, cy, st: St, r=22):
    return [circle(cx, cy, r, fill=st.fill, stroke=st.line),
            path(f"M {cx},{cy - r * 0.6} L {cx},{cy} L {cx + r * 0.45},{cy + r * 0.25}", stroke=st.line, sw=3.5)]


def tsdb(cx, cy, st: St):
    """시계열 DB: 원통과 시계(삽화_기본의 cylinder_db)."""
    return cylinder_db(cx, cy, st)


def cross(cx, cy, color=NAVY, s=12, sw=5):
    return [line(cx - s, cy - s, cx + s, cy + s, stroke=color, sw=sw), line(cx - s, cy + s, cx + s, cy - s, stroke=color, sw=sw)]


def arc(cx, cy, r, a1, a2, color=BLUE, sw=5, size=14):
    """원호 화살표(시계 방향, 도 단위. 0도 = 오른쪽, 90도 = 아래)."""
    x1, y1 = cx + r * math.cos(math.radians(a1)), cy + r * math.sin(math.radians(a1))
    x2, y2 = cx + r * math.cos(math.radians(a2)), cy + r * math.sin(math.radians(a2))
    big = 1 if (a2 - a1) % 360 > 180 else 0
    tang = math.radians(a2 + 90)
    return [path(f"M {x1:.1f},{y1:.1f} A {r} {r} 0 {big} 1 {x2:.1f},{y2:.1f}", stroke=color, sw=sw), head(x2, y2, tang, color, size)]


def loop(cx, cy, r, color=BLUE, sw=5):
    return arc(cx, cy, r, 200, 340, color, sw) + arc(cx, cy, r, 20, 160, color, sw)


def plus(cx, cy, color=NAVY, s=13):
    return [line(cx - s, cy, cx + s, cy, stroke=color, sw=6), line(cx, cy - s, cx, cy + s, stroke=color, sw=6)]


def equal(cx, cy, color=NAVY, s=14):
    return [line(cx - s, cy - 7, cx + s, cy - 7, stroke=color, sw=6), line(cx - s, cy + 7, cx + s, cy + 7, stroke=color, sw=6)]


# ───────────────────────── 1. 경보에서 승인까지 ─────────────────────────

def timeline() -> str:
    o: list[str] = []
    y = 210
    o += g(120, y, 2.4, bell(0, 0, ON))
    o += g(440, y, 1.35, agent_icon(0, 0, ON))
    o += loop(440, y, 104)
    o += cards(770, y + 6, ON)
    o += g(1030, y, 1.25, approve_icon(0, 0, ON))
    o.append(arrow([(190, y), (310, y)], NAVY))
    o.append(arrow([(570, y), (690, y)], NAVY))
    o.append(arrow([(850, y), (950, y)], NAVY))
    ay = 392
    for x in (120, 770, 1030):
        o += dots(x, 300, x, ay - 14, gap=14)
        o.append(line(x, ay - 14, x, ay + 14, stroke=NAVY, sw=4))
    o.append(line(120, ay, 770, ay, stroke=BLUE, sw=10))
    o.append(line(770, ay, 1030, ay, stroke=SKY, sw=10))
    return svg(o)


# ───────────────────────── 2. 에이전트의 세 요소 ─────────────────────────

def three_parts() -> str:
    o: list[str] = []
    y = 215
    o += bubble(170, y - 8, ON, w=130, h=88)
    o += plus(325, y)
    o += g(440, y - 44, 0.72, graph_icon(0, 0, ON))
    o += g(530, y - 40, 0.72, tsdb(0, 0, ON))
    o += g(485, y + 48, 0.8, table_icon(0, 0, ON))
    o += plus(645, y)
    o += loop(790, y, 62)
    o += wrench(790, y, ON, s=0.75)
    o += equal(935, y)
    o += g(1070, y, 1.5, agent_icon(0, 0, ON))
    return svg(o)


# ───────────────────────── 3. 실행 고리 ─────────────────────────

def run_loop() -> str:
    o: list[str] = []
    y, r = 285, 56
    xs = (150, 380, 610, 840, 1070)
    for i, x in enumerate(xs):
        last = i == len(xs) - 1
        o.append(circle(x, y, r, fill=PALE if 0 < i < 4 else WHITE, stroke=NAVY))
        if not last:
            o.append(arrow([(x + r + 8, y), (xs[i + 1] - r - 8, y)], NAVY))
    o += g(150, y, 0.72, doc(0, 0, ON, mark=1))
    for k, dy in enumerate((-20, 0, 20)):
        o += [circle(380 - 26, y + dy, 6, fill=SKY if k == 0 else WHITE, stroke=NAVY, sw=2.5), line(380 - 12, y + dy, 380 + 30, y + dy, stroke=NAVY, sw=3.5)]
    o += wrench(610, y, ON, s=0.8)
    o += magnifier(840 - 6, y - 6, ON, r=22)
    o += g(1070, y, 0.72, doc(0, 0, ON))
    o += check_badge(1070 + 30, y + 30, ON, r=17)
    # 되돌아가는 길: 결과 관찰 → 계획
    o.append(path(f"M 840,{y - r - 8} C 840,{y - r - 130} 380,{y - r - 130} 380,{y - r - 22}", stroke=BLUE, sw=5, stroke_dasharray="2 12"))
    o.append(head(380, y - r - 8, math.radians(90), BLUE, 15))
    return svg(o)


# ───────────────────────── 4. 네 정보원 ─────────────────────────

def sources() -> str:
    o: list[str] = []
    ax, ay = 600, 225
    lx, rx, ty, by = 175, 1025, 105, 345
    o += g(lx, ty, 1.0, graph_icon(0, 0, ON))
    o += g(lx, by, 0.95, book_icon(0, 0, ON))
    o += g(rx, ty, 1.0, tsdb(0, 0, ON))
    o += table_icon(rx, by, ON, w=112, h=88, hot=(2, 1))
    # 정보원 → 도구(작은 문) → 에이전트. 가로 · 세로 선만 쓴다.
    for sx, sy, ey, sign in ((lx + 75, ty, ay - 26, 1), (lx + 75, by, ay + 26, 1), (rx - 75, ty, ay - 26, -1), (rx - 75, by, ay + 26, -1)):
        mx = ax - sign * 190
        o.append(arrow([(sx, sy), (mx, sy), (mx, ey), (ax - sign * 78, ey)], NAVY))
        o.append(circle(mx, sy, 17, fill=WHITE, stroke=BLUE, sw=3.5))
        o += wrench(mx, sy, ON, s=0.34)
    o += g(ax, ay, 1.35, agent_icon(0, 0, ON))
    return svg(o)


# ───────────────────────── 5. 도구를 거쳐 읽는다 ─────────────────────────

def via_tool() -> str:
    o: list[str] = []
    y = 285
    # 직접 접속하는 길(없음): 회색 점선과 가위표
    o.append(path("M 170,200 L 170,60 L 990,60 L 990,128", stroke=GREY, sw=4, stroke_dasharray="10 10"))
    o += cross(580, 60, NAVY, s=13, sw=5)
    o += g(170, y, 1.3, agent_icon(0, 0, ON))
    o.append(rect(480, y - 78, 200, 156, 16, fill=PALE, stroke=NAVY))
    o += wrench(545, y - 6, ON, s=0.95)
    o += lock(630, y + 6, ON, s=1.5)
    o.append(arrow([(262, y - 26), (468, y - 26)], BLUE))
    o.append(arrow([(468, y + 26), (262, y + 26)], NAVY))
    o += g(990, 185, 0.95, tsdb(0, 0, ON))
    o += table_icon(990, 400, ON, w=112, h=84, hot=(2, 1))
    o.append(arrow([(690, y - 26), (800, y - 26), (800, 185), (922, 185)], BLUE))
    o.append(arrow([(690, y + 26), (800, y + 26), (800, 400), (922, 400)], BLUE))
    return svg(o)


# ───────────────────────── 6. 실행 기록 한 줄 ─────────────────────────

def record_row() -> str:
    o: list[str] = []
    # 위: 처리 기록(줄 다섯). 셋째 줄이 도구 호출 한 건.
    o.append(rect(80, 24, 1040, 196, 12, fill=WHITE, stroke=NAVY))
    for i in range(5):
        ry = 48 + i * 34
        hot = i == 2
        if hot:
            o.append(rect(96, ry - 14, 1008, 30, 6, fill=PALE, stroke=BLUE, sw=3))
        o.append(circle(120, ry + 1, 6, fill=SKY if hot else WHITE, stroke=NAVY if hot else GREY, sw=2.5))
        o.append(line(146, ry + 1, 240, ry + 1, stroke=NAVY if hot else GREY, sw=4))
        o.append(line(270, ry + 1, 270 + (560, 400, 760, 480, 620)[i], ry + 1, stroke=NAVY if hot else GREY, sw=3))
    # 아래: 그 한 줄을 다섯 칸으로 펼친 것
    y0, h = 298, 150
    xs = (80, 230, 450, 740, 990, 1120)
    o += dots(96, 148, 80, y0, color=BLUE, gap=14, r=3)
    o += dots(1104, 148, 1120, y0, color=BLUE, gap=14, r=3)
    o.append(rect(80, y0, 1040, h, 12, fill=WHITE, stroke=NAVY))
    for x in xs[1:-1]:
        o.append(line(x, y0, x, y0 + h, stroke=NAVY, sw=2.5))
    return svg(o)


# ───────────────────────── 7. 신선도 ─────────────────────────

def freshness() -> str:
    o: list[str] = []
    ay = 330
    o.append(rect(540, ay - 86, 440, 86, 0, fill=PALE, stroke="none", sw=0))
    o.append(arrow([(100, ay), (1110, ay)], NAVY))
    for x in range(160, 1100, 60):
        o.append(line(x, ay - 7, x, ay + 7, stroke=NAVY, sw=2.5))
    o.append(line(540, ay - 100, 540, ay + 14, stroke=BLUE, sw=4, stroke_dasharray="8 8"))
    o.append(line(980, ay - 190, 980, ay + 14, stroke=NAVY, sw=5))
    o += clock(980, ay - 214, ON, r=22)
    # 방금 읽은 값
    o.append(circle(962, ay - 40, 13, fill=SKY, stroke=NAVY))
    o += dots(962, ay - 58, 962, 150, color=BLUE, gap=13, r=3)
    o += check_badge(880, 132, ON, r=24)
    o.append(line(906, 132, 962, 132, stroke=BLUE, sw=4))
    # 묵은 값
    o.append(circle(330, ay - 40, 13, fill=GREY, stroke=NAVY))
    o += dots(330, ay - 58, 330, 150, color=GREY, gap=13, r=3)
    o += stop_sign(250, 132, ON, r=26)
    o.append(line(278, 132, 330, 132, stroke=GREY, sw=4))
    return svg(o)


# ───────────────────────── 8. 멈춤 조건 ─────────────────────────

def stops() -> str:
    """세 갈래(근거 부족 · 도구 호출 실패 · 권한 제한) → 멈춤 → 사람. 아이콘 아래에 두 줄 라벨이 들어갈 자리를 둔다."""
    o: list[str] = []
    ys = (60, 220, 380)
    cy = ys[1]
    o += g(125, cy, 1.2, agent_icon(0, 0, ON))
    for y in ys:
        o.append(arrow([(205, cy), (290, cy), (290, y), (385, y)] if y != cy else [(205, cy), (385, cy)], NAVY))
        o.append(arrow([(545, y), (700, y)], NAVY))
        o += stop_sign(742, y, ON, r=26)
        o.append(arrow([(784, y), (900, y), (900, cy), (968, cy)] if y != cy else [(784, cy), (968, cy)], BLUE))
    # 근거 부족: 값이 비어 있는 계기와 표
    o += g(465, ys[0], 0.7, tsdb(0, 0, OFF))
    o += cross(500, ys[0] - 26, NAVY, s=9, sw=4)
    # 도구 호출 실패: 도구와 끊긴 선
    o.append(circle(465, ys[1], 34, fill=WHITE, stroke=NAVY))
    o += wrench(465, ys[1], NORM, s=0.6)
    o += cross(500, ys[1] - 26, NAVY, s=9, sw=4)
    # 권한 제한: 잠긴 도구
    o.append(circle(465, ys[2], 34, fill=WHITE, stroke=NAVY))
    o += lock(465, ys[2], ON, s=1.4)
    o += g(1040, cy, 1.2, approve_icon(0, 0, ON))
    return svg(o)


def main():
    figs = {"경보에서승인까지": timeline, "세요소": three_parts, "실행고리": run_loop, "정보원": sources, "도구경유": via_tool,
            "기록한줄": record_row, "신선도": freshness, "멈춤조건": stops}
    for name, fn in figs.items():
        (HERE / f"{name}.svg").write_text(fn(), encoding="utf-8")
        print("wrote", name)


if __name__ == "__main__":
    main()
