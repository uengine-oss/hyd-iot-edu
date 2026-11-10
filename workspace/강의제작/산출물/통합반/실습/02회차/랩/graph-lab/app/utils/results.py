from pathlib import Path
import csv, io, json, re, traceback
HERE = Path(__file__).resolve().parents[2]

class Stop(Exception):
    """단계를 멈추는 알려진 까닭(계약 어긋남 · 랩 DB 꺼짐). 글은 그대로 화면에 빨갛게 쓴다."""


class Blank(Stop):
    """정할 자리 파일 안에서 이 단계 몫이 아직 비었음(예: 조회 파일에 이 질문의 조회가 아직 없음). 해당 조회를 작성한 뒤 실행한다."""


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


def source_lines(path, start, end=None):
    """원문 줄 보기 블록 — (파일, 줄 범위)를 줄 번호와 함께. 글자 방식을 함께 적는다."""
    text, enc = read_text(path)
    lines = text.splitlines()
    end = end or start
    if not 1 <= start <= end <= len(lines):
        raise Stop(f'{rel(path)}: {start}~{end}줄이 없습니다(전체 {len(lines)}줄).')
    return {'kind': 'source', 'title': f'{rel(path)} {start}' + (f'~{end}' if end != start else '') + f'줄 ({enc})',
            'lines': [(n, lines[n - 1]) for n in range(start, end + 1)]}


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


def where(exc):
    """예외가 난 곳 가운데 이 폴더 안 파일의 마지막 줄(파일:줄)."""
    for frame in reversed(traceback.extract_tb(exc.__traceback__)):
        try:
            return f'{Path(frame.filename).resolve().relative_to(HERE).as_posix()}:{frame.lineno}'
        except ValueError:
            continue
    return ''
