"""캡스톤 출발본 T2 (students/_template/load_graph.py): 학생 지식 적재 · 되돌리기 · 꼭 답할 질문 검사.

그래프 없이 본다: 파일 모양 · ns · id 접두어 강제, 남의 노드를 덮어쓰지 않음, 다리 끝은 수업 기준 노드만, 검사에 걸리면 아무것도 쓰지 않음,
적재 문장이 값을 매개변수로만 넘김, 되돌리기가 내 이름 공간만 지우고 빈 되돌리기는 실패, 질문은 $ns 를 봐야 하고 0행이면 못 답함.
실제 Neo4j 적재 · 되돌리기는 라이브 기록(docs/handoff/verification/2026-10-10/K-capstone.md)에 있다 — 여기 가짜 트랜잭션은 문장 뜻을 흉내 낼 뿐이다.
"""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / "students" / "_template"
EX = KIT / "example_meeting"
spec = importlib.util.spec_from_file_location("student_load_graph", KIT / "load_graph.py")
lg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lg)
ov = lg.ov
BASE_NODES = [{"labels": ["Role"], "props": {"id": "role:operator", "name": "운전원", "level": 1}},
              {"labels": ["System"], "props": {"id": "sys:agent", "name": "에이전트", "zone": "IT"}}]


class _Counters:
    def __init__(self, nodes_deleted):
        self.nodes_deleted = nodes_deleted


class _Result:
    def __init__(self, rows, nodes_deleted=0):
        self.rows, self.counters = rows, _Counters(nodes_deleted)

    def data(self):
        return self.rows

    def single(self):
        return self.rows[0]

    def consume(self):
        return self

    def __iter__(self):
        return iter(self.rows)


class FakeTx:
    """load_graph 가 쓰는 문장만 아는 기억 속 그래프. 모르는 문장은 실패한다(문장이 바뀌면 시험이 알게)."""

    def __init__(self, nodes=()):
        self.nodes = {n["props"]["id"]: copy.deepcopy(n) for n in nodes}
        self.rels = {}
        self.statements = []

    def run(self, stmt, params=None):
        params = params or {}
        self.statements.append((stmt, params))
        if stmt == lg.FIND:
            return _Result([{"id": i, "labels": list(self.nodes[i]["labels"]), "ns": self.nodes[i]["props"].get("ns"), "props": dict(self.nodes[i]["props"])}
                            for i in params["ids"] if i in self.nodes])
        if stmt == lg.MINE:
            kinds = {}
            for n in self.nodes.values():
                if n["props"].get("ns") == params["ns"]:
                    kind = "flow" if n["props"].get("source_type") == params["flow"] else "knowledge"
                    kinds[kind] = kinds.get(kind, 0) + 1
            return _Result([{"kind": k, "c": c} for k, c in kinds.items()])
        if stmt == lg.WIPE:
            gone = {i for i, n in self.nodes.items() if n["props"].get("ns") == params["ns"]}
            self.nodes = {i: n for i, n in self.nodes.items() if i not in gone}
            self.rels = {k: v for k, v in self.rels.items() if k[1] not in gone and k[2] not in gone}
            return _Result([], nodes_deleted=len(gone))
        if stmt == lg.LEFTOVER:
            return _Result([{"id": i, "ns": n["props"].get("ns")} for i, n in sorted(self.nodes.items()) if i.startswith(params["prefix"])])
        if stmt.startswith("UNWIND $rows AS r MERGE (n:`"):
            labels = [part.strip("`") for part in stmt.split("MERGE (n:`")[1].split("` {id")[0:1]]
            labels += [l.strip("`") for l in stmt.split(" SET n:")[1].split(":")] if " SET n:" in stmt else []
            for r in params["rows"]:
                self.nodes[r["id"]] = {"labels": labels, "props": dict(r["props"])}
            return _Result([])
        if stmt.startswith("UNWIND $rows AS r MATCH (a {id: r.a}), (b {id: r.b}) MERGE (a)-[x:`"):
            rel_type = stmt.split("[x:`")[1].split("`")[0]
            for r in params["rows"]:
                if r["a"] in self.nodes and r["b"] in self.nodes:
                    self.rels[(rel_type, r["a"], r["b"])] = dict(r["props"])
            return _Result([])
        if stmt.startswith("MATCH (n) RETURN labels(n)"):
            return _Result([{"l": n["labels"], "p": n["props"]} for n in self.nodes.values()])
        if stmt.startswith("MATCH (a)-[x]->(b) RETURN type(x)"):
            return _Result([{"t": t, "a": a, "b": b, "la": self.nodes[a]["labels"], "lb": self.nodes[b]["labels"], "p": p} for (t, a, b), p in self.rels.items()])
        raise AssertionError(f"모르는 문장: {stmt}")

    def writes(self):
        return [s for s, _ in self.statements if "MERGE" in s or "DELETE" in s]


def _files(folder=EX):
    extra = ov.load_extra(folder / "schema.json")
    return ov.load_schema(), extra, lg.read_graph(folder / "graph.json", extra["ns"])


def _write(tmp_path, graph) -> Path:
    path = tmp_path / "graph.json"
    path.write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")
    return path


def _raw(folder=EX) -> dict:
    return json.loads((folder / "graph.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------- 파일 검사(그래프 없이)
@pytest.mark.parametrize("folder", [KIT, EX])
def test_kit_files_pass_the_offline_check(folder, capsys):
    assert lg.main(["check", "--dir", str(folder)]) == 0
    assert "PASS (파일만 검사)" in capsys.readouterr().out


def test_every_node_must_carry_my_namespace_and_id_prefix(tmp_path):
    raw = _raw()
    raw["nodes"][0]["props"].pop("ns")                      # ns 없음 — 적재되면 수업 기준 노드처럼 보인다
    raw["nodes"][1]["props"]["id"] = "role:operator"        # 접두어 없음 — 수업 기준 id 를 노린다
    raw["nodes"].append(copy.deepcopy(raw["nodes"][2]))     # 같은 id 두 번
    with pytest.raises(lg.GraphFileError) as e:
        lg.read_graph(_write(tmp_path, raw), "demo")
    text = "\n".join(e.value.problems)
    assert "nodes[0] demo:persp:customer: ns = 'demo' 가 있어야 한다" in text
    assert "nodes[1] role:operator: id 는 'demo:' 로 시작해야 한다" in text
    assert "같은 id 가 두 번 나온다" in text


@pytest.mark.parametrize("mutate, phrase", [
    (lambda g: g.update(ns="s01"), "ns 's01' 가 스키마 파일의 ns 'demo' 와 다르다"),
    (lambda g: g.update(nodes=[]), "nodes 가 비어 있다"),
    (lambda g: g["nodes"][0].update(labels=["Bad Label`) DETACH DELETE (n"]), "labels 는 클래스 이름 목록"),
    (lambda g: g["nodes"][0].update(props={"name": "x"}), "props.id 가 없다"),
    (lambda g: g["rels"][0].update(type="x`]->() DETACH DELETE n //"), "모양이어야 한다"),
    (lambda g: g["rels"].append({"type": "PLAYS", "a": "role:operator", "b": "sys:agent"}), "양 끝이 모두 내 파일 밖이다"),
    (lambda g: g["rels"].append(copy.deepcopy(g["rels"][0])), "같은 관계가 두 번 나온다"),
    (lambda g: g.pop("rels"), "객체여야 한다"),
])
def test_malformed_graph_files_are_refused_with_coordinates(tmp_path, mutate, phrase):
    raw = _raw()
    mutate(raw)
    with pytest.raises(lg.GraphFileError) as e:
        lg.read_graph(_write(tmp_path, raw), "demo")
    assert phrase in "\n".join(e.value.problems)


def test_a_broken_file_fails_the_cli_without_a_traceback(tmp_path, capsys):
    for name in ("schema.json", "questions.cypher"):
        (tmp_path / name).write_text((EX / name).read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "graph.json").write_text("{", encoding="utf-8")
    assert lg.main(["check", "--dir", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "지식 파일을 읽을 수 없다" in out and "FAIL (1 problems) — 그래프에 닿지 않았다" in out


def test_schema_violations_in_the_file_fail_the_offline_check(tmp_path, capsys):
    raw = _raw()
    next(n for n in raw["nodes"] if n["labels"] == ["Meeting"])["props"]["kind"] = "party"       # 허용값 아님
    for name in ("schema.json", "questions.cypher"):
        (tmp_path / name).write_text((EX / name).read_text(encoding="utf-8"), encoding="utf-8")
    _write(tmp_path, raw)
    assert lg.main(["check", "--dir", str(tmp_path)]) == 1
    assert "kind='party' 허용값 아님" in capsys.readouterr().out


# ---------------------------------------------------------------- 적재
def test_load_writes_my_namespace_only_and_passes_the_same_check_as_validate_extra():
    base, extra, graph = _files()
    tx = FakeTx(BASE_NODES)
    done = lg.load_into(tx, graph, base, extra)
    assert done == {"nodes": 65, "rels": 107, "in_graph": 65, "bridge_ends": 0, "stale": []}
    assert {i for i in tx.nodes if not i.startswith("demo:")} == {"role:operator", "sys:agent"}      # 수업 기준 노드 그대로
    assert tx.nodes["role:operator"] == BASE_NODES[0]
    nodes, rels = ov.read_rows(tx)
    assert ov.validate_ns(nodes, rels, base, extra) == []
    again = lg.load_into(tx, graph, base, extra)                                                     # 다시 돌려도 같은 상태(멱등)
    assert again == done and len(tx.nodes) == 67 and len(tx.rels) == 107


def test_load_statements_pass_values_only_as_parameters():
    _, _, graph = _files()
    for stmt, params in lg.write_batches(graph):
        assert set(params) == {"rows"} and "demo:" not in stmt and "가온" not in stmt
        assert stmt.startswith("UNWIND $rows AS r ")


def test_load_never_overwrites_a_node_someone_else_owns():
    base, extra, graph = _files()
    squatted = graph["nodes"][0]["props"]["id"]
    for owner, phrase in ((None, "수업 기준 노드다"), ("s02", "s02 이름 공간 노드다")):
        props = {"id": squatted, "name": "남의 것"} | ({"ns": owner} if owner else {})
        tx = FakeTx(BASE_NODES + [{"labels": ["Perspective"], "props": props}])
        with pytest.raises(lg.Refused) as e:
            lg.load_into(tx, graph, base, extra)
        assert phrase in e.value.problems[0] and "덮어쓰지 않는다" in e.value.problems[0]
        assert tx.writes() == [] and tx.nodes[squatted]["props"] == props


def test_bridge_ends_must_be_base_nodes_that_exist():
    base, extra, graph = _files()
    organizer = next(n["props"]["id"] for n in graph["nodes"] if n["labels"] == ["Attendee"])
    graph["rels"].append({"type": "PLAYS", "a": organizer, "b": "role:operator", "props": {}})
    tx = FakeTx(BASE_NODES)
    done = lg.load_into(tx, graph, base, extra)
    assert done["rels"] == 108 and done["bridge_ends"] == 1 and ("PLAYS", organizer, "role:operator") in tx.rels    # 수업 기준 Role 에 다리
    assert tx.nodes["role:operator"] == BASE_NODES[0]                                                                # 다리 끝은 그대로
    with pytest.raises(lg.Refused) as e:                                                                             # 그래프에 없는 끝
        lg.load_into(FakeTx(), graph, base, extra)
    assert "끝점 role:operator: 내 파일에도 그래프에도 없다" in e.value.problems[0]
    other = FakeTx([{"labels": ["Role"], "props": {"id": "role:operator", "name": "남의 역할", "level": 1, "ns": "s02"}}])
    with pytest.raises(lg.Refused) as e:                                                                             # 다른 학생의 노드
        lg.load_into(other, graph, base, extra)
    assert "다른 이름 공간(s02)" in e.value.problems[0] and other.writes() == []


def test_a_bridge_end_changed_during_the_load_rolls_back():
    """적재 문장은 다리 끝을 MATCH 만 한다. 그 약속이 깨지면(끝 노드의 속성이 달라지면) 되돌린다 — 그래프 전체 수를 세지 않으므로
    그사이 다른 사람이 쓴 무관한 노드(처리 건 투영 등)는 거짓 실패를 만들지 않는다."""
    base, extra, graph = _files()
    organizer = next(n["props"]["id"] for n in graph["nodes"] if n["labels"] == ["Attendee"])
    graph["rels"].append({"type": "PLAYS", "a": organizer, "b": "role:operator", "props": {}})

    class TouchesBase(FakeTx):
        def run(self, stmt, params=None):
            if stmt.startswith("UNWIND $rows AS r MATCH (a {id: r.a})"):
                self.nodes["role:operator"]["props"]["name"] = "적재가 바꾼 이름"
            return super().run(stmt, params)

    with pytest.raises(lg.Refused) as e:
        lg.load_into(TouchesBase(BASE_NODES), graph, base, extra)
    assert any("끝점 role:operator: 적재 중에 수업 기준 노드가 달라졌다" in p for p in e.value.problems)

    class Unrelated(FakeTx):                                                                         # 무관한 수업 기준 노드가 그사이 생김
        def run(self, stmt, params=None):
            if stmt.startswith("UNWIND $rows AS r MATCH (a {id: r.a})"):
                self.nodes["pi:other"] = {"labels": ["Role"], "props": {"id": "pi:other", "name": "다른 사람이 쓴 것", "level": 1}}
            return super().run(stmt, params)

    assert lg.load_into(Unrelated(BASE_NODES), graph, base, extra)["bridge_ends"] == 1


def test_wipe_fails_when_the_deleted_count_differs_from_my_node_count():
    class DeletesLess(FakeTx):
        def run(self, stmt, params=None):
            result = super().run(stmt, params)
            return _Result([], nodes_deleted=0) if stmt == lg.WIPE else result

    tx = DeletesLess(BASE_NODES + [{"labels": ["Meeting"], "props": {"id": "demo:m", "name": "회의", "ns": "demo"}}])
    with pytest.raises(lg.Refused) as e:
        lg.wipe_from(tx, "demo")
    assert "지운 노드 0개가 내 이름 공간 노드 1개와 다르다" in e.value.problems[0]


def test_a_bridge_to_a_wrong_base_class_is_refused_before_writing():
    base, extra, graph = _files()
    organizer = next(n["props"]["id"] for n in graph["nodes"] if n["labels"] == ["Attendee"])
    graph["rels"].append({"type": "PLAYS", "a": organizer, "b": "sys:agent", "props": {}})           # PLAYS 의 끝은 Role 이어야 한다
    tx = FakeTx(BASE_NODES)
    with pytest.raises(lg.Refused) as e:
        lg.load_into(tx, graph, base, extra)
    assert "rel PLAYS" in e.value.problems[0] and "허용된 끝점" in e.value.problems[0] and tx.writes() == []


def test_an_old_load_under_another_class_is_caught_after_writing():
    """같은 id 가 예전에 다른 클래스로 적재돼 있으면 MERGE 가 노드를 하나 더 만든다 — 커밋 전 검사가 잡는다."""
    base, extra, graph = _files()

    class TwoNodesTx(FakeTx):
        def run(self, stmt, params=None):
            result = super().run(stmt, params)
            if stmt.startswith("MATCH (n) RETURN labels(n)"):
                return _Result(result.rows + [{"l": ["Objective"], "p": {"id": "demo:persp:customer", "name": "옛 적재", "ns": "demo"}}])
            return result

    with pytest.raises(lg.Refused) as e:
        lg.load_into(TwoNodesTx(BASE_NODES), graph, base, extra)
    assert any("같은 id 의 노드가 그래프에 2개" in p for p in e.value.problems)


def test_nodes_left_from_an_older_file_are_listed_not_deleted():
    base, extra, graph = _files()
    tx = FakeTx(BASE_NODES)
    lg.load_into(tx, graph, base, extra)
    removed = next(n for n in graph["nodes"] if n["props"]["id"] == "demo:att:han")
    graph["nodes"].remove(removed)
    graph["rels"] = [r for r in graph["rels"] if "demo:att:han" not in (r["a"], r["b"])]
    tx.nodes["demo:flow-node"] = {"labels": ["FlowNode", "Task"], "props": {"id": "demo:flow-node", "name": "투영", "taskType": "user", "ns": "demo",
                                                                           "source_type": lg.FLOW_SOURCE, "definition_id": "d"}}
    done = lg.load_into(tx, graph, base, extra)
    assert "demo:att:han" in tx.nodes                                                                # 지우지 않았다
    assert "node demo:att:han" in done["stale"] and not any("flow-node" in s for s in done["stale"])
    assert any(s.startswith("rel ") and "demo:att:han" in s for s in done["stale"])


# ---------------------------------------------------------------- 되돌리기
def test_wipe_removes_only_my_namespace_and_reports_flow_nodes():
    base, extra, graph = _files()
    tx = FakeTx(BASE_NODES + [{"labels": ["Role"], "props": {"id": "s02:m", "name": "다른 학생의 역할", "level": 1, "ns": "s02"}}])
    lg.load_into(tx, graph, base, extra)
    tx.nodes["demo:t"] = {"labels": ["FlowNode", "Task"], "props": {"id": "demo:t", "ns": "demo", "source_type": lg.FLOW_SOURCE}}
    done = lg.wipe_from(tx, "demo")
    assert done == {"knowledge": 65, "flow": 1}
    assert set(tx.nodes) == {"role:operator", "sys:agent", "s02:m"} and tx.rels == {}


def test_wipe_statement_is_scoped_to_the_namespace_parameter():
    """가짜 트랜잭션은 문장을 이름으로만 알아본다 — 지우는 문장이 ns 로 가리는지는 문장 글자로 고정한다(뜻은 라이브에서 실측)."""
    assert lg.WIPE == "MATCH (n {ns: $ns}) DETACH DELETE n"
    assert "{ns: $ns}" in lg.MINE


def test_wiping_an_empty_namespace_fails_instead_of_passing():
    tx = FakeTx(BASE_NODES)
    with pytest.raises(lg.Refused) as e:
        lg.wipe_from(tx, "demo")
    assert "0개다 — 되돌릴 것이 없다" in e.value.problems[0] and tx.writes() == []


def test_wipe_reports_nodes_with_my_prefix_it_could_not_delete():
    tx = FakeTx(BASE_NODES + [{"labels": ["Meeting"], "props": {"id": "demo:m", "name": "회의", "ns": "demo"}},
                              {"labels": ["Meeting"], "props": {"id": "demo:stray", "name": "ns 없는 것"}}])
    with pytest.raises(lg.Refused) as e:
        lg.wipe_from(tx, "demo")
    assert "node demo:stray: id 는 'demo:' 인데 ns 가 None 라 지우지 않았다" in e.value.problems[0]


# ---------------------------------------------------------------- 꼭 답할 질문
def test_example_questions_cover_the_nine_document_questions():
    questions = lg.read_questions(EX / "questions.cypher")
    asked = [line[2:].strip() for d in ("d1", "d2", "d3") for line in (EX / "docs" / f"{d}.md").read_text(encoding="utf-8").split("이 문서로 답할 질문")[1].splitlines()
             if line.startswith("- ")]
    assert len(asked) == 9 and len(questions) == 9
    for q, sentence in zip(questions, asked):
        assert sentence in q["ask"], (q["name"], sentence)


@pytest.mark.parametrize("text, phrase", [
    ("// 질문 없음\n", "질문이 0개다"),
    ("// @query a\n// @ask 무엇인가?\nMATCH (n:Meeting) RETURN n.name;\n", "$ns 를 쓰지 않는다"),
    ("// @query a\nMATCH (n {ns: $ns}) RETURN n.name;\n", "// @ask 질문 문장이 없다"),
    ("// @query a\n// @ask 무엇인가?\n", "Cypher 가 없다"),
    ("// @query a\n// @ask 무엇인가?\n// @params {\"ns\": \"s02\"}\nMATCH (n {ns: $ns}) RETURN n.name;\n", "@params 에 ns 를 적지 않는다"),
])
def test_question_files_must_ask_my_namespace(tmp_path, text, phrase):
    path = tmp_path / "questions.cypher"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(lg.GraphFileError) as e:
        lg.read_questions(path)
    assert phrase in "\n".join(e.value.problems)


def test_a_question_with_no_rows_is_not_answered():
    questions = lg.read_questions(EX / "questions.cypher")
    calls = []

    def run_read(cypher, params):
        calls.append(params)
        return [] if "room_capacity" in cypher else [{"x": 1}]

    results = lg.ask(run_read, questions, "demo")
    assert [r["name"] for r in results if not r["answered"]] == ["d1-room"]
    assert all(c["ns"] == "demo" for c in calls) and len(calls) == 9
