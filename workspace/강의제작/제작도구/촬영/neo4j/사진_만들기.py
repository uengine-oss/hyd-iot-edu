"""2회차 관계 조회(Neo4j Browser) 학생 가이드 사진을 게시본 영상의 프레임에서 뽑고 빨간 표시를 그린다. 사진의 영상 시각 · 자르기 · 표시 좌표는 이 파일 한 곳이다.

PYTHONUTF8=1 .venv314/Scripts/python.exe workspace/강의제작/제작도구/촬영/neo4j/사진_만들기.py --work 작업/<작업>/영상프레임
    → 두 과정 `02회차/랩/02일차_실습1_관계조회/images/<이름>.jpg`(같은 바이트)와 `실습시작/capture-provenance.json`의 그 사진 항목.
- 원본은 영상에서 뽑은 프레임(`--work`, git 밖)이다. 표시는 늘 그 원본에 다시 그린다(표시 위에 겹쳐 그리지 않는다).
- 시각은 9판 최종본(클라우드 녹화 · 쉼넣기 뒤)의 시각이다. 영상 판본이 바뀌면 시각을 다시 재고 이 파일을 고친다(영상 해시가 근거에 남는다).
- 2026-11-06 이전 사진(표시 없는 촬영 프레임)은 `사진원본/`에 그대로 두었다. 같은 이름의 사진은 그 원본과 같은 시각의 영상 프레임이다.
- 영상 밖 화면(첫 절의 파일 탐색기 · PowerShell)은 `SCREENS`이고, 그 원본 PNG도 `사진원본/`에 둔다.
- 사진의 설명 글은 가이드 생성기(`실습시작/graph_guide.py`)가 가진다.
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
VIDEO = '작업/촬영/neo4j/관계조회-9판-합본/관계조회-9판-최종_1080p.mp4'   # 9판 최종본(클라우드 녹화). Release `영상`의 int-02-04-lab.mp4와 같은 바이트이고, 근거에는 그 해시가 남는다
LABS = [f'workspace/강의제작/산출물/{c}/실습/02회차/랩/02일차_실습1_관계조회/images' for c in ('통합반', '실전반')]
PROVENANCE = HERE.parent.parent/'실습시작/capture-provenance.json'
ORIGINALS = HERE/'사진원본'
RED, WIDTH = '#d32f2f', 4

# 이름, 영상 초, 가이드 절, 빨간 표시들, 자르기(없으면 전체), 마우스 포인터 끝(x, y — 표시 검사에서 포인터만 뺀다)
# 표시 규칙(P-8): 선 굵기 WIDTH, 선의 안팎 GAP px 안에 글자 · 단추 같은 어두운 화소(밝기 DARK 미만)가 없고, 한 사진의 상자끼리는 GAP px 넘게 떨어진다.
# 이 검사는 연한 회색 글자(프롬프트 `$`, 줄 번호, 행 번호)를 세지 않는다 — DARK를 올리면 그래프 선과 노드 테두리까지 걸려 글자와 가르지 못한다. 그래서 상자 둘레의 연한 글자는 사진을 4배로 키워 눈으로 본다.
PHOTOS = [
    ('00-connect', 52.8, '예제 준비하고 연결하기', [[680, 442, 1229, 530], [679, 597, 1229, 688], [679, 697, 1234, 787], [800, 933, 1120, 1003]], None, (960, 660)),
    ('00-tour', 68.47, '예제 준비하고 연결하기', [[643, 83, 1063, 446]], None, (790, 200)),
    ('00-connected', 78.32, '예제 준비하고 연결하기', [[20, 4, 474, 37]], None, (414, 34)),
    ('00-overview', 169.92, '예제 준비하고 연결하기', [[5, 41, 55, 95], [10, 150, 422, 551]], None, (86, 532)),
    ('common-no-return', 251.33, '노드 만들고 RETURN으로 그래프 보기', [[512, 92, 1810, 134], [528, 212, 911, 282]], None, (750, 365)),
    ('common-created', 309.26, '노드 만들고 RETURN으로 그래프 보기', [[900, 370, 1020, 790], [1404, 328, 1603, 410]], None, (966, 444)),
    ('common-properties', 349.92, '노드 만들고 RETURN으로 그래프 보기', [[3, 43, 42, 83], [1260, 838, 1339, 881], [650, 668, 770, 788], [1408, 330, 1885, 644]], None, (1534, 624)),
    ('common-table', 413.24, '같은 노드를 그래프와 표로 조회하기', [[13, 273, 1035, 412]], None, (500, 356)),
    ('common-filtered', 448.73, '조건을 바꾸고 그래프 비교하기', [[607, 479, 801, 672], [1404, 329, 1596, 410]], None, (716, 592)),
    ('common-conditions', 530.35, '조건을 바꾸고 그래프 비교하기', [[24, 161, 1032, 204], [646, 368, 774, 792]], None, (720, 744)),
    ('common-linked', 670.21, '센서를 만들고 관계 연결하기', [[683, 488, 730, 668], [26, 889, 663, 985]], None, (230, 964)),
    ('common-relationship', 689.45, '센서를 만들고 관계 연결하기', [[675, 488, 738, 668], [1404, 283, 1600, 369]], None, (1534, 480)),
    ('common-updated', 736.67, '속성을 수정하고 연결 확인하기', [[594, 465, 814, 687], [1412, 530, 1885, 621]], None, (1534, 580)),
    ('common-unlinked', 818.01, '관계만 삭제하고 노드는 남기기', [[646, 368, 774, 792], [28, 889, 221, 927]], None, (720, 444)),
    ('common-remaining', 886.44, '노드 삭제와 정리 확인하기', [[646, 368, 774, 792]], None, (160, 984)),
    ('common-clean', 932.07, '노드 삭제와 정리 확인하기', [[24, 272, 270, 362]], None, (968, 356)),
    ('forest-layout', 1004.6, '전체 설비 지도 읽기', [[1096, 789, 1390, 830], [1342, 842, 1393, 894]], None, (1376, 876)),
    ('forest-whole', 1029.64, '전체 설비 지도 읽기', [[1340, 842, 1393, 880], [356, 322, 416, 384]], None, (110, 510)),
    ('forest-cooler', 1057.69, '전체 설비 지도 읽기', [[646, 500, 774, 628], [1408, 330, 1885, 575]], None, (1534, 530)),
    ('forest-sensor', 1157.5, '쿨러에 달린 센서 찾기', [[632, 491, 778, 637], [1412, 580, 1885, 713]], None, (1534, 620)),
    ('forest-quantity', 1243.33, '센서에서 물리량까지 따라가기', [[643, 503, 768, 628], [1410, 330, 1558, 367], [1412, 578, 1885, 759]], None, (1536, 714)),
    ('forest-filtered', 1288.31, '질문에 맞춰 조건과 반환값 바꾸기', [[672, 320, 738, 842], [1404, 329, 1835, 562]], None, (160, 984)),
    ('forest-part', 1416.21, '교체 부품 가지 탐색하기', [[638, 498, 772, 630], [1412, 578, 1885, 644]], None, (1536, 624)),
    ('forest-count', 1507.74, '그림에서 센 수와 집계 비교하기', [[956, 271, 1535, 462]], [0, 0, 1920, 650], (576, 464)),
    ('forest-png', 1576.7, '전체 지도에서 정리하고 저장하기', [[1848, 214, 1900, 273]], None, (1880, 252)),
    ('forest-queries', 1622.92, '전체 지도에서 정리하고 저장하기', [[44, 34, 100, 96], [650, 41, 692, 84]], None, (150, 610)),
    ('forest-saved', 1671.11, '전체 지도에서 정리하고 저장하기', [[650, 45, 785, 80], [498, 93, 1811, 340], [21, 165, 312, 261]], None, (644, 134)),
    ('forest-csv', 1694.29, '전체 지도에서 정리하고 저장하기', [[399, 103, 438, 155], [444, 103, 482, 140]], None, (424, 134)),
]
DARK, GAP = 140, 6
# 상자를 띄울 자리가 없어 표시 검사를 하지 않는 사진과 그 까닭(그 사진은 4배로 키워 눈으로 본다)
UNCHECKED = {'00-tour': '안내 창이 입력칸 글자와 6px 안쪽에 떠 있어 어느 자리에 선을 그어도 글자나 창에 닿는다'}

# 영상 밖 화면(영상이 연결 창부터 시작해 찍히지 않은 준비 단계): 이 PC에서 학생 경로대로 ZIP을 풀고 파일 탐색기 → PowerShell로 실행하며
# 창을 그대로 찍은 원본(사진원본/<이름>.png). 이름, 원본, 가이드 절, 빨간 표시들, 자르기(없으면 전체)
# 어두운 터미널에서는 밝기 검사(DARK)가 글자와 배경을 가르지 못해 검사하지 않고, 상자 둘레를 4배로 키워 눈으로 본다.
SCREENS = [
    ('00-explorer', ORIGINALS/'00-explorer.png', '예제 준비하고 연결하기', [[208, 47, 743, 80]], None),
    ('00-powershell', ORIGINALS/'00-powershell.png', '예제 준비하고 연결하기', [[10, 119, 1205, 415]], [0, 0, 1499, 440]),
]


def mark_problems(gray, rects, cursor):
    """표시 규칙 위반 목록. gray는 표시 전 프레임(흑백 배열 — 리스트의 리스트가 아닌 numpy)."""
    import numpy as np
    dark = gray < DARK
    if cursor:
        x, y = cursor
        dark[max(0, y-4):y+40, max(0, x-4):x+28] = False
    h, w = dark.shape
    def count(x0, y0, x1, y1):
        return int(dark[max(0, y0):min(h, y1), max(0, x0):min(w, x1)].sum())
    problems = []
    for r in rects:
        x0, y0, x1, y1 = r
        sides = {'위': count(x0-GAP, y0-GAP, x1+GAP, y0+WIDTH+GAP), '아래': count(x0-GAP, y1-WIDTH-GAP, x1+GAP, y1+GAP),
                 '왼쪽': count(x0-GAP, y0-GAP, x0+WIDTH+GAP, y1+GAP), '오른쪽': count(x1-WIDTH-GAP, y0-GAP, x1+GAP, y1+GAP)}
        problems += [f'{r} {side} 선 {GAP}px 안 어두운 화소 {n}' for side, n in sides.items() if n]
    for i, a in enumerate(rects):
        for b in rects[i+1:]:
            if a[0]-GAP < b[2] and b[0]-GAP < a[2] and a[1]-GAP < b[3] and b[1]-GAP < a[3]:
                problems.append(f'{a}와 {b}가 {GAP}px 안으로 붙거나 겹침')
    return problems


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    work = args.work.resolve()
    if not work.is_relative_to((ROOT/'작업').resolve()):
        parser.error('원본 프레임은 저장소 작업 폴더(작업/…)에 둡니다.')
    work.mkdir(parents=True, exist_ok=True)
    video_sha = sha(ROOT/VIDEO)
    targets = {f'{lab}/{name}.jpg' for lab in LABS for name, *_ in PHOTOS + SCREENS}
    import numpy as np
    frames, failures = {}, []
    for name, seconds, section, rects, crop, cursor in PHOTOS:   # 먼저 모든 표시를 검사하고, 하나라도 어기면 아무것도 쓰지 않는다
        frame = work/f'{video_sha[:12]}-{seconds}.png'
        if not frame.exists():
            subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-hide_banner', '-loglevel', 'error', '-ss', str(seconds),
                            '-i', str(ROOT/VIDEO), '-frames:v', '1', str(frame)], check=True)
        frames[name] = frame
        if name in UNCHECKED:
            continue
        failures += [f'{name}: {p}' for p in mark_problems(np.asarray(Image.open(frame).convert('L')).astype(int), rects, cursor)]
    if failures:
        raise SystemExit('표시 규칙 위반 — 사진을 쓰지 않았다:\n' + '\n'.join(failures))
    records = []
    for name, seconds, section, rects, crop, cursor in PHOTOS:
        frame = frames[name]
        image = Image.open(frame).convert('RGB')
        draw = ImageDraw.Draw(image)
        for rect in rects:
            draw.rectangle(rect, outline=RED, width=WIDTH)
        if crop:
            image = image.crop(crop)
        original = ORIGINALS/f'{name}.jpg'
        for lab in LABS:
            target = ROOT/lab/f'{name}.jpg'
            image.save(target, quality=92)
            records.append({'target': f'{lab}/{name}.jpg', 'kind': '학생 실습 화면', 'section': section,
                            'source': VIDEO, 'source_sha256': video_sha, 'seconds': seconds, 'raw_frame_sha256': sha(frame),
                            'crop_box': crop, 'rectangles': rects, 'pointer': list(cursor) if cursor else None, 'sha256': sha(target),
                            **({'earlier_unmarked': original.relative_to(ROOT).as_posix(), 'earlier_unmarked_sha256': sha(original)} if original.exists() else {})})
    for name, source, section, rects, crop in SCREENS:
        image = Image.open(source).convert('RGB')
        draw = ImageDraw.Draw(image)
        for rect in rects:
            draw.rectangle(rect, outline=RED, width=WIDTH)
        if crop:
            image = image.crop(crop)
        for lab in LABS:
            target = ROOT/lab/f'{name}.jpg'
            image.save(target, quality=92)
            records.append({'target': f'{lab}/{name}.jpg', 'kind': '학생 실습 화면', 'section': section, 'source_type': 'image',
                            'source': source.relative_to(ROOT).as_posix(), 'source_sha256': sha(source),
                            'source_note': '2026-11-06 이 PC에서 ZIP을 D:/HYD-Practice에 풀고 파일 탐색기 주소 표시줄 → PowerShell(Windows Terminal)로 두 명령을 실행하며 창을 찍음',
                            'crop_box': crop, 'rectangles': rects, 'pointer': None, 'sha256': sha(target)})
    for lab in LABS:
        stale = {p.name for p in (ROOT/lab).glob('*.jpg')} - {n+'.jpg' for n, *_ in PHOTOS + SCREENS}
        if stale:
            raise SystemExit(f'{lab}: 근거에 없는 사진 {sorted(stale)} — 이 파일에 넣거나 사진원본/으로 옮긴다')
    old = json.loads(PROVENANCE.read_text(encoding='utf-8'))
    keep = [x for x in old if x['target'] not in targets and x['target'].removeprefix('workspace/') not in {t.removeprefix('workspace/') for t in targets}]
    PROVENANCE.write_text(json.dumps(keep + records, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(len(PHOTOS) + len(SCREENS), '사진 × 두 과정. 눈으로 본 뒤 가이드를 만든다.')


if __name__ == '__main__':
    main()
