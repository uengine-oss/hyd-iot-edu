"""사진 근거의 원본 영상·시각·좌표로 사진을 재생성한다. 사진 내용이 바뀌면 검토 상태를 해제한다.

--work <작업 폴더> [--key <이름> …]: 사진을 다시 만든다(키가 없으면 crop이 있는 사진 전부).
--확인 <이름 …>: 눈으로 본 사진을 verified로 적는다.
네모 그리기 · 선 자리 검사 · 자르기 가장자리 검사(사진_만들기)는 포털 사진_만들기.py도 이 파일에서 가져다 쓴다.
"""
from pathlib import Path
import argparse
import hashlib
import json
import statistics
import subprocess

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]

RED = '#d32f2f'
PAD, WIDTH = 6, 6     # 네모는 대상 바로 바깥 6px 자리에 굵기 6으로 그린다(가이드 P-8, 2026-11-11 사용자 기준)
INK = 60              # 띠의 중앙 색과 한 채널이라도 이만큼 다르면 글자 · 그림 화소로 본다(옅은 칸 테두리는 20 안팎)
INK_LIMIT = 0         # 띠에 글자 화소가 하나라도 있으면 선이 글자를 지나거나 가린다(4로 두었을 때 「▶」 3화소를 지나간 선이 통과했다)


def _ink(image, box, ignore=()):
    """box(양끝 포함) 안에서 중앙 색과 INK 넘게 다른 화소 수. ignore 칸(근거에 적은 글자 아닌 칸) 안의 화소는 세지 않는다."""
    region = image.crop((box[0], box[1], box[2] + 1, box[3] + 1))
    pixels = [p for i, p in enumerate(region.get_flattened_data())
              if not any(c[0] <= box[0] + i % region.width <= c[2] and c[1] <= box[1] + i // region.width <= c[3] for c in ignore)]
    if not pixels:
        return 0
    median = [statistics.median(p[c] for p in pixels) for c in range(3)]
    return sum(1 for p in pixels if max(abs(p[c] - median[c]) for c in range(3)) > INK)


def _outer(image, rect):
    pad = rect[4] if len(rect) > 4 else PAD
    width = rect[5] if len(rect) > 5 else WIDTH
    x0, y0, x1, y1 = rect[:4]
    return (max(0, x0 - pad), max(0, y0 - pad), min(image.width - 1, x1 + pad), min(image.height - 1, y1 + pad)), width


def 표시하기(image, rects, name, erase=(), ignore=()):
    """원본 프레임에 빨간 네모를 그린다. 네모 값은 대상 [x0, y0, x1, y1]이고, 선은 대상 바깥 pad 자리부터 안쪽으로 굵기 width만큼 칠한다
    (기본 pad 6 · width 6 — 선이 대상에 바로 붙는다. 화면 가장자리에서는 화면 안쪽으로 붙인다). 옆 글자가 가까운 곳만 다섯째 값 pad,
    여섯째 값 width로 줄인다. 선이 칠해질 띠에 글자 화소가 있으면 그 사진 · 네모 · 변을 적어 실패한다(선이 글자를 지나거나 가리면 안 된다).
    ignore는 선 자리에 걸리지만 글자가 아닌 칸(누르는 순간 대상 밖으로 삐져나온 마우스 커서, 글자에 1px 붙은 창 테두리)이다 — 그 칸의 화소만 세지 않는다.
    erase는 남이 그려 넣은 표시(화살표 등)를 지울 칸이다. 칸 둘레가 한 색일 때만 그 색으로 메우고, 아니면 실패한다."""
    draw = ImageDraw.Draw(image)
    for box in erase:
        x0, y0, x1, y1 = box
        ring = [image.getpixel((x, y)) for x in range(x0 - 2, x1 + 3) for y in (y0 - 2, y1 + 2)] + \
               [image.getpixel((x, y)) for y in range(y0 - 2, y1 + 3) for x in (x0 - 2, x1 + 2)]
        color = tuple(int(statistics.median(p[c] for p in ring)) for c in range(3))
        if max(max(abs(p[c] - color[c]) for c in range(3)) for p in ring) > 12:
            raise ValueError(f'{name}: 지울 칸 {box}의 둘레가 한 색이 아닙니다 — 원래 화면을 되살릴 수 없어 지우지 않습니다')
        draw.rectangle(box, fill=color)
    plans = []
    for rect in rects:
        (ox0, oy0, ox1, oy1), width = _outer(image, rect)
        bands = {'위': (ox0, oy0, ox1, oy0 + width - 1), '아래': (ox0, oy1 - width + 1, ox1, oy1),
                 '왼쪽': (ox0, oy0, ox0 + width - 1, oy1), '오른쪽': (ox1 - width + 1, oy0, ox1, oy1)}
        for side, band in bands.items():
            count = _ink(image, band, ignore)
            if count > INK_LIMIT:
                raise ValueError(f'{name}: 네모 {rect}의 {side} 선 자리 {list(band)}에 글자 화소 {count}개 — 좌표나 pad를 고치세요')
        plans.append(((ox0, oy0, ox1, oy1), width))
    for outer, width in plans:
        draw.rectangle(outer, outline=RED, width=width)


def 자르기_검사(original, crop, rects, name):
    """프레임 전체가 아닌 crop은 가장자리가 글자를 자르면(문장 · 숫자 · 단위가 중간에 잘림) 실패하고,
    네모 선이 자르기 밖으로 나가도 실패한다. 표시를 그리기 전 화면으로 잰다."""
    if list(crop) == [0, 0, original.width, original.height]:
        return
    x0, y0, x1, y1 = crop
    edges = {'위': (x0, y0, x1 - 1, y0), '아래': (x0, y1 - 1, x1 - 1, y1 - 1), '왼쪽': (x0, y0, x0, y1 - 1), '오른쪽': (x1 - 1, y0, x1 - 1, y1 - 1)}
    for side, edge in edges.items():
        count = _ink(original, edge)
        if count > INK_LIMIT:
            raise ValueError(f'{name}: 자르기 {crop}의 {side} 가장자리가 글자 화소 {count}개를 자릅니다')
    for rect in rects:
        (ox0, oy0, ox1, oy1), _ = _outer(original, rect)
        if ox0 < x0 or oy0 < y0 or ox1 > x1 - 1 or oy1 > y1 - 1:
            raise ValueError(f'{name}: 네모 {rect}의 선이 자르기 {crop} 밖으로 나갑니다')


def 사진_만들기(frame, crop, rects, name, erase=(), redactions=(), ignore=()):
    """원본 프레임 → 가림 → 검사 → 표시 → 자르기. 두 생성기가 같은 순서로 쓴다."""
    image = Image.open(frame).convert('RGB')
    draw = ImageDraw.Draw(image)
    for redaction in redactions:
        draw.rectangle(redaction['box'], fill='white')
        font = ImageFont.truetype('C:/Windows/Fonts/malgun.ttf', 18)
        draw.text((redaction['box'][0]+3, redaction['box'][1]+2), redaction['label'], font=font, fill='#555555')
    자르기_검사(image, crop, rects, name)
    표시하기(image, rects, name, erase, ignore)
    return image.crop(tuple(crop))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path)
    parser.add_argument('--key', action='append', help='이 사진만 다시 만든다(여러 번 줄 수 있다). 없으면 crop이 있는 사진 전부')
    parser.add_argument('--확인', nargs='+', dest='confirm', help='눈으로 본 사진을 verified로 적는다')
    args = parser.parse_args()
    manifest_path = HERE/'학생가이드_사진근거.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if args.confirm:
        for key in args.confirm:
            photo = manifest['photos'][key]
            if hashlib.sha256((ROOT/photo['path']).read_bytes()).hexdigest() != photo['sha256']:
                raise SystemExit(f'{key}: 사진이 근거와 다릅니다 — 먼저 다시 만드세요')
            photo['verified'] = True
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print('확인 적음:', len(args.confirm))
        return
    if not args.work:
        parser.error('--work가 필요합니다')
    work = args.work.resolve()
    if not work.is_relative_to((ROOT/'작업').resolve()):
        parser.error('원본 프레임은 저장소 작업 폴더에 보존합니다.')
    work.mkdir(parents=True, exist_ok=True)
    count = 0
    source_hashes = {}
    unknown = set(args.key or []) - set(manifest['photos'])
    if unknown:
        parser.error('사진 근거에 없는 키: '+', '.join(sorted(unknown)))
    for key, photo in manifest['photos'].items():
        if 'crop' not in photo or (args.key and key not in args.key):
            continue
        source = ROOT/photo['source']
        if source not in source_hashes:
            source_hashes[source] = hashlib.sha256(source.read_bytes()).hexdigest()
        if source_hashes[source] != photo['source_sha256']:
            raise ValueError(f'영상 판본 불일치: {key}')
        if photo.get('source_type') == 'image':
            frame = source
        else:
            seconds = photo['seconds']
            if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or seconds < 0:
                raise ValueError(f'잘못된 프레임 시각: {key}')
            identity = hashlib.sha256(f'{source_hashes[source]}:{seconds}'.encode()).hexdigest()[:16]
            frame = work/(key+'-'+identity+'-original.png')
            if not frame.exists():
                subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-ss',str(photo['seconds']),'-i',str(source),'-frames:v','1',str(frame)],check=True)
        image = 사진_만들기(frame, photo['crop'], photo['rectangles'], key, photo.get('erase', []), photo.get('redactions') or [], photo.get('ignore', []))
        destination = ROOT/photo['path']
        destination.parent.mkdir(parents=True,exist_ok=True)
        image.save(destination)
        new_hash = hashlib.sha256(destination.read_bytes()).hexdigest()
        if photo.get('sha256') != new_hash:
            photo['verified'] = False
        photo['sha256'] = new_hash
        photo['raw_frame_sha256'] = hashlib.sha256(frame.read_bytes()).hexdigest()
        count += 1
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'{count}개 사진 생성. 바뀐 사진은 직접 확인 전 미검증 상태.')


if __name__ == '__main__':
    main()
