"""통합반 3회차 실습1 「운전 조건과 성과 기준에 따른 조치 결과 비교하기」(포털) 학생 가이드 사진을 새 영상의 프레임에서 뽑고 빨간 표시를 그린다.
사진의 영상 시각 · 빨간 표시 좌표는 이 파일 한 곳이고, 사진의 설명 글은 가이드 생성기(`실습시작/build_session3_whatif.py`)가 가진다.

python3 workspace/강의제작/제작도구/촬영/포털/사진_조치결과비교.py --work 작업/<작업>/영상프레임 [--영상 <mp4>] [--자막 <srt>]
    → `산출물/통합반/실습/03회차/랩/03일차_실습1_조치결과비교/images/<이름>.jpg`와 `실습시작/capture-provenance.json`의 그 사진 항목.
    그다음 `실습시작/build_session3_whatif.py`.
- 영상은 2026-11-20 확정 대본(71큐)으로 찍은 새 판이다. Release 「영상」에 올리기 전에는 합성한 자리(VIDEO)의 mp4를 읽고, 올린 뒤에는 받은 mp4를 `--영상`으로 준다.
  근거에는 실제로 읽은 영상의 이름과 sha256이 남는다.
- 시각은 큐 id로 적는다. 자막(SRT)의 n번째 말이 큐 파일의 n번째 큐이므로, 영상을 자르거나 쉼을 바꿔도 그 판의 자막을 주면 시각이 따라온다(말 수가 큐 수와 다르면 멈춘다).
- 영상의 강조(빨간 테두리 · 밑줄, 노란 띠)는 다음 짚기나 누르기 때까지 남는다. 그래서 사진 시각은 누른 직후나 화면을 굴린 직후처럼 강조가 없는 순간으로 고르고,
  프레임에 영상 강조가 남아 있으면 멈춘다(학생이 영상 강조와 가이드의 빨간 네모를 헷갈리지 않게 — 가이드 P-8).
- 원본은 영상에서 뽑은 프레임(`--work`, git 밖)이고, 표시는 늘 그 원본에 다시 그린다. 표시 규칙 검사는 `사진_지식지도.py`의 것을 같이 쓴다.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess
import sys

import imageio_ffmpeg
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sys.path.insert(0, str(HERE))
from 사진_지식지도 import INK, RED, WIDTH, mark_problems, text_pixels  # noqa: E402

VIDEO = '작업/촬영/포털/04-조치결과비교-새판3/04-조치결과비교-새판3_자름.mp4'
SRT = '작업/촬영/포털/04-조치결과비교-새판3/04-조치결과비교-새판3_자름.srt'
CUES = HERE/'통합_03_04_조치결과비교_큐.json'
LAB = 'workspace/강의제작/산출물/통합반/실습/03회차/랩/03일차_실습1_조치결과비교/images'
PROVENANCE = HERE.parent.parent/'실습시작/capture-provenance.json'

S1, S2, S3, S4 = '포털에서 조치 방법 열기', '조치 방법에서 SOP 찾기', '규칙 판단에서 모의 판단 해 보기', '조건 바꿔 보기: 제외와 감점'
S5, S6, S7 = '조건별 손익: 값 하나 바꿔 다시 계산하기', '성과 지표: KPI 목표 바꿔 판정 보기', '설비는 그대로인지 확인하기'

# (이름, 가이드 절, (큐 id, 'start'|'end', 더할 초), 빨간 표시들 [x0, y0, x1, y1](1920×1080 프레임), 마우스 포인터 끝(x, y) 또는 None)
# 시각은 누른 직후 · 굴린 직후의 강조 없는 순간이다(2026-11-20 판의 5fps 훑기로 골랐다). 위아래로 붙은 줄은 둘레 선이 글자에 닿지 않게 한 상자로 묶는다.
PHOTOS = [
    ('c01-open', S1, ('t0102', 'end', -0.84), [[14, 142, 116, 194], [50, 288, 152, 336]], (343, 166)),
    ('c02-pin', S2, ('t0202', 'end', 1.22),
     [[434, 578, 852, 662], [1086, 246, 1182, 284], [926, 424, 1644, 566], [918, 612, 1350, 702]], (617, 606)),
    ('c03-fan', S2, ('t0209', 'end', 0.86),
     [[434, 318, 852, 400], [1086, 246, 1182, 284], [926, 424, 1612, 566], [918, 612, 1350, 702], [922, 744, 1074, 790]], (617, 346)),
    ('c04-rules', S2, ('t0212', 'end', 1.18), [[1080, 702, 1856, 947]], (1070, 768)),
    ('c05-judge', S3, ('t0302', 'end', 1.2),
     [[50, 434, 152, 478], [426, 344, 858, 408], [426, 458, 858, 522], [426, 622, 858, 684], [1402, 440, 1622, 520]], (824, 656)),
    ('c06-candidates', S3, ('t0303', 'start', 5.81), [[926, 160, 1864, 646], [922, 1022, 1074, 1066]], (824, 656)),
    ('c07-inputs', S3, ('t0307', 'start', 0.81), [[921, 250, 1866, 362], [922, 912, 1866, 994]], (1090, 940)),
    ('c08-rule', S3, ('t0309', 'start', 7.95), [[1236, 162, 1402, 219], [918, 852, 1766, 955], [1782, 857, 1848, 926]], (1838, 908)),
    ('c09-manual', S4, ('t0402', 'end', 1.32),
     [[426, 538, 858, 600], [426, 976, 858, 1038], [1402, 340, 1622, 420], [918, 496, 1766, 582], [1004, 818, 1544, 976]], (824, 1010)),
    ('c10-penalty', S4, ('t0405', 'end', 1.39),
     [[426, 548, 858, 610], [426, 644, 858, 706], [918, 166, 1868, 250], [1004, 512, 1252, 724]], (824, 676)),
    ('c11-history', S4, ('t0408', 'end', 0.69), [[426, 224, 858, 286], [422, 430, 866, 906], [928, 106, 1866, 184]], (746, 878)),
    ('c12-whatif', S5, ('t0501', 'end', 1.32), [[50, 482, 180, 526], [423, 386, 858, 560], [426, 638, 858, 698]], (310, 506)),
    ('c13-base', S5, ('t0502', 'end', 1.2), [[920, 275, 1606, 358], [1318, 582, 1858, 622], [939, 642, 994, 960]], (824, 672)),
    ('c14-items', S5, ('t0506', 'start', 3.1),
     [[1538, 152, 1668, 207], [918, 282, 1874, 402], [918, 544, 1874, 594], [922, 872, 1150, 914]], (1640, 180)),
    ('c15-formula', S5, ('t0507', 'start', 5.22), [[954, 418, 1498, 524], [1512, 418, 1870, 820], [498, 643, 578, 682]], (1144, 880)),
    ('c16-values', S5, ('t0508', 'end', 1.66), [[423, 272, 858, 416], [918, 326, 1868, 386]], (540, 664)),
    ('c17-compare', S5, ('t0511', 'start', 2.65), [[423, 526, 858, 670], [936, 214, 1876, 388], [1747, 101, 1876, 138]], (670, 298)),
    ('c18-result', S5, ('t0513', 'start', 2.05),
     [[918, 93, 1856, 217], [918, 451, 1475, 490], [1726, 444, 1866, 496], [426, 456, 858, 516]], (1024, 468)),
    ('c19-reread', S5, ('t0516', 'end', 0.18), [[426, 286, 858, 348], [423, 846, 858, 950], [928, 276, 1858, 342]], (1862, 316)),
    ('c20-kpi', S6, ('t0601', 'end', 0.97),
     [[14, 434, 124, 478], [50, 530, 152, 574], [426, 310, 1866, 495], [423, 528, 548, 568], [426, 576, 898, 794]], (310, 554)),
    ('c21-panel', S6, ('t0603', 'end', 0.99),
     [[867, 71, 1134, 109], [866, 270, 1314, 358], [866, 436, 1898, 591], [1852, 34, 1892, 74], [430, 848, 612, 888]], (572, 630)),
    ('c22-target', S6, ('t0607', 'start', 28.17), [[456, 732, 1866, 802], [1744, 894, 1870, 954]], (1248, 770)),
    ('c23-judged', S6, ('t0608', 'start', 1.57), [[426, 258, 778, 440], [492, 448, 1355, 528], [494, 608, 990, 712]], (1832, 926)),
    ('c24-back', S6, ('t0609', 'end', 1.23), [[790, 258, 1140, 440], [910, 524, 1382, 742]], (572, 682)),
    ('c25-monitor', S7, ('t0701', 'end', 2.31), [[14, 194, 148, 238], [50, 338, 208, 382], [454, 268, 872, 314], [14, 482, 130, 526]], (310, 362)),
]


def cue_times(srt):
    """큐 id → (말 시작초, 말 끝초). SRT의 n번째 말이 큐 파일의 n번째 큐다."""
    blocks = [x for x in re.split(r'\n\s*\n', Path(srt).read_text('utf8').strip()) if x.strip()]
    ids = [q['id'] for q in json.loads(CUES.read_text('utf8'))['cues']]
    if len(blocks) != len(ids):
        raise SystemExit(f'자막 말 {len(blocks)}개와 큐 {len(ids)}개가 다르다 — 이 영상의 자막인지 본다')
    def sec(t):
        h, m, s = t.replace(',', '.').split(':')
        return int(h)*3600 + int(m)*60 + float(s)
    out = {}
    for cid, blk in zip(ids, blocks):
        a, z = blk.splitlines()[1].split(' --> ')
        out[cid] = (sec(a), sec(z))
    return out


def emphasis(rgb):
    """영상 강조가 남은 화소 수: 노란 띠, 그리고 가로나 세로로 40px 넘게 이어진 진한 빨강(테두리 · 밑줄)."""
    import numpy as np
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    yellow = int(((r > 235) & (g > 215) & (b < 170) & (b > 60)).sum())
    red = (r > 200) & (g < 110) & (b < 110)
    lines = 0
    for a in (red, red.T):
        s = np.cumsum(np.pad(a, ((0, 0), (1, 0))).astype(np.int32), axis=1)
        lines += int(((s[:, 40:] - s[:, :-40]) == 40).sum())
    return yellow, lines


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--영상', dest='video', type=Path, default=ROOT/VIDEO)
    parser.add_argument('--자막', dest='srt', type=Path, default=ROOT/SRT)
    args = parser.parse_args()
    work = args.work.resolve()
    if not work.is_relative_to((ROOT/'작업').resolve()):
        parser.error('원본 프레임은 저장소 작업 폴더(작업/…)에 둔다.')
    work.mkdir(parents=True, exist_ok=True)
    video = args.video.resolve()
    if not video.is_file():
        raise SystemExit(f'{video}: 영상이 없다')
    video_name = video.relative_to(ROOT.resolve()).as_posix() if video.is_relative_to(ROOT.resolve()) else video.name
    video_sha = sha(video)
    times = cue_times(args.srt)
    import numpy as np
    frames, failures = {}, []
    for name, section, (cid, where, delta), rects, pointer in PHOTOS:   # 먼저 모두 검사하고, 하나라도 어기면 아무것도 쓰지 않는다
        seconds = round(times[cid][0 if where == 'start' else 1] + delta, 2)
        frame = work/f'{video_sha[:12]}-{seconds}.png'
        if not frame.exists():
            subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-hide_banner', '-loglevel', 'error', '-threads', '2', '-ss', str(seconds),
                            '-i', str(video), '-frames:v', '1', str(frame)], check=True)
        frames[name] = (frame, seconds)
        yellow, lines = emphasis(np.asarray(Image.open(frame).convert('RGB')).astype(int))
        if yellow or lines:
            failures.append(f'{name} ({cid} {where}{delta:+}, {seconds}초): 영상 강조가 남았다 — 노란 화소 {yellow}, 빨간 선 {lines}')
        gray = np.asarray(Image.open(frame).convert('L')).astype(int)
        failures += [f'{name}: {p}' for p in mark_problems(text_pixels(gray), rects, pointer, gray < INK)]
    if failures:
        raise SystemExit('사진을 쓰지 않았다:\n' + '\n'.join(failures))
    records, lab = [], ROOT/LAB
    lab.mkdir(parents=True, exist_ok=True)
    for name, section, at, rects, pointer in PHOTOS:
        frame, seconds = frames[name]
        image = Image.open(frame).convert('RGB')
        draw = ImageDraw.Draw(image)
        for rect in rects:
            draw.rectangle(rect, outline=RED, width=WIDTH)
        target = lab/f'{name}.jpg'
        image.save(target, quality=92)
        records.append({'target': f'{LAB}/{name}.jpg', 'kind': '학생 실습 화면', 'section': section,
                        'source': video_name, 'source_sha256': video_sha, 'cue': list(at), 'seconds': seconds, 'raw_frame_sha256': sha(frame),
                        'crop_box': None, 'rectangles': rects, 'pointer': list(pointer) if pointer else None, 'sha256': sha(target)})
    stale = {p.name for p in lab.glob('*.jpg')} - {n+'.jpg' for n, *_ in PHOTOS}
    if stale:
        raise SystemExit(f'{LAB}: 근거에 없는 사진 {sorted(stale)} — 이 파일에 넣거나 지운다(옛 판은 git 이력에 있다)')
    old = json.loads(PROVENANCE.read_text(encoding='utf-8'))
    keep = [x for x in old if not x['target'].startswith(LAB + '/')]
    PROVENANCE.write_text(json.dumps(keep + records, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(len(PHOTOS), '사진. 눈으로 본 뒤 가이드를 만든다.')


if __name__ == '__main__':
    main()
