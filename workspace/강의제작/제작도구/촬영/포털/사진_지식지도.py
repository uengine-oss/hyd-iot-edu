"""2회차 지식 지도 탐색(포털) 학생 가이드 사진을 두 과정 게시본 영상의 프레임에서 뽑고 빨간 표시를 그린다. 사진의 영상 시각 · 자르기 · 표시 좌표는 이 파일 한 곳이다.

PYTHONUTF8=1 .venv314/Scripts/python.exe workspace/강의제작/제작도구/촬영/포털/사진_지식지도.py --work 작업/<작업>/영상프레임 [--course 통합반|실전반]
    → 과정마다 `02회차/랩/02일차_실습2_지식지도탐색/images/<이름>.jpg`와 `실습시작/capture-provenance.json`의 그 사진 항목.
- 원본은 영상에서 뽑은 프레임(`--work`, git 밖)이다. 표시는 늘 그 원본에 다시 그린다(표시 위에 겹쳐 그리지 않는다).
- 시각은 게시본 영상(통합반 900초 — 2026-11-07 m05-610 소리만 바꾼 판, 화면은 2026-11-06 녹화와 같다 · 실전반 447초)의 시각이다. 영상 판본이 바뀌면 시각을 다시 재고 이 파일을 고친다(영상 해시가 근거에 남는다).
- 설비 고르기 칸의 펼친 목록은 운영체제 창이라 녹화에 없다. 그래서 칸의 위치와 고른 뒤의 값만 표시한다.
- 사진의 설명 글은 가이드 생성기(`실습시작/build_common.py`의 지식 지도 부분)가 가진다.
"""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess

import imageio_ffmpeg
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
VIDEOS = {'통합반': 'workspace/강의제작/산출물/영상/통합반/통합반_02회차_05_실습_지식지도탐색.mp4',
          '실전반': 'workspace/강의제작/산출물/영상/실전반/실전반_02회차_06_실습_지식지도탐색.mp4'}
LAB = 'workspace/강의제작/산출물/{}/실습/02회차/랩/02일차_실습2_지식지도탐색/images'
PROVENANCE = HERE.parent.parent/'실습시작/capture-provenance.json'
RED, WIDTH = '#d32f2f', 4

# 표시 규칙(P-8): 선 굵기 WIDTH, 선의 안팎 GAP px 안에 글자 화소가 없고, 한 사진의 상자끼리는 GAP px 넘게 떨어진다.
# 글자 화소: 밝기 INK 미만인 화소(흐린 노드의 회색 글자까지 센다)에서 곧은 선(가로나 세로로 LINE px 넘게 이어진 화소와 그 둘레 LINE_NEAR px)을 빼고,
# 남은 화소를 8방향으로 이은 덩어리 가운데 높이가 GLYPH px 이하인 것. 노드 상자 · 표 줄 · 칸 테두리(곧은 선)와 지도의 곡선 연결선(높이가 큰 덩어리)은 글자가 아니다.
# 마우스 포인터는 글자 크기 덩어리라 사진마다 포인터 끝(x, y)을 적고, 그 자리(오른쪽 아래로 28×40)는 세지 않는다.
INK, GAP, LINE, LINE_NEAR, GLYPH = 225, 6, 30, 3, 40

# 과정 → [(이름, 영상 초, 가이드 절, 빨간 표시들, 자르기(없으면 전체), 마우스 포인터 끝(x, y) 또는 None)]
PHOTOS = {
    '통합반': [
        ('map-01-open', 66, '지식 지도 열고 읽는 법 익히기', [[12, 819, 171, 867], [409, 191, 613, 248], [409, 378, 1186, 421]], None, (1476, 234)),
        ('map-02-layers', 140, '지식 지도 열고 읽는 법 익히기', [[424, 325, 583, 368], [603, 325, 756, 367], [1330, 325, 1593, 368], [1612, 324, 1796, 371], [421, 716, 576, 791]], None, (560, 750)),
        ('map-03-search', 172, '설비를 골라 상세 칸 읽기', [[1503, 181, 1792, 255], [427, 516, 822, 563]], None, (1750, 230)),
        ('map-04-asset', 240, '설비를 골라 상세 칸 읽기', [[446, 457, 692, 540], [597, 585, 680, 624], [1145, 480, 1399, 743], [1145, 754, 1480, 909]], None, (1128, 790)),
        ('map-05-cooler', 372, '오일 쿨러에서 관계 방향 읽기', [[445, 603, 571, 684], [445, 690, 818, 733], [1145, 625, 1427, 782], [1115, 792, 1463, 936]], None, (1330, 740)),
        ('map-06-sensor', 400, '센서와 상태 변수 구별하기', [[446, 639, 571, 721], [446, 728, 923, 847], [1145, 661, 1369, 744], [1145, 755, 1369, 910]], None, (430, 766)),
        ('map-07-statevar', 506, '센서와 상태 변수 구별하기', [[446, 385, 547, 467], [445, 474, 870, 664], [1145, 408, 1441, 526], [1145, 537, 1538, 911]], None, (1130, 760)),
        ('map-08-efficiency', 544, '센서와 상태 변수 구별하기', [[446, 639, 646, 721], [445, 728, 936, 847], [1145, 661, 1415, 744], [1145, 755, 1415, 910]], None, (430, 760)),
        ('map-09-core', 606, '교체 부품과 여러 센서 찾기', [[445, 640, 571, 721], [446, 728, 838, 771], [1145, 661, 1426, 818]], None, (1130, 810)),
        ('map-10-pump-search', 620, '교체 부품과 여러 센서 찾기', [[1503, 133, 1792, 207], [426, 463, 830, 517]], None, (1750, 180)),
        ('map-11-pump', 630, '교체 부품과 여러 센서 찾기', [[445, 566, 591, 650], [1145, 589, 1422, 780], [1145, 791, 1488, 909]], None, (1130, 700)),
        ('map-12-seal', 662, '교체 부품과 여러 센서 찾기', [[446, 567, 636, 648], [446, 656, 838, 698], [1145, 589, 1424, 745]], None, (430, 690)),
        ('map-13-hyd02', 688, '설비를 바꿔 같은 노드 보기', [[409, 143, 613, 200], [1503, 132, 1791, 208], [426, 468, 818, 517]], None, (1652, 166)),
        ('map-14-cooler-hyd02', 716, '설비를 바꿔 같은 노드 보기', [[445, 603, 571, 684], [1145, 625, 1427, 782], [1147, 792, 1463, 910]], None, (1130, 870)),
        ('map-15-comp-cooler', 770, 'Cypher 예제 그래프와 비교하기', [[1504, 132, 1790, 208], [427, 468, 829, 517]], None, (812, 490)),
        ('map-16-tank', 820, 'Cypher 예제 그래프와 비교하기', [[446, 711, 596, 793], [1145, 733, 1454, 816], [1145, 828, 1463, 909]], None, (820, 556)),
        ('map-17-standby', 862, 'Cypher 예제 그래프와 비교하기', [[445, 711, 613, 795], [1145, 733, 1415, 816], [1145, 828, 1463, 909]], None, (1130, 810)),
    ],
    '실전반': [
        ('map-01-open', 36, '지식 지도 열기', [[12, 819, 171, 867], [409, 191, 613, 248], [967, 710, 1122, 784]], None, (980, 750)),
        ('map-02-search', 50, '설비에서 주 펌프와 센서로 내려가기', [[1520, 196, 1653, 240], [442, 481, 707, 562]], None, (697, 540)),
        ('map-03-asset', 62, '설비에서 주 펌프와 센서로 내려가기', [[446, 458, 692, 540], [597, 585, 680, 624], [1145, 480, 1399, 743]], None, (430, 620)),
        ('map-04-pump', 80, '설비에서 주 펌프와 센서로 내려가기', [[445, 566, 591, 650], [1145, 591, 1422, 780], [1147, 791, 1488, 909]], None, (1130, 870)),
        ('map-05-sensor', 100, '설비에서 주 펌프와 센서로 내려가기', [[446, 639, 627, 721], [446, 728, 923, 847], [1145, 661, 1414, 744], [1145, 755, 1415, 910]], None, (430, 766)),
        ('map-06-seal', 120, '씰 키트의 식별정보와 관계 읽기', [[445, 640, 635, 721], [446, 728, 838, 771], [1145, 661, 1424, 818], [1145, 828, 1534, 981]], None, (430, 766)),
        ('map-07-hyd02', 182, '씰 키트를 쓰는 설비 찾기', [[409, 148, 577, 192], [444, 700, 707, 746]], None, (583, 168)),
        ('map-08-pump-hyd02', 188, '씰 키트를 쓰는 설비 찾기', [[445, 566, 591, 650], [1145, 590, 1422, 780], [1147, 791, 1488, 909]], None, (1134, 870)),
        ('map-09-pump-hyd03', 214, '씰 키트를 쓰는 설비 찾기', [[445, 566, 591, 650], [1145, 591, 1422, 780], [1145, 791, 1488, 909]], None, (1125, 663)),
        ('map-10-order', 262, '발주 방법에서 근거 문서와 규칙까지 따라가기', [[1145, 237, 1806, 309], [1137, 431, 1831, 844]], None, (1124, 738)),
        ('map-11-step', 272, '발주 방법에서 근거 문서와 규칙까지 따라가기', [[446, 366, 1112, 487], [1145, 388, 1389, 471]], None, (1770, 276)),
        ('map-12-section', 286, '발주 방법에서 근거 문서와 규칙까지 따라가기', [[446, 368, 573, 448], [446, 455, 691, 495], [1146, 390, 1562, 472]], None, (1130, 466)),
        ('map-13-document', 296, '발주 방법에서 근거 문서와 규칙까지 따라가기', [[446, 479, 830, 562], [1145, 502, 1500, 801]], None, (1530, 466)),
        ('map-14-avl', 304, '발주 방법에서 근거 문서와 규칙까지 따라가기', [[446, 479, 656, 560], [1145, 594, 1831, 704]], None, (1400, 794)),
        ('map-15-suppliers', 332, '연결과 확보를 구별하기', [[1145, 482, 1426, 635]], None, (1395, 625)),
        ('map-16-ctrading', 346, '연결과 확보를 구별하기', [[445, 742, 882, 906], [1145, 764, 1396, 880]], None, (430, 864)),
        ('map-17-boem', 372, '연결과 확보를 구별하기', [[445, 742, 898, 906], [1145, 764, 1394, 917]], None, (430, 900)),
        ('map-18-stock-search', 398, '연결과 확보를 구별하기', [[1503, 133, 1792, 208], [967, 463, 1239, 518]], None, (1230, 506)),
        ('map-19-stock', 420, '연결과 확보를 구별하기', [[445, 544, 913, 624], [1146, 566, 1363, 646], [1145, 660, 1812, 907]], None, (1130, 870)),
    ],
}


def text_pixels(gray):
    """글자 화소 배열(bool). gray는 흑백 numpy 배열."""
    import numpy as np
    ink = gray < INK
    line = np.zeros_like(ink)
    for axis in (0, 1):
        a = ink if axis == 1 else ink.T
        s = np.cumsum(np.pad(a, ((0, 0), (1, 0))).astype(np.int32), axis=1)
        full = (s[:, LINE:] - s[:, :-LINE]) == LINE                 # 그 자리에서 시작하는 LINE칸이 모두 잉크
        start = np.pad(full, ((0, 0), (0, LINE - 1))).astype(np.int32)
        cover = np.cumsum(start, axis=1)
        cover[:, LINE:] -= cover[:, :-LINE].copy()
        m = cover > 0
        line |= m if axis == 1 else m.T
    near = line.copy()
    for dy in range(-LINE_NEAR, LINE_NEAR + 1):
        for dx in range(-LINE_NEAR, LINE_NEAR + 1):
            near |= np.roll(np.roll(line, dy, 0), dx, 1)
    rest = ink & ~near
    # 줄마다 이어진 구간(run)을 만들고, 위 줄 구간과 8방향으로 닿으면 한 덩어리로 묶는다.
    parent = []
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    runs, prev = [], []
    for y in range(rest.shape[0]):
        row = rest[y]
        if not row.any():
            prev = []
            continue
        d = np.diff(np.concatenate(([0], row.view(np.int8), [0])))
        starts, ends = np.flatnonzero(d == 1), np.flatnonzero(d == -1)
        cur = []
        j = 0
        for x0, x1 in zip(starts.tolist(), ends.tolist()):
            k = len(parent)
            parent.append(k)
            runs.append((y, x0, x1, k))
            while j < len(prev) and prev[j][1] < x0:
                j += 1
            t = j
            while t < len(prev) and prev[t][0] <= x1:
                a, b = find(prev[t][2]), find(k)
                if a != b:
                    parent[b] = a
                t += 1
            cur.append((x0, x1, k))
        prev = cur
    top, bottom = {}, {}
    for y, x0, x1, k in runs:
        r = find(k)
        top[r] = min(top.get(r, y), y)
        bottom[r] = max(bottom.get(r, y), y)
    text = np.zeros_like(ink)
    for y, x0, x1, k in runs:
        r = find(k)
        if bottom[r] - top[r] + 1 <= GLYPH:
            text[y, x0:x1] = True
    return text


def mark_problems(text, rects, cursor, ink=None):
    """표시 규칙 위반 목록. text는 text_pixels의 결과(포인터 자리는 여기서 뺀다).
    ink(밝기 INK 미만 배열)를 주면 「상자 안이 비었는지」를 잉크로 본다 — 이미 누른 노드처럼 글자가 흐려 글자로 잡히지 않는 노드도 테두리로 대상이 있음을 안다."""
    text = text.copy()
    if cursor:
        x, y = cursor
        text[max(0, y-4):y+40, max(0, x-4):x+28] = False
    h, w = text.shape
    def count(x0, y0, x1, y1):
        return int(text[max(0, y0):min(h, y1), max(0, x0):min(w, x1)].sum())
    problems = []
    for r in rects:
        x0, y0, x1, y1 = r
        sides = {'위': count(x0-GAP, y0-GAP, x1+GAP, y0+WIDTH+GAP), '아래': count(x0-GAP, y1-WIDTH-GAP, x1+GAP, y1+GAP),
                 '왼쪽': count(x0-GAP, y0-GAP, x0+WIDTH+GAP, y1+GAP), '오른쪽': count(x1-WIDTH-GAP, y0-GAP, x1+GAP, y1+GAP)}
        problems += [f'{r} {side} 선 {GAP}px 안 글자 화소 {n}' for side, n in sides.items() if n]
        inside = (ink if ink is not None else text)[max(0, y0+WIDTH):y1-WIDTH, max(0, x0+WIDTH):x1-WIDTH]
        if not inside.any():
            problems.append(f'{r} 안이 비어 있음')
    for i, a in enumerate(rects):
        for b in rects[i+1:]:
            if a[0]-GAP < b[2] and b[0]-GAP < a[2] and a[1]-GAP < b[3] and b[1]-GAP < a[3]:
                problems.append(f'{a}와 {b}가 {GAP}px 안으로 붙거나 겹침')
    return problems


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def frame_path(work, video, seconds):
    return work/f'{sha(ROOT/video)[:12]}-{seconds}.png'


def extract(work, video, seconds):
    frame = frame_path(work, video, seconds)
    if not frame.exists():
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-hide_banner', '-loglevel', 'error', '-ss', str(seconds),
                        '-i', str(ROOT/video), '-frames:v', '1', str(frame)], check=True)
    return frame


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--course', choices=list(VIDEOS), help='한 과정만 다시 만든다(다른 과정 사진 · 근거는 그대로 둔다)')
    args = parser.parse_args()
    work = args.work.resolve()
    if not work.is_relative_to((ROOT/'작업').resolve()):
        parser.error('원본 프레임은 저장소 작업 폴더(작업/…)에 둡니다.')
    work.mkdir(parents=True, exist_ok=True)
    import numpy as np
    chosen = {c: p for c, p in PHOTOS.items() if args.course in (None, c)}
    frames, failures = {}, []
    for course, photos in chosen.items():   # 먼저 모든 표시를 검사하고, 하나라도 어기면 아무것도 쓰지 않는다
        for name, seconds, section, rects, crop, cursor in photos:
            frame = extract(work, VIDEOS[course], seconds)
            frames[course, name] = frame
            gray = np.asarray(Image.open(frame).convert('L')).astype(int)
            failures += [f'{course} {name}: {p}' for p in mark_problems(text_pixels(gray), rects, cursor, gray < INK)]
    if failures:
        raise SystemExit('표시 규칙 위반 — 사진을 쓰지 않았다:\n' + '\n'.join(failures))
    records, targets = [], set()
    for course, photos in chosen.items():
        video, lab = VIDEOS[course], LAB.format(course)
        video_sha = sha(ROOT/video)
        for name, seconds, section, rects, crop, cursor in photos:
            frame = frames[course, name]
            image = Image.open(frame).convert('RGB')
            draw = ImageDraw.Draw(image)
            for rect in rects:
                draw.rectangle(rect, outline=RED, width=WIDTH)
            if crop:
                image = image.crop(crop)
            target = ROOT/lab/f'{name}.jpg'
            image.save(target, quality=92)
            targets.add(f'{lab}/{name}.jpg')
            records.append({'target': f'{lab}/{name}.jpg', 'kind': '학생 실습 화면', 'section': section,
                            'source': video, 'source_sha256': video_sha, 'seconds': seconds, 'raw_frame_sha256': sha(frame),
                            'crop_box': crop, 'rectangles': rects, 'pointer': list(cursor) if cursor else None, 'sha256': sha(target)})
        stale = {p.name for p in (ROOT/lab).glob('*.jpg')} - {n+'.jpg' for n, *_ in photos}
        if stale:
            raise SystemExit(f'{lab}: 근거에 없는 사진 {sorted(stale)} — 이 파일에 넣거나 지운다(옛 판은 git 이력에 있다)')
    old = json.loads(PROVENANCE.read_text(encoding='utf-8'))
    keep = [x for x in old if x['target'] not in targets]
    PROVENANCE.write_text(json.dumps(keep + records, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(sum(len(p) for p in chosen.values()), '사진. 눈으로 본 뒤 가이드를 만든다.')


if __name__ == '__main__':
    main()
