"""Choose host ports for Compose and Supabase before starting either stack.

Only host-side addresses change; container-to-container addresses stay the same.
The saved map is also consumed by check_windows.ps1. No services are started here.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
from urllib.parse import urlsplit, urlunsplit


DB_FIELDS = {
    ("api", "port"): 54321, ("db", "port"): 54322,
    ("db", "shadow_port"): 54320, ("db.pooler", "port"): 54329,
    ("studio", "port"): 54323, ("inbucket", "port"): 54324,
    ("inbucket", "smtp_port"): 54325, ("inbucket", "pop3_port"): 54326,
    ("analytics", "port"): 54327, ("analytics", "vector_port"): 54328,
}


def env_values(text):
    return {m[1]: m[2].strip().strip('"\'') for line in text.splitlines()
            if (m := re.match(r"^\s*([A-Z_0-9]+)\s*=\s*(.*?)\s*$", line))}


def set_values(text, updates):
    remaining = dict(updates)
    lines = []
    for line in text.splitlines():
        m = re.match(r"^\s*([A-Z_0-9]+)\s*=", line)
        if m and m[1] in updates:
            line = f"{m[1]}={updates[m[1]]}"
            remaining.pop(m[1], None)
        lines.append(line)
    lines.extend(f"{key}={value}" for key, value in remaining.items())
    return "\n".join(lines) + "\n"


def config_ports(text):
    section = ""
    result = {}
    for line in text.splitlines():
        if m := re.match(r"\s*\[([^]]+)\]", line):
            section = m[1]
        if m := re.match(r"\s*(\w+)\s*=\s*(\d+)", line):
            if (section, m[1]) in DB_FIELDS:
                result[DB_FIELDS[section, m[1]]] = int(m[2])
    if set(result) != set(DB_FIELDS.values()):
        raise RuntimeError("Supabase port configuration is incomplete")
    return result


def available(port):
    # Binding catches other Docker projects and Windows reserved ports as well
    # as ordinary processes; a process-name whitelist cannot distinguish them.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if os.name == "nt":
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            sock.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False


def docker_projects():
    """Inspect stopped containers and orphaned named volumes without reading container environment."""
    ids = subprocess.check_output(['docker', 'ps', '-aq'], text=True).split()
    labels = (subprocess.check_output(['docker', 'inspect', '--format', '{{json .Config.Labels}}', *ids], text=True)
              if ids else '')
    rows = [{'Config': {'Labels': json.loads(line)}} for line in labels.splitlines()]
    known_supa = {(row['Config']['Labels'] or {}).get('com.supabase.cli.project') for row in rows}
    known_compose = {(row['Config']['Labels'] or {}).get('com.docker.compose.project') for row in rows
                     if not (row['Config']['Labels'] or {}).get('com.supabase.cli.project')}
    volumes = subprocess.check_output(['docker', 'volume', 'ls', '-q'], text=True).splitlines()
    data = (subprocess.check_output(['docker', 'volume', 'inspect', '--format', '{{json .Labels}}', *volumes], text=True)
            if volumes else '')
    for line in data.splitlines():
        labels = json.loads(line) or {}
        supa = labels.get('com.supabase.cli.project')
        compose = labels.get('com.docker.compose.project')
        if (supa and supa not in known_supa) or (not supa and compose and compose not in known_compose):
            # A volume alone has no checkout path. Treat its owner as unknown,
            # so a fresh checkout chooses a different name rather than adopting it.
            rows.append({'Config': {'Labels': labels}})
    return rows


def project_names(root, compose_name, supabase_name, containers, *, saved, environment_name):
    """Choose unique names only for a new checkout; never redirect an existing installation."""
    normalize = lambda value: str(value or '').replace('\\', '/').rstrip('/').casefold()
    expected = normalize(root.as_posix())
    compose_owners, supabase_owners = {}, {}
    for container in containers:
        labels = container.get('Config', {}).get('Labels') or {}
        supa = labels.get('com.supabase.cli.project')
        if supa:
            supabase_owners.setdefault(supa, set()).add(normalize(labels.get('com.supabase.cli.workdir')))
        else:
            project = labels.get('com.docker.compose.project')
            if project:
                compose_owners.setdefault(project, set()).add(normalize(labels.get('com.docker.compose.project.working_dir')))
    compose_roots = compose_owners.get(compose_name, set())
    supabase_roots = supabase_owners.get(supabase_name, set())
    conflict_compose = bool(compose_roots - {expected})
    conflict_supabase = bool(supabase_roots - {expected + '/it'})
    # Normal stop_all keeps this checkout's Compose containers but Supabase
    # removes its containers while keeping volumes. The saved port map plus
    # an unambiguous same-checkout Compose owner ties that volume to this PC.
    if saved and compose_roots == {expected} and supabase_roots == {''}:
        conflict_supabase = False
    if not (conflict_compose or conflict_supabase):
        return compose_name, supabase_name
    if (saved or (conflict_compose and (expected in compose_roots or environment_name or expected + '/it' in supabase_roots))
            or (conflict_supabase and (expected in compose_roots or expected + '/it' in supabase_roots))):
        raise RuntimeError('다른 폴더의 기존 수업 프로젝트와 이름이 겹칩니다. 기존 데이터를 보존하려고 시작을 멈췄습니다.')
    suffix = hashlib.sha256(expected.encode('utf8')).hexdigest()[:10]
    def unique(base, owners):
        candidate = f'{base[:50]}-{suffix}'
        index = 1
        while candidate in owners:
            index += 1
            candidate = f'{base[:47]}-{suffix}-{index}'
        return candidate
    return (unique(compose_name, compose_owners) if conflict_compose else compose_name,
            unique(supabase_name, supabase_owners) if conflict_supabase else supabase_name)


def docker_ports(root, project_id):
    env_path = root / '.env'
    configured = env_values(env_path.read_text(encoding='utf-8-sig')) if env_path.exists() else {}
    compose_project = os.environ.get('COMPOSE_PROJECT_NAME') or configured.get('COMPOSE_PROJECT_NAME') or 'hyd-iot-edu'
    ids = subprocess.check_output(["docker", "ps", "-q"], text=True).split()
    owned, occupied = set(), set()
    if not ids:
        return owned, occupied
    containers = json.loads(subprocess.check_output(["docker", "inspect", *ids], text=True))
    for container in containers:
        labels = container["Config"].get("Labels") or {}
        workdir = labels.get("com.docker.compose.project.working_dir", "")
        same_root = workdir.replace("\\", "/").rstrip("/").casefold() == root.as_posix().casefold()
        own = (labels.get("com.docker.compose.project") == compose_project and same_root)
        supa_root = str(labels.get('com.supabase.cli.workdir') or '').replace('\\', '/').rstrip('/').casefold()
        own |= (labels.get('com.supabase.cli.project') == project_id and supa_root == root.as_posix().rstrip('/').casefold() + '/it')
        for bindings in (container["NetworkSettings"].get("Ports") or {}).values():
            for binding in bindings or []:
                port = int(binding["HostPort"])
                occupied.add(port)
                if own:
                    owned.add(port)
    return owned, occupied


def allocate(defaults, previous, owned, occupied, probe=available):
    selected = {}
    reserved = set(defaults)
    for default in sorted(defaults):
        current = int(previous.get(default, default))
        if not 1 <= current <= 65535:
            raise RuntimeError(f"Invalid saved port for {default}")
        def usable(port):
            return port not in selected.values() and ((port == current and port in owned) or (port not in occupied and probe(port)))
        if usable(current):
            selected[default] = current
            continue
        # Search the entire non-privileged range, including when a saved port
        # or the usual +10000 fallback is itself occupied.
        start = default + 10000 if default + 10000 <= 65535 else 1024
        for candidate in list(range(start, 65536)) + list(range(1024, start)):
            if candidate not in reserved and usable(candidate):
                selected[default] = candidate
                break
        else:
            raise RuntimeError(f"No free host port for {default}")
    return selected


def rewrite_url(value, replacements):
    """Only rewrite local host endpoints, preserving custom remote DB settings."""
    url = urlsplit(value)
    if url.hostname not in {"localhost", "127.0.0.1", "host.docker.internal"}:
        return value
    if url.port not in replacements:
        return value
    netloc = url.netloc.rsplit(":", 1)[0] + ":" + str(replacements[url.port])
    return urlunsplit(url._replace(netloc=netloc))


def update_config(text, ports, previous):
    section = ""
    lines = []
    for line in text.splitlines():
        if m := re.match(r"\s*\[([^]]+)\]", line):
            section = m[1]
        if m := re.match(r"(\s*)(\w+)(\s*=\s*)\d+(.*)", line):
            if (section, m[2]) in DB_FIELDS:
                line = f"{m[1]}{m[2]}{m[3]}{ports[DB_FIELDS[section, m[2]]]}{m[4]}"
        if section == "auth":
            line = re.sub(r'http://(localhost|127\.0\.0\.1):' + str(previous.get(8088, 8088)) + r'(?=[/"\s])',
                          lambda m: f"http://{m[1]}:{ports[8088]}", line)
        lines.append(line)
    return "\n".join(lines) + "\n"


def atomic_write(path, text):
    temp = path.with_name(path.name + ".ports-tmp")
    temp.write_text(text, encoding="utf-8", newline="\n")
    temp.replace(path)


def prepare(root):
    compose = (root / "compose.yaml").read_text(encoding="utf-8")
    service_ports = {int(p) for p in re.findall(r"\$\{HYD_PORT_(\d+):-", compose)}
    config_path = root / "it/supabase/config.toml"
    config = config_path.read_text(encoding="utf-8")
    project_id = re.search(r'^project_id\s*=\s*"([^"]+)"', config, re.M)[1]
    env_path = root / ".env"
    env_text = env_path.read_text(encoding="utf-8-sig")
    values = env_values(env_text)
    environment_name = os.environ.get('COMPOSE_PROJECT_NAME')
    compose_name = environment_name or values.get('COMPOSE_PROJECT_NAME') or 'hyd-iot-edu'
    actual_compose, actual_supabase = project_names(root, compose_name, project_id, docker_projects(),
        saved=(root / '.hyd-runtime/ports.json').exists(), environment_name=bool(environment_name))
    if actual_compose != compose_name:
        env_text = set_values(env_text, {'COMPOSE_PROJECT_NAME': actual_compose})
        values = env_values(env_text)
        print('다른 폴더의 기존 시스템과 분리해 이 폴더의 프로젝트 이름을 준비했습니다.')
    if actual_supabase != project_id:
        config = re.sub(r'^(project_id\s*=\s*)"[^"]+"', lambda m: m[1] + '"' + actual_supabase + '"', config, count=1, flags=re.M)
        project_id = actual_supabase
        print('다른 폴더의 기존 업무 DB와 분리해 이 폴더의 프로젝트 이름을 준비했습니다.')
    previous = {p: int(values.get(f"HYD_PORT_{p}", p)) for p in service_ports}
    previous.update(config_ports(config))
    owned, occupied = docker_ports(root, project_id)
    ports = allocate(service_ports | set(DB_FIELDS.values()), previous, owned, occupied)
    updates = {f"HYD_PORT_{p}": str(port) for p, port in ports.items()}
    updates["HYD_PORTS"] = '"' + " ".join(f"{p}={port}" for p, port in ports.items() if p != port) + '"'
    for key, default in {
        "SUPABASE_DSN": "postgresql://postgres:postgres@host.docker.internal:54322/postgres",
        "ENTERPRISE_READ_DSN": "postgresql://hyd_enterprise_reader:hyd-enterprise-read-local@host.docker.internal:54322/postgres",
        "HYD_MCP_OAUTH_CALLBACK_URL": "http://localhost:8088/api/mcp/connections/callback",
    }.items():
        replacements = {54322: ports[54322], 8088: ports[8088],
                        previous[54322]: ports[54322], previous[8088]: ports[8088]}
        updates[key] = rewrite_url(values.get(key, default), replacements)
    if values.get("EFFECTS_SMTP_PORT", str(previous[54325])) == str(previous[54325]):
        updates["EFFECTS_SMTP_PORT"] = str(ports[54325])
    # Host-worker rewrites use host ports; internal Docker endpoints are kept.
    if "MCP_HOST_REWRITE" in values:
        rewrite = values["MCP_HOST_REWRITE"]
        for p in (7687, 8199, 8198, 8196, 8195):
            rewrite = re.sub(r"(=127\.0\.0\.1:)" + str(previous[p]) + r"(?=,|$)",
                             lambda m: m[1] + str(ports[p]), rewrite)
        updates["MCP_HOST_REWRITE"] = rewrite
    runtime = root / ".hyd-runtime"
    runtime.mkdir(exist_ok=True)
    atomic_write(config_path, update_config(config, ports, previous))
    atomic_write(env_path, set_values(env_text, updates))
    atomic_write(runtime / "ports.json", json.dumps(ports, indent=2) + "\n")
    for default, port in ports.items():
        if default != port:
            print(f"Host port {default} -> {port}")


if __name__ == "__main__":
    try:
        prepare(Path(__file__).resolve().parents[1])
    except Exception as exc:
        # Environment values and command output may contain credentials.
        if isinstance(exc, RuntimeError) and str(exc).startswith('다른 폴더의 기존 수업 프로젝트'):
            print(str(exc), file=sys.stderr)
        else:
            print("Port preparation failed; check Docker, Python and writable project files.", file=sys.stderr)
        sys.exit(1)
