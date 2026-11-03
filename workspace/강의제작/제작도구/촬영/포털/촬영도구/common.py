"""촬영도구 공통 설정: config.json의 근거 폴더 · 음성 폴더, ffmpeg 위치. 값이 없으면 어디가 비었는지 알리고 멈춘다.
tool(<이름>)은 다른 도구(vscode · notion · arrows)의 config를 그 도구 촬영도구 폴더 기준으로 푼다 — 이 폴더의 합성기 · 실측이 --도구로 쓴다.
음성(voice.py)과 옛 합성 · 실측 사본은 아직 도구마다 있다."""
import json, os, shutil
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
CFG = json.loads((HERE / 'config.json').read_text(encoding='utf-8'))
WORK = (HERE / CFG['work']).resolve()
AUDIO = (HERE / CFG['audio']).resolve()
TOOLS = HERE.parent.parent   # 촬영/ — 도구마다 <도구>/촬영도구/config.json, 합성기록은 <도구>/합성기록/


def tool(name='포털', root=TOOLS):
    """도구 하나의 값: cfg, work(녹화 원본), audio(음성 캐시), record(합성기록 폴더, 커밋함)."""
    d = Path(root) / name / '촬영도구'
    f = d / 'config.json'
    if not f.is_file():
        raise SystemExit(f'도구 {name}: {f} 없음 (촬영도구/common.py tool)')
    cfg = json.loads(f.read_text(encoding='utf-8'))
    return SimpleNamespace(name=name, dir=d, cfg=cfg, work=(d / cfg['work']).resolve(),
                           audio=(d / cfg['audio']).resolve() if cfg.get('audio') else None, record=Path(root) / name / '합성기록')


def ffmpeg():
    ff = os.environ.get('FFMPEG') or shutil.which('ffmpeg')
    if not ff:
        raise SystemExit('ffmpeg 없음: 환경변수 FFMPEG에 경로를 넣거나 PATH에 추가한다 (촬영도구/common.py)')
    return ff


def chapters(f):
    """영상의 장(chapter) 목록 [(시작 초, 끝 초, 이름)]. 설치 영상처럼 장이 든 조각이 있다."""
    import subprocess
    j = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_chapters', '-of', 'json', str(f)]).decode())
    return [(float(c['start_time']), float(c['end_time']), c.get('tags', {}).get('title', '')) for c in j.get('chapters', [])]


def write_chapters(path, chs):
    """장 목록을 ffmetadata 파일로 쓴다. ffmpeg에 -i <path> 로 넣고 -map_chapters <그 입력 번호> 로 붙인다.
    ffmpeg는 따로 말하지 않으면 첫 입력의 장을 시간 그대로 옮긴다 — 잇거나 자른 영상에서는 장 위치가 틀어진다(2026-10-23 합본)."""
    esc = lambda s: ''.join('\\' + ch if ch in '=;#\\\n' else ch for ch in s)
    lines = [';FFMETADATA1']
    for a, z, t in chs:
        lines += ['[CHAPTER]', 'TIMEBASE=1/1000', f'START={round(a * 1000)}', f'END={round(z * 1000)}', f'title={esc(t)}']
    Path(path).write_text('\n'.join(lines) + '\n', encoding='utf-8')
