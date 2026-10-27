"""강사 참조 추출 함수 — 학생 배포 금지.

원문 Markdown의 절(##)·절차(###)·번호 단계·표·문장을 읽고 규칙으로 후보를 만든다.
LLM·네트워크를 쓰지 않는다. 출력 계약은 학생 시작본의 `입력/출력_계약.md`와 같다.

사용: python extract_reference.py <원문.md> --doc HM-8 --out <후보.json>
"""
from pathlib import Path
import argparse
import datetime as dt
import hashlib
import json
import re

NUM = r'(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)'
UNITS = ['mm/s', 'l/min', 'L/min', '만 원', '시간', '호기', 'bar', 'mm', '℃', '%', 'h', '분', '초', '원', '개', '명', '일', '건', '회']
UNIT = '(' + '|'.join(re.escape(u) for u in UNITS) + ')'
VALUE = re.compile(r'(?<![\w.\-~])(±\s*)?' + NUM + r'(?:\s*~\s*' + NUM + r')?\s*' + UNIT + r'(?![A-Za-z/])')
COMPARATORS = [('이상', '>='), ('이하', '<='), ('미만', '<'), ('초과', '>'), ('이내', '<='), ('아래', '<'), ('넘', '>')]
AFTER = re.compile(r'^\s*(?:를|을|이|가|로|으로|의)?\s*(이상|이하|미만|초과|이내|아래|넘)')

PROHIBITION = re.compile(r'않는다|않고|않는 것|말 것|금지|이내로 한다|안 된다')
COMPLETION = re.compile(r'성공한 것이다|정상이다|정상이면|완료로 본다|돌아왔는지|내려왔는지|회복 판정|시운전 확인|시운전 뒤|미달로 적')
PRECONDITION = re.compile(r'때만|경우에만|전에는|뒤에만|인지 확인한다|을 확인한다|를 확인한다|(?:이|하|으|되|가|보이|오르|넘으|떨어지)면[\s,]|^승인[:은]')
REF = re.compile(r'(SOP-[A-Z]+-)(\d+)(?:~(\d+))?|(?<![\w-])([A-Z]{2}-\d+\.\d+)')


def number(text):
    value = float(text.replace(',', ''))
    return int(value) if value.is_integer() else value


def refs_in(text, own):
    found = []
    for m in REF.finditer(text):
        if m.group(1):
            start = int(m.group(2)); end = int(m.group(3) or start)
            ids = [f'{m.group(1)}{n}' for n in range(start, end + 1)]
        else:
            ids = [m.group(4)]
        for i in ids:
            if i not in found and i not in own:
                found.append(i)
    return found


def sentences(line):
    return [s for s in re.split(r'(?<=[^\d]\.)\s+', line.strip()) if s.strip()]


def values(sentence):
    out = []
    for m in VALUE.finditer(sentence):
        plus, low, high, unit = m.groups()
        tail = sentence[m.end():m.end() + 12]
        cmp = None
        a = AFTER.match(tail)
        end = m.end()
        if a:
            cmp = dict(COMPARATORS)[a.group(1)]
            end = m.end() + a.end()
        item = {'value': number(low), 'unit': unit, 'comparator': cmp, 'value_text': sentence[m.start():end].strip()}
        if high:
            item['value_max'] = number(high); item['comparator'] = 'range'
        if plus:
            item['comparator'] = '±'
        if not any(o['value_text'] == item['value_text'] for o in out):  # 한 문장 안 같은 값 반복은 한 번만
            out.append(item)
    return out


def extract(path, doc_id):
    text = Path(path).read_text(encoding='utf-8')
    section, title, procedure = '머리말', '', None
    header = None
    out, warnings = [], []

    def add(kind, text_, quote, **extra):
        own = [section] + ([procedure] if procedure else [])
        item = {'id': f'{doc_id}-{len(out) + 1:03d}', 'doc_id': doc_id, 'section': section,
                'procedure': procedure, 'kind': kind, 'text': text_, 'quote': quote,
                'refs': refs_in(quote, own), 'status': 'pending'}
        item.update(extra)
        out.append(item)

    def classify(sentence):
        if COMPLETION.search(sentence):
            add('completion', sentence, sentence)
        elif PRECONDITION.search(sentence):
            add('precondition', sentence, sentence)
        if PROHIBITION.search(sentence):
            add('prohibition', sentence, sentence)
        for v in values(sentence):
            add('unit_value', sentence, sentence, **v)

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith('# '):
            header = None if not line.startswith('|') else header
            continue
        m = re.match(r'^##\s+(\S+)\s*(.*)$', line)
        if m and not line.startswith('###'):
            section, title, procedure, header = m.group(1), m.group(2), None, None
            continue
        m = re.match(r'^###\s+(SOP-[A-Z]+-\d+)\s*(.*)$', line)
        if m:
            procedure, header = m.group(1), None
            continue
        if line.startswith('###'):
            warnings.append(f'{section}: 절차 ID가 없는 소제목 「{line}」 — 절차로 보지 않음')
            continue
        if line.startswith('|'):
            cells = [c.strip() for c in line.strip('|').split('|')]
            if all(re.fullmatch(r':?-{2,}:?', c) for c in cells):
                continue
            if header is None:
                header = cells
                continue
            label = cells[0]
            for col, cell in enumerate(cells[1:], 1):
                for v in values(cell):
                    head = header[col] if col < len(header) else ''
                    add('unit_value', f'{label} · {head}: {cell}', line, **v)  # 칸 값만으로는 위치가 모호하므로 행 전체를 인용
            continue
        header = None
        m = re.match(r'^(\d+)\.\s+(.*)$', line)
        if m and procedure:
            order = int(m.group(1))
            body = m.group(2)
            add('step', body, body, order=order)
            for s in sentences(body):
                classify(s)
            continue
        if line.startswith('- '):
            line = line[2:]
        for s in sentences(line):
            classify(s)
    return {'doc_id': doc_id, 'source_file': Path(path).name,
            'source_sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            'extractor': '강사 참조 추출 함수(규칙 기반, LLM 없음)',
            'generated_at': dt.datetime.now().astimezone().isoformat(timespec='seconds'),
            'candidates': out, 'warnings': warnings}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('source'); p.add_argument('--doc', required=True); p.add_argument('--out', required=True)
    a = p.parse_args()
    result = extract(a.source, a.doc)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    kinds = {}
    for c in result['candidates']:
        kinds[c['kind']] = kinds.get(c['kind'], 0) + 1
    print(f"{a.doc}: 후보 {len(result['candidates'])}개 {kinds}, 경고 {len(result['warnings'])}개 → {a.out}")
