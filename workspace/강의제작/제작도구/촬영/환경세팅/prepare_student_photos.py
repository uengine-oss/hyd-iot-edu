"""사진 근거의 원본 영상·시각·좌표로 사진을 재생성한다. 사진 내용이 바뀌면 검토 상태를 해제한다."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', required=True, type=Path)
    parser.add_argument('--key', action='append', help='이 사진만 다시 만든다(여러 번 줄 수 있다). 없으면 crop이 있는 사진 전부')
    args = parser.parse_args()
    work = args.work.resolve()
    if not work.is_relative_to((ROOT/'작업').resolve()):
        parser.error('원본 프레임은 저장소 작업 폴더에 보존합니다.')
    work.mkdir(parents=True, exist_ok=True)
    manifest_path = HERE/'학생가이드_사진근거.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
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
        image = Image.open(frame).convert('RGB')
        draw = ImageDraw.Draw(image)
        for redaction in photo.get('redactions', []):
            draw.rectangle(redaction['box'],fill='white')
            font = ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',18)
            draw.text((redaction['box'][0]+3,redaction['box'][1]+2),redaction['label'],font=font,fill='#555555')
        # 화면 전체 사진은 가로 1920을 가이드 폭으로 줄여 보이므로 네모를 굵게, 대상 바깥으로 그려 글을 가리지 않는다(가이드 P-8 — 위치가 보이는 전체 화면, 2026-11-11 사용자 「전체화면이라던지」).
        full = photo['crop'] == [0, 0, image.width, image.height]
        for x0, y0, x1, y1 in photo['rectangles']:
            if full:
                draw.rectangle([x0-6, y0-6, x1+6, y1+6],outline='#d32f2f',width=6)
            else:
                draw.rectangle([x0, y0, x1, y1],outline='#d32f2f',width=3)
        image = image.crop(photo['crop'])
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
