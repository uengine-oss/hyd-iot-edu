"""Evidence-only mutation; missing official filter must break positive acceptance."""
from copy import deepcopy
from entsim import data
from test_education_pm_inventory_fixture import test_initial_educational_inventory_allows_actual_single_four_thousand_policy as original_check


def test_missing_filter_initial_row_breaks_original_positive_assertion(monkeypatch):
    old=deepcopy(data.SPARE_BASE)
    old.pop('P-RTN-FLT')
    monkeypatch.setattr(data,'SPARE_BASE',old)
    original_check()
