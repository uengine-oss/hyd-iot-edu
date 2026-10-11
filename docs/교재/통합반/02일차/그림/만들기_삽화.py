"""통합반 2일차 v3 삽화(SVG)를 만든다. 글자는 넣지 않는다(라벨은 덱 MD의 요소로 얹는다).

사용: python 만들기_삽화.py            → 이 폴더에 SVG를 쓴다
화풍(색 · 선 굵기 · 그림 조각)은 1일차의 만들기_삽화.py를 복사한 삽화_기본.py에서 가져온다.
같은 그림을 여러 장에 걸쳐 쓰며 한 번에 한 부분만 밝히는 그림은 stage 인자로 단계별 파일을 낸다.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from 삽화_기본 import (  # noqa: E402
    BLUE, GREY, LIGHT, NAVY, NORM, OFF, ON, PALE, SKY, WHITE,
    arrow, bell, broken_cooler, cabinet, circle, cylinder_db, dots, dusty_cooler, equip_mini, fan, g, gauge,
    graph_icon, line, path, poly, radiator, rect, svg, thermo,
)

DASH = "11 9"


def col(st):
    """화살표 색: 밝힌 것은 파랑, 보통은 남색, 끈 것은 회색."""
    return BLUE if st is ON else NAVY if st is NORM else GREY


def check(cx, cy, r=30):
    return [circle(cx, cy, r, fill=SKY, sw=4),
            path(f"M {cx - r * 0.45},{cy} L {cx - r * 0.1},{cy + r * 0.35} L {cx + r * 0.5},{cy - r * 0.35}", sw=5)]


def cross(cx, cy, r=30, st=ON):
    k = r * 0.38
    return [circle(cx, cy, r, fill=WHITE, stroke=st.line, sw=4),
            line(cx - k, cy - k, cx + k, cy + k, stroke=st.line, sw=5), line(cx - k, cy + k, cx + k, cy - k, stroke=st.line, sw=5)]


def table_icon(cx, cy, st=ON):
    o = [rect(cx - 52, cy - 40, 104, 80, 7, fill=st.fill, stroke=st.line),
         rect(cx - 52, cy - 40, 104, 22, 7, fill=st.accent, stroke=st.line)]
    for dy in (2, 22):
        o.append(line(cx - 52, cy + dy, cx + 52, cy + dy, stroke=st.line, sw=2.5))
    for dx in (-18, 18):
        o.append(line(cx + dx, cy - 18, cx + dx, cy + 40, stroke=st.line, sw=2.5))
    return o


def sym_icon(x, y, st=ON):
    return thermo(x - 8, y + 22, st, s=0.62, level=0.7) + [arrow([(x + 16, y + 18), (x + 16, y - 22)], col(st), sw=3.5, size=9)]


def var_icon(x, y, st=ON):
    return thermo(x, y + 22, st, s=0.62, level=0.7)


def nut(cx, cy, st=ON, r=30):
    pts = [(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))) for a in range(0, 360, 60)]
    return [poly(pts, fill=st.accent, stroke=st.line, sw=3.5), circle(cx, cy, r * 0.42, fill=st.fill, stroke=st.line, sw=3)]


def building(cx, cy, st=ON):
    o = [rect(cx - 30, cy - 36, 60, 72, 5, fill=st.fill, stroke=st.line)]
    for r_ in range(2):
        for c_ in range(2):
            o.append(rect(cx - 20 + c_ * 24, cy - 26 + r_ * 20, 14, 12, 2, fill=st.accent, stroke=st.line, sw=2))
    o.append(rect(cx - 8, cy + 16, 16, 20, 2, fill=st.soft, stroke=st.line, sw=2.5))
    return o


def doc(cx, cy, st=ON):
    o = [rect(cx - 26, cy - 32, 52, 64, 6, fill=st.fill, stroke=st.line)]
    for dy in (-16, -2, 12):
        o.append(line(cx - 14, cy + dy, cx + 14, cy + dy, stroke=st.line, sw=2.5))
    return o


def node(cx, cy, r, st, parts, k=1.0, boost=1.0, dashed=False, fill=None):
    f = fill if fill is not None else (PALE if st is ON else WHITE)
    return [circle(cx, cy, r, fill=f, stroke=st.line, sw=4, stroke_dasharray=DASH if dashed else None)] + g(cx, cy, k, parts, boost=boost)


# ───────────────────────── 1. 유형을 그린 그림과 실제 대상을 그린 그림 ─────────────────────────

def mixed(stage=0) -> str:
    o: list[str] = []
    cols = (430, 720, 1010)
    for ri, (y, dashed) in enumerate(((130, True), (370, False))):
        st = OFF if stage not in (0, ri + 1) else (NORM if dashed else ON)
        for a, b in zip(cols, cols[1:]):
            o.append(arrow([(a + 70, y), (b - 72, y)], GREY if (dashed or st is OFF) else NAVY, sw=4.5, size=14))
        for i, x in enumerate(cols):
            o.append(circle(x, y, 62, fill=WHITE if (dashed or st is OFF) else PALE, stroke=st.line, sw=4,
                            stroke_dasharray=DASH if dashed else None))
            if i == 0:
                o += g(x, y, 0.78, equip_mini(0, 0, st), boost=1.1)
            elif i == 1:
                o += gauge(x, y, st, r=30, hot=(st is ON))
            else:
                o += g(x, y, 1.0, sym_icon(0, 0, st), boost=1.0)
    return svg(o)


# ───────────────────────── 2. 클래스 하나와 인스턴스 여럿 ─────────────────────────

def class_inst(stage=3) -> str:
    o: list[str] = []
    ys = (130, 215, 300, 385, 470)
    lit = {1: (), 2: (0,), 3: (0, 1, 2, 3, 4)}[stage]
    for i, y in enumerate(ys):
        o.append(arrow([(372, 300), (470, 300), (520, y), (588, y)], BLUE if i in lit else GREY, sw=4, size=12))
    cst = ON if stage == 1 else NORM
    o.append(rect(70, 185, 300, 230, 18, fill=PALE if stage == 1 else LIGHT, stroke=SKY if stage == 1 else NAVY, sw=4, stroke_dasharray=DASH))
    o.append(circle(220, 300, 70, fill=WHITE, sw=4, stroke_dasharray=DASH))
    o += g(220, 300, 1.0, gauge(0, 0, cst, r=44, ang=-70), boost=1.0)
    for i, y in enumerate(ys):
        st = ON if i in lit else OFF
        o += gauge(628, y, st, r=30, hot=(i == 0 and st is ON), ang=(-50, -120, -80, -140, -100)[i])
    return svg(o)


# ───────────────────────── 3. 설비 영역의 다섯 클래스 ─────────────────────────

def gallery(stage=0) -> str:
    o: list[str] = []
    xs = (120, 360, 600, 840, 1080)
    icons = (lambda st: g(0, 0, 0.72, equip_mini(0, 0, st), boost=1.2),
             lambda st: g(0, 0, 0.58, radiator(-44, -34, 88, 68, st, fins=8, r=7)),
             lambda st: gauge(0, 0, st, r=28, hot=(st is ON)),
             lambda st: g(0, 0, 0.9, var_icon(0, 0, st), boost=1.0),
             lambda st: nut(0, 0, st, r=26))
    for i, x in enumerate(xs):
        st = (ON if stage == i + 1 else OFF) if stage else NORM
        hot = stage == i + 1
        o += dots(x, 196, x, 292, color=GREY if st is OFF else NAVY, gap=13, r=3)
        o.append(rect(x - 78, 60, 156, 130, 14, fill=PALE if hot else WHITE, stroke=SKY if hot else st.line, sw=4, stroke_dasharray=DASH))
        o += [f'<g transform="translate({x} 125)">'] + icons[i](st if st is not ON else NORM) + ["</g>"]
        ist = ON if (hot or not stage) else OFF
        o.append(circle(x, 345, 50, fill=PALE if ist is ON else WHITE, stroke=ist.line, sw=4))
        o += [f'<g transform="translate({x} 345)">'] + icons[i](ist) + ["</g>"]
    return svg(o)


# ───────────────────────── 4. 속성: 클래스가 정한 칸과 인스턴스가 채운 값 ─────────────────────────

def props(stage=3) -> str:
    o: list[str] = []
    top, hh, rh = 40, 70, 78
    cards = ((40, 300, True), (460, 320, False), (840, 320, False))
    shown = {1: (0,), 2: (0, 1), 3: (0, 1, 2)}[stage]
    for i in range(5):
        y = top + hh + rh * i + rh / 2
        if 1 in shown:
            o += dots(346, y, 454, y, gap=14, r=2.6)
        if 2 in shown:
            o += dots(786, y, 834, y, gap=14, r=2.6)
    for ci, (x, w, is_class) in enumerate(cards):
        on = ci in shown
        ln = NAVY if on else GREY
        hot = on and ci == stage - 1
        o.append(rect(x, top, w, hh + rh * 5, 14, fill=WHITE, stroke=ln, sw=4, stroke_dasharray=DASH if (is_class or not on) else None))
        o.append(rect(x, top, w, hh, 14, fill=(SKY if hot and not is_class else PALE if on and not is_class else LIGHT), stroke=ln, sw=4,
                      stroke_dasharray=DASH if (is_class or not on) else None))
        for i in range(1, 5):
            o.append(line(x + 14, top + hh + rh * i, x + w - 14, top + hh + rh * i, stroke=GREY, sw=2))
        if not is_class and on:
            o += gauge(x + 44, top + hh / 2, ON, r=22, hot=(x == 460), ang=-50 if x == 460 else -120)
    return svg(o)


# ───────────────────────── 5. 같은 클래스의 세 인스턴스 ─────────────────────────

def asset3() -> str:
    o: list[str] = []
    xs = (220, 600, 980)
    for x in xs:
        o += dots(600 + (x - 600) * 0.28, 150, x, 222, gap=13, r=3)
    o.append(rect(480, 24, 240, 120, 14, fill=LIGHT, sw=4, stroke_dasharray=DASH))
    o += g(600, 84, 0.78, equip_mini(0, 0, NORM), boost=1.1)
    for x in xs:
        o += node(x, 300, 72, ON, equip_mini(0, 0, ON), k=0.95, boost=1.0)
    return svg(o)


# ───────────────────────── 6. 필수 속성과 선택 속성 ─────────────────────────

def limits() -> str:
    o: list[str] = []
    xs = (130, 365, 600, 835, 1070)
    has = (True, True, True, False, False)
    for x, h in zip(xs, has):
        o.append(rect(x - 104, 60, 208, 400, 14, fill=WHITE, sw=4))
        o.append(rect(x - 104, 60, 208, 66, 14, fill=PALE, sw=4))
        o += g(x - 70, 93, 0.5, var_icon(0, -4, ON), boost=1.6)
        o.append(line(x - 88, 300, x + 88, 300, stroke=GREY, sw=2))
        if h:
            o.append(rect(x - 80, 340, 160, 76, 38, fill=SKY, sw=3.5))
        else:
            o.append(rect(x - 80, 340, 160, 76, 38, fill=WHITE, stroke=GREY, sw=3.5, stroke_dasharray=DASH))
    return svg(o)


# ───────────────────────── 7. 클래스 계층과 상속 ─────────────────────────

def inherit(hot="child") -> str:
    o: list[str] = []
    xs = (220, 600, 980)
    o.append(path("M 600,190 L 600,250 M 220,250 L 980,250", sw=4))
    for x in xs:
        o.append(line(x, 250, x, 318, sw=4))
    o.append(poly([(600, 162), (582, 192), (618, 192)], fill=WHITE, stroke=NAVY, sw=4))
    p = hot == "parent"
    o.append(rect(420, 40, 360, 120, 14, fill=PALE if p else LIGHT, stroke=SKY if p else NAVY, sw=4, stroke_dasharray=None if p else DASH))
    for i, x in enumerate(xs):
        h = hot == "child" and i == 1
        o.append(rect(x - 170, 320, 340, 130, 14, fill=PALE if h else WHITE, stroke=SKY if h else NAVY, sw=4))
    return svg(o)


# ───────────────────────── 8. 클래스 층과 인스턴스 층 ─────────────────────────

def two_layers(stage=3) -> str:
    o: list[str] = []
    cols = (330, 590, 850, 1110)
    yt, yb = 150, 380
    top_on, bot_on = stage in (1, 3), stage in (2, 3)
    o.append(rect(14, 60, 1172, 180, 14, fill=LIGHT, stroke="none", sw=0))
    for a, b in zip(cols, cols[1:]):
        o.append(arrow([(a + 82, yt), (b - 84, yt)], NAVY if top_on else GREY, sw=4, size=13))
        o.append(arrow([(a + 54, yb), (b - 56, yb)], BLUE if bot_on else GREY, sw=4.5, size=13))
    bst = ON if bot_on else OFF
    for x in cols:
        o += dots(x, yt + 52, x, yb - 58, color=BLUE if stage == 3 else GREY, gap=13, r=3.2 if stage == 3 else 2.6)
        o.append(rect(x - 78, yt - 46, 156, 92, 12, fill=WHITE, stroke=NAVY if top_on else GREY, sw=4, stroke_dasharray=DASH))
        o.append(circle(x, yb, 50, fill=PALE if bot_on else WHITE, stroke=bst.line, sw=4))
    o += g(cols[0], yb, 0.62, equip_mini(0, 0, bst), boost=1.2)
    o += g(cols[1], yb, 0.5, radiator(-44, -34, 88, 68, bst, fins=8, r=7))
    o += gauge(cols[2], yb, bst, r=26, hot=bot_on)
    o += g(cols[3], yb, 0.85, var_icon(-8, 0, bst), boost=1.0)
    return svg(o)


# ───────────────────────── 9. 카디널리티 ─────────────────────────

def cardinality() -> str:
    o: list[str] = []
    xs = (150, 450, 750, 1050)
    ys3 = (120, 195, 270)
    links = {
        0: ([195], [195], [(0, 0)]),
        1: ([195], ys3, [(0, 0), (0, 1), (0, 2)]),
        2: (ys3, [195], [(0, 0), (1, 0), (2, 0)]),
        3: (ys3, ys3, [(0, 0), (0, 1), (1, 1), (2, 1), (2, 2)]),
    }
    for i, x in enumerate(xs):
        o.append(rect(x - 130, 70, 260, 250, 14, fill=LIGHT, stroke="none", sw=0))
        ls, rs, ed = links[i]
        for a, b in ed:
            o.append(arrow([(x - 52, ls[a]), (x + 50, rs[b])], NAVY, sw=3.5, size=11))
        for y in ls:
            o.append(circle(x - 72, y, 20, fill=WHITE, sw=4))
        for y in rs:
            o.append(circle(x + 72, y, 20, fill=SKY, sw=4))
    return svg(o)


def card_1n() -> str:
    """조치 방법 하나 → 단계 셋."""
    o: list[str] = []
    ys = (110, 260, 410)
    for y in ys:
        o.append(arrow([(322, 260), (430, 260), (480, y), (566, y)], BLUE, sw=4.5, size=13))
    o += node(240, 260, 80, ON, fan(0, 0, 46, ON, rot=20, hot=True), k=1.05)
    for y in ys:
        o += node(620, y, 50, ON, doc(0, 0, ON), k=0.85, fill=WHITE)
    return svg(o)


def card_nm() -> str:
    """부품 셋과 공급사 셋(다대다)."""
    o: list[str] = []
    ys = (95, 260, 425)
    L, R = 400, 800
    links = [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (2, 0), (2, 1)]
    for a, b in links:
        o.append(arrow([(L + 56, ys[a]), (R - 58, ys[b])], NAVY, sw=3.5, size=12))
    for y in ys:
        o += node(L, y, 52, ON, nut(0, 0, ON, r=26), fill=WHITE)
        o += node(R, y, 52, ON, building(0, 0, ON), k=0.8, fill=PALE)
    return svg(o)


# ───────────────────────── 10. 관계의 속성: 공급 조건 ─────────────────────────

def supplier() -> str:
    o: list[str] = []
    ys = (95, 260, 425)
    for y in ys:
        o.append(arrow([(262, 260), (330, 260), (400, y), (866, y)], BLUE, sw=4.5, size=13))
        o.append(rect(470, y - 34, 340, 68, 8, fill=WHITE, sw=3.5))
    o += node(190, 260, 70, ON, nut(0, 0, ON, r=34), fill=WHITE)
    for y in ys:
        o += node(920, y, 52, ON, building(0, 0, ON), k=0.8)
    return svg(o)


# ───────────────────────── 11. 흔한 실수: 값을 노드로 만든다 ─────────────────────────

def mistake_value() -> str:
    o: list[str] = []
    o.append(line(600, 30, 600, 490, stroke=GREY, sw=2.5, stroke_dasharray="6 8"))
    # 왼쪽: 값을 노드로
    A = (170, 250)
    for (x, y) in ((440, 130), (440, 370)):
        o.append(arrow([(A[0] + 70, A[1] + (y - 250) * 0.3), (x - 52, y)], GREY, sw=4, size=12))
        o.append(circle(x, y, 46, fill=WHITE, stroke=NAVY, sw=4, stroke_dasharray=DASH))
    o += node(*A, 72, NORM, var_icon(0, 0, NORM), k=1.3, boost=0.9)
    o += cross(520, 60, 24)
    # 오른쪽: 속성으로
    B = (790, 250)
    o.append(line(B[0] + 72, B[1], 960, B[1], sw=3.5))
    o.append(rect(960, 170, 200, 160, 10, fill=LIGHT, sw=3.5))
    o += node(*B, 72, ON, var_icon(0, 0, ON), k=1.3, boost=0.9)
    o += check(1130, 60, 24)
    return svg(o)


# ───────────────────────── 12. 스키마 없이: 같은 대상이 여러 노드로 ─────────────────────────

def dup() -> str:
    o: list[str] = []
    cs = ((330, 120), (600, 280), (870, 120))
    nb = ((130, 120), (600, 450), (1070, 120))
    for (cx, cy), (nx, ny) in zip(cs, nb):
        d_ = math.hypot(nx - cx, ny - cy)
        ux, uy = (nx - cx) / d_, (ny - cy) / d_
        o.append(line(cx + ux * 60, cy + uy * 60, nx - ux * 50, ny - uy * 50, sw=4))
    for i in range(3):
        a, b = cs[i], cs[(i + 1) % 3]
        o += dots(a[0] + (b[0] - a[0]) * 0.3, a[1] + (b[1] - a[1]) * 0.3, a[0] + (b[0] - a[0]) * 0.7, a[1] + (b[1] - a[1]) * 0.7,
                  color=BLUE, gap=16, r=3.4)
    for c in cs:
        o += node(*c, 58, ON, radiator(-44, -34, 88, 68, ON, fins=8, r=7), k=0.62)
    o += node(*nb[0], 46, NORM, equip_mini(0, 0, NORM), k=0.6, boost=1.2)
    o.append(circle(*nb[1], 46, fill=WHITE, sw=4))
    o += gauge(nb[1][0], nb[1][1], NORM, r=26)
    o += node(*nb[2], 46, NORM, nut(0, 0, NORM, r=24))
    return svg(o)


# ───────────────────────── 13. 공통 식별자 ─────────────────────────

def shared_id(stage=2) -> str:
    o: list[str] = []
    C = (600, 250)
    spots = {"kg": (180, 190), "ts": (1010, 92), "biz": (1010, 352)}
    on = {"kg": True, "ts": True, "biz": stage == 2}
    for k, (x, y) in spots.items():
        o.append(line(C[0], C[1], x, y, stroke=BLUE if on[k] else GREY, sw=4.5))
    o.append(rect(C[0] - 150, C[1] - 52, 300, 104, 52, fill=SKY, sw=4))
    o.append(circle(C[0] - 112, C[1], 13, fill=WHITE, sw=3.5))
    for k, (x, y) in spots.items():
        o.append(circle(x, y, 66, fill=WHITE, stroke=NAVY if on[k] else GREY, sw=4))
    o += g(*spots["kg"], 1.0, graph_icon(0, 0, ON), boost=1.0)
    o += g(spots["ts"][0] - 5, spots["ts"][1] - 2, 0.8, cylinder_db(0, 0, ON), boost=1.1)
    o += g(*spots["biz"], 0.9, table_icon(0, 0, ON if on["biz"] else OFF), boost=1.05)
    return svg(o)


# ───────────────────────── 14. 관계 정의와 유효한 연결 ─────────────────────────

def endpoint(stage=2) -> str:
    o: list[str] = []
    A, B, V = 300, 700, 930
    for y, ok in ((170, True), (395, False)):
        dim = (not ok) and stage == 1
        st = OFF if dim else ON
        if ok:
            o.append(arrow([(A + 66, y), (B - 68, y)], BLUE if stage == 1 else NAVY, sw=5, size=15))
        else:
            o += dots(A + 70, y, B - 86, y, color=GREY if dim else NAVY, gap=17, r=3.6)
            o.append(arrow([(B - 84, y), (B - 68, y)], GREY if dim else NAVY, sw=4, size=14))
        o.append(circle(A, y, 60, fill=WHITE if dim else PALE, stroke=st.line, sw=4))
        o += gauge(A, y, st, r=30, hot=not dim)
        o.append(circle(B, y, 60, fill=PALE if ok else WHITE, stroke=st.line, sw=4))
        if ok:
            o += g(B, y, 1.0, var_icon(-8, 0, ON), boost=1.0)
        else:
            o += g(B, y, 0.78, equip_mini(0, 0, OFF if dim else NORM), boost=1.1)
        o += check(V, y) if ok else cross(V, y, st=st)
    return svg(o)


# ───────────────────────── 15. 설계 따라가기: 클래스 그림 ─────────────────────────

def classdiagram(stage=4) -> str:
    """1: 클래스 상자만, 2: 속성 칸을 밝힘, 3: 관계를 밝힘, 4: 완성본."""
    o: list[str] = []
    xs = (125, 441, 757, 1073)
    bw, y0, bh = 220, 40, 170
    part = (441, 330)
    ac = GREY if stage < 3 else BLUE if stage == 3 else NAVY
    if stage >= 3:
        for a, b in zip(xs, xs[1:]):
            o.append(arrow([(a + bw / 2 + 4, y0 + 85), (b - bw / 2 - 6, y0 + 85)], ac, sw=4.5, size=13))
        o.append(arrow([(part[0], y0 + bh + 4), (part[0], part[1] - 6)], ac, sw=4.5, size=13))
    boxes = [(x, y0) for x in xs] + [(part[0], part[1])]
    for x, y in boxes:
        body_hot = stage == 2
        o.append(rect(x - bw / 2, y, bw, bh, 12, fill=PALE if body_hot else WHITE, stroke=NAVY, sw=4))
        o.append(rect(x - bw / 2, y, bw, 52, 12, fill=SKY if stage == 1 else LIGHT, stroke=NAVY, sw=4))
    return svg(o)


# ───────────────────────── 16. 속성 그래프: 노드 · 레이블 · 관계 유형 · 속성 ─────────────────────────

def prop_graph(stage=3) -> str:
    o: list[str] = []
    A, B = (330, 215), (870, 215)
    rel_on, card_on = stage >= 2, stage >= 3
    o.append(arrow([(A[0] + 88, A[1]), (B[0] - 90, B[1])], (BLUE if stage == 2 else NAVY) if rel_on else GREY, sw=7, size=20))
    for c, fill in ((A, WHITE), (B, SKY)):
        o.append(line(c[0], c[1] - 80, c[0], c[1] - 118, sw=3.5))
        o.append(line(c[0], c[1] + 80, c[0], c[1] + 122, stroke=NAVY if card_on else GREY, sw=3.5))
        o.append(circle(c[0], c[1], 82, fill=fill, sw=5))
        o.append(rect(c[0] - 105, c[1] - 162, 210, 46, 23, fill=SKY if stage == 1 else PALE, sw=3.5))
        o.append(rect(c[0] - 150, c[1] + 122, 300, 130, 10, fill=PALE if stage == 3 else LIGHT if card_on else WHITE,
                      stroke=NAVY if card_on else GREY, sw=3.5, stroke_dasharray=None if card_on else DASH))
    o.append(rect(600 - 92, A[1] - 24, 184, 48, 8, fill=SKY if stage == 2 else WHITE, stroke=NAVY if rel_on else GREY, sw=3.5))
    o += g(*A, 1.0, gauge(0, 0, ON, r=44, hot=True), boost=1.0)
    o += g(*B, 1.5, var_icon(-8, 0, NORM), boost=0.8)
    return svg(o)


# ───────────────────────── 17. 관계형 DB의 조인과 그래프의 관계 ─────────────────────────

def join(stage=2) -> str:
    o: list[str] = []

    def table(x, y, rows, key_col):
        out = [rect(x, y, 340, 50 + rows * 46, 8, fill=WHITE, stroke=NAVY, sw=3.5), rect(x, y, 340, 50, 8, fill=LIGHT, stroke=NAVY, sw=3.5)]
        out.append(rect(x + key_col * 170 + 4, y + 4, 162, 42 + rows * 46, 6, fill=PALE if stage == 1 else LIGHT,
                        stroke=SKY if stage == 1 else GREY, sw=2.5))
        for r_ in range(1, rows):
            out.append(line(x, y + 50 + r_ * 46, x + 340, y + 50 + r_ * 46, stroke=GREY, sw=2))
        out.append(line(x + 170, y, x + 170, y + 50 + rows * 46, stroke=GREY, sw=2))
        return out
    o += table(40, 70, 1, 0)
    o += table(40, 300, 2, 1)
    o.append(arrow([(125, 172), (125, 236), (295, 236), (295, 294)], BLUE if stage == 1 else GREY, sw=4.5, size=13))
    o.append(line(600, 30, 600, 490, stroke=GREY, sw=2.5, stroke_dasharray="6 8"))
    rst = ON if stage == 2 else OFF
    P = (760, 260)
    for y in (150, 370):
        o.append(arrow([(P[0] + 62, 260 + (y - 260) * 0.3), (1004, y)], BLUE if stage == 2 else GREY, sw=4.5, size=13))
        o += node(1060, y, 50, rst, building(0, 0, rst), k=0.78)
    o += node(*P, 62, rst, nut(0, 0, rst, r=30), fill=WHITE)
    return svg(o)


# ───────────────────────── 18. 조회 결과를 읽는 법 ─────────────────────────

def result() -> str:
    o: list[str] = []
    x0, y0, cw, rh = 50, 130, 220, 80
    o.append(rect(x0, y0, cw * 2, rh * 3, 10, fill=WHITE, sw=4))
    o.append(rect(x0, y0, cw * 2, rh, 10, fill=LIGHT, sw=4))
    o.append(rect(x0 + 5, y0 + rh + 5, cw * 2 - 10, rh - 10, 6, fill=PALE, stroke=SKY, sw=3))
    o.append(line(x0, y0 + rh * 2, x0 + cw * 2, y0 + rh * 2, stroke=GREY, sw=2))
    o.append(line(x0 + cw, y0, x0 + cw, y0 + rh * 3, stroke=GREY, sw=2))
    o.append(line(560, 30, 560, 490, stroke=GREY, sw=2.5, stroke_dasharray="6 8"))
    C = (740, 260)
    o.append(arrow([(C[0] + 62, 240), (990, 150)], BLUE, sw=5.5, size=15))
    o.append(arrow([(C[0] + 62, 280), (990, 370)], NAVY, sw=4, size=13))
    o += node(*C, 64, ON, radiator(-44, -34, 88, 68, ON, fins=8, r=7), k=0.7)
    o += gauge(1034, 150, ON, r=38, hot=True)
    o += gauge(1034, 370, NORM, r=38, ang=-120)
    return svg(o)


# ───────────────────────── 19. Cypher 표기 ─────────────────────────

def notation(stage=3) -> str:
    """1: 노드 표기, 2: 관계 표기, 3: 변수."""
    o: list[str] = []
    A, B = (270, 105), (930, 105)
    n_on, r_on = stage in (1, 3), stage in (2, 3)
    o.append(arrow([(A[0] + 62, A[1]), (B[0] - 64, B[1])], (BLUE if stage == 2 else NAVY) if r_on else GREY, sw=5.5, size=17))
    o.append(circle(*A, 58, fill=WHITE, stroke=NAVY if n_on else GREY, sw=4.5))
    o.append(circle(*B, 58, fill=SKY if n_on else WHITE, stroke=NAVY if n_on else GREY, sw=4.5))
    o += gauge(A[0], A[1], ON if n_on else OFF, r=30, hot=n_on)
    o += g(*B, 1.0, var_icon(-8, 0, NORM if n_on else OFF), boost=1.0)
    for x in (270, 600, 930):
        lit = r_on if x == 600 else n_on
        o += dots(x, 180 if x != 600 else 122, x, 268, color=NAVY if lit else GREY, gap=13, r=3)
    y = 320
    o.append(line(440, y, 480, y, stroke=NAVY if r_on else GREY, sw=5.5))
    o.append(arrow([(720, y), (760, y)], NAVY if r_on else GREY, sw=5.5, size=17))
    o.append(rect(100, y - 48, 340, 96, 48, fill=PALE if stage == 1 else WHITE, stroke=NAVY if n_on else GREY, sw=4.5))
    o.append(rect(760, y - 48, 340, 96, 48, fill=PALE if n_on else WHITE, stroke=NAVY if n_on else GREY, sw=4.5))
    o.append(rect(480, y - 40, 240, 80, 6, fill=PALE if stage == 2 else LIGHT if r_on else WHITE, stroke=NAVY if r_on else GREY, sw=4.5))
    return svg(o)


# ───────────────────────── 20. 방향이 섞인 경로와 한 줄의 패턴 ─────────────────────────

def path_query(stage=2) -> str:
    """1: 화살표를 따라가는 두 걸음, 2: 거슬러 가는 걸음."""
    o: list[str] = []
    P, S, F = (130, 170), (390, 170), (650, 170)
    Cs = [(900, 62), (900, 170), (900, 278)]
    fwd = BLUE if stage == 1 else NAVY
    o.append(arrow([(P[0] + 50, 170), (S[0] - 52, 170)], fwd, sw=4.5, size=14))
    o.append(arrow([(S[0] + 50, 170), (F[0] - 60, 170)], fwd, sw=4.5, size=14))
    cst = ON if stage == 2 else OFF
    for c in Cs:
        ang = math.atan2(F[1] - c[1], F[0] - c[0])
        o.append(arrow([(c[0] + 46 * math.cos(ang), c[1] + 46 * math.sin(ang)),
                        (F[0] - 62 * math.cos(ang), F[1] - 62 * math.sin(ang))], BLUE if stage == 2 else GREY, sw=5, size=15))
    o.append(circle(*P, 46, fill=PALE, sw=4))
    o += g(*P, 1.0, bell(0, -3, ON, 1.6), boost=1.0)
    o.append(circle(*S, 46, fill=PALE, sw=4))
    o += g(*S, 1.0, sym_icon(0, 0, ON), boost=1.0)
    o.append(circle(*F, 54, fill=SKY, sw=4))
    o += g(*F, 0.62, broken_cooler(0, 0, NORM), boost=1.0)
    for c, fn, k in zip(Cs, (dusty_cooler, lambda x, y, st: fan(x, y, 46, st, rot=35), cabinet), (0.5, 0.6, 0.5)):
        o.append(circle(*c, 42, fill=PALE if stage == 2 else WHITE, stroke=cst.line, sw=4))
        o += g(*c, k, fn(0, 0, cst))
    o.append(rect(40, 388, 1120, 62, 10, fill=LIGHT, sw=3.5))
    return svg(o)


# ───────────────────────── 21. 예시 인스턴스 다섯과 관계 넷 ─────────────────────────

def instances5() -> str:
    o: list[str] = []
    xs = (150, 450, 750, 1050)
    y = 200
    for a, b in zip(xs, xs[1:]):
        o.append(arrow([(a + 64, y), (b - 66, y)], BLUE, sw=4.5, size=14))
    o.append(arrow([(450, y + 64), (450, 372)], BLUE, sw=4.5, size=14))
    o += node(xs[0], y, 60, ON, equip_mini(0, 0, ON), k=0.78, boost=1.1)
    o += node(xs[1], y, 60, ON, radiator(-44, -34, 88, 68, ON, fins=8, r=7), k=0.62)
    o.append(circle(xs[2], y, 60, fill=PALE, sw=4))
    o += gauge(xs[2], y, ON, r=30, hot=True)
    o += node(xs[3], y, 60, ON, var_icon(0, 0, ON), k=1.0)
    o += node(450, 430, 54, ON, nut(0, 0, ON, r=28), fill=WHITE)
    return svg(o)


def main():
    out = {
        "유형과대상_0.svg": mixed(0), "유형과대상_1.svg": mixed(1), "유형과대상_2.svg": mixed(2),
        "클래스인스턴스_1.svg": class_inst(1), "클래스인스턴스_2.svg": class_inst(2), "클래스인스턴스_3.svg": class_inst(3),
        **{f"설비클래스_{i}.svg": gallery(i) for i in range(6)},
        "속성_1.svg": props(1), "속성_2.svg": props(2), "속성_3.svg": props(3),
        "설비세대.svg": asset3(), "한계값.svg": limits(),
        "상속_상위.svg": inherit("parent"), "상속_하위.svg": inherit("child"),
        "두층_1.svg": two_layers(1), "두층_2.svg": two_layers(2), "두층_3.svg": two_layers(3),
        "카디널리티.svg": cardinality(), "일대다.svg": card_1n(), "다대다.svg": card_nm(),
        "공급조건.svg": supplier(), "실수_값노드.svg": mistake_value(),
        "여러노드.svg": dup(), "공통식별자_1.svg": shared_id(1), "공통식별자_2.svg": shared_id(2),
        "연결조건_1.svg": endpoint(1), "연결조건_2.svg": endpoint(2),
        **{f"설계_{i}.svg": classdiagram(i) for i in (1, 2, 3, 4)},
        "속성그래프_1.svg": prop_graph(1), "속성그래프_2.svg": prop_graph(2), "속성그래프_3.svg": prop_graph(3),
        "조인_1.svg": join(1), "조인_2.svg": join(2), "결과읽기.svg": result(),
        "표기_1.svg": notation(1), "표기_2.svg": notation(2), "표기_3.svg": notation(3),
        "경로질의_1.svg": path_query(1), "경로질의_2.svg": path_query(2), "예시인스턴스.svg": instances5(),
    }
    for name, text in out.items():
        assert "<text" not in text
        (HERE / name).write_text(text, encoding="utf-8")
    print("wrote", len(out))


if __name__ == "__main__":
    main()
