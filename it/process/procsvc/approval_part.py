"""캡스톤 G1 일반 사람 승인 부품 — "에이전트가 낸 안 중 하나를 고르고 승인(또는 반려)". 순수 로직(IO 없음).

판단 엔진 카드 승인(formHandler:select_card)은 HYD 판단(decision_id · 카드 · 역할 등급)을 전제로 한다. 학생 흐름(회의 준비 등)의 에이전트는
그런 카드가 아니라 처리 건 값 하나(예: proposal)에 안 목록을 낸다. 이 부품은 그 값을 읽어 사람이 하나를 고르게 하고, 승인은 서버 승인 경로
(instances.InstanceRuntime.approve, POST /api/todolist/{id}/approve)로만 받는다 — 일반 제출(/submit)은 막는다(instance_mode).

  승인  → 서버가 approved_by · approved_role · approved_option(고른 안의 사본)을 넣는다(보호 값, definition_registry.PROTECTED_OUTPUTS).
          승인 뒤 실행 부품(svc:mcp-call 등)은 approved_by 가 있어야 실행하고, 인자 틀에 {approved_option.slot} 처럼 고른 안을 쓴다.
  반려  → approved_* 를 비운다(앞 회차 승인이 남아 효과를 내지 않게). 흐름은 approval == '반려' 가지로 결과 보고(반려)에 간다.

설정(activity["approval"], 흐름 가져오기 매핑의 tasks[<id>].config):
  options      고를 안 목록이 든 처리 건 값 (필수, 예: proposal.options) — 안 하나 = 객체, `key` 칸으로 구분한다
  key          안을 구분하는 칸 이름 (기본 slot — 출발본 T6 요령의 약속: options[{slot, reason, score, …}])
  recommended  에이전트 추천 안의 key 값이 든 처리 건 값 (선택, 예: proposal.recommended)
  losers       지는 안 목록이 든 처리 건 값 (선택, 예: proposal.losers — [{slot, why}])
  docs         근거 자료 목록이 든 처리 건 값 (선택, 예: proposal.docs — [{title, link}])
화면(approvalCard.js hydApprove.proposalHtml)은 같은 약속을 읽어 "추천 1 + 지는 안 펼치기" 카드를 그리고, 약속에서 벗어난 값은 JSON 그대로
보이며 그 사실을 표시한다.

참고 원본(모방): process-gpt frontend src/components/ui/HumanFeedbackPanel.vue:99-131 · 422-429 (approve_reject_with_edit:
승인 / 반려 단추 + 사유, 응답 answer '승인' | '반려' · reason).
"""
from __future__ import annotations

from copy import deepcopy

from . import engine
from .effect_parts import IDENT_RE, PATH_RE, lookup

KEY = "human:approve"
TOOL = "formHandler:approve"
FORM_ID = TOOL.split(":", 1)[1]
APPROVE, REJECT = "승인", "반려"
OUTPUTS = ("approval", "approval_reason")
#: 승인 경로가 넣는 값 — 흐름의 어떤 task 도 낼 수 없다(PROTECTED_OUTPUTS)
SERVER_VALUES = ("approved_by", "approved_role", "approved_option")
DEFAULT_OPTION_KEY = "slot"
FORM = {"fields_json": [{"key": "approval", "text": "승인 / 반려", "type": "select", "items": [APPROVE, REJECT]},
                        {"key": "approval_reason", "text": "사유", "type": "textarea", "required": False}]}
PATH_FIELDS = ("options", "recommended", "losers", "docs")
CONFIG = {"options": "고를 안 목록이 든 처리 건 값 (필수, 예: proposal.options)",
          "key": f"안을 구분하는 칸 이름 (기본 {DEFAULT_OPTION_KEY})",
          "recommended": "추천 안의 구분 값이 든 처리 건 값 (선택, 예: proposal.recommended)",
          "losers": "지는 안 목록이 든 처리 건 값 (선택, 예: proposal.losers)",
          "docs": "근거 자료 목록이 든 처리 건 값 (선택, 예: proposal.docs)"}
PART = {"key": KEY, "group": "general", "name": "사람 승인 (안 고르기)", "kind": "human", "tool": TOOL, "form_id": FORM_ID,
        "form": FORM, "approval": True, "effect": None, "outputs": list(OUTPUTS), "server_values": list(SERVER_VALUES),
        "config": CONFIG,
        "help": "에이전트가 낸 안 목록(예: proposal.options) 중 하나를 담당자가 고르고 승인하거나 반려합니다. 승인하면 서버가 승인자 · 역할 · "
                "고른 안(approved_option)을 처리 건 값으로 넣고, 그 뒤 시스템 task(승인 뒤 MCP 호출 등)가 실행됩니다. "
                "반려하면 approval 값이 '반려'가 되므로 분기에서 결과 보고(반려)로 보내세요."}


def config_of(activity: dict) -> dict:
    cfg = activity.get("approval")
    return cfg if isinstance(cfg, dict) else {}


def option_key(cfg: dict) -> str:
    return cfg.get("key") or DEFAULT_OPTION_KEY


def roots(cfg: dict) -> list[str]:
    """설정이 읽는 처리 건 값의 맨 앞 이름(proposal.options → proposal) — 이 task 가 받을 값(inputData)이다."""
    return list(dict.fromkeys(str(cfg[f]).split(".", 1)[0] for f in PATH_FIELDS if cfg.get(f)))


def validate(activity: dict) -> None:
    """등록 · 가져오기 검사. 틀리면 ValueError(활동 id 와 사유)."""
    aid = activity.get("id")
    if activity.get("type") != "userTask" or engine.is_agent(activity) or activity.get("orchestration") not in engine.NO_MODE:
        raise ValueError(f"활동 {aid}: 사람 승인(안 고르기)은 사람이 하는 userTask 입니다")
    cfg = activity.get("approval")
    if not isinstance(cfg, dict):
        raise ValueError(f"활동 {aid}: 사람 승인 설정(approval)이 없습니다 — 고를 안이 든 처리 건 값(options)을 정하세요")
    unknown = sorted(set(cfg) - set(CONFIG))
    if unknown:
        raise ValueError(f"활동 {aid}: 사람 승인 설정에 모르는 칸이 있습니다 ({', '.join(unknown)}) — {', '.join(CONFIG)} 만 받습니다")
    if not cfg.get("options"):
        raise ValueError(f"활동 {aid}: 고를 안이 든 처리 건 값(options, 예: proposal.options)을 정하세요")
    for field in PATH_FIELDS:
        if cfg.get(field) is not None and (not isinstance(cfg[field], str) or not PATH_RE.match(cfg[field])):
            raise ValueError(f"활동 {aid}: {field} 는 처리 건 값 이름(점으로 안쪽 칸, 예: proposal.options)이어야 합니다")
    if cfg.get("key") is not None and (not isinstance(cfg["key"], str) or not IDENT_RE.match(cfg["key"])):
        raise ValueError(f"활동 {aid}: key 는 안 안의 칸 이름(예: slot)이어야 합니다")
    missing = [r for r in roots(cfg) if r not in (activity.get("inputData") or [])]
    if missing:
        raise ValueError(f"활동 {aid}: 설정이 읽는 값 {', '.join(missing)} 을(를) 받을 값(inputData)에 넣으세요")
    if list(activity.get("outputData") or []) != list(OUTPUTS):
        raise ValueError(f"활동 {aid}: 사람 승인의 outputData 는 {list(OUTPUTS)} 이어야 합니다")


def validate_form(form: dict | None, aid) -> None:
    """버전 안의 승인 폼은 부품의 폼 그대로여야 한다(승인 / 반려 고르기를 학생 흐름이 바꾸지 못하게)."""
    if not isinstance(form, dict) or form.get("fields_json") != FORM["fields_json"]:
        raise ValueError(f"활동 {aid}: 사람 승인의 폼({FORM_ID})은 부품 폼(승인 / 반려 · 사유) 그대로여야 합니다")


def activity_for(task: dict, config: dict | None, inputs: list[str], role: str) -> dict:
    """가져오기(bpmn_import)가 그림의 task 하나를 이 부품의 활동으로 만든다. 검사는 validate 가 한다."""
    cfg = deepcopy(config) if isinstance(config, dict) else {}
    return {"id": task["id"], "name": task.get("name") or PART["name"], "type": "userTask", "role": role, "tool": TOOL,
            "agent": None, "approval": cfg, "inputData": list(dict.fromkeys([*roots(cfg), *inputs])), "outputData": list(OUTPUTS),
            "checkpoints": ["사람 승인 1회 — 승인 경로(역할 검사)로만 제출한다"], "duration": 1,
            "description": task.get("name") or PART["name"]}


def options_of(values: dict, cfg: dict) -> list[dict]:
    """처리 건 값에서 고를 안 목록을 읽는다. 없거나 약속(객체 목록 · key 칸 · key 값 하나씩)에서 벗어나면 ValueError(값 이름 · 몇 번째 안)."""
    path, key = cfg["options"], option_key(cfg)
    try:
        options = lookup(values, path)
    except KeyError:
        raise ValueError(f"고를 안 '{path}' 이(가) 처리 건에 없습니다 — 앞 단계(에이전트)가 이 값을 내지 않아 승인할 수 없습니다") from None
    if not isinstance(options, list) or not options:
        raise ValueError(f"고를 안 '{path}' 이(가) 비어 있거나 목록이 아닙니다 — 고를 안이 없어 승인할 수 없습니다")
    seen: set[str] = set()
    for i, opt in enumerate(options, 1):
        if not isinstance(opt, dict) or opt.get(key) in (None, ""):
            raise ValueError(f"고를 안 '{path}' 의 {i}번째 안에 구분 칸 '{key}' 이(가) 없습니다")
        mark = str(opt[key])
        if mark in seen:
            raise ValueError(f"고를 안 '{path}' 에 '{key}' 값 {mark} 이(가) 두 번 있습니다 — 어느 안인지 정할 수 없습니다")
        seen.add(mark)
    return options


def choose(values: dict, cfg: dict, option) -> dict:
    """고른 안의 사본. 고른 안이 목록에 없으면 ValueError(있는 안을 함께)."""
    options, key = options_of(values, cfg), option_key(cfg)
    if option in (None, ""):
        raise ValueError("승인할 안을 고르세요")
    found = next((o for o in options if str(o[key]) == str(option)), None)
    if found is None:
        raise ValueError(f"고른 안 '{option}' 이(가) '{cfg['options']}' 에 없습니다 (있는 안: {', '.join(str(o[key]) for o in options)})")
    return deepcopy(found)
