"""녹화 take를 그대로 두고, 걸린 곳만 손본 사본 take를 만든다(공통 C-6 「합본에서 손봄」 — 다시 찍지 않는다).
사용(클라우드 python3): python3 손본_take.py <work 폴더> <원본 take> <새 take> [--미리보기 <폴더>] [--음성교체 <encode.py에 줄 음성교체 json>]
하는 일 셋(이 셋 밖은 원본과 같다 — 프레임은 원본 파일을 가리키는 링크, 고친 프레임만 새 파일):
 1. 입력칸 설명 창 덮기: 큐마다 정한 상자(프레임 px) 안이 그 큐의 기준 프레임(창이 뜨기 직전)과 다른 프레임만, 그 상자를 기준 프레임의 같은 자리로 덮는다.
    창이 사라진 뒤 첫 프레임의 상자가 기준과 같아야 한다(그 사이 창 아래 글이 바뀌지 않았다는 증거) — 다르면 멈춘다.
 2. 강조 끝: 그 큐의 말 끝보다 늦게 끝나는 강조는 말 끝에서 끝낸다(다음 큐가 다른 것을 말하는 동안 남지 않게 — 영상 V-11, 녹화기는 이제 녹화 때 이렇게 한다).
    --음성교체를 주면, 붙임 「뒤」(원래 시작에 놓는 고친 음성)인 큐의 말 끝은 새 음성 길이로 잰다(짧아진 말 뒤에 강조가 남지 않게).
 3. 빼는 강조: 0.2초도 안 떠서 번쩍임으로만 보이는 강조(큐 · 모양 · 길이로 고른다)를 뺀다.
화살표 이동 · 클릭 · 큐 시각은 손대지 않는다."""
import json, os, sys, shutil
from pathlib import Path
import numpy as np
from PIL import Image

# 설명 창: 큐 → 상자(x0, y0, x1, y1 프레임 px, 창보다 4px 넉넉히). 상자는 원본 프레임에서 창이 뜬 프레임과 그 앞 프레임의 차이로 잰 값이다.
# 입력칸 글자 커서(깜박임)가 상자에 들지 않게 잰다(g1011은 커서 바로 아래, g1303은 커서 바로 위에서 끊는다).
POPUPS = {
    'g0512': (237, 42, 1241, 129),
    'g1011': (156, 148, 477, 325),
    'g1103': (388, 93, 482, 130),
    'g1303': (114, 93, 235, 128),
    'g1409': (220, 42, 1224, 129),
}
DROP = [('g0507', 'underline', 300)]   # (큐, 모양, 이 ms보다 짧으면 뺀다)
DIFF = 24       # 화소 값이 이만큼 넘게 다르면 다른 화소
SAME_MAX = 40   # 상자 안 다른 화소가 이 수 이하면 같은 화면(글자 깜박이 · 압축 차)

def main():
    work, src, dst = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
    prev_dir = Path(sys.argv[sys.argv.index('--미리보기') + 1]) if '--미리보기' in sys.argv else None
    S, D = work / src, work / dst
    if D.exists():
        sys.exit(f'{D}: 이미 있다 — 새 이름으로')
    t = json.loads((S / 'timing.json').read_text(encoding='utf-8'))
    F = t['frames']; A = {a['id']: a for a in t['actions']}
    (D / 'frames').mkdir(parents=True)
    for name in ('pointer-start.json', 'initial-state.json', 'end-state.json', 'progress.json'):
        if (S / name).exists():
            shutil.copy2(S / name, D / name)
    load = lambda f: np.asarray(Image.open(S / f['file']).convert('RGB'))
    patched = {}
    report = []
    for cue, (x0, y0, x1, y1) in POPUPS.items():
        a = A[cue]; s, e = a['time'], a['time'] + a['duration']
        idx = [i for i, f in enumerate(F) if s <= f['time'] <= e + 1500]
        if not idx:
            sys.exit(f'{cue}: 그 큐 시각의 프레임이 없다')
        # 창이 뜬 첫 프레임: 바로 앞 프레임과 상자 안이 달라진 첫 프레임. 기준은 그 앞 프레임, 창이 켜진 동안은 기준과 다른 프레임이 이어지는 동안이다.
        box = lambda i: load(F[i])[y0:y1, x0:x1].astype(int)
        cnt = lambda a, b: int((np.abs(a - b).max(axis=2) > DIFF).sum())
        first = next((i for i in idx if cnt(box(i), box(i - 1)) > SAME_MAX), None)
        if first is None:
            sys.exit(f'{cue}: 그 큐 동안 상자 안에 창이 뜨지 않았다 — 상자나 시각을 다시 잰다')
        ref_i = first - 1; ref = box(ref_i)
        on = []
        i = first
        while i < len(F) and cnt(box(i), ref) > SAME_MAX:
            on.append(i); i += 1
        after = i
        if after >= len(F) or F[after]['time'] > e + 1500:
            sys.exit(f'{cue}: 창이 그 큐 안에서 사라지지 않았다(프레임 {on[-1]}까지) — 창 아래 글이 바뀌었을 수 있다')
        ref = ref.astype(np.uint8)
        for i in on:
            img = load(F[i]).copy(); img[y0:y1, x0:x1] = ref
            patched[i] = img
        report.append({'큐': cue, '상자': [x0, y0, x1, y1], '기준 프레임': F[ref_i]['file'], '덮은 프레임': len(on),
                       '처음': round(F[on[0]]['time'] / 1000, 2), '끝': round(F[on[-1]]['time'] / 1000, 2), '사라진 뒤 같음': F[after]['file']})
        if prev_dir:
            prev_dir.mkdir(parents=True, exist_ok=True)
            m = on[len(on) // 2]
            pad = 60
            box = (max(x0 - pad, 0), max(y0 - pad, 0), min(x1 + pad, 1920), min(y1 + pad, 1080))
            before = Image.fromarray(load(F[m])).crop(box); fixed = Image.fromarray(patched[m]).crop(box)
            c = Image.new('RGB', (before.width, before.height * 2 + 10), 'white'); c.paste(before, (0, 0)); c.paste(fixed, (0, before.height + 10))
            c.save(prev_dir / f'{cue}_전후.jpg')
    for i, f in enumerate(F):
        out = D / f['file']
        if i in patched:
            Image.fromarray(patched[i]).save(out, quality=95)
        else:
            os.symlink(os.path.relpath(S / f['file'], out.parent), out)
    said_end = {a['id']: a['time'] + a['duration'] for a in t['actions']}
    if '--음성교체' in sys.argv:
        ovf = Path(sys.argv[sys.argv.index('--음성교체') + 1]).resolve()
        for o in json.loads(ovf.read_text(encoding='utf-8')):
            if o.get('붙임') == '뒤':
                a = next(a for a in t['actions'] if abs(a['time'] - o['time']) < 5)
                new = json.loads((ovf.parent / o['file']).resolve().with_suffix('.json').read_text(encoding='utf-8'))['duration_ms']
                said_end[a['id']] = a['time'] + min(new, a['duration'])
    hs, cut, dropped = [], 0, []
    for h in t['highlights']:
        if any(h['cue'] == c and h['shape'] == sh and h['end'] - h['start'] < ms for c, sh, ms in DROP):
            dropped.append([h['cue'], h['shape'], round(h['end'] - h['start'])]); continue
        end = said_end.get(h['cue'])
        if end is not None and h['end'] > end:
            h = dict(h, end=end, endBy='말 끝'); cut += 1
        hs.append(h)
    t['highlights'] = hs
    (D / 'timing.json').write_text(json.dumps(t, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'설명 창': report, '말 끝에서 끊은 강조': cut, '뺀 강조': dropped, '덮은 프레임 합': len(patched)}, ensure_ascii=False, indent=1))

main()
