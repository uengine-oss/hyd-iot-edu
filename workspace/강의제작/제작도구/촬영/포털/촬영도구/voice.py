"""안치윤 음성 생성(ARROWS voice.py를 옮김). 포털 · Neo4j · 웹 VS Code가 이 파일 하나를 쓴다.
사용: ELEVENLABS_API_KEY=… python3 voice.py <큐 파일> [구간 ...] [--도구 <이름>] [--음성 <폴더> --큐 <id,…>] [--견적]
큐 파일 = {"voice_id", "model_id", "cues": [{"id", "segment", "text"}]}. 구간을 주면 segment가 그 값인 큐만 산다(포털은 번호, VS Code는 모듈 이름 — 큐 파일에 없는 구간을 주면 멈춘다).
키는 환경변수에서만 읽고 출력 · 저장하지 않는다. 같은 문장의 음성이 이미 있으면 다시 만들지 않는다(바뀐 문장만 생성 — 큐 글이 같아도 음성에 보낼 글 said가 기록과 다르면 다시 산다).
--도구: 그 도구 촬영도구/config.json의 audio 폴더에 쓴다(기본 포털, 예: --도구 vscode — common.tool, 합성기 · 실측의 --도구와 같다).
--음성: 도구의 audio 폴더 대신 그 폴더에 쓴다(다른 영상의 큐, 예: 환경세팅/음성). 그때는 --큐가 있어야 한다 —
캐시가 비어 있는 폴더에서 큐 파일 전체를 사지 않게(녹화 원본 없이 말만 바꾸는 쉼넣기.py의 바꾼 큐만 산다). 없는 id를 주면 멈춘다. --도구와 함께 주지 않는다.
--견적: 사지 않는다(키 · ffmpeg가 없어도 된다). 지금 사면 새로 살 큐의 id와 음성에 보낼 글자 수만 찍는다. 크레딧은 이 글자 수에 영상 V-4의 단가를 곱해 어림한다.
요청마다 응답의 character-cost(깎인 크레딧)를 <큐id>.json의 credits에 남긴다 — 계정을 여럿이 쓰면 잔액 차이로는 지출을 잴 수 없다. 값이 없으면 멈춘다.
음성에 보내는 글은 큐 글(대본 글자 · 화면 글자 그대로)을 said()로 바꾼 것이고(대본 S-7), 보낸 글은 <큐id>.json의 said에 남긴다. 캐시는 큐 글로 맞춘다.
  밑줄로 이은 이름은 eleven_v4가 밑줄을 「underscore」로 소리 내므로(옛 Neo4j 음성 r1207 MONITORED_BY → 「Monitored underscore by」, 2026-11-20 받아쓰기) 낱말마다 띄어 보내고
  (HAS_COMPONENT → Has Component), 붙여 쓴 이름은 띄운다(StateVariable → State Variable). 대문자로만 된 낱말은 그대로 보낸다 — 같은 받아쓰기에서 CREATE · RETURN · ORDER BY ·
  DETACH DELETE는 낱말로 읽혔고, 약어(GQL · MCP)를 고치면 글자로 읽어야 할 것이 낱말이 된다. 큐 파일 맨 위에 "read_as": {글자: 읽는 소리}가 있으면 그 낱말(앞뒤가 영문자가 아닌 자리)을
  그 소리로 바꿔 보낸다 — 새 목소리가 DB를 「디, 비」로 끊어 읽어(사용자 2026-11-20 「DB를 왜 끊어서 말하지」) Neo4j 2회차 04 큐가 {"DB": "디비"}를 준다. 이 바꿈은 쉼표 처리보다 먼저 해서,
  바꾼 낱말 앞 쉼표는 말줄임표가 되지 않는다. 새 목소리에서 대문자 낱말이 한 글자씩 끊겨 읽히면 그 큐 파일의 read_as에 더한다.
  큐 파일 맨 위에 "comma_pause_before_english": true가 있으면, 쉼표 바로 뒤에 영어 낱말이 오는 자리의 쉼표를 말줄임표로 바꿔 보낸다(「첫 줄을 보면, MATCH가」 → 「첫 줄을 보면... MATCH가」 — 지금은 Neo4j 2회차 04 큐만 켠다. 보통 쉼표가 많은 포털 큐에는 켜지 않는다). eleven_v4는 쉼표 · 줄표 · break 태그에서 거의 쉬지 않고(0.04~0.16초) 말줄임표에서만 0.45초쯤 쉬므로(2026-11-20 새 목소리 시험), 꾸밈말 뒤의 영어 낱말을 떼어 들리게 하려고 대본이 쉼표를 둔 자리다(대본 S-7 · 사용자 「첫줄 match 이런거 좀 쉼을 여유있게 … 매번 수식어 나오고 바로 나오지말고요」)."""
import json, os, re, subprocess, sys, urllib.request, urllib.error
from pathlib import Path
from common import ffmpeg, tool
sys.stdout.reconfigure(encoding='utf-8')
if len(sys.argv) < 2 or sys.argv[1].startswith('--'):
    sys.exit('사용: voice.py <큐 파일> [구간 ...] [--도구 <이름>] [--음성 <폴더> --큐 <id,…>] [--견적]')
args = sys.argv[2:]
def opt(name):
    if name not in args:
        return None
    i = args.index(name)
    if i + 1 >= len(args):
        sys.exit(f'{name} 뒤에 값이 없다')
    v = args[i + 1]; del args[i:i + 2]; return v
folder, only, tool_name = opt('--음성'), opt('--큐'), opt('--도구')
estimate = '--견적' in args
if estimate:
    args.remove('--견적')
if folder and tool_name:
    sys.exit('--음성과 --도구를 함께 주지 않는다(음성을 쓸 폴더는 하나다)')
if folder and not only:
    sys.exit('--음성을 주면 --큐 <id,…>로 살 큐를 정한다(빈 폴더에서 큐 파일 전체를 사지 않게)')
if [a for a in args if a.startswith('--')]:
    sys.exit(f"모르는 옵션: {[a for a in args if a.startswith('--')]}")
if not estimate:
    key = os.environ.get('ELEVENLABS_API_KEY') or sys.exit('ELEVENLABS_API_KEY 없음: 실행할 때 환경변수로 넘긴다(키를 파일 · 로그에 남기지 않는다)')
    ff = ffmpeg()
cfg = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
if not isinstance(cfg, dict) or not isinstance(cfg.get('cues'), list) or not cfg.get('voice_id') or not cfg.get('model_id'):
    sys.exit(f'{sys.argv[1]}: 큐 파일 꼴이 아니다 — {{"voice_id", "model_id", "cues": [{{"id", "segment", "text"}}]}} (촬영도구/voice.py)')
PAUSE = cfg.get('comma_pause_before_english') is True
READ_AS = cfg.get('read_as') or {}


def said(text, comma_pause=False):
    """음성에 보내는 글(대본 S-7, 머리말): read_as 낱말은 그 소리로, comma_pause면 쉼표 바로 뒤 영어 낱말 앞을 말줄임표로, 밑줄 이름은 띄어 낱말마다 첫 글자만 대문자로, 붙여 쓴 이름은 띄운다. 그 밖의 글은 그대로다."""
    def word(m):
        w = m.group(0)
        if '_' in w:
            return ' '.join(x.capitalize() for x in w.split('_') if x)
        return re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', w)
    for k, v in READ_AS.items():
        text = re.sub(rf'(?<![A-Za-z]){re.escape(k)}(?![A-Za-z])', v, text)
    if comma_pause:
        text = re.sub(r', (?=[A-Za-z])', '... ', text)
    return re.sub(r'[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+|[A-Za-z]+', word, text)



segs = set(args)   # 구간은 글자로 견준다(포털 1 · 2 …, VS Code i305-01.mjs …)
if segs - {str(c['segment']) for c in cfg['cues']}:
    sys.exit(f"{sys.argv[1]}에 없는 구간: {sorted(segs - {str(c['segment']) for c in cfg['cues']})}")
only = set(only.split(',')) if only else None
if only and only - {c['id'] for c in cfg['cues']}:
    sys.exit(f"{sys.argv[1]}에 없는 큐: {sorted(only - {c['id'] for c in cfg['cues']})}")
AUDIO = Path(folder).resolve() if folder else tool(tool_name or '포털').audio
if AUDIO is None:
    sys.exit(f'도구 {tool_name}: config.json에 audio가 없다 (촬영도구/voice.py)')
if not estimate:
    AUDIO.mkdir(parents=True, exist_ok=True)
made = chars = credits = 0
new = []
for c in cfg['cues']:
    if (segs and str(c['segment']) not in segs) or (only and c['id'] not in only):
        continue
    mp3, meta = AUDIO / (c['id'] + '.mp3'), AUDIO / (c['id'] + '.json')
    if meta.exists():
        old = json.loads(meta.read_text(encoding='utf-8'))
        # 같은 큐 글이라도 음성에 보낸 글(said)이 달라졌으면 다시 산다. said가 없는 옛 캐시는 큐 글로만 맞춘다.
        if old['text'] == c['text'] and ('said' not in old or old['said'] == said(c['text'], PAUSE)):
            continue
    if estimate:
        new.append((c['id'], len(said(c['text'], PAUSE))))
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
if estimate:
    print(f"견적(사지 않음): 음성 {cfg['voice_id']} · {cfg['model_id']} · 쓸 폴더 {AUDIO}")
    print('새로 살 큐', len(new), '보낼 글자', sum(n for _, n in new), '— 크레딧 어림은 글자 수 × 영상 V-4 단가')
    print(' '.join(i for i, _ in new))
    sys.exit(0)
print('generated', made, 'chars', chars, 'credits', credits)
