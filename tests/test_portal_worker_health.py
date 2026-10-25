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
