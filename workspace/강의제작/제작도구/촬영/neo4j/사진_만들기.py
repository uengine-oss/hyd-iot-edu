"""2회차 관계 조회(Neo4j Browser) 학생 가이드 사진을 게시본 영상의 프레임에서 뽑고 빨간 표시를 그린다. 사진의 영상 시각 · 자르기 · 표시 좌표는 이 파일 한 곳이다.

PYTHONUTF8=1 .venv314/Scripts/python.exe workspace/강의제작/제작도구/촬영/neo4j/사진_만들기.py --work 작업/<작업>/영상프레임
    → 두 과정 `02회차/랩/02일차_실습1_관계조회/images/<이름>.jpg`(같은 바이트)와 `실습시작/capture-provenance.json`의 그 사진 항목.
- 원본은 영상에서 뽑은 프레임(`--work`, git 밖)이다. 표시는 늘 그 원본에 다시 그린다(표시 위에 겹쳐 그리지 않는다).
- 시각은 게시본 영상(v6)의 시각이다. 영상 판본이 바뀌면 시각을 다시 재고 이 파일을 고친다(영상 해시가 근거에 남는다).
- 2026-11-06 이전 사진(표시 없는 촬영 프레임)은 `사진원본/`에 그대로 두었다. 같은 이름의 사진은 그 원본과 같은 시각의 영상 프레임이다.
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
VIDEO = 'workspace/강의제작/산출물/영상/통합반/통합반_02회차_04_실습_관계조회.mp4'
LABS = [f'workspace/강의제작/산출물/{c}/실습/02회차/랩/02일차_실습1_관계조회/images' for c in ('통합반', '실전반')]
PROVENANCE = HERE.parent.parent/'실습시작/capture-provenance.json'
ORIGINALS = HERE/'사진원본'
RED, WIDTH = '#d32f2f', 4

# 이름, 영상 초, 가이드 절, 빨간 표시들, 자르기(없으면 전체), 마우스 포인터 끝(x, y — 표시 검사에서 포인터만 뺀다)
# 표시 규칙(P-8): 선 굵기 WIDTH, 선의 안팎 GAP px 안에 글자 · 단추 같은 어두운 화소(밝기 DARK 미만)가 없고, 한 사진의 상자끼리는 GAP px 넘게 떨어진다.
# 이 검사는 연한 회색 글자(프롬프트 `$`, 줄 번호, 행 번호)를 세지 않는다 — DARK를 올리면 그래프 선과 노드 테두리까지 걸려 글자와 가르지 못한다. 그래서 상자 둘레의 연한 글자는 사진을 4배로 키워 눈으로 본다.
PHOTOS = [
    ('00-connect', 44.0, '예제 준비하고 연결하기', [[680, 445, 1229, 530], [679, 599, 1229, 688], [679, 698, 1229, 787], [793, 815, 1115, 887]], None, (954, 650)),
    ('00-connected', 52.0, '예제 준비하고 연결하기', [[18, 819, 296, 856]], None, (953, 852)),
    ('common-no-return', 179.5, '노드 만들고 RETURN으로 그래프 보기', [[512, 92, 1810, 134], [1847, 85, 1921, 141], [528, 212, 910, 249]], None, (750, 365)),
    ('common-created', 218.5, '노드 만들고 RETURN으로 그래프 보기', [[680, 497, 1228, 655], [1404, 328, 1592, 407]], None, (1062, 415)),
    ('common-properties', 256.5, '노드 만들고 RETURN으로 그래프 보기', [[3, 43, 42, 83], [1286, 838, 1327, 880], [594, 453, 814, 673], [1408, 330, 1862, 618]], None, (1567, 460)),
    ('common-table', 328.5, '같은 노드를 그래프와 표로 조회하기', [[13, 273, 1022, 412]], None, (487, 340)),
    ('common-filtered', 362.0, '조건을 바꾸고 그래프 비교하기', [[607, 479, 801, 672], [1404, 329, 1580, 407]], None, (1062, 415)),
    ('common-conditions', 455.5, '조건을 바꾸고 그래프 비교하기', [[24, 161, 1016, 199], [356, 478, 1052, 673]], None, (1062, 415)),
    ('common-linked', 569.5, '센서를 만들고 관계 연결하기', [[685, 488, 730, 668], [26, 889, 662, 959]], None, (1062, 415)),
    ('common-relationship', 598.0, '센서를 만들고 관계 연결하기', [[686, 488, 738, 668], [1404, 283, 1600, 367]], None, (1567, 460)),
    ('common-updated', 657.5, '속성을 수정하고 연결 확인하기', [[594, 465, 814, 687], [1412, 530, 1862, 618]], None, (1567, 460)),
    ('common-unlinked', 723.5, '관계만 삭제하고 노드는 남기기', [[356, 478, 1052, 673], [28, 889, 221, 925]], None, (1062, 415)),
    ('common-remaining', 803.5, '노드 삭제와 정리 확인하기', [[356, 478, 1052, 673]], None, (1062, 415)),
    ('common-clean', 860.5, '노드 삭제와 정리 확인하기', [[24, 272, 270, 362]], None, (948, 340)),
    ('forest-layout', 922.8, '전체 설비 지도 읽기', [[1572, 785, 1876, 830], [1830, 840, 1882, 878]], None, (1760, 812)),
    ('forest-whole', 946.5, '전체 설비 지도 읽기', [[1786, 838, 1827, 880], [586, 316, 644, 374]], None, (1585, 645)),
    ('forest-cooler', 1014.5, '전체 설비 지도 읽기', [[644, 502, 768, 626], [1408, 330, 1862, 575]], None, (1567, 460)),
    ('forest-sensor', 1167.5, '센서와 관계를 클릭해서 읽기', [[632, 491, 778, 637], [1412, 578, 1862, 712]], None, (1567, 460)),
    ('forest-relationship', 1238.5, '센서와 관계를 클릭해서 읽기', [[655, 440, 760, 630], [1404, 283, 1600, 367]], None, (1567, 460)),
    ('forest-quantity', 1322.0, '센서에서 물리량까지 따라가기', [[643, 503, 768, 628], [1410, 330, 1550, 366], [1412, 578, 1862, 754]], None, (1567, 460)),
    ('forest-filtered', 1362.5, '질문에 맞춰 조건과 반환값 바꾸기', [[672, 320, 738, 842], [1404, 329, 1830, 559]], None, (705, 800)),
    ('forest-part', 1519.5, '교체 부품 가지 탐색하기', [[638, 498, 772, 630], [1412, 578, 1862, 618]], None, (1567, 460)),
    ('forest-count', 1599.0, '그림에서 센 수와 집계 비교하기', [[956, 271, 1520, 460]], [0, 0, 1920, 650], (262, 345)),
    ('forest-png', 1687.0, '전체 지도에서 정리하고 저장하기', [[1838, 218, 1890, 264]], None, (1862, 240)),
    ('forest-queries', 1712.0, '전체 지도에서 정리하고 저장하기', [[44, 34, 100, 96], [650, 41, 692, 84]], None, (672, 62)),
    ('forest-saved', 1741.0, '전체 지도에서 정리하고 저장하기', [[650, 45, 785, 80], [498, 94, 1795, 340], [21, 165, 312, 261]], None, (282, 215)),
]
DARK, GAP = 140, 6


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
    targets = {f'{lab}/{name}.jpg' for lab in LABS for name, *_ in PHOTOS}
    import numpy as np
    frames, failures = {}, []
    for name, seconds, section, rects, crop, cursor in PHOTOS:   # 먼저 모든 표시를 검사하고, 하나라도 어기면 아무것도 쓰지 않는다
        frame = work/f'{video_sha[:12]}-{seconds}.png'
        if not frame.exists():
            subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-hide_banner', '-loglevel', 'error', '-ss', str(seconds),
                            '-i', str(ROOT/VIDEO), '-frames:v', '1', str(frame)], check=True)
        frames[name] = frame
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
    for lab in LABS:
        stale = {p.name for p in (ROOT/lab).glob('*.jpg')} - {n+'.jpg' for n, *_ in PHOTOS}
        if stale:
            raise SystemExit(f'{lab}: 근거에 없는 사진 {sorted(stale)} — 이 파일에 넣거나 사진원본/으로 옮긴다')
    old = json.loads(PROVENANCE.read_text(encoding='utf-8'))
    keep = [x for x in old if x['target'] not in targets and x['target'].removeprefix('workspace/') not in {t.removeprefix('workspace/') for t in targets}]
    PROVENANCE.write_text(json.dumps(keep + records, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(len(PHOTOS), '사진 × 두 과정. 눈으로 본 뒤 가이드를 만든다.')


if __name__ == '__main__':
    main()
