"""결과 화면 — 이 실습 폴더의 제공 흐름을 정할 자리가 채워진 단계까지 돌리고 `결과/보기.html`을 다시 쓴다.

사용:  python show_result.py            (처음 한 번은 브라우저로 연다 — 그 뒤에는 브라우저에서 F5)
       python show_result.py --no-open  (브라우저를 열지 않는다)

단계 목록과 단계마다 돌릴 일은 같은 폴더의 lab_steps.py가 정한다(TITLE, STEPS). 이 파일은 모든 실습에서 같다.
정할 자리 = `결과/` 아래 첫머리에 「제공 빈 틀」 표시가 있는 파일. 비어 있는 자리가 있는 단계에서 멈추고, 그 뒤 단계는 돌리지 않는다.
실패한 단계가 있으면 그 칸을 빨갛게 쓰고 종료 코드 1로 끝난다. 서버 · 설치 · 인터넷 없이 파이썬 표준 라이브러리만 쓴다.
"""
from pathlib import Path
import csv
import html
import importlib
import io
import json
import os
import re
import sys
import traceback
import webbrowser

HERE = Path(__file__).resolve().parent
OUT = HERE / '결과' / '보기.html'
SNAP = HERE / '결과' / '.보기_이전.json'
CHOSEN = HERE / '결과' / '정한_것.csv'
MARK = '제공 빈 틀'
FOLD = 30          # 이보다 행이 많은 표는 접어 두고 「모두 보기」로 편다


class Stop(Exception):
    """단계를 멈추는 알려진 까닭(계약 어긋남 · 랩 DB 꺼짐). 글은 그대로 화면에 빨갛게 쓴다."""


class Blank(Stop):
    """정할 자리 파일 안에서 이 단계 몫이 아직 비었음(예: 조회 파일에 이 질문의 조회가 아직 없음). 상태 「비어 있음」."""


# ───────────── 읽기 도우미(lab_steps.py가 import해서 쓴다) ─────────────
def rel(path):
    """화면에 쓰는 경로 — 이 폴더 기준 상대 경로(절대 경로를 쓰지 않는다)."""
    p = Path(path)
    try:
        return p.resolve().relative_to(HERE).as_posix()
    except ValueError:
        return p.name


def read_text(path):
    """(글, 글자 방식). UTF-8(BOM 포함)로 읽고, 안 되면 CP949로 읽는다 — 어느 쪽으로 읽었는지 함께 돌려준다."""
    data = Path(path).read_bytes()
    try:
        return data.decode('utf-8-sig'), 'UTF-8'
    except UnicodeDecodeError:
        return data.decode('cp949'), 'CP949'


def read_table(path):
    """CSV 한 장 → [dict]. 첫머리의 # 줄(「제공 빈 틀」 표시 · 설명)은 건너뛰고, 칸 앞뒤 공백은 정리한다."""
    text, _ = read_text(path)
    kept = [(no, x) for no, x in enumerate(text.splitlines(), 1) if x.strip() and not x.lstrip().startswith('#')]
    if not kept:
        raise Stop(f'{rel(path)}: 열 이름 줄이 없습니다 — 받은 빈 틀의 열 이름 줄을 지우지 않습니다.')
    rows = []
    reader = csv.DictReader(io.StringIO('\n'.join(x for _, x in kept)))
    for row in reader:
        line = kept[reader.line_num - 1][0]      # 건너뛴 # 줄 · 빈 줄을 셈에 넣은 실제 파일 줄 번호
        if None in row and list(row)[-2:-1] == ['근거']:      # 맨 끝 「근거」 칸 글에 쉼표가 든 경우 — 남은 칸을 근거에 이어 붙인다
            row['근거'] = ','.join([row['근거'] or '', *row.pop(None)])
        if None in row:
            raise Stop(f'{rel(path)}:{line}: 칸 수가 열 이름보다 많습니다(쉼표가 든 값은 큰따옴표로 감쌉니다).')
        rows.append({k.strip(): (v or '').strip() for k, v in row.items() if k is not None})
    return rows


def read_json(path):
    try:
        return json.loads(read_text(path)[0])
    except json.JSONDecodeError as e:
        raise Stop(f'{rel(path)}:{e.lineno}: JSON 꼴이 아닙니다 — {e.msg}')


def is_blank(path):
    """정할 자리가 아직 비었는가. .py = 본문이 NotImplementedError인 함수가 남음, 표(.csv) = 데이터 행 0,
    .cypher · .md · .txt = 주석 · 「제공 빈 틀」 줄 말고 글이 없음, .json = 빈 값."""
    p = Path(path)
    if not p.is_file():
        raise Stop(f'{rel(p)}: 정할 자리 파일이 없습니다 — 받은 ZIP의 빈 틀을 지우지 않습니다.')
    text, _ = read_text(p)
    if p.suffix == '.py':
        return 'NotImplementedError' in text
    if p.suffix == '.csv':
        return not read_table(p)
    if p.suffix == '.json':
        value = read_json(p)
        return value in ({}, [], None, '') or (isinstance(value, dict) and all(v in ('', None, [], {}) for v in value.values()))
    body = [x for x in text.splitlines() if x.strip() and not x.strip().startswith(('//', '#', '>', '--')) and MARK not in x]
    return not body


def blank_functions(path):
    """빈 함수 파일에서 아직 NotImplementedError인 함수 이름."""
    names, current = [], None
    for line in read_text(path)[0].splitlines():
        m = re.match(r'def (\w+)\(', line)
        if m:
            current = m.group(1)
        elif current and 'NotImplementedError' in line:
            names.append(current)
            current = None
    return names


def source_lines(path, start, end=None):
    """원문 줄 보기 블록 — (파일, 줄 범위)를 줄 번호와 함께. 글자 방식을 함께 적는다."""
    text, enc = read_text(path)
    lines = text.splitlines()
    end = end or start
    if not 1 <= start <= end <= len(lines):
        raise Stop(f'{rel(path)}: {start}~{end}줄이 없습니다(전체 {len(lines)}줄).')
    return {'kind': 'source', 'title': f'{rel(path)} {start}' + (f'~{end}' if end != start else '') + f'줄 ({enc})',
            'lines': [(n, lines[n - 1]) for n in range(start, end + 1)]}


# ───────────── 블록(lab_steps.py의 run이 돌려준다) ─────────────
def table(title, columns, rows, note=''):
    """표. rows = [[칸, …]] 또는 [dict]. 행이 많으면 접고, 글자 거르기 · 정렬을 붙인다."""
    rows = [[r.get(c, '') for c in columns] if isinstance(r, dict) else list(r) for r in rows]
    return {'kind': 'table', 'title': title, 'columns': list(columns), 'rows': rows, 'note': note}


def counts(title, items, note=''):
    """개수 — items = [(이름, 값)]. 직전 실행의 같은 이름 값과 나란히 보인다(전후 비교)."""
    return {'kind': 'counts', 'title': title, 'items': [(str(k), v) for k, v in items], 'note': note}


def compare(title, key, expected, actual, columns, note=''):
    """기대 ↔ 실제 대조. expected · actual = [dict], key = 짝을 짓는 열, columns = 견줄 열.
    칸 글자는 앞뒤 · 겹친 공백만 정리해 견준다. 행마다 같음 · 다름 · 실제 없음 · 기대 밖."""
    def norm(v):
        return re.sub(r'\s+', ' ', str(v if v is not None else '')).strip()
    for side, data in (('기대', expected), ('실제', actual)):
        keys = [norm(r.get(key)) for r in data]
        twice = sorted({k for k in keys if keys.count(k) > 1})
        if twice:      # 조용히 한 줄만 남기지 않는다
            raise Stop(f'{title}: {side} 쪽에 같은 짝이 두 번 있습니다 — ' + ', '.join(twice))
    exp = {norm(r.get(key)): r for r in expected}
    act = {norm(r.get(key)): r for r in actual}
    rows = []
    for k in list(exp) + [k for k in act if k not in exp]:
        e, a = exp.get(k), act.get(k)
        if e is None:
            state = '기대 밖'
        elif a is None:
            state = '실제 없음'
        else:
            state = '같음' if all(norm(e.get(c)) == norm(a.get(c)) for c in columns) else '다름'
        rows.append({'key': k, 'state': state, 'cells': [(norm(e.get(c)) if e else '', norm(a.get(c)) if a else '') for c in columns]})
    return {'kind': 'compare', 'title': title, 'key': key, 'columns': list(columns), 'rows': rows, 'note': note}


def before_after(title, before, after, note=''):
    """전후 비교 — before · after = {이름: 값}. 늘어남 · 사라짐 · 값 바뀜만 표로."""
    rows = []
    for k in sorted(set(before) | set(after)):
        if k not in before:
            rows.append((k, '늘어남', '', after[k]))
        elif k not in after:
            rows.append((k, '사라짐', before[k], ''))
        elif before[k] != after[k]:
            rows.append((k, '값 바뀜', before[k], after[k]))
    return {'kind': 'diff', 'title': title, 'rows': [[str(c) if not isinstance(c, str) else c for c in r] for r in rows],
            'same': len(set(before) & set(after)) - sum(r[1] == '값 바뀜' for r in rows), 'note': note}


def note(text):
    return {'kind': 'note', 'text': text}


def error(title, text):
    return {'kind': 'error', 'title': title, 'text': text}


# ───────────── 돌리기 ─────────────
def where(exc):
    """예외가 난 곳 가운데 이 폴더 안 파일의 마지막 줄(파일:줄)."""
    for frame in reversed(traceback.extract_tb(exc.__traceback__)):
        try:
            return f'{Path(frame.filename).resolve().relative_to(HERE).as_posix()}:{frame.lineno}'
        except ValueError:
            continue
    return ''


def run_steps(steps, previous):
    """단계마다 (번호, 이름, 상태, 블록). 상태 = 비어 있음 · 채움 · 오류 · 아직 · 볼 것 없음."""
    out, stopped = [], None
    for s in steps:
        no, name, slots, run = s['no'], s['name'], s.get('slots', []), s.get('run')
        if stopped:
            out.append((no, name, '아직', [note(f'{stopped}단계를 먼저 채웁니다.')]))
            continue
        try:
            empty = [rel(HERE / p) for p in slots if is_blank(HERE / p)]
        except Stop as e:
            out.append((no, name, '오류', [error('정할 자리를 읽지 못했습니다', str(e))]))
            stopped = no
            continue
        if empty:
            detail = []
            for p in slots:
                if (HERE / p).suffix == '.py' and rel(HERE / p) in empty:
                    detail.append(f'{rel(HERE / p)} — 아직 비어 있는 함수: ' + ', '.join(blank_functions(HERE / p)))
                elif rel(HERE / p) in empty:
                    detail.append(f'{rel(HERE / p)} — 아직 비어 있음')
            out.append((no, name, '비어 있음', [note('이 단계의 정할 자리를 채운 뒤 다시 실행합니다.\n' + '\n'.join(detail))]))
            stopped = no
            continue
        if run is None:
            out.append((no, name, '볼 것 없음' if not slots else '채움', []))
            continue
        try:
            blocks = run(previous) or []
            state = '채움' if slots else ('결과 보기' if blocks else '볼 것 없음')
            if any(b['kind'] == 'error' for b in blocks):
                state = '오류'
        except Blank as e:
            blocks, state = [note('이 단계의 정할 자리를 채운 뒤 다시 실행합니다.\n' + str(e))], '비어 있음'
        except Stop as e:
            blocks, state = [error('멈춤', str(e))], '오류'
        except Exception as e:        # 제공 흐름이 정할 자리 코드를 부르다 난 오류 — 파일:줄과 함께 그대로 보인다
            blocks, state = [error(f'실행 오류 {where(e)}', f'{type(e).__name__}: {e}')], '오류'
        out.append((no, name, state, blocks))
        if state in ('오류', '비어 있음'):
            stopped = no
    return out


def chosen_rows():
    if not CHOSEN.is_file():
        return None
    try:
        return read_table(CHOSEN)
    except Stop as e:
        return str(e)


# ───────────── HTML ─────────────
CSS = ('*{box-sizing:border-box}body{margin:0;background:#f4f6f3;color:#20342f;font:16px/1.7 "Malgun Gothic",sans-serif}'
       'main{max-width:1180px;margin:auto;padding:28px 20px}h1{font-size:26px;margin:0 0 6px}h2{font-size:20px;margin:0 0 10px}h3{font-size:16px;margin:16px 0 6px}'
       'section{background:#fff;border:1px solid #dce5df;border-radius:12px;padding:18px 20px;margin:16px 0}'
       '.band{display:flex;flex-wrap:wrap;gap:6px;margin:12px 0}.band a{padding:4px 10px;border-radius:14px;text-decoration:none;font-size:14px;border:1px solid #c9d6cf;color:#20342f}'
       '.s-채움,.s-볼{background:#e2eee7}.s-비어{background:#fff7e0;border-color:#e3c56b!important}.s-오류{background:#fde4e1;border-color:#d0574a!important}.s-아직{background:#f0f0f0;color:#7b8781!important}'
       'table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:6px 8px;border-bottom:1px solid #e3e9e5;text-align:left;vertical-align:top}'
       'th{background:#eef3f0;cursor:pointer;position:sticky;top:0}tr.hide{display:none}.st-같음{color:#1f6b4d}.st-다름,.st-사라짐,.st-실제{color:#b3392c;font-weight:bold}'
       '.st-기대,.st-늘어남,.st-값{color:#8a5a00;font-weight:bold}.err{border-left:4px solid #d0574a;background:#fdf1ef;padding:10px 14px;white-space:pre-wrap}'
       '.note{color:#4b5c55;white-space:pre-wrap}.src{font-family:Consolas,monospace;font-size:14px;background:#f6f8f7;padding:8px;white-space:pre-wrap}'
       '.src b{color:#8a9a92;font-weight:normal;display:inline-block;width:3.5em}input.f{margin:4px 0 8px;padding:4px 8px;border:1px solid #c9d6cf;border-radius:6px;width:16em}'
       'button.t{margin:0 0 8px 6px;padding:3px 10px;border:1px solid #176554;background:#fff;color:#176554;border-radius:6px;cursor:pointer}small{color:#607269}')
JS = ('<script>document.querySelectorAll("div.tbl").forEach(function(d){var t=d.querySelector("table"),rs=[].slice.call(t.tBodies[0].rows),'
      'f=d.querySelector("input.f"),m=d.querySelector("button.more"),o=d.querySelector("button.only"),all=!m,only=false;'
      'function show(){var q=f?f.value.trim().toLowerCase():"",n=0;rs.forEach(function(r){var ok=(!q||r.textContent.toLowerCase().indexOf(q)>=0)&&(!only||r.dataset.st!=="같음");'
      'if(ok)n++;r.classList.toggle("hide",!ok||(!all&&n>' + str(FOLD) + '))})}'
      'if(f)f.addEventListener("input",show);if(m)m.addEventListener("click",function(){all=!all;m.textContent=all?"접기":"모두 보기";show()});'
      'if(o)o.addEventListener("click",function(){only=!only;o.textContent=only?"모든 줄":"다른 줄만";show()});'
      '[].slice.call(t.tHead.rows[0].cells).forEach(function(th,i){th.addEventListener("click",function(){var up=th.dataset.up!=="1";th.dataset.up=up?"1":"0";'
      'rs.sort(function(a,b){var x=a.cells[i].textContent,y=b.cells[i].textContent,nx=parseFloat(x),ny=parseFloat(y);'
      'var c=(!isNaN(nx)&&!isNaN(ny))?nx-ny:x.localeCompare(y,"ko");return up?c:-c});rs.forEach(function(r){t.tBodies[0].appendChild(r)});show()})});show()})</script>')


def e(x):
    return html.escape(str(x))


def grid(columns, rows, marks=None, compare_rows=False):
    big = len(rows) > FOLD
    head = '<tr>' + ''.join(f'<th>{e(c)}</th>' for c in columns) + '</tr>'
    body = ''
    for i, r in enumerate(rows):
        st = marks[i] if marks else ''
        body += f'<tr data-st="{e(st)}">' + ''.join(f'<td class="st-{e(str(c).split(" ")[0])}">{e(c)}</td>' if (marks and j == 1) else f'<td>{e(c)}</td>'
                                                    for j, c in enumerate(r)) + '</tr>'
    tools = '<input class="f" placeholder="글자로 거르기">' if len(rows) > 8 else ''
    if big:
        tools += f'<button class="t more">모두 보기</button> <small>{len(rows)}행 가운데 {FOLD}행만 보임</small>'
    if compare_rows:
        tools += '<button class="t only">다른 줄만</button>'
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
        key = 'counts:' + b['title']
        before = dict(previous.get(key, []))
        current[key] = b['items']
        rows = [[name, value, before.get(name, '—'), '' if name not in before else ('같음' if before[name] == value else '바뀜')] for name, value in b['items']]
        return title + grid(['항목', '이번 실행', '직전 실행', '견줌'], rows) + tail
    if k == 'compare':
        cols = ['짝(' + b['key'] + ')', '견줌'] + [f'{c} — {side}' for c in b['columns'] for side in ('기대', '실제')]
        rows = [[r['key'], r['state']] + [v for pair in r['cells'] for v in pair] for r in b['rows']]
        marks = [r['state'] for r in b['rows']]
        summary = ' · '.join(f'{s} {marks.count(s)}' for s in ('같음', '다름', '실제 없음', '기대 밖') if marks.count(s))
        return title + f'<p class="note">{e(summary or "견줄 행 없음")}</p>' + grid(cols, rows, marks, True) + tail
    if k == 'diff':
        if not b['rows']:
            return title + f'<p class="note">늘어남 · 사라짐 · 값 바뀜 없음(같은 항목 {b["same"]}개)</p>' + tail
        return title + f'<p class="note">같은 항목 {b["same"]}개</p>' + grid(['항목', '바뀜', '전', '후'], b['rows'], [r[1] for r in b['rows']]) + tail
    raise ValueError(f'모르는 블록 종류 {k!r}')


def page(title, results, chosen, previous):
    current = {}
    band = ''.join(f'<a class="s-{e(state.split(" ")[0])}" href="#s{no}">{no:02d} {e(name)} · {e(state)}</a>' for no, name, state, _ in results)
    if chosen is None:
        side = '<p class="note">결과/정한_것.csv가 없습니다.</p>'
    elif isinstance(chosen, str):
        side = f'<div class="err">{e(chosen)}</div>'
    elif not chosen:
        side = '<p class="note">아직 적은 행이 없습니다.</p>'
    else:
        cols = list(chosen[0].keys())
        side = grid(cols, [[r.get(c, '') for c in cols] for r in chosen])
    body = ''
    for no, name, state, blocks in results:
        inner = ''.join(render_block(b, previous, current) for b in blocks) or '<p class="note">이 단계는 화면에 보일 결과가 없습니다.</p>'
        body += f'<section id="s{no}"><h2>{no:02d} {e(name)} <small>· {e(state)}</small></h2>{inner}</section>'
    doc = (f'<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
           f'<title>{e(title)} — 결과</title><style>{CSS}</style><main><small>HYD · 실습 결과 화면</small><h1>{e(title)}</h1>'
           '<p class="note">python show_result.py를 다시 실행하면 이 화면이 새로 써집니다. 브라우저에서 F5를 누릅니다.</p>'
           f'<div class="band">{band}</div><section><h2>정한 것 <small>· 결과/정한_것.csv</small></h2>{side}</section>{body}</main>{JS}</html>\n')
    return doc, current


def write(open_browser=True):
    sys.path.insert(0, str(HERE))
    # python show_result.py로 실행하면 이 파일은 __main__이다. lab_steps.py의 `import show_result as R`가 같은 모듈(같은 Stop · Blank)을 받게 한다.
    sys.modules.setdefault('show_result', sys.modules[__name__])
    steps_module = importlib.import_module('lab_steps')
    previous = {}
    if SNAP.is_file():
        try:
            previous = json.loads(SNAP.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            previous = {}
    results = run_steps(steps_module.STEPS, previous)
    doc, current = page(steps_module.TITLE, results, chosen_rows(), previous)
    first = not OUT.exists()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_name(OUT.name + '.tmp')
    tmp.write_text(doc, encoding='utf-8', newline='\n')
    os.replace(tmp, OUT)
    SNAP.write_text(json.dumps(current, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
    for no, name, state, blocks in results:
        line = f'{no:02d} {name}: {state}'
        print(line)
        for b in blocks:
            if b['kind'] == 'error':
                print('    ' + b['title'] + ' — ' + b['text'].replace('\n', '\n    '))
    print(f'결과/보기.html을 다시 썼습니다 — 브라우저에서 F5를 누릅니다.')
    if first and open_browser:
        webbrowser.open(OUT.as_uri())
    return 1 if any(state == '오류' for _, _, state, _ in results) else 0


if __name__ == '__main__':
    sys.exit(write(open_browser='--no-open' not in sys.argv[1:]))
