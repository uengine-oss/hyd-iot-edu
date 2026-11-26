"""언제: 다 쓴 이론 대본 한 편을 바깥 모델(OpenAI, 기본 gpt-6.2-astra)에 통째로 보내 적대적으로 읽고 다시 쓰게 할 때(대본 길 5).
대본 없이 글 한 장만 보낼 때도 쓴다(--글).

쓰는 법(저장소 루트에서):
  편 하나:  OPENAI_KEY_FILE=<키 파일> <py> workspace/강의제작/제작도구/검사/바깥검토.py \
                --지시 <지시.md> --편 <대본.md> --덱 <덱 원고.md> --그림폴더 <장 렌더 폴더> [--공통 <공통.md>] \
                [--까닭 <다시 보내는 까닭.md>] --출력 <새 폴더> [--모델 gpt-6.2-astra]
  글 한 장: OPENAI_KEY_FILE=<키 파일> <py> … 바깥검토.py --지시 <지시.md> --글 <글.md> --출력 <새 폴더>
  묶기만:   <py> … 바깥검토.py --지시 … --편 … --덱 … --그림폴더 … --출력 <새 폴더> --묶기만   (보내지 않고 보낸글.md만 쓴다)
  자가시험: <py> … 바깥검토.py --자가시험   (일부러 깨뜨린 입력이 모두 걸리는지 본다, 보내지 않는다)

- 편을 보내면 요청 한 번에 MD 하나가 간다. 맨 앞에 공통 자료(--공통, 제목을 단 MD)가 오고, 그 뒤에 대본의 장마다
  「장 그림 → 화면에 적힌 글 → 노트 → 대본」을 한 묶음으로 1장부터 차례대로 끼운다. 그림은 그 장 묶음 안에 들어간다.
  화면 글은 덱 원고의 「화면 내용」에서 화면에 실제로 보이는 글(제목 · 기관 · 과정 · 부제 · 메시지 · 표 머리 · 요소)만 뽑고,
  좌표 · 아이콘 · 그림 파일 이름 · 화면 구성 · 제작 기준(근거 문헌)은 보내지 않는다.
- 돌아온 판에서 걸린 곳을 다시 보낼 때는 그 판을 --편으로 주고 --까닭에 걸린 곳과 까닭을 적는다. 까닭은 공통 자료 바로 뒤에 간다.
- 대본의 장 · 덱 장 · 그림이 하나라도 맞지 않으면 보내기 전에 장 번호를 대며 멈춘다.
- 돌아온 판의 `# [` 구간 줄과 `## [SLIDE` 장 줄이 보낸 대본과 같은 차례가 아니면, 결과는 저장하되 어긋난 줄을 찍고 종료 코드 3으로 멈춘다.
- 키는 환경변수 OPENAI_API_KEY 또는 OPENAI_KEY_FILE(키 한 줄, 또는 `이름=값` 줄이 든 파일)로만 받는다.
  키 값과 키 파일 경로는 출력하거나 파일에 적지 않는다.
- 출력 폴더에 보낸글.md(그림은 파일 이름으로) · 요청.json(키 · 그림 데이터 없음) · 응답.json · 결과.md를 쓰고,
  이미 있으면 멈춘다(덮어쓰지 않는다).
- 유료 호출이다. 보내기 전에 글자 수와 그림 수를 찍고, 끝나면 응답의 토큰 수를 찍는다.
"""
import argparse
import base64
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

URL = 'https://api.openai.com/v1/responses'
OUTPUTS = ('보낸글.md', '요청.json', '응답.json', '결과.md')
SLIDE_RE = re.compile(r'^## \[SLIDE (\d+)(?:~(\d+))?\]')
DECK_RE = re.compile(r'^## SLIDE (\d+) — (.*)$')
COORD_RE = re.compile(r'^\d+(\.\d+)?(,\d+(\.\d+)?){2,}$')
SCREEN_KEYS = ('기관', '과정', '부제', '메시지', '머리')


class 멈춤(Exception):
    pass


def key():
    value = os.environ.get('OPENAI_API_KEY', '').strip()
    if value:
        return value
    path = os.environ.get('OPENAI_KEY_FILE', '').strip()
    if not path:
        sys.exit('바깥검토: 키가 없다 — 환경변수 OPENAI_API_KEY 또는 OPENAI_KEY_FILE을 준다.')
    p = Path(path)
    if not p.is_file():
        sys.exit('바깥검토: OPENAI_KEY_FILE이 가리키는 파일이 없다.')
    lines = [x.strip() for x in p.read_text(encoding='utf-8-sig').splitlines() if x.strip() and not x.strip().startswith('#')]
    for line in lines:
        if '=' in line:
            name, val = line.split('=', 1)
            if name.strip() in ('OPENAI_API_KEY', 'OPENAI_KEY'):
                return val.strip().strip('"').strip("'")
    if len(lines) == 1 and '=' not in lines[0]:
        return lines[0]
    sys.exit('바깥검토: 키 파일에서 키를 찾지 못했다 — 키 한 줄이거나 OPENAI_API_KEY=… 줄이어야 한다.')


def read(path, what):
    p = Path(path)
    if not p.is_file():
        raise 멈춤(f'{what} 파일이 없다 — {path}')
    text = p.read_text(encoding='utf-8-sig').strip()
    if not text:
        raise 멈춤(f'{what} 파일이 비었다 — {path}')
    return text


def script_body(path):
    """대본의 `# [도입]`부터 `# 촬영 본문 끝` 앞까지를 (구간 줄 · 장) 차례 그대로 나눈다."""
    lines = read(path, '대본').splitlines()
    start = next((i for i, l in enumerate(lines) if l.startswith('# [')), None)
    end = next((i for i, l in enumerate(lines) if l.startswith('# 촬영 본문 끝')), None)
    if start is None or end is None or end <= start:
        raise 멈춤(f'{path}: `# [` 구간 줄과 `# 촬영 본문 끝` 사이의 본문을 찾지 못했다')
    items, cur = [], None
    for n, line in enumerate(lines[start:end], start + 1):
        m = SLIDE_RE.match(line)
        if line.startswith('# ['):
            cur = None
            items.append(('구간', line, n))
        elif m:
            a = int(m.group(1))
            b = int(m.group(2) or a)
            cur = {'줄': line, '장': list(range(a, b + 1)), '행': n, '글': []}
            items.append(('장', cur, n))
        elif cur is not None and line.strip() != '---':
            cur['글'].append(line)
        elif cur is None and line.strip() and line.strip() != '---':
            raise 멈춤(f'{path}:{n}: 장 줄 앞에 낭독이 있다 — {line[:40]}')
    seen = []
    for kind, it, n in items:
        if kind != '장':
            continue
        it['글'] = '\n'.join(it['글']).strip()
        if not any(l.strip() and not l.startswith('>') for l in it['글'].splitlines()):
            raise 멈춤(f'{path}:{n}: {it["줄"]} 장에 낭독이 없다')
        for s in it['장']:
            if seen and s <= seen[-1]:
                raise 멈춤(f'{path}:{n}: 장 번호 {s}가 앞 장({seen[-1]})보다 크지 않다 — 차례가 틀렸거나 겹친다')
            seen.append(s)
    if not seen:
        raise 멈춤(f'{path}: 장 줄(`## [SLIDE NN]`)이 하나도 없다')
    return items


def deck_slides(path):
    """덱 원고에서 장마다 화면에 보이는 글과 노트를 뽑는다."""
    slides, cur, section = {}, None, None
    for n, line in enumerate(read(path, '덱 원고').splitlines(), 1):
        m = DECK_RE.match(line)
        if m:
            cur = {'제목': m.group(2).replace(' / ', ' '), '화면': [], '노트': None, '행': n}
            slides[int(m.group(1))] = cur
            section = None
            continue
        if cur is None:
            continue
        if line.startswith('### '):
            section = line[4:].strip()
            continue
        if section != '화면 내용':
            continue
        if line.startswith('- 노트:'):
            cur['노트'] = [x.strip() for x in line[len('- 노트:'):].split(' / ') if x.strip()]
        elif line.startswith('- '):
            k, _, v = line[2:].partition(':')
            if k.strip() in SCREEN_KEYS and v.strip():
                cur['화면'].append(f'{k.strip()}: {v.strip()}')
        elif re.match(r'^\s+\d+\.\s', line):
            fields = [f.strip().replace('**', '') for f in re.sub(r'^\s+\d+\.\s*', '', line).split('|')]
            fields = [f for f in fields if f and not COORD_RE.match(f)]
            if fields:
                cur['화면'].append('- ' + ' — '.join(fields))
    for s, d in slides.items():
        d['화면'] = [x.replace('**', '') for x in d['화면']]
    return slides


def pictures(folder):
    p = Path(folder)
    if not p.is_dir():
        raise 멈춤(f'그림 폴더가 없다 — {folder}')
    found = {}
    for f in p.glob('s-*.png'):
        m = re.fullmatch(r's-(\d+)\.png', f.name)
        if m:
            found[int(m.group(1))] = f
    if not found:
        raise 멈춤(f'그림 폴더에 s-NN.png가 없다 — {folder}')
    return found


def assemble(script, deck, folder, common=None, reasons=None):
    """보낼 묶음을 만든다. 돌려주는 것: (MD 조각과 그림이 차례대로 든 목록, 보낸 장 줄 목록, 보낸 구간 줄 목록)."""
    items = script_body(script)
    slides = deck_slides(deck)
    pics = pictures(folder)
    parts, heads = [], []
    if common:
        parts.append(('글', '# 공통 자료\n\n' + read(common, '공통 자료')))
    if reasons:
        parts.append(('글', '# 다시 보내는 까닭\n\n' + read(reasons, '다시 보내는 까닭')))
    parts.append(('글', '# 대본 — 장마다 그림 · 화면에 적힌 글 · 노트 · 대본'))
    for kind, it, n in items:
        if kind == '구간':
            heads.append(it)
            parts.append(('글', it))
            continue
        heads.append(it['줄'])
        for s in it['장']:
            if s not in slides:
                raise 멈춤(f'{script}:{n}: {it["줄"]} — 덱 원고에 SLIDE {s:02d}가 없다')
            if s not in pics:
                raise 멈춤(f'{script}:{n}: {it["줄"]} — 그림 폴더에 s-{s:02d}.png가 없다')
            if slides[s]['노트'] is None:
                raise 멈춤(f'{deck}:{slides[s]["행"]}: SLIDE {s:02d}에 노트 줄(`- 노트:`)이 없다')
        block = [it['줄']]
        for s in it['장']:
            d = slides[s]
            label = f' (SLIDE {s:02d})' if len(it['장']) > 1 else ''
            parts.append(('글', '\n'.join(block + [f'### 장 그림{label}'])))
            parts.append(('그림', pics[s]))
            screen = [f'제목: {d["제목"]}'] + d['화면']
            note = d['노트']
            block = [f'### 화면에 적힌 글{label}', *screen, '', f'### 노트{label}', *note]
        parts.append(('글', '\n'.join(block + ['', '### 대본', it['글']])))
    return parts, heads


def md_view(parts):
    out = []
    for kind, v in parts:
        out.append(v if kind == '글' else f'![{v.name}]({v.name})')
    return '\n\n'.join(out) + '\n'


def result_heads(text):
    return [l for l in text.splitlines() if l.startswith('# [') or SLIDE_RE.match(l)]


def compare_heads(sent, got):
    """보낸 구간 · 장 줄과 돌아온 줄을 견준다. 어긋난 곳의 설명 목록(없으면 빈 목록)."""
    bad = []
    for i in range(max(len(sent), len(got))):
        a = sent[i] if i < len(sent) else '(없음)'
        b = got[i] if i < len(got) else '(없음)'
        if a != b:
            bad.append(f'{i + 1}번째 줄: 보낸 「{a}」 ↔ 받은 「{b}」')
    return bad


def output_text(resp):
    parts = []
    for item in resp.get('output', []):
        if item.get('type') != 'message':
            continue
        for c in item.get('content', []):
            if c.get('type') == 'output_text':
                parts.append(c.get('text', ''))
    return '\n'.join(parts).strip()


def send(model, instructions, parts, out, heads):
    content, shown = [], []
    for kind, v in parts:
        if kind == '글':
            content.append({'type': 'input_text', 'text': v})
            shown.append({'type': 'input_text', 'text': v})
        else:
            content.append({'type': 'input_image', 'image_url': 'data:image/png;base64,' + base64.b64encode(v.read_bytes()).decode('ascii')})
            shown.append({'type': 'input_image', '그림': v.name})
    body = {'model': model, 'instructions': instructions, 'input': [{'role': 'user', 'content': content}]}
    secret = key()
    chars = sum(len(v) for k, v in parts if k == '글')
    print(f'바깥검토: {model}에 보냄 — 지시 {len(instructions):,}자 · 글 {chars:,}자 · 그림 {sum(1 for k, _ in parts if k == "그림")}장', flush=True)
    req = urllib.request.Request(URL, json.dumps(body, ensure_ascii=False).encode('utf-8'),
                                 {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + secret})
    try:
        with urllib.request.urlopen(req, timeout=1800) as r:
            raw = r.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        sys.exit(f'바깥검토: HTTP {e.code} — {e.read().decode("utf-8", "replace")[:2000]}')
    except (urllib.error.URLError, TimeoutError) as e:
        sys.exit(f'바깥검토: 연결 실패 — {e}. 크레딧이 차감됐는지 확인하기 전에는 다시 보내지 않는다.')
    resp = json.loads(raw)
    result = output_text(resp)
    if not result:
        sys.exit(f'바깥검토: 응답에 글이 없다 — 상태 {resp.get("status")}, 응답 앞부분 {raw[:1500]}')
    (out / '요청.json').write_text(json.dumps({**body, 'input': [{'role': 'user', 'content': shown}]}, ensure_ascii=False, indent=1), encoding='utf-8', newline='')
    (out / '응답.json').write_text(json.dumps(resp, ensure_ascii=False, indent=1), encoding='utf-8', newline='')
    (out / '결과.md').write_text(result + '\n', encoding='utf-8', newline='')
    u = resp.get('usage') or {}
    print(f'바깥검토: 받음 — 상태 {resp.get("status")} · 입력 {u.get("input_tokens")} · 출력 {u.get("output_tokens")} 토큰 · 결과 {out / "결과.md"}')
    if heads:
        bad = compare_heads(heads, result_heads(result))
        if bad:
            print('바깥검토: 돌아온 판의 구간 · 장 줄이 보낸 대본과 다르다 — 결과는 저장했다', *bad, sep='\n  ')
            sys.exit(3)


def self_test():
    """일부러 깨뜨린 입력이 모두 걸리는지 본다(보내지 않는다)."""
    png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=')
    deck = ('# 덱\n\n## SLIDE 01 — 표지 / 둘째 줄\n### 화면 내용\n- 유형: 표지\n- 부제: 부제 글\n'
            '- 노트: [짚을 곳] 제목 / · 메모 / [다음] 2장\n### 화면 구성\n그림 설명은 보내지 않는다\n### 제작 기준\n근거 문헌은 보내지 않는다\n\n'
            '## SLIDE 02 — 본문 장\n### 화면 내용\n- 유형: 삽화\n- 메시지: **굵은** 메시지\n- 그림: figures/x.svg\n- 요소:\n'
            '  1. 오일 쿨러 | | 10.00,20.00,30.00\n  2. | **센서** | 1.0,2.0,3.0\n- 노트: [짚을 곳] 오일 쿨러 / [다음] 끝\n')
    script = ('# 제목\n\n## 촬영 전 안내 — 낭독하지 않음\n\n머리\n\n# [도입] 표지\n\n## [SLIDE 01] 표지\n\n> [핵심]\n\n첫 장 낭독.\n\n---\n\n'
              '# [이론] 본문 · 10분\n\n## [SLIDE 02] 본문 장\n\n> [핵심]\n\n둘째 장 낭독.\n\n# 촬영 본문 끝\n\n## 제작 확인용 — 낭독하지 않음\n')
    fails = []
    with tempfile.TemporaryDirectory() as td:
        t = Path(td)

        def make(name, deck_text=deck, script_text=script, pics=(1, 2)):
            d = t / name
            (d / '그림').mkdir(parents=True)
            (d / '덱.md').write_text(deck_text, encoding='utf-8')
            (d / '대본.md').write_text(script_text, encoding='utf-8')
            for i in pics:
                (d / '그림' / f's-{i:02d}.png').write_bytes(png)
            (d / '공통.md').write_text('## 1회차에서 배운 이름\n\n- 노드', encoding='utf-8')
            (d / '까닭.md').write_text('- 2장: 위치로 가리켰다', encoding='utf-8')
            return d

        def expect_stop(label, d, needle):
            try:
                assemble(d / '대본.md', d / '덱.md', d / '그림', d / '공통.md')
            except 멈춤 as e:
                if needle not in str(e):
                    fails.append(f'{label}: 멈췄지만 까닭이 다르다 — {e}')
                return
            fails.append(f'{label}: 멈추지 않았다')

        d = make('좋음')
        parts, heads = assemble(d / '대본.md', d / '덱.md', d / '그림', d / '공통.md')
        kinds = [k for k, _ in parts]
        if kinds != ['글', '글', '글', '글', '그림', '글', '글', '글', '그림', '글']:
            fails.append(f'좋은 입력: 묶음 차례가 다르다 — {kinds}')
        md = md_view(parts)
        for must in ('# 공통 자료', '제목: 표지 둘째 줄', '부제: 부제 글', '\n[짚을 곳] 제목\n· 메모\n', '메시지: 굵은 메시지', '- 오일 쿨러', '- 센서', '첫 장 낭독.', '# [이론] 본문 · 10분'):
            if must not in md:
                fails.append(f'좋은 입력: 보낸글에 「{must}」가 없다')
        for never in ('10.00,20.00', '그림 설명', '근거 문헌', 'figures/x.svg', '유형:', '**', '머리', '제작 확인용'):
            if never in md:
                fails.append(f'좋은 입력: 보낸글에 군더더기 「{never}」가 들어갔다')
        if md.index('s-01.png') > md.index('첫 장 낭독.') or md.index('첫 장 낭독.') > md.index('s-02.png'):
            fails.append('좋은 입력: 그림이 제 장 묶음 안에 있지 않다')
        rp, _ = assemble(d / '대본.md', d / '덱.md', d / '그림', d / '공통.md', d / '까닭.md')
        rmd = md_view(rp)
        if not (rmd.index('# 공통 자료') < rmd.index('# 다시 보내는 까닭') < rmd.index('# 대본')):
            fails.append('까닭: 공통 자료 뒤 · 대본 앞에 있지 않다')
        if heads != ['# [도입] 표지', '## [SLIDE 01] 표지', '# [이론] 본문 · 10분', '## [SLIDE 02] 본문 장']:
            fails.append(f'좋은 입력: 구간 · 장 줄이 다르다 — {heads}')

        expect_stop('그림 빠짐', make('그림빠짐', pics=(1,)), 's-02.png가 없다')
        expect_stop('덱 장 빠짐', make('덱빠짐', deck_text=deck.split('## SLIDE 02')[0]), 'SLIDE 02가 없다')
        expect_stop('노트 빠짐', make('노트빠짐', deck_text=deck.replace('- 노트: [짚을 곳] 오일 쿨러 / [다음] 끝\n', '')), '노트 줄')
        expect_stop('장 차례 거꾸로', make('거꾸로', script_text=script.replace('[SLIDE 01]', '[SLIDE 03]')), '차례가 틀렸거나')
        expect_stop('낭독 빈 장', make('빈장', script_text=script.replace('둘째 장 낭독.', '')), '낭독이 없다')
        expect_stop('본문 끝 표시 빠짐', make('끝빠짐', script_text=script.replace('# 촬영 본문 끝', '# 끝')), '본문을 찾지 못했다')

        got = '# [도입] 표지\n## [SLIDE 01] 표지\n본문\n## [SLIDE 02] 본문 장\n'
        if not compare_heads(heads, result_heads(got)):
            fails.append('돌아온 판에서 구간 줄이 빠졌는데 걸리지 않았다')
        if compare_heads(heads, result_heads('# [도입] 표지\n## [SLIDE 01] 표지\n# [이론] 본문 · 10분\n## [SLIDE 02] 본문 장\n')):
            fails.append('같은 줄인데 어긋났다고 했다')
    if fails:
        print('바깥검토 자가시험: 실패', *fails, sep='\n  ')
        sys.exit(1)
    print('바깥검토 자가시험: 통과 — 좋은 입력 1 · 까닭 자리 1 · 깨뜨린 입력 6 · 돌아온 판 줄 대조 2')


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--지시')
    ap.add_argument('--편')
    ap.add_argument('--덱')
    ap.add_argument('--그림폴더')
    ap.add_argument('--공통')
    ap.add_argument('--까닭')
    ap.add_argument('--글')
    ap.add_argument('--출력')
    ap.add_argument('--모델', default='gpt-6.2-astra')
    ap.add_argument('--묶기만', action='store_true')
    ap.add_argument('--자가시험', action='store_true')
    a = ap.parse_args()
    if a.자가시험:
        return self_test()
    try:
        if not a.지시 or not a.출력:
            raise 멈춤('--지시와 --출력이 있어야 한다')
        if bool(a.편) == bool(a.글):
            raise 멈춤('--편(대본 한 편)과 --글(글 한 장) 가운데 하나만 준다')
        out = Path(a.출력)
        for name in OUTPUTS:
            if (out / name).exists():
                raise 멈춤(f'{out / name}이 이미 있다 — 새 폴더를 준다(덮어쓰지 않는다)')
        instructions = read(a.지시, '지시')
        if a.편:
            if not a.덱 or not a.그림폴더:
                raise 멈춤('--편에는 --덱과 --그림폴더가 함께 있어야 한다')
            parts, heads = assemble(a.편, a.덱, a.그림폴더, a.공통, a.까닭)
        else:
            if a.덱 or a.그림폴더 or a.공통 or a.까닭:
                raise 멈춤('--글에는 --덱 · --그림폴더 · --공통 · --까닭을 주지 않는다(대본 한 편은 --편으로)')
            parts, heads = [('글', read(a.글, '글'))], []
    except 멈춤 as e:
        sys.exit(f'바깥검토: {e}')
    out.mkdir(parents=True, exist_ok=True)
    (out / '보낸글.md').write_text(md_view(parts), encoding='utf-8', newline='')
    print(f'바깥검토: 보낸글 {out / "보낸글.md"} — 장 {sum(1 for h in heads if SLIDE_RE.match(h))}개 · 그림 {sum(1 for k, _ in parts if k == "그림")}장')
    if a.묶기만:
        return
    send(a.모델, instructions, parts, out, heads)


if __name__ == '__main__':
    main()
