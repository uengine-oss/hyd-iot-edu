"""G9 (전체 과정 랩업 — capstone-lab.md 5.2): 에이전트 실행의 고정 규칙 = 공통부 + 업무부. 워커가 CLI 에 시스템 지시로 붙여 넘기고
(worker/runner.py --append-system-prompt), 포털 에이전트 화면이 같은 글을 보인다(rule_card).

공통부는 어느 업무든 이 플랫폼에서 일하는 에이전트에 맞는 것이다: 작업 폴더 밖 금지 · 도구로 확인 · 근거 인용 · 지어내지 않기 · 승인 전 쓰기 금지.
제품 cli-agent 의 고정 규칙(process-gpt services/cli-agent/executor.py 501~516행 `_instructions`)도 업무 없는 공통 줄만 넣는다.
업무부는 한 업무에만 맞는 것이다(예: HYD 설비 — 어느 MCP 에서 무엇을 읽는지, 노드 id 체계, 업무 DB SQL 규칙, 설비 명령 금지).

작업 한 건의 지시는 여기 두지 않는다 — 작업 지시(worker/prompt.py) 한 곳이 갖는다: 결과 제출 형식과 보류 객체(폼마다 다름 — output_contract ·
DEFERRAL_RULE), 언어 · 이름 쓰기(LANGUAGE_RULE — 이어 하기 · 형식 교정 지시에도 다시 붙는다), 작업 디렉터리와 스키마 설명 파일 자리,
파일 읽기 · 쓰기 도구(FILE_READ_RULE). 셸 · Python 실행은 워커가 막는다(settings.BLOCKED_SHELL_TOOLS) — 실행 안내를 쓰지 않는다.

업무부는 에이전트 칸 users.work_rules(키)로 고른다. 키가 없으면 공통부만 넣고, 워커가 그 사실을 처리 기록에 남긴다(조용한 기본 업무 없음).
모르는 키는 실행 실패다(다른 업무 규칙으로 대신하지 않음). 기준 에이전트(sys:agent · agent:cooling · agent:pm-plan · agent:spare-buy,
seed.sql)는 'hyd-plant', 교대 인수인계 에이전트는 'hyd-handover'.
이 모듈은 워커 이미지에도 복사된다(it/agent-worker/Dockerfile) — 표준 라이브러리만 쓴다.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

COMMON_TITLE = "ProcessGPT 업무 에이전트 작업 규칙"


@dataclass(frozen=True)
class BusinessRules:
    """업무부 — 공통부의 정해진 자리에 들어간다. 각 칸은 그 자리의 원문 그대로(줄바꿈 · 들여쓰기 포함)."""
    key: str
    title: str              # 제목 앞머리 — "# <title> — ProcessGPT 업무 에이전트 작업 규칙"
    tool_sources: str       # '도구로 확인' 항목 뒤에 이어 쓰는 글: 무엇을 어느 도구에서 읽는지
    citation: str           # 근거 인용 항목(이 업무의 id 체계) — 공통 인용 항목 대신
    reassessment: str       # '반드시' 끝 항목: 다시 평가 · 보완 요청을 받았을 때 무엇을 새로 읽는가
    sections: str           # 업무 고유 절(앞뒤 빈 줄은 조립이 넣는다)
    forbidden_effects: str  # '절대 금지'의 승인 전 쓰기 항목(이 업무의 쓰기 이름으로) — 공통 항목 대신
    forbidden_extra: str    # '절대 금지'의 업무 고유 항목


# ---------------------------------------------------------------- 공통부
_INTRO = "당신은 ProcessGPT 업무 프로세스 안에서 실행되는 에이전트입니다. 프로세스 인스턴스의 한 작업(todolist 한 줄)만 맡습니다."
_WORKSPACE = "- 작업 디렉터리 밖의 파일을 읽거나 수정하지 마세요. 홈 디렉터리(`~/.claude` 등)를 찾아보지 마세요."
_TOOLS = "- 연결된 MCP 도구가 있으면 추측 대신 도구로 확인하세요."
_CITATION = "- 모든 판단에 근거(도구 응답 · 지식 그래프 노드 id · 문서 구절)를 인용합니다."
_NO_INVENTION = "- 확실하지 않은 값을 지어내지 말고, 모르면 모른다고 결과에 적으세요. 조회 실패와 값 없음을 구분합니다."
_FORBIDDEN_HEAD = "## 절대 금지"
_FORBIDDEN_EFFECTS = "- 업무 시스템 쓰기(메일 · 일정 · 기록 등)와 사람 대신 승인. 사람이 승인하기 전에는 어떤 조치도 실행하지 않습니다."


def constitution(rules: BusinessRules | None) -> str:
    """실행의 고정 규칙 글. rules None = 공통부만."""
    r = rules
    tools = _TOOLS + (" " + r.tool_sources if r else "")
    musts = [_WORKSPACE, tools, r.citation if r else _CITATION, _NO_INVENTION, *([r.reassessment] if r else [])]
    blocks = [f"# {r.title} — {COMMON_TITLE}" if r else f"# {COMMON_TITLE}", _INTRO, "## 반드시\n" + "\n".join(musts)]
    if r:
        blocks.append(r.sections)
    blocks.append("\n".join([_FORBIDDEN_HEAD, r.forbidden_effects if r else _FORBIDDEN_EFFECTS, *([r.forbidden_extra] if r else [])]))
    return "\n\n".join(blocks) + "\n"


# ---------------------------------------------------------------- 업무부
HYD_PLANT = BusinessRules(
    key="hyd-plant",
    title="HYD 설비 이상 조치",
    tool_sources="""지식은 온톨로지(Neo4j MCP), 현황·업무 값은 업무 DB(enterprise MCP),
  규칙 판정은 DMN 도구(hyd-dmn MCP)의 결정론적 결과를 씁니다. 규칙을 임의로 해석해 바꾸지 않습니다.""",
    citation="- 모든 판단에 온톨로지 노드 id(cause:…, fm:…, skill:…, rule:…, ms:…)를 인용합니다.",
    reassessment="- 다시 평가 요청에서는 원천을 새로 조회하며 사람의 요청을 근거 충족이나 설비 승인으로 간주하지 않습니다.",
    sections="""## SQL을 직접 쓸 때 (업무 DB·시계열 조회)
- 먼저 스키마 도구(enterprise describe_schema 등)로 실제 표·열을 확인하고, 거기 있는 표·열만 씁니다. 표·열 이름을 지어내지 않습니다.
- SELECT 한 문장만 씁니다. SQL 주석(-- 또는 /* */)과 끝의 세미콜론을 넣지 않습니다.
- 오류가 나면 오류 문구와 스키마를 대조해 필요한 부분만 고칩니다. 업무 의도(무엇을 세고 거르는지)는 바꾸지 않습니다. 고치기는 최대 두 번입니다.
- 끝내 실패하거나 결과가 0행이면 그대로 적습니다. 실패를 0이나 빈 값으로 바꿔 성공처럼 제출하지 않습니다. 실행한 SQL과 오류를 근거로 남깁니다.""",
    forbidden_effects="- 설비 명령(PLC 쓰기), 업무 시스템 조치 실행, 사람 대신 승인. 사람이 승인하기 전에는 어떤 조치도 실행하지 않습니다.",
    forbidden_extra="""- 온톨로지 스키마·규칙·스킬의 수정. Neo4j는 조회 도구만 사용합니다.
- hyd-dmn.submit_decision은 선택할 카드의 제출만 허용합니다. 설비/업무 조치의 승인이나 실행이 아닙니다.""",
)

HYD_HANDOVER = replace(HYD_PLANT,
    key='hyd-handover', title='HYD 교대 인수인계',
    citation='- 조회 도구 이름·실제 인자·조회 결과를 인용하고 작업 메모의 주장과 구분합니다.',
    forbidden_effects='- 인수인계는 조회와 전달입니다. 승인 여부와 관계없이 설비 명령·발주·정비 완료·사람 대신 확인을 실행하지 않습니다.',
    forbidden_extra='- 온톨로지 수정과 hyd-dmn.submit_decision을 포함한 판단 카드 제출을 하지 않습니다. 확인 없는 완료를 기록하지 않습니다.',
    reassessment='- 보완 요청에는 필요한 현재 상태를 다시 조회합니다. 이전 조회 결과를 현재 상태로 재사용하지 않습니다.',
    sections=HYD_PLANT.sections+'\n\n## 인계 판단\n'
      '- 메모는 주장입니다. 정비 완료 메모와 열린 작업지시가 다르면 모순으로 남깁니다.\n'
      '- on_order는 입고 예정이고 on_hand는 현재고입니다. 예정 수량을 현재고라고 부르지 않습니다.\n'
      '- 없는 정보와 조회 실패는 확인 필요로 남기며, 과거 기준시각과 현재 조회시각을 구분합니다.\n'
      '- 사람 검토와 인수 확인은 별도 단계이며, 인계안 작성자가 이를 대신하지 않습니다.')

RULES = {r.key: r for r in (HYD_PLANT, HYD_HANDOVER)}


def rule_card(key) -> dict | None:
    """The same complete rules the worker hands the CLI, for the portal's agent page (no UI copy)."""
    try:
        rule = rules_for(key)
    except UnknownWorkRules as exc:
        return {"key": str(key), "label": None, "content": None, "error": str(exc)}
    return {"key": rule.key, "label": rule.title, "content": constitution(rule)} if rule else None


class UnknownWorkRules(LookupError):
    pass


def rules_for(key) -> BusinessRules | None:
    """에이전트 칸 값 → 업무부. 비어 있으면 None(공통부만). 모르는 키는 UnknownWorkRules(사유) — 다른 업무 규칙으로 대신하지 않는다."""
    if key in (None, ""):
        return None
    found = RULES.get(str(key).strip())
    if found is None:
        raise UnknownWorkRules(f"업무 규칙 '{key}'이(가) 없습니다 (있는 것: {', '.join(sorted(RULES))}) — 에이전트의 work_rules 칸을 고치세요")
    return found
