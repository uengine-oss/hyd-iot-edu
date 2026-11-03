"""스키마와 인스턴스의 경계, 잘못 이어진 연결의 수정 전후. 글자는 덱 MD의 요소로 얹는다."""
from pathlib import Path
from 만들기_삽화 import (BLUE, GREY, NAVY, PALE, SKY, WHITE, ON, arrow, check_badge, circle, doc, g, line, rect, svg)

HERE = Path(__file__).resolve().parent


def node(x, y, r=24):
    return [circle(x, y, r, fill=SKY, stroke=NAVY)]


def steps(x, y, n, gap=46, r=12):
    """단계 묶음: 작은 원 n개를 한 줄로 잇는다. (왼쪽 끝, 오른쪽 끝)도 돌려준다."""
    x0 = x - gap * (n - 1) / 2
    xs = [x0 + k * gap for k in range(n)]
    o = [line(a + r, y, b - r, y, stroke=NAVY, sw=3) for a, b in zip(xs, xs[1:])]
    o += [circle(a, y, r, fill=PALE, stroke=NAVY, sw=3) for a in xs]
    return o, xs[0] - r, xs[-1] + r


def cross(x, y, r=19):
    d = r * 0.5
    return [circle(x, y, r, fill=WHITE, stroke=NAVY), line(x - d, y - d, x + d, y + d, stroke=NAVY, sw=4), line(x - d, y + d, x + d, y - d, stroke=NAVY, sw=4)]


def page(x, y):
    return g(x, y, 0.62, doc(0, 0, ON))


def value_box(x, y, w=224, h=106):
    return [rect(x - w / 2, y - h / 2, w, h, 12, fill=WHITE, stroke=NAVY, sw=3)]


def schema_instance():
    """위 띠: 세 종류와 두 관계. 아래 띠: 같은 종류에 속한 두 작업의 실제 연결."""
    cols = (330, 680, 1030)
    o = [rect(16, 16, 1168, 142, 16, fill=PALE, stroke=GREY, sw=2.5), rect(16, 174, 1168, 332, 16, fill=WHITE, stroke=GREY, sw=2.5)]
    y = 87
    for cx in cols:
        o.append(rect(cx - 105, y - 39, 210, 78, 12, fill=WHITE, stroke=NAVY))
    o.append(arrow([(cols[0] + 107, y), (cols[1] - 107, y)], BLUE))
    o.append(arrow([(cols[1] + 107, y), (cols[2] - 107, y)], BLUE))
    for y, n in ((238, 3), (396, 4)):
        o += node(cols[0], y)
        st, a, b = steps(cols[1], y, n)
        o += st
        o.append(arrow([(cols[0] + 26, y), (a - 4, y)], NAVY, sw=3.5))
        o.append(arrow([(b + 4, y), (cols[2] - 30, y)], NAVY, sw=3.5))
        o += page(cols[2], y)
    return svg(o)


def fix_link():
    """위 띠: 세척 단계가 벨트 교체 절로 이어진 연결. 아래 띠: 고친 연결과 그대로 둔 벨트 교체의 연결."""
    xn, xs, xm, xd, xv = 262, 500, 670, 790, 1040
    o = [rect(16, 16, 1168, 168, 16, fill=WHITE, stroke=GREY, sw=2.5), rect(16, 198, 1168, 308, 16, fill=PALE, stroke=GREY, sw=2.5)]
    for y, n, kind in ((78, 3, 'x'), (252, 3, 'ok'), (406, 4, None)):
        o += node(xn, y)
        st, a, b = steps(xs, y, n)
        o += st
        o.append(arrow([(xn + 26, y), (a - 4, y)], NAVY, sw=3.5))
        o.append(arrow([(b + 4, y), (xd - 30, y)], BLUE if kind == 'ok' else NAVY, sw=3.5))
        o += page(xd, y)
        if kind == 'x':
            o += cross(xm, y)
        elif kind == 'ok':
            o += g(xm, y, 1.0, check_badge(0, 0, ON))
        o += value_box(xv, y + 14)
    return svg(o)


if __name__ == '__main__':
    (HERE / '스키마와_인스턴스.svg').write_text(schema_instance(), encoding='utf8')
    (HERE / '연결_고치기전후.svg').write_text(fix_link(), encoding='utf8')
