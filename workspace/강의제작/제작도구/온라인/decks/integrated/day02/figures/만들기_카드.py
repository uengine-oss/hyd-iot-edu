"""통합반 2회차 이론 덱의 카드 그림(SVG)을 만든다. 글자는 넣지 않는다(라벨은 덱 MD의 요소로 얹는다, 덱 D-8).

사용:
  python 만들기_카드.py            → 이 폴더에 「카드_*.svg」와 새 꼴 견본 「새꼴_*.svg」를 쓴다(옛 그림과 옛 생성기 만들기_삽화*.py는 건드리지 않는다)
  python 만들기_카드.py --라벨     → 그림마다 덱 MD에 붙일 라벨 요소 줄(`라벨 | 설명 | x,y,폭`)을 찍는다
  python 만들기_카드.py --덱맞춤 <덱.md>  → 그 덱에서 이 그림을 쓰는 장의 `- 요소:` 목록을 이 파일의 라벨 줄로 바꿔 쓴다
                                          (라벨 글은 이 파일이 정본이다. 글을 고칠 때는 여기서 고친 뒤 덱맞춤을 돌린다)

그림체는 1회차 온톨로지 단원(만들기_삽화.py의 49~63장 카드 꼴)과 같다: 선 끝은 둥글게, 덱 색만, 그라디언트 · 그림자 · <text> 없음.
카드 하나가 노드 하나이고, 큰 아이콘 원판 아래(가로 카드는 오른쪽)에 클래스(작은 파란 글)와 이름(굵은 글)을 한 덩어리로 얹는다.
클래스 카드는 원판을 비운 테두리 원과 클래스 이름 하나만 담아, 인스턴스 카드와 한눈에 갈린다.
그림은 모두 1200 × 510이고, 라벨 좌표는 x ÷ 12, y ÷ 5.1(%)로 덱 MD에 옮긴다. 이 파일이 라벨 자리를 함께 계산하므로,
그림을 고치면 `--라벨`로 찍은 줄을 덱 MD의 그 장 요소와 다시 맞춘다. 1회차 생성기는 다른 세션이 고치는 파일이라 import하지 않고 조각을 옮겨 왔다.
"""
from __future__ import annotations

import math
import re
import sys
from pathlib import Path

NAVY, SKY, BLUE, PALE, GREY, LIGHT, WHITE = "#13294B", "#5CB8F2", "#1A6FC4", "#E7F3FD", "#D3D9E1", "#F3F6F9", "#FFFFFF"
FW, FH = 1200, 510
SW = 3.5
HERE = Path(__file__).resolve().parent

# 라벨 글자의 줄 높이(그림 px). 덱 `라벨: 큰`은 제목 16pt · 설명 13pt, `보통`은 13.5pt · 11pt이고 줄 간격은 1.22다.
LH_T, LH_D = 27, 22


class St:
    def __init__(self, line, fill, accent, soft):
        self.line, self.fill, self.accent, self.soft = line, fill, accent, soft


ON = St(NAVY, WHITE, SKY, PALE)
NORM = St(NAVY, WHITE, PALE, LIGHT)
OFF = St(GREY, WHITE, LIGHT, WHITE)


# ───────────────────────── 기본 도형(1회차 생성기와 같은 그림체) ─────────────────────────

def el(tag, **kw):
    kw.setdefault("stroke-linecap", "round")
    kw.setdefault("stroke-linejoin", "round")
    a = " ".join(f'{k.replace("_", "-")}="{v}"' for k, v in kw.items() if v is not None)
    return f"<{tag} {a}/>"


def rect(x, y, w, h, r=0, fill="none", stroke=NAVY, sw=SW, **kw):
    return el("rect", x=x, y=y, width=w, height=h, rx=r, ry=r, fill=fill, stroke=stroke, stroke_width=sw, **kw)


def line(x1, y1, x2, y2, stroke=NAVY, sw=SW, **kw):
    return el("line", x1=x1, y1=y1, x2=x2, y2=y2, stroke=stroke, stroke_width=sw, fill="none", **kw)


def path(d, stroke=NAVY, sw=SW, fill="none", **kw):
    return el("path", d=d, stroke=stroke, stroke_width=sw, fill=fill, **kw)


def circle(cx, cy, r, fill="none", stroke=NAVY, sw=SW, **kw):
    return el("circle", cx=cx, cy=cy, r=r, fill=fill, stroke=stroke, stroke_width=sw, **kw)


def ellipse(cx, cy, rx, ry, fill="none", stroke=NAVY, sw=SW, **kw):
    return el("ellipse", cx=cx, cy=cy, rx=rx, ry=ry, fill=fill, stroke=stroke, stroke_width=sw, **kw)


def poly(pts, fill=NAVY, stroke="none", sw=0):
    return el("polygon", points=" ".join(f"{x:.1f},{y:.1f}" for x, y in pts), fill=fill, stroke=stroke, stroke_width=sw)


def head(x, y, ang, color, size=13):
    """(x, y)가 끝점인 화살촉. ang은 진행 방향(라디안)."""
    a1, a2 = ang + math.radians(152), ang - math.radians(152)
    return poly([(x, y), (x + size * math.cos(a1), y + size * math.sin(a1)), (x + size * math.cos(a2), y + size * math.sin(a2))], fill=color)


def arrow(pts, color=NAVY, sw=5, size=17):
    """꺾은선 화살표. 마지막 점에 화살촉."""
    (x1, y1), (x2, y2) = pts[-2], pts[-1]
    ang = math.atan2(y2 - y1, x2 - x1)
    end = (x2 - size * 0.7 * math.cos(ang), y2 - size * 0.7 * math.sin(ang))
    d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in [*pts[:-1], end])
    return [path(d, stroke=color, sw=sw), head(x2, y2, ang, color, size)]


def dash_line(x1, y1, x2, y2, color=NAVY, sw=SW, on=10, off=8):
    """점선을 짧은 선분으로 그린다. 그림을 PNG로 바꾸는 PyMuPDF가 stroke-dasharray를 그리지 않는다."""
    n = math.hypot(x2 - x1, y2 - y1)
    ux, uy = (x2 - x1) / n, (y2 - y1) / n
    o, t = [], 0.0
    while t < n - 1:
        e = min(t + on, n)
        o.append(line(round(x1 + ux * t, 1), round(y1 + uy * t, 1), round(x1 + ux * e, 1), round(y1 + uy * e, 1), stroke=color, sw=sw))
        t = e + off
    return o


def dash_arrow(pts, color=NAVY, sw=4.5, size=16, on=10, off=8):
    """꺾은 점선 화살표. 마지막 점에 화살촉."""
    o = []
    (x1, y1), (x2, y2) = pts[-2], pts[-1]
    ang = math.atan2(y2 - y1, x2 - x1)
    end = (x2 - size * 0.8 * math.cos(ang), y2 - size * 0.8 * math.sin(ang))
    seg = [*pts[:-1], end]
    for a, b in zip(seg, seg[1:]):
        o += dash_line(a[0], a[1], b[0], b[1], color, sw, on, off)
    return o + [head(x2, y2, ang, color, size)]


def dash_rect(x, y, w, h, color=NAVY, sw=SW, on=12, off=9):
    return (dash_line(x, y, x + w, y, color, sw, on, off) + dash_line(x + w, y, x + w, y + h, color, sw, on, off)
            + dash_line(x + w, y + h, x, y + h, color, sw, on, off) + dash_line(x, y + h, x, y, color, sw, on, off))


def g(cx, cy, k, parts, boost=None):
    """원점 기준으로 그린 조각을 (cx, cy)에 k배로 놓는다. 선 굵기는 너무 가늘어지지 않게 되돌린다."""
    b = boost if boost is not None else min(1 / k, 1.9) * 0.85
    body = "\n".join(parts)
    body = re.sub(r'stroke-width="([\d.]+)"', lambda m: f'stroke-width="{float(m.group(1)) * b:.2f}"', body)
    return [f'<g transform="translate({cx} {cy}) scale({k})">', body, "</g>"]


def svg(body: list[str], w: int = FW, h: int = FH) -> str:
    assert not any("<text" in b for b in body)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">\n'
            + "\n".join(body) + "\n</svg>\n")


# ───────────────────────── 아이콘(원점 기준, 높이 약 100) ─────────────────────────

def gauge(cx, cy, st: St, r=16, hot=False, ang=-50):
    """센서: 원 + 눈금 + 바늘."""
    o = [circle(cx, cy, r, fill=st.accent if hot else st.fill, stroke=st.line)]
    for a in (-150, -90, -30):
        ra = math.radians(a)
        o.append(line(cx + (r - 6) * math.cos(ra), cy + (r - 6) * math.sin(ra), cx + (r - 3) * math.cos(ra), cy + (r - 3) * math.sin(ra), stroke=st.line, sw=2))
    ra = math.radians(ang)
    o.append(line(cx, cy + 2, cx + (r - 6) * math.cos(ra), cy + 2 + (r - 6) * math.sin(ra), stroke=st.line, sw=3))
    return o


def fan(cx, cy, r, st: St, blades=4, rot=20, hot=False):
    o = [circle(cx, cy, r, fill=st.fill, stroke=st.line)]
    for i in range(blades):
        a = rot + i * 360 / blades
        o.append(ellipse(cx, cy - r * 0.52, r * 0.21, r * 0.4, fill=st.accent if hot else st.soft, stroke=st.line, sw=3, transform=f"rotate({a} {cx} {cy})"))
    o.append(circle(cx, cy, r * 0.17, fill=st.line, stroke=st.line, sw=2))
    return o


def radiator(x, y, w, h, st: St, fins=12, r=8):
    o = [rect(x, y, w, h, r, fill=st.fill, stroke=st.line)]
    step = (w - 20) / (fins - 1)
    for i in range(fins):
        fx = x + 10 + i * step
        o.append(line(fx, y + 10, fx, y + h - 10, stroke=GREY if st is not OFF else LIGHT, sw=2))
    return o


def equip_mini(cx, cy, st: St):
    """설비(유압 파워팩): 탱크 위에 모터와 펌프."""
    return [rect(cx - 46, cy + 4, 92, 42, 6, fill=st.soft, stroke=st.line),
            path(f"M {cx - 40},{cy + 20} q 10,-6 20,0 t 20,0 t 20,0 t 20,0", stroke=st.line, sw=2),
            rect(cx - 40, cy - 38, 46, 32, 9, fill=st.fill, stroke=st.line),
            line(cx - 28, cy - 31, cx - 28, cy - 13, stroke=st.line, sw=2), line(cx - 17, cy - 31, cx - 17, cy - 13, stroke=st.line, sw=2),
            line(cx - 6, cy - 31, cx - 6, cy - 13, stroke=st.line, sw=2), line(cx + 6, cy - 22, cx + 14, cy - 22, stroke=st.line, sw=5),
            circle(cx + 28, cy - 22, 15, fill=st.accent, stroke=st.line), line(cx + 28, cy - 7, cx + 28, cy + 30, stroke=st.line, sw=4),
            line(cx - 30, cy - 6, cx - 30, cy + 4, stroke=st.line), line(cx - 4, cy - 6, cx - 4, cy + 4, stroke=st.line)]


def cooler_icon(st: St):
    """구성 요소 · 오일 쿨러: 핀이 든 방열 몸체와 양옆의 기름 통, 들고 나는 관."""
    o = radiator(-36, -34, 72, 68, st, fins=7, r=6)
    for sx in (-1, 1):
        o.append(rect(sx * 44 - 8, -40, 16, 80, 6, fill=st.accent, stroke=st.line))
    o += [line(-52, -24, -64, -24, stroke=st.line, sw=6), line(52, 24, 64, 24, stroke=st.line, sw=6)]
    return o


def core_icon(st: St):
    """부품 · 쿨러 코어: 관과 핀만 남은 덩어리와, 품번을 다는 꼬리표."""
    o = [rect(-44, -22, 74, 60, 6, fill=st.fill, stroke=st.line)]
    for i in range(9):
        x = -36 + i * 7.3
        o.append(line(x, -16, x, 32, stroke=GREY, sw=2))
    for y in (-4, 18):
        o.append(line(-44, y, 30, y, stroke=st.line, sw=4))
    o.append(path("M 20,-50 L 46,-50 L 46,-28 L 33,-17 L 20,-28 Z", fill=st.accent, stroke=st.line, sw=3))
    o.append(circle(33, -40, 4, fill=WHITE, stroke=st.line, sw=2.5))
    return o


def pump_icon(st: St):
    """구성 요소 · 주 펌프: 달팽이 몸체, 위로 나가는 토출구, 받침."""
    o = [rect(8, -46, 26, 30, 4, fill=st.accent, stroke=st.line),
         circle(0, 4, 34, fill=st.fill, stroke=st.line),
         rect(-44, 38, 88, 10, 4, fill=st.soft, stroke=st.line)]
    for a in (0, 90, 180, 270):
        ra = math.radians(a)
        o.append(path(f"M {10 * math.cos(ra):.1f},{4 + 10 * math.sin(ra):.1f} Q {22 * math.cos(ra + 0.5):.1f},{4 + 22 * math.sin(ra + 0.5):.1f} "
                      f"{24 * math.cos(ra + 1.1):.1f},{4 + 24 * math.sin(ra + 1.1):.1f}", stroke=st.line, sw=3))
    o.append(circle(0, 4, 7, fill=st.line, stroke=st.line, sw=2))
    return o


def bearing_icon(st: St):
    """부품 · 베어링: 바깥 고리와 안 고리 사이의 구슬."""
    o = [circle(0, 0, 42, fill=st.fill, stroke=st.line), circle(0, 0, 17, fill=st.soft, stroke=st.line)]
    for i in range(8):
        a = math.radians(i * 45)
        o.append(circle(29.5 * math.cos(a), 29.5 * math.sin(a), 7, fill=st.accent, stroke=st.line, sw=2.5))
    o.append(circle(0, 0, 7, fill=WHITE, stroke=st.line, sw=2.5))
    return o


def gasket_icon(st: St):
    """부품 · 가스켓: 가운데가 빈 판과 볼트 구멍."""
    o = [rect(-46, -34, 92, 68, 14, fill=st.accent, stroke=st.line), rect(-26, -16, 52, 32, 8, fill=WHITE, stroke=st.line)]
    for x, y in ((-36, -24), (36, -24), (-36, 24), (36, 24)):
        o.append(circle(x, y, 4.5, fill=WHITE, stroke=st.line, sw=2.5))
    return o


def loc_icon(st: St):
    """설치 위치: 바닥 위의 자리 표시 핀."""
    return [ellipse(0, 40, 30, 8, fill=st.soft, stroke=st.line, sw=3),
            path("M 0,38 C -6,22 -28,4 -28,-14 A 28 28 0 1 1 28,-14 C 28,4 6,22 0,38 Z", fill=st.accent, stroke=st.line),
            circle(0, -14, 10, fill=WHITE, stroke=st.line, sw=3)]


def supplier_icon(st: St):
    """공급사: 지붕 아래 창고와 셔터 문."""
    o = [rect(-38, -8, 76, 52, 3, fill=st.fill, stroke=st.line),
         path("M -48,-6 L 0,-40 L 48,-6", stroke=st.line, sw=5),
         rect(-16, 12, 32, 32, 2, fill=st.soft, stroke=st.line, sw=3)]
    o += [line(-16, 12 + d, 16, 12 + d, stroke=st.line, sw=2) for d in (8, 16, 24)]
    o.append(rect(-32, 2, 10, 8, 1, fill=st.accent, stroke=st.line, sw=2))
    return o


def note_doc(st: St):
    """기록 한 장(100 × 128)."""
    o = [rect(-50, -64, 100, 128, 8, fill=st.fill, stroke=st.line)]
    for dy in (-40, -18, 4, 26):
        o.append(line(-32, dy, 32, dy, stroke=st.line, sw=2.5))
    return o


def motor_icon(st: St):
    """구성 요소 · 구동 모터: 냉각 핀이 든 몸체, 끝 덮개, 축, 받침."""
    o = [rect(-44, -28, 64, 56, 8, fill=st.fill, stroke=st.line)]
    o += [line(x, -20, x, 20, stroke=GREY, sw=2.5) for x in (-34, -24, -14, -4, 6)]
    o += [rect(20, -20, 12, 40, 4, fill=st.accent, stroke=st.line), line(32, 0, 52, 0, stroke=st.line, sw=7),
          rect(-38, 28, 52, 9, 3, fill=st.soft, stroke=st.line, sw=3)]
    return o


def seal_icon(st: St):
    """부품 · 축 씰: 고무 고리 두 겹."""
    return [circle(0, 0, 40, fill=st.accent, stroke=st.line), circle(0, 0, 30, fill="none", stroke=st.line, sw=2.5),
            circle(0, 0, 20, fill=WHITE, stroke=st.line)]


def sheet_icon(st: St):
    """정의 표: 머리 띠와 칸 줄이 있는 종이."""
    o = [rect(-42, -50, 84, 100, 8, fill=st.fill, stroke=st.line), rect(-42, -50, 84, 22, 8, fill=st.accent, stroke=st.line)]
    o += [line(-42, y, 42, y, stroke=st.line, sw=2) for y in (-6, 16, 34)]
    o.append(line(-12, -28, -12, 50, stroke=st.line, sw=2))
    return o


def graph_icon(st: St):
    """지식 그래프: 원 다섯과 잇는 선."""
    pts = [(-30, -22), (32, -30), (4, 6), (-34, 30), (36, 28)]
    o = [line(pts[a][0], pts[a][1], pts[b][0], pts[b][1], stroke=st.line) for a, b in ((0, 2), (1, 2), (2, 3), (2, 4), (0, 1))]
    for i, (dx, dy) in enumerate(pts):
        o.append(circle(dx, dy, 13 if i == 2 else 10, fill=st.accent if i == 2 else st.fill, stroke=st.line))
    return o


def tsdb_icon(st: St):
    """시계열 저장소: 원통과 시계."""
    return [path("M -42,-34 L -42,34 A 42 14 0 0 0 42,34 L 42,-34", fill=st.fill, stroke=st.line),
            ellipse(0, -34, 42, 14, fill=st.accent, stroke=st.line),
            path("M -42,-10 A 42 14 0 0 0 42,-10", stroke=st.line), path("M -42,12 A 42 14 0 0 0 42,12", stroke=st.line),
            circle(36, 34, 17, fill=st.fill, stroke=st.line), path("M 36,24 L 36,34 L 44,38", stroke=st.line, sw=3)]


def question_icon(st: St):
    """역량 질문: 말풍선 안의 물음표."""
    return [path("M -46,-36 Q -46,-46 -36,-46 L 36,-46 Q 46,-46 46,-36 L 46,20 Q 46,30 36,30 L -6,30 L -22,46 L -20,30 L -36,30 "
                 "Q -46,30 -46,20 Z", fill=st.fill, stroke=st.line),
            path("M -12,-20 Q -12,-34 0,-34 Q 13,-34 13,-22 Q 13,-12 0,-8 L 0,2", stroke=BLUE, sw=6),
            circle(0, 15, 4.5, fill=BLUE, stroke=BLUE, sw=1)]


def card_icon(kind, cx, cy, k=1.0, grey=False):
    """카드 안 큰 아이콘. (cx, cy)는 아이콘 가운데, k는 배율(1.0 = 높이 약 100)."""
    st = OFF if grey else ON
    if kind == "none":
        return []
    if kind == "equip":
        return g(cx, cy - 2 * k, 0.8 * k, equip_mini(0, 0, st))
    if kind == "cooler":
        return g(cx, cy, 0.8 * k, cooler_icon(st))
    if kind == "core":
        return g(cx, cy + 4 * k, 0.82 * k, core_icon(st))
    if kind == "sensor":
        return g(cx, cy, k, gauge(0, 0, st, r=34, hot=not grey, ang=-40), boost=1.0)
    if kind == "fan":
        return g(cx, cy, k, fan(0, 0, 36, st, rot=20), boost=1.0)
    if kind == "pump":
        return g(cx, cy, 0.86 * k, pump_icon(st))
    if kind == "bearing":
        return g(cx, cy, 0.86 * k, bearing_icon(st))
    if kind == "gasket":
        return g(cx, cy, 0.86 * k, gasket_icon(st))
    if kind == "motor":
        return g(cx, cy, 0.86 * k, motor_icon(st))
    if kind == "seal":
        return g(cx, cy, 0.86 * k, seal_icon(st))
    if kind == "sheet":
        return g(cx, cy, 0.8 * k, sheet_icon(st))
    if kind == "graph":
        return g(cx, cy, 0.86 * k, graph_icon(st))
    if kind == "tsdb":
        return g(cx, cy, 0.8 * k, tsdb_icon(st))
    if kind == "question":
        return g(cx, cy, 0.86 * k, question_icon(st))
    if kind == "loc":
        return g(cx, cy, 0.9 * k, loc_icon(st))
    if kind == "supplier":
        return g(cx, cy, 0.9 * k, supplier_icon(st))
    if kind == "doc":
        return g(cx, cy, 0.56 * k, note_doc(NORM), boost=1.6)
    raise ValueError(kind)


# ───────────────────────── 카드와 라벨 ─────────────────────────

class Fig:
    """그림 한 장: SVG 조각과, 그 위에 덱 MD로 얹을 라벨 자리."""

    def __init__(self, name, dy=0):
        """dy: 그림 전체를 아래로 옮겨 세로 가운데에 둘 때의 거리(라벨 좌표도 같이 옮긴다)."""
        self.name, self.o, self.labels, self.dy = name, [], [], dy

    def add(self, parts):
        self.o += parts

    def lab(self, title, desc, x, y, w, strong=False):
        """라벨 하나. title이 비면 설명 줄만(작은 글씨) 쓴다. strong이면 제목을 강조색으로."""
        t = f"**{title}**" if (strong and title) else title
        pos = f"{x / 12:.2f},{(y + self.dy) / 5.1:.2f},{w / 12:.2f}"
        self.labels.append(" | ".join([t, desc, pos]).replace(" |  | ", " | | ").strip())

    def svg(self):
        if self.dy:
            return svg([f'<g transform="translate(0 {self.dy})">', *self.o, "</g>"])
        return svg(self.o)


def box(x, y, w, h, hot=False, grey=False, r=22):
    if grey:
        return [rect(x, y, w, h, r, fill=LIGHT, stroke=GREY, sw=3)]
    return [rect(x, y, w, h, r, fill=PALE if hot else WHITE, stroke=BLUE if hot else NAVY, sw=5 if hot else 3)]


def disc(cx, cy, r, kind, hot=False, ring=False, grey=False):
    if ring:
        return [circle(cx, cy, r, fill=WHITE, stroke=NAVY, sw=3)]
    o = [circle(cx, cy, r, fill=WHITE if hot else (LIGHT if grey else PALE), stroke="none", sw=0)]
    return o + card_icon(kind, cx, cy, r / 62, grey)


def vcard(f: Fig, cx, top, w, r, kind, cls, name, *, hot=False, grey=False, dashed=False, desc="", band=None):
    """세로 카드: 위에 큰 아이콘 원판, 그 아래 클래스(작은 파란 글)와 이름(굵은 글) 한 덩어리.
    cls가 비면 이름만 얹는다(두 띠 그림의 아래 띠처럼 위에 클래스가 따로 있을 때). desc는 이름 아래 작은 줄.
    band = (줄 수, 설명)이면 카드 아래쪽에 띠를 두고 그 설명을 얹는다. 돌려주는 값: (카드 아래 y, 원판 가운데 y)."""
    dcy = top + 18 + r
    y = dcy + r + 14
    if cls:
        f.lab("", f"**{cls}**", cx, y, w - 24)
        y += 28
    nd = len(desc.split(" / ")) if desc else 0
    f.lab(name, desc, cx, y, w - 20)
    bot = y + 5 + LH_T + nd * LH_D + 14
    if band:
        nb, text = band
        B = bot
        bot = B + 12 + 5 + nb * LH_D + 12
        f.lab("", text, cx, B + 12, w - 24)
    x0 = cx - w / 2
    if dashed:
        f.add([rect(x0, top, w, bot - top, 22, fill=WHITE, stroke="none", sw=0)] + dash_rect(x0, top, w, bot - top, BLUE, 4))
    elif band:
        f.add(banded(x0, top, w, bot, B, PALE if hot else LIGHT, BLUE if hot else NAVY, 5 if hot else 3))
    else:
        f.add(box(x0, top, w, bot - top, hot, grey))
    f.add(disc(cx, dcy, r, kind, hot and not band and not dashed, grey=grey))
    return bot, dcy


def hcard(f: Fig, cx, cy, w, h, kind, cls="", name="", *, hot=False, grey=False, ring=False, dashed=False, desc="", strong=False, small=False):
    """가로 카드: 왼쪽 큰 아이콘 원판, 오른쪽에 클래스와 이름 한 덩어리. ring이면 원판을 비운 클래스 카드(이름만, strong이면 파랗게).
    small이면 클래스와 이름을 작은 글씨 두 줄 라벨 하나로 얹는다(카드가 많은 그림)."""
    x0, x1 = cx - w / 2, cx + w / 2
    r = h / 2 - 14
    dx = x0 + 14 + r
    if dashed:
        f.add([rect(x0, cy - h / 2, w, h, 20, fill=WHITE, stroke="none", sw=0)] + dash_rect(x0, cy - h / 2, w, h, BLUE, 4))
    else:
        f.add(box(x0, cy - h / 2, w, h, hot, grey, r=20))
    f.add(disc(dx, cy, r, kind, hot, ring, grey))
    tx0 = dx + r + 8
    tx, tw = (tx0 + x1) / 2, x1 - tx0 - 6
    nd = len(desc.split(" / ")) if desc else 0
    if small:
        f.lab("", f"**{cls}** / {name}", tx, cy - 27, tw)
    elif cls:
        hgt = 28 + LH_T + nd * LH_D
        y = cy - hgt / 2 - 3
        f.lab("", f"**{cls}**", tx, y, tw)
        f.lab(name, desc, tx, y + 28, tw)
    else:
        hgt = LH_T + nd * LH_D
        f.lab(name, desc, tx, cy - hgt / 2 - 6, tw, strong=strong)
    return x0, x1


def banded(x, top, w, bot, B, band, edge, sw, r=22, fill=WHITE):
    """아래 띠(B~bot)가 있는 상자."""
    return [rect(x, top, w, bot - top, r, fill=fill, stroke="none", sw=0),
            path(f"M {x},{B} L {x + w},{B} L {x + w},{bot - r} A {r} {r} 0 0 1 {x + w - r},{bot} L {x + r},{bot} A {r} {r} 0 0 1 {x},{bot - r} Z",
                 fill=band, stroke="none", sw=0),
            rect(x, top, w, bot - top, r, fill="none", stroke=edge, sw=sw)]


def cells(f: Fig, x, y, w, rows, item_w=118, rh=50, gap=10, hot=(), empty=False):
    """속성 칸: 줄마다 왼쪽 항목 칸(회색, hot이면 하늘색)과 오른쪽 값 칸(흰색, empty면 점선 빈 칸). 돌려주는 값: 끝 y."""
    for i, (item, val) in enumerate(rows):
        ry = y + i * (rh + gap)
        h = i in hot
        f.add([rect(x, ry, item_w, rh, 10, fill=SKY if h else GREY, stroke="none", sw=0)])
        if empty:
            f.add(dash_rect(x + item_w + 10, ry, w - item_w - 10, rh, GREY, 3, 8, 6))
        else:
            f.add([rect(x + item_w + 10, ry, w - item_w - 10, rh, 10, fill=WHITE, stroke=BLUE if h else NAVY, sw=3 if h else 2)])
        f.lab(item, "", x + item_w / 2, ry + rh / 2 - 19, item_w - 6)
        if val:
            f.lab(val, "", x + item_w + 10 + (w - item_w - 10) / 2, ry + rh / 2 - 19, w - item_w - 16)
    return y + len(rows) * (rh + gap) - gap


def harrow(f, x1, x2, y, color=NAVY, label=None, small=True, above=True, dashed=False):
    """가로 화살표와 그 위(또는 아래)의 관계 이름."""
    f.add((dash_arrow if dashed else arrow)([(x1, y), (x2, y)], color))
    if label:
        mid, w = (x1 + x2) / 2, max(abs(x2 - x1) - 12, 130)
        if small:
            f.lab("", label, mid, y - 38 if above else y + 9, w)
        else:
            f.lab(label, "", mid, y - 46 if above else y + 9, w)


def band_rect(y0, y1, color, x0=3, x1=1197, r=24):
    return [rect(x0, y0, x1 - x0, y1 - y0, r, fill=color, stroke="none", sw=0)]


def tri_head(x, y, ang, color=NAVY, size=24):
    """속이 빈 삼각 화살촉(상속: 하위 클래스에서 상위 클래스로). (x, y)가 끝점."""
    a1, a2 = ang + math.radians(150), ang - math.radians(150)
    return [poly([(x, y), (x + size * math.cos(a1), y + size * math.sin(a1)), (x + size * math.cos(a2), y + size * math.sin(a2))],
                 fill=WHITE, stroke=color, sw=4)]


# ───────────────────────── 1단원(4~20장) ─────────────────────────

def f05():
    """5장: 위 띠는 클래스(관계 그림에서 원마다 붙인 종류), 아래 띠는 인스턴스(원 하나하나). 같은 가로 자리를 점선으로 잇는다.
    맨 아래 띠는 어디까지를 인스턴스 하나로 셀지 정하는 기준(14장이 받는다)."""
    f = Fig("카드_관계그림_두띠.svg")
    xs, ky = (390, 700, 1010), 72
    f.add(band_rect(4, 146, PALE) + band_rect(160, 408, LIGHT) + band_rect(422, 506, WHITE))
    f.add([rect(3, 422, 1194, 84, 24, fill=WHITE, stroke=BLUE, sw=3)])
    f.lab("클래스", "Class / 같은 성질의 대상을 / 묶은 갈래", 120, ky - 54, 210)
    f.lab("인스턴스", "Instance / 클래스에 속하는 / 실제 개별 대상", 120, 284 - 54, 210)
    top, r = 186, 50
    for x in xs:
        f.add(dash_line(x, ky + 46, x, top - 8, GREY, 3.5, 8, 6))
    for x, kind, cls in zip(xs, ("none",) * 3, ("설비", "부품", "센서")):
        hcard(f, x, ky, 200, 80, kind, name=cls, ring=True, strong=True)
    dcy = top + 18 + r
    for (a, b), rel in zip(((0, 1), (1, 2)), ("가진다", "감시된다")):
        harrow(f, xs[a] + 110, xs[b] - 110, ky, label=rel)
        harrow(f, xs[a] + 105, xs[b] - 105, dcy, label=rel)
    for x, kind, nm in zip(xs, ("equip", "cooler", "sensor"), ("1호기", "오일 쿨러", "유온 센서")):
        vcard(f, x, top, 190, r, kind, "", nm)
    f.lab("무엇을 인스턴스 하나로 셀지는 그래프가 답할 질문이 정한다", "", 600, 464 - 19, 1100)
    return f


def f06():
    """6장: 설비 한 대(1호기)에 딸린 대상을 네 클래스의 인스턴스로. 구성 요소와 부품 카드만 파랗게 하고, 아래 띠에 그 뜻을 둔다.
    쓴다 화살표는 유온 센서 카드 위로 돌아 쿨러 코어에 닿는다. 맨 아래 띠가 앞에서 「부품」이라 부른 것과의 이음새이고,
    1회차에서 배운 원리(다루려는 일이 넓어지면 종류를 더한다)로 받는다."""
    f = Fig("카드_설비한대_네클래스.svg")
    top, r = 96, 54
    spec = [(90, 160, "equip", "설비", "1호기", None), (417, 240, "cooler", "구성 요소", "오일 쿨러", (2, "설비를 이루는 / 기계 하나하나")),
            (743, 160, "sensor", "센서", "유온 센서", None), (1070, 240, "core", "부품", "쿨러 코어", (2, "구성 요소 안에서 / 닳으면 갈아 끼우는 것"))]
    bots = []
    for cx, w, kind, cls, nm, band in spec:
        b, dcy = vcard(f, cx, top, w, r, kind, cls, nm, hot=band is not None, band=band)
        bots.append(b)
    edge = lambda i, s: spec[i][0] + s * (spec[i][1] / 2 + 10)
    harrow(f, edge(0, 1), edge(1, -1), dcy, label="가진다", small=False)
    harrow(f, edge(1, 1), edge(2, -1), dcy, label="감시된다", small=False)
    ry = 46
    x1, x3 = spec[1][0], spec[3][0]
    f.add(arrow([(x1, top - 8), (x1, ry), (x3, ry), (x3, top - 8)], NAVY))
    f.lab("쓴다", "", (spec[2][0] + x3) / 2 + 20, ry - 46, 90)
    yb = max(bots) + 18
    f.add([rect(3, yb, 1194, FH - 3 - yb, 22, fill=LIGHT, stroke="none", sw=0)])
    f.lab("다루려는 일이 넓어지면 종류를 더한다",
          "앞에서 부품이라 부른 오일 쿨러 · 쿨러 팬 · 주 펌프는 **구성 요소**(관계 그림에서 붙인 Component), / "
          "그 안에서 닳으면 갈아 끼우는 쿨러 코어 · 팬 베어링은 **부품**으로 나눠, 갈아 끼울 것과 그 품번을 따로 묻는다",
          600, (yb + FH - 3) / 2 - 41, 1150)
    return f


COLS = (200, 600, 1000)


def f07():
    """7장: 같은 기종 설비 세 대가 저마다 「오일 쿨러」를 가진다. 이름만 적힌 정비 기록은 셋 가운데 어느 것인지 가리키지 못한다(회색 점선 갈래)."""
    f = Fig("카드_같은이름_세쿨러.svg")
    for x, nm in zip(COLS, ("1호기", "2호기", "3호기")):
        hcard(f, x, 52, 240, 92, "equip", "설비", nm)
        f.add(arrow([(x, 102), (x, 146)], NAVY))
        f.lab("가진다", "", x + 66, 103, 120)
        vcard(f, x, 152, 240, 46, "cooler", "구성 요소", "오일 쿨러")
    bus, rt = 390, 412
    f.add(dash_line(600, rt - 6, 600, bus, GREY, 3.5, 8, 6) + dash_line(200, bus, 1000, bus, GREY, 3.5, 8, 6))
    for x in COLS:
        f.add(dash_arrow([(x, bus), (x, 352)], GREY, 3.5, 13, 8, 6))
    hcard(f, 600, 459, 400, 90, "doc", name="정비 기록", desc="오일 쿨러 세척")
    f.lab("어느 오일 쿨러의 기록인가", "", 1000, 440, 300)
    return f


def f08():
    """8장: 7장과 같은 자리에 식별자를 더한다. 설비와 오일 쿨러마다 식별자가 달라, 식별자를 적은 기록은 하나(2호기의 오일 쿨러)만 가리킨다.
    같은 대상을 달리 부르는 다른 이름은 이름 쪽에 적는다."""
    f = Fig("카드_식별자_세쿨러.svg")
    for i, (x, nm) in enumerate(zip(COLS, ("1호기", "2호기", "3호기"))):
        hcard(f, x, 56, 250, 104, "equip", "설비", nm, desc=f"식별자 EQ-0{i + 1}")
        f.add(arrow([(x, 112), (x, 148)], NAVY))
        f.lab("가진다", "", x + 66, 112, 120)
        vcard(f, x, 152, 270, 42, "cooler", "구성 요소", "오일 쿨러", hot=i == 1,
              desc=f"식별자 **EQ-0{i + 1}-COOLER** / 다른 이름 쿨러 · 열교환기")
    f.add(arrow([(600, 420), (600, 396)], BLUE, sw=6, size=17))
    hcard(f, 600, 464, 400, 84, "doc", name="정비 기록", desc="**EQ-02-COOLER** 세척", hot=True)
    f.lab("다른 이름", "같은 대상을 달리 부르는 이름 / 이름 쪽에 두고 식별자로 쓰지 않는다", 1000, 428, 330)
    return f


def f09():
    """9장: 왼쪽 센서 클래스는 항목(속성)만 정하고 값 칸은 비어 있다. 오른쪽 인스턴스(유온 센서)는 같은 항목에 값을 채운다.
    값은 노드 안 칸에 적힌다(노드가 되지 않는다)."""
    f = Fig("카드_속성값_센서.svg")
    L, R, w, top = 40, 700, 460, 14
    rows_top, rh, gap = 236, 56, 12
    bot = rows_top + 3 * (rh + gap) - gap + 22
    f.add([rect(L, top, w, bot - top, 22, fill=WHITE, stroke=NAVY, sw=3), rect(R, top, w, bot - top, 22, fill=WHITE, stroke=BLUE, sw=5)])
    f.add([circle(L + w / 2, top + 18 + 52, 52, fill=WHITE, stroke=NAVY, sw=3)])
    f.lab("센서", "", L + w / 2, top + 18 + 104 + 18, w - 40, strong=True)
    f.add(disc(R + w / 2, top + 18 + 52, 52, "sensor"))
    f.lab("", "**센서**", R + w / 2, top + 18 + 104 + 12, w - 40)
    f.lab("유온 센서", "", R + w / 2, top + 18 + 104 + 40, w - 40)
    rows = [("식별자", "EQ-02-TEMP"), ("단위", "℃"), ("측정 범위", "0~120 ℃")]
    cells(f, L + 22, rows_top, w - 44, [(a, "") for a, _ in rows], item_w=140, rh=rh, gap=gap, empty=True)
    cells(f, R + 22, rows_top, w - 44, rows, item_w=140, rh=rh, gap=gap, hot=(0, 1, 2))
    mid = (rows_top + bot - 22) / 2
    f.add(arrow([(L + w + 18, mid), (R - 18, mid)], BLUE, sw=6, size=19))
    f.lab("인스턴스마다", "속성값을 채운다", (L + w + R) / 2, mid - 76, 200)
    f.lab("", "클래스는 항목만 정한다", L + w / 2, bot + 12, w)
    f.lab("", "값은 노드 안 칸에 적힌다", R + w / 2, bot + 12, w)
    return f


def side_card(f: Fig, x0, top, w, kind, cls, name, rows, *, grey=False, hot_rows=(), item_w=136):
    """10 · 11장의 인스턴스 카드: 위에 아이콘 원판과 클래스 · 이름, 아래에 속성 칸. 돌려주는 값: (카드 아래 y, 칸 줄의 가운데 y 목록)."""
    r, rh, gap = 44, 50, 10
    dcy = top + 18 + r
    rows_top = dcy + r + 82
    bot = rows_top + len(rows) * (rh + gap) - gap + 16
    f.add([rect(x0, top, w, bot - top, 22, fill=LIGHT if grey else WHITE, stroke=GREY if grey else NAVY, sw=3)])
    f.add(disc(x0 + w / 2, dcy, r, kind, grey=grey))
    f.lab("", f"**{cls}**", x0 + w / 2, dcy + r + 12, w - 40)
    f.lab(name, "", x0 + w / 2, dcy + r + 40, w - 40)
    cells(f, x0 + 20, rows_top, w - 40, rows, item_w=item_w, rh=rh, gap=gap, hot=hot_rows)
    return bot, [rows_top + i * (rh + gap) + rh / 2 for i in range(len(rows))]


QUESTION = "이 오일 쿨러를 재는 센서의 단위"


def f10():
    """10장: 오일 쿨러의 칸에 센서 이름을 글자로 적었다. 물음(이 쿨러를 재는 센서의 단위)은 쿨러까지 와서 그 글자에서 멈추고,
    실제 센서 노드(회색)의 단위 칸으로 건너갈 길이 없다."""
    f = Fig("카드_글자센서_막힘.svg")
    f.add([rect(3, 4, 560, 64, 18, fill=WHITE, stroke=NAVY, sw=3)])
    f.lab("물음", QUESTION, 283, 6, 520)
    cx0, cw, top = 40, 480, 90
    bot, ys = side_card(f, cx0, top, cw, "cooler", "구성 요소", "오일 쿨러",
                        [("식별자", "EQ-02-COOLER"), ("센서", "유온 센서")], hot_rows=(1,))
    f.add(arrow([(150, 72), (150, top - 6)], BLUE, sw=6, size=17))
    sx0, sw_ = 790, 400
    side_card(f, sx0, top, sw_, "sensor", "센서", "유온 센서", [("식별자", "EQ-02-TEMP"), ("단위", "℃")], grey=True)
    y = ys[1]
    f.add(dash_line(cx0 + cw + 10, y, 652, y, GREY, 4, 9, 7) + dash_line(728, y, sx0 - 12, y, GREY, 4, 9, 7))
    f.add([circle(690, y, 30, fill=WHITE, stroke=NAVY, sw=4), line(677, y - 13, 703, y + 13, stroke=NAVY, sw=6), line(703, y - 13, 677, y + 13, stroke=NAVY, sw=6)])
    f.lab("건너갈 길이 없다", "칸에 적힌 것은 / 글자일 뿐이다", 690, y - 30 - 12 - 76, 230)
    sbot = top + 18 + 44 + 44 + 82 + 2 * 60 - 10 + 16
    ab = sbot + 20
    f.add([rect(840, ab + 2, 300, FH - 6 - ab, 18, fill=LIGHT, stroke="none", sw=0)] + dash_rect(840, ab + 2, 300, FH - 6 - ab, GREY, 4))
    f.lab("찾은 답", "찾지 못한다", 990, ab + 2 + (FH - 6 - ab) / 2 - 31, 280)
    return f


def f11():
    """11장: 같은 오일 쿨러에서 센서 칸을 지우고 감시된다 화살표로 유온 센서 노드에 잇는다. 물음이 화살표를 건너 단위 칸(℃)에 닿는다.
    왼쪽 칸은 데이터 속성, 화살표는 객체 간 관계."""
    f = Fig("카드_데이터속성_객체간관계.svg")
    f.add([rect(3, 4, 560, 64, 18, fill=WHITE, stroke=NAVY, sw=3)])
    f.lab("물음", QUESTION, 283, 6, 520)
    cx0, cw, top = 40, 480, 90
    bot, ys = side_card(f, cx0, top, cw, "cooler", "구성 요소", "오일 쿨러", [("식별자", "EQ-02-COOLER")], hot_rows=(0,))
    f.add(arrow([(150, 72), (150, top - 6)], BLUE, sw=6, size=17))
    sx0, sw_ = 790, 400
    sbot, sys_ = side_card(f, sx0, top, sw_, "sensor", "센서", "유온 센서", [("식별자", "EQ-02-TEMP"), ("단위", "℃")], hot_rows=(1,))
    ay = top + 18 + 44
    harrow(f, cx0 + cw + 12, sx0 - 12, ay, BLUE, label="감시된다", small=False)
    f.lab("객체 간 관계", "Object Property / 다른 인스턴스를 가리킨다", 655, ay + 24, 250)
    f.lab("데이터 속성", "Data Property · 값을 담는다", cx0 + cw / 2, bot + 10, cw)
    ab = sbot + 20
    f.add(arrow([(990, sbot + 2), (990, ab)], BLUE, sw=6, size=15))
    f.add([rect(840, ab + 2, 300, FH - 6 - ab, 18, fill=PALE, stroke=BLUE, sw=4)])
    f.lab("찾은 답", "℃", 990, ab + 2 + (FH - 6 - ab) / 2 - 31, 280)
    return f


def f12():
    """12장: 위 띠는 클래스 사이에 한 번 정한 관계 유형(구성 요소 → 감시된다 → 센서), 아래 띠는 세 설비의 오일 쿨러와 유온 센서가
    저마다 같은 유형의 관계로 이어진 모습. 맨 아래 줄은 1회차에서 푼 까닭(이름이 갈리면 컴퓨터가 놓친다)을 한 마디로만 받는다."""
    f = Fig("카드_관계유형_세설비.svg")
    xa, xb, ky = 520, 940, 62
    f.add(band_rect(4, 120, PALE) + band_rect(132, 432, LIGHT))
    f.lab("관계 유형", "클래스 사이에 / 이름과 방향을 한 번 정한다", 145, ky - 46, 250)
    f.lab("인스턴스 사이의 관계", "모두 같은 유형을 따른다", 145, 282 - 35, 250)
    for x in (xa, xb):
        f.add(dash_line(x, ky + 40, x, 140, GREY, 3.5, 8, 6))
    hcard(f, xa, ky, 230, 76, "none", name="구성 요소", ring=True, strong=True)
    hcard(f, xb, ky, 230, 76, "none", name="센서", ring=True, strong=True)
    harrow(f, xa + 125, xb - 125, ky, label="감시된다")
    for i, cy in enumerate((182, 282, 382)):
        hcard(f, xa, cy, 270, 84, "cooler", name="오일 쿨러", desc=f"EQ-0{i + 1}-COOLER")
        hcard(f, xb, cy, 270, 84, "sensor", name="유온 센서", desc=f"EQ-0{i + 1}-TEMP")
        harrow(f, xa + 145, xb - 145, cy, label="감시된다")
    f.add([rect(3, 446, 1194, 60, 22, fill=PALE, stroke="none", sw=0)])
    f.lab("한 번 정해 두면 적는 사람마다 이름이 갈리지 않아, 세 설비의 연결을 한 번에 모아 묻는다", "", 600, 476 - 19, 1150)
    return f


def f13():
    """13장: 표기 셋을 줄 하나씩. 줄마다 왼쪽에 표기와 그 관계, 오른쪽에 인스턴스 카드와 화살표. 화살표를 세면 표기와 같다:
    1:1은 한 쌍, 1:N은 주 펌프 하나에 센서 둘, N:M은 공급사 하나가 부품 둘에, 부품 하나에 공급사 둘.
    1:1 줄에는 많아야 하나를 넘는 연결(2호기를 같은 자리에 또 잇기) 하나를 ✕로 보인다(10장의 ✕ 꼴). 맨 아래 줄은 많아야 · 적어도."""
    f = Fig("카드_카디널리티_세표기.svg")
    rows = [(4, 150), (158, 306), (314, 462)]
    for y0, y1 in rows:
        f.add([rect(3, y0, 1194, y1 - y0, 20, fill=LIGHT, stroke="none", sw=0)])
    heads = [("1:1", "설비 → 놓인다 → 설치 위치 / 양쪽 모두 많아야 하나"),
             ("1:N", "구성 요소 → 감시된다 → 센서 / 구성 요소 하나에 센서 여럿, / 센서 하나에 구성 요소 하나"),
             ("N:M", "공급사 → 공급한다 → 부품 / 양쪽 모두 여럿")]
    for (y0, y1), (t, d) in zip(rows, heads):
        nd = len(d.split(" / "))
        cy = (y0 + y1) / 2
        f.lab(t, d, 175, cy - (LH_T + nd * LH_D) / 2 - 6, 330, strong=True)
    LX, RX, W, H = 520, 960, 260, 64
    a0, a1 = LX + W / 2 + 10, RX - W / 2 - 10

    def node(x, y, kind, cls, nm, **kw):
        hcard(f, x, y, W, H, kind, cls, nm, small=True, **kw)
    # 1:1과 많아야를 넘는 연결 하나
    node(LX, 42, "equip", "설비", "1호기"); node(RX, 42, "loc", "설치 위치", "1번 자리")
    f.add(arrow([(a0, 42), (a1, 42)]))
    node(LX, 112, "equip", "설비", "2호기", grey=True)
    xs, ys_, xe, ye = a0, 108, a1, 58
    xm, ym = (xs + xe) / 2, (ys_ + ye) / 2
    f.add(dash_arrow([(xs, ys_), (xe, ye)], GREY, 4, 14, 9, 7))
    f.add([circle(xm, ym, 19, fill=WHITE, stroke=NAVY, sw=4), line(xm - 8, ym - 8, xm + 8, ym + 8, stroke=NAVY, sw=5),
           line(xm + 8, ym - 8, xm - 8, ym + 8, stroke=NAVY, sw=5)])
    f.lab("", "많아야 하나를 넘는다", xm + 20, ym + 24, 200)
    # 1:N
    node(LX, 232, "pump", "구성 요소", "주 펌프")
    node(RX, 197, "sensor", "센서", "토출 압력 센서"); node(RX, 267, "sensor", "센서", "유량 센서")
    f.add(arrow([(a0, 224), (a1, 201)]) + arrow([(a0, 240), (a1, 263)]))
    # N:M
    node(LX, 353, "supplier", "공급사", "공급사 1"); node(LX, 423, "supplier", "공급사", "공급사 2")
    node(RX, 353, "core", "부품", "쿨러 코어"); node(RX, 423, "bearing", "부품", "팬 베어링")
    f.add(arrow([(a0, 349), (a1, 349)]) + arrow([(a0, 361), (a1, 413)]) + arrow([(a0, 427), (a1, 427)]))
    f.lab("1:1 · 1:N · N:M은 많아야를 적고, 적어도 몇 개(하나 이상)는 표기 옆에 함께 적는다", "", 600, 488 - 19, 1150)
    return f


XE, XC, XP = 150, 560, 1000


def class_band(f: Fig, notes=True, bot=116, ky=42):
    """14 · 20장 위 띠: 클래스 셋(설비 · 구성 요소 · 부품)과 관계 유형 둘. notes면 관계 이름 아래에 카디널리티를 적는다."""
    f.add(band_rect(4, bot, PALE))
    for x, nm in ((XE, "설비"), (XC, "구성 요소"), (XP, "부품")):
        hcard(f, x, ky, 210, 64, "none", name=nm, ring=True, strong=True)
    f.add(arrow([(XE + 115, ky), (XC - 115, ky)]) + arrow([(XC + 115, ky), (XP - 115, ky)]))
    f.lab("가진다", "**1:N**" if notes else "", (XE + XC) / 2, ky + 10, 160)
    f.lab("쓴다", "**N:M**" if notes else "", (XC + XP) / 2, ky + 10, 160)


def f14():
    """14장: 오일 쿨러는 설비마다 하나씩(정비 이력을 묻는다), 쿨러 코어는 품번마다 하나(주문할 부품을 묻는다).
    화살표를 세면 위 띠의 표기와 같다: 가진다 1:N — 오일 쿨러마다 설비는 하나, 3호기는 오일 쿨러와 쿨러 팬(회색 갈래) 둘을 가진다.
    쓴다 N:M — 품번 하나(쿨러 코어 CC-2040)를 오일 쿨러 셋이 쓰고, 3호기의 오일 쿨러는 쿨러 가스켓(회색)도 쓴다."""
    f = Fig("카드_하나로세기.svg")
    class_band(f)
    R, h = (154, 224, 294), 62
    for y, nm in zip(R, ("1호기", "2호기", "3호기")):
        hcard(f, XE, y, 200, h, "equip", name=nm)
        hcard(f, XC, y, 220, h, "cooler", name="오일 쿨러")
        f.add(arrow([(XE + 110, y), (XC - 120, y)]))
    fy = 364
    hcard(f, XC, fy, 220, h, "fan", name="쿨러 팬", grey=True)
    f.add(arrow([(200, R[2] + h / 2 + 2), (200, fy), (XC - 120, fy)], GREY))
    cy, ch, kw = 206, 104, 250
    hcard(f, XP, cy, kw, ch, "core", "부품", "쿨러 코어", desc="품번 CC-2040", hot=True)
    gy = 330
    hcard(f, XP, gy, kw, 66, "gasket", name="쿨러 가스켓", grey=True)
    ex = XP - kw / 2 - 10
    for i, y in enumerate(R):
        sy = y - 6 if i == 2 else y
        f.add(arrow([(XC + 120, sy), (ex, cy + (y - cy) * 0.3)]))
    f.add(arrow([(XC + 120, R[2] + 8), (ex, gy)], GREY))
    f.add([rect(230, 410, 560, 96, 20, fill=WHITE, stroke=NAVY, sw=3), rect(810, 410, 387, 96, 20, fill=PALE, stroke=BLUE, sw=4)])
    f.lab("설비마다 하나씩 센다", "2호기 오일 쿨러의 정비 이력을 묻는다", 510, 458 - 30, 540)
    f.lab("품번마다 하나로 센다", "CC-2040 하나를 오일 쿨러 셋이 쓴다 / 쿨러마다 든 실물은 따로 세지 않는다", 1003, 458 - 41, 370)
    return f


def prop_class(f: Fig, cx, top, w, name, common, own, hot=False, h_head=84, r=28):
    """16 · 17장의 클래스 카드: 테두리 원(클래스) + 이름, 그 아래 속성 목록 칸. common은 강조(파랑)로 적는 공통 속성 줄.
    own은 「 / 」로 줄을 나눌 수 있다. 돌려주는 값: 카드 아래 y."""
    lines = (common.split(" / ") if common else []) + (own.split(" / ") if own else [])
    bh = 12 + 5 + len(lines) * LH_D + 10
    bot = top + h_head + bh + 12
    x0 = cx - w / 2
    f.add(box(x0, top, w, bot - top, hot))
    f.add([circle(x0 + 16 + r, top + h_head / 2 + 2, r, fill=WHITE, stroke=NAVY, sw=3)])
    tx0 = x0 + 16 + 2 * r + 10
    f.lab(name, "", (tx0 + x0 + w) / 2, top + h_head / 2 + 2 - 19, x0 + w - tx0 - 10, strong=True)
    f.add([rect(x0 + 14, top + h_head, w - 28, bh, 12, fill=PALE if hot else LIGHT, stroke="none", sw=0)])
    desc = " / ".join(([f"**{c}**" for c in common.split(" / ")] if common else []) + (own.split(" / ") if own else []))
    f.lab("", desc, cx, top + h_head + 12 - 5, w - 40)
    return bot


def f16():
    """16장: 펌프 · 쿨러 · 팬에만 있는 속성을 둘 곳. 왼쪽은 구성 요소 하나에 다 두어 오일 쿨러에도 빈 칸이 생기는 모습,
    오른쪽은 클래스 셋으로 나눠 공통 속성(파랑)을 세 번 적고 「모든 구성 요소」를 세 번 따로 묻는 모습."""
    f = Fig("카드_자기속성_세클래스.svg")
    f.add([rect(3, 4, 352, 502, 22, fill=LIGHT, stroke="none", sw=0), rect(370, 4, 827, 502, 22, fill=LIGHT, stroke="none", sw=0)])
    f.lab("한 클래스에 모두 두면", "", 179, 22, 330)
    f.lab("클래스를 따로 나누면", "", 783, 22, 600)
    top = 92
    b = prop_class(f, 179, top, 316, "구성 요소", "", "식별자 · 이름 · 다른 이름 / 토출 유량 · 냉각 용량 · 회전수")
    for cx, nm, own in ((520, "펌프", "토출 유량"), (783, "쿨러", "냉각 용량"), (1046, "팬", "회전수")):
        bb = prop_class(f, cx, top, 250, nm, "식별자 · 이름 / 다른 이름", own)
    yb = max(b, bb) + 34
    f.add([rect(26, yb, 306, 130, 16, fill=WHITE, stroke=GREY, sw=3), rect(396, yb, 775, 130, 16, fill=WHITE, stroke=GREY, sw=3)])
    f.lab("오일 쿨러에도", "토출 유량 · 회전수 칸이 / 빈 채로 붙는다", 179, yb + 65 - 41, 280)
    f.lab("같은 속성을 클래스마다 거듭 적는다", "모든 구성 요소를 찾으려면 / 세 클래스를 따로 묻는다", 783, yb + 65 - 41, 740)
    for cx in (520, 783, 1046):
        f.add(arrow([(cx, yb - 26), (cx, yb - 4)], GREY, sw=4, size=12))
    f.add(arrow([(179, yb - 26), (179, yb - 4)], GREY, sw=4, size=12))
    return f


def f17():
    """17장: 공통 속성은 상위 클래스(구성 요소)에 한 번, 하위 클래스(펌프 · 쿨러 · 팬)는 자기 속성만. 상속은 속이 빈 삼각 화살촉으로
    하위에서 상위로 긋는다. 맨 아래 2호기의 오일 쿨러는 쿨러의 인스턴스이고, 그래서 구성 요소의 인스턴스이기도 하다."""
    f = Fig("카드_상속_계층.svg")
    sb = prop_class(f, 600, 6, 400, "구성 요소", "식별자 · 이름 · 다른 이름", "", hot=True, h_head=78)
    f.lab("상위 클래스", "Superclass", 210, (6 + sb) / 2 - 30, 260)
    bus, stop = sb + 56, sb + 80
    f.add(tri_head(600, sb + 4, -math.pi / 2, NAVY, 24) + [line(600, sb + 26, 600, bus, stroke=NAVY, sw=4)])
    f.add([line(200, bus, 1000, bus, stroke=NAVY, sw=4)])
    for x in (200, 600, 1000):
        f.add([line(x, bus, x, stop, stroke=NAVY, sw=4)])
    f.lab("상속(Inheritance)", "", 1010, bus - 48, 260)
    f.lab("하위 클래스", "Subclass", 210, bus - 66, 260)
    for cx, nm, own in ((200, "펌프", "토출 유량"), (600, "쿨러", "냉각 용량"), (1000, "팬", "회전수")):
        b2 = prop_class(f, cx, stop, 300, nm, "", own, h_head=78)
    it = b2 + 44
    f.add(dash_arrow([(600, it - 4), (600, b2 + 8)], BLUE, 4.5, 16, 9, 7))
    f.lab("속한다", "", 662, b2 + 4, 90)
    hcard(f, 600, it + (FH - 4 - it) / 2, 300, FH - 4 - it, "cooler", "쿨러", "오일 쿨러", hot=True)
    f.lab("쿨러이면서 구성 요소", "하위 클래스의 인스턴스는 / 상위 클래스의 인스턴스이기도 하다", 975, it, 400)
    f.lab("클래스 계층", "Class Hierarchy / 클래스가 클래스 아래로 / 이어진 모양", 200, b2 + 22, 300)
    return f


def f18():
    """18장: 위 띠(클래스)에 설비 → 가진다 → 구성 요소(관계 유형)와 쿨러 ▷ 구성 요소(상속), 아래 띠(인스턴스)에 2호기 → 가진다 → 오일 쿨러.
    오일 쿨러에서 쿨러로 점선 「속한다」 하나를 올린다. ① 한 종류다 = 상속, ② 속한다 = 인스턴스, ③ 일부다 = 관계(가진다)."""
    f = Fig("카드_세연결_가르기.svg")
    XE, XC, XK, ky, iy = 170, 600, 1030, 92, 410
    f.add(band_rect(4, 182, PALE) + band_rect(196, 506, LIGHT))
    f.lab("", "**클래스**", 60, 12, 100)
    f.lab("", "**인스턴스**", 64, 204, 110)
    for x, nm in ((XE, "설비"), (XC, "구성 요소"), (XK, "쿨러")):
        hcard(f, x, ky, 230, 80, "none", name=nm, ring=True, strong=True)
    harrow(f, XE + 125, XC - 125, ky, label="가진다")
    f.add([line(XK - 125, ky, XC + 150, ky, stroke=NAVY, sw=4)] + tri_head(XC + 127, ky, math.pi, NAVY, 24))
    f.lab("① 한 종류다", "상속", (XC + XK) / 2 + 12, ky - 72, 200)
    for x, kind, nm in ((XE, "equip", "2호기"), (XK, "cooler", "오일 쿨러")):
        hcard(f, x, iy, 250, 92, kind, name=nm, hot=x == XK)
    f.add(dash_arrow([(XK, iy - 52), (XK, ky + 48)], BLUE, 4.5, 16, 9, 7))
    f.lab("② 속한다", "인스턴스", XK + 66, 232, 130)
    harrow(f, XE + 135, XK - 135, iy, BLUE, label=None)
    f.lab("③ 가진다", "일부다 · 관계", (XE + XK) / 2, iy - 70, 220)
    return f


def f19():
    """19장: 물음 「2호기 오일 쿨러에 갈아 끼울 부품의 품번」을 관계로 따라간다. ① 2호기가 가진 구성 요소 가운데 오일 쿨러로,
    ② 오일 쿨러가 쓰는 부품 쿨러 코어로, ③ 그 부품의 품번 칸을 읽어 답에 닿는다. 가지 않은 갈래(쿨러 팬 · 주 펌프)는 회색."""
    f = Fig("카드_품번_따라가기.svg", dy=12)
    f.add([rect(3, 4, 640, 66, 18, fill=WHITE, stroke=NAVY, sw=3), rect(840, 4, 357, 66, 18, fill=PALE, stroke=BLUE, sw=4)])
    f.lab("물음", "2호기 오일 쿨러에 갈아 끼울 부품의 품번", 323, 7, 600)
    f.lab("찾은 답", "품번 **CC-2040**", 1018, 7, 330)
    ry = 196
    hcard(f, 130, ry, 230, 96, "equip", "설비", "2호기", hot=True)
    f.add(arrow([(130, 74), (130, ry - 54)], BLUE, sw=6, size=17))
    hcard(f, 500, ry, 250, 96, "cooler", "구성 요소", "오일 쿨러", hot=True)
    harrow(f, 250, 370, ry, BLUE, label="① 가진다", small=False)
    hcard(f, 500, 330, 250, 80, "fan", "구성 요소", "쿨러 팬", grey=True)
    hcard(f, 500, 440, 250, 80, "pump", "구성 요소", "주 펌프", grey=True)
    f.add(arrow([(200, ry + 52), (200, 330), (370, 330)], GREY) + arrow([(200, 330), (200, 440), (370, 440)], GREY))
    kx0, kw, ktop, kB, kbot = 850, 330, 132, 244, 330
    f.add(banded(kx0, ktop, kw, kbot, kB, PALE, BLUE, 5))
    r = 40
    f.add(disc(kx0 + 16 + r, (ktop + kB) / 2, r, "core"))
    tx0 = kx0 + 16 + 2 * r + 8
    tx, tw = (tx0 + kx0 + kw) / 2, kx0 + kw - tx0 - 6
    f.lab("", "**부품**", tx, (ktop + kB) / 2 - 33, tw)
    f.lab("쿨러 코어", "", tx, (ktop + kB) / 2 - 5, tw)
    cells(f, kx0 + 16, kB + 14, kw - 32, [("③ 품번", "CC-2040")], item_w=124, rh=58, hot=(0,))
    harrow(f, 630, kx0 - 12, ry, BLUE, label="② 쓴다", small=False)
    f.add(arrow([(1150, ktop - 6), (1150, 76)], BLUE, sw=6, size=17))
    return f


def f20():
    """20장: 14장과 같은 띠(클래스 셋 · 관계 유형 둘, 바꾸지 않는다) 아래에 1~3호기와 저마다의 오일 쿨러, 그리고 새로 더한 4호기와
    그 오일 쿨러(식별자를 적은 파란 점선 카드)를 둔다. 새 오일 쿨러는 있던 품번 노드(쿨러 코어 CC-2040)에 잇는다.
    「있으면」의 몫이 먼저 보이게 카디널리티 표기와 회색 갈래는 14장에만 두고 여기서는 그리지 않는다."""
    f = Fig("카드_설비늘기.svg")
    class_band(f, notes=False, bot=100)
    R = (146, 214, 282, 352)
    for i, (y, nm) in enumerate(zip(R, ("1호기", "2호기", "3호기", "4호기"))):
        new = i == 3
        hh = 66 if new else 60
        hcard(f, XE, y, 200, hh, "equip", name=nm, dashed=new, desc="EQ-04" if new else "")
        hcard(f, XC, y, 220, hh, "cooler", name="오일 쿨러", dashed=new, desc="EQ-04-COOLER" if new else "")
        f.add(arrow([(XE + 110, y), (XC - 120, y)], BLUE if new else NAVY))
    cy, kw = 249, 250
    hcard(f, XP, cy, kw, 104, "core", "부품", "쿨러 코어", desc="품번 CC-2040", hot=True)
    ex = XP - kw / 2 - 10
    for i, y in enumerate(R):
        new = i == 3
        f.add((dash_arrow if new else arrow)([(XC + 120, y), (ex, cy + (y - cy) * 0.3)], BLUE if new else NAVY))
    f.add([rect(3, 410, 640, 96, 20, fill=WHITE, stroke=BLUE, sw=4)])
    f.lab("4호기 오일 쿨러에 갈아 끼울 부품의 품번", "가진다 → 쓴다 → 품번, 같은 길로 CC-2040", 323, 458 - 30, 620)
    f.add([rect(660, 410, 537, 96, 20, fill=PALE, stroke="none", sw=0)])
    f.lab("더한 것은 식별자를 붙인 인스턴스 둘", "클래스 · 관계 유형 · 카디널리티는 바꾸지 않는다", 928, 458 - 30, 520)
    return f


# ───────────────────────── 2단원(21~34장) ─────────────────────────

def check_badge(cx, cy, r=20):
    """받아들여진 것: 하늘색 원과 체크."""
    return [circle(cx, cy, r, fill=SKY, stroke=NAVY, sw=3.5),
            path(f"M {cx - r * 0.45},{cy + 1} L {cx - r * 0.1},{cy + r * 0.38} L {cx + r * 0.5},{cy - r * 0.38}", stroke=NAVY, sw=5)]


def cross_badge(cx, cy, r=20):
    """걸린 것: 흰 원과 ✕(10 · 13장과 같은 꼴)."""
    d = r * 0.42
    return [circle(cx, cy, r, fill=WHITE, stroke=NAVY, sw=4),
            line(cx - d, cy - d, cx + d, cy + d, stroke=NAVY, sw=5), line(cx + d, cy - d, cx - d, cy + d, stroke=NAVY, sw=5)]


def f22():
    """22장: 세 시스템이 클래스 · 관계 이름은 같게(오일 쿨러 → 쓴다 → 쿨러 코어) 적었지만, 같은 대상을 가리키는 값(품번 표기) ·
    값의 꼴(교체 주기) · 빠진 값(품번 빈칸) · 관계 방향이 갈린다. 맨 아래 물음은 오일 쿨러 셋 가운데 하나만 찾는다."""
    f = Fig("카드_의미불일치_세시스템.svg")
    spec = [("설비 대장", "품번 CC-2040 / 교체 주기 12", "견줄 기준으로 둔 기록", False),
            ("부품 목록", "품번 **cc2040** / 교체 주기 **1년**", "**같은 대상을 가리키는 값**과 / **값의 꼴**이 다르다", False),
            ("정비 기록", "품번 **(빈칸)** / 교체 주기 12", "**관계 방향**이 반대이고 / 품번이 **빠졌다**", True)]
    for i, (cx, (sysname, core, cap, rev)) in enumerate(zip((200, 600, 1000), spec)):
        f.add([rect(cx - 188, 4, 376, 404, 22, fill=LIGHT, stroke="none", sw=0)])
        hcard(f, cx, 44, 260, 64, "doc", name=sysname)
        hcard(f, cx, 140, 280, 80, "cooler", name="오일 쿨러", desc=f"EQ-0{i + 1}-COOLER")
        y0, y1 = 182, 236
        f.add(arrow([(cx, y1), (cx, y0 + 4)] if rev else [(cx, y0), (cx, y1 - 4)], BLUE if rev else NAVY))
        f.lab("쓴다", "", cx + 58, (y0 + y1) / 2 - 19, 90)
        hcard(f, cx, 290, 280, 104, "core", name="쿨러 코어", desc=core)
        f.lab("", cap, cx, 352, 350)
    f.add([rect(3, 420, 1194, 86, 22, fill=WHITE, stroke=BLUE, sw=3)])
    f.lab("물음 「CC-2040을 쓰는 구성 요소는」", "오일 쿨러 셋 가운데 품번과 방향이 맞게 적힌 하나만 나온다", 600, 463 - 30, 1100)
    return f


def f23():
    """23장: 위 띠는 온톨로지 스키마(클래스 · 속성 · 관계 · 제약 네 칸, 인스턴스 없음), 아래 띠는 그 정의대로 세 시스템이 적은
    인스턴스 데이터 — 22장의 세 시스템이 같은 스키마를 보고 적어 쿨러 코어가 같아졌다(품번 CC-2040 · 교체 주기 12 · 같은 방향의 쓴다).
    오른쪽 칸은 22장의 물음에 오일 쿨러 셋이 다 나온다는 답. 맨 아래 줄은 스키마와 인스턴스 데이터의 실제 차이."""
    f = Fig("카드_스키마_인스턴스데이터.svg")
    f.add(band_rect(4, 124, PALE) + band_rect(134, 442, LIGHT))
    f.lab("온톨로지 스키마", "Schema / 공통 정의", 130, 64 - 36, 230)
    f.lab("인스턴스 데이터", "Instance Data / 지식 그래프를 / 이루는 기록", 130, 286 - 47, 230)
    gx0, gx1 = 262, 1188
    cw = (gx1 - gx0) / 2
    for c, t in enumerate(("**클래스**   구성 요소 · 부품 / **관계**   쓴다, 방향과 개수까지",
                           "**속성**   품번 · 교체 주기, 값의 꼴과 꼭 적을지 / **제약**   적어 넣는 지식이 지켜야 할 조건")):
        x = gx0 + c * cw
        f.add([rect(x + 4, 14, cw - 8, 100, 14, fill=WHITE, stroke=NAVY, sw=2.5)])
        f.lab("", t, x + cw / 2, 64 - 24, cw - 30)
    f.add(dash_arrow([(500, 116), (500, 146)], GREY, 4, 12, 7, 5))
    rows = ((188, "설비 대장", "EQ-01-COOLER"), (286, "부품 목록", "EQ-02-COOLER"), (384, "정비 기록", "EQ-03-COOLER"))
    for cy, sysname, code in rows:
        f.lab("", sysname, 318, cy - 13, 104)
        hcard(f, 500, cy, 256, 74, "cooler", name="오일 쿨러", desc=code)
        harrow(f, 632, 704, cy, NAVY, label="쓴다" if sysname == "설비 대장" else None)
        hcard(f, 840, cy, 260, 88, "core", name="쿨러 코어", desc="품번 CC-2040 / 교체 주기 12")
    f.add([rect(982, 160, 206, 260, 20, fill=WHITE, stroke=BLUE, sw=4)])
    f.lab("물음", "CC-2040을 쓰는 / 구성 요소는 / → 오일 쿨러 셋이 / 다 나온다", 1085, 190, 190)
    f.add(check_badge(1085, 366, 24))
    f.lab("온톨로지 스키마에는 인스턴스가 없고, 인스턴스 데이터는 그 정의대로 적은 실제 대상 · 속성값 · 연결이다", "",
          600, 474 - 19, 1150)
    return f


def class_def_card(f: Fig, x0, top, w, h, name, meaning):
    """24장 클래스 정의 카드: 빈 테두리 원 + 클래스 이름, 아래 띠에 의미 한 문장."""
    B = top + h - 64
    f.add(banded(x0, top, w, top + h, B, PALE, NAVY, 3))
    f.add([circle(x0 + 16 + 36, (top + B) / 2, 36, fill=WHITE, stroke=NAVY, sw=3)])
    tx0 = x0 + 16 + 72 + 10
    f.lab(name, "", (tx0 + x0 + w) / 2, (top + B) / 2 - 19, x0 + w - tx0 - 10, strong=True)
    f.lab("", f"**의미**   {meaning}", x0 + w / 2, B + 32 - 13, w - 30)


def f24():
    """24장: 클래스 정의 카드 둘(이름 + 의미 한 문장). 새 대상 둘(구동 모터 · 펌프 축 씰)이 의미 문장에 맞는 클래스로 들어간다."""
    f = Fig("카드_클래스정의_의미.svg")
    f.lab("", "**새 대상**", 190, 8, 160)
    cards = [(125, "motor", "구동 모터", "구성 요소", "설비를 이루는 기계 하나하나"),
             (375, "seal", "펌프 축 씰", "부품", "구성 요소 안에서 닳으면 갈아 끼우는 것")]
    for cy, kind, nm, cls, meaning in cards:
        hcard(f, 190, cy, 300, 100, kind, name=nm)
        class_def_card(f, 635, cy - 80, 530, 160, cls, meaning)
        f.add(arrow([(352, cy), (621, cy)], BLUE, sw=6, size=19))
    f.lab("", "의미 문장에 맞춰 / 클래스를 고른다", 487, 250 - 24, 230)
    return f


def f25():
    """25장: 교체 주기를 자료형 수(개월)로 정의하면 12는 6과 견줄 수 있고, 글자로 적은 「1년」은 견줄 수 없다."""
    f = Fig("카드_자료형_수와글자.svg", dy=22)
    f.add([rect(20, 16, 520, 116, 18, fill=PALE, stroke=BLUE, sw=4), rect(600, 16, 580, 116, 18, fill=WHITE, stroke=NAVY, sw=3)])
    f.lab("교체 주기의 정의", "자료형 **수** · 단위 개월", 280, 74 - 30, 480)
    f.lab("물음", "교체 주기가 6개월보다 긴 부품", 890, 74 - 30, 540)
    for cy, val, ok, res in ((250, "교체 주기 12  (수)", True, "12 > 6, 견줄 수 있다"),
                             (410, "교체 주기 「1년」  (글자)", False, "글자라 6과 견줄 수 없다")):
        hcard(f, 280, cy, 420, 96, "core", name="쿨러 코어", desc=val)
        f.add(arrow([(500, cy), (640, cy)], NAVY if ok else GREY, sw=5))
        f.add(check_badge(680, cy, 24) if ok else cross_badge(680, cy, 24))
        f.lab(res, "", 920, cy - 19, 420)
    return f


def f26():
    """26장: 센서 클래스의 속성 셋(식별자 · 단위는 필수, 측정 범위는 선택). 단위가 빈 인스턴스는 넣기 전에 걸리고,
    측정 범위가 빈 인스턴스는 들어간다."""
    f = Fig("카드_필수선택_센서.svg")
    x0, w, top = 30, 480, 14
    bot = 470
    f.add([rect(x0, top, w, bot - top, 22, fill=WHITE, stroke=NAVY, sw=3)])
    f.add([circle(x0 + w / 2, top + 18 + 46, 46, fill=WHITE, stroke=NAVY, sw=3)])
    f.lab("센서", "", x0 + w / 2, top + 18 + 92 + 14, w - 40, strong=True)
    cells(f, x0 + 24, 210, w - 48, [("식별자", "필수"), ("단위", "필수"), ("측정 범위", "선택")], item_w=170, rh=60, gap=16, hot=(0, 1))
    for cy, desc, ok, res in ((130, "식별자 EQ-03-TEMP / 단위 **(빈칸)**", False, "걸린다"),
                              (360, "식별자 EQ-02-TEMP / 측정 범위 (빈칸)", True, "들어간다")):
        f.add(dash_arrow([(x0 + w + 10, cy), (596, cy)], GREY, 3.5, 13, 8, 6))
        hcard(f, 800, cy, 400, 104, "sensor", name="유온 센서", desc=desc)
        f.add(check_badge(1060, cy - 8, 24) if ok else cross_badge(1060, cy - 8, 24))
        f.lab(res, "", 1110, cy + 26, 170)
    return f


def f27():
    """27장: 위는 클래스마다 식별자로 쓸 속성 · 값을 적는 규칙 · 필수. 아래는 부품 기록 둘 — 정한 규칙대로 적은 CC-2040은 들어가고,
    규칙과 다른 cc2040은 넣기 전에 걸린다."""
    f = Fig("카드_식별자_스키마에적기.svg", dy=20)
    for cx, nm, desc in ((205, "설비", "식별자 **설비 코드** · 필수 / EQ-01처럼 적는다"),
                         (600, "구성 요소", "식별자 **구성 요소 코드** · 필수 / EQ-01-COOLER처럼 적는다"),
                         (995, "부품", "식별자 **품번** · 필수 / CC-2040처럼 적는다")):
        f.add([rect(cx - 190, 14, 380, 150, 18, fill=PALE, stroke=NAVY, sw=3)])
        f.lab(nm, desc, cx, 89 - 41, 360, strong=True)
    for cy, sysname, val, ok in ((290, "설비 대장", "품번 CC-2040", True), (420, "부품 목록", "품번 cc2040", False)):
        hcard(f, 250, cy, 380, 92, "doc", name=sysname, desc=val)
        f.add(arrow([(450, cy), (530, cy)], NAVY if ok else GREY, sw=5))
        f.add(check_badge(568, cy, 24) if ok else cross_badge(568, cy, 24))
    f.add(arrow([(602, 290), (780, 290)], BLUE, sw=6, size=19))
    hcard(f, 930, 290, 280, 112, "core", "부품", "쿨러 코어", desc="품번 CC-2040", hot=True)
    f.lab("정한 규칙과 달라 넣기 전에 걸린다", "", 830, 420 - 19, 460)
    return f


def f28():
    """28장: 설비 대장 · 시계열 저장소 · 생산 실적이 저마다의 칸에 같은 설비 코드 EQ-02를 적어, 따로 적은 기록이 설비 하나에 모인다.
    셋 모두 설비 단위로 적는 기록이다(구성 요소의 일은 구성 요소 식별자로 적는다 — 8장)."""
    f = Fig("카드_공통식별자_세시스템.svg")
    rows = ((95, "doc", "설비 대장", "**EQ-02** · 2호기 · 유압 파워팩"),
            (255, "tsdb", "시계열 저장소", "**EQ-02** · 유온 · 시각마다 값"),
            (415, "doc", "생산 실적", "**EQ-02** · 가동 시간"))
    for cy, kind, nm, desc in rows:
        hcard(f, 310, cy, 460, 112, kind, name=nm, desc=desc)
        f.add(arrow([(552, cy), (830, 255 + (cy - 255) * 0.25)], NAVY, sw=5))
    hcard(f, 1000, 255, 300, 120, "equip", "설비", "2호기", desc="EQ-02", hot=True)
    f.lab("", "설비 코드를 함께 쓴다", 1000, 330, 260)
    return f


def mini(f: Fig, cx, cy, kind, cls, nm, grey=False):
    hcard(f, cx, cy, 250, 66, kind, cls, nm, small=True, grey=grey)


def f29():
    """29장: 위는 관계 가진다의 정의(시작 클래스 설비 · 종료 클래스 구성 요소 · 1:N, 구성 요소마다 설비 적어도 하나).
    아래는 연결 셋 — 지킨 연결(✓), 오일 쿨러에서 2호기로 거꾸로 그은 연결(✕, 22장의 방향 갈림), 가진 설비가 없어 적어도를 못 채운 구성 요소(✕).
    많아야를 넘는 연결은 13장이 보였으므로 여기서는 그리지 않는다."""
    f = Fig("카드_관계정의_유효한연결.svg")
    f.add([rect(120, 10, 960, 176, 20, fill=PALE, stroke=BLUE, sw=4)])
    f.lab("가진다의 정의", "", 600, 22, 400, strong=True)
    for cx, item, val in ((300, "시작 클래스", "**설비**"), (600, "종료 클래스", "**구성 요소**"),
                          (900, "카디널리티", "**1:N** · 구성 요소마다 / 설비 적어도 하나")):
        f.add([rect(cx - 140, 66, 280, 108, 14, fill=WHITE, stroke=NAVY, sw=2)])
        f.lab(item, val, cx, 120 - 30 if "적어도" not in val else 120 - 41, 260)
    cols = (200, 600, 1000)
    for cx in cols:
        f.add([rect(cx - 190, 206, 380, 300, 22, fill=LIGHT, stroke="none", sw=0)])
    ty, by = 262, 386
    # 지킨 연결
    mini(f, 200, ty, "equip", "설비", "2호기"); mini(f, 200, by, "cooler", "구성 요소", "오일 쿨러")
    f.add(arrow([(200, ty + 36), (200, by - 37)]))
    f.lab("", "가진다", 250, (ty + by) / 2 - 13, 90)
    f.add(check_badge(330, (ty + by) / 2, 20))
    f.lab("유효한 연결", "", 200, 440, 340)
    # 거꾸로 그은 연결(22장 정비 기록의 방향 갈림을 막는 자리)
    mini(f, 600, ty, "equip", "설비", "2호기"); mini(f, 600, by, "cooler", "구성 요소", "오일 쿨러")
    f.add(arrow([(600, by - 36), (600, ty + 37)], GREY))
    f.lab("", "가진다", 650, (ty + by) / 2 - 13, 90)
    f.add(cross_badge(730, (ty + by) / 2, 20))
    f.lab("시작 · 종료 클래스가 거꾸로다", "", 600, 440, 360)
    # 적어도를 못 채움
    f.add(dash_rect(1000 - 125, ty - 33, 250, 66, GREY, 3, 9, 7))
    mini(f, 1000, by, "cooler", "구성 요소", "오일 쿨러")
    f.add(cross_badge(1000, (ty + by) / 2, 20))
    f.lab("가진 설비가 없다", "", 1000, 440, 340)
    return f


def f30():
    """30장: 역량 질문에서 시작해 필요한 것만 스키마에 정의하고, 정의대로 인스턴스 데이터를 적고, 다시 그 질문으로 확인하는 고리."""
    f = Fig("카드_역량질문_고리.svg")
    hcard(f, 250, 255, 440, 150, "question", name="역량 질문", desc="2호기 오일 쿨러에 갈아 끼울 / 부품의 품번은 무엇인가", hot=True)
    hcard(f, 960, 105, 300, 110, "sheet", name="스키마 정의")
    hcard(f, 960, 405, 300, 110, "graph", name="인스턴스 데이터")
    f.add(arrow([(475, 210), (800, 120)], NAVY, sw=5))
    f.add(arrow([(960, 166), (960, 344)], NAVY, sw=5))
    f.add(arrow([(800, 390), (475, 300)], BLUE, sw=5))
    f.lab("", "필요한 것만 정의한다", 600, 108, 240)
    f.lab("", "정의대로 적는다", 1090, 243, 200)
    f.lab("", "그 질문으로 확인한다", 600, 384, 240)
    return f


def f31():
    """31장: 19장의 질문을 낱말 칩으로 나누고, 칩마다 그 낱말을 무엇으로 옮기는지(클래스 · 관계 · 속성) 아래에 단다.
    「2호기 오일 쿨러」의 이어짐은 관계 가진다로 옮긴다."""
    f = Fig("카드_질문낱말_가르기.svg")
    f.lab("", "**역량 질문**", 600, 4, 300)
    chips = [(140, 150, "2호기", "클래스", "설비", "c"), (360, 210, "오일 쿨러에", "클래스", "구성 요소", "c"),
             (600, 200, "갈아 끼울", "관계", "쓴다", "r"), (830, 170, "부품의", "클래스", "부품", "c"),
             (1050, 170, "품번은", "속성", "품번", "p")]
    cy, ty = 76, 238
    for x, w, word, kind, val, k in chips:
        f.add([rect(x - w / 2, cy - 32, w, 64, 32, fill=WHITE, stroke=NAVY, sw=3)])
        f.lab(word, "", x, cy - 19, w - 16)
        f.add(arrow([(x, cy + 38), (x, ty - 48)], NAVY, sw=4, size=14))
        fill, edge = {"c": (PALE, NAVY), "r": (WHITE, BLUE), "p": (LIGHT, GREY)}[k]
        tw = max(w, 170)
        f.add([rect(x - tw / 2, ty - 42, tw, 84, 16, fill=fill, stroke=edge, sw=3 if k != "r" else 4)])
        f.lab(kind, f"**{val}**", x, ty - 30, tw - 16)
    gx, gy = 250, 384
    f.add(dash_line(140, ty + 46, 140, gy, GREY, 3, 8, 6) + dash_line(360, ty + 46, 360, gy, GREY, 3, 8, 6)
          + dash_line(140, gy, 360, gy, GREY, 3, 8, 6))
    f.add(arrow([(gx, gy), (gx, gy + 24)], GREY, sw=3, size=11))
    f.add([rect(gx - 105, gy + 30, 210, 84, 16, fill=WHITE, stroke=BLUE, sw=4)])
    f.lab("관계", "**가진다**", gx, gy + 42, 194)
    f.lab("", "2호기의 오일 쿨러라는 이어짐", gx + 250, gy + 50, 270)
    f.lab("", "클래스 셋 · 관계 둘 · 속성 하나를 정의하면 이 질문에 답한다", 905, 440, 500)
    return f


def f34():
    """34장: 역량 질문의 갈래대로 클래스를 네 영역에 나눠 맡는다. 영역마다 물음의 갈래와 1단원 꼴의 클래스 카드(빈 원판)를 두고,
    판단 · 성과는 회색으로 이름만 보인다. 진단 영역의 고장 유형 카드에서 설비 영역의 구성 요소 카드로 「일어난다」 하나가 영역을 건너
    같은 스키마의 관계로 잇는다. 맨 아래는 21장 물음의 「어떻게」에 답하는 한 줄."""
    f = Fig("카드_영역_넷.svg")
    boxes = [((10, 6, 520, 222), "설비 영역", "무엇이 어디에 달렸나", False, [("설비", "구성 요소"), ("센서", "부품")]),
             ((670, 6, 520, 222), "진단 영역", "왜 그렇게 됐나", False, [("고장 유형", "증상"), ("원인",)]),
             ((10, 240, 520, 160), "판단 영역", "무엇을 할 것인가", True, [("조치", "판단 규칙")]),
             ((670, 240, 520, 160), "성과 영역", "얼마나 나아졌나", True, [("전략 목표", "성과 지표")])]
    pos = {}
    for (x, y, w, h), nm, q, grey, grid in boxes:
        f.add([rect(x, y, w, h, 22, fill=LIGHT if grey else PALE, stroke=GREY if grey else NAVY, sw=3)])
        f.lab(nm, q, x + w / 2, y + 10, w - 40, strong=not grey)
        for r, row in enumerate(grid):
            for c, cls in enumerate(row):
                cx, cy = x + 135 + c * 250, y + 108 + r * 70
                hcard(f, cx, cy, 230, 60, "none", name=cls, ring=True, grey=grey)
                pos[cls] = (cx, cy)
    (gx, gy), (kx, ky) = pos["고장 유형"], pos["구성 요소"]
    f.add(arrow([(gx - 119, gy), (kx + 119, ky)], BLUE, sw=6, size=19))
    f.lab("일어난다", "", (gx + kx) / 2, gy - 46, 140, strong=True)
    f.add([rect(3, 422, 1194, 84, 22, fill=WHITE, stroke=BLUE, sw=3)])
    f.lab("역량 질문의 갈래로 나눠 맡아도, 같은 스키마 하나로 이어 같은 뜻으로 읽힌다", "", 600, 464 - 19, 1150)
    return f


# ───────────────────────── 3단원(35~51장) ─────────────────────────

def table(f: Fig, x, y, cols, header, rows, rh=50, hh=46, hot=(), title=False):
    """표 하나: 머리 줄(회색)과 값 줄(흰색, hot이면 하늘색). 칸 글은 라벨로 얹는다. 돌려주는 값: 칸마다의 (x0, x1) 목록과 끝 y."""
    w = sum(cols)
    xs, cx = [], x
    for c in cols:
        xs.append((cx, cx + c))
        cx += c
    f.add([rect(x, y, w, hh, 10, fill=GREY, stroke="none", sw=0)])
    for (a, b), h in zip(xs, header):
        f.lab("", h, (a + b) / 2, y + hh / 2 - 15, b - a - 8)
    ry = y + hh + 6
    for i, row in enumerate(rows):
        hr = i in hot
        f.add([rect(x, ry, w, rh, 10, fill=PALE if hr else WHITE, stroke=BLUE if hr else NAVY, sw=3 if hr else 2)])
        for k, ((a, b), v) in enumerate(zip(xs, row)):
            if k:
                f.add([line(a, ry + 8, a, ry + rh - 8, stroke=GREY, sw=2)])
            if title:
                f.lab(v, "", (a + b) / 2, ry + rh / 2 - 19, b - a - 8)
            else:
                f.lab("", v, (a + b) / 2, ry + rh / 2 - 15, b - a - 8)
        ry += rh + 6
    return xs, ry - 6


def code_box(f: Fig, cx, cy, w, h, text, hot=False):
    """글자로 적은 쿼리 조각을 담는 상자(연회색, hot이면 파란 테두리)."""
    f.add([rect(cx - w / 2, cy - h / 2, w, h, 14, fill=LIGHT, stroke=BLUE if hot else NAVY, sw=4 if hot else 2.5)])
    f.lab(text, "", cx, cy - 19, w - 20)


def ask_answer(f: Fig, answer=True):
    """38 · 39장 위 줄: 왼쪽 물음, 오른쪽 찾은 답(19장과 같은 꼴)."""
    f.add([rect(3, 4, 640, 66, 18, fill=WHITE, stroke=NAVY, sw=3)])
    f.lab("물음", "2호기 오일 쿨러에 갈아 끼울 부품의 품번", 323, 7, 600)
    if answer:
        f.add([rect(840, 4, 357, 66, 18, fill=PALE, stroke=BLUE, sw=4)])
        f.lab("찾은 답", "품번 **CC-2040**", 1018, 7, 330)


def f36():
    """36장: 그래프 DB 안의 모양. 노드 둘(설비 2호기 · 구성 요소 오일 쿨러)을 관계 가진다로 잇고, 노드마다 속성을 키와 값의 짝으로 붙인다.
    위 줄의 이름표(노드 · 관계 · 노드)가 세 조각을 가리킨다."""
    f = Fig("카드_저장구조_노드관계속성.svg", dy=36)
    for x, t in ((290, "노드"), (600, "관계"), (910, "노드")):
        f.lab(t, "", x, 0, 160, strong=True)
    spec = ((60, "equip", "설비", "2호기", [("설비 코드", "EQ-02"), ("이름", "2호기")], 150),
            (680, "cooler", "구성 요소", "오일 쿨러", [("구성 요소 코드", "EQ-02-COOLER"), ("이름", "오일 쿨러")], 196))
    top, B, w = 46, 160, 460
    for x0, kind, cls, nm, rows, iw in spec:
        bot = B + 18 + 2 * 54 + 10 + 18
        f.add(banded(x0, top, w, bot, B, LIGHT, NAVY, 3))
        r = 40
        f.add(disc(x0 + 18 + r, (top + B) / 2, r, kind))
        tx0 = x0 + 18 + 2 * r + 12
        tx, tw = (tx0 + x0 + w) / 2, x0 + w - tx0 - 8
        f.lab("", f"**{cls}**", tx, (top + B) / 2 - 33, tw)
        f.lab(nm, "", tx, (top + B) / 2 - 5, tw)
        cells(f, x0 + 18, B + 18, w - 36, rows, item_w=iw, rh=54)
    harrow(f, 530, 670, (top + B) / 2, BLUE, label="가진다", small=False)
    f.lab("속성", "회색 칸이 키(속성명), 흰 칸이 값(속성값)", 600, 330, 460, strong=True)
    return f


def f37():
    """37장: 관계형 DB는 클래스마다 테이블을 두고(위 줄 셋, 구성 요소 테이블만 파랑) 인스턴스 하나를 행 하나로, 속성을 열로 담는다.
    오일 쿨러 행은 하늘색, 이름 열은 파란 테두리."""
    f = Fig("카드_관계형_테이블.svg", dy=30)
    for cx, nm, hot in ((250, "설비 테이블", False), (600, "구성 요소 테이블", True), (950, "부품 테이블", False)):
        f.add([rect(cx - 150, 4, 300, 58, 16, fill=PALE if hot else WHITE, stroke=BLUE if hot else NAVY, sw=4 if hot else 2.5)])
        f.lab(nm, "", cx, 14, 280)
    f.add(arrow([(600, 66), (600, 104)], BLUE, sw=5, size=15))
    x0, cols = 150, (270, 230, 230)
    xs, yb = table(f, x0, 112, cols, ("구성 요소 코드", "이름", "설비 코드"),
                   [("EQ-02-COOLER", "오일 쿨러", "EQ-02"), ("EQ-02-FAN", "쿨러 팬", "EQ-02"), ("EQ-02-PUMP", "주 펌프", "EQ-02")],
                   rh=64, hh=50, hot=(0,), title=True)
    a, b = xs[1]
    f.add([rect(a + 4, 106, b - a - 8, yb - 106 + 8, 14, fill="none", stroke=BLUE, sw=4)])
    rx = x0 + sum(cols) + 30
    f.add(arrow([(rx + 64, 112 + 50 + 6 + 32), (rx + 4, 112 + 50 + 6 + 32)], BLUE, sw=5, size=15))
    f.lab("행", "인스턴스 하나", rx + 150, 112 + 50 + 6 + 32 - 30, 170, strong=True)
    f.lab("열", "속성 하나", (a + b) / 2, yb + 22, 200, strong=True)
    return f


def f38():
    """38장: 19장의 물음을 테이블 넷(설비 · 구성 요소 · 잇는 표 · 부품)에서 푼다. 표 이름 아래 작은 줄이 열 이름이고, 이웃한 두 테이블에서
    같은 값을 적은 열이 마주 본다. 마주 본 칸을 조인으로 잇는다. 쓴다는 다대다라 잇는 표(구성 요소 코드 · 품번)를 하나 더 건너고,
    그 표에는 다른 오일 쿨러가 같은 품번을 쓰는 줄도 있다. 질문의 길에 든 행은 하늘색."""
    f = Fig("카드_조인_네테이블.svg", dy=90)
    f.add([rect(3, 4, 640, 66, 18, fill=WHITE, stroke=NAVY, sw=3)])
    f.lab("물음", "2호기 오일 쿨러에 갈아 끼울 부품의 품번", 323, 7, 600)
    gap = 72
    specs = [("설비 테이블", "이름 · 설비 코드", (124, 124), [("2호기", "EQ-02")]),
             ("구성 요소 테이블", "설비 코드 · 구성 요소 코드", (124, 172), [("EQ-02", "EQ-02-COOLER")]),
             ("잇는 표", "구성 요소 코드 · 품번", (172, 124), [("EQ-02-COOLER", "CC-2040"), ("EQ-03-COOLER", "CC-2040")]),
             ("부품 테이블", "품번", (124,), [("CC-2040",)])]
    ty, rh = 186, 64
    x, edges = 4, []
    for i, (nm, cols_, ws, rows) in enumerate(specs):
        w = sum(ws)
        f.lab(nm, cols_, x + w / 2, ty - 66, max(w, 248) + 20, strong=(i == 2))
        for r, row in enumerate(rows):
            ry = ty + r * (rh + 8)
            hot = r == 0
            f.add([rect(x, ry, w, rh, 10, fill=PALE if hot else WHITE, stroke=BLUE if hot else NAVY, sw=3 if hot else 2)])
            cx0 = x
            for k, (v, cw) in enumerate(zip(row, ws)):
                if k:
                    f.add([line(cx0, ry + 8, cx0, ry + rh - 8, stroke=GREY, sw=2)])
                f.lab("", v, cx0 + cw / 2, ry + rh / 2 - 15, cw - 8)
                cx0 += cw
        edges.append((x, x + w))
        x += w + gap
    row_y = ty + rh / 2
    for i in range(3):
        a, b = edges[i][1], edges[i + 1][0]
        f.add([line(a + 6, row_y, b - 6, row_y, stroke=BLUE, sw=5), circle(a + 6, row_y, 5, fill=BLUE, stroke="none", sw=0),
               circle(b - 6, row_y, 5, fill=BLUE, stroke="none", sw=0)])
        f.lab("조인", "", (a + b) / 2, row_y + 14, gap - 4, strong=True)
    return f


def f39():
    """39장: 같은 물음을 그래프 DB에서 푼다. 2호기 → 가진다 → 오일 쿨러 → 쓴다 → 쿨러 코어로 저장된 관계를 따라간다.
    아래의 회색 오일 쿨러 둘(1 · 3호기)도 같은 쿨러 코어를 쓴다는 연결이 관계 하나씩으로 저장돼 있다(잇는 표가 없다)."""
    f = Fig("카드_관계따라가기_그래프.svg")
    ask_answer(f)
    ry = 196
    hcard(f, 150, ry, 270, 104, "equip", "설비", "2호기", desc="EQ-02", hot=True)
    hcard(f, 570, ry, 300, 104, "cooler", "구성 요소", "오일 쿨러", desc="EQ-02-COOLER", hot=True)
    hcard(f, 1018, ry, 300, 104, "core", "부품", "쿨러 코어", desc="품번 CC-2040", hot=True)
    harrow(f, 290, 414, ry, BLUE, label="가진다", small=False)
    harrow(f, 726, 862, ry, BLUE, label="쓴다", small=False)
    f.add(arrow([(1150, ry - 56), (1150, 76)], BLUE, sw=6, size=17))
    for y, code in ((340, "EQ-01-COOLER"), (440, "EQ-03-COOLER")):
        hcard(f, 570, y, 300, 80, "cooler", "구성 요소", "오일 쿨러", desc=code, grey=True, small=True)
        f.add(arrow([(726, y), (1018, ry + 58)], GREY, sw=4))
    f.lab("", "다른 오일 쿨러가 같은 부품을 쓰는 것도 / 관계 하나씩으로 저장돼 있다", 210, 362, 380)
    return f


def f40():
    """40장: 왼쪽은 온톨로지 스키마의 네 줄 — 위 둘(클래스 이름 · 관계 유형 이름)은 그래프 DB의 노드 · 관계에 이름으로 붙고(파랑),
    아래 둘(의미 · 자료형 · 필수, 시작 · 종료 클래스 · 카디널리티)은 노드 · 관계에 붙지 않고 스키마에 적혀 있으며 그 일부는 DB에 조건으로 건다(41장).
    오른쪽 이름은 쌍점 없이 영문만(쌍점은 44 · 45장에서 처음). 오른쪽 그래프 DB는 레이블이 붙은 노드 셋과
    관계 유형 둘(한글 이름을 곁에)."""
    f = Fig("카드_스키마와DB_가름.svg")
    f.add([rect(3, 4, 560, 502, 22, fill=LIGHT, stroke="none", sw=0), rect(640, 4, 557, 502, 22, fill=LIGHT, stroke="none", sw=0)])
    f.lab("온톨로지 스키마", "", 283, 16, 400, strong=True)
    f.lab("그래프 DB", "쿼리에 쓰는 영문 이름", 918, 6, 400, strong=True)
    rows = ((70, "클래스 이름", "설비 · 구성 요소 · 부품", False), (166, "관계 유형 이름", "가진다 · 쓴다", False),
            (282, "의미 · 자료형 · 필수", "", True), (378, "시작 · 종료 클래스 · 카디널리티", "", True))
    for y, nm, val, grey in rows:
        f.add([rect(26, y, 514, 80, 16, fill=WHITE if grey else PALE, stroke=GREY if grey else BLUE, sw=3 if grey else 4)])
        if val:
            f.lab(nm, val, 283, y + 40 - 30, 480)
        else:
            f.lab(nm, "", 283, y + 40 - 19, 480)
    f.lab("", "노드 · 관계에는 붙지 않는다 · 일부는 DB에 조건으로 건다", 283, 466, 520)
    f.add(arrow([(548, 158), (630, 158)], BLUE, sw=6, size=17))
    nodes = ((112, "Asset", "설비"), (264, "Component", "구성 요소"), (416, "Part", "부품"))
    for y, lb, ko in nodes:
        f.add([rect(680, y - 38, 290, 76, 38, fill=WHITE, stroke=NAVY, sw=3.5)])
        f.lab(lb, ko, 825, y - 30, 270)
    for (y1, _, _), (y2, _, _), lb, ko in ((nodes[0], nodes[1], "HAS_COMPONENT", "가진다"), (nodes[1], nodes[2], "USES_PART", "쓴다")):
        f.add(arrow([(825, y1 + 40), (825, y2 - 42)], BLUE, sw=5, size=15))
        f.lab(lb, ko, 1060, (y1 + y2) / 2 - 30, 260)
    return f


def f41():
    """41장: 넣을 데이터가 관문 둘을 지난다. 넣기 전에 검사 프로그램이 DB에 걸지 않은 규칙을 보고(29장의 거꾸로 그은 가진다 ✕),
    저장할 때 그래프 DB가 DB 제약 조건으로 막는다(유일 제약 — 품번이 같은 부품 둘째 ✕). 맨 아래는 걸 수 있는 조건이 제품 · 판마다 다르다는 한 줄."""
    f = Fig("카드_제약조건_두관문.svg")
    cy = 96
    hcard(f, 140, cy, 250, 100, "doc", name="넣을 데이터")
    hcard(f, 480, cy, 330, 116, "sheet", name="검사 프로그램", desc="넣기 전 / DB에 걸지 않은 규칙", hot=True)
    hcard(f, 870, cy, 330, 116, "graph", name="그래프 DB", desc="저장할 때 / DB에 건 조건", hot=True)
    f.add(arrow([(268, cy), (308, cy)], NAVY, sw=5, size=15) + arrow([(648, cy), (698, cy)], NAVY, sw=5, size=15)
          + arrow([(1038, cy), (1100, cy)], NAVY, sw=5, size=15))
    f.add(check_badge(1140, cy, 26))
    f.lab("", "저장", 1140, cy + 34, 90)
    for cx, bx, bw, title, desc in ((480, 480, 340, "", "오일 쿨러에서 2호기로 / 거꾸로 그은 가진다"),
                                    (870, 900, 470, "**유일 제약**(Uniqueness Constraint)", "품번 CC-2040인 부품이 / 하나 더 들어온다")):
        f.add(arrow([(cx, cy + 62), (cx, 214)], GREY, sw=4, size=14))
        f.add([rect(bx - bw / 2, 222, bw, 126, 18, fill=WHITE, stroke=NAVY, sw=2.5)])
        f.add(cross_badge(bx - bw / 2 + 40, 285, 20))
        if title:
            f.lab(title, desc, bx + 35, 285 - 52, bw - 90)
        else:
            f.lab("", desc, bx + 22, 285 - 26, 270)
    f.add([rect(3, 400, 1194, 106, 22, fill=PALE, stroke="none", sw=0)])
    f.lab("", "DB에 걸 수 있는 조건은 제품과 판마다 다르다 / DB에 걸지 않은 규칙은 넣기 전에 검사 프로그램이 맡는다", 600, 420, 1100)
    return f


def f42():
    """42장: 말로 물은 「2호기 쿨러 부품」이 세 갈래로 읽힌다 — 쿨러에 딸린 구성 요소(쿨러 팬), 오일 쿨러가 쓰는 부품의 이름(쿨러 코어),
    그 부품의 품번(CC-2040)."""
    f = Fig("카드_말질문_세갈래.svg")
    hcard(f, 250, 255, 450, 140, "question", name="2호기 쿨러 부품 알려 줘", hot=True)
    spec = ((80, "fan", "쿨러 팬", "쿨러에 딸린 / 구성 요소로 읽으면"),
            (255, "core", "쿨러 코어", "오일 쿨러가 쓰는 / 부품의 이름으로 읽으면"),
            (430, "core", "CC-2040", "그 부품의 / 품번으로 읽으면"))
    for y, kind, nm, desc in spec:
        hcard(f, 900, y, 520, 140, kind, name=nm, desc=desc)
        f.add(arrow([(482, 255 + (y - 255) * 0.25), (632, y)], NAVY, sw=5))
    return f


def f44():
    """44장: 위는 관계 그림 한 줄(설비 → 가진다 → 구성 요소, 클래스 카드), 아래는 같은 모양의 글자 한 줄. 카드는 괄호로,
    화살표는 화살표 모양 그대로 옮긴다. 점선이 위아래 짝을 잇는다."""
    f = Fig("카드_패턴_한줄.svg", dy=20)
    y1 = 110
    hcard(f, 210, y1, 300, 110, "none", name="설비", ring=True, strong=True)
    hcard(f, 990, y1, 300, 110, "none", name="구성 요소", ring=True, strong=True)
    harrow(f, 372, 828, y1, NAVY, label="가진다", small=False)
    y2 = 330
    f.add([rect(30, y2 - 46, 1140, 92, 18, fill=LIGHT, stroke=NAVY, sw=2.5)])
    for x, t in ((210, "(:Asset)"), (600, "-[:HAS_COMPONENT]->"), (990, "(:Component)")):
        f.lab(t, "", x, y2 - 19, 360)
    for x, t in ((210, "노드"), (600, "관계"), (990, "노드")):
        f.add(dash_line(x, y1 + 64 if x != 600 else y1 + 16, x, y2 - 52, BLUE, 3.5, 9, 7))
        f.lab("", t, x + 50, (y1 + 64 + y2 - 52) / 2 - 13, 80)
    return f


def f46():
    """46장: Neo4j Browser 화면 — 위 칸에 쿼리를 넣고, 아래 결과 칸에서 그래프 보기 · 표 보기로 결과를 본다.
    데이터는 화면이 아니라 점선으로 이어진 그래프 DB에 있다."""
    f = Fig("카드_브라우저_화면.svg")
    x0, x1 = 3, 790
    f.add([rect(x0, 4, x1 - x0, 502, 20, fill=WHITE, stroke=NAVY, sw=3), rect(x0, 4, x1 - x0, 46, 20, fill=LIGHT, stroke="none", sw=0),
           line(x0, 50, x1, 50, stroke=NAVY, sw=2)])
    f.add([circle(x0 + 30 + i * 26, 27, 7, fill=GREY, stroke="none", sw=0) for i in range(3)])
    f.add([rect(x0 + 22, 70, x1 - x0 - 44, 64, 12, fill=PALE, stroke=BLUE, sw=4)])
    f.lab("", "쿼리를 넣는 칸", (x0 + x1) / 2, 70 + 32 - 15, 500)
    fy0 = 156
    f.add([rect(x0 + 22, fy0, x1 - x0 - 44, 330, 12, fill=WHITE, stroke=NAVY, sw=2.5)])
    tabs = ((fy0 + 54, "그래프"), (fy0 + 140, "표"))
    for y, t in tabs:
        f.add([rect(x0 + 40, y - 34, 120, 68, 12, fill=PALE if t == "그래프" else LIGHT, stroke=BLUE if t == "그래프" else GREY, sw=3)])
        f.lab(t, "", x0 + 100, y - 19, 110)
    gx, gy = 520, fy0 + 170
    pts = [(gx, gy - 90), (gx - 170, gy + 70), (gx, gy + 100), (gx + 170, gy + 70)]
    for (px, py) in pts[1:]:
        f.add(arrow([(gx, gy - 90 + 30), (px + (gx - px) * 0.18, py - 26)], NAVY, sw=4, size=13))
    for i, (px, py) in enumerate(pts):
        f.add([circle(px, py, 30 if i == 0 else 26, fill=PALE if i == 0 else WHITE, stroke=NAVY, sw=3)])
    hcard(f, 1030, 255, 300, 130, "graph", name="그래프 DB", desc="데이터는 / 여기에 있다", hot=True)
    f.add(dash_line(x1 + 8, 255, 872, 255, BLUE, 4, 10, 8))
    f.lab("", "연결", 834, 255 - 40, 70)
    return f


def run_tag(f: Fig, cx, cy, n):
    f.add([rect(cx - 80, cy - 30, 160, 60, 30, fill=WHITE, stroke=NAVY, sw=2.5)])
    f.lab(f"{n}번째 실행", "", cx, cy - 19, 150)


def f49():
    """49장: 같은 CREATE를 두 번 돌리면 품번이 같은 부품 노드가 둘 생긴다(50장 MERGE와 같은 패턴으로 견준다). 맨 아래는 품번에 유일 제약이 걸려 있으면
    두 번째 실행이 거절된다는 한 줄(41장과 같은 ✕)."""
    f = Fig("카드_CREATE_두번.svg")
    for y, n in ((80, 1), (230, 2)):
        run_tag(f, 90, y, n)
        code_box(f, 470, y, 560, 76, "CREATE (:Part {partNo: 'CC-2040'})")
        f.add(arrow([(758, y), (836, y)], NAVY, sw=5, size=15))
        hcard(f, 1010, y, 330, 104, "core", "부품", "품번 CC-2040", hot=(n == 2))
    f.lab("", "품번이 같은 부품 노드가 둘", 1010, 292, 330)
    f.add([rect(3, 360, 1194, 146, 22, fill=WHITE, stroke=GREY, sw=3)])
    f.add(cross_badge(90, 433, 24))
    f.lab("품번에 유일 제약이 걸려 있으면", "2번째 실행은 DB가 거절하고, 부품 노드는 하나로 남는다", 640, 433 - 30, 1000)
    return f


def f50():
    """50장: 같은 MERGE를 두 번 돌린다. 1번째는 품번 CC-2040인 부품이 없으니 만들고, 2번째는 있으니 찾기만 해 노드는 하나다.
    맨 아래는 찾는 기준에 식별자(품번)를 적는다는 한 줄."""
    f = Fig("카드_MERGE_두번.svg")
    code_box(f, 470, 44, 560, 76, "MERGE (:Part {partNo: 'CC-2040'})")
    lanes = ((170, 1, "없으니 만든다", "품번 CC-2040인 부품이 없다"), (300, 2, "있으니 찾는다", "품번 CC-2040인 부품이 있다"))
    for y, n, t, d in lanes:
        run_tag(f, 90, y, n)
        f.add(arrow([(174, y), (226, y)], NAVY, sw=5, size=15))
        f.add([rect(236, y - 46, 470, 92, 18, fill=PALE if n == 1 else WHITE, stroke=BLUE if n == 1 else NAVY, sw=3)])
        f.lab(t, d, 471, y - 30, 440)
    f.add(arrow([(714, 170), (838, 222)], BLUE, sw=5, size=15))
    f.add(dash_arrow([(714, 300), (838, 250)], NAVY, sw=4.5, size=15))
    hcard(f, 1010, 236, 330, 120, "core", "부품", "품번 CC-2040", hot=True)
    f.lab("", "노드는 하나", 1010, 304, 300)
    f.add([rect(3, 392, 1194, 114, 22, fill=PALE, stroke="none", sw=0)])
    f.lab("MERGE의 패턴에는 식별자를 적는다", "바뀔 수 있는 이름까지 적으면, 이름이 다를 때 같은 부품을 못 찾고 하나 더 만든다", 600, 449 - 30, 1100)
    return f


# ───────────────────────── 새 꼴 견본(「새꼴_*.svg」) ─────────────────────────
# 장마다 답 하나만 남긴다. 카드는 크고 적게 두고, 띠는 정의와 기록 두 층을 가를 때만 쓰며, 카드에 딸린 글은 카드 안 한 덩어리로 둔다.
# 지금 판 그림(카드_*.svg)과 그 함수는 그대로 두고, 여기 함수만 「새꼴_<지금 판 장><나눈 차례>_<이름>.svg」를 쓴다.

def n06a():
    """6장을 나눈 첫 장: 앞에서 「부품」이라 부른 종류 하나가 구성 요소와 부품 두 클래스로 나뉜다. 칸 하나가 클래스 하나이고,
    칸 안의 원판은 그 클래스에 드는 대상의 예, 칸 아래 띠는 그 클래스의 뜻이다."""
    f = Fig("새꼴_06a_구성요소와부품.svg", dy=34)
    hcard(f, 600, 46, 260, 84, "none", name="부품", ring=True, desc="앞에서 부른 종류")
    f.add([path("M 600,92 L 600,112 M 305,112 L 895,112")])
    top, B, bot = 140, 372, 436
    panels = ((20, 570, "구성 요소", "Component", "설비를 이루는 기계 하나하나",
               ((125, "cooler", "오일 쿨러"), (305, "fan", "쿨러 팬"), (485, "pump", "주 펌프"))),
              (610, 570, "부품", "Part", "구성 요소 안에서 닳으면 갈아 끼우는 것",
               ((800, "core", "쿨러 코어"), (990, "bearing", "팬 베어링"))))
    for x0, w, name, eng, meaning, items in panels:
        cx = x0 + w / 2
        f.add(arrow([(cx, 112), (cx, top - 6)], NAVY, sw=SW, size=13))
        f.add(banded(x0, top, w, bot, B, PALE, BLUE, 4))
        f.lab(name, eng, cx, top + 10, 300, strong=True)
        for x, kind, nm in items:
            f.add(disc(x, 262, 46, kind))
            f.lab(nm, "", x, 316, 170)
        f.lab(meaning, "", cx, B + 13, w - 40)
    return f


def n06b():
    """6장을 나눈 둘째 장: 설비 한 대에 딸린 대상 넷을 큰 카드 넷으로. 가운데 줄은 설비 → 구성 요소 → 부품, 센서는 구성 요소 아래에 달려
    화살표가 카드를 돌아가지 않는다."""
    f = Fig("새꼴_06b_설비한대_네클래스.svg", dy=14)
    top, r, w, xs = 10, 58, 230, (200, 600, 1000)
    for x, kind, cls, nm in zip(xs, ("equip", "cooler", "core"), ("설비", "구성 요소", "부품"), ("1호기", "오일 쿨러", "쿨러 코어")):
        bot, dcy = vcard(f, x, top, w, r, kind, cls, nm)
    harrow(f, xs[0] + w / 2 + 10, xs[1] - w / 2 - 10, dcy, label="가진다", small=False)
    harrow(f, xs[1] + w / 2 + 10, xs[2] - w / 2 - 10, dcy, label="쓴다", small=False)
    sy, sh = 420, 110
    hcard(f, 600, sy, 310, sh, "sensor", "센서", "유온 센서")
    y0, y1 = bot + 8, sy - sh / 2 - 8
    f.add(arrow([(600, y0), (600, y1)]))
    f.lab("감시된다", "", 695, (y0 + y1) / 2 - 19, 130)
    return f


def n13a():
    """13장을 나눈 첫 장: 표기 셋을 줄 하나씩. 왼쪽은 표기와 클래스 사이의 관계, 오른쪽은 인스턴스 카드와 화살표이고 화살표를 세면 표기와 같다.
    띠와 설명 줄은 두지 않고, 줄 사이는 가는 선 하나로만 가른다."""
    f = Fig("새꼴_13a_카디널리티_세표기.svg")
    LX, RX, W, H = 560, 1000, 270, 72
    a0, a1 = LX + W / 2 + 10, RX - W / 2 - 10

    def node(x, y, kind, nm):
        hcard(f, x, y, W, H, kind, name=nm)

    def notation(t, d, cy):
        f.lab(t, d, 190, cy - (LH_T + LH_D) / 2 - 6, 340, strong=True)
    for y in (115, 311):
        f.add([line(20, y, 1180, y, stroke=GREY, sw=2)])
    notation("1:1", "설비 → 놓인다 → 설치 위치", 59)
    node(LX, 59, "equip", "1호기"); node(RX, 59, "loc", "1번 자리")
    f.add(arrow([(a0, 59), (a1, 59)]))
    notation("1:N", "구성 요소 → 감시된다 → 센서", 213)
    node(LX, 213, "pump", "주 펌프"); node(RX, 171, "sensor", "토출 압력 센서"); node(RX, 255, "sensor", "유량 센서")
    f.add(arrow([(a0, 205), (a1, 175)]) + arrow([(a0, 221), (a1, 251)]))
    notation("N:M", "공급사 → 공급한다 → 부품", 409)
    node(LX, 367, "supplier", "공급사 1"); node(LX, 451, "supplier", "공급사 2")
    node(RX, 367, "core", "쿨러 코어"); node(RX, 451, "bearing", "팬 베어링")
    f.add(arrow([(a0, 363), (a1, 363)]) + arrow([(a0, 375), (a1, 439)]) + arrow([(a0, 455), (a1, 455)]))
    return f


def n13b():
    """13장을 나눈 둘째 장: 1:1로 정한 관계에 많아야 하나를 넘는 연결 하나(2호기를 같은 자리에 또 잇기)가 ✕로 걸린다.
    맨 아래 한 줄은 표기가 적는 많아야와 함께 적는 적어도."""
    f = Fig("새꼴_13b_많아야를넘는연결.svg", dy=12)
    W, H, L, R_ = 320, 116, 275, 925
    f.lab("1:1", "양쪽 모두 많아야 하나", 600, 0, 320, strong=True)
    hcard(f, L, 150, W, H, "equip", "설비", "1호기")
    hcard(f, R_, 150, W, H, "loc", "설치 위치", "1번 자리")
    harrow(f, L + W / 2 + 10, R_ - W / 2 - 10, 150, label="놓인다", small=False)
    hcard(f, L, 340, W, H, "equip", "설비", "2호기", grey=True)
    xs, ys_, xe, ye = L + W / 2 + 10, 322, R_ - W / 2 - 2, 190
    xm, ym = (xs + xe) / 2, (ys_ + ye) / 2
    f.add(dash_arrow([(xs, ys_), (xe, ye)], GREY, 4.5, 16))
    f.add(cross_badge(xm, ym, 26))
    f.lab("많아야 하나를 넘는다", "", xm + 180, ym + 16, 260)
    f.lab("1:1 · 1:N · N:M은 많아야를 적고, 적어도 몇 개(하나 이상)는 표기 옆에 함께 적는다", "", 600, 440, 1150)
    return f


def n14a():
    """14장을 나눈 첫 장: 오일 쿨러는 설비마다 하나씩(식별자가 다른 카드 셋), 쿨러 코어는 품번마다 하나(카드 하나)로 센다.
    카드 묶음 아래에 세는 기준과 그 기준을 정한 물음을 둔다."""
    f = Fig("새꼴_14a_하나로세기.svg", dy=24)
    CX, W, H, ys = 250, 340, 104, (60, 180, 300)
    for i, y in enumerate(ys):
        hcard(f, CX, y, W, H, "cooler", "구성 요소", "오일 쿨러", desc=f"EQ-0{i + 1}-COOLER")
    KX, kw = 950, 290
    bot, dcy = vcard(f, KX, 50, kw, 62, "core", "부품", "쿨러 코어", hot=True, desc="품번 CC-2040")
    ex, mid = KX - kw / 2 - 12, (50 + bot) / 2
    for y, ty in zip(ys, (mid - 26, mid, mid + 26)):
        f.add(arrow([(CX + W / 2 + 10, y), (ex, ty)]))
    f.lab("쓴다", "", 650, 62, 90)
    f.lab("설비마다 하나씩 센다", "2호기 오일 쿨러의 정비 이력을 묻는다", CX, 372, 440)
    f.lab("품번마다 하나로 센다", "어떤 부품을 주문할지 묻는다 / 쿨러마다 든 실물은 따로 세지 않는다", KX, 372, 440, strong=True)
    return f


def n14b():
    """14장을 나눈 둘째 장: 세는 단위가 카디널리티로 드러난다. 화살표를 세면 위 띠의 표기와 같다(가진다 1:N — 오일 쿨러마다 설비 하나,
    3호기는 오일 쿨러와 쿨러 팬 둘 / 쓴다 N:M — 품번 하나를 오일 쿨러 셋이, 3호기의 오일 쿨러는 쿨러 가스켓도). 아래 칸은 앞 장으로 갔다."""
    f = Fig("새꼴_14b_세는단위와카디널리티.svg", dy=38)
    class_band(f)
    R, h = (178, 260, 342), 68
    for y, nm in zip(R, ("1호기", "2호기", "3호기")):
        hcard(f, XE, y, 200, h, "equip", name=nm)
        hcard(f, XC, y, 220, h, "cooler", name="오일 쿨러")
        f.add(arrow([(XE + 110, y), (XC - 120, y)]))
    fy = 424
    hcard(f, XC, fy, 220, h, "fan", name="쿨러 팬", grey=True)
    f.add(arrow([(200, R[2] + h / 2 + 2), (200, fy), (XC - 120, fy)], GREY))
    cy, ch, kw = 232, 110, 260
    hcard(f, XP, cy, kw, ch, "core", "부품", "쿨러 코어", desc="품번 CC-2040", hot=True)
    gy = 384
    hcard(f, XP, gy, kw, 70, "gasket", name="쿨러 가스켓", grey=True)
    ex = XP - kw / 2 - 10
    for i, y in enumerate(R):
        f.add(arrow([(XC + 120, y - 6 if i == 2 else y), (ex, cy + (y - R[1]) * 0.3)]))
    f.add(arrow([(XC + 120, R[2] + 8), (ex, gy)], GREY))
    return f


def record_row(f: Fig, cy, h, sysname, code, core, *, rev=False, ok=True, why="", x0=20, cw=270, aw=105):
    """22 · 23장의 한 줄: 시스템 이름 · 오일 쿨러 카드 → 쓴다 → 쿨러 코어 카드 · 물음에 나오는지(✓ ✕) · 그 까닭.
    x0은 줄의 왼쪽 끝, cw는 카드 폭, aw는 화살표 길이."""
    f.lab(sysname, "", x0 + 80, cy - 19, 150)
    c0 = x0 + 165
    hcard(f, c0 + cw / 2, cy, cw, h, "cooler", name="오일 쿨러", desc=code)
    x1, x2 = c0 + cw + 10, c0 + cw + 10 + aw
    f.add(arrow([(x2, cy), (x1, cy)] if rev else [(x1, cy), (x2, cy)], BLUE if rev else NAVY))
    f.lab("쓴다", "", (x1 + x2) / 2, cy - 46, 90)
    k0 = x2 + 10
    hcard(f, k0 + cw / 2, cy, cw, h, "core", name="쿨러 코어", desc=core)
    bx = k0 + cw + 45
    f.add((check_badge if ok else cross_badge)(bx, cy, 22))
    if why:
        f.lab("", why, bx + 167, cy - len(why.split(" / ")) * LH_D / 2 - 5, 260)


def n22():
    """22장: 세 시스템이 이름은 같게(오일 쿨러 → 쓴다 → 쿨러 코어) 적었지만 값의 꼴 · 빈칸 · 같은 대상을 가리키는 값 · 방향이 갈린다.
    줄 끝의 ✓ ✕가 맨 아래 물음에 그 오일 쿨러가 나오는지이고, 셋 가운데 하나만 나온다. 칸 바탕 · 시스템 카드 · 아래 상자는 두지 않는다."""
    f = Fig("새꼴_22_의미불일치.svg", dy=38)
    rows = (("설비 대장", "품번 CC-2040 / 교체 주기 12", False, True, "견줄 기준으로 둔 기록"),
            ("부품 목록", "품번 **cc2040** / 교체 주기 **1년**", False, False, "**같은 대상을 가리키는 값**과 / **값의 꼴**이 다르다"),
            ("정비 기록", "품번 **(빈칸)** / 교체 주기 12", True, False, "**관계 방향**이 반대이고 / 품번이 **빠졌다**"))
    for i, (cy, (sysname, core, rev, ok, why)) in enumerate(zip((58, 178, 298), rows)):
        record_row(f, cy, 96, sysname, f"EQ-0{i + 1}-COOLER", core, rev=rev, ok=ok, why=why)
    f.lab("물음 「CC-2040을 쓰는 구성 요소는」", "오일 쿨러 셋 가운데 품번과 방향이 맞게 적힌 하나만 나온다", 600, 372, 1100)
    return f


def n23a():
    """23장을 나눈 첫 장: 왼쪽 파란 카드 하나가 온톨로지 스키마, 오른쪽 세 줄이 그 정의대로 적은 인스턴스 데이터다. 22장의 세 시스템이
    같은 스키마를 보고 적어 같아졌고(품번 CC-2040 · 교체 주기 12 · 같은 방향의 쓴다), 줄 끝이 모두 ✓다(22장의 물음에 셋이 다 나온다)."""
    f = Fig("새꼴_23a_스키마대로적은기록.svg", dy=30)
    ys = (112, 220, 328)
    vcard(f, 143, 120, 210, 50, "sheet", "", "온톨로지 스키마", hot=True, desc="Schema · 공통 정의")
    f.add(dash_line(258, ys[1], 282, ys[1], BLUE, 4, 8, 6) + dash_line(282, ys[0], 282, ys[2], BLUE, 4, 8, 6))
    for y in ys:
        f.add(dash_arrow([(282, y), (318, y)], BLUE, 4, 13, 8, 6))
    f.lab("인스턴스 데이터", "Instance Data · 정의대로 적은 기록", 770, 0, 420, strong=True)
    for i, (cy, sysname) in enumerate(zip(ys, ("설비 대장", "부품 목록", "정비 기록"))):
        record_row(f, cy, 92, sysname, f"EQ-0{i + 1}-COOLER", "품번 CC-2040 / 교체 주기 12", x0=318, cw=250, aw=85)
    f.lab("물음 「CC-2040을 쓰는 구성 요소는」", "오일 쿨러 셋이 다 나온다", 600, 396, 1100)
    return f


def n45a():
    """45장을 나눈 첫 장: 패턴 한 줄(44장의 글자 띠 꼴)과 그 조각의 표기 넷. 조각마다 점선이 아래 카드로 내려가고, 카드 머리가 그 표기 글자다.
    변수 카드만 파랗다(이 장에서 푸는 용어)."""
    f = Fig("새꼴_45a_패턴표기.svg", dy=58)
    y1 = 90
    f.add([rect(150, y1 - 46, 960, 92, 18, fill=LIGHT, stroke=NAVY, sw=2.5)])
    for x, t, w in ((360, "(:Asset {code: 'EQ-02'})", 340), (670, "-[:HAS_COMPONENT]->", 300), (930, "(c:Component)", 220)):
        f.lab(t, "", x, y1 - 19, w)
    ty, th, by = 226, 124, 182
    cards = ((360, ((165, 210, ":Asset", "쌍점 뒤는 **레이블** / 이 노드는 설비", False),
                    (402, 230, "{code: 'EQ-02'}", "중괄호 안은 **속성** / 설비 코드가 EQ-02", False))),
             (670, ((670, 260, ":HAS_COMPONENT", "대괄호 안 쌍점 뒤는 / **관계 유형**", False),)),
             (930, ((980, 320, "c", "괄호 맨 앞은 **변수** / 뒤에서 c.name처럼 다시 부른다", True),)))
    for px, kids in cards:
        xs = [k[0] for k in kids]
        if len(xs) > 1:
            f.add(dash_line(px, y1 + 54, px, by, BLUE, 3.5, 9, 7) + dash_line(min(xs), by, max(xs), by, BLUE, 3.5, 9, 7))
        for cx, w, tok, desc, hot in kids:
            lx = cx if len(xs) > 1 else px
            f.add(dash_line(lx, by if len(xs) > 1 else y1 + 54, lx, ty - 8, BLUE, 3.5, 9, 7))
            f.add(box(cx - w / 2, ty, w, th, hot=hot))
            f.lab(tok, desc, cx, ty + (th - LH_T - 2 * LH_D) / 2 - 5, w - 16, strong=True)
    return f


def n45b():
    """45장을 나눈 둘째 장: 같은 관계를 설비부터 적은 줄과 구성 요소부터 적은 줄. 구성 요소 조각만 파란 칸이고, 줄 아래 파란 화살표가
    두 줄 모두 그 칸을 향한다(화살표 머리는 구성 요소 쪽 그대로)."""
    f = Fig("새꼴_45b_거꾸로적기.svg", dy=28)

    def strip(cy, cap, pieces, chip_x, ax0, ax1):
        f.lab(cap, "", 100, cy - 19, 180)
        f.add([rect(200, cy - 46, 980, 92, 18, fill=LIGHT, stroke=NAVY, sw=2.5),
               rect(chip_x - 130, cy - 30, 260, 60, 14, fill=PALE, stroke=BLUE, sw=4)])
        for x, t, w in pieces:
            f.lab(t, "", x, cy - 19, w)
        f.add(arrow([(ax0, cy + 78), (ax1, cy + 78)], BLUE))
    strip(70, "설비부터", ((400, "(:Asset {code: 'EQ-02'})", 360), (725, "-[:HAS_COMPONENT]->", 280), (1020, "(c:Component)", 240)), 1020, 600, 880)
    strip(280, "구성 요소부터", ((360, "(c:Component)", 240), (655, "<-[:HAS_COMPONENT]-", 280), (980, "(:Asset {code: 'EQ-02'})", 360)), 360, 780, 500)
    f.lab("화살표 머리는 두 줄 모두 구성 요소 쪽이다", "머리를 반대로 적으면 아무것도 찾지 못한다", 690, 392, 700)
    return f


NEW_FIGS = [n06a, n06b, n13a, n13b, n14a, n14b, n22, n23a, n45a, n45b]


# ───────────────────────── 새 꼴 2차 견본(「새꼴2_*.svg」) ─────────────────────────
# 역할마다 A안(한 장에 담은 안)과 B안(같은 역할 안에서 나눈 안, 나눌 까닭이 없으면 구도가 다른 안)을 그린다. 덱 전체에 쓰는 꼴:
#   · 세로 카드 V: 큰 아이콘 원판(반지름 60) 아래에 클래스(작은 파랑)와 이름(굵게). 한 줄에 셋까지는 폭 230, 넷이면 폭 200. 같은 줄은 같은 폭 · 같은 간격.
#   · 가로 카드 H: 화살표를 세어 봐야 해 카드가 많은 장에만. 그 장의 카드는 모두 같은 폭 · 높이이고 이름 한 줄만 얹는다.
#   · 파랑(칸 · 테두리 · 글자)은 그 장의 메시지가 가리키는 답에만, 견주는 짝은 같은 꼴로. 회색은 판단 밖의 곁가지와 걸리는 연결.
#   · 남색 실선 화살표 = 관계, 파란 점선 = 대응(정의 → 기록, 코드 글자 → 풀이), ✓ ✕는 반지름 22 한 가지.
#   · 라벨은 붙는 대상(카드 · 화살표 · 줄)에 줄을 맞추고, 본문 덩어리는 그림 세로 가운데에 둔다(Fig2.fin).
#   · 코드 글자는 고정폭 라벨(이름을 `…`로 감싼다 — deck2pptx.py render_illust)로 얹어 글자 자리를 계산한다.

VR = 60
CW16 = 16 * 1126 / 2048 / 72 * (FW / 12.133)   # 고정폭 16pt 한 글자의 그림 폭(px). Consolas 한 글자는 0.55em, 그림 1200px = 12.133인치


class Fig2(Fig):
    """라벨을 모아 두었다가 fin(위, 아래)에서 본문 덩어리를 그림 세로 가운데로 옮겨 좌표를 낸다."""

    def __init__(self, name):
        super().__init__(name)
        self.raw = []

    def lab(self, title, desc, x, y, w, strong=False, mono=False):
        self.raw.append((f"`{title}`" if mono else title, desc, x, y, w, strong))

    def fin(self, top, bot):
        self.dy = round((FH - top - bot) / 2)
        for a in self.raw:
            Fig.lab(self, *a)
        return self


def V(f, cx, top, kind, cls, name, w=230, **kw):
    """기본 세로 카드. 돌려주는 값: (카드 아래 y, 원판 가운데 y)."""
    return vcard(f, cx, top, w, VR, kind, cls, name, **kw)


def rel(f, x1, x2, y, name, color=NAVY, below="", strong_below=False, lift=46):
    """가로 관계 화살표. 이름은 화살표 위 가운데에, below는 화살표 아래 가운데에 붙인다."""
    f.add(arrow([(x1, y), (x2, y)], color))
    mid, w = (x1 + x2) / 2, abs(x2 - x1) + 16
    f.lab(name, "", mid, y - lift, w)
    if below:
        f.lab(below, "", mid, y + lift - 22, w, strong=strong_below)


def g06A():
    """6장 A안(한 장): 세로 카드 넷을 한 줄에. 구성 요소와 부품 두 카드만 파랗고(이 장에서 푸는 두 클래스), 그 위 묶음 줄이
    앞에서 「부품」이라 부른 것과의 이음새, 카드 아래 굵은 줄이 그 클래스의 뜻이다. 관계 화살표는 두지 않는다."""
    f = Fig2("새꼴2_06A_네클래스.svg")
    xs, top = (150, 450, 750, 1050), 88
    spec = (("equip", "설비", "1호기", False), ("cooler", "구성 요소", "오일 쿨러", True),
            ("core", "부품", "쿨러 코어", True), ("sensor", "센서", "유온 센서", False))
    for x, (kind, cls, nm, hot) in zip(xs, spec):
        bot, _ = V(f, x, top, kind, cls, nm, w=200, hot=hot)
    f.lab("앞에서 부품이라 부른 것", "", 600, 0, 400)
    f.add([path("M 600,40 L 600,56 M 450,56 L 750,56")])
    for x in (450, 750):
        f.add(arrow([(x, 56), (x, top - 6)], NAVY, sw=SW, size=13))
    f.lab("설비를 이루는 기계 하나하나", "", 450, bot + 10, 190)
    f.lab("구성 요소 안에서 닳으면 갈아 끼우는 것", "", 750, bot + 10, 290)
    return f.fin(0, bot + 10 + 5 + 2 * LH_T)


def g06B1(name="새꼴2_06B1_구성요소와부품.svg", dashed=False):
    """6장 B안 첫 장: 앞에서 「부품」이라 부른 것이 두 클래스로 나뉜다. 칸 하나가 클래스 하나(둘 다 같은 꼴 · 같은 파랑),
    칸 안의 원판은 그 클래스에 드는 대상의 예, 칸 아래 띠는 그 클래스의 뜻."""
    f = Fig2(name)
    f.lab("앞에서 부품이라 부른 것", "", 600, 0, 400)
    if dashed:
        f.add(dash_line(600, 40, 600, 58, GREY, 3.5, 8, 6) + dash_line(305, 58, 895, 58, GREY, 3.5, 8, 6))
    else:
        f.add([path("M 600,40 L 600,58 M 305,58 L 895,58")])
    top, B, bot = 90, 332, 398
    panels = ((20, "구성 요소", "Component", "설비를 이루는 기계 하나하나",
               ((125, "cooler", "오일 쿨러"), (305, "fan", "쿨러 팬"), (485, "pump", "주 펌프"))),
              (610, "부품", "Part", "구성 요소 안에서 닳으면 갈아 끼우는 것",
               ((805, "core", "쿨러 코어"), (985, "bearing", "팬 베어링"))))
    for x0, name, eng, meaning, items in panels:
        cx = x0 + 285
        f.add(dash_arrow([(cx, 58), (cx, top - 6)], GREY, 3.5, 13, 8, 6) if dashed else arrow([(cx, 58), (cx, top - 6)], NAVY, sw=SW, size=13))
        f.add(banded(x0, top, 570, bot, B, PALE, BLUE, 4))
        f.lab(name, eng, cx, top + 10, 300, strong=True)
        for x, kind, nm in items:
            f.add(disc(x, top + 126, 50, kind))
            f.lab(nm, "", x, top + 184, 170)
        f.lab(meaning, "", cx, B + 13, 530)
    return f.fin(0, bot)


def g06B2():
    """6장 B안 둘째 장: 설비 한 대에 딸린 대상 넷을 같은 세로 카드 넷으로 한 줄에. 설비 → 구성 요소 → 부품이 이웃하고,
    감시된다만 쿨러 코어 카드 위로 돌아 유온 센서에 닿는다. 파란 카드는 없다(넷이 같은 무게다)."""
    f = Fig2("새꼴2_06B2_네인스턴스.svg")
    xs, top, w = (150, 450, 750, 1050), 100, 200
    spec = (("equip", "설비", "1호기"), ("cooler", "구성 요소", "오일 쿨러"), ("core", "부품", "쿨러 코어"), ("sensor", "센서", "유온 센서"))
    for x, (kind, cls, nm) in zip(xs, spec):
        bot, dcy = V(f, x, top, kind, cls, nm, w=w)
    rel(f, xs[0] + w / 2 + 8, xs[1] - w / 2 - 8, dcy, "가진다")
    rel(f, xs[1] + w / 2 + 8, xs[2] - w / 2 - 8, dcy, "쓴다")
    ry = 48
    f.add(arrow([(xs[1], top - 8), (xs[1], ry), (xs[3], ry), (xs[3], top - 8)]))
    f.lab("감시된다", "", xs[2], ry - 46, 200)
    return f.fin(0, bot)


def rows13(f, hx, hw, LX, RX, W, H, ys, cross_x=None, small=False):
    """13장 표기 세 줄: 왼쪽에 표기와 클래스 사이의 관계, 오른쪽에 같은 꼴의 가로 카드와 화살표(화살표 수 = 표기).
    ys = (1:1 줄, 1:N 위, 1:N 아래, N:M 위, N:M 아래). cross_x를 주면 1:1 줄 오른쪽에 많아야 하나를 넘는 연결 하나를 둔다."""
    a0, a1 = LX + W / 2 + 8, RX - W / 2 - 8

    def node(x, y, kind, nm, **kw):
        if small:
            hs(f, x, y, W, H, kind, nm)
        else:
            hcard(f, x, y, W, H, kind, name=nm, **kw)

    def notation(t, d, cy):
        f.lab(t, d, hx, cy - (LH_T + LH_D) / 2 - 6, hw, strong=True)
    y1, n1, n2, m1, m2 = ys
    xr = (cross_x - W / 2 - 30) if cross_x else 1180
    for y in ((y1 + H / 2 + n1 - H / 2) / 2, (n2 + H / 2 + m1 - H / 2) / 2):
        f.add([line(20, y, xr if y < n1 else 1180, y, stroke=GREY, sw=2)])
    notation("1:1", "설비 → 놓인다 → 설치 위치", y1)
    node(LX, y1, "equip", "1호기"); node(RX, y1, "loc", "1번 자리")
    f.add(arrow([(a0, y1), (a1, y1)]))
    if cross_x:
        node(cross_x, y1, "equip", "2호기", grey=True)
        b0, b1 = cross_x - W / 2 - 8, RX + W / 2 + 8
        f.add(arrow([(b0, y1), (b1, y1)], GREY))
        f.add(cross_badge((b0 + b1) / 2, y1, 17))
        f.lab("많아야 하나를 넘는다", "", cross_x, y1 + H / 2 + 6, W + 20)
    nm_ = (n1 + n2) / 2
    notation("1:N", "구성 요소 → 감시된다 → 센서", nm_)
    node(LX, nm_, "pump", "주 펌프"); node(RX, n1, "sensor", "압력 센서"); node(RX, n2, "sensor", "유량 센서")
    f.add(arrow([(a0, nm_ - 8), (a1, n1 + 4)]) + arrow([(a0, nm_ + 8), (a1, n2 - 4)]))
    notation("N:M", "공급사 → 공급한다 → 부품", (m1 + m2) / 2)
    node(LX, m1, "supplier", "공급사 1"); node(LX, m2, "supplier", "공급사 2")
    node(RX, m1, "core", "쿨러 코어"); node(RX, m2, "bearing", "팬 베어링")
    f.add(arrow([(a0, m1 - 4), (a1, m1 - 4)]) + arrow([(a0, m1 + 8), (a1, m2 - 12)]) + arrow([(a0, m2 + 4), (a1, m2 + 4)]))


def g13A():
    """13장 A안(한 장): 표기 세 줄과, 1:1 줄 오른쪽 끝에 많아야 하나를 넘는 연결 하나(회색 2호기 · 회색 화살표 · ✕)."""
    f = Fig2("새꼴2_13A_카디널리티.svg")
    H = 68
    rows13(f, 140, 270, 410, 730, 230, H, (34, 150, 230, 346, 426), cross_x=1050)
    return f.fin(0, 426 + H / 2)


def g13B1():
    """13장 B안 첫 장: 표기 세 줄만."""
    f = Fig2("새꼴2_13B1_세표기.svg")
    H = 72
    rows13(f, 190, 340, 560, 1000, 250, H, (36, 154, 238, 356, 440))
    return f.fin(0, 440 + H / 2)


def g13B2():
    """13장 B안 둘째 장: 세로 카드 셋 한 줄. 1호기는 1번 자리에 놓여 있고(1:1), 회색 2호기를 같은 자리에 또 이으려는
    회색 화살표가 ✕에 걸린다. 라벨은 모두 두 화살표의 위아래에 붙는다."""
    f = Fig2("새꼴2_13B2_넘는연결.svg")
    xs, top = (190, 600, 1010), 0
    bot, dcy = V(f, xs[0], top, "equip", "설비", "1호기")
    V(f, xs[1], top, "loc", "설치 위치", "1번 자리")
    V(f, xs[2], top, "equip", "설비", "2호기", grey=True)
    rel(f, xs[0] + 123, xs[1] - 123, dcy, "놓인다", below="1:1", strong_below=True, lift=66)
    rel(f, xs[2] - 123, xs[1] + 123, dcy, "놓인다", GREY, below="하나를 넘는다", lift=66)
    f.add(cross_badge((xs[1] + xs[2]) / 2, dcy, 22))
    return f.fin(0, bot)


def grid14(f, caps):
    """14장 격자: 위 띠는 클래스 셋과 관계 유형 둘의 카디널리티, 아래는 같은 꼴의 가로 카드. 화살표를 세면 위 띠의 표기와 같다
    (가진다 1:N — 오일 쿨러마다 설비 하나, 3호기는 오일 쿨러와 쿨러 팬 둘 / 쓴다 N:M — 품번 하나를 오일 쿨러 셋이, 3호기의 오일 쿨러는
    쿨러 가스켓도). 곁가지는 회색이고 파란 카드는 없다. caps면 구성 요소 줄과 부품 줄 아래에 세는 단위를 정한 물음을 붙인다."""
    XE_, XC_, XP_, W, H, ky = 175, 600, 1025, 300, 68, 38
    f.add(band_rect(0, 108, PALE))
    for x, nm in ((XE_, "설비"), (XC_, "구성 요소"), (XP_, "부품")):
        hcard(f, x, ky, W, 64, "none", name=nm, ring=True, strong=True)
    for xa, xb, nm, card in ((XE_, XC_, "가진다", "1:N"), (XC_, XP_, "쓴다", "N:M")):
        f.add(arrow([(xa + W / 2 + 8, ky), (xb - W / 2 - 8, ky)]))
        f.lab(nm, f"**{card}**", (xa + xb) / 2, ky + 8, 140)
    R, fy = (164, 244, 324), 404
    a0, a1, b0, b1 = XE_ + W / 2 + 8, XC_ - W / 2 - 8, XC_ + W / 2 + 8, XP_ - W / 2 - 8
    for y, nm in zip(R, ("1호기", "2호기", "3호기")):
        hcard(f, XE_, y, W, H, "equip", name=nm)
        hcard(f, XC_, y, W, H, "cooler", name="오일 쿨러")
        f.add(arrow([(a0, y), (a1, y)]))
    hcard(f, XC_, fy, W, H, "fan", name="쿨러 팬", grey=True)
    f.add(arrow([(XE_, R[2] + H / 2 + 4), (XE_, fy), (a1, fy)], GREY))
    hcard(f, XP_, R[1], W, H, "core", name="쿨러 코어 CC-2040")
    hcard(f, XP_, fy, W, H, "gasket", name="쿨러 가스켓", grey=True)
    for i, y in enumerate(R):
        f.add(arrow([(b0, y - 8 if i == 2 else y), (b1, R[1] + (i - 1) * 14)]))
    f.add(arrow([(b0, R[2] + 10), (b1, fy)], GREY))
    bot = fy + H / 2
    if caps:
        f.lab("정비 이력 → 설비마다 센다", "", XC_, bot + 12, 330)
        f.lab("주문할 부품 → 품번마다 센다", "", XP_, bot + 12, 330)
        bot += 12 + 5 + LH_T
    return bot


def g14A():
    """14장 A안(한 장): 격자와, 구성 요소 줄 · 부품 줄 아래에 세는 단위를 정한 물음 한 줄씩."""
    f = Fig2("새꼴2_14A_세는단위와카디널리티.svg")
    return f.fin(0, grid14(f, True))


def g14B2():
    """14장 B안 둘째 장: 격자만(세는 단위가 카디널리티로 드러난다)."""
    f = Fig2("새꼴2_14B2_카디널리티.svg")
    return f.fin(0, grid14(f, False))


def g14B1():
    """14장 B안 첫 장: 오일 쿨러는 설비마다 하나씩(카드 셋), 쿨러 코어는 품번마다 하나(카드 하나). 넷 다 같은 가로 카드이고
    파란 카드는 없다(두 세는 법을 같은 무게로 견준다). 쓴다 셋은 한 줄로 모여 쿨러 코어에 닿는다. 줄 아래에 물음과 세는 단위."""
    f = Fig2("새꼴2_14B1_하나로세기.svg")
    W, H, LX, RX, ys = 290, 72, 400, 900, (36, 132, 228)
    for i, y in enumerate(ys):
        f.lab(f"{i + 1}호기", "", LX - W / 2 - 70, y - 19, 110)
        hcard(f, LX, y, W, H, "cooler", name="오일 쿨러")
    hcard(f, RX, ys[1], W, H, "core", name="쿨러 코어 CC-2040")
    bx = 650
    for y in ys:
        f.add([line(LX + W / 2 + 8, y, bx, y, sw=5)])
    f.add([line(bx, ys[0], bx, ys[2], sw=5)])
    rel(f, bx, RX - W / 2 - 8, ys[1], "쓴다")
    cy = ys[2] + H / 2 + 22
    for x, q, t in ((LX - 35, "2호기 오일 쿨러의 정비 이력을 묻는다", "설비마다 하나씩 센다"), (RX, "어떤 부품을 주문할지 묻는다", "품번마다 하나로 센다")):
        f.lab("", q, x, cy, 400)
        f.lab(t, "", x, cy + 26, 400)
    f.lab("", "쿨러마다 든 실물은 따로 세지 않는다", RX, cy + 60, 400)
    return f.fin(0, cy + 60 + 5 + LH_D)


def rec_grid(f, gx, wd, cols, y0, rows, *, schema=False, hdr_y=None):
    """22 · 23장의 기록 격자. 시스템 하나가 줄 하나(같은 꼴의 긴 칸)이고, 칸 안은 왼쪽부터 시스템 이름 · 쓴다의 방향(오일 쿨러와
    쿨러 코어 원판 사이의 화살표) · 쿨러 코어의 품번 · 교체 주기, 칸 밖 오른쪽이 물음에 그 오일 쿨러가 나오는지(✓ ✕)다.
    cols = (시스템, 방향, 원판 벌림, 품번, 주기, 표시)의 x(gx 기준). rows = (이름, 덧말, 품번, 주기, 거꾸로, 나옴, 다른 값 번호들).
    schema면 머리 줄을 파란 칸(온톨로지 스키마)으로 그리고 줄마다 파란 점선을 내린다. 돌려주는 값: (줄 가운데 y들, 아래 y)."""
    cs, cp, sp, c1, c2, cb = (gx + c if i != 2 else c for i, c in enumerate(cols))
    heads = ((cp, "오일 쿨러 → 쓴다 → 쿨러 코어"), (c1, "품번"), (c2, "교체 주기"))
    if schema:
        f.add([rect(gx, y0, wd, 56, 16, fill=PALE, stroke=BLUE, sw=4)])
        for x, t in heads:
            f.lab(t, "", x, y0 + 28 - 19, 340 if x == cp else 130)
        top = y0 + 56 + 44
        for x in (cp, c1, c2):
            f.add(dash_arrow([(x, y0 + 62), (x, top - 8)], BLUE, 4, 13, 8, 6))
        f.lab("", "CC-2040을 쓰는 / 구성 요소", cb, y0 + 28 - 27, 190)
    else:
        for x, t in heads:
            f.lab("", t, x, y0 + 12, 280 if x == cp else 130)
        f.lab("", "CC-2040을 쓰는 / 구성 요소", cb, y0, 190)
        top = y0 + 54
    ys = []
    for i, (name, sub, pno, cyc, rev, ok, hot) in enumerate(rows):
        cy = top + 38 + i * 92
        ys.append(cy)
        f.add([rect(gx, cy - 38, wd, 76, 20, fill=WHITE, stroke=NAVY, sw=3)])
        f.lab(name, sub, cs, cy - (LH_T + (LH_D if sub else 0)) / 2 - 6, 150)
        f.add(disc(cp - sp, cy, 26, "cooler") + disc(cp + sp, cy, 26, "core"))
        ax = (cp - sp + 36, cp + sp - 36)
        f.add(arrow([(ax[1], cy), (ax[0], cy)] if rev else [(ax[0], cy), (ax[1], cy)], BLUE if rev else NAVY))
        f.lab(pno, "", c1, cy - 19, 150, strong=1 in hot)
        f.lab(cyc, "", c2, cy - 19, 130, strong=2 in hot)
        f.add((check_badge if ok else cross_badge)(cb, cy, 22))
    return ys, ys[-1] + 38


ROWS22 = (("설비 대장", "견줄 기준", "CC-2040", "12", False, True, ()),
          ("부품 목록", "", "cc2040", "1년", False, False, (1, 2)),
          ("정비 기록", "", "(빈칸)", "12", True, False, (1,)))
ROWS23 = tuple((n, "", "CC-2040", "12", False, True, ()) for n in ("설비 대장", "부품 목록", "정비 기록"))


def g22A():
    """22장 A안: 기록 격자. 세 줄이 같은 이름(머리 줄)으로 적었지만 기준 줄과 다른 값만 파란 글씨이고, 정비 기록은 화살표가
    파랗게 거꾸로 간다. 줄 끝 ✓ ✕가 물음에 그 오일 쿨러가 나오는지다(셋 가운데 하나)."""
    f = Fig2("새꼴2_22A_의미불일치_격자.svg")
    _, bot = rec_grid(f, 80, 900, (105, 340, 80, 600, 780, 990), 0, ROWS22)
    return f.fin(0, bot)


def g22B():
    """22장 B안(구도가 다른 안): 시스템 하나가 세로 칸 하나. 칸마다 위에서부터 시스템 이름 · 품번과 교체 주기 · 쓴다의 방향,
    칸 아래에 물음에 나오는지(✓ ✕). 기준 칸과 다른 값만 파란 글씨다."""
    f = Fig2("새꼴2_22B_의미불일치_세칸.svg")
    W, hgt = 320, 290
    for cx, (name, sub, pno, cyc, rev, ok, hot) in zip((200, 600, 1000), ROWS22):
        f.add(box(cx - W / 2, 0, W, hgt))
        f.add(disc(cx, 58, 40, "doc"))
        f.lab(name, "", cx, 106, 200)
        for x, h, v, k in ((cx - 75, "품번", pno, 1), (cx + 75, "교체 주기", cyc, 2)):
            f.lab("", h, x, 146, 130)
            f.lab(v, "", x, 182, 140, strong=k in hot)
        py = 246
        f.add(disc(cx - 75, py, 26, "cooler") + disc(cx + 75, py, 26, "core"))
        ax = (cx - 39, cx + 39)
        f.add(arrow([(ax[1], py), (ax[0], py)] if rev else [(ax[0], py), (ax[1], py)], BLUE if rev else NAVY))
        f.add((check_badge if ok else cross_badge)(cx, hgt + 40, 22))
    f.lab("CC-2040을 쓰는 구성 요소를 물으면 셋 가운데 하나만 나온다", "", 600, hgt + 76, 900)
    return f.fin(0, hgt + 76 + 5 + LH_T)


def g23A():
    """23장 A안(한 장): 22장 격자의 머리 줄이 파란 칸(온톨로지 스키마 — 정의만 있고 값이 없다)이 되고, 그 아래 세 줄이
    정의대로 적은 인스턴스 데이터다. 세 줄의 값과 방향이 같아졌고 줄 끝이 모두 ✓다. 왼쪽 글 둘이 두 층의 이름이다."""
    f = Fig2("새꼴2_23A_스키마와기록_격자.svg")
    ys, bot = rec_grid(f, 255, 740, (85, 290, 70, 515, 650, 835), 0, ROWS23, schema=True)
    f.lab("온톨로지 스키마", "Schema / 인스턴스는 없다", 122, 28 - (LH_T + 2 * LH_D) / 2 - 5, 240, strong=True)
    f.lab("인스턴스 데이터", "Instance Data / 정의대로 적은 값과 연결", 122, ys[1] - (LH_T + 2 * LH_D) / 2 - 5, 240, strong=True)
    return f.fin(-8, bot)


def g23B1():
    """23장 B안 첫 장: 왼쪽 파란 세로 카드 하나가 온톨로지 스키마, 거기서 파란 점선이 세 갈래로 오른쪽 격자의 세 줄에 닿는다
    (세 시스템이 같은 정의를 보고 적는다). 세 줄의 값과 방향이 같아졌고 줄 끝이 모두 ✓다."""
    f = Fig2("새꼴2_23B1_스키마대로적은기록.svg")
    f.lab("인스턴스 데이터", "Instance Data", 660, 0, 300, strong=True)
    ys, bot = rec_grid(f, 300, 720, (80, 280, 70, 505, 635, 790), 62, ROWS23)
    vcard(f, 125, ys[1] - 110, 230, VR, "sheet", "", "온톨로지 스키마", hot=True, desc="Schema")
    f.add(dash_line(248, ys[1], 270, ys[1], BLUE, 4, 8, 6) + dash_line(270, ys[0], 270, ys[2], BLUE, 4, 8, 6))
    for y in ys:
        f.add(dash_arrow([(270, y), (294, y)], BLUE, 4, 13, 8, 6))
    return f.fin(0, bot)


P1 = "(:Asset {code: 'EQ-02'})-[:HAS_COMPONENT]->(c:Component)"
P2 = "(c:Component)<-[:HAS_COMPONENT]-(:Asset {code: 'EQ-02'})"


def code_line(f, text, cx, cy, hi="", hi_at=None):
    """고정폭 코드 한 줄(라벨 하나). hi 글자는 파랗게. 돌려주는 값: 조각 글자의 (왼, 오른) x를 내는 함수."""
    x0 = cx - len(text) * CW16 / 2
    shown = text.replace(hi, f"**{hi}**") if hi else text
    if hi_at:
        i, n = hi_at
        shown = text[:i] + "**" + text[i:i + n] + "**" + text[i + n:]
    f.lab(shown, "", cx, cy - 19, len(text) * CW16 * 1.14 + 40, mono=True)

    def span(s, skip=0, n=None):
        i = text.index(s) + skip
        return x0 + i * CW16, x0 + (i + (n or len(s) - skip)) * CW16
    return span


def underline(f, sp, cy):
    f.add([line(sp[0] + 2, cy + 25, sp[1] - 2, cy + 25, stroke=BLUE, sw=4)])


def callouts(f, toks, cy, cards, top, h, w, up=False):
    """코드 글자 조각마다 밑줄을 긋고 파란 점선으로 풀이 카드(같은 폭 · 같은 꼴: 굵은 읽는 법 한 줄 + 그 예 한 줄)에 잇는다.
    up이면 카드가 코드 줄 위에 있다. 조각과 카드 가운데가 거의 같은 자리면 꺾지 않고 곧게 잇는다."""
    lev = (top + h + 26) if up else (top - 26)
    for sp, (cx, name, desc) in zip(toks, cards):
        tx = (sp[0] + sp[1]) / 2
        underline(f, sp, cy)
        ya, yb = (cy - 44, top + h + 8) if up else (cy + 44, top - 8)
        if abs(tx - cx) < 15:
            f.add(dash_line(tx, ya, tx, yb, BLUE, 3.5, 9, 7))
        else:
            f.add(dash_line(tx, ya, tx, lev, BLUE, 3.5, 9, 7) + dash_line(cx, lev, cx, yb, BLUE, 3.5, 9, 7)
                  + dash_line(min(tx, cx), lev, max(tx, cx), lev, BLUE, 3.5, 9, 7))
        f.add(box(cx - w / 2, top, w, h))
        f.lab(name, desc, cx, top + (h - LH_T - LH_D) / 2 - 5, w - 10)


NOTE45 = (("쌍점 뒤는 레이블", "이 노드는 설비"), ("중괄호 안은 속성", "설비 코드가 EQ-02"),
          ("대괄호 안은 관계 유형", "가진다라는 관계"), ("괄호 맨 앞은 변수", "c.name처럼 다시 부른다"))


def g45A():
    """45장 A안(한 장): 위 카드 셋(레이블 · 속성 · 변수)이 파란 점선으로 코드 첫 줄의 그 글자에 닿고, 같은 상자의 둘째 줄이
    구성 요소부터 적은 같은 패턴이다. 두 줄의 화살표 머리(-> · <-)만 파란 글자다."""
    f = Fig2("새꼴2_45A_패턴표기.svg")
    h, c1, c2 = 96, 208, 260
    f.add([rect(170, c1 - 40, 860, 132, 18, fill=LIGHT, stroke=NAVY, sw=2.5)])
    sp = code_line(f, P1, 600, c1, "->")
    code_line(f, P2, 600, c2, "<-")
    callouts(f, (sp(":Asset"), sp("{code: 'EQ-02'}"), sp("(c:", 1, 1)), c1,
             tuple((x, *NOTE45[i]) for x, i in ((300, 0), (600, 1), (900, 3))), 0, h, 280, up=True)
    f.lab("구성 요소부터 적어도 화살표 머리는 구성 요소 쪽이다", "", 600, c2 + 64, 800)
    return f.fin(0, c2 + 64 + 5 + LH_T)


def g45B1():
    """45장 B안 첫 장: 코드 한 줄과, 그 글자 넷에서 파란 점선으로 내려온 같은 꼴의 풀이 카드 넷."""
    f = Fig2("새꼴2_45B1_패턴표기.svg")
    cy, h = 38, 96
    f.add([rect(170, 0, 860, 76, 18, fill=LIGHT, stroke=NAVY, sw=2.5)])
    sp = code_line(f, P1, 600, cy)
    callouts(f, (sp(":Asset"), sp("{code: 'EQ-02'}"), sp(":HAS_COMPONENT"), sp("(c:", 1, 1)), cy,
             tuple((x, *NOTE45[i]) for i, x in enumerate((156, 452, 748, 1044))), 156, h, 280)
    return f.fin(0, 156 + h)


def g45B2(name="새꼴2_45B2_거꾸로적기.svg"):
    """45장 B안 둘째 장: 같은 패턴을 설비부터 적은 줄과 구성 요소부터 적은 줄. 두 줄 모두 화살표 머리만 파란 글자이고,
    머리가 가리키는 (c:Component)에 파란 밑줄을 긋는다."""
    f = Fig2(name)
    for cy, cap, text, hi in ((38, "설비부터", P1, "->"), (160, "구성 요소부터", P2, "<-")):
        f.add([rect(270, cy - 38, 860, 76, 18, fill=LIGHT, stroke=NAVY, sw=2.5)])
        sp = code_line(f, text, 700, cy, hi)
        underline(f, sp("(c:Component)"), cy)
        f.lab(cap, "", 150, cy - 19, 200)
    f.lab("화살표 머리는 두 줄 모두 구성 요소 쪽이다", "머리를 반대로 적으면 아무것도 찾지 못한다", 700, 216, 800)
    return f.fin(0, 216 + 5 + LH_T + LH_D)


NEW_FIGS += [g06A, g06B1, g06B2, g13A, g13B1, g13B2, g14A, g14B1, g14B2, g22A, g22B, g23A, g23B1, g45A, g45B1, g45B2]


# ───────────────────────── 새 꼴 3차 견본(「새꼴3_*.svg」) ─────────────────────────
# 2차에서 고른 안(6 B · 13 B · 14 B · 22 A · 23 B · 45 B)만, 디자인 검토의 그림 · 배치 지적을 고쳐 그린다. 2차와 달라진 꼴:
#   · 회색은 「걸린 연결」 한 뜻으로만 쓴다(13장 둘째 장의 2호기). 여럿 쪽을 보이는 카드와 화살표는 다른 인스턴스와 같은 진한 꼴.
#   · 설명 이음(앞에서 부른 이름 → 두 칸)은 회색 점선으로 그려 관계 화살표(남색 실선)와 가른다.
#   · 카디널리티 표기는 관계 이름과 한 덩어리 · 같은 굵은 크기로 화살표 위에 둔다. ✓ ✕의 뜻은 격자 아래 굵은 한 줄이 말한다.
#   · 쌓인 가로 카드는 낮추고 사이를 25 이상 둔다.

def hs(f, cx, cy, w, h, kind, name, hot=False, desc=""):
    """낮은 가로 카드(카드가 많은 장): 왼쪽 원판(반지름 = 높이 ÷ 2 - 7), 오른쪽에 이름 한 줄(desc가 있으면 그 아래 작은 줄)."""
    x0, r = cx - w / 2, h / 2 - 7
    f.add(box(x0, cy - h / 2, w, h, hot, r=18) + disc(x0 + 10 + r, cy, r, kind, hot))
    tx0 = x0 + 10 + 2 * r + 8
    f.lab(name, desc, (tx0 + cx + w / 2) / 2, cy - 19 - (LH_D / 2 if desc else 0), cx + w / 2 - tx0 - 6)


def g3_06B1(name="새꼴3_06B1_구성요소와부품.svg"):
    """6장 첫 장: 2차 그림에서 갈라 내리는 줄만 회색 점선으로 바꿨다(관계 화살표와 다른 꼴)."""
    return g06B1(name, dashed=True)


def g3_06B2(name="새꼴3_06B2_네인스턴스.svg"):
    """6장 둘째 장: 같은 꼴의 가로 카드 넷(왼쪽 큰 원판, 오른쪽에 클래스와 이름). 윗줄은 설비 → 가진다 → 구성 요소 → 쓴다 → 부품,
    유온 센서는 오일 쿨러 바로 아래에서 감시된다로 세로로 이어진다(1회차 설비 고장 온톨로지 장의 감시된다 꼴)."""
    f = Fig2(name)
    W, H, xs, cy, sy = 290, 112, (190, 600, 1010), 56, 300
    for x, kind, cls, nm in zip(xs, ("equip", "cooler", "core"), ("설비", "구성 요소", "부품"), ("1호기", "오일 쿨러", "쿨러 코어")):
        hcard(f, x, cy, W, H, kind, cls, nm)
    rel(f, xs[0] + W / 2 + 8, xs[1] - W / 2 - 8, cy, "가진다")
    rel(f, xs[1] + W / 2 + 8, xs[2] - W / 2 - 8, cy, "쓴다")
    hcard(f, xs[1], sy, W, H, "sensor", "센서", "유온 센서")
    y0, y1 = cy + H / 2 + 8, sy - H / 2 - 8
    f.add(arrow([(xs[1], y0), (xs[1], y1)]))
    f.lab("감시된다", "", xs[1] + 72, (y0 + y1) / 2 - 19, 110)
    return f.fin(0, sy + H / 2)


def g3_13B1(name="새꼴3_13B1_세표기.svg"):
    """13장 첫 장: 표기 세 줄. 가로 카드를 낮추고(높이 56) 쌓인 카드 사이를 26으로 벌렸다."""
    f = Fig2(name)
    H = 56
    rows13(f, 190, 340, 560, 1000, 250, H, (28, 140, 222, 334, 416), small=True)
    return f.fin(0, 416 + H / 2)


def g3_13B2(name="새꼴3_13B2_넘는연결.svg"):
    """13장 둘째 장: 「놓인다 1:1」을 왼쪽 화살표 위 한 덩어리로. 오른쪽 회색 화살표(걸린 연결)는 위에 관계 이름, 아래에 걸린 까닭."""
    f = Fig2(name)
    xs = (190, 600, 1010)
    bot, dcy = V(f, xs[0], 0, "equip", "설비", "1호기")
    V(f, xs[1], 0, "loc", "설치 위치", "1번 자리")
    V(f, xs[2], 0, "equip", "설비", "2호기", grey=True)
    rel(f, xs[0] + 123, xs[1] - 123, dcy, "놓인다 **1:1**", lift=66)
    rel(f, xs[2] - 123, xs[1] + 123, dcy, "놓인다", GREY, below="하나를 넘는다", lift=66)
    f.add(cross_badge((xs[1] + xs[2]) / 2, dcy, 22))
    return f.fin(0, bot)


def g3_14B1(name="새꼴3_14B1_하나로세기.svg"):
    """14장 첫 장: 같은 가로 카드 넷. 쓴다 화살표 셋이 저마다 쿨러 코어로 모인다(화살표 수를 세는 꼴). 아래 글은 카드 가운데에 맞춘다."""
    f = Fig2(name)
    W, H, LX, RX, ys = 290, 72, 400, 900, (36, 132, 228)
    for i, y in enumerate(ys):
        f.lab(f"{i + 1}호기", "", LX - W / 2 - 70, y - 19, 110)
        hcard(f, LX, y, W, H, "cooler", name="오일 쿨러")
        f.add(arrow([(LX + W / 2 + 8, y), (RX - W / 2 - 8, ys[1] + (i - 1) * 14)]))
    hcard(f, RX, ys[1], W, H, "core", name="쿨러 코어 CC-2040")
    f.lab("쓴다", "", LX + W / 2 + 55, ys[1] - 46, 80)
    cy = ys[2] + H / 2 + 22
    for x, q, t in ((LX, "2호기 오일 쿨러의 정비 이력을 묻는다", "설비마다 하나씩 센다"), (RX, "어떤 부품을 주문할지 묻는다", "품번마다 하나로 센다")):
        f.lab("", q, x, cy, 400)
        f.lab(t, "", x, cy + 26, 400)
    f.lab("", "쿨러마다 든 실물은 따로 세지 않는다", RX, cy + 60, 400)
    return f.fin(0, cy + 60 + 5 + LH_D)


def g3_14B2(name="새꼴3_14B2_카디널리티.svg"):
    """14장 둘째 장: 위 띠와 클래스 카드를 걷고 열 머리(클래스 이름 셋)로 바꿨다. 두 화살표 열 위에 관계 이름과 카디널리티를 한 덩어리로
    굵게 둔다. 카드는 모두 같은 진한 가로 카드이고(쿨러 팬 · 쿨러 가스켓도), 화살표를 세면 표기와 같다."""
    f = Fig2(name)
    XE_, XC_, XP_, W, H = 175, 600, 1025, 300, 60
    for x, nm in ((XE_, "설비"), (XC_, "구성 요소"), (XP_, "부품")):
        f.lab("", f"**{nm}**", x, 4, 200)
    f.lab("가진다 **1:N**", "", (XE_ + XC_) / 2, 0, 200)
    f.lab("쓴다 **N:M**", "", (XC_ + XP_) / 2, 0, 200)
    R, fy = (78, 166, 254), 342
    a0, a1, b0, b1 = XE_ + W / 2 + 8, XC_ - W / 2 - 8, XC_ + W / 2 + 8, XP_ - W / 2 - 8
    for y, nm in zip(R, ("1호기", "2호기", "3호기")):
        hs(f, XE_, y, W, H, "equip", nm)
        hs(f, XC_, y, W, H, "cooler", "오일 쿨러")
        f.add(arrow([(a0, y), (a1, y)]))
    hs(f, XC_, fy, W, H, "fan", "쿨러 팬")
    f.add(arrow([(XE_, R[2] + H / 2 + 4), (XE_, fy), (a1, fy)]))
    hs(f, XP_, R[1], W, H, "core", "쿨러 코어 CC-2040")
    hs(f, XP_, fy, W, H, "gasket", "쿨러 가스켓")
    for i, y in enumerate(R):
        f.add(arrow([(b0, y - 8 if i == 2 else y), (b1, R[1] + (i - 1) * 14)]))
    f.add(arrow([(b0, R[2] + 10), (b1, fy)]))
    return f.fin(0, fy + H / 2)


def rec_grid3(f, gx, y0, rows, foot):
    """22 · 23장의 기록 격자(3차): 시스템 하나가 긴 칸 하나. 칸 안은 왼쪽부터 시스템 이름 · 오일 쿨러(원판과 굵은 식별자) · 쓴다 화살표 ·
    쿨러 코어(원판과 품번 · 교체 주기 값), 칸 밖 오른쪽이 맨 아래 굵은 줄의 물음에 그 오일 쿨러가 나오는지(✓ ✕)다.
    rows = (이름, 덧말, 품번, 주기, 거꾸로, 나옴, 다른 값 번호들) — 다른 값만 파란 글자로 쓴다. 돌려주는 값: (줄 가운데 y들, 아래 y)."""
    cs, ci, cid, a0, a1, ck, cv, wd = tuple(gx + v for v in (80, 172, 290, 385, 465, 505, 655)) + (780,)
    f.lab("", "오일 쿨러 → 쓴다 → 쿨러 코어", (ci + ck) / 2, y0 + 12, 290)
    f.lab("", "품번 · 교체 주기", cv, y0 + 12, 180)
    top, ys = y0 + 54, []
    for i, (name, sub, pno, cyc, rev, ok, hot) in enumerate(rows):
        cy = top + 38 + i * 92
        ys.append(cy)
        f.add([rect(gx, cy - 38, wd, 76, 20, fill=WHITE, stroke=NAVY, sw=3)])
        f.lab(name, sub, cs, cy - (LH_T + (LH_D if sub else 0)) / 2 - 6, 140)
        f.add(disc(ci, cy, 26, "cooler") + disc(ck, cy, 26, "core"))
        f.lab(f"EQ-0{i + 1}-COOLER", "", cid, cy - 19, 180)
        f.add(arrow([(a1, cy), (a0, cy)] if rev else [(a0, cy), (a1, cy)], BLUE if rev else NAVY))
        vals = " · ".join(f"**{v}**" if k in hot else v for k, v in ((1, pno), (2, cyc)))
        f.lab(vals, "", cv, cy - 19, 210)
        f.add((check_badge if ok else cross_badge)(gx + wd + 65, cy, 22))
    bot = ys[-1] + 38
    f.lab(foot, "", gx + (wd + 87) / 2, bot + 14, 900)
    return ys, bot + 14 + 5 + LH_T


def g3_22A(name="새꼴3_22A_의미불일치_격자.svg"):
    """22장: 기록 격자. 세 시스템이 서로 다른 오일 쿨러 셋(식별자)을 같은 이름으로 적었지만, 기준 줄과 다른 값만 파란 글씨이고
    정비 기록은 화살표가 파랗게 거꾸로 간다. 줄 끝 ✓ ✕는 맨 아래 굵은 줄의 물음에 그 오일 쿨러가 나오는지다."""
    f = Fig2(name)
    _, bot = rec_grid3(f, 166, 0, ROWS22, "CC-2040을 쓰는 구성 요소를 물으면 셋 가운데 하나만 나온다")
    return f.fin(0, bot)


def g3_23B1(name="새꼴3_23B1_스키마대로적은기록.svg"):
    """23장 첫 장: 왼쪽 파란 세로 카드 하나가 온톨로지 스키마, 파란 점선이 세 갈래로 오른쪽 격자의 세 줄에 닿는다. 세 줄은 22장과
    같은 꼴이되 값과 방향이 같아졌고 줄 끝이 모두 ✓다(맨 아래 굵은 줄: 셋 다 나온다)."""
    f = Fig2(name)
    gx = 300
    f.lab("인스턴스 데이터", "Instance Data", gx + 390, 0, 300, strong=True)
    ys, bot = rec_grid3(f, gx, 62, ROWS23, "CC-2040을 쓰는 구성 요소를 물으면 셋 다 나온다")
    vcard(f, 135, ys[1] - 110, 210, VR, "sheet", "", "온톨로지 스키마", hot=True, desc="Schema")
    f.add(dash_line(248, ys[1], 270, ys[1], BLUE, 4, 8, 6) + dash_line(270, ys[0], 270, ys[2], BLUE, 4, 8, 6))
    for y in ys:
        f.add(dash_arrow([(270, y), (294, y)], BLUE, 4, 13, 8, 6))
    return f.fin(0, bot)


def g3_45B1(name="새꼴3_45B1_패턴표기.svg"):
    """45장 첫 장: 코드 한 줄 위에 같은 꼴 · 같은 폭의 풀이 카드 셋(레이블 · 속성 · 변수)을 코드 상자 폭 안에 둔다. 레이블과 변수는
    점선이 곧게 내려가고, 속성은 :Asset과 붙어 있어 카드 둘이 나란히 설 자리가 없으므로 한 번만 꺾는다. 변수 c는 파란 글자와 넓힌 밑줄."""
    f = Fig2(name)
    h, cy = 96, 192
    f.add([rect(170, cy - 38, 860, 76, 18, fill=LIGHT, stroke=NAVY, sw=2.5)])
    sp = code_line(f, P1, 600, cy, hi_at=(P1.index("(c:") + 1, 1))
    c0, c1 = sp("(c:", 1, 1)
    toks = (sp(":Asset"), sp("{code: 'EQ-02'}"), ((c0 + c1) / 2 - 17, (c0 + c1) / 2 + 17))
    callouts(f, toks, cy, tuple((x, *NOTE45[i]) for x, i in ((310, 0), (560, 1), (810, 3))), 0, h, 230, up=True)
    return f.fin(0, cy + 38)


def g3_45B2(name="새꼴3_45B2_거꾸로적기.svg"):
    """45장 둘째 장: 2차 그림 그대로."""
    return g45B2(name)


NEW_FIGS += [g3_06B1, g3_06B2, g3_13B1, g3_13B2, g3_14B1, g3_14B2, g3_22A, g3_23B1, g3_45B1, g3_45B2]


# ───────────────────────── 1단원 새 꼴(4~20장을 다시 짠 최종 그림 「카드_*.svg」) ─────────────────────────
# 3차 견본의 꼴을 단원 전체에 쓴다. 카드의 문법:
#   · 인스턴스 카드 = 아이콘 원판 + 클래스(작은 파랑) + 이름(굵게). 값은 이름 아래 굵은 줄이나 「속성 | 값」 줄로.
#   · 클래스 카드 = 빈 테두리 원 + 클래스 이름(파랑). 속성은 그 아래 속성 이름 칸으로.
#   · 파란 점선 = 대응(인스턴스 → 클래스 「속한다」, 이름 → 인스턴스), 속이 빈 삼각 화살촉 = 상속, 회색 = 이어지지 못한 연결.
#   · 물음과 그 결과는 그림 맨 아래 굵은 한 줄로 둔다.

def vc(f, cx, top, w, kind, cls, name, lines=(), hot=False, r=VR):
    """세로 인스턴스 카드. lines = 이름 아래 굵은 값 줄 (글, 파랑인가). 돌려주는 값: (카드 아래 y, 원판 가운데 y)."""
    dcy = top + 18 + r
    y = dcy + r + 14
    if cls:
        f.lab("", f"**{cls}**", cx, y, w - 24)
        y += 28
    f.lab(name, "", cx, y, w - 20)
    y += 32
    for t, blue in lines:
        f.lab(t, "", cx, y, w - 12, strong=blue)
        y += 30
    bot = y + 14
    f.add(box(cx - w / 2, top, w, bot - top, hot) + disc(cx, dcy, r, kind, hot))
    return bot, dcy


def hc(f, cx, cy, w, h, kind, cls, name, extra="", blue=True):
    """가로 인스턴스 카드(왼쪽 큰 원판, 오른쪽에 클래스 · 이름 · 굵은 파란 값 줄)."""
    x0, r = cx - w / 2, min(h / 2 - 12, 42)
    f.add(box(x0, cy - h / 2, w, h, r=20) + disc(x0 + 14 + r, cy, r, kind))
    tx0 = x0 + 14 + 2 * r + 8
    tx, tw = (tx0 + cx + w / 2) / 2, cx + w / 2 - tx0 - 6
    y = cy - (28 + LH_T + (30 if extra else 0)) / 2 - 3
    f.lab("", f"**{cls}**", tx, y, tw)
    f.lab(name, "", tx, y + 28, tw)
    if extra:
        f.lab(extra, "", tx, y + 58, tw, strong=blue)


def chip(f, x, y, w, text, blue=False, h=46):
    """속성 이름 칸 하나."""
    f.add([rect(x, y, w, h, 10, fill=SKY if blue else GREY, stroke="none", sw=0)])
    f.lab(text, "", x + w / 2, y + h / 2 - 19, w - 10)


def prow(f, x, y, w, item, val="", *, hot=False, empty=False, mark=False, edge=False, item_w=124, h=46):
    """「속성 | 값」 한 줄. empty면 값 칸이 빈 점선 칸, mark면 값이 채워졌다는 표시(✓)만 둔다."""
    f.add([rect(x, y, item_w, h, 10, fill=GREY, stroke="none", sw=0)])
    vx, vw = x + item_w + 8, w - item_w - 8
    if empty:
        f.add(dash_rect(vx, y, vw, h, GREY, 3, 8, 6))
    else:
        f.add([rect(vx, y, vw, h, 10, fill=WHITE, stroke=BLUE if hot or edge else NAVY, sw=3 if hot or edge else 2)])
    f.lab(item, "", x + item_w / 2, y + h / 2 - 19, item_w - 6)
    if val:
        f.lab(val, "", vx + vw / 2, y + h / 2 - 19, vw - 6, strong=hot)
    if mark:
        f.add(check_badge(vx + vw / 2, y + h / 2, 13))


def icard(f, cx, top, w, kind, cls, name, rows, r=46, rows_n=0):
    """속성 줄이 있는 인스턴스 카드. rows = prow에 넘길 dict들. 돌려주는 값: (아래 y, 원판 가운데 y, 줄 가운데 y들)."""
    dcy = top + 16 + r
    y = dcy + r + 12
    f.lab("", f"**{cls}**", cx, y, w - 24)
    f.lab(name, "", cx, y + 28, w - 20)
    y += 28 + 32 + 10
    bot = y + max(len(rows), rows_n) * 56 + 6
    f.add(box(cx - w / 2, top, w, bot - top) + disc(cx, dcy, r, kind))
    ys = []
    for row in rows:
        prow(f, cx - w / 2 + 16, y, w - 32, **row)
        ys.append(y + 23)
        y += 56
    return bot, dcy, ys


def ccard(f, cx, top, w, name, chips, hot=False):
    """클래스 카드: 빈 테두리 원과 클래스 이름 한 줄, 그 아래 속성 이름 칸들 (글, 파랑인가). 돌려주는 값: 아래 y."""
    h, x0 = 68 + len(chips) * 56 + 4, cx - w / 2
    f.add(box(x0, top, w, h, hot, r=20) + [circle(x0 + 38, top + 34, 20, fill=WHITE, stroke=NAVY, sw=3)])
    f.lab(name, "", cx + 24, top + 34 - 19, w - 110, strong=True)
    for i, (t, blue) in enumerate(chips):
        chip(f, x0 + 14, top + 68 + i * 56, w - 28, t, blue)
    return top + h


def foot(f, text, y, cx=600, w=1100):
    """그림 맨 아래 굵은 결론 한 줄. 돌려주는 값: 아래 y."""
    f.lab(text, "", cx, y, w)
    return y + 5 + LH_T


def u05():
    """5장: 위 띠는 클래스 셋과 관계 유형 둘(관계 그림에서 원마다 붙인 종류), 아래는 그 클래스에 속하는 인스턴스 카드 셋.
    같은 가로 자리를 파란 점선(속한다)으로 잇는다. 맨 아래 한 줄은 무엇을 하나로 셀지 정하는 기준(뒤 장이 받는다)."""
    f = Fig2("카드_클래스와인스턴스.svg")
    xs, ky, W = (420, 720, 1020), 64, 180
    f.add(band_rect(0, 128, PALE))
    f.lab("클래스", "Class / 같은 성질의 대상을 / 묶은 갈래(앞의 종류)", 160, ky - 52, 300)
    for x, nm in zip(xs, ("설비", "부품", "센서")):
        hcard(f, x, ky, W, 64, "none", name=nm, ring=True, strong=True)
    top = 168
    for x, kind, nm in zip(xs, ("equip", "cooler", "sensor"), ("1호기", "오일 쿨러", "유온 센서")):
        bot, dcy = vc(f, x, top, W, kind, "", nm)
        f.add(dash_arrow([(x, top - 8), (x, ky + 40)], BLUE, 4, 13, 8, 6))
    f.lab("인스턴스", "Instance", 160, dcy - 30, 220, strong=True)
    for (a, b), nm in zip(((0, 1), (1, 2)), ("가진다", "감시된다")):
        rel(f, xs[a] + W / 2 + 8, xs[b] - W / 2 - 8, ky, nm)
        rel(f, xs[a] + W / 2 + 8, xs[b] - W / 2 - 8, dcy, nm)
    return f.fin(0, foot(f, "무엇을 인스턴스 하나로 셀지는 그래프가 답할 질문이 정한다", bot + 14))


def u06a():
    return g3_06B1("카드_구성요소와부품.svg")


def u06b():
    return g3_06B2("카드_설비한대_네인스턴스.svg")


def three_coolers(f, ids=False, r=52):
    """7 · 8장: 같은 기종 설비 세 대의 오일 쿨러(이름이 같은 인스턴스 셋). ids면 이름 아래에 식별자를 파란 굵은 줄로."""
    xs = (220, 600, 980)
    for i, x in enumerate(xs):
        f.lab(f"{i + 1}호기", "", x, 0, 120)
        bot, _ = vc(f, x, 46, 230, "cooler", "구성 요소", "오일 쿨러", ((f"EQ-0{i + 1}-COOLER", True),) if ids else (), r=r)
    return xs, bot


def u07():
    """7장: 이름이 같은 오일 쿨러 셋과, 이름만 적은 정비 기록. 기록에서 세 카드로 가는 줄은 회색 점선(어느 것인지 가리키지 못한다)."""
    f = Fig2("카드_같은이름_기록.svg")
    xs, bot = three_coolers(f)
    ry, by = bot + 106, bot + 30
    hcard(f, 600, ry, 330, 92, "doc", "정비 기록", "오일 쿨러 세척")
    f.add(dash_line(600, ry - 52, 600, by, GREY, 3.5, 8, 6) + dash_line(xs[0], by, xs[2], by, GREY, 3.5, 8, 6))
    for x in xs:
        f.add(dash_arrow([(x, by), (x, bot + 6)], GREY, 3.5, 13, 8, 6))
    return f.fin(0, foot(f, "어느 오일 쿨러의 기록인지 가리키지 못한다", ry + 46 + 22))


def u08a(name="카드_식별자_기록.svg", tail=""):
    """8장 첫 장: 같은 세 카드에 식별자를 붙이면, 식별자를 적은 기록이 그 인스턴스 하나만 가리킨다(남색 화살표 하나)."""
    f = Fig2(name)
    xs, bot = three_coolers(f, ids=True)
    ry = bot + 90
    hcard(f, 600, ry, 380, 92, "doc", "정비 기록", "EQ-02-COOLER 세척")
    f.add(arrow([(600, ry - 52), (600, bot + 8)]))
    end = ry + 46
    if tail:
        end = foot(f, tail, end + 12)
    return f.fin(0, end)


def u08b():
    """8장 둘째 장: 오일 쿨러 인스턴스 카드 하나. 이름과 다른 이름 둘이 「이름 쪽」 한 묶음(왼쪽 묶음 줄)에 들고, 식별자 줄은
    그 아래에 따로 있다. 다른 이름 두 줄만 파랗다(이 장에서 푸는 용어)."""
    f = Fig2("카드_다른이름.svg")
    cx, w, r = 620, 520, 46
    dcy, y = 16 + r, 16 + 2 * r + 12
    rows = (("이름", "오일 쿨러", False), ("다른 이름", "쿨러", True), ("다른 이름", "열교환기", True))
    y0 = y + 28 + 12
    bot = y0 + 3 * 56 + 14 + 56 + 6
    f.add(box(cx - w / 2, 0, w, bot) + disc(cx, dcy, r, "cooler"))
    f.lab("", "**구성 요소**", cx, y, w - 24)
    for i, (item, val, hot) in enumerate(rows):
        prow(f, cx - w / 2 + 16, y0 + i * 56, w - 32, item, val, hot=hot, item_w=140)
    y1 = y0 + 3 * 56 - 10
    bx = cx - w / 2 - 22
    f.add([path(f"M {bx + 12},{y0} L {bx},{y0} L {bx},{y1} L {bx + 12},{y1}", sw=3)])
    f.lab("이름 쪽", "", bx - 70, (y0 + y1) / 2 - 19, 120)
    prow(f, cx - w / 2 + 16, y0 + 3 * 56 + 14, w - 32, "식별자", "EQ-02-COOLER", item_w=140)
    return f.fin(0, foot(f, "어느 이름으로 불러도 오일 쿨러이고, 그중 하나를 가리키는 것은 식별자다", bot + 16))


def u09():
    """9장: 왼쪽 클래스 카드는 속성 이름만 정하고, 오른쪽 인스턴스 카드가 그 속성에 값을 채운다(파란 값 칸 = 속성값)."""
    f = Fig2("카드_속성값_채우기.svg")
    bot, dcy, ys = icard(f, 920, 0, 400, "sensor", "센서", "유온 센서",
                         ({"item": "단위", "val": "℃", "hot": True}, {"item": "측정 범위", "val": "0~120 ℃", "hot": True}))
    cb = ccard(f, 280, ys[0] - 23 - 68, 360, "센서", (("단위", False), ("측정 범위", False)))
    my = (ys[0] + ys[1]) / 2
    rel(f, 280 + 180 + 10, 920 - 200 - 10, my, "속성값을 채운다")
    f.lab("클래스는 항목만 정한다", "", 280, bot + 12, 360)
    f.lab("값은 노드 안 칸에 적힌다", "", 920, bot + 12, 400)
    return f.fin(0, bot + 12 + 5 + LH_T)


Q10 = "이 오일 쿨러를 재는 센서의 단위를 물으면 "


def u10():
    """10장: 오일 쿨러 카드에 식별자 칸과, 센서 이름을 글자로 적은 칸. 그 칸에서 유온 센서 카드의 단위 칸으로 가는 길은 회색 화살표가
    ✕에 걸리고, 걸린 까닭 둘이 ✕ 위아래에 붙는다."""
    f = Fig2("카드_글자센서_끊김.svg")
    bot, _, ya = icard(f, 230, 0, 380, "cooler", "구성 요소", "오일 쿨러", ({"item": "식별자", "val": "EQ-02-COOLER"}, {"item": "센서", "val": "유온 센서"}))
    icard(f, 970, 0, 380, "sensor", "센서", "유온 센서", ({"item": "측정 범위", "val": "0~120 ℃"}, {"item": "단위", "val": "℃"}))
    y = ya[1]
    f.add(arrow([(430, y), (770, y)], GREY) + cross_badge(600, y, 22))
    f.lab("건너갈 길이 없다", "", 600, y - 64, 330)
    f.lab("칸에 적힌 것은 글자다", "", 600, y + 27, 330)
    return f.fin(0, foot(f, Q10 + "찾지 못한다", y + 96))


def u11():
    """11장: 앞 장과 같은 두 카드에서 센서 칸만 빠지고 감시된다 화살표가 생겼다. 화살표가 객체 간 관계, 파란 테두리 칸들이 데이터 속성이고
    (가는 남색 지시선), 화살표를 건너 단위 칸(파란 값)에서 답을 읽는다."""
    f = Fig2("카드_속성과관계.svg")
    bot, dcy, ya = icard(f, 230, 0, 380, "cooler", "구성 요소", "오일 쿨러", ({"item": "식별자", "val": "EQ-02-COOLER", "edge": True},), rows_n=2)
    _, _, yb = icard(f, 970, 0, 380, "sensor", "센서", "유온 센서", ({"item": "측정 범위", "val": "0~120 ℃", "edge": True}, {"item": "단위", "val": "℃", "hot": True}))
    rel(f, 430, 770, dcy, "감시된다")
    f.lab("객체 간 관계", "Object Property", 600, dcy + 18, 300, strong=True)
    y = ya[0]
    f.lab("데이터 속성", "Data Property", 600, y - (LH_T + LH_D) / 2 - 6, 200, strong=True)
    f.add([line(426, y, 520, y, sw=2), line(680, y, 774, y, sw=2)])
    return f.fin(0, foot(f, Q10 + "℃가 나온다", yb[1] + 96))


def u12():
    """12장: 위 띠는 클래스 둘과 그 사이에 한 번 정한 관계 유형(파란 화살표와 이름, 그 아래 용어), 아래 세 줄은 세 설비의 인스턴스가
    같은 이름 · 같은 방향으로 이어진 관계."""
    f = Fig2("카드_관계유형_세줄.svg")
    LX, RX, W, ky = 540, 1000, 280, 50
    f.add(band_rect(0, 132, PALE))
    f.lab("클래스", "Class", 190, ky - 30, 220)
    for x, nm in ((LX, "구성 요소"), (RX, "센서")):
        hcard(f, x, ky, W, 64, "none", name=nm, ring=True, strong=True)
    a0, a1 = LX + W / 2 + 8, RX - W / 2 - 8
    f.add(arrow([(a0, ky), (a1, ky)], BLUE))
    f.lab("감시된다", "", (a0 + a1) / 2, ky - 46, a1 - a0 + 16, strong=True)
    f.lab("관계 유형", "Relationship Type", (a0 + a1) / 2, ky + 12, a1 - a0 + 16, strong=True)
    ys = (196, 288, 380)
    for i, y in enumerate(ys):
        hs(f, LX, y, W, 64, "cooler", "오일 쿨러", desc=f"{i + 1}호기")
        hs(f, RX, y, W, 64, "sensor", "유온 센서", desc=f"{i + 1}호기")
        rel(f, a0, a1, y, "감시된다")
    f.lab("인스턴스", "Instance", 190, ys[1] - 30, 220)
    return f.fin(0, foot(f, "한 번 정해 두면 적는 사람마다 이름이 갈리지 않아, 세 설비의 연결을 한 번에 모아 묻는다", ys[2] + 32 + 14))


def u13a():
    return g3_13B1("카드_카디널리티_표기셋.svg")


def u13b():
    return g3_13B2("카드_카디널리티_넘는연결.svg")


def u14a():
    return g3_14B1("카드_세는단위.svg")


def u14b():
    return g3_14B2("카드_세는단위_카디널리티.svg")


def part_blank(f, cx, top, w):
    """16장: 자기 속성 셋을 구성 요소 하나에 둔 오일 쿨러 인스턴스. 냉각 용량만 채워지고 두 칸은 빈 점선 칸. 돌려주는 값: 아래 y."""
    bot, _, _ = icard(f, cx, top, w, "cooler", "구성 요소", "오일 쿨러",
                      ({"item": "냉각 용량", "mark": True}, {"item": "토출 유량", "empty": True}, {"item": "회전수", "empty": True}))
    return bot


def part_repeat(f, xs, top, w):
    """16장: 펌프 · 쿨러 · 팬을 따로 나눈 클래스 카드 셋. 셋이 거듭 적은 공통 속성 칸만 파랗다. 돌려주는 값: 아래 y."""
    for x, nm, own in zip(xs, ("펌프", "쿨러", "팬"), ("토출 유량", "냉각 용량", "회전수")):
        bot = ccard(f, x, top, w, nm, (("식별자 · 이름", True), (own, False)))
    return bot


def u16a():
    """16장 첫 장: 왼쪽 클래스 카드 하나에 자기 속성 셋을 모두 두면, 오른쪽 오일 쿨러 인스턴스에 쓰지 않는 빈 칸 둘이 붙는다."""
    f = Fig2("카드_자기속성_빈칸.svg")
    bot = part_blank(f, 900, 0, 400)
    ccard(f, 290, bot - 6 - 3 * 56 - 68, 360, "구성 요소", (("냉각 용량", False), ("토출 유량", False), ("회전수", False)))
    rel(f, 290 + 190, 900 - 210, bot - 6 - 56 * 1.5 - 5, "인스턴스를 적으면")
    return f.fin(0, foot(f, "오일 쿨러에는 쓰지 않는 칸 둘이 빈 채로 붙는다", bot + 14))


def u16b():
    """16장 둘째 장: 클래스를 따로 나눈 카드 셋. 파란 칸(공통 속성)이 세 번 되풀이된다."""
    f = Fig2("카드_자기속성_거듭적기.svg")
    bot = part_repeat(f, (220, 600, 980), 0, 300)
    return f.fin(0, foot(f, "공통 속성을 클래스마다 거듭 적는다", bot + 14))


def tree17(f, cx, top, w=270, inst=False):
    """17장: 상위 클래스 카드(공통 속성, 파란 칸) 아래에 하위 클래스 카드 셋(자기 속성). 속이 빈 삼각 화살촉이 상속.
    inst면 쿨러 아래에 오일 쿨러 인스턴스를 파란 점선(속한다)으로 단다. 돌려주는 값: (하위 카드 가운데 x들, 아래 y)."""
    xs = (cx - 300, cx, cx + 300)
    b1 = ccard(f, cx, top, w, "구성 요소", (("식별자 · 이름", True),), hot=True)
    t2 = b1 + 124
    for x, nm, own in zip(xs, ("펌프", "쿨러", "팬"), ("토출 유량", "냉각 용량", "회전수")):
        b2 = ccard(f, x, t2, w, nm, ((own, False),))
        f.add([line(x, t2 - 6, x, b1 + 94, sw=4)])
    f.add([line(xs[0], b1 + 94, xs[2], b1 + 94, sw=4), line(cx, b1 + 94, cx, b1 + 26, sw=4)] + tri_head(cx, b1 + 6, -math.pi / 2, NAVY, 22))
    if inst:
        iy = b2 + 86
        hcard(f, cx, iy, w + 20, 84, "cooler", "쿨러", "오일 쿨러")
        f.add(dash_arrow([(cx, iy - 50), (cx, b2 + 8)], BLUE, 4, 13, 8, 6))
        f.lab("속한다", "", cx + 62, (iy - 42 + b2) / 2 - 19, 90)
        b2 = iy + 42
    return xs, b1, b2


def u17a():
    """17장 첫 장: 클래스 계층. 왼쪽에 줄마다 상위 클래스 · 하위 클래스, 줄기 옆에 상속, 맨 아래에 클래스 계층."""
    f = Fig2("카드_상속_나무.svg")
    xs, b1, b2 = tree17(f, 700, 0)
    f.lab("상위 클래스", "Superclass", 150, b1 / 2 - 30, 240, strong=True)
    f.lab("하위 클래스", "Subclass", 150, (b1 + 124 + b2) / 2 - 30, 240, strong=True)
    f.lab("상속", "Inheritance", 700 + 80, b1 + 28, 130, strong=True)
    f.lab("클래스 계층", "Class Hierarchy · 클래스가 클래스 아래로 이어진 모양", 700, b2 + 14, 600, strong=True)
    return f.fin(0, b2 + 14 + 5 + LH_T + LH_D)


def u17b():
    """17장 둘째 장: 오일 쿨러 인스턴스는 쿨러에 속하고, 쿨러는 구성 요소를 상속한다. 인스턴스의 두 칸이 두 클래스의 칸과 같은 색이다
    (파랑 = 구성 요소에게 물려받은 공통 속성, 회색 = 쿨러의 자기 속성)."""
    f = Fig2("카드_상속_인스턴스.svg")
    x0, x1, x2, w = 190, 600, 1010, 280
    dcy, y = 62, 62 + 46 + 12
    f.lab("", "**쿨러**", x0, y, w - 24)
    f.lab("오일 쿨러", "", x0, y + 28, w - 20)
    bot = y + 126 + 46 + 14
    f.add(box(x0 - w / 2, 0, w, bot) + disc(x0, dcy, 46, "cooler"))
    chip(f, x0 - w / 2 + 14, y + 70, w - 28, "식별자 · 이름", True)
    chip(f, x0 - w / 2 + 14, y + 126, w - 28, "냉각 용량")

    my = bot / 2
    ccard(f, x1, my - 64, w, "쿨러", (("냉각 용량", False),))
    ccard(f, x2, my - 64, w, "구성 요소", (("식별자 · 이름", True),))
    a0, a1 = x0 + w / 2 + 8, x1 - w / 2 - 8
    f.add(dash_arrow([(a0, my), (a1, my)], BLUE, 4, 13, 8, 6))
    f.lab("속한다", "", (a0 + a1) / 2, my - 46, 130)
    b0, b1 = x1 + w / 2 + 8, x2 - w / 2 - 8
    f.add([line(b0, my, b1 - 22, my, sw=4)] + tri_head(b1, my, 0, NAVY, 22))
    f.lab("상속", "", (b0 + b1) / 2, my - 46, 130)
    return f.fin(0, foot(f, "오일 쿨러는 쿨러의 인스턴스이면서 구성 요소의 인스턴스다", bot + 14))


def u18():
    """18장: 위 띠는 클래스(설비 → 가진다 → 구성 요소, 쿨러 ▷ 구성 요소), 아래는 인스턴스(2호기 → 가진다 → 오일 쿨러).
    세 연결에 ① ② ③과 메시지의 낱말을 붙이고, 그 연결을 무엇으로 적는지는 작은 파란 글로 둔다."""
    f = Fig2("카드_세연결.svg")
    xs, W, H, ky, iy = (250, 640, 1030), 230, 72, 78, 290
    f.add(band_rect(0, 132, PALE))
    f.lab("", "**클래스**", 78, ky - 13, 110)
    f.lab("", "**인스턴스**", 78, iy - 13, 110)
    for x, nm in zip(xs, ("설비", "구성 요소", "쿨러")):
        hcard(f, x, ky, W, 64, "none", name=nm, ring=True, strong=True)
    rel(f, xs[0] + W / 2 + 8, xs[1] - W / 2 - 8, ky, "가진다")
    b0, b1 = xs[2] - W / 2 - 8, xs[1] + W / 2 + 8
    f.add([line(b0, ky, b1 + 22, ky, sw=4)] + tri_head(b1, ky, math.pi, NAVY, 22))
    f.lab("① 한 종류다", "**상속**", (b0 + b1) / 2, ky - 66, 166)
    hcard(f, xs[0], iy, W, H, "equip", name="2호기")
    hcard(f, xs[2], iy, W, H, "cooler", name="오일 쿨러")
    a0, a1 = xs[0] + W / 2 + 8, xs[2] - W / 2 - 8
    f.add(arrow([(a0, iy), (a1, iy)]))
    f.lab("③ 가진다", "일부다 · **관계**", (a0 + a1) / 2, iy - 68, 220)
    f.add(dash_arrow([(xs[2], iy - H / 2 - 8), (xs[2], ky + 40)], BLUE, 4, 13, 8, 6))
    f.lab("② 속한다", "**인스턴스**", xs[2] + 82, (iy - H / 2 + ky + 32) / 2 - 30, 130)
    return f.fin(0, iy + H / 2)


def u19():
    """19장: 같은 가로 카드 다섯. 파란 화살표가 물음을 따라간 길(① 가진다 → ② 쓴다), 쿨러 코어 카드의 파란 줄이 읽은 속성값(③ 품번).
    2호기가 가진 다른 구성 요소 둘은 같은 꼴의 카드로 아래에 두고 남색 화살표로 잇는다."""
    f = Fig2("카드_품번_길.svg")
    xs, W, H, ys = (160, 600, 1040), 300, 116, (58, 198, 338)
    hc(f, xs[0], ys[0], W, H, "equip", "설비", "2호기")
    hc(f, xs[1], ys[0], W, H, "cooler", "구성 요소", "오일 쿨러")
    hc(f, xs[2], ys[0], W, H, "core", "부품", "쿨러 코어", "③ 품번 CC-2040")
    hc(f, xs[1], ys[1], W, H, "fan", "구성 요소", "쿨러 팬")
    hc(f, xs[1], ys[2], W, H, "pump", "구성 요소", "주 펌프")
    rel(f, xs[0] + W / 2 + 8, xs[1] - W / 2 - 8, ys[0], "① 가진다", BLUE)
    rel(f, xs[1] + W / 2 + 8, xs[2] - W / 2 - 8, ys[0], "② 쓴다", BLUE)
    for y in ys[1:]:
        f.add(arrow([(xs[0], ys[0] + H / 2 + 6), (xs[0], y), (xs[1] - W / 2 - 8, y)]))
    return f.fin(0, foot(f, "2호기 오일 쿨러에 갈아 끼울 부품의 품번을 물으면 CC-2040이 나온다", ys[2] + H / 2 + 14))


def u20():
    """20장: 14장 둘째 장과 같은 격자에 4호기 줄을 더했다. 더한 카드 둘만 파랗고 그 안에 식별자를 함께 적는다. 새 오일 쿨러도
    있던 쿨러 코어로 이어진다. 열 머리(클래스와 관계 유형)는 그대로다."""
    f = Fig2("카드_설비한대더.svg")
    XE_, XC_, XP_, W, H = 175, 600, 1025, 300, 64
    for x, nm in ((XE_, "설비"), (XC_, "구성 요소"), (XP_, "부품")):
        f.lab("", f"**{nm}**", x, 4, 200)
    f.lab("가진다", "", (XE_ + XC_) / 2, 0, 120)
    f.lab("쓴다", "", (XC_ + XP_) / 2, 0, 120)
    R = (78, 166, 254, 342)
    a0, a1, b0, b1 = XE_ + W / 2 + 8, XC_ - W / 2 - 8, XC_ + W / 2 + 8, XP_ - W / 2 - 8
    cy = (R[1] + R[2]) / 2
    for i, y in enumerate(R):
        new = i == 3
        hs(f, XE_, y, W, H, "equip", f"{i + 1}호기", hot=new, desc="**EQ-04**" if new else "")
        hs(f, XC_, y, W, H, "cooler", "오일 쿨러", hot=new, desc="**EQ-04-COOLER**" if new else "")
        f.add(arrow([(a0, y), (a1, y)]) + arrow([(b0, y), (b1, cy + (i - 1.5) * 12)]))
    hs(f, XP_, cy, W, H, "core", "쿨러 코어 CC-2040")
    return f.fin(0, foot(f, "4호기 오일 쿨러에 갈아 끼울 부품의 품번을 물어도 같은 길로 CC-2040이 나온다", R[3] + H / 2 + 16))


# 다른 안(검토자가 고른다): 나눈 장을 한 장에 담은 배치

def alt08():
    """8장 다른 안(한 장): 식별자 그림 아래에 다른 이름을 굵은 한 줄로 둔다."""
    return u08a("다른안_08_식별자와다른이름.svg", "쿨러 · 열교환기 같은 다른 이름은 이름 쪽에 두고 식별자로 쓰지 않는다")


def alt16():
    """16장 다른 안(한 장): 왼쪽에 빈 칸이 붙은 인스턴스 하나, 오른쪽에 공통 속성을 거듭 적은 클래스 셋."""
    f = Fig2("다른안_16_두길.svg")
    bot = part_blank(f, 170, 0, 320)
    b2 = part_repeat(f, (520, 790, 1060), bot - 184, 250)
    f.lab("빈 칸이 붙는다", "", 170, bot + 12, 320)
    f.lab("공통 속성을 거듭 적는다", "", 790, bot + 12, 500)
    return f.fin(0, bot + 12 + 5 + LH_T)


def alt17():
    """17장 다른 안(한 장): 클래스 계층 아래에 오일 쿨러 인스턴스를 달아 한 장에."""
    f = Fig2("다른안_17_상속한장.svg")
    xs, b1, b2 = tree17(f, 670, 0, inst=True)
    f.lab("상위 클래스", "Superclass", 150, b1 / 2 - 30, 240, strong=True)
    f.lab("하위 클래스", "Subclass", 150, b1 + 110 + 64 - 30, 240, strong=True)
    f.lab("상속(Inheritance)", "", 670 + 130, b1 + 26, 240, strong=True)
    f.lab("쿨러이면서 구성 요소", "하위 클래스의 인스턴스는 / 상위 클래스의 인스턴스이기도 하다", 980, b2 - 84, 330)
    return f.fin(0, b2)


U1_FIGS = [u05, u06a, u06b, u07, u08a, u08b, u09, u10, u11, u12, u13a, u13b, u14a, u14b, u16a, u16b, u17a, u17b, u18, u19, u20,
           alt08, alt16, alt17]
NEW_FIGS += U1_FIGS


# ───────────────────────── 2단원 새 꼴(21~34장을 다시 짠 최종 그림 「카드_*.svg」) ─────────────────────────
# 1단원의 카드 문법을 그대로 잇는다. 이 단원에서 더한 꼴:
#   · 정의 카드 = 머리(클래스면 빈 테두리 원과 파란 이름) + 「칸 | 정한 것」 줄. 스키마에 적는 것은 늘 이 꼴.
#   · 기록 줄 = 아이콘 원판 · 이름 · 적은 값, 줄 끝에 ✓ ✕(정의를 지켰는가). 정의 카드에서 기록 줄로 파란 점선이 간다.

def dcard(f, cx, top, w, name, rows, ring=True, item_w=124):
    """정의 카드. rows = prow에 넘길 dict들. 돌려주는 값: (아래 y, 줄 가운데 y들)."""
    h, x0 = 68 + len(rows) * 56 + 4, cx - w / 2
    f.add(box(x0, top, w, h, r=20))
    if ring:
        f.add([circle(x0 + 38, top + 34, 20, fill=WHITE, stroke=NAVY, sw=3)])
        f.lab(name, "", cx + 24, top + 15, w - 110, strong=True)
    else:
        f.lab(name, "", cx, top + 15, w - 30)
    ys = []
    for i, row in enumerate(rows):
        prow(f, x0 + 14, top + 68 + i * 56, w - 28, item_w=item_w, **row)
        ys.append(top + 68 + i * 56 + 23)
    return top + h, ys


def rrow(f, x0, cy, w, kind, name, val, ok, nw=120, h=68):
    """기록 한 줄: 아이콘 원판 · 이름 · 적은 값(정의와 다른 값은 **파랑**), 줄 끝에 ✓ ✕."""
    f.add(box(x0, cy - h / 2, w, h, r=18) + disc(x0 + 12 + 24, cy, 24, kind))
    f.lab(name, "", x0 + 68 + nw / 2, cy - 19, nw)
    f.lab(val, "", x0 + 68 + nw + (w - 76 - nw) / 2, cy - 19, w - 76 - nw)
    f.add((check_badge if ok else cross_badge)(x0 + w + 40, cy, 22))


def fan_out(f, x0, x1, ys, my):
    """정의 카드(오른쪽 끝 x0, 가운데 y my)에서 기록 줄들(왼쪽 끝 x1)로 가는 파란 점선 갈래."""
    bx = (x0 + x1) / 2
    f.add(dash_line(x0 + 8, my, bx, my, BLUE, 4, 8, 6) + dash_line(bx, min(ys + [my]), bx, max(ys + [my]), BLUE, 4, 8, 6))
    for y in ys:
        f.add(dash_arrow([(bx, y), (x1 - 6, y)], BLUE, 4, 13, 8, 6))


def u2_22():
    return g3_22A("카드_의미불일치_격자.svg")


def u2_23():
    return g3_23B1("카드_스키마대로_적은기록.svg")


def u2_24():
    """24장: 왼쪽 새 대상 둘이 오른쪽 클래스 정의 카드 둘(이름 + 의미 한 문장)로 간다. 의미 칸이 파랗다(이 장의 답)."""
    f = Fig2("카드_클래스정의_의미문장.svg")
    ys = (64, 232)
    for y, kind, nm, cls, mean in ((ys[0], "motor", "구동 모터", "구성 요소", "설비를 이루는 기계 하나하나"),
                                   (ys[1], "seal", "펌프 축 씰", "부품", "구성 요소 안에서 닳으면 갈아 끼우는 것")):
        hcard(f, 200, y, 320, 100, kind, "새 대상", nm)
        dcard(f, 870, y - 64, 580, cls, ({"item": "의미", "val": mean, "hot": True},), item_w=84)
        f.add(arrow([(368, y), (572, y)]))
    return f.fin(0, foot(f, "의미 문장에 대어 보고 클래스를 고른다", ys[1] + 64 + 14))


def u2_25():
    """25장: 왼쪽 정의 카드가 교체 주기의 자료형을 수로 정한다. 오른쪽 기록 둘 가운데 수로 적은 쪽만 ✓, 글자로 적은 쪽(파란 값)은 ✕."""
    f = Fig2("카드_자료형_견주기.svg")
    ys = [44, 132]
    bot, dy_ = dcard(f, 228, 88 - 64, 370, "부품", ({"item": "교체 주기", "val": "자료형 **수** · 개월"},))
    rrow(f, 528, ys[0], 560, "core", "쿨러 코어", "교체 주기 12", True)
    rrow(f, 528, ys[1], 560, "core", "쿨러 코어", "교체 주기 **1년**", False)
    fan_out(f, 413, 528, ys, 88)
    return f.fin(0, foot(f, "교체 주기가 6개월보다 긴 부품을 물으면 수로 적은 값만 견줄 수 있다", ys[1] + 34 + 16))


def u2_26():
    """26장: 왼쪽 정의 카드가 단위는 필수, 측정 범위는 선택으로 정한다. 필수 속성이 빈 기록은 ✕, 선택 속성이 빈 기록은 ✓."""
    f = Fig2("카드_필수선택_빈칸.svg")
    ys = [50, 138]
    dcard(f, 213, 94 - 92, 340, "센서", ({"item": "단위", "val": "필수", "hot": True}, {"item": "측정 범위", "val": "선택", "hot": True}))
    rrow(f, 468, ys[0], 620, "sensor", "유온 센서", "단위 **(빈칸)** · 측정 범위 0~120 ℃", False)
    rrow(f, 468, ys[1], 620, "sensor", "유온 센서", "단위 ℃ · 측정 범위 (빈칸)", True)
    fan_out(f, 383, 468, ys, 94)
    return f.fin(0, foot(f, "필수 속성이 비면 넣기 전에 걸리고, 선택 속성은 비어도 들어간다", 186 + 14))


def u2_27():
    """27장: 클래스 셋의 정의 카드. 윗칸(파랑)이 식별자로 쓰는 속성, 아랫칸이 그 값을 적는 규칙. 부품 카드 아래의 기록 둘 가운데
    규칙과 다르게 적은 품번(파란 값)만 ✕."""
    f = Fig2("카드_식별자_정의.svg")
    xs, w = (345, 640, 935), 270
    for x, nm, key, rule in zip(xs, ("설비", "구성 요소", "부품"), ("설비 코드", "구성 요소 코드", "품번"), ("EQ-01", "EQ-01-COOLER", "CC-2040")):
        bot = ccard(f, x, 0, w, nm, ((key, True), (rule, False)))
    f.lab("식별자 · 필수", "", 100, 68 + 23 - 19, 190)
    f.lab("적는 규칙", "", 100, 124 + 23 - 19, 190)
    ys = (bot + 72, bot + 152)
    f.add(dash_arrow([(xs[2], bot + 8), (xs[2], ys[0] - 36)], BLUE, 4, 13, 8, 6))
    rrow(f, xs[2] - 170, ys[0], 340, "doc", "설비 대장", "CC-2040", True, nw=125, h=60)
    rrow(f, xs[2] - 170, ys[1], 340, "doc", "부품 목록", "**cc2040**", False, nw=125, h=60)
    return f.fin(0, foot(f, "정한 규칙과 다르게 적은 품번은 넣기 전에 걸린다", ys[1] + 30 + 14))


def u2_28():
    """28장: 세 시스템의 기록(같은 설비 코드가 파랗다)이 파란 점선으로 설비 인스턴스 하나에 모인다."""
    f = Fig2("카드_공통식별자_모으기.svg")
    x0, w, h, ys = 76, 540, 72, (46, 146, 246)
    bot, _ = vc(f, 996, 146 - 128, 240, "equip", "설비", "2호기", (("EQ-02", True),))
    for i, (y, kind, name, what) in enumerate(zip(ys, ("doc", "tsdb", "doc"), ("설비 대장", "시계열 저장소", "생산 실적"),
                                                  ("이름과 종류", "시각마다 잰 유온", "가동 시간"))):
        f.add(box(x0, y - h / 2, w, h, r=18) + disc(x0 + 40, y, 26, kind))
        f.lab(name, "", x0 + 150, y - 19, 160)
        f.lab("EQ-02", "", x0 + 290, y - 19, 110, strong=True)
        f.lab("", what, x0 + 435, y - 13, 180)
        f.add(dash_arrow([(x0 + w + 8, y), (996 - 120 - 10, 146 + (i - 1) * 22)], BLUE, 4, 13, 8, 6))
    return f.fin(0, foot(f, "설비 코드를 함께 쓰면 따로 적은 기록이 2호기 하나에 모인다", ys[2] + h / 2 + 14))


def u2_29():
    """29장: 위 정의 줄이 가진다의 시작 클래스 · 종료 클래스 · 카디널리티를 정한다. 아래 연결 셋 가운데 조건을 지킨 것만 ✓,
    거꾸로 그은 연결(회색 화살표)과 가진 설비가 없는 구성 요소(빈 점선 칸)는 ✕이고 줄 끝에 그 까닭."""
    f = Fig2("카드_관계정의_연결셋.svg")
    f.add(box(10, 0, 1180, 74, r=20))
    f.lab("가진다의 정의", "", 98, 37 - 19, 170)
    for x, w, item, val in ((190, 270, "시작 클래스", "**설비**"), (475, 290, "종료 클래스", "**구성 요소**"), (780, 396, "카디널리티", "1:N · 적어도 하나")):
        prow(f, x, 14, w, item, val, item_w=150)
    A, B, W, H, ys = 330, 650, 230, 60, (140, 228, 316)
    a0, a1 = A + W / 2 + 8, B - W / 2 - 8
    for i, y in enumerate(ys):
        hs(f, B, y, W, H, "cooler", "오일 쿨러")
        if i < 2:
            hs(f, A, y, W, H, "equip", "2호기")
            f.add(arrow([(a0, y), (a1, y)]) if i == 0 else arrow([(a1, y), (a0, y)], GREY))
            f.lab("가진다", "", (a0 + a1) / 2, y - 46, 86)
        else:
            f.add(dash_rect(A - W / 2, y - H / 2, W, H, GREY, 3, 8, 6))
        f.add((check_badge if i == 0 else cross_badge)(B + W / 2 + 45, y, 22))
    rx = B + W / 2 + 45 + 190
    f.lab("유효한 연결", "", rx, ys[0] - 19, 300, strong=True)
    f.lab("시작 · 종료 클래스가 거꾸로다", "", rx, ys[1] - 19, 350)
    f.lab("가진 설비가 없다", "", rx, ys[2] - 19, 300)
    return f.fin(0, ys[2] + H / 2)


def u2_30():
    """30장: 세로 카드 셋 한 줄. 역량 질문(파랑)에서 필요한 것만 정의하고, 정의대로 적고, 아래로 돌아오는 화살표가 그 질문으로 확인한다."""
    f = Fig2("카드_역량질문_세걸음.svg")
    xs, w = (130, 600, 1070), 220
    for x, kind, nm in zip(xs, ("question", "sheet", "graph"), ("역량 질문", "온톨로지 스키마", "인스턴스 데이터")):
        bot, dcy = vc(f, x, 0, w, kind, "", nm, hot=x == xs[0])
    rel(f, xs[0] + w / 2 + 8, xs[1] - w / 2 - 8, dcy, "필요한 것만 정의한다")
    rel(f, xs[1] + w / 2 + 8, xs[2] - w / 2 - 8, dcy, "정의대로 적는다")
    ry = bot + 44
    f.add(arrow([(xs[2], bot + 8), (xs[2], ry), (xs[0], ry), (xs[0], bot + 8)]))
    f.lab("그 질문으로 확인한다", "", 600, ry + 6, 300)
    return f.fin(0, foot(f, "역량 질문 「2호기 오일 쿨러에 갈아 끼울 부품의 품번은 무엇인가」", ry + 6 + 5 + LH_T + 16))


def u2_31():
    """31장: 위 줄은 역량 질문의 낱말 다섯, 아래 줄은 낱말마다 정해진 자리(클래스 · 관계 · 속성과 그 이름). 2호기와 오일 쿨러 두 자리에서
    파란 점선이 모여 둘 사이의 관계 가진다가 나온다."""
    f = Fig2("카드_질문낱말_정의로.svg")
    xs, w = (130, 365, 600, 835, 1070), 190
    words = (("2호기", "클래스", "설비"), ("오일 쿨러에", "클래스", "구성 요소"), ("갈아 끼울", "관계", "쓴다"), ("부품의", "클래스", "부품"), ("품번은", "속성", "품번"))
    for x, (word, kind, name) in zip(xs, words):
        f.add(box(x - w / 2, 0, w, 60, r=30))
        f.lab(word, "", x, 30 - 19, w - 20)
        f.add(arrow([(x, 66), (x, 112)]))
        f.add(box(x - w / 2, 118, w, 84, r=18))
        f.lab(kind, f"**{name}**", x, 160 - (LH_T + LH_D) / 2 - 6, w - 20)
    gx, gy = (xs[0] + xs[1]) / 2, 300
    f.add(dash_line(xs[0], 208, xs[0], 236, BLUE, 4, 8, 6) + dash_line(xs[1], 208, xs[1], 236, BLUE, 4, 8, 6)
          + dash_line(xs[0], 236, xs[1], 236, BLUE, 4, 8, 6) + dash_arrow([(gx, 236), (gx, gy - 48)], BLUE, 4, 13, 8, 6))
    f.add(box(gx - w / 2, gy - 42, w, 84, r=18))
    f.lab("관계", "**가진다**", gx, gy - (LH_T + LH_D) / 2 - 6, w - 20)
    f.lab("2호기의 오일 쿨러라는 이어짐", "", gx + w / 2 + 180, gy - 19, 320)
    return f.fin(0, foot(f, "클래스 셋 · 관계 둘 · 속성 하나를 정의하면 이 질문에 답한다", gy + 42 + 16))


AREAS = (("설비 영역", "무엇이 어디에 달렸나", ("설비", "구성 요소", "센서", "부품")), ("진단 영역", "왜 그렇게 됐나", ("고장 유형", "증상", "원인")),
         ("판단 영역", "무엇을 할 것인가", ("조치", "판단 규칙")), ("성과 영역", "얼마나 나아졌나", ("전략 목표", "성과 지표")))


def u2_34():
    """34장: 영역 넷을 같은 꼴의 칸으로(2 × 2). 칸마다 영역 이름과 물음의 갈래, 그 영역의 클래스 이름 칸. 진단 영역의 고장 유형에서
    설비 영역의 구성 요소로 가는 일어난다 하나가 영역을 건너고, 그 두 칸만 파랗다."""
    f = Fig2("카드_영역_네칸.svg")
    pos = ((20, 0, 176), (660, 0, 176), (20, 200, 124), (660, 200, 124))
    for (x0, top, h), (name, q, classes) in zip(pos, AREAS):
        f.add(box(x0, top, 520, h))
        f.lab(name, q, x0 + 260, top + 6, 420, strong=True)
        for i, c in enumerate(classes):
            chip(f, x0 + 20 + (i % 2) * 250, top + 68 + (i // 2) * 52, 230, c, c in ("구성 요소", "고장 유형"), h=44)
    y = 68 + 22
    f.add(arrow([(676, y), (524, y)]))
    f.lab("일어난다", "", 600, y - 46, 110)
    return f.fin(0, foot(f, "역량 질문의 갈래로 나눠 맡아도, 같은 스키마 하나로 이어 같은 뜻으로 읽힌다", 324 + 14))


def alt2_27():
    """27장 다른 안: 25 · 26장과 같은 구도(왼쪽 정의 카드 하나, 오른쪽 기록 둘). 부품의 식별자만 보인다."""
    f = Fig2("다른안_27_식별자_부품만.svg")
    ys = [70, 158]
    dcard(f, 250, 114 - 120, 400, "부품", ({"item": "식별자", "val": "**품번**"}, {"item": "적는 규칙", "val": "CC-2040처럼"}, {"item": "필수 여부", "val": "필수"}))
    rrow(f, 555, ys[0], 520, "doc", "설비 대장", "품번 CC-2040", True)
    rrow(f, 555, ys[1], 520, "doc", "부품 목록", "품번 **cc2040**", False)
    fan_out(f, 450, 555, ys, 114)
    return f.fin(-6, foot(f, "정한 규칙과 다르게 적은 품번은 넣기 전에 걸린다", 234 + 14))


def alt2_34():
    """34장 다른 안: 영역 넷을 한 줄에. 클래스 이름은 칸 하나에 글로만 적고, 영역을 건너는 관계는 맨 아래 한 줄로 말한다."""
    f = Fig2("다른안_34_영역_한줄.svg")
    for x, (name, q, classes) in zip((150, 450, 750, 1050), AREAS):
        f.add(box(x - 135, 0, 270, 196))
        f.lab(name, q, x, 14, 250, strong=True)
        f.lab("", " / ".join(classes), x, 84, 250)
    return f.fin(0, foot(f, "고장 유형은 구성 요소에서 일어난다처럼, 영역 사이도 같은 스키마의 관계로 잇는다", 210))


U2_FIGS = [u2_22, u2_23, u2_24, u2_25, u2_26, u2_27, u2_28, u2_29, u2_30, u2_31, u2_34, alt2_27, alt2_34]
NEW_FIGS += U2_FIGS


# ───────────────────────── 3단원 새 꼴(35~51장을 다시 짠 최종 그림 「카드_*.svg」) ─────────────────────────
# 1 · 2단원의 카드 문법을 잇는다. 이 단원에서 더한 꼴:
#   · 코드 = 고정폭 16pt 글자를 연회색 상자에 줄마다 라벨 하나로(왼쪽 맞춤). 절의 첫 낱말만 파란 글자.
#     여러 줄 쿼리는 줄 사이를 넓혀 오른쪽에 줄마다 풀이 한 덩어리를 파란 점선으로 잇고, 결과는 맨 아래 굵은 한 줄.
#   · 표(관계형 DB) = 칸마다 흰 상자. 질문이 지나는 칸은 연하늘, 맞춰 잇는 자리는 파란 선.

def cw(ch):
    """고정폭 라벨에서 한 글자의 그림 폭. 한글 같은 비ASCII 글자는 덱 글꼴(전각)로 그려진다."""
    return CW16 if ord(ch) < 128 else CW16 / (1126 / 2048)


def code_block(f, x0, top, lines, pitch=64, pad=28, width=None):
    """코드 여러 줄을 왼쪽 맞춤으로. lines의 **…**는 파란 글자. 돌려주는 값: (줄 가운데 y들, 상자 오른쪽 x, 상자 아래 y)."""
    raws = [ln.replace("**", "") for ln in lines]
    w = width or max(sum(cw(c) for c in r) for r in raws) + 2 * pad
    h = (len(lines) - 1) * pitch + 76
    f.add([rect(x0, top, w, h, 18, fill=LIGHT, stroke=NAVY, sw=2.5)])
    ys = []
    for i, (ln, raw) in enumerate(zip(lines, raws)):
        body = raw.lstrip(" ")
        lead = (len(raw) - len(body)) * CW16
        tw = sum(cw(c) for c in body)
        cy = top + 38 + i * pitch
        f.lab(ln.lstrip(" "), "", x0 + pad + lead + tw / 2, cy - 19, tw * 1.14 + 40, mono=True)
        ys.append(cy)
    return ys, x0 + w, top + h


def note(f, bx, y0, y1, title, desc, cx, w=440):
    """코드 상자(오른쪽 끝 bx)의 y0~y1 줄에서 오른쪽 풀이(가운데 x cx)로 가는 파란 점선과 풀이 한 덩어리."""
    my = (y0 + y1) / 2
    if y1 > y0:
        f.add(dash_line(bx + 14, y0 - 14, bx + 14, y1 + 14, BLUE, 4, 8, 6))
    f.add(dash_arrow([(bx + 14, my), (bx + 62, my)], BLUE, 4, 13, 8, 6))
    f.lab(title, desc, cx, my - (LH_T + LH_D) / 2 - 6, w)


def u3_36():
    """36장: 11장과 같은 두 카드. 카드가 노드, 화살표가 관계, 카드 안 칸이 속성(키와 값의 짝)이다."""
    f = Fig2("카드_저장구조_키와값.svg")
    for x, kind, cls, nm, item, val in ((240, "equip", "설비", "2호기", "설비 코드", "EQ-02"), (960, "cooler", "구성 요소", "오일 쿨러", "구성 요소 코드", "EQ-02-COOLER")):
        f.lab("노드", "", x, 0, 120, strong=True)
        bot, dcy, ya = icard(f, x, 40, 440, kind, cls, nm, ({"item": item, "val": val, "item_w": 180},))
    rel(f, 470, 730, dcy, "가진다")
    f.lab("관계", "", 600, dcy + 16, 120, strong=True)
    y = ya[0]
    f.lab("속성", "키와 값의 짝", 600, y - (LH_T + LH_D) / 2 - 6, 130, strong=True)
    f.add(dash_arrow([(528, y), (470, y)], BLUE, 4, 13, 8, 6) + dash_arrow([(672, y), (730, y)], BLUE, 4, 13, 8, 6))
    return f.fin(0, bot)


def grid(f, x0, y0, widths, rows, rh=52, hot=(), head=None):
    """표 한 장: 칸마다 상자와 글. hot = 연하늘로 칠할 줄 번호들. head면 맨 위에 작은 머리 줄(회색 칸). 돌려주는 값: (열 왼쪽 x들, 줄 가운데 y들, 아래 y)."""
    xs = [x0 + sum(widths[:i]) for i in range(len(widths))]
    y = y0
    if head:
        for x, w, t in zip(xs, widths, head):
            f.add([rect(x, y, w, 40, 0, fill=GREY, stroke=NAVY, sw=2)])
            f.lab("", t, x + w / 2, y + 20 - 13, w - 8)
        y += 40
    ys = []
    for i, row in enumerate(rows):
        for x, w, t in zip(xs, widths, row):
            f.add([rect(x, y, w, rh, 0, fill=PALE if i in hot else WHITE, stroke=NAVY, sw=2)])
            f.lab(t, "", x + w / 2, y + rh / 2 - 19, w - 6)
        ys.append(y + rh / 2)
        y += rh
    return xs, ys, y


def u3_37():
    """37장: 클래스마다 테이블 하나(위 이름 셋), 아래는 구성 요소 테이블. 연하늘 줄이 행(인스턴스 하나), 파란 테두리가 열(속성 하나)."""
    f = Fig2("카드_테이블_행과열.svg")
    for x, nm in ((223, "설비 테이블"), (553, "구성 요소 테이블"), (883, "부품 테이블")):
        f.add(box(x - 125, 0, 250, 56, hot=x == 553, r=18))
        f.lab(nm, "", x, 28 - 19, 230, strong=x == 553)
    widths = (280, 200, 240)
    xs, ys, bot = grid(f, 193, 96, widths, (("EQ-02-COOLER", "오일 쿨러", "EQ-02"), ("EQ-02-FAN", "쿨러 팬", "EQ-02")), hot=(0,),
                       head=("구성 요소 코드", "이름", "설비 코드"))
    f.add(dash_arrow([(553, 62), (553, 90)], BLUE, 4, 13, 8, 6))
    f.add([rect(xs[1] - 4, 92, widths[1] + 8, bot - 92 + 4, 8, fill="none", stroke=BLUE, sw=5)])
    f.add(dash_arrow([(983, ys[0]), (923, ys[0])], BLUE, 4, 13, 8, 6))
    f.lab("행", "인스턴스 하나", 1053, ys[0] - (LH_T + LH_D) / 2 - 6, 140, strong=True)
    f.add(dash_arrow([(xs[1] + 100, bot + 50), (xs[1] + 100, bot + 12)], BLUE, 4, 13, 8, 6))
    f.lab("열", "속성 하나", xs[1] + 100, bot + 54, 140, strong=True)
    return f.fin(0, bot + 54 + 5 + LH_T + LH_D)


Q38 = "2호기 오일 쿨러에 갈아 끼울 부품의 품번을 물으면 "


def u3_38():
    """38장: 테이블 넷을 왼쪽부터. 질문이 지나는 칸은 연하늘이고, 이웃한 두 표에서 같은 값을 적은 칸을 파란 선(조인)으로 맞춰 잇는다.
    잇는 표의 둘째 줄(다른 오일 쿨러도 같은 품번)은 다대다라 잇는 표가 따로 있는 까닭이다."""
    f = Fig2("카드_조인_세번.svg")
    tabs = ((15, (100, 100), (("2호기", "EQ-02"),), "설비 테이블", False), (281, (110, 200), (("EQ-02", "EQ-02-COOLER"),), "구성 요소 테이블", False),
            (657, (200, 130), (("EQ-02-COOLER", "CC-2040"), ("EQ-03-COOLER", "CC-2040")), "잇는 표", True), (1053, (130,), (("CC-2040",),), "부품 테이블", False))
    ends = []
    for x0, widths, rows, title, blue in tabs:
        f.lab(title, "", x0 + sum(widths) / 2, 0, 200, strong=blue)
        xs, ys, bot = grid(f, x0, 44, widths, rows, hot=(0,))
        ends.append((x0, x0 + sum(widths)))
    y = 44 + 26
    for (_, a), (b, _) in zip(ends, ends[1:]):
        f.add([line(a, y, b, y, stroke=BLUE, sw=5), circle(a, y, 6, fill=BLUE, stroke=BLUE, sw=1), circle(b, y, 6, fill=BLUE, stroke=BLUE, sw=1)])
        f.add(dash_line((a + b) / 2, y + 8, (a + b) / 2, 152, BLUE, 4, 8, 6))
        f.lab("조인", "", (a + b) / 2, 156, 80, strong=True)
    return f.fin(0, foot(f, Q38 + "조인 셋을 거쳐 CC-2040이 나온다", 156 + 5 + LH_T + 16))


def u3_39():
    """39장: 38장과 같은 물음, 같은 왼쪽 → 오른쪽 구도. 파란 화살표 둘이 저장된 관계를 따라간 길이고, 다른 오일 쿨러도 잇는 표 없이
    관계 하나로 같은 쿨러 코어에 닿는다."""
    f = Fig2("카드_관계따라가기_두번.svg")
    xs, W, H, ys = (160, 600, 1040), 300, 116, (58, 198)
    hc(f, xs[0], ys[0], W, H, "equip", "설비", "2호기", "EQ-02", blue=False)
    hc(f, xs[1], ys[0], W, H, "cooler", "구성 요소", "오일 쿨러", "EQ-02-COOLER", blue=False)
    hc(f, xs[2], ys[0], W, H, "core", "부품", "쿨러 코어", "CC-2040")
    hc(f, xs[1], ys[1], W, H, "cooler", "구성 요소", "오일 쿨러", "EQ-03-COOLER", blue=False)
    rel(f, xs[0] + W / 2 + 8, xs[1] - W / 2 - 8, ys[0], "가진다", BLUE)
    rel(f, xs[1] + W / 2 + 8, xs[2] - W / 2 - 8, ys[0], "쓴다", BLUE)
    f.add(arrow([(xs[1] + W / 2 + 8, ys[1]), (xs[2], ys[1]), (xs[2], ys[0] + H / 2 + 8)]))
    f.lab("쓴다", "", (xs[1] + W / 2 + xs[2]) / 2, ys[1] - 46, 120)
    return f.fin(0, foot(f, Q38 + "관계 둘을 따라가 CC-2040이 나온다", ys[1] + H / 2 + 14))


def u3_40():
    """40장: 위 띠는 온톨로지 스키마의 클래스 이름과 관계 유형 이름, 아래는 그래프 DB의 노드와 관계. 파란 점선이 이름이 그대로 붙는
    자리를 잇는다(클래스 이름 → 레이블, 관계 유형 이름 → 관계 유형). 뜻과 규칙은 맨 아래 한 줄."""
    f = Fig2("카드_레이블_이름붙이기.svg")
    xs, W, H, ya, yb = (290, 680, 1070), 170, 76, 66, 250
    f.add(band_rect(0, 132, PALE))
    f.lab("온톨로지 스키마", "", 100, ya - 19, 190)
    f.lab("그래프 DB", "쿼리에 쓰는 영문 이름", 100, yb - (LH_T + LH_D) / 2 - 6, 210)
    for x, ko, en in zip(xs, ("설비", "구성 요소", "부품"), ("Asset", "Component", "Part")):
        f.add(box(x - W / 2, ya - H / 2, W, H, r=18) + box(x - W / 2, yb - H / 2, W, H, r=18))
        f.lab(ko, "클래스 이름", x, ya - (LH_T + LH_D) / 2 - 6, W - 16)
        f.lab(en, "**레이블**", x, yb - (LH_T + LH_D) / 2 - 6, W - 16)
        f.add(dash_arrow([(x, ya + H / 2 + 8), (x, yb - H / 2 - 8)], BLUE, 4, 13, 8, 6))
    for (a, b), ko, en in zip(((0, 1), (1, 2)), ("가진다", "쓴다"), ("HAS_COMPONENT", "USES_PART")):
        x0, x1 = xs[a] + W / 2 + 8, xs[b] - W / 2 - 8
        mx = (x0 + x1) / 2
        f.add(arrow([(x0, ya), (x1, ya)]) + arrow([(x0, yb), (x1, yb)]))
        f.lab(ko, "", mx, ya - 46, x1 - x0 + 32)
        f.lab(en, "", mx, yb - 46, x1 - x0 + 32)
        f.add(dash_arrow([(mx, ya + 12), (mx, yb - 52)], BLUE, 4, 13, 8, 6))
    return f.fin(0, foot(f, "의미 · 자료형 · 필수 · 카디널리티는 스키마에 남고, 그 일부만 DB에 조건으로 건다", yb + H / 2 + 16))


def u3_41():
    """41장: 세로 카드 셋 한 줄(넣을 데이터 → 검사 프로그램 → 그래프 DB). 두 관문 아래에 저마다 걸리는 것 하나씩(회색 화살표와 ✕)."""
    f = Fig2("카드_두관문_걸리는것.svg")
    xs, w = (165, 575, 985), 220
    for x, kind, nm in zip(xs, ("doc", "sheet", "graph"), ("넣을 데이터", "검사 프로그램", "그래프 DB")):
        bot, dcy = vc(f, x, 0, w, kind, "", nm)
    rel(f, xs[0] + w / 2 + 8, xs[1] - w / 2 - 8, dcy, "넣기 전")
    rel(f, xs[1] + w / 2 + 8, xs[2] - w / 2 - 8, dcy, "저장할 때")
    for x, t, d, blue in ((xs[1], "DB에 걸지 않은 규칙", "오일 쿨러에서 2호기로 거꾸로 그은 가진다", False),
                          (xs[2], "유일 제약(Uniqueness Constraint)", "품번 CC-2040인 부품이 하나 더 들어온다", True)):
        f.add(arrow([(x, bot + 8), (x, bot + 46)], GREY) + cross_badge(x, bot + 72, 22))
        f.lab(t, d, x, bot + 100, 390, strong=blue)
    return f.fin(0, foot(f, "DB에 걸지 않은 규칙은 넣기 전에 검사 프로그램이 맡는다", bot + 100 + 5 + LH_T + LH_D + 16, cx=575))


def u3_42():
    """42장: 말로 물은 질문 하나가 읽기에 따라 세 가지 답으로 갈라진다."""
    f = Fig2("카드_말질문_갈래.svg")
    ys, W, H = (42, 148, 254), 440, 84
    hcard(f, 250, ys[1], 420, 104, "question", name="2호기 쿨러 부품 알려 줘")
    for y, t, d in zip(ys, ("쿨러 팬", "쿨러 코어", "CC-2040"), ("쿨러에 딸린 구성 요소로 읽으면", "오일 쿨러가 쓰는 부품의 이름으로 읽으면", "그 부품의 품번으로 읽으면")):
        f.add(box(940 - W / 2, y - H / 2, W, H, r=18))
        f.lab(t, d, 940, y - (LH_T + LH_D) / 2 - 6, W - 20)
        f.add(arrow([(468, ys[1] + (y - ys[1]) * 0.25), (940 - W / 2 - 8, y)]))
    return f.fin(0, foot(f, "말로 물으면 어느 대상의 어느 값인지 하나로 정해지지 않는다", ys[2] + H / 2 + 16))


Q_MATCH = ("MATCH (:Asset {code: 'EQ-02'})", "      -[:HAS_COMPONENT]->(c:Component)")


def u3_43():
    """43장: 쿼리 세 줄과, 줄마다 오른쪽에 그 줄이 정하는 것(출발 노드 · 건널 관계 · 돌려받을 값)."""
    f = Fig2("카드_쿼리_세줄.svg")
    ys, bx, bot = code_block(f, 170, 0, (*Q_MATCH, "RETURN c.name"))
    for y, t, d in zip(ys, ("출발 노드", "건널 관계", "돌려받을 값"), ("설비 코드가 EQ-02인 설비", "가진다", "구성 요소의 이름")):
        note(f, bx, y, y, t, d, bx + 62 + 180, 340)
    return f.fin(0, foot(f, "이 세 줄이 그래프 DB에 보내는 쿼리 하나이고, 묻는 것이 하나로 정해진다", bot + 16))


def u3_44():
    """44장: 위는 관계 그림 한 줄(클래스 카드 둘과 가진다), 아래는 같은 모양을 글자로 옮긴 패턴 한 줄. 카드와 화살표가 저마다 제 글자
    바로 위에 있고 파란 점선이 곧게 내려간다."""
    f = Fig2("카드_패턴_그림과글자.svg")
    text, cy = "(:Asset)-[:HAS_COMPONENT]->(:Component)", 210
    f.add([rect(600 - 300, cy - 38, 600, 76, 18, fill=LIGHT, stroke=NAVY, sw=2.5)])
    sp = code_line(f, text, 600, cy)
    a, r, b = (sum(sp(t)) / 2 for t in ("(:Asset)", "-[:HAS_COMPONENT]->", "(:Component)"))
    W = 190
    hcard(f, a - 10, 40, W, 64, "none", name="설비", ring=True, strong=True)
    hcard(f, b + 10, 40, W, 64, "none", name="구성 요소", ring=True, strong=True)
    rel(f, a - 10 + W / 2 + 8, b + 10 - W / 2 - 8, 40, "가진다")
    for x, y0, t in ((a - 10, 78, "노드"), (r, 52, "관계"), (b + 10, 78, "노드")):
        f.add(dash_arrow([(x, y0), (x, cy - 46)], BLUE, 4, 13, 8, 6))
        f.lab("", t, x + 36, (y0 + cy - 46) / 2 - 13 + (14 if t == "관계" else 0), 60)
    return f.fin(0, cy + 38)


def u3_45a():
    return g3_45B1("카드_패턴표기_셋.svg")


def u3_45b():
    return g3_45B2("카드_패턴_거꾸로적기.svg")


def u3_46():
    """46장: 왼쪽 창이 Neo4j Browser(위에 쿼리를 넣는 칸, 아래에 결과를 그래프로 · 표로 보는 두 칸), 오른쪽이 연결된 그래프 DB."""
    f = Fig2("카드_브라우저_창.svg")
    f.add([rect(40, 0, 720, 330, 16, fill=WHITE, stroke=NAVY, sw=3), line(40, 40, 760, 40, sw=3)]
          + [circle(66 + i * 22, 20, 6, fill=GREY, stroke="none", sw=0) for i in range(3)])
    f.add([rect(64, 58, 672, 56, 12, fill=LIGHT, stroke=NAVY, sw=2.5)])
    f.lab("쿼리를 넣는 칸", "", 400, 86 - 19, 400)
    for x, t in ((64, "그래프"), (412, "표")):
        f.add([rect(x, 132, 324, 178, 12, fill=WHITE, stroke=NAVY, sw=2.5)])
        f.lab(t, "", x + 162, 138, 200)
    pts = ((226, 216), (150, 280), (226, 286), (302, 280))
    f.add([line(pts[0][0], pts[0][1], x, y, sw=3) for x, y in pts[1:]] + [circle(x, y, 14, fill=PALE if i else SKY, stroke=NAVY, sw=3) for i, (x, y) in enumerate(pts)])
    f.add([rect(436, 186, 276, 26, 6, fill=GREY, stroke="none", sw=0)] + [rect(436, 220 + i * 28, 276, 20, 6, fill=LIGHT, stroke="none", sw=0) for i in range(3)])
    bot, dcy = vc(f, 1010, 66, 220, "graph", "", "그래프 DB")
    f.add(dash_line(768, 165, 892, 165, BLUE, 4, 8, 6))
    f.lab("연결", "", 830, 165 - 46, 110)
    return f.fin(0, foot(f, "데이터는 Browser가 아니라 연결된 그래프 DB에 있다", 330 + 16))


def u3_47():
    """47장: 쿼리 세 줄. 절의 첫 낱말(MATCH · RETURN)이 파란 글자이고, 오른쪽에 절마다 하는 일. 맨 위 오른쪽이 절의 뜻, 맨 아래가 결과."""
    f = Fig2("카드_MATCH_RETURN.svg")
    ys, bx, bot = code_block(f, 95, 0, ("**MATCH** (:Asset {code: 'EQ-02'})", Q_MATCH[1], "**RETURN** c.name"))
    cx = bx + 62 + 250
    f.lab("절(Clause)", "첫 낱말로 시작해 할 일 하나를 맡는 부분", cx, -70, 480, strong=True)
    note(f, bx, ys[0], ys[1], "MATCH 절", "2호기에서 가진다로 이어진 구성 요소를 모두 찾는다", cx, 480)
    note(f, bx, ys[2], ys[2], "RETURN 절", "찾은 구성 요소 c의 이름을 돌려받는다", cx, 480)
    return f.fin(-70, foot(f, "결과 3행  주 펌프 · 쿨러 팬 · 오일 쿨러", bot + 16))


def u3_48():
    """48장: 쿼리 네 줄. WHERE만 파란 글자이고, 오른쪽에 WHERE 절과 RETURN 절이 하는 일. 맨 아래가 결과."""
    f = Fig2("카드_WHERE.svg")
    ys, bx, bot = code_block(f, 110, 0, (*Q_MATCH, "**WHERE** c.name = '오일 쿨러'", "RETURN c.code"), pitch=70)
    cx = bx + 62 + 220
    note(f, bx, ys[2], ys[2], "WHERE 절", "이름이 오일 쿨러라는 조건을 더한다", cx, 420)
    note(f, bx, ys[3], ys[3], "RETURN 절", "그 구성 요소의 구성 요소 코드를 돌려받는다", cx, 420)
    return f.fin(0, foot(f, "결과 1행  EQ-02-COOLER", bot + 16))


def two_runs(f, name, code, runs, one):
    """49 · 50장: 같은 쿼리를 두 번 돌린다. 위에 쿼리 한 줄, 아래에 실행 둘과 그 결과(부품 노드). one이면 두 실행이 노드 하나로 모인다."""
    ys, LX, RX = (150, 262), 355, 925
    f.add([rect(LX - 235, 0, 470, 76, 18, fill=LIGHT, stroke=NAVY, sw=2.5)])
    code_line(f, code, LX, 38, hi=name)
    f.add(dash_arrow([(LX, 82), (LX, ys[0] - 46)], BLUE, 4, 13, 8, 6) + dash_line(LX - 190, 82, LX - 190, ys[1], BLUE, 4, 8, 6)
          + dash_arrow([(LX - 190, ys[1]), (LX - 138, ys[1])], BLUE, 4, 13, 8, 6))
    for i, (y, (t, d)) in enumerate(zip(ys, runs)):
        f.add(box(LX - 130, y - 38, 260, 76, r=18))
        f.lab(t, d, LX, y - (LH_T + LH_D) / 2 - 6, 240)
        ty = (ys[0] + ys[1]) / 2 + (i - 0.5) * 24 if one else y
        if one and i == 1:
            f.add(dash_arrow([(LX + 138, y), (RX - 158, ty)], BLUE, 4.5, 15, 9, 7))
        else:
            f.add(arrow([(LX + 138, y), (RX - 158, ty)]))
        if not one:
            hc(f, RX, y, 300, 96, "core", "부품", "품번 CC-2040", blue=False)
    if one:
        hc(f, RX, (ys[0] + ys[1]) / 2, 300, 96, "core", "부품", "품번 CC-2040", blue=False)
    return ys[1] + 48


def u3_49():
    """49장: 같은 CREATE를 두 번 돌리면 품번이 같은 부품 노드가 둘. 맨 아래는 품번에 유일 제약이 걸려 있을 때."""
    f = Fig2("카드_CREATE_둘.svg")
    bot = two_runs(f, "CREATE", "CREATE (:Part {partNo: 'CC-2040'})", (("1번째 실행", "새로 만든다"), ("2번째 실행", "또 새로 만든다")), False)
    f.lab("품번에 유일 제약이 걸려 있으면", "2번째 실행은 DB가 거절하고, 부품 노드는 하나로 남는다", 625, bot + 14, 1000)
    return f.fin(0, bot + 14 + 5 + LH_T + LH_D)


def u3_50():
    """50장: 49장과 같은 구도. 같은 MERGE를 두 번 돌리면 1번째는 만들고(실선) 2번째는 찾기만 해(파란 점선) 노드는 하나. 맨 아래는
    MERGE의 패턴에 식별자를 적는 까닭."""
    f = Fig2("카드_MERGE_하나.svg")
    bot = two_runs(f, "MERGE", "MERGE (:Part {partNo: 'CC-2040'})", (("1번째 실행", "없으니 만든다"), ("2번째 실행", "있으니 찾는다")), True)
    f.lab("MERGE의 패턴에는 식별자를 적는다", "바뀔 수 있는 이름까지 적으면, 이름이 다를 때 같은 부품을 못 찾고 하나 더 만든다", 625, bot + 14, 1000)
    return f.fin(0, bot + 14 + 5 + LH_T + LH_D)


def u3_51():
    """51장: 쿼리 다섯 줄. 절의 첫 낱말이 파란 글자이고, 오른쪽에 절마다 하는 일(MATCH 세 줄은 손으로 따라간 길). 맨 아래가 결과."""
    f = Fig2("카드_역량질문_쿼리.svg")
    ys, bx, bot = code_block(f, 95, 0, ("**MATCH** (:Asset {code: 'EQ-02'})", Q_MATCH[1], "      -[:USES_PART]->(p:Part)",
                                        "**WHERE** c.name = '오일 쿨러'", "**RETURN** p.partNo"), pitch=68)
    cx = bx + 62 + 250
    note(f, bx, ys[0], ys[2], "MATCH 절", "설비 → 가진다 → 구성 요소 → 쓴다 → 부품", cx, 480)
    note(f, bx, ys[3], ys[3], "WHERE 절", "2호기의 구성 요소 가운데 오일 쿨러", cx, 480)
    note(f, bx, ys[4], ys[4], "RETURN 절", "그 부품의 품번", cx, 480)
    return f.fin(0, foot(f, "결과 1행  CC-2040", bot + 16))


U3_FIGS = [u3_36, u3_37, u3_38, u3_39, u3_40, u3_41, u3_42, u3_43, u3_44, u3_45a, u3_45b, u3_46, u3_47, u3_48, u3_49, u3_50, u3_51]
NEW_FIGS += U3_FIGS


FIGS = [f05, f06, f07, f08, f09, f10, f11, f12, f13, f14, f16, f17, f18, f19, f20,
        f22, f23, f24, f25, f26, f27, f28, f29, f30, f31, f34,
        f36, f37, f38, f39, f40, f41, f42, f44, f46, f49, f50]


def fit_deck(md: Path, labels: dict[str, list[str]]) -> int:
    """덱 MD에서 `- 그림: <폴더>/<이 생성기가 만든 그림>`인 장의 `- 요소:` 목록을 이 생성기의 라벨 줄로 바꿔 쓴다.
    그 장에 `- 요소:` 줄이 없으면 오류로 멈춘다. 돌려주는 값: 바꾼 장 수."""
    lines = md.read_text(encoding="utf-8").split("\n")
    out, i, n, cur = [], 0, 0, None
    starts = [k for k, s in enumerate(lines) if s.startswith("## SLIDE")] + [len(lines)]
    out = lines[:starts[0]]
    for a, b in zip(starts, starts[1:]):
        block = lines[a:b]
        pic = next((s.rsplit("/", 1)[-1].strip() for s in block if s.startswith("- 그림: ")), None)
        if pic in labels:
            if "- 요소:" not in block:
                raise SystemExit(f"{md}: {block[0]} 에 `- 요소:` 줄이 없다")
            k = block.index("- 요소:")
            j = k + 1
            while j < len(block) and re.match(r"  (\d+\.|-) ", block[j]):
                j += 1
            block = block[:k + 1] + [f"  {m}. {s}".replace(" |  | ", " | | ").rstrip() for m, s in enumerate(labels[pic], 1)] + block[j:]
            n += 1
        out += block
    md.write_bytes("\n".join(out).encode("utf-8"))
    return n


def main():
    show = "--라벨" in sys.argv
    labels = {}
    for fn in FIGS + NEW_FIGS:
        f = fn()
        text = f.svg()
        assert "<text" not in text
        (HERE / f.name).write_bytes(text.encode("utf-8"))
        labels[f.name] = f.labels
        if show:
            print(f"### {f.name} ({len(f.labels)}개)")
            for i, s in enumerate(f.labels, 1):
                print(f"  {i}. {s}")
        else:
            print("wrote", f.name)
    if "--덱맞춤" in sys.argv:
        md = Path(sys.argv[sys.argv.index("--덱맞춤") + 1])
        print(f"덱맞춤: {md.name}에서 {fit_deck(md, labels)}장의 라벨을 바꿔 썼다")


if __name__ == "__main__":
    main()
