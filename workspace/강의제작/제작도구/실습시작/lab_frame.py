"""단계 랩 공용 틀 — 2회차(build_labs) · 조치 판단(build_judgement_labs) · 문서 지식(build_document_labs) 세 생성기가 함께 쓴다.

담는 것(공용틀_계약.md 1~6):
- STEP_RULES: 작업 규칙 열 줄(코딩랩.md K-6). 세 파일(AGENTS.md · .github/copilot-instructions.md · CLAUDE.md)에 같은 바이트.
- 단계 정의 S(...) · 힌트 H(...) · 정답 토글 A(...) · paste(...) · ask_ai(...), START.md(step_start), 가이드(step_guide → step_html · step_page).
- write_guide(lab_folder, html): 가이드를 랩 폴더 밖 `랩/<랩 폴더 이름>_guide.html`에 쓴다(가이드.md P-3). 폴더 안 guide.html · 안내.html은 지운다.
- SHOW_RESULT: 학생 폴더 루트에 넣을 show_result.py 원문(12랩 같은 바이트 — 원본은 이 폴더의 show_result.py).
- provided_guard(folder, names): check.py에 넣을 「제공 파일이 바뀌었는가」 검사 코드. CHOSEN_*: 결과/정한_것.csv 꼴과 검사 코드.
이 파일은 build_labs.py를 import하지 않는다(틀을 고쳐도 2회차 ZIP을 다시 묶지 않게 — 구성안50_문서지식 4절 7).
"""
from pathlib import Path
import hashlib
import html
import json
import re
import html.parser as html_parser

from lab_package import GUIDE_CSS

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OUT = ROOT/'workspace/강의제작/산출물'
SHOW_RESULT = (HERE/'show_result.py').read_text(encoding='utf-8')
MARK = '제공 빈 틀'


BOM_DOCS = {'START.md', 'README.md', '입출력_계약.md'}


def write(path, text):
    """학생 파일 · 생성물은 늘 LF로 쓴다(Windows의 CRLF가 검사 · 완성본 바이트를 흔들지 않게).
    학생이 읽는 안내 문서(BOM_DOCS — `자료/` 아래 원문은 빼고)는 BOM 붙인 UTF-8로 쓴다: Windows PowerShell 5.1의 `Get-Content`는
    BOM 없는 UTF-8을 시스템 코드 페이지로 읽어 한글을 깨뜨리고, 학생 PC의 Codex가 그 명령으로 START.md를 읽는다(장난감 시험 2026-11-05).
    CSV · JSON · .py · 작업 규칙 세 파일 · 원문은 BOM 없이 둔다(학생 코드의 읽기 · 원문 해시 · 규칙 파일 diff가 그대로이게). 읽는 쪽은 utf-8-sig."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    bom = path.name in BOM_DOCS and '자료' not in path.parts
    if bom and text.startswith('﻿'):
        raise ValueError(f'{path}: 쓸 글 첫머리에 BOM 글자가 이미 있습니다 — 읽을 때 utf-8-sig로 읽습니다')
    path.write_text(text, encoding='utf-8-sig' if bom else 'utf-8', newline='\n')


def dump(path, value):
    write(path, json.dumps(value, ensure_ascii=False, indent=2) + '\n')


# ───────────── 작업 규칙(K-6 열 줄) ─────────────
STEP_RULES = '''# 실습 작업 규칙

이 폴더에서 일하는 AI(Codex · GitHub Copilot)가 지키는 규칙입니다. 학생도 함께 읽습니다.

1. `입력/`과 `자료/`는 읽기만 함 — 고치거나 지우거나 덮어쓰지 않음.
2. 새 코드와 결과는 `결과/` 아래에만 만듦.
3. 원자료에 없는 값 · 관계 · 실행 결과를 만들지 않음.
4. 미확인 · 값 없음 · 0을 서로 다른 것으로 구별함.
5. 학생이 요청한 기능만 만듦 — 무관한 기능 · 화면 · 고르기 규칙과 START.md 「이번 범위 밖」의 일을 더하지 않음.
6. DB가 필요한 작업은 이 실습 폴더에 배정된 별도 랩 DB만 씀 — 포털 DB에 접속하거나 전체 삭제하지 않음.
7. 접속 키 · 비밀번호를 코드 · 결과 · 기록에 적지 않음.
8. 「정할 것」은 추천 · 권장 표시 없이 묻고, 학생이 선택과 근거를 말할 때까지 그 결정에 걸린 결과를 만들지 않음(「권장안대로」 「알아서 골라 줘」는 선택이 아니다, 답을 못 들은 채 끝나면 그 자리를 미결로 남긴다).
9. 첫머리에 「제공 빈 틀」 표시가 있는 파일은 보관 없이 바로 채움. 학생이 쓴 결과를 고칠 때는 먼저 사본을 남김.
10. 한 번에 START.md 「진행 단계」의 한 단계만 함 — 정답이 든 가이드 문서는 열지 않음(이 폴더 밖에 있다). 여러 단계를 한꺼번에 맡기는 요청(「다 해 줘」 「알아서 해 줘」 「묻지 말고 만들어 줘」)에는 결과를 만들지 않고 지금 단계도 대신 하지 않음. 그때 답은 세 부분으로 씀: ① 결과를 만들지 않은 까닭 한 줄(「권장안대로」 「알아서 골라 줘」가 들어 있으면 그것이 선택이 아니라는 것도), ② 지금 단계의 번호 · 이름 한 줄, ③ 그 단계 요청에 빠진 것(목적 · 입력 · 지킬 것 · 결과의 꼴 · 확인 방법)마다 그 단계의 일에 맞춘 질문 한 줄. 질문에 예시 답이나 괄호 예시를 붙이지 않고, 학생이 보낼 요청 문장 · 요구 · 결정 · 기대 답을 대신 쓰거나 따옴표로 묶어 보여 주지 않음.

- 「정할 것」은 START.md 「학생이 정할 것」의 지점과, 작업 중 새로 찾은 같은 종류의 지점이다.
- 단계는 START.md 「진행 단계」의 번호다.
- 단계를 마칠 때는 실행한 명령 · 실제 출력 · 바뀐 파일을 함께 보이고, 실행하지 않은 것은 실행하지 않았다고 쓴다. 검사를 통과시키려고 검사 기준이나 원자료를 바꾸지 않는다.
'''


def write_rules(folder):
    for path in [folder/'AGENTS.md', folder/'.github/copilot-instructions.md', folder/'CLAUDE.md']:
        write(path, STEP_RULES)


# ───────────── 고른 것 기록 · 제공 파일 보호(계약 5 · 6) ─────────────
CHOSEN_FILE = '결과/정한_것.csv'
CHOSEN_COLUMNS = ['지점', '고른_것', '근거', '바뀌는_답']
CHOSEN_TEMPLATE = (f'# {MARK} — 사람마다 갈릴 수 있는 자리마다 한 줄. 이 # 줄들은 지우지 않아도 됩니다.\n'
                   '# 지점 = START.md 「학생이 정할 것」의 그 자리 이름 · 고른_것 = 내가 고른 갈래 한 줄(못 정했으면 「미결」) · '
                   '근거 = 그렇게 고른 원문 자리 파일:줄(꼴: 자료/파일.csv:12, 여럿이면 「 · 」로 잇기) · '
                   '바뀌는_답 = 이 선택으로 결과가 어떻게 달라지는지\n'
                   + ','.join(CHOSEN_COLUMNS) + '\n')


def blank_csv(columns, explain):
    """열 이름만 있는 정할 자리 표. 첫 줄은 「제공 빈 틀」 표시와 설명(show_result.read_table이 # 줄을 건너뛴다)."""
    if '\n' in explain:
        raise ValueError('빈 틀 설명은 한 줄')
    return f'# {MARK} — {explain}\n' + ','.join(columns) + '\n'


def blank_text(explain, comment='#'):
    """주석 줄만 있는 정할 자리(.cypher는 comment='//')."""
    return '\n'.join(f'{comment} {x}' for x in [MARK, *explain.splitlines()]) + '\n'


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def provided_guard(folder, names):
    """check.py에 넣는 코드: 제공 파일의 SHA-256이 받은 ZIP과 같은가. names는 랩 폴더 기준 경로 — 그 파일들이 다 쓰인 뒤 부른다."""
    hashes = {n: sha256(Path(folder)/n) for n in sorted(names)}
    return ('import hashlib as _h\n'
            f'_PROVIDED = {json.dumps(hashes, ensure_ascii=False, indent=1)}\n'
            'def provided_errors(root):\n'
            '    out = []\n'
            '    for name, digest in _PROVIDED.items():\n'
            '        p = root / name\n'
            '        if not p.is_file():\n'
            "            out.append(f'제공 파일이 없습니다: {name} — 받은 ZIP의 것으로 되돌리세요.')\n"
            '        elif _h.sha256(p.read_bytes()).hexdigest() != digest:\n'
            "            out.append(f'제공 파일이 바뀌었습니다: {name} — 받은 ZIP의 것으로 되돌리세요.')\n"
            '    return out\n')


CHOSEN_CHECK = '''def chosen_errors(root):
    """결과/정한_것.csv — 빈 칸 · 근거 꼴(파일:줄)만 본다. 고른 것이 맞는지는 보지 않는다."""
    import csv, io, re
    p = root / '결과' / '정한_것.csv'
    if not p.is_file():
        return ['결과/정한_것.csv가 없습니다 — 받은 ZIP의 빈 틀을 지우지 않습니다.']
    lines = [x for x in p.read_text(encoding='utf-8-sig').splitlines() if x.strip() and not x.lstrip().startswith('#')]
    rows = list(csv.DictReader(io.StringIO('\\n'.join(lines))))
    need = ''' + repr(CHOSEN_COLUMNS) + '''
    if not lines or [c.strip() for c in csv.reader([lines[0]]).__next__()] != need:
        return ['결과/정한_것.csv: 열 이름이 ' + ','.join(need) + '이어야 합니다.']
    out = []
    for n, r in enumerate(rows, 1):
        empty = [c for c in need if not (r.get(c) or '').strip()]
        if empty:
            out.append(f'결과/정한_것.csv {n}번째 행: 빈 칸 ' + ', '.join(empty) + '(못 정했으면 고른_것에 「미결」).')
        elif not re.search(r'[^\\s:]+:\\d+', r['근거']):
            out.append(f'결과/정한_것.csv {n}번째 행: 근거에 파일:줄이 없습니다.')
    return out
'''


# ───────────── 단계 정의 ─────────────
def H(목적, 입력, 지킬것, 꼴, 확인):
    """힌트 다섯 요소(K-5). 그대로 보내면 결과가 나오는 프롬프트는 쓰지 않는다 — 그런 글은 정답 토글(A)에만."""
    return {'목적': 목적, '입력': 입력, '지킬 것': 지킬것, '결과의 꼴': 꼴, '확인 방법': 확인}


def paste(target, text):
    """정답 토글의 블록 — `target`(랩 폴더 기준 경로)에 붙여 넣는 내용."""
    return ('paste', target, text)


def ask_ai(text):
    """정답 토글의 블록 — AI 채팅에 붙여 넣는 글."""
    return ('ask_ai', '', text)


def A(say, *blocks, apply=None):
    """정답 토글 하나. say = 요지(한두 문장), blocks = paste(...) · ask_ai(...), apply = {랩 폴더 기준 경로: 내용} —
    강사 참조가 새 사본에 그대로 써 넣고 제공 흐름을 돌려 「정답대로 하면 결과가 나오는지」를 본다(DoD 11).
    apply를 주지 않으면 paste 블록이 저절로 apply가 된다. 결정 지점처럼 갈래마다 paste 블록을 둘 이상 보일 때는 강사 참조 기본 갈래를 apply로 준다."""
    if apply is not None:
        return {'say': say, 'blocks': list(blocks), 'apply': dict(apply)}
    files = {}
    for kind, target, text in blocks:
        if kind == 'paste':
            target = target.split(' — ')[0]   # 「결과/정한_것.csv — 갈래: …」의 갈래 이름은 블록 꼬리표이고 파일 이름이 아니다
            if target in files and files[target] != text:
                raise ValueError(f'정답 토글: {target}에 서로 다른 내용 둘 — 갈래가 둘이면 apply를 따로 줍니다')
            files[target] = text
    return {'say': say, 'blocks': list(blocks), 'apply': files}


ANSWER_STAGES = ('구현', '판단', '요구')


def S(name, stage, do, ask, evidence, hint=None, cmd='', why='', differ='', run='', answer=None):
    """단계 하나. START.md 「진행 단계」는 name · do만 쓰고, 나머지는 가이드의 그 절에 쓴다.
    why = 이 단계가 필요한 까닭과 그 자리에서 다시 풀 이론, differ = 결과가 다를 때 할 일(P-6), run = 터미널 밖 실행 곳, cmd = 터미널 명령,
    answer = A(...) 정답 토글 — stage에 「구현 · 판단 · 요구」가 든 단계는 반드시 둔다(가이드.md P-3)."""
    return dict(name=name, stage=stage, do=do, ask=ask, hint=hint, cmd=cmd, evidence=evidence, why=why, differ=differ, run=run, answer=answer)


# ───────────── 단계 · 가이드 공용 문장 ─────────────
STAGE_LINE = '줄기(온톨로지 → 에이전트 → 프로세스)에서 이 실습은 첫 단계 온톨로지의 {what}를 맡습니다.'
STEP_INTRO = ('한 번에 한 단계씩 갑니다. 단계마다 결과를 확인한 뒤 다음 단계로 갑니다. 단계마다 정하거나 물을 것, 요청에 담을 것, 판단할 증거는 '
              '가이드(ZIP을 풀면 이 폴더 옆에 있는 `_guide.html` 파일)의 같은 번호에 있습니다.')
SEVEN = '이 순서는 바이브 코딩 일곱 단계 — 파일을 바꾸지 않고 파악 → 요구와 기대 답을 내 말로 → 계획 검토 → 작게 구현 → 원자료와 대조 → 고침 → 저장하고 다시 열기 — 를 따릅니다.'
BACKTICK = '요청에 파일 이름을 쓸 때는 `결과/schema.json`처럼 백틱(`)으로 감쌉니다. 채팅 입력이 밑줄(_)을 서식으로 바꾸기 때문입니다.'
DECIDE_INTRO = ('원자료만으로 하나로 정해지지 않아 내가 근거를 찾아 정할 지점입니다. 해당하는 행 · 절은 직접 찾고, '
                '지점마다 고른 것 · 근거(파일:줄) · 바뀌는 답을 `결과/정한_것.csv`에 한 줄씩 적습니다.')
DECIDE_AI = 'AI에게 이 지점을 정하게 하지 않습니다. AI가 고르거나 「권장」을 붙여도 따르지 말고 원문 줄을 열어 내 선택과 근거를 말하며, 못 정하면 미결로 둡니다.'
ASK_DECIDE = '지점마다 내 선택과 근거를 정합니다. AI의 「권장」은 따르지 않고 원문 줄로 정하며, 못 정하면 미결로 적습니다.'
EVIDENCE_LOOK = '짚은 줄을 열면 그 내용이 있고, AI가 바꾼 파일이 없습니다.'
FIX_LOOP = '입력 · 기대 · 실제를 AI에게 전해 고친 뒤 다시 확인합니다.'
REQ_AFTER = ' 다 적으면 AI에게 파일을 바꾸지 말고 되짚게만 합니다.'
REQ_EVIDENCE = ('기대 답마다 파일:줄이 있고, `결과/정한_것.csv`에 지점마다 고른 것 · 근거 · 바뀌는 답(또는 미결)이 있으며, AI가 바꾼 파일이 없습니다.')
WHY_START = '무엇이 주어졌고 이 답을 누가 쓰는지 알아야 AI에게 같은 출발점을 말할 수 있습니다.'
DIFFER_START = '보일 자리가 없으면 다른 실습이거나 덜 풀린 것이니 노션 「가이드문서」에서 ZIP을 다시 받아 풉니다.'
DIFFER_LOOK = '짚은 줄이 없거나 다르면 근거로 쓰지 않고 다시 찾게 합니다. 편집 승인 창이 뜨면 **Deny**를 누릅니다.'
WHY_REQ = ('기대 답을 원자료에서 먼저 적어야 결과를 견줄 기준이 생깁니다. AI의 답을 옮기면 틀린 결과도 맞아 보입니다.')
DIFFER_REQ = 'AI의 되짚기가 내 뜻과 다르면 `{rec}`를 고쳐 다시 되짚게 하고, 근거를 못 찾은 답은 미확인으로 둡니다.'
DIFFER_PLAN = '계획으로 답할 수 없는 질문이 있으면 그 질문을 들어 계획을 고쳐 달라고 한 뒤, 질문을 다시 하나씩 대어 봅니다.'
WHY_SAVE = '학교 PC는 재부팅하면 초기화될 수 있어, 다시 열어 같은 결과가 나와야 저장된 것입니다.'
DIFFER_SAVE = '단계 띠나 대조 표가 다르면 탭 이름 옆 ●가 남은 파일을 저장하고 다시 실행합니다.'
WHY_TABLE = 'RETURN에 속성 값을 돌려주면 표(Table)로 보여 원자료와 줄마다 견주기 쉽고, 노드를 돌려주면 그래프로 보입니다.'
PYCACHE = '(파이썬이 코드를 실행하며 저절로 만드는 `__pycache__` 폴더는 괜찮습니다)'
OWN_RUN = ' 실행은 내가 터미널에서 하고, AI가 답에 옮겨 적은 출력이 아니라 터미널에 나온 출력과 결과 화면으로 확인합니다 — 옮겨 적은 글은 실제 출력과 다를 수 있습니다.'
USB = '재부팅 전에 이 폴더를 USB나 개인 클라우드에 복사합니다(자동으로 되살리지 않음).'
COMPLETED_NOTE = 'AI 계정이 없거나 정답을 보고도 막히면 따로 받는 학생용 완성본으로 결과를 봅니다.'
GUIDE_HOW = ('단계마다 「요청에 담을 것」 다섯 칸을 내 말로 채워 AI에게 요청하고(그대로 보내는 글이 아니며, 값은 원자료에서 찾습니다), '
             '「증거」를 확인한 뒤 다음 단계로 갑니다. 막히면 「정답 보기」를 펼칩니다.')
SHOW_CMD = 'python show_result.py'


def req_hint(rec, look_step, cells):
    """요구 단계의 힌트. 기록은 학생이 편집기에서 직접 쓰고 AI는 파일을 바꾸지 않고 되짚기만 한다."""
    return H('내가 적은 요구를 AI가 같은 뜻으로 이해했는지 되짚게 한다',
             f'내가 채운 `{rec}` · `{CHOSEN_FILE}`, {look_step}단계에서 연 근거 줄',
             f'파일을 바꾸지 않는다 — `{rec}`와 `{CHOSEN_FILE}`는 내가 편집기에서 채운다. 기대 답은 내가 원자료에서 찾은 값이다(AI의 답을 옮기지 않는다). 「학생이 정할 것」은 내가 고른다.',
             f'내가 채운 칸({cells})을 AI가 자기 말로 다시 말한 것과, 근거 줄이 맞지 않거나 두 갈래로 읽히는 문장의 목록',
             '되짚기가 내 뜻과 다른 곳과 짚인 문장을 내가 편집기에서 고친다')


def req_template(record_title, extra_sections=''):
    """기록 md 빈 틀. 「정한 것」은 결과/정한_것.csv 한 곳에 적는다(계약 5)."""
    return (f'# {record_title}\n\n> {MARK}입니다. 보관하지 말고 바로 채웁니다.\n\n## 목표와 질문\n\n## 이 답을 쓰는 사람과 쓰는 곳\n\n## 사용할 자료와 기준일\n\n## 지킬 조건\n\n'
            f'## 정한 것\n\n고른 것 · 근거(파일:줄) · 바뀌는 답은 `{CHOSEN_FILE}`에 적습니다.\n\n'
            '## 기대 답과 실제 결과\n\n| 질문 · 물은 대상 | 원자료에서 먼저 찾은 기대 답(파일:줄) | 실제 결과 | 고친 점 · 다시 확인 |\n|---|---|---|---|\n| | | | |\n\n'
            + extra_sections +
            '## 저장 기록\n\n- 기준일:\n- 저장 시점:\n- 확인하지 못한 점:\n')


# ───────────── 도구 첫 사용 안내(가이드 그 단계에) ─────────────
# 화면 글자는 실제 화면 · 코드에서 나온 것만: 신뢰 창 영어 = VS Code 문서, 편집 승인 창 · Codex/Chat 탭 = 리허설 화면,
# Neo4j Browser 5.26 = 리허설_04_통합_실습3.md 「부족했던 곳」 2(Run 단추, 안내 풍선 · 광고 창), 오류 줄 = lab_db.py · check.py 출력.
TOOL = {
    '통합반': dict(
        get=('노션 「가이드문서」에서 이 실습의 **ZIP 내려받기**를 눌러 받고, 받은 ZIP을 오른쪽 버튼으로 눌러 **압축 풀기**(Extract All)를 고릅니다. '
             '풀린 폴더를 따라 들어가면 실습 폴더와 이 가이드(이름이 `_guide.html`로 끝나는 파일)가 나란히 있습니다. 가이드는 두 번 눌러 브라우저로 열고, '
             'VS Code에서는 **파일 → 폴더 열기**(File → Open Folder)로 **실습 폴더**를 엽니다 — 그 위 폴더를 열면 AI가 정답이 든 이 가이드까지 읽습니다. '
             '이어서 할 때는 같은 실습 폴더를 다시 엽니다(ZIP을 새로 풀면 고친 파일이 없는 새 폴더입니다).'),
        trust='처음 열 때 폴더를 신뢰할지 물으면 **Yes, I trust the authors**를 누릅니다 — **제한 모드**(Restricted Mode)에서는 AI 채팅이 동작하지 않습니다.',
        explorer='왼쪽 **탐색기**(Explorer)에서 폴더 이름을 보고 START.md를 엽니다(CSV는 누르면 표 글자가 보입니다).',
        ai=('AI 채팅은 왼쪽 **활동 표시줄**의 Codex 아이콘(GitHub Copilot은 같은 창의 **Chat** 탭)으로 엽니다. '
            '답에 나온 파일 · 줄은 편집기에서 직접 열어 보고, 「완료」라는 말 대신 실제 파일과 출력으로 확인합니다.'),
        card='AI가 이 지점을 물으며 「(권장)」을 붙인 선택지 카드를 내도 추천일 뿐입니다. 근거 줄을 연 뒤 직접 입력 칸에 내 결정과 근거 줄을 적어 보냅니다.',
        save='편집기에서 고친 뒤 **Ctrl+S**로 저장합니다(탭 이름 옆 ●가 사라지면 저장됨).',
        terminal=('**터미널 → 새 터미널**(Terminal → New Terminal)로 이 실습 폴더에서 터미널을 엽니다. 명령은 직접 치지 말고 블록의 **복사**로 붙여 넣은 뒤 Enter를 누릅니다(손으로 치면 오타가 납니다). '
                  '오류로 멈추면 명령과 출력 전문을 AI 채팅에 보내 까닭부터 묻습니다. 명령은 AI가 아니라 이 터미널에서 내가 실행합니다.'),
        result=('**결과 화면** `python show_result.py`가 `결과/보기.html`을 새로 쓰고 처음 한 번 브라우저로 엽니다(안 열리면 탐색기에서 그 파일을 오른쪽 클릭 → **Reveal in File Explorer** → 두 번 클릭). '
                '단계 띠의 「비어 있음 · 채움 · 오류」를 보고, 다시 실행한 뒤 **F5**를 누릅니다. 빨간 칸에는 멈춘 파일:줄과 까닭이 있습니다.'),
        review='편집 승인 창(Allow ChatGPT to edit…?)에서는 경로가 `결과/` 아래인 요청한 변경만 **Allow once**, 그 밖은 **Deny**를 누르고 까닭을 알립니다.',
        run_approve='AI가 Docker · 랩 DB 명령을 실행하려 하면 폴더 밖 실행 승인 창이 뜹니다. **Deny**를 누르고 그 명령을 내 터미널에서 실행합니다.',
        docker='랩 DB는 Docker로 켜므로 Docker Desktop을 먼저 켭니다. 처음 한 번은 DB 이미지를 받느라 오래 걸립니다.',
        db=('「랩 DB 준비 완료」 뒤 열린 Neo4j Browser 연결 창에서 **Connection URL**이 출력의 127.0.0.1:포트인지 보고, **Database user** neo4j · **Password**는 비운 채(이 PC 안에서만 열리는 DB) **Connect**를 누릅니다. '
            '안내 풍선은 **Esc**로 닫고, 입력 칸에 Cypher를 붙여 넣어 **Run**, 표는 **Table**로 봅니다.'),
        db_stuck=('**막히면** 「랩 DB 준비 확인 필요:」는 Docker Desktop을 켜고 다시 실행합니다. 「이 PC의 Docker에 없습니다」 뒤 「랩 DB 준비 완료」는 이 폴더 전용 랩 DB를 새로(빈 채로) 만든 것입니다.'),
        check_stop='**막히면** 「아직 검사할 결과가 없습니다」는 오류가 아니라 결과 파일이 아직 없다는 뜻입니다 — 단계 띠에서 비어 있는 단계를 먼저 채웁니다.'),
    '실전반': dict(
        get=('노션 「가이드문서」에서 이 실습의 ZIP을 받아 압축을 풀면, 풀린 폴더 안에 실습 폴더와 이 가이드가 나란히 있습니다. '
             '가이드는 브라우저로, 실습 폴더는 VS Code의 **파일 → 폴더 열기**(File → Open Folder)로 엽니다 — 그 위 폴더를 열면 AI가 정답이 든 가이드까지 읽습니다. '
             '이어서 할 때는 같은 실습 폴더를 다시 엽니다.'),
        trust='처음 열 때 폴더를 신뢰할지 물으면 신뢰합니다 — **제한 모드**(Restricted Mode)에서는 AI 채팅이 동작하지 않습니다.',
        explorer='왼쪽 **탐색기**(Explorer)에서 폴더 이름을 확인하고 START.md를 엽니다.',
        ai=('Codex는 왼쪽 **활동 표시줄**의 Codex 아이콘으로, GitHub Copilot은 같은 채팅 창의 **Chat** 탭으로 엽니다. '
            '답에 나온 줄은 편집기에서 직접 열어 읽고, 「완료」라는 말 대신 실제 파일과 출력으로 확인합니다.'),
        card='질문 카드의 「(권장)」은 AI의 추천일 뿐이니, 직접 입력 칸에 내 결정과 근거 줄을 적어 보냅니다.',
        save='고친 파일은 **Ctrl+S**로 저장합니다(탭 이름 옆 ●가 사라지면 저장됨).',
        terminal=('**터미널 → 새 터미널**(Terminal → New Terminal)로 이 실습 폴더에서 터미널을 엽니다. 명령은 직접 치지 말고 블록의 **복사**로 붙여 넣습니다(손으로 옮기면 오타가 납니다). '
                  '오류로 멈추면 명령과 출력 전문을 AI 채팅에 보내 까닭부터 묻습니다. 명령은 AI 채팅이 아니라 이 터미널에서 내가 실행합니다.'),
        result=('**결과 화면 여는 법** `python show_result.py`가 `결과/보기.html`을 새로 쓰고 처음 한 번 브라우저로 엽니다(안 열리면 탐색기에서 그 파일을 오른쪽 클릭 → **Reveal in File Explorer** → 두 번 클릭). '
                '단계 띠의 「비어 있음 · 채움 · 오류」를 보고, 다시 실행한 뒤 **F5**를 누릅니다.'),
        review='편집 승인 창(Allow ChatGPT to edit the following file?)에서는 경로가 `결과/` 아래인 요청한 변경만 **Allow once**, 그 밖은 **Deny**를 누릅니다.',
        run_approve='AI가 Docker · 랩 DB 명령을 실행하려 하면 폴더 밖 실행 승인 창이 뜹니다. **Deny**를 누르고 그 명령을 내 터미널에서 실행합니다.',
        docker='명령 전에 Docker Desktop을 켜 둡니다.',
        db=('「랩 DB 준비 완료」 뒤 열린 연결 창에서 **Protocol** bolt://, **Connection URL**은 출력의 127.0.0.1:포트, **Database user** neo4j, '
            '**Password**는 비운 채(이 PC 안에서만 열리는 DB라 비밀번호가 없습니다) **Connect**를 누릅니다. 안내 풍선 · 광고 창은 **Esc**로 닫고, 입력 칸에 Cypher를 붙여 넣어 **Run**, **Table**로 원자료와 견줍니다.'),
        db_stuck=('**막히면** 「랩 DB 준비 확인 필요:」 줄이 나오면 Docker Desktop이 켜져 있는지 보고 다시 실행합니다. '
                  '「이 PC의 Docker에 없습니다」 줄은 다른 PC에서 옮겨 온 폴더이거나 DB가 지워져 새 빈 랩 DB를 만들었다는 뜻입니다.'),
        check_stop='**막히면** 「아직 검사할 결과가 없습니다」는 오류가 아니라 결과 파일이 아직 그 자리에 없다는 뜻입니다 — 결과 화면에서 비어 있는 단계를 먼저 채웁니다.'),
}


# ───────────── 복사 블록 · 쪽 ─────────────
BLOCK_KIND = {
    'term': ('터미널(PowerShell · 이 실습 폴더)', 'VS Code 아래쪽 터미널', '붙여 넣고 Enter를 누르세요'),
    'term_tpl': ('터미널(PowerShell · 이 실습 폴더) — <…>는 내 파일 이름 · 물을 값으로', 'VS Code 아래쪽 터미널', '붙여 넣은 뒤 <…> 자리를 바꾸고 Enter를 누르세요'),
    'cypher': ('Neo4j Browser 입력 칸', 'Neo4j Browser 위쪽 입력 칸', '붙여 넣고 Run을 누르세요'),
    'cypher_tab': ('Neo4j Browser 새 쿼리 탭에 붙여 넣는 글', 'Neo4j Browser 새 쿼리 탭', '붙여 넣으세요'),
    'shell': ('PowerShell · 이 실습 폴더', 'PowerShell 창', '붙여 넣고 Enter를 누르세요'),
    'paste': ('붙여 넣는 내용 · VS Code 편집기에서 — {target}', 'VS Code 편집기의 {target}', '붙여 넣고 Ctrl+S로 저장하세요'),
    'ask_ai': ('AI 채팅에 붙여 넣는 글', 'AI 채팅 입력 칸', '붙여 넣고 보내세요'),
    'tree': ('탐색기 모양', '', '')}
STEP_CSS = ('.block{border:1px solid #c9d6cf;border-radius:10px;margin:14px 0;overflow:hidden}.block .kind{margin:0;padding:6px 14px;font-size:14px;font-weight:bold}'
            '.block pre{margin:0;border-radius:0}.block.term .kind,.block.term_tpl .kind,.block.shell .kind{background:#26323b;color:#f2f5f3}.block.cypher .kind,.block.cypher_tab .kind{background:#e3ebf8;color:#1d3f75}'
            '.block.paste .kind{background:#efe6f8;color:#4b2a73}.block.ask_ai .kind{background:#e6f3f1;color:#14524a}'
            '.block.tree .kind{background:#eef1ee;color:#4b5c55}.block .copy{margin:8px 14px;padding:3px 14px;border:1px solid #176554;background:white;color:#176554;border-radius:6px;cursor:pointer;font:inherit;font-size:14px}'
            '.block .copied{font-size:14px;color:#176554}.hint{border:1px solid #e3d6b0;background:#fffaf0;border-radius:10px;padding:2px 16px 12px;margin:14px 0}.hint .kind{font-weight:bold;color:#7a5a12;margin:10px 0 0}'
            'details.answer{border:1px solid #b9a3d6;border-radius:10px;margin:14px 0;padding:8px 16px;background:#fbf8ff}details.answer summary{font-weight:bold;color:#4b2a73}')
COPY_JS = ('<script>document.querySelectorAll(".block .copy").forEach(function(b){b.addEventListener("click",function(){'
           'var p=b.parentNode.querySelector("pre"),m=b.parentNode.querySelector(".copied"),t=p.innerText;'
           'function say(x){m.textContent=x}'
           'function legacy(){var r=document.createRange(),s=window.getSelection(),ok=false;r.selectNodeContents(p);s.removeAllRanges();s.addRange(r);'
           'try{ok=document.execCommand("copy")}catch(e){}s.removeAllRanges();say(ok?b.dataset.done:b.dataset.fail)}'
           'if(!t.trim()){say(b.dataset.fail);return}'
           'if(navigator.clipboard&&window.isSecureContext){navigator.clipboard.writeText(t).then(function(){say(b.dataset.done)},legacy)}else{legacy()}})})</script>')


def block(kind, text, target=''):
    """복사 블록 하나. kind는 BLOCK_KIND의 키 — 읽기만 하는 블록(tree)에는 복사 단추가 없다."""
    label, where, then = (x.format(target=target) for x in BLOCK_KIND[kind])
    body = f'<div class="block {kind}"><p class="kind">{html.escape(label)}</p><pre><code>{html.escape(text)}</code></pre>'
    if not where:
        return body + '</div>'
    done = html.escape(f'복사했습니다. {where}에 {then}.', quote=True)
    fail = html.escape(f'복사가 막혔습니다. 블록의 글자를 끌어 선택하고 Ctrl+C로 복사해 {where}에 {then}.', quote=True)
    return body + f'<button type="button" class="copy" data-done="{done}" data-fail="{fail}">복사</button> <span class="copied" role="status"></span></div>'


def command_block(cmd):
    return block('term_tpl' if '<' in cmd else 'term', cmd)


def inline(text):
    """START와 같은 문장을 가이드에 쓴다: 백틱은 <code>, **굵게**는 <b>."""
    t = html.escape(text)
    t = re.sub(r'`([^`]+)`', r'<code>\1</code>', t)
    return re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', t)


def tree(name, rows):
    width = max(len(k) for k, _ in rows) + 2
    lines = [f'{name}/'] + [('└ ' if i == len(rows) - 1 else '├ ') + k.ljust(width) + v for i, (k, v) in enumerate(rows)]
    return '\n'.join(lines)


def answer_html(answer):
    """「정답 보기」 토글. 닫힌 채로 두고(사람 눈에만 숨김), 안에는 요지와 복사 블록."""
    inner = f'<p>{inline(answer["say"])}</p>' + ''.join(block(kind, text, target) for kind, target, text in answer['blocks'])
    return f'<details class="answer"><summary>정답 보기</summary>{inner}</details>'


def ai_turn(s):
    """학생이 AI에게 요청을 보내는 단계인가: 파악 · 요구 단계, 또는 정답이 코드(.py · .cypher)를 채우는 단계(AI와 짜는 판단 함수 · 문장).
    표만 편집기에서 쓰거나 다시 실행 · 대조만 하는 단계는 아니다(리허설 50L2 — 통합 02-3 루나 턴이 2 · 3 · 5 · 6 · 7 · 8단계)."""
    if '파악' in s['stage'] or '요구' in s['stage']:
        return True
    files = (s.get('answer') or {}).get('apply', {})
    return any(k.endswith(('.py', '.cypher')) for k in files)


def step_html(s, extra='', last=False, after=''):  # last는 부르는 쪽 꼴을 지키려고 둔다
    """단계 한 절. extra = 할 일 바로 뒤(그 단계에서 처음 쓰는 도구), after = 명령 뒤(실행한 다음 볼 화면 · 막혔을 때)."""
    parts = [f'<p><b>왜</b> {inline(s["why"])}</p>' if s['why'] else '', f'<p><b>할 일</b> {inline(s["do"])}</p>', extra,
             f'<p><b>정할 것</b> {inline(s["ask"])}</p>']
    if s['hint']:
        rows_ = ''.join(f'<tr><th>{html.escape(k)}</th><td>{inline(v)}</td></tr>' for k, v in s['hint'].items())
        parts.append(f'<div class="hint{" ai" if ai_turn(s) else ""}"><p class="kind">요청에 담을 것</p><table>{rows_}</table></div>')
    if s.get('answer'):
        parts.append(answer_html(s['answer']))
    if s['run']:
        parts.append(f'<p><b>실행</b> {inline(s["run"])}</p>' + (command_block(s['cmd']) if s['cmd'] else ''))
    elif s['cmd']:
        parts.append(command_block(s['cmd']))
    else:
        parts.append('<p><b>명령</b> 없음</p>')
    parts.append(after)
    check = f'<b>증거</b> {inline(s["evidence"])}'
    if s['differ']:
        check += f'<br><b>다를 때</b> {inline(s["differ"])}'
    parts.append(f'<p class="check">{check}</p>')
    return ''.join(parts)


def step_page(title, lead, sections):
    """단계 랩 가이드 한 쪽. 절 머리(<section id="sN"><h2>NN 이름</h2>)는 verify_packages가 단계 이름을 읽는 꼴."""
    nav = ''.join(f'<a href="#s{i}">{i:02d} {html.escape(t)}</a>' for i, (t, _) in enumerate(sections, 1))
    body = ''.join(f'<section id="s{i}"><h2>{i:02d} {html.escape(t)}</h2>{content}</section>' for i, (t, content) in enumerate(sections, 1))
    return (f'<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title>'
            f'<style>{GUIDE_CSS}{STEP_CSS}</style><main><small>HYD · 실습 가이드</small><h1>{title}</h1><p>{lead}</p><p><b>진행 순서</b></p><nav>{nav}</nav>{body}</main>{COPY_JS}</html>')


def needs_answer(s):
    return any(x in s['stage'] for x in ANSWER_STAGES)


def step_guide(L, photos=None):
    """L = 랩 정의(dict). 키: title · course · goal · lead · need · tree · user · questions · terms · decide · decide_step · steps · reopen · save ·
    guide_extra({단계 번호(0부터): [TOOL 키 또는 HTML 조각]}) · guide_after(같은 꼴) · first_more(선택) · tools_from(선택 — 한 칸의 앞 랩 제목). photos는 아직 쓰지 않는다(None)."""
    if photos:
        raise ValueError(f'{L["title"]}: 가이드를 폴더 밖으로 옮긴 뒤 사진을 싣는 길은 아직 없습니다 — 사진 없이 만들거나 길을 먼저 정합니다.')
    missing = [i for i, s in enumerate(L['steps'], 1) if needs_answer(s) and not s.get('answer')]
    if missing:
        raise ValueError(f'{L["title"]}: 정답 토글이 없는 구현 · 판단 단계 {missing} — S(..., answer=A(...))를 채웁니다(가이드.md P-3).')
    T = TOOL[L['course']]
    if L.get('tools_from'):   # 한 칸에 이어 하는 둘째 랩 — 도구 사용법은 앞 가이드에서 읽었으므로 되풀이하지 않는다(사용자 2026-11-05 「가치 위주」)
        how = (f'<p><b>받기 · 도구</b> 노션 「가이드문서」에서 이 실습의 ZIP을 받아 풀고 실습 폴더를 VS Code로 엽니다. 받기 · 폴더 신뢰 · 탐색기 · 터미널 · 결과 화면 · AI 채팅 · 편집 승인 창은 '
               f'「{html.escape(L["tools_from"])}」 가이드와 같습니다. 명령은 직접 치지 말고 블록의 <b>복사</b>로 붙여 넣습니다. <b>필요한 것</b> {inline(L["need"])}</p>')
    else:
        how = f'<p><b>받기</b> {inline(T["get"])} <b>필요한 것</b> {inline(L["need"])}</p>'
    first = (''.join(f'<p>{inline(x)}</p>' for x in L['goal']) + how + block('tree', L['tree'])
             + (f'<p>{inline(COMPLETED_NOTE)}</p>' if L.get('tools_from') else f'<p>{inline(T["trust"])} {inline(T["explorer"])} {inline(COMPLETED_NOTE)}</p>'))
    # 질문 · 말 풀이는 첫 단계의 「할 일」 바로 뒤에 둔다 — 첫 화면에 설명을 몰아 두지 않고, 그 단계에서 확인하는 것 옆에 놓는다(의뢰_구현50 3절)
    asked = (f'<p><b>해결할 질문</b> {inline(L["user"])}</p><ol>' + ''.join(f'<li>{inline(q)}</li>' for q in L['questions']) + '</ol>'
             + f'<p><b>말 풀이</b> {inline(L["terms"])}</p>' + ''.join(f'<p>{inline(x)}</p>' for x in L.get('first_more', [])))
    decide = ('<p><b>학생이 정할 것 — 지점의 종류</b> ' + inline(DECIDE_INTRO) + '</p><ul>'
              + ''.join(f'<li><b>{html.escape(k)}</b> — {inline(v)}</li>' for k, v in L['decide']) + f'</ul><p>{inline(T["card"])}</p>')

    def joined(spec):
        return {i: ''.join((f'<p>{inline(T[k])}</p>' if k in T else k) for k in keys) for i, keys in spec.items()}
    extras, afters = joined(L['guide_extra']), joined(L.get('guide_after', {}))
    extras[0] = asked + extras.get(0, '')
    extras[L['decide_step']] = extras.get(L['decide_step'], '') + f'<p>{inline(T["save"])}</p>' + decide
    sections = []
    for i, s in enumerate(L['steps']):
        last = i == len(L['steps']) - 1
        body = (first if i == 0 else '') + step_html(s, extras.get(i, ''), last, afters.get(i, ''))
        if last:
            body += (f'<p><b>저장 위치</b> 이 실습 폴더의 <code>결과/</code></p><p><b>다시 열어 볼 것</b> {inline(L["reopen"])}</p>'
                     f'<p><b>다음 실습에 넘길 판본</b> {inline(L["save"])}</p>')
        sections.append((s['name'], body))
    lead = inline(L['lead'] + ' ' + GUIDE_HOW)
    return step_page(L['title'], lead, sections)


def step_start(L):
    """START.md. L 키: title · goal · make · start · tools(선택) · user · questions · decide · outside · formats · steps · cases · commands · readonly · done · save."""
    b = [f'# {L["title"]}', '## 목표', *L['goal'], L['make'], '## 출발점', '\n'.join('- ' + x for x in L['start'])]
    if L.get('tools'):
        b += ['## 처음 쓰는 도구', '\n'.join('- ' + x for x in L['tools'])]
    b += ['## 해결할 질문', L['user'], '\n'.join(f'{i}. {q}' for i, q in enumerate(L['questions'], 1)),
          '## 학생이 정할 것', DECIDE_INTRO, '\n'.join(f'- **{k}** — {v}' for k, v in L['decide']), DECIDE_AI,
          '## 이번 범위 밖', '\n'.join('- ' + x for x in L['outside']) + '\n\n자료에 있어도 이번 결과에 만들지 않습니다.',
          *[f.strip() for f in L['formats']],
          '## 진행 단계', STEP_INTRO, '\n'.join(f'{i}. **{s["name"]}** — {s["do"]}' for i, s in enumerate(L['steps'], 1)), SEVEN, BACKTICK,
          '## 확인', '확인할 사례의 종류(어느 행이 해당하는지는 원자료에서 직접 찾습니다):', '\n'.join('- ' + x for x in L['cases']),
          '실행 명령:', '```\n' + L['commands'] + '\n```',
          f'바뀐 파일 확인: AI가 단계를 마칠 때마다 바뀐 파일 목록을 봅니다. {L["readonly"]} 바뀌지 않았는지, 요청하지 않은 파일이 생기지 않았는지 확인합니다. 편집 승인 창에서는 경로가 `결과/` 아래일 때만 허용합니다.',
          '## 완료 판정', L['done'], '## 저장과 다음 실습', L['save']]
    return '\n\n'.join(b) + '\n'


# ───────────── 가이드 자리(랩 폴더 밖) ─────────────
GUIDE_SUFFIX = '_guide.html'
LEGACY_GUIDES = ('guide.html', '안내.html')


def guide_path(lab_folder):
    """`산출물/<과정>/실습/NN회차/랩/<랩 폴더 이름>_guide.html` — 랩 폴더 옆(공용틀_계약 2)."""
    lab_folder = Path(lab_folder)
    return lab_folder.parent/(lab_folder.name + GUIDE_SUFFIX)


def write_guide(lab_folder, text, ai_wait=None):
    """가이드를 랩 폴더 밖에 쓰고, 폴더 안의 옛 가이드(guide.html · 안내.html — 생성물)를 지운다. 사진 폴더가 있으면 멈춘다(옮길 길이 아직 없음).
    쓴 뒤 그 랩의 사람 환산 셈(guide_cost)을 한 줄 찍는다 — ai_wait = (분, 출처) 리허설 실측이 있으면 그 값."""
    lab_folder = Path(lab_folder)
    if (lab_folder/'images').exists():
        raise ValueError(f'{lab_folder}/images: 가이드를 폴더 밖에 둘 때 사진을 싣는 길이 아직 없습니다.')
    for name in LEGACY_GUIDES:
        (lab_folder/name).unlink(missing_ok=True)
    target = guide_path(lab_folder)
    write(target, text)
    print(cost_line(lab_folder, guide_cost(text, ai_wait)))
    return target


# ───────────── 사람 환산 셈(12랩 한 식 — 의뢰_구현50 3절) ─────────────
READ_PER_MIN, READ_SLOW, ROW_MIN, EVIDENCE_MIN, COMMAND_MIN, TURN_MIN = 500, 300, 0.3, 0.1, 0.5, 1.5   # 판정은 500(훑어 읽기), 300은 참고(꼼꼼히)


class _GuideText(html_parser.HTMLParser):
    """가이드에서 학생이 읽는 글만 모은다: 정답 토글 · 스크립트 · 스타일 · 복사 단추 · 사진은 뺀다. 명령 블록 · 요청 힌트 수와 토글 속 CSV 행도 센다."""
    HIDE = {'script', 'style', 'button', 'figure', 'img'}

    def __init__(self):
        super().__init__()
        self.stack, self.hidden, self.in_answer = [], 0, 0
        self.text, self.commands, self.hints, self.kind, self.code, self.rows, self.evidence = [], 0, 0, None, None, {}, {}

    def handle_starttag(self, tag, attrs):
        cls = (dict(attrs).get('class') or '').split()
        answer = tag == 'details' and 'answer' in cls
        hide = tag in self.HIDE or answer or (tag == 'span' and 'copied' in cls)
        self.stack.append((tag, hide, answer))
        self.hidden += hide
        self.in_answer += answer
        if tag == 'div' and 'block' in cls and not self.in_answer and {'term', 'term_tpl', 'cypher'} & set(cls):
            self.commands += 1
        if tag == 'div' and 'hint' in cls and 'ai' in cls and not self.in_answer:
            self.hints += 1
        if tag == 'p' and 'kind' in cls and self.in_answer:
            self.kind = ''
        if tag == 'code' and self.in_answer and self.kind:
            self.code = []

    def handle_endtag(self, tag):
        while self.stack:
            t, hide, answer = self.stack.pop()
            self.hidden -= hide
            self.in_answer -= answer
            if t == 'p' and self.kind is not None and self.code is None and t == tag:
                self.kind = self.kind.strip()
            if t == 'code' and self.code is not None:
                target = self.kind.split(' — ')[1].strip() if ' — ' in self.kind else ''
                if target.endswith('.csv'):
                    body = [x for x in ''.join(self.code).splitlines() if x.strip() and not x.lstrip().startswith('#')]
                    n = max(len(body) - 1, 0)
                    self.rows[target] = max(self.rows.get(target, 0), n)
                    if body and '근거' in [c.strip() for c in body[0].split(',')]:
                        self.evidence[target] = max(self.evidence.get(target, 0), n)
                self.code, self.kind = None, None
            if t == tag:
                break

    def handle_data(self, data):
        if self.code is not None:
            self.code.append(data)
        elif self.kind is not None and self.in_answer:
            self.kind += data
        if not self.hidden:
            self.text.append(data)


def guide_cost(guide_html, ai_wait=None):
    """사람 분 = max(보이는 글자 ÷ 500(판정 · 참고로 300도), AI 대기) + 손으로 쓰는 행 × 0.3 + 근거 줄을 열어 보는 행 × 0.1 + 명령 × 0.5(의뢰_구현50 3절 —
    강사가 AI를 기다리는 동안에도 설명하며 가고 가이드는 훑어 읽으므로 읽기와 AI 대기는 겹친다).
    보이는 글자 = 정답 토글 · 사진 · 복사 단추를 뺀 글을 공백 하나로 접어 센 수(이 정의는 여기 하나). 손 행 = 정답 토글이 채우는 정할 자리 · 기대 답 CSV의
    데이터 행(파일마다 한 번), 근거 행 = 그 가운데 「근거」 열이 있는 표의 행. 명령 = 토글 밖 터미널 · Cypher 블록 수.
    AI 대기 = 리허설 실측, 없으면 AI에게 요청하는 단계 수(ai_turn) × 1.5. 추정이다(사람 리허설로 재지 않음)."""
    p = _GuideText()
    p.feed(guide_html)
    chars = len(re.sub(r'\s+', ' ', ' '.join(p.text)).strip())
    rows, evidence = sum(p.rows.values()), sum(p.evidence.values())
    wait, source = ai_wait if ai_wait else (p.hints * TURN_MIN, f'루나 턴 {p.hints} × {TURN_MIN}')
    rest = rows * ROW_MIN + evidence * EVIDENCE_MIN + p.commands * COMMAND_MIN
    return {'글자': chars, '손_행': rows, '근거_행': evidence, '명령': p.commands, 'AI_대기': round(wait, 1), 'AI_대기_출처': source,
            '사람_분': round(max(chars / READ_PER_MIN, wait) + rest, 1), '사람_분_300': round(max(chars / READ_SLOW, wait) + rest, 1),
            '행_파일': dict(sorted(p.rows.items()))}


def cost_line(lab_folder, c):
    return (f'[사람 환산] {Path(lab_folder).name}: max(보이는 글자 {c["글자"]} ÷ {READ_PER_MIN}, AI 대기 {c["AI_대기"]}({c["AI_대기_출처"]}))'
            f' + 손 행 {c["손_행"]} × {ROW_MIN} + 근거 행 {c["근거_행"]} × {EVIDENCE_MIN} + 명령 {c["명령"]} × {COMMAND_MIN} = {c["사람_분"]}분'
            f' (참고: 분당 {READ_SLOW}자면 {c["사람_분_300"]}분)')


def write_provided(lab_folder, steps_source):
    """학생 폴더 루트의 제공 결과 화면 두 파일: show_result.py(12랩 같은 바이트) · lab_steps.py(이 랩)."""
    lab_folder = Path(lab_folder)
    write(lab_folder/'show_result.py', SHOW_RESULT)
    write(lab_folder/'lab_steps.py', steps_source)
