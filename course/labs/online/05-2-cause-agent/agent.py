"""에이전트. 허용 목록의 도구를 골라 부르고, 읽은 것으로 후보 원인을 가려 점검 계획을 낸다.

    python agent.py        모든 사례
    python agent.py S01    그 사례만
"""
import inspect
import json
import operator
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # __pycache__를 만들지 않는다

import llm_client  # noqa: E402
import tools  # noqa: E402

_HERE = Path(__file__).resolve().parent
_CONFIG = _HERE / "agent_config.json"
_CASES = _HERE / "cases" / "cases.json"
_PLAN_DIR = _HERE / "plan"

_COMPARE = {"lt": operator.lt, "gt": operator.gt, "gte": operator.ge}
_JSON_TYPE = {str: "string", int: "integer", float: "number"}

_ANSWER_FORMAT = """모든 도구 호출을 마친 뒤, 다른 말 없이 아래 모양의 JSON 하나만 답한다.
{"id": "사례 번호",
 "status": "SUPPORTED | UNKNOWN | UNSUPPORTED",
 "causes": [{"id": "원인의 id", "name": "원인의 이름", "verdict": "CONFIRMED | HYPOTHESIS | RULED_OUT",
             "evidence": [{"id": "증거의 id", "result": "MATCH | NO_MATCH | NOT_CHECKED", "value": 숫자 또는 null}]}],
 "checks": [{"order": 1, "check": "무엇을 점검하는지 한 문장", "evidence": ["증거의 id"], "actions": ["절차 번호"]}]}"""


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _tool_specs(allowed):
    """허용 목록의 도구를 알려 줄 모양으로 바꾼다. 설명은 tools.py의 함수에 적힌 글을 그대로 쓴다."""
    specs = []
    for name in allowed:
        func = getattr(tools, name, None)
        if func is None:
            raise SystemExit(f"허용 목록에는 있으나 tools.py에 없는 도구: {name}")
        params = inspect.signature(func).parameters
        specs.append({"type": "function", "function": {
            "name": name,
            "description": inspect.getdoc(func),
            "parameters": {
                "type": "object",
                "properties": {k: {"type": _JSON_TYPE.get(v.annotation, "string")} for k, v in params.items()},
                "required": [k for k, v in params.items() if v.default is inspect.Parameter.empty],
            },
        }})
    return specs


def _run_loop(case, config):
    """묻고, 부른 도구를 대신 실행해 돌려주기를 되풀이한다. (마지막 답, 호출 기록, 멈춘 까닭)을 돌려준다."""
    allowed = config["tools"]
    instructions = "\n".join([f"당신은 {config['name']}입니다.", f"목표: {config['goal']}", "작업 규칙:"]
                             + [f"- {rule}" for rule in config["rules"]] + ["", _ANSWER_FORMAT])
    messages = [{"role": "system", "content": instructions},
                {"role": "user", "content": f"사례 번호 {case['id']}, 경보 패턴 {case['alarm']}"}]
    calls, seen, tools_off = [], set(), False

    for _ in range(config["stop"]["max_turns"]):
        reply = llm_client.chat(messages, None if tools_off else _tool_specs(allowed))
        tool_calls = reply.get("tool_calls") or []
        if not tool_calls:
            return reply.get("content") or "", calls, "같은 호출을 되풀이해 도구를 거두고 답을 받음" if tools_off else "답을 냄"
        messages.append({"role": "assistant", "content": reply.get("content") or "", "tool_calls": tool_calls})
        for call in tool_calls:
            name, raw_args = call["function"]["name"], call["function"]["arguments"]
            if (name, raw_args) in seen:
                tools_off = True
            seen.add((name, raw_args))
            if name not in allowed:
                args, result = raw_args, {"refused": f"허용 목록에 없는 도구는 부르지 않는다: {name}"}
            else:
                try:
                    args = json.loads(raw_args)
                    result = getattr(tools, name)(**args)
                except (TypeError, ValueError) as error:
                    args, result = raw_args, {"error": f"인자의 모양이 맞지 않는다: {error}"}
            calls.append({"tool": name, "args": args, "result": result})
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result, ensure_ascii=False)})
        if tools_off:
            messages.append({"role": "user", "content": "같은 호출을 되풀이했습니다. 필요한 값은 이미 받았습니다. 이제 도구를 부르지 말고 정해진 모양의 JSON만 답하세요."})
    return "", calls, "횟수 한도에 닿아 멈춤"


def _find_mismatches(answer, calls):
    """답을 호출 기록에 대어 본다. 기록에 없는 것을 적었거나 값과 판정이 어긋나면 그 목록을 돌려준다."""
    rules, values, sop_ids, cause_ids, fresh = {}, {}, set(), set(), None
    for call in calls:
        result, args = call["result"], call["args"]
        if not isinstance(result, dict) or not isinstance(args, dict):
            continue
        if call["tool"] == "find_causes":
            cause_ids |= {cause["id"] for failure in result.get("failures", []) for cause in failure["causes"]}
        elif call["tool"] == "get_evidence":
            rules.update({item["id"]: item for item in result.get("evidence", [])})
        elif call["tool"] == "read_sensor":
            if "freshness" in result:
                fresh = (result["freshness"] or {}).get("ok") is True
            else:
                values[(result["tag"], result["aggregate"], result["windowSeconds"])] = result
        elif call["tool"] == "get_actions":
            sop_ids |= {action["sopId"] for action in result.get("actions", [])}

    found = []
    for cause in answer.get("causes", []):
        if cause.get("id") not in cause_ids:
            found.append(f"호출 기록에 없는 원인: {cause.get('id')}")
        for item in cause.get("evidence", []):
            rule = rules.get(item.get("id"))
            if rule is None:
                found.append(f"호출 기록에 없는 증거: {item.get('id')}")
                continue
            reading = values.get((rule["tag"], rule["aggregate"], rule["windowSeconds"]))
            if reading is None:
                if item.get("result") != "NOT_CHECKED":
                    found.append(f"{item['id']}: 값을 읽은 기록이 없는데 result가 {item.get('result')}")
                continue
            value, coverage = reading.get("value"), reading.get("coverage") or {}
            if value is None or coverage.get("covered") is not True or fresh is not True:
                continue  # 값이 없거나 관측이 모자라거나 신선하지 않은 것은 사람이 정한 규칙의 몫이라 대조하지 않는다
            expected = "MATCH" if _COMPARE[rule["expect"]](value, rule["threshold"]) else "NO_MATCH"
            if item.get("value") != value:
                found.append(f"{item['id']}: value {item.get('value')}, 호출 기록의 값 {value}")
            if item.get("result") != expected:
                found.append(f"{item['id']}: result {item.get('result')}, 값 {value}을 기준({rule['expect']} {rule['threshold']})에 대면 {expected}")
        # verdict는 사람이 정한 규칙(증거가 모두 MATCH이면 CONFIRMED, 모두 NO_MATCH이면 RULED_OUT, 그 밖은 HYPOTHESIS)에 대어 본다
        results = [item.get("result") for item in cause.get("evidence", [])]
        if results and all(result == "MATCH" for result in results):
            expected_verdict = "CONFIRMED"
        elif results and all(result == "NO_MATCH" for result in results):
            expected_verdict = "RULED_OUT"
        else:
            expected_verdict = "HYPOTHESIS"
        if cause.get("verdict") != expected_verdict:
            found.append(f"{cause.get('id')}: verdict {cause.get('verdict')}, 증거의 result({', '.join(map(str, results)) or '증거 없음'})에 대면 {expected_verdict}")
    # status는 사람이 정한 규칙(CONFIRMED가 하나라도 있으면 SUPPORTED, 모두 RULED_OUT이면 UNSUPPORTED, 그 밖은 UNKNOWN)에 대어 본다
    verdicts = [cause.get("verdict") for cause in answer.get("causes", [])]
    if "CONFIRMED" in verdicts:
        expected_status = "SUPPORTED"
    elif verdicts and all(verdict == "RULED_OUT" for verdict in verdicts):
        expected_status = "UNSUPPORTED"
    else:
        expected_status = "UNKNOWN"
    if answer.get("status") != expected_status:
        found.append(f"status {answer.get('status')}, 원인의 verdict({', '.join(map(str, verdicts)) or '후보 없음'})에 대면 {expected_status}")
    for check in answer.get("checks", []):
        for sop_id in check.get("actions") or []:
            if sop_id not in sop_ids:
                found.append(f"호출 기록에 없는 절차 번호: {sop_id}")
    return found


def run_case(case, config):
    text, calls, stopped = _run_loop(case, config)
    match = re.search(r"\{[\s\S]*\}", text)
    try:
        answer = json.loads(match.group(0)) if match else None
    except ValueError:
        answer = None
    if not isinstance(answer, dict):
        return {
            "id": case["id"], "status": "UNKNOWN", "causes": [],
            "checks": [{"order": 1, "check": "에이전트가 답을 내지 못했다. 사람이 직접 확인한다.", "evidence": [], "actions": []}],
            "calls": calls, "mismatches": [], "stopped": stopped if stopped.startswith("횟수") else "답이 정해진 모양이 아님",
        }
    return {
        "id": case["id"],
        "status": answer.get("status"),
        "causes": answer.get("causes", []),
        "checks": answer.get("checks", []),
        "calls": calls,
        "mismatches": _find_mismatches(answer, calls),
        "stopped": stopped,
    }


def _text(value):
    return json.dumps(value, ensure_ascii=False)


def to_markdown(plans):
    lines = ["# 점검 계획", ""]
    for plan in plans:
        lines += [f"## {plan['id']}", "", f"**근거 상태: {plan['status']}** · 멈춤: {plan['stopped']}", ""]
        lines += ["### 대조", ""]
        lines += [f"- {line}" for line in plan["mismatches"]] or ["어긋남 없음"]
        lines.append("")
        for verdict, title in (("CONFIRMED", "확인된 원인"), ("HYPOTHESIS", "가설"), ("RULED_OUT", "해당 없음")):
            lines += [f"### {title}", ""]
            causes = [c for c in plan["causes"] if c.get("verdict") == verdict]
            if not causes:
                lines += ["없음", ""]
                continue
            for cause in causes:
                lines.append(f"- {cause.get('name')} (`{cause.get('id')}`)")
                for item in cause.get("evidence") or []:
                    lines.append(f"  - `{item.get('id')}`: {item.get('result')} · 읽은 값 {_text(item.get('value'))}")
                if not cause.get("evidence"):
                    lines.append("  - 증거: 없음")
            lines.append("")
        lines += ["### 점검 순서", ""]
        for check in plan["checks"]:
            lines.append(f"{check.get('order')}. {check.get('check')}")
            if check.get("evidence"):
                lines.append("   - 근거: " + ", ".join(f"`{e}`" for e in check["evidence"]))
            if check.get("actions"):
                lines.append("   - 조치: " + ", ".join(check["actions"]))
        if not plan["checks"]:
            lines.append("없음")
        lines += ["", "### 호출 기록", ""]
        for i, call in enumerate(plan["calls"], 1):
            lines.append(f"{i}. `{call['tool']}` `{_text(call['args'])}`")
        lines.append("")
    return "\n".join(lines)


def main(argv):
    if len(argv) > 1:
        raise SystemExit("쓰는 법: python agent.py [사례 번호]")
    config = _load(_CONFIG)
    cases = _load(_CASES)
    if argv:
        cases = [c for c in cases if c["id"] == argv[0]]
        if not cases:
            raise SystemExit(f"cases.json에 없는 사례 번호: {argv[0]}")

    plans = []
    for case in cases:
        plan = run_case(case, config)
        plans.append(plan)
        print(f"{plan['id']}  {plan['status']}  도구 호출 {len(plan['calls'])}번  대조 어긋남 {len(plan['mismatches'])}건  ({plan['stopped']})")

    with open(_PLAN_DIR / "plan.json", "w", encoding="utf-8") as f:
        json.dump(plans, f, ensure_ascii=False, indent=2)
        f.write("\n")
    with open(_PLAN_DIR / "plan.md", "w", encoding="utf-8") as f:
        f.write(to_markdown(plans))


if __name__ == "__main__":
    main(sys.argv[1:])
