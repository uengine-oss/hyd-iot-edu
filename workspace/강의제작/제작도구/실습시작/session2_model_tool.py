"""스키마와 지식 그래프를 만드는 제공 코드 — 원자료와 `결과/`의 빈 틀(내가 정한 표 · 함수)을 읽어 `결과/schema.json` · `결과/graph.json`을 쓴다.

스키마는 내가 정한 표 세 장이다: 클래스.csv(클래스 · 의미 · 식별자 짓는 법), 속성.csv(클래스마다 속성 · 원자료의 어느 칸 · 자료형 · 필수 · 단위), 관계.csv(관계 이름 · 읽는 말 · 시작 · 종료 클래스 · 카디널리티 · 적어도 하나).
이 파일은 누가 해도 같은 일만 한다: 파일 읽기, 칸 공백 정리, 숫자 · 날짜 읽기, 같은 모델의 설비끼리 다르게 적힌 구성 요소 이름 하나로 맞추기, 단위 환산,
교체부품 칸의 품번 찾기(괄호 속 품번 · 사내 품번 · 품번 교차표에 하나로 적힌 표기), 원자료 행을 내 스키마 표에 대어 보기, 계약 꼴로 쓰기, 모델에 물어보기.
무엇을 클래스 · 속성 · 관계로 두고 어떤 자료형 · 필수 · 방향으로 둘지, 무엇을 하나로 보고 무엇을 따로 둘지는 `결과/`의 빈 틀이 정한다. 빈 틀에 없는 것은 짐작하지 않고 파일 · 행과 함께 멈춘다.
직접 실행하지 않는다 — `python show_result.py`가 단계마다 부른다.
"""
from pathlib import Path
import csv
import importlib.util
import io
import json
import re

HERE = Path(__file__).resolve().parent
DATA = HERE / '자료'
OUT = HERE / '결과'
KINDS = ['설비', '구성 요소', '센서', '물리량', '부품']
OPTIONAL_KINDS = ['실물']      # 자리(구성 요소)와 일련번호가 붙은 실물을 나눌 때만 결과/클래스.csv에 적는다
LABEL = {'설비': 'Asset', '구성 요소': 'Component', '센서': 'Sensor', '물리량': 'Quantity', '부품': 'Part', '실물': 'Unit'}
KIND_OF = {v: k for k, v in LABEL.items()}
# 클래스마다 인스턴스가 나오는 원자료 표(한 행이 인스턴스 하나). 물리량은 센서 행을 내 규칙(quantity_rules.py)으로 묶어 만든다. 실물은 일련번호가 적힌 구성 요소 행이다.
TABLE = {'설비': '설비_대장.csv', '구성 요소': '구성요소_목록.csv', '센서': '센서_목록.csv', '부품': '예비품_목록.csv', '실물': '구성요소_목록.csv'}
# 원자료 칸 말고 제공 코드가 만들어 주는 칸 — 속성.csv의 원자료_칸에 쓸 수 있다
DERIVED = {'구성 요소': {'다른이름': '같은 모델의 설비끼리 이름을 맞추기 전에 원자료에 적혀 있던 이름(목록)'},
           '부품': {'다른표기': '품번 교차표에서 이 사내 품번을 가리키는 다른 표기(목록)'},
           '물리량': {'물리량': '내 규칙이 묶음에 붙인 이름', '기준단위': '그 묶음의 센서 행이 가장 많이 쓴 단위'}}
LIST_COLUMNS = ('다른이름', '다른표기')
# 이 자료로 이을 수 있는 클래스의 짝. 화살표를 어느 쪽에서 긋는지(시작 · 종료 클래스)는 관계.csv가 정하고, 질문은 그은 방향 그대로든 거꾸로든 따라가 찾는다.
LINKS = {'설비-구성 요소': ('설비', '구성 요소'), '구성 요소-센서': ('구성 요소', '센서'), '센서-물리량': ('센서', '물리량'),
         '구성 요소-부품': ('구성 요소', '부품'), '구성 요소-실물': ('구성 요소', '실물')}
OPTIONAL_LINKS = ('구성 요소-실물',)   # 구성 요소 자리와 그 실물을 나눌 때만 적는 관계
CARDINALITY = ('1:1', '1:N', 'N:1', 'N:M')   # 시작 쪽 수:종료 쪽 수 — 「1」 쪽은 많아야 하나
LEAST = {'없음': (), '시작마다': ('시작',), '종료마다': ('종료',), '양쪽': ('시작', '종료')}   # 적어도 하나: 어느 쪽 인스턴스마다 이 관계가 하나는 있어야 하는가
TYPES = {'글자': 'string', '수': 'number', '날짜': 'date', '목록': 'list'}
YES_NO = {'예': True, '아니오': False}
UNIT_MODES = ('기준 단위', '적힌 그대로')   # 센서의 수 속성: 그 센서가 재는 물리량의 기준 단위로 바꿔 담을지, 원자료에 적힌 단위 그대로 담을지
# 결정 지점(결과/정한_것.csv에 지점 이름이 미리 있는 줄)과 그것을 쓰는 단계. 그 단계를 실행할 때 고른_것 · 근거가 비었거나 미결이면 그 줄을 짚고 멈춘다.
DECISIONS = {'이름': ['구성 요소 자리와 그 실물'], '센서': ['같은 물리량의 범위'], '부품': ['구성 요소 자리와 그 실물', '같은 물리량의 범위']}
# 단위 환산(일반 지식): (원래 단위, 기준 단위) → 곱할 값
FACTOR = {('W', 'kW'): 0.001, ('kW', 'W'): 1000, ('kPa', 'bar'): 0.01, ('bar', 'kPa'): 100, ('MPa', 'bar'): 10, ('bar', 'MPa'): 0.1,
          ('l/min', 'L/min'): 1, ('L/min', 'l/min'): 1, ('lpm', 'L/min'): 1, ('°C', '℃'): 1, ('℃', '°C'): 1}
UNKNOWN = '미확인'


class Stop(Exception):
    """빈 틀에 없는 것 · 계약 어긋남. 글에 파일 · 행이 있다."""


class Blank(Stop):
    """빈 틀이 아직 채워지지 않음."""


def josa(word, pair):
    """받침에 맞는 조사. pair = '이/가' · '을/를' · '은/는' · '과/와' — 앞이 받침 있는 말 뒤에 붙는 꼴."""
    with_final, without = pair.split('/')
    last = str(word).rstrip(')」 ')[-1:]
    if not ('가' <= last <= '힣'):
        return f'{word}{with_final}({without})'
    return f'{word}{with_final if (ord(last) - 0xAC00) % 28 else without}'


def text_of(path):
    """UTF-8로 저장된 글만 읽는다. 다른 글자표로 저장됐거나 한글이 물음표로 깨진 채 저장된 파일은 조용히 바꿔 읽지 않고 그 줄을 짚고 멈춘다."""
    data = Path(path).read_bytes()
    try:
        text = data.decode('utf-8-sig')
    except UnicodeDecodeError:
        bad = next(n for n, x in enumerate(data.split(b'\n'), 1) if not _utf8(x))
        raise Stop(f'{rel(path)}:{bad}: UTF-8로 저장되지 않은 글자가 있습니다 — Codex에게 「이 파일을 UTF-8로 다시 저장해 줘」라고 부탁합니다(한글이 다른 글자표로 저장됐습니다).')
    mine = OUT in Path(path).resolve().parents
    for n, x in enumerate(text.splitlines(), 1):
        if '\ufffd' in x or (mine and re.search(r'\?{2,}', x)):
            raise Stop(f'{rel(path)}:{n}: 한글이 「?」로 깨진 채 저장됐습니다 — Codex에게 「이 줄을 UTF-8로 다시 써 줘」라고 부탁합니다.')
    return text


def _utf8(data):
    try:
        data.decode('utf-8')
        return True
    except UnicodeDecodeError:
        return False


# ───────────── 읽기 ─────────────
def table(path):
    """CSV → [(편집기 줄 번호, dict)]. 첫머리 # 줄은 건너뛰고(줄 번호는 그대로 센다) 칸 앞뒤 공백을 정리한다."""
    lines = text_of(path).splitlines()
    head = next((i for i, x in enumerate(lines) if x.strip() and not x.lstrip().startswith('#')), None)
    if head is None:
        raise Stop(f'{rel(path)}: 열 이름 줄이 없습니다.')
    reader = csv.reader(io.StringIO('\n'.join(lines[head:])))
    cols = [c.strip() for c in next(reader)]
    out = []
    for offset, cells in enumerate(reader, head + 2):
        if not any(c.strip() for c in cells):
            continue
        # 칸 수가 열 이름과 다른 줄은 받지 않는다 — 넘친 칸을 끝 칸에 이어 붙이면, 앞 칸에 쉼표가 든 줄은 값이 한 칸씩 밀린 채 조용히 지나간다
        if len(cells) > len(cols):
            raise Stop(f'{rel(path)}:{offset}: 칸 수({len(cells)})가 열 이름({len(cols)}칸)보다 많습니다 — 값 안에 쉼표가 있으면 그 값을 큰따옴표로 감싸거나 쉼표를 「 · 」로 바꿉니다.')
        if len(cells) < len(cols):
            raise Stop(f'{rel(path)}:{offset}: 칸 수({len(cells)})가 열 이름({len(cols)}칸)보다 적습니다 — 빈 칸도 쉼표로 자리를 둡니다.')
        out.append((offset, {c: (cells[i].strip() if i < len(cells) else '') for i, c in enumerate(cols)}))
    return out


def need(path, columns):
    rows = table(path)
    have = list(rows[0][1]) if rows else [c.strip() for c in next(csv.reader(io.StringIO(
        next(x for x in text_of(path).splitlines() if x.strip() and not x.lstrip().startswith('#')))))]
    miss = [c for c in columns if c not in have]
    if miss:
        raise Stop(f'{rel(path)}: 열 {", ".join(miss)}이 없습니다(받은 빈 틀의 열 이름을 바꾸지 않습니다).')
    return rows


def rel(path):
    try:
        return Path(path).resolve().relative_to(HERE).as_posix()
    except ValueError:
        return Path(path).name


def number(text):
    m = re.match(r'\s*(-?\d+(?:\.\d+)?)', text or '')
    return float(m.group(1)) if m else None


def rules(name):
    """결과/<name>.py(내가 쓴 판단 함수)를 불러온다."""
    path = OUT / f'{name}.py'
    text_of(path)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except SyntaxError as e:
        raise Stop(f'{rel(path)}:{e.lineno}: 파이썬 문법에 맞지 않는 줄입니다 — {e.msg}. 그 줄을 Codex에게 보여 주고 까닭을 묻습니다.')
    return mod


def ask(mod, fn, want, *args):
    """판단 함수 하나를 부르고 돌려준 값의 꼴을 본다(want = bool · str). 꼴이 다르면 함수 이름과 받은 값으로 멈춘다."""
    try:
        value = getattr(mod, fn)(*args)
    except NotImplementedError:
        raise Blank(f'결과/{mod.__name__}.py의 {fn} 함수 — 같은 물리량을 가르는 규칙을 채운 뒤 다시 실행합니다.')
    if want is bool and value not in (True, False):
        raise Stop(f'결과/{mod.__name__}.py {fn}: True 또는 False를 돌려줘야 합니다(돌려준 값 {value!r}).')
    if want is str and not (isinstance(value, str) and value.strip()):
        raise Stop(f'결과/{mod.__name__}.py {fn}: 빈칸이 아닌 글자를 돌려줘야 합니다(돌려준 값 {value!r}).')
    return value.strip() if want is str else value


def grouped(items, same):
    """items를 판단 함수 same(a, b)가 True인 짝끼리 이어 묶는다(이어진 것은 모두 한 묶음). 묶음 = 원래 차례의 목록."""
    root = list(range(len(items)))

    def top(i):
        while root[i] != i:
            root[i] = root[root[i]]
            i = root[i]
        return i
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if top(i) != top(j) and same(items[i], items[j]):
                root[top(j)] = top(i)
    out = {}
    for i, x in enumerate(items):
        out.setdefault(top(i), []).append(x)
    return list(out.values())


def resolve_cell(cell, parts, cross):
    """교체부품 칸 → (사내 품번, 찾은 법)(일반 로직): 괄호 속 품번 · 사내 품번 · 품번 교차표에 하나로 적힌 표기. 못 풀면 (None, '')."""
    m = re.search(r'\((P-[A-Z0-9-]+)\)', cell)
    if m and m.group(1) in parts:
        return m.group(1), '괄호 속 품번'
    if cell in parts:
        return cell, '사내 품번'
    hits = sorted({c['사내품번'] for c in cross if c['다른표기'] == cell})
    if cell and len(hits) == 1 and hits[0] in parts:
        return hits[0], f'품번 교차표({next(c["표기종류"] for c in cross if c["다른표기"] == cell)})'
    return None, ''


# ───────────── 빈 틀(내 스키마 표 세 장과 결정) ─────────────
def decided(stage):
    """이 단계가 쓰는 결정이 결과/정한_것.csv에 정해졌는가 — 고른 것이 맞는지는 보지 않는다(그것은 학생의 판단). 모델 파일을 쓰는 단계(부품)는 두 결정을 다 본다."""
    need_ = DECISIONS[stage]
    rows = {r['지점']: (line, r) for line, r in need(OUT / '정한_것.csv', ['지점', '고른_것', '근거', '바뀌는_답'])}
    for point in need_:
        if point not in rows:
            raise Stop(f'결과/정한_것.csv: 지점 「{point}」 줄이 없습니다 — 받은 빈 틀의 지점 줄을 지우지 않습니다.')
        line, r = rows[point]
        if not r['고른_것'] or r['고른_것'] == '미결' or not r['근거']:
            raise Stop(f'결과/정한_것.csv:{line}: 「{point}」의 고른_것 · 근거가 아직 비어 있습니다(미결 포함). 이 단계는 이 결정대로 모델을 만듭니다 — '
                       '선택지와 그 결과를 따져 보고 내가 고른 것과 근거를 적은 뒤 다시 실행합니다.')
        if not re.search(r'[^\s:]+:\d+', r['근거']):
            raise Stop(f'결과/정한_것.csv:{line}: 「{point}」의 근거에 파일:줄이 없습니다 — 그렇게 고른 내 이유 뒤에, 정할 때 열어 본 원문 줄을 파일:줄 꼴로 함께 적습니다.')


def header(name):
    """원자료 표의 열 이름."""
    text = text_of(DATA / name)
    return [c.strip() for c in next(csv.reader(io.StringIO(text.splitlines()[0])))]


def columns(kind):
    """그 클래스의 식별자와 속성에 쓸 수 있는 칸: 그 클래스의 원자료 표 칸과 제공 코드가 만들어 주는 칸."""
    return (header(TABLE[kind]) if kind in TABLE else []) + list(DERIVED.get(kind, {}))


def read_classes():
    """클래스.csv → {클래스: {'id': 식별자 틀, '의미': 한 문장, '줄': 편집기 줄}}."""
    out = {}
    for line, r in need(OUT / '클래스.csv', ['클래스', '의미', 'ID_만드는_법', '근거']):
        k = r['클래스']
        if k not in KINDS + OPTIONAL_KINDS:
            raise Stop(f'결과/클래스.csv:{line}: 클래스 「{k}」 — 이 자료로 만들 수 있는 클래스는 {" · ".join(KINDS + OPTIONAL_KINDS)}입니다(실물은 구성 요소 자리와 그 실물을 나눌 때만).')
        if k in out:
            raise Stop(f'결과/클래스.csv:{out[k]["줄"]} · {line}: 클래스 「{k}」의 줄이 둘입니다 — 클래스마다 한 줄만 씁니다.')
        if not r['의미']:
            raise Stop(f'결과/클래스.csv:{line}: {k}의 의미 칸이 비었습니다 — 무엇을 이 클래스의 인스턴스 하나로 세는지 한 문장으로 적습니다.')
        can = [c for c in columns(k) if c not in LIST_COLUMNS and c != '기준단위']
        used = re.findall(r'\{([^}]*)\}', r['ID_만드는_법'])
        if not used or [x for x in used if x not in can]:
            raise Stop(f'결과/클래스.csv:{line}: {k}의 ID_만드는_법 「{r["ID_만드는_법"]}」 — {{칸 이름}} 꼴로 쓰고, 쓸 수 있는 칸은 {", ".join(can)}입니다.')
        out[k] = {'id': r['ID_만드는_법'], '의미': r['의미'], '줄': line}
    miss = [k for k in KINDS if k not in out]
    if miss:
        raise Stop('결과/클래스.csv: 아직 적지 않은 클래스 — ' + ', '.join(miss))
    return out


def read_properties(classes):
    """속성.csv → {클래스: [{'이름', '칸', '자료형', '필수', '단위', '줄'}]}. 식별자 id는 클래스.csv가 정하므로 여기에 적지 않는다."""
    out = {k: [] for k in classes}
    for line, r in need(OUT / '속성.csv', ['클래스', '속성', '원자료_칸', '자료형', '필수', '단위', '근거']):
        k, where = r['클래스'], f'결과/속성.csv:{line}'
        if k not in classes:
            raise Stop(f'{where}: 클래스 「{k}」 — 결과/클래스.csv에 적은 클래스({" · ".join(classes)}) 가운데 하나입니다.')
        if not re.fullmatch(r'[a-z][a-z0-9_]*', r['속성']) or r['속성'] == 'id':
            raise Stop(f'{where}: 속성 「{r["속성"]}」 — 속성 이름은 영어 소문자 · 숫자 · 밑줄로 씁니다(id는 식별자 자리라 쓰지 않습니다).')
        if any(p['이름'] == r['속성'] for p in out[k]):
            raise Stop(f'{where}: {k}의 속성 「{r["속성"]}」이 두 줄입니다 — 한 클래스에서 속성 이름은 하나씩입니다.')
        if r['원자료_칸'] not in columns(k):
            raise Stop(f'{where}: 원자료_칸 「{r["원자료_칸"]}」 — {k}에 쓸 수 있는 칸은 {", ".join(columns(k))}입니다.')
        if r['자료형'] not in TYPES:
            raise Stop(f'{where}: 자료형 「{r["자료형"]}」 — {" · ".join(TYPES)} 가운데 하나입니다.')
        if (r['원자료_칸'] in LIST_COLUMNS) != (r['자료형'] == '목록'):
            raise Stop(f'{where}: 자료형 「목록」은 값이 여럿인 칸({" · ".join(LIST_COLUMNS)})에만 쓰고, 그 칸은 「목록」으로 적습니다.')
        if r['필수'] not in YES_NO:
            raise Stop(f'{where}: 필수 「{r["필수"]}」 — 예 · 아니오 가운데 하나입니다.')
        scaled = k == '센서' and r['자료형'] == '수'
        if scaled and r['단위'] not in UNIT_MODES:
            raise Stop(f'{where}: 단위 「{r["단위"]}」 — 센서의 수 속성은 {" · ".join(UNIT_MODES)} 가운데 하나를 적습니다(기준 단위 = 그 센서가 재는 물리량의 기준 단위로 바꿔 담음).')
        if not scaled and r['단위']:
            raise Stop(f'{where}: 단위 칸은 센서의 수 속성에만 적습니다(이 줄은 비워 둡니다).')
        out[k].append({'이름': r['속성'], '칸': r['원자료_칸'], '자료형': r['자료형'], '필수': YES_NO[r['필수']], '단위': r['단위'], '줄': line})
    modes = {p['단위']: p['줄'] for p in out.get('센서', []) if p['단위']}
    if len(modes) > 1:
        raise Stop('결과/속성.csv:' + ' · '.join(str(v) for v in modes.values()) + ': 센서의 수 속성에 「기준 단위」와 「적힌 그대로」가 섞였습니다 — 한 센서의 정상값과 한계는 같은 단위로 담습니다.')
    return out


def read_relations(classes):
    """관계.csv → {연결: (관계 이름, 시작 클래스, 종료 클래스, 카디널리티, 줄, 적어도 하나인 쪽들, 읽는 말)}. 연결 = 두 클래스의 짝(LINKS의 이름)."""
    pair = {frozenset(v): k for k, v in LINKS.items()}
    links = {}
    for line, r in need(OUT / '관계.csv', ['관계_이름', '읽는_말', '시작', '종료', '카디널리티', '적어도_하나', '근거']):
        where = f'결과/관계.csv:{line}'
        if not re.fullmatch(r'[A-Z][A-Z0-9_]*', r['관계_이름']):
            raise Stop(f'{where}: 관계_이름 「{r["관계_이름"]}」 — 영어 대문자와 밑줄로 씁니다.')
        if not r['읽는_말']:
            raise Stop(f'{where}: 읽는_말 칸이 비었습니다 — 화살표를 「시작 → (읽는 말) → 종료」로 읽을 때의 우리말을 적습니다.')
        k = pair.get(frozenset((r['시작'], r['종료'])))
        if k is None or r['시작'] == r['종료']:
            raise Stop(f'{where}: 시작 「{r["시작"]}」 · 종료 「{r["종료"]}」 — 이 자료로 이을 수 있는 짝은 {" / ".join(" · ".join(v) for v in LINKS.values())}입니다.')
        if k in links:
            raise Stop(f'결과/관계.csv:{links[k][4]} · {line}: {josa(r["시작"], "과/와")} {r["종료"]} 사이의 관계가 두 줄입니다 — 한 짝에 관계 하나를 씁니다.')
        card = r['카디널리티'].replace(' ', '').upper()
        if card not in CARDINALITY:
            raise Stop(f'{where}: 카디널리티 「{r["카디널리티"]}」 — {" · ".join(CARDINALITY)} 가운데 하나입니다(시작 쪽 수:종료 쪽 수).')
        if r['적어도_하나'] not in LEAST:
            raise Stop(f'{where}: 적어도_하나 「{r["적어도_하나"]}」 — {" · ".join(LEAST)} 가운데 하나입니다(시작마다 = 시작 클래스의 인스턴스마다 이 관계가 하나는 있어야 함, 종료마다 = 종료 클래스의 인스턴스마다).')
        links[k] = (r['관계_이름'], r['시작'], r['종료'], card, line, LEAST[r['적어도_하나']], r['읽는_말'])
    miss = [k for k in LINKS if k not in links and k not in OPTIONAL_LINKS]
    if miss:
        raise Stop('결과/관계.csv: 아직 적지 않은 관계 — ' + ', '.join(' · '.join(LINKS[k]) for k in miss))
    if ('실물' in classes) != ('구성 요소-실물' in links):
        raise Stop('결과/클래스.csv · 결과/관계.csv: 구성 요소 자리와 그 실물을 나누려면 클래스.csv에 「실물」 줄과 관계.csv에 구성 요소와 실물을 잇는 줄을 함께 적고, 나누지 않으면 둘 다 적지 않습니다.')
    by_name = {}
    for k, v in links.items():
        by_name.setdefault(v[0], []).append(v[4])
    for name, lines in by_name.items():
        if len(lines) > 1:
            raise Stop(f'결과/관계.csv:{" · ".join(map(str, lines))}: 관계 이름 「{name}」을 두 줄에 썼습니다 — 관계마다 다른 이름을 씁니다.')
    return links


def relation_examples():
    """관계마다 문장으로 읽어 볼 실제 한 쌍을 원자료에서 고른다(그 표의 첫 줄) — {연결: (LINKS의 앞 클래스 쪽 글, 뒤 클래스 쪽 글)}."""
    src = raw()
    comp = src['구성요소_목록.csv']
    sensor = src['센서_목록.csv'][0][1]
    part = next((r for _, r in comp if r['교체부품']), None)
    unit = next((r for _, r in comp if r['일련번호']), None)
    out = {'설비-구성 요소': (comp[0][1]['설비코드'], comp[0][1]['구성요소']),
           '구성 요소-센서': (f"{sensor['설비코드']} {sensor['붙은곳']}", f"{sensor['센서명']}({sensor['태그']})"),
           '센서-물리량': (f"{sensor['센서명']}({sensor['태그']})", sensor['재는것'])}
    if part:
        out['구성 요소-부품'] = (f"{part['설비코드']} {part['구성요소']}", part['교체부품'])
    if unit:
        out['구성 요소-실물'] = (f"{unit['설비코드']} {unit['구성요소']}", unit['일련번호'])
    return out


def design():
    """내 스키마 표 세 장 → (클래스, 속성, 관계)."""
    classes = read_classes()
    return classes, read_properties(classes), read_relations(classes)


def make_id(template, kind, values, where):
    """식별자 틀에 그 행의 값을 넣는다. 틀에 쓴 칸이 그 행에서 비었으면 멈춘다(빈 값으로 지은 식별자는 서로 겹친다)."""
    empty = [x for x in re.findall(r'\{([^}]*)\}', template) if not values.get(x)]
    if empty:
        raise Stop(f'{where}: {kind} 식별자 틀 「{template}」에 쓴 {" · ".join(empty)} 칸이 이 행에서 비었습니다 — 그 클래스의 모든 행에 값이 있는 칸으로 짓습니다.')
    return template.format(**values)


def typed(value, kind):
    """원자료 글자 → (자료형에 맞춘 값, 맞는가). 수 = 숫자만, 날짜 = YYYY-MM-DD."""
    if kind == '수':
        ok = bool(re.fullmatch(r'-?\d+(?:\.\d+)?', value))
        return (float(value) if ok else value), ok
    if kind == '날짜':
        return value, bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}', value))
    return value, True


def why_same(members):
    """한 묶음을 같은 구성 요소로 본 까닭(화면용): 묶음의 모든 행에 같은 태그의 센서가 붙었는지 · 교체부품 칸이 같은 사내 품번으로 풀리는지."""
    tags = sorted(set.intersection(*[set(m['태그']) for m in members]))
    part = members[0]['부품'] if members[0]['부품'] and all(m['부품'] == members[0]['부품'] for m in members) else ''
    said = ['같은 태그의 센서(' + ' · '.join(tags) + ')가 붙음' if tags else '', f'교체부품 칸이 같은 사내 품번({part})' if part else '']
    return ' · '.join(x for x in said if x) or '같은 태그의 센서나 같은 부품으로 차례로 이어짐'


def same_kind(a, b):
    """같은 모델의 두 설비에서 같은 구성 요소를 다르게 적은 행인가(일반 로직). 모델과 계통이 같고, 이름이 같거나 · 같은 태그의 센서가 붙었거나 ·
    교체부품 칸이 같은 사내 품번으로 풀리면 그렇다(같은 모델의 설비는 같은 자리에 같은 태그 · 같은 부품을 쓴다). 모델이 다른 설비의 구성 요소는 견주지 않는다."""
    if a['모델'] != b['모델'] or a['계통'] != b['계통']:
        return False
    return a['이름'] == b['이름'] or bool(set(a['태그']) & set(b['태그'])) or (a['부품'] != '' and a['부품'] == b['부품'])


def name_map(src, rows_done, model_of):
    """원자료 구성 요소 행마다 이름을 정한다(제공 코드 — 누가 해도 같은 일). 같은 모델의 설비끼리 다르게 적힌 같은 구성 요소(same_kind)를 묶어,
    구성 요소 목록에서 먼저 나온 이름 하나로 맞춘다. 맞추기 전 원자료 이름은 그 구성 요소의 다른 이름(aliases)으로 남는다.
    그 모델의 설비가 하나뿐이면 원자료 이름 그대로다. 돌려주는 것: ({(원자료 이름, 모델): 이름}, 화면용 {묶음, 원자료 이름 그대로인 행})."""
    parts = {r['품번'] for _, r in src['예비품_목록.csv']}
    cross = [r for _, r in src['품번_교차표.csv']]
    live_sensors = [(line, r) for line, r in src['센서_목록.csv'] if not rows_done.get(('센서_목록.csv', line))]
    items = []
    for line, r in src['구성요소_목록.csv']:
        if rows_done.get(('구성요소_목록.csv', line)) or r['설비코드'] not in model_of:
            continue
        tags = sorted(s['태그'] for _, s in live_sensors if s['설비코드'] == r['설비코드'] and s['붙은곳'] == r['구성요소'])
        items.append({'설비코드': r['설비코드'], '모델': model_of[r['설비코드']], '계통': r['계통'], '이름': r['구성요소'], '태그': tags,
                      '부품': resolve_cell(r['교체부품'], parts, cross)[0] or '', '줄': f'구성요소_목록.csv:{line}'})
    groups = grouped(items, same_kind)
    named, by_rule = {}, []
    for members in groups:
        name = members[0]['이름']
        for m in members:
            key = (m['이름'], m['모델'])
            if key in named and named[key] != name:
                raise Stop(f'자료/{m["줄"]}: 같은 모델({m["모델"]})의 원자료 이름 「{m["이름"]}」이 서로 다른 구성 요소 둘({named[key]} · {name})에 쓰였습니다 — 그 줄의 계통과 이름을 봅니다.')
            named[key] = name
        if len({m['이름'] for m in members}) > 1:
            by_rule.append((name, members[0]['모델'], len({m['설비코드'] for m in members}), ' · '.join(f'{m["이름"]}({m["설비코드"]})' for m in members), why_same(members)))
    alone = [(m['줄'], m['설비코드'], m['모델'], m['계통'], m['이름']) for members in groups if len({m['설비코드'] for m in members}) == 1 for m in members]
    return named, {'묶음': sorted(by_rule), '그대로': sorted(alone, key=lambda x: int(x[0].split(':')[1]))}


def name_of(named, raw, model):
    """원자료 이름(붙은곳)을 그 모델의 설비끼리 하나로 맞춘 이름으로. 그 모델의 구성 요소 행에 없는 이름은 원자료 이름 그대로 견준다."""
    return named.get((raw, model), raw)


def handling():
    """행_처리.csv → ({(파일, 행): (처리, 대상)}, {(파일, 행): 행_처리.csv 줄}). 처리 = 빼기 · 지난 실물:<지금 행>."""
    out, where = {}, {}
    for line, r in need(OUT / '행_처리.csv', ['파일', '행', '처리', '근거']):
        if not r['행'].isdigit():
            raise Stop(f'결과/행_처리.csv:{line}: 행 「{r["행"]}」 — 편집기에 보이는 줄 번호(숫자)를 씁니다.')
        how = r['처리']
        r['파일'] = r['파일'].removeprefix('자료/')      # 「자료/센서_목록.csv」처럼 폴더를 붙여 적어도 같은 파일
        if r['파일'] not in ('설비_대장.csv', '구성요소_목록.csv', '센서_목록.csv'):
            raise Stop(f'결과/행_처리.csv:{line}: 파일 「{r["파일"]}」 — 설비_대장.csv · 구성요소_목록.csv · 센서_목록.csv 가운데 하나입니다.')
        key = (r['파일'], int(r['행']))
        if how == '빼기':
            out[key] = ('빼기', '')
        elif re.fullmatch(r'지난 실물:\d+', how) and r['파일'] == '구성요소_목록.csv':
            out[key] = ('지난 실물', int(how.split(':', 1)[1]))
        else:
            raise Stop(f'결과/행_처리.csv:{line}: 처리 「{how}」 — 빼기 · 지난 실물:<지금 실물 행 번호>(구성요소_목록.csv만) 가운데 하나로 씁니다.')
        where[key] = line
    return out, where


def quantity_map(src, rows_done, assets, place_of):
    """센서 행마다 물리량을 정한다. 내 규칙(결과/quantity_rules.py — same_quantity · quantity_name)으로 같은 물리량끼리 묶는다. place_of(센서 행) = (붙은 구성 요소 이름, 계통).
    규칙이 서로 다른 묶음에 같은 물리량 이름을 붙이면 멈춘다(같은 이름이면 같은 물리량으로 합쳐지므로). 돌려주는 것: {센서 줄: 물리량}."""
    mod = rules('quantity_rules')
    items = []
    for line, r in src['센서_목록.csv']:
        if rows_done.get(('센서_목록.csv', line)) or r['설비코드'] not in assets:
            continue
        place, group = place_of(line, r)
        items.append((line, {**{k: r[k] for k in ('설비코드', '태그', '센서명', '재는것', '단위')}, '붙은곳': place, '계통': group, '줄': f'센서_목록.csv:{line}'}))
    out, named = {}, {}
    for members in grouped(items, lambda a, b: ask(mod, 'same_quantity', bool, dict(a[1]), dict(b[1]))):
        name = ask(mod, 'quantity_name', str, [dict(m) for _, m in members])
        if name in named:
            raise Stop(f'결과/quantity_rules.py: 서로 다른 묶음 둘에 같은 물리량 이름 「{name}」을 붙였습니다 — {named[name]} · {members[0][1]["줄"]}. '
                       '같은 물리량이면 same_quantity가 묶게 하고, 다른 물리량이면 이름을 달리합니다.')
        named[name] = members[0][1]['줄']
        for line, _ in members:
            out[line] = name
    return out


def unit_map(src, qmap):
    """물리량마다 기준 단위(일반 처리): 그 물리량의 센서 행이 가장 많이 쓴 단위(같은 수면 센서 목록에서 먼저 나온 것). 단위가 적힌 행이 없으면 미확인.
    돌려주는 것: ({물리량: 기준 단위}, 화면용 [(물리량, 원자료에 적힌 단위, 기준 단위)])."""
    per_q = {}
    for line, r in src['센서_목록.csv']:
        if line in qmap:
            per_q.setdefault(qmap[line], []).append(r['단위'])
    base, shown = {}, []
    for q, units in sorted(per_q.items()):
        written = [u for u in units if u]
        base[q] = max(written, key=lambda u: (written.count(u), -written.index(u))) if written else UNKNOWN
        shown.append((q, ' · '.join(f'{u} {written.count(u)}행' for u in dict.fromkeys(written)) or '(적힌 단위 없음)', base[q]))
    return base, shown


# ───────────── 만들기(단계별) ─────────────
def raw():
    return {n: table(DATA / n) for n in ['설비_대장.csv', '구성요소_목록.csv', '센서_목록.csv', '예비품_목록.csv', '품번_교차표.csv']}


def instances(kind, src):
    """그 클래스의 인스턴스가 나오는 원자료 행(실물은 일련번호가 적힌 구성 요소 행)."""
    return [(line, r) for line, r in src[TABLE[kind]] if not (kind == '실물' and not r['일련번호'])]


def classes_view():
    """내 식별자 틀로 원자료 행마다 식별자를 지었을 때 — 서로 다른 식별자 수, 겹치는 행, 틀에 쓴 칸이 빈 행(이름은 아직 원자료 그대로).
    돌려주는 것: (클래스, {클래스: {'행', '개수', '겹침', '빈칸', '파일'}}, 센서 목록의 재는것 칸에 적힌 이름마다 [(이름, 그 이름으로 적힌 센서 행 수)])."""
    classes = read_classes()
    src = raw()
    out = {}
    for kind in classes:
        if kind not in TABLE:
            continue
        seen, blank, rows = {}, [], instances(kind, src)
        for line, r in rows:
            try:
                seen.setdefault(make_id(classes[kind]['id'], kind, r, ''), []).append(line)
            except Stop:
                blank.append(line)
        out[kind] = {'행': len(rows), '개수': len(seen), '겹침': {k: v for k, v in seen.items() if len(v) > 1}, '빈칸': blank, '파일': TABLE[kind]}
    written = [r['재는것'] for _, r in src['센서_목록.csv']]
    return classes, out, [(name, written.count(name)) for name in dict.fromkeys(written)]


def properties_view():
    """내 속성 표를 원자료 행에 대어 본다 — 속성마다 그 칸이 채워진 행 · 빈 행 · 자료형에 맞지 않는 행. 돌려주는 것: (클래스, 속성, [속성마다 dict])."""
    classes = read_classes()
    props = read_properties(classes)
    src = raw()
    rows = []
    for kind, plist in props.items():
        data = instances(kind, src) if kind in TABLE else []
        for p in plist:
            one = dict(클래스=kind, 속성=p['이름'], 칸=p['칸'], 자료형=p['자료형'], 필수=p['필수'], 단위=p['단위'], 줄=p['줄'], 파일=TABLE.get(kind, ''), 행=len(data), 빈칸=[], 안맞음=[], 예='')
            if p['칸'] in DERIVED.get(kind, {}):
                one.update(행=None, 예=DERIVED[kind][p['칸']])
            else:
                one['빈칸'] = [line for line, r in data if not r[p['칸']]]
                one['안맞음'] = [(line, r[p['칸']]) for line, r in data if r[p['칸']] and not typed(r[p['칸']], p['자료형'])[1]]
                one['예'] = next((r[p['칸']] for _, r in data if r[p['칸']]), '')
            rows.append(one)
    return classes, props, rows


def relations_view():
    classes = read_classes()
    return classes, read_relations(classes), relation_examples()


def check_cardinality(links, rels, where_of):
    """관계.csv에 적은 카디널리티를 지금까지 만든 연결과 견준다. 「1」 쪽에 둘 이상 이어진 대상이 있으면 그 관계.csv 줄과 원자료 줄을 짚고 멈춘다.
    카디널리티는 이어질 수 있는 개수를 정해 둔 것이라, 지금 자료의 연결이 그보다 적은 것은 어긋남이 아니다.
    돌려주는 것: 화면용 [(연결, 관계, 적은 것, 시작 하나에 이어진 종료 최대 수, 종료 하나에 이어진 시작 최대 수, 견줌)]."""
    shown = []
    for link, (name, _, _, card, line, *_) in links.items():
        out_n, in_n = {}, {}
        for i, r in enumerate(rels):
            if r['type'] == name:
                out_n.setdefault(r['a'], []).append(i)
                in_n.setdefault(r['b'], []).append(i)
        if not out_n:
            continue
        most_out, most_in = max(len(v) for v in out_n.values()), max(len(v) for v in in_n.values())
        start_side, end_side = card.split(':')
        for side, count, word in [(end_side, out_n, '시작 하나에 종료가'), (start_side, in_n, '종료 하나에 시작이')]:
            if side == '1':
                over = [(x, v) for x, v in count.items() if len(v) > 1]
                if over:
                    x, v = over[0]
                    raise Stop(f'결과/관계.csv:{line}: {name} 카디널리티 {card} — {word} 많아야 하나인데, {x}에 {len(v)}개가 이어집니다'
                               f'({" · ".join(where_of[i] for i in v[:4])}). 원자료가 맞으면 카디널리티를, 연결이 잘못이면 그 판단을 고칩니다'
                               f'(이렇게 걸린 대상 {len(over)}개).')
        shown.append((link, name, card, most_out, most_in, '정한 범위 안'))
    return shown


def build(stage, write=True):
    """stage = '이름' · '센서' · '부품'까지 만든다. 돌려주는 것: 화면용 값과 (부품 단계면) 만든 모델. write=False면 모델 파일을 쓰지 않는다(넣기 전 검증이 쓴다).
    원자료 행을 내 스키마 표에 대어 보아 어긋난 곳(필수 속성이 빈 행 · 자료형에 맞지 않는 값 · 「적어도 하나」인데 관계가 없는 대상)은 멈추지 않고 info['어긋남']에 모은다."""
    classes, props, links = design()
    decided(stage)
    ids = {k: v['id'] for k, v in classes.items()}
    split = '실물' in classes
    src = raw()
    rows_done, rule_line = handling()
    nodes, rels, where_of, index, node_at, info, findings = [], [], [], {}, {}, {}, []
    used_rows = set()
    convert = any(p['단위'] == UNIT_MODES[0] for p in props['센서'])

    def handled(file, line):
        h = rows_done.get((file, line))
        if h:
            used_rows.add((file, line))
        return h

    def node(kind, id_, where, values, factor=1):
        if id_ in index:
            raise Stop(f'{where}: 식별자 「{id_}」가 이미 있습니다(겹친 행). 결과/행_처리.csv에 이 행을 어떻게 할지 정하거나 결과/클래스.csv의 식별자를 바꿉니다.')
        index[id_], node_at[id_] = LABEL[kind], where
        out = {'id': id_}
        for p in props[kind]:
            v, at = values.get(p['칸']), f'결과/속성.csv:{p["줄"]}'
            if v in (None, '', []):
                if p['필수']:
                    findings.append({'종류': '필수 속성이 빈 행', '표': at, '원자료': where, '대상': id_, '글': f'{kind}의 {p["이름"]}({p["칸"]} 칸)을 필수로 정했는데 이 행은 그 칸이 비어 있습니다'})
                continue
            if isinstance(v, str):
                v, ok = typed(v, p['자료형'])
                if not ok:
                    findings.append({'종류': '자료형에 맞지 않는 값', '표': at, '원자료': where, '대상': id_, '글': f'{kind}의 {p["이름"]}({p["칸"]} 칸)을 {p["자료형"]}로 정했는데 이 행의 값은 「{v}」입니다'})
                elif p['자료형'] == '수' and p['단위'] == UNIT_MODES[0]:
                    v = round(v * factor, 6)
            out[p['이름']] = v
        nodes.append({'labels': [LABEL[kind]], 'props': out})

    def rel_(link, a, b, where, **more):
        """a = LINKS의 앞 클래스 쪽 대상, b = 뒤 클래스 쪽 대상. 화살표는 관계.csv가 정한 시작 쪽에서 긋는다."""
        name, start, *_ = links[link]
        x, y = (a, b) if start == LINKS[link][0] else (b, a)
        rels.append({'type': name, 'a': x, 'b': y, 'props': {k: v for k, v in more.items() if v not in (None, '')}})
        where_of.append(where)

    for (file, line), (how, target) in rows_done.items():
        if how == '지난 실물' and not split:
            raise Stop(f'결과/행_처리.csv:{rule_line[(file, line)]}: 「지난 실물」은 구성 요소 자리와 그 실물을 나눌 때(결과/클래스.csv에 실물 줄)만 씁니다 — 나누지 않으면 「빼기」로 둡니다.')

    # 설비
    assets, model_of = {}, {}
    for line, r in src['설비_대장.csv']:
        if handled('설비_대장.csv', line):
            continue
        assets[r['설비코드']] = make_id(ids['설비'], '설비', r, f'자료/설비_대장.csv:{line}')
        model_of[r['설비코드']] = r['모델']
        node('설비', assets[r['설비코드']], f'자료/설비_대장.csv:{line}', r)
    # 구성 요소(자리)와, 나누기로 했으면 그 자리의 실물
    comps, per_asset, comp_at_row = {}, {}, {}
    for line, r in src['구성요소_목록.csv']:
        if r['설비코드'] not in assets and not rows_done.get(('구성요소_목록.csv', line)):
            raise Stop(f'자료/구성요소_목록.csv:{line}: 설비코드 「{r["설비코드"]}」가 모델의 설비에 없습니다.')
    named, name_info = name_map(src, rows_done, model_of)
    info['이름'] = name_info
    units = []

    def unit(cid, r, line, current):
        values = {**r, '구성요소': name_of(named, r['구성요소'], model_of[r['설비코드']])}
        uid = make_id(ids['실물'], '실물', values, f'자료/구성요소_목록.csv:{line}')
        node('실물', uid, f'자료/구성요소_목록.csv:{line}', values)
        rel_('구성 요소-실물', cid, uid, f'구성요소_목록.csv:{line}', current=current)
        units.append((cid, r['일련번호'], '지금' if current else '지난', f'구성요소_목록.csv:{line}'))
    for line, r in src['구성요소_목록.csv']:
        per_asset.setdefault(r['설비코드'], [0, 0])[0] += 1
        if handled('구성요소_목록.csv', line):
            continue
        code = r['설비코드']
        cname = name_of(named, r['구성요소'], model_of[code])
        values = {**r, '구성요소': cname, '다른이름': [r['구성요소']] if r['구성요소'] != cname else []}
        cid = make_id(ids['구성 요소'], '구성 요소', values, f'자료/구성요소_목록.csv:{line}')
        node('구성 요소', cid, f'자료/구성요소_목록.csv:{line}', values)
        rel_('설비-구성 요소', assets[code], cid, f'구성요소_목록.csv:{line}')
        comps[(code, cname)] = (cid, line, r)
        comp_at_row[line] = (code, cname, cid)
        per_asset[code][1] += 1
        if split and r['일련번호']:
            unit(cid, r, line, True)
    by_line = dict(src['구성요소_목록.csv'])
    for (file, line), (how, target) in sorted(rows_done.items()):
        if how != '지난 실물':
            continue
        r = by_line.get(line)
        now = comp_at_row.get(target)
        if r is None or now is None or (r['설비코드'], name_of(named, r['구성요소'], model_of.get(r['설비코드'], ''))) != now[:2]:
            raise Stop(f'결과/행_처리.csv:{rule_line[(file, line)]}: 「지난 실물:{target}」 — 구성요소_목록.csv:{target}이 이 행(:{line})과 같은 설비 · 같은 자리의 살아 있는 행이어야 합니다.')
        if not r['일련번호']:
            raise Stop(f'결과/행_처리.csv:{rule_line[(file, line)]}: 구성요소_목록.csv:{line}에 일련번호가 없어 지난 실물로 남길 수 없습니다.')
        unit(now[2], r, line, False)
    info['구성 요소'] = {code: tuple(v) for code, v in sorted(per_asset.items())}
    info['실물'] = units if split else None
    info['어긋남'] = findings
    if stage == '이름':
        check_cardinality(links, rels, where_of)
        info.update(unused=[k for k in rows_done if k not in used_rows and k[0] in ('설비_대장.csv', '구성요소_목록.csv')])
        return info, None
    # 센서와 물리량
    for line, r in src['센서_목록.csv']:
        if r['설비코드'] not in assets and not rows_done.get(('센서_목록.csv', line)):
            raise Stop(f'자료/센서_목록.csv:{line}: 설비코드 「{r["설비코드"]}」가 모델의 설비에 없습니다.')

    def place_of(line, r):
        cname = name_of(named, r['붙은곳'], model_of[r['설비코드']])
        if (r['설비코드'], cname) not in comps:
            raise Stop(f'자료/센서_목록.csv:{line}: 붙은곳 「{r["붙은곳"]}」(→ {cname})이 {r["설비코드"]}의 구성 요소에 없습니다 — 붙은곳 칸의 이름이 그 설비의 구성 요소 목록에 적힌 이름과 같은지 봅니다.')
        return cname, comps[(r['설비코드'], cname)][2]['계통']
    qmap = quantity_map(src, rows_done, assets, place_of)
    base, base_shown = unit_map(src, qmap)
    info['단위'] = base_shown
    info['단위_담는_법'] = UNIT_MODES[0] if convert else UNIT_MODES[1]
    sensors, quants, convs = [], {}, []
    for line, r in src['센서_목록.csv']:
        if handled('센서_목록.csv', line):
            continue
        code, qname = r['설비코드'], qmap[line]
        qid = make_id(ids['물리량'], '물리량', {'물리량': qname}, f'자료/센서_목록.csv:{line}')
        sid = make_id(ids['센서'], '센서', r, f'자료/센서_목록.csv:{line}')
        unit_, factor, out_unit = r['단위'], 1, r['단위']
        if convert and unit_ and base[qname] != UNKNOWN and unit_ != base[qname]:
            if (unit_, base[qname]) not in FACTOR:
                raise Stop(f'자료/센서_목록.csv:{line}: 단위 「{unit_}」를 물리량 「{qname}」의 기준 단위 「{base[qname]}」로 바꾸는 법을 모릅니다'
                           f'(이 도구가 아는 환산: {", ".join(f"{a}→{b}" for a, b in FACTOR)}). 단위가 다른 것을 재는 센서가 한 물리량에 묶였는지 봅니다.')
            factor, out_unit = FACTOR[(unit_, base[qname])], base[qname]
            n, m = number(r['정상값']), number(r['한계'])
            convs.append((f'센서_목록.csv:{line}', sid, qname, unit_, out_unit, f'{r["정상값"] or "없음"} / {r["한계"] or "없음"}',
                          f'{"없음" if n is None else "%g" % round(n * factor, 6)} / {"없음" if m is None else "%g" % round(m * factor, 6)}'))
        node('센서', sid, f'자료/센서_목록.csv:{line}', {**r, '단위': out_unit}, factor)
        rel_('구성 요소-센서', comps[(code, place_of(line, r)[0])][0], sid, f'센서_목록.csv:{line}')
        quants.setdefault(qid, (qname, '' if base[qname] == UNKNOWN else base[qname], f'자료/센서_목록.csv:{line}'))
        rel_('센서-물리량', sid, qid, f'센서_목록.csv:{line}')
        sensors.append((sid, code, r['태그'], qname, f'센서_목록.csv:{line}', r['재는것']))
    for qid, (qname, unit_, first) in quants.items():
        node('물리량', qid, first, {'물리량': qname, '기준단위': unit_})
    info['센서'] = sensors
    info['변환'] = convs
    if stage == '센서':
        check_cardinality(links, rels, where_of)
        info.update(unused=[k for k in rows_done if k not in used_rows])
        return info, None
    # 부품 — 사내 품번 하나에 부품 하나, 다른 표기는 그 부품의 「다른표기」 칸(목록)으로 준다
    parts = {r['품번']: (line, r) for line, r in src['예비품_목록.csv']}
    cross = [r for _, r in src['품번_교차표.csv']]
    part_id, codes = {}, []
    for pid, (line, r) in parts.items():
        part_id[pid] = make_id(ids['부품'], '부품', r, f'자료/예비품_목록.csv:{line}')
        other = sorted({c['다른표기'] for c in cross if c['사내품번'] == pid})
        node('부품', part_id[pid], f'자료/예비품_목록.csv:{line}', {**r, '다른표기': other})
        codes.append((part_id[pid], pid, r['품명'], ' · '.join(other) or '없음'))
    linked, lost, blank = [], [], []
    for (code, cname), (cid, line, r) in comps.items():
        cell = r['교체부품']
        pid, how = resolve_cell(cell, parts, cross)
        if pid is None:      # 품번으로 풀리지 않는 칸 · 빈 칸은 짐작해 잇지 않고 화면에 따로 보인다
            (lost if cell else blank).append((f'구성요소_목록.csv:{line}', code, cname, cell or '(빈칸)'))
            continue
        rel_('구성 요소-부품', cid, part_id[pid], f'구성요소_목록.csv:{line}', source_text=cell)
        linked.append((f'구성요소_목록.csv:{line}', code, cname, cell, pid, how))
    info['카디널리티'] = check_cardinality(links, rels, where_of)
    for link, (name, start, end, _, line, least, _) in links.items():      # 「적어도 하나」로 정한 쪽에서 이 관계가 하나도 없는 대상
        for side in least:
            mine, other, key = (start, end, 'a') if side == '시작' else (end, start, 'b')
            has = {r[key] for r in rels if r['type'] == name}
            findings += [{'종류': '「적어도 하나」인데 관계가 없는 대상', '표': f'결과/관계.csv:{line}', '원자료': node_at[i], '대상': i,
                          '글': f'{name}: {mine}마다 {josa(other, "이/가")} 적어도 하나라고 정했는데 이 {mine}에는 하나도 이어지지 않았습니다'} for i, l in index.items() if l == LABEL[mine] and i not in has]
    info.update(이은_부품=linked, 못_찾은_칸=lost, 빈_칸=blank, 다른_표기=codes, unused=[k for k in rows_done if k not in used_rows])
    model = make_model(classes, props, links, nodes, rels)
    if write:
        OUT.mkdir(exist_ok=True)
        (OUT / 'schema.json').write_text(json.dumps(model[0], ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
        (OUT / 'graph.json').write_text(json.dumps(model[1], ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    return info, model


def make_model(classes, props, links, nodes, rels):
    """내 표 세 장 → 스키마(schema.json의 꼴), 만든 노드와 관계 → 인스턴스 데이터(graph.json의 꼴)."""
    schema_classes = {}
    for kind, c in classes.items():
        spec = {'meaning': c['의미'], 'required': {'id': 'string'}, 'optional': {}, 'source': {}}
        for p in props[kind]:
            spec['required' if p['필수'] else 'optional'][p['이름']] = TYPES[p['자료형']]
            spec['source'][p['이름']] = p['칸']
        schema_classes[LABEL[kind]] = spec
    relations, names = {}, {}
    for link, (name, start, end, card, _, least, reads) in links.items():
        relations[name] = {'from': LABEL[start], 'to': LABEL[end], 'reads': reads, 'cardinality': card, 'at_least_one': [{'시작': 'from', '종료': 'to'}[s] for s in least]}
        if link == '구성 요소-부품':
            relations[name]['properties'] = {'source_text': 'string'}
        if link == '구성 요소-실물':
            relations[name]['properties'] = {'current': 'boolean'}
        names[link] = name
    schema = {'classes': schema_classes, 'relations': relations, 'identity': {LABEL[k]: v['id'] for k, v in classes.items()}, 'links': names}
    return schema, {'nodes': nodes, 'rels': rels}


# ───────────── 물어보기(모델만 읽는다 — 원자료를 다시 읽지 않는다) ─────────────
def load_model():
    if not ((OUT / 'schema.json').is_file() and (OUT / 'graph.json').is_file()):
        raise Stop('아직 모델이 없습니다 — python run.py parts로 만든 뒤 다시 실행합니다.')
    schema = json.loads((OUT / 'schema.json').read_text(encoding='utf-8'))
    graph = json.loads((OUT / 'graph.json').read_text(encoding='utf-8'))
    return schema, graph


FILTERS = ('=', '>', '<', '없음', '있음', '가장 큰', '가장 작은', '가장 이른', '가장 늦은')
ASK_FORM = ('질문 4의 물을_값은 「클래스.속성 조건」 꼴입니다(조건 = ' + ' · '.join(FILTERS) + ', 「=」 · 「>」 · 「<」 뒤에는 값). 조건이 여럿이면 「 & 」로 잇고 한 클래스의 속성만 씁니다. '
            '항목에는 답으로 볼 그 클래스의 속성 이름 하나를 적습니다.')


def answers(asks, items=None):
    """asks = [(질문, 물을 값)] → [{'질문','물을_값','항목','답'}]. 물을 값과 답은 현장이 쓰는 값(설비 코드 · 사내 품번 · 다른 표기)이다 —
    식별자와 속성 이름을 어떻게 지었든, 그 원자료 칸을 담은 속성(스키마의 source)으로 찾고 그 속성으로 답한다. 그 칸을 담은 속성이 스키마에 없으면 「답할 수 없음」이다.
    관계는 화살표를 어느 쪽에서 그었든 따라간다(그은 방향 그대로, 또는 거꾸로) — 찾을 때는 거꾸로 따라가도 같은 연결이다.
    질문 1 = 설비 코드 → 구성 요소마다 붙은 센서 태그(항목 = 구성 요소 이름)와 그 자리에 달린 실물의 일련번호(항목 = 「구성 요소 이름 실물」 —
    실물을 따로 둔 모델이면 「일련번호(지금)」 · 「일련번호(지난)」, 아니면 구성 요소의 일련번호 속성 하나). 질문 1 줄에는 그 구성 요소의 다른 이름(원자료 이름)도 함께 돌려준다.
    질문 2 = 물리량 이름 → 그 물리량을 재는 센서(설비코드:태그, 항목 빈칸)와 센서마다 값(항목 = 설비코드:태그, 답 = 단위 · 정상값 · 한계 · 한계구분).
    질문 3 = 품번 · 표기 → 찾은 사내 품번(항목)과 그 부품을 쓰는 설비 코드. 없으면 답 「없음」.
    질문 4 = 내가 더한 질문 — 클래스의 속성으로 거르거나 견준다(ASK_FORM). items = {(질문, 물을 값): [(답으로 볼 속성 이름, 기대 답 표의 줄)]}."""
    schema, graph = load_model()
    label = {n['props']['id']: n['labels'][0] for n in graph['nodes']}
    props = {n['props']['id']: n['props'] for n in graph['nodes']}
    by_out, by_in = {}, {}
    for r in graph['rels']:
        by_out.setdefault((r['type'], r['a']), []).append(r)
        by_in.setdefault((r['type'], r['b']), []).append(r)
    def across(i, link, toward):
        """대상 i에서 그 연결을 따라 toward 클래스 쪽으로 이어진 [(대상, 관계)]. 화살표를 toward 쪽으로 그었으면 그대로, 반대로 그었으면 거꾸로 따라간다."""
        name = schema.get('links', {}).get(link)
        spec = schema['relations'].get(name) if name else None
        if not spec:
            return []
        if spec.get('to') == LABEL[toward]:
            return sorted(((r['b'], r) for r in by_out.get((name, i), [])), key=lambda x: x[0])
        return sorted(((r['a'], r) for r in by_in.get((name, i), [])), key=lambda x: x[0])

    def ends(i, link):
        return [x for x, _ in across(i, link, LINKS[link][1])]

    def starts(i, link):
        return [x for x, _ in across(i, link, LINKS[link][0])]

    def key(kind, column):
        """그 클래스에서 그 원자료 칸을 담은 속성 이름. 없으면 None."""
        source = schema['classes'].get(LABEL[kind], {}).get('source', {})
        return next((p for p, c in source.items() if c == column), None)

    def lack(kind, column):
        return f'답할 수 없음({kind} 클래스에 「{column}」 칸을 담은 속성이 없음)'

    def of(kind):
        return [i for i, l in label.items() if l == LABEL[kind]]

    def value_text(p):
        """질문 2 센서 값 — 「단위 · 정상값 · 한계 · 한계구분」 차례. 값 없음 · 그 칸을 담은 속성 없음은 「없음」."""
        def get(column):
            v = p.get(key('센서', column) or '')
            return '없음' if v in (None, '') else ('%g' % v if isinstance(v, (int, float)) else str(v))
        return ' · '.join(get(c) for c in ('단위', '정상값', '한계', '한계구분'))

    out = []
    for q, value in asks:
        q = str(q).strip()
        row = lambda item, answer, **more: out.append({'질문': q, '물을_값': value, '항목': item, '답': answer, **more})
        if q == '1':
            code, cname, tag = key('설비', '설비코드'), key('구성 요소', '구성요소'), key('센서', '태그')
            miss = next((lack(k, c) for k, c, p in (('설비', '설비코드', code), ('구성 요소', '구성요소', cname), ('센서', '태그', tag)) if p is None), None)
            if miss:
                row('', miss)
                continue
            hit = [i for i in of('설비') if props[i].get(code) == value]
            if not hit:
                row('', '없음')
                continue
            split = '구성 요소-실물' in schema.get('links', {})
            for c in ends(hit[0], '설비-구성 요소'):
                other = list(props[c].get(key('구성 요소', '다른이름') or '', []))
                tags = sorted(props[s].get(tag, '?') for s in ends(c, '구성 요소-센서'))
                row(props[c].get(cname, c), ' · '.join(tags) or '없음', 다른_이름=other)      # 센서가 없는 구성 요소도 빼지 않고 「없음」으로(기대 답 표의 「값이 없으면 없음」과 같은 꼴)
                serial = key('실물' if split else '구성 요소', '일련번호')
                if split:
                    held = sorted((not r['props'].get('current'), props[u].get(serial or '', '?')) for u, r in across(c, '구성 요소-실물', '실물'))
                    serials = ' · '.join(f'{s}({"지난" if past else "지금"})' for past, s in held) if serial else (lack('실물', '일련번호') if held else '')
                else:
                    serials = props[c].get(serial, '') if serial else ''
                if serials:
                    row(props[c].get(cname, c) + ' 실물', serials, 다른_이름=[x + ' 실물' for x in other])
        elif q == '2':
            qname, code, tag = key('물리량', '물리량'), key('설비', '설비코드'), key('센서', '태그')
            miss = next((lack(k, c) for k, c, p in (('물리량', '물리량', qname), ('설비', '설비코드', code), ('센서', '태그', tag)) if p is None), None)
            if miss:
                row('', miss)
                continue
            hit = [i for i in of('물리량') if props[i].get(qname) == value]
            if not hit:
                row('', '없음')
                continue
            found = []
            for s in starts(hit[0], '센서-물리량'):
                asset = next((a for c in starts(s, '구성 요소-센서') for a in starts(c, '설비-구성 요소')), None)
                item = f'{props[asset].get(code, "?") if asset else "?"}:{props[s].get(tag, "?")}'
                found.append(item)
                row(item, value_text(props[s]))
            row('', ' · '.join(sorted(found)))
        elif q == '3':
            no, other, code = key('부품', '품번'), key('부품', '다른표기'), key('설비', '설비코드')
            miss = next((lack(k, c) for k, c, p in (('부품', '품번', no), ('설비', '설비코드', code)) if p is None), None)
            if miss:
                row('', miss)
                continue
            ids = sorted(i for i in of('부품') if props[i].get(no) == value or value in props[i].get(other or '', []))
            if not ids:
                row('', '없음' if other or any(props[i].get(no) == value for i in of('부품')) else '없음(부품 클래스에 「다른표기」 칸을 담은 속성이 없어 사내 품번으로만 찾음)')
                continue
            for pid in ids:
                assets = sorted({props[a].get(code, a) for c in starts(pid, '구성 요소-부품') for a in starts(c, '설비-구성 요소')})
                row(props[pid].get(no, pid), ' · '.join(assets) or '쓰는 설비 없음')
        elif q == '4':
            for item, line in (items or {}).get((q, value)) or [('', '')]:
                row(item, filtered(schema, graph, value, item, f'결과/기대_답.csv:{line}' if line else '결과/기대_답.csv'))
        else:
            raise Stop(f'결과/기대_답.csv: 질문 「{q}」 — 질문은 1 · 2 · 3과 내가 더한 4입니다.')
    return out


def filtered(schema, graph, asked, item, where='결과/기대_답.csv'):
    """질문 4 — 「클래스.속성 조건」들로 그 클래스의 인스턴스를 거르고, 남은 인스턴스의 item 속성 값을 돌려준다. 스키마에 없는 속성 · 견줄 수 없는 자료형은 그 까닭을 답으로 돌려준다.
    where = 기대 답 표의 그 줄(파일:줄) — 꼴을 읽지 못하면 그 줄을 짚고 멈춘다."""
    conds, kinds = [], set()
    for piece in asked.split('&'):
        m = re.fullmatch(r'\s*(.+?)\.(\S+?)\s*(' + '|'.join(re.escape(f) for f in FILTERS) + r')\s*(.*?)\s*', piece)
        if not m or m.group(1) not in LABEL or (m.group(3) in ('=', '>', '<')) != bool(m.group(4)):
            raise Stop(f'{where}: 질문 4의 물을_값 「{asked}」을 읽지 못했습니다 — {ASK_FORM}')
        conds.append(m.groups())
        kinds.add(m.group(1))
    if len(kinds) != 1 or not (item or '').strip():
        raise Stop(f'{where}: 질문 4 「{asked}」 · 항목 「{item}」을 읽지 못했습니다 — {ASK_FORM}')
    kind = kinds.pop()
    spec = schema['classes'].get(LABEL[kind])
    if spec is None:
        return f'답할 수 없음(모델에 {kind} 클래스가 없음)'
    types = {'id': 'string', **spec.get('required', {}), **spec.get('optional', {})}
    for name in [c[1] for c in conds] + [item]:
        if name not in types:
            column = name in spec.get('source', {}).values() or not re.fullmatch(r'[a-z][a-z0-9_]*', name)      # 속성 이름 자리에 원자료 칸 이름을 적은 줄
            return f'답할 수 없음({kind} 클래스에 속성 「{name}」이 없음' + (' — 물을_값과 항목에는 원자료 칸 이름이 아니라 속성 표에 적은 속성 이름을 씁니다' if column else '') + ')'
    left = [n['props'] for n in graph['nodes'] if n['labels'][0] == LABEL[kind]]
    for _, name, how, want in conds:
        ordered = types[name] in ('number', 'date')
        if how in ('>', '<', '가장 큰', '가장 작은', '가장 이른', '가장 늦은') and not ordered:
            return f'견줄 수 없음({kind}의 속성 「{name}」의 자료형이 {next(k for k, v in TYPES.items() if v == types[name])} — 크기나 앞뒤를 견주려면 수나 날짜여야 함)'
        have = [p for p in left if p.get(name) not in (None, '', [])]
        if how == '없음':
            left = [p for p in left if p.get(name) in (None, '', [])]
        elif how == '있음':
            left = have
        elif how == '=':
            left = [p for p in have if (('%g' % p[name]) if isinstance(p[name], (int, float)) else str(p[name])) == (('%g' % float(want)) if types[name] == 'number' and number(want) is not None else want)]
        elif how in ('>', '<'):
            limit = number(want) if types[name] == 'number' else want
            if limit is None:
                raise Stop(f'{where}: 질문 4 「{asked}」 — 수 속성 「{name}」과 견줄 값 「{want}」이 숫자가 아닙니다.')
            left = [p for p in have if (p[name] > limit if how == '>' else p[name] < limit)]
        else:
            if have:
                best = (max if how in ('가장 큰', '가장 늦은') else min)(p[name] for p in have)
                have = [p for p in have if p[name] == best]
            left = have
    values = [p.get(item) for p in left]
    return ' · '.join(sorted(('%g' % v) if isinstance(v, (int, float)) else ' · '.join(v) if isinstance(v, list) else str(v) for v in values if v not in (None, '', []))) or '없음'
