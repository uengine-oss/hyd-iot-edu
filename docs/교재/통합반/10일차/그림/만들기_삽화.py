"""통합반 10일차 삽화(SVG)를 만든다. 글자는 넣지 않는다(라벨은 덱 MD의 요소로 얹는다).

화풍(선 굵기 · 색 · 그림 조각)은 `삽화_기본.py`(1일차의 것을 복사)에서 가져오고,
BPMN 도형과 승인 블록의 자리는 9일차의 `만들기_삽화.py`와 같게 그린다: 이벤트는 원(시작은 가는 테두리,
끝은 굵은 테두리, 경계는 겹테두리), 작업은 모서리가 둥근 사각형, 게이트웨이는 마름모, 시퀀스 흐름은 실선 화살표.
사용: python 만들기_삽화.py            → 이 폴더에 SVG를 쓴다
"""
from __future__ import annotations

import math
from pathlib import Path

from 삽화_기본 import (BLUE, GREY, LIGHT, NAVY, NORM, OFF, ON, PALE, SKY, WHITE, St, agent_icon, approve_icon, arrow,
                    bell, book_icon, calendar_icon, circle, cylinder_db, equip_mini, g, gauge, graph_icon, line, path,
                    poly, rect, server, svg)

HERE = Path(__file__).resolve().parent


# ───────────────────────── BPMN 도형 (9일차와 같다) ─────────────────────────

def envelope(cx, cy, w, st: St):
    h = w * 0.68
    return [rect(cx - w / 2, cy - h / 2, w, h, 2, fill=st.fill, stroke=st.line, sw=2.5),
            path(f"M {cx - w / 2},{cy - h / 2} L {cx},{cy + h * 0.08} L {cx + w / 2},{cy - h / 2}", stroke=st.line, sw=2.5)]


def clock(cx, cy, r, st: St):
    return [circle(cx, cy, r, fill=st.fill, stroke=st.line, sw=2.5),
            path(f"M {cx},{cy - r * 0.62} L {cx},{cy} L {cx + r * 0.5},{cy + r * 0.22}", stroke=st.line, sw=2.5)]


def ev(cx, cy, r=18, kind="start", st: St = ON, marker=None, dashed=False, fill=None):
    """이벤트. kind: start(가는 테두리) · end(굵은 테두리) · boundary(겹테두리, dashed면 비중단형)."""
    f = fill or st.fill
    if kind == "start":
        o = [circle(cx, cy, r, fill=f, stroke=st.line, sw=3)]
    elif kind == "end":
        o = [circle(cx, cy, r - 2, fill=f, stroke=st.line, sw=max(6.5, r * 0.3))]
    else:
        da = "7 6" if dashed else None
        o = [circle(cx, cy, r, fill=f, stroke=st.line, sw=2.5, stroke_dasharray=da),
             circle(cx, cy, r * 0.76, fill="none", stroke=st.line, sw=2.5, stroke_dasharray=da)]
    if marker == "message":
        o += envelope(cx, cy, r * 1.05, st)
    elif marker == "timer":
        o += clock(cx, cy, r * 0.5, st)
    return o


def user_mark(x, y, st: St, s=1.0):
    return [circle(x + 9 * s, y + 6 * s, 5.5 * s, fill=st.fill, stroke=st.line, sw=2.5),
            path(f"M {x},{y + 24 * s} Q {x},{y + 13 * s} {x + 9 * s},{y + 13 * s} Q {x + 18 * s},{y + 13 * s} {x + 18 * s},{y + 24 * s} Z",
                 fill=st.fill, stroke=st.line, sw=2.5)]


def gear_mark(x, y, st: St, s=1.0):
    cx, cy, r = x + 11 * s, y + 12 * s, 8 * s
    o = []
    for i in range(8):
        a = math.radians(i * 45)
        o.append(line(cx + r * math.cos(a), cy + r * math.sin(a), cx + (r + 4.5 * s) * math.cos(a), cy + (r + 4.5 * s) * math.sin(a),
                      stroke=st.line, sw=4 * s))
    o += [circle(cx, cy, r, fill=st.fill, stroke=st.line, sw=2.5), circle(cx, cy, r * 0.38, fill=st.line, stroke=st.line, sw=1)]
    return o


def task(cx, cy, w, h, st: St = ON, marker=None, fill=None, ms=1.0, r=12, dash=None, stroke=None):
    o = [rect(cx - w / 2, cy - h / 2, w, h, r, fill=fill or st.fill, stroke=stroke or st.line, stroke_dasharray=dash)]
    if marker == "user":
        o += user_mark(cx - w / 2 + 9, cy - h / 2 + 7, st, ms)
    elif marker == "service":
        o += gear_mark(cx - w / 2 + 6, cy - h / 2 + 4, st, ms)
    return o


def gateway(cx, cy, s=28, st: St = ON, kind="x", fill=None):
    o = [poly([(cx, cy - s), (cx + s, cy), (cx, cy + s), (cx - s, cy)], fill=fill or st.fill, stroke=st.line, sw=3.5)]
    k = s * 0.36
    o += [line(cx - k, cy - k, cx + k, cy + k, stroke=st.line, sw=max(4, s * 0.14)),
          line(cx + k, cy - k, cx - k, cy + k, stroke=st.line, sw=max(4, s * 0.14))]
    return o


def doc_icon(cx, cy, st: St, mark=None):
    o = [path(f"M {cx - 30},{cy - 42} L {cx + 14},{cy - 42} L {cx + 30},{cy - 26} L {cx + 30},{cy + 42} L {cx - 30},{cy + 42} Z",
              fill=st.fill, stroke=st.line),
         path(f"M {cx + 14},{cy - 42} L {cx + 14},{cy - 26} L {cx + 30},{cy - 26}", stroke=st.line, sw=2.5)]
    for dy in (-12, 2, 16):
        o.append(line(cx - 18, cy + dy, cx + 18, cy + dy, stroke=st.line, sw=2.5))
    if mark == "check":
        o += [circle(cx + 22, cy + 30, 16, fill=st.accent, stroke=st.line, sw=3),
              path(f"M {cx + 14},{cy + 30} L {cx + 20},{cy + 36} L {cx + 30},{cy + 24}", stroke=st.line, sw=3.5)]
    return o


def box(cx, cy, s, st: St, fill=None, dash=None, tag=False):
    """예비품 상자 하나. tag면 예약 꼬리표를 단다."""
    o = [rect(cx - s / 2, cy - s * 0.42, s, s * 0.84, 5, fill=fill or st.fill, stroke=st.line if not dash else GREY, stroke_dasharray=dash)]
    if not dash:
        o += [line(cx - s / 2, cy - s * 0.16, cx + s / 2, cy - s * 0.16, stroke=st.line, sw=2.5),
              line(cx, cy - s * 0.42, cx, cy - s * 0.16, stroke=st.line, sw=2.5)]
    if tag:
        o += [circle(cx + s * 0.34, cy + s * 0.36, s * 0.2, fill=WHITE, stroke=st.line, sw=3),
              line(cx + s * 0.26, cy + s * 0.44, cx + s * 0.42, cy + s * 0.28, stroke=st.line, sw=4)]
    return o


# ───────────────────────── 1. 세 업무의 시작 ─────────────────────────

def three_starts() -> str:
    o: list[str] = []
    for x0 in (20, 413, 806):
        o.append(rect(x0, 40, 374, 300, 14, fill=LIGHT, stroke="none", sw=0))
    # 긴급 대응: 설비의 계기가 한계로 오르고 경보가 난다
    o += g(140, 195, 1.55, equip_mini(0, 0, ON), boost=0.8)
    o += gauge(300, 140, ON, r=44, hot=True, ang=-28)
    o += g(300, 260, 2.1, bell(0, -2, ON), boost=0.6)
    # 정기 점검: 운전시간이 주기에 이른다
    o += g(533, 195, 1.55, equip_mini(0, 0, NORM), boost=0.8)
    o += g(693, 140, 0.82, calendar_icon(0, 0, ON), boost=1.1)
    o += clock(693, 262, 36, ON)
    # 재고 보충: 선반의 예비품이 기준 아래로 줄었다
    o += [rect(873, 80, 240, 220, 4, fill=WHITE), line(873, 190, 1113, 190)]
    for i, x in enumerate((925, 993, 1061)):
        o += box(x, 157, 52, ON, dash="6 6")
        o += box(x, 267, 52, ON, fill=SKY) if i == 0 else box(x, 267, 52, ON, dash="6 6")
    return svg(o)


# ───────────────────────── 2. 정기 점검 도래: 운전시간과 주기 ─────────────────────────

def pm_due() -> str:
    """운전시간 축. 0에서 끊김 표식까지는 줄여 그리고, 1,900~2,050 h 구간을 늘려 그린다."""
    o: list[str] = []
    y, x0, x1 = 300, 90, 1110
    px = lambda hour: 370 + (hour - 1900) * (740 / 150)      # noqa: E731
    xa, xd = px(1950), px(2000)
    o.append(rect(x0, y - 30, x1 - x0, 60, 30, fill=WHITE))
    o.append(path(f"M {x0 + 30},{y - 30} L {xa},{y - 30} L {xa},{y + 30} L {x0 + 30},{y + 30} A 30 30 0 0 1 {x0 + 30},{y - 30} Z",
                  fill=SKY, stroke=NAVY))
    for dx in (0, 22):                                             # 끊김 표식
        o.append(path(f"M {318 + dx},{y + 44} L {338 + dx},{y - 44}", stroke=WHITE, sw=11))
        o.append(path(f"M {318 + dx},{y + 44} L {338 + dx},{y - 44}", stroke=NAVY, sw=3))
    for hour in (1900, 2050):
        o.append(line(px(hour), y + 30, px(hour), y + 44, sw=3))
    # 알림 시점과 주기
    o.append(line(xa, y - 150, xa, y + 44, stroke=BLUE, sw=4))
    o.append(line(xd, y - 150, xd, y + 44, stroke=NAVY, sw=4, stroke_dasharray="9 8"))
    o += g(xa, y - 190, 2.3, bell(0, -2, ON), boost=0.6)
    o += g(xd, y - 190, 0.72, calendar_icon(0, 0, ON), boost=1.1)
    # 사전 알림 구간
    o.append(path(f"M {xa},{y + 62} L {xa},{y + 78} L {xd},{y + 78} L {xd},{y + 62}", stroke=BLUE, sw=4.5))
    o += g(185, y - 190, 1.2, equip_mini(0, 0, NORM), boost=0.9)
    return svg(o)


# ───────────────────────── 3. 재고 부족: 가용 재고와 재주문점 ─────────────────────────

def stock() -> str:
    o: list[str] = []
    xs = [300 + i * 118 for i in range(7)]
    # 윗줄: 현재고 셋 — 가용 하나, 정비에 예약된 둘
    y1, y2 = 120, 372
    o += box(xs[0], y1, 84, ON, fill=SKY)
    o += box(xs[1], y1, 84, NORM, fill=PALE, tag=True) + box(xs[2], y1, 84, NORM, fill=PALE, tag=True)
    o.append(arrow([(xs[0], y1 + 48), (xs[0], y2 - 52)], BLUE, sw=4.5, size=14))
    # 아랫줄: 가용 재고의 눈금 0~7
    o.append(line(xs[0] - 70, y2 + 50, xs[6] + 70, y2 + 50, sw=4))
    o += box(xs[0], y2, 84, ON, fill=SKY)
    for x in xs[1:]:
        o += box(x, y2, 84, ON, dash="7 7")
    xr = (xs[1] + xs[2]) / 2
    o.append(line(xr, y2 - 78, xr, y2 + 66, stroke=BLUE, sw=4.5, stroke_dasharray="10 8"))       # 재주문점 2
    xt = xs[6] + 59
    o.append(line(xt, y2 - 78, xt, y2 + 66, stroke=NAVY, sw=4.5))                                 # 목표 재고 7
    o.append(path(f"M {xs[1] - 46},{y2 + 72} L {xs[1] - 46},{y2 + 90} L {xs[6] + 46},{y2 + 90} L {xs[6] + 46},{y2 + 72}", stroke=NAVY, sw=4.5))
    return svg(o)


# ───────────────────────── 4. 세 프로세스를 나란히 ─────────────────────────

ROW_Y = (92, 256, 420)
ROW_TASKS = (4, 2, 3)


def three_rows() -> str:
    """세 프로세스의 뼈대: 시작 → 제안 → 승인 · 갈림 → 시스템 작업들 → 끝. 승인과 갈림의 자리에 띠를 깐다."""
    o: list[str] = []
    o.append(rect(290, 14, 256, 492, 14, fill=PALE, stroke="none", sw=0))
    xs_task = (632, 768, 904, 1040)
    for y, n in zip(ROW_Y, ROW_TASKS):
        xe = xs_task[n - 1] + 100
        o.append(arrow([(80, y), (120, y)], NAVY, sw=3.5, size=11))
        o.append(arrow([(262, y), (302, y)], NAVY, sw=3.5, size=11))
        o.append(arrow([(438, y), (460, y)], NAVY, sw=3.5, size=10))
        o.append(arrow([(516, y), (xs_task[0] - 62, y)], BLUE, sw=4, size=12))
        for a, b in zip(xs_task[:n - 1], xs_task[1:n]):
            o.append(arrow([(a + 62, y), (b - 62, y)], NAVY, sw=3.5, size=9))
        o.append(arrow([(xs_task[n - 1] + 62, y), (xe - 18, y)], NAVY, sw=3.5, size=10))
        o.append(arrow([(488, y + 28), (488, y + 52)], NAVY, sw=3.5, size=10))
        o += ev(60, y, 20, "start", ON, "message")
        o += task(190, y, 144, 84, ON, None, r=11)
        o += task(370, y, 136, 84, ON, "user", fill=WHITE, ms=0.6, r=11)
        o += gateway(488, y, 28, ON)
        o += ev(488, y + 66, 13, "end", ON)
        for x in xs_task[:n]:
            o += task(x, y, 124, 84, ON, "service", ms=0.5, r=10)
        o += ev(xe, y, 18, "end", ON)
    return svg(o)


# ───────────────────────── 5. 승인 블록: 같은 일곱 요소와 바뀌는 두 자리 ─────────────────────────

def approval_slots() -> str:
    o: list[str] = []
    o += task(140, 150, 200, 100, OFF, None, r=16)
    o.append(arrow([(240, 150), (330, 150)], GREY, sw=4.5, size=14))
    o += task(440, 150, 220, 110, ON, "user", fill=PALE, ms=1.4, r=16)
    o.append(arrow([(550, 150), (640, 150)], NAVY, sw=4.5, size=14))
    o += gateway(700, 150, 60, ON, fill=PALE)
    o.append(arrow([(760, 150), (900, 150)], NAVY, sw=4.5, size=14))
    o += task(1010, 150, 220, 100, ON, None, fill=WHITE, r=16, dash="12 9", stroke=BLUE)          # 바뀌는 자리: 승인 뒤의 첫 작업
    o.append(arrow([(700, 210), (700, 400), (790, 400)], NAVY, sw=4.5, size=14))
    o += task(900, 400, 220, 100, ON, "service", fill=PALE, ms=1.3, r=16)
    o.append(arrow([(1010, 400), (1110, 400)], NAVY, sw=4.5, size=14))
    o += ev(1140, 400, 28, "end", ON, fill=PALE)
    o += ev(500, 205, 28, "boundary", ON, "timer", dashed=True)
    o.append(arrow([(500, 233), (500, 400), (410, 400)], NAVY, sw=4.5, size=14))
    o += task(300, 400, 220, 100, ON, "service", fill=PALE, ms=1.3, r=16)
    o.append(arrow([(190, 400), (110, 400)], NAVY, sw=4.5, size=14))
    o += ev(80, 400, 28, "end", ON, fill=PALE)
    # 바뀌는 자리: 승인 역할
    o.append(circle(548, 96, 30, fill=WHITE, stroke=BLUE, sw=4, stroke_dasharray="9 7"))
    o += user_mark(539, 83, ON, 1.0)
    return svg(o)


# ───────────────────────── 6. 정기 점검 · 재고 보충 프로세스의 BPMN 그림 ─────────────────────────

LY = {"person": (10, 120), "agent": (120, 260), "system": (260, 510)}
TW, TH = 132, 72
BLOCK_N = {"Start": (148, 172), "T_agent": (255, 172), "T_approve": (372, 65), "G_approved": (500, 65),
           "R_rejected": (581, 400), "E_rejected": (581, 482), "T_notice": (410, 400), "E_notice": (410, 482), "B_overdue": (410, 101)}
BLOCK_F = {
    "F1": [(166, 172), (180, 172)],
    "F2": [(330, 172), (345, 172), (345, 101)],
    "F3": [(447, 65), (472, 65)],
    "F_approved": [(500, 93), (500, 269)],
    "F_rejected": [(528, 65), (581, 65), (581, 364)],
    "F_rej_end": [(581, 436), (581, 464)],
    "F_overdue": [(410, 119), (410, 364)],
    "F_notice_end": [(410, 436), (410, 464)],
}
BLOCK_IDS = {"T_approve", "B_overdue", "T_notice", "G_approved", "R_rejected", "E_notice", "E_rejected",
             "F3", "F_approved", "F_rejected", "F_rej_end", "F_overdue", "F_notice_end"}
WIDE = {"T_wo": 148, "T_po": 148, "T_approve": 150}       # 이름이 긴 작업(승인 지연 선 x=410과 거절 선 x=581 사이에 들어가는 폭)
PROC = {
    "pm": ({"T_wo": (498, 305), "R_ok": (760, 305), "E_end": (1000, 305)},
           {"F4": [(572, 305), (694, 305)], "F5": [(826, 305), (982, 305)]}),
    "spare": ({"T_po": (498, 305), "T_gr": (720, 305), "R_ok": (940, 305), "E_end": (1130, 305)},
              {"F4": [(572, 305), (654, 305)], "F5": [(786, 305), (874, 305)], "F6": [(1006, 305), (1112, 305)]}),
}


def flow(which: str) -> str:
    """정기 점검('pm') · 재고 보충('spare') 프로세스. 승인 블록의 요소와 선은 9일차의 긴급 대응 그림과 같은 자리에 두고 하늘색으로 칠한다."""
    own_n, own_f = PROC[which]
    nodes = {**BLOCK_N, **own_n}
    flows = {**BLOCK_F, **own_f}
    o: list[str] = []
    o.append(rect(8, 10, 1184, 500, 4, fill=WHITE))
    o.append(rect(8, 10, 92, 500, 4, fill=LIGHT))
    for y in (120, 260):
        o.append(line(8, y, 1192, y, sw=3))
    o.append(line(100, 10, 100, 510, sw=3))
    o += g(54, 44, 0.42, approve_icon(-4, 0, ON))
    o += g(54, 160, 0.42, agent_icon(0, 6, ON))
    o += g(54, 360, 0.42, server(0, 0, ON))
    for fid, pts in flows.items():
        hot = fid in BLOCK_IDS
        o.append(arrow(pts, BLUE if hot else NAVY, sw=4 if hot else 3.2, size=11))

    def tk(name, marker, w=TW):
        w = WIDE.get(name, w)
        return task(*nodes[name], w, TH, ON, marker, fill=PALE if name in BLOCK_IDS else WHITE, ms=0.6)

    o += ev(*nodes["Start"], 18, "start", ON, "message")
    o += tk("T_agent", None, 150) + tk("T_approve", "user")
    for name in nodes:
        if name[0] in "TR" and name not in ("T_agent", "T_approve"):
            o += tk(name, "service")
    o += gateway(*nodes["G_approved"], 28, ON, fill=PALE)
    for name in ("E_end", "E_rejected", "E_notice"):
        o += ev(*nodes[name], 18, "end", ON, fill=PALE if name in BLOCK_IDS else None)
    o += ev(*nodes["B_overdue"], 18, "boundary", ON, "timer", dashed=True)
    return svg(o)


# ───────────────────────── 7. 단계별 걸린 시간 (실제 기록) ─────────────────────────

# 승인된 처리 건 세 건의 단계별 걸린 시간(초). 순서: 에이전트 단계, 승인 단계, 시스템 단계들.
DUR = {"A": (82.3, 1.3, (1.1, 60.2, 1.0, 0.3)), "B": (55.3, 3.7, (1.0, 0.4)), "C": (54.4, 1.7, (0.3, 0.9, 0.4))}
BAR_X0, BAR_K = 190, 6.2


def bottleneck() -> str:
    o: list[str] = []
    for sec in (0, 30, 60, 90, 120, 150):
        x = BAR_X0 + sec * BAR_K
        o.append(line(x, 70, x, 470, stroke=GREY, sw=2.5))
    o.append(line(BAR_X0, 470, BAR_X0 + 150 * BAR_K, 470, sw=3.5))
    for key, y in zip("ABC", (140, 270, 400)):
        agent, human, systems = DUR[key]
        x = BAR_X0
        h = 62
        w = agent * BAR_K
        o.append(rect(x, y - h / 2, w, h, 6, fill=SKY))
        o += g(x + 46, y, 0.44, agent_icon(0, 4, ON))
        x += w
        w = max(human * BAR_K, 7)
        o.append(rect(x, y - h / 2, w, h, 2, fill=NAVY))
        x += w
        for s in systems:
            w = max(s * BAR_K, 5)
            o.append(rect(x, y - h / 2, w, h, 3 if w > 20 else 1, fill=PALE, sw=2.5 if w < 20 else 3.5))
            x += w
    return svg(o)


# ───────────────────────── 8. 처리 건이 지나는 다섯 자리 ─────────────────────────

FIVE_X = (130, 365, 600, 835, 1070)


def five_places() -> str:
    o: list[str] = []
    y, r = 190, 66
    for a, b in zip(FIVE_X, FIVE_X[1:]):
        o.append(arrow([(a + r + 8, y), (b - r - 10, y)], NAVY, sw=5, size=15))
    for i, x in enumerate(FIVE_X):
        o.append(circle(x, y, r, fill=PALE if i == 2 else WHITE, sw=4))
    o += ev(FIVE_X[0], y, 34, "start", ON, "message")
    o += g(FIVE_X[1], y, 0.9, agent_icon(0, 6, ON), boost=1.05)
    o += g(FIVE_X[2], y, 0.9, approve_icon(-4, -4, ON), boost=1.05)
    o += g(FIVE_X[3], y, 0.78, server(0, 0, ON), boost=1.1)
    o += g(FIVE_X[4], y, 0.9, doc_icon(0, 0, ON, "check"), boost=1.05)
    # 반려: 시스템의 처리를 지나지 않고 종료 기록으로 간다
    x1, x2, yb = FIVE_X[2], FIVE_X[4], 400
    o.append(path(f"M {x1},{y + r + 6} L {x1},{yb} L {x2},{yb} L {x2},{y + r + 26}", stroke=BLUE, sw=4.5, stroke_dasharray="11 9"))
    o.append(poly([(x2, y + r + 8), (x2 - 10, y + r + 28), (x2 + 10, y + r + 28)], fill=BLUE))
    return svg(o)


# ───────────────────────── 9. 온톨로지 → 에이전트 → 프로세스 ─────────────────────────

def three_layers() -> str:
    o: list[str] = []
    for x0, w, fill in ((20, 350, LIGHT), (425, 290, LIGHT), (770, 410, PALE)):
        o.append(rect(x0, 60, w, 330, 14, fill=fill, stroke="none", sw=0))
    o.append(arrow([(374, 225), (421, 225)], BLUE, sw=6, size=17))
    o.append(arrow([(719, 225), (766, 225)], BLUE, sw=6, size=17))
    # 지식: 지식 그래프, 문서에서 온 지식, 값이 놓인 곳
    o += g(120, 160, 1.15, graph_icon(0, 0, ON), boost=0.9)
    o += g(275, 165, 0.8, book_icon(0, 0, ON), boost=1.1)
    o += g(195, 305, 0.78, cylinder_db(0, 0, ON), boost=1.1)
    # 에이전트
    o += g(570, 230, 1.6, agent_icon(0, 6, ON), boost=0.75)
    # 프로세스: 제안 → 승인 → 갈림 → 처리 → 끝
    y = 225
    o += ev(812, y, 16, "start", ON, "message")
    o += task(880, y, 72, 56, ON, None, r=9) + task(968, y, 72, 56, ON, "user", fill=WHITE, ms=0.5, r=9)
    o += gateway(1036, y, 22, ON) + task(1100, y, 72, 56, ON, "service", ms=0.5, r=9) + ev(1160, y, 14, "end", ON)
    for a, b in ((828, 844), (916, 932), (1004, 1014), (1058, 1064), (1136, 1146)):
        o.append(arrow([(a, y), (b, y)], NAVY, sw=3, size=8))
    o.append(arrow([(1036, y + 22), (1036, y + 78), (1066, y + 78)], NAVY, sw=3, size=8))
    o += ev(1084, y + 78, 13, "end", ON)
    return svg(o)


# ───────────────────────── 10. 세 그림에 쓰인 BPMN 요소 ─────────────────────────

def symbols() -> str:
    o: list[str] = []
    xs = [95 + i * 168 for i in range(7)]
    y = 170
    o += ev(xs[0], y, 46, "start", ON, "message", fill=PALE)
    o += task(xs[1], y, 136, 92, ON, None, fill=PALE, r=16)
    o += task(xs[2], y, 136, 92, ON, "user", ms=1.2, r=16)
    o += task(xs[3], y, 136, 92, ON, "service", ms=1.2, r=16)
    o += gateway(xs[4], y, 54, ON)
    o += ev(xs[5], y, 46, "boundary", ON, "timer", dashed=True)
    o += ev(xs[6], y, 46, "end", ON)
    return svg(o)


# ───────────────────────── 11. 한 처리 건 안에서 주고받는 것 ─────────────────────────

HAND_X = (110, 355, 600, 845, 1090)


def packet(cx, cy, st: St = ON):
    """자리 사이를 건너가는 것(문서 한 장)."""
    return [rect(cx - 34, cy - 44, 68, 88, 7, fill=PALE, stroke=BLUE, sw=3.5),
            *[line(cx - 20, cy + dy, cx + 20, cy + dy, stroke=BLUE, sw=3) for dy in (-22, -6, 10)],
            line(cx - 20, cy + 26, cx + 4, cy + 26, stroke=BLUE, sw=3)]


def handoff() -> str:
    o: list[str] = []
    y, r = 150, 50
    for a, b in zip(HAND_X, HAND_X[1:]):
        o.append(arrow([(a + r + 6, y), (b - r - 8, y)], NAVY, sw=4.5, size=14))
        o += packet((a + b) / 2, y)
    for x in HAND_X:
        o.append(circle(x, y, r, fill=WHITE, sw=4))
    o += ev(HAND_X[0], y, 27, "start", ON, "message")
    o += g(HAND_X[1], y, 0.7, agent_icon(0, 6, ON), boost=1.15)
    o += g(HAND_X[2], y, 0.7, approve_icon(-4, -4, ON), boost=1.15)
    o += g(HAND_X[3], y, 0.62, server(0, 0, ON), boost=1.2)
    o += g(HAND_X[4], y, 0.7, doc_icon(0, 0, ON, "check"), boost=1.15)
    return svg(o)


# ───────────────────────── 12. 세 업무가 끝난 모습 ─────────────────────────

def check_mark(cx, cy, r=22):
    return [circle(cx, cy, r, fill=SKY, stroke=NAVY, sw=3.5),
            path(f"M {cx - r * 0.42},{cy + r * 0.02} L {cx - r * 0.1},{cy + r * 0.36} L {cx + r * 0.46},{cy - r * 0.32}", stroke=NAVY, sw=4.5)]


def three_ends() -> str:
    o: list[str] = []
    for x0 in (20, 413, 806):
        o.append(rect(x0, 40, 374, 300, 14, fill=LIGHT, stroke="none", sw=0))
    # 긴급 대응: 계기가 내려오고 작업지시가 남았다
    o += g(140, 195, 1.55, equip_mini(0, 0, NORM), boost=0.8)
    o += gauge(300, 140, ON, r=44, hot=False, ang=-140)
    o += g(300, 262, 0.8, doc_icon(0, 0, ON, "check"), boost=1.1)
    # 정기 점검: 정비 오더가 등록되고 공지가 나갔다
    o += g(533, 195, 1.55, equip_mini(0, 0, NORM), boost=0.8)
    o += g(693, 140, 0.8, doc_icon(0, 0, ON, "check"), boost=1.1)
    o += envelope(693, 262, 76, ON)
    # 재고 보충: 선반에 가용 재고 일곱
    o += [rect(858, 80, 270, 220, 4, fill=WHITE), line(858, 190, 1128, 190)]
    for i, x in enumerate((895, 961, 1027, 1093)):
        o += box(x, 157, 50, ON, fill=SKY)
        o += box(x, 267, 50, ON, fill=SKY) if i < 3 else box(x, 267, 50, ON, dash="6 6")
    return svg(o)


def main():
    out = {"세시작.svg": three_starts(), "운전시간.svg": pm_due(), "재고.svg": stock(), "세흐름_나란히.svg": three_rows(),
           "승인블록_자리.svg": approval_slots(), "흐름_정기점검.svg": flow("pm"), "흐름_재고보충.svg": flow("spare"),
           "병목.svg": bottleneck(), "다섯자리.svg": five_places(), "세층연결.svg": three_layers(), "요소_복습.svg": symbols(),
           "주고받는것.svg": handoff(), "세종료.svg": three_ends()}
    for name, text in out.items():
        assert "<text" not in text
        (HERE / name).write_text(text, encoding="utf-8")
        print("wrote", name)


if __name__ == "__main__":
    main()
