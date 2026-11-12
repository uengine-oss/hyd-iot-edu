"""강사 복제 음성 생성(구간 단위). 사용: python voice.py <구간번호...>
큐는 common.CUES(기본 work/cues.json, 목소리 · 모델도 거기서), 음성은 common.AUDIO(config audio, 커밋함)에 쓴다. 키는 common.elevenlabs_key()로만 읽고 출력하지 않는다. 이미 있는 큐는 다시 만들지 않는다(같은 문장이면 재사용)."""
import json, subprocess, sys, urllib.request, urllib.error
from common import AUDIO, CUES, ffmpeg, elevenlabs_key
sys.stdout.reconfigure(encoding='utf-8')
ff = ffmpeg()
key = elevenlabs_key()
cfg = json.loads(CUES.read_text(encoding='utf-8'))
args = sys.argv[1:]
only = set(args[args.index('--큐') + 1].split(',')) if '--큐' in args else None   # --큐 a001,a002: 그 큐만(대표 큐로 단가 재기)
segs = {int(s) for s in args if s.isdigit()}
audio = AUDIO; audio.mkdir(exist_ok=True)
made = 0
for c in cfg['cues']:
    if (only and c['id'] not in only) or (not only and c['segment'] not in segs):
        continue
    mp3, meta = audio / (c['id'] + '.mp3'), audio / (c['id'] + '.json')
    if meta.exists() and json.loads(meta.read_text(encoding='utf-8'))['text'] == c['text']:
        continue
    body = json.dumps({'text': c['text'], 'model_id': cfg['model_id'], 'voice_settings': {'stability': 0.5, 'similarity_boost': 0.75}}).encode()
    req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{cfg['voice_id']}?output_format=mp3_44100_128", data=body,
                                 headers={'xi-api-key': key, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            mp3.write_bytes(r.read()); cost = r.headers.get('character-cost')   # 같은 계정을 여러 세션이 쓰므로 이 요청의 실제 차감을 남긴다
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{c['id']}: voice HTTP {e.code} {e.read()[:200]!r}") from None
    pcm = subprocess.check_output([ff, '-v', 'error', '-i', str(mp3), '-f', 's16le', '-ac', '1', '-ar', '44100', '-'])
    dur = round(len(pcm) / 2 / 44100 * 1000)
    meta.write_text(json.dumps({'id': c['id'], 'text': c['text'], 'duration_ms': dur, 'voice_id': cfg['voice_id'], 'model_id': cfg['model_id'], 'character_cost': int(cost) if cost else None}, ensure_ascii=False), encoding='utf-8')
    made += 1
    spent = locals().get('spent', 0) + (int(cost) if cost else 0)
    print(c['id'], dur, 'cost', cost, flush=True)
print('generated', made, 'character-cost 합', locals().get('spent', 0))
