"""촬영도구 공통 설정: config.json의 근거 폴더 · 음성 폴더, 환경변수의 키 · ffmpeg 위치. 값이 없으면 어디가 비었는지 알리고 멈춘다."""
import json, os, shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
CFG = json.loads((HERE / 'config.json').read_text(encoding='utf-8'))
WORK = (HERE / CFG['work']).resolve()
# 음성 캐시(커밋함)와 큐 파일. 시험 녹화는 HYD_AUDIO · HYD_CUES로 다른 자리를 준다(본 음성 폴더를 더럽히지 않는다).
AUDIO = Path(os.environ['HYD_AUDIO']).resolve() if os.environ.get('HYD_AUDIO') else (HERE / CFG['audio']).resolve()
CUES = Path(os.environ['HYD_CUES']).resolve() if os.environ.get('HYD_CUES') else WORK / 'cues.json'


def ffmpeg():
    ff = os.environ.get('FFMPEG') or shutil.which('ffmpeg')
    if not ff:
        raise SystemExit('ffmpeg 없음: 환경변수 FFMPEG에 ffmpeg.exe 경로를 넣거나 PATH에 추가한다 (촬영도구/common.py)')
    return ff


def secret_file(env):
    """비밀 파일(키 · 토큰) 경로는 환경변수에서만 받는다. 없거나 파일이 없으면 무엇을 어디에 설정할지 알리고 멈춘다(값은 출력하지 않는다)."""
    p = os.environ.get(env)
    if not p:
        raise SystemExit(f'{env} 없음: 이 PC의 키 파일 경로를 환경변수 {env}에 넣는다 (촬영도구/common.py, 설정 예는 촬영/README.md 「자료」의 음성 키)')
    path = Path(p)
    if not path.is_file():
        raise SystemExit(f'{env}가 가리키는 파일 없음: {path} — 환경변수 {env}를 이 PC의 키 파일 경로로 고친다 (촬영도구/common.py)')
    return path


def elevenlabs_key():
    """ElevenLabs 키: 클라우드는 환경변수 ELEVENLABS_API_KEY, 이 PC는 HYD_ELEVENLABS_KEY_FILE이 가리키는 파일(sk_…). 값은 출력하지 않는다."""
    import re
    for name in ('ELEVENLABS_API_KEY', 'ElevenLabs_API_KEY'):   # 클라우드 환경 변수 칸에 대소문자가 다른 이름으로 들어온 적이 있다
        if os.environ.get(name):
            return os.environ[name].strip()
    m = re.search(r'(sk_[A-Za-z0-9]+)', secret_file('HYD_ELEVENLABS_KEY_FILE').read_text(encoding='utf-8-sig'))
    if not m:
        raise SystemExit('HYD_ELEVENLABS_KEY_FILE이 가리키는 파일에서 ElevenLabs 키(sk_…)를 찾지 못함 (촬영도구/common.py)')
    return m.group(1)
