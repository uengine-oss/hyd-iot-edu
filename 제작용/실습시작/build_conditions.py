"""실전반 온라인2 조건표(현업화 판): 냉각 경보 사례 48건 원자료와 원문, 빈 결과 틀, 단계별 구조 검사, 학생용 안내.

원자료는 data_conditions.py가 만든다(3회차 판정 랩과 같은 묶음). 강사 완성 조건표는 reference/session3/rules.csv이며
다음 회차 실전 실습2의 입력/rules.csv로 그대로 들어간다. 계약에는 형식·뜻만 적는다.
"""
from build_labs import ROOT, OUT, page, write, dump, pack, RULES
from build_session3_judgement import TABLE_CONTRACT, RULES_CHECK, STEP_TIPS, DATA_INTRO, force_template
from data_conditions import build as build_data
from pathlib import Path
import hashlib
import json
import shutil

HERE = Path(__file__).resolve().parent
VERSION = '2026-10-28-conditions-v4-rh2'
folder = OUT/'실전반/실습/02회차/랩/02일차_실습5_조치조건표'
DOCS = ['HM-8_매뉴얼.md', '규칙_원문.txt', '작업기준.md', 'HI-01_보충매뉴얼.md', '수집_설명.md', 'targets.csv']
RAW = ['경보_목록.csv', 'PLC_상태_수신.csv', '팬_운전_카운터.csv', '예측_결과.csv']
# 옛 판(폴더 맨 위에 원자료·입력틀)의 파일. 새 판은 자료/·결과/로 옮겼다.
OBSOLETE = ['HM-8_매뉴얼.md', '규칙_원문.txt', '사례_입력.csv', '작업기준.md', '조건표_입력틀.csv', '판단기록_입력틀.md']

CHECK = r'''"""결과/조건표.csv의 구조 검사와 판단기록.md 기록 칸 확인. 의미 정답은 판정하지 않는다."""
from pathlib import Path
import csv, sys
root = Path(__file__).resolve().parent
''' + RULES_CHECK + r'''
with (root/'자료/targets.csv').open(encoding='utf-8-sig', newline='') as f:
    sop_ids = [r['sop_id'] for r in csv.DictReader(f)]
state, errs, n = check_rules(root/'결과/조건표.csv', sop_ids)
parts = [('조건표.csv', state, errs, f'규칙 묶음 {n}개' if n else '', True)]
for column, label in [('정한 내용', '사람이 정한 결정'), ('만드는 방법', '판단 입력'), ('판정', '사례 대조')]:
    empty, total = empty_rows(root/'결과/판단기록.md', column)
    if empty is None: parts.append(('판단기록.md', '없음', [], '', False)); break
    if total == 0 or empty == total: parts.append((f'판단기록.md {label}', '아직 비어 있음', [], f'「{column}」 칸을 채우세요', False))
    else: parts.append((f'판단기록.md {label}', '작성 중' if empty else '작성됨', [], f'행 {total}개 중 빈 칸 {empty}개' if empty else f'행 {total}개', False))
print('구조 검사 결과')
ok = report(parts)
left = unused_rules(root/'결과/조건표.csv', root/'자료/규칙_원문.txt', root/'결과/판단기록.md', '정한 결정')
if left: notes([f'규칙 발췌의 규칙 중 조건표.csv source_section에도, 판단기록.md 결정 표에도 이름이 없는 것: {", ".join(left)}. 옮기지 않기로 정했다면 그 이유를 결정 표에 적습니다.'])
kinds = missing_kinds(root/'결과/판단기록.md', '사례 종류', [('경계', ['경계']), ('복수 사유', ['복수']), ('값 없음', ['값 없음', '누락', '미확인']), ('적용 대상 밖', ['대상 밖']), ('결정에 따라 바뀌는 사례', ['결정', '갈래', '갈림'])])
if kinds: notes([f'START.md 사례 종류 중 판단기록.md 「사례 종류」 칸에서 찾지 못한 것: {", ".join(kinds)} (다른 말로 적었다면 그대로 두어도 됩니다).'])
print('구조 검사는 형식만 봅니다. 경계·적용 대상·출처가 원문과 맞는지, 사례 판정이 원자료와 맞는지는 판단기록.md에서 별도로 대조하세요.')
sys.exit(0 if ok else 1)
'''

START = '''# 작업 기준을 조치 조건표로 옮기기

쿨러 냉각 성능 상실 경보에서 검토하는 조치 후보 네 개(SOP-COOL-11~14)의 경고·감점·제외 조건을 원문에서 찾아 조치 조건표로 만들고, 실제 경보 사례에 대입해 판단의 근거를 확인합니다. 다음 회차에는 이 조건표로 경보 사례 전체의 조치 검토 결과를 만듭니다.

## 출발점

''' + DATA_INTRO + '''
- `입출력_계약.md`: 조건표의 형식. `check.py`: 단계별 구조 검사.

## 이번에 만들 결과

- `결과/조건표.csv`: 입력·단위·연산자·기준값·경계 포함 여부·결과(WARN/PENALTY/EXCLUDE)·원문 출처. 같은 규칙의 비교 여러 개는 한 묶음으로 둡니다.
- `결과/판단기록.md`: 원문만으로 정해지지 않아 사람이 정한 결정과 근거, 조건표의 각 입력을 원자료에서 만드는 방법, 사례 종류마다 하나 이상 고른 경보 사례의 대조(원자료 행·판단 입력·일치 규칙·판정·근거).

## 작업 순서

1. **탐색만 요청**: AI에게 파일을 바꾸지 말고 자료/를 읽어 원문 세 개와 규칙 발췌의 관계, 원천 자료 네 개의 모양(주기·단위·빈 값)을 설명하게 합니다. 설명은 실제 파일과 대조합니다.
2. **요구 정리**: 사용할 자료, 만들 결과, 추가하면 안 되는 조건, 확인할 사례를 자기 말로 판단기록.md 첫머리에 적습니다. 원문으로 정해지지 않는 점은 직접 원문을 읽어 정하고, 결정·근거·그 결정으로 결과가 바뀌는 사례를 적습니다.
3. **계획 검토**: 조건표를 만들 순서를 계획만 받습니다. 원문에 없는 기준값·조건을 추가하려는 부분이 없는지 봅니다.
4. **작은 단위로 만들기**: 규칙 하나씩 조건표에 옮기고 `python check.py`로 형식을 확인합니다. 모든 행에 원문 출처를 답니다.
5. **원자료와 대조**: 사례 종류마다 경보 사례를 골라 원자료 행에서 판단 입력을 확인하고 조건표에 대입합니다.
6. **수정 요청**: 다르면 해당 행, 원문 문장(기대), 지금 결과(실제)를 함께 주고 그 부분만 고치게 합니다.
7. **저장·재열기**: 저장한 파일을 다시 열어 확인합니다.

''' + STEP_TIPS + '''
## 확인할 사례 종류

- 경계: 기준값과 같은 값, 바로 위·아래 값(단위가 다른 원천 포함)
- 복수 사유: 경고·감점·제외가 함께 맞는 후보
- 값 없음: 원천에서 값이 비는 이유가 서로 다른 사례. 값이 빠졌어도 이미 확인된 제외 사유가 있는 경우
- 적용 대상 밖: 값이 비어 있어도 그 후보에는 해당 규칙이 적용되지 않는 경우
- 사람이 정한 결정에 따라 결과가 바뀌는 사례

경보 사례는 48건입니다. 종류에 맞는 사례를 찾는 일은 AI에게 원자료 조회를 맡기고, 찾은 행을 직접 열어 확인합니다.

## 학생이 정할 것

원문만으로 하나로 정해지지 않아 학생이 원문을 읽고 정하는 지점입니다. 어느 규칙·절이 해당하는지는 탐색에서 직접 찾고, 정한 내용·근거·바뀌는 사례를 `결과/판단기록.md` 결정 표에 적습니다. AI는 이 지점을 정하기 전에 학생에게 묻습니다.

- 규칙의 식(적용 대상 목록)과 설명 문장이 서로 다른 범위를 말하는 곳
- 규칙 발췌와 HM-8이 같은 내용을 다르게 적은 곳, 시드의 스킬 ID와 이번 후보 SOP ID를 무엇을 근거로 잇는지
- 원천 자료의 기록 방식이 두 가지로 읽히는 곳에서 판단 입력을 어떻게 만들지
- 규칙 발췌의 규칙 가운데 조건표에 옮기지 않을 규칙과 그 이유

## 이번 범위 밖

경보 사례 48건 전체를 판정하는 프로그램과 교육용 비교 계산(다음 회차), SOP 구조 작성, 실제 설비·평가 함수 실행. 사례 대조는 고른 사례를 조건표에 손으로 대입합니다.

## 실행

```
python check.py
```

`check.py`는 조건표 형식과 판단기록.md 칸을 확인하고, 규칙 발췌의 규칙 중 조건표와 결정 표 어디에도 이름이 없는 규칙, 판단기록.md에 아직 없는 사례 종류를 「참고」로 알려 줍니다.

## 완료 조건

- `python check.py`에서 조건표.csv가 통과합니다.
- 조건표의 각 행에서 원문 문장으로 돌아갈 수 있고, 규칙 발췌의 시드 출처와 HM-8 절을 구별했습니다.
- 판단기록.md에 사람이 정한 결정과 근거, 입력을 만드는 방법, 사례 종류마다 대조가 있습니다.
- 규칙 발췌의 규칙마다 조건표에 옮겼거나, 옮기지 않은 이유를 판단기록.md 결정 표에 적었습니다.
- 후보 유지와 작업 실행 승인을 구별했습니다. 실제 설비나 평가 함수는 실행하지 않았습니다.

## 저장

결과 파일을 다시 열고, 보관할 파일은 재부팅 전에 USB 또는 개인 클라우드로 복사합니다.

다음 회차에는 완성된 조건표로 경보 사례 전체의 조치 검토 결과를 만들고 매뉴얼 근거를 연결합니다. 이번 결과가 없어도 다음 실습은 제공 조건표로 시작할 수 있습니다.
'''

RECORD = '''# 판단 기록

> 제공 빈 틀입니다. 보관하지 말고 바로 채웁니다.

- 작업 폴더:
- 확인 시각:
- 작성한 파일:

## 요구 정리

## 사람이 원문으로 정한 결정

| 모호한 점 | 정한 내용 | 원문 근거(파일·절·문장) | 이 결정으로 결과가 바뀌는 사례 |
|---|---|---|---|
| | | | |

## 판단 입력을 원자료에서 만드는 방법

| 조건표 입력 | 원천 파일·열 | 만드는 방법(단위 환산 포함) | 값이 없다고 보는 경우와 이유 | 근거 |
|---|---|---|---|---|
| | | | | |

## 사례 대조

| 사례 | 사례 종류 | 후보 | 원자료 행과 판단 입력 | 일치 규칙 | 경고 | 감점(만원) | 제외 사유 | 미확인 | 판정 | 원문 근거 |
|---|---|---|---|---|---|---:|---|---|---|---|
| | | | | | | | | | | |

## 사례별 유지 후보(없으면 그 사유)

| 사례 | 유지 후보 | 유지 후보가 없으면 그 사유 |
|---|---|---|
| | | |

## 확인하지 못한 점
'''


def main():
    data, _ = build_data()
    for name in OBSOLETE:
        if (folder/name).exists():
            (folder/name).unlink()
    if (folder/'자료').is_dir():
        shutil.rmtree(folder/'자료')
    for name in DOCS + RAW:
        write(folder/'자료'/name, data[name])
    rules = RULES.replace('입력/와 자료/는 보존한다.', '자료/의 파일과 check.py는 보존한다.')
    rules = rules.replace('- DB 작업은 안내된 별도 랩 주소만 사용한다. 포털 DB와 시스템 파일을 수정하거나 전체 삭제하지 않는다.\n', '- 실제 설비·포털·업무 시스템을 호출하지 않는다. 이번 실습은 제공 파일만 읽는다.\n')
    if '자료/의 파일과 check.py는 보존한다.' not in rules or '실제 설비·포털·업무 시스템을 호출하지 않는다.' not in rules:
        raise RuntimeError('build_labs.RULES 문구가 바뀌어 조건표 랩 규칙을 조정하지 못했습니다(보존·DB 줄).')
    rules += '- 원문만으로 정해지지 않는 점은 학생이 정한다. 학생에게 묻거나 미결로 표시하고 임의로 정하지 않는다.\n'
    for filename in ['AGENTS.md', 'CLAUDE.md', '.github/copilot-instructions.md']:
        write(folder/filename, rules)
    write(folder/'START.md', START)
    write(folder/'입출력_계약.md', '# 조치 조건표의 계약\n\n조건표는 다음 회차의 판정 기능이 그대로 읽는 입력이다. 열 이름을 바꾸면 다음 단계에서 읽지 못한다. 이 문서는 형식과 뜻만 정한다. 무엇을 어느 후보에 적용할지는 원문에서 정한다.\n\n' + TABLE_CONTRACT.replace('rules.csv', '결과/조건표.csv') + '\n## 원본과 결과\n\n자료/는 보존한다. 결과는 결과/에만 쓴다. 실제 설비·평가 함수를 실행하지 않는다.\n')
    write(folder/'check.py', CHECK)
    write(folder/'결과/README.md', '조건표.csv와 판단기록.md를 여기에 작성합니다.\n')
    force_template(folder/'결과/조건표.csv', 'rule_id,action,condition_index,logic,input,operator,value,unit,boundary_included,result,penalty_만원,reason,source_section\n', ['boundary_included'])
    force_template(folder/'결과/판단기록.md', RECORD, ['판단 입력을 원자료에서 만드는 방법', '제공 빈 틀'])
    sections = [
        ('자료 읽기', '<p>VS Code에서 이 폴더를 열고 <a href="START.md">START.md</a>와 <a href="입출력_계약.md">입출력_계약.md</a>를 읽으세요.</p><pre>자료/   HM-8 매뉴얼, 규칙 발췌, 작업기준, HI-01, 수집 설명, 대상 후보\n        경보 사례 48건의 원자료 4종(경보 목록, PLC 상태, 팬 카운터, 예측 결과)\n결과/   이번에 만들 조건표.csv, 판단기록.md\ncheck.py   단계별 구조 검사</pre><p>원자료는 수업용 시뮬레이터 로직으로 만든 교육용 가상 자료입니다. 원천마다 수집 주기·단위가 다르고 값이 비는 이유도 다릅니다. 먼저 AI에게 <b>파일을 바꾸지 말고</b> 자료를 설명하게 하고, 그 설명을 실제 파일과 대조하세요. 파일 이름은 백틱(`)으로 감싸 적습니다.</p>'),
        ('조건표 만들기', '<p>AI에 목표·자료·제약·확인 사례를 자기 말로 전달하고 계획을 먼저 받으세요. 규칙 하나씩 결과/조건표.csv에 옮기고 <code>python check.py</code>로 형식을 확인합니다.</p><p>입력, 연산자, 기준값, 단위, 경계 포함 여부, 결과, 원문 근거를 나누세요. 여러 비교가 한 규칙을 이루면 같은 규칙 번호로 묶습니다.</p><p class="check">이번 실습의 판단 지점: 규칙의 식과 설명 문장, 규칙 발췌와 HM-8, 원천 자료의 기록 방식이 서로 다른 답을 주는 곳이 있습니다. 그런 곳은 <b>사람이 원문을 읽고 정해</b> 판단기록.md에 결정·근거·바뀌는 사례를 적습니다. AI가 질문 카드로 물으면 「(권장)」은 추천일 뿐이니 원문 절을 직접 열어 확인하고 고릅니다. <code>python check.py</code>가 「옮기지 않은 규칙」을 알려 주면, 옮기거나 옮기지 않는 이유를 결정 표에 적습니다.</p>'),
        ('사례 대조하기', '<p>사례 종류마다 경보 사례를 고르고, 판단기록.md에 원자료 행·판단 입력·일치 규칙·판정을 적으세요. 조건표 입력을 원자료에서 만드는 방법도 표로 남깁니다.</p><p class="check">경계값 바로 아래·같은 값·바로 위에서 판단이 원문과 맞는지 확인합니다. 여러 사유는 모두 남기며 감점은 규칙당 한 번만 반영합니다. 값이 없는 규칙은 왜 없는지와 함께 미확인으로 남기고, 알려진 제외 사유는 지우지 않습니다.</p><p>AI가 완료를 알리면 실행한 명령과 출력 원문을 붙여 달라고 요청합니다.</p>'),
        ('저장하고 다시 읽기', '<p>조건표의 각 행에서 원문 절을 찾을 수 있는지 확인하세요. 조건표.csv와 판단기록.md를 저장하고 다시 엽니다.</p><p>후보 유지는 실행 승인이 아닙니다. 이번 실습에서는 표와 기록만 작성합니다.</p><p>보관할 결과는 USB 또는 개인 클라우드에 복사하세요.</p><p>다음 회차에는 완성된 조건표로 경보 사례 전체의 조치 검토 결과를 만들고 매뉴얼 근거를 연결합니다.</p>')]
    for filename in ['guide.html', '안내.html']:
        write(folder/filename, page('조치 조건과 판단 근거 정리하기', '원문 조건을 조치 조건표로 옮기고, 경보 사례의 원자료로 경계값·겹치는 조건·값 없음을 확인합니다.', sections))
    archive = pack(folder)
    catalog = json.loads((HERE/'package-index.json').read_text(encoding='utf-8'))
    catalog['labs'] = [x for x in catalog['labs'] if x['id'] != 'practical-02-conditions']
    catalog['labs'].append({'id': 'practical-02-conditions', 'course': '실전반', 'session': '온라인 02회차', 'title': '조치 조건과 판단 근거 정리하기', 'version': VERSION, 'folder': '02회차/랩/'+folder.name, 'path': archive.relative_to(ROOT).as_posix(), 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()})
    dump(HERE/'package-index.json', catalog)
    print('실전반 조건표 가이드·독립 ZIP·목록 동기화')


if __name__ == '__main__':
    main()
