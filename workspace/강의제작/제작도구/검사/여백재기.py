"""렌더 장 그림(s-NN.png 또는 s-NN.jpg)에서 제목 밑줄 아래 내용의 위 · 아래 · 좌 · 우 여백을 잰다.
장 그림이 하나도 없으면 오류로 멈추고, 밑줄을 못 찾아 재지 못한 장은 끝에 목록으로 알린다(재지 않은 장을 통과로 세지 않는다).

언제: 덱을 렌더한 뒤 「내용이 아래로 밀렸다 · 위에 붙었다 · 한쪽으로 쏠렸다」를 장마다 숫자로 찾을 때.
쓰는 법: <py> 여백재기.py <렌더 폴더> [--기준 -4.7] [--허용 3]
  - 위 · 아래는 제목 밑줄(폭의 절반 넘는 가로줄) 아래부터 잰다. 오른쪽 아래 쪽번호 자리는 뺀다.
  - 이 덱들의 보통 장은 (위 - 아래)가 약 -4.7%다(내용을 살짝 위에 둔다). 그 값에서 --허용(%p)보다
    벗어난 장과, 좌우 차가 --허용보다 큰 장에 「의심」을 찍는다. 의심은 렌더를 열어 눈으로 가른다
    (표 · 패널이 밑줄 바로 아래에서 시작하는 꼴, 문항 장의 왼쪽 정렬 글은 의도된 꼴이다).
자가시험: --자가시험 — 가운데 둔 상자와 아래로 민 상자를 그려 뒤쪽만 의심으로 잡는지 본다.
"""
import argparse, glob, os, sys, tempfile
import numpy as np
from PIL import Image, ImageDraw


def 재기(path):
    a = np.asarray(Image.open(path).convert('L')).astype(int)
    H, W = a.shape
    bg = np.median(a[:, :5])
    ink = np.abs(a - bg) > 25
    ink[int(H * 0.93):, int(W * 0.9):] = False
    rows = ink.sum(1)
    rule = None
    for y in range(int(H * 0.3)):
        if rows[y] > W * 0.5:
            rule = y
    if rule is None:
        return None
    sub = ink[rule + 3:, :]
    r = np.where(sub.sum(1) > 0)[0]
    c = np.where(sub.sum(0) > 0)[0]
    if len(r) == 0:
        return None
    top, bot = r[0] / H * 100, (sub.shape[0] - 1 - r[-1]) / H * 100
    L, R = c[0] / W * 100, (W - 1 - c[-1]) / W * 100
    return top, bot, L, R


def 장그림(폴더):
    """s-NN.png · s-NN.jpg(같은 장이 둘이면 png). 하나도 없으면 오류 — 렌더 폴더가 아니거나 이름이 다르다."""
    고른 = {}
    for f in sorted(glob.glob(os.path.join(폴더, 's-*.jpg'))) + sorted(glob.glob(os.path.join(폴더, 's-*.png'))):
        고른[os.path.splitext(os.path.basename(f))[0]] = f
    if not 고른:
        raise SystemExit(f'{폴더}: 장 그림 s-NN.png · s-NN.jpg가 없다 — 덱 PDF를 장마다 s-NN으로 뽑은 폴더를 준다')
    return [고른[k] for k in sorted(고른)]


def 판정(폴더, 기준, 허용, 못잰=None):
    나온 = []
    for f in 장그림(폴더):
        m = 재기(f)
        if m is None:
            if 못잰 is not None:
                못잰.append(os.path.basename(f))
            continue
        top, bot, L, R = m
        세로 = (top - bot) - 기준
        가로 = L - R
        의심 = []
        if 세로 > 허용: 의심.append('아래로 밀림')
        if 세로 < -허용: 의심.append('위로 붙음')
        if abs(가로) > 허용: 의심.append('왼쪽 쏠림' if 가로 < 0 else '오른쪽 쏠림')
        나온.append((os.path.basename(f), top, bot, L, R, 세로, 가로, 의심))
    return 나온


def 자가시험():
    d = tempfile.mkdtemp()
    for name, (y0, y1) in (('s-01.png', (120, 410)), ('s-02.png', (170, 440))):
        im = Image.new('L', (800, 450), 255); g = ImageDraw.Draw(im)
        g.rectangle([30, 90, 770, 91], fill=0)
        g.rectangle([250, y0, 550, y1], fill=0)
        im.save(os.path.join(d, name))
    Image.new('L', (800, 450), 255).save(os.path.join(d, 's-03.jpg'))   # 밑줄 없는 장(jpg) — 재지 못한 장으로 나와야 한다
    못잰 = []
    r = {x[0]: x[7] for x in 판정(d, -4.7, 3, 못잰)}
    assert r['s-01.png'] == [], r
    assert '아래로 밀림' in r['s-02.png'], r
    assert 못잰 == ['s-03.jpg'], 못잰
    빈 = tempfile.mkdtemp()
    Image.new('L', (800, 450), 255).save(os.path.join(빈, '덱-01.png'))  # 이름이 s-NN이 아닌 폴더 — 빈 성공 대신 오류
    try:
        판정(빈, -4.7, 3)
    except SystemExit:
        pass
    else:
        raise AssertionError('장 그림이 없는 폴더를 통과시켰다')
    print('자가시험 통과')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('폴더', nargs='?')
    ap.add_argument('--기준', type=float, default=-4.7)
    ap.add_argument('--허용', type=float, default=3.0)
    ap.add_argument('--자가시험', action='store_true')
    a = ap.parse_args()
    if a.자가시험:
        자가시험(); sys.exit(0)
    if not a.폴더:
        sys.exit('렌더 폴더를 주세요')
    n, 못잰 = 0, []
    나온 = 판정(a.폴더, a.기준, a.허용, 못잰)
    for f, top, bot, L, R, 세로, 가로, 의심 in 나온:
        표 = ' · '.join(의심)
        if 의심: n += 1
        print(f"{f} 위 {top:4.1f} 아래 {bot:4.1f} 좌 {L:4.1f} 우 {R:4.1f} | 세로 {세로:+5.1f} 가로 {가로:+5.1f} {표}")
    print(f'잰 장 {len(나온)} · 의심 {n}장')
    if 못잰:
        print(f'재지 못한 장 {len(못잰)}(제목 밑줄 없음 — 표지 · 간지가 아니면 렌더를 연다): {" ".join(못잰)}')
