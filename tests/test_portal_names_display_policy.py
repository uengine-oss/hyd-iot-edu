"""Offline projection contract: original graph/skill labels remain immutable."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("portal_names_policy", ROOT / "scripts/portal_names.py")
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


def test_generated_names_keep_maintenance_display_policy():
    # Exact pre-projection labels preserved from c163804; portable after future commits.
    original = json.loads((ROOT / "tests/fixtures/maintenance_display_names_original.json").read_text(encoding="utf-8"))
    actual = json.loads((ROOT / "it/portal/www/names.json").read_text(encoding="utf-8"))
    affected = {key: value for key, value in original.items() if "작업지시" in value}
    assert len(affected) == 7
    for key, label in affected.items():
        assert policy.display_name(label) == actual[key]
        assert "작업지시" in original[key]
        assert "작업지시" not in actual[key]
    assert policy.display_name(None) is None
    assert policy.display_name("미등록 외부 이름") == "미등록 외부 이름"
    assert policy.display_name("unknown:source") == "unknown:source"
    assert policy.display_name("정비 요청") == "정비 요청"


def test_known_technical_names_are_display_projection_only():
    expected = {"CMMS": "정비 관리", "ERP": "구매 · 재고 관리", "MES": "생산 관리", "SCM 구매 포털": "공급망 구매 창구", "Historian (TimescaleDB)": "센서 기록", "SCADA · PLC (cmd-gateway 경유)": "설비 제어", "PLC 상태": "설비 상태", "PLC 운전 모드": "설비 운전 모드", "경남유압 BSC 전략맵": "경남유압 성과 목표"}
    for original, shown in expected.items():
        assert policy.display_name(original) == shown
    for original in ["CMMS-custom-user-title", "HYD-02", "SOP-PM-22", "user@example.com", "unregistered"]:
        assert policy.display_name(original) == original
