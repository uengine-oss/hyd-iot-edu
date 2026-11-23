"""실전반 2회차 덱의 단원 끝 적용 장(24 · 40 · 58장) 그림(SVG)을 만든다. 글자는 넣지 않는다(라벨은 원고 `../실전반_02일차.md`의 요소로 얹는다, 덱 D-8).

사용:
  python 만들기_적용장.py          → 이 폴더에 「적용_*.svg」를 쓴다
  python 만들기_적용장.py --라벨   → 그림마다 원고에 붙일 라벨 줄(`라벨 | 설명 | x,y,폭`)을 찍는다(원고의 그 장 요소와 같아야 한다)

그림체 · 색 · 선 굵기 · 카드 · 아이콘은 통합반 2회차 생성기(../../../integrated/day02/figures/만들기_카드.py)의 것을 불러 쓴다.
그림은 모두 1200 × 510이고 라벨 좌표는 x ÷ 12, y ÷ 5.1(%)이다.
적용 장은 배운 원리로 따로 적힌 것이 하나로 모이거나 이어지는 것을 보인다. 어느 줄 · 코드 · 품번끼리 같은 대상인지, 어느 값을 식별자로 둘지는
실습이 학생에게 맡기는 판단이라 그림에 실제 코드 · 품번 · 이름을 넣지 않고, 칩과 막대로만 그린다(덱 D-13).
"""
from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _불러오기(이름: str, 경로: Path):
    spec = importlib.util.spec_from_file_location(이름, 경로)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[이름] = mod
    spec.loader.exec_module(mod)
    return mod


K = _불러오기("통합2_만들기_카드", HERE.parents[2] / "integrated/day02/figures/만들기_카드.py")
NAVY, SKY, BLUE, PALE, GREY, LIGHT, WHITE = K.NAVY, K.SKY, K.BLUE, K.PALE, K.GREY, K.LIGHT, K.WHITE
LH_T, LH_D = K.LH_T, K.LH_D
Fig2, banded, rect, line, circle, path, poly, arrow, dash_line, g, card_icon = (
    K.Fig2, K.banded, K.rect, K.line, K.circle, K.path, K.poly, K.arrow, K.dash_line, K.g, K.card_icon)


# ───────────────────────── 그림 칸에 놓는 조각((cx, cy)는 칸 가운데) ─────────────────────────

def _nut(x, y, r=21):
    pts = [(x + r * math.cos(math.radians(a)), y + r * math.sin(math.radians(a))) for a in range(0, 360, 60)]
    return [poly(pts, fill=PALE, stroke=NAVY, sw=3), circle(x, y, r * 0.42, fill=WHITE, stroke=NAVY, sw=3)]


def pic_grid(cx, cy, w=236, h=112, hot=None):
    """표 하나: 머리 줄과 세 줄 · 세 칸, 칸마다 회색 막대. hot = 짚는 줄(그 줄만 바탕을 깔고 막대를 진하게)."""
    hh = 25
    x, y = cx - w / 2, cy - h / 2
    rh, cw = (h - hh) / 3, w / 3
    o = [rect(x, y, w, h, 10, fill=WHITE, stroke=NAVY, sw=3), rect(x, y, w, hh, 10, fill=LIGHT, stroke=NAVY, sw=3)]
    if hot is not None:
        o.append(rect(x, y + hh + rh * hot, w, rh, 0, fill=PALE, stroke="none", sw=0))
    o += [line(x + cw * k, y + hh, x + cw * k, y + h, stroke=NAVY, sw=2) for k in (1, 2)]
    for i in range(3):
        ry = y + hh + rh * i + rh / 2
        if i:
            o.append(line(x, ry - rh / 2, x + w, ry - rh / 2, stroke=NAVY, sw=2))
        for k in range(3):
            bw = (46, 38, 52, 40, 50, 36, 44, 52, 40)[i * 3 + k] * min(1, w / 236)
            o.append(rect(x + cw * k + 12, ry - 4.5, bw, 9, 4.5, fill=NAVY if i == hot else GREY, stroke="none", sw=0))
    return o


# ───────────────────────── 적용 조각(칩 · 막대로, 따로 적힌 것이 하나로 모이거나 이어지는 것을 그린다) ─────────────────────────

def id_chip(cx, cy, w=52, h=16):
    """식별자 칩: 인스턴스 카드에서 그 하나를 가리키는 값(강조색)."""
    return [rect(cx - w / 2, cy - h / 2, w, h, h / 2, fill=BLUE, stroke=BLUE, sw=2)]


def inst_card(cx, cy, w, h, icon, alias=()):
    """인스턴스 카드: 위에 아이콘, 그 아래 식별자 칩, alias가 있으면 맨 아래에 다른 이름 자리(그 안에 모인 이름 칩들).
    icon = (cx, cy)를 받아 조각을 돌려주는 함수. 돌려주는 값은 (조각, 다른 이름 자리의 왼쪽 가운데 점)."""
    x, y = cx - w / 2, cy - h / 2
    o = [rect(x, y, w, h, 12, fill=WHITE, stroke=NAVY, sw=3)]
    if not alias:
        return o + icon(cx, cy - 13) + id_chip(cx, cy + 27, min(52, w - 18)), None
    o += icon(cx, cy - 27) + id_chip(cx, cy + 6)
    sy = cy + 36
    o.append(rect(x + 9, sy - 13, w - 18, 26, 8, fill=LIGHT, stroke=GREY, sw=2))
    bx = cx - (sum(a[0] for a in alias) + 6 * (len(alias) - 1)) / 2
    for bw, r, fill, edge in alias:
        o.append(rect(bx, sy - 6, bw, 12, r, fill=fill, stroke=edge, sw=2))
        bx += bw + 6
    return o, (x + 9, sy)


def _equip(cx, cy):
    return card_icon("equip", cx, cy, 25 / 62)


def _cooler(cx, cy):
    return card_icon("cooler", cx, cy, 25 / 62)


def _nut_s(cx, cy):
    return _nut(cx, cy, 17)


def pic_gather_rows(cx, cy):
    """대장의 줄 둘(지금 코드 · 옛 코드)이 설비 인스턴스 카드 하나로 모인다: 옛 코드 줄은 그 카드의 다른 이름 자리에 붙는다."""
    card, slot = inst_card(cx + 60, cy, 104, 116, _equip, alias=((46, 6, GREY, GREY),))
    o = list(card)
    for sy, old in ((-36, False), (36, True)):
        x, y = cx - 114, cy + sy
        o += [rect(x, y - 15, 92, 30, 8, fill=WHITE, stroke=NAVY, sw=3),
              rect(x + 9, y - 7, 44, 14, 7, fill=GREY if old else SKY, stroke=GREY if old else NAVY, sw=2.5),
              rect(x + 61, y - 4.5, 22, 9, 4.5, fill=GREY, stroke="none", sw=0)]
    o += arrow([(cx - 18, cy - 36), (cx + 5, cy - 22)], NAVY, 3.5, 11)
    o += arrow([(cx - 18, cy + 36), (slot[0] - 3, slot[1])], NAVY, 3.5, 11)
    return o


def pic_gather_names(cx, cy):
    """꼴이 다른 이름표 둘이 구성 요소 인스턴스 카드 하나로 모이고, 설비 카드가 그 카드를 가진다(오른쪽에서 들어오는 화살표)."""
    o = []
    for sy, bars in ((-27, (30,)), (27, (11, 14))):
        ty = cy + sy
        o.append(rect(cx - 114, ty - 14, 50, 28, 14, fill=WHITE, stroke=NAVY, sw=3))
        bx = cx - 89 - (sum(bars) + 6 * (len(bars) - 1)) / 2
        for bw in bars:
            o.append(rect(bx, ty - 4, bw, 8, 4, fill=NAVY, stroke="none", sw=0))
            bx += bw + 6
        o += arrow([(cx - 60, ty), (cx - 44, cy + sy * 0.55)], NAVY, 3.5, 10)
    o += inst_card(cx - 10, cy, 62, 104, _cooler)[0]
    o += inst_card(cx + 83, cy, 62, 104, _equip)[0]
    o += arrow([(cx + 50, cy), (cx + 24, cy)], NAVY, 3.5, 11)
    return o


def pic_gather_parts(cx, cy):
    """꼴이 다른 품번 칩 셋(하나는 회색 옛 품번)이 부품 인스턴스 카드 하나의 다른 이름 자리로 모인다."""
    card, slot = inst_card(cx + 60, cy, 104, 116, _nut_s,
                           alias=((24, 6, SKY, NAVY), (18, 2.5, WHITE, NAVY), (24, 6, GREY, GREY)))
    o = list(card)
    px = cx - 20
    for sy, (w, r, fill, edge) in zip((-38, 0, 38), ((60, 8.5, SKY, NAVY), (44, 3, WHITE, NAVY), (54, 8.5, GREY, GREY))):
        o.append(rect(cx - 114, cy + sy - 8.5, w, 17, r, fill=fill, stroke=edge, sw=2.5))
        o.append(line(cx - 114 + w + 7, cy + sy, px, slot[1], stroke=NAVY, sw=3))
    o += arrow([(px, slot[1]), (slot[0] - 3, slot[1])], NAVY, 3.5, 11)
    return o


def pic_criteria(cx, cy):
    """닮은 부품 카드 둘 사이에 기준 칸 하나: 같은지 아닌지를 그 칸이 가른다(칸의 네모는 비워 둔다 — 답은 그리지 않는다)."""
    o = []
    for sgn in (-1, 1):
        bx = cx + sgn * 81
        o.append(rect(bx - 33, cy - 54, 66, 108, 12, fill=WHITE, stroke=NAVY, sw=3))
        o += _nut(bx, cy - 16, 19)
        if sgn < 0:
            o.append(rect(bx - 24, cy + 22, 48, 16, 8, fill=SKY, stroke=NAVY, sw=2.5))
        else:
            o.append(rect(bx - 18, cy + 22, 36, 16, 3, fill=WHITE, stroke=NAVY, sw=2.5))
        o += arrow([(bx - sgn * 36, cy), (cx + sgn * 32, cy)], NAVY, 3.5, 10)
    x, y, w, h, hh = cx - 29, cy - 42, 58, 84, 20
    o += [rect(x, y, w, h, 9, fill=WHITE, stroke=NAVY, sw=3), rect(x, y, w, hh, 9, fill=LIGHT, stroke=NAVY, sw=3)]
    for i in range(3):
        ry = y + hh + (h - hh) / 3 * (i + 0.5)
        o += [rect(x + 9, ry - 5.5, 11, 11, 2.5, fill=WHITE, stroke=NAVY, sw=2.5),
              rect(x + 27, ry - 4, (22, 16, 20)[i], 8, 4, fill=GREY, stroke="none", sw=0)]
    return o


def pic_one_row(cx, cy):
    """표 한 장에서 한 줄만 짚는다."""
    return pic_grid(cx, cy, 204, 112, hot=1)


def pic_path(cx, cy):
    """노드 넷(설비 · 구성 요소 · 부품 · 공급사)을 잇는 길 하나. 그 아래 작은 표 넷은 제자리에 있고, 점선으로 올라와 연결만 그래프에 담긴다."""
    xs = [cx + d for d in (-87, -29, 29, 87)]
    ny, ty = cy - 30, cy + 38
    o = []
    for x in xs:
        o += dash_line(x, ny + 20, x, ty - 15, GREY, 3, 5, 4)
        o += [rect(x - 21, ty - 15, 42, 30, 5, fill=WHITE, stroke=GREY, sw=2.5), rect(x - 21, ty - 15, 42, 9, 4, fill=LIGHT, stroke=GREY, sw=2.5),
              line(x - 14, ty + 1, x + 14, ty + 1, stroke=GREY, sw=2.5), line(x - 14, ty + 8, x + 14, ty + 8, stroke=GREY, sw=2.5)]
    o.append(line(xs[0], ny, xs[-1], ny, stroke=NAVY, sw=4.5))
    for x, kind in zip(xs, ("equip", "cooler", "gasket", "supplier")):
        o.append(circle(x, ny, 20, fill=WHITE, stroke=NAVY, sw=3))
        o += card_icon(kind, x, ny, 15 / 62)
    return o


# ───────────────────────── 적용 장 그림 ─────────────────────────

PW, PH = 236, 132     # 그림 칸


def _폭(text, px):
    """라벨 한 줄의 그림 폭 어림(px = 한글 한 글자 폭: 굵은 16pt 25, 작은 13pt 18 — 접히지 않게 넉넉히 잡는다). 빈칸과 가운뎃점은 좁게 센다."""
    return sum(px * (0.3 if c in " ·" else 0.55 if c.isascii() else 1) for c in text)


def scene(name, left, right, icon, ask, ask_desc, need, tw=PW + 61):
    """위에 자료 카드 둘(왼쪽 그림 칸, 오른쪽에 자료 이름과 생기는 일, 아래 띠에 그 일로 엇갈리는 물음), 카드마다 아래로 화살표,
    맨 아래 파란 띠 하나(아이콘 · 물음 덩어리 → 먼저 정할 것). left · right = (그림 함수, 자료 이름, 생기는 일 두 줄, 엇갈리는 물음)."""
    f = Fig2(name)
    W, H, BB = 565, 16 + PH + 16, 58
    for x, (pic, title, desc, q) in zip((297, 903), (left, right)):
        x0 = x - W / 2
        f.add(banded(x0, 0, W, H + BB, H, LIGHT, NAVY, 3))
        f.add([rect(x0 + 16, 16, PW, PH, 16, fill=PALE, stroke="none", sw=0)] + pic(x0 + 16 + PW / 2, 16 + PH / 2))
        tx0 = x0 + 16 + PW
        f.lab(title, desc, (tx0 + x0 + W) / 2, H / 2 - (5 + LH_T + (desc.count(" / ") + 1) * LH_D) / 2, tw)
        f.lab(q, "", x, H + BB / 2 - 19, W - 20)
        f.add(arrow([(x, H + BB + 10), (x, H + BB + 46)]))
    top, bh = H + BB + 56, 96
    cy = top + bh / 2
    f.add([rect(15, top, 1170, bh, 22, fill=PALE, stroke=BLUE, sw=5)])
    w1 = max(_폭(ask, 25), _폭(ask_desc, 18)) + 24
    w2 = _폭(need, 25) + 24
    x = 600 - (72 + 18 + w1 + 84 + w2) / 2
    f.add([circle(x + 36, cy, 36, fill=WHITE, stroke="none", sw=0)] + card_icon(icon, x + 36, cy, 36 / 62))
    x += 72 + 18
    f.lab(ask, ask_desc, x + w1 / 2, cy - (5 + LH_T + LH_D) / 2, w1)
    x += w1
    f.add(arrow([(x + 16, cy), (x + 68, cy)]))
    x += 84
    f.lab(need, "", x + w2 / 2, cy - 19, w2)
    return f.fin(0, top + bh)


def a1():
    return scene("적용_설비등록부.svg",
                 (pic_gather_rows, "설비 대장의 줄", "옛 코드로 남은 줄은 / 그 한 대의 다른 이름이다", "설비는 몇 대인가 → 인스턴스를 센다"),
                 (pic_gather_names, "장치 목록의 이름", "사람마다 달리 부른 이름은 / 구성 요소 하나의 다른 이름이다", "이 장치가 달린 설비는 → 그 구성 요소를 가진 설비"),
                 "sheet", "설비 대장", "종류는 한 번 정의한다", "설비 한 대마다 식별자 붙인 인스턴스 하나", tw=318)


def a2():
    return scene("적용_부품기준.svg",
                 (pic_gather_parts, "옛 품번 · 문서의 품번", "같은 부품의 다른 이름으로 / 정의해 모은다", "지금까지 몇 개 샀나 → 식별자 하나로 모아 센다"),
                 (pic_criteria, "라인별 비슷한 두 부품", "무엇이 같으면 같은 부품인지 / 기준을 정의해 둔다", "같은 부품인가 → 정의한 기준과 근거로 가른다"),
                 "doc", "온톨로지 스키마", "모으기 전에 정의한다", "누가 언제 적었든 같은 기준으로 읽힌다", tw=318)


def a3():
    return scene("적용_표와그래프.svg",
                 (pic_one_row, "한 표 안에서 끝나는 물음", "이 공급사가 매긴 단가 · 납기", "그 표에서 찾는다"),
                 (pic_path, "여러 표를 건너는 물음", "이 부품을 쓰는 설비와 / 살 수 있는 공급사", "그래프에서 관계를 따라 꺼낸다"),
                 "graph", "표는 업무마다 제자리에", "저장소는 목적별로 둔다", "표를 잇는 연결은 그래프에 담는다", tw=318)


FIGS = [a1, a2, a3]


def main():
    show = "--라벨" in sys.argv
    for fn in FIGS:
        f = fn()
        text = f.svg()
        assert "<text" not in text
        (HERE / f.name).write_bytes(text.encode("utf-8"))
        if show:
            print(f"### {f.name} ({len(f.labels)}개)")
            for i, s in enumerate(f.labels, 1):
                print(f"  {i}. {s}")
        else:
            print("wrote", f.name)


if __name__ == "__main__":
    main()
