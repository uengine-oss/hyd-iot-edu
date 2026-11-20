"""강사 복제 음성 생성(구간 단위). 사용: python voice.py <구간번호...> | --큐 <id,…>  [--견적]
큐는 common.CUES(기본 work/cues.json, 목소리 · 모델도 거기서), 음성은 common.AUDIO(config audio, 커밋함)에 쓴다. 키는 common.elevenlabs_key()로만 읽고 출력하지 않는다.
- 같은 큐 id의 캐시가 글 · 목소리 · 모델 모두 큐 파일과 같으면 다시 만들지 않는다.
- 큐 id는 달라도 글이 글자 하나까지 같고 목소리 · 모델이 같은 캐시가 있으면(옛 판의 큐) 사지 않고 그 mp3 · json을 새 id로 복사한다.
  목소리가 다른 캐시(옛 계정 목소리 — 영상 V-4)는 글이 같아도 쓰지 않는다. 한 편 안에서 목소리가 섞이면 안 되기 때문이다.
- 음성에 보내는 글은 큐 글(대본 글자 그대로)을 said()로 바꾼 것이다. 음성 합성은 대문자 낱말과 밑줄로 이은 이름을 한 글자씩 읽으므로(대본 S-7),
  대문자로만 된 낱말은 첫 글자만 대문자인 낱말로(HAS_COMPONENT → Has Component, SOP-COOL-14 → SOP Cool 14), 붙여 쓴 이름은 띄어(FailureMode → Failure Mode),
  Ctrl은 Control로 보낸다. 글자로 읽는 약어(SPELL)는 그대로 둔다. 캐시는 큐 글로 맞추고, 보낸 글은 json의 said에 남긴다.
- --견적: 사지 않고(키 · ffmpeg도 읽지 않는다) 고른 큐의 재사용 수와 새로 살 큐 · 글자 수만 찍는다. 크레딧 단가는 영상.md V-4."""
import json, re, shutil, subprocess, sys, urllib.request, urllib.error
from common import AUDIO, CUES, ffmpeg, elevenlabs_key
sys.stdout.reconfigure(encoding='utf-8')
cfg = json.loads(CUES.read_text(encoding='utf-8'))
args = sys.argv[1:]
estimate = '--견적' in args
only = set(args[args.index('--큐') + 1].split(',')) if '--큐' in args else None   # --큐 e012,e013: 그 큐만(대표 큐로 단가 재기)
segs = {int(s) for s in args if s.isdigit()}
if only and only - {c['id'] for c in cfg['cues']}:
    raise SystemExit(f"--큐에 큐 파일에 없는 id가 있다: {sorted(only - {c['id'] for c in cfg['cues']})} ({CUES})")
audio = AUDIO; audio.mkdir(exist_ok=True)
SPELL = {'SOP', 'HYD', 'TS', 'HM', 'PNG', 'DB', 'AI', 'CE', 'ID'}   # 글자로 읽는 약어


def said(text):
    """음성에 보내는 글(대본 S-7): 대문자 낱말 · 밑줄 이름 · 붙여 쓴 이름을 낱말로 읽히게 바꾼다. 화면 글자인 큐 글은 그대로 둔다."""
    def word(m):
        w = m.group(0)
        if '_' in w:
            return ' '.join(x.capitalize() for x in w.split('_'))
        if w.isupper():
            return w if w in SPELL or len(w) < 3 else w.capitalize()
        return re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', w)
    t = re.sub(r'(?<![A-Za-z])Ctrl(?![A-Za-z])', 'Control', text)
    t = re.sub(r'SOP-([A-Z]+)-(\d+)', r'SOP \1 \2', t)   # 절차 번호: 이음표를 띄어 낱말 · 숫자로 읽힌다
    return re.sub(r'[A-Za-z]+(?:_[A-Za-z]+)*', word, t)


same_voice = lambda m: m.get('voice_id') == cfg['voice_id'] and m.get('model_id') == cfg['model_id']
by_text = {}   # 글 → 같은 목소리 · 모델로 그 글의 음성이 있는 캐시 id
for j in sorted(audio.glob('*.json')):
    m = json.loads(j.read_text(encoding='utf-8'))
    if j.with_suffix('.mp3').exists() and same_voice(m):
        by_text.setdefault(m['text'], j.stem)
if not estimate:
    ff, key = ffmpeg(), elevenlabs_key()
made = same = copied = spent = chars = 0
todo = []
for c in cfg['cues']:
    if (only and c['id'] not in only) or (not only and c['segment'] not in segs):
        continue
    mp3, meta = audio / (c['id'] + '.mp3'), audio / (c['id'] + '.json')
    if meta.exists() and mp3.exists() and (lambda m: m['text'] == c['text'] and same_voice(m))(json.loads(meta.read_text(encoding='utf-8'))):
        same += 1
        continue
    src = by_text.get(c['text'])
    if src:
        copied += 1
        if not estimate:
            shutil.copyfile(audio / (src + '.mp3'), mp3)
            meta.write_text(json.dumps({**json.loads((audio / (src + '.json')).read_text(encoding='utf-8')), 'id': c['id'], 'copied_from': src, 'character_cost': 0}, ensure_ascii=False), encoding='utf-8')
        print(c['id'], '재사용(같은 글)', src, flush=True)
        continue
    if estimate:
        chars += len(c['text']); todo.append(c['id'])
        continue
    body = json.dumps({'text': said(c['text']), 'model_id': cfg['model_id'], 'voice_settings': {'stability': 0.5, 'similarity_boost': 0.75}}).encode()
    req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{cfg['voice_id']}?output_format=mp3_44100_128", data=body,
                                 headers={'xi-api-key': key, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            mp3.write_bytes(r.read()); cost = r.headers.get('character-cost')   # 같은 계정을 여러 세션이 쓰므로 이 요청의 실제 차감을 남긴다
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{c['id']}: voice HTTP {e.code} {e.read()[:200]!r}") from None
    pcm = subprocess.check_output([ff, '-v', 'error', '-i', str(mp3), '-f', 's16le', '-ac', '1', '-ar', '44100', '-'])
    dur = round(len(pcm) / 2 / 44100 * 1000)
    meta.write_text(json.dumps({'id': c['id'], 'text': c['text'], 'said': said(c['text']), 'duration_ms': dur, 'voice_id': cfg['voice_id'], 'model_id': cfg['model_id'], 'character_cost': int(cost) if cost else None}, ensure_ascii=False), encoding='utf-8')
    made += 1; spent += int(cost) if cost else 0
    print(c['id'], dur, 'cost', cost, flush=True)
if estimate:
    print(f'견적: 고른 큐 {same + copied + len(todo)}개 — 같은 id 캐시 {same} · 같은 글 재사용 {copied} · 새로 살 큐 {len(todo)}개 · 새로 살 글자 {chars}자(공백 포함)')
    print('새로 살 큐:', ','.join(todo))
else:
    print('generated', made, '· 같은 id 캐시', same, '· 같은 글 재사용', copied, '· character-cost 합', spent)
