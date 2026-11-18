"""통합반 3회차 이론 덱의 카드 그림(SVG)을 만든다. 글자는 넣지 않는다(라벨은 덱 MD의 요소로 얹는다, 덱 D-8).

사용:
  python 만들기_카드.py            → 이 폴더에 지금 원고가 쓰는 「카드_*.svg」를 쓴다(옛 생성기 만들기_삽화*.py · 만들기_그래프*.py ·
                                    만들기_판단그림.py와 그 그림은 건드리지 않는다)
  python 만들기_카드.py --라벨     → 그림마다 덱 MD에 붙일 라벨 요소 줄(`라벨 | 설명 | x,y,폭`)을 찍는다
  python 만들기_카드.py --덱맞춤 <덱.md>  → 그 덱에서 이 그림을 쓰는 장의 `- 요소:` 목록을 이 파일의 라벨 줄로 바꿔 쓴다
                                          (라벨 글은 이 파일이 정본이다. 글을 고칠 때는 여기서 고친 뒤 덱맞춤을 돌린다)

그림체는 2회차 이론 덱의 새 꼴(day02/figures/만들기_카드.py의 1단원 새 꼴)과 같다: 흰 바탕, 선 끝은 둥글게, 덱 색만,
그라디언트 · 그림자 · <text> 없음, 큰 아이콘 원판과 굵은 이름을 한 덩어리로 담은 카드, 그림 아래 굵은 결론 한 줄.
강조(파란 칸 · 파란 테두리 · 파란 글)는 그 장의 풀 자리 용어와 판단을 가르는 값에만 건다.
그림은 모두 1200 × 510이고, 라벨 좌표는 x ÷ 12, y ÷ 5.1(%)로 덱 MD에 옮긴다. 이 파일이 라벨 자리를 함께 계산한다.
2회차 생성기는 다른 세션이 고치는 파일이라 import하지 않고 조각을 옮겨 왔다.
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

# 라벨 글자의 줄 높이(그림 px). 덱 `라벨: 큰`은 제목 16pt · 설명 13pt이고 줄 간격은 1.22다.
LH_T, LH_D = 27, 22


class St:
    def __init__(self, line, fill, accent, soft):
        self.line, self.fill, self.accent, self.soft = line, fill, accent, soft


ON = St(NAVY, WHITE, SKY, PALE)


# ───────────────────────── 기본 도형(2회차 생성기와 같은 그림체) ─────────────────────────

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


def check_badge(cx, cy, r=20, fill=SKY):
    """받아들여진 것: 하늘색 원과 체크. ✕와 같은 무게로 둘 때는 fill을 흰색으로 준다."""
    return [circle(cx, cy, r, fill=fill, stroke=NAVY, sw=3.5 if fill == SKY else 4),
            path(f"M {cx - r * 0.45},{cy + 1} L {cx - r * 0.1},{cy + r * 0.38} L {cx + r * 0.5},{cy - r * 0.38}", stroke=NAVY, sw=5)]


def cross_badge(cx, cy, r=20):
    """걸린 것: 흰 원과 ✕."""
    d = r * 0.42
    return [circle(cx, cy, r, fill=WHITE, stroke=NAVY, sw=4),
            line(cx - d, cy - d, cx + d, cy + d, stroke=NAVY, sw=5), line(cx + d, cy - d, cx - d, cy + d, stroke=NAVY, sw=5)]


# ───────────────────────── 아이콘(원점 기준, 높이 약 100) ─────────────────────────

def gauge(st: St, r=36, ang=-40, band=False):
    """계기: 원 + 눈금 + 바늘. band면 기준 띠(하늘색 호)를 그려 바늘이 그 안에 든 모습."""
    o = [circle(0, 0, r, fill=st.fill if band else st.accent, stroke=st.line)]
    if band:
        a0, a1 = math.radians(-115), math.radians(-65)
        rr = r - 9
        o.append(path(f"M {rr * math.cos(a0):.1f},{rr * math.sin(a0):.1f} A {rr} {rr} 0 0 1 {rr * math.cos(a1):.1f},{rr * math.sin(a1):.1f}",
                      stroke=SKY, sw=10))
    for a in (-150, -90, -30):
        ra = math.radians(a)
        o.append(line((r - 6) * math.cos(ra), (r - 6) * math.sin(ra), (r - 2) * math.cos(ra), (r - 2) * math.sin(ra), stroke=st.line, sw=2.5))
    ra = math.radians(ang)
    o += [line(0, 2, (r - 9) * math.cos(ra), 2 + (r - 9) * math.sin(ra), stroke=st.line, sw=4), circle(0, 2, 4, fill=st.line, stroke=st.line, sw=1)]
    return o


def fan_icon(st: St, r=38):
    o = [circle(0, 0, r, fill=st.fill, stroke=st.line)]
    for i in range(4):
        o.append(ellipse(0, -r * 0.52, r * 0.21, r * 0.4, fill=st.accent, stroke=st.line, sw=3, transform=f"rotate({20 + i * 90} 0 0)"))
    o.append(circle(0, 0, r * 0.17, fill=st.line, stroke=st.line, sw=2))
    return o


def radiator(x, y, w, h, st: St, fins=12, r=8):
    o = [rect(x, y, w, h, r, fill=st.fill, stroke=st.line)]
    step = (w - 20) / (fins - 1)
    for i in range(fins):
        fx = x + 10 + i * step
        o.append(line(fx, y + 10, fx, y + h - 10, stroke=GREY, sw=2))
    return o


def cooler_icon(st: St):
    """오일 쿨러: 핀이 든 방열 몸체와 양옆의 기름 통, 들고 나는 관."""
    o = radiator(-36, -34, 72, 68, st, fins=7, r=6)
    for sx in (-1, 1):
        o.append(rect(sx * 44 - 8, -40, 16, 80, 6, fill=st.accent, stroke=st.line))
    o += [line(-52, -24, -64, -24, stroke=st.line, sw=6), line(52, 24, 64, 24, stroke=st.line, sw=6)]
    return o


def dust_icon(st: St):
    """쿨러 핀 오염: 방열 핀 위에 낀 먼지 덩이."""
    o = radiator(-40, -34, 80, 68, st, fins=8, r=6)
    for x, y, r in ((-18, -10, 9), (6, 8, 11), (22, -16, 7), (-8, 18, 7), (-28, 12, 5)):
        o.append(circle(x, y, r, fill=GREY, stroke=st.line, sw=2.5))
    return o


def wash_icon(st: St):
    """쿨러 핀 세척: 방열 핀과 그 위로 떨어지는 물방울."""
    o = radiator(-40, -6, 80, 46, st, fins=8, r=6)
    for x in (-24, 0, 24):
        o.append(path(f"M {x},-46 C {x - 9},-34 {x - 9},-22 {x},-22 C {x + 9},-22 {x + 9},-34 {x},-46 Z", fill=st.accent, stroke=st.line, sw=3))
    return o


def equip_icon(st: St):
    """설비(유압 파워팩): 탱크 위에 모터와 펌프."""
    return [rect(-46, 4, 92, 42, 6, fill=st.soft, stroke=st.line),
            path("M -40,20 q 10,-6 20,0 t 20,0 t 20,0 t 20,0", stroke=st.line, sw=2),
            rect(-40, -38, 46, 32, 9, fill=st.fill, stroke=st.line),
            line(-28, -31, -28, -13, stroke=st.line, sw=2), line(-17, -31, -17, -13, stroke=st.line, sw=2),
            line(-6, -31, -6, -13, stroke=st.line, sw=2), line(6, -22, 14, -22, stroke=st.line, sw=5),
            circle(28, -22, 15, fill=st.accent, stroke=st.line), line(28, -7, 28, 30, stroke=st.line, sw=4),
            line(-30, -6, -30, 4, stroke=st.line), line(-4, -6, -4, 4, stroke=st.line)]


def equip2_icon(st: St):
    """다른 기종의 설비: 낮은 탱크 옆에 세운 모터와 펌프(부품 자리가 다르다)."""
    return [rect(-48, -6, 60, 50, 6, fill=st.soft, stroke=st.line),
            path("M -42,14 q 8,-6 16,0 t 16,0 t 16,0", stroke=st.line, sw=2),
            rect(20, -40, 28, 50, 9, fill=st.fill, stroke=st.line),
            line(26, -28, 42, -28, stroke=st.line, sw=2), line(26, -18, 42, -18, stroke=st.line, sw=2), line(26, -8, 42, -8, stroke=st.line, sw=2),
            circle(34, 28, 15, fill=st.accent, stroke=st.line),
            line(12, 28, 19, 28, stroke=st.line, sw=4),
            rect(-34, -22, 30, 16, 5, fill=st.fill, stroke=st.line, sw=3)]


def person_icon(st: St, role=""):
    """사람: 머리와 어깨. role = worker(안전모) · owner(체크 표시를 든 담당자)."""
    o = [path("M -32,42 Q -32,4 0,4 Q 32,4 32,42 Z", fill=st.accent, stroke=st.line),
         circle(0, -22, 18, fill=st.fill, stroke=st.line)]
    if role == "worker":
        o += [path("M -20,-27 A 20 20 0 0 1 20,-27 Z", fill=st.line, stroke=st.line, sw=2), line(-26, -27, 26, -27, stroke=st.line, sw=5)]
    if role == "owner":
        o += [circle(30, 30, 16, fill=WHITE, stroke=st.line, sw=3.5), path("M 22,31 L 28,37 L 38,24", stroke=st.line, sw=4.5)]
    return o


def sop_icon(st: St):
    """SOP 한 편: 머리 띠와 번호 붙은 줄이 있는 문서."""
    o = [rect(-40, -52, 80, 104, 8, fill=st.fill, stroke=st.line), rect(-40, -52, 80, 22, 8, fill=st.accent, stroke=st.line)]
    for y in (-14, 8, 30):
        o += [circle(-24, y, 4.5, fill=st.line, stroke=st.line, sw=1), line(-12, y, 26, y, stroke=st.line, sw=3)]
    return o


def lock_icon(st: St):
    """잠금: 자물쇠와 그 옆에 건 표지(꼬리표)."""
    return [path("M -30,-8 L -30,-24 A 18 18 0 0 1 6,-24 L 6,-8", stroke=st.line, sw=6),
            rect(-42, -8, 60, 50, 9, fill=st.accent, stroke=st.line),
            circle(-12, 12, 6, fill=st.line, stroke=st.line, sw=1), line(-12, 14, -12, 27, stroke=st.line, sw=5),
            line(18, 0, 30, -6, stroke=st.line, sw=3),
            path("M 30,-14 L 48,-14 L 48,22 L 39,30 L 30,22 Z", fill=st.fill, stroke=st.line, sw=3),
            line(35, 2, 43, 2, stroke=st.line, sw=2.5), line(35, 11, 43, 11, stroke=st.line, sw=2.5)]


def calendar_icon(st: St):
    """달력: 머리 띠, 고리 둘, 날짜 칸과 표시한 하루."""
    o = [rect(-40, -34, 80, 76, 9, fill=st.fill, stroke=st.line), rect(-40, -34, 80, 24, 9, fill=st.accent, stroke=st.line),
         line(-20, -44, -20, -28, stroke=st.line, sw=5), line(20, -44, 20, -28, stroke=st.line, sw=5)]
    for i, x in enumerate((-22, 0, 22)):
        for j, y in enumerate((4, 24)):
            hit = (i, j) == (1, 1)
            o.append(rect(x - 7, y - 7, 14, 14, 3, fill=st.line if hit else GREY, stroke="none", sw=0))
    return o


def tools_icon(st: St):
    """공구: 스패너와 드라이버."""
    return [line(34, 34, -6, -6, stroke=st.line, sw=5), rect(-34, -40, 16, 36, 6, fill=st.fill, stroke=st.line, sw=3, transform="rotate(-45 -16 -16)"),
            line(-30, 34, 12, -8, stroke=st.line, sw=12), line(-30, 34, 12, -8, stroke=st.accent, sw=5),
            circle(22, -20, 18, fill=st.accent, stroke=st.line), poly([(22, -22), (34, -46), (48, -32)], fill=WHITE),
            line(24, -22, 36, -34, stroke=WHITE, sw=10)]


def stop_icon(st: St):
    """정지: 둥근 버튼 안의 네모."""
    return [circle(0, 0, 40, fill=st.fill, stroke=st.line), rect(-17, -17, 34, 34, 6, fill=st.accent, stroke=st.line)]


def plug_icon(st: St):
    """에너지 차단: 콘센트에서 뽑아 떨어뜨린 플러그."""
    return [rect(26, -24, 22, 48, 6, fill=st.fill, stroke=st.line), line(34, -9, 40, -9, stroke=st.line, sw=4), line(34, 9, 40, 9, stroke=st.line, sw=4),
            rect(-30, -17, 30, 34, 8, fill=st.accent, stroke=st.line), line(0, -8, 12, -8, stroke=st.line, sw=5), line(0, 8, 12, 8, stroke=st.line, sw=5),
            path("M -30,0 Q -44,0 -44,14 Q -44,30 -56,30", stroke=st.line, sw=5)]


def hand_icon(st: St):
    """손: 편 손바닥."""
    o = [path("M -24,6 L -40,-10 Q -45,-18 -38,-22 Q -32,-24 -26,-17 L -18,-8 Z", fill=st.fill, stroke=st.line, sw=3)]
    for x, h in ((-24, 36), (-11, 44), (2, 42), (15, 34)):
        o.append(rect(x, -h, 11, h + 12, 5.5, fill=st.fill, stroke=st.line, sw=3))
    o.append(rect(-24, -4, 50, 46, 14, fill=st.fill, stroke=st.line, sw=3))
    o.append(rect(-21, -8, 44, 18, 6, fill=st.fill, stroke="none", sw=0))
    return o


def work_icon(st: St):
    """작업: 스패너 자루를 쥔 손(네 손가락과 엄지)."""
    o = [line(0, -22, 0, 46, stroke=st.line, sw=13), line(0, -22, 0, 46, stroke=st.accent, sw=6),
         circle(0, -32, 17, fill=st.accent, stroke=st.line), poly([(-9, -34), (-9, -54), (9, -54), (9, -34)], fill=WHITE),
         line(-9, -50, -9, -36, stroke=st.line, sw=3.5), line(9, -50, 9, -36, stroke=st.line, sw=3.5), line(-9, -36, 9, -36, stroke=st.line, sw=3.5),
         rect(-26, -8, 46, 42, 11, fill=st.fill, stroke=st.line, sw=3.5)]
    o += [line(-26, y, 6, y, stroke=st.line, sw=2.5) for y in (3, 13, 23)]
    o.append(rect(10, -14, 18, 30, 9, fill=st.fill, stroke=st.line, sw=3.5))
    return o


def server_icon(st: St):
    """위에서 명령을 내리는 서버: 세 단 장비와 표시등."""
    o = []
    for y in (-40, -12, 16):
        o += [rect(-38, y, 76, 24, 6, fill=st.fill, stroke=st.line), circle(-24, y + 12, 4, fill=st.accent, stroke=st.line, sw=2),
              line(-8, y + 12, 24, y + 12, stroke=st.line, sw=3)]
    return o


def monitor_icon(st: St):
    """관제 화면: 모니터와 그 안의 설비 표시."""
    return [rect(-42, -36, 84, 58, 7, fill=st.fill, stroke=st.line), rect(-32, -27, 64, 40, 3, fill=st.accent, stroke="none", sw=0),
            path("M -24,6 L -10,-8 L 2,0 L 22,-16", stroke=st.line, sw=3),
            line(0, 22, 0, 36, stroke=st.line, sw=5), line(-22, 38, 22, 38, stroke=st.line, sw=5)]


def panel_icon(st: St):
    """설비 옆 조작 패널: 함 안의 표시등, 누름 버튼, 선택 스위치."""
    return [rect(-32, -42, 64, 84, 7, fill=st.fill, stroke=st.line),
            circle(-12, -22, 7, fill=st.accent, stroke=st.line, sw=3), circle(12, -22, 7, fill=st.fill, stroke=st.line, sw=3),
            rect(-20, -4, 40, 12, 4, fill=GREY, stroke="none", sw=0),
            circle(0, 24, 11, fill=st.fill, stroke=st.line, sw=3), line(0, 24, 7, 15, stroke=st.line, sw=4)]


def stack_icon(st: St):
    """조치 후보: 겹쳐 놓은 카드 둘."""
    o = [rect(-30, -42, 76, 56, 9, fill=st.soft, stroke=st.line), rect(-46, -18, 76, 56, 9, fill=st.fill, stroke=st.line)]
    o += [line(-34, -2, 14, -2, stroke=st.line, sw=4), line(-34, 12, 18, 12, stroke=GREY, sw=3), line(-34, 24, 6, 24, stroke=GREY, sw=3)]
    return o


def sieve_icon(st: St):
    """체: 테두리와 그물 바닥, 아래로 걸러져 떨어진 알갱이."""
    o = [path("M -56,-26 Q -50,26 0,28 Q 50,26 56,-26 Z", fill=st.soft, stroke=st.line)]
    for x in (-32, -16, 0, 16, 32):
        o.append(line(x, -18, x * 0.86, 22 - abs(x) * 0.12, stroke=GREY, sw=2))
    for y in (-8, 8):
        hw = 50 - (y + 26) * 0.35
        o.append(line(-hw, y, hw, y, stroke=GREY, sw=2))
    o += [ellipse(0, -26, 56, 12, fill=st.fill, stroke=st.line), line(56, -26, 74, -34, stroke=st.line, sw=6)]
    o += [circle(-14, 42, 5, fill=GREY, stroke=st.line, sw=2.5), circle(8, 50, 5, fill=GREY, stroke=st.line, sw=2.5)]
    return o


def scale_icon(st: St):
    """저울: 기둥과 가로대, 양쪽 접시."""
    o = [line(0, -40, 0, 42, stroke=st.line, sw=5), rect(-26, 42, 52, 9, 4, fill=st.soft, stroke=st.line),
         line(-50, -34, 50, -46, stroke=st.line, sw=5), circle(0, -40, 6, fill=st.fill, stroke=st.line, sw=3)]
    for x, y in ((-50, -34), (50, -46)):
        o += [line(x, y, x - 20, y + 40, stroke=st.line, sw=2.5), line(x, y, x + 20, y + 40, stroke=st.line, sw=2.5),
              path(f"M {x - 24},{y + 40} Q {x},{y + 62} {x + 24},{y + 40} Z", fill=st.accent, stroke=st.line, sw=3)]
    return o


def warn_icon(st: St):
    """위험 표시: 세모 안의 느낌표."""
    return [path("M 0,-34 L 36,28 L -36,28 Z", fill=st.fill, stroke=st.line, sw=5), line(0, -12, 0, 8, stroke=st.line, sw=6),
            circle(0, 19, 3.5, fill=st.line, stroke=st.line, sw=1)]


ICONS = {  # 종류: (그리는 함수, 배율)
    "cooler": (cooler_icon, 0.8), "dust": (dust_icon, 0.82), "wash": (wash_icon, 0.86), "fan": (fan_icon, 1.0),
    "equip": (equip_icon, 0.8), "equip2": (equip2_icon, 0.8),
    "person": (person_icon, 0.9), "worker": (lambda st: person_icon(st, "worker"), 0.9), "owner": (lambda st: person_icon(st, "owner"), 0.9),
    "sop": (sop_icon, 0.78), "lock": (lock_icon, 0.9), "calendar": (calendar_icon, 0.86), "tools": (tools_icon, 0.86),
    "stop": (stop_icon, 0.9), "plug": (plug_icon, 0.9), "gauge0": (lambda st: gauge(st, ang=-150), 1.0), "hand": (hand_icon, 0.9), "work": (work_icon, 0.9),
    "server": (server_icon, 0.84), "monitor": (monitor_icon, 0.84), "panel": (panel_icon, 0.84),
    "stack": (stack_icon, 0.9), "sieve": (sieve_icon, 0.86), "scale": (scale_icon, 0.86), "warn": (warn_icon, 0.9),
}


def card_icon(kind, cx, cy, k=1.0):
    """원판 안 큰 아이콘. (cx, cy)는 아이콘 가운데, k는 배율(1.0 = 높이 약 100)."""
    fn, s = ICONS[kind]
    return g(cx, cy, s * k, fn(ON))


# ───────────────────────── 카드와 라벨 ─────────────────────────

class Fig:
    """그림 한 장: SVG 조각과, 그 위에 덱 MD로 얹을 라벨 자리. 라벨을 모아 두었다가 fin(위, 아래)에서
    본문 덩어리를 그림 세로 가운데로 옮겨 좌표를 낸다."""

    def __init__(self, name):
        self.name, self.o, self.labels, self.raw, self.dy = name, [], [], [], 0

    def add(self, parts):
        self.o += parts

    def lab(self, title, desc, x, y, w, strong=False):
        """라벨 하나. title이 비면 설명 줄만(작은 글씨) 쓴다. strong이면 제목을 강조색으로."""
        self.raw.append((title, desc, x, y, w, strong))

    def fin(self, top, bot):
        assert bot - top <= FH, (self.name, top, bot)
        self.dy = round((FH - top - bot) / 2)
        for title, desc, x, y, w, strong in self.raw:
            t = f"**{title}**" if (strong and title) else title
            pos = f"{x / 12:.2f},{(y + self.dy) / 5.1:.2f},{w / 12:.2f}"
            self.labels.append(" | ".join([t, desc, pos]).replace(" |  | ", " | | ").strip())
        return self

    def svg(self):
        return svg([f'<g transform="translate(0 {self.dy})">', *self.o, "</g>"])


def box(x, y, w, h, hot=False, r=22):
    return [rect(x, y, w, h, r, fill=PALE if hot else WHITE, stroke=BLUE if hot else NAVY, sw=5 if hot else 3)]


def disc(cx, cy, r, kind, ring=False, edge=False):
    """아이콘 원판. ring이면 원판을 비운 테두리 원(클래스 카드), edge면 파란 테두리를 두른 원판(강조)."""
    if ring:
        return [circle(cx, cy, r, fill=WHITE, stroke=NAVY, sw=3)]
    return [circle(cx, cy, r, fill=PALE, stroke=BLUE if edge else "none", sw=5 if edge else 0)] + card_icon(kind, cx, cy, r / 62)


def nlines(desc):
    return len(desc.split(" / ")) if desc else 0


def vcard(f: Fig, cx, top, w, h, kind, cls, name, r=40):
    """세로 인스턴스 카드(높이 고정): 큰 아이콘 원판 아래 클래스(작은 파란 글)와 이름(굵은 글) 한 덩어리. 돌려주는 값: 카드 가운데 y."""
    hh = 2 * r + 12 + (28 if cls else 0) + 32
    y = top + (h - hh) / 2
    f.add(box(cx - w / 2, top, w, h) + disc(cx, y + r, r, kind))
    y += 2 * r + 12 - 5
    if cls:
        f.lab("", f"**{cls}**", cx, y, w - 24)
        y += 28
    f.lab(name, "", cx, y, w - 20)
    return top + h / 2


def hcard(f: Fig, cx, cy, w, h, kind, name, desc="", *, ring=False, hot=False, strong=False):
    """가로 카드: 왼쪽 큰 아이콘 원판, 오른쪽에 이름(굵게)과 한 줄. ring이면 원판을 비운 클래스 카드, hot이면 파란 테두리."""
    x0, x1 = cx - w / 2, cx + w / 2
    r = h / 2 - 14
    dx = x0 + 14 + r
    f.add([rect(x0, cy - h / 2, w, h, 20, fill=WHITE, stroke=BLUE if hot else NAVY, sw=5 if hot else 3)] + disc(dx, cy, r, kind, ring))
    tx0 = dx + r + 8
    f.lab(name, desc, (tx0 + x1) / 2, cy - (LH_T + nlines(desc) * LH_D) / 2 - 6, x1 - tx0 - 6, strong=strong)


def tcard(f: Fig, cx, cy, w, h, title, desc="", *, hot=False, strong=False):
    """글만 든 카드: 이름(굵게)과 한 줄."""
    f.add(box(cx - w / 2, cy - h / 2, w, h, hot, r=20))
    f.lab(title, desc, cx, cy - (LH_T + nlines(desc) * LH_D) / 2 - 6, w - 16, strong=strong)


def chip(f, x, y, w, text, h=46):
    """이름 칸 하나(회색)."""
    f.add([rect(x, y, w, h, 10, fill=GREY, stroke="none", sw=0)])
    f.lab(text, "", x + w / 2, y + h / 2 - 19, w - 10)


def band_rect(y0, y1, color, x0=0, x1=1200, r=24):
    return [rect(x0, y0, x1 - x0, y1 - y0, r, fill=color, stroke="none", sw=0)]


def rel(f, x1, x2, y, name, color=NAVY, lift=46):
    """가로 관계 화살표. 이름은 화살표 위 가운데에 붙인다."""
    f.add(arrow([(x1, y), (x2, y)], color))
    if name:
        f.lab(name, "", (x1 + x2) / 2, y - lift, abs(x2 - x1) + 16)


def foot(f, text, y, cx=600, w=1100):
    """그림 맨 아래 굵은 결론 한 줄. 돌려주는 값: 아래 y."""
    f.lab(text, "", cx, y, w)
    return y + 5 + LH_T


def panel(f, cx, top, w, h, term, desc, strong=True):
    """칸 하나: 머리에 용어와 뜻 한 줄, 그 아래 가는 줄. 돌려주는 값: 가는 줄의 y."""
    f.add(box(cx - w / 2, top, w, h))
    f.lab(term, desc, cx, top + 12, w - 30, strong=strong)
    y = top + 12 + 5 + LH_T + LH_D + 12
    f.add([line(cx - w / 2 + 24, y, cx + w / 2 - 24, y, stroke=GREY, sw=2.5)])
    return y


# ───────────────────────── 1단원(5~19장) ─────────────────────────

def u05():
    """5장: 왼쪽은 진단(고장 유형 · 원인 카드), 가운데는 고장 유형에서 관계로 나온 조치 후보 둘, 오른쪽은 조치 결정
    (추천안의 조치 · 대안 · 이유 가운데 이유 칸만 빈 파란 점선 칸, 그 칸을 받는 담당자와 물음 셋)."""
    f = Fig("카드_진단과조치결정.svg")
    X1, X2, X3, X4, T, H, G = 150, 480, 800, 1085, 76, 176, 22
    f.lab("진단", "증거로 원인을 가린다", X1, 0, 280)
    f.lab("조치 결정", "무엇을 할지 정한다", (X3 + X4) / 2, 0, 400)
    y1 = vcard(f, X1, T, 270, H, "cooler", "고장 유형", "쿨러 냉각 성능 상실")
    y2 = vcard(f, X1, T + H + G, 270, H, "dust", "원인", "쿨러 핀 오염")
    f.lab("조치 후보", "", X2, T - 46, 200, strong=True)
    vcard(f, X2, T, 230, H, "fan", "", "팬 최대 운전")
    vcard(f, X2, T + H + G, 230, H, "wash", "", "쿨러 핀 세척")
    a0, a1, bx = X1 + 135 + 8, X2 - 115 - 8, (X1 + 135 + X2 - 115) / 2
    f.add(arrow([(a0, y1), (a1, y1)]) + arrow([(bx, y1), (bx, y2), (a1, y2)]))
    # 추천안
    w, top, my = 260, (y1 + y2) / 2 - 117, (y1 + y2) / 2
    x0 = X3 - w / 2
    mx = X2 + 115 + 8 + 26
    f.add([line(X2 + 123, y1, mx, y1, sw=5), line(X2 + 123, y2, mx, y2, sw=5), line(mx, y1, mx, y2, sw=5)] + arrow([(mx, my), (x0 - 8, my)]))
    f.add(box(x0, top, w, 234))
    f.lab("추천안", "", X3, top + 12, w - 30)
    ys = []
    for i, item in enumerate(("조치", "대안", "이유")):
        y = top + 58 + i * 56
        f.add([rect(x0 + 16, y, 84, 46, 10, fill=GREY, stroke="none", sw=0)])
        f.lab(item, "", x0 + 16 + 42, y + 4, 78)
        vx, vw = x0 + 108, w - 124
        if item == "이유":
            f.add(dash_rect(vx, y, vw, 46, BLUE, 4, 9, 7))
        else:
            f.add([rect(vx, y, vw, 46, 10, fill=WHITE, stroke=NAVY, sw=2), line(vx + 18, y + 23, vx + vw - 18, y + 23, stroke=GREY, sw=6)])
        ys.append(y + 23)
    # 담당자와 물음 셋
    r = 46
    f.add(arrow([(x0 + w + 8, ys[2]), (X4 - r - 8, ys[2])]) + disc(X4, ys[2], r, "owner"))
    f.lab("담당자", "", X4, ys[2] + r + 6, 140)
    bw, bt, bb = 216, T, ys[2] - r - 30
    bx0 = X4 - bw / 2
    f.add([path(f"M {bx0 + 18},{bt} L {bx0 + bw - 18},{bt} Q {bx0 + bw},{bt} {bx0 + bw},{bt + 18} L {bx0 + bw},{bb - 18} Q {bx0 + bw},{bb} {bx0 + bw - 18},{bb} "
                f"L {X4 + 14},{bb} L {X4},{bb + 18} L {X4 - 14},{bb} L {bx0 + 18},{bb} Q {bx0},{bb} {bx0},{bb - 18} L {bx0},{bt + 18} Q {bx0},{bt} {bx0 + 18},{bt} Z",
                fill=WHITE, sw=3)])
    step = (bb - bt - 16) / 3
    for i, q in enumerate(("어떻게 하나", "지금 해도 되나", "무엇이 나은가")):
        f.lab(q, "", X4, bt + 8 + i * step + step / 2 - 19, bw - 16)
    return f.fin(0, T + 2 * H + G)


def u06():
    """6장: 맨 위 가운데 조치 이름 한 줄(쪽지)이 두 사람에게 간다. 가운데 열이 줄 이름(시작할 때 · 닦을 때 · 끝낼 때)이고,
    그 양쪽에 두 사람이 저마다 정한 것을 같은 높이의 칸으로 둔다. 오른쪽 사람의 시작 칸에만 위험 표시."""
    f = Fig("카드_이름한줄_두사람.svg")
    XA, XB, cy, r = 280, 920, 50, 50
    f.add([path(f"M 480,{cy - 30} L 700,{cy - 30} L 720,{cy - 10} L 720,{cy + 30} L 480,{cy + 30} Z", fill=WHITE, sw=3),
           path(f"M 700,{cy - 30} L 700,{cy - 10} L 720,{cy - 10}", sw=3)])
    f.lab("쿨러 핀 세척", "", 600, cy - 19, 200)
    f.add(disc(XA, cy, r, "worker") + disc(XB, cy, r, "worker"))
    f.add(arrow([(472, cy), (XA + r + 10, cy)]) + arrow([(728, cy), (XB - r - 10, cy)]))
    ys = (164, 246, 328)
    rows = (("시작할 때", "세우고 잠근 뒤", "돌고 있는 채로"), ("닦을 때", "정해진 방향과 도구로", "손에 잡히는 대로"),
            ("끝낼 때", "다시 잰 냉각이 돌아오면", "보기에 깨끗하면"))
    for y, (nm, a, b) in zip(ys, rows):
        chip(f, 600 - 80, y - 23, 160, nm)
        for x, t in ((XA, a), (XB, b)):
            f.add([rect(x - 165, y - 31, 330, 62, 14, fill=WHITE, stroke=NAVY, sw=2.5)])
            f.lab(t, "", x, y - 19, 310)
    f.add(g(XB + 165 - 34, ys[0] - 1, 0.42, warn_icon(ON), boost=1.6))
    return f.fin(0, foot(f, "이름만으로는 무엇을 확인하고 어떤 차례로 하며 언제 끝낼지 알 수 없다", ys[2] + 31 + 30))


def sop_paper(DW=220, BH=84, P=98):
    """7 · 8장이 함께 쓰는 SOP 한 편(왼쪽 위가 원점): 머리 · 시작 전 · 하는 동안 · 끝낼 때의 네 부분. 돌려주는 값: (조각, 부분 가운데 y 목록)."""
    o = [rect(0, 0, DW, 3 * P + BH, 12, fill=WHITE, sw=3.5)]
    for i in range(1, 4):
        y = i * P - (P - BH) / 2
        o.append(line(14, y, DW - 14, y, stroke=GREY, sw=2.5))
    c = [i * P + BH / 2 for i in range(4)]
    L, R = 28, DW - 28
    o += [line(L, c[0] - 14, L + 96, c[0] - 14, sw=7), line(L, c[0] + 12, R - 20, c[0] + 12, stroke=GREY, sw=4)]
    for dy in (-15, 15):
        o += [rect(L, c[1] + dy - 9, 18, 18, 4, fill=WHITE, sw=3), line(L + 32, c[1] + dy, R - (0 if dy < 0 else 34), c[1] + dy, stroke=GREY, sw=4)]
    for k, dy in enumerate((-22, 0, 22)):
        o += [circle(L + 8, c[2] + dy, 6, fill=NAVY, sw=1), line(L + 32, c[2] + dy, R - (0, 40, 16)[k], c[2] + dy, stroke=GREY, sw=4)]
    o += check_badge(L + 12, c[3], 13) + [line(L + 40, c[3], R - 24, c[3], stroke=GREY, sw=4)]
    return o, c


def u07():
    """7장: 왼쪽에 SOP 한 편(문서의 네 부분), 오른쪽에 같은 폭의 구역 띠 넷. 문서의 부분마다 가는 선으로 그 띠에 잇는다."""
    f = Fig("카드_SOP_생김새.svg")
    DX, DW, BX, BW, T, BH, P = 240, 220, 500, 580, 70, 84, 98
    x0 = DX - DW / 2
    f.lab("SOP", "Standard Operating Procedure", DX, 0, 330)
    parts, c0 = sop_paper(DW, BH, P)
    f.add(g(x0, T, 1, parts, boost=1.0))
    c = [T + y for y in c0]
    names = (("머리", "누구에게 쓰고 누가 하나"), ("시작 전", "무엇이 맞아야 시작하나"), ("하는 동안", "어떤 차례로 하고 무엇을 하지 않나"),
             ("끝낼 때", "무엇을 보고 끝났다고 하나"))
    for y, (nm, q) in zip(c, names):
        f.add([line(x0 + DW + 8, y, BX - 10, y, sw=2.5), circle(x0 + DW + 8, y, 4.5, fill=NAVY, sw=1)])
        tcard(f, BX + BW / 2, y, BW, BH, nm, q)
    return f.fin(0, T + 3 * P + BH)


def u08():
    """8장: 가운데 SOP 한 편(7장과 같은 문서 조각)에서 같은 꼴의 세 사람 카드(왼쪽 작업자 · 오른쪽 담당자 · 아래 처음 맡은 사람)로 화살표가 간다."""
    f = Fig("카드_SOP_세사람.svg")
    cy, W, H, by = 66, 380, 104, 296
    k = 0.32
    f.add(g(600 - 110 * k, cy - 189 * k, k, sop_paper()[0], boost=1.7))
    f.lab("SOP", "", 600, cy + 68, 120)
    hcard(f, 200, cy, W, H, "worker", "작업자", "차례대로 따른다")
    hcard(f, 1000, cy, W, H, "owner", "담당자", "조건과 끝 기준으로 확인한다")
    hcard(f, 600, by, W, H, "person", "처음 맡은 사람", "그대로 배운다")
    f.add(arrow([(600 - 56, cy), (200 + W / 2 + 8, cy)]) + arrow([(600 + 56, cy), (1000 - W / 2 - 8, cy)])
          + arrow([(600, cy + 112), (600, by - H / 2 - 8)]))
    return f.fin(0, foot(f, "사람이 바뀌어도 같은 일이 같은 기준으로 끝난다", by + H / 2 + 24))


def u09():
    """9장: SOP 머리 구역의 두 칸. 왼쪽 적용 대상 칸에는 기종이 다른 설비 둘과 따로 적는 까닭, 오른쪽 담당 역할 칸에는 수행 · 승인 두 역할."""
    f = Fig("카드_머리_두칸.svg")
    W, H, r = 540, 326, 56
    for cx, term, q in ((310, "적용 대상", "어느 설비의 어떤 상황에 쓰나"), (890, "담당 역할", "누가 하고 누가 승인하나")):
        y = panel(f, cx, 0, W, H, term, q)
    iy = y + 26 + r
    f.add(disc(220, iy, r, "equip") + disc(400, iy, r, "equip2"))
    f.lab("", "같은 이름의 정비도 기종마다 부품 자리와 차례가 달라, / 기종마다 따로 적는다", 310, iy + r + 14, W - 40)
    for x, kind, a, b in ((800, "worker", "수행", "정비 작업자"), (980, "owner", "승인", "보전 책임자")):
        f.add(disc(x, iy, r, kind))
        f.lab(a, b, x, iy + r + 8, 170)
    return f.fin(0, foot(f, "누가 승인할지가 적혀 있어야, 그 조치를 승인할 담당자가 정해진다", H + 30))


XS3 = (216, 600, 984)


def u10():
    """10장: 같은 꼴 · 같은 폭의 칸 셋. 칸 머리에 용어와 뜻, 칸 안에 아이콘 하나(달력 · 자물쇠 · 공구)와 예 한 줄."""
    f = Fig("카드_시작전_세칸.svg")
    W, H, r = 350, 360, 72
    spec = (("작업 전제 조건", "이 작업을 시작해도 되는 상태", "calendar", "생산 계획상 설비를 세워도 되는 때"),
            ("안전 조건", "사람이 다치지 않을 설비 상태", "lock", "설비를 세우고 잠근 뒤"),
            ("준비사항", "손대기 전에 갖출 것", "tools", "공구 · 부품 · 보호구"))
    for cx, (term, q, kind, ex) in zip(XS3, spec):
        y = panel(f, cx, 0, W, H, term, q)
        f.add(disc(cx, y + 30 + r, r, kind))
        f.lab("", ex, cx, y + 30 + 2 * r + 18, W - 30)
    return f.fin(0, foot(f, "하나라도 맞지 않으면 시작하지 않는다", H + 36))


def u11():
    """11장: 같은 꼴의 원판 다섯을 한 방향 화살표로 잇는다(정지 · 플러그 차단 · 자물쇠와 표지 · 바늘이 0인 압력계 · 손).
    풀 자리인 잠금 원판에만 파란 테두리."""
    f = Fig("카드_정지와잠금.svg")
    xs, r, cy = (110, 355, 600, 845, 1090), 88, 88
    spec = (("정지", "설비를 세운다", "stop"), ("에너지 차단", "전기와 유압을 끊는다", "plug"), ("잠금", "잠금장치와 표지를 건다", "lock"),
            ("남은 압력 확인", "빼고 0인지 본다", "gauge0"), ("작업", "이제 손댄다", "work"))
    for i, (x, (nm, d, kind)) in enumerate(zip(xs, spec)):
        f.add(disc(x, cy, r, kind, edge=nm == "잠금"))
        f.lab(nm, d, x, cy + r + 24, 228, strong=nm == "잠금")
        if i:
            f.add(arrow([(xs[i - 1] + r + 12, cy), (x - r - 12, cy)]))
    return f.fin(0, foot(f, "멈춘 설비에도 압력과 전기가 남고, 누군가 다시 켤 수 있다", cy + r + 24 + 5 + LH_T + LH_D + 46))


def u12():
    """12장: 앞 장의 세 칸과 같은 꼴. 수행 단계 칸은 번호 붙은 줄 셋, 금지 사항 칸은 ✕ 줄 둘, 완료 확인 기준 칸은 바늘이 기준 띠 안으로
    돌아온 계기와 예 한 줄."""
    f = Fig("카드_하는동안_끝낼때.svg")
    W, H, r = 350, 360, 72
    spec = (("수행 단계", "어떤 차례로 하나"), ("금지 사항", "언제나 하지 않을 것"), ("완료 확인 기준", "무엇을 보면 끝났나"))
    for cx, (term, q) in zip(XS3, spec):
        y = panel(f, cx, 0, W, H, term, q)
    my = (y + H) / 2
    cx = XS3[0]
    for k, dy in enumerate((-66, 0, 66)):
        f.add([circle(cx - 100, my + dy, 18, fill=PALE, sw=3)] + [circle(cx - 100 + (j - k / 2) * 10, my + dy, 3, fill=NAVY, sw=1) for j in range(k + 1)]
              + [line(cx - 64, my + dy, cx + (116, 72, 100)[k], my + dy, stroke=GREY, sw=8)])
    cx = XS3[1]
    for dy in (-42, 42):
        f.add(cross_badge(cx - 100, my + dy, 20) + [line(cx - 62, my + dy, cx + (116 if dy < 0 else 78), my + dy, stroke=GREY, sw=8)])
    cx = XS3[2]
    f.add([circle(cx, y + 30 + r, r, fill=PALE, stroke="none", sw=0)] + g(cx, y + 30 + r, 1.44, gauge(ON, r=36, ang=-82, band=True), boost=0.85))
    f.lab("", "다시 잰 값이 기준 안으로 돌아왔다", cx, y + 30 + 2 * r + 18, W - 30)
    return f.fin(0, foot(f, "보기에 깨끗한 것이 아니라 다시 잰 값으로 끝을 판정한다", H + 36))


def steps13(f, x0, w, tops, h, lines, hot=(0,)):
    """13장: 번호 붙은 수행 단계 줄. hot 줄(조건 문장)만 파란 테두리."""
    for i, (top, s) in enumerate(zip(tops, lines)):
        hi = i in hot
        f.add([rect(x0, top, w, h, 14, fill=PALE if hi else WHITE, stroke=BLUE if hi else NAVY, sw=4.5 if hi else 2.5),
               rect(x0 + 10, top + (h - 44) / 2, 44, 44, 10, fill=SKY if hi else GREY, stroke="none", sw=0)])
        f.lab(str(i + 1), "", x0 + 32, top + h / 2 - 19, 40)
        f.lab("", s, x0 + 64 + (w - 74) / 2, top + h / 2 - nlines(s) * LH_D / 2 - 5, w - 84)


def u13():
    """13장: 같은 폭의 SOP 둘(정비 작업 · 원격 조작)의 수행 단계 세 줄을 좌우에 나란히. 맨 왼쪽 여백의 표시(조건 · 차례)가 줄 갈래이고,
    두 SOP의 1번 줄(조건 문장)만 파란 테두리다."""
    f = Fig("카드_순서와조건.svg")
    tops, h, w = (52, 146, 240), 78, 510
    for x0, nm, lines in ((130, "정비 작업의 SOP", ("설비를 세우고 잠근 뒤에만 / 덮개를 연다", "정해진 방향으로 닦는다", "다시 돌려 냉각을 잰다")),
                          (680, "자동으로 내려오는 조치의 SOP", ("자동으로 내려오는 명령을 / 받는 상태일 때만 진행한다", "출력을 정해진 값으로 올린다", "다시 재 본다"))):
        f.lab(nm, "", x0 + w / 2, 0, 400)
        steps13(f, x0, w, tops, h, lines)
    f.lab("조건", "", 56, tops[0] + h / 2 - 19, 90, strong=True)
    f.lab("차례", "", 56, (tops[1] + tops[2] + h) / 2 - 19, 90)
    f.add([path(f"M 116,{tops[1] + 6} L 106,{tops[1] + 6} L 106,{tops[2] + h - 6} L 116,{tops[2] + h - 6}", sw=3)])
    return f.fin(0, foot(f, "조건 문장이 맞는지는 그때의 설비 값을 보고 판정한다", tops[2] + h + 30))


def source(f, cx, cy, mode, k=1.0):
    """조작이 오는 곳: auto = 서버, manual = 관제 화면 앞의 사람, local = 설비 옆 패널 앞의 사람. 옅은 받침 위에 그린다."""
    w, h = 190 * k, 96 * k
    f.add([rect(cx - w / 2, cy - h / 2, w, h, h / 2, fill=PALE, stroke="none", sw=0)])
    if mode == "auto":
        f.add(g(cx, cy, 0.72 * k, server_icon(ON)))
    else:
        f.add(g(cx - 40 * k, cy + 2 * k, 0.7 * k, person_icon(ON)) + g(cx + 38 * k, cy, 0.72 * k, (monitor_icon if mode == "manual" else panel_icon)(ON)))


MODES = (("auto", "원격 자동"), ("manual", "원격 수동"), ("local", "현장 제어"))


def u14():
    """14장: 같은 꼴 · 같은 폭의 장면 칸 셋. 칸마다 위쪽에 조작이 오는 곳, 아래쪽에 같은 설비, 둘을 잇는 화살표 하나."""
    f = Fig("카드_운전모드_세장면.svg")
    W, H = 320, 250
    descs = ("승인 뒤 위에서 자동으로 / 내려오는 명령을 받는다", "관제 화면에서 / 사람이 조작한다", "설비 옆 패널에서 / 사람이 조작한다")
    for cx, (mode, nm), d in zip(XS3, MODES, descs):
        f.add(box(cx - W / 2, 0, W, H))
        source(f, cx, 66, mode)
        f.add(arrow([(cx, 122), (cx, 150)]) + disc(cx, 196, 42, "equip"))
        f.lab(nm, d, cx, H + 8, W)
    return f.fin(0, foot(f, "운전 모드를 바꾸는 것은 에너지를 끊는 잠금이 아니다", H + 8 + 5 + LH_T + 2 * LH_D + 30))


def u15():
    """15장: 맨 위 조치 하나(자동으로 내려오는 명령)가 앞 장과 같은 자리의 세 모드 칸으로 내려간다. 원격 자동 칸에는 닿고(✓),
    사람이 조작하는 두 칸 앞에서는 걸린다(✕)."""
    f = Fig("카드_한조치_세모드.svg")
    W, H, T, by = 320, 112, 200, 118
    hcard(f, 600, 46, 470, 92, "fan", "팬 최대 운전", "승인 뒤 자동으로 내려오는 명령")
    f.add([line(600, 100, 600, by, sw=5), line(XS3[0], by, XS3[2], by, sw=5)])
    for cx, (mode, nm) in zip(XS3, MODES):
        ok = mode == "auto"
        f.add(box(cx - W / 2, T, W, H))
        if ok:
            f.add(arrow([(cx, by), (cx, T - 8)]) + check_badge(cx, by + 36, 18))
            f.add(disc(cx, T + H / 2, 40, "equip"))
        else:
            f.add([line(cx, by, cx, by + 18, sw=5)] + cross_badge(cx, by + 36, 18))
            source(f, cx - 62, T + H / 2, mode, 0.74)
            f.add(arrow([(cx + 14, T + H / 2), (cx + 40, T + H / 2)], sw=4, size=13) + disc(cx + 90, T + H / 2, 40, "equip"))
        f.lab(nm, "**받아들인다**" if ok else "**받아들이지 않는다**", cx, T + H + 8, W)
    return f.fin(0, foot(f, "사람이 조작하는 동안 자동으로 내려오는 명령이 끼어들면, 둘이 같은 설비를 서로 다르게 움직인다", T + H + 8 + 5 + LH_T + LH_D + 22))


CW16, CH16 = 190, 64


def u16():
    """16장: 옅은 하늘색 띠(클래스 층) 위에 같은 꼴 · 같은 폭의 클래스 카드(가로 알약: 빈 테두리 원과 이름) 넷을 같은 간격으로 한 줄에.
    카드 사이 화살표 위에 관계 이름. 고장 유형 아래에 같은 꼴의 원인 카드를 두고 원인 → 일으킨다 → 고장 유형으로 잇는다.
    이 장에서 푸는 조치 방법 · 작업 단계 카드만 파랗다. 맨 위에 역량 질문 한 줄."""
    f = Fig("카드_조치방법_스키마.svg")
    xs, W, cy, cy2 = (105, 435, 765, 1095), CW16, 216, 336
    f.add([rect(310, 0, 580, 68, 18, fill=WHITE, sw=3)])
    f.lab("역량 질문", "조치 후보마다 하는 법과 근거는", 600, 4, 540)
    f.add(band_rect(98, cy2 + CH16 / 2 + 20, PALE))
    for x, nm in zip(xs, ("고장 유형", "조치 방법", "작업 단계", "근거 문서")):
        hot = nm in ("조치 방법", "작업 단계")
        hcard(f, x, cy, W, CH16, "none", nm, ring=True, hot=hot, strong=hot)
    a = [(xs[i] + W / 2 + 8, xs[i + 1] - W / 2 - 8) for i in range(3)]
    for (x1, x2), nm in zip(a, ("근본 해결된다", "단계를 가진다", "참조한다")):
        f.add(arrow([(x1, cy), (x2, cy)]))
        f.lab(nm, "", (x1 + x2) / 2, cy - 74, 180)   # 이름은 카드 윗변보다 위에 두어 카드 사이보다 넓어도 된다
    f.lab("완화된다", "", (a[0][0] + a[0][1]) / 2, cy - 74 - LH_T - 4, 180)
    hcard(f, xs[0], cy2, W, CH16, "none", "원인", ring=True)
    f.add(arrow([(xs[0], cy2 - CH16 / 2 - 8), (xs[0], cy + CH16 / 2 + 8)]))
    f.lab("일으킨다", "", xs[0] + 78, (cy + cy2) / 2 - 19, 110)
    f.lab("", "앞에서 조치라 부른 클래스", xs[1], cy + CH16 / 2 + 10, 280)
    bot = cy2 + CH16 / 2 + 20
    return f.fin(0, foot(f, "이 예에서는 SOP 하나를 조치 방법 하나로, 수행 단계 하나를 작업 단계 하나로 적고, 단계마다 근거 문서를 단다", bot + 20, w=1190))


def mcard(f, cx, cy, w, h, cls, title, desc, hot=False):
    """글 카드: 머리에 작은 파란 클래스 이름, 그 아래 이름(굵게)과 한 줄."""
    f.add(box(cx - w / 2, cy - h / 2, w, h, hot, r=20))
    y = cy - (26 + LH_T + LH_D) / 2 - 6
    f.lab("", f"**{cls}**", cx, y, w - 16)
    f.lab(title, desc, cx, y + 26, w - 16, strong=hot)


def u17():
    """17장: 위에 시간 띠(고장 전 · 고장 · 고장 뒤). 고장 시점 아래에 고장 유형 클래스 카드(16장과 같은 꼴), 그 왼쪽(고장 전)에 예방 조치,
    오른쪽(고장 뒤)에 완화 조치 · 근본 조치. 세 칸 머리의 작은 파란 글이 같은 클래스(조치 방법)이고, 관계 이름이 셋을 가른다.
    화살표는 모두 고장 유형에서 나가는 가로 화살표이고 그 위에 관계 이름."""
    f = Fig("카드_예방완화근본_시간띠.svg")
    FX, AY, CY, W, H, CW_ = 585, 52, 248, 290, 116, CW16
    LX, RX, ry = 165, 1045, (164, 332)
    f.lab("고장 전", "", (30 + FX) / 2, 0, 200)
    f.lab("고장", "", FX, 0, 100)
    f.lab("고장 뒤", "", (FX + 1180) / 2, 0, 200)
    f.add(arrow([(30, AY), (1180, AY)], GREY, sw=6, size=18) + [circle(FX, AY, 11, fill=NAVY, sw=1)] + dash_line(FX, AY + 18, FX, CY - 44, GREY, 3.5, 8, 6))
    hcard(f, FX, CY, CW_, CH16, "none", "고장 유형", ring=True)
    mcard(f, LX, CY, W, H, "조치 방법", "예방 조치", "고장이 나기 전에 미리 막는다", hot=True)
    rel(f, FX - CW_ / 2 - 8, LX + W / 2 + 8, CY, "예방된다")
    f.lab("", "정해진 운전 시간이나 날짜마다 / 하는 점검과 교체", LX, CY + H / 2 + 10, W)
    bx = FX + CW_ / 2 + 30
    f.add([line(FX + CW_ / 2 + 2, CY, bx, CY, sw=5), line(bx, ry[0], bx, ry[1], sw=5)])
    for y, nm, d, rn in zip(ry, ("완화 조치", "근본 조치"), ("증상을 우선 낮춘다", "원인을 없앤다"), ("완화된다", "근본 해결된다")):
        mcard(f, RX, y, W, H, "조치 방법", nm, d)
        rel(f, bx, RX - W / 2 - 8, y, rn)
    return f.fin(0, ry[1] + H / 2)


def u18():
    """18장: 왼쪽에 같은 꼴의 조치 후보 카드 둘, 가운데에 후보마다 이어진 SOP 카드(작업 단계 줄과 근거 문서 꼬리표).
    SOP마다 조건 줄 하나(파랑)가 파란 선으로 오른쪽 판단의 재료 칸(흰 칸)에 모인다. 파란 강조는 그 조건 줄에만 건다."""
    f = Fig("카드_후보와SOP.svg")
    ys, SX, SW_, SH = (72, 248), 350, 400, 144
    bx, my = 820, (72 + 248) / 2
    for cy in ys:
        hcard(f, 150, cy, 250, 84, "stack", "조치 후보")
        f.add(arrow([(150 + 125 + 8, cy), (SX - 8, cy)]) + box(SX, cy - SH / 2, SW_, SH, r=20))
        f.lab("SOP", "작업 단계 / 근거 문서", SX + 100, cy - (LH_T + 2 * LH_D) / 2 - 6, 180)
        lx = SX + 210
        for k, dy in enumerate((-39, -13, 13, 39)):
            y = cy + dy
            if k == 1:
                f.add([line(lx, y, bx, y, stroke=BLUE, sw=6)])
                continue
            f.add([circle(lx + 5, y, 5, fill=NAVY, sw=1), line(lx + 22, y, lx + (112, 0, 96, 104)[k], y, stroke=GREY, sw=5),
                   path(f"M {lx + 134},{y - 8} L {lx + 160},{y - 8} L {lx + 168},{y} L {lx + 160},{y + 8} L {lx + 134},{y + 8} Z", fill=PALE, sw=2.5)])
    f.add([line(bx, ys[0] - 13, bx, ys[1] - 13, stroke=BLUE, sw=6)] + arrow([(bx, my - 13), (890 - 8, my - 13)], BLUE, sw=6))
    tcard(f, 1040, my - 13, 300, 112, "판단의 재료", "조건 문장")
    return f.fin(0, foot(f, "이름 한 줄이던 조치 후보에 하는 법 · 근거 · 조건이 함께 따라온다", ys[1] + SH / 2 + 30))


def flow4(f, xs, cy, counts=(3, 2, 1), r=80):
    """19 · 45장이 함께 쓰는 자리: 조치 후보 → 체 → 걸러 남은 후보 → 저울 → 고른 하나 → 담당자의 한 방향 흐름.
    xs = (후보, 체, 남은 후보, 저울, 고른 하나, 담당자)의 가운데 x, cy = 가운데 y, counts = 세 자리에 놓는 후보 카드 수.
    글자는 부르는 쪽이 얹는다. 돌려주는 값: (그림 위 y, 그림 아래 y)."""
    hw = 52
    for x, n in zip(xs[0::2], counts):
        for i in range(n):
            y = cy + (i - (n - 1) / 2) * 58
            f.add([rect(x - hw, y - 21, 2 * hw, 42, 10, fill=WHITE, sw=3), line(x - 32, y, x + 26, y, stroke=GREY, sw=6)])
    for x, kind in zip(xs[1::2], ("sieve", "scale", "owner")):
        f.add(disc(x, cy, r, kind))
    for i, (a, b) in enumerate(zip(xs, xs[1:])):
        ga, gb = (hw + 10, r + 12) if i % 2 == 0 else (r + 12, hw + 10)
        f.add(arrow([(a + ga, cy), (b - gb, cy)]))
    return cy - r, cy + r


def u19():
    """19장: 조치 후보 셋 → 체(허용 조건) → 남은 둘 → 저울(선택 근거) → 고른 하나 → 담당자. 체와 저울 위에 용어와 물음,
    체 아래에 출력 이름 셋(작은 글). 후보 카드의 수가 줄어드는 것이 거르고 견주는 일이다."""
    f = Fig("카드_체와저울.svg")
    xs, cy = (75, 275, 480, 690, 890, 1100), 150
    top, bot = flow4(f, xs, cy)
    ty = top - 22 - 5 - LH_T - LH_D
    f.lab("허용 조건", "SOP의 조건으로 지금 해도 되나", xs[1], ty, 310, strong=True)
    f.lab("선택 근거", "무엇이 나은가", xs[3], ty, 240, strong=True)
    f.lab("조치 후보", "", xs[0], bot + 20, 170)
    f.lab("담당자", "", xs[5], bot + 20, 170)
    f.lab("", "허용 · 제외 · 감점", xs[1], bot + 22, 240)
    y = foot(f, "운전 모드처럼 지금 상태에 달린 조건은 고르기 전에 거르고,", bot + 20 + 5 + LH_T + 40)
    return f.fin(ty, foot(f, "세우고 잠그는 안전 조건은 손대기 직전에 확인한다", y))


# ───────────────────────── 2단원(21~33장) ─────────────────────────

def agent_icon(st: St):
    """AI 에이전트: 안테나가 달린 둥근 머리와 두 눈."""
    return [line(0, -44, 0, -30, stroke=st.line, sw=4), circle(0, -46, 5, fill=st.accent, stroke=st.line, sw=3),
            rect(-36, -30, 72, 58, 16, fill=st.fill, stroke=st.line), circle(-14, -4, 6, fill=st.line, stroke=st.line, sw=1),
            circle(14, -4, 6, fill=st.line, stroke=st.line, sw=1), line(-10, 14, 10, 14, stroke=st.line, sw=3.5),
            line(-44, -8, -44, 8, stroke=st.line, sw=5), line(44, -8, 44, 8, stroke=st.line, sw=5),
            path("M -22,40 L 22,40", stroke=st.line, sw=5)]


def rules_icon(st: St):
    """판단 규칙: 머리 줄과 행 셋이 있는 결정표."""
    o = [rect(-42, -36, 84, 72, 8, fill=st.fill, stroke=st.line), rect(-42, -36, 84, 20, 8, fill=st.accent, stroke=st.line)]
    o += [line(-42, y, 42, y, stroke=st.line, sw=2) for y in (2, 19)]
    o.append(line(14, -16, 14, 36, stroke=st.line, sw=3))
    return o


ICONS.update({"agent": (agent_icon, 0.9), "rules": (rules_icon, 0.86)})


def dtable(f, x, y, cols, header, rows, rh=64, hh=54, gap=10, nout=1, dashed=()):
    """결정표: 머리 줄(회색)과 규칙 행들. 조건 열과 출력 열 사이는 굵은 세로줄로 가른다. 칸 값: 글 = 굵은 라벨,
    (글, 작은 글) = 두 줄 라벨, 「!」로 시작하면 강조색, None = 상관없음(짧은 가로선), "" = 빈 칸. header가 None이면 머리 줄을 그리지 않는다.
    dashed = 점선 테두리로 그릴 행 번호. 돌려주는 값: (칸마다의 (x0, x1), 행 가운데 y 목록, 아래 y)."""
    w, xs, cx = sum(cols), [], x
    for c in cols:
        xs.append((cx, cx + c))
        cx += c
    ox = xs[len(cols) - nout][0] if nout else x + w + 4
    ry = y
    if header is not None:
        f.add([rect(x, y, ox - x - 4, hh, 10, fill=GREY, stroke="none", sw=0)] + ([rect(ox + 4, y, x + w - ox - 4, hh, 10, fill=GREY, stroke="none", sw=0)] if nout else []))
        for (a, b), h in zip(xs, header):
            if h:
                f.lab(h, "", (a + b) / 2, y + hh / 2 - 19, b - a - 8)
        ry = y + hh + gap
    cys = []
    for i, row in enumerate(rows):
        if i in dashed:
            f.add([rect(x, ry, w, rh, 12, fill=WHITE, stroke="none", sw=0)] + dash_rect(x, ry, w, rh, NAVY, 3, 10, 7))
        else:
            f.add([rect(x, ry, w, rh, 12, fill=WHITE, stroke=NAVY, sw=2.5)])
        for k, ((a, b), v) in enumerate(zip(xs, row)):
            if k:
                out = a == ox
                f.add([line(a, ry + (0 if out else 10), a, ry + rh - (0 if out else 10), stroke=NAVY if out else GREY, sw=3 if out else 2)])
            cy, mid = ry + rh / 2, (a + b) / 2
            if v is None:
                f.add([line(mid - 14, cy, mid + 14, cy, stroke=GREY, sw=6)])
            elif v:
                t, d = v if isinstance(v, tuple) else (v, "")
                strong = t.startswith("!")
                f.lab(t.lstrip("!"), d, mid, cy - (LH_T + nlines(d) * LH_D) / 2 - 6, b - a - 8, strong=strong)
        cys.append(ry + rh / 2)
        ry += rh + gap
    return xs, cys, ry - gap


TX, TCOLS = 270, (220, 210, 190, 210)
THEAD = ("설비가 멈췄나", "잠금", "남은 압력", "손대도 되나")
TROWS = (("멈췄다", "걸렸다", "없다", "된다"), (None, "걸리지 않았다", None, "안 된다"), (None, None, "남았다", "안 된다"))


def out_badge(cx, cy, r, ok):
    """결정표의 출력 표시: ✓ 된다 · ✕ 안 된다. 둘은 같은 무게(흰 원)다."""
    return check_badge(cx, cy, r, fill=WHITE) if ok else cross_badge(cx, cy, r)


def mrow(f, x, y, w, h, pat, ok, dashed=False):
    """글자 없는 작은 규칙 행: 조건 칸 셋(값이 있으면 회색 알약, 상관없으면 짧은 줄)과 출력 표시(✓ 된다 · ✕ 안 된다)."""
    if dashed:
        f.add([rect(x, y, w, h, h / 3, fill=WHITE, stroke="none", sw=0)] + dash_rect(x, y, w, h, NAVY, 2.5, 8, 6))
    else:
        f.add([rect(x, y, w, h, h / 3, fill=WHITE, stroke=NAVY, sw=2.5)])
    cw_ = (w - h - 8) / 3
    for i, v in enumerate(pat):
        mx, cy = x + 6 + cw_ * (i + 0.5), y + h / 2
        if v:
            f.add([rect(mx - cw_ * 0.34, cy - h * 0.2, cw_ * 0.68, h * 0.4, h * 0.2, fill=GREY, stroke="none", sw=0)])
        else:
            f.add([line(mx - 7, cy, mx + 7, cy, stroke=GREY, sw=4)])
    f.add([line(x + w - h - 2, y, x + w - h - 2, y + h, sw=2.5)] + out_badge(x + w - h / 2 - 1, y + h / 2, h / 2 - 6, ok))


R1, R2, R3, R4 = ((1, 1, 1), True), ((0, 1, 0), False), ((0, 0, 1), False), ((1, 0, 0), True)


def u21():
    """21장: 왼쪽 SOP 한 장의 조건 문장 한 줄(파란 테두리)에서 가는 선 셋이 오른쪽 같은 폭의 물음 칸 셋에 닿는다.
    칸마다 물음 한 줄과 답이 적히지 않은 빈 점선 칸."""
    f = Fig("카드_조건문장_빈칸.svg")
    PX, PW, PH = 40, 430, 336
    f.add([rect(PX, 0, PW, PH, 12, fill=WHITE, sw=3.5)])
    for k, y in enumerate((44, 76, 232, 264, 296)):
        f.add([circle(PX + 34, y, 5, fill=GREY, stroke="none", sw=0), line(PX + 54, y, PX + PW - (40, 110, 60, 130, 90)[k], y, stroke=GREY, sw=5)])
    by = 154
    f.add([rect(PX + 22, by - 36, PW - 44, 72, 14, fill=PALE, stroke=BLUE, sw=4.5)])
    f.lab("설비를 세우고 잠근 뒤에만", "", PX + PW / 2, by - 19, PW - 70)
    CX0, CW_, CH = 640, 520, 80
    ys = (48, 168, 288)
    bus = 560
    f.add([line(PX + PW - 22 + 8, by, bus, by, sw=2.5), line(bus, ys[0], bus, ys[2], sw=2.5), circle(PX + PW - 22 + 8, by, 4.5, fill=NAVY, sw=1)])
    for y, q in zip(ys, ("세웠다는 어느 값으로 보나", "잠갔다는 무엇으로 아나", "무엇을 보고 정했나")):
        f.add([line(bus, y, CX0 - 8, y, sw=2.5)] + box(CX0, y - CH / 2, CW_, CH, r=18) + dash_rect(CX0 + CW_ - 170, y - 22, 150, 44, GREY, 3, 8, 6))
        f.lab(q, "", CX0 + (CW_ - 180) / 2, y - 19, CW_ - 200)
    return f.fin(0, foot(f, "적혀 있지 않은 뜻은 컴퓨터가 알 수 없고 AI는 짐작할 뿐이다", PH + 30))


def u22():
    """22장: 결정표 하나의 생김새. 머리 띠에 판정할 물음, 그 아래 왼쪽 입력 열 둘과 오른쪽 출력 열 하나, 빈 행 셋."""
    f = Fig("카드_DMN_생김새.svg")
    x, w, ow = 230, 740, 250
    f.add([rect(x, 0, w, 66, 14, fill=LIGHT, sw=3)])
    f.lab("판정할 물음", "", x + w / 2, 33 - 19, 400)
    iw = w - ow
    f.add([rect(x, 80, iw - 4, 56, 10, fill=GREY, stroke="none", sw=0), rect(x + iw + 4, 80, ow - 4, 56, 10, fill=GREY, stroke="none", sw=0)])
    f.lab("입력", "", x + iw / 2, 108 - 19, 200)
    f.lab("출력", "", x + iw + ow / 2, 108 - 19, 200)
    y = 148
    for i in range(3):
        f.add([rect(x, y, w, 60, 12, fill=WHITE, sw=2.5), line(x + iw / 2, y + 10, x + iw / 2, y + 50, stroke=GREY, sw=2), line(x + iw, y, x + iw, y + 60, sw=3)])
        y += 70
    return f.fin(0, foot(f, "같은 입력이면 누가 보든 같은 출력이 나온다", y - 10 + 30))


def u23():
    """23장: 맨 위 조건 한 줄(파란 테두리)이 같은 폭 · 같은 꼴의 두 칸으로 갈라 내려간다. 왼쪽 SOP 칸은 그 조건이 든 단계 한 줄,
    오른쪽 DMN 칸은 결정표의 머리와 한 행."""
    f = Fig("카드_SOP와DMN.svg")
    LX, RX, W, T, H = 295, 905, 550, 124, 236
    tcard(f, 600, 34, 470, 68, "설비를 세우고 잠근 뒤에만", hot=True)
    f.add([line(600, 74, 600, 96, sw=5), line(LX, 96, RX, 96, sw=5)] + arrow([(LX, 96), (LX, T - 8)]) + arrow([(RX, 96), (RX, T - 8)]))
    for cx, nm, d in ((LX, "SOP", "사람이 따를 차례"), (RX, "DMN", "입력 값으로 판정")):
        y = panel(f, cx, T, W, H, nm, d, strong=False)
    r1, r2, rh = y + 18, y + 18 + 64, 54
    x0, w = LX - W / 2 + 30, W - 60
    f.add([rect(x0, (r1 + r2) / 2, w, rh, 12, fill=WHITE, sw=2.5)])
    f.lab("1 설비를 세우고 잠근 뒤에만 덮개를 연다", "", LX, (r1 + r2) / 2 + rh / 2 - 19, w)
    x0 = RX - W / 2 + 30
    cw_ = w - 150
    f.add([rect(x0, r1, cw_ - 4, rh, 10, fill=GREY, stroke="none", sw=0), rect(x0 + cw_ + 4, r1, 146, rh, 10, fill=GREY, stroke="none", sw=0),
           rect(x0, r2, w, rh, 12, fill=WHITE, sw=2.5), line(x0 + cw_, r2, x0 + cw_, r2 + rh, sw=3)])
    f.lab("멈췄다 · 걸렸다", "", x0 + cw_ / 2, r2 + rh / 2 - 19, cw_ - 16)
    f.lab("된다", "", x0 + cw_ + 75, r2 + rh / 2 - 19, 130)
    return f.fin(0, foot(f, "SOP는 하는 법을, DMN은 해도 되는지를 맡아 서로를 대신하지 않는다", T + H + 28))


def u24():
    """24장: 위에 결정 카드 하나(용어와 영문, 물음 한 줄과 확인하는 사람 한 줄), 아래에 같은 꼴 · 같은 폭의 입력 데이터 카드 셋.
    입력 카드마다 결정 카드로 곧게 올라가는 화살표."""
    f = Fig("카드_결정과입력.svg")
    xs, W, H, DH = (430, 710, 990), 250, 88, 156
    x0, x1 = xs[0] - W / 2, xs[2] + W / 2
    f.add(box(x0, 0, x1 - x0, DH))
    f.lab("결정", "Decision", 710, 10, 300, strong=True)
    f.lab("작업자가 지금 손대도 되는가", "", 710, 74, 500)
    f.lab("", "손대기 직전에 작업자가 확인한다", 710, 110, 500)
    cy = DH + 62 + H / 2
    for x, kind, nm in zip(xs, ("stop", "lock", "gauge0"), ("설비가 멈췄나", "잠금이 걸렸나", "남은 압력")):
        hcard(f, x, cy, W, H, kind, nm)
        f.add(arrow([(x, cy - H / 2 - 8), (x, DH + 8)]))
    f.lab("입력 데이터", "Input Data", 150, cy - 30, 220, strong=True)
    return f.fin(0, foot(f, "어느 공장에서나 손대기 전에 보는 안전 조건", cy + H / 2 + 30))


def u25():
    """25장: 결정표 하나(조건 열 셋 · 출력 열 하나 · 행 셋). 상관없는 칸은 짧은 가로선. 왼쪽에 결정표 용어,
    세 행에 하나씩 닿는 빗살 옆에 규칙 용어(한 행이 규칙 하나)."""
    f = Fig("카드_결정표_세행.svg")
    xs, cys, bot = dtable(f, TX, 0, TCOLS, THEAD, TROWS, rh=76, hh=58, gap=12)
    f.lab("결정표", "Decision Table", 125, 29 - 30, 230, strong=True)
    f.lab("규칙", "Rule", 125, cys[1] - 30, 120, strong=True)
    f.add([line(TX - 34, cys[0], TX - 34, cys[2], sw=2.5), line(180, cys[1], TX - 34, cys[1], sw=2.5)] + [line(TX - 34, y, TX - 10, y, sw=2.5) for y in cys])
    return f.fin(0, foot(f, "줄(-) 칸은 그 입력이 무엇이든 상관없다는 뜻", bot + 36))


def u26():
    """26장: 같은 폭의 수직선 둘. 위는 임계치 하나(0에 빈 점, 0보다 큰 쪽을 굵게), 아래는 범위(하한 · 상한에 채운 점, 사이를 굵게).
    오른쪽에 비교 연산자 넷 한 덩어리."""
    f = Fig("카드_수직선_경계.svg")
    X0, X1, PA, PB, y1, y2 = 250, 940, 380, 820, 96, 316
    for y in (y1, y2):
        f.add(arrow([(X0, y), (X1, y)], GREY, sw=5, size=16))
    f.lab("임계치 하나", "", 100, y1 - 19, 190)
    f.lab("남은 압력 > 0", "안 된다", (PA + X1) / 2, y1 - 22 - 5 - LH_T - LH_D, 330)
    f.add([line(PA + 14, y1, X1 - 30, y1, sw=11), circle(PA, y1, 13, fill=WHITE, stroke=BLUE, sw=5)])
    f.lab("0", "", PA, y1 + 20, 60)
    f.lab("0을 빼면 다 빠진 압력은 된다", "", PA + 40, y1 + 54, 400, strong=True)
    f.lab("범위", "Range", 100, y2 - 30, 190)
    f.lab("하한 ≤ 값 ≤ 상한", "", (PA + PB) / 2, y2 - 22 - 5 - LH_T, 330)
    f.add([line(PA, y2, PB, y2, sw=11), circle(PA, y2, 13, fill=NAVY, sw=1), circle(PB, y2, 13, fill=NAVY, sw=1)])
    f.lab("하한", "", PA, y2 + 20, 100)
    f.lab("상한", "", PB, y2 + 20, 100)
    my = (y1 + y2) / 2
    f.add(box(985, my - 46, 190, 92, r=18))
    f.lab("비교 연산자", "> · ≥ · < · ≤", 1080, my - 30, 180)
    f.lab("", "채운 점은 넣고 빈 점은 뺀다", (X0 + X1) / 2, y2 + 68, 400)
    return f.fin(y1 - 22 - 5 - LH_T - LH_D, y2 + 68 + 5 + LH_D)


def u27():
    """27장: 25장 결정표와 같은 자리 · 같은 꼴의 행 셋(머리 줄은 뺀다). 첫 행을 묶는 파란 테두리가 그리고,
    둘째 · 셋째 행을 함께 묶는 파란 테두리가 또는이다. 묶음마다 아래에 한 줄."""
    f = Fig("카드_그리고또는.svg")
    w, rh = sum(TCOLS), 76
    _, c1, b1 = dtable(f, TX, 0, TCOLS, None, TROWS[:1], rh=rh)
    f.lab("셋이 모두 맞아야 된다", "", TX + w / 2, b1 + 22, 500)
    t2 = b1 + 22 + 5 + LH_T + 40
    _, c2, b2 = dtable(f, TX, t2, TCOLS, None, TROWS[1:], rh=rh, gap=12)
    f.lab("둘 가운데 하나만 맞아도 안 된다", "", TX + w / 2, b2 + 22, 500)
    for top, bot in ((0, b1), (t2, b2)):
        f.add([rect(TX - 12, top - 12, w + 24, bot - top + 24, 20, fill="none", stroke=BLUE, sw=4.5)])
    f.lab("그리고", "AND", 125, c1[0] - 30, 200, strong=True)
    f.lab("또는", "OR", 125, (c2[0] + c2[1]) / 2 - 30, 200, strong=True)
    return f.fin(-12, b2 + 22 + 5 + LH_T)


CASES = (("누락", "맞는 행이 없다", "잠금은 걸었지만 아직 돌고 있고 / 압력이 없다", ()),
         ("중복", "같은 출력의 행이 함께 맞는다", "잠금도 없고 압력도 남았다", (R2, R3)),
         ("상충", "다른 출력의 행이 함께 맞는다", "멈췄지만 잠금이 없다", (R2, R4)))


def u28():
    """28장: 왼쪽에 25장 결정표(조건 열 셋의 머리와 값은 같은 낱말 · 같은 자리, 출력은 ✓ 된다 · ✕ 안 된다)를 두고 넷째 행을 점선으로 더한다.
    오른쪽에 같은 꼴 · 같은 폭의 칸 셋(누락 · 중복 · 상충)을 위아래로 두고, 칸마다 용어와 뜻, 그 입력, 그 입력이 맞은 행을
    왼쪽 표의 행과 같은 꼴(같은 칸 자리 · 같은 테두리)의 작은 행으로 그린다. 누락 칸은 맞은 행 자리가 빈 점선이다."""
    f = Fig("카드_누락중복상충.svg")
    CX0, CW_, CH, P = 600, 590, 120, 132
    tx, cols, rh, gap, hh = 10, (172, 172, 172, 56), 54, 8, 44
    th = hh + gap + 4 * rh + 3 * gap + 12 + 5 + LH_T + LH_D
    t0 = (2 * P + CH - th) / 2
    rows = (("멈췄다", "걸렸다", "없다", ""), (None, "걸리지 않았다", None, ""), (None, None, "남았다", ""), ("멈췄다", None, None, ""))
    xs, cys, bot = dtable(f, tx, t0, cols, ("설비가 멈췄나", "잠금", "남은 압력", ""), rows, rh=rh, hh=hh, gap=gap, dashed=(3,))
    for cy, (_, ok) in zip(cys, (R1, R2, R3, R4)):
        f.add(out_badge((xs[3][0] + xs[3][1]) / 2, cy, 17, ok))
    f.lab("멈췄으면 된다", "누군가 짧게 더한 행", tx + sum(cols) / 2, bot + 12, 400)
    for i, (nm, d, s, hits) in enumerate(CASES):
        cy = i * P + CH / 2
        f.add(box(CX0, cy - CH / 2, CW_, CH, r=20) + [line(CX0 + 276, cy - CH / 2 + 16, CX0 + 276, cy + CH / 2 - 16, stroke=GREY, sw=2.5)])
        f.lab(nm, d, CX0 + 138, cy - 30, 284, strong=True)
        rx = CX0 + 276 + (CW_ - 276) / 2
        n = nlines(s)
        f.lab("", s, rx, cy - 52 if n == 2 else cy - 40, CW_ - 286)
        ry = cy + 12 if n == 2 else cy + 2
        if hits:
            for k, (pat, ok) in enumerate(hits):
                mrow(f, rx - 146 + k * 152, ry, 140, 34, pat, ok, dashed=(pat, ok) == R4)
        else:
            f.add(dash_rect(rx - 70, ry, 140, 34, GREY, 3, 8, 6))
    return f.fin(0, foot(f, "빈 곳은 그 경우를 덮는 행을 더해 메운다", 2 * P + CH + 30))


def u29():
    """29장: 위에 두 갈래 머리(하나만 고른다 · 모두 모은다), 그 아래 같은 꼴 · 같은 폭의 칸 넷(Unique · Any · Priority | Collect).
    칸마다 이름과 뜻, 겹친 두 행에서 무엇이 나오는지의 작은 그림, 한 줄. 칸 아래에 어느 때 쓰는지."""
    f = Fig("카드_HitPolicy_셋.svg")
    xs, W, T, H = (150, 450, 750, 1050), 290, 70, 300
    for a, b, t in ((xs[0] - W / 2, xs[2] + W / 2, "하나만 고른다"), (xs[3] - W / 2, xs[3] + W / 2, "모두 모은다")):
        f.lab(t, "", (a + b) / 2, 0, 300)
        f.add([path(f"M {a + 10},{T - 12} L {a + 10},{T - 24} L {b - 10},{T - 24} L {b - 10},{T - 12}", sw=3)])
    spec = (("Unique", "겹치는 행을 / 두지 않는다", ("상충은 표를 고친다",), (R2, R4), "상충일 때"),
            ("Any", "겹쳐도 출력이 같으면 / 어느 행이든", (), (R2, R3), "중복일 때"),
            ("Priority", "정해 둔 출력 순위로 / 하나를 고른다", ("안 된다가", "된다보다 먼저"), (R2, R4), "상충일 때"),
            ("Collect", "맞은 행의 출력을 / 모두 낸다", ("맞은 출력을 모두",), (R2, R3), "빠짐없이 알아야 할 때"))
    by = T + H + 16
    for x, (nm, d, lines, hits, when) in zip(xs, spec):
        f.add(box(x - W / 2, T, W, H))
        f.lab(nm, d, x, T + 12, W - 10, strong=True)
        my = T + 160
        for k, (pat, ok) in enumerate(hits):
            mrow(f, x - 132, my - 39 + k * 44, 130, 34, pat, ok, dashed=(pat, ok) == R4)
        f.add(arrow([(x + 8, my), (x + 44, my)], sw=4, size=14))
        if nm == "Unique":
            f.add(g(x + 88, my, 0.52, tools_icon(ON)))
        elif nm == "Collect":
            f.add(cross_badge(x + 72, my, 18) + cross_badge(x + 114, my, 18))
        else:
            f.add(cross_badge(x + 80, my, 18))
        y0 = T + H - 22 - len(lines) * 32
        for k, t in enumerate(lines):
            f.lab(t, "", x, y0 + k * 32 - 5, W - 10)
        f.lab(when, "", x, by, W)
    return f.fin(0, by + 5 + LH_T)


def u30():
    """30장: 맨 위 작은 머리 칸 한 줄(체 아이콘과 허용 조건), 그 아래 결정표 하나(조건 열 셋 · 출력 열 · 근거 열, 행 셋 — 셋째 행은
    어느 조건에도 걸리지 않으면 허용). 출력 값만 파랗다."""
    f = Fig("카드_판단규칙_두행.svg")
    cols = (220, 290, 280, 126, 150)
    x = (FW - sum(cols)) / 2
    f.add([rect(250, 0, 700, 64, 18, fill=WHITE, sw=3), circle(292, 32, 24, fill=PALE, stroke="none", sw=0)] + g(292, 32, 0.36, sieve_icon(ON)))
    f.lab("허용 조건 · 고르기 전에 지금 상태로 정한다", "", 625, 32 - 19, 600)
    f.lab("", "2호기 오일 쿨러의 예", x + 96, 80, 200)
    rows = (("원격 자동이 아니다", "자동으로 내려오는 명령", None, "!제외", "정비 매뉴얼"),
            (None, "팬을 최대로 돌리는 조치", "기준을 넘었다", ("!감점", "팬 수명"), "정비 매뉴얼"),
            (None, None, None, "!허용", None))
    _, cys, bot = dtable(f, x, 120, cols, ("운전 모드", "조치의 갈래", "팬을 최대로 돌려 온 시간", "출력", "근거"), rows, rh=78, hh=58, gap=12, nout=2)
    return f.fin(0, bot)


def u31():
    """31장: 같은 폭의 세로 줄 둘. 줄마다 위에서 아래로 물음 → 입력 → Hit Policy(작은 결정표와 이름 · 뜻) → 출력의 네 단을 같은 높이로."""
    f = Fig("카드_물음둘_HitPolicy.svg")
    W = 520
    spec = ((300, "이 후보를 지금 해도 되나", ("입력 · 운전 모드",), "Priority", "제외가 허용보다 먼저 / 제외 행과 허용 행이 함께 맞으면 제외", "허용 · 제외 중 하나"),
            (900, "이 후보에 붙일 감점은", ("입력 · 조치의 갈래 ·", "팬을 최대로 돌려 온 시간"), "Collect", "붙는 감점을 모두", "감점 목록"))
    f.lab("", "2호기 오일 쿨러의 예", 300 - W / 2 + 96, 0, 200)
    T = 36
    for cx, q, ins, hp, d, o in spec:
        tcard(f, cx, T + 32, W, 64, q)
        f.add(arrow([(cx, T + 70), (cx, T + 94)], sw=4, size=14))
        f.add([rect(cx - 200, T + 100, 400, 80, 12, fill=GREY, stroke="none", sw=0)])
        for k, t in enumerate(ins):
            f.lab(t, "", cx, T + 140 - 19 + (k - (len(ins) - 1) / 2) * 32, 390)
        f.add(arrow([(cx, T + 186), (cx, T + 210)], sw=4, size=14))
        f.add(box(cx - W / 2, T + 216, W, 104, r=20) + disc(cx - W / 2 + 60, T + 268, 34, "rules"))
        f.lab(hp, d, cx + 46, T + 268 - (LH_T + nlines(d) * LH_D) / 2 - 6, W - 120, strong=True)
        f.add(arrow([(cx, T + 326), (cx, T + 350)], sw=4, size=14))
        f.add([rect(cx - 200, T + 356, 400, 56, 14, fill=WHITE, sw=2.5)])
        f.lab(o, "", cx, T + 384 - 19, 380)
    return f.fin(0, T + 412)


def u32():
    """32장: 맨 위 머리 칸에 지금 입력 한 줄. 그 아래 후보 둘을 행으로 두는 판정표(후보 → 해도 되나 · 감점 · 근거). 감점이 붙은 칸만 파란 칸."""
    f = Fig("카드_후보둘_판정.svg")
    f.add([rect(170, 0, 860, 64, 18, fill=WHITE, sw=3)])
    f.lab("지금 · 원격 자동 · 팬을 최대로 돌려 온 시간이 기준을 넘었다", "", 600, 32 - 19, 830)
    RX, cols, H = 380, (190, 310, 280), 92
    rows = ((140, "fan", "팬 최대 운전", "허용", "감점 · 팬 수명", "근거 · 정비 매뉴얼"), (262, "wash", "쿨러 핀 세척", "허용", "감점 없음", None))
    for cy, kind, nm, a, b, c in rows:
        hcard(f, 180, cy, 290, H, kind, nm)
        f.add(arrow([(180 + 145 + 8, cy), (RX - 8, cy)]) + [rect(RX, cy - H / 2, sum(cols), H, 16, fill=WHITE, sw=2.5)])
        x = RX
        for k, (cw_, v) in enumerate(zip(cols, (a, b, c))):
            if k:
                f.add([line(x, cy - H / 2 + 14, x, cy + H / 2 - 14, stroke=GREY, sw=2)])
            if v is None:
                f.add([line(x + cw_ / 2 - 14, cy, x + cw_ / 2 + 14, cy, stroke=GREY, sw=6)])
            else:
                if v == "감점 · 팬 수명":
                    f.add([rect(x + 20, cy - 27, cw_ - 40, 54, 12, fill=PALE, stroke=BLUE, sw=4)])
                f.lab(v, "", x + cw_ / 2, cy - 19, cw_ - 60)
            x += cw_
    f.lab("", "허용은 고를 수 있다는 뜻, 세우고 잠그는 확인은 손대기 직전에", RX + sum(cols) / 2, 262 + H / 2 + 10, 700)
    return f.fin(0, foot(f, "맞은 규칙과 그 근거가 출력 옆에 함께 남는다", 262 + H / 2 + 10 + 5 + LH_D + 26))


def u33():
    """33장: 왼쪽에서 오른쪽으로 AI 에이전트(아래 판단 규칙에서 올라오는 조회 화살표) → 추천안 카드(후보 줄 둘, 줄마다 출력 · 근거 꼬리표) → 담당자."""
    f = Fig("카드_에이전트_조회.svg")
    cy, H = 96, 104
    hcard(f, 170, cy, 320, H, "agent", "AI 에이전트", "판단 규칙을 조회한다")
    hcard(f, 1030, cy, 320, H, "owner", "담당자", "근거를 보고 승인한다")
    PX, PW = 420, 360
    f.add(box(PX, 0, PW, 192))
    f.lab("추천안", "후보마다 출력과 근거", 600, 10, PW - 20)
    for y in (96, 146):
        f.add([line(PX + 28, y, PX + 150, y, stroke=GREY, sw=7), rect(PX + 176, y - 15, 70, 30, 15, fill=PALE, sw=2.5),
               path(f"M {PX + 262},{y - 13} L {PX + 314},{y - 13} L {PX + 328},{y} L {PX + 314},{y + 13} L {PX + 262},{y + 13} Z", fill=WHITE, sw=2.5)])
    f.add(arrow([(338, cy), (PX - 8, cy)]) + arrow([(PX + PW + 8, cy), (862, cy)]))
    ry = 268
    f.add(disc(170, ry, 46, "rules") + arrow([(170, ry - 54), (170, cy + H / 2 + 8)]))
    f.lab("판단 규칙", "", 170, ry + 54, 200)
    f.lab("허용된 후보가 여럿 남는다", "", 600, 214, 400)
    return f.fin(0, foot(f, "AI 에이전트는 추천안까지, 승인과 안전 결정은 사람이 한다", ry + 54 + 5 + LH_T + 26))


# ───────────────────────── 3단원(35~45장) ─────────────────────────

def coin_icon(st: St):
    """재무: 쌓은 동전과 오르는 막대."""
    o = []
    for y in (30, 16, 2):
        o += [path(f"M -44,{y} L -44,{y + 10} A 22 8 0 0 0 0,{y + 10} L 0,{y}", fill=st.accent, stroke=st.line, sw=3), ellipse(-22, y, 22, 8, fill=st.fill, stroke=st.line, sw=3)]
    for i, h in enumerate((22, 40, 60)):
        o.append(rect(10 + i * 14, 40 - h, 10, h, 3, fill=st.accent, stroke=st.line, sw=3))
    return o


def gear_icon(st: St):
    """내부 프로세스: 톱니바퀴."""
    o = [rect(-7, -44, 14, 88, 4, fill=st.accent, stroke=st.line, sw=3, transform=f"rotate({a} 0 0)") for a in (0, 45, 90, 135)]
    return o + [circle(0, 0, 30, fill=st.accent, stroke=st.line), circle(0, 0, 12, fill=st.fill, stroke=st.line)]


def sprout_icon(st: St):
    """학습과 성장: 펼친 책 위로 자라는 새싹."""
    return [path("M 0,18 L 0,-14", stroke=st.line, sw=5),
            path("M 0,-12 C -6,-36 -34,-38 -38,-36 C -38,-18 -20,-8 0,-12 Z", fill=st.accent, stroke=st.line, sw=3),
            path("M 0,-20 C 6,-40 28,-44 34,-42 C 34,-26 18,-16 0,-20 Z", fill=st.accent, stroke=st.line, sw=3),
            path("M 0,24 Q -22,12 -44,20 L -44,44 Q -22,36 0,46 Q 22,36 44,44 L 44,20 Q 22,12 0,24 Z", fill=st.fill, stroke=st.line), line(0, 24, 0, 46, stroke=st.line, sw=3)]


ICONS.update({"coin": (coin_icon, 0.9), "gear": (gear_icon, 0.86), "sprout": (sprout_icon, 0.9)})

PERSP = (("coin", "재무", "돈으로 어떤 결과가 났나"), ("person", "고객", "고객에게 약속을 지켰나"),
         ("gear", "내부 프로세스", "일이 잘 돌아가나"), ("sprout", "학습과 성장", "사람과 지식이 나아지나"))
WAY_A, WAY_B = "설비를 세우고 원인을 고치는 조치", "운전하며 버티는 조치"


def u35():
    """35장: 두 갈래(행)를 두 성과(열)로 본다. 왼쪽 열은 기름 온도를 내리는 정도(막대의 길고 짧음), 오른쪽 열은 생산(멈춘다 · 이어 간다).
    두 갈래는 같은 꼴 · 같은 색이고 막대에 숫자가 없다."""
    f = Fig("카드_막대둘_한성과.svg")
    ys, RH, c1, c2 = (142, 292), 132, 430, 830
    chip(f, c1, 0, 360, "기름 온도를 내리는 정도", h=52)
    chip(f, c2, 0, 360, "생산", h=52)
    for cy, nm, ex, bar in zip(ys, (WAY_A, WAY_B), ("예: 쿨러 핀 세척", "예: 팬 최대 운전"), (310, 170)):
        f.add(box(10, cy - RH / 2, 1180, RH, r=20) + [line(x, cy - RH / 2 + 16, x, cy + RH / 2 - 16, stroke=GREY, sw=2.5) for x in (416, 810)])
        f.lab(nm, ex, 213, cy - 30, 400)
        f.add([rect(c1 + 20, cy - 19, bar, 38, 9, fill=PALE, sw=3)])
    cy = ys[0]
    f.add([line(c2 + 24, cy, c2 + 118, cy, sw=5)] + g(c2 + 150, cy, 0.42, stop_icon(ON), boost=1.6))
    f.lab("멈춘다", "", c2 + 268, cy - 19, 150)
    cy = ys[1]
    f.add(arrow([(c2 + 24, cy), (c2 + 196, cy)]))
    f.lab("이어 간다", "", c2 + 278, cy - 19, 140)
    return f.fin(0, ys[1] + RH / 2)


def u36():
    """36장: 같은 꼴 · 같은 폭의 층 넷을 위(재무)에서 아래(학습과 성장)로 쌓는다(38 · 39장 전략맵과 같은 차례).
    층마다 아이콘 하나와 관점 이름, 그 관점이 묻는 것 한 줄."""
    f = Fig("카드_BSC_네관점.svg")
    H, P = 84, 96
    for i, (kind, nm, q) in enumerate(PERSP):
        hcard(f, 600, H / 2 + i * P, 760, H, kind, nm, q, strong=True)
    return f.fin(0, foot(f, "재무 결과만이 아니라 그 결과를 만드는 쪽까지 함께 본다", 3 * P + H + 30))


def u37():
    """37장: 같은 폭의 열 둘(왼쪽 전략 목표 · 오른쪽 KPI)과 행 둘. KPI 카드에서 목표 카드로 가는 화살표가 「잰다」."""
    f = Fig("카드_목표와KPI.svg")
    LX, RX, W, H = 300, 900, 460, 104
    f.lab("전략 목표", "Strategic Objective", LX, 0, 380, strong=True)
    f.lab("KPI", "Key Performance Indicator", RX, 0, 380, strong=True)
    for cy, goal, per, kpi in ((136, "설비를 멈추지 않고 돌린다", "내부 프로세스", "설비 가동률(%)"), (272, "주문을 제때 낸다", "고객", "납기 준수율(%)")):
        tcard(f, LX, cy, W, H, goal, per)
        tcard(f, RX, cy, W, H, kpi)
        rel(f, RX - W / 2 - 8, LX + W / 2 + 8, cy, "잰다")
    return f.fin(0, foot(f, "지식의 성과 영역에서 KPI 하나가 성과 지표 인스턴스 하나다", 272 + H / 2 + 36))


GOALS = ("이익을 지킨다", "주문을 제때 낸다", "설비를 멈추지 않고 돌린다", "정비 판단 지식을 쌓는다")


def u38():
    """38장: 네 층의 가로 띠(위 재무 → 아래 학습과 성장, 옅은 하늘색과 흰색을 번갈아)에 층마다 목표 카드 하나를 같은 폭으로
    가운데 세로줄에 두고, 아래에서 위로 곧은 화살표 셋으로 잇는다. 왼쪽 끝에 층 이름."""
    f = Fig("카드_전략맵.svg")
    H, P, CX, CW_, CH = 92, 102, 660, 420, 62
    for i, ((_, nm, _), goal) in enumerate(zip(PERSP, GOALS)):
        cy = H / 2 + i * P
        if i % 2 == 0:
            f.add(band_rect(cy - H / 2, cy + H / 2, PALE))
        f.lab(nm, "", 150, cy - 19, 240)
        tcard(f, CX, cy, CW_, CH, goal)
        if i:
            f.add(arrow([(CX, cy - CH / 2 - 5), (CX, cy - P + CH / 2 + 5)], sw=4.5, size=15))
    return f.fin(0, foot(f, "한 조치의 영향이 어디까지 번지는지 따라간다", 3 * P + H + 26))


def u39():
    """39장: 전략맵의 두 층(위 고객 · 아래 내부 프로세스)과 같은 꼴의 띠 둘에 KPI 카드를 두고, 오른쪽에 시간 축을 붙였다.
    아래 선(설비 가동률)은 앞 시점에서, 위 선(납기 준수율)은 뒤 시점에서 꺾여 내려간다. 두 꺾임 시점에 세로 점선."""
    f = Fig("카드_선행후행_시간축.svg")
    H, CX = 132, 470
    tops = (0, 150)
    G0, G1, tA, tB = 620, 1160, 800, 1000
    for top, term, eng, kpi, t in zip(tops, ("후행 지표", "선행 지표"), ("Lagging Indicator", "Leading Indicator"), ("납기 준수율", "설비 가동률"), (tB, tA)):
        f.add(band_rect(top, top + H, PALE))
        f.lab(term, eng, 150, top + H / 2 - 30, 260, strong=True)
        tcard(f, CX, top + H / 2, 250, 60, kpi)
        hi, lo = top + 36, top + H - 26
        f.add([path(f"M {G0},{hi} L {t},{hi} L {t + 110},{lo} L {G1 - 10},{lo}", sw=5)])
    f.add(arrow([(CX, tops[1] + H / 2 - 35), (CX, tops[0] + H / 2 + 35)], sw=4.5, size=15))
    ay = tops[1] + H + 28
    for t in (tA, tB):
        f.add(dash_line(t, 8, t, ay, GREY, 3, 8, 6))
    f.add(arrow([(G0, ay), (G1 + 10, ay)], GREY, sw=5, size=16))
    f.lab("먼저 떨어진다", "", (G0 + tA) / 2 - 4, tops[1] + 62, 170)
    f.lab("뒤에 떨어진다", "", (tA + tB) / 2, tops[0] + 62, 170)
    f.lab("시간", "", G1 - 30, ay + 10, 80)
    return f.fin(0, foot(f, "선행 지표가 움직일 때 손쓰면 결과가 나기 전에 막을 수 있다", ay + 10 + 5 + LH_T + 22))


def u40():
    """40장: KPI 카드 한 장. 왼쪽 단은 정해 두는 칸 넷(칸 이름과 값), 오른쪽 단은 재서 나오는 칸 둘(파란 테두리).
    두 단 아래에 단 이름을 작게."""
    f = Fig("카드_KPI_칸.svg")
    X0, X1, bot = 110, 1090, 336
    f.add(box(X0, 0, X1 - X0, bot))
    f.lab("설비 가동률", "", 600, 14, 400)
    lx, iw, vw = X0 + 30, 140, 410
    rows = (("정의", "실제 생산 시간 ÷ 계획 가동 시간"), ("단위", "%"), ("목표값", "95"), ("측정 주기", "하루마다"))
    for i, (item, val) in enumerate(rows):
        y = 70 + i * 62
        f.add([rect(lx, y, iw, 50, 10, fill=GREY, stroke="none", sw=0), rect(lx + iw + 8, y, vw, 50, 10, fill=WHITE, sw=2)])
        f.lab(item, "", lx + iw / 2, y + 6, iw - 8)
        f.lab(val, "", lx + iw + 8 + vw / 2, y + 6, vw - 10)
    rx, rw = X1 - 30 - 300, 300
    for (term, val), y in zip((("실제값", "92"), ("목표 대비 차이", "-3 %p")), (70, 194)):
        f.add([rect(rx, y, rw, 112, 14, fill=WHITE, stroke=BLUE, sw=4.5)])
        f.lab(term, "", rx + rw / 2, y + 14, rw - 20, strong=True)
        f.lab(val, "", rx + rw / 2, y + 60, rw - 20)
    f.add(arrow([(lx + iw + 8 + vw + 10, 188), (rx - 10, 188)], sw=4.5, size=15))
    for a, b, t in ((lx, lx + iw + 8 + vw, "정해 두는 칸"), (rx, rx + rw, "재서 나오는 칸")):
        f.add([path(f"M {a},{bot + 12} L {a},{bot + 24} L {b},{bot + 24} L {b},{bot + 12}", sw=3)])
        f.lab(t, "", (a + b) / 2, bot + 34, 300)
    return f.fin(0, bot + 34 + 5 + LH_T)


KPI5 = (("설비 복구 시간", "시간"), ("생산 차질", "개"), ("전력비", "원"), ("품질", "불량률 %"), ("안전", "인터록까지 남은 여유"))


def u41():
    """41장: 위에 같은 폭의 KPI 칸 다섯(이름과 단위). 아래에 두 갈래 행(같은 꼴)을 두고, 득 · 실을 그 열의 양이 바뀌는 KPI 열 아래에 놓는다.
    득과 실이 서로 다른 열(단위)에 놓여 한 줄로 세울 수 없음을 보인다. 강조는 두지 않는다."""
    f = Fig("카드_다섯성과_단위.svg")
    L, P, CW_, HH, RH = 250, 190, 180, 78, 100
    cxs = [L + P / 2 + i * P for i in range(5)]
    for cx, (nm, unit) in zip(cxs, KPI5):
        f.add([rect(cx - CW_ / 2, 0, CW_, HH, 12, fill=GREY, stroke="none", sw=0)])
        f.lab(nm, unit, cx, HH / 2 - 30, CW_ + 34)
    rows = ((WAY_A, ((1, "실 · 생산이 멈춘다", ""), (4, "득 · 여유가", "더 커진다"))),
            (WAY_B, ((0, "실 · 원인이 남아", "복구가 미뤄진다"), (1, "득 · 생산을", "이어 간다"), (2, "실 · 전력을", "더 쓴다"))))
    for r, (nm, cells) in enumerate(rows):
        top = HH + 14 + r * (RH + 14)
        cy = top + RH / 2
        f.add(box(0, top, 1200, RH, r=18) + [line(L - 12, top + 14, L - 12, top + RH - 14, stroke=GREY, sw=2)])   # 열은 머리 칸 아래 자리로 맞춘다(칸 글이 열 폭을 거의 채워 세로줄을 두지 않는다)
        f.lab(nm, "", (L - 12) / 2, cy - 19 - (LH_T / 2 if r == 0 else 0), L - 12)
        for i, a, b in cells:      # b가 비면 한 라벨이 두 줄로 접힌다(라벨 17개 한도)
            f.lab(a, "", cxs[i], cy - (33 if not b else 35), CW_ if not b else P + 20)
            if b:
                f.lab(b, "", cxs[i], cy - 3, P + 20)
    return f.fin(0, foot(f, "득과 실이 서로 다른 단위라 그대로는 더하지도 견주지도 못한다", HH + 14 + 2 * RH + 14 + 30))


def u42():
    """42장: 왼쪽에서 오른쪽으로 체(판단 규칙) → 한 잣대로 만드는 두 길(같은 단위로 바꾼다 · 중요도, 위아래) → 저울(한 잣대).
    체 아래로 떨어진 후보 하나(✕)가 인터록에 닿아 저울에 오르지 않는 후보다. 체와 저울은 19장과 같은 꼴."""
    f = Fig("카드_한잣대_체먼저.svg")
    SX, BX, ZX, cy, r, BW, BH = 170, 610, 1060, 196, 76, 440, 108
    f.add(disc(SX, cy, r, "sieve") + disc(ZX, cy, r, "scale"))
    ty = cy - r - 16 - 5 - LH_T - 2 * LH_D
    f.lab("판단 규칙", "인터록에 닿을 후보는 / 저울에 오르지 않는다", SX, ty, 330)
    dy = cy + r + 56
    f.add(arrow([(SX, cy + r + 6), (SX, dy - 26)], GREY, sw=4, size=13)
          + [rect(SX - 52, dy - 20, 104, 40, 10, fill=WHITE, sw=3), line(SX - 36, dy, SX + 6, dy, stroke=GREY, sw=6)] + cross_badge(SX + 32, dy, 13))
    ys = (cy - 74, cy + 74)
    tcard(f, BX, ys[0], BW, BH, "같은 단위로 바꾼다", "생산 차질 · 전력비 · 감점을 원으로")
    tcard(f, BX, ys[1], BW, BH, "중요도", "관점마다 얼마나 무겁게 볼지")
    b1, b2 = 318, 906
    f.add([line(SX + r + 12, cy, b1, cy, sw=5), line(b1, ys[0], b1, ys[1], sw=5), line(BX + BW / 2 + 8, ys[0], b2, ys[0], sw=5),
           line(BX + BW / 2 + 8, ys[1], b2, ys[1], sw=5), line(b2, ys[0], b2, ys[1], sw=5)])
    f.add(arrow([(b1, ys[0]), (BX - BW / 2 - 8, ys[0])]) + arrow([(b1, ys[1]), (BX - BW / 2 - 8, ys[1])]) + arrow([(b2, cy), (ZX - r - 12, cy)]))
    f.lab("한 잣대", "", ZX, cy + r + 12, 160)
    return f.fin(ty, foot(f, "판단 규칙은 해도 되나와 감점을, 선택 근거는 허용된 후보의 효과와 비용을 맡는다", dy + 20 + 30))


def u43():
    """43장: 맨 위에 가정값 하나(손잡이가 달린 눈금 막대). 그 아래 가로축(낮게 · 높게)과 두 갈래의 선이 한 곳에서 엇갈리고,
    엇갈리는 곳에 세로 점선. 세로축 머리에 작은 글(한 잣대로 본 값 · 위가 낫다). 두 선은 같은 굵기 · 같은 색이다."""
    f = Fig("카드_WhatIf_순위교차.svg")
    AX0, AX1, top, bot = 140, 880, 150, 330
    f.lab("가정값 하나", "생산 한 시간을 원으로 바꾸는 값", 250, 0, 420)
    f.add([line(500, 30, 860, 30, stroke=GREY, sw=8)] + [line(500 + i * 90, 18, 500 + i * 90, 42, stroke=GREY, sw=3) for i in range(5)]
          + [circle(635, 30, 15, fill=WHITE, sw=4.5)])
    f.add(arrow([(AX0, bot), (AX1 + 20, bot)], GREY, sw=5, size=16) + arrow([(AX0, bot), (AX0, top - 22)], GREY, sw=5, size=16))
    f.lab("", "한 잣대로 본 값 · 위가 낫다", AX0 + 80, top - 22 - 12 - 5 - LH_D, 280)
    x0, x1 = AX0 + 40, AX1 - 40
    mx = (x0 + x1) / 2
    f.add([line(x0, top, x1, bot - 40, sw=5.5), line(x0, bot - 40, x1, top, sw=5.5)] + [circle(x, y, 8, fill=NAVY, sw=1) for x in (x0, x1) for y in (top, bot - 40)])
    f.add(dash_line(mx, top + 10, mx, bot, GREY, 3.5, 8, 6))
    f.lab("순위가 바뀌는 곳", "", mx, top - 48, 230)
    f.lab("운전하며 버티는 조치", "", x1 + 150, top - 19, 250)
    f.lab("원인을 고치는 조치", "", x1 + 150, bot - 40 - 19, 250)
    f.lab("낮게 잡으면", "", x0 + 30, bot + 12, 170)
    f.lab("높게 잡으면", "", x1 - 30, bot + 12, 170)
    return f.fin(0, foot(f, "결론이 가정값 하나에 크게 기대면 그 값부터 확인한다", bot + 12 + 5 + LH_T + 24))


def u44():
    """44장: 같은 꼴의 가로 띠 둘. 위 띠는 가정 → 계산 → 예상(점선 테두리 — 아직 일어나지 않은 것), 아래 띠는 실행 → 재관측 → 실제(실선 테두리).
    예상과 실제 사이에 세로 견줌 화살표, 띠마다 오른쪽 끝에 확인 한 줄."""
    f = Fig("카드_WhatIf_한계.svg")
    xs, W, H, BH, ys = (170, 470, 770), 210, 80, 136, (68, 286)
    for cy, names, dashed, note in zip(ys, (("가정", "계산", "예상"), ("실행", "재관측", "실제")), (True, False),
                                       ("실행 전 · 가정이 지금 맞나", "실행 뒤 · 예상과 실제를 견준다")):
        if dashed:
            f.add(dash_rect(30, cy - BH / 2, 880, BH, NAVY, 3, 12, 8))
        else:
            f.add([rect(30, cy - BH / 2, 880, BH, 24, fill="none", sw=3)])
        for i, (x, nm) in enumerate(zip(xs, names)):
            tcard(f, x, cy, W, H, nm)
            if i:
                f.add(arrow([(xs[i - 1] + W / 2 + 8, cy), (x - W / 2 - 8, cy)]))
        f.lab(note, "", 1060, cy - 19 - LH_T / 2, 210)
    a, b = ys[0] + BH / 2 + 10, ys[1] - BH / 2 - 10
    f.add([line(xs[2], a + 12, xs[2], b - 12, sw=5), head(xs[2], a, -math.pi / 2, NAVY, 17), head(xs[2], b, math.pi / 2, NAVY, 17)])
    return f.fin(0, ys[1] + BH / 2)


def u45():
    """45장: 19장과 같은 자리 · 같은 꼴(flow4)에 이름을 채운다. 후보 아래에 조치 방법 · SOP, 체 위에 허용 조건과 판단 규칙 · 출력 셋,
    저울 위에 선택 근거와 KPI · What-if, 담당자 아래에 승인. 강조는 두지 않는다."""
    f = Fig("카드_체와저울_완성.svg")
    xs, cy = (75, 275, 480, 690, 890, 1100), 150
    top, bot = flow4(f, xs, cy)
    ty = top - 22 - 5 - LH_T - LH_D
    f.lab("허용 조건", "판단 규칙 · 허용 · 제외 · 감점", xs[1], ty, 330)
    f.lab("선택 근거", "KPI · What-if", xs[3], ty, 260)
    f.lab("조치 후보", "조치 방법 · SOP", xs[0], bot + 20, 150)
    f.lab("담당자", "근거를 보고 승인한다", xs[5], bot + 20, 200)
    return f.fin(ty, foot(f, "SOP대로 하고, 손대기 직전에 안전 조건을 다시 확인한다", bot + 20 + 5 + LH_T + LH_D + 40))


# 지금 원고가 쓰는 그림을 내는 함수(차례는 장 차례)
FIGS = [u05, u06, u07, u08, u09, u10, u11, u12, u13, u14, u15, u16, u17, u18, u19,
        u21, u22, u23, u24, u25, u26, u27, u28, u29, u30, u31, u32, u33,
        u35, u36, u37, u38, u39, u40, u41, u42, u43, u44, u45]


def fit_deck(md: Path, labels: dict[str, list[str]]) -> int:
    """덱 MD에서 `- 그림: <폴더>/<이 생성기가 만든 그림>`인 장의 `- 요소:` 목록을 이 생성기의 라벨 줄로 바꿔 쓴다.
    그 장에 `- 요소:` 줄이 없으면 오류로 멈춘다. 돌려주는 값: 바꾼 장 수."""
    lines = md.read_text(encoding="utf-8").split("\n")
    starts = [k for k, s in enumerate(lines) if s.startswith("## SLIDE")] + [len(lines)]
    out, n = lines[:starts[0]], 0
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
    for fn in FIGS:
        f = fn()
        text = f.svg()
        assert "<text" not in text
        assert len(f.labels) <= 17, (f.name, len(f.labels))
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
