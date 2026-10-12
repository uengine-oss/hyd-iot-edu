"""통합반 8일차 삽화(SVG)를 만든다. 글자는 넣지 않는다(라벨은 덱 MD의 요소로 얹는다).

화풍(선 굵기 · 색 · 그림 조각)은 1일차의 `만들기_삽화.py`를 복사한 `삽화_기본.py`에서 가져온다.
사용: python 만들기_삽화.py            → 이 폴더에 SVG를 쓴다
"""
from __future__ import annotations

import math
from pathlib import Path

from 삽화_기본 import (BLUE, GREY, LIGHT, NAVY, NORM, OFF, ON, PALE, SKY, WHITE, St, agent_icon, approve_icon, arrow, bell,
                    calendar_icon, circle, cylinder_db, fan, g, gauge, graph_icon, head, line, path, poly, rect, svg, thermo)

HERE = Path(__file__).resolve().parent


# ───────────────────────── 작은 그림 조각 ─────────────────────────

def bar(x, y, w, h=12, color=GREY):
    return rect(x, y, w, h, h / 2, fill=color, stroke="none", sw=0)


def sop_doc(cx, cy, st: St, w=92, h=116):
    """문서: 제목 띠와 줄."""
    o = [rect(cx - w / 2, cy - h / 2, w, h, 8, fill=st.fill, stroke=st.line),
         rect(cx - w / 2 + 12, cy - h / 2 + 14, w * 0.5, 12, 4, fill=st.line, stroke="none", sw=0)]
    for i, k in enumerate((0.85, 0.6, 0.8, 0.5)):
        y = cy - h / 2 + 44 + i * 18
        o.append(line(cx - w / 2 + 14, y, cx - w / 2 + 14 + (w - 28) * k, y, stroke=st.line, sw=2.5))
    return o


def skill_doc(cx, cy, st: St, w=96, h=120):
    """에이전트 스킬 문서: 위의 머리말 띠와 번호 붙은 절차."""
    o = [rect(cx - w / 2, cy - h / 2, w, h, 8, fill=st.fill, stroke=st.line),
         rect(cx - w / 2, cy - h / 2, w, 26, 8, fill=st.accent, stroke=st.line)]
    for i, k in enumerate((0.8, 0.6, 0.75, 0.55)):
        y = cy - h / 2 + 46 + i * 19
        o += [circle(cx - w / 2 + 16, y, 5, fill=st.accent, stroke=st.line, sw=2),
              line(cx - w / 2 + 30, y, cx - w / 2 + 30 + (w - 44) * k, y, stroke=st.line, sw=2.5)]
    return o


def gear(cx, cy, r, st: St, hot=False):
    """도구(톱니바퀴)."""
    o = []
    for i in range(8):
        o.append(rect(cx - r * 0.17, cy - r, r * 0.34, r * 0.4, 2, fill=st.line, stroke="none", sw=0,
                      transform=f"rotate({i * 45} {cx} {cy})"))
    o += [circle(cx, cy, r * 0.74, fill=st.accent if hot else st.soft, stroke=st.line),
          circle(cx, cy, r * 0.27, fill=st.fill, stroke=st.line, sw=3)]
    return o


def magnifier(cx, cy, st: St, r=20):
    return [line(cx + r * 0.7, cy + r * 0.7, cx + r * 1.55, cy + r * 1.55, stroke=st.line, sw=7),
            circle(cx, cy, r, fill=st.accent, stroke=st.line)]


def check_mark(cx, cy, r=28):
    return [circle(cx, cy, r, fill=SKY, stroke=NAVY, sw=3.5),
            path(f"M {cx - r * 0.42},{cy + r * 0.02} L {cx - r * 0.1},{cy + r * 0.36} L {cx + r * 0.46},{cy - r * 0.32}", stroke=NAVY, sw=5)]


def cross_mark(cx, cy, r=28, color=NAVY):
    return [circle(cx, cy, r, fill=WHITE, stroke=color, sw=3.5),
            line(cx - r * 0.36, cy - r * 0.36, cx + r * 0.36, cy + r * 0.36, stroke=color, sw=5),
            line(cx + r * 0.36, cy - r * 0.36, cx - r * 0.36, cy + r * 0.36, stroke=color, sw=5)]


def table_icon(cx, cy, st: St):
    """업무 DB(표)."""
    o = [rect(cx - 46, cy - 38, 92, 76, 7, fill=st.fill, stroke=st.line), rect(cx - 46, cy - 38, 92, 20, 7, fill=st.accent, stroke=st.line)]
    for dy in (0, 19):
        o.append(line(cx - 46, cy + dy, cx + 46, cy + dy, stroke=st.line, sw=2.5))
    for dx in (-16, 14):
        o.append(line(cx + dx, cy - 38, cx + dx, cy + 38, stroke=st.line, sw=2.5))
    return o


def ranking(cx, cy, st: St, order=(0.9, 0.7, 0.7, 0.35)):
    """조치 카드 묶음: 순위가 매겨진 후보."""
    o = [rect(cx - 120, cy - 78, 240, 156, 10, fill=WHITE, stroke=st.line)]
    for i, k in enumerate(order):
        y = cy - 54 + i * 36
        on = i == 0 and st is not OFF
        o += [circle(cx - 96, y, 10, fill=SKY if on else WHITE, stroke=st.line, sw=2.5),
              rect(cx - 76, y - 9, 170 * k, 18, 6, fill=SKY if on else GREY if st is not OFF else LIGHT,
                   stroke=st.line if on else "none", sw=2.5 if on else 0)]
    return o


def lock(cx, cy, st: St, s=1.0):
    return [path(f"M {cx - 15 * s},{cy - 6 * s} L {cx - 15 * s},{cy - 20 * s} A {15 * s} {15 * s} 0 0 1 {cx + 15 * s},{cy - 20 * s} "
                 f"L {cx + 15 * s},{cy - 6 * s}", stroke=st.line, sw=5),
            rect(cx - 24 * s, cy - 6 * s, 48 * s, 40 * s, 7, fill=st.accent, stroke=st.line),
            circle(cx, cy + 10 * s, 5 * s, fill=st.line, stroke=st.line, sw=1),
            line(cx, cy + 12 * s, cx, cy + 22 * s, stroke=st.line, sw=4)]


def dashed(x1, y1, x2, y2, color=NAVY, sw=3.5):
    ang = math.atan2(y2 - y1, x2 - x1)
    return [line(x1, y1, x2 - 10 * math.cos(ang), y2 - 10 * math.sin(ang), stroke=color, sw=sw, stroke_dasharray="9 8"),
            head(x2, y2, ang, color, 12)]


def person(cx, cy, st: St):
    """사람(표시 없음)."""
    return [circle(cx, cy - 22, 17, fill=st.fill, stroke=st.line),
            path(f"M {cx - 34},{cy + 38} Q {cx - 34},{cy + 4} {cx},{cy + 4} Q {cx + 34},{cy + 4} {cx + 34},{cy + 38} Z", fill=st.fill, stroke=st.line)]


def clock(cx, cy, r, st: St, hot=False):
    return [circle(cx, cy, r, fill=st.accent if hot else st.fill, stroke=st.line),
            line(cx, cy, cx, cy - r * 0.58, stroke=st.line, sw=4), line(cx, cy, cx + r * 0.42, cy + r * 0.2, stroke=st.line, sw=4)]


def checklist(x, y, n, st: St, w=230, gap=44, hot=(), marks=None):
    """시나리오 목록: 줄마다 판정 표시와 문장 띠. hot = 강조할 줄, marks[i] = True 통과 · False 실패 · None 빈 칸."""
    o = [rect(x, y, w, n * gap + 20, 10, fill=WHITE, stroke=st.line)]
    for i in range(n):
        cy = y + 32 + i * gap
        m = True if marks is None else marks[i]
        on = i in hot
        o.append(circle(x + 28, cy, 13, fill=SKY if (m and on) else PALE if m else WHITE, stroke=st.line, sw=2.5))
        if m is True:
            o.append(path(f"M {x + 22},{cy} L {x + 27},{cy + 5} L {x + 35},{cy - 5}", stroke=st.line, sw=3))
        elif m is False:
            o += [line(x + 23, cy - 5, x + 33, cy + 5, stroke=st.line, sw=3), line(x + 33, cy - 5, x + 23, cy + 5, stroke=st.line, sw=3)]
        o.append(rect(x + 52, cy - 8, (w - 76) * (0.9, 0.7, 0.8, 0.6, 0.75, 0.65)[i % 6], 16, 6, fill=SKY if on else GREY,
                      stroke=st.line if on else "none", sw=2.5 if on else 0))
    return o


def spec_doc(x, y, w, h, bands=4):
    """명세 문서: 제목 띠 아래에 요소마다 한 칸."""
    o = [rect(x, y, w, h, 12, fill=WHITE), rect(x + 18, y + 16, w * 0.42, 16, 5, fill=NAVY, stroke="none", sw=0)]
    bh = (h - 62) / bands
    for i in range(bands):
        o.append(rect(x + 14, y + 48 + i * bh, w - 28, bh - 10, 8, fill=PALE, stroke=SKY, sw=3))
    return o


# ───────────────────────── 1. 명세에 적은 것과 실제 실행 ─────────────────────────

def spec_run() -> str:
    o = spec_doc(60, 24, 330, 386)
    o += [arrow([(404, 216), (486, 216)], NAVY, sw=5, size=14), arrow([(668, 216), (772, 216)], BLUE, sw=5, size=14)]
    o += g(576, 222, 1.5, agent_icon(0, 0, ON))
    o += g(920, 216, 0.95, ranking(0, 0, ON))
    # 대조: 명세와 실제 결과를 잇는 점선
    o += [path("M 225,418 L 225,468 L 540,468", stroke=BLUE, sw=4, stroke_dasharray="9 8"),
          path("M 920,300 L 920,468 L 626,468", stroke=BLUE, sw=4, stroke_dasharray="9 8")]
    o += magnifier(576, 462, ON, r=24)
    return svg(o)


# ───────────────────────── 2. Given · When · Then ─────────────────────────

def gwt() -> str:
    xs = (40, 430, 820)
    o: list[str] = []
    for i, x in enumerate(xs):
        o.append(rect(x, 96, 340, 400, 16, fill=PALE if i == 1 else LIGHT, stroke=SKY if i == 1 else "none", sw=3 if i == 1 else 0))
    o += [arrow([(384, 250), (426, 250)], NAVY, sw=5, size=13), arrow([(774, 250), (816, 250)], NAVY, sw=5, size=13)]
    # Given: 조치 카드 묶음이 올라와 담당자의 결정을 기다린다
    o += g(140, 250, 0.62, ranking(0, 0, ON))
    o += g(300, 250, 1.1, person(0, 0, ON))
    o += clock(336, 208, 20, ON, hot=True)
    # When: 담당자가 사유를 적고 거절한다
    o += g(540, 250, 1.1, person(0, 0, ON))
    o += cross_mark(586, 276, 22)
    o += sop_doc(690, 250, ON, w=84, h=104)
    # Then: 설비 명령 없음 · 업무 처리 없음 · 처리 건 종료
    o += fan(900, 220, 38, OFF, rot=20)
    o += g(1000, 220, 0.72, table_icon(0, 0, OFF))
    o += cross_mark(934, 260, 15, GREY) + cross_mark(1034, 260, 15, GREY)
    o += g(1100, 222, 0.62, sop_doc(0, 0, ON))
    o += check_mark(1128, 262, 16)
    return svg(o)


# ───────────────────────── 3. 시나리오에서 실행 가능한 검증으로 ─────────────────────────

def link() -> str:
    rows = (120, 260, 400)
    o = [rect(40, 40, 300, 440, 12, fill=WHITE)]
    for y in rows:
        o.append(rect(56, y - 46, 268, 92, 8, fill=PALE, stroke=SKY, sw=3))
        o.append(arrow([(344, y), (424, y)], BLUE, sw=4.5, size=13))
    o += g(500, rows[0], 0.8, table_icon(0, 0, ON))
    o += gear(500, rows[1], 38, ON, hot=True)
    o += checklist(440, rows[2] - 46, 2, ON, w=124, gap=34)
    o.append(arrow([(500, rows[0] + 40), (500, rows[1] - 46)], NAVY, sw=4.5, size=13))
    o.append(arrow([(546, rows[1]), (668, rows[1])], NAVY, sw=4.5, size=13))
    o += g(740, rows[1], 0.55, ranking(0, 0, ON))
    # 대조
    o += [arrow([(812, rows[1]), (900, rows[1]), (900, 300)], NAVY, sw=4.5, size=13),
          arrow([(568, rows[2]), (900, rows[2]), (900, 368)], BLUE, sw=4.5, size=13)]
    o += [circle(900, 334, 30, fill=WHITE, sw=4), line(886, 326, 914, 326, sw=5), line(886, 342, 914, 342, sw=5)]
    o += [arrow([(934, 322), (1000, 322), (1000, 250), (1040, 250)], NAVY, sw=4, size=12),
          arrow([(934, 346), (1000, 346), (1000, 418), (1040, 418)], NAVY, sw=4, size=12)]
    o += check_mark(1076, 250, 30) + cross_mark(1076, 418, 30)
    return svg(o)


# ───────────────────────── 4. 승인 단계에서 갈라지는 경우 ─────────────────────────

def branches() -> str:
    rows = (76, 198, 320, 442)
    o: list[str] = [rect(30, 150, 290, 220, 16, fill=PALE, stroke=SKY, sw=3)]
    o += g(120, 262, 0.55, ranking(0, 0, ON)) + g(248, 258, 1.0, person(0, 0, ON))
    for y in rows:
        o.append(path(f"M 324,260 C 400,260 380,{y} 452,{y}", stroke=NAVY, sw=4))
        o.append(arrow([(452, y), (486, y)], NAVY, sw=4, size=12))
        o.append(arrow([(596, y), (700, y)], BLUE, sw=4.5, size=13))
    # 승인 → 설비 명령
    o += check_mark(540, rows[0], 30) + fan(760, rows[0], 38, ON, rot=20, hot=True)
    # 거절 → 처리 없이 닫힘
    o += cross_mark(540, rows[1], 30) + g(760, rows[1], 0.6, sop_doc(0, 0, ON)) + cross_mark(790, rows[1] + 26, 14)
    # 무응답 → 지연 알림, 계속 대기
    o += clock(540, rows[2], 30, ON, hot=True) + [circle(760, rows[2], 38, fill=WHITE, sw=3.5)] + g(760, rows[2] - 3, 1.4, bell(0, 0, ON))
    # 사유 없음 · 권한 없음 → 요청이 받아들여지지 않음
    o += [circle(540, rows[3], 30, fill=WHITE, sw=3.5)] + g(540, rows[3] + 2, 0.72, lock(0, -6, ON))
    o += g(760, rows[3], 0.42, ranking(0, 0, ON)) + clock(800, rows[3] - 30, 15, ON)
    return svg(o)


# ───────────────────────── 5. 경계값: 기준의 바로 안쪽과 바깥쪽 ─────────────────────────

def boundary() -> str:
    Y, XT = 300, 800
    o = [rect(110, Y - 110, XT - 110, 220, 14, fill=PALE, stroke="none", sw=0)]
    o += [line(110, Y, 520, Y, sw=5), line(600, Y, 1090, Y, sw=5), head(1106, Y, 0, NAVY, 16)]
    o.append(path(f"M 520,{Y} L 535,{Y - 16} L 555,{Y + 16} L 575,{Y - 16} L 590,{Y + 16} L 600,{Y}", stroke=NAVY, sw=4))
    o.append(line(XT, Y - 150, XT, Y + 20, stroke=BLUE, sw=4.5, stroke_dasharray="10 8"))
    o += thermo(70, Y + 30, ON, s=1.1, level=0.6)
    for x, ok in ((280, True), (650, True), (XT, False), (950, False)):
        o.append(circle(x, Y, 13, fill=SKY if ok else WHITE, stroke=NAVY, sw=4))
        o += check_mark(x, Y - 62, 22) if ok else cross_mark(x, Y - 62, 22)
    return svg(o)


# ───────────────────────── 6. 회귀: 바꾼 뒤에 기존 시나리오를 모두 다시 ─────────────────────────

def regression() -> str:
    o = [rect(30, 60, 400, 430, 16, fill=LIGHT, stroke="none", sw=0), rect(660, 60, 510, 430, 16, fill=LIGHT, stroke="none", sw=0)]
    # 변경 전
    o += g(120, 262, 1.05, agent_icon(0, 0, ON))
    o += checklist(190, 164, 4, ON, w=220)
    # 변경
    o.append(arrow([(444, 262), (648, 262)], BLUE, sw=6, size=16))
    o += spec_doc(494, 110, 100, 120, bands=2)
    o += [circle(592, 118, 22, fill=SKY, sw=3.5), line(580, 118, 604, 118, sw=5), line(592, 106, 592, 130, sw=5)]
    # 변경 후
    o += g(734, 244, 0.95, agent_icon(0, 0, ON))
    o += [circle(778, 184, 16, fill=SKY, sw=3), line(770, 184, 786, 184, sw=4), line(778, 176, 778, 192, sw=4)]
    o += checklist(806, 120, 5, ON, w=214, hot=(4,))
    o.append(path("M 1028,138 L 1044,138 L 1044,298 L 1028,298", stroke=BLUE, sw=4))
    o.append(path("M 1028,316 L 1044,316 L 1044,340 L 1028,340", stroke=NAVY, sw=4))
    return svg(o)


# ───────────────────────── 7. 네 일차에 걸쳐 에이전트에 더해진 것 ─────────────────────────

def added() -> str:
    boxes = ((30, 20), (790, 20), (30, 280), (790, 280))
    o: list[str] = []
    for i, (x, y) in enumerate(boxes):
        o.append(rect(x, y, 380, 220, 16, fill=PALE if i == 3 else LIGHT, stroke=SKY if i == 3 else "none", sw=3 if i == 3 else 0))
    for (x1, y1), (x2, y2) in (((414, 150), (520, 214)), ((786, 150), (680, 214)), ((414, 372), (520, 306)), ((786, 372), (680, 306))):
        o.append(line(x1, y1, x2, y2, stroke=NAVY, sw=4))
    o += [circle(600, 260, 96, fill=WHITE, sw=4)] + g(600, 266, 1.45, agent_icon(0, 0, ON))
    # 5일차: 목표와 도구, 정보원
    o += gear(110, 160, 34, ON, hot=True) + g(220, 160, 0.72, graph_icon(0, 0, ON)) + g(326, 156, 0.66, cylinder_db(0, 0, ON))
    # 6일차: 스킬과 MCP
    o += g(880, 164, 0.82, skill_doc(0, 0, ON))
    o += [rect(968, 134, 150, 60, 12, fill=WHITE), circle(1000, 164, 11, fill=SKY, sw=3), line(1011, 164, 1050, 164, sw=4),
          line(1050, 150, 1050, 178, sw=4), line(1118, 152, 1132, 152, sw=5), line(1118, 176, 1132, 176, sw=5)]
    # 7일차: 사람의 결정과 명세
    o += g(140, 420, 0.95, approve_icon(0, 0, ON))
    o += g(290, 424, 0.86, sop_doc(0, 0, ON))
    # 8일차: 시나리오와 회귀
    o += checklist(870, 356, 3, ON, w=220, gap=38, hot=(2,))
    return svg(o)


# ───────────────────────── 8. 쿨러 사건 한 건 위에 놓은 장치 ─────────────────────────

def incident() -> str:
    Y = 200
    xs = (90, 250, 410, 570, 730, 890, 1070)
    o = [rect(176, 96, 314, 214, 16, fill=LIGHT, stroke="none", sw=0), rect(650, 96, 320, 214, 16, fill=LIGHT, stroke="none", sw=0)]
    for a, b in zip(xs[:-1], xs[1:]):
        o.append(arrow([(a + 56, Y), (b - 58, Y)], NAVY, sw=4.5, size=12))
    o += [circle(xs[0], Y, 46, fill=PALE, sw=4)] + g(xs[0], Y - 3, 1.6, bell(0, 0, ON))
    o += g(xs[1], Y, 0.82, skill_doc(0, 0, ON))
    o += gear(xs[2], Y, 40, ON, hot=True)
    o += g(xs[3], Y, 0.44, ranking(0, 0, ON))
    o += [rect(xs[4] - 44, Y - 50, 88, 100, 10, fill=WHITE)] + check_mark(xs[4], Y - 18, 16) + check_mark(xs[4], Y + 22, 16)
    o += g(xs[5], Y - 4, 1.0, approve_icon(0, 0, ON))
    o += fan(xs[6], Y, 42, ON, rot=20, hot=True)
    # 전체를 덮는 검증
    o.append(path("M 50,356 L 50,378 L 1140,378 L 1140,356", stroke=BLUE, sw=4.5))
    o.append(arrow([(596, 378), (596, 408)], BLUE, sw=4.5, size=13))
    o += checklist(486, 412, 2, ON, w=220, gap=34, hot=(1,))
    return svg(o)


# ───────────────────────── 9. 근거가 놓인 자리: 지식과 현재값 ─────────────────────────

def crate(cx, cy, st: St, s=1.0, hot=False):
    """예비품 상자: 뚜껑 띠와 가새."""
    w, h = 64 * s, 52 * s
    return [rect(cx - w / 2, cy - h / 2, w, h, 5, fill=st.accent if hot else st.fill, stroke=st.line),
            line(cx - w / 2, cy - h / 2 + 14 * s, cx + w / 2, cy - h / 2 + 14 * s, stroke=st.line, sw=3),
            line(cx - w / 2 + 8 * s, cy - h / 2 + 22 * s, cx + w / 2 - 8 * s, cy + h / 2 - 8 * s, stroke=st.line, sw=2.5),
            line(cx + w / 2 - 8 * s, cy - h / 2 + 22 * s, cx - w / 2 + 8 * s, cy + h / 2 - 8 * s, stroke=st.line, sw=2.5)]


def bubble(cx, cy, st: St, w=70, h=46):
    """말풍선: 점 셋."""
    o = [path(f"M {cx - w / 2 + 10},{cy - h / 2} L {cx + w / 2 - 10},{cy - h / 2} Q {cx + w / 2},{cy - h / 2} {cx + w / 2},{cy - h / 2 + 10} "
              f"L {cx + w / 2},{cy + h / 2 - 10} Q {cx + w / 2},{cy + h / 2} {cx + w / 2 - 10},{cy + h / 2} L {cx - 4},{cy + h / 2} "
              f"L {cx - 18},{cy + h / 2 + 16} L {cx - 16},{cy + h / 2} L {cx - w / 2 + 10},{cy + h / 2} Q {cx - w / 2},{cy + h / 2} {cx - w / 2},{cy + h / 2 - 10} "
              f"L {cx - w / 2},{cy - h / 2 + 10} Q {cx - w / 2},{cy - h / 2} {cx - w / 2 + 10},{cy - h / 2} Z", fill=st.accent, stroke=st.line, sw=3)]
    for dx in (-16, 0, 16):
        o.append(circle(cx + dx, cy, 4, fill=st.line, stroke=st.line, sw=1))
    return o


def evidence_place() -> str:
    # 위: 지식(지식 그래프의 관계) · 아래: 현재값(판단하는 순간에 읽는 값)
    o = [rect(30, 16, 650, 226, 16, fill=LIGHT, stroke="none", sw=0), rect(30, 270, 650, 234, 16, fill=PALE, stroke=SKY, sw=3)]
    # 지식: 원인 후보 셋 → 고장 유형 → 조치 방법(SOP)
    for y in (58, 104, 150):
        o.append(arrow([(286, y), (388, 104 + (y - 104) * 0.35)], NAVY, sw=3.5, size=11))
        o.append(circle(268, y, 15, fill=WHITE, sw=3.5))
    o.append(circle(268, 58, 15, fill=SKY, sw=3.5))
    o += [circle(416, 104, 26, fill=PALE, sw=4), arrow([(446, 104), (530, 104)], NAVY, sw=4, size=12)]
    o += g(586, 104, 0.8, sop_doc(0, 0, ON))
    # 현재값: 시계열 DB(계기) · 업무 DB(표와 달력)
    o += g(300, 352, 0.92, cylinder_db(0, 0, ON)) + gauge(246, 318, ON, r=22, hot=True)
    o += g(540, 352, 0.92, table_icon(0, 0, ON)) + g(596, 318, 0.42, calendar_icon(0, 0, ON))
    # 도구 호출 → 추천안
    o += [arrow([(684, 128), (838, 128), (838, 206)], NAVY, sw=4.5, size=13), arrow([(684, 388), (838, 388), (838, 314)], BLUE, sw=4.5, size=13)]
    o += gear(838, 260, 46, ON, hot=True)
    o.append(arrow([(892, 260), (954, 260)], NAVY, sw=5, size=14))
    o += g(1066, 252, 0.84, ranking(0, 0, ON))
    return svg(o)


# ───────────────────────── 10. 검사를 통과한 것과 승인된 것 ─────────────────────────

def two_gates() -> str:
    Y = 176
    o = [rect(372, 76, 190, 204, 16, fill=LIGHT, stroke="none", sw=0), rect(742, 76, 190, 204, 16, fill=PALE, stroke=SKY, sw=3)]
    o += g(96, Y + 4, 1.15, agent_icon(0, 0, ON))
    o.append(arrow([(160, Y), (204, Y)], NAVY, sw=4.5, size=12))
    o += g(274, Y, 0.5, ranking(0, 0, ON))
    o.append(arrow([(342, Y), (404, Y)], NAVY, sw=4.5, size=12))
    # 자동 검사: 검사 항목 셋이 모두 통과한 문서
    o.append(rect(416, Y - 62, 102, 124, 10, fill=WHITE))
    for i in range(3):
        y = Y - 36 + i * 36
        o += check_mark(442, y, 11) + [line(462, y, 462 + (40, 30, 36)[i], y, stroke=NAVY, sw=3)]
    o.append(arrow([(566, Y), (606, Y)], NAVY, sw=4.5, size=12))
    o += clock(650, Y, 32, ON)
    o.append(arrow([(694, Y), (746, Y)], NAVY, sw=4.5, size=12))
    # 사람의 승인
    o += g(836, Y - 4, 1.2, approve_icon(0, 0, ON))
    o.append(arrow([(936, Y), (1010, Y)], BLUE, sw=5.5, size=15))
    o += fan(1078, Y, 50, ON, rot=20, hot=True)
    # 결정 기록
    o += dashed(836, 338, 836, 388, BLUE)
    o += g(836, 444, 0.62, sop_doc(0, 0, ON)) + [circle(872, 470, 15, fill=SKY, sw=3)] + [path("M 865,470 L 870,476 L 880,464", stroke=NAVY, sw=3)]
    # 에이전트 단계에서 사람이 들어가는 두 자리: 질문에 답하기, 멈춘 작업 닫기
    o += [line(88, 246, 94, 312, stroke=NAVY, sw=3, stroke_dasharray="7 7"), line(130, 246, 290, 316, stroke=NAVY, sw=3, stroke_dasharray="7 7")]
    o += g(95, 368, 0.8, person(0, 0, ON)) + g(143, 326, 0.62, bubble(0, 0, ON))
    o += g(300, 368, 0.8, person(0, 0, ON)) + cross_mark(340, 334, 15)
    return svg(o)


# ───────────────────────── 11. 세 에이전트의 산출물 ─────────────────────────

def three_outputs() -> str:
    rows = (108, 264, 420)
    o = [rect(262, 58, 316, 458, 16, fill=PALE, stroke=SKY, sw=3)]
    for y in rows:
        o += [arrow([(160, y), (256, y)], NAVY, sw=4.5, size=12), arrow([(584, y), (668, y)], BLUE, sw=5, size=14)]
        o += g(346, y + 2, 0.82, agent_icon(0, 0, ON)) + g(486, y, 0.6, skill_doc(0, 0, ON))
    # 업무의 시작: 경보 · 정기 정비 도래 · 재고 기준 이탈
    o += [circle(98, rows[0], 40, fill=PALE, sw=4)] + g(98, rows[0] - 3, 1.45, bell(0, 0, ON))
    o += g(98, rows[1] + 2, 0.72, calendar_icon(0, 0, ON))
    o += [line(52, rows[2] + 30, 144, rows[2] + 30, sw=4), line(52, rows[2] - 26, 144, rows[2] - 26, stroke=BLUE, sw=3, stroke_dasharray="8 7")]
    o += crate(80, rows[2] + 6, ON, s=0.7)
    o += [rect(104, rows[2] - 16, 34, 44, 4, fill=WHITE, stroke=GREY, sw=2.5, stroke_dasharray="6 6")]
    # 산출물: 추천안(순위와 팬) · 정비 시간(달력과 시계) · 발주안(견적 문서와 상자)
    o += g(748, rows[0], 0.5, ranking(0, 0, ON)) + fan(860, rows[0], 32, ON, rot=20, hot=True)
    o += g(744, rows[1] + 2, 0.86, calendar_icon(0, 0, ON)) + clock(852, rows[1], 28, ON, hot=True)
    o += g(738, rows[2], 0.72, sop_doc(0, 0, ON)) + crate(838, rows[2] + 14, ON, s=0.8, hot=True) + crate(872, rows[2] - 22, ON, s=0.62)
    return svg(o)


# ───────────────────────── 12. 실습 산출물이 다음 일로 넘어가는 길 ─────────────────────────

def handover() -> str:
    o = [rect(26, 60, 300, 446, 16, fill=LIGHT, stroke="none", sw=0), rect(400, 60, 470, 446, 16, fill=PALE, stroke=SKY, sw=3)]
    # 7일차: 확인 질문 · 명세와 기대 결과 · 초안과 검토 의견과 수정본
    o += g(112, 108, 0.6, sop_doc(0, 0, ON)) + g(160, 80, 0.6, bubble(0, 0, ON))
    o += spec_doc(72, 204, 86, 104, bands=2) + checklist(170, 220, 2, ON, w=96, gap=30)
    for i, dx in enumerate((0, 44, 88)):
        o += g(92 + dx, 424 - i * 6, 0.5, sop_doc(0, 0, ON if i == 2 else NORM))
    # 8일차: 시나리오 → 회귀 기록, 인수인계서
    o += checklist(440, 150, 3, ON, w=170, gap=38, marks=(None, None, None))
    o.append(arrow([(616, 216), (670, 216)], NAVY, sw=4.5, size=13))
    o += checklist(680, 150, 3, ON, w=170, gap=38, hot=(2,))
    o += g(600, 426, 0.66, sop_doc(0, 0, ON)) + clock(640, 452, 17, ON, hot=True)
    # 7일차 → 8일차
    o += [arrow([(206, 112), (350, 112), (350, 190), (432, 190)], NAVY, sw=4, size=12),
          arrow([(274, 256), (350, 256), (350, 240), (432, 240)], BLUE, sw=4.5, size=13)]
    # 8일차 → 다음 변경, 다음 교대
    o.append(arrow([(858, 216), (944, 216)], BLUE, sw=5, size=14))
    o += spec_doc(962, 156, 96, 116, bands=2) + [circle(1058, 162, 20, fill=SKY, sw=3.5), line(1047, 162, 1069, 162, sw=4.5), line(1058, 151, 1058, 173, sw=4.5)]
    o += checklist(1076, 186, 2, ON, w=98, gap=30)
    o.append(arrow([(660, 426), (944, 426)], NAVY, sw=4.5, size=13))
    o += g(1010, 426, 0.95, person(0, 0, ON)) + clock(1076, 404, 24, ON)
    return svg(o)


def main():
    out = {"명세와실행.svg": spec_run(), "세부분.svg": gwt(), "시나리오연결.svg": link(), "갈래.svg": branches(),
           "경계값.svg": boundary(), "회귀.svg": regression(), "더해진것.svg": added(), "사건위장치.svg": incident(),
           "근거자리.svg": evidence_place(), "두문.svg": two_gates(), "세산출물.svg": three_outputs(), "산출물이음.svg": handover()}
    for name, text in out.items():
        assert "<text" not in text
        (HERE / name).write_text(text, encoding="utf-8")
        print("wrote", name)


if __name__ == "__main__":
    main()
