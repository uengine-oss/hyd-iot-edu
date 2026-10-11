"""통합반 11일차 삽화(SVG)를 만든다. 글자는 넣지 않는다(라벨은 덱 MD의 요소로 얹는다).

화풍(선 굵기 · 색 · 그림 조각)은 1일차의 `만들기_삽화.py`를 복사한 `삽화_기본.py`에서 가져온다.
BPMN 도형은 표준 기호 모양을 따른다: 이벤트는 원(시작은 가는 테두리, 끝은 굵은 테두리, 경계는 겹테두리),
작업은 모서리가 둥근 사각형, 게이트웨이는 마름모, 시퀀스 흐름은 실선 화살표, 메시지 흐름은 점선 화살표.
사용: python 만들기_삽화.py            → 이 폴더에 SVG를 쓴다
"""
from __future__ import annotations

import math
from pathlib import Path

from 삽화_기본 import (BLUE, GREY, LIGHT, NAVY, NORM, OFF, ON, PALE, SKY, WHITE, St, agent_icon, approve_icon, arrow,
                    bell, book_icon, calendar_icon, circle, cylinder_db, gauge, g, graph_icon, line, logstrip, monitor, path, plc, poly,
                    rect, server, svg)

HERE = Path(__file__).resolve().parent


# ───────────────────────── BPMN 도형 ─────────────────────────

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


def task(cx, cy, w, h, st: St = ON, marker=None, fill=None, ms=1.0, r=12):
    o = [rect(cx - w / 2, cy - h / 2, w, h, r, fill=fill or st.fill, stroke=st.line)]
    if marker == "user":
        o += user_mark(cx - w / 2 + 9, cy - h / 2 + 7, st, ms)
    elif marker == "service":
        o += gear_mark(cx - w / 2 + 6, cy - h / 2 + 4, st, ms)
    return o


def gateway(cx, cy, s=28, st: St = ON, kind="x", fill=None):
    o = [poly([(cx, cy - s), (cx + s, cy), (cx, cy + s), (cx - s, cy)], fill=fill or st.fill, stroke=st.line, sw=3.5)]
    k = s * 0.36
    if kind == "x":
        o += [line(cx - k, cy - k, cx + k, cy + k, stroke=st.line, sw=max(4, s * 0.14)),
              line(cx + k, cy - k, cx - k, cy + k, stroke=st.line, sw=max(4, s * 0.14))]
    else:
        k = s * 0.48
        o += [line(cx - k, cy, cx + k, cy, stroke=st.line, sw=max(4, s * 0.14)),
              line(cx, cy - k, cx, cy + k, stroke=st.line, sw=max(4, s * 0.14))]
    return o


def msgflow(pts, color=NAVY, sw=3.5):
    """메시지 흐름: 점선, 출발에 빈 원, 도착에 빈 화살촉."""
    (x1, y1), (x2, y2) = pts[-2], pts[-1]
    ang = math.atan2(y2 - y1, x2 - x1)
    d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    a1, a2 = ang + math.radians(152), ang - math.radians(152)
    hd = poly([(x2, y2), (x2 + 16 * math.cos(a1), y2 + 16 * math.sin(a1)), (x2 + 16 * math.cos(a2), y2 + 16 * math.sin(a2))],
              fill=WHITE, stroke=color, sw=3)
    return [path(d, stroke=color, sw=sw, stroke_dasharray="10 8"), circle(pts[0][0], pts[0][1], 6, fill=WHITE, stroke=color, sw=3), hd]


def token(cx, cy, r=13):
    return [circle(cx, cy, r + 6, fill=WHITE, stroke=BLUE, sw=2.5), circle(cx, cy, r - 2, fill=BLUE, stroke=BLUE, sw=1)]


def check_mark(cx, cy, r=22, st: St = ON):
    return [circle(cx, cy, r, fill=SKY if st is ON else WHITE, stroke=st.line, sw=3.5),
            path(f"M {cx - r * 0.42},{cy + r * 0.02} L {cx - r * 0.1},{cy + r * 0.36} L {cx + r * 0.46},{cy - r * 0.32}", stroke=st.line, sw=4.5)]


def cross_mark(cx, cy, r=22, st: St = ON):
    return [circle(cx, cy, r, fill=WHITE, stroke=st.line, sw=3.5),
            line(cx - r * 0.36, cy - r * 0.36, cx + r * 0.36, cy + r * 0.36, stroke=st.line, sw=4.5),
            line(cx + r * 0.36, cy - r * 0.36, cx - r * 0.36, cy + r * 0.36, stroke=st.line, sw=4.5)]


def doc_icon(cx, cy, st: St, mark=None):
    o = [path(f"M {cx - 30},{cy - 42} L {cx + 14},{cy - 42} L {cx + 30},{cy - 26} L {cx + 30},{cy + 42} L {cx - 30},{cy + 42} Z",
              fill=st.fill, stroke=st.line),
         path(f"M {cx + 14},{cy - 42} L {cx + 14},{cy - 26} L {cx + 30},{cy - 26}", stroke=st.line, sw=2.5)]
    for dy in (-12, 2, 16):
        o.append(line(cx - 18, cy + dy, cx + 18, cy + dy, stroke=st.line, sw=2.5))
    if mark == "check":
        o += [circle(cx + 22, cy + 30, 16, fill=st.accent, stroke=st.line, sw=3),
              path(f"M {cx + 14},{cy + 30} L {cx + 20},{cy + 36} L {cx + 30},{cy + 24}", stroke=st.line, sw=3.5)]
    elif mark == "wrench":
        o += [circle(cx + 22, cy + 30, 16, fill=st.accent, stroke=st.line, sw=3),
              line(cx + 14, cy + 38, cx + 28, cy + 24, stroke=st.line, sw=4.5)]
    return o


def person_icon(cx, cy, st: St):
    return [circle(cx, cy - 20, 17, fill=st.fill, stroke=st.line),
            path(f"M {cx - 34},{cy + 38} Q {cx - 34},{cy + 4} {cx},{cy + 4} Q {cx + 34},{cy + 4} {cx + 34},{cy + 38} Z", fill=st.soft, stroke=st.line)]


def phone_icon(cx, cy, st: St):
    return [rect(cx - 20, cy - 36, 40, 72, 8, fill=st.fill, stroke=st.line), line(cx - 8, cy + 26, cx + 8, cy + 26, stroke=st.line, sw=3),
            rect(cx - 13, cy - 26, 26, 40, 3, fill=st.soft, stroke=st.line, sw=2)]

# ───────────────────────── 2. BPM 생애주기 ─────────────────────────

def magnifier(cx, cy, st: St):
    return [circle(cx - 8, cy - 8, 26, fill=st.accent, stroke=st.line), line(cx + 12, cy + 12, cx + 36, cy + 36, stroke=st.line, sw=8)]


def mini_bpmn(cx, cy, st: St):
    return [line(cx - 34, cy, cx + 30, cy, stroke=st.line, sw=3), circle(cx - 40, cy, 9, fill=st.fill, stroke=st.line, sw=3),
            rect(cx - 22, cy - 13, 30, 26, 5, fill=st.accent, stroke=st.line, sw=3),
            poly([(cx + 30, cy - 15), (cx + 45, cy), (cx + 30, cy + 15), (cx + 15, cy)], fill=st.fill, stroke=st.line, sw=3)]


def play_icon(cx, cy, st: St):
    return [circle(cx, cy, 34, fill=st.accent, stroke=st.line), poly([(cx - 10, cy - 17), (cx + 18, cy), (cx - 10, cy + 17)], fill=st.line)]


def improve_icon(cx, cy, st: St):
    o = [rect(cx - 36 + i * 26, cy + 22 - h, 20, h, 3, fill=st.accent if i == 2 else st.soft, stroke=st.line, sw=3) for i, h in enumerate((20, 36, 54))]
    return o + [arrow([(cx - 38, cy - 10), (cx - 6, cy - 34)], BLUE if st is ON else st.line, sw=4, size=11)]




# ───────────────────────── 11일차 그림 ─────────────────────────

def put(cx, cy, k, parts, boost=1.1):
    return g(cx, cy, k, parts, boost=boost)


def node(cx, cy, st: St, parts, r=54):
    return [circle(cx, cy, r, fill=PALE if st is ON else WHITE, stroke=st.line, sw=4 if st is not OFF else 3),
            f'<g transform="translate({cx} {cy})">', *parts, "</g>"]


def brace(x1, x2, y, up, color, sw=5):
    t = -14 if up else 14
    return path(f"M {x1},{y + t} L {x1},{y} L {x2},{y} L {x2},{y + t}", stroke=color, sw=sw)


def lock_icon(cx, cy, st: St, s=1.0):
    return [path(f"M {cx - 11 * s},{cy - 4 * s} L {cx - 11 * s},{cy - 14 * s} A {11 * s} {11 * s} 0 0 1 {cx + 11 * s},{cy - 14 * s} L {cx + 11 * s},{cy - 4 * s}",
                 stroke=st.line, sw=4),
            rect(cx - 17 * s, cy - 4 * s, 34 * s, 26 * s, 5, fill=st.accent, stroke=st.line, sw=3),
            circle(cx, cy + 8 * s, 3.5 * s, fill=st.line, stroke=st.line, sw=1)]


def table_icon(cx, cy, st: St):
    o = [rect(cx - 46, cy - 36, 92, 72, 6, fill=st.fill, stroke=st.line), rect(cx - 46, cy - 36, 92, 20, 6, fill=st.accent, stroke=st.line)]
    for dy in (2, 20):
        o.append(line(cx - 46, cy + dy, cx + 46, cy + dy, stroke=st.line, sw=2.5))
    for dx in (-16, 16):
        o.append(line(cx + dx, cy - 16, cx + dx, cy + 36, stroke=st.line, sw=2.5))
    return o


def scale_icon(cx, cy, st: St):
    return [line(cx, cy - 34, cx, cy + 34, stroke=st.line, sw=4), line(cx - 22, cy + 36, cx + 22, cy + 36, stroke=st.line, sw=5),
            line(cx - 40, cy - 24, cx + 40, cy - 24, stroke=st.line, sw=4),
            path(f"M {cx - 56},{cy + 6} A 16 12 0 0 0 {cx - 24},{cy + 6} Z", fill=st.accent, stroke=st.line, sw=3),
            path(f"M {cx + 24},{cy + 6} A 16 12 0 0 0 {cx + 56},{cy + 6} Z", fill=st.soft, stroke=st.line, sw=3),
            line(cx - 40, cy - 24, cx - 54, cy + 6, stroke=st.line, sw=2.5), line(cx - 40, cy - 24, cx - 26, cy + 6, stroke=st.line, sw=2.5),
            line(cx + 40, cy - 24, cx + 26, cy + 6, stroke=st.line, sw=2.5), line(cx + 40, cy - 24, cx + 54, cy + 6, stroke=st.line, sw=2.5)]


def send_icon(cx, cy, st: St):
    return [poly([(cx - 40, cy - 6), (cx + 42, cy - 36), (cx + 14, cy + 40), (cx - 2, cy + 8)], fill=st.accent, stroke=st.line, sw=3.5),
            line(cx - 2, cy + 8, cx + 42, cy - 36, stroke=st.line, sw=3)]


def engine_icon(cx, cy, st: St):
    """프로세스 엔진: 작은 흐름 그림이 든 상자와 톱니."""
    return ([rect(cx - 74, cy - 52, 148, 104, 14, fill=st.fill, stroke=st.line, sw=4)] + mini_bpmn(cx - 2, cy - 14, st)
            + gear_mark(cx + 34, cy + 12, st, 1.5))


CH_X = (75, 225, 375, 525, 675, 825, 975, 1125)


def chain_nodes(y, sts):
    o = []
    for i in range(7):
        s = sts[i + 1]
        o.append(arrow([(CH_X[i] + 56, y), (CH_X[i + 1] - 58, y)], GREY if s is OFF else NAVY, sw=4, size=12))
    fns = [lambda s: put(0, 0, 1.9, bell(0, -2, s), 0.6), lambda s: put(0, 0, 0.78, agent_icon(0, 4, s)),
           lambda s: put(0, 0, 0.78, approve_icon(-4, -4, s)), lambda s: put(0, 0, 0.62, plc(0, 0, s), 1.2),
           lambda s: gauge(0, 0, s, r=30, hot=s is ON, ang=-120), lambda s: put(0, 0, 0.7, doc_icon(0, 0, s, "wrench")),
           lambda s: put(0, 0, 0.7, doc_icon(0, 0, s, "check"))]
    for i, fn in enumerate(fns):
        o += node(CH_X[i], y, sts[i], fn(sts[i]))
    o += ev(CH_X[7], y, 30, "end", sts[7])
    return o


def knowledge_block(x, y, w, h, st: St):
    o = [rect(x, y, w, h, 14, fill=LIGHT if st is not ON else PALE, stroke="none", sw=0)]
    step = w / 4
    icons = [graph_icon, book_icon, cylinder_db, table_icon]
    for i, fn in enumerate(icons):
        o += put(x + step * (i + 0.5), y + h * 0.42, 0.62, fn(0, 0, st))
    return o


def event_line(mode: str) -> str:
    """사건 한 건의 줄. all: 전체 / areas: 세 영역의 구간 / u1: 경보~판단 제출 / u2: 승인~끝."""
    o: list[str] = []
    y = 215 if mode != "all" else 230
    if mode == "all":
        sts = [NORM] * 8
    elif mode == "areas":
        sts = [NORM, ON, NORM, NORM, NORM, NORM, NORM, NORM]
    elif mode == "u1":
        sts = [NORM, ON] + [OFF] * 6
    else:
        sts = [NORM, NORM, ON, ON, ON, ON, ON, NORM]
    if mode != "all":
        kst = OFF if mode == "u2" else (ON if mode == "u1" else NORM)
        o += knowledge_block(40, 345, 370, 150, kst)
        o.append(arrow([(225, 345), (225, y + 62)], GREY if mode == "u2" else BLUE, sw=5, size=14))
    o += chain_nodes(y, sts)
    if mode == "areas":
        o.append(brace(CH_X[0] - 58, CH_X[7] + 40, 52, False, NAVY, 5))
    if mode == "u2":
        o.append(brace(CH_X[2] - 60, CH_X[7] + 40, y + 76, True, BLUE, 5))
    return svg(o)


def calls_knowledge() -> str:
    """위: 에이전트의 호출 순서. 아래: 호출마다 읽은 지식과 값."""
    o = [rect(14, 20, 1172, 220, 14, fill=LIGHT, stroke="none", sw=0), rect(14, 310, 1172, 196, 14, fill=LIGHT, stroke="none", sw=0)]
    xs = [90, 330, 560, 790, 1010]
    y = 160
    for a, b in zip(xs, xs[1:]):
        o.append(arrow([(a + 58, y), (b - 60, y)], NAVY, sw=4, size=12))
    o += node(xs[0], y, NORM, put(0, 0, 1.9, bell(0, -2, NORM), 0.6))
    o += node(xs[1], y, ON, put(4, 4, 0.8, magnifier(0, 0, ON)))
    o += node(xs[2], y, ON, put(0, 0, 0.62, scale_icon(0, 0, ON)))
    o += node(xs[3], y, ON, put(0, 0, 0.6, table_icon(0, 0, ON)))
    o += node(xs[4], y, ON, put(0, 0, 0.6, send_icon(0, 0, ON)))
    ky = 392
    stores = [(200, graph_icon, xs[1] - 24), (380, cylinder_db, xs[1] + 24), (560, book_icon, xs[2]), (790, table_icon, xs[3])]
    for x, fn, tx in stores:
        o += put(x, ky, 0.72, fn(0, 0, NORM))
        if x == tx:
            o.append(arrow([(x, ky - 50), (x, y + 62)], BLUE, sw=5, size=14))
        else:
            o.append(arrow([(x, ky - 50), (x, 276), (tx, 276), (tx, y + 60)], BLUE, sw=5, size=14))
    return svg(o)


def system_exec() -> str:
    """승인 뒤의 시스템 실행: 엔진이 설비, 시계열 DB, 업무 시스템을 차례로 부른다."""
    o: list[str] = []
    o += node(110, 260, NORM, put(0, 0, 0.78, approve_icon(-4, -4, NORM)))
    o.append(arrow([(168, 260), (322, 260)], NAVY, sw=5, size=14))
    o += engine_icon(400, 260, ON)
    ys = (100, 260, 420)
    for i, ty in enumerate(ys):
        o.append(rect(690, ty - 72, 470, 144, 14, fill=LIGHT, stroke="none", sw=0))
    o.append(arrow([(476, 240), (560, 240), (560, 100), (760, 100)], BLUE, sw=5, size=14))
    o.append(arrow([(760, 260), (478, 260)], NAVY, sw=5, size=14))
    o.append(arrow([(476, 280), (560, 280), (560, 420), (760, 420)], BLUE, sw=5, size=14))
    o += node(820, 100, ON, put(0, 0, 0.62, plc(0, 0, ON), 1.2), r=52)
    o += node(820, 260, NORM, put(-4, -2, 0.6, cylinder_db(0, 0, NORM)), r=52)
    o += node(820, 420, ON, put(0, 0, 0.7, doc_icon(0, 0, ON, "wrench")), r=52)
    return svg(o)


def three_areas() -> str:
    """지식 · 에이전트 · 프로세스가 주고받는 것."""
    o: list[str] = []
    xs = (150, 600, 1050)
    for x in xs:
        o.append(rect(x - 130, 110, 260, 260, 16, fill=LIGHT, stroke="none", sw=0))
    o += put(xs[0] - 56, 215, 0.72, graph_icon(0, 0, NORM))
    o += put(xs[0] + 58, 215, 0.66, book_icon(0, 0, NORM))
    o += node(xs[1], 215, ON, put(0, 0, 0.84, agent_icon(0, 4, ON)), r=62)
    o += engine_icon(xs[2], 215, NORM)
    o.append(arrow([(xs[0] + 140, 240), (xs[1] - 140, 240)], BLUE, sw=6, size=16))
    o.append(arrow([(xs[1] + 140, 240), (xs[2] - 140, 240)], BLUE, sw=6, size=16))
    o.append(arrow([(xs[2], 372), (xs[2], 420)], NAVY, sw=5, size=14))
    o += logstrip(xs[2] - 96, 452, NORM, n=8, cw=24, h=44)
    return svg(o)


def five_layers() -> str:
    o: list[str] = []
    top, pitch, hgt = 14, 100, 86
    icons = [lambda s: put(0, 0, 0.58, monitor(0, 0, s, "hmi")), lambda s: put(0, 0, 0.9, mini_bpmn(0, 0, s)),
             lambda s: put(0, 0, 0.6, graph_icon(0, 0, s)), lambda s: put(0, 0, 0.58, agent_icon(0, 4, s)),
             lambda s: put(0, 0, 0.56, server(0, 0, s))]
    for i, fn in enumerate(icons):
        st = ON if i in (1, 2, 3) else NORM
        y = top + i * pitch
        o.append(rect(60, y, 1080, hgt, 14, fill=PALE if st is ON else LIGHT, stroke=NAVY if st is ON else GREY, sw=3))
        o += [f'<g transform="translate(140 {y + hgt / 2})">', *fn(st), "</g>"]
        o.append(line(220, y + 14, 220, y + hgt - 14, stroke=NAVY if st is ON else GREY, sw=2.5))
    return svg(o)


def status_dot(cx, cy, kind):
    if kind == "done":
        return check_mark(cx, cy, 15, ON)
    if kind == "doing":
        return [circle(cx, cy, 15, fill=WHITE, stroke=BLUE, sw=4), circle(cx, cy, 6, fill=BLUE, stroke=BLUE, sw=1)]
    return [circle(cx, cy, 15, fill=WHITE, stroke=GREY, sw=3)]


def work_list(kinds=("agent", "person", "agent"), states=("done", "doing", "todo")) -> str:
    """엔진 ↔ 워크아이템 목록 ↔ 수행자. 행과 수행자를 같은 높이에 놓아 화살표를 가로로만 그린다."""
    o: list[str] = []
    n = len(kinds)
    ys = [70 + 380 * (i + 0.5) / n for i in range(n)]
    o += engine_icon(140, 260, ON)
    o.append(arrow([(218, 244), (404, 244)], NAVY, sw=5, size=14))
    o.append(arrow([(404, 276), (218, 276)], BLUE, sw=5, size=14))
    o.append(rect(410, 50, 330, 420, 14, fill=LIGHT, stroke=NAVY, sw=3.5))
    rh = min(88, 380 / n - 14)
    for y, k, s in zip(ys, kinds, states):
        hot = s == "doing"
        o.append(rect(428, y - rh / 2, 294, rh, 10, fill=PALE if hot else WHITE, stroke=NAVY if s != "todo" else GREY, sw=3))
        o += status_dot(460, y, s)
        c = GREY if s == "todo" else NAVY
        o.append(arrow([(746, y - 14), (896, y - 14)], c, sw=4.5, size=13))
        o.append(arrow([(896, y + 14), (746, y + 14)], GREY if s == "todo" else BLUE, sw=4.5, size=13))
        st = OFF if s == "todo" else (ON if hot else NORM)
        r = min(52, 380 / n / 2 - 8)
        k_ = r / 54
        if k == "person":
            o += node(958, y, st, put(0, 0, 0.78 * k_, approve_icon(-4, -4, st)), r=r)
        elif k == "agent":
            o += node(958, y, st, put(0, 0, 0.78 * k_, agent_icon(0, 4, st)), r=r)
        else:
            o += node(958, y, st, put(0, 0, 0.6 * k_, server(0, 0, st)), r=r)
    return svg(o)


def controls() -> str:
    """사건의 줄 위에 놓이는 통제: 실행 격리(에이전트 둘레), 결정론(에이전트 위), 승인과 권한(승인 위),
    보상(감사 추적(아래 띠), 변경 통제(왼쪽 아래 문서)."""
    o: list[str] = []
    y = 230
    o += chain_nodes(y, [NORM] * 8)
    o.append(rect(CH_X[1] - 68, y - 68, 136, 136, 16, fill="none", stroke=BLUE, sw=4, stroke_dasharray="10 8"))
    o += [circle(CH_X[1], y - 112, 28, fill=WHITE, stroke=BLUE, sw=4)] + put(CH_X[1], y - 112, 0.34, scale_icon(0, 0, ON), 1.6)
    o += [circle(CH_X[2], y - 112, 28, fill=WHITE, stroke=BLUE, sw=4)] + lock_icon(CH_X[2], y - 114, ON, 0.85)
    o.append(line(CH_X[2], y - 84, CH_X[2], y - 58, stroke=BLUE, sw=4))
    o += logstrip(CH_X[2] - 54, 412, NORM, n=33, cw=24, h=38)
    o += put(120, 408, 0.8, doc_icon(-10, -8, NORM) + doc_icon(10, 8, ON), 1.2)
    return svg(o)


def undo_mark(cx, cy, st: St, s=1.0):
    return [path(f"M {cx + 14 * s},{cy + 12 * s} A {15 * s} {15 * s} 0 1 0 {cx - 13 * s},{cy + 2 * s}", stroke=st.line, sw=4),
            poly([(cx - 22 * s, cy - 6 * s), (cx - 4 * s, cy - 2 * s), (cx - 16 * s, cy + 12 * s)], fill=st.line)]


def compensation() -> str:
    """앞으로 간 작업 셋과 실패한 넷째, 끝난 작업을 거꾸로 되돌리는 보상 작업."""
    o: list[str] = []
    xs = (170, 440, 710, 980)
    y = 150
    for a, b in zip(xs, xs[1:]):
        o.append(arrow([(a + 92, y), (b - 96, y)], NAVY, sw=4.5, size=13))
    for i, x in enumerate(xs):
        last = i == 3
        o += task(x, y, 180, 100, NORM if not last else OFF, fill=WHITE)
        o += (cross_mark(x + 64, y - 30, 17, ON) if last else check_mark(x + 64, y - 30, 17, ON))
    cy = 390
    for x in xs[:3]:
        o.append(line(x, y + 50, x, cy - 50, stroke=BLUE, sw=4, stroke_dasharray="9 8"))
        o += task(x, cy, 180, 100, ON, fill=PALE)
        o += undo_mark(x, cy, ON, 1.3)
    o.append(arrow([(xs[3], y + 50), (xs[3], cy), (xs[2] + 96, cy)], BLUE, sw=5, size=14))
    o.append(arrow([(xs[2] - 90, cy), (xs[1] + 96, cy)], BLUE, sw=5, size=14))
    o.append(arrow([(xs[1] - 90, cy), (xs[0] + 96, cy)], BLUE, sw=5, size=14))
    return svg(o)


def person_pin(cx, cy, r=26):
    return [circle(cx, cy, r, fill=WHITE, stroke=BLUE, sw=4)] + put(cx, cy + 2, r / 62, person_icon(0, 0, ON), 1.6)


def three_cases() -> str:
    """세 업무의 처리 건: 시작 사건 → 에이전트 → 승인자 → 실행 시스템 → 끝. 줄마다 그림 조각만 다르고 자리는 같다."""
    o: list[str] = []
    xs = (130, 390, 650, 910)
    starts = [lambda s: put(0, 0, 1.5, bell(0, -2, s), 0.7), lambda s: put(0, 0, 0.5, calendar_icon(0, 0, s), 1.4),
              lambda s: put(0, 0, 0.52, table_icon(0, 0, s), 1.4)]
    systems = [lambda s: put(0, 0, 0.5, plc(0, 0, s), 1.4), lambda s: put(0, 0, 0.56, doc_icon(0, 0, s, "wrench"), 1.3),
               lambda s: put(0, 0, 0.5, server(0, 0, s), 1.4)]
    for i, y in enumerate((95, 250, 405)):
        o.append(rect(20, y - 62, 1160, 144, 14, fill=LIGHT, stroke="none", sw=0))
        for a, b in zip(xs, (*xs[1:], 1110)):
            o.append(arrow([(a + 44, y), (b - (46 if b != 1110 else 30), y)], NAVY, sw=4, size=12))
        o += node(xs[0], y, NORM, starts[i](NORM), r=40)
        o += node(xs[1], y, ON, put(0, 0, 0.56, agent_icon(0, 4, ON), 1.3), r=40)
        o += node(xs[2], y, NORM, put(0, 0, 0.56, approve_icon(-4, -4, NORM), 1.3), r=40)
        o += node(xs[3], y, NORM, systems[i](NORM), r=40)
        o += ev(1110, y, 22, "end", NORM)
    return svg(o)


def people_spots() -> str:
    """사건의 줄에서 사람이 맡는 자리: 지식의 검토, 질문에 답하기, 멈춘 작업 닫기, 승인, 정의의 변경."""
    o: list[str] = []
    y = 230
    sts = [NORM, NORM, ON, NORM, NORM, NORM, NORM, NORM]
    o += chain_nodes(y, sts)
    for x in (160, 290):
        o += person_pin(x, y - 118)
    o.append(line(160, y - 92, 196, y - 48, stroke=BLUE, sw=3.5))
    o.append(line(290, y - 92, 254, y - 48, stroke=BLUE, sw=3.5))
    o += knowledge_block(40, 372, 330, 124, NORM)
    o += person_pin(414, 434)
    o.append(line(370, 434, 388, 434, stroke=BLUE, sw=3.5))
    o += put(820, 434, 0.8, doc_icon(-10, -8, NORM) + doc_icon(10, 8, ON), 1.2)
    o += person_pin(900, 434)
    o.append(line(860, 434, 874, 434, stroke=BLUE, sw=3.5))
    return svg(o)


def main():
    out = {"사건선_전체.svg": event_line("all"), "사건선_영역.svg": event_line("areas"), "사건선_지식에서판단.svg": event_line("u1"),
           "사건선_승인에서끝.svg": event_line("u2"), "호출과지식.svg": calls_knowledge(), "시스템실행.svg": system_exec(),
           "세영역.svg": three_areas(), "다섯계층.svg": five_layers(), "작업목록.svg": work_list(),
           "통제자리.svg": controls(), "세처리건.svg": three_cases(), "사람자리.svg": people_spots(), "보상.svg": compensation()}
    for name, text in out.items():
        assert "<text" not in text
        (HERE / name).write_text(text, encoding="utf-8")
        print("wrote", name)


if __name__ == "__main__":
    main()
