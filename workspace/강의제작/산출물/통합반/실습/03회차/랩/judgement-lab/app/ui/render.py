import html
FOLD = 30

JS = ('<script>document.querySelectorAll("div.tbl").forEach(function(d){var t=d.querySelector("table"),rs=[].slice.call(t.tBodies[0].rows),'
      'f=d.querySelector("input.f"),m=d.querySelector("button.more"),o=d.querySelector("button.only"),all=!m,only=false;'
      'function show(){var q=f?f.value.trim().toLowerCase():"",n=0;rs.forEach(function(r){var ok=(!q||r.textContent.toLowerCase().indexOf(q)>=0)&&(!only||r.dataset.st!=="같음");'
      'if(ok)n++;r.classList.toggle("hide",!ok||(!all&&n>' + str(FOLD) + '))})}'
      'if(f)f.addEventListener("input",show);if(m)m.addEventListener("click",function(){all=!all;m.textContent=all?"접기":"모두 보기";show()});'
      'if(o)o.addEventListener("click",function(){only=!only;o.textContent=only?"모든 줄 보기":"같음 줄 숨기기";show()});'
      '[].slice.call(t.tHead.rows[0].cells).forEach(function(th,i){th.addEventListener("click",function(){var up=th.dataset.up!=="1";th.dataset.up=up?"1":"0";'
      'rs.sort(function(a,b){var x=a.cells[i].textContent,y=b.cells[i].textContent,nx=parseFloat(x),ny=parseFloat(y);'
      'var c=(!isNaN(nx)&&!isNaN(ny))?nx-ny:x.localeCompare(y,"ko");return up?c:-c});rs.forEach(function(r){t.tBodies[0].appendChild(r)});show()})});show()})</script>')


def e(x):
    return html.escape(str(x))


def token(c):
    """띄어쓰기 없는 짧은 값(숫자 · 식별자)은 칸 안에서 꺾지 않게 표시한다."""
    s = str(c)
    return ' class="k"' if s and len(s) <= 20 and not any(ch.isspace() for ch in s) else ''


def grid(columns, rows, marks=None, compare_rows=False):
    big = len(rows) > FOLD
    head = '<tr>' + ''.join(f'<th>{e(c)}</th>' for c in columns) + '</tr>'
    body = ''
    for i, r in enumerate(rows):
        st = marks[i] if marks else ''
        body += f'<tr data-st="{e(st)}">' + ''.join(f'<td class="st-{e(str(c).split(" ")[0])}">{e(c)}</td>' if (marks and j == 1) else f'<td{token(c)}>{e(c)}</td>'
                                                    for j, c in enumerate(r)) + '</tr>'
    tools = '<input class="f" placeholder="글자로 거르기">' if len(rows) > 8 else ''
    if big:
        tools += f'<button class="t more">모두 보기</button> <small>{len(rows)}행 가운데 {FOLD}행만 보임</small>'
    if compare_rows:
        tools += '<button class="t only">같음 줄 숨기기</button>'
    return f'<div class="tbl">{tools}<table><thead>{head}</thead><tbody>{body}</tbody></table></div>'


def render_block(b, previous, current):
    k = b['kind']
    title = f'<h3>{e(b["title"])}</h3>' if b.get('title') else ''
    tail = f'<p class="note">{e(b["note"])}</p>' if b.get('note') else ''
    if k == 'note':
        return f'<p class="note">{e(b["text"])}</p>'
    if k == 'error':
        return f'{title}<div class="err">{e(b["text"])}</div>'
    if k == 'source':
        return title + '<div class="src">' + '\n'.join(f'<b>{n}</b>{e(t)}' for n, t in b['lines']) + '</div>'
    if k == 'table':
        return title + grid(b['columns'], b['rows']) + tail
    if k == 'counts':
        return title + grid(['항목', '개수'], b['items']) + tail
    if k == 'compare':
        cols = [('질문 · 입력 · 항목' if b['key'] == '짝' else b['key']), '견줌'] + [f'{c} — {side}' for c in b['columns'] for side in ('기대', '실제')]
        rows = [[r['key'], r['state']] + [v for pair in r['cells'] for v in pair] for r in b['rows']]
        marks = [r['state'] for r in b['rows']]
        summary = ' · '.join(f'{s} {marks.count(s)}' for s in ('같음', '다름', '실제 없음', '기대 밖') if marks.count(s))
        return title + f'<p class="note">{e(summary or "견줄 행 없음")}</p>' + grid(cols, rows, marks, True) + tail
    if k == 'diff':
        if not b['rows']:
            return title + f'<p class="note">늘어남 · 사라짐 · 값 바뀜 없음(같은 항목 {b["same"]}개)</p>' + tail
        return title + f'<p class="note">같은 항목 {b["same"]}개</p>' + grid(['항목', '바뀜', '전', '후'], b['rows'], [r[1] for r in b['rows']]) + tail
    raise ValueError(f'모르는 블록 종류 {k!r}')

CSS = '*{box-sizing:border-box}body{margin:0;background:#181b20;color:#e6eaf0;font:16px/1.65 "Malgun Gothic",sans-serif}main{max-width:1240px;margin:auto;padding:30px 24px}h1{font-size:28px;margin:0}h2{font-size:22px}h3{font-size:17px;margin:0 0 14px}section{margin:18px 0;padding:20px;background:#232830;border:1px solid #3b424e;border-radius:10px;overflow:auto}.tbl{overflow:auto}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:9px 12px;border-bottom:1px solid #3b424e;text-align:left;vertical-align:top}th{background:#303743;cursor:pointer}td{overflow-wrap:break-word}td.k{white-space:nowrap}tr.hide{display:none}.note,small{color:#b6c1d0}.note,.err{white-space:pre-wrap}.err{border-left:4px solid #ff8e88;padding:12px;background:#422b2d}.st-같음{color:#8cdbbc}.st-다름,.st-실제,.st-사라짐{color:#ffaaa4}.st-기대,.st-늘어남,.st-값{color:#eac77b}input.f,button.t{font:inherit;color:#e6eaf0;background:#303743;border:1px solid #687589;border-radius:6px;padding:5px 10px;margin:0 8px 12px 0}input.f{max-width:100%}.src{white-space:pre-wrap;font-family:Consolas,monospace}.src b{display:inline-block;width:4em;color:#a5b3c5}@media(max-width:600px){main{padding:18px 12px}section{padding:14px}h1{font-size:24px}}th{white-space:nowrap}td{word-break:keep-all}td[class^="st-"]{white-space:nowrap}.tbl:has(button.only) td:first-child{min-width:210px}'

def page(title, action, blocks):
    body = ''.join('<section>' + render_block(b, {}, {}) + '</section>' for b in blocks)
    return ('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{e(action)} · {e(title)}</title><style>{CSS}</style><main><small>{e(title)}</small>'
            f'<h1>{e(action)}</h1>{body}</main>{JS}</html>')
