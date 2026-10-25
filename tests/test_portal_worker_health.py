"""포털 상태 점에 AI 워커가 있는가(2026-10-25 수업 한 바퀴: 워커가 꺼져도 상단이 「모두 초록」이고 AI 단계만 무한 대기했다)."""
import re
from pathlib import Path

LAYERS = Path(__file__).resolve().parents[1] / "it/portal/www/layers.js"


def test_the_ai_worker_is_a_counted_health_dot():
    text = LAYERS.read_text(encoding="utf-8")
    entry = re.search(r"\{ name: 'agent-worker'[^\n]*\}", text)
    assert entry, "layers.js 에 agent-worker 가 없다"
    assert "health: P(8097) + '/healthz'" in entry.group(0) and "optional" not in entry.group(0)   # 선택 도구가 아니라 세는 대상
