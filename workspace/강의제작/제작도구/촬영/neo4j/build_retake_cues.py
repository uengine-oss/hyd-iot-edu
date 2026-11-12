"""관계조회 다시 찍을 판 대본 → 녹화 큐 JSON(record_graph_lesson.mjs가 찍고, 포털 voice.py가 음성을 산다).
언제: 다시 찍을 판 대본(▸ · ‖ 표기)을 고친 뒤 큐를 다시 만들 때.
사용: python3 build_retake_cues.py <대본.md> <안내.html> <출력 큐.json>
      python3 build_retake_cues.py <대본.md> <안내.html> --목록      구간 · 큐 번호 · 글만 찍는다(조작 표 RETAKE_OPS를 적을 때 본다)
  대본의 「### N. 제목」 절이 구간(segment N)이고, 절 안을 ▸ · ‖로 자른 말 조각 하나가 큐 하나다. 빈 조각은 앞 큐의 쉼만 바꾼다
  (「▸ ▸」= 말 없이 이어지는 조작, 앞 큐의 ops에 붙인다).
  쉼(영상 V-14, 2회차 값): 앞 표시가 ▸면 잇기 0.6초, ‖면 1.3초, 앞 큐가 결과를 띄운 조작(run · 누르기)으로 끝났으면 2.0초, 구간의 첫 큐는 2.3초.
  ‖(따라 하기 N초)는 그 큐 뒤 hold N초(학생이 따라 할 시간 — 말 사이 쉼이 아니다).
  조작은 retake_ops.py의 RETAKE_OPS에 구간마다 큐 차례로 적는다. 쿼리는 안내 문서의 칸 글을 그대로 쓴다(칸 번호 = 안내 문서에 나오는 차례, 1부터).
  큐 수와 조작 수가 다르면 멈춘다."""
import html, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from retake_ops import RETAKE_OPS  # noqa: E402

GAP = {'잇기': 600, '큐': 1300, '결과': 2000, '구간': 2300}
RESULT_OPS = {'run', 'runSummary', 'node', 'edge', 'clear', 'sidebar', 'layout', 'png', 'reopen', 'download', 'openFile'}


def guide_blocks(path):
    s = Path(path).read_text(encoding='utf-8')
    return [html.unescape(re.sub(r'<[^>]+>', '', m.group(1))).strip('\n') for m in re.finditer(r'<pre[^>]*>([\s\S]*?)</pre>', s)]


def chunks(script):
    s = Path(script).read_text(encoding='utf-8')
    body = s[s.index('### 1. '):s.index('# 촬영 본문 끝')]
    segs = []
    for sec in re.split(r'\n(?=### )', body):
        head, _, text = sec.partition('\n')
        n = int(re.match(r'### (\d+)\.', head).group(1))
        toks = re.split(r'(▸|‖(?:\(따라 하기 \d+초\))?)', text.replace('\n', ' '))
        items, buf = [], ''
        for x in toks:
            if x == '▸' or x.startswith('‖'):
                t = re.sub(r'\s+', ' ', buf).strip()
                hold = int(re.search(r'(\d+)초', x).group(1)) * 1000 if '따라' in x else 0
                if t:
                    items.append({'text': t, 'after': x[0], 'hold': hold, 'silent_ops': 0})
                elif items:
                    if x == '▸':
                        items[-1]['silent_ops'] += 1
                    else:
                        items[-1]['after'] = '‖'
                    items[-1]['hold'] = max(items[-1]['hold'], hold)
                else:
                    raise SystemExit(f'구간 {n}: 첫 조각이 비었다')
                buf = ''
            else:
                buf += x
        if re.sub(r'\s+', '', buf):
            raise SystemExit(f'구간 {n}: 끝에 표시 없는 글 — {buf.strip()[:40]}')
        segs.append((n, head[4:].strip(), items))
    return segs


def build(script, guide, out):
    segs, blocks = chunks(script), guide_blocks(guide)
    cues, prev, prev_ops = [], None, []
    for n, title, items in segs:
        ops = RETAKE_OPS.get(n)
        if ops is None or len(ops) != len(items):
            raise SystemExit(f'구간 {n}({title}): 큐 {len(items)}개, 조작 {None if ops is None else len(ops)}개 — --목록으로 보고 retake_ops.py를 맞춘다')
        for i, (it, (head, op)) in enumerate(zip(items, ops)):
            if not it['text'].startswith(head):
                raise SystemExit(f'구간 {n} 큐 {i}: 조작 표 첫머리 「{head}」와 큐 글 「{it["text"][:30]}」이 다르다 — retake_ops.py를 맞춘다')
            seq = [dict(o) for o in (op if isinstance(op, list) else [op])]
            for o in seq:
                if 'block' in o:
                    o['query'] = blocks[o.pop('block') - 1]
            c = {'id': f'r{n:02}{i:02}', 'segment': n, 'text': it['text'], 'ops': seq}
            if i == 0:
                c['gap'] = GAP['구간'] if prev else 300
            elif prev['after'] == '▸':
                c['gap'] = GAP['잇기']
            else:
                c['gap'] = GAP['결과'] if any(o['op'] in RESULT_OPS for o in prev_ops) else GAP['큐']
            if it['hold']:
                c['hold'] = it['hold']
            cues.append(c)
            prev, prev_ops = it, seq
    saved = blocks[-1]
    Path(out).write_text(json.dumps({'voice_id': '1PdAOcPlPTz12RwMyFVp', 'model_id': 'eleven_v4', 'saved_title': saved.splitlines()[0].lstrip('/ ').strip(),
                                     'saved_query': saved, 'source': Path(script).name, 'cues': cues}, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'큐 {len(cues)}개 · 구간 {len(segs)} · 글자 {sum(len(c["text"]) for c in cues)} → {out}')


if __name__ == '__main__':
    a = sys.argv[1:]
    if '--목록' in a:
        for n, title, items in chunks(a[0]):
            print(f'== {n} {title}')
            for i, it in enumerate(items):
                print(f'  {n}:{i:02} {it["after"]}{"+" * it["silent_ops"]} {it["hold"] // 1000 or ""} {it["text"][:90]}')
        blocks = guide_blocks(a[1])
        for k, b in enumerate(blocks, 1):
            print(f'칸 {k}: {b.splitlines()[0][:70]}')
    else:
        build(a[0], a[1], a[2])
