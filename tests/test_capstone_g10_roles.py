"""G10 (전체 과정 랩업 — docs/handoff/verification/2026-10-09/capstone-lab.md 5.2): 포털에서 역할 만들기.

학생 흐름의 레인(예: "회의 주관자")을 받을 역할이 기준 정의 · 시드에만 있었다. POST /api/roles 로 users 의 role:<키> 행(origin user)을
만들면 흐름 가져오기 역할 목록(bpmn_import.catalog)에 바로 보이고, 레인 이름이 같으면 자동으로 잇는다(merge_mapping).
기본 역할은 지울 수 없고, 흐름 정의가 쓰는 역할 · 열린 작업이 있는 역할도 지우지 않는다. 되돌리기는 만든 역할만 지운다.
"""
from __future__ import annotations

from procsvc import bpmn_import
from test_b1_agent_authoring import KIM, env  # noqa: F401 — 같은 시드 · 앱(B1)

ROLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" id="d1" targetNamespace="x">
  <bpmn:process id="meeting_prep" name="회의 준비" isExecutable="true">
    <bpmn:laneSet id="ls"><bpmn:lane id="lane_org" name="회의 주관자"><bpmn:flowNodeRef>approve</bpmn:flowNodeRef></bpmn:lane></bpmn:laneSet>
    <bpmn:startEvent id="s"/><bpmn:userTask id="approve" name="안 고르기"/><bpmn:endEvent id="e"/>
    <bpmn:sequenceFlow id="f1" sourceRef="s" targetRef="approve"/><bpmn:sequenceFlow id="f2" sourceRef="approve" targetRef="e"/>
  </bpmn:process>
</bpmn:definitions>"""


def _roles(client) -> dict:
    return {r["id"]: r for r in client.get("/api/agent-assignments").json()["roles"]}


def test_create_role_shows_in_the_board_and_the_flow_import_catalog_and_lanes_bind_by_name(env):  # noqa: F811
    client, rt = env
    r = client.post("/api/roles", json={"name": "회의 주관자", "key": "s01-organizer", "by": "학생"})
    assert r.status_code == 201, r.text
    assert r.json() == {"id": "role:s01-organizer", "name": "회의 주관자", "kind": "manager", "origin": "user", "members": []}
    roles = _roles(client)
    assert roles["role:s01-organizer"]["origin"] == "user" and roles["role:operator"]["origin"] == "seed"
    cat = bpmn_import.catalog(rt.defn.raw, rt.repo.list_users(None, "hyd"))
    assert {"name": "회의 주관자", "endpoint": "role:s01-organizer"}.items() <= next(x for x in cat["roles"] if x["endpoint"] == "role:s01-organizer").items()
    mapping, _ = bpmn_import.merge_mapping(bpmn_import.parse_bpmn(ROLE_XML), None, cat)
    assert mapping["lanes"] == {"lane_org": "회의 주관자"}                                  # 레인 이름 = 역할 이름 → 자동으로 잇는다
    # 사람을 넣는 기존 업무분장 경로가 새 역할에도 그대로 된다
    assert client.post("/api/role-members", json={"role_id": "role:s01-organizer", "user_id": KIM}).status_code == 201
    assert [m["id"] for m in _roles(client)["role:s01-organizer"]["members"]] == [KIM]


def test_role_rules(env):  # noqa: F811
    client, rt = env
    auto = client.post("/api/roles", json={"name": "자료 담당"}).json()
    assert auto["id"].startswith("role:u-") and len(auto["id"]) == len("role:u-") + 6
    assert client.post("/api/roles", json={"name": "자료 담당"}).status_code == 409              # 이름이 겹치면 레인 잇기가 모호하다
    assert client.post("/api/roles", json={"name": "운전원"}).status_code == 409                 # 기준 역할 이름도
    assert client.post("/api/roles", json={"name": "x", "key": "operator"}).status_code == 409   # role:operator 는 이미 있다
    assert client.post("/api/roles", json={"name": "y", "key": "Bad_Key"}).status_code == 422
    assert client.post("/api/roles", json={"name": "z", "kind": "agent"}).status_code == 422
    assert client.post("/api/roles", json={"name": ""}).status_code == 422
    assert client.delete("/api/roles/role:operator").status_code == 403                          # 기본 역할은 보호
    assert client.delete("/api/roles/role:nope").status_code == 404
    assert client.delete("/api/roles/" + auto["id"]).json() == {"id": auto["id"], "deleted": True}
    assert auto["id"] not in _roles(client)


def test_a_role_a_flow_definition_uses_is_kept(env):  # noqa: F811
    client, rt = env
    rid = client.post("/api/roles", json={"name": "회의 주관자", "key": "s01-organizer"}).json()["id"]
    raw = dict(rt.defn.raw, id="meeting_prep", processDefinitionName="회의 준비", version="1",
               roles=[{"name": "회의 주관자", "endpoint": rid}])
    rt.repo.def_versions[("meeting_prep", "hyd", "1")] = {"id": "meeting_prep", "name": "회의 준비", "prod_version": "1", "definition": raw}
    r = client.delete(f"/api/roles/{rid}")
    assert r.status_code == 409 and "회의 준비" in r.json()["detail"]
    out = client.post("/api/agents/reset").json()
    assert out["roles"] == 0 and out["kept_roles"] == [rid] and rid in _roles(client)
    del rt.repo.def_versions[("meeting_prep", "hyd", "1")]
    again = client.post("/api/agents/reset").json()
    assert again["roles"] == 1 and again["kept_roles"] == [] and rid not in _roles(client)


def test_reset_removes_made_roles_and_their_members_only(env):  # noqa: F811
    client, rt = env
    seed_users = sorted(u["id"] for u in rt.repo.list_users(None, "hyd"))
    rid = client.post("/api/roles", json={"name": "회의 주관자"}).json()["id"]
    client.post("/api/role-members", json={"role_id": rid, "user_id": KIM})
    out = client.post("/api/agents/reset").json()
    assert out["roles"] == 1 and out["role_members"] == 1
    assert sorted(u["id"] for u in rt.repo.list_users(None, "hyd")) == seed_users
    assert not [m for m in rt.repo.list_role_members("hyd") if m["role_id"] == rid]
