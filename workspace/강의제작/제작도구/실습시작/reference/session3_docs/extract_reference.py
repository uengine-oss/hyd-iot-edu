"""강사 참조 — 문서 추출의 두 번째 구현(규칙 기반, 모델을 부르지 않는다). 학생 폴더 · ZIP에 넣지 않는다.

문서 지식 묶음 추출 랩(통합 04-2 · 실전 03-4)의 학생 경로는 수업 모델의 답에서 후보를 만든다. 이 파일은 그와 다른 길 — 원문의 절 · 절차 ·
번호 단계 · 표 · 문장을 규칙으로 읽어 같은 계약(입출력_계약.md 「후보 파일」 · 「후보 하나」)의 후보를 만든다 — 이라서,
기대 항목(expected_items.py)과의 겹침으로 누락 · 근거 없는 생성을 세는 데와, 갈래별 강사 검토(branches.py)가 결정을 걸 후보 판을 만드는 데 쓴다.
옛 2판(git 이력 — 같은 이름)의 문장 분류 규칙을 옮기고 다음을 더했다: 문서 목록의 판 · SHA 대조, 선언한 글자 방식(CP949 규정 발췌),
txt 문서의 절(「제N조」 · 「HM-9.x」), 스캔본의 쪽(꼬리 「- 9-x -」), 인용의 줄 범위와 찾은 방법, 원문 여러 곳에 맞는 인용은 앞 줄을 붙여 한 곳으로.

사용: python extract_reference.py <랩 폴더> --out <폴더>     (자료/문서_목록.csv의 파일마다 후보 파일 하나)
"""
from __future__ import annotations

from pathlib import Path
import argparse
import csv
import hashlib
import io
import json
import re

EXTRACTOR = '문서 구조 · 문장 규칙으로 후보를 만든 실행(모델 응답 기록 없음)'
GENERATED_AT = '2026-10-28T09:00:00+09:00'      # 고정 — 같은 입력이면 같은 바이트(강사 판 · 다음 실습 입력)
ENCODINGS = ('utf-8', 'cp949')                  # 읽는 순서 — UTF-8로 풀리지 않으면 CP949

NUM = r'(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)'
NUM_SCAN = r'(\d(?: ?\d)*(?:\.\d+)?)'          # 스캔본 — 문자 인식이 숫자 사이에 띄어쓰기를 넣는다(「6 0 %」)
UNITS = ['operating hours', 'months', 'month', 'weeks', 'week', 'minutes', 'mm/s', 'l/min', 'L/min', 'N·m', '만 원', '운전시간',
         '시간', '개월', '호기', 'bar', 'psi', 'MPa', 'mm', 'µm', '℃', '°C', '°F', '%', 'h', '분', '초', '주', '원', '개', '명', '일', '건', '회']
UNIT = '(' + '|'.join(re.escape(u) for u in UNITS) + ')'
VALUE = re.compile(r'(?<![\w.\-~])(±\s*)?' + NUM + r'(?:\s*~\s*' + NUM + r')?\s*' + UNIT + r'(?![A-Za-z/])')
VALUE_SCAN = re.compile(r'(?<![\w.\-~])(±\s*)?' + NUM_SCAN + r'(?:\s*~\s*' + NUM_SCAN + r')?\s*' + UNIT + r'(?![A-Za-z/])')
DATE = re.compile(r'\d+월\s*$')
KO_AFTER = [('이상', '>='), ('이하', '<='), ('미만', '<'), ('초과', '>'), ('이내', '<='), ('아래', '<'), ('넘', '>'), ('안에', '<='),
            ('보다 적으면', '<'), ('에 이르면', '>='), ('에 닿으면', '>=')]
AFTER = re.compile(r'^\s*(?:를|을|이|가|로|으로|의)?\s*(' + '|'.join(re.escape(k) for k, _ in KO_AFTER) + ')')
EN_BEFORE = re.compile(r'(below|less than|under|more than|above|over|at least|reaches|within|up to|no more than|maximum is|not exceed)\s*$', re.I)
EN_CMP = {'below': '<', 'less than': '<', 'under': '<', 'more than': '>', 'above': '>', 'over': '>', 'at least': '>=',
          'reaches': '>=', 'within': '<=', 'up to': '<=', 'no more than': '<=', 'maximum is': '<=', 'not exceed': '<='}
NAME_AFTER = re.compile(r'^\s*(?:패키지|정기 점검|부품)')   # 「2,000 h 패키지」처럼 이름 속 수치

PROHIBITION = re.compile(r'않는다|않고|않는 것|말 것|금지|이내로 한다|안 된다|쓰지 않는다|\bNever\b|\bDo not\b|not valid|must not')
COMPLETION = re.compile(r'성공한 것이다|정상이다|정상이면|완료로 본다|돌아왔는지|내려왔는지|회복 판정|시운전 확인|시운전 뒤|미달로 적'
                        r'|미만이어야 한다|안에 있어야 한다|누유가 없는지|must be below|must be within|no leaks|작으면 안 된다'
                        r'|must not be less than|must not be lower than')
LOWER_BOUND = re.compile(r'must not be (?:less|lower) than|작으면 안 된다')   # 끝난 뒤 값의 하한 — 완료 기준의 말
PRECONDITION = re.compile(r'때만|경우에만|전에는|뒤에만|기 전에|인지 확인한다|을 확인한다|를 확인한다|려면|여야 한다'
                          r'|(?:이|하|으|되|가|보이|오르|넘으|떨어지|졌으|었으|았으|미만이|이르)면[\s,]|^승인[:은]|승인은|확인한 뒤|따른다'
                          r'|\bBefore\b|\buntil\b|\bonly\b|\bIf\b|must read|confirm that the gauge')
REF = re.compile(r'(SOP-[A-Z]+-)(\d+)(?:~(\d+))?|(?<![\w-])([A-Z]{2}-\d+(?:\.\d+)?)|\b(T-\d+\.\d+)\b|Section (\d+)|(?<![\d.])(\d+)절')
ARTICLE = re.compile(r'^(제\d+조)\(')                 # 규정 발췌의 조
SCAN_SECTION = re.compile(r'^(HM-9\.\d+)\s+\S')       # 스캔본의 절 머리(목차 줄은 점선으로 거른다)
FOOTER = re.compile(r'^-\s*(\S+)\s*-$')
CIRCLED = '①②③④⑤⑥⑦⑧⑨'


def squash(text):
    return ''.join(c for c in text.lower() if c.isalnum())


def number(text):
    value = float(text.replace(',', '').replace(' ', ''))
    return int(value) if value.is_integer() else value


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


def read_register(folder):
    lines = [x for x in (Path(folder)/'자료/문서_목록.csv').read_text(encoding='utf-8').splitlines() if not x.startswith('#')]
    return [r for r in csv.DictReader(io.StringIO('\n'.join(lines))) if r['파일']]


def decode(raw):
    for enc in ENCODINGS:
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    raise ValueError('UTF-8 · CP949 어느 쪽으로도 읽히지 않습니다')


def values(sentence, scanned=False):
    out = []
    for m in (VALUE_SCAN if scanned else VALUE).finditer(sentence):
        plus, low, high, unit = m.groups()
        if NAME_AFTER.match(sentence[m.end():]) or (unit == '일' and DATE.search(sentence[:m.start()])):
            continue
        tail = sentence[m.end():m.end() + 14]
        cmp, start, end = None, m.start(), m.end()
        a = AFTER.match(tail)
        if a:
            cmp = dict(KO_AFTER)[a.group(1)]
            end = m.end() + a.end()
        else:
            head = sentence[max(0, m.start() - 16):m.start()]
            b = EN_BEFORE.search(head)
            if b:
                cmp = EN_CMP[b.group(1).lower()]
                start = m.start() - (len(head) - b.start())
        item = {'value': number(low), 'unit': unit, 'comparator': cmp, 'value_text': sentence[start:end].strip()}
        if high:
            item['value_max'] = number(high)
            item['comparator'] = 'range'
        if plus:
            item['comparator'] = '±'
        if not any(o['value_text'] == item['value_text'] for o in out):
            out.append(item)
    return out


class Doc:
    """한 문서의 줄 · 절 · 절차 · 쪽."""

    def __init__(self, text, scanned):
        self.text = text
        self.lines = text.splitlines()
        self.scanned = scanned
        self.page = {}
        if scanned:
            pending = []
            for n, line in enumerate(self.lines, 1):
                m = FOOTER.match(line.strip())
                pending.append(n)
                if m:
                    for k in pending:
                        self.page[k] = m.group(1)
                    pending = []

    def locate(self, start, end, quote):
        """(quote, line_start, line_end, quote_match) — 원문 한 곳에만 맞을 때까지 앞 줄을 붙인다. 붙일 줄이 없으면 None."""
        for _ in range(4):
            segment = '\n'.join(self.lines[start - 1:end])
            if quote not in segment:
                return None
            exact = self.text.count(quote)
            near = squash(self.text).count(squash(quote))
            if exact == 1 and near <= 1:
                return quote, start, end, 'exact'
            if start == 1:
                return None
            start -= 1
            while start > 1 and not self.lines[start - 1].strip():
                start -= 1
            quote = '\n'.join(self.lines[start - 1:end])      # 앞 줄부터 그 줄 끝까지 — 원문 그대로 이어진 글
        return None


def extract(folder, row, lang='en'):
    """문서 목록 한 행의 후보 파일(dict)."""
    path = Path(folder)/'자료'/row['파일']
    raw = path.read_bytes()
    text, encoding = decode(raw)
    scanned = '스캔본' in row['상태']
    doc = Doc(text, scanned)
    bilingual = bool(re.search(r'^\s*(?:\d+\.\s+)?EN:', text, re.M))
    titles = {}
    for line in doc.lines:
        m = re.match(r'^###\s+(\S+)\s+(.*)$', line)
        if m:
            for t in m.group(2).split(' / '):
                titles[t.strip()] = m.group(1)
    state = {'section': '머리말', 'procedure': None}
    out, unlocated, warnings = [], [], []

    def refs_in(quote):
        own = {state['section'], state['procedure']}
        found = []
        for m in REF.finditer(quote):
            if m.group(1):
                a, b = int(m.group(2)), int(m.group(3) or m.group(2))
                ids = [f'{m.group(1)}{n}' for n in range(a, b + 1)]
            else:
                ids = [g for g in m.groups()[3:] if g]
            for i in ids:
                if i not in found and i not in own:
                    found.append(i)
        for title, pid in titles.items():
            if len(title) > 6 and title in quote and pid not in found and pid != state['procedure']:
                found.append(pid)
        return found

    def add(kind, body, quote, n, **extra):
        if any(o['kind'] == kind and o['text'] == body and o.get('value_text') == extra.get('value_text') and n in range(o['line_start'], o['line_end'] + 1)
               for o in out):
            return            # 같은 줄 · 같은 종류 · 같은 내용을 한 번 더 만들지 않는다(같은 인용 중복)
        located = doc.locate(n, n, quote)
        item = {'id': f'{row["문서 식별자"]}-{len(out) + len(unlocated) + 1:03d}', 'section': state['section'], 'procedure': state['procedure'],
                'kind': kind, 'text': body}
        if located is None:
            unlocated.append(item | {'quote': quote, 'note': '원문 여러 곳에 맞아 한 곳으로 정하지 못함', 'status': 'pending'} | extra)
            return
        q, ls, le, how = located
        item |= {'quote': q, 'quote_match': how, 'line_start': ls, 'line_end': le}
        if scanned:
            item['page'] = doc.page.get(le)
        if bilingual:
            item['lang'] = lang
        item |= {'refs': refs_in(q), 'status': 'pending'} | extra
        out.append(item)

    def classify(sentence, n):
        if COMPLETION.search(sentence):
            add('completion', sentence, sentence, n)
        elif PRECONDITION.search(sentence):
            add('precondition', sentence, sentence, n)
        if PROHIBITION.search(LOWER_BOUND.sub('', sentence)):   # 「must not be less than」 · 「작으면 안 된다」는 완료 기준의 하한이지 금지가 아니다
            add('prohibition', sentence, sentence, n)
        if state['section'] != '머리말':
            for v in values(sentence, scanned):
                add('unit_value', sentence, sentence, n, **v)

    def step(order, body, n):
        add('step', body, body, n, order=order)
        for s in sentences(body):
            classify(s, n)

    header, pending = None, None
    for n, raw_line in enumerate(doc.lines, 1):
        line = raw_line.strip()
        lead = re.match(r'^(EN|KO):\s*(.*)$', line)
        if pending and lead:
            if (lead.group(1) == 'EN') == (lang == 'en'):
                body = lead.group(2)
                add('step', body, body, n, order=pending)
                for s in sentences(body):
                    classify(s, n)
                pending = None
            continue
        if pending:
            warnings.append(f'{state["section"]} {state["procedure"]} {pending}단계: 고른 언어 줄을 찾지 못함')
            pending = None
        if not line or line.startswith('# ') or FOOTER.match(line) or line.startswith('=== 스캔'):
            header = None
            continue
        m = re.match(r'^##\s+(\S+)', line)
        if m and not line.startswith('###'):
            state.update(section=m.group(1), procedure=None)
            header = None
            continue
        m = re.match(r'^###\s+(\S+)', line)
        if m:
            state['procedure'] = m.group(1)
            header = None
            continue
        m = ARTICLE.match(line)
        if m or line == '부칙':
            state.update(section=m.group(1) if m else '부칙', procedure=None)
            continue
        if scanned:
            m = SCAN_SECTION.match(line)
            if m and '....' not in line:
                state.update(section=m.group(1), procedure=None)
                continue
            if '....' in line or line.startswith(('종합 정비 매뉴얼', '문자 인식', '원본:', '목차', '가상 사례', '제9장')):
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
                part = cell
                if bilingual and ' / ' in cell:
                    en, ko = [x.strip() for x in cell.split(' / ', 1)]
                    part = en if lang == 'en' else ko
                for v in values(part, scanned):
                    head = header[col] if col < len(header) else ''
                    add('unit_value', f'{label} · {head}: {part}', line, n, **v)
            continue
        header = None
        m = re.match(r'^(\d+)\.\s+(.*)$', line)
        if m and state['procedure']:
            body = m.group(2)
            lm = re.match(r'^(EN|KO):\s*(.*)$', body)
            if lm:
                if (lm.group(1) == 'EN') == (lang == 'en'):
                    step(int(m.group(1)), lm.group(2), n)
                else:
                    pending = int(m.group(1))
            else:
                step(int(m.group(1)), body, n)
            continue
        if lead:
            if (lead.group(1) == 'EN') != (lang == 'en'):
                continue
            line = lead.group(2)
        if line.startswith('- '):
            line = line[2:]
        if line[:1] in CIRCLED:
            line = line[1:].strip()
        if line.startswith('>') or line.startswith('1.1판:') or '판독 불가' in line:
            continue          # 개정 초안의 검토 의견 · 지금 문장 줄, 판독 불가 줄은 후보로 만들지 않는다
        for s in sentences(line):
            classify(s, n)
    return {'doc_id': row['문서 식별자'], 'rev': row['판'], 'doc_status': row['상태'], 'source_file': row['파일'],
            'source_sha256': hashlib.sha256(raw).hexdigest(), 'encoding': encoding,
            'extractor': EXTRACTOR + (f' · 인용 언어 {lang}' if bilingual else ''), 'generated_at': GENERATED_AT,
            'model_run': [], 'candidates': out, 'unlocated': unlocated, 'warnings': warnings}


def file_stem(row):
    return f'{row["문서 식별자"]}_{row["판"]}' if row['판'] else row['문서 식별자']


def extract_all(folder):
    """{후보 파일 이름: 후보 파일 dict} — 문서 목록의 파일 있는 행마다."""
    return {f'{file_stem(r)}.json': extract(folder, r) for r in read_register(folder)}


def dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + '\n'


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('lab')
    p.add_argument('--out', required=True)
    a = p.parse_args()
    dest = Path(a.out)
    dest.mkdir(parents=True, exist_ok=True)
    for name, data in extract_all(a.lab).items():
        (dest/name).write_text(dump(data), encoding='utf-8', newline='\n')
        kinds = {}
        for c in data['candidates']:
            kinds[c['kind']] = kinds.get(c['kind'], 0) + 1
        print(f'{name}: 후보 {len(data["candidates"])}개 {kinds}, 찾지 못한 인용 {len(data["unlocated"])}개')
