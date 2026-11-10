"""문서 지식 네 랩(통합반 04회차 실습2 · 3, 실전반 03회차 실습4 · 5)을 새 프로젝트 구조(코딩랩 K-5~K-7)로 만든다.

판단 · 자료 · 난도는 기존 생성기 build_document_labs.py의 것을 그대로 쓴다. 이 파일은 그 생성기로 옛 구조 랩을 작업 폴더 안 임시 자리에 만든 뒤
경로 · 파일 이름만 영어로 옮기고(convert), 결과 화면 · 실행 진입점 · 가이드를 새 구조로 쓴다. 제공 코드(doc_extract · doc_graph · lab_cypher · lab_db ·
lab_llm)와 검사기 알고리즘은 같은 원본을 경로만 바꿔 쓴다. 입력은 모듈 함수에서 받는다 — 문서 data_documents, 조건표 · SOP 구조 reference/session3/criteria,
판정 결과 judge_actions(3회차 강사 판 지점3 가 · 지점4 가), 설비 모델 build_labs.reference_model. 산출물/ 폴더를 입력으로 읽지 않는다.
학생용 완성본은 고정된 강사 추출 실행(reference/session3_docs/강사_추출/run1 · run2)의 응답 기록을 쓴다 — 수업 모델을 새로 부르지 않는다.

python build_session4_projects.py <lab …> --dest 작업/검사/<새 폴더> [--completed]
python build_session4_projects.py <lab …> --apply [--completed]      (정본 교체 — 메인이 한다)
lab: integrated-04-extract · integrated-04-graph · practical-03-extract · practical-03-card (그래프 랩은 같은 반의 추출 랩 입력을 함께 만든다)
"""
from pathlib import Path
import argparse
import contextlib
import hashlib
import html as _html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

import lab_frame as F
import build_labs as B
import build_judgement_labs as BJ
import build_document_labs as BD
import data_conditions as DC
import lab_llm as LLM
import session2_project as P
import session2_project_guides as SG
import session2_graph_project as GP
from lab_package import ROOT, pack, entry, register, student_files, write_zip
from project_layout import write_metadata, errors, AI_RULES, DB_RULE

HERE = Path(__file__).resolve().parent
REF = HERE / 'reference/session3_docs'
VERSION = '2026-11-11-project'
WORK = ROOT / '작업/검사/session4-projects'
OUT = F.OUT
TASK = BD.TASK

LABS = {   # 프로젝트 이름 = 실라버스 행 제목의 뜻(영문 kebab-case). 실전반 둘은 한 회차 랩 폴더 안에서 다른 랩과 겹치지 않는다.
    'integrated-04-extract': dict(name='knowledge-extract-lab', course='통합반', session='온라인 04회차', n=4, kind='extract',
                                  why='행 「문서에서 근거 있는 지식을 추출하는 기능 만들기」 — 문서 지식(knowledge) 추출(extract)'),
    'integrated-04-graph': dict(name='knowledge-graph-lab', course='통합반', session='온라인 04회차', n=4, kind='graph', extract='integrated-04-extract',
                                why='행 「검토한 문서 지식을 그래프 DB에 반영하고 관계 확인하기」 — 문서 지식(knowledge)을 그래프(graph)에'),
    'practical-03-extract': dict(name='condition-extract-lab', course='실전반', session='온라인 03회차', n=3, kind='extract',
                                 why='행 「문서에서 작업 조건과 근거를 추출하는 기능 만들기」 — 작업 조건(condition) 추출(extract)'),
    'practical-03-card': dict(name='work-card-lab', course='실전반', session='온라인 03회차', n=3, kind='graph', extract='practical-03-extract',
                              why='행 「검토 지식으로 작업 확인 카드 만들기」 — 작업 확인 카드(work card)'),
}
DEST = {'통합반': OUT / '통합반/실습/04회차/랩', '실전반': OUT / '실전반/실습/03회차/랩'}
COMPLETED_DIR = {'통합반': OUT / '통합반/실습/04회차/완성본', '실전반': OUT / '실전반/실습/03회차/완성본'}

# ───────────── 경로 · 파일 이름 옮기기(내용은 그대로) ─────────────
DOCS = {'HM-8_1.0판_매뉴얼.md': 'hm_8_rev_1_0_manual.md', 'HM-8_매뉴얼.md': 'hm_8_manual.md', 'HM-8_1.2판_개정요청.md': 'hm_8_rev_1_2_change_request.md',
        'HM-9장_스캔본.txt': 'hm_9_chapter_scan.txt', 'SR-04_설비안전규정_발췌.txt': 'sr_04_safety_rules_excerpt.txt', 'PM-02_정기점검표.md': 'pm_02_periodic_inspection.md',
        'PR-07_예비품기준.md': 'pr_07_spare_parts_standard.md', 'HI-01_보충매뉴얼.md': 'hi_01_supplementary_manual.md',
        'OEM-HPP45A_정비지침_영한.md': 'oem_hpp45a_maintenance_guide_en_ko.md', 'DC-01_문서관리기준.md': 'dc_01_document_control.md', '문서_목록.csv': 'catalog.csv'}
NAMES = {   # 이름만(경로 앞머리 없이)
    '나누기.json': 'split.json', '기대_항목.csv': 'expected.csv', '검토_결정.csv': 'review_decisions.csv', '조건_대조.csv': 'rule_links.csv',
    '역할.csv': 'roles.csv', '정한_것.csv': 'decisions.csv', '검토_기록.md': 'review.md', '시험_조각.json': 'trial_chunk.json',
    '선택작업_조건.json': 'selected_task.json', '기대_답.csv': 'expected.csv', '그래프_모양.json': 'graph_shape.json', '연결_규칙.csv': 'link_rules.csv',
    '별칭.csv': 'aliases.csv', '다른문서_조건.csv': 'other_doc_conditions.csv', '질문_값.csv': 'query_values.csv', '현재값_원천.csv': 'current_value_sources.csv',
    '구축_기록.md': 'build_record.md', '남은_질문.json': 'remaining_questions.json', '지식_내보내기.json': 'knowledge_export.json', '작업확인카드_': 'work_card_',
    '.적재_문서.json': '.loaded_docs.json', '추가전_내보내기.json': 'export_before_add.json', '랩_연결.json': '.lab_connection.json',
    '조건표.csv': 'conditions.csv', '조치검토결과.json': 'action_review.json', '조치검토결과.md': 'action_review.md', '_검토.json': '_review.json',
    '폴더_표지.txt': '.folder_mark', '.보기_이전.json': '.previous.json', '보기.html': 'result.html', '입출력_계약.md': 'data/contract.md', '입출력_계약': 'data/contract',
    '모델/graph.json': 'model/graph.json', '모델/schema.json': 'model/schema.json', **DOCS,
    '남은 질문': '추가 자료가 필요한 질문', '현재 값': '현재값', '조회문': '쿼리'}   # 장부 이름(사실표 「같은 말 · 같은 값」) — 「남은 질문」 · 「조회문」은 쓰지 않을 말
OUTPUT_FILES = ['trial_chunk.json', 'selected_task.json', '.folder_mark', 'remaining_questions.json', 'knowledge_export.json', 'work_card_', '.loaded_docs.json',
                'export_before_add.json', 'schema_ext.json', 'load.cypher', 'query.cypher', 'result.html', '.previous.json', 'schema.json', 'graph.json']
PATHS = ([('결과/내_입력', 'app/features/my_inputs'), ('입력/검토결과', 'data/reviews'), ('검토결과/', 'reviews/'), ('입력/모델', 'data/model'), ('결과/응답_기록', 'output/model_responses'), ('결과/요청', 'output/model_requests'), ('결과/후보', 'output/candidates'), ('결과/검토', 'output/reviews'),
          ('결과/내_입력', 'app/features/my_inputs'), ('결과/내_모델', 'app/features/my_model')]
         + [('결과/' + n, 'output/' + n) for n in OUTPUT_FILES]
         + [('결과/', 'app/features/'), ('입력/', 'data/'), ('자료/', 'data/documents/'),
            ("'검토결과'", "'reviews'"), ('"검토결과"', '"reviews"'), ("'결과' / ", "'app/features' / "), ("'입력'", "'data'"), ("'자료'", "'data/documents'")])
COMMANDS_TEXT = [('START.md 「학생이 정할 것」의 그 자리 이름', '사람이 결정할 지점의 이름'),
                 ('`python show_result.py`가 랩 DB에 올리는 것', '`python run.py db`가 랩 DB에 올리는 것'), ('`python show_result.py`의 마지막 단계가 쓴다', '`python run.py export`가 쓴다'),
                 ('`python show_result.py`가 채운 자리까지 제공 코드', '명령마다(`python run.py <명령>`) 그 명령이 쓰는 정할 자리까지 제공 코드'),
                 ('`현재값 필요`)과 질문 3 · 카드', '`현재값 필요`)과 카드'), ('python show_result.py', 'python run.py'), ('show_result.py', 'run.py'), ('python check.py', 'python run.py check'), ('`check.py`', '`python run.py check`'),
                 ('check.py', 'app/utils/check.py'), ('python lab_db.py', 'python run.py db'), ('lab_db.py', 'app/utils/db.py'),
                 ('python lab_cypher.py', 'python -m app.utils.cypher'), ('lab_cypher.py', 'app/utils/cypher.py'), ('doc_extract.py', 'app/utils/extract.py'),
                 ('doc_graph.py', 'app/utils/graph.py'), ('lab_steps.py', 'app/utils/actions.py'), ('lab_steps', 'app/utils/actions'), ('python llm_client.py', 'python run.py connect'),
                 ('llm_client.py', 'app/utils/llm_client.py'), ('START.md', '가이드')]
CODE = [("    path = RESULT / name\n", "    path = HERE / 'app/features' / name\n"),("RESULT / '", "HERE / '결과/"), ("RESULT = HERE / '결과'", "RESULT = HERE / 'output'"),
        ('import show_result as R', 'from app.utils import results as R'), ('import doc_extract as _X', 'from app.utils import extract as _X'),
        ('import doc_extract as X', 'from app.utils import extract as X'), ('import doc_graph as G', 'from app.utils import graph as G'),
        ('import llm_client as L', 'from app.utils import llm_client as L'), ('    import llm_client\n', '    from app.utils import llm_client\n'),
        ('    import lab_cypher, subprocess, sys\n', '    from app.utils import cypher as lab_cypher\n    import subprocess, sys\n'),
        ('    import lab_cypher\n', '    from app.utils import cypher as lab_cypher\n'),
        ("[sys.executable, str(HERE / 'check.py')]", "[sys.executable, '-m', 'app.utils.check']"),
        ('Path(__file__).resolve().parent\n', 'Path(__file__).resolve().parents[2]\n')]


def convert(text, code=False):
    """옛 구조의 경로 · 파일 이름을 새 구조로. code=True면 import · HERE · RESULT도 바꾼다(제공 코드 · 검사기 · 결과 화면 단계)."""
    if code:
        for old, new in CODE:
            text = text.replace(old, new)
    for old, new in sorted(NAMES.items(), key=lambda x: -len(x[0])):
        text = text.replace(old, new)
    for old, new in PATHS:
        text = text.replace(old, new)
    for old, new in COMMANDS_TEXT:
        text = text.replace(old, new)
    return text


RESIDUE = re.compile(r'(결과|입력|자료)/|[가-힣](?:app|output|data|reviews)/|show_result|lab_steps|doc_extract|doc_graph|START\.md|랩_연결|\.github|CLAUDE\.md')
KOREAN_FILE = re.compile(r'(?<![\w가-힣])(?!파일\.)[가-힣]+(?:_[가-힣]+)*\.(?:csv|json|md|txt|html|cypher)\b')   # 「파일.md」는 칸 뜻의 자리 표시
# data/의 판정 결과 · SOP 구조 · 검토 결과에 든 다른 랩의 파일 이름(3회차 자료의 출처 표기)은 이 랩의 경로가 아니라 그대로 둔다.


def residue(folder):
    """옮긴 뒤에도 옛 경로 · 한글 파일 이름 · 옛 파일이 남은 곳(문서 원문 · llm_client 바이트 · 문서 목록 머리는 뺀다) — 파일:줄 목록."""
    bad = []
    for p in sorted(folder.rglob('*')):
        rel = p.relative_to(folder).as_posix()
        if not p.is_file() or rel.startswith('data/documents/') and not rel.endswith('catalog.csv') or rel == 'app/utils/llm_client.py' or '__pycache__' in rel:
            continue
        try:
            text = p.read_text(encoding='utf-8-sig')
        except UnicodeDecodeError:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if RESIDUE.search(line) or (not rel.startswith('data/') or rel.endswith('catalog.csv')) and KOREAN_FILE.search(line):
                bad.append(f'{rel}:{n}: {line.strip()[:120]}')
    return bad


def write(path, text, bom=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8-sig' if bom else 'utf-8', newline='\n')


# ───────────── 입력(모듈 함수) — 옛 구조 랩을 임시 자리에 만든다 ─────────────
def incident(files):
    return f'10월 27일 {BJ.incident_time(files)}(한국 시각) HYD-02 쿨러 성능 저하 경보'


def judged_dir(files, folder):
    """3회차 판정 랩의 강사 판(지점3 가 · 지점4 가) — result.json(통합) · 조치검토결과.json(실전). reference/session3/run_reference.py judge_branches와 같은 계산 · 같은 꼴."""
    for p in (HERE / 'reference/session3', HERE / 'judgement_tools'):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    import judge_actions as J
    import criteria as CR
    lab = folder / 'lab'
    for name, core in BJ.DATA['integrated-03-judge']:
        value = files[core]
        (lab / '자료' / name).parent.mkdir(parents=True, exist_ok=True)
        (lab / '자료' / name).write_bytes(value if isinstance(value, bytes) else value.encode('utf-8'))
    BJ.judge_inputs(lab)
    res = J.run(lab, policy=J.BASE_POLICY)
    rv = J.review(res, json.loads(CR.sop_json(*CR.BASE)), J.load_table(lab / '입력/조건표.csv'))
    for name, value in (('result.json', J.student_view(res)), ('조치검토결과.json', rv)):
        write(folder / name, json.dumps(value, ensure_ascii=False, indent=1) + '\n')
    return folder


def model_dirs(folder):
    """그래프 랩의 설비 모델 — 통합반은 2회차 graph-lab의 data/model과 같은 꼴(P.convert), 실전반은 2회차 실습4 입력과 같은 꼴."""
    out = {}
    for course, practical in (('통합반', False), ('실전반', True)):
        schema, graph = B.reference_model(practical, B.LAB4_INPUT_BRANCH[course])
        for name, value in (('schema.json', B.student_schema(schema)), ('graph.json', graph)):
            text = json.dumps(value, ensure_ascii=False, indent=2) + '\n'
            write(folder / course / name, P.convert(text) if course == '통합반' else text)
        out[course] = folder / course
    return out


@contextlib.contextmanager
def legacy(work):
    """BD(옛 생성기)의 산출물 경로 · 입력 경로를 이 작업 자리로 돌린 채 쓴다. 끝나면 되돌린다."""
    files, _ = DC.build()
    judged = judged_dir(files, work / 'judged')
    models = model_dirs(work / 'models')
    saved = dict(BD.LABS), dict(BD.GLABS), dict(BD.LAB2_INPUT), BD.BASE_JUDGED, BD.incident
    try:
        for key in BD.LABS:
            BD.LABS[key] = work / 'legacy' / key / saved[0][key].name
        for key in BD.GLABS:
            BD.GLABS[key] = work / 'legacy' / key / saved[1][key].name
        BD.LAB2_INPUT.update(models)
        BD.BASE_JUDGED = judged
        BD.incident = lambda: incident(files)
        yield files
    finally:
        BD.LABS.clear(); BD.LABS.update(saved[0])
        BD.GLABS.clear(); BD.GLABS.update(saved[1])
        BD.LAB2_INPUT.clear(); BD.LAB2_INPUT.update(saved[2])
        BD.BASE_JUDGED, BD.incident = saved[3], saved[4]


def build_legacy(keys):
    """옛 구조 랩 폴더 — 추출을 먼저(그래프 랩이 그 자료 · 입력을 읽는다). 돌려주는 값: {열쇠: (폴더, L)}."""
    out = {}
    for key in sorted(k for k in keys if LABS[k]['kind'] == 'extract'):
        out[key] = BD.build(key)
    for key in sorted(k for k in keys if LABS[k]['kind'] == 'graph'):
        out[key] = BD.gbuild(key)
    return out


# ───────────── 새 프로젝트 쓰기 ─────────────
EXTRACT_SLOTS = ['나누기.json', 'prompt.md', '기대_항목.csv', '검토_결정.csv', '조건_대조.csv', '역할.csv', '정한_것.csv', '검토_기록.md']
GRAPH_SLOTS = ['기대_답.csv', '그래프_모양.json', '연결_규칙.csv', '별칭.csv', '다른문서_조건.csv', '역할.csv', '질문_값.csv', '현재값_원천.csv', '정한_것.csv', '구축_기록.md']


VERDICTS = [('. 옛 설명 문장은 제어 후보만 말하므로 작업지시 후보에는 맞지 않는다', ''), ('. 작업지시는 PLC 제어 명령이 아니어서 이 이유와 맞지 않는다', ''),
            (' 원문 미확인(1.0판 · 1.1판에 없음)', ''), ('(설비안전규정 SR-04) 원문 미확인', '(설비안전규정 SR-04)')]


def plain_reasons(text):
    """제공 조건표 · SOP 구조 · 판정 결과의 규칙 이유에서 판정 문장(조건의 근거 지점의 답)을 지우고 옛 판단 시스템이 규칙을 건 이유만 남긴다(메인 결정 2026-11-11)."""
    for old, new in VERDICTS:
        text = text.replace(old, new)
    return text


def copy_data(src, folder, graph):
    """원자료 · 제공 입력. 문서 원문은 바이트 그대로(이름만 영어), 문서 목록 · 조건표 · SOP 구조 · 판정 결과 · 검토 결과는 경로 · 파일 이름만 옮긴다."""
    for p in sorted((src / '자료').iterdir()):
        target = folder / 'data/documents' / DOCS[p.name]
        target.parent.mkdir(parents=True, exist_ok=True)
        if p.name == '문서_목록.csv':
            target.write_bytes(convert(p.read_bytes().decode('utf-8')).encode('utf-8'))
        else:
            target.write_bytes(p.read_bytes())
    for p in sorted((src / '입력').rglob('*')):
        rel = p.relative_to(src / '입력').as_posix()
        if not p.is_file() or rel == 'README.md':
            continue
        if rel.startswith('모델/'):
            write(folder / 'data/model' / p.name, P.convert(p.read_text(encoding='utf-8')))
        elif rel.startswith('검토결과/'):
            write(folder / 'data/reviews' / convert(p.name), plain_reasons(convert(p.read_text(encoding='utf-8'))))
        else:
            write(folder / 'data' / convert(rel), plain_reasons(convert(p.read_text(encoding='utf-8'))))
    write(folder / 'data/contract.md', convert((src / '입출력_계약.md').read_text(encoding='utf-8-sig')), bom=True)


def fix_review_hashes(folder, key):
    """그래프 랩 data/reviews의 candidates_sha256 — 옮긴 후보 파일(추출 랩 output/candidates와 같은 꼴)의 SHA-256으로 다시 적는다."""
    BR = BD.branches_module()
    cands, _ = BR.base_candidates()
    for p in sorted((folder / 'data/reviews').glob('*_review.json')):
        data = json.loads(p.read_text(encoding='utf-8'))
        name = Path(data['review']['candidates_file']).name
        raw = convert(BR.X.dump(cands[name])).encode('utf-8')
        text = p.read_text(encoding='utf-8').replace(data['review']['candidates_sha256'], hashlib.sha256(raw).hexdigest())
        write(p, text)


CHECK_TEXT = [('app/features/의 Cypher 파일', 'output/의 Cypher 파일'), ('app/features/에 적재 파일(.cypher)이 없습니다.', 'output/load.cypher가 없습니다 — python run.py load를 아직 실행하지 않았습니다.'),
              ('적재 파일을 아직 실행하지 않았습니다.', 'python run.py load를 아직 실행하지 않았습니다.'), ('(python -m app.utils.cypher export output/knowledge_export.json)', '(python run.py export)')]


def checker_source(template, folder, provided):
    """옛 검사기 알고리즘을 그대로 — 경로만 옮기고, 항목 번호 · 단계 말을 구조 검사 말로 바꾼다. 제공 파일 해시 대조를 넣는다."""
    text = convert(template, code=True)
    text = re.sub(r"(print\(f?')\[(?:\d+|\{[^}\]]*\})\] ", r'\1', text)   # 출력 줄 머리의 항목 번호만(코드의 [0] 같은 색인은 그대로)
    text = text.replace("print('완료 아님 — 남은 것:')", "print('구조 확인 필요:')").replace("print('구조상 빠진 단계는 없습니다. ' + END)", "print('구조 검사 통과. ' + END)")
    for old, new in CHECK_TEXT:
        text = text.replace(old, new)
    text = text.replace('단계별 상태(무엇이 있고 무엇이 비었는지)', '전체 구조 검사').replace('python app/utils/check.py', 'python -m app.utils.check')
    at = text.rindex("\nif __name__ == '__main__':")
    chosen = convert(F.CHOSEN_CHECK, code=True)
    return text[:at] + '\n' + chosen + '\n' + F.provided_guard(folder, provided) + text[at:]


STEP_TAIL = re.compile(r'\n__STEPS__\n')
ACTION_TEXT = [  # 결과 화면 글(장부 이름) · 검사 출력 전체 · 랩 DB 꺼짐 · 실전 모으기 표 제목 · 빈 카드로 덮지 않기
    ('python run.py 출력(끝 12줄, 종료 코드 ', 'python run.py check 출력(종료 코드 '), ('(키가 없으면 보낼 글이 output/model_requests/에 남습니다)', '(키가 없으면 완성본 ZIP으로 결과를 봅니다)'), ('splitlines()[-12:]', 'splitlines()'),
    ('목록의 판 · 상태와 읽은 결과(SHA-256이 목록과 같은 파일만 읽음)', '목록의 판본 · 상태와 읽은 결과(지문 SHA-256이 목록과 같은 파일만 읽음)'),
    ("        except G.Problem as e:\n            raise R.Stop(str(e))\n    return run",
     "        except G.Problem as e:\n            raise R.Stop(str(e))\n        except RuntimeError as e:\n            if type(e).__name__ == 'LabDbOff':\n                raise R.Stop(str(e) + ' Docker Desktop이 켜져 있는지 봅니다.')\n            raise\n    return run"),
    ("[(k, len(got[k])) for k in ('preparation', 'prohibitions', 'completion', 'remaining_questions', 'sop_diff')]",
     "[(LABEL[k], len(got[k])) for k in ('preparation', 'prohibitions', 'completion', 'remaining_questions', 'sop_diff')]"),
    ('        out.append(R.table(k, [', '        out.append(R.table(LABEL[k], ['),
    ("R.table('sop_diff', ['where', 'item', 'note']", "R.table(LABEL['sop_diff'], ['어디에만', '항목', '까닭']"),
    ("    G.write(HERE / f'output/work_card_{sop}.md', text)\n    exp = G.expect_rows(ITEMS)",
     "    if all(f'이 작업에 이은 {k} 지식이 그래프에 없음' in text for k in ('준비', '금지', '완료')):\n"
     "        raise R.Stop('그래프에 이 작업의 지식이 아직 없습니다 — 먼저 python run.py load → python run.py other를 실행합니다(카드 파일은 그대로 둡니다).')\n"
     "    G.write(HERE / f'output/work_card_{sop}.md', text)\n    exp = G.expect_rows(ITEMS)"),
]


def prune(source, roots):
    """COMMANDS가 부르는 함수와 그 함수가 쓰는 것만 남긴다 — 다른 과정 몫의 함수 · 같은 이름의 앞 정의는 학생 AI가 할 일로 읽지 않게 뺀다."""
    import ast
    tree = ast.parse(source)
    defs = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            defs.setdefault(node.name, []).append(node)
    used = lambda n: {x.id for x in ast.walk(n) if isinstance(x, ast.Name)} | {x.attr for x in ast.walk(n) if isinstance(x, ast.Attribute)}
    top = set()
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            top |= used(node)
    keep, todo = set(), list(set(roots) | (top & set(defs)))
    while todo:
        name = todo.pop()
        if name in keep or name not in defs:
            continue
        keep.add(name)
        node = defs[name][-1]
        todo += [x for x in used(node) if x in defs]
    lines = source.splitlines(keepends=True)
    drop = set()
    for name, nodes in defs.items():
        for node in (nodes if name not in keep else nodes[:-1]):
            start = min([node.lineno] + [d.lineno for d in node.decorator_list]) - 1
            drop |= set(range(start, node.end_lineno))
    text = ''.join(l for i, l in enumerate(lines) if i not in drop)
    return re.sub(r'\n{4,}', '\n\n\n', text)


def actions_source(template, fill, commands):
    """옛 결과 화면 단계(lab_steps 틀)의 함수를 그대로 — 기능 하나를 `python run.py <기능>`으로 부르는 COMMANDS로 묶는다(단계 번호 · 진척 표시 없음)."""
    text = template
    for old, new in fill.items():
        text = text.replace(old, new)
    text = convert(text, code=True)
    text = text.replace("    return f' — {hit[\"no\"]}단계 「{hit[\"name\"]}」의 정할 자리' if hit else ''",
                        "    return f' — python run.py {hit[\"command\"]}에서 쓰는 정할 자리' if hit else ''")
    text = re.sub(r'^""".*?"""', lambda m: f'"""{fill["__TITLE__"]} — 명령마다 한 기능을 실행해 결과를 output/result.html에 보인다. 제공 파일 — 고치지 않는다."""', text, count=1, flags=re.S)
    for old, new in ACTION_TEXT:
        text = text.replace(old, new)
    if fill['__KIND__'] == 'graph':
        text = text.replace('@guard\ndef save(previous):\n', '@guard\ndef save(previous):\n    shape()\n', 1)
    steps = 'STEPS = [\n' + ''.join(f'    dict(command={c!r}, slots={s!r}),\n' for c, (_, _, s) in commands.items() if s) + ']\n'
    table = 'COMMANDS = {\n' + ''.join(f'    {c!r}: ({label!r}, {fn}),\n' for c, (label, fn, _) in commands.items()) + '}\n'
    if '__STEPS__' not in text:
        raise RuntimeError('결과 화면 단계 틀에 __STEPS__ 자리가 없습니다')
    tail = '\n' + EXTRA[fill['__KIND__']] + '\n' + steps + '\n' + table
    text = STEP_TAIL.sub(lambda m: tail, text)   # 바꿀 글의 역슬래시를 re가 풀지 않게
    return prune(text, [fn for _, fn, _ in commands.values()])


EXTRA = {'extract': '''
def connect(previous):
    """수업 모델 연결 확인 — 짧은 질문 하나를 보낸다(키가 없으면 보내지 않고 알린다)."""
    import contextlib, io
    from app.utils import llm_client as L
    out = io.StringIO()
    code = 0
    with contextlib.redirect_stdout(out):
        try:
            L.main([])
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 1
    conf = L.settings()
    text = out.getvalue().strip()
    head = [R.error('수업 모델 연결 안 됨', text)] if code else [R.note(text)]
    return head + [R.counts('연결 값과 응답 기록(값은 보이지 않음)', [('.env에 채운 줄', f'{sum(1 for n in L.NAMES if conf[n])} / 3'), ('응답 기록 수', len(L.records())),
                                                        ('이 폴더의 안내용 상한까지 남은 수', L.MAX_SENT - L.sent_count())])]


def check(previous):
    return save(previous)


LABEL = {'preparation': '준비', 'prohibitions': '금지', 'completion': '완료', 'remaining_questions': '추가 자료가 필요한 질문', 'sop_diff': 'SOP 구조와 다른 곳'}
''', 'graph': '''
def prepare(previous):
    from app.utils import db as local_db
    try:
        local_db.prepare()
    except (RuntimeError, OSError) as e:
        raise R.Stop('랩 DB 꺼짐 — Docker Desktop이 켜져 있는지 보고 같은 명령을 다시 실행합니다. (' + str(e).splitlines()[0][:160] + ')')
    return (look_db if PRACTICAL else db)(previous)


@guard
def other_twice(previous):
    out = other(previous)
    first = G.counts()
    G.load_all()
    second = G.counts()
    flat = lambda c: {'노드': c['nodes'], '관계': c['rels'], **{'노드 ' + k: v for k, v in c['labels'].items()}, **{'관계 ' + k: v for k, v in c['types'].items()}}
    block = R.before_after('같은 적재를 한 번 더 실행한 전후 — 늘거나 사라진 것이 없어야 합니다', flat(first), flat(second))
    return out + [block] + ([] if block['rows'] else [R.note(f'한 번 더 적재해도 같음: 노드 {second["nodes"]} · 관계 {second["rels"]}')])


def check(previous):
    import subprocess, sys
    run = subprocess.run([sys.executable, '-m', 'app.utils.check'], capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=HERE)
    return [R.note('python run.py check 출력(종료 코드 ' + str(run.returncode) + ')\\n' + run.stdout.strip())]
'''}


RUN = '''"""한 기능을 실행하고 실제 결과를 output/result.html에 표시한다."""
from pathlib import Path
import argparse
import json
import os
import sys
import webbrowser
from app.utils import results__LLM_IMPORT__
from app.utils import actions
from app.ui.render import page

ROOT = Path(__file__).resolve().parent__LLM_SETUP__


def env_twice():
    """.env에 같은 이름이 두 번 있으면(받은 세 줄을 빈 세 줄 위에 붙인 경우) 뒤의 빈 값이 이겨 키가 없는 것처럼 된다 — 줄 번호를 짚고 멈춘다."""
    path = ROOT / '.env'
    if not path.is_file():
        return None
    seen = {}
    for n, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
        if '=' in line and not line.strip().startswith('#'):
            seen.setdefault(line.split('=', 1)[0].strip(), []).append(n)
    twice = [f'{" · ".join(map(str, lines))}줄에 {name}' for name, lines in seen.items() if len(lines) > 1]
    return ('.env ' + ', '.join(twice) + '가 두 번 있습니다 — 등호 뒤가 빈 줄을 지우고 받은 세 줄만 남긴 뒤 저장합니다.') if twice else None


def main():
    parser = argparse.ArgumentParser(description=actions.TITLE)
    parser.add_argument('action', nargs='?', default='sources', choices=actions.COMMANDS)
    parser.add_argument('--no-open', action='store_true', help='브라우저를 열지 않습니다')__LLM_ARGS__
    args = parser.parse_args()__LLM_RUN__
    title, function = actions.COMMANDS[args.action]
    try:
        twice = env_twice()
        if twice:
            raise results.Stop(twice)
        blocks = function({})
    except results.Blank as exc:
        blocks = [results.note('아직 비어 있습니다: ' + str(exc))]
    except results.Stop as exc:
        blocks = [results.error('확인 필요', str(exc))]
    except Exception as exc:
        message = str(exc).replace(str(ROOT) + os.sep, '').replace(str(ROOT), '.')   # 학생 PC의 절대 경로를 보이지 않는다
        blocks = [results.error('실행 확인 필요 ' + results.where(exc), message)]
    output = ROOT / 'output'
    output.mkdir(exist_ok=True)
    target = output / 'result.html'
    first = not target.exists()
    target.write_text(page(actions.TITLE, title, blocks), encoding='utf-8', newline='\\n')
    (output / 'result.json').write_text(json.dumps({'action': args.action, 'blocks': blocks}, ensure_ascii=False, indent=2) + '\\n', encoding='utf-8')
    print(title)
    for block in blocks:
        if block['kind'] in ('note', 'error'):
            print(block.get('title', '') + ('\\n' if block.get('title') else '') + block['text'])
        elif block['kind'] == 'table':
            print(f"{block['title']}: {len(block['rows'])}행")
        elif block['kind'] == 'counts':
            print(f"{block['title']}: " + ' · '.join(f'{name} {value}' for name, value in block['items']))
    print('결과: output/result.html' + (' — 열린 화면에서 F5로 새로 고침합니다.' if not first else ''))
    if first and not args.no_open:
        webbrowser.open(target.as_uri())
    return int(any(b['kind'] == 'error' for b in blocks))


if __name__ == '__main__':
    sys.exit(main())
'''


NO_KEY = """


class _NoKey(SystemExit):
    \"\"\"이 랩의 키 없는 길은 완성본 ZIP 하나다 — 공용 llm_client의 키 없음 안내(채팅 붙여 넣기)를 이 랩의 안내로 바꿔 알린다(llm_client 바이트는 그대로).\"\"\"
    def __init__(self, message, code=1):
        if str(message).startswith('키가 없어'):
            message = ('키가 없어 수업 모델에 보내지 않았습니다(.env가 없거나 LLM_API_KEY가 비어 있음).\\n'
                       '키를 받았으면 .env.example을 복사해 이름을 .env로 바꾸고, 강의에서 받은 세 줄을 붙여 넣어 저장한 뒤 같은 명령을 다시 실행합니다.\\n'
                       '키가 없으면 클래스룸에서 실습 폴더와 따로 받는 완성본 ZIP(__ZIP__)으로 결과를 봅니다.')
        print(message)
        super().__init__(code)


llm_client.Stop = _NoKey"""


def run_source(extract, zip_name=''):
    if not extract:
        return RUN.replace('__LLM_IMPORT__', '').replace('__LLM_SETUP__', '').replace('__LLM_ARGS__', '').replace('__LLM_RUN__', '')
    return (RUN.replace('__LLM_IMPORT__', ', llm_client')
            .replace('__LLM_SETUP__', '\nllm_client.configure(ROOT, project=True)   # 응답 기록은 output/model_responses/, 키는 이 폴더의 .env' + NO_KEY.replace('__ZIP__', zip_name))
            .replace('__LLM_ARGS__', "\n    parser.add_argument('--count', action='store_true', help='보내지 않고 응답 기록 수와 남은 수를 봅니다')")
            .replace('__LLM_RUN__', "\n    if args.count:\n        return llm_client.main(['--count'])"))


# 기능 이름 → (결과 화면 제목, 옛 단계 함수, 그 기능이 읽는 정할 자리)
EXTRACT_COMMANDS = {
    False: {'sources': ('사건과 문서 묶음', 'look', []), 'connect': ('수업 모델 연결', 'connect', []),
            'expected': ('기대 항목', 'expect', ['app/features/expected.csv']), 'split': ('나누는 단위', 'split', ['app/features/split.json']),
            'trial': ('요청 글과 한 조각', 'trial', ['app/features/prompt.md']), 'extract': ('주 대상 문서에 실행', 'main_run', []),
            'review': ('사람 검토', 'review', ['app/features/review_decisions.csv']), 'rules': ('조건의 근거', 'rules', ['app/features/rule_links.csv']),
            'other': ('다른 문서에 적용', 'other', []), 'check': ('구조 검사', 'check', [])},
    True: {'sources': ('사건과 문서 묶음', 'look', []), 'connect': ('수업 모델 연결', 'connect', []),
           'expected': ('기대 항목', 'expect', ['app/features/expected.csv']), 'trial': ('나누는 단위와 한 조각', 'split_trial', ['app/features/split.json', 'app/features/prompt.md']),
           'split': ('나누는 단위', 'split', ['app/features/split.json']),
           'extract': ('문서 묶음에 실행', 'main_other', []), 'review': ('사람 검토', 'review', ['app/features/review_decisions.csv']),
           'rules': ('이 작업에 걸린 조건의 근거', 'rules', ['app/features/rule_links.csv']), 'collect': ('준비 · 금지 · 완료 모으기', 'collect', ['app/features/roles.csv']),
           'check': ('구조 검사', 'check', [])}}
GRAPH_COMMANDS = {
    False: {'sources': ('검토 결과와 기존 ID', 'look', []), 'expected': ('기대 답', 'expect', ['app/features/expected.csv']),
            'db': ('랩 DB 준비와 설비 모델 적재', 'prepare', []), 'plan': ('그래프 모양과 ID', 'plan', ['app/features/graph_shape.json']),
            'load': ('승인 지식 적재', 'link', ['app/features/link_rules.csv', 'app/features/roles.csv']),
            'other': ('다른 문서의 조건 · 다시 적재', 'other_twice', ['app/features/other_doc_conditions.csv']),
            'query': ('질문 1~3 조회와 보류 확인', 'ask123', ['app/features/query_values.csv']), 'more': ('다른 문서 추가 반영', 'more', []),
            'scope': ('답할 수 있는 범위', 'scope', ['app/features/current_value_sources.csv']), 'export': ('내보내기', 'save', []), 'check': ('구조 검사', 'check', [])},
    True: {'sources': ('검토 결과와 기존 ID', 'look', []), 'db': ('랩 DB 준비와 검토 결과', 'prepare', []), 'expected': ('기대 카드', 'expect', ['app/features/expected.csv']),
           'plan': ('그래프 모양과 ID', 'plan', ['app/features/graph_shape.json']), 'load': ('승인 지식 적재', 'link', ['app/features/link_rules.csv', 'app/features/roles.csv']),
           'other': ('다른 문서의 조건 · 다시 적재', 'other_twice', ['app/features/other_doc_conditions.csv']),
           'card': ('작업 확인 카드', 'card', ['app/features/query_values.csv', 'app/features/current_value_sources.csv']),
           'scope': ('다른 작업과 답할 수 있는 범위', 'other_scope', []), 'export': ('내보내기', 'save', []), 'check': ('구조 검사', 'check', [])}}


def build_project(key, src, L, folder):
    """옛 구조 폴더 src를 새 프로젝트 folder로."""
    spec = LABS[key]
    practical = spec['course'] == '실전반'
    graph = spec['kind'] == 'graph'
    if folder.exists():
        raise RuntimeError(f'{folder}: 새 폴더에만 씁니다')
    copy_data(src, folder, graph)
    if graph:
        fix_review_hashes(folder, key)
    for name in (GRAPH_SLOTS if graph else EXTRACT_SLOTS):
        p = src / '결과' / name
        if p.is_file():
            text = p.read_text(encoding='utf-8-sig')
            write(folder / 'app/features' / NAMES.get(name, name), text if name == 'prompt.md' else convert(text))
    utilities, ui = P.result_sources()
    write(folder / 'app/utils/results.py', utilities)
    write(folder / 'app/ui/render.py', ui)
    if graph:
        write(folder / 'app/utils/graph.py', convert((HERE / 'doc_graph.py').read_text(encoding='utf-8'), code=True)
              .replace('는 data/reviews에 없는 짝', '는 읽은 검토 결과(app/features/my_inputs/reviews가 있으면 그것, 없으면 data/reviews)에 없는 짝'))
        write(folder / 'app/utils/cypher.py', convert((HERE / 'lab_cypher.py').read_text(encoding='utf-8'), code=True))
        write(folder / 'app/utils/db.py', GP.db_source().replace('새 DB는 비어 있으니, 저장해 둔 적재 · 수정 파일을 같은 순서로 다시 실행하세요.', '설비 모델 · 조치 기준은 이어서 다시 올립니다.')
              .replace("print('새로 만든 랩 DB라 비어 있습니다. 적재부터 다시 실행하세요.')", "print('새로 만든 랩 DB라 정할 자리의 적재가 없습니다. 이어서 python run.py load → python run.py other를 실행합니다.')"))
        commands = GRAPH_COMMANDS[practical]
        fill = {'__TITLE__': L['title'], '__PRACTICAL__': str(practical), '__TASK__': TASK, '__LATER__': repr(BD.LATER_DOCS),
                '__ITEMS__': repr(BD.CARD_HEADINGS if practical else None), '__KIND__': 'graph'}
        template, check_template = BD.GRAPH_STEPS, BD.graph_checker(key)
    else:
        write(folder / 'app/utils/extract.py', convert((HERE / 'doc_extract.py').read_text(encoding='utf-8'), code=True))
        (folder / 'app/utils/llm_client.py').write_bytes((HERE / 'lab_llm.py').read_bytes())
        write(folder / '.env.example', (src / '.env.example').read_text(encoding='utf-8'))
        commands = EXTRACT_COMMANDS[practical]
        fill = {'__TITLE__': L['title'], '__PRACTICAL__': str(practical), '__TASK__': TASK, '__ASSET__': BD.ASSET, '__EVENT__': BD.EVENT_UTC,
                '__JUDGED__': convert(BD.JUDGED[key]), '__OTHER__': repr([DOCS[d] for d in BD.OTHER_DOCS]), '__KIND__': 'extract'}
        template, check_template = BD.EXTRACT_STEPS, BD.checker(key)
    write(folder / 'app/utils/actions.py', actions_source(template, fill, commands))
    write(folder / 'run.py', run_source(not graph, folder.name + '-completed.zip'))
    provided = [p.relative_to(folder).as_posix() for p in sorted(folder.rglob('*')) if p.is_file()
                and p.relative_to(folder).as_posix().startswith(('app/ui/', 'app/utils/')) or p.name == 'run.py']
    write(folder / 'app/utils/check.py', checker_source(check_template, folder, provided))
    title = L['title']
    write_metadata(folder, title, PURPOSE[key], command='python run.py db' if practical and graph else 'python run.py', extra_rules=rules_for(key))
    for p in sorted(folder.rglob('*.py')):   # 옮긴 코드가 파이썬으로 읽히는지(실행 전에 파일:줄로 멈춘다)
        compile(p.read_text(encoding='utf-8'), str(p), 'exec')
    bad = residue(folder)
    if bad:
        raise RuntimeError(f'{folder.name}: 옛 경로 · 이름이 남음\n- ' + '\n- '.join(bad[:40]))
    return commands


def rules_for(key):
    practical = LABS[key]['course'] == '실전반'
    if LABS[key]['kind'] == 'graph':
        return RULES['graph'] + '\n' + DB_RULE
    return RULES['extract'].replace('__OTHER__', '' if practical else ' · `other`').replace('__JUDGED__', '조치 검토 결과' if practical else '판정 결과')


RULES = {   # AGENTS.md에 더하는 이 랩의 작업 경계(코딩랩 K-6 — 정답 · 단계표 없음)
    'extract': ('- 정할 자리는 `app/features/`의 파일이다. 후보 · 검토 결과 · 응답 기록 · 요청 글은 제공 코드가 `output/`에 쓴다. 응답 기록(`output/model_responses/`)은 고치지 않는다.\n'
                '- 수업 모델을 부르는 실행(`python run.py connect` · `trial` · `extract`__OTHER__)은 사람이 자기 터미널에서 한다. 키 · 접속 값을 채팅 · 파일 · 기록에 적지 않는다.\n'
                '- 지식 후보는 모델의 답에서 만든다. `data/`의 SOP 구조 · 조건표를 후보로 옮기지 않고, 조건표 · __JUDGED__는 바꾸지 않는다.\n'
                '- 어느 문서를 따를지, 어느 원문을 조건의 근거로 둘지는 사람이 원문 줄을 근거로 정한다.'),
    'graph': ('- 정할 자리는 `app/features/`의 파일이다. 적재 · 조회 · 내보내기는 제공 코드가 하고 그 결과를 `output/`에 쓴다.\n'
              '- 승인(`approved`) 후보만 적재한다. 기존 ID를 바꾸거나 모델에 없는 ID를 지어내지 않는다.\n'
              '- 현재값(재고 · 작업지시 상태 · 센서 값)은 그래프에 넣지 않고 읽을 원천을 가리킨다.\n'
              '- 다른 문서의 조건을 이을지, 무엇을 어느 기존 ID에 이을지는 사람이 원문 줄을 근거로 정한다.'),
}
PURPOSE = {
    'integrated-04-extract': '포털에서 본 문서 지식화 과정을 직접 만듭니다. 문서를 나누는 단위와 수업 모델에 보낼 요청 글을 정해 근거 있는 지식 후보를 받고, 원문과 견줘 채택 · 수정 · 제외 · 보류를 기록합니다.',
    'integrated-04-graph': '검토해 승인한 문서 지식을 랩 DB의 설비 모델과 조치 기준에 기존 ID로 잇습니다. 가이드의 다섯 질문으로 조회한 답을 원문과 견주고 하나의 온톨로지 구축 결과로 저장합니다.',
    'practical-03-extract': '포털에서 본 문서 지식화 과정을 직접 만듭니다. 근거 있는 지식 후보를 받아 원문과 견줘 결정하고, 핀 세척 작업의 준비 · 금지 · 완료 조건을 모읍니다.',
    'practical-03-card': '검토해 승인한 문서 지식을 랩 DB의 기존 ID에 잇고, 핀 세척 작업 확인 카드를 원문 출처와 함께 만듭니다.',
}


# ───────────── 가이드(지금 할 이유 · 첫 행동 · 확인할 결과) ─────────────
TERMINAL_LINES = ('**터미널 → 새 터미널**', '터미널을 엽니다')


def section(name, text, **kw):
    """본보기(session2_project_guides.section)와 같은 절. 터미널을 여는 문장은 그 절의 설명 맨 뒤, 명령 블록 바로 앞에 둔다."""
    return SG.section(name, [t for t in text if not t.startswith(TERMINAL_LINES)] + [t for t in text if t.startswith(TERMINAL_LINES)], **kw)


def event_facts(folder, key):
    """가이드 첫 단계의 사건 시각 — 경보 시각(사건 메모)과 결과 화면이 보이는 판정 요청 시각(UTC)을 나눠 적는다(같은 경보를 찾는 규칙은 actions.event와 같음)."""
    name = 'action_review.json' if LABS[key]['course'] == '실전반' else 'result.json'
    if not (folder / 'data' / name).is_file():   # 판정 결과를 받지 않는 랩(통합 그래프) — 결과 화면에 판정 요청 시각이 없다
        return None
    data = json.loads((folder / 'data' / name).read_text(encoding='utf-8'))
    mins = lambda t: int(t[8:10]) * 1440 + int(t[11:13]) * 60 + int(t[14:16])
    e = min((x for x in data['events'] if x['asset'] == BD.ASSET), key=lambda x: abs(mins(x['decision_time']) - mins(BD.EVENT_UTC)))
    t = e['decision_time']
    kst = (int(t[11:13]) + 9) % 24
    return {'id': e['id'], 'utc': t[11:16], 'kst': f'{kst:02d}:{t[14:16]}'}


SAVE_NOTE, IMPL_NOTE = SG.SAVE_NOTE, SG.IMPL_NOTE
COPY_WHY = '오타를 줄이도록 명령은 직접 치지 말고 블록의 **복사**로 붙여 넣습니다.'


def opening(key, event, facts, files_note, user, first=True):
    spec = LABS[key]
    text = [f'클래스룸의 {spec["n"]}회차 실습 자료에서 ZIP을 받아 **압축 풀기**를 선택합니다. VS Code의 **파일 → 폴더 열기**에서 `{spec["name"]}` 폴더를 엽니다. 함께 풀린 가이드는 브라우저로 엽니다.',
            '신뢰 여부를 물으면 **예, 작성자를 신뢰합니다**(Yes, I trust the authors)를 선택합니다. 제한 모드에서는 Codex를 사용할 수 없습니다.',
            files_note,
            (f'사건은 {event}(경보 `{facts["id"]}`)이고, 그 판정 뒤에 남은 근본 조치가 쿨러 핀 세척(`{TASK}`)입니다. 결과 화면의 판정 요청 시각 {facts["utc"]}(UTC)은 한국 시각 {facts["kst"]}입니다. {user}'
             if facts else f'사건은 {event}이고, 그 판정 뒤에 남은 근본 조치가 쿨러 핀 세척(`{TASK}`)입니다. {user}'),
            ('**터미널 → 새 터미널**을 엽니다. ' if first else '터미널을 엽니다. ') + COPY_WHY]
    return text


OPEN_RESULT = ('결과는 `output/result.html`에 저장됩니다. 브라우저가 열리지 않으면 Windows 파일 탐색기로 이 실습 폴더의 output 폴더를 열고 result.html을 두 번 누릅니다'
               '(VS Code 탐색기에서 누르면 화면이 아니라 HTML 글이 열립니다). 이후에는 명령을 실행한 뒤 열린 화면에서 F5를 누릅니다.')
FINGERPRINT = '문서 목록의 SHA-256은 파일 내용으로 계산한 지문이라 한 글자만 달라도 바뀝니다. 결과 화면은 목록과 지문이 같은 파일만 판본으로 읽습니다.'
RISKS = '누락 · 부정 조건 누락 · 수치 · 단위 오류 · 잘못된 관계 추론 · 근거 없는 내용 생성'
DECIDE_MINE = 'Codex가 고를 것을 내놓거나 「권장」을 붙여도 따르지 말고 원문 줄을 열어 내 선택과 근거를 말합니다. 못 정하면 미결로 둡니다.'


def extract_guide(key, event, facts):
    practical = key == 'practical-03-extract'
    name = LABS[key]['name']
    judged = '조치 검토 결과' if practical else '판정 결과'
    files_note = (f'`README.md`에서 폴더 역할을 봅니다. `data/`는 문서 묶음과 조건표 · SOP 구조 · {judged}, `app/features/`는 내가 Codex와 채울 정할 자리입니다. '
                  '문서를 읽고 나누어 보내고 답을 지식 후보로 바꾸는 일은 제공 코드가 합니다. `AGENTS.md`는 Codex가 지킬 공통 원칙이고, 파일의 모양과 칸의 뜻은 `data/contract.md`에 있습니다. '
                  + FINGERPRINT)
    user = ('이 답은 보전 야간조가 핀 세척 전에 준비 · 금지 · 완료를 원문으로 되짚고, 설비보전팀장이 작업지시를 승인할 때 씁니다.' if practical else
            '이 답은 설비보전팀장이 핀 세척 작업지시를 내기 전에, 이 작업의 조건과 판정에 쓴 조건이 문서 어디에서 왔는지 원문 인용으로 확인할 때 씁니다.')
    mine = (f'조치를 판정하는 실습에서 만든 내 조건표 · SOP 구조 · {judged}를 쓰는 것은 선택입니다. 쓸 때는 형식이 `data/contract.md` 「입력」과 같은지 견주고, `app/features/my_inputs/`에 `data/`와 같은 이름으로 복사합니다. '
            '없어도 제공 입력으로 끝까지 할 수 있습니다.') if not practical else (
            f'`data/action_review.json`은 판정 · 성과 비교 실습의 조치 검토 결과와 같은 꼴입니다. 내 결과를 쓰려면 형식을 `data/contract.md` 「입력」과 견준 뒤 `app/features/my_inputs/`에 같은 이름으로 복사합니다(선택).')
    no_key = f'키가 없으면 실습 폴더와 따로 받는 완성본 ZIP(`{name}-completed.zip`)으로 결과를 봅니다. 그때는 모델을 부르지 못한 단계를 `review.md`에 그렇다고 적습니다.'
    env_how = ('`.env.example`을 복사해 이름을 `.env`로 바꿉니다(탐색기에서 오른쪽 클릭 **복사**(Copy) → 빈 곳 **붙여넣기**(Paste) → 사본 **이름 바꾸기**(Rename)). '
               '`.env`를 열어 등호(=) 뒤가 비어 있는 세 줄을 지우고, 그 자리에 강의에서 받은 세 줄을 그대로 붙여 넣은 뒤 **Ctrl+S**로 저장합니다. 손으로 정하거나 고칠 값은 없습니다.')
    if practical:
        env_how = '`.env.example`을 복사해 이름을 `.env`로 바꾸고, 등호 뒤가 빈 세 줄을 지운 뒤 그 자리에 받은 세 줄을 그대로 붙여 넣어 **Ctrl+S**로 저장합니다.'
    wait = (f'조각마다 요청을 하나씩 보내므로 조각 수만큼 기다립니다. 같은 요청은 다시 보내지 않고, `output/model_responses/`에 보낸 기록이 {LLM.MAX_SENT}개가 되면 더 보내지 않습니다(비용을 지키는 이 폴더의 상한).')
    count_check = '먼저 보낼 요청 수가 남은 수 안인지 봅니다. 많으면 보낼 문서를 줄이거나 조각을 크게 묶습니다.'
    main_check = ('문서마다 지식 후보 · 찾지 못한 인용 · 잘린 답 수와, 기대 항목마다 맞음 · 종류 다름 · 줄 못 정함 · 누락이 보입니다. 「같은 요청의 기록이 … 개」로 멈추면 두 답을 원문 줄과 견줘 '
                  '`split.json` 「쓸_기록」에 고른 기록을 적습니다. 「길이 상한에서 잘린 답」이 핀 세척 조각이면 단위나 상한을 줄여 다시 실행합니다.')
    trial_check = ('두 답의 지식 후보 표(종류 · 절 · 줄 · 찾은 방법 · 인용)와 받은 SOP 구조 항목과의 짝 표가 보입니다. 다른 곳이 요청 글 때문인지 모델 응답 때문인지 원문 줄로 말할 수 있으면 요청 글을 굳힙니다. '
                   '후보 표가 비고 경고만 있으면 요청 글에 필드 이름을 적었는지 봅니다. 「같은 요청은 2번까지」가 나오면 요청 글을 고쳐야 새 요청이 됩니다.')
    split_why = '한 번에 보내는 글이 길면 답이 잘리거나 빠뜨리는 것이 늘고, 너무 짧게 자르면 조건과 그 대상이 다른 조각으로 갈라집니다. 문서마다 보관 단위(절 · 절차 · 쪽)가 달라 어디서 끊을지가 결과를 가르고, 조각 수만큼 요청을 보냅니다.'
    prompt_why = ('요청 글은 모델에게 주는 작업 지시이고, 구조화 출력은 답의 모양만 맞출 뿐 그 안의 사실이 원문과 같은지는 따로 확인해야 합니다. 같은 요청에도 답이 달라질 수 있어, '
                  '문서 전체에 보내기 전에 한 조각을 두 번 보내 받은 SOP 구조와 견주고 요청 글을 굳힙니다.')
    prompt_how = ('`app/features/prompt.md`의 다섯 칸(뽑을 것 · 지킬 것 · 하지 말 것 · 모르면 · 답의 꼴)을 Codex와 하나씩 정해 채웁니다. 모델은 이 폴더의 파일을 읽지 못하므로 답의 필드 이름과 값을 요청 글에 직접 적습니다. '
                  '`split.json` 「시험_조각」에는 먼저 보내 볼 핀 세척 줄을 「파일:줄」로 적습니다. 아래 명령은 그 조각을 보내고 같은 요청을 한 번 더 보냅니다(Codex 채팅이 대신 실행하면 「[Errno 1] Operation not permitted」로 멈춥니다).')
    prompt_toggle = ('app/features/prompt.md의 다섯 칸을 나와 함께 채우자. data/contract.md 4절의 후보 필드 이름과 종류의 뜻을 글에 직접 적고, 칸마다 네 안을 보이면 내가 고르거나 고칠게. '
                     '내가 말하지 않은 칸은 먼저 물어봐. split.json 「시험_조각」에는 내가 고른 핀 세척 줄만 적어 줘.')
    s = [section('폴더 열고 사건과 문서 확인하기', opening(key, event, facts, files_note, user, not practical) + [mine],
                 cmd='python run.py', check='사건 경보의 조치 후보, 핀 세척이 걸린 관계, 문서 묶음의 판본 · 상태 · 글자 방식 표가 보입니다. ' + OPEN_RESULT),
         section('Codex와 핀 세척 원문 찾기', [
             '문서마다 판본 · 형식이 달라, 핀 세척 조건이 어디에 있는지 먼저 알아야 기대를 적을 수 있습니다. Codex 확장 아이콘을 눌러 채팅을 열고 로그인합니다. '
             f'계정이 없거나 막히면 클래스룸에서 실습 폴더와 따로 받는 완성본 ZIP(`{name}-completed.zip`)으로 결과를 실행해 볼 수 있습니다.',
             '파일을 바꾸지 말고, 핀 세척 작업의 원문이 문서마다 어느 절 · 줄에 있는지와 이 작업이 즉시 완화가 아니라 근본 조치라는 근거 줄을 물어봅니다. 답에 나온 줄은 `data/documents/`에서 직접 엽니다.'
             + (' 확인한 작업과 그 줄을 `app/features/review.md` 「이 사건의 작업」에 적습니다.' if practical else ''),
             '이번에는 포털에 문서를 올리거나 포털의 추출 기능을 부르지 않고, 문서를 고쳐 쓰거나 번역하지 않습니다.'] + ([SAVE_NOTE] if practical else []),
             check='문서마다 핀 세척 절 · 줄을 말할 수 있으면 이어 갑니다. 짚은 줄이 없거나 다르면 근거로 쓰지 않고 다시 찾게 합니다. Codex가 파일을 바꾸려 하면 취소합니다.', ai=True),
         section('수업 모델 연결 확인하기', [
             '문서 조각을 수업 모델에 보내 지식 후보를 받습니다. 첫 요청은 서버가 준비되느라 1분쯤 걸릴 수 있어 여기서 미리 한 번 보냅니다.', env_how,
             '키는 이 폴더의 `.env`에만 둡니다. 키가 새면 다른 사람이 내 한도로 모델을 부를 수 있으므로 채팅 · 다른 파일 · 기록에 붙이지 않습니다.'],
             cmd='python run.py connect',
             check=('「연결됨」 줄과 모델 이름이 보입니다. 「키가 없어 수업 모델에 보내지 않았습니다」면 파일 이름이 `.env`인지, 탭 이름 옆 ●가 없는지 봅니다. 「.env의 … 값이 비어 있습니다」면 그 줄을 다시 붙여 넣고, '
                    '「.env … 줄에 … 두 번 있습니다」면 빈 줄을 지웁니다. '
                    f'{LLM.TIMEOUT_S}초 안에 답이 없으면 「모델 서버에 닿지 못했습니다」로 멈추니 1분쯤 뒤 같은 명령을 다시 실행합니다. ' + no_key)),
         section('기대 항목 먼저 적기', [
             '모델의 답을 본 뒤에 기대를 적으면 빠진 것과 지어낸 것이 기대에 섞여 보이지 않습니다. 02에서 찾은 핀 세척 줄(준비 · 방법 · 금지 · 완료 · 승인)을 '
             '`app/features/expected.csv`에 파일 · 줄 · 종류로 적습니다. 종류의 뜻은 `data/contract.md` 4절, 칸의 뜻은 파일 첫 줄에 있습니다.',
             '판본이 다른 같은 문서, 영문 원본과 번역이 함께 있는 줄, 부정 조건과 범위 참조(「~부터 ~까지」), 경계 낱말(초과 · 이상 · 미만 · 이내), 원문 여러 곳에 맞는 인용 같은 줄도 찾아 둡니다.',
             '`app/features/review.md`에 목표와 질문, 이 답을 쓰는 사람, 기대 칸을 쓴 시각을 적습니다.', SAVE_NOTE, IMPL_NOTE],
             prompt='02에서 함께 찾은 핀 세척 줄을 종류와 함께 app/features/expected.csv에 파일 · 줄 · 종류로 적어 줘. 종류를 정하지 못한 줄은 먼저 물어보고, 원문에 없는 줄은 넣지 마.',
             cmd='python run.py expected', check='내가 적은 줄의 원문과 종류가 보입니다. 이 표가 뒤에서 지식 후보와 견줄 기준이므로, 결과에 맞추려고 기대를 바꾸지 않습니다.', ai=True)]
    if practical:
        s.append(section('나누는 단위와 요청 글을 한 조각으로 시험하기', [
            split_why + ' Codex에게 단위(절 · 절차 · 쪽 · 글자)마다 핀 세척 절차가 몇 조각에 걸치는지 묻고, 정한 단위 · 글자 상한을 `app/features/split.json`에, 까닭을 `decisions.csv`에 한 줄 적습니다.',
            prompt_why, prompt_how],
            prompt='지금 정한 나누는 단위와 글자 상한을 split.json에 넣고, 정한 까닭을 decisions.csv에 한 줄 적어 줘. 이어서 ' + prompt_toggle,
            cmd='python run.py trial', check='문서마다 조각 수가 보이고 핀 세척 절차가 한 조각 안에 있습니다. ' + trial_check, ai=True))
        s.append(section('문서 묶음에 실행하고 기대 · 다른 문서와 견주기', [
            '한 조각에서 맞은 요청 글도 다른 절 · 다른 문서에서는 빠뜨리거나 지어냅니다. `split.json` 「보낼_문서」에 핀 세척 원문 · 이 작업에 걸린 조건의 근거를 가진 문서와 다른 문서(정기 점검표 · 예비품 기준 · 보충 매뉴얼)를 적습니다. ' + wait,
            f'기대와 다른 줄 두세 개의 차이 종류({RISKS})를 `review.md` 「기대와 다른 줄」에, 받은 SOP 구조와 짝이 없는 칸 두세 개를 원문 줄로 열어 본 실제 누락 · 근거 없는 내용 생성 수를 「다른 문서에 적용」에 적습니다.'],
            prompt='결과 화면에서 기대와 다른 줄과 짝 없는 칸을 하나씩 골라 원문 · 내 기대 · 지식 후보를 견줘 설명해 줘. 내가 차이 종류를 정하면 review.md 「기대와 다른 줄」 · 「다른 문서에 적용」 표에 그 행을 적어 줘. 다른 파일은 바꾸지 마.',
            cmd='python run.py split', check=count_check,
            followup=[('python run.py extract', main_check)], ai=True))
    else:
        s.append(section('문서를 나누는 단위 정하기', [
            split_why,
            'Codex에게 단위(절 · 절차 · 쪽 · 글자)마다 핀 세척 절차가 몇 조각에 걸치는지 물어봅니다. 정하는 것은 내가 하고, 단위 · 글자 상한을 `app/features/split.json`에, '
            '고른 까닭을 `app/features/decisions.csv`에 한 줄 적습니다. 칸의 뜻은 `data/contract.md` 「정할 자리」에 있습니다.'],
            prompt='단위(절 · 절차 · 쪽 · 글자)마다 핀 세척 절차가 몇 조각에 걸치는지 보여 줘. 내가 단위와 글자 상한을 고르면 app/features/split.json의 「단위」 · 「글자_상한」에 넣고, 고른 까닭을 decisions.csv에 한 줄 적어 줘. 다른 칸은 비워 둬.',
            cmd='python run.py split', check='문서마다 조각 수와 줄 범위가 보이고, 핀 세척 절차가 한 조각 안에 있습니다. 절차가 두 조각으로 갈라지면 단위나 상한을 바꿔 다시 봅니다.', ai=True))
        s.append(section('요청 글 쓰고 한 조각으로 시험하기', [prompt_why, prompt_how],
                         prompt=prompt_toggle, cmd='python run.py trial', check=trial_check, ai=True))
        s.append(section('주 대상 문서에 실행하고 기대와 견주기', [
            '한 조각에서 맞은 요청 글도 문서 전체에서는 빠뜨리거나 다른 절에 잇는 것이 생깁니다. 원문에서 적은 기대와 줄마다 견주어야 차이가 단위 · 요청 글 때문인지 모델 응답 때문인지 나눌 수 있습니다.',
            '`split.json` 「보낼_문서」에 핀 세척 원문과 조건표 조건의 근거를 가진 문서를 적습니다. ' + wait,
            f'기대와 다른 줄 두세 개의 차이 종류({RISKS})를 `review.md` 「기대와 다른 줄」에 적습니다.'],
            prompt='결과 화면에서 기대와 다른 줄 하나의 원문, 내 기대, 지식 후보를 견줘 차이가 나눈 단위 · 요청 글 때문인지 모델 응답 때문인지 설명해 줘. 내가 차이 종류를 정하면 review.md 「기대와 다른 줄」 표에 그 행을 적어 줘. 다른 파일은 바꾸지 마.',
            cmd='python run.py split', check=count_check, followup=[('python run.py extract', main_check)], ai=True))
    rules_name = '이 작업에 걸린 조건의 근거 견주기' if practical else '조건표 조건의 근거 견주기'
    rules_scope = '이 작업에 걸린 조건' if practical else '조건표의 조건'
    s.append(section('지식 후보 검토하기 — 사내 문서와 제조사 지침', [
        '사람 검토의 네 결정은 채택 · 수정 · 제외 · 보류이고, 보류는 근거가 더 필요하다는 기록이지 버린 것이 아닙니다. 원문과 견주지 않은 지식 후보는 승인하지 않습니다.',
        '같은 작업을 사내 문서와 제조사 지침이 함께 말하면, 제조사 지침이 사내 기준과 다르게 정하거나 정하지 않은 줄을 어떻게 둘지 문서 머리말 · 문서 관리 기준 줄을 열어 내가 정하고 `decisions.csv`에 적습니다. ' + DECIDE_MINE,
        '그 처리대로 `app/features/review_decisions.csv`에 기대 항목 줄마다 결정 · 근거 · 까닭을 적습니다. 같은 결정이 이어지는 줄은 줄 칸을 비운 판단 규칙 한 행으로 씁니다.'],
        prompt='내가 decisions.csv에 적은 사내 문서와 제조사 지침의 처리 방식대로, 기대 항목 줄마다 결정 · 근거 · 까닭을 app/features/review_decisions.csv에 적어 줘. 원문과 견주지 않은 줄은 보류로 두고, 내가 정하지 않은 줄은 먼저 물어봐.',
        cmd='python run.py review', check='검토 결과 파일마다 결정 수와 기대 항목 줄의 결정이 보이고, 채택 · 수정 · 제외마다 원문 근거가 있습니다. 빨간 칸이 짚는 행을 고칩니다. '
        '같은 문장이 여러 곳이라 줄을 정하지 못한 인용은 결정 표에 그 줄을 적으면 검토자가 더한 지식 후보가 됩니다.', ai=True))
    s.append(section(rules_name, [
        '허용 · 제외 조건은 출처로 돌아갈 수 있어야 고칠 수 있습니다. 원문이 말하는 대상 · 때와 조건이 거는 대상 · 때가 같은지 견주어야 그 원문이 그 조건의 근거인지 말할 수 있습니다.',
        f'{rules_scope}(`rule_id`)마다 근거 원문(파일:줄)과 맞는 정도를 내가 정해 `decisions.csv`에 적고, 그대로 `app/features/rule_links.csv`에 근거 · 맞는 정도 · 까닭 · 요청할 것을 적습니다. '
        '조건표와 결과 파일은 고치지 않고 바꿀 것은 요청할 것 칸에 둡니다.'],
        prompt=f'{rules_scope}마다 근거 후보가 될 원문 줄을 보여 줘. 내가 맞는 정도를 정하면 decisions.csv에 한 줄, app/features/rule_links.csv에 근거 · match · 까닭 · 요청할_것을 적어 줘. 원문을 찾지 못한 조건은 원문 없음으로 두고 근거를 비워 줘. 조건표는 바꾸지 마.',
        cmd='python run.py rules', check='조건마다 근거 원문 줄 · 맞는 정도와, 그 조건이 핀 세척을 제외한 지난 판정이 보입니다. 아직 근거 견주기가 없는 조건이 남지 않아야 합니다. '
        '「그 줄에 후보가 없음」이면 그 줄을 review_decisions.csv에 넣고 다시 실행합니다.', ai=True))
    if practical:
        s.append(section('준비 · 금지 · 완료 모으기', [
            '작업 전에 확인할 조건은 그 작업의 절차 안에만 있지 않습니다. 시작 전 조건 · 금지 · 완료 확인이 다른 절이나 다른 문서에 있을 수 있어, 모아 두어야 작업자가 한 번에 되짚습니다.',
            '`app/features/roles.csv`에 승인한 지식 후보의 종류(와 인용에 든 글자)를 이 작업의 준비 · 금지 · 완료 가운데 어디에 둘지, `data/contract.md` 7절 roles.csv의 기본과 다르게 둘 것만 적습니다. 방법 단계는 넣지 않고, 첫 단계가 작업 전 확인이면 준비로 둡니다.'],
            prompt='승인한 지식 후보 가운데 계약 7절 roles.csv의 기본과 다르게 둘 종류 · 글자를 보여 줘. 내가 준비 · 금지 · 완료 가운데 어디에 둘지 정하면 app/features/roles.csv에 적어 줘. 내가 정하지 않은 단계는 먼저 물어봐.',
            cmd='python run.py collect', check='준비 · 금지 · 완료 · 추가 자료가 필요한 질문 · SOP 구조와 다른 곳의 수와 항목마다 원문 인용이 보입니다. 항목 두세 개를 원문 줄로 열어 봅니다. 「어느 행에도 맞지 않는 승인 후보」면 그 종류의 행을 더합니다.', ai=True))
    else:
        s.append(section('다른 문서에 다시 적용하기', [
            '누락은 원문에 있는데 지식 후보에 없는 것, 근거 없는 내용 생성은 지식 후보에 있는데 원문에 없는 것입니다. 한 문서에 맞춘 단위 · 요청 글이 형식이 다른 문서에서도 맞는지는 돌려 세어 봐야 압니다.',
            '`split.json` 「보낼_문서」에 정기 점검표 · 예비품 기준 · 보충 매뉴얼을 더하고 실행합니다. 받은 SOP 구조의 한 칸은 여러 절을 합쳐 적은 것이 있어, 짝이 없는 칸 두세 개를 원문 줄로 열어 실제 누락인지 보고 '
            '`review.md` 「다른 문서에 적용」에 실제 누락 · 근거 없는 내용 생성 수를 적습니다.'],
            prompt='결과 화면에서 짝 없는 칸 하나가 원문의 어느 줄인지 짚고 실제 누락인지 여러 절을 합쳐 적은 것인지 설명해 줘. 내가 판단하면 review.md 「다른 문서에 적용」 표에 그 문서의 행을 적어 줘. 다른 파일은 바꾸지 마.',
            cmd='python run.py other', check='문서마다 지식 후보 · 찾지 못한 인용 수와 짝 표가 보이고, 기록에 센 수가 있습니다. 고치는 일은 마지막 단계에서 합니다.', ai=True))
    s.append(section('고치고 저장해 다시 열기', [
        '앞에서 적어 둔 누락 · 근거 없는 내용 생성 가운데 하나를 정할 자리(나누는 단위 · 요청 글 · 결정 표)에서 고치고, 그 문서를 `split.json` 「다시_보낼_문서」에 적어 아래 명령으로 다시 셉니다. '
        '이미 지식 후보가 있는 다른 문서는 그때 만든 그대로 둡니다. 다시 센 수를 `review.md`에 적습니다.',
        '**파일 → 모두 저장**을 선택하고 폴더를 닫았다 다시 연 뒤 구조 검사를 실행합니다. `review.md` 끝에 기준일 · 저장 시점 · 확인하지 못한 점을 적고, 응답 기록(`output/model_responses/`)까지 실습 폴더 전체를 USB나 개인 클라우드에 보관합니다(재부팅하면 학교 PC 파일이 초기화될 수 있습니다).'],
        prompt='구조 검사 출력이 가리키는 파일과 칸을 찾아 어느 정할 자리에서 생긴 문제인지 설명해 줘. 원자료 · 응답 기록 · 검사 기준은 바꾸지 마. 내가 원인을 확인하면 필요한 부분만 고쳐 줘.',
        cmd='python run.py extract', check='고친 문서의 지식 후보 수가 바뀐 만큼 기대 항목과 다시 견줍니다.',
        followup=[('python run.py check', '「구조 검사 통과」가 보이면 저장한 결과의 구조가 맞습니다. 「구조 확인 필요」 아래 줄마다 어느 파일을 채울지 보고 채운 뒤 다시 실행합니다. 구조가 맞아도 무엇을 채택할지는 원문과 견줘 판단합니다.')]))
    return s


def graph_guide(key, event, facts):
    practical = key == 'practical-03-card'
    name = LABS[key]['name']
    data_note = ('`README.md`에서 폴더 역할을 봅니다. `data/reviews/`는 문서에서 뽑은 지식 후보를 원문과 견줘 결정을 적은 검토 결과로, 문서 지식을 추출 · 검토하는 실습의 결과와 같은 꼴입니다. '
                 '`data/model/`은 설비 모델, `data/sop.json` · `data/conditions.csv`는 조치 기준, `data/documents/`는 원문입니다. 적재 · 조회 · 내보내기는 제공 코드가 하고, '
                 '`app/features/`에는 무엇을 어디에 이을지 내가 정할 자리가 있습니다. `AGENTS.md`는 Codex의 공통 작업 원칙입니다.')
    mine = ('내 앞 결과를 쓰는 것은 선택입니다. 쓸 때는 형식이 `data/contract.md` 「입력」과 같은지 먼저 견주고, `app/features/my_inputs/`에 `data/`와 같은 이름 · 같은 자리로 복사합니다(검토 결과는 `my_inputs/reviews/`'
            + (', 이 사건의 작업 조건은 추출 실습의 `output/selected_task.json`을 `my_inputs/reviews/selected_task.json`으로' if practical else '') + '). '
            '넣은 검토 결과는 제공 검토 결과를 통째로 대신하므로, 내 결과에 없는 문서의 행은 연결 규칙에서 뺍니다. 제공 입력은 그대로 둡니다.')
    docker = 'Docker Desktop을 켜고 실행 중인지 본 뒤 아래 명령을 실행합니다. 이 폴더 전용 랩 DB가 만들어지고, 설비 모델과 조치 기준(SOP 구조 · 조건표)이 올라갑니다. 포털 DB와 떨어져 있어 여러 번 넣어도 포털에 영향이 없습니다.'
    docker_off = '「랩 DB 꺼짐」이 나오면 Docker Desktop이 켜져 있는지 보고 같은 명령을 다시 실행합니다.'
    shape = ('스키마의 종류는 그래프의 레이블이 되고, 대상 하나를 저장한 것이 노드입니다. ID는 그래프 전체에서 하나여야 해서, ID를 어떻게 짓느냐에 따라 서로 다른 대상이 한 노드로 합쳐지거나 다시 적재할 때 늘어납니다.')
    link_why = '문서 속 대상은 모델과 다른 이름(설비 모델명 · 제조사 품번)으로 적혀 있어, 어느 기존 ID를 가리키는지 정해야 새 대상을 지어내지 않고 잇습니다. 승인한 것만 이어야 이 지식을 쓰는 쪽이 근거 있는 지식만 씁니다.'
    again = 'CREATE는 실행할 때마다 새로 만들고 MERGE는 같은 ID가 있으면 찾으므로, ID가 맞아야 다시 넣어도 늘지 않습니다. 다른 문서의 조건은 그 문서의 적용 범위와 이 작업을 말하는 사내 문장이 어긋날 수 있어 사람이 정합니다.'
    encoding = '원문 글자가 깨져 보이면 VS Code 오른쪽 아래 **UTF-8**을 눌러 **Reopen with Encoding → Korean (EUC-KR)**으로 다시 엽니다.'
    rec = 'app/features/build_record.md'
    outside = '검토 결과의 결정(채택 · 수정 · 제외 · 보류)과 기존 ID · 종류 · 관계의 뜻은 바꾸지 않습니다. 바꿀 것은 추가 자료가 필요한 질문으로 남깁니다.'
    ask_target = '02에서 적은 카드 항목 하나(예: 금지 · 제한)' if practical else '03에서 적은 다섯 질문 가운데 하나'
    shape_step = section('그래프 모양과 ID 정하기', [
        shape, '`app/features/graph_shape.json`에 문서 · 판본 · 절 · 지식과 그 관계의 이름 · 뜻, 판본을 따로 둘지(칸 이름 「판을_따로_둠」), 새 대상의 ID를 짓는 꼴을 Codex와 하나씩 정하고 그 까닭을 `decisions.csv`에 적습니다. '
        f'Codex에게 {ask_target}를 이 모양에 대어 어느 노드 · 관계를 따라 답이 나오는지 짚게 합니다. 칸의 뜻은 `data/contract.md` 「정할 자리」에 있습니다.'],
        prompt=f'app/features/graph_shape.json의 칸을 나와 함께 채우자. 칸마다 네 안과 그 까닭을 보이면 내가 고를게. 설비 모델이 쓰는 종류 이름은 쓰지 말고, 고른 뒤에는 {ask_target}가 이 모양에서 어느 노드 · 관계를 따라 답하는지 보여 줘. 까닭은 decisions.csv에 한 줄 적어 줘.',
        cmd='python run.py plan', check='적재하지 않고 센 노드 수와 적재하지 않는 보류 · 제외 수가 보이고, 「같은 ID에 서로 다른 대상이 겹침」이 없습니다. 겹치면 그 ID들이 어느 문서 · 판본 · 절인지 보고 ID 꼴에 빠진 자리를 더합니다.', ai=True)
    load_step = section('승인 지식을 기존 ID에 잇고 적재하기', [
        link_why, '`app/features/link_rules.csv`에 검토 결과의 문서마다(필요하면 절마다) 승인 후보를 어느 기존 ID에 어떤 관계로 이을지, `aliases.csv`에 원문의 이름 · 품번이 가리키는 기존 ID, '
        '`roles.csv`에 조치에 잇는 지식의 항목을 적습니다.' + ('' if practical else ' 제조사 지침과 예비품 기준의 행은 다른 문서 추가 단계에서 채웁니다.'), outside],
        prompt=('내가 정한 문서마다의 잇는 방법과 근거대로 link_rules.csv · aliases.csv · roles.csv를 채워 줘. 승인 후보만 잇고 모델에 없는 ID를 지어내지 마. '
                + ('' if practical else '제조사 지침과 예비품 기준의 행은 아직 넣지 마. ') + '기존 ID를 찾지 못한 대상은 어떻게 둘지 먼저 물어봐.'),
        cmd='python run.py load', check='적재 전후 수와 기존 ID에 이은 지식 수가 보이고, 「모델에 없는 ID」 오류가 없습니다. 「핀 세척과 그 단계에 이은 지식」 표의 몇 행을 그 줄 번호로 원문에서 열어 확인합니다. 빨간 칸이 짚는 파일 · 행을 고칩니다.', ai=True)
    other_step = section('다른 문서의 조건 정하고 다시 적재하기', [
        again, f'핀 세척(`{TASK}`)에 걸 다른 문서의 조건(시간 · 승인 · 준비)을 찾아, 그 문서의 적용 범위 절과 이 작업을 말하는 사내 문장을 원문으로 열어 이을지 정합니다. ' + DECIDE_MINE,
        '정한 대로 `app/features/other_doc_conditions.csv`에 잇는다 · 잇지 않는다와 근거를, 고른 것을 `decisions.csv`에 적습니다. 보고도 잇지 않기로 한 문장은 「아니오」 행으로 남깁니다.'],
        prompt='내가 원문을 열어 정한 대로 다른 문서의 조건마다 잇는다 · 잇지 않는다와 근거를 app/features/other_doc_conditions.csv에 적어 줘. 잇지 않기로 한 문장도 「아니오」 행으로 남기고, 내가 정하지 않은 조건은 먼저 물어봐.',
        cmd='python run.py other', check=f'고른 행과 근거 원문 줄, 그리고 같은 적재를 한 번 더 실행한 전후가 보입니다. 늘거나 사라진 것이 없어야 합니다. `{rec}` 「적재 수」에 두 줄을 적습니다. 늘었으면 늘어난 종류를 보고 ID 꼴을 고칩니다.', ai=True)
    reopen_query = ('python run.py card', '다시 연 폴더에서 카드가 앞과 같은지 봅니다.') if practical else ('python run.py query', '다시 연 폴더에서 조회 결과가 앞과 같은지 봅니다.')
    save_step = section('내보내고 저장해 다시 열기', [
        '내보내기는 지금 랩 DB의 그래프와 추가 자료가 필요한 질문을 한 파일로 남깁니다. 짚은 문제를 고친 뒤 아래 차례로 실행합니다: 내보내기 → 구조 검사 → **파일 → 모두 저장** → 폴더를 닫았다 다시 열기 → 랩 DB 다시 켜기 → 결과 다시 보기.',
        f'`{rec}` 끝에 기준일 · 저장 시점 · 확인하지 못한 점을 적고 실습 폴더 전체를 USB나 개인 클라우드에 보관합니다.'],
        prompt='구조 검사 출력이 가리키는 파일 · 노드 · 관계를 찾아 어느 정할 자리에서 생긴 문제인지 설명해 줘. 원자료와 검사 기준은 바꾸지 마. 내가 원인을 확인하면 필요한 부분만 고쳐 줘.',
        extra=SG.commands([('python run.py export', '내보내기의 노드 · 관계 · 추가 자료가 필요한 질문 수가 랩 DB 수와 같고, 이어지는 구조 검사 출력이 보입니다.'),
                           ('python run.py check', '「구조 검사 통과」가 보이면 저장해 닫습니다. 「구조 확인 필요」 아래 줄마다 남은 일을 채운 뒤 다시 실행합니다.')])
        + '<p>' + F.inline('폴더를 다시 연 뒤 랩 DB를 다시 켭니다.') + '</p>',
        cmd='python run.py db', check='같은 폴더의 랩 DB가 켜집니다. ' + docker_off,
        when_new=[('python run.py load', '정할 자리대로 다시 적재합니다.'), ('python run.py other', '다른 문서의 조건까지 다시 적재합니다.')],
        followup=[reopen_query])
    codex_step = section('Codex와 기존 ID 찾기' if not practical else 'Codex와 핀 세척 근거와 기존 ID 찾기', [
        f'문서 속 대상은 모델의 ID와 다른 이름 · 번호로 적혀 있을 수 있어, 어느 기존 ID를 가리키는지 먼저 봅니다. Codex 확장 아이콘을 눌러 채팅을 열고 로그인합니다. 계정이 없거나 막히면 클래스룸에서 따로 받는 `{name}-completed.zip`을 실행해 볼 수 있습니다.',
        '파일을 바꾸지 말고, 승인 후보가 가리키는 대상(설비 · 구성 요소 · 부품 · SOP · 단계 · 규칙)이 설비 모델 · SOP 구조 · 조건표의 어느 ID인지 물어봅니다'
        + (' 핀 세척의 준비 · 금지 · 완료가 검토 결과와 `data/reviews/selected_task.json`의 어느 줄에 있는지, 다른 문서가 이 작업에 거는 조건이 있는지도 함께 묻습니다.' if practical else '.')
        + ' 짚은 ID와 줄은 `data/model/graph.json` · `data/sop.json` · 원문에서 직접 엽니다.'],
        check='후보 대상과 기존 ID의 짝 몇 개를 말할 수 있으면 이어 갑니다. 짚은 ID나 줄이 파일에 없으면 근거로 쓰지 않습니다.', ai=True)
    if practical:
        return [section('폴더 열고 랩 DB 준비하기', opening(key, event, facts, data_note + ' ' + docker,
                        '이 카드는 보전 야간조가 핀 세척 전에 준비 · 금지 · 완료를 원문으로 되짚고, 설비보전팀장이 승인할 때 씁니다.', first=False) + [mine],
                        cmd='python run.py db', check=f'「랩 DB 준비 완료」와 127.0.0.1 주소, 검토 결과마다 승인 · 보류 · 제외 수와 기존 ID 수가 보입니다. 노드 · 관계 수를 `{rec}` 「적재 수」 첫 줄에 적습니다. {docker_off} ' + OPEN_RESULT),
                codex_step,
                section('기대 카드 먼저 적기', [
                    '조회 결과를 본 뒤에 기대를 적으면 빠진 연결이 기대에 맞춰 사라집니다. `app/features/expected.csv`에 카드 항목(준비 조건 · 금지 · 제한 · 작업 순서 · 완료 기준 · 작업 직전 확인할 현재값 · 승인 · 추가 자료가 필요한 질문)마다 기대를 원문 · 검토 결과의 파일:줄로 적고, '
                    f'`{rec}`에 목표 · 쓰는 사람 · 기대 칸을 쓴 시각을 적습니다. 절차 밖 절 · 다른 절차 · 다른 문서에 있는 작업 조건, 설비 별칭 · 제조사 품번으로 적힌 대상도 찾아 둡니다. ' + encoding, SAVE_NOTE, IMPL_NOTE],
                    prompt='02에서 함께 찾은 줄로 카드 항목마다 기대와 근거(파일:줄)를 app/features/expected.csv에 적어 줘. 항목 이름은 파일 첫 줄의 칸 뜻대로 쓰고, 근거를 못 찾은 항목은 먼저 물어봐.',
                    cmd='python run.py expected', check='내 기대와 근거마다 첫 원문 줄이 보이고, 그 줄이 내가 적은 내용입니다.', ai=True),
                shape_step, load_step, other_step,
                section('작업 확인 카드 만들기', [
                    '카드의 기준값은 문서에서 오고, 작업 직전의 현재값은 시계열 · CMMS · ERP · MES 같은 원천 시스템에서 옵니다. 카드에는 기준값과 그 값을 읽을 원천을 나란히 두되 섞지 않아야 작업자가 무엇을 지금 다시 봐야 하는지 압니다.',
                    '`app/features/query_values.csv`에 카드를 만들 작업, 같은 방법을 대 볼 다른 작업(사건 경보의 검토 의견이 먼저 검토할 후보로 둔 작업 — `data/action_review.json`의 `review`), '
                    '그래프에 없어야 할 보류 후보 둘(검토 결과 파일#후보 id), 제공되지 않은 작업 · 절의 값을 적습니다. `current_value_sources.csv`에는 작업 직전 확인할 현재값과 읽을 원천을 적습니다(값 자체는 적지 않습니다).'],
                    prompt='내가 정한 작업 · 다른 작업 · 보류 후보 · 제공되지 않은 작업과 절로 query_values.csv를, 작업 직전에 다시 볼 현재값과 원천으로 current_value_sources.csv를 채워 줘. 현재값이나 승인을 추정으로 채우지 말고, 내가 정하지 않은 값은 먼저 물어봐.',
                    cmd='python run.py card', check=f'`output/work_card_{TASK}.md` 카드가 보이고 준비 · 금지 · 순서 · 완료 항목마다 원문 인용이 있습니다. 현재값 칸에는 원천 이름만 있고, 승인은 원문의 역할입니다. 기대와 같음 · 다름을 기록에 적습니다. '
                    '「그래프에 이 작업의 지식이 아직 없습니다」가 나오면 `python run.py load` → `python run.py other`를 먼저 실행합니다.', ai=True),
                section('다른 작업과 답할 수 있는 범위 확인하기', [
                    '같은 방법이 다른 작업에도 통하고, 없는 것에 「결과 없음」을 돌려줘야 쓸 수 있는 기능입니다. 공급 조건은 설비 모델의 공급사(Supplier)와 공급 관계(SUPPLIES)에서 오고, 그날의 재고와 승인은 그래프 밖입니다.',
                    f'결과를 보고 `{rec}` 「다른 작업 · 제공되지 않은 것」과 「답할 수 있는 것과 없는 것」(그래프로 답함 · 현재값 필요 · 승인 필요 · 공급 정보 · 원문에 없음)에 근거와 함께 적습니다.'],
                    prompt='결과 화면의 다른 작업 카드와 「찾은 수 0」 조회가 data/action_review.json과 문서 목록의 어느 값에서 왔는지 짚어 줘. 내가 질문마다 분류를 정하면 build_record.md의 두 표에 그 행을 적어 줘. 다른 파일은 바꾸지 마.',
                    cmd='python run.py scope', check='두 번째 카드, 「찾은 수 0」 조회, 추가 자료가 필요한 질문 수가 보이고, 기록 두 표에 근거가 있습니다.', ai=True),
                save_step]
    return [section('폴더 열고 검토 결과 확인하기', opening(key, event, facts, data_note,
                    '이 답은 설비보전팀장이 핀 세척과 냉각 조치의 조건 · 근거를 그래프로 찾을 때 씁니다.') + [mine],
                cmd='python run.py', check='검토 결과마다 승인 · 보류 · 제외 수와 조건 근거 견주기, 기존 ID 수, 승인 후보 찾아보기 표가 보입니다. ' + OPEN_RESULT),
            codex_step,
            section('질문과 기대 답 먼저 적기', [
                '질문이 모델의 범위를 정합니다. 조회 결과를 본 뒤에 기대를 적으면 빠진 연결이 기대에 맞춰 사라지므로, 원문과 검토 결과로 먼저 적어 둡니다.',
                '물을 질문은 다섯입니다. ① HYD-02 냉각 성능 상실에서 쓸 수 있는 조치마다 수행 단계 · 준비 · 금지 · 완료 기준 · 승인과 근거 문서 · 판본 · 절 · 인용은? ② 판정에 쓴 규칙마다 근거 원문이 있고 조건과 무엇이 다른가? '
                '③ 핀 세척 전에 확인할 현재값은 무엇이고 어디서 읽는가? ④ 다른 문서를 더 반영하면 그 문서의 작업은 어느 대상에 걸리고 앞의 연결은 그대로인가? ⑤ 제공되지 않은 작업이나 절을 물으면 그래프는 무엇을 돌려주는가?',
                f'`app/features/expected.csv`에 질문 1 · 2의 기대 답을 문서 · 절로, 질문 3은 읽을 원천 이름으로 적고(근거는 파일:줄), `{rec}`에 목표 · 쓰는 사람 · 기대 칸을 쓴 시각을 적습니다. '
                '같은 번호를 쓰는 다른 문서의 절, 판본이 다른 같은 문서, 근거 원문이 있는 규칙 · 범위가 다른 원문 · 원문이 없는 규칙, 설비 별칭 · 제조사 품번으로 적힌 대상도 찾아 둡니다. ' + encoding, SAVE_NOTE, IMPL_NOTE],
                prompt='02에서 함께 찾은 줄로 질문 1 · 2의 기대 답을 문서 · 절로, 질문 3은 읽을 원천 이름으로 app/features/expected.csv에 근거(파일:줄)와 함께 적어 줘. 근거를 못 찾은 질문은 먼저 물어봐.',
                cmd='python run.py expected', check='내 기대와 근거마다 첫 원문 줄이 보이고, 그 줄이 내가 적은 내용입니다.', ai=True),
            section('랩 DB 준비하고 설비 모델 적재하기', [docker, '먼저 수를 적어 두어야 뒤에서 늘어난 수가 이번에 넣은 것임을 셀 수 있습니다.'],
                    cmd='python run.py db', check=f'「랩 DB 준비 완료」와 127.0.0.1 주소가 나오고, 설비 모델과 조치 기준을 올린 뒤의 종류별 수가 보입니다. 노드 · 관계 수를 `{rec}` 「적재 수」 첫 줄에 적습니다. {docker_off}'),
            shape_step, load_step, other_step,
            section('질문 1~3 조회와 보류 확인하기', [
                '조회가 성공했다고 답이 맞는 것은 아니므로, 결과 항목을 원문 인용으로 돌아가 견줍니다. 보류는 버린 것이 아니라 근거가 더 필요하다는 기록이라 그래프에 없어야 합니다.',
                f'`app/features/query_values.csv`에 질문 1 · 3에 넣을 설비 · 작업과 확인할 보류 후보 둘(검토 결과 파일#후보 id)을 적고 실행합니다. 기대와 같음 · 다름과 까닭을 `{rec}` 「질문별 기대와 실제」에 적습니다. '
                'Neo4j Browser로 모양을 볼 때는 `output/query.cypher`에서 그 질문의 「// Browser:」 줄을 따릅니다.'],
                prompt='내가 정한 설비 · 작업 · 보류 후보로 app/features/query_values.csv를 채워 줘. 결과가 기대와 다른 질문이 있으면 원인이 연결 규칙과 그래프 모양 가운데 어디인지 설명해 주고, 그 파일은 내가 원인을 확인한 뒤에 고치게 해 줘.',
                cmd='python run.py query', check='질문 1 · 2 · 3 결과와 보류 조회(찾은 수 0)가 보이고, `output/query.cypher`가 생깁니다. 결과 항목 몇 개를 원문 인용으로 직접 엽니다.', ai=True),
            section('다른 문서 추가 반영하기', [
                '여러 문서가 같은 대상을 말할 때, 뒤에 넣은 문서가 앞의 연결을 덮거나 같은 번호의 다른 절을 같은 대상으로 합치면 앞에서 맞던 답이 바뀝니다. 더한 뒤 기존 노드 · 관계를 견주어야 반영 범위를 압니다.',
                f'`app/features/link_rules.csv`에 제조사 지침과 예비품 기준의 행을, 필요하면 `aliases.csv`에 설비 모델명 · 제조사 품번을 더하고 실행합니다. 추가 전후 비교와 질문 1 · 4를 보고 `{rec}` 「다른 문서 추가 뒤 기존 연결」에 적습니다.'],
                prompt='내가 원문 줄로 확인한 대로 제조사 지침과 예비품 기준의 잇는 행을 link_rules.csv에, 필요한 별칭을 aliases.csv에 더해 줘. 기존 행은 바꾸지 말고, 어느 기존 ID인지 정하지 않은 이름은 먼저 물어봐.',
                cmd='python run.py more', check='늘어난 수와 「속성이 바뀐 기존 노드 0 · 사라진 관계 0」(또는 그 목록)이 보이고, 질문 1에서 늘어난 행을 원문으로 설명할 수 있습니다.', ai=True),
            section('답할 수 있는 범위 나누기', [
                '문서의 판단 기준은 그래프에 있지만, 작업 직전의 센서 값 · 작업지시 상태 · 재고는 시계열 · CMMS · ERP · MES 같은 원천 시스템에서 읽어야 합니다. 그래프가 무엇에 답하고 무엇에 답하지 못하는지 밝혀 두어야 이 지식을 쓰는 쪽이 읽을 곳을 압니다.',
                f'`app/features/current_value_sources.csv`에 핀 세척 전에 확인할 현재값과 읽을 원천을 적고(값 자체는 적지 않습니다) 실행합니다. 질문마다 그래프로 답하는지 · 현재값 필요 · 추가 자료 필요 · 원문에 없음인지를 `{rec}` 「답할 수 있는 것과 없는 것」에 적습니다.'],
                prompt='내가 정한 현재값과 원천으로 app/features/current_value_sources.csv를 채워 줘. 값 자체나 원천을 추정으로 채우지 말고, 근거 줄을 정하지 않은 행은 먼저 물어봐.',
                cmd='python run.py scope', check='현재값 · 원천 표와 질문 3 · 5, 추가 자료가 필요한 질문 수가 보이고, 기록 표에 질문마다 분류와 근거가 있습니다.', ai=True),
            save_step]


def guide(key, L, event, facts):
    steps = (graph_guide if LABS[key]['kind'] == 'graph' else extract_guide)(key, event, facts)
    lead = (PURPOSE[key] + ' 과정은 온톨로지 → 에이전트 → 프로세스 순서로 올라가며, 이 실습은 온톨로지 단계의 문서 지식을 맡습니다. '
            '단계마다 지금 할 일과 확인할 결과를 보고 진행하고, 막히면 「정답 보기」의 요청을 앞 단계에서 확인한 내용에 이어 보냅니다.')
    return steps, SG.render(L['title'], lead, steps)


GUIDE_LEAKS = BD.GUIDE_WORDS + BD.OPS_WORDS


def guide_checks(key, html_text, steps, commands):
    """가이드 단계 이름 = 생성기 정의, 구현 · 판단 단계(ai)에 정답 토글, 명령 = 정의된 기능, 토글 안팎 글에 결정 지점의 답 · 제작 말 0."""
    bad = []
    heads = [_html.unescape(h) for h in re.findall(r'<section id="s\d+"><h2>\d\d ([^<]+)</h2>', html_text)]
    if heads != [s['name'] for s in steps]:
        bad.append(f'가이드 절 {heads} ≠ 생성기 단계 {[s["name"] for s in steps]}')
    for i, s in enumerate(steps, 1):
        sec = re.search(rf'<section id="s{i}">.*?</section>', html_text, re.S).group()
        if s['ai'] and '<details class="answer">' not in sec and not s['name'].startswith('Codex와'):
            bad.append(f'{i}단계 「{s["name"]}」: AI와 구현 · 판단하는 단계인데 정답 토글 없음')
        for cmd in re.findall(r'python run\.py ?([a-z]*)', _html.unescape(re.sub(r'<[^>]+>', ' ', sec))):
            if (cmd or 'sources') not in commands:
                bad.append(f'{i}단계 「{s["name"]}」: 정의되지 않은 기능 python run.py {cmd}')
    leaks = (BD.GLEAKS if LABS[key]['kind'] == 'graph' else BD.LEAKS)
    body, whole = BD.guide_text(html_text), BD.guide_text(html_text, answers=True)
    for word in [w for w in leaks if w != '(권장)'] + GUIDE_LEAKS:
        for where, text in (('토글 밖', body), ('토글 안', whole)):
            if word in text:
                bad.append(f'가이드 {where} 글에 「{word}」')
    return bad


def text_checks(key, folder):
    """학생 문장(README · AGENTS · 계약 · 빈 틀 · 제공 코드 · 검사기)에 결정 지점의 답 · 운영 말이 없다(옛 생성기의 같은 낱말 목록)."""
    leaks = (BD.GLEAKS if LABS[key]['kind'] == 'graph' else BD.LEAKS) + BD.OPS_WORDS
    bad = []
    for p in sorted(folder.rglob('*')):
        rel = p.relative_to(folder).as_posix()
        if not p.is_file() or rel.startswith(('data/documents/', 'data/model/', 'data/reviews/')) or rel.endswith(('.json', '.csv')) and rel.startswith('data/'):
            continue
        text = p.read_text(encoding='utf-8-sig')
        # 공용 틀(project_layout의 AI 작업 경계 · 고른 것 빈 틀)의 「갈래」는 선택지라는 뜻이라 이 랩의 답이 아니다 — 이 랩이 쓴 글만 본다
        text = text.replace(AI_RULES, '').replace(convert(F.CHOSEN_TEMPLATE), '')
        for word in leaks:
            if word in text and not (rel.startswith('app/utils/') and word in ('reference', '갈래')):
                bad.append(f'{rel}: 「{word}」')
    if any((folder / 'output').glob('*')) if (folder / 'output').exists() else False:
        bad.append('시작 폴더에 output/이 있음')
    return bad


def build(key, legacy_folder, L, parent, event):
    folder = parent / LABS[key]['name']
    commands = build_project(key, legacy_folder, L, folder)
    steps, text = guide(key, L, event, event_facts(folder, key))
    cost = F.guide_cost(text, ai_turns=sum(1 for s in steps if s['ai']))
    legacy_cost = F.guide_cost(F.guide_path(legacy_folder).read_text(encoding='utf-8'))
    target = F.guide_path(folder)
    write(target, text)
    bad = guide_checks(key, text, steps, commands) + text_checks(key, folder)
    if bad:
        raise RuntimeError(f'{folder.name} 설계 조건 검사 실패:\n- ' + '\n- '.join(bad))
    hand = legacy_cost['손_행'] * F.ROW_MIN + legacy_cost['근거_행'] * F.EVIDENCE_MIN
    plan = dict(cost, 손_행_정할자리=legacy_cost['손_행'], 근거_행_정할자리=legacy_cost['근거_행'], 계획_분=round(cost['사람_분'] + hand, 1),
                옛_가이드_사람_분=legacy_cost['사람_분'])
    print(F.cost_line(folder, cost) + f' + 정할 자리 손 행 {legacy_cost["손_행"]} × {F.ROW_MIN} · 근거 행 {legacy_cost["근거_행"]} × {F.EVIDENCE_MIN} = 계획 {plan["계획_분"]}분'
          f' (옛 가이드 {legacy_cost["사람_분"]}분)')
    return folder, steps, plan


def validate(key, folder, L, steps):
    issues = errors({p.relative_to(folder).as_posix(): p.read_bytes() for p in student_files(folder)}, folder.name)
    if issues:
        raise ValueError(issues)
    pack(folder)
    spec = LABS[key]
    item = entry(key, spec['course'], spec['session'], L['title'], VERSION, folder, guide_steps=[s['name'] for s in steps])
    from verify_packages import check_zip, verify_lab
    bad, _ = check_zip(folder.with_suffix('.zip'), folder, need=('.env.example', 'run.py', 'README.md', 'AGENTS.md') if spec['kind'] == 'extract' else ('run.py', 'README.md', 'AGENTS.md'))
    assert not bad, bad
    verify_lab(item)
    return item


# ───────────── 학생용 완성본(시작 ZIP 밖, 모델을 새로 부르지 않음) ─────────────
def run(folder, *args, ok=True, timeout=1800):
    env = dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1')
    r = subprocess.run([sys.executable, *args], cwd=folder, capture_output=True, text=True, encoding='utf-8', errors='replace', env=env, timeout=timeout)
    if ok and r.returncode:
        raise RuntimeError(f'{folder.name}: {" ".join(args)} 종료 코드 {r.returncode}\n{r.stdout[-3000:]}\n{r.stderr[-2000:]}')
    return r


def blocks(folder):
    return json.loads((folder / 'output/result.json').read_text(encoding='utf-8'))['blocks']


def act(folder, action):
    """한 기능을 실행하고, 비어 있음 · 멈춤 · 오류가 없는지 본다."""
    (folder / 'output/result.json').unlink(missing_ok=True)
    r = run(folder, 'run.py', action, '--no-open', ok=False)
    if not (folder / 'output/result.json').is_file():
        raise RuntimeError(f'{folder.name}: python run.py {action} — 결과 화면을 쓰지 못함 rc {r.returncode}\n{r.stdout[-2500:]}\n{r.stderr[-2500:]}')
    got = blocks(folder)
    bad = [b for b in got if b['kind'] == 'error' or (b['kind'] == 'note' and b['text'].startswith('아직 비어 있습니다'))]
    if r.returncode or bad:
        raise RuntimeError(f'{folder.name}: python run.py {action} — rc {r.returncode}\n{r.stdout[-2500:]}')
    return r.stdout


SEED_TRIAL = r'''
import json, shutil, sys
from pathlib import Path
from app.utils import llm_client as L
L.configure(Path.cwd(), project=True)
from app.utils import extract as X
run2 = Path(sys.argv[1])
cfg, prompt = X.settings(), X.prompt_text()
name, line = cfg['시험_조각'].rsplit(':', 1)
row, text, enc, raw = X.by_file()[name]
first, body = next((f, b) for f, b in X.split_chunks(text, cfg['단위'], cfg['글자_상한']) if X.chunk_range(f, b)[0] <= int(line) <= X.chunk_range(f, b)[1])
digest = L.request_hash(L.body_of(L.as_messages(X.build_request(prompt, row, first, body)), 'coding'))
second = Path('output/model_responses') / f'{digest}-2.json'
shutil.copy2(run2 / f'{digest}.json', second)
answers = []
for p in (Path('output/model_responses') / f'{digest}.json', second):
    rec = dict(json.loads(p.read_text(encoding='utf-8')), file=p.as_posix())
    cands, unl, warns, _ = X.to_candidates(row, text, [rec])
    answers.append({'record': rec['file'], 'finish_reason': rec.get('finish_reason'), 'candidates': cands, 'unlocated': unl, 'warnings': warns})
a, b = X.chunk_range(first, body)
out = {'stamp': X.stamp(cfg, prompt) + f' · 시험 조각 {name} {a}~{b}줄', 'source_file': name, 'chunk': [a, b], 'request_hash': digest, 'answers': answers,
       'note': '다시 보낸 답은 같은 요청을 다른 폴더(강사 실행 둘째 판)에서 보낸 기록이다'}
Path('output/trial_chunk.json').write_text(X.dump(out), encoding='utf-8', newline='\n')
print(digest)
'''


def seed_extract(folder):
    """강사 추출 실행 run1의 응답 기록 · 폴더 표지와 모델 이름(.env) — 정할 자리가 같은 판이면 제공 코드가 다시 보내지 않고 이 기록을 쓴다(replay.seed_extract와 같음)."""
    run1 = REF / '강사_추출/run1/결과'
    shutil.copytree(run1 / '응답_기록', folder / 'output/model_responses', dirs_exist_ok=True)
    shutil.copy2(run1 / '폴더_표지.txt', folder / 'output/.folder_mark')
    write(folder / '.env', 'OPENAI_BASE_URL=\nLLM_API_KEY=\nLLM_MODEL=coding\n')


def seed_trial(folder):
    (folder / '_seed_trial.py').write_text(SEED_TRIAL, encoding='utf-8')
    try:
        return run(folder, '_seed_trial.py', str(REF / '강사_추출/run2/결과/응답_기록')).stdout.strip()
    finally:
        (folder / '_seed_trial.py').unlink()


def put_slots(folder, files):
    """{옛 결과/ 안 이름: 글} → app/features/ 새 이름에 경로만 옮겨 쓴다."""
    for name, text in files.items():
        write(folder / 'app/features' / NAMES.get(name, name), text if name == 'prompt.md' else convert(text))   # 요청 글은 그대로(바꾸면 요청 해시가 달라 고정된 응답 기록을 못 씀)


EXTRACT_ORDER = {False: ['sources', 'expected', 'split', 'trial', 'extract', 'review', 'rules', 'other'], True: ['sources', 'expected', 'trial', 'extract', 'review', 'rules', 'collect']}
GRAPH_ORDER = {False: ['db', 'sources', 'expected', 'plan', 'load', 'other', 'query', 'more', 'scope', 'export'],
               True: ['db', 'expected', 'plan', 'load', 'other', 'card', 'scope', 'export']}


def drop_db(folder):
    state = folder / '.lab_connection.json'
    if state.is_file():
        name = json.loads(state.read_text(encoding='utf-8'))['container']
        subprocess.run(['docker', 'rm', '-f', name], capture_output=True)
        return name


def fill_completed(key, folder, legacy_replay):
    """완성본 폴더 하나 — 옛 구조 정답 재생(replay.py)의 마지막 정할 자리 · 기록을 옮겨 쓰고 기능을 차례로 실행한다. 돌려주는 값: 실행 로그."""
    practical = LABS[key]['course'] == '실전반'
    graph = LABS[key]['kind'] == 'graph'
    slots = GRAPH_SLOTS if graph else EXTRACT_SLOTS
    put_slots(folder, {n: (legacy_replay / '결과' / n).read_text(encoding='utf-8-sig') for n in slots if (legacy_replay / '결과' / n).is_file()})
    logs = {}
    if graph:
        for action in GRAPH_ORDER[practical]:
            logs[action] = act(folder, action)
        logs['check'] = run(folder, '-m', 'app.utils.check', ok=False).stdout
    else:
        seed_extract(folder)
        for action in EXTRACT_ORDER[practical]:
            if action == 'trial':
                logs['seed_trial'] = seed_trial(folder)
            logs[action] = act(folder, action)
        logs['check'] = run(folder, '-m', 'app.utils.check', ok=False).stdout
    return logs


def compare_outputs(key, new, old):
    """새 구조 실행 결과 ↔ 옛 구조 정답 재생 결과(경로만 옮겨) — 같아야 하는 파일 목록과 다른 곳."""
    graph = LABS[key]['kind'] == 'graph'
    pairs = []
    if graph:
        names = ['지식_내보내기.json', 'schema_ext.json', 'load.cypher', '남은_질문.json'] + [p.name for p in (old / '결과').glob('작업확인카드_*.md')]
    else:
        names = [f'검토/{p.name}' for p in sorted((old / '결과/검토').glob('*.json'))] + [f'후보/{p.name}' for p in sorted((old / '결과/후보').glob('*.json'))]
        names += ['선택작업_조건.json'] if (old / '결과/선택작업_조건.json').is_file() else []
    out = []
    for name in names:
        a = model_names(convert((old / '결과' / name).read_text(encoding='utf-8')))
        target = folder_name(name)
        b = (new / target).read_text(encoding='utf-8') if (new / target).is_file() else None
        out.append({'old': f'결과/{name}', 'new': target, 'same': a == b,
                    'same_except_time': b is not None and same_content(a, b)})
    return out


def model_names(text):
    """설비 모델 속성의 출처 표기(2회차 원자료 이름) — data/model은 2회차 새 구조와 같이 P.convert로 옮겼으므로 견줄 때도 그 이름으로."""
    for old, new in sorted(P.NAMES.items(), key=lambda x: -len(x[0])):
        text = text.replace(old, new)
    return text


VOLATILE = re.compile(r'("(?:generated_at|reviewed_at|candidates_sha256)": )"[^"]*"')   # 실행 시각과, 그 시각이 든 후보 파일의 해시


def same_content(a, b):
    """실행 시각 칸을 뺀 내용이 같은가. JSON은 읽어서 견준다(랩 DB가 돌려주는 속성 순서는 실행마다 다를 수 있다)."""
    a, b = VOLATILE.sub(r'\1"…"', plain_reasons(a)), VOLATILE.sub(r'\1"…"', plain_reasons(b))   # 옛 판의 판정 문장은 이 판에서 지웠다
    try:
        return json.loads(a) == json.loads(b)
    except ValueError:
        return a == b


def folder_name(name):
    if name.startswith('검토/'):
        return 'output/reviews/' + convert(name[3:])
    if name.startswith('후보/'):
        return 'output/candidates/' + name[3:]
    return 'output/' + convert(name)


def completed(key, starter, work, legacy_folder):
    """학생용 완성본 ZIP과 실행 기록. 옛 구조 정답 재생을 같은 자리에서 돌려 그 결과와 새 구조 실행 결과를 견준다."""
    sys.path[:0] = [str(REF)]
    import replay as RP
    import completed as CP
    graph = LABS[key]['kind'] == 'graph'
    practical = LABS[key]['course'] == '실전반'
    snaps = []
    res, old = RP.replay(key, work / 'legacy-replay', keep_db=graph, snaps=snaps)
    bad = [(i, n, s) for i, n, s, _ in res if s not in ('채움', '볼 것 없음', '결과 보기')]
    if bad:
        raise RuntimeError(f'{key}: 옛 구조 정답 재생 불일치 {bad}')
    for name in ('lab_cypher', 'doc_graph', 'doc_extract', 'llm_client', 'show_result'):   # 앞 랩 사본에서 읽은 같은 이름 모듈을 쓰지 않게(랩 DB 연결이 폴더마다 다름)
        sys.modules.pop(name, None)
    try:
        record = (CP.card_record if practical else CP.graph_record)(old, snaps) if graph else CP.extract_record(old, practical)
    finally:
        if graph:
            RP.drop_db(old)
    folder = work / 'completed' / starter.name
    shutil.copytree(starter, folder, ignore=shutil.ignore_patterns('__pycache__', 'output'))
    record_name = 'build_record.md' if graph else 'review.md'
    try:
        logs = fill_completed(key, folder, old)
        same = compare_outputs(key, folder, old)
        write(folder / 'app/features' / record_name, convert(record))
        logs['check_after_record'] = run(folder, '-m', 'app.utils.check').stdout
        if graph:
            logs['export_after_record'] = act(folder, 'export')
    finally:
        container = drop_db(folder) if graph else None
    for rel in ('.env', 'output/.folder_mark', '.lab_connection.json', 'output/.previous.json'):
        (folder / rel).unlink(missing_ok=True)
    title = L_title(key)
    write_metadata(folder, title + ' · 완성본',
                   'AI 계정이 없거나 구현 중 막혔을 때 실행해 보는 묶음입니다. 정할 자리는 한 가지 판단으로 채웠고, 선택과 근거는 app/features/decisions.csv에 있습니다.'
                   + (' Docker Desktop을 켠 뒤 실행합니다.' if graph else ' 응답 기록은 강의에서 미리 받아 둔 수업 모델의 답이라, 정할 자리를 바꾸지 않으면 다시 보내지 않습니다.'),
                   command='\n'.join('python run.py ' + a for a in README_ORDER[(graph, practical)]), extra_rules=rules_for(key))
    archive = work / (starter.name + '-completed.zip')
    write_zip(archive, [(starter.name + '/' + p.relative_to(folder).as_posix(), p.read_bytes()) for p in student_files(folder)])
    fresh = fresh_completed(key, archive, work / 'completed-fresh')
    return archive, {'legacy_replay': [(i, n, s) for i, n, s, _ in res], 'same_as_legacy': same, 'logs': logs, 'fresh': fresh, 'container_removed': container}


README_ORDER = {(True, False): ['db', 'load', 'other', 'query'], (True, True): ['db', 'load', 'other', 'card', 'scope'],
                (False, False): ['extract', 'check'], (False, True): ['extract', 'check']}   # 완성본 README의 실행 순서 — 새 폴더 시험이 이 순서 그대로 돈다


def L_title(key):
    return (BD.GTITLES if LABS[key]['kind'] == 'graph' else BD.TITLES)[key]


def fresh_completed(key, archive, work):
    """새 폴더에 풀어 키 없이 다시 실행 → 결과가 같고 검사 통과, 응답 기록 수가 바뀌지 않는다(다시 보내지 않음)."""
    graph = LABS[key]['kind'] == 'graph'
    practical = LABS[key]['course'] == '실전반'
    if work.exists():
        shutil.rmtree(work)
    with zipfile.ZipFile(archive) as z:
        z.extractall(work)
    folder = work / LABS[key]['name']
    out = {}
    try:
        if graph:
            before = (folder / 'output/knowledge_export.json').read_text(encoding='utf-8')
            for action in README_ORDER[(True, practical)] + ['export']:
                act(folder, action)
            out['readme_order'] = README_ORDER[(True, practical)]
            out['export_same'] = (folder / 'output/knowledge_export.json').read_text(encoding='utf-8') == before
        else:
            n = len(list((folder / 'output/model_responses').glob('*.json')))
            before = {p.name: p.read_bytes() for p in (folder / 'output/reviews').glob('*.json')}
            for action in ('extract', 'review', 'rules') + (('collect',) if practical else ('other',)):
                act(folder, action)
            out['responses_same_count'] = len(list((folder / 'output/model_responses').glob('*.json'))) == n
            out['reviews_same'] = {p.name: p.read_bytes() for p in (folder / 'output/reviews').glob('*.json')} == before
        c = run(folder, '-m', 'app.utils.check', ok=False)
        out['check_rc'] = c.returncode
        out['check_tail'] = c.stdout.strip().splitlines()[-3:]
    finally:
        if graph:
            out['container_removed'] = drop_db(folder)
    if out.get('check_rc') or not all(v for k, v in out.items() if k.endswith('_same') or k == 'responses_same_count'):
        raise RuntimeError(f'{key}: 완성본 새 폴더 실행 확인 실패 {out}')
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('labs', nargs='+', choices=sorted(LABS))
    dest = parser.add_mutually_exclusive_group(required=True)
    dest.add_argument('--dest', type=Path, help='작업/ 아래 새 검증용 부모 폴더 — 목록은 등록하지 않음')
    dest.add_argument('--apply', action='store_true', help='검증 사본을 만든 뒤 지정한 랩만 정본에 바꿔 끼우고 목록에 등록(메인)')
    parser.add_argument('--completed', action='store_true', help='학생용 완성본도 실제 실행해 생성')
    parser.add_argument('--report', type=Path, help='생성 · 검사 기록 JSON을 쓸 곳')
    args = parser.parse_args()
    keys = set(args.labs) | {LABS[k]['extract'] for k in args.labs if LABS[k]['kind'] == 'graph'}
    WORK.mkdir(parents=True, exist_ok=True)
    if args.dest:
        parent = args.dest.resolve()
        if not parent.is_relative_to((ROOT / '작업').resolve()) or parent.exists():
            parser.error('--dest는 저장소 작업/ 아래 아직 없는 새 폴더입니다.')
    report = {'version': VERSION, 'labs': {}}
    with tempfile.TemporaryDirectory(dir=WORK, prefix='build-') as temp:
        work = Path(temp).resolve()
        with legacy(work) as files:
            event = incident(files)
            made = build_legacy(keys)
            for key in sorted(args.labs):
                old, L = made[key]
                parent = (args.dest.resolve() if args.dest else work / 'publish') / LABS[key]['course']
                folder, steps, plan = build(key, old, L, parent, event)
                item = validate(key, folder, L, steps)
                info = {'folder': folder.as_posix(), 'project': folder.name, 'name_reason': LABS[key]['why'], 'package': item, 'steps': [
                    {'name': s['name'], 'commands': re.findall(r'python run\.py(?: [a-z]+)?', _html.unescape(re.sub(r'<[^>]+>', ' ', s['body']))),
                     'answer_toggle': '<details class="answer">' in s['body'], 'ai': s['ai']} for s in steps], 'cost': plan, 'legacy_folder': old.as_posix()}
                if args.completed:
                    archive, info['completed'] = completed(key, folder, work / ('done-' + key), old)
                    target = (parent if args.dest else COMPLETED_DIR[LABS[key]['course']]) / archive.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(archive, target)
                    info['completed_zip'] = {'path': target.as_posix(), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}
                if args.apply:
                    final = DEST[LABS[key]['course']] / folder.name
                    if final.exists():
                        shutil.rmtree(final)
                    shutil.copytree(folder, final)
                    for suffix in ('_guide.html', '.zip'):
                        shutil.copyfile(folder.parent / (folder.name + suffix), final.parent / (final.name + suffix))
                    register([validate(key, final, L, steps)])
                    info['applied'] = final.as_posix()
                report['labs'][key] = info
                print(f'{key}: {folder}')
            if args.dest:
                (args.dest.resolve() / 'legacy').mkdir(parents=True, exist_ok=True)
                for key, (old, _) in made.items():   # 옛 구조 대조용 사본(같은 입력 함수로 만든 판) — 해시 대조 근거
                    shutil.copytree(old, args.dest.resolve() / 'legacy' / key / old.name)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
