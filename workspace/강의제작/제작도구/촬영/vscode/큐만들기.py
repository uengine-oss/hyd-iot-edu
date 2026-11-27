"""웹 VS Code 실습 대본의 표에서 큐 JSON을 만든다. 큐 JSON은 손으로 고치지 않고 대본을 고친 뒤 이 도구로 다시 만든다.
언제: 실습 대본(코딩 랩 영상)의 발화를 고친 뒤 · 음성 견적과 녹화 전에.
사용: <py> 큐만들기.py <대본.md> <큐 파일 이름(이 폴더)> [--목소리 <음성 ID>] [--나눔 <큐 id> …]
- 대본의 `# 촬영 본문 끝` 앞에 있는 표 줄 `| <큐 id> | 발화 | 조작 |`이 큐 하나이고, 글은 발화 칸 그대로다(큐 id 꼴은 `<영문 접두><장 2자리><번호 2자리>`, 예: wv0601).
- 구간(segment)은 녹화 모듈 파일 이름 `<접두>-<장 2자리>.mjs`이다. 한 장을 둘 이상의 구간으로 찍으면 --나눔에 새 구간을 여는 큐를 주고,
  그 장의 구간은 차례로 `<접두>-<장>a.mjs` · `b` · `c`가 된다(예: Codex 요청과 그 답 보기를 나눠 찍는 장 — 촬영준비 길 9).
- 목소리는 영상 V-4가 정한다(기본은 지금 계정의 목소리). 그 계정의 키가 없어 옛 계정 목소리로 사는 편은 --목소리로 준다 — 한 편 안에서는 목소리가 하나여야 한다.
- read_as: 「DB」는 음성에 「디비」로 보낸다(포털 voice.py 머리말 — 끊어 읽는 목소리).
- 큐 id가 겹치거나, 발화가 비었거나, --나눔의 큐가 대본에 없으면 그 큐 id를 대며 멈춘다.
"""
import json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VOICE_NOW, MODEL = 'tlxL9ilynpbOVf9sZXKh', 'eleven_v4'      # 영상 V-4
READ_AS = {'DB': '디비'}
ROW = re.compile(r'^\|\s*([a-z]+)(\d{2})(\d{2})\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*$')


def opt_values(args, name, many=False):
    out = []
    while name in args:
        i = args.index(name)
        if i + 1 >= len(args):
            sys.exit(f'{name} 뒤에 값이 없다')
        out.append(args[i + 1]); del args[i:i + 2]
        if not many:
            break
    return out


def main(argv):
    args = list(argv)
    voice = (opt_values(args, '--목소리') or [VOICE_NOW])[0]
    splits = set(opt_values(args, '--나눔', many=True))
    if len(args) != 2 or any(a.startswith('--') for a in args):
        sys.exit(__doc__.split('\n')[2])
    src, name = Path(args[0]), args[1]
    body = src.read_text(encoding='utf-8')
    if '# 촬영 본문 끝' not in body:
        sys.exit(f'{src}: `# 촬영 본문 끝` 줄이 없다')
    body = body.split('# 촬영 본문 끝')[0]
    cues, seen = [], set()
    part = {}      # 장 → 지금 구간 글자(나눔이 있는 장만)
    split_ch = {re.match(r'[a-z]+(\d{2})', s).group(1) for s in splits if re.match(r'[a-z]+\d{4}$', s)}
    for n, line in enumerate(body.splitlines(), 1):
        m = ROW.match(line)
        if not m:
            continue
        pre, ch, _, text, _ = m.groups()
        cid = pre + ch + m.group(3)
        if cid in seen:
            sys.exit(f'{src}:{n}: 큐 id가 겹친다 — {cid}')
        if not text:
            sys.exit(f'{src}:{n}: 발화가 비었다 — {cid}')
        seen.add(cid)
        if ch in split_ch:
            if ch not in part:
                part[ch] = 'a'
            elif cid in splits:
                part[ch] = chr(ord(part[ch]) + 1)
            seg = f'{pre}-{ch}{part[ch]}.mjs'
        else:
            seg = f'{pre}-{ch}.mjs'
        cues.append({'id': cid, 'segment': seg, 'text': text})
    if not cues:
        sys.exit(f'{src}: 큐 표 줄이 없다')
    missing = sorted(splits - seen)
    if missing:
        sys.exit(f'{src}: --나눔의 큐가 대본에 없다 — {", ".join(missing)}')
    out = HERE / name
    data = {'voice_id': voice, 'model_id': MODEL, 'read_as': READ_AS, 'cues': cues}
    with open(out, 'w', encoding='utf-8', newline='') as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    segs = {}
    for c in cues:
        segs[c['segment']] = segs.get(c['segment'], 0) + 1
    print(f'{out.name}: 큐 {len(cues)}개 · 구간 {len(segs)}개 · 목소리 {voice}')
    print(' · '.join(f'{k} {v}' for k, v in segs.items()))


if __name__ == '__main__':
    main(sys.argv[1:])
