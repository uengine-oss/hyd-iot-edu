"""실습 영상의 낭독이 그 큐 시각의 실제 화면과 맞는지 사람이 판정하도록 큐마다 프레임을 뽑아 대조판을 만든다(영상 V-2).
언제: 실습 대본 · 큐를 고친 뒤 음성을 사기 전(다시 찍지 않고 고치는 길 18은 옛 게시본 화면 위에서), 실습 영상을 굽거나 쉼넣기로 만든 뒤 사용자에게 보내기 전.
까닭: 낭독을 큐의 「조작 · 결과 확인」 글 칸과만 견주면, 화면이 이미 그 상태인데 바꾸라고 하는 말 · 화면에 없는 것을 가리키는 말 ·
      조작과 말 순서가 어긋난 곳을 못 잡는다. 이 도구는 말을 그 시각의 프레임 옆에 놓아 사람이 견주게 한다.

명령(저장소 루트에서, <py>는 공통.md 「자료」, ffmpeg는 PATH나 환경변수 FFMPEG · FFPROBE):
  <py> 화면대조.py 뽑기 <영상.mp4> <자막.srt> <출력 폴더> [--계획 <쉼넣기 계획.json> | --큐 <큐.json>] [--미끼 <수> --미끼답 <파일>]
  <py> 화면대조.py 채점 <출력 폴더> <판정.json>[,<판정2.json> …] [--미끼답 <파일>]
  <py> 화면대조.py 멈춤 <영상.mp4> <뽑은 폴더>              # 판은 두고 말 사이 멈춤만 다시 잰다
  <py> 화면대조.py 시험                                   # 일부러 깨뜨린 입력의 자가시험

뽑기
  - 단위: --계획이면 쉼넣기 계획의 단위(뺌은 건너뜀, 새글이 있으면 새글 — 만든 영상 · 그 자막과 짝). 음성을 사기 전에 옛 게시본 · 옛 자막 위에서
    새 글을 보려면 `--새글로 1`을 더한다(옛 글로 자막에 맞추고 판에는 새글을 그린다). --큐면 [{id, text}] 목록을 자막 블록에 글자로 맞춰 묶는다.
    둘 다 없으면 자막 블록 하나가 단위 하나다(id `#번호`). 글자가 맞지 않으면 단위 id와 자막 번호를 대고 멈춘다.
  - 단위마다 프레임 셋: 말 시작(+0.15초) · 말 가운데 · 다음 말 직전(−0.15초, 다음 말이 3초보다 멀면 말 끝 +3초) — 앞 둘은 말할 때의 상태, 셋째는 조작 결과.
  - 「변화」: 말 시작부터 다음 말 직전까지 이웃 프레임(0.2초 간격) 사이의 가장 큰 차이(96×54 회색 평균 절대차, 쉼넣기 SCENE과 같은 척도).
    말에 조작 낱말(쉼넣기 ACT)이 있는데 변화가 1.0 미만이면 「후보: 조작 말 · 화면 변화 없음」을 단다. 이 후보는 먼저 볼 곳일 뿐 판정이 아니다.
  - 「멈춤」: 말 끝부터 다음 말 시작 사이에서 화면이 그대로(이웃 프레임 차이 0.5 미만)인 가장 긴 길이. 3초 이상이면 `멈춤.json`에 적는다 —
    말도 움직임도 없이 화면이 서 있는 곳(영상 V-14)이라, 쉼넣기 「잘라낼」로 줄일지 그 자리가 따라 해 볼 시간인지 사람이 가른다.
  - 대조판 `판/판_NNN.jpg`: 한 장에 단위 셋, 줄마다 id · 시각 · 변화 · 말 전문 · 프레임 셋(512×288). `단위.json`에 단위 목록을 쓴다.
  - --미끼 N: 판정자가 실제로 화면과 말을 견주는지 재려고, N개 단위의 말을 멀리 떨어진 다른 단위의 말로 바꿔 판에 그린다.
    정답은 --미끼답 파일에만 쓴다(출력 폴더 밖에 두어 판정자가 보지 못하게 한다). 판정자는 미끼를 모른 채 판정한다.

판정.json(판정자가 쓴다): {"본 단위": 수, "걸림": [{"id", "시각", "말", "화면", "갈래", "고칠 말"}], "확인불가": [{"id", "까닭"}]}
  갈래 = 이미 그 상태 | 화면에 없음 | 행위 누락 | 예고 미이행 | 순서 어긋남 | 결과 앞질러 말함 | 화면과 다른 값 · 이름 | 학생 화면과 다름 | 그 밖
채점
  - 「본 단위」가 단위.json의 수와 같고, 걸림 · 확인불가의 id가 모두 단위.json에 있어야 한다.
  - --미끼답이 있으면 미끼 단위가 모두 「걸림」에 있어야 한다. 하나라도 빠지면 판정자가 견주지 않은 것이니 그 판정 전체를 쓰지 않는다(종료 1).
"""
import json, os, re, random, shutil, subprocess, sys, tempfile, textwrap
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding='utf-8')
ACT = re.compile(r'누르|누릅|눌러|클릭|선택|입력|적겠|적어|적을|적습|닫|열겠|열어|엽니다|열게|엔터|가져가|실행|붙여 ?넣|체크|복사|고릅|고를|칠게|쳐 볼|칩니다|바꿔|바꾸|바꿀|지울|지우|지웁|끌어|옮기|옮길')
STEP = 0.2          # 변화 재는 간격(초)
TW, TH = 512, 288   # 판의 프레임 크기
STILL, STALL = 0.5, 3.0   # 이웃 프레임 차이가 STILL 미만이면 멈춘 화면, 말 사이에서 STALL초 넘게 멈추면 「멈춤」 후보
FONTS = ('C:/Windows/Fonts/malgun.ttf', '/usr/share/fonts/malgun/malgun.ttf', '/usr/share/fonts/truetype/nanum/NanumGothic.ttf')


class 실패(SystemExit):
    pass


def fail(msg):
    raise 실패('화면대조: ' + msg)


def tool(name):
    env = os.environ.get(name.upper())
    if env:
        return env
    p = shutil.which(name)
    if p:
        return p
    la = os.environ.get('LOCALAPPDATA', '')
    for c in Path(la, 'Microsoft/WinGet/Packages').glob(f'Gyan.FFmpeg_*/ffmpeg-*/bin/{name}.exe'):
        return str(c)
    fail(f'{name}를 찾지 못함 — PATH나 환경변수 {name.upper()}')


def t2s(x):
    h, m, r = x.strip().split(':'); s, ms = r.split(',')
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def read_srt(p):
    blocks = []
    for chunk in re.split(r'\n\s*\n', Path(p).read_text(encoding='utf-8-sig').strip()):
        lines = chunk.strip().splitlines()
        if len(lines) < 2 or '-->' not in lines[1]:
            fail(f'{p}: 자막 블록 꼴이 아님 — {lines[:2]}')
        a, b = lines[1].split('-->')
        blocks.append({'n': int(lines[0]), 's': t2s(a), 'e': t2s(b), 'text': ' '.join(lines[2:]).strip()})
    for i in range(1, len(blocks)):
        if blocks[i]['s'] < blocks[i - 1]['s']:
            fail(f'{p}: 자막 {blocks[i]["n"]}번이 앞 블록보다 먼저 시작')
    return blocks


def norm(t):
    return re.sub(r'[\s\.,!?·…~「」『』"\'“”‘’()\[\]:;—\-]', '', t)


def units_from(cues, blocks):
    """cues [{id,text}] 순서대로 자막 블록을 글자로 맞춰 묶는다."""
    out, i = [], 0
    for c in cues:
        want, acc, first = norm(c['text']), '', i
        while i < len(blocks) and len(acc) < len(want):
            acc += norm(blocks[i]['text']); i += 1
        if acc != want:
            fail(f'단위 {c["id"]}: 자막 {blocks[first]["n"] if first < len(blocks) else "끝"}번부터의 글이 큐 글과 다름\n  큐: {c["text"][:80]}\n  자막: {" ".join(b["text"] for b in blocks[first:i])[:80]}')
        out.append({'id': c['id'], 's': blocks[first]['s'], 'e': blocks[i - 1]['e'], 'text': c['text'], '자막': [blocks[first]['n'], blocks[i - 1]['n']]})
    if i != len(blocks):
        fail(f'큐를 다 맞춘 뒤 자막 {blocks[i]["n"]}번부터 {len(blocks) - i}블록이 남음')
    return out


def load_units(args, blocks):
    if args.get('계획'):
        plan = json.loads(Path(args['계획']).read_text(encoding='utf-8'))
        if plan.get('잘라낼') and not args.get('새글로'):   # 만든 영상에는 잘라낸 구간 안에 통째로 든 단위가 없다(쉼넣기 「잘라낼」)
            old = read_srt(Path(args['계획']).parent / plan['자막'])
            cut = lambda u: any(a <= old[u['자막'][0]]['s'] and old[u['자막'][1]]['e'] <= b for a, b in plan['잘라낼'])
            plan['단위'] = [u for u in plan['단위'] if not cut(u)]
        if args.get('새글로'):   # 옛 게시본 · 옛 자막 위에 아직 음성을 사지 않은 새 글을 놓는다(길 18의 구매 전)
            us = units_from([{'id': u['id'], 'text': u['글']} for u in plan['단위']], blocks)
            new = {u['id']: u for u in plan['단위']}
            return [x | {'text': new[x['id']].get('새글') or x['text']} for x in us if not new[x['id']].get('뺌')]
        cues = [{'id': u['id'], 'text': u.get('새글') or u['글']} for u in plan['단위'] if not u.get('뺌')]
        return units_from(cues, blocks)
    if args.get('큐'):
        data = json.loads(Path(args['큐']).read_text(encoding='utf-8'))
        data = data.get('cues', data) if isinstance(data, dict) else data
        return units_from([{'id': c['id'], 'text': c['text']} for c in data], blocks)
    return [{'id': f'#{b["n"]}', 's': b['s'], 'e': b['e'], 'text': b['text'], '자막': [b['n'], b['n']]} for b in blocks]


def duration(video):
    r = subprocess.run([tool('ffprobe'), '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', video], capture_output=True)
    if r.returncode:
        fail(f'{video}: ffprobe 실패 — {r.stderr.decode("utf-8", "replace")[-300:]}')
    return float(r.stdout)


def plan_times(units, dur):
    for k, u in enumerate(units):
        nxt = units[k + 1]['s'] if k + 1 < len(units) else dur
        after = nxt - 0.15 if nxt - u['e'] <= 3.0 else u['e'] + 3.0
        after = min(max(after, u['e']), dur - 0.05)
        u['t'] = [min(u['s'] + 0.15, u['e']), (u['s'] + u['e']) / 2, after]
        u['창'] = [u['s'], after]
    return units


def decode(video, dur, want):
    """한 번 디코드하며 STEP 간격의 이웃 프레임 차이와, want(STEP 번호)의 프레임을 모은다."""
    want_set = set(want)
    cmd = [tool('ffmpeg'), '-v', 'error', '-i', video, '-vf', f'fps={1 / STEP},scale={TW}:{TH}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    size = TW * TH * 3
    grays, frames, k = [], {}, 0
    while True:
        buf = p.stdout.read(size)
        if len(buf) < size:
            break
        a = np.frombuffer(buf, np.uint8).reshape(TH, TW, 3)
        g = a.mean(axis=2)
        grays.append(np.asarray(Image.fromarray(g.astype(np.uint8)).resize((96, 54), Image.BILINEAR), np.float32))
        if k in want_set:
            frames[k] = a.copy()
        k += 1
    p.wait()
    if p.returncode:
        fail(f'{video}: ffmpeg 디코드 실패(코드 {p.returncode})')
    if k < (dur / STEP) - 3:
        fail(f'{video}: 프레임 {k}개만 읽음 — 길이 {dur:.1f}초면 {dur / STEP:.0f}개')
    return np.array([0.0] + [float(np.abs(grays[i] - grays[i - 1]).mean()) for i in range(1, len(grays))]), frames


def stalls(units, diffs, dur):
    """말과 말 사이에서 화면이 가장 오래 멈춘 길이(초) — 이웃 프레임 차이가 STILL 미만으로 이어진 가장 긴 줄."""
    out = []
    for k, u in enumerate(units):
        nxt = units[k + 1]['s'] if k + 1 < len(units) else dur
        a, b = int(u['e'] / STEP) + 1, int(nxt / STEP)
        run = best = 0
        for d in diffs[a:b + 1]:
            run = run + 1 if d < STILL else 0
            best = max(best, run)
        u['멈춤'] = round(best * STEP, 1)
        if u['멈춤'] >= STALL:
            out.append({'id': u['id'], '말 끝': round(u['e'], 2), '다음 말': round(nxt, 2), '틈': round(nxt - u['e'], 1), '멈춤': u['멈춤'], '말': u['text'][-60:]})
    return out


def scan(video, units, dur):
    want = {round(t / STEP) for u in units for t in u['t']}
    diffs, frames = decode(video, dur, want)
    for u in units:
        a, b = int(u['창'][0] / STEP) + 1, int(u['창'][1] / STEP) + 1
        u['변화'] = round(float(diffs[a:b].max()) if b > a else 0.0, 2)
        u['_img'] = [frames[min(frames, key=lambda x: abs(x - round(t / STEP)))] for t in u['t']]
        u['후보'] = '조작 말 · 화면 변화 없음' if ACT.search(u['text']) and u['변화'] < 1.0 else ''
    return stalls(units, diffs, dur)


def font(sz):
    for f in FONTS:
        if Path(f).exists():
            return ImageFont.truetype(f, sz)
    fail('한글 글꼴 없음 — ' + ', '.join(FONTS))


def mmss(t):
    return f'{int(t // 60)}:{t % 60:04.1f}'


def draw_sheets(units, out, text_of):
    (out / '판').mkdir(parents=True, exist_ok=True)
    f1, f2 = font(20), font(18)
    per, W = 3, TW * 3 + 8
    for si in range(0, len(units), per):
        rows = units[si:si + per]
        blocks = []
        for u in rows:
            lines = textwrap.wrap(text_of(u), 82) or ['']
            blocks.append((u, lines))
        H = sum(30 + 24 * len(l) + TH + 30 for _, l in blocks)
        im = Image.new('RGB', (W, H), (255, 255, 255)); d = ImageDraw.Draw(im); y = 0
        for u, lines in blocks:
            d.rectangle([0, y, W, y + 28], fill=(30, 30, 60))
            d.text((6, y + 3), f'{u["id"]}   {mmss(u["s"])} ~ {mmss(u["e"])}   변화 {u["변화"]}', font=f1, fill=(255, 255, 255))
            y += 30
            for ln in lines:
                d.text((6, y), ln, font=f2, fill=(0, 0, 0)); y += 24
            for j, a in enumerate(u['_img']):
                im.paste(Image.fromarray(a), (j * (TW + 4), y))
                lab = ('말 시작 ', '말 가운데 ', '다음 말 직전 ')[j] + mmss(u['t'][j])
                d.rectangle([j * (TW + 4), y + TH - 24, j * (TW + 4) + 230, y + TH], fill=(0, 0, 0))
                d.text((j * (TW + 4) + 4, y + TH - 23), lab, font=f2, fill=(255, 255, 0))
            y += TH + 30
        name = f'판_{si // per + 1:03d}.jpg'
        im.save(out / '판' / name, quality=88)
        for u in rows:
            u['판'] = name


def cmd_뽑기(video, srt, out, args):
    out = Path(out)
    blocks = read_srt(srt)
    dur = duration(video)
    if blocks[-1]['e'] > dur + 0.2:
        fail(f'자막 끝 {blocks[-1]["e"]:.2f}초가 영상 {dur:.2f}초보다 김 — 영상과 자막의 판이 다름')
    units = plan_times(load_units(args, blocks), dur)
    stall = scan(video, units, dur)
    decoy = {}
    n = int(args.get('미끼') or 0)
    if n:
        if not args.get('미끼답'):
            fail('--미끼에는 --미끼답 <파일>이 있어야 함')
        if Path(args['미끼답']).resolve().is_relative_to(out.resolve()):
            fail('--미끼답 파일을 출력 폴더 밖에 두어야 판정자가 보지 못한다')
        rng = random.Random(args.get('씨앗') or 7)
        idx = rng.sample(range(len(units)), min(n, len(units)))
        for i in idx:
            far = [j for j in range(len(units)) if abs(j - i) >= 20] or [j for j in range(len(units)) if j != i]
            decoy[units[i]['id']] = units[rng.choice(far)]['text']
        Path(args['미끼답']).write_text(json.dumps({'영상': str(video), '미끼': decoy}, ensure_ascii=False, indent=1), encoding='utf-8')
    draw_sheets(units, out, lambda u: decoy.get(u['id'], u['text']))
    rows = [{k: v for k, v in u.items() if not k.startswith('_') and k != '창'} | {'text': decoy.get(u['id'], u['text'])} for u in units]
    (out / '단위.json').write_text(json.dumps({'영상': str(video), '자막': str(srt), '단위': rows}, ensure_ascii=False, indent=1), encoding='utf-8')
    (out / '멈춤.json').write_text(json.dumps(stall, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'멈춤 후보(말 사이 {STALL}초 넘게 화면이 그대로) {len(stall)} — 멈춤.json')
    cand = [u for u in units if u['후보']]
    print(f'뽑기 끝: 단위 {len(units)} · 판 {len(list((out / "판").glob("*.jpg")))}장 · 후보(조작 말 · 화면 변화 없음) {len(cand)} · 미끼 {len(decoy)}')
    for u in cand:
        print(f'  후보 {u["id"]} {mmss(u["s"])} 변화 {u["변화"]} — {u["text"][:60]}')


def cmd_멈춤(video, out):
    """이미 뽑은 폴더의 단위.json 시각으로 말 사이 멈춤만 다시 잰다(판은 건드리지 않는다)."""
    out = Path(out)
    units = json.loads((out / '단위.json').read_text(encoding='utf-8'))['단위']
    dur = duration(video)
    diffs, _ = decode(video, dur, set())
    stall = stalls(units, diffs, dur)
    (out / '멈춤.json').write_text(json.dumps(stall, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'멈춤 후보 {len(stall)} — {out / "멈춤.json"}')
    for x in stall:
        print(f"  {x['id']} {mmss(x['말 끝'])} 틈 {x['틈']}초 · 멈춤 {x['멈춤']}초 — {x['말']}")


def cmd_채점(out, verdict, args):
    units = json.loads(Path(out, '단위.json').read_text(encoding='utf-8'))['단위']
    ids = {u['id'] for u in units}
    v = {'본 단위': 0, '걸림': [], '확인불가': []}
    for p in verdict.split(','):   # 판을 나눠 맡긴 판정은 쉼표로 이어 준다
        x = json.loads(Path(p).read_text(encoding='utf-8'))
        v['본 단위'] += x.get('본 단위', 0); v['걸림'] += x.get('걸림', []); v['확인불가'] += x.get('확인불가', [])
    err = []
    if v.get('본 단위') != len(units):
        err.append(f'본 단위 {v.get("본 단위")} ≠ 단위 {len(units)} — 다 보지 않음')
    for k in ('걸림', '확인불가'):
        for x in v.get(k, []):
            if x.get('id') not in ids:
                err.append(f'{k}의 id {x.get("id")}가 단위.json에 없음')
    hit = {x['id'] for x in v.get('걸림', [])}
    if args.get('미끼답'):
        decoy = json.loads(Path(args['미끼답']).read_text(encoding='utf-8'))['미끼']
        miss = sorted(set(decoy) - hit)
        print(f'미끼 {len(decoy)} 가운데 잡음 {len(decoy) - len(miss)}' + (f' · 놓침 {miss}' if miss else ''))
        if miss:
            err.append(f'미끼 놓침 {miss} — 이 판정은 화면과 말을 견주지 않았으므로 쓰지 않는다')
        real = [x for x in v.get('걸림', []) if x['id'] not in decoy]
    else:
        real = v.get('걸림', [])
    print(f'걸림(미끼 뺌) {len(real)} · 확인불가 {len(v.get("확인불가", []))}')
    if err:
        fail('채점 불통과\n  ' + '\n  '.join(err))
    return real


def cmd_시험():
    """깨뜨린 입력이 잡히는지 본다: ① 정지 화면 위 조작 말 → 후보 ② 움직이는 화면 위 조작 말 → 후보 아님
    ③ 큐 글과 다른 자막 → 멈춤 ④ 영상보다 긴 자막 → 멈춤 ⑤ 미끼를 놓친 판정 → 채점 불통과 ⑥ 다 잡은 판정 → 통과 ⑦ 말 사이 정지 화면 → 멈춤 ⑧ 말 사이 움직이는 화면 → 멈춤 아님."""
    tmp = Path(tempfile.mkdtemp(prefix='화면대조_시험_'))
    ff = tool('ffmpeg')
    v = tmp / 'v.mp4'
    # 0~6초 회색 정지, 6~12초 색이 바뀌는 화면
    subprocess.run([ff, '-v', 'error', '-f', 'lavfi', '-i', 'color=c=gray:s=640x360:d=6:r=30', '-f', 'lavfi',
                    '-i', 'testsrc2=s=640x360:d=6:r=30', '-filter_complex', '[0][1]concat=n=2:v=1', str(v)], check=True)
    srt = tmp / 's.srt'
    srt.write_text('1\n00:00:00,500 --> 00:00:02,000\n저장 버튼을 누르겠습니다.\n\n2\n00:00:02,500 --> 00:00:04,000\n여기는 설명이에요.\n\n'
                   '3\n00:00:06,500 --> 00:00:08,000\n색을 파란색으로 바꿀게요.\n\n4\n00:00:09,000 --> 00:00:11,000\n끝입니다.\n', encoding='utf-8')
    ok = []
    out = tmp / 'o'
    cmd_뽑기(str(v), str(srt), str(out), {})
    u = {x['id']: x for x in json.loads((out / '단위.json').read_text(encoding='utf-8'))['단위']}
    ok.append(('① 정지 화면 위 조작 말이 후보', bool(u['#1']['후보'])))
    ok.append(('② 움직이는 화면 위 조작 말은 후보 아님', not u['#3']['후보']))
    q = tmp / 'q.json'
    q.write_text(json.dumps([{'id': 'a', 'text': '저장 버튼을 누르겠습니다. 여기는 설명이에요.'}, {'id': 'b', 'text': '색을 빨간색으로 바꿀게요. 끝입니다.'}], ensure_ascii=False), encoding='utf-8')
    try:
        cmd_뽑기(str(v), str(srt), str(tmp / 'o2'), {'큐': str(q)}); ok.append(('③ 다른 글 멈춤', False))
    except 실패 as e:
        ok.append(('③ 큐 글과 다른 자막에서 단위 id를 대고 멈춤', '단위 b' in str(e)))
    long = tmp / 'l.srt'
    long.write_text(srt.read_text(encoding='utf-8') + '\n5\n00:00:30,000 --> 00:00:31,000\n남는 말.\n', encoding='utf-8')
    try:
        cmd_뽑기(str(v), str(long), str(tmp / 'o3'), {}); ok.append(('④ 긴 자막 멈춤', False))
    except 실패 as e:
        ok.append(('④ 영상보다 긴 자막에서 멈춤', '판이 다름' in str(e)))
    key = tmp / '답.json'
    cmd_뽑기(str(v), str(srt), str(tmp / 'o4'), {'미끼': 2, '미끼답': str(key)})
    decoy = list(json.loads(key.read_text(encoding='utf-8'))['미끼'])
    bad = tmp / 'bad.json'; bad.write_text(json.dumps({'본 단위': 4, '걸림': [{'id': decoy[0]}]}), encoding='utf-8')
    try:
        cmd_채점(str(tmp / 'o4'), str(bad), {'미끼답': str(key)}); ok.append(('⑤ 미끼 놓침 불통과', False))
    except 실패:
        ok.append(('⑤ 미끼를 놓친 판정은 채점 불통과', True))
    good = tmp / 'good.json'; good.write_text(json.dumps({'본 단위': 4, '걸림': [{'id': d} for d in decoy]}), encoding='utf-8')
    try:
        cmd_채점(str(tmp / 'o4'), str(good), {'미끼답': str(key)}); ok.append(('⑥ 다 잡은 판정은 통과', True))
    except 실패:
        ok.append(('⑥ 다 잡은 판정은 통과', False))
    s2 = tmp / 's2.srt'
    s2.write_text('1@00:00:00,500 --> 00:00:01,000@하나.@@2@00:00:05,000 --> 00:00:05,800@둘.@@3@00:00:06,500 --> 00:00:08,000@셋.@@4@00:00:11,000 --> 00:00:11,500@넷.@'.replace('@', chr(10)), encoding='utf-8')
    cmd_뽑기(str(v), str(s2), str(tmp / 'o5'), {})
    st = {x['id'] for x in json.loads((tmp / 'o5' / '멈춤.json').read_text(encoding='utf-8'))}
    ok.append(('⑦ 말 사이 4초 정지 화면은 멈춤 후보', '#1' in st))
    ok.append(('⑧ 말 사이 3초 움직이는 화면은 멈춤 아님', '#3' not in st))
    shutil.rmtree(tmp, ignore_errors=True)
    for name, r in ok:
        print(('통과 ' if r else '실패 ') + name)
    if not all(r for _, r in ok):
        fail('자가시험 실패')
    print(f'자가시험 통과 {len(ok)}/{len(ok)}')


def opts(argv):
    pos, kw, i = [], {}, 0
    while i < len(argv):
        if argv[i].startswith('--'):
            kw[argv[i][2:]] = argv[i + 1]; i += 2
        else:
            pos.append(argv[i]); i += 1
    return pos, kw


if __name__ == '__main__':
    a = sys.argv[1:]
    if not a:
        print(__doc__); sys.exit(2)
    pos, kw = opts(a[1:])
    if a[0] == '뽑기' and len(pos) == 3:
        cmd_뽑기(*pos, kw)
    elif a[0] == '멈춤' and len(pos) == 2:
        cmd_멈춤(*pos)
    elif a[0] == '채점' and len(pos) == 2:
        cmd_채점(*pos, kw)
    elif a[0] == '시험':
        cmd_시험()
    else:
        print(__doc__); sys.exit(2)
