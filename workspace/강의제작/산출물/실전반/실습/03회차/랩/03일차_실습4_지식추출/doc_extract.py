"""제공 코드 — 문서에서 후보를 뽑고 검토 결과를 쓰는 일반 로직. 누가 해도 같은 일만 한다: 파일 읽기 · 글자 방식 · 조각 만들기 · 요청 보내기 ·
답을 계약 꼴 후보로 바꾸기 · 인용 줄 찾기 · 견주기 · 검토 결과 쓰기. 어떻게 나눌지 · 무엇을 뽑을지 · 무엇을 채택할지 · 어느 원문을 근거로 둘지는
결과/의 정할 자리(나누기.json · prompt.md · 기대_항목.csv · 검토_결정.csv · 조건_대조.csv · 역할.csv)에 내가 적은 대로만 한다.
정할 자리가 비었거나 꼴이 틀리면 그 파일 · 칸과 함께 멈춘다(다른 값으로 대신하지 않는다). 이 파일은 고치지 않는다 — show_result.py가 부른다.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import csv
import hashlib
import io
import json
import re

HERE = Path(__file__).resolve().parent
RESULT = HERE / '결과'
ENCODINGS = ('utf-8', 'cp949')          # 읽는 차례 — UTF-8로 풀리지 않으면 CP949
UNITS = ('절', '절차', '쪽', '글자')
SECTION_HEAD = re.compile(r'^(##\s+\S|제\d+조\(|[A-Z]+-\d+\.\d+\s+\S|=== 스캔)')   # 절 머리 — 제목 줄 「## 」 · 규정의 「제N조(」 · 「AB-9.1 제목」 · 스캔 머리
PROC_HEAD = re.compile(r'^###\s+\S')                                         # 절차 머리 — 제목 줄 「### 」
FOOTER = re.compile(r'^-\s*(\S+)\s*-$')                                       # 스캔본 쪽 꼬리 「- 9-3 -」
LANG = re.compile(r'^\s*(?:\d+\.\s*)?(EN|KO):')
KINDS = ('step', 'precondition', 'prohibition', 'completion', 'unit_value')
COMPARATORS = {None, '>=', '>', '<=', '<', '=', 'range', '±'}
SAME_SIGN = {'≥': '>=', '≤': '<=', '＝': '='}
DECISIONS = {'채택': 'approved', '수정': 'approved', '제외': 'excluded', '보류': 'pending'}
MATCH = ('일치', '불일치', '원문 없음', '보류')
MARK = '제공 빈 틀'
REVIEWER = '이 폴더의 검토자'


class Problem(Exception):
    """정할 자리 · 입력의 꼴 문제 — 파일과 칸(또는 줄)을 함께 알린다."""
    def __init__(self, where, message):
        super().__init__(f'{where}: {message}')
        self.where, self.message = where, message


# ───────────── 읽기 ─────────────
def squash(text):
    """글자 · 숫자만 남기고 소문자로 — 계약의 normalized 비교."""
    return ''.join(c for c in str(text).lower() if c.isalnum())


def csv_rows(path, skip_mark=True):
    """CSV 행 — 「#」로 시작하는 줄과 「제공 빈 틀」 표시 줄은 건너뛴다. 칸의 앞뒤 공백은 지운다."""
    lines = [x for x in Path(path).read_text(encoding='utf-8-sig').splitlines()
             if not x.startswith('#') and not (skip_mark and MARK in x and x.count(',') == 0)]
    rows = list(csv.DictReader(io.StringIO('\n'.join(lines))))
    return [{(k or '').strip(): (v or '').strip() for k, v in r.items()} for r in rows]


def numbered(path, keys):
    """[(실제 줄 번호, 행)] — 「#」 줄 · 빈 줄도 세는 파일의 줄 번호. keys 칸이 모두 빈 행은 건너뛴다. 열 이름 · 칸 수가 틀리면 그 파일:줄로 멈춘다."""
    rel = f'결과/{Path(path).name}'
    kept = [(n, x) for n, x in enumerate(Path(path).read_text(encoding='utf-8-sig').splitlines(), 1) if x.strip() and not x.lstrip().startswith('#')]
    if not kept:
        return []
    head = [c.strip() for c in next(csv.reader([kept[0][1]]))]
    out = []
    for n, line in kept[1:]:
        vals = next(csv.reader([line]))
        if len(vals) != len(head):
            raise Problem(f'{rel}:{n}', f'칸 {len(vals)}개 — 열 {len(head)}개({",".join(head)})와 같아야 함(글 안의 쉼표는 칸 전체를 큰따옴표로 감쌈)')
        row = {k: v.strip() for k, v in zip(head, vals)}
        if any(row.get(k) for k in keys):
            out.append((n, row))
    missing = [k for k in keys if k not in head]
    if missing:
        raise Problem(f'{rel}:{kept[0][0]}', f'열 {", ".join(missing)}이 없음 — 열 이름은 입출력_계약.md 「정할 자리」 그대로')
    return out


REFS = re.compile(r'\s*[;·]\s*')


def refs_of(text):
    """근거 칸의 「파일:줄」들 — 여럿이면 「 · 」 또는 「;」로 잇는다."""
    return [x.strip() for x in REFS.split(text or '') if x.strip()]


def filled(rows, keys):
    """한 칸이라도 채운 행만(열 이름만 있는 빈 틀은 0행)."""
    return [r for r in rows if any(r.get(k) for k in keys)]


def register():
    """자료/문서_목록.csv의 행 — 첫 줄(내보내기 머리)은 # 로 시작한다."""
    return csv_rows(HERE / '자료/문서_목록.csv')


def stem(row):
    return f'{row["문서 식별자"]}_{row["판"]}' if row['판'] else row['문서 식별자']


def read_document(row):
    """(글, 글자 방식, 원문 바이트) 또는 읽지 못한 까닭(str)."""
    if not row['파일']:
        return '받은 파일이 없음(목록에만 있는 문서)'
    path = HERE / '자료' / row['파일']
    if not path.is_file():
        return f'자료/{row["파일"]} 파일이 없음'
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != row['SHA-256']:
        return '목록의 SHA-256과 다른 파일(다른 판일 수 있음)'
    for enc in ENCODINGS:
        try:
            return raw.decode(enc), enc, raw
        except UnicodeDecodeError:
            continue
    return 'UTF-8 · CP949 어느 쪽으로도 읽히지 않음'


def documents():
    """[(행, 글 또는 None, 글자 방식, 원문 바이트, 읽지 못한 까닭)] — 목록 차례대로."""
    out = []
    for row in register():
        got = read_document(row)
        if isinstance(got, str):
            out.append((row, None, None, None, got))
        else:
            out.append((row, got[0], got[1], got[2], None))
    return out


def by_file():
    return {row['파일']: (row, text, enc, raw) for row, text, enc, raw, why in documents() if text is not None}


def section_heads(text):
    return [n for n, line in enumerate(text.splitlines(), 1) if SECTION_HEAD.match(line.strip()) and '....' not in line]


# ───────────── 나누기(정할 자리: 결과/나누기.json) ─────────────
def settings():
    """결과/나누기.json — 비었으면 None, 꼴이 틀리면 Problem."""
    path = RESULT / '나누기.json'
    where = '결과/나누기.json'
    if not path.is_file():
        raise Problem(where, '파일이 없습니다 — 받은 빈 틀을 지웠으면 받은 ZIP에서 다시 꺼냅니다')
    try:
        cfg = json.loads(path.read_text(encoding='utf-8-sig'))
    except ValueError as e:
        raise Problem(where, f'JSON으로 읽지 못함({e})')
    unit = str(cfg.get('단위') or '').strip()
    if not unit:
        return None
    if unit not in UNITS:
        raise Problem(f'{where} 「단위」', f'{unit!r} — 절 · 절차 · 쪽 · 글자 중 하나')
    limit = cfg.get('글자_상한')
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 0:
        raise Problem(f'{where} 「글자_상한」', f'{limit!r} — 0 이상의 정수(0이면 묶지 않음)')
    if unit == '글자' and limit == 0:
        raise Problem(f'{where} 「글자_상한」', '단위가 글자면 1 이상')
    for key in ('보낼_문서',):
        if not isinstance(cfg.get(key, []), list):
            raise Problem(f'{where} 「{key}」', '목록이어야 함(자료/ 안의 파일 이름)')
    files = {r['파일'] for r in register() if r['파일']}
    for name in cfg.get('보낼_문서', []):
        if name not in files:
            raise Problem(f'{where} 「보낼_문서」', f'{name!r}는 문서 목록의 파일 이름이 아님')
    pick = cfg.get('쓸_기록', {})
    if not isinstance(pick, dict):
        raise Problem(f'{where} 「쓸_기록」', '{"요청 해시": "응답 기록 파일 이름"} 꼴')
    again = cfg.get('다시_보낼_문서', [])
    if not isinstance(again, list) or any(x not in cfg.get('보낼_문서', []) for x in again):
        raise Problem(f'{where} 「다시_보낼_문서」', '「보낼_문서」 가운데 지금 요청 글 · 나누기로 다시 보낼 파일 이름 목록')
    return {'단위': unit, '글자_상한': limit, '시험_조각': str(cfg.get('시험_조각') or '').strip(), '보낼_문서': list(cfg.get('보낼_문서', [])), '쓸_기록': pick,
            '다시_보낼_문서': list(again)}


def blocks_of(text, unit):
    """[(첫 줄 번호, [줄])] — 정한 단위의 머리에서 끊는다. 목차 줄(점선)은 머리로 보지 않는다."""
    lines = text.splitlines()
    blocks, cur, start = [], [], 1
    for n, line in enumerate(lines, 1):
        s = line.strip()
        if unit == '글자':
            head = bool(cur)
        elif unit == '쪽':
            head = False
        else:
            head = (SECTION_HEAD.match(s) or (unit == '절차' and PROC_HEAD.match(s))) and '....' not in line
        if head and cur:
            blocks.append((start, cur))
            cur, start = [], n
        cur.append(line)
        if unit == '쪽' and FOOTER.match(s):
            blocks.append((start, cur))
            cur, start = [], n + 1
    if cur:
        blocks.append((start, cur))
    return blocks


def split_chunks(text, unit, limit):
    """[(첫 줄 번호, 조각 글)] — 단위마다 끊고, 이어진 단위는 글자 상한 안에서 묶는다(상한 0이면 묶지 않음)."""
    out, buf, first = [], [], None
    for s, block in blocks_of(text, unit):
        body = '\n'.join(block)
        if buf and (limit == 0 or len('\n'.join(buf)) + len(body) > limit):
            out.append((first, '\n'.join(buf)))
            buf, first = [], None
        if first is None:
            first = s
        buf.append(body)
    if buf:
        out.append((first, '\n'.join(buf)))
    return out


def section_of(text, line):
    """(절 표기, 절차 표기) — 그 줄 앞의 가장 가까운 절 머리 · 절차 머리에서. 첫 절 앞이면 머리말."""
    sec, proc = '머리말', None
    for n, raw in enumerate(text.splitlines()[:line], 1):
        s = raw.strip()
        if '....' in s:
            continue
        m = re.match(r'^##\s+(\S+)', s) or re.match(r'^(제\d+조)\(', s) or re.match(r'^([A-Z]+-\d+\.\d+)\s+\S', s)
        if m and not s.startswith('###'):
            sec, proc = m.group(1), None
        m2 = re.match(r'^###\s+(\S+)', s)
        if m2:
            proc = m2.group(1)
    return sec, proc


def chunk_range(first, body):
    return first, first + body.count('\n')


# ───────────── 요청 글(정할 자리: 결과/prompt.md) ─────────────
def prompt_text():
    """요청 글 — 「제공 빈 틀」 표시 줄은 보내지 않는다. 머리 줄(#)만 남았으면 빈 것으로 본다."""
    path = RESULT / 'prompt.md'
    if not path.is_file():
        raise Problem('결과/prompt.md', '파일이 없습니다')
    lines = [x for x in path.read_text(encoding='utf-8-sig').splitlines() if not (x.startswith('>') and MARK in x)]
    text = '\n'.join(lines).strip('\n')
    body = [x for x in lines if x.strip() and not x.lstrip().startswith('#')]
    return text + '\n' if body else ''


def build_request(prompt, row, first, body):
    return [{'role': 'system', 'content': prompt},
            {'role': 'user', 'content': f'문서 {row["문서 식별자"]} 판 {row["판"]} 상태 {row["상태"]} — 원문 {first}줄부터:\n\n{body}'}]


def stamp(cfg, prompt):
    """후보를 만든 설정의 표지 — 같은 표지의 후보 파일이 있으면 다시 보내지 않는다."""
    digest = hashlib.sha256(prompt.encode('utf-8')).hexdigest()[:12]
    return f'show_result.py — 나누기 단위 {cfg["단위"]} · 글자 상한 {cfg["글자_상한"]} · 요청 글 sha256 {digest}'


# ───────────── 답 → 후보 ─────────────
def parse_reply(raw):
    """답 글 → (답 dict, 문제). 처음 { 부터 끝 } 까지를 JSON으로 읽고, 끝이 잘려 읽지 못하면 앞의 온전한 후보만 건진다."""
    start, end = raw.find('{'), raw.rfind('}')
    if start < 0:
        return {}, '답에 JSON이 없음'
    try:
        data = json.loads(raw[start:end + 1])
        return (data, None) if isinstance(data, dict) else ({}, '답의 JSON이 객체가 아님')
    except ValueError:
        pass
    key = raw.find('"candidates"', start)
    at = raw.find('[', key) if key >= 0 else -1
    if at < 0:
        return {}, '답을 JSON으로 읽지 못함'
    decoder, items, pos = json.JSONDecoder(), [], at + 1
    while True:
        while pos < len(raw) and raw[pos] in ' \r\n\t,':
            pos += 1
        try:
            item, pos = decoder.raw_decode(raw, pos)
        except ValueError:
            break
        items.append(item)
    return {'candidates': items}, f'답을 JSON으로 다 읽지 못해(끝이 잘림) 앞의 온전한 후보 {len(items)}개만 읽음'


def line_spans(text):
    spans, pos = [], 0
    for line in text.splitlines(keepends=True):
        body = line.rstrip('\r\n\x0b\x0c\x1c\x1d\x1e\x85  ')
        spans.append((pos, pos + len(body)))
        pos += len(line)
    return spans


def locate(text, lines, quote):
    """인용의 (line_start, line_end, quote_match) — 원문 한 곳에만 맞을 때. 여러 곳에 맞거나 없으면 None(계약: 찾지 못한 것)."""
    if not quote.strip():
        return None
    if text.count(quote) == 1:
        at = text.find(quote)
        spans = line_spans(text)
        first = next(i for i, (a, b) in enumerate(spans, 1) if at <= b)
        last = next(i for i, (a, b) in enumerate(spans, 1) if at + len(quote) - 1 <= b)
        return first, last, 'exact'
    key = squash(quote)
    if not key or text.count(quote) > 1 or squash(text).count(key) != 1:
        return None
    for b in range(1, len(lines) + 1):
        for a in range(b, max(0, b - 7), -1):
            if key in squash('\n'.join(lines[a - 1:b])):
                return a, b, 'normalized'
    return None


def matching_lines(text, quote):
    """인용이 맞는 줄 번호 전부(한 줄 안에서 글자 그대로 또는 글자 · 숫자 비교) — 찾지 못한 인용의 줄을 고를 때 보인다."""
    key = squash(quote)
    return [n for n, line in enumerate(text.splitlines(), 1) if quote in line or (key and key in squash(line))]


def as_number(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        try:
            value = float(value.replace(',', '').strip())
        except ValueError:
            return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def page_of(lines, line_end):
    return next((FOOTER.match(x.strip()).group(1) for x in lines[line_end - 1:] if FOOTER.match(x.strip())), None)


def lang_of(lines, start, end, quote):
    said = {m.group(1) for x in lines[start - 1:end] for m in [LANG.match(x)] if m}
    if len(said) == 1:
        return said.pop().lower()
    return 'ko' if re.search('[가-힣]', quote) else 'en'


def contract_problem(item, text):
    if item['section'] != '머리말' and squash(item['section']) not in squash(text):
        return f'원문에 없는 절 표기 {item["section"]!r}'
    if item['procedure'] is not None and squash(item['procedure']) not in squash(text):
        return f'원문에 없는 절차 표기 {item["procedure"]!r}'
    if item['kind'] == 'step' and item.get('order') is None:
        return '단계 번호를 알 수 없음'
    if item['kind'] == 'unit_value':
        if not isinstance(item.get('value'), (int, float)) or isinstance(item.get('value'), bool):
            return 'value가 숫자가 아님'
        if not item.get('unit'):
            return 'unit이 없음'
        if item['comparator'] not in COMPARATORS or (item['comparator'] == 'range' and not isinstance(item.get('value_max'), (int, float))):
            return f'comparator {item["comparator"]!r}'
        if not item.get('value_text') or str(item['value_text']) not in item['quote']:
            return 'value_text가 quote 안에 없음'
    return None


def to_candidates(row, text, replies):
    """받은 답들 → (후보, 찾지 못한 인용, 경고, model_run). 쓸 내용이 없는 답의 기록으로는 후보를 만들지 않는다."""
    lines = text.splitlines()
    scanned = '스캔본' in row['상태']
    bilingual = any(LANG.match(x) for x in lines)
    cands, unlocated, warnings, runs, seen = [], [], [], [], set()
    for reply in replies:
        if reply.get('usable') is False:
            warnings.append(f'{reply["file"]}: 쓸 내용이 없는 답이라 후보를 만들지 않음({reply.get("note")})')
            continue
        runs.append({'record': reply['file'], 'request_hash': reply['request_hash'], 'model': reply['model'], 'method': reply['method'], 'reused_from': None})
        data, problem = parse_reply(reply.get('response_text') or '')
        if problem:
            warnings.append(f'{reply["file"]}: {problem}')
        if reply.get('finish_reason') == 'length':
            warnings.append(f'{reply["file"]}: 답이 길이 상한에서 잘림 — 이 조각의 뒷부분 후보는 없음')
        warnings += [f'{reply["file"]}: 모델의 경고 — {w}' for w in data.get('warnings') or [] if str(w).strip()]
        for c in data.get('candidates') or []:
            if not isinstance(c, dict) or c.get('kind') not in KINDS:
                warnings.append(f'{reply["file"]}: 종류를 알 수 없는 후보 — {str(c)[:80]}')
                continue
            quote = str(c.get('quote') or '')
            refs = c.get('refs') or []
            item = {'id': f'{row["문서 식별자"]}-M{len(cands) + len(unlocated) + 1:03d}', 'section': str(c.get('section') or '머리말'),
                    'procedure': str(c['procedure']) if c.get('procedure') else None, 'kind': c['kind'],
                    'text': str(c.get('text') or '').strip() or quote, 'quote': quote,
                    'refs': [str(r) for r in ([refs] if isinstance(refs, str) else refs)]}
            if c['kind'] == 'unit_value':
                for k in ('value', 'value_max'):
                    if c.get(k) is not None:
                        item[k] = as_number(c[k])
                item['unit'] = c.get('unit')
                item['comparator'] = SAME_SIGN.get(c.get('comparator'), c.get('comparator'))
                item['value_text'] = c.get('value_text')
            found = locate(text, lines, quote)
            if not found:
                unlocated.append(item | {'status': 'pending', 'note': '원문 한 곳에서 찾지 못함(원문에 없거나 여러 곳에 맞음)'})
                continue
            values = {k: item.pop(k) for k in ('value', 'value_max', 'unit', 'comparator', 'value_text') if k in item}
            item |= {'quote_match': found[2], 'line_start': found[0], 'line_end': found[1]}
            if scanned:
                item['page'] = page_of(lines, found[1])
            if bilingual:
                item['lang'] = lang_of(lines, found[0], found[1], quote)
            item['status'] = 'pending'
            if c['kind'] == 'step':
                order = as_number(c.get('order'))
                if not isinstance(order, int) or isinstance(order, bool) or order < 1:
                    m = re.match(r'^\s*(?:(?:EN|KO):\s*)?(\d+)\.', lines[found[0] - 1])
                    order = int(m.group(1)) if m else None
                item['order'] = order
            item.update(values)
            problem = contract_problem(item, text)
            if problem:
                warnings.append(f'{reply["file"]}: 계약 꼴에 맞지 않아 후보에 넣지 않음({problem}) — 「{quote[:60]}」')
                continue
            key = (item['kind'], item['section'], item['procedure'], item['text'], quote, item.get('value_text'))
            if key in seen:
                continue
            seen.add(key)
            cands.append(item)
    return cands, unlocated, warnings, runs


def dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + '\n'


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8', newline='\n')


# ───────────── 보내기 ─────────────
def client():
    import llm_client
    return llm_client


def record_for(request, cfg):
    """이 요청의 응답 기록 — 쓸 수 있는 기록이 둘 이상이면 나누기.json 「쓸_기록」에 고른 파일만 쓴다(고르지 않았으면 멈춤). 없으면 None."""
    L = client()
    body = L.body_of(L.as_messages(request), L.settings()['LLM_MODEL'])
    digest = L.request_hash(body)
    good = [(p, d) for p, d in L.mine(L.records(digest), L.folder_mark(create=False)) if L.usable(d)]
    if not good:
        return digest, None
    if len(good) > 1:
        chosen = cfg['쓸_기록'].get(digest)
        if not chosen:
            raise Problem('결과/나누기.json 「쓸_기록」', f'요청 해시 {digest}의 기록이 {len(good)}개({", ".join(p.name for p, _ in good)}) — 검토에 쓸 기록 파일 이름을 적습니다')
        pick = [(p, d) for p, d in good if p.name == chosen]
        if not pick:
            raise Problem('결과/나누기.json 「쓸_기록」', f'{chosen!r}는 요청 해시 {digest}의 기록 파일이 아님')
        good = pick
    p, d = good[-1]
    return digest, dict(d, file=p.relative_to(HERE).as_posix())


def plan(cfg, prompt, files):
    """보낼 문서들의 [(행, 글, 글자 방식, 원문 바이트, [(첫 줄, 조각)])]."""
    docs = by_file()
    out = []
    for name in files:
        if name not in docs:
            raise Problem('결과/나누기.json 「보낼_문서」', f'{name}를 읽지 못함')
        row, text, enc, raw = docs[name]
        out.append((row, text, enc, raw, split_chunks(text, cfg['단위'], cfg['글자_상한'])))
    return out


def to_send(cfg, prompt, files):
    """(보낼 요청 수, 이 폴더의 남은 수) — 보내지 않고 센다."""
    L = client()
    n = 0
    mark = stamp(cfg, prompt)
    for row, text, enc, raw, parts in plan(cfg, prompt, files):
        path = candidate_path(row)
        if path.is_file():
            old = json.loads(path.read_text(encoding='utf-8'))
            if all((HERE / r['record']).is_file() for r in old.get('model_run', [])) and (old.get('extractor') == mark or row['파일'] not in cfg.get('다시_보낼_문서', [])):
                continue          # 이 문서는 지금 있는 후보 파일을 그대로 쓴다(extract와 같은 길)
        for first, body in parts:
            digest, rec = record_for(build_request(prompt, row, first, body), cfg)
            n += rec is None
    return n, L.MAX_SENT - L.sent_count()


def candidate_path(row):
    return RESULT / '후보' / f'{stem(row)}.json'


def extract(cfg, prompt, files, now=None):
    """보낼 문서마다 후보 파일을 쓴다. 같은 설정 표지의 후보 파일이 있으면 다시 보내지도 다시 쓰지도 않는다. 돌려주는 값: [(파일, 한 일)]."""
    L = client()
    mark = stamp(cfg, prompt)
    done = []
    todo = []
    for row, text, enc, raw, parts in plan(cfg, prompt, files):
        path = candidate_path(row)
        if path.is_file():
            try:
                old = json.loads(path.read_text(encoding='utf-8'))
            except ValueError:
                old = {}
            kept = all((HERE / r['record']).is_file() for r in old.get('model_run', []))
            if old.get('extractor') == mark and kept:
                done.append((row['파일'], '같은 설정의 후보 파일이 있어 그대로 둠'))
                continue
            if kept and row['파일'] not in cfg.get('다시_보낼_문서', []):
                # 문서마다 후보를 만든 요청 글 · 나누기를 지킨다 — 지금 판으로 다시 보낼 문서는 「다시_보낼_문서」에 적는다(결과 화면 표가 문서마다 어느 판인지 보인다)
                done.append((row['파일'], '앞 판 요청 글 · 나누기로 만든 후보 그대로 — 지금 판으로 다시 보내려면 「다시_보낼_문서」에'))
                continue
        todo.append((row, text, enc, raw, parts))
    need, left = (0, 0)
    for row, text, enc, raw, parts in todo:
        for first, body in parts:
            need += record_for(build_request(prompt, row, first, body), cfg)[1] is None
    left = L.MAX_SENT - L.sent_count()
    if need > left:
        raise Problem('결과/나누기.json', f'보낼 요청 {need}개가 이 폴더의 안내용 상한까지 남은 {left}개보다 많습니다 — 보낼 문서를 줄이거나 조각을 크게 묶습니다')
    for row, text, enc, raw, parts in todo:
        replies = []
        for first, body in parts:
            request = build_request(prompt, row, first, body)
            digest, rec = record_for(request, cfg)
            if rec is None:
                got = L.ask(request)
                digest, rec = record_for(request, cfg)
                if rec is None:
                    rec = dict(got)
            replies.append(rec)
        cands, unlocated, warnings, runs = to_candidates(row, text, replies)
        result = {'doc_id': row['문서 식별자'], 'rev': row['판'], 'doc_status': row['상태'], 'source_file': row['파일'],
                  'source_sha256': hashlib.sha256(raw).hexdigest(), 'encoding': enc, 'extractor': mark,
                  'generated_at': now or datetime.now().astimezone().isoformat(timespec='seconds'),
                  'model_run': runs, 'candidates': cands, 'unlocated': unlocated, 'warnings': warnings}
        write(candidate_path(row), dump(result))
        done.append((row['파일'], f'후보 {len(cands)}개 · 찾지 못한 인용 {len(unlocated)}개 · 경고 {len(warnings)}개'))
    return done


def trial(cfg, prompt):
    """시험 조각 — 나누기.json 「시험_조각」(파일:줄)이 든 조각 하나를 보내고, 같은 요청을 한 번 더 보낸다(같은 요청은 두 번까지).
    결과는 결과/시험_조각.json(후보 파일과 따로)."""
    spot = cfg['시험_조각']
    m = re.fullmatch(r'(.+):(\d+)', spot)
    if not m:
        raise Problem('결과/나누기.json 「시험_조각」', f'{spot!r} — 「자료 파일 이름:줄 번호」 꼴')
    name, line = m.group(1), int(m.group(2))
    docs = by_file()
    if name not in docs:
        raise Problem('결과/나누기.json 「시험_조각」', f'{name!r}는 읽을 수 있는 자료 파일이 아님')
    row, text, enc, raw = docs[name]
    parts = split_chunks(text, cfg['단위'], cfg['글자_상한'])
    hit = [(first, body) for first, body in parts if chunk_range(first, body)[0] <= line <= chunk_range(first, body)[1]]
    if not hit:
        raise Problem('결과/나누기.json 「시험_조각」', f'{line}줄이 원문 줄 범위(1~{len(text.splitlines())}) 밖')
    first, body = hit[0]
    request = build_request(prompt, row, first, body)
    mark = stamp(cfg, prompt) + f' · 시험 조각 {name} {chunk_range(first, body)[0]}~{chunk_range(first, body)[1]}줄'
    old = RESULT / '시험_조각.json'
    if old.is_file():
        prev = json.loads(old.read_text(encoding='utf-8'))
        if prev.get('stamp') == mark and len(prev.get('answers', [])) >= 2 and all((HERE / a['record']).is_file() for a in prev['answers']):
            return prev
    L = client()
    replies = []
    for again in (False, True):
        got = L.ask(request, again=again)
        replies.append(dict(got))
    seen = set()
    answers = []
    for reply in replies:
        if reply['file'] in seen:
            continue
        seen.add(reply['file'])
        cands, unlocated, warnings, runs = to_candidates(row, text, [reply])
        answers.append({'record': reply['file'], 'finish_reason': reply.get('finish_reason'), 'candidates': cands, 'unlocated': unlocated, 'warnings': warnings})
    out = {'stamp': mark, 'source_file': name, 'chunk': list(chunk_range(first, body)), 'request_hash': replies[0]['request_hash'], 'answers': answers}
    write(RESULT / '시험_조각.json', dump(out))
    return out


# ───────────── 기대와 견주기 ─────────────
def expected_rows():
    """결과/기대_항목.csv — (파일, 줄, 종류) 행. 꼴이 틀리면 Problem."""
    path = RESULT / '기대_항목.csv'
    rows = numbered(path, ['파일', '줄', '종류'])
    docs = by_file()
    out = []
    for i, r in rows:
        where = f'결과/기대_항목.csv:{i}'
        if r['파일'] not in docs:
            raise Problem(where, f'파일 {r["파일"]!r}는 읽을 수 있는 자료 파일 이름이 아님')
        if not r['줄'].isdigit() or not 1 <= int(r['줄']) <= len(docs[r['파일']][1].splitlines()):
            raise Problem(where, f'줄 {r["줄"]!r}가 그 파일의 줄 번호가 아님')
        if r['종류'] not in KINDS:
            raise Problem(where, f'종류 {r["종류"]!r} — {" · ".join(KINDS)} 중 하나')
        out.append((r['파일'], int(r['줄']), r['종류']))
    return out


def source_line(name, n):
    docs = by_file()
    return docs[name][1].splitlines()[n - 1]


def load_candidates(name):
    row = next((r for r in register() if r['파일'] == name), None)
    path = candidate_path(row) if row else None
    if not path or not path.is_file():
        return None
    return json.loads(path.read_text(encoding='utf-8'))


def compare_expected(cands_of=load_candidates):
    """기대 행마다 — 맞음(같은 줄 · 같은 종류 후보) · 종류 다름 · 줄 못 정함(찾지 못한 인용이 그 줄에 맞음) · 누락 · 아직(후보 파일 없음).
    그리고 기대 줄 범위 안의 기대 밖 후보. 뜻이 같은지는 판정하지 않는다."""
    rows, extra = [], []
    docs = by_file()
    exp = expected_rows()
    for name in dict.fromkeys(n for n, _, _ in exp):
        data = cands_of(name)
        mine = [(n, k) for f, n, k in exp if f == name]
        if data is None:
            rows += [(name, n, k, source_line(name, n), '아직', '') for n, k in mine]
            continue
        text = docs[name][1]
        for n, k in mine:
            on = [c for c in data['candidates'] if c['line_start'] <= n <= c['line_end']]
            same = [c for c in on if c['kind'] == k]
            if same:
                rows.append((name, n, k, source_line(name, n), '맞음', ' · '.join(f'{c["id"]} 「{c["quote"]}」' for c in same)))
            elif on:
                rows.append((name, n, k, source_line(name, n), '종류 다름', ' · '.join(f'{c["id"]} {c["kind"]}' for c in on)))
            else:
                loose = [u for u in data['unlocated'] if n in matching_lines(text, u['quote'])]
                rows.append((name, n, k, source_line(name, n), '줄 못 정함' if loose else '누락', ' · '.join(f'{u["id"]} 「{u["quote"]}」' for u in loose)))
            if rows[-1][4] == '종류 다름':
                loose = [u for u in data['unlocated'] if u['kind'] == k and n in matching_lines(text, u['quote'])]
                if loose:
                    rows[-1] = (name, n, k, source_line(name, n), '줄 못 정함', ' · '.join(f'{u["id"]} 「{u["quote"]}」' for u in loose))
        lo, hi = min(n for n, _ in mine), max(n for n, _ in mine)
        lines_set = {n for n, _ in mine}
        for c in data['candidates']:
            if lo <= c['line_start'] <= hi and not any(c['line_start'] <= n <= c['line_end'] for n in lines_set):
                extra.append((name, c['line_start'], c['kind'], c['id'], c['quote']))
    return rows, extra


def made_with(data):
    """후보 파일을 만든 판 — 표지(extractor)의 나누기 · 요청 글 sha. 지금 판과 같으면 「지금 판」."""
    cfg = settings()
    now = stamp(cfg, prompt_text() or '') if cfg else ''
    mark = data.get('extractor') or ''
    return '지금 판' if mark == now else mark.replace('show_result.py — ', '앞 판: ')


def coverage(cfg, name):
    """(후보 0개인 조각의 줄 범위 목록, 후보가 걸리지 않은 내용 줄 번호 목록) — 「찾지 못한 인용」과 달리 원문 쪽에서 센다.
    내용 줄 = 빈 줄 · 절 머리(#) · 표 구분 줄 · 쪽 꼬리가 아닌 줄. 후보의 line_start ~ line_end에 든 줄은 걸린 줄."""
    row, text, enc, raw = by_file()[name]
    data = load_candidates(name)
    if data is None:
        return [], []
    spans = [(c['line_start'], c['line_end']) for c in data['candidates']]
    empty = []
    for first, body in split_chunks(text, cfg['단위'], cfg['글자_상한']):
        a, b = chunk_range(first, body)
        if not any(a <= x <= b for x, _ in spans):
            empty.append(f'{a}~{b}')
    lines = text.splitlines()
    loose = [n for n, x in enumerate(lines, 1)
             if x.strip() and not x.lstrip().startswith('#') and not re.fullmatch(r'[\s|:\-]+', x) and not FOOTER.match(x.strip())
             and not any(a <= n <= b for a, b in spans)]
    return empty, loose


def compare_baseline():
    """받은 SOP 구조(입력/sop.json)의 항목 문장마다, 그 구조가 옮긴 문서의 후보 가운데 인용 · 내용이 겹치는 것. 글자 짝이 없는 칸은 원문 줄을 열어 실제 누락인지 내가 본다."""
    sop = json.loads(basis('sop.json').read_text(encoding='utf-8'))
    doc = sop.get('document') or {}
    name = Path(str(doc.get('file') or '')).name or None
    data = load_candidates(name) if name else None
    rows = []
    if data is None:
        return name, None, rows
    keys = [(c['id'], squash(c['quote']), squash(c['text'])) for c in data['candidates']]
    used = set()
    for s in sop['sops']:
        items = [('apply_conditions', x) for x in s.get('apply_conditions', [])] + [('prohibitions', x) for x in s.get('prohibitions', [])] + \
                [('steps', x) for x in s.get('steps', [])] + [('completion', x) for x in s.get('completion', [])]
        if s.get('approval'):
            items.append(('approval', s['approval']))
        for field, x in items:
            t = squash(x.get('text') if isinstance(x, dict) else x)
            hit = [cid for cid, q, tx in keys if t and q and (q in t or t in q or (tx and (tx in t or t in tx)))]
            used |= set(hit)
            rows.append((s['id'], field, x.get('text') if isinstance(x, dict) else str(x), ' · '.join(hit) or '짝 없음'))
    only = [(c['id'], c['procedure'], c['kind'], c['quote']) for c in data['candidates'] if c['id'] not in used and c['procedure'] in {s['id'] for s in sop['sops']}]
    return name, data, rows + [('(후보에만)', k, q, cid) for cid, p, k, q in only]


# ───────────── 검토(정할 자리: 검토_결정.csv · 조건_대조.csv) ─────────────
def basis(name):
    mine = RESULT / '내_입력' / name
    return mine if mine.is_file() else HERE / '입력' / name


def decision_rows():
    """결과/검토_결정.csv — 줄마다의 결정. 줄 칸을 비운 행은 판단 규칙: 그 파일(종류를 적으면 그 종류)의 기대 항목 줄 가운데 따로 적은 행이 없는 줄 전부에 같은 결정을 둔다."""
    rows = numbered(RESULT / '검토_결정.csv', ['파일', '줄', '종류', '결정', '근거', '까닭'])
    docs = by_file()
    out, rules = [], []
    for i, r in rows:
        where = f'결과/검토_결정.csv:{i}'
        if r['파일'] not in docs:
            raise Problem(where, f'파일 {r["파일"]!r}는 읽을 수 있는 자료 파일 이름이 아님')
        text = docs[r['파일']][1]
        rule = not r['줄']
        if not rule and (not r['줄'].isdigit() or not 1 <= int(r['줄']) <= len(text.splitlines())):
            raise Problem(where, f'줄 {r["줄"]!r}가 그 파일의 줄 번호가 아님(판단 규칙이면 비움)')
        if r['종류'] not in KINDS and not (rule and not r['종류']):
            raise Problem(where, f'종류 {r["종류"]!r} — {" · ".join(KINDS)} 중 하나(판단 규칙이면 비워도 됨)')
        if r['결정'] not in DECISIONS:
            raise Problem(where, f'결정 {r["결정"]!r} — 채택 · 수정 · 제외 · 보류 중 하나')
        if not r['까닭']:
            raise Problem(where, '까닭이 비어 있음 — 원문 근거를 든 결정 이유를 적습니다')
        refs = refs_of(r['근거'])
        if not refs or not all(re.fullmatch(r'[^:]+:\d+(-\d+)?', x) for x in refs):
            raise Problem(where, f'근거 {r["근거"]!r} — 「파일:줄」(여럿이면 「 · 」로)')
        if r['결정'] == '수정' and (rule or not r.get('고친_인용')):
            raise Problem(where, '수정은 줄을 적은 행에서만, 고친_인용(원문 그대로의 문장)과 함께')
        if r.get('고친_인용') and r['고친_인용'] not in text.splitlines()[int(r['줄']) - 1]:
            raise Problem(where, f'고친_인용이 {r["파일"]} {r["줄"]}줄에 글자 그대로 없음')
        (rules if rule else out).append((i, r))
    seen = {}
    for i, r in out:
        k = (r['파일'], int(r['줄']), r['종류'])
        if k in seen:
            raise Problem(f'결과/검토_결정.csv:{seen[k]} · {i}', f'같은 파일 · 줄 · 종류({r["파일"]} {r["줄"]} {r["종류"]})가 두 줄 — 한 줄로 합칩니다')
        seen[k] = i
    rows_out = [dict(r, 줄=int(r['줄'])) for _, r in out]
    if rules:
        exp = expected_rows()
        taken = {(r['파일'], r['줄'], r['종류']) for r in rows_out}
        claimed = {}
        for i, r in rules:
            for f, n, k in exp:
                if f == r['파일'] and r['종류'] in ('', k) and (f, n, k) not in taken:
                    if (f, n, k) in claimed:
                        raise Problem(f'결과/검토_결정.csv:{claimed[(f, n, k)]} · {i}', f'판단 규칙 두 줄이 같은 기대 줄({f} {n} {k})에 걸림 — 종류로 나누거나 한 줄로 합칩니다')
                    claimed[(f, n, k)] = i
                    rows_out.append(dict(r, 줄=n, 종류=k))
    return rows_out


def rule_rows(task=None):
    """결과/조건_대조.csv — rule_id 행마다 근거 · match · 까닭 · 요청할 것. task가 있으면 그 작업에 걸린 조건만 받는다."""
    rows = numbered(RESULT / '조건_대조.csv', ['근거', 'match', '까닭', '요청할_것'])
    table = csv_rows(basis('조건표.csv'))
    known = {r['rule_id'] for r in table if task is None or r.get('action') == task}
    out = []
    seen = {}
    for i, r in rows:
        where = f'결과/조건_대조.csv:{i}'
        if r['rule_id'] in seen:
            raise Problem(f'결과/조건_대조.csv:{seen[r["rule_id"]]} · {i}', f'같은 rule_id {r["rule_id"]}가 두 줄 — 한 줄로 합칩니다')
        seen[r['rule_id']] = i
        if r['rule_id'] not in known:
            raise Problem(where, f'rule_id {r["rule_id"]!r}는 ' + (f'{task}에 걸린 조건이 아님' if task else '기준 조건표의 rule_id가 아님'))
        if r['match'] not in MATCH:
            raise Problem(where, f'match {r["match"]!r} — {" · ".join(MATCH)} 중 하나')
        if not r['까닭']:
            raise Problem(where, '까닭이 비어 있음 — 원문이 말하는 대상 · 때와 조건이 거는 대상 · 때')
        refs = refs_of(r['근거'])
        if r['match'] == '원문 없음' and refs:
            raise Problem(where, '원문 없음이면 근거를 비웁니다')
        if r['match'] in ('일치', '불일치') and not refs:
            raise Problem(where, f'{r["match"]}이면 근거(파일:줄)가 필요')
        parsed = []
        docs = by_file()
        for ref in refs:
            m = re.fullmatch(r'(?:자료/)?(.+):(\d+)', ref)
            if not m:
                raise Problem(where, f'근거 {ref!r} — 「파일:줄」 꼴(자료/는 붙여도 · 빼도 됨)')
            if m.group(1) not in docs:
                raise Problem(where, f'근거 {ref!r} — {m.group(1)}는 자료/ 안의 읽을 수 있는 파일이 아님')
            if not 1 <= int(m.group(2)) <= len(docs[m.group(1)][1].splitlines()):
                raise Problem(where, f'근거 {ref!r} — 그 파일의 줄 번호가 아님')
            parsed.append((m.group(1), int(m.group(2))))
        out.append(dict(r, refs=parsed))
    return out, sorted(known)


def apply_review(cfg_task=None, now=None):
    """후보 파일마다 검토 결과(결과/검토/<문서>_<판>_검토.json)를 쓴다. 결정 표에 없는 후보는 보류(원문과 대조하지 않음).
    결정 표의 줄에 후보가 없고 찾지 못한 인용이 그 줄에 맞으면 검토자가 더한 후보로, 그것도 없으면 누락(missing)으로 적는다."""
    decisions = decision_rows()
    rules, _ = rule_rows(cfg_task)
    chosen = {r['지점']: r for r in filled(csv_rows(RESULT / '정한_것.csv'), ['지점', '고른_것', '근거', '바뀌는_답'])}
    files = sorted({d['파일'] for d in decisions} | {f for r in rules for f, _ in r['refs']})
    docs = by_file()
    written = []
    no_source = [r for r in rules if r['match'] in ('원문 없음', '보류') and not r['refs']]
    for name in files:
        row, text, enc, raw = docs[name]
        cpath = candidate_path(row)
        if not cpath.is_file():
            raise Problem(f'결과/후보/{stem(row)}.json', f'후보 파일이 없음 — 결정 표 · 조건 근거가 {name}를 가리킴(보낼_문서에 넣고 다시 실행)')
        base = json.loads(cpath.read_text(encoding='utf-8'))
        lines = text.splitlines()
        cands = [dict(c) for c in base['candidates']]
        mine = [d for d in decisions if d['파일'] == name]
        taken = set()
        out_c, missing = [], []
        seen = set()
        for c in cands:
            hit = next((d for d in mine if c['line_start'] <= d['줄'] <= c['line_end'] and d['종류'] == c['kind']), None)
            key = (hit['줄'], hit['종류'], squash(c['quote'])) if hit else None   # 같은 줄 · 종류라도 인용이 다르면 다른 후보(발행 · 승인처럼 한 줄에 둘)
            if hit is None:
                c.update(decision='보류', status='pending', reason='검토자가 이 후보를 원문과 대조하지 않음(결정 표에 그 줄 · 종류가 없음)', origin='extractor')
            elif key in seen:
                c.update(decision='제외', status='excluded', reason=f'같은 줄 · 종류 · 인용({name} {hit["줄"]}줄 {hit["종류"]})의 후보가 앞에 있어 중복', origin='extractor')
            else:
                seen.add(key)
                taken.add(key[:2])
                c.update(decision=hit['결정'], status=DECISIONS[hit['결정']], origin='extractor',
                         reason=f'{c["section"]} · {c["kind"]} · 「{c["quote"][:40]}」 — {hit["까닭"]} (근거 {hit["근거"]})')
                if hit['결정'] == '수정':
                    c['before'] = {'quote': c['quote'], 'line_start': c['line_start'], 'line_end': c['line_end'], 'quote_match': c['quote_match']}
                    c.update(quote=hit['고친_인용'], line_start=hit['줄'], line_end=hit['줄'], quote_match='exact')
            out_c.append(c)
        n = len(out_c)
        for d in mine:
            if (d['줄'], d['종류']) in taken:
                continue
            line = lines[d['줄'] - 1]
            loose = sorted([u for u in base['unlocated'] if d['줄'] in matching_lines(text, u['quote'])], key=lambda u: u['kind'] != d['종류'])
            quote = d.get('고친_인용') or line.strip()
            if loose:
                q = loose[0]['quote'] if loose[0]['quote'] in line else quote
                n += 1
                item = {k: loose[0][k] for k in ('section', 'procedure', 'kind', 'text', 'refs')}
                item.update(id=f'{row["문서 식별자"]}-R{n:03d}', kind=d['종류'], quote=q, quote_match='exact', line_start=d['줄'], line_end=d['줄'],
                            decision=d['결정'], status=DECISIONS[d['결정']], origin='reviewer',
                            reason=f'찾지 못한 인용 {loose[0]["id"]}의 줄을 골라 더함 — {d["까닭"]} (근거 {d["근거"]})')
                if '스캔본' in row['상태']:
                    item['page'] = page_of(lines, d['줄'])
                if any(LANG.match(x) for x in lines):
                    item['lang'] = lang_of(lines, d['줄'], d['줄'], q)
                if d['종류'] == 'step':
                    m = re.match(r'^\s*(?:(?:EN|KO):\s*)?(\d+)\.', line)
                    item['order'] = int(m.group(1)) if m else None
                if d['종류'] == 'unit_value':
                    if loose[0]['kind'] != 'unit_value':
                        raise Problem(f'결과/검토_결정.csv {name} {d["줄"]}줄', '기준값(unit_value)으로 더하려면 그 줄의 찾지 못한 인용도 기준값이어야 함 — 종류를 원문대로 고칩니다')
                    item.update({k: loose[0][k] for k in ('value', 'value_max', 'unit', 'comparator', 'value_text') if k in loose[0]})
                out_c.append(item)
                missing.append({'section': item['section'], 'procedure': item['procedure'], 'kind': d['종류'], 'quote': q, 'line_start': d['줄'], 'line_end': d['줄'],
                                'note': f'코드가 줄을 정하지 못한 인용({loose[0]["id"]}) — {d["까닭"]}', 'added': True})
                taken.add((d['줄'], d['종류']))
            elif d.get('고친_인용'):
                n += 1
                sec, proc = section_of(text, d['줄'])
                item = {'id': f'{row["문서 식별자"]}-R{n:03d}', 'section': sec, 'procedure': proc, 'kind': d['종류'], 'text': d['고친_인용'], 'quote': d['고친_인용'],
                        'refs': [], 'quote_match': 'exact', 'line_start': d['줄'], 'line_end': d['줄'], 'decision': d['결정'], 'status': DECISIONS[d['결정']],
                        'origin': 'reviewer', 'reason': f'모델의 답에 이 줄의 후보가 없어 검토자가 원문 문장으로 더함 — {d["까닭"]} (근거 {d["근거"]})'}
                if '스캔본' in row['상태']:
                    item['page'] = page_of(lines, d['줄'])
                if any(LANG.match(x) for x in lines):
                    item['lang'] = lang_of(lines, d['줄'], d['줄'], d['고친_인용'])
                if d['종류'] == 'step':
                    m = re.match(r'^\s*(?:(?:EN|KO):\s*)?(\d+)\.', line)
                    item['order'] = int(m.group(1)) if m else None
                if d['종류'] == 'unit_value':
                    raise Problem(f'결과/검토_결정.csv {name} {d["줄"]}줄', '기준값(unit_value)은 값 · 단위 · 비교가 있는 모델의 후보에서만 만든다 — 다른 종류로 적거나 요청 글을 고쳐 다시 보냅니다')
                out_c.append(item)
                missing.append({'section': sec, 'procedure': proc, 'kind': d['종류'], 'quote': d['고친_인용'], 'line_start': d['줄'], 'line_end': d['줄'],
                                'note': f'원문에 있는데 모델의 후보가 없어 검토자가 더함 — {d["까닭"]}', 'added': True})
                taken.add((d['줄'], d['종류']))
            else:
                missing.append({'section': section_of(text, d['줄'])[0], 'procedure': None, 'kind': d['종류'], 'quote': quote, 'line_start': d['줄'], 'line_end': d['줄'],
                                'note': f'원문에 있는데 후보가 없음 — {d["까닭"]}', 'added': False})
        links = []
        for r in rules:
            ids = []
            for f, ln in r['refs']:
                if f != name:
                    continue
                on = [c for c in out_c if c['line_start'] <= ln <= c['line_end'] and c['status'] != 'excluded'] or \
                     [c for c in out_c if c['line_start'] <= ln <= c['line_end']]
                if not on:
                    raise Problem(f'결과/조건_대조.csv {r["rule_id"]}', f'{f} {ln}줄에 후보가 없음 — 검토_결정.csv에 그 줄을 넣어 검토 결과에 후보를 둡니다')
                ids += [c['id'] for c in on if c['id'] not in ids]
            if ids:
                links.append({'rule_id': r['rule_id'], 'candidates': ids, 'match': r['match'], 'note': r['까닭']})
        if no_source and name == files[0]:
            links += [{'rule_id': r['rule_id'], 'candidates': [], 'match': r['match'], 'note': r['까닭']} for r in no_source]
        review = dict(base)
        review['review'] = {'reviewer': REVIEWER, 'reviewed_at': None, 'candidates_file': f'결과/후보/{stem(row)}.json',
                            'candidates_sha256': hashlib.sha256(cpath.read_bytes()).hexdigest(), 'selected_task': cfg_task,
                            'decisions': [f'{k}: {v["고른_것"]} — 근거 {v["근거"]}' for k, v in chosen.items()]}
        review['candidates'] = out_c
        review['missing'] = missing
        review['rule_links'] = links
        rpath = RESULT / '검토' / f'{stem(row)}_검토.json'
        stamp_at = now
        if rpath.is_file():
            old = json.loads(rpath.read_text(encoding='utf-8'))
            old_at = (old.get('review') or {}).get('reviewed_at')
            old['review'] = dict(old.get('review') or {}, reviewed_at=None)
            if old == dict(review):
                stamp_at = old_at
        review['review']['reviewed_at'] = stamp_at or datetime.now().astimezone().isoformat(timespec='seconds')
        write(rpath, dump(review))
        written.append(rpath)
    for path in sorted((RESULT / '검토').glob('*_검토.json')) if (RESULT / '검토').is_dir() else []:
        if path not in written:
            path.unlink()      # 결정 표 · 조건 근거가 더는 가리키지 않는 문서의 검토 결과 — 지난 실행이 남긴 파일
    return written


# ───────────── 이 작업의 조건 모으기(정할 자리: 역할.csv — 실전) ─────────────
ITEMS = {'준비': 'preparation', '금지': 'prohibitions', '완료': 'completion'}
ROLE_WORDS = ('준비', '금지', '순서', '완료', '승인', '넣지 않음')


def role_rows():
    rows = numbered(RESULT / '역할.csv', ['종류', '인용에_든_글자', '항목', '근거'])
    out = []
    for i, r in rows:
        where = f'결과/역할.csv:{i}'
        if r['종류'] not in KINDS:
            raise Problem(where, f'종류 {r["종류"]!r} — {" · ".join(KINDS)} 중 하나')
        if r['항목'] not in ROLE_WORDS:
            raise Problem(where, f'항목 {r["항목"]!r} — {" · ".join(ROLE_WORDS)} 중 하나')
        if not r.get('근거'):
            raise Problem(where, '근거(파일:줄 또는 계약 절)가 비어 있음')
        out.append(r)
    return out


ROLE_DEFAULT = {'precondition': '준비', 'prohibition': '금지', 'completion': '완료', 'unit_value': '완료', 'step': '넣지 않음'}   # 입출력_계약.md 6절 종류의 뜻 그대로 — 역할.csv는 이와 다르게 둘 것만


def role_of(c, roles):
    """후보 하나의 항목 — 역할.csv에서 종류가 같고 인용에 그 글자가 든 첫 행(글자 칸이 빈 행은 그 종류 전부), 맞는 행이 없으면 계약의 기본(ROLE_DEFAULT), 그것도 없으면 None."""
    for r in roles:
        if r['종류'] == c['kind'] and (not r['인용에_든_글자'] or r['인용에_든_글자'] in c['quote']):
            return r['항목']
    return ROLE_DEFAULT.get(c['kind'])


ABBREV = re.compile(r'(?:^|[\s(])(?:no|nos|rev|e\.g|i\.e|approx|fig|figs|vol|ref|sec|cf|vs|max|min|p|pp)\.$', re.I)


def sentences(line):
    """줄 하나를 문장으로 — 마침표 뒤 띄어쓰기에서 끊되, 숫자 바로 뒤(번호 「1.」), 줄임말(part no. · Rev. · e.g. · approx. · Fig.) 뒤,
    괄호 안에서는 끊지 않는다(옛 판은 「(part no. HI-RF-10)」을 「(part no.」에서 잘라 조각 후보를 만들었다)."""
    s = line.strip()
    out, depth, start = [], 0, 0
    for i, ch in enumerate(s):
        if ch in '([':
            depth += 1
        elif ch in ')]':
            depth = max(0, depth - 1)
        elif ch == '.' and depth == 0 and i + 1 < len(s) and s[i + 1].isspace() and i > 0 and not s[i - 1].isdigit() \
                and not ABBREV.search(s[start:i + 1]):
            out.append(s[start:i + 1].strip())
            start = i + 1
    out.append(s[start:].strip())
    return [x for x in out if x]


def sop_diff(task, prep, ban, done):
    """받은 SOP 구조의 이 작업(task)과 모은 조건을 견준 것 — 카드에만 있는 항목(어느 문서 · 절에서 왔는지)과 SOP 구조에만 있는 문장(그 필드).
    두 문장은 글자 · 숫자만 남겨 짧은 쪽의 80 % 이상이 같은 순서로 겹치면 같은 것으로 본다(조사 · 어미 차이는 넘김).
    카드 쪽은 SOP 구조의 모든 문장(단계 · 승인 역할 포함)과 견주고, SOP 구조 쪽은 카드에 넣는 준비(첫 단계 포함) · 금지 · 완료만 견준다 — 방법 단계는 카드에 넣지 않는다."""
    import difflib

    def same(a, b):
        a, b = squash(a), squash(b)
        short = min(len(a), len(b))
        if short and (a in b or b in a):      # 짧은 기준값 인용(「80 % 이상」)도 그 글이 통째로 들어 있으면 같은 것
            return True
        if short < 6:
            return False
        return sum(m.size for m in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks()) >= 0.8 * short

    def parts(rows):
        return [part for row in rows for part in sentences(re.sub(r'\([^)]*\)$', '', row['text']).strip())]
    cardside = [(name, field, part) for name, field, rows in [('준비', 'apply_conditions', task['apply_conditions']), ('준비', 'steps', [st for st in task['steps'] if st['order'] == 1]),
                                                           ('금지', 'prohibitions', task['prohibitions']), ('완료', 'completion', task['completion'])] for part in parts([*rows])]
    every = parts(task['apply_conditions'] + task['steps'] + task['prohibitions'] + task['completion'])
    role = (task.get('approval') or {}).get('role') or ''
    out = []
    for name, rows in [('준비', prep), ('금지', ban), ('완료', done)]:
        for r in rows:
            if not (any(same(r['quote'], part) for part in every) or (role and role in r['quote'] and '승인' in r['quote'])):
                out.append({'item': r['quote'], 'where': '카드에만', 'note': f'{name} — {r["doc_id"]} {r["rev"]} {r["section"]}에서 옴, 받은 SOP 구조의 이 작업에는 없음'})
    for name, field, part in cardside:
        if not any(same(r['quote'], part) for rows in (prep, ban, done) for r in rows):
            out.append({'item': part, 'where': 'SOP 구조에만', 'note': f'{name} — 입력/sop.json {task["id"]} {field}, 승인한 원문 후보가 없음'})
    return out


def collect_task(task, basis_line):
    """검토 결과의 승인 후보 가운데 기대_항목.csv의 줄(이 작업의 원문 줄)에 있는 것을 역할.csv대로 준비 · 금지 · 완료에 모은다.
    승인이 아닌 것은 remaining_questions, 받은 SOP 구조의 이 작업 항목과 글자가 겹치지 않는 곳은 sop_diff."""
    roles = role_rows()
    exp = {(f, n) for f, n, _ in expected_rows()}
    out = {'task': task, 'basis': basis_line, 'preparation': [], 'prohibitions': [], 'completion': [], 'remaining_questions': [], 'sop_diff': []}
    unmapped = []
    for path in sorted((RESULT / '검토').glob('*_검토.json')):
        rv = json.loads(path.read_text(encoding='utf-8'))
        for c in rv['candidates']:
            if not any(f == rv['source_file'] and c['line_start'] <= n <= c['line_end'] for f, n in exp):
                continue
            ref = f'결과/검토/{path.name}#{c["id"]}'
            if c['status'] == 'excluded':          # 원문과 대조해 뺀 것 — 남은 질문이 아니다(검토 결과에 결정 · 까닭이 있음)
                continue
            if c['status'] != 'approved':
                out['remaining_questions'].append({'item': c['text'], 'kind': '보류',
                                                   'source': f'{rv["doc_id"]} {rv["rev"]} {c["section"]} {c["line_start"]}줄', 'note': c['reason']})
                continue
            role = role_of(c, roles)
            if role is None:
                unmapped.append(f'{ref}({c["kind"]})')
                continue
            if role in ITEMS:
                out[ITEMS[role]].append({'candidate': ref, 'doc_id': rv['doc_id'], 'rev': rv['rev'], 'section': c['section'], 'quote': c['quote'], 'decision': c['decision']})
    if unmapped:
        raise Problem('결과/역할.csv', '어느 행에도 맞지 않는 승인 후보: ' + ', '.join(unmapped[:8]) + (' …' if len(unmapped) > 8 else ''))
    sop = json.loads(basis('sop.json').read_text(encoding='utf-8'))
    s = next((x for x in sop['sops'] if x['id'] == task), None)
    if s is None:
        raise Problem('입력/sop.json', f'{task}가 없음')
    out['sop_diff'] = sop_diff(s, out['preparation'], out['prohibitions'], out['completion'])
    write(RESULT / '선택작업_조건.json', dump(out))
    return out
