"""학생용 완성본 넷 — 문서 지식 묶음 네 랩을 실습 폴더와 따로 받는 ZIP으로 묶는다(코딩랩.md K-4 · K-12 · 「길」 5, 가이드.md P-3). 학생 폴더 · package-index 밖.

추출 둘(통합 04-2 · 실전 03-4): 다음 랩 입력과 같은 판(조건의 근거 = 운전 중 제어 후보에만 · 사내 기준이 정하지 않은 제조사 항목은 보류 — run_reference 3의 나-가)의
  검토를 강사 추출 실행(instructor_extract.py — 수업 모델)의 후보에 걸어, 학생이 만들 추출 코드(completed/extract_candidates.py — 그 실행을 한 코드) · 요청 글 ·
  응답 기록 · 후보 · 검토 결과 · 검토 기록을 결과/에 넣는다. 폴더 표지(결과/폴더_표지.txt)는 넣지 않는다 — 그래서 완성본 폴더나 내 실습 폴더에서 코드를 실행해도
  llm_client.py는 이 응답 기록을 「다른 폴더의 기록」으로 보고 다시 쓰지 않는다(강사가 받은 답을 재생하지 않음 — 코딩랩.md K-8). 실행은 --model-run <폴더>(기본 강사_추출/run1), 같은 요청을 새 폴더에서 한 번 더 보낸
  실행은 --again-run <폴더>(기본 강사_추출/run2 — 검토 기록 「같은 요청을 한 번 더 보낸 결과」의 다른 점을 센다, 그 기록은 완성본에 넣지 않는다).
  안내에 「모델의 답이라 다시 부르면 달라질 수 있다 · 이 응답 기록은 다시 쓰지 않는다」를 학생 말로 적는다.
  고정한 실행이 없으면 두 번째 구현(extract_reference.py — 문장 규칙)의 후보로 만든 임시판이다 — 응답 기록이 없어 check.py가 후보 파일마다 「model_run이 비어 있습니다」를 내고,
  안내에 그 사실을 학생 말로 적는다.
그래프 둘(통합 04-3 · 실전 03-5): run_reference 4의 지점7 가 실행 산출(갈래/그래프_<반>_가)을 머리말만 학생 말로 바꿔 넣고, 새 폴더에서 안내의 명령
  (lab_db → model → run → export)을 실제 Neo4j로 다시 돌려 내보내기가 같은 바이트인지 · 학생 검사기가 통과하는지 본다. --no-neo4j면 이 확인을 건너뛴다(미검증으로 찍음).
모델을 부르지 않는다. 산출: 산출물/<반>/실습/NN회차/완성본/<랩>_학생용완성본.zip과 completed.json. 어긋나면 「불일치」를 찍고 종료 코드 1.
사용: HYD_MAIN_ROOT=<main 체크아웃> python completed.py [--model-run <폴더>] [--again-run <폴더>] [--no-neo4j]
"""
from __future__ import annotations

from pathlib import Path
import argparse
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parents[1]
sys.path[:0] = [str(HERE), str(TOOLS)]
import build_document_labs as BD  # noqa: E402
import extract_reference as X  # noqa: E402
import branches as BR  # noqa: E402
import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location('docs_run_reference', HERE/'run_reference.py')   # build_judgement_labs가 sys.path 앞에 둔 3회차 run_reference와 이름이 같다
R = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(R)

STAMP = (2026, 1, 1, 0, 0, 0)
import instructor_extract as IE  # noqa: E402
BASE = ('나', '가')                      # 다음 랩 입력과 같은 판(조건의 근거 · 사내 문서와 제조사 지침)
failures = []
# 완성본에 더한 글에 두지 않는 강사 표기(갈래 이름 · 지점 번호 · 강사 참조 · 제작 파일 이름) — 3회차 완성본과 같은 확인
MARKS = [re.compile(p) for p in (r'강사 참조', r'강사 판', r'갈래', r'두 번째 구현', r'reference', r'instructor', r'검사기_확인', r'지점\s?[0-9]', r'였다면')]
HEAD_FIX = [('// 강사 참조 적재 — ', '// 적재 — '),
            ('// 강사 참조 조회문 — Neo4j Browser에서는 :param 줄부터, run_reference.py는 같은 매개변수로 HTTP 실행', '// 조회문 — Neo4j Browser에서는 :param 줄부터 실행한다'),
            ('> 강사 참조 — 지점7 가 갈래의 실제 실행 기록이다.\n\n', '')]
GRAPH_FILES = ['schema_ext.json', 'load.cypher', 'load_more.cypher', 'query.cypher', '남은_질문.json', '구축_기록.md', '작업확인카드_SOP-COOL-14.md', '작업확인카드_SOP-COOL-11.md',
               '지식_내보내기.json']
SAME_CHOICE = ('이 완성본이 따른 「정한 것」은 결과 기록 파일의 「정한 것」 표에 있습니다. 다른 선택을 하면 결과가 달라질 수 있으니, 내 실습에서는 원문을 열어 내 선택과 근거로 정합니다.')


def fail(msg):
    failures.append(msg)
    print('불일치:', msg)


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data if isinstance(data, bytes) else data.encode('utf-8'))


def run_py(folder, *args):
    r = subprocess.run([sys.executable, *args], cwd=folder, capture_output=True, text=True, encoding='utf-8')
    return r.returncode, r.stdout + r.stderr


def target(lab):
    return lab.parents[1]/'완성본'/f'{lab.name}_학생용완성본.zip', f'{lab.name}_학생용완성본'


def files_of(folder):
    return {p.relative_to(folder).as_posix(): p.read_bytes() for p in sorted(folder.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}


def zipped(name, files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        for rel, data in files.items():
            info = zipfile.ZipInfo(f'{name}/{rel}', STAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)
    with zipfile.ZipFile(io.BytesIO(buf.getvalue())) as z:
        if {n.split('/', 1)[1]: z.read(n) for n in z.namelist()} != files:
            fail(f'{name}: ZIP 안 경로 · 바이트가 묶은 폴더와 다름')
    return buf.getvalue()


def marks(files, added):
    """완성본에 더하거나 바꾼 글 파일에서 강사 표기를 찾는다 — [(경로:줄, 찾은 글)]."""
    hits = []
    for rel in added:
        text = files[rel].decode('utf-8')
        for rx in MARKS:
            hits += [(f'{rel}:{text.count(chr(10), 0, m.start()) + 1}', m.group(0)) for m in rx.finditer(text)]
    return hits


def with_pointer(folder):
    start = (folder/'START.md').read_text(encoding='utf-8')
    head, rest = start.split('\n', 1)
    write(folder/'START.md', head + '\n\n완성한 결과를 보려면 [완성본 안내](완성본_안내.md)를 여세요. 아래는 이 결과가 푸는 원래 과제입니다.\n' + rest)


def table(head, rows):
    return '\n'.join(['| ' + ' | '.join(head) + ' |', '|' + '---|' * len(head)] + ['| ' + ' | '.join(str(x).replace('|', '/').replace('\n', ' ') for x in r) + ' |' for r in rows])


# ───────────── 추출 완성본 ─────────────
def extraction_record(course, lab, cands, reviews, items, changes, selected, records, trial, again=None):
    """결과/검토_기록.md — 빈 틀(BD.record_template)의 절 그대로 채운 판. again = 같은 요청을 새 폴더에서 한 번 더 보낸 실행과 견준 것(compare_runs)."""
    practical = course == '실전반'
    by_file = {d['source_file']: d for d in cands.values()}
    use = {'현행': '작업 근거', '폐기': '지난 기록 해석에만', '개정 요청(미승인)': '작업 근거 아님(승인 전)', '보충': '기존 문서에 더함(대체 아님)',
           '참고(제조사)': '사내 기준과 다르게 정한 항목은 사내 기준', '참고(스캔본)': '사내 기준과 다르게 정한 항목은 사내 기준'}
    out = ['# 문서 지식 검토 기록', '', '## 목표와 질문', '',
           '핀 세척(SOP-COOL-14) 작업지시를 내기 전에 작업 조건과 판정에 쓴 조건의 원문 근거를 확인하고, 같은 기능이 다른 문서에서 빠뜨리거나 지어내지 않는지 센다.', '',
           '## 이 답을 쓰는 사람과 쓰는 곳', '', '설비보전팀장(작업지시 승인)' + (' · 보전 야간조(작업 준비)' if practical else '') + '.', '']
    if practical:
        out += ['## 이 사건의 작업', '', '- 작업: SOP-COOL-14 쿨러 핀 세척', f'- 근거(파일 · 줄): {selected["basis"]}', '']
    out += ['## 판 기준 — 어느 문서 · 판을 무엇에 쓰는가', '',
            table(['문서 · 판', '상태', '이번 검토에서 쓰는 곳', '근거(파일 · 줄)'],
                  [(f'{rv["doc_id"]} {rv["rev"]}', rv['doc_status'], use[rv['doc_status']], '자료/DC-01_문서관리기준.md 17~23줄(상태의 뜻)') for _, rv in sorted(reviews.items())]), '',
            '## 정한 것', '',
            table(['지점(종류)', '고른 것', '근거(파일 · 줄)', '이 선택으로 바뀌는 답'],
                  [('조건의 근거', 'SR-04 제4조 ①②는 운전 중 제어 후보의 근거로만 둔다 — 작업지시 후보의 예측 유온 제외(R4)는 근거 원문을 찾지 못함', '자료/SR-04_설비안전규정_발췌.txt 10 · 11줄',
                    'R4 불일치 — 조건표 변경 요청(SOP-COOL-14 빼기)'),
                   ('사내 문서와 제조사 지침', '사내 기준이 정하지 않은 제조사 항목(코어 상태 확인 · 코어 교체 · 유온 차)은 HM-8 소유 부서에 묻기 전까지 보류', '자료/OEM-HPP45A_정비지침_영한.md 107 · 114 · 116줄, 7줄(머리말)',
                    '핀 세척의 준비 · 완료 항목 수')]), '',
            '## 기대 항목 — 실행 전에 원문에서', '', '- 기대 칸을 쓴 시각: ' + (f'{stamp(min(r["received_at"] for r in records))} 이전 — 첫 요청을 보내기 전' if records else '2026-10-28 08:30'), '']
    rows = []
    by_review = {rv['source_file']: rv for rv in reviews.values()}
    for i in items:
        if i['kind'] == 'toc':
            continue
        data, rv = by_file.get(i['file']), by_review.get(i['file'])
        got = rv['candidates'] if rv else []
        mine = [c for c in got if c['origin'] == 'extractor']
        hits = [c for c in mine if BR.covers(c, i) and not c['reason'].startswith('같은 원문 항목(')]   # 검토가 이 기대 항목과 같은 것으로 본 후보(고친 뒤 값 — 중복으로 뺀 후보 빼고)
        hit = next((c for c in hits if c['decision'] != '제외'), hits[0] if hits else None)
        near = None if hit else next((c for c in mine if BR.matches(c, i)), None)                 # 같은 줄을 가리키지만 인용이 원문 문장과 다른 후보
        added = next((c for c in got if c['origin'] == 'reviewer' and c['quote'] == i['quote'] and c['kind'] == i['kind'] and c['line_start'] == i['line_start']
                      and (i['kind'] != 'unit_value' or c.get('value') == i.get('value'))), None)
        where = f'{data["doc_id"]} {data["rev"]} · {i["section"]} · {i["line_start"]}~{i["line_end"]}줄' if data else i['file']
        if hit:
            diff = '같음' if not hit.get('before') else '같은 원문 — ' + ' · '.join(
                (f'인용 경계를 원문 문장으로 고침(앞 인용 「{str(v)[:30]}」)' if k == 'quote' else f'{k} {v!r} → {hit.get(k)!r}')
                for k, v in hit['before'].items() if k not in ('line_start', 'line_end', 'quote_match'))
        elif added:
            diff = f'누락 — 검토에서 원문 문장으로 더함({added["id"]})' + (f' · 후보 {near["id"]}는 {near["decision"]}({near["reason"].split(" — ")[0][:40]})' if near else '')
        else:
            diff = '누락 — 같은 글이 원문 여러 곳에 있어 한 줄 근거로 더하지 않음(남은 누락)'
        rows.append((where, i['kind'], i['quote'][:70], hit['id'] if hit else (near['id'] if near else '없음'), diff))
    out += [table(['문서 · 판 · 절 · 줄', '종류', '원문(그대로)', '실제 후보', '차이 종류 · 고친 점'], rows), '', '## 조건 근거 대조', '']
    links = []
    for _, rv in sorted(reviews.items()):
        for link in rv.get('rule_links', []):
            req = {'불일치': '조건표 변경 요청', '원문 없음': '원본 확인 요청', '보류': '안전관리 담당 해석 요청'}.get(link['match'], '출처 칸 고침')
            links.append((link['rule_id'], f'{rv["doc_id"]} {rv["rev"]} (후보 {", ".join(link["candidates"]) or "없음"})', link['match'], link['note'][:90], req))
    out += [table(['조건(rule_id)', '근거를 찾은 문서 · 판 · 절 · 줄', 'match', '까닭', '요청할 것'], links), '', '## 다른 문서에 적용', '']
    other = []
    for _, rv in sorted(reviews.items()):
        data = by_file[rv['source_file']]
        missing = len(rv.get('missing', []))
        made_up, many, split = unlocated_kinds(lab, data)
        other.append((f'{rv["doc_id"]} {rv["rev"]}', len(data['candidates']), missing, made_up,
                      ' · '.join(x for x, on in (('빠진 항목은 검토에서 원문 문장으로 더함', missing),
                                                 (f'원문에 없는 인용 {made_up}개는 후보에서 뺌', made_up),
                                                 (f'원문 여러 곳에 맞아 줄을 정하지 못한 인용 {many}개는 후보에서 뺌(지어낸 글이 아님)', many),
                                                 (f'쪽 머리 · 꼬리를 건너 앞뒤 쪽 글을 이은 인용 {split}개는 후보에서 뺌(한 곳에 이어진 원문 글이 아님)', split)) if on) or '고칠 것 없음',
                      f'누락 {sum(1 for m in rv.get("missing", []) if not m.get("added"))}'))
    out += [table(['문서 · 판', '후보 수', '누락', '근거 없는 생성', '고친 점', '고친 뒤 다시 센 수'], other), '', '## 같은 요청을 한 번 더 보낸 결과', '']
    if again:
        t, a = again['task'], again['all']
        out.append(table(['조각', '첫 응답 기록', '다시 보낸 응답 기록', '다른 점'],
                         [(f'핀 세척 절이 든 조각(HM-8 1.1 {t["lines"]})', f'결과/응답_기록/{t["hash"]}.json', '같은 요청을 새 폴더에서 한 번 더 보낸 기록(이 묶음에 넣지 않음)',
                           f'후보 {t["n1"]}개 / {t["n2"]}개 · 두 답에 함께 있는 인용 {t["both"]}개 · 첫 답에만 {t["only1"]}개 · 다시 보낸 답에만 {t["only2"]}개'),
                          (f'조각 {a["chunks"]}개 전체', f'응답 기록 {a["chunks"]}개', '같은 요청 전부를 새 폴더에서 한 번 더',
                           f'답 글이 글자까지 같은 조각 {a["same_text"]}개 · 후보 {a["n1"]}개 / {a["n2"]}개 · 두 답에 함께 있는 인용 {a["both"]}개 · 첫 답에만 {a["only1"]}개 · 다시 보낸 답에만 {a["only2"]}개')]))
    elif records:
        out.append(table(['조각', '첫 응답 기록', '다시 보낸 응답 기록', '다른 점'], [('해당 없음', f'응답 기록 {len(records)}개', '이 실행에서 다시 보낸 요청 없음', '확인하지 못함')]))
    else:
        out.append(table(['조각', '첫 응답 기록', '다시 보낸 응답 기록', '다른 점'], [('해당 없음', '수업 모델을 부르지 않아 응답 기록 없음', '없음', '확인하지 못함')]))
    out.append('')
    if practical:
        out += ['## 검사가 잡는지 확인', '', table(['일부러 바꾼 곳(사본에서)', 'check.py가 짚은 줄', '되돌린 뒤 출력'], [trial]), '']
    pending = sum(1 for rv in reviews.values() if rv['doc_id'] == 'OEM-HPP45A-MM' for c in rv['candidates'] if c['status'] == 'pending')
    reviewed = max(rv['review']['reviewed_at'] for rv in reviews.values())
    unknown = (f'다시 보낸 답에만 있는 인용 {again["all"]["only2"]}개 — 첫 실행의 답으로 만든 후보만 검토함' if again else
               '같은 요청을 다시 보냈을 때의 차이' if records else '수업 모델의 답으로 만든 후보(이 묶음의 후보는 문장 규칙으로 만든 것)')
    out += ['## 남은 질문', '', '- 트립 뒤 복귀 조건(R5의 출처 HM-9.4) — 9장 스캔본에 9-7쪽이 없어 원본 확인 요청.',
            f'- 제조사 지침에서 보류한 후보 {pending}개 — HM-8 소유 부서에 적용 여부 확인 요청.',
            '- 작업지시 후보의 예측 유온 제외(R4) — 근거 원문을 찾지 못해 조건표 변경 요청.', '', '## 저장 기록', '', '- 기준일: 2026-10-28',
            '- 저장 시점: ' + (f'{reviewed[:10]}(검토 결과를 쓴 뒤 다시 열어 `python check.py` 출력이 같음)' if records else '2026-10-28 11:00'),
            '- 확인하지 못한 점: ' + unknown]
    return '\n'.join(out) + '\n'


def unlocated_kinds(lab, data):
    """찾지 못한 인용(unlocated)을 셋으로 센다 — (원문 어디에도 없는 인용 = 근거 없는 생성, 원문 여러 곳에 맞아 줄을 정하지 못한 인용,
    쪽 머리 · 꼬리(스캔본의 되풀이되는 머리 줄 · 「- 9-x -」 · 「=== 스캔 n/7 ===」)를 건너 이은 인용). 원문은 후보 파일이 적은 글자 방식으로 읽고,
    글자 그대로 또는 글자 · 숫자만 남긴 비교로 찾는다(계약 「인용」의 두 방법)."""
    text = (lab/'자료'/data['source_file']).read_bytes().decode(data['encoding'])
    lines = text.splitlines()
    flat = X.squash(text)
    body = X.squash('\n'.join(x for x in lines if lines.count(x) == 1 and not X.FOOTER.match(x.strip()) and not x.startswith('=== ')))
    made_up = many = split = 0
    for u in data['unlocated']:
        quote = str(u.get('quote') or '')
        key = X.squash(quote)
        found = text.count(quote) if quote.strip() else 0
        if not found and key:
            found = flat.count(key)
        if found:
            many += 1
        elif key and key in body:
            split += 1
        else:
            made_up += 1
    return made_up, many, split


def stamp(iso):
    return iso.replace('T', ' ')[:16]


def extraction_guide(title, model_mode, practical):
    look = ('`결과/후보/`는 문서마다 뽑은 후보, `결과/검토/`는 후보마다 채택 · 수정 · 제외 · 보류와 근거, 조건표 조건마다의 근거 대조(`rule_links`)이고, '
            + ('`결과/선택작업_조건.json`은 이 사건의 작업(핀 세척)의 준비 · 금지 · 완료를 문서를 가리지 않고 모은 것, ' if practical else '')
            + '`결과/검토_기록.md`는 판 기준 · 정한 것 · 기대 항목과 실제 · 다른 문서의 수 · 남은 질문입니다. `결과/prompt.md`는 수업 모델에 보내는 요청 글입니다.')
    if model_mode:
        made = ('후보 파일은 `결과/extract_candidates.py`가 문서를 절 머리에서 끊은 조각마다 `결과/prompt.md`와 함께 수업 모델에 보내 받은 답으로 만든 것이고 '
                '(답의 인용이 원문 어느 줄에 있는지는 코드로 찾았습니다), 그 요청과 답이 `결과/응답_기록/`에 있습니다. 같은 요청을 다시 보내면 답이 달라질 수 있어서, '
                '내 실습의 후보와 수 · 문장이 다를 수 있습니다. 이 응답 기록은 결과를 보는 데만 씁니다 — 이 폴더나 내 실습 폴더에서 코드를 실행해도 `llm_client.py`는 '
                '이 기록을 다시 쓰지 않고, 내 실습의 후보는 내 폴더에서 수업 모델을 불러 받은 답으로 만듭니다. 키를 넣고 이 폴더에서 추출 코드를 실행하면 새로 받은 답으로 '
                '후보 파일이 바뀌어 이 묶음의 검토 결과와 맞지 않게 되므로, 추출 코드는 내 실습 폴더에서 실행합니다.')
        run = ('`python check.py`는 마지막에 「구조상 빠진 단계는 없습니다」를 냅니다. `python 결과/extract_candidates.py --list`는 요청을 보내지 않고 '
               '문서마다 읽은 결과와 조각 목록을 보입니다.')
    else:
        made = ('이 묶음의 후보 파일은 수업 모델을 부르지 않고, 문서의 절 머리와 문장 꼴로 후보를 뽑는 프로그램으로 만든 것입니다. 그래서 `결과/응답_기록/`이 없고, '
                '`python check.py`는 후보 파일마다 「model_run이 비어 있습니다」 줄을 냅니다 — 실습에서는 수업 모델의 답으로 후보를 만들므로 내 결과에서는 이 줄이 나오지 않아야 합니다. '
                '검토 결과 · 조건 근거 대조 · 검토 기록이 어떤 모양인지 보는 데 씁니다.')
        run = '`python check.py`는 그 줄 밖의 문제를 짚지 않습니다.'
    return (f'# {title} — 학생용 완성본\n\nZIP 전체를 실습 폴더와 다른 새 폴더에 풀고, 이 문서가 있는 폴더를 VS Code에서 연 뒤 터미널에서 아래 명령을 실행합니다. '
            f'Python 3 표준 라이브러리만 쓰고, AI 계정 · 인터넷 접속 없이 실행됩니다.\n\n```text\npython check.py\n```\n\n{look}\n\n{made} {run}\n\n{SAME_CHOICE}\n')


def damage_trial(folder):
    """실전반 검토 기록의 「검사가 잡는지 확인」 — 후보 파일 사본에서 인용 한 글자를 바꿔 check.py가 짚는 줄(실제 출력)."""
    src = folder/'결과/후보/HM-8_1.1.json'
    data = json.loads(src.read_text(encoding='utf-8'))
    c = data['candidates'][0]
    c['quote'] = ('X' if c['quote'][0] != 'X' else 'Y') + c['quote'][1:]
    copy = folder/'결과/시험_사본.json'
    write(copy, X.dump(data))
    _, out = run_py(folder, 'check.py', '결과/시험_사본.json')
    copy.unlink()
    line = next((x.strip()[2:] for x in out.splitlines() if x.strip().startswith('- ') and c['id'] in x), None)
    if not line:
        fail(f'실전 추출 완성본: 인용 한 글자를 바꾼 사본을 check.py가 짚지 않음\n{out[:600]}')
    return ('`결과/후보/HM-8_1.1.json` 사본의 첫 후보 인용 첫 글자', line, '사본을 지운 뒤 계약 통과')


def extraction(course, model_run, again_run, tmp):
    ek = R.COURSES[course][0]
    lab = BD.LABS[ek]
    practical = course == '실전반'
    zpath, name = target(lab)
    folder = Path(tmp)/'ext'/name
    shutil.copytree(lab, folder)
    judged = json.loads((lab/'입력'/BD.JUDGED[ek]).read_text(encoding='utf-8'))
    records, again, when = [], None, {}
    if model_run:
        run = Path(model_run)
        if (run/'결과/extract_candidates.py').read_bytes() != IE.CODE.read_bytes():
            fail(f'{run}: 실행한 추출 코드가 지금 {IE.CODE.name}와 다름 — 완성본의 코드가 그 후보를 만든 코드가 아니게 된다(다시 실행)')
        if (run/'결과/prompt.md').read_text(encoding='utf-8') != R.PROMPT:
            fail(f'{run}: 실행한 요청 글이 지금 강사_요청글.md와 다름')
        cands = {p.name: json.loads(p.read_text(encoding='utf-8')) for p in sorted((run/'결과/후보').glob('*.json'))}
        for p in sorted((run/'결과/응답_기록').glob('*.json')):
            write(folder/'결과/응답_기록'/p.name, p.read_bytes())
            records.append(json.loads(p.read_text(encoding='utf-8')))
        write(folder/'결과/extract_candidates.py', IE.CODE.read_bytes())
        when = {'reviewed_at': BR.base_candidates(run)[1]}                       # 검토는 후보 파일을 다 만든 뒤(다음 랩 입력과 같은 규칙)
        again = IE.compare_runs(lab, run, again_run) if again_run else None
        if again and (not again['task'] or again['all']['chunks'] != again['chunks_first']):
            fail(f'두 강사 추출 실행: 짝지은 조각 {again["all"]["chunks"]} · 첫 실행 조각 {again["chunks_first"]} · 핀 세척 조각 {bool(again["task"])}')
    else:
        cands = {k: v for k, v in X.extract_all(lab).items() if v['source_file'] in BR.TARGETS}
    out, reviews = BR.build(lab, cands, judged, *BASE, course, **when)
    for rel, data in out.items():
        if rel.startswith(('후보/', '검토/')) or rel == '선택작업_조건.json':
            write(folder/'결과'/rel, data)
    if model_run:
        for fname in cands:
            if (folder/'결과/후보'/fname).read_bytes() != (Path(model_run)/'결과/후보'/fname).read_bytes():
                fail(f'완성본 {name}: 결과/후보/{fname}이 실행이 쓴 후보 파일과 다른 바이트')
    write(folder/'결과/prompt.md', R.PROMPT)
    trial = damage_trial(folder) if practical else None
    write(folder/'결과/검토_기록.md', extraction_record(course, lab, cands, reviews, BR.expected(lab), json.loads(out['판정_변화.json']),
                                                  json.loads(out['선택작업_조건.json']) if practical else None, records, trial, again))
    write(folder/'완성본_안내.md', extraction_guide(BD.TITLES[ek], bool(model_run), practical))
    with_pointer(folder)
    files = files_of(folder)
    added = [r for r in files if r.startswith('결과/') and r.endswith(('.md', '.json', '.py')) and not r.startswith('결과/응답_기록/')] + ['완성본_안내.md', 'START.md']
    for at, got in marks(files, added):
        fail(f'완성본 {name}/{at}: 강사 표기 「{got}」')
    # 새 폴더에서 안내의 명령(check.py) — 응답 기록이 있으면 통과, 없으면(임시판) model_run 줄만
    fresh = Path(tmp)/'ext_run'/name
    for rel, data in files.items():
        write(fresh/rel, data)
    code, text = run_py(fresh, 'check.py')
    todo = [x.strip()[2:] for x in text.split('완료 아님 — 남은 것:')[-1].splitlines() if x.strip().startswith('- ')] if '완료 아님' in text else []
    result = {}
    if model_run:
        if code or '구조상 빠진 단계는 없습니다' not in text:
            fail(f'완성본 {name}: 학생 검사기가 통과시키지 않음\n{text[-1500:]}')
        again_code, again_text = run_py(fresh, 'check.py')            # 「다시 열어 같은 출력」 — 기록의 저장 시점 문장
        if (again_code, again_text) != (code, text):
            fail(f'완성본 {name}: check.py를 다시 실행한 출력이 다름')
        lcode, ltext = run_py(fresh, '결과/extract_candidates.py', '--list')
        sent = [x for x in ltext.splitlines() if x.startswith('수업 모델에 요청을 보냅니다')]
        if lcode or sent or '조각 ' not in ltext or (fresh/'결과/요청').exists():
            fail(f'완성본 {name}: 추출 코드 --list가 보내지 않고 조각 목록만 보이지 않음 rc {lcode}\n{ltext[-800:]}')
        result['추출 코드 --list 끝줄'] = ltext.strip().splitlines()[-1]
        if (fresh/'결과/폴더_표지.txt').exists():
            fail(f'완성본 {name}: 추출 코드 --list가 폴더 표지를 만들었다')
        # 응답 기록을 재생하지 않는다(K-8): 새 폴더에 .env의 모델 이름만 두고 코드를 실행하면 기록을 다시 쓰지 않고, 키가 없어 보내지 않고 멈춘다
        replay = Path(tmp)/'ext_replay'/name
        for rel, data in files.items():
            write(replay/rel, data)
        model = sorted({r['model'] for r in records if r.get('method') == '모델 서버'})[0]
        write(replay/'.env', f'LLM_MODEL={model}\n')
        rcode, rtext = run_py(replay, '결과/extract_candidates.py')
        reused = rtext.count('같은 요청의 응답 기록을 씁니다')
        if reused or rcode != 2 or '키가 없어 요청을 보내지 않았습니다' not in rtext or '다른 폴더의 응답 기록' not in rtext:
            fail(f'완성본 {name}: 새 폴더에서 추출 코드를 실행했을 때 응답 기록을 다시 씀 {reused}번 · rc {rcode}\n{rtext[-600:]}')
        result['새 폴더에서 추출 코드 실행(.env에 모델 이름만)'] = f'다시 쓴 응답 기록 {reused}개 · rc {rcode} · ' + next(
            (x for x in rtext.splitlines() if x.startswith('키가 없어')), '')
        # 보내지 않고 멈춘 실행 뒤에도 완성본이 그대로 통과한다(폴더 표지를 만들지 않음)
        ccode, ctext = run_py(replay, 'check.py')
        if (replay/'결과/폴더_표지.txt').exists() or ccode or '구조상 빠진 단계는 없습니다' not in ctext:
            fail(f'완성본 {name}: 키 없이 추출 코드를 실행한 뒤 학생 검사기가 통과시키지 않음(표지 {(replay/"결과/폴더_표지.txt").exists()})\n{ctext[-800:]}')
        result['키 없이 실행한 뒤 check.py'] = ctext.strip().splitlines()[-1]
    else:
        # 임시판: 단계별 상태의 남은 것은 후보 · 검토 파일의 「계약 오류」뿐이고, 파일마다 계약 검사의 문제는 model_run 한 줄뿐이어야 한다
        other = [t for t in todo if '계약 오류' not in t]
        targets = sorted(r for r in files if r.startswith(('결과/후보/', '결과/검토/')))
        _, detail_text = run_py(fresh, 'check.py', *targets)
        detail = [x.strip()[2:] for x in detail_text.splitlines() if x.strip().startswith('- ')]
        if other or any(d != 'model_run이 비어 있습니다 — 후보 파일은 응답 기록에서 만듭니다.' for d in detail) or len(detail) != len(targets):
            fail(f'완성본 {name}: model_run 밖의 문제가 있음 {other} {[d for d in detail if "model_run" not in d][:8]} (줄 {len(detail)} · 파일 {len(targets)})')
    data = zipped(name, files)
    write(zpath, data)
    sent = [r for r in records if r.get('method') == '모델 서버']
    return {'경로': zpath.relative_to(BD.OUT).as_posix(), '파일수': len(files), 'sha256': hashlib.sha256(data).hexdigest(), '명령': 'python check.py',
            '후보 출처': f'수업 모델 응답 기록({label(model_run)} — 보낸 요청 {len(sent)}번 · 모델 {sorted({r["model"] for r in sent})})' if model_run
            else '문장 규칙(임시판 — 강사 추출 실행 뒤 다시)',
            '같은 요청을 다시 보낸 실행': ({'실행': label(again_run), **again} if again else None),
            '검사기 끝줄': text.strip().splitlines()[-1] if text.strip() else '', '종료 코드': code, **result}


def label(path):
    path = Path(path).resolve()
    return path.relative_to(HERE).as_posix() if path.is_relative_to(HERE) else path.name


# ───────────── 그래프 완성본 ─────────────
def graph_guide(title, practical):
    cmds = ['python lab_db.py', 'python lab_cypher.py model', 'python lab_cypher.py run 결과/load.cypher'] + ([] if practical else ['python lab_cypher.py run 결과/load_more.cypher']) + \
           ['python lab_cypher.py count', 'python lab_cypher.py export 결과/지식_내보내기.json', 'python check.py']
    look = ('`결과/schema_ext.json`은 문서 근거를 담으려고 더한 종류 · 관계, `결과/load.cypher`' + ('' if practical else ' · `load_more.cypher`(다른 문서 추가)')
            + '는 문서 · 판 · 절과 승인 후보를 기존 ID에 잇는 적재 파일, `결과/query.cypher`는 질문마다의 조회문입니다. '
            + ('`결과/작업확인카드_SOP-COOL-14.md` · `SOP-COOL-11.md`는 조회 결과로 쓴 작업 확인 카드, ' if practical else '')
            + '`결과/남은_질문.json` · `결과/지식_내보내기.json`은 그래프에 넣지 않은 남은 질문과 다음 실습에 넘길 내보내기, `결과/구축_기록.md`는 정한 것 · 질문별 기대와 실제 · 적재 수 · 답할 수 있는 것과 없는 것입니다.')
    return (f'# {title} — 학생용 완성본\n\nZIP 전체를 실습 폴더와 다른 새 폴더에 풀고, 이 문서가 있는 폴더를 VS Code에서 연 뒤 터미널에서 아래 명령을 차례로 실행합니다. '
            'Python 3 표준 라이브러리와 Docker Desktop(이 폴더 전용 랩 DB)을 쓰고, AI 계정 없이 실행됩니다. 처음 한 번은 DB 이미지를 내려받느라 인터넷 연결과 시간이 더 듭니다.\n\n'
            '```text\n' + '\n'.join(cmds) + '\n```\n\n'
            f'{look}\n\n`export`가 다시 쓴 `결과/지식_내보내기.json`은 이 묶음에 들어 있는 것과 같습니다. 질문별 조회는 `결과/query.cypher`의 조회문을 Neo4j Browser에 붙여 넣어 실행합니다. '
            f'`python check.py`는 마지막에 「구조상 빠진 단계는 없습니다」를 냅니다.\n\n{SAME_CHOICE}\n'), cmds


def docker(*args):
    return subprocess.run(['docker', *args], capture_output=True, text=True)


def graph(course, tmp, neo4j):
    gk = R.COURSES[course][1]
    lab = BD.GLABS[gk]
    practical = course == '실전반'
    zpath, name = target(lab)
    folder = Path(tmp)/'graph'/name
    shutil.copytree(lab, folder)
    src = HERE/'갈래'/f'그래프_{course}_가'
    for rel in GRAPH_FILES:
        if (src/rel).is_file():
            text = (src/rel).read_text(encoding='utf-8')
            for a, b in HEAD_FIX:
                text = text.replace(a, b)
            write(folder/'결과'/rel, text)
    guide, cmds = graph_guide(BD.GTITLES[gk], practical)
    write(folder/'완성본_안내.md', guide)
    with_pointer(folder)
    files = files_of(folder)
    added = [f'결과/{r}' for r in GRAPH_FILES if f'결과/{r}' in files] + ['완성본_안내.md', 'START.md']
    for at, got in marks(files, added):
        fail(f'완성본 {name}/{at}: 강사 표기 「{got}」')
    result = {'명령': ' · '.join(cmds), '실행 확인': '미검증(--no-neo4j)'}
    if neo4j:
        fresh = Path(tmp)/'graph_run'/name
        for rel, data in files.items():
            write(fresh/rel, data)
        container = None
        try:
            outs = []
            for cmd in cmds:
                args = cmd.split()[1:] + (['--no-open'] if cmd == 'python lab_db.py' else [])
                code, text = run_py(fresh, *args)
                outs.append((cmd, code, text.strip().splitlines()[-1] if text.strip() else ''))
                if cmd == 'python lab_db.py' and code == 0:
                    container = json.loads((fresh/'랩_연결.json').read_text(encoding='utf-8'))['container']
                if code and cmd != 'python check.py':
                    fail(f'완성본 {name}: {cmd} 실패\n{text[-800:]}')
                    break
            if (fresh/'결과/지식_내보내기.json').read_bytes() != files['결과/지식_내보내기.json']:
                fail(f'완성본 {name}: 안내의 명령으로 다시 쓴 지식_내보내기.json이 묶음의 것과 다름')
            last = outs[-1]
            if last[0] != 'python check.py' or last[1] != 0:
                fail(f'완성본 {name}: 학생 검사기가 통과시키지 않음 {outs[-1]}')
            result['실행 확인'] = '확인됨(새 폴더 · 실제 Neo4j)'
            result['출력 끝줄'] = [f'{c} → {t}' for c, _, t in outs]
        finally:
            if container:
                docker('rm', '-f', '-v', container)
                if docker('ps', '-a', '-q', '--filter', f'name=^/{container}$').stdout.strip():
                    fail(f'완성본 {name}: 컨테이너 {container}를 지우지 못함')
    data = zipped(name, files)
    write(zpath, data)
    result.update({'경로': zpath.relative_to(BD.OUT).as_posix(), '파일수': len(files), 'sha256': hashlib.sha256(data).hexdigest()})
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--model-run', help='강사 추출 실행 폴더(기본 강사_추출/run1 — 없으면 문장 규칙 후보의 임시판)')
    p.add_argument('--again-run', help='같은 요청을 새 폴더에서 한 번 더 보낸 실행(기본 강사_추출/run2)')
    p.add_argument('--no-neo4j', action='store_true')
    a = p.parse_args(argv)
    model_run = a.model_run or (IE.KEPT/'run1' if (IE.KEPT/'run1/결과/후보').is_dir() else None)
    again_run = a.again_run or (IE.KEPT/'run2' if model_run and (IE.KEPT/'run2/결과/응답_기록').is_dir() else None)
    report = {}
    with tempfile.TemporaryDirectory() as tmp:
        for course in R.COURSES:
            report[f'추출_{course}'] = extraction(course, model_run, again_run, tmp)
            report[f'그래프_{course}'] = graph(course, tmp, not a.no_neo4j)
    (HERE/'completed.json').write_text(json.dumps(report, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    for k, v in report.items():
        print(f'{k}: {v["경로"]} 파일 {v["파일수"]}개 sha256 {v["sha256"][:12]} · ' + (v.get('실행 확인') or v.get('후보 출처')))
    print(f'불일치 {len(failures)}건')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
