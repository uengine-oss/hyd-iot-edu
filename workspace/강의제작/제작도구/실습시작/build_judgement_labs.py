"""냉각 경보 조치 판단 묶음 네 랩의 학생 폴더 · ZIP · 가이드를 만든다 — 통합반 03회차 실습2(조치 기준) · 실습3(판단 기능),
실전반 02회차 실습5(조치 조건표) · 03회차 실습2(조치 검토 결과).

원자료 코어는 data_conditions.py 한 벌(고정 시드, 같은 입력이면 같은 바이트)이고, 랩마다 대조에 쓰는 파일만 넣는다.
학생은 방향이 갈리는 판단만 `결과/`의 정할 자리(「제공 빈 틀」 표 · 빈 함수)에 AI와 채운다. 일반 로직은 제공 코드 `judgement_tools/`(condition_tools ·
judge_tools · sop_tools — 정본 한 벌, 바이트 그대로 넣음)이고, `python show_result.py`가 채워진 단계까지 제공 흐름을 돌려 `결과/보기.html`을 쓴다(lab_steps.py).
단계 · 작업 규칙 · 가이드 · 결과 화면 틀은 lab_frame.py(공용 틀)에서 가져온다. 가이드는 랩 폴더 밖 `<랩 폴더>_guide.html`이고, 단계마다 「정답 보기」 토글은
강사 참조(reference/session3 — criteria.py · judge_actions.py)의 기본 갈래 채움이다. 토글을 새 사본에 넣어 결과가 나오는지는 reference/session3/run_reference.py가 본다.
판정 랩의 입력/(조건표 · SOP 구조)은 조건 랩의 강사 검증 판(criteria.py, 지점1 가 · 지점2 가)이다.

네 랩은 새 프로젝트 구조로 바뀌었다. 이 파일의 랩 정의 · 검사기 · 결과 화면 함수는 build_session3_projects.py가 입력으로 쓰고
(임시 폴더에 옛 구조를 만든 뒤 영어 경로로 옮김), 학생 폴더 · ZIP · package-index는 그 생성기가 쓴다. 이 파일을 직접 돌리면 새 생성기 이름을 대며 멈춘다.
LABS의 경로는 옛 구조 랩의 이름(새 생성기가 임시 폴더 이름으로 쓴다)이며, 그 정본 자리에는 이제 폴더가 없다.
"""
from pathlib import Path
import csv
import io
import json
import sys

import build_labs as B          # 2회차 설비 모델(통합 03-2 입력/) — 틀은 lab_frame
import lab_frame as F
from lab_frame import A, H, S, paste, tree, write
import data_conditions as DC
import data_session2 as D2

TOOLS = Path(__file__).resolve().parent
PROVIDED_SRC = TOOLS/'judgement_tools'
sys.path[:0] = [str(TOOLS/'reference/session3'), str(PROVIDED_SRC)]
import criteria as CR  # noqa: E402  강사 검증 판 · 정할 자리 기본 갈래 채움
import judge_actions as J  # noqa: E402  판정 랩 갈래 답
import condition_tools as CT  # noqa: E402

OUT = F.OUT
LABS = {
    'integrated-03-criteria': OUT/'통합반/실습/03회차/랩/03일차_실습2_조치기준만들기',
    'integrated-03-judge': OUT/'통합반/실습/03회차/랩/03일차_실습3_판단기능만들기',
    'practical-02-conditions': OUT/'실전반/실습/02회차/랩/02일차_실습5_조치조건표',
    'practical-03-review': OUT/'실전반/실습/03회차/랩/03일차_실습2_판단기능만들기',
}
TITLES = {   # 랩 제목 = 온라인 실라버스 행 제목(같은 ZIP을 오프라인이 받는다 — K-11). 다음 실습을 이름으로 가리킬 때도 여기서 읽는다(K-2)
    'integrated-03-criteria': '작업 절차와 판단 조건을 연결해 조치 기준 만들기',
    'integrated-03-judge': '설비 조건별 최적의 조치를 비교하는 판단 기능 만들기',
    'practical-02-conditions': '작업 기준의 복합 조건과 예외를 조치 조건표로 표현하기',
    'practical-03-review': '판정·성과 비교를 조치 검토 결과로 완성하기',
}
PROVIDED = {   # 랩 루트에 넣는 제공 도구(정본 judgement_tools/의 바이트 그대로)
    'integrated-03-criteria': ['condition_tools.py', 'sop_tools.py'],
    'practical-02-conditions': ['condition_tools.py'],
    'integrated-03-judge': ['condition_tools.py', 'judge_tools.py'],
    'practical-03-review': ['condition_tools.py', 'judge_tools.py'],
}
MINE = {   # 내 앞 결과를 쓰는 길(선택 — K-9). START 「출발점」과 가이드 첫 화면이 같은 문장을 쓴다
    'integrated-03-criteria': ('내 모델을 쓸 때: 제공 입력은 그대로 두고 내 `schema.json` · `graph.json`을 `결과/내_입력/`에 복사해, 형식과 ID 짓는 법이 제공 모델과 같은지 먼저 견준 뒤 씁니다. '
                               '제공 코드와 구조 검사는 `결과/내_입력/graph.json`이 있으면 그 모델의 ID로 봅니다. 내 모델이 없어도 제공된 모델로 끝까지 할 수 있습니다.'),
    'integrated-03-judge': ('내 조치 기준을 쓸 때: 제공 입력은 그대로 두고 내 `조건표.csv` · `sop.json`을 `결과/내_입력/`에 복사해, 열 이름 · ID가 `입출력_계약.md`와 같은지 먼저 견준 뒤 씁니다. '
                            '제공 코드와 구조 검사는 `결과/내_입력/`에 있는 파일을 기준으로 봅니다. 내 조치 기준이 없어도 제공된 입력으로 끝까지 할 수 있습니다.'),
    'practical-03-review': ('내 조건표를 쓸 때: 제공 입력은 그대로 두고 내 `조건표.csv`를 `결과/내_입력/`에 복사해, 열 이름 · 규칙이 거는 후보가 `입출력_계약.md`와 같은지 먼저 견준 뒤 씁니다. '
                            '제공 코드와 구조 검사는 `결과/내_입력/`에 있는 파일을 기준으로 봅니다. 내 조건표가 없어도 제공된 조건표로 끝까지 할 수 있습니다.'),
}
LAB4_INPUT = OUT/'통합반/실습/02회차/랩/graph-lab/data'
RULES_LINE = '`AGENTS.md` · `.github/copilot-instructions.md` · `CLAUDE.md` — Codex와 GitHub Copilot이 지키는 작업 규칙(세 파일이 같은 내용). 학생도 함께 읽습니다.'
SHOW_LINE = '`show_result.py` · `lab_steps.py` — 결과 화면(`python show_result.py`가 채운 단계까지 제공 흐름을 돌려 `결과/보기.html`을 다시 씀). 고치지 않습니다.'
MEMO = '사건_기록_HYD-02_1027.md'
EXPORT = '판단시스템_결정표_내보내기.txt'


def blank(columns, explain):
    return F.blank_csv(columns, explain)


EXPECT_COLUMNS = ['사례', '후보', '기대_판정', '근거']
CASE_FROM_CASES = '`자료/확인_사례.csv`의 사례 ID(사건 메모의 경보도 그 ID)'
CASE_FROM_ALARMS = '`자료/경보_목록.csv`의 RAISE 행 경보_ID'


def expect_cols(case_from):
    """기대_판정.csv 칸마다 뜻 — 빈 틀 첫 줄 · 정답 토글 첫 줄 · 그 단계 「지킬 것」이 같은 글을 쓴다(값은 넣지 않음)."""
    return (f'한 줄에 사례 하나의 후보 하나, 실행 전에 원자료로 구한 값 · 사례 = {case_from} · 후보 = `자료/targets.csv`의 SOP ID · '
            '기대_판정 = 유지 · 제외 · 보류 가운데 하나 · 근거 = 파일:줄(여러 개는 ;)')


def expect_blank(case_from):
    return blank(EXPECT_COLUMNS, expect_cols(case_from))


def csv_text(header, rows, explain):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator='\n')
    w.writerow(header)
    w.writerows(rows)
    return f'# {F.MARK} — {explain}\n' + buf.getvalue()


# ───────────── 계약(형식과 뜻만 — K-7) ─────────────
CODES_FROM_TARGETS = '`targets.csv`의 `kind` · `codes`'
CODES_FROM_EXPORT = '판단 시스템 결정표 내보내기의 「스킬」 절 — 종류 칸과, 동작 칸을 「코드 이름」 절의 괄호 안 코드로 바꾼 것'
SOURCE_FORM = ('받은 원문의 근거는 절 · SOP 단계 · 승인 줄을 ;로 잇고 문서 이름 · 판은 붙이지 않는다(꼴: HM-8.<절>; HM-8.<절> SOP-<ID> 단계 <n>; HM-8.<절> SOP-<ID> 승인), '
               '자료 파일의 줄은 파일:줄, 결정표에서 가져온 행은 「판단 시스템 결정표 rule:<id>; 출처 <그 규칙의 출처>」 뒤에 받은 원문에서 그 출처를 찾았는지를 적고, '
               '결정표 규칙을 고쳐 받은 원문 근거로 옮긴 행은 원문 출처 뒤에 「판단 시스템 결정표 rule:<id>」를 덧붙인다(결과 화면은 rule:<id>가 있어야 그 규칙을 출처로 든 것으로 읽는다)')
TABLE_CONTRACT = '''## 조건표 (`결과/조건표.csv`)

조건표는 다음 실습의 판정 기능이 그대로 읽는 입력이다. 열 이름을 바꾸면 다음 단계에서 읽지 못한다. 이 문서는 형식과 뜻만 정하고, 어떤 조건을 어느 조치에 걸지는 원문에서 정한다. 첫머리의 `#` 줄(「제공 빈 틀」 표시)은 데이터가 아니다.

열: `rule_id,action,condition_index,logic,input,operator,value,unit,boundary_included,result,penalty_manwon,reason,source_section`

- 비교 하나가 한 행이다. 같은 `rule_id` · `action`의 행은 한 규칙 묶음이고 `condition_index`를 1부터 차례로 적으며 `logic`은 `AND`다. OR는 다른 `rule_id`로 나눈다.
- `action`: `자료/targets.csv`의 SOP ID 하나. 같은 규칙을 여러 조치에 걸면 조치마다 묶음 전체를 적는다. 표에 없는 조치 · 규칙 조합은 그 조치에 그 규칙을 걸지 않는다는 뜻이다.
- `result`: `WARN`(경고) · `PENALTY`(감점) · `EXCLUDE`(제외). 같은 묶음의 `result` · `penalty_manwon` · `reason` · `source_section`은 모든 행에서 같다. `PENALTY`만 `penalty_manwon`(만원)을 적고 나머지는 빈칸이다.
- `operator`: `>=` · `>` · `<=` · `<` · `==` · `!=` · `has_other_than`(목록 입력에 기준값이 아닌 항목이 하나라도 있음). `boundary_included`: 기준값 자체가 조건에 들어가면 `예`, 들어가지 않으면 `아니오`, 글자 · 목록 비교는 `해당없음`.
- `input`과 단위: `forecast_ts1`(조치 후 예측 유온, ℃) · `forecast_ps1`(조치 후 예측 토출 압력, bar) · `fan100_hours`(팬 100 % 연속 운전 시간, h) · `plc_mode`(`REMOTE_AUTO` · `REMOTE_MANUAL` · `LOCAL`) · `plc_state`(`RUN` · `TRIP` · `STOP`) · `skill_kind`(조치 종류 `control` · `work_order`) · `skill_code`(실행 코드 목록). `skill_kind` · `skill_code` 값이 오는 곳: {codes_from}. 숫자 입력은 `unit`을 적는다.
- 목록 입력(`skill_code`)에는 `has_other_than`만 쓴다.
- `source_section`: 이 행의 근거를 다른 사람이 다시 찾을 수 있게 적는다 — ''' + SOURCE_FORM + '''.

모양을 보이는 한 줄(이 과제의 규칙이 아니다):

```
R0,SOP-COOL-00,1,AND,forecast_ts1,>=,0,℃,예,WARN,,이유 문장,문서 절
```
'''

SOP_CONTRACT = '''## SOP 구조 (`결과/sop.json` — 제공 코드 `sop_tools.py`가 아래 판단 표 셋으로 쓴다)

키는 영어로 적고 값(원문 문장 · 역할 이름)은 원문 그대로 적는다.

```
{
  "document": {"id": "...", "revision": "...", "file": "자료/..."},
  "failure_modes": [ {"id": "failuremodes.csv의 ID", "name": "...", "source": "..."} ],
  "causes": [ {"id": "cause:...", "name": "...", "source": "..."} ],
  "sops": [
    {
      "id": "targets.csv의 SOP ID", "name": "...", "kind": "control 또는 work_order 또는 null", "codes": ["..."],
      "source": "문서 절", "failure_mode": "고장 유형 ID",
      "model_refs": {"assets": ["..."], "components": ["..."], "sensors": ["..."], "not_linked": "..."},
      "apply_conditions": [ {"text": "...", "source": "...", "rules": ["rule_id"]} ],
      "prohibitions": [ {"type": "금지 또는 제한", "text": "...", "source": "...", "rules": []} ],
      "steps": [ {"order": 1, "text": "...", "source": "..."} ],
      "completion": [ {"text": "...", "source": "...", "rules": []} ],
      "approval": {"role": "...", "source": "..."}
    }
  ],
  "relations": [ {"type": "...", "from": "ID", "to": "ID", "source": "..."} ]
}
```

- 키의 뜻: `document` 원문 문서(식별자 · 판 · 파일), `failure_modes` 고장 유형, `causes` 원인, `sops` 조치 절차, `kind` 조치 종류, `codes` 실행 코드, `source` 출처,
  `failure_mode` 그 절차가 다루는 고장 유형, `model_refs` 모델 참조(`assets` 설비 · `components` 구성 요소 · `sensors` 센서 · `not_linked` 걸지 않은 대상과 까닭),
  `apply_conditions` 적용 조건, `prohibitions` 금지 조건, `steps` 수행 단계(`order` 순서), `completion` 완료 기준, `approval` 승인(`role` 역할), `rules` 이 조건을 옮긴 조건표의 `rule_id`, `relations` 관계 목록.
- `targets.csv`의 SOP는 `sops`에 한 번씩 있다. `steps`는 매뉴얼의 번호 줄 그대로다.
- `model_refs`의 값은 `입력/graph.json`에 있는 ID만 쓴다 — `assets`에는 설비, `components`에는 구성 요소, `sensors`에는 센서의 ID. 모델에 없는 대상은 ID를 만들지 않고 `not_linked`에 그 까닭을 적는다.
- `kind` · `codes` 값이 오는 곳: {codes_from}. 그곳에 같은 절차가 없으면 `kind`는 `null`, `codes`는 빈 목록이다.
- `causes`의 `id`는 `cause:`로 시작하는 영어 소문자 · 하이픈 이름이다.
- `relations`의 `type`: `MITIGATED_BY`(고장 유형 → 즉시 완화 SOP) · `REMEDIED_BY`(고장 유형 → 근본 조치 SOP) · `ADDRESSES`(SOP → 그 SOP가 맞는 원인). 양 끝은 이 파일의 `failure_modes` · `causes` · `sops`에 있는 ID다.
- 각 항목의 `source`는 문서 절과 SOP 단계(예: `HM-8.5 SOP-COOL-11 단계 2`)다. 매뉴얼 밖 자료를 근거로 들면 `파일:줄`이다.
- `approval`은 원문 승인 줄의 역할과 출처다. 원문에서 그 절차의 승인을 찾지 못하면 역할을 만들지 않고 `role`을 `미확인`으로 시작해 찾아본 결과를 적으며, `source`에는 찾아본 절을 적는다.
- 조건과 조건표의 연결은 `rules`에 조건표의 `rule_id`로 적는다. 조건표로 옮기지 않은 조건은 빈 목록이다.

## 판단 표 셋 (`결과/` — 「제공 빈 틀」, 첫머리 `#` 줄은 데이터가 아니다)

「원문」 칸: `;`로 나눈 원문 자리. `자료/HM-8_매뉴얼.md`의 줄 번호(`45`)나 그 줄의 몇째 문장(`45.2` — 마침표 뒤 띄어쓰기로 나눔), 매뉴얼 밖 자료는 `파일 이름:줄`(`판단시스템_결정표_내보내기.txt:37`).
제공 코드는 원문 자리의 문장을 그대로 인용하고, 그 자리가 있는 절 · SOP 단계 · 승인 줄을 출처로 적는다.

- `결과/조건_분류.csv` — 열 `sop_id,칸,원문,글,규칙`. 한 줄이 절차 하나의 한 칸이다 — 칸 · 원문 · 글 · 규칙이 같은 줄이 여러 절차에 걸리면 `sop_id`에 그 SOP ID를 `;`로 이어 한 줄에 적는다. `칸`: `고장 유형`(글 = failuremodes.csv의 ID) · `종류·코드`(글 = `control:코드;코드` · `work_order:코드` · `없음`) ·
  `적용` · `금지` · `제한` · `완료`(글은 비우면 원문 문장을 인용, 매뉴얼 밖 자료만 가리키면 그 조건을 글에 적음) · `승인`(글 = 역할, 찾지 못했으면 `미확인`으로 시작해 찾아본 결과). `규칙` = 그 조건을 옮긴 조건표의 `rule_id`(`;`로 나눔).
  절차마다 `고장 유형` · `종류·코드` · `승인`은 한 줄씩이다.
- `결과/관계.csv` — 열 `type,from,to,이름,원문`. `type`은 위 셋, `이름`은 `to`가 원인(`cause:…`)일 때 그 원인의 이름.
- `결과/설비_연결_기준.csv` — 열 `sop_id,설비,구성_요소,센서,걸지_않은_까닭`. 설비는 설비 ID(`;`로 나눔), 구성 요소 · 센서는 설비 ID 뒤의 이름(`HYD-01:fan`의 `fan`)이고, 제공 코드가 고른 설비마다 모델에 있는 ID만 잇는다.
'''

CASES_CONTRACT = '''## 확인 사례 (`자료/확인_사례.csv`, 읽기만)

열: `사례,설비,판정_요청_시각,후보,입력,값,단위,원천,원천_시각,비고`. 한 줄이 사례 하나의 판단 입력 하나다.

- `값`은 판정을 요청한 때(`판정_요청_시각`)의 판단 입력이고 단위는 `단위` 칸이다. 조건표 `input`과의 짝: `운전_모드` = `plc_mode`, `상태` = `plc_state`,
  `팬100_연속` = `fan100_hours`(판정 요청 때까지 팬 100 % 연속 운전 시간, h), `예측_TS1` = `forecast_ts1`(℃), `예측_PS1` = `forecast_ps1`(bar).
- `후보`가 빈칸인 줄은 그 사례의 모든 후보에 같은 입력이다. `skill_kind` · `skill_code`는 이 파일에 없다 — 값이 오는 곳은 조건표 절의 `input` 설명과 같다.
- `값`이 빈칸이면 그 입력을 얻지 못한 것이고, `비고`에 원천의 사정이 있다.
- `원천` · `원천_시각`은 그 값을 만든 기록과 그 기록의 시각이다.
'''

CHOSEN_CONTRACT = '''## 고른 것 (`결과/정한_것.csv`) · 기대 판정 (`결과/기대_판정.csv`)

- `결과/정한_것.csv` — 열 `지점,고른_것,근거,바뀌는_답`. 칸마다 뜻은 그 파일 첫머리 `#` 줄에 있다. 같은 종류의 지점이 여럿이면 지점마다 한 줄.
- `결과/기대_판정.csv` — 열 `사례,후보,기대_판정,근거`. `사례`는 {case_from}. 제공 코드를 돌리기 전에 원자료 · 조건표 · 원문으로 손으로 구한 기대. `기대_판정`은 `유지` · `제외` · `보류`(뜻은 `자료/작업기준.md` 4절), `근거`는 `파일:줄`.
'''

PLACE_JUDGE_CONTRACT = '''## 정할 자리 (`결과/gap_rule.py` · `결과/compare_rule.py` — 「제공 빈 틀」 빈 함수)

제공 코드 `judge_tools.py`가 부르는 함수 둘이다. 입력과 돌려줄 값의 꼴은 각 파일 머리에 있다. 함수가 꼴과 다른 값을 돌려주면 제공 코드가 그 파일 · 경보를 밝혀 멈춘다.
`결과/정한_것.csv`의 `빈 값의 뜻` · `쓰는 사람에 따라 갈리는 답` 행의 `고른_것`은 결과의 `decisions`에, `비교 기준 문장` 행의 `고른_것`은 결과의 `comparison_basis`에 그대로 옮겨진다.
'''

APPROVAL_CONTRACT = '''## 승인 (`결과/승인.csv` — 「제공 빈 틀」)

열 `sop_id,승인_역할,원문`. 후보마다 한 줄. `원문`은 `자료/HM-8_매뉴얼.md`의 승인 근거 줄 번호(`68` 또는 `자료/HM-8_매뉴얼.md:68`, `;`로 나눔, 찾지 못했으면 찾아본 절의 줄과 함께 `승인_역할`을 `미확인`으로 시작).
'''


# ───────────── 검사기(구조만 — 의미 정답은 판정하지 않는다, K-7) ─────────────
READ_CSV = r'''def csv_rows(path):
    """(열 이름, 행, 첫머리 # 줄 수) — 「제공 빈 틀」 표시 줄은 데이터가 아니다."""
    lines = path.read_text(encoding='utf-8-sig').splitlines(keepends=True)
    skip = 0
    while skip < len(lines) and lines[skip].lstrip().startswith('#'):
        skip += 1
    reader = csv.DictReader(io.StringIO(''.join(lines[skip:]), newline=''))
    return reader.fieldnames, list(reader), skip
def read_csv(path):
    head, rows, _ = csv_rows(path)
    return head, rows
def report(parts):
    ok = True
    for name, state, errs, note, required in parts:
        print(f'- {name}: {state}' + (f' — {note}' if note else ''))
        for e in errs[:40]: print('    ' + e)
        if len(errs) > 40: print(f'    … 외 {len(errs) - 40}건')
        if required and state not in ('통과', '아직 비어 있음'): ok = False
    return ok
def expect_part(root):
    p = root/'결과/기대_판정.csv'
    if not p.is_file(): return ('기대_판정.csv', '없음 — 받은 ZIP의 빈 틀을 지우지 않습니다', [], '', True)
    head, rows, skip = csv_rows(p)
    if head != ['사례', '후보', '기대_판정', '근거']: return ('기대_판정.csv', '확인 필요', ['열 이름이 사례,후보,기대_판정,근거가 아닙니다.'], '', True)
    if not rows: return ('기대_판정.csv', '아직 비어 있음', [], '실행 전에 기대 판정을 적습니다', False)
    errs = []
    for n, r in enumerate(rows, skip + 2):
        if (r.get('기대_판정') or '').strip() not in ('유지', '제외', '보류'): errs.append(f'기대_판정.csv:{n} 기대_판정은 유지 · 제외 · 보류 가운데 하나입니다.')
        if not re.search(r'[^\s:]+:\d+', r.get('근거') or ''): errs.append(f'기대_판정.csv:{n} 근거에 파일:줄이 없습니다.')
    return ('기대_판정.csv', '확인 필요' if errs else '통과', errs, f'행 {len(rows)}개', True)
def chosen_part(root):
    errs = chosen_errors(root)
    p = root/'결과/정한_것.csv'
    if not errs and p.is_file() and not csv_rows(p)[1]: return ('정한_것.csv', '아직 비어 있음', [], '지점마다 고른 것 · 근거를 적습니다', False)
    return ('정한_것.csv', '확인 필요' if errs else '통과', errs, '', True)
def provided_part(root):
    errs = provided_errors(root)
    return ('제공 파일', '확인 필요' if errs else '통과', errs, '', True)
'''
TABLE_CHECK = r'''HEADER = ['rule_id','action','condition_index','logic','input','operator','value','unit','boundary_included','result','penalty_manwon','reason','source_section']
OPS = {'>=':'예','<=':'예','>':'아니오','<':'아니오','==':'해당없음','!=':'해당없음','has_other_than':'해당없음'}
NUMERIC = {'forecast_ts1','forecast_ps1','fan100_hours'}
TEXT = {'plc_mode': {'REMOTE_AUTO','REMOTE_MANUAL','LOCAL'}, 'plc_state': {'RUN','TRIP','STOP'}, 'skill_kind': {'control','work_order'}}
LIST_INPUTS = {'skill_code'}
INPUTS = NUMERIC | set(TEXT) | LIST_INPUTS
def check_table(path, sop_ids):
    """(상태, 오류 목록, 규칙 묶음 수, rule_id 집합). 상태: 없음 · 아직 비어 있음 · 통과 · 확인 필요."""
    if not path.is_file(): return '없음', [], 0, set()
    header, table, skip = csv_rows(path)
    if header != HEADER: return '확인 필요', [f'{path.name}:{skip + 1} 열 이름 · 순서가 계약과 다릅니다: ' + ','.join(header or [])], 0, set()
    if not table: return '아직 비어 있음', [], 0, set()
    errs, groups = [], {}
    for line, r in enumerate(table, skip + 2):
        at = f'{path.name}:{line}'
        if r['action'] not in sop_ids: errs.append(f'{at} targets.csv에 없는 action {r["action"]}')
        if r['logic'] != 'AND': errs.append(f'{at} logic은 AND입니다(OR는 다른 rule_id로 나눕니다).')
        if r['input'] not in INPUTS: errs.append(f'{at} 계약에 없는 input {r["input"]}')
        if r['operator'] not in OPS: errs.append(f'{at} 계약에 없는 operator {r["operator"]}')
        elif OPS[r['operator']] != r['boundary_included']: errs.append(f'{at} boundary_included({r["boundary_included"]})가 operator {r["operator"]}와 맞지 않습니다.')
        if r['input'] in LIST_INPUTS and r['operator'] != 'has_other_than': errs.append(f'{at} 목록 입력 {r["input"]}에는 has_other_than만 씁니다.')
        if r['operator'] == 'has_other_than' and r['input'] not in LIST_INPUTS: errs.append(f'{at} has_other_than은 목록 입력에만 씁니다.')
        if r['input'] in TEXT and r['operator'] in ('==', '!=') and r['value'] not in TEXT[r['input']]: errs.append(f'{at} {r["input"]}의 값 {r["value"]}은 계약에 없는 값입니다.')
        if r['input'] in NUMERIC:
            try: float(r['value'])
            except ValueError: errs.append(f'{at} 숫자 입력의 기준값이 숫자가 아닙니다.')
            if not r['unit']: errs.append(f'{at} 숫자 입력의 unit이 비었습니다.')
        if r['result'] not in {'WARN','PENALTY','EXCLUDE'}: errs.append(f'{at} result는 WARN · PENALTY · EXCLUDE 가운데 하나입니다.')
        if r['result'] == 'PENALTY':
            try: float(r['penalty_manwon'])
            except ValueError: errs.append(f'{at} PENALTY 행에 penalty_manwon이 없습니다.')
        elif r['penalty_manwon']: errs.append(f'{at} PENALTY가 아닌 행에 penalty_manwon이 있습니다.')
        if not r['reason'] or not r['source_section']: errs.append(f'{at} reason · source_section이 필요합니다.')
        key = (r['rule_id'], r['action']); head = (r['result'], r['penalty_manwon'], r['reason'], r['source_section'])
        g = groups.setdefault(key, {'head': head, 'index': []})
        if g['head'] != head: errs.append(f'{at} 같은 묶음 {key}의 result · penalty · reason · source가 다릅니다.')
        try: g['index'].append(int(r['condition_index']))
        except ValueError: errs.append(f'{at} condition_index가 정수가 아닙니다.')
    for key, g in groups.items():
        if sorted(g['index']) != list(range(1, len(g['index']) + 1)): errs.append(f'{path.name} 묶음 {key}: condition_index가 1부터 차례가 아닙니다: {g["index"]}')
    return ('확인 필요' if errs else '통과'), errs, len(groups), {k[0] for k in groups}
'''

PICK = r'''def pick(name):
    # 검사의 기준 입력: 결과/내_입력/에 같은 이름 파일이 있으면 그것, 없으면 제공 입력/. 고른 파일을 찍는다(조용히 바꾸지 않는다).
    mine = root/'결과/내_입력'/name
    if mine.is_file():
        print(f'기준 입력: 결과/내_입력/{name} (내 입력)')
        return mine
    if (root/'결과/내_입력').is_dir():
        print(f'기준 입력: 입력/{name} — 결과/내_입력/에 {name}이 없어 제공 입력으로 봅니다')
    else:
        print(f'기준 입력: 입력/{name}')
    return root/'입력'/name
'''


def check_head(doc):
    return f'"""{doc}\n사용: python check.py\n"""\nfrom pathlib import Path\nimport csv, io, json, re, sys\nroot = Path(__file__).resolve().parent\n'


CRITERIA_CHECK_BODY = r'''
sop_ids = [r['sop_id'] for r in read_csv(root/'자료/targets.csv')[1]]
fm_ids = {r['failure_mode_id'] for r in read_csv(root/'자료/failuremodes.csv')[1]}
graph = json.loads(pick('graph.json').read_text(encoding='utf-8-sig'))
kind_of = {n['props']['id']: n['labels'][0] for n in graph['nodes']}
SLOT = {'assets': 'Asset', 'components': 'Component', 'sensors': 'Sensor'}
RELATIONS = {'MITIGATED_BY': ('failure_modes', 'sops'), 'REMEDIED_BY': ('failure_modes', 'sops'), 'ADDRESSES': ('sops', 'causes')}
def items(value, key):
    v = value.get(key)
    return v if isinstance(v, list) else None
def check_sop(path, rule_ids):
    if not path.is_file(): return '없음', [], ''
    try: sop = json.loads(path.read_text(encoding='utf-8-sig'))
    except ValueError as e: return '확인 필요', [f'JSON 읽기 실패: {e}'], ''
    if not isinstance(sop, dict) or not sop.get('sops'): return '아직 비어 있음', [], ''
    errs, unconfirmed = [], []
    fms = [f.get('id') for f in sop.get('failure_modes') or [] if isinstance(f, dict)]
    causes = [c.get('id') for c in sop.get('causes') or [] if isinstance(c, dict)]
    for f in fms:
        if f not in fm_ids: errs.append(f'failure_modes {f}: failuremodes.csv에 없는 고장 유형 ID입니다.')
    for c in causes:
        if not isinstance(c, str) or not re.fullmatch(r'cause:[a-z0-9]+(-[a-z0-9]+)*', c): errs.append(f'causes {c}: 원인 ID는 cause:로 시작하는 영어 소문자 · 하이픈 이름입니다.')
    for name, ids in [('failure_modes', fms), ('causes', causes)]:
        for x in set(ids):
            if ids.count(x) > 1: errs.append(f'{name} {x}가 {ids.count(x)}번 있습니다.')
    found = [s.get('id') for s in sop['sops'] if isinstance(s, dict)]
    for sid in sop_ids:
        if found.count(sid) != 1: errs.append(f'{sid}가 {found.count(sid)}번 있습니다(1번이어야 합니다).')
    for s in sop['sops']:
        if not isinstance(s, dict): errs.append('sops의 항목이 객체가 아닙니다.'); continue
        sid = s.get('id')
        if sid not in sop_ids: errs.append(f'targets.csv에 없는 SOP {sid}')
        if not s.get('source'): errs.append(f'{sid}: 출처(source)가 없습니다.')
        if s.get('failure_mode') not in fms: errs.append(f'{sid}: 고장 유형 {s.get("failure_mode")}을 sop.json failure_modes에서 찾을 수 없습니다.')
        for key in ['apply_conditions', 'prohibitions', 'steps', 'completion']:
            value = items(s, key)
            if value is None: errs.append(f'{sid}: {key}는 목록이어야 합니다.'); continue
            for i, item in enumerate(value, 1):
                if not isinstance(item, dict) or not item.get('text') or not item.get('source'): errs.append(f'{sid}.{key}[{i}]: 내용(text) · 출처(source)가 필요합니다.'); continue
                for rid in item.get('rules') or []:
                    if rule_ids and rid not in rule_ids: errs.append(f'{sid}.{key}[{i}]: 조건표에 없는 규칙 {rid}')
        steps = [x.get('order') for x in items(s, 'steps') or [] if isinstance(x, dict)]
        if not steps or steps != list(range(1, len(steps) + 1)): errs.append(f'{sid}: 수행 단계(steps)의 순서가 1부터 차례가 아닙니다: {steps}')
        approval = s.get('approval')
        if not isinstance(approval, dict) or not approval.get('role') or not approval.get('source'): errs.append(f'{sid}: 승인(approval — role · source)이 필요합니다. 원문에서 승인을 찾지 못했으면 role을 「미확인」으로 시작하고 source에 찾아본 절을 적습니다.')
        elif str(approval['role']).startswith('미확인'): unconfirmed.append(sid)
        ref = s.get('model_refs')
        if not isinstance(ref, dict): errs.append(f'{sid}: 모델 참조(model_refs)는 객체여야 합니다.'); continue
        used = 0
        for slot, want in SLOT.items():
            for x in ref.get(slot) or []:
                used += 1
                if x not in kind_of: errs.append(f'{sid}: 모델에 없는 ID {x} (새 ID를 만들지 말고 not_linked에 까닭을 적습니다)')
                elif kind_of[x] != want: errs.append(f'{sid}: {slot} 자리에 {kind_of[x]} ID {x}가 있습니다.')
        if not used and not ref.get('not_linked'): errs.append(f'{sid}: 모델 참조(model_refs)가 비어 있습니다(걸 대상이 없으면 not_linked에 까닭을 적습니다).')
    ends = {'failure_modes': set(fms), 'sops': set(found), 'causes': set(causes)}
    rels = sop.get('relations')
    if not isinstance(rels, list) or not rels: errs.append('관계 목록(relations)이 비어 있습니다.')
    else:
        for i, r in enumerate(rels, 1):
            t = r.get('type') if isinstance(r, dict) else None
            if t not in RELATIONS: errs.append(f'relations[{i}]: type {t}은 계약의 셋(MITIGATED_BY · REMEDIED_BY · ADDRESSES) 가운데 하나가 아닙니다.'); continue
            a, b = RELATIONS[t]
            if r.get('from') not in ends[a]: errs.append(f'relations[{i}] {t}: 시작 {r.get("from")}이 sop.json {a}에 없습니다.')
            if r.get('to') not in ends[b]: errs.append(f'relations[{i}] {t}: 끝 {r.get("to")}이 sop.json {b}에 없습니다.')
            if not r.get('source'): errs.append(f'relations[{i}]: source가 필요합니다.')
    return ('확인 필요' if errs else '통과'), errs, f'SOP {len(found)}개 · 관계 {len(rels) if isinstance(rels, list) else 0}개' + (f' · 승인 미확인 {", ".join(unconfirmed)}' if unconfirmed else '')
t_state, t_errs, n, rule_ids = check_table(root/'결과/조건표.csv', sop_ids)
s_state, s_errs, s_note = check_sop(root/'결과/sop.json', rule_ids)
if s_state == '없음':
    print('아직 검사할 결과가 없습니다: 결과/sop.json — python show_result.py가 판단 표로 만듭니다')
print('구조 검사 결과')
ok = report([('sop.json', s_state, s_errs, s_note, True), ('조건표.csv', t_state, t_errs, f'규칙 묶음 {n}개' if n else '', True),
             chosen_part(root), expect_part(root), provided_part(root)])
ok = ok and s_state == '통과' and t_state == '통과'
print('구조 검사 통과' if ok else '구조 확인 필요 — 위 줄마다 결과 파일의 어느 항목인지 찾아 고친 뒤 다시 실행합니다.')
print('이 검사는 모양만 봅니다. 의미와 질문별 답(조건 · 경계 · 출처가 원문과 맞는지, 사건의 판정)은 원자료와 따로 대조합니다.')
sys.exit(0 if ok else 1)
'''

CONDITIONS_CHECK_BODY = r'''
sop_ids = [r['sop_id'] for r in read_csv(root/'자료/targets.csv')[1]]
def approval_part():
    p = root/'결과/승인.csv'
    if not p.is_file(): return ('승인.csv', '없음 — 받은 ZIP의 빈 틀을 지우지 않습니다', [], '', True)
    head, rows, skip = csv_rows(p)
    if head != ['sop_id', '승인_역할', '원문']: return ('승인.csv', '확인 필요', ['열 이름이 sop_id,승인_역할,원문이 아닙니다.'], '', True)
    if not rows: return ('승인.csv', '아직 비어 있음', [], '', False)
    errs = []
    for n, r in enumerate(rows, skip + 2):
        if r['sop_id'] not in sop_ids: errs.append(f'승인.csv:{n} targets.csv에 없는 SOP {r["sop_id"]}')
        if not r['승인_역할'].strip(): errs.append(f'승인.csv:{n} 승인_역할이 비었습니다(찾지 못했으면 「미확인」으로 시작).')
        if not re.fullmatch(r'\s*(자료/HM-8_매뉴얼\.md:)?\d+(\s*;\s*(자료/HM-8_매뉴얼\.md:)?\d+)*\s*', r['원문'] or ''): errs.append(f'승인.csv:{n} 원문은 자료/HM-8_매뉴얼.md의 줄 번호(45 또는 자료/HM-8_매뉴얼.md:45, ;로 나눔)입니다.')
    for s in sop_ids:
        if [r['sop_id'] for r in rows].count(s) > 1: errs.append(f'승인.csv: {s}가 두 줄 이상입니다.')
    return ('승인.csv', '확인 필요' if errs else '통과', errs, f'행 {len(rows)}개', True)
state, errs, n, _ = check_table(root/'결과/조건표.csv', sop_ids)
print('구조 검사 결과')
ok = report([('조건표.csv', state, errs, f'규칙 묶음 {n}개' if n else '', True), approval_part(), chosen_part(root), expect_part(root), provided_part(root)])
ok = ok and state == '통과'
print('구조 검사 통과' if ok else '구조 확인 필요 — 위 줄마다 결과 파일의 어느 항목인지 찾아 고친 뒤 다시 실행합니다.')
print('이 검사는 모양만 봅니다. 의미와 질문별 답(조건 · 경계 · 출처가 원문과 맞는지, 사례의 판정)은 원자료와 따로 대조합니다.')
sys.exit(0 if ok else 1)
'''

JUDGE_CHECK_COMMON = r'''
INPUTS = ['forecast_ts1', 'forecast_ps1', 'fan100_hours', 'plc_mode', 'plc_state', 'skill_kind', 'skill_code']
RANGE = {'forecast_ts1': (0, 150, '℃'), 'forecast_ps1': (50, 300, 'bar'), 'fan100_hours': (0, 1000, 'h')}
LOSS = ['cost', 'production', 'quality', 'energy', 'penalty']
def rows(path): return read_csv(path)[1]
alarms = [r['경보_ID'] for r in rows(root/'자료/경보_목록.csv') if r['구분'] == 'RAISE' and r['판정_요청_시각']]
sops = [r['sop_id'] for r in rows(root/'자료/targets.csv')]
table_path = pick('조건표.csv')
table = rows(table_path)
if not table or not {'rule_id', 'action'} <= set(table[0]):
    print(f'구조 확인 필요 — {table_path.relative_to(root).as_posix()}의 열 이름이 계약(rule_id · action …)과 다릅니다. 내 입력이면 계약과 견주어 고친 뒤 다시 실행합니다.')
    sys.exit(1)
groups = {(r['rule_id'], r['action']) for r in table}
def num(x): return isinstance(x, (int, float)) and not isinstance(x, bool)
def inputs_errors(at, inputs, reasons):
    out = []
    for k in INPUTS:
        if k not in inputs: out.append(f'{at}: 입력에 {k}가 없습니다(값이 없으면 null).')
        elif inputs[k] is None and not (reasons or {}).get(k): out.append(f'{at}: {k}가 null인데 왜 없는지가 없습니다.')
    for k, (lo, hi, unit) in RANGE.items():
        v = inputs.get(k)
        if num(v) and not lo <= v <= hi: out.append(f'{at}: {k}={v}는 계약 단위 {unit}의 범위({lo} ~ {hi})를 벗어납니다. 원천의 단위를 확인합니다.')
    return out
def total_errors(at, value):
    if not isinstance(value, dict) or not all(num(value.get(k)) for k in LOSS + ['total']): return [f'{at}: 비교값(comparison)에 {LOSS + ["total"]}가 숫자로 있어야 합니다.']
    if abs(sum(value[k] for k in LOSS) - value['total']) > 0.03: return [f'{at}: 합계 total {value["total"]}가 네 손실과 감점의 합 {sum(value[k] for k in LOSS):.2f}와 다릅니다.']
    return []
def rank_errors(at, ranked):
    """ranked = [(sop, 순위, 합계)] — 합계 오름차순과 같은 합계 같은 순위(1, 1, 3)."""
    out, ranked = [], sorted(ranked, key=lambda x: (x[1] if num(x[1]) else 9e9))
    totals = [t for _, _, t in ranked]
    if totals != sorted(totals): out.append(f'{at}: 순위가 합계가 작은 순서가 아닙니다.')
    for i, (s, r, t) in enumerate(ranked):
        want = ranked[i - 1][1] if i and ranked[i - 1][2] == t else i + 1
        if r != want: out.append(f'{at}: {s}의 순위 {r} — 같은 합계는 같은 순위, 다음은 그 수만큼 건너뜁니다(1, 1, 3).')
    return out
def kept_errors(at, status, value, note):
    """비교값은 유지 후보에만, 비교값이 없는 유지 후보에는 까닭."""
    if status != '유지':
        return [f'{at}: 유지가 아닌 후보({status})에 비교값이 있습니다.'] if value is not None else []
    if value is None:
        return [] if note else [f'{at}: 유지 후보에 비교값이 없으면 no_comparison_reason에 까닭이 필요합니다.']
    return total_errors(at, value)
def decisions_errors(value):
    if not isinstance(value, list) or not value or any(not (isinstance(d, dict) and d.get('item') and d.get('decision') and d.get('basis')) for d in value):
        return ['decisions(item · decision · basis — 판단 입력을 만든 방법 · 견주는 후보 등 정한 것)가 필요합니다.']
    return []
'''

JUDGE_CHECK_BODY = r'''
def hit_errors(at, sop, hits, penalty=False):
    out = []
    if not isinstance(hits, list): return [f'{at}: 맞은 규칙은 목록입니다.']
    for h in hits:
        if (h.get('rule_id'), sop) not in groups: out.append(f'{at}: 기준 조건표에 없는 규칙 · 후보 {h.get("rule_id")}')
        if not h.get('source_section') or not isinstance(h.get('conditions'), list) or not h['conditions']: out.append(f'{at} {h.get("rule_id")}: source_section과 conditions(조건마다 실제 값)가 필요합니다.')
        if penalty and not num(h.get('penalty_manwon')): out.append(f'{at} {h.get("rule_id")}: penalty_manwon이 숫자로 필요합니다.')
    return out
def check_result(path):
    if not path.is_file(): return '없음', [], ''
    try: result = json.loads(path.read_text(encoding='utf-8-sig'))
    except ValueError as e: return '확인 필요', [f'JSON 읽기 실패: {e}'], ''
    errs = []
    if not str(result.get('comparison_basis', '')).strip(): errs.append('comparison_basis(비교 합계와 포털 성과 지표 점수의 구분 문장)가 없습니다.')
    errs += decisions_errors(result.get('decisions'))
    events = result.get('events')
    if not isinstance(events, list): return '확인 필요', errs + ['events 목록이 없습니다.'], ''
    got = [e.get('id') for e in events if isinstance(e, dict)]
    if got != alarms: errs.append(f'events: 경보_목록.csv의 RAISE 행과 사례 · 순서가 다릅니다(빠짐 {sorted(set(alarms) - set(got))}, 더함 {sorted(set(got) - set(alarms))}).')
    for e in events:
        eid = e.get('id'); cands = e.get('candidates') or []
        if [c.get('sop') for c in cands] != sops: errs.append(f'{eid}: 후보 목록 · 순서가 targets.csv와 다릅니다.')
        totals = {}
        for c in cands:
            at = f'{eid}/{c.get("sop")}'
            errs += inputs_errors(at, c.get('inputs') or {}, c.get('missing_reasons'))
            st = c.get('status')
            if st not in ('유지', '제외', '보류'): errs.append(f'{at}: status는 유지 · 제외 · 보류 가운데 하나입니다.'); continue
            errs += hit_errors(at, c.get('sop'), c.get('warnings')) + hit_errors(at, c.get('sop'), c.get('exclusions')) + hit_errors(at, c.get('sop'), c.get('penalties'), True)
            unknown = c.get('unknown') if isinstance(c.get('unknown'), list) else []
            for u in unknown:
                if (u.get('rule_id'), c.get('sop')) not in groups: errs.append(f'{at}: 기준 조건표에 없는 규칙 · 후보 {u.get("rule_id")}')
                if not u.get('missing'): errs.append(f'{at} {u.get("rule_id")}: unknown에는 빠진 입력 이름(missing)이 필요합니다.')
            ex = c.get('exclusions') or []
            want = '제외' if ex else ('보류' if unknown else '유지')
            if st != want: errs.append(f'{at}: status {st} — 제외 사유 {len(ex)}개 · 알 수 없는 규칙 {len(unknown)}개와 맞지 않습니다(뜻은 작업기준.md 4절).')
            comp = c.get('comparison')
            errs += kept_errors(at, st, comp, c.get('no_comparison_reason'))
            if st == '유지' and isinstance(comp, dict):
                totals[c.get('sop')] = comp.get('total')
                pen = sum(p.get('penalty_manwon', 0) for p in c.get('penalties') or [] if num(p.get('penalty_manwon')))
                if num(comp.get('penalty')) and abs(pen - comp['penalty']) > 0.001: errs.append(f'{at}: 감점 {comp["penalty"]}이 penalties 금액의 합 {pen}과 다릅니다.')
        ranking = e.get('ranking')
        if not isinstance(ranking, list): errs.append(f'{eid}: ranking 목록이 필요합니다.'); continue
        if sorted(r.get('sop') for r in ranking) != sorted(totals): errs.append(f'{eid}: ranking에는 비교값이 있는 후보가 모두 한 번씩 있어야 합니다(지금 {sorted(r.get("sop") for r in ranking)}, 비교값 있음 {sorted(totals)}).')
        for r in ranking:
            if r.get('total') != totals.get(r.get('sop')): errs.append(f'{eid}: ranking의 {r.get("sop")} total이 그 후보의 비교값과 다릅니다.')
        errs += rank_errors(eid, [(r.get('sop'), r.get('rank'), r.get('total')) for r in ranking])
        sel = e.get('selection') or {}
        if not sel.get('reason'): errs.append(f'{eid}: selection.reason(1위를 고른 까닭 또는 순위가 없는 까닭)이 필요합니다.')
        if not isinstance(sel.get('checks'), list): errs.append(f'{eid}: selection.checks 목록이 필요합니다(없으면 빈 목록).')
    return ('확인 필요' if errs else '통과'), errs, f'사례 {len(events)}건'
state, errs, note = check_result(root/'결과/result.json')
if state == '없음': print('아직 검사할 결과가 없습니다: 결과/result.json — python show_result.py가 정할 자리를 채운 단계까지 만듭니다')
print('구조 검사 결과')
ok = report([('result.json', state, errs, note, True), chosen_part(root), expect_part(root), provided_part(root)]) and state == '통과'
print('구조 검사 통과' if ok else '구조 확인 필요 — 위 줄마다 결과의 어느 사례 · 후보인지 찾아 고친 뒤 다시 실행합니다.')
print('이 검사는 모양과 계약만 봅니다. 의미와 질문별 답(어떤 규칙이 맞아야 하는지, 금액, 어느 후보가 1위인지)은 원자료와 따로 대조합니다.')
sys.exit(0 if ok else 1)
'''

REVIEW_CHECK_BODY = r'''
sop_doc = json.loads(pick('sop.json').read_text(encoding='utf-8-sig'))
approver = {s['id']: (s.get('approval') or {}).get('role') for s in sop_doc.get('sops', [])}
def check_review(jpath, mpath):
    if not jpath.is_file(): return '없음', [], ''
    try: rv = json.loads(jpath.read_text(encoding='utf-8-sig'))
    except ValueError as e: return '확인 필요', [f'JSON 읽기 실패: {e}'], ''
    md = mpath.read_text(encoding='utf-8-sig') if mpath.is_file() else ''
    errs = [] if md else ['조치검토결과.md가 없습니다.']
    if not str(rv.get('comparison_basis', '')).strip(): errs.append('comparison_basis(비교 합계와 포털 성과 지표 점수 · 실행 승인의 구분 문장)가 없습니다.')
    errs += decisions_errors(rv.get('decisions'))
    events = rv.get('events')
    if not isinstance(events, list): return '확인 필요', errs + ['events 목록이 없습니다.'], ''
    got = [i.get('id') for i in events if isinstance(i, dict)]
    if got != alarms: errs.append(f'events: 경보_목록.csv의 RAISE 행과 사례 · 순서가 다릅니다(빠짐 {sorted(set(alarms) - set(got))}, 더함 {sorted(set(got) - set(alarms))}).')
    for it in events:
        iid = it.get('id'); cands = it.get('candidates') or []
        if md and not re.search(r'^#+\s.*(?<![A-Za-z0-9-])' + re.escape(str(iid)) + r'(?![A-Za-z0-9-])', md, re.M): errs.append(f'조치검토결과.md에 {iid}의 절 제목이 없습니다.')
        if [c.get('sop') for c in cands] != sops: errs.append(f'{iid}: 후보 목록 · 순서가 targets.csv와 다릅니다.')
        totals, ranked = {}, []
        for c in cands:
            at = f'{iid}/{c.get("sop")}'
            st = c.get('status')
            reasons = c.get('reasons') if isinstance(c.get('reasons'), list) else None
            errs += inputs_errors(at, c.get('inputs') or {}, c.get('missing_reasons'))
            if st not in ('유지', '제외', '보류'): errs.append(f'{at}: status는 유지 · 제외 · 보류 가운데 하나입니다.'); continue
            if reasons is None: errs.append(f'{at}: 이유 목록(reasons)이 필요합니다.'); continue
            for r in reasons:
                if (r.get('rule_id'), c.get('sop')) not in groups: errs.append(f'{at}: 기준 조건표에 없는 규칙 · 후보 {r.get("rule_id")}')
                if r.get('result') not in ('WARN', 'PENALTY', 'EXCLUDE', '미확인'): errs.append(f'{at} {r.get("rule_id")}: result는 WARN · PENALTY · EXCLUDE · 미확인 가운데 하나입니다.')
                if not r.get('expression') or not r.get('source') or not isinstance(r.get('actual_inputs'), dict): errs.append(f'{at} {r.get("rule_id")}: actual_inputs · expression · source가 필요합니다.')
                if r.get('result') == '미확인' and (not r.get('missing_inputs') or not r.get('missing_reason')): errs.append(f'{at} {r.get("rule_id")}: 미확인에는 missing_inputs와 missing_reason이 필요합니다.')
            kinds = [r.get('result') for r in reasons]
            want = '제외' if 'EXCLUDE' in kinds else ('보류' if '미확인' in kinds else '유지')
            if st != want: errs.append(f'{at}: 판정 {st}이 이유의 결과({", ".join(kinds) or "없음"})와 맞지 않습니다(뜻은 작업기준.md 4절).')
            if not c.get('sources'): errs.append(f'{at}: 원문 출처(sources)가 비었습니다.')
            checks = c.get('checks')
            if not isinstance(checks, list): errs.append(f'{at}: 추가로 확인할 값(checks) 목록이 필요합니다.'); checks = []
            for m in sorted({m for r in reasons if r.get('result') == '미확인' for m in r.get('missing_inputs') or []}):
                if not any(m in str(x) for x in checks): errs.append(f'{at}: 미확인 규칙의 빠진 입력 {m}이 추가로 확인할 값(checks)에 없습니다.')
            ap = c.get('approval') or {}
            if not ap.get('role') or not ap.get('source') or not ap.get('note'): errs.append(f'{at}: 승인(approval — role · source · note)이 필요합니다.')
            elif ap.get('role') != approver.get(c.get('sop')): errs.append(f'{at}: 승인 역할 {ap.get("role")}이 기준 sop.json의 {approver.get(c.get("sop"))}과 다릅니다.')
            value, rank = c.get('comparison'), c.get('rank')
            errs += kept_errors(at, st, value, c.get('no_comparison_reason'))
            if value is None and rank is not None: errs.append(f'{at}: 비교값이 없는 후보에 순위(rank)가 있습니다.')
            if st == '유지' and isinstance(value, dict):
                totals[c.get('sop')] = value.get('total'); ranked.append((c.get('sop'), rank, value.get('total')))
        errs += rank_errors(iid, ranked)
        op = it.get('review') or {}
        top = op.get('top') if isinstance(op.get('top'), list) else None
        if top is None: errs.append(f'{iid}: review.top 목록이 필요합니다(1위가 없으면 빈 목록).'); top = []
        for s in top:
            if s not in totals: errs.append(f'{iid}: review.top의 {s}는 비교값이 있는 유지 후보가 아닙니다.')
        if not op.get('reason'): errs.append(f'{iid}: review.reason이 필요합니다.')
        if not isinstance(op.get('checks'), list): errs.append(f'{iid}: review.checks 목록이 필요합니다(없으면 빈 목록).')
    return ('확인 필요' if errs else '통과'), errs, f'사례 {len(events)}건'
state, errs, note = check_review(root/'결과/조치검토결과.json', root/'결과/조치검토결과.md')
if state == '없음': print('아직 검사할 결과가 없습니다: 결과/조치검토결과.json — python show_result.py가 정할 자리를 채운 단계까지 만듭니다')
print('구조 검사 결과')
ok = report([('조치검토결과.json · .md', state, errs, note, True), chosen_part(root), expect_part(root), provided_part(root)]) and state == '통과'
print('구조 검사 통과' if ok else '구조 확인 필요 — 위 줄마다 결과의 어느 사례 · 후보인지 찾아 고친 뒤 다시 실행합니다.')
print('이 검사는 모양과 계약만 봅니다. 의미와 질문별 답(판정 · 이유 · 출처가 원문과 맞는지, 금액, 어느 후보가 1위인지)은 원자료와 따로 대조합니다.')
sys.exit(0 if ok else 1)
'''

CHECKS = {
    'integrated-03-criteria': ('결과/sop.json · 조건표.csv의 구조 검사와 정한 것 · 기대 판정 · 제공 파일 확인. 생성 · 수정 · 네트워크 접속을 하지 않는다.\n'
                               '의미(조건 · 경계 · 출처가 원문과 맞는지, 사건의 판정)는 판정하지 않는다 — 원자료와 따로 대조한다. 모델 ID는 결과/내_입력/graph.json이 있으면 그것으로 본다.',
                               [TABLE_CHECK, PICK, CRITERIA_CHECK_BODY]),
    'practical-02-conditions': ('결과/조건표.csv · 승인.csv의 구조 검사와 정한 것 · 기대 판정 · 제공 파일 확인. 생성 · 수정 · 네트워크 접속을 하지 않는다.\n'
                                '의미(조건 · 경계 · 출처가 원문과 맞는지, 사례의 판정)는 판정하지 않는다 — 원자료와 따로 대조한다.',
                                [TABLE_CHECK, CONDITIONS_CHECK_BODY]),
    'integrated-03-judge': ('결과/result.json의 구조와 계약 검사, 정한 것 · 기대 판정 · 제공 파일 확인. 생성 · 수정 · 네트워크 접속을 하지 않는다.\n'
                            '어떤 규칙이 맞아야 하는지, 금액이 맞는지, 어느 후보가 1위여야 하는지는 판정하지 않는다. 규칙 ID는 결과/내_입력/조건표.csv가 있으면 그것으로 본다.',
                            [PICK, JUDGE_CHECK_COMMON, JUDGE_CHECK_BODY]),
    'practical-03-review': ('결과/조치검토결과.json · .md의 구조와 계약 검사, 정한 것 · 기대 판정 · 제공 파일 확인. 생성 · 수정 · 네트워크 접속을 하지 않는다.\n'
                            '판정 · 이유 · 출처가 원문 · 원천과 맞는지, 금액, 1위는 판정하지 않는다. 규칙 ID · 승인 역할은 결과/내_입력/의 파일이 있으면 그것으로 본다.',
                            [PICK, JUDGE_CHECK_COMMON, REVIEW_CHECK_BODY]),
}


def check_source(key, folder):
    doc, parts = CHECKS[key]
    names = sorted(['show_result.py', 'lab_steps.py', *PROVIDED[key]])
    return check_head(doc) + READ_CSV + F.CHOSEN_CHECK + F.provided_guard(folder, names) + ''.join(parts)


# ───────────── 결과 화면 단계(lab_steps.py) ─────────────
STEPS_HEAD = '''"""{title} — 결과 화면의 단계(제공 — 고치지 않는다). python show_result.py가 이 파일의 STEPS를 차례로 돌린다.
단계마다 정할 자리(slots)가 채워졌으면 제공 코드를 돌려 그 단계의 결과를 표 · 대조 · 개수로 돌려준다. 판단의 답은 이 파일에 없다.
"""
from pathlib import Path
import csv
import io
import subprocess
import sys

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from show_result import compare, counts, error, note, read_table, table  # noqa: E402
import condition_tools as C  # noqa: E402

TITLE = {title!r}
NAMES = {names!r}


def guarded(fn):
    """제공 코드가 알린 멈춤(정할 자리 비어 있음 · 계약 어긋남)을 빨간 칸으로 — 파일 · 줄과 까닭 그대로."""
    def run(previous):
        try:
            return fn(previous)
        except (C.ContractError, *EXTRA_STOP) as e:
            return [error('멈춤', str(e))]
    return run


EXPECT_COLUMNS = {expect_columns!r}


def expected_rows():
    """결과/기대_판정.csv → 표 줄. 꼴이 계약과 다르면 파일:줄을 대고 멈춘다(맞지 않는 줄을 「실제 없음」으로 조용히 두지 않음)."""
    p = HERE/'결과/기대_판정.csv'
    if not p.is_file():
        return []
    body, skip = C.csv_body(p)
    reader = csv.DictReader(io.StringIO(body, newline=''))
    if reader.fieldnames != EXPECT_COLUMNS:
        raise C.ContractError(f'결과/기대_판정.csv:{{skip + 1}} 열 이름이 {{",".join(EXPECT_COLUMNS)}}가 아님')
    cases, sops = case_ids(), [r['sop_id'] for r in C.read_csv(HERE/'자료/targets.csv')]
    out, seen = [], {{}}
    for line, r in enumerate(reader, start=skip + 2):
        where = f'결과/기대_판정.csv:{{line}}'
        if None in r or any(v is None for v in r.values()):
            raise C.ContractError(f'{{where}} 칸 수가 열 이름과 다릅니다 — 쉼표가 빠졌거나 더 있는지 봅니다(쉼표가 든 글은 큰따옴표로 감쌉니다).')
        if not any(v.strip() for v in r.values()):
            continue
        c, s, v = r['사례'].strip(), r['후보'].strip(), r['기대_판정'].strip()
        if c not in cases:
            raise C.ContractError(f'{{where}} 사례 「{{c}}」 — 사례 칸은 {{CASE_FROM}}')
        if s not in sops:
            raise C.ContractError(f'{{where}} 후보 「{{s}}」 — 후보 칸은 자료/targets.csv의 SOP ID({{" · ".join(sops)}})')
        if v not in ('유지', '제외', '보류'):
            raise C.ContractError(f'{{where}} 기대_판정 「{{v}}」 — 유지 · 제외 · 보류 가운데 하나')
        if (c, s) in seen:
            raise C.ContractError(f'{{where}} {{c}} / {{s}} 줄이 {{seen[(c, s)]}}줄에도 있습니다 — 사례 · 후보마다 한 줄')
        seen[(c, s)] = line
        out.append({{'사례 / 후보': f'{{c}} / {{s}}', '판정': v, '근거': r['근거'].strip()}})
    return out


def against_expected(title, judged):
    """judged = {{(사례, 후보): 판정}} — 기대_판정.csv에 적은 줄만 견준다."""
    exp = expected_rows()
    keys = {{e['사례 / 후보'] for e in exp}}
    act = [{{'사례 / 후보': f'{{c}} / {{s}}', '판정': v}} for (c, s), v in judged.items() if f'{{c}} / {{s}}' in keys]
    return compare(title, '사례 / 후보', exp, act, ['판정'], '기대는 실행 전에 손으로 적은 값입니다. 다른 줄은 기대 · 조건표 · 원문 가운데 어느 쪽이 원문과 다른지 찾아 고칩니다.')


def run_check(previous):
    p = subprocess.run([sys.executable, 'check.py'], cwd=HERE, capture_output=True, text=True, encoding='utf-8')
    lines = [[x] for x in (p.stdout + p.stderr).splitlines()]
    return [note('구조 검사 통과' if p.returncode == 0 else '구조 확인 필요 — 아래 줄마다 결과 파일의 어느 항목인지 찾아 고친 뒤 다시 실행합니다(앞 단계를 아직 채우는 중이면 그 단계의 자리가 짚힙니다).'),
            table('python check.py 출력', ['줄'], lines)]


def step(no, slots=(), run=None):
    return dict(no=no, name=NAMES[no - 1], slots=list(slots), run=guarded(run) if run else None)


def expected_view(previous):
    exp = expected_rows()
    return [table('기대 판정(실행 전에 적은 값)과 근거 줄', ['사례 / 후보', '판정', '근거'], exp)]
'''

CASES_SOURCE = '''
CASE_FROM = {case_from!r}


def case_ids():
    return {{r['사례'] for r in C.read_csv(HERE/'자료/확인_사례.csv')}}
'''

CRITERIA_STEPS = CASES_SOURCE + '''
import sop_tools as S  # noqa: E402
EXTRA_STOP = (S.Unfilled,)
CANDIDATES = ['SOP-COOL-11', 'SOP-COOL-12', 'SOP-COOL-13', 'SOP-COOL-14']


def overview(previous):
    sents = C.sentences(HERE)
    return [counts('받은 자료', [('매뉴얼 원문 문장', len(sents)), ('판단 시스템 결정표 규칙', len(C.export_rules(HERE/'자료/판단시스템_결정표_내보내기.txt'))),
                                ('확인 사례', len(C.case_inputs(HERE/'자료/확인_사례.csv', {{}}))), ('냉각 계통 SOP', len(C.read_csv(HERE/'자료/targets.csv')))]),
            table('매뉴얼 원문 문장 — 판단 표의 「원문」 칸에 쓰는 번호', ['원문', '절', 'SOP', '단계', '글'], sents)]


def facts(previous):
    return [table('판단 시스템 결정표 규칙 — 출처 칸의 절이 받은 원문에 있는가(사실만)', ['줄', 'id', '조건식', '결과', '대상', '출처', '출처_절'], C.export_facts(HERE))]


def built():
    doc, todo, missing = S.build(HERE)
    return doc, todo, missing


def classify(previous):
    doc, todo, _ = built()
    rows = []
    for s in doc['sops']:
        for key, name in (('apply_conditions', '적용'), ('prohibitions', '금지 · 제한'), ('completion', '완료')):
            for it in s[key]:
                rows.append([s['id'], it.get('type', name), it['text'], it['source'], ' · '.join(it['rules'])])
        rows.append([s['id'], '승인', s['approval']['role'], s['approval']['source'], ''])
        rows.append([s['id'], '종류 · 코드', f"{{s['kind']}} {{' · '.join(s['codes'])}}" if s['kind'] else '없음', '', ''])
    out = [counts('SOP 구조', [('SOP', len(doc['sops'])), ('적용 조건', sum(len(s['apply_conditions']) for s in doc['sops'])),
                              ('금지 · 제한', sum(len(s['prohibitions']) for s in doc['sops'])), ('완료 기준', sum(len(s['completion']) for s in doc['sops'])),
                              ('승인 미확인', sum(1 for s in doc['sops'] if s['approval']['role'].startswith('미확인')))]),
           table('결과/sop.json — 칸마다 원문 인용과 출처', ['SOP', '칸', '글(원문 인용)', '출처', '규칙'], rows)]
    left = [t for t in todo if '관계' not in t and '설비_연결' not in t]
    return out + ([error('아직 채우지 않은 곳', '\\n'.join(left))] if left else [])


def relations(previous):
    doc, todo, _ = built()
    rel_errors = [t for t in todo if t.startswith('관계.csv')]
    out = [table('관계 — 고장 유형 · 조치 · 원인', ['type', 'from', 'to', '출처'], [[r['type'], r['from'], r['to'], r['source']] for r in doc['relations']]),
           table('원인', ['id', '이름', '출처'], [[c['id'], c['name'], c['source']] for c in doc['causes']])]
    ends = {{f['id'] for f in doc['failure_modes']}} | {{c['id'] for c in doc['causes']}} | {{s['id'] for s in doc['sops']}}
    bad = [f"{{r['type']}} {{r['from']}} → {{r['to']}}" for r in doc['relations'] if r['from'] not in ends or r['to'] not in ends]
    return out + ([error('양 끝이 sop.json에 없는 관계', '\\n'.join(bad))] if bad else []) + ([error('관계.csv를 읽지 못한 줄', '\\n'.join(rel_errors))] if rel_errors else [])


def models(previous):
    doc, todo, missing = built()
    assets = sorted({{a for s in doc['sops'] for a in s['model_refs']['assets']}})
    rows = [[s['id'], ' · '.join(s['model_refs']['assets']), ' · '.join(s['model_refs']['components']), ' · '.join(s['model_refs']['sensors']), s['model_refs']['not_linked']] for s in doc['sops']]
    per = [[a, ' · '.join(s['id'] for s in doc['sops'] if a in s['model_refs']['assets'])] for a in assets]
    out = [table('SOP마다 모델 참조', ['SOP', '설비', '구성 요소', '센서', '걸지 않은 대상과 까닭'], rows), table('설비마다 걸린 SOP', ['설비', 'SOP'], per)]
    return out + ([error('모델에서 찾지 못한 ID(걸지 않음)', '\\n'.join(missing))] if missing else [])


def kinds(doc):
    by = {{s['id']: s for s in doc['sops']}}
    return {{c: (by[c]['kind'], by[c]['codes']) if c in by else (None, []) for c in CANDIDATES}}


def judged_cases(doc):
    groups = C.load_table(HERE/'결과/조건표.csv')
    k = kinds(doc)
    memo = C.memo_inputs((HERE/'자료/사건_기록_HYD-02_1027.md').read_text(encoding='utf-8'), k)
    cases = C.case_inputs(HERE/'자료/확인_사례.csv', k)
    incident = next(cid for cid in cases if cid in (HERE/'자료/사건_기록_HYD-02_1027.md').read_text(encoding='utf-8'))
    out = {{(incident, s): C.evaluate(s, x, groups) for s, x in memo.items()}}
    out.update({{(cid, s): C.evaluate(s, x, groups) for cid, cs in cases.items() if cid != incident for s, x in cs.items()}})
    return out, incident


def rules(previous):
    doc, _, _ = built()
    j, incident = judged_cases(doc)                     # 조건표 꼴 검사(파일:줄)가 출처 대조보다 먼저
    trace, miss = S.trace(HERE)
    rows = [r for r in trace if r['항목'].startswith('조건표')]
    inc = [[s, C.short(v)] for (c, s), v in j.items() if c == incident]
    return [table('조건표 규칙 — 출처 칸의 원문', ['항목', '내용', '출처 조각', '원문 줄', '원문'], rows),
            table('사건 네 후보(사건 메모의 값을 조건표에 댄 결과)', ['후보', '판정'], inc),
            against_expected('기대 판정 ↔ 조건표를 댄 판정', {{k: v['status'] for k, v in j.items()}})]


def sources(previous):
    doc, _, _ = built()
    j, _ = judged_cases(doc)
    mine = {{x for r in C.read_csv(HERE/'결과/조건표.csv') for x in C.RULE_REF.findall(r['source_section'])}}
    fx = [dict(r, 내_조건표='출처로 듦' if r['id'] in mine else '—') for r in C.export_facts(HERE)]
    trace, miss = S.trace(HERE)
    st = [v['status'] for v in j.values()]
    return [counts('확인 사례 판정(사건 포함, 후보마다)', [('유지', st.count('유지')), ('제외', st.count('제외')), ('보류', st.count('보류'))],
                   '직전 실행과 견줘 바뀐 개수가 이번 결정으로 바뀐 판정입니다.'),
            table('사례 · 후보마다 판정', ['사례', '후보', '판정'], [[c, s, C.short(v)] for (c, s), v in j.items()]),
            table('판단 시스템 결정표 규칙과 내 조건표', ['줄', 'id', '결과', '대상', '출처', '출처_절', '내_조건표'], fx),
            against_expected('기대 판정 ↔ 조건표를 댄 판정', {{k: v['status'] for k, v in j.items()}}),
            table('출처 대조 — 원문에서 찾지 못한 출처 조각', ['조각'], [[m] for m in miss])]


STEPS = [step(1, run=overview), step(2, run=facts), step(3, ['결과/기대_판정.csv'], expected_view), step(4),
         step(5, ['결과/조건_분류.csv'], classify), step(6, ['결과/관계.csv'], relations), step(7, ['결과/설비_연결_기준.csv'], models),
         step(8, ['결과/조건표.csv'], rules), step(9, run=sources), step(10, run=run_check)]
'''

CONDITIONS_STEPS = CASES_SOURCE + '''
EXTRA_STOP = ()


def targets():
    return {{r['sop_id']: (r['kind'], [x for x in r['codes'].split(';') if x]) for r in C.read_csv(HERE/'자료/targets.csv')}}


def overview(previous):
    return [counts('받은 자료', [('매뉴얼 원문 문장', len(C.sentences(HERE))), ('판단 시스템 결정표 규칙', len(C.export_rules(HERE/'자료/판단시스템_결정표_내보내기.txt'))),
                                ('확인 사례', len(C.case_inputs(HERE/'자료/확인_사례.csv', {{}}))), ('후보', len(targets()))]),
            table('매뉴얼 원문 문장', ['원문', '절', 'SOP', '단계', '글'], C.sentences(HERE))]


def facts(previous):
    return [table('판단 시스템 결정표 규칙 — 출처 칸의 절이 받은 원문에 있는가(사실만)', ['줄', 'id', '조건식', '결과', '대상', '출처', '출처_절'], C.export_facts(HERE))]


def judged():
    groups = C.load_table(HERE/'결과/조건표.csv')
    t = targets()
    memo_text = (HERE/'자료/사건_기록_HYD-02_1027.md').read_text(encoding='utf-8')
    cases = C.case_inputs(HERE/'자료/확인_사례.csv', t)
    incident = next(cid for cid in cases if cid in memo_text)
    out = {{(incident, s): C.evaluate(s, x, groups) for s, x in C.memo_inputs(memo_text, t).items()}}
    out.update({{(cid, s): C.evaluate(s, x, groups) for cid, cs in cases.items() if cid != incident for s, x in cs.items()}})
    return out


def rules(previous):
    j = judged()                                        # 조건표 꼴 검사(파일:줄)가 출처 표보다 먼저
    seen, rows = set(), []
    for r in C.read_csv(HERE/'결과/조건표.csv'):
        if (r['rule_id'], r['action']) in seen:
            continue
        seen.add((r['rule_id'], r['action']))
        for part, no, text in C.source_parts(HERE, r['source_section']):
            rows.append([r['rule_id'], r['action'], r['result'], part, no or '—', text])
    return [table('조건표 규칙 — 출처 칸의 원문', ['규칙', '후보', '결과', '출처 조각', '원문 줄', '원문'], rows),
            table('사건 · 확인 사례 — 후보마다 맞은 규칙과 알 수 없는 규칙', ['사례', '후보', '판정'], [[c, s, C.short(v)] for (c, s), v in j.items()]),
            against_expected('기대 판정 ↔ 조건표를 댄 판정', {{k: v['status'] for k, v in j.items()}})]


def sources(previous):
    j = judged()
    mine = {{x for r in C.read_csv(HERE/'결과/조건표.csv') for x in C.RULE_REF.findall(r['source_section'])}}
    st = [v['status'] for v in j.values()]
    return [counts('사건 · 확인 사례 판정(후보마다)', [('유지', st.count('유지')), ('제외', st.count('제외')), ('보류', st.count('보류'))],
                   '직전 실행과 견줘 바뀐 개수가 이번 결정으로 바뀐 판정입니다.'),
            table('판단 시스템 결정표 규칙과 내 조건표', ['줄', 'id', '결과', '대상', '출처', '출처_절', '내_조건표'],
                  [dict(r, 내_조건표='출처로 듦' if r['id'] in mine else '—') for r in C.export_facts(HERE)]),
            table('사건 · 확인 사례 판정', ['사례', '후보', '판정'], [[c, s, C.short(v)] for (c, s), v in j.items()])]


APPROVAL_COLUMNS = {approval_columns!r}


def approval_rows():
    """결과/승인.csv → {{후보: 행}}. 꼴이 계약과 다르면 파일:줄을 대고 멈춘다."""
    p = HERE/'결과/승인.csv'
    body, skip = C.csv_body(p)
    reader = csv.DictReader(io.StringIO(body, newline=''))
    if reader.fieldnames != APPROVAL_COLUMNS:
        raise C.ContractError(f'결과/승인.csv:{{skip + 1}} 열 이름이 {{",".join(APPROVAL_COLUMNS)}}가 아님')
    lines, sops, by = C.manual_lines(HERE), [r['sop_id'] for r in C.read_csv(HERE/'자료/targets.csv')], {{}}
    for line, r in enumerate(reader, start=skip + 2):
        where = f'결과/승인.csv:{{line}}'
        if None in r or any(v is None for v in r.values()):
            raise C.ContractError(f'{{where}} 칸 수가 열 이름과 다릅니다 — 쉼표가 빠졌거나 더 있는지 봅니다(쉼표가 든 글은 큰따옴표로 감쌉니다).')
        if not any(v.strip() for v in r.values()):
            continue
        s = r['sop_id'].strip()
        if s not in sops:
            raise C.ContractError(f'{{where}} sop_id 「{{s}}」 — 자료/targets.csv의 SOP ID({{" · ".join(sops)}})')
        if s in by:
            raise C.ContractError(f'{{where}} {{s}} 줄이 두 번째입니다 — 후보마다 한 줄')
        for n in [x.strip() for x in r['원문'].split(';') if x.strip()]:
            no = n.rsplit(':', 1)[-1]
            if not no.isdigit() or int(no) not in lines:
                raise C.ContractError(f'{{where}} 원문 「{{n}}」 — 자료/HM-8_매뉴얼.md의 줄 번호(68 또는 자료/HM-8_매뉴얼.md:68, 여러 개는 ;)')
        by[s] = r
    return by


def approvals(previous):
    lines = C.manual_lines(HERE)
    by = approval_rows()
    out = []
    for (c, s), v in judged().items():
        if v['status'] == '제외':
            continue
        r = by.get(s)
        nums = [int(n.strip().rsplit(':', 1)[-1]) for n in (r['원문'].split(';') if r else []) if n.strip().rsplit(':', 1)[-1].isdigit()]
        quote = ' / '.join(lines[n][3] for n in nums if n in lines)
        out.append([c, s + (' (보류: ' + ', '.join(m for u in v['unknown'] for m in u['missing']) + ' 빠짐)' if v['status'] == '보류' else ''),
                    r['승인_역할'] if r else '— 승인.csv에 없음', quote])
    return [table('남은 후보와 실행 승인 — 후보가 남은 것은 실행 허가가 아니다', ['사례', '남은 후보', '승인 역할', '원문 승인 줄'], out)]


STEPS = [step(1, run=overview), step(2, run=facts), step(3, ['결과/기대_판정.csv'], expected_view), step(4),
         step(5, ['결과/조건표.csv'], rules), step(6, run=sources), step(7, ['결과/승인.csv'], approvals), step(8, run=run_check)]
'''

JUDGE_STEPS = '''
import judge_tools as T  # noqa: E402
EXTRA_STOP = (T.Unfilled,)
CASE_FROM = {case_from!r}


def case_ids():
    return {{r['경보_ID'] for r in C.read_csv(HERE/'자료/경보_목록.csv') if r['구분'] == 'RAISE'}}


def num(x):
    """화면 표시용 수 — 원천 값은 소수 한두 자리라 계산 값(16.717499999999998)도 소수 둘째 자리로 둥글린다. 판정 · 결과 파일은 원값 그대로."""
    return round(x, 2) if isinstance(x, float) else x


REVIEW = {review!r}


def overview(previous):
    return [table('경보마다 판정 요청 직전 원천 기록(사실만 — 판정 없음)', ['경보', '설비', '판정 요청(UTC)', 'PLC 마지막 수신', '카운터 마지막 기록', '예측 행'], T.source_facts(HERE))]


def judged_all(events, groups):
    return {{(e['id'], c['sop']): C.evaluate(c['sop'], c['inputs'], groups) for e in events for c in e['candidates']}}


def inputs_view(previous):
    gap = T.load_function(HERE, T.GAP_FILE, 'fan_hours_when_gap')
    events, _ = T.prepare(HERE, gap)
    groups = C.load_table(T.pick(HERE, '조건표.csv'))
    rows = []
    for e in events:
        if not e['counter_gap']:
            continue
        c = e['candidates'][0]
        rows.append([e['id'], e['asset'], num(c['inputs']['fan100_hours']) if c['inputs']['fan100_hours'] is not None else '값 없음', c['missing_reasons'].get('fan100_hours', '')])
    j = judged_all(events, groups)
    st = [v['status'] for v in j.values()]
    return [table('카운터 기록이 끊긴 경보 — 내 함수가 낸 팬 100 % 연속 시간(h)', ['경보', '설비', 'fan100_hours', '값이 없는 까닭'], rows),
            counts('판정(경보 × 후보)', [('유지', st.count('유지')), ('제외', st.count('제외')), ('보류', st.count('보류'))]),
            against_expected('기대 판정 ↔ 판정', {{k: v['status'] for k, v in j.items()}})]


def compare_view(previous):
    gap = T.load_function(HERE, T.GAP_FILE, 'fan_hours_when_gap')
    cmp_ = T.load_function(HERE, T.COMPARE_FILE, 'choose_compared')
    choices = T.load_choices(HERE)
    res = T.run(HERE, T.pick(HERE, '조건표.csv'), gap, cmp_, choices, '')
    rows = [[e['id'], ', '.join(f"{{r['rank']}}위 {{r['sop']}} {{r['total']:.2f}}" for r in e['ranking']) or '순위 없음',
             '; '.join(f"{{c['sop']}}: {{' · '.join(c['no_comparison_reason'])}}" for c in e['candidates'] if c.get('no_comparison_reason'))] for e in res['events']]
    m = (HERE/'자료/metrics/지표_정의.md').read_text(encoding='utf-8')
    import re
    cid = re.search(r'사례 (\\S+)의 SOP-COOL-12', m).group(1)
    ex = next(c for e in res['events'] if e['id'] == cid for c in e['candidates'] if c['sop'] == 'SOP-COOL-12')
    hand = [[k, v, (ex['comparison'] or {{}}).get({{'비용': 'cost', '생산': 'production', '품질': 'quality', '에너지': 'energy'}}[k], '비교값 없음')]
            for k, v in re.findall(r'^\\| (비용|생산|품질|에너지) \\| .* \\| ([0-9.]+) \\|$', m, re.M)]
    ranked = sum(1 for e in res['events'] if e['ranking'])
    mine = sum(len(T.call_compare(cmp_, [c for c in e['candidates'] if c['status'] == '유지'])) for e in res['events'])
    skipped = sum(1 for e in res['events'] for c in e['candidates'] if c.get('no_comparison_reason'))
    return [counts('순위', [('순위가 있는 경보', ranked), ('내 함수(compare_rule)가 뺀 유지 후보', mine),
                           ('비교값이 없어 견주지 못한 유지 후보(까닭은 아래 표)', skipped - mine)]),
            table('경보마다 순위와 견주지 않은 후보', ['경보', '순위(합계, 만원)', '견주지 않은 유지 후보와 까닭'], rows),
            table(f'지표_정의.md 손계산 예({{cid}} SOP-COOL-12) ↔ 제공 코드', ['손실', '문서', '프로그램'], hand)]


def written(previous):
    try:
        res, files = T.run_folder(HERE, review_mode=REVIEW)
    except T.Unfilled as e:
        return [note(f'아직 결과 파일을 쓰지 않았습니다 — {{e}}')]
    exp_ids = {{r['사례 / 후보'].split(' / ')[0] for r in expected_rows()}}
    sel = [[e['id'], e['selection']['reason'], ' / '.join(e['selection']['checks']) or '—'] for e in res['events'] if e['id'] in exp_ids]
    return [note('쓴 파일: ' + ', '.join(files) + '\\ncomparison_basis: ' + res['comparison_basis']),
            table('기대를 적은 경보의 선택 이유와 추가로 확인할 사항', ['경보', '선택 이유', '추가로 확인할 사항'], sel)]


def cases_view(previous):
    gap = T.load_function(HERE, T.GAP_FILE, 'fan_hours_when_gap')
    cmp_ = T.load_function(HERE, T.COMPARE_FILE, 'choose_compared')
    res = T.run(HERE, T.pick(HERE, '조건표.csv'), gap, cmp_, T.load_choices(HERE), '')
    groups = C.load_table(T.pick(HERE, '조건표.csv'))
    thresholds = sorted({{(r['input'], float(r['value'])) for r in C.read_csv(T.pick(HERE, '조건표.csv')) if r['input'] in C.NUMERIC}})
    near = []
    for name, v in thresholds:
        vals = sorted({{c['inputs'][name] for e in res['events'] for c in e['candidates'] if c['inputs'][name] is not None}})
        below = [x for x in vals if x < v][-1:]
        above = [x for x in vals if x > v][:1]
        for x in [*below, *([v] if v in vals else []), *above]:
            hits = [f"{{e['id']}} {{c['sop']}}" for e in res['events'] for c in e['candidates'] if c['inputs'][name] == x]
            near.append([name, num(v), num(x), ', '.join(hits[:6]) + (' …' if len(hits) > 6 else '')])
    allx = [e['id'] for e in res['events'] if all(c['status'] == '제외' for c in e['candidates'])]
    ids = lambda hs: ' · '.join(h['rule_id'] for h in hs) or '—'
    per = [[e['id'], c['sop'], c['status'], ids(c['warnings']), ids(c['penalties']), ids(c['exclusions']), ids(c['unknown']),
            ' · '.join(f"{{m}}({{c['missing_reasons'].get(m, '')}})" for m in sorted({{m for u in c['unknown'] for m in u['missing']}})) or '—']
           for e in res['events'] for c in e['candidates']]
    out = [table('후보마다 판정 내용 — 사례 종류를 고를 때 거르기 칸에 경보 ID · 규칙 ID · 판정 낱말을 넣습니다',
                 ['경보', '후보', '판정', '경고', '감점', '제외', '미확인', '빠진 입력(까닭)'], per),
           table('조건표 기준값마다 같은 값 · 바로 아래 · 바로 위의 후보(사실)', ['입력', '기준값', '값', '경보 · 후보'], near),
           note('모든 후보가 제외된 경보: ' + (', '.join(allx) or '없음')),
           against_expected('기대 판정 ↔ 판정', {{(e['id'], c['sop']): c['status'] for e in res['events'] for c in e['candidates']}})]
    if REVIEW and (HERE/'결과/조치검토결과.md').is_file():
        md = (HERE/'결과/조치검토결과.md').read_text(encoding='utf-8')
        first = next(iter(sorted({{r['사례 / 후보'].split(' / ')[0] for r in expected_rows()}})), None)
        if first and f'## {{first}}' in md:
            part = md.split(f'## {{first}}', 1)[1].split('\\n## ', 1)[0]
            out.append(table(f'조치검토결과.md — {{first}} 절', ['줄'], [[x] for x in part.splitlines() if x.strip()]))
    return out
'''

JUDGE_STEPS_INTEGRATED = JUDGE_STEPS + '''

STEPS = [step(1, run=overview), step(2), step(3, ['결과/기대_판정.csv'], expected_view), step(4),
         step(5, ['결과/gap_rule.py'], inputs_view), step(6, ['결과/compare_rule.py'], compare_view), step(7, run=written),
         step(8, run=cases_view), step(9, run=run_check)]
'''
JUDGE_STEPS_PRACTICAL = JUDGE_STEPS + '''

def compare_and_write(previous):
    return compare_view(previous) + written(previous)


STEPS = [step(1, run=overview), step(2), step(3, ['결과/기대_판정.csv'], expected_view), step(4),
         step(5, ['결과/gap_rule.py'], inputs_view), step(6, ['결과/compare_rule.py'], compare_and_write), step(7, run=cases_view), step(8, run=run_check)]
'''


def steps_source(key, L):
    body = {'integrated-03-criteria': CRITERIA_STEPS, 'practical-02-conditions': CONDITIONS_STEPS,
            'integrated-03-judge': JUDGE_STEPS_INTEGRATED, 'practical-03-review': JUDGE_STEPS_PRACTICAL}[key]
    names = [s['name'] for s in L['steps']]
    case_from = (CASE_FROM_ALARMS if key in ('integrated-03-judge', 'practical-03-review') else CASE_FROM_CASES).replace('`', '')
    text = STEPS_HEAD.format(title=L['title'], names=names, expect_columns=EXPECT_COLUMNS) + body.format(review=key == 'practical-03-review', case_from=case_from, approval_columns=CR.APPROVAL_HEADER)
    return text


# ───────────── 정할 자리 빈 틀 ─────────────
# 칸마다 뜻 한 줄(값 없음) — 빈 틀 첫 줄 · 정답 토글 첫 줄 · 그 단계 힌트 「지킬 것」이 같은 글을 쓴다. 자세한 꼴은 입출력_계약.md.
REF_FORM = '매뉴얼 줄 번호(그 줄의 몇째 문장은 줄.문장), 매뉴얼 밖 자료는 파일:줄, 여러 개는 ;'
CLASS_COLS = ('한 줄이 칸 하나 · sop_id = 자료/targets.csv의 SOP ID(같은 칸 · 원문 · 글 · 규칙이 여러 절차에 걸리면 ;로 이어 한 줄) · '
              '칸 = 고장 유형 · 종류·코드 · 적용 · 금지 · 제한 · 완료 · 승인 가운데 하나(고장 유형 · 종류·코드 · 승인은 절차마다 하나) · '
              f'원문 = 근거 자리({REF_FORM}) · 글 = 비우면 원문을 그대로 인용(고장 유형은 failuremodes.csv ID, 종류·코드는 control:코드;코드 · work_order:코드 · 없음, '
              '승인은 역할 또는 「미확인」으로 시작해 찾아본 결과, 매뉴얼 밖 자료만 가리키면 그 조건) · 규칙 = 이 조건을 옮긴 조건표 rule_id(여러 개는 ;, 없으면 빈칸)')
REL_COLS = ('한 줄이 관계 하나 · type = MITIGATED_BY(고장 유형 → 즉시 완화 SOP) · REMEDIED_BY(고장 유형 → 근본 조치 SOP) · ADDRESSES(SOP → 그 SOP가 맞는 원인) 가운데 하나 · '
            'from · to = 양 끝 ID(고장 유형은 failuremodes.csv ID, SOP는 targets.csv ID, 원인은 cause:로 시작하는 영어 소문자 · 하이픈 이름) · '
            f'이름 = to가 원인이면 그 원인의 이름(아니면 빈칸) · 원문 = 근거 자리({REF_FORM})')
LINK_COLS = ('절차마다 한 줄 · sop_id = 자료/targets.csv의 SOP ID · 설비 = 걸 설비 ID(여러 개는 ;, 걸 설비가 없으면 빈칸) · '
             '구성_요소 · 센서 = 설비 ID 뒤의 이름(여러 개는 ;, 없으면 빈칸 — 고른 설비마다 모델에 있는 것만 이어짐) · 걸지_않은_까닭 = 걸지 않은 설비 · 대상과 그 까닭(없으면 빈칸)')
TABLE_COLS = ('비교 하나가 한 줄 · rule_id = 규칙 묶음 이름(같은 rule_id · action의 줄이 한 묶음) · action = 자료/targets.csv의 SOP ID 하나(여러 조치에 걸면 조치마다 묶음 전체) · '
              'condition_index = 묶음 안 비교 차례(1부터) · logic = AND · input · operator · value · unit = 입력 이름 · 비교 기호 · 기준값 · 단위(글자 · 목록 비교는 단위 빈칸) · '
              'boundary_included = 예 · 아니오 · 해당없음 · result = WARN · PENALTY · EXCLUDE · penalty_manwon = PENALTY만 만원(나머지 빈칸) · reason = 이유 문장 · '
              'source_section = ' + SOURCE_FORM + ' — 쓸 수 있는 값은 입출력_계약.md 「조건표」')
APPROVAL_COLS = ('후보마다 한 줄 · sop_id = 후보 SOP ID · 승인_역할 = 원문 승인 줄의 역할(찾지 못했으면 「미확인」으로 시작해 찾아본 결과) · '
                 '원문 = 자료/HM-8_매뉴얼.md의 승인 근거 줄 번호(여러 개는 ;)')
CLASS_BLANK = blank(CR.CLASS_HEADER, CLASS_COLS)
REL_BLANK = blank(CR.REL_HEADER, REL_COLS)
LINK_BLANK = blank(CR.LINK_HEADER, LINK_COLS)
TABLE_BLANK = blank(CR.HEADER, TABLE_COLS)
APPROVAL_BLANK = blank(CR.APPROVAL_HEADER, APPROVAL_COLS)


def table_answer(p2):
    """조건표 정답 토글 — 빈 틀과 같은 첫 줄 + 강사 참조 조건표."""
    return f'# {F.MARK} — {TABLE_COLS}\n' + CR.table_csv(p2)


GAP_HEAD = f'''"""{F.MARK}입니다. 보관하지 말고 바로 채웁니다 — START.md 「학생이 정할 것」의 빈 값의 뜻.

팬 운전 카운터의 정해진 주기 기록이 판정 요청 전에 끊긴 경보마다 제공 코드 judge_tools.py가 이 함수를 부릅니다.
ctx(읽기만): alarm_id 경보 ID · asset 설비 · decision_time 판정 요청 시각(UTC 글자) ·
  counter_last 판정 요청 전 마지막 카운터 기록(팬_운전_카운터.csv의 칸 이름 그대로 + '줄' 줄 번호) · counter_age_min 그 기록에서 판정 요청까지 지난 분 · counter_period_min 주기 기록 간격(분) ·
  plc_last 판정 요청 전 마지막 PLC 상태 수신(PLC_상태_수신.csv의 칸 이름 그대로 + '줄', 없으면 None) · plc_reason 운전 모드 · 상태를 값 없음으로 둔 까닭(값이 있으면 None)
돌려줄 값: (팬 100 % 연속 시간 h — 숫자 또는 None, None이면 값이 없는 까닭 글 · 숫자면 None)
"""
'''
COMPARE_HEAD = f'''"""{F.MARK}입니다. 보관하지 말고 바로 채웁니다 — START.md 「학생이 정할 것」의 쓰는 사람에 따라 갈리는 답.

경보마다 판정이 유지인 후보 목록으로 제공 코드 judge_tools.py가 이 함수를 부릅니다. 돌려준 후보는 비교 산식으로 견주지 않고 그 까닭을 결과에 남깁니다.
kept(읽기만): [{{'sop': 후보 ID, 'inputs': 판단 입력 일곱 개, 'warnings': 맞은 경고 규칙 목록, 'penalties': 맞은 감점 규칙 목록}}, ...]
돌려줄 값: {{견주지 않을 후보 ID: 까닭 글}} — 모두 견주면 빈 dict
"""
'''
GAP_BLANK = GAP_HEAD + "\n\ndef fan_hours_when_gap(ctx):\n    raise NotImplementedError('정할 자리: 결과/gap_rule.py fan_hours_when_gap')\n"
COMPARE_BLANK = COMPARE_HEAD + "\n\ndef choose_compared(kept):\n    raise NotImplementedError('정할 자리: 결과/compare_rule.py choose_compared')\n"


def gap_file(gap):
    return GAP_HEAD + '\n\n' + J.GAP_CODE[gap]


def compare_file(warned):
    return COMPARE_HEAD + '\n\n' + J.WARN_CODE[warned]


def record_template(title, extra=''):
    """기록 md — 목표 · 쓰는 사람 · 자료 · 지킬 조건 · 저장 기록. 고른 것 · 기대 판정은 CSV 두 개(한 곳)."""
    return (f'# {title}\n\n> {F.MARK}입니다. 보관하지 말고 바로 채웁니다.\n\n## 목표와 질문\n\n## 이 답을 쓰는 사람과 쓰는 곳\n\n## 사용할 자료와 기준일\n\n## 지킬 조건\n\n'
            '## 정한 것 · 기대 판정\n\n고른 것 · 근거(파일:줄) · 바뀌는 답은 `결과/정한_것.csv`, 실행 전에 손으로 구한 기대 판정은 `결과/기대_판정.csv`에 적습니다.\n\n'
            + extra + '## 저장 기록\n\n- 기준일:\n- 저장 시점:\n- 확인하지 못한 점:\n')


# ───────────── 학생 문장 ─────────────
USB = F.USB
WHY_TABLE = ('DMN의 결정표는 함께 맞아야 하는 비교 여러 개를 한 규칙으로 묶고, 「이상 · 이하」는 기준값을 포함하지만 「초과 · 미만」은 포함하지 않아 '
             '기준값과 같은 값에서 결과가 갈립니다.')
HIT_POLICY = '여러 규칙이 함께 맞을 때 무엇을 낼지 정한 것이 Hit Policy이고, 이 판정은 맞은 경고 · 감점 · 제외를 모두 모읍니다.'
WHY_SOURCE = ('판단 시스템의 결정표는 만들 때의 판으로 적혀 있어, 어느 행이 지금 원문의 어느 문장과 같은지 찾은 근거를 남겨야 '
              '다른 사람이 같은 판단을 다시 할 수 있습니다.')
WHY_UNKNOWN = '입력이 없어 확인할 수 없는 조건은 거짓과 달라 보류로 남기고, 이미 확인된 제외 사유는 다른 입력이 빠져도 그대로입니다.'
RESULT_KINDS = '**경고**는 그 조치에 주의할 점이 있다는 사유, **감점**은 비교할 때 금액으로 깎는 사유, **제외**는 그 조치를 쓸 수 없는 사유입니다.'
JUDGE_WORDS = ('판정은 그 사유를 모아 **유지** · **제외** · **보류**로 나뉩니다 — 보류는 제외 사유는 없지만 입력이 없어 맞는지 알 수 없는 규칙이 있는 후보이고, 세 말의 뜻은 `자료/작업기준.md` 4절에 있습니다.')
CONTRACT_TERM = '**계약**은 결과 파일의 모양(열 · 키와 그 뜻)을 정해 둔 `입출력_계약.md`입니다 — 다음 실습의 기능이 이 모양 그대로 읽습니다.'
PROVIDED_TERM = ('**제공 코드**는 누가 해도 같은 일(파일 읽기 · 원문 인용 · 조건표 적용 · 계약 꼴 쓰기 · 검사)을 하는 받은 코드이고, **정할 자리**는 `결과/`의 「제공 빈 틀」 파일 — '
                 '방향이 갈리는 판단을 내가 AI와 채우는 곳입니다. `python show_result.py`가 채운 자리까지 제공 코드를 돌려 `결과/보기.html`에 단계마다 결과를 보입니다.')
SYSTEM_TERM = '**판단 시스템**은 경보가 나면 조치 후보를 판정해 보여 주는 회사 시스템이고, 그 결정표를 내보낸 파일이 `자료/판단시스템_결정표_내보내기.txt`입니다.'
DECIDE_FIRM = ' 고른 것은 의견처럼 말하지 않고, 무엇으로 정했는지와 그 근거 줄을 단정해서 말합니다 — 의견으로 말하면 AI가 결정으로 받지 않고 다시 묻습니다.'
SHOW = F.SHOW_CMD
EXPECT_DIFFER = '기대와 다른 줄이 있으면 그 줄의 입력 값 · 맞은 규칙 · 원문 줄을 나란히 놓고 기대 · 판단 표 · 원문 가운데 어느 쪽이 원문과 다른지 찾아 고칩니다. 결과에 맞추려고 기대를 바꾸지 않습니다.'


def incident_line(files):
    """네 랩 첫머리의 사건 문장(한 곳) — 경보 ID를 적어 학생이 시각을 바꿔 찾지 않게 한다."""
    alarm = next(l.split('`')[1] for l in files[MEMO].splitlines() if l.startswith('- 경보 ID'))
    return (f'사건은 포털에서 본 경보와 같은 종류의 다른 경보 한 건, 10월 27일 {incident_time(files)}(한국 시각) HYD-02 쿨러 성능 저하 경보 '
            f'`{alarm}`입니다(경보 ID로 자료 · 결과 화면에서 찾습니다).')


def incident_time(files):
    for line in files[MEMO].splitlines():
        if line.startswith('- 경보 ID'):
            return line.split(': ', 1)[1][:5]
    raise RuntimeError('사건 메모에서 경보 시각을 찾지 못했습니다.')


def start_step(evidence, extra_why='', places='`입력/` · `자료/` · `결과/` · START.md'):
    return S('폴더와 출발점 확인 · 결과 화면 열기', '시작',
             f'VS Code 탐색기에서 {places}를 열어 각 자리의 역할과 이번 질문을 확인하고, 터미널에서 `python show_result.py`를 실행해 결과 화면을 엽니다.',
             '이번 질문과, 이 답을 쓰는 사람이 누구인지 확인합니다.', evidence + ' 결과 화면 맨 위 단계 띠에 이 실습의 단계가 보이고, 정할 자리가 있는 단계는 「비어 있음」입니다.',
             cmd=SHOW, why=F.WHY_START + extra_why, differ=F.DIFFER_START)


def look_step(do, ask, hint, why):
    return S('파일을 바꾸지 않고 자료 파악', '① 파악', do, ask, F.EVIDENCE_LOOK + ' 질문에 쓸 자료가 무엇인지 내 말로 말할 수 있습니다.', hint, why=why, differ=F.DIFFER_LOOK)


def plan_step(do, ask, evidence, hint, why):
    return S('계획 검토', '③ 계획', do, ask + DECIDE_FIRM, evidence, hint, why=why, differ=F.DIFFER_PLAN)


def save_step(n, rec, outputs):
    return S('검사 · 저장하고 다시 열기', '⑥ ⑦ 고침 · 저장',
             f'터미널에서 구조 검사를 실행해 짚은 문제를 고치고, 결과 파일을 모두 저장한 뒤 VS Code에서 폴더를 닫았다 다시 열어 `python show_result.py`와 구조 검사를 다시 실행합니다. `{rec}` 끝에 기준일 · 저장 시점 · 확인하지 못한 점을 적습니다.',
             '검사가 짚은 문제가 결과 파일 · 정할 자리의 어느 항목인지 묻습니다. 확인하지 못한 점으로 무엇을 남길지 정합니다.',
             f'「구조 검사 통과」 줄이 나오고, 다시 연 뒤에도 결과 화면과 검사 출력이 같습니다. `결과/`에 {outputs}가 있습니다.',
             cmd='python check.py\npython show_result.py',
             why='구조 검사는 ID · 열 · 짝처럼 모양만 보고, 결과가 원문과 맞는지는 원문에서 먼저 적은 기대 판정과 견주어 판단합니다. ' + F.WHY_SAVE,
             differ='「구조 확인 필요」가 나오면 줄마다 문제가 하나씩 적혀 있습니다. 줄마다 결과 파일의 어느 항목 · 행인지 AI에게 짚게 해 고친 뒤 다시 실행합니다. ' + F.DIFFER_SAVE)


def chosen_csv(rows):
    """정한 것 정답 토글 — 공용 빈 틀(칸 뜻 # 줄 + 열 이름) 그대로 + 행. 근거 여러 개는 공용 틀 꼴 「 · 」로 잇는다(강사 참조 문장의 ;를 바꿈)."""
    at = F.CHOSEN_COLUMNS.index('근거')
    rows = [[' · '.join(x.strip() for x in v.split(';')) if i == at else v for i, v in enumerate(r)] for r in rows]
    buf = io.StringIO()
    csv.writer(buf, lineterminator='\n').writerows(rows)
    return F.CHOSEN_TEMPLATE + buf.getvalue()


def expect_csv(rows, case_from):
    return csv_text(EXPECT_COLUMNS, rows, expect_cols(case_from))


def req_hint_expect(rec, cells, case_from):
    """요구 단계 힌트(공용) + 기대_판정.csv 칸마다 뜻."""
    h = F.req_hint(rec, 2, cells)
    h['지킬 것'] += ' 기대_판정.csv 칸: ' + expect_cols(case_from) + '.'
    return h


def memo_line(files, needle):
    return next(i for i, l in enumerate(files[MEMO].splitlines(), 1) if needle in l)


def incident_expect(files, kinds, table_text, cases=()):
    """사건 네 후보(+ 고른 확인 사례)의 기대 판정 — 강사 참조 조건표로 판정한 값과 근거 줄."""
    import tempfile
    p = Path(tempfile.mkdtemp())/'t.csv'
    p.write_text(table_text, encoding='utf-8', newline='\n')
    groups = CT.load_table(p)
    memo = CT.memo_inputs(files[MEMO], kinds)
    incident = next(l.split(',')[0] for l in files['확인_사례.csv'].splitlines()[1:] if l.split(',')[0] in files[MEMO])
    rows = []
    for s, x in memo.items():
        j = CT.evaluate(s, x, groups)
        rows.append([incident, s, j['status'], f'자료/{MEMO}:{memo_line(files, "| " + s)}; 자료/HM-8_매뉴얼.md:71'])
    if cases:
        cpath = Path(tempfile.mkdtemp())/'c.csv'
        cpath.write_text(files['확인_사례.csv'], encoding='utf-8', newline='\n')
        allc = CT.case_inputs(cpath, kinds)
        lines = files['확인_사례.csv'].splitlines()
        for cid in cases:
            ln = next(i for i, l in enumerate(lines, 1) if l.startswith(cid + ','))
            for s, x in allc[cid].items():
                rows.append([cid, s, CT.evaluate(s, x, groups)['status'], f'자료/확인_사례.csv:{ln}'])
    return rows


# ───────────── 랩 넷 ─────────────
def criteria_lab(files, folder):
    """통합반 03회차 실습2 — 작업 절차와 판단 조건을 연결해 조치 기준 만들기."""
    title = TITLES['integrated-03-criteria']
    rec = '결과/요구사항.md'
    kinds = {s: (k, list(c)) for s, _, k, c, *_ in CR.SOPS if s in CR.FOUR}
    exp_rows = incident_expect(files, kinds, CR.table_csv('가'))
    ch1 = CR.choice_rows_criteria('가', '가')[:1]
    ch_all = CR.choice_rows_criteria('가', '가')
    other = {'나': '다른 선택(HYD-04에도 SOP-COOL-13 · 15를 건다)이면 설비 표의 HYD-04 줄이 「걸었음」으로 바뀝니다.'}
    save = ('`결과/sop.json` · `결과/조건표.csv` · 판단 표 셋 · `결과/정한_것.csv` · `결과/기대_판정.csv` · `결과/요구사항.md`를 함께 보관합니다. '
            f'다음 실습 「{TITLES["integrated-03-judge"]}」에서는 이 조건표를 읽어 조치를 판정하고 견주는 기능을 만듭니다. 그 실습도 제공된 조건표로 시작할 수 있으므로 이 결과는 골라서 가져갑니다. ' + USB)
    steps = [
        start_step('탐색기에서 네 자리를 찾았고, `입력/graph.json`에 조치 절차와 판단 규칙이 아직 없다는 것을 파일에서 확인했습니다.'),
        look_step('AI에게 파일을 바꾸지 말고, 냉각 계통 조치마다 그 조치를 말하는 줄을 자료마다 찾아 파일:줄로 짚어 달라고 합니다. 짚은 줄을 직접 열고, 결과 화면의 「매뉴얼 원문 문장」 · 「판단 시스템 결정표 규칙」 표와 견줍니다.',
                  '같은 조치나 조건을 자료마다 다르게 적은 곳, 번호 · 표기 · 경계 낱말이 다른 곳이 있는지 묻습니다.',
                  H('조치마다 근거 줄을 자료마다 모은다. 아직 아무것도 만들지 않는다.', '`입력/` · `자료/` 전체, START.md 「해결할 질문」',
                    '파일을 바꾸지 않는다. 해석보다 파일:줄을 먼저 받는다.', '「파일:줄 · 그 줄이 말하는 것」 목록과, 자료끼리 말이 달라 보이는 곳 목록',
                    '`자료/targets.csv`의 조치가 모두 짚혔는지 개수를 세고, 결정표의 옛 판 번호를 현행 번호와 구별하며, 짚은 줄 몇 개를 직접 열어 결과 화면의 원문 번호와 견준다'),
                  '조치 기준에는 원문에 있는 것만 담아야 하므로, 만들기 전에 자료가 무엇을 말하는지부터 봅니다. 현행 원문 · 옛 판 · 시스템 내보내기 · 작업 기록은 만든 때와 사람이 달라 같은 일도 다르게 적혀 있을 수 있습니다.'),
        S('요구와 기대 판정 정하기', '② 요구',
          f'`{rec}`에 목표 · 쓰는 사람 · 쓸 판본 · 지킬 조건을 적고, 사건 네 후보가 조건표에서 유지 · 제외 · 보류 가운데 무엇이 될지 원문과 사건 메모에서 먼저 찾아 `결과/기대_판정.csv`에 근거 줄과 함께 적습니다.' + F.REQ_AFTER,
          '사건 메모의 값 가운데 조건에 그대로 대어 볼 수 없는 값(빈 칸 · 다른 단위)이 있는지 내가 정합니다.',
          '기대 판정마다 근거 파일:줄이 있습니다. 결과 화면 3단계에 내가 적은 기대가 보입니다. AI의 되짚기가 내 요구와 같고 바꾼 파일이 없습니다.',
          req_hint_expect(rec, '목표와 질문 · 쓰는 사람 · 자료와 기준일 · 지킬 조건, 기대_판정.csv', CASE_FROM_CASES), cmd=SHOW,
          why=F.WHY_REQ, differ=F.DIFFER_REQ.format(rec='결과/기대_판정.csv'),
          answer=A('사건 메모의 예측 · 운전 상태 · 팬 연속 시간을 원문 조건에 대면 아래 판정이 나옵니다. 값이 없는 후보는 그 값이 필요한 규칙 때문에 보류입니다.',
                   paste('결과/기대_판정.csv', expect_csv(exp_rows, CASE_FROM_CASES)))),
        plan_step('SOP 구조(판단 표 셋)와 조건표에 무엇을 나눠 담을지, 5 ~ 9단계에서 어느 정할 자리를 어떤 순서로 채울지 AI의 계획으로 받아 검토하고 동의합니다. 아직 파일을 만들지 않습니다.',
                  '같은 원문 문장이 SOP의 칸과 조건표의 행 둘 다에 걸리는 곳을 어떻게 이을지(규칙 칸) 정합니다.',
                  '질문 1 ~ 3마다 어느 정할 자리 · 결과 화면 단계로 답하는지 짚을 수 있습니다. 계획에 제공 코드를 다시 만드는 일과 「이번 범위 밖」의 일이 없습니다. 계획에 내가 동의했습니다.',
                  H('정할 자리의 몫과 순서를 합의한다', '`입출력_계약.md` 「판단 표 셋」 · 「조건표」, `결과/` 빈 틀', '제공 코드(`sop_tools.py` · `condition_tools.py`)는 고치지 않는다. 「이번 범위 밖」은 넣지 않는다.',
                    '정할 자리마다 채울 내용과 순서', '질문 1 ~ 3을 하나씩 계획에 대어 어느 자리 · 단계로 답하는지 짚게 한다'),
                  '「~일 때만 한다」 같은 문장은 SOP의 칸과 조건표의 행 둘 다에 걸리므로, 먼저 이을 방법을 정해야 같은 조건이 두 곳에 다르게 적히지 않습니다.'),
        S('조건 문장 나누기 — SOP 구조', '④ 판단',
          '절차마다 적용 · 금지 · 제한 · 완료 · 승인 칸에 들어갈 원문 문장과, 고장 유형 · 종류·코드를 `결과/조건_분류.csv`에 원문 자리로 적습니다. 실행해 결과 화면의 「SOP 구조」를 원문과 견줍니다.' + F.OWN_RUN,
          '「~일 때만」 「~하지 않는다」 「이내」 문장을 어느 칸에 둘지, 승인 줄이 없는 절차의 승인을 무엇으로 적을지, 다른 절 · 다른 SOP를 가리키는 문장을 어디에 둘지 내가 정하고 근거 줄을 말합니다.',
          '결과 화면 5단계에 절차 일곱이 모두 보이고 칸마다 원문 인용과 출처가 붙었습니다. 「아직 채우지 않은 곳」 칸이 없습니다. 3단계 기대와 다른 칸이 없거나 다른 까닭을 말할 수 있습니다.',
          H('원문 문장을 SOP 구조의 칸에 나눈다', '`자료/HM-8_매뉴얼.md`, 결과 화면의 원문 번호, `자료/판단시스템_결정표_내보내기.txt` 「스킬」 절',
            '원문에 없는 단계 · 값을 만들지 않는다. 승인 줄이 없으면 역할을 만들지 않는다. 칸: ' + CLASS_COLS + '.',
            '`결과/조건_분류.csv`의 행', '결과 화면 5단계 표에서 칸마다 인용된 문장을 원문 줄과 나란히 본다'),
          SHOW, why='같은 사실이라도 적용 조건과 금지 조건 가운데 어느 칸에 두느냐에 따라 판단이 「쓸 수 있다」와 「쓸 수 없다」로 갈리므로, 칸마다 원문 자리를 붙여 다시 확인할 수 있게 합니다. 수행 단계는 제공 코드가 매뉴얼의 번호 줄 그대로 옮깁니다.',
          differ=F.FIX_LOOP,
          answer=A('원격 조치 셋에는 REMOTE_AUTO 조건(45줄 첫 문장)을 적용, 87줄 · 45줄 둘째 문장을 금지, 부하 60 % 하한을 제한, HM-8.6 회복 판정을 완료로 둡니다. 승인 줄이 없는 SOP-FAN-11 · 12는 「미확인」입니다. 옛 결정표의 근거 없는 규칙(9단계)은 아직 넣지 않습니다.',
                   paste('결과/조건_분류.csv', csv_text(CR.CLASS_HEADER, CR.classify_rows('다'), CLASS_COLS)))),
        S('고장 유형 · 원인 · 조치 잇기', '④ 판단',
          '고장 유형에서 즉시 완화 조치 · 근본 조치로, 조치에서 그 조치가 맞는 원인으로 가는 관계를 `결과/관계.csv`에 원문 자리와 함께 적고 결과 화면의 「관계」 표를 봅니다.',
          '조치가 특정 원인에만 맞는지와 그 근거 줄, 점검 · 확인만 하는 절차를 근본 조치로 이을 수 있는지 정합니다.',
          '결과 화면 6단계에 「양 끝이 sop.json에 없는 관계」 칸이 없고, 원인마다 이어진 조치를 원문 줄로 말할 수 있습니다.',
          H('고장 유형 · 원인 · 조치를 관계로 잇는다', '매뉴얼의 원인 절(HM-8.4), `자료/failuremodes.csv`', '원문에 없는 연결을 만들지 않는다. 칸: ' + REL_COLS + '.',
            '`결과/관계.csv`의 행', '결과 화면 6단계 표의 원인마다 이어진 조치를 원문 줄과 견준다'),
          SHOW, why='즉시 완화는 지금 증상을 누그러뜨리는 조치이고, 근본 조치는 원인을 없애는 조치입니다. 같은 고장 유형이라도 원인에 따라 맞는 근본 조치가 다르므로 관계가 있어야 판단이 원인에 맞지 않는 조치를 고르지 않습니다.',
          differ=F.FIX_LOOP,
          answer=A('즉시 완화 셋, 근본 조치(핀 세척 · 환기 보강 · 벨트 교체), 원인 셋과 잇는 관계입니다. 점검만 하는 SOP-FAN-11은 근본 조치가 아니라 원인을 확인하는 관계로만 잇습니다.',
                   paste('결과/관계.csv', csv_text(CR.REL_HEADER, CR.relation_rows(), REL_COLS)))),
        S('적용 범위와 설비 모델 ID 잇기', '④ 판단 · 정할 것',
          '절차마다 걸 설비와 구성 요소 · 센서 이름, 걸지 않은 대상과 까닭을 `결과/설비_연결_기준.csv`에 적고, 「적용 범위」 지점의 고른 것 · 근거를 `결과/정한_것.csv`에 한 줄 적습니다. 결과 화면의 「설비마다 걸린 SOP」를 설비 대장 · 모델과 견줍니다.',
          '원문에 적용 범위 문장이 없을 때 어느 설비에 걸지, 절차마다 어느 장치 · 센서를 걸지 그 기준을 내가 정합니다. AI가 결정을 대신 정하려 하면 돌려보내고 내 선택과 근거를 다시 말합니다.',
          '결과 화면 7단계에 「모델에서 찾지 못한 ID」 칸이 없거나 그 까닭이 걸지 않은 대상에 적혀 있고, 설비마다 걸었음 · 뺐음을 대장 · 모델 줄로 말할 수 있습니다. `결과/정한_것.csv`에 적용 범위 줄이 있습니다.',
          H('절차가 걸리는 설비 · 장치 · 센서의 기준을 정한다', '`입력/graph.json` · `입력/schema.json` · `입력/자료/설비_대장.csv`, 결과 화면 7단계',
            '모델에 없는 ID를 만들지 않는다. 칸: ' + LINK_COLS + '. 정한_것.csv 칸 뜻은 그 파일 첫머리 # 줄.', '`결과/설비_연결_기준.csv`의 행과 `결과/정한_것.csv`의 적용 범위 줄',
            '설비 몇 대는 모델 파일에서 관계를 직접 따라가 보고, 결과 화면의 설비 표와 견준다'),
          SHOW, why='2회차에 만든 설비 모델의 ID를 그대로 써야 조치 기준이 모델과 이어지고, 새 ID를 지으면 같은 설비가 두 이름으로 갈라져 판단이 설비를 찾지 못합니다. 조치에 필요한 장치 · 센서가 그 설비에 실제로 있는지는 모델의 관계로 확인합니다.',
          differ='걸었음 · 뺐음의 까닭을 모델 줄로 말할 수 없는 설비가 있으면 그 설비의 관계를 AI와 하나씩 따라가 확인하고, 고친 뒤 결과 화면을 다시 봅니다.',
          answer=A('HYD-01 ~ 03(같은 모델 HPP-45A)에만 겁니다 — HYD-04는 수냉식 후속형이라 HM-8에 범위 문장이 없어 뺐습니다. ' + other['나'],
                   paste('결과/설비_연결_기준.csv', csv_text(CR.LINK_HEADER, CR.link_rows('가'), LINK_COLS)),
                   paste('결과/정한_것.csv', chosen_csv(ch1)))),
        S('조건표 규칙 — 복합 조건과 경계', '④ 구현',
          '원문의 경고 · 감점 · 제외 조건을 `결과/조건표.csv`에 계약 모양으로 옮기고, 조건 문장의 규칙 칸(`결과/조건_분류.csv`)에 그 rule_id를 적습니다. 결과 화면에서 규칙마다 출처의 원문과 사건 네 후보의 판정을 3단계 기대와 견줍니다.',
          '여러 조건을 한 묶음(AND)으로 둘지 나눌지, 「이상 · 초과 · 미만」이 원문끼리 다른 곳을 무엇으로 정할지, 규칙을 어느 조치에 걸지 원문 낱말로 정합니다.',
          '결과 화면 8단계의 「기대 판정 ↔ 조건표를 댄 판정」이 같거나, 다른 줄의 까닭을 원문 줄로 말할 수 있습니다. 규칙마다 출처 칸의 원문이 보입니다.',
          H('경고 · 감점 · 제외 조건을 규칙으로 옮긴다', '그 원문 줄, `입출력_계약.md` 「조건표」, `결과/조건_분류.csv`', '경계는 원문 낱말대로 옮긴다. 한 묶음씩 옮기고 결과 화면을 본다. 칸: ' + TABLE_COLS + '.',
            '`결과/조건표.csv`의 행과 조건 문장의 규칙 칸', '결과 화면 8단계의 원문 줄 · 사건 판정을 기대와 견준다'),
          SHOW, why=WHY_TABLE + ' ' + HIT_POLICY, differ=EXPECT_DIFFER,
          answer=A('원격 자동 아님 제외(R1, 두 조건 AND), 팬 100 % 24시간 초과 감점 20만 원(R2 — 「넘으면」은 초과), 예측 유온 55 ℃ 이상 경고(R3 — HM-8.6 「이상」)입니다.',
                   paste('결과/조건표.csv', table_answer('다')))),
        S('출처가 확인되지 않는 규칙', '⑤ 판단 · 정할 것',
          '판단 시스템 결정표에 있는데 받은 원문에서 근거 문장을 찾을 수 없는 규칙마다 조건표에 어떻게 둘지 정해 `결과/조건표.csv` · `결과/조건_분류.csv`에 반영하고, 규칙마다 `결과/정한_것.csv`에 한 줄씩 적습니다. 결과 화면에서 확인 사례의 판정이 직전 실행과 어떻게 바뀌었는지 봅니다.',
          '규칙마다 옮김 · 고침(대상을 바꿈) · 뺌 가운데 무엇으로 할지와 근거 줄을 내가 정합니다. AI가 결정을 대신 정하려 하면 돌려보내고 내 선택과 근거를 다시 말합니다.',
          '결과 화면 9단계의 결정표 규칙 표에서 내 조건표가 출처로 든 규칙이 내 결정과 같고, 확인 사례 판정 개수의 직전 실행 대비 변화를 내 결정으로 설명할 수 있습니다. `결과/정한_것.csv`에 규칙마다 줄이 있습니다.',
          H('근거 없는 옛 규칙을 어떻게 둘지 정해 반영한다', '`자료/판단시스템_결정표_내보내기.txt`, `자료/HM-8_매뉴얼.md` · `자료/HM-8_1.0판_매뉴얼.md`, `자료/작업기준.md`, 결과 화면 9단계 「출처_절」',
            '이름만 보고 잇지 않는다. 원문에서 찾지 못한 근거는 찾지 못했다고 출처 칸에 적는다.', '조건표 행 · 조건 문장 행과 `결과/정한_것.csv`의 규칙마다 줄',
            '결정이 바꾸는 확인 사례를 결과 화면에서 찾아 그 원천 줄을 연다'),
          SHOW, why=WHY_SOURCE + ' ' + WHY_UNKNOWN, differ=EXPECT_DIFFER,
          answer=A('rule:ts1-hard · rule:trip-reset-only를 옛 시스템이 건 그대로(대상 빈칸 = 네 후보) 제외로 옮기고 출처 칸에 원문 미확인을 적었습니다. 다른 선택(제어 후보에만 · 옮기지 않음)이면 트립 사례와 예측 65 ℃ 이상 사례의 판정이 바뀝니다. rule:ps1-warn은 펌프 계통 조건이라 옮기지 않습니다.',
                   paste('결과/조건표.csv', table_answer('가')),
                   paste('결과/조건_분류.csv', csv_text(CR.CLASS_HEADER, CR.classify_rows('가'), CLASS_COLS)),
                   paste('결과/정한_것.csv', chosen_csv(ch_all)))),
        save_step(10, rec, '`sop.json` · `조건표.csv` · 판단 표 셋 · `정한_것.csv` · `기대_판정.csv` · `요구사항.md`'),
    ]
    formats = ['## 결과 형식\n\n파일의 모양은 `입출력_계약.md`에 있습니다. 무엇을 어느 칸 · 행에 둘지는 원문을 읽고 직접 정합니다.\n\n'
               '- 정할 자리(「제공 빈 틀」): `결과/조건_분류.csv` · `결과/관계.csv` · `결과/설비_연결_기준.csv`(판단 표 셋), `결과/조건표.csv`, `결과/정한_것.csv`, `결과/기대_판정.csv`, `결과/요구사항.md`.\n'
               '- `결과/sop.json` — 제공 코드 `sop_tools.py`가 판단 표 셋으로 씁니다(`python show_result.py`).\n\n'
               '## 지킬 조건\n\n- 모델에 없는 대상에는 새 ID를 만들지 않습니다.\n- 조치 기준의 항목마다 원문 출처를 답니다.\n- 제공 코드(`show_result.py` · `lab_steps.py` · `sop_tools.py` · `condition_tools.py` · `check.py`)는 고치지 않습니다.\n']
    return dict(
        title=title, rec=rec, readonly='`입력/` · `자료/` · 제공 코드가', decide_step=2, course='통합반',
        goal=[f'포털의 조치 방법 화면에서 쿨러 조치의 단계 · 담당 · 승인을, 판단 규칙 화면에서 어떤 규칙이 조치를 허용 · 제외하는지 봤습니다. '
              f'이번에는 그 근거를 매뉴얼 원문에서 직접 찾아 작업 절차(SOP 구조)와 판단 조건(조건표)으로 나누고, 2회차에 만든 설비 모델의 ID에 잇습니다. '
              f'{incident_line(files)}',
              'SOP(표준 작업 절차, Standard Operating Procedure)는 사람이 따라 하는 절차(적용 조건 · 금지 조건 · 수행 단계 · 완료 기준 · 승인)를 담고, 조건표는 어떤 입력이 어떤 값일 때 조치를 경고 · 감점 · 제외하는지를 담습니다. '
              '조건표는 DMN(판단을 표준 모양으로 적는 방식)의 결정표 — 입력 조건과 판단 결과를 한 행씩 적은 표 — 를 이 실습에서 부르는 이름입니다.',
              '어느 문장을 어느 칸 · 규칙으로 옮길지, 무엇을 잇고 어느 설비에 걸지는 내가 판단 표에 정하고, 원문 인용 · JSON 꼴 쓰기 · 모델 ID 찾기 · 조건표 적용은 제공 코드가 합니다.',
              F.STAGE_LINE.format(what='판단 지식 — 절차와 판단 조건을 원문에서 구조화해 설비 모델에 잇는 일 — ')],
        make='만들 것: 판단 표 셋 · `결과/조건표.csv` · `결과/정한_것.csv` · `결과/기대_판정.csv` · `결과/요구사항.md`(내가 AI와 채움), `결과/sop.json`(제공 코드가 판단 표로 씀).',
        start=['`입력/schema.json` · `입력/graph.json` — 설비 7대의 설비 · 구성 요소 · 센서 · 부품 모델. 2회차에 만든 설비 모델과 같은 꼴로 제공된 판입니다. `입력/자료/설비_대장.csv` — 그 모델의 설비 대장(기준일 ' + D2.REF_DATE + ').',
               MINE['integrated-03-criteria'],
               '`자료/HM-8_매뉴얼.md` — 현행 HM-8 1.1판(2026-09-01 시행) 냉각 계통 조치 원문. `자료/HM-8_1.0판_매뉴얼.md` — 1.1판으로 대체된 옛 판(2025-03-10 시행). `자료/HI-01_보충매뉴얼.md` — 점검 · 이상 확인 보충 기준.',
               '`자료/판단시스템_결정표_내보내기.txt` — 판단 시스템에 등록된 결정표 · 스킬을 내보낸 것(2025년 도입 판, 2026-10-27 내보냄). `자료/작업지시_이력.csv` — CMMS 작업지시 1년치 내보내기(2026-10-28).',
               '`자료/작업기준.md` — 회사 작업 기준. `자료/targets.csv` — 냉각 계통 SOP 목록. `자료/failuremodes.csv` — 회사 고장 유형 목록. `자료/사건_기록_HYD-02_1027.md` — 야간 운전원이 HMI에서 옮겨 적은 사건 메모. '
               '`자료/확인_사례.csv` — 지난 30일 경보 가운데 고른 확인 사례의 판단 입력(입력마다 원천과 그 시각).',
               '`입출력_계약.md` — 결과 · 판단 표의 형식. `check.py` — 구조 검사. `sop_tools.py` · `condition_tools.py` — 제공 코드(고치지 않습니다).', SHOW_LINE,
               '`결과/` — 정할 자리(「제공 빈 틀」)와 README.', RULES_LINE],
        user='이 답은 설비보전팀장이 판단 시스템에 조치 기준을 올릴 때, 야간 운전원이 사건에서 할 수 있는 조치를 볼 때 씁니다.',
        questions=['냉각 계통 조치 일곱 개마다 적용 조건 · 금지 조건 · 수행 단계 · 완료 기준 · 승인은 무엇이고, 어느 고장 유형 · 원인과 어느 설비 · 구성 요소 · 센서에 걸리는가?',
                   '판단 규칙으로 옮길 조건의 입력 · 단위 · 연산자 · 경계 · 결과 · 출처는 무엇이고, 판단 시스템에 등록된 결정표의 규칙 가운데 원문에 근거가 없는 것은 어떻게 두는가?',
                   '사건 한 건의 판단 요청 때 값을 조건표에 대면 네 후보가 각각 어떻게 되는가?'],
        decide=[('적용 범위', '원문에 적용 범위 문장이 없을 때 이 조치 기준을 설비 모델의 어느 설비에 걸지'),
                ('출처가 확인되지 않는 기준', '판단 시스템 결정표에 있는데 지금 매뉴얼에서 근거 문장을 찾을 수 없는 규칙을 어떻게 둘지 — 그런 규칙이 여럿이면 규칙마다 정하고 근거를 적습니다')],
        outside=['원문에서 조건을 자동으로 뽑아내는 일(인제스천 — 뒤에서 직접 다룹니다)', '조건표로 원천 기록을 판정하고 견주는 기능(다음 실습)',
                 '설비 모델(schema · graph)을 고치거나 그래프 DB에 적재하는 일', '실제 설비 · 포털 · 업무 시스템을 부르는 일'],
        formats=formats, steps=steps,
        cases=['같은 조치를 판마다 다른 번호 · 절 · 낱말로 적은 곳(현행 원문 · 옛 판 · 판단 시스템 · 작업 이력)', '경계 낱말(「이상 · 초과 · 미만」)이 원문끼리 다른 조건',
               '여러 조건이 함께 맞아야 하는 조건과 다른 절 · 다른 SOP를 가리키는 단계', '조치에 필요한 구성 요소 · 센서가 모델에 없는 설비',
               '판단 시스템 결정표에서 냉각 계통 밖을 다루는 행', '사건 기록에서 값이 비어 있는 후보', '「정할 것」의 결정에 따라 결과가 바뀌는 확인 사례', '같은 명령을 다시 실행한 결과'],
        commands='python show_result.py\npython check.py',
        done=('형식 검사나 실행 성공만으로 완료하지 않습니다. 사건 네 후보의 기대 판정과 조건표를 댄 판정이 맞고, 「정한 것」마다 근거 줄과 그 선택으로 바뀌는 답을 설명할 수 있으며, '
              '`sop.json` · `조건표.csv`의 항목마다 원문 문장으로 돌아갈 수 있으면(결과 화면의 출처 대조) 완료입니다. 확인하지 못한 점은 `결과/요구사항.md`에 남깁니다.'),
        save=save, reopen='결과 화면의 단계 띠 · 출처 대조와 구조 검사 출력, `요구사항.md`의 기준일 · 저장 시점 · 확인하지 못한 점',
        tree=tree('03일차_실습2_조치기준만들기', [('.github/', 'Copilot 작업 규칙'), ('결과/', '정할 자리(판단 표 · 조건표 · 정한 것 · 기대 판정 · 요구사항 빈 틀)'),
                                            ('입력/', '설비 모델과 설비 대장(읽기만)'), ('자료/', '매뉴얼 · 판단 시스템 결정표 · 작업 이력 · 사건 메모 · 확인 사례(읽기만)'),
                                            ('AGENTS.md', 'Codex 작업 규칙'), ('check.py', '구조 검사'), ('CLAUDE.md', '작업 규칙(같은 내용)'), ('condition_tools.py', '제공 코드'),
                                            ('lab_steps.py', '결과 화면 단계(제공)'), ('show_result.py', '결과 화면(제공)'), ('sop_tools.py', '제공 코드'),
                                            ('START.md', '이번 과제와 진행 단계'), ('입출력_계약.md', '결과 · 판단 표의 형식')]),
        lead='매뉴얼 원문의 문장을 SOP 구조의 칸과 조건표의 규칙으로 나누는 판단을 하나씩 정하고, 제공 코드가 그 판단으로 만든 SOP 구조 · 판정을 결과 화면에서 원문 · 사건과 대조합니다.',
        need='VS Code와 Python, 로그인해 둔 Codex 또는 GitHub Copilot.',
        terms=('조건표의 결과는 셋입니다 — ' + RESULT_KINDS + ' ' + JUDGE_WORDS + ' ' + SYSTEM_TERM + ' ' + PROVIDED_TERM + ' ' + CONTRACT_TERM),
        first_more=[MINE['integrated-03-criteria']],
        guide_extra={0: ['terminal', 'result'], 1: ['ai', 'review']},
        files={'입출력_계약.md': ('# 입출력 계약\n\n결과 파일과 판단 표의 형식과 뜻만 정한다. 무엇을 담을지는 원문에서 정한다.\n\n' + SOP_CONTRACT + '\n' + TABLE_CONTRACT + '\n' + CHOSEN_CONTRACT.replace('{case_from}', CASE_FROM_CASES) + '\n' + CASES_CONTRACT).replace('{codes_from}', CODES_FROM_EXPORT),
               '결과/요구사항.md': record_template('요구사항'), '결과/조건표.csv': TABLE_BLANK, '결과/조건_분류.csv': CLASS_BLANK, '결과/관계.csv': REL_BLANK,
               '결과/설비_연결_기준.csv': LINK_BLANK, '결과/정한_것.csv': F.CHOSEN_TEMPLATE, '결과/기대_판정.csv': expect_blank(CASE_FROM_CASES),
               '결과/README.md': '이번 과제의 정할 자리(판단 표 셋 · 조건표 · 정한 것 · 기대 판정 · 요구사항)를 채우는 자리입니다. `python show_result.py`가 판단 표로 `sop.json`과 결과 화면 `보기.html`을 여기에 씁니다.\n',
               '입력/README.md': '2회차에 만든 설비 모델과 같은 꼴의 설비 7대 모델(schema.json · graph.json)과 그 설비 대장(자료/설비_대장.csv)입니다. 이 폴더는 읽기만 합니다.\n'})


def conditions_lab(files, folder):
    """실전반 02회차 실습5 — 작업 기준의 복합 조건과 예외를 조치 조건표로 표현하기."""
    title = TITLES['practical-02-conditions']
    rec = '결과/판단기록.md'
    kinds = {s: (k, list(c)) for s, _, k, c, *_ in CR.SOPS if s in CR.FOUR}
    cases = pick_cases(files, kinds)
    exp_rows = incident_expect(files, kinds, CR.table_csv('가'), cases)
    ch = CR.choice_rows_criteria('가', '가', practical=True)
    save = ('`결과/조건표.csv` · `결과/승인.csv` · `결과/정한_것.csv` · `결과/기대_판정.csv` · `결과/판단기록.md`를 함께 보관합니다. '
            f'다음 실습 「{TITLES["practical-03-review"]}」에서는 이 조건표를 읽어 후보별 판정과 조치 검토 결과를 만듭니다. 그 실습도 제공된 조건표로 시작할 수 있으므로 이 결과는 골라서 가져갑니다. ' + USB)
    steps = [
        start_step('탐색기에서 세 자리를 찾았고, `결과/조건표.csv`에 열 이름만 있다는 것을 확인했습니다.',
                   ' 이번에는 절차(SOP)가 아니라 어떤 조건에서 조치를 쓸 수 있는지를 정하는 판단 규칙 쪽을 표로 만듭니다.', '`자료/` · `결과/` · START.md'),
        look_step('AI에게 파일을 바꾸지 말고, 원문의 조건 문장 · 판단 시스템 결정표의 행 · 사건 기록 · 확인 사례가 각각 무엇을 담고 있는지 파일:줄로 짚어 달라고 합니다. 짚은 줄을 직접 열고 결과 화면 2단계 표와 견줍니다.',
                  '자료끼리 말이 달라 보이는 곳이 있는지, 확인 사례의 값이 비는 까닭이 몇 가지인지 묻습니다.',
                  H('조건과 판단 입력이 어디서 오는지 파악한다. 아직 아무것도 만들지 않는다.', '`자료/` 전체, START.md 「해결할 질문」',
                    '파일을 바꾸지 않는다. 해석보다 파일:줄을 먼저 받는다.', '원문 근거 목록, 자료끼리 말이 달라 보이는 곳 목록, 값이 비는 까닭 표', '짚은 줄 가운데 몇 개를 내가 직접 열어 같은 내용인지 본다'),
                  '조건표에는 원문에 있는 조건만 담아야 합니다. 원문 · 시스템 내보내기 · 기록은 만든 때와 사람이 달라 같은 조건도 다르게 적혀 있을 수 있으므로, 자료마다 어느 판 · 시점인지 먼저 압니다.'),
        S('요구와 기대 판정 정하기', '② 요구',
          f'`{rec}`에 목표 · 쓰는 사람 · 지킬 조건을 적고, 사건과 확인 사례 두세 개의 네 후보가 유지 · 제외 · 보류 가운데 무엇이 될지 원문에서 먼저 찾아 `결과/기대_판정.csv`에 근거 줄과 함께 적습니다.' + F.REQ_AFTER,
          '경계값과 같은 사례, 입력이 빠졌는데 제외 사유도 있는 사례를 고릅니다(AI에게는 판정을 빼고 위치만 찾게 합니다).',
          '기대 판정마다 근거 파일:줄이 있고 결과 화면 3단계에 보입니다. AI의 되짚기가 내 요구와 같고 바꾼 파일이 없습니다.',
          req_hint_expect(rec, '목표와 질문 · 쓰는 사람 · 자료와 기준일 · 지킬 조건, 기대_판정.csv', CASE_FROM_CASES), cmd=SHOW, why=F.WHY_REQ, differ=F.DIFFER_REQ.format(rec='결과/기대_판정.csv'),
          answer=A('사건 네 후보와, 경계값 사례 · 제외와 미확인이 함께 있는 사례를 원문 조건에 대면 아래 판정이 나옵니다.', paste('결과/기대_판정.csv', expect_csv(exp_rows, CASE_FROM_CASES)))),
        plan_step('조건표에 넣을 규칙과 옮길 순서, 승인 표를 채울 때를 AI의 계획으로 받아 검토하고 동의합니다. 아직 파일을 만들지 않습니다.',
                  '조건표에 옮기지 않을 원문 조건과 그 까닭을 정합니다.',
                  '사건의 네 후보에 걸릴 규칙을 계획에서 짚을 수 있습니다. 계획에 원문에 없는 기준값 · 조건과 제공 코드를 다시 만드는 일이 없습니다. 계획에 내가 동의했습니다.',
                  H('조건표에 들어갈 규칙과 순서를 합의한다', '`입출력_계약.md`, `결과/` 빈 틀', '원문에 없는 기준값 · 조건을 더하지 않는다. 제공 코드는 고치지 않는다.', '규칙 목록과 옮길 순서', '사건의 네 후보에 어느 규칙이 걸리는지 계획에서 짚게 한다'),
                  '한 문장에 조건 여러 개와 예외가 섞인 원문을 바로 표로 옮기면 빠지거나 겹치는 행이 생깁니다. 무엇을 몇 행으로 옮길지 먼저 합의해야 행마다 원문으로 돌아갈 수 있습니다.'),
        S('조건표 규칙 — 복합 조건과 경계', '④ 구현',
          '원문의 경고 · 감점 · 제외 조건을 `결과/조건표.csv`에 계약 모양으로 한 묶음씩 옮기며 결과 화면에서 출처의 원문과 사건 · 확인 사례의 판정을 3단계 기대와 견줍니다.' + F.OWN_RUN,
          '여러 조건을 한 묶음(AND)으로 둘지 나눌지, 「이상 · 초과 · 미만」이 원문끼리 다른 곳을 무엇으로 정할지, 규칙을 어느 조치에 걸지 원문 낱말로 정합니다.',
          '결과 화면 5단계의 「기대 판정 ↔ 조건표를 댄 판정」이 같거나 다른 줄의 까닭을 원문으로 말할 수 있고, 한 후보에 경고와 감점이 함께 맞은 줄, 제외와 미확인이 함께 있는 줄이 보입니다.',
          H('경고 · 감점 · 제외 조건을 규칙으로 옮긴다', '그 원문 줄, `입출력_계약.md` 「조건표」', '경계는 원문 낱말대로 옮긴다. 한 묶음씩 옮기고 결과 화면을 본다. 칸: ' + TABLE_COLS + '.', '`결과/조건표.csv`의 행', '결과 화면 5단계의 원문 줄 · 판정을 기대와 견준다'),
          SHOW, why=WHY_TABLE + ' ' + HIT_POLICY, differ=EXPECT_DIFFER,
          answer=A('원격 자동 아님 제외(R1), 팬 100 % 24시간 초과 감점 20만 원(R2), 예측 유온 55 ℃ 이상 경고(R3)입니다.', paste('결과/조건표.csv', table_answer('다')))),
        S('출처가 확인되지 않는 규칙', '⑤ 판단 · 정할 것',
          '판단 시스템 결정표에 있는데 제공 SOP에서 근거 문장을 찾을 수 없는 규칙마다 조건표에 어떻게 둘지 정해 `결과/조건표.csv`에 반영하고, 규칙마다 `결과/정한_것.csv`에 한 줄씩 적습니다. 결과 화면에서 사례 판정이 직전 실행과 어떻게 바뀌었는지 봅니다.',
          '규칙마다 옮김 · 고침 · 뺌 가운데 무엇으로 할지와 근거 줄을 내가 정합니다. AI가 결정을 대신 정하려 하면 돌려보내고 내 선택과 근거를 다시 말합니다.',
          '결과 화면 6단계에서 판정 개수의 직전 실행 대비 변화를 내 결정으로 설명할 수 있고(바뀌지 않았으면 그 까닭 — 5단계에서 이미 현행 원문으로 행을 썼거나 결정이 뺌 · 출처만 고침이었음 — 과 뺀 규칙이 바꿨을 사례를 말할 수 있고), 조건표의 출처 칸이 원문으로 돌아가거나 원문에서 찾지 못했다고 적혀 있습니다. `결과/정한_것.csv`에 규칙마다 줄이 있습니다.',
          H('근거 없는 옛 규칙을 어떻게 둘지 정해 반영한다', '`자료/판단시스템_결정표_내보내기.txt`, `자료/HM-8_매뉴얼.md`, `자료/작업기준.md`, 결과 화면 6단계 「출처_절」',
            '이름만 보고 잇지 않는다. 원문에서 찾지 못한 근거는 찾지 못했다고 출처 칸에 적는다. 출처 칸: ' + SOURCE_FORM + '. 정한_것.csv 칸 뜻은 그 파일 첫머리 # 줄.', '조건표 행과 `결과/정한_것.csv`의 규칙마다 줄', '결정이 바꾸는 사례를 결과 화면에서 찾아 그 원천 줄을 연다'),
          SHOW, why=WHY_SOURCE + ' ' + WHY_UNKNOWN, differ=EXPECT_DIFFER,
          answer=A('rule:ts1-hard · rule:trip-reset-only를 옛 시스템이 건 그대로 네 후보에 제외로 옮기고 출처 칸에 원문 미확인을 적었습니다. 다른 선택이면 트립 사례와 예측 65 ℃ 이상 사례의 판정이 바뀝니다.',
                   paste('결과/조건표.csv', table_answer('가')), paste('결과/정한_것.csv', chosen_csv(ch[:3])))),
        S('남은 후보와 실행 승인', '⑤ 판단',
          '후보마다 실행을 누가 승인하는지와 그 원문 승인 줄을 `결과/승인.csv`에 적습니다. 원문의 승인 줄이 하나로 읽히지 않는 후보는 고른 것 · 근거를 `결과/정한_것.csv`에 적습니다. 결과 화면의 「남은 후보와 실행 승인」 표를 봅니다.',
          '남은 후보마다 누가 승인하고 그 근거가 원문 어디에 있는지, 원문의 승인 줄이 하나로 읽히지 않는 후보를 어떻게 적을지 정합니다.',
          '결과 화면 7단계에 남은 후보(보류 표시 포함)마다 승인 역할과 원문 승인 줄이 보이고, 「후보가 남은 것은 실행 허가가 아니다」를 내 말로 말할 수 있습니다.',
          H('후보가 남는 것과 실행 승인을 따로 적는다', '`자료/HM-8_매뉴얼.md`의 승인 줄, 결과 화면 6단계 판정', '남은 것이나 순서를 승인처럼 쓰지 않는다. 승인 줄이 없으면 역할을 만들지 않는다. 칸: ' + APPROVAL_COLS + '.', '`결과/승인.csv`의 후보마다 한 줄', '사건의 후보마다 승인 줄을 원문에서 직접 연다'),
          SHOW, why='판단 규칙이 후보를 남겼다는 것은 쓸 수 있다는 뜻일 뿐 실행해도 된다는 허락이 아닙니다. 실행은 정해진 사람이 한 번 승인한 뒤에 하므로, 누가 승인하는지를 원문에서 따로 확인합니다.',
          differ=F.FIX_LOOP,
          answer=A('SOP-COOL-11 · 12 · 13의 승인 줄은 운전원(52 · 60 · 68줄)이고, 13의 4단계가 거는 핀 세척 작업지시와 SOP-COOL-14는 설비보전팀장(74줄)입니다.',
                   paste('결과/승인.csv', csv_text(CR.APPROVAL_HEADER, CR.approval_rows(), APPROVAL_COLS)), paste('결과/정한_것.csv', chosen_csv(ch)))),
        save_step(8, rec, '`조건표.csv` · `승인.csv` · `정한_것.csv` · `기대_판정.csv` · `판단기록.md`'),
    ]
    formats = ['## 결과 형식\n\n파일의 모양은 `입출력_계약.md`에 있습니다. 어떤 조건을 몇 행으로 옮길지는 원문을 읽고 직접 정합니다.\n\n'
               '- 정할 자리(「제공 빈 틀」): `결과/조건표.csv`, `결과/승인.csv`, `결과/정한_것.csv`, `결과/기대_판정.csv`, `결과/판단기록.md`.\n'
               '- 사례에 대는 일 · 원문 인용 · 남은 후보 표는 제공 코드가 결과 화면에 보입니다(`python show_result.py`).\n\n'
               '## 지킬 조건\n\n- 조건표의 행마다 원문 출처를 답니다.\n- 남은 후보를 실행 승인처럼 적지 않습니다.\n- 제공 코드(`show_result.py` · `lab_steps.py` · `condition_tools.py` · `check.py`)는 고치지 않습니다.\n']
    return dict(
        title=title, rec=rec, readonly='`자료/` · 제공 코드가', decide_step=2, course='실전반',
        goal=[f'포털 판단 규칙 화면에서 허용 · 제외된 후보를 SOP의 금지 조건과 대조했습니다. 이번에는 그 근거를 제공 SOP(HM-8 매뉴얼)에서 직접 뽑아 조치 조건표로 만들고, '
              f'판단 시스템에 등록된 결정표와 행마다 출처를 견줍니다. {incident_line(files)}',
              '조건표는 어떤 입력이 어떤 값일 때 조치를 경고 · 감점 · 제외하는지를 한 행씩 적은 판단 규칙이고, DMN(판단을 표준 모양으로 적는 방식)의 결정표 — 입력 조건과 판단 결과를 한 행씩 적은 표 — 를 이 실습에서 부르는 이름입니다. '
              '무엇을 규칙으로 옮기고 근거 없는 옛 규칙을 어떻게 둘지는 내가 정하고, 조건표를 사례에 대는 일은 제공 코드가 합니다.',
              F.STAGE_LINE.format(what='판단 지식 — 작업 기준의 조건을 판단 규칙으로 옮기는 일 — ')],
        make='만들 것: `결과/조건표.csv` · `결과/승인.csv` · `결과/정한_것.csv` · `결과/기대_판정.csv` · `결과/판단기록.md`(내가 AI와 채움). 사례 판정과 남은 후보 표는 결과 화면에 보입니다.',
        start=['`자료/HM-8_매뉴얼.md` — 제공 SOP: 현행 HM-8 1.1판(2026-09-01 시행) 냉각 계통 조치 원문. `자료/HI-01_보충매뉴얼.md` — 점검 · 이상 확인 보충 기준. `자료/작업기준.md` — 회사 작업 기준.',
               '`자료/판단시스템_결정표_내보내기.txt` — 판단 시스템에 등록된 결정표 · 스킬을 내보낸 것(2025년 도입 판, 2026-10-27 내보냄).',
               '`자료/targets.csv` — 이번 경보에서 검토하는 조치 후보 넷. `자료/사건_기록_HYD-02_1027.md` — 야간 운전원이 HMI에서 옮겨 적은 사건 메모. `자료/확인_사례.csv` — 지난 30일 경보 가운데 고른 확인 사례의 판단 입력.',
               '`입출력_계약.md` — 조건표 · 승인 표의 형식. `check.py` — 구조 검사. `condition_tools.py` — 제공 코드(고치지 않습니다).', SHOW_LINE,
               '`결과/` — 정할 자리(「제공 빈 틀」)와 README.', RULES_LINE],
        user='이 답은 야간 운전원이 경보가 났을 때 어느 조치가 남고 어느 조치가 빠지는지, 남은 조치를 누가 승인하는지 볼 때 씁니다.',
        questions=['네 조치의 경고 · 감점 · 제외 조건(입력 · 단위 · 연산자 · 경계 · 결과 · 출처)은 무엇인가?',
                   '사건과 확인 사례에서 각 후보는 남는가, 빠지는가, 무엇이 아직 모르는 값인가?', '남은 후보와 실행 승인은 어떻게 다른가 — 남은 후보마다 누가 승인하는가?'],
        decide=[('출처가 확인되지 않는 기준', '판단 시스템 결정표에 있는데 제공 SOP에서 근거 문장을 찾을 수 없는 규칙을 조건표에 어떻게 둘지 — 그런 규칙이 여럿이면 규칙마다 정하고 근거를 적습니다'),
                ('승인 역할', '원문의 승인 줄이 하나로 읽히지 않는 후보의 승인을 무엇으로 적을지')],
        outside=['원천 기록에서 판단 입력을 만드는 일과, 후보를 견주고 검토 결과로 내는 기능(다음 실습)', 'SOP 구조(적용 · 금지 · 단계 · 완료 · 승인 전체)를 만드는 일', '실제 설비 · 포털 · 업무 시스템을 부르는 일'],
        formats=formats, steps=steps,
        cases=['조건표의 숫자 기준값마다 그 값과 같거나 가장 가까운 값, 그 값의 바로 위 · 아래에서 가장 가까운 값(경계 — 같은 값이 없으면 없다고 적고 가장 가까운 사례로 경계를 본다)', '경고 · 감점 · 제외가 한 후보에 함께 맞는 경우(복수 사유)',
               '입력이 빠졌는데 이미 확인된 제외 사유가 있는 경우', '값이 비어 있어도 그 후보에는 해당 규칙이 걸리지 않는 경우(적용 대상 밖)', '「정할 것」의 결정에 따라 결과가 바뀌는 사례', '사건 한 건', '같은 명령을 다시 실행한 결과'],
        commands='python show_result.py\npython check.py',
        done=('형식 검사 통과만으로 완료하지 않습니다. 조건표의 행마다 원문 문장으로 돌아갈 수 있고, 원문에서 먼저 적은 기대 판정과 조건표를 댄 판정이 맞고, '
              '「정한 것」의 근거와 그 선택으로 바뀌는 사례를 설명할 수 있으며, 남은 후보와 실행 승인을 따로 말할 수 있으면 완료입니다.'),
        save=save, reopen='결과 화면의 단계 띠 · 사례 판정 · 남은 후보와 승인, 구조 검사 출력, `판단기록.md`의 기준일 · 저장 시점 · 확인하지 못한 점',
        tree=tree('02일차_실습5_조치조건표', [('.github/', 'Copilot 작업 규칙'), ('결과/', '정할 자리(조건표 · 승인 · 정한 것 · 기대 판정 · 판단기록 빈 틀)'),
                                         ('자료/', '매뉴얼 · 판단 시스템 결정표 · 사건 메모 · 확인 사례(읽기만)'), ('AGENTS.md', 'Codex 작업 규칙'), ('check.py', '구조 검사'),
                                         ('CLAUDE.md', '작업 규칙(같은 내용)'), ('condition_tools.py', '제공 코드'), ('lab_steps.py', '결과 화면 단계(제공)'),
                                         ('show_result.py', '결과 화면(제공)'), ('START.md', '이번 과제와 진행 단계'), ('입출력_계약.md', '조건표 · 승인 표의 형식')]),
        lead='제공 SOP의 경고 · 감점 · 제외 조건을 조치 조건표로 옮기고 근거 없는 옛 규칙을 어떻게 둘지 정한 뒤, 제공 코드가 조건표를 사건 · 확인 사례에 댄 결과와 남은 후보의 승인을 결과 화면에서 대조합니다.',
        need='VS Code와 Python, 로그인해 둔 Codex 또는 GitHub Copilot.',
        terms=('**SOP**는 표준 작업 절차입니다. ' + RESULT_KINDS + ' ' + JUDGE_WORDS + ' **미확인**은 입력이 없어 조건이 맞는지 알 수 없는 상태입니다. ' + SYSTEM_TERM + ' ' + PROVIDED_TERM + ' ' + CONTRACT_TERM),
        guide_extra={0: ['terminal', 'result'], 1: ['ai', 'review']},
        files={'입출력_계약.md': ('# 입출력 계약\n\n결과 파일의 형식과 뜻만 정한다. 무엇을 담을지는 원문에서 정한다.\n\n' + TABLE_CONTRACT + '\n' + APPROVAL_CONTRACT + '\n' + CHOSEN_CONTRACT.replace('{case_from}', CASE_FROM_CASES) + '\n' + CASES_CONTRACT).replace('{codes_from}', CODES_FROM_TARGETS),
               '결과/판단기록.md': record_template('판단 기록'), '결과/조건표.csv': TABLE_BLANK, '결과/승인.csv': APPROVAL_BLANK,
               '결과/정한_것.csv': F.CHOSEN_TEMPLATE, '결과/기대_판정.csv': expect_blank(CASE_FROM_CASES),
               '결과/README.md': '이번 과제의 정할 자리(조건표 · 승인 · 정한 것 · 기대 판정 · 판단기록)를 채우는 자리입니다. `python show_result.py`가 결과 화면 `보기.html`을 여기에 씁니다.\n'})


def pick_cases(files, kinds):
    """확인 사례 가운데 기대를 적을 두 사례: 예측 유온이 경고 기준값(55 ℃)과 같은 사례, 한 후보에 제외와 미확인이 함께 있는 사례."""
    import tempfile
    p = Path(tempfile.mkdtemp())/'c.csv'
    p.write_text(files['확인_사례.csv'], encoding='utf-8', newline='\n')
    t = Path(tempfile.mkdtemp())/'t.csv'
    t.write_text(CR.table_csv('가'), encoding='utf-8', newline='\n')
    groups, allc = CT.load_table(t), CT.case_inputs(p, kinds)
    edge = next(cid for cid, cs in allc.items() if any(x['forecast_ts1'] == 55.0 for x in cs.values()))
    both = next(cid for cid, cs in allc.items() if any((j := CT.evaluate(s, x, groups))['exclusions'] and j['unknown'] for s, x in cs.items()))
    return [edge, both]


JUDGE_DECIDE = [('빈 값의 뜻', '정해진 주기로 남아야 할 기록이 빠져 판정을 요청한 때의 값을 기록에서 바로 읽을 수 없을 때, 끊긴 구간을 이어 판단 입력을 만들지 — '
                                '어느 원천의 어느 경보에 그런 구간이 있는지, 이을 근거가 원천에 있는지는 원천에서 찾습니다'),
                ('쓰는 사람에 따라 갈리는 답', '경고가 붙은 후보를 비교 산식으로 견주는 후보에 넣을지'),
                ('비교 기준 문장', '이 비교 합계가 무엇을 견주는 값인지, 포털 성과 지표의 점수 · 실행 승인과 어떻게 다른지 내 말로')]


def alarm_line(files, alarm):
    return next(i for i, l in enumerate(files['경보_목록.csv'].splitlines(), 1) if l.startswith(alarm + ',') or f',{alarm},' in l)


def judge_answers(files, folder):
    """판정 랩 정답 토글의 내용 — 기대 판정(사건 · 카운터 끊김 경보 · 모두 제외 경보 · 경계 경보)과 기본 갈래 채움."""
    res = J.run(folder, folder/'입력/조건표.csv', J.BASE_POLICY)
    incident = next(l.split('`')[1] for l in files[MEMO].splitlines() if l.startswith('- 경보 ID'))
    pick = [incident, next(e['id'] for e in res['events'] if e.get('_counter_gap') and e['id'] != incident),
            next(e['id'] for e in res['events'] if all(c['status'] == '제외' for c in e['candidates']))]
    edges = {float(r['value']) for r in csv.DictReader(io.StringIO((folder/'입력/조건표.csv').read_text(encoding='utf-8'))) if r['input'] == 'forecast_ts1'}
    pick.append(next(e['id'] for e in res['events'] if e['id'] not in pick and any(c['inputs']['forecast_ts1'] in edges for c in e['candidates'])))
    rows = [[e['id'], c['sop'], c['status'], f'자료/경보_목록.csv:{alarm_line(files, e["id"])}; ' + (c['provenance'].get('forecast', '자료/예측_결과.csv')).replace('예측_결과.csv', '자료/예측_결과.csv')]
            for e in res['events'] if e['id'] in pick for c in e['candidates']]
    choice = [[r[0], r[1], r[2], r[3]] for r in J.choice_rows(*J.BASE_POLICY)]
    return dict(expect=expect_csv(rows, CASE_FROM_ALARMS), gap=gap_file(J.BASE_POLICY[0]), compare=compare_file(J.BASE_POLICY[1]),
                chosen=[chosen_csv(choice[:1]), chosen_csv(choice[:2]), chosen_csv(choice)])


def judge_steps(files, folder, review):
    ans = judge_answers(files, folder)
    gap_say = ('판정 요청 때 PLC가 정상 수신이고 팬 설정이 100 %면 끊긴 구간 동안 100 % 운전이 이어졌다고 보고 마지막 기록에 지난 시간을 더합니다(수집_설명.md 26줄). '
               '다른 선택(잇지 않고 값 없음)이면 사건의 SOP-COOL-11 · 12가 팬 연속 시간을 모르는 보류가 되어 1위가 바뀝니다.')
    cmp_say = ('경고는 견줄 때 남겨 두는 사유라 경고가 붙은 유지 후보도 견줍니다(HM-8.6 「다른 조치와 비교한다」). 다른 선택(경고 후보를 견주지 않음)이면 1위가 바뀌는 경보가 있습니다.')
    return [
        start_step('탐색기에서 네 자리를 찾았고, `입력/조건표.csv`가 규칙을, `자료/`의 원천 기록이 판단 입력을 담는다는 것을 파일에서 확인했습니다. 결과 화면 1단계에 경보마다 판정 요청 직전 원천 기록이 보입니다.'),
        look_step('AI에게 파일을 바꾸지 말고, 원천 네 개(경보 · PLC 상태 · 팬 카운터 · 예측)와 조건표 · 계약이 각각 무엇을 어떤 모양으로 담는지 파일:줄로 짚어 달라고 합니다. 결과 화면 1단계 표에서 판정 요청 직전 기록이 그 원천의 주기보다 오래된 경보 하나를 골라 원천 줄을 직접 엽니다.',
                  '원천마다 값이 비는 까닭이 몇 가지인지 묻습니다 — 칸이 빈 것뿐 아니라, 정해진 주기로 와야 할 기록이 오지 않은 곳(마지막 기록에서 판정 요청까지도)과 유효 시간이 지나 쓸 수 없는 값까지.',
                  H('판단 입력이 어디서 어떤 모양으로 오는지 파악한다. 아직 아무것도 만들지 않는다.', '`입력/` · `자료/` · `입출력_계약.md` · `자료/수집_설명.md`, 결과 화면 1단계',
                    '파일을 바꾸지 않는다. 해석보다 파일:줄을 먼저 받는다.', '원천마다 기록 주기 · 단위 · 시각 표기 · 값이 비는 까닭 표(칸이 빔, 와야 할 기록이 오지 않음, 유효 시간이 지남을 나눠)',
                    '원천마다 두세 줄을 내가 직접 열어 같은 내용인지 본다'),
                  '원천마다 기록 주기 · 단위 · 시각 표기와 값이 비는 까닭이 다르고, 판정을 요청한 시각까지의 기록만 써야 결과를 다시 만들 수 있습니다. '
                  '그 일반 처리(시각 맞추기 · 단위 · 하트비트 · 유효 시간)는 제공 코드가 `자료/수집_설명.md`대로 하고, 끊긴 기록을 어떻게 볼지만 내가 정합니다.'),
        S('기대 판정 먼저 적기', '② 요구',
          '`결과/기대결과.md`에 목표 · 쓰는 사람 · 지킬 조건을 적고, 사건의 네 후보와 카운터 기록이 끊긴 경보 하나, 모든 후보가 제외될 것 같은 경보 하나, 예측 값이 조건표 기준값과 같거나 가장 가까운 경계 경보 하나의 기대 판정을 원천 줄 · 조건표 · 원문으로 손으로 구해 `결과/기대_판정.csv`에 근거 줄과 함께 적습니다. 다 쓰면 「기대 칸을 쓴 시각」을 적습니다.' + F.REQ_AFTER,
          '경보는 결과 화면 1단계의 사실과 AI에게 판정 · 순위를 빼고 위치만 찾게 한 목록으로 고르고, 기대 판정은 그 줄을 열어 내가 구합니다.',
          '기대 판정마다 근거 파일:줄이 있고 결과 화면 3단계에 보입니다. 「기대 칸을 쓴 시각」이 5단계 실행보다 앞입니다. AI의 되짚기가 내 요구와 같고 바꾼 파일이 없습니다.',
          req_hint_expect('결과/기대결과.md', '목표와 질문 · 쓰는 사람 · 지킬 조건, 기대_판정.csv', CASE_FROM_ALARMS), cmd=SHOW,
          why='실행하기 전에 기대를 먼저 적어 두어야, 결과가 다를 때 판단 입력 · 판정 · 기대 가운데 어디가 틀렸는지 근거로 가릴 수 있습니다. AI가 낸 결과를 기대로 옮기면 틀린 결과도 맞아 보입니다.',
          differ=F.DIFFER_REQ.format(rec='결과/기대_판정.csv'),
          answer=A('사건 · 카운터 끊김 경보 · 모두 제외 경보 · 예측 유온이 기준값과 같은 경계 경보의 후보마다 원천 줄과 조건표로 구한 판정입니다(끊긴 기록은 판정 요청 때 PLC 팬 설정 100 %로 이어 본 판정).', paste('결과/기대_판정.csv', ans['expect']))),
        plan_step('제공 코드(`judge_tools.py`)가 판단 입력 → 판정 → 비교 → 결과 쓰기 가운데 어디서 두 정할 자리를 부르는지 AI에게 짚게 하고, 5 · 6단계 순서를 검토하고 동의합니다. 아직 파일을 만들지 않습니다.',
                  '판정에서 정보 부족(보류)을 어떤 경우에 내는지가 내 기대와 같은지 묻습니다.',
                  '사건 한 건을 계획에 대어 어느 자리 · 단계가 무엇을 내는지 짚을 수 있습니다. 계획에 제공 코드를 고치거나 규칙을 코드에 다시 적는 일이 없습니다. 계획에 내가 동의했습니다.',
                  H('정할 자리 둘과 제공 흐름의 경계를 합의한다', '`입출력_계약.md` 「정할 자리」, `결과/gap_rule.py` · `결과/compare_rule.py` 머리, `judge_tools.py`',
                    '제공 코드는 고치지 않는다. 규칙은 조건표에서 읽는다. 「이번 범위 밖」은 넣지 않는다.', '정할 자리마다 받는 값 · 돌려줄 값과 채울 순서', '사건 한 건을 계획에 대어 자리마다 무엇이 나오는지 짚게 한다'),
                  '판단 입력 · 판정 · 비교를 한 번에 만들면 결과가 다를 때 어느 부분이 틀렸는지 찾기 어렵습니다. 갈리는 판단을 자리 하나씩 정하고 결과 화면에서 확인해야 다른 줄의 원인을 한 곳으로 좁힐 수 있습니다.'),
        S('빈 값의 뜻 — 끊긴 카운터 기록', '④ 판단 · 정할 것',
          '`결과/gap_rule.py`의 함수를 AI와 채워, 카운터 기록이 판정 요청 전에 끊긴 경보의 팬 100 % 연속 시간을 내 결정대로 냅니다. 고른 것 · 근거를 `결과/정한_것.csv`에 한 줄 적고, 결과 화면에서 끊긴 경보의 값과 판정을 3단계 기대와 견줍니다.' + F.OWN_RUN,
          '끊긴 구간을 이을지, 잇는다면 원천의 무엇을 근거로 할지 내가 정합니다. AI가 결정을 대신 정하려 하면 돌려보내고 내 선택과 근거를 다시 말합니다.',
          '결과 화면 5단계의 「카운터 기록이 끊긴 경보」 표가 내 결정대로이고 값이 없으면 까닭이 붙었습니다. 「기대 판정 ↔ 판정」이 같거나 다른 줄의 까닭을 원천 줄로 말할 수 있습니다.',
          H('끊긴 카운터 기록의 팬 연속 시간을 정한다', '`자료/수집_설명.md` 팬 카운터 절, `자료/팬_운전_카운터.csv` · `자료/PLC_상태_수신.csv`, `결과/gap_rule.py` 머리의 ctx',
            '빈 값을 0이나 앞 값으로 채우지 않는다(까닭 없이). 판정 요청 시각 뒤의 기록은 쓰지 않는다. 함수 머리의 꼴을 지킨다.', '`결과/gap_rule.py`의 함수 본문과 `결과/정한_것.csv`의 빈 값의 뜻 줄',
            '결과 화면 5단계에서 사건의 값을 원천 줄과 직접 견준다'),
          SHOW, why='판단 입력은 원천마다 기록 방식이 달라, 값이 없는 입력은 0이나 앞 값으로 채우지 않고 까닭과 함께 남겨야 규칙이 무엇을 근거로 판정했는지 따라갈 수 있습니다. ' + WHY_UNKNOWN,
          differ=EXPECT_DIFFER,
          answer=A(gap_say, paste('결과/gap_rule.py', ans['gap']), paste('결과/정한_것.csv', ans['chosen'][0]))),
        S('쓰는 사람에 따라 갈리는 답 — 견줄 후보' + (' · 비교 기준 문장' if review else ''), '④ 판단 · 정할 것',
          '`결과/compare_rule.py`의 함수를 AI와 채워, 유지 후보 가운데 비교 산식으로 견주지 않을 후보와 그 까닭을 내 결정대로 냅니다. 고른 것 · 근거를 `결과/정한_것.csv`에 적고'
          + (', 이 비교 합계가 무엇을 견주는지 · 포털 성과 지표 점수 · 실행 승인과 어떻게 다른지를 「비교 기준 문장」 줄에 내 말로 적습니다.' if review else ',')
          + ' 결과 화면에서 순위와 손계산 예를 봅니다.',
          '경고가 붙은 후보를 견줄지 내가 정합니다. AI가 결정을 대신 정하려 하면 돌려보내고 내 선택과 근거를 다시 말합니다.',
          '결과 화면 6단계에 경보마다 순위와 견주지 않은 후보 · 까닭이 보이고, `지표_정의.md` 손계산 예의 네 손실이 프로그램 값과 같습니다.' + (' 7단계에 쓴 파일 목록이 보입니다.' if review else ''),
          H('견줄 후보를 정한다', '`자료/metrics/지표_정의.md`, `자료/HM-8_매뉴얼.md` HM-8.6, `자료/작업기준.md` 4절, `결과/compare_rule.py` 머리의 kept',
            '산식을 바꾸지 않는다. 견주지 않는 후보는 까닭을 남긴다. 함수 머리의 꼴을 지킨다.', '`결과/compare_rule.py`의 함수 본문과 `결과/정한_것.csv`의 줄', '손계산 예와 같은지 보고, 사건의 한 후보를 손으로 다시 계산해 견준다'),
          SHOW, why='후보마다 비용 · 생산 · 품질 · 에너지처럼 서로 다른 성과가 함께 움직이므로, 한 가지 값으로 견주려면 주어진 산식이 필요합니다. 어느 후보를 견줄지는 결과를 쓰는 사람의 일에 따라 달라질 수 있어 근거와 함께 남깁니다.',
          differ=EXPECT_DIFFER,
          answer=A(cmp_say, paste('결과/compare_rule.py', ans['compare']), paste('결과/정한_것.csv', ans['chosen'][2 if review else 1]))),
    ], ans


def judge_tail(review, rec='결과/기대결과.md'):
    outputs = '`조치검토결과.json` · `조치검토결과.md`' if review else '`result.json`'
    steps = []
    if not review:
        steps.append(S('비교 기준 문장과 결과 쓰기', '④ 판단',
                       '이 비교 합계가 무엇을 견주는 값인지, 포털 성과 지표의 점수와 어떻게 다르고 1위가 실행 승인이 아닌 까닭을 `결과/정한_것.csv`의 「비교 기준 문장」 줄에 내 말로 적고, 결과 화면이 `결과/result.json`을 쓰는지 봅니다.',
                       '내 문장이 `자료/metrics/지표_정의.md` 「포털의 성과 지표 점수」 절과 맞는지 묻습니다.',
                       '결과 화면 7단계에 `결과/result.json`을 썼다는 줄과 내 비교 기준 문장, 기대를 적은 경보의 선택 이유 · 추가로 확인할 사항이 보입니다.',
                       H('비교 합계의 뜻을 내 말로 적는다', '`자료/metrics/지표_정의.md` 18 ~ 22줄, `자료/작업기준.md` 5절', '1위를 실행 승인처럼 쓰지 않는다', '`결과/정한_것.csv`의 비교 기준 문장 줄', '사건의 선택 이유를 순위와 원천 줄로 내 말로 따라가 본다'),
                       SHOW, why='비교 합계는 후보를 견주는 계산이고 포털 성과 지표의 점수와 다른 값입니다. 1위도 실행 허가가 아닙니다 — 실행은 정해진 사람이 한 번 승인한 뒤에 합니다.',
                       differ=F.FIX_LOOP, answer=None))
    steps.append(S('사례 대조' if not review else '검토 결과 확인과 사례 대조', '⑤ 대조',
                   ('3단계에서 `결과/기대_판정.csv`에 먼저 적은 기대(사건 · 끊긴 경보 · 모두 제외 · 경계)를 8단계 대조와 견주고, 「후보마다 판정 내용」 표를 걸러 다른 사례 종류(정상 · 복수 조건 · 필수값 누락)를 더 고르면 원천 줄로 기대를 먼저 적어 더한 뒤 견줍니다. 기대와 다른 줄은 원인이 판단 입력 · 판정 · 산식 가운데 어디인지 `결과/기대결과.md`에 적습니다.'
                    if not review else
                    '결과 화면 7단계에서 `결과/조치검토결과.md`의 사건 절만 읽고 후보마다 판정 · 까닭 · 승인 역할과 먼저 확인할 값을 말해 보고, 3단계에서 `결과/기대_판정.csv`에 먼저 적은 기대(사건 · 끊긴 경보 · 모두 제외 · 경계)를 대조와 견주고, 「후보마다 판정 내용」 표를 걸러 제외 사유와 누락이 겹친 사례를 더 고르면 원천 줄로 기대를 먼저 적어 더한 뒤 견줍니다. 다른 줄의 원인을 `결과/기대결과.md`에 적습니다.'),
                   '다른 줄의 원인이 판단 입력 · 판정 · 산식 가운데 어디인지 묻습니다.',
                   '사례 종류마다 원천 줄을 연 경보가 하나 이상 있고, 「기대 판정 ↔ 판정」의 다른 줄마다 원인이 `결과/기대결과.md`에 있습니다.',
                   H('사례 종류마다 기대와 실제를 견준다', '결과 화면의 기준값 표 · 모두 제외 경보 · 대조표, `결과/기대_판정.csv`', '결과에 맞추려고 기대를 바꾸지 않는다. 기대를 고치면 근거를 남긴다.', '`결과/기대결과.md`의 다른 줄과 원인', '종류마다 한 사례는 원천 줄에서 다시 손으로 구해 본다'),
                   SHOW, why='사건 한 건이 맞아도 다른 경보에서 틀릴 수 있습니다. 경계값 · 모두 제외 · 값 누락처럼 결과가 갈리는 종류를 지난 경보 전체에서 골라 대조해야 기능을 다른 경보에도 쓸 수 있습니다.',
                   differ=EXPECT_DIFFER))
    steps.append(save_step(0, rec, outputs + ' · `정한_것.csv` · `기대_판정.csv` · `기대결과.md`'))
    return steps


def judge_record():
    return record_template('기대 결과와 실제 대조', '## 기대 칸을 쓴 시각\n\n- 기대 칸을 쓴 시각(실행 전, 내 PC 시계 그대로):\n- 5단계에서 내 판단 함수로 처음 실행한 시각(내 PC 시계 그대로 — 1단계의 결과 화면 열기는 세지 않음):\n\n'
                           '## 다른 줄과 원인\n\n| 사례 / 후보 | 기대 | 실제 | 원인(판단 입력 · 판정 · 산식) · 고친 점 |\n|---|---|---|---|\n| | | | |\n\n')


def judge_lab(files, folder):
    """통합반 03회차 실습3 — 설비 조건별 최적의 조치를 비교하는 판단 기능 만들기."""
    title = TITLES['integrated-03-judge']
    n = sum(1 for r in csv.DictReader(io.StringIO(files['경보_목록.csv'])) if r['구분'] == 'RAISE' and r['판정_요청_시각'])
    steps, ans = judge_steps(files, folder, review=False)
    tail = judge_tail(False)
    tail[0]['answer'] = A('비교 합계는 네 손실과 감점의 합계(작을수록 유리)이고, 포털 성과 지표의 정책 점수와 다른 값이며 순위는 실행 승인이 아닙니다.',
                          paste('결과/정한_것.csv', ans['chosen'][2]))
    steps += tail
    save = ('`결과/result.json` · 정할 자리 · `결과/기대결과.md`를 함께 보관합니다. 다음 실습에 넘길 것은 이 결과와, 받은 그대로의 `입력/조건표.csv` · `입력/sop.json`입니다. '
            '다음 실습 「문서에서 근거 있는 지식을 추출하는 기능 만들기」에서는 조건의 원문 근거를 검토합니다. ' + USB)
    return judge_common(title, 'integrated-03-judge', files, steps, n, save, review=False)


def review_lab(files, folder):
    """실전반 03회차 실습2 — 판정·성과 비교를 조치 검토 결과로 완성하기."""
    title = TITLES['practical-03-review']
    n = sum(1 for r in csv.DictReader(io.StringIO(files['경보_목록.csv'])) if r['구분'] == 'RAISE' and r['판정_요청_시각'])
    steps, ans = judge_steps(files, folder, review=True)
    steps += judge_tail(True)
    save = ('`결과/조치검토결과.json` · `결과/조치검토결과.md` · 정할 자리 · `결과/기대결과.md`를 함께 보관합니다. 다음 실습에 넘길 것은 이 검토 결과와, 받은 그대로의 `입력/조건표.csv` · `입력/sop.json`입니다. '
            '다음 실습은 「문서에서 작업 조건과 근거를 추출하는 기능 만들기」입니다. ' + USB)
    return judge_common(title, 'practical-03-review', files, steps, n, save, review=True)


def judge_common(title, key, files, steps, n, save, review):
    out = '`결과/조치검토결과.json` · `결과/조치검토결과.md`' if review else '`결과/result.json`'
    formats = ['## 결과 형식\n\n파일의 모양은 `입출력_계약.md`에 있습니다. 끊긴 기록을 어떻게 볼지와 어느 후보를 견줄지는 원천과 원문을 읽고 직접 정합니다.\n\n'
               '- 정할 자리(「제공 빈 틀」): `결과/gap_rule.py` · `결과/compare_rule.py`(빈 함수), `결과/정한_것.csv`, `결과/기대_판정.csv`, `결과/기대결과.md`.\n'
               f'- {out} — 제공 코드 `judge_tools.py`가 정할 자리를 불러 씁니다(`python show_result.py`).\n\n'
               '## 지킬 조건\n\n- `입력/`은 읽기만 합니다.\n- 규칙은 `입력/조건표.csv`에서 읽습니다(제공 코드가 읽습니다 — 정할 자리에 규칙을 다시 적지 않습니다).\n'
               + ('- 비교 순위와 검토 의견을 실행 승인처럼 적지 않습니다.\n' if review else '- 비교 순위와 선택 이유를 실행 승인처럼 적지 않습니다.\n')
               + '- 제공 코드(`show_result.py` · `lab_steps.py` · `judge_tools.py` · `condition_tools.py` · `check.py`)는 고치지 않습니다.\n']
    goal_head = ('포털에서 운전 모드와 설비 상태를 바꿔 판단을 다시 돌리고, 조건별 손익에서 순위가 바뀌는 것을 봤습니다. 포털은 사실을 자동으로 모아 한 건씩 판단했습니다. '
                 f'이번에는 같은 일을 원천 기록에서 직접 하고, 지난 30일 경보 전체로 기능을 검증합니다. {incident_line(files)}'
                 if not review else
                 '포털에서 순위가 높아도 금지 조건에 걸리면 고를 수 없는 이유를 결과에서 찾았습니다. 이번에는 조치 조건표로 사건과 지난 30일 경보를 원천 기록에서 직접 판정하고, '
                 f'담당자가 읽고 바로 결정할 수 있는 조치 검토 결과로 완성합니다. {incident_line(files)}'.replace('포틸', '포털'))
    goal = [goal_head,
            '판정 기능은 조건표를 읽어 후보마다 경고 · 감점 · 제외와, 입력이 없어 맞는지 알 수 없는 정보 부족을 이유와 함께 내고, 허용 후보만 주어진 비교 산식으로 견줍니다'
            + (' — 조치 검토 결과는 후보마다 그 판정과 이유 · 원문 출처 · 추가로 확인할 값 · 승인 역할을 담습니다. ' if review else '. ')
            + f'판단 입력은 원천 네 곳(경보 · PLC 상태 · 팬 카운터 · 예측)에 흩어져 있고, 경보 {n}건마다 후보가 넷이라 손으로 다 맞출 수 없습니다.',
            '원천 읽기 · 시각 · 단위 · 판정 · 산식 · 결과 쓰기는 제공 코드가 하고, 끊긴 기록을 어떻게 볼지와 어느 후보를 견줄지 — 쓰는 사람에 따라 방향이 갈리는 판단 — 는 내가 정할 자리에 AI와 구현합니다.',
            F.STAGE_LINE.format(what='판단 지식 — 조건표로 조치를 판정하고 견주는 일 — ')]
    user = ('이 답은 야간 운전원이 경보가 났을 때 네 후보를 쓸 수 있는지, 견준 후보 가운데 무엇이 1위이고 왜인지, 아직 무엇을 확인해야 하는지 볼 때 씁니다.' if not review else
            '이 답은 야간 운전원과 설비보전팀장이 이 검토 결과만 읽고 어느 후보를 승인 요청할지, 무엇을 먼저 확인할지 정할 때 씁니다.')
    questions = (['사건의 네 후보 — 판단 입력(원천 네 개, 판정을 요청한 시각 기준) · 판정(유지 · 제외 · 보류와 이유) · 비교값과 순위는 무엇인가?',
                  '같은 기능이 지난 경보의 정상 · 경계 · 복수 조건 · 모두 제외 · 필수값 누락 사례에서 기대와 같은가?',
                  '사건에서 1위는 무엇이고 그 까닭과 추가로 확인할 사항은 무엇인가? 이 비교값은 포털 성과 지표의 점수와 어떻게 다른가?'] if not review else
                 ['사건의 네 후보 — 판단 입력(원천 네 개, 판정을 요청한 시각 기준) · 판정(유지 · 제외 · 보류와 이유) · 비교값과 순위는 무엇인가?',
                  '같은 기능이 지난 경보의 경계값 · 제외 사유와 누락이 겹친 입력 · 모두 제외된 입력에서 기대와 같은가?',
                  '사건에서 승인 요청을 검토할 후보와 그 까닭은 무엇인가? 후보마다 이유 · 원문 출처 · 추가로 확인할 값 · 승인 역할은 무엇이고, 비교 순위는 실행 승인과 어떻게 다른가?'])
    cases = (['규칙이 하나도 맞지 않는 후보(정상)', '조건표의 숫자 기준값마다(예측 유온 · 팬 연속 시간 등) 그 값과 같은 후보와, 그 값의 바로 위 · 아래에서 가장 가까운 후보(경계 — 단위가 다른 원천 포함)',
              '경고 · 감점 · 제외가 한 후보에 함께 맞는 경우(복수 조건 — 감점이 규칙마다 한 번인지)', '모든 후보가 제외된 경보', '원천에서 값이 비는 까닭이 서로 다른 경보(필수값 누락 — 그 값이 필요한 규칙에만 영향이 가는지)',
              '「정할 것」의 결정에 따라 판단 입력 · 순위가 바뀌는 경보', '`자료/metrics/지표_정의.md`의 손계산 예', '같은 명령을 다시 실행한 결과'] if not review else
             ['조건표의 숫자 기준값마다(예측 유온 · 팬 연속 시간 등) 그 값과 같은 후보와, 그 값의 바로 위 · 아래에서 가장 가까운 후보(경계값 — 단위가 다른 원천 포함)',
              '확인된 제외 사유와 입력 누락이 한 후보에 겹친 경우', '모든 후보가 제외된 경보', '원천에서 값이 비는 까닭이 서로 다른 경보(그 값이 필요한 규칙에만 영향이 가는지)',
              '「정할 것」의 결정에 따라 검토 의견이 바뀌는 경보', '`자료/metrics/지표_정의.md`의 손계산 예', '같은 명령을 다시 실행한 결과'])
    done = ('형식 검사나 실행 성공만으로 완료하지 않습니다. 사례 종류마다 실행 전에 적은 기대와 실행 결과가 같거나 다른 까닭을 찾아 적은 기록이 있고, 손계산 예의 네 손실이 프로그램 값과 같으며, '
            + ('사건의 절만 읽고 후보마다 판정 · 까닭 · 승인 역할 · 먼저 확인할 값을 말할 수 있고, ' if review else '')
            + '「정한 것」의 근거와 그 선택으로 바뀌는 판단 입력 · 순위를 설명할 수 있으면 완료입니다.')
    contract = ('# 입출력 계약\n\n입력 · 정할 자리 · 결과 파일의 형식과 뜻만 정한다. 판정 원칙은 원문(`자료/HM-8_매뉴얼.md` · `자료/작업기준.md` · `자료/HI-01_보충매뉴얼.md`), 원천의 기록 방식은 `자료/수집_설명.md`에 있다.\n\n'
                + JUDGE_INPUT_CONTRACT + judge_table_contract() + '\n' + PLACE_JUDGE_CONTRACT + '\n' + CHOSEN_CONTRACT.replace('{case_from}', CASE_FROM_ALARMS) + '\n' + (REVIEW_RESULT if review else JUDGE_RESULT))
    lab_name = LABS[key].name
    return dict(
        title=title, rec='결과/기대결과.md', readonly='`입력/` · `자료/` · 제공 코드가', decide_step=2, course='실전반' if review else '통합반',
        goal=goal, make=f'만들 것: 정할 자리 둘(`결과/gap_rule.py` · `결과/compare_rule.py`), `결과/정한_것.csv` · `결과/기대_판정.csv` · `결과/기대결과.md`(내가 AI와 채움), {out}(제공 코드가 씀).',
        start=['`입력/조건표.csv` · `입력/sop.json` — 냉각 계통 조치의 조건표와 SOP 구조. ' + ('2회차 조치 조건표 실습' if review else '조치 기준 만들기 실습') + '의 결과와 같은 꼴로 검증해 제공하는 판입니다.', MINE[key],
               '`자료/경보_목록.csv` · `자료/PLC_상태_수신.csv` · `자료/팬_운전_카운터.csv` · `자료/예측_결과.csv` — 판단 입력의 원천 네 개(HYD-01 ~ 03, 2026-09-28 ~ 10-27). 기록 방식은 `자료/수집_설명.md`에 있습니다.',
               '`자료/오더_현황.csv` · `자료/metrics/` — 주어진 비교 산식(`지표_정의.md`)과 그 값.',
               '`자료/HM-8_매뉴얼.md` · `자료/HI-01_보충매뉴얼.md` · `자료/작업기준.md` — 조치 원문 · 보충 기준 · 회사 작업 기준. `자료/targets.csv` — 경보마다 검토하는 조치 후보 넷.',
               '`입출력_계약.md` — 입력 · 정할 자리 · 결과 파일의 형식. `check.py` — 구조 검사. `judge_tools.py` · `condition_tools.py` — 제공 코드(고치지 않습니다).', SHOW_LINE,
               '`결과/` — 정할 자리(「제공 빈 틀」)와 README.', RULES_LINE],
        user=user, questions=questions, decide=JUDGE_DECIDE,
        outside=['조건표 · SOP 구조를 고치는 일(입력은 읽기만 합니다)', '원문에서 작업 조건을 뽑거나 조건의 원문 근거를 다시 검토하는 일(다음 실습)', '비교 산식을 바꾸는 일', '실제 설비 조작과 실행 승인'],
        formats=formats, steps=steps, cases=cases, commands='python show_result.py\npython check.py', done=done, save=save,
        reopen='결과 화면의 단계 띠 · 대조표와 구조 검사 출력, `기대결과.md`의 다른 줄 · 기준일 · 저장 시점 · 확인하지 못한 점',
        tree=tree(lab_name, [('.github/', 'Copilot 작업 규칙'), ('결과/', '정할 자리(빈 함수 둘 · 정한 것 · 기대 판정 · 기대결과 빈 틀)'),
                             ('입력/', '조건표와 SOP 구조(읽기만)'), ('자료/', '판단 입력의 원천 · 비교 산식 · 원문(읽기만)'),
                             ('AGENTS.md', 'Codex 작업 규칙'), ('check.py', '구조 검사'), ('CLAUDE.md', '작업 규칙(같은 내용)'), ('condition_tools.py', '제공 코드'),
                             ('judge_tools.py', '제공 코드'), ('lab_steps.py', '결과 화면 단계(제공)'), ('show_result.py', '결과 화면(제공)'),
                             ('START.md', '이번 과제와 진행 단계'), ('입출력_계약.md', '입력 · 정할 자리 · 결과의 형식')]),
        lead=('원천 기록에서 판단 입력을 만들고 조건표로 판정 · 비교하는 제공 흐름에, 방향이 갈리는 판단 두 자리를 내가 구현해 끼우고 결과 화면에서 기대 · 원천 줄과 대조합니다.'
              + (' 결과는 담당자가 읽는 조치 검토 결과로 나옵니다.' if review else '')),
        need='VS Code와 Python, 로그인해 둔 Codex 또는 GitHub Copilot.',
        terms=(RESULT_KINDS + ' ' + JUDGE_WORDS + ' **판단 입력**은 규칙이 견주는 값(예측 유온 · 운전 모드 · 팬 연속 시간 등)이고 **원천**은 그 값이 기록된 곳, **비교 합계**는 주어진 산식의 네 손실과 감점을 더한 값입니다. '
               + ('**검토 의견**은 사례마다 승인 요청을 검토할 후보와 그 까닭, 먼저 확인할 값입니다. ' if review else '') + PROVIDED_TERM + ' ' + CONTRACT_TERM),
        first_more=[MINE[key]], guide_extra={0: ['terminal', 'result'], 1: ['ai', 'review']},
        files={'입출력_계약.md': contract, '결과/기대결과.md': judge_record(), '결과/gap_rule.py': GAP_BLANK, '결과/compare_rule.py': COMPARE_BLANK,
               '결과/정한_것.csv': F.CHOSEN_TEMPLATE, '결과/기대_판정.csv': expect_blank(CASE_FROM_ALARMS),
               '결과/README.md': f'이번 과제의 정할 자리(빈 함수 둘 · 정한 것 · 기대 판정 · 기대결과)를 채우는 자리입니다. `python show_result.py`가 {out.replace("`결과/", "`")}와 결과 화면 `보기.html`을 여기에 씁니다.\n',
               '입력/README.md': '냉각 계통 조치의 조건표(조건표.csv)와 SOP 구조(sop.json)입니다. 조건표의 형식은 입출력_계약.md에 있습니다. 이 폴더는 읽기만 합니다.\n\n' + SOP_KEYS})


# ───────────── 판정 랩 계약 ─────────────
JUDGE_INPUT_CONTRACT = '''## 입력

- `입력/조건표.csv` — 조건표(아래 「조건표」). 제공 코드는 규칙을 이 파일에서 읽는다. 열 이름이 계약과 다르면 파일 · 행을 밝혀 멈춘다.
- `입력/sop.json` — SOP 구조(적용 조건 · 금지 조건 · 수행 단계 · 완료 기준 · 승인과 원문 출처). 키의 뜻은 `입력/README.md`에 있다.
- `자료/`의 원천 네 개(`경보_목록.csv` · `PLC_상태_수신.csv` · `팬_운전_카운터.csv` · `예측_결과.csv`), `자료/오더_현황.csv`, `자료/metrics/`(`지표_정의.md` · `업무_값.json` · `후보_설정.csv`).
- 내 앞 결과를 쓸 때는 `결과/내_입력/`에 같은 이름으로 둔다. 제공 코드와 구조 검사는 그 폴더에 있는 파일을 기준으로 본다.

## 판단 입력

- 경보 하나(`경보_목록.csv`의 RAISE 행)가 사례 하나이고, 사례마다 `자료/targets.csv`의 후보를 판정한다.
- 후보마다 아래 「조건표」의 입력 이름 일곱 개를 모두 만든다(조건표가 지금 쓰지 않는 입력도). 단위는 그 표의 단위다.
- `skill_kind` · `skill_code`는 `targets.csv`의 `kind` · `codes`(`;`로 나눈 목록)다.
- 값을 정할 수 없는 입력은 `null`이고, 왜 없는지(원천 · 시각)를 함께 적는다.

'''

SOP_KEYS = ('sop.json 키의 뜻: `document` 원문 문서, `failure_modes` 고장 유형, `causes` 원인, `sops` 조치 절차(`id` · `name` 이름 · `kind` 조치 종류(없으면 null) · `codes` 실행 코드 · `source` 출처 · '
            '`failure_mode` 고장 유형 · `model_refs` 모델 참조 · `apply_conditions` 적용 조건 · `prohibitions` 금지 조건 · `steps` 수행 단계 · `completion` 완료 기준 · `approval` 승인(`role` 역할)), '
            '`relations` 관계 목록. 항목마다 `text`는 원문 문장, `rules`는 그 조건을 옮긴 조건표의 `rule_id`다.\n')


def judge_table_contract():
    head, body = TABLE_CONTRACT.replace('{codes_from}', CODES_FROM_TARGETS).split('\n\n', 1)
    body = body.split('\n\n', 1)[1].split('모양을 보이는 한 줄')[0].rstrip()
    return '## 조건표 (`입력/조건표.csv`)\n\n' + body + '\n'


CANDIDATE_SHAPE = '''```
{"sop": "SOP-...", "status": "유지 | 제외 | 보류",
 "inputs": {"forecast_ts1": 숫자 또는 null, "forecast_ps1": ..., "fan100_hours": ..., "plc_mode": ..., "plc_state": ..., "skill_kind": ..., "skill_code": [...]},
 "missing_reasons": {"null인 입력": "왜 없는지(원천 · 시각)"},
 "warnings":   [ {"rule_id": "...", "reason": "...", "source_section": "...", "conditions": [ {"input": "...", "actual": 값, "operator": "...", "value": "...", "unit": "..."} ]} ],
 "penalties":  [ {위와 같음, "penalty_manwon": 숫자} ],
 "exclusions": [ {위와 같음} ],
 "unknown":    [ {"rule_id": "...", "result": "...", "missing": ["빠진 입력"], "source_section": "..."} ],
 "comparison": {"cost": 0, "production": 0, "quality": 0, "energy": 0, "penalty": 0, "total": 0} 또는 null,
 "no_comparison_reason": ["유지 후보인데 비교값이 없는 까닭"]}
```'''

COMMON_RESULT_NOTES = '''- 키의 뜻: `comparison_basis` 비교 기준 문장, `decisions` 정한 것(`item` 항목 · `decision` 정한 방법 · `basis` 근거), `decision_time` 판정을 요청한 시각, `status` 판정,
  `inputs` 판단 입력, `missing_reasons` 값이 없는 까닭, `comparison` 비교값(`cost` 비용 · `production` 생산 · `quality` 품질 · `energy` 에너지 · `penalty` 감점 · `total` 합계, 만원),
  `no_comparison_reason` 비교값이 없는 까닭, `rank` 순위.
- 사례의 순서는 `자료/경보_목록.csv`의 RAISE 행 순서, 후보의 순서는 `자료/targets.csv`의 순서다.
- `status`는 `유지` · `제외` · `보류` 가운데 하나이고, 세 말의 뜻은 `자료/작업기준.md` 4절의 말이다.
- `comparison`이 있는 후보는 `유지` 후보다. 비교값이 없는 유지 후보는 `no_comparison_reason`에 그 까닭을 적는다.
- 금액은 `지표_정의.md` 식의 원값을 소수 둘째 자리로 반올림해 적고, `total`은 네 손실과 감점의 원값을 더한 뒤 반올림한다.
  반올림은 사사오입이다 — 셋째 자리가 5 이상이면 올린다(0.125는 0.13). 부동소수 계산의 작은 오차로 끝자리 5가 4999…가 되어 내려가지 않게 한다.
- 순위는 비교값이 있는 후보마다 하나이고 `total`이 작은 순서다. 같은 `total`은 같은 순위다(1, 1, 3).
'''

JUDGE_RESULT = '''## 결과 (`결과/result.json` — 제공 코드가 쓴다)

```
{
  "comparison_basis": "이 비교 합계가 무엇을 견주는 값인지, 포털 성과 지표의 점수와 어떻게 다른지",
  "decisions": [ {"item": "...", "decision": "판단 입력을 만든 방법 · 견주는 후보 등 정한 것", "basis": "파일 · 절"} ],
  "events": [
    {"id": "경보_ID", "asset": "HYD-..", "decision_time": "판정_요청_시각",
     "candidates": [ 후보 판정 ],
     "ranking": [ {"rank": 1, "sop": "...", "total": 0.0} ],
     "selection": {"reason": "1위를 고른 까닭 또는 순위가 없는 까닭", "checks": ["추가로 확인할 사항"]}}
  ]
}
```

후보 판정:

''' + CANDIDATE_SHAPE + '''

''' + COMMON_RESULT_NOTES + '''- 이 결과만의 키: `warnings` 경고 · `penalties` 감점 · `exclusions` 제외(맞은 규칙과 조건마다 실제 값 `actual`), `penalty_manwon` 감점 금액(만원),
  `unknown` 입력이 없어 맞는지 알 수 없는 규칙(`missing` 빠진 입력), `ranking` 순위 목록, `selection` 고른 까닭(`reason` · `checks`).
- `ranking`은 사례마다 비교값이 있는 후보의 순위 목록이고 `total`은 그 후보의 `comparison.total`과 같다.
- `selection`의 `reason`은 1위를 고른 까닭(순위가 없으면 그 까닭), `checks`는 실행 전후에 추가로 확인할 사항이다.
'''

REVIEW_RESULT = '''## 결과 (`결과/조치검토결과.json` · `결과/조치검토결과.md` — 제공 코드가 쓴다)

```
{
  "comparison_basis": "이 비교 합계가 무엇을 견주는 값인지, 포털 성과 지표의 점수 · 실행 승인과 어떻게 다른지",
  "decisions": [ {"item": "...", "decision": "판단 입력을 만든 방법 · 견주는 후보 등 정한 것", "basis": "파일 · 절"} ],
  "events": [
    {"id": "경보_ID", "asset": "HYD-..", "decision_time": "판정_요청_시각",
     "candidates": [
       {"sop": "SOP-...", "status": "유지 | 제외 | 보류",
        "inputs": {"forecast_ts1": 숫자 또는 null, ...},
        "missing_reasons": {"null인 입력": "왜 없는지(원천 · 시각)"},
        "reasons": [ {"rule_id": "...", "result": "WARN | PENALTY | EXCLUDE | 미확인", "actual_inputs": {"입력": 값}, "expression": "식", "source": "...",
                      "missing_inputs": ["미확인일 때"], "missing_reason": "미확인일 때 원천의 사정"} ],
        "sources": ["..."],
        "checks": ["..."],
        "comparison": {"cost": 0, "production": 0, "quality": 0, "energy": 0, "penalty": 0, "total": 0} 또는 null,
        "no_comparison_reason": ["유지 후보인데 비교값이 없는 까닭"],
        "rank": 1 또는 null,
        "approval": {"role": "...", "source": "...", "note": "..."}}
     ],
     "review": {"top": ["..."], "reason": "...", "checks": ["..."]}}
  ]
}
```

''' + COMMON_RESULT_NOTES + '''- 이 결과만의 키: `reasons` 후보의 이유(맞은 규칙과, 입력이 없어 맞는지 알 수 없는 규칙 `미확인`) — `actual_inputs` 실제 입력 · `expression` 비교식 · `source` 출처 · `missing_inputs` 빠진 입력 · `missing_reason` 빠진 까닭,
  `sources` 원문 출처, `checks` 추가로 확인할 값, `approval` 승인(`role` 역할 · `source` 출처 · `note` 안내), `review` 검토 의견(`top` 승인 요청을 검토할 후보 · `reason` 까닭 · `checks` 먼저 확인할 값).
- `reasons`의 `result`가 `미확인`이면 `missing_inputs`와 `missing_reason`을 적는다.
- `sources`는 이유에 쓴 규칙의 출처와 그 후보 SOP의 절이다.
- `checks`에는 미확인 규칙의 빠진 입력마다 그 입력 이름과 다시 받을 곳을 적고, 유지 후보는 실행 전에 확인할 조건 · 완료 기준(`입력/sop.json`)을 적는다.
- `approval`은 그 후보의 승인 역할과 출처(`입력/sop.json`)와, 순위가 실행 승인이 아니라는 안내다.
- `review.top`은 비교 순위 1위 후보(없으면 빈 목록)이고, `reason`은 그 까닭 또는 순위가 없는 까닭, `checks`는 담당자가 먼저 확인할 값이다.
- `결과/조치검토결과.md`는 같은 내용을 사례마다 절로 나눠 사람이 읽게 쓴다. 절 제목에 경보 ID를 넣는다.
'''


# 랩마다 넣는 원자료(대조에 쓰는 파일만 — K-3). (자료 안 경로, 코어의 이름)
DATA = {
    'integrated-03-criteria': [('HM-8_매뉴얼.md',) * 2, ('HM-8_1.0판_매뉴얼.md',) * 2, ('HI-01_보충매뉴얼.md',) * 2, ('작업기준.md',) * 2,
                               (EXPORT,) * 2, ('작업지시_이력.csv',) * 2, (MEMO,) * 2, ('확인_사례.csv',) * 2, ('targets.csv', 'targets_sop.csv'), ('failuremodes.csv',) * 2],
    'practical-02-conditions': [('HM-8_매뉴얼.md',) * 2, ('HI-01_보충매뉴얼.md',) * 2, ('작업기준.md',) * 2, (EXPORT,) * 2, (MEMO,) * 2, ('확인_사례.csv',) * 2, ('targets.csv',) * 2],
}
DATA['integrated-03-judge'] = DATA['practical-03-review'] = [
    (name,) * 2 for name in ['HM-8_매뉴얼.md', 'HI-01_보충매뉴얼.md', '작업기준.md', '수집_설명.md', 'targets.csv', '경보_목록.csv', 'PLC_상태_수신.csv',
                             '팬_운전_카운터.csv', '예측_결과.csv', '오더_현황.csv', 'metrics/지표_정의.md', 'metrics/업무_값.json', 'metrics/후보_설정.csv']]
BUILDERS = {'integrated-03-criteria': criteria_lab, 'integrated-03-judge': judge_lab, 'practical-02-conditions': conditions_lab, 'practical-03-review': review_lab}


def criteria_inputs(folder):
    """통합03 기존 형식은 보존하고 통합02의 영문 경로 변환 외 내용이 같은지 본다."""
    from session2_project import convert
    schema, graph = B.reference_model(False, B.LAB4_INPUT_BRANCH['통합반'])
    F.dump(folder/'입력/schema.json', B.student_schema(schema))
    F.dump(folder/'입력/graph.json', graph)
    write(folder/'입력/자료/설비_대장.csv', D2._csv(D2.ASSET_COLS, D2.asset_rows()))
    diff = []
    for rel, current in [('schema.json', 'model/schema.json'), ('graph.json', 'model/graph.json'), ('자료/설비_대장.csv', 'equipment.csv')]:
        src = LAB4_INPUT/current
        if not src.is_file():
            raise RuntimeError(f'2회차 실습4 입력 {rel}이 없습니다 — 2회차 생성기로 먼저 만듭니다.')
        if src.read_text(encoding='utf-8-sig') != convert((folder/'입력'/rel).read_text(encoding='utf-8-sig')):
            diff.append(rel)
    if diff:
        raise RuntimeError(f'통합 03 실습2 입력이 2회차 실습4 입력과 다릅니다: {diff} — 2회차 생성기와 판을 맞춘 뒤 다시 만듭니다.')


def judge_inputs(folder):
    """판정 랩 입력/ = 조건 랩의 강사 검증 판(지점1 가 · 지점2 가)."""
    write(folder/'입력/조건표.csv', CR.table_csv(CR.BASE[1]))
    write(folder/'입력/sop.json', CR.sop_json(*CR.BASE))


NEW_GENERATOR = {   # 네 랩은 새 프로젝트 구조로 바뀌었다 — 학생 폴더 · ZIP · package-index는 build_session3_projects.py가 쓴다
    'integrated-03-criteria': 'build_session3_projects.py criteria --apply [--completed]',
    'integrated-03-judge': 'build_session3_projects.py judge --apply [--completed]',
    'practical-02-conditions': 'build_session3_projects.py conditions --apply [--completed]',
    'practical-03-review': 'build_session3_projects.py review --apply [--completed]',
}


def main(argv=None):
    raise SystemExit('build_judgement_labs.py는 학생 랩을 만들지 않습니다(옛 구조 정본 자리는 지웠다). 랩은 새 생성기로 만듭니다:\n'
                     + '\n'.join(f'  {key}: {how}' for key, how in NEW_GENERATOR.items()))


if __name__ == '__main__':
    sys.exit(main())
