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
