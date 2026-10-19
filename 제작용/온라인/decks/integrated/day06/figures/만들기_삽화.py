"""통합반 6일차 삽화(SVG)를 만든다. 글자는 넣지 않는다(라벨은 덱 MD의 요소로 얹는다).

화풍(선 굵기 · 색 · 그림 조각)은 1일차의 `만들기_삽화.py`를 복사한 `삽화_기본.py`에서 가져온다.
사용: python 만들기_삽화.py            → 이 폴더에 SVG를 쓴다
"""
from __future__ import annotations

import math
from pathlib import Path

from 삽화_기본 import (BLUE, GREY, LIGHT, NAVY, NORM, OFF, ON, PALE, SKY, WHITE, St, agent_icon, approve_icon, arrow, bell,
                    circle, cylinder_db, fan, g, graph_icon, head, line, path, poly, rect, server, svg)

HERE = Path(__file__).resolve().parent


# ───────────────────────── 작은 그림 조각 ─────────────────────────

def bar(x, y, w, h=12, color=GREY):
    return rect(x, y, w, h, h / 2, fill=color, stroke="none", sw=0)


def sop_doc(cx, cy, st: St, w=92, h=116):
    """현장 문서(SOP): 제목 띠와 줄."""
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
    """읽는 도구(돋보기)."""
    return [line(cx + r * 0.7, cy + r * 0.7, cx + r * 1.55, cy + r * 1.55, stroke=st.line, sw=7),
            circle(cx, cy, r, fill=st.accent, stroke=st.line)]


def pencil(cx, cy, st: St, s=1.0):
    """쓰는 도구(연필)."""
    return [f'<g transform="rotate(38 {cx} {cy})">',
            rect(cx - 8 * s, cy - 30 * s, 16 * s, 44 * s, 3, fill=st.fill, stroke=st.line),
            line(cx - 8 * s, cy - 18 * s, cx + 8 * s, cy - 18 * s, stroke=st.line, sw=2.5),
            poly([(cx - 8 * s, cy + 14 * s), (cx + 8 * s, cy + 14 * s), (cx, cy + 32 * s)], fill=st.line),
            "</g>"]


def tag(cx, cy, st: St, ok: bool):
    """도구에 다는 표시. ok = 읽기 전용."""
    pts = [(cx - 34, cy), (cx - 16, cy - 20), (cx + 34, cy - 20), (cx + 34, cy + 20), (cx - 16, cy + 20)]
    o = [poly(pts, fill=SKY if ok else WHITE, stroke=st.line, sw=3.5), circle(cx - 14, cy, 4.5, fill=WHITE, stroke=st.line, sw=2.5)]
    if ok:
        o.append(path(f"M {cx + 2},{cy} L {cx + 10},{cy + 8} L {cx + 24},{cy - 8}", stroke=st.line, sw=4))
    else:
        o += [line(cx + 4, cy - 9, cx + 22, cy + 9, stroke=st.line, sw=4), line(cx + 22, cy - 9, cx + 4, cy + 9, stroke=st.line, sw=4)]
    return o


def check_mark(cx, cy, r=28):
    return [circle(cx, cy, r, fill=SKY, stroke=NAVY, sw=3.5),
            path(f"M {cx - r * 0.42},{cy + r * 0.02} L {cx - r * 0.1},{cy + r * 0.36} L {cx + r * 0.46},{cy - r * 0.32}", stroke=NAVY, sw=5)]


def cross_mark(cx, cy, r=28):
    return [circle(cx, cy, r, fill=WHITE, stroke=NAVY, sw=3.5),
            line(cx - r * 0.36, cy - r * 0.36, cx + r * 0.36, cy + r * 0.36, stroke=NAVY, sw=5),
            line(cx + r * 0.36, cy - r * 0.36, cx - r * 0.36, cy + r * 0.36, stroke=NAVY, sw=5)]


def client_box(cx, cy, st: St, s=1.0):
    """클라이언트: 서버 하나와 이어지는 연결 단자."""
    w, h = 84 * s, 58 * s
    return [rect(cx - w / 2, cy - h / 2, w, h, 12 * s, fill=st.fill, stroke=st.line),
            circle(cx - 14 * s, cy, 9 * s, fill=st.accent, stroke=st.line, sw=3),
            line(cx - 5 * s, cy, cx + 22 * s, cy, stroke=st.line, sw=4),
            line(cx + 22 * s, cy - 11 * s, cx + 22 * s, cy + 11 * s, stroke=st.line, sw=4),
            line(cx + w / 2, cy - 10 * s, cx + w / 2 + 10 * s, cy - 10 * s, stroke=st.line, sw=5),
            line(cx + w / 2, cy + 10 * s, cx + w / 2 + 10 * s, cy + 10 * s, stroke=st.line, sw=5)]


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


def dashed(x1, y1, x2, y2, color=NAVY, sw=3.5):
    ang = math.atan2(y2 - y1, x2 - x1)
    return [line(x1, y1, x2 - 10 * math.cos(ang), y2 - 10 * math.sin(ang), stroke=color, sw=sw, stroke_dasharray="9 8"),
            head(x2, y2, ang, color, 12)]


# ───────────────────────── 1. 실행 고리와 스킬의 자리 ─────────────────────────

def loop(skill: bool) -> str:
    o: list[str] = [rect(840, 24, 340, 472, 16, fill=LIGHT, stroke="none", sw=0)]
    o.append(arrow([(176, 264), (306, 264)], NAVY, sw=5, size=14))
    o += [circle(110, 264, 58, fill=PALE, sw=4)] + g(110, 260, 2.0, bell(0, 0, ON))
    o += g(400, 264, 1.7, agent_icon(0, 0, ON))
    o += [arrow([(496, 226), (828, 226)], BLUE, sw=5, size=14), arrow([(828, 304), (496, 304)], NAVY, sw=5, size=14)]
    o += g(935, 110, 0.85, graph_icon(0, 0, ON)) + g(935, 260, 0.85, cylinder_db(0, 0, ON)) + g(935, 410, 0.85, table_icon(0, 0, ON))
    o.append(arrow([(400, 330), (400, 392)], NAVY, sw=5, size=14))
    o += g(400, 450, 0.6, ranking(0, 0, ON))
    if skill:
        o += skill_doc(400, 66, ON, w=92, h=104)
        o.append(arrow([(400, 122), (400, 166)], BLUE, sw=5, size=14))
    return svg(o)


# ───────────────────────── 2. SKILL.md의 구성 ─────────────────────────

def skilldoc() -> str:
    X = 100
    o = [rect(X + 40, 8, 500, 504, 12, fill=WHITE)]
    hot = dict(fill=PALE, stroke=SKY, sw=3)
    # 머리말
    o += [rect(X + 58, 22, 464, 64, 8, **hot),
          line(X + 72, 34, X + 150, 34, stroke=NAVY, sw=3, stroke_dasharray="8 7"),
          line(X + 72, 76, X + 150, 76, stroke=NAVY, sw=3, stroke_dasharray="8 7"),
          bar(X + 72, 43, 56, 10, NAVY), bar(X + 138, 43, 230, 10), bar(X + 72, 58, 96, 10, NAVY), bar(X + 178, 58, 320, 10)]
    # 제목과 요약
    o += [rect(X + 62, 98, 210, 20, 6, fill=NAVY, stroke="none", sw=0), rect(X + 58, 128, 464, 44, 8, **hot),
          bar(X + 72, 137, 420, 10), bar(X + 72, 153, 300, 10)]
    # 절차
    o += [rect(X + 62, 184, 90, 14, 5, fill=NAVY, stroke="none", sw=0), rect(X + 58, 204, 464, 178, 8, fill=LIGHT, stroke="none", sw=0),
          rect(X + 64, 208, 452, 28, 6, **hot), rect(X + 92, 265, 424, 22, 6, **hot)]
    for y, w in ((222, 330), (252, 380), (304, 300), (334, 390), (364, 340)):
        o += [circle(X + 80, y, 9, fill=SKY, stroke=NAVY, sw=2.5), bar(X + 98, y - 6, w, 12)]
    o.append(bar(X + 104, 271, 300, 10))
    o.append(path(f"M {X + 498},300 L {X + 508},300 L {X + 508},368 L {X + 498},368", stroke=BLUE, sw=3.5))
    # 결과
    o += [rect(X + 62, 396, 90, 14, 5, fill=NAVY, stroke="none", sw=0), rect(X + 58, 418, 464, 52, 8, **hot),
          bar(X + 72, 430, 400, 10), bar(X + 72, 448, 280, 10)]
    for y in (54, 150, 214, 276, 340, 444):
        o.append(arrow([(X + 528, y), (X + 596, y)], BLUE, sw=3.5, size=11))
    return svg(o)


# ───────────────────────── 4. 한 사건의 두 절차 ─────────────────────────

def twoproc() -> str:
    Y = 270
    o = [rect(196, 70, 470, 390, 16, fill=PALE, stroke=SKY, sw=3), rect(880, 70, 300, 390, 16, fill=LIGHT, stroke=GREY, sw=3)]
    o += [arrow([(152, Y), (234, Y)], NAVY, sw=5, size=13), arrow([(344, Y), (378, Y)], BLUE, sw=5, size=12),
          arrow([(500, Y), (522, Y)], BLUE, sw=5, size=12), arrow([(668, Y), (716, Y)], NAVY, sw=5, size=13),
          arrow([(832, Y), (896, Y)], NAVY, sw=5, size=13), arrow([(1004, Y), (1044, Y)], BLUE, sw=5, size=12)]
    o += [circle(96, Y, 52, fill=WHITE, sw=4)] + g(96, Y - 4, 1.8, bell(0, 0, ON))
    o += skill_doc(290, Y, ON)
    o += g(440, Y + 6, 1.15, agent_icon(0, 0, ON))
    o += g(586, Y, 0.5, ranking(0, 0, ON))
    o += g(772, Y - 6, 1.1, approve_icon(0, 0, ON))
    o += sop_doc(950, Y, ON)
    o += fan(1102, Y, 44, ON, rot=20, hot=True)
    o.append(arrow([(1163, Y + 20), (1163, Y - 22)], BLUE, sw=5, size=12))
    return svg(o)


# ───────────────────────── 5. 같은 스킬, 다른 경보 ─────────────────────────

def reuse() -> str:
    rows = (100, 260, 420)
    o: list[str] = []
    for i, by in enumerate(rows):
        c = BLUE if i < 2 else GREY
        o.append(path(f"M 232,260 L 290,260 C 350,260 340,{by} 400,{by}", stroke=c, sw=4.5))
        o.append(arrow([(400, by), (486, by)], c, sw=4.5, size=13))
    o += g(150, 260, 1.6, skill_doc(0, 0, ON), boost=0.7)
    for i, by in enumerate(rows):
        st = ON if i < 2 else OFF
        c = NAVY if i < 2 else GREY
        o += [circle(540, by, 44, fill=PALE if i < 2 else WHITE, stroke=st.line, sw=4)] + g(540, by - 3, 1.5, bell(0, 0, st))
        o += [arrow([(592, by), (688, by)], c, sw=4.5, size=13), arrow([(812, by), (900, by)], c, sw=4.5, size=13)]
        o += g(750, by + 4, 0.95, agent_icon(0, 0, st))
        o += g(980, by, 0.55, ranking(0, 0, st))
    return svg(o)


# ───────────────────────── 6. 따로 잇는 방식과 표준으로 잇는 방식 ─────────────────────────

def nm() -> str:
    ys = (125, 270, 415)
    o = [line(600, 30, 600, 490, stroke=GREY, sw=2.5, stroke_dasharray="6 8")]
    for a in ys:
        for b in ys:
            o.append(line(166, a, 418, b, stroke=NAVY, sw=3))
    o.append(rect(884, 78, 32, 384, 16, fill=SKY, stroke=NAVY, sw=3.5))
    for y in ys:
        o += [line(766, y, 884, y, stroke=BLUE, sw=4.5), line(916, y, 1034, y, stroke=BLUE, sw=4.5)]
    icons = (graph_icon, cylinder_db, table_icon)
    for i, y in enumerate(ys):
        o += g(110, y + 4, 0.8, agent_icon(0, 0, ON)) + g(470, y, 0.75, icons[i](0, 0, ON))
        o += g(710, y + 4, 0.8, agent_icon(0, 0, ON)) + g(1090, y, 0.75, icons[i](0, 0, ON))
    return svg(o)


# ───────────────────────── 7. MCP의 네 구성요소 ─────────────────────────
# 통합반 6회차 원 덱과 조립 덱(실전반 4일차 · 실전반 오프라인 5회차 · 통합반 오프라인 6회차)이 함께 쓴다.

def mcp_parts() -> str:
    ys = (160, 295, 430)
    o = [rect(30, 70, 530, 426, 18, fill=PALE, stroke=SKY, sw=3)]
    o += [line(224, 295, 330, 295, sw=3.5), line(330, ys[0], 330, ys[-1], sw=3.5)]
    o += g(150, 295, 1.35, agent_icon(0, 0, ON))
    icons = (graph_icon, cylinder_db, table_icon)
    for i, y in enumerate(ys):
        o.append(arrow([(330, y), (422, y)], NAVY, sw=3.5, size=11))
        o += client_box(470, y, ON)
        o.append(arrow([(526, y), (654, y)], BLUE, sw=5, size=14))
        o.append(rect(662, y - 40, 300, 80, 14, fill=WHITE, stroke=NAVY, sw=3.5))
        o += g(722, y, 0.6, server(0, 0, ON))
        o += gear(812, y, 22, ON, hot=True) + gear(868, y, 22, ON, hot=True) + gear(924, y, 22, ON, hot=True)
        o.append(arrow([(966, y), (1030, y)], NAVY, sw=3.5, size=11))
        o += g(1090, y - 8, 0.66, icons[i](0, 0, ON))
    return svg(o)


# ───────────────────────── 8. 도구 목록의 발견과 호출 ─────────────────────────

def listcall() -> str:
    CX, SX = 330, 930
    o: list[str] = []
    for y0 in (120, 244, 368):
        o.append(rect(60, y0, 1080, 116, 12, fill=LIGHT, stroke="none", sw=0))
    o += [line(CX, 100, CX, 494, stroke=NAVY, sw=3, stroke_dasharray="7 8"), line(SX, 100, SX, 494, stroke=NAVY, sw=3, stroke_dasharray="7 8")]
    o += client_box(CX, 58, ON, 1.1) + g(SX, 56, 0.72, server(0, 0, ON))
    for y0 in (120, 244, 368):
        o += [arrow([(CX + 8, y0 + 50), (SX - 8, y0 + 50)], BLUE, sw=5, size=14),
              arrow([(SX - 8, y0 + 104), (CX + 8, y0 + 104)], NAVY, sw=5, size=14)]
    return svg(o)


# ───────────────────────── 9. 연결 방식 두 가지 ─────────────────────────

def transports() -> str:
    o = [line(600, 30, 600, 490, stroke=GREY, sw=2.5, stroke_dasharray="6 8")]
    # stdio: 한 PC 안의 클라이언트와 서버 프로세스
    o.append(rect(50, 110, 500, 310, 18, fill=LIGHT, stroke=NAVY, sw=3.5))
    o += client_box(170, 250, ON, 1.3) + g(430, 250, 0.95, server(0, 0, ON))
    o += [arrow([(236, 226), (378, 226)], BLUE, sw=4.5, size=12), arrow([(378, 274), (236, 274)], NAVY, sw=4.5, size=12)]
    # HTTP: 두 PC가 떠 있는 서버 하나에 접속
    for y in (150, 372):
        o.append(rect(650, y - 62, 190, 124, 16, fill=LIGHT, stroke=NAVY, sw=3.5))
        o += client_box(745, y - 14, ON)
    o.append(rect(990, 176, 170, 168, 16, fill=PALE, stroke=SKY, sw=3))
    o += g(1075, 260, 0.95, server(0, 0, ON))
    o += [arrow([(842, 150), (916, 150), (916, 236), (986, 236)], BLUE, sw=4.5, size=12),
          arrow([(842, 372), (916, 372), (916, 286), (986, 286)], BLUE, sw=4.5, size=12)]
    return svg(o)


# ───────────────────────── 10. 읽기와 쓰기를 가르는 세 겹 ─────────────────────────

def gates() -> str:
    lanes = (140, 275, 410)
    o = [rect(60, 84, 270, 412, 16, fill=LIGHT, stroke="none", sw=0), rect(400, 84, 150, 412, 16, fill=LIGHT, stroke="none", sw=0),
         rect(640, 84, 220, 412, 16, fill=PALE, stroke=SKY, sw=3)]
    o += [arrow([(300, lanes[0]), (438, lanes[0])], BLUE, sw=5, size=13), arrow([(300, lanes[1]), (438, lanes[1])], GREY, sw=4, size=12),
          arrow([(300, lanes[2]), (438, lanes[2])], GREY, sw=4, size=12), arrow([(512, lanes[0]), (656, lanes[0])], BLUE, sw=5, size=13),
          arrow([(864, lanes[0]), (936, lanes[0]), (936, 275), (1006, 275)], BLUE, sw=5, size=13)]
    o += magnifier(122, lanes[0] - 6, ON) + pencil(130, lanes[1], ON) + gear(130, lanes[2], 28, NORM)
    o += tag(246, lanes[0], ON, True) + tag(246, lanes[1], ON, False)
    o += check_mark(475, lanes[0]) + cross_mark(475, lanes[1]) + cross_mark(475, lanes[2])
    o.append(rect(662, lanes[0] - 17, 176, 34, 9, fill=SKY, stroke=NAVY, sw=3))
    for k in range(1, 6):
        o.append(bar(668, lanes[0] + 12 + k * 52, (150, 120, 160, 110, 140)[k - 1], 16))
    o += g(1082, 281, 1.3, agent_icon(0, 0, ON))
    return svg(o)


def main():
    out = {"고리_1.svg": loop(True), "스킬문서.svg": skilldoc(),
           "두절차.svg": twoproc(), "재사용.svg": reuse(), "연결의수.svg": nm(), "MCP구성.svg": mcp_parts(),
           "목록호출.svg": listcall(), "연결방식.svg": transports(), "세겹.svg": gates()}
    for name, text in out.items():
        assert "<text" not in text
        (HERE / name).write_text(text, encoding="utf-8")
        print("wrote", name)


if __name__ == "__main__":
    main()
