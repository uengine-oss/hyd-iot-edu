"""2회차 지식 지도 탐색(포털) 학생 가이드 사진을 게시본 영상의 프레임에서 뽑고 빨간 표시를 그린다. 사진의 영상 시각 · 자르기 · 표시 좌표는 이 파일 한 곳이다.

PYTHONUTF8=1 .venv314/Scripts/python.exe workspace/강의제작/제작도구/촬영/포털/사진_지식지도.py --work 작업/<작업>/영상프레임 [--course 통합반] [--영상 <mp4>]
    → `통합반/실습/02회차/랩/02일차_실습2_지식지도탐색/images/<이름>.jpg`와 `실습시작/capture-provenance.json`의 그 사진 항목.
- 원본은 영상에서 뽑은 프레임(`--work`, git 밖)이다. 표시는 늘 그 원본에 다시 그린다(표시 위에 겹쳐 그리지 않는다).
- 영상은 VIDEOS의 정본 자리가 기본이다. 정본 자리에 아직 없는 같은 판(예: 클라우드에서 합성해 Release에 올리기 전의 mp4)은 `--영상`으로 주고 `--course`로 그 과정만 만든다. 근거에는 실제로 읽은 영상의 경로와 sha256이 남는다.
- 시각은 그 영상의 시각이다. 통합반은 48큐 대본으로 포털 main ca7fdee8 화면을 찍은 판 05-지식지도-새판4(끝을 1.6초 늘린 997.4초, 합성기록 `합성기록/05-지식지도-새판4.json` — 정본 자리에 올리기 전에는 `--영상 작업/촬영/포털/05-지식지도-새판4/05-지식지도-새판4_끝.mp4`)이다. 실전반은 같은 가이드 · 영상을 쓴다(공통 C-4). 영상 판본이 바뀌면 시각을 다시 재고 이 파일을 고친다(영상 해시가 근거에 남는다).
- 새 영상에는 강사가 짚는 빨간 밑줄 · 띠 · 테두리가 합성돼 있어 가이드의 빨간 표시와 섞인다. 그래서 통합반 사진은 큐와 큐 사이(앞 큐의 강조가 지워진 뒤, 다음 큐가 시작하기 전)나 누른 직후의 프레임에서 뽑는다. 시각은 합성기록의 `cue_timeline`(말 · 조작 · 누른 시각)으로 고르고, 뽑은 프레임에 강조가 남지 않았는지 눈으로 본다.
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
VIDEOS = {'통합반': 'workspace/강의제작/산출물/영상/통합반/통합반_02회차_05_실습_지식지도탐색.mp4'}
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
    '통합반': [   # 영상 05-지식지도-새판2 — 시각 옆 주석은 그 프레임의 자리(합성기록 cue_timeline)
        ('m05-01-open', 33.0, '지식 지도 열고 설비 고르기', [[13, 146, 106, 190], [51, 242, 151, 285]], None, (309, 266)),   # k0102 뒤, 지도가 다 그려진 화면
        ('m05-02-search', 113.87, '지식 지도 열고 설비 고르기', [[466, 199, 577, 241], [1056, 582, 1239, 700]], None, (657, 215)),   # k0203 「유압 파워팩」을 넣은 뒤 Enter 전
        ('m05-03-asset', 117.87, '설비 노드 읽기: 클래스 · 이름 · 식별자', [[1421, 206, 1538, 245], [1421, 290, 1572, 329], [1426, 740, 1886, 781]], None, (657, 217)),   # k0203 Enter 뒤 · k0301 전
        ('m05-04-direction', 218.48, '관계의 방향 읽고 오일 쿨러로 건너가기', [[1421, 411, 1552, 450], [1423, 558, 1549, 597], [1731, 498, 1846, 548]], None, (1575, 300)),   # k0304 뒤 · k0401 전(설비 판 그대로)
        ('m05-05-cooler', 318.9, '관계의 방향 읽고 오일 쿨러로 건너가기', [[1421, 206, 1574, 245], [1421, 290, 1561, 329], [1421, 371, 1722, 415], [1423, 500, 1762, 588], [1423, 597, 1568, 686], [1423, 693, 1886, 786]], None, (1826, 535)),   # k0403에서 오일 쿨러를 누른 뒤 · k0501 전
        ('m05-06-sensor', 424.97, '센서의 속성과 관계 읽기', [[1421, 290, 1518, 327], [1421, 371, 1680, 497], [1423, 679, 1886, 768], [1423, 776, 1886, 864]], None, (1540, 570)),   # k0505에서 유온 센서를 누른 뒤 · k0602 전
        ('m05-07-symptom', 545.66, '증상에서 부품까지 따라가기', [[1421, 206, 1574, 245], [1423, 500, 1640, 588]], None, (1534, 841)),   # k0604에서 유온 상승을 누른 뒤 · k0701 전
        ('m05-08-failure', 577.7, '증상에서 부품까지 따라가기', [[1423, 705, 1560, 792], [1423, 800, 1886, 839], [1439, 893, 1576, 935]], None, (1610, 580)),   # k0701에서 쿨러 냉각 성능 상실을 누른 뒤 · k0702 전
        ('m05-09-cause', 633.81, '증상에서 부품까지 따라가기', [[1421, 206, 1573, 245], [1423, 882, 1592, 966]], None, (1555, 917)),   # k0705에서 쿨러 핀 오염을 누른 뒤 · k0704 전
        ('m05-10-part', 647.4, '증상에서 부품까지 따라가기', [[1421, 206, 1539, 245], [1421, 371, 1726, 411], [1423, 935, 1886, 1023]], None, (1530, 461)),   # k0801 첫머리, 첫 강조 전(누른 직후에는 포인터가 ← 구성 요소 1의 숫자를 가린다)
        ('m05-11-before', 731.13, '다른 설비의 지도에서 같은 쿨러 찾기', [[1421, 290, 1561, 329], [1660, 96, 1820, 162]], None, (1540, 1020)),   # k0803에서 오일 쿨러로 돌아온 뒤 · k0901 전
        ('m05-12-hyd02', 797.64, '다른 설비의 지도에서 같은 쿨러 찾기', [[1656, 92, 1824, 166], [466, 199, 577, 241]], None, (1784, 133)),   # k0903에서 HYD-02를 고르고 판이 닫힌 뒤 · k0909 전
        ('m05-13-find', 821.64, '다른 설비의 지도에서 같은 쿨러 찾기', [[466, 195, 600, 245]], None, (630, 221)),   # k0904에서 comp:cooler를 넣은 뒤 · k0905 Enter 전
        ('m05-14-same', 823.78, '다른 설비의 지도에서 같은 쿨러 찾기', [[1421, 290, 1561, 329], [1421, 371, 1722, 415], [1423, 500, 1762, 686], [1423, 693, 1886, 786], [1656, 92, 1824, 166]], None, (640, 232)),   # k0905 Enter 뒤 · k0906 전
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


def video_of(course, given):
    """과정의 영상 경로(저장소 기준). --영상이 있으면 그 파일, 없으면 VIDEOS의 정본 자리."""
    if given is None:
        return VIDEOS[course]
    path = given.resolve()
    if not path.is_file():
        raise SystemExit(f'{given}: 영상 파일이 없다')
    return path.relative_to(ROOT.resolve()).as_posix() if path.is_relative_to(ROOT.resolve()) else str(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--course', choices=list(VIDEOS), help='한 과정만 다시 만든다(다른 과정 사진 · 근거는 그대로 둔다)')
    parser.add_argument('--영상', dest='video', type=Path, help='정본 자리 대신 읽을 같은 판 mp4(--course와 함께 준다)')
    args = parser.parse_args()
    if args.video and not args.course:
        parser.error('--영상은 한 과정의 영상이므로 --course와 함께 준다.')
    work = args.work.resolve()
    if not work.is_relative_to((ROOT/'작업').resolve()):
        parser.error('원본 프레임은 저장소 작업 폴더(작업/…)에 둡니다.')
    work.mkdir(parents=True, exist_ok=True)
    import numpy as np
    chosen = {c: p for c, p in PHOTOS.items() if args.course in (None, c)}
    frames, failures = {}, []
    for course, photos in chosen.items():   # 먼저 모든 표시를 검사하고, 하나라도 어기면 아무것도 쓰지 않는다
        for name, seconds, section, rects, crop, cursor in photos:
            frame = extract(work, video_of(course, args.video), seconds)
            frames[course, name] = frame
            gray = np.asarray(Image.open(frame).convert('L')).astype(int)
            failures += [f'{course} {name}: {p}' for p in mark_problems(text_pixels(gray), rects, cursor, gray < INK)]
    if failures:
        raise SystemExit('표시 규칙 위반 — 사진을 쓰지 않았다:\n' + '\n'.join(failures))
    records, targets = [], set()
    for course, photos in chosen.items():
        video, lab = video_of(course, args.video), LAB.format(course)
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
    labs = tuple(LAB.format(c) + '/' for c in chosen)   # 다시 만든 과정의 옛 사진 항목은 이름이 바뀌었어도 모두 뺀다
    keep = [x for x in old if x['target'] not in targets and not x['target'].startswith(labs)]
    PROVENANCE.write_text(json.dumps(keep + records, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(sum(len(p) for p in chosen.values()), '사진. 눈으로 본 뒤 가이드를 만든다.')


if __name__ == '__main__':
    main()
