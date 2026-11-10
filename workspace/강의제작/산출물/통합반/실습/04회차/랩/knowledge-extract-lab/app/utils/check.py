"""app/features/의 후보 파일 · 검토 결과 · 응답 기록 짝과 review.md 칸의 구조 검사. 생성 · 수정 · 네트워크 접속을 하지 않는다.
후보의 인용이 짝지은 응답 기록의 답 글에 있는지(글자 · 숫자만 남겨 소문자로 비교)도 본다 — 답 글에 있다고 원문과 뜻이 맞는 것은 아니다.
어떤 후보가 맞는지, 빠진 지식, 어느 원문을 근거로 둘지는 판정하지 않는다 — 의미와 질문별 답은 원자료와 따로 대조한다.
사용:
  python run.py check                                   전체 구조 검사
  python run.py check output/candidates/<파일>.json [...]         파일별 계약 검사(후보 파일 · 검토 결과 파일)
"""
from pathlib import Path
import csv, hashlib, io, json, re, sys

HERE = Path(__file__).resolve().parents[2]
RESULT = HERE / 'output'
JUDGED = 'result.json'
PRACTICAL = False
TASK = 'SOP-COOL-14' if PRACTICAL else None          # 실전반: 이 사건의 작업 — 조건 근거 대조는 이 작업에 걸린 조건만 본다
SENT = '모델 서버'
PASTED = '채팅으로 받음'
KINDS = {'step', 'precondition', 'prohibition', 'completion', 'unit_value'}
COMPARATORS = {None, '>=', '>', '<=', '<', '=', 'range', '±'}
STATUS = {'채택': 'approved', '수정': 'approved', '제외': 'excluded', '보류': 'pending'}
MATCH = {'일치', '불일치', '원문 없음', '보류'}
TOP = ['doc_id', 'rev', 'doc_status', 'source_file', 'source_sha256', 'encoding', 'extractor', 'generated_at', 'model_run', 'candidates', 'unlocated']
REQUIRED = ['id', 'section', 'procedure', 'kind', 'text', 'quote', 'quote_match', 'line_start', 'line_end', 'refs', 'status']
FOOTER = re.compile(r'^-\s*(\S+)\s*-$')
LANG = re.compile(r'^\s*(?:\d+\.\s*)?(EN|KO):')
END = '의미와 질문별 답은 원자료와 따로 대조합니다.'


def squash(text):
    """글자 · 숫자만 남기고 소문자로 — 계약 「인용」의 normalized 비교."""
    return ''.join(c for c in str(text).lower() if c.isalnum())


def reply_strings(record):
    """응답 기록의 답 글에서 비교할 글들 — 답 글 그대로와, 답 글 안 JSON(처음 { 부터 끝 } 까지)을 풀어 낸 글 값 전부."""
    raw = str(record.get('response_text') or '')
    out = [raw]
    start, end = raw.find('{'), raw.rfind('}')
    if 0 <= start < end:
        try:
            stack = [json.loads(raw[start:end + 1])]
        except ValueError:
            stack = []
        while stack:
            x = stack.pop()
            if isinstance(x, str):
                out.append(x)
            elif isinstance(x, dict):
                stack += list(x.values())
            elif isinstance(x, list):
                stack += x
    return out


def in_replies(quote, records):
    """인용 전체(여러 줄이면 모든 줄)가 응답 기록들의 답 글 한 곳에 있는가 — 글자 · 숫자만 남겨 소문자로 비교한다."""
    key = squash(quote)
    return bool(key) and any(key in squash(s) for r in records for s in reply_strings(r))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def csv_rows(path):
    lines = [x for x in Path(path).read_text(encoding='utf-8-sig').splitlines() if not x.startswith('#')]
    return list(csv.DictReader(io.StringIO('\n'.join(lines))))


def register():
    return {r['파일']: r for r in csv_rows(HERE / 'data/documents/catalog.csv') if r.get('파일')}


def basis(name):
    mine = HERE / 'app/features/my_inputs' / name
    return mine if mine.is_file() else HERE / 'data' / name


def rule_ids():
    """검토 결과의 rule_links가 받는 규칙 id — 기준 조건표의 rule_id와, 제공 · 기준 조건표의 출처 칸에 적힌 규칙 id."""
    ids = set()
    for path in {basis('conditions.csv'), HERE / 'data/conditions.csv'}:
        for r in csv_rows(path):
            if path == basis('conditions.csv'):
                ids.add(r.get('rule_id'))
            ids |= set(re.findall(r'rule:[a-z0-9-]+', r.get('source_section') or ''))
    return ids - {None, ''}


def mark():
    path = HERE / 'output/.folder_mark'
    return path.read_text(encoding='utf-8').strip() if path.is_file() else None


def locate(text, quote):
    """(정확히 찾힌 수, 글자 · 숫자 비교로 찾힌 수) — 파일 전체에서."""
    return text.count(quote), squash(text).count(squash(quote)) if squash(quote) else 0


def check(path):
    errors, notes = [], []
    data = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if not isinstance(data, dict):
        return ['최상위가 객체가 아닙니다.'], notes
    missing = [k for k in TOP if k not in data]
    if missing:
        return [f'최상위 필드 없음: {missing}'], notes
    source = HERE / 'data/documents' / str(data['source_file'])
    if not source.is_file():
        return [f'data/documents/{data["source_file"]} 파일이 없습니다.'], notes
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != data['source_sha256']:
        errors.append('source_sha256이 data/documents/의 파일과 다릅니다(다른 파일을 읽었거나 해시를 지어냈음).')
    row = register().get(data['source_file'])
    if row is None:
        errors.append('data/documents/catalog.csv에 없는 파일입니다.')
    else:
        notes.append(f'문서 목록: {row["문서 식별자"]} {row["판"]}판 · 상태 {row["상태"]}')
        for key, col in [('doc_id', '문서 식별자'), ('rev', '판'), ('doc_status', '상태'), ('source_sha256', 'SHA-256')]:
            if str(data[key]) != row[col]:
                errors.append(f'{key} {data[key]!r}가 문서 목록의 {col} {row[col]!r}와 다릅니다.')
    try:
        text = raw.decode(str(data['encoding']))
    except (LookupError, UnicodeDecodeError) as e:
        return errors + [f'encoding {data["encoding"]!r}로 원문을 읽지 못했습니다({e.__class__.__name__}).'], notes
    if '�' in text:
        errors.append(f'encoding {data["encoding"]!r}로 읽은 원문에 깨진 글자(�)가 있습니다.')
    lines = text.splitlines()
    bilingual = any(LANG.match(x) for x in lines)
    scanned = row is not None and '스캔본' in row['상태']
    # 응답 기록 짝
    here = mark()
    runs = data['model_run'] if isinstance(data['model_run'], list) else []
    if not runs:
        errors.append('model_run이 비어 있습니다 — 후보 파일은 응답 기록에서 만듭니다.')
    paired = []
    for run in runs:
        rec_path = HERE / str(run.get('record', ''))
        if not run.get('record') or not rec_path.is_file():
            errors.append(f'model_run의 응답 기록이 없습니다: {run.get("record")!r}')
            continue
        rec = json.loads(rec_path.read_text(encoding='utf-8'))
        if rec.get('usable') is False:
            errors.append(f'{run.get("record")}: 쓸 내용이 없는 답의 기록입니다(usable false — {rec.get("note")}) — 이 기록으로 후보를 만들지 않습니다.')
        else:
            paired.append(rec)
        for key in ['request_hash', 'model', 'method']:
            if run.get(key) != rec.get(key):
                errors.append(f'model_run {run.get("record")}: {key} {run.get(key)!r}가 응답 기록의 {rec.get(key)!r}와 다릅니다.')
        if not rec.get('model') or not rec.get('received_at'):
            errors.append(f'{run.get("record")}: 응답 기록에 model · 받은 시각이 없습니다.')
        if here is not None and rec.get('folder_mark') != here:
            errors.append(f'{run.get("record")}: 다른 폴더의 응답 기록입니다(기록의 폴더 표지 {rec.get("folder_mark")!r}, 이 폴더 {here!r}) — '
                          '후보는 이 폴더에서 수업 모델을 불러 받은 답으로 만듭니다.')
        if run.get('reused_from') is not None:
            errors.append(f'model_run {run.get("record")}: reused_from {run.get("reused_from")!r} — 다른 폴더의 응답 기록으로는 후보를 만들지 않습니다.')
        if rec.get('method') == PASTED:
            notes.append(f'{run.get("record")}: 채팅으로 받은 답 — 수업 모델을 부른 기록으로 세지 않습니다.')
    if here is None and len({str(r.get('folder_mark')) for r in paired}) > 1:
        errors.append('output/.folder_mark가 없는데 짝지은 응답 기록의 폴더 표지가 여럿입니다 — 여러 폴더의 응답 기록을 섞었습니다.')
    reviewed = 'review' in data
    added = {(m.get('kind'), str(m.get('quote')), m.get('line_start')) for m in data.get('missing', []) if isinstance(m, dict) and m.get('added') is True} if reviewed else set()
    seen, dup, cands = set(), set(), {}
    for i, c in enumerate(data['candidates'] if isinstance(data['candidates'], list) else []):
        where = c.get('id', f'#{i}') if isinstance(c, dict) else f'#{i}'
        if not isinstance(c, dict):
            errors.append(f'{where}: 후보가 객체가 아님')
            continue
        miss = [k for k in REQUIRED if k not in c]
        if miss:
            errors.append(f'{where}: 필수 필드 없음 {miss}')
            continue
        cands[c['id']] = c
        if c['id'] in seen:
            errors.append(f'{where}: 중복 id')
        seen.add(c['id'])
        if c['kind'] not in KINDS:
            errors.append(f'{where}: 알 수 없는 kind {c["kind"]!r}')
        if not str(c['text']).strip():
            errors.append(f'{where}: text가 비어 있음')
        if not str(c['section']).strip():
            errors.append(f'{where}: section이 비어 있음')
        elif c['section'] != '머리말' and squash(str(c['section'])) not in squash(text):
            errors.append(f'{where}: 원문에 없는 절 표기 — section {c["section"]!r}')
        if c['procedure'] is not None and squash(str(c['procedure'])) not in squash(text):
            errors.append(f'{where}: 원문에 없는 절차 표기 — procedure {c["procedure"]!r}')
        if not isinstance(c['refs'], list):
            errors.append(f'{where}: refs는 목록이어야 함')
        ls, le, quote = c['line_start'], c['line_end'], str(c['quote'])
        if not (isinstance(ls, int) and isinstance(le, int) and not isinstance(ls, bool) and 1 <= ls <= le <= len(lines)):
            errors.append(f'{where}: line_start · line_end가 원문 줄 범위(1~{len(lines)}) 안의 정수가 아님')
            continue
        segment = '\n'.join(lines[ls - 1:le])
        exact, near = locate(text, quote)
        by_reviewer = reviewed and c.get('origin') == 'reviewer'    # 같은 문장이 여러 곳이면 코드는 줄을 정하지 못한다 — 검토자가 고른 줄은 받는다
        if not quote.strip():
            errors.append(f'{where}: quote가 비어 있음')
        elif c['quote_match'] == 'exact':
            if quote not in segment:
                errors.append(f'{where}: quote가 {ls}~{le}줄에 글자 그대로 없음' + ('(파일의 다른 줄에 있음)' if exact else ''))
            elif exact > 1 and not by_reviewer:
                errors.append(f'{where}: quote가 원문 {exact}곳에 맞음 — 코드가 찾은 인용이 여러 곳에 맞으면 찾지 못한 것(unlocated)으로 두고, 그 줄은 검토자가 골라 더한다')
        elif c['quote_match'] == 'normalized':
            if quote in segment:
                errors.append(f'{where}: 글자 그대로 찾히는 인용은 quote_match가 exact')
            elif squash(quote) not in squash(segment):
                errors.append(f'{where}: quote가 {ls}~{le}줄에서 글자 · 숫자 비교로도 찾히지 않음')
            elif near > 1 and not by_reviewer:
                errors.append(f'{where}: quote가 글자 · 숫자 비교로 원문 {near}곳에 맞음 — 코드가 찾은 인용이면 찾지 못한 것(unlocated)으로 두고, 그 줄은 검토자가 골라 더한다')
        else:
            errors.append(f'{where}: quote_match는 exact 또는 normalized')
        if reviewed and c.get('origin') == 'reviewer':
            if (c['kind'], quote, ls) not in added:
                errors.append(f'{where}: origin reviewer인데 같은 종류 · 인용 · 줄의 missing 항목(added: true)이 없음 — 검토자가 더한 후보는 missing에 함께 적습니다')
        elif paired:
            said = str((c.get('before') or {}).get('quote', quote)) if reviewed else quote    # 검토에서 인용을 고쳤으면(수정) 고치기 전 인용으로 본다
            if said.strip() and not in_replies(said, paired):
                errors.append(f'{where}: 인용이 짝지은 응답 기록의 답 글에 없음 — 후보는 모델의 답에서 만듭니다' + ('(검토에서 고친 인용은 before.quote로 봄)' if reviewed else ''))
        if bilingual:
            said = {m.group(1) for x in lines[ls - 1:le] for m in [LANG.match(x)] if m}
            if c.get('lang') not in ('ko', 'en'):
                errors.append(f'{where}: 영문 원본과 번역이 함께 있는 문서라 lang(ko · en)이 필요')
            elif len(said) == 1 and said != {c['lang'].upper()}:
                errors.append(f'{where}: lang {c["lang"]!r}가 인용한 줄({", ".join(sorted(said))})과 다름')
        if scanned:
            foot = next((FOOTER.match(x.strip()).group(1) for x in lines[le - 1:] if FOOTER.match(x.strip())), None)
            if not c.get('page'):
                errors.append(f'{where}: 스캔본에서 인용한 후보는 page가 필요')
            elif foot != c['page']:
                errors.append(f'{where}: page {c["page"]!r}가 그 줄이 있는 쪽 꼬리({foot})와 다름')
        if c['kind'] == 'step' and not (isinstance(c.get('order'), int) and not isinstance(c.get('order'), bool) and c['order'] >= 1):
            errors.append(f'{where}: step에는 1 이상의 정수 order가 필요')
        if c['kind'] == 'unit_value':
            if not isinstance(c.get('value'), (int, float)) or isinstance(c.get('value'), bool):
                errors.append(f'{where}: unit_value의 value는 숫자여야 함')
            if not c.get('unit'):
                errors.append(f'{where}: unit_value에 unit이 없음')
            if c.get('comparator', 'missing') not in COMPARATORS:
                errors.append(f'{where}: comparator가 계약 값이 아님 {c.get("comparator", "(필드 없음)")!r}')
            if c.get('comparator') == 'range' and not isinstance(c.get('value_max'), (int, float)):
                errors.append(f'{where}: range에는 value_max가 필요')
            if not c.get('value_text') or str(c['value_text']) not in quote:
                errors.append(f'{where}: value_text가 quote 안에 그대로 없음')
        key = (c['kind'], c['section'], c['procedure'], c['text'], quote, c.get('value_text'))
        if key in dup:
            errors.append(f'{where}: 같은 종류 · 절 · 내용 · 인용 · 값의 후보가 이미 있음')
        dup.add(key)
        if reviewed:
            dec = c.get('decision')
            if dec not in STATUS:
                errors.append(f'{where}: decision은 채택 · 수정 · 제외 · 보류 중 하나')
            elif c['status'] != STATUS[dec]:
                errors.append(f'{where}: {dec}이면 status는 {STATUS[dec]}')
            if not str(c.get('reason', '')).strip():
                errors.append(f'{where}: 결정 이유(reason)가 없음')
            if dec == '수정' and not c.get('before'):
                errors.append(f'{where}: 수정에는 바꾸기 전 값(before)이 필요')
            if c.get('origin') not in ('extractor', 'reviewer'):
                errors.append(f'{where}: origin은 extractor 또는 reviewer')
        elif c['status'] != 'pending':
            errors.append(f'{where}: 추출 직후 status는 pending')
    for u in data['unlocated'] if isinstance(data['unlocated'], list) else []:
        if not isinstance(u, dict) or not u.get('quote') or not u.get('note'):
            errors.append('unlocated의 항목마다 quote와 찾지 못한 까닭(note)이 필요')
        elif 1 in locate(text, str(u['quote'])):
            notes.append(f'참고: unlocated의 인용 「{str(u["quote"])[:30]}」은 원문 한 곳에서 찾힙니다.')
    if reviewed:
        rv = data['review'] if isinstance(data['review'], dict) else {}
        for key in ['reviewer', 'reviewed_at', 'candidates_file', 'candidates_sha256']:
            if not rv.get(key):
                errors.append(f'review.{key} 없음')
        original = HERE / str(rv.get('candidates_file', ''))
        if rv.get('candidates_file') and not original.is_file():
            errors.append(f'review.candidates_file이 없습니다: {rv.get("candidates_file")}')
        elif rv.get('candidates_file') and sha(original) != rv.get('candidates_sha256'):
            errors.append('후보 파일 원본의 SHA-256이 review.candidates_sha256과 다릅니다(검토 뒤 후보 원본이 바뀜).')
        for m in data.get('missing', []):
            if not isinstance(m, dict) or not m.get('quote') or not any(locate(text, str(m['quote']))):
                errors.append(f'missing {m.get("section") if isinstance(m, dict) else m}: quote가 원문에 없음')
        known = rule_ids()
        for link in data.get('rule_links', []):
            if not isinstance(link, dict):
                errors.append('rule_links의 항목이 객체가 아님')
                continue
            rid, ids = link.get('rule_id'), link.get('candidates')
            if rid not in known:
                errors.append(f'rule_links {rid!r}: 기준 조건표의 rule_id나 그 출처 칸의 규칙 id가 아님')
            if link.get('match') not in MATCH:
                errors.append(f'rule_links {rid}: match는 일치 · 불일치 · 원문 없음 · 보류 중 하나')
            if not str(link.get('note', '')).strip():
                errors.append(f'rule_links {rid}: 까닭(note)이 없음')
            if not isinstance(ids, list) or any(x not in cands for x in ids):
                errors.append(f'rule_links {rid}: candidates는 이 파일 후보 id의 목록')
            elif link.get('match') in ('일치', '불일치') and not ids:
                errors.append(f'rule_links {rid}: {link.get("match")}이면 근거 후보 id가 필요')
            elif link.get('match') == '원문 없음' and ids:
                errors.append(f'rule_links {rid}: 원문 없음이면 candidates는 빈 목록')
    kinds = {}
    for c in cands.values():
        kinds[c.get('kind')] = kinds.get(c.get('kind'), 0) + 1
    notes.append(f'후보 {len(cands)}개, 종류별 {kinds}, 찾지 못한 인용 {len(data["unlocated"]) if isinstance(data["unlocated"], list) else 0}개')
    if reviewed:
        dec = {}
        for c in cands.values():
            dec[c.get('decision')] = dec.get(c.get('decision'), 0) + 1
        notes.append(f'결정별 {dec}, 누락 기록 {len(data.get("missing", []))}개, 조건 근거 대조 {len(data.get("rule_links", []))}개')
    return errors, notes


def seen_list(path):
    """통과 줄이 말할 「본 것」 — 그 파일에서 실제로 본 검사만."""
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return ['필드']
    if not isinstance(data, dict) or 'candidates' not in data:
        return ['필드']
    out = ['필드', '인용이 선언한 줄에 있는지']
    if data.get('model_run'):
        out += ['응답 기록 짝(모델 · 받은 시각 · ' + ('이 폴더의 기록인지)' if mark() else '기록끼리 한 폴더의 것인지 — 이 폴더의 표지가 없어 이 폴더의 기록인지는 보지 못함)'),
                '모델 답에서 온 후보의 인용이 짝지은 답 글에 있는지']
    if 'review' in data:
        out += ['결정 · 상태 · 이유', '검토자가 더한 후보마다 missing 항목이 있는지', '조건 근거 대조의 꼴']
    return out


def run(path):
    try:
        return check(path)
    except (OSError, ValueError, TypeError, AttributeError, KeyError) as e:
        return [f'읽기 실패: {e}'], []


def check_selected(path):
    """output/selected_task.json — 항목마다 검토 결과의 승인 후보를 가리키는지."""
    errors = []
    data = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    for key in ['task', 'basis', 'preparation', 'prohibitions', 'completion', 'remaining_questions', 'sop_diff']:
        if key not in data:
            errors.append(f'필드 없음: {key}')
    if 'task' in data and data['task'] != TASK:
        errors.append(f'task {data["task"]!r}가 이 사건의 작업 {TASK}와 다름')
    for part in ['preparation', 'prohibitions', 'completion']:
        for item in data.get(part, []):
            ref = str(item.get('candidate', ''))
            file, _, cid = ref.partition('#')
            target = HERE / file
            if not target.is_file():
                errors.append(f'{part}: {ref!r}의 검토 결과 파일이 없음')
                continue
            review = json.loads(target.read_text(encoding='utf-8-sig'))
            cand = next((c for c in review.get('candidates', []) if c.get('id') == cid), None)
            if cand is None:
                errors.append(f'{part}: {ref!r}의 후보가 없음')
            elif cand.get('status') != 'approved':
                errors.append(f'{part}: {ref!r}는 승인(approved) 후보가 아님 — 보류 · 원문 미확인은 remaining_questions에')
            else:
                for key in ['section', 'quote']:
                    if item.get(key) != cand.get(key):
                        errors.append(f'{part}: {ref!r}의 {key}가 검토 결과와 다름')
                for key in ['doc_id', 'rev']:
                    if item.get(key) != review.get(key):
                        errors.append(f'{part}: {ref!r}의 {key}가 검토 결과와 다름')
    for q in data.get('remaining_questions', []):
        if not isinstance(q, dict) or not q.get('item') or not q.get('note'):
            errors.append('remaining_questions의 항목마다 item과 note가 필요')
    for d in data.get('sop_diff', []):
        if not isinstance(d, dict) or not d.get('item') or not d.get('note') or d.get('where') not in ('카드에만', 'SOP 구조에만'):
            errors.append('sop_diff의 항목마다 item · note와 where(카드에만 · SOP 구조에만)가 필요')
    return errors


def empty_tables(md):
    """기록 파일의 절별 표 행 수 · 빈 칸 수 · 칸 수가 머리 줄과 다른 행 수."""
    out, sec, width = {}, '머리', None
    for line in md.splitlines():
        if line.startswith('## '):
            sec, width = line[3:].strip(), None
            continue
        if line.startswith('|'):
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            if all(re.fullmatch(r':?-{2,}:?', c) for c in cells):
                out.setdefault(sec, [0, 0, 0])
                continue
            if width is None:
                width = len(cells)
                continue
            out.setdefault(sec, [0, 0, 0])
            out[sec][0] += 1
            out[sec][1] += sum(1 for c in cells if not c)
            out[sec][2] += len(cells) != width
        elif not line.strip():
            width = None
    return out


def slot_errors():
    """정할 자리의 꼴 — 제공 코드(app/utils/extract.py)의 검사로 본다. 비어 있는 자리는 결과 화면의 단계 띠에서 짚으므로 여기서는 꼴만."""
    from app.utils import extract as X
    out = []
    for fn in (X.settings, X.expected_rows, X.decision_rows, lambda: X.rule_rows(TASK), (X.role_rows if PRACTICAL else (lambda: None))):
        try:
            fn()
        except X.Problem as e:
            out.append(f'정할 자리: {e}')
        except OSError as e:
            out.append(f'정할 자리 파일을 읽지 못함: {e}')
    return out


def stages():
    todo = []
    print(f'기준 입력: {basis("conditions.csv").relative_to(HERE).as_posix()} · {basis(JUDGED).relative_to(HERE).as_posix()}')
    here = mark()
    recs = []
    for p in sorted((HERE / 'output/model_responses').glob('*.json')):
        try:
            recs.append(json.loads(p.read_text(encoding='utf-8')))
        except (OSError, ValueError):
            todo.append(f'응답_기록/{p.name}을 읽지 못했습니다.')
    sent = sum(1 for r in recs if r.get('method') == SENT and r.get('folder_mark') == here)
    empty = sum(1 for r in recs if r.get('usable') is False)
    chat = sum(1 for r in recs if r.get('method') == PASTED)
    other = sum(1 for r in recs if r.get('folder_mark') != here)
    print(f'응답 기록 {len(recs)}개(이 폴더에서 모델 서버로 보낸 요청 {sent} · 쓸 내용이 없던 답 {empty} · 채팅으로 받음 {chat} · 다른 폴더 기록 {other})')
    from app.utils import extract as _X
    try:
        has_prompt = bool(_X.prompt_text())
    except _X.Problem:
        has_prompt = False
    print(f'요청 글 app/features/prompt.md: {"있음" if has_prompt else "없음(빈 틀)"}')
    if not has_prompt:
        todo.append('요청 글 app/features/prompt.md가 아직 빈 틀입니다.')
    files = sorted((HERE / 'output/candidates').glob('*.json'))
    print(f'후보 파일 {len(files)}개')
    first = []
    for f in files:
        errors, notes = run(f)
        print(f'    {f.name}: {"구조 검사 통과" if not errors else f"계약 확인 필요 {len(errors)}건"} · ' + ' · '.join(notes))
        if errors:
            todo.append(f'{f.name} 계약 오류(파일 이름을 인자로 주고 실행하면 목록이 나옵니다).')
        try:
            first.append(str(json.loads(f.read_text(encoding='utf-8-sig')).get('generated_at')))
        except (OSError, ValueError, AttributeError):
            pass
    if len(files) < 2:
        todo.append('다른 문서에 다시 실행한 후보 파일이 아직 없습니다.')
    reviews = sorted((HERE / 'output/reviews').glob('*.json'))
    print(f'검토 결과 {len(reviews)}개')
    linked = set()
    for f in reviews:
        errors, notes = run(f)
        print(f'    {f.name}: {"구조 검사 통과" if not errors else f"계약 확인 필요 {len(errors)}건"} · ' + ' · '.join(notes))
        if errors:
            todo.append(f'{f.name} 계약 오류.')
        try:
            data = json.loads(f.read_text(encoding='utf-8-sig'))
        except (OSError, ValueError):
            continue
        cands = [c for c in data.get('candidates', []) if isinstance(c, dict)]
        linked |= {x.get('rule_id') for x in data.get('rule_links', []) if isinstance(x, dict)}
        if not any(c.get('status') == 'approved' for c in cands):
            print(f'    참고: {f.name}에 approved 후보가 없습니다 — 다음 실습은 approved 후보만 씁니다.')
        elif cands and all(c.get('decision') == '채택' for c in cands) and not data.get('missing'):
            print(f'    참고: {f.name}는 모든 후보가 「채택」이고 누락 기록이 0개입니다 — 원문과 줄마다 대조했는지 검토 기록에 남깁니다.')
    if not reviews:
        todo.append('검토 결과가 없습니다.')
    table = {r.get('rule_id') for r in csv_rows(basis('conditions.csv')) if TASK is None or r.get('action') == TASK} - {None, ''}
    rest = sorted(table - linked)
    scope = f'이 작업({TASK})에 걸린 조건' if TASK else '조건표의 조건'
    print(f'조건 근거 대조: {scope} {len(table)}개 가운데 rule_links가 있는 것 {len(table & linked)}개' + (f' — 없는 것 {", ".join(rest)}' if rest else ''))
    if rest:
        todo.append(f'{scope}마다 검토 결과의 rule_links가 필요합니다: ' + ', '.join(rest))
    if PRACTICAL:
        sel = HERE / 'output/selected_task.json'
        if not sel.is_file():
            print('selected_task.json: 없음')
            todo.append('output/selected_task.json이 없습니다.')
        else:
            try:
                errs = check_selected(sel)
            except (OSError, ValueError, AttributeError) as e:
                errs = [f'읽기 실패: {e}']
            print(f'selected_task.json: {"구조 검사 통과" if not errs else f"계약 확인 필요 {len(errs)}건"}')
            for e in errs:
                print('    - ' + e)
            if errs:
                todo.append('selected_task.json 계약 오류.')
    record = HERE / 'app/features/review.md'
    print(f'review.md')
    if not record.is_file():
        todo.append('review.md가 없습니다.')
    else:
        text = record.read_text(encoding='utf-8-sig')
        for line in text.splitlines():
            if re.match(r'^- [^:]+:\s*$', line):
                print(f'    빈 항목: {line.strip()}')
                todo.append(f'review.md의 빈 항목 「{line.strip()}」')
        for sec, (n, blanks, shifted) in empty_tables(text).items():
            state = '표에 기록 없음' if n == 0 else f'{n}행' + (f', 빈 칸 {blanks}개' if blanks else '') + (f', 칸 수가 머리 줄과 다른 행 {shifted}개' if shifted else '')
            print(f'    「{sec}」: {state}')
            if n == 0 or blanks or shifted:
                todo.append(f'review.md 「{sec}」 — {state}')
        when = re.search(r'^- 기대 칸을 쓴 시각:[ \t]*(\S.*)$', text, re.M)
        stamp = lambda x: x.replace('T', ' ')[:16]
        if when and first and stamp(min(first)) < stamp(when.group(1).strip()):
            todo.append(f'review.md의 기대 칸을 쓴 시각({when.group(1).strip()})이 첫 후보 파일({min(first)})보다 뒤입니다.')
    todo += slot_errors() + chosen_errors(HERE) + provided_errors(HERE)
    print()
    if todo:
        print('구조 확인 필요:')
        for t in todo:
            print('  - ' + t)
        print(END)
        return 1
    print('구조 검사 통과. ' + END)
    return 0


def chosen_errors(root):
    """app/features/decisions.csv — 빈 칸 · 근거 꼴(파일:줄)만 본다. 고른 것이 맞는지는 보지 않는다."""
    import csv, io, re
    p = root / 'app/features' / 'decisions.csv'
    if not p.is_file():
        return ['app/features/decisions.csv가 없습니다 — 받은 ZIP의 빈 틀을 지우지 않습니다.']
    lines = [x for x in p.read_text(encoding='utf-8-sig').splitlines() if x.strip() and not x.lstrip().startswith('#')]
    rows = list(csv.DictReader(io.StringIO('\n'.join(lines))))
    need = ['지점', '고른_것', '근거', '바뀌는_답']
    if not lines or [c.strip() for c in csv.reader([lines[0]]).__next__()] != need:
        return ['app/features/decisions.csv: 열 이름이 ' + ','.join(need) + '이어야 합니다.']
    out = []
    for n, r in enumerate(rows, 1):
        empty = [c for c in need if not (r.get(c) or '').strip()]
        if empty:
            out.append(f'app/features/decisions.csv {n}번째 행: 빈 칸 ' + ', '.join(empty) + '(못 정했으면 고른_것에 「미결」).')
        elif not re.search(r'[^\s:]+:\d+', r['근거']):
            out.append(f'app/features/decisions.csv {n}번째 행: 근거에 파일:줄이 없습니다.')
    return out

import hashlib as _h
_PROVIDED = {
 "app/ui/render.py": "794a7c0de17bbbf7dd6e2896397c1db32cb4079b6fe7dfa88dc67160c2a0d81e",
 "app/utils/actions.py": "43d7aa989110200367807cdb12f2b69bd8ef3d44363068d99d4aa10a83bcc585",
 "app/utils/extract.py": "8e9e8b199eea3ae695ead4d2f42df7978063a64b6230ee23a12cdf5c2bb46b23",
 "app/utils/llm_client.py": "53358ba7b090ab65dc800d877b50e9a495289734f039df2504e8ea03bb0b697a",
 "app/utils/results.py": "1c5b0596745e9ac1e9b7f06d84c7463d99720597edcf46801d32a51e640ae86b",
 "run.py": "deea21d94d8e48e7ae7d06879e17cbbfa885a11f68c371e7398e6a23bd40e032"
}
def provided_errors(root):
    out = []
    for name, digest in _PROVIDED.items():
        p = root / name
        if not p.is_file():
            out.append(f'제공 파일이 없습니다: {name} — 받은 ZIP의 것으로 되돌리세요.')
        elif _h.sha256(p.read_bytes()).hexdigest() != digest:
            out.append(f'제공 파일이 바뀌었습니다: {name} — 받은 ZIP의 것으로 되돌리세요.')
    return out

if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(stages())
    failed = False
    for arg in sys.argv[1:]:
        errors, notes = run(arg)
        print(f'== {arg}')
        for n in notes:
            print('  ' + n)
        if errors:
            failed = True
            print(f'  계약 확인 필요 {len(errors)}건')
            for e in errors[:40]:
                print('  - ' + e)
            if len(errors) > 40:
                print(f'  … 외 {len(errors) - 40}건')
        else:
            print('  구조 검사 통과 — 본 것: ' + ' · '.join(seen_list(arg)) + '.')
    print(END)
    sys.exit(1 if failed else 0)
