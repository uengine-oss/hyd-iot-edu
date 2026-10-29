"""강사 참조 실습5 전체 실행: 빈 랩 DB에서 모델 적재 → 지식 적재 → 재적재 → 카드(두 판단 갈래) → 조회 → 형식 검사.
이 폴더에는 학생 시작본(`산출물/실전반/실습/03회차/랩/03일차_실습5_그래프반영/`)과 다른 파일만 있다. 학생 시작본 사본 위에 이 폴더를 덮은
작업 폴더에서 먼저 python lab_db.py --no-open 으로 그 폴더 전용 DB를 준비한다(빈 DB여야 수치가 맞다). 학생 배포 금지.
결과: 결과/실행기록.txt, 결과/구축_기록.md(학생 기록 틀을 참조 수치로 채운 것), 결과/갈래_비교.md
"""
from pathlib import Path
import json
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
PY = sys.executable
TASKS = ['SOP-COOL-14', 'SOP-PM-21', 'SOP-PM-22', 'T-3.1', 'T-4.1']
LOG = []


def run(*args):
    r = subprocess.run([PY, *args], cwd=HERE, capture_output=True, text=True, encoding='utf-8', errors='replace',
                       env={**__import__('os').environ, 'PYTHONUTF8': '1'})
    LOG.append(f'$ python {" ".join(args)}  (rc={r.returncode})\n{r.stdout}{r.stderr}')
    return r.returncode, r.stdout


def counts(out):
    m = re.search(r'전체 노드 (\d+)개, 관계 (\d+)개', out)
    kinds = re.search(r'종류별: (.*)', out).group(1)
    return int(m.group(1)), int(m.group(2)), kinds


def main():
    rc, out = run('lab_cypher.py', 'count')
    empty = counts(out)
    if empty[0]:
        raise SystemExit(f'빈 DB가 아닙니다(노드 {empty[0]}). 새 랩 DB에서 실행하세요.')
    run('make_load.py')
    report = json.loads((HERE / '결과/load_report.json').read_text(encoding='utf-8'))
    _, out = run('lab_cypher.py', 'model'); m1 = counts(out)
    _, out = run('lab_cypher.py', 'model'); m2 = counts(out)
    rc, out = run('lab_cypher.py', 'run', '결과/load.cypher')
    (HERE / '결과/load_1차.log').write_text(out, encoding='utf-8')
    created1 = out.count('created')
    _, out = run('lab_cypher.py', 'count'); l1 = counts(out)
    rc, out = run('lab_cypher.py', 'run', '결과/load.cypher')
    (HERE / '결과/load_2차.log').write_text(out, encoding='utf-8')
    created2 = len(re.findall(r'created|deleted', out))
    _, out = run('lab_cypher.py', 'count'); l2 = counts(out)
    cards = {}
    for t in TASKS:
        for label, extra in [('기본', []), ('지난시행_ID만', ['--match', 'strict', '--out', '결과/갈래_지난시행_ID만']), ('수량_PR07', ['--stock', 'pr07', '--out', '결과/갈래_수량_PR07'])]:
            rc, out = run('make_card.py', t, *extra)
            n = re.search(r'지난 시행 (\d+)건', out)
            cards[(t, label)] = int(n.group(1)) if n else None
    miss = {}
    for t in ['SOP-PM-24', '코어교체']:
        rc, out = run('make_card.py', t); miss[t] = rc
    run('make_query.py')
    rc, qout = run('lab_cypher.py', 'run', '결과/query.cypher')
    (HERE / '결과/query_결과.txt').write_text(qout, encoding='utf-8')
    blocks = re.split(r'-- \d+/\d+\n', qout)[1:]
    qrows = [int(re.search(r'\((\d+)행\)', b).group(1)) for b in blocks]
    loaded_bad = re.search(r'loaded_not_approved\n(\d+)', qout).group(1)
    _, out = run('lab_cypher.py', 'count'); l3 = counts(out)
    # 갈래 비교
    diff = ['# 판단 갈래 비교 — 실습5', '', '`python run_lab5.py`가 만든 파일. 같은 DB·같은 조회에서 학생이 정할 두 가지만 바꿨다.', '',
            '| 작업 | 지난 시행: 이름·약어 포함(기본) | 지난 시행: 절차 ID·구판 ID만 | 부품 수량: 현재고−예약(기본) | 부품 수량: PR-07 가용 재고 |', '|---|---|---|---|---|']
    for t in TASKS:
        def qty(folder):
            text = (HERE / folder / f'작업확인카드_{t}.md').read_text(encoding='utf-8')
            return '; '.join(re.findall(r'(P-[A-Z-]+) [^:]*: .*?→ (?:현재고−예약(?:\+입고 예정)?) = (-?\d+)', text) and
                             [f'{p} {n}' for p, n in re.findall(r'(P-[A-Z-]+) [^:]*: .*?→ (?:현재고−예약(?:\+입고 예정)?) = (-?\d+)', text)]) or '부품 없음'
        diff.append(f'| {t} | {cards[(t, "기본")]}건 | {cards[(t, "지난시행_ID만")]}건 | {qty("결과")} | {qty("결과/갈래_수량_PR07")} |')
    diff += ['', '- 지난 시행 범위를 절차 ID·구판 ID만으로 좁히면 절차 ID 없이 적힌 기록(예: SOP-COOL-14의 「쿨러 핀 막힘 - … 고압 세척기로 마무리」, SOP-PM-22의 「4000h PM - SOP-PM-21 1~6 + …」 PM-2.9 미달인데 완료로 닫힌 기록)이 카드에서 빠진다. 넓히면 그 기록이 들어오는 대신 이 절차를 따른 시행인지 확정할 수 없다는 남은 질문이 생긴다.',
             '- 부품 수량을 PR-07 7.2 가용 재고(입고 예정 포함)로 세면 리턴 필터가 4개로 나와 준비된 것처럼 보인다. HI-01 SOP-HI-03(입고 예정을 현재고로 합산하지 않음)으로 세면 0개로 준비 불가가 된다. 입고 예정일 2026-10-31·공급사 납기 회신 없음은 두 갈래 모두 카드에 적는다.']
    (HERE / '결과/갈래_비교.md').write_text('\n'.join(diff) + '\n', encoding='utf-8')
    # 구축 기록(참조 수치)
    docs = '\n'.join(f'| `{d["file"]}` | {d["document"]} {d["status"]} ({d["sha12"]}) | {d["approved"]} | {d["not_loaded"]} |' for d in report['documents'])
    rec = f'''# 온톨로지 구축 기록 — 강사 참조 실행

- 확인 일시 / 사용한 랩 DB: 2026-10-28, 이 폴더 전용 컨테이너(lab_db.py, 127.0.0.1 임의 포트, 인증 없음)

## 1. 질문

- 선택한 작업(SOP-COOL-14)과 다른 작업(SOP-PM-21·SOP-PM-22·T-3.1·T-4.1)을 하기 전에 무엇을 준비·금지·확인해야 하고, 지난 시행 기록은 완료 기준을 보여 주는가?
- 그 작업에 필요한 부품은 지금 쓸 수 있고, 공급 조건은 어디까지 그래프로 답하는가?

## 2. 정한 것

| 정할 것 | 정한 내용 | 근거(문서·절·자료) | 다르게 정하면 바뀌는 카드 항목 |
|---|---|---|---|
| 지난 시행으로 볼 작업지시의 범위 | 절차 ID·구판 ID(판 대응표) + 작업 이름·현장 약어, 적용 설비 밖 행 제외 | HM-8 문서 목록(1.0판 폐기·판 대응), 작업지시 서술의 약어·별칭 | 갈래_비교.md: SOP-COOL-14 {cards[("SOP-COOL-14", "기본")]}→{cards[("SOP-COOL-14", "지난시행_ID만")]}건, T-4.1 {cards[("T-4.1", "기본")]}→{cards[("T-4.1", "지난시행_ID만")]}건 |
| 부품 준비 수량을 세는 기준 | 현재고−예약(입고 예정 제외) | HI-01 SOP-HI-03 3단계 「입고 예정 수량을 현재고로 합산해 도착 완료라고 보고하지 않는다」. PR-07 7.2 가용 재고는 발주 판단용 | P-RTN-FLT 0 ↔ 4(입고 예정 포함) |

## 3. 모델 확장

| 새 종류·관계 | 뜻 | 연결한 기존 ID | 근거(원문 절·자료) |
|---|---|---|---|
| Document·Section·Procedure, IN_DOCUMENT·DEFINED_IN | 문서 판·절·절차 | — | 자료/문서_목록.csv, 원문 `##`·`###` |
| Knowledge(Step·Precondition·Prohibition·Completion·UnitValue), STATED_IN·HAS_STEP·HAS_CONDITION·REFERS_TO | 검토한 지식과 출처 | — | 입력/검토결과 approved |
| ABOUT_QUANTITY | 지식이 말하는 물리량 | Quantity(인용 속 태그 → Sensor.tag → OBSERVES) | 인용 문자열 |
| MENTIONS_PART | 지식이 말하는 부품 | Part {len(report["part_links"])}개 지식 연결(품명·다른 표기) | 인용 문자열, 2회차 품번 교차 |
| APPLIES_TO | 절차의 적용 설비 | Asset {", ".join(sorted({a for v in report["applies_to"].values() for a in v}))} | PM-2.1·HI-1·제조사 발췌 머리말(HM-8은 정하지 않음) |

## 4. 입력 문서와 검토 결과

| 파일 | 판·상태(SHA-256 앞 12자리) | 적재한 approved 수 | 적재하지 않은 수(제외·보류) |
|---|---|---|---|
{docs}

## 5. 적재와 반복 적재

| 시점 | 노드 수 | 관계 수 | 메모 |
|---|---|---|---|
| 빈 DB | {empty[0]} | {empty[1]} | lab_db.py 직후 |
| 모델 적재 후 | {m1[0]} | {m1[1]} | {m1[2]}. 재실행 {m2[0]}/{m2[1]} |
| 1차 적재 후 | {l1[0]} | {l1[1]} | load.cypher {report["statements"]}문장, 생성 표시 {created1}줄 |
| 같은 적재 재실행 후 | {l2[0]} | {l2[1]} | 생성·삭제 표시 {created2}줄. 종류별 {l2[2]} |
| 카드·조회 뒤 | {l3[0]} | {l3[1]} | 조회는 DB를 바꾸지 않음 |

## 6. 조회와 카드

| 질문·사례 | 실행 전 기대 | 조회문 | 실제 결과 요약 | 원문·자료 대조 |
|---|---|---|---|---|
| SOP-COOL-14 카드 | 준비에 LOTO·CMMS 작업지시, 금지에 고압수, 완료 CE 80 % 이상, 승인 설비보전팀장 | query.cypher 1번 | {qrows[0]}행 → 카드 작성 | check_card 인용 대조 통과, 원문 HM-8.7과 대조 |
| 다른 작업 T-3.1 카드 | 1절 안전 조치·0 psi, 차압 10 psi 미만, HI-RF-10 → P-RTN-FLT | query.cypher 2번 | {qrows[1]}행 → 카드 작성 | 같음 |
| 미제공 작업 SOP-PM-24·코어 교체 | 결과 없음 | query.cypher 3번, make_card | {qrows[2]}행, 카드 rc {miss["SOP-PM-24"]}·{miss["코어교체"]}(만들지 않음) | 원문에 없음 |
| 제외·보류 후보 적재 여부 | 0 | query.cypher 4번 | {loaded_bad} | 검토결과 상태 |
| 작업 → 부품 → 공급 조건 | P-PMP-SEAL 공급 3행(C트레이딩 비승인) | query.cypher 6번 | {qrows[5]}행 | 2회차 모델 SUPPLIES |

## 7. 답할 수 있는 것과 없는 것

| 질문 | 그래프로 답함 / 현재 값 필요 / 승인 필요 / 원문에 없음 | 근거 |
|---|---|---|
| 작업 전 준비·금지·완료 조건과 출처 | 그래프로 답함 | 카드 5개 |
| 지금 LOCAL·LOTO·0 psi·운전시간 계수기 상태 | 현재 값 필요 | 카드 「작업 직전 확인할 현재 값」 |
| 작업을 해도 되는지 | 승인 필요 | 카드 「승인」 |
| HM-8 절차의 적용 설비 | 원문에 없음 | HM-8 1.1판에 적용 설비 ID 없음 |
| 부품을 지금 쓸 수 있는지 | 기록으로 답함(재고 현황 시각 기준), 현장 확인 필요 | 재고_현황.csv 07:00 |
'''
    (HERE / '결과/구축_기록.md').write_text(rec, encoding='utf-8')
    rc, out = run('check_card.py')
    (HERE / '결과/실행기록.txt').write_text('\n'.join(LOG), encoding='utf-8')
    print(f'빈 DB {empty[:2]} → 모델 {m1[:2]}(재실행 {m2[:2]}) → 1차 {l1[:2]} → 재적재 {l2[:2]}(생성·삭제 {created2}줄) → 조회 뒤 {l3[:2]}')
    print(f'카드 지난 시행 {cards}')
    print(f'미제공 작업 rc {miss}, 조회 행 수 {qrows}, 제외·보류 적재 {loaded_bad}')
    print(out)


if __name__ == '__main__':
    main()
