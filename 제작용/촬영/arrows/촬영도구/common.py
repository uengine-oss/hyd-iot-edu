"""촬영도구 공통 설정: config.json의 근거 폴더 · 키 파일, ffmpeg 위치. 값이 없으면 어디가 비었는지 알리고 멈춘다."""
import json, os, shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
CFG = json.loads((HERE / 'config.json').read_text(encoding='utf-8'))
WORK = (HERE / CFG['work']).resolve()


def ffmpeg():
    ff = os.environ.get('FFMPEG') or shutil.which('ffmpeg')
    if not ff:
        raise SystemExit('ffmpeg 없음: 환경변수 FFMPEG에 ffmpeg.exe 경로를 넣거나 PATH에 추가한다 (촬영도구/common.py)')
    return ff
