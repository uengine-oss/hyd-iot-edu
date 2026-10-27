"""강사 참조 추출 함수 2판 — 학생 배포 금지.

1판(extract_v1_hm8.py)은 HM-8에 맞춰 만든 규칙이다. 다른 문서(PM-02·제조사 발췌·HI-01)에 다시 실행해 드러난
누락·근거 없는 생성을 보고 고친 것이 이 2판이다. 무엇을 고쳤는지는 현업화_작업기록.md §4.
원문 Markdown의 절(##)·절차(###)·번호 단계·표·문장을 읽고 규칙으로 후보를 만든다. LLM·네트워크를 쓰지 않는다.
출력 계약은 학생 시작본의 `입력/출력_계약.md`와 같다.

사용: python extract_reference.py <원문.md> --doc HM-8 --out <후보.json> [--lang ko|en]
  --lang: 영한 병기 문서(EN:/KO: 줄, 「영문 / 한글」 표 칸)에서 인용 근거로 쓸 줄. 병기가 아닌 문서에는 영향 없음.
"""
from pathlib import Path
import argparse
import datetime as dt
import hashlib
import json
import re

NUM = r'(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)'
UNITS = ['operating hours', 'months', 'month', 'weeks', 'week', 'minutes', 'mm/s', 'l/min', 'L/min', 'N·m', '만 원', '운전시간',
         '시간', '개월', '호기', 'bar', 'psi', 'mm', 'µm', '℃', '°C', '°F', '%', 'h', '분', '초', '주', '원', '개', '명', '일', '건', '회']
UNIT = '(' + '|'.join(re.escape(u) for u in UNITS) + ')'
VALUE = re.compile(r'(?<![\w.\-~])(±\s*)?' + NUM + r'(?:\s*~\s*' + NUM + r')?\s*' + UNIT + r'(?![A-Za-z/])')
KO_AFTER = [('이상', '>='), ('이하', '<='), ('미만', '<'), ('초과', '>'), ('이내', '<='), ('아래', '<'), ('넘', '>'), ('안에', '<='),
            ('보다 적으면', '<'), ('에 이르면', '>='), ('에 닿으면', '>=')]
AFTER = re.compile(r'^\s*(?:를|을|이|가|로|으로|의)?\s*(' + '|'.join(re.escape(k) for k, _ in KO_AFTER) + ')')
EN_BEFORE = re.compile(r'(below|less than|under|more than|above|over|at least|reaches|within|up to|maximum is|not exceed)\s*$', re.I)
EN_CMP = {'below': '<', 'less than': '<', 'under': '<', 'more than': '>', 'above': '>', 'over': '>', 'at least': '>=',
          'reaches': '>=', 'within': '<=', 'up to': '<=', 'maximum is': '<=', 'not exceed': '<='}
NAME_AFTER = re.compile(r'^\s*(?:패키지|정기 점검|부품)')   # 「2,000 h 패키지」처럼 이름 속 수치

PROHIBITION = re.compile(r'않는다|않고|않는 것|말 것|금지|이내로 한다|안 된다|쓰지 않는다|\bNever\b|\bDo not\b|not valid|Never charge')
COMPLETION = re.compile(r'성공한 것이다|정상이다|정상이면|완료로 본다|돌아왔는지|내려왔는지|회복 판정|시운전 확인|시운전 뒤|미달로 적'
                        r'|미만이어야 한다|안에 있어야 한다|누유가 없는지|must be below|must be within|no leaks')
PRECONDITION = re.compile(r'때만|경우에만|전에는|뒤에만|기 전에|인지 확인한다|을 확인한다|를 확인한다|려면|여야 한다'
                          r'|(?:이|하|으|되|가|보이|오르|넘으|떨어지|졌으|었으|았으|미만이|이르)면[\s,]|^승인[:은]'
                          r'|\bBefore\b|\buntil\b|\bonly\b|\bIf\b|must read|confirm that the gauge')
REF = re.compile(r'(SOP-[A-Z]+-)(\d+)(?:~(\d+))?|(?<![\w-])([A-Z]{2}-\d+\.\d+)|\b(T-\d+\.\d+)\b|Section (\d+)|(?<![\d.])(\d+)절')


def number(text):
    value = float(text.replace(',', ''))
    return int(value) if value.is_integer() else value


def sentences(line):
    return [s for s in re.split(r'(?<=[^\d]\.)\s+', line.strip()) if s.strip()]


def bilingual(text):
    return bool(re.search(r'^\s*(?:\d+\.\s+)?EN:', text, re.M))


def pick(cell, lang):
    """「영문 / 한글」 칸에서 고른 언어 쪽. 나눌 수 없으면 칸 전체."""
    parts = [p.strip() for p in cell.split(' / ')]
    if len(parts) != 2:
        return cell
    return parts[0] if lang == 'en' else parts[1]


def values(sentence, skip_names=True):
    out = []
    for m in VALUE.finditer(sentence):
        plus, low, high, unit = m.groups()
        if skip_names and NAME_AFTER.match(sentence[m.end():]):
            continue
        tail = sentence[m.end():m.end() + 14]
        cmp, start, end = None, m.start(), m.end()
        a = AFTER.match(tail)
        if a:
            cmp = dict(KO_AFTER)[a.group(1)]
            end = m.end() + a.end()
        else:
            b = EN_BEFORE.search(sentence[max(0, m.start() - 16):m.start()])
            if b:
                cmp = EN_CMP[b.group(1).lower()]
                start = m.start() - (len(sentence[max(0, m.start() - 16):m.start()]) - b.start())
        item = {'value': number(low), 'unit': unit, 'comparator': cmp, 'value_text': sentence[start:end].strip()}
        if high:
            item['value_max'] = number(high); item['comparator'] = 'range'
        if plus:
            item['comparator'] = '±'
        if not any(o['value_text'] == item['value_text'] for o in out):
            out.append(item)
    return out


def extract(path, doc_id, lang='ko'):
    text = Path(path).read_text(encoding='utf-8')
    two = bilingual(text)
    titles = {}
    for line in text.splitlines():
        m = re.match(r'^###\s+(\S+)\s+(.*)$', line)
        if m:
            for t in m.group(2).split(' / '):
                titles[t.strip()] = m.group(1)
    section, procedure, header = '머리말', None, None
    pending_step = None
    out, warnings = [], []

    def refs_in(quote):
        own = {section, procedure}
        found = []
        for m in REF.finditer(quote):
            if m.group(1):
                start = int(m.group(2)); end = int(m.group(3) or start)
                ids = [f'{m.group(1)}{n}' for n in range(start, end + 1)]
            else:
                ids = [g for g in m.groups()[3:] if g]
            for i in ids:
                if i not in found and i not in own:
                    found.append(i)
        for title, pid in titles.items():   # 절차를 ID 없이 이름으로 가리킨 것
            if len(title) > 6 and title in quote and pid not in found and pid != procedure:
                found.append(pid)
        return found

    def add(kind, text_, quote, **extra):
        item = {'id': f'{doc_id}-{len(out) + 1:03d}', 'doc_id': doc_id, 'section': section,
                'procedure': procedure, 'kind': kind, 'text': text_, 'quote': quote,
                'refs': refs_in(quote), 'status': 'pending'}
        item.update(extra)
        out.append(item)

    def classify(sentence):
        if COMPLETION.search(sentence):
            add('completion', sentence, sentence)
        elif PRECONDITION.search(sentence):
            add('precondition', sentence, sentence)
        if PROHIBITION.search(sentence):
            add('prohibition', sentence, sentence)
        if section != '머리말':          # 머리말의 판·환산 수치는 기준값이 아니다
            for v in values(sentence):
                add('unit_value', sentence, sentence, **v)

    def step(order, body):
        add('step', body, body, order=order)
        for s in sentences(body):
            classify(s)

    for raw in text.splitlines():
        line = raw.strip()
        lead = re.match(r'^(EN|KO):\s*(.*)$', line)
        if pending_step and lead:       # 번호 단계 아래 들여 쓴 다른 언어 줄
            if (lead.group(1) == 'EN') == (lang == 'en'):
                step(pending_step, lead.group(2))
                pending_step = None
            continue
        if pending_step:
            warnings.append(f'{section} {procedure} {pending_step}단계: 고른 언어 줄을 찾지 못함')
            pending_step = None
        if not line or line.startswith('# '):
            header = None if not line.startswith('|') else header
            continue
        m = re.match(r'^##\s+(\S+)\s*(.*)$', line)
        if m and not line.startswith('###'):
            section, procedure, header = m.group(1), None, None
            continue
        m = re.match(r'^###\s+(\S+)\s*(.*)$', line)
        if m:
            procedure, header = m.group(1), None
            continue
        if line.startswith('|'):
            cells = [c.strip() for c in line.strip('|').split('|')]
            if all(re.fullmatch(r':?-{2,}:?', c) for c in cells):
                continue
            if header is None:
                header = [pick(c, lang) if two else c for c in cells]
                continue
            label = pick(cells[0], lang) if two else cells[0]
            for col, cell in enumerate(cells[1:], 1):
                part = pick(cell, lang) if two else cell
                for v in values(part):
                    head = header[col] if col < len(header) else ''
                    add('unit_value', f'{label} · {head}: {part}', line, **v)
            continue
        header = None
        m = re.match(r'^(\d+)\.\s+(.*)$', line)
        if m and procedure:
            body = m.group(2)
            lm = re.match(r'^(EN|KO):\s*(.*)$', body)
            if lm:
                if (lm.group(1) == 'EN') == (lang == 'en'):
                    step(int(m.group(1)), lm.group(2))
                else:
                    pending_step = int(m.group(1))
            else:
                step(int(m.group(1)), body)
            continue
        if lead:
            if (lead.group(1) == 'EN') != (lang == 'en'):
                continue
            line = lead.group(2)
        if line.startswith('- '):
            line = line[2:]
        for s in sentences(line):
            classify(s)
    return {'doc_id': doc_id, 'source_file': Path(path).name,
            'source_sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            'extractor': f'강사 참조 추출 함수 2판(규칙 기반, LLM 없음, lang={lang if two else "해당 없음"})',
            'generated_at': dt.datetime.now().astimezone().isoformat(timespec='seconds'),
            'candidates': out, 'warnings': warnings}


def save(result, dest):
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    Path(dest).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('source'); p.add_argument('--doc', required=True); p.add_argument('--out', required=True)
    p.add_argument('--lang', choices=['ko', 'en'], default='ko')
    a = p.parse_args()
    result = extract(a.source, a.doc, a.lang)
    save(result, a.out)
    kinds = {}
    for c in result['candidates']:
        kinds[c['kind']] = kinds.get(c['kind'], 0) + 1
    print(f"{a.doc}: 후보 {len(result['candidates'])}개 {kinds}, 경고 {len(result['warnings'])}개 → {a.out}")
