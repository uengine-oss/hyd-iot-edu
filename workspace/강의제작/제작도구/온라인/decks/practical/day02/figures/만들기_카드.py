"""실전반 2회차 이론 덱의 새 카드 그림(SVG)을 만든다. 글자는 넣지 않는다(라벨은 덱 MD의 요소로 얹는다, 덱 D-8).

사용:
  python 만들기_카드.py                    → 이 폴더에 「카드_*.svg」를 쓴다(하위 폴더 day03/ · 관계표현/은 건드리지 않는다)
  python 만들기_카드.py --라벨             → 그림마다 라벨 자리(`라벨 | 설명 | x,y,폭`)를 찍는다
  python 만들기_카드.py --덱맞춤 <덱.md>   → 그 덱에서 이 그림을 쓰는 장의 `- 요소:` 줄마다 셋째 칸(x,y,폭)만 이 파일의 자리로 바꿔 쓴다

라벨 글은 원고(덱 MD)가 정본이다. 이 파일의 라벨 글은 자리를 계산하려고 원고와 같게 적어 둔 것이고, `--덱맞춤`은 원고의 글과
이 파일의 글이 한 글자라도 다르면 장과 다른 줄을 찍고 멈춘다(원고의 글 · 차례 · 번호는 건드리지 않는다).

그림체 · 색 · 선 굵기 · 카드 · 아이콘은 통합반 2회차 생성기(`../../../integrated/day02/figures/만들기_카드.py`)의 것을 불러 쓴다.
이 파일에는 실전 장에만 있는 그림 함수만 둔다. 그림은 모두 1200 × 510이고 라벨 좌표는 x ÷ 12, y ÷ 5.1(%)이다.
"""
from __future__ import annotations

import importlib.util
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _불러오기(이름: str, 경로: Path):
    spec = importlib.util.spec_from_file_location(이름, 경로)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[이름] = mod            # dataclass가 제 모듈을 sys.modules에서 찾는다
    spec.loader.exec_module(mod)
    return mod


K = _불러오기("통합2_만들기_카드", HERE.parents[2] / "integrated" / "day02" / "figures" / "만들기_카드.py")
NAVY, BLUE, PALE, GREY, LIGHT, WHITE = K.NAVY, K.BLUE, K.PALE, K.GREY, K.LIGHT, K.WHITE
LH_T, LH_D = K.LH_T, K.LH_D
Fig2, hcard, hs, icard, prow, chip, rel, foot = K.Fig2, K.hcard, K.hs, K.icard, K.prow, K.chip, K.rel, K.foot
arrow, dash_line, dash_arrow, line, rect, circle, box, disc = K.arrow, K.dash_line, K.dash_arrow, K.line, K.rect, K.circle, K.box, K.disc


# ───────────────────────── 실전 장에만 있는 조각 ─────────────────────────

def idcard(f, cx, top, w, kind, cls, name, desc, ident, r=38):
    """세로 인스턴스 카드: 큰 원판 아래 클래스 · 이름 · 작은 줄 · 식별자(파란 굵은 글) 한 덩어리. 돌려주는 값: 카드 아래 y."""
    dcy = top + 14 + r
    y = dcy + r + 10
    f.lab("", f"**{cls}**", cx, y, w - 24)
    f.lab(name, desc, cx, y + 26, w - 20)
    f.lab(ident, "", cx, y + 26 + LH_T + LH_D + 8, w - 12, strong=True)
    bot = y + 26 + LH_T + LH_D + 8 + 5 + LH_T + 12
    f.add(box(cx - w / 2, top, w, bot - top) + disc(cx, dcy, r, kind))
    return bot


def text_row(f, x, y, w, item, val, item_w=124, h=46):
    """다른 대상의 이름을 글자로 적어 둔 속성 줄: 칸 둘이 회색이다(건너갈 수 없는 칸)."""
    vx, vw, cy = x + item_w + 8, w - item_w - 8, y + h / 2
    f.add([rect(x, y, item_w, h, 10, fill=LIGHT, stroke=GREY, sw=2), rect(vx, y, vw, h, 10, fill=LIGHT, stroke=GREY, sw=2)])
    f.lab(item, "", x + item_w / 2, cy - 19, item_w - 6)
    f.lab(val, "", vx + vw / 2, cy - 19, vw - 6)


def hclass(f, cx, cy, name, chips, nw=64, h=72, hot=False):
    """가로 클래스 카드: 빈 테두리 원 · 클래스 이름(파란 글) · 속성 이름 칸들 (글, 파랑인가, 폭)이 한 줄. 돌려주는 값: (왼 x, 오른 x)."""
    w = 60 + nw + 6 + sum(c[2] for c in chips) + 8 * (len(chips) - 1) + 13
    x0 = cx - w / 2
    f.add(box(x0, cy - h / 2, w, h, hot, r=20) + [circle(x0 + 34, cy, 20, fill=WHITE, stroke=NAVY, sw=3)])
    f.lab(name, "", x0 + 60 + nw / 2, cy - 19, nw + 8, strong=True)
    x = x0 + 60 + nw + 6
    for text, blue, cw in chips:
        chip(f, x, cy - 23, cw, text, blue)
        x += cw + 8
    return x0, x0 + w


def ask_unit(f, cx, y, q, unit, w=420):
    """물음(작은 줄)과 그 물음이 정한 세는 단위(굵은 줄) 한 덩어리. 돌려주는 값: 아래 y."""
    f.lab("", q, cx, y, w)
    f.lab(unit, "", cx, y + 28, w)
    return y + 28 + 5 + LH_T


# ───────────────────────── 1단원(5~20장) ─────────────────────────

def p06():
    """6장: 아래는 통합 7장의 가로 카드 넷(1호기 → 가진다 → 오일 쿨러 → 쓴다 → 쿨러 코어, 오일 쿨러 ↓ 감시된다 ↓ 유온 센서).
    위는 통합 6장의 갈래: 맨 위 한 줄에서 회색 점선이 갈라져 오일 쿨러 · 쿨러 코어 카드 바로 위의 클래스 이름 덩어리에 닿는다."""
    f = Fig2("카드_설비한대_구성요소와부품.svg")
    W, H, xs = 290, 104, (180, 585, 990)
    mx, by = (xs[1] + xs[2]) / 2, 56
    f.lab("앞에서 부품이라 부른 것", "", mx, 0, 400)
    f.add(dash_line(mx, 40, mx, by, GREY, 3.5, 8, 6) + dash_line(xs[1], by, xs[2], by, GREY, 3.5, 8, 6))
    for x, nm, d in ((xs[1], "구성 요소", "Component · 설비를 이루는 기계 하나하나"), (xs[2], "부품", "Part · 구성 요소 안에서 닳으면 갈아 끼우는 것")):
        f.add(dash_arrow([(x, by), (x, by + 26)], GREY, 3.5, 13, 8, 6))
        f.lab(nm, d, x, by + 32, 420, strong=True)
    cy = by + 32 + 5 + LH_T + LH_D + 16 + H / 2
    for x, kind, cls, nm in zip(xs, ("equip", "cooler", "core"), ("설비", "구성 요소", "부품"), ("1호기", "오일 쿨러", "쿨러 코어")):
        hcard(f, x, cy, W, H, kind, cls, nm)
    rel(f, xs[0] + W / 2 + 8, xs[1] - W / 2 - 8, cy, "가진다")
    rel(f, xs[1] + W / 2 + 8, xs[2] - W / 2 - 8, cy, "쓴다")
    sy = cy + H + 86
    hcard(f, xs[1], sy, W, H, "sensor", "센서", "유온 센서")
    y0, y1 = cy + H / 2 + 8, sy - H / 2 - 8
    f.add(arrow([(xs[1], y0), (xs[1], y1)]))
    f.lab("감시된다", "", xs[1] + 72, (y0 + y1) / 2 - 19, 110)
    return f.fin(0, sy + H / 2)


def p07():
    """7장: 가운데 줄에 이름이 같은 오일 쿨러 셋(식별자는 저마다 다르다). 위의 회색 기록(이름만 적음)은 회색 점선이 세 카드 모두로
    내려가고, 아래의 기록(식별자를 적음)은 남색 화살표 하나가 2호기의 오일 쿨러에만 닿는다."""
    f = Fig2("카드_식별자_전후.svg")
    xs, W, RH = (220, 600, 980), 240, 80
    hcard(f, 600, RH / 2, 330, RH, "doc", "정비 기록", "오일 쿨러 세척", grey=True)
    f.lab("", "어느 오일 쿨러인지 가리키지 못한다", 965, RH / 2 - 16, 360)
    by, top = RH + 20, RH + 44
    f.add(dash_line(600, RH + 6, 600, by, GREY, 3.5, 8, 6) + dash_line(xs[0], by, xs[2], by, GREY, 3.5, 8, 6))
    for i, x in enumerate(xs):
        f.add(dash_arrow([(x, by), (x, top - 6)], GREY, 3.5, 13, 8, 6))
        bot = idcard(f, x, top, W, "cooler", "구성 요소", "오일 쿨러", f"{i + 1}호기", f"EQ-0{i + 1}-COOLER")
    ry = bot + 40 + RH / 2
    hcard(f, 600, ry, 380, RH, "doc", "정비 기록", "EQ-02-COOLER 세척")
    f.add(arrow([(600, ry - RH / 2 - 8), (600, bot + 8)]))
    return f.fin(0, ry + RH / 2)


def p10():
    """10장: 통합 13장 그림(인스턴스 카드 둘을 감시된다로 잇고, 데이터 속성 표시선이 양쪽 칸을 가리킨다)에, 오일 쿨러 카드의 식별자 칸
    아래로 통합 12장의 센서 칸(글자 「유온 센서」)을 회색 칸으로 되살렸다. 그 칸에서 유온 센서 카드 쪽으로 가는 회색 점선은 가운데의
    ✕에서 끊기고(글자 칸은 못 건너간다), 위의 남색 감시된다 화살표만 닿는다(관계로 이으면 건너간다)."""
    f = Fig2("카드_글자칸에서_관계로.svg")
    bot, dcy, ya = icard(f, 230, 0, 380, "cooler", "구성 요소", "오일 쿨러", ({"item": "식별자", "val": "EQ-02-COOLER", "edge": True},), rows_n=2)
    text_row(f, 230 - 190 + 16, ya[0] - 23 + 56, 380 - 32, "센서", "유온 센서")
    _, _, yb = icard(f, 970, 0, 380, "sensor", "센서", "유온 센서", ({"item": "측정 범위", "val": "0~120 ℃", "edge": True}, {"item": "단위", "val": "℃", "hot": True}))
    rel(f, 430, 770, dcy, "감시된다")
    f.lab("객체 간 관계", "Object Property", 600, dcy + 18, 300, strong=True)
    y = ya[0]
    f.lab("데이터 속성", "Data Property", 600, y - (LH_T + LH_D) / 2 - 6, 200, strong=True)
    f.add([line(426, y, 520, y, sw=2), line(680, y, 774, y, sw=2)])
    gy = y + 56
    f.add(dash_line(430, gy, 576, gy, GREY, 4.5, 10, 8) + K.cross_badge(600, gy, 18))
    f.lab("건너갈 길이 없다", "", 600, gy + 23, 240)
    return f.fin(0, foot(f, "이 오일 쿨러를 재는 센서의 단위를 물으면 ℃가 나온다", yb[1] + 104))


def p12():
    """12장: 표기 하나가 가로 줄 하나(왼쪽에 표기와 관계, 오른쪽에 같은 꼴의 낮은 가로 카드와 화살표 — 화살표 수가 표기와 같다).
    1:1 줄에만 많아야 하나를 넘는 연결(회색 2호기 · 회색 화살표 · ✕)을 더했다. 맨 아래는 굵은 한 줄.
    세 줄이 같은 세 칸(왼쪽 대상 · 반대쪽 대상 · 걸린 연결)을 쓴다. 아래 두 줄을 통합 15장의 넓은 두 칸 그대로 두면 1:1 줄의 카드와 세로 자리가 어긋난다."""
    f = Fig2("카드_카디널리티_표기와거름.svg")
    H, hx, hw = 56, 165, 330
    W, X1, X2, X3 = 190, 420, 720, 1085
    L1, R1, WL = X1, X2, W
    y1, n1, n2, m1, m2 = 28, 138, 214, 302, 378

    def notation(t, d, cy):
        f.lab(t, d, hx, cy - (LH_T + LH_D) / 2 - 6, hw, strong=True)

    for y in (94, (n2 + m1) / 2):
        f.add([line(20, y, 1180, y, stroke=GREY, sw=2)])
    notation("1:1", "설비 → 놓인다 → 설치 위치", y1)
    hs(f, X1, y1, W, H, "equip", "1호기"); hs(f, X2, y1, W, H, "loc", "1번 자리")
    f.add(arrow([(X1 + W / 2 + 8, y1), (X2 - W / 2 - 8, y1)]))
    x0, r = X3 - W / 2, H / 2 - 7                                   # 걸린 연결의 대상은 회색 카드
    f.add(box(x0, y1 - H / 2, W, H, grey=True, r=18) + disc(x0 + 10 + r, y1, r, "equip", grey=True))
    tx0 = x0 + 10 + 2 * r + 8
    f.lab("2호기", "", (tx0 + X3 + W / 2) / 2, y1 - 19, X3 + W / 2 - tx0 - 6)
    b0, b1 = X3 - W / 2 - 8, X2 + W / 2 + 8
    f.add(arrow([(b0, y1), (b1, y1)], GREY) + K.cross_badge((b0 + b1) / 2, y1, 17))
    f.lab("하나를 넘는다", "", (b0 + b1) / 2, y1 + 22, 170)
    a0, a1 = L1 + WL / 2 + 8, R1 - WL / 2 - 8
    nm = (n1 + n2) / 2
    notation("1:N", "구성 요소 → 감시된다 → 센서", nm)
    hs(f, L1, nm, WL, H, "pump", "주 펌프"); hs(f, R1, n1, WL, H, "sensor", "압력 센서"); hs(f, R1, n2, WL, H, "sensor", "유량 센서")
    f.add(arrow([(a0, nm - 8), (a1, n1 + 4)]) + arrow([(a0, nm + 8), (a1, n2 - 4)]))
    notation("N:M", "공급사 → 공급한다 → 부품", (m1 + m2) / 2)
    hs(f, L1, m1, WL, H, "supplier", "공급사 1"); hs(f, L1, m2, WL, H, "supplier", "공급사 2")
    hs(f, R1, m1, WL, H, "core", "쿨러 코어"); hs(f, R1, m2, WL, H, "bearing", "팬 베어링")
    f.add(arrow([(a0, m1 - 4), (a1, m1 - 4)]) + arrow([(a0, m1 + 8), (a1, m2 - 12)]) + arrow([(a0, m2 + 4), (a1, m2 + 4)]))
    return f.fin(0, foot(f, "표기는 많아야를 적은 것이라 넘는 연결은 걸리고, 적어도 몇 개인지는 표기 옆에 함께 적는다", m2 + H / 2 + 30))


def p13():
    """13장: 통합 18장 격자(열 머리 클래스 셋, 화살표 열 위 관계 이름과 카디널리티, 세 줄과 3호기 갈래 줄)를 위로 모으고,
    구성 요소 열 · 부품 열 아래에 세는 단위(굵은 줄)와 그 단위를 정한 물음(작은 줄)을 한 덩어리씩 둔다."""
    f = Fig2("카드_세는단위_묶음.svg")
    XE, XC, XP, W, H = 175, 600, 1025, 300, 60
    for x, nm in ((XE, "설비"), (XC, "구성 요소"), (XP, "부품")):
        f.lab("", f"**{nm}**", x, 4, 200)
    f.lab("가진다 **1:N**", "", (XE + XC) / 2, 0, 200)
    f.lab("쓴다 **N:M**", "", (XC + XP) / 2, 0, 200)
    R, fy = (76, 154, 232), 310
    a0, a1, b0, b1 = XE + W / 2 + 8, XC - W / 2 - 8, XC + W / 2 + 8, XP - W / 2 - 8
    for y, nm in zip(R, ("1호기", "2호기", "3호기")):
        hs(f, XE, y, W, H, "equip", nm)
        hs(f, XC, y, W, H, "cooler", "오일 쿨러")
        f.add(arrow([(a0, y), (a1, y)]))
    hs(f, XC, fy, W, H, "fan", "쿨러 팬")
    f.add(arrow([(XE, R[2] + H / 2 + 4), (XE, fy), (a1, fy)]))
    hs(f, XP, R[1], W, H, "core", "쿨러 코어 CC-2040")
    hs(f, XP, fy, W, H, "gasket", "쿨러 가스켓")
    for i, y in enumerate(R):
        f.add(arrow([(b0, y - 8 if i == 2 else y), (b1, R[1] + (i - 1) * 14)]))
    f.add(arrow([(b0, R[2] + 10), (b1, fy)]))
    by = fy + H / 2 + 30
    f.lab("설비마다 하나씩 센다", "2호기 오일 쿨러의 정비 이력을 묻는다", XC, by, 360)
    f.lab("품번마다 하나로 센다", "어떤 부품을 주문할지 묻는다 / 쿨러마다 든 실물은 따로 세지 않는다", XP, by, 340)
    return f.fin(0, by + 5 + LH_T + 2 * LH_D)


def p15():
    """15장: 공급사 둘이 같은 팬 베어링을 댄다. 두 공급한다 화살표마다 가운데에 속성 칸 한 쌍(회색 키 칸 · 파란 테두리 값 칸)이
    걸려 있고, 두 값 칸에서 나온 가는 남색 선이 가운데에서 만나는 자리가 그 이름(관계에 붙는 속성)이다. 노드 카드에는 값 칸이 없다."""
    f = Fig2("카드_관계에붙는속성.svg")
    W, H, LX, RX, T, B = 280, 104, 170, 1030, 70, 330
    C = (T + B) / 2
    hcard(f, LX, T, W, H, "supplier", "공급사", "공급사 1")
    hcard(f, LX, B, W, H, "supplier", "공급사", "공급사 2")
    hcard(f, RX, C, W, H, "bearing", "부품", "팬 베어링")
    a0 = LX + W / 2 + 8
    f.add(arrow([(a0, T), (RX, T), (RX, C - H / 2 - 8)]) + arrow([(a0, B), (RX, B), (RX, C + H / 2 + 8)]))
    px, pw, iw = 540, 300, 110
    vx = px + iw + 8 + (pw - iw - 8) / 2
    for y, val in ((T, "20만 원"), (B, "26만 원")):
        f.lab("공급한다", "", (a0 + px) / 2, y - 46, 150)
        prow(f, px, y - 23, pw, "단가", val, hot=True, item_w=iw)
    f.lab("관계에 붙는 속성", "Relationship Property", vx, C - (LH_T + LH_D) / 2 - 6, 300, strong=True)
    f.add([line(vx, T + 23 + 6, vx, C - 36, sw=2), line(vx, C + 36, vx, B - 23 - 6, sw=2)])
    return f.fin(0, foot(f, "단가는 어느 공급사가 어느 부품을 대느냐, 그 짝이 정한다", B + H / 2 + 22))


def p16():
    """16장: 가는 세로 선으로 나눈 두 대안(같은 무게). 왼쪽은 자기 속성 셋을 구성 요소 하나에 둔 오일 쿨러 인스턴스(냉각 용량만 ✓,
    두 칸은 빈 점선 칸), 오른쪽은 따로 나눈 클래스 카드 셋(공통 속성 칸 파랑이 세 번, 자기 속성 칸 회색)."""
    f = Fig2("카드_자기속성_두대안.svg")
    LX, RX = 290, 890          # 두 칸의 가운데. 왼쪽 카드(폭 420)와 오른쪽 카드(폭 471)의 바깥 여백이 같게 잡았다
    f.lab("한 클래스에 모두 두면", "쓰지 않는 칸이 빈 채로 붙는다", LX, 0, 480)
    f.lab("클래스를 따로 나누면", "공통 속성을 클래스마다 거듭 적는다", RX, 0, 480)
    top = 78
    bot = K.part_blank(f, LX, top, 420)
    f.add([line(577, 0, 577, bot, stroke=GREY, sw=2)])
    my, pitch = (top + bot) / 2, 112
    for i, (nm, own) in enumerate((("펌프", "토출 유량"), ("쿨러", "냉각 용량"), ("팬", "회전수"))):
        hclass(f, RX, my + (i - 1) * pitch, nm, (("식별자 · 이름", True, 180), (own, False, 140)))
    return f.fin(0, bot)


def p17():
    """17장: 위에 상위 클래스 카드(파란 테두리 · 공통 속성 칸 파랑), 아래에 하위 클래스 카드 셋(자기 속성 칸 회색), 세 줄기를 모은
    속이 빈 삼각 화살촉이 상속. 쿨러 카드 바로 아래의 오일 쿨러 인스턴스는 파란 점선(속한다)으로 쿨러에 이어지고, 두 칸의 색이
    그 속성을 정한 클래스의 칸과 같다. 클래스 카드는 16장 오른쪽 칸과 같은 가로 꼴이다(통합 22장의 세로 꼴 카드로는 클래스 두 층 ·
    줄기 · 인스턴스 카드의 높이가 그림 높이 510을 넘는다)."""
    f = Fig2("카드_상속_나무와인스턴스.svg")
    cx, xs, h = 700, (400, 700, 1000), 72
    y1, y2 = h / 2, h + 108 + h / 2
    hclass(f, cx, y1, "구성 요소", (("식별자 · 이름", True, 190),), nw=110, hot=True)
    for x, nm, own in zip(xs, ("펌프", "쿨러", "팬"), ("토출 유량", "냉각 용량", "회전수")):
        hclass(f, x, y2, nm, ((own, False, 132),))
    bus = y2 - h / 2 - 26
    f.add([line(x, y2 - h / 2 - 6, x, bus, sw=4) for x in xs]
          + [line(xs[0], bus, xs[2], bus, sw=4), line(cx, bus, cx, h + 26, sw=4)] + K.tri_head(cx, h + 6, -math.pi / 2, NAVY, 22))
    f.lab("상위 클래스", "Superclass", 150, y1 - 30, 240, strong=True)
    f.lab("하위 클래스", "Subclass", 150, y2 - 30, 240, strong=True)
    f.lab("상속", "Inheritance", cx + 80, h + 10, 130, strong=True)
    f.lab("클래스 계층", "Class Hierarchy · 클래스가 클래스 아래로 이어진 모양", 150, y2 + 42, 264, strong=True)
    it, iw, ih, r = y2 + h / 2 + 62, 520, 124, 44
    x0 = cx - iw / 2
    f.add(box(x0, it, iw, ih) + disc(x0 + 14 + r, it + ih / 2, r, "cooler"))
    tx0, tx1 = x0 + 14 + 2 * r + 8, x0 + iw - 6
    tc = (tx0 + tx1) / 2
    f.lab("오일 쿨러", "쿨러의 인스턴스이면서 구성 요소의 인스턴스", tc, it + 8, tx1 - tx0)
    cw = 178
    chip(f, tc - cw - 4, it + 72, cw, "식별자 · 이름", True, h=40)
    chip(f, tc + 4, it + 72, cw, "냉각 용량", False, h=40)
    f.add(dash_arrow([(cx, it - 8), (cx, y2 + h / 2 + 8)], BLUE, 4, 13, 8, 6))
    f.lab("속한다", "", cx + 62, (it + y2 + h / 2) / 2 - 19, 90)
    return f.fin(0, it + ih)


def p19():
    """19장: 통합 26장 격자(네 줄의 설비 → 가진다 → 오일 쿨러, 네 쓴다 화살표가 쿨러 코어 하나로 모인다. 더한 4호기 줄만 파랑)에서
    쿨러 코어 카드만 통합 25장의 쿨러 코어 카드 높이로 키워, 이름 아래에 읽은 속성값 줄(③ 품번, 파란 굵은 글)을 둔다."""
    f = Fig2("카드_설비늘기_품번읽기.svg")
    XE, XC, XP, W, H, PH = 175, 600, 1025, 300, 64, 116
    for x, nm in ((XE, "설비"), (XC, "구성 요소"), (XP, "부품")):
        f.lab("", f"**{nm}**", x, 4, 200)
    f.lab("① 가진다", "", (XE + XC) / 2, 0, 120)
    f.lab("② 쓴다", "", (XC + XP) / 2, 0, 120)
    R = (78, 166, 254, 342)
    a0, a1, b0, b1 = XE + W / 2 + 8, XC - W / 2 - 8, XC + W / 2 + 8, XP - W / 2 - 8
    cy = (R[1] + R[2]) / 2
    for i, y in enumerate(R):
        new = i == 3
        hs(f, XE, y, W, H, "equip", f"{i + 1}호기", hot=new, desc="**EQ-04**" if new else "")
        hs(f, XC, y, W, H, "cooler", "오일 쿨러", hot=new, desc="**EQ-04-COOLER**" if new else "")
        f.add(arrow([(a0, y), (a1, y)]) + arrow([(b0, y), (b1, cy + (i - 1.5) * 12)]))
    x0, r = XP - W / 2, 42
    f.add(box(x0, cy - PH / 2, W, PH, r=20) + disc(x0 + 14 + r, cy, r, "core"))
    tx0 = x0 + 14 + 2 * r + 8
    tx, tw = (tx0 + XP + W / 2) / 2, XP + W / 2 - tx0 - 6
    f.lab("쿨러 코어", "", tx, cy - 36, tw)
    f.lab("③ 품번 CC-2040", "", tx, cy - 4, tw, strong=True)
    return f.fin(0, foot(f, "오일 쿨러에 갈아 끼울 부품의 품번을 2호기에서 물어도 4호기에서 물어도 같은 길로 CC-2040이 나온다", R[3] + H / 2 + 16))


def p20():
    """20장: 왼쪽은 설비 안의 자리(구성 요소 주 펌프), 오른쪽은 그 자리에 달렸던 실물 둘(지금 달린 것은 남색, 떼어 낸 것은 회색).
    아래에는 왼쪽 열 · 오른쪽 열마다 물음(작은 줄)과 그 물음이 정한 세는 단위(굵은 줄)를 한 덩어리씩 둔다."""
    f = Fig2("카드_자리와실물.svg")
    W, H, LX, RX, T, B = 390, 116, 270, 930, 58, 214
    C = (T + B) / 2
    hcard(f, LX, C, W, H, "pump", "구성 요소", "주 펌프", desc="설비 안의 자리")
    for y, sn, d, grey in ((T, "KP-2603-114", "지금 달린 실물", False), (B, "KP-1902-551", "2026-03-11에 떼어 낸 실물", True)):
        x0, r = RX - W / 2, H / 2 - 14
        f.add(box(x0, y - H / 2, W, H, grey=grey, r=20)
              + [circle(x0 + 14 + r, y, r, fill=WHITE if grey else LIGHT, stroke="none", sw=0)] + K.card_icon("pump", x0 + 14 + r, y, r / 62, grey))
        tx0 = x0 + 14 + 2 * r + 8
        tx, tw = (tx0 + RX + W / 2) / 2, RX + W / 2 - tx0 - 6
        ty = y - (28 + LH_T + LH_D) / 2 - 3
        f.lab("", "**실물**", tx, ty, tw)
        f.lab(sn, d, tx, ty + 28, tw)
    a0, a1 = LX + W / 2 + 8, RX - W / 2 - 8
    f.add(arrow([(a0, C - 8), (a1, T + 4)]) + arrow([(a0, C + 8), (a1, B - 4)], GREY))
    by = B + H / 2 + 38
    ask_unit(f, LX, by, "이 자리에 맞는 교체 부품을 묻는다", "자리마다 하나로 센다")
    end = ask_unit(f, RX, by, "어느 펌프를 언제 달고 뗐는지 묻는다", "실물마다 하나로 센다")
    return f.fin(0, end)


FIGS = [p06, p07, p10, p12, p13, p15, p16, p17, p19, p20]


# ───────────────────────── 덱 맞춤 ─────────────────────────

def fit_deck(md: Path, labels: dict[str, list[str]]) -> int:
    """덱 MD에서 `- 그림: figures/<이 생성기가 만든 그림>`인 장의 요소 줄마다 셋째 칸만 이 생성기의 자리로 바꿔 쓴다.
    요소의 글 · 차례 · 번호는 원고 그대로 둔다. 원고의 글과 이 파일의 글이 다르면 멈춘다. 돌려주는 값: 바꾼 장 수."""
    text = md.read_bytes().decode("utf-8")
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(nl)
    starts = [k for k, s in enumerate(lines) if s.startswith("## SLIDE")] + [len(lines)]
    n, errs = 0, []
    for a, b in zip(starts, starts[1:]):
        pic = next((s[len("- 그림: "):].strip() for s in lines[a:b] if s.startswith("- 그림: ")), "")
        if not pic.startswith("figures/") or pic.rsplit("/", 1)[-1] not in labels:
            continue
        pool = [tuple(s.rsplit(" | ", 1)) for s in labels[pic.rsplit("/", 1)[-1]]]      # (글, 자리)
        k = lines.index("- 요소:", a, b) + 1
        while k < b and (m := re.match(r"(  (?:\d+\.|-) )(.*) \| [\d.,]+$", lines[k])):
            hit = next((i for i, (글, _) in enumerate(pool) if 글 == m.group(2)), None)
            if hit is None:
                errs.append(f"{lines[a]}: 원고 라벨 「{m.group(2)}」이 생성기에 없다")
            else:
                lines[k] = f"{m.group(1)}{m.group(2)} | {pool.pop(hit)[1]}"
            k += 1
        errs += [f"{lines[a]}: 생성기 라벨 「{글}」이 원고에 없다" for 글, _ in pool]
        n += 1
    if errs:
        raise SystemExit("덱맞춤을 멈춘다(원고는 그대로다):\n  " + "\n  ".join(errs))
    md.write_bytes(nl.join(lines).encode("utf-8"))
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
        print(f"덱맞춤: {md.name}에서 {fit_deck(md, labels)}장의 라벨 자리를 바꿔 썼다")


if __name__ == "__main__":
    main()
