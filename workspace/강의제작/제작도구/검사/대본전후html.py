"""언제: 이론 대본 · 덱을 고치거나 새로 쓴 판을 사용자에게 확정받을 때(hyd-task 3-5) — 장마다 새 장 그림과 낭독, 옛 판과의 전후를 한 HTML에 담는다.

쓰는 법: <py> workspace/강의제작/제작도구/검사/대본전후html.py <설정.json> <출력.html>

설정 JSON(옛대본은 git 판 「refs/…:경로」 · 「커밋:경로」 또는 파일 경로):
{
  "제목": "…",
  "머리": "머리말 마크다운 파일 경로(문단 · '- ' 목록 · '## ' 제목 · '**굵게**'만 읽는다)",
  "편": [
    {
      "이름": "2회차 01편 · 클래스와 인스턴스",
      "대본": "workspace/…/01_이론_클래스와인스턴스.md",           # 지금 판(작업 트리)
      "옛대본": "refs/heads/workspace:workspace/…/01_….md",      # git 판(ref:경로) 또는 파일 경로
      "꼴": "새로" | "고침",       # 새로: 새 낭독을 본문으로 · 옛 낭독은 접어 둠 / 고침: 낱말 단위 전후(지운 말 · 넣은 말)
      "새그림": "작업/…/렌더/새판",   # 새 판 장 그림 폴더(s-NN.png)
      "옛그림": "workspace/…/슬라이드/통합반_02일차",  # 옛 판 장 그림 폴더(화면이 바뀐 장만 옛 그림을 함께 보인다)
      "화면바뀐장": [29, 39, 48, 69],
      "옛장": {"64": null, "65": 64},  # 새 장 번호 → 옛 장 번호(없으면 같은 번호, null이면 옛 판에 없는 새 장)
      "옛장밀림": [[65, 73, -1]],      # [시작, 끝, 더할 값] — 새 장 65~73은 옛 장 64~72
      "장": [1, 26],                 # 보일 장 범위(없으면 대본이 덮는 전부)
      "바뀐장만": false              # 고침 꼴에서 낭독 · 화면이 같은 장은 뺄지
    }
  ]
}
장 그림은 가로 900점 JPEG로 줄여 HTML 안에 넣는다(파일 하나로 보내려고). 읽기만 하고 대본 · 덱을 고치지 않는다.
"""
import base64, difflib, html, io, json, re, subprocess, sys
from pathlib import Path

from PIL import Image

E = html.escape


def read_src(src):
    rev = src.split(':', 1)[0] if ':' in src else ''
    if rev.startswith('refs/') or re.fullmatch(r'[0-9a-f]{7,40}(~\d+)?', rev):
        return subprocess.run(['git', 'show', src], capture_output=True, check=True).stdout.decode('utf-8')
    return Path(src).read_bytes().decode('utf-8')


def blocks(text):
    """## [SLIDE NN] 구획 → {장: (제목, [낭독 문단])}. `>` 줄 · 빈 문단은 뺀다. 촬영 본문 끝에서 멈춘다."""
    text = text.split('\n# 촬영 본문 끝')[0]
    out = {}
    for m in re.finditer(r'^## \[SLIDE (\d+)(?:~(\d+))?\]([^\n]*)\n(.*?)(?=^---\s*$|^## \[SLIDE|^# |\Z)', text, re.S | re.M):
        paras = [p.strip() for p in re.split(r'\n\s*\n', m[4]) if p.strip() and not p.strip().startswith('>')]
        n0, n1 = int(m[1]), int(m[2] or m[1])
        out[n0] = (m[3].strip(), paras, n1)
    return out


def img(path, width=900):
    p = Path(path)
    if not p.exists():
        return None
    im = Image.open(p).convert('RGB')
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)))
    buf = io.BytesIO()
    im.save(buf, 'JPEG', quality=72)
    return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()


def words_diff(a, b):
    sa, sb = re.findall(r'\S+|\s+', a), re.findall(r'\S+|\s+', b)
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, sa, sb, autojunk=False).get_opcodes():
        if op == 'equal':
            out.append(E(''.join(sa[i1:i2])))
        if op in ('delete', 'replace'):
            out.append('<del>' + E(''.join(sa[i1:i2])) + '</del>')
        if op in ('insert', 'replace'):
            out.append('<ins>' + E(''.join(sb[j1:j2])) + '</ins>')
    return ''.join(out)


def md(text):
    out, lst = [], []

    def inline(s):
        return re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', E(s))

    def flush():
        if lst:
            out.append('<ul>' + ''.join(f'<li>{inline(x)}</li>' for x in lst) + '</ul>')
            lst.clear()
    for para in re.split(r'\n\s*\n', text.strip()):
        for line in para.split('\n'):
            if line.startswith('- '):
                lst.append(line[2:])
                continue
            flush()
            if line.startswith('## '):
                out.append(f'<h2>{inline(line[3:])}</h2>')
            elif line.startswith('### '):
                out.append(f'<h3>{inline(line[4:])}</h3>')
            elif line.strip():
                out.append(f'<p>{inline(line)}</p>')
        flush()
    return '\n'.join(out)


def old_no(n, sec):
    m = sec.get('옛장', {})
    if str(n) in m:
        return m[str(n)]
    for a, b, d in sec.get('옛장밀림', []):
        if a <= n <= b:
            return n + d
    return n


def section(sec):
    new = blocks(read_src(sec['대본']))
    old = blocks(read_src(sec['옛대본'])) if sec.get('옛대본') else {}
    lo, hi = sec.get('장', [min(new), max(new)])
    mode, changed_screens = sec.get('꼴', '새로'), set(sec.get('화면바뀐장', []))
    parts, n_shown = [f'<section><h2 class="sec">{E(sec["이름"])}</h2>'], 0
    whole = []
    for n in sorted(k for k in new if lo <= k <= hi):
        title, paras, n_end = new[n]
        on = old_no(n, sec)
        ot, op = (old[on][0], old[on][1]) if on is not None and on in old else ('', [])
        same_text = '\n\n'.join(paras) == '\n\n'.join(op)
        # 고침 꼴이라도 장을 통째로 다시 쓴 장(옛 낭독과 닮은 정도가 절반 아래)은 낱말 전후가 뒤엉켜 읽을 수 없으므로 새로 꼴로 보인다
        rewritten = mode == '고침' and op and not same_text and difflib.SequenceMatcher(None, '\n'.join(op), '\n'.join(paras), autojunk=False).ratio() < 0.5
        if mode == '고침' and sec.get('바뀐장만') and same_text and n not in changed_screens:
            continue
        n_shown += 1
        label = f'{n}' if n_end == n else f'{n}~{n_end}'
        tag = ''
        if on is None:
            tag = '<span class="tag new">새 장</span>'
        elif n in changed_screens:
            tag = '<span class="tag scr">화면 바뀜</span>'
        if mode == '고침' and not same_text and op:
            tag += '<span class="tag txt">' + ('낭독 새로 씀' if rewritten else '낭독 바뀜') + '</span>'
        rewritten = rewritten or (mode == '고침' and not op)   # 옛 판에 없는 새 장은 새 낭독만 보인다
        parts.append(f'<article id="s{sec.get("키", "")}{n}"><h3>{label}장 · {E(title)} {tag}</h3>')
        nimg = img(Path(sec['새그림']) / f's-{n:02d}.png') if sec.get('새그림') else None
        oimg = img(Path(sec['옛그림']) / f's-{on:02d}.png') if (n in changed_screens and on and sec.get('옛그림')) else None
        if oimg and nimg:
            parts.append(f'<div class="two"><figure><img src="{oimg}"><figcaption>옛 화면</figcaption></figure><figure><img src="{nimg}"><figcaption>새 화면</figcaption></figure></div>')
        elif nimg:
            parts.append(f'<figure><img src="{nimg}"></figure>')
        if mode == '새로' or rewritten:
            parts.append('<div class="say">' + ''.join(f'<p>{E(p)}</p>' for p in paras) + '</div>')
            if op:
                parts.append('<details><summary>옛 판 낭독 보기</summary><div class="old">' + ''.join(f'<p>{E(p)}</p>' for p in op) + '</div></details>')
        else:
            if same_text:
                parts.append('<div class="say">' + ''.join(f'<p>{E(p)}</p>' for p in paras) + '</div>')
            else:
                parts.append('<div class="say">' + ''.join(f'<p>{x}</p>' for x in words_diff('\n\n'.join(op), '\n\n'.join(paras)).split('\n\n')) + '</div>')
        parts.append('</article>')
        whole.append(f'<h4>{label}장</h4>' + ''.join(f'<p>{E(p)}</p>' for p in paras))
    if mode == '새로':
        parts.insert(1, '<details class="whole"><summary>이 편을 그림 없이 처음부터 끝까지 이어 읽기</summary>' + ''.join(whole) + '</details>')
    parts.append('</section>')
    return '\n'.join(parts), n_shown


CSS = """
body{font-family:'Malgun Gothic',sans-serif;max-width:980px;margin:24px auto;padding:0 16px;color:#1d2433;line-height:1.75}
h1{font-size:26px} h2{margin-top:36px} h2.sec{border-bottom:3px solid #1d4f91;padding-bottom:6px}
article{border:1px solid #d9dee8;border-radius:10px;padding:14px 18px;margin:18px 0;background:#fff}
article h3{margin:0 0 10px;font-size:18px}
figure{margin:8px 0} img{max-width:100%;border:1px solid #ccd3df;border-radius:6px}
.two{display:grid;grid-template-columns:1fr 1fr;gap:10px} figcaption{font-size:13px;color:#5b6575;text-align:center}
.say p{margin:8px 0} .old p{color:#5b6575;margin:6px 0}
del{background:#ffe1e1;color:#a11;text-decoration:line-through} ins{background:#dcf5dc;color:#11621a;text-decoration:none}
.tag{font-size:12px;border-radius:10px;padding:2px 8px;margin-left:6px;vertical-align:middle}
.new{background:#1d4f91;color:#fff} .scr{background:#f2b33d;color:#3a2a00} .txt{background:#e5ebf5;color:#1d4f91}
details{margin:8px 0} summary{cursor:pointer;color:#1d4f91} .whole{background:#f6f8fb;padding:10px 14px;border-radius:8px}
nav a{margin-right:14px}
"""


def main():
    cfg = json.loads(Path(sys.argv[1]).read_bytes().decode('utf-8'))
    out = [f'<!doctype html><html lang="ko"><meta charset="utf-8"><title>{E(cfg["제목"])}</title><style>{CSS}</style><body><h1>{E(cfg["제목"])}</h1>']
    if cfg.get('머리'):
        out.append(md(Path(cfg['머리']).read_bytes().decode('utf-8')))
    out.append('<nav>' + ''.join(f'<a href="#sec{i}">{E(s["이름"])}</a>' for i, s in enumerate(cfg['편'])) + '</nav>')
    total = 0
    for i, sec in enumerate(cfg['편']):
        sec.setdefault('키', f'{i}-')
        body, k = section(sec)
        out.append(f'<a id="sec{i}"></a>' + body)
        total += k
        print(f'{sec["이름"]}: 장 {k}개')
    out.append('</body></html>')
    Path(sys.argv[2]).write_bytes('\n'.join(out).encode('utf-8'))
    print(f'만듦 {sys.argv[2]} — 장 {total}개, {Path(sys.argv[2]).stat().st_size // 1024} KB')


if __name__ == '__main__':
    main()
