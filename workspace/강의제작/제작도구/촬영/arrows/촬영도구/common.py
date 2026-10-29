"""촬영도구 공통 설정: config.json의 근거 폴더, 환경변수의 키 파일 · ffmpeg 위치. 값이 없으면 어디가 비었는지 알리고 멈춘다."""
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


def secret_file(env):
    """비밀 파일(키 · 토큰) 경로는 환경변수에서만 받는다. 없거나 파일이 없으면 무엇을 어디에 설정할지 알리고 멈춘다(값은 출력하지 않는다)."""
    p = os.environ.get(env)
    if not p:
        raise SystemExit(f'{env} 없음: 이 PC의 키 파일 경로를 환경변수 {env}에 넣는다 (촬영도구/common.py, 설정 예는 촬영준비.md 3절)')
    path = Path(p)
    if not path.is_file():
        raise SystemExit(f'{env}가 가리키는 파일 없음: {path} — 환경변수 {env}를 이 PC의 키 파일 경로로 고친다 (촬영도구/common.py)')
    return path
