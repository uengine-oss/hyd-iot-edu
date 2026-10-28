"""AI 워커 컨테이너 이미지(it/agent-worker/Dockerfile)가 워커가 실제로 부르는 procsvc 모듈과 그 모듈의 외부 패키지를 모두 싣는가.

2026-10-25 강의실 조건 점검: Dockerfile 이 procsvc 파일 여섯 개만 골라 복사해, procdb 가 새로 부르는 approval_store 등이 빠져
컨테이너 워커가 켜지자마자 ModuleNotFoundError 로 재시작을 반복했다(호스트 워커는 저장소 전체를 보므로 드러나지 않았다).
mcp_check 가 쓰는 jsonschema 도 워커 요구 파일에 없었다(실행마다 bridge._written_secrets 가 부른다)."""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "it/agent-worker/worker"
PROCSVC = ROOT / "it/process/procsvc"
DOCKERFILE = ROOT / "it/agent-worker/Dockerfile"
REQUIREMENTS = ROOT / "it/agent-worker/requirements.txt"
# 요구 파일의 패키지가 함께 싣는 모듈(jsonschema → referencing) · 이미지가 따로 복사하는 모듈
BUNDLED = {"jsonschema": {"jsonschema", "referencing"}, "psycopg": {"psycopg"}}
COPIED = {"hydcommon", "procsvc", "worker"}


def test_worker_sql_evidence_guard_uses_same_pinned_parser_as_process():
    process = (ROOT/'it/process/requirements.txt').read_text(encoding='utf8')
    worker = REQUIREMENTS.read_text(encoding='utf8')
    pattern = r'^sqlglot==([^\s#]+)'
    assert re.search(pattern, process, re.M).group(1) == re.search(pattern, worker, re.M).group(1)


def test_worker_build_rejects_node_before_security_release():
    import shutil
    import subprocess
    node = shutil.which('node')
    assert node, 'Node is required to execute the Dockerfile version guard'
    source = DOCKERFILE.read_text(encoding='utf-8')
    guard = re.search(r'node -e "([^"]+)"', source).group(1)
    # Same LTS line and floor as the classroom PCs (install_windows.ps1 · install_macos.sh · README: 24.22.1).
    for version, expected in [('24.22.0', False), ('24.22.1', True), ('24.23.0', True), ('22.23.4', False), ('26.12.1', False), ('18.20.8', False)]:
        code = guard.replace('process.versions.node', repr(version))
        result = subprocess.run([node, '-e', code], capture_output=True)
        assert (result.returncode == 0) is expected, version


def _imports(path: Path, top_level_only: bool) -> list[tuple[str, int, list[str]]]:
    """(모듈, 상대 단계, 가져온 이름) — top_level_only 면 모듈 몸통의 import 만(함수 안의 늦은 import 는 뺀다)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    nodes = tree.body if top_level_only else list(ast.walk(tree))
    out = []
    for n in nodes:
        if isinstance(n, ast.ImportFrom):
            out.append((n.module or "", n.level, [a.name for a in n.names]))
        elif isinstance(n, ast.Import):
            out += [(a.name, 0, []) for a in n.names]
    return out


def _procsvc_refs(mod: str, level: int, names: list[str], inside_procsvc: bool) -> set[str]:
    if level and inside_procsvc:
        return {mod.split(".")[0]} if mod else set(names)
    if mod == "procsvc":
        return set(names)
    if mod.startswith("procsvc."):
        return {mod.split(".")[1]}
    return set()


def worker_closure() -> tuple[set[str], set[str]]:
    """워커가 부르는 procsvc 모듈(워커 코드의 모든 import + 그 모듈들의 몸통 import 를 따라간 닫힘)과 그 닫힘의 외부 최상위 패키지."""
    todo, external = set(), set()
    for f in WORKER.rglob("*.py"):
        for mod, level, names in _imports(f, top_level_only=False):
            todo |= _procsvc_refs(mod, level, names, inside_procsvc=False)
    seen: set[str] = set()
    while todo:
        m = todo.pop()
        if m in seen or not (PROCSVC / f"{m}.py").exists():
            continue
        seen.add(m)
        for mod, level, names in _imports(PROCSVC / f"{m}.py", top_level_only=True):
            refs = _procsvc_refs(mod, level, names, inside_procsvc=True)
            if refs:
                todo |= {r for r in refs if (PROCSVC / f"{r}.py").exists()}
            elif not level:
                external.add(mod.split(".")[0])
    return seen, external


def test_the_worker_image_copies_every_procsvc_module_the_worker_imports():
    copies = re.findall(r"^COPY\s+(\S+)\s+(\S+)", DOCKERFILE.read_text(encoding="utf-8"), re.M)
    whole = any(src.rstrip("/") == "it/process/procsvc" and dst.rstrip("/") == "/srv/procsvc" for src, dst in copies)
    files = {Path(src).stem for src, dst in copies if src.startswith("it/process/procsvc/") and dst.startswith("/srv/procsvc/")}
    modules, _ = worker_closure()
    assert {"procdb", "approval_store", "mcp_check", "result_correction"} <= modules     # 닫힘 계산이 실제로 따라갔는가
    missing = sorted(m for m in modules if not whole and m not in files)
    assert not missing, f"it/agent-worker/Dockerfile 이 복사하지 않는 procsvc 모듈: {missing}"


def test_the_worker_requirements_cover_the_third_party_imports_of_that_closure():
    pins = {re.split(r"[\[=<>~ ]", line.strip())[0].lower() for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#") and not line.startswith("git+")}
    provided = set().union(*(BUNDLED.get(p, {p}) for p in pins)) | COPIED
    _, external = worker_closure()
    third_party = {m for m in external if m not in sys.stdlib_module_names and m != "__future__"}
    assert not third_party - provided, f"it/agent-worker/requirements.txt 에 없는 패키지: {sorted(third_party - provided)}"
