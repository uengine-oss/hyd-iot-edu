"""통합반 1일차 v3 샘플 삽화(SVG)를 만든다. 글자는 넣지 않는다(라벨은 덱 MD의 요소로 얹는다).

사용: python 만들기_삽화.py            → 이 폴더에 SVG를 쓴다
색은 덱 색만, 선 그림(끝 둥글게), 그라디언트 · 그림자 · 필터 · <text> 없음.
"""
from __future__ import annotations

import math
from pathlib import Path

NAVY, SKY, BLUE, PALE, GREY, LIGHT, WHITE = "#13294B", "#5CB8F2", "#1A6FC4", "#E7F3FD", "#D3D9E1", "#F3F6F9", "#FFFFFF"
W, H = 1200, 520
SW = 3.5
HERE = Path(__file__).resolve().parent


class St:
    def __init__(self, line, fill, accent, soft):
        self.line, self.fill, self.accent, self.soft = line, fill, accent, soft


ON = St(NAVY, WHITE, SKY, PALE)
NORM = St(NAVY, WHITE, PALE, LIGHT)
OFF = St(GREY, WHITE, LIGHT, WHITE)


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
    return poly([(x, y), (x + size * math.cos(a1), y + size * math.sin(a1)),
                 (x + size * math.cos(a2), y + size * math.sin(a2))], fill=color)


def arrow(pts, color=NAVY, sw=4, size=13):
    """꺾은선 화살표. 마지막 점에 화살촉."""
    (x1, y1), (x2, y2) = pts[-2], pts[-1]
    ang = math.atan2(y2 - y1, x2 - x1)
    end = (x2 - size * 0.7 * math.cos(ang), y2 - size * 0.7 * math.sin(ang))
    d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in [*pts[:-1], end])
    return path(d, stroke=color, sw=sw) + head(x2, y2, ang, color, size)


def svg(body: list[str], w: int = W, h: int = H) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">\n'
            + "\n".join(body) + "\n</svg>\n")


# ───────────────────────── 작은 그림 조각 ─────────────────────────

def gauge(cx, cy, st: St, r=16, hot=False, ang=-50):
    """계기(센서 자리). 원 + 눈금 + 바늘."""
    o = [circle(cx, cy, r, fill=st.accent if hot else st.fill, stroke=st.line)]
    for a in (-150, -90, -30):
        ra = math.radians(a)
        o.append(line(cx + (r - 6) * math.cos(ra), cy + (r - 6) * math.sin(ra),
                      cx + (r - 3) * math.cos(ra), cy + (r - 3) * math.sin(ra), stroke=st.line, sw=2))
    ra = math.radians(ang)
    o.append(line(cx, cy + 2, cx + (r - 6) * math.cos(ra), cy + 2 + (r - 6) * math.sin(ra), stroke=st.line, sw=3))
    return o


def fan(cx, cy, r, st: St, blades=4, rot=20, hot=False):
    o = [circle(cx, cy, r, fill=st.fill, stroke=st.line)]
    for i in range(blades):
        a = rot + i * 360 / blades
        o.append(ellipse(cx, cy - r * 0.52, r * 0.21, r * 0.4, fill=st.accent if hot else st.soft, stroke=st.line, sw=3,
                         transform=f"rotate({a} {cx} {cy})"))
    o.append(circle(cx, cy, r * 0.17, fill=st.line, stroke=st.line, sw=2))
    return o


def radiator(x, y, w, h, st: St, fins=12, r=8):
    o = [rect(x, y, w, h, r, fill=st.fill, stroke=st.line)]
    step = (w - 20) / (fins - 1)
    for i in range(fins):
        fx = x + 10 + i * step
        o.append(line(fx, y + 10, fx, y + h - 10, stroke=GREY if st is not OFF else LIGHT, sw=2))
    return o


def dust(cx, cy, st: St, s=1.0):
    pts = [(-22, -14, 8), (-6, -20, 6), (10, -12, 9), (24, -18, 5), (-16, 4, 7), (2, 2, 10), (20, 6, 7),
           (-8, 20, 6), (12, 22, 8), (-26, 18, 5)]
    return [circle(cx + dx * s, cy + dy * s, rr * s, fill=GREY, stroke=st.line, sw=2) for dx, dy, rr in pts]


def thermo(cx, cy, st: St, s=1.0, level=0.6):
    """온도계. (cx, cy)는 구부 중심."""
    tw, th, br = 13 * s, 78 * s, 15 * s
    o = [rect(cx - tw / 2, cy - th - br * 0.6, tw, th + br, tw / 2, fill=st.fill, stroke=st.line),
         circle(cx, cy, br, fill=st.accent, stroke=st.line)]
    lh = th * level
    o.append(line(cx, cy - br * 0.4, cx, cy - br * 0.6 - lh, stroke=st.accent if st.accent != WHITE else st.line, sw=5 * s))
    return o


def equip_mini(cx, cy, st: St):
    return [rect(cx - 46, cy + 4, 92, 42, 6, fill=st.soft, stroke=st.line),
            path(f"M {cx - 40},{cy + 20} q 10,-6 20,0 t 20,0 t 20,0 t 20,0", stroke=st.line, sw=2),
            rect(cx - 40, cy - 38, 46, 32, 9, fill=st.fill, stroke=st.line),
            line(cx - 28, cy - 31, cx - 28, cy - 13, stroke=st.line, sw=2),
            line(cx - 17, cy - 31, cx - 17, cy - 13, stroke=st.line, sw=2),
            line(cx - 6, cy - 31, cx - 6, cy - 13, stroke=st.line, sw=2),
            line(cx + 6, cy - 22, cx + 14, cy - 22, stroke=st.line, sw=5),
            circle(cx + 28, cy - 22, 15, fill=st.accent, stroke=st.line),
            line(cx + 28, cy - 7, cx + 28, cy + 30, stroke=st.line, sw=4),
            line(cx - 30, cy - 6, cx - 30, cy + 4, stroke=st.line), line(cx - 4, cy - 6, cx - 4, cy + 4, stroke=st.line)]


def plc(cx, cy, st: St):
    o = [line(cx - 60, cy - 30, cx + 60, cy - 30, stroke=st.line, sw=6),
         rect(cx - 48, cy - 44, 96, 88, 6, fill=st.fill, stroke=st.line),
         rect(cx - 48, cy - 44, 26, 88, 6, fill=st.soft, stroke=st.line)]
    for dx in (-22, 2, 26):
        o.append(line(cx + dx, cy - 44, cx + dx, cy + 44, stroke=st.line))
    for i, dx in enumerate((-35, -10, 14, 37)):
        o.append(circle(cx + dx, cy - 28, 4, fill=st.accent if i in (0, 2) else st.fill, stroke=st.line, sw=2))
        for k in range(3):
            o.append(circle(cx + dx, cy + 6 + k * 13, 3, fill=st.fill, stroke=st.line, sw=2))
    return o


def server(cx, cy, st: St):
    o = [rect(cx - 44, cy - 48, 88, 96, 8, fill=st.fill, stroke=st.line)]
    for dy in (-16, 16):
        o.append(line(cx - 44, cy + dy, cx + 44, cy + dy, stroke=st.line))
    for dy in (-32, 0, 32):
        o.append(circle(cx - 28, cy + dy, 5, fill=st.accent, stroke=st.line, sw=2))
        o.append(line(cx - 12, cy + dy, cx + 30, cy + dy, stroke=st.line, sw=3))
    return o


def monitor(cx, cy, st: St, kind="hmi"):
    o = [rect(cx - 58, cy - 46, 116, 76, 7, fill=st.fill, stroke=st.line),
         line(cx, cy + 30, cx, cy + 44, stroke=st.line, sw=5), line(cx - 26, cy + 45, cx + 26, cy + 45, stroke=st.line, sw=5)]
    if kind == "hmi":
        o += [path(f"M {cx - 44},{cy + 10} A 20 20 0 0 1 {cx - 4},{cy + 10}", stroke=st.line),
              line(cx - 24, cy + 10, cx - 12, cy - 6, stroke=st.line, sw=3),
              rect(cx + 8, cy - 32, 12, 48, 3, fill=st.fill, stroke=st.line, sw=2.5),
              rect(cx + 8, cy - 6, 12, 22, 3, fill=st.accent, stroke=st.line, sw=2.5),
              rect(cx + 30, cy - 32, 12, 48, 3, fill=st.fill, stroke=st.line, sw=2.5),
              rect(cx + 30, cy - 20, 12, 36, 3, fill=st.accent, stroke=st.line, sw=2.5)]
    elif kind == "graph":   # 화면 속 관계 그림: 원 둘과 이름 붙은 화살표
        o += [circle(cx - 28, cy - 8, 13, fill=st.accent, stroke=st.line, sw=3),
              circle(cx + 28, cy - 8, 13, fill=st.fill, stroke=st.line, sw=3),
              arrow([(cx - 13, cy - 8), (cx + 13, cy - 8)], BLUE if st is ON else st.line, sw=3, size=9)]
    else:
        o += [path(f"M {cx - 44},{cy - 34} L {cx - 44},{cy + 16} L {cx + 46},{cy + 16}", stroke=st.line, sw=2.5),
              path(f"M {cx - 38},{cy + 6} L {cx - 20},{cy + 2} L {cx - 4},{cy - 18} L {cx + 10},{cy - 26} "
                   f"L {cx + 22},{cy - 8} L {cx + 40},{cy - 2}", stroke=BLUE if st is ON else st.line, sw=3.5)]
    return o


def window(cx, cy, st: St, kind="gate"):
    o = [rect(cx - 52, cy - 46, 104, 92, 8, fill=st.fill, stroke=st.line),
         line(cx - 52, cy - 24, cx + 52, cy - 24, stroke=st.line)]
    for dx in (-38, -27, -16):
        o.append(circle(cx + dx, cy - 35, 2.8, fill=st.line, stroke=st.line, sw=1))
    if kind == "gate":      # 벽의 틈으로 한 방향만 지나가는 화살표
        o += [line(cx, cy - 14, cx, cy, stroke=st.line, sw=5), line(cx, cy + 22, cx, cy + 36, stroke=st.line, sw=5),
              arrow([(cx - 36, cy + 11), (cx + 36, cy + 11)], BLUE if st is ON else st.line, sw=4, size=11)]
    else:                   # 기준선을 넘어 오르는 값
        o += [line(cx - 40, cy + 4, cx + 40, cy + 4, stroke=BLUE if st is ON else st.line, sw=2.5, stroke_dasharray="6 6"),
              path(f"M {cx - 40},{cy + 30} L {cx - 20},{cy + 26} L {cx - 2},{cy + 14} L {cx + 16},{cy - 4} L {cx + 38},{cy - 12}",
                   stroke=st.line, sw=3.5),
              circle(cx + 7, cy + 4, 5, fill=st.accent, stroke=st.line, sw=2)]
    return o


def bell(cx, cy, st: St, s=1.0):
    return [path(f"M {cx - 13 * s},{cy + 8 * s} Q {cx - 13 * s},{cy - 14 * s} {cx},{cy - 15 * s} "
                 f"Q {cx + 13 * s},{cy - 14 * s} {cx + 13 * s},{cy + 8 * s} L {cx + 18 * s},{cy + 13 * s} "
                 f"L {cx - 18 * s},{cy + 13 * s} Z", fill=st.accent, stroke=st.line, sw=3),
            circle(cx, cy + 19 * s, 3.2 * s, fill=st.line, stroke=st.line, sw=1)]


def logstrip(x, cy, st: St, n=7, cw=24, h=46):
    o = []
    for i in range(n):
        if i == n - 1:
            o.append(rect(x + i * cw, cy - h / 2, cw, h, 3, fill=st.fill, stroke=st.line, sw=2.5, stroke_dasharray="5 5"))
        else:
            o.append(rect(x + i * cw, cy - h / 2, cw, h, 3, fill=st.accent if i == n - 2 else st.soft, stroke=st.line, sw=3))
    return o


def cylinder_db(cx, cy, st: St):
    o = [path(f"M {cx - 42},{cy - 34} L {cx - 42},{cy + 34} A 42 14 0 0 0 {cx + 42},{cy + 34} L {cx + 42},{cy - 34}",
              fill=st.fill, stroke=st.line),
         ellipse(cx, cy - 34, 42, 14, fill=st.accent, stroke=st.line),
         path(f"M {cx - 42},{cy - 10} A 42 14 0 0 0 {cx + 42},{cy - 10}", stroke=st.line),
         path(f"M {cx - 42},{cy + 12} A 42 14 0 0 0 {cx + 42},{cy + 12}", stroke=st.line),
         circle(cx + 36, cy + 34, 17, fill=st.fill, stroke=st.line),
         path(f"M {cx + 36},{cy + 24} L {cx + 36},{cy + 34} L {cx + 44},{cy + 38}", stroke=st.line, sw=3)]
    return o


def graph_db(cx, cy, st: St):
    """그래프 DB: 시계열 저장소의 시계 대신 노드와 연결선 표시를 붙인 저장소."""
    return cylinder_db(cx, cy, st)[:4] + [circle(cx + 38, cy + 34, 26, fill=WHITE, stroke=st.line)] + g(cx + 38, cy + 34, 0.5, graph_icon(0, 0, st))


def pipe(d, inner=PALE, outer=NAVY):
    return [path(d, stroke=outer, sw=12), path(d, stroke=inner, sw=5.5)]


# ───────────────────────── 1. 유압 파워팩 ─────────────────────────

def hyd_unit() -> str:
    o: list[str] = []
    # 작동유 탱크
    o += [rect(70, 330, 400, 150, 12, fill=WHITE), rect(75, 374, 390, 101, 8, fill=PALE, stroke="none", sw=0),
          path("M 75,374 q 15,-8 30,0 t 30,0 t 30,0 t 30,0 t 30,0 t 30,0 t 30,0 t 30,0 t 30,0 t 30,0 t 30,0 t 30,0 t 30,0",
               stroke=NAVY, sw=2.5)]
    # 배관: 흡입 · 토출 · 복귀(뜨거운 쪽) · 쿨러 출구
    o += pipe("M 300,318 L 300,448")
    o += pipe("M 300,240 L 300,110 L 760,110")
    o += pipe("M 820,140 L 820,232", inner=SKY)
    o += pipe("M 660,388 L 660,422 L 472,422")
    o += [rect(285, 440, 30, 22, 4, fill=WHITE, sw=3), line(293, 444, 293, 458, sw=2), line(300, 444, 300, 458, sw=2),
          line(307, 444, 307, 458, sw=2)]
    # 흐름 방향
    o += [head(300, 352, -math.pi / 2, NAVY, 12), head(300, 168, -math.pi / 2, NAVY, 12), head(640, 110, 0, NAVY, 12),
          head(820, 216, math.pi / 2, NAVY, 12), head(552, 422, math.pi, NAVY, 12)]
    # 모터와 펌프
    o += [rect(108, 242, 124, 76, 16, fill=WHITE), rect(124, 318, 22, 12, 2, fill=WHITE, sw=3), rect(194, 318, 22, 12, 2, fill=WHITE, sw=3)]
    for fx in (134, 154, 174, 194, 214):
        o.append(line(fx, 254, fx, 306, sw=2.5))
    o += [line(232, 280, 262, 280, sw=9), circle(300, 280, 40, fill=PALE), circle(287, 280, 15, fill=WHITE, sw=3),
          circle(313, 280, 15, fill=WHITE, sw=3)]
    # 부하: 유압 실린더
    o += [rect(760, 80, 200, 60, 8, fill=WHITE), rect(852, 85, 14, 50, 2, fill=NAVY, sw=2), line(866, 110, 1044, 110, sw=10),
          circle(1058, 110, 13, fill=WHITE)]
    # 오일 쿨러
    o += radiator(620, 232, 220, 158, ON, fins=15, r=10)
    o.append(path("M 820,232 L 820,264 L 652,264 A 23 23 0 0 0 652,310 L 808,310 A 23 23 0 0 1 808,356 L 660,356 L 660,388",
                  stroke=NAVY, sw=6))
    # 쿨러 팬과 바람
    o += fan(955, 311, 66, ON)
    for ay in (281, 311, 341):
        o.append(arrow([(884, ay), (850, ay)], SKY, sw=4, size=10))
    # 센서 자리
    o += [line(796, 178, 814, 178, sw=3)] + gauge(780, 178, ON, hot=True)
    o += [line(480, 84, 480, 104, sw=3)] + gauge(480, 68, NORM)
    o += [line(1004, 356, 1036, 384, sw=3)] + gauge(1048, 394, NORM)
    return svg(o)


# ───────────────────────── 2. 데이터 리니지 (단계별 강조) ─────────────────────────

R1, R2 = 200, 365
X = dict(equip=85, plc=245, emqx=410, ingest=607, log=814, det=1085, tsdb=870, graf=1085, fuxa=410)


def lineage(stage: int) -> str:
    states = {
        0: dict(on="equip plc emqx fuxa ingest log tsdb det graf", norm="", aon="all", anorm=""),
        2: dict(on="ingest log", norm="emqx", aon="emqx_ing ing_log", anorm=""),
        3: dict(on="tsdb det", norm="log graf fuxa emqx", aon="log_tsdb log_det", anorm="tsdb_graf emqx_fuxa"),
    }[stage]

    def st(name):
        return ON if name in states["on"].split() else NORM if name in states["norm"].split() else OFF

    def ar(name, pts):
        if states["aon"] == "all" or name in states["aon"].split():
            return arrow(pts, BLUE, sw=5, size=14)
        if name in states["anorm"].split():
            return arrow(pts, NAVY, sw=3, size=11)
        return arrow(pts, GREY, sw=3, size=11)

    o: list[str] = []
    # 영역 띠: OT / DMZ / IT
    o += [rect(14, 8, 486, 504, 14, fill=LIGHT, stroke="none", sw=0),
          rect(514, 8, 186, 504, 14, fill=PALE if stage in (0, 2) else LIGHT, stroke=SKY if stage == 2 else "none", sw=2.5 if stage == 2 else 0),
          rect(714, 8, 472, 504, 14, fill=LIGHT, stroke="none", sw=0)]
    # 화살표(그림 조각보다 먼저)
    o += [ar("eq_plc", [(136, R1), (186, R1)]), ar("plc_emqx", [(302, R1), (358, R1)]),
          ar("emqx_ing", [(460, R1), (548, R1)]), ar("ing_log", [(664, R1), (722, R1)]),
          ar("emqx_fuxa", [(410, R1 + 54), (410, R2 - 54)]),
          ar("log_tsdb", [(870, R1 + 30), (870, R2 - 54)]), ar("log_det", [(904, R1), (1026, R1)]),
          ar("tsdb_graf", [(932, R2), (1020, R2)])]
    o += equip_mini(X["equip"], R1, st("equip"))
    o += plc(X["plc"], R1, st("plc"))
    o += server(X["emqx"], R1, st("emqx"))
    o += monitor(X["fuxa"], R2, st("fuxa"), "hmi")
    o += window(X["ingest"], R1, st("ingest"), "gate")
    o += logstrip(730, R1, st("log"))
    o += cylinder_db(X["tsdb"], R2, st("tsdb"))
    o += window(X["det"], R1, st("det"), "detect")
    o += bell(1163, R1 - 4, st("det"), 0.9)
    o += monitor(X["graf"], R2, st("graf"), "chart")
    return svg(o)


def envelope(cx, cy, st: St):
    """메시지 한 통(봉투). 화살표 위에 얹어 그 화살표로 가는 메시지를 나타낸다."""
    return [rect(cx - 24, cy - 17, 48, 34, 5, fill=st.fill, stroke=st.line, sw=3),
            path(f"M {cx - 24},{cy - 15} L {cx},{cy + 4} L {cx + 24},{cy - 15}", stroke=st.line, sw=3)]


def lineage_mqtt() -> str:
    """리니지 1단계(MQTT)만 크게: 설비 → 게이트웨이(발행자) → 브로커 → 구독자 둘. 아직 다루지 않은 IT 구간은 그리지 않는다.
    라벨은 그림 하나에 하나씩 붙는다: 봉투(토픽) · 브로커는 위, 나머지는 아래. 그림 사이 간격은 고르게 둔다."""
    w, h, r1, r2 = 1100, 500, 190, 345
    x = dict(equip=110, plc=350, env=530, emqx=710, ingest=980)
    o: list[str] = [rect(12, 8, 848, 484, 14, fill=LIGHT, stroke="none", sw=0),        # OT
                    rect(875, 8, 213, 484, 14, fill=LIGHT, stroke="none", sw=0)]       # DMZ
    o += [arrow([(161, r1), (291, r1)], BLUE, sw=5, size=14), arrow([(407, r1), (658, r1)], BLUE, sw=5, size=14),
          arrow([(760, r1), (920, r1)], BLUE, sw=5, size=14), arrow([(x["emqx"], r1 + 54), (x["emqx"], r2 - 54)], BLUE, sw=5, size=14)]
    o += equip_mini(x["equip"], r1, ON) + plc(x["plc"], r1, ON) + envelope(x["env"], r1, ON) + server(x["emqx"], r1, ON)
    o += monitor(x["emqx"], r2, ON, "hmi") + window(x["ingest"], r1, ON, "gate")
    return svg(o, w, h)


KG_NODES = {"asset": (80, 100, 56), "comp": (385, 100, 64), "sen": (150, 440, 56), "sym": (470, 440, 60),
            "fm": (700, 262, 76), "cause": (975, 88, 56), "skill": (925, 450, 60), "doc": (1128, 262, 80)}
KG_EDGES = [("asset", "comp"), ("comp", "sen"), ("sym", "sen"), ("sym", "fm"), ("cause", "fm"), ("fm", "comp"), ("fm", "skill"),
            ("skill", "doc")]


def kg_map() -> str:
    """HYD 지식 그래프 지도(Neo4j 그래프 꼴): 동그라미 노드를 흩어 놓고 대각선으로 잇는다. 1인치 = 100(본문 12.13 × 5.4).
    고장 유형은 가운데 진한 원, 고장 유형에 직접 붙은 넷은 파란 테두리, 바깥 셋(설비 · 센서 · 매뉴얼 절)은 회색.
    노드 이름과 관계 이름은 덱 라벨로 얹는다(좌표는 덱 MD). 읽는 순서는 설비(왼쪽 위)에서 오른쪽으로."""
    ring = {"fm": (SKY, NAVY, 4), "comp": (PALE, BLUE, 3), "skill": (PALE, BLUE, 3), "cause": (PALE, BLUE, 3), "sym": (PALE, BLUE, 3),
            "asset": (LIGHT, GREY, 3), "sen": (LIGHT, GREY, 3), "doc": (LIGHT, GREY, 3)}
    o: list[str] = []
    # 이 지도만의 선: 구성 요소 → 센서는 빼고(증상 → 센서 하나로 센서 쪽을 보인다), 근본 조치가 어느 원인을 없애는지 잇는 조치 방법 → 원인을 더한다.
    edges = [e for e in KG_EDGES if e != ("comp", "sen")] + [("skill", "cause")]
    for a, b in edges:
        (ax, ay, ar), (bx, by, br) = KG_NODES[a], KG_NODES[b]
        d_ = math.hypot(bx - ax, by - ay)
        ux, uy = (bx - ax) / d_, (by - ay) / d_
        hot = "fm" in (a, b)
        o.append(arrow([(ax + ux * (ar + 5), ay + uy * (ar + 5)), (bx - ux * (br + 9), by - uy * (br + 9))],
                       BLUE if hot else NAVY, sw=4 if hot else 3, size=13))
    for k, (x, y, r) in KG_NODES.items():
        fill, stroke, sw = ring[k]
        o.append(circle(x, y, r, fill=fill, stroke=stroke, sw=sw))
    return svg(o, 1213, 540)


# ───────────────────────── 3. 원인 후보 ─────────────────────────

def causes() -> str:
    o: list[str] = []
    rows = (100, 262, 424)
    # 가지: 맨 위(확인된 원인)만 진하게
    for i, by in enumerate(rows):
        c, sw = (BLUE, 5) if i == 0 else (GREY, 4)
        o.append(path(f"M 196,262 L 250,262 C 310,262 300,{by} 360,{by} L 420,{by}", stroke=c, sw=sw))
        o.append(arrow([(486, by), (566, by)], c, sw=sw, size=13))
    o.append(path("M 196,262 L 250,262", stroke=BLUE, sw=5))
    # 증상: 온도계 + 오르는 화살표
    o += thermo(110, 300, ON, s=1.7, level=0.72)
    o.append(arrow([(166, 290), (166, 176)], BLUE, sw=5, size=14))
    # 가지마다 가르는 센서 자리
    o += gauge(453, rows[0], ON, r=30, hot=True, ang=-140)
    o += gauge(453, rows[1], NORM, r=30, ang=-120)
    o += gauge(453, rows[2], NORM, r=30, ang=-110)
    # 원인 1: 핀이 막힌 쿨러
    o += radiator(582, rows[0] - 46, 116, 92, ON, fins=9)
    o += dust(640, rows[0], ON, 1.25)
    # 원인 2: 흔들리는 팬
    o += fan(640, rows[1], 42, NORM, rot=35)
    for sgn in (-1, 1):
        for k, rr in enumerate((54, 66)):
            a0, a1 = math.radians(-28), math.radians(28)
            x0, y0 = 640 + sgn * rr * math.cos(a0), rows[1] + rr * math.sin(a0)
            x1, y1 = 640 + sgn * rr * math.cos(a1), rows[1] + rr * math.sin(a1)
            o.append(path(f"M {x0:.1f},{y0:.1f} A {rr} {rr} 0 0 {1 if sgn > 0 else 0} {x1:.1f},{y1:.1f}", stroke=NAVY, sw=3))
    # 원인 3: 더운 캐비닛
    cy = rows[2]
    o += [rect(596, cy - 50, 76, 100, 6, fill=WHITE), line(634, cy - 50, 634, cy + 50, sw=2.5)]
    for dy in (-30, -18, -6):
        o += [line(606, cy + dy, 624, cy + dy, sw=2.5), line(644, cy + dy, 662, cy + dy, sw=2.5)]
    o += [circle(628, cy + 12, 2.5, fill=NAVY, sw=1), circle(640, cy + 12, 2.5, fill=NAVY, sw=1)]
    for wx in (690, 708, 726):
        o.append(path(f"M {wx},{cy + 40} q -10,-13 0,-26 t 0,-26 t 0,-26", stroke=NAVY, sw=3))
    return svg(o)


# ───────────────────────── 4. 관계 그림 ─────────────────────────

def relation() -> str:
    o: list[str] = []
    A, B, C, D = (170, 200), (600, 200), (1030, 200), (600, 432)
    o += [arrow([(236, 200), (532, 200)], NAVY, sw=5, size=15), arrow([(964, 200), (668, 200)], NAVY, sw=5, size=15),
          arrow([(600, 268), (600, 370)], NAVY, sw=5, size=15)]
    o += [circle(*A, 60, fill=WHITE), circle(*B, 62, fill=SKY), circle(*C, 60, fill=WHITE), circle(*D, 56, fill=WHITE)]
    # 증상: 오르는 온도
    o += thermo(A[0] - 12, A[1] + 22, ON, s=0.72, level=0.7)
    o.append(arrow([(A[0] + 18, A[1] + 20), (A[0] + 18, A[1] - 30)], BLUE, sw=4, size=11))
    # 고장 유형: 제 구실을 못 하는 쿨러(사선)
    o += radiator(B[0] - 34, B[1] - 26, 68, 52, NORM, fins=7, r=6)
    o.append(line(B[0] - 40, B[1] + 34, B[0] + 40, B[1] - 34, stroke=NAVY, sw=5))
    # 원인: 핀에 낀 오염
    o += radiator(C[0] - 34, C[1] - 26, 68, 52, NORM, fins=7, r=6)
    o += dust(C[0], C[1], ON, 0.72)
    # 조치: 팬
    o += fan(D[0], D[1], 34, ON, rot=20, hot=True)
    return svg(o)



# ───────────────────────── 축소 배치 도우미 ─────────────────────────
import re


def g(cx, cy, k, parts, boost=None):
    """원점 기준으로 그린 조각을 (cx, cy)에 k배로 놓는다. 선 굵기는 너무 가늘어지지 않게 되돌린다."""
    b = boost if boost is not None else min(1 / k, 1.9) * 0.85
    body = "\n".join(parts)
    body = re.sub(r'stroke-width="([\d.]+)"', lambda m: f'stroke-width="{float(m.group(1)) * b:.2f}"', body)
    return [f'<g transform="translate({cx} {cy}) scale({k})">', body, "</g>"]


def graph_icon(cx, cy, st: St):
    pts = [(-30, -22), (32, -30), (4, 6), (-34, 30), (36, 28)]
    o = [line(cx + pts[a][0], cy + pts[a][1], cx + pts[b][0], cy + pts[b][1], stroke=st.line)
         for a, b in ((0, 2), (1, 2), (2, 3), (2, 4), (0, 1))]
    for i, (dx, dy) in enumerate(pts):
        o.append(circle(cx + dx, cy + dy, 13 if i == 2 else 10, fill=st.accent if i == 2 else st.fill, stroke=st.line))
    return o


def agent_icon(cx, cy, st: St):
    return [line(cx, cy - 44, cx, cy - 30, stroke=st.line), circle(cx, cy - 48, 5, fill=st.accent, stroke=st.line, sw=2.5),
            rect(cx - 40, cy - 30, 80, 62, 14, fill=st.fill, stroke=st.line),
            circle(cx - 16, cy - 4, 7, fill=st.accent, stroke=st.line, sw=2.5), circle(cx + 16, cy - 4, 7, fill=st.accent, stroke=st.line, sw=2.5),
            line(cx - 14, cy + 16, cx + 14, cy + 16, stroke=st.line), line(cx - 48, cy - 6, cx - 40, cy - 6, stroke=st.line, sw=5),
            line(cx + 40, cy - 6, cx + 48, cy - 6, stroke=st.line, sw=5)]


def approve_icon(cx, cy, st: St):
    return [circle(cx - 10, cy - 22, 17, fill=st.fill, stroke=st.line),
            path(f"M {cx - 44},{cy + 38} Q {cx - 44},{cy + 4} {cx - 10},{cy + 4} Q {cx + 24},{cy + 4} {cx + 24},{cy + 38} Z", fill=st.fill, stroke=st.line),
            circle(cx + 30, cy + 20, 19, fill=st.accent, stroke=st.line),
            path(f"M {cx + 21},{cy + 20} L {cx + 28},{cy + 27} L {cx + 40},{cy + 13}", stroke=st.line, sw=4)]


def book_icon(cx, cy, st: St):
    return [path(f"M {cx},{cy - 34} Q {cx - 30},{cy - 48} {cx - 58},{cy - 38} L {cx - 58},{cy + 36} Q {cx - 30},{cy + 26} {cx},{cy + 40} Z", fill=st.fill, stroke=st.line),
            path(f"M {cx},{cy - 34} Q {cx + 30},{cy - 48} {cx + 58},{cy - 38} L {cx + 58},{cy + 36} Q {cx + 30},{cy + 26} {cx},{cy + 40} Z", fill=st.soft, stroke=st.line),
            *[line(cx - 46, cy + dy - 6, cx - 12, cy + dy, stroke=st.line, sw=2.5) for dy in (-18, -4, 10)],
            *[line(cx + 12, cy + dy, cx + 46, cy + dy - 6, stroke=st.line, sw=2.5) for dy in (-18, -4, 10)]]


def calendar_icon(cx, cy, st: St):
    o = [rect(cx - 50, cy - 40, 100, 84, 8, fill=st.fill, stroke=st.line), rect(cx - 50, cy - 40, 100, 24, 8, fill=st.accent, stroke=st.line),
         line(cx - 26, cy - 50, cx - 26, cy - 32, stroke=st.line, sw=5), line(cx + 26, cy - 50, cx + 26, cy - 32, stroke=st.line, sw=5)]
    for r_ in range(3):
        for c_ in range(4):
            hot = (r_, c_) == (1, 2)
            o.append(rect(cx - 38 + c_ * 20, cy - 6 + r_ * 15, 13, 9, 2, fill=st.line if hot else st.soft, stroke=st.line, sw=1.5))
    return o


def cabinet(cx, cy, st: St):
    o = [rect(cx - 38, cy - 50, 76, 100, 6, fill=st.fill, stroke=st.line), line(cx, cy - 50, cx, cy + 50, stroke=st.line, sw=2.5)]
    for dy in (-30, -18, -6):
        o += [line(cx - 28, cy + dy, cx - 10, cy + dy, stroke=st.line, sw=2.5), line(cx + 10, cy + dy, cx + 28, cy + dy, stroke=st.line, sw=2.5)]
    return o


def broken_cooler(cx, cy, st: St):
    return radiator(cx - 44, cy - 34, 88, 68, st, fins=8, r=7) + [line(cx - 52, cy + 44, cx + 52, cy - 44, stroke=st.line, sw=6)]


def dusty_cooler(cx, cy, st: St):
    return radiator(cx - 44, cy - 34, 88, 68, st, fins=8, r=7) + dust(cx, cy, st, 0.95)


def dots(x1, y1, x2, y2, color=GREY, gap=16, r=3.2):
    n = max(2, int(math.hypot(x2 - x1, y2 - y1) // gap))
    return [circle(x1 + (x2 - x1) * i / n, y1 + (y2 - y1) * i / n, r, fill=color, stroke="none", sw=0) for i in range(n + 1)]


# ───────────────────────── 5. HYD의 9개 기능 계층 ─────────────────────────

def layers(focus: str) -> str:
    """focus: 'all' 또는 '79'(Layer 7~9 강조)."""
    o: list[str] = []
    top, pitch, hgt = 40, 53, 47
    zones = {9: "I", 8: "I", 7: "I", 6: "OI", 5: "I", 4: "I", 3: "DI", 2: "O", 1: "O"}
    icons = {9: approve_icon, 8: agent_icon, 7: graph_icon, 6: lambda x, y, st: monitor(x, y, st, "hmi"),
             5: cylinder_db, 4: lambda x, y, st: window(x, y, st, "detect"), 3: None, 2: server, 1: equip_mini}
    for col, zx in (("O", 1040), ("D", 1100), ("I", 1160)):
        o.append(rect(zx - 24, top - 4, 48, pitch * 9 + 2, 12, fill=LIGHT, stroke="none", sw=0))
    for i, n in enumerate(range(9, 0, -1)):
        y = top + i * pitch
        hot = focus == "79" and n >= 7
        dim = focus == "79" and n < 7
        st = ON if hot else NORM if not dim else OFF
        o.append(rect(14, y, 990, hgt, 10, fill=PALE if hot else LIGHT, stroke=SKY if hot else "none", sw=2.5 if hot else 0))
        yc = y + hgt / 2
        if n == 3:
            o += g(58, yc, 0.42, logstrip(-84, 0, st))
        else:
            o += g(58, yc, 0.40, icons[n](0, 0, st))
        for col, zx in (("O", 1040), ("D", 1100), ("I", 1160)):
            if col in zones[n]:
                o.append(circle(zx, yc, 12, fill=SKY if not dim else GREY, stroke=NAVY if not dim else GREY, sw=3))
            else:
                o.append(circle(zx, yc, 3.5, fill=GREY, stroke="none", sw=0))
    return svg(o)


# ───────────────────────── 8. 흩어진 정보 ─────────────────────────

def scattered() -> str:
    o: list[str] = []
    C = (600, 205)
    spots = {"tsdb": (190, 90), "plc": (190, 335), "book": (985, 90), "cal": (985, 335)}
    for x, y in spots.values():
        dx, dy = C[0] - x, C[1] - y
        d_ = math.hypot(dx, dy)
        o += dots(x + dx * 120 / d_, y + dy * 120 / d_, C[0] - dx * 96 / d_, C[1] - dy * 96 / d_)
    o += [circle(*C, 78, fill=PALE, stroke=NAVY, sw=4)] + g(C[0], C[1] - 4, 2.4, bell(0, 0, ON), boost=0.55)
    o += g(*spots["tsdb"], 1.0, cylinder_db(0, 0, ON))
    o += g(*spots["plc"], 1.05, plc(0, 0, ON))
    o += g(*spots["book"], 1.05, book_icon(0, 0, ON))
    o += g(*spots["cal"], 1.05, calendar_icon(0, 0, ON))
    return svg(o)


# ───────────────────────── 9. 노드 · 관계 · 방향 ─────────────────────────

def node_rel() -> str:
    o: list[str] = []
    A, B = (250, 250), (950, 250)
    o.append(arrow([(366, 250), (834, 250)], NAVY, sw=8, size=24))
    o += [circle(*A, 108, fill=WHITE, sw=5), circle(*B, 108, fill=SKY, sw=5)]
    o += g(*A, 1.5, dusty_cooler(0, 0, ON), boost=0.8)
    o += g(*B, 1.5, broken_cooler(0, 0, NORM), boost=0.8)
    return svg(o)


# ───────────────────────── 10. 질문에 답하는 경로 (단계별 강조) ─────────────────────────

def walk(stage: int) -> str:
    P, S, F, K = (95, 205), (275, 205), (465, 205), (465, 432)
    Cs = [(700, 80), (700, 205), (700, 330)]
    Es = [(865, 80), (865, 205), (865, 330)]

    def stn(name):
        cur = {1: "P S F PS SF", 2: "C0 C1 C2 E0 E1 E2 CF0 CF1 CF2 CE0 CE1 CE2", 3: "K FK C0 E0"}[stage].split()
        done = {1: "", 2: "P S F PS SF", 3: "P S F PS SF CF0 CE0"}[stage].split()
        return ON if name in cur else NORM if name in done else OFF

    def ar(name, pts):
        st = stn(name)
        return arrow(pts, BLUE if st is ON else NAVY if st is NORM else GREY, sw=5 if st is ON else 3.5, size=14 if st is ON else 12)

    o: list[str] = []
    o += [ar("PS", [(143, 205), (225, 205)]), ar("SF", [(323, 205), (407, 205)]), ar("FK", [(465, 261), (465, 380)])]
    for i, (c, e) in enumerate(zip(Cs, Es)):
        ang = math.atan2(F[1] - c[1], F[0] - c[0])
        o.append(ar(f"CF{i}", [(c[0] + 48 * math.cos(ang), c[1] + 48 * math.sin(ang)), (F[0] - 58 * math.cos(ang), F[1] - 58 * math.sin(ang))]))
        o.append(ar(f"CE{i}", [(c[0] + 48, c[1]), (e[0] - 40, e[1])]))

    def node(c, r, name, parts_fn, k, fill_hot=False):
        st = stn(name)
        out = [circle(c[0], c[1], r, fill=(SKY if fill_hot else PALE) if st is ON else WHITE, stroke=st.line, sw=4 if st is not OFF else 3)]
        return out + g(c[0], c[1], k, parts_fn(0, 0, st), boost=1.0 if k > 0.6 else None)

    o += node(P, 46, "P", lambda x, y, st: bell(x, y - 3, st, 1.6), 1.0)
    o += node(S, 46, "S", lambda x, y, st: thermo(x - 8, y + 22, st, s=0.62, level=0.7) + [arrow([(x + 16, y + 18), (x + 16, y - 22)], BLUE if st is ON else st.line, sw=3.5, size=9)], 1.0)
    o += node(F, 54, "F", broken_cooler, 0.62, fill_hot=True)
    o += node(Cs[0], 44, "C0", dusty_cooler, 0.52)
    o += node(Cs[1], 44, "C1", lambda x, y, st: fan(x, y, 46, st, rot=35), 0.62)
    o += node(Cs[2], 44, "C2", cabinet, 0.52)
    for i, e in enumerate(Es):
        st = stn(f"E{i}")
        o += gauge(e[0], e[1], st, r=30, hot=(st is ON and (stage == 3 or i == 0)) or (stage == 3 and i == 0), ang=(-140, -120, -110)[i])
    o += node(K, 48, "K", lambda x, y, st: fan(x, y, 46, st, rot=20, hot=True), 0.7)
    return svg(o)


# 경로 그림(압축판, 2026-10-14): 지식그래프_지도.svg와 같은 그래프 꼴(동그라미 노드 · 대각선 · 글자는 덱 라벨).
# 1단계 = 이상 패턴 → 증상 → 고장 유형, 2단계 = 원인 후보 · 증거 · 완화 조치. 좌표를 바꾸면 덱 MD의 라벨 좌표도 함께 고친다.
WALK = {"P": (110, 110, 98), "S": (265, 420, 66), "F": (480, 250, 80), "K": (620, 460, 72),
        "C0": (770, 95, 78), "C1": (830, 280, 78), "C2": (800, 455, 78),
        "E0": (1075, 95, 64), "E1": (1135, 280, 64), "E2": (1110, 455, 64)}
WALK_WH = (1213, 540)            # 지도와 같은 축척(1인치 = 100)
WALK_EDGES = [("P", "S"), ("S", "F"), ("C0", "F"), ("C1", "F"), ("C2", "F"), ("C0", "E0"), ("C1", "E1"), ("C2", "E2"), ("F", "K")]


def walk2(stage: int) -> str:
    on = {1: "P S F", 2: "C0 C1 C2 E0 E1 E2 K"}[stage].split()
    done = {1: [], 2: ["P", "S", "F"]}[stage]
    hot = {1: set(), 2: {"C0", "E0"}}[stage]          # 2단계에서 확인된 원인과 그 증거

    def state(k):
        return "on" if k in on else "done" if k in done else "off"

    o: list[str] = []
    for a, b in WALK_EDGES:
        (ax, ay, ar), (bx, by, br) = WALK[a], WALK[b]
        d_ = math.hypot(bx - ax, by - ay)
        ux, uy = (bx - ax) / d_, (by - ay) / d_
        if stage == 1:
            color = BLUE if (a, b) in (("P", "S"), ("S", "F")) else GREY
        else:
            color = NAVY if a in ("P", "S") else BLUE if {a, b} & (hot | {"K"}) else NAVY
        strong = color == BLUE
        o.append(arrow([(ax + ux * (ar + 5), ay + uy * (ar + 5)), (bx - ux * (br + 9), by - uy * (br + 9))],
                       color, sw=4 if strong else 3, size=13))
    for k, (x, y, r) in WALK.items():
        st = state(k)
        if k == "F" and st != "off":
            fill, stroke, sw = SKY, NAVY, 4
        elif st == "on":
            fill, stroke, sw = (SKY if k in hot else PALE), BLUE, 3
        elif st == "done":
            fill, stroke, sw = WHITE, NAVY, 3
        else:
            fill, stroke, sw = LIGHT, GREY, 3
        o.append(circle(x, y, r, fill=fill, stroke=stroke, sw=sw))
    return svg(o, *WALK_WH)



# ───────────────────────── 11. 계층 그림(줄 수를 줄여 크게) ─────────────────────────

def layer_rows(ns, hot=()) -> str:
    o: list[str] = []
    top = 40
    pitch = (H - top - 4) / len(ns)
    hgt = pitch - 6
    k = min(0.40 * pitch / 53, 0.95)
    zones = {9: "I", 8: "I", 7: "I", 6: "OI", 5: "I", 4: "I", 3: "DI", 2: "O", 1: "O"}
    icons = {9: approve_icon, 8: agent_icon, 7: graph_icon, 6: lambda x, y, st: monitor(x, y, st, "hmi"),
             5: cylinder_db, 4: lambda x, y, st: window(x, y, st, "detect"), 3: None, 2: server, 1: equip_mini}
    ix = 58 if len(ns) > 6 else 78 if len(ns) > 3 else 100
    for col, zx in (("O", 1040), ("D", 1100), ("I", 1160)):
        o.append(rect(zx - 24, top - 4, 48, pitch * len(ns) + 2, 12, fill=LIGHT, stroke="none", sw=0))
    for i, n in enumerate(ns):
        y = top + i * pitch
        st = ON if n in hot else NORM
        o.append(rect(14, y, 990, hgt, 10, fill=PALE if n in hot else LIGHT, stroke=SKY if n in hot else "none", sw=2.5 if n in hot else 0))
        yc = y + hgt / 2
        if n == 3:
            o += g(ix, yc, k * 1.05, logstrip(-84, 0, st))
        else:
            o += g(ix, yc, k, icons[n](0, 0, st))
        for col, zx in (("O", 1040), ("D", 1100), ("I", 1160)):
            if col in zones[n]:
                o.append(circle(zx, yc, 12, fill=SKY, stroke=NAVY, sw=3))
            else:
                o.append(circle(zx, yc, 3.5, fill=GREY, stroke="none", sw=0))
    return svg(o)


# ───────────────────────── 12. 설비에서 근거 문서까지의 연결 ─────────────────────────

def connect() -> str:
    o: list[str] = []
    N = {"sen": (200, 110), "comp": (600, 110), "asset": (1000, 110), "sym": (200, 270), "fm": (600, 270),
         "cause": (1000, 270), "skill": (600, 430), "doc": (1000, 430)}
    R = 44

    def link(a, b):
        (ax, ay), (bx, by) = N[a], N[b]
        d_ = math.hypot(bx - ax, by - ay)
        ux, uy = (bx - ax) / d_, (by - ay) / d_
        ra = 52 if a == "fm" else R
        rb = 52 if b == "fm" else R
        return arrow([(ax + ux * (ra + 4), ay + uy * (ra + 4)), (bx - ux * (rb + 6), by - uy * (rb + 6))], NAVY, sw=4, size=13)

    for a, b in (("asset", "comp"), ("comp", "sen"), ("sym", "sen"), ("sym", "fm"), ("fm", "comp"), ("cause", "fm"),
                 ("fm", "skill"), ("skill", "doc")):
        o.append(link(a, b))
    for name, (x, y) in N.items():
        hot = name == "fm"
        o.append(circle(x, y, 52 if hot else R, fill=SKY if hot else WHITE, sw=4))
    o += gauge(*N["sen"], ON, r=26, hot=True)
    o += g(*N["comp"], 0.5, radiator(-44, -34, 88, 68, ON, fins=8, r=7))
    o += g(*N["asset"], 0.62, equip_mini(0, 0, ON), boost=1.2)
    o += g(N["sym"][0], N["sym"][1], 1.0, thermo(-8, 22, ON, s=0.6, level=0.7) + [arrow([(16, 18), (16, -22)], BLUE, sw=3.5, size=9)], boost=1.0)
    o += g(*N["fm"], 0.6, broken_cooler(0, 0, NORM))
    o += g(*N["cause"], 0.5, dusty_cooler(0, 0, ON))
    o += g(*N["skill"], 0.66, fan(0, 0, 46, ON, rot=20, hot=True), boost=1.0)
    o += g(*N["doc"], 0.52, book_icon(0, 0, ON))
    return svg(o)



# ───────────────────────── 13. 같은 그림에서 한 부분만 밝히는 판 ─────────────────────────
# 승인된 그림의 모양은 그대로 두고, 밝히지 않는 조각의 색만 흐리게 바꾼다(다시 그리지 않는다).

def dim(parts):
    out = []
    for p in parts:
        for a, b in ((NAVY, "#D3D9E1"), (BLUE, "#D3D9E1"), (SKY, "#F3F6F9"), (PALE, "#FFFFFF")):
            p = p.replace(a, b)
        out.append(p)
    return out


def pick(focus, name, parts):
    return parts if focus is None or name in focus else dim(parts)


def hyd_unit_f(focus=None) -> str:
    o: list[str] = []
    P = lambda name, parts: o.extend(pick(focus, name, parts))
    P("tank", [rect(70, 330, 400, 150, 12, fill=WHITE), rect(75, 374, 390, 101, 8, fill=PALE, stroke="none", sw=0),
               path("M 75,374 q 15,-8 30,0 t 30,0 t 30,0 t 30,0 t 30,0 t 30,0 t 30,0 t 30,0 t 30,0 t 30,0 t 30,0 t 30,0 t 30,0",
                    stroke=NAVY, sw=2.5)])
    P("suction", pipe("M 300,318 L 300,448"))
    P("press", pipe("M 300,240 L 300,110 L 760,110"))
    P("ret", pipe("M 820,140 L 820,232", inner=SKY))
    P("out", pipe("M 660,388 L 660,422 L 472,422"))
    P("suction", [rect(285, 440, 30, 22, 4, fill=WHITE, sw=3), line(293, 444, 293, 458, sw=2), line(300, 444, 300, 458, sw=2),
                  line(307, 444, 307, 458, sw=2)])
    P("suction", [head(300, 352, -math.pi / 2, NAVY, 12)])
    P("press", [head(300, 168, -math.pi / 2, NAVY, 12), head(640, 110, 0, NAVY, 12)])
    P("ret", [head(820, 216, math.pi / 2, NAVY, 12)])
    P("out", [head(552, 422, math.pi, NAVY, 12)])
    pump = [rect(108, 242, 124, 76, 16, fill=WHITE), rect(124, 318, 22, 12, 2, fill=WHITE, sw=3), rect(194, 318, 22, 12, 2, fill=WHITE, sw=3)]
    for fx in (134, 154, 174, 194, 214):
        pump.append(line(fx, 254, fx, 306, sw=2.5))
    pump += [line(232, 280, 262, 280, sw=9), circle(300, 280, 40, fill=PALE), circle(287, 280, 15, fill=WHITE, sw=3),
             circle(313, 280, 15, fill=WHITE, sw=3)]
    P("pump", pump)
    P("load", [rect(760, 80, 200, 60, 8, fill=WHITE), rect(852, 85, 14, 50, 2, fill=NAVY, sw=2), line(866, 110, 1044, 110, sw=10),
               circle(1058, 110, 13, fill=WHITE)])
    P("cooler", radiator(620, 232, 220, 158, ON, fins=15, r=10) + [
        path("M 820,232 L 820,264 L 652,264 A 23 23 0 0 0 652,310 L 808,310 A 23 23 0 0 1 808,356 L 660,356 L 660,388",
             stroke=NAVY, sw=6)])
    fanp = fan(955, 311, 66, ON)
    for ay in (281, 311, 341):
        fanp.append(arrow([(884, ay), (850, ay)], SKY, sw=4, size=10))
    P("fan", fanp)
    P("ts1", [line(796, 178, 814, 178, sw=3)] + gauge(780, 178, ON, hot=True))
    P("ps1", [line(480, 84, 480, 104, sw=3)] + gauge(480, 68, NORM))
    P("vs1", [line(1004, 356, 1036, 384, sw=3)] + gauge(1048, 394, NORM))
    return svg(o)


def lineage_zone(zone: str) -> str:
    """리니지 그림에서 한 보안 영역만 밝힌다. zone: 'OT' | 'IT'."""
    on = {"OT": "equip plc emqx fuxa", "IT": "log tsdb det graf"}[zone].split()
    aon = {"OT": "eq_plc plc_emqx emqx_fuxa", "IT": "log_tsdb log_det tsdb_graf"}[zone].split()
    st = lambda name: ON if name in on else OFF
    ar = lambda name, pts: arrow(pts, BLUE, sw=5, size=14) if name in aon else arrow(pts, GREY, sw=3, size=11)
    o: list[str] = []
    for z, (x, w) in (("OT", (14, 486)), ("DMZ", (514, 186)), ("IT", (714, 472))):
        hot = z == zone
        o.append(rect(x, 8, w, 504, 14, fill=PALE if hot else LIGHT, stroke=SKY if hot else "none", sw=2.5 if hot else 0))
    o += [ar("eq_plc", [(136, R1), (186, R1)]), ar("plc_emqx", [(302, R1), (358, R1)]),
          ar("emqx_ing", [(460, R1), (548, R1)]), ar("ing_log", [(664, R1), (722, R1)]),
          ar("emqx_fuxa", [(410, R1 + 54), (410, R2 - 54)]),
          ar("log_tsdb", [(870, R1 + 30), (870, R2 - 54)]), ar("log_det", [(904, R1), (1026, R1)]),
          ar("tsdb_graf", [(932, R2), (1020, R2)])]
    o += equip_mini(X["equip"], R1, st("equip")) + plc(X["plc"], R1, st("plc")) + server(X["emqx"], R1, st("emqx"))
    o += monitor(X["fuxa"], R2, st("fuxa"), "hmi") + window(X["ingest"], R1, st("ingest"), "gate")
    o += logstrip(730, R1, st("log")) + cylinder_db(X["tsdb"], R2, st("tsdb")) + window(X["det"], R1, st("det"), "detect")
    o += bell(1163, R1 - 4, st("det"), 0.9) + monitor(X["graf"], R2, st("graf"), "chart")
    return svg(o)


def causes_f(focus: int) -> str:
    """원인 후보 그림에서 가지 하나만 밝힌다(0 핀 오염 · 1 팬 구동 불량 · 2 주변 온도 상승)."""
    o: list[str] = []
    rows = (100, 262, 424)
    for i, by in enumerate(rows):
        c, sw = (BLUE, 5) if i == focus else (GREY, 4)
        o.append(path(f"M 196,262 L 250,262 C 310,262 300,{by} 360,{by} L 420,{by}", stroke=c, sw=sw))
        o.append(arrow([(486, by), (566, by)], c, sw=sw, size=13))
    o.append(path("M 196,262 L 250,262", stroke=BLUE, sw=5))
    o += thermo(110, 300, ON, s=1.7, level=0.72)
    o.append(arrow([(166, 290), (166, 176)], BLUE, sw=5, size=14))
    angs = (-140, -120, -110)
    for i, by in enumerate(rows):
        gz = gauge(453, by, ON if i == focus else NORM, r=30, hot=(i == focus), ang=angs[i])
        o += gz if i == focus else dim(gz)
    c0 = radiator(582, rows[0] - 46, 116, 92, ON, fins=9) + dust(640, rows[0], ON, 1.25)
    c1 = fan(640, rows[1], 42, NORM, rot=35)
    for sgn in (-1, 1):
        for rr in (54, 66):
            a0, a1 = math.radians(-28), math.radians(28)
            x0, y0 = 640 + sgn * rr * math.cos(a0), rows[1] + rr * math.sin(a0)
            x1, y1 = 640 + sgn * rr * math.cos(a1), rows[1] + rr * math.sin(a1)
            c1.append(path(f"M {x0:.1f},{y0:.1f} A {rr} {rr} 0 0 {1 if sgn > 0 else 0} {x1:.1f},{y1:.1f}", stroke=NAVY, sw=3))
    cy = rows[2]
    c2 = [rect(596, cy - 50, 76, 100, 6, fill=WHITE), line(634, cy - 50, 634, cy + 50, sw=2.5)]
    for dy in (-30, -18, -6):
        c2 += [line(606, cy + dy, 624, cy + dy, sw=2.5), line(644, cy + dy, 662, cy + dy, sw=2.5)]
    c2 += [circle(628, cy + 12, 2.5, fill=NAVY, sw=1), circle(640, cy + 12, 2.5, fill=NAVY, sw=1)]
    for wx in (690, 708, 726):
        c2.append(path(f"M {wx},{cy + 40} q -10,-13 0,-26 t 0,-26 t 0,-26", stroke=NAVY, sw=3))
    for i, c in enumerate((c0, c1, c2)):
        o += c if i == focus else dim(c)
    return svg(o)


def relation_f(focus: str) -> str:
    """관계 그림에서 한 부분만 밝힌다. 'meet' = 증상 · 원인이 고장 유형에서 만남, 'act' = 조치."""
    A, B, C, D = (170, 200), (600, 200), (1030, 200), (600, 432)
    a1 = [arrow([(236, 200), (532, 200)], NAVY, sw=5, size=15)]
    a2 = [arrow([(964, 200), (668, 200)], NAVY, sw=5, size=15)]
    a3 = [arrow([(600, 268), (600, 370)], NAVY, sw=5, size=15)]
    nA = [circle(*A, 60, fill=WHITE)] + thermo(A[0] - 12, A[1] + 22, ON, s=0.72, level=0.7) + [
        arrow([(A[0] + 18, A[1] + 20), (A[0] + 18, A[1] - 30)], BLUE, sw=4, size=11)]
    nB = [circle(*B, 62, fill=SKY)] + radiator(B[0] - 34, B[1] - 26, 68, 52, NORM, fins=7, r=6) + [
        line(B[0] - 40, B[1] + 34, B[0] + 40, B[1] - 34, stroke=NAVY, sw=5)]
    nC = [circle(*C, 60, fill=WHITE)] + radiator(C[0] - 34, C[1] - 26, 68, 52, NORM, fins=7, r=6) + dust(C[0], C[1], ON, 0.72)
    nD = [circle(*D, 56, fill=WHITE)] + fan(D[0], D[1], 34, ON, rot=20, hot=True)
    on = {"meet": "a1 a2 A B C", "act": "a3 B D"}[focus].split()
    o: list[str] = []
    for name, parts in (("a1", a1), ("a2", a2), ("a3", a3), ("A", nA), ("B", nB), ("C", nC), ("D", nD)):
        o += parts if name in on else dim(parts)
    return svg(o)


def connect_f(focus: str) -> str:
    """연결 그림에서 한쪽만 밝힌다. 'asset' = 설비 · 부품 · 센서 쪽, 'diag' = 증상 · 고장 유형 · 원인 · 조치 · 근거 문서 쪽."""
    N = {"sen": (200, 110), "comp": (600, 110), "asset": (1000, 110), "sym": (200, 270), "fm": (600, 270),
         "cause": (1000, 270), "skill": (600, 430), "doc": (1000, 430)}
    R = 44
    on_nodes = {"asset": "sen comp asset", "diag": "sym fm cause skill doc"}[focus].split()
    on_links = {"asset": [("asset", "comp"), ("comp", "sen")],
                "diag": [("sym", "fm"), ("cause", "fm"), ("fm", "skill"), ("skill", "doc")]}[focus]

    def link(a, b):
        (ax, ay), (bx, by) = N[a], N[b]
        d_ = math.hypot(bx - ax, by - ay)
        ux, uy = (bx - ax) / d_, (by - ay) / d_
        ra = 52 if a == "fm" else R
        rb = 52 if b == "fm" else R
        return arrow([(ax + ux * (ra + 4), ay + uy * (ra + 4)), (bx - ux * (rb + 6), by - uy * (rb + 6))], NAVY, sw=4, size=13)

    o: list[str] = []
    for a, b in (("asset", "comp"), ("comp", "sen"), ("sym", "sen"), ("sym", "fm"), ("fm", "comp"), ("cause", "fm"),
                 ("fm", "skill"), ("skill", "doc")):
        o += [link(a, b)] if (a, b) in on_links else dim([link(a, b)])
    icon = {"sen": gauge(*N["sen"], ON, r=26, hot=True),
            "comp": g(*N["comp"], 0.5, radiator(-44, -34, 88, 68, ON, fins=8, r=7)),
            "asset": g(*N["asset"], 0.62, equip_mini(0, 0, ON), boost=1.2),
            "sym": g(N["sym"][0], N["sym"][1], 1.0, thermo(-8, 22, ON, s=0.6, level=0.7) + [arrow([(16, 18), (16, -22)], BLUE, sw=3.5, size=9)], boost=1.0),
            "fm": g(*N["fm"], 0.6, broken_cooler(0, 0, NORM)),
            "cause": g(*N["cause"], 0.5, dusty_cooler(0, 0, ON)),
            "skill": g(*N["skill"], 0.66, fan(0, 0, 46, ON, rot=20, hot=True), boost=1.0),
            "doc": g(*N["doc"], 0.52, book_icon(0, 0, ON))}
    for name, (x, y) in N.items():
        hot = name == "fm"
        parts = [circle(x, y, 52 if hot else R, fill=SKY if hot else WHITE, sw=4)] + icon[name]
        o += parts if name in on_nodes else dim(parts)
    return svg(o)


def scattered_f(focus: str) -> str:
    """흩어진 정보 그림에서 한 곳만 밝힌다. 'val' = TimescaleDB와 PLC, 'mes' = MES."""
    C = (600, 205)
    spots = {"tsdb": (190, 90), "plc": (190, 335), "book": (985, 90), "cal": (985, 335)}
    on = {"val": "tsdb plc", "mes": "cal"}[focus].split()
    o: list[str] = []
    for x, y in spots.values():
        dx, dy = C[0] - x, C[1] - y
        d_ = math.hypot(dx, dy)
        o += dots(x + dx * 120 / d_, y + dy * 120 / d_, C[0] - dx * 96 / d_, C[1] - dy * 96 / d_)
    o += [circle(*C, 78, fill=PALE, stroke=NAVY, sw=4)] + g(C[0], C[1] - 4, 2.4, bell(0, 0, ON), boost=0.55)
    icons = {"tsdb": g(*spots["tsdb"], 1.0, cylinder_db(0, 0, ON)), "plc": g(*spots["plc"], 1.05, plc(0, 0, ON)),
             "book": g(*spots["book"], 1.05, book_icon(0, 0, ON)), "cal": g(*spots["cal"], 1.05, calendar_icon(0, 0, ON))}
    for name, parts in icons.items():
        o += parts if name in on else dim(parts)
    return svg(o)


def data_command_routes() -> str:
    """1500×600. 위: 계측 데이터, 아래: 승인된 자동 명령. 글자는 MD에 둔다."""
    xs = (125, 375, 625, 875, 1125, 1375)
    yt, yb = 210, 430
    o = [rect(15, 60, 720, 525, 12, fill=LIGHT, stroke="none"),
         rect(755, 60, 240, 525, 12, fill=PALE, stroke="none"),
         rect(1015, 60, 470, 525, 12, fill=LIGHT, stroke="none")]
    for xa, xb in zip(xs, xs[1:]):
        o.append(arrow([(xa + 90, yt), (xb - 90, yt)], NAVY, sw=4, size=13))
        o.append(path(f"M {xb - 90},{yb} L {xa + 99},{yb}",
                      stroke=BLUE, sw=4, stroke_dasharray="10 8"))
        o.append(head(xa + 90, yb, math.pi, BLUE, 13))
    o += plc(xs[0], yt, ON) + plc(xs[1], yt, NORM)
    o += server(xs[2], yt, ON) + window(xs[3], yt, ON, "gate")
    o += logstrip(xs[4] - 72, yt, ON, n=6) + window(xs[5], yt, ON, "detect")
    o += plc(xs[0], yb, ON) + plc(xs[1], yb, NORM)
    o += server(xs[2], yb, ON)
    o.append('<g transform="translate(1750 0) scale(-1 1)">')
    o += window(xs[3], yb, ON, "gate")
    o.append('</g>')
    o += logstrip(xs[4] - 72, yb, ON, n=6)
    cx, cy = xs[5], yb
    pts = []
    for i in range(32):
        a = math.tau * i / 32
        r = 46 if i % 4 in (0, 3) else 36
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    o += [poly(pts, fill=WHITE, stroke=NAVY, sw=SW),
          circle(cx, cy, 18, fill=PALE, stroke=NAVY, sw=SW)]
    return svg(o, 1500, 600)


# ───────────────────────── 14. 판단 · 분기 · 전후를 보이는 그림 ─────────────────────────

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


def dash_rect(x, y, w, h, color=NAVY, sw=SW, on=10, off=8):
    return (dash_line(x, y, x + w, y, color, sw, on, off) + dash_line(x + w, y, x + w, y + h, color, sw, on, off)
            + dash_line(x + w, y + h, x, y + h, color, sw, on, off) + dash_line(x, y + h, x, y, color, sw, on, off))


def note_doc(cx, cy, st: St, mark=None):
    """기록 한 장. mark: 'gap' 빠진 줄(점선) · 'check' 확인 표시 · 'fix' 고친 줄(강조)."""
    o = [rect(cx - 50, cy - 64, 100, 128, 8, fill=st.fill, stroke=st.line)]
    for i, dy in enumerate((-40, -18, 4, 26)):
        if mark == "gap" and i == 2:
            o += dash_line(cx - 32, cy + dy, cx + 32, cy + dy, BLUE, 3.5, 7, 8)
        elif mark == "fix" and i == 2:
            o.append(line(cx - 32, cy + dy, cx + 32, cy + dy, stroke=SKY, sw=7))
        else:
            o.append(line(cx - 32, cy + dy, cx + 32, cy + dy, stroke=st.line, sw=2.5))
    if mark in ("check", "fix"):
        o.append(circle(cx + 46, cy + 56, 21, fill=SKY if mark == "fix" else st.soft, stroke=st.line, sw=3))
        o.append(path(f"M {cx + 36},{cy + 56} L {cx + 44},{cy + 64} L {cx + 57},{cy + 47}", stroke=st.line, sw=3.5))
    return o


def record_trail() -> str:
    """내 설명 → 출처 · 실습 기록 → 고친 설명."""
    o = [arrow([(215, 215), (505, 115)], BLUE, sw=4.5), arrow([(215, 290), (505, 375)], BLUE, sw=4.5),
         arrow([(690, 115), (975, 215)], NAVY, sw=4), arrow([(690, 375), (975, 290)], NAVY, sw=4)]
    o += note_doc(150, 250, ON, "gap") + book_icon(600, 100, ON) + note_doc(600, 372, NORM, "check") + note_doc(1040, 250, ON, "fix")
    return svg(o)


def offset_rows() -> str:
    """같은 레코드 다섯 칸 위에서 두 소비자의 읽기 위치. 위: 저장 서비스가 멈춘 동안, 아래: 돌아온 뒤."""
    x0, cw, ch = 300, 170, 62
    o: list[str] = []

    def row(y, det_to, sto_from, sto_to):
        for i in range(5):
            o.append(rect(x0 + i * cw, y - ch / 2, cw, ch, 4, fill=LIGHT if i < det_to else WHITE, stroke=NAVY, sw=3))
        o.append(arrow([(x0 + 6, y - ch / 2 - 22), (x0 + det_to * cw - 6, y - ch / 2 - 22)], BLUE, sw=7, size=18))
        if sto_from == sto_to:
            o.append(path(f"M {x0 + 6},{y + ch / 2 + 22} L {x0 + sto_to * cw - 6},{y + ch / 2 + 22}", stroke=NAVY, sw=7))
            xm = x0 + sto_to * cw
            o.append(line(xm - 6, y + ch / 2 + 10, xm - 6, y + ch / 2 + 34, stroke=NAVY, sw=7))
        else:
            o.append(path(f"M {x0 + 6},{y + ch / 2 + 22} L {x0 + sto_from * cw - 6},{y + ch / 2 + 22}", stroke=NAVY, sw=7))
            o.append(arrow([(x0 + sto_from * cw - 6, y + ch / 2 + 22), (x0 + sto_to * cw - 6, y + ch / 2 + 22)], SKY, sw=7, size=18))

    row(135, 4, 1, 1)
    row(385, 5, 1, 3)
    return svg(o)


def diamond(cx, cy, hw, hh, st: St):
    return [poly([(cx, cy - hh), (cx + hw, cy), (cx, cy + hh), (cx - hw, cy)], fill=st.soft, stroke=st.line, sw=SW)]


def lineage_narrow() -> str:
    """값이 달라 보일 때: 같은 대상 · 시각인가 → 원천인가 계산인가 → 확인할 곳."""
    o = [rect(15, 185, 175, 150, 12, fill=LIGHT)]
    o += diamond(375, 260, 125, 95, NORM) + diamond(700, 260, 125, 95, NORM)
    o += [arrow([(190, 260), (246, 260)], NAVY), arrow([(500, 260), (571, 260)], BLUE, sw=5),
          arrow([(375, 355), (375, 405)], NAVY),
          path("M 700,165 L 700,85 L 840,85", stroke=BLUE, sw=5), arrow([(840, 85), (900, 85)], BLUE, sw=5),
          arrow([(825, 260), (900, 260)], BLUE, sw=5)]
    o += [rect(250, 405, 250, 100, 12, fill=WHITE), rect(900, 20, 285, 130, 12, fill=PALE, stroke=BLUE),
          rect(900, 195, 285, 130, 12, fill=PALE, stroke=BLUE),
          rect(900, 375, 285, 130, 12, fill=WHITE, stroke="none", sw=0)]
    o += dash_rect(900, 375, 285, 130, NAVY, SW, 9, 8) + dash_line(1042, 325, 1042, 375, NAVY, 3, 6, 7)
    return svg(o)


def kinds_columns() -> str:
    """쿨러 사건의 이름을 네 질문의 칸에 놓는다."""
    xs = (150, 450, 750, 1050)
    o: list[str] = []
    for x in xs:
        o.append(rect(x - 138, 8, 276, 504, 14, fill=LIGHT, stroke="none", sw=0))
    y1, y2 = 185, 370
    o += g(xs[0], y1, 0.9, radiator(-44, -34, 88, 68, ON, fins=8, r=7)) + gauge(xs[0], y2, ON, r=32, hot=True)
    o += thermo(xs[1] - 14, y1 + 34, ON, s=0.72, level=0.7) + [arrow([(xs[1] + 22, y1 + 26), (xs[1] + 22, y1 - 34)], BLUE, sw=4, size=11)]
    o += g(xs[1] - 14, y2, 0.8, radiator(-44, -34, 88, 68, NORM, fins=8, r=7)) + [arrow([(xs[1] + 42, y2 - 30), (xs[1] + 42, y2 + 30)], BLUE, sw=4, size=11)]
    o += g(xs[2], y1, 0.9, dusty_cooler(0, 0, ON)) + fan(xs[2], y2, 40, NORM, rot=35)
    for sgn in (-1, 1):
        for rr in (50, 60):
            a0, a1 = math.radians(-28), math.radians(28)
            o.append(path(f"M {xs[2] + sgn * rr * math.cos(a0):.1f},{y2 + rr * math.sin(a0):.1f} A {rr} {rr} 0 0 {1 if sgn > 0 else 0} "
                          f"{xs[2] + sgn * rr * math.cos(a1):.1f},{y2 + rr * math.sin(a1):.1f}", stroke=NAVY, sw=3))
    o += fan(xs[3], y1, 44, ON, rot=20, hot=True)
    o += g(xs[3], y2, 0.9, radiator(-44, -34, 88, 68, ON, fins=8, r=7))
    for dx, dy in ((-52, -30), (56, -24), (-56, 24), (54, 30)):
        o.append(path(f"M {xs[3] + dx},{y2 + dy - 9} L {xs[3] + dx},{y2 + dy + 9} M {xs[3] + dx - 9},{y2 + dy} L {xs[3] + dx + 9},{y2 + dy}", stroke=BLUE, sw=3.5))
    return svg(o)


def property_scale() -> str:
    """왼쪽: 유온의 속성 항목. 오른쪽: 온도 눈금 위의 정상값 · 한계(설정)와 관측값."""
    tx = lambda t: 530 + (t - 40) * 640 / 30
    o = [circle(105, 255, 88, fill=PALE, sw=4)]
    o += thermo(105, 295, ON, s=0.95, level=0.6)
    for y in (105, 255, 405):
        o.append(line(190, 255 + (y - 255) * 0.32, 235, y, stroke=NAVY, sw=3.5))
        o.append(rect(235, y - 45, 225, 90, 10, fill=WHITE))
    y = 270
    o.append(rect(tx(40), y - 13, tx(70) - tx(40), 26, 13, fill=LIGHT))
    o.append(rect(tx(48), y - 13, tx(65) - tx(48), 26, 0, fill=PALE, stroke="none", sw=0))
    o.append(rect(tx(40), y - 13, tx(70) - tx(40), 26, 13))
    for t in (48, 65):
        o.append(line(tx(t), y - 44, tx(t), y + 13, stroke=NAVY, sw=5))
    o.append(circle(tx(55.71), y, 16, fill=SKY, sw=4))
    o += g(tx(55.71), 420, 0.8, cylinder_db(0, 0, ON))
    o.append(arrow([(tx(55.71), 372), (tx(55.71), y + 22)], BLUE, sw=4.5))
    o += dash_line(tx(55.71) + 24, y - 24, tx(65) - 8, y - 24, BLUE, 3.5, 7, 7)
    return svg(o)


def relation_named() -> str:
    """이름 없는 선(왼쪽)과 이름 붙은 관계(오른쪽)."""
    o: list[str] = []
    for ox, named in ((0, False), (610, True)):
        o.append(rect(ox + 15, 8, 560, 504, 14, fill=PALE if named else LIGHT, stroke="none", sw=0))
        for ty in (120, 400):
            if named:
                o.append(arrow([(ox + 200, 260 + (ty - 260) * 0.25), (ox + 400, ty + (260 - ty) * 0.12)], BLUE, sw=5, size=15))
            else:
                o.append(line(ox + 200, 260 + (ty - 260) * 0.25, ox + 400, ty + (260 - ty) * 0.12, stroke=NAVY, sw=4))
        o.append(circle(ox + 130, 260, 72, fill=SKY, sw=4))
        o += g(ox + 130, 228, 0.5, broken_cooler(0, 0, NORM))
        o.append(circle(ox + 465, 120, 58, fill=WHITE, sw=4))
        o += fan(ox + 465, 120, 40, ON, rot=20, hot=True)
        o.append(circle(ox + 465, 400, 58, fill=WHITE, sw=4))
        o += g(ox + 465, 400, 0.72, radiator(-44, -34, 88, 68, ON, fins=8, r=7))
    return svg(o)


def fill_or_redefine() -> str:
    """지식을 더 채운다(왼쪽) · 공통 정의를 바꾼다(오른쪽)."""
    o: list[str] = []
    for ox, redefine in ((0, False), (610, True)):
        o.append(rect(ox + 15, 8, 560, 504, 14, fill=LIGHT, stroke="none", sw=0))
        o.append(rect(ox + 45, 28, 500, 96, 12, fill=PALE if redefine else WHITE, stroke=BLUE if redefine else NAVY, sw=5 if redefine else 3))
        o.append(arrow([(ox + 295, 124), (ox + 295, 168)], NAVY, sw=3.5, size=11))
        tx, ty = ox + 460, 340
        for i, yy in enumerate((215, 340, 465)):
            new = (not redefine) and i == 1
            start = (ox + 212, yy + (ty - yy) * 0.04)
            end = (tx - 72, ty + (yy - ty) * 0.2)
            if redefine:
                o += dash_line(start[0], start[1], end[0], end[1], BLUE, 4, 9, 8)
            else:
                o.append(arrow([start, end], BLUE if new else NAVY, sw=5.5 if new else 3.5, size=15 if new else 13))
            o.append(circle(ox + 195, yy, 14, fill=SKY if new else WHITE, stroke=BLUE if (new or redefine) else NAVY, sw=4))
        o.append(circle(tx, ty, 66, fill=SKY, sw=4))
    return svg(o)


def stored_not_true() -> str:
    """같은 잘못된 연결이 저장 · 그림에 그대로 남는다. 오른쪽은 따로 확인할 두 가지."""
    o: list[str] = []

    def pair(ax, ay, bx, by, r):
        d_ = math.hypot(bx - ax, by - ay)
        ux, uy = (bx - ax) / d_, (by - ay) / d_
        return [arrow([(ax + ux * (r + 4), ay + uy * (r + 4)), (bx - ux * (r + 8), by - uy * (r + 8))], BLUE, sw=4, size=12),
                circle(ax, ay, r, fill=SKY, sw=3.5), circle(bx, by, r, fill=WHITE, sw=3.5)]

    o += pair(70, 260, 265, 260, 58)
    o += [path("M 330,235 L 390,130", stroke=NAVY, sw=3.5), arrow([(390, 130), (440, 130)], NAVY, sw=3.5),
          path("M 330,285 L 390,390", stroke=NAVY, sw=3.5), arrow([(390, 390), (440, 390)], NAVY, sw=3.5)]
    o += g(510, 130, 0.95, graph_db(0, 0, ON)) + monitor(510, 390, ON, "graph")
    o += [arrow([(585, 130), (640, 130)], NAVY, sw=3.5), arrow([(585, 390), (640, 390)], NAVY, sw=3.5)]
    o += pair(695, 130, 880, 130, 58) + pair(695, 335, 880, 445, 58)
    o += [rect(965, 40, 225, 440, 14, fill=PALE, stroke=BLUE, sw=3)]
    for yy in (145, 345):
        o.append(circle(1077, yy, 26, fill=WHITE, stroke=NAVY, sw=3))
        o.append(path(f"M {1064},{yy} L {1074},{yy + 10} L {1091},{yy - 11}", stroke=BLUE, sw=4))
    return svg(o)


def evidence_outcomes() -> str:
    """위: 후보 · 증거 · 대조의 세 상태. 아래: 대조에서 갈라지는 세 결과."""
    o: list[str] = []
    for x in (30, 440, 850):
        o.append(rect(x, 14, 320, 96, 12, fill=WHITE))
    o += [arrow([(350, 62), (440, 62)], NAVY), arrow([(760, 62), (850, 62)], NAVY)]
    o += [line(1010, 110, 1010, 150, stroke=NAVY, sw=4), line(190, 150, 1010, 150, stroke=NAVY, sw=4)]
    for x in (190, 600, 1010):
        o.append(arrow([(x, 150), (x, 196)], NAVY, sw=4))
    o += [rect(30, 196, 320, 256, 14, fill=PALE, stroke=BLUE, sw=4), rect(440, 196, 320, 256, 14, fill=LIGHT, stroke="none", sw=0),
          rect(850, 196, 320, 256, 14, fill=WHITE, stroke="none", sw=0)]
    o += dash_rect(850, 196, 320, 256, NAVY, SW, 9, 8)
    o += g(190, 262, 0.85, dusty_cooler(0, 0, ON)) + fan(600, 262, 40, NORM, rot=35)
    o += gauge(1010, 262, NORM, r=34, ang=-90)
    o.append(line(976, 296, 1044, 228, stroke=BLUE, sw=5))
    return svg(o)


def person_icon(cx, cy, st: St):
    return [circle(cx, cy - 22, 18, fill=st.fill, stroke=st.line),
            path(f"M {cx - 34},{cy + 34} Q {cx - 34},{cy + 2} {cx},{cy + 2} Q {cx + 34},{cy + 2} {cx + 34},{cy + 34} Z", fill=st.fill, stroke=st.line)]


def bubble(x, y, w, h, side, stroke, fill, dashed=False):
    """말풍선 하나. side: 'L'이면 왼쪽(나), 'R'이면 오른쪽(AI)으로 꼬리를 낸다. 점선은 dash_line으로 긋는다(PyMuPDF가 dasharray를 그리지 않는다)."""
    r, ty = 22, y + h / 2
    tx = x if side == "L" else x + w
    tip = tx - 24 if side == "L" else tx + 24
    o = [path(f"M {tx},{ty - 14} L {tip},{ty} L {tx},{ty + 14} Z", stroke="none", fill=fill, sw=0),
         rect(x, y, w, h, r, fill=fill, stroke="none", sw=0)]
    if not dashed:
        o.append(rect(x, y, w, h, r, fill="none", stroke=stroke, sw=3))
        o.append(line(tx, ty - 12, tx, ty + 12, stroke=fill, sw=6))
        o.append(path(f"M {tx},{ty - 14} L {tip},{ty} L {tx},{ty + 14}", stroke=stroke, sw=3))
        return o
    for a, b in (((x + r, y), (x + w - r, y)), ((x + r, y + h), (x + w - r, y + h)),
                 ((x + w, y + r), (x + w, y + h - r)) if side == "L" else ((x, y + r), (x, ty - 16)),
                 ((x, y + r), (x, ty - 16)) if side == "L" else ((x + w, y + r), (x + w, y + h - r)),
                 ((x, ty + 16), (x, y + h - r)) if side == "L" else ((x + w, ty + 16), (x + w, y + h - r))):
        o += dash_line(a[0], a[1], b[0], b[1], stroke, 3, 10, 9)
    for cx_, cy_, a0 in ((x + r, y + r, 180), (x + w - r, y + r, 270), (x + w - r, y + h - r, 0), (x + r, y + h - r, 90)):
        import math as _m
        p0 = (cx_ + r * _m.cos(_m.radians(a0)), cy_ + r * _m.sin(_m.radians(a0)))
        p1 = (cx_ + r * _m.cos(_m.radians(a0 + 90)), cy_ + r * _m.sin(_m.radians(a0 + 90)))
        o.append(path(f"M {p0[0]:.1f},{p0[1]:.1f} A {r},{r} 0 0 1 {p1[0]:.1f},{p1[1]:.1f}", stroke=stroke, sw=3))
    o += dash_line(tx, ty - 14, tip, ty, stroke, 3, 8, 7) + dash_line(tip, ty, tx, ty + 14, stroke, 3, 8, 7)
    return o


def chat_teacher() -> str:
    """AI를 선생님으로 두고 주고받는 대화. 흐린 첫 말(점선) → 교정 → 모르는 말을 쉽게 파고드는 두 말(안쪽으로 들임) → 또렷해진 내 설명(강조).
    글은 덱 MD 라벨로 얹는다."""
    o: list[str] = []
    h, step = 86, 104
    # (줄, 쪽, 선, 바탕, 점선, 들임)
    rows = [(0, "L", GREY, WHITE, True, 0), (1, "R", NAVY, LIGHT, False, 0), (2, "L", NAVY, WHITE, False, 70),
            (3, "R", NAVY, LIGHT, False, 70), (4, "L", SKY, PALE, False, 0)]
    for i, side, stroke, fill, dashed, ind in rows:
        y = 14 + i * step
        if side == "L":
            o += person_icon(70 + ind, y + h / 2, NORM if dashed else ON) + bubble(150 + ind, y, 690 - ind, h, "L", stroke, fill, dashed)
        else:
            o += agent_icon(1130 - ind, y + h / 2 + 2, ON) + bubble(360, y, 690 - ind, h, "R", stroke, fill, dashed)
    return svg(o)


def retention_curves() -> str:
    """시간이 지나며 남는 이해 — 외운 정의(회색, 빨리 내려감)와 내 말로 설명한 것(하늘색, 천천히 내려감). 숫자 · 눈금 없는 개념 그림."""
    ox, oy, xr, yt = 130, 470, 1110, 40
    o = [arrow([(ox, oy), (xr, oy)], NAVY, sw=3.5, size=14), arrow([(ox, oy), (ox, yt)], NAVY, sw=3.5, size=14)]
    o.append(path(f"M {ox + 10},90 C {ox + 140},330 {ox + 330},410 {xr - 40},430", stroke=GREY, sw=7))
    o.append(path(f"M {ox + 10},90 C {ox + 260},130 {ox + 560},165 {xr - 40},185", stroke=SKY, sw=9))
    o.append(circle(ox + 10, 90, 9, fill=NAVY, stroke=NAVY, sw=2))
    return svg(o)


# ───────────────────────── 02편 층 그림(스캔 고리 · 연결 · 이벤트 로그 · 처리 · 시계열) ─────────────────────────

def _arc(cx, cy, r, a0, a1, color=BLUE, sw=7, size=18):
    """시계 방향 원호와 끝 화살촉. 각도는 SVG 좌표(아래가 +)의 도."""
    p0 = (cx + r * math.cos(math.radians(a0)), cy + r * math.sin(math.radians(a0)))
    p1 = (cx + r * math.cos(math.radians(a1)), cy + r * math.sin(math.radians(a1)))
    big = 1 if (a1 - a0) % 360 > 180 else 0
    tang = math.radians(a1 + 90)
    return [path(f"M {p0[0]:.1f},{p0[1]:.1f} A {r},{r} 0 {big} 1 {p1[0]:.1f},{p1[1]:.1f}", stroke=color, sw=sw),
            head(p1[0] + 4 * math.cos(tang), p1[1] + 4 * math.sin(tang), tang, color, size)]


def octagon(cx, cy, r, st: St):
    pts = [(cx + r * math.cos(math.radians(22.5 + 45 * i)), cy + r * math.sin(math.radians(22.5 + 45 * i))) for i in range(8)]
    return [poly(pts, fill=st.accent, stroke=st.line, sw=SW), line(cx - r * 0.5, cy, cx + r * 0.5, cy, stroke=WHITE, sw=7)]


def plc_scan_loop() -> str:
    """센서 → PLC를 감싼 읽기 · 판단 · 지시의 고리 → 구동기(팬). 아래 틈에 고리를 끊는 인터록 정지 표시."""
    cx, cy, r = 600, 250, 160
    o = _arc(cx, cy, r, 192, 348) + _arc(cx, cy, r, 12, 74) + _arc(cx, cy, r, 106, 168)
    o += plc(cx, cy, ON)
    o += thermo(200, 335, ON)
    o.append(arrow([(250, 255), (418, 255)], NAVY, sw=4.5))
    o.append(arrow([(782, 255), (918, 255)], NAVY, sw=4.5))
    o += fan(1000, 255, 62, ON)
    o += octagon(cx, cy + r, 30, ON)
    return svg(o)


def connect_p2p_broker() -> str:
    """왼쪽: 보내는 쪽 셋과 받는 쪽 셋을 모두 직접 이은 얽힌 선. 오른쪽: 가운데 브로커 하나로 모이는 선."""
    ys = (150, 280, 410)
    o = dash_line(600, 70, 600, 500, GREY, 3, 10, 9)
    for ya in ys:
        for yb in ys:
            o.append(line(150, ya, 440, yb, stroke=NAVY, sw=2.5))
    bx, by = 905, 280
    for y in ys:
        o.append(line(760, y, bx - 42, by, stroke=BLUE, sw=3.5))
        o.append(line(bx + 42, by, 1050, y, stroke=BLUE, sw=3.5))
    for y in ys:
        o += g(115, y, 0.55, plc(0, 0, NORM)) + g(475, y, 0.55, monitor(0, 0, NORM, "trend"))
        o += g(725, y, 0.55, plc(0, 0, NORM)) + g(1085, y, 0.55, monitor(0, 0, NORM, "trend"))
    o += g(bx, by, 0.8, server(0, 0, ON))
    return svg(o)


def event_log_band() -> str:
    """뒤에 덧붙여 쌓이는 기록 띠(오른쪽 끝 점선 칸이 새 기록), 오른쪽 생산자, 아래 소비자 셋이 각자 읽는다."""
    x0, cw, ch, y = 230, 62, 74, 190
    n = 11
    o: list[str] = []
    for i in range(n):
        if i == n - 1:
            o += dash_rect(x0 + i * cw, y - ch / 2, cw, ch, NAVY, 3, 9, 7)
        else:
            o.append(rect(x0 + i * cw, y - ch / 2, cw, ch, 4, fill=PALE if i >= n - 3 else LIGHT, stroke=NAVY, sw=3))
    o.append(arrow([(1015, y), (x0 + n * cw + 8, y)], BLUE, sw=5, size=16))
    o += g(1085, y, 0.85, server(0, 0, ON))
    for cxc, part, k in ((360, bell(0, 0, ON, 1.9), 1.0), (600, cylinder_db(0, 0, ON), 0.8), (840, monitor(0, 0, ON, "trend"), 0.8)):
        o.append(arrow([(cxc, y + ch / 2 + 10), (cxc, 345)], NAVY, sw=4))
        o += g(cxc, 410, k, part)
    return svg(o)


def batch_vs_stream() -> str:
    """왼쪽: 통에 모았다가 정한 때(시계) 한꺼번에 처리 → 늦은 알림. 오른쪽: 흘러오는 기록을 관문에 바로 견주어 바로 알림."""
    o = dash_line(600, 40, 600, 500, GREY, 3, 10, 9)
    o.append(rect(70, 210, 300, 200, 10, fill=WHITE, stroke=NAVY))
    for r_ in range(4):
        for c in range(7):
            o.append(rect(88 + c * 39, 230 + r_ * 44, 30, 32, 4, fill=LIGHT, stroke=NAVY, sw=2.5))
    o += [circle(220, 120, 40, fill=WHITE, stroke=NAVY), line(220, 120, 220, 92, stroke=NAVY, sw=4), line(220, 120, 242, 132, stroke=NAVY, sw=4)]
    o.append(arrow([(380, 310), (468, 310)], NAVY, sw=4.5))
    o += bell(515, 305, NORM, 1.6)
    ys = 310
    for x in (650, 715, 780, 845):
        o.append(rect(x, ys - 18, 36, 36, 4, fill=LIGHT, stroke=NAVY, sw=2.5))
    o.append(rect(905, ys - 70, 26, 140, 6, fill=PALE, stroke=NAVY))
    for dy in (-40, 0, 40):
        o.append(line(905, ys + dy, 931, ys + dy, stroke=NAVY, sw=2.5))
    o.append(rect(968, ys - 18, 36, 36, 4, fill=SKY, stroke=NAVY, sw=2.5))
    o.append(rect(1040, ys - 18, 36, 36, 4, fill=LIGHT, stroke=NAVY, sw=2.5))
    o.append(arrow([(640, ys + 52), (1120, ys + 52)], NAVY, sw=4))
    o.append(arrow([(986, ys - 26), (986, 205)], BLUE, sw=4.5))
    o += bell(986, 160, ON, 1.6)
    return svg(o)


def series_window() -> str:
    """시각 축 위에 쌓인 세 태그의 값 줄과, 시각으로 골라 찾는 구간(하늘색 띠)."""
    o = [rect(650, 70, 230, 370, 10, fill=PALE, stroke="none"),
         arrow([(170, 455), (1130, 455)], NAVY, sw=4, size=15)]
    base = (150, 260, 360)
    xs = [200 + i * 60 for i in range(16)]
    jit = (0, -10, 6, -4, 10, -8, 4, 12, -6, 2, -12, 8, -2, 6, -10, 4)
    for k, b in enumerate(base):
        pts = [(x, b + jit[(i + k * 5) % 16]) for i, x in enumerate(xs)]
        o.append(path("M " + " L ".join(f"{x},{y}" for x, y in pts), stroke=GREY, sw=2.5))
        for x, y in pts:
            inside = 650 <= x <= 880
            o.append(circle(x, y, 8, fill=SKY if inside else WHITE, stroke=NAVY, sw=2.5))
    return svg(o)



def kg_map_focus(side: str) -> str:
    """지식 그래프 지도와 같은 자리 · 같은 선. side 쪽 노드와 그 쪽 관계만 밝히고 나머지는 회색으로 둔다.
    'equip': 설비 · 구성 요소 · 센서와 증상의 관측, 고장이 생긴 곳. 'diag': 증상 · 고장 유형 · 원인 · 조치 방법 · 매뉴얼 절."""
    nodes = {"equip": {"asset", "comp", "sen", "sym", "fm"}, "diag": {"sym", "fm", "cause", "skill", "doc"}}[side]
    edges = {"equip": {("asset", "comp"), ("comp", "sen"), ("sym", "sen"), ("fm", "comp")},
             "diag": {("sym", "fm"), ("cause", "fm"), ("fm", "skill"), ("skill", "doc")}}[side]
    o: list[str] = []
    for a, b in KG_EDGES:
        (ax, ay, ar), (bx, by, br) = KG_NODES[a], KG_NODES[b]
        d_ = math.hypot(bx - ax, by - ay)
        ux, uy = (bx - ax) / d_, (by - ay) / d_
        hot = (a, b) in edges
        o.append(arrow([(ax + ux * (ar + 5), ay + uy * (ar + 5)), (bx - ux * (br + 9), by - uy * (br + 9))],
                       BLUE if hot else GREY, sw=4 if hot else 3, size=13))
    for k, (x, y, r) in KG_NODES.items():
        if k not in nodes:
            fill, stroke, sw = LIGHT, GREY, 3
        elif k == "fm":
            fill, stroke, sw = SKY, NAVY, 4
        else:
            fill, stroke, sw = PALE, BLUE, 3
        o.append(circle(x, y, r, fill=fill, stroke=stroke, sw=sw))
    return svg(o, 1213, 540)



def words_apart() -> str:
    """세 사람이 같은 일을 다른 말로 한다(말풍선) → 컴퓨터에게는 서로 이어지지 않은 세 말(따로 놓인 칸, 끊긴 표시)."""
    o: list[str] = []
    ys = (95, 260, 425)
    for y in ys:
        o += person_icon(80, y, NORM) + bubble(150, y - 39, 380, 78, "L", NAVY, WHITE)
        o += dash_line(552, y, 712, y, GREY, 3, 9, 8)
        o.append(rect(720, y - 30, 150, 60, 8, fill=LIGHT, stroke=NAVY, sw=3))
        o.append(line(875, y, 1030, 260, stroke=GREY, sw=2.5))
    for ym in ((95 + 260) / 2, (260 + 425) / 2):
        o.append(line(781, ym - 14, 809, ym + 14, stroke=BLUE, sw=4))
        o.append(line(809, ym - 14, 781, ym + 14, stroke=BLUE, sw=4))
    o += agent_icon(1095, 268, ON)
    return svg(o)


def promised_words() -> str:
    """흩어진 말(점선 칸 셋) → 약속된 단어장(하늘 바탕) 안에서 이름 · 종류가 정해진 두 대상과 이름 붙은 관계."""
    o: list[str] = []
    for y in (70, 200, 330):
        o += dash_rect(40, y, 290, 70, GREY, 3, 9, 8)
    o.append(arrow([(352, 240), (478, 240)], BLUE, sw=6, size=18))
    o.append(rect(500, 40, 670, 362, 16, fill=PALE, stroke="none", sw=0))
    o.append(circle(640, 225, 72, fill=WHITE, stroke=BLUE, sw=4))
    o.append(circle(1030, 225, 82, fill=SKY, stroke=NAVY, sw=4))
    o.append(arrow([(717, 225), (941, 225)], NAVY, sw=5, size=16))
    return svg(o)



# ───────────────────────── 02편 다듬기: MQTT(OT 안) · 통로와 창고 · 원인 갈래 · 에이전트 다섯 걸음 · 사건 한 건의 단계 ─────────────────────────

def lineage_mqtt_ot() -> str:
    """MQTT 발행 · 구독을 OT 안에서만: 설비 → 엣지(발행자) → 브로커 → 구독자 둘(운전 화면 · 다른 OT 프로그램). 바깥으로 내보내는 일은 그리지 않는다."""
    w, h, r1, r2 = 1100, 500, 190, 345
    x = dict(equip=110, plc=350, env=530, emqx=710, sub=980)
    o: list[str] = [rect(12, 8, 1076, 484, 14, fill=LIGHT, stroke="none", sw=0)]
    o += [arrow([(161, r1), (291, r1)], BLUE, sw=5, size=14), arrow([(407, r1), (658, r1)], BLUE, sw=5, size=14),
          arrow([(760, r1), (928, r1)], BLUE, sw=5, size=14), arrow([(x["emqx"], r1 + 54), (x["emqx"], r2 - 54)], BLUE, sw=5, size=14)]
    o += equip_mini(x["equip"], r1, ON) + plc(x["plc"], r1, ON) + envelope(x["env"], r1, ON) + server(x["emqx"], r1, ON)
    o += monitor(x["emqx"], r2, ON, "hmi") + monitor(x["sub"], r1, ON, "trend")
    return svg(o, w, h)


def flow_vs_store() -> str:
    """위: 기록이 차례로 지나가는 컨베이어(이벤트 로그). 그 끝에서 아래 창고 선반(시계열 저장소)으로 옮겨 쌓이고, 선반은 시각 축을 따라 칸이 놓여 구간(하늘색 두 열)을 골라 꺼낸다."""
    o: list[str] = []
    o.append(rect(60, 125, 600, 50, 25, fill=LIGHT, stroke=NAVY))
    for cx in (85, 635):
        o.append(circle(cx, 150, 18, fill=WHITE, stroke=NAVY, sw=3))
    for i, bx in enumerate((150, 250, 350, 450, 550)):
        o.append(rect(bx - 26, 72, 52, 52, 5, fill=PALE if i == 4 else WHITE, stroke=NAVY, sw=3))
    o.append(arrow([(130, 40), (600, 40)], NAVY, sw=4, size=14))
    o.append(arrow([(680, 150), (860, 150), (860, 205)], BLUE, sw=5, size=16))
    gx, gy, cw, ch = 760, 220, 95, 52
    for r_ in range(4):
        for c in range(4):
            hot = c in (1, 2)
            o.append(rect(gx + c * cw, gy + r_ * ch, cw - 10, ch - 10, 4, fill=SKY if hot else WHITE, stroke=NAVY, sw=2.5))
    o.append(arrow([(gx - 5, 452), (gx + 4 * cw + 20, 452)], NAVY, sw=4, size=14))
    return svg(o)


def cause_branches() -> str:
    """경보 → 고장 유형 → 원인 후보 두 갈래 → 갈래마다 확인할 값 → 흔적 없는 아래 갈래는 내려놓고(회색 · X) 위 갈래만 조치로."""
    o: list[str] = []
    yb, yu, yl = 260, 130, 390
    o.append(arrow([(150, yb), (232, yb)], NAVY, sw=4.5))
    o.append(arrow([(355, yb - 25), (500, yu + 12)], BLUE, sw=4.5))
    o.append(arrow([(355, yb + 25), (500, yl - 12)], GREY, sw=4))
    o.append(arrow([(612, yu), (748, yu)], BLUE, sw=4.5))
    o.append(arrow([(612, yl), (748, yl)], GREY, sw=4))
    o.append(arrow([(852, yu), (998, yu)], BLUE, sw=4.5))
    o += bell(95, yb, ON, 2.0)
    o.append(circle(295, yb, 62, fill=SKY, stroke=NAVY, sw=4))
    o += [line(270, yb - 22, 320, yb - 22, stroke=NAVY, sw=4), line(270, yb, 320, yb, stroke=NAVY, sw=4), line(270, yb + 22, 305, yb + 22, stroke=NAVY, sw=4)]
    o.append(circle(556, yu, 52, fill=PALE, stroke=BLUE, sw=4))
    o += dust(556, yu, ON, 0.85)
    o.append(circle(556, yl, 52, fill=LIGHT, stroke=GREY, sw=3))
    o += fan(556, yl, 30, OFF)
    o.append(circle(800, yu, 46, fill=WHITE, stroke=BLUE, sw=4))
    o += gauge(800, yu, ON, r=26, hot=True)
    o.append(circle(800, yl, 46, fill=LIGHT, stroke=GREY, sw=3))
    o += gauge(800, yl, OFF, r=26)
    o += [line(895, yl - 26, 947, yl + 26, stroke=BLUE, sw=6), line(947, yl - 26, 895, yl + 26, stroke=BLUE, sw=6)]
    o.append(circle(1052, yu, 52, fill=PALE, stroke=BLUE, sw=4))
    o += radiator(1022, yu - 26, 60, 52, ON, fins=7, r=6)
    return svg(o)


def agent_five_steps() -> str:
    """가운데 AI 에이전트를 두고 위로 둥글게 놓인 다섯 걸음(받기 · 조회 · 진단 · 추천안 · 남기기)을 차례로 잇는다."""
    pts = [(170, 360), (340, 160), (600, 90), (860, 160), (1030, 360)]
    o: list[str] = []
    for (ax, ay) in pts:
        o.append(line(600, 340, ax, ay, stroke=GREY, sw=2.5))
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        d_ = math.hypot(bx - ax, by - ay)
        ux, uy = (bx - ax) / d_, (by - ay) / d_
        o.append(arrow([(ax + ux * 58, ay + uy * 58), (bx - ux * 62, by - uy * 62)], BLUE, sw=4.5, size=15))
    for i, (cx, cy) in enumerate(pts):
        o.append(circle(cx, cy, 52, fill=SKY if i == 3 else WHITE, stroke=NAVY if i == 3 else BLUE, sw=4))
    o += bell(170, 356, ON, 1.3)
    o += g(340, 160, 0.55, cylinder_db(0, 0, ON))
    o += gauge(600, 90, ON, r=28, hot=True)
    o += g(860, 160, 0.4, note_doc(0, 0, NORM))
    o += g(1030, 360, 0.5, book_icon(0, 0, ON))
    o.append(circle(600, 340, 74, fill=PALE, stroke="none", sw=0))
    o += g(600, 345, 1.15, agent_icon(0, 0, ON))
    return svg(o)


def case_track() -> str:
    """사건 한 건(왼쪽 서류철)이 다섯 단계 정류장을 차례로 지나고, 셋째(승인)에서 사람을 기다리며, 단계마다 아래에 기록이 한 장씩 남는다."""
    xs = (240, 435, 630, 825, 1020)
    y = 230
    o: list[str] = [line(150, y, 1020, y, stroke=GREY, sw=6)]
    o += [rect(40, y - 44, 76, 88, 8, fill=PALE, stroke=NAVY), line(56, y - 18, 100, y - 18, stroke=NAVY, sw=3), line(56, y + 4, 100, y + 4, stroke=NAVY, sw=3)]
    o.append(arrow([(122, y), (186, y)], BLUE, sw=5, size=15))
    for i, x in enumerate(xs):
        hot = i == 2
        o.append(circle(x, y, 46, fill=SKY if hot else WHITE, stroke=NAVY, sw=4))
        o += dash_line(x, y + 50, x, 352, GREY, 3, 8, 7)
        o += g(x, 400, 0.42, note_doc(0, 0, NORM))
    for a, b in zip(xs, xs[1:]):
        o.append(arrow([(a + 50, y), (b - 52, y)], NAVY, sw=4, size=13))
    o += g(xs[2], y + 6, 0.62, person_icon(0, 0, ON))
    return svg(o)



# ───────────────────────── 03편 재편: 이름이 갈린 기록 · 한 대상으로 모이는 이름 · 틀을 두고 더하는 원인 · 따라가기 입구 ─────────────────────────

def records_apart() -> str:
    """정비 기록(위)과 설비 목록(아래)이 같은 부품을 다른 이름으로 적어, 컴퓨터에게는 이어지지 않은 두 칸(사이 X)으로 보인다."""
    o: list[str] = []
    for y in (140, 380):
        o += note_doc(130, y, NORM)
        o += dash_line(195, y, 708, y, GREY, 3, 9, 8)
        o.append(rect(720, y - 30, 170, 60, 8, fill=LIGHT, stroke=NAVY, sw=3))
        o.append(line(895, y, 1030, 265, stroke=GREY, sw=2.5))
    o += [line(788, 246, 822, 280, stroke=BLUE, sw=5), line(822, 246, 788, 280, stroke=BLUE, sw=5)]
    o += agent_icon(1095, 272, ON)
    return svg(o)


def aliases_merge() -> str:
    """다른 이름으로 적힌 기록 셋(왼쪽 칸)이 한 대상(가운데 원)으로 모이고, 그 대상의 이력이 한곳에 쌓인다(오른쪽 기록 묶음)."""
    o: list[str] = []
    ys = (95, 260, 425)
    for y in ys:
        o.append(rect(50, y - 32, 280, 64, 10, fill=WHITE, stroke=NAVY, sw=3))
        o.append(arrow([(340, y), (668, 260 + (y - 260) * 0.25)], BLUE, sw=4.5, size=15))
    o.append(circle(760, 260, 88, fill=SKY, stroke=NAVY, sw=4))
    o += g(760, 262, 0.95, radiator(-46, -32, 92, 64, ON, fins=8, r=8))
    o.append(arrow([(852, 260), (968, 260)], NAVY, sw=4.5, size=15))
    for i, dx in enumerate((0, 16, 32)):
        o += g(1040 + dx, 250 + dx, 0.6, note_doc(0, 0, ON if i == 2 else NORM))
    return svg(o)


def add_cause() -> str:
    """정의(위 칸)는 그대로 두고, 같은 고장 유형에 원인 하나를 더 잇는다(맨 아래 하늘색 원과 굵은 파란 화살표)."""
    o: list[str] = [rect(560, 24, 520, 84, 12, fill=PALE, stroke=BLUE, sw=3)]
    fx, fy = 820, 300
    for i, y in enumerate((80, 200, 320, 440)):
        new = i == 3
        o.append(circle(300, y, 30, fill=SKY if new else WHITE, stroke=BLUE if new else NAVY, sw=4))
        d_ = math.hypot(fx - 300, fy - y)
        ux, uy = (fx - 300) / d_, (fy - y) / d_
        o.append(arrow([(300 + ux * 36, y + uy * 36), (fx - ux * 90, fy - uy * 90)], BLUE if new else NAVY, sw=6 if new else 3.5, size=16 if new else 13))
    o.append(circle(fx, fy, 80, fill=SKY, stroke=NAVY, sw=4))
    return svg(o)


def walk_entry() -> str:
    """따라가기 입구: 이상 패턴 → 증상 → 고장 유형만 진하게, 고장 유형에서 원인 쪽으로 나갈 길은 짧은 회색 점선으로만 남긴다."""
    o: list[str] = []
    for a, b in (("P", "S"), ("S", "F")):
        (ax, ay, ar), (bx, by, br) = WALK[a], WALK[b]
        d_ = math.hypot(bx - ax, by - ay)
        ux, uy = (bx - ax) / d_, (by - ay) / d_
        o.append(arrow([(ax + ux * (ar + 5), ay + uy * (ar + 5)), (bx - ux * (br + 9), by - uy * (br + 9))], BLUE, sw=4, size=13))
    fx, fy, fr = WALK["F"]
    for ty in (120, 260, 400):
        d_ = math.hypot(760 - fx, ty - fy)
        ux, uy = (760 - fx) / d_, (ty - fy) / d_
        o += dash_line(fx + ux * (fr + 10), fy + uy * (fr + 10), fx + ux * (fr + 150), fy + uy * (fr + 150), GREY, 4, 10, 9)
    for k in ("P", "S", "F"):
        x, y, r = WALK[k]
        o.append(circle(x, y, r, fill=SKY if k == "F" else PALE, stroke=NAVY if k == "F" else BLUE, sw=4 if k == "F" else 3))
    return svg(o, *WALK_WH)


# ───────────────────────── 03편 온톨로지 차례: 모양 · 문장으로 읽기 · 약속과 채움 · 네 가지 짚기 ─────────────────────────

def _edge_arrow(a, b, color=NAVY, sw=4.5, size=15, gap_a=5, gap_b=9):
    """원 a(x, y, r)의 테두리에서 원 b의 테두리까지 화살표. 화살촉은 b 쪽."""
    (ax, ay, ar), (bx, by, br) = a, b
    d_ = math.hypot(bx - ax, by - ay)
    ux, uy = (bx - ax) / d_, (by - ay) / d_
    return [arrow([(ax + ux * (ar + gap_a), ay + uy * (ar + gap_a)), (bx - ux * (br + gap_b), by - uy * (br + gap_b))], color, sw=sw, size=size)]


def _rise_icon(cx, cy, k=1.0):
    """증상: 온도계와 위 화살표."""
    return thermo(cx - 12 * k, cy + 24 * k, ON, s=0.62 * k, level=0.7) + [arrow([(cx + 18 * k, cy + 20 * k), (cx + 18 * k, cy - 26 * k)], BLUE, sw=4, size=11)]


def _shaky_fan(cx, cy, r, st: St):
    """상한 팬: 팬 둘레에 떨림 호 두 겹."""
    o = fan(cx, cy, r, st, rot=35)
    for sgn in (-1, 1):
        for rr in (r * 1.25, r * 1.5):
            a0, a1 = math.radians(-28), math.radians(28)
            o.append(path(f"M {cx + sgn * rr * math.cos(a0):.1f},{cy + rr * math.sin(a0):.1f} A {rr:.1f} {rr:.1f} 0 0 {1 if sgn > 0 else 0} "
                          f"{cx + sgn * rr * math.cos(a1):.1f},{cy + rr * math.sin(a1):.1f}", stroke=NAVY, sw=3))
    return o


def _tag(tx, ty, to, sw=3):
    """작은 둥근 꼬리표(연하늘 채움 · 남색 테두리)와 원 테두리 점 to까지의 짧은 끈."""
    return [line(tx, ty, to[0], to[1], stroke=NAVY, sw=sw),
            rect(tx - 34, ty - 17, 68, 34, 17, fill=PALE, stroke=NAVY, sw=sw), circle(tx - 18, ty, 4.5, fill=WHITE, stroke=NAVY, sw=2.5)]


def _onto(P, k=1.0, rings=False):
    """온톨로지의 모양: 증상 S · 고장 유형 F · 원인 C · 조치 방법 K의 원 넷과 이름 붙은 화살표 셋(S → F, C → F, F → K), 증상 원의 꼬리표.
    P는 이름마다 (x, y, r). rings면 「일으킨다」 화살표의 출발 · 도착에 작은 파란 고리를 둔다."""
    S, F, C, K, T = P["S"], P["F"], P["C"], P["K"], P["T"]
    o: list[str] = []
    o += _edge_arrow(S, F) + _edge_arrow(C, F) + _edge_arrow(F, K)
    sx, sy, sr = S
    d_ = math.hypot(T[0] - sx, T[1] - sy)
    o += _tag(T[0] + (sx - T[0]) / d_ * 30, T[1] + (sy - T[1]) / d_ * 14, (sx + (T[0] - sx) / d_ * sr, sy + (T[1] - sy) / d_ * sr))
    for key, (x, y, r) in (("S", S), ("C", C), ("K", K)):
        o.append(circle(x, y, r, fill=PALE, stroke=BLUE, sw=3.5))
    o.append(circle(*F, fill=SKY, stroke=NAVY, sw=4))
    o += _rise_icon(S[0], S[1], k)
    o += g(F[0], F[1], 0.62 * k * F[2] / 72, broken_cooler(0, 0, NORM))
    o += g(C[0], C[1], 0.62 * k * C[2] / 56, dusty_cooler(0, 0, NORM))
    o += fan(K[0], K[1], 0.62 * K[2], NORM, rot=20, hot=True)
    if rings:
        (cx, cy, cr), (fx, fy, fr) = C, F
        d_ = math.hypot(fx - cx, fy - cy)
        ux, uy = (fx - cx) / d_, (fy - cy) / d_
        for px_, py_ in ((cx + ux * (cr + 5), cy + uy * (cr + 5)), (fx - ux * (fr + 5), fy - uy * (fr + 5))):
            o.append(circle(round(px_, 1), round(py_, 1), 11, fill="none", stroke=BLUE, sw=4))
    return o


ONTO = {"S": (190, 270, 56), "F": (560, 180, 72), "C": (960, 85, 56), "K": (980, 305, 56), "T": (95, 180)}


def ontology_shape() -> str:
    """49장: 지식 그래프 지도와 같은 자리(증상 왼쪽 아래 · 원인 오른쪽 위 · 고장 유형 가운데 · 조치 방법 오른쪽 아래)의 원 넷과 화살표 셋,
    증상 원의 꼬리표. 아래 띠(비유의 닮은 점 · 다른 점 두 칸)는 라벨 자리로 비운다."""
    o: list[str] = [rect(20, 430, 570, 82, 12, fill=LIGHT, stroke="none", sw=0), rect(610, 430, 570, 82, 12, fill=LIGHT, stroke="none", sw=0)]
    o += _onto(ONTO)
    return svg(o)


def ontology_sentences() -> str:
    """50장: 원 셋을 한 줄로(증상 → 고장 유형 ← 원인), 고장 유형 아래로 조치 방법. 화살표마다 바로 아래에 흰 문장 칸(① 왼쪽 · ③ 가운데 · ② 오른쪽)을
    가는 회색 점선으로 잇고, 문장 칸 줄의 오른쪽 끝에서 컴퓨터(로봇 얼굴)로 화살표 하나."""
    S, F, C, K = (130, 130, 52), (470, 130, 62), (810, 130, 52), (470, 300, 50)
    o: list[str] = []
    o += _edge_arrow(S, F) + _edge_arrow(C, F) + _edge_arrow(F, K)
    for (x, y, r) in (S, C, K):
        o.append(circle(x, y, r, fill=PALE, stroke=BLUE, sw=3.5))
    o.append(circle(*F, fill=SKY, stroke=NAVY, sw=4))
    o += _rise_icon(S[0], S[1], 0.95)
    o += g(F[0], F[1], 0.53, broken_cooler(0, 0, NORM)) + g(C[0], C[1], 0.6, dusty_cooler(0, 0, NORM))
    o += fan(K[0], K[1], 31, NORM, rot=20, hot=True)
    boxes = ((15, 315), (330, 630), (645, 945))          # ① · ③ · ②
    for x0, x1 in boxes:
        o.append(rect(x0, 392, x1 - x0, 110, 16, fill=WHITE, stroke=NAVY, sw=3))
    o += dash_line(300, 142, 175, 386, GREY, 3, 8, 7)                                    # ① 가리킨다
    o += dash_line(482, 222, 555, 222, GREY, 3, 8, 7) + dash_line(555, 222, 555, 386, GREY, 3, 8, 7)   # ③ 완화된다
    o += dash_line(640, 142, 790, 386, GREY, 3, 8, 7)                                    # ② 일으킨다
    o.append(arrow([(958, 447), (1022, 447)], NAVY, sw=4.5, size=15))
    o += g(1105, 440, 1.25, agent_icon(0, 0, ON))
    return svg(['<g transform="translate(0 -10)">', *o, "</g>"])          # 본문 영역에서 내용을 살짝 위에 둔다


def promise_fill_layers() -> str:
    """56장: 위 띠(연하늘) = 약속 — 테두리만 있는 원 셋(원인 → 고장 유형 → 조치 방법). 아래 띠(흰) = 채움 — 같은 가로 자리의 원 셋과 아이콘
    (먼지 낀 쿨러 · 금이 간 쿨러 · 팬), 같은 화살표 둘. 아래 띠 원인 원 바로 아래에 원 하나(상한 팬)를 더 두고 고장 유형으로 잇는다.
    위아래 같은 자리의 원은 가는 회색 점선으로 잇는다. 띠 왼쪽 끝은 띠 이름 라벨 자리로 비운다."""
    xs, yt, yb = (400, 700, 1000), 125, 305
    o: list[str] = [rect(15, 10, 1170, 200, 16, fill=PALE, stroke="none", sw=0), rect(15, 226, 1170, 288, 16, fill=WHITE, stroke=GREY, sw=3)]
    for x in xs:
        o += dash_line(x, yt + 53, x, yb - 55, GREY, 3, 8, 7)
    o += [arrow([(xs[0] + 53, yt), (xs[1] - 57, yt)], NAVY, sw=4.5, size=15), arrow([(xs[1] + 53, yt), (xs[2] - 57, yt)], NAVY, sw=4.5, size=15)]
    o += [arrow([(xs[0] + 55, yb), (xs[1] - 59, yb)], NAVY, sw=4.5, size=15), arrow([(xs[1] + 55, yb), (xs[2] - 59, yb)], NAVY, sw=4.5, size=15)]
    for x in xs:
        o.append(circle(x, yt, 48, fill=WHITE, stroke=NAVY, sw=3.5))
    E = (400, 455, 40)
    o += _edge_arrow(E, (xs[1], yb, 50), NAVY, sw=4.5)
    for i, x in enumerate(xs):
        o.append(circle(x, yb, 50, fill=SKY if i == 1 else PALE, stroke=NAVY if i == 1 else BLUE, sw=4 if i == 1 else 3.5))
    o.append(circle(*E, fill=PALE, stroke=BLUE, sw=3.5))
    o += g(xs[0], yb, 0.58, dusty_cooler(0, 0, NORM)) + g(xs[1], yb, 0.58, broken_cooler(0, 0, NORM)) + fan(xs[2], yb, 31, NORM, rot=20, hot=True)
    o += _shaky_fan(E[0], E[1], 19, NORM)
    return svg(o)


ONTO4 = {"S": (135, 330, 50), "F": (370, 215, 62), "C": (610, 95, 50), "K": (615, 395, 50), "T": (55, 220)}


def ontology_four() -> str:
    """58장: 49장의 모양을 왼쪽 60 % 폭에 다시 그리고, 「일으킨다」 화살표의 출발 · 도착에 작은 파란 고리 둘. 짚는 번호(①~④)는 라벨로 얹는다.
    오른쪽 40 %는 네 칸 목록(연회색 칸 넷)을 라벨로 얹는 자리다."""
    o: list[str] = [rect(735, 12 + i * 126, 450, 114, 14, fill=LIGHT, stroke="none", sw=0) for i in range(4)]
    o += _onto(ONTO4, 0.95, rings=True)
    return svg(o)


def memo_two_readings() -> str:
    """51장: 위 가운데 메모 한 장을 왼쪽은 사람이, 오른쪽은 컴퓨터가 읽는다. 두 칸의 글(읽어 낸 것)은 라벨로 얹는다."""
    o: list[str] = []
    o += g(300, 78, 0.95, note_doc(0, 0, ON))
    o += [line(600, 150, 600, 172, stroke=NAVY, sw=3.5), line(300, 172, 900, 172, stroke=NAVY, sw=3.5)]
    o += [arrow([(300, 172), (300, 208)], NAVY, sw=3.5), arrow([(900, 172), (900, 208)], NAVY, sw=3.5)]
    o += [rect(40, 212, 520, 296, 14, fill=LIGHT, stroke="none", sw=0), rect(640, 212, 520, 296, 14, fill=LIGHT, stroke="none", sw=0)]
    o += g(125, 365, 1.45, person_icon(0, 0, ON)) + g(725, 362, 1.15, agent_icon(0, 0, ON))
    return svg(o)


def ontology_frame() -> str:
    """52장: 온톨로지의 틀 — 빈 원 둘(종류), 왼쪽 원의 꼬리표(속성), 이름 붙은 화살표(관계), 화살표 양 끝의 파란 고리(제약).
    실제 대상의 그림은 넣지 않는다. 오른쪽 40 %는 네 칸 목록(연회색 칸 넷)을 라벨로 얹는 자리다."""
    o: list[str] = [rect(735, 12 + i * 126, 450, 114, 14, fill=LIGHT, stroke="none", sw=0) for i in range(4)]
    C, F = (160, 300, 84), (530, 300, 94)
    o += _edge_arrow(C, F)
    o += _tag(78, 150, (C[0] - 84 * 0.55, C[1] - 84 * 0.835))
    o.append(circle(*C, fill=PALE, stroke=BLUE, sw=3.5))
    o.append(circle(*F, fill=SKY, stroke=NAVY, sw=4))
    for px_ in (C[0] + C[2] + 5, F[0] - F[2] - 5):
        o.append(circle(px_, 300, 11, fill="none", stroke=BLUE, sw=4))
    return svg(o)


def constraint_check() -> str:
    """57장: 위 띠 = 정해 둔 조건(빈 원 둘과 화살표, 양 끝 고리). 아래 두 칸 = 그 조건에 실제 연결을 대어 본 것 —
    왼쪽은 맞는 연결(확인 표시), 오른쪽은 거꾸로 이은 연결(X 표시)."""
    o: list[str] = [rect(15, 10, 1170, 180, 16, fill=PALE, stroke="none", sw=0)]
    A, B = (470, 104, 58), (810, 104, 58)
    o += _edge_arrow(A, B)
    o += [circle(*A, fill=WHITE, stroke=NAVY, sw=3.5), circle(*B, fill=WHITE, stroke=NAVY, sw=3.5)]
    for px_ in (A[0] + A[2] + 5, B[0] - B[2] - 5):
        o.append(circle(px_, 104, 11, fill="none", stroke=BLUE, sw=4))
    for ox, ok in ((15, True), (610, False)):
        o.append(rect(ox, 208, 575, 304, 14, fill=LIGHT, stroke="none", sw=0))
        a, b = (ox + 120, 318, 58), (ox + 390, 318, 58)
        o += _edge_arrow(a, b, BLUE)
        cause, fm = (a, b) if ok else (b, a)
        o.append(circle(*cause, fill=PALE, stroke=BLUE, sw=3.5))
        o.append(circle(*fm, fill=SKY, stroke=NAVY, sw=4))
        mx, my = ox + 505, 318
        o.append(circle(mx, my, 27, fill=WHITE, stroke=NAVY if ok else BLUE, sw=3))
        if ok:
            o.append(path(f"M {mx - 13},{my} L {mx - 3},{my + 10} L {mx + 14},{my - 11}", stroke=BLUE, sw=4.5))
        else:
            o += [line(mx - 11, my - 11, mx + 11, my + 11, stroke=BLUE, sw=4.5), line(mx + 11, my - 11, mx - 11, my + 11, stroke=BLUE, sw=4.5)]
    return svg(o)


def cause_to_action() -> str:
    """67장: 가려진 원인(왼쪽 위)에서 근본 조치(가운데 위)로, 고장 유형(왼쪽 아래)에서 완화 조치(가운데 아래)로, 두 조치에서 근거 문서(오른쪽)로.
    원인을 없애는 조치의 화살표와 완화 화살표는 파랑, 나머지는 남색."""
    C, F, R, M, D = (300, 125, 62), (300, 395, 70), (680, 125, 62), (680, 395, 62), (1050, 260, 68)
    o: list[str] = []
    o += _edge_arrow(C, F) + _edge_arrow(R, C, BLUE) + _edge_arrow(F, M, BLUE) + _edge_arrow(R, D) + _edge_arrow(M, D)
    o.append(circle(*C, fill=PALE, stroke=BLUE, sw=3.5))
    o.append(circle(*F, fill=SKY, stroke=NAVY, sw=4))
    o += [circle(*R, fill=WHITE, stroke=NAVY, sw=3.5), circle(*M, fill=WHITE, stroke=NAVY, sw=3.5), circle(*D, fill=LIGHT, stroke=GREY, sw=3.5)]
    o += g(C[0], C[1], 0.66, dusty_cooler(0, 0, NORM)) + g(F[0], F[1], 0.62, broken_cooler(0, 0, NORM))
    o += g(R[0], R[1], 0.72, radiator(-44, -34, 88, 68, ON, fins=8, r=7)) + fan(M[0], M[1], 38, ON, rot=20, hot=True)
    o += g(D[0], D[1], 0.72, book_icon(0, 0, NORM))
    return svg(o)


# ───────────────────────── 03편 새 차례: 메모 한 줄을 처음부터 끝까지 들고 간다 ─────────────────────────

def _node(P, kind, hot=False, grey=False, k=1.0):
    """실제 대상 하나를 그린 원과 그 안의 그림. P = (x, y, r). kind: rise · fm · pin · wash · fanmax · fanbad · amb · equip · cooler · sensor · doc."""
    x, y, r = P
    if grey:
        o = [circle(x, y, r, fill=LIGHT, stroke=GREY, sw=3)]
        st = OFF
    elif hot:
        o = [circle(x, y, r, fill=SKY, stroke=NAVY, sw=4)]
        st = NORM
    else:
        o = [circle(x, y, r, fill=PALE, stroke=BLUE, sw=3.5)]
        st = NORM
    s = r / 56 * k
    if kind == "rise":
        o += thermo(x - 12 * s, y + 24 * s, st, s=0.62 * s, level=0.7) + [arrow([(x + 18 * s, y + 20 * s), (x + 18 * s, y - 26 * s)], GREY if grey else BLUE, sw=4, size=11)]
    elif kind == "fm":
        o += g(x, y, 0.6 * s, broken_cooler(0, 0, st))
    elif kind == "pin":
        o += g(x, y, 0.6 * s, dusty_cooler(0, 0, st))
    elif kind == "wash":
        o += g(x, y, 0.66 * s, radiator(-44, -34, 88, 68, ON if not grey else OFF, fins=8, r=7))
    elif kind == "fanmax":
        o += fan(x, y, 0.62 * r, st, rot=20, hot=not grey)
    elif kind == "fanbad":
        o += _shaky_fan(x, y, 0.38 * r, st)
    elif kind == "amb":
        o += g(x, y, 0.6 * s, cabinet(0, 0, st))
    elif kind == "equip":
        o += g(x, y - 2 * s, 0.72 * s, equip_mini(0, 0, st))
    elif kind == "cooler":
        o += g(x, y, 0.66 * s, radiator(-44, -34, 88, 68, st, fins=8, r=7))
    elif kind == "sensor":
        o += gauge(x, y, st, r=0.52 * r, hot=not grey)
    elif kind == "doc":
        o += g(x, y, 0.6 * s, book_icon(0, 0, st))
    return o


def same_reading() -> str:
    """49장: 까닭이 달라도(위 먼지 낀 쿨러 · 아래 떨리는 팬) 온도계의 숫자는 똑같이 오른다. 오른쪽 세 칸은 값만으로는 알 수 없는 것."""
    o: list[str] = []
    A, B = (150, 135, 62), (150, 385, 62)
    o += [arrow([(222, 150), (398, 232)], NAVY, sw=4.5), arrow([(222, 370), (398, 288)], NAVY, sw=4.5)]
    o += _node(A, "pin") + _node(B, "fanbad")
    o.append(circle(490, 260, 86, fill=SKY, stroke=NAVY, sw=4))
    o += thermo(470, 305, NORM, s=1.25, level=0.78) + [arrow([(522, 300), (522, 215)], BLUE, sw=6, size=16)]
    o.append(arrow([(590, 260), (668, 260)], GREY, sw=5, size=16))
    for i in range(3):
        o.append(rect(690, 40 + i * 152, 490, 136, 14, fill=LIGHT, stroke="none", sw=0))
    return svg(o)


MEMO4 = {"Y": (190, 345, 60), "F": (480, 345, 68), "C": (770, 345, 60), "K": (1050, 345, 60)}


def _memo_row(P, hot_edges=(), tags=True):
    """메모를 다시 적은 한 줄: 증상 Y → 고장 유형 F ← 원인 C ← 조치 K. 원 위의 연하늘 칸은 종류 이름표 자리."""
    Y, F, C, K = P["Y"], P["F"], P["C"], P["K"]
    o: list[str] = []
    for key, (a, b) in (("YF", (Y, F)), ("CF", (C, F)), ("KC", (K, C))):
        o += _edge_arrow(a, b, BLUE if key in hot_edges else NAVY, sw=5 if key in hot_edges else 4.5)
    o += _node(Y, "rise") + _node(F, "fm", hot=True) + _node(C, "pin") + _node(K, "wash")
    if tags:
        for (x, y, r) in (Y, F, C, K):
            o.append(rect(x - 78, y - r - 58, 156, 40, 20, fill=PALE, stroke=NAVY, sw=2.5))
    return o


def memo_rewritten() -> str:
    """52장: 위 왼쪽 메모 한 장(글은 라벨), 아래는 같은 내용을 종류 이름표와 이름 붙은 화살표로 다시 적은 한 줄."""
    o: list[str] = []
    o += g(120, 92, 0.72, note_doc(0, 0, ON))
    o.append(arrow([(600, 150), (600, 200)], GREY, sw=5, size=16))
    o += _memo_row(MEMO4)
    return svg(o)


ASK4 = {"Y": (330, 330, 58), "F": (600, 330, 66), "C": (870, 330, 58), "K": (1110, 330, 58)}


def ask_and_follow() -> str:
    """53장: 왼쪽 프로그램이 증상에서 출발해 이름 붙은 화살표를 따라 원인과 조치에 닿는다. 위 칸은 물음과 답 자리."""
    o: list[str] = [rect(230, 14, 960, 116, 14, fill=LIGHT, stroke="none", sw=0)]
    o += g(95, 335, 1.15, agent_icon(0, 0, ON))
    o.append(arrow([(165, 330), (258, 330)], BLUE, sw=5, size=15))
    o += _memo_row(ASK4, hot_edges=("YF", "CF", "KC"))
    return svg(o)


def line_vs_named() -> str:
    """56장: 왼쪽은 이름 없는 선으로 이은 두 원, 오른쪽은 같은 두 원을 이름 붙은 화살표로 이은 것."""
    o: list[str] = [rect(15, 40, 540, 440, 14, fill=LIGHT, stroke="none", sw=0), rect(645, 40, 540, 440, 14, fill=PALE, stroke="none", sw=0)]
    a, b = (150, 290, 62), (420, 290, 68)
    o.append(line(a[0] + a[2] + 6, 290, b[0] - b[2] - 6, 290, stroke=NAVY, sw=4.5))
    o += _node(a, "pin") + _node(b, "fm", hot=True)
    a2, b2 = (780, 290, 62), (1050, 290, 68)
    o += _edge_arrow(a2, b2, BLUE, sw=5.5, size=17)
    o += _node(a2, "pin") + _node(b2, "fm", hot=True)
    return svg(o)


def two_actions() -> str:
    """57장: 완화 조치(왼쪽 팬)는 고장 유형으로, 근본 조치(오른쪽 세척)는 원인으로 — 이름이 다른 두 화살표. 가운데는 원인 → 고장 유형."""
    M, F, C, R = (140, 270, 62), (440, 270, 70), (760, 270, 62), (1060, 270, 62)
    o: list[str] = []
    o += _edge_arrow(M, F, BLUE, sw=5.5, size=17) + _edge_arrow(C, F) + _edge_arrow(R, C, BLUE, sw=5.5, size=17)
    o += _node(M, "fanmax") + _node(F, "fm", hot=True) + _node(C, "pin") + _node(R, "wash")
    return svg(o)


def property_card() -> str:
    """58장: 왼쪽 원(부품 하나)과 그 원에 달아 둔 항목 네 줄(오른쪽 카드). 줄마다 왼쪽이 항목 이름, 오른쪽이 값 자리."""
    o: list[str] = []
    P = (210, 270, 96)
    o.append(rect(132, 110, 156, 40, 20, fill=PALE, stroke=NAVY, sw=2.5))
    o.append(line(312, 270, 452, 270, stroke=NAVY, sw=4))
    o += _node(P, "cooler")
    o.append(rect(460, 40, 700, 440, 16, fill=WHITE, stroke=NAVY, sw=3.5))
    for i in range(4):
        y = 60 + i * 102
        o.append(rect(480, y, 240, 86, 10, fill=PALE, stroke="none", sw=0))
        o.append(rect(736, y, 404, 86, 10, fill=LIGHT, stroke="none", sw=0))
    return svg(o)


def schema_and_graph() -> str:
    """61장: 위 띠 = 온톨로지(빈 원 셋: 조치 → 원인 → 고장 유형, 화살표 이름만). 아래 띠 = 지식 그래프(같은 자리의 실제 대상).
    아래 띠에 원인 하나(떨리는 팬)를 더해 같은 고장 유형으로 잇는다(굵은 파란 화살표). 띠 왼쪽 끝은 띠 이름 자리."""
    xs, yt, yb = (400, 690, 980), 118, 300
    o: list[str] = [rect(15, 10, 1170, 196, 16, fill=PALE, stroke="none", sw=0), rect(15, 222, 1170, 292, 16, fill=WHITE, stroke=GREY, sw=3)]
    for x in xs:
        o += dash_line(x, yt + 52, x, yb - 62, GREY, 3, 8, 7)
    o += [arrow([(xs[0] + 52, yt), (xs[1] - 56, yt)], NAVY, sw=4.5, size=15), arrow([(xs[1] + 52, yt), (xs[2] - 56, yt)], NAVY, sw=4.5, size=15)]
    for x in xs:
        o.append(circle(x, yt, 46, fill=WHITE, stroke=NAVY, sw=3.5))
    K, C, F, E = (xs[0], yb, 52), (xs[1], yb, 52), (xs[2], yb, 58), (690, 455, 42)
    o += _edge_arrow(K, C) + _edge_arrow(C, F) + _edge_arrow(E, F, BLUE, sw=6, size=17)
    o += _node(K, "wash") + _node(C, "pin") + _node(F, "fm", hot=True)
    o.append(circle(E[0], E[1], E[2], fill=SKY, stroke=BLUE, sw=4))
    o += _shaky_fan(E[0], E[1], 17, NORM)
    return svg(o)


FMAP = {"E": (90, 135, 46), "P": (300, 135, 46), "S": (510, 135, 46), "Y": (510, 385, 46), "F": (720, 385, 54),
        "C": (720, 135, 46), "R": (930, 135, 46), "D": (1120, 135, 42)}
FMAP_EDGES = (("E", "P"), ("S", "P"), ("S", "Y"), ("Y", "F"), ("C", "F"), ("R", "C"), ("R", "D"))
FMAP_KIND = {"E": "equip", "P": "cooler", "S": "sensor", "Y": "rise", "F": "fm", "C": "pin", "R": "wash", "D": "doc"}


def fault_map(on=None, hot=()) -> str:
    """63장: 설비 고장을 다룰 때의 지도 — 설비 E · 부품 P · 센서 S · 증상 Y · 고장 유형 F · 원인 C · 조치 R · 근거 문서 D.
    on이 있으면 그 원과 hot 화살표만 밝히고 나머지는 회색으로 둔다."""
    o: list[str] = []
    for a, b in FMAP_EDGES:
        lit = on is None or (a, b) in hot
        o += _edge_arrow(FMAP[a], FMAP[b], (BLUE if (a, b) in hot else NAVY) if lit else GREY, sw=4.5 if lit else 3, size=14)
    for k, P in FMAP.items():
        o += _node(P, FMAP_KIND[k], hot=(k == "F"), grey=(on is not None and k not in on))
    return svg(o)


def walk_to_causes() -> str:
    """64장: 값을 낸 센서 S에서 부품 P로(아래), 증상 Y → 고장 유형 F로(오른쪽), F로 들어오는 화살표를 반대로 따라 원인 후보 셋으로."""
    S, P, Y, F = (120, 200, 52), (120, 400, 52), (390, 200, 52), (670, 200, 62)
    Cs = ((1000, 80, 50), (1000, 260, 50), (1000, 440, 50))
    o: list[str] = []
    o += _edge_arrow(S, P, BLUE, sw=5) + _edge_arrow(S, Y, BLUE, sw=5) + _edge_arrow(Y, F, BLUE, sw=5)
    for c in Cs:
        o += _edge_arrow(c, F, NAVY, sw=4.5)
    o += _node(S, "sensor") + _node(P, "cooler") + _node(Y, "rise") + _node(F, "fm", hot=True)
    o += _node(Cs[0], "pin") + _node(Cs[1], "fanbad") + _node(Cs[2], "amb")
    return svg(o)


def cause_to_actions() -> str:
    """66장: 남은 원인 C(왼쪽 위)를 없애는 근본 조치 R, 고장 유형 F(왼쪽 아래)를 완화하는 완화 조치 M, 두 조치가 근거로 하는 문서 D."""
    C, F, R, M, D = (240, 140, 62), (240, 385, 64), (640, 140, 62), (640, 385, 62), (1040, 262, 66)
    o: list[str] = []
    o += _edge_arrow(C, F) + _edge_arrow(R, C, BLUE, sw=5.5, size=17) + _edge_arrow(M, F, BLUE, sw=5.5, size=17) + _edge_arrow(R, D) + _edge_arrow(M, D)
    o += _node(C, "pin") + _node(F, "fm", hot=True) + _node(R, "wash") + _node(M, "fanmax") + _node(D, "doc")
    return svg(o)


NEW_ONLY: set = {"경로2_1.svg", "경로2_2.svg", "데이터_명령_두경로.svg", "온톨로지_모양.svg", "온톨로지_문장읽기.svg", "약속_채움_두층.svg", "온톨로지_네가지.svg",
                 "값_같은숫자.svg", "메모_다시적기.svg", "물음_따라가기.svg", "관계_선과화살표.svg", "조치_두화살표.svg", "속성_항목.svg",
                 "정한것_적은것.svg", "고장지도.svg", "따라가기_원인후보.svg", "따라가기_조치.svg"}


def main():
    out = {"데이터_명령_두경로.svg": data_command_routes(), "설비_유압파워팩.svg": hyd_unit(), "리니지_1_MQTT.svg": lineage_mqtt(),
           "계층_0_전체.svg": layers("all"),
           "흩어진정보.svg": scattered(), "노드관계.svg": node_rel(),
           "경로2_1.svg": walk2(1), "경로2_2.svg": walk2(2),
           "지식그래프_지도.svg": kg_map(),
           "기록_되짚기.svg": record_trail(), "대화_교정.svg": chat_teacher(), "기억_곡선.svg": retention_curves(), "읽기위치_전후.svg": offset_rows(), "리니지_좁히기.svg": lineage_narrow(),
           "종류_네칸.svg": kinds_columns(), "속성_눈금.svg": property_scale(), "관계_이름.svg": relation_named(),
           "채우기_정의변경.svg": fill_or_redefine(), "저장_그림_옳음.svg": stored_not_true(), "증거_세결과.svg": evidence_outcomes(),
           "PLC_스캔고리.svg": plc_scan_loop(), "연결_점대점_브로커.svg": connect_p2p_broker(), "이벤트로그_띠.svg": event_log_band(),
           "처리_배치_스트림.svg": batch_vs_stream(), "시계열_구간.svg": series_window(),
           "지식그래프_설비쪽.svg": kg_map_focus("equip"), "지식그래프_진단조치쪽.svg": kg_map_focus("diag"),
           "말_다르게부르기.svg": words_apart(), "단어장_약속.svg": promised_words(),
           "MQTT_OT안.svg": lineage_mqtt_ot(), "통로_창고.svg": flow_vs_store(), "원인후보_갈래.svg": cause_branches(),
           "에이전트_다섯걸음.svg": agent_five_steps(), "사건_단계.svg": case_track(),
           "기록_이름갈림.svg": records_apart(), "이름_한대상.svg": aliases_merge(), "원인_더하기.svg": add_cause(), "경로_입구.svg": walk_entry(),
           "온톨로지_모양.svg": ontology_shape(), "온톨로지_문장읽기.svg": ontology_sentences(), "약속_채움_두층.svg": promise_fill_layers(),
           "온톨로지_네가지.svg": ontology_four(),
           "메모_두읽기.svg": memo_two_readings(), "온톨로지_틀.svg": ontology_frame(), "제약_걸러내기.svg": constraint_check(),
           "원인에서_조치로.svg": cause_to_action(),
           "값_같은숫자.svg": same_reading(), "메모_다시적기.svg": memo_rewritten(), "물음_따라가기.svg": ask_and_follow(),
           "관계_선과화살표.svg": line_vs_named(), "조치_두화살표.svg": two_actions(), "속성_항목.svg": property_card(),
           "정한것_적은것.svg": schema_and_graph(), "고장지도.svg": fault_map(), "따라가기_원인후보.svg": walk_to_causes(),
           "따라가기_조치.svg": cause_to_actions()}
    for name, text in out.items():
        assert "<text" not in text
        if (HERE / name).exists() and name not in NEW_ONLY:
            continue          # 승인된 그림은 다시 쓰지 않는다
        (HERE / name).write_text(text, encoding="utf-8")
        print("wrote", name)


if __name__ == "__main__":
    main()
