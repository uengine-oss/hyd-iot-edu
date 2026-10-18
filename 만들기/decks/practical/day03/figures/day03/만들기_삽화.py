"""통합반 3일차 삽화(SVG)를 만든다. 글자는 넣지 않는다(라벨은 덱 MD의 요소로 얹는다).

화풍(선 굵기 · 색 · 그림 조각)은 1일차의 `만들기_삽화.py`를 복사한 `삽화_기본.py`에서 가져온다.
한 그림을 여러 장에 걸쳐 쓰며 한 번에 한 부분만 밝히므로(제작지시 6.8) 그림마다 단계별 파일을 낸다.
사용: python 만들기_삽화.py            → 이 폴더에 SVG를 쓴다
"""
from __future__ import annotations

import math
from pathlib import Path

from 삽화_기본 import (BLUE, GREY, LIGHT, NAVY, NORM, OFF, ON, PALE, SKY, WHITE, St, arrow, bell, book_icon,
                    broken_cooler, calendar_icon, circle, cylinder_db, dusty_cooler, fan, g, line, path, poly, radiator,
                    rect, svg, thermo)
from 삽화_기본 import approve_icon, plc, server

HERE = Path(__file__).resolve().parent


# ───────────────────────── 작은 그림 조각 ─────────────────────────

def pump(cx, cy, st: St, r=30):
    return [circle(cx, cy, r, fill=st.soft, stroke=st.line),
            circle(cx - r * 0.33, cy, r * 0.38, fill=st.fill, stroke=st.line, sw=3),
            circle(cx + r * 0.33, cy, r * 0.38, fill=st.fill, stroke=st.line, sw=3)]


def updown(cx, cy, up: bool, color=BLUE, h=34, sw=5):
    return [arrow([(cx, cy + h / 2), (cx, cy - h / 2)] if up else [(cx, cy - h / 2), (cx, cy + h / 2)], color, sw=sw, size=12)]


def moon(cx, cy, st: St, r=22):
    return [path(f"M {cx + r * 0.5},{cy - r * 0.85} A {r} {r} 0 1 0 {cx + r * 0.85},{cy + r * 0.5} "
                 f"A {r * 0.72} {r * 0.72} 0 0 1 {cx + r * 0.5},{cy - r * 0.85} Z", fill=st.accent, stroke=st.line, sw=3)]


def nozzle(cx, cy, st: St):
    o = [rect(cx, cy - 10, 44, 20, 5, fill=st.fill, stroke=st.line, sw=3), rect(cx + 26, cy + 10, 16, 30, 4, fill=st.fill, stroke=st.line, sw=3),
         poly([(cx, cy - 7), (cx - 14, cy - 3), (cx - 14, cy + 3), (cx, cy + 7)], fill=st.line)]
    for dy in (-16, 0, 16):
        o.append(line(cx - 22, cy + dy * 0.35, cx - 50, cy + dy, stroke=SKY if st is ON else GREY, sw=3.5))
    return o


def check_mark(cx, cy, r=30, st: St = ON):
    return [circle(cx, cy, r, fill=SKY if st is ON else WHITE, stroke=st.line, sw=3.5),
            path(f"M {cx - r * 0.42},{cy + r * 0.02} L {cx - r * 0.1},{cy + r * 0.36} L {cx + r * 0.46},{cy - r * 0.32}", stroke=st.line, sw=5)]


def cross_mark(cx, cy, r=30, st: St = ON):
    return [circle(cx, cy, r, fill=WHITE, stroke=st.line, sw=3.5),
            line(cx - r * 0.36, cy - r * 0.36, cx + r * 0.36, cy + r * 0.36, stroke=st.line, sw=5),
            line(cx + r * 0.36, cy - r * 0.36, cx - r * 0.36, cy + r * 0.36, stroke=st.line, sw=5)]


def selector(cx, cy, pos: int, st: St, r=32):
    o = [circle(cx, cy, r, fill=st.fill, stroke=st.line)]
    for i, a in enumerate((-140, -90, -40)):
        ra = math.radians(a)
        o.append(circle(cx + (r + 13) * math.cos(ra), cy + (r + 13) * math.sin(ra), 5,
                        fill=st.accent if i == pos else WHITE, stroke=st.line, sw=2.5))
    ra = math.radians((-140, -90, -40)[pos])
    o += [line(cx, cy, cx + (r - 8) * math.cos(ra), cy + (r - 8) * math.sin(ra), stroke=st.line, sw=7),
          circle(cx, cy, 6, fill=st.line, stroke=st.line, sw=1)]
    return o


def bolt(cx, cy, st: St, s=1.0):
    pts = [(6, -30), (-16, 4), (-2, 4), (-8, 30), (16, -6), (2, -6)]
    return [poly([(cx + x * s, cy + y * s) for x, y in pts], fill=st.accent, stroke=st.line, sw=3)]


def crates(cx, cy, st: St):
    o = []
    for dx, dy in ((-24, 6), (4, 6), (-10, -22)):
        o += [rect(cx + dx, cy + dy, 26, 26, 3, fill=st.soft, stroke=st.line, sw=3),
              line(cx + dx, cy + dy + 9, cx + dx + 26, cy + dy + 9, stroke=st.line, sw=2)]
    return o


def shield(cx, cy, st: St, s=1.0):
    return [path(f"M {cx},{cy - 30 * s} L {cx + 24 * s},{cy - 20 * s} L {cx + 24 * s},{cy + 2 * s} "
                 f"Q {cx + 22 * s},{cy + 22 * s} {cx},{cy + 32 * s} Q {cx - 22 * s},{cy + 22 * s} {cx - 24 * s},{cy + 2 * s} "
                 f"L {cx - 24 * s},{cy - 20 * s} Z", fill=st.accent, stroke=st.line),
            path(f"M {cx - 10 * s},{cy} L {cx - 2 * s},{cy + 9 * s} L {cx + 12 * s},{cy - 9 * s}", stroke=st.line, sw=4)]


def sliders(cx, cy, st: St):
    o = []
    for i, k in enumerate((0.3, 0.7, 0.45)):
        y = cy - 26 + i * 26
        o += [line(cx - 50, y, cx + 50, y, stroke=st.line, sw=4), circle(cx - 50 + 100 * k, y, 9, fill=st.accent, stroke=st.line, sw=3)]
    return o


def ranking(cx, cy, order, hot, st: St):
    o = [rect(cx - 120, cy - 78, 240, 156, 10, fill=WHITE, stroke=st.line)]
    for i, k in enumerate(order):
        y = cy - 54 + i * 36
        on = i == hot and st is not OFF
        o += [circle(cx - 96, y, 10, fill=SKY if on else WHITE, stroke=st.line, sw=2.5),
              rect(cx - 76, y - 9, 170 * k, 18, 6, fill=SKY if on else GREY if st is not OFF else LIGHT, stroke=st.line if on else "none", sw=2.5 if on else 0)]
    return o


def doc(cx, cy, st: St, w=90, h=112):
    o = [rect(cx - w / 2, cy - h / 2, w, h, 8, fill=st.fill, stroke=st.line)]
    for i, k in enumerate((0.8, 0.6, 0.8, 0.5, 0.7)):
        y = cy - h / 2 + 22 + i * 18
        o.append(line(cx - w / 2 + 14, y, cx - w / 2 + 14 + (w - 28) * k, y, stroke=st.line, sw=2.5))
    return o


def frame(x, y, w, h, r=10):
    return rect(x, y, w, h, r, fill="none", stroke=BLUE, sw=4.5)


# ───────────────────────── 1. 조치 후보 넷 ─────────────────────────

def candidates(focus) -> str:
    """focus: None = 넷 모두, 0 = 원인과 고장 유형만, 1~4 = 그 후보만 밝힌다."""
    o: list[str] = []
    C, F = (125, 260), (400, 260)
    rows = (68, 196, 324, 452)

    def st(i):
        return ON if focus is None or focus == i else OFF

    def col(i):
        return (BLUE if focus == i else NAVY) if st(i) is ON else GREY

    o.append(arrow([(C[0] + 78, C[1]), (F[0] - 82, F[1])], NAVY, sw=5, size=15))
    for i, by in enumerate(rows, 1):
        o.append(path(f"M {F[0] + 74},{F[1]} L 500,{F[1]} C 560,{F[1]} 548,{by} 606,{by}", stroke=col(i), sw=5 if focus == i else 4))
        o.append(arrow([(606, by), (640, by)], col(i), sw=5 if focus == i else 4, size=13))
    o += [circle(*C, 72, fill=WHITE, sw=4), circle(*F, 74, fill=SKY, sw=4)]
    o += g(*C, 1.05, dusty_cooler(0, 0, ON), boost=0.95)
    o += g(*F, 1.05, broken_cooler(0, 0, NORM), boost=0.95)
    ud = lambda i: BLUE if st(i) is ON else GREY
    o += fan(700, rows[0], 40, st(1), rot=20, hot=True) + updown(760, rows[0], True, ud(1))
    o += fan(690, rows[1], 36, st(2), rot=20, hot=True) + updown(742, rows[1], True, ud(2))
    o += pump(800, rows[1], st(2), 28) + updown(846, rows[1], False, ud(2))
    o += pump(690, rows[2], st(3), 30) + updown(738, rows[2], False, ud(3))
    o += moon(800, rows[2], st(3))
    o += radiator(650, rows[3] - 34, 88, 68, st(4), fins=8, r=7) + nozzle(790, rows[3], st(4))
    return svg(o)


# ───────────────────────── 2. SOP 문서와 구성요소 ─────────────────────────

SOP_BLOCKS = {"target": (20, 40), "pre": (70, 40), "prep": (148, 28), "steps": (184, 84), "role": (276, 28),
              "safety": (338, 32), "done": (384, 40), "forbid": (434, 40)}   # 구성요소 여덟(준비사항 포함)
SOP_TITLES = (118, 310)   # SOP 제목 줄(SOP-COOL-11, SOP-COOL-14)


def sopdoc(focus: str) -> str:
    o = [rect(40, 8, 500, 504, 12, fill=WHITE)]
    for ty in SOP_TITLES:
        o.append(rect(62, ty, 210, 22, 6, fill=NAVY, stroke="none", sw=0))
    for key, (y, h) in SOP_BLOCKS.items():
        hot = focus in ("all", key)
        o.append(rect(58, y, 464, h, 8, fill=PALE if hot else LIGHT, stroke=SKY if hot else "none", sw=3 if hot else 0))
        if key == "steps":
            for k in range(3):
                yy = y + 16 + k * 26
                o += [circle(78, yy, 8, fill=SKY if hot else WHITE, stroke=NAVY if hot else GREY, sw=2.5),
                      rect(96, yy - 6, (330, 290, 360)[k], 12, 6, fill=GREY, stroke="none", sw=0)]
        else:
            for k in range(2 if h >= 40 else 1):
                o.append(rect(72, y + 10 + k * 14, (420, 300)[k], 9, 4, fill=GREY, stroke="none", sw=0))
        if focus == "all":
            o.append(arrow([(528, y + h / 2), (600, y + h / 2)], BLUE, sw=3.5, size=11))
        elif focus == key:      # 오른쪽에 인용문을 얹을 큰 칸
            cy = max(86, min(430, y + h / 2))
            o.append(rect(604, cy - 78, 570, 156, 14, fill=PALE, stroke=SKY, sw=3))
            o.append(arrow([(528, y + h / 2), (598, y + h / 2)], BLUE, sw=5, size=14))
    return svg(o)


# ───────────────────────── 3. 운전 모드와 조치의 수행 가능 여부 ─────────────────────────

def modes(stage: int) -> str:
    """0 = 운전 모드 셋만, 1 = 원격 자동의 팬 최대 운전, 2 = 세 모드의 팬 최대 운전, 3 = 핀 세척까지."""
    o: list[str] = []
    cols = (500, 760, 1020)
    rows = (275, 425)
    hot = {0: (0, 1, 2), 1: (0,), 2: (1, 2), 3: (0, 1, 2)}[stage]
    for i, x in enumerate(cols):
        on = i in hot
        o.append(rect(x - 118, 14, 236, 492, 14, fill=PALE if on else LIGHT, stroke=SKY if on else "none", sw=2.5 if on else 0))
        o += selector(x, 78, i, ON if on else NORM)
    if stage == 0:      # 누가 설비를 움직이는가: 상위 시스템 · 사람의 수동 조작 · 현장 패널
        o += g(cols[0], 370, 0.95, server(0, 0, ON))
        o += g(cols[1], 370, 1.0, approve_icon(0, 0, ON)[:2])
        o += g(cols[2], 370, 0.95, plc(0, 0, ON))
    if stage >= 1:
        o += fan(86, rows[0], 42, ON if stage < 3 else NORM, rot=20, hot=stage < 3)
        for i, x in enumerate(cols):
            if stage == 1 and i > 0:
                continue
            o += check_mark(x, rows[0] - 8) if i == 0 else cross_mark(x, rows[0] - 8)
    if stage >= 3:
        o.append(line(30, 350, 1150, 350, stroke=GREY, sw=2))
        o += radiator(42, rows[1] - 34, 88, 68, ON, fins=8, r=7)
        for x in cols:
            o += check_mark(x, rows[1] - 8)
    return svg(o)


# ───────────────────────── 4. 예방 · 완화 · 근본 조치의 때 ─────────────────────────

def timeline(focus: str) -> str:
    o: list[str] = []
    spots = {"prevent": 230, "mitigate": 600, "remedy": 960}
    o.append(arrow([(50, 300), (1160, 300)], NAVY, sw=4, size=14))
    # 유온의 흐름: 평소 → 경보 → 완화 뒤(조금 높은 채) → 근본 조치 뒤
    o.append(path("M 60,455 L 470,455 C 500,455 510,380 540,372 C 580,362 590,420 640,424 L 900,424 C 940,424 950,455 990,455 L 1150,455",
                  stroke=NAVY, sw=4))
    o.append(line(60, 400, 1150, 400, stroke=SKY, sw=2.5, stroke_dasharray="7 7"))
    o += bell(505, 296, ON, 1.5)
    for key, x in spots.items():
        st = ON if focus in ("all", key) else OFF
        o.append(circle(x, 150, 78, fill=(PALE if focus == "all" else SKY) if st is ON else WHITE, stroke=st.line, sw=4))
        o.append(line(x, 228, x, 292, stroke=st.line, sw=3, stroke_dasharray="6 6"))
        if key == "prevent":
            o += g(x, 150, 0.9, calendar_icon(0, 0, st))
        elif key == "mitigate":
            o += fan(x, 150, 48, st, rot=20, hot=True)
        else:
            o += radiator(x - 62, 150 - 30, 76, 60, st, fins=7, r=6) + nozzle(x + 40, 150, st)
    return svg(o)


# ───────────────────────── 5. 결정표 ─────────────────────────

TX = (330, 600, 870, 1170)
TY = (126, 196, 304, 412)


def dtable(stage: int) -> str:
    """1 결정 · 2 입력 데이터 · 3 규칙 한 행 · 4 조건과 출력 · 5 둘째 규칙 · 6 값을 대어 본다 · 7 근거."""
    X0, X1, X2, X3 = TX
    Y0, Y1, Y2, Y3 = TY
    o: list[str] = []
    o.append(rect(X0, 6, X3 - X0, 52, 12, fill=PALE if stage == 1 else LIGHT, stroke=SKY if stage == 1 else "none", sw=2.5 if stage == 1 else 0))
    if stage == 6:      # 지금의 값
        for a, b in ((X0, X1), (X1, X2)):
            o.append(rect(a + 30, 68, b - a - 60, 40, 20, fill=SKY, sw=3))
            o.append(arrow([((a + b) / 2, 108), ((a + b) / 2, Y0 - 4)], BLUE, sw=4, size=11))
    else:
        for a, b in ((X0, X2 - 10), (X2 + 10, X3)):
            o.append(path(f"M {a + 6},{Y0 - 6} L {a + 6},{Y0 - 14} L {b - 6},{Y0 - 14} L {b - 6},{Y0 - 6}", stroke=NAVY, sw=3))
    o += [rect(X0, Y0, X3 - X0, Y3 - Y0, 10, fill=WHITE), rect(X0, Y0, X3 - X0, Y1 - Y0, 10, fill=LIGHT),
          rect(X2, Y0, X3 - X2, Y3 - Y0, 10, fill=PALE, stroke="none", sw=0), rect(X0, Y0, X3 - X0, Y3 - Y0, 10, fill="none")]
    for y in (Y1, Y2):
        o.append(line(X0, y, X3, y, sw=2.5))
    o.append(line(X1, Y0, X1, Y3, stroke=GREY, sw=2))
    o += [line(X2 - 3, Y0, X2 - 3, Y3, sw=2.5), line(X2 + 3, Y0, X2 + 3, Y3, sw=2.5)]
    if stage == 2:
        o.append(frame(X0 - 6, Y0 - 4, X2 - X0 + 2, Y1 - Y0 + 8))
    if stage == 3:
        o.append(frame(X0 - 6, Y1, X3 - X0 + 12, Y2 - Y1))
    if stage == 4:
        o += [frame(X0 - 6, Y1 + 2, X2 - X0 - 2, Y2 - Y1 - 4), rect(X2 + 8, Y1 + 2, X3 - X2 - 2, Y2 - Y1 - 4, 10, fill="none", stroke=NAVY, sw=4.5)]
    if stage in (5, 6):
        o.append(frame(X0 - 6, Y2, X3 - X0 + 12, Y3 - Y2 + 6))
    if stage in (2, 3, 5):
        yy = {2: (Y0 + Y1) / 2, 3: (Y1 + Y2) / 2, 5: (Y2 + Y3) / 2}[stage]
        o.append(arrow([(250, yy), (X0 - 14, yy)], BLUE, sw=4, size=12))
    st = ON if stage == 7 else NORM
    o += g(1110, 468, 0.55, book_icon(0, 0, st))
    o.append(path(f"M 1110,{Y3 + 4} L 1110,438", stroke=BLUE if stage == 7 else NAVY, sw=4 if stage == 7 else 3, stroke_dasharray="6 6"))
    if stage == 7:
        o.append(circle(1110, 468, 44, fill="none", stroke=BLUE, sw=4))
    return svg(o)


# ───────────────────────── 6. 수직선: 임계값 · 범위 · 결함 ─────────────────────────

AY = 330


def _axis(ticks):
    out = [arrow([(80, AY), (1140, AY)], NAVY, sw=4, size=14)]
    for t in ticks:
        out.append(line(t, AY - 12, t, AY + 12, sw=4))
    return out


def _bar(x0, x1, level=0, fill=PALE, stroke=NAVY, dash=None):
    top = AY - 96 - level * 76
    return rect(x0, top, x1 - x0, 60, 10, fill=fill, stroke=stroke, sw=3.5, stroke_dasharray=dash)


def _probe(x, ok):
    """값 하나를 대어 본 자리: 축 아래의 표시와 위로 올라가는 가는 선."""
    out = [line(x, AY + 14, x, AY + 60, stroke=NAVY, sw=2.5, stroke_dasharray="5 5")]
    out += check_mark(x, AY + 92, 28) if ok else cross_mark(x, AY + 92, 28)
    return out


def _dot(x, closed, level=0):
    return [circle(x, AY - 66 - level * 76, 10, fill=NAVY if closed else WHITE, stroke=NAVY, sw=3.5)]


def numline(kind: str) -> str:
    o: list[str] = []
    if kind == "ge":          # forecast_ts1 >= 55
        o += _axis((380, 600, 820)) + [_bar(600, 1120)] + _dot(600, True) + _probe(380, False) + _probe(600, True) + _probe(820, True)
    elif kind == "gt":        # fan100_hours > 24
        o += _axis((380, 600, 820)) + [_bar(600, 1120)] + _dot(600, False) + _probe(380, False) + _probe(600, False) + _probe(820, True)
    elif kind == "range":     # 55 < 유온 < 65
        o += _axis((380, 860)) + [_bar(380, 860)] + _dot(380, False) + _dot(860, False) + _probe(220, False) + _probe(620, True) + _probe(1010, False)
    elif kind == "missing":
        o += _axis((430, 770)) + [_bar(100, 430), _bar(770, 1120, fill=GREY), _bar(430, 770, fill=WHITE, stroke=BLUE, dash="9 8")]
        o += _probe(600, False)
    elif kind in ("dup", "conflict"):
        o += _axis((430, 700))
        o.append(rect(700, AY - 180, 420, 152, 10, fill=LIGHT, stroke=BLUE if kind == "conflict" else "none", sw=3.5 if kind == "conflict" else 0))
        o += [_bar(430, 1120, level=1), _bar(700, 1120, level=0, fill=PALE if kind == "dup" else GREY)]
        o += [line(900, AY + 14, 900, AY + 60, stroke=NAVY, sw=2.5, stroke_dasharray="5 5"), circle(900, AY + 92, 28, fill=SKY, sw=3.5)]
    return svg(o)


# ───────────────────────── 7. Hit Policy ─────────────────────────

def hit(policy: str) -> str:
    """세 행 가운데 둘째 · 셋째 행이 함께 맞은 결정표. policy: base · unique · first · priority · collect."""
    o: list[str] = []
    X0, X1, X2 = 250, 640, 900
    Y = (70, 130, 230, 330, 430)
    o += [rect(X0, Y[0], X2 - X0, Y[4] - Y[0], 10, fill=WHITE), rect(X0, Y[0], X2 - X0, Y[1] - Y[0], 10, fill=LIGHT)]
    for r_ in (2, 3):   # 맞은 행
        o.append(rect(X0 + 3, Y[r_] + 3, X2 - X0 - 6, Y[r_ + 1] - Y[r_] - 6, 6, fill=PALE, stroke="none", sw=0))
    o.append(rect(X0, Y[0], X2 - X0, Y[4] - Y[0], 10, fill="none"))
    for y in Y[1:4]:
        o.append(line(X0, y, X2, y, sw=2.5))
    o += [line(X1 - 3, Y[0], X1 - 3, Y[4], sw=2.5), line(X1 + 3, Y[0], X1 + 3, Y[4], sw=2.5)]
    o += cross_mark(195, (Y[1] + Y[2]) / 2, 22, OFF) + check_mark(195, (Y[2] + Y[3]) / 2, 22) + check_mark(195, (Y[3] + Y[4]) / 2, 22)
    fr = lambda r_: frame(X0 - 6, Y[r_] - 2, X2 - X0 + 12, Y[r_ + 1] - Y[r_] + 4)
    RX = 1040
    if policy == "unique":
        o += [fr(2), fr(3)]
        o += [arrow([(X2 + 10, (Y[2] + Y[3]) / 2), (RX - 62, 320)], NAVY, sw=4, size=12), arrow([(X2 + 10, (Y[3] + Y[4]) / 2), (RX - 62, 340)], NAVY, sw=4, size=12)]
        o += cross_mark(RX, 330, 52)
    elif policy == "first":
        o.append(fr(2))
        o.append(arrow([(120, Y[1] + 10), (120, Y[2] + 50)], BLUE, sw=5, size=14))
        o.append(arrow([(X2 + 10, (Y[2] + Y[3]) / 2), (RX - 70, (Y[2] + Y[3]) / 2)], BLUE, sw=5, size=14))
        o.append(rect(RX - 62, (Y[2] + Y[3]) / 2 - 36, 190, 72, 12, fill=SKY, sw=3.5))
    elif policy == "priority":
        o.append(fr(3))
        o.append(arrow([(X2 + 10, (Y[3] + Y[4]) / 2), (RX - 70, (Y[3] + Y[4]) / 2)], BLUE, sw=5, size=14))
        o.append(rect(RX - 62, (Y[3] + Y[4]) / 2 - 36, 190, 72, 12, fill=SKY, sw=3.5))
    elif policy == "collect":
        o += [fr(2), fr(3)]
        o += [arrow([(X2 + 10, (Y[2] + Y[3]) / 2), (RX - 70, 315)], BLUE, sw=5, size=14), arrow([(X2 + 10, (Y[3] + Y[4]) / 2), (RX - 70, 345)], BLUE, sw=5, size=14)]
        o += [rect(RX - 62, 262, 190, 136, 12, fill=SKY, sw=3.5), line(RX - 46, 330, RX + 112, 330, sw=2.5)]
    return svg(o)


# ───────────────────────── 8. 전략맵 ─────────────────────────

OBJ = {"profit": (700, 66), "cost": (1010, 66), "delivery": (580, 192), "quality": (830, 192),
       "safety": (330, 320), "avail": (580, 320), "energy": (1010, 320), "knowledge": (580, 448)}
LANE = {"profit": 0, "cost": 0, "delivery": 1, "quality": 1, "safety": 2, "avail": 2, "energy": 2, "knowledge": 3}
EDGES = (("knowledge", "avail"), ("safety", "avail"), ("avail", "delivery"), ("delivery", "profit"), ("quality", "profit"),
         ("energy", "cost"), ("cost", "profit"))
BW, BH = 210, 58


def strategy_map(lanes=(0, 1, 2, 3), edges=(), hot_lane=None, hot_edges=()) -> str:
    o: list[str] = []
    for i, y in enumerate((8, 134, 262, 390)):
        o.append(rect(14, y, 1172, 116, 14, fill=PALE if i == hot_lane else LIGHT, stroke=SKY if i == hot_lane else "none", sw=2.5 if i == hot_lane else 0))
        o.append(line(196, y + 16, 196, y + 100, stroke=GREY, sw=2))

    def edge(a, b, color, sw):
        (ax, ay), (bx, by) = OBJ[a], OBJ[b]
        if abs(ay - by) < 5:
            sx = ax + BW / 2 * (1 if bx > ax else -1)
            ex = bx - (BW / 2 + 4) * (1 if bx > ax else -1)
            return arrow([(sx, ay), (ex, by)], color, sw=sw, size=13)
        tx = bx + max(-70, min(70, (ax - bx) * 0.55))
        return arrow([(ax, ay - BH / 2), (tx, by + BH / 2 + 4)], color, sw=sw, size=13)

    for i in edges:
        o.append(edge(*EDGES[i], BLUE if i in hot_edges else NAVY, 5 if i in hot_edges else 3.5))
    for name, (cx, cy) in OBJ.items():
        on = LANE[name] in lanes
        o.append(rect(cx - BW / 2, cy - BH / 2, BW, BH, 12, fill=(SKY if name == "profit" else WHITE) if on else WHITE,
                      stroke=NAVY if on else GREY, sw=3.5 if on else 2.5))
    return svg(o)


# ───────────────────────── 9. 인터록 여유 ─────────────────────────

def margin(stage: int) -> str:
    """1 정의 · 2 목표값 · 3 실제값 · 4 목표 대비 차이. 가로축은 유온 45~67 ℃."""
    x = lambda t: 100 + (t - 45) / 22 * 1000
    o: list[str] = []
    AY2 = 300
    if stage in (2, 4):
        o.append(rect(100, AY2 - 60, x(55) - 100, 60, 8, fill=PALE, stroke="none", sw=0))
    o.append(arrow([(80, AY2), (1150, AY2)], NAVY, sw=4, size=14))
    for t in (45, 50, 55, 60, 65):
        o.append(line(x(t), AY2 - 8, x(t), AY2 + 8, sw=3))
    o.append(line(x(65), 60, x(65), AY2 + 70, stroke=NAVY, sw=6))                      # 유온 한계
    o += thermo(x(62.47), AY2 - 26, ON, s=0.7, level=0.85)                              # 기간 중 최고 유온
    o.append(line(x(62.47), AY2 - 8, x(62.47), AY2 + 70, stroke=BLUE, sw=3, stroke_dasharray="6 6"))

    def bracket(t0, t1, y, color, sw=4.5):
        return [line(x(t0), y, x(t1), y, stroke=color, sw=sw), line(x(t0), y - 12, x(t0), y + 12, stroke=color, sw=sw),
                line(x(t1), y - 12, x(t1), y + 12, stroke=color, sw=sw)]

    if stage in (1, 3, 4):
        o += bracket(62.47, 65, AY2 + 60, BLUE)
    if stage in (2, 4):
        o.append(line(x(55), 110, x(55), AY2 + 8, stroke=SKY, sw=3.5, stroke_dasharray="8 7"))
        o += bracket(55, 65, 130, NAVY)
    if stage == 4:
        o += bracket(55, 62.47, AY2 + 130, BLUE, sw=6)
    return svg(o)


# ───────────────────────── 10. 조치 하나가 성과에 닿는 길 ─────────────────────────

def tradeoff(stage: int) -> str:
    """1 조치와 설비의 값 · 2 유온과 인터록 여유 · 3 전력 사용량 · 4 생산량과 납기 준수율 · 5 전체."""
    N = {"skill": (112, 230), "fan": (400, 80), "load": (400, 400), "ts1": (690, 236), "power": (985, 56),
         "margin": (985, 236), "out": (690, 400), "otd": (985, 400)}
    R = 46
    full = "skill fan load ts1 margin power out otd"
    shown = {1: "skill fan load", 2: "skill fan load ts1 margin", 3: "skill fan load ts1 margin power",
             4: full, 5: full, 6: full}[stage].split()
    # 6 = 전체판에서 득의 갈래(팬 · 부하 → 유온 → 인터록 여유)는 파랑, 실의 갈래(전력 · 생산량 · 납기)는 남색으로 나눈다
    hot = {1: "skill fan load", 2: "ts1 margin", 3: "power", 4: "out otd", 5: "", 6: "ts1 margin"}[stage].split()
    o: list[str] = []

    def st(name):
        return ON if name in shown else OFF

    def link(a, b):
        (ax, ay), (bx, by) = N[a], N[b]
        d_ = math.hypot(bx - ax, by - ay)
        ux, uy = (bx - ax) / d_, (by - ay) / d_
        ra = 62 if a == "skill" else R
        on = a in shown and b in shown
        hl = on and b in hot
        return arrow([(ax + ux * (ra + 6), ay + uy * (ra + 6)), (bx - ux * (R + 8), by - uy * (R + 8))],
                     BLUE if hl else NAVY if on else GREY, sw=5 if hl else 4 if on else 3, size=13)

    for a, b in (("skill", "fan"), ("skill", "load"), ("fan", "ts1"), ("load", "ts1"), ("ts1", "margin"),
                 ("fan", "power"), ("load", "out"), ("out", "otd")):
        o.append(link(a, b))
    o.append(circle(*N["skill"], 62, fill=PALE, sw=4))
    o += g(N["skill"][0] - 20, N["skill"][1], 0.62, fan(0, 0, 46, ON, rot=20, hot=True), boost=1.0)
    o += g(N["skill"][0] + 28, N["skill"][1], 0.62, pump(0, 0, ON, 30), boost=1.0)
    fills = {"fan": WHITE, "load": WHITE, "ts1": WHITE, "out": WHITE, "margin": SKY, "power": LIGHT, "otd": LIGHT}
    for name, f in fills.items():
        s_ = st(name)
        o.append(circle(*N[name], R, fill=f if s_ is ON else WHITE, stroke=s_.line, sw=4 if s_ is ON else 3))
    o += g(*N["fan"], 0.6, fan(0, 0, 46, st("fan"), rot=20), boost=1.0)
    o += g(*N["load"], 0.9, pump(0, 0, st("load"), 30), boost=0.9)
    o += g(N["ts1"][0], N["ts1"][1], 1.0, thermo(0, 22, st("ts1"), s=0.6, level=0.5), boost=1.0)
    o += g(*N["out"], 0.95, crates(0, 0, st("out")), boost=0.9)
    o += g(*N["power"], 0.85, bolt(0, 0, NORM if st("power") is ON else OFF), boost=0.9)
    o += g(*N["margin"], 0.85, shield(0, 0, NORM if st("margin") is ON else OFF), boost=0.9)
    o += g(*N["otd"], 0.5, calendar_icon(0, 0, NORM if st("otd") is ON else OFF))
    ups = {"fan": True, "load": False, "ts1": False, "out": False, "power": True, "margin": True, "otd": False}
    for name, up in ups.items():
        if name in shown:
            cx, cy = N[name]
            o += updown(cx + R * 0.9 + 12, cy - R * 0.9 - 2, up, BLUE if name in ("fan", "load", "ts1", "margin") else NAVY, h=30)
    return svg(o)


# ───────────────────────── 11. What-if ─────────────────────────

def whatif(stage: int) -> str:
    """1 사본을 만든다 · 2 가정값을 바꾼다 · 3 결과를 견준다 · 4 경계값 · 5 원본은 그대로."""
    o: list[str] = []
    src = ON if stage in (1, 5) else NORM
    o += [rect(14, 90, 250, 340, 14, fill=PALE if stage == 5 else LIGHT, stroke=SKY if stage == 5 else "none", sw=2.5 if stage == 5 else 0),
          rect(330, 90, 270, 340, 14, fill=PALE if stage in (1, 2) else LIGHT, stroke=SKY if stage in (1, 2) else "none", sw=2.5 if stage in (1, 2) else 0)]
    o += g(139, 185, 0.95, cylinder_db(0, 0, src)[:4])
    o += g(139, 335, 0.95, cylinder_db(0, 0, src)[:4])
    o.append(arrow([(272, 260), (322, 260)], BLUE if stage in (1, 5) else NAVY, sw=5, size=14))
    o += doc(465, 195, ON, w=100, h=110)
    sl = ON if stage >= 2 else OFF
    o += sliders(465, 365, sl)
    o.append(path("M 465,258 L 465,322", stroke=sl.line, sw=3, stroke_dasharray="6 6"))
    r1 = NORM if stage >= 3 else OFF
    r2 = ON if stage >= 3 else OFF
    o += [arrow([(606, 195), (760, 170)], r1.line, sw=4.5, size=13), arrow([(606, 365), (760, 350)], BLUE if stage >= 3 else GREY, sw=5, size=14)]
    o += ranking(890, 165, (0.95, 0.8, 0.78, 0.3), 0, r1)
    o += ranking(890, 345, (0.9, 0.86, 0.7, 0.3), 0, r2)
    if stage >= 4:
        o.append(path("M 1018,215 C 1050,235 1050,275 1018,295", stroke=BLUE, sw=5 if stage == 4 else 4, stroke_dasharray="7 7"))
    return svg(o)


# ───────────────────────── 12. 지식 그래프 꼴(1회차 지도 · 2회차 kg_svg와 같은 꼴): 원형 노드 · 대각선 ─────────────────────────
# 1인치 = 100(본문 12.13 × 5.4인치와 같은 축척). 노드에는 글자를 넣지 않고 클래스 이름은 덱 MD 라벨로 얹는다.
# 역할별 색: hub = 여러 관계가 모이는 노드(진한 원), near = 직접 붙은 노드(파란 테두리), far = 바깥 노드(회색).
KW, KH = 1213, 540
RING = {"hub": (SKY, NAVY, 4), "near": (PALE, BLUE, 3), "far": (LIGHT, GREY, 3)}


def _kg_arrow(a, b, color, dashed=False):
    (ax, ay, ar, *_), (bx, by, br, *_) = a, b
    d_ = math.hypot(bx - ax, by - ay)
    ux, uy = (bx - ax) / d_, (by - ay) / d_
    p0, p1 = (ax + ux * (ar + 5), ay + uy * (ar + 5)), (bx - ux * (br + 9), by - uy * (br + 9))
    if not dashed:
        return [arrow([p0, p1], color, sw=4 if color == BLUE else 3, size=13)]
    tip = (p1[0] - ux * 2, p1[1] - uy * 2)
    return [line(p0[0], p0[1], p1[0] - ux * 14, p1[1] - uy * 14, stroke=color, sw=4, stroke_dasharray="12 9"),
            arrow([(p1[0] - ux * 16, p1[1] - uy * 16), tip], color, sw=4, size=13)]


def kg_svg(nodes: dict, edges: list, extra=(), after=()) -> str:
    """nodes: {키: (x, y, r, 역할)}, edges: [(시작, 끝, 색[, 점선])] — 화살표는 저장 방향(시작 → 끝)."""
    o: list[str] = list(extra)
    for e in edges:
        o += _kg_arrow(nodes[e[0]], nodes[e[1]], e[2], dashed=len(e) > 3 and e[3])
    for x, y, r, role in nodes.values():
        fill, stroke, sw = RING[role]
        o.append(circle(x, y, r, fill=fill, stroke=stroke, sw=sw))
    o += list(after)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {KW} {KH}" width="{KW}" height="{KH}">\n'
            + "\n".join(o) + "\n</svg>\n")


def _band():
    """그래프 아래의 띠: 점선 구분과 실제 대상을 얹을 칸(글은 덱 라벨)."""
    return [line(20, 432, KW - 20, 432, stroke=GREY, sw=2.5, stroke_dasharray="6 8"),
            rect(40, 452, KW - 80, 72, 14, fill=LIGHT, stroke="none", sw=0)]


def kg_skill() -> str:
    """원인 → 고장 유형 → 조치 방법(Skill, 가운데) → 단계 → 근거 절, 승인 역할, 원인 한정(ADDRESSES). 아래 띠는 쿨러 사건의 실제 연결."""
    n = {"cause": (110, 120, 60, "near"), "fm": (360, 320, 84, "near"), "skill": (640, 150, 68, "hub"),
         "role": (900, 70, 56, "near"), "step": (850, 330, 60, "near"), "ms": (1100, 250, 84, "far")}
    edges = [("cause", "fm", NAVY), ("fm", "skill", BLUE), ("skill", "cause", NAVY), ("skill", "role", NAVY),
             ("skill", "step", BLUE), ("step", "ms", NAVY)]
    return kg_svg(n, edges, extra=_band())


def kg_dmn() -> str:
    """결정 → 결정표 → 규칙(가운데) → 입력 데이터 · 적용 조치 · 근거 절. 아래 띠는 실제 규칙 한 행."""
    n = {"dec": (110, 110, 70, "near"), "dt": (380, 320, 86, "near"), "rule": (650, 150, 66, "hub"),
         "skill": (930, 70, 52, "near"), "input": (880, 340, 74, "near"), "ms": (1110, 250, 84, "far")}
    edges = [("dec", "dt", NAVY), ("dt", "rule", NAVY), ("rule", "input", BLUE), ("rule", "skill", BLUE), ("rule", "ms", NAVY)]
    return kg_svg(n, edges, extra=_band())


def numline_pair() -> str:
    """위: forecast_ts1 >= 55(채운 점), 아래: fan100_hours > 24(빈 점). 축마다 기준값 · 바로 아래 · 바로 위의 세 시험점."""
    o: list[str] = []
    xs = (520, 700, 880)
    for ay, closed, oks in ((150, True, (False, True, True)), (400, False, (False, False, True))):
        o.append(arrow([(300, ay), (1180, ay)], NAVY, sw=4, size=14))
        for x in xs:
            o.append(line(x, ay - 12, x, ay + 12, sw=4))
        o.append(rect(700, ay - 92, 460, 52, 10, fill=PALE, stroke=NAVY, sw=3.5))
        o.append(circle(700, ay - 66, 10, fill=NAVY if closed else WHITE, stroke=NAVY, sw=3.5))
        for x, ok in zip(xs, oks):
            o.append(line(x, ay + 14, x, ay + 40, stroke=NAVY, sw=2.5, stroke_dasharray="5 5"))
            o += check_mark(x, ay + 66, 22) if ok else cross_mark(x, ay + 66, 22)
    o.append(line(20, 272, 1180, 272, stroke=GREY, sw=2, stroke_dasharray="6 8"))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {KW} {KH}" width="{KW}" height="{KH}">\n'
            + "\n".join(o) + "\n</svg>\n")


def lead_lag() -> str:
    """펌프 부하 → 생산량(선행) → 납기 준수율 → 지체상금(후행). 왼쪽 띠 = 선행, 오른쪽 띠 = 후행."""
    o = [rect(14, 8, 556, 524, 14, fill=PALE, stroke="none", sw=0), rect(590, 8, 606, 524, 14, fill=LIGHT, stroke="none", sw=0)]
    n = {"load": (130, 330, 56, "far"), "tp": (400, 190, 62, "hub"), "otd": (760, 330, 62, "near"), "pen": (1050, 190, 62, "near")}
    edges = [("load", "tp", NAVY), ("tp", "otd", BLUE), ("otd", "pen", BLUE)]
    icons = (g(130, 330, 0.85, pump(0, 0, NORM, 30), boost=0.9) + g(400, 190, 0.95, crates(0, 0, NORM), boost=0.9)
             + g(760, 330, 0.5, calendar_icon(0, 0, NORM)) + g(1050, 190, 0.8, bolt(0, 0, NORM)))
    ud = updown(130 + 70, 330 - 52, False, NAVY, h=30) + updown(400 + 76, 190 - 56, False, BLUE, h=30) \
        + updown(760 + 76, 330 - 56, False, BLUE, h=30) + updown(1050 + 76, 190 - 56, True, BLUE, h=30)
    return kg_svg(n, edges, extra=o, after=icons + ud)


def cond_path() -> str:
    """부품 단가 ↓ → 부품 구매비 ↓ (조건 없음) / 부품 단가 ↓ → 부품 품질 ↓ (조건부, 점선) → 클레임 ↑ → 브랜드 ↓ → 매출 ↓.
    오른쪽 아래 칩 셋은 조건의 판정(TRUE · UNKNOWN · FALSE) — 글은 덱 라벨."""
    n = {"price": (110, 270, 62, "hub"), "cost": (380, 90, 62, "near"), "quality": (380, 420, 62, "near"),
         "claim": (640, 300, 62, "near"), "brand": (880, 150, 62, "near"), "rev": (1110, 330, 62, "far")}
    edges = [("price", "cost", NAVY), ("price", "quality", BLUE, True), ("quality", "claim", BLUE), ("claim", "brand", BLUE),
             ("brand", "rev", BLUE)]
    ud = (updown(110 + 80, 270 - 50, False, NAVY, h=30) + updown(380 + 80, 90 + 10, False, NAVY, h=30)
          + updown(380 + 80, 420 - 50, False, BLUE, h=30) + updown(640 + 80, 300 + 10, True, BLUE, h=30)
          + updown(880 + 80, 150 + 10, False, BLUE, h=30) + updown(1110 - 80, 330 + 70, False, BLUE, h=30))
    chips = []
    for i, fill in enumerate((SKY, PALE, WHITE)):
        chips.append(rect(560 + i * 215, 462, 200, 62, 12, fill=fill, stroke=NAVY, sw=3))
    return kg_svg(n, edges, after=ud + chips)


SMAP = {"profit": (700, 64, 60, "hub"), "cost": (1050, 78, 60, "near"), "delivery": (560, 205, 60, "near"),
        "quality": (860, 198, 60, "near"), "safety": (330, 330, 60, "near"), "avail": (650, 345, 64, "hub"),
        "energy": (1010, 335, 60, "near"), "knowledge": (520, 472, 60, "near")}


def strategy_kg() -> str:
    """전략맵(원형 노드 · 대각선): 관점 네 띠 위에 목표 여덟. 쿨러 사건이 지나는 길(무재해 → 가용성 → 납기 → 이익)은 파랑.
    목표 이름은 덱 라벨로 원 안에 얹는다."""
    lanes = [rect(14, y, KW - 28, 126, 14, fill=LIGHT if i % 2 == 0 else WHITE, stroke="none", sw=0)
             for i, y in enumerate((4, 138, 272, 406))]
    lanes += [line(200, y + 14, 200, y + 112, stroke=GREY, sw=2) for y in (4, 138, 272, 406)]
    edges = [("knowledge", "avail", NAVY), ("safety", "avail", BLUE), ("avail", "delivery", BLUE), ("delivery", "profit", BLUE),
             ("quality", "profit", NAVY), ("energy", "cost", NAVY), ("cost", "profit", NAVY)]
    return kg_svg(SMAP, edges, extra=lanes)


def main():
    out = {"조치후보_전체.svg": candidates(None), "조치후보_0.svg": candidates(0)}
    out["전략맵_그래프.svg"] = strategy_kg()
    out.update({"조치연결_그래프.svg": kg_skill(), "결정표_그래프.svg": kg_dmn(), "수직선_경계.svg": numline_pair(),
                "선행후행_경로.svg": lead_lag(), "조건부영향.svg": cond_path(), "성과경로_6.svg": tradeoff(6)})
    out.update({f"조치후보_{i}.svg": candidates(i) for i in (1, 2, 3, 4)})
    out.update({f"SOP문서_{k}.svg": sopdoc(k) for k in ("all", *SOP_BLOCKS)})
    out.update({f"운전모드_{i}.svg": modes(i) for i in range(4)})
    out.update({f"조치시점_{k}.svg": timeline(k) for k in ("all", "prevent", "mitigate", "remedy")})
    out.update({f"결정표_{i}.svg": dtable(i) for i in range(1, 8)})
    out.update({f"수직선_{k}.svg": numline(k) for k in ("ge", "gt", "range", "missing", "dup", "conflict")})
    out.update({f"히트_{k}.svg": hit(k) for k in ("base", "unique", "first", "priority", "collect")})
    out["전략맵_관점_재무.svg"] = strategy_map(lanes=(0,), hot_lane=0)
    out["전략맵_관점_고객.svg"] = strategy_map(lanes=(1,), hot_lane=1)
    out["전략맵_관점_내부.svg"] = strategy_map(lanes=(2,), hot_lane=2)
    out["전략맵_관점_학습.svg"] = strategy_map(lanes=(3,), hot_lane=3)
    out["전략맵_1.svg"] = strategy_map(edges=(0, 1), hot_edges=(0, 1))
    out["전략맵_2.svg"] = strategy_map(edges=(0, 1, 2), hot_edges=(2,))
    out["전략맵_3.svg"] = strategy_map(edges=(0, 1, 2, 3, 4), hot_edges=(3, 4))
    out["전략맵_4.svg"] = strategy_map(edges=(0, 1, 2, 3, 4, 5, 6), hot_edges=(5, 6))
    out.update({f"인터록여유_{i}.svg": margin(i) for i in range(1, 5)})
    out.update({f"성과경로_{i}.svg": tradeoff(i) for i in range(1, 6)})
    out.update({f"가정분석_{i}.svg": whatif(i) for i in range(1, 6)})
    for name, text in out.items():
        assert "<text" not in text
        (HERE / name).write_text(text, encoding="utf-8")
    print("wrote", len(out))


if __name__ == "__main__":
    main()
