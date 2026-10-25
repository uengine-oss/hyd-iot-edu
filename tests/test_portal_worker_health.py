"""포털 상태 점에 AI 워커가 있는가(2026-10-25 수업 한 바퀴: 워커가 꺼져도 상단이 「모두 초록」이고 AI 단계만 무한 대기했다)."""
import re
from pathlib import Path

LAYERS = Path(__file__).resolve().parents[1] / "it/portal/www/layers.js"


def test_the_ai_worker_is_a_counted_health_dot():
    text = LAYERS.read_text(encoding="utf-8")
    entry = re.search(r"\{ name: 'agent-worker'[^\n]*\}", text)
    assert entry, "layers.js 에 agent-worker 가 없다"
    assert "health: P(8097) + '/healthz'" in entry.group(0) and "optional" not in entry.group(0)   # 선택 도구가 아니라 세는 대상


def test_alert_route_table_names_business_and_trip_patterns_in_korean():
    """2026-10-25 수업 한 바퀴: 흐름 배포 화면 「경보 → 흐름」 표가 PM_DUE · SPARE_BELOW_MIN 코드를 그대로 보였다(app.js PATTERN_LABEL)."""
    app = (LAYERS.parent / "app.js").read_text(encoding="utf-8")
    label = re.search(r"const PATTERN_LABEL = \{(.*?)\};", app, re.S).group(1)
    for code in ("PM_DUE", "SPARE_BELOW_MIN", "LOW_PRESSURE_TRIP", "HIGH_VIBRATION_TRIP", "OIL_ANALYSIS"):
        assert re.search(code + r": '[가-힣]", label), code


def test_ask_screen_names_the_agents_servers_not_as_tool_ids():
    """2026-10-25 수업 한 바퀴: 질문 화면의 에이전트 도구 칩이 「도구 표시 이름 미등록」(서버 이름을 도구 id 용 UI.toolName 에 넣음)."""
    ask = (LAYERS.parent / "ask.js").read_text(encoding="utf-8")
    line = next(l for l in ask.splitlines() if "const tools = a.tools.length" in l)
    assert "serverLabel(t)" in line and "UI.toolName" not in line
    assert "serverName" in (LAYERS.parent / "agents.js").read_text(encoding="utf-8").split("window.hydAgents = {")[1].split("}")[0]


def test_decision_says_when_a_changed_condition_is_read_by_no_rule():
    """2026-10-25 수업 한 바퀴: HM-8 지식에는 보호 정지 규칙이 없어 「설비 상태 = 보호 정지」로 바꿔도 결과가 같았고, 화면은 말이 없었다."""
    import json, subprocess
    src = (LAYERS.parent / "enterprise.js").read_text(encoding="utf-8")
    fn = re.search(r"const FACT_LABEL = .*?\nfunction unusedFacts\(facts, trace\) \{.*?\n\}", src, re.S).group(0)
    trace = [{"when": "plc_mode != 'REMOTE_AUTO'"}, {"when": "fan100_hours > 24"}]
    js = fn + f"\nconsole.log(JSON.stringify(unusedFacts({json.dumps({'plc_state': 'TRIP', 'plc_mode': 'LOCAL', 'fan100_hours': 30})}, {json.dumps(trace)})))"
    out = subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == ["plc_state"]
    assert "unusedFacts(ent.facts, r.trace)" in src and "ent.facts = facts" in src
