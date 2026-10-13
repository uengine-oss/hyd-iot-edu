"""통합반 7일차 삽화(SVG)를 만든다. 글자는 넣지 않는다(라벨은 덱 MD의 요소로 얹는다).

화풍(선 굵기 · 색 · 그림 조각)은 1일차의 `만들기_삽화.py`를 복사한 `삽화_기본.py`에서 가져오고,
문서 · 겹친 카드 · 멈춤 표지 같은 조각은 5일차 `만들기_삽화.py`의 것을 그대로 옮겼다.
사용: python 만들기_삽화.py            → 이 폴더에 SVG를 쓴다
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from 삽화_기본 import (BLUE, GREY, LIGHT, NAVY, NORM, OFF, ON, PALE, SKY, WHITE, St, agent_icon,  # noqa: E402
                    approve_icon, arrow, bell, circle, dots, fan, g, head, line, monitor, path, poly, rect, svg)


# ───────────────────────── 작은 그림 조각 (5일차의 것) ─────────────────────────

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


def check_badge(cx, cy, st: St, r=17):
    return [circle(cx, cy, r, fill=st.accent, stroke=st.line),
            path(f"M {cx - r * 0.47},{cy} L {cx - r * 0.1},{cy + r * 0.38} L {cx + r * 0.52},{cy - r * 0.36}", stroke=st.line, sw=4)]


def bubble(cx, cy, st: St, w=110, h=74):
    """말풍선: 글로 된 요청이나 질문."""
    x, y = cx - w / 2, cy - h / 2
    o = [path(f"M {x + 12},{y} L {x + w - 12},{y} Q {x + w},{y} {x + w},{y + 12} L {x + w},{y + h - 12} Q {x + w},{y + h} {x + w - 12},{y + h} "
              f"L {x + 44},{y + h} L {x + 24},{y + h + 20} L {x + 26},{y + h} L {x + 12},{y + h} Q {x},{y + h} {x},{y + h - 12} "
              f"L {x},{y + 12} Q {x},{y} {x + 12},{y} Z", fill=st.fill, stroke=st.line)]
    for i, dy in enumerate((-16, 0, 16)):
        o.append(line(x + 18, cy + dy, x + w - (40 if i == 2 else 18), cy + dy, stroke=st.line, sw=3))
    return o


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


def cross(cx, cy, color=NAVY, s=12, sw=5):
    return [line(cx - s, cy - s, cx + s, cy + s, stroke=color, sw=sw), line(cx - s, cy + s, cx + s, cy - s, stroke=color, sw=sw)]


# ───────────────────────── 작은 그림 조각 (7일차에서 새로 쓰는 것) ─────────────────────────

def person(cx, cy, st: St):
    """사람(승인 표시 없음)."""
    return [circle(cx, cy - 22, 17, fill=st.fill, stroke=st.line),
            path(f"M {cx - 34},{cy + 38} Q {cx - 34},{cy + 4} {cx},{cy + 4} Q {cx + 34},{cy + 4} {cx + 34},{cy + 38} Z", fill=st.fill, stroke=st.line)]


def cross_badge(cx, cy, st: St, r=17):
    return [circle(cx, cy, r, fill=st.fill, stroke=st.line), *cross(cx, cy, st.line, s=r * 0.42, sw=4)]


def shield(cx, cy, st: St, s=1.0):
    """가드레일: 방패와 점검 표시."""
    w, h = 36 * s, 44 * s
    o = [path(f"M {cx},{cy - h} L {cx + w},{cy - h * 0.66} L {cx + w},{cy + h * 0.1} Q {cx + w},{cy + h * 0.8} {cx},{cy + h} "
              f"Q {cx - w},{cy + h * 0.8} {cx - w},{cy + h * 0.1} L {cx - w},{cy - h * 0.66} Z", fill=st.soft, stroke=st.line)]
    for i, dy in enumerate((-18, 0, 18)):
        yy = cy + dy * s - 4 * s
        o.append(path(f"M {cx - 20 * s},{yy} L {cx - 15 * s},{yy + 5 * s} L {cx - 7 * s},{yy - 5 * s}", stroke=BLUE if st is ON else st.line, sw=3))
        o.append(line(cx + 1 * s, yy, cx + (20 if i < 2 else 12) * s, yy, stroke=st.line, sw=3))
    return o


def closed_case(cx, cy, st: St):
    """명령 없이 닫힌 처리 건: 문서와 가위표."""
    return doc(cx, cy, st, w=70, h=90, lines=4) + cross_badge(cx + 30, cy + 34, st, r=16)


def fan_cmd(cx, cy, st: St, r=44):
    """설비 명령이 닿는 팬."""
    return fan(cx, cy, r, st, hot=st is ON)


# ───────────────────────── 1. 추천안 뒤의 갈림 ─────────────────────────

def fork() -> str:
    o: list[str] = []
    y = 250
    o += g(120, y, 1.15, agent_icon(0, 0, NORM))
    o.append(arrow([(190, y), (270, y)], NAVY))
    o += cards(350, y + 6, ON)
    o.append(arrow([(425, y), (520, y)], NAVY))
    o += g(600, y, 1.5, person(0, 0, ON))
    # 승인: 위 가지
    o.append(arrow([(680, y - 20), (760, y - 20), (760, 120), (850, 120)], BLUE))
    o += check_badge(760, 185, ON, r=20)
    o += fan_cmd(930, 120, ON, r=50)
    o.append(arrow([(990, 120), (1060, 120)], NAVY))
    o += g(1120, 120, 0.8, doc(0, 0, ON, mark=1))
    # 거절: 아래 가지
    o.append(arrow([(680, y + 20), (760, y + 20), (760, 400), (850, 400)], NAVY))
    o += cross_badge(760, 325, ON, r=20)
    o += g(930, 400, 1.05, closed_case(0, 0, ON))
    # 시간 축: 추천안에서 결정까지
    ay = 452
    for x in (350, 600):
        o += dots(x, 340, x, ay - 14, gap=13)
        o.append(line(x, ay - 14, x, ay + 14, stroke=NAVY, sw=4))
    o.append(line(350, ay, 600, ay, stroke=SKY, sw=10))
    return svg(o)


# ───────────────────────── 2. 사람이 개입하는 세 지점 ─────────────────────────

def three_points() -> str:
    o: list[str] = []
    by = 62
    # 위: 처리의 구간 띠 (에이전트 단계 · 승인 단계 · 시스템 실행)
    o.append(line(90, by, 700, by, stroke=BLUE, sw=14))
    o.append(line(700, by, 930, by, stroke=SKY, sw=14))
    o.append(line(930, by, 1110, by, stroke=GREY, sw=14))
    for x in (90, 700, 930, 1110):
        o.append(line(x, by - 18, x, by + 18, stroke=NAVY, sw=4))
    sy = 320
    # 에이전트의 질문 (에이전트 단계 안)
    o += dots(230, by + 22, 230, sy - 120, color=BLUE, gap=14, r=3)
    o += g(140, sy, 0.95, agent_icon(0, 0, ON))
    o += g(330, sy, 1.1, person(0, 0, ON))
    o.append(arrow([(190, sy - 22), (278, sy - 22)], BLUE))
    o.append(arrow([(278, sy + 22), (190, sy + 22)], NAVY))
    o += g(235, sy - 82, 0.55, bubble(0, 0, ON))
    # 멈춘 작업 닫기 (에이전트 단계 안)
    o += dots(570, by + 22, 570, sy - 120, color=BLUE, gap=14, r=3)
    o += g(490, sy, 0.95, agent_icon(0, 0, OFF))
    o += stop_sign(545, sy - 52, ON, r=22)
    o.append(arrow([(545, sy), (610, sy)], NAVY))
    o += g(670, sy, 1.1, person(0, 0, ON))
    o += cross_badge(712, sy + 30, ON, r=17)
    # 승인 단계
    o += dots(815, by + 22, 815, sy - 120, color=BLUE, gap=14, r=3)
    o += cards(880, sy + 6, ON)
    o.append(arrow([(955, sy), (1010, sy)], NAVY))
    o += g(1075, sy, 1.15, approve_icon(0, 0, ON))
    # 지점 사이 구분선
    for x in (425, 775):
        o.append(line(x, 170, x, 430, stroke=GREY, sw=2.5, stroke_dasharray="6 10"))
    return svg(o)


# ───────────────────────── 3. 응답이 없을 때 ─────────────────────────

def no_answer() -> str:
    o: list[str] = []
    ay = 380
    o.append(arrow([(90, ay), (1120, ay)], NAVY))
    xs = (190, 620, 960)
    # 기다리는 구간: 알림 시점을 지나서도 끊기지 않는다
    o.append(line(xs[0], ay - 40, xs[2], ay - 40, stroke=SKY, sw=16))
    for x in xs:
        o.append(line(x, ay - 62, x, ay + 14, stroke=NAVY, sw=4))
    o += g(xs[0], 180, 0.95, cards(0, 0, ON))
    o += dots(xs[0], 250, xs[0], ay - 70, gap=13)
    o += g(xs[1], 190, 3.0, bell(0, 0, ON))
    o += dots(xs[1], 250, xs[1], ay - 70, color=BLUE, gap=13, r=3)
    o += g(xs[2], 185, 1.3, approve_icon(0, 0, ON))
    o += dots(xs[2], 250, xs[2], ay - 70, gap=13)
    # 기다리는 담당자
    o += g(400, 200, 1.0, person(0, 0, NORM))
    return svg(o)


# ───────────────────────── 4. 가드레일과 사람 승인: 두 관문 ─────────────────────────

def two_gates() -> str:
    o: list[str] = []
    y = 190
    o += g(100, y, 1.1, agent_icon(0, 0, ON))
    o.append(arrow([(170, y), (235, y)], NAVY))
    o += g(300, y + 4, 0.85, cards(0, 0, ON))
    o.append(arrow([(365, y), (430, y)], NAVY))
    # 관문 1: 가드레일
    o.append(rect(440, y - 96, 150, 192, 16, fill=WHITE, stroke=NAVY))
    o += shield(515, y, ON, s=1.25)
    o.append(arrow([(600, y), (690, y)], BLUE))
    # 관문 2: 사람의 승인
    o.append(rect(700, y - 96, 150, 192, 16, fill=PALE, stroke=NAVY))
    o += g(770, y, 1.3, approve_icon(0, 0, ON))
    o.append(arrow([(860, y), (960, y)], BLUE))
    o += fan_cmd(1040, y, ON, r=52)
    # 걸러진 것
    o.append(arrow([(515, y + 104), (515, 380)], NAVY))
    o += g(515, 440, 0.8, closed_case(0, 0, NORM))
    o.append(arrow([(775, y + 104), (775, 380)], NAVY))
    o += g(775, 440, 0.8, closed_case(0, 0, NORM))
    return svg(o)


# ───────────────────────── 5. 한 문장의 세 가지 해석 ─────────────────────────

def three_readings() -> str:
    o: list[str] = []
    ys = (86, 260, 434)
    o += bubble(150, 250, ON, w=170, h=104)
    for y in ys:
        o.append(arrow([(250, 260), (330, 260), (330, y), (440, y)] if y != 260 else [(250, 260), (440, 260)], NAVY))
    # ① 출력 형식: 결과 문서에 줄 하나가 더해진다
    o += g(520, ys[0], 1.0, doc(0, 0, ON, mark=2, lines=6, h=92))
    # ② 승인 조건: 사람을 건너뛰는 길
    o += g(520, ys[1], 0.95, person(0, 0, OFF))
    o.append(path(f"M 462,{ys[1] + 52} C 480,{ys[1] - 78} 560,{ys[1] - 78} 578,{ys[1] + 52}", stroke=BLUE, sw=5, stroke_dasharray="2 12"))
    o.append(head(578, ys[1] + 52, math.radians(80), BLUE, 14))
    # ③ 기존 요청: 앞서 되던 처리와 달라진 처리
    o += g(490, ys[2], 0.8, doc(0, 0, NORM))
    o.append(arrow([(524, ys[2]), (552, ys[2])], NAVY, sw=3.5, size=10))
    o += g(586, ys[2], 0.8, doc(0, 0, ON, mark=3))
    return svg(o)


# ───────────────────────── 6. 명세 문서의 다섯 구획 ─────────────────────────

SPEC_BLOCKS = (("req", 62, 66), ("in", 142, 66), ("out", 222, 84), ("ban", 320, 66), ("acc", 400, 92))


def specdoc() -> str:
    o = [rect(60, 8, 470, 504, 12, fill=WHITE), rect(82, 24, 200, 22, 6, fill=NAVY, stroke="none", sw=0)]
    for key, y, h in SPEC_BLOCKS:
        o.append(rect(78, y, 434, h, 8, fill=PALE, stroke=SKY, sw=3))
        if key == "acc":
            for k in range(3):
                yy = y + 20 + k * 26
                o += [rect(94, yy - 9, 18, 18, 4, fill=WHITE, stroke=NAVY, sw=2.5),
                      path(f"M {98},{yy} L {102},{yy + 5} L {109},{yy - 5}", stroke=BLUE, sw=3),
                      rect(124, yy - 6, (330, 280, 350)[k], 12, 6, fill=GREY, stroke="none", sw=0)]
        elif key == "ban":
            for k in range(2):
                yy = y + 22 + k * 24
                o += [circle(103, yy, 9, fill=WHITE, stroke=NAVY, sw=2.5), line(97, yy + 6, 109, yy - 6, stroke=NAVY, sw=2.5),
                      rect(124, yy - 6, (320, 250)[k], 12, 6, fill=GREY, stroke="none", sw=0)]
        else:
            n = 3 if h >= 80 else 2
            for k in range(n):
                o.append(rect(94, y + 18 + k * 22, (390, 300, 340)[k], 11, 5, fill=GREY, stroke="none", sw=0))
        o += dots(520, y + h / 2, 600, y + h / 2, color=BLUE, gap=13, r=3)
    return svg(o)


# ───────────────────────── 7. 입력 계약과 출력 계약 ─────────────────────────

def contracts() -> str:
    o: list[str] = []
    y = 215
    o += g(110, y, 3.0, bell(0, 0, ON))
    o.append(arrow([(175, y), (300, y)], NAVY))
    o += g(355, y, 0.9, doc(0, 0, ON, lines=4))
    o += check_badge(385, y + 34, ON, r=14)
    o.append(arrow([(410, y), (520, y)], NAVY))
    o += g(600, y, 1.45, agent_icon(0, 0, ON))
    o.append(arrow([(690, y), (790, y)], NAVY))
    o += g(845, y, 0.9, doc(0, 0, ON, lines=4))
    o += check_badge(875, y + 34, ON, r=14)
    o.append(arrow([(900, y), (1000, y)], NAVY))
    o += g(1080, y - 4, 1.05, monitor(0, 0, ON, kind="plain"))
    # 계약의 자리를 묶는 받침선
    for x1, x2 in ((300, 410), (790, 900)):
        o.append(line(x1, y + 86, x2, y + 86, stroke=BLUE, sw=6))
        o.append(line(x1, y + 74, x1, y + 98, stroke=BLUE, sw=4))
        o.append(line(x2, y + 74, x2, y + 98, stroke=BLUE, sw=4))
    return svg(o)


def main():
    figs = {"갈림": fork, "세지점": three_points, "무응답": no_answer, "두관문": two_gates, "세해석": three_readings,
            "명세문서": specdoc, "계약": contracts}
    for name, fn in figs.items():
        (HERE / f"{name}.svg").write_text(fn(), encoding="utf-8")
        print("wrote", name)


if __name__ == "__main__":
    main()
