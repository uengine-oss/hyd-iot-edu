"""문서 목록의 문서를 읽어 조각으로 나누고, 조각마다 결과/prompt.md와 함께 수업 모델에 보내 받은 답을 후보 파일로 바꾼다.
후보의 인용이 원문 어느 줄에 있는지는 코드로 찾는다(입출력_계약.md 「후보 파일」 · 「후보 하나」).

사용(실습 폴더에서):
  python 결과/extract_candidates.py --list                     읽기 · 나누기만 — 문서마다 판 · 상태 · 글자 방식 · 줄 수, 조각 목록, 보낼 요청 수(보내지 않는다)
  python 결과/extract_candidates.py [파일 이름 ...]              그 문서들(주지 않으면 문서 관리 기준을 뺀 전부)을 보내고 결과/후보/<문서 식별자>_<판>.json을 쓴다
  python 결과/extract_candidates.py --again <파일 이름> <조각 번호>  그 조각 하나를 한 번 더 보내 두 응답 기록의 답을 견준다(후보 파일은 쓰지 않는다)
같은 요청의 응답 기록이 있으면 llm_client가 다시 보내지 않고 그 기록을 돌려준다.
"""
from datetime import datetime
from pathlib import Path
import argparse
import csv
import hashlib
import io
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
ENCODINGS = ('utf-8', 'cp949')          # 읽는 순서 — UTF-8로 풀리지 않으면 CP949(규정 발췌가 CP949)
SKIP = {'DC-01'}                        # 문서 관리 기준 — 판 · 상태의 뜻을 정하는 문서라 작업 지식을 뽑지 않는다
LIMIT = 1000                            # 조각 하나의 글자 수 상한
HEAD = re.compile(r'^(##\s+\S|제\d+조\(|HM-9\.\d+\s+\S|=== 스캔)')   # 절 머리 — md의 ##, 규정의 「제N조(」, 스캔본의 「HM-9.x 제목」
FOOTER = re.compile(r'^-\s*(\S+)\s*-$')                           # 스캔본 쪽 꼬리 「- 9-3 -」
LANG = re.compile(r'^\s*(?:\d+\.\s*)?(EN|KO):')
KINDS = ('step', 'precondition', 'prohibition', 'completion', 'unit_value')
COMPARATORS = {None, '>=', '>', '<=', '<', '=', 'range', '±'}
SAME_SIGN = {'≥': '>=', '≤': '<=', '＝': '='}


def squash(text):
    """글자 · 숫자만 남기고 소문자로 — 계약의 normalized 비교."""
    return ''.join(c for c in str(text).lower() if c.isalnum())


def register(root):
    """자료/문서_목록.csv의 행 — 첫 줄(내보내기 머리)은 # 로 시작한다."""
    lines = [x for x in (root/'자료/문서_목록.csv').read_text(encoding='utf-8-sig').splitlines() if not x.startswith('#')]
    return list(csv.DictReader(io.StringIO('\n'.join(lines))))


def stem(row):
    return f'{row["문서 식별자"]}_{row["판"]}' if row['판'] else row['문서 식별자']


def read_document(root, row):
    """(글, 글자 방식, 원문 바이트) 또는 읽지 못한 까닭(str)."""
    if not row['파일']:
        return '받은 파일이 없음(목록에만 있는 문서)'
    path = root/'자료'/row['파일']
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


def split_chunks(text):
    """[(첫 줄 번호, 조각 글)] — 절 머리에서 끊고, 이어진 절은 LIMIT 글자 안에서 묶는다. 목차 줄(점선)은 머리로 보지 않는다."""
    lines = text.splitlines()
    blocks, cur, start = [], [], 1
    for n, line in enumerate(lines, 1):
        if HEAD.match(line.strip()) and cur and '....' not in line:
            blocks.append((start, cur))
            cur, start = [], n
        cur.append(line)
    if cur:
        blocks.append((start, cur))
    out, buf, first = [], [], None
    for s, block in blocks:
        body = '\n'.join(block)
        if buf and len('\n'.join(buf)) + len(body) > LIMIT:
            out.append((first, '\n'.join(buf)))
            buf, first = [], None
        if first is None:
            first = s
        buf.append(body)
    if buf:
        out.append((first, '\n'.join(buf)))
    return out


def build_request(prompt, row, first, body):
    return [{'role': 'system', 'content': prompt},
            {'role': 'user', 'content': f'문서 {row["문서 식별자"]} 판 {row["판"]} 상태 {row["상태"]} — 원문 {first}줄부터:\n\n{body}'}]


def parse_reply(raw):
    """답 글 → (답 dict, 문제). 답 글 속 처음 { 부터 끝 } 까지를 JSON으로 읽고, 길이 상한에서 잘려 읽지 못하면 앞의 온전한 후보만 건진다."""
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
    """줄마다 (시작 위치, 끝 위치) — splitlines()와 같은 줄 나눔."""
    spans, pos = [], 0
    for line in text.splitlines(keepends=True):
        body = line.rstrip('\r\n\x0b\x0c\x1c\x1d\x1e\x85  ')
        spans.append((pos, pos + len(body)))
        pos += len(line)
    return spans


def locate(text, lines, quote):
    """인용의 (line_start, line_end, quote_match) — 원문 한 곳에만 맞을 때. 여러 곳에 맞거나 없으면 None."""
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
    for b in range(1, len(lines) + 1):                  # 가장 먼저 끝나는 줄, 그 줄로 끝나는 가장 짧은 범위
        for a in range(b, max(0, b - 7), -1):
            if key in squash('\n'.join(lines[a - 1:b])):
                return a, b, 'normalized'
    return None


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
    """스캔본 — 그 줄 뒤에 처음 나오는 쪽 꼬리의 쪽 표기."""
    return next((FOOTER.match(x.strip()).group(1) for x in lines[line_end - 1:] if FOOTER.match(x.strip())), None)


def lang_of(lines, start, end, quote):
    said = {m.group(1) for x in lines[start - 1:end] for m in [LANG.match(x)] if m}
    if len(said) == 1:
        return said.pop().lower()
    return 'ko' if re.search('[가-힣]', quote) else 'en'


def contract_problem(item, text):
    """계약 꼴에 맞지 않아 후보로 둘 수 없는 까닭(없으면 None) — 절 · 절차 표기가 원문에 있는지, 단계 번호, 기준값 필드."""
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
        runs.append({'record': reply['file'], 'request_hash': reply['request_hash'], 'model': reply['model'], 'method': reply['method'],
                     'reused_from': reply.get('reused_from')})
        data, problem = parse_reply(reply.get('response_text') or '')
        if problem:
            warnings.append(f'{reply["file"]}: {problem}')
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
            found = locate(text, lines, quote)
            if not found:
                unlocated.append(item | {'status': 'pending', 'note': '원문 한 곳에서 찾지 못함(원문에 없거나 여러 곳에 맞음)'})
                continue
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
            if c['kind'] == 'unit_value':
                for k in ('value', 'value_max'):
                    if c.get(k) is not None:
                        item[k] = as_number(c[k])
                item['unit'] = c.get('unit')
                item['comparator'] = SAME_SIGN.get(c.get('comparator'), c.get('comparator'))
                item['value_text'] = c.get('value_text')
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


def documents(root, names):
    """보낼 문서 [(행, 글, 글자 방식, 원문 바이트)] — 읽은 결과를 문서마다 찍는다."""
    rows = register(root)
    missing = [n for n in names if n not in {r['파일'] for r in rows}]
    if missing:
        raise SystemExit(f'문서 목록에 없는 파일 이름: {", ".join(missing)}')
    out = []
    for row in rows:
        if names and row['파일'] not in names:
            continue
        got = read_document(root, row)
        label = f'{row["문서 식별자"]} {row["판"] or "(판 없음)"} · {row["상태"]}'
        if isinstance(got, str):
            print(f'{label}: 읽지 못함 — {got}')
            continue
        text, enc, raw = got
        print(f'{label}: {row["파일"]} · 글자 방식 {enc} · {len(text.splitlines())}줄')
        if row['문서 식별자'] in SKIP and not names:
            print('  문서 관리 기준이라 후보를 뽑지 않음(판 · 상태의 뜻을 읽는 데 씀)')
            continue
        out.append((row, text, enc, raw))
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description='문서 조각을 수업 모델에 보내 후보 파일을 만든다')
    p.add_argument('files', nargs='*', help='자료/ 안의 파일 이름(주지 않으면 문서 관리 기준을 뺀 전부)')
    p.add_argument('--list', action='store_true', help='보내지 않고 읽기 · 나누기 결과와 보낼 요청 수만 본다')
    p.add_argument('--again', nargs=2, metavar=('파일', '조각'), help='그 문서의 조각 하나를 한 번 더 보내 두 답을 견준다')
    a = p.parse_args(argv)
    sys.path.insert(0, str(ROOT))
    from llm_client import ask, count_to_send
    prompt_file = ROOT/'결과/prompt.md'
    prompt = prompt_file.read_text(encoding='utf-8') if prompt_file.is_file() else ''
    if not prompt.strip() and not a.list:
        raise SystemExit('결과/prompt.md가 비어 있습니다 — 요청 글을 먼저 짭니다.')
    docs = documents(ROOT, [a.again[0]] if a.again else a.files)
    if a.again:
        row, text, _, _ = docs[0]
        parts = split_chunks(text)
        no = int(a.again[1])
        if not 1 <= no <= len(parts):
            raise SystemExit(f'조각 번호는 1~{len(parts)}')
        request = build_request(prompt, row, *parts[no - 1])
        quotes = []
        for reply in (ask(request), ask(request, again=True)):
            got = to_candidates(row, text, [reply])[0]
            quotes.append({squash(c['quote']) for c in got})
            print(f'{reply["file"]}: 후보 {len(got)}개 · 받은 시각 {reply.get("received_at")}')
        print(f'두 답에 함께 있는 인용 {len(quotes[0] & quotes[1])}개 · 첫 답에만 {len(quotes[0] - quotes[1])}개 · 다시 보낸 답에만 {len(quotes[1] - quotes[0])}개')
        return 0
    requests = []
    for row, text, _, _ in docs:
        for no, (first, body) in enumerate(split_chunks(text), 1):
            if a.list:
                print(f'  조각 {no}: {first}~{first + body.count(chr(10))}줄 · {len(body)}자')
            requests.append(build_request(prompt, row, first, body))
    print(f'문서 {len(docs)}개 · 조각 {len(requests)}개')
    count_to_send(requests)
    if a.list:
        return 0
    out_dir = ROOT/'결과/후보'
    out_dir.mkdir(parents=True, exist_ok=True)
    for row, text, enc, raw in docs:
        replies = [ask(build_request(prompt, row, first, body)) for first, body in split_chunks(text)]
        cands, unlocated, warnings, runs = to_candidates(row, text, replies)
        result = {'doc_id': row['문서 식별자'], 'rev': row['판'], 'doc_status': row['상태'], 'source_file': row['파일'],
                  'source_sha256': hashlib.sha256(raw).hexdigest(), 'encoding': enc,
                  'extractor': 'python 결과/extract_candidates.py(요청 글 결과/prompt.md · 절 머리에서 끊은 1,000자 조각)',
                  'generated_at': datetime.now().astimezone().isoformat(timespec='seconds'),
                  'model_run': runs, 'candidates': cands, 'unlocated': unlocated, 'warnings': warnings}
        (out_dir/f'{stem(row)}.json').write_text(dump(result), encoding='utf-8')
        print(f'{stem(row)}: 후보 {len(cands)}개 · 찾지 못한 인용 {len(unlocated)}개 · 경고 {len(warnings)}개 → 결과/후보/{stem(row)}.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
