"""완성 영상의 소리를 받아써서(ElevenLabs speech-to-text, scribe_v1) 자막 문장과 대조한다 — 빠진 말 · 잘린 말 · 잘못 읽은 말을 찾는다.
사용: ELEVENLABS_API_KEY=… python3 listen.py <영상.mp4> <자막.srt> [<결과 폴더>]
키는 환경변수에서만 읽고 출력 · 저장하지 않는다. 받아쓰기는 유료 크레딧을 쓴다(27분 영상 1회 정도는 수업 계정 한도 안).
대조: 자막 문장 구간(앞뒤 0.3초 여유)에 들어온 단어를 모아 띄어쓰기 · 문장부호를 지우고 비교한다. 영어 이름을 한글로 적은 자막(파이썬 / Python)은
아래 표기표로 맞춘다. 일치율 0.95 미만만 출력한다 — 남은 것 대부분은 다음 문장 첫 단어가 구간 끝에 걸린 것이라 눈으로 가린다.
결과: <결과 폴더>/받아쓰기.json · 대조.txt. 일치율 0.8 미만이 있으면 종료 코드 1(말이 빠졌거나 크게 다름)."""
import difflib, json, os, re, subprocess, sys, urllib.request
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
from common import ffmpeg

mp4, srt = Path(sys.argv[1]), Path(sys.argv[2])
out = Path(sys.argv[3]) if len(sys.argv) > 3 else mp4.parent / (mp4.stem + '_받아쓰기')
out.mkdir(parents=True, exist_ok=True)
key = os.environ.get('ELEVENLABS_API_KEY') or sys.exit('ELEVENLABS_API_KEY 없음: 실행할 때 환경변수로 넘긴다')
stt = out / '받아쓰기.json'
if not stt.exists():
    mp3 = out / '소리.mp3'
    subprocess.run([ffmpeg(), '-v', 'error', '-y', '-i', str(mp4), '-vn', '-ac', '1', '-ar', '16000', '-b:a', '48k', str(mp3)], check=True)
    r = subprocess.run(['curl', '-s', '-m', '1500', '-X', 'POST', 'https://api.elevenlabs.io/v1/speech-to-text', '-H', f'xi-api-key: {key}',
                        '-F', 'model_id=scribe_v1', '-F', 'language_code=kor', '-F', 'timestamps_granularity=word', '-F', f'file=@{mp3}',
                        '-o', str(stt), '-w', '%{http_code}'], capture_output=True, text=True)
    if r.stdout != '200': stt.unlink(missing_ok=True); sys.exit(f'받아쓰기 실패 HTTP {r.stdout}')
    mp3.unlink()
W = [w for w in json.loads(stt.read_text(encoding='utf-8'))['words'] if w.get('type') == 'word']
def ms(t):
    h, m, s = t.split(':'); s, f = s.split(','); return (int(h) * 60 + int(m)) * 60 + int(s) + int(f) / 1000
cues = []
for b in srt.read_text(encoding='utf-8-sig').strip().split('\n\n'):
    l = b.strip().split('\n'); a, z = l[1].split(' --> '); cues.append((ms(a), ms(z), ' '.join(l[2:])))
# 표기표: 자막의 한글 표기 → 받아쓰기가 내는 영어 표기(길게 겹치는 것을 먼저)
T = [('비주얼 스튜디오 코드', 'visualstudiocode'), ('노드 제이에스', 'nodejs'), ('인스톨 나우', 'installnow'), ('더블유에스엘', 'wsl'), ('도커 데스크톱', 'dockerdesktop'),
     ('깃 배시', 'gitbash'), ('엔진 러닝', 'enginerunning'), ('에이치티티피에스', 'https'), ('스타티드', 'started'), ('헬시', 'healthy'), ('파이썬', 'python'),
     ('리드미', 'readme'), ('파워셸', 'powershell'), ('패스', 'path'), ('피니시', 'finish'), ('코덱스', 'codex'), ('오픈에이아이', 'openai'), ('챗지피티', 'chatgpt'),
     ('우분투', 'ubuntu'), ('오케이', 'ok'), ('배시', 'bash'), ('도커', 'docker'), ('노드', 'node'), ('깃허브', 'github'), ('깃', 'git'), ('스터디', 'study'),
     ('여덟', '8'), ('일곱', '7'), ('스물다섯', '25')]
def norm(s):
    s = s.lower()
    for k, v in T: s = s.replace(k, v)
    return re.sub(r'[\s.,?!·\-—「」()%℃°"\'“”:/_]', '', s.replace('.js', 'js'))
rows, worst = [], 1.0
for i, (a, z, t) in enumerate(cues):
    heard = ''.join(w['text'] for w in W if a - 0.3 <= (w['start'] + w['end']) / 2 <= z + 0.3)
    r = difflib.SequenceMatcher(None, norm(t), norm(heard)).ratio(); worst = min(worst, r)
    if r < 0.95: rows.append(f'#{i+1} {int(a//60)}:{a%60:04.1f} 일치 {r:.2f}\n 자막: {t}\n 들림: {heard}')
(out / '대조.txt').write_text('\n\n'.join(rows), encoding='utf-8')
print(json.dumps({'문장': len(cues), '확인할 것': len(rows), '가장 낮은 일치': round(worst, 2), '대조': str(out / '대조.txt')}, ensure_ascii=False))
sys.exit(1 if worst < 0.8 else 0)
