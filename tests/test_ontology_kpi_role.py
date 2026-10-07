"""Measure.kpiRole (A144, sweep item 37 / D02): the BSC leading/lagging role is declared in schema.json, every seed
Measure carries one, the roles agree with the INFLUENCES causality (lagging never drives leading; every leading reaches a
lagging), the validator and the seed read-back cover it, and the semantic audit asks about it."""
import ast
import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ontology_v2_kpi", ROOT / "scripts" / "ontology_v2.py")
ov = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ov)
S = ov.load_schema()
INSTANCES = (ov.V2 / "instances.cypher").read_text(encoding="utf-8")


def _node(labels, **props):
    return {"labels": labels, "props": props}


def _rel(t, a, la, b, lb, **props):
    return {"type": t, "a": a, "b": b, "la": la, "lb": lb, "props": props}


def _measure(mid, role, direction="UP"):
    return _node(["Measure"], id=mid, name=mid, unit="%", direction=direction, kpiRole=role)


def _influences(a, b):
    return _rel("INFLUENCES", a, ["Measure"], b, ["Measure"], sign=1)


def _cypher_list(block: str):
    """Parse a Cypher UNWIND [...] literal of strings/numbers/null/lists into Python."""
    return ast.literal_eval(block.replace("null", "None"))


def _unwind_block(after_marker: str, before_marker: str) -> str:
    """The `UNWIND [ … ] AS r` literal that follows `after_marker` and precedes the line starting with `before_marker`."""
    lines = INSTANCES.splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith(after_marker))
    first = next(i for i in range(start, len(lines)) if lines[i].startswith("UNWIND ["))
    last = next(i for i in range(first, len(lines)) if lines[i + 1].startswith(before_marker))
    body = "\n".join(lines[first:last + 1])
    body = body[len("UNWIND "):]
    assert body.endswith("] AS r"), body[-30:]
    return re.sub(r"//[^\n]*", "", body[:-len(" AS r")])    # trailing `// 조건:` comments inside the list


def seed_measures():
    header = next(l for l in INSTANCES.splitlines() if l.startswith("// BSC 성과 지표: ["))
    cols = [c.strip() for c in header.split("[", 1)[1].split("]", 1)[0].split(",")]
    return cols, _cypher_list(_unwind_block("// BSC 성과 지표: [", "MERGE (n:Measure {id: r[0]})"))


def seed_influences():
    return _cypher_list(_unwind_block("// 상충 관계 (성과 지표 → 성과 지표)", "MATCH (a:Measure {id: r[0]}), (b:Measure {id: r[1]})"))


def test_schema_declares_kpi_role_as_a_required_enum():
    prop = next(p for p in ov.classes_by_name(S)["Measure"]["properties"] if p["name"] == "kpiRole")
    assert prop["type"] == "enum" and prop["values"] == ["leading", "lagging"] and prop["required"] is True
    assert "kpiRole![leading|lagging]" in (ov.V2 / "schema_prompt.md").read_text(encoding="utf-8")


def test_every_seed_measure_has_a_role_and_the_roles_follow_the_strategy_map():
    cols, rows = seed_measures()
    assert cols[-1] == "kpiRole" and len(rows) == 21
    role = {r[0]: r[cols.index("kpiRole")] for r in rows}
    assert set(role.values()) == {"leading", "lagging"}
    # BSC: financial/customer outcomes are lagging, internal-process/learning drivers are leading (instances.cypher objectives)
    obj = {r[0]: r[cols.index("objective")] for r in rows}
    lagging_objectives = {"obj:profit", "obj:cost", "obj:delivery", "obj:quality"}
    for mid, r in role.items():
        if r == "lagging":
            assert obj[mid] in lagging_objectives, (mid, obj[mid])
    assert role["msr:op-profit"] == "lagging" and role["msr:availability"] == "leading" and role["msr:precedent"] == "leading"
    nodes = [_measure(mid, r) for mid, r in role.items()]
    rels = [_influences(a, b) for a, b, *_ in seed_influences()]
    assert ov.kpi_role_integrity(nodes, rels) == []
    assert "SET n.name = r[1]" in INSTANCES and "n.kpiRole = r[10]" in INSTANCES


def test_validator_requires_kpi_role_and_catches_causality_violations():
    missing = _node(["Measure"], id="msr:m", name="M", unit="%", direction="UP")
    assert "필수 속성 kpiRole 없음" in "\n".join(ov.validate([missing], [], S))
    bad_enum = _measure("msr:m", "driver")
    assert "kpiRole='driver'" in "\n".join(ov.validate([bad_enum], [], S))
    # lagging -> leading edge
    nodes = [_measure("msr:profit", "lagging"), _measure("msr:avail", "leading"), _measure("msr:rev", "lagging")]
    errs = "\n".join(ov.validate(nodes, [_influences("msr:profit", "msr:avail"), _influences("msr:avail", "msr:rev")], S))
    assert "후행(lagging) 지표가 선행(leading) 지표 msr:avail에 INFLUENCES" in errs
    # leading that reaches nothing lagging (only another leading, or nothing)
    nodes = [_measure("msr:a", "leading"), _measure("msr:b", "leading"), _measure("msr:c", "lagging")]
    errs = "\n".join(ov.validate(nodes, [_influences("msr:a", "msr:b")], S))
    assert "msr:a: 선행(leading) 지표인데" in errs and "msr:b: 선행(leading) 지표인데" in errs
    assert ov.validate(nodes, [_influences("msr:a", "msr:b"), _influences("msr:b", "msr:c")], S) == []
    # a cycle among leading measures must not hang the reachability walk
    cyc = [_measure("msr:x", "leading"), _measure("msr:y", "leading")]
    assert "msr:x" in "\n".join(ov.kpi_role_integrity(cyc, [_influences("msr:x", "msr:y"), _influences("msr:y", "msr:x")]))


def test_seed_read_back_covers_every_label_the_seed_files_merge_and_the_kpi_role():
    checks = (ov.V2 / "seed_checks.cypher").read_text(encoding="utf-8")
    queries = [l for l in checks.splitlines() if l.strip() and not l.startswith("//")]
    assert all(q.startswith("MATCH") and "AS problem" in q for q in queries) and len(queries) >= 10
    merged = set()
    for f in ("instances.cypher", "knowledge_a098.cypher"):
        code = "\n".join(l for l in (ov.V2 / f).read_text(encoding="utf-8").splitlines() if not l.strip().startswith("//"))
        merged |= set(re.findall(r"MERGE \(\s*\w*\s*:(\w+)", code)) | set(re.findall(r"SET \w+:(\w+)", code))
    listed = set(re.findall(r"'([A-Za-z]+)'", queries[0]))
    assert merged <= listed, merged - listed
    assert any("kpiRole IS NULL" in q for q in queries) and any("kpiRole:'lagging'" in q and "kpiRole:'leading'" in q for q in queries)
    seed_sh = (ROOT / "it" / "neo4j" / "seed.sh").read_text(encoding="utf-8")
    assert "seed_checks.cypher" in seed_sh and 'exit 1' in seed_sh


def test_semantic_audit_asks_the_kpi_role_question():
    text = (ROOT / "scripts" / "probe_semantic_links.py").read_text(encoding="utf-8")
    assert "Q23 BSC kpiRole" in text and "kpiRole:'lagging'" in text
