"""안치윤 음성 준비. 사용: python voice.py
1) voice-jobs.json의 새 큐를 ElevenLabs(eleven_v4, 안치윤, stability 0.5 · similarity 0.75)로 만든다. 이미 같은 문장이 있으면 다시 만들지 않는다.
2) fix-* 큐: 오전 검수에서 고친 음성(음성내용검수/<이름>.mp3)을 음성 캐시에 큐로 복사한다(새 비용 없음).
키는 config.json의 keyFile에서만 읽고 출력하지 않는다. 결과 = 음성 캐시(config audio)의 <id>.mp3 · <id>.json(text, duration_ms)."""
import concurrent.futures, json, re, shutil, subprocess, sys, urllib.request, urllib.error
from pathlib import Path
from common import CFG, HERE, AUDIO, ffmpeg
sys.stdout.reconfigure(encoding='utf-8')
ff = ffmpeg()
VOICE, MODEL = '1PdAOcPlPTz12RwMyFVp', 'eleven_v4'

def duration_ms(mp3):
    pcm = subprocess.check_output([ff, '-v', 'error', '-i', str(mp3), '-f', 's16le', '-ac', '1', '-ar', '44100', '-'])
    return round(len(pcm) / 2 / 44100 * 1000)

def write_meta(cid, text, mp3):
    (AUDIO / f'{cid}.json').write_text(json.dumps({'id': cid, 'text': text, 'duration_ms': duration_ms(mp3)}, ensure_ascii=False), encoding='utf-8')

# 2) 검수에서 고친 음성
review = AUDIO.parent / '음성내용검수'
for f in json.loads((review / '음성수정안.json').read_text(encoding='utf-8')):
    src, cid = review / f"{f['name']}.mp3", f"fix-{f['name']}"
    if not src.exists():
        raise SystemExit(f'검수 음성 없음: {src}')
    dst = AUDIO / f'{cid}.mp3'
    shutil.copyfile(src, dst); write_meta(cid, f['text'], dst)

# 1) 새 큐
jobs = json.loads((HERE / 'voice-jobs.json').read_text(encoding='utf-8'))
todo = [j for j in jobs if not ((AUDIO / f"{j['id']}.json").exists() and json.loads((AUDIO / f"{j['id']}.json").read_text(encoding='utf-8'))['text'] == j['text'])]
print(f'새로 만들 큐 {len(todo)} / 전체 {len(jobs)}', flush=True)
if todo:
    m = re.search(r'(sk_[A-Za-z0-9]+)', Path(CFG['keyFile']).read_text(encoding='utf-8-sig'))
    if not m:
        raise SystemExit(f"{CFG['keyFile']}: ElevenLabs 키(sk_…)를 찾지 못함")
    key = m.group(1)
    def make(j):
        body = json.dumps({'text': j['text'], 'model_id': MODEL, 'voice_settings': {'stability': 0.5, 'similarity_boost': 0.75}}).encode()
        req = urllib.request.Request(f'https://api.elevenlabs.io/v1/text-to-speech/{VOICE}?output_format=mp3_44100_128', data=body,
                                     headers={'xi-api-key': key, 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                mp3 = AUDIO / f"{j['id']}.mp3"; mp3.write_bytes(r.read())
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"{j['id']}: voice HTTP {e.code} {e.read()[:200]!r}") from None
        write_meta(j['id'], j['text'], mp3)
        return j['id']
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for cid in pool.map(make, todo):
            print('made', cid, flush=True)
print('done')
