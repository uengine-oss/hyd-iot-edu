"""A148 (sweep 57): `projection_repair.execution_drift` — a graph-only change to a projected field is reported by inspect.

The fence hash only covers the payload the projector sent, so a node edited (or lost) in Neo4j alone used to be invisible
until someone compared two inspections by hand (`.evidence/a148/57/`).
"""
from procsvc.projection_repair import execution_drift


def _source(status="COMPLETED", items=None, deleted=False):
    inst = {"proc_inst_id": "p1", "status": status, "end_event": "ev:closed", "proc_def_version": "2.2", "rework_generation": 0,
            "proc_def_id": "anomaly_response", "is_deleted": deleted}
    return {"instance": inst, "definition": {}, "items": items if items is not None else [{"id": "w1", "status": "DONE", "draft_status": "COMPLETED", "activity_id": "task:diagnose", "generation": 0}]}


def _graph(status="COMPLETED", item_status="DONE", with_item=True, with_node=True):
    nodes = [{"node": {"id": "p1", "status": status, "end_event": "ev:closed", "version": "2.2", "rework_generation": 0, "definition_id": "anomaly_response"}, "edges": []}] if with_node else []
    items = [{"node": {"id": "w1", "status": item_status, "draft_status": "COMPLETED", "activity_id": "task:diagnose", "generation": 0}, "edges": []}] if with_item else []
    return {"fence": {"revision": 1, "payload_hash": "x"}, "nodes": nodes, "items": items}


def test_matching_projection_has_no_drift():
    assert execution_drift(_source(), _graph()) == []


def test_tampered_instance_status_is_reported():
    d = execution_drift(_source(), _graph(status="TAMPERED-A148"))
    assert d == [{"where": "ProcessInstance", "field": "status", "source": "COMPLETED", "graph": "TAMPERED-A148"}]


def test_tampered_or_missing_work_item_is_reported():
    assert execution_drift(_source(), _graph(item_status="TODO"))[0]["field"] == "status"
    assert execution_drift(_source(), _graph(with_item=False)) == [{"where": "WorkItem:w1", "field": "*", "source": "present", "graph": "missing"}]


def test_missing_node_and_resurrected_deleted_instance_are_reported():
    assert execution_drift(_source(), _graph(with_node=False)) == [{"where": "ProcessInstance", "field": "*", "source": "present", "graph": "missing"}]
    assert execution_drift(_source(deleted=True), _graph()) == [{"where": "ProcessInstance", "field": "*", "source": "deleted", "graph": "present"}]
    assert execution_drift(_source(deleted=True), _graph(with_node=False, with_item=False)) == []
