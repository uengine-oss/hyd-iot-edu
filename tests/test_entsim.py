"""enterprise-sim: mock ERP/MES/CMMS/QMS/SCM/EMS. The ontology's formulas may only use facts these systems really serve."""
import re
from pathlib import Path

import pytest

from entsim import data, state

INSTANCES = Path(__file__).resolve().parents[1] / "it" / "neo4j" / "v2" / "instances.cypher"
# ontology v2: InputData -SOURCED_FROM-> sys:mes is fetched by the agent from enterprise-sim (variable -> MES fact key)
MES_FACTS = {"order_due_h": "due_in_h"}


@pytest.mark.parametrize("asset", ["HYD-01", "HYD-02", "HYD-03"])
def test_every_mes_input_of_the_ontology_is_served(asset):
    rows = re.findall(r"\['in:[a-z0-9-]+','[^']*','[a-z]+','([a-z0-9_]+)','sys:mes'", INSTANCES.read_text(encoding="utf-8"))
    assert rows, "no InputData sourced from sys:mes?"
    facts = data.mes_orders(asset)["facts"]
    for var in rows:
        assert isinstance(facts.get(MES_FACTS[var]), (int, float)), var


def test_facts_are_prefixed_by_their_system():
    f = data.prefixed(data.mes_orders("HYD-01"))
    assert f["mes_due_in_h"] == 6 and "mes_records" not in f


def test_executing_a_maintenance_skill_opens_a_work_order_in_cmms():
    st = state.EnterpriseState()
    tx = st.execute({"decision": "DEC-1", "option": "opt:sc1-derate", "skill": "skill:schedule-maintenance", "system": "sys:cmms",
                     "asset": "HYD-01", "by": "role:prod-mgr"})
    assert tx["system"] == "sys:cmms" and tx["ref"].startswith("WO-")
    assert st.snapshot()["cmms"]["work_orders"][0]["id"] == tx["ref"]


def test_reallocation_moves_the_order_to_the_alternate_asset():
    st = state.EnterpriseState()
    st.execute({"decision": "DEC-2", "option": "opt:sc1-transfer", "skill": "skill:reallocate-production", "system": "sys:mes",
                "asset": "HYD-01", "by": "role:prod-mgr"})
    orders = st.snapshot()["mes"]["orders"]
    assert any(o["asset"] == "HYD-02" and o["moved_from"] == "HYD-01" for o in orders)


def test_unknown_skill_is_refused():
    with pytest.raises(ValueError):
        state.EnterpriseState().execute({"skill": "skill:launch-missiles", "system": "sys:erp", "asset": "HYD-01"})


def test_transactions_are_logged_newest_first_and_reset_clears_them():
    st = state.EnterpriseState()
    st.execute({"skill": "skill:hold-lot", "system": "sys:qms", "asset": "HYD-01", "decision": "D1"})
    st.execute({"skill": "skill:procure-part", "system": "sys:erp", "asset": "HYD-01", "decision": "D2", "params": {"supplier": "sup:b"}})
    assert [t["skill"] for t in st.transactions()] == ["skill:procure-part", "skill:hold-lot"]
    st.reset()
    assert st.transactions() == []


def test_work_order_cancellation_is_an_exact_idempotent_inverse():
    st = state.EnterpriseState()
    wo = st.execute({"decision": "D-A072", "option": "skill:x", "skill": "skill:schedule-maintenance", "asset": "HYD-01", "by": "x"})
    undo = st.execute({"decision": "D-A072", "skill": "skill:cancel-work-order", "asset": "HYD-01", "by": "reviewer",
                       "params": {"ref": wo["ref"]}, "compensates": wo["id"]})
    assert undo["system"] == "sys:cmms" and undo["ref"] == wo["ref"] and undo["compensates"] == wo["id"]
    assert st.snapshot()["cmms"]["work_orders"][0]["status"] == state.CANCELLED
    again = st.execute({"decision": "D-A072", "skill": "skill:cancel-work-order", "asset": "HYD-01", "by": "reviewer",
                        "params": {"ref": wo["ref"]}, "compensates": wo["id"]})
    assert again == undo                                           # same request → same receipt, no second cancellation
    with pytest.raises(ValueError, match="cannot be cancelled"):   # a second attempt with a different decision meets the moved-on record
        st.execute({"decision": "D-other", "skill": "skill:cancel-work-order", "asset": "HYD-01", "by": "x", "params": {"ref": wo["ref"]}})
    with pytest.raises(ValueError, match="no such work order"):
        st.execute({"skill": "skill:cancel-work-order", "asset": "HYD-01", "params": {"ref": "WO-NOPE"}})
    with pytest.raises(ValueError, match="params.ref"):
        st.execute({"skill": "skill:cancel-work-order", "asset": "HYD-01"})
    assert [tx["skill"] for tx in st.transactions("D-A072")] == ["skill:schedule-maintenance", "skill:cancel-work-order"]


def test_other_inverses_and_the_irreversible_list():
    st = state.EnterpriseState()
    pr = st.execute({"decision": "D1", "skill": "skill:procure-part", "asset": "HYD-01", "params": {"supplier": "sup:b"}})
    assert st.execute({"decision": "D1", "skill": "skill:cancel-purchase-request", "asset": "HYD-01", "params": {"ref": pr["ref"]}})["ref"] == pr["ref"]
    assert st.snapshot()["erp"]["purchase_requests"][0]["status"] == state.CANCELLED
    mv = st.execute({"decision": "D2", "skill": "skill:reallocate-production", "asset": "HYD-01"})
    st.execute({"decision": "D2", "skill": "skill:restore-production", "asset": "HYD-01", "params": {"ref": mv["ref"]}})
    assert all(o["moved_from"] is None for o in st.snapshot()["mes"]["orders"])
    assert st.execute({"decision": "D2", "skill": "skill:restore-production", "asset": "HYD-01", "params": {"ref": mv["ref"]}})["ref"] == mv["ref"]   # replay → same receipt
    with pytest.raises(ValueError, match="no reallocation"):                                                                                     # a new request meets the restored order
        st.execute({"decision": "D2-again", "skill": "skill:restore-production", "asset": "HYD-01", "params": {"ref": mv["ref"]}})
    hold = st.execute({"decision": "D3", "skill": "skill:hold-lot", "asset": "HYD-01"})
    st.execute({"decision": "D3", "skill": "skill:release-hold", "asset": "HYD-01", "params": {"ref": hold["ref"]}})
    assert st.snapshot()["qms"]["holds"][0]["status"] == "격리 해제"
    assert set(state.INVERSE_OF) == {"skill:schedule-maintenance", "skill:procure-part", "skill:reallocate-production", "skill:hold-lot"}
    assert set(state.IRREVERSIBLE) == {"skill:release-lot", "skill:substitute-shipment", "skill:demand-control"}
    assert not set(state.INVERSE_OF) & set(state.IRREVERSIBLE) and set(state.INVERSE_OF.values()) == set(state.COMPENSATION_SKILLS)
    for forward in ("skill:release-lot", "skill:substitute-shipment", "skill:demand-control"):
        assert forward in state.SKILLS and forward not in state.INVERSE_OF

