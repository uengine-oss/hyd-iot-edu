"""강사 참조 실행 · 대조 — 문서 지식 묶음 네 랩(통합 04회차 실습2 · 3, 실전 03회차 실습4 · 5). 학생 폴더 · ZIP에 넣지 않는다. 모델을 부르지 않는다.

사용: HYD_MAIN_ROOT=<main 체크아웃> python run_reference.py [--model-candidates <결과/후보 폴더> ...] [--no-neo4j]
학생 폴더는 임시 사본에서만 실행하고 원본 결과/를 건드리지 않는다.
1. 사슬(바이트): 추출 랩 입력 = 3회차 판정 랩 입력 · 강사 판 결과, 그래프 랩 입력 = 2회차 실습4 입력 · 3회차 판 · 강사 추출 실행 run1의 강사 판 검토 결과
   (추출 학생용 완성본의 결과/검토와 같은 판), 두 랩의 자료 = 한 벌.
2. 기대 항목(expected_items.py — 원문에서 손으로)과 두 번째 구현(extract_reference.py — 규칙 기반)의 겹침: 문서마다 누락 · 값이 글과 다른 후보 · 기대 절 안의 기대 밖 후보.
   강사 추출 실행(instructor_extract.py — 수업 모델)의 후보도 같은 기준으로 센다(모델 출력이 매번 달라도 서는 기준). 실행은 --model-candidates <실행 폴더>/결과/후보
   (여러 번), 주지 않으면 고정한 강사_추출/run*/결과/후보. 실행마다 3의 갈래 검토를 그 후보에 걸어 학생 검사기를 그 실행의 실제 응답 기록과 짝지어 돌리고,
   갈래마다 rule_links · 판정 변화가 두 번째 구현 후보의 갈래와 같은지, 실전 선택 작업 조건이 갈래마다 갈리는지 본다. 두 실행이면 문서마다 · 조각마다 차이를 센다.
3. 추출 갈래 — 판정 랩 입력(3회차 지점2 가)에서 지점5(가 · 나 · 다) × 지점6(가 · 나) = 6, 내 입력이 3회차 지점2 나 · 다이면 지점5만 각 3 — 두 반마다.
   갈래마다 검토 결과 · rule_links · 선택 작업 조건(실전) · 판정이 달라지는 지난 경보를 쓰고, 학생 검사기를 사본에서 실제 실행한다(계약 통과 · 단계 남은 것 0).
4. 그래프 갈래 — 입력 = 지점5 나 · 지점6 가, 지점7(가 · 나) × 두 반 = 4. 실제 Neo4j(학생 도구 lab_db.py · lab_cypher.py)로 앞 단계 판 적재 → 적재 → 세기 →
   같은 적재 → 세기 같음 → (통합) 다른 문서 추가 → 기존 ID · 속성 그대로 → 질문 다섯 · 보류 · 미제공 조회 → (실전) 카드 둘 → 내보내기 → 학생 검사기. 끝나면 그 컨테이너와 볼륨을 지운다.
5. 검사기 고의 손상: 추출 검사기(두 반) · 그래프 검사기(두 반, 랩 DB 포함)에 일부러 망가뜨린 입력을 넣어 잡는지 본다 → 검사기_확인.json.
6. 장난감 시험 통과 기준(toy_criteria.py)의 자기 시험 — 손대지 않은 사본은 통과, 일부러 어긴 사본은 그 기준에서 걸린다. ②의 답 글 비교는 같은 규칙 기반 후보에
   관계없는 답 · 스스로 써 넣은(채팅으로 받음) 답 · 키 없이 보낸 기록 · 실제 호출보다 많은 모델 서버 기록을 짝지으면 걸리고, 실제 호출 수를 주지 않으면 판정하지 않으며,
   그 후보를 담은 모델 답(실제 호출과 같은 수)이면 통과하는지 본다.
산출: 갈래/, expected_results.json, 사건_갈래표.md, 검사기_확인.json. 어긋나면 「불일치」 줄을 찍고 종료 코드 1 — 결과를 맞추지 말고 원인을 고친다(코딩랩.md K요-11).
"""
from __future__ import annotations

from pathlib import Path
import argparse
import contextlib
import copy
import hashlib
import importlib.util
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
import graph_reference as G  # noqa: E402
import toy_criteria as T  # noqa: E402
import instructor_extract as IE  # noqa: E402
S = IE.student_code()                                  # 학생 추출 코드(완성본에 들어가는 그 코드) — 조각 · 답 → 후보

OUTDIR = HERE/'갈래'
COURSES = {'통합반': ('integrated-04-extract', 'integrated-04-graph'), '실전반': ('practical-03-extract', 'practical-03-card')}
PROMPT = (HERE/'강사_요청글.md').read_text(encoding='utf-8')
failures = []


def fail(msg):
    failures.append(msg)
    print('불일치:', msg)


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


LLM = module(TOOLS/'lab_llm.py', 'lab_llm_limits')       # 학생 폴더 llm_client.py의 원본 — 상한 값 한 곳


def copy_lab(folder, tmp):
    dst = Path(tmp)/Path(folder).name
    shutil.copytree(folder, dst)
    return dst


def run_py(folder, *args):
    r = subprocess.run([sys.executable, *args], cwd=folder, capture_output=True, text=True, encoding='utf-8')
    return r.returncode, r.stdout + r.stderr


# ───────────── 1. 사슬 ─────────────
def chain():
    out = {}
    for course, (ek, gk) in COURSES.items():
        try:
            BD.design_checks(ek, BD.LABS[ek])
            BD.gdesign_checks(gk, BD.GLABS[gk], BD.glab(gk))
            out[course] = '설계 조건 검사 통과(같은 바이트 · 학생 문장 답 0 · 응답 기록 0 · .env 틀)'
        except RuntimeError as e:
            fail(f'{course} 설계 조건: {e}')
            out[course] = str(e)
    return out


# ───────────── 2 · 3. 추출 — 점수 · 갈래 · 학생 검사기 ─────────────
def fixture(lab_tmp, cands):
    """사본에 「채팅으로 받음」 응답 기록을 만들어 후보 파일마다 model_run을 붙인다 — 검사기 시험용(수업 모델 호출 아님, 기록도 그렇게 남는다).
    붙여 넣는 답 글은 그 후보들을 담은 JSON이라, 후보 인용이 짝지은 답 글에 있는지 보는 검사(toy_criteria.quote_in_replies와 같은 비교)도 통과한다."""
    client = module(lab_tmp/'llm_client.py', 'llm_client_fixture')
    out = {}
    for fname, data in cands.items():
        msgs = [{'role': 'user', 'content': f'{fname} — 검사기 시험'}]
        digest = client.request_hash(client.body_of(msgs, ''))
        if not (lab_tmp/'결과/응답_기록'/f'{digest}.json').is_file():
            client.write_request(digest, msgs)
            stdin = sys.stdin
            body = [{k: c[k] for k in ('section', 'procedure', 'kind', 'text', 'quote') if k in c} for c in data['candidates']]
            sys.stdin = io.StringIO(json.dumps({'candidates': body}, ensure_ascii=False))   # 후보를 만든 답 글 — 인용이 답 글에 있다
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    client.paste(digest, '채팅(모델 이름 모름)')
            finally:
                sys.stdin = stdin
        d = copy.deepcopy(data)
        d['model_run'] = [{'record': f'결과/응답_기록/{digest}.json', 'request_hash': digest, 'model': '채팅(모델 이름 모름)', 'method': '채팅으로 받음', 'reused_from': None}]
        out[fname] = d
    return out


def record_md(course, p5, p6, own, reviews, scores, changes, selected):
    """강사 판 검토_기록.md(결과/검토_기록.md 빈 틀의 칸 그대로)."""
    practical = course == '실전반'
    rows_rev = []
    for stem, rv in sorted(reviews.items()):
        use = {'현행': '작업 근거', '폐기': '지난 기록 해석에만', '개정 요청(미승인)': '작업 근거 아님(승인 전)', '보충': '기존 문서에 더함(대체 아님)',
               '참고(제조사)': '사내 기준과 다르게 정한 항목은 사내 기준', '참고(스캔본)': '사내 기준과 다르게 정한 항목은 사내 기준'}[rv['doc_status']]
        rows_rev.append(f'| {rv["doc_id"]} {rv["rev"]} | {rv["doc_status"]} | {use} | 자료/DC-01_문서관리기준.md 17~23줄(상태의 뜻) |')
    p5_text = {'가': 'SR-04 제4조 ①②를 R4 전체(네 후보)의 근거로', '나': 'SR-04 제4조 ①②는 운전 중 제어 후보의 근거로만 — 작업지시 후보의 R4는 근거 없음', '다': 'SR-04 제4조 해석을 안전관리 담당에게 받기 전까지 보류'}[p5]
    p6_text = {'가': '사내 기준이 정하지 않은 제조사 항목(코어 상태 확인 · 코어 교체 · 유온 차)은 보류', '나': '사내 기준이 정하지 않은 제조사 항목을 까닭을 적고 채택'}[p6]
    changed = {'가': 'R4 일치 — 조건표 출처 칸 고침 요청', '나': 'R4 불일치 — 조건표 변경 요청(SOP-COOL-14 빼기)', '다': 'R4 보류 — 안전관리 담당 해석 요청'}[p5]
    lines = ['# 문서 지식 검토 기록', '', '> 강사 참조 — 두 번째 구현(규칙 기반)의 후보를 갈래 규칙으로 검토한 판이다.', '', '## 목표와 질문', '',
             '핀 세척(SOP-COOL-14) 작업지시 전에 작업 조건과 판정에 쓴 조건의 원문 근거를 확인하고, 같은 기능이 다른 문서에서 빠뜨리거나 지어내지 않는지 센다.', '',
             '## 이 답을 쓰는 사람과 쓰는 곳', '', '설비보전팀장(작업지시 승인)' + (' · 보전 야간조(작업 준비)' if practical else '') + '.', '']
    if practical:
        lines += ['## 이 사건의 작업', '', f'- 작업: SOP-COOL-14 쿨러 핀 세척', f'- 근거(파일 · 줄): {selected["basis"] if selected else "자료/HM-8_매뉴얼.md 73~79줄"}', '']
    lines += ['## 판 기준 — 어느 문서 · 판을 무엇에 쓰는가', '', '| 문서 · 판 | 상태 | 이번 검토에서 쓰는 곳 | 근거(파일 · 줄) |', '|---|---|---|---|', *rows_rev, '',
              '## 정한 것', '', '| 지점(종류) | 고른 것 | 근거(파일 · 줄) | 이 선택으로 바뀌는 답 |', '|---|---|---|---|',
              f'| 조건의 근거 | {p5_text} | 자료/SR-04_설비안전규정_발췌.txt 10 · 11줄 | {changed} |',
              f'| 사내 문서와 제조사 지침 | {p6_text} | 자료/OEM-HPP45A_정비지침_영한.md 107 · 114 · 116줄, 7줄(머리말) | 핀 세척의 준비 · 완료 항목 수 |', '',
              '## 기대 항목 — 실행 전에 원문에서', '', '- 기대 칸을 쓴 시각: 2026-10-28 08:30', '',
              '| 문서 · 판 · 절 · 줄 | 종류 | 원문(그대로) | 실제 후보 | 차이 종류 · 고친 점 |', '|---|---|---|---|---|']
    for name, sc in sorted(scores.items()):
        lines.append(f'| {name} | 기대 {sc["expected"]}개 | 문서별 기대 항목(강사 참조 기대 항목) | 맞은 {sc["matched"]}개 | 누락 {len(sc["missing"])}개 — 검토에서 원문 문장으로 더함 |')
    lines += ['', '## 조건 근거 대조', '', '| 조건(rule_id) | 근거를 찾은 문서 · 판 · 절 · 줄 | match | 까닭 | 요청할 것 |', '|---|---|---|---|---|']
    for stem, rv in sorted(reviews.items()):
        for link in rv.get('rule_links', []):
            req = '조건표 변경 요청' if link['match'] == '불일치' else ('원본 확인 요청' if link['match'] == '원문 없음' else ('안전관리 담당 해석 요청' if link['match'] == '보류' else '출처 칸 고침'))
            lines.append(f'| {link["rule_id"]} | {rv["doc_id"]} {rv["rev"]} (후보 {", ".join(link["candidates"]) or "없음"}) | {link["match"]} | {link["note"][:60]} | {req} |')
    lines += ['', '## 다른 문서에 적용', '', '| 문서 · 판 | 후보 수 | 누락 | 근거 없는 생성 | 고친 점 | 고친 뒤 다시 센 수 |', '|---|---|---|---|---|---|']
    for name, sc in sorted(scores.items()):
        lines.append(f'| {name} | {sc["candidates"]} | {len(sc["missing"])} | {len(sc["value_differs_from_text"])} | 값이 글과 다른 후보는 수정 · 빠진 것은 더함 | 누락 0 |')
    lines += ['', '## 같은 요청을 한 번 더 보낸 결과', '', '| 조각 | 첫 응답 기록 | 다시 보낸 응답 기록 | 다른 점 |', '|---|---|---|---|',
              '| 해당 없음 | 이 판은 모델 응답이 아니라 규칙 실행 | 강사 추출 두 번(강사_추출/run1 · run2)의 차이는 사건_갈래표.md 「강사 추출 실행」 | 규칙 실행이라 해당 없음 |', '']
    if practical:
        lines += ['## 검사가 잡는지 확인', '', '| 일부러 바꾼 곳(사본에서) | check.py가 짚은 줄 | 되돌린 뒤 출력 |', '|---|---|---|',
                  '| 인용 한 글자 | 검사기_확인.json 「extract」 01 | 계약 검사 통과 |', '']
    lines += ['## 남은 질문', '', '- 트립 뒤 복귀(R5 출처 HM-9.4) — 9장 스캔본에 9-7쪽이 없어 원본 확인 요청.', '', '## 저장 기록', '',
              '- 기준일: 2026-10-28', '- 저장 시점: 2026-10-28 11:00', '- 확인하지 못한 점: 학생 실행(장난감 시험 · 리허설)의 후보에 같은 결정을 건 결과 — 수업 모델 답의 후보에 건 결과는 사건_갈래표.md 「강사 추출 실행」']
    return '\n'.join(lines) + '\n'


def student_check(course, lab, cands, judged, p5, p6, own, record):
    """학생 검사기를 사본에서 실행 — 후보 · 검토 계약 통과와 단계 남은 것 0."""
    ek = COURSES[course][0]
    with tempfile.TemporaryDirectory() as tmp:
        t = copy_lab(lab, tmp)
        fx = fixture(t, cands)
        if own:
            table, sop = BR.own_table(own)
            (t/'결과/내_입력').mkdir(parents=True, exist_ok=True)
            (t/'결과/내_입력/조건표.csv').write_text(table, encoding='utf-8')
            (t/'결과/내_입력/sop.json').write_text(sop, encoding='utf-8')
            (t/'결과/내_입력'/BD.JUDGED[ek]).write_bytes((lab/'입력'/BD.JUDGED[ek]).read_bytes())
        out, _ = BR.build(t, fx, judged, p5, p6, course, own)
        for rel, data in out.items():
            if rel.startswith(('후보/', '검토/')) or rel == '선택작업_조건.json':
                (t/'결과'/rel).parent.mkdir(parents=True, exist_ok=True)
                (t/'결과'/rel).write_bytes(data)
        (t/'결과/prompt.md').write_text(PROMPT, encoding='utf-8')
        (t/'결과/검토_기록.md').write_text(record, encoding='utf-8')
        files = sorted(str(p.relative_to(t)) for p in (t/'결과/후보').glob('*.json')) + sorted(str(p.relative_to(t)) for p in (t/'결과/검토').glob('*.json'))
        rc1, o1 = run_py(t, 'check.py', *files)
        rc2, o2 = run_py(t, 'check.py')
    return {'contract_rc': rc1, 'stage_rc': rc2, 'stage_tail': o2.strip().splitlines()[-3:], 'contract_errors': [l for l in o1.splitlines() if l.startswith('  - ')][:10]}


def student_check_model(course, lab, run, out, record):
    """수업 모델 실행의 후보로 만든 갈래 — 사본에 그 실행의 응답 기록 · 폴더 표지를 그대로 두고 학생 검사기를 돌린다(fixture 아님)."""
    with tempfile.TemporaryDirectory() as tmp:
        t = copy_lab(lab, tmp)
        for p in sorted((run/'결과/응답_기록').glob('*.json')) + [run/'결과/폴더_표지.txt']:
            (t/p.relative_to(run)).parent.mkdir(parents=True, exist_ok=True)
            (t/p.relative_to(run)).write_bytes(p.read_bytes())
        for rel, data in out.items():
            if rel.startswith(('후보/', '검토/')) or rel == '선택작업_조건.json':
                (t/'결과'/rel).parent.mkdir(parents=True, exist_ok=True)
                (t/'결과'/rel).write_bytes(data)
        (t/'결과/prompt.md').write_text(PROMPT, encoding='utf-8')
        (t/'결과/검토_기록.md').write_text(record, encoding='utf-8')
        files = sorted(str(p.relative_to(t)) for p in (t/'결과/후보').glob('*.json')) + sorted(str(p.relative_to(t)) for p in (t/'결과/검토').glob('*.json'))
        rc1, o1 = run_py(t, 'check.py', *files)
        rc2, o2 = run_py(t, 'check.py')
    return {'contract_rc': rc1, 'stage_rc': rc2, 'stage_tail': o2.strip().splitlines()[-3:], 'contract_errors': [l for l in o1.splitlines() if l.startswith('  - ')][:10]}


def model_runs(model_dirs, oracle):
    """강사 추출 실행마다 — 점수, 갈래(판정 랩 입력의 6갈래)별 결정 수 · rule_links · 판정 변화 · 선택 작업 조건 수 · 학생 검사기, 두 번째 구현 갈래와의 대조. 두 실행 사이의 차이."""
    out, runs = {}, []
    for d in model_dirs:
        d = Path(d).resolve()
        run = d.parents[1]
        name = IE_label(run)
        cands = {p.name: json.loads(p.read_text(encoding='utf-8')) for p in sorted(d.glob('*.json'))}
        recs = [json.loads(p.read_text(encoding='utf-8')) for p in sorted((run/'결과/응답_기록').glob('*.json'))]
        sent = [r for r in recs if r.get('method') == '모델 서버']
        tokens = {k: sum((r.get('usage') or {}).get(k) or 0 for r in sent) for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')}
        when = max(c['generated_at'] for c in cands.values())
        entry = {'records': len(recs), 'sent': len(sent), 'unusable': sum(1 for r in recs if r.get('usable') is False), 'models': sorted({r['model'] for r in sent}),
                 'response_models': sorted({str(r.get('response_model')) for r in sent}), 'tokens': tokens,
                 'finish_length': sum(1 for r in sent if r.get('finish_reason') == 'length'),
                 'candidates': {k: len(v['candidates']) for k, v in cands.items()}, 'unlocated': {k: len(v['unlocated']) for k, v in cands.items()},
                 'warnings': {k: len(v['warnings']) for k, v in cands.items()}, 'branches': {}}
        lab = BD.LABS['integrated-04-extract']
        sc = BR.score({c['source_file']: c for c in cands.values()}, BR.expected(lab))
        entry['score'] = {n: {k: (len(v) if isinstance(v, list) else v) for k, v in x.items()} for n, x in sc.items()}
        for course, (ek, _) in COURSES.items():
            lab = BD.LABS[ek]
            judged = json.loads((lab/'입력'/BD.JUDGED[ek]).read_text(encoding='utf-8'))
            sizes = {}
            for p5 in BR.P5:
                for p6 in BR.P6:
                    bname = f'추출_{course}_{p5}-{p6}'
                    built, reviews = BR.build(lab, cands, judged, p5, p6, course, reviewed_at=when)
                    selected = json.loads(built['선택작업_조건.json']) if '선택작업_조건.json' in built else None
                    record = record_md(course, p5, p6, None, reviews, sc, json.loads(built['판정_변화.json']), selected)
                    chk = student_check_model(course, lab, run, built, record)
                    dec = {}
                    for rv in reviews.values():
                        for c in rv['candidates']:
                            dec[c['decision']] = dec.get(c['decision'], 0) + 1
                    links = {l['rule_id']: l['match'] for rv in reviews.values() for l in rv.get('rule_links', [])}
                    changes = json.loads(built['판정_변화.json'])
                    sizes[bname] = {k: len(v) for k, v in selected.items() if isinstance(v, list)} if selected else None
                    same = oracle[bname]
                    entry['branches'][bname] = {'decisions': dec, 'rule_links': links, 'judge_changes': changes['changed'], 'selected': sizes[bname],
                                                'reviewer_added': sum(1 for rv in reviews.values() for c in rv['candidates'] if c['origin'] == 'reviewer'),
                                                'checker': {'contract': '통과' if chk['contract_rc'] == 0 else '실패', 'stage': '남은 것 0' if chk['stage_rc'] == 0 else '남은 것 있음'},
                                                'same_as_rules': {'rule_links': links == same['rule_links'], 'judge_changes': changes == same['judge_changes']}}
                    if chk['contract_rc'] or chk['stage_rc']:
                        fail(f'강사 추출 {name} {bname}: 학생 검사기 — 계약 rc {chk["contract_rc"]} · 단계 rc {chk["stage_rc"]} {chk["contract_errors"]} {chk["stage_tail"]}')
                    if links != same['rule_links'] or changes != same['judge_changes']:
                        fail(f'강사 추출 {name} {bname}: 갈래 판정이 두 번째 구현 후보의 갈래와 다름 — rule_links {links} / {same["rule_links"]} · 판정 변화 {changes["changed"]} / {same["judge_changes"]["changed"]}')
            if course == '실전반' and len({json.dumps(v, sort_keys=True) for v in sizes.values()}) < 3:
                fail(f'강사 추출 {name} {course}: 갈래마다 선택 작업 조건이 충분히 갈리지 않음 {sizes}')
        out[name] = entry
        runs.append((name, run, cands))
    diff = {}
    if len(runs) >= 2:
        (n1, r1, c1), (n2, r2, c2) = runs[:2]
        per_doc = {}
        for f in sorted(set(c1) | set(c2)):
            q1 = {X.squash(c['quote']) for c in c1.get(f, {}).get('candidates', [])}
            q2 = {X.squash(c['quote']) for c in c2.get(f, {}).get('candidates', [])}
            per_doc[f] = {'n1': len(c1.get(f, {}).get('candidates', [])), 'n2': len(c2.get(f, {}).get('candidates', [])), 'both': len(q1 & q2), 'only1': len(q1 - q2), 'only2': len(q2 - q1)}
        chunks = IE.compare_runs(BD.LABS['integrated-04-extract'], r1, r2)
        if chunks['all']['chunks'] != chunks['chunks_first'] or not chunks['task']:
            fail(f'두 강사 추출 실행 {n1} · {n2}: 짝지은 조각 {chunks["all"]["chunks"]} · 첫 실행 조각 {chunks["chunks_first"]}')
        diff = {'runs': [n1, n2], 'per_doc': per_doc, 'chunks': chunks}
    return out, diff


def IE_label(path):
    path = Path(path).resolve()
    return path.relative_to(HERE).as_posix() if path.is_relative_to(HERE) else path.name


def extraction(model_dirs):
    results = {'score': {}, 'branches': {}, 'model_candidates': {}}
    for course, (ek, _) in COURSES.items():
        lab = BD.LABS[ek]
        judged = json.loads((lab/'입력'/BD.JUDGED[ek]).read_text(encoding='utf-8'))
        cands = {k: v for k, v in X.extract_all(lab).items() if v['source_file'] in BR.TARGETS}
        items = BR.expected(lab)
        scores = BR.score({d['source_file']: d for d in cands.values()}, items)
        results['score'][course] = scores
        runs = [(p5, p6, None) for p5 in BR.P5 for p6 in BR.P6] + [(p5, '가', own) for own in BR.OWN for p5 in BR.P5]
        for p5, p6, own in runs:
            name = f'추출_{course}_' + (f'내입력{own}_' if own else '') + f'{p5}-{p6}'
            out, reviews = BR.build(lab, cands, judged, p5, p6, course, own)
            dest = OUTDIR/name
            if dest.exists():
                shutil.rmtree(dest)
            for rel, data in out.items():
                target = (OUTDIR/f'후보_{course}'/rel.split('/', 1)[1]) if rel.startswith('후보/') else dest/rel   # 후보는 갈래와 상관없이 같다 — 반마다 한 벌
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            changes = json.loads(out['판정_변화.json'])
            selected = json.loads(out['선택작업_조건.json']) if '선택작업_조건.json' in out else None
            record = record_md(course, p5, p6, own, reviews, scores, changes, selected)
            (dest/'검토_기록.md').write_text(record, encoding='utf-8')
            chk = student_check(course, lab, cands, judged, p5, p6, own, record)
            if chk['contract_rc'] != 0 or chk['stage_rc'] != 0:
                fail(f'{name}: 학생 검사기 — 계약 rc {chk["contract_rc"]} · 단계 rc {chk["stage_rc"]} {chk["contract_errors"]} {chk["stage_tail"]}')
            dec = {}
            for rv in reviews.values():
                for c in rv['candidates']:
                    dec[c['decision']] = dec.get(c['decision'], 0) + 1
            results['branches'][name] = {
                'decisions': dec, 'rule_links': {l['rule_id']: l['match'] for rv in reviews.values() for l in rv.get('rule_links', [])},
                'judge_changes': changes, 'selected': ({k: len(v) for k, v in selected.items() if isinstance(v, list)} if selected else None),
                'checker': {'contract': '통과' if chk['contract_rc'] == 0 else '실패', 'stage': '남은 것 0' if chk['stage_rc'] == 0 else '남은 것 있음'}}
        # 갈래가 실제로 갈리는가 — 판정 변화 · 선택 작업 조건 수가 갈래마다 다르다
        if course == '실전반':
            sizes = {n: v['selected'] for n, v in results['branches'].items() if n.startswith(f'추출_{course}_') and '내입력' not in n}
            if len({json.dumps(v, sort_keys=True) for v in sizes.values()}) < 3:
                fail(f'{course}: 갈래마다 선택 작업 조건이 충분히 갈리지 않음 {sizes}')
        base = results['branches'][f'추출_{course}_나-가']['judge_changes']
        if [c['event'] for c in base['cases']] != ['ALT-hyd02-0171-051f']:
            fail(f'{course}: R4 하나로 SOP-COOL-14가 빠진 사례가 0171-051f 하나가 아님 — {base}')
    results['model_candidates'], results['model_runs_diff'] = model_runs(model_dirs, results['branches'])
    return results


def instructor_path():
    """강사 추출 실행 경로를 모델 없이 시험 — 두 번째 구현의 후보를 답 글로 넣어 후보 변환 · 인용 찾기가 도는지, 지어낸 인용이 unlocated로 가는지."""
    lab = BD.LABS['integrated-04-extract']
    out = {}
    for row in X.read_register(lab):
        if row['파일'] not in BR.TARGETS:
            continue
        text, _ = X.decode((lab/'자료'/row['파일']).read_bytes())
        orc = X.extract(lab, row)
        body = {'candidates': [{k: c[k] for k in c if k in ('section', 'procedure', 'kind', 'text', 'quote', 'refs', 'order', 'value', 'value_max', 'unit', 'comparator', 'value_text')}
                               for c in orc['candidates']] + [{'section': '머리말', 'procedure': None, 'kind': 'precondition', 'text': '지어낸 문장', 'quote': '원문에 없는 문장입니다', 'refs': []}]}
        reply = {'file': '결과/응답_기록/시험.json', 'request_hash': '시험', 'model': '(모델 없음 — 경로 시험)', 'method': '경로 시험', 'response_text': json.dumps(body, ensure_ascii=False)}
        c, u, w, r = S.to_candidates(row, text, [reply])
        out[row['파일']] = {'located': len(c), 'unlocated': len(u), 'oracle': len(orc['candidates'])}
        if len(c) != len(orc['candidates']) or len(u) != 1:
            fail(f'강사 추출 경로 {row["파일"]}: 찾은 인용 {len(c)} · 못 찾음 {len(u)} (기대 {len(orc["candidates"])} · 1)')
    out['chunks'] = sum(len(S.split_chunks(X.decode((lab/'자료'/r['파일']).read_bytes())[0])) for r in X.read_register(lab) if r['파일'] in BR.TARGETS)
    out['folder_limit'] = LLM.MAX_SENT
    if out['chunks'] * 2 + 1 > LLM.MAX_SENT:     # 연결 확인 한 번 + 조각 전부를 한 번 고쳐 다시 보내도 상한 안
        fail(f'강사 추출 조각 {out["chunks"]}개 — 고쳐 한 번 더 보내면 {out["chunks"] * 2 + 1}번으로 llm_client 안내용 상한 {LLM.MAX_SENT}개를 넘음')
    return out


# ───────────── 4. 그래프 — 실제 Neo4j ─────────────
def docker(*args):
    return subprocess.run(['docker', *args], capture_output=True, text=True)


def graph_record(course, p7, counts, reviews, answers, qrows, invariance):
    practical = course == '실전반'
    L = ['# 온톨로지 구축 기록', '', '> 강사 참조 — 지점7 ' + p7 + ' 갈래의 실제 실행 기록이다.', '', '## 목표와 질문', '',
         ('핀 세척 작업 확인 카드를 원문 · 기록으로 만들고 다른 작업 · 제공되지 않은 것 · 반복 적재를 확인한다.' if practical else
          '검토한 문서 지식을 기존 ID에 잇고 질문 다섯에 원문대로 답하는지 확인한다.'), '', '## 이 답을 쓰는 사람과 쓰는 곳', '',
         ('보전 야간조 · 설비보전팀장.' if practical else '설비보전팀장 · 다음 실습의 에이전트.'), '', '## 정한 것', '',
         '| 지점(종류) | 고른 것 | 근거(파일 · 줄) | 이 선택으로 바뀌는 답 |', '|---|---|---|---|',
         ('| 다른 문서의 조건 | PM-2.4 예정된 정비 시간을 핀 세척 준비 조건으로 잇는다 | 자료/PM-02_정기점검표.md 30줄 · 자료/HM-8_매뉴얼.md 66줄 | 핀 세척 준비에 「생산 오더 없는 시간 — MES 계획」이 생김 |' if p7 == '가' else
          '| 다른 문서의 조건 | 잇지 않는다(PM-02는 정기 정비 범위) | 자료/PM-02_정기점검표.md 10 · 30줄 | 핀 세척 준비는 HM-8.7 승인 · 정지 · 잠금만 |'), '']
    if practical:
        L += ['## 카드 항목별 기대 — 카드를 만들기 전에 원문 · 검토 결과 · 기록에서', '', '- 기대 칸을 쓴 시각: 2026-10-28 13:00', '',
              '| 카드 항목 | 기대(근거 파일 · 줄 · 후보 id · 기록 번호) | 실제 카드 | 같음 · 다름과 까닭 |', '|---|---|---|---|']
        L += [f'| {k} | {v} | {answers.get(k, "")} | 같음 |' for k, v in qrows]
    else:
        L += ['## 질문별 기대 답 — 조회 전에 원문 · 검토 결과에서', '', '- 기대 칸을 쓴 시각: 2026-10-28 13:00', '',
              '| 질문 | 기대 답(근거 파일 · 줄 · 후보 id) | 실제 조회 결과 | 같음 · 다름과 까닭 |', '|---|---|---|---|']
        L += [f'| {k} | {v} | {answers.get(k, "")} | 같음 |' for k, v in qrows]
    L += ['', '## 스키마 확장', '', '| 새 종류 · 관계 | 뜻 | 잇는 기존 종류 | 근거 |', '|---|---|---|---|']
    for name, spec in G.SCHEMA_EXT['classes'].items():
        L.append(f'| {name} | {spec["meaning"]} | — | 문서 목록 · 검토 결과 |')
    for name, spec in G.SCHEMA_EXT['relations'].items():
        L.append(f'| {name} | {spec.get("note", "연결")} | {spec["to"] if isinstance(spec["to"], str) else " · ".join(spec["to"])} | 검토 결과 |')
    L += ['', '## 입력 문서와 검토 결과', '', '| 검토 결과 파일 | 문서 · 판 · 상태 | SHA-256 앞 12자리 | 적재한 승인 후보 수 | 적재하지 않은 후보 수(보류 · 제외) |', '|---|---|---|---|---|']
    for fname, rv in reviews:
        ok = sum(1 for c in rv['candidates'] if c['status'] == 'approved')
        L.append(f'| {fname} | {rv["doc_id"]} {rv["rev"]} {rv["doc_status"]} | {rv["source_sha256"][:12]} | {ok} | {len(rv["candidates"]) - ok} |')
    L += ['', '## 적재 수', '', '| 시점 | 노드 수 | 관계 수 | 확인한 것 |', '|---|---|---|---|']
    names = ['설비 모델 · 조치 기준 적재 뒤', '첫 적재 뒤', '같은 적재 다시'] + ([] if practical else ['다른 문서 추가 뒤'])
    for n in names:
        nodes, rels = counts[n]
        L.append(f'| {n} | {nodes} | {rels} | count 출력 |')
    if not practical:
        L += ['', '## 다른 문서 추가 뒤 기존 연결', '', '| 확인한 기존 ID · 관계 | 추가 전 | 추가 뒤 | 같음 · 다름 |', '|---|---|---|---|',
              f'| 앞서 적재한 노드 전부(id · 속성) | {invariance["nodes_before"]} | {invariance["nodes_kept"]} | {"같음" if invariance["nodes_before"] == invariance["nodes_kept"] else "다름"} |',
              f'| 앞서 적재한 관계 전부 | {invariance["rels_before"]} | {invariance["rels_kept"]} | {"같음" if invariance["rels_before"] == invariance["rels_kept"] else "다름"} |']
    L += ['', '## ' + ('다른 작업 · 제공되지 않은 것' if practical else '보류 후보 · 제공되지 않은 것 조회'), '', '| 물은 것 | 조회문 · 명령 | 결과 | 원문 · 목록 근거 |', '|---|---|---|---|',
          f'| 보류 후보 | query.cypher HOLD | {answers["HOLD"]} | 입력/검토결과/ 보류 후보 |',
          f'| HYD-04 냉각 정비 | query.cypher Q5a | {answers["Q5a"]} | 자료/문서_목록.csv HPP-45B 행(파일 없음) |',
          f'| 트립 뒤 복귀 절 | query.cypher Q5b | {answers["Q5b"]} | 자료/HM-9장_스캔본.txt 15줄(목차만) |']
    if practical:
        L.append(f'| 다른 작업 카드 | query.cypher CARD($sop=SOP-COOL-11) | {answers.get("OTHER", "")} | 입력/조치검토결과.json review.top |')
    L += ['', '## 답할 수 있는 것과 없는 것', '', '| 질문 | ' + ('그래프로 답함 · 현재 값 필요 · 승인 필요 · 공급 정보 · 원문에 없음' if practical else '그래프로 답함 · 현재 값 필요 · 추가 자료 필요 · 원문에 없음') + ' | 근거(원천 이름 · 파일) |', '|---|---|---|']
    L += (['| 준비 · 금지 · 순서 · 완료 · 승인 역할 | 그래프로 답함 | 입력/검토결과 · sop.json |', '| 부품 공급 조건(공급사 · 부품) | 공급 정보 | 입력/모델/graph.json 공급 관계 |',
           '| 작업 직전 CE · TS1 · PLC 모드 | 현재 값 필요 | 시계열 |', '| 그날의 부품 재고 | 현재 값 필요 | ERP(전사 자원 관리 시스템) |', '| 작업지시 승인 | 승인 필요 | 설비보전팀장 |',
           '| 트립 뒤 복귀 조건 | 원문에 없음 | 9장 9-7쪽 없음 |'] if practical else
          ['| 질문 1 · 2 · 4 | 그래프로 답함 | 입력/검토결과 · sop.json · 조건표 |', '| 질문 3 | 현재 값 필요 | 시계열(CE · TS1)' + (' · MES 계획' if p7 == '가' else '') + ' |',
           '| 질문 5 | 원문에 없음 | 문서 목록 HPP-45B 행 · 9장 9-7쪽 없음 |'])
    L += ['', '## 남은 질문', '', '- 남은_질문.json 참고.', '', '## 저장 기록', '', '- 랩 DB 주소(인증값 제외): 127.0.0.1(이 폴더 전용)', '- 기준일: 2026-10-28', '- 저장 시점: 2026-10-28 15:00',
          '- 확인하지 못한 점: VS Code 화면 · 학교 PC']
    return '\n'.join(L) + '\n'


def snapshot(LC):
    res = LC.cypher([('MATCH (n) RETURN n.id, properties(n)', {}), ('MATCH (a)-[r]->(b) RETURN a.id, type(r), b.id, properties(r)', {})])
    nodes = {r['row'][0]: json.dumps(r['row'][1], sort_keys=True, ensure_ascii=False) for r in res[0]['data']}
    rels = {json.dumps(r['row'], sort_keys=True, ensure_ascii=False) for r in res[1]['data']}
    return nodes, rels


def counts_of(LC):
    res = LC.cypher([('MATCH (n) RETURN count(n)', {}), ('MATCH ()-[r]->() RETURN count(r)', {})])
    return res[0]['data'][0]['row'][0], res[1]['data'][0]['row'][0]


def graph_run(course, p7, trials=False):
    ek, gk = COURSES[course]
    practical = course == '실전반'
    lab = BD.GLABS[gk]
    result = {'p7': p7}
    trial_out = []
    with tempfile.TemporaryDirectory() as tmp:
        t = copy_lab(lab, tmp)
        container = None
        try:
            rc, out = run_py(t, 'lab_db.py', '--no-open')
            if rc:
                fail(f'{course} 지점7 {p7}: lab_db.py 실패 {out[-300:]}')
                return result, trial_out
            container = json.loads((t/'랩_연결.json').read_text(encoding='utf-8'))['container']
            LC = module(t/'lab_cypher.py', f'lab_cypher_{course}_{p7}')
            rc, out = run_py(t, 'lab_cypher.py', 'model')
            if rc:
                fail(f'{course} 지점7 {p7}: lab_cypher model 실패 {out[-300:]}')
                return result, trial_out
            counts = {'설비 모델 · 조치 기준 적재 뒤': counts_of(LC)}
            model_snapshot = snapshot(LC)
            sop = json.loads((t/'입력/sop.json').read_text(encoding='utf-8'))
            reviews = [(f.name, json.loads(f.read_text(encoding='utf-8'))) for f in sorted((t/'입력/검토결과').glob('*_검토.json'))]
            phase1 = [(n, d) for n, d in reviews if practical or d['doc_id'] not in G.PHASE2]
            phase2 = [] if practical else [(n, d) for n, d in reviews if d['doc_id'] in G.PHASE2]
            (t/'결과/schema_ext.json').write_text(json.dumps(G.SCHEMA_EXT, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            (t/'결과/load.cypher').write_text(G.load_cypher(t, phase1, sop, '나', p7), encoding='utf-8')
            if phase2:
                (t/'결과/load_more.cypher').write_text(G.load_cypher(t, phase2, sop, '나', p7, with_register=False), encoding='utf-8')
            (t/'결과/query.cypher').write_text(G.query_file(), encoding='utf-8')
            rc, out = run_py(t, 'lab_cypher.py', 'run', '결과/load.cypher')
            if rc:
                fail(f'{course} 지점7 {p7}: 적재 실패 {out[-400:]}')
                return result, trial_out
            counts['첫 적재 뒤'] = counts_of(LC)
            run_py(t, 'lab_cypher.py', 'run', '결과/load.cypher')
            counts['같은 적재 다시'] = counts_of(LC)
            if counts['첫 적재 뒤'] != counts['같은 적재 다시']:
                fail(f'{course} 지점7 {p7}: 같은 적재 다시 수가 다름 {counts}')
            # 앞 단계 판(모델 · SOP 구조 · 조건표)의 노드 속성이 적재로 바뀌지 않았다
            nodes_now, rels_now = snapshot(LC)
            changed = [k for k, v in model_snapshot[0].items() if nodes_now.get(k) != v]
            if changed:
                fail(f'{course} 지점7 {p7}: 적재가 앞 단계 판 노드를 바꿈 {changed[:5]}')
            invariance = {}
            if phase2:
                before = (nodes_now, rels_now)
                run_py(t, 'lab_cypher.py', 'run', '결과/load_more.cypher')
                counts['다른 문서 추가 뒤'] = counts_of(LC)
                after = snapshot(LC)
                kept = sum(1 for k, v in before[0].items() if after[0].get(k) == v)
                invariance = {'nodes_before': len(before[0]), 'nodes_kept': kept, 'rels_before': len(before[1]), 'rels_kept': len(before[1] & after[1])}
                if kept != len(before[0]) or invariance['rels_kept'] != len(before[1]):
                    fail(f'{course} 지점7 {p7}: 다른 문서 추가가 앞의 노드 · 관계를 바꿈 {invariance}')
                added = sum(1 for _, d in phase2 for c in d['candidates'] if c['status'] == 'approved')
                kn = LC.cypher([('MATCH (k:Knowledge) RETURN count(k)', {})])[0]['data'][0]['row'][0]
                if kn != sum(1 for _, d in reviews for c in d['candidates'] if c['status'] == 'approved'):
                    fail(f'{course} 지점7 {p7}: 지식 노드 {kn}개가 승인 후보 수와 다름')
                result['added_knowledge'] = added
            # 독립 기대 — 검토 결과 JSON에서 센 수
            approved = sum(1 for _, d in phase1 + phase2 for c in d['candidates'] if c['status'] == 'approved')
            hold_ids = [f'{G.rev_id(d["doc_id"], d["rev"])}:{c["id"]}' for _, d in reviews for c in d['candidates'] if c['status'] != 'approved']
            params = {'asset': 'HYD-02', 'sop': 'SOP-COOL-14', 'doc': 'OEM-HPP45A-MM', 'ref': 'HM-9.4', 'ids': hold_ids}
            ans = {}
            res = {k: [r['row'] for r in LC.cypher([(qt, params)])[0]['data']] for k, qt in G.QUERIES.items()}
            kn = LC.cypher([('MATCH (k:Knowledge) RETURN count(k)', {})])[0]['data'][0]['row'][0]
            if kn != approved:
                fail(f'{course} 지점7 {p7}: 지식 노드 {kn}개 ≠ 승인 후보 {approved}개')
            q1 = [r for r in res['Q1'] if r[0] == 'SOP-COOL-14']
            pm24 = [r for r in q1 if r[4] == 'PM-02' and r[6] == 'PM-2.4']
            oem = [r for r in q1 if r[4] == 'OEM-HPP45A-MM']
            if (p7 == '가') != bool(pm24):
                fail(f'{course} 지점7 {p7}: 핀 세척 준비에 PM-2.4가 ' + ('없음' if p7 == '가' else '있음'))
            if not oem and (practical or phase2):
                fail(f'{course} 지점7 {p7}: 핀 세척에 제조사 지침 항목이 이어지지 않음')
            if any('Inspect the core' in (r[7] or '') or 'replace the core' in (r[7] or '') or 'cooler inlet and outlet' in (r[7] or '') for r in q1):
                fail(f'{course} 지점7 {p7}: 보류한 제조사 항목(코어 확인 · 교체 · 유온 차)이 그래프에 있음')
            q2 = {}
            for r in res['Q2']:
                q2.setdefault(r[0], set()).add(r[2])
            r123 = {None} if practical else {'일치'}      # 실전반은 이 작업(SOP-COOL-14)에 걸린 R4 · R5만 대조한다(R1~R3 근거 대조 없음)
            if q2.get('R4') != {'불일치'} or q2.get('R5') != {None} or not all(q2.get(x) == r123 for x in ('R1', 'R2', 'R3')):
                fail(f'{course} 지점7 {p7}: 규칙 근거 대조가 기대와 다름 {q2}')
            sensors = sorted(r[1] for r in res['Q3'] if r[0] == 'sensor')
            plan = [r for r in res['Q3'] if r[0] == 'plan']
            if sensors != ['HYD-02:CE'] or (p7 == '가') != bool(plan):
                fail(f'{course} 지점7 {p7}: 질문 3 현재 값이 기대와 다름 {res["Q3"]}')
            if res['HOLD'][0][0] != 0 or res['Q5a'][0][1] != 0 or res['Q5b'][0][1] != 0:
                fail(f'{course} 지점7 {p7}: 보류 · 미제공 조회 {res["HOLD"]} {res["Q5a"]} {res["Q5b"]}')
            if phase2:
                q4 = {r[2] for r in res['Q4']}
                if not {'HYD-01:rtn-filter', 'HYD-02:accumulator'} <= q4 or any(x.startswith('HYD-04') for x in q4):
                    fail(f'{course} 지점7 {p7}: 질문 4 — 제조사 지침이 걸린 대상 {sorted(q4)}')
            ans.update({'HOLD': f'{res["HOLD"][0][0]}건', 'Q5a': f'지식 {res["Q5a"][0][1]}건 — 결과 없음', 'Q5b': f'절 {res["Q5b"][0][1]}개 — 원문 절 미제공'})
            qrows = []
            if practical:
                questions = [{'item': '트립 뒤 복귀 조건(R5 출처 HM-9.4)', 'kind': '제공되지 않은 절', 'source': '자료/HM-9장_스캔본.txt 15줄', 'note': '9-7쪽 없음 — 원본 확인 요청'},
                             {'item': 'HPP-45B(HYD-04) 정비 지침', 'kind': '제공되지 않은 문서', 'source': '자료/문서_목록.csv', 'note': '제조사에 요청 중 — 파일 없음'}]
                sel = json.loads((t/'입력/검토결과/선택작업_조건.json').read_text(encoding='utf-8'))
                questions += [q for q in sel['remaining_questions'] if q['kind'] == '보류']
                row14 = LC.cypher([(G.QUERIES['CARD'], {'sop': 'SOP-COOL-14'})])[0]['data'][0]['row']
                row11 = LC.cypher([(G.QUERIES['CARD'], {'sop': 'SOP-COOL-11'})])[0]['data'][0]['row']
                (t/'결과/작업확인카드_SOP-COOL-14.md').write_text(G.card(row14, t, p7, questions[:2] + questions[2:5]), encoding='utf-8')
                (t/'결과/작업확인카드_SOP-COOL-11.md').write_text(G.card(row11, t, p7, questions[:1]), encoding='utf-8')
                ans['OTHER'] = 'SOP-COOL-11 카드 형식 통과'
                for k, v in [('준비 조건', 'HM-8 1.1 HM-8.7 · 제조사 지침 7' + (' · PM-02 PM-2.4' if p7 == '가' else '')), ('금지 · 제한', 'HM-8 1.1 「고압수는 쓰지 않는다」 · 제조사 「Do not use a high-pressure washer」'),
                             ('완료 기준', 'HM-8 1.1 CE 80 %'), ('작업 직전 확인할 현재 값', 'CE · TS1 · PLC 모드(시계열)' + (' · 생산 오더 없는 시간(MES)' if p7 == '가' else '')), ('승인', '설비보전팀장(HM-8.7)')]:
                    qrows.append((k, v))
                    ans[k] = '카드에 있음'
            else:
                questions = [{'item': '트립 뒤 복귀 조건(R5 출처 HM-9.4)', 'kind': '제공되지 않은 절', 'source': '자료/HM-9장_스캔본.txt 15줄', 'note': '9-7쪽 없음 — 원본 확인 요청'},
                             {'item': 'HPP-45B(HYD-04) 정비 지침', 'kind': '제공되지 않은 문서', 'source': '자료/문서_목록.csv', 'note': '제조사에 요청 중 — 파일 없음'},
                             {'item': '제조사 지침이 더한 코어 확인 · 교체 · 유온 차', 'kind': '보류', 'source': '입력/검토결과/OEM-HPP45A-MM_C_검토.json', 'note': 'HM-8 소유 부서 확인 전'}]
                for k, v, a in [('질문 1', 'SOP-COOL-11~15 · FAN-12의 단계 · 조건과 HM-8 1.1 · 제조사 지침 근거', f'핀 세척 근거 {len(q1)}행'),
                                ('질문 2', 'R1~R3 일치(HM-8 1.1), R4 불일치(SR-04 제4조), R5 원문 없음', '같음'), ('질문 3', 'HYD-02:CE(시계열)' + (' · MES 계획' if p7 == '가' else ''), ', '.join(sensors) + (' · MES' if plan else '')),
                                ('질문 4', 'HYD-01~03 리턴 필터 · 어큐뮬레이터 · 펌프 축 씰 · 작동유', f'{len(res["Q4"])}행'), ('질문 5', '결과 없음 · 원문 절 미제공', '결과 없음')]:
                    qrows.append((k, v))
                    ans[k] = a
            (t/'결과/남은_질문.json').write_text(json.dumps(questions, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            rc, out = run_py(t, 'lab_cypher.py', 'export', '결과/지식_내보내기.json')
            exported = json.loads((t/'결과/지식_내보내기.json').read_text(encoding='utf-8'))
            (t/'결과/구축_기록.md').write_text(graph_record(course, p7, counts, reviews, ans, qrows, invariance), encoding='utf-8')
            rc, out = run_py(t, 'check.py')
            result.update(counts={k: list(v) for k, v in counts.items()}, knowledge=kn, export={'nodes': len(exported['nodes']), 'rels': len(exported['rels']),
                          'labels': sorted({l for n in exported['nodes'] for l in n['labels']}), 'remaining_questions': len(exported['remaining_questions'])},
                          checker_rc=rc, checker_tail=out.strip().splitlines()[-2:], q2={k: sorted(map(str, v)) for k, v in q2.items()}, q3=res['Q3'],
                          pm24_in_preparation=bool(pm24), oem_rows=len(oem))
            if rc:
                fail(f'{course} 지점7 {p7}: 그래프 검사기 남은 것 {out[-900:]}')
            # 5회차가 읽는 내보내기 — 2회차 graph.json 꼴 · 문서 근거 · 원인 증거(집계 구간) · 남은 질문
            evid = [n for n in exported['nodes'] if 'Knowledge' in n['labels'] and n['props'].get('unit') in ('초', '분')]
            if not ({'Document', 'Revision', 'Section', 'Knowledge', 'Skill', 'Rule', 'Asset'} <= set(result['export']['labels'])) or not evid or not exported['remaining_questions']:
                fail(f'{course} 지점7 {p7}: 내보내기에 문서 근거 · 집계 구간 증거 · 남은 질문이 다 있지 않음 {result["export"]} 증거 {len(evid)}')
            result['export']['evidence_windows'] = sorted({f'{n["props"].get("value")} {n["props"].get("unit")}' for n in evid})
            if trials:
                trial_out = graph_trials(t, LC, course)
            if p7 == G.BASE_P7:
                keep = OUTDIR/f'그래프_{course}_{p7}'
                if keep.exists():
                    shutil.rmtree(keep)
                for rel in ['schema_ext.json', 'load.cypher', 'load_more.cypher', 'query.cypher', '남은_질문.json', '구축_기록.md', '작업확인카드_SOP-COOL-14.md', '작업확인카드_SOP-COOL-11.md', '지식_내보내기.json']:
                    if (t/'결과'/rel).is_file():
                        (keep/rel).parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(t/'결과'/rel, keep/rel)
            else:
                keep = OUTDIR/f'그래프_{course}_{p7}'
                if keep.exists():
                    shutil.rmtree(keep)
                keep.mkdir(parents=True)
                for rel in ['load.cypher', '구축_기록.md'] + (['작업확인카드_SOP-COOL-14.md'] if practical else []):
                    shutil.copy2(t/'결과'/rel, keep/rel)
        finally:
            if container:
                docker('rm', '-f', '-v', container)
                left = docker('ps', '-a', '-q', '--filter', f'name=^/{container}$').stdout.strip()
                result['container_removed'] = not left
                if left:
                    fail(f'{course} 지점7 {p7}: 컨테이너 {container}를 지우지 못함')
    return result, trial_out


def graph_trials(t, LC, course):
    """그래프 검사기 고의 손상 — 랩 DB가 켜진 채로 결과 파일 · DB를 하나씩 망가뜨리고 되돌린다."""
    practical = course == '실전반'
    out = []

    def trial(no, name, apply_, undo, needle):
        apply_()
        rc, text = run_py(t, 'check.py')
        undo()
        rc2, _ = run_py(t, 'check.py')
        caught = needle in text and (rc != 0 or needle.startswith('참고'))
        out.append({'no': no, 'trial': name, 'caught': caught, 'restored_pass': rc2 == 0, 'line': next((l.strip() for l in text.splitlines() if needle in l), '')[:160]})
        if not caught or rc2 != 0:
            fail(f'그래프 검사기 {course} {no} {name}: 잡음 {caught} · 되돌린 뒤 통과 {rc2 == 0}')

    def edit(rel, fn):
        p = t/'결과'/rel
        old = p.read_bytes()
        return (lambda: p.write_text(fn(old.decode('utf-8')), encoding='utf-8')), (lambda: p.write_bytes(old))

    def add_file(rel, text):
        p = t/'결과'/rel
        return (lambda: p.write_text(text, encoding='utf-8')), (lambda: p.unlink())

    def db_add(stmt, undo_stmt):
        return (lambda: LC.cypher([(stmt, {})])), (lambda: LC.cypher([(undo_stmt, {})]))

    hold = next(f'{G.rev_id(d["doc_id"], d["rev"])}:{c["id"]}' for f in sorted((t/'입력/검토결과').glob('*_검토.json')) for d in [json.loads(f.read_text(encoding='utf-8'))]
                for c in d['candidates'] if c['status'] == 'pending')
    hold_cid = hold.split(':', 1)[1]
    a, u = add_file('extra_load.cypher', 'MATCH (n) DETACH DELETE n;\n')
    trial('29', '전체 삭제', a, u, '전체를 지우는 문장')
    a, u = add_file('extra_load.cypher', "MATCH (k:Knowledge {id: 'x'}) DETACH DELETE k;\n")
    trial('32', '적재문 부분 삭제', a, u, '참고: extra_load.cypher')
    a, u = add_file('extra_load.cypher', f"MERGE (k:Knowledge {{id: '{hold}'}}) SET k.quote = 'x';\n")
    trial('34', '보류 후보 적재(적재 파일)', a, u, '승인(approved)이 아닌 후보 id')
    a, u = add_file('extra_load.cypher', "MATCH (c:Component {id: 'HYD-09:cooler'}) MERGE (k:Knowledge {id: 'K-x'})-[:APPLIES_TO]->(c);\n")
    trial('35', '없는 기존 ID', a, u, '기존 ID 꼴인데')
    a, u = db_add("MERGE (x:Section {id: 'HM-9@1.0#HM-9.4'})", "MATCH (x:Section {id: 'HM-9@1.0#HM-9.4'}) DETACH DELETE x")
    trial('36', '미제공 절을 노드로', a, u, '원문에 절 머리가 없는 절 표기')
    a, u = db_add("MERGE (x:Document {id: 'OEM-HPP45B-MM'})", "MATCH (x:Document {id: 'OEM-HPP45B-MM'}) DETACH DELETE x")
    trial('37', '받은 파일이 없는 문서를 노드로', a, u, '받은 파일이 없는 문서')
    a, u = db_add("MATCH (p:Part {id: 'P-CLR-CORE'}) MERGE (s:Stock {id: 'stock:P-CLR-CORE'}) SET s.on_hand = 2", "MATCH (s:Stock {id: 'stock:P-CLR-CORE'}) DETACH DELETE s")
    trial('38', '현재 재고 수를 그래프 속성으로', a, u, '현재 값(재고')
    a, u = db_add(f"MERGE (k:Knowledge {{id: 'K-hold'}}) SET k.candidate = '{hold_cid}'", "MATCH (k:Knowledge {id: 'K-hold'}) DETACH DELETE k")
    trial('39', '보류 후보를 랩 DB에(속성)', a, u, '승인(approved)이 아닌 후보')
    a, u = edit('지식_내보내기.json', lambda s: s.replace('"rels": [', '"rels": [\n    {"type": "X", "a": "없는-노드", "b": "HYD-02", "props": {}},', 1))
    trial('40', '내보내기 끝점 없음', a, u, '끝점이 없는 관계')
    a, u = edit('query.cypher', lambda s: s + "\nMATCH (k:Knowledge {id: 'x'}) DELETE k;\n")
    trial('41', '조회문에 DELETE', a, u, '조회문은 읽기만')
    # 33 기존 ID 연결 없음 — 새 DB에 잇지 않은 노드만 있을 때: 지금 그래프의 기존 ID 연결 관계를 잠시 떼어 본다
    snap = LC.cypher([("MATCH (k:Knowledge)-[r]->(t) WHERE NOT t:Section RETURN k.id, type(r), t.id, properties(r)", {}),
                      ("MATCH (t:Step)-[r:REFERS_TO]->(x) RETURN t.id, type(r), x.id, properties(r)", {}),
                      ("MATCH (v:Revision)-[r:HAS_SECTION]->(x) WHERE (v)<-[:HAS_REVISION]-() RETURN v.id, type(r), x.id, properties(r)", {})])
    keep = [r['row'] for res in snap for r in res['data']]

    def cut():
        LC.cypher([("MATCH (k:Knowledge)-[r]->(t) WHERE NOT t:Section DELETE r", {}), ("MATCH (:Step)-[r:REFERS_TO]->() DELETE r", {})])

    def restore():
        stmts = [(f"MATCH (a {{id: $a}}), (b {{id: $b}}) MERGE (a)-[r:`{rel}`]->(b) SET r += $p", {'a': x, 'b': y, 'p': p}) for x, rel, y, p in keep if rel != 'HAS_SECTION']
        for i in range(0, len(stmts), 200):
            LC.cypher(stmts[i:i + 200])
    trial('33', '기존 ID 연결 없음', cut, restore, '기존 ID와 하나도 이어지지 않았습니다')
    if practical:
        card = 'card_trial'
        base = (t/'결과/작업확인카드_SOP-COOL-14.md').read_text(encoding='utf-8')
        for no, name, fn, needle in [
                ('24', '카드 제목 없음', lambda s: s.replace('## 완료 기준\n', '## 끝 기준\n'), '제목 「## 완료 기준」 없음'),
                ('25', '카드 인용 변경', lambda s: s.replace('고압수는 쓰지 않는다', '고압수는 쓰지 말 것', 1), '그대로 없는 인용'),
                ('27', '인용 없는 항목', lambda s: s.replace('## 금지 · 제한\n\n', '## 금지 · 제한\n\n- 장갑을 낀다\n', 1), '「원문 인용」이 없음'),
                ('28', '빈 절', lambda s: re.sub(r'## 승인\n\n[^\n]+\n', '## 승인\n\n', s), '아래가 비어 있음'),
                ('42', '없는 품번', lambda s: s.replace('## 남은 질문\n\n', '## 남은 질문\n\n- P-CLR-CORE2 쿨러 코어를 미리 준비할지\n', 1), '없는 품번')]:
            a, u = edit('작업확인카드_SOP-COOL-14.md', fn)
            trial(no, name, a, u, needle)
        _ = card, base
    return out


# ───────────── 5. 추출 검사기 고의 손상 ─────────────
def extraction_trials(course):
    ek = COURSES[course][0]
    lab = BD.LABS[ek]
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        t = copy_lab(lab, tmp)
        cands = {k: v for k, v in X.extract_all(t).items() if v['source_file'] in BR.TARGETS}
        fx = fixture(t, cands)
        judged = json.loads((t/'입력'/BD.JUDGED[ek]).read_text(encoding='utf-8'))
        built, reviews = BR.build(t, fx, judged, *BR.BASE, course)
        for rel, data in built.items():
            if rel.startswith(('후보/', '검토/')) or rel == '선택작업_조건.json':
                (t/'결과'/rel).parent.mkdir(parents=True, exist_ok=True)
                (t/'결과'/rel).write_bytes(data)

        def jload(rel):
            return json.loads((t/rel).read_text(encoding='utf-8'))

        def trial(no, name, rel, mutate, needle=None, stage=False, undo=None):
            p = t/rel
            old = p.read_bytes() if p.exists() else None
            mutate()
            rc, text = run_py(t, 'check.py') if stage else run_py(t, 'check.py', rel)
            if old is None:
                p.unlink(missing_ok=True)
            else:
                p.write_bytes(old)
            if undo:
                undo()
            restore_rc, _ = run_py(t, 'check.py', rel) if not stage else (0, '')
            caught = (needle in text) if needle else ('계약 확인 필요' in text)
            caught = caught and (rc != 0)
            out.append({'no': no, 'trial': name, 'file': rel, 'caught': caught, 'restored_pass': restore_rc == 0,
                        'line': next((l.strip() for l in text.splitlines() if l.startswith('  - ') or (needle and needle in l)), '')[:160]})
            if not caught or restore_rc != 0:
                fail(f'추출 검사기 {course} {no} {name}: 잡음 {caught} · 되돌린 뒤 통과 {restore_rc == 0}\n{text[-600:]}')

        def cand_mut(rel, fn):
            def go():
                d = jload(rel)
                fn(d)
                (t/rel).write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding='utf-8')
            return go

        def first(d, kind=None, pred=None):
            return next(c for c in d['candidates'] if (kind is None or c['kind'] == kind) and (pred is None or pred(c)))

        H11, OEMF, SRF, SCANF, H12 = '결과/후보/HM-8_1.1.json', '결과/후보/OEM-HPP45A-MM_C.json', '결과/후보/SR-04_2024.json', '결과/후보/HM-9_1.0.json', '결과/후보/HM-8_1.2.json'
        R11 = '결과/검토/HM-8_1.1_검토.json'
        trial('01', '인용 한 글자 변경', H11, cand_mut(H11, lambda d: first(d, 'step').update(quote=first(d, 'step')['quote'].replace('다', '나', 1))))
        lines11 = (t/'자료/HM-8_매뉴얼.md').read_text(encoding='utf-8').splitlines()
        trial('02', '다른 절 인용', H11, cand_mut(H11, lambda d: first(d, 'step').update(quote=lines11[87].lstrip('- ').strip())), '파일의 다른 줄에 있음')
        trial('03', '원문 없는 인용', H11, cand_mut(H11, lambda d: first(d, 'step').update(quote='원문에 없는 문장을 지어낸다.')))
        trial('04', '해시 지어냄', H11, cand_mut(H11, lambda d: d.update(source_sha256='0' * 64)), 'source_sha256')
        trial('05', '종류 오류', H11, cand_mut(H11, lambda d: first(d).update(kind='warning')), '알 수 없는 kind')
        trial('06', '값 글 없음', H11, cand_mut(H11, lambda d: first(d, 'unit_value').pop('value_text')), 'value_text')
        trial('07', '비교 기호 오류', H11, cand_mut(H11, lambda d: first(d, 'unit_value').update(comparator='≥')), 'comparator')
        trial('08', '범위 최대값 없음', H11, cand_mut(H11, lambda d: first(d, 'unit_value', lambda c: c.get('comparator') == 'range').pop('value_max')), 'value_max')
        trial('09', '없는 절차', H11, cand_mut(H11, lambda d: first(d, 'step').update(procedure='SOP-COOL-99')), '원문에 없는 절차 표기')
        trial('10', '중복 후보', H11, cand_mut(H11, lambda d: d['candidates'].append(dict(d['candidates'][0], id='dup-1'))), '이미 있음')
        trial('11', '단계 번호 없음', H11, cand_mut(H11, lambda d: first(d, 'step').pop('order')), 'order')
        trial('12', '추출 직후 승인', H11, cand_mut(H11, lambda d: first(d).update(status='approved')), '추출 직후 status는 pending')
        trial('13', '검토 상태 불일치', R11, cand_mut(R11, lambda d: first(d).update(decision='제외')), 'status는')
        trial('14', '수정 전 값 없음', R11, cand_mut(R11, lambda d: first(d).update(decision='수정', status='approved', before=None)), 'before')
        trial('15', '이유 없음', R11, cand_mut(R11, lambda d: first(d).update(reason='')), 'reason')
        trial('16', '누락 인용 지어냄', R11, cand_mut(R11, lambda d: d['missing'].append({'section': 'HM-8.9', 'quote': '없는 절의 지어낸 문장', 'note': 'x'})), 'missing')
        trial('17', '필드 없음', H11, cand_mut(H11, lambda d: first(d).pop('section')), '필수 필드 없음')
        trial('18', '문서 식별자 불일치', H11, cand_mut(H11, lambda d: d.update(doc_id='HM-9')), 'doc_id')

        def unregistered():
            (t/'자료/메모.md').write_text('# 메모\n\n설비를 정지한다.\n', encoding='utf-8')
            d = jload(H11)
            raw = (t/'자료/메모.md').read_bytes()
            d.update(source_file='메모.md', source_sha256=hashlib.sha256(raw).hexdigest(), candidates=[], unlocated=[])
            (t/H11).write_text(json.dumps(d, ensure_ascii=False), encoding='utf-8')
        trial('19', '문서 목록에 없는 파일', H11, unregistered, '문서_목록.csv에 없는 파일', undo=lambda: (t/'자료/메모.md').unlink(missing_ok=True))
        trial('20', 'OEM 없는 절차', OEMF, cand_mut(OEMF, lambda d: first(d, 'step').update(procedure='T-9.9')), '원문에 없는 절차 표기')
        oem_lines = (t/'자료/OEM-HPP45A_정비지침_영한.md').read_text(encoding='utf-8').splitlines()
        ko = next(n for n, l in enumerate(oem_lines, 1) if l.strip().startswith('KO: 고압 세척기는 쓰지 않는다'))
        trial('21', '번역 줄을 다른 절 · 언어로', OEMF, cand_mut(OEMF, lambda d: first(d, 'prohibition', lambda c: 'high-pressure' in c['quote']).update(
            quote='고압 세척기는 쓰지 않는다.', line_start=ko, line_end=ko, lang='en')), 'lang')
        trial('22', 'order가 참거짓', H11, cand_mut(H11, lambda d: first(d, 'step').update(order=True)), 'order')
        trial('23', '줄 범위 밖 인용', H11, cand_mut(H11, lambda d: first(d).update(line_end=999)), '줄 범위')
        trial('24', '글자 방식을 잘못 적은 SR-04 인용', SRF, cand_mut(SRF, lambda d: d.update(encoding='utf-8')), 'encoding')
        trial('25', '단위를 바꾼 OEM 인용', OEMF, cand_mut(OEMF, lambda d: first(d, 'unit_value', lambda c: 'psi' in c['quote']).update(
            quote=first(d, 'unit_value', lambda c: 'psi' in c['quote'])['quote'].replace('30 psi', '2 bar'), value_text='2 bar', unit='bar', value=2)))
        trial('26', '고친 글로 쓴 스캔본 인용', SCANF, cand_mut(SCANF, lambda d: first(d, 'prohibition', lambda c: 'REM0TE' in c['quote']).update(
            quote='원격 조치(SOP-COOL-01~03)는 REMOTE_AUTO가 아닐 때 쓰지 않는다.', quote_match='normalized')), '글자 · 숫자 비교로도')
        trial('27', '1.2 초안 문장을 1.1 파일로', H11, cand_mut(H11, lambda d: first(d, 'step', lambda c: '압축공기로' in c['quote']).update(
            quote='압축공기 또는 저압수(0.2 MPa 이하)로 핀 바깥쪽에서 안쪽으로 세척한다.')))
        orig11 = (t/H11).read_bytes()
        trial('28', '검토 뒤 고친 후보 원본', R11, lambda: (t/H11).write_bytes(orig11.replace(b'"warnings": []', b'"warnings": ["x"]')), '검토 뒤 후보 원본이 바뀜',
              undo=lambda: (t/H11).write_bytes(orig11))
        trial('29', '응답 기록 없는 후보 파일', H11, cand_mut(H11, lambda d: d.update(model_run=[])), 'model_run이 비어')
        rec = jload(H11)['model_run'][0]['record']
        rec_bytes = (t/rec).read_bytes()
        def other_folder():
            r = json.loads(rec_bytes)
            r['folder_mark'] = 'ffffffffffffffff'
            (t/rec).write_text(json.dumps(r, ensure_ascii=False), encoding='utf-8')
        trial('30', '다른 폴더의 응답 기록으로 만든 후보(폴더 표지가 다름)', H11, other_folder, '다른 폴더의 응답 기록입니다', undo=lambda: (t/rec).write_bytes(rec_bytes))
        trial('40', 'model_run에 reused_from을 적은 후보(다른 폴더 기록을 옮겨 씀)', H11,
              cand_mut(H11, lambda d: d['model_run'][0].update(reused_from='ffffffffffffffff')), '다른 폴더의 응답 기록으로는 후보를 만들지 않습니다')
        def reply_text(text):
            def go():
                r = json.loads(rec_bytes)
                r['response_text'] = text
                (t/rec).write_text(json.dumps(r, ensure_ascii=False), encoding='utf-8')
            return go
        trial('36', '관계없는 답 글과 짝지은 후보(규칙으로 만든 후보)', H11, reply_text('네, 연결되었습니다.'), '답 글에 없음', undo=lambda: (t/rec).write_bytes(rec_bytes))
        def unusable():
            r = json.loads(rec_bytes)
            r.update(usable=False, note='끝난 까닭 content_filter, 답 글이 비어 있음', response_text='')
            (t/rec).write_text(json.dumps(r, ensure_ascii=False), encoding='utf-8')
        trial('37', '쓸 내용이 없는 답의 기록과 짝지음', H11, unusable, 'usable false', undo=lambda: (t/rec).write_bytes(rec_bytes))
        # 38 · 39: origin reviewer로 꾸민 후보 — 후보 파일(검토 전)에서는 origin을 보지 않고 답 글과 견주고, 검토 결과에서는 reviewer 후보마다 missing(added: true)이 있어야 한다
        said = ' '.join(c['quote'] for c in jload(H11)['candidates'])
        spare = next((n, l) for n, l in enumerate(lines11, 1) if l.strip() and not l.startswith('#') and l not in said and X.squash(l) not in X.squash(said)
                     and '\n'.join(lines11).count(l) == 1 and '|' not in l)
        def fake_reviewer(d):
            n, l = spare
            d['candidates'].append({'id': 'fake-r1', 'section': first(d)['section'], 'procedure': None, 'kind': 'precondition', 'text': l, 'quote': l, 'quote_match': 'exact',
                                    'line_start': n, 'line_end': n, 'refs': [], 'status': 'pending', 'origin': 'reviewer'})
        trial('38', '답 글에 없는 원문 줄을 origin reviewer로 꾸민 후보(검토 전 후보 파일)', H11, cand_mut(H11, fake_reviewer), '답 글에 없음')
        trial('39', '검토 결과에서 모델 후보를 origin reviewer로 바꿈(missing 항목 없음)', R11,
              cand_mut(R11, lambda d: first(d, pred=lambda c: c['origin'] == 'extractor').update(origin='reviewer')), 'missing 항목(added: true)이 없음')
        RSR = '결과/검토/SR-04_2024_검토.json'
        trial('31', '조건표에 없는 규칙 id', RSR, cand_mut(RSR, lambda d: d['rule_links'][0].update(rule_id='R9')), '규칙 id가 아님')
        trial('32', '집합 밖 match 값', RSR, cand_mut(RSR, lambda d: d['rule_links'][0].update(match='범위 다름')), 'match는')
        trial('33', '스캔본 쪽 틀림', SCANF, cand_mut(SCANF, lambda d: first(d).update(page='9-5')), 'page')
        trial('34', '1.2 초안 파일 인용을 1.1 줄 번호로', H12, cand_mut(H12, lambda d: first(d, 'step').update(line_start=1, line_end=1)), '줄에 글자 그대로 없음')
        if course == '실전반':
            SEL = '결과/선택작업_조건.json'
            def held():
                d = jload(SEL)
                rv = jload('결과/검토/OEM-HPP45A-MM_C_검토.json')
                c = next(x for x in rv['candidates'] if x['status'] == 'pending')
                d['preparation'].append({'candidate': f'결과/검토/OEM-HPP45A-MM_C_검토.json#{c["id"]}', 'doc_id': 'OEM-HPP45A-MM', 'rev': 'C', 'section': c['section'], 'quote': c['quote'], 'decision': '보류'})
                (t/SEL).write_text(json.dumps(d, ensure_ascii=False), encoding='utf-8')
            trial('35', '보류 후보를 선택 작업 조건에', SEL, held, '승인(approved) 후보가 아님', stage=True)
    return out


# ───────────── 6. 장난감 시험 통과 기준 자기 시험 ─────────────
def toy_selftest():
    out = {}
    for course, (ek, gk) in COURSES.items():
        for key, folder in [(ek, BD.LABS[ek]), (gk, BD.GLABS[gk])]:
            archive = folder.parent/(folder.name + '.zip')
            with tempfile.TemporaryDirectory() as tmp:
                t = copy_lab(folder, tmp)
                clean = T.judge(archive, t)
                (t/'입력/README.md').write_text('바꿈\n', encoding='utf-8')
                (t/'결과/후보').mkdir(parents=True, exist_ok=True)
                (t/'결과/후보/HM-8_1.1.json').write_text(json.dumps({'model_run': [], 'candidates': []}), encoding='utf-8')
                (t/'결과/검토').mkdir(parents=True, exist_ok=True)
                (t/'결과/검토/HM-8_1.1_검토.json').write_text(json.dumps({'candidates': [{'id': 'x', 'decision': '보류', 'reason': ''}],
                                                                       'rule_links': [{'rule_id': 'R4', 'match': '보류', 'note': '근거 확인 중'}]}, ensure_ascii=False), encoding='utf-8')
                broken = T.judge(archive, t)
            out[key] = {'clean_pass': clean['pass'], 'broken': {k: broken[k]['pass'] for k in '①②③④'}}
            if not clean['pass'] or any(broken[k]['pass'] for k in '①②③④'):
                fail(f'장난감 기준 자기 시험 {key}: 손대지 않은 사본 {clean["pass"]} · 어긴 사본 {out[key]["broken"]}')
            if key == ek:
                out[key]['reply_compare'] = toy_reply_cases(folder, archive, key)
    return out


def toy_reply_cases(folder, archive, key):
    """② 「후보는 모델의 답에서 만든다」 — 같은 규칙 기반 후보 파일에 짝지은 응답 기록만 바꿔 판정을 본다.
    가: 관계없는 답(연결 확인 답)을 모델 서버 기록으로 → 모델 답에 없는 후보로 걸림. 나: 그 후보 인용을 담은 답을 「채팅으로 받음」으로(학생 AI가 --paste로 써 넣음)
    → 스스로 써 넣은 답으로 걸림. 다: 같은 답을 모델 서버 기록으로(키 있는 시험, 실제 호출 1번) → 통과. 라: 다를 --no-key로 → 키 없이 모델 서버 기록이 있어 걸림.
    마: 다와 같은데 실제 호출 0번(학생 AI가 응답 기록 JSON을 직접 써 넣음) → 실제 호출보다 많은 기록으로 걸림. 바: 다와 같은데 실제 호출 수를 주지 않음 → 판정하지 않음(통과 아님)."""
    row = next(r for r in X.read_register(folder) if r['파일'] == 'HM-8_매뉴얼.md')
    cands = X.extract(folder, row)
    body = json.dumps({'candidates': [{k: c[k] for k in ('section', 'procedure', 'kind', 'text', 'quote') if k in c} for c in cands['candidates']]}, ensure_ascii=False)
    cases = {'가': ('모델 서버', '네, 연결되었습니다.', False, 1), '나': ('채팅으로 받음', body, False, 0), '다': ('모델 서버', body, False, 1), '라': ('모델 서버', body, True, None),
             '마': ('모델 서버', body, False, 0), '바': ('모델 서버', body, False, None)}
    want = {'가': ('fail', 'not_in_model_reply_count'), '나': ('fail', 'pasted_by_ai'), '다': ('pass', None), '라': ('fail', 'records_without_key'),
            '마': ('fail', 'records_beyond_server_calls'), '바': ('fail', 'server_calls_unverified')}
    out = {}
    for name, (method, text, no_key, calls) in cases.items():
        with tempfile.TemporaryDirectory() as tmp:
            t = copy_lab(folder, tmp)
            (t/'결과/응답_기록').mkdir(parents=True, exist_ok=True)
            rec = {'request_hash': 'toy000000000', 'model': 'coding', 'method': method, 'received_at': '2026-11-04T10:00:00+09:00', 'folder_mark': 'toy', 'response_text': text}
            (t/'결과/응답_기록/toy000000000.json').write_text(json.dumps(rec, ensure_ascii=False), encoding='utf-8')
            d = copy.deepcopy(cands)
            d['model_run'] = [{'record': '결과/응답_기록/toy000000000.json', 'request_hash': 'toy000000000', 'model': 'coding', 'method': method, 'reused_from': None}]
            (t/'결과/후보').mkdir(parents=True, exist_ok=True)
            (t/'결과/후보/HM-8_1.1.json').write_text(json.dumps(d, ensure_ascii=False), encoding='utf-8')
            r = T.judge(archive, t, no_key, calls)['②']
        got = 'pass' if r['pass'] else 'fail'
        out[name] = {'method': method, 'no_key': no_key, 'server_calls': calls, 'result': got, 'not_in_model_reply': r['not_in_model_reply_count'], 'pasted_by_ai': len(r['pasted_by_ai']),
                     'records_without_key': len(r['records_without_key']), 'records_beyond_server_calls': len(r['records_beyond_server_calls']),
                     'server_calls_unverified': r['server_calls_unverified'], 'candidates': len(cands['candidates'])}
        expect, field = want[name]
        if got != expect or (field == 'not_in_model_reply_count' and r[field] != len(cands['candidates'])) or (field and field != 'not_in_model_reply_count' and not r[field]):
            fail(f'장난감 기준 ② 답 글 비교 {key} {name}: 기대 {expect}({field}) — 실제 {out[name]}')
    return out


def table_md(ext, graphs):
    """사건 갈래표 — 대본 · 가이드가 넘겨받을 「판단이 갈리는 지점과 확인할 사례」(코딩랩.md K맥-10)."""
    L = ['# 사건 갈래표 — 문서 지식 묶음(강사 참조)', '', '사건: 10월 27일 01:59 HYD-02 쿨러 성능 저하 경보의 판정 뒤에 남은 근본 조치 — 쿨러 핀 세척(SOP-COOL-14) 작업지시 전.', '',
         '## 지점5 조건의 근거 · 지점6 사내 문서와 제조사 지침(추출 랩)', '', '| 갈래 | 결정 수 | R4 맞는 정도 | 0171-051f(10월 26일 01:58 HYD-02)의 SOP-COOL-14 | 선택 작업 조건(실전) | 검사기 |', '|---|---|---|---|---|---|']
    for name, b in ext['branches'].items():
        r4 = b['rule_links'].get('R4') or b['rule_links'].get('rule:ts1-hard') or '—'
        case = '; '.join(f'{c["event"][-9:]} {c["sop"]} {c["after"]}' for c in b['judge_changes']['cases']) or '해당 없음'
        L.append(f'| {name} | {b["decisions"]} | {r4} | {case} | {b["selected"] or "—"} | {b["checker"]["contract"]} · {b["checker"]["stage"]} |')
    L += ['', '손익으로 지는 대안은 구성안 4절 그대로다 — 가: 실측 · 운전 중 원문을 예측 · 작업지시 규칙의 근거로 굳힘(감사 때 범위 문제) / 나: 예측 65.3 ℃ 작업지시 단독 후보가 비교에 들어옴 / 다: 회신까지 출처 미확인.',
          '지점6 가: 공기 세척으로 회복하지 않으면 미달로 끝나고 코어 상태를 보지 않음 / 나: 사내 승인 없는 기준으로 정지 시간 · 코어 비용이 늘고 완료 판단이 두 갈래.', '']
    if ext.get('model_candidates'):
        L += ['## 강사 추출 실행(수업 모델) — 같은 요청을 두 폴더에서', '', '같은 갈래 검토를 수업 모델 답의 후보에 걸었다. 갈래 판정 = rule_links · 판정이 달라지는 지난 경보가 위 표(문장 규칙 후보)와 같은가.', '',
              '| 실행 | 모델 · 보낸 요청 | 토큰(입력 / 출력) | 후보 · 찾지 못한 인용 | 기대 항목 맞음 / 기대 | 통합 나-가 결정 수 · 검토자가 더한 후보 | 갈래 판정 같음 | 검사기(12갈래) |', '|---|---|---|---|---|---|---|---|']
        for name, m in ext['model_candidates'].items():
            matched = sum(v['matched'] for v in m['score'].values())
            expect = sum(v['expected'] for v in m['score'].values())
            base = m['branches']['추출_통합반_나-가']
            same = sum(1 for b in m['branches'].values() if all(b['same_as_rules'].values()))
            ok = sum(1 for b in m['branches'].values() if b['checker']['contract'] == '통과' and b['checker']['stage'] == '남은 것 0')
            L.append(f'| {name} | {", ".join(m["models"])} · {m["sent"]}번 | {m["tokens"]["prompt_tokens"]} / {m["tokens"]["completion_tokens"]} | '
                     f'{sum(m["candidates"].values())} · {sum(m["unlocated"].values())} | {matched} / {expect} | {base["decisions"]} · {base["reviewer_added"]} | '
                     f'{same}/{len(m["branches"])} | {ok}/{len(m["branches"])} |')
        d = ext.get('model_runs_diff')
        if d:
            a = d['chunks']['all']
            L += ['', f'두 실행의 차이(요청 해시가 같은 조각 {a["chunks"]}개): 답 글이 글자까지 같은 조각 {a["same_text"]}개 · 후보 {a["n1"]} / {a["n2"]}개 · '
                  f'두 답에 함께 있는 인용 {a["both"]}개 · 첫 실행에만 {a["only1"]}개 · 둘째 실행에만 {a["only2"]}개.', '',
                  '| 후보 파일 | 첫 실행 후보 | 둘째 실행 후보 | 함께 있는 인용 | 첫 실행에만 | 둘째 실행에만 |', '|---|---|---|---|---|---|']
            L += [f'| {f} | {v["n1"]} | {v["n2"]} | {v["both"]} | {v["only1"]} | {v["only2"]} |' for f, v in d['per_doc'].items()]
        L.append('')
    L += ['## 지점7 다른 문서의 조건(그래프 랩)', '', '| 반 · 갈래 | 적재 수(앞 단계 → 첫 → 다시' + ' → 추가' + ') | 핀 세척 준비에 PM-2.4 | 질문 3 현재 값 | 내보내기 | 검사기 · 컨테이너 |', '|---|---|---|---|---|---|']
    for name, g in graphs.items():
        cs = ' → '.join(f'{v[0]}/{v[1]}' for v in g.get('counts', {}).values())
        L.append(f'| {name} | {cs} | {"있음" if g.get("pm24_in_preparation") else "없음"} | {g.get("q3")} | 노드 {g.get("export", {}).get("nodes")} · 관계 {g.get("export", {}).get("rels")} | '
                 f'rc {g.get("checker_rc")} · 지움 {g.get("container_removed")} |')
    L += ['', '손익: 가 = 세척이 다음 예정된 정비 시간까지 늦어질 수 있음(그동안 팬 100 %) / 나 = 생산 중이면 납기가 걸린 오더를 세울 수 있음. 다음 실습 에이전트의 「핀 세척은 언제 할 수 있나」 답이 갈래마다 다르다.']
    return '\n'.join(L) + '\n'


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--model-candidates', action='append', default=[], help='강사 추출 실행의 결과/후보 폴더(여러 번) — 주지 않으면 강사_추출/run*/결과/후보')
    ap.add_argument('--no-neo4j', action='store_true')
    a = ap.parse_args(argv)
    OUTDIR.mkdir(exist_ok=True)
    results = {'chain': chain()}
    print('1 사슬:', results['chain'])
    ext = extraction(a.model_candidates or sorted(str(p) for p in IE.KEPT.glob('run*/결과/후보') if p.is_dir()))
    results['extraction'] = ext
    print('2 · 3 추출 갈래', len(ext['branches']), '개')
    results['instructor_path'] = instructor_path()
    # 그래프 입력 = 강사 추출 실행 run1의 후보를 강사 판 갈래(나-가)로 검토한 결과 — 추출 학생용 완성본의 결과/검토와 같은 판(코딩랩.md K-48)
    base, when = BR.base_candidates()
    for course, (ek, gk) in COURSES.items():
        lab_e = BD.LABS[ek]
        built, _ = BR.build(lab_e, base, json.loads((lab_e/'입력'/BD.JUDGED[ek]).read_text(encoding='utf-8')), *BR.BASE, course, reviewed_at=when)
        mine = {rel.split('/', 1)[1]: data for rel, data in built.items() if rel.startswith('검토/')}
        if course == '실전반':
            mine['선택작업_조건.json'] = built['선택작업_조건.json']
        lab = {p.name: p.read_bytes() for p in (BD.GLABS[gk]/'입력/검토결과').iterdir()}
        if mine != lab:
            fail(f'{course}: 그래프 랩 입력/검토결과가 강사 추출 실행 run1의 강사 판 갈래(나-가) 검토와 다름')
    trials = {'extract': {c: extraction_trials(c) for c in COURSES}}
    graphs = {}
    if not a.no_neo4j:
        for course in COURSES:
            for p7 in G.P7:
                g, tr = graph_run(course, p7, trials=(p7 == G.BASE_P7))
                graphs[f'{course} 지점7 {p7}'] = g
                if tr:
                    trials.setdefault('graph', {})[course] = tr
                print(f'4 그래프 {course} 지점7 {p7}:', g.get('counts'), 'rc', g.get('checker_rc'), '컨테이너 지움', g.get('container_removed'))
    results['graph'] = graphs
    results['toy_criteria_selftest'] = toy_selftest()
    summary = {k: {c: f'{sum(1 for x in v if x["caught"])}/{len(v)}' for c, v in d.items()} for k, d in trials.items()}
    (HERE/'검사기_확인.json').write_text(json.dumps({'summary': summary, 'trials': trials}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (HERE/'사건_갈래표.md').write_text(table_md(ext, graphs), encoding='utf-8')
    results['failures'] = failures
    (HERE/'expected_results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    print('검사기 고의 손상:', summary)
    print(f'불일치 {len(failures)}건')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
