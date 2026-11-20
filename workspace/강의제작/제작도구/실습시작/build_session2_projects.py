"""통합02의 지정 프로젝트 하나만 생성한다. 다른 과정·회차·강사 참조를 재생성하지 않는다.

python build_session2_projects.py ontology --dest 작업/검사/...
python build_session2_projects.py ontology --apply [--completed]
"""
from pathlib import Path
import argparse
from contextlib import nullcontext
import json
import shutil
import subprocess
import sys
import tempfile

import build_labs as B
import data_session2 as D
import lab_frame as F
from lab_package import ROOT, pack, entry, register, student_files, write_zip
from project_layout import write_metadata, errors, DB_RULE
import session2_project as P
import session2_project_guides as G
import session2_graph_project as GP

DEST = ROOT / 'workspace/강의제작/산출물/통합반/실습/02회차/랩'
# 그래프 랩 v33-lab(2026-11-18): 장난감 시험 two_turn에서 AI가 「다 해 줘」에 기능 파일 둘을 한 번에 고치고 update.cypher에 불용 설비 처리(정할 지점)를 학생 선택 없이 써 넣어, 랩별 경계 두 줄을 더함(GRAPH_RULE). 설계 랩은 v32-lab 그대로다.
# v34-lab(2026-11-18): 학생 역 리허설(판정/리허설_i2v32_ontology.md · 리허설_i2v33_graph.md)의 막힐 자리 — 기대 답 틀의 칸 뜻(기준 단위 · 질문 3 항목), 가이드 문장 여덟 곳, 칸 수가 다른 CSV 줄을 파일:줄로 짚고 멈춤.
VERSIONS = {'ontology-lab': 'v50-lab', 'graph-lab': 'v50-lab'}
# v50-lab(2026-11-20, 사용자 「적대적 검토를 통해서 1번 더 봐봐」): 적대 검토 둘(판정/검토_가이드_ontology_v49.json · 검토_가이드_graph_v49.json)의 지적 고침 — 설계 06 예가 원자료와 거꾸로였던 것, 식별자 · 카디널리티 풀이를 이론 정의로, MATCH를 이론 53 · 55장대로, 그래프 11 기준 지도 비교를 화면에 보이는 줄로, 없는 품번의 답 꼴을 04에서, 10 개수를 종류마다, 결정 표 네 칸, 결정 단계 정답 보기에 갈래 묻기 부탁, 승인 · 백틱 줄을 차례 목록 밖으로, 겹친 말 · 이름 섞임 정리.
# v49-lab(2026-11-20, 사용자 「목표 상황 말고 뭔가 이유라든지 지금 뭘 해야 되는지를 짧게 핵심만 … 두 줄 정도까지는 괜찮을 것 같은데」): 목표 칸을 「무엇을 하는지 + 왜 하는지」 두 문장까지로, 상황 칸에 있던 같은 까닭은 목표로 옮김.
# v48-lab(2026-11-20, 사용자 「말을 좀 더 쉽게 표현해보고 … 말을 좀 유먼을 해서 좀 다듬어줄 수 없나요??」): 목표 · 상황 · 뭐부터 · 확인의 모든 줄을 사람이 말하듯 쉬운 문장으로 윤문(칸과 차례는 그대로).
# v47-lab(2026-11-20, 사용자 「지금도 어려운데 그그냥 각 파일별로 어떠파일인지 설명 … 지금 목표강 ㅣ렇고 이런상황이다 뭐부터해야할까 라면서..」): 폴더 열기 단계에서 폴더 · 파일마다 무엇인지 한 줄씩(AGENTS.md는 「AI가 지킬 공통 규칙」 — 코딩랩 K-6), 단계마다 처음 나오는 파일은 상황 칸에서 한 마디로, 힌트 칸을 「뭐부터 해야 할까?」 차례 목록으로.
# v46-lab(2026-11-20, 사용자 「쉽게 가야한다.. 알지? 가이드 좀 어려운것가틍ㄴ데」): 힌트에서 코드 수준 이름(볼_열 · SET · $rows · $ 자리 · 돌려줄 열 · other_codes · note · 판단 함수)을 빼고 쉬운 말과 이론 이름(식별자 · 관계 방향 · 카디널리티 · MERGE · MATCH)만 — 코드 이름은 정답 보기에만.
# v45-lab(2026-11-20, 사용자 「계정이없으면.. 이런말이 왜있음..? 가정은 하지마」 · 「가이드에서 복사하라는말 x 알아서 가이드에서 제공할거임」): 계정이 없는 경우의 안내와 「복사해 붙여 넣는다」를 뺌.
# v44-lab(2026-11-20, 사용자 「지금 현재 목표 이렇고 상황 이렇고 힌트 이렇게 이런 거 이런 걸 해야 되겠다 … 그냥 하나의 문맥으로 탕 떄려넣지말고」 · 「결과 화면에 띄워」): 가이드 단계를 목표 · 상황 · 힌트 칸(session2_project_guides.plan)으로, 그래프 랩 비교 기능이 내 그래프 아래에 기준 지도 표를 띄움(제공 입력 data/reference_map.json — build_labs.portal_reference, 가이드의 기준 지도 표는 뺌).
# v43-lab(2026-11-20, 사용자 「(손으로 치면 오타가 납니다). 이런ㄱ말 codex가 가ㅣ드 정답까지 읽는다 는 등 다 x 넣지마」): 괄호 속 까닭(오타 · 바깥 폴더 · Docker · 재부팅)을 뺌.
# v42-lab(2026-11-20, 사용자 「작업지시 같은 말을 빼라고 그냥 딱 행위 설명만 있어야 있어라고 왜 자꾸 막 이상 쓸데없는 말을 다 더워 군더더기 다 빼고」): 단계는 할 행동 한두 문장 → 힌트(물음 하나와 단어 목록) → 명령 → 확인 한 줄만. 「지금 · 할 일 · 요령」 꼬리표, 요령의 까닭 문장(TIP_* — 까닭은 영상과 현장이 푼다), 힌트 속 작업 지시 문구를 뺌.
# v41-lab(2026-11-20, 사용자 「가이드는 이정표처ㅓㅁ 지금 이런 상황이고 이러 ㅇ리렇다 어떻게햐앟ㄹ가?」 · 「지금 이런이런거가지 알았다 그러면 ~~ 일떄에 어떻게행할까 -- OO -- OO … 정답을 단어형태로 알려주는건 좋은데 프롬포트 자체를 주면안됨」): 단계를 「지금(앞 단계까지 안 것과 상황) → 힌트(그러면 무엇을 물어보고 알아야 할까 + 단어 · 짧은 구 목록) → 요령 → 명령 → 확인」으로, 파악 단계에도 정답 보기(완성 부탁 글은 정답 보기에만).
# v40-lab(2026-11-20, 사용자 「코덱스 채팅에 붙여놓는 그 자체를 그냥 통으로 제공하는 이유가 뭐야 … 글이 너무 많다니까」 · 「현장에서 설명 및 영상에서 설명하는데 왜 가이드에도 설명을 풀로하나요 핵시만 있으면됨 여떻게해야하나 왜? (핵심만)」): 단계를 「왜 / 할 일 / 확인」으로, 본문의 Codex 붙여 넣기 블록을 빼고 부탁은 학생이 짠다(완성 부탁 글은 정답 보기에만 — 가이드 P-3 · P-4 · P-5).
# v39-lab(2026-11-20): v38 적대 검토 두 건(fable · 추론 중간 — 판정/검토_통합2_ontology_v38.json · graph_v38.json) 고침: 받기 문단에 안쪽 폴더를 열라고, 역량 질문은 Codex에 붙여 넣는 글 블록(F.block ask_ai)으로, 그래프 랩 정할 지점을 한 단계로 떼고 결정 요청 틀(decide_request), 볼_열 · 확인 문장 되살림, 명령마다 하는 일 한 구절과 Codex가 채운 파일을 열어 보는 자리, 같은 화면 · 물음 되풀이 뺌, 자기 모델 복사는 접힌 안내의 터미널 명령(학생 입력은 터미널과 Codex뿐).
# v38-lab(2026-11-20, 사용자 「가이드에 글이 너무 많은데..? 가이드의 원칙 모름?」): 가이드 P-5대로 단계 글을 핵심 설명 한두 줄 · Codex에게 부탁할 것 · 명령 블록 · 확인할 결과 화면으로 줄이고, 결과가 학생마다 같지 않아도 된다는 것을 첫 단계에 밝힘. 랩 폴더 · AGENTS.md는 v37과 같다.
# v37-lab(2026-11-20): v36 독립 검토 두 건(작업 폴더 판정/검토_통합2_ontology_v36.json · 검토_통합2_graph_v36.json) 고침 — Codex의 첫 파일 쓰기 단계로 승인 창 안내를 옮김,
#   역량 질문을 Codex에게 붙여 넣게 하고 정답 토글에 질문 문장을, 요령 「묻게 하기」를 첫 결정 자리로(TIP_ASK 문장도 「짐작」 되풀이를 피해 고침), Codex가 채운 design.csv · quantity_rules.py를 열어 역할 짚기,
#   그래프 10단계는 compare 명령을 먼저(Codex는 포털 표를 못 봄), 09단계 질문 3 기대 답도 Codex에게, 손으로 쓰는 것처럼 읽히는 문장 · 토글 속 단계 번호 · `$` 자리 풀이 · 새 대화 여는 법.
# v36-lab(2026-11-20, 사용자 「냉정하게 그냥 헌법, 입력데이터 및 입력 문서 … , 로직 끝아님?」 · 「학생은 오로직 입력은 터미널에서 실행 및 띄워보기, 그리고 바이브코딩 codex 챗엣만」):
#   랩 폴더에는 규칙(AGENTS.md) · 입력(data/) · 로직(app/) · 실행 파일만 둔다 — README.md · requirements.md · review.md · data/model/provenance.md를 뺐다(코드가 읽지 않는 사본 · 서류).
#   가이드는 학생 손으로 파일을 쓰게 하지 않고 Codex에게 적게 하며, 요령 셋(TIP_ASK · TIP_PROOF · TIP_FRESH)을 처음 쓰는 단계에 싣는다. AGENTS.md와 판단 칸은 v35와 같다(장난감 시험 다시 돌리지 않음 — 코딩랩 길 6).
# v35: 랩별 경계에 「권장안대로는 결정이 아니다」(장난감 시험 v34 two_turn)
# v32-lab — 2026-11-18: 독립 검토 두 건(판정/검토_통합2_ontology_v31.json · 검토_통합2_graph_v31.json) 고침 — 가이드 끝의 내 말로 되짚기, 기대 답을 결정 직후 · 구현 앞에, 역량 질문을 현장 값(설비 코드 · 품번)으로 묻기(식별자 틀과 무관), 같은 모델의 구성 요소 이름 맞추기는 제공 코드로(name_rules.py 뺌), 그래프 랩의 쿼리 짚어 보기와 장부의 이름. 앞 판 v31-lab: 설비 3대는 눈으로 다 읽혀 실습 랩 규모(코딩랩 K-3)보다 작아, 공장 규모에서 2라인 한일유압 설비 5대 · 모델 셋(현장 지시계 포함)을 골라 다시 만듦 — 정할 지점은 그대로, 이론 개편의 이름을 받고 요령의 까닭은 lab_frame TIP_*. 앞 판 v30-lab: 독립 검토(판정/검토_지침과_통합2회차.json) 고침 — 작업 2026-11-17_코딩랩-원리중심-학생결정자
WORK = ROOT / '작업/검사/session2-projects'


def write(path, text):
    F.write(path, text)


STRICT_OLD = """        if None in row and list(row)[-2:-1] == ['근거']:      # 맨 끝 「근거」 칸 글에 쉼표가 든 경우 — 남은 칸을 근거에 이어 붙인다
            row['근거'] = ','.join([row['근거'] or '', *row.pop(None)])
        if None in row:
            raise Stop(f'{rel(path)}:{line}: 칸 수가 열 이름보다 많습니다(쉼표가 든 값은 큰따옴표로 감쌉니다).')
"""
STRICT_NEW = """        if None in row:      # 넘친 칸을 끝 칸에 이어 붙이지 않는다 — 앞 칸에 쉼표가 든 줄은 값이 한 칸씩 밀린 채 조용히 지나간다
            raise Stop(f'{rel(path)}:{line}: 칸 수가 열 이름({len(reader.fieldnames)}칸)보다 많습니다 — 값 안에 쉼표가 있으면 그 값을 큰따옴표로 감싸거나 쉼표를 「 · 」로 바꿉니다.')
        if None in row.values():
            raise Stop(f'{rel(path)}:{line}: 칸 수가 열 이름({len(reader.fieldnames)}칸)보다 적습니다 — 빈 칸도 쉼표로 자리를 둡니다.')
"""


def result_sources(strict=False):
    """제공 결과 화면 코드. 대조 표의 거르기 단추 글자를 표 머리로 읽히지 않는 말로 바꾼다(리허설 06 막힘 6).
    strict = 통합반 2회차 두 랩: 칸 수가 열 이름과 다른 CSV 줄을 파일:줄로 짚고 멈춘다(리허설 v32 — 코딩랩 「함정」의 틀 꼴 멈춤). 실전반 · 3회차 생성기는 기본값을 쓴다."""
    utilities, ui = P.result_sources()
    if strict:
        if utilities.count(STRICT_OLD) != 1:
            raise ValueError('결과 화면 코드의 CSV 읽기 꼴이 바뀌었습니다 — 칸 수 멈춤을 넣을 자리를 다시 봅니다.')
        utilities = utilities.replace(STRICT_OLD, STRICT_NEW)
    for old, new in [('o.textContent=only?"모든 줄":"다른 줄만"', 'o.textContent=only?"모든 줄 보기":"같음 줄 숨기기"'),
                     ('<button class="t only">다른 줄만</button>', '<button class="t only">같음 줄 숨기기</button>')]:
        if ui.count(old) != 1:
            raise ValueError(f'결과 화면 코드에서 바꿀 글을 찾지 못했습니다: {old}')
        ui = ui.replace(old, new)
    return utilities, ui


# 장난감 시험(2026-11-12) — AI가 결정 · 기대 답을 스스로 채우고, 기능 파일 여럿을 한꺼번에 짰다. 작업 경계만 둔다(형식은 강제하지 않음, 코딩랩 K-6).
DECISION_RULE = ('- `app/features/decisions.csv`의 고른_것 · 근거와 `app/features/expected.csv`의 기대 답에는 학생이 대화에서 정한 것만 적는다(학생이 보고 받아들인 근거 줄과 기대 답 후보도 된다). '
                 '학생이 정하지 않았으면 적지 않고, 정할 것을 선택지와 그 결과로 보여 묻는다.\n'
                 '- 한 번에 요청받은 기능 파일 하나만 고치고, 그 기능을 실행해 실제 결과를 보인 뒤 멈춘다. 랩 DB를 쓰는 기능은 랩 DB에서 실행한 결과로 확인한다.')   # 실전반 설계 랩이 쓴다(build_practical2_projects)

# 장난감 시험(v34-lab two_turn, 2026-11-18): 「권장안대로 다 해 줘」에 AI가 decisions.csv 두 줄을 근거 칸에 학생 이유 없이 스스로 채우고 끝까지 실행했다.
# 코딩랩 K-3 「이유 없이 판단을 넘기는 부탁은 결정이 아니다」를 이 랩들의 파일 이름으로 적는다(통합반 두 랩만 — 실전반 바이트는 그대로).
NOT_DECIDED = ('- 「권장안대로」 · 「알아서」 · 「다 해 줘」처럼 갈래를 고르지 않거나 이유를 말하지 않은 부탁은 결정이 아니다. '
               '학생이 고를 갈래와 그렇게 고른 자기 이유를 말하기 전에는 `decisions.csv`의 그 줄을 쓰지 않고, 그 결정이 걸린 {files}도 만들거나 고치지 않는다. '
               '추천안을 냈더라도 학생이 그 추천을 받아들인다고 말하고 이유를 대야 결정이고, `decisions.csv`의 근거 칸에는 그 이유를 학생의 말로 적는다. '
               '그때까지는 무엇을 정해야 하는지와 선택지 · 각 선택의 결과를 쉬운 말로 다시 묻는다.')

# 통합반 설계 랩의 랩별 경계 — 이 랩에는 랩 DB가 없고, 판단 함수 파일은 하나다. 표는 가이드가 한 요청에 둘셋을 맞추게 하므로 「요청받은 것만」으로 적는다(검토 지적, 코딩랩 K-6).
DESIGN_RULE = (DECISION_RULE.split('\n')[0] + '\n'
               '- 판단 함수 파일은 `app/features/quantity_rules.py` 하나다. 요청받았을 때만 고치고, 그 기능을 실행해 실제 결과를 보인 뒤 멈춘다. '
               '표(`design.csv` · `relations.csv` · `row_rules.csv` · `expected.csv` · `decisions.csv`)는 요청받은 것만 고친다.\n'
               '- 모델은 `python run.py parts`가 `output/schema.json` · `output/graph.json`에 쓴다. 이 두 파일을 손으로 고치지 않는다.\n'
               + NOT_DECIDED.format(files='`quantity_rules.py`, `row_rules.csv`의 떼어 낸 펌프 줄, `design.csv` · `relations.csv`의 실물 행'))


# 리허설 07 막힘: Codex 샌드박스는 랩 DB(Docker)에 닿지 못해 AI가 실행을 시도하다 실패했다. 그래프 랩은 랩 DB 명령을 학생 터미널에 둔다.
GRAPH_DECISION_RULE = ('- `app/features/decisions.csv`의 고른_것 · 근거와 `app/features/expected.csv`의 기대 답에는 학생이 대화에서 정한 것만 적는다(학생이 보고 받아들인 근거 줄과 기대 답 후보도 된다). '
                       '학생이 정하지 않았으면 적지 않고, 정할 것을 선택지와 그 결과로 보여 묻는다.\n'
                       '- 한 번에 요청받은 기능 파일 하나만 고친 뒤 멈춘다. 랩 DB를 쓰는 명령(`python run.py` 기능)은 학생이 자기 터미널에서 실행하고, '
                       'AI는 학생이 붙여 준 터미널 출력과 결과 화면으로 확인한다. AI가 그 명령을 직접 실행하지 않는다.')   # 실전반 그래프 랩이 쓴다(build_practical2_projects)

# 통합반 그래프 랩의 랩별 경계 — 위 둘에 장난감 시험(v32-lab two_turn)에서 뚫린 두 틈을 막는 줄을 더한다(코딩랩 K-6 · 길 6).
GRAPH_RULE = (GRAPH_DECISION_RULE + '\n'
              '- `app/features/update.cypher`의 불용 설비 처리는 `decisions.csv` 「불용 결정 설비」 줄을 학생이 정한 뒤에만 쓴다. '
              '정하기 전에는 수정본의 다른 줄만 반영하고 그 처리는 쓰지 않으며, 무엇을 정해야 하는지 선택지와 결과로 묻는다.\n'
              '- 「다 해 줘」처럼 여러 기능을 한꺼번에 부탁받아도 기능 파일 하나를 고친 뒤 멈추고, 다음 기능을 할지 묻는다.\n'
              + NOT_DECIDED.format(files='`update.cypher`의 불용 설비 처리'))


def run_source():
    """제공 run.py — 실행이 확인 필요로 끝나도 직전에 성공한 결과를 지우지 않고, 이번 실패를 위에 · 직전 성공을 그 아래에 밝혀 보인다(리허설 07 막힘)."""
    BS = chr(92)
    text = P.RUN
    old = "    target.write_text(page(actions.TITLE, title, blocks), encoding='utf-8', newline='" + BS + "n')" + chr(10) + \
          "    (output / 'result.json').write_text(json.dumps({'action': args.action, 'blocks': blocks}, ensure_ascii=False, indent=2) + '" + BS + "n', encoding='utf-8')" + chr(10)
    new = ("    failed = any(b['kind'] == 'error' for b in blocks)" + chr(10) +
           "    saved = output / 'result.json'" + chr(10) +
           "    last = json.loads(saved.read_text(encoding='utf-8')).get('last_success') if saved.exists() else None" + chr(10) +
           "    if not failed:" + chr(10) +
           "        last = {'action': args.action, 'title': title, 'blocks': blocks}" + chr(10) +
           "    shown = blocks + ([results.note('아래는 직전에 성공한 「' + last['title'] + '」 실행의 결과입니다. 이번 실행은 위의 확인 필요로 끝났습니다.')] + last['blocks'] if failed and last else [])" + chr(10) +
           "    target.write_text(page(actions.TITLE, title, shown), encoding='utf-8', newline='" + BS + "n')" + chr(10) +
           "    saved.write_text(json.dumps({'action': args.action, 'blocks': blocks, 'last_success': last}, ensure_ascii=False, indent=2) + '" + BS + "n', encoding='utf-8')" + chr(10))
    if text.count(old) != 1:
        raise ValueError('run.py 원본의 결과 쓰기 줄을 찾지 못했습니다.')
    return text.replace(old, new)


def source_data(folder):
    work = (ROOT / '작업/검사/session2-projects').resolve()
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=work, prefix='data-') as temp:
        raw = Path(temp).resolve()
        assert raw.is_relative_to(work) and raw != work
        D.write_sources(raw)
        for path in raw.iterdir():
            write(folder / 'data' / P.NAMES[path.name], P.convert(path.read_text(encoding='utf-8-sig')))


def checker(folder, L):
    provided = [p.relative_to(folder).as_posix() for p in student_files(folder)
                if p.relative_to(folder).as_posix().startswith(('app/ui/', 'app/utils/')) or p.name == 'run.py']
    guard = F.provided_guard(folder, provided)
    chosen = P.convert(F.CHOSEN_CHECK)
    head = ('from pathlib import Path\nimport sys\n' + guard + chosen +
            '_root = Path(__file__).resolve().parents[2]\n_pre = provided_errors(_root) + chosen_errors(_root)\n')
    body = P.convert(B.CHECKER).replace('Path(__file__).resolve().parent', 'Path(__file__).resolve().parents[2]')
    body = body.replace("root/'app/features'", "root/'output'")
    body = body.replace('가이드 「결과 형식」의 모양으로 만든 뒤 다시 실행하세요.', 'python run.py parts로 모델을 생성한 뒤 다시 실행하세요.')
    body = body.replace('(가이드 결과 형식 참고)', '')
    body = body.replace('if errors:\n', 'errors = _pre + errors\nif errors:\n')
    if L['kind'].startswith('graph'):
        body = body.replace('python run.py parts로 모델을 생성', 'python run.py export로 그래프를 저장')
    return head + body


def build_ontology(folder):
    D.require('통합반')
    L = B.design_integrated()
    source_data(folder)
    drawing = Path(__file__).with_name('session2_relationships.json')
    write(folder / 'data/relationships.json', drawing.read_text(encoding='utf-8-sig'))
    for name, text in L['files'].items():
        if name.startswith('결과/') and not name.endswith('README.md'):
            write(folder / P.convert(name), P.convert(text))
    utilities, ui = result_sources(strict=True)
    write(folder / 'app/utils/results.py', utilities)
    write(folder / 'app/ui/render.py', ui)
    write(folder / 'app/utils/model.py', P.model_source())
    actions = P.actions_source(L)
    commands = {'sources': ('원자료', 'sources'), 'expected': ('기대 답', 'expected'),
                'design': ('식별자와 관계', 'design'), 'names': ('구성 요소 이름과 실물', 'names'),
                'quantities': ('물리량과 센서', 'sensors'),
                'parts': ('부품과 모델', 'parts'), 'query': ('질문별 대조', 'ask'), 'check': ('구조 검사', 'check')}
    actions += '\nCOMMANDS = {\n' + ''.join(f'    {cmd!r}: ({label!r}, {fn}),\n' for cmd, (label, fn) in commands.items()) + '}\n'
    write(folder / 'app/utils/actions.py', actions)
    write(folder / 'run.py', run_source())
    write(folder / 'app/utils/check.py', checker(folder, L))
    write_metadata(folder, L['title'], G.ONTOLOGY_PURPOSE, extra_rules=DESIGN_RULE, readme_file=False)
    steps = G.ontology()
    F.write_guide(folder, G.render(L['title'], G.ONTOLOGY_PURPOSE, steps), ai_turns=sum(s['ai'] for s in steps))
    return L, steps


def build_graph(folder):
    D.require('통합반')
    L = B.graph_lab('통합반')
    source_data(folder)
    schema, graph = B.reference_model(False, B.GRAPH_LAB_INPUT['통합반'])
    for name, value in [('schema.json', B.student_schema(schema)), ('graph.json', graph)]:
        write(folder / 'data/model' / name, P.convert(json.dumps(value, ensure_ascii=False, indent=2) + '\n'))
    write(folder / 'data/reference_map.json', json.dumps(B.portal_reference(), ensure_ascii=False, indent=2) + '\n')   # 비교 기능(compare)이 내 그래프 아래에 띄우는 기준 지도
    for name, text in L['files'].items():
        if name.startswith('결과/') and not name.endswith('README.md'):
            if name == '결과/기대_답.csv':
                text = text.replace('값이 없으면(원자료에 없는 품번 · 빈 값) 「없음」',
                                    '쿼리 결과가 0행이면 「0줄」, 반환된 행의 빈 칸은 「없음」. 없는 품번을 설명하는 행을 반환하면 그 설명을 그대로 적음')
                if '쿼리 결과가 0행이면' not in text:
                    raise ValueError('그래프 랩 기대 답 틀의 값 꼴 문장이 바뀌었습니다.')
            write(folder / P.convert(name), P.convert(text).replace('python show_result.py가 실행', 'python run.py load가 실행'))
    with tempfile.TemporaryDirectory(dir=WORK, prefix='changes-') as temp:
        raw = Path(temp).resolve()
        assert raw.is_relative_to(WORK.resolve()) and raw != WORK.resolve()
        D.write_changes(raw)
        for path in raw.iterdir():
            name = 'notes.md' if path.name == 'README.md' else P.NAMES[path.name]
            text = P.convert(path.read_text(encoding='utf-8-sig')).replace('`../data/`', '`data/`')
            write(folder / 'data/changes' / D.CHANGE_DATE / name, text)
    utilities, ui = result_sources(strict=True)
    write(folder / 'app/utils/results.py', utilities)
    write(folder / 'app/ui/render.py', ui)
    write(folder / 'app/utils/db.py', GP.db_source())
    write(folder / 'app/utils/cypher.py', GP.cypher_source(integrated=True))
    write(folder / 'app/utils/actions.py', GP.actions_source(L))
    write(folder / 'run.py', run_source())
    write(folder / 'app/utils/check.py', checker(folder, L))
    write_metadata(folder, L['title'], G.GRAPH_PURPOSE, extra_rules=GRAPH_RULE + '\n' + DB_RULE, readme_file=False)
    steps = G.graph()
    F.write_guide(folder, G.render(L['title'], G.GRAPH_PURPOSE, steps), ai_turns=sum(s['ai'] for s in steps))
    return L, steps


def validate(folder, L, steps):
    issues = errors({p.relative_to(folder).as_posix(): p.read_bytes() for p in student_files(folder)}, folder.name)
    if issues:
        raise ValueError(issues)
    pack(folder)
    item = entry('integrated-02-' + folder.name.removesuffix('-lab'), '통합반', '온라인 02회차', L['title'], VERSIONS[folder.name], folder,
                 guide_steps=[s['name'] for s in steps])
    from verify_packages import check_zip, verify_lab
    assert not check_zip(folder.with_suffix('.zip'), folder)[0]
    verify_lab(item)
    return item


def replace_generated(source, target):
    """검사가 끝난 이 생성기의 프로젝트 하나만 정본에 반영한다."""
    target = target.resolve()
    if target.parent != DEST.resolve() or target.name != source.name or target.name not in ('ontology-lab', 'graph-lab'):
        raise ValueError('지정한 통합02 프로젝트 밖에는 반영하지 않습니다.')
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)
    for suffix in ('_guide.html', '.zip'):
        shutil.copyfile(source.parent / (source.name + suffix), target.parent / (target.name + suffix))


def completed(starter, destination, work):
    """학생용 완성본은 별도 묶음이며 시작 ZIP에 넣지 않는다. 유료 AI 호출 없음."""
    import session2_answers as A
    folder = work / 'completed' / starter.name
    shutil.copytree(starter, folder)
    if starter.name == 'ontology-lab':
        branch = B.GRAPH_LAB_INPUT['통합반']    # 완성본은 다음 랩(그래프)의 제공 모델과 같은 판단
        files = A.integrated_design(branch)
        files['결과/정한_것.csv'] = B.chosen_text(A.integrated_chosen(branch))
        files['결과/기대_답.csv'] = B.expect_design_text(branch)
        for name, text in files.items():
            write(folder / P.convert(name), P.convert(text))
        title, initial = '온톨로지 설계', 'python run.py parts\npython run.py query'
        context, actions, rules = nullcontext(), ('parts', 'check', 'query'), DESIGN_RULE
    else:
        from reference.session2_graph_trials import expectation, fill, instance
        fill(folder)
        expectation(folder, after='남김')     # 완성본은 수정본까지 반영한 상태라 기대 답도 그 뒤의 답이다
        target = folder / 'app/features/expected.csv'   # 칸 뜻 머리는 학생 빈 틀과 같은 줄을 쓴다(v36 검토 — 강사 참조의 머리는 「0줄」 꼴을 모른다)
        head = (starter / 'app/features/expected.csv').read_text(encoding='utf-8').split('\n', 1)[0]
        target.write_text(head + '\n' + target.read_text(encoding='utf-8').split('\n', 1)[1], encoding='utf-8', newline='')
        title, initial = '그래프 구현과 검증', 'python run.py db\npython run.py load\npython run.py update\npython run.py usage'
        context, actions, rules = instance(folder), ('load', 'repeat', 'sensors', 'parts', 'update', 'usage', 'compare', 'export', 'check'), GRAPH_RULE + '\n' + DB_RULE
    write_metadata(folder, title + ' · 완성본',
                   'AI 계정이 없거나 구현 중 막혔을 때 실행해 보는 묶음입니다. 판단마다 갈래 하나를 골라 적용했으며 선택과 근거는 app/features/decisions.csv에 있습니다.'
                   + (' Docker Desktop을 켠 뒤 실행합니다.' if starter.name == 'graph-lab' else ''), command=initial, extra_rules=rules, readme_file=False)   # 완성본을 Codex로 열어도 같은 랩별 경계
    logs = {}
    with context:
        for action in actions:
            run = subprocess.run([sys.executable, 'run.py', action, '--no-open'], cwd=folder,
                                 capture_output=True, text=True, encoding='utf-8')
            logs[action] = run.stdout + run.stderr
            if run.returncode:
                raise RuntimeError(logs[action])
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / (starter.name + '-completed.zip')
    write_zip(archive, [(starter.name + '/' + p.relative_to(folder).as_posix(), p.read_bytes()) for p in student_files(folder)])
    write(work / 'completed-execution.json', json.dumps(logs, ensure_ascii=False, indent=2) + '\n')
    return archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('lab', choices=['ontology', 'graph'])
    dest = parser.add_mutually_exclusive_group(required=True)
    dest.add_argument('--dest', type=Path, help='작업/ 아래 새 검증용 부모 폴더; 목록은 등록하지 않음')
    dest.add_argument('--apply', action='store_true', help='검증 사본을 만든 뒤 지정한 통합02 랩만 교체')
    parser.add_argument('--completed', action='store_true', help='별도 학생용 완성본도 실제 실행해 생성')
    args = parser.parse_args()
    build = build_ontology if args.lab == 'ontology' else build_graph
    WORK.mkdir(parents=True, exist_ok=True)
    with D.for_course('통합반'):
        generate(parser, args, build)


def generate(parser, args, build):
    if args.dest:
        parent = args.dest.resolve()
        if not parent.is_relative_to((ROOT / '작업').resolve()):
            parser.error('--dest는 저장소 작업/ 아래 새 폴더입니다.')
        folder = parent / (args.lab + '-lab')
        if folder.exists():
            parser.error('검증 폴더가 있습니다. 다른 --dest를 사용합니다.')
        L, steps = build(folder)
        validate(folder, L, steps)
        if args.completed:
            completed(folder, parent, parent)
    else:
        with tempfile.TemporaryDirectory(dir=WORK, prefix='publish-') as temp:
            work = Path(temp).resolve()
            assert work.is_relative_to(WORK.resolve()) and work != WORK.resolve()
            source = work / (args.lab + '-lab')
            L, steps = build(source)
            validate(source, L, steps)
            archive = completed(source, work, work) if args.completed else None
            folder = DEST / source.name
            replace_generated(source, folder)
            register([validate(folder, L, steps)])
            if archive:
                target = DEST.parent / '완성본' / archive.name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(archive, target)
                shutil.copyfile(work / 'completed-execution.json', WORK / (args.lab + '-completed-execution.json'))
    print(folder)


if __name__ == '__main__':
    main()
