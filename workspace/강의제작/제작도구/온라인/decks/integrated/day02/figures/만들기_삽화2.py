"""통합반 2회차 단원 01 · 02 · 03 삽화(SVG)를 만든다. 글자는 넣지 않는다(라벨은 덱 MD의 요소로 얹는다).

사용: <py> 만들기_삽화2.py            → 이 폴더에 SVG를 쓴다
색 · 선 굵기 · 그림 조각은 공용 조각 `workspace/강의제작/제작도구/온라인/tools/deck/삽화_기본.py`와
1회차 생성기(`decks/integrated/day01/figures/만들기_삽화.py`)의 것과 같다. 점선은 짧은 선분으로 긋는다(PyMuPDF가 dasharray를 그리지 않는다).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = next(p for p in HERE.parents if (p / ".git").exists())
sys.path.insert(0, str(ROOT / "workspace/강의제작/제작도구/온라인/tools/deck"))

from 삽화_기본 import (BLUE, GREY, LIGHT, NAVY, NORM, OFF, ON, PALE, SKY, WHITE, St, arrow, circle, equip_mini,  # noqa: E402
                    fan, g, gauge, line, path, radiator, rect, svg, thermo, broken_cooler, book_icon, cylinder_db, graph_icon, poly)


def dash_line(x1, y1, x2, y2, color=NAVY, sw=3.5, on=10, off=8):
    """점선을 짧은 선분으로 그린다(1회차 생성기의 dash_line과 같다)."""
    n = math.hypot(x2 - x1, y2 - y1)
    ux, uy = (x2 - x1) / n, (y2 - y1) / n
    o, t = [], 0.0
    while t < n - 1:
        e = min(t + on, n)
        o.append(line(round(x1 + ux * t, 1), round(y1 + uy * t, 1), round(x1 + ux * e, 1), round(y1 + uy * e, 1), stroke=color, sw=sw))
        t = e + off
    return o


def dash_rect(x, y, w, h, color=NAVY, sw=3.5, on=10, off=8):
    return (dash_line(x, y, x + w, y, color, sw, on, off) + dash_line(x + w, y, x + w, y + h, color, sw, on, off)
            + dash_line(x + w, y + h, x, y + h, color, sw, on, off) + dash_line(x, y + h, x, y, color, sw, on, off))


def edge(a, b, color=NAVY, sw=4.5, size=15, gap_a=5, gap_b=9):
    """원 a(x, y, r) 테두리에서 원 b 테두리까지 화살표. 화살촉은 b 쪽(1회차 _edge_arrow와 같다)."""
    (ax, ay, ar), (bx, by, br) = a, b
    d_ = math.hypot(bx - ax, by - ay)
    ux, uy = (bx - ax) / d_, (by - ay) / d_
    return [arrow([(ax + ux * (ar + gap_a), ay + uy * (ar + gap_a)), (bx - ux * (br + gap_b), by - uy * (br + gap_b))], color, sw=sw, size=size)]


def tag(tx, ty, to, hot=False, sw=3):
    """작은 둥근 꼬리표와 원 테두리 점 to까지의 끈(1회차 _tag와 같은 꼴, 폭만 넓혔다)."""
    return [line(tx, ty, to[0], to[1], stroke=NAVY, sw=sw),
            rect(tx - 44, ty - 17, 88, 34, 17, fill=SKY if hot else PALE, stroke=NAVY, sw=sw), circle(tx - 28, ty, 4.5, fill=WHITE, stroke=NAVY, sw=2.5)]


def cooler_node(x, y, r, st=NORM, fill=WHITE, stroke=NAVY, sw=4):
    return [circle(x, y, r, fill=fill, stroke=stroke, sw=sw)] + g(x, y, 0.62 * r / 56, radiator(-44, -34, 88, 68, st, fins=8, r=7))


def equip_node(x, y, r, st=NORM, fill=WHITE, stroke=NAVY, sw=4):
    return [circle(x, y, r, fill=fill, stroke=stroke, sw=sw)] + g(x, y + 4, 0.55 * r / 50, equip_mini(0, 0, st))


def sensor_node(x, y, r, st=NORM, fill=WHITE, stroke=NAVY, sw=4, hot=False):
    return [circle(x, y, r, fill=fill, stroke=stroke, sw=sw)] + gauge(x, y, st, r=r * 0.5, hot=hot)


def fan_node(x, y, r, st=NORM, fill=WHITE, stroke=NAVY, sw=4):
    return [circle(x, y, r, fill=fill, stroke=stroke, sw=sw)] + fan(x, y, r * 0.62, st, rot=20)


def var_node(x, y, r, fill=PALE, stroke=BLUE, sw=4):
    """상태 변수(물리량 유온): 온도계."""
    return [circle(x, y, r, fill=fill, stroke=stroke, sw=sw)] + thermo(x, y + r * 0.42, ON, s=0.5 * r / 50, level=0.62)


# ───────────────────────── 5장: 클래스와 인스턴스 ─────────────────────────

def class_instance() -> str:
    """위: 클래스 상자 둘(설비 · 구성 요소). 아래: 그 클래스에 속하는 인스턴스 원(HYD-01 · 02 · 03 / 오일 쿨러 · 쿨러 팬).
    상자와 원은 가는 회색 점선으로 잇는다. 왼쪽 띠는 두 줄의 이름(클래스 · 인스턴스) 라벨 자리로 비운다."""
    o: list[str] = [rect(10, 20, 1180, 140, 14, fill=PALE, stroke="none", sw=0), rect(10, 190, 1180, 320, 14, fill=LIGHT, stroke="none", sw=0)]
    boxes = {"asset": (300, 640), "comp": (760, 1150)}
    for x0, x1 in boxes.values():
        o.append(rect(x0, 45, x1 - x0, 90, 12, fill=WHITE, stroke=BLUE, sw=4))
    yi, ri = 315, 56
    inst = [("asset", 360, equip_node), ("asset", 470, equip_node), ("asset", 580, equip_node),
            ("comp", 860, cooler_node), ("comp", 1050, fan_node)]
    for cls, x, _ in inst:
        x0, x1 = boxes[cls]
        o += dash_line((x0 + x1) / 2 + (x - (x0 + x1) / 2) * 0.35, 137, x, yi - ri - 6, GREY, 3, 8, 7)
    for cls, x, fn in inst:
        o += fn(x, yi, ri if cls == "comp" else 48, NORM)
    return svg(o)


# ───────────────────────── 6장: 설비가 늘 때 쿨러를 그리는 두 방법 ─────────────────────────

def cooler_two_ways() -> str:
    """왼쪽: 설비 셋이 저마다 쿨러 원을 하나씩(같은 모양의 원 셋). 오른쪽: 설비 셋이 쿨러 원 하나를 함께 가리키고,
    그 옆에 적을 자리가 없는 정비 기록(점선 테두리)."""
    o: list[str] = []
    for ox in (0, 610):
        o.append(rect(ox + 15, 8, 560, 504, 14, fill=LIGHT, stroke="none", sw=0))
    ye, yc = 120, 330
    lx = (130, 295, 460)
    for x in lx:
        o += edge((x, ye, 46), (x, yc, 50), NAVY, sw=4)
    for x in lx:
        o += equip_node(x, ye, 46)
        o += cooler_node(x, yc, 50)
    rx = (740, 905, 1070)
    C = (905, yc, 56)
    for x in rx:
        o += edge((x, ye, 46), C, NAVY, sw=4)
    for x in rx:
        o += equip_node(x, ye, 46)
    o += cooler_node(*C, fill=WHITE)
    o += dash_rect(1030, yc - 52, 84, 104, BLUE, 3.5, 9, 8)
    for dy in (-26, -4, 18):
        o += dash_line(1046, yc + dy, 1098, yc + dy, GREY, 3, 7, 7)
    return svg(o)


# ───────────────────────── 10장: 클래스가 정하는 칸과 인스턴스가 채우는 속성값 ─────────────────────────

def slots_values() -> str:
    """왼쪽: 클래스 카드(머리 + 빈 칸 셋, 점선). 오른쪽: 인스턴스 카드(머리 + 채운 칸 셋, 가운데 칸은 연하늘 바탕 · 파란 테두리로 강조해 강조 글씨가 읽힌다). 사이에 굵은 화살표 하나."""
    o: list[str] = []
    cards = ((60, False), (720, True))
    for x0, filled in cards:
        o.append(rect(x0, 20, 420, 400, 14, fill=WHITE, stroke=BLUE if filled else NAVY, sw=4 if filled else 3.5))
        o.append(rect(x0, 20, 420, 92, 14, fill=PALE if filled else LIGHT, stroke="none", sw=0))
        o.append(line(x0, 112, x0 + 420, 112, stroke=NAVY, sw=3))
        o += g(x0 + 52, 66, 1.0, gauge(0, 0, ON if filled else NORM, r=26, hot=filled))
        for i, y in enumerate((140, 230, 320)):
            if filled:
                o.append(rect(x0 + 30, y, 360, 70, 10, fill=PALE if i == 1 else LIGHT, stroke=BLUE if i == 1 else NAVY, sw=4 if i == 1 else 3))
            else:
                o.append(rect(x0 + 30, y, 360, 70, 10, fill=LIGHT, stroke="none", sw=0))
                o += dash_rect(x0 + 30, y, 360, 70, GREY, 3, 9, 7)
    o.append(arrow([(500, 220), (700, 220)], BLUE, sw=6, size=18))
    return svg(o)


# ───────────────────────── 12장: 글자 칸과 관계의 차이 ─────────────────────────

def text_vs_relation() -> str:
    """왼쪽: 센서 원에 붙은 글자 칸 하나, 칸 뒤로 이어지는 길이 없다(회색 점선이 가위표에서 끊김).
    오른쪽: 쿨러 원이 센서 둘로 이어지고, 고장 유형 원이 쿨러를 가리킨다(저장된 방향대로 화살촉)."""
    o: list[str] = []
    for ox in (0, 610):
        o.append(rect(ox + 15, 8, 560, 504, 14, fill=LIGHT if ox == 0 else PALE, stroke="none", sw=0))
    # 왼쪽
    S = (130, 250, 56)
    o.append(line(S[0] + S[2], S[1], 230, S[1], stroke=NAVY, sw=3))
    o.append(rect(230, S[1] - 42, 230, 84, 12, fill=WHITE, stroke=NAVY, sw=3))
    o += dash_line(468, S[1], 520, S[1], GREY, 3, 8, 7)
    o += [line(512, S[1] - 14, 540, S[1] + 14, stroke=BLUE, sw=5), line(540, S[1] - 14, 512, S[1] + 14, stroke=BLUE, sw=5)]
    o += sensor_node(*S, hot=True)
    # 오른쪽: 유온 센서 ← 쿨러 → 냉각 효율 센서, 고장 유형 → 쿨러
    T, C, E, F = (680, 250, 44), (950, 250, 56), (1100, 110, 50), (1100, 395, 54)
    o += edge(C, T, NAVY, sw=4.5) + edge(C, E, NAVY, sw=4.5) + edge(F, C, NAVY, sw=4.5)
    o += sensor_node(*T, hot=True)
    o += cooler_node(*C, fill=SKY)
    o += sensor_node(*E)
    o += [circle(*F, fill=WHITE, stroke=NAVY, sw=4)] + g(F[0], F[1], 0.5, broken_cooler(0, 0, NORM))
    return svg(o)


# ───────────────────────── 14장: 한계를 센서에 둘 때와 상태 변수에 둘 때 ─────────────────────────

def limit_state_variable() -> str:
    """왼쪽: 유온 센서 둘에 같은 한계 꼬리표가 하나씩(두 꼬리표 강조). 오른쪽: 유온 센서 둘이 상태 변수 원 하나를 가리키고,
    한계 꼬리표는 상태 변수 원에 하나."""
    o: list[str] = []
    for ox in (0, 610):
        o.append(rect(ox + 15, 8, 560, 504, 14, fill=LIGHT if ox == 0 else PALE, stroke="none", sw=0))
    for y in (120, 330):
        S = (170, y, 52)
        o += tag(320, y, (S[0] + S[2], y), hot=True)
        o += sensor_node(*S, hot=True)
    V = (1010, 225, 66)
    for y in (120, 330):
        S = (730, y, 52)
        o += edge(S, V, NAVY, sw=4.5)
        o += sensor_node(*S, hot=True)
    o += tag(1010, 392, (V[0], V[1] + V[2]), hot=True)
    o += var_node(*V)
    return svg(o)


# ───────────────────────── 18장: 관계 유형을 클래스 사이에 한 번 정한다 ─────────────────────────

def relation_type_once() -> str:
    """위 띠(연하늘): 클래스 상자 둘(구성 요소 → 센서)과 이름 붙은 화살표 하나, 양 끝에 작은 파란 고리.
    아래 띠(흰): 같은 꼴의 인스턴스 쌍 셋(쿨러 원 → 센서 원). 왼쪽 끝은 두 띠의 이름 라벨 자리로 비운다."""
    o: list[str] = [rect(15, 10, 1170, 196, 16, fill=PALE, stroke="none", sw=0), rect(15, 222, 1170, 292, 16, fill=WHITE, stroke=GREY, sw=3)]
    o.append(rect(330, 60, 240, 96, 12, fill=WHITE, stroke=BLUE, sw=4))
    o.append(rect(900, 60, 240, 96, 12, fill=WHITE, stroke=BLUE, sw=4))
    o.append(arrow([(580, 108), (888, 108)], NAVY, sw=5, size=17))
    for x in (586, 882):
        o.append(circle(x, 108, 11, fill="none", stroke=BLUE, sw=4))
    pairs = (290, 600, 910)
    for x0 in pairs:
        A, B = (x0 + 30, 330, 38), (x0 + 190, 330, 38)
        o += edge(A, B, NAVY, sw=4, size=13)
        o += cooler_node(*A, sw=3.5)
        o += sensor_node(*B, sw=3.5)
    return svg(o)


# ───────────────────────── 단원 02: 온톨로지 스키마 ─────────────────────────

def person(cx, cy, st=NORM, r=17):
    """사람 하나(머리 원 + 어깨)."""
    return [circle(cx, cy - r * 0.6, r, fill=st.fill, stroke=st.line, sw=3),
            path(f"M {cx - r * 1.7},{cy + r * 2.1} Q {cx - r * 1.7},{cy + r * 0.6} {cx},{cy + r * 0.6} "
                 f"Q {cx + r * 1.7},{cy + r * 0.6} {cx + r * 1.7},{cy + r * 2.1} Z", fill=st.soft, stroke=st.line, sw=3)]


def schema_and_data() -> str:
    """24장: 왼쪽 정의서(머리 띠 + 항목 넷, 항목마다 작은 표시), 오른쪽 연회색 칸에 그 정의대로 채운 인스턴스 사슬 둘
    (설비 → 쿨러 → 센서). 사이에 굵은 파란 화살표."""
    o: list[str] = [rect(40, 20, 470, 480, 14, fill=WHITE, stroke=BLUE, sw=4), rect(40, 20, 470, 80, 14, fill=PALE, stroke="none", sw=0),
                    line(40, 100, 510, 100, stroke=NAVY, sw=3), rect(660, 20, 525, 480, 14, fill=LIGHT, stroke="none", sw=0)]
    for i, y in enumerate((120, 215, 310, 405)):
        o.append(rect(65, y, 420, 75, 10, fill=LIGHT, stroke=NAVY, sw=2.5))
        cx, cy = 105, y + 37
        if i == 0:
            o.append(rect(cx - 18, cy - 14, 36, 28, 5, fill=WHITE, stroke=NAVY, sw=3))
        elif i == 1:
            o += [line(cx - 18, cy, cx - 4, cy, stroke=NAVY, sw=3), rect(cx - 4, cy - 11, 26, 22, 11, fill=PALE, stroke=NAVY, sw=3)]
        elif i == 2:
            o.append(arrow([(cx - 20, cy), (cx + 20, cy)], NAVY, sw=4, size=11))
        else:
            o += [circle(cx - 11, cy, 9, fill="none", stroke=BLUE, sw=3.5), circle(cx + 11, cy, 9, fill="none", stroke=BLUE, sw=3.5)]
    o.append(arrow([(530, 260), (640, 260)], BLUE, sw=6, size=18))
    for y in (165, 370):
        E, C, S = (740, y, 40), (905, y, 40), (1070, y, 40)
        o += edge(E, C, NAVY, sw=4, size=13) + edge(C, S, NAVY, sw=4, size=13)
        o += equip_node(*E, sw=3.5) + cooler_node(*C, sw=3.5) + sensor_node(*S, sw=3.5)
    return svg(o)


def _record_card(x0, y0, w, h, rows, st_rows, head_y=70):
    """적은 사람 하나의 기록 카드: 머리(사람) + 줄 셋. st_rows: 줄마다 'norm' · 'diff'(파란 테두리) · 'empty'(점선)."""
    o = [rect(x0, y0, w, h, 14, fill=WHITE, stroke=NAVY, sw=3.5)]
    o += g(x0 + 45, y0 + head_y / 2 - 4, 0.85, person(0, 0, NORM))
    o.append(line(x0, y0 + head_y, x0 + w, y0 + head_y, stroke=NAVY, sw=2.5))
    for (ry, rh), kind in zip(rows, st_rows):
        if kind == "empty":
            o.append(rect(x0 + 22, ry, w - 44, rh, 10, fill=WHITE, stroke="none", sw=0))
            o += dash_rect(x0 + 22, ry, w - 44, rh, BLUE, 3, 9, 7)
        else:
            o.append(rect(x0 + 22, ry, w - 44, rh, 10, fill=PALE if kind == "diff" else LIGHT,
                          stroke=BLUE if kind == "diff" else NAVY, sw=3.5 if kind == "diff" else 2.5))
    return o


def three_records() -> str:
    """25장: 세 사람이 같은 센서를 따로 적은 기록 카드 셋. 서로 다른 줄은 파란 테두리, 빈 값은 점선."""
    o: list[str] = []
    rows = ((135, 70), (225, 70), (315, 70))
    kinds = (("diff", "norm", "norm"), ("diff", "diff", "empty"), ("diff", "norm", "norm"))
    for x0, k in zip((40, 430, 820), kinds):
        o += _record_card(x0, 40, 340, 375, rows, k)
    return svg(o)


def same_schema() -> str:
    """26장: 위 가운데 스키마 정의서 하나에서 세 기록 카드로 화살표, 세 카드의 줄은 모두 같은 모양(보통 줄)."""
    o: list[str] = [rect(420, 14, 360, 92, 12, fill=PALE, stroke=BLUE, sw=4)]
    for k, dy in enumerate((40, 60, 80)):
        o.append(line(450, 14 + dy - 6, 750, 14 + dy - 6, stroke=NAVY if k == 0 else GREY, sw=3 if k == 0 else 2.5))
    for x0 in (40, 430, 820):
        cx = x0 + 170
        o.append(arrow([(600, 110), (600, 125), (cx, 125), (cx, 145)] if cx != 600 else [(600, 110), (600, 145)], NAVY, sw=3.5, size=12))
        o += _record_card(x0, 152, 340, 290, ((228, 54), (296, 54), (364, 54)), ("norm", "norm", "norm"), head_y=64)
    return svg(o)


def identifier_vs_alias() -> str:
    """31장: 왼쪽 — 이름이 같은 쿨러 원 셋(아래에 식별자 라벨 자리). 오른쪽 — 다른 이름으로 적힌 기록 둘이 쿨러 원 하나로 모인다."""
    o: list[str] = []
    for ox in (0, 610):
        o.append(rect(ox + 15, 8, 560, 504, 14, fill=LIGHT if ox == 0 else PALE, stroke="none", sw=0))
    for x in (130, 295, 460):
        o += cooler_node(x, 230, 52, fill=WHITE)
    C = (1010, 240, 62)
    for y in (130, 350):
        o.append(arrow([(780, y), (C[0] - 70, C[1] + (y - C[1]) * 0.35)], BLUE, sw=4.5, size=14))
        o += g(700, y, 0.7, [rect(-50, -64, 100, 128, 8, fill=WHITE, stroke=NAVY, sw=3.5)]
               + [line(-32, dy, 32, dy, stroke=NAVY, sw=2.5) for dy in (-40, -18, 4, 26)], boost=1.0)
    o += cooler_node(*C, fill=SKY)
    return svg(o)


def check_with_instances() -> str:
    """36장: 왼쪽 정의 표(격자) → 가운데 인스턴스 사슬(설비 → 쿨러 → 센서 → 물리량) → 오른쪽 확인 표시.
    사슬 아래에서 정의 표로 돌아가는 파란 점선(빠진 곳을 찾아 고친다)."""
    o: list[str] = [rect(40, 110, 240, 200, 12, fill=WHITE, stroke=NAVY, sw=3.5), rect(40, 110, 240, 44, 12, fill=PALE, stroke="none", sw=0),
                    line(40, 154, 280, 154, stroke=NAVY, sw=2.5)]
    for y in (194, 234, 274):
        o.append(line(40, y, 280, y, stroke=GREY, sw=2))
    o.append(line(130, 154, 130, 310, stroke=GREY, sw=2))
    o.append(arrow([(295, 210), (370, 210)], BLUE, sw=5, size=15))
    N = [(440, 210, 44), (610, 210, 44), (780, 210, 44), (950, 210, 44)]
    for a, b in zip(N, N[1:]):
        o += edge(a, b, NAVY, sw=4, size=13)
    o += equip_node(*N[0]) + cooler_node(*N[1]) + sensor_node(*N[2]) + var_node(*N[3], fill=WHITE, stroke=NAVY)
    o.append(arrow([(1000, 210), (1060, 210)], NAVY, sw=4, size=13))
    o += [circle(1115, 210, 40, fill=PALE, stroke=BLUE, sw=4), path("M 1097,211 L 1110,225 L 1135,195", stroke=BLUE, sw=6)]
    o += dash_line(950, 324, 950, 440, BLUE, 4, 10, 8) + dash_line(950, 440, 160, 440, BLUE, 4, 10, 8) + dash_line(160, 440, 160, 335, BLUE, 4, 10, 8)
    o.append(arrow([(160, 345), (160, 322)], BLUE, sw=4, size=13))
    return svg(o)


# ───────────────────────── 단원 03: 그래프 DB와 Cypher ─────────────────────────

def pill(cx, cy, w, h=60, fill=PALE, stroke=NAVY, sw=3):
    return rect(cx - w / 2, cy - h / 2, w, h, h / 2, fill=fill, stroke=stroke, sw=sw)


def node_store() -> str:
    """40장: 노드 둘(쿨러 · 센서)과 그 사이 이름 붙은 관계 하나, 노드마다 아래로 달린 속성 꼬리표 둘."""
    o: list[str] = []
    A, B = (300, 200, 80), (900, 200, 80)
    o += edge(A, B, NAVY, sw=6, size=20)
    for (x, y, r), fn in ((A, cooler_node), (B, sensor_node)):
        o.append(line(x, y + r, x, 300, stroke=NAVY, sw=3))
        o.append(line(x, 360, x, 380, stroke=NAVY, sw=3))
        o.append(pill(x, 330, 300))
        o.append(pill(x, 410, 300))
        o += fn(x, y, r, fill=SKY if fn is cooler_node else WHITE)
    return svg(o)


def _table(x0, y0, w, h, rows=3, hot=None, head=50):
    """표 하나: 머리 띠 + 줄. hot: 강조할 칸 (줄 번호, 열 번호)의 집합 — 조인 열."""
    o = [rect(x0, y0, w, h, 10, fill=WHITE, stroke=NAVY, sw=3.5), rect(x0, y0, w, head, 10, fill=PALE, stroke="none", sw=0),
         line(x0, y0 + head, x0 + w, y0 + head, stroke=NAVY, sw=3)]
    rh = (h - head) / rows
    for i in range(1, rows):
        o.append(line(x0, y0 + head + i * rh, x0 + w, y0 + head + i * rh, stroke=GREY, sw=2))
    o.append(line(x0 + w / 2, y0 + head, x0 + w / 2, y0 + h, stroke=GREY, sw=2))
    for i in range(rows):
        for j in range(2):
            cx = x0 + w / 4 + j * w / 2
            cy = y0 + head + (i + 0.5) * rh
            key = hot is not None and (i, j) in hot
            o.append(rect(cx - w / 6, cy - 8, w / 3, 16, 8, fill=SKY if key else GREY, stroke="none", sw=0))
    return o


def join_tables() -> str:
    """42장: 위 줄에 질문 길의 표 넷(설비 → 구성 요소 → 센서 → 물리량)을 같은 값의 열로 이은 조인 화살표 셋.
    아래 가운데에 다대다일 때 끼는 잇는 표 하나(양옆 표는 점선 테두리)."""
    o: list[str] = []
    xs = (20, 320, 620, 920)
    hot = ({(1, 0)}, {(1, 0), (1, 1)}, {(1, 0), (1, 1)}, {(1, 1)})
    for x0, h in zip(xs, hot):
        o += _table(x0, 30, 220, 220, hot=h)
    for x0 in xs[:-1]:
        o.append(arrow([(x0 + 228, 150), (x0 + 292, 150)], BLUE, sw=5, size=14))
    o += dash_rect(250, 360, 180, 110, GREY, 3, 9, 7) + dash_rect(770, 360, 180, 110, GREY, 3, 9, 7)
    o += _table(510, 340, 180, 150, rows=2, hot={(0, 0), (0, 1)})
    o.append(arrow([(436, 415), (502, 415)], BLUE, sw=4, size=12))
    o.append(arrow([(698, 415), (764, 415)], BLUE, sw=4, size=12))
    return svg(o)


def spoken_branches() -> str:
    """47장: 왼쪽 사람과 말풍선 하나, 말풍선에서 세 갈래로 나뉜 길(저마다 원 셋), 세 길의 끝은 서로 다른 대상."""
    o: list[str] = []
    o += g(110, 250, 1.6, person(0, 0, NORM))
    o += [rect(190, 180, 280, 160, 22, fill=WHITE, stroke=NAVY, sw=3.5), poly([(190, 280), (160, 300), (190, 300)], fill=WHITE, stroke=NAVY, sw=3)]
    o.append(rect(186, 282, 8, 16, 0, fill=WHITE, stroke="none", sw=0))
    ys = (110, 260, 410)
    for k, y in enumerate(ys):
        o.append(path(f"M 475,260 C 520,260 520,{y} 565,{y}", stroke=GREY if k else BLUE, sw=4))
        N = [(610, y, 30), (730, y, 30), (850, y, 30)]
        o += edge(N[0], N[1], NAVY, sw=3.5, size=11) + edge(N[1], N[2], NAVY, sw=3.5, size=11)
        o += equip_node(*N[0], sw=3)
        o += (fan_node(*N[1], sw=3) if k == 1 else cooler_node(*N[1], sw=3))
        o += sensor_node(*N[2], sw=3, hot=(k == 0))
    return svg(o)


def browser_screen() -> str:
    """50장: 왼쪽 화면 창(머리 띠 · 쿼리 입력줄 · 그래프 보기 칸 · 표 보기 칸), 오른쪽 그래프 DB 저장소, 사이에 오가는 화살표 둘."""
    o: list[str] = [rect(30, 20, 850, 480, 14, fill=WHITE, stroke=NAVY, sw=3.5), rect(30, 20, 850, 40, 14, fill=LIGHT, stroke="none", sw=0),
                    line(30, 60, 880, 60, stroke=NAVY, sw=2.5)]
    for dx in (55, 75, 95):
        o.append(circle(dx, 40, 5, fill=GREY, stroke="none", sw=0))
    o.append(rect(60, 80, 790, 52, 10, fill=PALE, stroke=BLUE, sw=3))
    o.append(rect(60, 155, 420, 325, 10, fill=LIGHT, stroke="none", sw=0))
    o.append(rect(505, 155, 345, 325, 10, fill=LIGHT, stroke="none", sw=0))
    N = [(150, 330, 34), (270, 270, 34), (390, 330, 34), (270, 420, 30)]
    o += edge(N[0], N[1], NAVY, sw=3, size=10) + edge(N[1], N[2], NAVY, sw=3, size=10) + edge(N[1], N[3], NAVY, sw=3, size=10)
    o += equip_node(*N[0], sw=3) + cooler_node(*N[1], sw=3, fill=SKY) + sensor_node(*N[2], sw=3) + sensor_node(*N[3], sw=3)
    for i in range(4):
        y = 230 + i * 58
        o.append(line(525, y - 20, 830, y - 20, stroke=GREY, sw=2))
        o.append(rect(540, y, 120, 14, 7, fill=GREY, stroke="none", sw=0))
        o.append(rect(690, y, 110, 14, 7, fill=SKY if i == 0 else GREY, stroke="none", sw=0))
    o += g(1050, 280, 1.15, cylinder_db(0, 0, ON)[:4], boost=0.8)
    o.append(arrow([(895, 255), (985, 255)], NAVY, sw=4, size=13))
    o.append(arrow([(985, 305), (895, 305)], BLUE, sw=4, size=13))
    return svg(o)


def main():
    out = {"클래스_인스턴스.svg": class_instance(), "쿨러_두그림.svg": cooler_two_ways(), "칸_속성값.svg": slots_values(),
           "글자칸_관계.svg": text_vs_relation(), "한계_상태변수.svg": limit_state_variable(), "관계유형_한번정의.svg": relation_type_once(),
           "스키마_인스턴스데이터.svg": schema_and_data(), "세사람_기록.svg": three_records(), "스키마_같이적기.svg": same_schema(),
           "식별자_다른이름.svg": identifier_vs_alias(), "인스턴스로_확인.svg": check_with_instances(),
           "저장구조_노드관계.svg": node_store(), "조인_건너기.svg": join_tables(), "말질문_여러갈래.svg": spoken_branches(),
           "브라우저_쿼리화면.svg": browser_screen()}
    for name, text in out.items():
        assert "<text" not in text and "stroke-dasharray" not in text, name
        (HERE / name).write_text(text, encoding="utf-8", newline="")
        print("wrote", name)


if __name__ == "__main__":
    main()
