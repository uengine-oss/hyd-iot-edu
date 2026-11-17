"""통합반 2회차 이론 덱의 카드 그림(SVG)을 만든다. 글자는 넣지 않는다(라벨은 덱 MD의 요소로 얹는다, 덱 D-8).

사용:
  python 만들기_카드.py            → 이 폴더에 「카드_*.svg」를 쓴다(옛 그림과 옛 생성기 만들기_삽화*.py는 건드리지 않는다)
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
             ("1:N", "구성 요소 → 감시된다 → 센서 / 구성 요소 하나에 센서 여럿, / 센서 하나에 구성 요소 하나 / 반대쪽에서 읽으면 N:1"),
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
    인스턴스는 점선 「속한다」로 제 클래스에 닿는다. ① 한 종류다 = 상속, ② 속한다 = 인스턴스, ③ 일부다 = 관계(가진다)."""
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
        f.add(dash_arrow([(x, iy - 52), (x, ky + 48)], BLUE if x == XK else GREY, 4.5, 16, 9, 7))
    f.lab("② 속한다", "인스턴스", XK + 66, 232, 130)
    f.lab("", "속한다", XE + 52, 248, 90)
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


FIGS = [f05, f06, f07, f08, f09, f10, f11, f12, f13, f14, f16, f17, f18, f19, f20,
        f22, f23, f24, f25, f26, f27, f28, f29, f30, f31, f34]


def fit_deck(md: Path, labels: dict[str, list[str]]) -> int:
    """덱 MD에서 `- 그림: figures/<이 생성기가 만든 그림>`인 장의 `- 요소:` 목록을 이 생성기의 라벨 줄로 바꿔 쓴다.
    그 장에 `- 요소:` 줄이 없으면 오류로 멈춘다. 돌려주는 값: 바꾼 장 수."""
    lines = md.read_text(encoding="utf-8").split("\n")
    out, i, n, cur = [], 0, 0, None
    starts = [k for k, s in enumerate(lines) if s.startswith("## SLIDE")] + [len(lines)]
    out = lines[:starts[0]]
    for a, b in zip(starts, starts[1:]):
        block = lines[a:b]
        pic = next((s.split("figures/", 1)[1].strip() for s in block if s.startswith("- 그림: figures/")), None)
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
    for fn in FIGS:
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
