"""안치윤 음성 생성(ARROWS voice.py를 옮김). 사용: ELEVENLABS_API_KEY=… python3 voice.py <큐 파일> [구간 번호 ...]
키는 환경변수에서만 읽고 출력 · 저장하지 않는다. 같은 문장의 음성이 이미 있으면 다시 만들지 않는다(바뀐 문장만 생성)."""
import json, os, subprocess, sys, urllib.request, urllib.error
from pathlib import Path
from common import AUDIO, ffmpeg
sys.stdout.reconfigure(encoding='utf-8')
key = os.environ.get('ELEVENLABS_API_KEY') or sys.exit('ELEVENLABS_API_KEY 없음: 실행할 때 환경변수로 넘긴다(키를 파일 · 로그에 남기지 않는다)')
ff = ffmpeg()
cfg = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
segs = {int(s) for s in sys.argv[2:]}
AUDIO.mkdir(parents=True, exist_ok=True)
made = chars = 0
for c in cfg['cues']:
    if segs and c['segment'] not in segs:
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
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{c['id']}: voice HTTP {e.code} {e.read()[:200]!r}") from None
    pcm = subprocess.check_output([ff, '-v', 'error', '-i', str(mp3), '-f', 's16le', '-ac', '1', '-ar', '44100', '-'])
    dur = round(len(pcm) / 2 / 44100 * 1000)
    meta.write_text(json.dumps({'id': c['id'], 'text': c['text'], 'duration_ms': dur}, ensure_ascii=False), encoding='utf-8')
    made += 1; chars += len(c['text'])
    print(c['id'], dur, flush=True)
print('generated', made, 'chars', chars)
