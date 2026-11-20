"""안치윤 음성 생성(ARROWS voice.py를 옮김). 사용: ELEVENLABS_API_KEY=… python3 voice.py <큐 파일> [구간 번호 ...] [--음성 <폴더> --큐 <id,…>]
키는 환경변수에서만 읽고 출력 · 저장하지 않는다. 같은 문장의 음성이 이미 있으면 다시 만들지 않는다(바뀐 문장만 생성 — 큐 글이 같아도 음성에 보낼 글 said가 기록과 다르면 다시 산다).
--음성: 이 도구 config의 audio 폴더 대신 그 폴더에 쓴다(다른 도구 · 다른 영상의 큐, 예: 환경세팅/음성). 그때는 --큐가 있어야 한다 —
캐시가 비어 있는 폴더에서 큐 파일 전체를 사지 않게(녹화 원본 없이 말만 바꾸는 쉼넣기.py의 바꾼 큐만 산다). 없는 id를 주면 멈춘다.
요청마다 응답의 character-cost(깎인 크레딧)를 <큐id>.json의 credits에 남긴다 — 계정을 여럿이 쓰면 잔액 차이로는 지출을 잴 수 없다. 값이 없으면 멈춘다.
음성에 보내는 글은 큐 글(대본 글자 · 화면 글자 그대로)을 said()로 바꾼 것이고(대본 S-7), 보낸 글은 <큐id>.json의 said에 남긴다. 캐시는 큐 글로 맞춘다.
  밑줄로 이은 이름은 eleven_v4가 밑줄을 「underscore」로 소리 내므로(옛 Neo4j 음성 r1207 MONITORED_BY → 「Monitored underscore by」, 2026-11-20 받아쓰기) 낱말마다 띄어 보내고
  (HAS_COMPONENT → Has Component), 붙여 쓴 이름은 띄운다(StateVariable → State Variable). 대문자로만 된 낱말은 그대로 보낸다 — 같은 받아쓰기에서 CREATE · RETURN · ORDER BY ·
  DETACH DELETE는 낱말로 읽혔고, 약어(GQL · MCP · DB)를 고치면 글자로 읽어야 할 것이 낱말이 된다. 새 목소리에서 대문자 낱말이 한 글자씩 읽히면 그 낱말을 여기에 더한다.
  큐 파일 맨 위에 "comma_pause_before_english": true가 있으면, 쉼표 바로 뒤에 영어 낱말이 오는 자리의 쉼표를 말줄임표로 바꿔 보낸다(「첫 줄을 보면, MATCH가」 → 「첫 줄을 보면... MATCH가」 — 지금은 Neo4j 2회차 04 큐만 켠다. 보통 쉼표가 많은 포털 큐에는 켜지 않는다). eleven_v4는 쉼표 · 줄표 · break 태그에서 거의 쉬지 않고(0.04~0.16초) 말줄임표에서만 0.45초쯤 쉬므로(2026-11-20 새 목소리 시험), 꾸밈말 뒤의 영어 낱말을 떼어 들리게 하려고 대본이 쉼표를 둔 자리다(대본 S-7 · 사용자 「첫줄 match 이런거 좀 쉼을 여유있게 … 매번 수식어 나오고 바로 나오지말고요」)."""
import json, os, re, subprocess, sys, urllib.request, urllib.error
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
PAUSE = cfg.get('comma_pause_before_english') is True


def said(text, comma_pause=False):
    """음성에 보내는 글(대본 S-7, 머리말): comma_pause면 쉼표 바로 뒤 영어 낱말 앞을 말줄임표로, 밑줄 이름은 띄어 낱말마다 첫 글자만 대문자로, 붙여 쓴 이름은 띄운다. 그 밖의 글은 그대로다."""
    def word(m):
        w = m.group(0)
        if '_' in w:
            return ' '.join(x.capitalize() for x in w.split('_') if x)
        return re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', w)
    if comma_pause:
        text = re.sub(r', (?=[A-Za-z])', '... ', text)
    return re.sub(r'[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+|[A-Za-z]+', word, text)



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
    if meta.exists():
        old = json.loads(meta.read_text(encoding='utf-8'))
        # 같은 큐 글이라도 음성에 보낸 글(said)이 달라졌으면 다시 산다. said가 없는 옛 캐시는 큐 글로만 맞춘다.
        if old['text'] == c['text'] and ('said' not in old or old['said'] == said(c['text'], PAUSE)):
            continue
    body = json.dumps({'text': said(c['text'], PAUSE), 'model_id': cfg['model_id'], 'voice_settings': {'stability': 0.5, 'similarity_boost': 0.75}}).encode()
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
    meta.write_text(json.dumps({'id': c['id'], 'text': c['text'], 'said': said(c['text'], PAUSE), 'duration_ms': dur, 'credits': int(cost) if cost else None}, ensure_ascii=False), encoding='utf-8')
    if not cost:   # 음성과 기록은 남기고(다시 사지 않게) 멈춘다
        sys.exit(f"{c['id']}: 응답에 character-cost가 없어 지출을 잴 수 없다 — 멈춤")
    made += 1; chars += len(c['text']); credits += int(cost)
    print(c['id'], dur, cost, flush=True)
print('generated', made, 'chars', chars, 'credits', credits)
