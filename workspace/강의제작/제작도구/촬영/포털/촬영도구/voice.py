"""안치윤 음성 생성(ARROWS voice.py를 옮김). 사용: ELEVENLABS_API_KEY=… python3 voice.py <큐 파일> [구간 번호 ...] [--음성 <폴더> --큐 <id,…>]
키는 환경변수에서만 읽고 출력 · 저장하지 않는다. 같은 문장의 음성이 이미 있으면 다시 만들지 않는다(바뀐 문장만 생성).
--음성: 이 도구 config의 audio 폴더 대신 그 폴더에 쓴다(다른 도구 · 다른 영상의 큐, 예: 환경세팅/음성). 그때는 --큐가 있어야 한다 —
캐시가 비어 있는 폴더에서 큐 파일 전체를 사지 않게(녹화 원본 없이 말만 바꾸는 쉼넣기.py의 바꾼 큐만 산다). 없는 id를 주면 멈춘다.
요청마다 응답의 character-cost(깎인 크레딧)를 <큐id>.json의 credits에 남긴다 — 계정을 여럿이 쓰면 잔액 차이로는 지출을 잴 수 없다. 값이 없으면 멈춘다."""
import json, os, subprocess, sys, urllib.request, urllib.error
from pathlib import Path
from common import AUDIO, ffmpeg
sys.stdout.reconfigure(encoding='utf-8')
key = os.environ.get('ELEVENLABS_API_KEY') or sys.exit('ELEVENLABS_API_KEY 없음: 실행할 때 환경변수로 넘긴다(키를 파일 · 로그에 남기지 않는다)')
ff = ffmpeg()
args = sys.argv[2:]
def opt(name):
    if name not in args:
        return None
    i = args.index(name); v = args[i + 1]; del args[i:i + 2]; return v
folder, only = opt('--음성'), opt('--큐')
if folder and not only:
    sys.exit('--음성을 주면 --큐 <id,…>로 살 큐를 정한다(빈 폴더에서 큐 파일 전체를 사지 않게)')
cfg = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
segs = {int(s) for s in args}
only = set(only.split(',')) if only else None
if only and only - {c['id'] for c in cfg['cues']}:
    sys.exit(f"{sys.argv[1]}에 없는 큐: {sorted(only - {c['id'] for c in cfg['cues']})}")
AUDIO = Path(folder).resolve() if folder else AUDIO
AUDIO.mkdir(parents=True, exist_ok=True)
made = chars = credits = 0
for c in cfg['cues']:
    if (segs and c['segment'] not in segs) or (only and c['id'] not in only):
        continue
    mp3, meta = AUDIO / (c['id'] + '.mp3'), AUDIO / (c['id'] + '.json')
    if meta.exists() and json.loads(meta.read_text(encoding='utf-8'))['text'] == c['text']:
        continue
    body = json.dumps({'text': c['text'], 'model_id': cfg['model_id'], 'voice_settings': {'stability': 0.5, 'similarity_boost': 0.75}}).encode()
    req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{cfg['voice_id']}?output_format=mp3_44100_128", data=body,
                                 headers={'xi-api-key': key, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            mp3.write_bytes(r.read())
            cost = r.headers.get('character-cost')   # 이 요청이 깎은 크레딧 — 한 계정을 여럿이 쓰면 잔액 차이로는 지출을 잴 수 없다
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{c['id']}: voice HTTP {e.code} {e.read()[:200]!r}") from None
    pcm = subprocess.check_output([ff, '-v', 'error', '-i', str(mp3), '-f', 's16le', '-ac', '1', '-ar', '44100', '-'])
    dur = round(len(pcm) / 2 / 44100 * 1000)
    meta.write_text(json.dumps({'id': c['id'], 'text': c['text'], 'duration_ms': dur, 'credits': int(cost) if cost else None}, ensure_ascii=False), encoding='utf-8')
    if not cost:   # 음성과 기록은 남기고(다시 사지 않게) 멈춘다
        sys.exit(f"{c['id']}: 응답에 character-cost가 없어 지출을 잴 수 없다 — 멈춤")
    made += 1; chars += len(c['text']); credits += int(cost)
    print(c['id'], dur, cost, flush=True)
print('generated', made, 'chars', chars, 'credits', credits)
